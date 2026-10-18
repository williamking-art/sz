# -*- coding: utf-8 -*-
"""质量放行门 · 载具级矩阵与**效果词条驱动**的科技修正（2026-10-18）。

用户：「这个矩阵没考虑载具的」「而且没有考虑科技进步」「不用限定接口，玩家会自创科技的」。

设计：载具表显式化（既有系数=基准载具系数）；科技修正走**效果词条**——
官方节点与玩家自创节点（`state.tech_registry`）只要声明白名单里的 `transport_*` 键就自动生效，
程序只按 `TRANSPORT_EFFECT_CAPS` 封顶，**不绑节点 id**。

本门钉住：
1. 载具表：每路网恰一个 baseline，且 baseline 系数 = 既有矩阵常量；
2. 效果词条：白名单登记完整、聚合只取已解锁/active 节点、未登记键忽略；
3. 封顶生效；无词条 ⇒ 参数原样（缺失≠0）；
4. 反例自证：注册节点停用后不生效。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_constants import (  # noqa: E402
    TRANSIT_LABOR_PER_STONE, TRANSIT_RATION_PER_LABOR_DAY, TRANSPORT_CARRIERS,
    TRANSPORT_EFFECT_CAPS)
from core.foundation.registries import TECH_EFFECT_WHITELIST  # noqa: E402
from core.transport import (  # noqa: E402
    baseline_carrier, carrier_labor, carrier_params, carrier_ration, carriers_for,
    transport_effect_sources, transport_effects)

MODES = ("waterway", "maritime", "overland", "post")


def test_each_mode_has_one_baseline_carrier():
    for mode in MODES:
        cs = carriers_for(mode)
        assert cs, f"{mode} 无载具"
        bases = [c for c in cs if c.get("baseline")]
        assert len(bases) == 1, f"{mode} baseline 必须恰一个"
        for c in cs:
            assert float(c.get("load") or 0) > 0, c
            assert float(c.get("km_per_day") or 0) > 0, c
            assert 0 < float(c.get("labor_per_stone") or 0) <= 2, c


def test_baseline_matches_existing_matrix_constants():
    for mode in MODES:
        b = baseline_carrier(mode)
        assert abs(float(b["labor_per_stone"]) - float(TRANSIT_LABOR_PER_STONE[mode])) < 1e-9
        assert abs(float(b["ration_per_labor_day"]) - float(TRANSIT_RATION_PER_LABOR_DAY[mode])) < 1e-9


def test_labor_and_ration_scale_with_cargo():
    b = baseline_carrier("waterway")
    assert carrier_labor(1000, b) == 50
    assert abs(carrier_ration(1000, b, 30) - 50 * 0.005 * 30) < 1e-9
    assert carrier_labor(0, b) == 0


def test_effect_keys_are_whitelisted():
    for key in TRANSPORT_EFFECT_CAPS:
        assert key in TECH_EFFECT_WHITELIST, f"{key} 未进科技效果白名单（玩家自创科技无法声明）"


def test_no_effects_means_unchanged():
    from core.commands import new_game

    s = new_game()
    s.tech_registry = {}
    b = baseline_carrier("waterway")
    p = carrier_params(s, "waterway", b)
    assert abs(p["km_per_day"] - float(b["km_per_day"])) < 1e-9, p
    assert abs(p["load"] - float(b["load"])) < 1e-9, p
    assert abs(p["labor_per_stone"] - float(b["labor_per_stone"])) < 1e-9, p


def test_player_created_tech_counts():
    """玩家自创科技（tech_registry）声明 transport_* 即生效——这是开放接口。"""
    from core.commands import new_game

    s = new_game()
    s.tech_registry = {
        "p_bigship": {"active": True, "effect": {"transport_water_speed": 0.12,
                                               "transport_labor_save": 0.05}},
    }
    eff = transport_effects(s)
    assert abs(eff["transport_water_speed"] - 0.12) < 1e-9, eff
    b = baseline_carrier("waterway")
    p = carrier_params(s, "waterway", b)
    assert p["km_per_day"] > float(b["km_per_day"])
    assert p["labor_per_stone"] < float(b["labor_per_stone"])


def test_inactive_node_does_not_count():
    from core.commands import new_game

    s = new_game()
    s.tech_registry = {"p_dead": {"active": False, "effect": {"transport_water_speed": 0.2}}}
    assert transport_effects(s) == {}


def test_unknown_keys_are_ignored():
    from core.commands import new_game

    s = new_game()
    s.tech_registry = {"p_weird": {"active": True, "effect": {"teleport": 5.0}}}
    assert transport_effects(s) == {}


def test_caps_apply():
    from core.commands import new_game

    s = new_game()
    s.tech_registry = {"p_absurd": {"active": True, "effect": {"transport_water_speed": 99.0}}}
    eff = transport_effects(s)
    assert eff["transport_water_speed"] == TRANSPORT_EFFECT_CAPS["transport_water_speed"]

def test_multiple_sources_sum():
    """科技与国策都是**复数**：多条同时生效时求和（不是覆盖）。"""
    from core.commands import new_game

    s = new_game()
    s.tech_registry = {
        "p_a": {"active": True, "effect": {"transport_water_speed": 0.08}},
        "p_b": {"active": True, "effect": {"transport_water_speed": 0.05,
                                          "transport_water_load": 0.10}},
    }
    s.active_decrees = [
        {"title": "兴漕运", "effects": {"transport_water_speed": 0.04}},
        {"title": "修闸堰", "effects": {"transport_water_speed": 0.03}},
    ]
    eff = transport_effects(s)
    assert abs(eff["transport_water_speed"] - 0.20) < 1e-9, eff
    assert abs(eff["transport_water_load"] - 0.10) < 1e-9, eff
    rows = transport_effect_sources(s)
    assert sum(1 for r in rows if r["source_type"] == "tech_player") == 3
    assert sum(1 for r in rows if r["source_type"] == "decree") == 2


def test_sum_is_capped_not_per_source():
    """封顶作用于**合计**：三条各 0.2 合计 0.6 ⇒ 压到 cap。"""
    from core.commands import new_game

    s = new_game()
    s.tech_registry = {
        f"p_{i}": {"active": True, "effect": {"transport_water_speed": 0.2}}
        for i in range(3)
    }
    assert transport_effects(s)["transport_water_speed"] == TRANSPORT_EFFECT_CAPS["transport_water_speed"]


def test_inactive_decree_or_node_not_counted():
    from core.commands import new_game

    s = new_game()
    s.tech_registry = {"p_off": {"active": False, "effect": {"transport_water_speed": 0.2}}}
    s.active_decrees = [{"title": "空诏", "effects": {}}]
    assert transport_effects(s) == {}
