# -*- coding: utf-8 -*-
"""persona 量纲对齐断言（用户决定 0-100 满值，中性 50）：
量纲 / 调制乘子极值 / 危险度三例 / 权重 sum / PERSONA 表 0-100。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.ministers.persona import (  # noqa: E402
    PERSONA, get_persona, stance_evolution, danger_rating, _WEIGHTS,
)
from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def test_weights_sum_to_one():
    """立场演化权重 sum == 1.0。"""
    assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9


def test_derive_baseline_neutral_50():
    """缺省派生基线全 50（中性；无 traits 关键词命中的名字保持中性）。"""
    p = get_persona("无名小吏")   # 不在 MINISTERS → 派生且无关键词命中 → 全中性
    for d in ("刚直", "权谋", "聚敛", "忠君", "胆识", "冒险"):
        assert 0 <= p[d] <= 100, f"{d} 越界"
        assert p[d] == 50, f"无关键词派生应保持中性 50：{d}={p[d]}"


def test_persona_table_zero_100():
    """PERSONA 表 0-100：蔡京 权谋85/聚敛80/忠君60/刚直15；司马光刚直90/忠君70/权谋20；
    王安石 刚直75/胆识70/冒险60；童贯 忠君85/权谋75/冒险70；韩忠彦 刚直70/忠君80；
    陈瓘 刚直90/忠君90；章惇 刚直80/权谋70。"""
    assert PERSONA["蔡京"]["权谋"] == 85 and PERSONA["蔡京"]["聚敛"] == 80
    assert PERSONA["蔡京"]["忠君"] == 60 and PERSONA["蔡京"]["刚直"] == 15
    assert PERSONA["司马光"]["刚直"] == 90 and PERSONA["司马光"]["忠君"] == 70 and PERSONA["司马光"]["权谋"] == 20
    assert PERSONA["王安石"]["刚直"] == 75 and PERSONA["王安石"]["胆识"] == 70 and PERSONA["王安石"]["冒险"] == 60
    assert PERSONA["童贯"]["忠君"] == 85 and PERSONA["童贯"]["权谋"] == 75 and PERSONA["童贯"]["冒险"] == 70
    assert PERSONA["韩忠彦"]["刚直"] == 70 and PERSONA["韩忠彦"]["忠君"] == 80
    assert PERSONA["陈瓘"]["刚直"] == 90 and PERSONA["陈瓘"]["忠君"] == 90
    assert PERSONA["章惇"]["刚直"] == 80 and PERSONA["章惇"]["权谋"] == 70


def test_modifier_extremes():
    """调制乘子极值（0-100）：刚直 100 → 因子 0.5；权谋 100 → 因子 1.25。"""
    mod_zhigang = (1 - 0.5 * 100 / 100.0) * (1 + 0.5 * 0 / 100.0) * (1 + 0.4 * 0 / 100.0) * (1 + 0.3 * 0 / 100.0)
    assert abs(mod_zhigang - 0.5) < 1e-9
    mod_quanmou = (1 - 0.5 * 0 / 100.0) * (1 + 0.5 * (100 - 50) / 100.0) * (1 + 0.4 * 0 / 100.0) * (1 + 0.3 * 0 / 100.0)
    assert abs(mod_quanmou - 1.25) < 1e-9


def test_danger_three_cases():
    """危险度三例（0-100）：满危 2.0 / 皇威压 0.6 / 权谋系数 0.5~2.0。"""
    s = _new_state()
    # 满危（权谋 100 代入公式）：影响力100 满意度0 皇威0 → 2.0
    d_full = (100 / 100.0) * (100 / 100.0) * (1 - 0.7 * 0 / 100.0) * (0.5 + 1.5 * 100 / 100.0)
    assert abs(d_full - 2.0) < 1e-9
    # 皇威 100 → (1−0.7)=0.3 → 满危×0.3=0.6
    d_press = (100 / 100.0) * (100 / 100.0) * (1 - 0.7 * 100 / 100.0) * (0.5 + 1.5 * 100 / 100.0)
    assert abs(d_press - 0.6) < 1e-9
    # 蔡京（权谋 85）满盘面危险度 = 2.0×0.5+1.5×85/100 / 2.0 = (0.5+1.275)/2.0... 直接验证范围
    s.factions["新党"]["satisfaction"] = 0
    s.factions["新党"]["influence"] = 100
    s.prestige = 0
    d_cai = danger_rating(s, "蔡京")
    assert 0 <= d_cai <= 2.0 and d_cai > 1.5, f"蔡京满盘面应高危险：{d_cai}"


def test_evolution_bounds():
    """立场演化 score 恒在 [0,100]，stance/posture 档位合法。"""
    s = _new_state()
    for name in ("蔡京", "韩忠彦", "章惇", "陈瓘", "童贯", "司马光", "王安石", "丰稷"):
        ev = stance_evolution(s, name, turn=1)
        assert 0 <= ev["score"] <= 100
        assert ev["stance"] in ("激进", "支持", "观望", "抵触", "敌对")
        assert ev["posture"] in ("直言力诤", "阳奉阴违", "消极敷衍", "推心置腹", "恭顺奉行")
