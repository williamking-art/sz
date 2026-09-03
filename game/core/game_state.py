# -*- coding: utf-8 -*-
"""宋祚 · 核心游戏状态"""
import json
import os
import random
from datetime import datetime

from content.data import (
    START_YEAR, START_MONTH, ERA_NAME_START, PRESTIGE_START,
    TREASURY_START, INNER_TREASURY_START, ARRIVAL_BASE, EMPEROR_HEALTH_START,
    EMPEROR_ART_START, EMPEROR_TAOISM_START, EMPEROR_PLEASURE_START,
    FACTION_INIT, FACTION_NAMES, EXTERNAL_FORCES,
    DEFENSE_LINES, DECREE_BASE_BANDWIDTH, DIFFICULTY_PRESETS,
    ANNUAL_TAX_BASE, MONTHLY_EXP_CIVIL_BASE, ERA_NAMES_HISTORY,
    get_prestige_level, desensitize_prestige, desensitize_arrival,
    desensitize_satisfaction, desensitize_treasury,
    EXTERNAL_REGIMES,
    YAMEN_LIST, YAMEN_INFO, PREFECTURE_LIST, PREFECTURE_INFO, LAND_INFO,
    JIAOZI_INFO, MARITIME_INFO, COIN_INFO, BANK_INFO, STANDARD_INFO,
    EXAM_INFO, TECH_INFO,
    desensitize_trust, desensitize_shortage, desensitize_talent, desensitize_tech,
    GRANARY_START, GRANARY_START_CAP, GRANARY_CAP_SOFT, GRAIN_PRICE_MIN,
    GRAIN_PRICE_MAX, PER_CAPITA_MONTH_GRAIN, PRICE_LEVEL_BASE, PRICE_LEVEL_MIN,
    PRICE_LEVEL_MAX, MONEY_SUPPLY_START, PAY_SYSTEM_DEFAULT, CANAL_BLOCK_START,
    COMMERCE_TAX_RATE_DEFAULT, PRICE_VELOCITY, MARITIME_TRADE_BASE,
    PREFECTURE_INITIAL_GRAIN_PRICE,
    desensitize_granary, desensitize_price, desensitize_canal,
    # 经济全浮动重构新增常量
    TAX_COLOR_RATE, LAND_TAX_RATE_BENEFIT, LAND_TAX_RATE_BASE,
    SOLDIER_GRAIN_PER_MONTH, SOLDIER_PAY_PER_MONTH,
    OFFICIAL_PAY_PER_MONTH, OFFICIAL_GRAIN_PER_MONTH,
    CLERK_PAY_PER_MONTH, CLERK_GRAIN_PER_MONTH, CLERK_PER_OFFICIAL,
    CORRUPTION_MULT, BRIBE_FLOOR, IMPERIAL_SHARE,
    WINE_YIELD_PER_GRAIN, SALT_PROFIT_PER_JIN, SALT_CAPACITY_BASE, SALT_POP_BASE,
    SALT_PRICE_FLOOR, SALT_PRICE_CEIL, WINE_COIN_BASE,
    MATERIAL_PRICE_BASE, RESOURCE_DIMS,
)
from content.ministers import (
    MINISTERS, loyalty_init, corruption_init, CENTRAL_ORG_INFO, AUTHORITY_MATTERS, REFORM_TYPES,
    org_lead,
)
from core.game_state_econ import GameStateEconMixin


def _next_month(year: int, month: int):
    """推进一个月份，返回新的 (year, month)。作为模块级纯函数，供 commands 与 settlement 共用。"""
    month += 1
    if month > 12:
        month = 1
        year += 1
    return year, month


def _build_pops(info: dict, p_type: str) -> dict:
    """每路 POP 群体开局分配（参考维多利亚人口分层）。

    各 POP = {size(人数), wealth(钱/贯), grain(粮/石)}；钱粮守恒：
    士绅 wealth 为囤粮本钱、grain 为其囤粮，随低买高卖此消彼长。
    """
    from content.data import (
        POP_SHARE, GENTRY_TREASURY_SOUTH, GENTRY_TREASURY_NORTH,
        CIVILIAN_HOARD_SOUTH, CIVILIAN_HOARD_NORTH,
        RESOURCE_DIMS, RAW_DIMS,
    )
    pop_total = info.get("population", 0)
    south = p_type in ("财赋膏腴", "沿海市舶", "天府沃野")
    share_shen = POP_SHARE["士绅"] * (1.3 if south else 0.7)
    sz_shen = int(pop_total * share_shen)
    sz_gong = int(pop_total * POP_SHARE["工匠"])
    sz_shang = int(pop_total * POP_SHARE["商人"])
    _off = round(info.get("households", 0) * 0.00135)   # 官数（与 officials 派生同口径）
    sz_guan = _off + _off * 8                             # 官 + 吏（在籍人口的一部分，须从农里扣除）
    sz_nong = max(0, pop_total - sz_shen - sz_gong - sz_shang - sz_guan)
    monthly_grain = info.get("grain", 0) / 12.0
    monthly_tax = info.get("monthly_tax", 200_000)
    # 商品种类（成品，多商品支持；后期玩家新增商品经 register_finished_good 加入）
    _goods_dims = [d for d in RESOURCE_DIMS if d not in RAW_DIMS]
    _g0 = lambda: {d: 0 for d in _goods_dims}
    return {
        "农": {"size": sz_nong, "wealth": int(monthly_tax * 0.5), "grain": int(monthly_grain * 2.0), "goods": _g0(), "欠税": 0},
        "士绅": {
            "size": sz_shen,
            "wealth": int(monthly_tax * (GENTRY_TREASURY_SOUTH if south else GENTRY_TREASURY_NORTH)),
            "grain": int(monthly_grain * (CIVILIAN_HOARD_SOUTH if south else CIVILIAN_HOARD_NORTH)),
            "goods": _g0(),
            "窖银": 0,           # 士绅窖藏之银（贯）：退出流通、可后续掏出（挥霍/抄家）
            "欠税": 0,           # 欠税科目（A1）：税征缺口累计，逐月追缴；存档兼容见 save_load 迁移
        },
        "工匠": {"size": sz_gong, "wealth": int(monthly_tax * 1.0), "grain": int(monthly_grain * 0.1), "goods": _g0(), "欠税": 0},
        "商人": {"size": sz_shang, "wealth": int(monthly_tax * 2.0), "grain": int(monthly_grain * 0.2), "goods": _g0(), "欠税": 0},
        "官僚": {"size": sz_guan,
                  "wealth": int(monthly_tax * 0.5), "grain": int(monthly_grain * 0.02), "goods": _g0(), "欠税": 0},
        # 官僚开局 grain = 月产×0.02（≈4.9石/人 = 1~2 月口粮缓冲；旧 0.1 为设计残留，见调参定案 Q2）
        "兵": {"size": 0, "wealth": 0, "grain": 0, "goods": _g0(), "欠税": 0},  # 兵额由 army_units 聚合后回填
    }


def _init_local_refugees(info: dict) -> int:
    """按路本地流民开局基数：边镇/高动乱路略高，腹里近 0，体现北宋常态流徙而非开局危机。"""
    p_type = info.get("type", "腹里州路")
    unrest = info.get("unrest", 15)
    base = 800 if p_type in ("边镇路", "沿边路") else 200
    base += int(unrest * 30)            # 动乱越高，常态流民越多
    if info.get("is_capital"):
        base = max(0, base - 300)        # 京畿吸纳力强，基数更低
    return max(0, base)


def _init_city_defense(p_type: str) -> int:
    """按路类型初始化城防（0~100）：边镇/沿边高，腹里低，京畿最高。"""
    if p_type in ("京畿路", "京畿"):
        return 80
    if p_type in ("边镇路", "沿边路"):
        return 65
    if p_type in ("沿江路", "沿海路"):
        return 50
    return 40


def _clamp(value: float, lo: float, hi: float) -> float:
    """把数值钳制到 [lo, hi] 闭区间（供各粮价/物价计算复用，消除重复 max/min）。"""
    return max(lo, min(hi, value))


def _garrison_by_tier(state, road: str) -> dict:
    """某路各军籍兵额（人）聚合（供 to_public 快照，非真账）。"""
    out: dict = {}
    for u in state.army_units:
        if u.station == road and u.troops > 0:
            out[u.tier] = out.get(u.tier, 0) + u.troops
    return out


class GameState(GameStateEconMixin):
    """宋祚游戏主状态（经济计算族继承自 GameStateEconMixin）"""

    def __init__(self, difficulty: str = "史实"):
        diff = DIFFICULTY_PRESETS.get(difficulty, DIFFICULTY_PRESETS["史实"])

        # ---- 时间 ----
        self.year: int = START_YEAR
        self.month: int = START_MONTH
        self.turn: int = 0
        self.era_name: str = ERA_NAME_START
        self.difficulty: str = difficulty
        self.difficulty_presets: dict = dict(diff)

        # ---- 皇帝 ----
        self.emperor_name: str = "赵佶"
        self.emperor_health: int = EMPEROR_HEALTH_START
        self.emperor_alive: bool = True
        self.is_abdicated: bool = False
        self.abdication_reason: str = ""

        # 皇帝三项
        self.art_mastery: int = EMPEROR_ART_START
        self.taoism_leaning: int = EMPEROR_TAOISM_START
        self.pleasure_leaning: int = EMPEROR_PLEASURE_START

        # ---- 皇威 ----
        self.prestige: int = diff["prestige_start"]
        self._prestige_history: list = []

        # ---- 到账率 ----
        self.arrival_rate_base: float = diff["arrival_base"]

        # ---- 国库 ----
        self.treasury: int = TREASURY_START

        # ---- 内帑 / 内藏库（皇帝私库，与国库分理）----
        self.imperial_treasury: int = INNER_TREASURY_START
        # 内帑粮（石，皇帝私库的粮，皇庄皇租本色入此；田产的是粮不是钱，不折银）
        self.imperial_granary: int = 0
        # 酒课（贯/月，进内帑净入）：开局 WINE_COIN_BASE，随酒坊建设增加（见 _settle_workshops）
        self.wine_tax: int = WINE_COIN_BASE

        # ---- 经济全浮动重构新增状态 ----
        # 七维物资仓：{dim: {"stock": 现有, "cap": 容量}}
        from content.data import RESOURCE_DIMS
        self.resources: dict = {d: {"stock": 0, "cap": 50_000} for d in RESOURCE_DIMS}
        # 工程系统（玩家手动发起，逐月推进）：{pid: {...}}
        self.projects: dict = {}
        # 制作/作坊系统（配方：粮→酒/肉 等）：{wid: {...}}
        # 加消耗修正·加工型消耗依托建筑：开局每路 2 酒坊 + 2 畜栏（各 ×5万石/月太仓粮耗 → 120万石/月），
        # 酒坊产酒增 wine_tax、畜栏产肉折钱入内帑（玩家可建更多；存档已序列化 workshops）
        from content.data import PREFECTURE_INFO, WORKSHOP_RECIPES
        self.workshops = {}
        _widx = 0
        for _rname in PREFECTURE_INFO:
            for _ in range(2):
                _jw = WORKSHOP_RECIPES["酒坊"]
                self.workshops[f"酒坊_{_rname}_{_widx}"] = {
                    "name": "酒坊", "recipe": dict(_jw["recipe"]), "output_dim": _jw["output_dim"],
                    "yield": _jw["yield"], "active": True}
                _jc = WORKSHOP_RECIPES["畜栏"]
                self.workshops[f"畜栏_{_rname}_{_widx}"] = {
                    "name": "畜栏", "recipe": dict(_jc["recipe"]), "output_dim": _jc["output_dim"],
                    "yield": _jc["yield"], "active": True}
                _widx += 1
        # 内帑（甲口径）：imperial_treasury = 国库净结余抽成 + 榷酒课，与国库分理
        # 对话口谕内帑调拨（商量确认式）：皇帝谕发内帑入国库，大臣商量回奏、当场点「准」才守恒移库
        self.pending_inner_transfer = None   # {"amount": 贯, "turn": 回合}；None=无待准调拨
        # free_effect 长期制度队列（言枢密 v3 契约）：[{name, mode, duration, effects, cost}]，
        # 由 _settle_free_effects 在「长期诏」步位月度结算；存档已序列化
        self.longterm_effects: list = []
        # 记忆知识库（Phase 3a）：图谱存史、跨回合连贯；按存档槽位读写
        from memory.memory_graph import MemoryGraph
        self.memory = MemoryGraph()
        self.memory_slot = 0
        # 短期记忆库（Phase 3b，用户指示：短期不污染上下文、做过的事有记录）：
        # append-only 行为日志（圣旨/口谕/决策，全量保留、可追溯、**不注入 AI 上下文**）
        self.short_term_log: list = []
        # 大臣自设工具注册表（三方案：注册护栏 + 上限 16 + 存档持久化）
        self.tool_registry: dict = {}
        # 新兵种注册表（branch_registry 仿 tool_registry：玩家自由设立 + 门槛 + 存档）
        self.branch_registry: dict = {}
        # 玩家科技注册表（tech_registry 仿 branch_registry：承接天马行空 + 门槛 + 存档）
        self.tech_registry: dict = {}
        # 金融推演价格系数（通胀/通缩 ±5%，clamp [0.5,3.0]；月度重置不落档）
        self._price_mult: float = 1.0
        # 时代状态（建筑-时代交互，言枢密方案）：五维认知层 0-100 刻度（兴/平/衰 程序定幅迁移）
        from content.data import ERA_DIMENSIONS
        self.era_state: dict = {d: 50 for d in ERA_DIMENSIONS}
        # 建筑兴衰记录（记忆图谱 building 实体 + 毁损标记）
        self.era_building_log: list = []
        # 大臣家产（言枢密设计）：{大臣: {wealth, land}}；开局基线 ESTATE_INIT（存档序列化）
        from content.data import ESTATE_INIT
        self.minister_estate: dict = {k: dict(v) for k, v in ESTATE_INIT.items()}
        # POP 建筑（政府 projects 复用；POP 建筑按路）：prefectures[路].buildings 由 _build_pops 初始化
        # 投资记录（invest_decide 记账）：{invest_id: {field, fund, amount, return, risk, months_left, seized}}
        self.investments: dict = {}
        # 加俸预算（厚禄养廉政令投入，逐月驱动 pay_ratio 上升）
        self.payraise_budget: int = 0
        # 监察力度（整顿吏治提升，压缩贪腐扣减）
        self.oversight: float = 0.30

        # ---- 中央粮仓（太仓，实物粮石；田赋征本色经漕运汇聚于此）----
        self.granary: int = GRANARY_START
        self.granary_cap: int = GRANARY_START_CAP     # 仓容（石），可经新建仓储工程扩建
        self.granary_stats: dict = {"canal_in": 0, "military": 0, "converted": 0,
                                    "relief": 0, "tax": 0, "sparrow": 0, "canal_loss": 0,
                                    "official": 0}

        # ---- 通货 / 物价（货币经济学，钱/物之比）----
        self.money_supply: float = MONEY_SUPPLY_START   # 货币有效供给（贯）
        self.price_level: float = PRICE_LEVEL_BASE      # 物价水平（基准 1.0）

        # ---- 工商征率（玩家可调，对工商经济总量按"几成"征收）----
        # 默认 0.15（抽一成五）：对 calc_commerce() 年工商产出征 15%。
        # 玩家经诏令/滑动条调整；调高增收但增民怨/商旅怨，调低减收但惠商。
        self.commerce_tax_rate: float = COMMERCE_TAX_RATE_DEFAULT
        self.tax_breakdown: dict = {"commerce": 0, "poll": 0}  # 本月货币税分项（会计录展示用）
        # 变法节流（省浮费/裁汰冗员）：隐性三冗不可见不可直裁，只能经长期变法逐月挤出水分。
        #   {"active": bool, "kind": "curtail_waste|reduce_office", "savings": 月省贯,
        #    "target": 目标月省贯, "months_left": 剩余月数, "progress": 0~100}
        self.waste_reform: dict = {"active": False, "kind": "", "savings": 0,
                                   "target": 0, "months_left": 0, "progress": 0}

        # ---- 漕运状态（0 通畅 ~ 100 阻塞）----
        self.canal_block: int = CANAL_BLOCK_START

        # ---- 一条鞭法（False=征本色 / True=田赋改征银入国库）----
        self.single_whip: bool = False

        # ---- 历史改写位（玩家改革改写史实）----
        # 玩家改革/战略达成充分条件后写入改写位，关闭或偏转史实硬锚。
        # {改写位id: {"year": 触发年, "label": 描述}}
        #   jin_crushed  灭金于萌芽（金军永不南侵）
        #   liao_ally    联辽抗金（辽免衰、金的崛起被压制）
        #   no_jingkang  避免靖康（国力/外交达线后金军南侵事件失效）
        self.timeline: dict = {}

        # ---- 待确认改写位（战略决策点·奏报朱批）----
        # 玩家成效达线后先写入此处为「候选」，并不直接改写历史；
        # 待奏报中「枢密院/军机密奏」由陛下朱批「准予/从长计议」后，
        # 才由 commands.confirm_timeline_break 正式落 timeline。
        # {改写位id: {"year": 年, "label": 描述}}
        #   jin_crushed  灭金于萌芽（金 power≤25）
        #   liao_ally    联辽抗金（辽 attitude≥70）
        #   no_jingkang  避免靖康（威望≥70+兵力≥280+金 invasion_will<40）
        self.pending_breaks: dict = {}

        # ---- 俸禄/军饷制度（支出侧货币化演化）----
        self.pay_system: dict = dict(PAY_SYSTEM_DEFAULT)

        # ---- 动态粮价（贯/石，区域+通货+季节+丰歉驱动）----
        self.grain_price: float = 1.0

        # ---- 经济信息不对称：真实层 vs 认知层（滞后奏报）----
        self.economy_history: list = []      # 真实层快照环形缓冲（近 12 月）
        self.economy_knowledge: dict = {}    # 认知层（朝廷实际掌握的奏报认知）

        # ---- 派系 ----
        self.factions: dict = {}
        for name in FACTION_NAMES:
            init = FACTION_INIT[name].copy()
            self.factions[name] = {
                "influence": init["influence"],
                "satisfaction": init["satisfaction"],
                "cohesion": init["cohesion"],
                "leader": init["leader"],
                "net_support": 0,  # stance * influence/100
                "decree_stance": 0,  # -1/0/+1 对当前政令态度
                "last_decree_comment": "",
            }

        # ---- 外部势力 ----
        self.external: dict = {}
        for k, v in EXTERNAL_FORCES.items():
            self.external[k] = v.copy()
        self.external["金"]["invasion_will"] = 0

        # ---- 军事（兵额唯一真账 = army_units 实体列表）----
        # 旧 self.armies（质量参数 dict）已废弃：质量并入 UNIT_TIER，战力由 _army_power 派生。
        # 旧各路 prefectures[路]["garrisons"] 已删除：兵额改由各路 army_units.troops 求和派生。
        # 延迟导入：core 不得顶层依赖 ui（避免潜伏环），见 TEAM.md 工程约束
        from ui.panels_military import build_army_units, CentralArsenal
        self.army_units: list = build_army_units(self)
        # 中央武库
        self.central_arsenal: CentralArsenal = CentralArsenal()
        # defense_lines：fortification 取 DEFENSE_LINES 初值，garrison 由 army_units 聚合派生（见 _derive_defense）
        self.defense_lines: dict = {}
        for k, v in DEFENSE_LINES.items():
            self.defense_lines[k] = dict(v)  # v 仅含 fortification
        # 注意：_derive_defense_lines 依赖 self.army_units，须在军事初始化完成后调用（见下方）

        # ---- 诏令 ----
        self.decree_bandwidth: int = DECREE_BASE_BANDWIDTH
        self.direct_decree_used: int = 0
        self.wolf_count: int = 0   # 狼来了计数器
        self.pending_decrees: list = []  # 待执行圣旨（旧规则程序）
        self.pending_secret_decrees: list = []  # 待执行密令（即时，由 _settle_decrees 处理）
        self.pending_public_decrees: list = []  # 旧兼容字段（保留）
        self.longterm_public: list = []   # 在办公开事务（长期，月度推进）
        self.longterm_secret: list = []   # 在办密令（长期，月度推进）
        self.active_decrees: list = []  # 持续效力的政令
        self.edict_drafts: list = []    # 待会签诏草（诏令会签页）
        self.council_reviews: dict = {}  # draft_id -> 会签意见

        # ---- 施政 ----
        self.personal_action: str = ""   # 旧单值个人行动（兼容旧档；新通道走 imperial_action）
        self.imperial_action: dict = {}  # 皇帝个人行动矩阵（契约 v2）：
        #   {location, mode, action, prepared, pending_months, target}；
        #   pending_months > 0 表示出京准备中（pending_imperial_trip 月度推进）
        self.pending_imperial_trip = None   # 出京准备期（= imperial_action 同一 dict；准备中非 None，成行后置 None）
        self.imperial_micro_count: int = 0  # 微服京城每月 1 次计数（程序限，结算月末归零）
        self._emperor_ai = None             # 皇帝个人行动 AI 推演槽位（契约 v2 结果，回合内瞬态不落档）
        self.major_policy: str = ""
        self.major_policy_target: str = ""

        # ---- 事件 ----
        self.active_events: list = []
        self.event_pressure: dict = {}
        self.event_history: list = []

        # ---- 人口/民生 ----
        self.population: int = 80_000_000   # 约8000万
        self.population_satisfaction: int = 55
        # 注意：refugee_count 已改为各路 refugees 求和的 property 派生（见类末），
        # 此处不再作为独立存储字段；保留兼容赋值语义由 property setter 兜底。

        # ---- 灾荒 ----
        self.disaster_severity: int = 0
        self.disaster_region: str = ""

        # ---- 难度系数 ----
        self.diff_params = diff

        # ---- 统计 ----
        self.statistics: dict = {
            "total_income": 0,
            "total_expenditure": 0,
            "total_decrees": 0,
            "total_wars": 0,
            "total_disasters": 0,
        }

        # ---- 锦衣卫渗透 (密折) ----
        self.spy_network: dict = {fn: 0.0 for fn in FACTION_NAMES}
        self.spy_network["宫禁"] = 0.5

        # ---- 记录 ----
        self.settlement_log: list = []
        self.game_over: bool = False
        self.game_result: str = ""
        self.victory: bool = False

        # ---- 四大机制改良（参考《明末：捞金模拟器》）----
        # 开局邸报（文言局势 + 待办三事）：new_game 时由 content/legacy_gazette 生成注入
        self.opening_gazette: dict = {}
        # 帝国修正（legacies）：开局即存在的条件式长期修正符，带消除条件
        self.legacies: dict = {}
        # 国策树（focus）：五大分支（政务/军事/科学/内卫/税务），权力等级 + 互斥 + 解锁建筑
        self.focus_tree: dict = {}

        # ---- 六部衙门 ----
        self.yamen: dict = {}
        for name in YAMEN_LIST:
            info = YAMEN_INFO[name]
            self.yamen[name] = {
                "duty": info["duty"],
                "faction": info["faction"],
                "efficiency": 60,          # 衙门施政效率 0-100
                "backlog": 0,              # 积压政务
                "acts": list(info["acts"]),
            }

        # ---- 地方州县 ----
        self.prefectures: dict = {}
        for name in PREFECTURE_LIST:
            info = PREFECTURE_INFO[name]
            p_type = info.get("type", "腹里州路")
            self.prefectures[name] = {
                "name": info.get("name", name),     # 舆图展示名（可由圣旨更名）
                "households": info["households"],   # 户数(户)
                "land": info["land"],               # 田亩(亩，在册 = 自耕农田 + 地主田 + 官田 + 皇庄)
                # 田亩归属（开局数据，随抑兼并/清丈/隐漏演化）：粮是田产的，按归属分配
                "self_farm_land": int(info["land"] * 0.40),   # 自耕农田（亩，主户自耕，产粮自留）
                "gentry_land": int(info["land"] * 0.50),      # 地主田（亩，士绅所有，佃户租种交租）
                "official_land": int(info["land"] * 0.08),    # 官田（亩，官府所有，租佃租入归国库）
                "imperial_land": int(info["land"] * 0.02),    # 皇庄（亩，皇室所有，产粮归内帑）
                "grain": info["grain"],             # 粮产(石)
                "mood": info["mood"],               # 民情 0-100
                "govern": info["govern"],           # 治理度 0-100
                "population": info.get("population", info["households"] * 4),  # 人口(口，在籍，户均4口)
                "unrest": info.get("unrest", 15),               # 动乱 0-100
                "monthly_tax": info.get("monthly_tax", 200_000),     # 月税实收锚(贯)→二税折色 tax_base
                "hidden_land": info.get("hidden_land", 0),      # 隐田(亩，开局数字 = land×25%，随清丈/隐漏回升演化)
                "storage": info.get("storage", 0),              # 存粮(石，州仓/上供仓，漕运只动此仓)
                # 常平仓存粮（石，平抑储备，与州仓 storage 分离、不参与漕运上供）：
                # 初值 = 月产 20%；容量上限 = 月产 50%（见 _settle_granary），防止籴入无上限膨胀
                "changping_stock": info.get("changping_stock",
                                            round(info.get("grain", 0) / 12 * 0.2)),
                # 经济全浮动重构新增字段（兼容缺省）
                "grain_yield": info.get("grain_yield", info["grain"]),   # 兼容旧字段：粮年产量(石/年)（新口径 grain 即年产，不再 ×12）
                "yields": dict(info.get("yields", {})),                        # 七维物资初值
                "officials": info.get("officials", round(info["households"] * 0.00135)),  # 官数（真实官；households 为在籍明户，×0.00135 → 全国约 2.7 万官，史实 2-4 万）
                "clerks": info.get("clerks", round(info["households"] * 0.00135) * 8),    # 吏数（=官×8，全国约 21.6 万，史实 20-30 万）
                "route_mult": info.get("route_mult", 1.0),                     # 路级乘数
                # 地方财力（贯，俸给足额率用）：地方留成月税实收的 25% 作俸给财力。
                # 单位统一：不得用 storage（石）当财力（贯），否则 pay_ratio 恒满、吏俸缺口恒 0。
                "local_finance": info.get("local_finance",
                                          round(info.get("monthly_tax", 200_000) * 0.25)),
                # 地方府库（贯）：州县常平仓粜籴的钱账（与中央国库分理），初值约 3 个月税入
                "local_treasury": info.get("local_treasury",
                                           round(info.get("monthly_tax", 200_000) * 3)),
                # POP 人口群体（参考维多利亚）：每路按职业分六群体，每群体 {size, wealth, grain}
                # 士绅 wealth/grain 即其囤粮居奇的资金与粮储（钱粮守恒，取代旧 civilian_granary/gentry_treasury）
                "pops": _build_pops(info, p_type),
                # POP 建筑（言枢密设计）：{农田/工坊/商铺/庄园: Lv1-5}，阶层 wealth 出资；
                # 效果乘数对既有公式（×0.05/Lv 封顶 ×2.0），守恒走既有路径；存档迁移缺省 {}
                "buildings": {},
                "pay_ratio": 0.5,                                              # 俸给充足率初值
                "gap": 0,                                                      # 俸给缺口初值
                # 开局区域米价：按"京畿边镇贵、膏腴贱"原则给变量（避免开局全 1.00 平庸），
                # 后续由 calc_region_grain_price 每月按供需比动态调整覆盖此值。
                "grain_price": PREFECTURE_INITIAL_GRAIN_PRICE.get(p_type, 1.00),
                "type": p_type,
                "is_capital": info.get("is_capital", False),
                # ---- 按路本地流民池（五层地理挂载数据地基）----
                # 真相源为各路本地，全局 refugee_count 退化为各路求和派生。
                # 开局按 unrest/type 赋极低基数：边镇/高动乱路略高，腹里近 0。
                "refugees": _init_local_refugees(info),
                # 本路所辖机构分支列表（与 central_orgs[机构]["branches"] 双向索引）
                "orgs": [],
                "rename_log": [],
                # ---- 地区模型深化（参考《明末：捞金模拟器》）----
                # 控制势力：默认宋；领土争夺时可为"辽/西夏/金/叛军"等
                "controlled_by": info.get("controlled_by", "宋"),
                # 民心（0~100）：与 mood 同源，供地区深化结算与展示
                "public_support": info.get("public_support", info["mood"]),
                # 士绅抵抗（0~100）：士绅对朝廷政策的抵抗度（清丈/仰兼并时上升）
                "gentry_resistance": info.get("gentry_resistance",
                                              max(0, min(100, 100 - int(info["govern"])))),
                # 城防（0~100）：城防坚固度（边镇高、腹里低）
                "city_defense": info.get("city_defense",
                                         _init_city_defense(p_type)),
                # 财政（贯/月）：地方财政健康度（0~100，基于月税与支出）
                "fiscal": info.get("fiscal",
                                   max(0, min(100, round(int(info.get("monthly_tax", 200_000)) / 8000)))),
            }

        # 兵额回填到各路 POP：兵 POP.size = 该路 army_units 兵额合计（兵额唯一真账）
        for u in self.army_units:
            if u.station in self.prefectures and u.troops > 0:
                self.prefectures[u.station]["pops"]["兵"]["size"] += u.troops

        # 开局货币校准（A1 定稿）：修复 F1（士绅卖粮造币）后补开局货币，防跌回通缩地板。
        # 注入民间 wealth（按各 POP 财富比例分配），不注入国库——物价由民间购买力驱动。
        from content.data import START_MONEY_BOOST
        _boost = START_MONEY_BOOST
        _total_w = sum(pop.get("wealth", 0)
                       for _p in self.prefectures.values() for pop in _p["pops"].values())
        if _boost > 0 and _total_w > 0:
            for _p in self.prefectures.values():
                for pop in _p["pops"].values():
                    pop["wealth"] += int(_boost * pop.get("wealth", 0) / _total_w)

        # 防区派生：此时 prefectures 已就绪（fortification 由 DEFENSE_LINES 初值，garrison 由各路聚合）
        self._derive_defense_lines()

        # ---- 外部政权（31 个，完整数据 + 简单模拟） ----
        self.external_regimes: dict = {}
        for key, info in EXTERNAL_REGIMES.items():
            item = {k: v for k, v in info.items() if k != "hotspot"}
            item["growth_curve"] = dict(info["growth_curve"])
            item["rename_log"] = []
            self.external_regimes[key] = item

        # ---- 田亩户籍 ----
        self.land = dict(LAND_INFO)

        # ---- 奏对历史（召见大臣多轮对话） ----
        self.dialogue_history: list = []   # [(speaker, text), ...]
        self.last_audience: str = ""       # 最近召见的大臣

        # ---- 扩展维度：金融/货币/市舶/交子/银行/本位 ----
        self.jiaozi = dict(JIAOZI_INFO)
        self.maritime = dict(MARITIME_INFO)
        self.coin = dict(COIN_INFO)
        self.bank = dict(BANK_INFO)
        self.standard = dict(STANDARD_INFO)

        # ---- 扩展维度：科举/学校 ----
        self.exam = dict(EXAM_INFO)

        # ---- 扩展维度：科技/工技 ----
        self.tech = dict(TECH_INFO)
        # 开局默认已启北宋既有之器（DEFAULT_UNLOCKED 9 根节点）
        if not self.tech.get("unlocked"):
            from content.data import DEFAULT_UNLOCKED
            self.tech["unlocked"] = list(DEFAULT_UNLOCKED)
        # 研发管线（五层③）：玩家可研项目 {名: {progress, masters, monthly_cost}}
        self.tech.setdefault("projects", {})

        # ---- 机制槽（五层②）：{机制名: {org, params, progress}} ----
        self.mechanisms: dict = {}

        # ---- 扩展维度：外交细化（金/辽/夏关系动作后的态势标记） ----
        self.diplomacy_log: list = []      # 外交动作记录
        self.alliance_jin_liao: bool = False  # 是否联金抗辽（海上之盟）
        # 外交对话协议（言枢密 diplomacy_dialogue 落地；存档持久化）
        self.treaties: dict = {}                 # {势力: [{type, terms, turn, year, month}]}
        self._at_war: dict = {}                  # {势力: 1/0} 战争标记
        self._sui_gong_mult: dict = {"辽": 1.0, "金": 1.0, "西夏": 1.0}   # 岁币倍率
        self._trade_income: dict = {}            # {势力: 榷场月入}

        # ---- 大臣长期记忆（真 function calling 落档；存档兼容旧档缺字段默认空） ----
        self.minister_memory: dict = {}    # {大臣名: [办差记录/长久偏好]}
        self.player_minister_status: dict = {}  # {大臣名: "active"|"dead"|"dismissed"} 角色状态校验

        # ---- 大臣忠诚度（后台隐藏，不可见；0.0 离心 ~ 1.0 死忠）----
        # 注意：权限归属机构/职位（见 central_orgs），忠诚度归属个人，二者分离。
        self.loyalty: dict = loyalty_init()

        # ---- 大臣贪腐度（后台隐藏，不可见；0.0 清廉 ~ 1.0 贪墨极甚）----
        # 随制度/圣旨颁布后的事件联动变化，绝不进入任何 UI 文本。
        self.corruption: dict = corruption_init()

        # ---- 中枢机构运行态（权限跟随机构/职位，不跟随人）----
        # lead 由 posts[0].holder 派生（兼容旧接口）；posts/holders/comissions 承载权限。
        self.central_orgs: dict = {
            name: {
                "lead": org_lead(info),
                "belong": info.get("belong", "皇帝"),
                "scope": info.get("scope", ""),
                "authority": list(info.get("authority", [])),
                "matter_keys": list(info.get("matter_keys", [])),
                "posts": [dict(p) for p in info.get("posts", [])],   # 岗位表（属机构）
                "holders": dict(info.get("holders", {})),            # 人岗映射（换人不变权）
                "comissions": list(info.get("comissions", [])),      # 差遣列表（交差即撤）
                "abolished": False,        # 是否被裁撤
                "efficiency": 1.0,         # 运行效率倍率（改制后果结算用）
                "backlog": 0,              # 政务积压
                # ---- 五层承接层扩展字段 ----
                "branches": {},            # 地理挂载：{路名: [分机构名]}（与 prefectures[路]["orgs"] 双向索引）
                "budget_in": 0,           # 机构经济生命周期：本月进项（朝廷拨/民间工程，贯）
                "budget_out": 0,          # 机构经济生命周期：本月支出（工匠俸/工训营/流民口粮，贯）
                "net": 0,                 # 机构经济生命周期：本月净结余（受崩盘线约束）
            }
            for name, info in CENTRAL_ORG_INFO.items()
        }
        self.authority_matters: dict = {
            k: dict(v) for k, v in AUTHORITY_MATTERS.items()
        }

    # ================================================================
    # 皇威工具
    # ================================================================
    def get_prestige_info(self) -> dict:
        level, w, authority = get_prestige_level(self.prestige)
        return {
            "value": self.prestige,
            "level": level,
            "multiplier": w,
            "authority_index": authority,
            "description": desensitize_prestige(self.prestige),
        }

    def change_prestige(self, delta: int, reason: str = "", is_major: bool = False):
        """修改皇威，自动做上限截断"""
        cap = 15 if is_major else 8
        delta = max(-cap, min(cap, delta))
        self.prestige = max(0, min(100, self.prestige + delta))
        self._prestige_history.append((self.turn, delta, reason, self.prestige))

    # ================================================================
    # 国库工具
    # ================================================================
    def change_treasury(self, delta: int):
        """修改国库"""
        self.treasury += delta

    def change_imperial_treasury(self, delta: int):
        """修改内帑（皇帝私库，与国库分理）"""
        self.imperial_treasury += delta

    def change_granary(self, delta: int):
        """修改中央粮仓存粮（石），自动封顶于容量。"""
        self.granary = max(0, min(self.granary_cap, self.granary + delta))

    def granary_capacity_used(self) -> float:
        return self.granary / max(self.granary_cap, 1)

    def change_granary_cap(self, delta: int):
        """新建仓储：扩建中央仓容量（石）。"""
        self.granary_cap = max(0, min(GRANARY_CAP_SOFT, self.granary_cap + delta))

    # 经济计算族见 core/game_state_econ.GameStateEconMixin（mixin 继承）
    def _derive_defense_lines(self):
        """由各路 army_units 聚合防线兵额（兵额唯一真账 = unit.troops）。"""
        ga = {line: 0 for line in self.defense_lines}
        for u in self.army_units:
            if u.defense_line in ga:
                ga[u.defense_line] += u.troops
        for k, v in self.defense_lines.items():
            v["garrison"] = int(ga.get(k, 0))

    def defense_lines_view(self) -> dict:
        """返回防区派生只读视图（每次调用实时聚合）。"""
        self._derive_defense_lines()
        return {k: dict(v) for k, v in self.defense_lines.items()}

    # ================================================================
    # 诏令执行率
    # ================================================================
    def calc_decree_execution_rate(self, faction_stances: dict, is_secret: bool = False,
                                    is_direct: bool = False, secret_loyalty: float = 0.5,
                                    is_zhongzhi: bool = False, org_hint: str = "政府") -> float:
        """计算诏令执行率。
        中旨（御笔强推）按机构归属执行率：内廷 1.0 / 政府 0.85 / 地方 0.60。"""
        from content.data import ZHONGZHI_AFFILIATION_RATE
        _, w, _ = get_prestige_level(self.prestige)

        # 净支持 = Σ(立场 × 影响力/100)
        net_support = 0.0
        faction_conflict = 0.0
        for name, stance in faction_stances.items():
            f = self.factions[name]
            inf = f["influence"] / 100.0
            if stance == 1:
                net_support += inf
            elif stance == -1:
                net_support -= inf
                faction_conflict += inf

        if is_secret:
            s = 0.30 + secret_loyalty * 0.7
        elif is_zhongzhi:
            # 中旨绕过会签，执行率主要由机构归属决定
            base = ZHONGZHI_AFFILIATION_RATE.get(org_hint, 0.85)
            s = base + net_support * 0.04
        else:
            s = 0.45 + net_support * 0.08
            if is_direct:
                s += (0.10 if self.wolf_count < 3 else -0.15)
            else:
                # 经会签的正式诏：门下封驳已消化的部分冲突，执行率略稳
                pass

        s -= faction_conflict * 0.15

        e = max(0.05, min(0.95, w * s))
        return e

    # ================================================================
    # 诏草与会签（拟旨·会签）
    # ================================================================
    def add_edict_draft(self, draft: dict) -> str:
        """将一道诏草加入待会签队列，返回 draft_id。"""
        import uuid
        did = "d" + uuid.uuid4().hex[:8]
        draft["id"] = did
        draft.setdefault("kind", "formal")
        draft.setdefault("org_hint", "政府")
        draft.setdefault("title", "御笔诏")
        draft.setdefault("body", "")
        draft.setdefault("effects", [])
        draft.setdefault("source_minister", "陛下亲拟")
        draft.setdefault("turn_created", self.turn)
        draft.setdefault("reviewed", False)
        self.edict_drafts.append(draft)
        return did

    def get_edict_draft(self, draft_id: str):
        for d in self.edict_drafts:
            if d.get("id") == draft_id:
                return d
        return None

    # ================================================================
    # 大臣角色状态（死亡 / 革职）校验 —— 防错：不在朝之臣不可办差
    # ================================================================
    def minister_status(self, name: str) -> str:
        """返回大臣状态：'active' | 'dead' | 'dismissed'；缺省视为主事在朝。"""
        return self.player_minister_status.get(name, "active")

    def mark_minister_status(self, name: str, status: str) -> None:
        if status in ("active", "dead", "dismissed"):
            self.player_minister_status[name] = status

    def is_minister_available(self, name: str) -> bool:
        return self.minister_status(name) == "active"

    def remove_edict_draft(self, draft_id: str):
        self.edict_drafts = [d for d in self.edict_drafts if d.get("id") != draft_id]
        self.council_reviews.pop(draft_id, None)

    def store_council_review(self, draft_id: str, review: dict):
        self.council_reviews[draft_id] = review

    # ================================================================
    # 年号管理
    # ================================================================
    def update_era_name(self):
        for year, name in sorted(ERA_NAMES_HISTORY.items(), reverse=True):
            if self.year >= year:
                self.era_name = name
                break

    # ================================================================
    # 改制推演素材（供结算 AI；忠诚度隐藏为定性档位，绝不下放数字）
    # ================================================================
    def _loyalty_band(self, name: str) -> str:
        """把后台忠诚度映射为定性档位（玩家不可见数值）。"""
        v = self.loyalty.get(name, 0.5)
        if v >= 0.75:
            return "效忠"
        if v >= 0.55:
            return "顺从"
        if v >= 0.38:
            return "敷衍"
        return "离心"

    def authority_brief_for_ai(self, target_org: str = "", target_ministers: list = None) -> str:
        """为改制结算 AI 组装定性上下文：威望 + 相关机构运行态度 + 大臣定性效忠度。
        注意：只给定性（效忠/顺从/敷衍/离心），绝不给 loyalty 数值。
        """
        pi = self.get_prestige_info()
        prestige_line = f"圣威：{pi['level']}（{pi['description']}）"

        org_lines = []
        orgs = [target_org] if target_org else list(self.central_orgs.keys())
        for oname in orgs:
            o = self.central_orgs.get(oname)
            if not o:
                continue
            lead = o.get("lead", "")
            band = self._loyalty_band(lead) if lead else "无主官"
            status = "已裁撤" if o.get("abolished") else f"运行效率×{o.get('efficiency', 1.0):.2f}/积压{o.get('backlog', 0)}"
            org_lines.append(f"  - {oname}（主官{lead}：{band}；{belong if (belong:=o.get('belong')) else '皇帝'}下属；{status}）")

        minister_lines = []
        for m in (target_ministers or []):
            if m in self.loyalty:
                minister_lines.append(f"  - {m}：{self._loyalty_band(m)}")

        brief = [prestige_line, "中枢机构态势："]
        brief += org_lines if org_lines else ["  （无）"]
        if minister_lines:
            brief.append("相关大臣定性态度：")
            brief += minister_lines
        return "\n".join(brief)

    # ================================================================
    # 中枢相关大臣（供廷议入对）
    # ================================================================
    def org_ministers(self, org_name: str) -> list:
        """返回某机构「依职权回话」的相关大臣：含各岗位在任者与在办差遣领办人。
        只返回在朝（loyalty 中存在）者；空岗/差遣未领办不纳入。
        """
        o = self.central_orgs.get(org_name)
        if not o or o.get("abolished"):
            return []
        names = []
        for holder in (o.get("holders") or {}).values():
            if holder and holder not in names:
                names.append(holder)
        for com in (o.get("comissions") or []):
            if isinstance(com, dict) and com.get("lead") and com["lead"] not in names:
                names.append(com["lead"])
        # 仅保留在朝者（loyalty 存在即视为可入对）
        return [n for n in names if n in self.loyalty]

    def matter_org(self, matter_key: str) -> str:
        """返回某事权当前 owner 机构名（改权限/越权授权后可动态变化）。"""
        info = self.authority_matters.get(matter_key) or {}
        return info.get("owner", "")

    # ================================================================
    # 获取完整状态摘要
    # ================================================================
    def get_state_summary(self) -> dict:
        """获取完整状态，用于 AI 调用"""
        pi = self.get_prestige_info()
        arrival = self.calc_arrival_rate()
        arrival_desc = desensitize_arrival(arrival)
        treasury_desc = desensitize_treasury(self.treasury)

        return {
            "time": f"{self.era_name}{self.year}年{self.month}月",
            "prestige": {"value": self.prestige, "level": pi["level"], "desc": pi["description"]},
            "health": self.emperor_health,
            "treasury": {"amount": self.treasury, "desc": treasury_desc},
            "imperial_treasury": {"amount": self.imperial_treasury, "desc": desensitize_treasury(self.imperial_treasury)},
            # 认知层滞后值（上月 economy_knowledge 快照，供脱敏层做"奏报延迟"）
            "treasury_lagged": self.economy_knowledge.get("treasury"),
            "imperial_treasury_lagged": self.economy_knowledge.get("imperial_treasury"),
            "granary_lagged": self.economy_knowledge.get("granary"),
            "refugee_count_lagged": self.economy_knowledge.get("refugee_count"),
            "arrival_rate": {"value": round(arrival, 2), "desc": arrival_desc},
            "factions": {
                name: {
                    "influence": f["influence"],
                    "satisfaction": f["satisfaction"],
                    "sat_desc": desensitize_satisfaction(f["satisfaction"]),
                }
                for name, f in self.factions.items()
            },
            "external": self.external,
            "military": {
                "garrisons": {
                    name: _garrison_by_tier(self, name)
                    for name in self.prefectures
                    if any(u.station == name and u.troops > 0 for u in self.army_units)
                },
                "armies": {u.unit_id: {"name": u.name, "tier": u.tier, "branches": dict(u.branches),
                                       "troops": u.troops, "morale": u.morale,
                                       "training": u.training, "station": u.station,
                                       "defense_line": u.defense_line}
                           for u in self.army_units},
                "defenses": self.defense_lines,
            },
            "population": self.population,
            "pop_satisfaction": self.population_satisfaction,
            "pop_sat_desc": desensitize_satisfaction(self.population_satisfaction),
            "refugee_count": self.refugee_count,
            "decree_bandwidth": self.decree_bandwidth,
            "pending_decrees": len(self.pending_decrees),
            "active_events": self.active_events,
            "event_pressure": self.event_pressure,
            "personal": {
                "art": self.art_mastery,
                "taoism": self.taoism_leaning,
                "pleasure": self.pleasure_leaning,
            },
            # ---- 扩展维度（脱敏） ----
            "finance_ext": {
                "jiaozi_trust": desensitize_trust(self.jiaozi["trust"]),
                "coin_shortage": desensitize_shortage(self.coin["shortage"]),
                "maritime_open": "广开市舶" if self.maritime["open"] else "市舶未广",
                "bank": "已设官营银行" if self.bank["established"] else "未设银行",
                "commerce_tax": self._describe_tax_rate(),
            },
            # ---- 仓廪 / 通货（脱敏定性，供 AI 认知层） ----
            "granary_ext": {
                "granary": desensitize_granary(self.granary, self.granary_cap),
                "granary_util": round(self.granary_capacity_used(), 2),
                "price": desensitize_price(self.grain_price),
                "price_level": round(self.price_level, 2),
                "canal": desensitize_canal(self.canal_block),
                "pay": self.pay_system.get("mode", "本色折色"),
                "whip": "已行一条鞭" if self.single_whip else "仍征本色",
            },
            "granary_amount": self.granary,
            # ---- 米价趋势（数值供脱敏层比较，不直发 AI） ----
            "grain_price": round(self.grain_price, 3),
            "grain_price_prev": round(self.economy_knowledge.get("grain_price", self.grain_price), 3),
            "exam_ext": {
                "open": "开科取士" if self.exam["open"] else "停科",
                "mode": self.exam["mode"],
                "talent": desensitize_talent(self.exam["talent_pool"]),
            },
            "tech_ext": {
                "level": desensitize_tech(self.tech["level"]),
                "gunpowder": self.tech["gunpowder"],
            },
            "diplomacy_ext": {
                "alliance": "已联金抗辽" if self.alliance_jin_liao else "未结海上之盟",
            },
            # 大臣角色状态（死亡/革职）摘要：供叙事防错与锚定
            "minister_states": {
                n: st for n, st in self.player_minister_status.items()
                if st in ("dead", "dismissed")
            },
        }

    @property
    def posture(self) -> str:
        """AI 所需的精简脱敏态势字符串。

        改进：国库/太仓/流民用区间脱敏（"约X至Y万缗"）替代纯定性
        （"充裕"），让 AI 知道量级可做有依据判断，但区间内不确定性
        使其无法精确计算最优解——这才是真实的决策混沌。
        认知层滞后：经济读数用上月快照（economy_knowledge），模拟奏报延迟。
        """
        from ai.desensitize import desensitize_band
        s = self.get_state_summary()
        fin = s.get("finance_ext", {})
        ex = s.get("exam_ext", {})
        te = s.get("tech_ext", {})
        gr = s.get("granary_ext", {})
        _att = lambda a: "友善" if a >= 70 else ("一般" if a >= 40 else ("敌视" if a >= 20 else "仇敌"))
        # 区间脱敏：国库/太仓/流民用区间+认知层滞后，其余仍用定性
        _treasury_band = desensitize_band(
            s["treasury"]["amount"], "缗", width_pct=0.20,
            lag_value=s.get("treasury_lagged"))
        _granary_band = desensitize_band(
            s.get("granary_amount", 0), "石", width_pct=0.20,
            lag_value=s.get("granary_lagged")) if s.get("granary_amount", 0) > 0 else "太仓告罄"
        _ref = s.get("refugee_count", 0)
        _ref_band = desensitize_band(
            _ref, "口", width_pct=0.25,
            lag_value=s.get("refugee_count_lagged")) if _ref > 0 else "无"
        return (
            f"时间：{s['time']}；皇威：{s['prestige']['desc']}；"
            f"国库：{_treasury_band}（{s['treasury']['desc']}）；"
            f"太仓：{_granary_band}；流民：{_ref_band}；民心：{s['pop_sat_desc']}；"
            f"金融：交子{fin.get('jiaozi_trust','')}、{fin.get('coin_shortage','')}、{fin.get('maritime_open','')}；"
            f"仓廪：{gr.get('granary','')}、米价{gr.get('price','')}、"
            f"漕运{gr.get('canal','')}、{gr.get('whip','')}、俸禄{gr.get('pay','')}；"
            f"科举：{ex.get('open','')}（{ex.get('mode','')}）、人才{ex.get('talent','')}；"
            f"科技：{te.get('level','')}；外交：{s.get('diplomacy_ext',{}).get('alliance','')}；"
            f"金态度：{_att(self.external.get('金',{}).get('attitude',50))}，"
            f"辽态度：{_att(self.external.get('辽',{}).get('attitude',50))}，"
            f"西夏态度：{_att(self.external.get('西夏',{}).get('attitude',50))}。"
        )

    # ================================================================
    # 五层⑤：按路本地流民 —— 全局 refugee_count 退化为各路求和派生
    # ================================================================
    @property
    def refugee_count(self) -> int:
        """全局流民数 = 各路本地 refugees 求和（单一事实来源，避免双写漂移）。"""
        return sum(p.get("refugees", 0) for p in self.prefectures.values())

    @refugee_count.setter
    def refugee_count(self, value):
        """兼容旧代码对 self.refugee_count 的赋值：按比例摊回各路（极端兜底，正常不应触发）。"""
        total = sum(p.get("refugees", 0) for p in self.prefectures.values())
        if total <= 0:
            # 无现有流民时把新值均摊到非京畿路
            roads = [k for k, p in self.prefectures.items() if not p.get("is_capital")]
            if roads:
                share = value // len(roads)
                for k in roads:
                    self.prefectures[k]["refugees"] = share
        else:
            ratio = value / total
            for p in self.prefectures.values():
                p["refugees"] = int(p.get("refugees", 0) * ratio)
