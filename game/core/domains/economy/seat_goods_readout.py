# -*- coding: utf-8 -*-
"""州府级商品**只读**读数（统一民间市场「真实交易与州府价格」的第一块） —— M46。

为什么先做读数
--------------
M42g/i 之后商品**真的落在治所真账**（`seats[治所]["pops"][类]["goods"]`），
但全库几乎没有"按州府看商品"的读口：现有读取都是**路级镜像**。做价格/成交的州府化之前，
先要有可信的州府级读数与**真账↔镜像一致性**自检——否则后面所有州府化都会建在看不见的漂移上。

口径
----
* **只读**：不写任何 state（`survey` 前后深比较一致）。
* **真账优先**：`seat_goods` 读治所真账；**未下沉（无 `seats`）⇒ `None`**（缺失≠0，不回落路级）。
* **阶层维度保留**：返回 `{路: {治所: {类: {dim: qty}}}}`——商品在哪个阶层手里是**业务事实**，
  不做"总持有"合并（合并会把"工匠待售"与"士绅囤积"混为一谈）。
* **一致性自检**：`seat_consistency` 逐 `(路, 类, dim)` 比对 `Σ治所` 与**路级镜像**
  （经 `material_holding.goods_amount` 单点读口，含州府桶），差异如实列出——
  M42g/i 修掉的正是"直写镜像"一类缺陷，本读数用于**持续看得见**它是否复发。
* **作坊归属覆盖率**（为下一批"产出地点并轨"取证）：`state.workshops` 键形如 `麻坊_京畿路_2`
  ⇒ 按**已知路名**判定可归属比例；归不到的一律如实计数（不臆造）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

__all__ = [
    "SCHEMA_VERSION", "POP_GOODS_CLASSES", "seat_goods", "route_seat_totals",
    "seat_consistency", "workshop_attribution", "survey_seat_goods",
]

SCHEMA_VERSION = 1

#: 关心商品的阶层（与既有 POP 分类一致；顺序即报表顺序）
POP_GOODS_CLASSES = ("士绅", "官僚", "商人", "工匠", "农", "兵")


def _prefs(state) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None)
    return prefs if isinstance(prefs, dict) else None


def _flat_goods(goods: Any) -> Dict[str, int]:
    """把某阶层 `goods` 摊平为 `{dim: qty}`（兼容 `{治所:{dim:n}}` 桶形态）。"""
    out: Dict[str, int] = {}
    if not isinstance(goods, dict):
        return out
    for k, v in goods.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[str(k)] = out.get(str(k), 0) + int(v)
        elif isinstance(v, dict):
            for d, q in v.items():
                if isinstance(q, (int, float)) and not isinstance(q, bool):
                    out[str(d)] = out.get(str(d), 0) + int(q)
    return out


def seat_goods(state, route: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """治所真账商品 `{路: {治所: {类: {dim: qty}}}}`。

    `route` 给定 ⇒ 只返回该路（路不存在 / 无 `seats` ⇒ `None`）。
    **未下沉（整局无 `seats`）⇒ `None`**（不回落路级镜像，避免把镜像当本地事实）。
    """
    prefs = _prefs(state)
    if prefs is None:
        return None
    routes = [route] if route is not None else list(prefs)
    out: Dict[str, Any] = {}
    for r in routes:
        pdata = prefs.get(r)
        if not isinstance(pdata, dict):
            if route is not None:
                return None
            continue
        seats = pdata.get("seats")
        if not isinstance(seats, dict) or not seats:
            if route is not None:
                return None
            # 🔴 **该路未下沉 ⇒ 显式 `None`**（不静默省略：省略会让调用方分不清
            #    "没有 seats" 与"有 seats 但没货" —— 缺失≠0）
            out[str(r)] = None
            continue
        per_seat: Dict[str, Any] = {}
        for sid, srow in seats.items():
            pops = (srow or {}).get("pops") if isinstance(srow, dict) else None
            if not isinstance(pops, dict):
                continue
            classes: Dict[str, Any] = {}
            for cls in POP_GOODS_CLASSES:
                row = pops.get(cls)
                if not isinstance(row, dict):
                    continue
                g = _flat_goods(row.get("goods"))
                if g:
                    classes[cls] = g
            if classes:
                per_seat[str(sid)] = classes
        out[str(r)] = per_seat
    if route is not None:
        return out.get(route)
    return out


def route_seat_totals(state, route: str) -> Optional[Dict[str, Dict[str, int]]]:
    """该路逐治所**商品合计**（跨阶层相加，仅用于总量读数；阶层明细见 `seat_goods`）。"""
    per_seat = seat_goods(state, route)
    if per_seat is None:
        return None
    out: Dict[str, Dict[str, int]] = {}
    for sid, classes in per_seat.items():
        tot: Dict[str, int] = {}
        for g in classes.values():
            for d, q in g.items():
                tot[d] = tot.get(d, 0) + int(q)
        out[str(sid)] = tot
    return out


def seat_consistency(state) -> Dict[str, Any]:
    """**真账 ↔ 路级镜像一致性**（只读自检）：逐 `(路, 类, dim)` 比对 `Σ治所` 与镜像。

    镜像读取走 `material_holding.goods_amount`（单点读口，含州府桶）。
    返回 `{checked, mismatches:[{route, cls, dim, seat_sum, mirror, diff}], ok, reason?}`。
    未下沉 / 无 `prefectures` ⇒ `ok=None` ＋ `reason`（**不假装通过**）。
    """
    prefs = _prefs(state)
    if prefs is None:
        return {"ok": None, "reason": "无 prefectures", "checked": 0, "mismatches": []}
    try:
        from core.foundation.ledger.material_holding import goods_amount
    except Exception:                                       # noqa: BLE001
        return {"ok": None, "reason": "goods_amount 不可用", "checked": 0, "mismatches": []}
    checked = 0
    mismatches: List[Dict[str, Any]] = []
    any_sunk = False
    for r, pdata in prefs.items():
        seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
        if not isinstance(seats, dict) or not seats:
            continue
        any_sunk = True
        pops = (pdata or {}).get("pops") or {}
        for cls in POP_GOODS_CLASSES:
            # Σ治所
            seat_sum: Dict[str, int] = {}
            for srow in seats.values():
                row = ((srow or {}).get("pops") or {}).get(cls) if isinstance(srow, dict) else None
                for d, q in _flat_goods(row.get("goods") if isinstance(row, dict) else None).items():
                    seat_sum[d] = seat_sum.get(d, 0) + int(q)
            mirror_goods = (pops.get(cls) or {}).get("goods") if isinstance(pops.get(cls), dict) else None
            dims = set(seat_sum) | set(_flat_goods(mirror_goods))
            for d in sorted(dims):
                checked += 1
                m = goods_amount(mirror_goods, d)
                m = None if m is None else int(m)
                s = int(seat_sum.get(d, 0))
                if m != s:
                    mismatches.append({"route": r, "cls": cls, "dim": d,
                                       "seat_sum": s, "mirror": m,
                                       "diff": None if m is None else m - s})
    if not any_sunk:
        return {"ok": None, "reason": "全库未下沉（无 seats）", "checked": 0, "mismatches": []}
    return {"ok": not mismatches, "reason": None, "checked": checked,
            "mismatches": mismatches[:50], "mismatch_count": len(mismatches)}


def workshop_attribution(state) -> Dict[str, Any]:
    """作坊**可按路归属**的覆盖率（为下一批"产出地点并轨"取证）。

    判据：`state.workshops` 的键形如 `麻坊_京畿路_2`；能匹配到已知路名 ⇒ 可归属。
    匹配不到的如实计数（**不臆造地点**）。返回 `{total, attributable, ratio, unattributed:[keys]}`。
    """
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"total": 0, "attributable": 0, "ratio": None, "unattributed": [],
                "reason": "state.workshops 缺失"}
    routes = list(_prefs(state) or {})
    total = attributable = 0
    bad: List[str] = []
    for key in ws:
        if not isinstance(key, str):
            continue
        total += 1
        if any(r and r in key for r in routes):
            attributable += 1
        else:
            bad.append(key)
    return {"total": total, "attributable": attributable,
            "ratio": (attributable / total) if total else None,
            "unattributed": bad[:20]}


def survey_seat_goods(state) -> Dict[str, Any]:
    """州府级商品总读数：路/治所/维规模 ＋ 一致性 ＋ 作坊可归属率。"""
    sg = seat_goods(state)
    cons = seat_consistency(state)
    wa = workshop_attribution(state)
    if sg is None:
        return {"schema_version": SCHEMA_VERSION, "sunk": False, "routes": 0, "seats": 0,
                "dims": [], "consistency": cons, "workshops": wa,
                "reason": "未下沉或无 prefectures（缺失≠0）"}
    seats = sum(len(v) for v in sg.values() if isinstance(v, dict))
    dims = sorted({d for v in sg.values() if isinstance(v, dict)
                   for cl in v.values() for g in cl.values() for d in g})
    routes = sum(1 for v in sg.values() if isinstance(v, dict))
    return {"schema_version": SCHEMA_VERSION, "sunk": True, "routes": routes, "seats": seats,
            "dims": dims, "consistency": cons, "workshops": wa,
            "unsunk_routes": sorted(r for r, v in sg.items() if v is None)}
