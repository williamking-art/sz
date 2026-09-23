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
        # 审查 P2-36（登记，未停用）：结算侧暂无消费者（_settle_finance 不读 _finance_ai）
        # → 唤醒结果会被丢弃（白烧 token）。接线需先设计消费语义，见 PENDING_CONTRACTS。
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
    # ---- 审查 P2-35 接线：以下契约**结算侧已消费**（settlement_steps/settlement 读取槽位），
    #      但原先无生产者（getattr 恒 None → 永久走本地兜底）。接入后按需唤醒——
    #      平时零 token，命中条件才推演并注入，两侧一致。----
    "decree_execute": {
        "order": 7,
        "method": "decree_execute_decide",
        "settle_attr": "_decree_execute_ai",
        "wake_keywords": ["诏", "旨", "敕", "令", "推行", "申饬"],
        "wake_state": [("pending_decrees", lambda v: isinstance(v, list) and bool(v))],
        "wake_diff_paths": ["pending_decrees.", "active_decrees."],
        "domain_fields": ["decree_execution", "implementation"],
    },
    "survey": {
        "order": 8,
        "method": "survey_settle",
        "settle_attr": "_survey_ai",
        "wake_keywords": ["清丈", "田亩", "隐田", "隐户", "括田"],
        "wake_state": [],
        "wake_diff_paths": ["land."],
        "domain_fields": ["land_survey", "hidden_land"],
    },
    "faction": {
        "order": 9,
        "method": "faction_decide",
        "settle_attr": "_faction_ai",
        "wake_keywords": ["党", "派系", "党争", "元祐", "新党", "旧党"],
        "wake_state": [("factions", lambda v: isinstance(v, dict) and any(
            int((f or {}).get("satisfaction", 50)) < 40 for f in v.values()))],
        "wake_diff_paths": ["factions."],
        "domain_fields": ["faction_stances", "party_strife"],
    },
    "land_local": {
        "order": 10,
        "method": "land_local_decide",
        "settle_attr": "_land_local_ai",
        "wake_keywords": ["田", "州县", "赋役", "劝农", "垦"],
        "wake_state": [],
        "wake_diff_paths": ["land.", "prefectures."],
        "domain_fields": ["land", "local_governance"],
    },
    "granary": {
        "order": 11,
        "method": "granary_decide",
        "settle_attr": "_granary_ai",
        "wake_keywords": ["仓", "漕运", "常平", "粮", "太仓", "转般"],
        "wake_state": [],
        "wake_diff_paths": ["granary", "granary_stats."],
        "domain_fields": ["granary", "canal"],
    },
}

#: 结算侧已预留、但**契约方法尚不存在**的 AI 槽位（审查 P2-35 登记）：
#: 接线步骤 = 补 AIClient 契约方法 → 从本表移除 → 加进 AGENT_DEFS（wired 默认 True）。
#: 接线前对应 getattr 分支恒走本地兜底（等价扩展挂点，非缺陷）。
PENDING_CONTRACTS = (
    ("_reform_ai", "reform_decide", "core/settlement.py::_apply_reform"),
    # 反向不一致（有生产者无消费者）：唤醒会消耗 token 但结果被丢弃；接线需先设计消费语义
    ("_finance_ai", "finance_decide", "core/settlement_steps.py::_settle_finance（未消费）"),
    # 半接线：结算侧已有消费者（settle_investments），但落地入口 invest() 无生产调用方
    ("_invest_ai", "invest_decide", "core/estate_mechanic.py::invest（无调用方）"),
)

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


def _path_matches(path: str, pattern: str) -> bool:
    """diff 路径与唤醒模式匹配（审查 P2-37：支持段级 * 通配 + 前缀）。

    - `external.` / `army_units.` 等尾点模式 → 前缀匹配；
    - `prefectures.*.tax` 等含 * 模式 → 逐段匹配（path 允许更长，如
      `prefectures.两浙路.tax` 命中，`prefectures.两浙路.pops.农.wealth` 不命中）；
    - 无通配无尾点 → 前缀匹配。
    """
    if not path or not pattern:
        return False
    if pattern == path:
        return True
    if pattern.endswith("."):
        return path.startswith(pattern)
    if "*" not in pattern:
        return path.startswith(pattern)
    p_parts, w_parts = path.split("."), pattern.split(".")
    if len(p_parts) < len(w_parts):
        return False
    return all(w == "*" or w == p for w, p in zip(w_parts, p_parts))


def _wake_by_diff(agent_def: dict, last_diff: Optional[dict]) -> bool:
    if not last_diff:
        return False
    diffs = last_diff.get("changes") or last_diff.get("applied") or []
    paths = agent_def.get("wake_diff_paths", [])
    if not paths:
        return False
    for d in diffs:
        p = d.get("path", "") if isinstance(d, dict) else str(d)
        if any(_path_matches(p, pattern) for pattern in paths):
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
    woken = []
    for aid, adef in sorted(AGENT_DEFS.items(), key=lambda kv: kv[1]["order"]):
        if adef.get("wired") is False:
            continue  # 审查 P2-36：契约未接线（结算侧不消费）→ 不唤醒，避免白烧 token
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
def _inject_one(state, ai_client, failures: list, aid: str) -> Optional[str]:
    """单个 agent 的注入（强并发的单元，2026-09-21「民间情况先行」首段并发化）。

    并发安全性（逐一核对过）：
      · AIClient 的 provider 栈是 `threading.local()`（ai/client.py:213-244——每线程
        独立 push/pop）→ 多线程各自进入/退出 provider 的行为互不串扰；
      · 各 agent 只写**自己**的 `settle_attr` 槽位（对 state 不同字段赋值）；
      · `failures.append`（list）单次 append 在 CPython 下原子；
    失败语义不变：单 agent 失败照旧记入 failures，不影响他 agent 与结算。
    """
    adef = AGENT_DEFS.get(aid)
    if not adef or adef.get("wired") is False:
        return None
    method = adef.get("method")
    attr = adef.get("settle_attr")
    if not method or not attr:
        return None                                    # narrative 无 settle_attr，跳过
    # economy 由调用方强制前置推演并写入 _economy_ai（P1-11），此处跳过防双倍 token。
    if attr == "_economy_ai" and getattr(state, "_economy_ai", None):
        return None
    try:
        try:
            r = getattr(ai_client, method)(state.posture, state=state)
        except TypeError:
            # 兼容旧签名契约（如 survey_settle(posture) 无 state 形参）
            r = getattr(ai_client, method)(state.posture)
    except Exception as e:  # noqa: BLE001
        failures.append({"agent": aid, "method": method,
                         "error": f"{type(e).__name__}: {e}"})
        log.warning("Agent %s 唤醒失败: %s", aid, e)
        return None
    if isinstance(r, dict) and not r.get("_error"):
        setattr(state, attr, r)
        return aid
    failures.append({"agent": aid, "method": method, "error": "contract_failed"})
    log.warning("Agent %s 契约失败: %r", aid, r)
    return None


def inject_woken_agents(state, ai_client, woken: List[str]) -> List[str]:
    """只调用被唤醒的 Agent，注入 state._xxx_ai 槽位（未唤醒不消耗 token）。
    返回实际注入成功的 Agent id 列表。

    T8 推演分级（不伪造 + 明确失败信号）：被唤醒的推演 Agent 失败 → **记入
    state._ai_failures**（明确失败清单：{agent, error}），不注入假槽位、不静默；
    economy 为强制核心推演，其失败由调用方（settle_turn/_ai_prelude）拒绝式处理。

    **并发注入（2026-09-21，两段式首段提速）**：≥2 个唤醒 agent 时用线程池并发推演
    （每个 agent 独立网络往返 ~7s，串行为首段耗时主因；并发后首段 ≈ max(单路)）。
    单个唤醒 → 串行照旧（零额外开销）；economy 仍由调用方前置（并发只发被唤醒的其余 agent）。
    """
    failures = getattr(state, "_ai_failures", None)
    if failures is None:
        failures = []
        state._ai_failures = failures

    # economy 双引擎防覆盖（原逻辑原样保留）：调用方已注入 → 此处跳过
    usable = []
    for aid in woken:
        adef = AGENT_DEFS.get(aid)
        if not adef or adef.get("wired") is False:
            continue
        attr = adef.get("settle_attr")
        if attr == "_economy_ai" and getattr(state, "_economy_ai", None):
            continue
        usable.append(aid)

    if len(usable) <= 1:
        injected = []
        for aid in usable:
            r = _inject_one(state, ai_client, failures, aid)
            if r:
                injected.append(r)
        return injected

    from concurrent.futures import ThreadPoolExecutor
    # 每线程独立 provider 栈（threading.local，ai/client.py:213-244）+ 各 agent
    # 只写自己的 settle_attr → 并发安全；失败按 agent 记入 state._ai_failures。
    injected: list = []
    with ThreadPoolExecutor(max_workers=min(4, len(usable)),
                            thread_name_prefix="agent-inject") as pool:
        futs = [pool.submit(_inject_one, state, ai_client, failures, aid)
                for aid in usable]
        for f in futs:
            r = f.result() or None
            if r:
                injected.append(r)
    return injected
