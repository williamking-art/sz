# -*- coding: utf-8 -*-
"""田赋征管宽严 → 应征额（2026-10-22 审查 B1 后重写：**概率连续**，不再是档位表）。

改前（旧契约）：`strict ⇒ ×1.03 / lenient ⇒ ×0.97`（argmax 查表，违反
`core/ai/README.md` 契约第 14 条）。
改后：`factor = 1 + 0.03 × (p_strict − p_lenient) × jitter`，扰子**只乘增量**，
故 `net == 0`（多空均衡/无信号）时**精确** 1.0（不吃扰子）；分布缺失亦 1.0。

本文件只钉「消费者真的按概率咬住 + 缺失中性 + 单调」，细粒度契约在
`test_tiandao_effects_probabilistic_fiscal.py`。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    turn = 3


def _obs(st, dist=None, decisions=None):
    st._tiandao_observe = {
        "turn": 3, "read_only": True,
        "decisions": dict(decisions or {}),
        "distributions": ({"tax_stance": dist} if dist else {}),
        "strengths": {},
    }
    return st


def test_missing_distribution_is_neutral():
    """无观测副本 / 无分布 ⇒ 恰好 1.0（与改前"无记录"路径一致）。"""
    from core.settlement_finance import _tax_stance_factor

    assert _tax_stance_factor(_S()) == 1.0
    assert _tax_stance_factor(_obs(_S(), dist=None)) == 1.0


def test_zero_net_is_exactly_one_across_turns():
    """均衡分布（net=0）⇒ 精确 1.0（**不吃天意扰子**；这是 D2 的验收点）。"""
    from core.settlement_finance import _tax_stance_factor

    for turn in range(0, 13):
        st = _obs(_S(), dist={"strict": 0.4, "moderate": 0.2, "lenient": 0.4})
        st.turn = turn
        assert _tax_stance_factor(st) == 1.0, turn


def test_factor_is_monotone_in_probability_spread():
    """strict 概率越高、lenient 越低 ⇒ 因子越大；反向则越小（连续，非查表）。"""
    from core.settlement_finance import _tax_stance_factor

    strong = _tax_stance_factor(_obs(_S(), dist={"strict": 0.9, "moderate": 0.08,
                                                 "lenient": 0.02}))
    mild = _tax_stance_factor(_obs(_S(), dist={"strict": 0.5, "moderate": 0.4,
                                               "lenient": 0.1}))
    flat = _tax_stance_factor(_obs(_S(), dist={"strict": 0.34, "moderate": 0.33,
                                               "lenient": 0.33}))
    lenient = _tax_stance_factor(_obs(_S(), dist={"strict": 0.02, "moderate": 0.08,
                                                  "lenient": 0.9}))
    assert strong > mild > flat > lenient, (strong, mild, flat, lenient)
    # 端点在量级上仍接近旧表（±3%），但幅度随概率差**连续**变化
    assert 1.0 < strong <= 1.03 + 1e-9
    assert 0.97 - 1e-9 <= lenient < 1.0


def test_same_argmax_different_spread_differs():
    """同为 strict 占优，概率差不同 ⇒ 因子不同（B1 的核心：同档不同概率）。"""
    from core.settlement_finance import _tax_stance_factor

    a = _tax_stance_factor(_obs(_S(), dist={"strict": 0.5, "moderate": 0.3,
                                             "lenient": 0.2}))
    b = _tax_stance_factor(_obs(_S(), dist={"strict": 0.9, "moderate": 0.09,
                                             "lenient": 0.01}))
    assert b > a > 1.0


def test_land_tax_assessed_is_monotone_in_stance_probability():
    """结算级：应征额随 strict 概率单调（旧测试断言 1.03>1.0>0.97 的档位序，现改为概率序）。"""
    from core.commands import new_game
    from core.settlement_finance import _settle_land_tax_color

    def run(dist):
        s = new_game("史实")
        s._tiandao_observe = {"turn": 3, "read_only": True, "decisions": {},
                              "distributions": {"tax_stance": dist}, "strengths": {}}
        return _settle_land_tax_color(s, [])

    strict = run({"strict": 0.9, "moderate": 0.08, "lenient": 0.02})
    neutral = run({"strict": 0.34, "moderate": 0.33, "lenient": 0.33})
    lenient = run({"strict": 0.02, "moderate": 0.08, "lenient": 0.9})
    assert strict["assessed"] > neutral["assessed"] > lenient["assessed"], (
        strict["assessed"], neutral["assessed"], lenient["assessed"])
