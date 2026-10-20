# -*- coding: utf-8 -*-
"""事故单与逐级处理（2026-10-19，奏折之前）。

- 事故存 `prefectures[parent_seat_id]["incidents"]`，不新增顶层 `state.*`；
- 县官从 MemoryGraph 的 `county`/`governs` 取；无县官则由州府通判/幕职代行；
- 逐级：locality → prefecture → circuit → central；急报可越级（调用方传 level）；
- 只做确定性处理，不随机；同 incident_id 幂等；
- 不做 UI、不直接写奏折；central 只给 summary/recommendation，后续由奏报层消费。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from core.county_registry import county_officials
from core.faction_ban import actor_faction, is_official_banned
from core.report_ledger import handle_report, record_raw_report
from memory.memory_graph import get_memory_graph

__all__ = ["create_incident", "settle_incidents", "incident_of", "incidents_of"]

_TERMINAL = {"resolved", "failed", "awaiting_decision"}
_NEXT_LEVEL = {"locality": "prefecture", "prefecture": "circuit",
               "circuit": "central", "central": None}
_KIND_ROLE = {
    "military": "shuai", "border": "shuai", "bandit": "shuai", "revolt": "shuai",
    "finance": "cao", "judicial": "xian",
    "flood": "cang", "famine": "cang", "grain": "cang",
}


def _seat_row(state, parent_seat_id: str) -> Optional[Dict[str, Any]]:
    """`路|治所` → `prefectures[路]["seats"][路|治所]` 真账行。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    seat = str(parent_seat_id or "").strip()
    route = seat.split("|")[0]
    row = prefs.get(route)
    seats = row.get("seats") if isinstance(row, dict) else None
    return seats.get(seat) if isinstance(seats, dict) else None


def _iter_seats(state):
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return
    for _route, row in prefs.items():
        seats = row.get("seats") if isinstance(row, dict) else None
        if not isinstance(seats, dict):
            continue
        for seat_id, seat_row in seats.items():
            if isinstance(seat_row, dict):
                yield str(seat_id), seat_row


def incidents_of(state, parent_seat_id: str) -> Dict[str, Any]:
    row = _seat_row(state, parent_seat_id)
    if not isinstance(row, dict):
        return {}
    inc = row.get("incidents")
    return inc if isinstance(inc, dict) else {}


def incident_of(state, parent_seat_id: str, incident_id: str) -> Optional[Dict[str, Any]]:
    return incidents_of(state, parent_seat_id).get(str(incident_id or ""))


def create_incident(state, *, kind: str, locality: str, parent_seat_id: str,
                    route: str = "", severity: float = 0.5,
                    level: str = "locality", summary: str = "",
                    submitted_by: str = "", from_post: str = "",
                    channel: str = "通进银台司",
                    channel_matter: str = "奏章进纳",
                    body: str = "", delay_turns: int = 0,
                    priority: str = "normal") -> Dict[str, Any]:
    """开事故单；父州府必须真实存在。"""
    seat = str(parent_seat_id or "").strip()
    loc = str(locality or "").strip()
    seat_row = _seat_row(state, seat)
    if seat_row is None:
        return {"ok": False, "reason": "parent_seat_not_found"}
    if not loc:
        return {"ok": False, "reason": "locality_required"}
    turn = int(getattr(state, "turn", 0) or 0)
    raw = f"{kind}|{loc}|{seat}|{turn}"
    iid = "inc_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    row = seat_row
    row.setdefault("incidents", {})
    if iid in row["incidents"]:
        return {"ok": True, "incident": row["incidents"][iid], "duplicate": True}
    inc = {
        "incident_id": iid,
        "kind": str(kind or "governance"),
        "locality": loc,
        "parent_seat_id": seat,
        "route": str(route or seat.split("|")[0]),
        "severity": max(0.0, min(1.0, float(severity))),
        "status": "reported",
        "level": str(level or "locality"),
        "handled_by": "",
        "acting_official": "",
        "escalation_path": [],
        "raw_report_ids": [],
        "summary": str(summary or f"{loc}{kind}事"),
        "recommendation": "",
        "unresolved": [],
        "created_turn": turn,
        "due_turn": turn + 1 + max(0, int(delay_turns or 0)),
        "priority": str(priority or "normal"),
        "delay_turns": max(0, int(delay_turns or 0)),
        "arrive_turn": turn + max(0, int(delay_turns or 0)),
    }
    row["incidents"][iid] = inc
    rid = record_raw_report(
        state, incident_id=iid, parent_seat_id=seat,
        submitted_by=submitted_by or f"{loc}{kind}有司",
        from_post=from_post, channel=channel,
        channel_matter=channel_matter,
        title=f"{loc}{kind}事", body=body or inc["summary"],
        priority=priority, delay_turns=delay_turns,
        arrive_turn=inc["arrive_turn"], turn=turn)
    if rid:
        inc["raw_report_ids"] = [rid]
    return {"ok": True, "incident": inc}


def _capacity(actor: Dict[str, Any], penalty: float = 0.0) -> float:
    try:
        ab = float(actor.get("ability", 0.6) or 0.6)
        it = float(actor.get("integrity", 0.6) or 0.6)
    except (TypeError, ValueError):
        ab, it = 0.6, 0.6
    return max(0.0, min(1.0, 0.6 * ab + 0.4 * it - penalty))


def _county_actor(state, locality: str) -> Optional[Dict[str, Any]]:
    try:
        mem = get_memory_graph(getattr(state, "slot", 0))
        holders = county_officials(mem, locality)
    except Exception:
        holders = []
    if not holders:
        return None
    for holder in holders:
        name = str(holder.get("name") or holder.get("eid") or "")
        if not name or is_official_banned(state, name):
            continue
        return {"name": name, "ability": 0.65, "integrity": 0.65,
                "faction": actor_faction(state, holder), "acting": False}
    return None


def _prefecture_actor(state, seat: str) -> Optional[Dict[str, Any]]:
    po = (getattr(state, "prefect_officials", None) or {}).get(seat)
    if not isinstance(po, dict):
        return None
    for key in ("subprefect", "prefect"):
        row = po.get(key)
        if not isinstance(row, dict) or not str(row.get("name") or "").strip():
            continue
        if is_official_banned(state, row):
            continue
        return dict(row, acting=(key == "subprefect"))
    return None


def _circuit_actor(state, route: str, kind: str) -> Optional[Dict[str, Any]]:
    c = (getattr(state, "circuit_officials", None) or {}).get(route)
    if not isinstance(c, dict):
        return None
    offs = c.get("officials") or {}
    role = _KIND_ROLE.get(kind, "prefect")
    row = offs.get(role) or offs.get("prefect")
    if (isinstance(row, dict) and str(row.get("name") or "").strip()
            and not is_official_banned(state, row)):
        return row
    return None


def _incident_memorial(state, inc: Dict[str, Any]) -> None:
    """central 事故 → 御前摘要折；同一 incident_id 幂等。"""
    memos = getattr(state, "memorials", None)
    if not isinstance(memos, list):
        memos = []
        state.memorials = memos
    mid = "mem_inc_" + str(inc.get("incident_id") or "")
    if any(isinstance(m, dict) and m.get("memorial_id") == mid for m in memos):
        return
    kind = "military" if inc.get("kind") in (
        "military", "border", "bandit", "revolt") else "governance"
    req = _recommend(inc.get("kind"))
    memo = {
        "memorial_id": mid,
        "kind": kind,
        "title": f"《{inc.get('locality', '')}{inc.get('kind', '')}急奏》",
        "body": (f"{inc.get('summary', '')}。"
                 f"有司核议：{req}。"
                 f"（原件 {len(inc.get('raw_report_ids') or [])} 件留档）"),
        "source_tag": "通进银台司进呈",
        "incident_id": inc.get("incident_id"),
        "raw_report_ids": list(inc.get("raw_report_ids") or []),
        "recommendation": req,
        "priority": ("urgent" if str(inc.get("priority") or "") == "urgent"
                     or float(inc.get("severity", 0.5)) >= 0.7 else "normal"),
    }
    if memo["priority"] == "urgent":
        memos.insert(0, memo)
    else:
        memos.append(memo)
    inc["memorial_id"] = mid


def _recommend(kind: str) -> str:
    return {
        "flood": "请拨帑、免赋、开常平", "famine": "请拨粮、赈济、平粜",
        "bandit": "请调厢军/巡检捕盗", "revolt": "请调兵、抚剿",
        "border": "请枢密院调兵/备边", "fire": "请赈恤、重建",
        "epidemic": "请遣医、拨药、隔离", "judicial": "请刑部/宪司复核",
    }.get(kind, "请有司核议、酌情处置")


def _escalate(state, inc: Dict[str, Any], *, reason: str, turn: int) -> None:
    rid = record_raw_report(
        state, incident_id=inc.get("incident_id", ""),
        parent_seat_id=inc.get("parent_seat_id", ""),
        submitted_by=inc.get("handled_by") or "有司",
        from_post=inc.get("level", ""),
        channel="通进银台司", channel_matter="奏章进纳",
        title=f"{inc.get('locality', '')}升级报",
        body=f"{inc.get('summary', '')}：{reason}", turn=turn)
    if rid and rid not in (inc.get("raw_report_ids") or []):
        inc.setdefault("raw_report_ids", []).append(rid)
    nxt = _NEXT_LEVEL.get(inc.get("level"), None)
    inc["escalation_path"].append({
        "level": inc.get("level"), "actor": inc.get("handled_by") or "有司",
        "turn": turn, "reason": reason,
    })
    if not nxt:
        inc["status"] = "awaiting_decision"
        inc["recommendation"] = _recommend(inc.get("kind"))
        inc["unresolved"].append(reason)
        inc["due_turn"] = None
        return
    inc["level"] = nxt
    inc["status"] = "escalated"
    inc["due_turn"] = turn + 1


def settle_incidents(state, turn: Optional[int] = None) -> Dict[str, Any]:
    """月度/回合固定点：逐级处理事故；只推进到 central 摘要层，不生成奏折。"""
    now = int(getattr(state, "turn", 0) or 0) if turn is None else int(turn)
    handled = escalated = resolved = 0
    for seat, row in list(_iter_seats(state)):
        if not isinstance(row, dict):
            continue
        incs = row.get("incidents")
        if not isinstance(incs, dict):
            continue
        for inc in list(incs.values()):
            if not isinstance(inc, dict):
                continue
            if inc.get("status") in _TERMINAL:
                continue
            due = inc.get("due_turn")
            if due is not None and int(due) > now:
                continue
            level = str(inc.get("level") or "locality")
            if level == "central":
                inc["status"] = "awaiting_decision"
                inc["recommendation"] = _recommend(inc.get("kind"))
                inc["due_turn"] = None
                for rid in inc.get("raw_report_ids") or []:
                    handle_report(
                        state, rid, handled_by="中书/门下",
                        summary=inc.get("summary", ""),
                        recommendation=inc.get("recommendation", ""), turn=now)
                _incident_memorial(state, inc)
                escalated += 1
                continue

            actor = None
            penalty = 0.0
            if level == "locality":
                actor = _county_actor(state, inc.get("locality", ""))
                if actor is None:
                    actor = _prefecture_actor(state, seat)
                    if actor:
                        actor["acting"] = True
                        inc["acting_official"] = actor.get("name", "")
                        penalty = 0.15
            elif level == "prefecture":
                actor = _prefecture_actor(state, seat)
            elif level == "circuit":
                actor = _circuit_actor(state, inc.get("route", ""), inc.get("kind", ""))

            if actor is None:
                _escalate(state, inc, reason="无在任承办官", turn=now)
                escalated += 1
                continue

            name = str(actor.get("name") or "有司")
            inc["handled_by"] = name
            handled += 1
            if _capacity(actor, penalty) >= float(inc.get("severity", 0.5)):
                inc["status"] = "resolved"
                inc["due_turn"] = None
                inc["recommendation"] = ""
                resolved += 1
            else:
                _escalate(state, inc, reason="本级能力/资源不足", turn=now)
                escalated += 1
    return {"handled": handled, "resolved": resolved, "escalated": escalated}

