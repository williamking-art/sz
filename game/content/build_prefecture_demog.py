# -*- coding: utf-8 -*-
"""宋祚 · 州府级人口经济表生成器（P0/A2 · 2026-10-02）

**为什么需要它**：州府级人口经济数据（面积 × 史实锚点权重）已由
`content/demography.py` + `build_map_basemap.py` 产出到
`assets/map/web/prefectures.geojson`——但那是**生成物**（`.gitignore` 忽略），
运行时依赖它会让游戏在没跑过地图构建的机器上读不到数据。

本脚本把该生成物**固化为入库的 Python 表** `content/data_prefecture_demog.py`，
使运行时不依赖任何生成文件，且数值可评审、可 diff、可回归。

**口径（不得改动，否则破坏与既有测试的一致性）**：
- 拆分逻辑复用 `content.demography.split_circuit_demog_scoped`（面积 × `SONG_SEAT_WEIGHTS`）；
- **省级归入**（无地图府块的 11 席）的份额**留在路级作 `residual`**，不摊给邻府；
- 恒等式：`Σ(府块) + 路级 residual == 路级总量`（逐维、拾整后精确）。

**用法**（在 `game/` 下，先跑 `build_map_basemap.py` 产出 geojson）：
    python content/build_prefecture_demog.py
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GAME = os.path.dirname(_HERE)
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from content.data import PREFECTURE_INFO                      # noqa: E402
from content.data_households_hist import hist_households_of  # noqa: E402
from content.demography import (                              # noqa: E402
    EXTRA_CIRCUIT_DEMOG, SONG_SEAT_WEIGHTS,
)
from content.geo_admin import CIRCUIT_INFO                    # noqa: E402

#: 数值依据（写进生成表，供 `core/prefecture_entity` **单一来源**读取，不再二次推断）
BASIS_HISTORICAL = "historical"      # 该路席位齐全且已录史料 ⇒ 按**崇宁户比例**分配
BASIS_AREA_ANCHOR = "area_x_anchor"  # 回退：面积 × 史实锚点权重（该席是锚点）
BASIS_AREA_ONLY = "area_only"        # 回退：面积 × 1.0（**面积估计，精度低**）
BASIS_MERGED = "merged"              # 省级归入：无府块、无数值

_GEOJSON = os.path.join(_GAME, "assets", "map", "web", "prefectures.geojson")
_LEDGER = os.path.join(_GAME, "assets", "map", "web", "circuit_seat_ledger.json")
_OUT = os.path.join(_HERE, "data_prefecture_demog.py")

_DIMS = ("population", "households", "land", "grain", "monthly_tax")


def _polygon_area(ring) -> float:
    """平面多边形面积（度²，鞋带公式）。仅用于**相对**权重，故不需投影校正。"""
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _feature_area(feat) -> float:
    g = feat.get("geometry") or {}
    t = g.get("type")
    if t == "Polygon":
        return sum(_polygon_area(r) for r in g.get("coordinates") or [])
    if t == "MultiPolygon":
        return sum(_polygon_area(r) for poly in g.get("coordinates") or [] for r in poly)
    return 0.0


def _hist_split(circuit: str, base: dict, names: list, weights: dict) -> dict:
    """按**史料户数比例**把路级总量分到各治所（尾差归最大权重块）。

    口径：史料值**只作相对权重**（游戏路级户口远大于史料，绝对值不可用）；
    逐维 `Σ子 == 父级`（拾整后精确）。
    """
    tot = sum(weights[n] for n in names) or 1
    anchor = max(names, key=lambda n: weights[n])
    out: dict = {n: {} for n in names}
    for dim in _DIMS:
        v = base.get(dim)
        if v is None:
            continue
        parts = {n: round(v * weights[n] / tot) for n in names}
        parts[anchor] += v - sum(parts.values())
        for n, val in parts.items():
            out[n][dim] = int(val)
    for k, v in (base.get("yields") or {}).items():
        parts = {n: round(v * weights[n] / tot) for n in names}
        parts[anchor] += v - sum(parts.values())
        for n, val in parts.items():
            out[n].setdefault("yields", {})[k] = int(val)
    return out


def build() -> dict:
    """返回 {seats: {路: [{name, blocked, basis, demog}]}, residuals: {...}}。"""
    gj = json.load(open(_GEOJSON, encoding="utf-8"))
    features = gj.get("features") or []
    # 府块：名称 → 面积 / 经济属性
    area_of = {}
    econ_of = {}
    for f in features:
        pr = f.get("properties") or {}
        nm = pr.get("name")
        if not nm:
            continue
        area_of[nm] = _feature_area(f)
        econ_of[nm] = pr

    seats_by_circuit = {}
    residuals = {}
    hist_circuits = []
    for circuit, info in CIRCUIT_INFO.items():
        members = [m[0] for m in (info.get("members") or [])]
        if not members:
            continue
        base = PREFECTURE_INFO.get(circuit) or EXTRA_CIRCUIT_DEMOG.get(circuit)
        blocked = [n for n in members if n in area_of]
        merged = [n for n in members if n not in area_of]
        # 该路可否用史料？**必须席位齐全**（部分覆盖会让同路两种口径混用，语义不清）
        _hu = {n: hist_households_of(n) for n in blocked}
        use_hist = bool(blocked) and all(_hu.get(n) for n in blocked) and base is not None
        rows = []
        if use_hist:
            hist_circuits.append(circuit)
            split = _hist_split(circuit, base, blocked, _hu)
            for n in blocked:
                row = {"name": n, "blocked": True, "basis": BASIS_HISTORICAL}
                row.update(split.get(n, {}))
                rows.append(row)
        else:
            for n in blocked:
                e = econ_of[n]
                row = {"name": n, "blocked": True,
                       "basis": BASIS_AREA_ANCHOR if n in SONG_SEAT_WEIGHTS else BASIS_AREA_ONLY}
                for d in _DIMS:
                    if e.get(d) is not None:
                        row[d] = int(e[d])
                ys = e.get("yields") or {}
                if ys:
                    row["yields"] = {k: int(v) for k, v in sorted(ys.items()) if v}
                rows.append(row)
        for n in merged:
            rows.append({"name": n, "blocked": False, "basis": BASIS_MERGED,
                         "note": "省级归入：无地图府块，份额留路级 residual"})
        # 路级 residual：由恒等式反推（父级 − Σ有块），不另算一遍权重，避免分叉
        if base is not None:
            res = {}
            for d in _DIMS:
                pv = base.get(d)
                if pv is None:
                    continue
                got = sum(r.get(d, 0) or 0 for r in rows if r["blocked"])
                res[d] = int(pv) - got
            ys = {}
            for k, v in sorted((base.get("yields") or {}).items()):
                got = sum((r.get("yields") or {}).get(k, 0) or 0 for r in rows if r["blocked"])
                ys[k] = int(v) - got
            if ys:
                res["yields"] = ys
            residuals[circuit] = res
        seats_by_circuit[circuit] = rows
    return {"seats": seats_by_circuit, "residuals": residuals, "areas": area_of,
            "weights": dict(SONG_SEAT_WEIGHTS), "hist_circuits": hist_circuits}


def _fmt(d: dict, indent: int = 8) -> str:
    pad = " " * indent
    items = []
    for k, v in d.items():
        key = json.dumps(str(k), ensure_ascii=False)
        if isinstance(v, dict):
            body = ", ".join(f"{json.dumps(str(a), ensure_ascii=False)}: {b}"
                             for a, b in v.items())
            items.append(f"{pad}{key}: {{{body}}}")
        elif isinstance(v, bool) or isinstance(v, (int, float)):
            items.append(f"{pad}{key}: {v!r}")
        else:
            # ⚠️ 字符串必须加引号——否则生成物是**语法错误**的 Python（曾踩）
            items.append(f"{pad}{key}: {json.dumps(str(v), ensure_ascii=False)}")
    return ",\n".join(items)


def emit(data: dict) -> str:
    L = []
    L.append('# -*- coding: utf-8 -*-')
    L.append('"""宋祚 · 州府级人口经济表（**生成物，勿手改**）')
    L.append("")
    L.append("由 `content/build_prefecture_demog.py` 生成；口径见该脚本 docstring。")
    L.append("")
    L.append("· 拆分依据：**已录史料的路（席位齐全）按《宋史·地理志》崇宁户比例**分配")
    L.append('（`basis="historical"`）；其余回退**地图府块面积 × `SONG_SEAT_WEIGHTS` 锚点权重**')
    L.append("（`area_x_anchor` / `area_only`，后者是**面积估计、精度低**）。")
    L.append("史料值**只作相对权重**，绝对值不可用（游戏量级远大于史料）；")
    L.append("设计文档 §4.2 禁止按面积随意拆分，故 `basis` 必须如实标注、下游不得混用。")
    L.append("· `PREFECTURE_SEATS[路]` = 该路治所清单；`blocked=True` 者有经济数据；")
    L.append("· `blocked=False` 者为**省级归入**（无地图府块），其份额留在 `PREFECTURE_RESIDUAL`；")
    L.append("· 恒等式：`Σ(blocked 各维) + PREFECTURE_RESIDUAL[路][维] == PREFECTURE_INFO[路][维]`。")
    L.append('"""')
    L.append("from __future__ import annotations")
    L.append("")
    L.append("__all__ = [\"PREFECTURE_SEATS\", \"PREFECTURE_RESIDUAL\", \"PREFECTURE_SEAT_COUNT\"]")
    L.append("")
    tot = sum(len(v) for v in data["seats"].values())
    blocked = sum(1 for v in data["seats"].values() for r in v if r["blocked"])
    hist = sum(1 for v in data["seats"].values() for r in v
               if r.get("basis") == BASIS_HISTORICAL)
    L.append(f"#: 治所总数 {tot}（有块 {blocked} / 省级归入 {tot - blocked}），路数 {len(data['seats'])}")
    L.append(f"#: 其中 **史料口径 {hist} 席**（余 {blocked - hist} 席为面积估计，精度低）")
    L.append("PREFECTURE_SEAT_COUNT = {")
    L.append(f'    "seats": {tot}, "blocked": {blocked}, "merged": {tot - blocked},')
    L.append(f'    "historical": {hist}, "circuits": {len(data["seats"])},')
    L.append(f'    "hist_circuits": {len(data.get("hist_circuits") or [])},')
    L.append("}")
    L.append("")
    L.append("#: 治所名 → 路名（反向索引，供 `circuit_of()` 同源使用）")
    L.append("SEAT_TO_CIRCUIT = {")
    for c, rows in data["seats"].items():
        for r in rows:
            L.append(f'    "{r["name"]}": "{c}",')
    L.append("}")
    L.append("")
    L.append("PREFECTURE_SEATS: dict[str, list[dict]] = {")
    for c, rows in data["seats"].items():
        L.append(f'    "{c}": [')
        for r in rows:
            L.append("        {" + _fmt(r, 0).replace("\n", " ").lstrip() + "},")
        L.append("    ],")
    L.append("}")
    L.append("")
    L.append("#: 路级未摊派残差（省级归入席的份额；**不摊给邻府**）")
    L.append("PREFECTURE_RESIDUAL: dict[str, dict] = {")
    for c, res in data["residuals"].items():
        L.append(f'    "{c}": {{')
        for k, v in res.items():
            if isinstance(v, dict):
                L.append(f'        "{k}": {{' + ", ".join(f'"{a}": {b}' for a, b in v.items()) + "},")
            else:
                L.append(f'        "{k}": {v},')
        L.append("    },")
    L.append("}")
    L.append("")
    return "\n".join(L)


def verify(data: dict) -> list:
    """恒等式自检：Σ(有块各维) + residual == 路级总量（逐路逐维）。"""
    bad = []
    for c, rows in data["seats"].items():
        base = PREFECTURE_INFO.get(c) or EXTRA_CIRCUIT_DEMOG.get(c)
        if base is None:
            continue
        res = data["residuals"].get(c, {})
        for d in _DIMS:
            pv = base.get(d)
            if pv is None:
                continue
            got = sum(r.get(d, 0) or 0 for r in rows if r["blocked"]) + int(res.get(d, 0) or 0)
            if abs(got - int(pv)) > 1:
                bad.append(f"{c}/{d}: Σ{got} vs 父级 {pv}")
        for k, v in (base.get("yields") or {}).items():
            got = sum((r.get("yields") or {}).get(k, 0) or 0 for r in rows if r["blocked"]) \
                + int((res.get("yields") or {}).get(k, 0) or 0)
            if abs(got - int(v)) > 1:
                bad.append(f"{c}/yields.{k}: Σ{got} vs 父级 {v}")
    return bad


def main() -> int:
    if not os.path.exists(_GEOJSON):
        print(f"[pref-demog] 缺少 {_GEOJSON}——请先在 game/ 下运行 build_map_basemap.py", file=sys.stderr)
        return 2
    data = build()
    bad = verify(data)
    if bad:
        print("[pref-demog] 恒等式不成立，拒绝写出：", file=sys.stderr)
        for b in bad[:12]:
            print("  " + b, file=sys.stderr)
        return 1
    with open(_OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(emit(data))
    tot = sum(len(v) for v in data["seats"].values())
    blocked = sum(1 for v in data["seats"].values() for r in v if r["blocked"])
    print(f"[pref-demog] 已写出 {_OUT}")
    print(f"[pref-demog] 治所 {tot}（有块 {blocked} / 省级归入 {tot - blocked}）"
          f"，路数 {len(data['seats'])}，恒等式 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
