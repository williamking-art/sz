# -*- coding: utf-8 -*-
"""宋祚 · GameState 经济计算族（mixin）

拆分自 core/game_state.py 的 calc_* / finance_readout / 物价与派生计算方法。
作为 GameStateEconMixin 被 GameState 继承，保持 state.calc_* 调用约定不变。
"""

from content.data import (
    ANNUAL_TAX_BASE, TAX_POLL_RATIO, MONTHLY_EXP_CIVIL_BASE,
    # 到账率公式常量（2026-09-19 质量全检回收：此前 `calc_arrival_rate` 内硬编码同值）
    ARRIVAL_AUDIT_WEIGHT, ARRIVAL_AUTHORITY_WEIGHT, ARRIVAL_DIVERSION_WEIGHT,
    ARRIVAL_MIN, ARRIVAL_MAX,
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
    UNIT_TIER, branch_std,
    MARITIME_TRADE_BASE,
)
from content.data import (
    GRAIN_PRICE_MONTHLY_CAP, PRICE_LEVEL_MONTHLY_CAP,
    TRANSPORT_PRICE_WEIGHT, STOCK_PRICE_RELIEF_MAX,
    MONEY_SUPPLY_PRICE_WEIGHT,
)
from content.data import (
    desensitize_shortage, desensitize_price,
)
from content.data import (
    get_prestige_level,
)


# 审查 P3 修复：_clamp 统一由 content.data.clamp 提供（单一权威源，原此处与
# game_state.py、本文件 mixin 方法共三份重复）
from content.data import clamp as _clamp  # noqa: E402

# 官制 × POP 的单一权威源（官额/吏额/子池付款权数一律经此读取，杜绝 officials 双账复活）
from core import officialdom as _officialdom  # noqa: E402



# ============================================================
# 整改①-2 / ①-3：价格月度上限 + 生产/工程声明契约
# ============================================================
def cap_monthly_price(prev: float, target: float, cap: float) -> float:
    """把 target 钳制到相对 prev 的单月变动上限内（整改①-3「价格有月度上限」）。

    纯函数（不碰状态），供 `_settle_land_local` / `_settle_econ_prices`
    以及测试共用；prev<=0（缺省/损坏存档）时不设限。
    """
    try:
        prev = float(prev)
        target = float(target)
        cap = float(cap)
    except (TypeError, ValueError) as exc:  # 不得静默成功
        raise ValueError(f"cap_monthly_price 需要数值（got {prev!r},{target!r},{cap!r}）") from exc
    if prev <= 0 or cap < 0:
        return target
    return max(prev * (1.0 - cap), min(prev * (1.0 + cap), target))


# 生产/工程项目必须声明的九项（整改①-2）：
#   原料、钱粮、工匠工时、产出、施工期、维护、折旧、路线、POP受益者。
# 字段可用别名（兼容现有 cost_material/cost_coin/speed 写法）；
# 缺声明不静默、不拒绝，但会转为可诊断的缺口清单（见 project_declaration_gaps）。
PROJECT_DECLARATION_FIELDS = (
    ("materials", ("cost_material", "materials"), "原料"),
    ("money", ("cost_coin", "money"), "钱粮"),
    ("craft_hours", ("craft_hours", "labor_hours", "工匠工时"), "工匠工时"),
    ("output", ("output", "outputs"), "产出"),
    ("duration", ("duration", "months", "speed", "工期"), "施工期"),
    ("upkeep", ("upkeep", "upkeep_per_month", "维护"), "维护"),
    ("depreciation", ("depreciation", "depreciation_rate", "折旧"), "折旧"),
    ("route", ("route", "routes", "路线"), "路线"),
    ("beneficiaries", ("beneficiaries", "pop_beneficiaries", "受益者"), "POP受益者"),
)


def project_declaration_gaps(proj) -> list:
    """返回工程声明的**缺失字段**（中文名列表）。非 dict 视为全缺。"""
    if not isinstance(proj, dict):
        return [label for _, _, label in PROJECT_DECLARATION_FIELDS]
    gaps = []
    for _canon, aliases, label in PROJECT_DECLARATION_FIELDS:
        # 字段在与否为准：显式声明 0（如「无需钱粮」）也算已声明；
        # 仅空值/None/空容器视为未声明。
        if not any(a in proj and proj.get(a) not in (None, "", {}, []) for a in aliases):
            gaps.append(label)
    return gaps


def project_supply_ratio(proj, resources, treasury) -> float:
    """工程当月**供给满足率** ∈ [0,1]：材料/钱的**最短板**。

    整改①-2「材料不足逐步降效」：调用方据此按比例推进进度并同比例消耗，
    而非“不足则格式化停滞”。纯函数，不写状态。
    """
    ratios = []
    if isinstance(proj, dict):
        for _dim, need in (proj.get("cost_material") or {}).items():
            need = float(need or 0)
            if need <= 0:
                continue
            have = float((resources.get(_dim) or {}).get("stock", 0) or 0)
            ratios.append(max(0.0, min(1.0, have / need)))
        coin_need = float(proj.get("cost_coin", 0) or 0)
        if coin_need > 0:
            ratios.append(max(0.0, min(1.0, float(treasury or 0) / coin_need)))
    return min(ratios) if ratios else 1.0


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

    def _real_output_monthly(self) -> float:
        """月度实物经济总量（贯）= 月粮产 × 粮价 + 工商产出。

        单一公式源：calc_price_level（全国物价指数）与路线粮价的货币项共用，
        避免“同一比率两处各算一遍”的口径漂移。
        """
        grain_prod = sum(p.get("grain", 0) for p in self.prefectures.values()) / 12.0
        return grain_prod * self.grain_price + self.calc_commerce()

    def calc_price_level(self) -> float:
        """物价水平 = 货币有效供给 / 实物经济总量（钱/物之比）。"""
        # 货币有效供给 = Σ各 POP 财富（民间持钱）+ 国库/内帑（国家持钱）+ 有效交子 + 白银折钱。
        # 货币总量由 POP 经济自然派生（不再用 MONEY_SUPPLY_START 常量兜底），
        # 钱在 POP 间流转、税入国库、俸禄回民间，总量随经济涨落。
        # ---- 阶段 B-3 改造：改用货币口径 M1（见 core/money.py 与 货币口径规范 §三）----
        # 三处修正：
        #  ① **整体 private_melt 缩放 → 只作用铜钱**：原实现把
        #     `(pop_wealth + 国库 + 内帑 + 交子 + 白银) × (1 − private_melt)` 一并缩水 10%，
        #     而 `private_melt` 按定义是"铜钱私铸/外流比例"，作用于国库/内帑/交子/白银
        #     属记账错误，且会掩盖其他科目的真实变化。
        #  ② **白银流量当存量 → 退出物价口径**：原式用 `maritime.silver_in`（万两/**年**，
        #     流量）直接 ×10000 当作白银存量。现白银走 `state.silver_stock` 存量，
        #     且按规范 §三 只计入 M3、不驱动物价（待其实际分发入 POP wealth 后自然进入 M1）。
        #  ③ **国库封桩分层**：物价 = M1(working)，即国库/内帑只按"周转金"计入
        #     （3×月常费；内帑 1/3），超出部分视为封桩（M2 沉淀），
        #     使"囤钱不流通的玩家不会凭空制造通胀"（规范 §12.2、§13.3）。
        from core.money import (m1 as _m1_working, pop_money as _pop_money,
                                estate_wealth as _estate_wealth,
                                copper_share as _copper_share)
        _cs = _copper_share(self)
        _melt = float(self.coin.get("private_melt", 0.2) or 0)
        _copper_amt = (_pop_money(self) + _estate_wealth(self)) * _cs
        # 白银**存量**计入货币（规范 M-D6：白银由流量改存量，仍影响物价）。
        # 修复前是把 `maritime.silver_in`（万两/年，流量）直接 ×10000 当存量用；
        # 现用逐月累积的真实存量 `state.silver_stock`（见 _settle_extensions）。
        _silver = float(getattr(self, "silver_stock", 0) or 0)
        money = _m1_working(self, working_only=True) - _copper_amt * _melt + _silver
        money = max(0.0, money)
        self.money_supply = money

        # 实物经济总量（单一公式 _real_output_monthly）
        real_output = self._real_output_monthly()

        pl = PRICE_LEVEL_BASE * (money * PRICE_VELOCITY / max(real_output, 1))
        # 金融推演价格系数（通胀/通缩 ±5%，clamp [0.5,3.0]；月度重置不落档——运行时态）
        _pm = getattr(self, "_price_mult", 1.0)
        pl *= _pm
        # T9 物价封顶 2.8（防触 3.0 恶性通胀）：稳定器（常平/换界/熔化）在前端抑价，
        # 此为上界硬钳（与 PRICE_LEVEL_MIN 对称）；全程 ∈ [0.8, 2.8]（断言口径）
        from content.data import PRICE_FLOOR_HARD, PRICE_CEIL_HARD
        return _clamp(pl, PRICE_FLOOR_HARD, PRICE_CEIL_HARD)

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
        """某州府区域粮价（贯/石）：由本地供需 + 库存 + 运输 + 货币有效供给派生。

        整改①-3（路线物价）：全国 PRICE_LEVEL 只是**加权读数**，路线价才是权威
        派生入口（`_settle_econ_prices` 每月调用）。因子：
          - 供需：需求 = 在籍口 × 人均月耗 × 隐户系数 + 酒耗；供给 = 田产月均 +
            POP 存粮释放 − 士绅囤积挤压；
          - 库存：本路太仓（按人口摊）+常平存粮充足时抑价；
          - 运输：漕运阻塞越高，外粮难入 → 加价；
          - 货币有效供给：M1/实物产出偏离基准 → 加价。
        """
        p = self.prefectures.get(name)
        if not p:
            return self.grain_price
        # 隐户 2000 万口也吃粮（不落籍、不纳税，但真实消耗），按在籍比例摊入各路需求
        total_pop = self.population + self.land.get("hidden_households", 0) * 4
        factor = total_pop / max(self.population, 1)
        # 酒耗粮：酿酒消耗粮食（总酒课 × WINE_GRAIN_PER_GUAN），按该路在籍人口比例摊入当地需求
        from content.data import WINE_TAX_SHARE, WINE_GRAIN_PER_GUAN
        wine_grain_monthly = self.wine_tax / WINE_TAX_SHARE * WINE_GRAIN_PER_GUAN
        wine_share = wine_grain_monthly * (p.get("population", 0) / max(self.population, 1))
        need = p.get("population", 0) * PER_CAPITA_MONTH_GRAIN * factor + wine_share   # 月需求（石）
        grain = float(p.get("grain", 0))
        total_grain = grain
        from content.data import HOARD_SUPPLY_SQUEEZE
        hoard = float(p.get("pops", {}).get("士绅", {}).get("grain", 0))
        _pop_release = sum(pop.get("grain", 0) for pop in p.get("pops", {}).values()) * 0.02
        supply = max(total_grain / 12.0 + _pop_release - hoard * HOARD_SUPPLY_SQUEEZE, 0.01)
        ratio = max(0.5, min(2.0, need / max(supply, 0.01)))
        price = self.grain_price * ratio
        # 库存抑价：本路太仓（按人口摊）+常平存粮相对月需求越充足，价越低
        _gran_share = float(getattr(self, "granary", 0) or 0) * (
            p.get("population", 0) / max(self.population, 1))
        stock = (float(p.get("changping_stock", 0) or 0)
                 + float(p.get("storage", 0) or 0) + _gran_share)
        _months = stock / max(need, 1.0)
        relief = min(STOCK_PRICE_RELIEF_MAX,
                     max(0.0, (_months - 1.0) / 11.0) * STOCK_PRICE_RELIEF_MAX)
        price *= (1.0 - relief)
        # 运输加价：漕运阻塞 0~100 → 最多 +加权
        _block = max(0.0, min(1.0, float(getattr(self, "canal_block", 0) or 0) / 100.0))
        price *= 1.0 + _block * TRANSPORT_PRICE_WEIGHT
        # 货币有效供给：M1 与实物产出之比偏离基准 → 加/减价
        _money = float(getattr(self, "money_supply", 0) or 0)
        _real = self._real_output_monthly()
        if _real > 0 and _money > 0:
            _dev = max(-0.5, min(0.5, (_money * PRICE_VELOCITY / _real) - PRICE_LEVEL_BASE))
            price *= 1.0 + _dev * MONEY_SUPPLY_PRICE_WEIGHT
        return _clamp(price, GRAIN_PRICE_MIN, GRAIN_PRICE_MAX)

    def national_grain_price_weighted(self) -> float:
        """全国粮价**加权读数**：按各路在籍人口加权平均路线粮价。

        整改①-3：路线价由供需/库存/运输/货币派生，全国值只是读数（不反向驱动路线价）。
        仅供面板/审计读取，不作为任何算式的输入（避免循环）。
        """
        _tot = sum(p.get("population", 0) for p in self.prefectures.values())
        if _tot <= 0:
            return self.grain_price
        _w = sum(float(p.get("grain_price", self.grain_price) or self.grain_price)
                 * p.get("population", 0) for p in self.prefectures.values())
        return _w / _tot

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
        # 役钱（徭役代役钱）：与 _settle_finance 同源——只从农 POP 征（坊郭户/官户/兵免役）
        _farm_pop = sum(p["pops"]["农"]["size"] for p in self.prefectures.values())
        poll_tax = int((_farm_pop * TAX_POLL_RATIO / 12) * arrival * tax_coeff)
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
        _mult = getattr(self, "_sui_gong_mult", None) or {}
        if self.external.get("辽", {}).get("attitude", 50) >= 60:
            sui_gong += int(SUI_GONG_ANNUAL * 0.6 / 12 * _mult.get("辽", 1.0))   # 岁币倍率（外交协议）
        if self.external.get("西夏", {}).get("attitude", 50) >= 60:
            sui_gong += int(SUI_GONG_ANNUAL * 0.4 / 12 * _mult.get("西夏", 1.0))
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
        # 与 _settle_finance 对齐：一体发钞时 effective_cash_out=0；否则取实际发放 personnel_cash
        if self.pay_system.get("mode") == "一体发钞":
            effective_cash_out = 0
        else:
            effective_cash_out = personnel_cash
        # 加俸预算消耗（与 _settle_finance 同源：min(payraise_budget, 吏俸缺口+10000)）
        clerk_gap_total, _ = self.calc_clerk_gap()
        payraise_used = min(self.payraise_budget, int(clerk_gap_total) + 10_000)
        monthly_in = commerce_tax + poll_tax + maritime_tax + tax_color_total + salt_coin
        total_out = (expenditure + effective_cash_out
                     + int(corruption_cash_ded) + payraise_used + sui_gong)

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
            + audit_effort * ARRIVAL_AUDIT_WEIGHT
            + authority * ARRIVAL_AUTHORITY_WEIGHT
            - diversion * ARRIVAL_DIVERSION_WEIGHT
        )
        return max(ARRIVAL_MIN, min(ARRIVAL_MAX, rate))

    # ================================================================
    # 经济全浮动重构：派生函数族（纯函数风格，返回 (total, by_route) 或 float）
    # ================================================================
    # ---- 二税折色（全进国库，钱）----
    # POP 化：二税折色 = 田赋本色（税粮）× 折色率 × 粮价（替代凭空 monthly_tax 锚）
    # 折色率 = TAX_COLOR_RATE（田赋中折银的比例），本色折银互为消长
    # 平衡修复（蔡权衡）：折色**按月 1/12 摊**（每月都收钱，去财政季节性摆动；
    # 年折色总额 = 年税基×折色率×粮价，与本色同税基——年均总量不变，平滑不造假账；本色仍运期不动）
    def calc_monthly_tax_income(self, tax_coeff: float = 1.0):
        arrival = self.calc_arrival_rate()
        hyd = self.tech.get("hydraulics", 40) / 100.0
        hidden = self.land.get("hidden_rate", 0.35)
        harvest = self.land.get("yield", 1.0)
        by_route = {}
        total = 0.0
        for name, p in self.prefectures.items():
            gy = float(p.get("grain", 0))                   # 年总产（石/年）
            grain_annual = gy * LAND_TAX_RATE_BENEFIT * arrival * harvest * (1 - hidden) * (0.8 + 0.4 * hyd)
            inc = grain_annual * TAX_COLOR_RATE * self.grain_price / 12.0   # 年折色总额按月 1/12
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
    # 每路禁/厢/乡各一支（用户定稿）：branches 键 = 兵种名，军籍由 u.tier 定；
    # 粮/饷 = Σ_unit Σ_branches(人数 × branch_std(u.tier, 兵种).grain/pay)（BRANCH_BASE × ARMY_RATE 按率）。
    # for_issue=True（太仓实发口径）：乡兵军队粮饷缺口自备（史实农隙自备，不造钱/造粮），仅发禁军+厢军。
    # 兵 POP 口粮 1.5 石/月为军籍无关消费（GRAIN_CONSUME_PER_CAPITA），与军粮实发口径分离。
    def calc_army_grain(self, for_issue: bool = False):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            g = 0.0
            for u in self.army_units:
                if u.station != name:
                    continue
                if for_issue and u.tier == "乡兵":
                    continue   # 乡兵军粮自备，太仓不实发
                for b, n in u.branches.items():
                    g += n * branch_std(u.tier, b)["grain"]   # 石/人/月（兵种标准 × 军籍系数）
            by_route[name] = g
            total += g
        return total, by_route

    def calc_army_cash(self, for_issue: bool = False):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            c = 0.0
            for u in self.army_units:
                if u.station != name:
                    continue
                if for_issue and u.tier == "乡兵":
                    continue   # 乡兵无饷（自备）
                for b, n in u.branches.items():
                    c += n * branch_std(u.tier, b)["pay"]      # 贯/人/月（兵种标准 × 军籍系数）
            by_route[name] = c
            total += c
        return total, by_route

    # ---- 税基 / 免役口径（阶段 C-4，§13.6）----
    def tax_base_summary(self) -> dict:
        """税基与免役派生视图（**只读**，口径唯一权威源）。

        「冗官 → 财政恶化」最史实的一条链是 **免役 → 税基萎缩**：
        役钱只从 `农` POP 征；`士绅`（形势户）、`官僚`（官户）、`兵` 免役。
        冗官膨胀（科举/恩荫/宗室入官）把人口从 `农` 抽走 → 纳税人口下降；
        官户另行纳**助役钱**（俸禄总额 5%），但远不足以抵消其俸禄本身。

        返回：纳税人口、免役人口与占比、役钱与助役钱实收、冗官数。
        """
        from core import officialdom as _od

        pops = {}
        for p in self.prefectures.values():
            for k, v in (p.get("pops") or {}).items():
                pops[k] = pops.get(k, 0) + int(v.get("size", 0) or 0)
        taxable = pops.get("农", 0)
        exempt = pops.get("士绅", 0) + pops.get("官僚", 0) + pops.get("兵", 0)
        total = sum(pops.values()) or 1
        _od.ensure_quota(self)      # 定员是惰性初始化的**岗位**存量（幂等），其余全为派生
        t = _od.totals(self)
        return {
            "taxable_pop": taxable,
            "exempt_pop": exempt,
            "exempt_share": round(exempt / total, 6),
            "poll_tax": int((self.tax_breakdown or {}).get("poll", 0)),
            "official_service_tax": int((self.tax_breakdown or {}).get("official_service", 0)),
            "taxable_share": round(taxable / total, 6),
            "officials": t["officials"],
            "redundant_officials": t["redundant"],
            "awaiting_posts": t["waiting"],
        }

    # ---- 官俸（Σ官×人均；官额与子池计价一律取自 POP，见 core/officialdom.py）----
    # POP 挂载律：`p["officials"]` 只是派生镜像，**不得**作为俸禄依据（否则双账复活：
    # 科举让官僚 POP 涨、镜像不涨 → "养更多官、一分钱不多花"，30 月实证 +23.1% vs +0.0%）。
    def calc_official_grain(self):
        total = 0.0
        by_route = {}
        _rank = float(getattr(self, "official_rank_index", 1.0) or 1.0)   # 磨勘：品阶上浮
        for name, p in self.prefectures.items():
            # 在岗全禄、待阙半禄、祠禄折禄（§13.6）× 磨勘指数
            g = _officialdom.route_pay_units(p) * OFFICIAL_GRAIN_PER_MONTH * _rank
            by_route[name] = g
            total += g
        return total, by_route

    def calc_official_cash(self):
        total = 0.0
        by_route = {}
        _rank = float(getattr(self, "official_rank_index", 1.0) or 1.0)   # 磨勘：品阶上浮
        for name, p in self.prefectures.items():
            c = _officialdom.route_pay_units(p) * OFFICIAL_PAY_PER_MONTH * _rank
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
        officials = float(_officialdom.route_pay_units(p))
        clerks = float(_officialdom.route_clerks(p))
        due = officials * OFFICIAL_PAY_PER_MONTH + clerks * CLERK_PAY_PER_MONTH
        if due <= 0:
            return 1.0
        # 加俸预算为全国池，按"官额缺口"占比摊还：缺口 = max(0, 应得due - 地方财力)，
        # 全国无缺口时退化为按官额（应得 due）占比。
        due_total = 0.0
        gap_total = 0.0
        for q in self.prefectures.values():
            qo = float(_officialdom.route_pay_units(q))
            qc = float(_officialdom.route_clerks(q))
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
        return _clamp(financed / due, 0.0, 1.0)   # 审查 P3：改用单一权威源 clamp

    def calc_clerk_grain(self):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            pr = self.calc_pay_ratio(name)
            g = float(_officialdom.route_clerks(p)) * CLERK_GRAIN_PER_MONTH * pr  # 吏×每吏月禄(石)
            by_route[name] = g
            total += g
        return total, by_route

    def calc_clerk_cash(self):
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            pr = self.calc_pay_ratio(name)
            c = float(_officialdom.route_clerks(p)) * CLERK_PAY_PER_MONTH * pr
            by_route[name] = c
            total += c
        return total, by_route

    def calc_clerk_gap(self):
        """吏俸缺口（折色，未补发部分）Σ gap_i = 应得_i × (1 - pay_ratio_i)。"""
        total = 0.0
        by_route = {}
        for name, p in self.prefectures.items():
            pr = self.calc_pay_ratio(name)
            clerks = float(_officialdom.route_clerks(p))
            officials = float(_officialdom.route_pay_units(p))
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
