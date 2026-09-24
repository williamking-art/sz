# -*- coding: utf-8 -*-
"""宋祚 · 皇帝个人与隐藏状态（从 settlement_steps.py 拆出，零行为变更）。

`_settle_emperor_personal` / 帝王行动效果 / `_settle_hidden(_pop)`。"""
from __future__ import annotations

import random

from content.data import (
    TIER_RANGE,
)

from core.settlement_common import (
    _distribute_cash,
)

def _settle_hidden_pop(state, log):
    """隐户动态（月度，人口守恒——隐户是第 7 类动态人口池，与六类 POP 转换）：

    1) 在籍 → 隐户（史实：赋税重/灾荒/民怨时民逃为隐户）：税重 + 灾荒（路粮缺）+
       民怨 → 部分农/工匠/商人转隐户（农 POP size 减、隐户增——逃税逃役）；
    2) 隐户 → 在籍（史实：清丈/轻徭/招抚时归籍）：清丈（land.survey）或轻徭政策
       → 隐户转农（隐户减、POP 增——归籍复业）。
    守恒：Σ六类 size（口） + hidden_households×4（口） 不变（转换非凭空）；
    隐户不落籍不纳税；UI 不显示（设计锚）。"""
    land = state.land
    hidden = int(land.get("hidden_households", 5_000_000))
    total_in_reg = sum(pop["size"] for _p in state.prefectures.values()
                       for pop in _p["pops"].values())
    if total_in_reg <= 0:
        return
    # 1) 逃户压力（在籍→隐户）：税率高 + 灾荒 + 民怨
    # 审查 P2-20 修复：原读 `commerce_tax`（不存在，getattr 恒返回默认 0.05）→ 压力恒 0，
    # 「税重→逃户」永不触发。改为真实字段 commerce_tax_rate，基准取默认税率 0.15
    # （超过常规税率才产生逃户压力，默认配置下不改变既有平衡）。
    _tax_pressure = min(0.010, max(0.0, (getattr(state, "commerce_tax_rate", 0.15) - 0.15) * 1.0))
    _sat_pressure = max(0.0, (50 - getattr(state, "population_satisfaction", 50)) / 50.0) * 0.004
    _disaster = 0.0
    for _p in state.prefectures.values():
        if _p.get("grain", 0) < max(_p.get("population", 1_000_000), 1) * 0.3:
            _disaster = 0.008
            break
    _flee_rate = min(0.012, _tax_pressure + _sat_pressure + _disaster)
    if _flee_rate > 0:
        _flee = int(total_in_reg * _flee_rate)
        _flee_left = _flee
        for _pop_name in ("农", "工匠", "商人"):
            if _flee_left <= 0:
                break
            for _p in state.prefectures.values():
                if _flee_left <= 0:
                    break
                _pop = _p["pops"][_pop_name]
                _t = min(_flee_left, int(_pop["size"] * 0.02))
                if _t > 0:
                    _pop["size"] = max(0, _pop["size"] - _t)
                    _flee_left -= _t
        _flee_actual = _flee - _flee_left
        if _flee_actual > 0:
            # 口 → 户精确换算：整除转户 + 余数口记账（land["hidden_rem"] 累计 ≥4 转户）
            # ——修复整数截断凭空多/少人口（test_global_ledger_total ΔP 根因）
            hidden += _flee_actual // 4
            _rem = int(land.get("hidden_rem", 0)) + _flee_actual % 4
            if _rem >= 4:
                hidden += _rem // 4
                _rem = _rem % 4
            land["hidden_rem"] = _rem
            log.append(f"[隐户] 税重民困，{_flee_actual:,} 口逃为隐户（不落籍不纳税）")
    # 2) 归籍（隐户→在籍）：清丈/轻徭/招抚——隐户减、农增（×4 口）
    _survey = int(land.get("survey", 0) or 0)
    _back_rate = 0.004 + (0.010 if _survey else 0.0)
    _back = int(hidden * _back_rate)
    if _back > 0:
        _back_people = _back * 4
        _bl = _back_people
        for _p in state.prefectures.values():
            if _bl <= 0:
                break
            _t = min(_bl, max(0, int(_p.get("population", 0) * 0.004)))
            _p["pops"]["农"]["size"] = _p["pops"]["农"].get("size", 0) + _t
            _bl -= _t
        # 尾差强制分配（修复：上限截断致农增 < 隐户减×4——人口凭空少）
        if _bl > 0 and state.prefectures:
            _p0 = next(iter(state.prefectures.values()))
            _p0["pops"]["农"]["size"] = _p0["pops"]["农"].get("size", 0) + _bl
        hidden = max(0, hidden - _back)
        log.append(f"[隐户] {'清丈' if _survey else '招抚'}，{_back:,} 户（{_back_people:,} 口）归籍复业")
    state.land["hidden_households"] = max(0, hidden)


def _settle_emperor_personal(state, log):
    """皇帝个人行动结算（行动矩阵契约 v2）。

    时序：带宽回调 → 自然衰老 → 出京政务减损（远程批奏 -1）→
    出京准备期月度推进（pending_imperial_trip）→ 成行落地（程序基础开销守恒 +
    效果档位落地 + 风险事件）→ 清场（行动/准备/微服计数/旧字段）。
    AI（_emperor_ai 契约 v2）只给 effects 档位词与 risk/narrative；失败走矩阵
    base_effects 程序兜底（不伪造 AI 文本）。费用由程序按行动类型核算，AI 不写数值。
    """
    # 1) 基础回调：上月临时带宽过期（最低 6）
    state.decree_bandwidth = max(6, state.decree_bandwidth - 2)

    # 2) 自然衰老（原有；健康不触发 game over，仅影响衰减/行动）
    if state.year >= 1120:
        natural_decay = 1 + (state.year - 1120) // 2
    else:
        natural_decay = (state.year - 1101) // 4
    if natural_decay > 0:
        state.emperor_health = max(0, state.emperor_health - natural_decay)
        log.append(f"[皇帝] 春秋渐高，龙体自然损耗 {natural_decay}")

    # 3) 公开出京：不影响政务（远程批奏），圣旨带宽仅 -1
    act = state.imperial_action or {}
    if act and act.get("location") == "出京" and act.get("mode") == "公开":
        state.decree_bandwidth = max(5, state.decree_bandwidth - 1)
        log.append("[皇帝] 大驾出京，政务远程批奏，圣旨额度稍减（-1）")

    # 4) 出京准备期月度推进（pending_imperial_trip）
    if getattr(state, "pending_imperial_trip", None) is not None:
        state.pending_imperial_trip["pending_months"] = max(
            0, state.pending_imperial_trip.get("pending_months", 1) - 1)
        if state.pending_imperial_trip.get("pending_months", 0) > 0:
            _left = state.pending_imperial_trip["pending_months"]
            log.append(f"[皇帝] {act.get('action', '出京')}准备中，尚余 {_left} 月")
            state.personal_action = ""
            state.major_policy = ""
            state.imperial_micro_count = 0
            return
        log.append("[皇帝] 銮驾备毕，本月成行")

    # 5) 行动落地（宫里/京城 当月生效；出京准备完成当月成行）
    if act:
        _apply_imperial_action(state, act, log)
    else:
        # 旧档/旧通道兼容：单值 personal_action → 宫里·公开 矩阵行动
        from content.data import LEGACY_PERSONAL_ACTION_MAP
        _legacy = LEGACY_PERSONAL_ACTION_MAP.get(getattr(state, "personal_action", ""))
        if _legacy:
            state.imperial_action = {
                "location": "宫里", "mode": "公开", "action": _legacy,
                "prepared": False, "pending_months": 0, "target": "",
            }
            _apply_imperial_action(state, state.imperial_action, log)
        else:
            # 无行动：龙体自然起伏（原有 idle 漂移）
            state.emperor_health = max(0, min(100,
                state.emperor_health + random.randint(-1, 1)))

    # 6) 清场
    state.imperial_action = {}
    state.pending_imperial_trip = None
    state.personal_action = ""
    state.major_policy = ""
    state.imperial_micro_count = 0


def _imp_split_tier(value):
    """皇帝行动效果档位拆解：'±档位词' → (档位词, 方向 ±1)；数字原样 (值, +1)。"""
    if isinstance(value, (int, float)):
        return str(value), 1.0
    text = str(value).strip()
    direction = 1.0
    if text.startswith("+"):
        text = text[1:]
    elif text.startswith("-"):
        direction = -1.0
        text = text[1:]
    return text, direction


def _imp_tier_delta(dim, tier, direction):
    """档位词 → 数值：prestige/民心走 ai.client_utils 既有换算；
    健康/心情等 0~100 刻度维度用 IMPERIAL_EFFECT_BASE 基准（单一权威源 content.data）。"""
    from content.data import IMPERIAL_EFFECT_BASE
    if dim == "prestige":
        from ai.client_utils import tier_to_value
        return int(round(direction * tier_to_value("prestige", tier, 1.0)))
    if dim == "population_satisfaction":
        from ai.client_utils import tier_to_value
        return int(round(direction * tier_to_value("population_satisfaction", tier, 1.0)))
    base = IMPERIAL_EFFECT_BASE.get(dim, 3.0)
    return int(round(direction * base * TIER_RANGE.get(tier, 0.0)))


def _apply_imperial_action(state, act, log):
    """落地皇帝个人行动：程序基础开销（守恒）→ 效果（AI 档位/矩阵兜底）→ 风险事件。"""
    from content.data import (IMPERIAL_ACTION_MATRIX, IMPERIAL_RISK_PROB,
                              IMPERIAL_EFFECT_DIM)
    from core.events import get_imperial_risk_event
    cell = (IMPERIAL_ACTION_MATRIX.get(act.get("location", ""), {})
                                   .get(act.get("mode", ""), {}).get(act.get("action", "")))
    if not cell:
        log.append("[皇帝] 行止无效（矩阵外），未执行")
        return
    _name = f"{act.get('location', '')}·{act.get('mode', '')}·{act.get('action', '')}"

    # 1) 程序基础开销（守恒：公开→国库 / 微服→内帑；AI 不写数值）
    cost = int(cell.get("base_cost", 0))
    fund = cell.get("fund", "treasury")
    if cost > 0:
        avail = state.treasury if fund == "treasury" else state.imperial_treasury
        paid = min(cost, max(0, int(avail)))
        short = cost - paid
        # 2026-09-18 测试体检修复（货币守恒）：原为裸扣（`change_treasury(-paid)` /
        # `imperial_treasury -= paid`）—— 无对手方，皇帝个人行动的度支凭空消失。
        # 皇帝挥霍/兴造是**宫廷支出**，按"支出回流"口径转入民间（工匠40%/商人60%），
        # 与 `_settle_finance` 常费、`_settle_upkeep` 维持费、国策度支同口径。
        _given = 0
        if paid > 0:
            if fund == "treasury":
                state.change_treasury(-paid)
            else:
                state.imperial_treasury = max(0, state.imperial_treasury - paid)
            try:
                from content.data import GOV_SPEND_TO
                _given = _distribute_cash(state, paid, GOV_SPEND_TO)
            except Exception:            # noqa: BLE001
                _given = 0
            if _given != paid:           # 无接收方兜底：退回国库/内帑，不静默销毁
                _back = paid - _given
                if fund == "treasury":
                    state.change_treasury(_back)
                else:
                    state.imperial_treasury += _back
        _note = f"（府库不足，缺 {short:,} 贯）" if short else ""
        _src = "国库" if fund == "treasury" else "内帑"
        log.append(f"[皇帝] {_name}：{_src}支 {paid:,} 贯{_note}")

    # 2) 效果：矩阵 base_effects（程序兜底）+ AI 契约 v2 档位词（有则覆盖核心 4 键）
    _ai = getattr(state, "_emperor_ai", None)
    ai_eff = _ai.get("effects") if isinstance(_ai, dict) and not _ai.get("_error") else None
    deltas = {}
    for k, v in (cell.get("base_effects") or {}).items():
        if k == "faction_change":
            continue  # 派系单独处理（见落地）
        deltas[k] = v
    if isinstance(ai_eff, dict):
        for k, tier in ai_eff.items():
            dim = IMPERIAL_EFFECT_DIM.get(k)
            if not dim:
                continue
            t, d = _imp_split_tier(tier)
            deltas[dim] = _imp_tier_delta(dim, t, d)   # AI 覆盖 base 的同键
    _apply_imperial_effects(state, deltas, cell, log, _name)

    # 3) 风险事件（risk 档 → 程序概率：低2%/中8%/高20%；时代门槛/史实锚见 events.py）
    risk = cell.get("risk", "低")
    if isinstance(_ai, dict) and not _ai.get("_error") and _ai.get("risk") in IMPERIAL_RISK_PROB:
        risk = _ai["risk"]
    prob = IMPERIAL_RISK_PROB.get(risk, 0.02)
    if random.random() < prob:
        ev = get_imperial_risk_event(state, act)
        if ev:
            _apply_imperial_effects(state, ev.get("effects") or {}, None, log, ev.get("title", "风险事件"))
            _tag = ev.get("label", "合理推演")
            _desc = ev.get("desc", "")
            log.append(f"[风险·{_tag}] {ev.get('title', '')}：{_desc}")
            state.active_events.append({"title": ev.get("title", "风险事件"),
                                        "message": _desc, "label": _tag, "risk": risk})
            state.event_history.append(ev)
            try:
                state.memory.record_event(f"imperial_{ev.get('id', 'risk')}",
                                          ev.get("title", ""), involved=(), turn=state.turn)
            except Exception:
                pass  # 记忆写入失败不阻断结算


def _apply_imperial_effects(state, effects, cell, log, name):
    """效果落地（state_applier 白名单 path：prestige/population_satisfaction/emperor_health/
    art_mastery/taoism_leaning/pleasure_leaning/factions.*.satisfaction/decree_bandwidth）。"""
    if "bandwidth_bonus" in effects:
        state.decree_bandwidth = min(10, state.decree_bandwidth + int(effects["bandwidth_bonus"]))
    if "prestige" in effects:
        d = int(effects["prestige"])
        state.change_prestige(d, name)
        log.append(f"[皇帝] {name}：皇威 {'+' if d >= 0 else ''}{d}")
    if "population_satisfaction" in effects:
        d = int(effects["population_satisfaction"])
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + d))
        log.append(f"[皇帝] {name}：民心 {'+' if d >= 0 else ''}{d}")
    if "emperor_health" in effects:
        d = int(effects["emperor_health"])
        state.emperor_health = max(0, min(100, state.emperor_health + d))
        log.append(f"[皇帝] {name}：龙体 {'+' if d >= 0 else ''}{d}")
    if "pleasure_leaning" in effects:
        d = int(effects["pleasure_leaning"])
        state.pleasure_leaning = max(0, min(100, state.pleasure_leaning + d))
    if "art_mastery" in effects:
        d = int(effects["art_mastery"])
        state.art_mastery = max(0, min(100, state.art_mastery + d))
    if "taoism_leaning" in effects:
        d = int(effects["taoism_leaning"])
        state.taoism_leaning = max(0, min(100, state.taoism_leaning + d))
    if "treasury" in effects:
        d = int(effects["treasury"])
        state.change_treasury(d)   # 风险事件（地方应奉/花石纲等）显式收支，reason 见事件描述
        log.append(f"[皇帝] {name}：国帑 {'+' if d >= 0 else ''}{d:,} 贯")
    if cell and (cell.get("base_effects") or {}).get("faction_change"):
        for fname, d in (cell["base_effects"]["faction_change"] or {}).items():
            if fname in state.factions:
                state.factions[fname]["satisfaction"] = max(0, min(100,
                    state.factions[fname]["satisfaction"] + int(d)))
                log.append(f"[皇帝] {name}：{fname}满意度 {'+' if d >= 0 else ''}{d}")


# ------------------------------------------------------------
# Step 10: 隐藏状态
# ------------------------------------------------------------

def _settle_hidden(state, log):
    """隐藏状态结算（灾害、政令累积效果等）"""
    # 隐户动态（用户指示：隐户是动态人口池，与六类 POP 转换，非静态）——月度逃户/归籍
    try:
        _settle_hidden_pop(state, log)
    except Exception:
        pass
    if state.population_satisfaction < 30:
        if random.random() < 0.15:
            # 审查 P2-21：补下限钳制（其余结算处均已 max(0,…)，此处漏）
            state.population_satisfaction = max(0, state.population_satisfaction - 1)
            log.append("[激变] 民怨沸腾，偶有骚乱")

    jin = state.external["金"]
    if jin.get("invasion_will", 0) >= 90 and state.year >= 1122:
        if random.random() < 0.08:
            from core.army_models import _army_power, _army_power_total, _resolve_battle
            jin["invasion_will"] = 80
            gunpowder = state.tech.get("gunpowder", 20)
            front_routes = ("河北路", "河东路", "陕西路")
            front_units = [u for u in state.army_units if u.station in front_routes]
            my_power = _army_power_total(front_units, gunpowder)
            jin_power = state.external["金"]["power"]
            win, loss_power, breach = _resolve_battle(my_power, jin_power)
            # 按各 unit 战力占比把 loss_power 分摊成真实伤亡（向下取整，余数归主将部）
            casualty = 0
            if my_power > 0 and loss_power > 0 and front_units:
                powers = [_army_power(u, gunpowder) for u in front_units]
                total_p = sum(powers)
                # 总伤亡人数 = 沿线总兵力 × (loss_power/my_power)
                total_troops = sum(u.troops for u in front_units)
                total_cas = int(total_troops * (loss_power / my_power))
                assigned = 0
                # 主将部 = 战力最大的 unit（余数归它）
                main_idx = max(range(len(front_units)), key=lambda i: powers[i])
                for i, u in enumerate(front_units):
                    if i == main_idx:
                        continue
                    part = int(total_cas * (powers[i] / total_p)) if total_p > 0 else 0
                    part = min(part, u.troops)
                    u.add_troops(-part)
                    assigned += part
                rest = min(total_cas - assigned, front_units[main_idx].troops)
                front_units[main_idx].add_troops(-max(0, rest))
                casualty = assigned + max(0, rest)
            if breach:
                for line in ("北线_太原真定", "北线_陕西"):
                    if line in state.defense_lines:
                        f0 = state.defense_lines[line].get("fortification", 0)
                        state.defense_lines[line]["fortification"] = max(0, min(100, int(f0 * 0.5)))
            if win:
                log.append(f"[紧急] 金军大举南下！沿边诸军力战却敌，伤亡约{casualty}人")
            else:
                log.append(f"[紧急] 金军大举南下！沿边诸军败绩，防线告破，伤亡约{casualty}人")
            state._derive_defense_lines()

    if state.pleasure_leaning > 80 and random.random() < 0.05:
        state.emperor_health -= 3

    if state.emperor_health > 0 and random.random() < 0.02:
        state.emperor_health -= 1


