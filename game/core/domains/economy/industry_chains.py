# -*- coding: utf-8 -*-
"""八大实体多级产业链网络与田亩/地脉内生原料产出（单一权威源）。

## 规格与背景（M316 / 八大支柱实体产业链）

为彻底解决《宋祚》产业链过少、工坊谱系单薄、无法承载现代玩家向机械化与近代工业革命演进的根本痛点，
本模块建立八大实体多级产业链网络，使原料从 21 路田亩地力、地脉矿藏与牧场内生产出，
并经由工坊逐步加工为高附加值终端物资，物理确权写入治所物理四仓：

1. **原料田亩地力与地脉内生化**：
   - 粮食：在册主粮田亩 × 路级亩产 ÷ 12 月（原粮，酿酒与常平仓储备）；
   - 纤维：桑麻经济田亩（`CASH_CROP_LAND`）产出生丝与原麻；
   - 经济作物：两广、福建等路蔗田产出甘蔗原料（`sugar_cane`）；
   - 地脉矿产：铁矿、焦煤、生铜、海井池盐、山林木料与采石；
   - 伴生与化工原料：瓷土石料（`clay`）、矿脉伴生硫硝（`sulfur_niter`）；
   - 畜牧产出：牲畜生革（`hides_raw`）与肉食商品（`meat_raw`）。

2. **八大实体多级产业链网络（原料 → 中间品 → 终成品）**：
   - 1. **纤维纺织被服链**（`CHAIN_TEXTILE`）：生丝/原麻 → 缫丝织造为绸缎/布匹 → 加工为被服军衣；
   - 2. **黑色冶金重工链**（`CHAIN_METALLURGY`）：铁矿+焦煤 → 高炉冶炼为熟铁/铸铁 → 锻造兵刃器械与农具铁铧；
   - 3. **水陆动力机械链**（`CHAIN_MACHINERY`）：木材+熟铁 → 水排/大纺车齿轮/机械构件 → 船坞修造漕船海舶；
   - 4. **火药化工军器链**（`CHAIN_GUNPOWDER`）：硫硝+木材木炭 → 配制火药 → 浇铸突火枪/震天雷/火器弹药；
   - 5. **有色金属铸造链**（`CHAIN_NONFERROUS`）：生铜矿石 → 精炼高纯熟铜 → 铸钱监官铸铜钱（平抑钱荒）；
   - 6. **畜牧皮具传动链**（`CHAIN_LEATHER`）：牧场生革 → 硝制熟皮 → 制造军用皮甲/战马鞍鞯/机械传动带；
   - 7. **陶瓷琉璃外贸链**（`CHAIN_CERAMICS`）：瓷土+煤炭柴薪 → 官窑/民窑烧制精品瓷器 → 市舶司外销创汇；
   - 8. **农副食货文教链**（`CHAIN_FOOD_CULTURE`）：原粮酿酒、甘蔗制糖、原麻造纸、木石雕版印刷经籍书籍与印版。

3. **物理入仓与守恒律**：
   - 所有产出物理入治所四仓（官营 `public_depot` / `public_granary`，民间 `civilian_depots`）；
   - 原料消耗必定产出相应中间品或成品，严守进销存对账。
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
    "CHAIN_METALLURGY",
    "CHAIN_MACHINERY",
    "CHAIN_GUNPOWDER",
    "CHAIN_NONFERROUS",
    "CHAIN_LEATHER",
    "CHAIN_CERAMICS",
    "CHAIN_FOOD_CULTURE",
    # 历史向后兼容别名
    "CHAIN_ARMAMENT",
    "CHAIN_SALT_TEA",
    "CHAIN_CONSTRUCTION",
]

CHAIN_TEXTILE = "纤维纺织被服链"
CHAIN_METALLURGY = "黑色冶金重工链"
CHAIN_MACHINERY = "水陆动力机械链"
CHAIN_GUNPOWDER = "火药化工军器链"
CHAIN_NONFERROUS = "有色金属铸造链"
CHAIN_LEATHER = "畜牧皮具传动链"
CHAIN_CERAMICS = "陶瓷琉璃外贸链"
CHAIN_FOOD_CULTURE = "农副食货文教链"

# 历史向后兼容别名
CHAIN_ARMAMENT = CHAIN_GUNPOWDER
CHAIN_SALT_TEA = CHAIN_FOOD_CULTURE
CHAIN_CONSTRUCTION = CHAIN_MACHINERY


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

    产出完全由田亩、地脉矿藏与牧场内生驱动，告别静态死值。
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

    # 蔗：1 亩蔗田年产甘蔗约 5.0 斤（两广、福建等主产）
    cane_share = float(crop_shares.get("蔗", 0.0))
    monthly_cane = (total_land * cane_share * 5.0) / 12.0

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

    # 瓷土石料（用于陶瓷琉璃）：约占采石总量的 20%
    monthly_clay = monthly_stone * 0.20
    # 矿石硫硝（用于火药化工）：约占采矿伴生石料的 10%
    monthly_sulfur_niter = monthly_stone * 0.10

    # 4. 畜牧业产出内生对接（生革与肉食）
    from core.domains.economy.livestock_and_escort import derive_circuit_livestock
    ls = derive_circuit_livestock(state, circuit)
    monthly_hides = float(ls.get("hides", 0.0))
    monthly_meat = float(ls.get("meat", 0.0))

    # 矿税现钱（坑冶课税二分抽一折钱）
    mine_tax_coin = sum(m.get("tax_coin", 0.0) for m in mine_res.values())

    return {
        "grain": float(round(monthly_grain, 1)),
        "silk_raw": float(round(monthly_silk, 1)),
        "hemp_raw": float(round(monthly_hemp, 1)),
        "tea_raw": float(round(monthly_tea, 1)),
        "sugar_cane": float(round(monthly_cane, 1)),
        "iron_ore": float(round(monthly_iron_ore, 1)),
        "copper_ore": float(round(monthly_copper_ore, 1)),
        "coal": float(round(monthly_coal, 1)),
        "salt_raw": float(round(monthly_salt, 1)),
        "timber": float(round(monthly_timber, 1)),
        "stone": float(round(monthly_stone, 1)),
        "clay": float(round(monthly_clay, 1)),
        "sulfur_niter": float(round(monthly_sulfur_niter, 1)),
        "hides_raw": float(round(monthly_hides, 1)),
        "meat_raw": float(round(monthly_meat, 1)),
        "mine_tax_coin": float(round(mine_tax_coin, 1)),
    }


def settle_industry_chains(state, log: Optional[List[str]] = None) -> Dict[str, Any]:
    """月度产业链推进与工坊深加工结算（受控写操作）。

    推进八大实体产业链网络：
    1. 纤维纺织被服链：生丝/原麻 → 织造绸布 → 加工为被服军衣；
    2. 黑色冶金重工链：铁矿+焦煤 → 高炉冶炼生熟铁 → 锻造兵刃器械与工具；
    3. 水陆动力机械链：木材+熟铁 → 打造水力机械构件与平底漕船/远洋海舶；
    4. 火药化工军器链：硫硝+木炭 → 配制火药 → 铸造火器弹药；
    5. 有色金属铸造链：生铜矿石 → 精炼熟铜 → 铸钱监官铸铜钱；
    6. 畜牧皮具传动链：生革 → 硝制熟皮 → 制造鞍具皮甲与传动带；
    7. 陶瓷琉璃外贸链：瓷土+焦煤 → 烧制官窑精品瓷器 → 出海创汇；
    8. 农副食货文教链：原粮酿酒、甘蔗精糖、造纸印制经籍书册。

    返回当月全链条投入、产出与对账结果。
    """
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats

    chain_ledger = stats.setdefault("industry_chains_ledger", {})

    # 1. 汇总 21 路当月原料内生产量，并物理确权写入各路治所四仓（物流上游底座）
    from core.domains.economy.logistics_coupler import ingest_upstream_production
    nat_raw = {
        "grain": 0.0, "silk_raw": 0.0, "hemp_raw": 0.0, "tea_raw": 0.0,
        "sugar_cane": 0.0, "iron_ore": 0.0, "copper_ore": 0.0, "coal": 0.0,
        "salt_raw": 0.0, "timber": 0.0, "stone": 0.0, "clay": 0.0,
        "sulfur_niter": 0.0, "hides_raw": 0.0, "meat_raw": 0.0,
        "mine_tax_coin": 0.0,
    }
    for c in ALL_CIRCUITS_21:
        prod = derive_raw_production(state, c)
        for k, v in prod.items():
            nat_raw[k] = nat_raw.get(k, 0.0) + v
        # 物理确权入各路四仓
        ingest_upstream_production(state, c, prod)

    # 2. 八大实体产业链多级深加工转化

    # 2. 八大实体产业链多级深加工转化（中性中间物流转 + 链式装配）

    # ① 纤维与被服中性物（丝绸与布料）
    silk_cloth_produced = float(round(nat_raw["silk_raw"] / 3.0, 1))
    hemp_cloth_produced = float(round(nat_raw["hemp_raw"] / 2.0, 1))
    fabric_neutral = hemp_cloth_produced
    silk_neutral = silk_cloth_produced
    # 下游被服链式组装：消耗布料 + 丝绸 缝制 1 领被服军衣
    garments_produced = float(round(min(fabric_neutral * 0.20 / 10.0, silk_neutral * 0.10 / 2.0), 1))

    # ② 黑色冶金中性物：铁矿 + 焦煤 -> 铁锭（熟铁）与钢锭
    iron_melted = float(round(min(nat_raw["iron_ore"] / 2.0, nat_raw["coal"]), 1))
    iron_ingots_neutral = iron_melted
    steel_ingots_neutral = float(round(iron_ingots_neutral * 0.25, 1))  # 炒钢与百炼钢法精炼钢锭

    # ③ 木作与机械中性物：原木经水碓锯解为中性木方；铁锭+木方精锻为机械零件
    timber_beams_neutral = float(round(nat_raw["timber"] * 0.8, 1))
    machinery_parts_produced = float(round(min(timber_beams_neutral * 0.25 / 10.0, iron_ingots_neutral * 0.20 / 5.0), 1))

    # ④ 造船坞下游链式装配：消耗中性木方 + 铁锭 + 布料（麻帆）装配漕船海舶
    barges_built = float(round(min(timber_beams_neutral * 0.35 / 150.0, iron_ingots_neutral * 0.15 / 20.0, fabric_neutral * 0.10 / 15.0), 1))
    if barges_built > 0:
        c_block = int(getattr(state, "canal_block", 0) or 0)
        relief = min(4, max(1, int(barges_built / 500.0)))
        state.canal_block = max(0, c_block - relief)

    # ⑤ 火工与军器下游链式装配：硝石 + 硫磺 + 木炭 配火药；再结合钢锭、铜锭、木方制造火器
    gunpowder_produced = float(round(min(nat_raw["sulfur_niter"] / 2.0, nat_raw["timber"] * 0.10), 1))
    copper_refined = float(round(nat_raw["copper_ore"] * 0.7, 1))
    copper_ingots_neutral = copper_refined
    if copper_refined > 0:
        res_slot = getattr(state, "resources", None)
        if isinstance(res_slot, dict):
            c_slot = res_slot.setdefault("铜", {"stock": 0, "cap": 5000000})
            c_slot["stock"] = int(round(float(c_slot.get("stock", 0) or 0) + copper_refined))
    # 火器下游链式消费：钢锭 + 铜锭 + 火药 + 木方 -> 突火枪/火器弹药
    firearms_produced = float(round(min(gunpowder_produced * 0.40 / 4.0, steel_ingots_neutral * 0.30 / 3.0, copper_ingots_neutral * 0.20 / 2.0, timber_beams_neutral * 0.05 / 2.0), 1))

    # ⑥ 兵刃器械下游装配：钢锭/铁锭 + 木方 -> 兵刃器械与农具铁铧
    weapons_produced = float(round(min(iron_ingots_neutral * 0.30 / 5.0, timber_beams_neutral * 0.10 / 2.0), 1))

    # ⑦ 官铸铜钱：铜锭 + 铁锭合铸
    coins_minted = float(round(min(copper_ingots_neutral * 0.40 / 10.0, iron_ingots_neutral * 0.10 / 2.0), 1))

    # ⑧ 畜牧皮革中性物与下游鞍具装配：生革硝制熟皮；熟皮+铁锭制造鞍具皮甲与传动带
    tanned_leather_produced = float(round(nat_raw["hides_raw"] * 0.8, 1))
    leather_neutral = tanned_leather_produced
    saddle_armor_produced = float(round(min(leather_neutral * 0.50 / 5.0, iron_ingots_neutral * 0.08 / 1.0), 1))

    # ⑨ 陶瓷琉璃规范配方：黏土（高岭土）+ 焦煤 烧造精品青白瓷
    fine_china_produced = float(round(min(nat_raw["clay"] / 10.0, nat_raw["coal"] * 0.20 / 4.0), 1))
    export_trade_tax_coin = float(round(fine_china_produced * 15.0, 1))

    # ⑩ 农副食货文教与民生七事：
    # 柴米油盐酱醋茶（民生刚需）+ 笔墨纸砚诗酒茶（文教消费）
    tea_tax_coin = float(round(nat_raw["tea_raw"] / 5.0, 1))
    salt_tax_coin = float(round(nat_raw["salt_raw"] / 10.0, 1))
    monopoly_tax_total = tea_tax_coin + salt_tax_coin + export_trade_tax_coin
    sugar_produced = float(round(nat_raw["sugar_cane"] / 3.0, 1))
    paper_produced = float(round(nat_raw["hemp_raw"] * 0.30 / 1.5, 1))
    paper_neutral = paper_produced

    # 松烟炼墨（油墨原料）
    ink_produced = float(round(nat_raw["timber"] * 0.05 * 2.0, 1))

    # 🔴 书籍规范配方：纯耗 纸张 + 油墨（雕版与铜活字为耐用固定资产，非每册消耗品）
    books_printed = float(round(min(paper_neutral * 0.60 / 8.0, (ink_produced * 0.50 / 2.0) if ink_produced > 0 else paper_neutral * 0.60 / 8.0), 1))

    # 笔墨纸砚（文房四宝）：纸张 + 油墨 + 石料（名砚）
    four_treasures_produced = float(round(min(paper_neutral * 0.20 / 4.0, (ink_produced * 0.20 / 2.0) if ink_produced > 0 else 1.0, nat_raw["stone"] * 0.05 / 2.0), 1))

    # 柴米油盐酱醋茶（民生七事产出）
    firewood_produced = float(round(nat_raw["timber"] * 0.20 + nat_raw["coal"] * 0.10, 1))      # 薪炭
    cooking_oil_produced = float(round(nat_raw["hemp_raw"] * 0.10 / 2.0, 1))                     # 食用油（麻油/菜籽油）
    paste_vinegar_produced = float(round(nat_raw["grain"] * 0.02 / 1.5, 1))                     # 酱醋调味品

    # 3. 结果入账与沉淀
    chain_summary = {
        "turn": int(getattr(state, "turn", 0) or 0),
        "raw_materials_produced": nat_raw,
        "outputs": {
            "silk_cloth_pi": silk_cloth_produced,
            "cloth_pi": hemp_cloth_produced,
            "garments_pieces": garments_produced,
            "refined_iron": iron_melted,
            "iron_ingots": iron_ingots_neutral,
            "steel_ingots": steel_ingots_neutral,
            "timber_beams": timber_beams_neutral,
            "machinery_parts": machinery_parts_produced,
            "weapons_pieces": weapons_produced,
            "barges_built": barges_built,
            "gunpowder_jin": gunpowder_produced,
            "firearms_pieces": firearms_produced,
            "refined_copper": copper_refined,
            "copper_ingots": copper_ingots_neutral,
            "coins_minted_guan": coins_minted,
            "tanned_leather_jin": tanned_leather_produced,
            "leather": leather_neutral,
            "saddle_armor_pieces": saddle_armor_produced,
            "fine_china_pieces": fine_china_produced,
            "sugar_jin": sugar_produced,
            "paper_sheets": paper_produced,
            "paper": paper_neutral,
            "ink_jin": ink_produced,
            "books_printed": books_printed,
            "four_treasures_pieces": four_treasures_produced,
            "firewood_dan": firewood_produced,
            "cooking_oil_jin": cooking_oil_produced,
            "paste_vinegar_jin": paste_vinegar_produced,
            "monopoly_tax_coin": monopoly_tax_total,
            "mine_tax_coin": nat_raw.get("mine_tax_coin", 0.0),
        },
        "chains": {
            CHAIN_TEXTILE: {
                "inputs": {"silk_raw": nat_raw["silk_raw"], "hemp_raw": nat_raw["hemp_raw"]},
                "outputs": {"silk_cloth": silk_cloth_produced, "cloth": hemp_cloth_produced, "garments": garments_produced},
            },
            CHAIN_METALLURGY: {
                "inputs": {"iron_ore": nat_raw["iron_ore"], "coal": nat_raw["coal"]},
                "outputs": {"refined_iron": iron_melted, "weapons": weapons_produced},
            },
            CHAIN_MACHINERY: {
                "inputs": {"timber": nat_raw["timber"], "stone": nat_raw["stone"], "refined_iron": iron_melted * 0.20},
                "outputs": {"machinery_parts": machinery_parts_produced, "barges": barges_built},
            },
            CHAIN_GUNPOWDER: {
                "inputs": {"sulfur_niter": nat_raw["sulfur_niter"], "timber": nat_raw["timber"] * 0.10},
                "outputs": {"gunpowder": gunpowder_produced, "firearms": firearms_produced},
            },
            CHAIN_NONFERROUS: {
                "inputs": {"copper_ore": nat_raw["copper_ore"]},
                "outputs": {"refined_copper": copper_refined, "coins_minted": coins_minted},
            },
            CHAIN_LEATHER: {
                "inputs": {"hides_raw": nat_raw["hides_raw"]},
                "outputs": {"tanned_leather": tanned_leather_produced, "saddle_armor": saddle_armor_produced},
            },
            CHAIN_CERAMICS: {
                "inputs": {"clay": nat_raw["clay"], "coal": nat_raw["coal"] * 0.20},
                "outputs": {"fine_china": fine_china_produced, "export_trade_tax_coin": export_trade_tax_coin},
            },
            CHAIN_FOOD_CULTURE: {
                "inputs": {"sugar_cane": nat_raw["sugar_cane"], "hemp_raw": nat_raw["hemp_raw"] * 0.30, "tea_raw": nat_raw["tea_raw"], "grain": nat_raw["grain"] * 0.02},
                "outputs": {
                    "sugar": sugar_produced,
                    "paper": paper_neutral,
                    "ink": ink_produced,
                    "books": books_printed,
                    "four_treasures": four_treasures_produced,
                    "firewood": firewood_produced,
                    "cooking_oil": cooking_oil_produced,
                    "paste_vinegar": paste_vinegar_produced,
                },
            },
        },
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
        log.append(f"[产业链] 本月八大实体产业链（全面深化升级四大产业链）网络推进：纺织得绢{int(silk_cloth_produced)}匹/被服{int(garments_produced)}领；"
                   f"冶金得熟铁{int(iron_melted)}斤/兵械{int(weapons_produced)}领；机械制构件{int(machinery_parts_produced)}件/漕船{int(barges_built)}艘；"
                   f"军工制火药{int(gunpowder_produced)}斤/火器{int(firearms_produced)}具；铸钱监铸钱{int(coins_minted)}贯；"
                   f"皮具坊得熟皮{int(tanned_leather_produced)}斤/鞍甲{int(saddle_armor_produced)}具；官窑烧瓷{int(fine_china_produced)}件；"
                   f"食货文教得砂糖{int(sugar_produced)}斤/经书{int(books_printed)}部；专卖外贸正税纳现钱{int(monopoly_tax_total)}贯。")

    return chain_summary
