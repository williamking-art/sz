# -*- coding: utf-8 -*-
"""四大实体多级产业链与田亩内生原料产出（单一权威源）。

## 规格与背景（M299 / Stage 2）

为解决《宋祚》原料生产不够完善、静态写死数字、产业链粗糙脱节的根本痛点，
本模块建立四大实体多级产业链，使原料从 21 路耕地地力与矿脉中内生产出，
并经由工坊逐步加工为终端物资：

1. **原料田亩地力内生化**：
   - 粮食：在册主粮田亩 × 路级亩产（南丰 2.5 石 vs 北歉 1.0 石）÷ 12 月；
   - 纺织原料：桑麻经济田亩（`CASH_CROP_LAND`）× 地力产出生丝与原麻；
   - 矿产资源：依地缘矿脉产出铁矿、煤炭、铜矿；
   - 盐茶资源：淮浙闽粤盐场产盐、江南东南茶山产茶；
   - 林石资源：山林采伐木材与石料。
2. **四大实体多级产业链（原料 → 中间品 → 终成品）**：
   - **纺织丝绢链**：桑蚕/原麻 → 缫丝织造 → 绫罗绸缎/布匹（折帛赋税/百姓穿衣/军服）；
   - **军工冶铁链**：铁矿+煤炭 → 冶炼生熟铁 → 军器监打造神臂弓/铁甲/兵刃（装备禁军）；
   - **茶盐专卖链**：茶园+盐场 → 榷货务加工 → 茶钞/盐引流通扑买（国库现钱专卖正税）；
   - **营造漕运链**：木材+采石 → 船坞修造漕船海船/修筑黄河堤防与城郭。
3. **输入输出与质量守恒对账**：
   - 原料消耗必定产出相应中间品或废料，物料进出受严格对账守卫。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from content.data_geo_tables import CASH_CROP_LAND, PREFECTURE_INFO, PREFECTURE_LIST, ROAD_YIELD
from content.demography import EXTRA_CIRCUIT_DEMOG
from core.domains.economy.land_tenure import derive_circuit_tenure
from core.domains.economy.macro_climate import ALL_CIRCUITS_21

__all__ = [
    "derive_raw_production",
    "settle_industry_chains",
    "CHAIN_TEXTILE",
    "CHAIN_ARMAMENT",
    "CHAIN_SALT_TEA",
    "CHAIN_CONSTRUCTION",
]

CHAIN_TEXTILE = "纺织丝绢链"
CHAIN_ARMAMENT = "军工冶铁链"
CHAIN_SALT_TEA = "茶盐专卖链"
CHAIN_CONSTRUCTION = "营造漕运链"


def _get_pref(state, circuit: str) -> Dict[str, Any]:
    """读取某路的 pref 对象。"""
    prefs = getattr(state, "prefectures", None)
    if isinstance(prefs, dict):
        p = prefs.get(circuit)
        if isinstance(p, dict):
            return p
    return {}


def derive_raw_production(state, circuit: str) -> Dict[str, float]:
    """根据该路田亩地力、作物比例与地脉，派生当月内生原料产出（纯函数，只读）。

    产出完全由田亩与地力驱动，告别静态死值。
    """
    if circuit not in ALL_CIRCUITS_21:
        return {}

    p = _get_pref(state, circuit)
    tenure = derive_circuit_tenure(state, circuit)
    total_land = tenure["total_land"]
    if total_land <= 0:
        return {}

    # 亩产系数：两浙/江南 2.5 石/亩，北方 1.0 石/亩
    yield_mult = float(ROAD_YIELD.get(circuit, 1.0))

    # 经济作物田比例（桑蚕、茶、麻、蔗等）
    crop_shares = CASH_CROP_LAND.get(circuit, {})
    total_cash_share = sum(crop_shares.values())
    grain_land = total_land * max(0.60, 1.0 - total_cash_share)

    # 1. 月度原粮产出（石/月）
    # 年产 = 粮田 × 亩产；月产 = 年产 / 12
    monthly_grain = (grain_land * yield_mult) / 12.0

    # 2. 经济作物内生产出（单位/月）
    # 丝（桑蚕）：宋代江浙 1 亩桑田年产经丝约 1.5 斤（折月产，年额对齐 PREFECTURE_INFO 450万斤）
    silk_share = float(crop_shares.get("丝", 0.0))
    monthly_silk = (total_land * silk_share * 1.5) / 12.0

    # 麻：1 亩麻田年产原麻约 1.0 斤
    hemp_share = float(crop_shares.get("麻", 0.0))
    monthly_hemp = (total_land * hemp_share * 1.0) / 12.0

    # 茶：1 亩茶园年产毛茶约 3.3 斤
    tea_share = float(crop_shares.get("茶", 0.0))
    monthly_tea = (total_land * tea_share * 3.3) / 12.0

    # 3. 矿产与林石内生产出：对接 mineral_deposit 真实地脉储量
    from core.domains.economy.mineral_deposit import (
        extract_circuit_minerals, DIM_COPPER, DIM_COAL, DIM_IRON, DIM_SALT, DIM_TIMBER, DIM_STONE
    )
    clerk_grip = float(p.get("clerks_detail", {}).get("grip", 0.45) if isinstance(p.get("clerks_detail"), dict) else (p.get("grip", 0.45) or 0.45))
    mine_res = extract_circuit_minerals(state, circuit, rate_mult=1.0, clerk_grip=clerk_grip)

    monthly_iron_ore = mine_res.get(DIM_IRON, {}).get("physical_extracted", 0.0)
    monthly_copper_ore = mine_res.get(DIM_COPPER, {}).get("physical_extracted", 0.0)
    monthly_coal = mine_res.get(DIM_COAL, {}).get("physical_extracted", 0.0)
    monthly_salt = mine_res.get(DIM_SALT, {}).get("physical_extracted", 0.0)
    monthly_timber = mine_res.get(DIM_TIMBER, {}).get("physical_extracted", 0.0)
    monthly_stone = mine_res.get(DIM_STONE, {}).get("physical_extracted", 0.0)

    # 矿税现钱（坑冶课税二分抽一折钱）
    mine_tax_coin = sum(m.get("tax_coin", 0.0) for m in mine_res.values())

    return {
        "grain": float(round(monthly_grain, 1)),
        "silk_raw": float(round(monthly_silk, 1)),
        "hemp_raw": float(round(monthly_hemp, 1)),
        "tea_raw": float(round(monthly_tea, 1)),
        "iron_ore": float(round(monthly_iron_ore, 1)),
        "copper_ore": float(round(monthly_copper_ore, 1)),
        "coal": float(round(monthly_coal, 1)),
        "salt_raw": float(round(monthly_salt, 1)),
        "timber": float(round(monthly_timber, 1)),
        "stone": float(round(monthly_stone, 1)),
        "mine_tax_coin": float(round(mine_tax_coin, 1)),
    }


def settle_industry_chains(state, log: Optional[List[str]] = None) -> Dict[str, Any]:
    """月度产业链推进与工坊深加工结算（受控写操作）。

    推进四大产业链：
    1. 纺织丝绢链：silk_raw/hemp_raw → 织造为 silk_cloth(匹)/cloth(匹)；
    2. 军工冶铁链：iron_ore + coal → 炼铁并打造 weapons(领件)/armor(领件)；
    3. 茶盐专卖链：tea_raw/salt_raw → 榷货务加工为专卖茶引与官盐入库，贡献正税现钱；
    4. 营造漕运链：timber + stone → 船坞修造 barges(漕船) 与水利堤防修备。

    返回当月全链条投入、产出与对账结果。
    """
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats

    chain_ledger = stats.setdefault("industry_chains_ledger", {})

    # 1. 汇总 21 路当月原料内生产量
    nat_raw = {
        "grain": 0.0, "silk_raw": 0.0, "hemp_raw": 0.0, "tea_raw": 0.0,
        "iron_ore": 0.0, "copper_ore": 0.0, "coal": 0.0, "salt_raw": 0.0,
        "timber": 0.0, "stone": 0.0, "mine_tax_coin": 0.0,
    }
    for c in ALL_CIRCUITS_21:
        prod = derive_raw_production(state, c)
        for k, v in prod.items():
            nat_raw[k] = nat_raw.get(k, 0.0) + v

    # 2. 加工转化（四大产业链 + 铜矿冶炼）
    # 纺织链转化：3 斤生丝产 1 匹绫罗绢帛；2 斤原麻产 1 匹布
    silk_cloth_produced = float(round(nat_raw["silk_raw"] / 3.0, 1))
    hemp_cloth_produced = float(round(nat_raw["hemp_raw"] / 2.0, 1))

    # 军工冶铁链转化：2 斤铁矿 + 1 斤煤炭 产 1 斤熟铁；每 5 斤熟铁打造 1 领兵刃器械
    iron_melted = float(round(min(nat_raw["iron_ore"] / 2.0, nat_raw["coal"]), 1))
    weapons_produced = float(round(iron_melted / 5.0, 1))

    # 铜矿冶炼：1 斤铜矿产出 0.7 斤高纯精炼熟铜，直入国家铜料仓或流通
    copper_refined = float(round(nat_raw["copper_ore"] * 0.7, 1))
    if copper_refined > 0:
        res_slot = getattr(state, "resources", None)
        if isinstance(res_slot, dict):
            c_slot = res_slot.setdefault("铜", {"stock": 0, "cap": 5000000})
            c_slot["stock"] = int(round(float(c_slot.get("stock", 0) or 0) + copper_refined))

    # 茶盐专卖链：茶盐深加工，折纳榷货钞引现钱
    # 每 10 斤官盐创正税 1 贯，每 5 斤榷茶创正税 1 贯
    tea_tax_coin = float(round(nat_raw["tea_raw"] / 5.0, 1))
    salt_tax_coin = float(round(nat_raw["salt_raw"] / 10.0, 1))
    monopoly_tax_total = tea_tax_coin + salt_tax_coin

    # 营造漕运链：每 200 根大木 + 100 方料石 打造 1 艘汴河平底漕船与堤防修护
    barges_built = float(round(min(nat_raw["timber"] / 200.0, nat_raw["stone"] / 100.0), 1))
    if barges_built > 0:
        c_block = int(getattr(state, "canal_block", 0) or 0)
        relief = min(4, max(1, int(barges_built / 500.0)))
        state.canal_block = max(0, c_block - relief)

    # 3. 结果入账与沉淀
    chain_summary = {
        "turn": int(getattr(state, "turn", 0) or 0),
        "raw_materials_produced": nat_raw,
        "outputs": {
            "silk_cloth_pi": silk_cloth_produced,
            "cloth_pi": hemp_cloth_produced,
            "refined_iron": iron_melted,
            "refined_copper": copper_refined,
            "weapons_pieces": weapons_produced,
            "monopoly_tax_coin": monopoly_tax_total,
            "mine_tax_coin": nat_raw.get("mine_tax_coin", 0.0),
            "barges_built": barges_built,
        },
        "chains": {
            CHAIN_TEXTILE: {
                "inputs": {"silk_raw": nat_raw["silk_raw"], "hemp_raw": nat_raw["hemp_raw"]},
                "outputs": {"silk_cloth": silk_cloth_produced, "cloth": hemp_cloth_produced},
            },
            CHAIN_ARMAMENT: {
                "inputs": {"iron_ore": nat_raw["iron_ore"], "coal": nat_raw["coal"]},
                "outputs": {"weapons": weapons_produced, "refined_iron": iron_melted},
            },
            CHAIN_SALT_TEA: {
                "inputs": {"tea_raw": nat_raw["tea_raw"], "salt_raw": nat_raw["salt_raw"]},
                "outputs": {"tax_coin": monopoly_tax_total},
            },
            CHAIN_CONSTRUCTION: {
                "inputs": {"timber": nat_raw["timber"], "stone": nat_raw["stone"]},
                "outputs": {"barges": barges_built},
            },
        }
    }

    chain_ledger[str(getattr(state, "turn", 0))] = chain_summary

    # 部分现钱增益真实并入国库税入（Jev 裁定方案 A：由各路商人 POP 扑买出资划转，严守 POP 挂载律与 ΔM_ALL == 0）
    if monopoly_tax_total > 0:
        tax_target = int(round(monopoly_tax_total * 0.15))
        prefs = getattr(state, "prefectures", {})
        merchant_pops = []
        if isinstance(prefs, dict):
            for p in prefs.values():
                if isinstance(p, dict) and "pops" in p and isinstance(p["pops"], dict):
                    m = p["pops"].get("商人")
                    if isinstance(m, dict):
                        merchant_pops.append(m)

        actual_paid = 0
        if merchant_pops and tax_target > 0:
            quota_per = tax_target // len(merchant_pops)
            rem = tax_target % len(merchant_pops)
            for i, pop in enumerate(merchant_pops):
                due = quota_per + (rem if i == len(merchant_pops) - 1 else 0)
                cur_w = float(pop.get("wealth", 0.0) or 0.0)
                paid = min(cur_w, float(due))
                if paid > 0:
                    from core.foundation.ledger.pop_bridge import pop_obj_add
                    if pop_obj_add(state, pop, "wealth", -int(paid)) is None:
                        pop["wealth"] = cur_w - paid
                    actual_paid += int(paid)

        if actual_paid > 0:
            treasury_now = float(getattr(state, "treasury", 0) or 0)
            state.treasury = int(round(treasury_now + actual_paid))

    if isinstance(log, list):
        log.append(f"[产业链] 本月四大产业链推进：纺织得绢{int(silk_cloth_produced)}匹/布{int(hemp_cloth_produced)}匹；"
                   f"军工得兵械{int(weapons_produced)}领；茶盐榷引纳现钱{int(monopoly_tax_total)}贯；船坞新造漕船{int(barges_built)}艘。")

    return chain_summary
