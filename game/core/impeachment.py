# -*- coding: utf-8 -*-
"""M3a 弹劾案件闭环（JEV 裁 B：中枢大臣 + 联名弹章）。

链路：弹章 → 开案 investigating → 证据审查 → 制度建议 → awaiting_disposal
→ 玩家处置（pardon/force_dismiss/remand/none）→ 可追溯人事动作。

纪律：
- 准奏只开案，不直接罢官；留中不开案；
- 事实只看 evidence_refs，派系影响力不进入 fact_finding/裁定；
- force_dismiss 不改 fact_finding；同一 case_id 幂等；
- 中枢目标只清 holder + mark_minister_status，不直接删大臣；
- 状态在 `state.impeachments`（save_load 白名单）。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

__all__ = [
    "open_case", "review_case", "dispose_case",
    "settle_impeachment_cases", "case_of",
]


def _cases(state) -> dict:
    cases = getattr(state, "impeachments", None)
    if not isinstance(cases, dict):
        cases = {}
        state.impeachments = cases
    return cases


def case_of(state, case_id: str) -> Optional[Dict[str, Any]]:
    return _cases(state).get(str(case_id or ""))


def _case_id(memorial: Dict[str, Any], turn: int) -> str:
    raw = f"{memorial.get('memorial_id') or ''}|{memorial.get('target') or ''}|{turn}"
    return "imp_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def open_case(state, memorial: Dict[str, Any]) -> Dict[str, Any]:
    """准奏弹章 → 开案；缺字段拒绝，不直接罢官。"""
    if not isinstance(memorial, dict):
        return {"ok": False, "msg": "弹章不是对象"}
    target = str(memorial.get("target") or "").strip()
    fact = str(memorial.get("trigger_fact") or "").strip()
    accusers = [str(x).strip() for x in (memorial.get("accusers") or [])
                if str(x).strip()]
    if not accusers and str(memorial.get("accuser") or "").strip():
        accusers = [str(memorial.get("accuser")).strip()]
    if not target or not fact or not accusers:
        return {"ok": False, "msg": "弹章缺少 target/trigger_fact/accuser(s)，不开案"}

    turn = int(getattr(state, "turn", 0) or 0)
    cid = _case_id(memorial, turn)
    cases = _cases(state)
    if cid in cases:
        return {"ok": True, "case_id": cid, "duplicate": True,
                "msg": f"弹章已开案（{cid}）"}
    cases[cid] = {
        "case_id": cid,
        "status": "investigating",
        "target": target,
        "target_kind": str(memorial.get("target_kind") or "central"),
        "circuit": memorial.get("circuit"),
        "role_key": memorial.get("role_key"),
        "seat_id": memorial.get("seat_id"),
        "role": memorial.get("role"),
        "accusers": accusers,
        "trigger_fact": fact,
        "target_faction": memorial.get("target_faction"),
        "evidence_refs": list(memorial.get("evidence_refs") or []),
        "severity": float(memorial.get("severity", 0.5) or 0.5),
        "fact_finding": None,
        "evidence_score": None,
        "institutional_ruling": None,
        "imperial_disposal": None,
        "due_turn": turn + 1,
        "created_turn": turn,
        "closed_turn": None,
        "event_ids": [],
        "memorial_id": memorial.get("memorial_id"),
    }
    return {"ok": True, "case_id": cid, "msg": f"已准奏开案（{cid}），待查证。"}


def _ref_status(state, ref) -> tuple[bool, bool]:
    """返回 (可解析, 已核实)。只认显式 verified/可解析引用，不猜。"""
    if not isinstance(ref, dict):
        return False, False
    if "verified" in ref:
        return True, bool(ref.get("verified"))
    if ref.get("id") or ref.get("ref"):
        return True, False
    return False, False


def review_case(state, case_id: str) -> Dict[str, Any]:
    case = case_of(state, case_id)
    if not case:
        return {"ok": False, "msg": "案件不存在"}
    if case.get("status") != "investigating":
        return {"ok": True, "case": case}
    refs = case.get("evidence_refs") or []
    resolved = [_ref_status(state, r) for r in refs]
    verified = sum(1 for ok, v in resolved if ok and v)
    resolvable = sum(1 for ok, _ in resolved if ok)
    if not refs:
        fact = "unknown"
        score = 0.0
    else:
        ratio = verified / max(1, len(refs))
        score = max(0.0, min(1.0, 0.6 * ratio + 0.4 * min(1.0, float(case.get("severity", 0.5)))))
        if verified >= 1 and score >= 0.5:
            fact = "supported"
        elif resolvable == len(refs) and verified == 0:
            fact = "unsupported"
        else:
            fact = "unknown"
    case["fact_finding"] = fact
    case["evidence_score"] = round(score, 4)
    sev = float(case.get("severity", 0.5))
    if fact == "unsupported":
        ruling = "acquit"
    elif fact == "unknown":
        ruling = "retry" if int(case.get("retry_count", 0) or 0) < 2 else "acquit"
    elif score >= 0.7 and sev >= 0.6:
        ruling = "dismiss"
    elif score >= 0.4:
        ruling = "demote"
    else:
        ruling = "acquit"
    case["institutional_ruling"] = ruling
    if fact == "unknown" and ruling == "retry":
        case["retry_count"] = int(case.get("retry_count", 0) or 0) + 1
        case["due_turn"] = int(state.turn) + 1
        case["status"] = "investigating"
    else:
        case["status"] = "awaiting_disposal"
        case["due_turn"] = None
    return {"ok": True, "case": case}


def _event(state, event_id: str, payload: Dict[str, Any]) -> bool:
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        return False
    ledger = stats.setdefault("political_event_ledger", {})
    if event_id in ledger:
        return False
    ledger[event_id] = dict(payload)
    return True


def _dismiss_target(state, case: Dict[str, Any]) -> bool:
    target = str(case.get("target") or "")
    kind = str(case.get("target_kind") or "central")
    if kind == "circuit":
        from core.domains.administration.circuit_officials import dismiss_circuit_official
        return dismiss_circuit_official(
            state, case.get("circuit"), case.get("role_key"),
            reason="弹劾裁定") is not None
    if kind == "prefect":
        from core.domains.administration.prefect_officials import dismiss_prefect_official
        return bool((dismiss_prefect_official(
            state, case.get("seat_id"), case.get("role")) or {}).get("ok"))
    cleared = []
    for org in (getattr(state, "central_orgs", None) or {}).values():
        holders = org.get("holders") if isinstance(org, dict) else None
        if not isinstance(holders, dict):
            continue
        for title, holder in list(holders.items()):
            if str(holder or "") == target:
                holders[title] = ""
                cleared.append(title)
    if hasattr(state, "mark_minister_status"):
        state.mark_minister_status(target, "dismissed")
    return bool(cleared)


def dispose_case(state, case_id: str, disposal: str,
                 executor=None) -> Dict[str, Any]:
    case = case_of(state, case_id)
    if not case:
        return {"ok": False, "msg": "案件不存在"}
    if case.get("status") == "closed":
        return {"ok": True, "case": case, "duplicate": True}
    if case.get("status") != "awaiting_disposal":
        return {"ok": False, "msg": "案件尚未完成查证，不能处置"}
    disposal = str(disposal or "none")
    case["imperial_disposal"] = disposal
    dismissed = False
    if disposal == "remand":
        case["status"] = "investigating"
        case["due_turn"] = int(state.turn) + 1
        case["fact_finding"] = None
        case["institutional_ruling"] = None
        return {"ok": True, "case": case}
    if disposal == "force_dismiss":
        dismissed = _dismiss_target(state, case)
    elif disposal == "none":
        if case.get("institutional_ruling") == "dismiss":
            dismissed = _dismiss_target(state, case)
    elif disposal == "pardon":
        dismissed = False
    else:
        return {"ok": False, "msg": f"未知处置：{disposal}"}
    case["status"] = "closed"
    case["closed_turn"] = int(state.turn)
    case["due_turn"] = None
    eid = f"{case_id}:dispose"
    if _event(state, eid, {
        "kind": "impeachment_dispose", "case_id": case_id,
        "target": case.get("target"), "disposal": disposal,
        "dismissed": dismissed, "turn": int(state.turn),
    }):
        case["event_ids"].append(eid)
    return {"ok": True, "case": case, "dismissed": dismissed}


def settle_impeachment_cases(state) -> Dict[str, Any]:
    """月度固定点：到期案件查证；不自动罢官。"""
    turn = int(getattr(state, "turn", 0) or 0)
    reviewed = 0
    for cid, case in list(_cases(state).items()):
        if not isinstance(case, dict):
            continue
        if case.get("status") != "investigating":
            continue
        due = case.get("due_turn")
        if due is not None and int(due) > turn:
            continue
        review_case(state, cid)
        reviewed += 1
    return {"reviewed": reviewed}

