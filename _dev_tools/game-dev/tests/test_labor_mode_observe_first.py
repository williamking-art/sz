# -*- coding: utf-8 -*-
"""G1（Jev p=0.9915）：采购的劳动政策**优先读当月观测副本**，无记录才回落直调门面。

为什么钉：月结 Step 0 已把 labor_policy 裁决写进 `state._tiandao_observe` 与 `decision_log`；
`create_procurement_order` 原先每次都重调门面（自建 ctx）⇒ 日志与结算可能不是同一个裁决。
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.economy import procurement as P  # noqa: E402


def _state(obs=None, turn=3):
    st = SimpleNamespace(
        turn=turn,
        treasury=500_000.0,
        prefectures={"京畿路": {"local_treasury": 100_000.0, "unrest": 5.0,
                                "pops": {}}},
        goods={},
    )
    if obs is not None:
        st._tiandao_observe = obs
    return st


def _obs(verdict):
    return {"turn": 3, "read_only": True,
            "decisions": {"labor_service_policy": verdict},
            "distributions": {"labor_policy": {verdict: 1.0}}, "strengths": {}}


def test_observation_wins_over_live_facade():
    calls = []

    def _boom(ctx):
        calls.append(ctx)
        raise AssertionError("有观测副本时不得再调门面（否则日志与结算可能分叉）")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(P.EmbeddedDecisionFacade, "labor_service_policy",
                        staticmethod(_boom))
    try:
        st = _state(_obs("hired"))
        order = P.create_procurement_order(st, "京畿路", budget=1000)
        assert calls == [], "观测副本存在时不得回落直调门面"
        assert getattr(order, "labor_mode", None) == "hired"
    finally:
        monkeypatch.undo()


def test_falls_back_to_facade_without_record():
    seen = []

    def _fake(ctx):
        seen.append(ctx)
        return "corvee"

    mp = pytest.MonkeyPatch()
    mp.setattr(P.EmbeddedDecisionFacade, "labor_service_policy", staticmethod(_fake))
    try:
        st = _state(obs=None)          # 无观测副本（首月/读旧档）
        order = P.create_procurement_order(st, "京畿路", budget=1000)
        assert len(seen) == 1, "无记录时必须回落直调门面（保留旧行为）"
        assert getattr(order, "labor_mode", None) == "corvee"
    finally:
        mp.undo()
