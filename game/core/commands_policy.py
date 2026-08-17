# -*- coding: utf-8 -*-
"""宋祚 · 各项施政 policy 指令族（拆分自 core/commands.py）"""
import random
from typing import Any
from core.game_state import GameState
from core.settlement import run_monthly_settlement
from core.errors import AIRuntimeError
from content.data import (
    desensitize_satisfaction, desensitize_shortage,
    desensitize_talent, desensitize_tech, desensitize_trust,
)


def _mainforce(state, station: str, tier: str, default_branch: str):
    """取某路某军籍的主将部（troops 最大者）；无军籍实体则新建一支并入册。

    军事重构后兵额唯一真账在 state.army_units（list[ArmyUnit]），诏令增兵一律
    落到实体 troops 上，不再写 prefectures[路]["garrisons"] 或 state.armies。
    """
    from ui.panels_military import ArmyUnit, UNIT_TIER, EQUIP_STD, _defense_line_for
    units = getattr(state, "army_units", None)
    if units is None:
        units = state.army_units = []
    same = [u for u in units if u.station == station and u.tier == tier]
    if same:
        return max(same, key=lambda u: u.troops)
    base = UNIT_TIER[tier]
    std = EQUIP_STD.get(default_branch, {})
    uid = f"cmd{tier}{default_branch}{station}{state.year}{state.month}{len(units)}"
    unit = ArmyUnit(
        unit_id=uid,
        name=f"{station}诏增{tier}",
        tier=tier,
        branch=default_branch,
        troops=0,
        morale=base["morale_base"],
        training=base["train_base"],
        station=station,
        defense_line=_defense_line_for(station, tier),
        equip={k: 0 for k in std},
    )
    units.append(unit)
    return unit


def _reinforce(state, station: str, tier: str, add: int, default_branch: str):
    """向某路某军籍主将部增兵额（人），并按新兵额从中央武库补装备缺口。"""
    from ui.panels_military import distribute_arsenal
    unit = _mainforce(state, station, tier, default_branch)
    unit.troops += int(add)
    distribute_arsenal(state, unit, None)
    return unit


def _units_of_tier(state, tier: str, station: str = ""):
    """按军籍（可选限定驻地）取实体列表。"""
    units = getattr(state, "army_units", None) or []
    return [u for u in units if u.tier == tier and (not station or u.station == station)]


def start_project(state: GameState, pid: str, project: dict) -> str:
    """发起一项工程（如新建仓储/加固边备/兴酒坊）。

    project 结构示例：
      {"name": "新建仓储", "type": "granary", "progress": 0, "speed": 12,
       "cost_material": {"timber": 30, "stone": 20}, "cost_coin": 200000,
       "output": {"granary_cap_add": 500}}
    """
    if not isinstance(state.projects, dict):
        state.projects = {}
    project.setdefault("progress", 0)
    project.setdefault("done", False)
    state.projects[pid] = project
    return f"已兴工「{project.get('name', pid)}」，物料齐备则次月推进。"


def local_policy(state: GameState, pref_name: str, act: str, ai_client=None) -> str:
    """对一州一路施行地方政令。返回叙事文本。"""
    if pref_name not in state.prefectures:
        return "并无此路。"
    p = state.prefectures[pref_name]
    if act == "劝农":
        p["land"] = int(p["land"] * 1.02)
        p["grain"] = int(p["grain"] * 1.03)
        p["mood"] = max(0, min(100, p["mood"] + 3))
        rule = f"{pref_name}劝课农桑，田畴增辟，仓廪渐实。"
    elif act == "赈灾":
        p["mood"] = max(0, min(100, p["mood"] + 5))
        p["govern"] = max(0, min(100, p["govern"] + 2))
        state.treasury -= 150000
        rule = f"{pref_name}发仓赈灾，饥民得活，舆情稍安。"
    elif act == "平盗":
        p["govern"] = max(0, min(100, p["govern"] + 4))
        p["mood"] = max(0, min(100, p["mood"] + 2))
        rule = f"{pref_name}剿平盗匪，道路以通，商旅称便。"
    elif act == "减税":
        p["mood"] = max(0, min(100, p["mood"] + 4))
        state.treasury -= 100000
        rule = f"{pref_name}蠲免租税，百姓感悦。"
    else:
        rule = f"{pref_name}施行「{act}」。"
    narr = ""
    if ai_client and getattr(ai_client, "available", False):
        try:
            mood_desc = desensitize_satisfaction(p["mood"])
            obj = ai_client.local_policy(pref_name, p["households"], p["land"], mood_desc, act, state.get_state_summary())
            narr = obj.get("narrative", "") if isinstance(obj, dict) else ""
        except Exception as e:
            raise AIRuntimeError(f"地方施政时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return (narr + "\n" + rule) if narr else rule


# ============================================================
# 扩展维度命令：金融 / 科举 / 科技 / 扩军 / 外交 / 改革
# （AI 叙事 + 规则结算；数值由程序按成法折算）
# ============================================================


def diplomacy_policy(state: GameState, act: str, ai_client=None) -> str:
    """金/辽/夏外交之政。返回叙事文本。"""
    summary = _state_summary_min(state)
    if act == "联金抗辽(海上之盟)":
        state.alliance_jin_liao = True
        state.external["金"]["attitude"] = max(0, min(100, state.external["金"]["attitude"] + 15))
        state.external["辽"]["attitude"] = max(0, min(100, state.external["辽"]["attitude"] - 15))
        state.external["金"]["invasion_will"] = state.external["金"].get("invasion_will", 0) + 5
        rule = "遣使渡海，结金抗辽（海上之盟）。金人乐从，而辽疑我贰、且养虎为患。"
    elif act == "通好辽国":
        state.external["辽"]["attitude"] = max(0, min(100, state.external["辽"]["attitude"] + 12))
        rule = "遣使通好辽国，边境互市稍通，北顾暂安。"
    elif act == "绥靖西夏":
        state.external["西夏"]["attitude"] = max(0, min(100, state.external["西夏"]["attitude"] + 12))
        state.treasury -= 200000
        rule = "岁赐西夏、许其互市，西陲兵革暂息，然耗赀不少。"
    elif act == "备边严守":
        # 增兵边镇：兵额直入河北/河东两路军籍实体（真账），派生自动体现于北线防区
        for route in ("河北路", "河东"):
            _reinforce(state, route, "禁军", 30000, "重步兵")
            _reinforce(state, route, "厢军", 20000, "轻步兵")
        state._derive_defense_lines()
        rule = "增兵边镇、严守要冲，辽夏不敢轻动（禁军各增三万、厢军各增二万，入军籍真账）。"
    elif act == "遣使修好":
        for k in ("金", "辽", "西夏"):
            state.external[k]["attitude"] = max(0, min(100, state.external[k]["attitude"] + 5))
        rule = "遍遣使节修好于四邻，外衅稍弭。"
    else:
        rule = f"施行「{act}」。"
    state.diplomacy_log.append({"act": act, "year": state.year, "month": state.month})
    narr = ""
    if ai_client and getattr(ai_client, "available", False):
        try:
            obj = ai_client.diplomacy(
                f"国力{'强盛' if state.external['辽']['power']>=70 else '中等'}、态度{state.external['辽']['attitude']}",
                f"崛起中、态度{state.external['金']['attitude']}",
                f"国力{'强盛' if state.external['西夏']['power']>=70 else '中等'}、态度{state.external['西夏']['attitude']}",
                "海上之盟" if state.alliance_jin_liao else "未结盟",
                act, summary,
            )
            narr = obj.get("narrative", "") if isinstance(obj, dict) else ""
        except Exception as e:
            raise AIRuntimeError(f"施政时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return (narr + "\n" + rule) if narr else rule


def military_expand(state: GameState, act: str, ai_client=None) -> str:
    """扩军/整军之政。返回叙事文本。

    口径：兵额唯一真账在 state.army_units（list[ArmyUnit]，troops 为真实人数）；
    训练/士气/装备皆为实体字段，装备经中央武库实拨；军费由兵额派生，政令不写死 treasury。
    """
    from ui.panels_military import distribute_arsenal
    summary = _state_summary_min(state)
    if act == "募兵益军":
        # 中央广募厢军：兵额入东京开封府厢军实体（真账）
        _reinforce(state, "东京开封府", "厢军", 60000, "轻步兵")
        rule = "广募厢军六万，兵额大增，然粮饷益绌（军费随兵额派生）。"
    elif act == "整练新军":
        # 西军即驻陕西路禁军：增兵额五万（边地禁军以重骑为骨干）
        _reinforce(state, "陕西路", "禁军", 50000, "重骑兵")
        rule = "整练新军、择将练兵，驻陕禁军增五万，西陲益振（军费随兵额派生）。"
    elif act == "缮修兵甲":
        # 充实武库：为全军禁军实体按缺口实拨装备（无兵额变动）
        got = 0
        for u in _units_of_tier(state, "禁军"):
            granted = distribute_arsenal(state, u, None)
            got += sum(granted.values())
        rule = f"缮修兵甲、充实武库，诸路禁军补给军器 {got} 件，器械精利。"
    elif act == "置将练兵":
        # 禁军训练有素（实体训练度）
        for u in _units_of_tier(state, "禁军"):
            u.training = max(0, min(100, u.training + 5))
        rule = "以文臣换武将、专任责成，禁军训练有素。"
    elif act == "修城备边":
        # 边镇增守城厢军（兵额真账）+ 提升城防质量（fortification 为持久字段，非派生视图）
        for route in ("河北路", "河东"):
            _reinforce(state, route, "厢军", 30000, "轻步兵")
        state._derive_defense_lines()
        for line in ("北线_太原真定", "中线_黄河渡口"):
            if line in state.defense_lines:
                state.defense_lines[line]["fortification"] = max(0, min(100,
                    state.defense_lines[line]["fortification"] + 5))
        rule = "增修边城、浚濠列垒，北顾稍安（守军入军籍真账，城防质量提升）。"
    else:
        rule = f"施行「{act}」。"
    narr = ""
    if ai_client and getattr(ai_client, "available", False):
        try:
            jin_all = sum(u.troops for u in _units_of_tier(state, "禁军"))
            jin_sx = sum(u.troops for u in _units_of_tier(state, "禁军", "陕西路"))
            xiang_all = sum(u.troops for u in _units_of_tier(state, "厢军"))
            obj = ai_client.military_expand(
                f"禁军{jin_all}人（驻陕西军{jin_sx}人）、厢军{xiang_all}人",
                "北顾辽金、西眺西夏",
                "将帅如种师道、折可适等",
                act, summary,
            )
            narr = obj.get("narrative", "") if isinstance(obj, dict) else ""
        except Exception as e:
            raise AIRuntimeError(f"施政时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return (narr + "\n" + rule) if narr else rule


def start_workshop(state: GameState, wid: str, workshop: dict) -> str:
    """发起一座作坊（如酒坊：粮→酒）。

    workshop 结构示例：
      {"name": "酒坊", "recipe": {"grain_feed": 50}, "output_dim": "wine",
       "yield": 30, "active": True}
    """
    if not isinstance(state.workshops, dict):
        state.workshops = {}
    workshop.setdefault("active", True)
    state.workshops[wid] = workshop
    return f"已设「{workshop.get('name', wid)}」，供料则次月产作。"


def reform_policy(state: GameState, act: str, ai_client=None) -> str:
    """制度更张/变法之政。返回叙事文本。"""
    summary = _state_summary_min(state)
    if act == "更役法":
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 5))
        state.treasury += 200000
        rule = "更定役法、均其劳逸，民稍苏而豪右不便。"
    elif act == "行方田均税":
        state.land["hidden_rate"] = max(0.1, state.land["hidden_rate"] - 0.06)
        state.land["cultivated"] = int(state.land["cultivated"] * 1.02)
        state.treasury += 300000
        rule = "方田均税，隐漏稍清、赋役稍均，田主怨谤纷起。"
    elif act == "整顿吏治":
        for fn in state.factions:
            state.factions[fn]["cohesion"] = max(0, min(100, state.factions[fn]["cohesion"] + 3))
        state.prestige = max(0, min(100, state.prestige + 3))
        rule = "澄清吏治、黜陟分明，官方稍肃。"
    elif act == "抑兼并":
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 4))
        state.land["hidden_rate"] = max(0.1, state.land["hidden_rate"] - 0.03)
        rule = "限田抑兼并，贫民稍宽，而权贵侧目。"
    elif act == "宽恤民力":
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 6))
        state.treasury -= 150000
        rule = "宽恤民力、屡下德音，闾阎颂圣。"
    elif act == "核实军籍":
        # 汰去虚额：厢军诸部训练度提升（strength 已废弃，兵精以 training 表达）
        for u in _units_of_tier(state, "厢军"):
            u.training = max(0, min(100, u.training + 3))
        state.treasury += 100000
        rule = "核实军籍、汰去虚额，厢军训练稍进，兵精费省。"
    elif act == "厚禄养廉":
        # 加俸：投入国库 50 万贯进 payraise_budget，逐月驱动各路 pay_ratio 上升、压缩吏俸缺口
        cost = 500_000
        if state.treasury >= cost:
            state.treasury -= cost
            state.payraise_budget += cost
            rule = "厚禄养廉，增俸以绝溪壑之欲，吏稍安而库帑稍减。"
        else:
            rule = "府库不给，厚禄养廉之议暂寝。"
    elif act == "肃察吏弊":
        # 整顿吏治：提升监察力度 oversight，压缩贪腐扣减
        state.oversight = min(1.0, state.oversight + 0.10)
        for fn in state.factions:
            state.factions[fn]["cohesion"] = max(0, min(100, state.factions[fn]["cohesion"] + 3))
        state.prestige = max(0, min(100, state.prestige + 3))
        rule = "肃察吏弊、峻其纠劾，墨吏敛迹而官方稍肃。"
    elif act == "裁汰冗员":
        # 分路减 clerks（联动减 officials×8 关系：clerks 已是 officials×8，此处直接减 clerks 与对应 officials）
        cut = 0
        for p in state.prefectures.values():
            if p.get("clerks", 0) > 0:
                dec = max(1, p["clerks"] // 4)
                p["clerks"] -= dec
                p["officials"] = max(1, p["officials"] - max(1, dec // 8))
                cut += dec
        rule = f"裁汰冗员，诸路省吏 {cut} 员，岁省冗费而失意者怨望。"
    else:
        rule = f"施行「{act}」。"
    narr = ""
    if ai_client and getattr(ai_client, "available", False):
        try:
            obj = ai_client.reform(
                "新党柄国、旧党蓄愤、言路纷纭",
                "冗官冗兵冗费之积弊",
                "陛下倾向" + ("更张" if state.prestige > 50 else "守成"),
                act, summary,
            )
            narr = obj.get("narrative", "") if isinstance(obj, dict) else ""
        except Exception as e:
            raise AIRuntimeError(f"施政时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return (narr + "\n" + rule) if narr else rule


# ============================================================
# 工程 / 制作系统（玩家手动发起，缺料停滞由结算推进）
# ============================================================


def science_policy(state: GameState, act: str, ai_client=None) -> str:
    """科技/工技之政。返回叙事文本。"""
    summary = _state_summary_min(state)
    if act == "修撰营造法式":
        state.tech["level"] = max(0, min(100, state.tech["level"] + 6))
        rule = "诏修《营造法式》，工部营缮有度，百工竞巧。"
    elif act == "火药军用":
        from ui.panels_military import distribute_arsenal
        state.tech["gunpowder"] = max(0, min(100, state.tech["gunpowder"] + 12))
        # 火器入军：为驻陕禁军诸部按缺口实拨军器
        got = 0
        for u in _units_of_tier(state, "禁军", "陕西路"):
            got += sum(distribute_arsenal(state, u, None).values())
        rule = f"火药入于军仗，霹雳震敌，驻陕禁军补给军器 {got} 件，守边之具一新。"
    elif act == "兴水利机械":
        state.tech["hydraulics"] = max(0, min(100, state.tech["hydraulics"] + 10))
        for p in state.prefectures.values():
            p["grain"] = int(p["grain"] * 1.01)
        rule = "水轮、翻车之属兴于陂塘，溉田倍旧。"
    elif act == "校勘医书":
        state.tech["level"] = max(0, min(100, state.tech["level"] + 3))
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 1))
        rule = "校勘医方、颁行天下，民多赖之。"
    elif act == "改历法":
        state.tech["calendar"] = max(0, min(100, state.tech["calendar"] + 8))
        state.prestige = max(0, min(100, state.prestige + 2))
        rule = "更定历法、造新仪，观象益精，朝野称善。"
    elif act == "奖百工":
        state.tech["level"] = max(0, min(100, state.tech["level"] + 5))
        state.tech["masters"] = max(0, min(99, state.tech["masters"] + 1))
        rule = "设奖掖之科，匠人有功则录，技艺日进。"
    elif act == "聘西洋匠":
        state.tech["west"] = max(0, min(5, state.tech["west"] + 1))
        state.tech["level"] = max(0, min(100, state.tech["level"] + 4))
        rule = "远聘西土匠人，舟楫新法渐入，西学东渐。"
    elif act == "设机器局":
        if state.tech["west"] >= 2 and state.tech["level"] >= 85:
            state.tech["level"] = max(0, min(100, state.tech["level"] + 6))
            rule = "设机器局，购机仿制，蒸汽机械遂兴。"
        else:
            rule = "西学未备（需西学≥2、总体≥85），机器局暂难设。"
    elif act == "开矿炼油":
        if state.tech["west"] >= 3:
            state.tech["level"] = max(0, min(100, state.tech["level"] + 6))
            rule = "凿井开矿，熬炼黑金，石油之利渐显。"
        else:
            rule = "西学未及（需西学≥3），炼油之法难行。"
    elif act == "架设电线":
        if state.tech["west"] >= 4:
            state.tech["level"] = max(0, min(100, state.tech["level"] + 6))
            rule = "架设铜线，电传讯息，驿报为之一新。"
        else:
            rule = "西学未及（需西学≥4），电线难架。"
    else:
        rule = f"施行「{act}」。"
    narr = ""
    if ai_client and getattr(ai_client, "available", False):
        try:
            from core.asset_context import build_asset_summary, should_inject
            assets = build_asset_summary(state) if should_inject(act, "科技") else ""
            obj = ai_client.science(
                desensitize_tech(state.tech["level"]),
                f"作坊兴盛度{desensitize_tech(state.tech['level'])}",
                f"火药军用程度{state.tech['gunpowder']}",
                act, summary,
            )
            narr = obj.get("narrative", "") if isinstance(obj, dict) else ""
        except Exception as e:
            raise AIRuntimeError(f"施政时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return (narr + "\n" + rule) if narr else rule


def exam_policy(state: GameState, act: str, ai_client=None) -> str:
    """科举/学校/育才之政。返回叙事文本。"""
    summary = _state_summary_min(state)
    if act == "开科取士":
        state.exam["open"] = True
        state.exam["talent_pool"] = max(0, min(100, state.exam["talent_pool"] + 8))
        state.prestige = max(0, min(100, state.prestige + 3))
        rule = "开科取士，寒俊竞进，人才储备大增。"
    elif act == "改革科举(经义)":
        state.exam["mode"] = "经义"
        state.exam["talent_pool"] = max(0, min(100, state.exam["talent_pool"] + 4))
        rule = "科举改重经义，旧党士子向风，取士稍公。"
    elif act == "改革科举(词学)":
        state.exam["mode"] = "词学"
        state.exam["talent_pool"] = max(0, min(100, state.exam["talent_pool"] + 4))
        state.art_mastery = max(0, min(100, state.art_mastery + 3))
        rule = "科举仍重词学，东南才士归心，艺文益盛。"
    elif act == "兴州县学":
        state.exam["schools"] = max(0, min(100, state.exam["schools"] + 15))
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 2))
        rule = "广设州县之学，童蒙向学，教化稍行。"
    elif act == "制科荐才":
        state.exam["talent_pool"] = max(0, min(100, state.exam["talent_pool"] + 6))
        rule = "诏举制科、大臣荐才，隐逸稍出。"
    elif act == "武举":
        state.exam["talent_pool"] = max(0, min(100, state.exam["talent_pool"] + 3))
        # 擢骁勇为将：驻陕禁军（西军）训练度提升
        for u in _units_of_tier(state, "禁军", "陕西路"):
            u.training = max(0, min(100, u.training + 3))
        rule = "复武举，擢骁勇，将才稍备。"
    else:
        rule = f"施行「{act}」。"
    narr = ""
    if ai_client and getattr(ai_client, "available", False):
        try:
            obj = ai_client.exam(
                "开科" if state.exam["open"] else "停科",
                f"州县学普及{desensitize_talent(state.exam['schools'])}",
                "士论" + ("称之" if state.exam["talent_pool"] > 50 else "平平"),
                act, summary,
            )
            narr = obj.get("narrative", "") if isinstance(obj, dict) else ""
        except Exception as e:
            raise AIRuntimeError(f"施政时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return (narr + "\n" + rule) if narr else rule


def finance_policy(state: GameState, act: str, ai_client=None) -> str:
    """货币/市舶/交子/银行/本位之政。返回叙事文本。"""
    summary = _state_summary_min(state)
    if act == "行交子":
        state.jiaozi["issued"] += 200
        state.jiaozi["trust"] = max(0, min(100, state.jiaozi["trust"] - 5))
        state.treasury += 400000
        rule = "交子增印二百万贯，府库暂充，然商民疑其无本，信用稍减。"
    elif act == "榷货市舶":
        state.maritime["open"] = True
        state.maritime["tariff"] = 0.10
        state.treasury += 300000
        rule = "广开市舶、稍宽舶税，番商云集，海外金银渐入。"
    elif act == "设银行":
        state.bank["established"] = True
        state.bank["capital"] = 500
        state.treasury -= 200000
        rule = "设官营银行（检校库升格），平准物价、收放交子，初立规模。"
    elif act == "定金银铜三品本位":
        state.standard["silver_per_copper"] = 1.0
        state.standard["gold_per_copper"] = 10.0
        state.coin["shortage"] = max(0.0, state.coin["shortage"] - 0.05)
        rule = "定金银铜三品相权之制，钱荒稍纾。"
    elif act == "平抑物价":
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 3))
        state.treasury -= 100000
        rule = "设平准、抑兼并，物价稍平，市井称便。"
    elif act == "铸铁钱":
        state.treasury += 200000
        state.coin["shortage"] = max(0.0, state.coin["shortage"] - 0.08)
        rule = "铸铁钱以济铜荒，泉货稍通，然私铸难禁。"
    else:
        rule = f"施行「{act}」。"
    narr = ""
    if ai_client and getattr(ai_client, "available", False):
        try:
            obj = ai_client.finance(
                desensitize_trust(state.jiaozi["trust"]),
                f"已发{state.jiaozi['issued']}万贯、信用{desensitize_trust(state.jiaozi['trust'])}",
                "市舶" + ("已广开" if state.maritime["open"] else "未广"),
                desensitize_shortage(state.coin["shortage"]),
                "官营银行" + ("已立" if state.bank["established"] else "未立"),
                act, summary,
            )
            narr = obj.get("narrative", "") if isinstance(obj, dict) else ""
        except Exception as e:
            raise AIRuntimeError(f"施政时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return (narr + "\n" + rule) if narr else rule


def govern_yamen(state: GameState, yamen_name: str, act: str, ai_client=None) -> str:
    """在六部衙门施行一项举措。返回叙事文本。"""
    if yamen_name not in state.yamen:
        return "并无此衙门。"
    y = state.yamen[yamen_name]
    y["efficiency"] = max(0, min(100, y["efficiency"] + 4))
    y["backlog"] = max(0, y["backlog"] - 2)
    # 规则结算（数值由程序定，AI 只叙事）
    if act == "整饬吏治":
        state.factions[y["faction"]]["satisfaction"] = max(0, min(100, state.factions[y["faction"]]["satisfaction"] + 4))
        state.prestige = max(0, min(100, state.prestige + 2))
        rule = f"{yamen_name}整饬吏治，官场为之一清，{y['faction']}颇有微词而惮于帝威。"
    elif act == "裁汰冗员":
        state.treasury += 300000
        state.population_satisfaction = max(0, min(100, state.population_satisfaction - 2))
        rule = f"{yamen_name}裁汰冗员，岁省冗费三十万贯，然失意者怨望。"
    elif act == "清丈田亩":
        state.land["cultivated"] = int(state.land["cultivated"] * 1.03)
        state.land["hidden_rate"] = max(0.1, state.land["hidden_rate"] - 0.04)
        state.treasury += 400000
        rule = f"{yamen_name}清丈田亩，隐漏稍清，岁入增四十万贯。"
    elif act == "减免田赋":
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 6))
        state.treasury -= 300000
        rule = f"{yamen_name}奏请减免田赋，民间称颂，国帑少入。"
    elif act == "常平仓赈济":
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 4))
        state.refugee_count = max(0, state.refugee_count - 100000)
        state.treasury -= 250000
        rule = f"{yamen_name}开常平仓赈济，流民稍安。"
    elif act == "兴修水利":
        for p in state.prefectures.values():
            p["mood"] = max(0, min(100, p["mood"] + 2))
        state.treasury -= 300000
        rule = f"{yamen_name}兴修水利，诸路农田得利，民情渐安。"
    elif act == "营缮宫观":
        state.art_mastery = max(0, min(100, state.art_mastery + 3))
        state.prestige = max(0, min(100, state.prestige + 1))
        state.population_satisfaction = max(0, min(100, state.population_satisfaction - 3))
        state.treasury -= 500000
        rule = f"{yamen_name}营缮宫观，工役繁兴，百姓劳苦而园林壮丽。"
    elif act == "开矿铸钱":
        state.treasury += 350000
        state.population_satisfaction = max(0, min(100, state.population_satisfaction - 2))
        rule = f"{yamen_name}开矿铸钱，国用稍宽，然钱法渐乱。"
    elif act == "整练新军":
        # 兵额入陕西路禁军实体真账（西军即驻陕禁军）
        _reinforce(state, "陕西路", "禁军", 50000, "重骑兵")
        rule = f"{yamen_name}整练新军，驻陕禁军增五万，武备稍振（军费随兵额派生）。"
    elif act == "宽刑省狱":
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 3))
        rule = f"{yamen_name}宽刑省狱，囹圄一空，颂声四起。"
    elif act == "重开贡举":
        state.prestige = max(0, min(100, state.prestige + 4))
        state.art_mastery = max(0, min(100, state.art_mastery + 2))
        rule = f"{yamen_name}重开贡举，天下士子向风。"
    elif act == "兴修礼乐":
        state.art_mastery = max(0, min(100, state.art_mastery + 4))
        state.prestige = max(0, min(100, state.prestige + 2))
        rule = f"{yamen_name}兴修礼乐，雅颂复作。"
    else:
        rule = f"{yamen_name}依制施行「{act}」。"
    # AI 叙事（核心玩法依赖，故障即停）
    narr = ""
    if ai_client and getattr(ai_client, "available", False):
        try:
            obj = ai_client.govern_yamen(yamen_name, y["duty"], y["faction"], act, state.get_state_summary())
            narr = obj.get("narrative", "") if isinstance(obj, dict) else ""
        except Exception as e:
            raise AIRuntimeError(f"施政时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return (narr + "\n" + rule) if narr else rule


# ============================================================
# 地方州县施政（AI 叙事 + 规则结算）
# ============================================================


def granary_policy(state: GameState, act: str, amount: int = 0, ai_client=None) -> str:
    """仓廪施政：折变/和籴/开仓赈济/兴漕运(治水)/扩建仓储/颁一条鞭/复本色/方田均税/安置流民。

    一切重大仓廪之政本应经拟旨系统下发（皇帝管方向、官僚管执行）；本命令作为
    单机便捷入口，供仓廪面板调用。返回叙事文本。
    """
    from content.data import DISASTER_RELIEF_GRAIN, GRANARY_CAP_SOFT
    if act == "折变":
        amount = max(0, min(state.granary, amount))
        if amount <= 0:
            return "太仓已无余粟可折变。"
        price = state.grain_price
        got = int(amount * price * 10000)
        state.change_granary(-amount)
        state.treasury += got
        state.granary_stats["converted"] += amount
        return f"诏发太仓粟 {amount}万石折变，得钱 {got/10000:.0f}万贯入国库（米价 {price:.2f}贯/石）。"
    elif act == "和籴":
        if amount <= 0:
            return "请指定和籴粮数。"
        price = state.grain_price * 1.3   # 灾年谷贵，购价高于折变
        cost = int(amount * price * 10000)
        if state.treasury < cost:
            return "国帑不足，难以和籴。"
        state.treasury -= cost
        room = max(0, state.granary_cap - state.granary)
        amount = min(amount, room)
        state.change_granary(amount)
        return f"朝廷于丰处和籴粟 {amount}万石入太仓，耗钱 {cost/10000:.0f}万贯。"
    elif act == "开仓赈济":
        relief = min(DISASTER_RELIEF_GRAIN, state.granary)
        if relief <= 0:
            return "太仓无粟，无法赈济。"
        state.change_granary(-relief)
        state.granary_stats["relief"] += relief
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 4))
        state.refugee_count = max(0, state.refugee_count - relief * 3000)
        return f"开太仓发粟 {relief}万石赈济，饥民得食，流民稍安。"
    elif act == "兴漕运":
        # 疏浚运河、治水，降漕运阻塞
        cost = 200000
        if state.treasury < cost:
            return "国帑不足，难以大兴漕运。"
        state.treasury -= cost
        state.canal_block = max(0, state.canal_block - random.randint(10, 20))
        return f"兴修漕渠，增置纲船，输粟转运益通（阻塞降至 {state.canal_block}）。"
    elif act == "扩建仓储":
        cost = int(amount * 10000) if amount > 0 else 200000
        if state.treasury < cost:
            return "国帑不足，难以扩建仓储。"
        add = amount if amount > 0 else 200
        room = max(0, GRANARY_CAP_SOFT - state.granary_cap)
        add = min(add, room)
        if add <= 0:
            return "太仓已臻规制之极，难再增容。"
        state.treasury -= cost
        state.change_granary_cap(add)
        return f"新筑仓廪，太仓增容 {add}万石（现容 {state.granary_cap}万石）。"
    elif act == "颁一条鞭":
        state.single_whip = True
        return "颁行一条鞭法，两税改征折银，岁入稍丰而仓廪失本色之源。"
    elif act == "复本色":
        state.single_whip = False
        return "复旧制，两税仍征本色入仓，太仓渐实而国用待折变。"
    elif act == "方田均税":
        state.land["hidden_rate"] = max(0.0, state.land["hidden_rate"] - 0.10)
        for fn in ("旧党", "东南士人"):
            if fn in state.factions:
                state.factions[fn]["satisfaction"] = max(0, state.factions[fn]["satisfaction"] - 5)
        return "行方田均税，清丈隐田，隐漏稍抑，然豪强怨望。"
    elif act == "安置流民":
        used = min(amount if amount > 0 else 100, state.land.get("wasteland", 0))
        state.land["wasteland"] = max(0, state.land.get("wasteland", 0) - used)
        state.land["cultivated"] += used
        state.refugee_count = max(0, state.refugee_count - used * 5000)
        return f"安置流民垦荒 {used}万亩，流民渐归田亩。"
    return "未知仓廪之政。"


def _state_summary_min(state):
    """给 AI 的精简脱敏态势字符串（避免超长）。"""
    s = state.get_state_summary()
    fin = s.get("finance_ext", {})
    ex = s.get("exam_ext", {})
    te = s.get("tech_ext", {})
    return (
        f"时间：{s['time']}；皇威：{s['prestige']['desc']}；"
        f"国库：{s['treasury']['desc']}；民心：{s['pop_sat_desc']}；"
        f"金融：交子{fin.get('jiaozi_trust','')}、{fin.get('coin_shortage','')}、{fin.get('maritime_open','')}；"
        f"工商征{fin.get('commerce_tax','')}；"
        f"科举：{ex.get('open','')}（{ex.get('mode','')}）、人才{ex.get('talent','')}；"
        f"科技：{te.get('level','')}；外交：{s.get('diplomacy_ext',{}).get('alliance','')}；"
        f"金态度：{state.external.get('金',{}).get('attitude',50)}，"
        f"辽态度：{state.external.get('辽',{}).get('attitude',50)}，"
        f"西夏态度：{state.external.get('西夏',{}).get('attitude',50)}。"
    )


