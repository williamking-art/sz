# -*- coding: utf-8 -*-
"""P2b：matter_effects 分区、逐事权幂等、partially_executed 聚合。"""
from core import commands, decree_gates, settlement
from core.commands_decree import issue_decree
from core.decree_confirm import STATUS_CONFIRMED
from core.settlement_decree import _settle_decrees


def _state():
    s = commands.new_game()
    # 让同一 actor 同时持有吏部/户部主官，构造单 executor 双事权
    s.central_orgs["户部"]["holders"]["户部尚书"] = "邓洵武"
    return s


def _issue(s, effects=None):
    decree = {
        "title": "双事权", "category": "民政",
        "primary_matter": "官吏铨选", "co_matters": ["度支调度"],
        "executor": "邓洵武", "addressees": ["邓洵武"],
        "effects": {},
        "matter_effects": effects or {
            "官吏铨选": {"audit_route": "两浙路"},
            "度支调度": {"treasury": 1000},
        },
    }
    msg = issue_decree(s, decree)
    return msg, s.pending_decrees[-1]


def _confirm_ok(monkeypatch):
    monkeypatch.setattr(
        decree_gates, "confirm_decree",
        lambda *a, **k: {"status": STATUS_CONFIRMED, "digest": "x"},
    )


def test_matter_effects_keys_must_match():
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(s, {
        "title": "坏分区", "category": "民政",
        "primary_matter": "官吏铨选", "co_matters": ["度支调度"],
        "executor": "邓洵武", "effects": {},
        "matter_effects": {"官吏铨选": {"audit_route": "两浙路"}},
    })
    assert "matter_effects 键集合" in msg
    assert len(s.pending_decrees) == n


def test_partial_then_complete_and_no_repeat(monkeypatch):
    s = _state()
    _msg, last = _issue(s)
    _confirm_ok(monkeypatch)
    assert last["matter_effects"]

    calls = []
    real = settlement._apply_decree_effect

    def _spy(state, decree, log):
        calls.append(decree.get("title"))
        return real(state, decree, log)

    monkeypatch.setattr(settlement, "_apply_decree_effect", _spy)

    seq = {"n": 0}

    def _dice(cls, seed, entropy=0.05):
        seq["n"] += 1
        return -1.0 if seq["n"] % 2 == 1 else 1.0

    monkeypatch.setattr(decree_gates.TianDaoEngine, "dice", classmethod(_dice))

    _settle_decrees(s, [])
    assert s.pending_decrees
    assert s.pending_decrees[0]["exec_state"] == "partially_executed"
    assert s.pending_decrees[0]["matter_exec"]["官吏铨选"]["status"] == "executed"
    assert s.pending_decrees[0]["matter_exec"]["度支调度"]["status"] == "resisted"

    s.turn = 1
    monkeypatch.setattr(
        decree_gates.TianDaoEngine, "dice",
        classmethod(lambda cls, seed, entropy=0.05: -1.0),
    )
    _settle_decrees(s, [])
    assert not s.pending_decrees
    assert len(calls) == 2, calls  # 已执行事权不重复施效
    ledger = list(s.statistics.get("decree_exec_ledger", {}).values())
    assert ledger and ledger[-1]["outcome"] == "executed"

