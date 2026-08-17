# -*- coding: utf-8 -*-
"""宋祚 · 结算评价系统"""
import random

from content.data import EVAL_WEIGHTS, EVAL_OUTCOMES, END_YEAR


def evaluate_game(state) -> dict:
    """七维评价，返回评价结果"""
    # 文治 (诏令执行率 & 政绩)
    wen = 50
    total_decrees = state.statistics["total_decrees"]
    if total_decrees > 50:
        wen += 20
    elif total_decrees > 20:
        wen += 10
    # 政体稳定度
    n_factions = len(state.factions)
    avg_sat = sum(f["satisfaction"] for f in state.factions.values()) / n_factions if n_factions else 50
    wen += (avg_sat - 50) * 0.3
    wen = max(0, min(100, wen))

    # 武功
    wu = 50
    if state.statistics["total_wars"] == 0:
        wu -= 10  # 毫无战事也算不上武功
    # 军队综合强度：以实体层 army_units 的单兵战力均值折算为 0~100 强度百分
    from ui.panels_military import _army_power
    gun = state.tech.get("gunpowder", 20)
    powers = [_army_power(u, gun) for u in state.army_units] if state.army_units else [0]
    avg_army = sum(powers) / len(powers) if powers else 0
    avg_army = max(0, min(100, avg_army / 1000.0))
    wu += (avg_army - 50) * 0.5
    avg_def = sum(d["garrison"] for d in state.defense_lines.values()) / len(state.defense_lines)
    wu += (avg_def - 50) * 0.3
    wu = max(0, min(100, wu))

    # 民生
    minsheng = state.population_satisfaction

    # 财政
    caizheng = 50
    if state.treasury > 10_000_000:
        caizheng = 90
    elif state.treasury > 5_000_000:
        caizheng = 70
    elif state.treasury > 0:
        caizheng = 50
    elif state.treasury > -2_000_000:
        caizheng = 30
    else:
        caizheng = 10

    # 艺术造诣
    yishu = state.art_mastery

    # 声望 (皇威 + 综合影响力)
    shengwang = state.prestige * 0.6 + (sum(f["influence"] for f in state.factions.values()) / n_factions if n_factions else 0) * 0.4

    # 百姓口碑：流民率（refugee/population，通常落在 0~0.1 区间）越高口碑越低，量纲平滑
    refugee_rate = state.refugee_count / max(state.population, 1)
    koubei = state.population_satisfaction * 0.7 + (100 - refugee_rate * 100) * 0.3
    koubei = max(0, min(100, koubei))

    scores = {
        "文治": wen,
        "武功": wu,
        "民生": minsheng,
        "财政": caizheng,
        "艺术造诣": yishu,
        "声望": shengwang,
        "百姓口碑": koubei,
    }

    # 加权总分
    # EVAL_WEIGHTS 各项之和为 1.0，各维分数均在 0~100，故 total 天然落在 0~100。
    # 不再乘以 100/85（原会把 85 分拉到 117 再截断为 100，使阈值失真）。
    total = max(0, min(100, sum(scores[k] * EVAL_WEIGHTS[k] for k in EVAL_WEIGHTS)))

    # 判定结局
    outcome = "身死国灭"
    for threshold, name in EVAL_OUTCOMES:
        if total >= threshold:
            outcome = name
            break

    return {
        "scores": scores,
        "total": round(total, 1),
        "outcome": outcome,
        "description": _get_outcome_desc(outcome),
    }


def _get_outcome_desc(outcome: str) -> str:
    descs = {
        "中兴": "挽狂澜于既倒，扶大厦之将倾。大宋中兴之主，青史流芳。",
        "守成": "虽无开拓之功，然守成有方，大宋基业得以维系。",
        "治平": "庸主之姿，乏善可陈。天下粗安，然隐患已伏。",
        "昏聩": "嬉游无度、任用非人，国势日蹙，堪称昏聩之主。",
        "身死国灭": "重蹈史实覆辙，靖康之耻，身死国灭，为天下笑。",
    }
    return descs.get(outcome, "")

# ------------------------------------------------------------
# 防线判定公共骨架（退位/游戏结束共用；两套阈值语义不同，必须各自保留）
# ------------------------------------------------------------
def _garrison_breached(state, threshold: int, line_name: str = None) -> bool:
    """防线驻军是否跌破阈值。

    - line_name 为 None：任一边防空虚（供退位「边防空虚」判定，无年份约束）
    - line_name 指定：仅该线跌破（供游戏结束「京城陷落」判定，调用方另加年份约束）
    两处阈值/年份条件语义不同，由调用方各自传参，不在此合并。
    """
    if line_name is None:
        for _ln, line in state.defense_lines.items():
            if line.get("garrison", 0) < threshold:
                return True
        return False
    line = state.defense_lines.get(line_name, {})
    return line.get("garrison", 100) < threshold


# ------------------------------------------------------------
# 退位条件检测
# ------------------------------------------------------------
def check_abdication(state) -> tuple:
    """检测是否触发退位条件，(是否退位, 原因)"""
    reasons = []

    # 民怨沸腾
    if state.population_satisfaction < 20:
        reasons.append("民怨沸腾")
    # 国库亏空严重
    if state.treasury < -5000000:
        reasons.append("国库亏空")
    # 皇威扫地且健康差
    if state.prestige < 25 and state.emperor_health < 30:
        reasons.append("皇威扫地龙体不支")
    # 兵临城下（任一边防空虚，阈值 20，无年份约束）
    for line_name, line in state.defense_lines.items():
        if _garrison_breached(state, 20, line_name):
            reasons.append(f"边防空虚-{line_name}")
            break

    if len(reasons) >= 2:
        return (True, "、".join(reasons))
    return (False, "")

# ------------------------------------------------------------
# 死亡判定
# ------------------------------------------------------------
def check_emperor_death(state) -> tuple:
    """检测皇帝是否死亡，(是否死亡, 原因)"""
    if state.emperor_health <= 0:
        return (True, "龙驭上宾")
    # 强制收束年：到达 END_YEAR 后无论如何收束，避免玩家无限拖局刷分
    if state.year >= END_YEAR:
        if state.emperor_health < 20 or random.random() < 0.5:
            return (True, "岁暮龙驭（收束年驾崩）")
        return (False, "")
    # 自然衰老：年事渐高（1120 年后）且龙体欠佳时，每月有一定概率寝疾
    if state.year >= 1120 and state.emperor_health < 30:
        if random.random() < 0.03:
            return (True, "寝疾弥留")
    return (False, "")


def check_reach_end_year(state) -> tuple:
    """到达强制收束年但皇帝尚在人世时，游戏仍应以收束方式结束，不再允许继续拖延。"""
    if state.year >= END_YEAR:
        return (True, "收束之年已至，国事当有定论")
    return (False, "")


def check_game_over(state):
    """综合检测游戏结束条件"""
    # 国库崩坏（国用耗竭，天下鼎沸）
    from content.data import TREASURY_COLLAPSE_LINE
    if state.treasury < TREASURY_COLLAPSE_LINE:
        state.game_over = True
        state.game_result = "国用耗竭，天下鼎沸——大宋府库空虚，纲纪尽弛"
        return True
    # 死亡
    dead, reason = check_emperor_death(state)
    if dead:
        state.game_over = True
        state.emperor_alive = False
        state.game_result = f"大宋皇帝{state.emperor_name}驾崩——{reason}"
        return True

    # 退位
    abd, reason = check_abdication(state)
    if abd:
        state.game_over = True
        state.is_abdicated = True
        state.abdication_reason = reason
        state.game_result = f"被迫退位——{reason}"
        return True

    # 到达强制收束年但尚未触发其他结局时，以收束方式结束
    reached, reach_reason = check_reach_end_year(state)
    if reached:
        state.game_over = True
        state.game_result = f"收束之年——{reach_reason}"
        return True

    # 强制结束 (被围、社稷颠覆)
    # 检查京城防线（内线_东京城防，阈值 10 且年 >=1126 —— 与退位的任一边防空虚语义不同）
    if _garrison_breached(state, 10, "内线_东京城防") and state.year >= 1126:
        state.game_over = True
        state.game_result = "京城陷落，社稷颠覆——靖康之耻重演"
        return True

    return False
