# -*- coding: utf-8 -*-
"""宋祚 · 游戏内容数据 —— 诏令系统参数 / 固定程序模板

从 content/data.py 拆出（零行为变更，只搬代码）。
"""
# cspell:words MEIPASS ZHONGZHI KOUYU MULT JIAOZI COEFF CHANGPING prereq steampump elecbasis elecsteel metaltype hotspot mult

# ============================================================
# 诏令系统
# ============================================================
# 【零引用常量状态说明 — 2026-09-19 代码质量全检】
# 本文件有一批"配置已定义、机制未接线"的常量（全项目零引用，前端也不读）。**不删除**：
# 它们是设计意图的落点，删除会丢失后续接线锚点。已接线者见下方 `DIRECT_DECREE_MAX`。
# 未接线清单（接线位置见《宋祚代码质量全检》§2.4）：
#   诏令类：DECREE_MAX_BANDWIDTH / SECRET_DECREE_MIN / SECRET_DECREE_MAX / WOLF_THRESHOLD(已停用)
#   财政类：BANK_DEPOSIT_RATE / TAX_LAND_RATIO / TAX_COMMERCE_RATIO / FINANCE_DESC
#   产业类：CASH_CROP_LAND / INDUSTRY_OLD_DECAY / FIREARM_TIERS
#   军制类：MILITARY_GRAIN_MONTHLY / INLAND_TRAIN_BONUS / INLAND_MORALE_BONUS
#   考课类：EXAM_TAKER_MULT(注释自标"暂不做") / POP_TYPES(与 GRAIN_CONSUME_PER_CAPITA 重复)
#   内容类：ARMY_EXPAND_ACTS / DIPLOMACY_ACTS / EXAM_ACTS / FINANCE_ACTS / FIXED_PROCEDURES /
#           BRANCH_ANCHORS / EXTERNAL_ALWAYS_SHOW / ORG_AFFILIATION
# 判定纪律：实现里有**同值硬编码** → 回收为引用（本轮已回收 DIRECT_DECREE_MAX / ROUTE_MULT_DEFAULT）；
# 无对应实现 → 保留本注释、**不删**，待机制接线或确认废弃后转 `deprecated`。
DECREE_BASE_BANDWIDTH = 6      # 圣旨基础带宽
DECREE_MAX_BANDWIDTH = 10      # 圣旨上限（未接线）
SECRET_DECREE_MIN = 2          # 密旨最低
SECRET_DECREE_MAX = 3          # 密旨最高
DIRECT_DECREE_MAX = 2          # 御笔直发上限
WOLF_THRESHOLD = 3             # 已停用：狼来了机制取消（审查 2026-09），保留常量仅存档/引用兼容

# 诏意机构归属（拟旨润色时由 AI 建议，会签与执行共用）
# 归属类别：内廷（直属皇帝，无条件执行）/ 政府（三省六部，走会签）/ 地方（州县，可能抗旨）
ORG_AFFILIATION = {
    "内廷": ["枢密院(内廷)", "内侍省", "御药院", "皇城司", "殿前司"],
    "政府": ["中书省", "门下省", "尚书省", "吏部", "户部", "礼部", "兵部", "刑部", "工部"],
    "地方": ["京畿路", "京西路", "京东东路", "京东西路", "河北路", "河东路", "陕西路", "两浙路",
            "江南东路", "江南西路", "淮南东路", "淮南西路", "荆湖北路", "荆湖南路", "福建路",
            "成都府路", "利州路", "夔州路", "广南东路", "广南西路"],
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
# 固定程序四类的参数模板（AI 解析拟旨时按 category 归一到这些参数）
FIXED_PROCEDURES = {
    "fixed_tech":         {"label": "科技营缮", "fields": ["project", "invest", "months"]},
    "fixed_finance":      {"label": "钱粮调度", "fields": ["source", "target", "amount"]},
    "fixed_army":         {"label": "军队调动", "fields": ["army", "to_line", "scale"]},
    "fixed_construction": {"label": "工程建设", "fields": ["site", "kind", "invest", "months"]},
}

