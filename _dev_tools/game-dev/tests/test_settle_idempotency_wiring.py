# -*- coding: utf-8 -*-
"""幂等接线（HTTP / 两段式 / 收尾）的定向回归。

补的是「守卫已经接进真实调用链」这一层：
- `advance_two_phase` 入口判重：落后 ⇒ 重放（不触发事件、不 spawn daemon、不改状态）、超前 ⇒ 抛 `StaleAdvanceError`；
- `/api/advance`：收到 `expect_turn` 并透传；`StaleAdvanceError` 映射 409 + `STALE_TURN`；
- `LocalBackend.settle_local`：重放（回合未推进）时**跳过 `finish_turn`**（否则同回合重复终局判定/自动存档）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.commands import StaleAdvanceError, advance_two_phase  # noqa: E402


def _state(turn=2, logs=(("L0",), ("L1",))):
    return SimpleNamespace(turn=turn, settlement_log=[list(x) for x in logs],
                           rich_ready=False, rich_report="", rich_civilian="",
                           settle_error="", _settle_in_progress=False)


# ---------------------------------------------------------------- 两段式入口
def test_advance_two_phase_replay_does_not_trigger_or_spawn():
    st = _state(turn=2)
    # 3 元组契约（与 backend/client.py:196 及 test_two_phase_advance.py 一致；
    # backend 层负责补 state 组成统一的 (events, log, report, state) 四元组）
    events, log, report = advance_two_phase(st, None, expect_turn=0)
    assert (events, report) == ([], "")
    assert log == ["L0"], "重放必须返回该回合历史日志"
    assert st.turn == 2, "重放不得推进回合"
    assert st._settle_in_progress is False, "重放不得进入结算窗口（=不 spawn daemon）"
    assert st.rich_ready is False, "重放不得改动富化链字段"


def test_advance_two_phase_replay_before_ai_precheck():
    """落后重放**不需要 AI**：守卫在 AI 预检之前（重试不该因 AI 掉线而失败）。"""
    st = _state(turn=2)
    events, log, _ = advance_two_phase(st, None, expect_turn=1)   # ai_client=None
    assert log == ["L1"] and events == []


def test_advance_two_phase_ahead_raises_stale():
    st = _state(turn=2)
    with pytest.raises(StaleAdvanceError) as ei:
        advance_two_phase(st, None, expect_turn=9)
    assert "超前" in str(ei.value)
    assert st.turn == 2, "拒绝路径不得改状态"


def test_advance_two_phase_missing_history_returns_empty():
    st = _state(turn=5, logs=())
    events, log, _report = advance_two_phase(st, None, expect_turn=0)
    assert events == [] and log == []
    assert st.turn == 5


def test_advance_two_phase_equal_turn_still_requires_ai():
    """`expect_turn == turn` 走正常流程 ⇒ 仍要过 AI 预检（不得因新参数放松拒绝式）。"""
    from core.commands import AIRuntimeError

    st = _state(turn=2)
    with pytest.raises(AIRuntimeError):
        advance_two_phase(st, None, expect_turn=2)


# ---------------------------------------------------------------- HTTP 层
def test_api_advance_passes_expect_turn(monkeypatch):
    import backend.server as S

    seen = {}

    class _B:
        def advance(self, state, ai, expect_turn=None):
            seen["expect_turn"] = expect_turn
            return [], ["x"], "", SimpleNamespace(turn=3)

    monkeypatch.setattr(S, "_require_auth", lambda req: None)
    monkeypatch.setattr(S, "_require_settle_idle", lambda: None)
    monkeypatch.setattr(S, "_require_state", lambda: SimpleNamespace(turn=3))
    monkeypatch.setattr(S, "_get_ai", lambda: None)
    monkeypatch.setattr(S, "_backend", _B())
    monkeypatch.setattr(S, "_state_to_dict", lambda s: {})

    r = S.api_advance(request=object(), req=S.AdvanceReq(expect_turn=7))
    assert seen["expect_turn"] == 7
    assert r["log"] == ["x"]


def test_api_advance_without_body_keeps_legacy_behavior(monkeypatch):
    import backend.server as S

    seen = {}

    class _B:
        def advance(self, state, ai, expect_turn=None):
            seen["expect_turn"] = expect_turn
            return [], [], "", SimpleNamespace(turn=1)

    monkeypatch.setattr(S, "_require_auth", lambda req: None)
    monkeypatch.setattr(S, "_require_settle_idle", lambda: None)
    monkeypatch.setattr(S, "_require_state", lambda: SimpleNamespace(turn=0))
    monkeypatch.setattr(S, "_get_ai", lambda: None)
    monkeypatch.setattr(S, "_backend", _B())
    monkeypatch.setattr(S, "_state_to_dict", lambda s: {})

    S.api_advance(request=object(), req=None)
    assert seen["expect_turn"] is None


def test_api_advance_maps_stale_to_409(monkeypatch):
    from fastapi import HTTPException

    import backend.server as S

    class _B:
        def advance(self, state, ai, expect_turn=None):
            raise StaleAdvanceError("结算请求超前：expect_turn=9")

    monkeypatch.setattr(S, "_require_auth", lambda req: None)
    monkeypatch.setattr(S, "_require_settle_idle", lambda: None)
    monkeypatch.setattr(S, "_require_state", lambda: SimpleNamespace(turn=1))
    monkeypatch.setattr(S, "_get_ai", lambda: None)
    monkeypatch.setattr(S, "_backend", _B())

    with pytest.raises(HTTPException) as ei:
        S.api_advance(request=object(), req=S.AdvanceReq(expect_turn=9))
    assert ei.value.status_code == 409
    assert ei.value.detail["error_code"] == "STALE_TURN"


# ---------------------------------------------------------------- 收尾跳过
def test_settle_local_skips_finish_turn_on_replay(monkeypatch):
    """重放（回合未推进）⇒ 不跑 finish_turn；正常推进 ⇒ 照跑。"""
    from core import commands as C
    from backend.client import LocalBackend

    calls = {"finish": 0}
    st = SimpleNamespace(turn=3)

    def _fake_settle(state, expect_turn=None):
        if expect_turn is None:          # 正常推进
            state.turn += 1
        return ["log"]

    monkeypatch.setattr(C, "settle_local", _fake_settle)
    monkeypatch.setattr(C, "finish_turn", lambda s: calls.__setitem__("finish", calls["finish"] + 1))

    b = LocalBackend()
    b.settle_local(st, expect_turn=3)          # 重放（turn 不变）
    assert calls["finish"] == 0
    b.settle_local(st)                          # 正常（turn+1）
    assert calls["finish"] == 1
