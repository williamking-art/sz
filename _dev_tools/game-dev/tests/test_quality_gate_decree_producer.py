# -*- coding: utf-8 -*-
"""质量放行门 · 诏令天道槽位生产者（2026-10-20）。

生产者 = `AIClient.decree_duration_decide`（调内嵌 jev_gate 出档位，填 state._decree_ai）。

钉住：
1. Jev 可用 ⇒ 槽位被填（pace/execution_timing/execution_attitude/landing_level），消费者能读到；
2. Jev 不可用（decide_choice 返回 None）⇒ **不写槽位**、返回 None（缺失≠假装已判）；
3. 非法档位被丢弃，不污染槽位；
4. 已注册为可唤醒 Agent（AGENT_DEFS），且不再列在 PENDING_CONTRACTS；
5. 结算链不直接调用（静态断言：settlement_decree 不 import jev_gate）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    def __init__(self):
        self.prestige = 70
        self.population_satisfaction = 55
        self.pending_decrees = [{"decree_id": "d1", "title": "加薪诏", "category": "诏令",
                                 "effects": {"pay_reform": "常"}}]


class _Client:
    """用 mixin 直接挂到最小 client 上（不依赖 AIClient 组合方式）。"""

    def __init__(self):
        from ai.contracts_decree import DecreeContractMixin

        self._mixin = DecreeContractMixin()

    def decree_duration_decide(self, state):
        return self._mixin.decree_duration_decide(state)


def _client():
    return _Client()


def test_slot_filled_when_jev_available(monkeypatch):
    from ai import jev_gate

    answers = {"速": "速", "即时": "即时", "奉行": "奉行", "全办": "全办"}

    def fake_choice(ctx, instructions, criteria, *, question_key="q"):
        for k, v in answers.items():
            if k in criteria:
                return {"choice": v, "probabilities": {v: 0.9}, "confidence": None}
        return None

    monkeypatch.setattr(jev_gate, "decide_choice", fake_choice)
    s = _S()
    out = _client().decree_duration_decide(s)
    assert out, out
    assert s._decree_ai["pace"] == "速"
    assert s._decree_ai["execution_timing"] == "即时"
    assert s._decree_ai["execution_attitude"] == "奉行"
    assert s._decree_ai["landing_level"] == "全办"


def test_consumer_reads_produced_slot(monkeypatch):
    from ai import jev_gate
    from core.domains.politics.decree_duration import resolve_decree_duration

    monkeypatch.setattr(jev_gate, "decide_choice",
                        lambda *a, **k: {"choice": "长期", "probabilities": {}, "confidence": None}
                        if "即时" in a[2] else None)
    s = _S()
    _client().decree_duration_decide(s)
    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=60, followup=0)
    assert got["timing"] == "long" and got["timing_source"] == "天道"


def test_no_slot_when_jev_unavailable(monkeypatch):
    from ai import jev_gate

    monkeypatch.setattr(jev_gate, "decide_choice", lambda *a, **k: None)
    s = _S()
    out = _client().decree_duration_decide(s)
    assert out is None
    assert not hasattr(s, "_decree_ai"), "Jev 不可用不得写槽位"


def test_invalid_choice_discarded(monkeypatch):
    from ai import jev_gate

    monkeypatch.setattr(jev_gate, "decide_choice",
                        lambda *a, **k: {"choice": "胡说", "probabilities": {}, "confidence": None})
    s = _S()
    out = _client().decree_duration_decide(s)
    assert out is None and not hasattr(s, "_decree_ai")


def test_registered_in_agent_defs():
    from application import agent_router as ar

    assert "decree_duration" in ar.AGENT_DEFS
    assert ar.AGENT_DEFS["decree_duration"]["method"] == "decree_duration_decide"
    assert not any(p[0] == "_decree_ai" for p in ar.PENDING_CONTRACTS), ar.PENDING_CONTRACTS


def test_settlement_does_not_call_jev():
    import inspect

    from core import settlement_decree as sd

    src = inspect.getsource(sd)
    assert "jev_gate" not in src, "结算链不得直接调 Jev（同步 HTTP）"