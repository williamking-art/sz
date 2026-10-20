# -*- coding: utf-8 -*-
"""军令待批队列（2026-10-19，低皇威走流程）。

- 低皇威 + `defer=True` 的军令入 `state.ai_pending_actions`（kind=military_dispatch），
  `payload.due_turn=T+1`，次月由枢密院/掌调兵主体批红落地；
- 高皇威直行不走此队列；
- 只消费既有 `approve_ai_action`，不新增落地通道。
"""
from __future__ import annotations

from typing import Any, Dict

__all__ = ["settle_military_orders", "military_order_delay_info"]


def military_order_delay_info(state, unit) -> Dict[str, Any]:
    """军令从京畿到编制单位驻地的交通耗时（复用军报同一入口）。"""
    seat = ""
    try:
        from core.foundation.ledger.building_bridge import capital_seat_id
        route = str(getattr(unit, "station", "") or "")
        pdata = (getattr(state, "prefectures", None) or {}).get(route)
        seat = str(capital_seat_id(pdata, route) or "") if isinstance(pdata, dict) else ""
    except Exception:  # noqa: BLE001 — 驻地不可读则回落
        seat = ""
    from core.military_report import military_report_delay_info
    info = military_report_delay_info(
        state, seat_id=seat, urgent=True, border=False)
    return {
        "delay_turns": max(1, int(info.get("delay_turns") or 1)),
        "distance_km": info.get("distance_km"),
        "basis": info.get("basis"),
        "route_hops": info.get("route_hops"),
    }


def settle_military_orders(state) -> Dict[str, Any]:
    turn = int(getattr(state, "turn", 0) or 0)
    applied = pending = 0
    for item in list(getattr(state, "ai_pending_actions", None) or []):
        if not isinstance(item, dict):
            continue
        if item.get("kind") != "military_dispatch" or item.get("status") != "pending":
            continue
        payload = item.get("payload") or {}
        if not payload.get("defer"):
            continue
        if int(payload.get("due_turn", turn + 1) or 0) > turn:
            pending += 1
            continue
        from core.commands import approve_ai_action
        approve_ai_action(state, str(item.get("id") or ""))
        applied += 1
    return {"applied": applied, "pending": pending}

