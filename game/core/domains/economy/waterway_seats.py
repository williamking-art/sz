# -*- coding: utf-8 -*-
"""航道（`canal`/水运可航档）**治所级**表 —— 交通下沉州府级 M39a。

口径（Jev 裁定 2026-10-13 choose A **0.690**）
---------------------------------------------
用户裁定「**交通是州府级**」（`specs/transport/交通下沉州府级.md`）。本模块承载其**静态史料部分**：

* **治所级真账**：`SEAT_WATERWAY`＝`{治所 id: 档位}`，由既有路级史料表 `ROUTE_WATERWAY`
  （`trade_shadow.py`，21 路分 强/有/弱，依据 `specs/ROUTE_WATERWAY逐路可航性.md`）
  经 **首府（路治）承载** 生成；
* **路级为派生聚合**：`waterway_tier_route(route)` = 该路**已登记治所中的最高档**
  （档序 强 ＞ 有 ＞ 弱）；迁移后与原表**逐路相等**（只有首府登记 ⇒ 聚合即首府值）；
* **缺失 ≠ 0**：未登记治所 ⇒ `None`（⇒ 不可水运），**不回落"有"或"弱"**；
* **不编造**：每治所档位**无史料来源**（规格 ②：逐治所初始值需地理事实，Natural Earth 已证不可用）
  ⇒ 只做**首府承载的结构性下沉**，其余治所**留空**（将来有依据再逐治所登记）。

**为什么放模块常量而不是 state**（Jev 同问裁定 A）：它是**静态史料表**，不入档、无需迁移；
写入 `seats[治所]["waterway"]`（B 方案）会带来存档体积与旧档迁移成本，收益仅"形式更彻底"（B 得 0.290）。

⚠️ 本模块**不改变任何行为**：路级值与原表逐路相等（由用例与 A/B 对照锁定）。
`trade_shadow` 是**影子模块**（不接入正式结算）⇒ 本批是**结构性预备**，
真正牵动数值的是 M39c（`canal_block` 逐治所 + 粮价改逐路读）。
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

log = logging.getLogger(__name__)

#: 档序（**从优到劣**）：聚合时取"最优"档
TIER_ORDER: Tuple[str, ...] = ("强", "有", "弱")

__all__ = [
    "TIER_ORDER", "SEAT_WATERWAY", "capital_seat_id", "waterway_tier_seat",
    "waterway_tier_route", "survey_waterway", "rebuild_seat_table",
]


def _route_table() -> Dict[str, Tuple[str, ...]]:
    """路级史料源表（`trade_shadow.ROUTE_WATERWAY`）。取模块属性便于测试打桩。"""
    from core.domains.economy import trade_shadow
    return dict(getattr(trade_shadow, "ROUTE_WATERWAY", {}) or {})


def capital_seat_id(route: str) -> Optional[str]:
    """该路首府（路治）治所 id：`SEAT_LEVELS` 序最优，同级取人口（`demog.population`）多者。

    **不需要 state**——只读 `prefecture_entity` 的静态治所实体表。
    判不出（无治所实体）⇒ `None`（该路不登记，**不臆造地点**）。
    """
    try:
        from core.foundation.ledger.prefecture_entity import SEAT_LEVELS, seats_of
    except Exception:                                   # noqa: BLE001
        log.warning("waterway_seats: 取治所实体模块失败 route=%s", route, exc_info=True)
        return None
    best, best_key = None, None
    for ent in (seats_of(route, include_merged=False) or []):
        sid = str(ent.get("seat_id") or "")
        if not sid:
            continue
        lvl = str(ent.get("level") or "")
        rank = SEAT_LEVELS.index(lvl) if lvl in SEAT_LEVELS else len(SEAT_LEVELS)
        pop = float((ent.get("demog") or {}).get("population") or 0)
        key = (rank, -pop, sid)
        if best_key is None or key < best_key:
            best, best_key = sid, key
    return best


def rebuild_seat_table() -> Dict[str, str]:
    """按路级史料表重建治所级表（**首府承载**）。无治所实体的路**跳过**（不臆造）。"""
    out: Dict[str, str] = {}
    for tier, routes in _route_table().items():
        for route in routes:
            sid = capital_seat_id(route)
            if sid:
                out[sid] = tier
    return out


#: 治所级真账：`{治所 id: 档位}`（模块加载时由路级史料表首府承载生成）
SEAT_WATERWAY: Dict[str, str] = rebuild_seat_table()


def waterway_tier_seat(seat_id: str) -> Optional[str]:
    """某治所的可航档；**未登记 ⇒ `None`**（缺失≠0 ⇒ 不可水运）。"""
    return SEAT_WATERWAY.get(str(seat_id))


def waterway_tier_route(route: str) -> Optional[str]:
    """**路级派生聚合**：该路已登记治所中的**最高档**；一个都没登记 ⇒ `None`。

    注意：本函数**只认治所级真账**。若需"源表值"请直接读 `trade_shadow.ROUTE_WATERWAY`。
    """
    best: Optional[str] = None
    best_rank = len(TIER_ORDER)
    for tier, routes in _route_table().items():
        if route not in routes:
            continue
        for sid, seat_tier in SEAT_WATERWAY.items():
            # 治所 id 形如 `路|治所`（稳定主键，见 prefecture_entity）
            if not str(sid).startswith(str(route) + "|"):
                continue
            if seat_tier != tier:
                continue
            rank = TIER_ORDER.index(seat_tier) if seat_tier in TIER_ORDER else len(TIER_ORDER)
            if rank < best_rank:
                best, best_rank = seat_tier, rank
    return best


def survey_waterway() -> dict:
    """**对账**：逐路比对「派生值」与「史料源表值」——本批要求**逐路相等**。"""
    out = {"路由数": 0, "失配": []}
    for tier, routes in _route_table().items():
        for route in routes:
            out["路由数"] += 1
            derived = waterway_tier_route(route)
            if derived != tier:
                out["失配"].append({"路": route, "源表": tier, "派生": derived})
    return out
