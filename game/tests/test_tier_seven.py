# -*- coding: utf-8 -*-
"""档位词丰富测试（7 档 + 丰富表达归一映射）+ P2 事件闭集化。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import TIER_RANGE, TIER_ORDER, normalize_tier  # noqa: E402
from ai.client_utils import tier_to_value  # noqa: E402


def test_tier_range_seven():
    """TIER_RANGE 7 档：无0/微0.25/小0.5/中1.0/大1.5/巨2.0/极2.5。"""
    assert TIER_ORDER == ["无", "微", "小", "中", "大", "巨", "极"]
    assert TIER_RANGE == {"无": 0.0, "微": 0.25, "小": 0.5, "中": 1.0,
                          "大": 1.5, "巨": 2.0, "极": 2.5}


def test_normalize_tier_alias():
    """丰富表达归一映射：些许/微澜→微、稍/小波→小、明显/中浪→中、
    显著/大潮→大、剧烈/巨涛→巨、极端/海啸→极。"""
    cases = {
        "些许": "微", "微澜": "微", "略": "微",
        "稍": "小", "小波": "小", "微起": "小",
        "明显": "中", "中浪": "中", "可观": "中",
        "显著": "大", "大潮": "大", "猛烈": "大",
        "剧烈": "巨", "巨涛": "巨", "浩大": "巨",
        "极端": "极", "海啸": "极", "惊天": "极",
    }
    for word, expect in cases.items():
        assert normalize_tier(word) == expect, f"{word} → {expect}"
    assert normalize_tier("无") == "无" and normalize_tier("毫无") == "无"
    assert normalize_tier("古怪词") == "无"   # 未知词回「无」


def test_tier_to_value_new_tiers():
    """tier_to_value 支持巨/极 + 丰富表达归一。"""
    # prestige base 4：巨=4×2.0=8、极=4×2.5=10
    assert tier_to_value("prestige", "巨", 1.0) == 8
    assert tier_to_value("prestige", "极", 1.0) == 10
    assert tier_to_value("prestige", "海啸", 1.0) == 10


def test_normalize_in_effects_flow():
    """丰富表达归一贯穿换算（commerce_tax 巨/极 + 未知词回无）。"""
    assert tier_to_value("commerce_tax", "巨", 1.0) == 0.30
    assert tier_to_value("commerce_tax", "极", 1.0) == 0.35
    assert tier_to_value("prestige", "不知所谓", 1.0) == 0   # 回「无」→ 0
