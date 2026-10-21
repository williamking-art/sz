# -*- coding: utf-8 -*-
"""P1：天道/Jev 与 DecisionService 适配（只读、行为一致、写决策日志）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def test_adapter_matches_facade_for_all_observe_objectives():
    from core.ai.tiandao_facade import TianDaoFacade
    from core.ai.tiandao_decision import SPECS, build_service
    from core.foundation.kernel.decision import DecisionRequest
    from core.commands import new_game

    s = new_game("史实")
    ctx = TianDaoFacade.build_state_context(s)
    svc = build_service()
    for method, objective in TianDaoFacade.OBSERVE_OBJECTIVES.items():
        direct = getattr(TianDaoFacade, method)(ctx)
        request = DecisionRequest(objective, {"state_context": ctx},
                                  options=tuple(SPECS[objective][1]), turn=0)
        result = svc.decide(request)
        if isinstance(direct, dict):
            direct_v, direct_d = direct.get("verdict"), direct.get("defined")
        else:
            direct_v, direct_d = direct, True
        assert result.verdict == direct_v, objective
        assert bool(result.defined) == bool(direct_d), objective


def test_observe_monthly_writes_decision_log_readonly():
    from core.ai.tiandao_facade import TianDaoFacade
    from core.commands import new_game

    s = new_game("史实")
    before = s.treasury
    Facade = TianDaoFacade.observe_monthly(s)
    assert s.treasury == before, "只读观察不得改钱"
    assert len(s.decision_log) == len(TianDaoFacade.OBSERVE_OBJECTIVES)
    assert {x["objective"] for x in s.decision_log} == set(TianDaoFacade.OBSERVE_OBJECTIVES.values())
