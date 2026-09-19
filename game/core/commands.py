# -*- coding: utf-8 -*-
"""宋祚 · 与 UI 无关的游戏命令层

把"可玩逻辑"（颁诏、召见、施政、个人行动、回合结算、事件、结局、遣使缔约、
拨帑养廉）从界面层抽离出来，保证游戏逻辑只有单一来源。

消费方：`backend/`（FastAPI；`backend/client.py` 的分派表把动作名映射到本层函数，
Electron 前端经 HTTP 调用）与测试。**Tkinter GUI 已废弃删除**——原文「供 GUI 版
(ui/gui.py)使用」所述消费方已不存在，此处据实更新。
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
    propose_inner_transfer, confirm_inner_transfer, cancel_inner_transfer,
)


def new_game(difficulty: str = "史实", ai_client=None) -> GameState:
    """创建新游戏（含记忆知识库开局基线：大臣/机构/派系实体）。"""
    state = GameState(difficulty=difficulty)
    # 开局邸报（参考《明末：捞金模拟器》）：文言局势 + 待办三事，注入 state.opening_gazette
    try:
        from content.legacy_gazette import build_opening_gazette
        state.opening_gazette = build_opening_gazette()
    except Exception:
        state.opening_gazette = {}
    # 帝国修正（legacies）：开局即存在的条件式长期修正符
    try:
        from core.legacy_mechanic import init_legacies
        init_legacies(state)
    except Exception:
        state.legacies = {}
    # 国策树（focus）：五大分支（政务/军事/科学/内卫/税务）
    try:
        from core.focus_mechanic import init_focus_tree
        init_focus_tree(state)
    except Exception:
        state.focus_tree = {}
    # 记忆基线：开局录大臣/派系/机构/外部政权实体
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
    # 审查 P1-6 修复：原实现 `[n for n,f in state.factions.items() if f["leader"]==leader][0]`
    # 对非派系领袖的大臣直接 IndexError 崩溃。改为：命中派系领袖优先；否则按大臣档案
    # 反查其所属派系（仍属某派系则按该派系生效）；两者皆无则明确拒绝。
    faction = next((n for n, f in state.factions.items()
                    if f.get("leader") == leader), None)
    if faction is None:
        try:
            from content.ministers.data import MINISTERS
            _fac = (MINISTERS.get(leader) or {}).get("faction", "")
            if _fac in state.factions:
                faction = _fac
        except Exception:
            faction = None
    if faction is None:
        return f"{leader}未领一派、亦无所属派系，无从以派系之名行事。"
    f = state.factions[faction]
    # 行动效果
    if action == "安抚":
        f["satisfaction"] = max(0, min(100, f["satisfaction"] + 4))
        msg = f"{leader}心甚慰，对陛下更忠恳了。"
    elif action == "施恩":
        cost = 200_000
        if state.treasury < cost:
            msg = f"欲厚赏 {leader}，然国库不足二十万贯，赏赉未行。"
            return msg
        f["satisfaction"] = max(0, min(100, f["satisfaction"] + 7))
        f["influence"] = max(0, min(100, f["influence"] + 2))
        # 守恒：国库 → 该派系领袖对应官僚 POP（有则转入，无则按各路官僚池摊）
        moved = 0
        for road, p in state.prefectures.items():
            guan = (p.get("pops") or {}).get("官僚")
            if isinstance(guan, dict) and guan.get("size", 0) > 0:
                moved = state.transfer_money("treasury", f"pop:{road}:官僚", cost)
                if moved > 0:
                    break
        if moved <= 0:
            moved = state.transfer_money("treasury", "imperial_treasury", cost)
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
    # 便于 dev/replay 回放与平衡 A/B 对比。
    # 注意：不可用 hash()（Python 哈希随机化导致跨进程不一致），改用确定性多项式。
    # 审查 P3 修复：_rnd 即全局 random 模块本体，原 `_rnd.seed(_seed)` 会改写全局
    # 随机状态（注释所称「不污染」不成立）。现改为「暂存 → 定种子取事件 → 恢复」，
    # 既保留可复现性，又不影响后续全局随机调用。
    import random as _rnd
    _seed = (state.year * 1000003 + state.month * 10007 + state.turn * 131) & 0xFFFFFFFF
    _stash = _rnd.getstate()
    try:
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
    finally:
        _rnd.setstate(_stash)
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
        # 2026-09-18：补 code（原仅传消息，`AIRuntimeError.code` 恒为空，
        # 使 /api/advance 无法回精确错误码 —— 见 backend/server.py 的 503 分支）
        raise AIRuntimeError(AI_ERROR_CODES.get("AI_NOT_CONFIGURED", "AI 未接入"),
                             code="AI_NOT_CONFIGURED")
    # **回合结算专用 provider**（用户定稿 2026-09-19：过回合结算时调用 agnes-2.5-flash）：
    # prelude + 12 步推演 + 月报整体在 `settlement_mode()` 内执行；未配置 settle_model 时
    # 该上下文不切换（等价于原行为），测试替身没有该方法也不受影响。
    import contextlib as _ctx
    _mode = getattr(ai_client, "settlement_mode", None)
    with (_mode() if callable(_mode) else _ctx.nullcontext(False)):
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
    # 审查 2026-09：把本回合 AI 用量（玩家操作+推演）落成一行附表（calls/tokens/时间）后清零，
    # 供前端「治务 · AI计量」表格展示。放在 finish_turn 前，label 用本回合年月。
    _flush_ai_token(state, ai_client)
    finish_turn(state)
    return log, report


def _flush_ai_token(state: GameState, ai_client) -> None:
    """把 AIClient 本回合累计的 token 用量写进 state.ai_token_log（一行），然后重置计量。

    计量含本回合内玩家操作（拟旨/召对）与推演族的全部 AI 调用；回合推进时成行入账。
    失败静默（计量绝不影响结算）。
    """
    try:
        u = getattr(ai_client, "token_usage", None)
        if not u or int(u.get("calls", 0) or 0) <= 0:
            return
        _calls = int(u.get("calls", 0) or 0)
        _p = int(u.get("prompt", 0) or 0)
        _c = int(u.get("completion", 0) or 0)
        try:
            from datetime import datetime
            _ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            _ts = f"{state.year}年{state.month}月"
        log = getattr(state, "ai_token_log", None)
        if not isinstance(log, list):
            log = []
            state.ai_token_log = log
        log.append({
            "turn": state.turn,
            "label": f"{getattr(state, 'era_name', '')}{state.year}年{state.month}月",
            "calls": _calls,
            "prompt_tokens": _p,
            "completion_tokens": _c,
            "total_tokens": _p + _c,
            "ts": _ts,
        })
        if len(log) > 500:
            del log[: len(log) - 500]
        if hasattr(ai_client, "reset_meter"):
            ai_client.reset_meter()
    except Exception:
        pass


def _ai_prelude(state, ai_client):
    """结算前 AI 推演族（同步版）：economy 强制推演 + 按需唤醒注入，写 state 槽位。

    economy 缺失/失败 → **拒绝式**（抛 AIRuntimeError，不静默兜底、不伪造档位）；
    其余唤醒契约失败仅跳过（settle 读不到槽位走本地兜底，不阻断结算）。
    """
    from content.data import AI_ERROR_CODES
    try:
        eco = ai_client.economy_decide(state.posture)
    except Exception as e:
        # 审查修复：玩家可见文案不直出异常类名；原文只入服务端日志
        print(f"[settle] 经济推演失败: {e!r}", flush=True)
        # 2026-09-18 修复：保留底层错误码——AIClient 已把 401/403 映射为 AI_AUTH_FAILED、
        # 超时映射为 AI_TIMEOUT（R2 修复）；此处原样丢弃，导致 HTTP 层无法给出精确诊断
        # （`AIRuntimeError` 的 `code` 字段形同虚设）。现透传，无码时留空由上层兜底。
        raise AIRuntimeError(
            "经济推演失败：请检查 AI 配置或网络后重试。",
            code=getattr(e, "code", "") or "",
        ) from e
    if not isinstance(eco, dict) or eco.get("_error"):
        raise AIRuntimeError(AI_ERROR_CODES.get("AI_CONTRACT_FAILED", "AI 输出不满足契约"),
                             code="AI_CONTRACT_FAILED")
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


def _snapshot_state(state) -> dict:
    """结算前状态快照（供失败回滚）：深拷贝各状态字段，不可拷贝对象（SQLite 连接/锁等）跳过。

    另记录 `__mem_turn__` 记忆水位（审查 A2）：记忆库含 SQLite 连接，深拷贝必被
    跳过，无法随字段一并还原，故单独记回合号，由 `_restore_state` 按水位截断。
    """
    import copy
    snap: dict = {}
    for k, v in list(getattr(state, "__dict__", {}).items()):
        try:
            snap[k] = copy.deepcopy(v)
        except Exception:  # noqa: BLE001
            continue  # 不可深拷贝（连接/锁等）→ 保持原引用，回滚时不动该字段
    snap["__mem_turn__"] = int(getattr(state, "turn", 0) or 0)
    return snap


def _restore_state(state, snap: dict) -> None:
    """把快照字段写回 state（不删除快照之后新增的瞬态键，如 _economy_ai）。

    审查 A2 补齐：还原 state 后按快照水位截断记忆库（主库 + 对话库）中**失败回合
    已写入**的关系/召对/总结。缺此步则重试结算时同一事实被重复 upsert，关系权重
    叠加（不可逆）；召对残留还会污染「卿前番之言」注入。记忆库不可深拷贝故不能
    走字段还原，只能按水位截断（各库 `rollback_after`）。
    """
    for k, v in snap.items():
        if k.startswith("__"):
            continue          # 内部水位标记不可 setattr 回 state
        try:
            setattr(state, k, v)
        except Exception:  # noqa: BLE001
            continue
    _turn = snap.get("__mem_turn__")
    if _turn is None:
        return
    _objs = [getattr(state, "memory", None)]
    try:
        from memory.dialogue_memory import get_dialogue_memory
        _objs.append(get_dialogue_memory(state))
    except Exception:  # noqa: BLE001
        pass
    for _obj in _objs:
        _fn = getattr(_obj, "rollback_after", None)
        if callable(_fn):
            try:
                _fn(int(_turn))
            except Exception:  # noqa: BLE001
                pass          # 记忆回滚失败不阻断状态回滚（已记录于自身日志）


def advance_and_settle(state, ai_client=None) -> tuple:
    """事件触发 + 月度结算的原子封装。返回 (events, log, report)。

    审查修复（幽灵事件 / 半更新）：advance_month 会向 state.active_events 追加
    当月事件、并可能置 game_over，而快照回滚只在 settle_local 内部建立
    —— 晚于该写入。于是结算失败回滚后，事件仍留在场且已计一次：重试玩家会看到
    重复/幽灵事件，README 所称「月度结算异常快照回滚」并未覆盖此路径。
    本函数把「取事件」与「结算」纳入同一快照，异常时整体回滚后再抛出。
    """
    snap = _snapshot_state(state)
    try:
        events = advance_month(state)
        log, report = settle_turn(state, ai_client)
        # 审查补齐（奏折面板恒空的根因）：state.memorials 注释为「待审奏折（每回合
        # 开始按局势自动上折，君主批红）」，但全库**无任何写入方**。而 AI 侧
        # generate_memorials 与无 key 时的模板兜底 fallback_memorials 早已就绪，
        # 只是从未被调用。现按回合生成：AI 可用走 AI，否则走模板兜底（皆真内容）。
        # 本步在快照范围内，失败随结算一并回滚。
        try:
            _memos = None
            if ai_client is not None and getattr(ai_client, "available", False):
                _res = ai_client.generate_memorials(
                    getattr(state, "posture", ""), state=state, count=3)
                _memos = (_res or {}).get("memorials") if isinstance(_res, dict) else None
            if not _memos:
                from ai.narrative_fallback import fallback_memorials
                _fb = fallback_memorials(state=state, turn=getattr(state, "turn", 0))
                _memos = (_fb or {}).get("memorials") if isinstance(_fb, dict) else None
            if _memos:
                state.memorials = _memos
        except Exception as _e:  # noqa: BLE001
            print(f"[memorials] 上折未成: {_e!r}", flush=True)
        return events, log, report
    except Exception:  # noqa: BLE001
        _restore_state(state, snap)
        raise


def settle_local(state) -> list:
    """本地 12 步结算（确定性，主线程执行）：委托 run_monthly_settlement（含回合推进）。

    不含终局判定/自动存档（由 finish_turn 统一收尾），供同步 settle_turn 与
    T6 异步拆分（后台 AI 推演族 → 主线程本函数 → 叙事后补）共用。

    审查 P1-3 修复（半结算脏状态）：结算内含守恒断言（太仓恒等/财政恒等），一旦触发
    会从本函数抛出，而此前步骤的税收/扣款/POP/军队变更均已就地生效且无回滚，
    state.turn 也未推进 → 下次结算在脏状态上重复计征，长期系统性偏差。
    现于结算前快照状态，异常时回滚后再抛出（记忆库等不可拷贝对象保持原引用）。
    """
    import logging as _lg
    snap = _snapshot_state(state)
    try:
        return run_monthly_settlement(state)
    except Exception as e:  # noqa: BLE001
        _restore_state(state, snap)
        _lg.getLogger("settle_local").error(
            "月度结算异常，已回滚状态快照（回合未推进，可安全重试）：%s", e)
        raise


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
            # 容量治理（补接线 memory_graph._ARCHIVE_INTERVAL=12）：归档 w_eff 低于阈值的
            # 旧史——只打 archived 标记、不物理删除，检索不再注入陈旧关系。原实现 archive()
            # 零调用方 → 关系/实体只增不减，而 save() 每回合 DELETE 后全量重写，IO 随历史
            # 线性放大。顺序：先总结（概要已覆盖本轮）再降权。
            _aslot = getattr(mg, "_slot", None)
            if _aslot is None:
                _aslot = getattr(state, "memory_slot", None)
            if _aslot is not None:
                mg.archive(_aslot)
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
    """处理玩家对某事件的选择，返回效果叙述。

    审查 P1-12：event 须为**完整事件对象**（含 choices）。传入标题字符串等非法值时
    明确拒绝（原实现会在 apply_event_choice 内抛 AttributeError 崩溃）。
    """
    if not isinstance(event, dict):
        return "事件抉择失败：缺少完整事件对象（无法取得选项）。"
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
    # 清除该事件在场标记（审查 P2：title 为空时 `"" not in msg` 恒 False 会清空全部在场事件，
    # 故空标题直接跳过清理）
    title = event.get("title", "")
    if title:
        state.active_events = [e for e in state.active_events
                               if title not in e.get("message", "")]
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


# ============================================================
# AI 待批行动：批红 / 驳回（严格模式落地通道）
# ============================================================
def approve_ai_action(state: GameState, action_id: str) -> str:
    """批红一条 AI 待批行动；按 kind 落地。返回叙述。"""
    item = state.pop_ai_pending(action_id)
    if not item or item.get("status") != "pending":
        return "无此待批条目（或已处置）。"
    kind = item.get("kind", "")
    payload = item.get("payload") or {}
    title = item.get("title", "无题")

    try:
        if kind == "secret_order":
            if payload.get("longterm"):
                state.longterm_secret.append({
                    "title": title, "summary": item.get("summary", ""),
                    "task_name": title, "months": 12, "progress": 0,
                })
            else:
                state.pending_secret_decrees.append({
                    "title": title, "summary": item.get("summary", ""),
                    "is_secret": True, "secret_loyalty": 0.6,
                    "effects": {}, "duration": 1,
                    "faction_stances": _random_faction_stances(state),
                })
            state.set_ai_pending_status(action_id, "approved")
            return f"批红：密令「{title}」奉行。"

        if kind == "propose_governance":
            state.longterm_public.append({
                "title": title, "summary": item.get("summary", ""),
                "effects": payload.get("effects") or {},
                "task_name": title, "months": 18, "progress": 0,
            })
            state.set_ai_pending_status(action_id, "approved")
            return f"批红：施政「{title}」立案在办。"

        if kind == "military_dispatch":
            return _apply_military_dispatch(state, action_id, payload, title)

        state.set_ai_pending_status(action_id, "rejected")
        return f"未知待批类型：{kind}，已驳回。"
    except Exception as e:  # noqa: BLE001
        state.set_ai_pending_status(action_id, "rejected")
        # 审查修复：玩家可见文案不直出异常类名；原文只入服务端日志
        print(f"[approve_ai_action] 落地失败: {e!r}", flush=True)
        return f"批红未成：{title}（该条已驳回）。"


def reject_ai_action(state: GameState, action_id: str) -> str:
    item = state.pop_ai_pending(action_id)
    if not item or item.get("status") != "pending":
        return "无此待批条目（或已处置）。"
    state.set_ai_pending_status(action_id, "rejected")
    return f"已驳回：「{item.get('title', '')}」。"


def _apply_military_dispatch(state, action_id, payload, title) -> str:
    """批红军令：先校验钱粮，增募钱不够则整单拒绝。"""
    tier = str(payload.get("army", "禁军"))
    act = str(payload.get("action", "整编"))
    tgt = str(payload.get("target", "") or "")
    scale = max(1, min(5, int(payload.get("scale", 3) or 3)))
    if tier in ("西军", "北军"):
        tier = "禁军"
    units = [u for u in state.army_units if u.tier == tier]
    if not units:
        state.set_ai_pending_status(action_id, "rejected")
        return f"批红驳回：无此军籍 {tier}。"

    if act in ("操练", "整编"):
        for u in units:
            u.training = max(0, min(100, u.training + scale * 2))
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{tier} {act}（档 {scale}）已饬行。"

    if act == "增募":
        _N = scale * 2000
        planned = []  # (unit, road, taken)
        total = 0
        for u in units:
            station = getattr(u, "station", "")
            if station not in state.prefectures:
                continue
            p = state.prefectures[station]
            want = _N
            taken = 0
            t = 0
            if u.tier == "厢军":
                ref = int(p.get("refugees", 0))
                t = min(want, ref)
                taken += t
            farm = int(p["pops"]["农"]["size"])
            t2 = min(want - taken, max(0, farm - farm // 2))
            taken += t2
            if taken > 0:
                planned.append((u, station, taken, t, t2))
                total += taken
        cost = total * 5
        if total <= 0:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：无可募之丁。"
        if state.treasury < cost:
            state.set_ai_pending_status(action_id, "rejected")
            return f"批红驳回：增募需 {cost} 贯，国库不足，整单不行（人口未扣）。"
        # 先扣人口再扣款（钱不够已在上方拒绝）
        for u, station, taken, from_ref, from_farm in planned:
            p = state.prefectures[station]
            if from_ref:
                p["refugees"] = max(0, int(p.get("refugees", 0)) - from_ref)
            if from_farm:
                p["pops"]["农"]["size"] = max(0, int(p["pops"]["农"]["size"]) - from_farm)
            if u.branches:
                bk = next(iter(u.branches))
                u.branches[bk] = u.branches.get(bk, 0) + taken
            else:
                u.branches["轻步兵"] = taken
            p["pops"]["兵"]["size"] = p["pops"]["兵"].get("size", 0) + taken
            u.training = max(0, min(100, u.training + scale))
        # 守恒：国库 → 兵 wealth
        paid = 0
        for road in state.prefectures:
            if paid >= cost:
                break
            paid += state.transfer_money("treasury", f"pop:{road}:兵", cost - paid)
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{tier} 增募 {total} 人，縻饷 {paid} 贯。"

    if act == "调赴" and tgt:
        for u in units:
            u.station = tgt
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{tier} 调赴 {tgt}。"

    state.set_ai_pending_status(action_id, "rejected")
    return f"批红驳回：未识军令动作「{act}」。"


__all__ = [
    "new_game", "audience_minister", "issue_decree", "issue_secret_decree",
    "do_personal_action", "choose_imperial_action", "choose_major_policy", "advance_month", "settle_turn",
    "settle_local", "finish_turn", "monthly_report_args",
    "resolve_event", "save", "load", "save_slots", "conclude",
    "audience_dialogue", "audience_dialogue_prepare", "audience_dialogue_apply",
    "envoy_diplomacy",
    "issue_drafted_decree", "preview_draft",
    "approve_ai_action", "reject_ai_action",
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
def _record_dialogue_row(state, minister_name: str, speaker: str, text: str,
                         topic: str = "", intent: str = "",
                         stance: str = "") -> None:
    """把单条召对发言写入对话记忆库（失败不阻断，兼容层 dialogue_history 仍在）。

    统一写入口径：`audience_dialogue_prepare`（朕言）/ `_apply`（回奏）与两个短路
    路径（本地预过滤模板、召对缓存复用）都经此落库 —— 否则短路回合在记忆库与召对
    面板里整轮消失（回看只见空缺）；`topic` 同源 `_topic_key` 使问答两侧同组。
    """
    try:
        from memory.dialogue_memory import get_dialogue_memory
        dm = get_dialogue_memory(state)
        dm.turn = state.turn
        dm.add_dialogue(minister_name, state.turn, speaker, text,
                        intent=intent[:50], stance=stance[:20], topic=topic)
    except Exception:
        pass


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
        _record_dialogue_row(state, minister_name, "朕", player_input,
                             _topic_key(player_input))
        _record_dialogue_row(state, minister_name, minister_name, pref,
                             _topic_key(player_input))
        state.dialogue_history.append((minister_name, pref))
        return pref
    # 召对缓存：同话题近 N 回合结果复用（结构化键 + 相似度 fallback）
    cached = _dialogue_cache_hit(state, minister_name, player_input)
    if cached:
        _record_dialogue_row(state, minister_name, "朕", player_input,
                             _topic_key(player_input))
        _record_dialogue_row(state, minister_name, minister_name, cached,
                             _topic_key(player_input))
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
    _ai_ok = True       # AI 是否真正产出该回复（决定是否计 token / 写召对缓存）
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
        _ai_ok = False
        from ai.narrative_fallback import fallback_dialogue
        obj = fallback_dialogue(kwargs["minister_name"], state.turn)
    reply = audience_dialogue_apply(state, minister_name, obj)
    if not reply:
        # T8 分级降级：AI 返回空 → 召对模板兜底（不报错阻断）
        _ai_ok = False
        from ai.narrative_fallback import fallback_dialogue
        obj = fallback_dialogue(minister_name, state.turn)
        reply = audience_dialogue_apply(state, minister_name, obj) or "（大臣未及应诏。）"
    # 审查修复：仅在 AI 真正产出时计数并写召对缓存。
    # 原实现无条件执行 → ①「召对·AI」次数虚增（该次 AI 其实未参与，计量与显示失真）；
    # ② 模板兜底文本被当「大臣回复」写入缓存最多 8 回合 —— AI 配好后同话题也不再调用；
    # ③ 对话记忆库混入占位文本。
    if _ai_ok:
        _dialogue_stats(state)["ai_calls"] += 1
        _dialogue_cache_store(state, minister_name, player_input, reply)
    return reply


def allocate_payraise(state: GameState, amount) -> str:
    """拨国帑入加俸预算（厚禄养廉）。

    审查 D9 补齐：`state.payraise_budget` 初始 0 且**只减不增**——`_settle_finance`
    与 `game_state_econ` 的月用度均只做 `payraise_budget - payraise_used`，全库无任何
    写入方 → 恒为 0 →「厚禄养廉」整条是死路（会计面板那行永不出现，诸路俸给亦永无
    补足，`financed = local + payraise_budget * share` 中的第二项恒 0）。

    现补玩家明拨入口：国帑出、入加俸预算（外流记账，非凭空生钱）。拒绝式：
    数额非正 / 超国库 / 不可解析为整数一律不受，且不动国帑。
    """
    try:
        amt = int(amount or 0)
    except (TypeError, ValueError):
        return "拨帑数额须为整数。"
    if amt <= 0:
        return "拨帑数额须为正数。"
    _tre = int(getattr(state, "treasury", 0) or 0)
    if amt > _tre:
        return f"国帑不足：现有 {_tre:,} 贯，不能拨 {amt:,} 贯入加俸预算。"
    state.change_treasury(-amt)
    state.payraise_budget = int(getattr(state, "payraise_budget", 0) or 0) + amt
    return (f"已拨国帑 {amt:,} 贯入加俸预算（厚禄养廉），"
            f"逐月摊还以足诸路俸给；预算现余 {state.payraise_budget:,} 贯。")


def envoy_diplomacy(state: GameState, target: str, speech: str, ai_client) -> str:
    """遣使通谕一轮：AI 扮国主应答 → 达成协议则落地（apply_treaty）。

    审查补齐（「条约」页恒空的根因）：`ai_client.diplomacy_dialogue` 与
    `core.diplomacy_treaty.apply_treaty` 均已实现且带 T5 测试，却**全库无生产调用方**
    —— 前端「遣使」原走 `audience_dialogue`（把外国君主当大臣召对），于是协议永不
    落地、`state.treaties` 恒空。

    拒绝式纪律（与召对同级）：AI 未接入或校验不过 → 不伪造国主应答与协议，只记外交
    纪事；`apply_treaty` 自身校验对象/类型/内帑，不通过则如实回奏而不写 treaties。
    """
    from core.diplomacy_treaty import apply_treaty

    target = str(target or "").strip()
    speech = str(speech or "").strip()
    if target not in ("辽", "金", "西夏"):
        return "遣使须择辽、金、西夏之一。"
    if not speech:
        return "国书未具，遣使不行。"

    _dlog = getattr(state, "diplomacy_log", None)
    _y, _m = int(getattr(state, "year", 0) or 0), int(getattr(state, "month", 0) or 0)

    def _note(text: str) -> None:
        if isinstance(_dlog, list):
            _dlog.append({"year": _y, "month": _m, "text": text})

    if not (ai_client and getattr(ai_client, "available", False)):
        _note(f"遣使{target}，国主未及接见（AI 未接入），和战未定")
        return f"遣使{target}未达：国主未及接见，和战未定。"

    try:
        obj = ai_client.diplomacy_dialogue(speech, target, state=state)
    except Exception as e:  # noqa: BLE001
        print(f"[diplomacy] 遣使{target}失败: {e!r}", flush=True)
        obj = None
    if not isinstance(obj, dict):
        _note(f"遣使{target}，国书往返而未成议")
        return f"遣使{target}未成：国书往返，未达成协议。"

    narrative = str(obj.get("narrative") or "").strip()
    stance = str(obj.get("stance") or "")
    agreement = str(obj.get("agreement") or "拒绝")

    if agreement == "拒绝":
        _note(f"遣使{target}，国主{stance}而不许：{narrative}")
        return narrative or f"{target}国主不许所请。"

    res = apply_treaty(state, target, agreement, obj.get("terms") or {},
                       year=_y, month=_m)
    if not res.get("ok"):
        _note(f"遣使{target}议{agreement}未成：{res.get('msg')}")
        return f"与{target}议{agreement}未成：{res.get('msg')}"
    _note(f"与{target}定{agreement}：{res.get('msg')}（国主{stance}）")
    return f"{narrative}\n\n{res.get('msg')}" if narrative else str(res.get("msg"))


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
    # 会话流两侧对称入库：`dialogue_history` 存了「朕言」而对话库只存大臣回奏，导致
    # 记忆库/召对面板回看时只剩单边对白（「对话没展示出来」）。此处补写陛下之言，
    # topic 与 `_topic_key` 同源 —— 使 (minister, topic) 下两侧同组，概要可还原问答。
    _record_dialogue_row(state, minister_name, "朕", player_input,
                         topic=_topic_key(player_input))
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
    # 对话记忆库（SQLite，单独存对话）：召对记录入库（量大高频，与圣旨/口谕主库分离）。
    # topic 取紧邻的上一条「朕」之言（prepare 刚写入）→ 与设问同组，概要可还原问答成对。
    prev = state.dialogue_history[-2] if len(state.dialogue_history) >= 2 else None
    topic = _topic_key(str(prev[1])) if prev and prev[0] == "朕" else ""
    _record_dialogue_row(state, minister_name, minister_name, reply, topic=topic,
                         intent=intent_hint, stance=str(intent_hint))
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
            "东南士人": _fac == "东南士人",
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