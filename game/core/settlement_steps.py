# -*- coding: utf-8 -*-
"""宋祚 · 月度结算各步骤实现（Step 1 ~ Step 11）

本模块承载 run_monthly_settlement 流水线中除"主流程/机构改制/五层承接层"之外的
全部 Step 函数。拆分自原 settlement.py，主流程见 core/settlement.py。
"""
import random

from content.data import (
    get_prestige_level, EVENT_CATEGORIES,
    CANAL_MONTHLY_RATE, SPARROW_RAT, CANAL_LOSS_BASE, CANAL_LOSS_CORRUPT_WEIGHT,
    CHANGPING_HIGH, CHANGPING_LOW,
    ECONOMY_PRESSURE_THRESHOLD_GRANARY, ECONOMY_PRESSURE_THRESHOLD_PRICE,
    COMMERCE_TAX_RATE_MIN, COMMERCE_TAX_RATE_MAX,
    MATERIAL_PRICE_BASE, RESOURCE_DIMS,
    GOODS_DEMAND,
    # 消费端校准 / POP 流动（Phase B 定稿）
    GRAIN_CONSUME_PER_CAPITA, HIDDEN_CONSUME_PER_CAPITA, GOODS_CONSUME_RATE,
    FARMER_SELL_FLOOR, POP_FLOW_RATE, URBAN_SPLIT,
    BOOM_MULT, TIER_RANGE,
    # 金融推演调制基准（审查 P2-53：幅度/值域唯一权威源，消除 _settle_extensions 内硬编码副本）
    FINANCE_DECIDE_BASE,
    # 加消耗方案（生产过剩吸收，完整定案修正：加工型消耗依托建筑）
    SEED_GRAIN_PER_MU, FARMER_STORE_CAP, FARMER_SPOIL_RATE,
    MEAT_PRICE,
    # 财政结算（原 settlement_finance.py 内联）
    TAX_COEFF_MIN, TAX_COEFF_MAX, TAX_POLL_RATIO,
    COMMERCE_TAX_RATE_DEFAULT, PAY_CASH_BASE, MONTHLY_EXP_CIVIL_BASE,
    SUI_GONG_ANNUAL, GRAIN_PRICE_MIN, GRAIN_PRICE_MAX,
    ARREARS_COLLECT_RATE, OFFICIAL_SERVICE_TAX_RATIO,
    # 灾荒结算（原 settlement_disaster.py 内联）
    DISASTER_RELIEF_GRAIN,
    # 士绅囤粮/窖银（原 settlement_civilian.py 内联）
    HOARD_SUPPLY_SQUEEZE, HOARD_SPOIL_RATE, HOARD_DRAW_RATE,
    HOARD_CAP_MULT, HOARD_COPPER_RATIO_BASE,
)

# 官制 × POP 的受控流动入口（官额/吏额/在岗/待阙/祠禄；禁止直接改 pops["官僚"]["size"]）
from core import officialdom as _officialdom


# ------------------------------------------------------------
# Step 1: 诏令执行
# ------------------------------------------------------------
def _settle_decrees(state, log):
    """执行本月诏令（12 步 agent 化 P2+：诏令执行契约接线）"""
    # 月初重置：御笔直发额度恢复；狼来了计数仍按既有衰减规则
    state.direct_decree_used = 0

    if state.wolf_count > 0:
        if random.random() < 0.1:
            state.wolf_count = max(0, state.wolf_count - 1)

    # 12 步 agent 化 P2+：读取诏令执行 AI 契约
    _decree_ai = getattr(state, "_decree_execute_ai", None)
    ai_tasks = []
    if isinstance(_decree_ai, dict) and not _decree_ai.get("_error"):
        ai_tasks = _decree_ai.get("tasks", [])
        if _decree_ai.get("narrative"):
            log.append(f"[诏令执行] {_decree_ai['narrative']}")

    executed = 0
    failed = 0
    longterm_this_turn = []

    # 吏治把持度对本轮所有诏令的执行折扣（§16.4；只读派生，见 core/clerks.py）
    try:
        from core.clerks import decree_execution_mult as _dem
        _grip_mult = _dem(state)
    except Exception:  # noqa: BLE001 — 吏制不可用时不得阻断诏令结算
        _grip_mult = 1.0
    if _grip_mult < 0.98:
        log.append(f"[吏治] 吏胥把持，政令执行率 ×{_grip_mult:.2f}")

    active_ids = {d.get("id") for d in state.active_decrees if d.get("id")}

    remaining = []
    for decree in state.pending_decrees[:]:
        # AI 契约加成：若有对应机构的高优先级任务，提升执行率
        org_hint = decree.get("org_hint", "政府")
        ai_boost = 0.0
        for task in ai_tasks:
            if task.get("org") == org_hint and task.get("priority") == "高":
                ai_boost = 0.15  # 高优先级任务 +15% 执行率
                break
            elif task.get("org") == org_hint and task.get("priority") == "中":
                ai_boost = 0.08
                break

        rate = state.calc_decree_execution_rate(
            decree.get("faction_stances", {}),
            is_secret=decree.get("is_secret", False),
            is_direct=decree.get("is_direct", False),
            secret_loyalty=decree.get("secret_loyalty", 0.5),
            is_zhongzhi=decree.get("is_zhongzhi", False),
            org_hint=org_hint,
        )
        # §16.4 吏强官弱：实际执行率 = 官效率 × (1 − 把持度 × w)
        # 官三年一任、回避本籍；吏世代本地、掌握簿书 → 政令必须经吏才能落地。
        # 这是给审计 J-2「叙事说办了、数值没动」一个有原因、可诊断、可治理的载体：
        # 回执仍是"已施行"，但效果打折，而原因可在面板查到吏治状态。
        rate = rate * _grip_mult
        rate = min(0.95, rate + ai_boost)  # 封顶 95%

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
        rate = rate * _grip_mult          # 密旨亦须经吏手，同受把持度折扣
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


def _state_grain_trade(state, grain_amt: int, direction: str, price: float, log, tag: str) -> tuple:
    """政府粮食交易的守恒配对（审查 P0：杜绝「国库灭钱/太仓凭空得粮」幻影对手）。

    direction='buy'（和籴/入中/平籴——政府买粮入仓）：
        太仓 +grain、国库 -钱；民间（各路农/士绅等存粮 POP）售粮得钱。
        民间存粮不足 → 少买（实际买入量封顶）。
    direction='sell'（平粜/平准粜——政府卖粮收钱）：
        太仓 -grain、国库 +钱；民间买粮付钱（按可支付财富封顶，避免扣成负）。
    钱、粮两组合计 ΣΔ==0（政府仓 ↔ 民间账户成对划转）。
    返回 (实际 grain 量, 实际钱额)；grain 与钱的价格换算用当前 price。
    """
    pools = []
    for _p in getattr(state, "prefectures", {}).values():
        pops = _p.get("pops") if isinstance(_p, dict) else None
        if not isinstance(pops, dict):
            continue
        for pk in ("农", "士绅", "工匠", "商人", "官僚", "兵"):
            pp = pops.get(pk)
            if isinstance(pp, dict):
                pools.append(pp)
    if not pools:
        return 0, 0
    p = max(float(price), 0.1)
    if direction == "buy":
        # 仓容上限：太仓 change_granary 有 cap 封顶，先按余量限购（防钱付了粮被 cap 吞）
        _room = max(0, int(getattr(state, "granary_cap", 1 << 30)) - int(getattr(state, "granary", 0) or 0))
        # 按民间存粮从多到少征购
        total = 0
        money_paid = 0
        remain = min(int(grain_amt), _room)
        # 审查修复（潜伏造币）：原实现先给民间全额记账、再用 max(0, …) 截断国库
        # → 一旦 caller 未保证 money_paid ≤ 国库（新增调用方或价格下限变动），
        # 差额即凭空产生。此处把「国库可付额」提前作为钱腿硬上限，与 _changping_trade 同规。
        _cash_cap = int(getattr(state, "treasury", 0) or 0)
        for pp in sorted(pools, key=lambda x: -int(x.get("grain", 0) or 0)):
            if remain <= 0 or money_paid >= _cash_cap:
                break
            avail = int(pp.get("grain", 0) or 0)
            take = min(remain, avail)
            if take <= 0:
                continue
            if int(take * p) > _cash_cap - money_paid:      # 国库不足则少买
                take = int((_cash_cap - money_paid) / p)
                if take <= 0:
                    break
            pp["grain"] = avail - take
            _pay = int(take * p)
            pp["wealth"] = int(pp.get("wealth", 0) or 0) + _pay
            remain -= take
            total += take
            money_paid += _pay
        if total <= 0:
            return 0, 0
        state.change_granary(total)
        _treasury = getattr(state, "treasury", 0)
        state.treasury = max(0, _treasury - money_paid)
        log.append(f"[{tag}] 民间籴粮入仓 {total}石，散钱 {money_paid}贯与民")
        return total, money_paid
    # sell：按民间财富摊售（有钱才买得起；实际卖出量受民间可支付力限制）
    total = 0
    money_in = 0
    want = int(grain_amt)
    _buyers = [pp for pp in pools if int(pp.get("wealth", 0) or 0) > 0]
    if not _buyers:
        return 0, 0
    _total_w = sum(int(x.get("wealth", 0) or 0) for x in _buyers)
    for pp in _buyers:
        if want <= 0:
            break
        _share = min(1.0, (int(pp.get("wealth", 0) or 0)) / max(_total_w, 1))
        _alloc = min(want, int(grain_amt * _share))
        # 支付能力校验：买 _alloc 石需 _alloc*p 钱，不够则少买
        _can_afford = int((int(pp.get("wealth", 0) or 0)) // p)
        _alloc = min(_alloc, _can_afford)
        if _alloc <= 0:
            continue
        _cost = int(_alloc * p)
        pp["wealth"] = int(pp.get("wealth", 0) or 0) - _cost
        pp["grain"] = int(pp.get("grain", 0) or 0) + _alloc
        total += _alloc
        money_in += _cost
        want -= _alloc
    if total <= 0:
        return 0, 0
    state.change_granary(-total)
    state.treasury = getattr(state, "treasury", 0) + money_in
    log.append(f"[{tag}] 官仓粜粮 {total}石，回收 {money_in}贯")
    return total, money_in


def _changping_trade(pref, name, grain_amt, direction, price, log, tag):
    """州县常平仓粜籴的守恒配对（与 _state_grain_trade 同构；钱腿为本路府库）。

    审查修复背景：常平仓原实现只动 `changping_stock` / `local_treasury` 两个
    政府侧账户 —— 平粜放出的粮无买家（粮凭空消失）、回收的钱无付款方（钱凭空
    产生）；平籴买入的粮无卖家（粮凭空产生）、付出的钱无收款方（钱凭空消失）。
    现改为与本路民间 POP 成对划转，两侧合计 ΣΔ==0：

      direction='buy'（平籴·政府买粮入仓）：
          常平仓 +grain、本路府库 -钱；存粮 POP 售粮得钱。
          受「府库可付额」与「民间可售粮」双重封顶。
      direction='sell'（平粜·政府卖粮收钱）：
          常平仓 -grain、本路府库 +钱；有钱 POP 买粮付钱（按可支付力封顶）。

    返回 (实际粮量, 实际钱额)；两者皆 0 表示本次未成交易（调用方不应记动作）。
    """
    pools = []
    pops = pref.get("pops") if isinstance(pref, dict) else None
    if isinstance(pops, dict):
        for pk in ("农", "士绅", "工匠", "商人", "官僚", "兵"):
            pp = pops.get(pk)
            if isinstance(pp, dict):
                pools.append(pp)
    if not pools:
        return 0, 0
    _price = max(float(price), 0.1)

    if direction == "buy":
        _pay_cap = int(pref.get("local_treasury", 0) or 0)
        total = 0
        money = 0
        remain = int(grain_amt)
        for pp in sorted(pools, key=lambda x: -int(x.get("grain", 0) or 0)):
            if remain <= 0 or money >= _pay_cap:
                break
            avail = int(pp.get("grain", 0) or 0)
            take = min(remain, avail)
            _pay = int(take * _price)
            if _pay > _pay_cap - money:                     # 府库不足则少买
                take = int((_pay_cap - money) / _price)
                _pay = int(take * _price)
            if take <= 0:
                continue
            pp["grain"] = avail - take
            pp["wealth"] = int(pp.get("wealth", 0) or 0) + _pay
            remain -= take
            total += take
            money += _pay
        if total <= 0:
            return 0, 0
        pref["changping_stock"] = int(pref.get("changping_stock", 0) or 0) + total
        pref["local_treasury"] = _pay_cap - money
        log.append(f"[{tag}] {name}平籴入常平 {total}石，散钱 {money}贯与民")
        return total, money

    total = 0
    money = 0
    want = int(grain_amt)
    _buyers = [pp for pp in pools if int(pp.get("wealth", 0) or 0) > 0]
    if not _buyers:
        return 0, 0
    _tw = sum(int(x.get("wealth", 0) or 0) for x in _buyers)
    for pp in _buyers:
        if want <= 0:
            break
        _share = min(1.0, int(pp.get("wealth", 0) or 0) / max(_tw, 1))
        _alloc = min(want, int(grain_amt * _share))
        _alloc = min(_alloc, int(int(pp.get("wealth", 0) or 0) // _price))   # 买得起才买
        if _alloc <= 0:
            continue
        _cost = int(_alloc * _price)
        pp["wealth"] = int(pp.get("wealth", 0) or 0) - _cost
        pp["grain"] = int(pp.get("grain", 0) or 0) + _alloc
        total += _alloc
        money += _cost
        want -= _alloc
    if total <= 0:
        return 0, 0
    pref["changping_stock"] = max(0, int(pref.get("changping_stock", 0) or 0) - total)
    pref["local_treasury"] = int(pref.get("local_treasury", 0) or 0) + money
    log.append(f"[{tag}] {name}常平粜粮 {total}石，回收 {money}贯入府库")
    return total, money


def _levy_men(state, road: str, need: int) -> int:
    """自本路农户、其次流民中征补兵员（人守恒：农/流民 → 兵）。

    审查配套：诏令/事件的整军增兵若只 add_troops，则在 _settle_finance 以
    Σbranches 重聚合兵 POP、并把 ΣPOP 写回 population 之后，会表现为「凭空
    产生人口」（实测量级可达数万）。故增兵须有来源，且不足时按实有截断
    —— 宁少征，不造人。返回实际征得人数。
    """
    if need <= 0:
        return 0
    p = getattr(state, "prefectures", {}).get(road)
    if not isinstance(p, dict):
        return 0
    got = 0
    pops = p.get("pops") or {}
    farmer = pops.get("农") if isinstance(pops, dict) else None
    if isinstance(farmer, dict):
        take = min(need, int(farmer.get("size", 0) or 0))
        if take > 0:
            farmer["size"] = int(farmer.get("size", 0) or 0) - take
            got += take
    if got < need:                                   # 农户不足 → 再征流民
        ref = int(p.get("refugees", 0) or 0)
        take = min(need - got, ref)
        if take > 0:
            p["refugees"] = ref - take
            got += take
    return got


def _return_men(state, road: str, n: int) -> int:
    """裁汰兵力回流本路农户（人守恒：兵 → 农）；无农户时归流民池。

    与 _levy_men 对称：凡减少兵额（裁汰/整编）都应把人丁送回民户，
    否则 _settle_finance 以 Σbranches 重聚合兵 POP 时表现为人口凭空消失。
    """
    if n <= 0:
        return 0
    p = getattr(state, "prefectures", {}).get(road)
    if not isinstance(p, dict):
        return 0
    pops = p.get("pops") or {}
    farmer = pops.get("农") if isinstance(pops, dict) else None
    if isinstance(farmer, dict):
        farmer["size"] = int(farmer.get("size", 0) or 0) + n
    else:
        p["refugees"] = int(p.get("refugees", 0) or 0) + n
    return n


def _apply_decree_effect(state, decree, log):
    """应用诏令效果"""
    effects = decree.get("effects", {})
    if "prestige" in effects:
        state.change_prestige(effects["prestige"], decree.get("title", ""))
    if "treasury" in effects:
        _dt = int(effects["treasury"])
        if _dt > 0:
            got = state.drain_pop_wealth("商人", int(_dt * 0.7)) + \
                  state.drain_pop_wealth("农", _dt - int(_dt * 0.7))
            if got < _dt:
                log.append(f"[诏令·守恒] 国库增收应 {_dt}，民间可征仅 {got}，按实入账")
            state.change_treasury(got)
        elif _dt < 0:
            need = abs(_dt)
            paid = 0
            for _road in state.prefectures:
                if paid >= need:
                    break
                paid += state.transfer_money("treasury", f"pop:{_road}:官僚", need - paid)
            if paid < need:
                state.change_treasury(-(need - paid))
    if "imperial_treasury" in effects:
        _it = int(effects["imperial_treasury"])
        if _it > 0:
            got = state.drain_pop_wealth("商人", _it)
            state.change_imperial_treasury(got if got > 0 else 0)
            if got < _it:
                log.append(f"[诏令·守恒] 内帑增收应 {_it}，实征 {got}")
        elif _it < 0:
            state.change_imperial_treasury(_it)
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
        # 裁冗**先从冗处裁**：优先祠禄 → 待阙 → 在岗（见 core/officialdom.remove_officials）。
        # 返乡去向：裁下的官重回士绅（ΣPOP 守恒，§13.5 出口轴）。
        if kind == "reduce_office":
            for _p in state.prefectures.values():
                _guan = _p["pops"]["官僚"]
                _cut = _officialdom.remove_officials(_p, int(_guan["size"] * 0.05))
                _p["pops"]["士绅"]["size"] += _cut
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
            # 审查 P0：和籴为政府向民间买粮——国库出钱、民间售粮（钱粮均守恒）
            _amt, _cost = _state_grain_trade(state, amount, "buy", state.grain_price,
                                             log, "和籴")
            if _amt > 0:
                log.append(f"[和籴] 丰处和籴粟 {_amt}石入太仓，散钱 {_cost}贯与民")
    if "land_survey" in effects:
        state.land["hidden_rate"] = max(0.0, state.land["hidden_rate"] - float(effects["land_survey"]))
        # 政策 → 田亩归属/POP：清丈隐田转正 + 抑兼并退田 + 士绅吐粮（钱粮守恒）
        # 效果优先用结算前注入的 _survey_ai 槽位；无则本地档位兜底（禁止结算路径同步 HTTP）
        from content.data import TIER_RANGE
        _hidden_mult = TIER_RANGE.get("小", 0.5) * 0.10   # 兜底：清隐田 5%
        _gentry_mult = TIER_RANGE.get("小", 0.5) * 0.10   # 兜底：退地主田 5%
        _res = getattr(state, "_survey_ai", None)
        if isinstance(_res, dict) and not _res.get("_error"):
            _hidden_mult = TIER_RANGE.get(_res.get("hidden_cleared"), 0.5) * 0.10
            _gentry_mult = TIER_RANGE.get(_res.get("gentry_returned"), 0.5) * 0.10
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
            # 审查 P0：入中粮草 = 政府购粮——国库出钱、民间售粮（钱粮均守恒）
            _amt, _cost = _state_grain_trade(state, amount, "buy", state.grain_price,
                                             log, "军需")
            if _amt > 0:
                log.append(f"[军需] 入中粮草 {_amt}石，军储稍实")
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
            want = int(effects["grain_stabilize"]) * 10000
            # 审查 P0：平粜 = 政府卖粮收钱（民间付钱得粮），钱粮守恒
            _amt, _cost = _state_grain_trade(state, min(want, state.granary), "sell",
                                             state.grain_price, log, "平准")
            if _amt > 0:
                log.append(f"[平准] 粜粮 {_amt}石以抑米价，回收 {_cost}贯")
        elif state.grain_price < CHANGPING_LOW:
            want = int(effects["grain_stabilize"]) * 10000
            budget = int(state.treasury // max(state.grain_price, 0.4))
            # 审查 P0：平籴 = 政府买粮托市（民间售粮得钱），钱粮守恒
            _amt, _cost = _state_grain_trade(state, min(want, budget), "buy",
                                             state.grain_price, log, "平准")
            if _amt > 0:
                log.append(f"[平准] 籴粮 {_amt}石以托米价")

    # 文档第八节白名单所列、此前在 _apply_decree_effect 中缺失的键：补齐以免 AI 拟诏被静默丢弃
    if "army_strength" in effects:
        # 全军员额增益：按各军现有兵力比例分摊（整训/整编）
        # 审查修复：u.troops 为只读 property（真账=Σbranches），须经 add_troops 落分支
        # —— 这一点原已修；但增兵**无人口来源**（此前不计来源直接加人），而本步之后
        # _settle_finance 会以 Σbranches 重聚合兵 POP、并把 ΣPOP 写回 population
        # → 诏令一句即凭空产生数万「人」（最多可为每军 +50% 员额）。
        # 现改为自本路农户／流民成对征补（_levy_men），不足则少增，不造人。
        bonus = int(effects["army_strength"])
        total_troops = sum(u.troops for u in state.army_units) or 1
        _want = max(0, bonus)
        _recruited = 0
        for u in state.army_units:
            if _want <= 0:
                break
            _ask = (min(int(u.troops * 1.5), u.troops + int(bonus * u.troops / total_troops))
                    - u.troops)
            if _ask <= 0:
                continue
            _got = _levy_men(state, u.station, min(_ask, _want))
            if _got > 0:
                u.add_troops(_got)
                _recruited += _got
                _want -= _got
        if _recruited > 0:
            log.append(f"[整军] 诏令整训，自民户征补 {_recruited} 人，诸军战力益壮")
        elif state.army_units:
            log.append("[整军] 诏令整训，然民户无余丁可征，员额未增")
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
    """派系内部结算（12 步 agent 化 P2+：派系结算契约接线）"""
    # 12 步 agent 化 P2+：读取派系 AI 契约
    _faction_ai = getattr(state, "_faction_ai", None)
    ai_factions = {}
    ai_events = []
    if isinstance(_faction_ai, dict) and not _faction_ai.get("_error"):
        ai_factions = _faction_ai.get("factions", {})
        ai_events = _faction_ai.get("events", [])
        if _faction_ai.get("narrative"):
            log.append(f"[党争] {_faction_ai['narrative']}")

    # 派系满意度/影响力/立场自然演进 + AI 契约调制
    for name, f in state.factions.items():
        cohesion_delta = random.randint(-2, 2)
        f["cohesion"] = max(10, min(100, f["cohesion"] + cohesion_delta))

        # 基础满意度回归
        if f["satisfaction"] > 55:
            f["satisfaction"] = max(50, f["satisfaction"] - random.randint(0, 2))
        elif f["satisfaction"] < 45:
            f["satisfaction"] = min(50, f["satisfaction"] + random.randint(0, 1))

        inf_delta = random.randint(-1, 1)
        f["influence"] = max(5, min(100, f["influence"] + inf_delta))

        # AI 契约调制：按档位微调
        if name in ai_factions:
            ai_f = ai_factions[name]
            sat_tier = ai_f.get("satisfaction", "小")
            inf_tier = ai_f.get("influence", "小")
            stance = ai_f.get("stance", "观望")

            # 满意度档位映射
            sat_map = {"微": 1, "小": 2, "中": 4, "大": 6}
            inf_map = {"微": 1, "小": 2, "中": 3, "大": 5}

            sat_delta = sat_map.get(sat_tier, 2)
            inf_delta = inf_map.get(inf_tier, 2)

            # 立场决定方向
            if stance == "进取":
                f["satisfaction"] = min(100, f["satisfaction"] + sat_delta)
                f["influence"] = min(100, f["influence"] + inf_delta)
            elif stance == "守成":
                f["satisfaction"] = max(0, f["satisfaction"] - sat_delta)
                f["influence"] = max(0, f["influence"] - inf_delta)
            # 观望：不额外调整

    # AI 契约事件
    for event in ai_events:
        etype = event.get("type", "")
        desc = event.get("desc", "")
        tier = event.get("tier", "小")
        if etype == "党争":
            log.append(f"[党争] {desc}")
            state.change_prestige(-2, "党争")
        elif etype == "联姻":
            log.append(f"[联姻] {desc}")
        elif etype == "分裂":
            log.append(f"[分裂] {desc}")
            state.change_prestige(-3, "派系分裂")
        elif etype == "和解":
            log.append(f"[和解] {desc}")
            state.change_prestige(2, "派系和解")
        elif etype == "清算":
            log.append(f"[清算] {desc}")
            state.change_prestige(-5, "派系清算")

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
    # 人口自然净增长（审查 2026-09 调参）：按在籍人口月化比率 + 死亡/疫病随机抖动，
    # 使长局人口稳中有升（原固定 randint(-5000,15000) 期望 +0.5 万/月，年化仅 0.075%）
    from content.data import POP_GROWTH_RATE, POP_GROWTH_JITTER
    growth = int(state.population * POP_GROWTH_RATE) + random.randint(-POP_GROWTH_JITTER, POP_GROWTH_JITTER)
    state.population = max(10_000_000, state.population + growth)
    _boom = (getattr(state, "_economy_ai", None) or {}).get("景气", "中")
    _exam_open = state.exam.get("open")
    # 增长分摊份额分母：各路在籍基准之和（恒定 = PREFECTURE_INFO population 合计 ≈8000 万）。
    # 不能用"增长后的动态 state.population"做分母——否则 Σshare<1，农流入比 growth 系统性
    # 少 growth²/总人口，破 ΔΣPOP==growth 守恒不变式（审查回归修复）。
    _pop_base_total = sum(p.get("population", 0) for p in state.prefectures.values()) or 1
    # 合并4次遍历为1次：人口增长分配 → POP职业流动 → 科举入仕 → 流民吸收
    for name, p in state.prefectures.items():
        pops = p["pops"]
        # 1) 人口自然增长/萎缩落到各路农 POP（农民为主，按各路人口比例摊）
        if growth != 0:
            share = p.get("population", 1) / _pop_base_total
            pops["农"]["size"] = max(0, pops["农"]["size"] + int(growth * share))
        # 2) POP 职业流动（AI 化·Phase B 定稿）：城市化/回乡档位 → 程序换算速率，net 流守恒。
        #    全游戏级强制 AI（拒绝式）：无 _economy_ai（经济推演未注入）→ 城市化/回乡/科举
        #    一律「无」（不流动、不伪造档位）；有推演才按档位流动。
        _eco = getattr(state, "_economy_ai", None) or {}
        _boom = _eco.get("景气", "中") if _eco else None

        def _flow_tier(key, fallback):
            v = _eco.get(key)
            return v if v in TIER_RANGE else fallback

        _tier_city = _flow_tier("城市化", "中" if _boom in ("中", "大") else "无")
        _tier_back = _flow_tier("回乡", "中" if _boom == "微" else "无")
        rate_city = POP_FLOW_RATE["城市化"] * TIER_RANGE.get(_tier_city, 0.0)
        rate_back = POP_FLOW_RATE["回乡"] * TIER_RANGE.get(_tier_back, 0.0)
        urban = round(pops["农"]["size"] * rate_city)
        back = round((pops["工匠"]["size"] + pops["商人"]["size"]) * rate_back)
        net = urban - back
        if net > 0:
            net = min(net, pops["农"]["size"])                 # 钳制：农不减负
            pops["农"]["size"] -= net
            pops["工匠"]["size"] += int(net * URBAN_SPLIT["工匠"])
            pops["商人"]["size"] += net - int(net * URBAN_SPLIT["工匠"])
        elif net < 0:
            _out = min(-net, pops["工匠"]["size"] + pops["商人"]["size"])  # 钳制：工/商不减负
            _art_out = min(int(_out * URBAN_SPLIT["工匠"]), pops["工匠"]["size"])
            pops["工匠"]["size"] -= _art_out
            pops["商人"]["size"] -= _out - _art_out
            pops["农"]["size"] += _out
        # 3) 科举入仕已改为**离散科次**（阶段 C-6，§15）：见 `core/officialdom._triennial_exam`
        #    —— 每 EXAM_INTERVAL_YEARS 年一次，一次入仕一批（数百人），落在**待阙**池。
        #    此处不再做每月连续小额入仕：那既不符合史实形态（一期数百进士），
        #    也让"同年/座主"这类真实政治结构无从表达。
        # 4) 流民吸收（跨路迁入，非本地农户流出）
        # 语义澄清（审查复核结论，勿按「方向反了」误改）：absorb 为**流入率**——
        # 治理良好（mood/govern 高、unrest 低）时吸引外来流民迁入本路，故写成
        # local + delta；其 cap（本路人口 5%）也只对流入成立。
        # 已知取舍：跨路迁入未与来源路配对（全局人口账因此非闭合），
        # tests/test_pop_identity.py 已将此列为「设计内·非闭合」科目并断言其公式。
        local = p.get("refugees", 0)
        if local > 0 or p.get("unrest", 15) >= 20:
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
    或（行一条鞭后）折银入国库。粮产率随科技/工业、田亩随开垦动态变化。
    （12 步 agent 化 P2+：田亩地方契约接线）"""
    # 12 步 agent 化 P2+：读取田亩地方 AI 契约
    _land_ai = getattr(state, "_land_local_ai", None)
    ai_prefs = {}
    if isinstance(_land_ai, dict) and not _land_ai.get("_error"):
        ai_prefs = _land_ai.get("prefectures", {})
        if _land_ai.get("narrative"):
            log.append(f"[田亩] {_land_ai['narrative']}")

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
        # AI 契约档位映射
        ai_pref = ai_prefs.get(name, {})
        survey_tier = ai_pref.get("survey", "小")
        reclaim_tier = ai_pref.get("reclaim", "小")
        tax_fair_tier = ai_pref.get("tax_fair", "小")
        ai_mood = ai_pref.get("mood", "平实")

        # 档位力度表（审查 P1：7 档闭环——原 4 档表缺 无/巨/极：
        # 无→默认 1.0 竟与「小」同效、巨/极→回落 1.0 低于「大」=档位倒挂）
        tier_map = {"无": 0.0, "微": 0.5, "小": 1.0, "中": 2.0, "大": 3.0,
                    "巨": 4.0, "极": 5.0}

        # 清丈力度（AI 契约加成）
        survey_boost = tier_map.get(survey_tier, 1.0)
        # 劝垦力度（AI 契约加成）
        reclaim_boost = tier_map.get(reclaim_tier, 1.0)
        # 均税力度（AI 契约加成）
        tax_fair_boost = tier_map.get(tax_fair_tier, 1.0)

        # 地方民情：AI 契约档位词 → 程序映射为数值（AI 只给定性，数值程序定）
        _mood_map = {"安定": 75, "平实": 55, "动荡": 35}
        if ai_mood in _mood_map:
            p["mood"] = _mood_map[ai_mood]

        tax = int(grain_by.get(name, 0))
        _land = max(float(p.get("land", 1)), 1.0)
        _nong, _shen = p["pops"]["农"], p["pops"]["士绅"]
        if _harvest:
            produce = int(p["grain"] / 3.0)
            _nong["grain"] += int(produce * p.get("self_farm_land", 0) / _land)          # 自耕田→自耕农
            _gp = int(produce * p.get("gentry_land", 0) / _land)
            _nong["grain"] += _gp // 2; _shen["grain"] += _gp // 2                      # 地主田→佃户半+士绅半
            _op = int(produce * p.get("official_land", 0) / _land)
            # 官田→佃户半 + 太仓半。
            # 审查修复（静默丢粮）：change_granary 有 cap 封顶，原未先查余量
            # → 满仓时该半份粮被 cap 吞掉且不留痕（漕运段已先算 room，此处对齐）。
            # 现按余量截断，仓不容者归佃户，粮量不凭空消失；统计只记实际入仓数。
            _op_half = _op // 2
            _room = max(0, int(getattr(state, "granary_cap", 1 << 30))
                        - int(getattr(state, "granary", 0) or 0))
            _op_in = min(_op_half, _room)
            _nong["grain"] += _op_half - _op_in
            if _op_in > 0:
                state.change_granary(_op_in)
                state.granary_stats["official"] = (
                    state.granary_stats.get("official", 0) + _op_in)
            _ip = int(produce * p.get("imperial_land", 0) / _land)
            _nong["grain"] += _ip // 2; state.imperial_granary += _ip // 2              # 皇庄→佃户半+内帑粮
            _shen["grain"] += int(produce * p.get("hidden_land", 0) / _land)            # 隐田→士绅(逃税)
        # 田赋按田亩归属征：自耕田→自耕农、地主田→士绅；官田皇庄免、隐田逃税
        _st = int(tax * p.get("self_farm_land", 0) / _land); _gt = int(tax * p.get("gentry_land", 0) / _land)
        # AI 契约：均税力度减轻赋税负担
        if tax_fair_boost > 1.0:
            _st = int(_st * (1.0 - min(0.2, tax_fair_boost * 0.05)))
            _gt = int(_gt * (1.0 - min(0.2, tax_fair_boost * 0.05)))
        if state.single_whip:
            # 一条鞭：田赋折银——粮留给民间，从农/士绅 wealth 按税粮比例征银入国库（守恒）
            price = max(float(state.grain_price), 0.1)
            silver_nong = int(_st * price)
            silver_shen = int(_gt * price)
            got_nong = state.transfer_money(f"pop:{name}:农", "treasury", silver_nong) if silver_nong else 0
            got_shen = state.transfer_money(f"pop:{name}:士绅", "treasury", silver_shen) if silver_shen else 0
            short = (silver_nong + silver_shen) - (got_nong + got_shen)
            if short > 0:
                _nong["欠税"] = int(_nong.get("欠税", 0)) + (silver_nong - got_nong)
                _shen["欠税"] = int(_shen.get("欠税", 0)) + (silver_shen - got_shen)
        else:
            _nong["grain"] = max(0, _nong["grain"] - _st)
            _shen["grain"] = max(0, _shen["grain"] - _gt)
            p["storage"] = p.get("storage", 0) + _st + _gt
        # 种粮（加消耗完整定案）：播种预留 = 耕地亩 × SEED_GRAIN_PER_MU / 12（石/月，约250万石/月），
        # 从农存粮扣（农户备种，真实粮耗不造币；口粮已改「纯口粮」口径防双计）
        _seed = int(p.get("land", 0) * SEED_GRAIN_PER_MU / 12.0)
        if _seed > 0:
            _nong["grain"] = max(0, _nong["grain"] - _seed)
            state.granary_stats["seed_grain"] = state.granary_stats.get("seed_grain", 0) + _seed
    if state.single_whip:
        if land_grain > 0:
            silver_total = int(land_grain * state.grain_price)
            state.statistics["total_income"] += silver_total
            log.append(f"[田赋·一条鞭] 两税折银（税粮当量 {land_grain}石）按 wealth 实征入国库，不足记欠税")
    else:
        state.granary_stats["tax"] += land_grain
        if land_grain > 0:
            log.append(f"[田赋] 两税本色征收粮 {land_grain}石，分储诸路仓廪（三运期各征 1/3 年产）")

    state.price_level = state.calc_price_level()
    state.grain_price = state.calc_grain_price()
    for name, p in state.prefectures.items():
        p["grain_price"] = state.calc_region_grain_price(name)
        target = state.population_satisfaction
        if p["mood"] > target:
            p["mood"] = max(target, p["mood"] - 1)
        elif p["mood"] < target:
            p["mood"] = min(target, p["mood"] + 1)
        p["govern"] = max(20, min(100, p["govern"] + random.randint(-1, 1)))
        p["grain"] = int(p["grain"] * 1.002)

    for yname, y in state.yamen.items():
        # 政务积压增长（§11.6 第一行）：原为 `random.randint(0, 3)` —— 一个**无载体的随机**，
        # 与"有司拖延"的成因完全脱钩。现改为 **净积压 = W − C_eff**：
        #   W     = 本路政务量（案牍件/月，见 core/clerks.route_workload）
        #   C_eff = 吏数 × (1 − 吏怨/100)，即"吏数够、但吏怨高 → 有效处理能力不足"
        # 于是「冗吏」与「积压」可以并存（§16.6 的史实悖论），且玩家有明确杠杆
        # （少下诏 / 裁并机构 / 增吏 / 治吏怨）。吏制不可用时退化为旧的随机项。
        try:
            from core.clerks import backlog_gain as _bg
            # 六部 yamen 与路的对应：近似按 yamen 名匹配路（无匹配则取全国均值增量）
            _route = yname if yname in state.prefectures else None
            if _route:
                _gain = _bg(state, _route)
            else:
                _gains = [_bg(state, r) for r in state.prefectures]
                _gain = sum(_gains) / max(1, len(_gains))
        except Exception:  # noqa: BLE001
            _gain = float(random.randint(0, 3))
        y["backlog"] = max(0, int(y["backlog"] + _gain - y["efficiency"] / 40))
        y["efficiency"] = max(20, min(100, y["efficiency"] + random.randint(-2, 1)))


def _settle_region_deepen(state, log):
    """地区模型深化月度结算（参考《明末：捞金模拟器》）。

    对每路补充字段做动态演化：
      - public_support（民心）：随 mood/unrest/治理度 演化；
      - gentry_resistance（士绅抵抗）：随清丈/抑兼并/士绅影响力 演化；
      - city_defense（城防）：随军备/边患 演化；
      - fiscal（财政）：随月税/支出 演化；
      - controlled_by（控制势力）：默认宋，领土争夺时由 AI/事件改写。
    轻量 O(路数)，不引入 N+1 查询；数值走既有 state 字段，不破坏守恒。
    """
    from content.data import PREFECTURE_TYPE_FRONTIER, PREFECTURE_TYPE_CAPITAL
    for name, p in state.prefectures.items():
        # 民心：随动乱与治理演化（mood 同源，向 mood 收敛）
        mood = p.get("mood", 50)
        unrest = p.get("unrest", 15)
        support = p.get("public_support", mood)
        # 动乱高则民心降，治理高则民心升
        drift = (mood - support) * 0.1 - (unrest - 15) * 0.05
        p["public_support"] = max(0, min(100, support + drift))

        # 2. 士绅抵抗：随士绅影响力与清丈力度演化
        gentry = p.get("gentry_resistance", 30)
        gentry_power = 0.0
        try:
            gentry_power = state.factions.get("东南士人", {}).get("influence", 50) / 100.0
        except Exception:
            pass
        # 清丈（land_survey 施行）则士绅抵抗上升；治理高则下降
        survey = 1.0 if state.land.get("survey_active") else 0.0
        gentry_drift = (gentry_power - 0.5) * 2 + survey * 2 - (p.get("govern", 50) - 50) * 0.02
        p["gentry_resistance"] = max(0, min(100, gentry + gentry_drift))

        # 3. 城防：随军备/边患演化（边镇自然加固，腹里缓慢）
        defense = p.get("city_defense", 40)
        p_type = p.get("type", "腹里州路")
        if p_type in PREFECTURE_TYPE_FRONTIER:
            defense_drift = 0.3
        elif p_type == PREFECTURE_TYPE_CAPITAL:
            defense_drift = 0.1
        else:
            defense_drift = -0.05
        p["city_defense"] = max(0, min(100, defense + defense_drift))

        # 4. 财政：随月税与支出演化（地方财政健康度）
        fiscal = p.get("fiscal", 50)
        monthly_tax = p.get("monthly_tax", 200_000)
        # 财政健康度向"月税充足"收敛
        fiscal_target = max(0, min(100, round(monthly_tax / 8000)))
        p["fiscal"] = fiscal + (fiscal_target - fiscal) * 0.05

        # 5. 控制势力：默认宋，领土争夺由事件/命令改写（此处不主动改）
        p.setdefault("controlled_by", "宋")


def _settle_extensions(state, log):
    """金融/科举/科技/外交 等扩展维度的自然演进。

    经济金融推演接入（蔡权衡定稿）：读 _economy_ai 金融 5 字段（三态词）→ 程序换算
    （FINANCE_DECIDE_BASE CAP 封顶），守恒由既有公式（交子超发崩溃/市舶关税/钱荒联动
    tax_coeff）保证——AI 只给方向词，不触碰守恒数值。
    """
    _fin = getattr(state, "_economy_ai", None) or {}
    _bank_on = getattr(state, "bank", {}).get("established", False) \
        if isinstance(getattr(state, "bank", None), dict) else False

    _fdb = FINANCE_DECIDE_BASE   # 审查 P2-53：金融调制幅度/值域唯一权威源
    if state.jiaozi["issued"] > 0:
        _ceiling = state._jiaozi_ceiling()                    # 可发额度 = 准备金 × 准备金率（皇威放宽）
        over = max(0, state.jiaozi["issued"] - _ceiling)
        # 金融调制（交子信任/发行——三态词，CAP ±5 / +100万）
        _jt_cfg = _fdb["jiaozi_trust"]
        _jt = _fin.get("jiaozi_trust", "稳")
        if _jt == "增":
            state.jiaozi["trust"] = min(_jt_cfg["max"], state.jiaozi["trust"] + _jt_cfg["cap"])
        elif _jt == "跌":
            state.jiaozi["trust"] = max(_jt_cfg["min"], state.jiaozi["trust"] - _jt_cfg["cap"])
        if _fin.get("jiaozi_issued") == "增" and over <= 0:
            # 增发须 ≤ 可发额度（超发由下方既有超发逻辑触发崩溃）
            _add = min(_fdb["jiaozi_issued"]["cap"], max(0, _ceiling - state.jiaozi["issued"]))
            if _add > 0:
                state.jiaozi["issued"] += _add
        over = max(0, state.jiaozi["issued"] - _ceiling)
        if over > 0:
            # 超发→信用崩（trust 降，贬值）+ 铜钱被挤兑囤积→钱荒加剧；皇威高可减缓贬值
            _prestige_factor = 2.0 - state.prestige / 50.0   # 皇威 0→2.0倍(快崩), 100→0(不崩)
            state.jiaozi["trust"] = max(0, state.jiaozi["trust"] - int(over / 1_000_000 * 10 * max(0.0, _prestige_factor)))
            state.coin["shortage"] = min(0.9, state.coin.get("shortage", 0.3) + 0.01)
        else:
            # 适量发钞→缓解钱荒（纸币替代铜钱，铜钱流通压力减）
            state.coin["shortage"] = max(0.1, state.coin.get("shortage", 0.3) - 0.005)
    # 钱荒调制（缓/加剧 ±0.05，clamp [0.05,0.95]；联动 tax_coeff 由 finance 既有公式）
    _sh_cfg = _fdb["shortage"]
    _sh = _fin.get("shortage", "平")
    if _sh == "缓":
        state.coin["shortage"] = max(_sh_cfg["min"], state.coin.get("shortage", 0.3) - _sh_cfg["cap"])
    elif _sh == "加剧":
        state.coin["shortage"] = min(_sh_cfg["max"], state.coin.get("shortage", 0.3) + _sh_cfg["cap"])
    if state.maritime["open"]:
        # 市舶外贸：关税抽解入国库 + 商人 POP 得外贸利润（白银流入民间）
        _trade_month = state.calc_maritime_trade() / 12.0                     # 月贸易额（贯）
        # 市舶调制（兴/衰：tariff ±0.02 clamp [0.05,0.20]、silver_in ±10 clamp [10,60]）
        _tf_cfg, _sv_cfg = _fdb["tariff"], _fdb["silver_in"]
        _mt = _fin.get("maritime", "平")
        if _mt == "兴":
            state.maritime["tariff"] = max(_tf_cfg["min"], min(
                _tf_cfg["max"], state.maritime.get("tariff", 0.10) + _tf_cfg["cap"]))
            state.maritime["silver_in"] = max(_sv_cfg["min"], min(
                _sv_cfg["max"], state.maritime.get("silver_in", 30) + _sv_cfg["cap"]))
        elif _mt == "衰":
            state.maritime["tariff"] = max(_tf_cfg["min"], min(
                _tf_cfg["max"], state.maritime.get("tariff", 0.10) - _tf_cfg["cap"]))
            state.maritime["silver_in"] = max(_sv_cfg["min"], min(
                _sv_cfg["max"], state.maritime.get("silver_in", 30) - _sv_cfg["cap"]))
        _tariff_rate = state.maritime.get("tariff", 0.10)
        # B1 修复（市舶关税重复计账）：关税的**唯一**入账通道是 _settle_finance
        # （从商人 POP wealth 征收并入 actual_tax → 国库，钱守恒）。此处原再
        # `state.treasury += 关税` 属第二次全额入账且无对手账户（凭空增币），
        # 使国库市舶收入被系统性放大近一倍。只保留商人外贸利润分配与白银流入。
        _merchant_profit = int(_trade_month * (1 - _tariff_rate) * 0.3)       # 商人毛利 30%
        _total_merchant = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
        for _p in state.prefectures.values():
            if _p["pops"]["商人"]["size"] > 0:
                _p["pops"]["商人"]["wealth"] += int(_merchant_profit * _p["pops"]["商人"]["size"] / _total_merchant)
        state.coin["shortage"] = max(0.0, state.coin["shortage"] - 0.01)      # 白银流入缓解钱荒
        # 白银**存量**累积（阶段 B-1）：silver_in 是「万两/年」的**流量**，此前只被
        # calc_price_level 当作白银存量 ×10000 使用，**从未进入任何持有账户**——
        # 既是"把流量当存量"的建模错误，也是货币对账里一笔无对手方的注入。
        # 现按 1/12 月度份额累积进 `state.silver_stock`（外部注入的唯一合法入口，
        # 供 core/money.py 对账时作为外部项扣除）。**不改动任何既有数值**：
        # calc_price_level 仍读 silver_in，silver_stock 在阶段 B-1 只被 money.py 读取。
        try:
            _sv_annual = float(state.maritime.get("silver_in", 0) or 0) * 10000.0   # 万两/年 → 贯/年
            state.silver_stock = int(getattr(state, "silver_stock", 0) or 0) + int(_sv_annual / 12.0)
        except Exception:  # noqa: BLE001 — 对账辅助字段，失败不影响结算
            pass
    # 银行调制（扩/损——仅 established；capital ±20%、reserve +50万）
    if _bank_on:
        _bk_cfg, _br_cfg = _fdb["bank_capital"], _fdb["bank_reserve"]
        _bk = _fin.get("bank", "稳")
        if _bk == "扩":
            state.bank["capital"] = state.bank.get("capital", 1.0) * _bk_cfg["up"]
            state.bank["reserve"] = state.bank.get("reserve", 0) + _br_cfg["cap"]
        elif _bk == "损":
            state.bank["capital"] = state.bank.get("capital", 1.0) * _bk_cfg["down"]
            state.bank["reserve"] = max(_br_cfg["min"], state.bank.get("reserve", 0) - _br_cfg["cap"])
    state.jiaozi["trust"] = min(100, state.jiaozi["trust"] + 1)
    # 价格系数调制（通胀/通缩 ±5%，挂 calc_price_level ×mult，clamp [0.5,3.0]；月度重置不落档）
    _pm_cfg = _fdb["price_mult"]
    _pt = _fin.get("price_trend", "平")
    _pm = getattr(state, "_price_mult", 1.0)
    if _pt == "通胀":
        _pm = max(_pm_cfg["min"], min(_pm_cfg["max"], _pm * _pm_cfg["up"]))
    elif _pt == "通缩":
        _pm = max(_pm_cfg["min"], min(_pm_cfg["max"], _pm * _pm_cfg["down"]))
    state._price_mult = _pm
    # 大臣家产月度循环（奢侈消费/收租/聚敛窖藏/物议——守恒转移）
    try:
        from core.estate_mechanic import settle_minister_estate
        settle_minister_estate(state, log)
    except Exception:
        pass
    # 投资分期回报（国库/内帑回流，守恒）
    try:
        from core.estate_mechanic import settle_investments
        settle_investments(state, log)
    except Exception:
        pass
    # 建筑-时代交互（言枢密方案）：下行联动（建筑累积到 era_state 五维）
    try:
        from core.era_mechanic import settle_era_links
        settle_era_links(state, log)
    except Exception:
        pass
    # 新旧产业规模化（用户指示）：转型阵痛叙事 + 记忆记录
    try:
        from core.era_mechanic import settle_industry_shift
        settle_industry_shift(state, log)
    except Exception:
        pass

    state.exam["talent_pool"] = max(0, min(100, state.exam["talent_pool"]
                                           - 1 + int(state.exam["schools"] / 40)))

    state.tech["level"] = max(0, min(100, state.tech["level"] + random.randint(-1, 1)))
    # 建筑反馈科技（用户指示）：学校/书院 → 科技研发加速（tech level 加成）
    try:
        from core.era_mechanic import tech_build_bonus
        _tb = tech_build_bonus(state)
        if _tb > 0:
            # 审查 P2-25 修复：tech_build_bonus 返回浮点（Σ学校等级×0.05），原 `int(_tb)`
            # 把 <1 的加成恒截断为 0（5 所学校 Lv1 → 0.25 → 0，学校加成基本永不生效）。
            # 现累积到小数池，满 1 兑现 1 点科技等级（无截断浪费）。
            _pool = float(state.tech.get("_build_bonus_pool", 0.0) or 0.0) + _tb
            _gain = int(_pool)
            state.tech["_build_bonus_pool"] = round(_pool - _gain, 4)
            if _gain > 0:
                state.tech["level"] = max(0, min(100, state.tech["level"] + _gain))
    except Exception:
        pass
    state.tech["gunpowder"] = max(0, min(100, state.tech["gunpowder"] + random.randint(-1, 1)))
    state.tech["iron"] = max(0, min(100, state.tech["iron"] + random.randint(0, 1)))
    if getattr(state, "maritime", {}).get("open"):
        state.tech["west"] = max(0, min(5, state.tech["west"] + 0.01))
    _settle_tech_research(state, log)

    # ---- T9 物价方案：交子界制销币（Step 3.6 扩展）----
    # 一界 JIAOZI_TERM=36 回合；到界换发新钞，按在发额 JIAOZI_REDEEM_FEE=5% 工墨费销毁
    # （**销币通道**：回收流通货币抑通胀）；超界未换部分作废（退出流通）。
    # 换界销毁记 statistics["jiaozi_redeemed"] + jiaozi.redeemed_total（审计/断言用）。
    _settle_jiaozi_term(state, log)

    # ---- T9 物价方案：私铸熔化真实化（Step 3.8 前）----
    # 民间铜钱逐月真实熔化：各 POP wealth 按 MELT_RATE=0.1%/月扣减退出流通
    # （非一次性 private_melt 系数，真实逐月衰减；private_melt 已 0.2→0.1 用于物价公式）。
    _settle_coin_melt(state, log)


def _settle_jiaozi_term(state, log):
    """交子界制：满一界换发新钞（5% 工墨费销毁）+ 超界作废（销币，抑通胀）。

    守恒：销毁额 = issued × JIAOZI_REDEEM_FEE（退出流通，不入任何账户）；
    换界不新增发行（以旧换新，issued 保持流通额）。
    """
    from content.data import JIAOZI_TERM, JIAOZI_REDEEM_FEE
    jz = state.jiaozi
    if jz.get("issued", 0) <= 0:
        return
    jz["age"] = jz.get("age", jz.get("term_progress", 0)) + 1
    if jz["age"] < JIAOZI_TERM:
        return
    # 到界：换发新钞，5% 工墨费销毁（销币），issued 缩水；统计留痕
    _burn = int(jz["issued"] * JIAOZI_REDEEM_FEE)
    jz["issued"] = max(0, jz["issued"] - _burn)
    jz["cycle"] = jz.get("cycle", 0) + 1
    jz["age"] = 0
    jz["redeemed_total"] = jz.get("redeemed_total", jz.get("burned_total", 0)) + _burn
    state.statistics["jiaozi_redeemed"] = state.statistics.get("jiaozi_redeemed", 0) + _burn
    log.append(f"[交子] 第{jz['cycle']}界届满，换发新钞，工墨费销毁 {_burn}贯（销币抑价）")


def _settle_coin_melt(state, log):
    """私铸熔化真实化：民间铜钱逐月真实熔化扣减（退出流通，抑通胀）。

    各 POP wealth 按 MELT_RATE 比例扣减（0.1%/月）；扣减额**转入熔铜池**
    （state.coin["melted_pool"]，钱变铜料，守恒成立不凭空消失）；熔铜池**不在
    money 公式**（calc_price_level 只加 pop_wealth/treasury/imperial/jiaozi/silver），
    故真实退出流通；熔铜池供铸钱（_settle_mint 从池取料，闭环）。
    不碰国库/内帑（国家持币不熔化）。
    """
    # 审查修复（A1）：COPPER_RESOURCE_DIM 只在 _settle_mint 内局部导入，本函数
    # 熔铜池溢出分支（下方 >1 亿贯）却直接使用该名 → 一旦触发即 NameError，
    # 中断整月结算。此处与 _settle_mint 一致一并导入。
    from content.data import MELT_RATE, COPPER_RESOURCE_DIM
    if MELT_RATE <= 0:
        return
    _melted = 0
    for p in state.prefectures.values():
        for pop in p.get("pops", {}).values():
            w = float(pop.get("wealth", 0))
            if w > 0:
                _take = int(w * MELT_RATE)
                if _take > 0:
                    pop["wealth"] = max(0, w - _take)
                    _melted += _take
    if _melted > 0:
        # 熔铜池：钱变铜料（守恒），不在 money 公式（退出流通）
        state.coin["melted_pool"] = state.coin.get("melted_pool", 0) + _melted
        state.statistics["coin_melted"] = state.statistics.get("coin_melted", 0) + _melted
        # 熔铜池出口（备选·蔡权衡）：池 > 阈值（1 亿贯）→ 自动入 resources["铜"]
        # （防只进不出；铜料可被铸钱/建筑消耗回流）
        _pool = state.coin.get("melted_pool", 0)
        if _pool > 100_000_000:
            _overflow = _pool - 100_000_000
            state.coin["melted_pool"] = 100_000_000
            _res = getattr(state, "resources", None)
            if _res is None:
                _res = {}
                state.resources = _res
            # 审查修复（schema 破坏 + 口径断链）：原写 _res["铜"] = int，而
            # state.resources 的 schema 是 {dim: {"stock","cap"}} → 引入非 dict 值，
            # 任何 resources[x]["stock"] 形式的访问一旦命中即崩；且 "铜" 不在
            # RESOURCE_DIMS、铸钱侧只认 COPPER_RESOURCE_DIM(=iron) → 该铜料
            # 永不会被消耗。现并入铸钱所用铜料维（按 cap 截断，余量留池）。
            _slot = _res.get(COPPER_RESOURCE_DIM)
            if not isinstance(_slot, dict):
                _slot = {"stock": 0, "cap": 0}
                _res[COPPER_RESOURCE_DIM] = _slot
            _cap = int(_slot.get("cap", 0) or 0)
            _cur = int(_slot.get("stock", 0) or 0)
            _room = max(0, _cap - _cur) if _cap > 0 else _overflow
            _taken = min(_overflow, _room)
            _slot["stock"] = _cur + _taken
            # 未入仓者仍留熔铜池（不凭空消失）
            state.coin["melted_pool"] = 100_000_000 + (_overflow - _taken)
            state.statistics["copper_recycled"] = (
                state.statistics.get("copper_recycled", 0) + _taken)
        log.append(f"[私铸] 民间铜钱熔化 {_melted}贯（铸器外流，入熔铜池）")


# 兼容别名（并行契约曾用 _settle_melt_copper/_settle_jiaozi_cycle；保留双向可用）
_settle_jiaozi_cycle = _settle_jiaozi_term
_settle_melt_copper = _settle_coin_melt


def _settle_stabilizer_recycle(state, log):
    """稳定器净回收公式（T9 定稿·蔡权衡）：月销币目标 = money × (price−1.2)/price × 0.5。

    通道联动：平粜吸钱入 local_treasury（货币回收，不碰内帑）→ 评估回收目标达成度；
    local_treasury 不在 money 公式（calc_price_level 只计 pop_wealth+treasury+imperial），
    故平粜回收**真实退出流通**（不回流物价公式），是纯销币通道。
    """
    from content.data import STABILIZER_RECYCLE_RATE, CHANGPING_PRICE_TARGET_LOW
    _price = state.grain_price
    if _price <= CHANGPING_PRICE_TARGET_LOW:
        return
    # 回收目标只基于**民间持币**（POP wealth）——内帑/国库膨胀不触发回收（T9 定稿：
    # 内帑抽流通不影响物价公式分母，故不参与销币目标；民间购买力才是通胀之源）。
    _money = 0.0
    for _p in state.prefectures.values():
        for _pop in _p.get("pops", {}).values():
            _money += max(0.0, float(_pop.get("wealth", 0)))
    _target = int(_money * (_price - CHANGPING_PRICE_TARGET_LOW) / max(_price, 1e-6) * STABILIZER_RECYCLE_RATE)
    if _target <= 0:
        return
    # 评估：本月经常平平粜实际回收（local_treasury 增量）——仅记录达成度（不强制追平，
    # 由粜量扩容与交子换界/熔化通道共同作用；物价封顶由 calc_price_level 的 PRICE_CEIL_HARD 保证）
    _recycled = int(getattr(state, "_stabilizer_recycled", 0) or 0)
    state.statistics["stabilizer_target"] = state.statistics.get("stabilizer_target", 0) + _target
    state.statistics["stabilizer_recycled"] = state.statistics.get("stabilizer_recycled", 0) + _recycled
    if _recycled >= _target:
        log.append(f"[稳定器] 净回收目标 {_target}贯已达成（销币抑价）")


def _settle_mint(state, log, amount: int = 0):
    """铸钱受控（T9 定稿）：铜资源约束 + 熔耗 20% 净增 80% + 物价>2.0 禁止。

    供诏令/工具调用（铸钱请求 amount 贯）：校验物价上限与金属资源存量，
    熔耗 20%（MINT_MELT_LOSS）→ 净增 80%（MINT_NET_RATIO）入民间流通（工匠/商人 wealth）。
    返回 (ok, message)。
    """
    from content.data import (MINT_MELT_LOSS, MINT_NET_RATIO, MINT_PRICE_BAN,
                              COPPER_RESOURCE_DIM)
    if state.price_level > MINT_PRICE_BAN:
        return False, f"物价 {state.price_level:.2f} 高于 {MINT_PRICE_BAN}，禁铸钱（防助涨通胀）"
    if amount <= 0:
        return False, "铸钱量须为正"
    # 金属料：优先熔铜池（熔化回收的铜料，闭环），不足回退 resources 存量
    _pool = int(state.coin.get("melted_pool", 0) or 0)
    _res = state.resources.get(COPPER_RESOURCE_DIM, {})
    _metal = _pool + int(_res.get("stock", 0) or 0)
    # 金属需求 = 铸钱额 / 净增率（含熔耗；熔耗 20% 时需金属 = 额 / 0.8）
    _need_metal = int(amount / MINT_NET_RATIO)
    if _metal < _need_metal:
        return False, f"铜料不足：需 {_need_metal} 单位（熔铜池+存 {_metal}），铸钱受阻"
    # 先耗熔铜池，再耗 resources（守恒：wealth→池→铸钱→wealth 闭环）
    _from_pool = min(_pool, _need_metal)
    state.coin["melted_pool"] = _pool - _from_pool
    if _need_metal > _from_pool:
        _res["stock"] = max(0, int(_res.get("stock", 0) or 0) - (_need_metal - _from_pool))
    _net = int(amount * MINT_NET_RATIO)          # 净增 80%（20% 熔耗蒸发，退出流通）
    _total = sum(p["pops"]["工匠"]["size"] + p["pops"]["商人"]["size"]
                 for p in state.prefectures.values()) or 1
    _art_total = sum(p["pops"]["工匠"]["size"] for p in state.prefectures.values()) or 1
    _mer_total = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
    for _p in state.prefectures.values():
        if _p["pops"]["工匠"]["size"] > 0:
            _p["pops"]["工匠"]["wealth"] += int(_net * 0.5 * _p["pops"]["工匠"]["size"] / _art_total)
        if _p["pops"]["商人"]["size"] > 0:
            _p["pops"]["商人"]["wealth"] += int(_net * 0.5 * _p["pops"]["商人"]["size"] / _mer_total)
    state.statistics["minted"] = state.statistics.get("minted", 0) + _net
    log.append(f"[铸钱] 熔铜铸钱 {amount}贯（熔耗 {amount - _net}贯，净增 {_net}贯入市）")
    return True, f"铸钱 {_net}贯入市（熔耗 {amount - _net}贯）"


def _settle_tech_research(state, log):
    """按月推进所有攻关中科技节点，满进度点亮并入资产。"""
    from core.asset_context import unlock_node, tech_cost_with_era, get_tech_node
    tech = state.tech
    researching = tech.get("researching", {})
    if not researching:
        return
    for node_id, r in list(researching.items()):
        node = get_tech_node(node_id)
        if node is None:
            # 承接模式：玩家注册节点兼容
            try:
                from core.registries import node_entry
                node = node_entry(state, node_id)
            except Exception:
                node = None
        if not node:
            researching.pop(node_id, None)
            continue
        cost = tech_cost_with_era(node, int(tech.get("era", 0)))
        # P1 修复（蔡权衡·超时代软约束递增）：第 N 个超时代节点研发成本 ×(1+0.1×(N-1))
        # （era ≥4 的超时代节点；防一口气全研，与工具注册软约束同构）
        if int(node[2]) >= 4:
            _n = sum(1 for nid in tech.get("unlocked", [])
                     if (lambda nd: nd and int(nd[2]) >= 4)(get_tech_node(nid)))
            from core.registries import soft_cost_mult
            _mult = soft_cost_mult(_n)
            cost = {k: (int(v * _mult) if isinstance(v, (int, float)) else v)
                    for k, v in cost.items()}
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
            # 承接模式：玩家投入（invest_silver/grain）加速推进 + west 跨时代加速因子
            _invest = max(0, float(r.get("invest_silver", 0)))
            if _invest > 0:
                rate *= 1 + min(2.0, _invest / 1_000_000.0)
            _west = int(tech.get("west", 0))
            if _west > 0:
                rate *= 1 + _west * 0.10   # west 保留为跨时代加速因子（×1+west×0.1）
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
            # 记忆知识库（Phase 3a）：任务推进写入图谱（progresses）
            try:
                tname = task.get("task_name", "政务")
                state.memory.add_entity(f"task_{tname}", "task", tname, turn=state.turn)
                state.memory.add_relation(f"task_{tname}", f"progress_{int(task['progress'])}",
                                          "progresses", weight=1.0, turn=state.turn,
                                          note=f"{label}进度{int(task['progress'])}%")
            except Exception:
                pass
            if task["progress"] >= 100:
                queue.remove(task)
                log.append(f"[{label}] {task.get('task_name', '政务')} 告成，钦此。")

    _progress(getattr(state, "longterm_public", []), "公开事务")
    _progress(getattr(state, "longterm_secret", []), "密令")
    # free_effect 长期制度（言枢密 v3 契约）：「长期诏」步位旁月度结算
    from core.free_effect import _settle_free_effects  # 延迟导入，避免顶层环
    _settle_free_effects(state, log)


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
        # 记忆知识库（Phase 3a）：外部政权态度推演写入图谱（stance）
        try:
            state.memory.add_entity(f"external_{key}", "external_power", key, turn=state.turn)
            state.memory.upsert_relation(f"external_{key}", "宋", "stance",
                                         weight=1.0 + att / 100.0, turn=state.turn,
                                         note=f"态度{att}")
        except Exception:
            pass
        # 审查 2026-09：六阶 POP 与省份运行态随国人口/兵额演化（参与月度结算）。
        #   - 国 population(万) 变化 → pop 各阶层 size 等比重算；
        #   - 省份人口/兵力按权重与国一致重摊；
        #   - 与外邦交战（treaty "_at_war"）或态度恶劣时，兵 POP 与省兵力月耗减（战争损耗）。
        try:
            from content.data import external_pop_shares
            _sh = external_pop_shares(str(ex.get("type", "")))
            _total = max(0, int(ex.get("population", 0))) * 10000
            pop = ex.get("pop")
            if not isinstance(pop, dict):
                pop = {}
                ex["pop"] = pop
            for _kl, _share in _sh.items():
                _sz = int(_total * _share)
                _slot = pop.setdefault(_kl, {"size": 0, "wealth": 0, "grain": 0})
                _slot["size"] = _sz
            _troops_total = int(_total * _sh.get("兵", 0))
            # 战争损耗：交战(sui_x bian/战争标记) 或态度<30 的敌意国，兵 P OP/省兵力每月损耗 0.5%
            # 战争损耗：交战（diplomacy_treaty 战争标记 state._at_war）或态度<30 的敌意国，
            # 兵 POP/省兵力每月损耗 0.5%（进攻方国力/人口亦受战损影响，参与结算）
            _at_war = bool((getattr(state, "_at_war", {}) or {}).get(key))
            _hostile = att < 30
            if _at_war or _hostile:
                _loss = max(1, int(_troops_total * 0.005))
                _troops_total = max(0, _troops_total - _loss)
                _bs = pop.get("兵") or pop.setdefault("兵", {"size": 0, "wealth": 0, "grain": 0})
                _bs["size"] = max(0, _bs.get("size", 0) - _loss)
            provinces = ex.get("provinces")
            provinces = ex.get("provinces")
            if isinstance(provinces, list):
                _tot_w = sum(p.get("weight", 1.0) for p in provinces) or 1.0
                for _p in provinces:
                    _w = float(_p.get("weight", 0)) / _tot_w
                    _p["population"] = int(_total * _w)
                    _p["troops"] = int(_troops_total * _w)
                # 兵 POP 对齐 Σ省兵力（int 截断差归零，三元一致）
                _eb = ex.setdefault("pop", {}).get("兵")
                if isinstance(_eb, dict):
                    _eb["size"] = sum(int(p.get("troops", 0) or 0) for p in provinces)
            # 军队实体化同步：每支军队按其驻地省份 troops 重算 branches/兵额，
            # 与省兵力、兵 POP 三元一致（损耗/扩张后同步）。
            _armies = ex.get("armies")
            if isinstance(_armies, list) and isinstance(provinces, list):
                _prov_by_name = {p.get("name"): int(p.get("troops", 0) or 0) for p in provinces}
                for _a in _armies:
                    _target = int(_prov_by_name.get(_a.get("station"), 0))
                    if _target <= 0:
                        _a["branches"] = {}
                        _a["troops"] = 0
                        continue
                    _br = _a.get("branches") or {}
                    _cur = sum(_br.values())
                    _scale = (_target / _cur) if _cur > 0 else 0.0
                    _nb = {k: int(v * _scale) for k, v in _br.items()}
                    _d = _target - sum(_nb.values())
                    if _d and _nb:
                        _nb[max(_nb, key=_nb.get)] = max(0, _nb[max(_nb, key=_nb.get)] + _d)
                    _nb = {k: n for k, n in _nb.items() if n > 0}
                    if not _nb and _target > 0:
                        _nb = {(_a.get("tier") or "轻步兵"): _target}
                    _a["branches"] = _nb
                    _a["troops"] = sum(_nb.values())
        except Exception:
            pass


# ------------------------------------------------------------
# Step 3.8: 仓廪漕运
# ------------------------------------------------------------
def _settle_granary(state, log):
    """仓廪系统月度结算：漕运汇聚 + 雀鼠耗 + 本色支取 + 常平仓 + 认知层。
    （12 步 agent 化 P2+：仓廪漕运契约接线）"""
    # 12 步 agent 化 P2+：读取仓廪漕运 AI 契约
    _granary_ai = getattr(state, "_granary_ai", None)
    ai_granary = {}
    if isinstance(_granary_ai, dict) and not _granary_ai.get("_error"):
        ai_granary = _granary_ai.get("granary", {})
        if _granary_ai.get("narrative"):
            log.append(f"[仓漕] {_granary_ai['narrative']}")

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

    # AI 契约档位映射（审查 P1：7 档闭环——原 4 档表 无→1.0 错当「小」执行、
    # 巨/极→回落 1.0 低于「大」=档位倒挂）
    tier_map = {"无": 0.0, "微": 0.5, "小": 1.0, "中": 1.5, "大": 2.0,
                "巨": 2.5, "极": 3.0}
    inflow_tier = ai_granary.get("inflow", "小")
    outflow_tier = ai_granary.get("outflow", "小")
    price_stabilize_tier = ai_granary.get("price_stabilize", "小")
    army_supply_tier = ai_granary.get("army_supply", "小")

    inflow_mult = tier_map.get(inflow_tier, 1.0)
    outflow_mult = tier_map.get(outflow_tier, 1.0)
    price_stabilize_mult = tier_map.get(price_stabilize_tier, 1.0)
    army_supply_mult = tier_map.get(army_supply_tier, 1.0)

    # 三运制：漕运非月月进行——一年分春(3月)/夏(6月)/秋(9月)三个运期，
    # 运期当月发纲集中上供，其余月份不发纲（史实纲运节奏：岁漕三运）。
    if state.month in (3, 6, 9):
        canal_eff = CANAL_MONTHLY_RATE * (1.0 - block / 100.0) * inflow_mult
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

    # AI 契约：雀鼠耗（outflow 档位调制）
    sparrow = int(state.granary * SPARROW_RAT * outflow_mult)
    if sparrow > 0:
        state.granary = max(0, state.granary - sparrow)
        state.granary_stats["sparrow"] += sparrow
        log.append(f"[雀鼠耗] 仓储月耗 {sparrow}石（存粮折损）")

    pay = state.pay_system.get("grain_ratio", 0.5)
    # 兵口粮联动（蔡权衡定案）：军粮实发按「禁/厢加权实发 + 乡兵缺口自备」口径
    # （乡兵军粮自备，太仓不造粮），故用 calc_army_grain(for_issue=True)
    army_grain_total, _ = state.calc_army_grain(for_issue=True)
    # AI 契约：军粮保障档位调制
    mil_grain = int(army_grain_total * pay * army_supply_mult)
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
    # 记录**实际**扣减额（供面板与账本测试读取）。此前测试改为"事后复算"同一条公式，
    # 但复算点在月内的位置与这里不同（官额会因科举在月内变化）→ 会算出 42 石的假残差。
    # 账本测试必须读**台账记录的实扣额**，而不是在别处重算派生量。
    state.granary_stats["corruption_grain"] = \
        state.granary_stats.get("corruption_grain", 0) + corr_actual
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
    # T9 常平扩容为货币稳定器：平粜吸买家钱入地方府库（货币回收，不碰内帑；
    # local_treasury 不在 money 公式）。净回收联动：价>2.0 时平粜量上限 60%，
    # 并评估稳定器净回收目标（月销币目标 = money×(price−1.2)/price×0.5）。
    from content.data import (CHANGPING_BUY_BUDGET_RATIO, CHANGPING_CAP_RATIO,
                              CHANGPING_SELL_RATIO, CHANGPING_PRICE_TARGET_HIGH,
                              CHANGPING_PRICE_TARGET_LOW, PRICE_TARGET_SUPER)
    _sell_ratio = CHANGPING_SELL_RATIO          # 0.60（价>2.0 档，原 0.45）
    _recycled_total = 0                          # 本月平粜回收累计（稳定器达成度）
    for name, p in state.prefectures.items():
        price = p.get("grain_price", state.grain_price)
        cp_stock = p.get("changping_stock", 0)
        coffer = p.get("local_treasury", 0)
        if price > CHANGPING_HIGH and cp_stock > 0:
            # 平粜（高价抑价）：放常平仓粮入市，钱入地方府库（货币回收，不碰内帑）。
            # 量随价格超幅线性放大：price 1.6→放 5% 常平储、2.5→放 60%（T9 扩容 45%→60%）
            # 审查修复：原实现对手方未建模（粮凭空消失、钱凭空产生），
            # 现经 _changping_trade 与本路民间 POP 成对划转（买不起则少卖）。
            ratio = min(_sell_ratio, (price - CHANGPING_HIGH) * 0.5)
            sell = max(1, int(cp_stock * ratio))
            sell = min(sell, cp_stock)
            _g, _recycled = _changping_trade(p, name, sell, "sell", price, log, "常平")
            if _g > 0:
                _recycled_total += _recycled
                # 对账统计：平粜回收（买家钱入地方府库）
                state.statistics["changping_recycled"] = (
                    state.statistics.get("changping_recycled", 0) + _recycled)
                # 放粮入市 → 当地粮价回落（常平抑价的正确触发）
                p["grain_price"] = _recalc_region_price(state, name, extra_supply=_g)
                changping_acted = True
        elif price < CHANGPING_LOW and coffer > 0:
            # 平籴（低价托市）：动用地方府库 50% 预算买粮入常平仓（T9 扩容 30%→50%）。
            # 量不超过当地月供一半，且受常平仓容（月产 100%，T9 扩容 50%→100%）约束，防止无上限膨胀
            budget = int(coffer * CHANGPING_BUY_BUDGET_RATIO)
            monthly_supply = max(p.get("grain", 0) / 12.0, 1.0)
            cap = max(monthly_supply * CHANGPING_CAP_RATIO, 1.0)
            room = max(0, int(cap - cp_stock))
            buy = min(int(budget / max(price, 0.4)), int(monthly_supply * 0.5), room)
            if buy > 0:
                _g, _ = _changping_trade(p, name, buy, "buy", price, log, "常平")
                if _g > 0:
                    # 收粮出市 → 当地粮价回升（常平托市的正确触发）
                    p["grain_price"] = _recalc_region_price(state, name, extra_supply=-_g)
                    changping_acted = True
    # AI 契约：平抑物价（price_stabilize 档位调制常平仓操作强度）
    # 注：本分支须排在「稳定器回收结算」之前，其回收额才会计入
    # state._stabilizer_recycled（原顺序在后，致 AI 加强档的销币账漏记，
    # 稳定器「目标 vs 实回收」读数系统性偏低）。
    if price_stabilize_mult > 1.0:
        for name, p in state.prefectures.items():
            price = p.get("grain_price", state.grain_price)
            cp_stock = p.get("changping_stock", 0)
            coffer = p.get("local_treasury", 0)
            if price > CHANGPING_HIGH and cp_stock > 0:
                # AI 加强平粜（T9 扩容：上限 60%）
                ratio = min(_sell_ratio, (price - CHANGPING_HIGH) * 0.5 * price_stabilize_mult)
                sell = max(1, int(cp_stock * ratio))
                sell = min(sell, cp_stock)
                _g, _recycled = _changping_trade(p, name, sell, "sell", price, log, "常平·AI")
                if _g > 0:
                    _recycled_total += _recycled
                    state.statistics["changping_recycled"] = (
                        state.statistics.get("changping_recycled", 0) + _recycled)
                    p["grain_price"] = _recalc_region_price(state, name, extra_supply=_g)
                    changping_acted = True
            elif price < CHANGPING_LOW and coffer > 0:
                # AI 加强平籴（T9 扩容：预算 50%、仓容月产 100%）
                budget = int(coffer * CHANGPING_BUY_BUDGET_RATIO * price_stabilize_mult)
                monthly_supply = max(p.get("grain", 0) / 12.0, 1.0)
                cap = max(monthly_supply * CHANGPING_CAP_RATIO, 1.0)
                room = max(0, int(cap - cp_stock))
                buy = min(int(budget / max(price, 0.4)), int(monthly_supply * 0.5), room)
                if buy > 0:
                    _g, _ = _changping_trade(p, name, buy, "buy", price, log, "常平·AI")
                    if _g > 0:
                        p["grain_price"] = _recalc_region_price(state, name, extra_supply=-_g)
                        changping_acted = True

    if changping_acted:
        state._stabilizer_recycled = _recycled_total
        log.append("[常平] 州县常平仓平粜籴，物价稍纾")
        _settle_stabilizer_recycle(state, log)

    # ---- 商品交易（多商品）+ 粮市交易 + 各 POP 消费 ----
    # 工匠产不同商品、各 POP 按阶级买不同商品（钱→工匠/商人，钱守恒；新增商品经 register_finished_good 扩展）
    _eco = getattr(state, "_economy_ai", None) or {}
    # 全游戏级强制 AI（拒绝式）：无经济推演 → 景气消费倍率中性 1.0（不伪造景气档位）
    _boom = BOOM_MULT.get(_eco.get("景气", "中"), 1.0) if _eco else 1.0
    _prod = {"无": 0.0, "微": 0.5, "小": 0.75, "中": 1.0, "大": 1.3, "巨": 1.6, "极": 1.9}.get(_eco.get("生产", "中"), 1.0)  # 生产力度（审查 P1-3：7 档闭合）
    for name, p in state.prefectures.items():
        artisan, merchant = p["pops"]["工匠"], p["pops"]["商人"]
        # 1) 工匠产商品 + 商人贩运（实物生产；钱只在交易时流转，产出不凭空造钱——
        #    守恒修正：移除"产出 30% 折算 wealth 入账"（曾致工匠凭空得钱，且与消费段
        #    0.4/0.3 分配的 0.3 蒸发不配平，月净缺口达百万贯级））
        for gdim in artisan["goods"]:                       # 工匠产商品（绸价高量少、布价低量大）
            _add = int(artisan["size"] * (0.10 if gdim == "绸" else 0.20) * _prod)
            artisan["goods"][gdim] += _add
        for gdim in merchant["goods"]:                      # 商人贩运
            merchant["goods"][gdim] += int(merchant["size"] * 0.10 * _prod)
        # 2) 各 POP 按阶级买商品（有钱就消费，wealth 弹性收敛；买家支出全额入工匠/商人，钱守恒）
        for pop_name, pop in p["pops"].items():
            base_rate = GOODS_CONSUME_RATE.get(pop_name, 0.01)   # Phase B 定稿：商品消费率（单一权威源）
            _per_capita = pop["wealth"] / max(pop["size"], 1)
            _elastic = min(3.0, max(1.0, _per_capita / 5.0))
            spend = int(pop["wealth"] * base_rate * _elastic * _boom)
            if spend > 0:
                pop["wealth"] -= spend
                for gdim, share in GOODS_DEMAND.get(pop_name, {"布": 1.0}).items():
                    if share > 0:
                        pop["goods"][gdim] = pop["goods"].get(gdim, 0) + int(spend * share)
                artisan["wealth"] += int(spend * 0.7); merchant["wealth"] += int(spend * 0.3)  # 全额分配（0.7+0.3=1.0，钱守恒）
        # 3) 商品折旧（各 POP 持有商品每月 5% 消耗，商品有使用寿命、用完再买，防只增不耗）
        for _pop in p["pops"].values():
            for _gdim in _pop.get("goods", {}):
                _pop["goods"][_gdim] = int(_pop["goods"][_gdim] * 0.95)
        # 3.5) 存货外销变现（蔡权衡裁决：goods 存量 > 库存上限（月产×12）→ 外销
        #      min(存量-上限, 月产×0.3) × GOODS_PRICE 入工匠 wealth；goods 出 == 外部钱入，
        #      守恒（来源=外销，非凭空）；记 statistics["export_income"]）
        try:
            from content.data import GOODS_PRICE, EXPORT_STOCK_MONTHS, EXPORT_RATE
            for _gdim, _gprice in GOODS_PRICE.items():
                _month_prod = int(artisan["size"] * (0.10 if _gdim == "绸" else 0.20) * _prod)
                _cap = _month_prod * EXPORT_STOCK_MONTHS
                _stock = artisan["goods"].get(_gdim, 0)
                if _stock > _cap and _month_prod > 0:
                    _export = min(_stock - _cap, int(_month_prod * EXPORT_RATE))
                    if _export > 0:
                        artisan["goods"][_gdim] = _stock - _export
                        _income = int(_export * _gprice)
                        artisan["wealth"] += _income
                        state.statistics["export_income"] = state.statistics.get("export_income", 0) + _income
                        # 阶段 B-2：外销变现是**真实体外注入**（goods 出、外部钱入），
                        # 登记入货币台账，使对账残差不再把它误算成"凭空造币"。
                        # 见 core/money.py 的 register_flow 与 货币口径规范 §4.2。
                        try:
                            from core.money import register_flow as _reg_flow
                            _reg_flow(state, "external", _income, f"外销变现·{_gdim}")
                        except Exception:  # noqa: BLE001 — 台账登记失败不影响结算
                            pass
        except Exception:
            pass
        # 4) 士绅奢侈消费（蓄养奴婢/园林/宴饮/香火/收藏），消耗财富、钱流向工匠商人（服务），体现"富而奢"
        # Phase B 定稿：奢侈品 = 士绅wealth × 0.01 × 景气倍率（景气驱动，繁荣挥霍、萧条收缩）
        _genty = p["pops"]["士绅"]
        _lux = int(_genty["wealth"] * 0.01 * _boom)
        if _lux > 0:
            _genty["wealth"] -= _lux
            artisan["wealth"] += int(_lux * 0.5); merchant["wealth"] += int(_lux * 0.5)
    # ---- 士绅囤粮操作（AI 推演档位优先，无 AI 按粮价方向兜底；钱粮守恒）----
    # B1（A1）出清顺序裁决：士绅先售、农售余量——士绅囤抛先于下方"非农缺粮买农粮"执行，
    # 与农售粮共用同一批缺粮 POP（工匠/商人/官僚/兵）的 wealth 池：先扣士绅粮款，
    # 剩余可支付余力才买农粮，写死防双重扣款（同一笔钱不得两处买粮）。
    _settle_civilian_hoard(state, log)

    # 粮市净头寸撮合（Phase B 定稿）：各 POP 净头寸 = 持有 − 消费 need；盈余者入卖方池、
    # 缺口者入买方池；买方池 = Σmin(缺口, (wealth−保底线)/区域价)；按卖方供给占比分配
    # （农保底 FARMER_SELL_FLOOR）；买方扣款 == 卖方收款（尾差归末位）；净头寸单边参与防双重扣款。
    # 顺序：士绅囤抛（_settle_civilian_hoard）先售（B1），本撮合处理余量——缺粮 POP 先扣士绅粮款、
    # 剩余可支付余力才入本撮合买方池，写死防双重扣款（同一笔钱不得两处买粮）。
    _famine = False
    for name, p in state.prefectures.items():
        price = p.get("grain_price", state.grain_price)
        price_wen = max(int(price * 1000), 1)
        pops = p["pops"]
        # 1) 各 POP 净头寸（need 按职业口粮）
        need_of = {pn: int(pop["size"] * GRAIN_CONSUME_PER_CAPITA.get(pn, 0.5))
                   for pn, pop in pops.items()}
        sellers = []
        for pn, pop in pops.items():
            surplus = max(0, pop["grain"] - need_of[pn])
            if pn == "农":
                # P0-① 农存粮安全垫：保留 1 个月口粮不卖（可卖 = grain − 2×need），
                # 防农存粮被粮市系统性抽干 → 非收获月缺粮 → 1% 逃荒 → 流民爆炸。
                surplus = max(0, surplus - need_of[pn])
            if surplus > 0:
                sellers.append((pn, surplus))
        buyers = []
        buyer_pool = 0
        for pn, pop in pops.items():
            short = max(0, need_of[pn] - pop["grain"])
            if short <= 0:
                continue
            floor = int(pop["size"] * GRAIN_CONSUME_PER_CAPITA.get(pn, 0.5) * price)  # 保底线（贯）
            # 可购量：wealth（贯）按文级单价折算石（×1000 对齐 price_wen=文/石，防贯/文 1000 倍量级 bug）
            can_buy = min(short, (max(0, pop["wealth"] - floor) * 1000) // price_wen)
            if can_buy > 0:
                buyers.append((pn, can_buy))
                buyer_pool += can_buy
        # 2) 撮合：成交 = min(买方池, 卖方供给)
        sell_total = sum(s for _, s in sellers)
        if sell_total > 0 and buyers:
            trade = min(buyer_pool, sell_total)
            # 诊断统计：粮市撮合月成交量（石），供回归断言防 P0 量级 bug（买方池饿死）
            state.granary_stats["grain_market_trade"] = state.granary_stats.get("grain_market_trade", 0) + trade
            # 卖方分配：按盈余占比，农保底 FARMER_SELL_FLOOR（权重抬升，防农被挤出粮市）
            _sw = {}
            for sname, s in sellers:
                w = s / sell_total
                if sname == "农":
                    w = max(w, FARMER_SELL_FLOOR)
                _sw[sname] = w
            _wsum = sum(_sw.values())
            _sell_q = {}
            _left = trade
            _snames = list(_sw.keys())
            for j, sname in enumerate(_snames):
                q = int(trade * _sw[sname] / _wsum)
                if j == len(_snames) - 1:
                    q = _left                    # 尾差归末位（trade ≤ sell_total 保证不超盈余）
                _sell_q[sname] = q
                _left -= q
            # 买方分配：按可购占比（trade ≤ buyer_pool 保证不超可购）
            _buy_q = {}
            _left = trade
            for i, (bname, can_buy) in enumerate(buyers):
                q = int(trade * can_buy / buyer_pool)
                if i == len(buyers) - 1:
                    q = _left
                _buy_q[bname] = q
                _left -= q
            # 3) 落地：卖方 grain −、wealth +；买方 grain +、wealth −（钱粮双向守恒，总量 == trade）
            for sname, q in _sell_q.items():
                if q > 0:
                    pops[sname]["grain"] -= q
                    pops[sname]["wealth"] += int(q * price)
            for bname, q in _buy_q.items():
                if q > 0:
                    pops[bname]["grain"] += q
                    pops[bname]["wealth"] -= int(q * price)
        # 4) 口粮消费（按职业）：不足则饥荒（农逃荒）
        for pn, pop in pops.items():
            need = need_of[pn]
            if pop["grain"] >= need:
                pop["grain"] -= need
            else:
                pop["grain"] = 0
                # 兵口粮由军粮段（太仓本色）单独保障与惩罚（训练/士气/民心），
                # 本色半折+俸禄折钞、不靠粮市买粮——此处不重复计入民间饥荒 _famine，
                # 防兵永远缺粮→每月 _famine→民心持续 -1（P0 崩盘链一部分）。
                if pn != "兵":
                    _famine = True
                if pn == "农":                    # 农民缺粮 → 逃荒为流民（POP 人数减、本地流民池增）
                    # P0-④ 逃荒降档（0.01 → 0.002）并设单路上限 5 万/月，
                    # 防粮市冲击下农缺粮触发海量流民 → 起义压力爆炸。
                    _flee = min(int(pop["size"] * 0.002), 50_000)
                    pop["size"] -= _flee
                    p["refugees"] = p.get("refugees", 0) + _flee
        # 5) 农储粮上限+霉耗（加消耗兜底·自然消耗）：农 grain > 12石/人 → 超出按 2%/月霉耗核销（收敛 ~12石/人）
        _nong_g = pops["农"]
        _cap_g = _nong_g["size"] * FARMER_STORE_CAP
        if _nong_g["grain"] > _cap_g:
            _spoil = int((_nong_g["grain"] - _cap_g) * FARMER_SPOIL_RATE)
            if _spoil > 0:
                _nong_g["grain"] -= _spoil
                state.granary_stats["farmer_spoil"] = state.granary_stats.get("farmer_spoil", 0) + _spoil
        # 6) 隐户消费（Phase B）：隐户不落籍（每户按 4 口计），吃粮由该路士绅/地主供给（记 hidden_feed）
        _hidden_share = state.land.get("hidden_households", 0) * 4 * p.get("population", 1) / max(state.population, 1)
        _hidden_feed = int(_hidden_share * HIDDEN_CONSUME_PER_CAPITA)
        if _hidden_feed > 0:
            _g0 = pops["士绅"]
            _g0["grain"] = max(0, _g0["grain"] - _hidden_feed)
            state.granary_stats["hidden_feed"] = state.granary_stats.get("hidden_feed", 0) + _hidden_feed
    if _famine:
        state.population_satisfaction = max(0, state.population_satisfaction - 1)

    state.economy_history.append({
        "granary": state.granary,
        "granary_cap": state.granary_cap,
        "grain_price": state.grain_price,
        "price_level": state.price_level,
        "coin_shortage": state.coin.get("shortage", 0.3),
        "canal_block": state.canal_block,
        # 认知层滞后快照（供脱敏层做"奏报延迟"，AI 看到的是上月数而非实时）
        "treasury": state.treasury,
        "imperial_treasury": state.imperial_treasury,
        "refugee_count": state.refugee_count,
    })
    if len(state.economy_history) > 12:
        state.economy_history = state.economy_history[-12:]
    if state.economy_history:
        state.economy_knowledge = dict(state.economy_history[-1])


# ------------------------------------------------------------
# 士绅囤粮/窖银（原 settlement_civilian.py 内联；钱粮守恒）
# ------------------------------------------------------------
def _buyer_pool(p, price):
    """该路缺粮 POP 的可支付财富池（A1/B1 抛粮买方化）。

    买方 = 工匠/商人/官僚/兵 中当月缺粮者；可支付财富 = wealth - 保底线
    （保底线 = 1 个月口粮钱，与税征段 _min_wealth 同口径）。
    返回 ([ (pop_name, 缺口石, 可支付贯) ...], 池总额贯)；无合格买方返回 ([], 0)。
    """
    from content.data import PER_CAPITA_MONTH_GRAIN
    buyers = []
    pool = 0
    for pop_name in ("工匠", "商人", "官僚", "兵"):
        pop = p["pops"][pop_name]
        need = int(pop["size"] * PER_CAPITA_MONTH_GRAIN)
        short = max(0, need - pop.get("grain", 0))
        if short <= 0:
            continue
        floor = int(pop["size"] * PER_CAPITA_MONTH_GRAIN * price)   # 保底线（贯）
        afford = max(0, pop["wealth"] - floor)
        if afford <= 0:
            continue
        buyers.append((pop_name, short, afford))
        pool += afford
    return buyers, pool


def _sell_to_buyers(p, seller, qty, price, copper_share=1.0):
    """把 qty 石粮卖给该路缺粮 POP 买方池，返回实售石数（A1/B1）。

    实售 = min(qty, 池可购石数)；买方按缺口比例扣 wealth、得粮（钱粮双向守恒）：
      买方 wealth -= share（钱出）、grain += 份额粮（缺口被填补，粮进）；
      卖方士绅 grain -= sold（粮出，调用处扣减）、wealth+窖银 += sold×price（钱进）。
    尾差归末位：买方扣款合计 == cost、买方得粮合计 == sold（无凭空生钱/灭粮）。
    窖银只藏铜钱（用户史实指示 b）：交子有界贬值、不能窖藏——交子部分全额进 wealth，
    仅铜钱部分按 30/70 拆分（copper_share = 铜钱占流通货币比例）。
    池为 0 → 实售 0（囤积维持，不造币）。
    """
    buyers, pool = _buyer_pool(p, price)
    if not buyers:
        return 0
    price_wen = max(int(price * 1000), 1)
    can_buy = (pool * 1000) // price_wen   # pool（贯）按文级单价折算石（×1000 对齐 price_wen，防贯/文量级 bug）
    sold = min(qty, can_buy)
    if sold <= 0:
        return 0
    cost = int(sold * price)
    short_total = sum(b[1] for b in buyers)
    aff_total = sum(b[2] for b in buyers) or 1
    paid = 0
    grain_given = 0
    _n = len(buyers)
    for i, (pop_name, short, aff) in enumerate(buyers):
        # 审查 P2-17 修复：扣款按「可支付力 afford」加权分摊。原按缺口 short 分摊，
        # 缺口大但 wealth 少的买方会被分摊超额款项（wealth 可被扣穿甚至为负）；
        # 粮仍按缺口 short 分配（谁缺得多谁得粮）。
        if i == _n - 1:                     # 尾差归末位：得粮合计 == sold
            share = cost - paid
            grain_share = sold - grain_given
        else:
            share = int(cost * aff / aff_total)
            grain_share = int(sold * short / short_total)
        pop = p["pops"][pop_name]
        # 逐户封顶：绝不扣穿当前 wealth（实收不足部分由卖方按实收记账，钱不进不出）
        share = max(0, min(share, int(pop.get("wealth", 0))))
        pop["wealth"] -= share              # 钱出
        pop["grain"] = pop.get("grain", 0) + grain_share   # 粮进（缺口被填补）
        paid += share
        grain_given += grain_share
    copper = int(paid * max(0.0, min(1.0, copper_share)))   # 铜钱部分
    jiaozi_part = paid - copper                              # 交子部分（不窖藏，全进流通）
    # 用户关键修正：**窖银只囤银**——铜钱/交子（钞）均不入窖，全部进 wealth（流通）；
    # 窖银（白银）由 _settle_civilian_hoard 从市舶 silver 池分配（银硬通货可窖、钞不可窖）
    # 审查 P2-17：卖方按「实收 paid」入账（与买方实扣合计一致，钱粮双向守恒）
    seller["wealth"] += paid
    return sold


def _settle_civilian_hoard(state, log):
    """士绅囤粮操作（钱粮守恒）：AI 推演档位优先，无 AI 时按粮价方向兜底。

    囤 = 士绅用 wealth 买粮（wealth↓ grain↑，受资金约束）；抛 = 卖粮得钱（grain↓ wealth↑）。
    士绅囤粮挤压市场流通（见 calc_region_grain_price 的 HOARD_SUPPLY_SQUEEZE）。
    """
    # AI 经济动态推演（settle_turn 已注入 state._economy_ai：{景气,士绅,士绅力度,生产,窖银}）或无
    _eco = getattr(state, "_economy_ai", None) or {}
    _ai_act = _eco.get("士绅", "") if _eco.get("士绅") in ("囤", "抛") else None
    _ai_tier = _eco.get("士绅力度", "中")
    # 窖银只藏铜钱（用户史实指示 b）：铜钱占流通货币比例 = 1 - 交子有效额 / 货币总量
    # （交子有界贬值、不能窖藏；issued=0 时 100% 铜钱，藏富不受影响）
    _jiaozi_eff = state.jiaozi.get("issued", 0) * state._jiaozi_acceptance()
    _pop_money = sum(pop.get("wealth", 0)
                     for _p in state.prefectures.values() for pop in _p.get("pops", {}).values())
    _money_total = _jiaozi_eff + _pop_money + max(0, state.treasury) + max(0, state.imperial_treasury)
    _copper_share = max(0.0, min(1.0, 1.0 - _jiaozi_eff / max(_money_total, 1.0)))
    # 窖银动用档位（A1 定稿·用户史实指示 c）：AI 推演决定每月动用比例，程序换算；
    # 无 AI（本地降级/_economy_ai 缺该键）默认「无」= 冻结不动用（藏富不到最后关头不用）。
    _draw_tier = _eco.get("窖银") if _eco.get("窖银") in HOARD_DRAW_RATE else "小"   # no-AI 被动缓释 0.5%/月（防永久抽水；有 AI 由档位决定）
    _draw_rate = HOARD_DRAW_RATE.get(_draw_tier, 0.0)
    for name, p in state.prefectures.items():
        genty = p["pops"]["士绅"]
        price = p.get("grain_price", state.grain_price)
        # 用户关键修正：**窖银只囤银**——每月从市舶白银池（silver_in，硬通货）按
        # HOARD_COPPER_RATIO_BASE 比例分配入士绅窖银（白银退出流通）；铜钱/交子不可入窖
        try:
            _mar = getattr(state, "maritime", None) or {}
            _silver = int(_mar.get("silver_in", 0)) if isinstance(_mar, dict) else 0
            if _silver > 0 and _mar.get("open"):
                _silver_share = int(_silver * HOARD_COPPER_RATIO_BASE / max(len(state.prefectures), 1))
                if _silver_share > 0:
                    genty["窖银"] = genty.get("窖银", 0) + _silver_share
                    _mar["silver_in"] = max(0, _mar["silver_in"] - _silver_share)  # 银入窖退出流通
                    state.statistics["hoard_growth"] = state.statistics.get("hoard_growth", 0) + _silver_share
        except Exception:
            pass
        if _ai_act:
            act, tier = _ai_act, _ai_tier   # AI 推演（全国统一景气下的士绅行为）
        elif not _eco:
            # 全游戏级强制 AI（拒绝式）：无经济推演 → 不伪造囤/抛决策，士绅按兵不动
            act, tier = "观望", "无"
        else:
            # 兜底：丰收贱买囤积、高价惜售/抛售获利（不再高价囤，与常平粜粮方向一致）
            if price < 0.6:
                act, tier = "囤", "小"
            elif price > 2.2:
                act, tier = "抛", "中"
            elif price > 1.6:
                act, tier = "抛", "微"       # 高价惜售（小幅抛售获利）
            else:
                # 粮价平稳：士绅卖囤粮换钱（买商品/维持现金流），卖 5%/月使囤粮存量稳定
                act, tier = "抛", "中"
        mult = TIER_RANGE.get(tier, 0.5) * 0.05   # 囤/抛比例：微0.0125/小0.025/中0.05/大0.09（不 round）
        # 囤粮上限（A1 定案·软约束）：软上限 = 士绅田产年产 × HOARD_CAP_MULT（0.3），
        # 硬上限 = 软上限 × 1.5。超软上限先售买方池、未售保留（囤积居奇机制保留）；
        # 仅超硬上限强制出清，未售按 3% 损耗核销（防无限囤积）。
        _land = max(float(p.get("land", 1)), 1.0)
        _gentry_land_total = float(p.get("gentry_land", 0)) + float(p.get("hidden_land", 0))
        _soft_cap = int(p.get("grain", 0) * _gentry_land_total / _land * HOARD_CAP_MULT)
        _hard_cap = int(_soft_cap * 1.5)
        if act == "囤":
            buy = int(p.get("grain", 0) / 12.0 * mult)      # 月产 × 档位
            price_wen = max(int(price * 1000), 1)           # 文级单价（与 _sell_to_buyers 同口径）
            # 审查修复（量级错）：wealth 单位为贯、price_wen 为文/石，
            # 原式 wealth // price_wen 少乘 1000 → 可购量被低估千倍，囤粮机制实质失效
            # （例：26 万贯、1 贯/石 时只能买 260 石）。统一为贯→文换算。
            afford = genty["wealth"] * 1000 // price_wen     # 资金能买多少石（文级精度）
            room = max(0, _soft_cap - genty["grain"])       # 囤粮余量（软上限约束）
            src = max(0, int(p.get("grain", 0) / 12.0))     # 粮源上限：本路在库粮的月产部分
            buy = min(buy, afford, room, src)
            if buy > 0:
                # 审查 P2-16 修复（钱粮双破守恒）：原实现士绅 wealth 减少无对手方、
                # grain 增加无来源，且 `int(...)/1000.0` 使 wealth 变 float。
                # 现改为成对划转：钱 士绅→本路农户 wealth；粮 本路在库粮→士绅囤粮。
                cost = int(buy * price)                     # 贯（整数）
                farmers = (p.get("pops") or {}).get("农")
                if isinstance(farmers, dict):
                    genty["wealth"] -= cost
                    farmers["wealth"] = farmers.get("wealth", 0) + cost
                # 无农户接收方时不划钱（宁可不流转，也不凭空灭币）
                genty["grain"] += buy
                p["grain"] = max(0, int(p.get("grain", 0)) - buy)
        elif act == "抛":
            sell = int(genty["grain"] * mult)
            if sell > 0:
                # B1：抛粮买方化——卖给该路缺粮 POP 可支付财富池，不卖给虚空；
                # 未售部分继续囤（囤积维持，不造币）。窖银只藏铜钱（copper_share）。
                sold = _sell_to_buyers(p, genty, sell, price, _copper_share)
                if sold > 0:
                    genty["grain"] -= sold
        # 超软上限：先售买方池，未售保留（不压回、不核销）——囤积居奇机制保留
        if genty["grain"] > _soft_cap:
            sold = _sell_to_buyers(p, genty, genty["grain"] - _soft_cap, price, _copper_share)
            if sold > 0:
                genty["grain"] -= sold
        # 仅超硬上限：强制出清，未售按损耗核销（不凭空变钱；粮压回硬上限，防无限囤积）
        if genty["grain"] > _hard_cap:
            _excess = genty["grain"] - _hard_cap
            sold = _sell_to_buyers(p, genty, _excess, price, _copper_share)
            genty["grain"] = _hard_cap
            _unsold = _excess - sold
            if _unsold > 0:
                # 未售部分按 HOARD_SPOIL_RATE 损耗核销（雀鼠耗/霉变）：粮凭空消失但钱不凭空生；
                # 3% 记入损耗统计，余量一并出清（grain 压回硬上限）
                _spoil = int(_unsold * HOARD_SPOIL_RATE)
                state.granary_stats["hoard_spoil"] = state.granary_stats.get("hoard_spoil", 0) + _spoil
        # 窖银动用（A1 定稿·用户史实指示 c）：按 AI 档位换算的每月动用比例取窖银出窖，
        # 流向工匠/商人（挥霍/购地/市舶投资等服务消费），死钱转活钱、不积累 wealth；
        # 无 AI 时 _draw_rate = 0（冻结，不到最后关头不用）。
        _draw = int(genty.get("窖银", 0) * _draw_rate)
        if _draw > 0:
            genty["窖银"] = genty.get("窖银", 0) - _draw
            p["pops"]["工匠"]["wealth"] += int(_draw * 0.5)
            p["pops"]["商人"]["wealth"] += int(_draw * 0.5)



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
            # 审查防御：资源维可能缺槽（新注册物资/旧存档），原为硬下标 → KeyError
            # 会中断整月结算。统一 setdefault 建槽后再扣。
            _slot = state.resources.setdefault(dim, {"stock": 0, "cap": 0})
            _slot["stock"] = max(0, int(_slot.get("stock", 0) or 0) - need)
        if coin_need > 0:
            # 2026-09-18 测试体检修复（货币守恒）：原为裸 `state.treasury -= coin_need`
            # —— 无对手方，钱凭空消失（实测：单项工程 500,000 贯 → ΔM_ALL = −500,000）。
            # 工程款是**政府营造/购办支出**，按"支出回流"口径转入民间（工匠40%/商人60%）。
            # 财政成本不变（国库照扣），货币总量守恒。
            state.treasury -= coin_need
            try:
                from content.data import GOV_SPEND_TO
                _given = _distribute_cash(state, coin_need, GOV_SPEND_TO)
                if _given != coin_need:      # 无接收方兜底：退回国库，不静默销毁
                    state.treasury += coin_need - _given
            except Exception:                # noqa: BLE001 — 回流失败不得阻断工程推进
                state.treasury += coin_need
        proj["progress"] = min(100, proj.get("progress", 0) + int(proj.get("speed", 10)))
        if proj["progress"] >= 100:
            proj["done"] = True
            out = proj.get("output") or {}
            if "granary_cap_add" in out:
                state.change_granary_cap(int(out["granary_cap_add"]))
            if "defense_add" in out:
                from core.army_models import ArmyUnit, EQUIP_STD, _defense_line_for
                add = int(out["defense_add"])
                for route in out.get("defense_routes", []):
                    if route not in state.prefectures or add <= 0:
                        continue
                    xiang = [u for u in state.army_units
                             if u.station == route and u.tier == "厢军"]
                    if xiang:
                        # 归入该路厢军军队的轻步兵兵种（装备不随增）
                        main = max(xiang, key=lambda u: u.troops)
                        main.branches["轻步兵"] = main.branches.get("轻步兵", 0) + add
                    else:
                        branch = "轻步兵"
                        std = EQUIP_STD.get(branch, {})
                        state.army_units.append(ArmyUnit(
                            unit_id=f"eng{route}{state.year}{state.month}{pid}",
                            name=f"{route}工役厢",
                            tier="厢军",
                            branches={"轻步兵": add},
                            morale=45,
                            training=35,
                            station=route,
                            defense_line=_defense_line_for(route, "厢军"),
                            equip={k: int(add * per) for k, per in std.items()},
                        ))
                state._derive_defense_lines()
            if "wine_coin_add" in out:
                # 2026-09-18 测试体检修复（货币守恒）：原为裸
                # `state.imperial_treasury += int(out["wine_coin_add"])` —— **无买方**，
                # 与审查 A-4（畜栏产肉）同类：产物收益凭空造币。
                # 现改为向民间**守恒征收**（实收才入账，不足则少收、不补差额）。
                # 注：当前 content 里无工程使用该产出（属预留路径），但契约必须正确，
                # 否则一旦有数据启用就会静默造币。
                _want = int(out["wine_coin_add"])
                _got = _collect_from_pops(state, _want)
                state.imperial_treasury += _got
                if _got < _want:
                    log.append(f"[工程] 酒课增收应 {_want:,} 贯，民间可缴仅 {_got:,} 贯，按实入账")
            log.append(f"[工程] {proj.get('name','工程')} 告成，效益已落实")


# ------------------------------------------------------------
# Step 4.5b: 制作/作坊系统
# ------------------------------------------------------------
def _collect_from_pops(state, amount: int) -> int:
    """按人口比例向六类 POP 征收 `amount` 贯（买家支付），返回**实收**额。

    用途：把"产出型/外部型入账"改为**守恒转移**——POP 挂载律要求"凡钱必须落在
    POP wealth 或国库/内帑，且来源=去向"。用于修复审查 A-4（畜栏产肉原
    `imperial_treasury += 收入` 无买方 → 凭空造币）。

    语义：按 POP `size` 比例分摊；某池 wealth 不足时**按实收计，不补差额**——
    宁可少收，也绝不凭空造币。两轮征收（第二轮补齐首轮 int 截断余额）以保证
    在余额充足时能收满 `amount`，从而使"扣减额 == 入账额"精确成立。
    """
    amount = int(amount or 0)
    if amount <= 0:
        return 0
    pools = [(pp, float(pp.get("size", 0) or 0))
             for p in state.prefectures.values()
             for pp in (p.get("pops") or {}).values()]
    total_size = sum(sz for _, sz in pools) or 1.0
    taken = 0
    remaining = amount
    for pp, size in pools:                      # 第一轮：按人口比例
        if remaining <= 0:
            break
        if size <= 0:
            continue
        want = min(int(amount * size / total_size), remaining)
        avail = int(pp.get("wealth", 0) or 0)
        got = min(want, avail)
        if got > 0:
            pp["wealth"] = avail - got
            taken += got
            remaining -= got
    for pp, _sz in pools:                       # 第二轮：补齐 int 截断余额
        if remaining <= 0:
            break
        avail = int(pp.get("wealth", 0) or 0)
        got = min(remaining, avail)
        if got > 0:
            pp["wealth"] = avail - got
            taken += got
            remaining -= got
    return taken


def _settle_clan(state, log):
    """宗室俸禄（L2c money sink，宋代官制设计 §8.2 / 技术方案「宗室俸禄」行）。

    口径：**内帑出账**（史实宗室赡养由内帑/宗正寺支给），全额转入 `士绅` POP 的 `wealth`。
      `内帑 −paid`，`Σ士绅.wealth +paid` → **ΔM_ALL == 0**（纯转移，不造币）。
    按实付：内帑不足时只支可支部分，缺口记 `statistics["clan_arrears"]`（与欠饷/欠费同构）。

    为什么这是最有价值的一层 sink：宗室人口按 **3%/年复利** 膨胀，无需玩家做任何事，
    时间本身就是支出增量；而砍宗室要付皇威代价 → 天然的艰难抉择。
    """
    from content.data import CLAN_PAY_PER_MONTH

    _clan_by_route = []
    total_clan = 0
    for p in state.prefectures.values():
        shen = (p.get("pops") or {}).get("士绅")
        n = int((shen or {}).get("clan", 0) or 0) if isinstance(shen, dict) else 0
        if n > 0:
            _clan_by_route.append((p, n))
            total_clan += n
    if total_clan <= 0:
        return 0

    due = int(total_clan * CLAN_PAY_PER_MONTH)
    available = max(0, int(getattr(state, "imperial_treasury", 0) or 0))
    paid = min(due, available)
    if paid < due:
        state.statistics["clan_arrears"] = state.statistics.get("clan_arrears", 0) + (due - paid)
        log.append(f"[宗室] 内帑不足以赡宗室，欠支 {due - paid:,} 贯"
                   f"（应支 {due:,}，实支 {paid:,}）")
    if paid <= 0:
        return 0

    state.imperial_treasury -= paid
    # 按各宗室人口比例精确分配（末位吃尾差，保证 Σ入账 == paid）
    given = 0
    for i, (p, n) in enumerate(_clan_by_route):
        shen = p["pops"]["士绅"]
        g = (paid - given) if i == len(_clan_by_route) - 1 else int(paid * n / total_clan)
        g = max(0, int(g))
        shen["wealth"] = int(shen.get("wealth", 0) or 0) + g
        given += g
    if given != paid:                       # 极端兜底：分配残差退回内帑
        state.imperial_treasury += paid - given
    log.append(f"[宗室] 赡宗室 {given:,} 贯（宗室 {total_clan:,} 口 × {CLAN_PAY_PER_MONTH:.0f} 贯，内帑出）")
    return given


def _settle_clerks(state, log):
    """Step 3.97 吏制结算（薄封装，实现在 `core/clerks.py`——单一权威源）。

    吏额由**政务量**驱动（脱离「官 × 8」）、吏禄不足 → **陋规**（民间三池 → 官僚 POP 的
    纯转移，零货币残差）、**把持度**与**吏怨**缓动，并导出「有效吏力」与吏治四档。
    """
    from core import clerks as _clerks
    return _clerks.settle_clerks(state, log)


def _settle_officialdom(state, log):
    """Step 3.95 官制结算（薄封装，实现在 `core/officialdom.py`——单一权威源）。

    职责：旧档子池迁移修复 → 不变量校验（size == officials + clerks；
    officials == on_post + waiting + sinecure）→ 派生镜像同步（`p["officials"]`/`["clerks"]`
    的唯一写入点）→ 把冗官关键指标写进 `state.statistics` 供面板与审计读取。
    """
    return _officialdom.settle_officialdom(state, log)


def _distribute_cash(state, amount: int, shares: dict) -> int:
    """把 `amount` 贯按 `shares` {阶层: 占比} 精确分发给各路该阶层 POP wealth。

    末位（最后一个阶层 × 最后一支池）吃尾差，保证 **Σ入账 == amount**（精确守恒），
    从而与 `state.change_treasury(-paid)` 构成 `ΣΔ==0` 的守恒转移。
    返回实际分发额。
    """
    amount = int(amount or 0)
    if amount <= 0:
        return 0
    roads = list(state.prefectures.values())
    items = [(c, float(s)) for c, s in (shares or {}).items()]
    paid = 0
    for i, (cls, share) in enumerate(items):
        want = (amount - paid) if i == len(items) - 1 else int(amount * share)
        if want <= 0:
            continue
        pools = [(_p.get("pops") or {}).get(cls) for _p in roads]
        pools = [x for x in pools if isinstance(x, dict)]
        if not pools:
            continue
        _tot = sum(float(x.get("size", 0) or 0) for x in pools) or 1.0
        given = 0
        for j, x in enumerate(pools):
            g = (want - given) if j == len(pools) - 1 else int(
                want * float(x.get("size", 0) or 0) / _tot)
            g = max(0, int(g))
            x["wealth"] = int(x.get("wealth", 0) or 0) + g
            given += g
        paid += given
    return paid


def _settle_upkeep(state, log):
    """资产维持费（L1 money sink，阶段 B-3）：建筑/工程/作坊/军械/城防 按月计维护费。

    设计依据：`BUILDING_STD[*]["maintain"] = 0.5%/月` 早已写定但**从未被消费**（死数据）。
    本步把它接上，并补齐其余资产类型的折算基准（单一权威源见 `content/data.py`）。

    口径：
      资产折算造价 = Σ(政府工程按等级造价) ＋ Σ(POP 建筑按等级造价)
                    ＋ 作坊数 × WORKSHOP_VALUE ＋ 武库件数 × EQUIP_UNIT_VALUE
                    ＋ Σ城防点 × FORT_VALUE
      本月维持费   = 资产折算造价 × ASSET_MAINTAIN_RATE

    守恒与纪律（POP 挂载律）：
      · 支出从**国库**出账（`change_treasury(-paid)`）；
      · 全额**支付给民间**（营造/修缮服务：工匠 40% ＋ 商人 60%，`_distribute_cash` 精确守恒）；
      · 国库不足时**只按实付**（不穿底、不造币），缺口记 `statistics["upkeep_arrears"]`
        —— 与军俸的「欠饷」、税收的「欠税」科目同构。
    返回本月实付额。
    """
    from content.data import (BUILDING_STD, BUILDING_COST_GROWTH, WORKSHOP_VALUE,
                              EQUIP_UNIT_VALUE, FORT_VALUE, POP_BUILDING_VALUE,
                              ASSET_MAINTAIN_RATE, UPKEEP_PAY_TO)
    # 编制参数（阶段 C-7 / 财力消耗设计 S-D6）：玩家可经政令**主动降维持费**（裁汰冗费）。
    from core import institution as _inst
    _maintain_rate = float(ASSET_MAINTAIN_RATE) * _inst.get(state, "asset_maintain_mult")

    def _lv_cost(std: dict, lv: int) -> float:
        return float(std["base_cost"]) * (BUILDING_COST_GROWTH ** (max(1, int(lv)) - 1))

    asset_value = 0.0
    # 1) 政府工程（projects）：类型命中 BUILDING_STD 时按等级造价
    for _pj in (getattr(state, "projects", {}) or {}).values():
        if not isinstance(_pj, dict):
            continue
        _std = BUILDING_STD.get(str(_pj.get("name") or _pj.get("type") or ""))
        if _std:
            asset_value += _lv_cost(_std, _pj.get("level", 1))
    # 2) POP 建筑（按路）：命中 BUILDING_STD 用其 base_cost，否则用 POP_BUILDING_VALUE
    for _p in state.prefectures.values():
        for _bt, _lv in ((_p.get("buildings") or {})).items():
            _std = BUILDING_STD.get(str(_bt))
            if _std:
                asset_value += _lv_cost(_std, _lv)
            else:
                asset_value += POP_BUILDING_VALUE * max(1, int(_lv or 1))
    # 3) 作坊（酒坊/畜栏…）：按名义造价
    asset_value += len(getattr(state, "workshops", {}) or {}) * float(WORKSHOP_VALUE)
    # 4) 中央武库：按件折价
    _ca = getattr(state, "central_arsenal", None)
    if _ca is not None:
        asset_value += sum((getattr(_ca, "stock", {}) or {}).values()) * float(EQUIP_UNIT_VALUE)
    # 5) 城防：按点折价
    asset_value += sum((l.get("fortification", 0) or 0)
                       for l in getattr(state, "defense_lines", {}).values()) * float(FORT_VALUE)

    due = int(asset_value * _maintain_rate)
    if due <= 0:
        return 0

    available = max(0, int(getattr(state, "treasury", 0) or 0))
    paid = min(due, available)
    if paid < due:
        state.statistics["upkeep_arrears"] = \
            state.statistics.get("upkeep_arrears", 0) + (due - paid)
        log.append(f"[维持] 营造修葺欠费 {due - paid:,} 贯"
                   f"（应支 {due:,}，实支 {paid:,}；帑藏不足）")
    if paid <= 0:
        return 0

    state.change_treasury(-paid)
    _given = _distribute_cash(state, paid, UPKEEP_PAY_TO)
    if _given != paid:                      # 极端兜底：无工匠/商人池时余额退回国库
        state.change_treasury(paid - _given)
    log.append(f"[维持] 资产维持费 {paid:,} 贯（资产折算 {asset_value:,.0f} 贯 ×"
               f" {_maintain_rate:.1%}/月）")
    return paid


def _settle_workshops(state, log):
    """作坊月度推进：配方消耗 inputs（如粮→酒），产出 outputs 入 resources/内帑。"""
    _wine_bonus = 0     # 本月酒课**加成**汇总；下方据此**重算** wine_tax（不做月度累加，见 A-5）
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
            state.granary_stats["workshop_feed"] = state.granary_stats.get("workshop_feed", 0) + grain_feed
        for dim, need in recipe.items():
            if dim == "grain_feed":
                continue  # 粮耗已单独从太仓扣，不作为资源维度
            _slot = state.resources.setdefault(dim, {"stock": 0, "cap": 0})
            _slot["stock"] = max(0, int(_slot.get("stock", 0) or 0) - need)
        out_dim = ws.get("output_dim")
        yld = float(ws.get("yield", 0))
        if out_dim == "wine":
            # 酒坊产能 → 酒课**加成**（汇入下方重算，**不在此累加**）
            # 审查 A-5 修复（2026-09-18 阶段 B-1 实测：内帑 +2.91M/月、民间 −2.28M/月、
            # 残差 +0.93M/月 的主要来源）：`state.wine_tax` 是**月度收入率**
            # （见 game_state_econ.py:520 与下方财政步 `_wine_tax_cash = int(wine_coin)`），
            # 原实现在此 `+=` 每月再加一次常量 → 60 个月把月率抬高约 60 倍，
            # 使财政步每月从工匠/商人 wealth **超额扣缴**进内帑，是"钱荒"的直接推手。
            # 现改为按月**重算**：酒课 = 保底 WINE_COIN_BASE ＋ Σ各酒坊产能加成。
            _wine_bonus += int(yld * MATERIAL_PRICE_BASE.get("wine", 0) * 0.1)
        elif out_dim == "meat":
            # 畜栏产肉折钱入内帑（加消耗修正·依托建筑；耗粮已在 grain_feed 从太仓扣）
            # 审查 A-4 修复（阶段 B-1 实测的残差主源）：原 `imperial_treasury += 收入`
            # **无买方** → 凭空造币。肉是消费品，收入须由买家（民间 POP wealth）支付：
            # 现按人口比例向六类 POP 征收，**只把实收额**入内帑（不足则按实收计）。
            _meat_gain = int(yld * MEAT_PRICE)
            _meat_taken = _collect_from_pops(state, _meat_gain)
            if _meat_taken < _meat_gain:
                log.append(f"[作坊] 畜栏产品滞销：应售 {_meat_gain:,} 贯，"
                           f"民间仅能支付 {_meat_taken:,} 贯（民穷则肉卖不动）")
            state.imperial_treasury += _meat_taken
            state.granary_stats["meat_revenue"] = \
                state.granary_stats.get("meat_revenue", 0) + _meat_taken
        elif out_dim in RESOURCE_DIMS:
            # 审查防御：同上（缺槽即 KeyError）；且 cap<=0 时原式 min(0, …) 会把
            # 全部产出抹成 0（静默丢料），故仅在 cap>0 时封顶。
            _slot = state.resources.setdefault(out_dim, {"stock": 0, "cap": 0})
            _cap = int(_slot.get("cap", 0) or 0)
            _new = int(_slot.get("stock", 0) or 0) + yld
            _slot["stock"] = min(_cap, _new) if _cap > 0 else _new
    # 酒课按月**重算**（保底 ＋ Σ酒坊产能加成）——杜绝"月度率被逐月累加"（A-5）
    from content.data import WINE_COIN_BASE
    state.wine_tax = int(WINE_COIN_BASE) + int(_wine_bonus)


# ------------------------------------------------------------
# Step 5: 国库结算
# ------------------------------------------------------------
def _settle_hidden_pop(state, log):
    """隐户动态（月度，人口守恒——隐户是第 7 类动态人口池，与六类 POP 转换）：

    1) 在籍 → 隐户（史实：赋税重/灾荒/民怨时民逃为隐户）：税重 + 灾荒（路粮缺）+
       民怨 → 部分农/工匠/商人转隐户（农 POP size 减、隐户增——逃税逃役）；
    2) 隐户 → 在籍（史实：清丈/轻徭/招抚时归籍）：清丈（land.survey）或轻徭政策
       → 隐户转农（隐户减、POP 增——归籍复业）。
    守恒：Σ六类 size（口） + hidden_households×4（口） 不变（转换非凭空）；
    隐户不落籍不纳税；UI 不显示（设计锚）。"""
    land = state.land
    hidden = int(land.get("hidden_households", 5_000_000))
    total_in_reg = sum(pop["size"] for _p in state.prefectures.values()
                       for pop in _p["pops"].values())
    if total_in_reg <= 0:
        return
    # 1) 逃户压力（在籍→隐户）：税率高 + 灾荒 + 民怨
    # 审查 P2-20 修复：原读 `commerce_tax`（不存在，getattr 恒返回默认 0.05）→ 压力恒 0，
    # 「税重→逃户」永不触发。改为真实字段 commerce_tax_rate，基准取默认税率 0.15
    # （超过常规税率才产生逃户压力，默认配置下不改变既有平衡）。
    _tax_pressure = min(0.010, max(0.0, (getattr(state, "commerce_tax_rate", 0.15) - 0.15) * 1.0))
    _sat_pressure = max(0.0, (50 - getattr(state, "population_satisfaction", 50)) / 50.0) * 0.004
    _disaster = 0.0
    for _p in state.prefectures.values():
        if _p.get("grain", 0) < max(_p.get("population", 1_000_000), 1) * 0.3:
            _disaster = 0.008
            break
    _flee_rate = min(0.012, _tax_pressure + _sat_pressure + _disaster)
    if _flee_rate > 0:
        _flee = int(total_in_reg * _flee_rate)
        _flee_left = _flee
        for _pop_name in ("农", "工匠", "商人"):
            if _flee_left <= 0:
                break
            for _p in state.prefectures.values():
                if _flee_left <= 0:
                    break
                _pop = _p["pops"][_pop_name]
                _t = min(_flee_left, int(_pop["size"] * 0.02))
                if _t > 0:
                    _pop["size"] = max(0, _pop["size"] - _t)
                    _flee_left -= _t
        _flee_actual = _flee - _flee_left
        if _flee_actual > 0:
            # 口 → 户精确换算：整除转户 + 余数口记账（land["hidden_rem"] 累计 ≥4 转户）
            # ——修复整数截断凭空多/少人口（test_global_ledger_total ΔP 根因）
            hidden += _flee_actual // 4
            _rem = int(land.get("hidden_rem", 0)) + _flee_actual % 4
            if _rem >= 4:
                hidden += _rem // 4
                _rem = _rem % 4
            land["hidden_rem"] = _rem
            log.append(f"[隐户] 税重民困，{_flee_actual:,} 口逃为隐户（不落籍不纳税）")
    # 2) 归籍（隐户→在籍）：清丈/轻徭/招抚——隐户减、农增（×4 口）
    _survey = int(land.get("survey", 0) or 0)
    _back_rate = 0.004 + (0.010 if _survey else 0.0)
    _back = int(hidden * _back_rate)
    if _back > 0:
        _back_people = _back * 4
        _bl = _back_people
        for _p in state.prefectures.values():
            if _bl <= 0:
                break
            _t = min(_bl, max(0, int(_p.get("population", 0) * 0.004)))
            _p["pops"]["农"]["size"] = _p["pops"]["农"].get("size", 0) + _t
            _bl -= _t
        # 尾差强制分配（修复：上限截断致农增 < 隐户减×4——人口凭空少）
        if _bl > 0 and state.prefectures:
            _p0 = next(iter(state.prefectures.values()))
            _p0["pops"]["农"]["size"] = _p0["pops"]["农"].get("size", 0) + _bl
        hidden = max(0, hidden - _back)
        log.append(f"[隐户] {'清丈' if _survey else '招抚'}，{_back:,} 户（{_back_people:,} 口）归籍复业")
    state.land["hidden_households"] = max(0, hidden)


def _settle_treasury(state, log):
    """国库结算——**占位（无操作）**：国库收支已在 Step 4（_settle_finance）完成。

    保留空实现仅为维持 settlement 主流程的步骤编号（Step 5）与导入稳定性；
    此处不得再写任何财政逻辑（避免与 Step 4 重复计征）。
    """
    return None


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

    from core.army_models import _army_power_total
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
# 12 步 agent 化 P1 换算表（程序 TIER_RANGE 同源原则：agent 只给档位词，数值程序换算封顶）
# 审查修复：契约 validate 允许的档位是七档（无/微/小/中/大/巨/极，见
# ai/client_utils._TIERS7），而本表原只登记四档 → "无" 被 .get(默认值) 当成
# 微/小执行（赈济仍开仓、征发仍扣 10 万贯），"巨/极" 反落到"大"之下（档位倒挂）。
# 现补齐七档：无=0（明确不生效），巨/极按 content.data.TIER_RANGE 比例外推
# （大:巨:极 = 1.5:2.0:2.5）。
_TA = 5 / 3.0          # 大 → 巨 倍率（2.0/1.5）
_TB = 5 / 2.0          # 大 → 极 倍率（2.5/1.5）


def _tier7(v_tiny: int, v_small: int, v_mid: int, v_big: int,
           cap: int = None) -> dict:
    """构造七档换算表（无/微/小/中/大/巨/极）。

    巨/极由大档按 content.data.TIER_RANGE 比例外推；若给出 cap，则一律受其钳制
    （外交 attitude 原 CAP 8、兵额原 CAP 5 万不得因补档而被越过）。
    """
    big_j = int(v_big * _TA)
    big_k = int(v_big * _TB)
    if cap is not None:
        big_j = min(big_j, cap)
        big_k = min(big_k, cap)
    return {"无": 0, "微": v_tiny, "小": v_small, "中": v_mid, "大": v_big,
            "巨": big_j, "极": big_k}


_P1_ATT_DELTA = _tier7(3, 5, 6, 8, cap=8)      # 外交 attitude ±3~±8（CAP 8）
_P1_ARM_DELTA = _tier7(10000, 20000, 35000, 50000, cap=50000)   # 兵额 ±1万~±5万（CAP 5万）
_P1_TRAIN_DELTA = _tier7(2, 3, 5, 6)           # 训练/士气 ±2~±6
_P1_LEVY_COST = _tier7(100000, 200000, 350000, 500000)  # 征发 cost 10万~50万
_P1_RELIEF = _tier7(100000, 200000, 350000, 500000)     # 赈济 10万~50万石
_P1_REFUGEE = _tier7(50000, 120000, 200000, 300000)     # 流民 ±5万~±30万


def _settle_military_diplomacy(state, log):
    """军事与外部势力推进（12 步 agent 化 P1：外交/军事契约接线，守恒铁律——
    岁币金额/兵额扣补走既有守恒步，agent 只给档位词）"""
    tl = state.timeline
    _dip = getattr(state, "_diplomacy_ai", None)
    _mil = getattr(state, "_military_ai", None)

    # 外交契约（attitude 档位 → ±3~±8；岁币/盟约布尔）
    if isinstance(_dip, dict) and not _dip.get("_error"):
        d = _P1_ATT_DELTA.get(_dip.get("attitude", "小"), 5)
        for k in ("金", "辽", "西夏"):
            cur = state.external[k]["attitude"]
            direction = 1 if cur < 70 else -1     # 岁币阈值 70 同源：低于趋善、高于遏制
            state.external[k]["attitude"] = max(0, min(100, cur + direction * d))
        if _dip.get("sui_gong") == "订":
            state._sui_gong = True
        elif _dip.get("sui_gong") == "毁":
            state._sui_gong = False
        if _dip.get("alliance") == "结":
            state.alliance_jin_liao = True
        elif _dip.get("alliance") == "断":
            state.alliance_jin_liao = False

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

    # 军事契约（power%/兵额/训练士气/征发——训练士气与兵额调整程序换算，cost 由守恒步扣）
    # 审查 P1：无论有无 AI，一律叠加月度衰减基线（防只增不减导致士气/训练长期膨胀）
    for u in state.army_units:
        if random.random() < 0.15:
            u.training = max(10, u.training - random.randint(1, 2))
        if random.random() < 0.10:
            u.morale = max(10, u.morale - 1)
    if isinstance(_mil, dict) and not _mil.get("_error"):
        for u in state.army_units:
            u.training = max(10, min(100, u.training + _P1_TRAIN_DELTA.get(_mil.get("training", "微"), 2)))
            u.morale = max(10, min(100, u.morale + _P1_TRAIN_DELTA.get(_mil.get("morale", "微"), 2)))
        # 兵额调整：AI 只可减员（裁汰）；增募必须走批红军令通道（防 AI 直接铸兵）
        # 审查修复三处：
        #  (1) 原判 d_arm < 0，而 _P1_ARM_DELTA 全为正值（1万~5万）→ 本分支实为死码；
        #      语义应为「该档位即裁汰额上限」，故改判 _cut > 0；
        #  (2) 原直接改 branches 字典，绕开 add_troops（真账=Σbranches，余数归主兵种）；
        #      改用 add_troops(-_cut)；
        #  (3) 裁下的人丁原凭空消失，现经 _return_men 回流本路农户（人守恒）。
        # 另：默认档由「微」改「无(=0)」——缺 army 键时不应凭空裁汰一万人。
        _cut = _P1_ARM_DELTA.get(_mil.get("army", "无"), 0)
        if _cut > 0 and state.army_units:
            u = max(state.army_units, key=lambda x: x.troops)
            _cut = min(_cut, u.troops)
            if _cut > 0:
                u.add_troops(-_cut)
                _return_men(state, u.station, _cut)
                log.append(f"[枢密] 裁汰冗兵 {_cut} 人（人丁还民）")
        levy = _P1_LEVY_COST.get(_mil.get("levy", "微"), 100000)
        if getattr(state, "treasury", 0) >= levy:
            state.change_treasury(-levy)     # 征发 cost 守恒扣款（程序，非 agent 直写）
            log.append(f"[枢密] 征发军资 {levy} 贯")


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
    # P0-③ 起义类事件压力仅在史实窗口（1118 年方腊/1111 年宋江起）受
    # 流民/太仓/米价/民怨推动，杜绝 1101 年开局即触发 1118 年起义（史实错误）。
    if state.year >= 1118:
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
    # 记忆知识库（Phase 3a）：事件落地写入图谱（event 实体 + involves）
    try:
        state.memory.turn = state.turn
        state.memory.record_event(f"event_{state.turn}_{category}", category, turn=state.turn)
    except Exception:
        pass


# ------------------------------------------------------------
# Step 8: 灾荒结算
# ------------------------------------------------------------


# ------------------------------------------------------------
# Step 9: 皇帝个人结算（契约 v2 重做，A15 素材）
# ------------------------------------------------------------
def _settle_emperor_personal(state, log):
    """皇帝个人行动结算（行动矩阵契约 v2）。

    时序：带宽回调 → 自然衰老 → 出京政务减损（远程批奏 -1）→
    出京准备期月度推进（pending_imperial_trip）→ 成行落地（程序基础开销守恒 +
    效果档位落地 + 风险事件）→ 清场（行动/准备/微服计数/旧字段）。
    AI（_emperor_ai 契约 v2）只给 effects 档位词与 risk/narrative；失败走矩阵
    base_effects 程序兜底（不伪造 AI 文本）。费用由程序按行动类型核算，AI 不写数值。
    """
    # 1) 基础回调：上月临时带宽过期（最低 6）
    state.decree_bandwidth = max(6, state.decree_bandwidth - 2)

    # 2) 自然衰老（原有；健康不触发 game over，仅影响衰减/行动）
    if state.year >= 1120:
        natural_decay = 1 + (state.year - 1120) // 2
    else:
        natural_decay = (state.year - 1101) // 4
    if natural_decay > 0:
        state.emperor_health = max(0, state.emperor_health - natural_decay)
        log.append(f"[皇帝] 春秋渐高，龙体自然损耗 {natural_decay}")

    # 3) 公开出京：不影响政务（远程批奏），圣旨带宽仅 -1
    act = state.imperial_action or {}
    if act and act.get("location") == "出京" and act.get("mode") == "公开":
        state.decree_bandwidth = max(5, state.decree_bandwidth - 1)
        log.append("[皇帝] 大驾出京，政务远程批奏，圣旨额度稍减（-1）")

    # 4) 出京准备期月度推进（pending_imperial_trip）
    if getattr(state, "pending_imperial_trip", None) is not None:
        state.pending_imperial_trip["pending_months"] = max(
            0, state.pending_imperial_trip.get("pending_months", 1) - 1)
        if state.pending_imperial_trip.get("pending_months", 0) > 0:
            _left = state.pending_imperial_trip["pending_months"]
            log.append(f"[皇帝] {act.get('action', '出京')}准备中，尚余 {_left} 月")
            state.personal_action = ""
            state.major_policy = ""
            state.imperial_micro_count = 0
            return
        log.append("[皇帝] 銮驾备毕，本月成行")

    # 5) 行动落地（宫里/京城 当月生效；出京准备完成当月成行）
    if act:
        _apply_imperial_action(state, act, log)
    else:
        # 旧档/旧通道兼容：单值 personal_action → 宫里·公开 矩阵行动
        from content.data import LEGACY_PERSONAL_ACTION_MAP
        _legacy = LEGACY_PERSONAL_ACTION_MAP.get(getattr(state, "personal_action", ""))
        if _legacy:
            state.imperial_action = {
                "location": "宫里", "mode": "公开", "action": _legacy,
                "prepared": False, "pending_months": 0, "target": "",
            }
            _apply_imperial_action(state, state.imperial_action, log)
        else:
            # 无行动：龙体自然起伏（原有 idle 漂移）
            state.emperor_health = max(0, min(100,
                state.emperor_health + random.randint(-1, 1)))

    # 6) 清场
    state.imperial_action = {}
    state.pending_imperial_trip = None
    state.personal_action = ""
    state.major_policy = ""
    state.imperial_micro_count = 0


def _imp_split_tier(value):
    """皇帝行动效果档位拆解：'±档位词' → (档位词, 方向 ±1)；数字原样 (值, +1)。"""
    if isinstance(value, (int, float)):
        return str(value), 1.0
    text = str(value).strip()
    direction = 1.0
    if text.startswith("+"):
        text = text[1:]
    elif text.startswith("-"):
        direction = -1.0
        text = text[1:]
    return text, direction


def _imp_tier_delta(dim, tier, direction):
    """档位词 → 数值：prestige/民心走 ai.client_utils 既有换算；
    健康/心情等 0~100 刻度维度用 IMPERIAL_EFFECT_BASE 基准（单一权威源 content.data）。"""
    from content.data import IMPERIAL_EFFECT_BASE
    if dim == "prestige":
        from ai.client_utils import tier_to_value
        return int(round(direction * tier_to_value("prestige", tier, 1.0)))
    if dim == "population_satisfaction":
        from ai.client_utils import tier_to_value
        return int(round(direction * tier_to_value("population_satisfaction", tier, 1.0)))
    base = IMPERIAL_EFFECT_BASE.get(dim, 3.0)
    return int(round(direction * base * TIER_RANGE.get(tier, 0.0)))


def _apply_imperial_action(state, act, log):
    """落地皇帝个人行动：程序基础开销（守恒）→ 效果（AI 档位/矩阵兜底）→ 风险事件。"""
    from content.data import (IMPERIAL_ACTION_MATRIX, IMPERIAL_RISK_PROB,
                              IMPERIAL_EFFECT_DIM)
    from core.events import get_imperial_risk_event
    cell = (IMPERIAL_ACTION_MATRIX.get(act.get("location", ""), {})
                                   .get(act.get("mode", ""), {}).get(act.get("action", "")))
    if not cell:
        log.append("[皇帝] 行止无效（矩阵外），未执行")
        return
    _name = f"{act.get('location', '')}·{act.get('mode', '')}·{act.get('action', '')}"

    # 1) 程序基础开销（守恒：公开→国库 / 微服→内帑；AI 不写数值）
    cost = int(cell.get("base_cost", 0))
    fund = cell.get("fund", "treasury")
    if cost > 0:
        avail = state.treasury if fund == "treasury" else state.imperial_treasury
        paid = min(cost, max(0, int(avail)))
        short = cost - paid
        # 2026-09-18 测试体检修复（货币守恒）：原为裸扣（`change_treasury(-paid)` /
        # `imperial_treasury -= paid`）—— 无对手方，皇帝个人行动的度支凭空消失。
        # 皇帝挥霍/兴造是**宫廷支出**，按"支出回流"口径转入民间（工匠40%/商人60%），
        # 与 `_settle_finance` 常费、`_settle_upkeep` 维持费、国策度支同口径。
        _given = 0
        if paid > 0:
            if fund == "treasury":
                state.change_treasury(-paid)
            else:
                state.imperial_treasury = max(0, state.imperial_treasury - paid)
            try:
                from content.data import GOV_SPEND_TO
                _given = _distribute_cash(state, paid, GOV_SPEND_TO)
            except Exception:            # noqa: BLE001
                _given = 0
            if _given != paid:           # 无接收方兜底：退回国库/内帑，不静默销毁
                _back = paid - _given
                if fund == "treasury":
                    state.change_treasury(_back)
                else:
                    state.imperial_treasury += _back
        _note = f"（府库不足，缺 {short:,} 贯）" if short else ""
        _src = "国库" if fund == "treasury" else "内帑"
        log.append(f"[皇帝] {_name}：{_src}支 {paid:,} 贯{_note}")

    # 2) 效果：矩阵 base_effects（程序兜底）+ AI 契约 v2 档位词（有则覆盖核心 4 键）
    _ai = getattr(state, "_emperor_ai", None)
    ai_eff = _ai.get("effects") if isinstance(_ai, dict) and not _ai.get("_error") else None
    deltas = {}
    for k, v in (cell.get("base_effects") or {}).items():
        if k == "faction_change":
            continue  # 派系单独处理（见落地）
        deltas[k] = v
    if isinstance(ai_eff, dict):
        for k, tier in ai_eff.items():
            dim = IMPERIAL_EFFECT_DIM.get(k)
            if not dim:
                continue
            t, d = _imp_split_tier(tier)
            deltas[dim] = _imp_tier_delta(dim, t, d)   # AI 覆盖 base 的同键
    _apply_imperial_effects(state, deltas, cell, log, _name)

    # 3) 风险事件（risk 档 → 程序概率：低2%/中8%/高20%；时代门槛/史实锚见 events.py）
    risk = cell.get("risk", "低")
    if isinstance(_ai, dict) and not _ai.get("_error") and _ai.get("risk") in IMPERIAL_RISK_PROB:
        risk = _ai["risk"]
    prob = IMPERIAL_RISK_PROB.get(risk, 0.02)
    if random.random() < prob:
        ev = get_imperial_risk_event(state, act)
        if ev:
            _apply_imperial_effects(state, ev.get("effects") or {}, None, log, ev.get("title", "风险事件"))
            _tag = ev.get("label", "合理推演")
            _desc = ev.get("desc", "")
            log.append(f"[风险·{_tag}] {ev.get('title', '')}：{_desc}")
            state.active_events.append({"title": ev.get("title", "风险事件"),
                                        "message": _desc, "label": _tag, "risk": risk})
            state.event_history.append(ev)
            try:
                state.memory.record_event(f"imperial_{ev.get('id', 'risk')}",
                                          ev.get("title", ""), involved=(), turn=state.turn)
            except Exception:
                pass  # 记忆写入失败不阻断结算


def _apply_imperial_effects(state, effects, cell, log, name):
    """效果落地（state_applier 白名单 path：prestige/population_satisfaction/emperor_health/
    art_mastery/taoism_leaning/pleasure_leaning/factions.*.satisfaction/decree_bandwidth）。"""
    if "bandwidth_bonus" in effects:
        state.decree_bandwidth = min(10, state.decree_bandwidth + int(effects["bandwidth_bonus"]))
    if "prestige" in effects:
        d = int(effects["prestige"])
        state.change_prestige(d, name)
        log.append(f"[皇帝] {name}：皇威 {'+' if d >= 0 else ''}{d}")
    if "population_satisfaction" in effects:
        d = int(effects["population_satisfaction"])
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + d))
        log.append(f"[皇帝] {name}：民心 {'+' if d >= 0 else ''}{d}")
    if "emperor_health" in effects:
        d = int(effects["emperor_health"])
        state.emperor_health = max(0, min(100, state.emperor_health + d))
        log.append(f"[皇帝] {name}：龙体 {'+' if d >= 0 else ''}{d}")
    if "pleasure_leaning" in effects:
        d = int(effects["pleasure_leaning"])
        state.pleasure_leaning = max(0, min(100, state.pleasure_leaning + d))
    if "art_mastery" in effects:
        d = int(effects["art_mastery"])
        state.art_mastery = max(0, min(100, state.art_mastery + d))
    if "taoism_leaning" in effects:
        d = int(effects["taoism_leaning"])
        state.taoism_leaning = max(0, min(100, state.taoism_leaning + d))
    if "treasury" in effects:
        d = int(effects["treasury"])
        state.change_treasury(d)   # 风险事件（地方应奉/花石纲等）显式收支，reason 见事件描述
        log.append(f"[皇帝] {name}：国帑 {'+' if d >= 0 else ''}{d:,} 贯")
    if cell and (cell.get("base_effects") or {}).get("faction_change"):
        for fname, d in (cell["base_effects"]["faction_change"] or {}).items():
            if fname in state.factions:
                state.factions[fname]["satisfaction"] = max(0, min(100,
                    state.factions[fname]["satisfaction"] + int(d)))
                log.append(f"[皇帝] {name}：{fname}满意度 {'+' if d >= 0 else ''}{d}")


# ------------------------------------------------------------
# Step 10: 隐藏状态
# ------------------------------------------------------------
def _settle_hidden(state, log):
    """隐藏状态结算（灾害、政令累积效果等）"""
    # 隐户动态（用户指示：隐户是动态人口池，与六类 POP 转换，非静态）——月度逃户/归籍
    try:
        _settle_hidden_pop(state, log)
    except Exception:
        pass
    if state.population_satisfaction < 30:
        if random.random() < 0.15:
            # 审查 P2-21：补下限钳制（其余结算处均已 max(0,…)，此处漏）
            state.population_satisfaction = max(0, state.population_satisfaction - 1)
            log.append("[激变] 民怨沸腾，偶有骚乱")

    jin = state.external["金"]
    if jin.get("invasion_will", 0) >= 90 and state.year >= 1122:
        if random.random() < 0.08:
            from core.army_models import _army_power, _army_power_total, _resolve_battle
            jin["invasion_will"] = 80
            gunpowder = state.tech.get("gunpowder", 20)
            front_routes = ("河北路", "河东路", "陕西路")
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
                    u.add_troops(-part)
                    assigned += part
                rest = min(total_cas - assigned, front_units[main_idx].troops)
                front_units[main_idx].add_troops(-max(0, rest))
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


# ============================================================
# 财政结算（原 settlement_finance.py 内联）
# ============================================================
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
def _settle_tax_grain_sale(state, p, need: int) -> int:
    """农户「粜粮完税」：现金不足时向本路 `士绅`/`商人` 卖粮换钱，用于缴纳当期税。

    ## 为什么需要它（历史↔游戏性取中）

    实证：农户 POP 现金恒低于「1 月口粮折价 × 保底系数」，于是**役钱与自耕田折色
    全部记为欠税且永不回收**（60 月累计农欠税 4,399 万贯）——农税通道整体是死账。
    这既不史实（免役钱、二税折色本是**现钱**之征，农户卖粮完税是常态），
    也不好玩（"三冗 → 加征 → 民怨"这条链在农户一侧根本传导不到）。

    ## 守恒（两条同时成立）

    - **钱**：`士绅/商人.wealth → 农.wealth`，Σ钱 不变，`ΔM_ALL == 0`（不造币）；
    - **粮**：`农.grain → 士绅/商人.grain`，Σ粮 不变（不凭空生粮）。

    买主是**豪强/粮商**（史实如此），不是朝廷——所以它不是"国库自己给自己付钱"的循环。

    ## 约束

    - 仅在**现金不足**时触发，且只补当期缺口；
    - 卖后须留 `FARMER_TAX_GRAIN_KEEP_MONTHS` 个月口粮；
    - 单月最多卖农存粮的 `TAX_GRAIN_SALE_MAX_SHARE`。

    返回实际换得、可用于缴税的现钱（贯）。
    """
    from content.data import (FARMER_TAX_GRAIN_KEEP_MONTHS, PER_CAPITA_MONTH_GRAIN,
                              TAX_GRAIN_SALE_ENABLED, TAX_GRAIN_SALE_MAX_SHARE)

    if not TAX_GRAIN_SALE_ENABLED or need <= 0:
        return 0
    pops = p.get("pops") or {}
    farm = pops.get("农")
    if not isinstance(farm, dict):
        return 0
    price = float(getattr(state, "grain_price", 1.0) or 1.0)
    if price <= 0:
        return 0

    keep = int(int(farm.get("size", 0) or 0) * PER_CAPITA_MONTH_GRAIN
               * FARMER_TAX_GRAIN_KEEP_MONTHS)
    cap_month = int(int(farm.get("grain", 0) or 0) * TAX_GRAIN_SALE_MAX_SHARE)
    sellable = max(0, min(int(farm.get("grain", 0) or 0) - keep, cap_month))
    if sellable <= 0:
        return 0

    # 卖多少粮够补缺口
    want_grain = int(need / price) + 1
    grain = min(sellable, want_grain)
    if grain <= 0:
        return 0

    # 买方：本路 士绅 ＋ 商人，按持钱比例（买不起则按实际成交）
    buyers = [(k, pops.get(k)) for k in ("士绅", "商人")]
    buyers = [(k, b) for k, b in buyers if isinstance(b, dict) and int(b.get("wealth", 0) or 0) > 0]
    if not buyers:
        return 0
    avail = sum(int(b.get("wealth", 0) or 0) for _, b in buyers)
    cost = min(int(grain * price), avail)
    grain = min(grain, int(cost / price))
    if grain <= 0 or cost <= 0:
        return 0

    # 分钱（末位吃尾差，Σ付出 == cost）；分粮（末位吃尾差，Σ得粮 == grain）
    paid = 0
    gave = 0
    n = len(buyers)
    for i, (_k, b) in enumerate(buyers):
        pay = (cost - paid) if i == n - 1 else int(cost * int(b.get("wealth", 0) or 0) / max(1, avail))
        pay = max(0, min(pay, int(b.get("wealth", 0) or 0)))
        g = (grain - gave) if i == n - 1 else int(grain * int(b.get("wealth", 0) or 0) / max(1, avail))
        g = max(0, g)
        b["wealth"] = int(b.get("wealth", 0) or 0) - pay
        b["grain"] = int(b.get("grain", 0) or 0) + g
        paid += pay
        gave += g

    # 若因逐户封顶导致实际成交少于计划：以实际为准（粮随钱走，双向精确守恒）
    if gave > grain:
        gave = grain
    farm["grain"] = int(farm.get("grain", 0) or 0) - gave
    farm["wealth"] = int(farm.get("wealth", 0) or 0) + paid
    state.statistics["tax_grain_sale"] = state.statistics.get("tax_grain_sale", 0) + paid
    state.granary_stats["tax_grain_sold"] = \
        state.granary_stats.get("tax_grain_sold", 0) + gave
    return paid


def _settle_arrears_repayment(state, log):
    """结余**补发积欠**（史实：丰年补发积欠俸饷）。

    为什么需要：取中校准后国帑在长局中转为丰裕（240 月 4,682 万贯），而
    `statistics["pay_arrears"]`（按实付产生的欠饷欠俸）仍在**单向累积** ——
    「国库满、军队欠饷」是玩家一眼能看出的自相矛盾。史实上朝廷在宽裕时确实补发积欠。

    守恒：**国库 → 兵/官僚 POP `wealth`**，纯转移（`ΔM_ALL == 0`），不造币；
    同时按同一比例冲减各军 `ArmyUnit.arrears`，保持「Σ各军欠饷 ↔ `pay_arrears`」同源。

    仅动用**超出应急安全库存**的结余，且单月只补 `ARREARS_REPAY_SHARE`——
    避免"一丰就花光"，也避免把它变成自动清零欠饷的假机制。
    """
    from content.data import ARREARS_KEEP_TREASURY, ARREARS_REPAY_SHARE

    arrears = int(state.statistics.get("pay_arrears", 0) or 0)
    if arrears <= 0:
        return 0
    usable = max(0, int(state.treasury or 0) - int(ARREARS_KEEP_TREASURY))
    amount = int(min(usable * ARREARS_REPAY_SHARE, arrears))
    if amount <= 0:
        return 0

    state.change_treasury(-amount)

    _total_army = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values())
    _total_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values())
    _scale = _total_army + _total_guan
    if _scale <= 0:                      # 无接收方：退回国库，不静默销毁
        state.change_treasury(amount)
        return 0
    _army_amt = int(amount * _total_army / _scale)
    _guan_amt = amount - _army_amt
    # 分配给兵/官僚 POP。权重把"兵总额/官僚总额"的分配与"按 size 摊到各路"**合成一次**，
    # 末位吃尾差 → `Σ入账 == amount` 精确成立（不再有分配残差需要退回国库）。
    _receivers = []
    for _p in state.prefectures.values():
        _b, _g = _p["pops"]["兵"], _p["pops"]["官僚"]
        if _total_army > 0 and int(_b.get("size", 0) or 0) > 0:
            _receivers.append((_b, int(_b["size"]) * _army_amt / _total_army))
        if _total_guan > 0 and int(_g.get("size", 0) or 0) > 0:
            _receivers.append((_g, int(_g["size"]) * _guan_amt / _total_guan))
    _tot_w = sum(_w for _, _w in _receivers)
    if _tot_w <= 0:                      # 无接收方：退回国库，不静默销毁
        state.change_treasury(amount)
        return 0
    _given = 0
    for _i, (_pop, _w) in enumerate(_receivers):
        _gv = (amount - _given) if _i == len(_receivers) - 1 else int(amount * _w / _tot_w)
        _gv = max(0, _gv)
        _pop["wealth"] = int(_pop.get("wealth", 0) or 0) + _gv
        _given += _gv

    # 冲减各军欠饷（同源同减；军饷欠额大，按剩余欠饷比例摊还）
    _unit_due = {}
    for _u in state.army_units:
        _d = float(getattr(_u, "arrears", 0) or 0)
        if _d > 0:
            _unit_due[_u.unit_id or id(_u)] = _d
    _due_total = sum(_unit_due.values())
    if _due_total > 0:
        for _u in state.army_units:
            _k = _u.unit_id or id(_u)
            if _k in _unit_due:
                _u.arrears = max(0, int(getattr(_u, "arrears", 0))
                                 - int(_army_amt * _unit_due[_k] / _due_total))

    state.statistics["pay_arrears"] = max(0, arrears - amount)
    state.statistics["arrears_repaid"] = state.statistics.get("arrears_repaid", 0) + amount
    log.append(f"[补发] 帑藏稍丰，补发积欠 {amount:,} 贯"
               f"（欠饷余额 {state.statistics['pay_arrears']:,}）")
    return amount


def _settle_finance(state, log):
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
    state.tax_breakdown = {"commerce": commerce_tax, "poll": poll_tax, "maritime": maritime_tax,
                           "official_service": 0}

    tax_color_total, tax_color_by = state.calc_monthly_tax_income(tax_coeff)
    salt_coin = state.calc_salt_coin(arrival)
    material_coin = 0.0
    monthly_tax_full = monthly_tax + tax_color_total + salt_coin + material_coin  # 目标收入（展示/预期）

    # 税从 POP 征（钱守恒）：役钱→农；二税折色按田亩归属拆分（农担自耕田、士绅担地主田）；工商税→工匠60%+商人40%；盐课+市舶→商人
    from content.data import PER_CAPITA_MONTH_GRAIN
    _tot_land = sum(p.get("land", 1) for p in state.prefectures.values()) or 1
    _self_share = sum(p.get("self_farm_land", 0) for p in state.prefectures.values()) / _tot_land
    _gentry_share = sum(p.get("gentry_land", 0) for p in state.prefectures.values()) / _tot_land
    _tax_agents = {
        "农": poll_tax + int(tax_color_total * _self_share),
        "士绅": int(tax_color_total * _gentry_share),
        # 蔡权衡裁决（工匠外销收入源）：工商税工匠份额 0.6→0.5（工匠税负减轻，配合外销变现防破产）
        "工匠": int(commerce_tax * 0.5),
        "商人": int(commerce_tax * 0.5) + int(salt_coin) + maritime_tax,
    }
    actual_tax = 0.0
    for _agent, _tax_total in _tax_agents.items():
        _total_wealth = sum(p["pops"][_agent]["wealth"] for p in state.prefectures.values())
        if _total_wealth <= 0:
            continue
        for _p in state.prefectures.values():
            _pop = _p["pops"][_agent]
            _deduct = int(_tax_total * (_pop["wealth"] / _total_wealth))
            _min_wealth = int(_pop["size"] * PER_CAPITA_MONTH_GRAIN * state.grain_price)  # 保留1个月口粮钱，不足则欠税
            # 平衡修复（蔡权衡）：保底豁免 × MIN_WEALTH_FLOOR_RATIO（0.75）——农可多缴 25%
            # 仍保生存底线（豁免线×0.5 验证），缓解「粮价下跌→农穷→税豁免」链
            from content.data import MIN_WEALTH_FLOOR_RATIO
            _min_wealth = int(_min_wealth * MIN_WEALTH_FLOOR_RATIO)
            _paid = min(_deduct, max(0, _pop["wealth"] - _min_wealth))
            # ---- 农「粜粮完税」（历史↔游戏性取中）----
            # 农户现金不足时卖粮给本路士绅/商人换钱完税（钱粮双向守恒）。
            # 原实现只把缺口记成欠税，而农户现金恒在保底线之下 → 欠税永不回收、
            # 农税通道整体死掉（60 月累计 4,399 万贯）。
            if _agent == "农" and _deduct - _paid > 0:
                _sold = _settle_tax_grain_sale(state, _p, _deduct - _paid)
                _paid += _sold
            _short = _deduct - _paid
            if _short > 0:
                # A1：缺口记入欠税科目（替代原直接蒸发），后续逐月追缴；存档兼容见 save_load 迁移
                _pop["欠税"] = _pop.get("欠税", 0) + _short
            _pop["wealth"] -= _paid
            actual_tax += _paid   # 累计实际到库税额（保底豁免部分不入库，钱不凭空生）
            # A1 追缴段：紧随税征，按「可支付余力（wealth - 保底线）× ARREARS_COLLECT_RATE」回收欠税
            _recoverable = max(0, _pop["wealth"] - _min_wealth)
            _recover = min(_pop.get("欠税", 0), int(_recoverable * ARREARS_COLLECT_RATE))
            if _recover > 0:
                _pop["wealth"] -= _recover
                _pop["欠税"] = _pop.get("欠税", 0) - _recover
                actual_tax += _recover

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
    # C（A1）：真俸额先算，一体发钞时按真俸额单发交子（替代固定 cash_pay，防"纸钞+现金"双发）
    army_cash_total, _ = state.calc_army_cash()
    official_cash_total, _ = state.calc_official_cash()
    clerk_cash_total, _ = state.calc_clerk_cash()
    personnel_cash = int(army_cash_total + official_cash_total + clerk_cash_total)
    # 官户免役钱（史实免役法·调参定案）：助役钱 = 俸钱总额 × OFFICIAL_SERVICE_TAX_RATIO
    # （基于名义俸禄，指数化前计算，扣缴见俸禄发放后）
    official_service_tax = int((official_cash_total + clerk_cash_total) * OFFICIAL_SERVICE_TAX_RATIO)
    # ---- C-4 免役 → 税基口径（§13.6「冗官经 POP 侵蚀税基」这条链的显式化与可观测化）----
    # 役钱只从 `农` POP 征（乡村主户服徭役）；`士绅`（形势户）、`官僚`（官户）、`兵` 免役。
    # 官府并非全无所得：官户纳**助役钱**（上方 official_service_tax）。
    # 冗官膨胀的两条财政后果因此同时在场：
    #   ① 免除差役的人口↑ → **役钱税基萎缩**（科举寒门从农迁出，农 POP 直接变小）；
    #   ② 助役钱随俸禄总额↑ → 部分**自我补偿**（但只有 5%，远不足以抵消俸禄本身）。
    # 这里把两者记入 `tax_breakdown` / `statistics`，让玩家与 AI 都能看见"税基在缩"。
    _exempt_gentry = sum(p["pops"]["士绅"]["size"] for p in state.prefectures.values())
    _exempt_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values())
    _exempt_army = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values())
    _exempt_pop = _exempt_gentry + _exempt_guan + _exempt_army
    _taxable_pop = sum(p["pops"]["农"]["size"] for p in state.prefectures.values())
    _all_pop = _taxable_pop + _exempt_pop + sum(
        p["pops"]["工匠"]["size"] + p["pops"]["商人"]["size"] for p in state.prefectures.values())
    state.statistics["poll_base_pop"] = _taxable_pop          # 役钱税基（人）
    state.statistics["exempt_pop"] = _exempt_pop              # 免役人口（人）
    state.statistics["exempt_share"] = round(_exempt_pop / max(1, _all_pop), 6)
    state.statistics["poll_tax_nominal"] = poll_tax
    # T9 俸禄指数化（Step 4）：粮价 > PAY_INDEX_BASE 时俸禄 ×(1 + PAY_INDEX_STEP×超额)，
    # 抵补官吏/兵卒购买力（粮价通胀时俸禄随涨，防吏治崩坏）；超额 = 粮价 − 基准。
    # P1-1 守恒修复：发放给兵/官僚的俸禄与国库支出同源（同用指数化后金额），
    # 差额不再凭空消失（此前国库扣指数化俸禄、POP 只收未指数化 → 每月货币黑洞）。
    from content.data import PAY_INDEX_BASE, PAY_INDEX_STEP
    _pay_index = 1.0
    if state.grain_price > PAY_INDEX_BASE:
        _pay_index = 1.0 + PAY_INDEX_STEP * (state.grain_price - PAY_INDEX_BASE)
        personnel_cash = int(personnel_cash * _pay_index)
    army_pay = int(army_cash_total * _pay_index)
    official_pay = int((official_cash_total + clerk_cash_total) * _pay_index)
    # 一体发钞：俸禄以交子支付（国库不出现金、POP 不增铜钱）。此标志在两处消费：
    # 俸禄落账（下方 POP wealth）与支出计账（effective_cash_out），必须一致。
    _paper_pay = state.pay_system.get("mode") == "一体发钞"
    if _paper_pay:
        state.jiaozi["issued"] += personnel_cash          # 交子按真俸额发行（单发，替代固定 cash_pay）
        state.jiaozi["trust"] = max(0, state.jiaozi["trust"] - 2)
        expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
        cash_out = 0
    else:
        expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
        cash_out = cash_pay

    corruption_cash_ded, corruption_grain_loss = state.calc_corruption_deduction()
    clerk_gap_total, _ = state.calc_clerk_gap()
    payraise_used = min(state.payraise_budget, int(clerk_gap_total) + 10_000)
    state.payraise_budget = max(0, state.payraise_budget - payraise_used)

    sui_gong = 0
    _mult = getattr(state, "_sui_gong_mult", None) or {}
    if state.external.get("辽", {}).get("attitude", 50) >= 60:
        sui_gong += int(SUI_GONG_ANNUAL * 0.6 / 12 * _mult.get("辽", 1.0))   # 岁币倍率（外交协议）
    if state.external.get("西夏", {}).get("attitude", 50) >= 60:
        sui_gong += int(SUI_GONG_ANNUAL * 0.4 / 12 * _mult.get("西夏", 1.0))
    # 阶段 B-2：岁币岁赐是**真实外流**（钱付与辽/西夏，退出本经济体），
    # 登记为销毁通道，使对账残差不再把它误算成"凭空销毁"。
    if sui_gong > 0:
        try:
            from core.money import register_flow as _reg_flow
            _reg_flow(state, "burn", int(sui_gong), "岁币岁赐外流")
        except Exception:  # noqa: BLE001
            pass

    # 兵 POP size 重聚合（兵额唯一真账 = army_units.troops 求和，避免增募/伤亡后 POP 漂移）
    for _p in state.prefectures.values():
        _p["pops"]["兵"]["size"] = 0
    for _u in state.army_units:
        if _u.station in state.prefectures and _u.troops > 0:
            state.prefectures[_u.station]["pops"]["兵"]["size"] += _u.troops
    # 收支双向落地：国库俸禄钱 → 兵/官僚 POP 钱（闭环，不凭空消失）
    _total_soldiers = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values()) or 1
    _total_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values()) or 1
    # 守恒修复（一体发钞）：俸禄已以交子支付，POP 铜钱不得再增。
    # 原实现无条件给 POP 记铜钱，而同月既发行等额交子、国库又不支出 →
    # 一笔俸禄记两次且凭空造币（货币总账逐月污染）。此处以 _paper_pay 门控。
    # ---- 阶段 B-3：按实付 ＋ 欠饷（修审查 A-2「穿底造币」）----
    # 军俸提至史实水平后（1,349 万贯/年），国库常有力不能及之月。原实现是：
    # POP **全额**收俸禄，而国库侧 `max(0, _avail)` 把差额钳掉、只记 `deficit_depth`
    # → 等于**凭空造币**（月度对账实测残差 +894,491/月，game_over 提前触发）。
    # 现先算支付能力，按比例实付，短付部分记「欠饷/欠俸」科目（与既有「欠税」科目对称）。
    # 语义：宁可欠着（欠饷 → 军心/官僚怨望的后继机制），也绝不凭空造币。
    _civil_back = max(0, expenditure)
    _credits_due = (0 if _paper_pay else personnel_cash) + _civil_back + int(corruption_cash_ded)
    _cash_available = max(0, int(state.treasury) + int(actual_tax) - int(sui_gong))
    _pay_scale = 1.0 if _credits_due <= 0 else min(1.0, _cash_available / float(_credits_due))
    _paid_personnel = int((0 if _paper_pay else personnel_cash) * _pay_scale)
    _paid_civil = int(_civil_back * _pay_scale)
    _paid_corruption = int(int(corruption_cash_ded) * _pay_scale)
    _arrears = _credits_due - (_paid_personnel + _paid_civil + _paid_corruption)
    if _arrears > 0:
        state.statistics["pay_arrears"] = state.statistics.get("pay_arrears", 0) + _arrears
        log.append(f"[财政] 帑藏不足：欠饷欠俸 {_arrears:,} 贯（本月实付率 {_pay_scale:.0%}）")

    # ---- 欠饷落到**各军**（阶段 B-3，用户要求）----
    # 把「军队部分的短付额」按各军本月应发军饷比例分摊，累加到 `ArmyUnit.arrears`。
    # 这样玩家点开任一军，都能看到该军被欠了多少（欠饷 → 军心/士气的后继机制挂点）。
    # 守恒无关（只是把已经发生的短付**记录**到编制单位，不再移动任何钱）。
    if not _paper_pay and _pay_scale < 1.0 and army_pay > 0:
        from content.data import branch_std as _bstd
        _unit_due = {}
        for _u in state.army_units:
            if _u.tier == "乡兵":          # 乡兵无饷（自备），不参与欠饷分摊
                continue
            _due = 0.0
            for _b, _n in (_u.branches or {}).items():
                _due += _n * _bstd(_u.tier, _b)["pay"]
            if _due > 0:
                _unit_due[_u.unit_id] = _due
        _due_total = sum(_unit_due.values()) or 1.0
        _army_due = float(army_pay)
        _army_paid = _army_due - _army_due * _pay_scale
        for _u in state.army_units:
            _due = _unit_due.get(_u.unit_id, 0.0)
            if _due > 0:
                _u.arrears = int(getattr(_u, "arrears", 0)) + int(_army_paid * _due / _due_total)

    # 官户免役钱（史实免役法·调参定案）：官户纳助役钱 = 俸钱总额 × 0.05，
    # 从官僚 POP wealth 按 size 扣缴入国库（钱守恒：官僚交钱、国库收钱，不凭空生钱）
    # 审查 P0：wealth 不足时只按实收入账（_tax_left 反映欠缴，不再全额造币）
    if official_service_tax > 0:
        _tax_left = official_service_tax
        for _p in state.prefectures.values():
            if _p["pops"]["官僚"]["size"] > 0:
                _take = int(official_service_tax * _p["pops"]["官僚"]["size"] / max(_total_guan, 1))
                _take = min(_take, int(_p["pops"]["官僚"]["wealth"]))
                _p["pops"]["官僚"]["wealth"] = max(0, _p["pops"]["官僚"]["wealth"] - _take)
                _tax_left -= _take
        actual_tax += official_service_tax - max(0, _tax_left)
        # 助役钱实收额入账（原先只并入 actual_tax、无科目，玩家看不到"官户也在纳钱"）
        _ost_actual = int(official_service_tax - max(0, _tax_left))
        state.tax_breakdown["official_service"] = _ost_actual
        state.statistics["official_service_tax"] = _ost_actual
    else:
        state.tax_breakdown["official_service"] = 0

    # 收支双向落地：国库俸禄钱 → 兵/官僚 POP 钱（闭环；金额取**实付额**，见上）
    # 守恒修复（一体发钞）：俸禄已以交子支付，POP 铜钱不得再增（_paper_pay 门控）。
    if not _paper_pay and _paid_personnel > 0:
        _ratio_army = army_pay / max(army_pay + official_pay, 1.0)
        _army_paid = int(_paid_personnel * _ratio_army)
        _off_paid = _paid_personnel - _army_paid
        for _p in state.prefectures.values():
            if _p["pops"]["兵"]["size"] > 0:
                _p["pops"]["兵"]["wealth"] += int(_army_paid * _p["pops"]["兵"]["size"] / _total_soldiers)
            if _p["pops"]["官僚"]["size"] > 0:
                _p["pops"]["官僚"]["wealth"] += int(_off_paid * _p["pops"]["官僚"]["size"] / _total_guan)
    # 支出回流（A1 定案·修货币漂移斜率 -13%→-3.5%）：常费不再纯蒸发 → 工匠 40% + 商人 60%（按 size 分摊，
    # 政府花钱买营造/服务/商品，钱进民间）；贪腐扣减 → 官僚 wealth（隐性聚敛，可抄没）；岁币保留销币（真实外流）。
    # 以上三项同样按 **实付额** 落地（`_pay_scale`），保证"扣==收"。
    _total_artisan = sum(p["pops"]["工匠"]["size"] for p in state.prefectures.values()) or 1
    _total_merchant = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
    for _p in state.prefectures.values():
        if _p["pops"]["工匠"]["size"] > 0:
            _p["pops"]["工匠"]["wealth"] += int(_paid_civil * 0.4 * _p["pops"]["工匠"]["size"] / _total_artisan)
        if _p["pops"]["商人"]["size"] > 0:
            _p["pops"]["商人"]["wealth"] += int(_paid_civil * 0.6 * _p["pops"]["商人"]["size"] / _total_merchant)
        if _p["pops"]["官僚"]["size"] > 0:
            _p["pops"]["官僚"]["wealth"] += int(_paid_corruption * _p["pops"]["官僚"]["size"] / _total_guan)
    # 一体发钞时俸禄由交子支付（国库不发现金）；否则按**实付** personnel 计出
    if _paper_pay:
        effective_cash_out = 0
    else:
        effective_cash_out = _paid_personnel
    total_out = (_paid_civil + effective_cash_out
                 + _paid_corruption + payraise_used + sui_gong)
    net = monthly_tax_full - total_out
    # 实际到库净额：保底豁免的税不入国库（钱不凭空生），故用 actual_tax 替代目标 monthly_tax_full
    actual_net = actual_tax - total_out

    treasury_before = state.treasury
    imp_share, wine_coin = state.calc_imperial_treasury(actual_net)
    # 酒课税改造（加消耗完整定案）：酒课（60万贯/月）从工匠 60% / 商人 40% wealth 扣缴入内帑
    # （钱守恒转移，修复现行 wine_coin 凭空入内帑的漏洞；酿酒耗粮另在 Step 3.8 从农存粮扣）
    _wine_tax_cash = int(wine_coin)
    if _wine_tax_cash > 0:
        _art_total = sum(p["pops"]["工匠"]["size"] for p in state.prefectures.values()) or 1
        _mer_total = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
        _wine_left = _wine_tax_cash
        for _p in state.prefectures.values():
            _art, _mer = _p["pops"]["工匠"], _p["pops"]["商人"]
            if _art["size"] > 0:
                _take = int(_wine_tax_cash * 0.6 * _art["size"] / _art_total)
                # P0 修复（蔡权衡·工匠 wealth 归零）：扣缴上限 = 工匠 wealth 的 5%/月
                # （超时代酒课膨胀时扣缴抽干工匠 → 税基崩；上限保工匠生存底线）
                _take = min(_take, int(_art["wealth"] * 0.05))
                _art["wealth"] = max(0, _art["wealth"] - _take)
                _wine_left -= _take
            if _mer["size"] > 0:
                _take = int(_wine_tax_cash * 0.4 * _mer["size"] / _mer_total)
                _take = min(_take, int(_mer["wealth"] * 0.10))
                _mer["wealth"] = max(0, _mer["wealth"] - _take)
                _wine_left -= _take
        # 实征入账（审查 P0：禁止全额入内帑造币）——短征不记入内帑
        _wine_tax_cash = max(0, _wine_tax_cash - max(0, _wine_left))
    # 国库保持整数贯：actual_net 为 float（各 calc_* 乘积），入账前截断
    # B3 修复：国库禁止穿底，不足部分记入**累计亏空深度**（破产两档线的唯一判据），
    # 有结余时优先冲抵历史亏空，余下才进国库。
    _deficit_used = 0
    _avail = state.treasury + int(actual_net) - int(imp_share)
    _prior_deficit = int(getattr(state, "treasury_deficit", 0) or 0)
    if _avail < 0:
        state.treasury_deficit = _prior_deficit + (-_avail)
        _avail = 0
    elif _prior_deficit > 0:
        _deficit_used = min(_prior_deficit, _avail)
        state.treasury_deficit = _prior_deficit - _deficit_used
        _avail -= _deficit_used
    else:
        state.treasury_deficit = 0
    state.treasury = max(0, int(_avail))
    state.imperial_treasury = max(0, state.imperial_treasury + int(imp_share) + int(_wine_tax_cash))
    state.statistics["total_income"] += int(actual_tax)
    state.statistics["total_expenditure"] += total_out

    # 恒等式：未穿底时 Δtreasury == actual_net − imp − 冲抵亏空额；
    # 穿底钳到 0（差额已入 treasury_deficit）时 Δ == -treasury_before
    _delta = state.treasury - treasury_before
    _expect = actual_net - int(imp_share)
    _floored = state.treasury == 0 and (treasury_before + _expect) < 0
    assert _floored or abs(_delta - _expect + _deficit_used) < 1, \
        f"财政恒等断裂：Δtreasury={_delta} actual_net={actual_net} imp={int(imp_share)}"

    # 结余补发积欠（在恒等式校验**之后**执行：它是独立的一笔守恒转移，不改财政恒等）
    _settle_arrears_repayment(state, log)

    inc_parts = f"工商{commerce_tax:.0f}+役钱{poll_tax:.0f}+二税折色{tax_color_total:.0f}+盐课{salt_coin:.0f}"
    if maritime_tax > 0:
        inc_parts += f"+市舶{maritime_tax:.0f}"
    if net < 0:
        log.append(f"[财政] 货币月入 {actual_tax:.0f}贯（{inc_parts}） 支 {total_out:.0f}贯 亏空 {abs(actual_net):.0f}贯（宜折变补之）")
    else:
        log.append(f"[财政] 货币月入 {actual_tax:.0f}贯（{inc_parts}） 支 {total_out:.0f}贯 结余 {actual_net:.0f}贯")
    if sui_gong > 0:
        log.append(f"[岁币] 岁币岁赐 {sui_gong:.0f}贯，纳贡以安边")
        # 审查补齐（外交纪事面板恒空的根因）：本项支付原先只入结算流水，不写
        # state.diplomacy_log —— 而该字段在全库**再无任何写入方**，故面板永久空白
        # （前端它处亦有"（纪事阙文）"兜底文案，正是为此）。
        _dlog = getattr(state, "diplomacy_log", None)
        if isinstance(_dlog, list):
            _parts = []
            if _mult.get("辽", 1.0):
                _parts.append("辽")
            if _mult.get("西夏", 1.0):
                _parts.append("西夏")
            _dlog.append({
                "year": int(getattr(state, "year", 0) or 0),
                "month": int(getattr(state, "month", 0) or 0),
                "text": f"输岁币岁赐 {int(sui_gong)}贯（{'、'.join(_parts) or '北境'}），纳贡以安边",
            })

    from content.data import TREASURY_CRISIS_LINE
    # B3：判据由「负国库」改为「累计亏空深度」（国库禁穿底，负值不可达）。
    if state.deficit_depth() > TREASURY_CRISIS_LINE:
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


# ============================================================
# 灾荒结算（原 settlement_disaster.py 内联）
# ============================================================
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
    """天灾结算。灾荒时开仓赈济，耗太仓存粮；有粮则安民，无粮则民怨更重。

    12 步 agent 化 P1：有 _relief_ai 契约（按察使）时赈济量/流民按档位换算（10万~50万石、
    流民 ±5万~±30万），灾级 1~5 放大既有减产/粮价；无契约走既有 DISASTER_RELIEF_GRAIN。
    守恒铁律：赈济扣太仓/流民回流农 POP 由本步程序守恒（agent 只给档位词）。
    """
    _relief_ai = getattr(state, "_relief_ai", None)
    relief_grain = DISASTER_RELIEF_GRAIN
    if isinstance(_relief_ai, dict) and not _relief_ai.get("_error"):
        relief_grain = _P1_RELIEF.get(_relief_ai.get("relief", "微"), DISASTER_RELIEF_GRAIN)
        # 灾级 1~5 放大既有公式（减产/粮价由灾荒触发方按 severity 处理）
        state.disaster_severity = max(1, min(5, int(_relief_ai.get("disaster_level", 1))))
    if state.disaster_severity > 0:
        state.disaster_severity = max(0, state.disaster_severity - 1)
        relief = min(relief_grain, state.granary)
        state.change_granary(-relief)
        state.granary_stats["relief"] += relief
        if relief >= relief_grain:
            state.population_satisfaction = max(0, min(100, state.population_satisfaction + 1))
            relieved = relief * 3000
            region = _normalize_disaster_region(state, state.disaster_region)
            if region is not None:
                local = state.prefectures[region].get("refugees", 0)
                used = min(relieved, local)
                state.prefectures[region]["refugees"] = max(0, local - used)
                # 人口守恒（QA 定位修复）：本地安置流民回流农 POP（流民→自耕农/佃户），
                # 防止"流民减少但人口凭空消失"；人口守恒：本地 used + 邻路 Σadd == 流民减少 == 农 POP 增加。
                state.prefectures[region]["pops"]["农"]["size"] += used
                spill = relieved - used
            else:
                used = 0
                spill = relieved
            if spill > 0:
                others = {k: v.get("refugees", 0) for k, v in state.prefectures.items()}
                tot = sum(others.values())
                if tot > 0:
                    for k, rv in others.items():
                        # add 受该路流民存量约束（min(rv)）：每路最多安置其全部流民，
                        # 防止赈济能力（relief×3000）远超流民存量时"超额安置"凭空创造人口。
                        add = min(int(spill * rv / tot), rv)
                        if add > 0:
                            state.prefectures[k]["refugees"] = max(0, state.prefectures[k]["refugees"] - add)
                            # 人口守恒（QA 定位修复）：溢邻路安置流民回流该路农 POP
                            state.prefectures[k]["pops"]["农"]["size"] += add
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
            # BUG#2 修复（人口守恒，与 BUG#1 对称）：灾荒新发流民不再凭空增——
            # flee 受 add_ref、流民 cap 余量与农 POP size 三重约束；
            # 受灾农 POP 减少 flee（逃荒为流民），流民增加 flee，人口不凭空增减。
            room = max(0, cap - p.get("refugees", 0))
            flee = min(add_ref, room, p["pops"]["农"]["size"])
            p["pops"]["农"]["size"] -= flee
            p["refugees"] = p.get("refugees", 0) + flee
            # 灾荒减产：受灾路年产减产（8%/级），下次收获即少粮，体现"灾年减产"而非只涨价
            p["grain"] = int(p.get("grain", 0) * (1 - 0.08 * severity))
            log.append(f"[流民] {region}灾荒（{severity}级），本地流民骤增 {flee}，四散就食，田禾减产")
        log.append(f"[灾荒] {region}发生灾荒！严重度 {severity}")
        state.statistics["total_disasters"] += 1
