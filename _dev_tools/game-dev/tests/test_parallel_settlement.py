# -*- coding: utf-8 -*-
"""并行执行升级测试：run_settlement_ai 线程池并行 / 结果统一 / economy 拒绝式 / 失败隔离。"""
import os
import sys
import threading
import time

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


class _FakeAI:
    """假 AI（测并行：记录并发执行、economy 拒绝/隔离）。"""

    def __init__(self, economy_ok=True, fail_agents=()):
        self.available = True
        self.economy_ok = economy_ok
        self.fail_agents = set(fail_agents)
        self.active = 0
        self.max_active = 0
        self.calls = []

    def _guard(self, name):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)
        self.active -= 1
        self.calls.append(name)

    def economy_decide(self, posture):
        self._guard("economy")
        if not self.economy_ok:
            return {"_error": "AI_CONTRACT_FAILED"}
        return {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
                "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无",
                "jiaozi_trust": "稳", "shortage": "平", "maritime": "平",
                "bank": "稳", "price_trend": "平"}

    def diplomacy_decide(self, posture, state=None):
        self._guard("diplomacy")
        if "diplomacy" in self.fail_agents:
            raise RuntimeError("diplomacy 失败")
        return {"attitude": "小", "sui_gong": "不变", "alliance": "不变"}

    def military_decide(self, posture, state=None):
        self._guard("military")
        if "military" in self.fail_agents:
            raise RuntimeError("military 失败")
        return {"power": "小", "army": "微", "training": "微", "morale": "微", "levy": "微"}

    def relief_decide(self, posture, state=None):
        self._guard("relief")
        if "relief" in self.fail_agents:
            raise RuntimeError("relief 失败")
        return {"disaster_level": 1, "relief": "微", "refugee": "微"}


def _run(client, woken=None):
    """同步包装 run_settlement_ai（无 UI → future.result() 直接取）。"""
    from core.async_ai import run_settlement_ai
    s = _new_state()
    fut = run_settlement_ai(client, "posture", s, woken, ui=None,
                            on_success=None, on_error=None)
    return fut.result(timeout=10)


def test_parallel_agents_all_results():
    """多 Agent 并行调用（woken 多个 → 全部进 results，统一字典）。"""
    fake = _FakeAI()
    # woken 含 diplomacy/military/relief（economy 强制并行）
    results = _run(fake, woken=["diplomacy", "military", "relief"])
    assert "_economy_ai" in results
    assert "_diplomacy_ai" in results
    assert "_military_ai" in results
    assert "_relief_ai" in results
    assert set(fake.calls) == {"economy", "diplomacy", "military", "relief"}


def test_parallel_concurrency():
    """并行：同一 client 锁内串行化（安全优先），多 agent 均被执行。"""
    fake = _FakeAI()
    _run(fake, woken=["diplomacy", "military", "relief"])
    assert len(fake.calls) == 4
    assert fake.max_active == 1, "同 client 锁内串行化（max_active 应 ≤1）"


def test_economy_reject():
    """economy 拒绝式：失败/非法 → AIRuntimeError（整单拒绝，不伪造）。"""
    from core.errors import AIRuntimeError
    fake = _FakeAI(economy_ok=False)
    with pytest.raises(AIRuntimeError):
        _run(fake, woken=["diplomacy"])


def test_failure_isolation():
    """失败隔离：非 economy 失败不阻断——其余 agent 仍进 results。"""
    fake = _FakeAI(fail_agents=("military",))
    results = _run(fake, woken=["diplomacy", "military", "relief"])
    assert "_economy_ai" in results
    assert "_diplomacy_ai" in results
    assert "_relief_ai" in results
    assert "_military_ai" not in results, "military 失败应隔离（不注入）"


def test_woken_none_fallback():
    """woken=None 路由失败退化：P1 三契约保底注入。"""
    fake = _FakeAI()
    results = _run(fake, woken=None)
    assert "_economy_ai" in results
    assert "_diplomacy_ai" in results
    assert "_military_ai" in results
    assert "_relief_ai" in results
