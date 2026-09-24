# -*- coding: utf-8 -*-
"""宋祚 · 军事外交、派系冲击与事件（从 settlement_steps.py 拆出，零行为变更）。

`_settle_military_diplomacy` / `_settle_events` / `_settle_factions`。"""
from __future__ import annotations

import random

from content.data import (
    EVENT_CATEGORIES,
    ECONOMY_PRESSURE_THRESHOLD_GRANARY,
    ECONOMY_PRESSURE_THRESHOLD_PRICE,
)

from core.settlement_common import (
    _return_men,
    _P1_ATT_DELTA,
    _P1_ARM_DELTA,
    _P1_TRAIN_DELTA,
    _P1_LEVY_COST,
)

def _settle_factions(state, log):
    """派系**冲击**结算（Step 2）：只读 AI 契约 → 记事件叙事与 `_event_delta` 冲击。

    2026-09-19 方案第 3 步（faction_pop_optimization_plan）：本步**不再随机游走、
    不再直接改 influence/satisfaction/cohesion** —— 那三个读数改由 Step 5 之后的
    `_settle_faction_metrics`（core/faction_settle.py，**唯一写入点**）由 POP 派生。
    纪律（政策传导顺序）：**禁止先改 faction 数值再假设 POP 受益**；本步只把
    “本月发生的事”（党争/联姻/分裂/和解/清算、AI 契约档位）记成 `_event_delta`，
    由派生步在读完 POP 之后一次性消化。
    """
    from core.numeric import parse_number as _num
    # 12 步 agent 化 P2+：读取派系 AI 契约
    _faction_ai = getattr(state, "_faction_ai", None)
    ai_factions = {}
    ai_events = []
    if isinstance(_faction_ai, dict) and not _faction_ai.get("_error"):
        ai_factions = _faction_ai.get("factions", {})
        ai_events = _faction_ai.get("events", [])
        if _faction_ai.get("narrative"):
            log.append(f"[党争] {_faction_ai['narrative']}")

    # AI 契约档位 + 立场 → `_event_delta`（冲击；不直接落 satisfaction/influence）
    sat_map = {"微": 1.0, "小": 2.0, "中": 4.0, "大": 6.0}
    for name, f in state.factions.items():
        if not isinstance(f, dict) or name not in ai_factions:
            continue
        ai_f = ai_factions[name] if isinstance(ai_factions[name], dict) else {}
        stance = str(ai_f.get("stance", "观望"))
        sign = {"进取": 1.0, "守成": -1.0}.get(stance, 0.0)
        if sign == 0.0:
            continue
        d = sign * sat_map.get(str(ai_f.get("satisfaction", "小")), 2.0)
        f["_event_delta"] = max(-12.0, min(12.0,
                                          _num(f.get("_event_delta"), 0.0) + d))

    # AI 契约事件
    for event in ai_events:
        etype = event.get("type", "")
        desc = event.get("desc", "")
        tier = event.get("tier", "小")
        if etype == "党争":
            log.append(f"[党争] {desc}")
            state.change_prestige(-2, "党争")
        elif etype == "联姻":
            log.append(f"[联姻] {desc}")
        elif etype == "分裂":
            log.append(f"[分裂] {desc}")
            state.change_prestige(-3, "派系分裂")
        elif etype == "和解":
            log.append(f"[和解] {desc}")
            state.change_prestige(2, "派系和解")
        elif etype == "清算":
            log.append(f"[清算] {desc}")
            state.change_prestige(-5, "派系清算")

    infs = [(name, f["influence"]) for name, f in state.factions.items()]
    infs.sort(key=lambda x: x[1], reverse=True)
    if infs[0][1] - infs[-1][1] > 40:
        log.append("[党争] 朝堂势力悬殊，暗流涌动")
        state.change_prestige(-1, "党争")


def _settle_military_diplomacy(state, log):
    """军事与外部势力推进（12 步 agent 化 P1：外交/军事契约接线，守恒铁律——
    岁币金额/兵额扣补走既有守恒步，agent 只给档位词）"""
    tl = state.timeline
    _dip = getattr(state, "_diplomacy_ai", None)
    _mil = getattr(state, "_military_ai", None)

    # 外交契约（attitude 档位 → ±3~±8；岁币/盟约布尔）
    if isinstance(_dip, dict) and not _dip.get("_error"):
        d = _P1_ATT_DELTA.get(_dip.get("attitude", "小"), 5)
        for k in ("金", "辽", "西夏"):
            cur = state.external[k]["attitude"]
            direction = 1 if cur < 70 else -1     # 岁币阈值 70 同源：低于趋善、高于遏制
            state.external[k]["attitude"] = max(0, min(100, cur + direction * d))
        if _dip.get("sui_gong") == "订":
            state._sui_gong = True
        elif _dip.get("sui_gong") == "毁":
            state._sui_gong = False
        if _dip.get("alliance") == "结":
            state.alliance_jin_liao = True
        elif _dip.get("alliance") == "断":
            state.alliance_jin_liao = False

    jin = state.external["金"]
    if "jin_crushed" in tl:
        jin["power"] = min(jin["power"], 20)
        jin["invasion_will"] = 0
    elif state.year >= 1115 and "liao_ally" not in tl:
        jin["power"] = min(100, jin["power"] + random.uniform(0.5, 1.5))
        jin["invasion_will"] = min(100, jin["invasion_will"] + random.uniform(0.2, 0.8))
    elif state.year >= 1115 and "liao_ally" in tl:
        jin["power"] = min(100, jin["power"] + random.uniform(0.1, 0.5))

    liao = state.external["辽"]
    if "liao_ally" in tl:
        liao["power"] = min(100, liao["power"] + random.uniform(0.1, 0.4))
    elif state.year >= 1110:
        liao["power"] = max(10, liao["power"] - random.uniform(0.3, 0.8))

    xixia = state.external["西夏"]
    if random.random() < 0.1:
        xixia["attitude"] = max(10, min(90, xixia["attitude"] + random.randint(-10, 10)))

    # 军事契约（power%/兵额/训练士气/征发——训练士气与兵额调整程序换算，cost 由守恒步扣）
    # 审查 P1：无论有无 AI，一律叠加月度衰减基线（防只增不减导致士气/训练长期膨胀）
    for u in state.army_units:
        if random.random() < 0.15:
            u.training = max(10, u.training - random.randint(1, 2))
        if random.random() < 0.10:
            u.morale = max(10, u.morale - 1)
    if isinstance(_mil, dict) and not _mil.get("_error"):
        for u in state.army_units:
            u.training = max(10, min(100, u.training + _P1_TRAIN_DELTA.get(_mil.get("training", "微"), 2)))
            u.morale = max(10, min(100, u.morale + _P1_TRAIN_DELTA.get(_mil.get("morale", "微"), 2)))
        # 兵额调整：AI 只可减员（裁汰）；增募必须走批红军令通道（防 AI 直接铸兵）
        # 审查修复三处：
        #  (1) 原判 d_arm < 0，而 _P1_ARM_DELTA 全为正值（1万~5万）→ 本分支实为死码；
        #      语义应为「该档位即裁汰额上限」，故改判 _cut > 0；
        #  (2) 原直接改 branches 字典，绕开 add_troops（真账=Σbranches，余数归主兵种）；
        #      改用 add_troops(-_cut)；
        #  (3) 裁下的人丁原凭空消失，现经 _return_men 回流本路农户（人守恒）。
        # 另：默认档由「微」改「无(=0)」——缺 army 键时不应凭空裁汰一万人。
        _cut = _P1_ARM_DELTA.get(_mil.get("army", "无"), 0)
        if _cut > 0 and state.army_units:
            u = max(state.army_units, key=lambda x: x.troops)
            _cut = min(_cut, u.troops)
            if _cut > 0:
                u.add_troops(-_cut)
                _return_men(state, u.station, _cut)
                log.append(f"[枢密] 裁汰冗兵 {_cut} 人（人丁还民）")
        levy = _P1_LEVY_COST.get(_mil.get("levy", "微"), 100000)
        if getattr(state, "treasury", 0) >= levy:
            state.change_treasury(-levy)     # 征发 cost 守恒扣款（程序，非 agent 直写）
            log.append(f"[枢密] 征发军资 {levy} 贯")


# ------------------------------------------------------------
# Step 7: 事件系统
# ------------------------------------------------------------

def _settle_events(state, log):
    """事件压力推进与触发"""
    for cat in EVENT_CATEGORIES:
        if cat not in state.event_pressure:
            state.event_pressure[cat] = 0
        growth = random.uniform(0, 2) * state.diff_params.get("event_pressure_mult", 1.0)
        state.event_pressure[cat] += growth

    util = state.granary_capacity_used()
    # P0-③ 起义类事件压力仅在史实窗口（1118 年方腊/1111 年宋江起）受
    # 流民/太仓/米价/民怨推动，杜绝 1101 年开局即触发 1118 年起义（史实错误）。
    if state.year >= 1118:
        for name, p in state.prefectures.items():
            local_unrest = p.get("unrest", 15)
            local_ref = p.get("refugees", 0)
            if local_unrest >= 40 or local_ref >= 8000:
                boost = (local_unrest - 30) * 0.05 + local_ref / 2000.0
                for cat in ("方腊起义", "宋江起义"):
                    if cat in state.event_pressure:
                        state.event_pressure[cat] += boost * random.uniform(0.8, 1.2)
        if util < ECONOMY_PRESSURE_THRESHOLD_GRANARY:
            for cat in ("方腊起义", "宋江起义"):
                if cat in state.event_pressure:
                    state.event_pressure[cat] += random.uniform(1.0, 2.5)
            log.append("[经济] 太仓告匮，流民聚啸，起义之谋渐生")
        if state.grain_price >= ECONOMY_PRESSURE_THRESHOLD_PRICE:
            for cat in ("方腊起义", "宋江起义"):
                if cat in state.event_pressure:
                    state.event_pressure[cat] += random.uniform(0.5, 1.5)
            log.append("[经济] 米价腾涌，民不堪命，变乱之兆萌焉")
        if state.population_satisfaction < 30:
            for cat in ("方腊起义", "宋江起义"):
                if cat in state.event_pressure:
                    state.event_pressure[cat] += random.uniform(0.5, 1.5)

    if state.year >= 1102 and "花石纲" not in state.event_pressure:
        state.event_pressure["花石纲"] = 10

    if state.year >= 1118:
        if "方腊起义" not in state.event_pressure:
            state.event_pressure["方腊起义"] = 20
        state.event_pressure["方腊起义"] += random.uniform(1, 4)

    if state.year >= 1111:
        if "宋江起义" not in state.event_pressure:
            state.event_pressure["宋江起义"] = 10
        state.event_pressure["宋江起义"] += random.uniform(0.5, 2)

    if "jin_crushed" in state.timeline or "no_jingkang" in state.timeline:
        state.event_pressure["金军南侵"] = 0
    elif state.year >= 1120:
        if "金军南侵" not in state.event_pressure:
            state.event_pressure["金军南侵"] = 10
        if "liao_ally" in state.timeline:
            state.event_pressure["金军南侵"] += random.uniform(0.25, 0.75)
        else:
            state.event_pressure["金军南侵"] += random.uniform(0.5, 1.5)

    threshold_base = 80
    threshold = threshold_base * state.diff_params.get("event_threshold_mult", 1.0)
    for cat, pressure in list(state.event_pressure.items()):
        if pressure >= threshold:
            _trigger_event(state, cat, log)
            state.event_pressure[cat] = 0


def _trigger_event(state, category, log):
    """触发事件"""
    message = f"[事件] {category} 爆发！"
    log.append(message)
    state.active_events.append({
        "category": category,
        "turn": state.turn,
        "message": message,
    })
    state.statistics["total_disasters" if "灾" in category or "起义" in category else "total_wars"] += 1
    state.change_prestige(-5, f"{category}爆发")
    # 记忆知识库（Phase 3a）：事件落地写入图谱（event 实体 + involves）
    try:
        state.memory.turn = state.turn
        state.memory.record_event(f"event_{state.turn}_{category}", category, turn=state.turn)
    except Exception:
        pass


