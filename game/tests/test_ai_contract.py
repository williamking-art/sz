# -*- coding: utf-8 -*-
"""AI 契约回归测试：档位换算 / 效果字典 / 白名单。"""
from ai.client_utils import (
    tier_to_value, effects_to_dict, _EFFECT_WHITELIST, _normalize_decree_effects,
)


def test_tier_to_value_basic():
    """档位 × 基准 × 皇威乘数。"""
    assert tier_to_value("prestige", "中", 1.0) == 4      # 4×1.0×1.0
    assert tier_to_value("prestige", "大", 1.0) == 7      # 4×1.8=7.2→round 7
    assert tier_to_value("prestige", "微", 1.0) == 1      # 4×0.25=1.0


def test_tier_to_value_cap():
    """单项封顶。"""
    assert tier_to_value("treasury", "大", 2.0) == 2_880_000   # 800000×1.8×2 未超 300 万
    assert tier_to_value("treasury", "大", 3.0) == 3_000_000   # 432 万 → 封顶 300 万


def test_tier_to_value_commerce_tax():
    """工商征率是设定值（档位→税率），非增量。"""
    assert tier_to_value("commerce_tax", "中", 1.0) == 0.20
    assert tier_to_value("commerce_tax", "大", 1.0) == 0.30
    assert tier_to_value("commerce_tax", "无", 1.0) == 0.05


def test_tier_to_value_unknown_dim():
    """未知维度返回 0，不抛异常。"""
    assert tier_to_value("nonexistent", "中", 1.0) == 0


def test_effects_to_dict_basic():
    eff = [{"dim": "prestige", "tier": "中"}]
    assert effects_to_dict(eff, 1.0) == {"prestige": 4}


def test_effects_to_dict_faction_change():
    """faction_change 用 prestige 档位换算各派系数值。"""
    eff = [{"dim": "faction_change", "value": {"旧党": "中", "新党": "小"}}]
    out = effects_to_dict(eff, 1.0)
    assert out["faction_change"]["旧党"] == 4   # 中档
    assert out["faction_change"]["新党"] == 2   # 小档 4×0.5


def test_effects_to_dict_commerce_tax_precise():
    """commerce_tax 优先用精确 value，无 value 回退档位。"""
    eff = [{"dim": "commerce_tax", "value": 0.18}]
    assert effects_to_dict(eff, 1.0)["commerce_tax"] == 0.18
    eff2 = [{"dim": "commerce_tax", "tier": "大"}]
    assert effects_to_dict(eff2, 1.0)["commerce_tax"] == 0.30


def test_effect_whitelist_17_keys():
    """白名单与 _TIER_BASE 对齐（17 维度）。"""
    assert len(_EFFECT_WHITELIST) == 17
    for k in ("prestige", "treasury", "land_survey", "hoard", "commerce_tax", "reform"):
        assert k in _EFFECT_WHITELIST


def test_normalize_decree_effects():
    """归一化：只留白名单键 + 强制数值类型，非法键/非法值丢弃。"""
    out = _normalize_decree_effects({"prestige": "4", "bad_key": "999", "treasury": "abc"})
    assert out == {"prestige": 4.0}
