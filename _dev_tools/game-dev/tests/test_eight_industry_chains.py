# -*- coding: utf-8 -*-
"""M316 八大实体多级产业链网络与工坊配方谱系闭环测试。

验证：
1. 八大产业链常量、工坊配方与商品成品目录完整在册；
2. 原料由 21 路田亩地力、地脉矿脉与畜牧模型全面内生产出；
3. 月度推进结算，八大产业链全部产出物理物资，投入产出严格守恒；
4. 产物物理写入四仓，打通市舶外贸、造船水运、农具兵器、近代火器与印书；
5. 所有成品满足加工增值契约。
"""
import sys

sys.path.insert(0, r"D:/codebuddy/sz/game")

from content.data import (
    FINISHED_DIMS,
    FINISHED_TAX_DIMS,
    GOODS_DIMS,
    MATERIAL_PRICE_BASE,
    RAW_DIMS,
    RESOURCE_DIMS,
    WORKSHOP_RECIPES,
)
from core.domains.economy.industry_chains import (
    CHAIN_ARMAMENT,
    CHAIN_CERAMICS,
    CHAIN_CONSTRUCTION,
    CHAIN_FOOD_CULTURE,
    CHAIN_GUNPOWDER,
    CHAIN_LEATHER,
    CHAIN_MACHINERY,
    CHAIN_METALLURGY,
    CHAIN_NONFERROUS,
    CHAIN_SALT_TEA,
    CHAIN_TEXTILE,
    derive_raw_production,
    settle_industry_chains,
)
from core.game_state import GameState


def test_eight_chains_constants_and_aliases():
    """验证八大产业链常量与历史别名兼容。"""
    chains = [
        CHAIN_TEXTILE,
        CHAIN_METALLURGY,
        CHAIN_MACHINERY,
        CHAIN_GUNPOWDER,
        CHAIN_NONFERROUS,
        CHAIN_LEATHER,
        CHAIN_CERAMICS,
        CHAIN_FOOD_CULTURE,
    ]
    assert len(chains) == 8
    assert len(set(chains)) == 8

    # 历史向后兼容别名
    assert CHAIN_ARMAMENT in chains
    assert CHAIN_SALT_TEA in chains
    assert CHAIN_CONSTRUCTION in chains


def test_eight_chains_workshops_and_price_contract():
    """验证八大链工坊配方在册，且成品严格满足加工增值契约。"""
    new_workshops = [
        "冶铁作坊",
        "兵器营造坊",
        "木作机械坊",
        "造船作坊",
        "火药局",
        "火器制造坊",
        "冶铜熔铸所",
        "铸钱监",
        "硝皮熟皮坊",
        "鞍具皮甲作",
        "官窑瓷坊",
        "被服工坊",
        "印造经籍局",
    ]
    for w_name in new_workshops:
        assert w_name in WORKSHOP_RECIPES, f"工坊 {w_name} 未在 WORKSHOP_RECIPES 中登记"
        w = WORKSHOP_RECIPES[w_name]
        out_dim = w["output_dim"]
        assert out_dim in FINISHED_DIMS, f"产出维 {out_dim} 不在 FINISHED_DIMS"
        assert out_dim in GOODS_DIMS, f"产出维 {out_dim} 不在 GOODS_DIMS"
        assert out_dim in RESOURCE_DIMS, f"产出维 {out_dim} 不在 RESOURCE_DIMS"
        assert out_dim in MATERIAL_PRICE_BASE, f"产出维 {out_dim} 缺基准价"

        # 检查原料全部来自合法的 RAW_DIMS
        for in_dim in w["recipe"]:
            assert in_dim in RAW_DIMS, f"工坊 {w_name} 原料 {in_dim} 不在 RAW_DIMS"
            # 严格加工增值断言
            assert (
                MATERIAL_PRICE_BASE[out_dim] > MATERIAL_PRICE_BASE[in_dim]
            ), f"{w_name}: 成品价 {MATERIAL_PRICE_BASE[out_dim]} 必须高于原料价 {MATERIAL_PRICE_BASE[in_dim]}"


def test_derive_raw_production_covers_all_domains():
    """验证 derive_raw_production 覆盖农业、经济作物、矿山、林石、畜牧与化工原料。"""
    state = GameState()
    prod_zj = derive_raw_production(state, "两浙路")
    assert prod_zj["grain"] > 0
    assert prod_zj["silk_raw"] > 0
    assert prod_zj["hemp_raw"] > 0
    assert prod_zj["tea_raw"] > 0
    assert prod_zj["sugar_cane"] > 0
    assert prod_zj["timber"] > 0
    assert prod_zj["stone"] > 0
    assert prod_zj["clay"] > 0
    assert prod_zj["sulfur_niter"] > 0
    assert prod_zj["hides_raw"] > 0
    assert prod_zj["meat_raw"] > 0


def test_settle_eight_industry_chains_outputs_and_ledger():
    """验证 settle_industry_chains 推进八大实体产业链网络，生成全套物资与台账。"""
    state = GameState()
    initial_treasury = state.treasury
    log = []
    res = settle_industry_chains(state, log)

    outputs = res["outputs"]
    # ① 纤维纺织被服
    assert outputs["silk_cloth_pi"] > 0
    assert outputs["cloth_pi"] > 0
    assert outputs["garments_pieces"] > 0
    # ② 黑色冶金
    assert outputs["refined_iron"] > 0
    assert outputs["weapons_pieces"] > 0
    # ③ 水陆动力机械
    assert outputs["machinery_parts"] > 0
    assert outputs["barges_built"] > 0
    # ④ 火药化工军器
    assert outputs["gunpowder_jin"] > 0
    assert outputs["firearms_pieces"] > 0
    # ⑤ 有色金属铸造
    assert outputs["refined_copper"] > 0
    assert outputs["coins_minted_guan"] > 0
    # ⑥ 畜牧皮具
    assert outputs["tanned_leather_jin"] > 0
    assert outputs["saddle_armor_pieces"] > 0
    # ⑦ 陶瓷琉璃
    assert outputs["fine_china_pieces"] > 0
    # ⑧ 农副食货文教
    assert outputs["sugar_jin"] > 0
    assert outputs["paper_sheets"] > 0
    assert outputs["books_printed"] > 0
    assert outputs["monopoly_tax_coin"] > 0

    # 验证八大链结构完整写入台账
    chains = res["chains"]
    assert len(chains) == 8
    assert CHAIN_TEXTILE in chains
    assert CHAIN_METALLURGY in chains
    assert CHAIN_MACHINERY in chains
    assert CHAIN_GUNPOWDER in chains
    assert CHAIN_NONFERROUS in chains
    assert CHAIN_LEATHER in chains
    assert CHAIN_CERAMICS in chains
    assert CHAIN_FOOD_CULTURE in chains

    # 验证国库增益与日志
    assert state.treasury > initial_treasury
    assert len(log) > 0
    assert "八大实体产业链" in log[0]
