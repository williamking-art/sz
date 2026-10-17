# -*- coding: utf-8 -*-
"""测试空间四仓与结算管线读数（含系统层 vs 朝廷层账目口径分离）。

验证目标：
1. 空间四仓实物储备读数正常提取（官方料场、常平官仓、商人行栈、在途物流）；
2. 结算管线 48 步健康度读数正常输出；
3. 🔴 系统层与朝廷层账目口径严格分离：
   - 朝廷层账目仅含国库、内帑、太仓、官料场与朝廷负债；
   - 系统层全账包含 M_ALL、民间 POP 财富、地方府库与在途全集；
   - 两层对照断言：朝廷可用资金绝不等于全社会 M_ALL，民间资产不被误计为朝廷可用头寸；
4. readout_hub 统一读数集成健全，缺失值绝不作 0。
"""
import pytest
from application.game_init import new_game
from core.domains.economy import spatial_warehouse_readout as swr
from core.domains.economy import readout_hub


def test_spatial_warehouse_readout_basic():
    """验证空间四仓与管线健康度基本读数。"""
    state = new_game()

    depot = swr.public_depot_summary(state)
    assert depot["display"] != "undefined" or depot["reason"] is not None

    granary = swr.public_granary_summary(state)
    assert granary["total_grain"] is not None
    assert granary["total_grain"] > 0

    transit = swr.in_transit_summary(state)
    assert transit["batch_count"] is not None
    assert transit["batch_count"] >= 0

    pipeline = swr.pipeline_health_readout(state)
    assert pipeline["total_steps"] == 48
    assert pipeline["healthy"] is True


def test_court_vs_system_ledger_separation():
    """验证系统层账目与朝廷层账目的严格分离（用户硬约束）。"""
    state = new_game()

    # 1. 朝廷层账目（户部/三司度支视角）
    court = swr.court_ledger_summary(state)
    assert court["scope"] == "court_government"
    assert court["treasury"] == float(state.treasury)
    assert court["imperial_treasury"] == float(state.imperial_treasury)
    assert court["available_cash"] == float(state.treasury + state.imperial_treasury)
    assert court["central_granary"] == float(state.granary)
    assert "liabilities" in court

    # 2. 系统层账目（全知全集上帝视角）
    system = swr.system_ledger_summary(state)
    assert system["scope"] == "system_universe"
    assert system["m_all"] is not None
    assert system["civilian_pop_wealth"] > 0
    assert system["local_treasuries"] >= 0

    # 3. 核心断言：朝廷层资金 ≠ 系统层 M_ALL（民间财富绝不可被当作朝廷可用款！）
    assert court["available_cash"] < system["m_all"], "朝廷可用资金不可超过或等同全社会 M_ALL"
    assert system["civilian_pop_wealth"] > court["available_cash"], "民间藏富总额应大于朝廷即期资金"

    # 4. 对照读数
    contrast = swr.court_vs_system_contrast(state)
    assert contrast["court_money_share"] is not None
    assert 0.0 < contrast["court_money_share"] < 1.0
    assert contrast["civilian_wealth_share"] > 0.0


def test_readout_hub_integration():
    """验证空间四仓与两层账目读数成功接入 readout_hub。"""
    state = new_game()
    rep = readout_hub.collect(state)

    readouts = rep["readouts"]
    expected_keys = [
        "public_depot_materials",
        "public_granary_grain",
        "spatial_in_transit_batches",
        "settlement_pipeline_steps",
        "court_vs_system_contrast",
    ]

    for k in expected_keys:
        assert k in readouts, f"readout_hub 缺失注册项: {k}"
        item = readouts[k]
        assert "label" in item
        assert "display" in item
        assert item["display"] != "0" or item["value"] == 0, f"{k} 缺失不得显示为 0"
