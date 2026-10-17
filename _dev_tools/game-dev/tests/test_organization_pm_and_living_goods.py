# -*- coding: utf-8 -*-
"""M318 生产组织形态（作坊/工场/大工厂）与民生文教消费闭环测试。

验证：
1. 书本印造配方规范（纸张 + 油墨，排除木方消耗）；
2. 民生七事（柴米油盐酱醋茶）与文房雅宝（笔墨纸砚）商品基准价与产出体系；
3. 生产组织形态 PM（行会作坊 vs 工场分工 vs 动力大工厂）注册、用工配比与产能阶梯；
4. 机械化大工厂的动力机械前置条件守卫（拒绝纯人力手摇）；
5. 综合物料吞吐、用工结构与全产业链月度结算推进。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

from content.data import (
    FINISHED_DIMS,
    GOODS_DIMS,
    MATERIAL_PRICE_BASE,
    RAW_DIMS,
    WORKSHOP_RECIPES,
)
from core.domains.economy.industry_chains import (
    CHAIN_FOOD_CULTURE,
    settle_industry_chains,
)
from core.domains.economy.production_methods import (
    PM_REGISTRY,
    calculate_building_throughput,
    can_switch_pm,
    get_building_pms,
    switch_pm,
)
from core.game_state import GameState


def test_book_recipe_and_living_goods_catalog():
    """验证书籍印造配方纠偏与民生文教商品目录完整性。"""
    # 1. 印造经籍局配方纠偏：仅耗纸与油墨，无木方
    book_recipe = WORKSHOP_RECIPES["印造经籍局"]["recipe"]
    assert "纸" in book_recipe
    assert "油墨" in book_recipe
    assert "木" not in book_recipe
    assert "木方" not in book_recipe

    # 2. PM 注册表中的活字雕版印造：inputs 仅纸张与油墨
    pm_book = PM_REGISTRY["pm_printing_press"]
    assert pm_book.inputs == {"纸张": 8.0, "油墨": 2.0}
    assert pm_book.outputs == {"印造书籍": 3.0}

    # 3. 民生七事与文教商品基准价
    for good in ("油墨", "薪炭", "食用油", "酱醋", "文房四宝"):
        assert good in MATERIAL_PRICE_BASE, f"商品 {good} 必须在 MATERIAL_PRICE_BASE 中"
        assert MATERIAL_PRICE_BASE[good] > 0
        assert good in GOODS_DIMS, f"商品 {good} 必须在 GOODS_DIMS 中"
        assert good in FINISHED_DIMS or good in RAW_DIMS


def test_organization_pms_registry():
    """验证生产组织形态三大 PM（行会作坊、工场手工业、机械化大工厂）。"""
    org_keys = ["pm_org_craft_guild", "pm_org_manufactory", "pm_org_industrial_factory"]
    for k in org_keys:
        assert k in PM_REGISTRY
        pm = PM_REGISTRY[k]
        assert pm.category == "organization"

    guild = PM_REGISTRY["pm_org_craft_guild"]
    manu = PM_REGISTRY["pm_org_manufactory"]
    factory = PM_REGISTRY["pm_org_industrial_factory"]

    # 产能乘数阶梯递增
    assert guild.throughput_mult == 1.0
    assert manu.throughput_mult >= 1.8
    assert factory.throughput_mult >= 4.0

    # 用工结构：作坊纯工匠；大工厂以普通劳工为主、工匠为辅
    assert "工匠" in guild.worker_demand and "工人" not in guild.worker_demand
    assert factory.worker_demand.get("工人", 0) > factory.worker_demand.get("工匠", 0) * 5


def test_industrial_factory_power_prerequisite():
    """验证机械化大工厂对水力/蒸汽动力的强制依赖守卫。"""
    state = GameState()
    circuit = "两浙路"
    seat_id = "seat_hz"
    building = "冶铁工场"

    # 默认动力为人力手工 (pm_power_manual)
    pms = get_building_pms(state, circuit, seat_id, building)
    assert pms["power"] == "pm_power_manual"

    # 尝试在人力手工下直接切换为机械化动力大工厂：拒绝！
    allowed, reason = can_switch_pm(state, circuit, seat_id, building, "pm_org_industrial_factory")
    assert allowed is False
    assert "必须依赖水力或蒸汽动力" in reason

    # 切换动力为水排水力组
    ok_power = switch_pm(state, circuit, seat_id, building, "pm_power_water")
    assert ok_power is True

    # 此时允许切换为机械化大工厂
    allowed_factory, _ = can_switch_pm(state, circuit, seat_id, building, "pm_org_industrial_factory")
    assert allowed_factory is True
    ok_factory = switch_pm(state, circuit, seat_id, building, "pm_org_industrial_factory")
    assert ok_factory is True

    # 检查状态已切换
    cur = get_building_pms(state, circuit, seat_id, building)
    assert cur["organization"] == "pm_org_industrial_factory"


def test_throughput_and_labor_structure_shift():
    """验证组织形态切换带来的产能暴增与用工结构转移（工匠 -> 产业工人）。"""
    state = GameState()
    circuit = "两浙路"
    seat = "seat_hz"
    b_name = "冶铁工场"

    # 1. 传统手工作坊
    switch_pm(state, circuit, seat, b_name, "pm_power_water")  # 统一在水力基底对比
    switch_pm(state, circuit, seat, b_name, "pm_org_craft_guild")
    res_guild = calculate_building_throughput(state, circuit, seat, b_name)

    # 2. 机械化大工厂
    switch_pm(state, circuit, seat, b_name, "pm_org_industrial_factory")
    res_factory = calculate_building_throughput(state, circuit, seat, b_name)

    # 产能乘数与产出大幅跃升
    assert res_factory["total_mult"] >= res_guild["total_mult"] * 3.5
    assert res_factory["outputs"]["铁锭"] >= res_guild["outputs"]["铁锭"] * 3.5

    # 用工结构转变：从纯工匠变成大批产业劳工
    assert res_guild["worker_demand"]["工匠"] == 100
    assert "工人" not in res_guild["worker_demand"]

    assert res_factory["worker_demand"]["工人"] == 60
    assert res_factory["worker_demand"]["工匠"] == 5


def test_industry_chains_settlement_with_living_goods():
    """验证产业链月度推进包含油墨、书籍、文房四宝与民生七事。"""
    state = GameState()
    # 模拟两浙路等产出环境
    pref = state.prefectures.setdefault("两浙路", {})
    pref["total_land"] = 2000000.0
    pref["pops"] = {"商人": {"wealth": 50000}}

    summary = settle_industry_chains(state)
    assert "outputs" in summary
    outs = summary["outputs"]

    # 检查新增产出已入账
    assert "ink_jin" in outs
    assert "books_printed" in outs
    assert "four_treasures_pieces" in outs
    assert "firewood_dan" in outs
    assert "cooking_oil_jin" in outs
    assert "paste_vinegar_jin" in outs

    # 检查食货文教链
    assert CHAIN_FOOD_CULTURE in summary["chains"]
    fc = summary["chains"][CHAIN_FOOD_CULTURE]["outputs"]
    assert "paper" in fc
    assert "ink" in fc
    assert "books" in fc
    assert "four_treasures" in fc
