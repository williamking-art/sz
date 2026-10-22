# -*- coding: utf-8 -*-
"""变法遵从 → 财政改革幅度（2026-10-22 审查 B1 后重写：**按强度连续**，不再是二值 ×0.5）。

改前（旧契约）：`reform_compliance_gate is False ⇒ ×0.5`、True ⇒ 1.0（argmax 查表）。
改后：`factor = REFORM_COMPLIANCE_FLOOR(0.5) + 0.5 × strength`，
其中 `strength = observe_strength("reform_compliance") ∈ [0,1]`；
恒等式：p ≥ 阈值时 `factor ≡ p`（0.805 ⇒ ×0.805）；p < 阈值 ⇒ ×0.5；缺失 ⇒ 1.0。

细粒度契约见 `test_tiandao_effects_probabilistic_fiscal.py`。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    turn = 3


def _obs(st, strength=None):
    st._tiandao_observe = {
        "turn": 3, "read_only": True, "decisions": {}, "distributions": {},
        "strengths": ({} if strength is None else {"reform_compliance": strength}),
    }
    return st


def test_factor_defaults_without_record():
    """无观测副本 ⇒ 1.0（不施加惩罚）。"""
    from core.settlement_decree import _reform_compliance_factor

    assert _reform_compliance_factor(_S()) == 1.0


def test_factor_floor_when_strength_zero():
    """门闸未过（含 p<阈值、未定义）⇒ 下限 0.5（沿用改前"不遵从"的幅度）。"""
    from core.settlement_decree import _reform_compliance_factor

    assert _reform_compliance_factor(_obs(_S(), 0.0)) == 0.5
    assert _reform_compliance_factor(_obs(_S(), 0.5)) == 0.5


def test_factor_continuous_in_strength():
    """同 gate 通过、强度不同 ⇒ 因子不同且单调（0.6/0.9 强度 ⇒ 0.8/0.95）。"""
    from core.settlement_decree import _reform_compliance_factor

    lo = _reform_compliance_factor(_obs(_S(), 0.6))
    hi = _reform_compliance_factor(_obs(_S(), 0.9))
    assert 1.0 > hi > lo > 0.5, (lo, hi)
    # 恒等式：p ≥ 阈值时 factor ≡ p（0.6 ⇒ 0.6；0.9 ⇒ 0.9）
    assert abs(lo - 0.6) < 1e-9 and abs(hi - 0.9) < 1e-9


def test_finance_reform_scaled_by_continuous_factor():
    """结算级：改革幅度按因子缩放（p=0.9 ⇒ ×0.9，不再是 ×0.5 或 1.0）。"""
    from core.commands import new_game
    from core.settlement_decree import _apply_decree_effect

    s = new_game("史实")
    s._tiandao_observe = {"turn": 3, "read_only": True, "decisions": {},
                          "distributions": {},
                          "strengths": {"reform_compliance": 0.9}}
    base = float(s.finance.get("collection_rate"))
    log = []
    _apply_decree_effect(s, {"effects": {"finance_rates": {"collection_rate": 0.10}}}, log)
    got = float(s.finance.get("collection_rate"))
    assert abs((got - base) - 0.09) < 1e-9, (base, got)


def test_finance_reform_unscaled_without_record():
    from core.commands import new_game
    from core.settlement_decree import _apply_decree_effect

    s = new_game("史实")
    base = float(s.finance.get("collection_rate"))
    _apply_decree_effect(s, {"effects": {"finance_rates": {"collection_rate": 0.10}}}, [])
    got = float(s.finance.get("collection_rate"))
    assert abs((got - base) - 0.10) < 1e-9, (base, got)
