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
from core.commands_policy import (
    _state_summary_min, start_project, start_workshop,
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
    """执行月度结算，返回 (log, ai_report)。

    全游戏级强制 AI（用户定稿）：AI 缺失/推演失败 → **拒绝式**（抛 AIRuntimeError，
    不静默兜底、不伪造景气/城市化/科举档位）；结算不进行，由上层提示配置 OpenAI 兼容 API。
    月份/年份的推进已收敛到 run_monthly_settlement 内部（与 Rust 后端 settle.rs 的
    推进位置保持一致）。
    """
    from content.data import AI_ERROR_CODES
    # AI 经济推演（景气/士绅囤粮/生产）须在结算之前注入，本月生效（结算内读 _economy_ai）
    if not (ai_client and getattr(ai_client, "available", False)):
        raise AIRuntimeError(AI_ERROR_CODES.get("AI_NOT_CONFIGURED", "AI 未接入"))
    try:
        eco = ai_client.economy_decide(state.posture)
    except Exception as e:
        raise AIRuntimeError(f"经济推演失败（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    if not isinstance(eco, dict) or eco.get("_error"):
        raise AIRuntimeError(AI_ERROR_CODES.get("AI_CONTRACT_FAILED", "AI 输出不满足契约"))
    state._economy_ai = eco
    # 12 步 agent 化 P1：外交/军事/灾荒契约注入（agent 只给档位词，守恒数值由程序换算）
    for _attr, _call in (("_diplomacy_ai", "diplomacy_decide"),
                         ("_military_ai", "military_decide"),
                         ("_relief_ai", "relief_decide")):
        try:
            _r = getattr(ai_client, _call)(state.posture, state=state)
            if isinstance(_r, dict) and not _r.get("_error"):
                setattr(state, _attr, _r)
        except Exception:
            pass   # P1 契约失败不阻断结算（保留既有规则）
    log = run_monthly_settlement(state)
    report = ""
    # 月报为装饰性 AI 文本：失败拒绝式报错（不降级为空、不伪造），
    # 结算已就地发生，UI 需在展示层处理（勿误判"未推进"而重复结算）
    try:
        # 记忆知识库（Phase 3a）：月报注入近期事件/决策子图（脱敏）
        _posture = state.posture
        try:
            rows = state.memory.query("event", time_window=24, top_k=6)
            if not rows:
                rows = state.memory.query("decision", time_window=24, top_k=6)
            _mem_hint = state.memory.summarize(rows, max_chars=120)
            if _mem_hint:
                _posture = f"{state.posture}\n【近期朝局】{_mem_hint}"
        except Exception:
            _posture = state.posture
        # 建筑-时代交互：月报注入时代档位（认知层脱敏；句式库待史翰青素材）
        try:
            from core.era_mechanic import era_brief
            _posture += f"\n【时代】{era_brief(state)}"
        except Exception:
            pass
        monthly = ai_client.monthly_report(state.year, state.month, state.era_name, _posture)
        if isinstance(monthly, dict):
            report = str(monthly.get("report") or "")
        else:
            report = str(monthly or "")
    except Exception as e:
        raise AIRuntimeError(f"月报生成失败（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    if check_game_over(state):
        state.game_over = True
    # 自动存档：每年正月（1 月）自动写入槽 0（自动槽），游戏结束也存一份最终档
    if state.month == 1 or state.game_over:
        try:
            from core.save_load import save_game
            save_game(state, slot=0)
        except Exception:
            pass  # 自动存档失败不阻断结算
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
    "audience_dialogue", "issue_drafted_decree", "preview_draft",
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
            # 两层记忆 + persona（Phase 3b）：召对注入 persona（身份/立场/姿态/相关历史），
            # loyalty 数值绝不注入；口谕写入短期行为日志（不注入 AI 上下文）
            persona_hint = ""
            try:
                from content.ministers.persona import _build_persona_prompt
                persona_hint = _build_persona_prompt(state, minister_name, state.turn)
            except Exception:
                persona_hint = ""
            try:
                state.short_term_log.append(
                    {"turn": state.turn, "kind": "edict", "title": player_input[:40],
                     "note": f"召对{minister_name}", "year": state.year, "month": state.month})
            except Exception:
                pass
            # 省 token（用户定稿）：召对基础注入只带人物上下文（身份/立场/姿态/相关历史），
            # **不主动注入全局数值**；AI 需数值时调 query_state 工具查（本地精准值，防瞎编）
            state_summary = persona_hint or "（无特别注记）"
            # 三方案：来源闭集 + 人物校验表（黑名单模式，省 token）
            try:
                from ai.narrative_guard import _build_source_closure, build_character_statuses, build_character_blacklist
                closure = _build_source_closure(state)
                blacklist = build_character_blacklist(build_character_statuses(state))
                state_summary += f"\n{closure}\n{blacklist}"
            except Exception:
                pass
            # 新旧产业认知层感知（用户指示）：召对注入产业状态（「铁路通了」「机器局开了」）
            try:
                from core.era_mechanic import industry_brief
                state_summary += f"\n【产业】{industry_brief(state)}"
            except Exception:
                pass
            obj = ai_client.dialogue(
                minister_name, faction, faction_stance, minister_traits,
                minister_role, state.era_name, state.dialogue_history,
                player_input, state_summary, state=state,
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