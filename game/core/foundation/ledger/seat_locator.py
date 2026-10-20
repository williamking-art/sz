# -*- coding: utf-8 -*-
"""**治所定位基座**（共享内核，唯一实现）。

2026-10-20 复用批 P1：`_seats_map / _locate / _routed / _seat_of` 曾在 5 个 bridge 里
逐字节复制（`test_duplicate_impl_guard.py` 冻结组）。定位是**机制无关**的能力，
按「复用向下不横向」原则下沉到 `foundation/ledger`，各 bridge 只做别名导入，
调用点不改。

纪律：
- 非 dict / 无 `seats` ⇒ 空映射（**缺失≠0**：这里只回答"有没有"，不造数）；
- `route` 不存在/非 dict ⇒ `None`（不臆造路）；
- 不改任何 state（纯读）。
"""
from __future__ import annotations

from typing import Dict, Optional


def seats_map(pdata) -> Dict[str, dict]:
    """路级 `seats` 映射（非 dict 一律当空）。"""
    if not isinstance(pdata, dict):
        return {}
    seats = pdata.get("seats")
    return seats if isinstance(seats, dict) else {}


def locate_route(state, route: str) -> Optional[dict]:
    """`state.prefectures[route]`，不存在/非 dict ⇒ `None`（缺失不回落空 dict）。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    pdata = prefs.get(route)
    return pdata if isinstance(pdata, dict) else None


def seat_of(pdata, seat_id: str) -> Optional[dict]:
    """取某治所 dict；不存在 ⇒ `None`。"""
    seat = seats_map(pdata).get(str(seat_id))
    return seat if isinstance(seat, dict) else None
