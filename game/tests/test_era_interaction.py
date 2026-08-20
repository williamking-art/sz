# -*- coding: utf-8 -*-
"""建筑-时代交互测试（言枢密方案）：era_state 五维 / 双向联动 / 记忆 / 时代叙事。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import ERA_DIMENSIONS, ERA_TREND_SHIFT  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.era_mechanic import (  # noqa: E402
    era_trend, era_migrate, settle_era_links, build_speed_mod,
    damage_buildings, record_building_memory, era_brief,
)


def _new_state():
    return GameState("史实")


def test_era_state_init_and_migrate():
    """era_state 五维初始 50；trend 兴/平/衰 程序定幅迁移（±10）clamp [0,100]。"""
    s = _new_state()
    assert set(s.era_state) == set(ERA_DIMENSIONS)
    assert all(v == 50 for v in s.era_state.values())
    assert ERA_TREND_SHIFT == {"兴": 10, "平": 0, "衰": -10}
    assert era_migrate(s.era_state, "economy_center", "兴") == 60
    assert era_migrate(s.era_state, "culture", "衰") == 40
    # clamp
    s.era_state["military"] = 95
    assert era_migrate(s.era_state, "military", "兴") == 100
    s.era_state["urban"] = 5
    assert era_migrate(s.era_state, "urban", "衰") == 0


def test_era_trend_words():
    """认知层档位词：≥70 兴 / 40-69 平 / <40 衰。"""
    s = _new_state()
    s.era_state["economy_center"] = 75
    s.era_state["culture"] = 50
    s.era_state["commerce"] = 30
    assert era_trend(s.era_state, "economy_center") == "兴"
    assert era_trend(s.era_state, "culture") == "平"
    assert era_trend(s.era_state, "commerce") == "衰"


def test_era_downlink_buildings():
    """下行联动：建筑累积到 era_state（水利→economy_center、学校→culture、军营→military）。"""
    s = _new_state()
    s.projects = {"p1": {"type": "水利", "level": 3, "name": "水利"},
                  "p2": {"type": "学校", "level": 2, "name": "学校"}}
    s.prefectures["河北路"]["buildings"] = {"军营": 2, "农田": 3}
    settle_era_links(s, [])
    assert s.era_state["economy_center"] >= 50 + 3 + 3   # 水利 3 + 农田 3
    assert s.era_state["culture"] >= 50 + 2              # 学校 2
    assert s.era_state["military"] >= 50 + 2             # 军营 2


def test_era_uplink_build_speed():
    """上行调制：国库充足+景气中/大 → ×1.3；国库紧张/钱荒 → ×0.7。"""
    s = _new_state()
    s.treasury = 5_000_000
    s._economy_ai = {"景气": "中"}
    assert build_speed_mod(s) == 1.3
    s.treasury = 100_000
    assert build_speed_mod(s) == 0.7
    s.treasury = 5_000_000
    s.coin["shortage"] = 0.7
    assert build_speed_mod(s) == 0.7


def test_era_damage_and_memory():
    """战乱毁损（level 降/移除）+ 记忆记录（building 实体 + 兴衰事件）。"""
    s = _new_state()
    s.prefectures["东京开封府"]["buildings"] = {"农田": 3, "商铺": 1}
    d = damage_buildings(s, [], reason="金兵南下")
    assert d == 2
    assert s.prefectures["东京开封府"]["buildings"] == {"农田": 2}
    assert "毁于金兵南下" in s.era_building_log[-1]["event"]
    # 记忆图谱
    record_building_memory(s, "水利", "河北路", "建于崇宁", turn=1)
    assert any(k.startswith("building_") for k in s.memory.entities)


def test_era_brief_and_roundtrip():
    """时代叙事（脱敏档位）+ 存档往返。"""
    s = _new_state()
    s.era_state["economy_center"] = 80
    brief = era_brief(s)
    assert "economy_center兴" in brief
    from core.save_load import save_game, load_game, _slot_path
    assert save_game(s, slot=4)
    s2 = load_game(4)
    assert s2 is not None
    assert s2.era_state["economy_center"] == 80
    if os.path.exists(_slot_path(4)):
        os.remove(_slot_path(4))
