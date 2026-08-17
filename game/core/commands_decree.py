# -*- coding: utf-8 -*-
"""宋祚 · 诏令/密旨/拟旨/会签 指令族（拆分自 core/commands.py）"""
import random
from typing import Any
from core.game_state import GameState
from core.settlement import run_monthly_settlement, settle_reform, _apply_decree_effect
from core.errors import AIRuntimeError
from content.data import (
    ZHONGZHI_AFFILIATION_RATE,
    FACTION_NAMES,
    get_prestige_level,
)
from content.ministers import MINISTERS, loyalty_init


def _rule_draft(intent: str) -> dict:
    """无 AI 客户端时的极简拟诏（返回错误标记，不伪造文本）。"""
    from ai.client import _ai_unavailable
    return _ai_unavailable("draft_decree", title="（AI 不可用）", body=intent)


# ============================================================
# 六部衙门施政（AI 叙事 + 规则结算）
# ============================================================


def _enqueue(state, task, is_secret):
    if is_secret:
        state.longterm_secret.append(task)
    else:
        state.longterm_public.append(task)


def dismiss_pending_break(state: GameState, break_id: str) -> str:
    """朱批「从长计议」：取消该候选改写位（本次不改写历史）。

    后续若玩家成效持续达线，仍会在未来回合重新生成候选。
    """
    pb = getattr(state, "pending_breaks", {})
    if break_id not in pb:
        return f"无待确认改写位：{break_id}"
    pb.pop(break_id)
    return "〔朱批〕从长计议，此事暂缓。"


def _run_fixed(state, cat, params):
    """固定程序四类的即时规则效果（长期类不在此处结算）。"""
    if cat == "fixed_finance":
        amt = int(params.get("amount", 0))
        target = params.get("target")
        # 拨入来源：移库时从何处支出（如「移国库入内帑」from=国库 to=内帑）
        src = params.get("from")
        if not target and src:
            target = params.get("to", "国库")
        if not amt or not target:
            return
        if target == "内藏":
            state.change_imperial_treasury(amt)
        elif target == "国库":
            state.change_treasury(amt)
        elif target == "州郡":
            # 州郡赈济等仍走国库列支
            state.change_treasury(amt)
        # 若指定了来源（移库），从来源扣除
        if src == "内藏":
            state.change_imperial_treasury(-amt)
        elif src == "国库":
            state.change_treasury(-amt)
    elif cat == "fixed_army":
        # 即时整训：小幅提升相关防线
        pass


def reject_edict_draft(state: GameState, draft_id: str) -> str:
    """打回诏草，令改。"""
    draft = state.get_edict_draft(draft_id)
    if not draft:
        return "诏草已不存在。"
    state.remove_edict_draft(draft_id)
    return f"已打回诏草：「{draft.get('title','')}」，着另行拟奏。"


def _apply_rename(state, old_name, new_name):
    """按显示名查找并更名（宋本土路或外部政权）。"""
    for key, p in state.prefectures.items():
        if p.get("name") == old_name or key == old_name:
            p["name"] = new_name
            p.setdefault("rename_log", []).append(new_name)
            return
    for key, ex in state.external_regimes.items():
        if ex.get("name") == old_name or key == old_name:
            ex["name"] = new_name
            ex.setdefault("rename_log", []).append(new_name)
            return


def issue_edict_from_review(state: GameState, draft_id: str,
                            decision: str = "approve", revised_effects=None) -> str:
    """据会签意见下发诏草。
    decision: 'approve'(准奏，走会签生效) | 'force'(御笔直发，转中旨)。
    返回消息。"""
    draft = state.get_edict_draft(draft_id)
    if not draft:
        return "诏草已不存在。"
    org = draft.get("org_hint", "政府")
    effs = revised_effects if revised_effects is not None else draft.get("effects", [])

    if decision == "force":
        # 御笔直发：绕过会签，转中旨
        if len(state.pending_secret_decrees) >= 3:
            return "密旨（中旨）已满，御笔暂不能发。"
        decree_full = {
            "title": draft.get("title", "御笔中旨"),
            "category": "中旨",
            "is_secret": True,
            "is_direct": True,
            "is_zhongzhi": True,
            "org_hint": org,
            "turn_issued": state.turn,
            "faction_stances": _random_faction_stances(state),
            "secret_loyalty": 0.7,
            "effects": _draft_to_effects_dict(state, {**draft, "effects": effs}),
            "duration": 1,
            "desc": draft.get("body", ""),
        }
        state.pending_secret_decrees.append(decree_full)
        state.wolf_count += 1
        state.statistics["total_decrees"] += 1
        state.remove_edict_draft(draft_id)
        warn = "（狼来了！中旨公信力下降。）" if state.wolf_count >= 3 else ""
        return f"御笔直发（中旨）：「{decree_full['title']}」已下{warn}"
    else:
        # 准奏：经会签生效，入待下诏令
        if len(state.pending_decrees) >= state.decree_bandwidth:
            return "诏令带宽已满！"
        decree_full = {
            "title": draft.get("title", "诏令"),
            "category": "诏令",
            "is_secret": False,
            "is_direct": False,
            "org_hint": org,
            "turn_issued": state.turn,
            "faction_stances": _random_faction_stances(state),
            "effects": _draft_to_effects_dict(state, {**draft, "effects": effs}),
            "duration": 1,
            "desc": draft.get("body", ""),
        }
        state.pending_decrees.append(decree_full)
        state.statistics["total_decrees"] += 1
        state.remove_edict_draft(draft_id)
        return f"已准奏下诏：「{decree_full['title']}」（交三省施行）"


def _random_faction_stances(state: GameState) -> dict:
    stances = {}
    for name in FACTION_NAMES:
        f = state.factions[name]
        sat = f["satisfaction"]
        if sat >= 70:
            stances[name] = 1
        elif sat <= 30:
            stances[name] = -1
        else:
            stances[name] = 0
    return stances


def merge_drafts(state: GameState, draft_ids: list) -> str:
    """将多道诏草汇成一道正式诏书，进入待会签队列。"""
    drafts = [state.get_edict_draft(d) for d in draft_ids]
    drafts = [d for d in drafts if d]
    if not drafts:
        return "无可用诏草。"
    title = "汇纂诏令"
    body = "朕览群臣所奏、与诸草所拟，汇为一道，咸使闻知：\n" + "\n".join(
        f"· {d.get('title','')}：{d.get('body','')[:80]}" for d in drafts)
    all_effs = []
    org_set = set()
    for d in drafts:
        all_effs.extend(d.get("effects", []))
        org_set.add(d.get("org_hint", "政府"))
    org = "政府" if "政府" in org_set else (org_set.pop() if org_set else "政府")
    merged = {
        "title": title, "body": body, "effects": all_effs[:6],
        "org_hint": org, "source_minister": "汇纂",
    }
    for d in drafts:
        state.remove_edict_draft(d.get("id"))
    state.add_edict_draft(merged)
    return f"已将 {len(drafts)} 道诏草汇为「{title}」，重入待会签。"


def _draft_to_effects_dict(state, draft):
    """把诏草的 tier 效果列表换算为数值效果字典。"""
    from ai.client import effects_to_dict
    _, _, authority_index = get_prestige_level(state.prestige)
    authority = max(0.5, min(1.6, 0.5 + authority_index))
    return effects_to_dict(draft.get("effects", []), authority)


def _generate_decree_effects(category: str, idx: int) -> dict:
    effects_map = {
        "财政": [
            {"treasury": 300000, "population_satisfaction": -3},
            {"treasury": -200000, "population_satisfaction": 5},
            {"treasury": 200000, "population_satisfaction": 2},
            {"treasury": 500000, "population_satisfaction": -2},
            {"treasury": 100000, "population_satisfaction": 1},
        ],
        "军事": [
            {"prestige": 2, "treasury": -500000},
            {"prestige": 1, "treasury": -200000},
            {"prestige": 3, "treasury": -300000},
            {"treasury": 200000, "population_satisfaction": 2},
            {"prestige": 2, "treasury": -400000},
        ],
        "人事": [
            {"prestige": 2, "faction_change": {"新党": 5, "旧党": -3}},
            {"prestige": -1, "faction_change": {"新党": -5, "旧党": 3}},
            {"prestige": 1},
            {"prestige": 3, "treasury": -100000},
            {"prestige": 2, "population_satisfaction": 3},
        ],
        "民生": [
            {"population_satisfaction": 5, "treasury": -300000},
            {"population_satisfaction": 3, "treasury": -200000},
            {"population_satisfaction": 4, "treasury": -100000},
            {"population_satisfaction": 6, "treasury": -500000},
            {"population_satisfaction": 2, "prestige": 1},
        ],
        "外交": [
            {"prestige": 3, "treasury": -200000},
            {"prestige": 5, "treasury": -500000},
            {"prestige": -2, "treasury": -300000},
            {"prestige": 2},
            {"prestige": 1, "treasury": -100000},
        ],
    }
    effects = effects_map.get(category, [{"prestige": 0}])
    return effects[min(idx, len(effects) - 1)]


def issue_drafted_decree(state: GameState, minister_advice: str, player_intent: str,
                          ai_client) -> tuple:
    """兼容接口：先预览草稿，再颁布。返回 (消息, 诏书dict)。"""
    d = preview_draft(state, minister_advice, player_intent, ai_client)
    issue_decree(state, {
        "title": d["title"], "category": d["category"],
        "effects": d["effects"], "desc": d["body"], "targets": [],
    })
    return f"已下诏：「{d['title']}」", d


def issue_decree(state: GameState, decree: dict, direct: bool = False) -> str:
    """下达一份普通诏令 / 御笔直发。decree 需含 title/category。
    targets 为受影响派系列表。返回消息。"""
    if direct:
        if state.direct_decree_used >= 2:
            return "本月御笔已用尽。"
        decree_full = {
            "title": decree.get("title", "御笔诏令"),
            "category": decree.get("category", "御笔"),
            "is_secret": False,
            "is_direct": True,
            "turn_issued": state.turn,
            "faction_stances": _random_faction_stances(state),
            "effects": {"prestige": 1},
            "duration": 1,
            "desc": decree.get("desc", ""),
        }
        state.pending_decrees.append(decree_full)
        state.direct_decree_used += 1
        state.wolf_count += 1
        state.statistics["total_decrees"] += 1
        warn = "（警告：狼来了！密旨公信力下降。）" if state.wolf_count >= 3 else ""
        return f"御笔直发：「{decree_full['title']}」{warn}"
    # 普通诏令
    if len(state.pending_decrees) >= state.decree_bandwidth:
        return "诏令带宽已满！"
    cat = decree.get("category", "财政")
    # 计算效果序号：用 targets 不强求，这里直接生成默认效果
    idx = 0
    if "effects" in decree and isinstance(decree["effects"], int):
        idx = decree["effects"]
    decree_full = {
        "title": decree.get("title", "诏令"),
        "category": cat,
        "is_secret": False,
        "is_direct": False,
        "turn_issued": state.turn,
        "faction_stances": _random_faction_stances(state),
        "effects": decree.get("effects") if isinstance(decree.get("effects"), dict) else _generate_decree_effects(cat, idx),
        "duration": 1,
        "targets": decree.get("targets", []),
        "desc": decree.get("desc", ""),
    }
    state.pending_decrees.append(decree_full)
    state.statistics["total_decrees"] += 1
    return f"已下诏：「{decree_full['title']}」"


def issue_secret_decree(state: GameState, target: str, content: str = "") -> str:
    """下达一道密旨。返回消息。"""
    if len(state.pending_secret_decrees) >= 3:
        return "密旨已满（上限3道）。"
    decree = {
        "title": content or "密旨",
        "category": "密旨",
        "is_secret": True,
        "is_direct": False,
        "turn_issued": state.turn,
        "faction_stances": {},
        "secret_loyalty": 0.6,
        "effects": {"prestige": 0},
        "duration": 1,
        "target": target,
    }
    state.pending_secret_decrees.append(decree)
    state.statistics["total_decrees"] += 1
    return f"密旨已下，目标：{target}。"


# ============================================================
# 个人行动 / 施政大项
# ============================================================


def issue_free_decree(state, parse_result, minister, is_secret=False):
    """将 AI 解析结果落地为即时效果或长期任务。

    parse_result: ai.decree.parse_decree 返回结构。
    返回简短日志文本。
    """
    cat = parse_result.get("category", "free_edcree")
    mode = parse_result.get("exec_mode", "longterm")
    params = parse_result.get("params", {}) or {}
    rename = parse_result.get("rename")

    # 行政区更名（即时）
    if rename and rename.get("new_name"):
        _apply_rename(state, rename.get("region", ""), rename.get("new_name"))

    # 御笔直发的可程序落地效果（effects 契约）：改税/节流/拨帑等即时生效，与主路径同构。
    # 这些效果不需走长期任务，落地后反馈在月度结算中体现（改税即时、节流逐月挤出水分）。
    effects = parse_result.get("effects")
    if effects:
        from core.settlement import _apply_decree_effect
        decree_holder = {
            "title": parse_result.get("title", "御笔诏"),
            "effects": {k: int(v) if k not in ("commerce_tax",) else v
                        for k, v in effects.items()},
        }
        _apply_decree_effect(state, decree_holder, [])

    # 固定程序四类：以规则方式登记为长期任务（或即时简报）
    if cat in ("fixed_tech", "fixed_finance", "fixed_army", "fixed_construction"):
        task = parse_result.get("task") or {
            "task_name": parse_result.get("title", "营缮"),
            "months": 12,
        }
        task["category"] = cat
        task["params"] = params
        task["minister"] = minister
        task["progress"] = 0
        task["last_log"] = "已下诏，诸司奉行。"
        if mode == "instant":
            _run_fixed(state, cat, params)
            return f"〔{parse_result.get('title','诏')}〕即时施行：{cat}"
        _enqueue(state, task, is_secret)
        return f"〔{parse_result.get('title','诏')}〕列为长期政务，由{ minister or '有司' }督办。"

    # 机构改制类：完全自由，后果由「威望 + 隐藏忠诚度 + 派系」AI 推演决定
    if cat == "reform_org":
        from core.settlement import settle_reform
        reform = parse_result.get("reform") or {}
        decree_for_settle = {
            "title": parse_result.get("title", "改制诏"),
            "body": parse_result.get("body", ""),
            "text": parse_result.get("body", ""),
            "reform": reform,
            "is_zhongzhi": parse_result.get("is_zhongzhi", False),
            "is_secret": is_secret,
            "faction_stances": _random_faction_stances(state),
        }
        res = settle_reform(state, decree_for_settle)
        report = res.get("court_report", "")
        gazette = res.get("gazette", "")
        rtype = reform.get("reform_type", "改制")
        line = f"〔{parse_result.get('title','改制诏')}〕{rtype}：{report}"
        if gazette:
            line += f"\n〔邸报〕{gazette}"
        # 也记入长期政务，便于月度复盘
        task = parse_result.get("task")
        if task and mode == "longterm":
            task["category"] = "reform_org"
            task["reform"] = reform
            task["minister"] = minister
            task["progress"] = 0
            task["last_log"] = report
            _enqueue(state, task, is_secret)
        return line

    # 自由推演类
    if mode == "instant":
        return f"〔{parse_result.get('title','诏')}〕即时诏下，天下咸闻。"
    task = parse_result.get("task") or {
        "task_name": parse_result.get("title", "政务"),
        "months": 18,
    }
    task["category"] = "free_edict"
    task["params"] = params
    task["minister"] = minister
    task["progress"] = 0
    task["last_log"] = "已下诏，待诸司奉行推演。"
    _enqueue(state, task, is_secret)
    return f"〔{parse_result.get('title','诏')}〕列为长期政务，由{ minister or '有司' }督办。"


def confirm_timeline_break(state: GameState, break_id: str) -> str:
    """将待确认改写位（state.pending_breaks）正式落 timeline。

    由奏报朱批「准予」时调用：候选移除、改写位生效，
    之后硬锚（金崛起/辽衰落/金军南侵）查 timeline 失效，分支事件接管。
    """
    pb = getattr(state, "pending_breaks", {})
    if break_id not in pb:
        return f"无待确认改写位：{break_id}"
    meta = pb.pop(break_id)
    state.timeline[break_id] = {"year": meta.get("year", state.year),
                                "label": meta.get("label", "改写历史")}
    return f"〔朱批〕圣意已决：{meta.get('label', '')}（改写位落档）"


def preview_draft(state: GameState, minister_advice: str, player_intent: str,
                  ai_client) -> dict:
    """由 AI 起草诏书并推断效果，仅返回草稿 dict（不颁布）。"""
    from ai.client import effects_to_dict
    pi = state.get_prestige_info()
    decree = None
    if ai_client and getattr(ai_client, "available", False):
        try:
            decree = ai_client.draft_decree(minister_advice, player_intent, state.get_state_summary(), state=state)
        except Exception as e:
            # 运行时故障：停下，不静默、不伪造
            raise AIRuntimeError(f"拟诏时 AI 叙事中断（{type(e).__name__}）：请检查 AI 配置或网络后重试。") from e
    else:
        # 未配置 AI：停下并提示配置
        raise AIRuntimeError(
            "AI 叙事不可用：拟诏需要 AI 起草。请在「游戏设置 → AI 配置」中完成配置后重试。"
        )
    if not isinstance(decree, dict):
        # 防御性：AI 返回非 dict，视为故障
        raise AIRuntimeError("拟诏失败：AI 返回了非预期格式，请重试。")
    # 把档位 effects 换算为数值 dict
    eff = effects_to_dict(decree.get("effects", []),
                          authority=max(0.5, min(1.6, 0.5 + pi["authority_index"])))
    return {
        "title": decree.get("title", "御制诏书"),
        "category": "御制",
        "effects": eff,
        "body": decree.get("body", player_intent),
        "intent": player_intent,
    }


def issue_kouyu(state: GameState, draft: dict) -> str:
    """口宣（口谕）：即时弱效、不占带宽、可能走样。"""
    from content.data import KOUYU_EFFECT_MULT, KOUYU_DRIFT_CHANCE, KOUYU_DRIFT_DOWN, TIER_ORDER
    effs = draft.get("effects", [])
    applied = {}
    for e in effs:
        if e.get("dim") == "faction_change":
            applied.setdefault("faction_change", {})
            for fn, t in (e.get("value") or {}).items():
                applied["faction_change"][fn] = t
            continue
        if e.get("dim") == "commerce_tax":
            # 工商征率是"设定值"而非增量：优先透传精确 value（0<v≤1），无 value 才回退档位。
            v = e.get("value")
            try:
                v = round(float(v), 2)
            except (TypeError, ValueError):
                v = None
            if v is not None and 0 < v <= 1:
                applied["commerce_tax"] = {"value": v}
            else:
                t = e.get("tier", "无")
                idx = TIER_ORDER.index(t) if t in TIER_ORDER else 0
                if random.random() < KOUYU_DRIFT_CHANCE and idx > 0:
                    idx -= KOUYU_DRIFT_DOWN
                applied["commerce_tax"] = {"tier": TIER_ORDER[idx]}
            continue
        t = e.get("tier", "无")
        idx = TIER_ORDER.index(t) if t in TIER_ORDER else 0
        if random.random() < KOUYU_DRIFT_CHANCE and idx > 0:
            idx -= KOUYU_DRIFT_DOWN
        applied[e.get("dim")] = TIER_ORDER[idx]
    # 用与诏令同一换算
    from ai.client import effects_to_dict
    _, _, authority_index = get_prestige_level(state.prestige)
    authority = max(0.5, min(1.6, 0.5 + authority_index))
    eff_dict = effects_to_dict(
        [{"dim": k, **v} if isinstance(v, dict) else {"dim": k, "tier": v}
         for k, v in applied.items() if k != "faction_change"], authority)
    if "faction_change" in applied:
        eff_dict["faction_change"] = applied["faction_change"]
    # 口谕弱效：整体乘以乘数（对数值）。commerce_tax 是设定税率，不打折、不 int 截断。
    for k in list(eff_dict.keys()):
        if k == "commerce_tax":
            continue
        if isinstance(eff_dict[k], dict):
            eff_dict[k] = {fn: int(d * KOUYU_EFFECT_MULT) for fn, d in eff_dict[k].items()}
        else:
            eff_dict[k] = int(eff_dict[k] * KOUYU_EFFECT_MULT)
    decree_full = {
        "title": draft.get("title", "口谕") + "（口宣）",
        "category": "口谕",
        "is_secret": False,
        "is_direct": True,
        "turn_issued": state.turn,
        "faction_stances": _random_faction_stances(state),
        "effects": eff_dict,
        "duration": 1,
        "desc": draft.get("body", ""),
    }
    state.active_decrees.append(decree_full)
    state.statistics["total_decrees"] += 1
    # 口谕即时生效：直接落地效果（弱效），不再等月度 pending 结算。
    # 否则 active_decrees 仅供展示，改税等 value 键永不落地（历史"口谕清零税率"更深根因）。
    try:
        from core.settlement import _apply_decree_effect
        _apply_decree_effect(state, decree_full, [])
    except Exception:
        pass
    return f"口宣：「{decree_full['title']}」即时传谕（效力稍弱，或失本意）。"


