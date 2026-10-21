# -*- coding: utf-8 -*-
"""P1：本地 Agent 决策第一片（仓廪）——降 token，默认关闭、失败回落。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def test_local_granary_contract_shape(monkeypatch):
    from application.local_agent_decisions import local_granary_decide

    class S:
        granary = 800_000
        granary_cap = 1_000_000
        canal_block = 10
        disaster_severity = 2
        month = 6
        grain_price = 100
        prefectures = {"路A": {"unrest": 10, "grain_price": 160}}
        army_units = []
        corruption = {"甲": 0.7}

    got = local_granary_decide(S())
    assert got and got["_source"] == "local_tiandao"
    g = got["granary"]
    for k in ("inflow", "outflow", "price_stabilize", "army_supply"):
        assert g[k] in ("微", "小", "中", "大")
    assert g["storage_loss"] in ("无", "轻", "中", "重")
    assert got["narrative"]


def test_local_decide_respects_flag(monkeypatch):
    from application import local_agent_decisions as lad

    class S:
        granary = 1
        month = 1

    monkeypatch.delenv("SONGZUO_LOCAL_AGENTS", raising=False)
    assert lad.local_decide("granary", S()) is None
    monkeypatch.setenv("SONGZUO_LOCAL_AGENTS", "1")
    assert lad.local_decide("granary", S()) is not None
    assert lad.local_decide("unknown", S()) is None


def test_local_relief_contract_shape():
    from application.local_agent_decisions import local_relief_decide

    class S:
        disaster_severity = 4
        granary = 100_000
        prefectures = {"路A": {"refugees": 120_000}, "路B": {"refugees": 20_000}}

    got = local_relief_decide(S())
    assert got["disaster_level"] == 4
    assert got["relief"] == "大"
    assert got["refugee"] in ("微", "小", "中", "大")
    assert got["_source"] == "local_tiandao"
    assert local_relief_decide(type("S", (), {"disaster_severity": 0,
                                              "prefectures": {}})()) is None


def test_local_economy_contract_shape():
    from application.local_agent_decisions import local_economy_decide
    from core.commands import new_game

    got = local_economy_decide(new_game("史实"))
    assert got["_source"] == "local_tiandao"
    assert got["士绅"] in ("囤", "抛", "观望")
    for k in ("jiaozi_trust", "shortage", "maritime", "bank", "price_trend"):
        assert isinstance(got[k], str) and got[k]
    assert got["景气"] in ("无", "微", "小", "中", "大", "巨", "极")


def test_ai_prelude_local_economy_skips_llm(monkeypatch):
    from core.commands import _ai_prelude
    from core.commands import new_game

    monkeypatch.setenv("SONGZUO_LOCAL_AGENTS", "1")
    s = new_game("史实")
    calls = []

    class FakeAI:
        available = False

        def economy_decide(self, posture):
            calls.append("llm")
            raise AssertionError("本地经济已判，不应调 LLM")

    _ai_prelude(s, FakeAI())
    assert calls == []
    assert s._economy_ai.get("_source") == "local_tiandao"
    assert s.local_agent_stats["economy"] == 1


def test_local_diplomacy_and_military_shapes():
    from application.local_agent_decisions import (
        local_diplomacy_decide, local_military_decide)

    class S:
        treasury = 2_500_000
        external = {"金": {"invasion_will": 75}, "辽": {"invasion_will": 10}}
        army_units = []

    d = local_diplomacy_decide(S())
    assert d["attitude"] in ("微", "小", "中", "大")
    assert d["sui_gong"] in ("订", "毁", "不变")
    assert d["alliance"] in ("结", "断", "不变")

    m = local_military_decide(S())
    for k in ("power", "army", "training", "morale", "levy"):
        assert m[k] in ("微", "小", "中", "大")


def test_local_unrest_and_sentiment_shapes():
    from application.local_agent_decisions import (
        local_agent_savings, local_sentiment_decide, local_unrest_decide)

    class S:
        population_satisfaction = 35
        prestige = 50
        treasury = 1_000_000
        prefectures = {"路A": {"unrest": 70, "refugees": 120_000}}
        local_agent_stats = {"economy": 2, "saved_llm_calls": 2}

    u = local_unrest_decide(S())
    assert u["tier"] in ("无", "小乱", "骚乱", "大乱")
    s = local_sentiment_decide(S())
    assert s["tier"] in ("大坏", "转坏", "持平", "转好", "大好")
    save = local_agent_savings(S())
    assert save["by_agent"] == {"economy": 2} and save["saved_llm_calls"] == 2


def test_local_decree_duration_shape():
    from application.local_agent_decisions import local_decree_duration_decide

    class S:
        turn = 5
        prestige = 50
        population_satisfaction = 50
        corruption = {"甲": 0.4}
        pending_decrees = [{"decree_id": "d1", "title": "裁冗",
                            "effects": {"reduce_office": 1}}]

    got = local_decree_duration_decide(S())
    assert got["pace"] in ("速", "常", "缓")
    assert got["execution_timing"] in ("即时", "短期", "长期")
    assert got["execution_attitude"] in ("奉行", "依违", "阳奉阴违", "拖延")
    assert got["landing_level"] in ("全办", "大部", "半数", "少半", "未办")
    assert got["_decree_ids"] == ["d1"] and got["_turn"] == 5


def test_inject_one_uses_local_and_skips_llm(monkeypatch):
    from application.agent_router import _inject_one
    from core.commands import new_game

    monkeypatch.setenv("SONGZUO_LOCAL_AGENTS", "1")
    s = new_game("史实")
    calls = []

    class FakeAI:
        def granary_decide(self, posture, state=None):
            calls.append("llm")
            return {"granary": {"inflow": "小", "outflow": "小",
                                "price_stabilize": "小", "army_supply": "小",
                                "storage_loss": "中"}, "narrative": "llm"}

    failures = []
    injected = _inject_one(s, FakeAI(), failures, "granary")
    assert injected == "granary"
    assert calls == [], "本地已判时不应再调 LLM"
    assert getattr(s, "_granary_ai", {}).get("_source") == "local_tiandao"
    assert s.local_agent_stats["granary"] == 1
    assert s.local_agent_stats["saved_llm_calls"] == 1
    assert failures == []
