# -*- coding: utf-8 -*-
"""军报/急递（2026-10-19，奏折前）。

- 军报先登记原件，按驿传/急递延迟到达；不瞬达；
- 默认从 circuit 层进入（帅司/枢密院），处理不了再 central 摘要；
- 不直接调兵；调兵仍走 `issue_military_order`/批红。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.incident import create_incident
from core.report_ledger import report_of
from core.transport import route_path

__all__ = [
    "military_report_delay_turns", "military_report_delay_info",
    "create_military_report",
]

CAPITAL_SEAT_ID = "京畿路|开封府"


def _seat_route_to_capital(seat_id: str) -> Dict[str, Any]:
    try:
        return route_path(CAPITAL_SEAT_ID, str(seat_id or "")) or {}
    except Exception:  # noqa: BLE001 — 路线不可读不阻断军报
        return {}


def military_report_delay_info(state, route: str = "", *,
                               seat_id: str = "",
                               border: bool = False,
                               urgent: bool = True,
                               road_blocked: bool = False) -> Dict[str, Any]:
    """军报延迟：优先消费交通层最短路（km/days）；否则回落档位；阻断 +1。"""
    path = _seat_route_to_capital(seat_id)
    km = path.get("km") if path.get("reachable") else None
    if km is not None:
        base = max(1, int(path.get("days") or 1))
        basis = "transport"
    else:
        base = 1 if border else 2
        basis = "fallback"
    if not urgent:
        base += 1
    if road_blocked:
        base += 1
    return {"delay_turns": base, "distance_km": km, "basis": basis,
            "road_blocked": bool(road_blocked),
            "route_hops": path.get("hops") if path.get("reachable") else None}


def military_report_delay_turns(state, route: str = "", *,
                                seat_id: str = "",
                                border: bool = False,
                                urgent: bool = True,
                                road_blocked: bool = False) -> int:
    return int(military_report_delay_info(
        state, route, seat_id=seat_id, border=border,
        urgent=urgent, road_blocked=road_blocked)["delay_turns"])


def create_military_report(
    state,
    *,
    parent_seat_id: str,
    kind: str = "border",
    locality: str = "",
    route: str = "",
    severity: float = 0.7,
    submitted_by: str = "帅司/边将",
    from_post: str = "帅司",
    border: bool = False,
    urgent: bool = True,
    body: str = "",
    delay_turns: Optional[int] = None,
    road_blocked: bool = False,
) -> Dict[str, Any]:
    seat = str(parent_seat_id or "").strip()
    route_name = str(route or seat.split("|")[0])
    info = military_report_delay_info(
        state, route_name, seat_id=seat, border=border,
        urgent=urgent, road_blocked=road_blocked)
    delay = int(delay_turns) if delay_turns is not None else int(info["delay_turns"])
    out = create_incident(
        state, kind=kind, locality=locality or seat.split("|")[-1],
        parent_seat_id=seat, route=route_name, severity=severity,
        level="circuit", submitted_by=submitted_by, from_post=from_post,
        channel="急递" if urgent else "通进银台司",
        channel_matter="军务机要" if urgent else "边防",
        body=body or f"{locality or seat}{kind}军报",
        delay_turns=delay, priority="urgent" if urgent else "normal")
    if out.get("ok"):
        inc = out["incident"]
        inc["military_report"] = True
        inc["arrive_turn"] = int(getattr(state, "turn", 0) or 0) + delay
        inc["distance_km"] = info["distance_km"]
        inc["delay_basis"] = info["basis"]
        inc["road_blocked"] = bool(road_blocked)
        inc["route_hops"] = info.get("route_hops")
        for rid in inc.get("raw_report_ids") or []:
            rep = report_of(state, rid)
            if isinstance(rep, dict):
                rep["distance_km"] = info["distance_km"]
                rep["delay_basis"] = info["basis"]
                rep["road_blocked"] = bool(road_blocked)
    return out

