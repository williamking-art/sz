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
SAVE_DIR = os.path.join(_BASE, "saves")

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
MONTHLY_EXP_CIVIL_BASE = 550_000    # 朝廷经常性货币开支派生基准（营造/赏赐/诸司常费，税基 POP 化后按收入规模校准）

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
SALT_PROFIT_PER_JIN = 0.045      # 盐榷利单价（贯/斤）：史实每斤盐榷利 40~45 文；盐课 = 盐产量 × 此价 × 到账率
SALT_CAPACITY_BASE = 185_000_000.0  # 开局 Σ各路盐产量基准（斤/年，1.85 亿斤）
SALT_POP_BASE = 80_000_000.0     # 食盐人口基准（口）= 在籍人口 8000 万（与 12 路人口合计一致，开局 pop_scale≈1）
SALT_PRICE_FLOOR = 0.6           # price_factor 下限（产能远不抵基准时）
SALT_PRICE_CEIL = 1.3            # price_factor 上限（产能远超基准时）
# 酒课（保底基准）：WINE_COIN_BASE 为「无作坊时的保底月额」，受 tech.level 微扰；
#   玩家建作坊/工程产酒时，额外酒课走动态价 MATERIAL_PRICE_BASE["wine"]（见 settlement._settle_workshops）。
WINE_COIN_BASE = 100_000
# 内置作坊配方（玩家建作坊 / AI 拟诏可扩展）：{name, recipe(原料消耗), output_dim, yield(成品产出)}
#   recipe 键为原料维度（grain_feed 表粮耗）；output_dim 为成品维度（绸/布/wine）。
WORKSHOP_RECIPES = {
    "丝坊": {"name": "丝坊", "recipe": {"silk": 10000}, "output_dim": "绸", "yield": 8000},
    "麻坊": {"name": "麻坊", "recipe": {"hemp": 10000}, "output_dim": "布", "yield": 9000},
    "酒坊": {"name": "酒坊", "recipe": {"grain_feed": 50000}, "output_dim": "wine", "yield": 30},
}
WINE_TAX_SHARE = 0.12          # 内帑取酒课净额比例（史实：酒课多数归地方军资库，进内帑者约 12%）
WINE_GRAIN_PER_GUAN = 1.5      # 酿酒耗粮（石/贯总酒课）：酒耗粮 = 总酒课 × 此值，随酒课（酒产量）动态          # 酒课保底月基准（贯，进内帤）—— audit-data 裁决：史实酒课~1000万/年，取象征性净额12%（开局约10万贯/月）
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

# 工商征率（玩家可调）：对 POP 商品消费额（工匠/商人真实产值）按"几成"征收。
# 默认 0.25 = 抽二成五。税基 POP 化后按真实商品消费额征，量级校准到收支平衡。
COMMERCE_TAX_RATE_DEFAULT = 0.05
# 工匠/商人人均月产值（贯）：工商税基 = (工匠+商人)size × 此值，为"产值流量"（不随财富存量下降，避免税抽干税基的螺旋）
CRAFT_OUTPUT_PER_CAPITA = 4.5
COMMERCE_TAX_RATE_MIN = 0.05   # 最低 0.5 成
COMMERCE_TAX_RATE_MAX = 0.40   # 最高 4 成

# 破产兜底：国库深度亏空的两档阈值（贯）
#  - TREASURY_CRISIS_LINE：国库跌破此值触发"库藏空虚"危机事件，逼玩家表态
#  - TREASURY_COLLAPSE_LINE：跌破此值强判 game_over（国用耗竭，天下鼎沸）
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

# 军籍待遇/素质基线（含粮饷双系数）。grain_mult 仅管粮、pay_mult 仅管饷，二者独立。
# 旧 ARMY_INIT 的 strength/morale/training/equipment 并入：
#   morale→morale_base, training→train_base, equipment→equip_base（装备实物率基线）。
UNIT_TIER = {
    "禁军": {"equip_base": 0.85, "train_base": 65, "morale_base": 70, "grain_mult": 1.0, "pay_mult": 1.0},
    "厢军": {"equip_base": 0.45, "train_base": 35, "morale_base": 45, "grain_mult": 0.9, "pay_mult": 0.5},
    "乡兵": {"equip_base": 0.30, "train_base": 25, "morale_base": 50, "grain_mult": 0.7, "pay_mult": 0.2},
}

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


def _firearm_tier(gunpowder: int) -> str:
    """按火药军用程度返回当前制式火器形态名。"""
    name = "突火枪"
    for thr, n in FIREARM_TIERS:
        if gunpowder >= thr:
            name = n
    return name

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
    "西辽":       _ext("西辽", "喀喇契丹", (0.0535, 0.2669, 0.0938, 0.125), 26, 55, 65, 0.018, 0.028),
    "高昌回鹘":       _ext("高昌回鹘", "西域汗国", (0.117, 0.4287, 0.0781, 0.0833), 24, 50, 60, 0.012, 0.020),
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
TIER_ORDER = ["无", "微", "小", "中", "大"]

# 档位换算表（单一权威源：AI 只给 tier，数字由程序掷定并封顶；ai/client_utils 从此导入）
TIER_RANGE = {
    "无": 0.0,
    "微": 0.25,
    "小": 0.5,
    "中": 1.0,
    "大": 1.8,
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
}
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
    "private_melt": 0.20, # 铜钱私铸/外流比例
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
CANAL_MONTHLY_RATE = 0.90      # 漕运效率基准：每月把州府可输存粮的 90% 输往中央仓
MILITARY_GRAIN_MONTHLY = 600_000    # 军粮月耗 (石)，从中央仓支取（禁军/厢军/西军粮饷）
OFFICIAL_GRAIN_MONTHLY = 200_000    # 官俸本色禄米月耗 (石)，从中央仓支取
DISASTER_RELIEF_GRAIN = 200_000     # 单次开仓赈济耗粮 (石)
SPARROW_RAT = 0.01             # 雀鼠耗：存粮月自然损耗率（1%）
CANAL_LOSS_BASE = 0.04         # 漕运漂没基础损耗（4%）
CANAL_LOSS_CORRUPT_WEIGHT = 0.06  # 漕运侵盗损耗随押运官贪腐放大系数
LAND_TAX_RATE = 0.15           # 田赋本色率：月田赋 = 月粮产 × 15%（按粮产系统核算）

# 通货 / 物价（货币经济学，钱/物之比）
PRICE_LEVEL_BASE = 1.0         # 物价基准（钱/物之比 = 1）
PRICE_LEVEL_MIN = 0.5          # 物价下限（钱荒极深）
PRICE_LEVEL_MAX = 3.0          # 物价上限（恶性通胀）
MONEY_SUPPLY_START = 200_000_000  # 货币有效供给初值（贯）：铜钱+有效交子+白银折钱。
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
PER_CAPITA_MONTH_GRAIN = 0.5    # 人均月耗粮（石），含口粮/种粮/酿造/损耗/家畜综合（史实人均年耗 5-7 石）

# 常平仓（区域粮价自动稳定器）
CHANGPING_HIGH = 1.6            # 粮价高于此则常平粜粮抑价
CHANGPING_LOW = 0.6             # 粮价低于此则常平籴粮托市

# 经济→事件压力反馈（粮荒/通胀→起义压力）
ECONOMY_PRESSURE_THRESHOLD_GRANARY = 0.2   # 太仓存量低于容量 20% → 粮荒压力
ECONOMY_PRESSURE_THRESHOLD_PRICE = 2.0     # 粮价高于 2.0 → 通胀压力

# 岁币/岁赐支出（外交稳定 vs 财政负担）
SUI_GONG_ANNUAL = 300_000      # 岁币岁赐年支出基准（贯），随外交态势浮动

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
    ("M5_steampump","机械动力", 4, "蒸汽抽水机", "汽机汲水，矿穴乃通", ["M4_furnace"], 80, [("west",1)], {"silver":500000,"months":20,"masters":6}, {"mining_income":0.20}),
    ("M6_loco",     "机械动力", 5, "蒸汽机车",   "汽机驱动，铁轨万里", ["M5_steampump","E3_steel"], 85, [("west",2)], {"silver":1200000,"months":28,"masters":8}, {"canal_efficiency":0.30}),
    ("M7_elecbasis","机械动力", 5, "电学基础",   "琥珀引电，磁石感线", ["M6_loco"], 88, [("west",2)], {"silver":1500000,"months":26,"masters":8}, {"production":0.15}),
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
    "M5_steampump":  {"name": "蒸汽矿场", "kind": "矿业", "cost": {"silver":300000,"months":16}, "effect": {"mining_income":0.20}, "need_node": "M5_steampump"},
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
# 金融/科举/科技/军/外交/改革 → 脱敏描述辅助
# ============================================================
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