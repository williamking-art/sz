# -*- coding: utf-8 -*-
"""事故单：MemoryGraph 县官 → 州府代行 → 路省 → 中央摘要。"""
from core import commands
from core.county_registry import assign_county_official
from core.incident import create_incident, incidents_of, settle_incidents
from memory.memory_graph import get_memory_graph

SEAT = "京畿路|开封府"
ROUTE = "京畿路"


def _state():
    return commands.new_game()


def _incident(s, *, locality="X县", severity=0.1, kind="flood"):
    out = create_incident(
        s, kind=kind, locality=locality, parent_seat_id=SEAT,
        route=ROUTE, severity=severity)
    assert out["ok"] is True
    return out["incident"]


def test_incident_stored_under_parent_seat_not_top_level():
    s = _state()
    inc = _incident(s)
    assert inc["incident_id"] in incidents_of(s, SEAT)
    assert not hasattr(s, "incidents")


def test_county_official_from_memory_graph_handles():
    s = _state()
    s.slot = 9876
    mem = get_memory_graph(9876)
    mem.add_entity("测试知县", "minister", "测试知县", {}, turn=0)
    assign_county_official(
        mem, "测试知县", "测试县_9876", post="知县",
        route=ROUTE, parent_seat_id=SEAT, turn=0)
    mem.save(9876)
    inc = _incident(s, locality="测试县_9876", severity=0.1)
    settle_incidents(s, turn=1)
    assert inc["status"] == "resolved"
    assert inc["handled_by"] == "测试知县"
    assert inc["acting_official"] == ""


def test_no_county_official_uses_acting_prefecture():
    s = _state()
    inc = _incident(s, locality="Y县", severity=0.1)
    settle_incidents(s, turn=1)
    assert inc["status"] == "resolved"
    assert inc["handled_by"] != ""
    assert inc["acting_official"] != ""


def test_insufficient_capacity_escalates():
    s = _state()
    inc = _incident(s, severity=0.99)
    settle_incidents(s, turn=1)
    assert inc["status"] in ("escalated", "awaiting_decision")
    assert inc["level"] in ("prefecture", "circuit", "central")
    assert inc["escalation_path"]


def test_settle_is_idempotent_same_turn():
    s = _state()
    inc = _incident(s, severity=0.1)
    settle_incidents(s, turn=1)
    path = list(inc["escalation_path"])
    settle_incidents(s, turn=1)
    assert inc["escalation_path"] == path


def test_central_ends_awaiting_decision_with_recommendation():
    s = _state()
    inc = _incident(s, severity=1.0)
    for turn in (1, 2, 3, 4, 5):
        settle_incidents(s, turn=turn)
    assert inc["level"] == "central"
    assert inc["status"] == "awaiting_decision"
    assert inc["recommendation"]
    assert inc["due_turn"] is None
    memos = [m for m in s.memorials if m.get("incident_id") == inc["incident_id"]]
    assert len(memos) == 1
    assert memos[0]["memorial_id"].startswith("mem_inc_")
    assert memos[0]["recommendation"] == inc["recommendation"]
    assert memos[0]["priority"] == "urgent"


def test_incident_memorial_is_not_duplicated():
    s = _state()
    inc = _incident(s, severity=1.0)
    for turn in (1, 2, 3, 4, 5):
        settle_incidents(s, turn=turn)
    n = len([m for m in s.memorials if m.get("incident_id") == inc["incident_id"]])
    settle_incidents(s, turn=5)
    assert len([m for m in s.memorials
                if m.get("incident_id") == inc["incident_id"]]) == n == 1

