# -*- coding: utf-8 -*-
"""建筑跟随科技测试（用户指示）：科技-建筑映射 / 升级上限 / 反馈科技 / 史实锚。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import TECH_BUILDING_MAP  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.era_mechanic import (  # noqa: E402
    building_unlocked, building_level_cap, tech_build_bonus,
)


def _new_state():
    return GameState("史实")


def test_tech_building_map_anchors():
    """科技-建筑映射（史实锚）：三舍法→学校、火药→火器作坊、水利→水利、市舶法→市舶司、冶铁→铁作。"""
    assert TECH_BUILDING_MAP["hydraulics"] == ("水利", 30)
    assert TECH_BUILDING_MAP["gunpowder"] == ("火器作坊", 30)
    assert TECH_BUILDING_MAP["iron"] == ("铁作", 30)
    assert TECH_BUILDING_MAP["school_three_halls"] == ("学校", 40)
    assert TECH_BUILDING_MAP["maritime_law"] == ("市舶司", 40)


def test_building_unlocked_by_tech():
    """科技没研出 → 建筑类型不可建；研出 → 解锁；基础建筑恒可建。"""
    s = _new_state()
    # 基础建筑恒可建
    assert building_unlocked(s, "农田") is True
    assert building_unlocked(s, "常平仓") is True
    # 火药 20（<30）→ 火器作坊不可建
    s.tech["gunpowder"] = 20
    assert building_unlocked(s, "火器作坊") is False
    s.tech["gunpowder"] = 50
    assert building_unlocked(s, "火器作坊") is True
    # 三舍法（level）→ 学校
    s.tech["level"] = 30
    assert building_unlocked(s, "学校") is False
    s.tech["level"] = 50
    assert building_unlocked(s, "学校") is True


def test_building_level_cap_by_tech():
    """科技升级上限：Lv 上限 = f(科技等级)（level 每 20 → +1，clamp 1~5）。"""
    s = _new_state()
    s.tech["level"] = 10
    assert building_level_cap(s, "水利") == 1
    s.tech["level"] = 50
    assert building_level_cap(s, "水利") == 3
    s.tech["level"] = 100
    assert building_level_cap(s, "水利") == 5
    s.tech["level"] = 0
    assert building_level_cap(s, "水利") == 1


def test_building_feedback_tech():
    """建筑反馈科技：学校/书院 → 科技研发加速（tech level 加成）。"""
    s = _new_state()
    s.projects = {"s1": {"type": "学校", "level": 2, "name": "州学"}}
    bonus = tech_build_bonus(s)
    assert abs(bonus - 0.10) < 1e-9   # 2 级 ×0.05
    s.projects["s2"] = {"type": "书院", "level": 3, "name": "书院"}
    assert abs(tech_build_bonus(s) - 0.25) < 1e-9
