# -*- coding: utf-8 -*-
"""宋祚 · 州府实体层（P0/A2 · 2026-10-02）

**定位**：把"州府"确立为**一级可寻址的经济实体**，为 `market-civilian-economy`
之后的 P0–P2（空间可达性 / 纵向切片 / 建筑—经营并轨）提供稳定主键与派生读数。
本模块**只读**：不写 `state`、不落档、不改任何既有结算。

## 数据来源（两级，各自权威）

| 层级 | 权威 | 内容 |
|---|---|---|
| **身份**（名/路/等级/经纬） | `content.geo_admin.CIRCUIT_INFO.members` | 137 治所，**实测地图点** |
| **人口经济**（人口/户/田/粮/税/产出） | `content.data_prefecture_demog` | 由 `content/build_prefecture_demog.py` 生成 |
| **路级总量**（父级真账） | `content.data.PREFECTURE_INFO` | 20 路 |

## 拆分口径与**精度声明**（务必读；设计文档 §4.2 明令不得伪造精度）

拆分 = **地图府块真实面积 × `SONG_SEAT_WEIGHTS` 史实锚点权重**，尾差归最大块，
`Σ(有块) + 路级 residual == 路级总量`（逐维精确，有回归守）。

⚠️ **精度边界（如实声明，不得含糊）**：
- `SONG_SEAT_WEIGHTS` 只标了 **约 25 个重镇**（开封府 1.6、杭州 1.4…），
  其余**默认 1.0** ⇒ 对**大部分州**，该拆分**实际退化为"按面积"**。
- 设计文档 §4.2 要求"**不得按地图面积或等比例随意拆分**"。
  故本层给每个数值附 **`basis`** 字段：
  - `"area_x_anchor"`：该州是**权重锚点**（有史实依据的加成）
  - `"area_only"` ⚠️：该州**无锚点**，数值实为**面积估计**（精度低）
  - `"merged"`：省级归入席（**无经济数值**，份额留在路级 `residual`）
- **实测偏差证据**：京畿路下 开封府 74.3 万 < 陈州 277 万——而史实开封府（崇宁）户数
  冠绝天下。根因即"锚点 1.6 不足以补偿其**面积极小**"。
  ⇒ **下游若需要真实精度，应改用史料户口（《宋史·地理志》崇宁户数）替换本表**；
  在替换前，本层数值只能作**量级参考**，不得当"已下沉的史料级州府数据"呈现。

## 与路级的关系（单向派生，禁止双账）

路级 = `Σ(下辖有块州府) + residual`，是**聚合读数**，不是第二份可独立结算的真账。
`circuit_aggregate()` 每次现算并与 `PREFECTURE_INFO` 断言一致；不一致即 raise（不静默）。
"""
from __future__ import annotations

from functools import lru_cache as _lru_cache
from typing import Any, Dict, List, Optional

__all__ = [
    "BASIS_HISTORICAL", "BASIS_AREA_ANCHOR", "BASIS_AREA_ONLY", "BASIS_MERGED",
    "SEAT_LEVELS", "ANCHOR_WEIGHTS", "seat_id_of", "split_seat_id",
    "all_seats", "seats_of", "circuit_of", "seat_entity",
    "prefecture_demog", "circuit_aggregate", "coverage_report",
    "duplicate_display_names",
]

#: ✅ 数值依据：该路席位齐全且**已录史料** ⇒ 按《宋史·地理志》崇宁户**比例**分配
BASIS_HISTORICAL = "historical"
#: 数值依据：该州是 `SONG_SEAT_WEIGHTS` 里的史实锚点（加成有据，但仍是面积法）
BASIS_AREA_ANCHOR = "area_x_anchor"
#: ⚠️ 数值依据：该州**既无史料也无锚点**，实为**面积估计**（精度低）
BASIS_AREA_ONLY = "area_only"
#: 省级归入：无地图府块 ⇒ **无经济数值**，份额留在路级 residual
BASIS_MERGED = "merged"

#: ⚠️ **主键是限定名 `路|治所`，不是显示名**——实测 `颍昌府` 同时出现在
#: **京畿路与京西路**的成员表里（136 唯一名 / 137 席）⇒ 显示名**不唯一**。
#: 设计文档 §4.10 明确要求「采用**稳定地域 ID**，而不是仅靠显示地名或所属路名」；
#: 本项目当前以 `路|治所` 作稳定 ID（路名与成员表均已入库、变动受测试守护）。
_SEP = "|"


def seat_id_of(circuit: str, seat: str) -> str:
    """构造稳定主键 `路|治所`（**唯一**，可作 dict 键与存档键）。"""
    return f"{circuit}{_SEP}{seat}"


def split_seat_id(seat_id: str):
    """`路|治所` → `(路, 治所)`；格式非法返回 `(None, None)`（缺失≠猜）。"""
    if not isinstance(seat_id, str) or _SEP not in seat_id:
        return None, None
    c, s = seat_id.split(_SEP, 1)
    return (c or None), (s or None)


def duplicate_display_names() -> Dict[str, List[str]]:
    """显示名**跨路重名**清单（如实报出，供上层决定是否消歧）。"""
    seen: Dict[str, List[str]] = {}
    for s in all_seats():
        seen.setdefault(s["seat"], []).append(s["circuit"])
    return {k: v for k, v in seen.items() if len(v) > 1}


#: 数值依据：该州是 `SONG_SEAT_WEIGHTS` 里的史实锚点（加成有据）
BASIS_AREA_ANCHOR = "area_x_anchor"
#: ⚠️ 数值依据：该州**无锚点**，实为**面积估计**（精度低，设计文档禁止的口径）
BASIS_AREA_ONLY = "area_only"
#: 省级归入：无地图府块 ⇒ **无经济数值**，份额留在路级 residual
BASIS_MERGED = "merged"

#: 州府等级（来自地图点位，非经济口径）
SEAT_LEVELS = ("京府", "府", "州", "军", "部")


def _geo():
    from content.geo_admin import CIRCUIT_INFO
    return CIRCUIT_INFO


def ANCHOR_WEIGHTS() -> Dict[str, float]:      # noqa: N802 — 与既有 `SONG_SEAT_WEIGHTS` 同义
    """史实锚点权重（只读副本）。"""
    from content.demography import SONG_SEAT_WEIGHTS
    return dict(SONG_SEAT_WEIGHTS)


def _table():
    from content import data_prefecture_demog as T
    return T


@_lru_cache(maxsize=4)
def _all_seats_cached(include_merged: bool = True) -> tuple:
    """治所实体表的**只读缓存**（源数据来自 content 静态表，不随回合变化）。

    2026-10-18 全审性能修复：`all_seats()` 此前每次从静态表重建 136 个 dict，
    240 月结算中调用 2.2 万次 ⇒ 长局严重退化。缓存后调用方**只读**，不得原地修改。
    """
    T = _table()
    out: List[Dict[str, Any]] = []
    for circuit, info in _geo().items():
        meta = {m[0]: (m[1], m[2], m[3]) for m in (info.get("members") or [])}
        for row in (T.PREFECTURE_SEATS.get(circuit) or []):
            seat = row.get("name")
            lvl, lon, lat = meta.get(seat, (None, None, None))
            blocked = bool(row.get("blocked"))
            if not include_merged and not blocked:
                continue
            if blocked:
                basis = row.get("basis") or BASIS_AREA_ONLY
                demog = {k: v for k, v in row.items()
                         if k not in ("name", "blocked", "note", "basis")}
            else:
                basis, demog = BASIS_MERGED, None
            out.append({"seat_id": seat_id_of(circuit, seat), "seat": seat,
                        "circuit": circuit, "level": lvl,
                        "lon": lon, "lat": lat, "blocked": blocked,
                        "basis": basis, "demog": demog})
    return tuple(out)


def all_seats(include_merged: bool = True) -> List[Dict[str, Any]]:
    """全部治所实体（默认含省级归入席）。**返回只读缓存列表的浅拷贝**。

    返回 `[{seat, circuit, level, lon, lat, blocked, basis, demog}]`：
    - `level/lon/lat` 取自 `CIRCUIT_INFO.members`（**实测地图点**）；
    - `demog`：有块者给出人口/户/田/粮/税/产出；归入席为 `None`（**缺失≠0**）；
    - `basis`：见模块头精度声明。
    """
    return list(_all_seats_cached(include_merged))


@_lru_cache(maxsize=64)
def _seats_of_cached(circuit: str, include_merged: bool = True) -> tuple:
    return tuple(s for s in _all_seats_cached(include_merged)
                 if s["circuit"] == circuit)


def seats_of(circuit: str, include_merged: bool = True) -> List[Dict[str, Any]]:
    """某路下辖治所实体；未知路返回 `[]`（**不抛**，便于 UI 容错）。"""
    return list(_seats_of_cached(circuit, include_merged))


def circuit_of(seat_id: str) -> Optional[str]:
    """治所主键（`路|治所`）→ 所隶路；未知返回 `None`（缺失≠空串）。

    ⚠️ 传入**显示名**（不含 `|`）时，因显示名可能跨路重名（如 `颍昌府`），
    本函数**返回 `None` 而不猜**——请改用 `seat_id_of(路, 治所)` 构造主键。
    """
    c, s = split_seat_id(seat_id)
    if c is None:
        return None
    for x in all_seats():
        if x["seat_id"] == seat_id:
            return x["circuit"]
    return None


def seat_entity(seat_id: str) -> Optional[Dict[str, Any]]:
    """单个治所实体（**传主键 `路|治所`**；传显示名返回 `None`，不猜）。"""
    for s in all_seats():
        if s["seat_id"] == seat_id:
            return s
    return None


def prefecture_demog(seat_id: str) -> Optional[Dict[str, Any]]:
    """州府级人口经济（**传主键 `路|治所`**）；归入席与未知键一律 `None`（缺失≠0）。

    调用方须把 `None` 显示为"未分配/未定义"，**不得回落 0**。
    """
    ent = seat_entity(seat_id)
    return ent["demog"] if ent else None


def circuit_aggregate(circuit: str, dim: str = "population") -> Optional[int]:
    """路级聚合读数 = `Σ(有块州府) + residual`，并与 `PREFECTURE_INFO` **断言一致**。

    这是"路级不得成为第二份真账"的执行点：一旦不一致即 `ValueError`（不静默）。
    """
    T = _table()
    from content.data import PREFECTURE_INFO
    base = PREFECTURE_INFO.get(circuit)
    if base is None:
        return None
    rows = T.PREFECTURE_SEATS.get(circuit) or []
    if not rows:
        return None
    got = sum(int(r.get(dim, 0) or 0) for r in rows if r.get("blocked"))
    res = int((T.PREFECTURE_RESIDUAL.get(circuit) or {}).get(dim, 0) or 0)
    total = got + res
    parent = base.get(dim)
    if parent is None:
        return total
    if abs(total - int(parent)) > 1:
        raise ValueError(
            f"{circuit}/{dim} 聚合不一致：Σ子+residual={total} vs 路级={parent}"
            f"（路级不得成为与州府并行的第二份真账）")
    return total


def coverage_report() -> Dict[str, Any]:
    """覆盖率与**精度构成**（给 UI/审计用；不臆断，如实报数）。"""
    seats = all_seats()
    by_basis: Dict[str, int] = {}
    for s in seats:
        by_basis[s["basis"]] = by_basis.get(s["basis"], 0) + 1
    anchored = [s["seat_id"] for s in seats if s["basis"] == BASIS_AREA_ANCHOR]
    blocked = sum(1 for s in seats if s["blocked"])
    hist = by_basis.get(BASIS_HISTORICAL, 0)
    return {
        "total_seats": len(seats),
        "unique_seat_ids": len({s["seat_id"] for s in seats}),
        "unique_display_names": len({s["seat"] for s in seats}),
        "duplicate_display_names": duplicate_display_names(),
        "blocked": blocked,
        "merged": sum(1 for s in seats if not s["blocked"]),
        "by_basis": by_basis,
        "anchor_seats": sorted(anchored),
        # 史料覆盖率（分子/分母如实；分母＝有块席，归入席本就无数值）
        "historical_seats": hist,
        "historical_coverage": (round(hist / blocked, 4) if blocked else None),
        # ⚠️ 如实声明精度：未录史料的席位是**面积估计**
        "precision_note": (
            f"史料口径 {hist}/{blocked} 席（覆盖 {round(100.0 * hist / blocked, 1) if blocked else 0}%）；"
            f"其余 {blocked - hist} 席无史料，其人口经济为**面积估计**"
            "（设计文档 §4.2 禁止'按面积随意拆分'）——"
            "下游不得把面积估计当史料级州府数据呈现。"
            "补录方式：向 `content/data_households_hist.py` 增录《宋史·地理志》崇宁户并重跑生成器。"),
    }
