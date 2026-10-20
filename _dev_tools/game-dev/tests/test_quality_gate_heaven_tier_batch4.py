# -*- coding: utf-8 -*-
"""质量放行门 · 天道档位化 batch4：诏令生效月数（2026-10-20）。

用户裁定：「多方面因素影响，天道，主持官员能力，皇威，后续跟进等等」。

钉住：
1. **纯函数**（不耗随机数）；同一输入必得同一月数；
2. 天道节奏 速/常/缓 → 基础 6/12/18（`_decree_ai.pace` 或任务 priority 推导）；
3. 能力：<40 ×1.25 / 40–69 ×1.00 / ≥70 ×0.80，未指定 ⇒ 1.00 且注明原因；
4. 皇威：<40 ×1.20 / 40–79 ×1.00 / ≥80 ×0.85；
5. 跟进：0 ×1.10 / 1 ×0.95 / ≥2 ×0.85；
6. 月数夹在 3–36；breakdown 记录每项系数与来源；
7. 缺天道档 ⇒ 常（12 月）且 source 明示缺档。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.politics.decree_duration import (  # noqa: E402
    MONTHS_MAX, MONTHS_MIN, resolve_decree_duration)


class _S:
    def __init__(self, prestige=55, pace=None, priorities=None):
        self.prestige = prestige
        if pace:
            self._decree_ai = {"pace": pace}
        if priorities:
            self._decree_execute_ai = {"tasks": [{"priority": p} for p in priorities]}


def test_deterministic_no_random():
    s = _S()
    a = resolve_decree_duration(s, ability=55, followup=1)
    b = resolve_decree_duration(s, ability=55, followup=1)
    assert a == b


def test_pace_mapping():
    assert resolve_decree_duration(_S(pace="速"))["base"] == 6
    assert resolve_decree_duration(_S(pace="常"))["base"] == 12
    assert resolve_decree_duration(_S(pace="缓"))["base"] == 18


def test_priority_derives_pace():
    got = resolve_decree_duration(_S(priorities=["低", "高"]))
    assert got["pace"] == "速" and "任务优先级" in got["source"]


def test_ability_effect():
    low = resolve_decree_duration(_S(), ability=20)["breakdown"]["ability"]["mult"]
    mid = resolve_decree_duration(_S(), ability=55)["breakdown"]["ability"]["mult"]
    high = resolve_decree_duration(_S(), ability=85)["breakdown"]["ability"]["mult"]
    assert (low, mid, high) == (1.25, 1.00, 0.80)


def test_prestige_effect():
    weak = resolve_decree_duration(_S(prestige=30))["breakdown"]["prestige"]["mult"]
    mid = resolve_decree_duration(_S(prestige=60))["breakdown"]["prestige"]["mult"]
    strong = resolve_decree_duration(_S(prestige=90))["breakdown"]["prestige"]["mult"]
    assert (weak, mid, strong) == (1.20, 1.00, 0.85)


def test_followup_effect():
    assert resolve_decree_duration(_S(), followup=0)["breakdown"]["followup"]["mult"] == 1.10
    assert resolve_decree_duration(_S(), followup=1)["breakdown"]["followup"]["mult"] == 0.95
    assert resolve_decree_duration(_S(), followup=3)["breakdown"]["followup"]["mult"] == 0.85


def test_months_clamped():
    fast = resolve_decree_duration(_S(prestige=99, pace="速"), ability=99, followup=3)
    slow = resolve_decree_duration(_S(prestige=10, pace="缓"), ability=10, followup=0)
    assert fast["months"] >= MONTHS_MIN
    assert slow["months"] <= MONTHS_MAX


def test_missing_ai_defaults_and_marks_source():
    got = resolve_decree_duration(_S())
    assert got["pace"] == "常" and got["base"] == 12
    assert "缺档" in got["source"]


def test_unset_ability_is_documented():
    got = resolve_decree_duration(_S(), ability=None)
    assert got["breakdown"]["ability"]["mult"] == 1.00
    assert "未指定" in got["breakdown"]["ability"]["note"]

def test_attitude_levels_and_effect():
    """天道判断「谁敢拖」：态度档位直接影响月数。"""
    from core.domains.politics.decree_duration import ATTITUDE_MULT, ATTITUDE_LEVELS

    assert ATTITUDE_LEVELS == ("奉行", "依违", "阳奉阴违", "拖延")
    assert ATTITUDE_MULT == {"奉行": 1.00, "依违": 1.15, "阳奉阴违": 1.35, "拖延": 1.60}


def test_attitude_slot_changes_months():
    """同局势下「奉行」与「拖延」月数不同（AI 判断空间生效）。"""

    class _Fast(_S):
        pass

    s1 = _Fast(prestige=70, pace="常")
    s1._decree_ai = {"pace": "常", "execution_attitude": "奉行"}
    s2 = _Fast(prestige=70, pace="常")
    s2._decree_ai = {"pace": "常", "execution_attitude": "拖延",
                     "attitude_note": "百官阴奉阳违，敢拖者众"}
    d1 = resolve_decree_duration(s1, ability=60, followup=0)
    d2 = resolve_decree_duration(s2, ability=60, followup=0)
    assert d1["months"] < d2["months"], (d1["months"], d2["months"])
    assert d2["attitude"]["level"] == "拖延"
    assert "敢拖者众" in d2["attitude"]["note"]


def test_attitude_from_execute_contract_and_provider():
    from core.domains.politics import decree_duration as dd

    s = _S(prestige=70, pace="常")
    s._decree_execute_ai = {"execution_attitude": "阳奉阴违", "attitude_note": "六部推诿"}
    got = resolve_decree_duration(s, ability=60, followup=0)
    assert got["attitude"]["level"] == "阳奉阴违"
    assert "执行契约" in got["attitude"]["source"]

    s2 = _S(prestige=70, pace="常")
    dd.register_attitude_provider(lambda st, kind, bene: {"execution_attitude": "依违", "note": "provider"})
    try:
        got2 = resolve_decree_duration(s2, ability=60, followup=0)
        assert got2["attitude"]["level"] == "依违"
        assert "provider" in got2["attitude"]["source"]
    finally:
        dd._ATTITUDE_PROVIDERS.clear()


def test_attitude_missing_is_neutral_and_marked():
    got = resolve_decree_duration(_S(), ability=60, followup=0)
    assert got["attitude"]["mult"] == 1.00
    assert got["attitude"]["source"] == "缺档"
    assert "未判" in got["attitude"]["note"]


def test_attitude_invalid_falls_back():
    s = _S()
    s._decree_ai = {"execution_attitude": "抗旨不遵"}
    got = resolve_decree_duration(s, ability=60, followup=0)
    assert got["attitude"]["mult"] == 1.00

def test_weights_declared_and_sum_to_one():
    """权重必须显式且归一（否则无法解释主次）。"""
    from core.domains.politics.decree_duration import FACTOR_WEIGHTS

    assert set(FACTOR_WEIGHTS) == {"attitude", "ability", "prestige", "followup"}
    assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 1e-9


def test_weighted_geometric_mean_is_bounded():
    """最坏因素同时出现也不爆炸：加权几何平均 + 总乘数夹取双保险。"""
    from core.domains.politics.decree_duration import MULT_MAX, MULT_MIN

    s = _S(prestige=10, pace="缓")
    s._decree_ai = {"pace": "缓", "execution_attitude": "拖延"}
    worst = resolve_decree_duration(s, ability=10, followup=0)
    assert MULT_MIN <= worst["breakdown"]["weighted_mult"] <= MULT_MAX
    assert worst["months"] <= 36

    s2 = _S(prestige=99, pace="速")
    s2._decree_ai = {"pace": "速", "execution_attitude": "奉行"}
    best = resolve_decree_duration(s2, ability=99, followup=3)
    assert MULT_MIN <= best["breakdown"]["weighted_mult"] <= MULT_MAX
    assert best["months"] >= 3


def test_high_weight_factor_moves_more():
    """态度权重 0.40 > 跟进 0.15 ⇒ 同幅度变化，态度对月数影响更大。"""
    base = _S(prestige=70, pace="常")
    base._decree_ai = {"pace": "常", "execution_attitude": "奉行"}
    m0 = resolve_decree_duration(base, ability=60, followup=0)["months"]

    s_att = _S(prestige=70, pace="常")
    s_att._decree_ai = {"pace": "常", "execution_attitude": "拖延"}
    m_att = resolve_decree_duration(s_att, ability=60, followup=0)["months"]

    m_fol = resolve_decree_duration(base, ability=60, followup=3)["months"]
    assert abs(m_att - m0) > abs(m_fol - m0), (m0, m_att, m_fol)


def test_breakdown_reports_weights_and_mult():
    got = resolve_decree_duration(_S(), ability=60, followup=1)
    bd = got["breakdown"]
    assert "weighted_mult" in bd and isinstance(bd["weights"], dict)
    assert abs(sum(bd["weights"].values()) - 1.0) < 1e-9

def test_immediate_decree_is_one_turn():
    """加薪这类即时诏令：本回合生效（months=1），拖延**不**拖成长期。"""
    s = _S(prestige=70)
    s._decree_ai = {"pace": "缓", "execution_attitude": "拖延"}
    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=50, followup=0)
    assert got["timing"] == "immediate"
    assert got["months"] == 1, got["months"]
    assert got["execution_completion"] == 0.35


def test_immediate_奉行_full_completion():
    s = _S(prestige=70)
    s._decree_ai = {"pace": "常", "execution_attitude": "奉行"}
    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=50, followup=0)
    assert got["months"] == 1 and got["execution_completion"] == 1.0


def test_long_decree_keeps_months():
    """裁冗/省费属长期工程：月数仍按多因素算（不会被当成即时）。"""
    s = _S(prestige=70)
    s._decree_ai = {"pace": "常", "execution_attitude": "阳奉阴违"}
    got = resolve_decree_duration(s, decree_kind="reduce_office", ability=50, followup=0)
    assert got["timing"] == "long"
    assert got["months"] >= 6, got["months"]


def test_short_decree_bounded_1_to_3():
    s = _S(prestige=70)
    s._decree_ai = {"pace": "常", "execution_attitude": "奉行"}
    got = resolve_decree_duration(s, decree_kind="canal_dredge", ability=99, followup=3)
    assert got["timing"] == "short"
    assert 1 <= got["months"] <= 3


def test_unknown_kind_treated_as_long_with_reason():
    from core.domains.politics.decree_duration import classify_decree_timing

    timing, reason = classify_decree_timing("反间计")
    assert timing == "long" and "未知" in reason

def test_ai_can_escalate_immediate_to_long():
    """推演 AI 判断：加薪通常是即时，但朝局崩坏时可判为长期拉锯。"""
    s = _S(prestige=70)
    s._decree_ai = {"execution_timing": "长期", "timing_note": "朝议拉锯，拖而不办"}
    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=50, followup=0)
    assert got["timing"] == "long"
    assert got["timing_source"] == "天道"
    assert got["months"] >= 6, got["months"]
    assert "拉锯" in got["timing_reason"]


def test_ai_can_compress_long_to_immediate():
    s = _S(prestige=70)
    s._decree_ai = {"execution_timing": "即时", "timing_note": "圣威所至，一旬而办"}
    got = resolve_decree_duration(s, decree_kind="reduce_office", ability=50, followup=0)
    assert got["timing"] == "immediate" and got["months"] == 1


def test_missing_timing_falls_back_to_effect_table():
    s = _S(prestige=70)
    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=50, followup=0)
    assert got["timing"] == "immediate"
    assert "效果键" in got["timing_source"]


def test_timing_from_execute_contract_and_provider():
    from core.domains.politics import decree_duration as dd

    s = _S(prestige=70)
    s._decree_execute_ai = {"execution_timing": "短期"}
    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=50, followup=0)
    assert got["timing"] == "short" and "执行契约" in got["timing_source"]

    s2 = _S(prestige=70)
    dd.register_timing_provider(lambda st, kind: {"execution_timing": "长期", "note": "p"})
    try:
        got2 = resolve_decree_duration(s2, decree_kind="pay_reform", ability=50, followup=0)
        assert got2["timing"] == "long" and "provider" in got2["timing_source"]
    finally:
        dd._TIMING_PROVIDERS.clear()


def test_invalid_timing_falls_back():
    s = _S(prestige=70)
    s._decree_ai = {"execution_timing": "千年大计"}
    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=50, followup=0)
    assert got["timing"] == "immediate"
    assert "效果键" in got["timing_source"]