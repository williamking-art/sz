# -*- coding: utf-8 -*-
"""M1b-1：显式事权校验（默认中性）。

只有显式携带 `primary_matter` / `co_matters` 的新诏令才校验；
旧调用（无这两个字段）保持原行为并标 `legacy_unchecked=True`。
"""
from core import commands
from core.commands_decree import issue_decree


def _state():
    return commands.new_game()


def _d(**kw):
    base = {"title": "测试诏", "category": "民政"}
    base.update(kw)
    return base


def test_legal_matter_is_accepted():
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(s, _d(primary_matter="官吏铨选", executor={"org": "吏部"}))
    assert "已下诏" in msg
    assert len(s.pending_decrees) == n + 1
    last = s.pending_decrees[-1]
    assert last["legacy_unchecked"] is False
    assert last["primary_matter"] == "官吏铨选"
    assert "吏部" in last["authority_label"]


def test_wrong_executor_is_rejected():
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(s, _d(primary_matter="官吏铨选", executor={"org": "户部"}))
    assert "事权不合法" in msg
    assert "官吏铨选" in msg
    assert len(s.pending_decrees) == n


def test_co_matter_not_held_is_rejected():
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(
        s,
        _d(primary_matter="官吏铨选", co_matters=["赋税"], executor={"org": "吏部"}),
    )
    assert "事权不合法" in msg
    assert "赋税" in msg
    assert len(s.pending_decrees) == n


def test_old_call_is_legacy_unchecked():
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(s, _d())
    assert "已下诏" in msg
    assert len(s.pending_decrees) == n + 1
    last = s.pending_decrees[-1]
    assert last["legacy_unchecked"] is True
    assert last["primary_matter"] is None
    assert last["co_matters"] == []


def test_direct_decree_with_illegal_matter_is_rejected():
    s = _state()
    before_used = s.direct_decree_used
    n = len(s.pending_decrees)
    msg = issue_decree(
        s, _d(primary_matter="官吏铨选", executor={"org": "户部"}), direct=True
    )
    assert "事权不合法" in msg
    assert s.direct_decree_used == before_used
    assert len(s.pending_decrees) == n


def test_co_matters_without_primary_is_rejected():
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(s, _d(co_matters=["赋税"], executor={"org": "户部"}))
    assert "缺少 primary_matter" in msg
    assert len(s.pending_decrees) == n


def test_unknown_executor_is_rejected():
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(s, _d(primary_matter="官吏铨选", executor={"org": "不存在"}))
    assert "事权不合法" in msg
    assert len(s.pending_decrees) == n


def test_executor_alone_does_not_activate_check():
    """旧调用可能带 executor 作其他用途；无 primary/co 时仍走 legacy。"""
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(s, _d(executor={"org": "户部"}))
    assert "已下诏" in msg
    assert len(s.pending_decrees) == n + 1
    assert s.pending_decrees[-1]["legacy_unchecked"] is True


def test_high_prestige_does_not_bypass_authority():
    s = _state()
    s.prestige = 100
    n = len(s.pending_decrees)
    msg = issue_decree(s, _d(primary_matter="官吏铨选", executor={"org": "户部"}))
    assert "事权不合法" in msg
    assert len(s.pending_decrees) == n


def test_legal_direct_with_co_matter_accepted():
    s = _state()
    msg = issue_decree(
        s,
        _d(primary_matter="官吏铨选", co_matters=["官员考课"], executor="吏部"),
        direct=True,
    )
    assert "御笔直发" in msg
    last = s.pending_decrees[-1]
    assert last["is_direct"] is True
    assert last["legacy_unchecked"] is False
    assert last["co_matters"] == ["官员考课"]

