# -*- coding: utf-8 -*-
"""军报/急递（2026-10-19，奏折前）。

- 军报先登记原件，按驿传/急递延迟到达；不瞬达；
- 默认从 circuit 层进入（帅司/枢密院），处理不了再 central 摘要；
- 不直接调兵；调兵仍走 `issue_military_order`/批红。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.incident import create_incident

__all__ = ["military_report_delay_turns", "create_military_report"]


def military_report_delay_turns(state, route: str = "", *,
                                border: bool = False,
                                urgent: bool = True) -> int:
    """确定性延迟：边报 1 回合；腹里急报 2 回合；常规军报 3 回合。"""
    if border:
        return 1
    return 2 if urgent else 3


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
) -> Dict[str, Any]:
    seat = str(parent_seat_id or "").strip()
    route_name = str(route or seat.split("|")[0])
    delay = (int(delay_turns) if delay_turns is not None
             else military_report_delay_turns(state, route_name, border=border, urgent=urgent))
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
    return out

