# -*- coding: utf-8 -*-
"""M36 **察访（监司／御史差遣）**编制与在途容器（**监察世界接口层**：只给事实/约束/合法性/迁移/存档/守恒）。

⚠️ **称谓规范（2026-10-11 用户裁定）**：故事背景为**宋**，宋制**无**「巡按」（那是明代巡按御史）。
本模块技术层统一用 `inspection_*`；**内容层称谓一律按朝代映射**（`INSPECTION_IDENTITY`）：
宋＝**察访**／**差遣**（御史台・监司：转运使／提点刑狱／提举常平）；明＝巡按御史；清＝巡察·钦差。

架构定位（用户裁定 2026-10-11）：
```
游戏系统提供事实 → 决策方读取信息与约束 → 决策方提出行动 → 系统校验合法性 → 执行并产生反馈
```
**决策方＝玩家或扮演玩家的外部 AI**；⚠️ **本游引擎内不存在中央政务 AI**——
引擎**不**自己决定是否察访、派谁、查哪里（那正是"自动派遣/固定触发"被禁止的原因）。
**系统负责**：`inspection_capacity()`（可授差遣数/在途）、`inspection_candidates()`（既有官员池事实）、
任务合法性检查、状态迁移（时间推进）、存档、守恒校验；
**决策方负责**：是否差遣／授何人／察何处／察何事／明察还是密访／是否暂缓（**不提前枚举为固定规则**）。

**本模块禁止**（M36-1／M36-2 边界）：
- 自动派遣算法、固定触发条件、自动监察策略（**无任何自动派遣/自动触发**）；
- 修改 POP／occupation／`settlement_common`／`money`／`finance`／`tax`／`grain`；
- **自动**判断调查结论/产生证据/成案/处罚/定罪/抄没/降官；**不调用** `audit_case.resolve_audit`。

流程仍为：观察 → 察访任务 → 证据 → 审理 → 执行（M36 只覆盖**任务容器、生命周期与奏报容器**）。

M36-2（2026-10-11 裁决）新增：任务生命周期 `created → active → completed ／ expired`
＋ **奏报容器**（`file_inspection_report`：只记录奏报与**已存在**案卷的引用，**不建案**）。
M36-3（2026-10-11 裁决）新增：**反馈观察层**（`inspection_feedback`，只记录政治后果，不判断成败）。
"""
from typing import Any, Dict, List, Optional

__all__ = ["ensure_inspection_schema", "window_for", "inspection_capacity",
           "inspection_candidates", "enqueue_inspection", "inspection_tick",
           "inspection_task_list", "inspection_readout", "file_inspection_report",
           "ensure_inspection_feedback_schema", "inspection_feedback_readout",
           "inspection_identity"]

# M36-2 生命周期（AI 提交 → created；月度推进 → active；回奏 → completed；超期 → expired）
_TASK_STATUSES = ("created", "active", "completed", "expired")


def _i(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _period(state) -> str:
    """结算期标识 `年-月`（tick 幂等键；跨年不碰撞）。"""
    return f"{_i(getattr(state, 'year', 0))}-{_i(getattr(state, 'month', 0))}"


# ---------------------------------------------------------------- M36-3 反馈观察层
def ensure_inspection_feedback_schema(state) -> None:
    """**幂等**补齐反馈容器 `state.inspection_feedback`（旧档迁移 / 新局）。

    结构：`{"observables": {四键: float}, "events": int, "by_route": {路: {...}}, "recent": [...]}`。
    **只读口径**：本容器是**累计观察量**，与 `identity_pressures()` 同名项**不同物**
    （那是即时身份压力；本处是监察事件累计反馈）。
    """
    from content.data import INSPECTION_FEEDBACK_KEYS
    fb = getattr(state, "inspection_feedback", None)
    if not isinstance(fb, dict):
        fb = {}
    obs = fb.get("observables")
    obs = obs if isinstance(obs, dict) else {}
    for k in tuple(INSPECTION_FEEDBACK_KEYS or ()):
        obs.setdefault(k, 0.0)
    fb["observables"] = obs
    fb.setdefault("events", 0)
    if not isinstance(fb.get("by_route"), dict):
        fb["by_route"] = {}
    if not isinstance(fb.get("recent"), list):
        fb["recent"] = []
    state.inspection_feedback = fb


def _record_feedback(state, route: str, kind: str, secret: bool, event: str,
                     deltas: Dict[str, float]) -> Dict[str, Any]:
    """**唯一写入点**：把一次监察事件的反馈写入容器（累计观察量；**只写本容器**）。

    禁止：不改 money／tax／grain／POP／occupation／官员属性／案卷，**不写** rumor 状态与 `grip`。
    """
    from content.data import INSPECTION_FEEDBACK_KEYS, INSPECTION_FEEDBACK_LOG_CAP
    ensure_inspection_feedback_schema(state)
    fb = state.inspection_feedback
    applied: Dict[str, float] = {}
    for k in tuple(INSPECTION_FEEDBACK_KEYS or ()):
        dv = float(deltas.get(k, 0.0) or 0.0)
        if dv:
            fb["observables"][k] = round(float(fb["observables"].get(k, 0.0)) + dv, 3)
        applied[k] = round(dv, 3)
    fb["events"] = _i(fb.get("events")) + 1
    entry = {"period": _period(state), "route": route, "kind": kind,
             "secret": bool(secret), "event": event, "deltas": applied}
    fb["recent"].append(entry)
    cap = int(INSPECTION_FEEDBACK_LOG_CAP or 24)
    if len(fb["recent"]) > cap:
        del fb["recent"][:len(fb["recent"]) - cap]
    br = fb["by_route"].get(route)
    if not isinstance(br, dict):
        br = {"observables": {k: 0.0 for k in tuple(INSPECTION_FEEDBACK_KEYS or ())},
              "events": 0}
        fb["by_route"][route] = br
    for k in tuple(INSPECTION_FEEDBACK_KEYS or ()):
        br["observables"][k] = round(float(br["observables"].get(k, 0.0))
                                     + float(applied.get(k, 0.0) or 0.0), 3)
    br["events"] = _i(br.get("events")) + 1
    br["last_event"] = event
    br["last_period"] = _period(state)
    return entry


def _feedback_deltas_dispatch(secret: bool) -> Dict[str, float]:
    """① 出发：明查＝地方知中央关注（戒备↑、文书整理加强）；密查＝短期戒备较低。"""
    from content.data import (INSPECTION_FEEDBACK_CAUTION_PUBLIC,
                              INSPECTION_FEEDBACK_CAUTION_SECRET)
    c = (INSPECTION_FEEDBACK_CAUTION_SECRET if secret
         else INSPECTION_FEEDBACK_CAUTION_PUBLIC)
    return {"local_caution": float(c)}


def _feedback_deltas_expired(secret: bool) -> Dict[str, float]:
    """① + ② 超期未回：明查＝官场议论微升；**密查＝暴露后反弹更明显**（观察量，非惩罚）。"""
    from content.data import (INSPECTION_FEEDBACK_EXPIRE_EXPOSURE_PUBLIC,
                              INSPECTION_FEEDBACK_EXPIRE_EXPOSURE_SECRET,
                              INSPECTION_FEEDBACK_EXPIRE_PRESSURE_PUBLIC,
                              INSPECTION_FEEDBACK_EXPIRE_PRESSURE_SECRET,
                              INSPECTION_FEEDBACK_EXPIRE_RUMOR_PUBLIC,
                              INSPECTION_FEEDBACK_EXPIRE_RUMOR_SECRET)
    if secret:
        return {"exposure": float(INSPECTION_FEEDBACK_EXPIRE_EXPOSURE_SECRET),
                "official_pressure": float(INSPECTION_FEEDBACK_EXPIRE_PRESSURE_SECRET),
                "rumor_change": float(INSPECTION_FEEDBACK_EXPIRE_RUMOR_SECRET)}
    return {"exposure": float(INSPECTION_FEEDBACK_EXPIRE_EXPOSURE_PUBLIC),
            "official_pressure": float(INSPECTION_FEEDBACK_EXPIRE_PRESSURE_PUBLIC),
            "rumor_change": float(INSPECTION_FEEDBACK_EXPIRE_RUMOR_PUBLIC)}


def _feedback_deltas_filed(secret: bool, late: bool) -> Dict[str, float]:
    """② 回奏：明查＝民间期待／议论微升；密查＝走漏少；**迟回**＝更可能走漏（观察量）。"""
    from content.data import (INSPECTION_FEEDBACK_DONE_RUMOR_PUBLIC,
                              INSPECTION_FEEDBACK_DONE_RUMOR_SECRET,
                              INSPECTION_FEEDBACK_LATE_EXPOSURE,
                              INSPECTION_FEEDBACK_LATE_PRESSURE)
    d = {"rumor_change": float(INSPECTION_FEEDBACK_DONE_RUMOR_SECRET if secret
                               else INSPECTION_FEEDBACK_DONE_RUMOR_PUBLIC)}
    if late:
        d["exposure"] = float(INSPECTION_FEEDBACK_LATE_EXPOSURE)
        d["official_pressure"] = float(INSPECTION_FEEDBACK_LATE_PRESSURE)
    return d


def ensure_inspection_schema(state) -> None:
    """幂等补齐容器（旧档迁移 / 新局）：`inspection_tasks`／`inspection_agent_state`。

    M36-2：同时**规范化在途任务**（旧档任务无 `report`／`created_period` 等字段时补默认；
    未知状态归一为 `active`），可安全重复调用（全部 `setdefault`）。
    """
    if not isinstance(getattr(state, "inspection_tasks", None), list):
        state.inspection_tasks = []
    st = getattr(state, "inspection_agent_state", None)
    if not isinstance(st, dict):
        st = {}
    st.setdefault("started", 0)
    st.setdefault("done", 0)
    st.setdefault("expired", 0)
    state.inspection_agent_state = st
    for seq, t in enumerate(state.inspection_tasks):
        _normalize_task(t, seq)
    ensure_inspection_feedback_schema(state)       # M36-3 反馈容器（幂等）


def _normalize_task(t: Any, seq: int) -> None:
    """**幂等**规范化单个任务（旧档兼容；不改任何财政/POP）。"""
    if not isinstance(t, dict):
        return
    kind = str(t.get("kind") or "")
    t.setdefault("id", f"legacy-{seq + 1}")
    t.setdefault("route", "")
    t.setdefault("kind", kind)
    t.setdefault("secret", False)
    t.setdefault("status", "active")
    if str(t.get("status")) not in _TASK_STATUSES:
        t["status"] = "active"                      # 未知状态归一（不猜成 completed）
    t.setdefault("window_months", window_for(kind, bool(t.get("secret"))))
    t.setdefault("remaining", int(t.get("window_months") or 0))
    t.setdefault("created_period", t.get("started_period"))
    t.setdefault("started_period", t.get("created_period"))
    t.setdefault("dispatched_period",
                 t.get("started_period") if str(t.get("status")) != "created" else None)
    t.setdefault("settled_turn", None)
    t.setdefault("report", None)                    # M36-2 回奏容器（默认空）


def inspection_identity(state=None, era: str = "") -> Dict[str, Any]:
    """**只读**朝代身份映射（内容层称谓）：宋＝**察访/差遣**；明＝巡按御史；清＝巡察·钦差。

    供 UI/AI 按本朝制度说话；**不改任何状态**。技术层函数名一律 `inspection_*`（跨朝代复用）。
    """
    from content.data import INSPECTION_IDENTITY, INSPECTION_IDENTITY_DEFAULT_ERA
    _era = str(era or INSPECTION_IDENTITY_DEFAULT_ERA)
    prof = (INSPECTION_IDENTITY or {}).get(_era) or (INSPECTION_IDENTITY or {}).get(
        INSPECTION_IDENTITY_DEFAULT_ERA) or {}
    out = dict(prof)
    out["era_requested"] = _era
    out["note"] = ("本朝（宋）用语以 term／dispatch／agency／actors 为准：中央监察在御史台、"
                   "地方按察在监司、出使以**差遣**；技术层接口名保持 `inspection_*`，"
                   "以便跨朝代（明／清）复用同一套接口。")
    return out


def window_for(kind: str, secret: bool = False) -> int:
    """D3/D4 时间窗口（月）：普通 2／复杂 3；**密查固定 4**（不提高成功率，只换时间与风险）。"""
    from content.data import (INSPECTION_KIND_COMPLEXITY, INSPECTION_WINDOW_COMPLEX,
                              INSPECTION_WINDOW_NORMAL, INSPECTION_WINDOW_SECRET)
    if secret:
        return int(INSPECTION_WINDOW_SECRET)
    return int(INSPECTION_WINDOW_COMPLEX
               if (INSPECTION_KIND_COMPLEXITY or {}).get(kind) == "complex"
               else INSPECTION_WINDOW_NORMAL)


def inspection_candidates(state) -> Dict[str, Dict[str, int]]:
    """**只读**候选池（D1）：逐路 `waiting`（待阙）＋`sinecure`（祠禄）人数——**既有官员池**。

    固定口径（**不用动态百分比**）；**不看派系/党争**（D8：只给"身份 + 可用状态"这一层）。
    本函数**只读**：不改 POP／官员池／粮耗。
    新局时官员皆在岗（`on_post`），故候选池通常为 0，须待**冗官/祠禄**渐生方可差遣——
    这正是"有限人力"的体现（`on_post` 一并给出，仅作**事实**，不参与可派口径）。
    """
    out: Dict[str, Dict[str, int]] = {}
    for name, p in (getattr(state, "prefectures", None) or {}).items():
        if not isinstance(p, dict):
            continue
        pool = (p.get("pops") or {}).get("官僚")
        pool = pool if isinstance(pool, dict) else {}
        waiting = max(0, _i(pool.get("waiting")))
        sinecure = max(0, _i(pool.get("sinecure")))
        out[name] = {"waiting": waiting, "sinecure": sinecure,
                     "on_post": max(0, _i(pool.get("on_post"))),
                     "candidates": waiting + sinecure}
    return out


def inspection_capacity(state, tier: str = "") -> Dict[str, Any]:
    """**只读**编制容量（D2）：在途/受理/上限/富余 ＋ 逐路占用。**不读任何财政量**。

    `created`（已受理待发）与 `active`（在途）**同占名额**（`occupied`）——避免
    在受理与在途之间出现上限漏洞；两者分开给出（AI 需要知道有几个已出发）。
    `tier`：**只由调用方显式传入**（默认「正常」），**不自动**随民怨/政治状态升档；
    接受中文或别名（`small`/`normal`/`strong`）。
    """
    try:
        from content.data import (INSPECTION_CAPACITY_TIER_ALIASES,
                                  INSPECTION_MAX_ACTIVE_DEFAULT,
                                  INSPECTION_MAX_ACTIVE_TASKS,
                                  INSPECTION_MAX_ACTIVE_TIER_DEFAULT)
    except ImportError:                              # 兜底（老常量集）
        from content.data import (INSPECTION_MAX_ACTIVE_DEFAULT,
                                  INSPECTION_MAX_ACTIVE_TASKS)
        INSPECTION_CAPACITY_TIER_ALIASES = {}
        INSPECTION_MAX_ACTIVE_TIER_DEFAULT = "正常"
    ensure_inspection_schema(state)
    busy = {"created": 0, "active": 0}
    by_route: Dict[str, int] = {}
    for t in state.inspection_tasks:
        if not isinstance(t, dict):
            continue
        _st = str(t.get("status") or "active")
        if _st not in busy:
            continue
        busy[_st] += 1
        rk = str(t.get("route") or "")
        by_route[rk] = by_route.get(rk, 0) + 1
    _tier = str(tier or INSPECTION_MAX_ACTIVE_TIER_DEFAULT)
    _tier = str((INSPECTION_CAPACITY_TIER_ALIASES or {}).get(_tier, _tier))
    cap = int((INSPECTION_MAX_ACTIVE_TASKS or {}).get(_tier, INSPECTION_MAX_ACTIVE_DEFAULT))
    occupied = busy["created"] + busy["active"]
    return {"tier": _tier, "max_active_tasks": cap,
            "created": busy["created"], "active": busy["active"],
            "occupied": occupied, "free": max(0, cap - occupied),
            "by_route": by_route,
            "tiers": dict(INSPECTION_MAX_ACTIVE_TASKS or {})}


def enqueue_inspection(state, route: str, kind: str, secret: bool = False,
                       log: Optional[list] = None) -> Dict[str, Any]:
    """**入列**一件察访差遣（**系统校验合法性 → 执行**；**绝不自动调用**）。

    合法性（引擎职责）：① 路存在；② 种类在首批清单（D5）；③ 在途未超上限（D2）；
    ④ 该路候选池 > 0（D1）。
    **不做**任何"该不该派"的判断（那是 **AI 的决策空间**）；仅容器写入，
    **不**改财政／POP／欠给，**不**成案。
    注：候选池仅作**门槛**（> 0），本批**不预扣**官员（禁止写 POP）；逐路精确预扣若需要，
    留待 M36-2 在容器内记数（仍不动 POP）。
    """
    from content.data import INSPECTION_KINDS
    ensure_inspection_schema(state)
    prefs = getattr(state, "prefectures", None) or {}
    if route not in prefs:
        return {"ok": False, "reason": f"路名不存在：{route}"}
    if kind not in tuple(INSPECTION_KINDS or ()):
        return {"ok": False, "reason": f"本批未开放的任务种类：{kind}"}
    cap = inspection_capacity(state)
    if cap["free"] <= 0:
        return {"ok": False, "reason": f"在途已达上限（{cap['max_active_tasks']}）"}
    cand = inspection_candidates(state).get(route) or {}
    if _i(cand.get("candidates")) <= 0:
        return {"ok": False, "reason": f"{route} 无可差遣官员（waiting+sinecure=0）"}
    turn = _i(getattr(state, "turn", 0))
    win = window_for(kind, secret)
    task = {"id": f"ins{_period(state)}-{len(state.inspection_tasks) + 1}",
            "route": route, "kind": kind, "secret": bool(secret),
            "window_months": win, "remaining": win,
            "status": "created",                     # M36-2：受理待发（出发由月度推进完成）
            "created_period": _period(state),
            "started_period": _period(state),
            "started_turn": turn,
            "dispatched_period": None,
            "settled_turn": None,
            "report": None}
    state.inspection_tasks.append(task)
    state.inspection_agent_state["started"] = \
        _i(state.inspection_agent_state.get("started")) + 1
    if log is not None:
        log.append(f"[察访] 授差遣赴 {route} {kind}"
                   f"{'（密访）' if secret else ''}，限 {win} 月（待发）")
    return {"ok": True, "task": task}


def inspection_tick(state, log: Optional[list] = None) -> Dict[str, int]:
    """**月度状态迁移**（幂等）：`created → active`（出发），在途 `remaining −1`，到期 → `expired`。

    - **出发**：受理当期的结算即完成出发（`dispatched_period`），**出发当月不扣窗口**；
    - **推进**：此后每结算期 `remaining −1`；归零 → `expired`（＝**超期未回**，非"查出问题"）；
    - **幂等**：同结算期重复调用不重复出发/扣减（`last_tick_period`＝"年-月"）；
    - **不生案**：**不**调用 `resolve_audit`、**不**产生证据/案卷/处罚，**不**写 money／finance／POP／欠给／粮。
    """
    ensure_inspection_schema(state)
    now = _period(state)
    dispatched = 0
    advanced = 0
    expired = 0
    for t in state.inspection_tasks:
        if not isinstance(t, dict):
            continue
        _st = str(t.get("status") or "active")
        if _st not in ("created", "active"):
            continue
        if str(t.get("last_tick_period") or "") == now:
            continue                              # **幂等**：同结算期不重复处理
        t["last_tick_period"] = now
        if _st == "created":                      # 受理 → 出发（本期不扣窗口）
            t["status"] = "active"
            t["dispatched_period"] = now
            dispatched += 1
            # 🟢 M36-3 ①：出发的**戒备/暴露**反馈（观察量；只写反馈容器）
            _record_feedback(state, str(t.get("route") or ""), str(t.get("kind") or ""),
                             bool(t.get("secret")), "dispatch",
                             _feedback_deltas_dispatch(bool(t.get("secret"))))
            continue
        t["remaining"] = max(0, _i(t.get("remaining")) - 1)
        advanced += 1
        if _i(t.get("remaining")) <= 0:
            t["status"] = "expired"
            t["settled_turn"] = _i(getattr(state, "turn", 0))
            t["settled_period"] = now
            expired += 1
            state.inspection_agent_state["expired"] = \
                _i(state.inspection_agent_state.get("expired")) + 1
            # 🟢 M36-3 ①+②：超期（＝暴露风险，**非**"查出问题"）反馈；密查反弹更明显
            _record_feedback(state, str(t.get("route") or ""), str(t.get("kind") or ""),
                             bool(t.get("secret")), "expired",
                             _feedback_deltas_expired(bool(t.get("secret"))))
    if log is not None and (dispatched or advanced or expired):
        log.append(f"[察访] 出发 {dispatched} 项，在途推进 {advanced} 项，超期 {expired} 项")
    return {"dispatched": dispatched, "advanced": advanced, "expired": expired}


def file_inspection_report(state, task_id: str, summary: str = "",
                           case_id: Optional[str] = None,
                           log: Optional[list] = None) -> Dict[str, Any]:
    """**奏报容器**：登记察访奏报（`active → completed`；超期后奏报记 `late=True`）。

    **系统只做容器与合法性**：
    - ① 任务存在；② 已出发（`created` 不可回奏）；③ **未重复回奏**（已完成则拒绝）；
    - ④ 若给 `case_id`，该案卷**必须已存在**于 `state.audit_cases`（引擎**绝不建案**，
      只做引用校验，避免悬空引用）。
    **不**判断调查结论、**不**产生证据、**不**成案/处罚、**不**写任何财政/POP。
    """
    ensure_inspection_schema(state)
    tid = str(task_id or "")
    task = next((t for t in state.inspection_tasks
                 if isinstance(t, dict) and str(t.get("id")) == tid), None)
    if task is None:
        return {"ok": False, "reason": f"任务不存在：{tid}"}
    _st = str(task.get("status") or "")
    if _st == "completed":
        return {"ok": False, "reason": f"任务已回奏，不可重复（{tid}）"}
    if _st == "created":
        return {"ok": False, "reason": f"任务尚未出发，无可回奏（{tid}）"}
    cases = getattr(state, "audit_cases", None) or {}
    if case_id is not None and str(case_id) not in cases:
        return {"ok": False, "reason": f"未知案卷引用（引擎不建案）：{case_id}"}
    now = _period(state)
    task["report"] = {"summary": str(summary or "")[:500],
                      "case_id": (str(case_id) if case_id is not None else None),
                      "filed_period": now,
                      "filed_turn": _i(getattr(state, "turn", 0)),
                      "late": _st == "expired"}       # 超期后回奏：**标注**而非改写历史
    task["status"] = "completed"
    task["settled_period"] = now
    task["settled_turn"] = _i(getattr(state, "turn", 0))
    state.inspection_agent_state["done"] = \
        _i(state.inspection_agent_state.get("done")) + 1
    # 🟢 M36-3 ②：回奏的风闻反馈（明查＝期待/议论微升；密查＝走漏少；迟回＝更可能走漏）
    _record_feedback(state, str(task.get("route") or ""), str(task.get("kind") or ""),
                     bool(task.get("secret")), "completed",
                     _feedback_deltas_filed(bool(task.get("secret")),
                                            bool(task["report"]["late"])))
    if log is not None:
        log.append(f"[察访] {task.get('route')} {task.get('kind')} 奏报"
                   f"{'（超期）' if task['report']['late'] else ''}")
    return {"ok": True, "task": task, "report": task["report"]}


def inspection_task_list(state) -> List[Dict[str, Any]]:
    """**只读**任务列表（浅拷贝，供 AI/面板；调用不改状态）。"""
    ensure_inspection_schema(state)
    return [dict(t) for t in state.inspection_tasks if isinstance(t, dict)]


def inspection_readout(state) -> Dict[str, Any]:
    """**只读**汇总（**AI 决策入口**）：编制容量 ＋ 候选（逐路事实）＋ 在途/回奏状态计数 ＋ 任务列表。

    仅提供**事实与约束**；不提供"该不该派/派谁/查哪里/如何解释回奏"的建议（AI 自行判断）。
    """
    cap = inspection_capacity(state)
    cands = inspection_candidates(state)
    total = sum(_i(v.get("candidates")) for v in cands.values())
    counts = {s: 0 for s in _TASK_STATUSES}
    pending: List[str] = []
    for t in state.inspection_tasks:
        if not isinstance(t, dict):
            continue
        _st = str(t.get("status") or "active")
        counts[_st if _st in counts else "active"] += 1
        _rep = t.get("report")
        if _st == "completed" and isinstance(_rep, dict) and _rep.get("suspicion") is None:
            pending.append(str(t.get("id") or ""))
    return {"capacity": cap,
            "candidates_total": total,
            "candidates_by_route": cands,
            "status_counts": counts,
            "identity": inspection_identity(state),
            # M36-4 事实（**不替代决策**）：已奏报、尚未经决策方桥接入怀疑层的差遣
            "suspicion_pending": pending,
            "tasks": inspection_task_list(state)}


def inspection_feedback_readout(state) -> Dict[str, Any]:
    """🟢 M36-3 **监察反馈观察量**读数（**只读**；**不判断成败**，无成功率/概率/阻力）。

    返回**事实**：
    - `observables`：累计反馈（`exposure`／`local_caution`／`official_pressure`／`rumor_change`）；
    - `by_route`／`recent`：逐路累计与最近事件（有界）；
    - `context`：**只读**引用既有通道 —— `rumor_tier()`（风闻档位）、`grip_by_route`（把持度，
      即"文书整理/把持"现状）、`backlash`（P3-4 反向观察量）。这些**只读**，本层不写。
    - `interpretation`：固定 `"record-only"` —— 明确**本层不做**成败判定。
    """
    from content.data import INSPECTION_FEEDBACK_KEYS
    ensure_inspection_feedback_schema(state)
    fb = state.inspection_feedback
    obs = {k: round(float(fb["observables"].get(k, 0.0) or 0.0), 3)
           for k in tuple(INSPECTION_FEEDBACK_KEYS or ())}
    grip = {}
    for name, p in (getattr(state, "prefectures", None) or {}).items():
        if not isinstance(p, dict):
            continue
        cd = p.get("clerks_detail")
        if isinstance(cd, dict) and cd.get("grip") is not None:
            grip[name] = round(float(cd.get("grip") or 0.0), 3)
    ctx: Dict[str, Any] = {"grip_by_route": grip}
    _rt = getattr(state, "rumor_tier", None)
    if callable(_rt):
        try:
            ctx["rumor_tier"] = _rt()
        except Exception:                          # noqa: BLE001 — 读数失败不阻断
            ctx["rumor_tier"] = None
    _bl = getattr(state, "inspection_backlash_readout", None)
    if callable(_bl):
        try:
            ctx["backlash"] = _bl()
        except Exception:                          # noqa: BLE001
            ctx["backlash"] = None
    return {"observables": obs,
            "events": _i(fb.get("events")),
            "by_route": {r: v for r, v in (fb.get("by_route") or {}).items()
                         if isinstance(v, dict)},
            "recent": [dict(e) for e in (fb.get("recent") or []) if isinstance(e, dict)],
            "context": ctx,
            "interpretation": "record-only",
            "note": ("累计**反馈观察量**（非即时身份压力）：只记录监察行为造成的环境反馈，"
                     "不判断查出与否、不产生证据/案卷、不写财政/POP/吏治状态。")}


