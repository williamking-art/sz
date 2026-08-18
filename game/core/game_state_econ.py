# -*- coding: utf-8 -*-
"""宋祚 · GameState 经济计算族（mixin）

拆分自 core/game_state.py 的 calc_* / finance_readout / 物价与派生计算方法。
作为 GameStateEconMixin 被 GameState 继承，保持 state.calc_* 调用约定不变。
"""

from content.data import (
    ANNUAL_TAX_BASE, TAX_POLL_RATIO, MONTHLY_EXP_CIVIL_BASE,
    PAY_CASH_BASE, SUI_GONG_ANNUAL, COMMERCE_TAX_RATE_MIN,
    COMMERCE_TAX_RATE_MAX, COMMERCE_TAX_RATE_DEFAULT,
    SALT_PROFIT_PER_JIN, SALT_CAPACITY_BASE, SALT_POP_BASE,
    SALT_PRICE_FLOOR, SALT_PRICE_CEIL,
    WINE_COIN_BASE, IMPERIAL_SHARE, TAX_COLOR_RATE,
    MONEY_SUPPLY_START, PRICE_LEVEL_BASE, PRICE_LEVEL_MIN,
    PRICE_LEVEL_MAX, PRICE_VELOCITY, PER_CAPITA_MONTH_GRAIN,
    GRAIN_PRICE_MIN, GRAIN_PRICE_MAX,
    TAX_COEFF_MIN, TAX_COEFF_MAX,
    LAND_TAX_RATE_BENEFIT, CLERK_PER_OFFICIAL, CORRUPTION_MULT, BRIBE_FLOOR,
    GRANARY_CAP_SOFT,
    SOLDIER_GRAIN_PER_MONTH, SOLDIER_PAY_PER_MONTH,
    OFFICIAL_PAY_PER_MONTH, OFFICIAL_GRAIN_PER_MONTH,
    CLERK_PAY_PER_MONTH, CLERK_GRAIN_PER_MONTH,
    WINE_YIELD_PER_GRAIN, LAND_TAX_RATE_BASE,
    MATERIAL_PRICE_BASE, RESOURCE_DIMS,
    UNIT_TIER,
    MARITIME_TRADE_BASE,
)
from content.data import (
    desensitize_shortage, desensitize_price,
)
from content.data import (
    get_prestige_level,
)


def _clamp(value: float, lo: float, hi: float) -> float:
    """把数值钳制到 [lo, hi] 闭区间（供各粮价/物价计算复用）。"""
    return max(lo, min(hi, value))



class GameStateEconMixin:
    def calc_commerce(self) -> float:
        """国内工商经济总量（贯/年），作为国内工商税基与物价分母的同源口径。

        随科技 / 工业(艺术) 增长（市舶是独立税源，走 calc_maritime_trade，不再作为税基乘数）：
          - 科技 level 50→100：×1.0→×1.25；
          - 工业/艺术 mastery 85→100：×1.0→×1.0375；
          - 人口贡献小项：population // 100_000。
        开局（tech=50, art=85）≈ 3.5 亿贯——不再因"市舶未开"打对折。
        """
        base = 350_000_000
        tech = self.tech.get("level", 50)
        tech_mult = 1.0 + (tech - 50) / 200.0                      # 50→1.0, 100→1.25
        art = self.art_mastery
        art_mult = 1.0 + (art - 85) / 400.0                        # 85→1.0, 100→1.0375
        return base * tech_mult * art_mult + self.population // 100_000

    def calc_maritime_trade(self) -> float:
        """市舶海外贸易年总额（贯/年，独立税源）。

        市舶抽解是关税：税基为进出口贸易额，与国内工商税基并列，非放大关系。
        未开为 0；广开后随科技(造船/航海)/工业(商品供给)增长：
          - 科技 level 50→100：×1.0→×1.5；
          - 工业/艺术 mastery 85→100：×1.0→×1.0375。
        开局广开 ≈ 2000 万贯/年，占岁入 3~5%，贴史实占比。
        """
        maritime = getattr(self, "maritime", {}) or {}
        if not maritime.get("open"):
            return 0.0
        base = MARITIME_TRADE_BASE
        tech = self.tech.get("level", 50)
        tech_mult = 1.0 + (tech - 50) / 100.0                      # 50→1.0, 100→1.5
        art = self.art_mastery
        art_mult = 1.0 + (art - 85) / 400.0                        # 85→1.0, 100→1.0375
        return base * tech_mult * art_mult

    def _describe_tax_rate(self) -> str:
        """工商征率的定性描述（供 AI 认知层，不泄露精确税入数字）。"""
        rate = getattr(self, "commerce_tax_rate", COMMERCE_TAX_RATE_DEFAULT)
        if rate <= 0.10:
            return "工商薄征（不足一成）"
        if rate <= 0.20:
            return "工商常征（约一至两成）"
        if rate <= 0.30:
            return "工商重榷（约二至三成）"
        return "工商苛征（三成以上）"

    def _jiaozi_acceptance(self) -> float:
        """交子接受度 = 信用度(trust)，决定发行交子实际流通的比例（贬值部分退出流通）。"""
        return max(0.0, min(1.0, self.jiaozi.get("trust", 60) / 100.0))

    def _jiaozi_ceiling(self) -> int:
        """交子可发额度 = 准备金 × 准备金率（皇威高可放宽准备金约束）。"""
        prestige_ratio = 2.0 + (self.prestige - 50) / 50.0   # 皇威 50→2倍, 100→3倍, 0→1倍
        return int(self.jiaozi.get("reserve", 0) * max(1.0, prestige_ratio))

    def calc_price_level(self) -> float:
        """物价水平 = 货币有效供给 / 实物经济总量（钱/物之比）。"""
        # 货币有效供给 = Σ各 POP 财富（民间持钱）+ 国库/内帑（国家持钱）+ 有效交子 + 白银折钱。
        # 货币总量由 POP 经济自然派生（不再用 MONEY_SUPPLY_START 常量兜底），
        # 钱在 POP 间流转、税入国库、俸禄回民间，总量随经济涨落。
        pop_wealth = 0.0
        for p in self.prefectures.values():
            for pop in p.get("pops", {}).values():
                pop_wealth += float(pop.get("wealth", 0))
        copper_base = pop_wealth + max(0.0, self.treasury) + max(0.0, self.imperial_treasury)
        # 有效交子 = 发行 × 接受度（trust×皇威；超发→信用崩→接受度降→贬值部分退出流通）
        jiaozi_eff = self.jiaozi.get("issued", 0) * self._jiaozi_acceptance()
        maritime = getattr(self, "maritime", {}) or {}
        silver = maritime.get("silver_in", 0) * (1 if maritime.get("open") else 0) * 10000
        money = copper_base + jiaozi_eff + silver
        money *= (1 - self.coin.get("private_melt", 0.2))
        self.money_supply = max(0, money)

        # 实物经济总量 = 月粮产 × 粮价（石折贯）+ 工商产出（贯），避免石贯混加
        grain_prod = sum(p.get("grain", 0) for p in self.prefectures.values()) / 12.0
        real_output = grain_prod * self.grain_price + self.calc_commerce()

        pl = PRICE_LEVEL_BASE * (money * PRICE_VELOCITY / max(real_output, 1))
        return _clamp(pl, PRICE_LEVEL_MIN, PRICE_LEVEL_MAX)

    def calc_grain_price(self) -> float:
        """全国基准粮价（贯/石）：物价 × 季节 × 丰歉 × 灾害（按灾级放大）。"""
        price = self.price_level
        m = self.month
        if m in (4, 5, 6, 7):        # 青黄不接
            price *= 1.15
        elif m in (9, 10, 11):       # 秋收
            price *= 0.90
        if self.disaster_severity > 0:
            # 灾年粮价按灾级放大：轻灾1级×1.5、中灾3级×2.5、重灾5级×3.5
            # （史实灾年粮价可达丰年 3~5 倍）
            price *= 1.0 + self.disaster_severity * 0.5
        return _clamp(price, GRAIN_PRICE_MIN, GRAIN_PRICE_MAX)

    def calc_region_grain_price(self, name: str) -> float:
        """某州府区域粮价（贯/石）：基准粮价 × 本地供需比。

        市场供给 = 本地年成月均（grain/12）**含隐田产**：隐田不征田赋，但其产粮
        仍入市场供给（供人食用、平抑粮价）。隐田产按该路隐田/在册比例折算：
        供给 = grain × (1 + hidden_land/land) / 12。storage 是政府仓（非市场供给），
        不计入供需比；常平粜籴的粮流由 _settle_granary 显式作用于当月当地价。
        """
        p = self.prefectures.get(name)
        if not p:
            return self.grain_price
        # 隐户 2000 万口也吃粮（不落籍、不纳税，但真实消耗），按在籍比例摊入各路需求：
        # 隐户系数 = 总口/在籍 = (population + hidden_households×4) / population
        total_pop = self.population + self.land.get("hidden_households", 0) * 4
        factor = total_pop / max(self.population, 1)
        # 酒耗粮：酿酒消耗粮食（总酒课 × WINE_GRAIN_PER_GUAN），按该路在籍人口比例摊入当地需求
        from content.data import WINE_COIN_BASE, WINE_TAX_SHARE, WINE_GRAIN_PER_GUAN
        wine_grain_monthly = self.wine_tax / WINE_TAX_SHARE * WINE_GRAIN_PER_GUAN  # 随酒课（酒产量）动态
        wine_share = wine_grain_monthly * (p.get("population", 0) / max(self.population, 1))
        need = p.get("population", 0) * PER_CAPITA_MONTH_GRAIN * factor + wine_share   # 月需求（石，含隐户+酒耗）
        grain = float(p.get("grain", 0))                                # 在册年总产（石/年）
        # 市场供给 = 在册田产月均 + POP 存粮 2%/月释放（囤积真实入市、谷贱伤农）
        total_grain = grain
        from content.data import HOARD_SUPPLY_SQUEEZE
        hoard = float(p.get("pops", {}).get("士绅", {}).get("grain", 0))
        _pop_release = sum(pop.get("grain", 0) for pop in p.get("pops", {}).values()) * 0.02
        supply = max(total_grain / 12.0 + _pop_release - hoard * HOARD_SUPPLY_SQUEEZE, 0.01)  # 月供应（石）
        ratio = max(0.5, min(2.0, need / max(supply, 0.01)))
        price = self.grain_price * ratio
        return _clamp(price, GRAIN_PRICE_MIN, GRAIN_PRICE_MAX)

    # ================================================================
    # 财政读数（会计录）— 只读估算，与 _settle_finance 口径一致
    # ================================================================
    def finance_readout(self) -> dict:
        """本月财政预估读数（供会计录只读奏报台，GUI 与终端共用，避免两处口径漂移）。

        口径与 _settle_finance 一致：名义岁入（账面） vs 实际到库（按月结算）。
        差额即"隐漏与拖欠"——把漏出做成可见读数，呼应田赋隐漏。
        """
        from content.data import (
            ANNUAL_TAX_BASE, TAX_POLL_RATIO, MONTHLY_EXP_CIVIL_BASE,
            PAY_CASH_BASE, SUI_GONG_ANNUAL, COMMERCE_TAX_RATE_MIN,
            COMMERCE_TAX_RATE_MAX, COMMERCE_TAX_RATE_DEFAULT,
            SOLDIER_PAY_PER_MONTH, OFFICIAL_PAY_PER_MONTH, CLERK_PAY_PER_MONTH,
            SALT_PROFIT_PER_JIN, SALT_CAPACITY_BASE, SALT_POP_BASE,
            SALT_PRICE_FLOOR, SALT_PRICE_CEIL,
            WINE_COIN_BASE, IMPERIAL_SHARE, TAX_COLOR_RATE,
        )
        arrival = self.calc_arrival_rate()
        shortage = self.coin.get("shortage", 0.3)
        from content.data import TAX_COEFF_MIN, TAX_COEFF_MAX
        tax_coeff = TAX_COEFF_MIN + (TAX_COEFF_MAX - TAX_COEFF_MIN) * (1 - shortage)

        commerce = self.calc_commerce()
        rate = max(COMMERCE_TAX_RATE_MIN, min(COMMERCE_TAX_RATE_MAX,
                    getattr(self, "commerce_tax_rate", COMMERCE_TAX_RATE_DEFAULT)))
        commerce_tax = int((commerce / 12.0) * rate * arrival * tax_coeff)
        poll_tax = int((ANNUAL_TAX_BASE * TAX_POLL_RATIO / 12) * arrival * tax_coeff)
        maritime_trade = self.calc_maritime_trade()
        maritime_tax = int((maritime_trade / 12.0) *
                           (self.maritime.get("tariff", 0.10) if self.maritime.get("open") else 0.0) *
                           arrival * tax_coeff)

        # 名义岁入（账面，贴史实） = 年应征工商税 + 年役钱 + 年市舶抽解
        nominal_annual = int(commerce * rate) + int(ANNUAL_TAX_BASE * TAX_POLL_RATIO) \
            + int(maritime_trade * (self.maritime.get("tariff", 0.10) if self.maritime.get("open") else 0.0))

        # 支出侧：常支 + 折色俸禄 + 岁币
        pay = self.pay_system.get("cash_ratio", 0.5)
        cash_pay = int(PAY_CASH_BASE * pay)
        sui_gong = 0
        if self.external.get("辽", {}).get("attitude", 50) >= 60:
            sui_gong += int(SUI_GONG_ANNUAL * 0.6 / 12)
        if self.external.get("西夏", {}).get("attitude", 50) >= 60:
            sui_gong += int(SUI_GONG_ANNUAL * 0.4 / 12)
        wr = getattr(self, "waste_reform", None) or {}
        waste_savings = int(wr.get("savings", 0))
        if self.pay_system.get("mode") == "一体发钞":
            expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
            cash_out = 0
        else:
            expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
            cash_out = cash_pay

        # 经济全浮动重构读数（与 _settle_finance 同源）
        tax_color_total, _ = self.calc_monthly_tax_income(tax_coeff)
        salt_coin = self.calc_salt_coin(arrival)
        army_cash_total, _ = self.calc_army_cash()
        official_cash_total, _ = self.calc_official_cash()
        clerk_cash_total, _ = self.calc_clerk_cash()
        corruption_cash_ded, _ = self.calc_corruption_deduction()
        personnel_cash = int(army_cash_total + official_cash_total + clerk_cash_total)
        effective_cash_out = max(cash_out, personnel_cash)
        monthly_in = commerce_tax + poll_tax + maritime_tax + tax_color_total + salt_coin
        total_out = (expenditure + effective_cash_out
                     + int(corruption_cash_ded) + sui_gong)

        # ---- 后端权威定性字段（前端一律读这里，杜绝多口径重复与真实层泄漏）----
        from content.data import desensitize_shortage, desensitize_price
        # 钱荒定性：统一走 desensitize_shortage（与仓廪页/状态条同源）
        shortage_desc = desensitize_shortage(shortage)
        # 税率定性：统一走 _describe_tax_rate（与 AI 认知层同源）
        tax_rate_desc = self._describe_tax_rate()
        # 米价趋势：基于认知层（滞后奏报）而非真实层，避免上帝视角泄漏；
        # 认知层无历史时回退绝对定性 desensitize_price
        trend = "（初设）"
        hist = self.economy_knowledge.get("grain_price")
        cur = self.economy_knowledge.get("grain_price", self.grain_price)
        if hist and cur:
            if cur > hist * 1.02:
                trend = "米价连涨，民多艰食"
            elif cur < hist * 0.98:
                trend = "米价趋落，谷贱伤农"
            else:
                trend = "米价平，市侩安和"
        else:
            trend = desensitize_price(cur)

        return {
            "nominal_annual": nominal_annual,      # 名义岁入（贯/年，账面）
            "commerce": commerce_tax,              # 月工商税（实际到库）
            "poll": poll_tax,                      # 月役钱
            "maritime": maritime_tax,              # 月市舶抽解
            "tax_color": tax_color_total,          # 月二税折色（全进国库）
            "salt_coin": salt_coin,                # 月盐课（单列，不进二税）
            "monthly_in": monthly_in,              # 月实际到库合计
            "expenditure": expenditure,            # 月常支（派生）
            "army_cash": army_cash_total,          # 月军费（折色饷钱）
            "official_cash": official_cash_total,  # 月官俸折色
            "clerk_cash": clerk_cash_total,        # 月吏俸折色（实发）
            "corruption_ded": corruption_cash_ded, # 月吏俸缺口贪腐扣减（隐性，不进UI明细）
            "cash_out": cash_out,                  # 月折色俸禄（旧口径兜底）
            "sui_gong": sui_gong,                  # 月岁币
            "total_out": total_out,                # 月支出合计
            "net": monthly_in - total_out,         # 月结余（正=结余 负=亏空）
            "imperial_treasury": self.imperial_treasury,   # 内帑余额（甲口径：抽成+酒课）
            "wine_coin": WINE_COIN_BASE,           # 月酒课（进内帑）
            "granary": self.granary,               # 太仓净储（石）
            "granary_cap": self.granary_cap,       # 太仓仓容
            "rate": rate,                          # 当前征率
            "shortage_desc": shortage_desc,        # 钱荒定性（后端权威）
            "tax_rate_desc": tax_rate_desc,        # 税率定性（后端权威）
            "price_trend": trend,                  # 米价趋势（基于认知层）
        }

    # ================================================================
    # 到账率
    # ================================================================
    def calc_arrival_rate(self, audit_effort: float = 0.5, diversion: float = 0.35) -> float:
        """
        计算当月实际到账率
        audit_effort: 审计力度 (0-1)
        diversion: 截流比例 (0-1)
        """
        _, _, authority = get_prestige_level(self.prestige)
        rate = (
            self.arrival_rate_base
            + audit_effort * 0.30
            + authority * 0.15
            - diversion * 0.25
        )
        return max(0.05, min(0.95, rate))

    # ================================================================
    # 经济全浮动重构：派生函数族（纯函数风格，返回 (total, by_route) 或 float）
    # ================================================================
    def _clamp(self, v, lo, hi):
        return max(lo, min(hi, v))

    # ---- 二税折色（全进国库，钱）----
    # POP 化：二税折色 = 田赋本色（税粮）× 折色率 × 粮价（替代凭空 monthly_tax 锚）
    # 折色率 = TAX_COLOR_RATE（田赋中折银的比例），本色折银互为消长
    def calc_monthly_tax_income(self, tax_coeff: float = 1.0):
        _, grain_by = self.calc_monthly_grain()              # 田赋本色（税粮，运期才有）
        by_route = {}
        total = 0.0
        for name, g in grain_by.items():
            inc = g * TAX_COLOR_RATE * self.grain_price      # 税粮 × 折色率 × 粮价 = 折色钱
            by_route[name] = inc
            total += inc
        return total, by_route

    # ---- 太仓月入（田赋本色，三运期征收）----
    # 产粮集中在三运期（春3/夏6/秋9月，与漕运同节奏）：每期征收 1/3 年产，非运期不征本色。
    # grain_in_i = grain_i/3 × LAND_TAX_RATE_BENEFIT × arrival × 丰歉(yield) × 隐漏 × 水利科技
    def calc_monthly_grain(self):
        if getattr(self, "month", 1) not in (3, 6, 9):
            return 0.0, {name: 0.0 for name in self.prefectures}
        arrival = self.calc_arrival_rate()
        hyd = self.tech.get("hydraulics", 40) / 100.0       # 水利科技 0-1
        hidden = self.land.get("hidden_rate", 0.35)         # 隐漏率
        harvest = self.land.get("yield", 1.0)               # 亩产丰歉系数
        by_route = {}
        total = 0.0
        for name, p in self.prefectures.items():
            gy = float(p.get("grain", 0))                   # 年总产（石/年）= land × ROAD_YIELD
            grain_in = gy / 3.0 * LAND_TAX_RATE_BENEFIT * arrival * harvest * (1 - hidden) * (0.8 + 0.4 * hyd) * (1 - TAX_COLOR_RATE)
            by_route[name] = grain_in
            total += grain_in
        return total, by_route

    # ---- 军粮 / 军饷（逐实体按军籍分档；粮、饷两笔独立账）----
    # 旧模型：全军统一单价 × 全局质量系数 sf。现改为 Σ(unit.troops × 军籍系数)：
    #   粮 = Σ(unit.troops × UNIT_TIER[tier].grain_mult) × SOLDIER_GRAIN_PER_MONTH
    #   饷 = Σ(unit.troops × UNIT_TIER[tier].pay_mult)  × SOLDIER_PAY_PER_MONTH
    # grain_mult/pay_mult 为两个独立系数，分别作用于粮/饷，不共用。
    # 全局 sf 已废弃：质量影响并入 UNIT_TIER（equip_base/train_base/morale_base）。
    def calc_army_grain(self):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            g = 0.0
            for u in self.army_units:
                if u.station == name:
                    mult = UNIT_TIER.get(u.tier, UNIT_TIER["禁军"])["grain_mult"]
                    g += u.troops * mult * SOLDIER_GRAIN_PER_MONTH  # 每兵月耗(石)
            by_route[name] = g
            total += g
        return total, by_route

    def calc_army_cash(self):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            c = 0.0
            for u in self.army_units:
                if u.station == name:
                    mult = UNIT_TIER.get(u.tier, UNIT_TIER["禁军"])["pay_mult"]
                    c += u.troops * mult * SOLDIER_PAY_PER_MONTH
            by_route[name] = c
            total += c
        return total, by_route

    # ---- 官俸（Σ官×人均）----
    def calc_official_grain(self):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            g = float(p.get("officials", 0)) * OFFICIAL_GRAIN_PER_MONTH  # 官×每官月禄(石)
            by_route[name] = g
            total += g
        return total, by_route

    def calc_official_cash(self):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            c = float(p.get("officials", 0)) * OFFICIAL_PAY_PER_MONTH
            by_route[name] = c
            total += c
        return total, by_route

    # ---- 吏俸（基于 pay_ratio）----
    def calc_pay_ratio(self, route: str) -> float:
        p = self.prefectures.get(route, {})
        local = float(p.get("local_finance", 0))
        # 应得：官+吏的折色应发基准（官少吏多，吏按 CLERK_PAY_PER_MONTH）
        # 单位统一：officials/clerks 为真实人数，OFFICIAL/CLERK_PAY_PER_MONTH 为贯/人月，
        # due 直接为贯（不再 /10000，与 calc_clerk_gap 的 qdue 口径一致）。
        officials = float(p.get("officials", 0))
        clerks = float(p.get("clerks", 0))
        due = officials * OFFICIAL_PAY_PER_MONTH + clerks * CLERK_PAY_PER_MONTH
        if due <= 0:
            return 1.0
        # 加俸预算为全国池，按"官额缺口"占比摊还：缺口 = max(0, 应得due - 地方财力)，
        # 全国无缺口时退化为按官额（应得 due）占比。
        due_total = 0.0
        gap_total = 0.0
        for q in self.prefectures.values():
            qo = float(q.get("officials", 0))
            qc = float(q.get("clerks", 0))
            qdue = qo * OFFICIAL_PAY_PER_MONTH + qc * CLERK_PAY_PER_MONTH
            due_total += qdue
            gap_total += max(0.0, qdue - float(q.get("local_finance", 0)))
        my_gap = max(0.0, due - local)
        if gap_total > 1e-9:
            share = my_gap / gap_total
        elif due_total > 1e-9:
            share = due / due_total
        else:
            share = 0.0
        financed = local + self.payraise_budget * share
        return self._clamp(financed / due, 0.0, 1.0)

    def calc_clerk_grain(self):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            pr = self.calc_pay_ratio(name)
            g = float(p.get("clerks", 0)) * CLERK_GRAIN_PER_MONTH * pr  # 吏×每吏月禄(石)
            by_route[name] = g
            total += g
        return total, by_route

    def calc_clerk_cash(self):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            pr = self.calc_pay_ratio(name)
            c = float(p.get("clerks", 0)) * CLERK_PAY_PER_MONTH * pr
            by_route[name] = c
            total += c
        return total, by_route

    def calc_clerk_gap(self):
        """吏俸缺口（折色，未补发部分）Σ gap_i = 应得_i × (1 - pay_ratio_i)。"""
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            pr = self.calc_pay_ratio(name)
            clerks = float(p.get("clerks", 0))
            officials = float(p.get("officials", 0))
            due = officials * OFFICIAL_PAY_PER_MONTH + clerks * CLERK_PAY_PER_MONTH
            gap = due * (1 - pr)
            by_route[name] = gap
            total += gap
        return total, by_route

    # ---- 贪腐扣减（折色扣中央月入 + 本色放大太仓损耗）----
    def calc_corruption_deduction(self):
        gap_total, _ = self.calc_clerk_gap()
        # 折色扣减 = gap × CORRUPTION_MULT × (1 - oversight)，下限 BRIBE_FLOOR 顽固
        cash_ded = gap_total * CORRUPTION_MULT * (1 - self.oversight)
        cash_ded = cash_ded * (1 - BRIBE_FLOOR) + gap_total * BRIBE_FLOOR * 0.3
        # 本色损耗（太仓）：贪腐放大雀鼠耗，量纲取 cash_ded 金额折算粮（约 1:1 石等价）
        grain_loss = gap_total * CORRUPTION_MULT * 0.5 * (1 - self.oversight)
        return cash_ded, grain_loss

    # ---- 盐课（活基准：盐产区产能 × 动态盐价 × 食盐人口）----
    def calc_salt_coin(self, arrival: float = 1.0) -> float:
        """月盐课（贯），随盐产区产能、食盐人口、到库率浮动。

        盐课 = Σ各路盐产量(斤/年) × SALT_PROFIT_PER_JIN × price_factor × arrival × (总人口/SALT_POP_BASE)
          - 盐产区产能：各路七维物资初值 yields["salt"] 之和（工程/市舶可改 yields 或 resources 而变）
          - price_factor：产能/基准产能比越紧俏价越高，夹在 [SALT_PRICE_FLOOR, SALT_PRICE_CEIL]
          - 总人口缩放：食盐人口增减直接线性反映到盐课（开局缩放=1）
          - arrival：到库率（灾荒/治理低则折损）
        不再使用写死的月额常量。
        """
        salt_capacity = 0.0
        total_pop = 0.0
        for p in self.prefectures.values():
            salt_capacity += float(p.get("yields", {}).get("salt", 0))
            total_pop += float(p.get("population", 0))
        adequacy = salt_capacity / SALT_CAPACITY_BASE if SALT_CAPACITY_BASE > 0 else 1.0
        price_factor = 1.0 + (min(adequacy, 2.0) - 1.0) * 0.3
        price_factor = max(SALT_PRICE_FLOOR, min(SALT_PRICE_CEIL, price_factor))
        pop_scale = total_pop / SALT_POP_BASE if SALT_POP_BASE > 0 else 1.0
        return salt_capacity / 12.0 * SALT_PROFIT_PER_JIN * price_factor * arrival * pop_scale

    # ---- 内帑反馈（重构口径）----
    def calc_imperial_treasury(self, net: float = 0.0):
        """结余为正时抽成；另计酒课入内帑。返回 (抽成额, 酒课额)。"""
        share = max(0.0, net) * IMPERIAL_SHARE
        wine = self.wine_tax * (1.0 + 0.01 * (self.tech.get("level", 50) - 50))
        return share, wine

    # ---- 防区派生视图（各路 garrisons 聚合）----
