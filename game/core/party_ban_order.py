# -*- coding: utf-8 -*-
"""党禁令（2026-10-19，M4 最小闭环）。

- 皇威 > `imperial_mandate.party_ban` 阈值（90）⇒ 直行：立即写 faction ban + 扣皇威；
- 皇威不足 ⇒ 入 `state.statistics["pending_party_ban_orders"]`，`due_turn=T+1` 结算；
- 幂等 `order_id`，已落地/失败不重复；
- 不新增顶层 `state.*`；不生成奏折/UI。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from core import imperial_mandate
from core.faction_ban import BAN_LEVELS, start_faction_ban

__all__ = [
    "PENDING_KEY", "LEDGER_KEY", "can_ban_immediately",
    "issue_party_ban_order", "settle_party_ban_orders",
]

PENDING_KEY = "pending_party_ban_orders"
LEDGER_KEY = "party_ban_order_ledger"


def can_ban_immediately(state) -> bool:
    return bool(imperial_mandate.can_direct(state, "party_ban"))


def _stats(state) -> Dict[str, Any]:
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats
    return stats


def _queue(state) -> list:
    q = _stats(state).get(PENDING_KEY)
    if not isinstance(q, list):
        q = []
        _stats(state)[PENDING_KEY] = q
    return q


def _ledger(state) -> Dict[str, Any]:
    led = _stats(state).get(LEDGER_KEY)
    if not isinstance(led, dict):
        led = {}
        _stats(state)[LEDGER_KEY] = led
    return led


def _order_id(faction: str, level: str, decree_id: str, turn: int) -> str:
    raw = f"{faction}|{level}|{decree_id}|{turn}"
    return "pb_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _apply(state, order: Dict[str, Any]) -> Dict[str, Any]:
    faction = str(order.get("faction") or "")
    level = str(order.get("level") or "")
    res = start_faction_ban(
        state, faction, level,
        decree_id=str(order.get("decree_id") or ""),
        turn=int(order.get("apply_turn") or 0))
    if not res.get("ok"):
        order["status"] = "failed"
        order["error"] = res.get("reason", "")
        return res
    order["status"] = "applied"
    order["applied_turn"] = int(order.get("apply_turn") or 0)
    return res


def issue_party_ban_order(
    state,
    *,
    faction: str,
    level: str = "轻",
    executor=None,
    decree_id: str = "",
    reason: str = "",
    turn: Optional[int] = None,
) -> Dict[str, Any]:
    """玩家/诏令侧入口：高皇威直行，否则入队下一回合。"""
    fac = str(faction or "").strip()
    lv = str(level or "轻").strip()
    if fac not in (getattr(state, "factions", None) or {}):
        return {"ok": False, "immediate": False, "reason": "unknown_faction"}
    if lv not in BAN_LEVELS:
        return {"ok": False, "immediate": False, "reason": "unknown_level"}
    now = int(getattr(state, "turn", 0) or 0) if turn is None else int(turn)
    did = str(decree_id or f"party_ban:{fac}:{now}")
    oid = _order_id(fac, lv, did, now)
    ledger = _ledger(state)
    if oid in ledger and ledger[oid].get("status") in ("applied", "failed"):
        return {"ok": True, "immediate": False, "duplicate": True,
                "order": ledger[oid]}

    direct = can_ban_immediately(state)
    order = {
        "order_id": oid, "faction": fac, "level": lv,
        "executor": executor, "decree_id": did, "reason": str(reason or ""),
        "created_turn": now, "due_turn": now + 1,
        "apply_turn": now, "status": "pending",
        "imperial_direct": direct,
    }
    ledger[oid] = order
    if direct:
        res = _apply(state, order)
        if res.get("ok"):
            order["prestige_cost"] = imperial_mandate.charge_direct_cost(state, "party_ban")
            order["immediate"] = True
            return {"ok": True, "immediate": True, "order": order}
        return {"ok": False, "immediate": True, "reason": res.get("reason"),
                "order": order}

    _queue(state).append(order)
    return {"ok": True, "immediate": False, "order": order}


def settle_party_ban_orders(state) -> Dict[str, Any]:
    """回合固定点：到期党禁令落地；幂等。"""
    turn = int(getattr(state, "turn", 0) or 0)
    applied = failed = 0
    for order in list(_queue(state)):
        if not isinstance(order, dict) or order.get("status") != "pending":
            continue
        if int(order.get("due_turn", turn + 1) or 0) > turn:
            continue
        order["apply_turn"] = turn
        res = _apply(state, order)
        if res.get("ok"):
            applied += 1
        else:
            failed += 1
    _queue(state)[:] = [o for o in _queue(state)
                        if isinstance(o, dict) and o.get("status") == "pending"]
    return {"applied": applied, "failed": failed}

