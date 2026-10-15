# -*- coding: utf-8 -*-
"""M302 测试：货物流动与产业链产出史实标定、POP 生计闭环及月度结算主流水并轨。"""
import pytest

from core.game_state import GameState
from core.domains.economy.industry_chains import (
    derive_raw_production,
    settle_industry_chains,
)
from core.domains.economy.pop_livelihood import (
    derive_pop_livelihood,
    settle_pop_livelihood,
)
from core.settlement import run_monthly_settlement


def test_calibrated_raw_production_historical_alignment():
    """验证校准后的内生原料产出与北宋史实年额及地力完全吻合。"""
    s = GameState()
    
    # 1. 两浙路（东南财赋蚕桑之冠）
    prod_lz = derive_raw_production(s, "两浙路")
    # 桑蚕丝：月产 ~30~40 万斤，年产 400~500 万斤
    assert 200000.0 <= prod_lz["silk_raw"] <= 600000.0, f"两浙丝产量偏离史实：{prod_lz['silk_raw']}"
    # 茶叶：月产 40~70 万斤，年产 500~800 万斤
    assert 300000.0 <= prod_lz["tea_raw"] <= 800000.0, f"两浙茶产量偏离史实：{prod_lz['tea_raw']}"
    # 粮食：月产 500~800 万石，年产 ~8000 万石
    assert 5000000.0 <= prod_lz["grain"] <= 9000000.0

    # 2. 河东路（解州池盐与晋南铁冶之冠）
    prod_hd = derive_raw_production(s, "河东路")
    assert prod_hd["salt_raw"] >= 4000000.0  # 池盐大宗（月产数百上千万斤）
    assert prod_hd["iron_ore"] >= 150000.0  # 铁冶重地


def test_calibrated_industry_chains_outputs_and_canal_relief():
    """验证四大实体产业链产出与漕运船队缓解联动。"""
    s = GameState()
    s.canal_block = 20
    log = []
    res = settle_industry_chains(s, log)

    outputs = res["outputs"]
    # 丝绢月产应在数十万匹量级（年产几百万至千万匹），绝非虚高亿匹
    assert 100000.0 <= outputs["silk_cloth_pi"] <= 1000000.0, f"丝绢产出量级异常：{outputs['silk_cloth_pi']}"
    # 茶盐月税应在百万贯量级（年入千余万贯，北宋史实岁入约 1500 万贯）
    assert 500000.0 <= outputs["monopoly_tax_coin"] <= 3000000.0, f"茶盐税额量级异常：{outputs['monopoly_tax_coin']}"
    # 军械打造：数千至数万领
    assert outputs["weapons_pieces"] >= 1000.0
    # 营造漕船对运河淤塞产生实际疏浚缓解
    assert s.canal_block < 20, "新造漕船与堤防修护应缓解漕运阻塞"


def test_pop_peasant_income_historical_sanity():
    """验证自耕农月均收入回归北宋自耕农 600~1500 文真实历史区间。"""
    s = GameState()
    res_lz = derive_pop_livelihood(s, "两浙路")
    nong_lz = res_lz["pops"]["农"]
    assert 600.0 <= nong_lz["income"] <= 1500.0, f"两浙农户收入偏离史实千文水平：{nong_lz['income']}"
    assert nong_lz["net_balance"] > 0  # 治世丰年结余为正


def test_full_settlement_monthly_pipeline_integration():
    """验证主结算大流水 settle_month 端到端推进并成功更新产业链与生计台账。"""
    s = GameState()
    s.turn = 1
    s.month = 1
    s.year = 1101

    logs = run_monthly_settlement(s)

    # 1. 验证四大产业链台账已自动沉淀进 state.statistics
    ledger = s.statistics.get("industry_chains_ledger", {})
    assert str(s.turn) in ledger or "1" in ledger, "产业链台账未随月结大流水更新"
    
    # 2. 验证 POP 民怨池与微观生计已随月结大流水演化
    unrest_pool = s.statistics.get("organic_unrest_pool", {})
    assert "两浙路" in unrest_pool
    assert unrest_pool["两浙路"] > 0
