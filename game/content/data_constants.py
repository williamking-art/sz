# -*- coding: utf-8 -*-
"""宋祚 · 游戏内容数据 —— 公式常量 / 数值工具 / 档位契约 / 脱敏映射（单一权威源）

从 content/data.py 拆出（零行为变更，只搬代码）。
"""

# ============================================================
# 开局时间
# ============================================================
START_YEAR = 1101
START_MONTH = 1
ERA_NAME_START = "建中靖国"
# 强制收束年：无论皇帝健康如何，到达该年后游戏必须走向结局，避免无限拖局
END_YEAR = 1135

# ============================================================
# 皇威系统
# ============================================================
PRESTIGE_START = 55
PRESTIGE_MAX = 100
PRESTIGE_MIN = 0
PRESTIGE_MONTHLY_CAP = 8          # 单月变动上限
PRESTIGE_MAJOR_EVENT_CAP = 15     # 大事件突破上限

PRESTIGE_LEVELS = {
    "扫地":  (0,  25, 0.4),
    "不振":  (26, 40, 0.7),
    "平平":  (41, 60, 1.0),
    "尚隆":  (61, 80, 1.3),
    "鼎盛":  (81, 100, 1.6),
}

def get_prestige_level(value: int) -> tuple[str, float, float]:
    """返回 (等级名, 乘数W, 威权指数)"""
    authority_map = {"扫地": 0.2, "不振": 0.4, "平平": 0.5, "尚隆": 0.6, "鼎盛": 0.7}
    for name, (lo, hi, w) in PRESTIGE_LEVELS.items():
        if lo <= value <= hi:
            return (name, w, authority_map[name])
    if value <= 25:
        return ("扫地", 0.4, 0.2)
    return ("鼎盛", 1.6, 0.7)

# ============================================================
# 皇帝个人
# ============================================================
EMPEROR_HEALTH_START = 75
EMPEROR_HEALTH_MAX = 100
EMPEROR_ART_START = 85       # 艺术造诣
EMPEROR_TAOISM_START = 25    # 崇道倾向
EMPEROR_PLEASURE_START = 30  # 享乐倾向


# 执行率公式常量
S_BASE = 0.45                  # 圣旨基础成功率
S_SUPPORT_WEIGHT = 0.08        # 派系净支持权重
S_CONFLICT_WEIGHT = 0.15       # 党争修正权重
S_SECRET_BASE = 0.30           # 密旨基础成功率
S_SECRET_LOYALTY_WEIGHT = 0.7  # 密旨忠诚度权重
S_DIRECT_BONUS = 0.10          # 御笔加成
S_ZHONGZHI_SUPPORT_WEIGHT = 0.04  # 中旨：净支持对执行率的影响权重（2026-09-19 由实现里的硬编码单点化）
S_DIRECT_PENALTY = 0.0         # 已停用：狼来了惩罚取消（原 -0.15，现 0）
E_MIN = 0.05
E_MAX = 0.95

# ============================================================
# 到账率系统
# ============================================================
ARRIVAL_BASE = 0.45            # 史实难度基准
ARRIVAL_AUDIT_WEIGHT = 0.30
ARRIVAL_AUTHORITY_WEIGHT = 0.15
ARRIVAL_DIVERSION_WEIGHT = 0.25
ARRIVAL_MIN = 0.05
ARRIVAL_MAX = 0.95

# ============================================================
# 经济/财政
# ============================================================
TREASURY_START = 5_000_000      # 国库初始 (贯) — 约 500 万贯活钱
INNER_TREASURY_START = 1_000_000  # 内帑/内藏库初始 (贯) — 皇帝私库，与国库分理
ANNUAL_TAX_BASE = 80_000_000    # 年应征基准 ~8000万贯（含田赋60%+工商30%+丁口10%）

# =================================================================
# 经济全浮动重构（二税折色 + 太仓本色 + 七维物资 + 工程制作）
# =================================================================
# 朝廷经常性货币开支派生基准（可见支出，单位贯/月）。
# 原写死的 MONTHLY_EXPENDITURE_BASE(210万) 已废除，改由本基准派生；
# 营造/赏赐等原常项不再写死，改由工程系统 + 派生公式给出，避免破坏既有结算。
MONTHLY_EXP_CIVIL_BASE = 880_000    # 朝廷经常性货币开支派生基准（营造/赏赐/诸司常费，税基 POP 化后按收入规模校准）

# 二税折色：各路 monthly_tax_income_i = tax_base_i × arrival × tax_coeff × ROUTE_MULT_i × COLOR_RATE
# tax_base_i 取现有 monthly_tax 初值（单位贯/月）作锚。审查锚校准：20 路 Σmonthly_tax
# ≈5_480_000 贯/月（旧 12 路口径 ≈4_100_000；ANNUAL_TAX_BASE=8000 万为年度名义锚），
# 折色 40% 后实入国库 ≈2.19M 贯/月量级，与月支锚（PAY_CASH_BASE 等）构成收支平衡基准。
TAX_COLOR_RATE = 0.40           # 折色率（田赋中折银的比例：40% 折银入国库、60% 本色入太仓；税基 POP 化后校准）
ROUTE_MULT_DEFAULT = 1.0        # 路级乘数默认（个别路可微调，如京畿加征/边镇减免），见 PREFECTURE_INFO.route_mult

# 田赋本色率：原 LAND_TAX_RATE=0.15 现拆为「本色率+综合率」两层，保留兼容。
LAND_TAX_RATE = 0.15            # 兼容旧值（综合田赋率，结算沿用）
LAND_TAX_RATE_BENEFIT = 0.10    # 本色率：太仓月入 = Σ各路 grain_yield_i/12 × 本色率 × 到账 × 丰歉 × 隐漏 × 水利
LAND_TAX_RATE_BASE = 0.10       # 同 LAND_TAX_RATE_BENEFIT 别名（口径文档要求）

# 兵员单位：ARMY_INIT 仅保留质量参数；兵额(人)改由各路 garrisons 派生并汇总（详见 GARRISON_DERIVE）。
# 人均常量（单位已是真实兵/官/吏，消耗=石或贯 per 月）：
SOLDIER_GRAIN_PER_MONTH = 2.0   # 每兵月耗粮（石）
SOLDIER_PAY_PER_MONTH = 0.5     # 每兵月饷（贯）
OFFICIAL_PAY_PER_MONTH = 30      # 每官月俸折色（贯）
OFFICIAL_GRAIN_PER_MONTH = 15    # 每官月禄米（石）
CLERK_PAY_PER_MONTH = 2.4        # 每吏月俸折色（贯）——**历史↔游戏性取中**：
#   史实吏禄极薄（2.0 贯 → 实得 ≈3.5 贯/月，仅及家庭口粮一半，是陋规的制度性根源）；
#   游戏性要求"先定编、再提薪"的公务员化路线走得通。取中 2.4（实得 ≈3.9 贯/月，
#   仍在 7.2 贯生计线之下 → **陋规与吏怨依然存在**，压力保留）；玩家经 `clerk_pay_mult`
#   参数可继续推到公务员制取值（见 core/institution.py）。
CLERK_GRAIN_PER_MONTH = 1.5      # 每吏月禄米（石）
CLERK_PER_OFFICIAL = 8           # 吏数 = 官数 × 8（旧档迁移基准；§16 吏制将改为编制驱动）
# ---- 官僚 POP 身份子池（宋代官制设计 §13.3/§13.4）----
# 官（officials）内部再分三池，俸禄按池计价；吏（clerks）单列，不参与子池。
# 不变量：size == officials + clerks；officials == on_post + waiting + sinecure。
WAITING_PAY_RATIO = 0.35         # 待阙（守选无差遣）**取中**：史实待阙多无俸（=0），
#                                但游戏需要"待阙堆积"有财政成本（否则冗官不痛）。取中 0.35。
SINECURE_PAY_RATIO = 0.4         # 祠禄（宫观官）折俸——史实约半俸偏低，取中 0.4
OFFICIAL_SUB_KEYS = ("officials", "clerks", "on_post", "waiting", "sinecure")
# ---- 官制结算（阶段 C-3，见宋代官制设计 §七/§13.5）----
ROUTE_POST_QUOTA = 1350          # 每路差遣定员（知州/通判/幕职/县令/监当等，含胥吏外之职官）
WAITING_SINECURE_MULT = 0.5      # 待阙超过「定员 × 此倍数」→ 超额转祠禄（宫观官，仍食折俸）
OFFICIAL_RETIRE_RATE_YEAR = 0.03  # 在岗官年退出率（致仕/死亡/罢黜合计）：退出者回**士绅**
RANK_UP_PER_YEAR = 0.006         # 磨勘：品阶上浮带来的人均俸禄年增幅（每年正月一次）
YINBEN_PER_JIAOSI = 0.004        # 恩荫：每 3 年郊祀荫补 = 士绅人口 × 此比例（随皇威缩放）
YINBEN_PRESTIGE_REF = 55.0       # 恩荫的皇威基准（皇威越高，荫补越多）
CLAN_OFFICE_RATIO = 0.02         # 宗室年入官比例（占宗室人口；随宗室复利增长）
CLAN_GROWTH_ANNUAL = 0.03        # 宗室人口年复利（3%/年，L2c 的来源）
CLAN_GRAIN_PER_MONTH = 8.0       # 宗室每人月禄米（石）
CLAN_PAY_PER_MONTH = 30.0        # 宗室每人月俸折色（贯）——沿用官制设计 S-D3 的 30 贯/月
CORRUPTION_MULT = 0.8             # 吏俸缺口→贪腐扣减放大系数
BRIBE_FLOOR = 0.2                # 加俸无法消除的顽固贪腐下限（pay_ratio 折损下限 0.2）
IMPERIAL_SHARE = 0.10            # 内帑抽成：结余为正时 max(0,净结余)×IMPERIAL_SHARE（plan L148/L207 定稿 0.1）
WINE_YIELD_PER_GRAIN = 0.6       # 酿酒耗粮：每石粮酿 WINE_YIELD_PER_GRAIN 酒单位
# 盐课（活基准）：不再写死月额，改为随「盐产区产能 × 动态盐价 × 食盐人口」浮动。
#   盐课 = Σ各路盐产量(斤/年) × SALT_PROFIT_PER_JIN × price_factor × arrival × (总人口 / SALT_POP_BASE)
#   price_factor 由 盐产能 / 基准产能 之比决定（产能不足则价涨课利高，富余则价稳）；
#   总人口缩放使食盐人口增减直接反映到盐课。
#   开局 Σ盐产量≈1.85 亿斤/年 → price_factor=1.0、缩放=1 → 盐课≈39万贯/月（对齐史实榷盐净利 700~900万贯/年×到账率）。
SALT_PROFIT_PER_JIN = 0.055     # 盐榷利单价（贯/斤）：史实每斤盐榷利 40~45 文；平衡修复 0.045→0.055；盐课 = 盐产量 × 此价 × 到账率
SALT_CAPACITY_BASE = 185_000_000.0  # 开局 Σ各路盐产量基准（斤/年，1.85 亿斤）
SALT_POP_BASE = 80_000_000.0     # 食盐人口基准（口）= 在籍人口 8000 万（20 路 PREFECTURE_INFO 人口合计一致，开局 pop_scale≈1）
SALT_PRICE_FLOOR = 0.6           # price_factor 下限（产能远不抵基准时）
SALT_PRICE_CEIL = 1.3            # price_factor 上限（产能远超基准时）
# 酒课（保底基准）：WINE_COIN_BASE 为「无作坊时的保底月额」，受 tech.level 微扰；
#   玩家建作坊/工程产酒时，额外酒课走动态价 MATERIAL_PRICE_BASE["wine"]（见 settlement._settle_workshops）。
WINE_COIN_BASE = 600_000        # 酒课保底月额（加消耗定案扩容 10万→60万贯/月；酒课从工匠60%/商人40% wealth 扣缴入内帑）
# 内置作坊配方（玩家建作坊 / AI 拟诏可扩展）：{name, recipe(原料消耗), output_dim, yield(成品产出)}
#   recipe 键为原料维度（grain_feed 表粮耗）；output_dim 为成品维度（绸/布/wine/meat）。
#   grain_feed 从太仓扣（加工型消耗依托建筑，非无条件消耗）。
WORKSHOP_RECIPES = {
    "丝坊": {"name": "丝坊", "recipe": {"silk": 10000}, "output_dim": "绸", "yield": 8000},
    "麻坊": {"name": "麻坊", "recipe": {"hemp": 10000}, "output_dim": "布", "yield": 9000},
    "酒坊": {"name": "酒坊", "recipe": {"grain_feed": 50000}, "output_dim": "wine", "yield": 30},
    "畜栏": {"name": "畜栏", "recipe": {"grain_feed": 50000}, "output_dim": "meat", "yield": 2000},
}
WINE_TAX_SHARE = 0.12          # 内帑取酒课净额比例（史实：酒课多数归地方军资库，进内帑者约 12%）
WINE_GRAIN_PER_GUAN = 2.5      # 酿酒耗粮系数（石/贯总酒课，用于区域粮价需求推演；**不再作为无条件耗粮**，
                               # 加工型耗粮已依托酒坊建筑：坊数×5万石/月从太仓扣）
MEAT_PRICE = 0.5               # 畜栏产出折价（贯/单位，肉/畜产品售钱入内帑）
# 七维物资基准价（钱/单位，动态价=base×供需因子）；wine 为作坊榷酒课利基准价（不属七维物资仓）
MATERIAL_PRICE_BASE = {
    "salt": 300, "tea": 200, "silk": 200, "hemp": 40, "cane": 60,
    "fruit": 70, "timber": 50, "stone": 30, "iron": 250,
    "wine": 400,   # 酒单位动态价（钱/单位）：作坊产酒折钱归内帑的系数基准
    "绸": 800,     # 丝织成品（钱/匹），丝坊产出，高于生丝原料价
    "布": 120,     # 麻织成品（钱/匹），麻坊产出，高于麻原料价
}
# 七维物资维度（与 PREFECTURE_INFO.yields 键对齐）
# 原料维度（与 PREFECTURE_INFO.yields 键对齐；单位见 yields 注释）
RAW_DIMS = ["salt", "tea", "silk", "hemp", "cane", "fruit", "timber", "stone", "iron",
            "gold", "copper", "silver", "livestock", "horses", "herbs"]
# 成品维度（作坊产出，进物资仓；丝→绸、麻→布、粮→酒）
FINISHED_DIMS = ["绸", "布", "wine"]
# 物资仓维度 = 原料 + 成品（wine 走酒课进内帑，不入仓）
RESOURCE_DIMS = RAW_DIMS + ["绸", "布"]
# 14 维原料（外邦/宋统一表，§4.1）：与 EXTERNAL_ECON.RAW_DIMS 同名同义
# 金属 ≠ 钱（§4.3）：金/银/铜/铁是实物存量，禁止"仓里有银→自动加 treasury"
RAW_DIMS_14 = ("石", "木", "粮", "麻", "丝", "金", "铁", "铜", "银",
               "果", "牲畜", "药材", "马", "蔗")
# 原料单位表（供注册/展示；成品单位：绸/布=匹、wine=酒单位）
# 民间屯粮（士绅囤积居奇，模拟南方地主操纵粮价）：
#   开局屯粮 = 月产 × 系数（南方士绅势力大）。士绅每月囤/抛多少由 AI 推演（返回档位），
#   程序按档位换算成具体量（见 core.settlement_steps._settle_civilian_hoard），不写死比例。
CIVILIAN_HOARD_SOUTH = 2.0      # 南方路开局民间屯粮（= 月产 2 倍）
CIVILIAN_HOARD_NORTH = 0.5      # 北方路开局民间屯粮（= 月产 0.5 倍）
HOARD_SUPPLY_SQUEEZE = 0.03     # 屯粮挤压流通比例：每月 3% 屯粮退出流通、推高粮价
HOARD_SPOIL_RATE = 0.03         # 超硬上限囤粮未售部分损耗率（雀鼠耗/霉变，A1）：强制出清卖不掉的部分按此损耗核销，不凭空变钱
HOARD_COPPER_RATIO_BASE = 0.5   # 卖粮所得铜钱入窖比例（窖藏抽水复核定案：70%→50%）；交子部分仍全进 wealth 不入窖
HOARD_CAP_MULT = 0.3            # 士绅囤粮软上限系数（A1 定案）：囤粮上限 = 士绅田产年产的该比例（原硬编码 0.2 上调），
                                # 超软上限先售买方池、未售保留（囤积居奇机制保留）；仅超硬上限（软上限×1.5）强制出清
# 窖银动用率（A1 定稿·用户史实指示 c + 窖藏抽水复核定案）：由 AI 推演档位（_economy_ai["窖银"]）决定每月动用比例，
# 程序换算；无 AI（本地降级/缺键）兜底「小」= 0.5%/月被动缓释（藏富缓慢回流市场，不再完全冻结）。
HOARD_DRAW_RATE = {"无": 0.0, "微": 0.002, "小": 0.005, "中": 0.01, "大": 0.02,
                   "巨": 0.03, "极": 0.04}   # 审查 P1-3 修复：补巨/极，7 档闭合
# 开局货币校准（A1 定稿）：修复 F1（士绅卖粮造币）后补开局货币，防跌回通缩地板（物价 0.5）。
# 数值按蔡权衡量化：开局缺约 9400 万贯才到物价 1.0；落地后按回放微调（目标开局物价 0.9~1.1）。
# 开局货币校准（A1 定稿·蔡权衡量化定案）：START_MONEY_BOOST 170M。
# 依据：物价 1.0 需名义货币约 2.86 亿，118M 后 60 月末仅 0.798 偏低；
# 注入民间 wealth（按各 POP 财富比例分配），不注入国库。
START_MONEY_BOOST = 170_000_000
GENTRY_TREASURY_NORTH = 12     # 北方士绅资金（贯）= 月税入 × 12（士绅财力有限，囤粮受资金约束）
GENTRY_TREASURY_SOUTH = 24     # 南方士绅资金（贯）= 月税入 × 24（南方地主富）
# ---- POP 人口群体模型（参考维多利亚：每路人口按职业分层，每 POP 有 人数/钱/粮）----
POP_TYPES = ["农", "士绅", "工匠", "商人", "官僚", "兵"]
POP_SHARE = {                 # 开局各 POP 占在籍人口比例（官僚/兵另由 officials/clerks/army 给出）
    "士绅": 0.015,            # 地主+官，南方更集中
    "工匠": 0.05,             # 坊郭工匠
    "商人": 0.03,             # 行商坐贾
    # 农 = 其余（1 - 士绅 - 工匠 - 商人）
}
RAW_UNITS = {"salt": "斤", "tea": "斤", "silk": "匹", "hemp": "匹", "cane": "斤",
             "fruit": "斤", "timber": "根", "stone": "方", "iron": "斤", "绸": "匹", "布": "匹"}

def register_raw_material(dim, unit, price, default_yield=0, state=None):
    """预留接口：注册新作物 / 新矿（AI 拟诏开发时调用）。

    加入原料维度、价格表、单位表；传入 state 时**同时为该维建好资源槽**
    （state.resources[dim] = {"stock": 0, "cap": 0}）。
    返回 dim，供注册方回填叙事。

    审查修复：原实现只改模块级 RESOURCE_DIMS，不补 state.resources → 之后
    工程/作坊读取该维时，`state.resources[dim]["stock"]` 直接 KeyError（中断整月
    结算，由快照回滚兜底但该月白跑），或按缺料判定而永久停滞。调用方应传入 state。
    """
    global RAW_DIMS, RESOURCE_DIMS
    if dim not in RAW_DIMS:
        RAW_DIMS.append(dim)
    if dim not in RESOURCE_DIMS:
        RESOURCE_DIMS.append(dim)
    MATERIAL_PRICE_BASE[dim] = price
    RAW_UNITS[dim] = unit
    if state is not None:
        res = getattr(state, "resources", None)
        if isinstance(res, dict):
            res.setdefault(dim, {"stock": 0, "cap": 0})
    return dim


def register_finished_good(dim, unit, price, demand=None):
    """预留接口：注册新商品（成品，玩家/AI 开发新作物→新作坊→新商品时调用）。

    加入成品维度、价格表、单位表、物资仓，并为各 POP 补默认商品需求分层。
    demand 为可选 {pop: 占比}，缺省归入「布」类日用（农/兵消费）。
    返回 dim。"""
    global FINISHED_DIMS, RESOURCE_DIMS
    if dim not in FINISHED_DIMS:
        FINISHED_DIMS.append(dim)
    if dim not in RESOURCE_DIMS:
        RESOURCE_DIMS.append(dim)
    MATERIAL_PRICE_BASE[dim] = price
    RAW_UNITS[dim] = unit
    GOODS_DEMAND.setdefault(dim, demand or {"农": 0.5, "兵": 0.5})
    return dim


# 各 POP 商品需求分层（按阶级买不同商品：士绅买绸贵、农兵买布日用；新增商品经 register_finished_good 加入）
# 结构 {pop: {商品: 占比}}：该 POP 的消费额按占比分配到各商品
GOODS_DEMAND = {
    "士绅": {"绸": 0.7, "布": 0.3},
    "官僚": {"绸": 0.5, "布": 0.5},
    "商人": {"绸": 0.3, "布": 0.7},
    "工匠": {"绸": 0.2, "布": 0.8},
    "兵": {"布": 1.0},
    "农": {"布": 1.0},
}

# 各路兵额派生说明（DEFENSE_DERIVE）：
#   DEFENSE_LINES 的 garrison 不再写死，改为由各路 garrisons 聚合的只读视图：
#   北线_太原真定 ← 河北+河东；中线_黄河渡口 ← 京西+东京；内线_东京城防 ← 东京+京西+禁军余部。
#   兵额单位：人（真实整数）。开局 12 路合计约 75 万兵（750000 人），西军仅在陕西路。

# 税收结构
TAX_LAND_RATIO = 0.60          # 田赋占六成（名义口径，实征走田亩系统）
TAX_COMMERCE_RATIO = 0.30      # 工商占三成（名义口径；实征按 commerce_tax_rate 对经济总量征收）
TAX_POLL_RATIO = 0.10          # 丁口(役钱)占一成（税基 POP 化后校准）
# 欠税月追缴率（A1）：税征不足时缺口记入 POP 欠税科目，次月起每月最多按
# 「可支付财富（wealth - 保底线）的该比例」追缴回收（替代原直接蒸发，钱不凭空生）。
ARREARS_COLLECT_RATE = 0.25    # 欠税追缴率（/月；蔡权衡开局回调 0.25→0.22，恢复开局窘迫——追缴放缓）
MIN_WEALTH_FLOOR_RATIO = 0.78  # 保底豁免口径系数（蔡权衡开局回调 0.75→0.78：豁免口径放宽——农免缴更多，
                               # 税入略降，开局窘迫；农仍保生存底线）
# ---- 农户「粜粮完税」（2026-09-18 · 历史↔游戏性取中）----
# 实证：农户 POP 现金恒低于「1 月口粮折价 × 系数」的保底线 → **役钱与自耕田折色
# 全部转为欠税且永不回收**（60 月累计农欠税 4,399 万贯），即整条农税通道是死账。
# 历史事实是：农户现金少，但**卖粮换钱完税**（免役钱、二税折色皆需现钱），买主是豪强/粮商。
# 故新增本通道 —— 农缺现金时向本路 `士绅`/`商人` 粜粮，**钱与粮双向守恒**
# （士绅/商人 wealth ↓、粮 ↑；农 wealth ↑、粮 ↓），既不造币也不凭空生粮。
TAX_GRAIN_SALE_ENABLED = True
FARMER_TAX_GRAIN_KEEP_MONTHS = 3.0   # 粜粮后须保有的口粮月数（安全垫：不许"卖粮完税卖到饿死"）
TAX_GRAIN_SALE_MAX_SHARE = 0.05      # 单月最多卖掉农存粮的比例（防一次性倾仓冲击粮价）
# ---- 结余「补发积欠」（2026-09-18 · 历史↔游戏性取中）----
# 取中后出现的新内部矛盾：国帑丰裕（240 月 4,682 万贯）而 `pay_arrears`（欠饷欠俸）
# 仍在单向累积 —— 「国库满、军队欠饷」，玩家一看就假。史实上丰年确实**补发积欠**。
# 故：结余动用一部分补发积欠（国库 → 兵/官僚 POP wealth，纯转移），并同步冲减各军欠饷。
ARREARS_REPAY_SHARE = 0.25           # 单月用「超安全库的结余」补发积欠的比例
ARREARS_KEEP_TREASURY = 500_000      # 国库应急安全库存（低于此不动用）
# ---- 政府支出回流去向（统一口径，"支出回流" A1 定案）----
# 政府花钱买营造/服务/商品 → 钱进民间（工匠 40% / 商人 60%）。`_settle_finance` 的常费回流、
# `_settle_upkeep` 的维持费、`focus_mechanic` 的国策度支**共用同一去向**，
# 避免"支出凭空蒸发"（那会让 `money.reconcile` 报出非零残差）。
GOV_SPEND_TO = {"工匠": 0.4, "商人": 0.6}

# 工商征率（玩家可调）：对 POP 商品消费额（工匠/商人真实产值）按"几成"征收。
# 默认 0.25 = 抽二成五。税基 POP 化后按真实商品消费额征，量级校准到收支平衡。
COMMERCE_TAX_RATE_DEFAULT = 0.06   # 蔡权衡开局回调：0.055→0.05（下限，备选旋钮——亏损仍浅则再调 ARREARS/MIN_WEALTH）
# 工匠/商人人均月产值（贯）：工商税基 = (工匠+商人)size × 此值，为"产值流量"（不随财富存量下降，避免税抽干税基的螺旋）
CRAFT_OUTPUT_PER_CAPITA = 4.5
COMMERCE_TAX_RATE_MIN = 0.05   # 最低 0.5 成
COMMERCE_TAX_RATE_MAX = 0.40   # 最高 4 成
# ---- 人口自然增长率（审查 2026-09 调参：原固定 randint(-5000,15000) 月期望仅 +0.5 万，
#      占 8000 万≈0.075%/年，过低致长局人口一路缓降。改为按在籍人口一定月化比率，单一权威源）----
POP_GROWTH_RATE = 0.0008        # 月净自然增长率 0.08% → 年化≈0.96%（北宋徽宗朝承平约 0.5%~1%/年）
POP_GROWTH_JITTER = 5000        # 月度死亡/疫病/丰歉随机抖动（历史均值≈0，仅加波幅，不改变净趋势）
# 工商征率档位表（审查 P1 单一权威源：AI「征几成」经档位词归档→税率；
# 此前 ai/client_utils 硬编码同表造成双源。极=0.35 为既有保守口径
# （低于玩家政策上限 COMMERCE_TAX_RATE_MAX=0.40——AI 征率留余量，不追满））
COMMERCE_TAX_RATE_BY_TIER = {
    # E 说明（消除"与 TIER_RANGE['无']=0.0 矛盾"的误读）：本表是**税率设定值**表，
    # 不是增量倍率表 —— 工商征率是"设成几成"的绝对量，而非"加/减多少"。
    # 故「无」在此语义为「不调整该税率」（落到政策下限 5%），而非「税率归零」；
    # 且 _settle_finance / game_state_econ 对征率一律 clamp 到 [MIN, MAX]，
    # 归零在现行口径下本就不可施行。真出现"零征率"需求时须先放开该 clamp。
    "无": COMMERCE_TAX_RATE_MIN,
    "微": 0.10, "小": 0.15, "中": 0.20,
    "大": 0.25, "巨": 0.30, "极": 0.35,
}

# 破产兜底：**累计亏空深度**的两档阈值（贯，正数）
#  - TREASURY_CRISIS_LINE：累计亏空超过此深度触发"库藏空虚"危机事件，逼玩家表态
#  - TREASURY_COLLAPSE_LINE：超过此深度强判 game_over（国用耗竭，天下鼎沸）
# B3 修复（原为负值 −500万 / −2000万）：国库写入全链路禁止穿底
# （GameState.change_treasury 与 _settle_finance 均 max(0,…)），负余额永不存在，
# 原阈值针对「state.treasury < 负数」判定 → 两条线与全部消费方均为死分支
# （破产结局、「库藏空虚」危机、财政评价 30/10 档全部不可达）。
# 现改判 GameState.deficit_depth()：当月资金不足以覆盖支出时，差额逐月累加，
# 有结余时优先冲抵。语义等价，且真实可达。
TREASURY_CRISIS_LINE = 5_000_000
TREASURY_COLLAPSE_LINE = 20_000_000



# ============================================================
# 数值工具（单一权威源）
# ============================================================
def clamp(value: float, lo: float, hi: float) -> float:
    """把数值钳制到 [lo, hi] 闭区间（**单一权威源**）。

    审查 P3 修复：`_clamp` 原在 core/game_state.py（模块级）与 core/game_state_econ.py
    （模块级 + mixin 方法）各写一份、共三处重复；现统一由本函数提供，
    各模块 `from content.data import clamp as _clamp`（保留既有调用点写法）。
    """
    return max(lo, min(hi, value))


# ============================================================
# 脱敏词映射
# ============================================================
DESENSITIZE_MAP = {
    # 皇威
    "prestige": {
        25: "皇威扫地",
        40: "皇威不振",
        60: "皇威平平",
        80: "皇威尚隆",
        100: "皇威鼎盛",
    },
    # 到账率
    "arrival": {
        0.2: "十不存二",
        0.4: "不足五成",
        0.6: "六成上下",
        0.8: "十之七八",
        1.0: "几近全数",
    },
    # 满意度
    "satisfaction": {
        20: "怨声载道",
        40: "颇有微词",
        60: "大体认可",
        80: "心悦诚服",
        100: "感恩戴德",
    },
    # 国库
    "treasury": {
        0: "库空如洗",
        2000000: "入不敷出",
        5000000: "略有结余",
        10000000: "国库充盈",
        20000000: "富甲天下",
    },
}



# 效果档位顺序（口谕走样降档用）
TIER_ORDER = ["无", "微", "小", "中", "大", "巨", "极"]

# 档位换算表（单一权威源：AI 只给 tier，数字由程序掷定并封顶；ai/client_utils 从此导入）。
# 用户确认：5 档 → 7 档（无/微/小/中/大/巨/极；大 1.8→1.5 归一，巨 2.0、极 2.5）。
TIER_RANGE = {
    "无": 0.0,
    "微": 0.25,
    "小": 0.5,
    "中": 1.0,
    "大": 1.5,
    "巨": 2.0,
    "极": 2.5,
}

# 档位丰富表达映射表（AI 可输出生动词，validator 归一映射到标准档位）。
# normalize_tier(词) → 标准档位；未知词按字形含「极/巨/大/中/小/微」就近归一。
TIER_ALIAS = {
    "无": ("无", "毫无", "绝无", "零"),
    "微": ("微", "些许", "微澜", "略", "一星"),
    "小": ("小", "稍", "小波", "微起", "浅"),
    "中": ("中", "明显", "中浪", "可观", "寻常"),
    "大": ("大", "显著", "大潮", "甚", "猛烈"),
    "巨": ("巨", "剧烈", "巨涛", "严重", "浩大"),
    "极": ("极", "极端", "海啸", "惊天", "绝伦"),
}
_TIER_ALIAS_REV = {a: k for k, vals in TIER_ALIAS.items() for a in vals}


def normalize_tier(word) -> str:
    """丰富表达 → 标准档位（validator 归一映射）；未知词就近匹配或回「无」。"""
    if not isinstance(word, str):
        return "无"
    w = word.strip()
    if w in _TIER_ALIAS_REV:
        return _TIER_ALIAS_REV[w]
    for k in ("极", "巨", "大", "中", "小", "微"):
        if k in w:
            return k
    return "无"

# ---- free_effect 通用契约（言枢密 v3 设计）：AI 自由动作可落地的白名单字段 ----
# 拒绝式校验：AI 输出的 effects 键必须 ∈ 此白名单，否则整单拒绝（不落地）；
# 数值经 TIER_RANGE/tier_to_value 换算并 CAP 封顶，AI 只有提议权。
FREE_EFFECT_FIELD_WHITELIST = (
    "prestige", "treasury", "population_satisfaction", "faction_change",
    "external_jin", "external_liao", "external_xixia", "defense_bonus",
    "tech", "art_mastery", "army", "finance", "talent",
    # 阶段 C-7：官制/吏制的**编制参数**可由AI 拟诏调整（§12.3 六杠杆 ＋ §17.4 参数清单）。
    # 值为 {参数名: 档位词或数值}，与 faction_change 同为"字典型"字段。
    # 决策 3（已拍板）：**不为公务员制做转轨系统**——玩家用政令把参数移到公务员制的取值即可。
    "institution",
)
# free_effect 单字段封顶（CAP，防 AI 提议越权量级）：字段 → (上限值)（与 ai/client_utils._TIER_CAP 对齐并扩展）
FREE_EFFECT_CAP = {
    "prestige": 12, "treasury": 3_000_000, "population_satisfaction": 10,
    "external_jin": 12, "external_liao": 12, "external_xixia": 12,
    "defense_bonus": 10, "tech": 10, "art_mastery": 10, "army": 10,
    "finance": 3_000_000, "talent": 10,
    "institution": 1.0,          # 参数**增量**封顶（每个键各自还会按 SPEC 的值域再钳一次）
}

# ============================================================
# 编制参数（阶段 C-7）：宋代官吏制 ＝ 这组参数的一组取值；公务员制 ＝ 另一组取值。
# 决策 3 定案：不做转轨系统，只保证**这些参数可被政令修改**并被结算消费。
# 全部为**乘数/比例**（倍率），默认 1.0（muster_share 例外，是比例），
# 值域由 `INSTITUTION_PARAM_SPEC` 单点约束；`state.institution_params` 存**增量后的倍率**。
# ============================================================
INSTITUTION_PARAM_SPEC = {
    # §12.3 杠杆 1：定编宽严 → 差遣定员（= 冗官的闸门）
    "posts_quota_mult":    {"default": 1.0, "min": 0.4, "max": 1.6, "label": "定编宽严"},
    # §17.4：吏职级薪基 → 吏禄充足度 → 陋规强度（"花钱买治理"的核心旋钮）
    "clerk_pay_mult":      {"default": 1.0, "min": 0.0, "max": 5.0, "label": "吏职级薪基"},
    # §12.3 杠杆 2：荫补之门 → 恩荫规模（**冗官主源**）
    "yinben_mult":         {"default": 1.0, "min": 0.0, "max": 3.0, "label": "荫补之门"},
    # §12.3 杠杆 3：磨勘年限（越大升迁越快→人均俸禄膨胀越快）
    "rank_up_mult":        {"default": 1.0, "min": 0.0, "max": 3.0, "label": "磨勘年限"},
    # §12.3 杠杆 4：祠禄比例 → 待阙转宫观闲职的阈值
    "sinecure_mult":       {"default": 1.0, "min": 0.0, "max": 3.0, "label": "祠禄比例"},
    # §12.3 杠杆 5/§17.4：世袭比例 → 把持度
    "hereditary_mult":     {"default": 1.0, "min": 0.0, "max": 2.0, "label": "世袭比例"},
    # §12.3 杠杆 5/§17.4：差役 ↔ 募吏结构（比例：募吏占比）
    "muster_share":        {"default": 0.4, "min": 0.0, "max": 1.0, "label": "募吏比例"},
    # §12.3 杠杆 6：考课黜落 → 每年在岗官退出率
    "retire_mult":         {"default": 1.0, "min": 0.2, "max": 2.5, "label": "考课黜落"},
    # 财力消耗设计 S-D6：玩家**主动降维持费**（裁汰冗费）
    "asset_maintain_mult": {"default": 1.0, "min": 0.0, "max": 2.0, "label": "资产维持费"},
    # ---- 金融：抵当所旋钮（第二节§3；史实为「抵当所」，宋无银行）----
    # **权限归属**：这些不是"定义"，而是**户部（部门）+ 抵当所提举（官职）的权限**；
    # 调整须经圣旨、由掌「官营放贷」事权者执行（人是载体，换人不换权）。
    # 设计：**参数不删、只给旋钮** —— 玩家经诏令 `effects: {"institution": {...}}` 调，
    # AI 同经 free_effect 提案；值域由本表单点约束（未知键整单/逐项拒绝）。
    "didang_reserve_ratio": {"default": 0.20, "min": 0.05, "max": 0.60, "label": "抵当所准备金率"},
    "didang_loan_rate":     {"default": 0.01, "min": 0.0,  "max": 0.05, "label": "抵当所月息"},
    "didang_loan_share":    {"default": 0.10, "min": 0.0,  "max": 0.50, "label": "抵当所放贷力度"},
    "didang_deposit_share": {"default": 0.05, "min": 0.0,  "max": 0.20, "label": "抵当所吸储力度"},
    "didang_deposit_cap":   {"default": 0.30, "min": 0.05, "max": 0.80, "label": "抵当所存款上限"},
}

# ---- 档位→数值换算单一权威源（审查 P1-2/P2-3 修复：消除 _TIER_BASE/_TIER_CAP 与
#      FREE_EFFECT_CAP 双权威源漂移；补 art_mastery 基值与封顶）----
# tier_to_value(dim, tier) = TIER_VALUE_BASE[dim] × TIER_RANGE[tier] × authority，再 CAP 封顶。
# 此表为全游戏唯一的档位基值权威源；ai/client_utils._TIER_BASE/_TIER_CAP 已改为从此 import。
TIER_VALUE_BASE = {
    "prestige": 4,                     # 皇威 ±
    "treasury": 800_000,               # 国帑 ±（贯）
    "population_satisfaction": 3,      # 民心 ±
    "external_jin": 4,                 # 金态度 ±
    "external_liao": 4,                # 辽态度 ±
    "external_xixia": 4,               # 西夏态度 ±
    "defense_bonus": 3,                # 城防 ±
    "commerce_tax": 0.15,              # 工商征率（设定值：tier 档位→税率，非增量）
    "curtail_waste": 100_000,          # 省浮费：月省贯（设定值）
    "reduce_office": 100_000,          # 裁汰冗员：月省贯（设定值）
    "land_survey": 0.05,               # 方田均税：清丈隐田，降隐漏率
    "hoard": 0.05,                     # 士绅囤粮：囤/抛「中」档 = 月产(囤)或屯粮(抛)的 5%
    "finance": 800_000,                # 金融（交子/市舶收益）±
    "talent": 3,                       # 科举得才 ±
    "tech": 3,                         # 科技积累 ±
    "army": 3,                         # 军力 ±
    "reform": 3,                       # 改革推进 ±
    "art_mastery": 3,                  # 艺事精进 ±（审查修复：原 _TIER_BASE 缺此项致换算恒0）
}
# 单项封顶（与 FREE_EFFECT_CAP 对齐并扩展 curtail_waste/reduce_office/land_survey/hoard/reform）
TIER_VALUE_CAP = {
    "prestige": 12, "treasury": 3_000_000, "population_satisfaction": 10,
    "external_jin": 12, "external_liao": 12, "external_xixia": 12,
    "defense_bonus": 10, "finance": 3_000_000, "talent": 10, "tech": 10,
    "army": 10, "reform": 10, "land_survey": 0.10,
    "art_mastery": 10,                 # 审查修复：补 art_mastery 封顶
    "curtail_waste": 500_000, "reduce_office": 500_000,
    "hoard": 0.20,
}
# free_effect 成本（cost）超存量判定用的软上限比例：cost.treasury 超过当前国库该比例 → 整单不执行（拒绝）
FREE_EFFECT_COST_REJECT_RATIO = 2.0

# ---- 记忆知识库（Phase 3a，言枢密方案）：关系衰减 λ（/回合，单一权威源）----
# w_eff = w_base × exp(-λ × Δturn)；λ 大 = 淡忘快（promises 诺言、progresses 进度）、
# λ 小 = 持久（governs 主政、stance 态度、supports/opposes 立场）。
MEMORY_RELATION_DECAY = {
    "supports": 0.02, "opposes": 0.02, "involves": 0.03, "produces": 0.03,
    "progresses": 0.02, "promises": 0.05, "stance": 0.015, "governs": 0.01,
}
MEMORY_ARCHIVE_WEIGHT = 0.25   # 归档阈值：w_eff 低于此 → 标记 archived（SQLite summaries 表，不物理删除）

# ---- 全游戏级强制 AI：统一错误码（单一权威源，AI 缺失/失败一律拒绝式报错，不降级不伪造）----
AI_ERROR_CODES = {
    "AI_NOT_CONFIGURED": "未接入 AI：请配置 OpenAI 兼容 API（base_url/api_key/model）",
    "AI_TIMEOUT": "AI 服务连接超时：请检查网络或 base_url 后重试",
    "AI_AUTH_FAILED": "AI 鉴权失败：请检查 api_key",
    "AI_EMPTY_RESPONSE": "AI 返回空响应",
    "AI_INVALID_JSON": "AI 返回非 JSON / 契约无法解析",
    "AI_CONTRACT_FAILED": "AI 输出不满足契约（字段缺失/越界）",
}


# ---- 金融数据契约（第六节）：schema version + 单位 + 守恒/上限约束 ----
# 单位契约：金额一律「贯」(MONEY_UNIT)，粮一律「石」(GRAIN_UNIT)；只有以 won 计
# （万贯）的 legacy 字段才用 WON_PER_GUAN 换算。**禁止贯与万贯混用**——
# BANK_INFO.capital 是已知 legacy「万贯」字段，读取必须走 core.money.BankCapital。
FINANCE_SCHEMA_VERSION = 1
MONEY_UNIT = "贯"
GRAIN_UNIT = "石"
WON_PER_GUAN = 10_000

FINANCE_UNITS = {
    "money": MONEY_UNIT,          # 铜钱/交子/国库/内帑/府库/银折钱 …
    "grain": GRAIN_UNIT,          # 太仓/州仓/POP 粮 …
    "silver": "两",               # 白银原始计量；折钱用 STANDARD_INFO 汇率
    "material": "单位",           # 材料走 RESOURCE_DIMS[*]["stock"] 的抽象单位
    "bank_capital": "万贯",       # ⚠ legacy：仅 BANK_INFO.capital；换算 WON_PER_GUAN
    "bank_reserve": MONEY_UNIT,   # 银行准备金/存款/贷款一律贯（与 capital 区分）
}

# 交子约束（第二节§2）：发行上限 = 准备金×皇威 × 税收接受度 × 信用上限
JIAOZI_TAX_ACCEPTANCE = 0.80    # 税收接受度默认值（0~1）
JIAOZI_CREDIT_FLOOR = 0.50      # 信用上限系数下限（trust=0 时保留的发行能力）
JIAOZI_RUN_TRUST_LINE = 40      # 信用跌破此线 → 折价/挤兑派生
JIAOZI_RUN_RESERVE_LINE = 0.50  # 兑付率低于此线 → 挤兑压力上升

# 银行信贷（第二节§3）：月息/准备金率/放贷与存款月度份额/坏账基准
BANK_LOAN_RATE = 0.01            # 贷款月息（1%/月）；利息归银行留存，**不入国库**
BANK_DEPOSIT_RATE = 0.003        # 存款月息（0.3%/月）
BANK_RESERVE_RATIO_MIN = 0.10    # 准备金率下限
BANK_LOAN_MONTH_SHARE = 0.10     # 每月放贷 ≤ 可用准备金 × 此比例
BANK_DEPOSIT_MONTH_SHARE = 0.05  # 每月吸储 ≤ 目标 POP wealth × 此比例


# ---- 资产维持费（L1 money sink，2026-09-18 阶段 B-3）----
# 设计早已在 `BUILDING_STD[*]["maintain"]` 写明"维护 ×0.5%/月"，但**全库从未消费**
# （实测：`maintain` 仅有定义、零引用）——正是审查 A-1/财力消耗设计 L1 要补的那一环。
# 本组常量补齐**其余资产类型**的折算基准，使"玩家越扩张 → 固定支出越大"成立。
# 计费口径：资产折算造价 × ASSET_MAINTAIN_RATE（月）→ 国库支出 → 支付给营造/修缮方（民间）。
WORKSHOP_VALUE = 120_000        # 单座作坊折算造价（贯）
EQUIP_UNIT_VALUE = 2.0          # 军械折价（贯/件）
FORT_VALUE = 10_000             # 城防每点折算造价（贯）
POP_BUILDING_VALUE = 100_000    # 非 BUILDING_STD 的 POP 建筑（农田/工坊/商铺/庄园）每级折算造价（贯）
ASSET_MAINTAIN_RATE = 0.005     # 统一月维护率 0.5%/月（与 BUILDING_STD[*].maintain 一致）
UPKEEP_PAY_TO = {"工匠": 0.4, "商人": 0.6}   # 维护支出支付对象（营造/修缮服务；和为 1）
POP_BUILDING_TYPES = ("农田", "工坊", "商铺", "庄园")   # POP 建筑（阶层 wealth 出资，Lv1-5，×0.05/Lv）
POP_BUILDING_EFFECT = 0.05     # 每级 ×0.05（封顶 ×2.0 由 BUILDING_EFFECT_CAP 统一）

# 校准说明：岁入缗钱 5000~6000 万贯（流量），流通货币存量须按周转 3~4 次反推约 1.5~2.5 亿贯，
# 否则"一年收税近 6000 万、流通仅 6000 万"会自相矛盾、把市场一年抽干。故存量取 2 亿贯。
# 货币流通速度：周转次数/年。税基抬升后若无流通速度，货币/实物比会骤跌、物价触底钱荒恶化，
# 故在物价公式中显式加入 PRICE_VELOCITY（≈1.8 次/年，与周转概念自洽）。
PRICE_VELOCITY = 1.8
TAX_COEFF_MIN = 0.75           # 纳税系数下限（钱荒税难征）
TAX_COEFF_MAX = 1.25           # 纳税系数上限（泉货充裕税易征）

# ---- 铸钱受控（T9 定稿）：铜资源约束 + 熔耗 20% 净增 80% + 物价>2.0 禁止 ----
MINT_MELT_LOSS = 0.20           # 铸钱熔耗 20%（熔铜铸钱损耗）
MINT_NET_RATIO = 0.80           # 净增 80%（1 − 熔耗）
MINT_PRICE_BAN = 2.0            # 物价 > 此值禁止铸钱（防助涨通胀）
COPPER_RESOURCE_DIM = "iron"    # 铸钱金属资源维度（resources 记账；用既有 iron 维度承载铸钱金属，不新增维度破坏存档/初始化）



# ============================================================
# 金融/科举/科技/军/外交/改革 → 脱敏描述辅助（原 data_desensitize.py 内联）
# ============================================================
def _desensitize_from_map(field: str, value) -> str:
    """按 DESENSITIZE_MAP 阈值升序取档（单一权威源；超上界收敛到最高档）。

    审查 P2-61 修复：原四个 desensitize_* 函数各自硬编码同一组阈值/文案（与
    DESENSITIZE_MAP 双份定义、修改需两处同步），现统一查表（对外行为逐值等价）。
    """
    tiers = DESENSITIZE_MAP.get(field) or {}
    if not tiers:
        return ""
    for th in sorted(tiers):
        if value <= th:
            return tiers[th]
    return tiers[max(tiers)]


def desensitize_prestige(value: int) -> str:
    """皇威数值→脱敏描述（阈值/文案取自 DESENSITIZE_MAP）"""
    return _desensitize_from_map("prestige", value)

def desensitize_arrival(rate: float) -> str:
    """到账率→脱敏描述"""
    return _desensitize_from_map("arrival", rate)

def desensitize_satisfaction(value: int) -> str:
    """满意度→脱敏描述"""
    return _desensitize_from_map("satisfaction", value)

def desensitize_treasury(amount: int) -> str:
    """国库→脱敏描述"""
    return _desensitize_from_map("treasury", amount)

def desensitize_trust(value: int) -> str:
    if value <= 20: return "交子几不可信"
    if value <= 40: return "商民疑之"
    if value <= 60: return "信用尚稳"
    return "远近信行"

def desensitize_shortage(rate: float) -> str:
    if rate <= 0.1: return "泉货流转"
    if rate <= 0.3: return "钱荒渐显"
    if rate <= 0.6: return "钱荒严重"
    return "几乎无钱可用"

def desensitize_granary(amount: float, cap: float = 1500) -> str:
    """太仓虚实（定性）：用于奏报与 AI 认知层，绝不下放精确存粮数。"""
    if cap <= 0:
        cap = 1500
    r = amount / cap
    if r >= 0.75: return "太仓丰盈，粟积如丘"
    if r >= 0.5:  return "仓储殷实，足以支国用"
    if r >= 0.25: return "仓廪见绌，宜促漕运"
    if r > 0:     return "太仓空虚，几无隔宿之粮"
    return "太仓告罄，京畿乏食"

def desensitize_price(price: float) -> str:
    """米价定性：用于趋势读数与 AI 认知层。"""
    if price >= 2.0: return "米珠薪桂，民不堪命"
    if price >= 1.5: return "米价腾涌，市井骚然"
    if price >= 1.1: return "米价偏高，小民艰食"
    if price <= 0.6: return "谷贱伤农，丰年反困"
    if price <= 0.8: return "米价低平，农人或困"
    return "米价适中，市侩安和"

def desensitize_canal(block: int) -> str:
    """漕运通滞定性。"""
    if block >= 70: return "漕路断绝，纲船难通"
    if block >= 40: return "漕运受阻，输粟不畅"
    if block >= 15: return "漕途多阻，转运维艰"
    return "漕运通畅，转输无滞"

def desensitize_talent(value: int) -> str:
    if value <= 20: return "人才凋零"
    if value <= 50: return "人才平平"
    if value <= 80: return "人才颇盛"
    return "人才辈出"

def desensitize_tech(value: int) -> str:
    if value <= 20: return "技艺粗疏"
    if value <= 50: return "技艺尚可"
    if value <= 80: return "百工精进"
    return "巧夺天工"

# 常平仓初值：月产占比（原 game_state/save_load 双处硬编码 /12*0.2）
CHANGPING_INIT_MONTHLY_SHARE = 0.2 / 12  # = grain/12*0.2，单点权威
