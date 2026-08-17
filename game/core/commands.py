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

from core.game_state import GameState
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
from core.commands_policy import (
    _state_summary_min, diplomacy_policy, exam_policy, finance_policy, govern_yamen, granary_policy, local_policy, military_expand, reform_policy, science_policy, start_project, start_workshop,
)


def new_game(difficulty: str = "史实", ai_client=None) -> GameState:
    """创建新游戏"""
    state = GameState(difficulty=difficulty)
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
    # AI 建言（若启用）
    if ai_client and ai_client.available:
        try:
            advice_raw = ai_client.advice(state.posture, faction)
            advice = str(advice_raw.get("advice") or "") if isinstance(advice_raw, dict) else str(advice_raw or "")
            msg += f"\n〔{leader}奏曰〕{advice}"
        except Exception as e:
            raise AIRuntimeError(f"召见时 AI 建言中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return msg


# ============================================================
# 下旨颁诏
# ============================================================
def do_personal_action(state: GameState, name: str) -> str:
    if name not in PERSONAL_ACTIONS:
        return "无此行动。"
    state.personal_action = name
    return f"本回合个人行动：{name} — {PERSONAL_ACTIONS[name]['desc']}"


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


def _next_month(year: int, month: int):
    month += 1
    if month > 12:
        month = 1
        year += 1
    return year, month


# ============================================================
# 统一拟旨（圣旨 / 密旨）— AI 解析结果落地
# ============================================================
def settle_turn(state: GameState, ai_client=None) -> tuple:
    """执行月度结算，返回 (log, ai_report)。"""
    log = run_monthly_settlement(state)
    # 结算完成后再推进月份，保证结算与事件都作用于当前月；回合数由 run_monthly_settlement 统一递增。
    state.year, state.month = _next_month(state.year, state.month)
    report = ""
    if ai_client and ai_client.available:
        try:
            summary = state.get_state_summary()
            monthly = ai_client.monthly_report(state.year, state.month, state.era_name, state.posture)
            # monthly_report 返回 {"report": str, "scenes": [...]}
            if isinstance(monthly, dict):
                report = str(monthly.get("report") or "")
            else:
                report = str(monthly or "")
        except Exception as e:
            raise AIRuntimeError(f"月度结算时 AI 报告中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    if check_game_over(state):
        state.game_over = True
    return log, report


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
        except Exception as e:
            raise AIRuntimeError(f"事件叙事时 AI 中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
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
        except Exception as e:
            raise AIRuntimeError(f"结局评定时 AI 中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    return eval_result, ai_eval


__all__ = [
    "new_game", "audience_minister", "issue_decree", "issue_secret_decree",
    "do_personal_action", "choose_major_policy", "advance_month", "settle_turn",
    "resolve_event", "save", "load", "save_slots", "conclude",
    "audience_dialogue", "issue_drafted_decree", "preview_draft", "govern_yamen", "local_policy",
]


# ============================================================
# 召见大臣 · 多轮奏对（AI 叙事）
# ============================================================
def audience_dialogue(state: GameState, minister_name: str, player_input: str,
                      ai_client) -> str:
    """与大臣奏对一轮。返回大臣的奏对文本，并把对话记入 state.dialogue_history。"""
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
        return f"{minister_name}{note}"
    state.last_audience = minister_name
    state.dialogue_history.append(("朕", player_input))
    reply = ""
    intent_hint = ""
    if ai_client and getattr(ai_client, "available", False):
        try:
            obj = ai_client.dialogue(
                minister_name, faction, faction_stance, minister_traits,
                minister_role, state.era_name, state.dialogue_history,
                player_input, state.get_state_summary(), state=state,
            )
            if isinstance(obj, dict):
                reply = obj.get("reply", "")
                intent_hint = obj.get("intent_hint", "")
        except Exception as e:
            # 运行时故障（超时/限流/报错）：停下，不静默、不伪造
            raise AIRuntimeError(f"召对时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    if not reply:
        # 仅"未配置 AI"会到此：停下并提示配置
        raise AIRuntimeError(
            "AI 叙事不可用：召对需要 AI 接入。请在「游戏设置 → AI 配置」中完成配置后重试。"
        )
    # 把大臣倾向记下来，供拟诏时喂给 AI
    if intent_hint:
        state._last_intent_hint = intent_hint
    state.dialogue_history.append((minister_name, reply))
    return reply


# ============================================================
# 拟诏颁布（基于大臣奏对与陛下自拟意图）
# ============================================================