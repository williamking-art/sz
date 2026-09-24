# -*- coding: utf-8 -*-
"""宋祚 · 游戏内容数据 —— 科技树 / 建筑蓝图 / 研发预算

从 content/data.py 拆出（零行为变更，只搬代码）。
"""
# cspell:words MEIPASS ZHONGZHI KOUYU MULT JIAOZI COEFF CHANGPING prereq steampump elecbasis elecsteel metaltype hotspot mult

from .data_constants import ASSET_MAINTAIN_RATE  # noqa: F401  (TECH_NODE_MAINTENANCE 换算)

# 科技效果键 → 中文标签（迁移补齐：原 ui/panels_economy.py 模块级常量；
# Tk 废弃后归位权威常量源，供 content/codex_data 图鉴与前端导出共用）
TECH_EFFECT_LABELS = {
    "production": "产能",
    "yield_bonus": "田产加成",
    "mining_income": "矿冶收入",
    "build_cost": "营造成本",
    "canal_efficiency": "漕运效率",
    "army_power": "军力",
    "training": "操练",
    "equipment": "武备",
    "morale": "士气",
    "epidemic_risk": "疫病风险",
    "prestige": "皇威",
    "prestige_gain": "皇威增益",
    "exam_talent": "科举才俊",
    "granary_cap": "扩仓容",
    "workshop_output": "增作坊产出",
    "trade_income": "贸易收入",
    "build_speed": "建造速度",
    "decree_speed": "政令速率",
    "bandwidth_bonus": "圣裁带宽",
    "treasury": "国库",
    "tax": "税入",
    "grain": "粮储",
    "unrest": "民乱",
    "loyalty": "忠诚",
    "satisfaction": "满意度",
    "influence": "势力",
    "power": "实力",
    "population": "人口",
    # 修正（2026-09-18 全审 F601 + G-16）：本行原为 `"trade_income": "市舶收入"`，
    # 与 `:847` 的 `"trade_income": "贸易收入"` 构成**重复键**（后者覆盖前者，
    # 使 `trade_income` 的标签被静默改写）。核对用法后确认本行本意是另一个维度：
    # `("航海","贸易"): {"maritime_income": 0.20}`（`:1931`）用到 `maritime_income`
    # 却一直没有标签 —— 属键名笔误。改正后同时消除重复键与一个缺失标签。
    "maritime_income": "市舶收入",
    "ship_capacity": "舟运运力",
    "naval_power": "水师",
    "firepower": "火力",
    "fortification": "城防",
    "garrison": "驻军",
    "art_gain": "艺术造诣",
    "health_cost": "健康消耗",
    "taoism_gain": "道术造诣",
    "pleasure_gain": "逸乐",
    "clergy_satisfaction": "僧道满意度",
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
    ("E0_firewood", "能源与材料", 0, "柴薪取火",  "柴薪为燃，窑冶之基", [], 0, [], {"silver":0,"months":0,"masters":0}, {"build_speed":0.05}),
    ("E1_coal",     "能源与材料", 0, "煤炭开采",  "山石可燃，可代柴薪", [], 0, [], {"silver":0,"months":0,"masters":0}, {"production":0.08}),
    ("E2_coke",     "能源与材料", 2, "焦炭冶铁",  "煤炼成焦，火猛而无硫", ["E1_coal","M4_furnace"], 72, [("iron",60)], {"silver":300000,"months":18,"masters":6}, {"build_cost":-0.18}),
    ("E3_steel",    "能源与材料", 4, "钢铁精炼",  "百炼成钢，器用坚利", ["E2_coke"], 82, [("west",1)], {"silver":800000,"months":22,"masters":7}, {"army_power":0.20}),
    ("E4_oil",      "能源与材料", 5, "石油提炼",  "井中黑金，炼为灯油沥青", ["E3_steel"], 88, [("west",2)], {"silver":1500000,"months":26,"masters":8}, {"mining_income":0.25}),
    ("E5_alloy",    "能源与材料", 6, "合金钢材",  "锰镍入钢，造轮船轨", ["E4_oil"], 93, [("west",3)], {"silver":2500000,"months":30,"masters":10}, {"army_power":0.25,"production":0.15}),
    ("E6_elecsteel","能源与材料", 6, "电工钢",    "硅钢导磁，电机之骨", ["E5_alloy","M9_power"], 97, [("west",4)], {"silver":3500000,"months":34,"masters":12}, {"production":0.35}),
    # ---- 化学化工 ----
    ("C0_alchemy",  "化学化工", 0, "炼丹术",     "炉鼎丹砂，化玄为妙", [], 0, [], {"silver":0,"months":0,"masters":0}, {"build_speed":0.05}),
    ("C1_gunpowder","化学化工", 0, "火药成熟",   "硝硫木炭，一硝二磺三木炭", ["C0_alchemy"], 20, [("gunpowder",30)], {"silver":30000,"months":5,"masters":2}, {"army_power":0.10}),
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
    ("I6_radio",    "信息通讯", 6, "无线电",     "电波无远不至，千里同声", ["I5_phone"], 95, [("west",4)], {"silver":3000000,"months":30,"masters":11}, {"decree_speed":-6}),
    # ---- 生命医学 ----
    ("H0_herbal",   "生命医学", 0, "本草医方",   "尝百草辨药性，济世活人", [], 0, [], {"silver":0,"months":0,"masters":0}, {"epidemic_risk":-0.10}),
    ("H1_forensic", "生命医学", 1, "法医检勘",   "验尸断狱，洗冤录成", ["H0_herbal"], 50, [], {"silver":40000,"months":6,"masters":2}, {"epidemic_risk":-0.10}),
    ("H2_variola",  "生命医学", 2, "人痘接种",   "痘痂种鼻，以毒攻毒", ["H1_forensic"], 68, [], {"silver":200000,"months":12,"masters":4}, {"epidemic_risk":-0.30}),
    ("H3_anatomy",  "生命医学", 3, "人体解剖",   "剖尸明理，血脉经络", ["H2_variola"], 75, [("west",1)], {"silver":400000,"months":14,"masters":5}, {"epidemic_risk":-0.20}),
    ("H4_bacteria", "生命医学", 4, "细菌学说",   "微虫致病，灭之可防", ["H3_anatomy"], 82, [("west",2)], {"silver":800000,"months":20,"masters":6}, {"epidemic_risk":-0.40}),
    ("H5_anesthesia","生命医学", 5, "外科麻醉",   "麻沸汤药，剖腹不痛", ["H4_bacteria"], 88, [("west",2)], {"silver":1500000,"months":24,"masters":8}, {"epidemic_risk":-0.30,"production":0.05}),
    ("H6_vaccine",  "生命医学", 6, "疫苗学",     "减毒作苗，疫病可御", ["H5_anesthesia"], 93, [("west",3)], {"silver":2200000,"months":28,"masters":9}, {"epidemic_risk":-0.50}),
    # ---- 观念与制度（idea 类：穿越者观念启发，近零成本，靠推行）----
    ("X0_assembly", "观念与制度", 1, "流水线",   "工序拆解，流水作业，百器速成", ["M2_spindle"], 60, [], {"silver":0,"months":6,"masters":0,"idea":True}, {"production":0.15}),
    ("X1_standard", "观念与制度", 2, "标准化",   "模件互换，尺寸划一，营造尤便", ["X0_assembly"], 65, [], {"silver":0,"months":8,"masters":0,"idea":True}, {"build_cost":-0.12}),
    ("X2_bookkeeping","观念与制度", 3, "复式记账", "出入分账，盈亏立见，财政为之一明", ["I3_post"], 70, [], {"silver":0,"months":10,"masters":0,"idea":True}, {"mining_income":0.10}),
    ("X3_regulation","观念与制度", 4, "制式化军械", "枪械划一，零件可换，士卒易用", ["X1_standard","E3_steel"], 80, [("west",1)], {"silver":0,"months":12,"masters":0,"idea":True}, {"army_power":0.15}),
    # ---- 能力域补全（整改④.1）：历法 / 航海 ----
    ("A0_calendar", "观念与制度", 1, "历法修订", "观测星度，校正岁差，颁历授时", ["I0_block"], 50, [("calendar",60)], {"silver":60000,"months":8,"masters":3}, {"calendar":4,"calendar_bonus":5}),
    ("N0_compass",  "机械动力", 1, "航海罗盘", "水浮磁针，辨向通洋", ["M1_noria"], 50, [("hydraulics",40)], {"silver":90000,"months":9,"masters":3}, {"maritime_income":0.15,"trade_income":0.10}),

]


# ------------------------------------------------------------
# 建筑蓝图：科技节点点亮 → 可建 → 落成持续效果
#   key 为关联科技节点 id；cost 沿用固定工程字段 {silver, months}
# ------------------------------------------------------------
BUILDING_BLUEPRINTS = {
    # 蓝图字段（2026-09-19 仿明末模式调整）：
    #   name/kind      —— 中文名 / 细分类型（沿用）
    #   category       —— **上位分类**（财政/军事/民生/科技/交通/内廷），供图鉴与关系图分组
    #   branch         —— 科技树分线（军工/文教/财计/农医/工巧）
    #   requires_region—— **地利前置**（宋祚路型元组，满足其一即可；空 = 何地皆可）
    #   cost           —— {silver: 造价(贯), months: 工期(月)}；工期按明末档压到 **1-6 月**
    #   outputs        —— **产出词条**（结构化声明，与 effect 同源，供面板/AI 阅读）
    #   effect         —— 既有结算维度（保留，结算仍读它）
    #   need_node      —— 前置科技节点
    "M2_spindle": {
        "name": "大纺务", "kind": "纺织", "category": "民生", "branch": "工巧",
        "requires_region": (),
        "cost": {"silver": 80000, "months": 3},
        "outputs": [{"kind": "贸易收入", "amount": 0.15, "unit": "比例"}],
        "effect": {"trade_income": 0.15}, "need_node": "M2_spindle"},
    "M4_furnace": {
        "name": "铁冶务", "kind": "冶金", "category": "民生", "branch": "工巧",
        "requires_region": (),
        "cost": {"silver": 200000, "months": 4},
        "outputs": [{"kind": "营建成本", "amount": -0.10, "unit": "比例"}],
        "effect": {"build_cost": -0.10}, "need_node": "M4_furnace"},
    "C1_gunpowder": {
        "name": "火药局", "kind": "军工", "category": "军事", "branch": "军工",
        "requires_region": (),
        "cost": {"silver": 60000, "months": 2},
        "outputs": [{"kind": "军备库", "amount": 400, "item": "火铳", "unit": "件/月"}],
        "effect": {"army_power": 0.10}, "need_node": "C1_gunpowder"},
    "I0_block": {
        "name": "国子监印书局", "kind": "文化", "category": "科技", "branch": "文教",
        "requires_region": ("京畿要地",),
        "cost": {"silver": 50000, "months": 2},
        "outputs": [{"kind": "科研速度", "amount": 10, "unit": "%"},
                    {"kind": "科举得才", "amount": 3}],
        "effect": {"exam_talent": 3}, "need_node": "I0_block"},
    "I4_telegraph": {
        "name": "电报局", "kind": "通讯", "category": "交通", "branch": "工巧",
        "requires_region": (),
        "cost": {"silver": 600000, "months": 5},
        "outputs": [{"kind": "建造速度", "amount": 15, "unit": "%"}],
        "effect": {"decree_speed": -3}, "need_node": "I4_telegraph"},
    "H2_variola": {
        "name": "痘苗局", "kind": "医学", "category": "民生", "branch": "农医",
        "requires_region": (),
        "cost": {"silver": 80000, "months": 3},
        "outputs": [{"kind": "瘟疫抵抗", "amount": 30, "unit": "%"}],
        "effect": {"epidemic_risk": -0.30}, "need_node": "H2_variola"},
    "C4_fertilizer": {
        "name": "肥料局", "kind": "农业", "category": "民生", "branch": "农医",
        "requires_region": (),
        "cost": {"silver": 150000, "months": 3},
        "outputs": [{"kind": "粮食产量", "amount": 15, "unit": "%"}],
        "effect": {"yield_bonus": 0.15}, "need_node": "C4_fertilizer"},
    "M5_steampump": {
        "name": "蒸汽矿场", "kind": "矿业", "category": "民生", "branch": "工巧",
        "requires_region": (),
        "cost": {"silver": 300000, "months": 4},
        "outputs": [{"kind": "矿产收入", "amount": 0.10, "unit": "比例"}],
        "effect": {"mining_income": 0.10}, "need_node": "M5_steampump"},
    "M6_loco": {
        "name": "机器局·铁路", "kind": "交通", "category": "交通", "branch": "工巧",
        "requires_region": (),
        "cost": {"silver": 800000, "months": 6},
        "outputs": [{"kind": "漕运效率", "amount": 0.30, "unit": "比例"}],
        "effect": {"canal_efficiency": 0.30}, "need_node": "M6_loco"},
    "M9_power": {
        "name": "发电厂", "kind": "能源", "category": "科技", "branch": "工巧",
        "requires_region": (),
        "cost": {"silver": 2000000, "months": 6},
        "outputs": [{"kind": "建筑产出", "amount": 15, "unit": "%"}],
        "effect": {"production": 0.15}, "need_node": "M9_power"},
}

# 蓝图分类/分线的合法枚举（供图鉴与校验用；仿明末模式）
BLUEPRINT_CATEGORIES = ("财政", "军事", "民生", "科技", "交通", "内廷")
BLUEPRINT_BRANCHES = ("军工", "文教", "财计", "农医", "工巧")
#: 蓝图工期档（月）：仿明末——小型 1-2、中型 3-4、大型/超前 5-6
BLUEPRINT_MONTHS_MIN, BLUEPRINT_MONTHS_MAX = 1, 6


def blueprint_region_ok(route_type, blueprint_key) -> bool:
    """蓝图**地利前置**校验：该路的路型是否满足该蓝图要求（空要求 → 处处可建）。

    `route_type` 取 `prefectures[路]["type"]`（京畿要地/沿海/缘边…），
    `blueprint_key` 取 `BUILDING_BLUEPRINTS` 的键。仿明末「requires_region_tags」。
    """
    bp = BUILDING_BLUEPRINTS.get(str(blueprint_key))
    if not isinstance(bp, dict):
        # 非科技蓝图（如 BUILDING_STD 的政府建筑）：未声明地利前置 → 处处可建
        return True
    need = bp.get("requires_region") or ()
    if not need:
        return True
    t = str(route_type or "")
    return any(str(n) in t for n in need)



# ------------------------------------------------------------
# 科技「能力域」索引（整改④.1）：TECH_INFO.level 只作综合读数；
# 真正可用能力拆入 火药/冶金/水利/历法/航海/财政/医学农学 七域，每域至少一个可研节点。
# ------------------------------------------------------------
TECH_DOMAIN_NODES: dict[str, tuple[str, ...]] = {
    "火药": ("C1_gunpowder", "C1b_huochong", "C1c_huoqiang", "C1d_suifa"),
    "冶金": ("M3_bellows", "M4_furnace", "E2_coke", "E3_steel"),
    "水利": ("M1_noria", "M5_steampump"),
    "历法": ("A0_calendar",),
    "航海": ("N0_compass",),
    "财政": ("X2_bookkeeping",),
    "医学农学": ("H0_herbal", "H1_forensic", "H2_variola", "C4_fertilizer"),
}

# 节点「部署 + 维护」声明（整改④.3）：解锁 ≠ 全国生效，须建筑/作坊/军队部署，
# 以 adoption 覆盖率产生效果。部署建筑 = 蓝图建筑名（缺失视为无独立部署路径，coverage 取默认值）；
# 维护费率 = 该建筑 BUILDING_STD[*]["maintain"]（并入 _settle_upkeep 的资产维持口径，不另设账本）。
TECH_NODE_DEPLOY: dict[str, str] = {
    nid: bp["name"] for nid, bp in BUILDING_BLUEPRINTS.items()
}
# 维护费率：部署建筑按统一月维护率（0.5%/月，与 ASSET_MAINTAIN_RATE 同源）。
# >0 表示该节点须持续维护，否则 adoption 覆盖率按月折损（维护 → 折旧，§三.3）。
TECH_NODE_MAINTENANCE: dict[str, float] = {
    nid: float(ASSET_MAINTAIN_RATE) for nid in BUILDING_BLUEPRINTS
}

# ---- 科技研发预算 + adoption + 西学来源（整改④，2026-09-19）----
TECH_ADOPTION_DEFAULT = 1.0        # 无部署建筑的节点：技艺已内化于现有作坊/衙署
TECH_ADOPTION_MAX = 1.0
TECH_ADOPTION_PER_LEVEL = 0.25     # 每级部署建筑提升 25% 覆盖率（4 级 → 全国生效）
TECH_ADOPTION_DECAY = 0.05         # 维持费欠缴时月覆盖率折损（维护 → 折旧）
TECH_RESEARCH_BUDGET_RATIO = 0.25  # 立项银 × 比例 → 月度研发经费（国库 → 学者/工匠 POP）
TECH_RESEARCH_PAY_TO = {"士绅": 0.5, "工匠": 0.5}
TECH_RESEARCH_LITERACY_W = 0.30    # 识字率（0-100）对研发速率的最大加成
TECH_RESEARCH_SCHOOL_CAP = 0.30    # 学校/书院（tech_build_bonus）对研发速率的最大加成
TECH_RESEARCH_MATERIAL_FLOOR = 0.50  # 材料不足时研发速率下限（降效不归零）
TECH_RESEARCH_RATE_CAP = 2.0       # 研发速率总加成封顶
TECH_WEST_SOURCES = {"trade": 0.004, "mission": 0.02, "books": 0.015,
                     "artisan": 0.02, "war": 0.01}   # west 只来自具体来源（§四.4）
TECH_WEST_MAX = 5.0
TECH_WEST_ACCEL_PER_POINT = 0.04   # west → 研发加速（1 + west×0.04）
TECH_WEST_ACCEL_CAP = 1.25         # west 加速封顶（≤1.25×，非万能加速器）


# ------------------------------------------------------------
# 科技树查询工具（供命令 / 结算 / UI 共用）
# ------------------------------------------------------------
_TECH_NODE_MAP: dict[str, TechNode] = {t[0]: t for t in TECH_NODES}

# 能力域索引自检（整改④.1）：域内节点必须真实存在——防声明与节点表漂移。
_missing_domain_nodes = [nid for _ids in TECH_DOMAIN_NODES.values()
                         for nid in _ids if nid not in _TECH_NODE_MAP]
if _missing_domain_nodes:
    raise ValueError(f"TECH_DOMAIN_NODES 指向不存在节点：{_missing_domain_nodes}")


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

