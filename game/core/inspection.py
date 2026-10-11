# -*- coding: utf-8 -*-
"""M36-1 巡按**编制与在途容器**（**监察世界接口层**：只给事实/约束/合法性/迁移/存档/守恒）。

架构定位（用户裁定 2026-10-11）：
```
游戏系统提供事实 → AI 读取信息与约束 → AI 提出政治行动选择 → 系统校验合法性 → 执行并产生反馈
```
**系统负责**：`inspection_capacity()`（编制/在途/上限）、`inspection_candidates()`（既有官员池事实）、
任务合法性检查、状态迁移（时间推进）、存档、守恒校验；
**AI 负责**：是否派/派谁/查哪里/查什么/明查还是密查/是否暂缓（**不提前枚举为固定规则**）。

**本模块禁止**（M36-1 边界）：
- 自动派遣算法、固定触发条件、自动监察策略（**无任何自动派遣/自动触发**）；
- 修改 POP／occupation／`settlement_common`／`money`／`finance`／`tax`／`grain`；
- **自动**成案/处罚/定罪/抄没/降官（到期只做**状态迁移**，**不调用** `audit_case.resolve_audit`）。

流程仍为：观察 → 监察任务 → 证据 → 审理 → 执行（M36-1 只覆盖前两步的**容器与迁移**）。
"""
from typing import Any, Dict, List, Optional

__all__ = ["ensure_inspection_schema", "window_for", "inspection_capacity",
           "inspection_candidates", "enqueue_inspection", "inspection_tick",
           "inspection_task_list", "inspection_readout"]


def _i(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _period(state) -> str:
    """结算期标识 `年-月`（tick 幂等键；跨年不碰撞）。"""
    return f"{_i(getattr(state, 'year', 0))}-{_i(getattr(state, 'month', 0))}"


def ensure_inspection_schema(state) -> None:
    """幂等补齐容器（旧档迁移 / 新局）：`inspection_tasks`／`inspection_agent_state`。"""
    if not isinstance(getattr(state, "inspection_tasks", None), list):
        state.inspection_tasks = []
    st = getattr(state, "inspection_agent_state", None)
    if not isinstance(st, dict):
        st = {}
    st.setdefault("started", 0)
    st.setdefault("done", 0)
    st.setdefault("expired", 0)
    state.inspection_agent_state = st


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
    """**只读**编制容量（D2）：在途/上限/富余 ＋ 逐路占用。**不读任何财政量**。"""
    from content.data import INSPECTION_MAX_ACTIVE_DEFAULT, INSPECTION_MAX_ACTIVE_TASKS
    ensure_inspection_schema(state)
    active = [t for t in state.inspection_tasks if isinstance(t, dict)
              and str(t.get("status") or "active") == "active"]
    by_route: Dict[str, int] = {}
    for t in active:
        rk = str(t.get("route") or "")
        by_route[rk] = by_route.get(rk, 0) + 1
    _tier = str(tier or "正常")
    cap = int((INSPECTION_MAX_ACTIVE_TASKS or {}).get(_tier,
                                                      INSPECTION_MAX_ACTIVE_DEFAULT))
    return {"tier": _tier, "max_active_tasks": cap, "active": len(active),
            "free": max(0, cap - len(active)), "by_route": by_route,
            "tiers": dict(INSPECTION_MAX_ACTIVE_TASKS or {})}


def enqueue_inspection(state, route: str, kind: str, secret: bool = False,
                       log: Optional[list] = None) -> Dict[str, Any]:
    """**入列**一个巡按任务（**系统校验合法性 → 执行**；**绝不自动调用**）。

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
            "started_turn": turn, "started_period": _period(state),
            "settled_turn": None, "status": "active"}
    state.inspection_tasks.append(task)
    state.inspection_agent_state["started"] = \
        _i(state.inspection_agent_state.get("started")) + 1
    if log is not None:
        log.append(f"[巡按] 派员赴 {route} {kind}"
                   f"{'（密查）' if secret else ''}，限 {win} 月")
    return {"ok": True, "task": task}


def inspection_tick(state, log: Optional[list] = None) -> Dict[str, int]:
    """**月度状态迁移**（幂等）：在途任务 `remaining −1`；到期 → `expired`。

    **不**调用 `resolve_audit`（**不成案**）、**不**写 money／finance／POP／欠给／粮；
    同结算期重复调用**不重复扣减**（以 `last_tick_period`＝"年-月" 标记，`remaining` 单调递减）。
    到期语义＝**超期未回**（不是"查出问题"）——证据/审理留待后续阶段与 AI 决策。
    """
    ensure_inspection_schema(state)
    now = _period(state)
    advanced = 0
    expired = 0
    for t in state.inspection_tasks:
        if not isinstance(t, dict) or str(t.get("status")) != "active":
            continue
        if t.get("settled_turn") is not None:
            continue
        if str(t.get("last_tick_period") or "") == now:
            continue                              # **幂等**：同结算期不重复扣减
        t["last_tick_period"] = now
        t["remaining"] = max(0, _i(t.get("remaining")) - 1)
        advanced += 1
        if _i(t.get("remaining")) <= 0:
            t["status"] = "expired"
            t["settled_turn"] = _i(getattr(state, "turn", 0))
            t["settled_period"] = now
            expired += 1
            state.inspection_agent_state["expired"] = \
                _i(state.inspection_agent_state.get("expired")) + 1
    if log is not None and (advanced or expired):
        log.append(f"[巡按] 在途推进 {advanced} 项，超期 {expired} 项")
    return {"advanced": advanced, "expired": expired}


def inspection_task_list(state) -> List[Dict[str, Any]]:
    """**只读**任务列表（浅拷贝，供 AI/面板；调用不改状态）。"""
    ensure_inspection_schema(state)
    return [dict(t) for t in state.inspection_tasks if isinstance(t, dict)]


def inspection_readout(state) -> Dict[str, Any]:
    """**只读**汇总（**AI 决策入口**）：编制容量 ＋ 候选（逐路事实）＋ 在途列表。

    仅提供**事实与约束**；不提供"该不该派/派谁/查哪里"的建议（AI 自行判断）。
    """
    cap = inspection_capacity(state)
    cands = inspection_candidates(state)
    total = sum(_i(v.get("candidates")) for v in cands.values())
    return {"capacity": cap,
            "candidates_total": total,
            "candidates_by_route": cands,
            "tasks": inspection_task_list(state)}


