# -*- coding: utf-8 -*-
"""宋祚 · 游戏内容数据 —— 所有静态数据/常量定义"""
# cspell:words MEIPASS ZHONGZHI KOUYU MULT JIAOZI COEFF CHANGPING prereq steampump elecbasis elecsteel metaltype hotspot mult
import os
import sys

# ============================================================
# 存档目录
# ============================================================
# 打包态（PyInstaller）：_MEIPASS 为资源解包目录，_BASE 为可执行文件所在目录；
# 源码运行态：_BASE 为项目根目录（content 的上级），资源/存档均在其下。
# 用条件表达式一次性赋值 _BASE，避免全大写常量被重复定义
_BASE = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

_MEIPASS: str | None = getattr(sys, "_MEIPASS", None)
# 共用：基于 _BASE 推导资源与存档目录
ASSETS_DIR = os.path.join(_MEIPASS, "assets") if _MEIPASS else os.path.join(_BASE, "assets")

# 存档统一放在"我的文档/宋祚/saves"，与 exe 所在位置解耦，便于分发与跨版本保留进度
_DOCUMENTS = os.path.expanduser("~/Documents")
SAVE_DIR = os.path.join(_DOCUMENTS, "宋祚", "saves")

# 资源目录（底图等）
MAP_DIR = os.path.join(ASSETS_DIR, "map")


def get_resource(rel_path: str):
    """返回资源文件的绝对路径（rel_path 相对 assets 目录）。"""
    return os.path.join(ASSETS_DIR, rel_path)


def empire_bg_path() -> str:
    return os.path.join(MAP_DIR, "empire_bg.png")


# 舆图上常驻显示的境外政权（主要势力），其余境外只在 hover 时显示标签/高亮
EXTERNAL_ALWAYS_SHOW = {
    "辽", "西夏", "吐蕃", "高丽", "日本",
}





def desk_bg_path() -> str:
    return os.path.join(MAP_DIR, "desk_bg.png")

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

# ============================================================
# 诏令系统
# ============================================================
DECREE_BASE_BANDWIDTH = 6      # 圣旨基础带宽
DECREE_MAX_BANDWIDTH = 10      # 圣旨上限
SECRET_DECREE_MIN = 2          # 密旨最低
SECRET_DECREE_MAX = 3          # 密旨最高
DIRECT_DECREE_MAX = 2          # 御笔直发上限
WOLF_THRESHOLD = 3             # 狼来了阈值

# 诏意机构归属（拟旨润色时由 AI 建议，会签与执行共用）
# 归属类别：内廷（直属皇帝，无条件执行）/ 政府（三省六部，走会签）/ 地方（州县，可能抗旨）
ORG_AFFILIATION = {
    "内廷": ["枢密院(内廷)", "内侍省", "御药院", "皇城司", "殿前司"],
    "政府": ["中书省", "门下省", "尚书省", "吏部", "户部", "礼部", "兵部", "刑部", "工部"],
    "地方": ["京东东路", "京西路", "河北路", "河东", "陕西路", "两浙路", "江南东路",
            "江南西路", "荆湖南路", "福建路", "成都府路", "广南东路"],
}
# 中旨（御笔强推）按机构归属的执行率（与 calc_decree_execution_rate 合并计算）
ZHONGZHI_AFFILIATION_RATE = {
    "内廷": 1.00,   # 直属内廷，无条件奉行
    "政府": 0.85,   # 政府衙门，阳奉阴违有限
    "地方": 0.60,   # 地方州县，可能抗旨不办
}
# 口谕（召对现场口宣）即时生效但效果弱、可能走样
KOUYU_EFFECT_MULT = 0.6        # 口谕效果乘数（弱效）
KOUYU_DRIFT_CHANCE = 0.30      # 口谕走样概率（降一档）
KOUYU_DRIFT_DOWN = 1            # 走样降档级数（TIER_RANGE 索引下移）

# 执行率公式常量
S_BASE = 0.45                  # 圣旨基础成功率
S_SUPPORT_WEIGHT = 0.08        # 派系净支持权重
S_CONFLICT_WEIGHT = 0.15       # 党争修正权重
S_SECRET_BASE = 0.30           # 密旨基础成功率
S_SECRET_LOYALTY_WEIGHT = 0.7  # 密旨忠诚度权重
S_DIRECT_BONUS = 0.10          # 御笔加成
S_DIRECT_PENALTY = -0.15       # 狼来了惩罚
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
# tax_base_i 取现有 monthly_tax 初值（单位贯/月）作锚，开局全国锚≈1_097_000贯/月，全进国库（钱）。
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
CLERK_PAY_PER_MONTH = 2.0        # 每吏月俸折色（贯）
CLERK_GRAIN_PER_MONTH = 1.5      # 每吏月禄米（石）
CLERK_PER_OFFICIAL = 8           # 吏数 = 官数 × 8
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
SALT_POP_BASE = 80_000_000.0     # 食盐人口基准（口）= 在籍人口 8000 万（与 12 路人口合计一致，开局 pop_scale≈1）
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
RAW_DIMS = ["salt", "tea", "silk", "hemp", "cane", "fruit", "timber", "stone", "iron"]
# 成品维度（作坊产出，进物资仓；丝→绸、麻→布、粮→酒）
FINISHED_DIMS = ["绸", "布", "wine"]
# 物资仓维度 = 原料 + 成品（wine 走酒课进内帑，不入仓）
RESOURCE_DIMS = RAW_DIMS + ["绸", "布"]
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

def register_raw_material(dim, unit, price, default_yield=0):
    """预留接口：注册新作物 / 新矿（AI 拟诏开发时调用）。

    加入原料维度、价格表、单位表，并为各路补默认产量（开局 0，之后劝种/开矿/市舶演化）。
    返回 dim，供注册方回填叙事。"""
    global RAW_DIMS, RESOURCE_DIMS
    if dim not in RAW_DIMS:
        RAW_DIMS.append(dim)
    if dim not in RESOURCE_DIMS:
        RESOURCE_DIMS.append(dim)
    MATERIAL_PRICE_BASE[dim] = price
    RAW_UNITS[dim] = unit
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

# 工商征率（玩家可调）：对 POP 商品消费额（工匠/商人真实产值）按"几成"征收。
# 默认 0.25 = 抽二成五。税基 POP 化后按真实商品消费额征，量级校准到收支平衡。
COMMERCE_TAX_RATE_DEFAULT = 0.06   # 蔡权衡开局回调：0.055→0.05（下限，备选旋钮——亏损仍浅则再调 ARREARS/MIN_WEALTH）
# 工匠/商人人均月产值（贯）：工商税基 = (工匠+商人)size × 此值，为"产值流量"（不随财富存量下降，避免税抽干税基的螺旋）
CRAFT_OUTPUT_PER_CAPITA = 4.5
COMMERCE_TAX_RATE_MIN = 0.05   # 最低 0.5 成
COMMERCE_TAX_RATE_MAX = 0.40   # 最高 4 成

# 破产兜底：国库深度亏空的两档阈值（贯）
#  - TREASURY_CRISIS_LINE：国库跌破此值触发"库藏空虚"危机事件，逼玩家表态
#  - TREASURY_COLLAPSE_LINE：跌破此值强判 game_over（国用耗竭，天下鼎沸）
# 用户确认最终版：内帑黑洞不修（设计保留），危机线恢复原 −500万
TREASURY_CRISIS_LINE = -5_000_000
TREASURY_COLLAPSE_LINE = -20_000_000

# ============================================================
# 派系系统 (朝堂 6 派)
# ============================================================
FACTION_NAMES = [
    "新党",      # 蔡京系
    "旧党",      # 元祐旧臣
    "宦官集团",   # 童贯等
    "西军集团",   # 边防将领
    "东南士人",   # 东南科举士绅
    "清流言官",   # 台谏系统
]

FACTION_INIT = {
    "新党":     {"influence": 90, "satisfaction": 85, "cohesion": 70, "leader": "蔡京"},
    "旧党":     {"influence": 20, "satisfaction": 20, "cohesion": 40, "leader": "韩忠彦"},
    "宦官集团":  {"influence": 70, "satisfaction": 80, "cohesion": 65, "leader": "童贯"},
    "西军集团":  {"influence": 60, "satisfaction": 70, "cohesion": 75, "leader": "种师道"},
    "东南士人":  {"influence": 50, "satisfaction": 55, "cohesion": 50, "leader": "曾布"},
    "清流言官":  {"influence": 40, "satisfaction": 40, "cohesion": 55, "leader": "陈瓘"},
}

# ============================================================
# 外部势力
# ============================================================
EXTERNAL_FORCES = {
    "辽": {"power": 75, "attitude": 50, "internal_pressure": 20},
    "金":  {"power": 30, "attitude": 45, "internal_pressure": 10, "invasion_will": 0},
    "西夏": {"power": 55, "attitude": 35, "internal_pressure": 25},
}

# ============================================================
# 军事
# ============================================================
# ============================================================
# 军队实体层重构（兵额真账 = ArmyUnit.troops）
# ============================================================
# 军籍三分：禁军 / 厢军 / 乡兵。"西军"非独立军籍，即驻陕西边地的禁军。
# 旧 ARMY_INIT 的质量参数经此并入 UNIT_TIER；strength（锐气）字段已废弃，
# 战力改由 _army_power(unit, gunpowder) 统一派生（见 ui/panels_military.py）。
#
# 各路兵额唯一源头改为 ARMY_UNIT_INIT（单位：人，真实整数），
# 由各路 PREFECTURE_INFO.garrisons 直接载入（已是真实人数），
# 陕西"西军 20万"归入"禁军 200000"，数字原样、仅改归类。
ARMY_UNIT_INIT = {
    # 军籍键仅 禁军/厢军/乡兵
    "东京开封府": {"禁军": 60000,  "厢军": 20000,  "乡兵": 0},
    "京西路":     {"禁军": 10000,  "厢军": 10000,  "乡兵": 10000},
    "河北路":     {"禁军": 30000,  "厢军": 20000,  "乡兵": 30000},
    "河东":       {"禁军": 20000,  "厢军": 20000,  "乡兵": 10000},
    "陕西路":     {"禁军": 220000, "厢军": 20000,  "乡兵": 20000},  # 西军20万并入禁军
    "两浙路":     {"禁军": 20000,  "厢军": 20000,  "乡兵": 20000},
    "江南东路":   {"禁军": 10000,  "厢军": 10000,  "乡兵": 10000},
    "江南西路":   {"禁军": 10000,  "厢军": 10000,  "乡兵": 10000},
    "荆湖南路":   {"禁军": 10000,  "厢军": 10000,  "乡兵": 10000},
    "福建路":     {"禁军": 10000,  "厢军": 10000,  "乡兵": 10000},
    "成都府路":   {"禁军": 10000,  "厢军": 20000,  "乡兵": 10000},
    "广南东路":   {"禁军": 10000,  "厢军": 10000,  "乡兵": 10000},
}

# 军籍素质基线（train/morale 用；粮饷已由 BRANCH_BASE×ARMY_RATE 按率计算，grain_mult/pay_mult 退役）。
UNIT_TIER = {
    "禁军": {"equip_base": 0.85, "train_base": 65, "morale_base": 70},
    "厢军": {"equip_base": 0.45, "train_base": 35, "morale_base": 45},
    "乡兵": {"equip_base": 0.30, "train_base": 25, "morale_base": 50},
}

# 军队粮饷/装备按率计算（蔡权衡数值定案，避免 21 张手写表）：
#   粮饷人均 = BRANCH_BASE[兵种] × ARMY_RATE[军籍]（石/贯 每人/月）
#   装备人均 = EQUIP_STD[兵种] × EQUIP_RATE[军籍]
ARMY_RATE = {"禁军": 1.0, "厢军": 0.55, "乡兵": 0.35}   # 粮饷军籍系数
EQUIP_RATE = {"禁军": 1.0, "厢军": 0.6, "乡兵": 0.4}    # 装备配给率（军籍装备差）
BRANCH_BASE = {   # 禁军基准（石/贯 每人/月）
    "重骑兵": {"grain": 2.0, "pay": 0.5},
    "轻骑兵": {"grain": 1.8, "pay": 0.45},
    "重步兵": {"grain": 1.7, "pay": 0.42},
    "轻步兵": {"grain": 1.5, "pay": 0.38},
    "弓弩兵": {"grain": 1.6, "pay": 0.40},
    "器械兵": {"grain": 1.5, "pay": 0.38},
    "水军":   {"grain": 1.7, "pay": 0.42},
}


def branch_std(tier: str, branch: str) -> dict:
    """军籍×兵种 → 粮饷装备标准（按率计算，单一权威源）：
    grain/pay = BRANCH_BASE[兵种] × ARMY_RATE[军籍]；equip = EQUIP_STD[兵种] × EQUIP_RATE[军籍]。
    """
    base = BRANCH_BASE.get(branch, BRANCH_BASE["轻步兵"])
    rate = ARMY_RATE.get(tier, 1.0)
    eq = {k: per * EQUIP_RATE.get(tier, 1.0) for k, per in EQUIP_STD.get(branch, {}).items()}
    return {"grain": base["grain"] * rate, "pay": base["pay"] * rate, "equip": eq}

# 战区类型：边地（陕西/河北/河东）多骑兵、内地多步弓。仅两档。
FRONTIER_ROUTES = {"陕西路", "河北路", "河东"}
# 边地禁军素质上调档（相对 UNIT_TIER 基线增量）
FRONTIER_TRAIN_BONUS = 20      # 边地禁军 training 上浮
FRONTIER_MORALE_BONUS = 10     # 边地禁军 morale 上浮
INLAND_TRAIN_BONUS = 0
INLAND_MORALE_BONUS = 0

# 兵种配给标准（每人实数表）。装备 7 项：枪刀/弓弩/火器/战马/盔甲/舟船/器械。
EQUIP_STD = {
    "重骑兵": {"枪刀": 1.0, "弓弩": 0.4, "火器": 0.0, "战马": 1.1, "盔甲": 1.0, "舟船": 0.0, "器械": 0.1},
    "轻骑兵": {"枪刀": 0.8, "弓弩": 0.6, "火器": 0.0, "战马": 1.0, "盔甲": 0.6, "舟船": 0.0, "器械": 0.0},
    "重步兵": {"枪刀": 1.0, "弓弩": 0.5, "火器": 0.0, "战马": 0.0, "盔甲": 1.0, "舟船": 0.0, "器械": 0.2},
    "轻步兵": {"枪刀": 1.0, "弓弩": 0.3, "火器": 0.0, "战马": 0.0, "盔甲": 0.3, "舟船": 0.0, "器械": 0.1},
    "弓弩兵": {"枪刀": 0.5, "弓弩": 1.0, "火器": 0.0, "战马": 0.0, "盔甲": 0.4, "舟船": 0.0, "器械": 0.1},
    "水军":   {"枪刀": 0.8, "弓弩": 0.5, "火器": 0.0, "战马": 0.0, "盔甲": 0.5, "舟船": 1.0, "器械": 0.3},
    "器械兵": {"枪刀": 0.3, "弓弩": 0.2, "火器": 0.0, "战马": 0.0, "盔甲": 0.2, "舟船": 0.0, "器械": 1.0},
}

# 各军籍 × 战区类型 → 兵种拆比（比例和=1）。build_army_units 按此拆支，余数归主将部。
ARMY_UNIT_SPLIT = {
    ("禁军", "边地"): {"重骑兵": 0.30, "轻骑兵": 0.25, "重步兵": 0.20, "轻步兵": 0.15, "弓弩兵": 0.10},
    ("禁军", "内地"): {"重步兵": 0.35, "轻骑兵": 0.15, "轻步兵": 0.25, "弓弩兵": 0.20, "重骑兵": 0.05},
    ("厢军", "边地"): {"轻步兵": 0.40, "器械兵": 0.25, "水军": 0.10, "轻骑兵": 0.15, "重步兵": 0.10},
    ("厢军", "内地"): {"轻步兵": 0.45, "器械兵": 0.25, "水军": 0.15, "轻骑兵": 0.10, "重步兵": 0.05},
    ("乡兵", "边地"): {"轻步兵": 0.55, "器械兵": 0.30, "弓弩兵": 0.15},
    ("乡兵", "内地"): {"轻步兵": 0.55, "器械兵": 0.30, "弓弩兵": 0.15},
}

# 宋制军队番号素材（A7 史翰青，玩法抽象层；只动番号命名层，不碰 troops/结算/存档键）：
#   禁军军号池按司（上四军史实 [B1]；殿前/马军/步军军号史实池，个别归属待考取一）；
#   厢军 = 路+役种（史实役种名 [B3]）；乡兵 = 史实名（[B4]；南方诸路保甲兜底合理推演）。
ARMY_ORG = {
    # 上四军（三衙最高资次）
    "禁军_上四": {"捧日": "殿前司", "天武": "殿前司", "龙卫": "侍卫马军司", "神卫": "侍卫步军司"},
    # 普通军号池（按司，供非上四军号轮转）
    "禁军_殿前马": ["骁骑", "宁朔", "龙猛", "飞猛", "神骑", "骁雄"],
    "禁军_殿前步": ["神勇", "宣武", "虎翼", "广勇", "雄武", "效忠", "神锐", "威虎"],
    "禁军_马军司": ["骁捷", "云骑", "武骑", "飞捷", "骁武", "广锐", "云翼", "克胜", "飞骑", "威远", "万捷", "云捷", "横塞", "蕃落"],
    "禁军_步军司": ["雄勇", "广捷", "神捷"],
    # 厢军役种（路 → 主/次役种，史实役种名，州军映射为路属玩法抽象）
    "厢军_役种": {
        "东京开封府": ("壮城", "装发"), "京西路": ("桥道", "清务"), "河北路": ("清务", "马监"),
        "河东": ("马监", "壮城"), "陕西路": ("山场", "铁作"), "两浙路": ("水军", "酒务"),
        "江南东路": ("竹作", "木务"), "江南西路": ("船坊", "装发"), "荆湖南路": ("车营", "桥道"),
        "福建路": ("船坊", "水军"), "成都府路": ("盐井", "山场"), "广南东路": ("水军", "装发"),
    },
    # 乡兵史实名（按路；南方诸路以保甲兜底，合理推演）
    "乡兵_名": {
        "河北路": "河北弓箭社", "河东": "河东强壮", "陕西路": "陕西义勇", "京西路": "京西保甲",
        "东京开封府": "京畿保甲", "福建路": "福建枪仗手", "广南东路": "广南土丁",
        "两浙路": "两浙保甲", "江南东路": "江南东保甲", "江南西路": "江南西保甲",
        "荆湖南路": "荆湖保甲", "成都府路": "川峡保甲",
    },
}

# 中央武库初值（7 项实物，按全军应配总量给合理开局库存的 60% 作为可调拨余量）
CENTRAL_ARSENAL_INIT = {
    "枪刀": 300000, "弓弩": 150000, "火器": 20000, "战马": 120000,
    "盔甲": 200000, "舟船": 3000, "器械": 60000,
}

# 火器代际（tech.gunpowder 0~100 → 形态名），_firearm_tier 使用
FIREARM_TIERS = [
    (20, "突火枪"),   # 火药成熟节点已启（gunpowder 开局 20）
    (40, "火铳"),
    (65, "火枪"),
    (85, "燧发枪"),
]


DEFENSE_LINES = {
    # 防区 garrison 为只读派生视图：由各路 army_units 聚合（见 game_state.defense_lines_view()）。
    #   北线_太原真定 ← 河北 + 河东
    #   北线_陕西      ← 陕西（驻边禁军核心）
    #   中线_黄河渡口 ← 京西 + 东京
    #   内线_东京城防 ← 东京 + 京西 + 余部
    # 此处仅存 fortification（城防质量）初值，garrison 初始化在 GameState.__init__ 派生注入。
    "北线_太原真定": {"fortification": 60},
    "北线_陕西": {"fortification": 70},
    "中线_黄河渡口": {"fortification": 45},
    "内线_东京城防": {"fortification": 75},
}

# ============================================================
# 事件系统
# ============================================================
EVENT_CATEGORIES = [
    "花石纲", "方腊起义", "宋江起义", "海上之盟",
    "金灭辽", "金军南侵", "宋夏战争", "黄河决口",
    "祥瑞", "党争", "科举", "灾荒",
]

# 史实年号序列
ERA_NAMES_HISTORY = {
    1101: "建中靖国",
    1102: "崇宁",
    1107: "大观",
    1111: "政和",
    1118: "重和",
    1119: "宣和",
}

# 难度预设
DIFFICULTY_PRESETS = {
    "史实": {
        "prestige_start": 55,
        "arrival_base": 0.45,
        "event_pressure_mult": 1.0,
        "event_threshold_mult": 1.0,
        "refugee_pressure_mult": 1.0,
        "external_growth": 1.0,     # 外部政权发育曲线倍率
    },
    "轻松": {
        "prestige_start": 60,
        "arrival_base": 0.55,
        "event_pressure_mult": 0.5,
        "event_threshold_mult": 1.25,
        "refugee_pressure_mult": 0.5,
        "external_growth": 0.6,
    },
    "艰难": {
        "prestige_start": 48,
        "arrival_base": 0.35,
        "event_pressure_mult": 1.4,
        "event_threshold_mult": 0.85,
        "refugee_pressure_mult": 1.4,
        "external_growth": 1.6,
    },
}

# 固定程序四类的参数模板（AI 解析拟旨时按 category 归一到这些参数）
FIXED_PROCEDURES = {
    "fixed_tech":         {"label": "科技营缮", "fields": ["project", "invest", "months"]},
    "fixed_finance":      {"label": "钱粮调度", "fields": ["source", "target", "amount"]},
    "fixed_army":         {"label": "军队调动", "fields": ["army", "to_line", "scale"]},
    "fixed_construction": {"label": "工程建设", "fields": ["site", "kind", "invest", "months"]},
}

# ============================================================
# 七维评价权重
# ============================================================
EVAL_WEIGHTS = {
    "文治": 0.15,
    "武功": 0.15,
    "民生": 0.15,
    "财政": 0.10,
    "艺术造诣": 0.10,
    "声望": 0.15,
    "百姓口碑": 0.20,
}

EVAL_OUTCOMES = [
    (85, "中兴"),
    (70, "守成"),
    (55, "治平"),
    (40, "昏聩"),
    (0,  "身死国灭"),
]

# ============================================================
# 名人档案已迁出至独立模块：content/ministers
# （大臣数量会持续扩充，且需绑定个人立绘，故单列文件夹管理）
# ============================================================

# ============================================================
# 个人行动效果
# ============================================================
PERSONAL_ACTIONS = {
    "勤政": {
        "bandwidth_bonus": 2,
        "prestige_gain": 3,
        "health_cost": 2,
        "desc": "批阅奏章、召对大臣，增加圣旨带宽与皇威"
    },
    "书画翰墨": {
        "art_gain": 3,
        "prestige_gain": 1,
        "desc": "挥毫泼墨、吟诗作画，提升艺术造诣"
    },
    "崇道修醮": {
        "taoism_gain": 4,
        "treasury_cost": 50000,
        "clergy_satisfaction": 5,
        "desc": "设醮祈福、召见方士，增僧道满意度但耗财"
    },
    "享乐宴游": {
        "health_cost": 5,
        "pleasure_gain": 4,
        "treasury_cost": 80000,
        "desc": "大宴群臣、游幸园林，损健康耗国帑"
    },
}

# ============================================================
# 皇帝个人行动矩阵（言枢密契约 v2 + A15 史实素材，单一权威源）
# 结构：location -> mode -> action -> 行动定义
#   label     三标签：史实 / 合理推演 / 玩法抽象（防捏造史实）
#   desc      行动说明（UI 与叙事用）
#   base_cost 程序基础开销（贯；AI 不写数值，守恒走此通道）
#   fund      资源通道：treasury=公开大驾（国库）/ imperial_treasury=微服便服（内帑）
#   risk      默认风险档（低/中/高；AI 契约可覆盖）
#   era_gate  时代门槛（年份，None=不限；艮岳1117/延福宫1113/上清宝箓宫1117/东幸镇江1126）
#   prep      公开出京准备期月数（与 prepared 联动：实际 = prep - (1 if prepared else 0)，即 1~2 月）
#   distance  微服他地距离核算（True 时按目标路距离档定装备月数）
#   micro_once 微服京城每月 1 次（程序按回合计数限）
#   base_effects 程序兜底效果（数值；AI 契约失败时以此落地，不伪造 AI 文本）
# 注：effects 落地白名单 = prestige / population_satisfaction / emperor_health /
#     art_mastery / taoism_leaning / pleasure_leaning / factions.*.satisfaction /
#     decree_bandwidth（bandwidth_bonus），与 state_applier 白名单对齐。
# ============================================================
IMPERIAL_LOCATIONS = ("宫里", "京城", "出京")
IMPERIAL_MODES = ("公开", "微服")
IMPERIAL_RISK_LEVELS = ("低", "中", "高")
# 风险概率（程序掷定）：低 2% / 中 8% / 高 20%
IMPERIAL_RISK_PROB = {"低": 0.02, "中": 0.08, "高": 0.20}

IMPERIAL_ACTION_MATRIX = {
    "宫里": {
        "公开": {
            "临朝": {
                "label": "史实", "desc": "临朝视事、批阅奏章、召对大臣",
                "base_cost": 0, "fund": "treasury", "risk": "低", "era_gate": None,
                "base_effects": {"bandwidth_bonus": 2, "prestige": 3, "emperor_health": -2},
            },
            "书画翰墨": {
                "label": "史实", "desc": "挥毫泼墨、吟诗作画，提升艺术造诣",
                "base_cost": 0, "fund": "treasury", "risk": "低", "era_gate": None,
                "base_effects": {"art_mastery": 3, "prestige": 1},
            },
            "崇道修醮": {
                "label": "史实", "desc": "设醮祈福、召见方士，增道门与皇威",
                "base_cost": 50000, "fund": "treasury", "risk": "低", "era_gate": None,
                "base_effects": {"taoism_leaning": 4, "faction_change": {"新党": 3}},
            },
            "宴游享乐": {
                "label": "史实", "desc": "大宴群臣、游幸园林，损健康耗国帑",
                "base_cost": 80000, "fund": "treasury", "risk": "低", "era_gate": None,
                "base_effects": {"emperor_health": -5, "pleasure_leaning": 4},
            },
        },
        "微服": {},   # 宫里无微服（跨格子非法）
    },
    "京城": {
        "公开": {
            "幸艮岳": {
                "label": "史实", "desc": "游幸艮岳万岁山，御制《艮岳记》（政和七年始筑）",
                "base_cost": 300000, "fund": "treasury", "risk": "低", "era_gate": 1117,
                "base_effects": {"pleasure_leaning": 3, "population_satisfaction": -2},
            },
            "延福宫宴游": {
                "label": "史实", "desc": "延福宫宴游，与近臣赋诗观花（政和三年建）",
                "base_cost": 150000, "fund": "treasury", "risk": "低", "era_gate": 1113,
                "base_effects": {"pleasure_leaning": 2, "art_mastery": 1},
            },
            "上清宝箓宫": {
                "label": "史实", "desc": "幸上清宝箓宫，会道士二千余人（政和七年）",
                "base_cost": 100000, "fund": "treasury", "risk": "低", "era_gate": 1117,
                "base_effects": {"taoism_leaning": 3, "prestige": 1},
            },
        },
        "微服": {
            "微行市井": {
                "label": "史实(方向)+合理推演", "desc": "微服夜行汴京街市酒肆（传闻细节为推演）",
                "base_cost": 20000, "fund": "imperial_treasury", "risk": "高", "era_gate": None,
                "micro_once": True, "base_effects": {"prestige": -1},
            },
            "微行大臣府第": {
                "label": "史实", "desc": "微服过近臣第宅（《宋史·王黼传》载微行过其家）",
                "base_cost": 10000, "fund": "imperial_treasury", "risk": "中", "era_gate": None,
                "micro_once": True, "base_effects": {"prestige": 1},
            },
        },
    },
    "出京": {
        "公开": {
            "巡幸东南": {
                "label": "合理推演", "desc": "大驾巡幸东南（正史无成行，标推演）",
                "base_cost": 500000, "fund": "treasury", "risk": "中", "era_gate": None,
                "prep": 2, "bandwidth_cost": 1,
                "base_effects": {"prestige": 2, "population_satisfaction": -1},
            },
            "东幸镇江": {
                "label": "史实(避难)", "desc": "金军南下时东幸镇江避兵（靖康元年起）",
                "base_cost": 300000, "fund": "treasury", "risk": "高", "era_gate": 1126,
                "prep": 1, "bandwidth_cost": 1,
                "base_effects": {"prestige": -5, "population_satisfaction": -3},
            },
        },
        "微服": {
            "微服他地": {
                "label": "合理推演", "desc": "微服往他州路察访民情（近当月来回/中备1月/远备2月）",
                "base_cost": 50000, "fund": "imperial_treasury", "risk": "中", "era_gate": None,
                "distance": True, "base_effects": {"population_satisfaction": 2},
            },
        },
    },
}

# 微服他地距离档 → 装备月数（近=当月来回 / 中=装备1月 / 远=装备2月）
IMPERIAL_DISTANCE_MONTHS = {"近": 0, "中": 1, "远": 2}
# 目标路名 → 距离档（关键词前缀匹配；未命中默认「中」）
IMPERIAL_ROUTE_DISTANCE = {
    "近": ("开封", "京畿", "京西", "京东"),
    "中": ("河北", "河东", "淮南", "京西南", "京西北", "京东南", "京东北"),
    "远": ("陕西", "江南", "两浙", "荆湖", "四川", "广南", "福建", "燕云", "永兴", "秦凤"),
}


def imperial_distance(target: str) -> str:
    """目标州路名 → 距离档（近/中/远）；未识别默认「中」。"""
    t = str(target or "")
    for dist, kws in IMPERIAL_ROUTE_DISTANCE.items():
        if any(k in t for k in kws):
            return dist
    return "中"


def imperial_prep_months(location: str, mode: str, action: str,
                         prepared: bool = False, target: str = "") -> int:
    """行动准备期（月）：
    - 公开出京：prep 基础月数 - (1 if prepared) → 1~2 月（pending_imperial_trip 月度推进）；
    - 微服他地：按目标路距离档定装备月数（近0/中1/远2）；
    - 其余（宫里/京城）：0（当月生效）。
    """
    cell = IMPERIAL_ACTION_MATRIX.get(location, {}).get(mode, {}).get(action) or {}
    if cell.get("distance"):
        return IMPERIAL_DISTANCE_MONTHS.get(imperial_distance(target), 1)
    if location == "出京" and mode == "公开":
        return max(1, int(cell.get("prep", 2)) - (1 if prepared else 0))
    return 0


# 皇帝个人行动 AI 契约 v2 effects 键 → 落地维度（与 state_applier 白名单 path 对齐）
IMPERIAL_EFFECT_DIM = {
    "威望": "prestige",
    "民心": "population_satisfaction",
    "健康": "emperor_health",
    "心情": "pleasure_leaning",   # 心情 → 享乐/心情倾向（0~100）
}
# 0~100 刻度维度的档位基准（prestige/民心 走 ai.client_utils._TIER_BASE 同源换算）
IMPERIAL_EFFECT_BASE = {"emperor_health": 3.0, "pleasure_leaning": 3.0}

# 旧单值 personal_action → 宫里·公开 矩阵行动（旧档/旧 UI 通道迁移）
# 旧键以 PERSONAL_ACTIONS 为准（享乐宴游）；矩阵行动名为「宴游享乐」。
LEGACY_PERSONAL_ACTION_MAP = {
    "勤政": "临朝",
    "书画翰墨": "书画翰墨",
    "崇道修醮": "崇道修醮",
    "享乐宴游": "宴游享乐",
}


# 施政大项
MAJOR_POLICIES = [
    "设衙改制",   # 创设/调整衙门
    "科举改革",   # 调整科举制度
    "税务改革",   # 方田均税 / 调整税率
    "货币改革",   # 钱法/交子改革
    "军事改革",   # 军制/装备改革
    "外交大政",   # 和战/盟约
    "治河工程",   # 黄河治理专项
]

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



# ============================================================
# 六部衙门（中枢施政机构）
# ============================================================
YAMEN_LIST = ["吏部", "户部", "礼部", "兵部", "刑部", "工部"]
YAMEN_INFO = {
    "吏部": {"duty": "铨选官吏、考核黜陟", "faction": "旧党", "acts": ["整饬吏治", "裁汰冗员", "兴办科举"]},
    "户部": {"duty": "户口田赋、度支钱粮", "faction": "新党", "acts": ["清丈田亩", "减免田赋", "常平仓赈济"]},
    "礼部": {"duty": "礼仪祭祀、科举学校", "faction": "旧党", "acts": ["重开贡举", "兴修礼乐", "褒崇道教"]},
    "兵部": {"duty": "武官选授、舆图军籍", "faction": "西军", "acts": ["整练新军", "缮修兵甲", "置将练兵"]},
    "刑部": {"duty": "律令刑名、刑狱冤滞", "faction": "枢密", "acts": ["宽刑省狱", "修订刑统", "平反冤案"]},
    "工部": {"duty": "山泽沟洫、营造工役", "faction": "宦官", "acts": ["兴修水利", "营缮宫观", "开矿铸钱"]},
}


# ============================================================
# 地方州县（路·府·县）
# ============================================================
PREFECTURE_LIST = ["东京开封府", "京西路", "河北路", "河东", "陕西路", "两浙路", "江南东路", "江南西路", "荆湖南路", "福建路", "成都府路", "广南东路"]
# 宋本土十二概括路。
#   键为稳定 ID（不可改），name 为舆图与详情面板展示名（可由圣旨更名）。
# 路级亩产基准（石/亩/年，方案 C 分路差异化）：
#   北方旱作 1.0（京畿/腹里/缘边），南方稻作 2.5（财赋膏腴/沿海/天府）。
#   各路 grain（年总产，石/年）= land（田亩）× ROAD_YIELD[路] × (1 - CASH_CROP_RATE[路])；
#   丰歉/科技由 land["yield"] 动态放大。
ROAD_YIELD = {
    "东京开封府": 1.0, "京西路": 1.0, "河北路": 1.0, "河东": 1.0, "陕西路": 1.0,
    "两浙路": 2.5, "江南东路": 2.5, "江南西路": 2.5, "荆湖南路": 2.5,
    "福建路": 2.5, "成都府路": 2.5, "广南东路": 2.5,
}
# 经济作物占田（开局数据，按路×产物细分）：值为占该路田亩的比例。
#   盐/木/石/铁为矿冶山林（不占农田）；茶/桑(丝)/麻/蔗/果 占田。
#   北方旱作合计 10%（桑 5% + 麻 5%）、南方稻作桑茶蔗区合计 20%。
#   粮田率 = 1 - Σ(该路各产物占比)；grain = land × ROAD_YIELD × 粮田率。
CASH_CROP_LAND = {
    "东京开封府": {"silk": 0.05, "hemp": 0.05},
    "京西路":     {"silk": 0.05, "hemp": 0.05},
    "河北路":     {"silk": 0.05, "hemp": 0.05},
    "河东":       {"silk": 0.05, "hemp": 0.05},
    "陕西路":     {"silk": 0.05, "hemp": 0.05},
    "两浙路":     {"silk": 0.07, "tea": 0.05, "cane": 0.04, "hemp": 0.02, "fruit": 0.02},
    "江南东路":   {"silk": 0.07, "tea": 0.05, "cane": 0.04, "hemp": 0.02, "fruit": 0.02},
    "江南西路":   {"silk": 0.06, "tea": 0.06, "cane": 0.03, "hemp": 0.03, "fruit": 0.02},
    "荆湖南路":   {"silk": 0.06, "tea": 0.06, "cane": 0.03, "hemp": 0.03, "fruit": 0.02},
    "福建路":     {"silk": 0.04, "tea": 0.07, "cane": 0.06, "hemp": 0.01, "fruit": 0.02},
    "成都府路":   {"silk": 0.06, "tea": 0.07, "cane": 0.02, "hemp": 0.03, "fruit": 0.02},
    "广南东路":   {"silk": 0.04, "tea": 0.04, "cane": 0.08, "hemp": 0.02, "fruit": 0.02},
}
PREFECTURE_INFO = {
    # 字段说明（经济全浮动重构新增）：
    #   grain       年总产(石/年) = land × ROAD_YIELD[路]（口径：年产，不再有 ×12 的 grain_yield）
    #   yields       dict: 七维物资年产量初值(开局写死，随政策/市舶/工程/劝农演化)。单位：
    #               salt/tea/iron/cane/fruit=斤、silk/hemp=匹、timber=根、stone=方；盐为榷盐产能、铁为铁矿冶铁
    #   officials    官数 = round(households×0.00135)（在籍明户 2000 万 → 全国约 2.7 万官）
    #   clerks       吏数 = officials×CLERK_PER_OFFICIAL(8)
    #   route_mult   路级乘数(二税折色)
    "东京开封府": {"name": "东京开封府", "households": 1_661_662, "land": 42_000_000, "grain": 37_800_000, "mood": 62, "govern": 60,
                "population": 6_646_648, "unrest": 12, "monthly_tax": 460_000, "hidden_land": 10_500_000,
                "storage": 5_400_000, "type": "京畿要地", "is_capital": True,
                "route_mult": 1.05,
                "yields": {"salt": 0, "tea": 0, "silk": 1_000_000, "hemp": 500_000, "cane": 0, "fruit": 500_000, "timber": 200_000, "stone": 300_000, "iron": 0}},
    "京西路": {"name": "京西", "households": 1_081_081, "land": 30_000_000, "grain": 27_000_000, "mood": 60, "govern": 58,
                "population": 4_324_324, "unrest": 14, "monthly_tax": 280_000, "hidden_land": 7_500_000,
                "storage": 3_300_000, "type": "腹里州路", "is_capital": False,
                "route_mult": 1.0,
                "yields": {"salt": 0, "tea": 0, "silk": 500_000, "hemp": 3_000_000, "cane": 0, "fruit": 500_000, "timber": 500_000, "stone": 500_000, "iron": 500_000}},
    "河北路": {"name": "河北", "households": 1_821_822, "land": 48_000_000, "grain": 43_200_000, "mood": 55, "govern": 55,
                "population": 7_287_288, "unrest": 24, "monthly_tax": 400_000, "hidden_land": 12_000_000,
                "storage": 3_800_000, "type": "缘边重镇", "is_capital": False,
                "route_mult": 0.95,
                "yields": {"salt": 18_000_000, "tea": 0, "silk": 2_000_000, "hemp": 2_000_000, "cane": 0, "fruit": 1_000_000, "timber": 500_000, "stone": 800_000, "iron": 4_000_000}},
    "河东": {"name": "河东", "households": 1_201_201, "land": 31_000_000, "grain": 27_900_000, "mood": 58, "govern": 57,
                "population": 4_804_804, "unrest": 19, "monthly_tax": 260_000, "hidden_land": 7_750_000,
                "storage": 2_900_000, "type": "缘边重镇", "is_capital": False,
                "route_mult": 0.95,
                "yields": {"salt": 70_000_000, "tea": 0, "silk": 500_000, "hemp": 1_000_000, "cane": 0, "fruit": 500_000, "timber": 800_000, "stone": 1_000_000, "iron": 2_500_000}},
    "陕西路": {"name": "陕西", "households": 1_561_562, "land": 45_000_000, "grain": 40_500_000, "mood": 50, "govern": 52,
                "population": 6_246_248, "unrest": 30, "monthly_tax": 320_000, "hidden_land": 11_250_000,
                "storage": 3_000_000, "type": "缘边重镇", "is_capital": False,
                "route_mult": 0.95,
                "yields": {"salt": 3_000_000, "tea": 0, "silk": 500_000, "hemp": 1_000_000, "cane": 0, "fruit": 500_000, "timber": 600_000, "stone": 1_000_000, "iron": 500_000}},
    "两浙路": {"name": "两浙", "households": 2_482_482, "land": 52_000_000, "grain": 104_000_000, "mood": 66, "govern": 68,
                "population": 9_929_928, "unrest": 8, "monthly_tax": 780_000, "hidden_land": 13_000_000,
                "storage": 8_800_000, "type": "财赋膏腴", "is_capital": False,
                "route_mult": 1.0,
                "yields": {"salt": 25_000_000, "tea": 8_000_000, "silk": 5_000_000, "hemp": 1_000_000, "cane": 3_000_000, "fruit": 2_000_000, "timber": 1_000_000, "stone": 500_000, "iron": 0}},
    "江南东路": {"name": "江南东", "households": 2_242_242, "land": 49_000_000, "grain": 98_000_000, "mood": 64, "govern": 65,
                "population": 8_968_968, "unrest": 10, "monthly_tax": 700_000, "hidden_land": 12_250_000,
                "storage": 8_000_000, "type": "财赋膏腴", "is_capital": False,
                "route_mult": 1.0,
                "yields": {"salt": 30_000_000, "tea": 6_000_000, "silk": 4_000_000, "hemp": 1_000_000, "cane": 1_000_000, "fruit": 1_000_000, "timber": 1_500_000, "stone": 500_000, "iron": 0}},
    "江南西路": {"name": "江南西", "households": 2_102_102, "land": 47_000_000, "grain": 94_000_000, "mood": 63, "govern": 64,
                "population": 8_408_408, "unrest": 11, "monthly_tax": 640_000, "hidden_land": 11_750_000,
                "storage": 7_600_000, "type": "财赋膏腴", "is_capital": False,
                "route_mult": 1.0,
                "yields": {"salt": 5_000_000, "tea": 6_000_000, "silk": 3_000_000, "hemp": 1_000_000, "cane": 500_000, "fruit": 1_000_000, "timber": 2_000_000, "stone": 500_000, "iron": 1_500_000}},
    "荆湖南路": {"name": "荆湖", "households": 1_521_522, "land": 36_000_000, "grain": 72_000_000, "mood": 60, "govern": 56,
                "population": 6_086_088, "unrest": 18, "monthly_tax": 360_000, "hidden_land": 9_000_000,
                "storage": 4_300_000, "type": "腹里州路", "is_capital": False,
                "route_mult": 1.0,
                "yields": {"salt": 2_000_000, "tea": 4_000_000, "silk": 1_000_000, "hemp": 2_000_000, "cane": 500_000, "fruit": 500_000, "timber": 2_000_000, "stone": 500_000, "iron": 0}},
    "福建路": {"name": "福建", "households": 1_401_401, "land": 26_000_000, "grain": 52_000_000, "mood": 61, "govern": 59,
                "population": 5_605_604, "unrest": 13, "monthly_tax": 420_000, "hidden_land": 6_500_000,
                "storage": 4_000_000, "type": "沿海市舶", "is_capital": False,
                "route_mult": 1.0,
                "yields": {"salt": 8_000_000, "tea": 4_000_000, "silk": 1_000_000, "hemp": 500_000, "cane": 4_000_000, "fruit": 3_000_000, "timber": 1_500_000, "stone": 500_000, "iron": 1_000_000}},
    "成都府路": {"name": "川峡", "households": 1_761_762, "land": 39_000_000, "grain": 78_000_000, "mood": 65, "govern": 66,
                "population": 7_047_048, "unrest": 12, "monthly_tax": 520_000, "hidden_land": 9_750_000,
                "storage": 6_200_000, "type": "天府沃野", "is_capital": False,
                "route_mult": 1.0,
                "yields": {"salt": 12_000_000, "tea": 6_000_000, "silk": 3_000_000, "hemp": 1_000_000, "cane": 2_000_000, "fruit": 2_000_000, "timber": 2_000_000, "stone": 500_000, "iron": 0}},
    "广南东路": {"name": "广南", "households": 1_161_161, "land": 23_000_000, "grain": 46_000_000, "mood": 58, "govern": 53,
                "population": 4_644_644, "unrest": 20, "monthly_tax": 340_000, "hidden_land": 5_750_000,
                "storage": 2_800_000, "type": "沿海市舶", "is_capital": False,
                "route_mult": 1.0,
                "yields": {"salt": 12_000_000, "tea": 1_000_000, "silk": 1_000_000, "hemp": 2_000_000, "cane": 5_000_000, "fruit": 3_000_000, "timber": 1_500_000, "stone": 500_000, "iron": 0}},
}

# ============================================================
# 外部政权（31 个）
#   与宋本土同构字段，另含 growth_curve（发育曲线，乘以难度 external_growth 生效）。
#   仅做简单模拟：按曲线缓变 power / population / storage。
# ============================================================
def _ext(name: str, typ: str, hotspot: tuple[float, float, float, float],
         power: int, population: int, storage: int, expansion: float,
         power_growth: float, attitude: int = 50, monthly_tax: int = 0,
         land: int = 0, grain: int = 0
         ) -> dict[str, str | int | tuple[float, float, float, float] | dict[str, float]]:
    d = {
        "name": name, "type": typ, "hotspot": hotspot,
        "power": power, "attitude": attitude, "internal_pressure": 20,
        "population": population, "unrest": 15,
        "monthly_tax": monthly_tax or max(4, power // 6),
        "land": land or population * 8,
        "hidden_land": (land or population * 8) // 8,
        "grain": grain or population * 2,
        "storage": storage,
        "growth_curve": {"expansion": expansion, "power_growth": power_growth},
    }
    return d


# ============================================================
# 外部势力省份（史翰青素材 A12：辽 5 京道 / 夏 2 州 + 其余本部）
#   {势力: [(省名, 权重), ...]}——派生：人口/月税按权重分摊（省为展示层，不落独立状态）
# ============================================================
EXTERNAL_PROVINCES = {
    "辽": [("南京道", 0.30), ("东京道", 0.20), ("上京道", 0.25), ("西京道", 0.15), ("中京道", 0.10)],
    "西夏": [("兴庆府", 0.60), ("西平府", 0.40)],
    "金": [("上京会宁", 0.55), ("黄龙府", 0.45)],
    "高丽": [("开京", 0.50), ("西京平壤", 0.30), ("东京开城", 0.20)],
    "大理": [("大理", 0.55), ("善阐", 0.45)],
    "日本": [("京都", 0.40), ("镰仓", 0.35), ("九州", 0.25)],
    # 其余势力（本部单一省）
}
_EXTERNAL_PROVINCES_DEFAULT = [("本部", 1.0)]


EXTERNAL_REGIMES = {
    # —— 北方与西北 ——
    "辽":       _ext("辽", "游牧帝国", (0.6828, 0.3829, 0.1406, 0.125), 75, 380, 520, 0.030, 0.045),
    "西夏":       _ext("西夏", "党项蕃国", (0.3921, 0.4088, 0.0625, 0.0729), 55, 160, 240, 0.020, 0.035),
    "吐蕃":       _ext("吐蕃", "高原诸部", (0.3066, 0.5356, 0.1719, 0.1458), 40, 120, 150, 0.008, 0.012),
    "喀尔喀蒙古":       _ext("喀尔喀蒙古", "漠北游牧", (0.4373, 0.3381, 0.1406, 0.1042), 30, 70, 90, 0.030, 0.050),
    "漠南蒙古":       _ext("漠南蒙古", "漠南游牧", (0.5408, 0.3731, 0.0781, 0.0625), 28, 60, 80, 0.028, 0.045),
    "科尔沁":       _ext("科尔沁", "东蒙部族", (0.6859, 0.3335, 0.0625, 0.0521), 22, 45, 55, 0.022, 0.035),
    "察哈尔":       _ext("察哈尔", "蒙古本部", (0.58, 0.3752, 0.0625, 0.0625), 26, 52, 65, 0.025, 0.040),
    "海西":       _ext("海西", "女真诸部", (0.7588, 0.2745, 0.0625, 0.0625), 18, 32, 40, 0.030, 0.055),
    "建州":       _ext("建州", "女真诸部", (0.7343, 0.3836, 0.0547, 0.0625), 20, 35, 45, 0.035, 0.065),
    "东海":       _ext("东海", "女真诸部", (0.8031, 0.1769, 0.0547, 0.0521), 14, 25, 30, 0.026, 0.048),
    # —— 东方 ——
    "高丽":       _ext("高丽", "东方藩属", (0.7348, 0.4056, 0.0469, 0.0521), 35, 150, 180, 0.010, 0.018),
    "日本":       _ext("日本", "海东岛国", (0.8533, 0.5214, 0.0625, 0.1042), 38, 200, 260, 0.012, 0.022),
    "琉球":       _ext("琉球", "海岛番社", (0.7764, 0.6177, 0.0234, 0.0312), 8, 12, 15, 0.006, 0.010),
    # —— 西南与南方 ——
    "大理":       _ext("大理", "西南属国", (0.4175, 0.6326, 0.0625, 0.0625), 30, 90, 110, 0.008, 0.014),
    "安南":       _ext("安南", "交趾属国", (0.4889, 0.6834, 0.0469, 0.0521), 28, 85, 100, 0.014, 0.024),
    "占城":       _ext("占城", "南海小国", (0.5479, 0.7552, 0.0234, 0.0312), 15, 40, 45, 0.008, 0.012),
    "真腊":       _ext("真腊", "南海小国", (0.5304, 0.7815, 0.0312, 0.0417), 20, 55, 60, 0.009, 0.014),
    "暹罗":       _ext("暹罗", "南海小国", (0.5025, 0.7503, 0.0391, 0.0417), 22, 60, 70, 0.011, 0.017),
    "缅甸":       _ext("缅甸", "西南邻国", (0.3829, 0.6977, 0.0469, 0.0521), 24, 70, 80, 0.010, 0.016),
    "喜马拉雅山南诸国":       _ext("喜马拉雅山南诸国", "山南列邦", (0.1901, 0.6377, 0.0938, 0.0521), 12, 35, 35, 0.005, 0.008),
    # —— 中亚南亚边缘（替换晚于北宋的政权为同时代势力）——
    "注辇":       _ext("注辇", "南印度大国", (0.0626, 0.6284, 0.0938, 0.125), 45, 260, 300, 0.014, 0.024),
    "身毒":       _ext("身毒", "天竺诸邦", (0.05, 0.60, 0.10, 0.12), 40, 240, 280, 0.012, 0.022),
    "蒲甘":       _ext("蒲甘", "西南属国", (0.38, 0.69, 0.05, 0.05), 25, 75, 85, 0.010, 0.016),
    "大越":       _ext("大越", "交趾李朝", (0.48, 0.68, 0.05, 0.05), 30, 90, 110, 0.014, 0.024),
    "占婆":       _ext("占婆", "南海古国", (0.54, 0.75, 0.03, 0.03), 16, 42, 48, 0.008, 0.012),
    "吴哥":       _ext("吴哥", "高棉帝国", (0.53, 0.78, 0.04, 0.04), 28, 80, 95, 0.010, 0.016),
    "罗斛":       _ext("罗斛", "暹罗列邦", (0.50, 0.75, 0.04, 0.04), 22, 60, 70, 0.011, 0.017),
    "澜沧":       _ext("澜沧", "中南部族", (0.51, 0.70, 0.04, 0.05), 18, 50, 60, 0.009, 0.015),
    "三佛齐":     _ext("三佛齐", "南海大国", (0.52, 0.88, 0.04, 0.04), 36, 160, 200, 0.015, 0.025),
    "西辽":       _ext("西辽", "喀喇契丹", (0.0535, 0.2669, 0.0938, 0.125), 26, 55, 65, 0.018, 0.028),
    "高昌回鹘":       _ext("高昌回鹘", "西域汗国", (0.117, 0.4287, 0.0781, 0.0833), 24, 50, 60, 0.012, 0.020),
    "喀喇汗":       _ext("喀喇汗", "西域汗国", (0.18, 0.46, 0.07, 0.088), 28, 52, 62, 0.013, 0.021),
    "汪古部":       _ext("汪古部", "漠北部族", (0.3363, 0.4714, 0.0625, 0.0833), 22, 42, 50, 0.020, 0.032),
    # —— 南洋群岛 ——
    "吕宋":       _ext("吕宋", "南洋岛国", (0.6753, 0.7518, 0.0312, 0.0312), 10, 20, 22, 0.006, 0.010),
    "柔佛":       _ext("柔佛", "南洋岛国", (0.5514, 0.8663, 0.0312, 0.0312), 12, 24, 28, 0.007, 0.011),
    "苏门答剌":       _ext("苏门答剌", "南洋岛国", (0.5225, 0.8809, 0.0391, 0.0312), 14, 30, 34, 0.007, 0.012),
    "婆罗":       _ext("婆罗", "南洋岛国", (0.6526, 0.8998, 0.0469, 0.0417), 11, 22, 25, 0.006, 0.010),
    "爪哇":       _ext("爪哇", "南洋岛国", (0.6471, 0.9596, 0.0469, 0.0312), 18, 48, 55, 0.008, 0.013),
    "美洛居":       _ext("美洛居", "香料群岛", (0.8102, 0.9409, 0.0312, 0.0312), 8, 12, 16, 0.005, 0.009),
    "渤泥":       _ext("渤泥", "婆罗洲岛国", (0.9964, 1.0, 0.0625, 0.0833), 5, 8, 8, 0.003, 0.005)
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
)
# free_effect 单字段封顶（CAP，防 AI 提议越权量级）：字段 → (上限值)（与 ai/client_utils._TIER_CAP 对齐并扩展）
FREE_EFFECT_CAP = {
    "prestige": 12, "treasury": 3_000_000, "population_satisfaction": 10,
    "external_jin": 12, "external_liao": 12, "external_xixia": 12,
    "defense_bonus": 10, "tech": 10, "art_mastery": 10, "army": 10,
    "finance": 3_000_000, "talent": 10,
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


# ============================================================
# 田亩户籍总览
# ============================================================
LAND_INFO = {
    "cultivated": 460_000_000,       # 垦田（亩）
    "households": 20_000_000,        # 在籍明户（户）——12 路 PREFECTURE_INFO.households 合计即此值
    "hidden_households": 5_000_000,  # 隐户（户，不在籍，UI 不显示；设计锚：总户 2500 万 = 明 2000 万 + 隐 500 万，总口 1 亿）
    "hidden_rate": 0.35,             # 田赋隐漏率（税收口径，与隐户人口锚不同维）
    "wasteland": 80_000_000,         # 荒田（亩）
    "yield": 1.0,                    # 亩产系数
}


# ============================================================
# 金融 / 货币 / 市舶 / 交子 / 官营机构（扩展维度）
# ============================================================
JIAOZI_INFO = {
    "issued": 0,          # 已发交子（贯）
    "trust": 60,          # 纸币信用（0~100）
    "reserve": 2_000_000, # 本钱准备（贯）
    # ---- 界制（T9 物价方案定稿·蔡权衡）：交子一界 36 回合，换界 5% 工墨费销毁 ----
    "term": 36,           # 一界回合数（JIAOZI_TERM）
    "cycle": 0,           # 当前界数（每换一界 +1）
    "age": 0,             # 当前界已行用回合数（达 term 触发换界）
    "redeemed_total": 0,  # 累计换界销毁（贯，statistics 口径）
}
# 交子界制常量（T9 定稿）：换界销毁为**销币通道**（回收流通货币，抑通胀）
JIAOZI_TERM = 36            # 一界回合数
JIAOZI_REDEEM_FEE = 0.05    # 换界工墨费比例（换界时按在发额 5% 销毁）
MARITIME_INFO = {
    "open": False,        # 市舶司是否广开
    "tariff": 0.10,       # 舶税税率（抽解率）
    "silver_in": 30,      # 海外白银流入（万两/年，基准）
}
# 市舶独立税源：海外贸易年总额（贯/年，基准）。市舶抽解是关税，税基为进出口贸易额，
# 与国内工商税基（生产流通总量）并列，二者是不同税源，而非放大关系。
MARITIME_TRADE_BASE = 20_000_000   # 广开市舶基准 2000万贯/年，随科技(造船/航海)/工业(商品供给)增长
COIN_INFO = {
    "shortage": 0.30,     # 钱荒程度（0~1，越高越荒）
    "private_melt": 0.10, # 铜钱私铸/外流比例（T9 定稿 0.2→0.1；熔化走 MELT_RATE 真实化）
}
# ---- 私铸熔化真实化（T9 定稿）：POP 铜钱 wealth 逐月真实熔化扣减 ----
MELT_RATE = 0.001         # 民间铜钱熔化率（/月，wealth 0.1% 扣减，退出流通）

# ---- 经济金融推演基准（蔡权衡定稿，接档位词丰富 7 档）----
# economy_decide 扩展 5 金融字段：AI 只给三态词（增/稳/跌、缓/平/加剧、兴/平/衰、
# 扩/稳/损、通胀/平/通缩），数值由程序按此基准换算并 CAP 封顶。
FINANCE_DECIDE_BASE = {
    "jiaozi_trust": {"cap": 5},          # 交子信任 增/跌 → trust ±5
    "jiaozi_issued": {"cap": 1_000_000}, # 交子发行 增 → issued +100万（≤可发额度，超发触发既有崩溃）
    "shortage": {"cap": 0.05},           # 钱荒 缓/加剧 → shortage ±0.05（clamp [0.05,0.95]）
    "tariff": {"cap": 0.02},             # 市舶 兴/衰 → tariff ±0.02（clamp [0.05,0.20]）
    "silver_in": {"cap": 10},            # 市舶白银 silver_in ±10（clamp [10,60] 万两/年）
    "bank_capital": {"cap": 0.20},       # 银行 扩/损 → capital ±20%（仅 established）
    "bank_reserve": {"cap": 500_000},    # 银行 reserve +50万
    "price_mult": {"cap": 0.05},         # 价格系数 ±5%（挂 calc_price_level ×mult，clamp [0.5,3.0]）
}
# 三态词白名单（金融字段）
FINANCE_STATES = {
    "jiaozi_trust": ("增", "稳", "跌"),
    "shortage": ("缓", "平", "加剧"),
    "maritime": ("兴", "平", "衰"),
    "bank": ("扩", "稳", "损"),
    "price_trend": ("通胀", "平", "通缩"),
}
BANK_INFO = {
    "established": False, # 是否设立官营银行（如检校库/交子务升级）
    "capital": 0,         # 官营资本（万贯）
}
STANDARD_INFO = {
    # 金银铜三品本位：铜钱基准，银一两≈铜钱一贯，金一两≈铜钱十贯（示意）
    "silver_per_copper": 1.0,   # 银一两合铜钱（贯）
    "gold_per_copper": 10.0,    # 金一两合铜钱（贯）
}
FINANCE_ACTS = ["行交子", "榷货市舶", "设银行", "定金银铜三品本位", "平抑物价", "铸铁钱"]

# ============================================================
# 仓廪漕运（实物粮最小单位：石，已去「万」）——「仓廪虚实，系乎国运」
# ============================================================
GRANARY_START = 15_000_000     # 中央粮仓（太仓）初始存粮 (石)
GRANARY_START_CAP = 20_000_000 # 中央仓初始容量 (石)，可经"新建仓储"工程扩建
GRANARY_CAP_SOFT = 150_000_000 # 仓储扩建软上限 (石)

# 开局各路米价（按"京畿边镇贵、膏腴贱"原则硬编码，避免全 1.0 平庸）
# 后续由 calc_region_grain_price 每月按供需比动态调整，此处仅给开局变量。
PREFECTURE_INITIAL_GRAIN_PRICE = {
    "京畿要地":   1.30,   # 东京开封府
    "缘边重镇":   1.25,   # 河北/河东/陕西
    "沿海市舶":   1.10,   # 福建
    "财赋膏腴":   0.85,   # 两浙/江南东/江南西
    "天府沃野":   0.90,   # 川峡
    "腹里州路":   1.00,   # 京西/荆湖/广南
}

# ---- 大臣家产（言枢密设计 + 蔡权衡数值；基线用史翰青 1101 开局，钱贯/田亩）----
# 1101 年六贼多在野未起用，家产远小于靖康籍没时——蔡京 3万/800 殷实起步（崇宁后膨胀），
# 朱勔 3万/1500（苏州富室），韩忠彦/曾布 在朝相臣较厚；陈瓘 清贫。存档序列化 state.minister_estate。
ESTATE_INIT = {
    "蔡京": {"wealth": 30_000, "land": 800},
    "童贯": {"wealth": 20_000, "land": 300},
    "王黼": {"wealth": 5_000, "land": 100},
    "朱勔": {"wealth": 30_000, "land": 1_500},
    "韩忠彦": {"wealth": 50_000, "land": 1_500},
    "曾布": {"wealth": 60_000, "land": 2_000},
    "陈瓘": {"wealth": 5_000, "land": 80},
    "李纲": {"wealth": 10_000, "land": 300},
    "种师道": {"wealth": 15_000, "land": 500},
    "杨戬": {"wealth": 20_000, "land": 400},
    "梁师成": {"wealth": 10_000, "land": 200},
    "蔡攸": {"wealth": 10_000, "land": 200},
    "高俅": {"wealth": 20_000, "land": 300},
    "余深": {"wealth": 20_000, "land": 600},
}
# 家产档位词（脱敏：玩家/AI 只见档位；数值程序管、展示管、AI 只叙事）
# 清贫<1万 / 小康≥1万 / 殷实≥3万 / 豪富≥10万 / 巨富≥50万（贯）
ESTATE_TIERS = (
    ("巨富", 500_000), ("豪富", 100_000), ("殷实", 30_000),
    ("小康", 10_000), ("清贫", 0),
)
# 膨胀机制（史翰青 1101 基线 → 靖康籍没锚点：杨戬「尚拥万金」、朱勔田「跨连郡县」）：
# 家产随年按 corruption 膨胀（俸禄基准 + 贪腐×系数）；封顶巨富上限（籍没锚点验证）
ESTATE_GROWTH_BASE = 0.001       # 月俸禄基准（家产 ×1‰）
ESTATE_GROWTH_CORRUPT = 0.05     # 月贪腐膨胀系数（家产 ×corruption×5%；杨戬 25 年→巨富锚点）
ESTATE_WEALTH_CAP = 50_000_000   # 封顶（巨富档上限，靖康籍没锚点）
# 家产钱的循环/田的循环（月流，程序守恒）
ESTATE_FLOW = {
    "salary_share": 0.20,      # 俸给划转家产比例（同步从官僚 POP wealth 扣，防双计）
    "luxury_rate": 0.01,       # 奢侈消费 = 家产×0.01×BOOM_MULT×奢侈系数（→工匠/商人）
    "hoard_rate": 0.30,        # 聚敛窖藏比例（→钱荒 shortage +）
    "rent_rate": 0.05,         # 田租月率（并入 gentry_land 增产量）
    "estate_tax_rate": 0.02,   # 田赋/免役钱比例（家产田 → 国库，守恒）
    "persona_rich": 1_000_000, # 家产≥100万 → 丰厚（危险度 +0.15）
    "persona_poor": 50_000,    # 家产≤5万 → 清贫（敢谏 +15%）
    "seize_land_rate": 0.5,    # 抄没田比例（→官田）
}
# 建筑标准（政府 projects output 扩展 + POP buildings；Lv1-5 ×1.5/级，成本 ×1.8^(Lv-1)，维护 ×0.5%/月）
BUILDING_STD = {
    "水利": {"base_cost": 200_000, "effect": "yield_bonus", "maintain": 0.005},
    "常平仓": {"base_cost": 150_000, "effect": "granary_cap", "maintain": 0.005},
    "官营作坊": {"base_cost": 300_000, "effect": "workshop_output", "maintain": 0.005},
    "官署": {"base_cost": 250_000, "effect": "decree_speed", "maintain": 0.005},
    "军营": {"base_cost": 400_000, "effect": "army_power", "maintain": 0.005},
    "学校": {"base_cost": 180_000, "effect": "exam_talent", "maintain": 0.005},
}
BUILDING_LEVEL_MULT = 1.5      # 每级效果 ×1.5
BUILDING_COST_GROWTH = 1.8     # 建造成本 ×1.8^(Lv-1)
BUILDING_EFFECT_CAP = 2.0      # 效果乘数封顶 ×2.0
POP_BUILDING_TYPES = ("农田", "工坊", "商铺", "庄园")   # POP 建筑（阶层 wealth 出资，Lv1-5，×0.05/Lv）
POP_BUILDING_EFFECT = 0.05     # 每级 ×0.05（封顶 ×2.0 由 BUILDING_EFFECT_CAP 统一）
# 投资（invest_decide 复用 free_effect 载体；六领域基准年回报/风险）
# 对齐（复用原有机制）：+科技领域（研发投入走既有投资通道，落地进 tech researching 加速）
INVEST_BASE = {
    "农业": {"return": 0.08, "risk": 0.15},
    "水利": {"return": 0.10, "risk": 0.10},
    "工坊": {"return": 0.12, "risk": 0.20},
    "商铺": {"return": 0.15, "risk": 0.25},
    "漕运": {"return": 0.10, "risk": 0.15},
    "军器": {"return": 0.18, "risk": 0.30},
    "科技": {"return": 0.0, "risk": 0.0, "rnd": True},   # 研发投入（无回报，加速 tech researching）
}
INVEST_FUND_SOURCES = ("treasury", "imperial_treasury")   # 资金来源：国库（会签/廷议执行率）/内帑（乾纲独断）
CANAL_MONTHLY_RATE = 0.90      # 漕运效率基准：每月把州府可输存粮的 90% 输往中央仓
MILITARY_GRAIN_MONTHLY = 600_000    # 军粮月耗 (石)，从中央仓支取（禁军/厢军/西军粮饷）
OFFICIAL_GRAIN_MONTHLY = 200_000    # 官俸本色禄米月耗 (石)，从中央仓支取
DISASTER_RELIEF_GRAIN = 200_000     # 单次开仓赈济耗粮 (石)
SPARROW_RAT = 0.012            # 雀鼠耗：存粮月自然损耗率（加消耗定案 1%→1.2%）
CANAL_LOSS_BASE = 0.06         # 漕运漂没基础损耗（加消耗定案 4%→6%）
CANAL_LOSS_CORRUPT_WEIGHT = 0.06  # 漕运侵盗损耗随押运官贪腐放大系数
LAND_TAX_RATE = 0.15           # 田赋本色率：月田赋 = 月粮产 × 15%（按粮产系统核算）

# 通货 / 物价（货币经济学，钱/物之比）
PRICE_LEVEL_BASE = 1.0         # 物价基准（钱/物之比 = 1）
PRICE_LEVEL_MIN = 0.5          # 物价下限（钱荒极深）

# ---- 新兵种（branch_registry 仿 tool_registry，玩家自由设立；言枢密契约 + 史翰青素材 + 蔡权衡数值）----
# 特化系数（蔡权衡定稿）：equip 1+0.67×档 封顶2.0 / 非特化降配 1−0.33×档 下限0.5、
# train 1+0.30×档 封顶1.75、position 场景表 +80%/−30%、cost 0.15/0.10/0.08
BRANCH_SPEC = {
    "specialize": {"equip": lambda t: min(2.0, 1 + 0.67 * t),     # t=档位指数 0~1.5
                   "train": lambda t: min(1.75, 1 + 0.30 * t)},
    "despecialize": {"equip": lambda t: max(0.5, 1 - 0.33 * t)},
    "position": {"平原": 0.8, "山地": -0.3, "水战": -0.3, "攻城": 0.3, "守城": 0.3,
                 "野战": 0.2, "巷战": -0.1},
    "cost": {"禁军": 0.15, "厢军": 0.10, "乡兵": 0.08},   # 招募成本系数（/人/月 粮饷基准）
}
# 装备单价（贯/件）：枪刀5/弓弩8/火器30/战马50/盔甲20/舟船16.7/器械15
EQUIP_PRICE = {"枪刀": 5, "弓弩": 8, "火器": 30, "战马": 50, "盔甲": 20,
               "舟船": 16.7, "器械": 15}
RECRUIT_MONTHS = 6            # 招募粮饷预支月数（成本 = Σ人数×(装备现值 + 粮饷×6月)）
# 新兵种封顶（蔡权衡定稿）：战力 ≤1.8×、粮饷 ≤2.0×、双方向、注册 ≤3
BRANCH_POWER_CAP = 1.8
BRANCH_PAY_CAP = 2.0
BRANCH_REGISTRY_MAX = 3
# 科技门槛（史实锚）：火器→gunpowder≥30/45/65/85、弓弩→弓弩工艺、战马→马政
BRANCH_TECH_GATE = {
    "gunpowder": (30, 45, 65, 85),     # 火器档位 1~4 → gunpowder 门槛
    "archery": 60,                     # 弓弩系
    "cavalry": 55,                     # 马政
}
# 史实锚兵种（史翰青 A12）：神臂弩/胜捷军/水虎翼 史实番号、拐子马金军、火器北宋史实；
# 赤心队待考禁用（不入锚）。
BRANCH_ANCHORS = ("神臂弩", "胜捷军", "水虎翼", "拐子马", "火器军")
PRICE_LEVEL_MAX = 3.0          # 物价上限（恶性通胀）
MONEY_SUPPLY_START = 200_000_000  # 货币有效供给初值（贯）：铜钱+有效交子+白银折钱。

# ---- 建筑-时代交互（言枢密方案，告别纯数值）----
# era_state 五维认知层（兴/平/衰，程序定幅迁移）：economy_center 财赋重心 /
# culture 文教 / commerce 商贸 / military 军备 / urban 都市化
ERA_DIMENSIONS = ("economy_center", "culture", "commerce", "military", "urban")
ERA_TREND_SHIFT = {"兴": 10, "平": 0, "衰": -10}    # 每档迁移幅度（0-100 刻度，程序定幅）
ERA_BUILDING_LINK = {          # 下行联动：建筑 → era 维度（乘数走既有公式，累积到 era）
    "水利": "economy_center", "常平仓": "economy_center",
    "学校": "culture", "市舶": "commerce", "码头": "commerce",
    "军营": "military", "城防": "military", "官营作坊": "commerce",
    "农田": "economy_center", "商铺": "commerce", "庄园": "economy_center",
}
ERA_UP_LINK = {                # 上行调制：国库/景气 → 建造速度/解锁
    "build_speed_boost": 1.3,  # 国库充足+景气中/大 → 建造速度 ×1.3
    "unlock_threshold": 60,    # economy_center/culture ≥60 → 新建筑解锁
}
# 科技-建筑映射（用户指示·建筑跟随科技）：节点/副指标 → 解锁建筑类型 + 阈值
# 史实锚：三舍法→太学/州学、火药→火器作坊、水利机械→水利设施、市舶法→市舶司、冶铁→铁作
# 科技没研出 → 建筑类型不可建/不出现（对齐「蓝图库只列现在真造得出的」设计）
TECH_BUILDING_MAP = {
    "hydraulics": ("水利", 30),          # 水利机械 ≥30 → 水利设施可建
    "gunpowder": ("火器作坊", 30),        # 火药 ≥30 → 火器作坊
    "iron": ("铁作", 30),                # 冶铁 ≥30 → 铁作
    "school_three_halls": ("学校", 40),   # 三舍法（level ≥40）→ 太学/州学
    "maritime_law": ("市舶司", 40),       # 市舶法（level ≥40）→ 市舶司
}
# 科技升级上限：建筑 Lv 上限 = f(科技等级)（level 0-100 → Lv1-6，clamp ≤5）
BUILDING_LEVEL_CAP_STEP = 20            # level 每 20 → +1 Lv
# ---- 新旧产业规模化（用户指示：产业属性 + 认知层感知 + 大臣立场）----
# 建筑新旧产业分类：旧产业（传统）/新产业（科技解锁，跟随科技落地）
INDUSTRY_CLASS = {
    "old": ("农田", "磨坊", "手工作坊", "传统织坊", "木帆船", "常平仓", "官署", "庄园", "商铺", "水利", "军营"),
    "new": ("重工业", "铁路", "商船货运", "机器局", "火器作坊", "市舶司", "铁作"),
}
# 产业结构认知层档位词（新产业占比 → 档位，脱敏：AI/大臣只见档位）
INDUSTRY_SHARE_TIERS = (
    ("新产业主导", 0.5), ("新旧并立", 0.25), ("新芽初萌", 0.1), ("纯旧产业", 0),
)
INDUSTRY_OLD_DECAY = 0.005   # 新产业兴起 → 旧产业相对衰落（月，转型阵痛）
# 校准说明：岁入缗钱 5000~6000 万贯（流量），流通货币存量须按周转 3~4 次反推约 1.5~2.5 亿贯，
# 否则"一年收税近 6000 万、流通仅 6000 万"会自相矛盾、把市场一年抽干。故存量取 2 亿贯。
# 货币流通速度：周转次数/年。税基抬升后若无流通速度，货币/实物比会骤跌、物价触底钱荒恶化，
# 故在物价公式中显式加入 PRICE_VELOCITY（≈1.8 次/年，与周转概念自洽）。
PRICE_VELOCITY = 1.8
TAX_COEFF_MIN = 0.75           # 纳税系数下限（钱荒税难征）
TAX_COEFF_MAX = 1.25           # 纳税系数上限（泉货充裕税易征）

# 俸禄/军饷制度（支出侧货币化演化）
PAY_SYSTEM_DEFAULT = {
    "mode": "本色折色",          # 本色折色 | 仅发钱 | 一体发钞 | 仅本色
    "grain_ratio": 0.5,          # 本色（禄米/军粮）占比
    "cash_ratio": 0.5,           # 折色（俸钱/饷钱）占比
}
# 俸禄总盘子（月度基准）：本色禄米+军粮 ≈ 80 万石（即 8e5 石），折色俸钱+饷钱 ≈ 200 万贯
PAY_GRANARY_BASE = 800_000      # 本色月度总盘子（石）= 军粮60万 + 禄米20万
PAY_CASH_BASE = 2_000_000       # 折色月度总盘子（贯）

# 漕运阻塞（0 通畅 ~ 100 阻塞）
CANAL_BLOCK_START = 10

# 一条鞭法（田赋改征银）与俸禄改革均为长期政务，无额外常量

# 区域粮价（贯/石）——按人口/产量供需，京畿边镇贵、膏腴贱
GRAIN_PRICE_MIN = 0.4
GRAIN_PRICE_MAX = 2.5
PER_CAPITA_MONTH_GRAIN = 0.5    # 人均月耗粮（石）**纯口粮口径**（种粮/酿酒/饲料/损耗已单列消耗，防双计）

# ---- 消费端校准（Phase B 定稿）：按职业口粮 + 隐户消费 + 商品消费率 + POP 流动 ----
GRAIN_CONSUME_PER_CAPITA = {"农": 0.5, "士绅": 0.5, "工匠": 0.4, "商人": 0.4, "官僚": 1.8, "兵": 1.5}  # 石/人/月
# 官僚 1.8 = 官2.7万×6石 + 吏21.6万×1.2石 加权 ≈1.73 → 取 1.8（家口折算，调参定案；禄粟本色 15 石仍不动）
OFFICIAL_SERVICE_TAX_RATIO = 0.05  # 官户免役钱比例（史实免役法：官户/形势户纳助役钱）= 官僚俸钱总额 × 此比例，入国库
# 加消耗方案（用户指示·生产过剩处理，亩产保持史实不改；完整定案修正：加工型消耗依托酒坊/畜栏建筑）
SEED_GRAIN_PER_MU = 0.065      # 种粮预留 = 耕地亩 × 此值 / 12（石/月，播种用；约 250万石/月，自然消耗）
FARMER_STORE_CAP = 12          # 农储粮上限（石/人）：超出部分按 FARMER_SPOIL_RATE 月霉耗核销（收敛 ~12石/人）
FARMER_SPOIL_RATE = 0.02       # 农超储霉耗率（/月，兜底防农存粮无限涨）
HIDDEN_CONSUME_PER_CAPITA = 0.4    # 隐户人均月耗粮（石/口/月）；隐户不落籍，由该路士绅/地主供给
GOODS_CONSUME_RATE = {"士绅": 0.05, "官僚": 0.03, "商人": 0.03, "工匠": 0.01, "兵": 0.02, "农": 0.010}  # 商品消费率（/月）；工匠 0.02→0.01（蔡权衡：防工匠破产）
# 工匠存货外销变现（蔡权衡裁决：goods 存量 > 库存上限 → 外销，goods 出 == 外部钱入，守恒）
GOODS_PRICE = {"布": 1, "绸": 3}          # 外销单价（贯/单位）
EXPORT_STOCK_MONTHS = 12                  # 库存上限 = 月产 × 12（超上限触发外销）
EXPORT_RATE = 0.3                         # 月外销 = 月产 × 0.3（min(存量-上限, 外销额)）
BOOM_MULT = {"无": 0.0, "微": 0.4, "小": 0.7, "中": 1.0, "大": 1.4, "巨": 1.8, "极": 2.2}
# 景气消费倍率（Phase B 定稿 + 审查 P1-3 修复）：消费/奢侈品按景气放大。
# 补无/巨/极 3 档，7 档闭合——原缺此 3 档时 AI 出「巨」被 .get(默认1.0) 静默降级为中性。
FARMER_SELL_FLOOR = 0.5            # 农最低供给份额：粮市撮合中农卖方权重保底（防农被挤出粮市）
POP_FLOW_RATE = {"城市化": 0.0008, "回乡": 0.0008, "科举": 0.0001}  # POP 流动基准（/月）
EXAM_HARD_POOR_SHARE = {"无": 0.0, "微": 0.3, "小": 0.5, "中": 0.7, "大": 0.9}  # 科举寒门（农）入仕占比
URBAN_SPLIT = {"工匠": 0.6, "商人": 0.4}  # 城市化净流入在工匠/商人间的分配

# ---- 俸禄指数化（T9 定稿·Step 4）：粮价 > 1.5 时俸禄 ×(1+0.1×超额) ----
PAY_INDEX_BASE = 1.5            # 粮价触发基准（高于此指数化）
PAY_INDEX_STEP = 0.1            # 超额每档系数（×0.1）

# 常平仓（区域粮价自动稳定器）
CHANGPING_HIGH = 1.6            # 粮价高于此则常平粜粮抑价
CHANGPING_LOW = 0.9             # 粮价低于此则常平籴粮托市（加消耗定案 0.6→0.9，收储托价扩容）
# ---- 常平扩容为货币稳定器（T9 定稿·蔡权衡）----
# 平粜吸买家钱入地方府库（货币回收，不碰内帑；local_treasury 不在 money 公式）
CHANGPING_CAP_RATIO = 1.0       # 常平仓容 = 月产 100%（原 50%）
CHANGPING_BUY_BUDGET_RATIO = 0.50  # 平籴预算 = 地方府库 50%（原 30%）
CHANGPING_SELL_RATIO = 0.60     # 平粜量上限 = 常平储 60%（价>2.0 档，原 45%）
CHANGPING_PRICE_TARGET_LOW = 1.2   # 稳定器目标价下限（PRICE_TARGET_SUPER[0]）
CHANGPING_PRICE_TARGET_HIGH = 2.5  # 稳定器目标价上限（PRICE_TARGET_SUPER[1]）
# ---- 物价目标区间（T9 定稿）：物价全程 ∈ [0.8, 2.8]，稳定器目标 [1.2, 2.5] ----
PRICE_TARGET_SUPER = (1.2, 2.5)
PRICE_FLOOR_HARD = 0.8          # 断言下界（物价 ≥ 0.8）
PRICE_CEIL_HARD = 2.8           # 断言上界（物价 ≤ 2.8，防触 3.0 恶性通胀）
# ---- 稳定器净回收公式（T9 定稿）：月销币目标 = money × (price−1.2)/price × 0.5 ----
STABILIZER_RECYCLE_RATE = 0.5   # 净回收系数（0.5）
# ---- 铸钱受控（T9 定稿）：铜资源约束 + 熔耗 20% 净增 80% + 物价>2.0 禁止 ----
MINT_MELT_LOSS = 0.20           # 铸钱熔耗 20%（熔铜铸钱损耗）
MINT_NET_RATIO = 0.80           # 净增 80%（1 − 熔耗）
MINT_PRICE_BAN = 2.0            # 物价 > 此值禁止铸钱（防助涨通胀）
COPPER_RESOURCE_DIM = "iron"    # 铸钱金属资源维度（resources 记账；用既有 iron 维度承载铸钱金属，不新增维度破坏存档/初始化）

# 经济→事件压力反馈（粮荒/通胀→起义压力）
ECONOMY_PRESSURE_THRESHOLD_GRANARY = 0.2   # 太仓存量低于容量 20% → 粮荒压力
ECONOMY_PRESSURE_THRESHOLD_PRICE = 2.0     # 粮价高于 2.0 → 通胀压力

# 岁币/岁赐支出（外交稳定 vs 财政负担）
SUI_GONG_ANNUAL = 300_000      # 岁币岁赐年支出基准（贯），随外交态势浮动
# ============================================================
# 外交对话协议（言枢密 diplomacy_dialogue + 蔡权衡系数表）
# ============================================================
# 协议 → attitude 变化（六协议 × 档位；CAP ±15）
_DIPLO_ATT = {
    "和亲": {"微": 2, "小": 4, "中": 6, "大": 8, "极": 10},
    "岁币": {"减": 2, "增": -2, "停": -8},
    "榷场": {"开": 3, "扩": 2, "停": -5},
    "盟约": {"结": 6, "断": -10},
    "纳贡": {"献": 4, "停": -6},
    "战争": {"小": -8, "中": -12, "大": -12},
}
DIPLO_ATT_CAP = 15              # 单次协议 attitude 变化 CAP
DOWRY_BASE = {"微": 50_000, "小": 100_000, "中": 200_000, "大": 400_000, "极": 700_000}  # 和亲嫁妆（贯，内帑出守恒）
SUI_GONG_MULT = {"增": 1.5, "减": 0.7, "停": 0.0}   # 岁币倍率（_settle_finance sui_gong × mult）
TRADE_INCOME = {"微": 30_000, "小": 60_000, "中": 100_000, "大": 150_000, "极": 200_000}  # 榷场月入（国库，不重复计税）
WAR_RISK_BOOST = 0.10           # 战争边患事件概率 +10%（基础概率上）
# 国主 persona（言枢密：diplomacy_dialogue 注入 sys_p）
MONARCH_PERSONAS = {
    "辽": "辽帝耶律洪基：骄矜自负，重岁币之利，轻汉民之怨；喜和亲之固，恶盟约之缚。",
    "金": "金主完颜阿骨打：雄猜善战，志在灭辽；岁币可收，战争可启，骄兵之性难驯。",
    "西夏": "夏主李乾顺：狡黠善变，骑墙于宋辽之间；岁币多多益善，和亲可结，盟约不信。",
}

FINANCE_DESC = {
    "trust": {20: "交子几不可信", 40: "商民疑之", 60: "信用尚稳", 80: "远近信行"},
    "shortage": {0.1: "泉货流转", 0.3: "钱荒渐显", 0.6: "钱荒严重", 0.9: "几乎无钱可用"},
}


# ============================================================
# 科举 / 学校 / 教育（扩展维度）
# ============================================================
EXAM_INFO = {
    "open": True,         # 是否开科
    "mode": "词学",       # 词学 / 经义 / 兼取
    "talent_pool": 50,    # 人才储备（0~100）
    "schools": 30,        # 州县学普及（0~100）
}
EXAM_ACTS = ["开科取士", "改革科举(经义)", "改革科举(词学)", "兴州县学", "制科荐才", "武举"]


# ============================================================
# 科技 / 工技（扩展维度）—— 资产驱动型科技树
# ============================================================
# 设计原则（专家团定稿）：
#  - 时间不设硬锁，解锁只由「前置节点 + 总体 level + 副指标 + 投入」驱动。
#  - 时代 era 仅作叙事标签与跨时代成本系数（非硬门槛）。
#  - 起点锚定北宋既有之器：根节点默认已启，从已有成就向前推演。
#  - 跨时代成本系数 = 1 + max(0, 节点时代 - 当前时代) * 0.2（时代差5 → ×2）。
TECH_INFO: dict[str, object] = {
    "level": 50,          # 总体技术积累（0~100）
    "gunpowder": 20,      # 火药军用程度（0~100）
    "hydraulics": 40,     # 水利机械
    "calendar": 60,       # 历法天文
    "iron": 20,           # 冶金副指标（0~100）
    "masters": 3,         # 工匠/学者人才（可投入量）
    "era": 0,             # 当前所处时代序号 0~6（叙事标签）
    "west": 0,            # 西学东渐程度 0~5（跨时代加速因子）
    "unlocked": [],       # 已点亮节点 id
    "researching": {},    # 攻关中节点 {node_id: {progress, silver_in, months}}
    "assets": {},         # 已入库资产 {asset_id: {...}}（科技+建筑+器物统一）
    "pending_inventions": [],   # 工部献策待审 [{kind,name,desc,effect_dim,effect_tier,prereq_hint,minister,source}]
    "dynamic_capabilities": {}, # AI 提议并已登记的新能力标签 {标签: {effect_dim, tier, asset_id}}
    "milestones": {},     # 已点亮节点 → 解锁叙事/年份
    "generated_nodes": {},# AI 生成的节点/建筑记录 {id: {...}}
}
TECH_ACTS = ["修撰营造法式", "火药军用", "兴水利机械", "校勘医书", "改历法", "奖百工"]
# 新增科技/发明类动作（与西学/工业挂钩）
TECH_ACTS_EX = ["聘西洋匠", "设机器局", "开矿炼油", "架设电线"]

# 开局默认已启的北宋既有之器（专家团定稿 9 根节点）
DEFAULT_UNLOCKED = ["M0_plow", "M1_noria", "E0_firewood", "E1_coal",
                    "C0_alchemy", "C1_gunpowder", "I0_block", "I1_movable", "H0_herbal"]


# ------------------------------------------------------------
# 七时代谱（叙事横幅；非硬门槛）
# ------------------------------------------------------------
TECH_ERAS = [
    (0, "北宋初中期", 960, 1100, "百工肇始，技进于器"),
    (1, "北宋后期至南宋", 1100, 1279, "火药军兴，海道初开"),
    (2, "元代集成", 1279, 1368, "冶铁规模化，天文钟成"),
    (3, "明代中后期", 1368, 1600, "航海大发展，早火绳枪"),
    (4, "清代中后期", 1600, 1800, "西学东渐，启蒙交织"),
    (5, "第一次工业革命", 1800, 1870, "蒸汽为用，铁路纵横"),
    (6, "第二次工业革命", 1870, 1900, "电气内燃，钢铁化工"),
]

# 五条主干线 + 观念与制度（穿越者观念启发，idea 类，近零成本）
TECH_LINES = ["机械动力", "能源与材料", "化学化工", "信息通讯", "生命医学", "观念与制度"]


# ------------------------------------------------------------
# 能力标签 → 数值增益模板（授权矩阵）
# 预置标签查表给精确值；AI 只可「引用 + 组合」，不可直接改数值。
# ------------------------------------------------------------
CAPABILITY_EFFECTS = {
    ("道路", "漕运"):   {"canal_efficiency": 0.15},
    ("道路", "贸易"):   {"trade_income": 0.15},
    ("建材", "营造"):   {"build_speed": 0.20, "build_cost": -0.10},
    ("筑城", "城防"):   {"defense_bonus": 8},
    ("防水", "水利"):   {"flood_risk": -0.20},
    ("动力", "制造"):   {"production": 0.20},
    ("运输", "漕运"):   {"canal_efficiency": 0.20},
    ("冶炼", "营造"):   {"build_cost": -0.08},
    ("冶金", "营造"):   {"build_cost": -0.10},
    ("军事", "军械"):   {"army_power": 0.15},
    ("军工", "军械"):   {"army_power": 0.15},
    ("开矿", "财政"):   {"mining_income": 0.15},
    ("化学", "制造"):   {"production": 0.10},
    ("印刷", "文化"):   {"exam_talent": 3, "decree_speed": -1},
    ("通讯", "政令"):   {"decree_speed": -2},
    ("医学", "民生"):   {"epidemic_risk": -0.30},
    ("农业", "粮产"):   {"yield_bonus": 0.15},
    ("灌溉", "粮产"):   {"yield_bonus": 0.12},
    ("纺织", "贸易"):   {"trade_income": 0.15},
    ("航海", "贸易"):   {"maritime_income": 0.20},
    ("天文", "历法"):   {"calendar_bonus": 5},
}


# ------------------------------------------------------------
# 科技节点元组：
#   (id, line, era, name, desc, prereq, need_level, need_sub, cost, effect)
#   cost: {silver, months, masters}；实际造价乘以跨时代成本系数。
#   effect: 点亮后直接数值钩子（能力标签由 ASSETS 统一描述）。
# ------------------------------------------------------------
# 节点元组类型别名（供映射与查询函数共用）
TechNode = tuple[str, str, int, str, str, list[str], int,
                 list[tuple[str, int]], dict[str, int | bool], dict[str, int | float]]
TECH_NODES: list[TechNode] = [
    # ---- 机械动力 ----
    ("M0_plow",     "机械动力", 0, "牛耕挽犁",   "铁犁牛耕，九州之基", [], 0, [], {"silver":0,"months":0,"masters":0}, {"yield_bonus":0.05}),
    ("M1_noria",    "机械动力", 0, "水排筒车",   "水激轮转，灌田碾谷", [], 0, [], {"silver":0,"months":0,"masters":0}, {"yield_bonus":0.08}),
    ("M2_spindle",  "机械动力", 1, "水力大纺车", "水转大纺，昼夜不息", ["M1_noria"], 60, [("hydraulics",50)], {"silver":120000,"months":9,"masters":3}, {"trade_income":0.15}),
    ("M3_bellows",  "机械动力", 1, "水力鼓风",   "水排鼓风，铸冶不绝", ["M1_noria"], 55, [("iron",35)], {"silver":80000,"months":7,"masters":3}, {"build_cost":-0.08}),
    ("M4_furnace",  "机械动力", 2, "砖石高炉",   "高炉积薪，万斛铁出", ["M3_bellows"], 72, [("iron",55)], {"silver":300000,"months":18,"masters":6}, {"build_cost":-0.15}),
    ("M5_steampump","机械动力", 4, "蒸汽抽水机", "汽机汲水，矿穴乃通", ["M4_furnace"], 80, [("west",1)], {"silver":500000,"months":20,"masters":6}, {"mining_income":0.10}),
    ("M6_loco",     "机械动力", 5, "蒸汽机车",   "汽机驱动，铁轨万里", ["M5_steampump","E3_steel"], 85, [("west",2)], {"silver":1200000,"months":28,"masters":8}, {"canal_efficiency":0.30}),
    ("M7_elecbasis","机械动力", 5, "电学基础",   "琥珀引电，磁石感线", ["M6_loco"], 88, [("west",2)], {"silver":1500000,"months":26,"masters":8}, {"production":0.08}),
    ("M8_ice",      "机械动力", 6, "内燃机",     "油气入炉，机转如雷", ["M6_loco","E4_oil"], 90, [("west",3)], {"silver":2000000,"months":30,"masters":10}, {"production":0.25}),
    ("M9_power",    "机械动力", 6, "电力传输",   "电枢旋转，千里动力一脉", ["M8_ice","M7_elecbasis"], 95, [("west",4)], {"silver":3000000,"months":32,"masters":12}, {"production":0.30}),
    # ---- 能源与材料 ----
    ("E0_firewood", "能源与材料", 0, "柴薪取火",  "薪樵为燃，窑冶之基", [], 0, [], {"silver":0,"months":0,"masters":0}, {"build_speed":0.05}),
    ("E1_coal",     "能源与材料", 0, "煤炭开采",  "山石可燃，代薪为薪", [], 0, [], {"silver":0,"months":0,"masters":0}, {"production":0.08}),
    ("E2_coke",     "能源与材料", 2, "焦炭冶铁",  "煤炼成焦，火猛而无硫", ["E1_coal","M4_furnace"], 72, [("iron",60)], {"silver":300000,"months":18,"masters":6}, {"build_cost":-0.18}),
    ("E3_steel",    "能源与材料", 4, "钢铁精炼",  "百炼成钢，器用坚利", ["E2_coke"], 82, [("west",1)], {"silver":800000,"months":22,"masters":7}, {"army_power":0.20}),
    ("E4_oil",      "能源与材料", 5, "石油提炼",  "井中黑金，炼为灯油沥青", ["E3_steel"], 88, [("west",2)], {"silver":1500000,"months":26,"masters":8}, {"mining_income":0.25}),
    ("E5_alloy",    "能源与材料", 6, "合金钢材",  "锰镍入钢，造轮船轨", ["E4_oil"], 93, [("west",3)], {"silver":2500000,"months":30,"masters":10}, {"army_power":0.25,"production":0.15}),
    ("E6_elecsteel","能源与材料", 6, "电工钢",    "硅钢导磁，电机之骨", ["E5_alloy","M9_power"], 97, [("west",4)], {"silver":3500000,"months":34,"masters":12}, {"production":0.35}),
    # ---- 化学化工 ----
    ("C0_alchemy",  "化学化工", 0, "炼丹术",     "炉鼎丹砂，化玄为妙", [], 0, [], {"silver":0,"months":0,"masters":0}, {"build_speed":0.05}),
    ("C1_gunpowder","化学化工", 0, "火药成熟",   "硝硫木炭，一硝二磺三木", ["C0_alchemy"], 20, [("gunpowder",30)], {"silver":30000,"months":5,"masters":2}, {"army_power":0.10}),
    ("C1b_huochong","化学化工", 1, "火铳",       "铜铁为管，火药推送子丸", ["C1_gunpowder"], 40, [("gunpowder",45)], {"silver":120000,"months":8,"masters":3}, {"army_power":0.12}),
    ("C1c_huoqiang","化学化工", 2, "火枪",       "更制枪铳，演为列阵之器", ["C1b_huochong"], 65, [("gunpowder",65)], {"silver":300000,"months":14,"masters":5}, {"army_power":0.15}),
    ("C1d_suifa",  "化学化工", 4, "燧发枪",     "燧石击发，机巧胜于人力", ["C1c_huoqiang"], 85, [("gunpowder",85),("west",2)], {"silver":800000,"months":20,"masters":7}, {"army_power":0.20}),
    ("C2_acid",     "化学化工", 3, "酸碱制取",   "石胆绿矾，化水为强酸", ["C1_gunpowder"], 70, [("iron",45)], {"silver":250000,"months":16,"masters":5}, {"production":0.10}),
    ("C3_dye",      "化学化工", 3, "合成染料",   "靛蓝茜草，色染天下", ["C2_acid"], 75, [], {"silver":400000,"months":16,"masters":5}, {"trade_income":0.20}),
    ("C4_fertilizer","化学化工", 4, "化学肥料",  "骨粉硝石，沃土千亩", ["C2_acid"], 80, [], {"silver":600000,"months":18,"masters":6}, {"yield_bonus":0.20}),
    ("C5_rubber",   "化学化工", 5, "人造橡胶",   "石脑油蒸，炼为弹体", ["C4_fertilizer","E4_oil"], 90, [("west",3)], {"silver":2000000,"months":28,"masters":9}, {"production":0.20}),
    ("C6_plastic",  "化学化工", 6, "合成塑料",   "酚醛树脂，百器可塑", ["C5_rubber"], 95, [("west",4)], {"silver":3000000,"months":30,"masters":11}, {"production":0.30}),
    # ---- 信息通讯 ----
    ("I0_block",    "信息通讯", 0, "雕版印刷",   "雕木为版，刷印成书", [], 0, [], {"silver":0,"months":0,"masters":0}, {"exam_talent":3}),
    ("I1_movable",  "信息通讯", 0, "活字印刷",   "胶泥活字，可拆可排", ["I0_block"], 15, [], {"silver":20000,"months":4,"masters":2}, {"exam_talent":5}),
    ("I2_metaltype","信息通讯", 1, "金属活字",   "铜锡浇铸，耐久复用", ["I1_movable"], 58, [], {"silver":60000,"months":8,"masters":3}, {"exam_talent":5}),
    ("I3_post",     "信息通讯", 2, "邮政驿站",   "驿路烽烟，传檄四方", ["I2_metaltype"], 65, [], {"silver":150000,"months":10,"masters":4}, {"decree_speed":-2}),
    ("I4_telegraph","信息通讯", 5, "电报",       "铜线千里，电传讯息", ["I3_post","M7_elecbasis"], 85, [("west",2)], {"silver":1200000,"months":24,"masters":8}, {"decree_speed":-4}),
    ("I5_phone",    "信息通讯", 5, "电话",       "声波化电，隔空传语", ["I4_telegraph"], 90, [("west",3)], {"silver":2000000,"months":26,"masters":9}, {"decree_speed":-5}),
    ("I6_radio",    "信息通讯", 6, "无线电",     "电波无远弗届，千里同声", ["I5_phone"], 95, [("west",4)], {"silver":3000000,"months":30,"masters":11}, {"decree_speed":-6}),
    # ---- 生命医学 ----
    ("H0_herbal",   "生命医学", 0, "本草医方",   "尝百草辨药性，济世活人", [], 0, [], {"silver":0,"months":0,"masters":0}, {"epidemic_risk":-0.10}),
    ("H1_forensic", "生命医学", 1, "法医检勘",   "验尸断狱，洗冤录成", ["H0_herbal"], 50, [], {"silver":40000,"months":6,"masters":2}, {"epidemic_risk":-0.10}),
    ("H2_variola",  "生命医学", 2, "人痘接种",   "痘痂种鼻，以毒攻毒", ["H1_forensic"], 68, [], {"silver":200000,"months":12,"masters":4}, {"epidemic_risk":-0.30}),
    ("H3_anatomy",  "生命医学", 3, "人体解剖",   "剖尸明理，血脉经络", ["H2_variola"], 75, [("west",1)], {"silver":400000,"months":14,"masters":5}, {"epidemic_risk":-0.20}),
    ("H4_bacteria", "生命医学", 4, "细菌学说",   "微虫致病，灭之可防", ["H3_anatomy"], 82, [("west",2)], {"silver":800000,"months":20,"masters":6}, {"epidemic_risk":-0.40}),
    ("H5_anesthesia","生命医学", 5, "外科麻醉",   "麻沸汤药，剖腹不痛", ["H4_bacteria"], 88, [("west",2)], {"silver":1500000,"months":24,"masters":8}, {"epidemic_risk":-0.30,"production":0.05}),
    ("H6_vaccine",  "生命医学", 6, "疫苗学",     "减毒作苗，疫疠可御", ["H5_anesthesia"], 93, [("west",3)], {"silver":2200000,"months":28,"masters":9}, {"epidemic_risk":-0.50}),
    # ---- 观念与制度（idea 类：穿越者观念启发，近零成本，靠推行）----
    ("X0_assembly", "观念与制度", 1, "流水线",   "工序拆解，流水作业，百器速成", ["M2_spindle"], 60, [], {"silver":0,"months":6,"masters":0,"idea":True}, {"production":0.15}),
    ("X1_standard", "观念与制度", 2, "标准化",   "模件互换，尺寸划一，营造尤便", ["X0_assembly"], 65, [], {"silver":0,"months":8,"masters":0,"idea":True}, {"build_cost":-0.12}),
    ("X2_bookkeeping","观念与制度", 3, "复式记账", "出入分账，盈亏立见，财政为之一明", ["I3_post"], 70, [], {"silver":0,"months":10,"masters":0,"idea":True}, {"mining_income":0.10}),
    ("X3_regulation","观念与制度", 4, "制式化军械", "枪械划一，零件可换，士卒易用", ["X1_standard","E3_steel"], 80, [("west",1)], {"silver":0,"months":12,"masters":0,"idea":True}, {"army_power":0.15}),
]


# ------------------------------------------------------------
# 建筑蓝图：科技节点点亮 → 可建 → 落成持续效果
#   key 为关联科技节点 id；cost 沿用固定工程字段 {silver, months}
# ------------------------------------------------------------
BUILDING_BLUEPRINTS = {
    "M2_spindle":    {"name": "大纺务",   "kind": "纺织", "cost": {"silver":80000,"months":12}, "effect": {"trade_income":0.15}, "need_node": "M2_spindle"},
    "M4_furnace":    {"name": "铁冶务",   "kind": "冶金", "cost": {"silver":200000,"months":16}, "effect": {"build_cost":-0.10}, "need_node": "M4_furnace"},
    "C1_gunpowder":  {"name": "火药局",   "kind": "军工", "cost": {"silver":60000,"months":8},   "effect": {"army_power":0.10}, "need_node": "C1_gunpowder"},
    "I0_block":      {"name": "国子监印书局", "kind": "文化", "cost": {"silver":50000,"months":8}, "effect": {"exam_talent":3}, "need_node": "I0_block"},
    "I4_telegraph":  {"name": "电报局",   "kind": "通讯", "cost": {"silver":600000,"months":18}, "effect": {"decree_speed":-3}, "need_node": "I4_telegraph"},
    "H2_variola":    {"name": "痘苗局",   "kind": "医学", "cost": {"silver":80000,"months":10}, "effect": {"epidemic_risk":-0.30}, "need_node": "H2_variola"},
    "C4_fertilizer": {"name": "肥料局",   "kind": "农业", "cost": {"silver":150000,"months":12}, "effect": {"yield_bonus":0.15}, "need_node": "C4_fertilizer"},
    "M5_steampump":  {"name": "蒸汽矿场", "kind": "矿业", "cost": {"silver":300000,"months":16}, "effect": {"mining_income":0.10}, "need_node": "M5_steampump"},
    "M6_loco":       {"name": "机器局·铁路", "kind": "交通", "cost": {"silver":800000,"months":20}, "effect": {"canal_efficiency":0.30}, "need_node": "M6_loco"},
    "M9_power":      {"name": "发电厂",   "kind": "能源", "cost": {"silver":2000000,"months":24}, "effect": {"production":0.15}, "need_node": "M9_power"},
}


# ------------------------------------------------------------
# 科技树查询工具（供命令 / 结算 / UI 共用）
# ------------------------------------------------------------
_TECH_NODE_MAP: dict[str, TechNode] = {t[0]: t for t in TECH_NODES}


def get_tech_node(node_id: str) -> TechNode | None:
    """按 id 查科技节点元组；不存在返回 None。"""
    return _TECH_NODE_MAP.get(node_id)


def tech_cost_with_era(node: TechNode, current_era: int) -> dict[str, int | bool]:
    """节点实际成本 = 基础成本 × 跨时代系数（1 + 时代差×0.2）。

    观念类节点（cost["idea"]=True）：银两强制为 0（观念革新不花钱，
    只耗推广期 months），故无跨时代银两放大；months 仍按跨时代放缩。
    """
    era = node[2]
    mult = 1.0 + max(0, era - current_era) * 0.2
    base = node[8]
    is_idea = bool(base.get("idea"))
    return {
        "silver": 0 if is_idea else int(base["silver"] * mult),
        "months": max(1, int(base["months"] * mult)),
        "masters": base["masters"],
        "idea": is_idea,
    }



# ============================================================
# 扩军 / 整军（扩展维度，与 ARMY_INIT 互补）
# ============================================================
ARMY_EXPAND_ACTS = ["募兵益军", "整练新军", "缮修兵甲", "置将练兵", "修城备边"]


# ============================================================
# 外交（细化为金/辽/夏关系动作）
# ============================================================
DIPLOMACY_ACTS = ["联金抗辽(海上之盟)", "通好辽国", "绥靖西夏", "备边严守", "遣使修好"]


# ============================================================
# 改革 / 变法（扩展维度）
# ============================================================
REFORM_ACTS = ["更役法", "行方田均税", "整顿吏治", "抑兼并", "宽恤民力", "核实军籍"]


# ============================================================
# 金融/科举/科技/军/外交/改革 → 脱敏描述辅助（原 data_desensitize.py 内联）
# ============================================================
def desensitize_prestige(value: int) -> str:
    """皇威数值→脱敏描述"""
    if value <= 25: return "皇威扫地"
    if value <= 40: return "皇威不振"
    if value <= 60: return "皇威平平"
    if value <= 80: return "皇威尚隆"
    return "皇威鼎盛"

def desensitize_arrival(rate: float) -> str:
    """到账率→脱敏描述"""
    if rate <= 0.2: return "十不存二"
    if rate <= 0.4: return "不足五成"
    if rate <= 0.6: return "六成上下"
    if rate <= 0.8: return "十之七八"
    return "几近全数"

def desensitize_satisfaction(value: int) -> str:
    """满意度→脱敏描述"""
    if value <= 20: return "怨声载道"
    if value <= 40: return "颇有微词"
    if value <= 60: return "大体认可"
    if value <= 80: return "心悦诚服"
    return "感恩戴德"

def desensitize_treasury(amount: int) -> str:
    """国库→脱敏描述"""
    if amount <= 0: return "库空如洗"
    if amount <= 2000000: return "入不敷出"
    if amount <= 5000000: return "略有结余"
    if amount <= 10000000: return "国库充盈"
    return "富甲天下"

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