# -*- coding: utf-8 -*-
"""奏报原件台账（2026-10-19，奏折之前/之后的分层）。

- 原件存 `prefectures[路]["seats"][seat]["raw_reports"]`，不新增顶层 `state.*`；
- 部门可 `handle_report`（已办/摘要/建议）或 `suppress_report`（压案/拖延）；
- 原件正文、来源、渠道永不因“没到御前”而删除；
- 御前摘要折只引用 `report_id`（`raw_report_ids`），不复制/篡改原件。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

__all__ = [
    "record_raw_report", "report_of", "raw_reports_of",
    "handle_report", "suppress_report", "delay_report",
    "report_status_summary",
]


def _seat_row(state, seat: str) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    seat = str(seat or "").strip()
    route = seat.split("|")[0]
    row = prefs.get(route)
    seats = row.get("seats") if isinstance(row, dict) else None
    return seats.get(seat) if isinstance(seats, dict) else None


def _reports(state, seat: str) -> Optional[Dict[str, Any]]:
    row = _seat_row(state, seat)
    if not isinstance(row, dict):
        return None
    reports = row.setdefault("raw_reports", {})
    return reports if isinstance(reports, dict) else None


def record_raw_report(
    state,
    *,
    incident_id: str,
    parent_seat_id: str,
    submitted_by: str = "地方有司",
    from_post: str = "",
    channel: str = "通进银台司",
    channel_matter: str = "奏章进纳",
    title: str = "",
    body: str = "",
    priority: str = "normal",
    delay_turns: int = 0,
    arrive_turn: Optional[int] = None,
    turn: Optional[int] = None,
) -> Optional[str]:
    """登记原件；同内容幂等；返回 report_id。"""
    reports = _reports(state, parent_seat_id)
    if reports is None:
        return None
    now = int(getattr(state, "turn", 0) or 0) if turn is None else int(turn)
    raw = f"{incident_id}|{submitted_by}|{channel}|{turn}|{str(body or '')[:120]}"
    rid = "rep_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    if rid in reports:
        return rid
    reports[rid] = {
        "report_id": rid,
        "incident_id": str(incident_id or ""),
        "parent_seat_id": str(parent_seat_id or ""),
        "submitted_by": str(submitted_by or ""),
        "from_post": str(from_post or ""),
        "channel": str(channel or ""),
        "channel_matter": str(channel_matter or ""),
        "title": str(title or ""),
        "body": str(body or ""),
        "created_turn": now,
        "priority": str(priority or "normal"),
        "delay_turns": int(delay_turns or 0),
        "arrive_turn": int(arrive_turn) if arrive_turn is not None else now,
        "status": "raw",
        "handled_by": "",
        "handled_turn": None,
        "summary": "",
        "recommendation": "",
        "suppressed_by": "",
        "suppressed_by_faction": False,
        "reason": "",
        "delay_until": None,
    }
    return rid


def report_of(state, report_id: str) -> Optional[Dict[str, Any]]:
    rid = str(report_id or "")
    prefs = getattr(state, "prefectures", None) or {}
    for row in prefs.values():
        seats = row.get("seats") if isinstance(row, dict) else None
        if not isinstance(seats, dict):
            continue
        for seat_row in seats.values():
            reports = seat_row.get("raw_reports") if isinstance(seat_row, dict) else None
            if isinstance(reports, dict) and rid in reports:
                return reports[rid]
    return None


def raw_reports_of(state, parent_seat_id: str) -> Dict[str, Any]:
    reports = _reports(state, parent_seat_id)
    return reports if isinstance(reports, dict) else {}


def _set_status(state, report_id: str, status: str, **fields: Any) -> bool:
    rep = report_of(state, report_id)
    if not isinstance(rep, dict):
        return False
    rep["status"] = status
    for k, v in fields.items():
        if v is not None:
            rep[k] = v
    return True


def handle_report(state, report_id: str, *, handled_by: str, summary: str = "",
                  recommendation: str = "", turn: Optional[int] = None) -> bool:
    now = int(getattr(state, "turn", 0) or 0) if turn is None else int(turn)
    return _set_status(
        state, report_id, "handled", handled_by=str(handled_by or ""),
        handled_turn=now, summary=str(summary or ""),
        recommendation=str(recommendation or ""), reason="")


def suppress_report(state, report_id: str, *, suppressed_by: str = "",
                    faction: str = "", reason: str = "压案") -> bool:
    return _set_status(
        state, report_id, "suppressed", suppressed_by=str(suppressed_by or ""),
        suppressed_by_faction=bool(faction), reason=str(reason or "压案"))


def delay_report(state, report_id: str, *, delay_until: int,
                 suppressed_by: str = "", reason: str = "拖延") -> bool:
    return _set_status(
        state, report_id, "delayed", delay_until=int(delay_until),
        suppressed_by=str(suppressed_by or ""), reason=str(reason or "拖延"))


def report_status_summary(state) -> Dict[str, int]:
    out: Dict[str, int] = {}
    prefs = getattr(state, "prefectures", None) or {}
    for row in prefs.values():
        seats = row.get("seats") if isinstance(row, dict) else None
        if not isinstance(seats, dict):
            continue
        for seat_row in seats.values():
            reports = seat_row.get("raw_reports") if isinstance(seat_row, dict) else None
            if not isinstance(reports, dict):
                continue
            for rep in reports.values():
                if not isinstance(rep, dict):
                    continue
                st = str(rep.get("status") or "raw")
                out[st] = out.get(st, 0) + 1
    return out

