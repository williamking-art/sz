# -*- coding: utf-8 -*-
"""质量放行门 · 民心变动天道档位化（2026-10-20）。

背景：花石纲修正写死「每月民心 -1」⇒ 60 月回放民心 55→0。
改法：天道/Jev 出民情档位（大坏/转坏/持平/转好/大好）→ 程序换算月度增量；
缺档 ⇒ 程序先验（花石纲在册 -1/月）；有界 [-3,+3]、民心 [0,100]。

钉住：
1. 档位映射：大坏-3 / 转坏-1 / 持平0 / 转好+1 / 大好+3；
2. 天道档优先于程序先验；provider 次之；全缺 ⇒ 先验（花石纲在册 -1，否则 0）；
3. 花石纲修正**不再直接改数值**（只留痕）；
4. 边界：民心不越 [0,100]；
5. 生产者（AI 契约）用内嵌 Jev 出档并写槽位，失败不写槽；
6. 已注册 agent 与 token 分组「推演」。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.politics.sentiment_tier import (  # noqa: E402
    SENTIMENT_DELTA, apply_sentiment_trend, register_sentiment_provider,
    resolve_sentiment)


class _S:
    def __init__(self, sat=55, legacy=None):
        self.population_satisfaction = sat
        self.legacy_modifiers = legacy if legacy is not None else {"huashigang": True}


def test_tier_mapping():
    assert SENTIMENT_DELTA == {"大坏": -3, "转坏": -1, "持平": 0, "转好": 1, "大好": 3}


def test_ai_tier_beats_prior():
    s = _S(sat=50)
    s._sentiment_ai = {"tier": "转好"}
    got = resolve_sentiment(s)
    assert got["source"] == "天道" and got["delta"] == 1
    apply_sentiment_trend(s, [])
    assert s.population_satisfaction == 51


def test_missing_tier_falls_back_to_prior():
    s = _S(sat=50)
    got = resolve_sentiment(s)
    assert got["source"] == "程序先验" and got["delta"] == -1, got
    s2 = _S(sat=50, legacy=[])
    assert resolve_sentiment(s2)["delta"] == 0


def test_provider_injection():
    s = _S(sat=50)
    register_sentiment_provider(lambda st: {"tier": "大好", "note": "test"})
    try:
        got = resolve_sentiment(s)
        assert got["tier"] == "大好" and got["delta"] == 3
        assert got["source"].startswith("天道")
    finally:
        from core.domains.politics import sentiment_tier as st_mod
        st_mod._PROVIDERS.clear()


def test_bounds():
    s = _S(sat=1)
    s._sentiment_ai = {"tier": "大坏"}
    apply_sentiment_trend(s, [])
    assert s.population_satisfaction == 0, "民心不得为负"
    s2 = _S(sat=100)
    s2._sentiment_ai = {"tier": "大好"}
    apply_sentiment_trend(s2, [])
    assert s2.population_satisfaction == 100, "民心不得超 100"


def test_huashigang_no_longer_writes_number():
    from core.domains.politics import legacy_mechanic as lm

    s = _S(sat=50)
    log = []
    lm._eff_huashigang(s, log)
    assert s.population_satisfaction == 50, "花石纲不得再直接扣民心"
    assert any("天道裁断" in x for x in log)


def test_producer_uses_jev_choice(monkeypatch):
    from ai import jev_gate
    from ai.client import AIClient

    monkeypatch.setattr(jev_gate, "decide_choice",
                        lambda *a, **k: {"choice": "转坏", "probabilities": {}, "confidence": None})
    s = _S(sat=60)
    got = AIClient().sentiment_decide(s)
    assert got == {"tier": "转坏", "note": "天道裁民情"}
    assert s._sentiment_ai["tier"] == "转坏"


def test_producer_invalid_choice_no_slot(monkeypatch):
    from ai import jev_gate
    from ai.client import AIClient

    monkeypatch.setattr(jev_gate, "decide_choice",
                        lambda *a, **k: {"choice": "胡说", "probabilities": {}, "confidence": None})
    s = _S(sat=60)
    assert AIClient().sentiment_decide(s) is None
    assert not hasattr(s, "_sentiment_ai")


def test_registered_and_grouped():
    from ai.token_meter import token_group_of
    from application import agent_router as ar

    assert "sentiment" in ar.AGENT_DEFS
    assert ar.AGENT_DEFS["sentiment"]["method"] == "sentiment_decide"
    assert token_group_of("sentiment_decide") == "推演"
