# -*- coding: utf-8 -*-
"""M2a：显式事权诏令的三关与 resisted 状态机（旧诏令不走这里）。

只处理 `primary_matter`/`co_matters` 全部落在 `M2A_MATTERS` 的诏令；
旧调用（无 primary/co）完全不进入，由 `settlement_decree` 原循环处理。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from content.ministers.data import MINISTERS
from core.ai.tiandao_engine import TianDaoEngine
from core.authority_gate import check_matter_authority
from core.decree_confirm import (
    OUTCOME_EXECUTED,
    OUTCOME_FAILED,
    OUTCOME_REGISTERED_ONLY,
    OUTCOME_VETOED,
    STATUS_CONFIRMED,
    STATUS_MISMATCH,
    STATUS_UNAUTHORIZED,
    STATUS_UNDEFINED,
    STATUS_VETO,
    canonical_decree,
    confirm_decree,
    decree_digest,
    ensure_decree_id,
    execution_of,
    record_execution,
)
from core.permission_model import permission_holders

M2A_MATTERS = {"官吏铨选", "度支调度"}
M2A_PROCEDURE_INTENTS = {"调停", "站队", "打压"}


def matters_of(decree: Dict[str, Any]) -> List[str]:
    primary = str(decree.get("primary_matter") or "").strip()
    co = [str(x).strip() for x in (decree.get("co_matters") or []) if str(x).strip()]
    out = []
    for m in [primary] + co:
        if m and m not in out:
            out.append(m)
    return out


def is_m2a_decree(decree: Dict[str, Any]) -> bool:
    matters = matters_of(decree)
    return bool(matters) and all(m in M2A_MATTERS for m in matters)


def _reviewer_faction(name: str) -> str:
    return str((MINISTERS.get(name) or {}).get("faction") or "")


def _event_once(state, event_id: str, payload: Dict[str, Any]) -> bool:
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        return False
    ledger = stats.setdefault("political_event_ledger", {})
    if not isinstance(ledger, dict):
        return False
    if event_id in ledger:
        return False
    ledger[event_id] = dict(payload)
    return True


def _fail(state, decree, log, *, did, reason, digest, outcome=OUTCOME_FAILED,
          detail="", confirm_status=STATUS_UNAUTHORIZED):
    decree["exec_state"] = "not_entered"
    decree["exec_reason"] = reason
    record_execution(
        state, did, by=decree.get("executor_actor") or "朝廷",
        digest=digest, title=decree.get("title"),
        confirm_status=confirm_status, outcome=outcome, detail=detail or reason,
    )
    log.append(f"[诏令] 「{decree.get('title', '')}」M2a 未执行：{reason}。")
    return "done"


def settle_m2a_decree(state, decree: Dict[str, Any], log) -> str:
    """返回 `done`（终态/已处理）或 `pending`（留在队列）。"""
    did = ensure_decree_id(state, decree)
    digest = decree_digest(canonical_decree(decree))
    prev = execution_of(state, did)
    if prev and prev.get("outcome") in (
        OUTCOME_EXECUTED, OUTCOME_REGISTERED_ONLY, OUTCOME_VETOED
    ):
        return "done"

    matters = matters_of(decree)
    executor = decree.get("executor")
    # 关口一：结算前重校验 actor 仍在任并有权限
    actor = ""
    for matter in matters:
        ok, actor_or_reason = check_matter_authority(state, executor, matter)
        if not ok:
            return _fail(state, decree, log, did=did,
                         reason=f"承办人失效：{actor_or_reason}", digest=digest)
        actor = actor_or_reason
    decree["executor_actor"] = actor or decree.get("executor_actor")

    # 关口二：程序态
    procedure = str(decree.get("procedure_state") or "not_required")
    if procedure == "pending_review":
        reviewer = str(decree.get("procedure_reviewer") or "").strip()
        if not reviewer:
            holders = permission_holders(state, "诏令封驳")
            reviewer = holders[0] if holders else ""
        if not reviewer:
            decree["exec_state"] = "not_entered"
            return "pending"
        ok, _why = check_matter_authority(state, reviewer, "诏令封驳")
        if not ok:
            decree["exec_state"] = "not_entered"
            return "pending"
        decree["procedure_reviewer"] = reviewer
        decree["procedure_reviewed_turn"] = int(state.turn)
        veto = reviewer in (decree.get("veto_ministers") or [])
        oppose = _reviewer_faction(reviewer) in (decree.get("oppose_factions") or [])
        if veto or oppose:
            decree["procedure_state"] = "returned"
            return _fail(
                state, decree, log, did=did,
                reason="程序封驳：reviewer 明示反对", digest=digest,
                outcome=OUTCOME_VETOED, detail="procedure_returned",
                confirm_status=STATUS_VETO,
            )
        decree["procedure_state"] = "passed"
    if procedure == "returned":
        return "done"
    if procedure not in ("not_required", "passed", "bypassed"):
        decree["exec_state"] = "not_entered"
        decree["exec_reason"] = f"unknown_procedure_state:{procedure}"
        return "pending"

    # 等待期：due_turn 未到，不重评、不掷点
    due = decree.get("due_turn")
    if due is not None and int(due) > int(state.turn):
        return "pending"

    # 关口三：受命人复述（有受命人时）
    addrs = decree.get("addressees") or []
    aid = str(addrs[0]).strip() if addrs else ""
    if aid:
        gate = confirm_decree(state, did, aid, decree=decree, record=True, turn=state.turn)
        st = gate.get("status")
        if st == STATUS_UNDEFINED:
            decree["exec_state"] = "not_entered"
            return "pending"
        if st in (STATUS_MISMATCH, STATUS_UNAUTHORIZED):
            return _fail(state, decree, log, did=did,
                         reason=f"复述/受命受阻：{gate.get('reason')}", digest=digest)
        if st == STATUS_VETO:
            ok, _why = check_matter_authority(state, aid, "诏令封驳")
            if ok:
                decree["procedure_state"] = "returned"
                return _fail(state, decree, log, did=did,
                             reason="封驳", digest=digest,
                             outcome=OUTCOME_VETOED, detail="veto",
                             confirm_status=STATUS_VETO)
            decree["refusal_fact"] = {
                "who": aid, "when": int(state.turn), "decree_id": did,
                "reason_code": "unknown", "reason_text": str(gate.get("reason") or ""),
            }
            return _fail(state, decree, log, did=did,
                         reason="拒收事实（未定罪）", digest=digest)
        if st != STATUS_CONFIRMED:
            return "pending"

    # 确定性执行掷点
    period = int(decree.get("resist_period", 0) or 0)
    try:
        rate = float(state.calc_decree_execution_rate(
            decree.get("faction_stances", {}),
            is_secret=decree.get("is_secret", False),
            is_direct=decree.get("is_direct", False),
            secret_loyalty=decree.get("secret_loyalty", 0.5),
            is_zhongzhi=decree.get("is_zhongzhi", False),
            org_hint=decree.get("org_hint", "政府"),
        ))
    except Exception:
        rate = 0.5
        decree["rate_undefined"] = True
    rate = max(0.05, min(0.95, rate))
    seed = int(hashlib.sha1(
        f"{did}|{matters[0]}|{state.turn}|{period}|{actor}".encode("utf-8")
    ).hexdigest()[:16], 16)
    roll = 0.5 + TianDaoEngine.dice(seed, entropy=0.5)
    success = roll < rate

    if success:
        from core.settlement import _apply_decree_effect
        _apply_decree_effect(state, decree, log)
        for m in matters:
            decree.setdefault("matter_exec", {})[m] = {
                "status": "executed", "executor": actor, "attempts": period + 1,
                "last_turn": int(state.turn), "due_turn": None, "error": "",
            }
        decree["exec_state"] = "ready"
        decree["completed_turn"] = int(state.turn)
        record_execution(
            state, did, by=actor, digest=digest, title=decree.get("title"),
            confirm_status=STATUS_CONFIRMED, outcome=OUTCOME_EXECUTED,
        )
        return "done"

    if period < 2:
        decree["exec_state"] = "resisted"
        decree["resist_period"] = period + 1
        decree["due_turn"] = int(state.turn) + 1
        decree["exec_reason"] = "execution_resisted"
        for m in matters:
            decree.setdefault("matter_exec", {})[m] = {
                "status": "resisted", "executor": actor, "attempts": period + 1,
                "last_turn": int(state.turn), "due_turn": int(state.turn) + 1,
                "error": "",
            }
        log.append(f"[诏令] 「{decree.get('title', '')}」执行受阻，resist_period={period + 1}。")
        return "pending"

    decree["exec_state"] = "blocked"
    decree["exec_reason"] = "resisted_expired"
    decree["completed_turn"] = int(state.turn)
    for m in matters:
        decree.setdefault("matter_exec", {})[m] = {
            "status": "failed", "executor": actor, "attempts": period + 1,
            "last_turn": int(state.turn), "due_turn": None, "error": "resisted_expired",
        }
    _event_once(state, f"{did}:resisted_expired", {
        "kind": "resisted_expired", "decree_id": did, "turn": int(state.turn),
    })
    record_execution(
        state, did, by=actor, digest=digest, title=decree.get("title"),
        confirm_status=STATUS_CONFIRMED, outcome=OUTCOME_FAILED,
        detail="resisted_expired",
    )
    log.append(f"[诏令] 「{decree.get('title', '')}」三期受阻，终止。")
    return "done"

