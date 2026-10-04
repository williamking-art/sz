# -*- coding: utf-8 -*-
"""🔴 **州府级 POP 基座 + 读写桥**（2026-10-04 用户裁定 **方案乙**：POP 实体下沉州府级）。

## 裁定与约束

- **真账**：`prefectures[路]["seats"][治所]["pops"][类]` —— 每治所一个独立 POP；
- **路级 `pops`** 降为**只读派生聚合**（Σ 治所），写入必须落州府，
  否则构成 AGENTS §3-1 禁止的「与 POP 平行的账本」；
- 本模块已改写 `AGENTS.md` §3-1（前置条件，2026-10-04）。

## 拆分依据

宋有州府级户籍与仓储，故按**治所人口比例**拆分：`demog.population`（如京畿路开封府 510 万）。
🔴 **尾差归权重最大者**，保证 `Σ治所 == 路级原值` **逐字段精确相等**（不丢一钱一人）。

## 迁移状态

`pops` 直访仍有 **39 文件 / 197 处**。本模块**不改任何调用点**，
过渡期桥接是唯一允许的写入口；直访清零后路级 `pops` 才可退役。
"""
from typing import Dict, List, Optional

#: POP 6 类（AGENTS §3-1 挂载律：人只落这 6 类的 size）
POP_CLASSES = ("农", "士绅", "商人", "官僚", "兵", "工匠")

#: 拆分时需**逐字段守恒**的数值字段（尾差归权重最大者）
SPLIT_FIELDS = ("size", "kou", "ding", "wealth", "literacy", "hidden",
                 "欠税", "自耕农", "佃农", "富农", "贫农")


def seat_pop_weights(circuit: str) -> List[tuple]:
    """该路各治所的人口权重 [(seat_id, pop), ...]（`demog.population`）。

    无治所或人口全缺 ⇒ 返回 []，调用方据此**不做拆分**（不臆造归属）。
    """
    try:
        from core.prefecture_entity import seats_of
        seats = seats_of(circuit, include_merged=False)
    except Exception:
        return []
    out = []
    for s in seats:
        sid = str(s.get("seat_id") or "")
        if not sid:
            continue
        demog = s.get("demog") or {}
        v = demog.get("population")
        if not isinstance(v, (int, float)) or v <= 0:
            continue
        out.append((sid, float(v)))
    return out


def _split_int(total: int, weights: List[tuple]) -> Dict[str, int]:
    """按权重拆整数，**尾差归权重最大者**，Σ 精确等于 `total`。"""
    if total == 0 or not weights:
        return {sid: 0 for sid, _w in weights}
    tw = sum(w for _s, w in weights)
    if tw <= 0:
        return {sid: 0 for sid, _w in weights}
    anchor = max(weights, key=lambda kv: kv[1])[0]
    parts = {sid: int(round(total * w / tw)) for sid, w in weights}
    parts[anchor] += total - sum(parts.values())
    return parts


def split_pops_to_seats(pdata: dict, circuit: str) -> int:
    """把路级 POP 聚合**就地拆入** `pdata["seats"][治所]["pops"]`。返回拆出的治所数。

    幂等：已有 `seats` 且非空则**直接返回**（不重复拆，避免二次拆分导致 double）。
    """
    if not isinstance(pdata, dict):
        return 0
    if pdata.get("seats"):
        return len(pdata["seats"])
    pops = pdata.get("pops") or {}
    if not isinstance(pops, dict) or not pops:
        return 0
    w = seat_pop_weights(circuit)
    if not w:
        return 0
    seats = {}
    for sid, _pop in w:
        seat_pops = {}
        for cls in POP_CLASSES:
            src = pops.get(cls)
            if not isinstance(src, dict):
                continue
            row = dict(src)
            for f in SPLIT_FIELDS:
                v = src.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    row[f] = _split_int(int(v), w).get(sid, 0)
            gd = src.get("goods")
            if isinstance(gd, dict):
                row["goods"] = {k: _split_int(int(v), w).get(sid, 0)
                                for k, v in gd.items()
                                if isinstance(v, (int, float)) and not isinstance(v, bool)}
            seat_pops[cls] = row
        seats[sid] = {"pops": seat_pops}
    pdata["seats"] = seats
    return len(seats)


def aggregate_seat_pops(pdata: dict, cls: str) -> Optional[dict]:
    """**派生聚合**：Σ 各治所该类 POP ⇒ 路级视图。`seats` 不存在 ⇒ 返回 None。

    缺失 ≠ 0：无 `seats` 时返回 None（表示「未下沉」），不回落成空账。
    """
    if not isinstance(pdata, dict):
        return None
    seats = pdata.get("seats") or {}
    if not seats:
        return None
    rows = [(s.get("pops") or {}).get(cls) for s in seats.values()]
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        return None
    out = dict(rows[0])
    for f in SPLIT_FIELDS:
        if any(isinstance(r.get(f), (int, float)) for r in rows):
            out[f] = sum(int(r.get(f, 0) or 0) for r in rows)
    goods = {}
    for r in rows:
        for k, v in (r.get("goods") or {}).items():
            goods[k] = goods.get(k, 0) + int(v or 0)
    out["goods"] = goods
    return out


def survey_pops(state) -> Dict[str, object]:
    """**迁移对账**：逐路比对路级 POP 与 Σ治所 POP 是否**逐字段相等**。"""
    prefs = getattr(state, "prefectures", {}) or {}
    out = {"路由数": len(prefs), "已下沉路由": 0, "字段失配": []}
    for route, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        seats = pdata.get("seats") or {}
        if seats:
            out["已下沉路由"] += 1
        pops = pdata.get("pops") or {}
        for cls in POP_CLASSES:
            src = pops.get(cls)
            agg = aggregate_seat_pops(pdata, cls)
            if not isinstance(src, dict) or not isinstance(agg, dict):
                continue
            for f in SPLIT_FIELDS:
                a1 = src.get(f)
                a2 = agg.get(f)
                if isinstance(a1, (int, float)) and isinstance(a2, (int, float)) \
                        and int(a1) != int(a2):
                    out["字段失配"].append("%s/%s/%s: %s != %s" % (route, cls, f, a1, a2))
    return out


__all__ = ["POP_CLASSES", "SPLIT_FIELDS", "seat_pop_weights",
           "split_pops_to_seats", "aggregate_seat_pops", "survey_pops"]
