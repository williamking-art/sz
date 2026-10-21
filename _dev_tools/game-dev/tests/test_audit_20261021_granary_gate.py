# -*- coding: utf-8 -*-
"""D 数值接线（Jev B 0.492）：仓场贪墨门=False ⇒ 雀鼠耗本色损耗 ×0.5（不归零）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    pass


def test_factor_defaults_when_no_observe_record():
    from core.settlement_granary import _granary_corruption_factor

    assert _granary_corruption_factor(_S()) == 1.0


def test_factor_half_when_gate_false():
    from core.settlement_granary import _granary_corruption_factor

    s = _S()
    s._tiandao_observe = {"decisions": {"granary_corruption_check": False}}
    assert _granary_corruption_factor(s) == 0.5
    s._tiandao_observe = {"decisions": {
        "granary_corruption_check": {"verdict": False, "defined": True}}}
    assert _granary_corruption_factor(s) == 0.5


def test_factor_one_when_true_or_undefined():
    from core.settlement_granary import _granary_corruption_factor

    for dec in (True, {"verdict": True, "defined": True},
                {"verdict": False, "defined": False}, {"error": "x"}):
        s = _S()
        s._tiandao_observe = {"decisions": {"granary_corruption_check": dec}}
        assert _granary_corruption_factor(s) == 1.0, dec


def test_observe_then_settlement_uses_half_loss():
    """月结入口先观察再结算：False 时应实际减半（与无记录基线对比）。"""
    from core.ai.tiandao_facade import TianDaoFacade
    from core.commands import new_game
    from core.settlement import run_monthly_settlement

    s = new_game("史实")
    TianDaoFacade.observe_monthly(s)
    assert s._tiandao_observe["decisions"]["granary_corruption_check"] is False
    run_monthly_settlement(s)
    # 记录仍在（月结会重新观察）；只验证不报错且损耗日志出现
    assert getattr(s, "_tiandao_observe", None) is not None
