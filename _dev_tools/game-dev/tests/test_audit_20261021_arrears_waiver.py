# -*- coding: utf-8 -*-
"""蠲免陈年逋欠 → 核销比例（2026-10-22 审查 B1 后重写：**按强度比例**，不再是布尔全免）。

改前（旧契约）：`should_waive_ancient_arrears is True` ⇒ 核销 10% 欠税存量 + 暂停追缴（布尔开关，
违反 `core/ai/README.md` 契约第 14 条）。
改后：`_arrears_waiver_ratio(state)` = `observe_strength("waive_arrears") ∈ [0,1]`：
- 核销额 = 欠税存量 × `WAIVER_WRITEOFF_CAP`(10%) × ratio；
- 追缴额 = 应追缴 × (1 − ratio)（不再是"全停"）；
- 缺失 / 未过阈值 ⇒ 0.0（= 改前 False 路径，逐字节一致）。

细粒度契约见 `test_tiandao_effects_probabilistic_fiscal.py`。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    turn = 3


def _obs(st, strength=None, decisions=None):
    st._tiandao_observe = {
        "turn": 3, "read_only": True,
        "decisions": dict(decisions or {}),
        "distributions": {},
        "strengths": ({} if strength is None else {"waive_arrears": strength}),
    }
    return st


def test_ratio_defaults_zero():
    """无观测副本 / 无强度 ⇒ 0.0（不蠲免，与改前 False 路径一致）。"""
    from core.settlement_finance import _arrears_waiver_ratio

    assert _arrears_waiver_ratio(_S()) == 0.0
    assert _arrears_waiver_ratio(_obs(_S())) == 0.0


def test_ratio_is_continuous_in_strength():
    """同 gate 通过、强度不同 ⇒ ratio 不同且单调（0.6 与 0.9 的强度 ⇒ 0.2 / 0.8）。"""
    from core.settlement_finance import _arrears_waiver_ratio

    lo = _arrears_waiver_ratio(_obs(_S(), 0.6))     # (0.6-0.5)/0.5 = 0.2
    hi = _arrears_waiver_ratio(_obs(_S(), 0.9))     # (0.9-0.5)/0.5 = 0.8
    assert 0.0 < lo < hi <= 1.0
    assert abs(lo - 0.2) < 1e-9 and abs(hi - 0.8) < 1e-9


def test_ratio_zero_at_or_below_threshold():
    from core.settlement_finance import _arrears_waiver_ratio

    for p in (0.0, 0.25, 0.4999, 0.5):
        assert _arrears_waiver_ratio(_obs(_S(), p)) == 0.0, p


def test_settlement_writeoff_scales_with_strength():
    """结算级：核销额随强度单调递增；强档核销多于弱档。"""
    from core.commands import new_game
    from core.settlement_finance import _settle_finance

    def run(strength):
        s = new_game("史实")
        for p in s.prefectures.values():
            p["pops"]["农"]["欠税"] = 1_000_000
        before = sum(int(p["pops"]["农"].get("欠税", 0) or 0)
                     for p in s.prefectures.values())
        s._tiandao_observe = {"turn": 3, "read_only": True, "decisions": {},
                              "distributions": {},
                              "strengths": {"waive_arrears": strength}}
        log = []
        _settle_finance(s, log)
        after = sum(int(p["pops"]["农"].get("欠税", 0) or 0)
                    for p in s.prefectures.values())
        return before - after, log

    weak, _ = run(0.6)
    strong, log_strong = run(0.9)
    assert strong > weak > 0, (weak, strong)
    assert any("蠲免" in line for line in log_strong)
