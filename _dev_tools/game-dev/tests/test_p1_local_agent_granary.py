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
