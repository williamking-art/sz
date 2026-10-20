# -*- coding: utf-8 -*-
"""`state.resources[dim]["stock"]` 的**单一写口**（商品/物料存量州府化·**先桥**步） —— M64a。

裁定（🔴 裁定档：`decisions/M64-resource-stock-bridge-scope.json`）
------------------------------------------------------------------
Jev **甲 0.817**：**保持全国池不下沉**，只给"**有路的**"写点加**可选路参数**的桥：
给了 `route` 且该路**已下沉** ⇒ 写治所真账并刷镜像；**否则回到全国池＝现状**。
理由（实测）：`state.resources` 是**全国池、没有路维度**——11 处写点里只有一部分**天然有路**
（生产链/和买/作坊投料/作坊产出…），另一些（官仓售料/领料/基座写/熔铜溢出）是**全国口径操作、
根本没有路**；若强改逐路池，就得为它们**新造归属规则**＝按人口比例伪造地点（M37/M47 明令禁止）。

本模块的口径
------------
* **唯一行为契约**：调用方**先问桥**；桥返回 `None` ⇒ **调用方保留原写法**（⇒ 今日**零行为变化**，
  因为还没有任何路被下沉）；桥返回数值 ⇒ 桥已经写完（调用方不要再写）。
* **治所真账**：`seats[治所]["resources"] = {dim: stock}`；**路级/全国镜像**：`Σ已下沉路的治所`。
* **cap 归全国**：`cap` 是**全国制度上限**，不进治所；本模块不碰 `cap`。
* **缺失 ≠ 0**：读不到 ⇒ `None`；**未下沉/无路/参数非法 ⇒ `None`**（不臆造、不回落 0）。
* **首府承载**：缺省治所取既有单点 `building_bridge.capital_seat_id`，取不到退人口权重最大者，
  再无 ⇒ `None`（**不臆造地点**）。
* **夹紧留痕**：扣减夹到 0 记一次（不静默）。
* `sink_route_resource_stock` / `sink_resource_stock_to_seats` **已实现、本批不调用**
  （将来若改逐路池才接线；按本裁定**暂不启用**）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

from core.foundation.ledger.seat_locator import seats_map as _seats_map

#: 治所真账里承载资源存量的键名（与 `"pops"` 平级）
SEAT_KEY = "resources"

#: 夹紧（扣到 0）事件：模块级，**不静默**
_CLAMP_EVENTS: List[Dict[str, Any]] = []

__all__ = [
    "SEAT_KEY", "is_sunk", "seat_stock", "route_stock_total", "stock_get",
    "stock_add", "stock_set", "stock_take", "sink_route_resource_stock",
    "sink_resource_stock_to_seats", "survey_resource_stock", "clamp_events",
]


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _int_or_none(v) -> Optional[int]:
    n = _num(v)
    return None if n is None else int(n)


def _prefs(state) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None)
    return prefs if isinstance(prefs, dict) else None


def _routed(state, route) -> Optional[dict]:
    prefs = _prefs(state)
    if prefs is None or not route:
        return None
    pdata = prefs.get(route)
    return pdata if isinstance(pdata, dict) else None


def _seat_res(pdata, seat_id) -> Optional[dict]:
    seat = _seats_map(pdata).get(str(seat_id))
    if not isinstance(seat, dict):
        return None
    res = seat.get(SEAT_KEY)
    if not isinstance(res, dict):
        res = {}
        seat[SEAT_KEY] = res
    return res


def is_sunk(pdata) -> bool:
    """该路是否已下沉：**至少一个治所有 `resources` 桶**（未登记治所缺席＝正确语义）。"""
    for s in _seats_map(pdata).values():
        if isinstance(s, dict) and isinstance(s.get(SEAT_KEY), dict):
            return True
    return False


def seat_stock(pdata, seat_id, dim: str) -> Optional[int]:
    """某治所某维存量；治所/桶/该维不可读 ⇒ `None`（缺失≠0）。"""
    seat = _seats_map(pdata).get(str(seat_id))
    res = seat.get(SEAT_KEY) if isinstance(seat, dict) else None
    if not isinstance(res, dict):
        return None
    return _int_or_none(res.get(dim))


def route_stock_total(pdata, dim: str) -> Optional[int]:
    """Σ治所（只统计**有数值**的治所）；一个都没有 ⇒ `None`（不回落 0）。"""
    tot, seen = 0, False
    for sid in _seats_map(pdata):
        v = seat_stock(pdata, sid, dim)
        if v is not None:
            tot += v
            seen = True
    return tot if seen else None


def _sum_known_stock(state, dim: str) -> Optional[int]:
    """Σ（**已下沉路**的治所 + **未下沉路**的路级 `resources[dim].stock`）。

    这是"翻开关后的全国池口径"：已下沉的路从治所真账算，尚未下沉的路仍从其既有载体算
    —— **不给未桥接部分造数**（未下沉且无路级值 ⇒ 不计入，`seen` 保持 False）。
    """
    prefs = _prefs(state)
    if prefs is None:
        return None
    tot, seen = 0, False
    for pdata in prefs.values():
        if not isinstance(pdata, dict):
            continue
        v = None
        if is_sunk(pdata):
            v = route_stock_total(pdata, dim)
        else:
            cell = (pdata.get("resources") or {}).get(dim)
            v = _int_or_none(cell.get("stock")) if isinstance(cell, dict) else None
        if v is not None:
            tot += v
            seen = True
    return tot if seen else None


def _refresh_national(state, dim: str) -> Optional[int]:
    """把**全国池**（`state.resources[dim]["stock"]`）刷成 `_sum_known_stock`；`cap` 不动。

    仅在桥接管（即该路已下沉）的写入后调用；今日无任何路下沉 ⇒ **从不被调用** ⇒ 零行为变化。
    """
    total = _sum_known_stock(state, dim)
    if total is None:
        return None
    res = getattr(state, "resources", None)
    if not isinstance(res, dict):
        return None
    slot = res.get(dim)
    if not isinstance(slot, dict):
        slot = {"stock": 0, "cap": 0}
        res[dim] = slot
    slot["stock"] = int(total)
    return int(total)


def _clamp_note(route, dim: str, want: int, got: int) -> None:
    if len(_CLAMP_EVENTS) < 200:
        _CLAMP_EVENTS.append({"route": route, "dim": dim, "want": want, "got": got})
    log.warning("[资源桥] 扣减夹紧 route=%s dim=%s want=%s got=%s", route, dim, want, got)


def clamp_events() -> List[Dict[str, Any]]:
    """夹紧事件（读数/回归用）。"""
    return list(_CLAMP_EVENTS)


def _default_seat(pdata, route) -> Optional[str]:
    """缺省承载治所：**首府**（既有单点）→ 人口权重最大 → 任一治所；都没有 ⇒ `None`。"""
    try:
        from core.foundation.ledger.building_bridge import capital_seat_id
        sid = capital_seat_id(pdata, route)
        if sid:
            return str(sid)
    except Exception:                                       # noqa: BLE001
        log.warning("resource_stock_bridge: 首府判定不可用 route=%s", route, exc_info=True)
    try:
        from core.foundation.ledger.pop_bridge import seat_pop_weights
        w = seat_pop_weights(route) or []
        if w:
            return str(max(w, key=lambda kv: kv[1])[0])
    except Exception:                                       # noqa: BLE001
        log.warning("resource_stock_bridge: 人口权重不可用 route=%s", route, exc_info=True)
    seats = _seats_map(pdata)
    return str(next(iter(seats))) if seats else None


def stock_get(state, dim: str, route=None) -> Optional[int]:
    """读存量：给了 `route` 且该路已下沉 ⇒ Σ治所；否则 ⇒ `None`（调用方按原口径读）。"""
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    return route_stock_total(pdata, dim)


def stock_add(state, dim: str, delta, route=None, seat_id=None) -> Optional[int]:
    """**增量写**（桥接管时返回**写后全国池**值；未接管 ⇒ `None`）。

    接管条件：`route` 给定 **且** 该路已下沉 **且** `delta` 可解析。否则返回 `None`
    ⇒ 调用方**保留原写法**（今日零行为变化）。
    """
    d = _int_or_none(delta)
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata) or d is None:
        return None
    sid = seat_id or _default_seat(pdata, route)
    if sid is None:
        return None
    res = _seat_res(pdata, sid)
    if res is None:
        return None
    cur = _int_or_none(res.get(dim)) or 0
    nv = cur + d
    if nv < 0:
        _clamp_note(route, dim, nv, 0)
        nv = 0
    res[dim] = int(nv)
    return _refresh_national(state, dim)


def stock_set(state, dim: str, value, route=None, seat_id=None) -> Optional[int]:
    """**设值**（接管条件同 `stock_add`）；未接管 ⇒ `None`。"""
    v = _int_or_none(value)
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata) or v is None:
        return None
    sid = seat_id or _default_seat(pdata, route)
    if sid is None:
        return None
    res = _seat_res(pdata, sid)
    if res is None:
        return None
    res[dim] = max(0, int(v))
    return _refresh_national(state, dim)


def stock_take(state, dim: str, want, route=None) -> Optional[int]:
    """**取货**：接管时从**治所真账**按各治所持仓占比取（逐个夹紧 ≥0），返回实际取出量；
    未接管 ⇒ `None`（调用方保留原写法）。"""
    w = _int_or_none(want)
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata) or w is None or w <= 0:
        return None
    rows = []
    for sid in _seats_map(pdata):
        v = seat_stock(pdata, sid, dim)
        if v and v > 0:
            rows.append([str(sid), float(v)])
    if not rows:
        _clamp_note(route, dim, w, 0)
        return 0
    total = sum(r[1] for r in rows)
    taken = 0
    for i, (sid, v) in enumerate(rows):
        take = w - taken if i == len(rows) - 1 else int(w * v / total)
        take = max(0, min(int(v), take, w - taken))
        if take:
            res = _seat_res(pdata, sid)
            res[dim] = int(v) - take
            taken += take
    if taken < w:
        _clamp_note(route, dim, w, taken)
    _refresh_national(state, dim)
    return taken


def sink_route_resource_stock(pdata, route, dim: str, value=None) -> bool:
    """把该路某维存量**全部落到首府治所**并刷镜像。已下沉 ⇒ `False`（不覆盖）。

    ⚠️ **本批不调用**（裁定：**保持全国池不下沉**）；实现 + 单测就位，便于将来若要改逐路池时接线。
    """
    if not isinstance(pdata, dict) or is_sunk(pdata):
        return False
    v = value
    if v is None:
        slot = (pdata.get("resources") or {}).get(dim)
        v = _int_or_none(slot.get("stock")) if isinstance(slot, dict) else None
    v = _int_or_none(v)
    if v is None:
        return False
    sid = _default_seat(pdata, route)
    if sid is None:
        return False
    res = _seat_res(pdata, sid)
    if res is None:
        return False
    res[dim] = max(0, int(v))
    return True


def sink_resource_stock_to_seats(state, dims=None, routes=None) -> int:
    """**无条件幂等入口**（同 `sink_pops_to_seats` 同型）。⚠️ **本批不调用**（见裁定）。"""
    prefs = _prefs(state)
    if prefs is None:
        return 0
    res = getattr(state, "resources", None)
    dim_list = list(dims) if dims else (list(res) if isinstance(res, dict) else [])
    n = 0
    for route in (routes if routes else list(prefs)):
        pdata = prefs.get(route)
        if not isinstance(pdata, dict):
            continue
        for dim in dim_list:
            if sink_route_resource_stock(pdata, route, dim):
                n += 1
    return n


def survey_resource_stock(state) -> Dict[str, Any]:
    """只读对账：**全国池** vs `Σ（已下沉路治所 + 未下沉路路级）`；并报已下沉/未下沉路数与夹紧次数。"""
    prefs = _prefs(state)
    rows, sunk, unsunk = [], 0, 0
    for route, pdata in (prefs or {}).items():
        if not isinstance(pdata, dict):
            continue
        if is_sunk(pdata):
            sunk += 1
        else:
            unsunk += 1
    dims = set(getattr(state, "resources", None) or {})
    for route, pdata in (prefs or {}).items():
        if isinstance(pdata, dict):
            dims |= set(pdata.get("resources") or {})
    for dim in sorted(dims):
        known = _sum_known_stock(state, dim)
        cell = (getattr(state, "resources", None) or {}).get(dim)
        national = _int_or_none(cell.get("stock")) if isinstance(cell, dict) else None
        if known is None and national is None:
            continue
        if known != national:
            rows.append({"dim": dim, "sum_known": known, "national": national})
    return {"sunk_routes": sunk, "unsunk_routes": unsunk, "mismatch_count": len(rows),
            "mismatches": rows[:50], "clamp_count": len(_CLAMP_EVENTS)}
