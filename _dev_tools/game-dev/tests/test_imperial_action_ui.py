# -*- coding: utf-8 -*-
"""T8 皇帝行动全矩阵 UI 数据一致性测试（UI 渲染依赖的常量结构校验）。

覆盖：
  1) UI 效果键中文名映射覆盖矩阵全部 base_effects 键（防「预期」预览漏键）；
  2) 旧 4 固定动作 → 宫里·公开 矩阵白名单映射合法（旧面板兼容）；
  3) 约束字段齐全性：时代门槛/微服限次/准备期/距离核算 的触发字段与位置合法。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)
sys.path.insert(0, os.path.join(_GAME_ROOT, "tests"))

from content.data import (  # noqa: E402
    IMPERIAL_ACTION_MATRIX, IMPERIAL_LOCATIONS, IMPERIAL_MODES,
    LEGACY_PERSONAL_ACTION_MAP, PERSONAL_ACTIONS,
)


def _effect_names_map():
    """UI 效果键中文名映射（与 ui/panels_economy.py._IMPERIAL_EFFECT_NAMES 同源快照）。"""
    return {
        "prestige": "威望", "population_satisfaction": "民心", "emperor_health": "健康",
        "pleasure_leaning": "心情", "art_mastery": "艺术造诣", "taoism_leaning": "道门倾向",
        "bandwidth_bonus": "圣旨额度",
    }


def test_effect_names_cover_matrix():
    """UI 效果键中文名覆盖矩阵全部 base_effects 键（faction_change 单独处理）。"""
    names = _effect_names_map()
    for loc in IMPERIAL_LOCATIONS:
        for mode in IMPERIAL_MODES:
            for action, cell in IMPERIAL_ACTION_MATRIX[loc][mode].items():
                for k in (cell.get("base_effects") or {}):
                    if k == "faction_change":
                        continue  # 派系单独渲染
                    assert k in names, f"{loc}.{mode}.{action} 效果键 {k} 缺 UI 中文名"


def test_micro_once_only_in_imperial_capital_micro():
    """微服每月 1 次（micro_once）只出现在 京城·微服 格（UI 置灰依据）。"""
    for loc in IMPERIAL_LOCATIONS:
        for mode in IMPERIAL_MODES:
            for action, cell in IMPERIAL_ACTION_MATRIX[loc][mode].items():
                if cell.get("micro_once"):
                    assert (loc, mode) == ("京城", "微服"), \
                        f"{loc}.{mode}.{action} micro_once 应仅在京城·微服"
                if cell.get("micro_once") and mode == "微服":
                    assert cell.get("fund") == "imperial_treasury", \
                        f"微服开销应走内帑：{loc}.{action}"


def test_prep_only_outbound_public():
    """准备期（prep）只在 出京·公开；且带宽占用（bandwidth_cost）同在出京公开。"""
    for loc in IMPERIAL_LOCATIONS:
        for mode in IMPERIAL_MODES:
            for action, cell in IMPERIAL_ACTION_MATRIX[loc][mode].items():
                if cell.get("prep"):
                    assert (loc, mode) == ("出京", "公开"), \
                        f"准备期应仅在出京公开：{loc}.{mode}.{action}"
                if cell.get("bandwidth_cost"):
                    assert (loc, mode) == ("出京", "公开"), \
                        f"带宽占用应仅在出京公开：{loc}.{mode}.{action}"


def test_distance_only_outbound_micro():
    """距离核算（distance）只在 出京·微服（UI 目标路输入框显示依据）。"""
    for loc in IMPERIAL_LOCATIONS:
        for mode in IMPERIAL_MODES:
            for action, cell in IMPERIAL_ACTION_MATRIX[loc][mode].items():
                if cell.get("distance"):
                    assert (loc, mode) == ("出京", "微服"), \
                        f"距离核算应仅在出京微服：{loc}.{mode}.{action}"


def test_legacy_map_inside_palace_public():
    """旧 4 固定动作全部映射到 宫里·公开 矩阵白名单（旧面板兼容不越格）。"""
    palace_public = set(IMPERIAL_ACTION_MATRIX["宫里"]["公开"].keys())
    for name in PERSONAL_ACTIONS:
        mapped = LEGACY_PERSONAL_ACTION_MAP.get(name)
        assert mapped, f"旧行动 {name} 缺矩阵映射"
        assert mapped in palace_public, f"旧行动 {name} → {mapped} 不在宫里·公开白名单"
