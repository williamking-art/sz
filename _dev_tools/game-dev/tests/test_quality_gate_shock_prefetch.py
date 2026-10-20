# -*- coding: utf-8 -*-
"""质量放行门 · 事件民心冲击档生产者与预取（2026-10-20）。

链路：settle_local → 预取（application/shock_prefetch）→ AI 契约 shock_decide（内嵌 Jev）
      → state._<kind>_shock_tier → 结算按档扣民心（缺档回退旧 -1）。

钉住：
1. 生产者：三个 kind 分别写对应槽位；非法档/未知 kind 不写；
2. 预取：仓廪低于阈值 ⇒ 预判 granary+famine；大策内卫 ⇒ focus；无条件 ⇒ 空；
3. 预取失败吞掉（不抛）；
4. 结算前调用点在 settle_local（源码静态断言）。
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    def __init__(self, granary=1000, cap=100000, branch=""):
        self.granary = granary
        self.granary_cap = cap
        self.focus = {"branch": branch} if branch else {}
        self.population_satisfaction = 50
        self.prestige = 50
        self.treasury = 100000
        self.statistics = {}


def test_producer_writes_slots(monkeypatch):
    from ai import jev_gate
    from ai.client import AIClient

    monkeypatch.setattr(jev_gate, "decide_choice",
                        lambda *a, **k: {"choice": "重", "probabilities": {}, "confidence": None})
    s = _S()
    got = AIClient().shock_decide(s, "famine", "仓廪将空")
    assert got == {"kind": "famine", "tier": "重"}
    assert s._famine_shock_tier == "重"


def test_producer_rejects_bad(monkeypatch):
    from ai import jev_gate
    from ai.client import AIClient

    monkeypatch.setattr(jev_gate, "decide_choice",
                        lambda *a, **k: {"choice": "胡说", "probabilities": {}, "confidence": None})
    s = _S()
    assert AIClient().shock_decide(s, "granary") is None
    assert not hasattr(s, "_granary_shock_tier")
    assert AIClient().shock_decide(s, "unknown") is None


def test_detect_kinds():
    from application.shock_prefetch import detect_kinds

    assert detect_kinds(_S(granary=1000, cap=100000)) == ["granary", "famine"]
    assert detect_kinds(_S(granary=50000, cap=100000, branch="internal")) == ["focus"]
    assert detect_kinds(_S(granary=50000, cap=100000)) == []


def test_prefetch_writes_slots(monkeypatch):
    import application.shock_prefetch as sp

    class _C:
        def shock_decide(self, state, kind, context=""):
            setattr(state, "_%s_shock_tier" % kind, "中")
            return {"kind": kind, "tier": "中"}

    monkeypatch.setattr(sp, "AIClient", lambda: _C(), raising=False)
    monkeypatch.setattr("ai.client.AIClient", lambda: _C())
    s = _S(granary=1000, cap=100000)
    got = sp.prefetch_shock_tiers(s)
    assert got == {"granary": "中", "famine": "中"}
    assert s._granary_shock_tier == "中" and s._famine_shock_tier == "中"


def test_prefetch_failure_swallowed(monkeypatch):
    import application.shock_prefetch as sp

    monkeypatch.setattr("ai.client.AIClient", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    s = _S(granary=0, cap=100000)
    assert sp.prefetch_shock_tiers(s) == {}


def test_settle_local_calls_prefetch():
    from core import commands

    src = inspect.getsource(commands.settle_local)
    assert "prefetch_shock_tiers" in src
