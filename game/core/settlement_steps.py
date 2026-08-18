# -*- coding: utf-8 -*-
"""宋祚 · 月度结算各步骤实现（Step 1 ~ Step 11）

本模块承载 run_monthly_settlement 流水线中除"主流程/机构改制/五层承接层"之外的
全部 Step 函数。拆分自原 settlement.py，主流程见 core/settlement.py。
"""
import random
from typing import Any

from content.data import (
    MONTHLY_EXP_CIVIL_BASE, ANNUAL_TAX_BASE, TAX_POLL_RATIO, LAND_INFO,
    get_prestige_level, EVENT_CATEGORIES,
    CANAL_MONTHLY_RATE, MILITARY_GRAIN_MONTHLY, OFFICIAL_GRAIN_MONTHLY,
    DISASTER_RELIEF_GRAIN, SPARROW_RAT, CANAL_LOSS_BASE, CANAL_LOSS_CORRUPT_WEIGHT,
    LAND_TAX_RATE, PAY_GRANARY_BASE, PAY_CASH_BASE,
    CHANGPING_HIGH, CHANGPING_LOW, GRAIN_PRICE_MIN, GRAIN_PRICE_MAX,
    ECONOMY_PRESSURE_THRESHOLD_GRANARY, ECONOMY_PRESSURE_THRESHOLD_PRICE,
    SUI_GONG_ANNUAL, TAX_COEFF_MIN, TAX_COEFF_MAX,
    COMMERCE_TAX_RATE_DEFAULT, COMMERCE_TAX_RATE_MIN, COMMERCE_TAX_RATE_MAX,
    # 经济全浮动重构新增
    TAX_COLOR_RATE, LAND_TAX_RATE_BENEFIT, SOLDIER_GRAIN_PER_MONTH, SOLDIER_PAY_PER_MONTH,
    OFFICIAL_PAY_PER_MONTH, OFFICIAL_GRAIN_PER_MONTH, CLERK_PAY_PER_MONTH,
    CLERK_GRAIN_PER_MONTH, CLERK_PER_OFFICIAL, CORRUPTION_MULT, BRIBE_FLOOR,
    IMPERIAL_SHARE, WINE_YIELD_PER_GRAIN, SALT_PROFIT_PER_JIN, SALT_CAPACITY_BASE, SALT_POP_BASE,
    SALT_PRICE_FLOOR, SALT_PRICE_CEIL, WINE_COIN_BASE,
    MATERIAL_PRICE_BASE, RESOURCE_DIMS,
)


# ------------------------------------------------------------
# Step 1: 诏令执行
# ------------------------------------------------------------
def _settle_decrees(state, log):
    """执行本月诏令"""
    # 月初重置：御笔直发额度恢复；狼来了计数仍按既有衰减规则
    state.direct_decree_used = 0

    if state.wolf_count > 0:
        if random.random() < 0.1:
            state.wolf_count = max(0, state.wolf_count - 1)

    executed = 0
    failed = 0
    longterm_this_turn = []

    active_ids = {d.get("id") for d in state.active_decrees if d.get("id")}

    remaining = []
    for decree in state.pending_decrees[:]:
        rate = state.calc_decree_execution_rate(
            decree.get("faction_stances", {}),
            is_secret=decree.get("is_secret", False),
            is_direct=decree.get("is_direct", False),
            secret_loyalty=decree.get("secret_loyalty", 0.5),
            is_zhongzhi=decree.get("is_zhongzhi", False),
            org_hint=decree.get("org_hint", "政府"),
        )
        if random.random() < rate:
            _apply_decree_effect(state, decree, log)
            executed += 1
        else:
            log.append(f"[诏令] 「{decree['title']}」执行受阻，部分落实")
            failed += 1

        did = decree.get("id")
        if decree.get("duration", 0) > 0:
            if did:
                if did not in active_ids:
                    longterm_this_turn.append(decree)
                    active_ids.add(did)
            else:
                if decree not in state.active_decrees and decree not in longterm_this_turn:
                    longterm_this_turn.append(decree)
        else:
            remaining.append(decree)

    state.active_decrees = longterm_this_turn
    state.pending_decrees = remaining

    for decree in state.pending_secret_decrees[:]:
        rate = state.calc_decree_execution_rate(
            decree.get("faction_stances", {}),
            is_secret=True,
            secret_loyalty=decree.get("secret_loyalty", 0.6),
            is_zhongzhi=decree.get("is_zhongzhi", False),
            org_hint=decree.get("org_hint", "政府"),
        )
        if random.random() < rate:
            _apply_decree_effect(state, decree, log)
            log.append(f"[密旨] 「{decree.get('title','密令')}」暗中推行")
            executed += 1
        else:
            if random.random() < 0.2:
                log.append(f"[密旨泄露] 「{decree.get('title','密令')}」被台谏察觉！")
                state.change_prestige(-3, "密旨泄露")
        state.pending_secret_decrees.remove(decree)

    if executed > 0:
        log.append(f"[本月] 诏令执行 {executed} 项，{failed} 项受阻")


def _apply_decree_effect(state, decree, log):
    """应用诏令效果"""
    effects = decree.get("effects", {})
    if "prestige" in effects:
        state.change_prestige(effects["prestige"], decree.get("title", ""))
    if "treasury" in effects:
        state.change_treasury(effects["treasury"])
    if "imperial_treasury" in effects:
        state.change_imperial_treasury(int(effects["imperial_treasury"]))
    if "population_satisfaction" in effects:
        state.population_satisfaction = max(0, min(100,
            state.population_satisfaction + effects["population_satisfaction"]))
    for ext_key, ek in (("external_jin", "金"), ("external_liao", "辽"), ("external_xixia", "西夏")):
        if ext_key in effects and ek in state.external:
            state.external[ek]["attitude"] = max(0, min(100,
                state.external[ek]["attitude"] + effects[ext_key]))
    if "defense_bonus" in effects:
        for line in state.defense_lines.values():
            line["fortification"] = max(0, min(100,
                line["fortification"] + effects["defense_bonus"]))
    if "faction_change" in effects and isinstance(effects["faction_change"], dict):
        for fn, d in effects["faction_change"].items():
            if fn in state.factions:
                state.factions[fn]["satisfaction"] = max(0, min(100,
                    state.factions[fn]["satisfaction"] + d))

    if "single_whip" in effects:
        state.single_whip = bool(effects["single_whip"])
        log.append(f"[改制] {'行一条鞭法，田赋改征折银' if state.single_whip else '复本色，田赋仍征粮'}")
    if "pay_reform" in effects:
        mode = effects["pay_reform"]
        if mode in ("本色折色", "仅发钱", "一体发钞", "仅本色"):
            state.pay_system["mode"] = mode
            if mode == "仅发钱":
                state.pay_system["grain_ratio"], state.pay_system["cash_ratio"] = 0.0, 1.0
            elif mode == "一体发钞":
                state.pay_system["grain_ratio"], state.pay_system["cash_ratio"] = 0.0, 1.0
            elif mode == "仅本色":
                state.pay_system["grain_ratio"], state.pay_system["cash_ratio"] = 1.0, 0.0
            else:
                state.pay_system["grain_ratio"], state.pay_system["cash_ratio"] = 0.5, 0.5
            log.append(f"[改制] 俸禄制度改为「{mode}」")
    if "commerce_tax" in effects:
        target = round(max(COMMERCE_TAX_RATE_MIN, min(COMMERCE_TAX_RATE_MAX, float(effects["commerce_tax"]))), 2)
        state.commerce_tax_rate = target
        if target >= 0.30:
            state.population_satisfaction = max(0, state.population_satisfaction - 4)
            log.append("[改制] 工商重榷，商旅怨声载道，民情愤懑")
        elif target <= 0.10:
            state.population_satisfaction = min(100, state.population_satisfaction + 3)
        log.append(f"[改制] 工商征率定为 {target:.0%}（{'重榷聚财' if target >= 0.3 else ('薄征惠商' if target <= 0.1 else '常征')}）")
    if "curtail_waste" in effects or "reduce_office" in effects:
        kind = "reduce_office" if "reduce_office" in effects else "curtail_waste"
        target = max(50_000, min(150_000, int(float(effects.get("curtail_waste") or effects.get("reduce_office") or 0)) or 100_000))
        state.waste_reform = {
            "active": True, "kind": kind, "savings": 0,
            "target": target, "months_left": random.randint(12, 18), "progress": 0,
        }
        state.change_prestige(-2, "省浮费/裁冗员阻力")
        # 政策 → POP：裁汰冗员裁减官僚 POP 人数（裁 5%，钱粮随之减少，体现三冗之减）
        if kind == "reduce_office":
            for _p in state.prefectures.values():
                _guan = _p["pops"]["官僚"]
                _cut = int(_guan["size"] * 0.05)
                _guan["size"] = max(0, _guan["size"] - _cut)
        log.append(f"[变法] 诏{ '裁汰冗员' if kind=='reduce_office' else '省浮费' }，期以{state.waste_reform['months_left']}月渐省浮费，然官僚梗阻、怨声渐起")
    # 粮量单位约定：decree effect 中的粮额（he_mi/military_supply/relief/grain_stabilize/granary_reform）
    # 语义为「万石」，转到后台「石」需 ×10000；日志仍按设计语义显示「万石」。
    if "granary_reform" in effects:
        add = int(effects["granary_reform"]) * 10000
        state.change_granary_cap(add)
        log.append(f"[仓储] 修葺仓廪，太仓增容 {int(effects['granary_reform'])*10000}石")
    if "canal_dredge" in effects:
        state.canal_block = max(0, state.canal_block - int(effects["canal_dredge"]))
        log.append(f"[漕运] 疏浚运河，漕路阻塞减 {effects['canal_dredge']}")
    if "anti_corruption" in effects:
        for org_key in ("户部",):
            o = state.central_orgs.get(org_key)
            if o and o.get("lead") and o["lead"] in state.corruption:
                state.corruption[o["lead"]] = max(0.0,
                    state.corruption[o["lead"]] - float(effects["anti_corruption"]))
        log.append("[肃贪] 诏令严饬，理财之臣稍敛，截留侵盗略减")
    if "relief" in effects:
        relief = min(int(effects["relief"]) * 10000, state.granary)
        state.change_granary(-relief)
        state.granary_stats["relief"] += relief
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 3))
        log.append(f"[赈济] 开太仓发粟 {int(effects['relief'])*10000}石，饥民得食")
    if "he_mi" in effects:
        amount = int(effects["he_mi"]) * 10000   # 万石 → 石
        cost = int(amount * state.grain_price)   # 石 × (贯/石) = 贯
        if state.treasury >= cost:
            state.treasury -= cost
            state.change_granary(amount)
            log.append(f"[和籴] 丰处和籴粟 {int(effects['he_mi'])*10000}石入太仓，耗钱 {cost:.0f}贯")
    if "land_survey" in effects:
        state.land["hidden_rate"] = max(0.0, state.land["hidden_rate"] - float(effects["land_survey"]))
        # 政策 → 田亩归属/POP：清丈隐田转正 + 抑兼并退田 + 士绅吐粮（钱粮守恒）
        # 效果由 AI 推演评估（据隐田规模/士绅阻力/皇威推演清多少、退多少），无 AI 按档位兜底
        from ai.client_utils import TIER_RANGE
        _hidden_mult = TIER_RANGE.get("小", 0.5) * 0.10   # 兜底：清隐田 5%
        _gentry_mult = TIER_RANGE.get("小", 0.5) * 0.10   # 兜底：退地主田 5%
        try:
            from ai.client import AIClient
            _client = AIClient.load_saved()
            if _client is not None:
                _res = _client.survey_settle(state.posture)
                if _res:
                    _hidden_mult = TIER_RANGE.get(_res.get("hidden_cleared"), 0.5) * 0.10
                    _gentry_mult = TIER_RANGE.get(_res.get("gentry_returned"), 0.5) * 0.10
        except Exception:
            pass
        for _p in state.prefectures.values():
            # 清丈隐田：隐田转正为在册田（士绅隐漏被查出）
            _hidden_reduce = int(_p.get("hidden_land", 0) * _hidden_mult)
            _p["hidden_land"] = max(0, _p.get("hidden_land", 0) - _hidden_reduce)
            _p["land"] = _p.get("land", 0) + _hidden_reduce
            # 抑兼并退田：地主田 → 自耕农田（士绅退田给自耕农）
            _gentry_reduce = int(_p.get("gentry_land", 0) * _gentry_mult)
            _p["gentry_land"] = max(0, _p.get("gentry_land", 0) - _gentry_reduce)
            _p["self_farm_land"] = _p.get("self_farm_land", 0) + _gentry_reduce
            # 士绅囤粮吐出给农 POP（清丈打击囤积）
            _genty = _p["pops"]["士绅"]
            _release = int(_genty["grain"] * _hidden_mult)
            _genty["grain"] -= _release
            _p["pops"]["农"]["grain"] += _release
            # 抄没士绅窖银（清丈/抑兼并时抄家，窖银掏出回国库）
            _confiscate = int(_genty.get("窖银", 0) * _hidden_mult)
            _genty["窖银"] = _genty.get("窖银", 0) - _confiscate
            state.treasury += _confiscate
        for fn in ("旧党", "东南士人"):
            if fn in state.factions:
                state.factions[fn]["satisfaction"] = max(0,
                    state.factions[fn]["satisfaction"] - 5)
        log.append("[方田均税] 清丈隐田转正、抑兼并退田，士绅囤粮吐还，隐漏稍抑，豪强怨望")
    if "military_supply" in effects:
        amount = int(effects["military_supply"]) * 10000
        cost = int(amount * state.grain_price)
        if state.treasury >= cost:
            state.treasury -= cost
            state.change_granary(amount)
            log.append(f"[军需] 入中粮草 {int(effects['military_supply'])*10000}石，军储稍实")
    if "settle_refugees" in effects:
        total_wasteland = sum(p.get("wasteland", state.land.get("wasteland", 0)) for p in state.prefectures.values()) \
            if any("wasteland" in p for p in state.prefectures.values()) else state.land.get("wasteland", 0)
        target = int(effects["settle_refugees"])
        local_total = sum(p.get("refugees", 0) for p in state.prefectures.values())
        placed = 0
        if local_total > 0:
            for name, p in state.prefectures.items():
                share = int(target * p.get("refugees", 0) / local_total)
                if share <= 0:
                    continue
                avail = min(share, p.get("refugees", 0))
                p["refugees"] = max(0, p["refugees"] - avail)
                p["pops"]["农"]["size"] += avail                  # 流民安置回农 POP（人口回流）
                wl = p.get("wasteland")
                if wl is not None:
                    reclaim = avail * 2  # 每流民垦 2 亩
                    p["wasteland"] = max(0, wl - reclaim)
                    p["cultivated"] = p.get("cultivated", 0) + reclaim
                placed += avail
        else:
            used = min(target * 2, state.land.get("wasteland", 0))  # 人数×2 转亩
            state.land["wasteland"] = max(0, state.land.get("wasteland", 0) - used)
            state.land["cultivated"] += used
            placed = used // 2
        log.append(f"[安民] 安置流民垦荒 {placed * 2}亩，各路流民渐归")
    if "grain_stabilize" in effects:
        if state.grain_price > CHANGPING_HIGH:
            sell = min(int(effects["grain_stabilize"]) * 10000, state.granary)
            state.change_granary(-sell)
            state.treasury += int(sell * state.grain_price)
            log.append(f"[平准] 粜粮 {int(effects['grain_stabilize'])*10000}石以抑米价")
        elif state.grain_price < CHANGPING_LOW:
            buy = min(int(effects["grain_stabilize"]) * 10000,
                      int(state.treasury // max(state.grain_price, 0.4)))
            if buy > 0:
                state.treasury -= int(buy * state.grain_price)
                state.change_granary(buy)
                log.append(f"[平准] 籴粮 {int(effects['grain_stabilize'])*10000}石以托米价")

    # 文档第八节白名单所列、此前在 _apply_decree_effect 中缺失的键：补齐以免 AI 拟诏被静默丢弃
    if "army_strength" in effects:
        # 全军战力增益：按各军现有兵力比例分摊（训练/整编加成）
        bonus = int(effects["army_strength"])
        total_troops = sum(u.troops for u in state.army_units) or 1
        for u in state.army_units:
            u.troops = min(int(u.troops * 1.5), u.troops + int(bonus * u.troops / total_troops))
        if state.army_units:
            log.append(f"[整军] 诏令整训，诸军战力益壮（增兵约{bonus}）")
    if "factions_prestige" in effects:
        delta = int(effects["factions_prestige"])
        for fn, f in state.factions.items():
            f["satisfaction"] = max(0, min(100, f["satisfaction"] + delta))
        log.append(f"[朝堂] 诏抚百官，诸派系人心{'稍附' if delta >= 0 else '离散'}（{delta:+d}）")
    if "art_mastery" in effects:
        state.art_mastery = max(0, min(100, state.art_mastery + int(effects["art_mastery"])))
        log.append(f"[文华] 陛下艺事精进（+{int(effects['art_mastery'])}）")


# ------------------------------------------------------------
# Step 2: 派系结算
# ------------------------------------------------------------
def _settle_factions(state, log):
    """派系内部结算"""
    for name, f in state.factions.items():
        cohesion_delta = random.randint(-2, 2)
        f["cohesion"] = max(10, min(100, f["cohesion"] + cohesion_delta))

        if f["satisfaction"] > 55:
            f["satisfaction"] = max(50, f["satisfaction"] - random.randint(0, 2))
        elif f["satisfaction"] < 45:
            f["satisfaction"] = min(50, f["satisfaction"] + random.randint(0, 1))

        inf_delta = random.randint(-1, 1)
        f["influence"] = max(5, min(100, f["influence"] + inf_delta))

    infs = [(name, f["influence"]) for name, f in state.factions.items()]
    infs.sort(key=lambda x: x[1], reverse=True)
    if infs[0][1] - infs[-1][1] > 40:
        log.append("[党争] 朝堂势力悬殊，暗流涌动")
        state.change_prestige(-1, "党争")


# ------------------------------------------------------------
# Step 3: 经济结算
# ------------------------------------------------------------
def _settle_economy(state, log):
    """经济基础结算"""
    growth = random.randint(-5000, 15000)
    state.population = max(10_000_000, state.population + growth)
    # 人口自然增长/萎缩落到各路农 POP（农民为主，按各路人口比例摊）
    if growth != 0:
        for name, p in state.prefectures.items():
            share = p.get("population", 1) / max(state.population, 1)
            p["pops"]["农"]["size"] = max(0, p["pops"]["农"]["size"] + int(growth * share))
    for name, p in state.prefectures.items():
        local = p.get("refugees", 0)
        if local <= 0 and p.get("unrest", 15) < 20:
            continue
        mood = p.get("mood", 55)
        unrest = p.get("unrest", 15)
        govern = p.get("govern", 55)
        absorb = (mood - 50) * 0.001 + (40 - unrest) * 0.0008 + (govern - 50) * 0.0006
        delta = int(local * absorb)
        cap = int(p.get("population", 1_000_000) * 0.05)
        new_local = max(0, min(local + delta, cap))
        if new_local != local:
            p["refugees"] = new_local


def _settle_land_local(state, log):
    """田亩户籍与地方州县自然演进；田赋以实物粮（本色）征收入各州府储粮，
    或（行一条鞭后）折银入国库。粮产率随科技/工业、田亩随开垦动态变化。"""
    arrival = state.calc_arrival_rate()

    hyd = state.tech.get("hydraulics", 40) / 100.0
    tech = state.tech.get("level", 50) / 100.0
    tech_target = 0.6 + hyd * 0.6 + tech * 0.3
    yield_val = state.land.get("yield", 1.0)
    state.land["yield"] = max(0.3, min(2.5, yield_val * 0.97 + tech_target * 0.03))

    if state.land.get("wasteland", 0) > 0:
        cultivate = int(max(20, state.population // 4000))  # 人口(口)→亩
        cultivate = min(cultivate, state.land["wasteland"])
        state.land["cultivated"] += cultivate
        state.land["wasteland"] -= cultivate

    state.land["cultivated"] += int(state.land["cultivated"] * 0.002)
    state.land["hidden_rate"] = min(0.6, state.land["hidden_rate"] + 0.003)

    # ---- 土地演化（开局初值可变化）：自然兼并 + 诡名寄产（隐田）----
    for name, p in state.prefectures.items():
        # 自然兼并：自耕农破产卖地给士绅（每月 0.1%，北宋土地兼并的长期趋势）
        _transfer = int(p.get("self_farm_land", 0) * 0.001)
        p["self_farm_land"] = max(0, p.get("self_farm_land", 0) - _transfer)
        p["gentry_land"] = p.get("gentry_land", 0) + _transfer
        # 诡名寄产/诡名子户：士绅把地主田藏到别人名下逃税（地主田→隐田，随东南士人势力增减）
        _gentry_power = state.factions.get("东南士人", {}).get("influence", 50) / 100.0
        _conceal = int(p.get("gentry_land", 0) * 0.001 * (0.5 + _gentry_power))
        p["gentry_land"] = max(0, p.get("gentry_land", 0) - _conceal)
        p["hidden_land"] = p.get("hidden_land", 0) + _conceal

    _, grain_by = state.calc_monthly_grain()
    land_grain = int(sum(grain_by.values()))

    # 产粮按田亩归属分配 + 田赋按田亩归属征（粮是田产的）
    _harvest = state.month in (3, 6, 9)
    for name, p in state.prefectures.items():
        tax = int(grain_by.get(name, 0))
        _land = max(float(p.get("land", 1)), 1.0)
        _nong, _shen = p["pops"]["农"], p["pops"]["士绅"]
        if _harvest:
            produce = int(p["grain"] / 3.0)
            _nong["grain"] += int(produce * p.get("self_farm_land", 0) / _land)          # 自耕田→自耕农
            _gp = int(produce * p.get("gentry_land", 0) / _land)
            _nong["grain"] += _gp // 2; _shen["grain"] += _gp // 2                      # 地主田→佃户半+士绅半
            _op = int(produce * p.get("official_land", 0) / _land)
            _nong["grain"] += _op // 2; state.change_granary(_op // 2)                   # 官田→佃户半+太仓
            state.granary_stats["official"] = state.granary_stats.get("official", 0) + _op // 2
            _ip = int(produce * p.get("imperial_land", 0) / _land)
            _nong["grain"] += _ip // 2; state.imperial_granary += _ip // 2              # 皇庄→佃户半+内帑粮
            _shen["grain"] += int(produce * p.get("hidden_land", 0) / _land)            # 隐田→士绅(逃税)
        # 田赋按田亩归属征：自耕田→自耕农、地主田→士绅；官田皇庄免、隐田逃税
        _st = int(tax * p.get("self_farm_land", 0) / _land); _gt = int(tax * p.get("gentry_land", 0) / _land)
        _nong["grain"] = max(0, _nong["grain"] - _st); _shen["grain"] = max(0, _shen["grain"] - _gt)
        if state.single_whip:
            state.treasury += int((_st + _gt) * state.grain_price)
        else:
            p["storage"] = p.get("storage", 0) + _st + _gt
    state.granary_stats["tax"] += land_grain
    if land_grain > 0:
        if state.single_whip:
            silver_total = int(land_grain * state.grain_price)
            state.statistics["total_income"] += silver_total
            log.append(f"[田赋·一条鞭] 两税折银征 {silver_total}贯入国库（本色 {land_grain}石改折银）")
        else:
            log.append(f"[田赋] 两税本色征收粮 {land_grain}石，分储诸路仓廪（三运期各征 1/3 年产）")

    state.price_level = state.calc_price_level()
    state.grain_price = state.calc_grain_price()
    for name, p in state.prefectures.items():
        p["grain_price"] = state.calc_region_grain_price(name)

    for name, p in state.prefectures.items():
        target = state.population_satisfaction
        if p["mood"] > target:
            p["mood"] = max(target, p["mood"] - 1)
        elif p["mood"] < target:
            p["mood"] = min(target, p["mood"] + 1)
        p["govern"] = max(20, min(100, p["govern"] + random.randint(-1, 1)))
        p["grain"] = int(p["grain"] * 1.002)

    for yname, y in state.yamen.items():
        y["backlog"] = max(0, y["backlog"] + random.randint(0, 3) - int(y["efficiency"] / 40))
        y["efficiency"] = max(20, min(100, y["efficiency"] + random.randint(-2, 1)))


def _settle_extensions(state, log):
    """金融/科举/科技/外交 等扩展维度的自然演进。"""
    if state.jiaozi["issued"] > 0:
        _ceiling = state._jiaozi_ceiling()                    # 可发额度 = 准备金 × 准备金率（皇威放宽）
        over = max(0, state.jiaozi["issued"] - _ceiling)
        if over > 0:
            # 超发→信用崩（trust 降，贬值）+ 铜钱被挤兑囤积→钱荒加剧；皇威高可减缓贬值
            _prestige_factor = 2.0 - state.prestige / 50.0   # 皇威 0→2.0倍(快崩), 100→0(不崩)
            state.jiaozi["trust"] = max(0, state.jiaozi["trust"] - int(over / 200 * max(0.0, _prestige_factor)))
            state.coin["shortage"] = min(0.9, state.coin.get("shortage", 0.3) + 0.01)
        else:
            # 适量发钞→缓解钱荒（纸币替代铜钱，铜钱流通压力减）
            state.coin["shortage"] = max(0.1, state.coin.get("shortage", 0.3) - 0.005)
    if state.maritime["open"]:
        # 市舶外贸：关税抽解入国库 + 商人 POP 得外贸利润（白银流入民间）
        _trade_month = state.calc_maritime_trade() / 12.0                     # 月贸易额（贯）
        _tariff_rate = state.maritime.get("tariff", 0.10)
        state.treasury += int(_trade_month * _tariff_rate)                    # 关税抽解
        _merchant_profit = int(_trade_month * (1 - _tariff_rate) * 0.3)       # 商人毛利 30%
        _total_merchant = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
        for _p in state.prefectures.values():
            if _p["pops"]["商人"]["size"] > 0:
                _p["pops"]["商人"]["wealth"] += int(_merchant_profit * _p["pops"]["商人"]["size"] / _total_merchant)
        state.coin["shortage"] = max(0.0, state.coin["shortage"] - 0.01)      # 白银流入缓解钱荒
    state.jiaozi["trust"] = min(100, state.jiaozi["trust"] + 1)

    state.exam["talent_pool"] = max(0, min(100, state.exam["talent_pool"]
                                           - 1 + int(state.exam["schools"] / 40)))

    state.tech["level"] = max(0, min(100, state.tech["level"] + random.randint(-1, 1)))
    state.tech["gunpowder"] = max(0, min(100, state.tech["gunpowder"] + random.randint(-1, 1)))
    state.tech["iron"] = max(0, min(100, state.tech["iron"] + random.randint(0, 1)))
    if getattr(state, "maritime", {}).get("open"):
        state.tech["west"] = max(0, min(5, state.tech["west"] + 0.01))
    _settle_tech_research(state, log)


def _settle_tech_research(state, log):
    """按月推进所有攻关中科技节点，满进度点亮并入资产。"""
    from core.asset_context import unlock_node, tech_cost_with_era, get_tech_node
    tech = state.tech
    researching = tech.get("researching", {})
    if not researching:
        return
    for node_id, r in list(researching.items()):
        node = get_tech_node(node_id)
        if not node:
            researching.pop(node_id, None)
            continue
        cost = tech_cost_with_era(node, int(tech.get("era", 0)))
        months = max(1, r.get("months", cost["months"]))
        if r.get("idea"):
            from content.data import get_prestige_level
            _, _, authority = get_prestige_level(state.prestige)
            push = 0.6 + authority * 0.4
            if abs(state.factions.get("新党", {}).get("influence", 50) -
                   state.factions.get("旧党", {}).get("influence", 50)) > 40:
                push *= 0.85
            rate = (100.0 / months) * push
            r["progress"] = min(100.0, r.get("progress", 0) + rate)
        else:
            masters = max(1, r.get("masters", cost["masters"]))
            rate = (100.0 / months) * (0.8 + 0.15 * masters)
            r["progress"] = min(100.0, r.get("progress", 0) + rate)
        if r["progress"] >= 100:
            researching.pop(node_id, None)
            unlock_node(state, node_id)
            tag = "颁行" if r.get("idea") else "研成"
            log.append(f"[科技] 新制「{node[3]}」{tag}，技进于器！")

    base = {"金": 50, "辽": 50, "西夏": 50}
    for k in ("金", "辽", "西夏"):
        cur = state.external[k]["attitude"]
        base_k = base[k]
        if state.alliance_jin_liao:
            if k == "金":
                base_k += 10
            elif k == "辽":
                base_k -= 10
        state.external[k]["attitude"] = max(0, min(100, cur + int((base_k - cur) * 0.05)))


# ------------------------------------------------------------
# Step 3.7a: 长期拟旨推进（公开事务 / 密令）
# ------------------------------------------------------------
def _settle_longterm_decrees(state, log):
    """按月推进所有长期政务（公开事务 + 密令），满进度核销。"""
    presets = state.difficulty_presets.get(state.difficulty, {})
    growth = presets.get("external_growth", 1.0)

    def _progress(queue, label):
        for task in list(queue):
            months = max(1, int(task.get("task", {}).get("months", task.get("months", 18)) if isinstance(task.get("task"), dict) else task.get("months", 18)))
            rate = (100 / months) * (0.8 + 0.4 * growth)
            task["progress"] = min(100, task.get("progress", 0) + rate)
            if random.random() < 0.5:
                task["last_log"] = f"诸司奉行，事有进境（进度 {int(task['progress'])}%）。"
            if task["progress"] >= 100:
                queue.remove(task)
                log.append(f"[{label}] {task.get('task_name', '政务')} 告成，钦此。")

    _progress(getattr(state, "longterm_public", []), "公开事务")
    _progress(getattr(state, "longterm_secret", []), "密令")


# ------------------------------------------------------------
# Step 3.7b: 外部政权简单模拟（按发育曲线 × 难度缓变）
# ------------------------------------------------------------
def _simulate_external(state, log):
    presets = state.difficulty_presets.get(state.difficulty, {})
    mult = presets.get("external_growth", 1.0)
    regime = getattr(state, "external_regimes", {})
    for key, ex in regime.items():
        curve = ex.get("growth_curve", {"expansion": 0.0, "power_growth": 0.0})
        ex["power"] = max(0, ex.get("power", 0) + curve.get("power_growth", 0) * 100 * mult)
        ex["population"] = max(0, ex.get("population", 0) + curve.get("expansion", 0) * 100 * mult)
        ex["storage"] = max(0, ex.get("storage", 0) + curve.get("power_growth", 0) * 40 * mult)
        att = ex.get("attitude", 50)
        ex["attitude"] = max(0, min(100, att + random.randint(-2, 2)))


# ------------------------------------------------------------
# Step 3.8: 仓廪漕运
# ------------------------------------------------------------
def _settle_granary(state, log):
    """仓廪系统月度结算：漕运汇聚 + 雀鼠耗 + 本色支取 + 常平仓 + 认知层。"""
    block = state.canal_block
    if random.random() < 0.08:
        block = min(100, block + random.randint(3, 8))
    if state.disaster_severity > 0 and random.random() < 0.3:
        block = min(100, block + random.randint(5, 15))
    jin_will = state.external.get("金", {}).get("invasion_will", 0)
    if jin_will >= 80 and random.random() < 0.3:
        block = min(100, block + random.randint(3, 10))
    block = max(0, block - random.randint(0, 2))
    state.canal_block = block
    # 三运制：漕运非月月进行——一年分春(3月)/夏(6月)/秋(9月)三个运期，
    # 运期当月发纲集中上供，其余月份不发纲（史实纲运节奏：岁漕三运）。
    if state.month in (3, 6, 9):
        canal_eff = CANAL_MONTHLY_RATE * (1.0 - block / 100.0)
    else:
        canal_eff = 0.0

    corrupt_avg = _avg_corruption(state)
    loss_rate = CANAL_LOSS_BASE + corrupt_avg * CANAL_LOSS_CORRUPT_WEIGHT
    canal = 0
    for p in state.prefectures.values():
        movable = int(p.get("storage", 0) * canal_eff)
        room = max(0, state.granary_cap - state.granary)
        take = min(movable, room)
        if take > 0:
            loss = int(take * loss_rate)
            p["storage"] -= take
            state.change_granary(take - loss)
            state.granary_stats["canal_loss"] += loss
            canal += (take - loss)
    if canal > 0:
        state.granary_stats["canal_in"] += canal
        log.append(f"[漕运] 诸路上供输粟 {canal}石（途中耗 {state.granary_stats['canal_loss']}石），太仓现 {state.granary}石")

    granary_before_out = state.granary

    sparrow = int(state.granary * SPARROW_RAT)
    if sparrow > 0:
        state.granary = max(0, state.granary - sparrow)
        state.granary_stats["sparrow"] += sparrow
        log.append(f"[雀鼠耗] 仓储月耗 {sparrow}石（存粮折损）")

    pay = state.pay_system.get("grain_ratio", 0.5)
    army_grain_total, _ = state.calc_army_grain()
    mil_grain = int(army_grain_total * pay)
    official_grain_total, _ = state.calc_official_grain()
    off_grain = int(official_grain_total * pay)
    clerk_grain_total, _ = state.calc_clerk_grain()
    clerk_grain = int(clerk_grain_total * pay)
    _, corruption_grain_loss = state.calc_corruption_deduction()
    corr_grain = int(corruption_grain_loss * pay)

    need = mil_grain + off_grain + clerk_grain
    given = min(need, state.granary)
    state.change_granary(-given)
    # 收支双向落地：太仓本色支出 → 兵/官僚 POP 粮持有（钱粮循环闭环，不凭空消失）
    if given > 0 and need > 0:
        ratio = given / need
        total_soldiers = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values()) or 1
        total_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values()) or 1
        soldier_grain = mil_grain * ratio
        guan_grain = (off_grain + clerk_grain) * ratio
        for p in state.prefectures.values():
            if p["pops"]["兵"]["size"] > 0:
                p["pops"]["兵"]["grain"] += int(soldier_grain * p["pops"]["兵"]["size"] / total_soldiers)
            if p["pops"]["官僚"]["size"] > 0:
                p["pops"]["官僚"]["grain"] += int(guan_grain * p["pops"]["官僚"]["size"] / total_guan)
    # 贪腐本色损耗实发受剩余太仓约束：change_granary 有 0 下限，
    # 先截断再出账，保证下方太仓恒等断言在枯竭时仍闭合（不因 clamp 断裂）。
    corr_actual = min(corr_grain, state.granary)
    state.change_granary(-corr_actual)
    state.granary_stats["military"] += given
    short = need - given
    if short > 0:
        for u in state.army_units:
            u.training = max(10, u.training - 2)
            u.morale = max(10, u.morale - 2)
        log.append(f"[军粮] 太仓乏粮，本色俸饷短 {short}石，士卒困顿")
        state.population_satisfaction = max(0, state.population_satisfaction - 1)
    elif given > 0:
        log.append(f"[俸禄·本色] 支禄米军粮 {given}石（军粮{mil_grain}+官禄{off_grain}+吏禄{clerk_grain}）")

    out_total = sparrow + given + corr_actual
    assert abs((granary_before_out - state.granary) - out_total) < 1, \
        f"太仓恒等断裂：Δ={granary_before_out - state.granary} out={out_total}"

    changping_acted = False
    for name, p in state.prefectures.items():
        price = p.get("grain_price", state.grain_price)
        cp_stock = p.get("changping_stock", 0)
        coffer = p.get("local_treasury", 0)
        if price > CHANGPING_HIGH and cp_stock > 0:
            # 平粜（高价抑价）：放常平仓粮入市，钱入地方府库。
            # 只动 changping_stock/local_treasury，不涉州仓 storage，故与漕运上供完全解耦；
            # 量随价格超幅线性放大：price 1.6→放 5% 常平储、2.5→放 45%（不固定）
            ratio = min(0.45, (price - CHANGPING_HIGH) * 0.5)
            sell = max(1, int(cp_stock * ratio))
            sell = min(sell, cp_stock)
            p["changping_stock"] = cp_stock - sell
            p["local_treasury"] = coffer + int(sell * price)
            # 放粮入市 → 当地粮价回落（常平抑价的正确触发）
            p["grain_price"] = _recalc_region_price(state, name, extra_supply=sell)
            changping_acted = True
        elif price < CHANGPING_LOW and coffer > 0:
            # 平籴（低价托市）：动用地方府库 30% 预算买粮入常平仓。
            # 量不超过当地月供一半，且受常平仓容（月产 50%）约束，防止无上限膨胀
            budget = int(coffer * 0.30)
            monthly_supply = max(p.get("grain", 0) / 12.0, 1.0)
            cap = max(monthly_supply * 0.5, 1.0)
            room = max(0, int(cap - cp_stock))
            buy = min(int(budget / max(price, 0.4)), int(monthly_supply * 0.5), room)
            if buy > 0:
                p["local_treasury"] = coffer - int(buy * price)
                p["changping_stock"] = cp_stock + buy
                # 收粮出市 → 当地粮价回升（常平托市的正确触发）
                p["grain_price"] = _recalc_region_price(state, name, extra_supply=-buy)
                changping_acted = True
    if changping_acted:
        log.append("[常平] 州县常平仓平粜籴，物价稍纾")

    # ---- 商品交易（多商品）+ 粮市交易 + 各 POP 消费 ----
    # 工匠产不同商品、各 POP 按阶级买不同商品（钱→工匠/商人，钱守恒；新增商品经 register_finished_good 扩展）
    from content.data import GOODS_DEMAND
    _eco = getattr(state, "_economy_ai", None) or {}
    _boom = {"微": 0.5, "小": 0.75, "中": 1.0, "大": 1.3}.get(_eco.get("景气", "中"), 1.0)  # 消费景气
    _prod = {"微": 0.5, "小": 0.75, "中": 1.0, "大": 1.3}.get(_eco.get("生产", "中"), 1.0)  # 生产力度
    for name, p in state.prefectures.items():
        artisan, merchant = p["pops"]["工匠"], p["pops"]["商人"]
        for gdim in artisan["goods"]:                       # 工匠产商品（绸价高量少、布价低量大）
            artisan["goods"][gdim] += int(artisan["size"] * (0.10 if gdim == "绸" else 0.20) * _prod)
        for gdim in merchant["goods"]:                      # 商人贩运
            merchant["goods"][gdim] += int(merchant["size"] * 0.10 * _prod)
        for pop_name, pop in p["pops"].items():             # 各 POP 按阶级买商品
            if pop_name in ("工匠", "商人"):
                continue
            spend = int(pop["wealth"] * {"士绅": 0.05, "官僚": 0.03, "兵": 0.01, "农": 0.005}.get(pop_name, 0.01) * _boom)
            if spend > 0:
                pop["wealth"] -= spend
                for gdim, share in GOODS_DEMAND.get(pop_name, {"布": 1.0}).items():
                    if share > 0:
                        pop["goods"][gdim] = pop["goods"].get(gdim, 0) + int(spend * share)
                artisan["wealth"] += int(spend * 0.7); merchant["wealth"] += int(spend * 0.3)  # 70%工匠 30%商人
    # 士绅奢侈消费（蓄养奴婢/园林/宴饮/香火/收藏），消耗财富、钱流向工匠商人（服务），体现"富而奢"
    for name, p in state.prefectures.items():
        _genty = p["pops"]["士绅"]
        _lux = int(_genty["wealth"] * 0.10)
        if _lux > 0:
            _genty["wealth"] -= _lux
            p["pops"]["工匠"]["wealth"] += int(_lux * 0.5); p["pops"]["商人"]["wealth"] += int(_lux * 0.5)
    # 非农 POP 缺粮用钱从农 POP 余粮买，再各 POP 消费（钱粮守恒）
    from content.data import PER_CAPITA_MONTH_GRAIN
    _famine = False
    for name, p in state.prefectures.items():
        price = p.get("grain_price", state.grain_price)
        price_wen = max(int(price * 1000), 1)
        farmers = p["pops"]["农"]
        for pop_name in ("工匠", "商人", "官僚", "兵"):
            pop = p["pops"][pop_name]
            short = max(0, int(pop["size"] * PER_CAPITA_MONTH_GRAIN) - pop["grain"])
            if short > 0:
                buy = min(short, farmers["grain"])
                if buy * price > pop["wealth"]:
                    buy = max(0, pop["wealth"] // price_wen)
                if buy > 0:
                    _cost = int(buy * price * 1000) / 1000.0   # 文级精度（1贯=1000文）
                    pop["wealth"] -= _cost; pop["grain"] += buy
                    farmers["grain"] -= buy; farmers["wealth"] += _cost
        for pop_name, pop in p["pops"].items():
            need = int(pop["size"] * PER_CAPITA_MONTH_GRAIN)
            if pop["grain"] >= need:
                pop["grain"] -= need
            else:
                pop["grain"] = 0; _famine = True
                if pop_name == "农":                    # 农民缺粮 → 逃荒为流民（POP 人数减、本地流民池增）
                    _flee = int(pop["size"] * 0.01)
                    pop["size"] -= _flee
                    p["refugees"] = p.get("refugees", 0) + _flee
    if _famine:
        state.population_satisfaction = max(0, state.population_satisfaction - 1)

    # ---- 士绅囤粮操作（AI 推演档位优先，无 AI 按粮价方向兜底；钱粮守恒）----
    _settle_civilian_hoard(state, log)

    state.economy_history.append({
        "granary": state.granary,
        "granary_cap": state.granary_cap,
        "grain_price": state.grain_price,
        "price_level": state.price_level,
        "coin_shortage": state.coin.get("shortage", 0.3),
        "canal_block": state.canal_block,
    })
    if len(state.economy_history) > 12:
        state.economy_history = state.economy_history[-12:]
    if state.economy_history:
        state.economy_knowledge = dict(state.economy_history[-1])


def _settle_civilian_hoard(state, log):
    """士绅囤粮操作（钱粮守恒）：AI 推演档位优先，无 AI 时按粮价方向兜底。

    囤 = 士绅用 wealth 买粮（wealth↓ grain↑，受资金约束）；抛 = 卖粮得钱（grain↓ wealth↑）。
    士绅囤粮挤压市场流通（见 calc_region_grain_price 的 HOARD_SUPPLY_SQUEEZE）。
    """
    from content.data import HOARD_SUPPLY_SQUEEZE
    from ai.client_utils import TIER_RANGE
    # AI 经济动态推演（settle_turn 已注入 state._economy_ai：{景气,士绅,士绅力度,生产}）或无
    _eco = getattr(state, "_economy_ai", None) or {}
    _ai_act = _eco.get("士绅", "") if _eco.get("士绅") in ("囤", "抛") else None
    _ai_tier = _eco.get("士绅力度", "中")
    for name, p in state.prefectures.items():
        genty = p["pops"]["士绅"]
        price = p.get("grain_price", state.grain_price)
        if _ai_act:
            act, tier = _ai_act, _ai_tier   # AI 推演（全国统一景气下的士绅行为）
        else:
            # 兜底：丰收贱买囤积、歉收惜售囤积、极端高价抛售获利
            if price < 0.6:
                act, tier = "囤", "小"
            elif price > 2.5:
                act, tier = "抛", "中"
            elif price > 1.6:
                act, tier = "囤", "微"
            else:
                # 粮价平稳：士绅卖囤粮换钱（买商品/维持现金流），卖 5%/月使囤粮存量稳定
                act, tier = "抛", "中"
        mult = TIER_RANGE.get(tier, 0.5) * 0.05   # 囤/抛比例：微0.0125/小0.025/中0.05/大0.09（不 round）
        # 士绅囤粮上限 = 士绅田产年产（地主田 + 隐田的产粮，囤 1 年即封顶，囤不了那么多）
        _land = max(float(p.get("land", 1)), 1.0)
        _gentry_land_total = float(p.get("gentry_land", 0)) + float(p.get("hidden_land", 0))
        _hoard_cap = int(p.get("grain", 0) * _gentry_land_total / _land)
        if act == "囤":
            buy = int(p.get("grain", 0) / 12.0 * mult)      # 月产 × 档位
            afford = genty["wealth"] // max(int(price * 1000), 1)  # 资金能买多少石（文级精度）
            room = max(0, _hoard_cap - genty["grain"])       # 囤粮余量（上限约束）
            buy = min(buy, afford, room)
            if buy > 0:
                genty["wealth"] -= int(buy * price * 1000) / 1000.0
                genty["grain"] += buy
        elif act == "抛":
            sell = int(genty["grain"] * mult)
            if sell > 0:
                genty["grain"] -= sell
                genty["wealth"] += int(sell * price * 0.2)            # 20% 进流通
                genty["窖银"] = genty.get("窖银", 0) + int(sell * price * 0.8)  # 80% 窖藏（可后续掏出）
        # 超上限强制卖粮（士绅粮仓装不下，超出部分必卖回市场，体现囤积有上限）
        if genty["grain"] > _hoard_cap:
            _excess = genty["grain"] - _hoard_cap
            genty["grain"] = _hoard_cap
            genty["wealth"] += int(_excess * price * 0.2)
            genty["窖银"] = genty.get("窖银", 0) + int(_excess * price * 0.8)
        # 窖银退出流通（藏富死钱），后续经抄家/清查政策一次性掏出，平时不自动回流


def _avg_corruption(state):
    """全国理财主官平均贪腐度（后台隐藏，仅影响数值，绝不进 UI 文本）。"""
    names = []
    for org_key in ("户部",):
        o = state.central_orgs.get(org_key)
        if o and o.get("lead"):
            names.append(o["lead"])
    if not names:
        return 0.0
    vals = [state.corruption.get(n, 0.0) for n in names]
    return sum(vals) / len(vals)


def _recalc_region_price(state, name: str, extra_supply: float = 0.0) -> float:
    """按当月供需（年成月均 + 常平净粮流）重算当地粮价（贯/石）。

    价格体系内部允许"文"级精度（1 贯 = 1000 文，即 0.001 贯），
    仅用于价格推导与折银换算；国库/地方府库记账仍为整数贯。
    """
    from content.data import PER_CAPITA_MONTH_GRAIN
    p = state.prefectures.get(name)
    if not p:
        return state.grain_price
    need = p.get("population", 0) * PER_CAPITA_MONTH_GRAIN          # 月需求（石）
    supply = max(p.get("grain", 0) / 12.0 + extra_supply, 0.01)     # 月供应（石）
    ratio = max(0.5, min(2.0, need / supply))
    return max(GRAIN_PRICE_MIN, min(GRAIN_PRICE_MAX, state.grain_price * ratio))


# ------------------------------------------------------------
# Step 4: 财政结算
# ------------------------------------------------------------
def _settle_finance(state: Any, log: Any) -> Any:
    """月度税收与支出结算。国库只收货币税（工商+丁口）+ 一条鞭折银 + 折变；
    田赋本色为实物入粮仓。支出含折色俸禄（随 pay_system）与岁币岁赐。"""
    arrival = state.calc_arrival_rate()
    shortage = state.coin.get("shortage", 0.3)
    tax_coeff = TAX_COEFF_MIN + (TAX_COEFF_MAX - TAX_COEFF_MIN) * (1 - shortage)

    # 工商税基 POP 化：工匠/商人产值流量 = (工匠+商人)size × 人均产值（替代 calc_commerce 凭空 3.5 亿）
    # 产值流量不随 POP 财富存量下降（避免"税抽干财富→税基萎缩"的负反馈螺旋）
    from content.data import CRAFT_OUTPUT_PER_CAPITA
    _commerce_monthly = 0.0
    for _p in state.prefectures.values():
        _commerce_monthly += (_p["pops"]["工匠"]["size"] + _p["pops"]["商人"]["size"]) * CRAFT_OUTPUT_PER_CAPITA
    rate = max(COMMERCE_TAX_RATE_MIN, min(COMMERCE_TAX_RATE_MAX,
                                          getattr(state, "commerce_tax_rate", COMMERCE_TAX_RATE_DEFAULT)))
    commerce_tax = int(_commerce_monthly * rate * arrival * tax_coeff)
    # 役钱（徭役代役钱）：只从农 POP 征（乡村民户负担徭役）；坊郭户（工匠/商人）不服乡村差役、
    # 官户（士绅/官僚）免役、兵免。坊郭户的科配负担并入工商税（commerce_tax）。
    _farm_pop = sum(p["pops"]["农"]["size"] for p in state.prefectures.values())
    poll_tax = int((_farm_pop * TAX_POLL_RATIO / 12) * arrival * tax_coeff)
    maritime_tax = int((state.calc_maritime_trade() / 12.0) *
                       (state.maritime.get("tariff", 0.10) if state.maritime.get("open") else 0.0) *
                       arrival * tax_coeff)
    monthly_tax = commerce_tax + poll_tax + maritime_tax
    state.tax_breakdown = {"commerce": commerce_tax, "poll": poll_tax, "maritime": maritime_tax}

    tax_color_total, tax_color_by = state.calc_monthly_tax_income(tax_coeff)
    salt_coin = state.calc_salt_coin(arrival)
    material_coin = 0.0
    monthly_tax_full = monthly_tax + tax_color_total + salt_coin + material_coin

    # 税从 POP 征（钱守恒）：役钱+二税折色→农、工商税→工匠60%+商人40%、盐课+市舶→商人
    from content.data import PER_CAPITA_MONTH_GRAIN
    _tax_agents = {
        "农": poll_tax + int(tax_color_total),
        "工匠": int(commerce_tax * 0.6),
        "商人": int(commerce_tax * 0.4) + int(salt_coin) + maritime_tax,
    }
    for _agent, _tax_total in _tax_agents.items():
        _total_wealth = sum(p["pops"][_agent]["wealth"] for p in state.prefectures.values())
        if _total_wealth <= 0:
            continue
        for _p in state.prefectures.values():
            _pop = _p["pops"][_agent]
            _deduct = int(_tax_total * (_pop["wealth"] / _total_wealth))
            _min_wealth = int(_pop["size"] * PER_CAPITA_MONTH_GRAIN * state.grain_price)  # 保留1个月口粮钱，不足则欠税
            _pop["wealth"] -= min(_deduct, max(0, _pop["wealth"] - _min_wealth))

    wr = getattr(state, "waste_reform", None) or {}
    if wr.get("active"):
        step = max(10_000, int(wr["target"] / max(1, wr["months_left"])))
        if random.random() < 0.85:
            wr["savings"] = min(wr["target"], wr["savings"] + step)
        else:
            wr["savings"] = max(0, wr["savings"] - step)
        wr["months_left"] -= 1
        wr["progress"] = min(100, int(wr["savings"] / max(1, wr["target"]) * 100))
        if wr["months_left"] <= 0 or wr["savings"] >= wr["target"]:
            wr["active"] = False
            wr["savings"] = wr["target"]
            wr["progress"] = 100
            log.append(f"[变法] {'裁汰冗员' if wr['kind']=='reduce_office' else '省浮费'}告成，浮费月省 {wr['savings']:.0f}贯")
        elif wr["progress"] % 30 == 0:
            log.append(f"[变法] {'裁汰冗员' if wr['kind']=='reduce_office' else '省浮费'}推进中，用度稍省（月省 {wr['savings']:.0f}贯）")
    waste_savings = int(wr.get("savings", 0))

    pay = state.pay_system.get("cash_ratio", 0.5)
    cash_pay = int(PAY_CASH_BASE * pay)
    if state.pay_system.get("mode") == "一体发钞":
        state.jiaozi["issued"] += int(cash_pay)
        state.jiaozi["trust"] = max(0, state.jiaozi["trust"] - 2)
        expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
        cash_out = 0
    else:
        expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
        cash_out = cash_pay

    army_cash_total, _ = state.calc_army_cash()
    official_cash_total, _ = state.calc_official_cash()
    clerk_cash_total, _ = state.calc_clerk_cash()
    corruption_cash_ded, corruption_grain_loss = state.calc_corruption_deduction()
    clerk_gap_total, _ = state.calc_clerk_gap()
    payraise_used = min(state.payraise_budget, int(clerk_gap_total) + 10_000)
    state.payraise_budget = max(0, state.payraise_budget - payraise_used)

    sui_gong = 0
    if state.external.get("辽", {}).get("attitude", 50) >= 60:
        sui_gong += int(SUI_GONG_ANNUAL * 0.6 / 12)
    if state.external.get("西夏", {}).get("attitude", 50) >= 60:
        sui_gong += int(SUI_GONG_ANNUAL * 0.4 / 12)

    personnel_cash = int(army_cash_total + official_cash_total + clerk_cash_total)
    # 收支双向落地：国库俸禄钱 → 兵/官僚 POP 钱（闭环，不凭空消失）
    _total_soldiers = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values()) or 1
    _total_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values()) or 1
    for _p in state.prefectures.values():
        if _p["pops"]["兵"]["size"] > 0:
            _p["pops"]["兵"]["wealth"] += int(army_cash_total * _p["pops"]["兵"]["size"] / _total_soldiers)
        if _p["pops"]["官僚"]["size"] > 0:
            _p["pops"]["官僚"]["wealth"] += int((official_cash_total + clerk_cash_total) * _p["pops"]["官僚"]["size"] / _total_guan)
    effective_cash_out = max(cash_out, personnel_cash)
    total_out = (expenditure + effective_cash_out
                 + int(corruption_cash_ded) + payraise_used + sui_gong)
    net = monthly_tax_full - total_out

    treasury_before = state.treasury
    imp_share, wine_coin = state.calc_imperial_treasury(net)
    # 国库保持整数贯：net 为 float（各 calc_* 乘积），入账前截断
    state.treasury += int(net) - int(imp_share)
    state.imperial_treasury += int(imp_share) + int(wine_coin)
    state.statistics["total_income"] += int(monthly_tax_full)
    state.statistics["total_expenditure"] += total_out

    assert abs((state.treasury - treasury_before) - (net - int(imp_share))) < 1, \
        f"财政恒等断裂：Δtreasury={state.treasury-treasury_before} net={net} imp={int(imp_share)}"

    inc_parts = f"工商{commerce_tax:.0f}+役钱{poll_tax:.0f}+二税折色{tax_color_total:.0f}+盐课{salt_coin:.0f}"
    if maritime_tax > 0:
        inc_parts += f"+市舶{maritime_tax:.0f}"
    if net < 0:
        log.append(f"[财政] 货币月入 {monthly_tax:.0f}贯（{inc_parts}） 支 {total_out:.0f}贯 亏空 {abs(net):.0f}贯（宜折变补之）")
    else:
        log.append(f"[财政] 货币月入 {monthly_tax:.0f}贯（{inc_parts}） 支 {total_out:.0f}贯 结余 {net:.0f}贯")
    if sui_gong > 0:
        log.append(f"[岁币] 岁币岁赐 {sui_gong:.0f}贯，纳贡以安边")

    from content.data import TREASURY_CRISIS_LINE
    if state.treasury < TREASURY_CRISIS_LINE:
        state.population_satisfaction = max(0, state.population_satisfaction - 2)
        log.append("[民生] 国库亏空严重，民怨渐起")

    corrupt_targets = []
    for org_key in ("户部",):
        o = state.central_orgs.get(org_key)
        if o and o.get("lead"):
            corrupt_targets.append(o["lead"])
    if corrupt_targets:
        stress = (state.land.get("hidden_rate", 0.0) - 0.3) + (-net / 1_000_000 if net < 0 else 0)
        drift = max(-0.01, min(0.02, stress * 0.05))
        for name in corrupt_targets:
            if name in state.corruption:
                state.corruption[name] = max(0.0, min(1.0, state.corruption[name] + drift))


# ------------------------------------------------------------
# Step 4.5a: 工程系统
# ------------------------------------------------------------
def _settle_projects(state, log):
    """工程月度推进：扣 BOM（七维物资 + 钱），推进 progress，完工结算产出。"""
    for pid, proj in list(state.projects.items()):
        if proj.get("done"):
            continue
        lack = []
        for dim, need in (proj.get("cost_material") or {}).items():
            if state.resources.get(dim, {}).get("stock", 0) < need:
                lack.append(dim)
        coin_need = int(proj.get("cost_coin", 0))
        if state.treasury < coin_need:
            lack.append("钱")
        if lack:
            log.append(f"[工程] {proj.get('name','工程')} 缺料停滞（缺：{','.join(lack)}），待补给")
            continue
        for dim, need in (proj.get("cost_material") or {}).items():
            state.resources[dim]["stock"] = max(0, state.resources[dim]["stock"] - need)
        if coin_need > 0:
            state.treasury -= coin_need
        proj["progress"] = min(100, proj.get("progress", 0) + int(proj.get("speed", 10)))
        if proj["progress"] >= 100:
            proj["done"] = True
            out = proj.get("output") or {}
            if "granary_cap_add" in out:
                state.change_granary_cap(int(out["granary_cap_add"]))
            if "defense_add" in out:
                from ui.panels_military import ArmyUnit, EQUIP_STD, _defense_line_for
                add = int(out["defense_add"])
                for route in out.get("defense_routes", []):
                    if route not in state.prefectures or add <= 0:
                        continue
                    xiang = [u for u in state.army_units
                             if u.station == route and u.tier == "厢军"]
                    if xiang:
                        # 归入该路厢军主将部（兵额最大者），装备不随增
                        main = max(xiang, key=lambda u: u.troops)
                        main.troops += add
                    else:
                        branch = "轻步兵"
                        std = EQUIP_STD.get(branch, {})
                        state.army_units.append(ArmyUnit(
                            unit_id=f"eng{route}{state.year}{state.month}{pid}",
                            name=f"{route}工役厢（{branch}）",
                            tier="厢军",
                            branch=branch,
                            troops=add,
                            morale=45,
                            training=35,
                            station=route,
                            defense_line=_defense_line_for(route, "厢军"),
                            equip={k: int(add * per) for k, per in std.items()},
                        ))
                state._derive_defense_lines()
            if "wine_coin_add" in out:
                state.imperial_treasury += int(out["wine_coin_add"])
            log.append(f"[工程] {proj.get('name','工程')} 告成，效益已落实")


# ------------------------------------------------------------
# Step 4.5b: 制作/作坊系统
# ------------------------------------------------------------
def _settle_workshops(state, log):
    """作坊月度推进：配方消耗 inputs（如粮→酒），产出 outputs 入 resources/内帑。"""
    for wid, ws in list(state.workshops.items()):
        if not ws.get("active"):
            continue
        recipe = ws.get("recipe") or {}
        lack = []
        # 用 get 而非 pop：recipe 是存档持久 dict，pop 会销毁 grain_feed 键，
        # 导致次月起作坊不再耗粮、白嫖产出。
        grain_feed = recipe.get("grain_feed", 0)
        if grain_feed and state.granary < grain_feed:
            lack.append("太仓粮")
        for dim, need in recipe.items():
            if dim == "grain_feed":
                continue  # 粮耗已按太仓粮单独检查，不作为资源维度
            if state.resources.get(dim, {}).get("stock", 0) < need:
                lack.append(dim)
        if lack:
            log.append(f"[作坊] {ws.get('name','作坊')} 缺料停滞（缺：{','.join(lack)}）")
            continue
        if grain_feed:
            state.change_granary(-grain_feed)
        for dim, need in recipe.items():
            if dim == "grain_feed":
                continue  # 粮耗已单独从太仓扣，不作为资源维度
            state.resources[dim]["stock"] = max(0, state.resources[dim]["stock"] - need)
        out_dim = ws.get("output_dim")
        yld = float(ws.get("yield", 0))
        if out_dim == "wine":
            # 酒坊产酒增加酒课（进内帑净入），酒课随酒坊建设累积；酒耗粮随酒课联动
            state.wine_tax += int(yld * MATERIAL_PRICE_BASE.get("wine", 0) * 0.1)
        elif out_dim in RESOURCE_DIMS:
            cap = state.resources[out_dim]["cap"]
            state.resources[out_dim]["stock"] = min(cap, state.resources[out_dim]["stock"] + yld)


# ------------------------------------------------------------
# Step 5: 国库结算
# ------------------------------------------------------------
def _settle_treasury(state, log):
    """国库结算"""
    pass  # Step 4 已经结算


# ------------------------------------------------------------
# Step 6.5: 历史改写位评估
# ------------------------------------------------------------
def _evaluate_timeline_breaks(state, log):
    """检测玩家成效是否达成改写史实的条件（不直接改写历史）。"""
    tl = state.timeline
    pb = state.pending_breaks
    jin = state.external.get("金", {})
    liao = state.external.get("辽", {})

    if "jin_crushed" not in tl and "jin_crushed" not in pb and jin.get("power", 100) <= 25:
        pb["jin_crushed"] = {"year": state.year, "label": "女真已衰，可趁势灭其于萌芽"}
        log.append("[军机] 女真部族已遭重创，枢密院已具密奏，候陛下朱批定夺")

    if "liao_ally" not in tl and "liao_ally" not in pb and liao.get("attitude", 0) >= 70:
        pb["liao_ally"] = {"year": state.year, "label": "辽主示好，可许盟南北夹击"}
        log.append("[军机] 辽主亲善，枢密院已具密奏，候陛下朱批定夺")

    from ui.panels_military import _army_power_total
    army_str = int(_army_power_total(state.army_units, state.tech.get("gunpowder", 20)) / 1000.0)
    if ("no_jingkang" not in tl and "no_jingkang" not in pb
            and "jin_crushed" not in tl and "jin_crushed" not in pb
            and state.prestige >= 70 and army_str >= 280
            and jin.get("invasion_will", 100) < 40):
        pb["no_jingkang"] = {"year": state.year, "label": "社稷可固，靖康之祸可消弭于未然"}
        log.append("[军机] 国势鼎盛、甲兵方强，枢密院已具密奏，候陛下朱批定夺")


# ------------------------------------------------------------
# Step 6: 军事/外交结算
# ------------------------------------------------------------
def _settle_military_diplomacy(state, log):
    """军事与外部势力推进"""
    tl = state.timeline

    jin = state.external["金"]
    if "jin_crushed" in tl:
        jin["power"] = min(jin["power"], 20)
        jin["invasion_will"] = 0
    elif state.year >= 1115 and "liao_ally" not in tl:
        jin["power"] = min(100, jin["power"] + random.uniform(0.5, 1.5))
        jin["invasion_will"] = min(100, jin["invasion_will"] + random.uniform(0.2, 0.8))
    elif state.year >= 1115 and "liao_ally" in tl:
        jin["power"] = min(100, jin["power"] + random.uniform(0.1, 0.5))

    liao = state.external["辽"]
    if "liao_ally" in tl:
        liao["power"] = min(100, liao["power"] + random.uniform(0.1, 0.4))
    elif state.year >= 1110:
        liao["power"] = max(10, liao["power"] - random.uniform(0.3, 0.8))

    xixia = state.external["西夏"]
    if random.random() < 0.1:
        xixia["attitude"] = max(10, min(90, xixia["attitude"] + random.randint(-10, 10)))

    for u in state.army_units:
        if random.random() < 0.05:
            u.training = max(10, u.training - random.randint(1, 3))


# ------------------------------------------------------------
# Step 7: 事件系统
# ------------------------------------------------------------
def _settle_events(state, log):
    """事件压力推进与触发"""
    for cat in EVENT_CATEGORIES:
        if cat not in state.event_pressure:
            state.event_pressure[cat] = 0
        growth = random.uniform(0, 2) * state.diff_params.get("event_pressure_mult", 1.0)
        state.event_pressure[cat] += growth

    util = state.granary_capacity_used()
    for name, p in state.prefectures.items():
        local_unrest = p.get("unrest", 15)
        local_ref = p.get("refugees", 0)
        if local_unrest >= 40 or local_ref >= 8000:
            boost = (local_unrest - 30) * 0.05 + local_ref / 2000.0
            for cat in ("方腊起义", "宋江起义"):
                if cat in state.event_pressure:
                    state.event_pressure[cat] += boost * random.uniform(0.8, 1.2)
    if util < ECONOMY_PRESSURE_THRESHOLD_GRANARY:
        for cat in ("方腊起义", "宋江起义"):
            if cat in state.event_pressure:
                state.event_pressure[cat] += random.uniform(1.0, 2.5)
        log.append("[经济] 太仓告匮，流民聚啸，起义之谋渐生")
    if state.grain_price >= ECONOMY_PRESSURE_THRESHOLD_PRICE:
        for cat in ("方腊起义", "宋江起义"):
            if cat in state.event_pressure:
                state.event_pressure[cat] += random.uniform(0.5, 1.5)
        log.append("[经济] 米价腾涌，民不堪命，变乱之兆萌焉")
    if state.population_satisfaction < 30:
        for cat in ("方腊起义", "宋江起义"):
            if cat in state.event_pressure:
                state.event_pressure[cat] += random.uniform(0.5, 1.5)

    if state.year >= 1102 and "花石纲" not in state.event_pressure:
        state.event_pressure["花石纲"] = 10

    if state.year >= 1118:
        if "方腊起义" not in state.event_pressure:
            state.event_pressure["方腊起义"] = 20
        state.event_pressure["方腊起义"] += random.uniform(1, 4)

    if state.year >= 1111:
        if "宋江起义" not in state.event_pressure:
            state.event_pressure["宋江起义"] = 10
        state.event_pressure["宋江起义"] += random.uniform(0.5, 2)

    if "jin_crushed" in state.timeline or "no_jingkang" in state.timeline:
        state.event_pressure["金军南侵"] = 0
    elif state.year >= 1120:
        if "金军南侵" not in state.event_pressure:
            state.event_pressure["金军南侵"] = 10
        if "liao_ally" in state.timeline:
            state.event_pressure["金军南侵"] += random.uniform(0.25, 0.75)
        else:
            state.event_pressure["金军南侵"] += random.uniform(0.5, 1.5)

    threshold_base = 80
    threshold = threshold_base * state.diff_params.get("event_threshold_mult", 1.0)
    for cat, pressure in list(state.event_pressure.items()):
        if pressure >= threshold:
            _trigger_event(state, cat, log)
            state.event_pressure[cat] = 0


def _trigger_event(state, category, log):
    """触发事件"""
    message = f"[事件] {category} 爆发！"
    log.append(message)
    state.active_events.append({
        "category": category,
        "turn": state.turn,
        "message": message,
    })
    state.statistics["total_disasters" if "灾" in category or "起义" in category else "total_wars"] += 1
    state.change_prestige(-5, f"{category}爆发")


# ------------------------------------------------------------
# Step 8: 灾荒结算
# ------------------------------------------------------------
def _normalize_disaster_region(state, region):
    """把灾荒 region 俗名归一到 prefectures 稳定键。"""
    if not region:
        return None
    if region in state.prefectures:
        return region
    for key, p in state.prefectures.items():
        if p.get("name") == region:
            return key
    for key, p in state.prefectures.items():
        name = p.get("name", key)
        if region in key or region in name:
            return key
    return None


def _settle_disaster(state, log):
    """天灾结算。灾荒时开仓赈济，耗太仓存粮；有粮则安民，无粮则民怨更重。"""
    if state.disaster_severity > 0:
        state.disaster_severity = max(0, state.disaster_severity - 1)
        relief = min(DISASTER_RELIEF_GRAIN, state.granary)
        state.change_granary(-relief)
        state.granary_stats["relief"] += relief
        if relief >= DISASTER_RELIEF_GRAIN:
            state.population_satisfaction = max(0, min(100, state.population_satisfaction + 1))
            relieved = relief * 3000
            region = _normalize_disaster_region(state, state.disaster_region)
            if region is not None:
                local = state.prefectures[region].get("refugees", 0)
                used = min(relieved, local)
                state.prefectures[region]["refugees"] = max(0, local - used)
                spill = relieved - used
            else:
                used = 0
                spill = relieved
            if spill > 0:
                others = {k: v.get("refugees", 0) for k, v in state.prefectures.items()}
                tot = sum(others.values())
                if tot > 0:
                    for k, rv in others.items():
                        add = int(spill * rv / tot)
                        if add > 0:
                            state.prefectures[k]["refugees"] += add
            log.append(f"[赈济·{region}] 开太仓发粟 {relief}石赈灾，本地流民稍安，余者溢邻路")
        else:
            state.population_satisfaction = max(0, state.population_satisfaction - 3)
            log.append(f"[饥馑] 太仓乏粟（仅发 {relief}石），饿殍渐现，逃荒者众！")
        log.append(f"[灾荒] {state.disaster_region} 持续，严重度 {state.disaster_severity}")

    if random.random() < 0.03:
        severity = random.randint(1, 5)
        region = random.choice(["河北", "京东", "两浙", "陕西", "河东", "荆湖"])
        state.disaster_severity = severity
        state.disaster_region = region
        state.population_satisfaction = max(0, state.population_satisfaction - severity * 2)
        road_key = _normalize_disaster_region(state, region)
        if road_key is not None:
            p = state.prefectures[road_key]
            add_ref = severity * 5000
            cap = int(p.get("population", 1_000_000) * 0.10)  # 人口(口)上限
            p["refugees"] = min(p.get("refugees", 0) + add_ref, cap)
            log.append(f"[流民] {region}灾荒，本地流民骤增 {add_ref}，四散就食")
        log.append(f"[灾荒] {region}发生灾荒！严重度 {severity}")
        state.statistics["total_disasters"] += 1


# ------------------------------------------------------------
# Step 9: 皇帝个人结算
# ------------------------------------------------------------
def _settle_emperor_personal(state, log):
    """皇帝个人行动结算"""
    # 先做基础回调：上月临时带宽过期（最低 6），再结算本月个人行动加成
    state.decree_bandwidth = max(6, state.decree_bandwidth - 2)

    # 自然衰老：随着年龄增长，龙体每月自然损耗，避免玩家靠"不点宴游/勤政"无限拖局
    # 1101 起每过 4 年 +1 点/月基础衰减，1120 后加速（每过 2 年 +1 点/月）
    if state.year >= 1120:
        natural_decay = 1 + (state.year - 1120) // 2
    else:
        natural_decay = (state.year - 1101) // 4
    if natural_decay > 0:
        state.emperor_health = max(0, state.emperor_health - natural_decay)
        log.append(f"[皇帝] 春秋渐高，龙体自然损耗 {natural_decay}")

    action = state.personal_action
    if action == "勤政":
        state.decree_bandwidth = min(10, state.decree_bandwidth + 2)
        state.change_prestige(3, "勤政")
        state.emperor_health -= 2
        log.append("[皇帝] 勤政不怠，天子威仪")
    elif action == "书画翰墨":
        state.art_mastery = min(100, state.art_mastery + 3)
        state.change_prestige(1, "书画")
        log.append("[皇帝] 挥毫翰墨，才情洋溢")
    elif action == "崇道修醮":
        state.taoism_leaning = min(100, state.taoism_leaning + 4)
        state.treasury -= 50000
        for fn in ["新党", "旧党"]:
            if random.random() < 0.5:
                state.factions[fn]["satisfaction"] += 5
        log.append("[皇帝] 崇道修醮，国库耗资五万贯")
    elif action == "享乐宴游":
        state.emperor_health -= 5
        state.pleasure_leaning = min(100, state.pleasure_leaning + 4)
        state.treasury -= 80000
        log.append("[皇帝] 宴游享乐，损耗龙体")
    else:
        state.emperor_health = max(0, min(100,
            state.emperor_health + random.randint(-1, 1)))

    state.personal_action = ""
    state.major_policy = ""


# ------------------------------------------------------------
# Step 10: 隐藏状态
# ------------------------------------------------------------
def _settle_hidden(state, log):
    """隐藏状态结算（灾害、政令累积效果等）"""
    if state.population_satisfaction < 30:
        if random.random() < 0.15:
            state.population_satisfaction -= 1
            log.append("[激变] 民怨沸腾，偶有骚乱")

    jin = state.external["金"]
    if jin.get("invasion_will", 0) >= 90 and state.year >= 1122:
        if random.random() < 0.08:
            from ui.panels_military import _army_power, _army_power_total, _resolve_battle
            jin["invasion_will"] = 80
            gunpowder = state.tech.get("gunpowder", 20)
            front_routes = ("河北路", "河东", "陕西路")
            front_units = [u for u in state.army_units if u.station in front_routes]
            my_power = _army_power_total(front_units, gunpowder)
            jin_power = state.external["金"]["power"]
            win, loss_power, breach = _resolve_battle(my_power, jin_power)
            # 按各 unit 战力占比把 loss_power 分摊成真实伤亡（向下取整，余数归主将部）
            casualty = 0
            if my_power > 0 and loss_power > 0 and front_units:
                powers = [_army_power(u, gunpowder) for u in front_units]
                total_p = sum(powers)
                # 总伤亡人数 = 沿线总兵力 × (loss_power/my_power)
                total_troops = sum(u.troops for u in front_units)
                total_cas = int(total_troops * (loss_power / my_power))
                assigned = 0
                # 主将部 = 战力最大的 unit（余数归它）
                main_idx = max(range(len(front_units)), key=lambda i: powers[i])
                for i, u in enumerate(front_units):
                    if i == main_idx:
                        continue
                    part = int(total_cas * (powers[i] / total_p)) if total_p > 0 else 0
                    part = min(part, u.troops)
                    u.troops -= part
                    assigned += part
                rest = min(total_cas - assigned, front_units[main_idx].troops)
                front_units[main_idx].troops -= max(0, rest)
                casualty = assigned + max(0, rest)
            if breach:
                for line in ("北线_太原真定", "北线_陕西"):
                    if line in state.defense_lines:
                        f0 = state.defense_lines[line].get("fortification", 0)
                        state.defense_lines[line]["fortification"] = max(0, min(100, int(f0 * 0.5)))
            if win:
                log.append(f"[紧急] 金军大举南下！沿边诸军力战却敌，伤亡约{casualty}人")
            else:
                log.append(f"[紧急] 金军大举南下！沿边诸军败绩，防线告破，伤亡约{casualty}人")
            state._derive_defense_lines()

    if state.pleasure_leaning > 80 and random.random() < 0.05:
        state.emperor_health -= 3

    if state.emperor_health > 0 and random.random() < 0.02:
        state.emperor_health -= 1
