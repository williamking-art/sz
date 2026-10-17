# -*- coding: utf-8 -*-
"""M317 维多利亚3风格生产方式（PM）与中性通用中间物架构测试。

验证：
1. 原料纠偏（瓷器=黏土+煤炭，火药=硝石+硫磺+木炭）；
2. 通用中性中间物（铁锭、钢锭、铜锭、木方、机械零件、布料、丝绸、皮革、纸张、火药）登记与价格守卫；
3. 建筑PM槽位（基础工艺、动力方式、所有权）读取与动态切换；
4. 水排水力与蒸汽动力前置条件守卫（地理水运与科技门控）；
5. 链式组装物料吞吐与加工增值计算。
"""
import sys

sys.path.insert(0, r"D:/codebuddy/sz/game")

from content.data import (
    FINISHED_DIMS,
    GOODS_DIMS,
    MATERIAL_PRICE_BASE,
    RAW_DIMS,
    WORKSHOP_RECIPES,
)
from core.domains.economy.production_methods import (
    NEUTRAL_INTERMEDIATES,
    PM_REGISTRY,
    calculate_building_throughput,
    can_switch_pm,
    get_building_pms,
    switch_pm,
)
from core.game_state import GameState


def test_raw_dims_rectification_and_neutral_intermediates():
    """验证火药、瓷器原料纠偏及通用中性中间物目录。"""
    # 1. 原料纠偏
    for dim in ("黏土", "煤炭", "木炭", "硝石", "硫磺"):
        assert dim in RAW_DIMS, f"纠偏原料 {dim} 必须在 RAW_DIMS 中"
        assert dim in MATERIAL_PRICE_BASE, f"纠偏原料 {dim} 必须有基准价"

    # 2. 瓷器与火药配方严格使用纠偏原料
    assert WORKSHOP_RECIPES["官窑瓷坊"]["recipe"] == {"黏土": 10000, "煤炭": 5000}
    assert WORKSHOP_RECIPES["火药局"]["recipe"] == {"硝石": 5000, "硫磺": 3000, "木炭": 2000}

    # 3. 十大通用中性中间物
    for inter in NEUTRAL_INTERMEDIATES:
        assert inter in FINISHED_DIMS, f"中性物 {inter} 必须在 FINISHED_DIMS 中"
        assert inter in GOODS_DIMS, f"中性物 {inter} 必须在 GOODS_DIMS 中"
        assert inter in MATERIAL_PRICE_BASE, f"中性物 {inter} 必须有基准价"


def test_pm_registry_integrity():
    """验证生产方式注册表完整性与槽位划分。"""
    assert len(PM_REGISTRY) >= 12
    categories = {pm.category for pm in PM_REGISTRY.values()}
    assert "base" in categories
    assert "power" in categories
    assert "ownership" in categories

    # 检查水排动力与蒸汽动力规格
    water_pm = PM_REGISTRY["pm_power_water"]
    assert water_pm.prereq_waterway is True
    assert water_pm.throughput_mult >= 2.0

    steam_pm = PM_REGISTRY["pm_power_steam"]
    assert steam_pm.prereq_tech == "steam_engine_unlocked"
    assert steam_pm.throughput_mult >= 5.0


def test_pm_switching_and_prerequisites():
    """验证建筑PM动态切换与前置条件（水运、科技）守卫。"""
    state = GameState()

    # 1. 读取默认配置
    pms = get_building_pms(state, "两浙路", "seat_hz", "冶铁工场")
    assert pms["base"] == "pm_smelting_coke"
    assert pms["power"] == "pm_power_manual"

    # 2. 在两浙路（水系强）切换水排水力机组：允许
    allowed, msg = can_switch_pm(state, "两浙路", "seat_hz", "冶铁工场", "pm_power_water")
    assert allowed is True
    ok = switch_pm(state, "两浙路", "seat_hz", "冶铁工场", "pm_power_water")
    assert ok is True

    # 验证切换后已生效
    pms_after = get_building_pms(state, "两浙路", "seat_hz", "冶铁工场")
    assert pms_after["power"] == "pm_power_water"

    # 3. 蒸汽动力未解锁科技前：拒绝切换
    state.steam_engine_unlocked = False
    allowed_steam, _ = can_switch_pm(state, "两浙路", "seat_hz", "冶铁工场", "pm_power_steam")
    assert allowed_steam is False

    # 解锁科技后：允许切换
    state.steam_engine_unlocked = True
    allowed_steam_ok, _ = can_switch_pm(state, "两浙路", "seat_hz", "冶铁工场", "pm_power_steam")
    assert allowed_steam_ok is True


def test_building_throughput_and_added_value():
    """验证建筑吞吐量计算与水力动力带来的产能跃升。"""
    state = GameState()

    # 人力冶铁工场
    res_manual = calculate_building_throughput(state, "两浙路", "seat_hz", "冶铁工场", scale=1.0)
    assert res_manual["net_value"] > 0
    outputs_manual = res_manual["outputs"]["铁锭"]

    # 切换为水力水排
    switch_pm(state, "两浙路", "seat_hz", "冶铁工场", "pm_power_water")
    res_water = calculate_building_throughput(state, "两浙路", "seat_hz", "冶铁工场", scale=1.0)
    outputs_water = res_water["outputs"]["铁锭"]

    # 水力水排铁锭产能大幅超越人力
    assert outputs_water > outputs_manual * 2.0
    assert res_water["net_value"] > res_manual["net_value"]
