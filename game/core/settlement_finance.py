# -*- coding: utf-8 -*-
"""宋祚 · Step 4 财政结算子模块。

拆分自 core/settlement_steps.py：财政收支结算、区域粮价重算、贪腐均值。
主流程见 core/settlement.py；本模块被 settlement_steps re-export 保持调用兼容。
"""
import random
from typing import Any

from content.data import (
    TAX_COEFF_MIN, TAX_COEFF_MAX, TAX_POLL_RATIO,
    COMMERCE_TAX_RATE_DEFAULT, COMMERCE_TAX_RATE_MIN, COMMERCE_TAX_RATE_MAX,
    PAY_CASH_BASE, MONTHLY_EXP_CIVIL_BASE, SUI_GONG_ANNUAL,
    GRAIN_PRICE_MIN, GRAIN_PRICE_MAX,
    ARREARS_COLLECT_RATE, OFFICIAL_SERVICE_TAX_RATIO,
)


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
    monthly_tax_full = monthly_tax + tax_color_total + salt_coin + material_coin  # 目标收入（展示/预期）

    # 税从 POP 征（钱守恒）：役钱→农；二税折色按田亩归属拆分（农担自耕田、士绅担地主田）；工商税→工匠60%+商人40%；盐课+市舶→商人
    from content.data import PER_CAPITA_MONTH_GRAIN
    _tot_land = sum(p.get("land", 1) for p in state.prefectures.values()) or 1
    _self_share = sum(p.get("self_farm_land", 0) for p in state.prefectures.values()) / _tot_land
    _gentry_share = sum(p.get("gentry_land", 0) for p in state.prefectures.values()) / _tot_land
    _tax_agents = {
        "农": poll_tax + int(tax_color_total * _self_share),
        "士绅": int(tax_color_total * _gentry_share),
        "工匠": int(commerce_tax * 0.6),
        "商人": int(commerce_tax * 0.4) + int(salt_coin) + maritime_tax,
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
    # 官户免役钱（史实免役法·调参定案）：助役钱 = 俸钱总额 × OFFICIAL_SERVICE_TAX_RATIO（扣缴见俸禄发放后）
    official_service_tax = int((official_cash_total + clerk_cash_total) * OFFICIAL_SERVICE_TAX_RATIO)
    if state.pay_system.get("mode") == "一体发钞":
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
    if state.external.get("辽", {}).get("attitude", 50) >= 60:
        sui_gong += int(SUI_GONG_ANNUAL * 0.6 / 12)
    if state.external.get("西夏", {}).get("attitude", 50) >= 60:
        sui_gong += int(SUI_GONG_ANNUAL * 0.4 / 12)

    # 兵 POP size 重聚合（兵额唯一真账 = army_units.troops 求和，避免增募/伤亡后 POP 漂移）
    for _p in state.prefectures.values():
        _p["pops"]["兵"]["size"] = 0
    for _u in state.army_units:
        if _u.station in state.prefectures and _u.troops > 0:
            state.prefectures[_u.station]["pops"]["兵"]["size"] += _u.troops
    # 收支双向落地：国库俸禄钱 → 兵/官僚 POP 钱（闭环，不凭空消失）
    _total_soldiers = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values()) or 1
    _total_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values()) or 1
    for _p in state.prefectures.values():
        if _p["pops"]["兵"]["size"] > 0:
            _p["pops"]["兵"]["wealth"] += int(army_cash_total * _p["pops"]["兵"]["size"] / _total_soldiers)
        if _p["pops"]["官僚"]["size"] > 0:
            _p["pops"]["官僚"]["wealth"] += int((official_cash_total + clerk_cash_total) * _p["pops"]["官僚"]["size"] / _total_guan)
    # 官户免役钱（史实免役法·调参定案）：官户纳助役钱 = 俸钱总额 × 0.05，
    # 从官僚 POP wealth 按 size 扣缴入国库（钱守恒：官僚交钱、国库收钱，不凭空生钱）
    if official_service_tax > 0:
        _tax_left = official_service_tax
        for _p in state.prefectures.values():
            if _p["pops"]["官僚"]["size"] > 0:
                _take = int(official_service_tax * _p["pops"]["官僚"]["size"] / max(_total_guan, 1))
                _p["pops"]["官僚"]["wealth"] = max(0, _p["pops"]["官僚"]["wealth"] - _take)
                _tax_left -= _take
        actual_tax += official_service_tax
    # 支出回流（A1 定案·修货币漂移斜率 -13%→-3.5%）：常费不再纯蒸发 → 工匠 40% + 商人 60%（按 size 分摊，
    # 政府花钱买营造/服务/商品，钱进民间）；贪腐扣减 → 官僚 wealth（隐性聚敛，可抄没）；岁币保留销币（真实外流）。
    _civil_back = max(0, expenditure)
    _total_artisan = sum(p["pops"]["工匠"]["size"] for p in state.prefectures.values()) or 1
    _total_merchant = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
    for _p in state.prefectures.values():
        if _p["pops"]["工匠"]["size"] > 0:
            _p["pops"]["工匠"]["wealth"] += int(_civil_back * 0.4 * _p["pops"]["工匠"]["size"] / _total_artisan)
        if _p["pops"]["商人"]["size"] > 0:
            _p["pops"]["商人"]["wealth"] += int(_civil_back * 0.6 * _p["pops"]["商人"]["size"] / _total_merchant)
        if _p["pops"]["官僚"]["size"] > 0:
            _p["pops"]["官僚"]["wealth"] += int(int(corruption_cash_ded) * _p["pops"]["官僚"]["size"] / _total_guan)
    # 一体发钞时俸禄由交子支付（国库不发现金）；否则按实际发放 personnel_cash 计出（不以 cash_out 上限蒸发）
    if state.pay_system.get("mode") == "一体发钞":
        effective_cash_out = 0
    else:
        effective_cash_out = personnel_cash
    total_out = (expenditure + effective_cash_out
                 + int(corruption_cash_ded) + payraise_used + sui_gong)
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
                _art["wealth"] = max(0, _art["wealth"] - _take)
                _wine_left -= _take
            if _mer["size"] > 0:
                _take = int(_wine_tax_cash * 0.4 * _mer["size"] / _mer_total)
                _mer["wealth"] = max(0, _mer["wealth"] - _take)
                _wine_left -= _take
    # 国库保持整数贯：actual_net 为 float（各 calc_* 乘积），入账前截断
    state.treasury += int(actual_net) - int(imp_share)
    state.imperial_treasury += int(imp_share) + _wine_tax_cash
    state.statistics["total_income"] += int(actual_tax)
    state.statistics["total_expenditure"] += total_out

    assert abs((state.treasury - treasury_before) - (actual_net - int(imp_share))) < 1, \
        f"财政恒等断裂：Δtreasury={state.treasury-treasury_before} actual_net={actual_net} imp={int(imp_share)}"

    inc_parts = f"工商{commerce_tax:.0f}+役钱{poll_tax:.0f}+二税折色{tax_color_total:.0f}+盐课{salt_coin:.0f}"
    if maritime_tax > 0:
        inc_parts += f"+市舶{maritime_tax:.0f}"
    if net < 0:
        log.append(f"[财政] 货币月入 {actual_tax:.0f}贯（{inc_parts}） 支 {total_out:.0f}贯 亏空 {abs(actual_net):.0f}贯（宜折变补之）")
    else:
        log.append(f"[财政] 货币月入 {actual_tax:.0f}贯（{inc_parts}） 支 {total_out:.0f}贯 结余 {actual_net:.0f}贯")
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

