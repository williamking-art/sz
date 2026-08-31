# -*- coding: utf-8 -*-
"""宋祚 · Agent 路由层（core/agent_router.py）

按需唤醒：定义每个 Agent 的唤醒条件（关键词 / 状态触发 / 上一轮 diff 路径），
route_agents 返回需要唤醒的 Agent 列表；game loop 只调用被唤醒的 Agent，
未唤醒的不消耗任何 token。narrative Agent 始终唤醒但 token 预算极低。

执行顺序（前面的 Agent 变更注入后面 Agent 的 prompt 作为 cumulative_diff）：
    diplomacy → finance → military → narrative
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger("agent_router")

# ---------------------------------------------------------------------------
# Agent 注册表（融合游戏本体：字段/契约方法/结算步与现有实现对齐）
# ---------------------------------------------------------------------------
AGENT_DEFS: Dict[str, dict] = {
    "diplomacy": {
        "order": 1,
        "method": "diplomacy_decide",       # ai/client.py 契约方法
        "settle_attr": "_diplomacy_ai",     # 注入 state 的槽位
        "wake_keywords": ["外交", "辽", "金", "西夏", "岁币", "盟", "和战", "使"],
        "wake_state": [("external", lambda v: isinstance(v, dict) and bool(v))],
        "wake_diff_paths": ["external.", "diplomacy."],
        "domain_fields": ["external_jin", "external_liao", "external_xixia",
                          "sui_gong", "alliance_jin_liao"],
    },
    "finance": {
        "order": 2,
        "method": "finance_decide",
        "settle_attr": "_finance_ai",
        "wake_keywords": ["税", "银", "钱", "开支", "岁入", "商", "盐", "市舶",
                          "折色", "役钱", "粮价", "交子", "钱荒"],
        "wake_state": [("treasury", lambda v: isinstance(v, (int, float)) and v < 0)],
        "wake_diff_paths": ["treasury", "tax_breakdown.", "prefectures.*.tax"],
        "domain_fields": ["treasury", "imperial_treasury", "tax_breakdown",
                          "commerce_tax_rate"],
    },
    "military": {
        "order": 3,
        "method": "military_decide",
        "settle_attr": "_military_ai",
        "wake_keywords": ["军", "兵", "战", "边", "守", "攻", "戍", "营", "将"],
        # T3 修复：真实军情唤醒——军队士气/训练低落 或 敌军入侵/战事事件（原 `if False else False` 恒 False 调试残留）
        "wake_state": [
            ("army_units", lambda v: isinstance(v, list) and bool(v)
             and any(getattr(u, "morale", 50) < 30 or getattr(u, "training", 50) < 20
                     for u in v)),
            ("active_events", lambda v: isinstance(v, list)
             and any(("入侵" in str(e.get("category", "")) or "战" in str(e.get("category", ""))
                      or "围城" in str(e.get("category", "")))
                     for e in v)),
        ],
        "wake_diff_paths": ["army_units.", "defense_lines.", "military."],
        "domain_fields": ["army", "training", "morale", "defense_bonus",
                          "fortification"],
    },
    "relief": {
        "order": 4,
        "method": "relief_decide",
        "settle_attr": "_relief_ai",
        "wake_keywords": ["灾", "赈", "饥", "荒", "流民", "疫", "旱", "水"],
        # T3 修复：真实灾荒唤醒——灾荒类事件 / disaster_severity>0 / 流民池 refugees 异常
        # （原依赖不存在的 state.disaster → 恒 None → 永不唤醒）
        "wake_state": [
            ("active_events", lambda v: isinstance(v, list)
             and any(("灾" in str(e.get("category", "")) or "荒" in str(e.get("category", ""))
                      or "疫" in str(e.get("category", "")))
                     for e in v)),
            ("disaster_severity", lambda v: isinstance(v, (int, float)) and v > 0),
            ("prefectures", lambda v: isinstance(v, dict)
             and any(p.get("refugees", 0) > 8000 for p in v.values())),
        ],
        "wake_diff_paths": ["disaster.", "prefectures.*.unrest", "refugee"],
        "domain_fields": ["relief", "refugee", "disaster"],
    },
    "economy": {
        "order": 5,
        "method": "economy_decide",
        "settle_attr": "_economy_ai",
        "wake_keywords": ["经济", "景气", "民生", "物价", "生产", "窖银", "科举"],
        "wake_state": [],  # 经济 Agent 月度必醒（核心推演）
        "wake_diff_paths": [],
        "domain_fields": ["景气", "士绅", "生产", "窖银", "城市化", "科举",
                          "jiaozi_trust", "shortage", "maritime", "bank", "price_trend"],
        "always": True,   # 经济为核心推演，始终唤醒
    },
    "narrative": {
        "order": 6,
        "method": "monthly_report",
        "settle_attr": None,
        "wake_keywords": [],
        "wake_state": [],
        "wake_diff_paths": [],
        "domain_fields": [],
        "always": True,   # 始终唤醒，但 token 预算极低（只填模板，不调 AI 或极短）
        "low_token": True,
    },
}

_state_of = None  # 模块级引用（状态触发用），避免在默认参数里引用


def _wake_by_keywords(agent_def: dict, player_input: str) -> bool:
    kws = agent_def.get("wake_keywords", [])
    if not kws or not player_input:
        return False
    return any(k in player_input for k in kws)


def _wake_by_state(agent_def: dict, state) -> bool:
    for path, pred in agent_def.get("wake_state", []):
        try:
            val = getattr(state, path, None)
            if pred(val):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _wake_by_diff(agent_def: dict, last_diff: Optional[dict]) -> bool:
    if not last_diff:
        return False
    diffs = last_diff.get("changes") or last_diff.get("applied") or []
    paths = agent_def.get("wake_diff_paths", [])
    if not paths:
        return False
    for d in diffs:
        p = d.get("path", "") if isinstance(d, dict) else str(d)
        if any(p.startswith(prefix) for prefix in paths):
            return True
    return False


def route_agents(player_input: str = "", state=None,
                 last_diff: Optional[dict] = None) -> List[str]:
    """返回需要唤醒的 Agent id 列表（按 order 排序）。

    - 关键词匹配（player_input 含领域词）
    - 状态触发（如 treasury < 0 → finance）
    - 上一轮 diff 包含该 Agent 关注的路径
    - always=True 始终唤醒（economy 核心 / narrative 低 token）
    """
    global _state_of
    _state_of = state
    woken = []
    for aid, adef in sorted(AGENT_DEFS.items(), key=lambda kv: kv[1]["order"]):
        if adef.get("always"):
            woken.append(aid)
            continue
        if _wake_by_keywords(adef, player_input):
            woken.append(aid)
            continue
        if state is not None and _wake_by_state(adef, state):
            woken.append(aid)
            continue
        if _wake_by_diff(adef, last_diff):
            woken.append(aid)
            continue
    # 确保 narrative 始终最后（低 token 模板）
    if "narrative" in woken and woken[-1] != "narrative":
        woken.remove("narrative")
        woken.append("narrative")
    return woken


# ---------------------------------------------------------------------------
# 与 game loop 融合：按需注入 Agent 契约（供 settle_turn 调用）
# ---------------------------------------------------------------------------
def inject_woken_agents(state, ai_client, woken: List[str]) -> List[str]:
    """只调用被唤醒的 Agent，注入 state._xxx_ai 槽位（未唤醒不消耗 token）。
    返回实际注入成功的 Agent id 列表。

    T8 推演分级（不伪造 + 明确失败信号）：被唤醒的推演 Agent 失败 → **记入
    state._ai_failures**（明确失败清单：{agent, error}），不注入假槽位、不静默；
    economy 为强制核心推演，其失败由调用方（settle_turn/_ai_prelude）拒绝式处理。
    """
    injected = []
    failures = getattr(state, "_ai_failures", None)
    if failures is None:
        failures = []
        state._ai_failures = failures
    for aid in woken:
        adef = AGENT_DEFS.get(aid)
        if not adef:
            continue
        method = adef.get("method")
        attr = adef.get("settle_attr")
        if not method or not attr:
            continue  # narrative 无 settle_attr，跳过（月报另行）
        try:
            r = getattr(ai_client, method)(state.posture, state=state)
            if isinstance(r, dict) and not r.get("_error"):
                setattr(state, attr, r)
                injected.append(aid)
            else:
                # 契约失败/返回错误标记：明确记录，不伪造槽位
                failures.append({"agent": aid, "method": method,
                                 "error": "contract_failed"})
                log.warning("Agent %s 契约失败: %r", aid, r)
        except Exception as e:  # noqa: BLE001
            failures.append({"agent": aid, "method": method,
                             "error": f"{type(e).__name__}: {e}"})
            log.warning("Agent %s 唤醒失败: %s", aid, e)
    return injected
