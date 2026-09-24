# -*- coding: utf-8 -*-
"""两段式回合推进（2026-09-21「点过回合即弹民间情况」）的验收测试。

三段语义（用户定稿）：
  ① **民间情况**（首段，<1s）：`advance_two_phase` 立即返回 `(events, [], civilian)`——
     民间小故事串 = 本回合局势 + 圣旨 → 民间反应（程序真值模板，**不依赖结算**）。
  ② **后台段**（daemon `_async_settle`）：economy 强制 + agent 注入 → 程序结算
     → finish_turn；然后 `_rich_narrative` 三路：AI 民间反应(`rich_civilian`)、
     AI 官方月报(`rich_report`)、AI 奏章(`memorials`)。
  ③ **回合报告**（第二次弹）：`rich_ready=true` + `rich_report`（AI 官方月报 / fallback
     兜底）；**数值失败** → 快照回滚（**富化字段不随快照折回**，S-1 2026-09-21 重审）
     + `state.settle_error` + `rich_ready=True`（前端走"推演未成"路径，不再抛给 HTTP）。
     **AI 缺席/未配置** → 首段**预检立即拒绝式** `AIRuntimeError(code="AI_NOT_CONFIGURED")`
     （M-1 2026-09-21 重审：与 settle_turn 同形，不 spawn daemon、回合不推进）。
"""
import contextlib
import os
import sys
import threading
import time

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.commands import advance_two_phase  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402

RICH_TEXT = "【AI 富化月报】市易务行户争相质入库钱，商旅乃通。（由 fake 模型生成）"
RICH_CIV = "【AI 民间反应】米肆贩夫私语：清丈令既下，邻里相询者众。（AI 版民间反应）"
FAKE_MEMOS = [{"title": "劝农使上言", "text": "臣本月按行州县……"}]


class TwoPhaseFakeAI:
    """两段式结算专用替身（接口面与 tests.fake_ai_backend.FakeAIClient 不同，故独立命名）。"""

    def __init__(self):
        self.available = True
        self.token_usage = {"calls": 0, "prompt": 0, "completion": 0}

    def settlement_mode(self):
        return contextlib.nullcontext(False)

    def economy_decide(self, posture):
        return {"景气档": "中", "士绅囤粮": "微", "生产投入": "微"}

    def civilian_situation(self, state=None):
        return {"text": RICH_CIV}

    def generate_memorials(self, posture, state=None, count=3):
        return {"memorials": [{"title": "劝农使上言", "text": "臣本月按行州县……"}]}

    def monthly_report(self, year, month, era_name, posture):
        return {"report": RICH_TEXT}

    def reset_meter(self):
        self.token_usage = {"calls": 0, "prompt": 0, "completion": 0}


def _wait_ready(state, timeout: float = 10.0) -> bool:
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        if getattr(state, "rich_ready", False):
            return True
        time.sleep(0.05)
    return False


def test_first_phase_returns_civilian_immediately_algorithmic_not_rich():
    """"点过回合"首段（<3s，fake 无网络）：civilian=程序真值民间反应，**非 AI 富文本**；
    数值结算（log）留空（后台段跑）。"""
    s = GameState("史实")
    init_legacies(s)
    fake = TwoPhaseFakeAI()
    events, log, civilian = advance_two_phase(s, fake)
    assert isinstance(civilian, str) and civilian, "民间反应文本必须即得"
    assert RICH_TEXT not in civilian and RICH_CIV not in civilian, \
        "首段（民间情况）不得含 AI 富化文本（同源的富文本在 round2，玩家读的是程序版）"
    assert log == [], "首段 log 为空（数值结算已押后台）"
    assert _wait_ready(s, 10.0), "后台段应在窗口内完成"


def test_async_settle_fills_rich_fields_and_settle_log():
    """round2 完成 → rich_report / rich_civilian / memorials 就位；朝报挂在 _last_settle_log。"""
    s = GameState("史实")
    init_legacies(s)
    advance_two_phase(s, TwoPhaseFakeAI())
    assert _wait_ready(s, 10.0), "后台段须在 10s 窗口内跑完（fake 无网络）"
    assert s.rich_report == RICH_TEXT, "官方月报（结算后总结）应入 rich_report"
    assert s.rich_civilian == RICH_CIV, "AI 民间反应应入 rich_civilian"
    assert getattr(s, "_last_settle_log", None), "后台结算的朝报应挂 _last_settle_log（供回合报告弹窗）"
    assert s.memorials, "AI 奏章应入 state.memorials"


def test_ai_missing_raises_not_configured_before_daemon():
    """M-1（2026-09-21 重审）：AI 缺席/未配置 → 首段**预检立即拒绝式**（与 settle_turn
    同形）：抛 `AIRuntimeError(code="AI_NOT_CONFIGURED")`，不 spawn daemon、回合不推进。
    修复前：首段照常返回民间故事，后台段才落 `settle_error='AI_CONTRACT_FAILED…'`
    （`AIClient()` 未配置时 `economy_decide` 静默返回 None，错码误导），且故事随回滚消失。"""
    from core.errors import AIRuntimeError

    s = GameState("史实")
    init_legacies(s)
    n_threads = threading.active_count()
    with pytest.raises(AIRuntimeError) as ei:
        advance_two_phase(s, None)
    assert ei.value.code == "AI_NOT_CONFIGURED", "AI 缺席必须落精确错误码 AI_NOT_CONFIGURED"
    assert s.turn == 0, "拒绝路径回合不得推进"
    assert threading.active_count() == n_threads, "拒绝路径不得 spawn 后台 daemon"

    class _NoAI:            # available=False 的替身（不依赖本机 ai_config.json）
        available = False

    with pytest.raises(AIRuntimeError) as ei2:
        advance_two_phase(s, _NoAI())
    assert ei2.value.code == "AI_NOT_CONFIGURED"


def test_settle_failure_clears_rich_fields():
    """S-1（2026-09-21 重审）：数值结算失败回滚后，富化字段必须清空——
    绝不携带上一回合的 rich_report / rich_civilian / _last_settle_log（前端
    AdvancePanel 只判 ready，残留会让上月文本当月显示；Dock 单次触发会弹上月报告）。"""
    s = GameState("史实")
    init_legacies(s)
    advance_two_phase(s, TwoPhaseFakeAI())
    assert _wait_ready(s, 10.0), "首回合成功，富化字段就位"
    assert s.rich_report == RICH_TEXT and s.rich_civilian == RICH_CIV
    assert getattr(s, "_last_settle_log", None), "成功回合朝报应就位"

    class Boom(TwoPhaseFakeAI):
        def economy_decide(self, posture):
            raise RuntimeError("模拟推演失败")

    turn_before = s.turn
    advance_two_phase(s, Boom())
    assert _wait_ready(s, 10.0), "失败也要就位 rich_ready（前端停轮询）"
    assert s.settle_error, "失败回合必须落账 settle_error"
    assert s.rich_report == "", "失败回滚不得残留上一回合月报"
    assert s.rich_civilian == "", "失败回滚不得残留上一回合民间反应"
    assert not getattr(s, "_last_settle_log", None), "失败回滚不得残留上一回合朝报"
    assert s.turn == turn_before, "失败回滚回合不推进"


def test_no_stale_ready_window_on_failure():
    """S-1 窗口回归：失败回合期间任何时刻，round2 视角都不得出现
    「ready=True + settle_error='' + 富文本非空」组合（修复前：快照把上一回合的
    ready=True 与富文本折回，Dock 单次触发轮询命中即弹上月报告并吞掉「推演未成」）。
    采样从首次 advance 返回后开始——成功残留态（ready+无错误+富文本）是合法态不计入。"""
    s = GameState("史实")
    init_legacies(s)
    advance_two_phase(s, TwoPhaseFakeAI())
    assert _wait_ready(s, 10.0)

    class Boom(TwoPhaseFakeAI):
        def economy_decide(self, posture):
            raise RuntimeError("模拟推演失败")

    bad: list = []
    stop = threading.Event()

    def _sampler():
        while not stop.is_set():
            try:
                if (getattr(s, "rich_ready", False)
                        and not getattr(s, "settle_error", "")
                        and (getattr(s, "rich_report", "")
                             or getattr(s, "rich_civilian", ""))):
                    bad.append(1)
            except Exception:  # noqa: BLE001 — 采样不干扰主流程
                pass

    advance_two_phase(s, Boom())           # 首个失败回合：发起后再开采样
    th = threading.Thread(target=_sampler, daemon=True)
    th.start()
    try:
        assert _wait_ready(s, 10.0)
        assert s.settle_error
        for _ in range(5):                 # 连续失败回合反复压测窗口
            advance_two_phase(s, Boom())
            assert _wait_ready(s, 10.0)
            assert s.settle_error
    finally:
        stop.set()
        th.join(timeout=2)
    assert not bad, f"检测到 {len(bad)} 次「ready+无错误+富文本」窗口（S-1 回归）"


def test_rich_fields_survive_save_roundtrip(tmp_path, monkeypatch):
    """存档兼容：rich_report/rich_civilian/rich_ready 三字段幂等往返。"""
    import core.save_load as sl
    monkeypatch.setattr(sl, "SAVE_DIR", str(tmp_path), raising=False)
    s = GameState("史实")
    s.rich_report = "旧档富文样例"
    s.rich_civilian = "旧档民间反应样例"
    s.rich_ready = True
    assert sl.save_game(s, 6) is True
    s2 = sl.load_game(6)
    assert s2 is not None
    assert s2.rich_report == "旧档富文样例"
    assert s2.rich_civilian == "旧档民间反应样例"
    assert s2.rich_ready is True
