# -*- coding: utf-8 -*-
"""宋祚 · 诏令/密旨/拟旨/会签 指令族（拆分自 core/commands.py）"""
import logging
import random
from core.game_state import GameState
from core.foundation.common.errors import AIRuntimeError
from content.data import (
    DIRECT_DECREE_MAX,
    FACTION_NAMES,
    get_prestige_level,
)

log = logging.getLogger("commands_decree")


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
        target = params.get("target") or params.get("to")
        # 拨入来源：移库时从何处支出（如「移内帑入国库」source=内藏 target=国库）
        src = params.get("source") or params.get("from")
        # T9 铸钱受控：target="铸钱"/"mint" → 铜资源约束 + 熔耗 20% 净增 80% + 物价>2.0 禁止
        if target in ("铸钱", "mint"):
            if amt <= 0:
                return "铸钱量须为正。"
            from core.settlement_steps import _settle_mint
            _log = []
            ok, msg = _settle_mint(state, _log, amount=amt)
            if ok:
                return f"〔铸钱〕{msg}"
            return f"〔铸钱〕{msg}"
        if not target and src:
            target = "国库"
        if not amt or not target:
            return
        # 审查 P0 修复（造钱漏洞）：原实现「先给目标全额入账、再扣来源」，
        # 而 change_* 内部 max(0, …) 会把来源截断 → 差额凭空产生；未指定来源时
        # 目标更是直接凭空增账；且 target="州郡" 原写作 change_treasury(+amt)，
        # 赈济反给国库加钱（符号反）。现统一为「按来源可付额先截断、下不足上不划」，
        # 口径与 confirm_inner_transfer（同族已修）一致。
        _SRC_DST = {"内藏": "imperial_treasury", "国库": "treasury"}

        def _avail(key: str) -> int:
            return int(getattr(state, key, 0) or 0)

        if target == "州郡":
            # 州郡赈济：国库 → 各州郡府库（成对划转，按路数均分，余数归首路）
            payable = min(amt, _avail("treasury"))
            if payable <= 0:
                return "国库不足，州郡赈济未能拨付。"
            state.change_treasury(-payable)
            _prefs = list(state.prefectures.items())
            if _prefs:
                _each, _rem = divmod(payable, len(_prefs))
                # 🟢 主线 B（M37b）：地方府库写点走桥（未下沉 ⇒ None ⇒ 回落原写法）
                from core.foundation.ledger import local_treasury_bridge as _ltb
                for _i, (_rn, _p) in enumerate(_prefs):
                    _add = _each + (_rem if _i == 0 else 0)
                    if _ltb.local_treasury_add(state, _rn, _add) is None:
                        _p["local_treasury"] = int(_p.get("local_treasury", 0) or 0) + _add
            return f"〔拨付〕州郡赈济 {payable} 贯（自国库列支）。"

        _dst = _SRC_DST.get(target)
        if _dst is None:
            return
        # 未指定来源时按「国库列支」处理（避免凭空增账）；同库同名则无可划
        _src = _SRC_DST.get(src, "treasury") if src else "treasury"
        if _src == _dst:
            return
        payable = min(amt, _avail(_src))
        if payable <= 0:
            return f"{src or '国库'}不足 {amt} 贯，未予拨付。"
        if _src == "treasury":
            state.change_treasury(-payable)
        else:
            state.change_imperial_treasury(-payable)
        if _dst == "treasury":
            state.change_treasury(payable)
        else:
            state.change_imperial_treasury(payable)
        return f"〔移库〕{src or '国库'} → {target}：{payable} 贯。"
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
        state.statistics["total_decrees"] += 1
        state.remove_edict_draft(draft_id)
        # 狼来了已取消（审查 2026-09）：不再累计 wolf_count / 提示公信下降
        return f"御笔直发（中旨）：「{decree_full['title']}」已下"
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
    """下达一份普通诏令 / 御笔直发 / 密谕。decree 需含 title/category。
    targets 为受影响派系列表。返回消息。

    审查 P1 契约对齐：前端 DecreePanel 发 {text,title,minister,is_secret}——
    is_secret=True 转密旨通道（text/title 为密旨内容、minister 为目标）；
    text 落 desc（正文随诏存档/叙事显示），不再静默丢弃玩家正文。
    """
    # ---- 批 5 C2 · 409 未决呈请守卫 ----
    # 颁诏前若有大臣呈请未决 → 显式拦截（把「漏看」从静默丢数据变成 409）。
    _pending = [a for a in (getattr(state, "ai_pending_actions", None) or [])
                if isinstance(a, dict) and a.get("status") == "pending"]
    if _pending:
        _titles = "、".join(str(a.get("title", "无题"))[:12] for a in _pending[:3])
        return (
            f"⚠ 409 未决呈请：尚有 {len(_pending)} 件大臣呈请待朱批（{_titles}…）。"
            f"此刻颁诏，这些事会随本月一并作废，且从未办过。"
            f"请先至「朱批待阅」处置后再颁诏。"
        )
    # 密谕分支（前端密谕勾选：is_secret=True → 走密旨通道，上限 3 道）
    if decree.get("is_secret"):
        target = str(decree.get("target") or decree.get("minister") or "有司")
        content = str(decree.get("text") or decree.get("desc") or decree.get("title") or "密谕")
        return issue_secret_decree(state, target, content)
    if direct:
        if state.direct_decree_used >= DIRECT_DECREE_MAX:
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
        state.statistics["total_decrees"] += 1
        # 两层记忆（Phase 3b）：短期行为日志（全量保留、不注入 AI）+ 短期喂长期（决策实体 + produces）
        try:
            state.short_term_log.append(
                {"turn": state.turn, "kind": "decree", "title": decree_full["title"],
                 "note": "御笔直发", "year": state.year, "month": state.month})
            state.memory.turn = state.turn
            did = state.memory.record_decision(decree_full["title"], {"prestige": 1},
                                               turn=state.turn, note="御笔直发")
            state.memory.add_relation(did, "皇权", "produces", weight=1.0, turn=state.turn, note="皇威")
            state.memory.save(state.memory_slot)
        except Exception:
            pass
        # 狼来了已取消：不再提示中旨公信力下降
        return f"御笔直发：「{decree_full['title']}」"
    # 普通诏令
    if len(state.pending_decrees) >= state.decree_bandwidth:
        return "诏令带宽已满！"
    cat = decree.get("category", "财政")
    # 计算效果序号：用 targets 不强求，这里直接生成默认效果
    idx = 0
    if "effects" in decree and isinstance(decree["effects"], int):
        # 审查 P3：非负校验（负 idx 会在 _generate_decree_effects 里取到列表末端错误项）
        idx = max(0, int(decree["effects"]))
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
        "desc": decree.get("desc") or decree.get("text", ""),   # 正文随诏落档（审查 P1）
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
    # B5-4/B5-5（2026-11 接线）：**下达这一刻就定 `decree_id` 并建立知情范围**。
    # 此前全仓从不写该键 ⇒ `settlement_decree` 的 `if _did:` 恒假、
    # **密令泄露推演从未执行过**、`_secret_contacts` 恒返回 `[]`。
    # 顺序要紧：必须先有 id 再 seal，否则知情范围会挂在 `title` 上，
    # 而结算时用的是另一个 id ⇒ 查不到授权人。
    try:
        from core.decree_confirm import ensure_decree_id
        ensure_decree_id(state, decree)
    except Exception:                # noqa: BLE001 — 补id 失败不阻断下旨
        pass
    try:
        from content.ministers.data import MINISTERS
        if isinstance(target, str) and target in MINISTERS:
            from core.decree_confidential import seal_secret_decree
            seal_secret_decree(state, decree, authorized=[target],
                               channel="奏对", turn=state.turn)
    except Exception as _se_e:      # noqa: BLE001 — 建知情范围失败不阻断下旨
        logging.getLogger("settlement").warning(
            "[密旨] 知情范围未建立：%s", _se_e, exc_info=True)
    return f"密旨已下，目标：{target}。"


# ============================================================
# 个人行动 / 施政大项
# ============================================================


def issue_free_decree(state, parse_result, minister, is_secret=False):
    # ---- 批 5 C2 · 409 未决呈请守卫（与 issue_decree 同款）----
    _pending = [a for a in (getattr(state, "ai_pending_actions", None) or [])
                if isinstance(a, dict) and a.get("status") == "pending"]
    if _pending:
        _titles = "、".join(str(a.get("title", "无题"))[:12] for a in _pending[:3])
        return (
            f"⚠ 409 未决呈请：尚有 {len(_pending)} 件大臣呈请待朱批（{_titles}…）。"
            f"此刻颁诏，这些事会随本月一并作废，且从未办过。"
            f"请先至「朱批待阅」处置后再颁诏。"
        )
    """将 AI 解析结果落地为即时效果或长期任务。

    parse_result: ai.decree.parse_decree 返回结构。
    返回简短日志文本。
    """
    cat = parse_result.get("category", "free_edict")
    # 审查修复：未知 category 原会一路走到底、**无 return**（返回 None）→ 诏令被
    # 静默丢弃，而调用方拿到 None 后往往仍提示成功。前端降级路径正是传 "custom"。
    # 另原默认值拼写为 "free_edcree"（少一个 t），缺 category 时同样落入未知分支。
    # 现统一将未登记类别按「自由诏」落地，不再静默丢失。
    if cat not in ("fixed_tech", "fixed_finance", "fixed_army", "fixed_construction",
                   "reform_org", "free_edict"):
        cat = "free_edict"
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

    # 新作物/新矿注册（预留接口落地）：AI 推演「劝种新作物/开新矿/引进新物产」时，
    # 经 new_material 契约注册进物资格局；价格程序默认，产量开局 0 随劝种/开矿演化。
    new_mat = parse_result.get("new_material")
    if new_mat and new_mat.get("dim"):
        from content.data import register_raw_material, MATERIAL_PRICE_BASE
        dim = str(new_mat.get("dim", "")).strip()
        if dim and dim not in MATERIAL_PRICE_BASE:
            name = new_mat.get("name", dim)
            unit = new_mat.get("unit", "斤")
            # 传入 state：同时为新区建好资源槽，否则后续工程/作坊读该维会
            # KeyError（中断整月结算）或按缺料永久停滞（审查修复）
            register_raw_material(dim, unit, 150, state=state)  # 新物资默认价 150 钱/单位
            log_new = f"[新物产] 诏引「{name}」（{dim}，{unit}），已入物资格局，各路可劝种/开矿增其产。"
            _enqueue(state, {"task_name": f"推广{name}", "months": 12, "category": "fixed_tech",
                             "params": params, "minister": minister, "progress": 0,
                             "last_log": log_new}, is_secret)
            return f"〔{parse_result.get('title','诏')}〕{log_new}"

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

    # 自由推演类：接入 free_effect 通用契约（言枢密 v3）——AI 推演效果契约，
    # 程序侧拒绝式校验落地（白名单/CAP/cost 承受/失衡拒绝）；AI 缺失/失败 → 诏令不落地并明确报错（不降级）。
    if cat == "free_edict":
        from core.free_effect import _apply_free_effect
        from ai.client import AIClient
        ai = AIClient.load_saved()
        if ai is None or not getattr(ai, "available", False):
            return f"〔{parse_result.get('title', '诏')}〕AI 未配置，诏令未落地（请先在 AI 设置配置 OpenAI 兼容 API）。"
        contract = ai.free_effect_decide(
            getattr(state, "posture", ""), parse_result.get("title", ""), parse_result.get("body", ""))
        if isinstance(contract, dict) and not contract.get("_error"):
            eff_log = _apply_free_effect(state, contract)
            # 两层记忆（Phase 3b）：短期行为日志 + 短期喂长期（决策实体 + produces）
            try:
                state.short_term_log.append(
                    {"turn": state.turn, "kind": "decree", "title": parse_result.get("title", "自由诏"),
                     "note": "自由诏落地", "year": state.year, "month": state.month})
                state.memory.turn = state.turn
                did = state.memory.record_decision(
                    parse_result.get("title", "自由诏"),
                    str({k: v for k, v in (contract.get("effects") or {}).items()}),
                    minister=minister or "", turn=state.turn,
                    supports=(), opposes=(), note="自由诏落地")
                for k, v in (contract.get("effects") or {}).items():
                    # 审查 P2-8 修复：note 不存原始数值（防经 summarize 回灌 AI 泄漏量级）。
                    # 数值→档位词归一（用 normalize_tier 反查不可行，改用定性描述）。
                    _note_v = v
                    if isinstance(v, (int, float)):
                        try:
                            from content.data import FREE_EFFECT_CAP
                            _cap = FREE_EFFECT_CAP.get(k, 1)
                            _ratio = abs(v) / max(_cap, 1)
                            _note_v = ("微" if _ratio < 0.25 else "小" if _ratio < 0.5
                                       else "中" if _ratio < 0.75 else "大")
                        except Exception:
                            _note_v = "中"
                    state.memory.add_relation(did, str(k), "produces", weight=1.0,
                                              turn=state.turn, note=f"效果·{_note_v}")
                state.memory.save(state.memory_slot)
            except Exception:
                pass
            return f"〔{parse_result.get('title', '诏')}〕" + "；".join(eff_log)
        # 审查修复：玩家文案不得直出英文错误码（原样输出 AI_CONTRACT_FAILED 等）。
        # 现把码映射为中文，原始码只入服务端日志。
        from content.data import AI_ERROR_CODES
        _raw = contract.get("_error", "") if isinstance(contract, dict) else ""
        if _raw:
            log.warning("[decree] 契约失败: %s", _raw)
        return (f"〔{parse_result.get('title', '诏')}〕AI 推演未成"
                f"（{AI_ERROR_CODES.get(_raw, '诏意未能落地')}），诏令未落地。")


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
            # 运行时故障：停下，不静默、不伪造（2026-09-18：透传底层错误码）
            log.warning("[decree] 拟诏叙事中断: %s", e)
            raise AIRuntimeError(
                "拟诏时 AI 叙事中断：请检查 AI 配置或网络后重试。",
                code=getattr(e, "code", "") or "",
            ) from e
    else:
        # 未配置 AI：停下并提示配置（2026-09-18：补 code，使 HTTP 层可回精确错误码）
        raise AIRuntimeError(
            "AI 叙事不可用：拟诏需要 AI 起草。请在「游戏设置 → AI 配置」中完成配置后重试。",
            code="AI_NOT_CONFIGURED",
        )
    if not isinstance(decree, dict):
        # 防御性：AI 返回非 dict，视为故障（2026-09-18：补错误码）
        raise AIRuntimeError("拟诏失败：AI 返回了非预期格式，请重试。", code="AI_INVALID_JSON")
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


def _kouyu_drift_factor(state) -> tuple:
    """口谕**走样**判定（B5-4· 2026-11 废除固定概率）。

    旧实现是 `random.random() < KOUYU_DRIFT_CHANCE`（固定 0.30）——
    与 B5-4「废除『固定 0.6/30% 假装弱效』」的要求冲突：
    走样与否**与吏治无关**，纯随机，治理无从下手（审计 J-2 同类问题）。

    现口径：走样概率＝**该路吏胥把持度**（`clerks.decree_execution_mult`
    的补数：把持越高越易走样），治理方向与 §16.4 一致。
    读数缺失 ⇒ `prob=None` ⇒ **不掷骰、不走样**（拒绝式：不按 0.30 假装）。

    返回 `(prob: float|None, source: str)`。
    """
    try:
        from core.clerks import totals as _cl_totals
        mult = float((_cl_totals(state) or {}).get("decree_mult"))
    except Exception:                # noqa: BLE001 — 读数不可用
        return None, "undefined"
    # `decree_mult` 越小＝把持越重；把它反比为走样压力。
    p = max(0.0, min(0.9, 1.0 - mult))
    return p, "clerks_decree_mult"


def issue_kouyu(state: GameState, draft: dict) -> str:
    """口宣（口谕）：即时生效、不占带宽。

    **强度与走样均改由吏治单点读数决定**（B5-4 · 2026-11）：
    旧实现用固定 `KOUYU_EFFECT_MULT = 0.6` 与 `KOUYU_DRIFT_CHANCE = 0.30`，
    属"假装弱效/走样"的第二口径点；现统一走 `clerks`（§16.4 吏治是唯一强关联）。
    读数缺失 ⇒ **不按固定值假装**，标记 `undefined` 并按原档位如实登记。
    """
    from content.data import KOUYU_DRIFT_DOWN, TIER_ORDER
    try:
        from core.clerks import decree_execution_mult
        _gov = decree_execution_mult(state)      # 吏治单点（唯一强关联）
    except Exception:                # noqa: BLE001
        _gov = None
    _drift_p, _drift_src = _kouyu_drift_factor(state)
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
                if _drift_p and random.random() < _drift_p and idx > 0:
                    idx -= KOUYU_DRIFT_DOWN
                applied["commerce_tax"] = {"tier": TIER_ORDER[idx]}
            continue
        t = e.get("tier", "无")
        idx = TIER_ORDER.index(t) if t in TIER_ORDER else 0
        if _drift_p and random.random() < _drift_p and idx > 0:
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
    # 口谕弱效：改由**吏治折扣**决定（不再用固定 0.6）。
    # 缺失 ⇒ `_gov is None` ⇒ **不打折也不假装**，按原值登记并留痕。
    if _gov is not None:
        _k = max(0.0, min(1.0, float(_gov)))
        for k in list(eff_dict.keys()):
            if k == "commerce_tax":
                continue          # 设定税率不打折（与旧口径一致）
            if isinstance(eff_dict[k], dict):
                eff_dict[k] = {fn: int(d * _k) for fn, d in eff_dict[k].items()}
            else:
                eff_dict[k] = int(eff_dict[k] * _k)
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
    # P2-3（M5）：原实现 `except Exception: pass` 后**无条件**返回成功文案 → 改税率/发帑
    # 实际未落地，玩家却看到"即时传谕"（历史"口谕清零税率"根因会以更隐蔽的形式复现）。
    # 现失败即如实回报，成功文案只在真正落地时给。
    try:
        from core.settlement import _apply_decree_effect
        _apply_decree_effect(state, decree_full, [])
    except Exception as e:  # noqa: BLE001 — 单条口谕失败不得中断命令层
        log.warning("[kouyu] 口谕效果落地失败：%s", e, exc_info=True)
        return (f"口宣：「{decree_full['title']}」**未落地**"
                f"（{type(e).__name__}，已记服务端日志）——该谕未见施行，请改由正式诏令下颁。")
    return f"口宣：「{decree_full['title']}」即时传谕（效力稍弱，或失本意）。"


# ============================================================
# 对话口谕内帑调拨（商量确认式，用户定稿）
#   皇帝在召对中谕「发内帑 X 贯入国库」→ 大臣商量回奏（不即时划账）→
#   皇帝当场点「准」confirm 守恒移库 /「罢」cancel 不动账。
#   皇帝私库乾纲独断：金额精确整数贯，不受口谕弱效/走样约束（非模糊指令）。
# ============================================================
def propose_inner_transfer(state: GameState, amount) -> str:
    """口谕发内帑入国库（商量确认式）：记录 pending_inner_transfer，不划账。"""
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return "金额须为整数贯"
    if amount <= 0:
        return "金额须为正整数贯"
    if amount > state.imperial_treasury:
        return f"内帑不足（现有 {state.imperial_treasury} 贯），不予记录"
    state.pending_inner_transfer = {"amount": amount, "turn": state.turn}
    return f"已谕：发内帑 {amount} 贯入国库，待准（不即时划账）"


def confirm_inner_transfer(state: GameState) -> str:
    """准：守恒移库（国库 +amount、内帑 -amount），清除 pending。

    审查 P1-2 修复（造钱漏洞）：提议时校验过内帑余额，但确认时可能已被其它结算
    消耗。原实现直接按原额划拨：国库 +amt，而 change_imperial_treasury 内部
    max(0,…) 会把内帑截断（少扣），差额凭空产生。现执行前按当前内帑余额复检，
    不足则作罢（不划账、清 pending 并提示重新商议）。
    """
    p = getattr(state, "pending_inner_transfer", None)
    if not p:
        return "无待准之内帑调拨"
    try:
        amt = int(p.get("amount", 0))
    except (TypeError, ValueError):
        amt = 0
    state.pending_inner_transfer = None
    if amt <= 0:
        return "调拨额非法，已作罢"
    avail = int(getattr(state, "imperial_treasury", 0) or 0)
    if avail < amt:
        return (f"内帑现存仅 {avail} 贯，不足原议 {amt} 贯，调拨未行（已作罢）。"
                f"可重新商议额度。")
    state.change_treasury(amt)
    state.change_imperial_treasury(-amt)
    return f"准：内帑 {amt} 贯入国库"


def cancel_inner_transfer(state: GameState) -> str:
    """罢：清除 pending，不动账。"""
    if getattr(state, "pending_inner_transfer", None):
        state.pending_inner_transfer = None
        return "罢：不动内帑"
    return "无待准之内帑调拨"


# ============================================================
# 对话口谕内帑调拨：金额解析（迁移补齐：原 ui/panels_govern.py 模块级函数，
# Tk 废弃后随内帑调拨逻辑归位本模块）
# ============================================================
_CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000, "万": 10000}


def _cn_amount(s: str):
    """中文数字 → int（五十万=500000、十二万=120000、三千=3000）。"""
    total, num = 0, 0
    for ch in s:
        v = _CN_NUM.get(ch)
        if v is None:
            return None
        if v == 10000:
            total = (total + num if (total or num) else 1) * 10000
            num = 0
        elif v >= 10:
            total += (num if num else 1) * v
            num = 0
        else:
            num = v
    return total + num


def parse_inner_amount(text: str):
    """从召对输入提取内帑调拨金额（贯）；支持 500000 / 50万 / 五十万；失败返回 None。"""
    t = str(text).replace(",", "").replace("，", "")
    import re
    m = re.search(r"(\d+)\s*万", t)
    if m:
        return int(m.group(1)) * 10000
    m = re.search(r"\d+", t)
    if m:
        return int(m.group(0))
    m = re.search(r"[零一二两三四五六七八九十百千万]+", t)
    if m:
        return _cn_amount(m.group(0))
    return None


# 兼容旧名（Tk 面板曾用 _parse_inner_amount）
_parse_inner_amount = parse_inner_amount


