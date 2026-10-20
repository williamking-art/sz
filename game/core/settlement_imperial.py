# -*- coding: utf-8 -*-
"""宋祚 · 皇帝个人与隐藏状态（从 settlement_steps.py 拆出，零行为变更）。

`_settle_emperor_personal` / 帝王行动效果 / `_settle_hidden(_pop)`。"""
from __future__ import annotations

import logging
import random

from content.data import (
    TIER_RANGE,
)

# 🔴 方案乙（2026-10-04 POP 实体下沉州府级）：POP 写入走桥接层；未下沉时回落原写法
from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add
from core.settlement_common import (
    distribute_cash,
)
from content.data_constants import PERSONS_PER_HOUSEHOLD
from core.domains.population.settlement_hidden import (
    ensure_hidden_in_pops, _settle_hidden_pop,
)

_log = logging.getLogger("settlement")

def _hidden_people(p) -> int:
    """某路隐户**口数**（`农` POP 的加法子池 `hidden`；缺键视为 0）。"""
    return max(0, int((((p.get("pops") or {}).get("农")) or {}).get("hidden", 0) or 0))


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
        #
        # 审查 P2-3 / M3 修复（**部分分发后全额退款 = 造币 + 日志谎报**）：
        # 原实现 `except Exception: _given = 0` → 退 `paid - 0` **全额**回国库/内帑，
        # 而 `distribute_cash`（旧名 `_distribute_cash`）是边算边写各 POP `wealth` 的（非原子）——先入账的 POP
        # 留下、国库又全退 ⇒ 净扣 0 而民间多钱（ΣΔ>0，凭空造币）；随后日志仍写
        # 「支 {paid} 贯」把没花出去的钱说成花出去了。
        # 现口径：① `distribute_cash` 两阶段（构造完才写，异常时零写入）；
        #          ② 退款额用**实际已分发额**（`_applied` 逐笔累加，不信任"0"）；
        #          ③ 日志打印**实扣额**（= 已分发额），异常另补一行可见说明＋traceback。
        _applied = []
        _given = 0
        _dist_err = None
        if paid > 0:
            if fund == "treasury":
                state.change_treasury(-paid)
            else:
                state.imperial_treasury = max(0, state.imperial_treasury - paid)
            try:
                from content.data import GOV_SPEND_TO
                _given = distribute_cash(state, paid, GOV_SPEND_TO, applied=_applied)
            except Exception as e:            # noqa: BLE001 — 必须可见，且按实际已分发额退款
                _given = sum(_applied)        # ← 实际已分发额（不得按 0 全额退）
                _dist_err = e
                logging.getLogger("settlement").exception(
                    "[皇帝] %s：宫廷支出分发异常（已分发 %s/%s 贯，按实际额退款）",
                    _name, _given, paid)
                log.append(f"[皇帝][WARN] {_name}：支出发放异常，仅按已分发额记账"
                           f"（{type(e).__name__}）")
            if _given != paid:           # 无接收方/异常兜底：退回未分发部分，不静默销毁
                _back = paid - _given
                if fund == "treasury":
                    state.change_treasury(_back)
                else:
                    state.imperial_treasury += _back
        _actual = _given                          # 实扣额 = 实际分发额（自洽，非请求额）
        _note = f"（府库不足，缺 {short:,} 贯）" if short else ""
        # 未散出部分与实扣额写在**同一行**：`flow_summary._extract_one_off` 取该行
        # 第一个「数字+贯」，若另起一行会被当成第二笔「皇帝行止」支出（面板双计）。
        if _dist_err is not None and _actual < paid:
            _note += f"（{paid - _actual:,} 贯未散出，已退回国库/内帑）"
        _src = "国库" if fund == "treasury" else "内帑"
        # 日志金额 == **实扣额**（审查 P2-3 验收断言）：分发出错时不得仍写请求额。
        log.append(f"[皇帝] {_name}：{_src}支 {_actual:,} 贯{_note}")

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
                pass  # 记忆知识库写入失败属纯增强，无状态风险（设计豁免，保留不留痕）


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
    """隐藏状态结算。本函数已降为**薄编排**：三段逻辑已按域拆开（2026-10-07 用户裁定「拆开」），

    调用顺序 a→b→c→d **与拆分前完全一致**（策略规则：结算步序是玩法规则，不得调整）。

    a) 隐户归籍 + b) 民怨骚乱 → core.domains.population.settlement_hidden
    c) 金军南侵             → core.domains.military.settlement_front
    d) 皇帝健康衰减         → core.domains.politics.settlement_imperial
    """
    from core.domains.military.settlement_front import _settle_front_battle
    from core.domains.politics.settlement_imperial import _settle_emperor_health_decay

    # a) 隐户归籍（失败必须可见：记入结算日志）
    try:
        _settle_hidden_pop(state, log)
    except Exception as e:  # noqa: BLE001 — 已改为记入结算日志（失败可见）
        _log.exception("[归籍] 隐户结算失败（本月未归籍，POP 未变）")
        log.append("[归籍] 隐户归籍结算失败，本月未归籍（POP 未变）"
                   f"（{type(e).__name__}）")

    # b) 民怨骚乱
    if state.population_satisfaction < 30:
        if random.random() < 0.15:
            # 审查 P2-21：补下限钳制（其余结算处均已 max(0,…)，此处漏）
            state.population_satisfaction = max(0, state.population_satisfaction - 1)
            log.append("[激变] 民怨沸腾，偶有骚乱")

    # c) 金军南侵
    _settle_front_battle(state, log)

    # d) 皇帝健康衰减
    _settle_emperor_health_decay(state, log)


