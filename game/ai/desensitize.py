# -*- coding: utf-8 -*-
"""宋祚 · AI 事实脱敏模块
将数值型游戏状态转化为自然语言描述后发给 AI，
避免 AI 基于精确数值做"计算最优解"。
"""
import json
from content.data import (
    desensitize_prestige, desensitize_arrival,
    desensitize_satisfaction, desensitize_treasury,
    get_prestige_level,
)


def desensitize_state(state_summary: dict) -> dict:
    """将 GameState 摘要脱敏为叙事可读的状态描述"""
    sensitive = {}

    # 时间
    sensitive["时间"] = state_summary.get("time", "未知")

    # 皇威脱敏
    prestige = state_summary.get("prestige", {})
    sensitive["皇威"] = {
        "等级": prestige.get("level", "平平"),
        "描述": prestige.get("desc", "平平"),
    }

    # 皇帝健康脱敏
    health = state_summary.get("health", 75)
    if health >= 80:
        sensitive["龙体"] = "圣躬安泰"
    elif health >= 60:
        sensitive["龙体"] = "偶有小恙"
    elif health >= 40:
        sensitive["龙体"] = "龙体欠安"
    elif health >= 20:
        sensitive["龙体"] = "病体沉重"
    else:
        sensitive["龙体"] = "龙驭垂危"

    # 国库脱敏
    treasury = state_summary.get("treasury", {})
    sensitive["国库"] = treasury.get("desc", "勉强维持")

    # 到账率脱敏
    arrival = state_summary.get("arrival_rate", {})
    sensitive["税收到账"] = arrival.get("desc", "不足五成")

    # 朝堂派系脱敏
    factions = state_summary.get("factions", {})
    sensitive["朝堂"] = {}
    for fname, finfo in factions.items():
        sensitive["朝堂"][fname] = {
            "势力": _desensitize_influence(finfo.get("influence", 50)),
            "对君态度": finfo.get("sat_desc", "大体认可"),
        }

    # 外部脱敏
    external = state_summary.get("external", {})
    sensitive["边境"] = {}
    for ename, einfo in external.items():
        power = einfo.get("power", 50)
        attitude = einfo.get("attitude", 50)
        if attitude >= 70:
            rel = "友善"
        elif attitude >= 40:
            rel = "一般"
        elif attitude >= 20:
            rel = "敌视"
        else:
            rel = "仇敌"

        if power >= 80:
            pow_desc = "强盛"
        elif power >= 50:
            pow_desc = "中等"
        elif power >= 30:
            pow_desc = "虚弱"
        else:
            pow_desc = "衰微"

        sensitive["边境"][ename] = f"国力{pow_desc}，关系{rel}"

    # 民情脱敏
    sensitive["民情"] = {
        "民心": state_summary.get("pop_sat_desc", "大体认可"),
        "流民": f"{state_summary.get('refugee_count', 0)}人" if state_summary.get("refugee_count", 0) > 0 else "无",
    }

    # 诏令资源
    sensitive["政令资源"] = {
        "可下圣旨": f"最多{state_summary.get('decree_bandwidth', 6)}条",
        "待执行": f"{state_summary.get('pending_decrees', 0)}条",
    }

    # 皇帝个人
    personal = state_summary.get("personal", {})
    art = personal.get("art", 85)
    tao = personal.get("taoism", 25)
    pleas = personal.get("pleasure", 30)
    sensitive["天子好尚"] = []
    if art >= 80:
        sensitive["天子好尚"].append("酷爱书画")
    if tao >= 60:
        sensitive["天子好尚"].append("笃信道教")
    if pleas >= 60:
        sensitive["天子好尚"].append("喜好宴游")

    return sensitive


def _desensitize_influence(influence: int) -> str:
    """影响力脱敏"""
    if influence >= 90:
        return "权倾朝野"
    elif influence >= 70:
        return "势力强劲"
    elif influence >= 50:
        return "中流砥柱"
    elif influence >= 30:
        return "势单力薄"
    elif influence >= 10:
        return "苟延残喘"
    return "几近消亡"


def desensitize_for_ai(state) -> str:
    """将完整 GameState 转为 AI 可读的脱敏文本"""
    summary = state.get_state_summary()
    ds = desensitize_state(summary)
    return json.dumps(ds, ensure_ascii=False, indent=2)
