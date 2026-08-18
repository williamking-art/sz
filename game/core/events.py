# -*- coding: utf-8 -*-
"""宋祚 · 事件系统 —— 史实事件脚本"""
import random


# ============================================================
# 预设史实事件
# ============================================================
HISTORICAL_EVENTS = [
    # (年份范围, 触发概率per月, 事件标题, 效果函数或效果dict, 描述)
    {
        "id": "huashigang",
        "year_range": (1102, 1120),
        "prob": 0.04,
        "title": "花石纲引发民怨",
        "category": "花石纲",
        "effects": {"prestige": -2, "population_satisfaction": -3},
        "desc": "朱勔借花石纲之名大肆搜刮，东南民怨沸腾",
        "choices": [
            {"text": "默许", "effects": {"prestige": -1, "population_satisfaction": -2, "treasury": 200000}},
            {"text": "斥责朱勔", "effects": {"prestige": 2, "population_satisfaction": 3, "treasury": -100000}},
            {"text": "严惩朱勔", "effects": {"prestige": 5, "population_satisfaction": 5, "treasury": -300000}},
        ],
    },
    {
        "id": "fangla_uprising",
        "year_range": (1118, 1121),
        "prob": 0.05,
        "title": "方腊起义",
        "category": "方腊起义",
        "effects": {"prestige": -10, "population_satisfaction": -5, "treasury": -1000000},
        "desc": "方腊在睦州起义，聚众十万，东南震动",
        "choices": [
            {"text": "派童贯率西军平叛", "effects": {"prestige": 3, "treasury": -2000000, "external_jin": -5}},
            {"text": "招安安抚", "effects": {"prestige": -2, "treasury": -500000, "population_satisfaction": 1}},
            {"text": "调禁军亲征", "effects": {"prestige": 8, "treasury": -3000000, "army_strength": -10}},
        ],
    },
    {
        "id": "songjiang",
        "year_range": (1119, 1121),
        "prob": 0.03,
        "title": "宋江三十六人纵横河朔",
        "category": "宋江起义",
        "effects": {"prestige": -3, "population_satisfaction": -2},
        "desc": "宋江率三十六人转战河朔、京东，州县骚然",
        "choices": [
            {"text": "招安", "effects": {"prestige": 2, "treasury": -300000}},
            {"text": "派张叔夜剿灭", "effects": {"prestige": 4, "treasury": -500000}},
            {"text": "不理", "effects": {"prestige": -3, "population_satisfaction": -3}},
        ],
    },
    {
        "id": "sea_alliance",
        "year_range": (1118, 1120),
        "prob": 0.06,
        "title": "女真遣使——海上之盟",
        "category": "海上之盟",
        "effects": {},
        "desc": "女真完颜阿骨打遣使渡海而来，邀大宋共击辽国",
        "choices": [
            {"text": "允盟，联金灭辽", "effects": {"prestige": 5, "external_jin": 20, "external_liao": -30, "external_xixia": -10}},
            {"text": "拒绝，固守盟约", "effects": {"prestige": -1, "external_jin": -10, "external_liao": 5}},
            {"text": "待价而沽，虚与委蛇", "effects": {"prestige": 2, "external_jin": 5}},
        ],
    },
    {
        "id": "jin_destroys_liao",
        "year_range": (1122, 1125),
        "prob": 0.04,
        "title": "金灭辽——唇亡齿寒",
        "category": "金灭辽",
        "effects": {"prestige": -5},
        "desc": "女真铁骑势如破竹，辽祚将尽",
        "choices": [
            {"text": "加强边防，备战", "effects": {"prestige": 3, "treasury": -2000000, "defense_bonus": 10}},
            {"text": "继续观望", "effects": {"prestige": -2}},
            {"text": "遣使示好金国", "effects": {"prestige": -3, "treasury": -500000, "external_jin": 5}},
        ],
    },
    {
        "id": "jin_invasion",
        "year_range": (1125, 1127),
        "prob": 0.06,
        "title": "金军挥师南下！",
        "category": "金军南侵",
        "effects": {"prestige": -15},
        "desc": "金将斡离不、粘罕分两路南侵，铁骑逼近黄河",
        "choices": [
            {"text": "死守东京", "effects": {"prestige": 10, "defense_bonus": 15, "treasury": -3000000}},
            {"text": "迁都南幸", "effects": {"prestige": -15, "population_satisfaction": -10, "defense_bonus": -5}},
            {"text": "遣使乞和", "effects": {"prestige": -20, "treasury": -10000000}},
        ],
    },
    {
        "id": "huanghe_flood",
        "year_range": (1101, 1125),
        "prob": 0.02,
        "title": "黄河决口",
        "category": "黄河决口",
        "effects": {"treasury": -500000, "population_satisfaction": -5},
        "desc": "黄河泛滥，河北数州被淹，数十万灾民流离",
        "choices": [
            {"text": "全力赈灾", "effects": {"prestige": 5, "treasury": -1000000, "population_satisfaction": 3}},
            {"text": "象征性救济", "effects": {"prestige": -1, "treasury": -200000, "population_satisfaction": -2}},
        ],
    },
    {
        "id": "xiangrui",
        "year_range": (1101, 1125),
        "prob": 0.03,
        "title": "祥瑞之兆",
        "category": "祥瑞",
        "effects": {},
        "desc": "天降祥瑞，地方奏报鹤降、芝生、醴泉涌出",
        "choices": [
            {"text": "大加宣扬，祀天告庙", "effects": {"prestige": 3, "treasury": -200000}},
            {"text": "淡然处之", "effects": {"prestige": 0}},
            {"text": "斥为妄言", "effects": {"prestige": 1, "factions_prestige": {"清流言官": 5}}},
        ],
    },
    {
        "id": "party_strife",
        "year_range": (1101, 1125),
        "prob": 0.04,
        "title": "党争再起",
        "category": "党争",
        "effects": {},
        "desc": "朝中新旧党争又起，互相攻讦，朝政瘫痪",
        "choices": [
            {"text": "压制新党", "effects": {"faction_change": {"新党": -10, "旧党": 10}}},
            {"text": "压制旧党", "effects": {"faction_change": {"新党": 10, "旧党": -10}}},
            {"text": "调停", "effects": {"prestige": 2, "faction_change": {"新党": -3, "旧党": -3}}},
            {"text": "置之不理", "effects": {"prestige": -2}},
        ],
    },
]

# ============================================================
# 随机事件库
# ============================================================
RANDOM_EVENTS = [
    {
        "title": "御史进谏",
        "prob": 0.05,
        "desc": "某御史直言进谏，言辞激烈",
        "choices": [
            {"text": "嘉纳", "effects": {"prestige": 2, "faction_change": {"清流言官": 5}}},
            {"text": "贬斥", "effects": {"prestige": -1, "faction_change": {"清流言官": -10}}},
        ],
    },
    {
        "title": "商人献宝",
        "prob": 0.04,
        "desc": "有富商献上奇珍异宝，但有人告其偷税",
        "choices": [
            {"text": "收宝惩商", "effects": {"prestige": 1, "treasury": 100000}},
            {"text": "拒收并查税", "effects": {"prestige": 3, "treasury": 300000}},
        ],
    },
    {
        "title": "翰林画院新作",
        "prob": 0.04,
        "desc": "翰林图画院呈上新作，画艺精湛",
        "choices": [
            {"text": "大加赏赐", "effects": {"art_mastery": 1, "treasury": -50000}},
            {"text": "勉励即可", "effects": {}},
        ],
    },
    {
        "title": "边境滋事",
        "prob": 0.03,
        "desc": "西夏边境又有小规模骚扰",
        "choices": [
            {"text": "增兵防御", "effects": {"prestige": 2, "treasury": -300000}},
            {"text": "遣使交涉", "effects": {"treasury": -50000}},
        ],
    },
    {
        "title": "宫内太监贪墨案",
        "prob": 0.03,
        "desc": "查出宫中太监贪墨御用钱粮",
        "choices": [
            {"text": "严惩不贷", "effects": {"prestige": 3, "faction_change": {"宦官集团": -5}}},
            {"text": "从轻发落", "effects": {"faction_change": {"宦官集团": 5, "清流言官": -5}}},
        ],
    },
    {
        "title": "黄河秋汛告急",
        "prob": 0.03,
        "desc": "都水监奏：黄河秋汛将至，河北堤防多有隐患",
        "choices": [
            {"text": "拨帑修堤", "effects": {"prestige": 2, "treasury": -500000, "population_satisfaction": 1}},
            {"text": "暂缓", "effects": {"prestige": -1}},
        ],
    },
    {
        "title": "太学三舍法争议",
        "prob": 0.04,
        "desc": "太学推行三舍法，新旧两党争执不下",
        "choices": [
            {"text": "力主推行", "effects": {"prestige": 1, "faction_change": {"新党": 5, "旧党": -5}, "tech": 1}},
            {"text": "罢废之", "effects": {"faction_change": {"旧党": 5, "新党": -5}}},
            {"text": "折中调和", "effects": {"faction_change": {"新党": 1, "旧党": 1}}},
        ],
    },
    {
        "title": "市舶贡使献方物",
        "prob": 0.03,
        "desc": "市舶司奏：海外番商贡犀象、香药，请开市舶以广财源",
        "choices": [
            {"text": "广开市舶", "effects": {"prestige": 2, "treasury": 200000, "tech": 1}},
            {"text": "仅受贡物", "effects": {"prestige": 1, "treasury": 100000}},
        ],
    },
    {
        "title": "常平仓奏请籴粜",
        "prob": 0.04,
        "desc": "户部奏请于丰歉之地籴粜常平，以平抑粮价",
        "choices": [
            {"text": "准奏", "effects": {"population_satisfaction": 2, "treasury": -200000}},
            {"text": "不准", "effects": {"population_satisfaction": -1}},
        ],
    },
    {
        "title": "西军乏饷",
        "prob": 0.03,
        "desc": "陕西沿边奏：西军粮饷久欠，军心浮动",
        "choices": [
            {"text": "拨帑补饷", "effects": {"treasury": -600000, "army_strength": 2, "prestige": 1}},
            {"text": "暂缓", "effects": {"army_strength": -3, "prestige": -2}},
        ],
    },
]


def get_historical_event(year: int, month: int) -> dict | None:
    """根据年份检查是否有史实事件触发"""
    for ev in HISTORICAL_EVENTS:
        lo, hi = ev["year_range"]
        if lo <= year <= hi:
            if random.random() < ev["prob"]:
                return ev
    return None


def get_random_event() -> dict | None:
    """随机事件触发"""
    for ev in RANDOM_EVENTS:
        if random.random() < ev.get("prob", 0.03):
            return ev
    return None


def apply_event_choice(state, event: dict, choice_idx: int) -> list:
    """执行事件选择，返回效果日志"""
    choices = event.get("choices", [])
    if choice_idx >= len(choices):
        return ["选择无效"]

    choice = choices[choice_idx]
    effects = choice.get("effects", {})
    log = []

    log.append(f"选择：{choice['text']}")

    # 皇威
    if "prestige" in effects:
        state.change_prestige(effects["prestige"], event.get("title", ""))
        log.append(f"皇威 {'+' if effects['prestige']>=0 else ''}{effects['prestige']}")

    # 国库
    if "treasury" in effects:
        state.change_treasury(effects["treasury"])
        log.append(f"国帑 {'+' if effects['treasury']>=0 else ''}{effects['treasury']:.0f}贯")

    # 人口满意度
    if "population_satisfaction" in effects:
        state.population_satisfaction = max(0, min(100,
            state.population_satisfaction + effects["population_satisfaction"]))
        log.append(f"民情 {'+' if effects['population_satisfaction']>=0 else ''}{effects['population_satisfaction']}")

    # 外部势力
    for key in ["external_jin", "external_liao", "external_xixia"]:
        if key in effects:
            ext_key = {"external_jin": "金", "external_liao": "辽", "external_xixia": "西夏"}[key]
            state.external[ext_key]["attitude"] = max(0, min(100,
                state.external[ext_key].get("attitude", 50) + effects[key]))

    # 派系影响
    if "faction_change" in effects:
        for fname, delta in effects["faction_change"].items():
            if fname in state.factions:
                state.factions[fname]["satisfaction"] = max(0, min(100,
                    state.factions[fname]["satisfaction"] + delta))
                log.append(f"{fname}满意度 {'+' if delta>=0 else ''}{delta}")

    # 边防
    if "defense_bonus" in effects:
        bonus = effects["defense_bonus"]
        for line in state.defense_lines.values():
            line["fortification"] = max(0, min(100,
                line["fortification"] + bonus))

    # 军队强度（方腊起义「调禁军亲征」等）—— 对各军综合强度施加统一增减
    # strength 字段已废弃，改以训练/士气二者表达综合强度
    if "army_strength" in effects:
        delta = int(effects["army_strength"])
        for u in state.army_units:
            u.training = max(0, min(100, u.training + delta))
            u.morale   = max(0, min(100, u.morale + delta))
        log.append(f"军力 {'+' if delta>=0 else ''}{delta}")

    # 派系皇威（祥瑞「斥为妄言」等）—— {派系: 增减} 作用于派系满意度
    if "factions_prestige" in effects and isinstance(effects["factions_prestige"], dict):
        for fname, d in effects["factions_prestige"].items():
            if fname in state.factions:
                state.factions[fname]["satisfaction"] = max(0, min(100,
                    state.factions[fname]["satisfaction"] + d))
                log.append(f"{fname}皇威 {'+' if d>=0 else ''}{d}")

    # 艺术造诣
    if "art_mastery" in effects:
        state.art_mastery = max(0, min(100,
            state.art_mastery + effects["art_mastery"]))

    # 战略决策点·朱批（由奏报抉择触发，落/撤改写位）
    # 延迟导入避免 commands<->events 循环依赖
    if "_confirm_break" in effects:
        from core.commands import confirm_timeline_break
        log.append(confirm_timeline_break(state, effects["_confirm_break"]))
    if "_dismiss_break" in effects:
        from core.commands import dismiss_pending_break
        log.append(dismiss_pending_break(state, effects["_dismiss_break"]))

    return log


# ============================================================
# 战略改写分支事件（玩家改革改写历史后触发）
# 仅当 state.timeline 中存在对应改写位时，经 get_strategic_branch 返回。
# ============================================================
STRATEGIC_BRANCHES = [
    {
        "id": "jin_crushed_peace",
        "break": "jin_crushed",
        "year_range": (1115, 1130),
        "prob": 0.08,
        "title": "北疆升平·女真已灭",
        "category": "战略改写",
        "effects": {"prestige": 6, "population_satisfaction": 3},
        "desc": "女真部族早经剿灭于萌芽，松花江畔不复有狼烟。北疆无事，流民渐归，市马之利复通。",
        "choices": [
            {"text": "置东北都护府镇抚", "effects": {"prestige": 4, "population_satisfaction": 2, "treasury": -400000}},
            {"text": "徙民实边，屯田自给", "effects": {"prestige": 2, "population_satisfaction": 3}},
        ],
    },
    {
        "id": "liao_ally_victory",
        "break": "liao_ally",
        "year_range": (1118, 1125),
        "prob": 0.10,
        "title": "宋辽夹击·女真大败",
        "category": "战略改写",
        "effects": {"prestige": 8, "external_jin": -15, "external_liao": 5},
        "desc": "海上之盟既成，宋辽两军会于混同江，女真惨败，阿骨打请盟修好。北顾无忧，朝野称庆。",
        "choices": [
            {"text": "乘胜约辽共分女真故地", "effects": {"prestige": 5, "external_liao": 3, "external_jin": -10}},
            {"text": "敛兵守盟，休养国力", "effects": {"prestige": 3, "treasury": 300000, "population_satisfaction": 2}},
        ],
    },
    {
        "id": "no_jingkang_tribute",
        "break": "no_jingkang",
        "year_range": (1120, 1130),
        "prob": 0.09,
        "title": "金使来朝·称臣纳贡",
        "category": "战略改写",
        "effects": {"prestige": 10, "external_jin": -10, "treasury": 500000},
        "desc": "国势鼎盛，甲兵方强。金主惮宋之威，遣使奉表称臣，岁贡良马貂皮，请互市通好。靖康之祸，至此消弭。",
        "choices": [
            {"text": "受贡而羁縻之", "effects": {"prestige": 4, "treasury": 200000, "external_jin": -5}},
            {"text": "拒贡，陈兵备边以示威", "effects": {"prestige": 6, "external_jin": -8, "army_strength": 5}},
        ],
    },
]


def get_strategic_branch(state) -> dict | None:
    """若玩家已激活某历史改写位，按年份窗口返回对应的战略分支事件。

    返回 None 表示当前无改写位事件（史实事件照常走 get_historical_event）。
    优先级：改写位事件在 _settle_events 中先于普通史实事件检测。
    """
    tl = getattr(state, "timeline", {})
    if not tl:
        return None
    for ev in STRATEGIC_BRANCHES:
        if ev["break"] in tl:
            lo, hi = ev["year_range"]
            if lo <= state.year <= hi and random.random() < ev["prob"]:
                return ev
    return None


# ============================================================
# 战略决策点·待确认改写位（枢密院/军机密奏，朱批后落 timeline）
# 仅当 state.pending_breaks 中存在对应候选时，经 get_pending_break_event 返回。
# 该事件带 choices（准予改写 / 从长计议），是「改写历史」的主动决策入口。
# ============================================================
PENDING_BREAK_EVENTS = {
    "jin_crushed": {
        "id": "jin_crushed_petition",
        "title": "枢密院密奏·军机",
        "category": "战略决策",
        "desc": "臣等窃观女真一部，去岁以来连遭挫败，部族离散，势已将熄。今其主阿骨打虽称帝，然羽翼未丰，兵力凋零。若乘此天亡之时，遣精兵出辽东，可一举剿其萌芽，永绝北顾之忧。然用兵劳民，且启边衅，亦不可不虑。伏候圣裁。",
        "choices": [
            {"text": "准予：乘势出兵，灭其于萌芽", "effects": {"_confirm_break": "jin_crushed"}},
            {"text": "从长计议：按兵不动，静观其变", "effects": {"_dismiss_break": "jin_crushed"}},
        ],
    },
    "liao_ally": {
        "id": "liao_ally_petition",
        "title": "枢密院密奏·军机",
        "category": "战略决策",
        "desc": "辽主屡遣使臣示好，献方物、请盟约，其意甚诚。今女真鸱张于东北，宋辽若缔盟夹击，可消腹背之患，北疆永宁。然海上之盟，向为识者所忧，辽之虚实未可逆料，结盟或养虎遗患。可否许盟，伏候圣裁。",
        "choices": [
            {"text": "准予：许盟夹击，共御女真", "effects": {"_confirm_break": "liao_ally"}},
            {"text": "从长计议：婉拒来使，自固边防", "effects": {"_dismiss_break": "liao_ally"}},
        ],
    },
    "no_jingkang": {
        "id": "no_jingkang_petition",
        "title": "枢密院密奏·军机",
        "category": "战略决策",
        "desc": "臣等伏查：今国势鼎盛，府库充盈，甲兵之强冠于往岁；陛下威加海内，万姓归心。金人虽号小夷，然其主侵逼之念，已为天兵之威所慑，不敢萌南下之志。此社稷永固之机也。若加意练兵、怀远以德，靖康之祸可消弭于未然。是否乘时经略，永固根本，伏候圣裁。",
        "choices": [
            {"text": "准予：经略固本，永靖边患", "effects": {"_confirm_break": "no_jingkang"}},
            {"text": "从长计议：居安思危，慎保太平", "effects": {"_dismiss_break": "no_jingkang"}},
        ],
    },
}


def get_pending_break_event(state) -> dict | None:
    """返回当前待陛下朱批的战略决策点奏章（优先级最高的事件）。

    若有候选改写位（state.pending_breaks 非空），返回对应密奏事件。
    返回 None 表示当前无待确认改写位（走战略分支→史实→随机事件）。
    """
    pb = getattr(state, "pending_breaks", {})
    if not pb:
        return None
    # 取最早进入候选的改写位（按 year 升序，稳定可追踪）
    first_id = min(pb.keys(), key=lambda k: pb[k].get("year", 0))
    ev = PENDING_BREAK_EVENTS.get(first_id)
    if not ev:
        return None
    # 附带候选元数据，便于 UI 角标与日志追踪
    return dict(ev, _break_id=first_id)
