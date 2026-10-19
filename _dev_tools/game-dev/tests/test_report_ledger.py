# -*- coding: utf-8 -*-
"""奏报原件台账：全量留档、压案/拖延、御前摘要引用原件。"""
from core import commands
from core.incident import create_incident, settle_incidents
from core.report_ledger import (
    delay_report,
    raw_reports_of,
    record_raw_report,
    report_of,
    report_status_summary,
    suppress_report,
)

SEAT = "京畿路|开封府"
ROUTE = "京畿路"


def _state():
    return commands.new_game()


def test_record_raw_report_idempotent_and_preserved():
    s = _state()
    r1 = record_raw_report(
        s, incident_id="inc_x", parent_seat_id=SEAT,
        submitted_by="X县知县", from_post="知县",
        channel="都进奏院", body="X县大水，民田被淹", turn=3)
    r2 = record_raw_report(
        s, incident_id="inc_x", parent_seat_id=SEAT,
        submitted_by="X县知县", from_post="知县",
        channel="都进奏院", body="X县大水，民田被淹", turn=3)
    assert r1 == r2
    reports = raw_reports_of(s, SEAT)
    assert len(reports) == 1
    assert reports[r1]["body"] == "X县大水，民田被淹"
    assert reports[r1]["status"] == "raw"


def test_suppress_report_keeps_original():
    s = _state()
    rid = record_raw_report(
        s, incident_id="inc_y", parent_seat_id=SEAT,
        submitted_by="X县知县", body="盗贼聚众", turn=1)
    assert suppress_report(s, rid, suppressed_by="中书", faction="旧党",
                           reason="压案") is True
    rep = report_of(s, rid)
    assert rep["status"] == "suppressed"
    assert rep["suppressed_by_faction"] is True
    assert rep["body"] == "盗贼聚众"


def test_delay_report_keeps_original():
    s = _state()
    rid = record_raw_report(
        s, incident_id="inc_z", parent_seat_id=SEAT,
        submitted_by="州府", body="河堤决口", turn=1)
    assert delay_report(s, rid, delay_until=5, suppressed_by="转运司",
                        reason="待覆核") is True
    rep = report_of(s, rid)
    assert rep["status"] == "delayed"
    assert rep["delay_until"] == 5
    assert rep["body"] == "河堤决口"


def test_incident_create_links_raw_report():
    s = _state()
    out = create_incident(
        s, kind="flood", locality="X县", parent_seat_id=SEAT,
        route=ROUTE, severity=0.3, submitted_by="X县知县",
        from_post="知县", channel="都进奏院", body="X县大水")
    inc = out["incident"]
    assert inc["raw_report_ids"]
    rep = report_of(s, inc["raw_report_ids"][0])
    assert rep["incident_id"] == inc["incident_id"]
    assert rep["body"] == "X县大水"
    assert rep["submitted_by"] == "X县知县"


def test_central_marks_reports_handled_and_memorial_links_them():
    s = _state()
    inc = create_incident(
        s, kind="flood", locality="X县", parent_seat_id=SEAT,
        route=ROUTE, severity=1.0, body="X县大水，请拨帑")["incident"]
    for turn in (1, 2, 3, 4, 5):
        settle_incidents(s, turn=turn)
    assert inc["status"] == "awaiting_decision"
    reps = [report_of(s, rid) for rid in inc["raw_report_ids"]]
    assert reps and all(r["status"] == "handled" for r in reps)
    memo = [m for m in s.memorials if m.get("incident_id") == inc["incident_id"]][0]
    assert set(memo["raw_report_ids"]) == set(inc["raw_report_ids"])


def test_report_status_summary_counts():
    s = _state()
    rid1 = record_raw_report(s, incident_id="a", parent_seat_id=SEAT, body="甲")
    rid2 = record_raw_report(s, incident_id="b", parent_seat_id=SEAT, body="乙")
    suppress_report(s, rid2, reason="压案")
    summ = report_status_summary(s)
    assert summ.get("raw", 0) >= 1
    assert summ.get("suppressed", 0) >= 1

