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
    # 优先压缩版 JPEG；缺失时回退 PNG（旧资源）
    jpg = os.path.join(MAP_DIR, "desk_bg.jpg")
    if os.path.exists(jpg):
        return jpg
    return os.path.join(MAP_DIR, "desk_bg.png")


# ============================================================
# 分模块实现见 content/data_*.py；本文件为**唯一公共入口**，
# 下列 import 即 re-export（含 _ 下划线兼容名），既有
# `from content.data import X` / `import content.data as D` 均不破坏。
# ============================================================
from .data_constants import (
    CHANGPING_INIT_MONTHLY_SHARE,
    AI_ERROR_CODES, ANNUAL_TAX_BASE, ARREARS_COLLECT_RATE, ARREARS_KEEP_TREASURY,
    ARREARS_REPAY_SHARE, ARRIVAL_AUDIT_WEIGHT, ARRIVAL_AUTHORITY_WEIGHT, ARRIVAL_BASE,
    ARRIVAL_DIVERSION_WEIGHT, ARRIVAL_MAX, ARRIVAL_MIN, ASSET_MAINTAIN_RATE,
    BANK_DEPOSIT_MONTH_SHARE, BANK_DEPOSIT_RATE, BANK_LOAN_MONTH_SHARE, BANK_LOAN_RATE,
    BANK_RESERVE_RATIO_MIN, BRIBE_FLOOR, CIVILIAN_HOARD_NORTH, CIVILIAN_HOARD_SOUTH,
    CLAN_GRAIN_PER_MONTH, CLAN_GROWTH_ANNUAL, CLAN_OFFICE_RATIO, CLAN_PAY_PER_MONTH,
    CLERK_GRAIN_PER_MONTH, CLERK_PAY_PER_MONTH, CLERK_PER_OFFICIAL,
    COMMERCE_TAX_RATE_BY_TIER, COMMERCE_TAX_RATE_DEFAULT, COMMERCE_TAX_RATE_MAX,
    COMMERCE_TAX_RATE_MIN, COPPER_RESOURCE_DIM, CORRUPTION_MULT,
    CRAFT_OUTPUT_PER_CAPITA, DESENSITIZE_MAP, EMPEROR_ART_START, EMPEROR_HEALTH_MAX,
    EMPEROR_HEALTH_START, EMPEROR_PLEASURE_START, EMPEROR_TAOISM_START, END_YEAR,
    EQUIP_UNIT_VALUE, ERA_NAME_START, E_MAX, E_MIN, FARMER_TAX_GRAIN_KEEP_MONTHS,
    FINANCE_SCHEMA_VERSION, FINANCE_UNITS, FINISHED_DIMS, FORT_VALUE, FREE_EFFECT_CAP,
    FREE_EFFECT_COST_REJECT_RATIO, FREE_EFFECT_FIELD_WHITELIST, GENTRY_TREASURY_NORTH,
    GENTRY_TREASURY_SOUTH, GOODS_DEMAND, GOV_SPEND_TO, GRAIN_UNIT, HOARD_CAP_MULT,
    HOARD_COPPER_RATIO_BASE, HOARD_DRAW_RATE, HOARD_SPOIL_RATE, HOARD_SUPPLY_SQUEEZE,
    IMPERIAL_SHARE, INNER_TREASURY_START, INSTITUTION_PARAM_SPEC, JIAOZI_CREDIT_FLOOR,
    JIAOZI_RUN_RESERVE_LINE, JIAOZI_RUN_TRUST_LINE, JIAOZI_TAX_ACCEPTANCE,
    LAND_TAX_RATE, LAND_TAX_RATE_BASE, LAND_TAX_RATE_BENEFIT, MATERIAL_PRICE_BASE,
    MEAT_PRICE, MEMORY_ARCHIVE_WEIGHT, MEMORY_RELATION_DECAY, MINT_MELT_LOSS,
    MINT_NET_RATIO, MINT_PRICE_BAN, MIN_WEALTH_FLOOR_RATIO, MONEY_UNIT,
    MONTHLY_EXP_CIVIL_BASE, OFFICIAL_GRAIN_PER_MONTH, OFFICIAL_PAY_PER_MONTH,
    OFFICIAL_RETIRE_RATE_YEAR, OFFICIAL_SUB_KEYS, POP_BUILDING_EFFECT,
    POP_BUILDING_TYPES, POP_BUILDING_VALUE, POP_GROWTH_JITTER, POP_GROWTH_RATE,
    POP_SHARE, POP_TYPES, PRESTIGE_LEVELS, PRESTIGE_MAJOR_EVENT_CAP, PRESTIGE_MAX,
    PRESTIGE_MIN, PRESTIGE_MONTHLY_CAP, PRESTIGE_START, PRICE_VELOCITY,
    RANK_UP_PER_YEAR, RAW_DIMS, RAW_UNITS, RESOURCE_DIMS, ROUTE_MULT_DEFAULT,
    ROUTE_POST_QUOTA, SALT_CAPACITY_BASE, SALT_POP_BASE, SALT_PRICE_CEIL,
    SALT_PRICE_FLOOR, SALT_PROFIT_PER_JIN, SINECURE_PAY_RATIO, SOLDIER_GRAIN_PER_MONTH,
    SOLDIER_PAY_PER_MONTH, START_MONEY_BOOST, START_MONTH, START_YEAR, S_BASE,
    S_CONFLICT_WEIGHT, S_DIRECT_BONUS, S_DIRECT_PENALTY, S_SECRET_BASE,
    S_SECRET_LOYALTY_WEIGHT, S_SUPPORT_WEIGHT, S_ZHONGZHI_SUPPORT_WEIGHT,
    TAX_COEFF_MAX, TAX_COEFF_MIN, TAX_COLOR_RATE, TAX_COMMERCE_RATIO,
    TAX_GRAIN_SALE_ENABLED, TAX_GRAIN_SALE_MAX_SHARE, TAX_LAND_RATIO, TAX_POLL_RATIO,
    TIER_ALIAS, TIER_ORDER, TIER_RANGE, TIER_VALUE_BASE, TIER_VALUE_CAP,
    TREASURY_COLLAPSE_LINE, TREASURY_CRISIS_LINE, TREASURY_START, UPKEEP_PAY_TO,
    WAITING_PAY_RATIO, WAITING_SINECURE_MULT, WINE_COIN_BASE, WINE_GRAIN_PER_GUAN,
    WINE_TAX_SHARE, WINE_YIELD_PER_GRAIN, WON_PER_GUAN, WORKSHOP_RECIPES,
    WORKSHOP_VALUE, YINBEN_PER_JIAOSI, YINBEN_PRESTIGE_REF, clamp, desensitize_arrival,
    desensitize_canal, desensitize_granary, desensitize_prestige, desensitize_price,
    desensitize_satisfaction, desensitize_shortage, desensitize_talent,
    desensitize_tech, desensitize_treasury, desensitize_trust, get_prestige_level,
    normalize_tier, register_finished_good, register_raw_material, _TIER_ALIAS_REV,
    _desensitize_from_map,
)
from .data_decree import (
    DECREE_BASE_BANDWIDTH, DECREE_MAX_BANDWIDTH, DIRECT_DECREE_MAX, FIXED_PROCEDURES,
    KOUYU_DRIFT_CHANCE, KOUYU_DRIFT_DOWN, KOUYU_EFFECT_MULT, ORG_AFFILIATION,
    SECRET_DECREE_MAX, SECRET_DECREE_MIN, WOLF_THRESHOLD, ZHONGZHI_AFFILIATION_RATE,
)
from .data_external import (
    DIPLOMACY_ACTS, DIPLO_ATT_CAP, DOWRY_BASE, EXTERNAL_ECON, EXTERNAL_ECONOMY_REGIMES,
    EXTERNAL_FORCES, EXTERNAL_PROVINCES, EXTERNAL_PROV_ECON_REGIMES, EXTERNAL_REGIMES,
    MONARCH_PERSONAS, SUI_GONG_ANNUAL, SUI_GONG_MULT, TRADE_INCOME, WAR_RISK_BOOST,
    external_army_spec, external_pop_shares, external_province_buildings,
    external_provinces_of, _DIPLO_ATT, _EXTERNAL_ARM_CAVALRY, _EXTERNAL_ARM_DEFAULT,
    _EXTERNAL_ARM_FOOT, _EXTERNAL_ARM_HILL, _EXTERNAL_ARM_SPEC, _EXTERNAL_ARM_WATER,
    _EXTERNAL_POP_SHARE_BY_TYPE, _EXTERNAL_PROVINCES_DEFAULT,
    _EXTERNAL_PROVINCES_EXTRA, _EXT_POP_DEFAULT, _ext, _ext_pop, _ext_pop_by_heads,
)
from .data_geo_tables import (
    CASH_CROP_LAND, PREFECTURE_INFO, PREFECTURE_LIST, ROAD_YIELD,
)
from .data_imperial import (
    ERA_NAMES_HISTORY, IMPERIAL_ACTION_MATRIX, IMPERIAL_DISTANCE_MONTHS,
    IMPERIAL_EFFECT_BASE, IMPERIAL_EFFECT_DIM, IMPERIAL_LOCATIONS, IMPERIAL_MODES,
    IMPERIAL_RISK_LEVELS, IMPERIAL_RISK_PROB, IMPERIAL_ROUTE_DISTANCE,
    LEGACY_PERSONAL_ACTION_MAP, PERSONAL_ACTIONS, imperial_distance,
    imperial_prep_months,
)
from .data_military import (
    ARMY_EXPAND_ACTS, ARMY_ORG, ARMY_RATE, ARMY_UNIT_INIT, ARMY_UNIT_SPLIT,
    BRANCH_ANCHORS, BRANCH_BASE, BRANCH_PAY_CAP, BRANCH_POWER_CAP, BRANCH_REGISTRY_MAX,
    BRANCH_SPEC, BRANCH_TECH_GATE, CENTRAL_ARSENAL_INIT, DEFENSE_LINES, EQUIP_PRICE,
    EQUIP_RATE, EQUIP_STD, FIREARM_TIERS, FRONTIER_MORALE_BONUS, FRONTIER_ROUTES,
    FRONTIER_TRAIN_BONUS, INLAND_MORALE_BONUS, INLAND_TRAIN_BONUS, RECRUIT_MONTHS,
    UNIT_TIER, branch_std,
)
from .data_tech import (
    BLUEPRINT_BRANCHES, BLUEPRINT_CATEGORIES, BLUEPRINT_MONTHS_MAX,
    BLUEPRINT_MONTHS_MIN, BUILDING_BLUEPRINTS, CAPABILITY_EFFECTS, DEFAULT_UNLOCKED,
    TECH_ACTS, TECH_ACTS_EX, TECH_ADOPTION_DECAY, TECH_ADOPTION_DEFAULT,
    TECH_ADOPTION_MAX, TECH_ADOPTION_PER_LEVEL, TECH_BUILDING_MAP, TECH_DOMAIN_NODES,
    TECH_EFFECT_LABELS, TECH_ERAS, TECH_INFO, TECH_LINES, TECH_NODES, TECH_NODE_DEPLOY,
    TECH_NODE_MAINTENANCE, TECH_RESEARCH_BUDGET_RATIO, TECH_RESEARCH_LITERACY_W,
    TECH_RESEARCH_MATERIAL_FLOOR, TECH_RESEARCH_PAY_TO, TECH_RESEARCH_RATE_CAP,
    TECH_RESEARCH_SCHOOL_CAP, TECH_WEST_ACCEL_CAP, TECH_WEST_ACCEL_PER_POINT,
    TECH_WEST_MAX, TECH_WEST_SOURCES, TechNode, blueprint_region_ok, get_tech_node,
    tech_cost_with_era, _TECH_NODE_MAP, _missing_domain_nodes,
)

# ============================================================
# 派系系统 (朝堂 6 派)
# ============================================================
FACTION_NAMES = [
    "新党",      # 蔡京系
    "旧党",      # 元祐旧臣
    "皇党集团",   # 童贯等
    "军功集团",   # 边防将领
    "中立派",   # 东南科举士绅
    # 注（2026-09-19 用户定稿）：**台谏（御史台/谏院）是「官职」，不是利益集团**——
    # 台谏官各有人事派系（新党/旧党/中立…），故按**个人立场**归入相应集团，
    # 不设"台谏集团"，也**不并入皇党**（皇党＝内侍/内廷势力，与台谏无关）。
    # 详见 content/ministers/data.py 中各台谏官的 faction 归属。
]

FACTION_INIT = {
    "新党":     {"influence": 90, "satisfaction": 85, "cohesion": 70, "leader": "蔡京"},
    "旧党":     {"influence": 20, "satisfaction": 20, "cohesion": 40, "leader": "韩忠彦"},
    "皇党集团":  {"influence": 70, "satisfaction": 80, "cohesion": 65, "leader": "童贯"},
    "军功集团":  {"influence": 60, "satisfaction": 70, "cohesion": 75, "leader": "种师道"},
    "中立派":  {"influence": 50, "satisfaction": 55, "cohesion": 50, "leader": "曾布"},
}

# ------------------------------------------------------------
# 利益集团 ↔ POP 归属（POP 挂载律：集团**不新开账本**）
# ------------------------------------------------------------
# 规则（用户定稿 2026-09）：
#   ① 每个集团必须声明其 **POP 基本盘**（哪些 POP 类、哪些路、哪个子池）——势力的来源
#      是人口与财赋，不是无源的影响力数字；
#   ② 影响力的增减由**基本盘 POP 的相对得失**派生（v2 结算），禁止凭空加减；
#   ③ 玩家改革会改变 POP 结构与规模 → 既会改变既有集团的满意度/影响力，
#      也可能**催生新集团**；新集团同样必须先声明 `pop_basis` 才能登记（见 REFORM_POP_BASIS）。
# `routes=None` 表示全国；`pool` 取值 `officials|clerks|clan|None`（POP 子池）。
# **集团 ⊆ 阶级**：`subset_of` 声明母集 POP 类，`subset_kind` 说明取子集的方式
#   （`national`＝全国整个阶级；`pool`＝只取该阶级的某个子池；`route`＝只取若干路的该阶级；
#     `pool+route`＝两者的交）。展示时必须写成「占母集 X%」的**子集**，不得与 POP 并列。
POP_POOLS_VALID = ("officials", "clerks", "clan")   # POP 的合法子池（官僚官/吏、士绅宗室）
# 集团类型（kind）：说明这是“什么性质的政治网络”（与用于判重叠与关系图），
# 与 POP 基本盘正交：kind 讲政治联结方式，pop_basis 讲势力来源（人口与财赋）。
FACTION_KINDS = (
    "policy_network",            # 政策网络（同一套变法主张）
    "institution_network",       # 制度网络（台谏/铨选等制度职位）
    "court_network",             # 内廷网络（近侍、入内、供奉）
    "military_command",          # 军镇网络（边地军镇与将校）
    "gentry_alliance",           # 士绅联盟（田产与旧法既得）
    "gentry_merchant_alliance",  # 士商联盟（市舶/行会/形势户）
    "agrarian_movement",         # 农户运动（税负/灾荒/欠粮暴露催生）
    "artisan_guild",             # 工匠行会（军器/官营作坊与持续订单）
    "merchant_network",          # 全国商人网络（市舶/盐茶/行会跨路线暴露）
)

# 推荐显示名（历史化命名，2026-09-19）：前端/AI 文案一律取此表，不硬编码中文旧名。
# **口径（用户定稿 2026-09-19）：集团名取「总集」**（能涵盖其下多支的政治集团整体），
# 而具体地域/群体（西军、中立派…）是它的**子集**，下沉到 `subchannels`，不得当集团名。
# 故「军功集团」→「西北武人集团」、「中立派」→「东南士商集团」。
FACTION_DISPLAY_NAMES = {
    "新党": "新法系",
    "旧党": "元祐旧臣与保守士绅",
    "皇党集团": "皇党集团",
    "军功集团": "军功集团",
    "中立派": "中立派",
}

# ------------------------------------------------------------
# 利益集团 ↔ POP 归属（POP 挂载律：集团**不新开账本**），含集团模型元数据
# ------------------------------------------------------------
# 元数据字段（均为“偏好/关系”而非资源存量：
#   kind         集团类型（FACTION_KINDS）；
#   aliases      显示名 / 旧名 / 内部 ID 候选，由 resolve_faction_key 归一；
#   interests    诉求：[{pop_class, topic, direction(+1 支持 / −1 反对)}]；
#   red_lines    不可让步的政线（触发公开反对的条件）；
#   subchannels  子通道（把本集团基本盘拆成多个诉求口径，含 pop_class）；
#   overlaps     可重叠的其他集团（重叠**只影响政治读数**，不重复扣 POP）；
#   thresholds   活跃/维持门槛（population_share 占母集比 / cohesion / exposure_months）。
# 主键仍为**中文**（存档/结算/AI/前端现有键不动）；英文 ID 先作 alias 铺路，
# 待方案第 4 步统一迁移时再切主键（见 analysis/faction_pop_optimization_plan_2026-09-19.md）。
# ------------------------------------------------------------
# 利益集团的「立场占比」（2026-09-19 用户定稿）—— 给 POP 加政治派系标签
# ------------------------------------------------------------
# 口径：**立场跟派系，不跟地域**（地域只是官僚的出身）。故占比是**类级**（不按路分）；
# 各路差异由"处境"体现（进入满意度/声量），**不进入立场基数**。
# 它是**比率**（Σ=1），不是人口账本：
#     集团人数 = Σ_路 Σ_类 (基数人数 × split[集团])
# 农 / 工匠**无集团** —— 沉默的多数，只经"民心"这一弱通道表达（故无占比项）。
FACTION_SPLIT_INIT = {
    "官僚": {"新党": 0.45, "旧党": 0.25, "皇党集团": 0.05,
             "军功集团": 0.10, "中立派": 0.15},
    "士绅": {"旧党": 0.55, "中立派": 0.45},
    "商人": {"中立派": 1.00},
    "兵":   {"军功集团": 1.00},
}

FACTION_POP_BASIS = {
    "新党": {
        "pop_classes": ["官僚"], "pool": "officials", "routes": None,
        "subset_of": ["官僚"], "subset_kind": "faction",
        "desc": "变法受益的在朝官——**官僚 POP 在岗官子池中持新法立场的那一部分**"
                "（立场按派系而非地域切；地域只是出身）",
        "kind": "policy_network",
        "aliases": ["新法系", "绍述派", "new_law_network"],
        "interests": [
            {"pop_class": "官僚", "topic": "新法财利与差遣恩泽", "direction": 1},
            {"pop_class": "士绅", "topic": "新法政策暴露", "direction": 1},
        ],
        "red_lines": ["废署新法", "追夺绍述之政"],
        "subchannels": [],
        "overlaps": ["皇党集团"],
        "thresholds": {"population_share": 0.05, "cohesion": 30, "exposure_months": 6},
    },
    "旧党": {
        "pop_classes": ["士绅", "官僚"], "pool": None, "routes": None,
        "subset_of": ["士绅", "官僚"], "subset_kind": "faction",
        "desc": "持旧法立场的士绅与在朝官——**士绅/官僚 POP 中反对绍述的那一部分**"
                "（按立场切，不与任何地域绑定）",
        "kind": "gentry_alliance",
        "aliases": ["旧法系", "元祐旧臣", "元祐党人", "yuanyou_old_officials"],
        "interests": [
            {"pop_class": "士绅", "topic": "田税与隐田", "direction": 1},
            {"pop_class": "士绅", "topic": "科举取士", "direction": 1},
            {"pop_class": "官僚", "topic": "元祐旧制与差遣", "direction": 1},
        ],
        "red_lines": ["恢复新法", "绍述绍圣之政"],
        "subchannels": [],
        "overlaps": ["中立派"],   # 均含士绅，可重叠（只影响读数，不重复扣 POP）
        "thresholds": {"population_share": 0.05, "cohesion": 25, "exposure_months": 6},
    },
    "皇党集团": {
        "pop_classes": ["官僚"], "pool": "officials", "routes": None,
        "subset_of": ["官僚"], "subset_kind": "faction",
        "desc": "内廷与入内内侍省及依附内廷者——**官僚 POP 在岗官子池中依附皇权的那一部分**"
                "（按立场切，不绑定京畿）",
        "kind": "court_network",
        "aliases": ["宦官集团", "内侍与内廷势力", "内廷",
                    "inner_court"],
        "interests": [
            {"pop_class": "官僚", "topic": "入内供奉与内库", "direction": 1},
            {"pop_class": "官僚", "topic": "御笔与中旨", "direction": 1},
        ],
        "red_lines": ["裁押内侍", "罢内库供奉"],
        "subchannels": [
            {"name": "入内内侍省", "pop_class": "官僚"},
            {"name": "内廷供奉官", "pop_class": "官僚"},
            {"name": "依附内廷的官僚", "pop_class": "官僚"},
        ],
        "overlaps": ["新党"],
        "thresholds": {"population_share": 0.02, "cohesion": 40, "exposure_months": 3},
    },
    "军功集团": {
        "pop_classes": ["兵", "官僚"], "pool": None, "routes": None,
        "subset_of": ["兵", "官僚"], "subset_kind": "faction",
        "desc": "以军功晋身的武臣与文官——**兵/官僚 POP 中持军功立场的那一部分**"
                "（经略安抚、军前参议、军功补官者皆入此网络；兵系仍只来自兵 POP）",
        "kind": "military_command",
        "aliases": ["西军集团", "西北武人集团", "陕西边将与西军", "西军",
                    "northwest_frontier_command"],
        "interests": [
            {"pop_class": "兵", "topic": "军饷与编制", "direction": 1},
            {"pop_class": "兵", "topic": "军功与迁补", "direction": 1},
            {"pop_class": "官僚", "topic": "军前差遣与边帅除授", "direction": 1},
            {"pop_class": "官僚", "topic": "军功补官与武臣转文", "direction": 1},
        ],
        "red_lines": ["裁撤边军", "夺边将兵柄", "废军功补官"],
        "subchannels": [
            {"name": "陕西边将", "pop_class": "兵"},
            {"name": "西军", "pop_class": "兵"},
            {"name": "军户", "pop_class": "兵"},
            {"name": "边地军民", "pop_class": "兵"},
            {"name": "边帅与军前文官", "pop_class": "官僚"},
        ],
        "overlaps": ["皇党集团"],
        "thresholds": {"population_share": 0.05, "cohesion": 45, "exposure_months": 3},
    },
    "中立派": {
        "pop_classes": ["士绅", "商人"], "pool": None, "routes": None,
        "subset_of": ["士绅", "商人"], "subset_kind": "faction",
        "desc": "**党争之外的第三方**（不结党的士商力量）——**士绅/商人 POP 中不结党的那一部分**"
                "：以保境安民、通商与科举为诉求，不卷入新旧党争（按立场切，不绑定东南）",
        "kind": "gentry_merchant_alliance",
        "aliases": ["东南士人", "东南士商集团", "东南形势户与市舶商人",
                    "southeast_gentry_merchants"],
        "interests": [
            {"pop_class": "士绅", "topic": "不结党与保境安民", "direction": 1},
            {"pop_class": "士绅", "topic": "科举取士与地方秩序", "direction": 1},
            {"pop_class": "商人", "topic": "通商与市舶", "direction": 1},
            {"pop_class": "商人", "topic": "货币与盐茶", "direction": 1},
        ],
        "red_lines": ["党争倾轧", "禁海", "抑商与榷禁过苛"],
        "subchannels": [
            # 显示名（总集）＝「中立派」；下面列**具体群体**（子集）。
            # `东南士人` 是本集团的旧称/具体群体名，与 `军功集团` 下的 `西军` 同构 ——
            # 按"显示名不得同时是自己的子集"纪律，此处只能出现具体群体名，不能出现总集名。
            {"name": "东南士人", "pop_class": "士绅"},
            {"name": "形势户", "pop_class": "士绅"},
            {"name": "市舶商人", "pop_class": "商人"},
            {"name": "城市商人", "pop_class": "商人"},
        ],
        "overlaps": [],
        "thresholds": {"population_share": 0.05, "cohesion": 30, "exposure_months": 6},
    },
}

# ------------------------------------------------------------
# 改革 → POP 得失 → 集团变动（键为**已实现**的改革标识：诏令效果键或国策 node_key）
# ------------------------------------------------------------
# 语义：`gain`/`lose` 列出该改革**直接改变的 POP 类**（v2 据此派生各集团满意度增量：
# 基本盘 POP 受益则满意度升、受损则降）；`emergent` 是因该项改革而**新获财利/新成群**的
# 集团，必须带 `pop_basis`（POP 归属声明）——没有 POP 基本盘的集团不予登记。
_REFORM_LAND_SURVEY = {
    "label": "方田均税（清丈隐田）",
    "gain": [{"class": "农", "why": "隐田出税、赋役均平"}],
    "lose": [{"class": "士绅", "why": "隐田蔽课被括、形势户受损"}],
    "emergent": [{
        "name": "括田新贵", "pop_classes": ["官僚"], "pool": "officials", "routes": None,
        "subset_of": ["官僚"], "subset_kind": "pool",
        "desc": "奉行清丈的提举官与手实推排之吏，因新法财利而结党",
    }],
}
_REFORM_CURTAIL_WASTE = {
    "label": "裁汰冗费（省浮节流）",
    "gain": [{"class": "农", "why": "减浮费、宽民力"}],
    "lose": [{"class": "官僚", "pool": "officials", "why": "裁冗官闲曹、夺其廪禄"}],
    "emergent": [{
        "name": "理财新进", "pop_classes": ["官僚"], "pool": "officials", "routes": None,
        "subset_of": ["官僚"], "subset_kind": "pool",
        "desc": "以勾稽财计、厘定省费令而进用的三司与户部属官",
    }],
}
_REFORM_REDUCE_OFFICE = {
    "label": "省官并职（裁并机构）",
    "gain": [{"class": "农", "why": "省冗禄以宽民"}],
    "lose": [{"class": "官僚", "pool": "officials", "why": "并职失位、待阙更众"}],
    "emergent": [{
        "name": "铨选清流", "pop_classes": ["官僚"], "pool": "officials", "routes": None,
        "subset_of": ["官僚"], "subset_kind": "pool",
        "desc": "主持铨选澄汰、以守正自居的郎官与台谏",
    }],
}
_REFORM_REFORM = {
    "label": "更张法度（官制改革）",
    "gain": [{"class": "官僚", "pool": "officials", "why": "新制授职、升擢有门"}],
    "lose": [{"class": "士绅", "why": "旧法既得与恩荫受损"}],
    "emergent": [{
        "name": "新制官僚", "pop_classes": ["官僚"], "pool": "officials", "routes": None,
        "subset_of": ["官僚"], "subset_kind": "pool",
        "desc": "依新官制进用的在朝官，以新典为进身之阶",
    }],
}
_REFORM_MILITARY = {
    "label": "整军经武（边备与军器）",
    "gain": [{"class": "兵", "why": "增饷、补械、军功有赏"}],
    "lose": [{"class": "农", "why": "加赋供军、力役加派"}],
    "emergent": [{
        "name": "新军将校", "pop_classes": ["兵"], "routes": None,
        "subset_of": ["兵"], "subset_kind": "national",
        "desc": "整编厢军入禁军后以新军功进身的将校",
    }],
}
REFORM_POP_BASIS = {
    "land_survey": _REFORM_LAND_SURVEY,
    "t1_land_survey": _REFORM_LAND_SURVEY,     # 国策「方田均税」
    "curtail_waste": _REFORM_CURTAIL_WASTE,
    "g3_curtail": _REFORM_CURTAIL_WASTE,       # 国策「裁汰冗费」
    "reduce_office": _REFORM_REDUCE_OFFICE,
    "hoard": _REFORM_REDUCE_OFFICE,            # 括籴/括藏：动的是形势户之藏
    "reform": _REFORM_REFORM,
    "g2_reform": _REFORM_REFORM,               # 国策「官制改革」
    "m1_garrison": _REFORM_MILITARY,
    "m3_war_machine": _REFORM_MILITARY,        # 国策「军备军器」
}


# ============================================================
# 事件系统
# ============================================================
EVENT_CATEGORIES = [
    "花石纲", "方腊起义", "宋江起义", "海上之盟",
    "金灭辽", "金军南侵", "宋夏战争", "黄河决口",
    "祥瑞", "党争", "科举", "灾荒",
]


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
# 六部衙门（中枢施政机构）
# ============================================================
YAMEN_LIST = ["吏部", "户部", "礼部", "兵部", "刑部", "工部"]
YAMEN_INFO = {
    "吏部": {"duty": "铨选官吏、考核黜陟", "faction": "旧党", "acts": ["整饬吏治", "裁汰冗员", "兴办科举"]},
    "户部": {"duty": "户口田赋、度支钱粮", "faction": "新党", "acts": ["清丈田亩", "减免田赋", "常平仓赈济"]},
    "礼部": {"duty": "礼仪祭祀、科举学校", "faction": "旧党", "acts": ["重开贡举", "兴修礼乐", "褒崇道教"]},
    "兵部": {"duty": "武官选授、舆图军籍", "faction": "军功集团", "acts": ["整练新军", "缮修兵甲", "置将练兵"]},
    "刑部": {"duty": "律令刑名、刑狱冤滞", "faction": "旧党", "acts": ["宽刑省狱", "修订刑统", "平反冤案"]},
    "工部": {"duty": "山泽沟洫、营造工役", "faction": "皇党集团", "acts": ["兴修水利", "营缮宫观", "开矿铸钱"]},
}



# ============================================================
# 田亩户籍总览
# ============================================================
LAND_INFO = {
    "cultivated": 460_000_000,       # 垦田（亩）
    "households": 20_000_000,        # 在籍明户（户）——20 路 PREFECTURE_INFO.households 合计即此值
    "hidden_households": 5_000_000,  # 隐户（户，不在籍，UI 不显示；设计锚：总户 2500 万 = 明 2000 万 + 隐 500 万，总口 1 亿）
    "hidden_rate": 0.35,             # 田赋隐漏率（税收口径，与隐户人口锚不同维）
    "wasteland": 80_000_000,         # 荒田（亩）
    "yield": 1.0,                    # 亩产系数
}


# ============================================================
# 金融 / 货币 / 市舶 / 交子 / 官营机构（扩展维度）
# ============================================================
JIAOZI_INFO = {
    "issued": 0,          # 发行额/发行面额（贯）——存量券面，**不等于**流通额
    "trust": 60,          # 纸币信用（0~100）→ 派生信用上限与折价
    "reserve": 2_000_000, # 准备金/本钱准备（贯）——**不计入**流通货币供给
    # ---- 数据契约（第二节§2）：区分 发行额 / 流通额 / 准备金 / 兑付率 / 界期 ----
    # `circulating` / `redeem_rate` 为**派生读数缓存**：由 core.money 依
    # 发行额×接受度(trust/100) 与 准备金÷流通额 逐月刷新（_settle_extensions），
    # 只作对账/展示，不参与货币守恒运算（避免双权威源）。
    "circulating": 0,        # 流通额（贯，派生缓存：issued×trust/100）
    "redeem_rate": 1.0,      # 兑付率（准备金÷流通额；流通为 0 时记足额 1.0）
    "discount": 0.0,         # 折价率（0~1；信用下降派生，损失落到持券者）
    "run_pressure": 0.0,     # 挤兑压力（0~1；兑付率/信用跌破线派生）
    "tax_acceptance": 0.80,  # 税收接受度（0~1）：官府课税接受交子的比例（发行上限约束）
    "credit_ceiling": 1.0,   # 信用上限系数（0~1，= trust/100；发行上限约束）
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
    # 审查 P2-53 修复（死数据 → 单一权威源）：本表为金融调制的**唯一权威源**——
    # core/settlement_steps._settle_extensions 原另行硬编码同一组数值（±5/100万/0.05/0.02/10/
    # ×1.20/×0.80/50万/×1.05 及各自 clamp），两处各自维护；现结算侧一律读本表。
    #   cap     = 每次调制幅度；min/max = 该字段值域钳制（与结算侧原 clamp 逐值一致）
    #   up/down = 乘数式调制的精确倍率（保留字面量，避免 1.0+cap 引入 1ulp 浮点差）
    "jiaozi_trust": {"cap": 5, "min": 0, "max": 100},        # 交子信任 增/跌 → trust ±5
    "jiaozi_issued": {"cap": 1_000_000},                     # 交子发行 增 → +100万（≤可发额度）
    "shortage": {"cap": 0.05, "min": 0.05, "max": 0.95},     # 钱荒 缓/加剧 → shortage ±0.05
    "tariff": {"cap": 0.02, "min": 0.05, "max": 0.20},       # 市舶 兴/衰 → tariff ±0.02
    "silver_in": {"cap": 10, "min": 10, "max": 60},          # 市舶白银 silver_in ±10 万两/年
    "bank_capital": {"cap": 0.20, "up": 1.20, "down": 0.80}, # 银行 扩/损 → capital ×1.20/×0.80
    "bank_reserve": {"cap": 500_000, "min": 0},              # 银行 reserve ±50万（floor 0）
    "price_mult": {"cap": 0.05, "up": 1.05, "down": 0.95,
                   "min": 0.5, "max": 3.0},                  # 价格系数 ±5%（clamp [0.5,3.0]）
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
    "capital": 0,         # 官营资本（⚠单位=万贯，legacy；换算见 core.money._bank_capital_as_guan）
    "reserve": 0,         # 准备金/库存现金（贯；money.ACCOUNTS 认可账户，勿与 capital 混单位）
    "deposits": 0,        # 吸收存款（贯，银行负债 memo；钱在 reserve，不重复计入货币供给）
    "loans": 0,           # 放出贷款（贯，银行债权 memo；对应借款方 POP wealth 资产）
    "reserve_ratio": 0.20,  # 准备金率（0~1，法定最低；放贷上限约束）
    "overdue_rate": 0.0,  # 逾期率（0~1；违约派生 → 信用下降/坏账）
    "run_pressure": 0.0,  # 挤兑压力（0~1；存款人集中提现，抑制放贷）
    "branches": 0,        # 网点数（家）
    "target": "",         # 放贷对象（"农"/"工匠"/"商人"/"士绅"；空=未定）
}
STANDARD_INFO = {
    # 金银铜三品本位：铜钱基准，银一两≈铜钱一贯，金一两≈铜钱十贯（示意）
    # 第二节§5：**记账汇率（book）与市场汇率（market）分离**——
    #   记账汇率 = 官府账册/税赋折算口径；市场汇率 = 民间兑换实际行市。
    #   两者之差 + fee_rate（手续费）+ mint_loss（铸币/熔铸损耗）构成兑换记录。
    "book_silver_per_copper": 1.0,     # 记账：银一两合铜钱（贯）
    "book_gold_per_copper": 10.0,      # 记账：金一两合铜钱（贯）
    "market_silver_per_copper": 1.0,   # 市场：银一两合铜钱（贯）
    "market_gold_per_copper": 10.0,    # 市场：金一两合铜钱（贯）
    "fee_rate": 0.01,                  # 兑换手续费率（0~1，付给兑换机构）
    "mint_loss": 0.02,                 # 铸币/熔铸损耗率（0~1，真实退出流通、须记 burn）
    # ---- 向后兼容别名（legacy；= 记账汇率）----
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

# 路类型闭集（审查 P1：原消费方写「边镇路/沿边路/京畿路」等**不存在**的 type 值，
# 致边镇城防/流民基数加成全失效——统一到 PREFECTURE_INFO.type 的真实取值）
PREFECTURE_TYPE_FRONTIER = ("缘边重镇", "沿边山郡", "缘边山郡")   # 缘边防区（北/西线）
PREFECTURE_TYPE_COASTAL = ("沿海市舶",)                          # 沿海
PREFECTURE_TYPE_CAPITAL = "京畿要地"

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


# ---- 工程状态机 / 工匠工时 / 运维折旧（整改③，2026-09-19）----
# 项目状态机：proposed → funded → building → operating → degraded / abandoned。
# 资金、材料、灾害或治安不足 → 延期或降效，**绝不静默完工**（源：整改意见 §三.1）。
PROJECT_STATUS_FLOW = ("proposed", "funded", "building", "operating",
                       "degraded", "abandoned")
PROJECT_STATUS_LABELS = {
    "proposed": "拟议", "funded": "已拨款", "building": "营建中",
    "operating": "运行", "degraded": "降效", "abandoned": "废弃",
}
PROJECT_LABOR_RATIO = 0.25          # 工程就地征用工匠 POP 的上限比例（可用工时口径）
PROJECT_UNDERSTAFF_MIN = 0.34       # 工匠工时到位率下限：低于此值延期（不推进）
PROJECT_SECURITY_UNREST = 60        # 治安口径：本地动乱 > 此值 → 工程降效
PROJECT_SECURITY_MIN_FACTOR = 0.35  # 降效下限（进度不足额推进，但仍向前）
PROJECT_DEPRECIATION_RATE = 0.02    # 运行资产月折旧率（产能 → capacity）
PROJECT_MAINTENANCE_RECOVER = 0.05  # 维持到位时月修复率（折旧可逆）
PROJECT_DEGRADED_LINE = 0.60        # 产能低于此线 → degraded（降效）
PROJECT_PROPOSED_TIMEOUT = 6        # 拟议逾 6 月未获拨款 → abandoned

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
# 注：田赋率单一权威源见上方 LAND_TAX_RATE（0.15 综合率）+ LAND_TAX_RATE_BENEFIT（0.10 本色率）；
# 月田赋 = 月粮产 × LAND_TAX_RATE × 折色率（按粮产系统核算）。此处不再重复定义（审查 P2：双定义消除）。

# 通货 / 物价（货币经济学，钱/物之比）
PRICE_LEVEL_BASE = 1.0         # 物价基准（钱/物之比 = 1）
PRICE_LEVEL_MIN = 0.5          # 物价下限（钱荒极深）


PRICE_LEVEL_MAX = 3.0          # 物价上限（恶性通胀）
MONEY_SUPPLY_START = 200_000_000  # 货币有效供给初值（贯）：铜钱+有效交子+白银折钱。

# ---- 建筑-时代交互（言枢密方案，告别纯数值）----
# era_state 五维认知层（兴/平/衰，程序定幅迁移）：economy_center 财赋重心 /
# culture 文教 / commerce 商贸 / military 军备 / urban 都市化
ERA_DIMENSIONS = ("economy_center", "culture", "commerce", "military", "urban")
ERA_TREND_SHIFT = {"兴": 10, "平": 0, "衰": -10}    # 每档迁移幅度（0-100 刻度，程序定幅）
ERA_BUILDING_LINK = {          # 下行联动：建筑 → era 维度（乘数走既有公式，累积到 era）
    # 审查 P2-55 修复（死键）：原表 市舶/码头/城防 不对应任何真实建筑类型（联动永不命中）。
    # 对齐真实建筑闭集：BUILDING_STD(水利/常平仓/官营作坊/官署/军营/学校)
    # + POP_BUILDING_TYPES(农田/工坊/商铺/庄园) + TECH_BUILDING_MAP(市舶司/火器作坊/铁作)。
    "水利": "economy_center", "常平仓": "economy_center",
    "学校": "culture", "市舶司": "commerce", "工坊": "commerce",
    "军营": "military", "官营作坊": "commerce",
    "农田": "economy_center", "商铺": "commerce", "庄园": "economy_center",
}
ERA_UP_LINK = {                # 上行调制：国库/景气 → 建造速度/解锁
    "build_speed_boost": 1.3,  # 国库充足+景气中/大 → 建造速度 ×1.3
    "unlock_threshold": 60,    # economy_center/culture ≥60 → 新建筑解锁
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
EXAM_HARD_POOR_SHARE = {"无": 0.0, "微": 0.3, "小": 0.5, "中": 0.7, "大": 0.9,
                        "巨": 0.9, "极": 0.9}  # 科举寒门（农）入仕占比
# 审查 P2-52 修复（档位不全）：原表只 5 档 → AI 出「巨/极」（7 档合法词）时被 .get(tier, 0.0)
# 静默归零（寒门入仕份额消失）。补 巨/极 闭合 7 档（同 BOOM_MULT 写法），按份额上限 0.9 收敛。
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
# ---- 物价月度上限 + 路线粮价派生（整改①三、①五联动）----
# 粮价优先由产量/粮仓/漕运派生，且有**月度上限**（单月涨跌幅硬钳），
# 防止灾荒/AI 推演造成的单月价格跳变传导到全部下游计算。
GRAIN_PRICE_MONTHLY_CAP = 0.15   # 粮价（全国/路线）单月最大涨跌幅（±15%）
PRICE_LEVEL_MONTHLY_CAP = 0.20   # 全国物价指数单月最大涨跌幅
# 路线物价由供给/需求/库存/运输/货币有效供给派生（全国 PRICE_LEVEL 只是加权读数）
TRANSPORT_PRICE_WEIGHT = 0.20    # 漕运阻塞 0~100 → 路线粮价最多 +20%（运输成本）
STOCK_PRICE_RELIEF_MAX = 0.15    # 本地库存（太仓+常平）充足时最多抑价 15%
MONEY_SUPPLY_PRICE_WEIGHT = 0.10 # 货币有效供给偏离基准 ±100% → 路线粮价浮动 ±10%
# ---- 稳定器净回收公式（T9 定稿）：月销币目标 = money × (price−1.2)/price × 0.5 ----
STABILIZER_RECYCLE_RATE = 0.5   # 净回收系数（0.5）

# 经济→事件压力反馈（粮荒/通胀→起义压力）
ECONOMY_PRESSURE_THRESHOLD_GRANARY = 0.2   # 太仓存量低于容量 20% → 粮荒压力
ECONOMY_PRESSURE_THRESHOLD_PRICE = 2.0     # 粮价高于 2.0 → 通胀压力

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
# ---- 科举「离散科次」（阶段 C-6，宋代官制设计 §15）----
# 原实现把科举做成**每月连续小额流**（`POP_FLOW_RATE["科举"]=1e-4/月`，约 100 人/月
# ≈ 3,700 人/科次），既不符合史实形态（一期数百进士），也让"同年/座主"这类
# 真实政治结构无从表达。现改为**每 EXAM_INTERVAL_YEARS 年一次科次**，一次入仕一批。
EXAM_INTERVAL_YEARS = 3
EXAM_COHORT_SIZE = {          # 每科次取士额（人），随 AI 科举档位缩放
    "无": 0, "微": 180, "小": 320, "中": 520, "大": 820,
}
EXAM_TAKER_MULT = 0.0         # 预留：落第者规模 = 取士额 × 此系数（§15.6 两端代价，暂不做）

# ---- 科举「座主门生」与人员进出口的派系流动（利益集团二期，2026-09-19）----
# 座主（知贡举）派系解析顺序：显式指派（state.exam["examiner"]/["examiner_faction"]）
#   → 礼部在任者 → 朝堂声量最大的派系（声量由官职权限派生，见 core/faction_voice.py）。
# 本榜进士（同年）随座主入派；恩荫随父辈（士绅立场分布）；致仕带本派立场回士绅。
# **只改立场占比（Σ=1），不新增人口账本**：人仍在同一 POP 的 size 里。
EXAM_EXAMINER_ORG = "礼部"          # 知贡举所在机构（取其在任者派系；空则回落声量最大者）
FACTION_SINECURE_EXIT_TILT = 0.5    # 祠禄安置的「失势派系」倾斜：月转出中归最低满意度派系的比例

# ---- 吏制（阶段 C-5，宋代官制设计 §16）----
# 吏 = 「不可见的执行层」。官三年一任、回避本籍；吏世代本地、掌握簿书 → 吏强官弱。
# 现行模型的三个空白：吏额静态（官×8）、吏禄不足无后果、把持/吏怨不存在。以下为其参数。
CLERK_SUBSISTENCE_CASH = 7.2   # 吏户维持生计所需（贯/月）：户均4口 × 1.8石 × 1贯/石（§16.2）
EXACTION_RATE = 0.35           # 吏禄缺口 → 陋规取偿的转化强度
EXACTION_MAX_SHARE = 0.05      # 单月从本路民间三池最多抽取的比例（防一次性抽干）
EXACTION_MOOD_DIVISOR = 0.01   # 陋规额/人口 → 民心扣分 的除数（越大扣得越轻）
CLERK_ADJUST_RATE = 0.02       # 编制惯性：吏额每月向编制靠拢的比例
CLERK_STAFFING_ALPHA = 0.8     # 编制对政务量的弹性（<1 = 规模经济，§11.5）
CLERK_ENTITLEMENT_GROWTH = 0.0010  # 编制**自我膨胀**（/月）：世袭吏职是私产、豪强请托添额，
#                                「吏额有增无损」——这是"冗吏"真正的来源（不随政务量下降而减）。
#                                **取中**：史实吏额冗滥严重，但 0.06%/月 的冗吏率在 20 年内仅 6.6%、
#                                玩家几乎无感；取中 0.10%/月 → 20 年冗吏率 ≈ 11%，可感知而不过火。
GRIP_BASE = 0.10               # 把持度基准
GRIP_HEREDITARY_W = 0.25       # 世袭比例对把持度的贡献
GRIP_COVERAGE_W = 0.15         # 陋规补足率对把持度的贡献（有油水才有动力把持）
GRIP_MAX = 0.85                # 把持度上限
GRIP_DECAY_TOWARD = 0.05       # 把持度向目标值缓动速度（/月）
DECREE_GRIP_W = 0.35           # 把持度 → 诏令执行率 的折扣权重（§16.4）
GRIEVANCE_ADJUST = 0.15        # 吏怨向目标值缓动速度（/月）
GRIEVANCE_COVERAGE_RELIEF = 0.5  # 陋规补足能缓解的吏怨比例（上限 0.5：靠陋规吃饭终究不体面）
GRIEVANCE_MIN_FLOOR = 0.0      # 吏怨目标值下限
BACKLOG_GAIN_MAX = 4.0         # 积压增量上限（与旧 random.randint(0,3) 同量级，§11.6）
# 政务量 W 折算基准（§11.4；只取全部映射到现有字段的分项）
W_POP_BASE = 100_000.0         # 每 10 万人 1 件/月（民政基础 A）
W_LITIGATION_BASE = 500_000.0  # 每 50 万人 1 件/月（刑狱词讼 G）
W_LITIGATION_UNREST_W = 0.8    # 动乱对讼案量的放大权重
W_LAND_BASE = 1_000_000.0      # 每百万亩 1 件/月（田赋户籍 B）
W_ORG_EACH = 1.0               # 每机构分支 1 件/月（机构事权 D）
W_OFFICIAL_BASE = 100.0        # 每 100 官 1 件/月（人事铨选 I：冗官 → 冗吏 的闭路）
W_GARRISON_BASE = 100_000.0    # 每 10 万兵 1 件/月（军需后勤 J）



# ============================================================
# 改革 / 变法（扩展维度）
# ============================================================
REFORM_ACTS = ["更役法", "行方田均税", "整顿吏治", "抑兼并", "宽恤民力", "核实军籍"]
