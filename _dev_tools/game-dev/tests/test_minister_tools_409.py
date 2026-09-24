# -*- coding: utf-8 -*-
"""批 5 · 大臣工具化最小闭环 + 409 未决呈请守卫回归。

断言：
  1) `enqueue_finance_proposal` 落草案（status=pending）；
  2) 批红 `finance_proposal` 走 state_applier 落地；
  3) 驳回不落地；
  4) 颁诏前有未决呈请 → 409 拦截（issue_decree / issue_free_decree）；
  5) 处置完未决后颁诏放行。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.commands import (  # noqa: E402
    approve_ai_action, reject_ai_action, enqueue_finance_proposal,
)
from core.commands_decree import issue_decree, issue_free_decree  # noqa: E402


def test_enqueue_finance_proposal_pending():
    """财政草案入队，status=pending。"""
    s = GameState("史实")
    aid = enqueue_finance_proposal(
        s, title="调整宗室禄米", summary="现 66 万贯/月 → 定为 50 万贯/月",
        changes=[{"path": "imperial_treasury", "op": "add", "value": -160000,
                   "reason": "裁减宗室禄米"}],
        proposer="户部")
    assert aid
    items = s.get_ai_pending("pending")
    assert len(items) == 1
    assert items[0]["kind"] == "finance_proposal"
    assert items[0]["title"] == "调整宗室禄米"


def test_approve_finance_proposal_applies():
    """批红财政草案：changes 走 state_applier 落地（成对划转守恒）。"""
    s = GameState("史实")
    t0 = s.treasury
    p0 = s.prestige
    # 成对划转：国库 -10 万 → 民间（士绅 wealth +10 万），money 组 ΣΔ=0
    aid = enqueue_finance_proposal(
        s, title="拨帑赈济", summary="拨 10 万贯赈济（国库→士绅）",
        changes=[
            {"path": "treasury", "op": "add", "value": -100000,
             "reason": "赈济支出"},
            {"path": "prefectures.京畿路.pops.士绅.wealth", "op": "add",
             "value": 100000, "reason": "赈济入民间"},
        ],
        proposer="户部")
    msg = approve_ai_action(s, aid)
    assert "批红" in msg and "已落地" in msg
    assert s.treasury == t0 - 100000
    assert s.pop_ai_pending(aid)["status"] == "approved"


def test_reject_finance_proposal_no_effect():
    """驳回财政草案：状态不变。"""
    s = GameState("史实")
    t0 = s.treasury
    aid = enqueue_finance_proposal(
        s, title="加税", summary="商税加征",
        changes=[
            {"path": "treasury", "op": "add", "value": 500000, "reason": "加税"},
            {"path": "prefectures.京畿路.pops.农.wealth", "op": "add",
             "value": -500000, "reason": "民间缴税"},
        ],
        proposer="户部")
    msg = reject_ai_action(s, aid)
    assert "驳回" in msg
    assert s.treasury == t0, "驳回不得落地"
    assert s.pop_ai_pending(aid)["status"] == "rejected"


def test_issue_decree_409_when_pending():
    """颁诏前有未决呈请 → 409 拦截。"""
    s = GameState("史实")
    enqueue_finance_proposal(
        s, title="未决条陈", summary="待批",
        changes=[{"path": "treasury", "op": "add", "value": 0, "reason": "x"}],
        proposer="户部")
    msg = issue_decree(s, {"title": "颁诏", "category": "财政"})
    assert "409" in msg and "未决" in msg
    assert "待朱批" in msg or "处置" in msg


def test_issue_free_decree_409_when_pending():
    """自由拟旨同款 409 守卫。"""
    s = GameState("史实")
    enqueue_finance_proposal(
        s, title="未决条陈", summary="待批",
        changes=[{"path": "treasury", "op": "add", "value": 0, "reason": "x"}],
        proposer="户部")
    msg = issue_free_decree(s, {"title": "test", "body": "x"}, "某臣")
    assert "409" in msg


def test_issue_decree_ok_after_clear():
    """处置完未决后颁诏放行。"""
    s = GameState("史实")
    aid = enqueue_finance_proposal(
        s, title="已决", summary="批红",
        changes=[{"path": "prestige", "op": "add", "value": 0, "reason": "x"}],
        proposer="户部")
    approve_ai_action(s, aid)
    msg = issue_decree(s, {"title": "颁诏", "category": "财政"})
    assert "409" not in msg, f"处置后不应 409：{msg}"


def test_pending_contracts_guard_count():
    """409 文案含未决件数。"""
    s = GameState("史实")
    for i in range(3):
        enqueue_finance_proposal(
            s, title=f"条陈{i}", summary="x",
            changes=[{"path": "treasury", "op": "add", "value": 0, "reason": "x"}],
            proposer="户部")
    msg = issue_decree(s, {"title": "颁诏", "category": "财政"})
    assert "3" in msg, f"应含件数：{msg}"
