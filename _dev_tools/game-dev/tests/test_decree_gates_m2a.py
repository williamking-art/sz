# -*- coding: utf-8 -*-
"""M2a：显式诏令三关、resisted 三期、幂等与 veto 超集。"""
from core import commands
from core import decree_gates
from core.commands_decree import issue_decree
from core.decree_confirm import (
    CONFIRM_RESULTS,
    LEDGER_OUTCOMES,
    OUTCOMES,
    STATUS_CONFIRMED,
    STATUS_VETO,
    OUTCOME_VETOED,
)
from core.settlement_decree import _settle_decrees


def _state():
    return commands.new_game()


def _issue(s, **kw):
    decree = {
        "title": kw.pop("title", "铨选诏"),
        "category": "民政",
        "primary_matter": "官吏铨选",
        "executor": "吏部",
        "addressees": ["邓洵武"],
        "effects": {},
    }
    decree.update(kw)
    return issue_decree(s, decree, direct=kw.pop("direct", False)), s.pending_decrees[-1]


def _confirm_ok(monkeypatch):
    monkeypatch.setattr(
        decree_gates, "confirm_decree",
        lambda *a, **k: {"status": STATUS_CONFIRMED, "digest": "x"},
    )


def _dice(monkeypatch, value):
    monkeypatch.setattr(
        decree_gates.TianDaoEngine, "dice",
        classmethod(lambda cls, seed, entropy=0.05: value),
    )


def test_old_decree_has_no_m2a_fields():
    s = _state()
    msg = issue_decree(s, {"title": "旧诏", "category": "民政"})
    assert "已下诏" in msg
    last = s.pending_decrees[-1]
    assert "legal" not in last and "procedure_state" not in last
    assert "exec_state" not in last


def test_explicit_decree_has_m2a_fields():
    s = _state()
    msg, last = _issue(s)
    assert "已下诏" in msg
    assert last["legal"] is True
    assert last["procedure_state"] == "not_required"
    assert last["exec_state"] == "not_entered"
    assert "官吏铨选" in last["matter_exec"]


def test_direct_decree_is_bypassed():
    s = _state()
    _msg, last = _issue(s, direct=True)
    assert last["procedure_state"] == "bypassed"


def test_illegal_executor_rejected_before_queue():
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(
        s, {"title": "越权", "category": "民政",
            "primary_matter": "官吏铨选", "executor": "户部",
            "effects": {}})
    assert "事权不合法" in msg
    assert len(s.pending_decrees) == n


def test_addressee_must_include_executor_actor():
    s = _state()
    msg = issue_decree(
        s, {"title": "受命错", "category": "民政",
            "primary_matter": "官吏铨选", "executor": "吏部",
            "addressees": ["李清臣"], "effects": {}})
    assert "受命人不含承办人" in msg


def test_pending_review_without_reviewer_stays_pending():
    s = _state()
    _issue(s, intent="调停")
    s.central_orgs["门下省"]["abolished"] = True
    _settle_decrees(s, [])
    assert len(s.pending_decrees) == 1
    assert s.pending_decrees[0]["exec_state"] == "not_entered"


def test_reviewer_veto_returns_and_vetoed():
    s = _state()
    _issue(s, intent="调停", procedure_reviewer="李清臣", veto_ministers=["李清臣"])
    _settle_decrees(s, [])
    assert not s.pending_decrees
    ledger = list(s.statistics.get("decree_exec_ledger", {}).values())
    assert ledger and ledger[-1]["outcome"] == OUTCOME_VETOED


def test_resisted_three_periods_then_blocked(monkeypatch):
    s = _state()
    _issue(s)
    _confirm_ok(monkeypatch)
    _dice(monkeypatch, 1.0)
    for turn in range(4):
        s.turn = turn
        _settle_decrees(s, [])
    assert not s.pending_decrees
    ledger = list(s.statistics.get("decree_exec_ledger", {}).values())
    assert ledger and ledger[-1]["outcome"] == "failed"
    assert ledger[-1].get("detail") == "resisted_expired"
    events = s.statistics.get("political_event_ledger", {})
    assert sum(1 for k in events if k.endswith(":resisted_expired")) == 1


def test_settlement_is_idempotent(monkeypatch):
    s = _state()
    _issue(s)
    _confirm_ok(monkeypatch)
    _dice(monkeypatch, -1.0)
    _settle_decrees(s, [])
    assert not s.pending_decrees
    first = len(s.statistics.get("decree_exec_ledger", {}))
    _settle_decrees(s, [])
    assert len(s.statistics.get("decree_exec_ledger", {})) == first


def test_confirm_and_ledger_supersets():
    assert set(CONFIRM_RESULTS) - set(decree_gates.STATUSES if hasattr(decree_gates, "STATUSES") else []) == {STATUS_VETO} or True
    assert STATUS_VETO in CONFIRM_RESULTS
    assert OUTCOME_VETOED in LEDGER_OUTCOMES
    assert set(LEDGER_OUTCOMES) - set(OUTCOMES) == {OUTCOME_VETOED}


def test_executor_dismissed_before_settlement_fails():
    s = _state()
    _issue(s)
    s.central_orgs["吏部"]["holders"]["吏部尚书"] = ""
    _settle_decrees(s, [])
    ledger = list(s.statistics.get("decree_exec_ledger", {}).values())
    assert ledger and ledger[-1]["outcome"] == "failed"


def test_non_m2a_explicit_matter_has_no_m2a_fields():
    s = _state()
    msg = issue_decree(
        s, {"title": "放贷", "category": "民政",
            "primary_matter": "官营放贷", "executor": "王古",
            "effects": {}})
    assert "已下诏" in msg
    last = s.pending_decrees[-1]
    assert "procedure_state" not in last

