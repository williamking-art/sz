# -*- coding: utf-8 -*-
"""D 数值接线 2/10（Jev A 0.464）：reform_compliance_gate=False ⇒ finance_rates 幅度 ×0.5。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    pass


def test_factor_defaults_without_record():
    from core.settlement_decree import _reform_compliance_factor

    assert _reform_compliance_factor(_S()) == 1.0


def test_factor_half_when_gate_false_or_undefined_one():
    from core.settlement_decree import _reform_compliance_factor

    s = _S()
    s._tiandao_observe = {"decisions": {"reform_compliance_gate": False}}
    assert _reform_compliance_factor(s) == 0.5
    s._tiandao_observe = {"decisions": {
        "reform_compliance_gate": {"verdict": False, "defined": True}}}
    assert _reform_compliance_factor(s) == 0.5
    for dec in (True, {"verdict": True, "defined": True},
                {"verdict": False, "defined": False}):
        s._tiandao_observe = {"decisions": {"reform_compliance_gate": dec}}
        assert _reform_compliance_factor(s) == 1.0, dec


def test_finance_reform_scaled_by_half_when_gate_false():
    from core.commands import new_game
    from core.settlement_decree import _apply_decree_effect

    s = new_game("史实")
    s._tiandao_observe = {"decisions": {"reform_compliance_gate": False}}
    base = float(s.finance.get("collection_rate"))
    log = []
    _apply_decree_effect(s, {"effects": {"finance_rates": {"collection_rate": 0.10}}}, log)
    got = float(s.finance.get("collection_rate"))
    assert abs((got - base) - 0.05) < 1e-9, (base, got)
    assert any("×0.5" in line for line in log), log


def test_finance_reform_unscaled_without_record():
    from core.commands import new_game
    from core.settlement_decree import _apply_decree_effect

    s = new_game("史实")
    base = float(s.finance.get("collection_rate"))
    _apply_decree_effect(s, {"effects": {"finance_rates": {"collection_rate": 0.10}}}, [])
    got = float(s.finance.get("collection_rate"))
    assert abs((got - base) - 0.10) < 1e-9, (base, got)
