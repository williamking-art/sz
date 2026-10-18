# -*- coding: utf-8 -*-
"""人事令（2026-10-18 用户设定）：**皇威权柄 > 阈值 ⇒ 当场任免；否则走流程**。

- 直行：皇威高于 `imperial_mandate` 的 `appoint` 阈值 ⇒ 皇帝言出即行，
  跳过执行侧权限与程序，但仍校验目标合法/职位存在，并支付皇威代价；
- 走流程：皇威不足 ⇒ 承办人必须因**在任职位**持有「官吏铨选」，
  令进入 `state.statistics["pending_personnel_orders"]`，`due_turn=T+1` 结算；
- 幂等键 `order_id`，已落地/失败的令不重复执行；
- 低层 `appoint_*`/`dismiss_*` 仍是即时写入口；本模块是玩家/诏令侧通道。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from core import imperial_mandate
from core.permission_model import personnel_authority

__all__ = [
    "PRESTIGE_IMMEDIATE_THRESHOLD", "can_appoint_immediately",
    "issue_personnel_order", "settle_personnel_orders",
    "PENDING_KEY", "LEDGER_KEY",
]

PRESTIGE_IMMEDIATE_THRESHOLD = imperial_mandate.threshold("appoint") or 80
PENDING_KEY = "pending_personnel_orders"
LEDGER_KEY = "personnel_order_ledger"

_ACTIONS = (
    "appoint_circuit", "dismiss_circuit",
    "appoint_prefect", "dismiss_prefect",
)


def can_appoint_immediately(state) -> bool:
    """皇威权柄：`appoint` 已接线且皇威 > 阈值 ⇒ 可当场任免。"""
    return imperial_mandate.can_direct(state, "appoint")


def _stats(state) -> Dict[str, Any]:
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats
    return stats


def _queue(state) -> list:
    stats = _stats(state)
    queue = stats.get(PENDING_KEY)
    if not isinstance(queue, list):
        queue = []
        stats[PENDING_KEY] = queue
    return queue


def _ledger(state) -> Dict[str, Any]:
    stats = _stats(state)
    ledger = stats.get(LEDGER_KEY)
    if not isinstance(ledger, dict):
        ledger = {}
        stats[LEDGER_KEY] = ledger
    return ledger


def _order_key(action: str, order: Dict[str, Any]) -> str:
    if action in ("appoint_circuit", "dismiss_circuit"):
        key = f"{order.get('circuit') or ''}|{order.get('role_key') or ''}"
    else:
        key = f"{order.get('seat_id') or ''}|{order.get('role') or ''}"
    if action.startswith("appoint"):
        key += f"|{(order.get('official_data') or {}).get('name') or ''}"
    return key


def _order_id(action: str, order: Dict[str, Any], turn: int) -> str:
    raw = f"{action}|{_order_key(action, order)}|{turn}"
    return "po_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _apply(state, order: Dict[str, Any]) -> Dict[str, Any]:
    """执行一条人事令（低层写入口只在这里被调用）。"""
    action = order.get("action")
    executor = order.get("executor")
    try:
        if action == "appoint_circuit":
            from core.domains.administration.circuit_officials import (
                appoint_circuit_official,
            )
            ok = appoint_circuit_official(
                state, order.get("circuit"), order.get("role_key"),
                order.get("official_data") or {}, executor=executor,
                imperial_direct=bool(order.get("imperial_direct")),
            )
            return {"ok": bool(ok), "result": ok}
        if action == "dismiss_circuit":
            from core.domains.administration.circuit_officials import (
                dismiss_circuit_official,
            )
            result = dismiss_circuit_official(
                state, order.get("circuit"), order.get("role_key"),
                reason=order.get("reason") or "罢免", executor=executor,
                imperial_direct=bool(order.get("imperial_direct")),
            )
            return {"ok": result is not None, "result": result}
        if action == "appoint_prefect":
            from core.domains.administration.prefect_officials import (
                appoint_prefect_official,
            )
            result = appoint_prefect_official(
                state, order.get("seat_id"), order.get("role"),
                order.get("official_data") or {}, executor=executor,
                imperial_direct=bool(order.get("imperial_direct")),
            )
            return {"ok": bool((result or {}).get("ok")), "result": result}
        if action == "dismiss_prefect":
            from core.domains.administration.prefect_officials import (
                dismiss_prefect_official,
            )
            result = dismiss_prefect_official(
                state, order.get("seat_id"), order.get("role"),
                executor=executor,
                imperial_direct=bool(order.get("imperial_direct")),
            )
            return {"ok": bool((result or {}).get("ok")), "result": result}
    except Exception as e:  # noqa: BLE001 — 单令人事失败不炸结算
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": False, "error": f"未知人事令动作：{action}"}


def issue_personnel_order(
    state,
    *,
    action: str,
    executor=None,
    circuit: Optional[str] = None,
    role_key: Optional[str] = None,
    seat_id: Optional[str] = None,
    role: Optional[str] = None,
    official_data: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Dict[str, Any]:
    """玩家/诏令侧入口：皇威 >80 立即落地；否则入队，下一回合结算。"""
    act = str(action or "").strip()
    if act not in _ACTIONS:
        return {"ok": False, "immediate": False, "reason": f"未知人事令动作：{act}"}
    if act.startswith("appoint") and not isinstance(official_data, dict):
        return {"ok": False, "immediate": False, "reason": "任命缺 official_data"}

    turn = int(getattr(state, "turn", 0) or 0)
    direct = can_appoint_immediately(state)
    order = {
        "action": act, "executor": executor,
        "circuit": circuit, "role_key": role_key,
        "seat_id": seat_id, "role": role,
        "official_data": dict(official_data or {}),
        "reason": reason, "created_turn": turn,
        "due_turn": turn + 1, "status": "pending",
        "imperial_direct": direct,
    }
    oid = _order_id(act, order, turn)
    order["order_id"] = oid

    if direct:
        res = _apply(state, order)
        status = "applied" if res.get("ok") else "failed"
        cost = imperial_mandate.charge_direct_cost(state, "appoint") if res.get("ok") else 0
        _ledger(state)[oid] = {
            "status": status, "turn": turn, "action": act, "mode": "imperial_direct",
            "error": res.get("error"), "immediate": True, "prestige_cost": cost,
        }
        return {
            "ok": bool(res.get("ok")), "immediate": True, "order_id": oid,
            "mode": "imperial_direct", "prestige_cost": cost,
            "result": res.get("result"), "error": res.get("error"),
        }

    ok, actor_or_reason, mode = personnel_authority(state, executor, strict=True)
    if not ok:
        return {"ok": False, "immediate": False, "reason": actor_or_reason, "mode": mode}

    queue = _queue(state)
    if any(str(o.get("order_id")) == oid for o in queue):
        return {"ok": True, "immediate": False, "order_id": oid,
                "due_turn": order["due_turn"], "duplicate": True, "mode": mode}
    queue.append(order)
    return {"ok": True, "immediate": False, "order_id": oid,
            "due_turn": order["due_turn"], "mode": mode}


def settle_personnel_orders(state, turn: Optional[int] = None) -> Dict[str, Any]:
    """在下一回合结算走流程的人事令（由 `_settle_officialdom` 调用）。"""
    current = int(getattr(state, "turn", 0) or 0) if turn is None else int(turn)
    queue = _queue(state)
    ledger = _ledger(state)
    remaining = []
    applied = failed = 0
    for order in list(queue):
        if not isinstance(order, dict) or order.get("status") != "pending":
            continue
        oid = str(order.get("order_id") or "")
        if not oid or oid in ledger:
            continue
        try:
            due = int(order.get("due_turn", 0) or 0)
        except (TypeError, ValueError):
            due = 0
        if due > current:
            remaining.append(order)
            continue
        ok, actor_or_reason, mode = personnel_authority(
            state, order.get("executor"), strict=True
        )
        if not ok:
            order["status"] = "failed"
            order["reason"] = actor_or_reason
            ledger[oid] = {
                "status": "failed", "turn": current, "action": order.get("action"),
                "mode": mode, "error": actor_or_reason, "immediate": False,
            }
            failed += 1
            continue
        res = _apply(state, order)
        status = "applied" if res.get("ok") else "failed"
        order["status"] = status
        ledger[oid] = {
            "status": status, "turn": current, "action": order.get("action"),
            "mode": mode, "error": res.get("error"), "immediate": False,
        }
        if status == "applied":
            applied += 1
        else:
            failed += 1
    _stats(state)[PENDING_KEY] = remaining
    return {"applied": applied, "failed": failed, "pending": len(remaining)}

