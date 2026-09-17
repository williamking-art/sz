# -*- coding: utf-8 -*-
"""审查修复回归：钱守恒 / 家产来源 / 一条鞭 / AI 待批队列 / 异步无嵌套。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "game"))


def _state():
    from core.game_state import GameState
    return GameState("史实")


def test_transfer_money_pair():
    s = _state()
    road = next(iter(s.prefectures))
    t0 = s.treasury
    w0 = s.prefectures[road]["pops"]["官僚"]["wealth"]
    moved = s.transfer_money("treasury", f"pop:{road}:官僚", 10_000)
    assert moved == 10_000
    assert s.treasury == t0 - 10_000
    assert s.prefectures[road]["pops"]["官僚"]["wealth"] == w0 + 10_000


def test_change_treasury_no_underflow():
    s = _state()
    s.treasury = 100
    s.change_treasury(-500)
    assert s.treasury == 0


def test_estate_growth_drains_bureaucrat():
    from core.estate_mechanic import settle_minister_estate
    s = _state()
    s._economy_ai = {"景气": "中"}
    pool0 = sum(p["pops"]["官僚"]["wealth"] for p in s.prefectures.values())
    e0 = sum(e["wealth"] for e in s.minister_estate.values())
    settle_minister_estate(s, [])
    pool1 = sum(p["pops"]["官僚"]["wealth"] for p in s.prefectures.values())
    e1 = sum(e["wealth"] for e in s.minister_estate.values())
    # 官僚池减少 ≈ 家产净增（奢侈/窖藏另计，池必不增）
    assert pool1 <= pool0
    assert e1 != e0 or pool1 == pool0  # 有变化时必有来源


def test_single_whip_no_mint():
    from core.settlement_steps import _settle_land_local
    s = _state()
    s.single_whip = True
    money0 = s.treasury + sum(
        p["pops"][k]["wealth"] for p in s.prefectures.values()
        for k in ("农", "士绅"))
    _settle_land_local(s, [])
    money1 = s.treasury + sum(
        p["pops"][k]["wealth"] for p in s.prefectures.values()
        for k in ("农", "士绅"))
    # 折银只做民间→国库划转，钱组合计不增（允许欠税科目记账造成的微小差）
    assert money1 <= money0 + 1


def test_ai_pending_queue_strict():
    from ai.client_utils import _tool_dispatch
    s = _state()
    calls = [{
        "id": "c1",
        "function": {
            "name": "secret_order",
            "arguments": '{"title":"试密","summary":"测","longterm":false}',
        },
    }]
    _tool_dispatch(s, calls, minister_name="测试臣")
    assert s.get_ai_pending("pending"), "密令应入待批队列"
    assert not s.pending_secret_decrees, "批红前不得写入密令队列"
    from core.commands import approve_ai_action, reject_ai_action
    aid = s.get_ai_pending("pending")[0]["id"]
    msg = approve_ai_action(s, aid)
    assert "批红" in msg
    assert s.pending_secret_decrees
    assert not s.get_ai_pending("pending")


def test_military_increase_rejected_without_money():
    from core.commands import approve_ai_action
    s = _state()
    s.treasury = 0
    aid = s.enqueue_ai_action(
        "military_dispatch", "禁军·增募", "测",
        {"army": "禁军", "action": "增募", "scale": 3}, proposer="x")
    msg = approve_ai_action(s, aid)
    assert "驳回" in msg
    assert s.pop_ai_pending(aid)["status"] == "rejected"


def test_async_settlement_no_nested_submit():
    """run_settlement_ai 的 worker 不得再 submit 到同一 _EXECUTOR（防死锁）。"""
    import inspect
    import core.async_ai as m
    src = inspect.getsource(m.run_settlement_ai)
    assert "_EXECUTOR.submit(_call_guarded" not in src
    assert "as_completed" not in src
