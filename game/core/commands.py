# -*- coding: utf-8 -*-
"""宋祚 · 与 UI 无关的游戏命令层

把"可玩逻辑"（颁诏、召见、施政、个人行动、回合结算、事件、结局、遣使缔约、
拨帑养廉）从界面层抽离出来，保证游戏逻辑只有单一来源。

消费方：`backend/`（FastAPI；`backend/client.py` 的分派表把动作名映射到本层函数，
Electron 前端经 HTTP 调用）与测试。**Tkinter GUI 已废弃删除**——原文「供 GUI 版
(ui/gui.py)使用」所述消费方已不存在，此处据实更新。
"""

# ══ 目录（**纯符号索引**，2026-09-27 起不写行号）══
#   背景：原为自动生成的行号目录，实测 46/46（game_state）与 38/38（commands）**行号全错**，
#   反而误导；行号会随每次编辑漂移，符号名不会。查定义位置请用 `rg 'def <名字>'`。
#      def    new_game   —— 创建新游戏（含记忆知识库开局基线：大臣/机构/派系实体）。
#      def    audience_minister   —— 召见大臣并施行一项行动，返回叙述文本
#      def    choose_imperial_action   —— 皇帝个人行动矩阵（契约 v2）：按 location×mode 限定 action 白名单（跨格子非法），
#      def    do_personal_action   —— 旧单值个人行动通道（UI/后端兼容）：映射到 宫里·公开 矩阵行动。
#      def    choose_major_policy   
#      def    advance_month   —— 触发当月事件。返回本回合需要玩家处理的事件列表。
#      def    settle_turn   —— 执行月度结算，返回 (log, ai_report)。行为与拆分前完全一致：
#      def    _flush_ai_token   —— 把 AIClient 本回合累计的 token 用量写进 state.ai_token_log（一行），然后重置
#      def    _ai_prelude   —— 结算前 AI 推演族（同步版）：economy 强制推演 + 按需唤醒注入，写 state 槽位。
#      def    _snapshot_state   —— 结算前状态快照（供失败回滚）：深拷贝各状态字段，不可拷贝对象（SQLite 连接/锁等）跳过。
#      def    _restore_state   —— 把快照字段写回 state（不删除快照之后新增的瞬态键，如 _economy_ai）。
#      def    advance_and_settle   —— 事件触发 + 月度结算的原子封装。返回 (events, log, report)。
#      def    settle_local   —— 本地 12 步结算（确定性，主线程执行）：委托 run_monthly_settlement（含回合推进）。
#      def    finish_turn   —— 结算收尾（主线程）：终局判定 + 记忆库压缩/总结/落盘 + 对话记忆库每 3 回合总结去重。
#      def    monthly_report_args   —— 构建月报调用入参（主线程快照）：(year, month, era_name, posture_with_mem
#      def    _monthly_report_text   —— 生成月报文本（装饰性 AI 文本）。
#      def    resolve_event   —— 处理玩家对某事件的选择，返回效果叙述。
#      def    save   
#      def    load   
#      def    save_slots   
#      def    conclude   —— 生成结局评定，返回 (eval_result, ai_eval_text)。
#      def    approve_ai_action   —— 批红一条 AI 待批行动；按 kind 落地。返回叙述。
#      def    reject_ai_action   
#      def    issue_task_decree   —— 对某在办长期事务颁旨（督行/调兵督行/御笔中旨）；单一实现在 core/longterm_task
#      def    _apply_military_dispatch   —— 批红军令：先校验钱粮，增募钱不够则整单拒绝。
#      def    _prefilter_rules   —— 预过滤规则：(关键词组, 模板, 意图词)。模板用 {m} 占位大臣名。
#      def    _prefilter_intent_hint   —— 预过滤命中后的意图词（供后续拟诏 AI 上下文，降低模板与 AI 割裂）。
#      def    _prefilter_dialogue   —— 召对 token 优化：本地规则匹配常用诏令 → 本地模板回复（AI 只处理非常规）。
#      def    _dialogue_stats   —— 召对 token 统计（省 token 可量化；动态字段不序列化）：预过滤命中/缓存命中/AI 调用。
#      def    _topic_key   —— 召对意图主题词（缓存键组成部分）：命中主题词取主题词（同话题不同措辞命中），
#      def    _dialogue_cache_store   —— AI 成功回复后写召对缓存（结构化键：minister+topic+意图摘要；近 N 回合复用）。
#      def    _dialogue_cache_hit   —— 召对缓存：同大臣同话题近 N 回合的召对结果复用（省 token，命中不调 AI）。
#      def    _record_dialogue_row   —— 把单条召对发言写入对话记忆库（失败不阻断，兼容层 dialogue_history 仍在）。
#      def    audience_dialogue   —— 与大臣奏对一轮。返回大臣的奏对文本，并把对话记入 state.dialogue_history。
#      def    allocate_payraise   —— 拨国帑入加俸预算（厚禄养廉）。
#      def    envoy_diplomacy   —— 遣使通谕一轮：AI 扮国主应答 → 达成协议则落地（apply_treaty）。
#      def    audience_dialogue_prepare   —— 召对前奏（主线程）：身份/状态校验 + 入史（朕言/短期日志）+ 构建 AI 入参。
#      def    audience_dialogue_apply   —— 召对落定（主线程）：解出回奏并写入史册/意向，返回回奏文本。
#      def    apply_minister_departure   —— 执行大臣离任（贬黜/致仕/病故/战殁/处死/乞休），返回日志列表。
# ══ 目录结束 ══
import logging

log = logging.getLogger("commands")

from content.data import (
    PERSONAL_ACTIONS, MAJOR_POLICIES,
)

from core.game_state import GameState
# 🔴 方案乙（2026-10-04 POP 实体下沉州府级）：POP 写入走桥接层；未下沉时回落原写法
from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add
from core.settlement import run_monthly_settlement
from core.save_load import save_game, load_game, get_save_slots
from core.workflows.evaluation import evaluate_game, check_game_over
from core.events import get_historical_event, get_random_event, apply_event_choice, get_strategic_branch, get_pending_break_event
from core.foundation.common.errors import AIRuntimeError


# ============================================================
# 新游戏 / 难度
# ============================================================

from core.commands_decree import (
    _random_faction_stances, confirm_timeline_break, dismiss_pending_break, issue_decree, issue_drafted_decree, issue_secret_decree, preview_draft,
    accept_memorial, dismiss_memorial,
    # 2026-10-17 全审 A-3：backend/client.py 的 action 分派表直接引用这些符号，
    # 但此前未在 core.commands 重导出 ⇒ /api/action 抛 AttributeError -> 500。
    # 新增分派动作时必须同步本清单（契约测试见 test_backend_action_contract.py）。
    issue_free_decree, issue_kouyu, merge_drafts,
    issue_edict_from_review, reject_edict_draft,
    propose_inner_transfer, confirm_inner_transfer, cancel_inner_transfer,
    bestow_imperial_favor,
)


def new_game(difficulty: str = "史实", ai_client=None) -> GameState:
    """创建新游戏（含记忆知识库开局基线：大臣/机构/派系实体）。"""
    # 🔴 2026-10-07 用户裁定（M25）：**新局不再直接构造 GameState**，
    #   始终委托 application/game_init.new_game（同为用例层横移，与 commands.finish_turn
    #   → application.turn_lifecycle 同一先例），确保隐户口数完成物化。
    from application.game_init import new_game as _new_game
    state = _new_game(difficulty)
    # 清空对话记忆库（slot_{n}_dialogue.db）：新游戏不得残留旧局召对留档
    try:
        import os as _os
        from memory.dialogue_memory import _dialogue_path
        _dp = _dialogue_path(state.memory_slot)
        for _suffix in ("", "-wal", "-shm"):
            _p = _dp + _suffix
            if _os.path.exists(_p):
                _os.remove(_p)
    except Exception:
        pass
    # 开局邸报（参考《明末：捞金模拟器》）：文言局势 + 待办三事，注入 state.opening_gazette
    try:
        from content.legacy_gazette import build_opening_gazette
        state.opening_gazette = build_opening_gazette()
    except Exception:
        state.opening_gazette = {}
    # 帝国修正（legacies）：开局即存在的条件式长期修正符
    try:
        from core.domains.politics.legacy_mechanic import init_legacies
        init_legacies(state)
    except Exception:
        state.legacies = {}
    # 国策树（focus）：五大分支（政务/军事/科学/内卫/税务）
    try:
        from core.focus_mechanic import init_focus_tree
        init_focus_tree(state)
    except Exception:
        state.focus_tree = {}
    # 局势系统 v1 开局种子（批 2）：花石纲民怨 / 东南财政亏空 / 辽事边备
    # 成败条件全公开 + 持续代价；幂等（按 situation_key 去重），失败不阻断开局
    try:
        from content.situation_seeds import seed_initial_situations
        seed_initial_situations(state, turn=0)
    except Exception:
        state.situations = getattr(state, "situations", None) or []
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
    from content.data import LEGACY_PERSONAL_ACTION_MAP
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
            # 传入 state：历史压力链改写位（sea_pact_jin / 花石纲默许）可动态前移卡窗口
            ev = get_historical_event(state.year, state.month, state)
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
            if isinstance(report, dict):
                report = report.get("report", "")
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
        log.warning("[settle] 经济推演失败: %s", e)
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
        from application.agent_router import route_agents, inject_woken_agents
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

    # 局势推进档位（规范 §7）：审查 S9 —— `AIClient.situations_grade_decide` 早已实现
    #   （只给档位与叙事、数值程序算、非法条目丢弃），`core/situation_settle.py:191`
    #   也确实消费 `state._situation_grades`，但**全库无任何生产调用方** →
    #   该字典恒空 → 局势评分**永远走程序 inertia 兜底**，AI 通道 100% 死码
    #   （前次审查 A.4 记为 P1 未修）。现按契约 docstring 的既定设计接线：
    #   仅当「有活跃局势」且「AI 可用」时调用；失败/不可用 → 保持空 dict，
    #   由 Step 8.5 走 inertia（**不伪造** AI 评分）。
    try:
        if (getattr(ai_client, "available", False)
                and any(isinstance(r, dict) and r.get("status") == "active"
                        for r in (getattr(state, "situations", None) or []))):
            _sg = ai_client.situations_grade_decide(state=state)
            if isinstance(_sg, dict) and not _sg.get("_error"):
                _grades = _sg.get("grades")
                if isinstance(_grades, list) and _grades:
                    # 只落"档位 + 叙事"，数值仍由程序算（situation_settle 的效果契约）
                    state._situation_grades = {
                        str(g.get("situation_id")): g
                        for g in _grades if isinstance(g, dict) and g.get("situation_id")
                    }
    except Exception as _e:  # noqa: BLE001 — 局势评分失败不得阻断结算
        log.warning("[settle] 局势档位推演失败（回落程序 inertia）: %s", _e)


def _snapshot_state(state) -> dict:
    """结算前状态快照（供失败回滚）：深拷贝各状态字段，不可拷贝对象（SQLite 连接/锁等）跳过。

    另记录 `__mem_turn__` 记忆水位（审查 A2）：记忆库含 SQLite 连接，深拷贝必被
    跳过，无法随字段一并还原，故单独记回合号，由 `_restore_state` 按水位截断。

    审查 P2-3 应修：被跳过的字段名落 `snap["__skipped__"]`（**可诊断**）——
    原实现 `continue` 后无任何痕迹，"哪些字段没进快照"完全不可查，
    一旦这些字段参与结算就成了"回滚回不干净"的隐形来源。
    """
    import copy
    import logging as _lg
    snap: dict = {}
    _skipped = []
    for k, v in list(getattr(state, "__dict__", {}).items()):
        try:
            snap[k] = copy.deepcopy(v)
        except Exception as e:  # noqa: BLE001
            _skipped.append(k)      # 不可深拷贝（连接/锁等）→ 保持原引用，回滚时不动该字段
            _lg.getLogger("commands").debug("快照跳过不可深拷贝字段 %s：%s", k, e)
    snap["__skipped__"] = _skipped
    if _skipped:
        # 只记 DEBUG：`memory`（含 SQLite 连接）等**每回合都会**被跳过，属正常，
        # 记 WARNING 会变成每回合一条的无意义噪声（P2-3「正常路径不产生噪声」）。
        # 字段名随快照保存（`snap["__skipped__"]`），回滚不完整时由 `_restore_state`
        # 连同失败字段一并 ERROR 报出 → 需要时可定位，平时不吵。
        _lg.getLogger("commands").debug(
            "状态快照跳过 %d 个不可深拷贝字段：%s", len(_skipped), _skipped[:10])
    snap["__mem_turn__"] = int(getattr(state, "turn", 0) or 0)
    return snap


def _restore_state(state, snap: dict) -> None:
    """把快照字段写回 state（不删除快照之后新增的瞬态键，如 _economy_ai）。

    审查 A2 补齐：还原 state 后按快照水位截断记忆库（主库 + 对话库）中**失败回合
    已写入**的关系/召对/总结。缺此步则重试结算时同一事实被重复 upsert，关系权重
    叠加（不可逆）；召对残留还会污染「卿前番之言」注入。记忆库不可深拷贝故不能
    走字段还原，只能按水位截断（各库 `rollback_after`）。

    审查 P2-3 应修：`setattr` 失败原为静默 `continue` —— **回滚失败了自己不说**，
    玩家与开发者都以为状态已完整还原。现统一 `logging.error` 并统计失败字段数
    （回滚不完整必须可见，否则"重试结算"会建立在半回滚的状态上）。
    """
    import logging as _lg
    _rlog = _lg.getLogger("commands")
    _snap_skipped = list(snap.get("__skipped__") or [])
    _failed = []
    for k, v in snap.items():
        if k.startswith("__"):
            continue          # 内部水位标记不可 setattr 回 state
        try:
            setattr(state, k, v)
        except Exception as e:  # noqa: BLE001
            _failed.append(k)
            _rlog.error("状态回滚失败：字段 %s 未能还原：%s", k, e, exc_info=True)
    if _failed:
        _rlog.error("状态回滚**不完整**：%d 个字段失败（%s）；另有 %d 个字段未进快照（%s）",
                    len(_failed), _failed[:10], len(_snap_skipped), _snap_skipped[:10])
    _turn = snap.get("__mem_turn__")
    if _turn is None:
        return
    _objs = [getattr(state, "memory", None)]
    try:
        from memory.dialogue_memory import get_dialogue_memory
        _objs.append(get_dialogue_memory(state))
    except Exception as e:  # noqa: BLE001
        # 取不到对话库 → 该库**不会**被回滚（失败回合的召对残留会留下），必须可见。
        _rlog.warning("状态回滚：对话记忆库不可达，其水位未截断（召对可能残留）：%s", e)
    for _obj in _objs:
        _fn = getattr(_obj, "rollback_after", None)
        if callable(_fn):
            try:
                _fn(int(_turn))
            except Exception as e:  # noqa: BLE001
                # P2-3 应修：原注释称"已记录于自身日志"与事实不符 ——
                # `memory/memory_graph.py::rollback_after` 内并**无** warning。
                # 该文件不在本次授权范围，故此处据实补记（注释同步更正），
                # 使"记忆回滚失败"确实留下痕迹，而不是只留一句不成立的注释。
                _rlog.error("状态回滚：记忆库水位截断失败（rollback_after(%s)）：%s",
                            _turn, e, exc_info=True)


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
                    _memorial_posture(state), state=state, count=3)
                _memos = (_res or {}).get("memorials") if isinstance(_res, dict) else None
            if not _memos:
                from ai.narrative_fallback import fallback_memorials
                _fb = fallback_memorials(state=state, turn=getattr(state, "turn", 0))
                _memos = (_fb or {}).get("memorials") if isinstance(_fb, dict) else None
            if _memos:
                _keep = [m for m in (getattr(state, "memorials", None) or [])
                         if isinstance(m, dict) and m.get("incident_id")]
                state.memorials = _keep + list(_memos)
        except Exception as _e:  # noqa: BLE001
            log.warning("[memorials] 上折未成: %s", _e)
        return events, log, report
    except Exception:  # noqa: BLE001
        _restore_state(state, snap)
        raise


def _rich_narrative(state, ai_client) -> None:
    """**AI 三路富化**（`_async_settle` 尾段）：AI 民间反应 / AI 奏章 / AI 官方月报。

    分层（2026-09-21 用户定稿）：
      · 民间情况（首段弹，玩家立读）—— **程序真值民间反应**先行（`civilian_situation`），
        AI 版就位后写 `state.rich_civilian`（前端就地替换民间段）；
      · 回合报告（第二弹，结算后）—— AI 官方月报（`_monthly_report_text`）或本地模板
        兜底（`fallback_report`）→ `state.rich_report`；
      · AI 奏章 → `state.memorials`（原文案路径搬入）。
    装饰层失败**全兜底**（失败路 → 不写字段，程序版仍可用），绝不把结算拉回；
    `rich_ready` 无条件置 True（前端停轮询）；`_flush_ai_token` 落附表附表一行。
    """
    try:
        if ai_client is not None and getattr(ai_client, "available", False):
            # ① AI 民间反应（rich_civilian；失败保程序版即 UI 已有）
            try:
                if hasattr(ai_client, "civilian_situation"):
                    _res = ai_client.civilian_situation(state=state)
                    _civ = (_res or {}).get("text") if isinstance(_res, dict) else None
                    if _civ:
                        state.rich_civilian = str(_civ)
                    _civ_scenes = (_res or {}).get("scenes") if isinstance(_res, dict) else None
                    if _civ_scenes:
                        state.rich_civilian_scenes = list(_civ_scenes)
            except Exception as _e:  # noqa: BLE001
                log.warning("[rich_civilian] 民间反应富化未成: %s", _e)
            # ② AI 奏章（memorials）
            try:
                _res = ai_client.generate_memorials(
                    _memorial_posture(state), state=state, count=3)
                _memos = (_res or {}).get("memorials") if isinstance(_res, dict) else None
                if _memos:
                    _keep = [m for m in (getattr(state, "memorials", None) or [])
                             if isinstance(m, dict) and m.get("incident_id")]
                    state.memorials = _keep + list(_memos)
            except Exception as _e:  # noqa: BLE001
                log.warning("[memorials] round2 上折未成: %s", _e)
            # ③ AI 官方月报（结算后的官方总结；失败走本地模板 → 不写 rich_report）
            try:
                _rpt = _monthly_report_text(state, ai_client)
                if isinstance(_rpt, dict):
                    if _rpt.get("report"):
                        state.rich_report = str(_rpt["report"])
                    _scenes = _rpt.get("scenes") or []
                    if _scenes:
                        state.rich_report_scenes = _scenes
                elif isinstance(_rpt, str) and _rpt:
                    state.rich_report = _rpt
            except Exception as _e:  # noqa: BLE001
                log.warning("[rich_report] 回合报告富化未成: %s", _e)
            _flush_ai_token(state, ai_client)
    finally:
        state.rich_ready = True


def _async_settle(state, ai_client=None, snap=None) -> None:
    """**后台段**（daemon）：数值结算链 + AI 三路富化，完成后写 `rich_ready` / `settle_error`。

    语义分层（用户定稿 2026-09-21）：
      · **民间情况**（点过回合立刻弹）＝ 民间小故事串（平民/市井/士绅视角）——程序版
        真值先行，AI 版跑完写 `state.rich_civilian`（前端就地替换民间段）；
      · **回合报告**＝ **结算后官方总结**（数值变化/政务/人事），程序真值月报先落
        `state.rich_report`（fallback 版），AI 版再就地替换；前端第二次弹窗。

    **失败链（AI 拒绝式）**：`economy_decide` 失败 → **回滚快照**（active_events 一并消失，
    防幽灵事件）+ `state.settle_error`（前端弹"推演失败"）+ `rich_ready=True`（前端停轮询）。
    """

    try:
        # —— settlement_mode + 数值链（economy / agents / 程序结算）——
        import contextlib as _ctx
        _mode = getattr(ai_client, "settlement_mode", None)
        with (_mode() if callable(_mode) else _ctx.nullcontext(False)):
            _ai_prelude(state, ai_client)
            log = settle_local(state)
        if snap is not None:
            state._last_settle_log = log        # 后台结算的朝报（log 行暂存，前端弹窗用）
            state.settle_error = ""
        _flush_ai_token(state, ai_client)
        finish_turn(state)
    except Exception as e:  # noqa: BLE001
        # 数值结算失败：快照回滚（events 一并回滚防幽灵事件）+ 状态落账错误。
        # S-1（2026-09-21 重审）：富化字段不随快照折回（advance_two_phase 已从 snap
        # 剔除），此处再显式清空并**最后**置 ready —— 保证失败期间任何一次 round2
        # 轮询都不会读到「ready + 无错误 + 上月富文本」组合（Dock 单次触发轮询命中
        # 即弹上月「回合报告」并吞掉「推演未成」，`turn` 守卫因回滚未推进而拦不住）。
        _restore_state(state, snap)
        state.rich_report = ""
        state.rich_civilian = ""
        state._last_settle_log = []
        state.settle_error = (str(getattr(e, "code", "")) or "RUNTIME") + ":" + type(e).__name__
        state.rich_ready = True                # 前端停止轮询（错误路径）
        return
    # —— AI 三路富化（装饰性；AI 缺失/失败 → 字段留空，程序版文本已在 UI 端）——
    _rich_narrative(state, ai_client)


def advance_two_phase(state, ai_client=None) -> tuple:
    """三段式回合推进（2026-09-21 **「点过回合 即弹民间情况」**用户定稿）。返回 (events, log, civilian)。

    **三段**（先快出后结算，用户语义：民间情况 **点了过回合立即可读、文本小故事串**；
    **回合报告＝结算后官方总结**，重数值/政务/人事）：
      ① **首段（同步 <100ms）**：`advance_month`（当月事件已触发）+ **民间反应文本**
         （`civilian_situation(state)` 程序真值模板 —— 引用本回合圣旨 / 局势，自拟
         小故事式反应）→ **立刻返回**。在此期间 **economy / agent / 数值结算尚未跑**。
      ② **后台段（daemon）**：`_async_settle` —— economy+agent 注入 → `settle_local`
         → `_flush_ai_token` → `finish_turn`；然后 `_rich_narrative`（AI 民间反应版
         `rich_civilian` / AI 官方月报 `rich_report` / AI 奏章 `memorials`）。
      ③ **前端（第二弹）**：`rich_ready=true` 且富文本就位 → 弹**回合报告**（官方月报）
         —— 玩家的阅读窗口在后台完成富化，**体验完全两码事**。

    **预检（M-1，2026-09-21 重审）**：AI 缺失/未配置 → **立即拒绝式**（与 `settle_turn`
    同形抛 `AIRuntimeError(code="AI_NOT_CONFIGURED")`）——恢复「点过回合立即 503 ＋ 精确
    错误码」，**不 spawn daemon、不弹会被回滚的民间故事**。修复前：首段照常返回、后台段
    才失败，且未配置被误报为 `AI_CONTRACT_FAILED`（`AIClient().economy_decide` 未配置时
    静默返回 `None`，经 `_ai_prelude` 落错码）。
    **回滚**：后台段失败（AI 拒绝式）→ `_restore_state(snap)` 整体回滚（防幽灵事件），
    `state.settle_error` + `rich_ready=True` —— 前端弹"回合结算失败"而不是等待。
    **富化字段不随快照折回（S-1）**：`rich_ready/rich_report/rich_civilian/settle_error/
    _last_settle_log` 在快照后复位、失败后由 `_async_settle` 显式落账——若随快照还原，
    失败回合会带回**上一回合**的 `rich_ready=True` 与富文本（前端可能弹上月「回合报告」）。
    **并发风险**（接受并留档）：后台段与玩家轮询的 action 写入在 server 层 `_lock`
    下互斥，但 core 不知 server 锁 —— 玩家在读民间情况（加强了阈值不动锁），
    实际并发窗口 ~ 40 ms（数值段），概率低。后期 Hardening（若需要）走 server `_lock`。
    """
    from content.data import AI_ERROR_CODES
    # —— M-1 预检：数值结算链依赖 economy 强制推演（拒绝式），AI 缺失直接拒绝 ——
    if not (ai_client and getattr(ai_client, "available", False)):
        raise AIRuntimeError(AI_ERROR_CODES.get("AI_NOT_CONFIGURED", "AI 未接入"),
                             code="AI_NOT_CONFIGURED")
    snap = _snapshot_state(state)
    # S-1：富化链字段不参与快照回滚（快照早于下方复位；若随快照还原，失败回合会
    # 折回上一回合的 ready=True 与富文本）。失败后的落账统一在 `_async_settle`。
    for _rk in ("rich_ready", "rich_report", "rich_civilian",
                "settle_error", "_last_settle_log"):
        snap.pop(_rk, None)
    # 本回合富化链先复位（round2 尚未开始）
    state.rich_ready = False
    state.rich_report = ""
    state.rich_civilian = ""
    state.settle_error = ""
    try:
        events = advance_month(state)
    except Exception:  # noqa: BLE001
        _restore_state(state, snap)
        raise
    # —— 民间反应（程序真值，不等 economy / agent / 结算）——
    from ai.narrative_fallback import civilian_situation as _civ_prog
    civilian = str(_civ_prog(state) or "")
    # —— 数值结算与 AI 三路富化 押后台（daemon）——
    # 结算窗口标记：server 层据此对 action/save/propose 返回 409，避免与后台写并发。
    state._settle_in_progress = True

    def _run_async_settle():
        try:
            _async_settle(state, ai_client, snap)
        finally:
            state._settle_in_progress = False

    _th = __import__("threading")
    try:
        _th.Thread(target=_run_async_settle, args=(),
                   daemon=True, name=f"settle-{state.turn}").start()
    except Exception:
        state._settle_in_progress = False
        raise
    return events, [], civilian


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
    # 🔴 路级 `pops` 只读守卫（观察型，缺省关闭）：`SONGZUO_POPS_GUARD=1` 时在结算
    #    观察期给已下沉路装上守卫，结算后读违规汇总并**还原 plain dict**。记录型、
    #    不硬中断、不改数值；装/卸成对（`finally`），异常路径由 `_restore_state`
    #    用装守卫前的 plain 快照整体替换 `prefectures`，守卫子类随之卸除。
    import os as _os
    _guard_on = _os.environ.get("SONGZUO_POPS_GUARD", "").strip() not in ("", "0", "false", "no")
    if _guard_on:
        try:
            from core.foundation.ledger.pop_bridge import (
                install_all_guards, uninstall_all_guards,
                reset_pops_guard, pops_guard_violations,
            )
            reset_pops_guard()
            install_all_guards(state)
        except Exception:  # noqa: BLE001 —— 守卫接线失败绝不影响结算
            # N1：装配失败必须留痕（否则"守卫没启用"与"守卫零违规"在日志上无法区分）
            _lg.getLogger("settle_local").warning(
                "路级 pops 守卫装配失败，本回合按未启用处理（结算照常）：", exc_info=True)
            _guard_on = False
    try:
        return run_monthly_settlement(state)
    except Exception as e:  # noqa: BLE001
        _restore_state(state, snap)
        _lg.getLogger("settle_local").error(
            "月度结算异常，已回滚状态快照（回合未推进，可安全重试）：%s", e)
        raise
    finally:
        if _guard_on:
            try:
                _viol = pops_guard_violations()
                if _viol:
                    _lg.getLogger("settle_local").warning(
                        "路级 pops 只读守卫：结算期检出 %d 处直写（路级应只读、"
                        "写入须走桥接）：%s", len(_viol), _viol[:10])
            finally:
                try:
                    uninstall_all_guards(state)
                except Exception:  # noqa: BLE001 —— 卸守卫失败不得升级为结算异常
                    _lg.getLogger("settle_local").error("路级 pops 守卫还原失败", exc_info=True)


def finish_turn(state) -> None:
    """结算收尾的**薄代理**（架构方案 §5.2：迁移期保留同名入口）。

    实现已抽到 `game/application/turn_lifecycle.py`（终局判定 → 记忆生命周期三步 →
    自动存档），本处只维持 `from core.commands import finish_turn` 的既有调用面
    （`backend/client.py`、`settle_turn`、`__all__`）。

    契约不变：不抛错、返回 `None`。用延迟导入而非顶层导入，避免
    `core.commands ← application ← core.workflows.evaluation/save_load` 在导入期互锁。
    """
    from application.turn_lifecycle import finish_turn as _finish_turn
    _finish_turn(state)


def _memorial_posture(state) -> str:
    """奏折入参 = 时局 posture ＋ **天道事实签**（管道一）。

    事实签由 `TianDaoFacade.scan_memorial_seeds` 从真实账本提炼（受命大臣取自
    `state.central_orgs` 在任主官），注入后大模型据实拟折，不再凭空选题。
    取不到事实签 ⇒ 原样返回 base posture（**不伪造**、不影响无 AI 兜底）。
    """
    base = getattr(state, "posture", "") or ""
    try:
        from core.ai.tiandao_facade import TianDaoFacade
        seeds = TianDaoFacade.scan_memorial_seeds(state, limit=3)
    except Exception:  # noqa: BLE001 — 事实签失败不得阻断上折
        return base
    if not seeds:
        return base
    lines = ["【天道事实签｜据真实账本，拟折须据此，不得虚构人物与数据】"]
    for i, s in enumerate(seeds, 1):
        lines.append(
            f"{i}) 类别={s.get('matter_domain')}"
            f"｜建议受命大臣={s.get('target_minister')}"
            f"｜事实={s.get('trigger_fact')}"
            f"｜主张={s.get('core_claim')}"
            f"｜拟题={s.get('suggested_title')}"
        )
    return base + "\n" + "\n".join(lines)


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
    # 六类心气真值注入（众生相 P1）：供 AI 分幕锚定各阶层真实状态
    try:
        _posture += "\n" + pop_sentiment_brief(state)
    except Exception:
        pass
    # 天道月度天机实录（管道三）：给月报一个真实因果骨架（气数档 / 民怨告警 / 行政效能）
    try:
        from core.ai.tiandao_facade import TianDaoFacade
        _omen = TianDaoFacade.summarize_monthly_omen(state)
        _bits = []
        if _omen.get("omen_defined"):
            _bits.append(f"气数{_omen['omen_level']}（皇威{_omen['prestige']}）")
        if _omen.get("unrest_circuits"):
            _bits.append("民怨告警：" + "、".join(_omen["unrest_circuits"]))
        if _omen.get("admin_efficiency_defined"):
            _bits.append(f"行政效能×{_omen['admin_efficiency']:.2f}")
        if _bits:
            _posture += "\n【天道月度实录】" + "；".join(_bits)
    except Exception:  # noqa: BLE001 — 实录失败不得阻断月报
        pass
    return state.year, state.month, state.era_name, _posture


def pop_sentiment_brief(state) -> str:
    """六民生齿真值摘要（众生相 P1）：供叙事 prompt 锚定各阶层真实状态。

    数据源：`POP_SENTIMENT_CHANNELS`（六类心气通道）+ `situation_metrics` 快照。
    只给定性描述（偏高/偏低/疲敝/安和），**不注入精确数值**（脱敏约束）。
    """
    try:
        from core.situations import build_situation_readout
        out = build_situation_readout(state)
        pop_ch = (out.get("pop_channels") or {})
        by_route = (pop_ch.get("by_route") or {})
        nation = (pop_ch.get("nation") or {})
    except Exception:
        return "【六民生齿】（读数暂缺，按常情叙写）"
    lines = ["【六民生齿真值（只写入叙事，不编造数值）】"]
    _LABELS = {"农": "民心", "士绅": "士绅抵抗", "工匠": "工困", "商人": "商情",
               "官僚": "官心", "兵": "军心", "吏": "吏怨"}
    # 逐类给全国截面 + 最差路
    for cls, label in _LABELS.items():
        vals = []
        for rname, row in by_route.items():
            v = row.get(cls)
            if isinstance(v, (int, float)):
                vals.append((rname, float(v)))
        if not vals:
            # 全国截面
            nrow = nation.get(cls) or {}
            nv = nrow.get("primary") or nrow.get("均")
            if isinstance(nv, (int, float)):
                vals.append(("全国", float(nv)))
        if not vals:
            continue
        hb = cls in ("农", "兵")   # 军心/民心越高越好；其余越低越好
        # 最差 = 距理想方向最远
        if hb:
            vals.sort(key=lambda x: x[1])   # 越低越差
        else:
            vals.sort(key=lambda x: -x[1])  # 越高越差
        worst_name, worst_v = vals[0]
        best_name, best_v = vals[-1]

        def _q(v, higher_better):
            if higher_better:
                return "疲敝" if v < 40 else ("偏低" if v < 55 else ("尚安" if v < 70 else "安和"))
            return "偏高" if v > 60 else ("偏高" if v > 45 else "平和")

        lines.append(f"- {cls}·{label}：最差 {worst_name}（{_q(worst_v, hb)}）｜最好 {best_name}（{_q(best_v, hb)}）")
    # 吏怨单列
    try:
        clerks = (pop_ch.get("clerks") or (out.get("pop_channels") or {}).get("clerks") or {})
        g = clerks.get("grievance") or clerks.get("吏怨")
        if isinstance(g, (int, float)):
            lines.append(f"- 吏怨：全国均值（{'偏高' if g > 55 else '平和'}，政令折扣受影响）")
    except Exception:
        pass
    lines.append("约束：标了偏高/疲敝的路，对应幕须写疲敝之态；标了安和的路，可写太平之景。")
    return "\n".join(lines)


def _monthly_report_text(state, ai_client) -> dict:
    """生成月报文本（装饰性 AI 文本）+ 众生相分幕。

    返回 `{"report": str, "scenes": [{"scene", "text"}]}`。
    T8 分级降级：AI 失败 / 未接入 / 返回 _fallback 标记 → 本地模板 + 结构化真值组装
    （只引用 settlement_log 程序真值，不伪造数字、不伪造 AI 口吻）。
    """
    year, month, era_name, posture = monthly_report_args(state)
    if not (ai_client and getattr(ai_client, "available", False)):
        from ai.narrative_fallback import fallback_report
        fb = fallback_report(year=year, month=month, era_name=era_name, state=state)
        return {"report": str(fb.get("report") or ""), "scenes": []}
    monthly = ai_client.monthly_report(year, month, era_name, posture)
    if isinstance(monthly, dict):
        if monthly.get("_error") or monthly.get("_fallback"):
            from ai.narrative_fallback import fallback_report
            fb = fallback_report(year=year, month=month, era_name=era_name, state=state)
            return {"report": str(fb.get("report") or ""), "scenes": []}
        return {"report": str(monthly.get("report") or ""),
                "scenes": list(monthly.get("scenes") or [])}
    return {"report": str(monthly or ""), "scenes": []}


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

        if kind == "finance_proposal":
            return _apply_finance_proposal(state, action_id, payload, title)

        # ---- M36.5：察访呈请（呈请 ≠ 批准 ≠ 执行；批红后才落到既有单点）----
        if kind in ("inspect_dispatch", "inspect_report", "inspect_allege"):
            return _apply_inspect_request(state, action_id, kind, payload, title)

        state.set_ai_pending_status(action_id, "rejected")
        return f"未知待批类型：{kind}，已驳回。"
    except Exception as e:  # noqa: BLE001
        state.set_ai_pending_status(action_id, "rejected")
        # 审查修复：玩家可见文案不直出异常类名；原文只入服务端日志
        log.warning("[approve_ai_action] 落地失败: %s", e)
        return f"批红未成：{title}（该条已驳回）。"


def _record_action_feedback(state: GameState, action_id: str, outcome: str, reason: str) -> None:
    """🟢 M36.6 收口第 4 项：把**处置结果**记为事实，附在既有提案容器 `ai_pending_actions` 项上。

    只写既有容器（**不新增结构、不新增通道**）；**不自动注入**下一轮提示词（P3 冻结），
    也**不**触发重试/升级/自动提案。
    """
    try:
        for it in (getattr(state, "ai_pending_actions", None) or []):
            if isinstance(it, dict) and it.get("id") == action_id:
                it["feedback"] = {"outcome": str(outcome),
                                  "reason": str(reason or "")[:200],
                                  "period": f"{getattr(state, 'year', 0)}-{getattr(state, 'month', 0)}"}
                return
    except Exception:                      # noqa: BLE001 — 反馈记录不得阻断处置
        pass


def _apply_inspect_request(state: GameState, action_id: str, kind: str,
                           payload: dict, title: str) -> str:
    """M36.5 察访呈请的**批红落地**：把呈请载荷交既有单点执行；成功才记 approved。

    纪律：**呈请 ≠ 批准 ≠ 执行**——本函数只在**批红**（`approve_ai_action`）路径被调用；
    引擎不得在结算时自动调用（`settlement.py` 不得出现这些名字，源码测试钉住）。
    三动作一律落到既有单点：`enqueue_inspection`／`file_inspection_report`／
    `record_report_suspicion`（唯一桥接）；**不含**成案入口（`resolve_audit` 仍只经 `audit_route`）。
    """
    from core.inspection_wiring import apply_inspect_decree_payload
    _log: list = []
    done = apply_inspect_decree_payload(state, {kind: dict(payload or {})}, _log)
    _msg = _log[-1] if _log else ""
    if done:
        state.set_ai_pending_status(action_id, "approved")
        _record_action_feedback(state, action_id, "executed", _msg)
        return f"批红：{title}（{_msg}）"
    state.set_ai_pending_status(action_id, "rejected")
    _record_action_feedback(state, action_id, "failed", _msg)
    return f"批红未成，已驳回：{title}（{_msg}）"


def reject_ai_action(state: GameState, action_id: str) -> str:
    item = state.pop_ai_pending(action_id)
    if not item or item.get("status") != "pending":
        return "无此待批条目（或已处置）。"
    state.set_ai_pending_status(action_id, "rejected")
    _record_action_feedback(state, action_id, "rejected", "陛下驳回")
    return f"已驳回：「{item.get('title', '')}」。"


# ============================================================
# 长期事务（P1-1）：事务—圣旨闭环的玩家入口
# ============================================================
def issue_task_decree(state: GameState, task_id: str, kind: str = "督行",
                      target: str = "", title: str = "") -> str:
    """对某在办事务颁旨（`督行` / `调兵督行` / `御笔中旨`），返回叙述。

    命令层**只转发**：支持模型与三通道差异的单一实现在 `core/longterm_task.py`
    （不得在此复制算法）。供 `backend/client.py` 动作分派表
    （`action("issue_task_decree", …)`）与测试消费。
    """
    from core.longterm_task import issue_task_decree as _impl
    return _impl(state, task_id, kind, target, title)


def enqueue_finance_proposal(state: GameState, title: str, summary: str,
                              changes: list, proposer: str = "",
                              executor=None) -> str:
    """批 5 C1 · 财政域草案入队：大臣工具产物先落草案，玩家「准/驳」后才立项。

    `changes` 为 `update_state` 契约的 changes 数组（`{path, op, value, reason}`）；
    落地走 `engine/state_applier.applier_pipeline`（与 AI 写状态同一批量事务 API）。
    返回 action_id。
    """
    return state.enqueue_ai_action(
        kind="finance_proposal", title=title, summary=summary,
        payload={"changes": list(changes or []), "executor": executor},
        proposer=proposer)


def _apply_finance_proposal(state: GameState, action_id: str, payload: dict,
                            title: str) -> str:
    """批红财政草案：changes 走 state_applier（验证/守恒/原子写库）。"""
    changes = payload.get("changes") or []
    if not changes:
        state.set_ai_pending_status(action_id, "rejected")
        return f"批红驳回：「{title}」无变更明细。"
    executor = payload.get("executor")
    try:
        from core.authority_gate import (
            check_matter_authority,
            matters_for_finance_changes,
        )
        _matters = matters_for_finance_changes(changes)
        if _matters and executor:
            for _matter in _matters:
                _ok, _why = check_matter_authority(state, executor, _matter)
                if not _ok:
                    state.set_ai_pending_status(action_id, "rejected")
                    return f"批红未成：「{title}」（财政事权拒绝：{_why}）。"
        elif _matters:
            stats = getattr(state, "statistics", None)
            if isinstance(stats, dict):
                stats["legacy_unchecked_fiscal"] = int(
                    stats.get("legacy_unchecked_fiscal", 0) or 0) + 1
    except Exception as e:  # noqa: BLE001 — 权限核验异常 fail-closed
        state.set_ai_pending_status(action_id, "rejected")
        log.warning("[finance_proposal] 事权核验异常: %s", e, exc_info=True)
        return f"批红未成：「{title}」（财政事权核验异常，未落地）。"
    try:
        from engine.state_applier import applier_pipeline
        res = applier_pipeline(state, [("大臣财政草案", changes)])
        if res.get("applied"):
            state.set_ai_pending_status(action_id, "approved")
            return f"批红：财政草案「{title}」已落地。"
        errs = res.get("rejected") or res.get("errors") or ["未落地"]
        state.set_ai_pending_status(action_id, "rejected")
        return f"批红未成：「{title}」（{str(errs[0])[:40]}）。"
    except Exception as e:  # noqa: BLE001
        state.set_ai_pending_status(action_id, "rejected")
        log.warning("[finance_proposal] 落地失败: %s", e)
        return f"批红未成：「{title}」（该条已驳回）。"


def _apply_military_dispatch(state, action_id, payload, title) -> str:
    """批红军令：先校验钱粮，增募钱不够则整单拒绝。"""
    tier = str(payload.get("army", "禁军"))
    act = str(payload.get("action", "整编"))
    tgt = str(payload.get("target", "") or "")
    scale = max(1, min(5, int(payload.get("scale", 3) or 3)))
    if tier in ("西军", "北军"):
        tier = "禁军"
    # 2026-09-27（方案 §3.1，用户口径"军队按编制成军"）：军令的对象是**编制单位**（ArmyUnit 实体）。
    #   · 带 `unit_id` → 只作用于**该一支**（对应参考图"选中某支军再下令"）；
    #   · 不带 → 维持旧行为（按军籍整批扫），**向后兼容**，不新增写状态通道。
    unit_id = str(payload.get("unit_id", "") or "").strip()
    if unit_id:
        units = [u for u in state.army_units
                 if str(getattr(u, "unit_id", "") or "") == unit_id]
        if not units:
            state.set_ai_pending_status(action_id, "rejected")
            return f"批红驳回：无此编制单位「{unit_id}」。"
    else:
        units = [u for u in state.army_units if u.tier == tier]
        if not units:
            state.set_ai_pending_status(action_id, "rejected")
            return f"批红驳回：无此军籍 {tier}。"
    # 回执标签：定向时用**实际单位**的军籍·番号，避免 payload.tier 与实际不符时误导
    label = (f"{getattr(units[0], 'tier', tier)}·{getattr(units[0], 'name', '')}"
             if unit_id else tier)

    if act in ("操练", "整编"):
        for u in units:
            u.training = max(0, min(100, u.training + scale * 2))
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{label} {act}（档 {scale}）已饬行。"

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
                _far = p["pops"]["农"]
                if _pop_obj_add(state, _far, "size", -from_farm) is None:
                    _far["size"] = max(0, int(_far["size"]) - from_farm)
            if u.branches:
                bk = next(iter(u.branches))
                u.branches[bk] = u.branches.get(bk, 0) + taken
            else:
                u.branches["轻步兵"] = taken
            _bin = p["pops"]["兵"]
            if _pop_obj_add(state, _bin, "size", taken) is None:
                _bin["size"] = _bin.get("size", 0) + taken
            u.training = max(0, min(100, u.training + scale))
        # 守恒：国库 → 兵 wealth
        paid = 0
        for road in state.prefectures:
            if paid >= cost:
                break
            paid += state.transfer_money("treasury", f"pop:{road}:兵", cost - paid)
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{label} 增募 {total} 人，縻饷 {paid} 贯。"

    if act == "改名":
        # 2026-09-27（方案 §3.2 方案 B）：**改宋制番号**——只动**展示层**（army_models.py:53-57
        # 明示"宋制番号命名层只读展示，与兵额真账解耦"）。
        # 三条校验：① 须指定**单一编制单位**（整军籍批量改名无意义）；② 1–12 字、去空白；
        #           ③ 同路番号不得重复（否则面板/军表将出现两个同名单位）。
        # **不动** branches/troops/morale/training/station/arrears —— 改名不改变真账。
        if len(units) != 1:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：改名须指定单一编制单位。"
        new_name = str(payload.get("new_name", "") or "").strip()
        if not new_name or len(new_name) > 12:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：番号须为 1–12 字。"
        u = units[0]
        station = getattr(u, "station", "")
        if any(x is not u and getattr(x, "station", "") == station
               and str(getattr(x, "army_name", "") or "") == new_name
               for x in state.army_units):
            state.set_ai_pending_status(action_id, "rejected")
            return f"批红驳回：本路已有番号「{new_name}」。"
        old_name = str(getattr(u, "army_name", "") or "")
        u.army_name = new_name
        # 完整番号「路·军号」同步替换军号段，避免展示层一处新一处旧（`army_name || name` 已优先，
        # 但 `name` 会被其它军表直接显示，故一并同步）
        full = str(getattr(u, "name", "") or "")
        u.name = (full.split("·", 1)[0] + "·" + new_name) if "·" in full else new_name
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{old_name or '旧番号'} 改称「{new_name}」。"

    if act == "拆分":
        # 2026-09-27（方案 §3.2 方案 B）：从选中编制单位**拨出一部另立新番**（同路同军籍）。
        # 规则与理由：
        #   · **逐个兵种对半**（floor），余数留原军 → 两边非负且 Σbranches **精确**守恒；
        #   · 装备同法对半（Σ装备守恒）；morale/training 复制（新立之部沿用本军操练水平）；
        #   · **arrears 留原军**：欠饷随原番号追讨，不凭空把债务记到新单位；
        #   · **兵 POP size 不变**（兵额总账不变）→ ΣPOP 不变（POP 挂载律）；
        #   · `unit_id` = 原 + "s"+n（唯一、可复现）；`serial` = 原 +100（避让原序列）。
        if len(units) != 1:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：拆分须指定单一编制单位。"
        u = units[0]
        if sum(u.branches.values()) < 2:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：兵额不足，无可拆分。"
        from core.domains.military.army_models import ArmyUnit as _AU
        _new_br, _new_eq = {}, {}
        for _k, _v in list(u.branches.items()):
            _half = int(_v) // 2
            if _half > 0:
                _new_br[_k] = _half
            u.branches[_k] = int(_v) - _half
        u.branches = {k: v for k, v in u.branches.items() if v > 0}
        if not _new_br:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：各兵种仅 1 人，不足拆分。"
        _eq = dict(getattr(u, "equip", None) or {})
        for _k, _v in list(_eq.items()):
            try:
                _iv = int(_v)
            except Exception:      # noqa: BLE001
                continue
            _half = _iv // 2
            if _half > 0:
                _new_eq[_k] = _half
            _eq[_k] = _iv - _half
        u.equip = _eq
        _nn = str(payload.get("new_name", "") or "").strip() or \
            f"{getattr(u, 'army_name', '') or '本军'}·别部"
        _base = str(getattr(u, "unit_id", "") or "u") + "s"
        _i = 1
        while any(str(getattr(x, "unit_id", "")) == f"{_base}{_i}" for x in state.army_units):
            _i += 1
        _st = str(getattr(u, "station", "") or "")
        state.army_units.append(_AU(
            unit_id=f"{_base}{_i}",
            name=(f"{_st}·{_nn}" if _st else _nn),
            tier=str(getattr(u, "tier", "禁军") or "禁军"),
            branches=dict(_new_br), station=_st,
            defense_line=str(getattr(u, "defense_line", "") or ""),
            morale=int(_mil_int(getattr(u, "morale", 0))),
            training=int(_mil_int(getattr(u, "training", 0))),
            equip=dict(_new_eq),
            army_name=_nn,
            org_arm=str(getattr(u, "org_arm", "") or ""),
            scale=str(getattr(u, "scale", "") or ""),
            serial=int(_mil_int(getattr(u, "serial", 0))) + 100,
            arrears=0,
            commander=str(getattr(u, "commander", "") or ""),
        ))
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{label} 拨出「{_nn}」{sum(_new_br.values())} 人，别立一军。"

    if act == "合并":
        # 2026-09-27：同路**同军籍**两支合为一支（`merge_ids` 指定，选中者承接）。
        # 守恒：Σbranches/Σ装备 不变、兵 POP size 不变、ΣPOP 不变；**arrears 相加**（存续番号承接旧欠）。
        _ids = [str(x) for x in (payload.get("merge_ids") or []) if str(x).strip()]
        _picked = [x for x in state.army_units if str(getattr(x, "unit_id", "")) in _ids]
        if len(_picked) != 2:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：合并须指定两支编制单位。"
        _a, _b2 = _picked
        if str(getattr(_a, "station", "")) != str(getattr(_b2, "station", "")) or \
                str(getattr(_a, "tier", "")) != str(getattr(_b2, "tier", "")):
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：只能合并同一路、同一军籍的编制单位。"
        for _k, _v in (_b2.branches or {}).items():
            _a.branches[_k] = _a.branches.get(_k, 0) + int(_v)
        _eq = dict(getattr(_a, "equip", None) or {})
        for _k, _v in (getattr(_b2, "equip", None) or {}).items():
            _eq[_k] = int(_eq.get(_k, 0) or 0) + int(_v or 0)
        _a.equip = _eq
        _a.arrears = int(_mil_int(getattr(_a, "arrears", 0))) + int(_mil_int(getattr(_b2, "arrears", 0)))
        state.army_units.remove(_b2)
        state.set_ai_pending_status(action_id, "approved")
        return (f"批红：{label} 并为一军，兵额 {sum(_a.branches.values())} 人"
                f"（并欠饷 {_a.arrears} 贯）。")

    if act == "换帅":
        # 2026-09-27：指派统帅（展示层留痕）。校验：须为现有大臣、**一人不得领两军**。
        # ⚠️ 刻意**不**改战力/士气/结算：那属平衡设计，须单独拍板并补对拍断言。
        if len(units) != 1:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：换帅须指定单一编制单位。"
        _cm = str(payload.get("commander", "") or "").strip()
        if not _cm:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：须指定统帅姓名。"
        # 在朝大臣名册 = `state.loyalty` 的键（game_state.py:1346 亦以 `n in self.loyalty` 判在朝）；
        # 旧写法查 `state.ministers` —— 该属性**不存在**（2026-09-27 断言当场抓出）。
        _roster = getattr(state, "loyalty", None)
        if not isinstance(_roster, dict):
            _roster = getattr(state, "corruption", None)
        _ok_min = isinstance(_roster, dict) and _cm in _roster
        if not _ok_min:
            state.set_ai_pending_status(action_id, "rejected")
            return f"批红驳回：无此大臣「{_cm}」。"
        _other = next((x for x in state.army_units
                       if x is not units[0]
                       and str(getattr(x, "commander", "") or "") == _cm), None)
        if _other is not None:
            state.set_ai_pending_status(action_id, "rejected")
            return f"批红驳回：{_cm} 已领「{getattr(_other, 'name', '')}」，一人不得领两军。"
        _old = str(getattr(units[0], "commander", "") or "")
        units[0].commander = _cm
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{label} 统帅 {_old or '（虚位）'} → {_cm}。"

    if act == "裁撤":
        # 2026-09-27（方案 §3.2 方案 B）：**裁减兵额**，与增募对称（档位 scale×2000）。
        # ⚠️ 只减兵额，**不删编制单位实体**：编制单位按"每路禁/厢/乡各一支"被多处引用，
        #    删除属结构变更（须先定 unit_id/serial 规则）→ 裁到 0 亦保留空编制。
        # 归农：兵额减 N → 该路 `兵` POP size −N → 同路 `农` POP size +N（复员归田），
        #    **Σ(农 + 流民 + 兵) 不变**（POP 挂载律）；N 取 min(档位, 兵额, 兵POP) 以保证精确守恒。
        cut_total = 0
        for u in units:
            station = getattr(u, "station", "")
            if station not in state.prefectures:
                continue
            p = state.prefectures[station]
            troops = sum(u.branches.values())
            pop_bing = max(0, int(p["pops"]["兵"].get("size", 0) or 0))
            want = min(scale * 2000, troops, pop_bing)
            if want <= 0:
                continue
            left = want
            for key in sorted(u.branches, key=lambda k: -u.branches[k]):
                if left <= 0:
                    break
                take = min(left, u.branches[key])
                u.branches[key] = u.branches[key] - take
                left -= take
            u.branches = {k: v for k, v in u.branches.items() if v > 0}
            _cb = p["pops"]["兵"]
            _cf = p["pops"]["农"]
            if _pop_obj_add(state, _cb, "size", (pop_bing - want) - int(_cb.get("size", 0) or 0)) is None:
                _cb["size"] = pop_bing - want
            if _pop_obj_add(state, _cf, "size", -want) is None:
                _cf["size"] = int(_cf.get("size", 0) or 0) + want
            cut_total += want
        if cut_total <= 0:
            state.set_ai_pending_status(action_id, "rejected")
            return "批红驳回：无可裁之兵。"
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{label} 裁减 {cut_total} 人，复员归农。"

    if act == "调赴" and tgt:
        for u in units:
            u.station = tgt
        state.set_ai_pending_status(action_id, "approved")
        return f"批红：{label} 调赴 {tgt}。"

    state.set_ai_pending_status(action_id, "rejected")
    return f"批红驳回：未识军令动作「{act}」。"


# ============================================================
# 玩家主动军令（方案 §3.2 方案 B；2026-09-27 用户口径"对齐"参考图）
# ============================================================
# **参考图 8 按钮** → 命令层动作（仅列已实现者；拆分/合并/裁撤/换帅/改名尚无契约）
def _mil_int(v, d: int = 0) -> int:
    """军令用安全整数：坏值/NaN/inf → 默认值（本模块无 `_num`，勿误用别处的同名函数）。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return d
    if f != f or f in (float("inf"), float("-inf")):
        return d
    return int(f)


_MILITARY_BUTTON_ACTS = {
    "整编": "整编", "扩编": "增募", "地图调度": "调赴",
    "调度军令": "调赴",
    "拆分": "拆分", "合并": "合并", "换帅": "换帅",
    "裁撤": "裁撤", "改名": "改名",
}   # 参考图 8 类；“地图调度/调度军令”是同一动作的两种 UI 文案


def issue_military_order(state: GameState, unit_id: str, button: str,
                         scale: int = 3, target: str = "", new_name: str = "",
                         merge_unit_id: str = "", commander: str = "",
                         executor: str = "") -> str:
    """**玩家亲裁军令**：对象是**编制单位**（非兵种、非军籍整批），入队后即时批红。

    为什么这样接（三条，缺一不可）：
      ① **执行仍走唯一通道** `approve_ai_action` → `_apply_military_dispatch`：
         校验、档位封顶、钱粮与 POP 守恒都在那一处，本函数**不写任何状态**；
      ② **必留审计**：经 `enqueue_ai_action(kind="military_dispatch", proposer="玩家")` 入
         `ai_pending_actions`（与 AI 提议同构），批红后 `status="approved"`，可回溯谁在何月下的令；
      ③ **未实现的按钮明确拒绝**，不静默、不假装成功。
    """
    act = _MILITARY_BUTTON_ACTS.get(str(button or "").strip())
    if not act:
        return (f"未成：军令「{button}」尚无契约（现可施行："
                f"{'、'.join(_MILITARY_BUTTON_ACTS)}）。")
    uid = str(unit_id or "").strip()
    unit = next((u for u in (getattr(state, "army_units", None) or [])
                 if str(getattr(u, "unit_id", "") or "") == uid), None)
    if unit is None:
        return f"未成：无此编制单位「{uid}」。"

    # C-2：军令的增募/调赴/换帅/裁撤/合并/拆分都改变兵额或驻地，须由掌「调兵」
    # 事权主体执行。默认按枢密院（玩家亲裁军令的法定承办机构），调用方可显式传
    # executor（部门/官职/人名）以便拒绝越权主体；纯展示的整编/改名不在此门禁。
    # 皇威 >85（military_dispatch 已接线）⇒ 皇帝言出即行，跳过执行侧事权；
    # 皇威不足 ⇒ 必须走枢密院/掌「调兵」主体的正常流程。
    from core import imperial_mandate
    _direct = imperial_mandate.can_direct(state, "military_dispatch")
    if act in ("增募", "调赴", "换帅", "裁撤", "合并", "拆分") and not _direct:
        _executor = str(executor or "枢密院").strip()
        try:
            from core.authority_gate import check_matter_authority
            _ok, _label = check_matter_authority(state, _executor, "调兵")
        except Exception as e:  # noqa: BLE001
            return f"未成：军令事权核验异常（{type(e).__name__}），不予执行。"
        if not _ok:
            return f"未成：军令须由掌「调兵」事权主体执行；{_label}。"

    payload = {"army": str(getattr(unit, "tier", "禁军") or "禁军"), "action": act,
               "unit_id": uid, "scale": max(1, min(5, int(scale or 3))),
               "executor": executor, "imperial_direct": bool(_direct)}
    if act == "改名" or act == "拆分":
        payload["new_name"] = str(new_name or "").strip()
    if act == "换帅":
        payload["commander"] = str(commander or "").strip()
    if act == "合并":
        _mid = str(merge_unit_id or "").strip()
        if not _mid or _mid == uid:
            return "未成：合并须指定**另一支**编制单位。"
        payload["merge_ids"] = [uid, _mid]
    if act == "调赴":
        dest = str(target or "").strip()
        if dest not in (getattr(state, "prefectures", None) or {}):
            return f"未成：调赴目的地「{dest}」不在本朝州路中。"
        payload["target"] = dest

    title = f"{getattr(unit, 'tier', '')}·{getattr(unit, 'name', '') or uid}·{button}"
    aid = state.enqueue_ai_action(
        "military_dispatch", title,
        f"玩家亲裁军令（编制单位 {uid}）", payload, proposer="玩家")
    result = approve_ai_action(state, aid)
    if _direct and "驳回" not in result and "未成" not in result:
        imperial_mandate.charge_direct_cost(state, "military_dispatch")
    return result


__all__ = [
    "new_game", "audience_minister", "issue_decree", "issue_secret_decree",
    "do_personal_action", "choose_imperial_action", "choose_major_policy", "advance_month", "settle_turn",
    "settle_local", "finish_turn", "monthly_report_args",
    "resolve_event", "save", "load", "save_slots", "conclude",
    "audience_dialogue", "audience_dialogue_prepare", "audience_dialogue_apply",
    "envoy_diplomacy",
    "issue_drafted_decree", "preview_draft",
    "approve_ai_action", "reject_ai_action",
    "issue_military_order",
    "confirm_timeline_break",
    "dismiss_pending_break",
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
    # 管道二：天道立场定势注入（天理定立场，防大模型被玩家口吻牵着走）
    _summary = kwargs["state_summary"]
    try:
        from core.ai.tiandao_facade import TianDaoFacade
        _st = TianDaoFacade.derive_dialogue_stance(
            kwargs["minister_name"], kwargs["player_input"], kwargs["state"])
        if _st.get("defined"):
            _floor = _st.get("compromise_threshold")
            _summary = (
                f"{_summary}\n【天道定势·须恪守，不得因圣意口吻改易】"
                f"立场={_st.get('stance')}（强度{_st.get('intensity')}"
                f"{'，在任' if _st.get('in_office') else '，已去职'}）"
                f"；核心论据={_st.get('argument_anchor')}"
                + (f"；可让步底线={_floor}" if _floor is not None else "")
            )
    except Exception:  # noqa: BLE001 — 定势失败退回原始摘要，不阻断召对
        _summary = kwargs["state_summary"]
    try:
        # 按位置传递（兼容真实 AIClient 与测试替身的参数名差异），state 走关键字
        obj = ai_client.dialogue(
            kwargs["minister_name"], kwargs["faction"], kwargs["faction_stance"],
            kwargs["minister_traits"], kwargs["minister_role"], kwargs["era_name"],
            kwargs["history"], kwargs["player_input"], _summary,
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
    `core.domains.diplomacy.treaty.apply_treaty`（旧路径 `core.diplomacy_treaty`）均已实现且带 T5 测试，却**全库无生产调用方**
    —— 前端「遣使」原走 `audience_dialogue`（把外国君主当大臣召对），于是协议永不
    落地、`state.treaties` 恒空。

    拒绝式纪律（与召对同级）：AI 未接入或校验不过 → 不伪造国主应答与协议，只记外交
    纪事；`apply_treaty` 自身校验对象/类型/内帑，不通过则如实回奏而不写 treaties。
    """
    from core.domains.diplomacy.treaty import apply_treaty   # 第十四包：直认真实家

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
        log.warning("[diplomacy] 遣使%s失败: %s", target, e)
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


def _faction_stance_word(state: GameState, faction: str) -> str:
    """派系满意度（0~100）→ 对话注入的「派系底色」档位词。

    档位：≥70 上气昂扬乐于任事 / 40~70 循例奉行 / <40 心怀怨望多讥讽。
    只给档位词，不外泄满意度数值（与 loyalty/满意度脱敏铁律一致）。
    """
    try:
        sat = int(state.factions.get(faction, {}).get("satisfaction", 50))
    except Exception:
        sat = 50
    if sat >= 70:
        return "本派上意气昂扬，乐于任事，愿附议陛下之兴作"
    if sat >= 40:
        return "本派循例奉行，不置可否，勉力王事而已"
    return "本派心怀怨望，言辞间多有讥讽，凡有兴作必陈其弊"


def audience_dialogue_prepare(state: GameState, minister_name: str,
                              player_input: str):
    """召对前奏（主线程）：身份/状态校验 + 入史（朕言/短期日志）+ 构建 AI 入参。

    返回 (kwargs, note)：
      - note 非 None → 不可召对（已薨/罢黜），已写入史册说明，无需 AI；
      - 否则 kwargs 为 ai_client.dialogue 的调用参数（state 为只读引用；
        history 为快照列表，避免后台读取时主线程追加的竞态）。
    """
    from content.ministers import HISTORICAL_FIGURES
    from core.faction_basis import resolve_faction_key  # 延迟导入（项目约定）
    # 找到大臣所属派系：先按档案 faction（覆盖全体大臣，经 resolve_faction_key
    # 归一），回退按派系领袖反查，再回退「中枢」。
    # 修复：旧逻辑只认「派系领袖」，非领袖大臣一律落到「中枢」，persona 立场尽失。
    fig = HISTORICAL_FIGURES.get(minister_name, {})
    faction = resolve_faction_key(fig.get("faction", "")) or ""
    if not faction:
        for fn, f in state.factions.items():
            if f["leader"] == minister_name:
                faction = fn
                break
    if not faction:
        faction = "中枢"
    minister_traits = fig.get("traits", "老成持重")
    minister_role = fig.get("role", "朝中大臣")
    # 派系底色：由该派系对朝局的满意度派生档位词（不外泄数值）。
    # 修复：旧逻辑把 FACTION_INIT 的派系领袖**人名**当 stance 注入（「派系底色：蔡京」）。
    faction_stance = _faction_stance_word(state, faction)
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
    # 动态记忆图谱分层检索注入（M304：图谱存史，召对按需切片，严格锁定 350 字以内防 Token 膨胀）
    try:
        from memory.memory_graph import get_memory_graph
        mem = get_memory_graph(getattr(state, "slot", 0))
        h_hits = mem.retrieve_hierarchical(minister_name, top_k=2)
        if h_hits and h_hits.get("summary"):
            state_summary += f"\n【前尘往事】{str(h_hits['summary'])[:350]}"
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

    无回奏（AI 不可用/失败标记）时**或回奏过短**（<10 字，如「臣谨奏」占位）
    不写史册，返回空串，由调用方走 fallback。
    """
    reply = obj.get("reply", "") if isinstance(obj, dict) else str(obj or "")
    if not reply or len(reply.strip()) < 4:
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
    # M34-③：召对**回奏**若含财政疑虑 → 记入发现链二级"怀疑"（唯一写入点）
    try:
        from core.audit_case import record_suspicion
        record_suspicion(state, reply, source="召对", minister=minister_name)
    except Exception:  # noqa: BLE001 — 奏报记录失败不得阻断召对落定
        pass
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

    # ④ 派系离散（2026-09-19 三期接口接线）：非正常离任（贬黜/处死/战殁）→
    # 该派系在**官僚**政治盘上小幅退出（党羽离散，其余派系按剩余量归一吸收）。
    # 只改「立场占比」，**不动 POP size**（人头侧由官制步负责），Σ 占比仍为 1。
    if _fac and reason in ("贬黜", "处死", "战殁"):
        try:
            from core.domains.politics.split import exit_faction_members, split_of
            cur = split_of(state, "官僚")
            if _fac in cur and cur[_fac] > 0:
                exit_faction_members(state, "官僚", _fac, cur[_fac] * 0.05)
                log.append(f"[派系] {_fac} 失重臣（{name}·{reason}），其党羽稍散")
        except Exception as e:  # noqa: BLE001
            log.append(f"[派系] {_fac} 离散结算异常：{type(e).__name__}")

    # 特殊修饰（条件式判定，写死可审查；数值仍走档位换算）
    _corr = state.corruption.get(name, 0.0)
    _has_war = bool(set(traits_of(name)) & {"军略", "忠勇"})
    for spec in rule.get("specials", []):
        when = spec.get("when", "")
        hit = {
            "中立派": _fac == "中立派",
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


# ============================================================
# M314 产业物流调拨（2026-10-18 全审生产入口）
# ============================================================
def dispatch_logistics(state, origin: str, target: str, dim: str,
                       amount, owner: str = "state:treasury") -> str:
    """玩家/AI 调拨产业原料：`dispatch_industry_logistics` 的唯一命令入口。

    - origin/target 为路名；实际收发治所由物流耦合层取首府治所；
    - 货从始发地官仓（state:/local: 货主）或民仓（其它货主）真扣；
    - 走到货才入账的**在途批次**，并清算沈括途耗/镖局风险；
    - 参数非法或货源不足 ⇒ ValueError（由 `/api/action` 映射为 4xx）。
    """
    from core.domains.economy.logistics_coupler import dispatch_industry_logistics
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        raise ValueError("调拨量须为数字")
    if amt <= 0:
        raise ValueError("调拨量须大于 0")
    if not str(origin).strip() or not str(target).strip():
        raise ValueError("始发路与目标路均不能为空")
    if str(origin).strip() == str(target).strip():
        raise ValueError("同路无需调拨（请用市集内成交）")
    res = dispatch_industry_logistics(
        state, str(origin).strip(), str(target).strip(), str(dim).strip(),
        amt, owner=str(owner or "state:treasury"))
    if not res.get("ok"):
        raise ValueError(f"调拨失败：{res.get('reason') or '未知原因'}")
    return (f"已调拨 {amt:,.0f} 单位「{dim}」：{origin} → {target}"
            f"（{res.get('transit_mode', 'overland')}，批次 {res.get('batch_id')}）")