# -*- coding: utf-8 -*-
"""宋祚 · 与 UI 无关的游戏命令层

把"可玩逻辑"（颁诏、召见、施政、个人行动、回合结算、事件、结局）
从界面层抽离出来，供 GUI 版(ui/gui.py)使用，保证游戏逻辑只有单一来源。
"""
import random

from content.data import (
    FACTION_NAMES, PERSONAL_ACTIONS, MAJOR_POLICIES, get_prestige_level,
    desensitize_satisfaction,
    desensitize_trust, desensitize_shortage, desensitize_talent, desensitize_tech,
)

from core.game_state import GameState, _next_month
from core.settlement import run_monthly_settlement
from core.save_load import save_game, load_game, get_save_slots
from core.evaluation import evaluate_game, check_game_over
from core.events import get_historical_event, get_random_event, apply_event_choice, get_strategic_branch, get_pending_break_event
from core.errors import AIRuntimeError


# ============================================================
# 新游戏 / 难度
# ============================================================

from core.commands_decree import (
    _apply_rename, _draft_to_effects_dict, _enqueue, _generate_decree_effects, _random_faction_stances, _rule_draft, _run_fixed, confirm_timeline_break, dismiss_pending_break, issue_decree, issue_drafted_decree, issue_edict_from_review, issue_free_decree, issue_kouyu, issue_secret_decree, merge_drafts, preview_draft, reject_edict_draft,
)


def new_game(difficulty: str = "史实", ai_client=None) -> GameState:
    """创建新游戏（含记忆知识库开局基线：大臣/机构/派系实体）。"""
    state = GameState(difficulty=difficulty)
    # 记忆基线（Phase 3a）：图谱存史——开局录大臣/派系/机构/外部政权实体
    try:
        g = state.memory
        from content.ministers.data import MINISTERS, CENTRAL_ORG_INFO
        from content.data import FACTION_NAMES, EXTERNAL_FORCES
        for name in MINISTERS:
            fig = MINISTERS[name]
            g.add_entity(f"minister_{name}", "minister", name,
                         {"faction": fig.get("faction", ""), "role": fig.get("role", "")}, turn=0)
        for fn in FACTION_NAMES:
            g.add_entity(f"faction_{fn}", "institution", fn, turn=0)
        for org in CENTRAL_ORG_INFO:
            g.add_entity(f"org_{org}", "org", org, turn=0)
        for ext in EXTERNAL_FORCES:
            g.add_entity(f"external_{ext}", "external_power", ext, turn=0)
            g.add_relation(f"external_{ext}", "宋", "stance", weight=1.0, turn=0, note="邦交")
    except Exception:
        pass  # 记忆基线失败不阻断开局
    return state


# ============================================================
# 召见大臣
# ============================================================
def audience_minister(state: GameState, leader: str, action: str = "安抚", ai_client=None) -> str:
    """召见大臣并施行一项行动，返回叙述文本"""
    faction = [n for n, f in state.factions.items() if f["leader"] == leader][0]
    f = state.factions[faction]
    # 行动效果
    if action == "安抚":
        f["satisfaction"] = max(0, min(100, f["satisfaction"] + 4))
        msg = f"{leader}心甚慰，对陛下更忠恳了。"
    elif action == "施恩":
        f["satisfaction"] = max(0, min(100, f["satisfaction"] + 7))
        f["influence"] = max(0, min(100, f["influence"] + 2))
        state.treasury -= 200000
        msg = f"厚赏之下，{leader}感念隆恩，然国库耗银二十万贯。"
    elif action == "试探":
        f["satisfaction"] = max(0, min(100, f["satisfaction"] - 2))
        msg = f"陛下言语敲打，{leader}神情微变，似有戒心。"
    elif action == "调拨军权":
        f["influence"] = max(0, min(100, f["influence"] + 3))
        msg = f"{leader}得掌兵柄，权势更盛。"
    else:
        msg = f"与{leader}闲谈而已。"
    # AI 建言（若启用；失败 → 本地模板兜底，不阻断）
    if ai_client and ai_client.available:
        try:
            advice_raw = ai_client.advice(state.posture, faction)
            advice = str(advice_raw.get("advice") or "") if isinstance(advice_raw, dict) else str(advice_raw or "")
            msg += f"\n〔{leader}奏曰〕{advice}"
        except Exception:
            from ai.narrative_fallback import fallback_advice
            advice = str(fallback_advice(state.turn).get("advice") or "")
            msg += f"\n〔{leader}奏曰〕{advice}"
    return msg


# ============================================================
# 下旨颁诏 / 皇帝个人行动矩阵（契约 v2）
# ============================================================
def choose_imperial_action(state: GameState, location: str, mode: str, action: str,
                           target: str = "", prepared: bool = False) -> str:
    """皇帝个人行动矩阵（契约 v2）：按 location×mode 限定 action 白名单（跨格子非法），
    时代门槛 / 微服京城每月 1 次由程序限制；出京准备期入 pending_imperial_trip 月度推进。
    state.imperial_action = {location, mode, action, prepared, pending_months, target}。
    """
    from content.data import (IMPERIAL_ACTION_MATRIX, IMPERIAL_LOCATIONS, IMPERIAL_MODES,
                              imperial_prep_months)
    if location not in IMPERIAL_LOCATIONS:
        return "行止地点非法。"
    if mode not in IMPERIAL_MODES:
        return "行止方式非法。"
    cell = IMPERIAL_ACTION_MATRIX.get(location, {}).get(mode, {}).get(action)
    if not cell:
        return f"「{location}·{mode}·{action}」不在行动矩阵白名单内（跨格子非法）。"
    # 时代门槛（艮岳 1117 / 延福宫 1113 / 上清宝箓宫 1117 / 东幸镇江 1126）
    gate = cell.get("era_gate")
    if gate is not None and state.year < gate:
        return f"「{action}」未至该时代（{gate} 年起方可行），不可行此行动。"
    # 出京准备中不可另定行动
    if getattr(state, "pending_imperial_trip", None) is not None:
        return "大驾出京准备中，须待成行后再定个人行止。"
    # 微服京城每月 1 次（程序限，按回合计数；结算月末归零）
    if cell.get("micro_once") and getattr(state, "imperial_micro_count", 0) >= 1:
        return "陛下本月已微服出宫，只可一次，请下月再行。"
    prep = imperial_prep_months(location, mode, action, prepared=prepared, target=target)
    state.imperial_action = {
        "location": location, "mode": mode, "action": action,
        "prepared": bool(prepared), "pending_months": prep, "target": str(target or ""),
    }
    if cell.get("micro_once"):
        state.imperial_micro_count += 1
    if prep > 0:
        state.pending_imperial_trip = state.imperial_action
        return f"已定行止：{location}·{mode}·{action}（出京准备 {prep} 月，月度推进）。"
    return f"本回合个人行止：{location}·{mode}·{action} — {cell.get('desc', '')}"


def do_personal_action(state: GameState, name: str) -> str:
    """旧单值个人行动通道（UI/后端兼容）：映射到 宫里·公开 矩阵行动。"""
    from content.data import PERSONAL_ACTIONS, LEGACY_PERSONAL_ACTION_MAP
    if name not in PERSONAL_ACTIONS:
        return "无此行动。"
    mapped = LEGACY_PERSONAL_ACTION_MAP.get(name)
    if not mapped:
        return "无此行动。"
    return choose_imperial_action(state, "宫里", "公开", mapped)


def choose_major_policy(state: GameState, policy: str) -> str:
    if policy not in MAJOR_POLICIES:
        return "无此大项。"
    state.major_policy = policy
    return f"已定施政大项：「{policy}」"


# ============================================================
# 回合推进 / 结算（返回日志与触发事件）
# ============================================================
def advance_month(state: GameState) -> list:
    """触发当月事件。返回本回合需要玩家处理的事件列表。

    月份与回合推进统一在 settle_turn 的月度结算之后完成，避免一回合重复计数。
    """
    # 事件触发随机纳入确定性种子（与 run_monthly_settlement 同源），使同回合可复现，
    # 便于 dev/replay 回放与平衡 A/B 对比；不污染全局 random 后续调用。
    # 注意：不可用 hash()（Python 哈希随机化导致跨进程不一致），改用确定性多项式。
    import random as _rnd
    _seed = (state.year * 1000003 + state.month * 10007 + state.turn * 131) & 0xFFFFFFFF
    _rnd.seed(_seed)
    # 触发事件优先级：
    #   1) 待确认改写位奏章（战略决策点·朱批）——最高优先，让玩家主动拍板改写历史
    #   2) 已确认改写位的分支事件
    #   3) 史实事件
    #   4) 随机事件
    ev = get_pending_break_event(state)
    if not ev:
        ev = get_strategic_branch(state)
    if not ev:
        ev = get_historical_event(state.year, state.month)
    if not ev:
        ev = get_random_event()
    events = []
    if ev:
        events.append(ev)
        state.active_events.append({"title": ev.get("title", "事件"), "message": ev.get("desc", "")})
    if check_game_over(state):
        state.game_over = True
    return events


# ============================================================
# 统一拟旨（圣旨 / 密旨）— AI 解析结果落地
# ============================================================
def settle_turn(state: GameState, ai_client=None) -> tuple:
    """执行月度结算，返回 (log, ai_report)。行为与拆分前完全一致：

    AI 推演族（economy 强制 + 按需唤醒注入）→ 本地 12 步结算 → 月报 → 终局/自动存档。
    全游戏级强制 AI（用户定稿）：AI 缺失/推演失败 → **拒绝式**（抛 AIRuntimeError，
    不静默兜底、不伪造景气/城市化/科举档位）；结算不进行，由上层提示配置 OpenAI 兼容 API。
    月份/年份的推进已收敛到 run_monthly_settlement 内部（与 Rust 后端 settle.rs 的
    推进位置保持一致）。
    """
    from content.data import AI_ERROR_CODES
    # AI 经济推演（景气/士绅囤粮/生产）须在结算之前注入，本月生效（结算内读 _economy_ai）
    if not (ai_client and getattr(ai_client, "available", False)):
        raise AIRuntimeError(AI_ERROR_CODES.get("AI_NOT_CONFIGURED", "AI 未接入"))
    _ai_prelude(state, ai_client)
    log = settle_local(state)
    report = ""
    # 月报为装饰性 AI 文本：失败 → 本地模板兜底（T8 分级降级，体验韧性；
    # 模板只影响叙事呈现，结算已就地发生，勿误判"未推进"而重复结算）
    try:
        report = _monthly_report_text(state, ai_client)
    except Exception:
        from ai.narrative_fallback import fallback_report
        report = str(fallback_report(state=state).get("report") or "")
    finish_turn(state)
    return log, report


def _ai_prelude(state, ai_client):
    """结算前 AI 推演族（同步版）：economy 强制推演 + 按需唤醒注入，写 state 槽位。

    economy 缺失/失败 → **拒绝式**（抛 AIRuntimeError，不静默兜底、不伪造档位）；
    其余唤醒契约失败仅跳过（settle 读不到槽位走本地兜底，不阻断结算）。
    """
    from content.data import AI_ERROR_CODES
    try:
        eco = ai_client.economy_decide(state.posture)
    except Exception as e:
        raise AIRuntimeError(f"经济推演失败（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    if not isinstance(eco, dict) or eco.get("_error"):
        raise AIRuntimeError(AI_ERROR_CODES.get("AI_CONTRACT_FAILED", "AI 输出不满足契约"))
    state._economy_ai = eco
    # 12 步 agent 化：按需唤醒注入（route_agents 结合关键词/状态触发/上轮 diff；
    # 未唤醒的 Agent 不消耗任何 token；economy 始终唤醒为核心推演）
    try:
        from core.agent_router import route_agents, inject_woken_agents
        # 玩家本回合政令摘要（作为关键词路由输入；无则空）
        _player_hint = ""
        try:
            _decs = getattr(state, "pending_decrees", []) or []
            _player_hint = " ".join(
                str(d.get("title", "")) for d in _decs[-3:])
        except Exception:
            _player_hint = ""
        # 上轮结算 diff（供路径唤醒；无则空）
        _last_diff = getattr(state, "_last_agent_diff", None)
        _woken = route_agents(_player_hint, state, _last_diff)
        inject_woken_agents(state, ai_client, _woken)
    except Exception:
        # 路由失败回退：P1 三契约保底注入（不阻断结算）
        for _attr, _call in (("_diplomacy_ai", "diplomacy_decide"),
                             ("_military_ai", "military_decide"),
                             ("_relief_ai", "relief_decide")):
            try:
                _r = getattr(ai_client, _call)(state.posture, state=state)
                if isinstance(_r, dict) and not _r.get("_error"):
                    setattr(state, _attr, _r)
            except Exception:
                pass
    # 皇帝个人行动推演（契约 v2）：玩家已定行止（imperial_action）或旧档有 personal_action 时，
    # AI 推演 effects/risk/narrative（跨格子非法由契约 validate 拒绝式拦截）；失败 → 跳过，
    # 结算走矩阵 base_effects 程序兜底（非经济契约不阻断结算、不伪造 AI 文本）。
    try:
        if getattr(state, "imperial_action", None) or getattr(state, "personal_action", ""):
            _ea = ai_client.emperor_personal_decide(state.posture, state=state)
            if isinstance(_ea, dict) and not _ea.get("_error"):
                state._emperor_ai = _ea
    except Exception:
        pass


def settle_local(state) -> list:
    """本地 12 步结算（确定性，主线程执行）：委托 run_monthly_settlement（含回合推进）。

    不含终局判定/自动存档（由 finish_turn 统一收尾），供同步 settle_turn 与
    T6 异步拆分（后台 AI 推演族 → 主线程本函数 → 叙事后补）共用。
    """
    return run_monthly_settlement(state)


def finish_turn(state) -> None:
    """结算收尾（主线程）：终局判定 + 记忆库压缩/总结/落盘 + 对话记忆库每 3 回合总结去重。"""
    import logging as _lg
    _flog = _lg.getLogger("finish_turn")
    if check_game_over(state):
        state.game_over = True
    # 主记忆库（审查 P1-5 修复接线）：每 6 回合压缩、每 12 回合周期总结（不动旧数据）
    try:
        mg = state.memory
        mg.turn = state.turn
        if state.turn > 0 and state.turn % 6 == 0:
            mg.compress(state.turn)
        if state.turn > 0 and state.turn % 12 == 0:
            mg.summarize_period(state.turn)
    except Exception as e:  # noqa: BLE001
        _flog.warning("记忆库压缩/总结失败（不阻断结算）：%s", e)
    # 对话记忆库：每 3 回合总结去重（防记忆漂移/膨胀；不动旧数据）
    try:
        from memory.dialogue_memory import get_dialogue_memory
        dm = get_dialogue_memory(state)
        dm.turn = state.turn
        if state.turn % 3 == 0:
            dm.summarize_dialogues(state.turn)
    except Exception as e:  # noqa: BLE001
        _flog.warning("对话总结失败（不阻断结算）：%s", e)
    # 审查 P1-5/P2-2 修复：每回合落盘记忆库（防中途崩溃丢失；失败记日志而非静默吞）
    try:
        mg = state.memory
        _slot = getattr(mg, "_slot", None) or getattr(state, "memory_slot", None)
        if _slot is not None:
            ok = mg.save(_slot)
            if not ok:
                _flog.warning("记忆库写盘失败（slot=%s），本轮记忆未持久化", _slot)
    except Exception as e:  # noqa: BLE001
        _flog.warning("记忆库落盘异常（不阻断结算）：%s", e)
    # 自动存档：每年正月（1 月）自动写入槽 0（自动槽），游戏结束也存一份最终档
    if state.month == 1 or state.game_over:
        try:
            from core.save_load import save_game
            save_game(state, slot=0)
        except Exception:
            pass  # 自动存档失败不阻断结算


def monthly_report_args(state) -> tuple:
    """构建月报调用入参（主线程快照）：(year, month, era_name, posture_with_memory)。

    记忆知识库（Phase 3a）近期事件/决策子图 + 时代档位（认知层脱敏）注入 posture；
    供同步 settle_turn 与 T6 异步叙事后补共用，避免 UI 层复制核心规则。
    """
    _posture = state.posture
    try:
        # 审查 P1-5 修复：用层级检索 retrieve_hierarchical（先概要后细节），替代裸 query。
        # 命中周期概要时只给概要（省 token）；否则回退近 24 回合事件/决策细节。
        mg = state.memory
        _period = state.turn // 12 if state.turn > 0 else None
        hier = mg.retrieve_hierarchical(subject="event", period=_period, top_k=6)
        _mem_hint = hier.get("summary", "") if isinstance(hier, dict) else ""
        if not _mem_hint:
            rows = mg.query("event", time_window=24, top_k=6)
            if not rows:
                rows = mg.query("decision", time_window=24, top_k=6)
            _mem_hint = mg.summarize(rows, max_chars=120)
        if _mem_hint:
            _posture = f"{state.posture}\n【近期朝局】{_mem_hint}"
    except Exception:
        pass
    # 建筑-时代交互：月报注入时代档位（认知层脱敏；句式库待史翰青素材）
    try:
        from core.era_mechanic import era_brief
        _posture += f"\n【时代】{era_brief(state)}"
    except Exception:
        pass
    return state.year, state.month, state.era_name, _posture


def _monthly_report_text(state, ai_client) -> str:
    """生成月报文本（装饰性 AI 文本）。

    T8 分级降级：AI 失败 / 未接入 / 返回 _fallback 标记 → 本地模板 + 结构化真值组装
    （只引用 settlement_log 程序真值，不伪造数字、不伪造 AI 口吻）。
    """
    year, month, era_name, posture = monthly_report_args(state)
    if not (ai_client and getattr(ai_client, "available", False)):
        # AI 未接入 → 本地模板兜底（游戏可继续）
        from ai.narrative_fallback import fallback_report
        return str(fallback_report(year=year, month=month, era_name=era_name,
                                   state=state).get("report") or "")
    monthly = ai_client.monthly_report(year, month, era_name, posture)
    if isinstance(monthly, dict):
        if monthly.get("_error") or monthly.get("_fallback"):
            # AI 未接入/失败 → 本地模板 + 真值组装（游戏可继续）
            from ai.narrative_fallback import fallback_report
            return str(fallback_report(year=year, month=month, era_name=era_name,
                                       state=state).get("report") or "")
        return str(monthly.get("report") or "")
    return str(monthly or "")


# ============================================================
# 拟旨·会签：诏草 → 会签 → 下发
# ============================================================
def resolve_event(state: GameState, event: dict, choice_idx: int, ai_client=None) -> str:
    """处理玩家对某事件的选择，返回效果叙述。"""
    log = apply_event_choice(state, event, choice_idx)
    narr = ""
    if ai_client and ai_client.available:
        try:
            narr_raw = ai_client.event_narrative(event.get("title", ""), event.get("desc", event.get("title", "")))
            narr = str(narr_raw.get("narrative") or "") if isinstance(narr_raw, dict) else str(narr_raw or "")
        except Exception:
            # T8 分级降级：事件叙事失败 → 本地模板兜底（按 severity 分档，不阻断）
            from ai.narrative_fallback import fallback_event
            _sev = "重" if ("灾" in str(event.get("category", "")) or "战" in str(event.get("category", ""))) else "中"
            narr = str(fallback_event(event.get("title", ""), _sev).get("narrative") or "")
    # 清除该事件在场标记
    title = event.get("title", "")
    state.active_events = [e for e in state.active_events if title not in e.get("message", "")]
    if check_game_over(state):
        state.game_over = True
    return "\n".join(log) + (("\n〔朝堂〕" + narr) if narr else "")


# ============================================================
# 存档 / 读档
# ============================================================
def save(state: GameState, slot: int = 1) -> bool:
    return save_game(state, slot)


def load(slot: int = 1):
    return load_game(slot)


def save_slots() -> list:
    return get_save_slots()


# ============================================================
# 结局评估
# ============================================================
def conclude(state: GameState, ai_client=None) -> tuple:
    """生成结局评定，返回 (eval_result, ai_eval_text)。"""
    eval_result = evaluate_game(state)
    ai_eval = ""
    if ai_client and ai_client.available:
        try:
            summary = state.get_state_summary()
            ai_eval_raw = ai_client.final_eval(state.year, state.year, state.posture)
            ai_eval = str(ai_eval_raw.get("commentary") or "") if isinstance(ai_eval_raw, dict) else str(ai_eval_raw or "")
        except Exception:
            # T8 分级降级：结局叙事失败 → 本地模板兜底（评定数据仍来自程序 evaluate_game）
            from ai.narrative_fallback import fallback_eval
            ai_eval = str(fallback_eval(state.turn).get("commentary") or "")
    return eval_result, ai_eval


__all__ = [
    "new_game", "audience_minister", "issue_decree", "issue_secret_decree",
    "do_personal_action", "choose_imperial_action", "choose_major_policy", "advance_month", "settle_turn",
    "settle_local", "finish_turn", "monthly_report_args",
    "resolve_event", "save", "load", "save_slots", "conclude",
    "audience_dialogue", "audience_dialogue_prepare", "audience_dialogue_apply",
    "issue_drafted_decree", "preview_draft",
]


# ============================================================
# 召见大臣 · 多轮奏对（AI 叙事）
# ============================================================
# 预过滤讨论类排除词（含这些词 → 走 AI 讨论，防误伤：把议政当诏令）
_DISCUSS_KEYWORDS = ("利弊", "之辩", "高见", "何如", "奈何", "可否", "如何", "议论", "容臣", "且慢")
# 预过滤长度上限：>40 字复杂诏令不预过滤（走 AI）
_PREFILTER_MAX_LEN = 40


def _prefilter_rules():
    """预过滤规则：(关键词组, 模板, 意图词)。模板用 {m} 占位大臣名。"""
    return [
        (("调兵", "整军", "阅兵", "边防", "戍"), "{m}：臣已奉诏整饬军务，以军令严肃待陛下亲阅。", "调兵"),
        (("赈灾", "开仓", "发粟", "饥荒"), "{m}：臣已奉诏发仓赈济，先安流民，再图善后。", "赈灾"),
        (("减税", "免税", "蠲免", "薄赋"), "{m}：臣已奉诏蠲免，民力稍纾，待有司核算具奏。", "减税"),
        (("宽民", "恤民", "安民"), "{m}：臣已奉诏宽恤，当下各县遵行，以安民心。", "恤民"),
        (("整吏", "肃贪", "清吏", "查贪"), "{m}：臣已奉诏整饬吏治，严查贪墨，以清纲纪。", "肃贪"),
        (("兴学", "贡举", "科举", "学校"), "{m}：臣已奉诏兴学劝士，贡举之制当徐徐图之。", "兴学"),
        (("市舶", "通商", "海贸"), "{m}：臣已奉诏广开市舶，招徕商贾，岁入可期。", "市舶"),
        (("粮价", "常平", "平籴"), "{m}：臣已奉诏平抑粮价，常平籴粜以济民艰。", "平籴"),
        (("内帑", "发内帑", "私帑", "内库"), "{m}：臣已奉诏开内帑，以私蓄济公，度支稍纾。", "内帑"),
        (("军饷", "发饷", "饷银", "支饷"), "{m}：臣已奉诏支拨军饷，三军立解饥寒，士气可期。", "军饷"),
        # A 建议：补漏高频新机制类别（低误伤）
        (("建军", "新军", "募兵", "团练"), "{m}：臣已奉诏募练新军，择其精壮编伍成军，候陛下阅视。", "建军"),
        (("研制", "发明", "工器", "试造"), "{m}：臣已奉诏督办工器，选匠聚料，当按程试造。", "研制"),
        (("遣使", "和议", "岁币"), "{m}：臣已奉诏遣使通好，修两国之谊。", "遣使"),
        (("营造", "修园", "建宫"), "{m}：臣已奉诏督工营造，先度材用，再兴土木。", "营造"),
    ]


def _prefilter_intent_hint(player_input: str) -> str:
    """预过滤命中后的意图词（供后续拟诏 AI 上下文，降低模板与 AI 割裂）。"""
    text = player_input or ""
    for kws, _tmpl, intent in _prefilter_rules():
        if any(k in text for k in kws):
            return intent
    return ""


def _prefilter_dialogue(minister_name: str, player_input: str):
    """召对 token 优化：本地规则匹配常用诏令 → 本地模板回复（AI 只处理非常规）。

    误伤缓解（B 建议）：讨论类（利弊/之辩/高见/何如…）跳过走 AI；>40 字复杂诏令
    不预过滤；短祈使句（如「赈灾开仓」）视为下诏意图命中。模板为本地组装非 AI 伪造。
    """
    text = (player_input or "").strip()
    if not text or len(text) > _PREFILTER_MAX_LEN:
        return None
    if any(k in text for k in _DISCUSS_KEYWORDS):
        return None
    for kws, tmpl, _intent in _prefilter_rules():
        if any(k in text for k in kws):
            return tmpl.format(m=minister_name)
    return None


def _dialogue_stats(state):
    """召对 token 统计（省 token 可量化；动态字段不序列化）：预过滤命中/缓存命中/AI 调用。"""
    st = getattr(state, "_dialogue_stats", None)
    if st is None:
        st = state._dialogue_stats = {"prefilter_hits": 0, "cache_hits": 0, "ai_calls": 0}
    return st


_DIALOGUE_CACHE_TURNS = 8    # 近 N 回合复用窗口
_DIALOGUE_CACHE_MAX = 256    # 防膨胀上限


# 召对主题词归一（D 建议）：同话题不同措辞 → 同一主题词 → 缓存命中
_TOPIC_WORDS = ("河工", "变法", "岁币", "市舶", "科举", "赈济", "军饷", "内帑",
                "减税", "边防", "粮价", "营建", "新军", "工器")


def _topic_key(player_input: str) -> str:
    """召对意图主题词（缓存键组成部分）：命中主题词取主题词（同话题不同措辞命中），
    否则回退输入前 12 字。"""
    text = (player_input or "").strip()
    for w in _TOPIC_WORDS:
        if w in text:
            return w
    return text[:12]


def _dialogue_cache_store(state, minister_name: str, player_input: str, reply: str):
    """AI 成功回复后写召对缓存（结构化键：minister+topic+意图摘要；近 N 回合复用）。"""
    cache = getattr(state, "_dialogue_cache", None)
    if cache is None:
        cache = state._dialogue_cache = {}
    if len(cache) >= _DIALOGUE_CACHE_MAX:      # 防膨胀：超限清空重建（缓存可重建，非权威）
        cache.clear()
    cache[f"{minister_name}|{_topic_key(player_input)}"] = {
        "reply": reply, "turn": state.turn}


def _dialogue_cache_hit(state, minister_name: str, player_input: str):
    """召对缓存：同大臣同话题近 N 回合的召对结果复用（省 token，命中不调 AI）。

    本地缓存键 = minister + topic（意图摘要）；未命中回退相似度扫描（>0.85 复用上次，
    兼容既有行为），命中时写回结构化缓存供后续精确复用。
    """
    key = f"{minister_name}|{_topic_key(player_input)}"
    cache = getattr(state, "_dialogue_cache", None)
    if cache:
        entry = cache.get(key)
        if entry and state.turn - entry.get("turn", -99) <= _DIALOGUE_CACHE_TURNS:
            _dialogue_stats(state)["cache_hits"] += 1
            return entry["reply"]
    # 相似度 fallback（既有行为）：玩家重复问同一话题（相似度>0.85）→ 复用上次大臣回复
    try:
        from difflib import SequenceMatcher
        hist = state.dialogue_history
        for i in range(len(hist) - 2, -1, -1):
            if hist[i][0] == "朕" and i + 1 < len(hist) and hist[i + 1][0] == minister_name:
                if SequenceMatcher(None, player_input, str(hist[i][1])).ratio() > 0.85:
                    reply = str(hist[i + 1][1])
                    _dialogue_stats(state)["cache_hits"] += 1
                    _dialogue_cache_store(state, minister_name, player_input, reply)
                    return reply
                break
    except Exception:
        pass
    return None
def audience_dialogue(state: GameState, minister_name: str, player_input: str,
                      ai_client) -> str:
    """与大臣奏对一轮。返回大臣的奏对文本，并把对话记入 state.dialogue_history。

    同步版（T6 异步拆分的组装）：prepare（主线程入史/快照）→ AI 调用 → apply（主线程落定）。
    落地改进 3（召对 token 优化）：玩家输入预过滤（本地规则匹配常用诏令 → 本地模板，
    AI 只处理非常规）+ 召对缓存（同话题近期结果复用，省 token）。
    """
    # 预过滤（本地规则，非 AI 伪造）：常用诏令 → 模板回复（带意图词供后续拟诏）
    pref = _prefilter_dialogue(minister_name, player_input)
    if pref:
        _dialogue_stats(state)["prefilter_hits"] += 1
        hint = _prefilter_intent_hint(player_input)
        if hint:
            state._last_intent_hint = hint
        state.dialogue_history.append((minister_name, pref))
        return pref
    # 召对缓存：同话题近 N 回合结果复用（结构化键 + 相似度 fallback）
    cached = _dialogue_cache_hit(state, minister_name, player_input)
    if cached:
        state.dialogue_history.append((minister_name, cached))
        return cached
    kwargs, note = audience_dialogue_prepare(state, minister_name, player_input)
    if note is not None:
        return note
    if not (ai_client and getattr(ai_client, "available", False)):
        # T8 分级降级：AI 未接入 → 召对模板兜底（大臣未及具奏，不伪造政见，游戏可继续）
        from ai.narrative_fallback import fallback_dialogue
        obj = fallback_dialogue(minister_name, state.turn)
        reply = audience_dialogue_apply(state, minister_name, obj)
        return reply or "（大臣未及应诏。）"
    try:
        # 按位置传递（兼容真实 AIClient 与测试替身的参数名差异），state 走关键字
        obj = ai_client.dialogue(
            kwargs["minister_name"], kwargs["faction"], kwargs["faction_stance"],
            kwargs["minister_traits"], kwargs["minister_role"], kwargs["era_name"],
            kwargs["history"], kwargs["player_input"], kwargs["state_summary"],
            state=kwargs["state"],
        )
    except Exception:
        # T8 分级降级：召对叙事失败 → 本地模板兜底（大臣未及具奏，不伪造政见）
        from ai.narrative_fallback import fallback_dialogue
        obj = fallback_dialogue(kwargs["minister_name"], state.turn)
    reply = audience_dialogue_apply(state, minister_name, obj)
    if not reply:
        # T8 分级降级：AI 返回空 → 召对模板兜底（不报错阻断）
        from ai.narrative_fallback import fallback_dialogue
        obj = fallback_dialogue(minister_name, state.turn)
        reply = audience_dialogue_apply(state, minister_name, obj) or "（大臣未及应诏。）"
    # AI 调用成功：计数 + 写召对缓存（同话题近 N 回合复用，省 token）
    _dialogue_stats(state)["ai_calls"] += 1
    _dialogue_cache_store(state, minister_name, player_input, reply)
    return reply


def audience_dialogue_prepare(state: GameState, minister_name: str,
                              player_input: str):
    """召对前奏（主线程）：身份/状态校验 + 入史（朕言/短期日志）+ 构建 AI 入参。

    返回 (kwargs, note)：
      - note 非 None → 不可召对（已薨/罢黜），已写入史册说明，无需 AI；
      - 否则 kwargs 为 ai_client.dialogue 的调用参数（state 为只读引用；
        history 为快照列表，避免后台读取时主线程追加的竞态）。
    """
    from content.ministers import HISTORICAL_FIGURES
    from content.data import FACTION_INIT
    # 找到大臣所属派系
    faction = "中枢"
    for fn, f in state.factions.items():
        if f["leader"] == minister_name:
            faction = fn
            break
    fig = HISTORICAL_FIGURES.get(minister_name, {})
    faction_stance = FACTION_INIT.get(faction, {}).get("leader", "")
    minister_traits = fig.get("traits", "老成持重")
    minister_role = fig.get("role", "朝中大臣")
    # 角色状态校验：已薨/已革职之臣不可再召对办差
    mstatus = state.minister_status(minister_name)
    if mstatus != "active":
        note = "（已薨，不及奉诏）" if mstatus == "dead" else "（已罢黜，不在朝列）"
        state.dialogue_history.append((minister_name, note))
        return None, f"{minister_name}{note}"
    state.last_audience = minister_name
    state.dialogue_history.append(("朕", player_input))
    try:
        state.short_term_log.append(
            {"turn": state.turn, "kind": "edict", "title": player_input[:40],
             "note": f"召对{minister_name}", "year": state.year, "month": state.month})
    except Exception:
        pass
    # 省 token（用户定稿）：召对基础注入只带人物上下文（身份/立场/姿态/相关历史），
    # **不主动注入全局数值**；AI 需数值时调 query_state 工具查（本地精准值，防瞎编）
    persona_hint = ""
    try:
        from content.ministers.persona import _build_persona_prompt
        persona_hint = _build_persona_prompt(state, minister_name, state.turn)
    except Exception:
        persona_hint = ""
    state_summary = persona_hint or "（无特别注记）"
    # 三方案：来源闭集 + 人物校验表（黑名单模式，省 token）
    try:
        from ai.narrative_guard import _build_source_closure, build_character_statuses, build_character_blacklist
        closure = _build_source_closure(state)
        blacklist = build_character_blacklist(build_character_statuses(state))
        state_summary += f"\n{closure}\n{blacklist}"
    except Exception:
        pass
    # 对话记忆库概要注入（省 token：概要优先，细节按需——只注入概要，不展开 details 防全量）
    try:
        from memory.dialogue_memory import get_dialogue_memory
        dm = get_dialogue_memory(state)
        dm.turn = state.turn
        q = dm.query_for_dialogue(minister_name, state.turn, top_k=2)
        if q and q.get("summary"):
            state_summary += f"\n【卿前番之言】{q['summary']}"
    except Exception:
        pass
    # 新旧产业认知层感知（用户指示）：召对注入产业状态（「铁路通了」「机器局开了」）
    try:
        from core.era_mechanic import industry_brief
        state_summary += f"\n【产业】{industry_brief(state)}"
    except Exception:
        pass
    kwargs = {
        "minister_name": minister_name,
        "faction": faction,
        "faction_stance": faction_stance,
        "minister_traits": minister_traits,
        "minister_role": minister_role,
        "era_name": state.era_name,
        "history": list(state.dialogue_history),   # 快照，防后台读时主线程追加竞态
        "player_input": player_input,
        "state_summary": state_summary,
        "state": state,
    }
    return kwargs, None


def audience_dialogue_apply(state: GameState, minister_name: str, obj) -> str:
    """召对落定（主线程）：解出回奏并写入史册/意向，返回回奏文本。

    无回奏（AI 不可用/失败标记）时不写史册，返回空串，由调用方拒绝式处理。
    """
    reply = obj.get("reply", "") if isinstance(obj, dict) else str(obj or "")
    if not reply:
        return ""
    # 把大臣倾向记下来，供拟诏时喂给 AI
    intent_hint = obj.get("intent_hint", "") if isinstance(obj, dict) else ""
    if intent_hint:
        state._last_intent_hint = intent_hint
    state.dialogue_history.append((minister_name, reply))
    # 对话记忆库（SQLite，单独存对话）：召对记录入库（量大高频，与圣旨/口谕主库分离）
    try:
        from memory.dialogue_memory import get_dialogue_memory
        dm = get_dialogue_memory(state)
        dm.turn = state.turn
        stance = str(obj.get("intent_hint", "") if isinstance(obj, dict) else "")
        dm.add_dialogue(minister_name, state.turn, minister_name, reply,
                        intent=intent_hint, stance=stance[:20])
    except Exception:
        pass  # 对话库失败不阻断召对（兼容层 dialogue_history 保留）
    return reply


# ============================================================
# 拟诏颁布（基于大臣奏对与陛下自拟意图）
# ============================================================


# ============================================================
# 大臣离任执行（A3，素材 a6_narrative_materials.md 第 2.3 节）
#   契约：① 清 central_orgs 该大臣所任岗位 holder → ② mark_minister_status
#   → ③ 按 DEPARTURE_RULES 应用档位影响（tier_to_value/TIER_RANGE 换算封顶）
#   → ④ 追加 minister_memory → ⑤ 返回日志。
#   玩家与 AI 只见档位词，数值归程序换算；离任事实（某人某年贬/殁）待考据单逐人核卷。
# ============================================================
def apply_minister_departure(state: GameState, name: str, reason: str) -> list:
    """执行大臣离任（贬黜/致仕/病故/战殁/处死/乞休），返回日志列表。"""
    from content.ministers.data import departure_effects, traits_of, MINISTERS
    from content.data import TIER_RANGE
    from ai.client_utils import tier_to_value

    rule = departure_effects(reason)
    if not rule:
        return [f"[离任] 未知离任原因：{reason}（{name} 未处理）"]
    log = []

    # ① 清岗：central_orgs 中该大臣所任岗位 holder 置空（权限跟机构不跟人，仅换 holder）
    cleared = []
    for org_key, org in (getattr(state, "central_orgs", {}) or {}).items():
        holders = org.get("holders") or {}
        for title, holder in list(holders.items()):
            if holder == name:
                holders[title] = ""
                cleared.append(f"{org_key}·{title}")
    if cleared:
        log.append(f"[离任] 罢免 {name} 职务：{'、'.join(cleared)}（{rule.get('handle', '依官制补缺')}）")

    # ② 状态映射（reason → player_minister_status）
    _status_map = {"贬黜": "dismissed", "致仕": "dismissed", "乞休": "dismissed",
                   "病故": "dead", "战殁": "dead", "处死": "dead"}
    state.mark_minister_status(name, _status_map.get(reason, "dismissed"))

    # ③ 档位影响（档位词 → 数值，程序换算封顶）
    def _tier_pair(tier):
        """档位词（可带 +/-）→ (方向, 档位词)。"""
        text = str(tier).strip()
        direction = 1.0
        if text.startswith("-"):
            direction, text = -1.0, text[1:]
        elif text.startswith("+"):
            text = text[1:]
        return direction, text

    def _apply(dim, tier):
        direction, t = _tier_pair(tier)
        if t == "无" or not t:
            return 0
        if dim == "faction":
            # 派系满意度 0~100 刻度（与 population_satisfaction 基准一致）
            return int(direction * round(3.0 * TIER_RANGE.get(t, 0.0)))
        return int(direction * tier_to_value(dim, t, 1.0))

    _fig = MINISTERS.get(name, {})
    _fac = _fig.get("faction", "")
    _p = _apply("prestige", rule.get("prestige", "无"))
    _t = _apply("treasury", rule.get("treasury", "无"))
    _f = _apply("faction", rule.get("faction_satisfaction", "无"))
    if _p:
        state.change_prestige(_p, f"{name}{reason}")
        log.append(f"[皇威] {reason} {name}，皇威 {'+' if _p >= 0 else ''}{_p}")
    if _t:
        state.change_treasury(_t)
        log.append(f"[国库] {reason}相关，国帑 {'+' if _t >= 0 else ''}{_t}贯")
    if _f and _fac in state.factions:
        state.factions[_fac]["satisfaction"] = max(0, min(100, state.factions[_fac]["satisfaction"] + _f))
        log.append(f"[派系] {_fac}满意度 {'+' if _f >= 0 else ''}{_f}")

    # 特殊修饰（条件式判定，写死可审查；数值仍走档位换算）
    _corr = state.corruption.get(name, 0.0)
    _has_war = bool(set(traits_of(name)) & {"军略", "忠勇"})
    for spec in rule.get("specials", []):
        when = spec.get("when", "")
        hit = {
            "清流言官": _fac == "清流言官",
            "权臣": _corr >= 0.6,
            "老臣": (state.year - _fig.get("born", 1100)) >= 60,
            "名将": _has_war,
            "惩贪": _corr >= 0.5,
            "冤杀": _corr < 0.5,
        }.get(when, False)
        if not hit:
            continue
        for target, tier in spec.get("effects", {}).items():
            if target == "corruption":
                # 隐藏贪腐度 0~1 刻度，档位微调（0.05 步长），绝不出现在任何 UI 文本
                direction, _ = _tier_pair(tier)
                delta = direction * 0.05
                if name in state.corruption:
                    state.corruption[name] = max(0.0, min(1.0, state.corruption[name] + delta))
                log.append(f"[贪墨] {name}贪腐度 {'+' if delta >= 0 else ''}{delta:.2f}")
            elif target == "边境士气":
                _b = _apply("defense_bonus", tier)
                for line in state.defense_lines.values():
                    line["fortification"] = max(0, min(100, line.get("fortification", 50) + _b))
                log.append(f"[军心] 边境士气 {'+' if _b >= 0 else ''}{_b}")
            elif target in state.factions:
                _d = _apply("faction", tier)
                state.factions[target]["satisfaction"] = max(0, min(100, state.factions[target]["satisfaction"] + _d))
                log.append(f"[派系] {target}满意度 {'+' if _d >= 0 else ''}{_d}")
            else:
                log.append(f"[离任修饰] {when}：{target} {tier}（待核）")

    # ④ 大臣记忆（离任事实留痕，供后续考据/叙事；双写：minister_memory + 记忆图谱）
    mem = state.minister_memory.setdefault(name, [])
    mem.append(f"{state.year}年{state.month}月 {reason}（{rule.get('handle', '')}）")
    try:
        state.memory.turn = state.turn
        state.memory.add_entity(f"minister_{name}", "minister", name, turn=state.turn)
        state.memory.upsert_relation(f"minister_{name}", f"status_{reason}", "governs",
                                     weight=1.0, turn=state.turn, note=reason)
    except Exception:
        pass

    # ⑤ 日志
    log.insert(0, f"[离任] {name} {reason}")
    return log