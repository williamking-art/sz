# -*- coding: utf-8 -*-
"""军报/急递：延迟到达、circuit 入口、原件字段。"""
from core import commands
from core.incident import settle_incidents
from core.military_report import create_military_report, military_report_delay_turns
from core.report_ledger import report_of

SEAT = "京畿路|开封府"
ROUTE = "京畿路"


def _state():
    return commands.new_game()


def test_military_report_delay_turns():
    s = _state()
    assert military_report_delay_turns(s, ROUTE, border=True) == 1
    assert military_report_delay_turns(s, ROUTE, border=False, urgent=True) == 2
    assert military_report_delay_turns(s, ROUTE, border=False, urgent=False) == 3


def test_military_report_waits_for_arrival():
    s = _state()
    s.turn = 3
    out = create_military_report(
        s, parent_seat_id=SEAT, kind="border", locality="边寨",
        route=ROUTE, severity=0.7, border=True, body="敌骑犯边")
    assert out["ok"] is True
    inc = out["incident"]
    assert inc["level"] == "circuit"
    assert inc["priority"] == "urgent"
    assert inc["delay_turns"] == 1
    assert inc["arrive_turn"] == 4
    assert inc["due_turn"] == 5
    rid = inc["raw_report_ids"][0]
    rep = report_of(s, rid)
    assert rep["channel"] == "急递"
    assert rep["channel_matter"] == "军务机要"
    assert rep["priority"] == "urgent"
    assert rep["delay_turns"] == 1
    assert rep["arrive_turn"] == 4
    settle_incidents(s, turn=4)
    assert inc["status"] == "reported"
    assert inc["handled_by"] == ""
    settle_incidents(s, turn=5)
    assert inc["handled_by"] != ""


def test_military_report_no_direct_troop_change():
    s = _state()
    before = [(u.name, u.troops) for u in s.army_units]
    create_military_report(
        s, parent_seat_id=SEAT, kind="border", locality="边寨",
        route=ROUTE, severity=0.9, border=True, body="请调兵")
    after = [(u.name, u.troops) for u in s.army_units]
    assert before == after

