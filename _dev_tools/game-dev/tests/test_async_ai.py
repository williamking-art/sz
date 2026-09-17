# -*- coding: utf-8 -*-
"""T6 异步化核心测试：core/async_ai.py（run_ai_call / run_settlement_ai / 线程纪律）
+ 结算拆分基件（settle_local / finish_turn / monthly_report_args）
+ 召对拆分（audience_dialogue_prepare / audience_dialogue_apply）。

线程纪律断言：
- 后台只做「AI 网络调用 + 纯函数校验」，不写 GameState（结果经 on_success 主线程落地）；
- 异常统一经 on_error 回到主线程回调（AIRuntimeError 弹错语义）。
"""
import os
import sys
import time

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)
sys.path.insert(0, os.path.join(_GAME_ROOT, "tests"))

from core.game_state import GameState  # noqa: E402
from core.errors import AIRuntimeError  # noqa: E402


class _FakeUI:
    """假主线程宿主：after(ms, fn) 真实延时后执行（模拟主线程轮询回调）。"""

    def __init__(self):
        self.root = self

    def after(self, delay_ms, fn):
        time.sleep(delay_ms / 1000.0)
        fn()


class _EchoAI:
    """假 AI：available + 契约方法即时返回（不联网）。"""

    available = True

    def __init__(self):
        self.calls = []

    def echo(self, x):
        self.calls.append(x)
        return {"ok": x, "echo": x}

    def boom(self):
        raise AIRuntimeError("AI 服务连接超时（限时 30s）")


# ============================================================
# run_ai_call：成功 / 失败 / 未知方法 / 无 UI
# ============================================================
def test_run_ai_call_success_main_thread_callback():
    """后台执行成功 → on_success 收到返回值，on_error 不被调用。"""
    from core.async_ai import run_ai_call
    ai = _EchoAI()
    got, errors = [], []

    def _ok(res):
        got.append(res)

    def _err(e):
        errors.append(e)

    fut = run_ai_call(ai, "echo", 42, on_success=_ok, on_error=_err, ui=_FakeUI())
    assert fut.done()
    assert got == [{"ok": 42, "echo": 42}]
    assert errors == []
    assert ai.calls == [42]


def test_run_ai_call_error_routes_to_on_error():
    """后台抛 AIRuntimeError → on_error 收到异常，on_success 不被调用。"""
    from core.async_ai import run_ai_call
    ai = _EchoAI()
    got, errors = [], []

    def _ok(res):
        got.append(res)

    def _err(e):
        errors.append(e)

    run_ai_call(ai, "boom", on_success=_ok, on_error=_err, ui=_FakeUI())
    assert got == []
    assert len(errors) == 1
    assert isinstance(errors[0], AIRuntimeError)
    assert "超时" in str(errors[0])


def test_run_ai_call_unknown_method():
    """未知方法名 → on_error 收到 TypeError（不炸 mainloop）。"""
    from core.async_ai import run_ai_call
    ai = _EchoAI()
    errors = []

    def _err(e):
        errors.append(e)

    run_ai_call(ai, "no_such_method", on_error=_err, ui=_FakeUI())
    assert len(errors) == 1
    assert isinstance(errors[0], TypeError)


def test_run_ai_call_ui_none_returns_future():
    """无 UI（测试/无 Tk 环境）：直接返回 future，结果可取。"""
    from core.async_ai import run_ai_call
    ai = _EchoAI()
    fut = run_ai_call(ai, "echo", "x", ui=None)
    assert fut.result() == {"ok": "x", "echo": "x"}


# ============================================================
# run_settlement_ai：后台 AI 推演族（不写 state）+ 拒绝式 economy
# ============================================================
class _SettleAI(_EchoAI):
    def __init__(self, economy=None):
        super().__init__()
        self._economy = economy

    def economy_decide(self, posture):
        if self._economy is None:
            return {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
                    "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无"}
        return dict(self._economy)

    def diplomacy_decide(self, posture, state=None):
        return {"attitude": "小", "sui_gong": "不变", "alliance": "不变"}

    def military_decide(self, posture, state=None):
        return {"power": "小", "army": "微", "training": "微", "morale": "微", "levy": "微"}

    def relief_decide(self, posture, state=None):
        return {"disaster_level": 1, "relief": "微", "refugee": "微"}


def test_run_settlement_ai_no_state_write():
    """后台推演族不写 GameState：结果经 on_success 返回，state 槽位保持未注入。"""
    from core.async_ai import run_settlement_ai
    s = GameState("史实")
    ai = _SettleAI()
    results, errors = [], []

    def _ok(r):
        results.append(r)

    def _err(e):
        errors.append(e)

    run_settlement_ai(ai, s.posture, s, woken=[], ui=_FakeUI(),
                      on_success=_ok, on_error=_err)
    assert errors == []
    assert len(results) == 1
    r = results[0]
    assert "_economy_ai" in r and r["_economy_ai"]["景气"] == "中"
    # 关键：后台期间 state 未被写入（主线程 on_success 才落地）
    assert not hasattr(s, "_economy_ai") or getattr(s, "_economy_ai", None) is None


def test_run_settlement_ai_woken_agents_inject_results():
    """按需唤醒：woken 列表里的领域契约结果并入返回字典（仍不写 state）。"""
    from core.async_ai import run_settlement_ai
    s = GameState("史实")
    ai = _SettleAI()
    results = []

    def _ok(r):
        results.append(r)

    run_settlement_ai(ai, s.posture, s, woken=["diplomacy", "military"], ui=_FakeUI(),
                      on_success=_ok, on_error=lambda e: pytest.fail(f"不应失败：{e}"))
    r = results[0]
    assert r["_diplomacy_ai"]["attitude"] == "小"
    assert r["_military_ai"]["army"] == "微"
    assert not hasattr(s, "_diplomacy_ai")


def test_run_settlement_ai_economy_refusal():
    """economy 推演失败（_error）→ 拒绝式：on_error 收到 AIRuntimeError，结算不进行。"""
    from core.async_ai import run_settlement_ai
    s = GameState("史实")
    ai = _SettleAI(economy={"_error": "AI_CONTRACT_FAILED"})
    results, errors = [], []

    def _ok(r):
        results.append(r)

    def _err(e):
        errors.append(e)

    run_settlement_ai(ai, s.posture, s, woken=[], ui=_FakeUI(),
                      on_success=_ok, on_error=_err)
    assert results == []
    assert len(errors) == 1
    assert isinstance(errors[0], AIRuntimeError)


def test_settle_local_and_finish_turn():
    """结算拆分基件：settle_local 跑完 12 步（回合推进），finish_turn 收尾不炸。"""
    from core.commands import settle_local, finish_turn
    s = GameState("史实")
    t0 = s.turn
    log = settle_local(s)
    assert s.turn == t0 + 1, "settle_local 应推进回合（委托 run_monthly_settlement）"
    assert isinstance(log, list) and log
    finish_turn(s)  # 终局判定 + 自动存档（正月/终局）——不抛即可
    assert s.game_over in (True, False)


def test_monthly_report_args_shape():
    """monthly_report_args 返回主线程快照四元组（year, month, era_name, posture）。"""
    from core.commands import monthly_report_args
    s = GameState("史实")
    args = monthly_report_args(s)
    assert len(args) == 4
    assert args[0] == s.year and args[1] == s.month
    assert isinstance(args[3], str) and args[3]


# ============================================================
# 召对拆分：prepare / apply / 同步包装器兼容
# ============================================================
def test_audience_dialogue_prepare_and_apply():
    """prepare 入史（朕言）+ 构建入参；apply 落定（回奏 + 意向），行为与拆分前一致。"""
    from core.commands import audience_dialogue_prepare, audience_dialogue_apply
    s = GameState("史实")
    kwargs, note = audience_dialogue_prepare(s, "蔡京", "卿近来如何？")
    assert note is None
    assert ("朕", "卿近来如何？") in s.dialogue_history
    assert kwargs["minister_name"] == "蔡京"
    assert kwargs["state"] is s
    assert isinstance(kwargs["history"], list) and ("朕", "卿近来如何？") in kwargs["history"]
    # apply：主线程落定
    reply = audience_dialogue_apply(s, "蔡京", {"reply": "臣谨奏，国用宜节。", "intent_hint": "中"})
    assert reply == "臣谨奏，国用宜节。"
    assert ("蔡京", "臣谨奏，国用宜节。") in s.dialogue_history
    assert s._last_intent_hint == "中"


def test_audience_dialogue_prepare_dead_minister():
    """已薨/罢黜之臣：prepare 返回 note 并写史册说明，不走 AI。"""
    from core.commands import audience_dialogue_prepare
    s = GameState("史实")
    s.mark_minister_status("蔡京", "dead")
    kwargs, note = audience_dialogue_prepare(s, "蔡京", "卿近来如何？")
    assert kwargs is None
    assert note and "不及奉诏" in note
    assert ("朕", "卿近来如何？") not in s.dialogue_history


def test_audience_dialogue_wrapper_sync_compat():
    """同步包装器（audience_dialogue）行为与拆分前一致：兼容假 dialogue 替身。"""
    from core.commands import audience_dialogue
    from tests.fake_ai_backend import FakeAIClient

    class _FakeDialogueAI(FakeAIClient):
        def __init__(self):
            super().__init__()
            self.available = True

        def dialogue(self, minister_name, faction, stance, traits, role, era, history,
                     player_input, state_summary, state=None):
            return {"reply": "臣谨奏。", "mood": "中", "intent_hint": "小"}

    s = GameState("史实")
    reply = audience_dialogue(s, "蔡京", "卿近来如何？", _FakeDialogueAI())
    assert reply == "臣谨奏。"
    assert ("朕", "卿近来如何？") in s.dialogue_history
    assert ("蔡京", "臣谨奏。") in s.dialogue_history
