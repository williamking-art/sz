# -*- coding: utf-8 -*-
"""宋祚 · GameState 经济计算族（mixin）

拆分自 core/game_state.py 的 calc_* / finance_readout / 物价与派生计算方法。
作为 GameStateEconMixin 被 GameState 继承，保持 state.calc_* 调用约定不变。
"""

from content.data import (
    ANNUAL_TAX_BASE, TAX_POLL_RATIO, POLL_TAX_NOMINAL_SHARE, MONTHLY_EXP_CIVIL_BASE,
    # 到账率公式常量（2026-09-19 质量全检回收：此前 `calc_arrival_rate` 内硬编码同值）
    ARRIVAL_AUDIT_WEIGHT, ARRIVAL_AUTHORITY_WEIGHT, ARRIVAL_DIVERSION_WEIGHT,
    ARRIVAL_MIN, ARRIVAL_MAX,
    # P1 双层税基·四率（V1.3 终稿 §3；Q3 甲：先作用于田赋折色）
    FIN_COLLECTION_BASE, FIN_COLLECTION_GOVERN_W, FIN_COLLECTION_MIN, FIN_COLLECTION_MAX,
    FIN_TRANSFER_RATE, FIN_TRANSFER_CAP, FIN_KEEP_BASE, FIN_KEEP_GOVERN_ANCHOR,
    FIN_KEEP_GOVERN_W, FIN_KEEP_MIN, FIN_KEEP_MAX, FIN_KEEP_CAP, FIN_DIV_RATE,
    # P2 账面（V1.3 终稿 §5）：损耗科目与信息差闸门
    FIN_LOSS_NORM, FIN_LOSS_ALERT_MULT, FIN_ANOMALY_OVERSIGHT_LINE,
    # M34-① 地方支出 V2（裁决 2026-10-11）：地方经费保障倍数（玩家接口）
    LOCAL_EXP_MULT_BASE, LOCAL_EXP_MULT_MIN, LOCAL_EXP_MULT_MAX,
    PAY_CASH_BASE, SUI_GONG_ANNUAL, COMMERCE_TAX_RATE_MIN,
    COMMERCE_TAX_RATE_MAX, COMMERCE_TAX_RATE_DEFAULT,
    SALT_PROFIT_PER_JIN, SALT_CAPACITY_BASE, SALT_POP_BASE,
    SALT_PRICE_FLOOR, SALT_PRICE_CEIL,
    WINE_COIN_BASE, IMPERIAL_SHARE, TAX_COLOR_RATE,
    PRICE_LEVEL_BASE, PRICE_VELOCITY, PER_CAPITA_MONTH_GRAIN,
    GRAIN_PRICE_MIN, GRAIN_PRICE_MAX,
    TAX_COEFF_MIN, TAX_COEFF_MAX,
    LAND_TAX_RATE_BENEFIT, CORRUPTION_MULT, BRIBE_FLOOR,
    OFFICIAL_PAY_PER_MONTH, OFFICIAL_GRAIN_PER_MONTH,
    CLERK_PAY_PER_MONTH, CLERK_GRAIN_PER_MONTH,
    branch_std,
    MARITIME_TRADE_BASE,
)
from content.data import (
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

# P3 发现系统（V1.3 §7）：四级阶梯读数（异常→怀疑→证据→真相；只读组装）
from core.audit_case import discovery_readout as _discovery_readout  # noqa: E402

# 官制 × POP 的单一权威源（官额/吏额/子池付款权数一律经此读取，杜绝 officials 双账复活）
from core.domains.administration import officialdom as _officialdom  # noqa: E402



# ============================================================
# 整改①-2 / ①-3：价格月度上限 + 生产/工程声明契约
# ============================================================
def normalize_finance_split(transfer: float, keep: float, div: float) -> tuple:
    """财政分流三率归一（**全库唯一单点**；V1.3 终稿 §3.4）。

    输入三率意图值 → 输出保证 `t + k + d ≡ 1` 的三率：
    - 修正**自最低保护等级起**：① diversion（残差吸收）→ ② keep → ③ transfer
      （最后才动 transfer：中央稳定是系统核心）；
    - 钳制：`transfer ≤ FIN_TRANSFER_CAP`、`keep ≤ FIN_KEEP_CAP`、各率 ≥ 0。
    纯函数（不读 state）；结算侧唯一出口为 `GameStateEconMixin.finance_split`。
    """
    t = _clamp(float(transfer), 0.0, FIN_TRANSFER_CAP)
    k = _clamp(float(keep), 0.0, FIN_KEEP_CAP)
    d = max(0.0, float(div))
    delta = 1.0 - (t + k + d)
    if abs(delta) <= 1e-12:
        return t, k, d
    # ① diversion 先吸收（残差）
    nd = max(0.0, d + delta)
    delta -= (nd - d)
    d = nd
    if abs(delta) <= 1e-12:
        return t, k, d
    # ② keep 其次
    nk = _clamp(k + delta, 0.0, FIN_KEEP_CAP)
    delta -= (nk - k)
    k = nk
    if abs(delta) <= 1e-12:
        return t, k, d
    # ③ transfer 最后（极端输入兜底；正常值域不可达）
    t = _clamp(t + delta, 0.0, FIN_TRANSFER_CAP)
    return t, k, d


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

        🔴 **实现状态（2026-10-05 据实更正）**：`state.maritime["open"]` **当前恒为 False**
        —— 全库**无任何代码会将其置 True** ⇒ **本函数恒返回 0，市舶从不结算**。

        ⚠️ 原 docstring 写「**开局广开 ≈ 2000 万贯/年，占岁入 3~5%，贴史实占比**」——
        那是**设计意图**，**与当前实现不符**，已更正（承 §6.1：文档与代码不符须顺手改）。

        **史实**：宋代市舶极发达（广州/泉州/明州/杭州/密州），市舶收入为财政重要来源。
        ⇒ 本机制**应在开局即生效**；当前「永不结算」属**实现缺陷**，非史实认定。
        详见 `_dev_tools/game-docs/specs/外贸缺失是实现缺陷非史实认定.md`。
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
        from core.foundation.ledger.money import (m1 as _m1_working, pop_money as _pop_money,
                                copper_share as _copper_share)
        _cs = _copper_share(self)
        _melt = float(self.coin.get("private_melt", 0.2) or 0)
        # 家产的钱已在 pop_money 内（士绅 `estate` 子池），不得再叠加 estate_wealth（双计）
        _copper_amt = _pop_money(self) * _cs
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
          - 供需：需求 = (本路在籍口 + 本路农.hidden) × 人均月耗 + 全国酒耗按在籍口分摊；
            供给 = 田产月均 + POP 存粮释放 − 士绅囤积挤压；
          - 库存：本路太仓（按在籍口份额分摊）+ 常平存粮充足时抑价；本地隐户只增本路需求，不缩放中央粮份额；
          - 运输：漕运阻塞越高，外粮难入 → 加价；
          - 货币有效供给：M1/实物产出偏离基准 → 加价。
        """
        p = self.prefectures.get(name)
        if not p:
            return self.grain_price
        # 隐户也吃粮（不落籍、不纳税），直接计入其所在路的本地需求。
        # 旧式全国隐户/全国在籍比例会把甲路隐户增长扩散到乙路价格，违反地区供需粒度；
        # 真值已有 prefecture POP `农.hidden`，无需全国估比例。
        route_pop = max(0.0, float(p.get("population", 0) or 0))
        route_hidden = max(0, int((((p.get("pops") or {}).get("农")) or {}).get("hidden", 0) or 0))
        route_demand_people = route_pop + route_hidden
        # 全国酒耗是全国总量，按本路在籍人口份额分配；仅作全国流量分摊，不缩放本地口粮需求。
        from content.data import WINE_TAX_SHARE, WINE_GRAIN_PER_GUAN
        wine_grain_monthly = self.wine_tax / WINE_TAX_SHARE * WINE_GRAIN_PER_GUAN
        wine_share = wine_grain_monthly * (route_pop / max(float(self.population), 1.0))
        need = route_demand_people * PER_CAPITA_MONTH_GRAIN + wine_share   # 月需求（石）
        grain = float(p.get("grain", 0))
        total_grain = grain
        from content.data import HOARD_SUPPLY_SQUEEZE
        hoard = float(p.get("pops", {}).get("士绅", {}).get("grain", 0))
        _pop_release = sum(pop.get("grain", 0) for pop in p.get("pops", {}).values()) * 0.02
        supply = max(total_grain / 12.0 + _pop_release - hoard * HOARD_SUPPLY_SQUEEZE, 0.01)
        ratio = max(0.5, min(2.0, need / max(supply, 0.01)))
        price = self.grain_price * ratio
        # 库存抑价：本路太仓（按人口摊）+常平存粮相对月需求越充足，价越低
        # 全国太仓仍按各路在籍口份额分粮，这是中央库存的分摊规则；不要拿它来缩放本地隐户需求。
        _gran_share = float(getattr(self, "granary", 0) or 0) * (
            route_pop / max(float(self.population), 1.0))
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

        **P2-2 口径注记（2026-09-19）**：`nominal_annual` 只是**三项账面**（工商·役钱·市舶，
        贴史实年额），而 `monthly_in` 是**五项月度应征**（另加二税折色、盐课），二者**不同口径**，
        不可直接相除；`nominal_annual/12 − monthly_in` 也不是"隐漏与拖欠"（开局为**负值**，
        −682,098贯/月，漏出不可能为负）。故本函数**新增** `nominal_annual_full` /
        `monthly_in_taxed` / `arrival_ratio_taxed` / `arrival_ratio_full` /
        `arrival_ratio_cross_scope`（旧面板跨口径原值，仅作诊断）/ `mechanism_arrival_rate` /
        `arrival_ratio_scope*` 单点派生字段：前端直读比率、不再自行相除，避免多口径复制。
        三个比率**分子分母各自同科目**（跨口径旧值单列保留、不得当"到账率"用）。

        **M34-④ 口径统一（2026-10-11，用户裁 D1=甲/D2=保留诊断/D3=显式命名）**：
        二税折色自 P1 起结算走**新模型**（应征＝全额税基×征收率，**无 arrival 折扣**），
        面板旧径（`calc_monthly_tax_income`，arrival 已乘进税基）只作兼容锚保留于
        `tax_color_legacy`。故：
          - `tax_color` / `assessed_total` = **月应征**（`calc_land_tax_channels`）；
          - `tax_color_annual` = 月应征×12（**去**旧径 `/arrival×12` 反推）；
          - `arrival_ratio_*` 家族＝**诊断口径**（勿当精确到账率；scope 串已明写）；
          - 新增 `land_tax_last`（上月结账快照：应征/实收/三分）、`land_tax_cum`（累计三分）、
            `collection_rate_avg` / `transfer_rate_avg`（月度双率均值）、`legacy_arrival_rate`。
        机制常量与既有字段语义**未动**（`tax_color` 语义按本次裁决由"旧径到库"改为"新径应征"）。

        **M34-① 地方支出 V2（2026-10-11 · 只读预报层先行）**：新增 `local_expenditure`
        （五科目应支/封顶/计划/缺口，`calc_local_expenditure()`）——**只报不记**，
        真扣款（府库支用）与欠费科目待用户裁决 D1–D5；该字段**不并入** `total_out`。
        """
        from content.data import (
            COMMERCE_TAX_RATE_DEFAULT,
        )
        arrival = self.calc_arrival_rate()
        shortage = self.coin.get("shortage", 0.3)
        tax_coeff = TAX_COEFF_MIN + (TAX_COEFF_MAX - TAX_COEFF_MIN) * (1 - shortage)

        commerce = self.calc_commerce()
        rate = max(COMMERCE_TAX_RATE_MIN, min(COMMERCE_TAX_RATE_MAX,
                    getattr(self, "commerce_tax_rate", COMMERCE_TAX_RATE_DEFAULT)))
        commerce_tax = int((commerce / 12.0) * rate * arrival * tax_coeff)
        # 役钱（徭役代役钱）：与 `_settle_finance` 同源——税基＝**应役丁**（B1b，
        # 佃农（客户）无国税/摊派、坊郭户（工匠/商人）不服乡村差役、官户（士绅/官僚）免役、兵免；
        # 隐户不落籍，既不在 `size` 也不在 `ding`）。
        from core.foundation.ledger.pop_structure import service_ding_total
        poll_tax = int((service_ding_total(self) * TAX_POLL_RATIO / 12) * arrival * tax_coeff)
        maritime_trade = self.calc_maritime_trade()
        maritime_tax = int((maritime_trade / 12.0) *
                           (self.maritime.get("tariff", 0.10) if self.maritime.get("open") else 0.0) *
                           arrival * tax_coeff)

        # 名义岁入（账面，贴史实） = 年应征工商税 + 年役钱 + 年市舶抽解
        nominal_annual = int(commerce * rate) + int(ANNUAL_TAX_BASE * POLL_TAX_NOMINAL_SHARE) \
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
        # M34-④ 口径统一（甲）：二税折色改**新模型应征**（全额税基×征收率，无 arrival 折扣）；
        # 旧径值另存 `tax_color_legacy`（兼容/回归锚——结算侧自 P1 起已走新径）。
        tax_color_legacy, _ = self.calc_monthly_tax_income(tax_coeff)
        _ch = self.calc_land_tax_channels()
        assessed_total = int(_ch.get("assessed_total", 0) or 0)
        tax_color_total = assessed_total
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
        # 加俸预算消耗（与 _settle_finance 同源口径：M2 定稿 (a) 后池是**真实分账基金**，
        # 发放额只作读数展示，**不再计入 total_out** —— 它已由池支付并落入官僚 POP，
        # 再计一次支出即重复计账）。
        clerk_gap_total, _ = self.calc_clerk_gap()
        payraise_used = min(self.payraise_budget, int(clerk_gap_total) + 10_000)
        monthly_in = commerce_tax + poll_tax + maritime_tax + tax_color_total + salt_coin
        total_out = (expenditure + effective_cash_out
                     + int(corruption_cash_ded) + sui_gong)

        # ---- P2-2（会计指标口径核对）：到账率**收敛为单点派生**，前端不再自行相除 ----
        # 为什么要有这一段：`nominal_annual` 只覆盖**三项**（工商·役钱·市舶），
        # `monthly_in` 却覆盖**五项**（另加二税折色、盐课）。前端原来自行算
        # `monthly_in / (nominal_annual/12)`，分母缺了二税折色与盐课——开局这两项
        # 合计 1,578,554 贯/月，占分子 **50.9%** —— 于是比值必然 >100%：
        # 开局实测 3,098,770 ÷ (29,000,060 ÷ 12) = **128.2%**（走查截图同值）。
        # 更早一步，`diff = nominal_annual/12 − monthly_in = −682,098贯/月` 被面板当作
        # 「隐漏与拖欠」输出 → 出现**负的隐漏**，自相矛盾（漏出不可能为负）。
        # 修法：**不动**任何机制常量、**不改** `nominal_annual` 的取值口径与字段语义，
        # 只在此处补**同口径分母**与比率读数，前端直读（单点口径，杜绝算法复制）。
        # 应征额反推（**仅盐课仍适用**）：`calc_salt_coin`（盐课）的月额**已乘 arrival**，
        # 故 ÷ arrival × 12 即回年度应征额；arrival 可能为 0 或
        # 缺失（损坏存档）→ 用 max(arrival, ARRIVAL_MIN) 兜底，并保证结果为有限值：
        # 科目为 0 时该项为 0（不做无意义反推）。
        # M34-④ 注：二税折色**不再走此反推**——自 P1 起其月额已是新模型**应征**
        #   （全额税基×征收率，无 arrival 折扣），见下方 `tax_color_annual`。
        import math as _math   # 局部导入（本文件既有风格：函数内按需 import）
        try:
            _arr = float(arrival)
        except (TypeError, ValueError):
            _arr = ARRIVAL_MIN
        if not _math.isfinite(_arr) or _arr < ARRIVAL_MIN:
            _arr = ARRIVAL_MIN
        # M34-④（甲②）：应征已是**全额税基×征收率**（无 arrival 折扣）→ 年应征 = 月应征×12；
        # **不得**再 ÷arrival（旧径的反推式在新口径下会放大 1/arrival ≈1.7×）。
        tax_color_annual = (float(assessed_total) * 12.0) if assessed_total else 0.0
        salt_annual = (float(salt_coin) / _arr * 12.0) if salt_coin else 0.0
        # 五项全口径年度应征（**新增**派生量；不是对 nominal_annual 的改写）
        nominal_annual_full = nominal_annual + tax_color_annual + salt_annual
        # 三税（工商·役钱·市舶）月度应征合计：供前端 tooltip 展示"同口径分子"，
        # 免得前端为写等式再自行相加（前端不复制算法）。
        monthly_in_taxed = commerce_tax + poll_tax + maritime_tax
        _den_taxed = nominal_annual / 12.0          # 三税口径：三项账面月额
        _den_full = nominal_annual_full / 12.0      # 五科目口径：五项应征月额
        # 分母为 0（极端存档）→ None（缺失语义：前端显示"未定义"）；
        # **禁止**回落 0 或 1.0 假装无事（1.0 会让"到账完美"成为默认）。
        # 口径纪律：**分子与分母必须同科目**，否则又回到本次要修的"跨口径比值"。
        #   arrival_ratio_taxed ＝ 三税应征 ÷ 三税账面月额（分子分母都是三税）
        #   arrival_ratio_full  ＝ 五项（四实收＋二税折色**应征**）÷ 五项应征月额（同科目）
        #     M34-④ 注：二税折色分子按**应征**计入（月度实收须待月结）⇒ 该比值是"到账率"的
        #     近似**上界**，精确到账见 `land_tax_last`／`land_tax_cum`；已在 scope 串明写诊断口径。
        # 注：任务书初稿把 arrival_ratio_taxed 写成 `monthly_in / (nominal_annual/12)`
        #   （＝五科目÷三税，开局 128.2%），那正是本次要修的跨口径比值本身，与
        #   tooltip 要求的"成立等式（≈64.6%）"矛盾；故此处按**同口径**实现，跨口径旧值
        #   另立 arrival_ratio_cross_scope 保留（仅作诊断/回归凭证，**不得**当到账率显示）。
        #   实测同口径三税值 62.9%（＝1,520,216 ÷ 2,416,672），与走查所记 64.625% 的差
        #   来自**役钱基数不同源**：三税实际役钱按**应役丁**（7,228,339/年），而
        #   `nominal_annual` 的役钱项按 ANNUAL_TAX_BASE×POLL_TAX_NOMINAL_SHARE（8,000,000/年）；
        #   64.625% 正是 arrival×TAX_COEFF（1.1）——只对工商项精确成立（1,130,940÷(21,000,060/12)）。
        #   改名义岁入役钱基数属机制改动，本轮不做（见交付说明"遗留/需用户裁决"）。
        arrival_ratio_taxed = (monthly_in_taxed / _den_taxed) if _den_taxed > 0 else None
        # M34-④（甲③）：五科目口径——分子/分母**同步换新口径**（二税折色按**应征**计入；
        # 月度实收须待月结，真实到账见 `land_tax_last`（上月结账）/`land_tax_cum`（累计三分））。
        # ⇒ 本比值为**诊断口径**（"到账率"的近似上界），**勿**当精确到账率使用。
        arrival_ratio_full = (monthly_in / _den_full) if _den_full > 0 else None
        # 旧面板算法原值（跨口径：分子五科目、分母三税账面）——开局 128.2%。
        # 保留它只为「可复现旧读数 + 回归断言」，UI 一律不得据此称"到账率"。
        arrival_ratio_cross_scope = (monthly_in / _den_taxed) if _den_taxed > 0 else None
        # 机制到账率（隐漏/胥吏侵蚀/钱荒后的折扣系数）＝ 二税折色、盐课实收的隐含折扣，
        # 也是 `calc_arrival_rate()` 的当月值；供 tooltip 解释"为何二税折色/盐课口径 = 58.8%"。
        # 缺失（非有限值）→ None（不伪造 1.0）。
        # M34-④（D3）：**旧口径**——改名 `legacy_arrival_rate`（新键），旧键保留兼容一版。
        mechanism_arrival_rate = _arr if _math.isfinite(_arr) else None
        legacy_arrival_rate = mechanism_arrival_rate
        # M34-④（乙）：新模型只读字段（月度双率均值 + 真账快照/累计三分）
        _crs = [self.calc_collection_rate(_r) for _r in self.prefectures]
        collection_rate_avg = round(sum(_crs) / len(_crs), 4) if _crs else None
        _splits = [self.finance_split(_r) for _r in self.prefectures]
        transfer_rate_avg = round(sum(_s[0] for _s in _splits) / len(_splits), 4) if _splits else None
        _last = self.statistics.get("land_tax_last")
        land_tax_last = dict(_last) if isinstance(_last, dict) else None
        land_tax_cum = {
            "assessed": int(self.statistics.get("land_tax_assessed", 0) or 0),
            "collected": int(self.statistics.get("land_tax_collected", 0) or 0),
            "central": int(self.statistics.get("land_tax_central", 0) or 0),
            "local": int(self.statistics.get("land_tax_local", 0) or 0),
            "diverted": int(self.statistics.get("land_tax_diverted", 0) or 0),
        }
        scope_taxed = "三税（工商·役钱·市舶）——不含二税折色与盐课（诊断口径·勿当到账率）"
        scope_full = "五科目（工商·役钱·市舶·二税折色[按应征]·盐课）（诊断口径·勿当到账率）"
        # M34-①（V2 **预报层**·只读）：州郡府库支用应支/封顶/计划/缺口——五科目各挂既有派生量，
        # **不改钱账**（真扣款与欠费科目待裁决 D1–D5，见 specs/economy/地方支出V2_开工门台账.md）；
        # 也**不并入** total_out（地方与中央是不同主体，并入即双计）。
        local_expenditure = self.calc_local_expenditure()

        # ---- 后端权威定性字段（前端一律读这里，杜绝多口径重复与真实层泄漏）----
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
            # ---- P2-2 新增单点派生（既有字段一律原值/原语义，机制常量未动）----
            # `nominal_annual_full`：**五项全口径**年度应征 = nominal_annual（三项账面）
            #   + 二税折色应征年 + 盐课应征年。与旧「名义岁入」不同的**唯一原因**就是
            #   它多含二税折色与盐课；旧比值之所以 >100%，正是分母缺这两项所致。
            # `monthly_in_taxed`：**三税**（工商·役钱·市舶）月度应征合计，即
            #   `nominal_annual` 那三项在月度侧的同科目分子。
            # `arrival_ratio_taxed`：**三税口径**到账率 = 三税应征 ÷ (三税账面年额÷12)，
            #   覆盖 工商·役钱·市舶，**分子分母同科目**（开局 62.9%）。分母为 0 → None。
            #   （不是 monthly_in/(nominal_annual/12)：那是跨口径比值，见下一字段。）
            # `arrival_ratio_full`：**五科目口径**诊断比值 = monthly_in ÷ (nominal_annual_full/12)，
            #   分子分母同口径（覆盖 工商·役钱·市舶·二税折色[按应征]·盐课；开局 60.7%）。
            #   M34-④ 注：二税折色分子按**应征**计入（月度实收须待月结）⇒ 它是"到账率"的
            #   **近似上界**，真实到账看 `land_tax_last` / `land_tax_cum`。分母为 0 → None。
            # `arrival_ratio_cross_scope`：**旧面板算法原值**（分子五科目 ÷ 分母三税账面）
            #   = 开局 **128.2%**。它的存在本身就是"分母缺二税折色与盐课 → 比值 >100%
            #   → 差额为负却被当『隐漏与拖欠』"这条自相矛盾的凭证；**仅作诊断与回归**，
            #   UI 不得把它当"到账率"显示。
            # `mechanism_arrival_rate`：机制到账率（隐漏/钱荒后的折扣系数），供 tooltip 解释。
            #   M34-④（D3）：**旧口径**，新键 `legacy_arrival_rate` 为权威命名，旧键保留兼容一版。
            # `land_tax_last`：**上月**田赋折色结账快照（应征/实收/上供/留州/截留），未结账 → None。
            # `land_tax_cum`：**累计**真账三分（应征/实收/上供/留州/截留），审计留痕。
            # `collection_rate_avg` / `transfer_rate_avg`：各路征收率/上供份额的月度均值。
            # `arrival_ratio_scope*`：上面比率各自覆盖的科目（中文可读，前端直取，
            #   不再各处自写口径）；两处均**明写不含二税折色与盐课**，以免再被当成同一比率。
            "nominal_annual_full": nominal_annual_full,
            "monthly_in_taxed": monthly_in_taxed,
            "arrival_ratio_taxed": arrival_ratio_taxed,
            "arrival_ratio_full": arrival_ratio_full,
            "arrival_ratio_cross_scope": arrival_ratio_cross_scope,
            "mechanism_arrival_rate": mechanism_arrival_rate,
            "arrival_ratio_scope": f"{scope_taxed}｜{scope_full}",
            "arrival_ratio_scope_taxed": scope_taxed,
            "arrival_ratio_scope_full": scope_full,
            "commerce": commerce_tax,              # 月工商税（实际到库）
            "poll": poll_tax,                      # 月役钱
            "maritime": maritime_tax,              # 月市舶抽解
            "tax_color": tax_color_total,          # 月二税折色**应征**（新模型；M34-④ 口径统一）
            "tax_color_legacy": int(tax_color_legacy),  # 旧径（arrival 折扣）——兼容/回归锚
            "salt_coin": salt_coin,                # 月盐课（单列，不进二税）
            # M34-④（乙）：新模型只读字段（月度双率 + 真账快照/累计三分）
            "assessed_total": assessed_total,             # 田赋折色月应征（≡ tax_color）
            "collection_rate_avg": collection_rate_avg,   # 各路征收率均值
            "transfer_rate_avg": transfer_rate_avg,       # 各路上供份额均值
            "land_tax_last": land_tax_last,               # 上月结账快照（应征/实收/三分）
            "land_tax_cum": land_tax_cum,                 # 累计真账三分（审计留痕）
            "legacy_arrival_rate": legacy_arrival_rate,   # 旧口径到账率（D3 显式命名）
            # M34-①（V2 预报层·只读）：州郡支用应支/计划/缺口（不并入 total_out）
            "local_expenditure": local_expenditure,
            # M34-① 批次 1 真账留痕（顺序改造 + 地方支用腿）
            "local_arrears": int(self.statistics.get("local_arrears", 0) or 0),
            "local_expense_paid": int(self.statistics.get("local_expense_paid", 0) or 0),
            "land_tax_required": int(self.statistics.get("land_tax_required", 0) or 0),
            # M34-① 欠支的 **POP 挂载**读数（债权人在 POP 上；与欠税对称）
            "local_arrears_by_kind": dict(self.statistics.get("local_arrears_by_kind") or {}),
            "local_arrears_pop": sum(
                int((v or {}).get("欠给", 0) or 0)
                for p in self.prefectures.values()
                for v in (p.get("pops") or {}).values() if isinstance(v, dict)),
            # M34-① D6′：地方附加收入（独立池；坊场钱/经制钱/杂税）
            "local_extra_income": int(self.statistics.get("local_extra_income", 0) or 0),
            "local_extra_by_kind": dict(self.statistics.get("local_extra_by_kind") or {}),
            # M34-① D5′：欠给分层压力（AI/事件接口；只报压力，不判事件）
            "local_arrears_pressure": dict(
                self.statistics.get("local_arrears_pressure") or {}),
            # 🟢 M35-B：欠给**身份化**（官员欠俸／胥吏欠钱／衙役欠钱／士卒欠饷）
            "local_arrears_by_identity": dict(
                self.statistics.get("local_arrears_by_identity") or {}),
            # 🟢 M35-A/C/D：身份经济层 · 职业映射 · 财政可见度（均只读）
            "identity_economics": self.identity_economics(),
            "local_identities": self.calc_local_identities(),
            # 🟢 M35-2-B：身份压力状态（只报状态，不自动成事件）
            "identity_pressures": self.identity_pressures(),
            # 🟢 M35-2-C：**玩家视角**的可见度（不含 real；真账另走内部 `fiscal_visibility()`）
            "fiscal_visibility": self.fiscal_visibility_view("player"),
            # 欠给时间化（金额之外的"欠了几个月"；供 AI 判断慢性程度）
            "local_arrears_months": self.arrears_months_summary(),
            # 🟢 M35-3：补发能力（AI 决策接口：是否拨款/减税/整顿）；累计补发额
            "arrears_recovery_capacity": self.arrears_recovery_capacity(),
            "local_arrears_repaid": int(self.statistics.get("local_arrears_repaid", 0) or 0),
            # 🟢 M35-D：民间传闻档位（0–4；AI 可读状态，非事件）
            "rumor_tier": self.rumor_tier()["tier"],
            "rumor": self.rumor_tier(),
            # 🟢 M35-C-1：人口口径分解（六桶 ＋ occupation ＋ 流民）
            "population_breakdown": self.population_breakdown(),
            # 🟢 P3-3/P3-4：差额报表（**玩家视角**：只账面侧）＋ 巡按反向观察量
            "fiscal_gap_report": self.fiscal_gap_report("player"),
            "inspection_backlash": self.inspection_backlash_readout(),
            # P2 账面（V1.3 §5）：田赋折色真账留痕 ＋ 损耗科目（信息差一/二级；三级留调查·P3）
            "land_tax": {
                "assessed": int(self.statistics.get("land_tax_assessed", 0) or 0),
                "collected": int(self.statistics.get("land_tax_collected", 0) or 0),
                "central": int(self.statistics.get("land_tax_central", 0) or 0),
                "local": int(self.statistics.get("land_tax_local", 0) or 0),
                "diverted": int(self.statistics.get("land_tax_diverted", 0) or 0),
            },
            "tax_loss": self.tax_loss_readout(),
            # P3 发现系统（V1.3 §7）：四级阶梯读数（异常→怀疑→证据→真相）
            "discovery": _discovery_readout(self),
            "monthly_in": monthly_in,              # 月实际到库合计
            "expenditure": expenditure,            # 月常支（派生）
            "army_cash": army_cash_total,          # 月军费（折色饷钱）
            "official_cash": official_cash_total,  # 月官俸折色
            "clerk_cash": clerk_cash_total,        # 月吏俸折色（实发）
            "corruption_ded": corruption_cash_ded, # 月吏俸缺口贪腐扣减（隐性，不进UI明细）
            "cash_out": cash_out,                  # 月折色俸禄（旧口径兜底）
            "sui_gong": sui_gong,                  # 月岁币
            # 审查 M2：加俸发放额**单列**（池支出 → 官僚 POP 收款）。
            # 它**不在** `total_out` 里（池是钱、已直接付给官吏，非国库支出）；
            # 单列供面板显示"本月加俸发放多少"，避免读者以为漏计。
            "payraise_disbursed": payraise_used,
            "payraise_pool": self.payraise_budget,
            "total_out": total_out,                # 月支出合计（不含 payraise，见上）
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
    # P1 双层税基 · 四率（V1.3 终稿 §2-§3；Q3 甲：先作用于田赋折色）
    # ================================================================
    def calc_collection_rate(self, route: str) -> float:
        """征收率（P1 首版·C2 小权重起步）：基线 ＋ 治理微调（全域约 ±0.02）。

        征收侧唯一出口（原由 `arrival` 一并承担，P1 拆出）；灾/逃项留 P4 小权重接入。
        """
        p = self.prefectures.get(route) or {}
        gov = float(p.get("govern", FIN_KEEP_GOVERN_ANCHOR) or FIN_KEEP_GOVERN_ANCHOR)
        base = float((getattr(self, "finance", None) or {}).get(
            "collection_rate", FIN_COLLECTION_BASE))
        rate = base + (gov - FIN_KEEP_GOVERN_ANCHOR) * FIN_COLLECTION_GOVERN_W
        return _clamp(rate, FIN_COLLECTION_MIN, FIN_COLLECTION_MAX)

    def finance_split(self, route: str) -> tuple:
        """该路归一三率 `(transfer, keep, div)`（保证 t+k+d≡1）。

        结算侧唯一出口；归一化单点见 `normalize_finance_split`（保护顺序 div→keep→transfer）。
        """
        fin = getattr(self, "finance", None) or {}
        p = self.prefectures.get(route) or {}
        gov = float(p.get("govern", FIN_KEEP_GOVERN_ANCHOR) or FIN_KEEP_GOVERN_ANCHOR)
        keep = _clamp(float(fin.get("local_keep_rate", FIN_KEEP_BASE))
                      + (gov - FIN_KEEP_GOVERN_ANCHOR) * FIN_KEEP_GOVERN_W,
                      FIN_KEEP_MIN, FIN_KEEP_MAX)
        return normalize_finance_split(
            float(fin.get("transfer_rate", FIN_TRANSFER_RATE)), keep,
            float(fin.get("diversion_rate", FIN_DIV_RATE)))

    def apply_finance_reform(self, deltas: dict) -> dict:
        """改革轴（V1.3 §9）：按增量调整四率，随后**归一化**（保护顺序 div→keep→transfer）。

        - 接受键：`transfer_rate`／`local_keep_rate`／`diversion_rate`／`collection_rate`；
        - 三率（分流）调后归一（和 ≡ 1，transfer 最高保护）；`collection_rate` 单独钳制；
        - 未知键/坏值忽略；返回 `{"before","after","applied"}`（供日志与审计）。
        """
        fin = getattr(self, "finance", None)
        if not isinstance(fin, dict):
            return {"before": {}, "after": {}, "applied": {}}
        before = dict(fin)
        applied = {}
        for _k, _v in (deltas or {}).items():
            if _k not in ("transfer_rate", "local_keep_rate",
                          "diversion_rate", "collection_rate", "local_expense_mult"):
                continue
            if isinstance(_v, bool) or not isinstance(_v, (int, float)):
                continue
            fin[_k] = float(fin.get(_k, 0.0)) + float(_v)
            applied[_k] = float(_v)
        _t, _k2, _d = normalize_finance_split(
            float(fin.get("transfer_rate", FIN_TRANSFER_RATE)),
            float(fin.get("local_keep_rate", FIN_KEEP_BASE)),
            float(fin.get("diversion_rate", FIN_DIV_RATE)))
        fin["transfer_rate"], fin["local_keep_rate"], fin["diversion_rate"] = _t, _k2, _d
        fin["collection_rate"] = float(_clamp(
            float(fin.get("collection_rate", FIN_COLLECTION_BASE)),
            FIN_COLLECTION_MIN, FIN_COLLECTION_MAX))
        # M34-①（裁决 2026-10-11 · 留接口）：**地方经费保障倍数**——不参与四率归一化，
        # 独立钳制到 [MIN, MAX]（集权下调 → 责任收归中央；分权上调 → 地方经费更足）。
        fin["local_expense_mult"] = float(_clamp(
            float(fin.get("local_expense_mult", LOCAL_EXP_MULT_BASE)),
            LOCAL_EXP_MULT_MIN, LOCAL_EXP_MULT_MAX))
        return {"before": before, "after": dict(fin), "applied": applied}

    def calc_land_tax_channels(self) -> dict:
        """田赋折色「双层税基＋三率」读数（只读；P1·Q3 甲：**仅折色**走新模型）。

        返回 `{"assessed_total": int, "by_route": {路: {tax_base, assessed, transfer, keep, div}}}`
        - `tax_base`：全额税基（贯/月；＝旧公式去 arrival 折扣）；
        - `assessed`：应征 ＝ `int(tax_base × collection_rate)`；
        - 三率为**归一后**值（assessed 可被完整三分，无残差）。
        """
        hyd = self.tech.get("hydraulics", 40) / 100.0
        hidden = self.land.get("hidden_rate", 0.35)
        harvest = self.land.get("yield", 1.0)
        by_route = {}
        total = 0
        for name, p in self.prefectures.items():
            gy = float(p.get("grain", 0))                    # 年总产（石/年）
            tax_base = (gy * LAND_TAX_RATE_BENEFIT * harvest * (1 - hidden)
                        * (0.8 + 0.4 * hyd) * TAX_COLOR_RATE
                        * self.grain_price / 12.0)           # 年折色总额按月 1/12
            assessed = int(tax_base * self.calc_collection_rate(name))
            transfer, keep, div = self.finance_split(name)
            by_route[name] = {"tax_base": tax_base, "assessed": assessed,
                              "transfer": transfer, "keep": keep, "div": div}
            total += assessed
        return {"assessed_total": int(total), "by_route": by_route}

    def calc_local_expenditure(self) -> dict:
        """州郡府库支用 **只读预报**（M34-① V2 预报层；**不写任何账本**）。

        依据：`_dev_tools/game-docs/specs/economy/地方支出V2_开工门台账.md`
        —— 现状府库只有流入与平籴，**消费性支用＝0**。本函数把"若接线将要花多少"提前算出：
        五科目应支 → 预算封顶 → 计划额 → 缺口，供面板/AI 在钱还没花之前就看见地方财政压力。

        口径（各挂**既有派生量**，不新造税基；费率见 `content` 常量 `LOCAL_EXP_*`，待校准门定值）：
          ① 行政 `admin`   ＝ 本路官俸 × `LOCAL_EXP_ADMIN_SHARE`（史实：公使钱/职田）
          ② 治安 `security`＝ 本路军费 × `LOCAL_EXP_SECURITY_SHARE` × (1 + unrest/100)
          ③ 水利 `waterworks` ＝ 本路水利资产折算造价 × `LOCAL_EXP_WATERWORKS_RATE`
             （折算式与 `_settle_upkeep` 同源：`base_cost × BUILDING_COST_GROWTH^(lv-1)`）
          ④ 粮仓 `granary` ＝ 本路常平库存(石) × `LOCAL_EXP_GRANARY_PER_STONE`
          ⑤ 救灾 `relief`  ＝ 灾路人丁 × `LOCAL_EXP_RELIEF_PER_CAPITA` × 严重度(1–5)；**非灾月为 0**
        封顶（D4 初值）：`cap = 本路府库 × LOCAL_EXP_CAP_SHARE`，`plan = min(due, cap)`。
        **缺口 `shortfall` ＝ due − plan**：本层**只报不记**（真扣款与欠费科目待裁决 D1–D5）。
        """
        from content.data import (BUILDING_COST_GROWTH, BUILDING_STD,
                                  LOCAL_EXP_ACTIVE_KINDS, LOCAL_EXP_ADMIN_SHARE,
                                  LOCAL_EXP_CAP_SHARE, LOCAL_EXP_CLERK_SHARE,
                                  LOCAL_EXP_EFFICACY_GRIP_W,
                                  LOCAL_EXP_EFFICACY_MIN, LOCAL_EXP_EFFICACY_PAY_W,
                                  LOCAL_EXP_GRANARY_PER_STONE, LOCAL_EXP_MULT_BASE,
                                  LOCAL_EXP_MULT_MAX, LOCAL_EXP_MULT_MIN,
                                  LOCAL_EXP_RELIEF_PER_CAPITA,
                                  LOCAL_EXP_SECURITY_SHARE, LOCAL_EXP_WATERWORKS_RATE)
        from core.building_jobs import building_level as _bld_lv
        import math as _math   # 局部导入（本文件既有风格：函数内按需 import）

        def _i(v, default=0):
            try:
                f = float(v)
            except (TypeError, ValueError):
                return default
            return int(f) if _math.isfinite(f) else default

        _official = self.calc_official_cash()[1]
        _army = self.calc_army_cash()[1]
        _sev = max(0, _i(getattr(self, "disaster_severity", 0)))
        _region = str(getattr(self, "disaster_region", "") or "")
        _wstd = BUILDING_STD.get("水利") or {"base_cost": 0}
        by_route = {}
        tot = {"official_salary": 0, "clerk_pay": 0, "runner_pay": 0,
               "public_supply": 0, "granary": 0, "relief": 0}
        for name, p in self.prefectures.items():
            if not isinstance(p, dict):
                continue
            pops = p.get("pops") if isinstance(p.get("pops"), dict) else {}
            pop_total = sum(_i((v or {}).get("size")) for v in pops.values()
                            if isinstance(v, dict))
            if pop_total <= 0:
                pop_total = _i(p.get("population"))
            unrest = min(100.0, max(0.0, float(_i(p.get("unrest")))))
            # ⑤ 史实科目（裁决词表）：官员俸禄／胥吏雇钱／衙役雇钱／公用钱
            official_salary = int(_i(_official.get(name, 0)) * LOCAL_EXP_ADMIN_SHARE)
            # 胥吏雇钱应得 = 路吏额 × 吏月俸 × 地方承担份额（**应得**口径，未乘 pay_ratio；
            # 欠给正是"应得 − 实付"的差额，故基数须为应得）
            clerk_pay = int(float(_officialdom.route_clerks(p)) * CLERK_PAY_PER_MONTH
                            * LOCAL_EXP_CLERK_SHARE)
            runner_pay = int(_i(_army.get(name, 0)) * LOCAL_EXP_SECURITY_SHARE
                             * (1.0 + unrest / 100.0))
            _wlv = _bld_lv((p.get("buildings") or {}).get("水利"), 1) if isinstance(
                p.get("buildings"), dict) else 0
            _wasset = float(_wstd.get("base_cost", 0)) * (
                BUILDING_COST_GROWTH ** (max(1, _wlv) - 1)) if _wlv > 0 else 0.0
            public_supply = int(_wasset * LOCAL_EXP_WATERWORKS_RATE)
            granary = int(_i(p.get("changping_stock")) * LOCAL_EXP_GRANARY_PER_STONE)
            relief = 0
            if _sev > 0 and (not _region or _region == name):
                relief = int(pop_total * LOCAL_EXP_RELIEF_PER_CAPITA * _sev)
            due = official_salary + clerk_pay + runner_pay + public_supply + granary + relief
            coffer = max(0, _i(p.get("local_treasury")))
            cap = int(coffer * LOCAL_EXP_CAP_SHARE)
            plan = min(due, cap)
            due_active = official_salary + clerk_pay + runner_pay + public_supply
            plan_active = min(due_active, cap)
            # M34-①（裁决：官员要能**有效使用**府库资金）：有效使用率 = 1 − 把持/欠俸/侵渔
            _grip = float((p.get("clerks_detail") or {}).get("grip", 0.0) or 0.0) \
                if isinstance(p.get("clerks_detail"), dict) else 0.0
            try:
                _pay = float(self.calc_pay_ratio(name))
            except Exception:            # noqa: BLE001 — 读数不得因单路坏值整体失败
                _pay = 1.0
            _div = float(self.finance_split(name)[2])
            efficacy = 1.0 - (LOCAL_EXP_EFFICACY_GRIP_W * min(1.0, max(0.0, _grip))
                              + LOCAL_EXP_EFFICACY_PAY_W * min(1.0, max(0.0, 1.0 - _pay))
                              + min(1.0, max(0.0, _div)))
            efficacy = round(min(1.0, max(LOCAL_EXP_EFFICACY_MIN, efficacy)), 4)
            # 保障倍数（玩家接口·集权可下调）：责任科目 × 倍数 × 有效使用率 = **现实应支**
            _mult = min(LOCAL_EXP_MULT_MAX, max(LOCAL_EXP_MULT_MIN, float(
                (self.finance or {}).get("local_expense_mult", LOCAL_EXP_MULT_BASE))))
            due_eff = int(due_active * _mult * efficacy)
            plan_eff = min(due_eff, cap)
            by_route[name] = {
                "coffer": coffer, "official_salary": official_salary,
                "clerk_pay": clerk_pay, "runner_pay": runner_pay,
                "public_supply": public_supply, "granary": granary, "relief": relief,
                "due": due, "cap": cap, "plan": plan, "shortfall": due - plan,
                # M34-① 批次 1（财政顺序）：**责任科目**应支/计划（真扣款只用这组）
                "due_active": due_active, "plan_active": plan_active,
                "shortfall_active": due_active - plan_active,
                # 官员有效使用：grip/实付率/侵渔 → 有效使用率 → 现实应支/计划
                "grip": round(min(1.0, max(0.0, _grip)), 4),
                "pay_ratio": round(min(1.0, max(0.0, _pay)), 4),
                "efficacy": efficacy,
                "due_eff": due_eff, "plan_eff": plan_eff,
                "shortfall_eff": due_eff - plan_eff,
            }
            tot["official_salary"] += official_salary
            tot["clerk_pay"] += clerk_pay
            tot["runner_pay"] += runner_pay
            tot["public_supply"] += public_supply
            tot["granary"] += granary
            tot["relief"] += relief
        total_due = sum(tot.values())
        total_plan = sum(r["plan"] for r in by_route.values())
        total_due_active = sum(r["due_active"] for r in by_route.values())
        total_plan_active = sum(r["plan_active"] for r in by_route.values())
        total_due_eff = sum(r["due_eff"] for r in by_route.values())
        total_plan_eff = sum(r["plan_eff"] for r in by_route.values())
        _mult_all = min(LOCAL_EXP_MULT_MAX, max(LOCAL_EXP_MULT_MIN, float(
            (self.finance or {}).get("local_expense_mult", LOCAL_EXP_MULT_BASE))))
        return {
            "cap_share": LOCAL_EXP_CAP_SHARE,
            "active_kinds": tuple(LOCAL_EXP_ACTIVE_KINDS),
            "expense_mult": _mult_all,
            "disaster": {"severity": _sev, "region": _region},
            "by_kind": dict(tot),
            "total_due": total_due,
            "total_plan": total_plan,
            "total_shortfall": total_due - total_plan,
            # 责任科目口径（批次 1 真扣款用；粮仓/救灾仍为预报）
            "total_due_active": total_due_active,
            "total_plan_active": total_plan_active,
            "total_shortfall_active": total_due_active - total_plan_active,
            # 现实口径（× 保障倍数 × 官员有效使用率）＝批次 1 实际划出/支付的口径
            "total_due_eff": total_due_eff,
            "total_plan_eff": total_plan_eff,
            "total_shortfall_eff": total_due_eff - total_plan_eff,
            "by_route": by_route,
        }

    def identity_economics(self) -> dict:
        """M35-A 官僚**身份经济层**（只读投影）：官／吏 财富归属、份额、身份欠给。

        口径（裁决：**只加经济接口，不改人口真账**）：
          - 记账额＝`officials_wealth`／`clerks_wealth`（**记账层**；两池合计 ≤ 整池 wealth）；
          - `wealth_share` ＝ 记账额 ÷ Σ记账额（**读侧派生**；两池皆空 → `None`，缺失不作 0）；
          - 身份欠给：`officials_salary_arrears`（官欠俸）／`clerks_pay_arrears`（吏欠钱）；
          - **不改粮耗、不拆 POP、不动 `pop_bridge` 镜像**（新字段已注册为可加类）。
        """
        def _i(v):
            try:
                return int(v or 0)
            except (TypeError, ValueError):
                return 0

        by_route = {}
        tot = {"officials": 0, "clerks": 0, "officials_wealth": 0, "clerks_wealth": 0,
               "pool_wealth": 0, "officials_salary_arrears": 0, "clerks_pay_arrears": 0,
               "runner_count": 0, "occupation_income_runner": 0}
        for name, p in self.prefectures.items():
            pool = ((p.get("pops") or {}) if isinstance(p, dict) else {}).get("官僚")
            if not isinstance(pool, dict):
                continue
            ow = _i(pool.get("officials_wealth"))
            cw = _i(pool.get("clerks_wealth"))
            attr = ow + cw
            row = {
                "officials": _i(pool.get("officials")),
                "clerks": _i(pool.get("clerks")),
                "officials_wealth": ow,
                "clerks_wealth": cw,
                "attributed_total": attr,
                "pool_wealth": _i(pool.get("wealth")),
                "coverage": (round(attr / float(pool.get("wealth") or 1), 4)
                             if _i(pool.get("wealth")) > 0 else None),
                "officials_wealth_share": (round(ow / float(attr), 4) if attr > 0 else None),
                "clerks_wealth_share": (round(cw / float(attr), 4) if attr > 0 else None),
                "officials_salary_arrears": _i(pool.get("officials_salary_arrears")),
                "clerks_pay_arrears": _i(pool.get("clerks_pay_arrears")),
                # 🟢 M35-C-1：职业（occupation）层——役人计数与雇钱记账（裁决 D3 字段形状）
                "runner_count": _i(pool.get("runner_count")),
                "occupation_income": {"runner": _i(pool.get("occupation_income_runner"))},
            }
            by_route[name] = row
            for k in tot:
                if k in row:
                    tot[k] += row[k]
            tot["occupation_income_runner"] += min(
                _i(pool.get("occupation_income_runner")),
                _i(row.get("occupation_income", {}).get("runner")))
        _sum = tot["officials_wealth"] + tot["clerks_wealth"]
        tot["officials_wealth_share"] = (round(tot["officials_wealth"] / float(_sum), 4)
                                         if _sum > 0 else None)
        tot["clerks_wealth_share"] = (round(tot["clerks_wealth"] / float(_sum), 4)
                                      if _sum > 0 else None)
        tot["occupation_income"] = {"runner": tot.pop("occupation_income_runner", 0)}
        return {"total": tot, "by_route": by_route}

    def calc_local_identities(self) -> dict:
        """M35-C **职业/身份映射**（只读派生；**不改军费算法**）：官／吏／士卒／乡兵／衙役。

        - `official` / `clerk`：来自 `官僚` POP 子池（`officials` / `clerks`）；
        - `soldier` / `militia`：来自 `army_units`（`tier == "乡兵"` → militia，其余 → soldier）；
          **只映射、不改军费**（军费仍按 `calc_army_cash` 现行口径）；
        - `runner`：**接口留白**——衙役（弓手/手力）尚未建模，读 `prefectures[路].get("runners", 0)`
          （AI/事件可填；不新增 POP、不改人口真账）；`runner_pay` 收款方暂挂 `兵`（后续脱离）。
        """
        by_route = {}
        for name, p in self.prefectures.items():
            if not isinstance(p, dict):
                continue
            pool = (p.get("pops") or {}).get("官僚")
            pool = pool if isinstance(pool, dict) else {}
            _rc = int(pool.get("runner_count", 0) or 0)
            if _rc <= 0:
                _rc = int(p.get("runners", 0) or 0)      # 兼容：旧档/测试直写路级 `runners`
            by_route[name] = {
                "official": int(pool.get("officials", 0) or 0),
                "clerk": int(pool.get("clerks", 0) or 0),
                "soldier": 0, "militia": 0,
                "runner": _rc,
                # 🟢 M35-C-1：役人雇钱记账层（累计）与身份欠给（挂官僚桶）
                "runner_income": int(pool.get("occupation_income_runner", 0) or 0),
                "soldiers_arrears": 0, "runners_pay_arrears": 0, "militia_pay_arrears": 0,
            }
        for u in getattr(self, "army_units", []) or []:
            row = by_route.get(getattr(u, "station", None))
            if row is None:
                continue
            n = int(getattr(u, "troops", 0) or 0)
            if str(getattr(u, "tier", "")) == "乡兵":
                row["militia"] += n
            else:
                row["soldier"] += n
        for name, row in by_route.items():
            pool_b = ((self.prefectures.get(name) or {}).get("pops") or {}).get("兵")
            if isinstance(pool_b, dict):
                row["soldiers_arrears"] = int(pool_b.get("soldiers_arrears", 0) or 0)
                row["militia_pay_arrears"] = int(pool_b.get("militia_pay_arrears", 0) or 0)
            pool_g = ((self.prefectures.get(name) or {}).get("pops") or {}).get("官僚")
            if isinstance(pool_g, dict):
                # 🟢 M35-C-1：役人欠给挂官僚桶；兵侧字段为**旧位兼容**（迁移前档仍可读）
                row["runners_pay_arrears"] = int(pool_g.get("runners_pay_arrears", 0) or 0)
                if row["runners_pay_arrears"] <= 0 and isinstance(pool_b, dict):
                    row["runners_pay_arrears"] = int(pool_b.get("runners_pay_arrears", 0) or 0)
        tot = {k: sum(r[k] for r in by_route.values())
               for k in ("official", "clerk", "soldier", "militia", "runner", "runner_income",
                         "soldiers_arrears", "runners_pay_arrears", "militia_pay_arrears")}
        return {"total": tot, "by_route": by_route}

    def population_breakdown(self) -> dict:
        """M35-C-1 **人口口径分解**（只读；裁决 D1 甲）：六桶 size ＋ occupation ＋ 流民。

        · `pop_classes`：六桶 size（**不含** occupation，也不含隐户/役人）；
        · `occupations`：职业人口（`runner_count`，不进任何桶 size）；
        · `in_registry_total` ＝ Σ六桶 size ＋ Σoccupation（不含流民）；
        · `refugees`／`population_field`：流民与 `state.population`（后者含流民，用于对账）。
        """
        pop_classes = {}
        occupations = {"runner": 0}
        for p in self.prefectures.values():
            if not isinstance(p, dict):
                continue
            for cls, pool in (p.get("pops") or {}).items():
                if isinstance(pool, dict):
                    pop_classes[cls] = pop_classes.get(cls, 0) + int(pool.get("size", 0) or 0)
            guan = (p.get("pops") or {}).get("官僚")
            if isinstance(guan, dict):
                _rc = int(guan.get("runner_count", 0) or 0)
                if _rc <= 0:
                    _rc = int(p.get("runners", 0) or 0)      # 旧位兼容
                occupations["runner"] += _rc
        _size_total = sum(pop_classes.values())
        _occ_total = sum(occupations.values())
        return {"pop_classes": pop_classes,
                "occupations": occupations,
                "size_total": _size_total,
                "occupation_total": _occ_total,
                "in_registry_total": _size_total + _occ_total,
                "refugees": int(getattr(self, "refugee_count", 0) or 0),
                "population_field": int(getattr(self, "population", 0) or 0)}

    def rumor_tier(self) -> dict:
        """M35-D **民间传闻档位**（只读·档位化观察结果；**不生成剧情/事件**）。

        档位（裁决）：`0 无异常｜1 钱粮迟滞｜2 吏胥鼓噪｜3 州县积欠｜4 地方失控风险`
        输入一律为**可观察量**（**不暴露真账**）：欠给连续月数、身份压力、吏胥把持度、本路粮价、动乱。
        ⇒ 档位表示"民间/中央**听到了什么**"，**不是**"已查实腐败"；查实须靠监察（P3 保真度）。

        规则（初值·待校准，越严重档位越高、单调）：
          L1 钱粮迟滞：本路粮价 ≥ `RUMOR_PRICE_L1` **或** 存在欠给（≥1 月）
          L2 吏胥鼓噪：把持度 ≥ `RUMOR_GRIP_L2` **或** 身份压力 ≥ `RUMOR_PRESSURE_L2`
          L3 州县积欠：欠给月数 ≥ `RUMOR_MONTHS_L3` **或** 压力 ≥ `RUMOR_PRESSURE_L3`
          L4 地方失控：动乱 ≥ `RUMOR_UNREST_L4` **或**（月数 ≥ `RUMOR_MONTHS_L4` 且压力 ≥ `RUMOR_PRESSURE_L4`）
        返回 `{"tier","label","signals","by_route"}`（全国＝逐路最高）。
        """
        from content.data import (RUMOR_GRIP_L2, RUMOR_LABELS, RUMOR_MONTHS_L3,
                                  RUMOR_MONTHS_L4, RUMOR_PRESSURE_L2, RUMOR_PRESSURE_L3,
                                  RUMOR_PRESSURE_L4, RUMOR_PRICE_L1, RUMOR_UNREST_L4)
        try:
            pr = self.identity_pressures().get("by_route", {})
        except Exception:                    # noqa: BLE001 — 读数失败不得整体崩
            pr = {}

        def _f(v):
            try:
                return float(v or 0)
            except (TypeError, ValueError):
                return 0.0

        by_route = {}
        for name, p in self.prefectures.items():
            if not isinstance(p, dict):
                continue
            months = p.get("arrears_months") if isinstance(p.get("arrears_months"), dict) else {}
            _months = max([_f(v) for v in months.values()] or [0.0])
            _press = max([_f((pr.get(name) or {}).get(k)) for k in
                          ("clerk_pressure", "runner_pressure", "official_pressure")] or [0.0])
            _grip = _f((p.get("clerks_detail") or {}).get("grip", 0.0))
            _price = _f(p.get("grain_price", getattr(self, "grain_price", 1.0)))
            _unrest = _f(p.get("unrest", 0.0))
            tier = 0
            if _price >= RUMOR_PRICE_L1 or _months >= 1.0:
                tier = 1
            if _grip >= RUMOR_GRIP_L2 or _press >= RUMOR_PRESSURE_L2:
                tier = max(tier, 2)
            if _months >= RUMOR_MONTHS_L3 or _press >= RUMOR_PRESSURE_L3:
                tier = max(tier, 3)
            if _unrest >= RUMOR_UNREST_L4 or (_months >= RUMOR_MONTHS_L4
                                              and _press >= RUMOR_PRESSURE_L4):
                tier = max(tier, 4)
            by_route[name] = {
                "tier": tier, "label": RUMOR_LABELS.get(tier, "无异常"),
                "signals": {"months": round(_months, 2), "pressure": round(_press, 2),
                            "grip": round(_grip, 4), "grain_price": round(_price, 4),
                            "unrest": round(_unrest, 2)},
            }
        top = max([r["tier"] for r in by_route.values()] or [0])
        return {"tier": top, "label": RUMOR_LABELS.get(top, "无异常"),
                "signals": {"routes_tier_ge1": sum(1 for r in by_route.values() if r["tier"] >= 1),
                            "routes_tier_ge2": sum(1 for r in by_route.values() if r["tier"] >= 2),
                            "routes_tier_ge3": sum(1 for r in by_route.values() if r["tier"] >= 3),
                            "routes_tier_ge4": sum(1 for r in by_route.values() if r["tier"] >= 4)},
                "by_route": by_route}

    def fiscal_visibility(self) -> dict:
        """M35-D 财政**可见度接口**（只读；三层，**不做**完整调查系统）。

        · `real`     **真账**：真值（田赋应征/实收/三分、地方支用、欠给、附加收入）；
        · `official` **官府账**：真账 ＋ P2 做账掩护（`tax_loss_readout` 损耗科目）；
        · `rumor`    **风闻**：定档/区间（P3 发现链 `discovery_readout`）。
        三层**同为只读投影**，不新建账本、不改钱粮。
        """
        st = self.statistics or {}
        real = {
            "land_assessed": int(st.get("land_tax_assessed", 0) or 0),
            "land_collected": int(st.get("land_tax_collected", 0) or 0),
            "land_central": int(st.get("land_tax_central", 0) or 0),
            "land_local": int(st.get("land_tax_local", 0) or 0),
            "land_diverted": int(st.get("land_tax_diverted", 0) or 0),
            "local_extra_income": int(st.get("local_extra_income", 0) or 0),
            "local_expense_paid": int(st.get("local_expense_paid", 0) or 0),
            "local_arrears": int(st.get("local_arrears", 0) or 0),
        }
        try:
            loss = self.tax_loss_readout() or {}
        except Exception:                     # noqa: BLE001 — 读数不得因单点失败整体崩
            loss = {}
        official = {"land_central": real["land_central"],
                    "loss_report": loss.get("report", {}),
                    "loss_status": loss.get("status", "正常")}
        try:
            _disc = dict(_discovery_readout(self) or {})
        except Exception:                     # noqa: BLE001
            _disc = {}
        # 🟢 M35-D：rumor 层**档位化**（0–4；"听到什么"而非"已查实"）；P3 发现链原文入 `discovery`
        rumor = dict(self.rumor_tier())
        rumor["discovery"] = _disc
        return {"real": real, "official": official, "rumor": rumor}

    def identity_pressures(self) -> dict:
        """M35-2-B **身份压力接口**（只读状态；**不自动腐败、不生成剧本事件**）。

        公式（各项先归一到 0–1，再加权，最后 ×100，常量见 content）：
          clerk_pressure    = 100·clamp(w_amount·金额占比 ＋ w_months·月数占比
                                        ＋ w_grip·吏胥把持度 ＋ w_div·侵渔率)
          official_pressure = 100·clamp(w_amount·金额占比 ＋ w_months·月数占比
                                        ＋ w_underpay·(1 − 俸禄实付率) ＋ w_div·侵渔率)
        其中：金额占比 ＝ 身份欠给**存量** ÷ 该科目当月**现实应支**（封顶 1）；
              月数占比 ＝ 连续欠给**月数** ÷ `LOCAL_PRESSURE_MONTHS_REF`（封顶 1）。
        ⇒ **金额与时间分离贡献**：同为 1 万贯，欠 1 月与欠 24 月压力不同（M35-2-A）。
        仅输出状态与构成，供 AI/事件层自行决定如何反应。
        """
        from content.data import (LOCAL_PRESSURE_MONTHS_REF, LOCAL_PRESSURE_W_AMOUNT,
                                  LOCAL_PRESSURE_W_DIV, LOCAL_PRESSURE_W_GRIP,
                                  LOCAL_PRESSURE_W_MONTHS, LOCAL_PRESSURE_W_UNDERPAY)
        try:
            plan = self.calc_local_expenditure().get("by_route", {})
        except Exception:                    # noqa: BLE001 — 压力读数不得因单点失败整体崩
            plan = {}

        def _clamp01(v):
            return max(0.0, min(1.0, float(v)))

        def _f(v):
            try:
                return float(v or 0)
            except (TypeError, ValueError):
                return 0.0

        by_route = {}
        for name, p in self.prefectures.items():
            if not isinstance(p, dict):
                continue
            pops = p.get("pops") if isinstance(p.get("pops"), dict) else {}
            guan = pops.get("官僚") if isinstance(pops.get("官僚"), dict) else {}
            bing = pops.get("兵") if isinstance(pops.get("兵"), dict) else {}
            months = p.get("arrears_months") if isinstance(p.get("arrears_months"), dict) else {}
            due = plan.get(name) or {}
            grip = _clamp01(_f((p.get("clerks_detail") or {}).get("grip", 0.0)))
            try:
                pay_ratio = _clamp01(_f(self.calc_pay_ratio(name)))
            except Exception:                # noqa: BLE001
                pay_ratio = 1.0
            try:
                div = _clamp01(_f(self.finance_split(name)[2]))
            except Exception:                # noqa: BLE001
                div = 0.0

            def _ratio(amount, due_amt, months_v):
                return (_clamp01(amount / due_amt) if due_amt > 0 else 0.0,
                        _clamp01(_f(months_v) / float(LOCAL_PRESSURE_MONTHS_REF)))

            _a, _m = _ratio(int(guan.get("officials_salary_arrears", 0) or 0),
                            _f(due.get("official_salary", 0)), months.get("official_salary", 0))
            official_pressure = 100.0 * _clamp01(
                LOCAL_PRESSURE_W_AMOUNT * _a + LOCAL_PRESSURE_W_MONTHS * _m
                + LOCAL_PRESSURE_W_UNDERPAY * (1.0 - pay_ratio) + LOCAL_PRESSURE_W_DIV * div)
            _a2, _m2 = _ratio(int(guan.get("clerks_pay_arrears", 0) or 0),
                              _f(due.get("clerk_pay", 0)), months.get("clerk_pay", 0))
            clerk_pressure = 100.0 * _clamp01(
                LOCAL_PRESSURE_W_AMOUNT * _a2 + LOCAL_PRESSURE_W_MONTHS * _m2
                + LOCAL_PRESSURE_W_GRIP * grip + LOCAL_PRESSURE_W_DIV * div)
            _a3, _m3 = _ratio(int((guan.get("runners_pay_arrears", 0)
                                   or bing.get("runners_pay_arrears", 0) or 0)),
                              _f(due.get("runner_pay", 0)), months.get("runner_pay", 0))
            runner_pressure = 100.0 * _clamp01(
                LOCAL_PRESSURE_W_AMOUNT * _a3 + LOCAL_PRESSURE_W_MONTHS * _m3
                + LOCAL_PRESSURE_W_GRIP * grip + LOCAL_PRESSURE_W_DIV * div)
            by_route[name] = {
                "clerk_pressure": round(clerk_pressure, 2),
                "official_pressure": round(official_pressure, 2),
                "runner_pressure": round(runner_pressure, 2),
                "inputs": {"clerk_arrears": int(guan.get("clerks_pay_arrears", 0) or 0),
                           "official_arrears": int(guan.get("officials_salary_arrears", 0) or 0),
                           "runner_arrears": int(guan.get("runners_pay_arrears", 0)
                                                 or bing.get("runners_pay_arrears", 0) or 0),
                           "clerk_months": round(_f(months.get("clerk_pay", 0)), 2),
                           "official_months": round(_f(months.get("official_salary", 0)), 2),
                           "runner_months": round(_f(months.get("runner_pay", 0)), 2),
                           "grip": round(grip, 4), "pay_ratio": round(pay_ratio, 4),
                           "div": round(div, 4)},
            }
        if not by_route:
            return {"total": {}, "by_route": {}}
        tot = {
            "clerk_pressure_max": max(r["clerk_pressure"] for r in by_route.values()),
            "official_pressure_max": max(r["official_pressure"] for r in by_route.values()),
            "runner_pressure_max": max(r["runner_pressure"] for r in by_route.values()),
            "routes_with_clerk_arrears": sum(1 for r in by_route.values()
                                             if r["inputs"]["clerk_arrears"] > 0),
            "routes_with_official_arrears": sum(1 for r in by_route.values()
                                                if r["inputs"]["official_arrears"] > 0),
            "max_arrears_months": max(
                max(r["inputs"]["clerk_months"], r["inputs"]["official_months"],
                    r["inputs"]["runner_months"]) for r in by_route.values()),
        }
        return {"total": tot, "by_route": by_route}

    def fiscal_visibility_view(self, viewer: str = "player", oversight=None,
                               secret: bool = False) -> dict:
        """M35-2-C 财政可见度**读取规则**（只完善规则，**不开放玩家读真账**）。

        - `viewer="player"`（默认）→ `official` ＋ `rumor`（**不含 real**）；
        - `viewer="audit"` → 同上；**仅当**监察力度 ≥ `FIN_ANOMALY_OVERSIGHT_LINE`
          或**密查**（`secret=True`）时，追加 `real`（即"查得实情"）；
        - `viewer="system"／"ai"` → 三层全给（系统/AI 内部，不面向玩家）。
        返回结构与 `fiscal_visibility()` 相同，但**只含被允许的层**；
        **真实层入口仅 `fiscal_visibility()`（内部）**——为审计/巡按/调查系统预留接口。
        """
        from content.data import (FIN_ANOMALY_OVERSIGHT_LINE, FIN_VIS_GRANULARITY,
                                  FIN_VIS_LAYERS_AUDIT, FIN_VIS_LAYERS_AUDIT_TRUTH,
                                  FIN_VIS_LAYERS_PLAYER, FIN_VIS_LAYERS_SYSTEM)
        raw = self.fiscal_visibility()
        v = str(viewer or "player").lower()
        if v in ("system", "ai", "truth"):
            layers = FIN_VIS_LAYERS_SYSTEM
        elif v in ("audit", "inspector", "censor"):
            _ov = oversight
            if _ov is None:
                _ov = float(getattr(self, "oversight", 0.0) or 0.0)
            layers = (FIN_VIS_LAYERS_AUDIT_TRUTH
                      if (secret or float(_ov or 0.0) >= FIN_ANOMALY_OVERSIGHT_LINE)
                      else FIN_VIS_LAYERS_AUDIT)
        else:
            # 🟢 M35-D：`player`（玩家）／`official`（地方官）／`court`（中央）／未知 ⇒ **不含 real**
            layers = FIN_VIS_LAYERS_PLAYER
        out = {k: raw.get(k, {}) for k in layers}
        out["viewer"] = v
        out["layers"] = list(layers)
        gran = FIN_VIS_GRANULARITY.get(v, "route")
        out["granularity"] = gran
        if gran == "national":
            # 信息差：中央只见**汇总**（不给逐路明细与信号构成）
            for _k in ("official", "rumor"):
                _sec = out.get(_k)
                if isinstance(_sec, dict):
                    _sec.pop("by_route", None)
                    if _k == "rumor":
                        _sec.pop("signals", None)
        return out

    def arrears_months_summary(self) -> dict:
        """M35-2-A 欠给**时间**汇总（只读；与金额分离）：各科目 全国最大／均值／最长欠给路。

        数据源＝`prefectures[路]["arrears_months"]`（连续欠给月数，按月累进／恢复递减，
        身份欠给清偿则清零）。供 AI 判断"慢性程度"（1 月 vs 24 月风险不同）。
        """
        kinds = ("official_salary", "clerk_pay", "runner_pay", "public_supply")
        rows = {}
        for name, p in self.prefectures.items():
            if not isinstance(p, dict):
                continue
            m = p.get("arrears_months")
            if isinstance(m, dict):
                rows[name] = m
        out = {}
        for k in kinds:
            vals = [float((rows.get(n) or {}).get(k, 0.0) or 0.0) for n in rows]
            if not vals:
                continue
            _mx = max(vals)
            _arg = max(rows, key=lambda n: float((rows.get(n) or {}).get(k, 0.0) or 0.0))
            out[k] = {"max": round(_mx, 2),
                      "mean": round(sum(vals) / float(len(vals)), 2),
                      "routes_over_3": sum(1 for v in vals if v >= 3.0),
                      "longest_route": _arg if _mx > 0 else None}
        return out

    def arrears_recovery_capacity(self) -> dict:
        """M35-3 **补发能力读数**（只读；供 AI 决策：是否拨款／减税／整顿）。

        逐路给出：
          · `coffer_surplus`   路级府库可动用额（＝余额 − `LOCAL_REPAY_KEEP_MONTHS` 个月现实应支）；
          · `treasury_available` 中央可拨额（＝国库 − `ARREARS_KEEP_TREASURY` 应急线）；
          · `arrears_by_kind` 各科目欠给**规模**（身份字段／池 `欠给`）；
          · `priority` 建议补发顺序（**＝D7′ 刚性等级**，非"公平分配"）；
          · `months` 各科目连续欠给月数；`pressure` 同路压力（供权衡）。
        `total`：可补发合计、欠给规模合计、超 3 月路数（AI 的"要不要动"依据）。
        """
        from content.data import (ARREARS_KEEP_TREASURY, LOCAL_EXP_PAY_TIERS,
                                  LOCAL_REPAY_KEEP_MONTHS)
        try:
            plan = self.calc_local_expenditure().get("by_route", {})
        except Exception:                    # noqa: BLE001
            plan = {}
        try:
            pressures = self.identity_pressures().get("by_route", {})
        except Exception:                    # noqa: BLE001
            pressures = {}
        _treasury_avail = max(0, int(getattr(self, "treasury", 0) or 0)
                              - int(ARREARS_KEEP_TREASURY))
        priority = [k for _t in LOCAL_EXP_PAY_TIERS for k in _t]
        by_route = {}
        for name, p in self.prefectures.items():
            if not isinstance(p, dict):
                continue
            pops = p.get("pops") if isinstance(p.get("pops"), dict) else {}
            guan = pops.get("官僚") if isinstance(pops.get("官僚"), dict) else {}
            bing = pops.get("兵") if isinstance(pops.get("兵"), dict) else {}
            _due_eff = float((plan.get(name) or {}).get("due_eff", 0) or 0)
            _keep = int(_due_eff * float(LOCAL_REPAY_KEEP_MONTHS))
            by_route[name] = {
                "coffer": int(p.get("local_treasury", 0) or 0),
                "coffer_surplus": max(0, int(p.get("local_treasury", 0) or 0) - _keep),
                "treasury_available": _treasury_avail,
                "arrears_by_kind": {
                    "official_salary": int(guan.get("officials_salary_arrears", 0) or 0),
                    "clerk_pay": int(guan.get("clerks_pay_arrears", 0) or 0),
                    "runner_pay": int(guan.get("runners_pay_arrears", 0)
                                      or bing.get("runners_pay_arrears", 0) or 0),
                    "public_supply": (int((pops.get("工匠") or {}).get("欠给", 0) or 0)
                                      + int((pops.get("商人") or {}).get("欠给", 0) or 0)),
                },
                "arrears_total": int(guan.get("欠给", 0) or 0) + int(bing.get("欠给", 0) or 0)
                + int((pops.get("工匠") or {}).get("欠给", 0) or 0)
                + int((pops.get("商人") or {}).get("欠给", 0) or 0),
                "months": {k: round(float((p.get("arrears_months") or {}).get(k, 0.0) or 0.0), 2)
                           for k in ("official_salary", "clerk_pay", "runner_pay",
                                     "public_supply")},
                "pressure": {k: (pressures.get(name) or {}).get(k)
                             for k in ("clerk_pressure", "official_pressure",
                                       "runner_pressure")},
                "priority": list(priority),
            }
        if not by_route:
            return {"total": {}, "by_route": {}}
        tot = {
            "treasury_available": _treasury_avail,
            "coffer_surplus_total": sum(r["coffer_surplus"] for r in by_route.values()),
            "arrears_total": sum(r["arrears_total"] for r in by_route.values()),
            "recoverable_total": (sum(r["coffer_surplus"] for r in by_route.values())
                                  + _treasury_avail),
            "routes_with_arrears": sum(1 for r in by_route.values() if r["arrears_total"] > 0),
            "routes_over_3_months": sum(
                1 for r in by_route.values()
                if max(r["months"].values() or [0]) >= 3.0),
            "priority": list(priority),
        }
        return {"total": tot, "by_route": by_route}

    def inspection_backlash_readout(self) -> dict:
        """P3-4 **巡按反向观察量**读数（只读）：监察的代价（扰民/吏怨），供 AI 权衡"还查不查"。

        来源：`statistics["inspection_*"]` 计数（由 `audit_case.resolve_audit` 写入）
        ＋ 逐路 `clerks_detail.grievance` 现值。**只读**；不含任何财政量。
        """
        st = self.statistics or {}

        def _f(v):
            try:
                return float(v or 0)
            except (TypeError, ValueError):
                return 0.0

        by_route = {}
        for name, p in self.prefectures.items():
            if not isinstance(p, dict):
                continue
            _cd = p.get("clerks_detail") if isinstance(p.get("clerks_detail"), dict) else {}
            by_route[name] = {"grievance": round(_f(_cd.get("grievance")), 3),
                              "unrest": round(_f(p.get("unrest")), 2)}
        return {"actions": int(st.get("inspection_actions", 0) or 0),
                "grievance_added": round(_f(st.get("inspection_grievance_added")), 3),
                "unrest_added": round(_f(st.get("inspection_unrest_added")), 3),
                "by_route": by_route}

    def fiscal_gap_report(self, viewer: str = "player", oversight=None,
                          secret: bool = False) -> dict:
        """P3-3 **差额报表复核**（**只读接口**；**不进入月报**）。

        复核三类差额与两条恒等式（口径**单点复用** `audit_case.financial_evidence`，不另算）：
          ① **掩护虚增** ＝ Σ账面损耗 − Σ真侵渔（>0 ⇒ 多报损耗掩盖侵渔）；
          ② **未承认欠支** ＝ Σ真欠给（官方口径不记欠支 ⇒ 差额＝全额）；
          ③ **征收缺口** ＝ 应征 − 实收；并校验两条恒等式：
              `应征 ≡ 实收 ＋ 豁免欠税`、`实收 ≡ 上供 ＋ 留州 ＋ 侵渔`。

        **权限（信息差）**：`player`／`official`／`court` **只给账面侧**（不含 real 差额与逐路真账）；
        真账差额需 `inspector`（监察足额 `| oversight≥门限` **或** 密查）或 `ai`／`system`。
        纪律：只读；**不改** money／POP／欠给／压力／案卷；**不写月报**。
        """
        from content.data import FIN_ANOMALY_OVERSIGHT_LINE
        from core.audit_case import financial_evidence
        v = str(viewer or "player").lower()
        if v in ("ai", "system", "truth"):
            allow_real = True
        elif v in ("inspector", "audit", "censor"):
            _ov = oversight
            if _ov is None:
                _ov = float(getattr(self, "oversight", 0.0) or 0.0)
            allow_real = bool(secret) or float(_ov or 0.0) >= FIN_ANOMALY_OVERSIGHT_LINE
        else:
            allow_real = False

        st = self.statistics or {}
        by_route = {}
        for name in self.prefectures:
            try:
                ev = financial_evidence(self, name, include_real=True) or {}
            except Exception:                 # noqa: BLE001 — 单路失败不阻断复核
                continue
            if not ev.get("available"):
                continue
            _a = ev.get("local_arrears") or {}
            _g = ev.get("official_gap") or {}
            row = {"route": name,
                   # 账面侧（玩家/中央可见）
                   "loss_report_total": int(_g.get("loss_report_total", 0) or 0)}
            if allow_real:
                row.update({
                    "real_diverted": int(_g.get("real_diverted", 0) or 0),
                    "cover_overstatement": int(_g.get("cover_overstatement", 0) or 0),
                    "unacknowledged_arrears": int(_g.get("unacknowledged_arrears", 0) or 0),
                    "local_arrears": dict(_a),
                    "collection_gap": dict(_g.get("collection_gap") or {}),
                })
            by_route[name] = row

        out = {"viewer": v, "allow_real": allow_real, "by_route": by_route}
        # 全国合计（账面侧恒给；真账侧按权限）
        out["totals"] = {"loss_report_total": sum(r["loss_report_total"]
                                                  for r in by_route.values())}
        if allow_real:
            out["totals"].update({
                "real_diverted": sum(r.get("real_diverted", 0) for r in by_route.values()),
                "cover_overstatement": sum(r.get("cover_overstatement", 0)
                                           for r in by_route.values()),
                "unacknowledged_arrears": sum(r.get("unacknowledged_arrears", 0)
                                              for r in by_route.values()),
            })
        # 恒等式复核（真账口径；仅有权者可见结果）
        _assessed = int(st.get("land_tax_assessed", 0) or 0)
        _collected = int(st.get("land_tax_collected", 0) or 0)
        _central = int(st.get("land_tax_central", 0) or 0)
        _local = int(st.get("land_tax_local", 0) or 0)
        _div = int(st.get("land_tax_diverted", 0) or 0)
        _checks = {
            "three_way_identity": (_central + _local + _div) == _collected,
            "collection_le_assessed": _collected <= _assessed,
            "assessed_minus_collected": _assessed - _collected,
        }
        out["identities"] = _checks if allow_real else {"note": "需监察权限（只读复核）"}
        return out

    def tax_loss_readout(self) -> dict:
        """账面损耗读数（P2）：`tax_loss_report` 累计 ＋ 份额 ＋ 分级状态（信息差一/二级）。

        - 一级（普通账面）：损耗可见（`report` 四类目＋total）；
        - 二级（监察能力高）：份额超常（≥ `FIN_LOSS_NORM×FIN_LOSS_ALERT_MULT`）
          且 `oversight ≥ FIN_ANOMALY_OVERSIGHT_LINE` → `status="耗损异常"`；
          超常但监察不足 → `"耗损偏重"`；否则 `"正常"`；
        - 三级（"侵渔金额"）由调查（P3）揭示，本读数**不越级**。
        """
        rep = dict(self.statistics.get("tax_loss_report") or {})
        for _k in ("运输损耗", "地方耗费", "火耗", "杂费", "total"):
            rep.setdefault(_k, 0)
        total = int(rep.get("total", 0) or 0)
        assessed = int(self.statistics.get("land_tax_assessed", 0) or 0)
        share = (total / assessed) if assessed > 0 else 0.0
        status = "正常"
        if total > 0 and share >= FIN_LOSS_NORM * FIN_LOSS_ALERT_MULT:
            oversight = float(getattr(self, "oversight", 0.0) or 0.0)
            status = ("耗损异常" if oversight >= FIN_ANOMALY_OVERSIGHT_LINE
                      else "耗损偏重")
        return {"report": rep, "total": total, "share": round(share, 4),
                "status": status}

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
        役钱税基＝**应役丁**（B1b）= 农的**丁** × (1 − 佃农占比)；
        `士绅`（形势户）、`官僚`（官户）、`兵` 免役；佃农（客户）**无国税、无摊派**（负担在地租里）。
        冗官膨胀（科举/恩荫/宗室入官）把人口从 `农` 抽走 → 应役丁下降；
        官户另行纳**助役钱**（俸禄总额 5%），但远不足以抵消其俸禄本身。

        返回：纳税人口（**应役丁**）、免役人口与占比、农总口/佃农口（对照读数）、
        役钱与助役钱实收、冗官数。
        """
        from core.domains.administration import officialdom as _od
        from core.foundation.ledger.pop_structure import service_ding_total

        pops = {}
        for p in self.prefectures.values():
            for k, v in (p.get("pops") or {}).items():
                pops[k] = pops.get(k, 0) + int(v.get("size", 0) or 0)
        taxable = service_ding_total(self)          # 应役丁（B1b；原为农 POP 全额）
        farm_pop = pops.get("农", 0)
        tenant_pop = sum(int((p["pops"]["农"].get("佃农", 0) or 0))
                         for p in self.prefectures.values())
        exempt = pops.get("士绅", 0) + pops.get("官僚", 0) + pops.get("兵", 0)
        total = sum(pops.values()) or 1
        _od.ensure_quota(self)      # 定员是惰性初始化的**岗位**存量（幂等），其余全为派生
        t = _od.totals(self)
        return {
            "taxable_pop": taxable,
            "farm_pop": farm_pop,          # 农总口（对照；含佃农）
            "tenant_pop": tenant_pop,      # 佃农口（免役；B1b 新增）
            "exempt_pop": exempt,
            "exempt_share": round(exempt / total, 6),
            "poll_tax": int((self.tax_breakdown or {}).get("poll", 0)),
            "official_service_tax": int((self.tax_breakdown or {}).get("official_service", 0)),
            "taxable_share": round(taxable / total, 6),
            "officials": t["officials"],
            "redundant_officials": t["redundant"],
            "awaiting_posts": t["waiting"],
        }

    # ---- 官俸（Σ官×人均；官额与子池计价一律取自 POP，见 core/domains/administration/officialdom.py）----
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
          - 盐产区产能：各路七维物资初值 yields["盐"] 之和（工程/市舶可改 yields 或 resources 而变）
          - price_factor：产能/基准产能比越紧俏价越高，夹在 [SALT_PRICE_FLOOR, SALT_PRICE_CEIL]
          - 总人口缩放：食盐人口增减直接线性反映到盐课（开局缩放=1）
          - arrival：到库率（灾荒/治理低则折损）
        不再使用写死的月额常量。
        """
        salt_capacity = 0.0
        total_pop = 0.0
        for p in self.prefectures.values():
            salt_capacity += float(p.get("yields", {}).get("盐", 0))
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
