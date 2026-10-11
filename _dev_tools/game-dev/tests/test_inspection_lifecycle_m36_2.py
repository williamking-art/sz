# -*- coding: utf-8 -*-
"""M36-2《任务生命周期与回奏容器》契约回归（**监察世界接口层**；**零财政耦合**）。

生命周期（用户裁定 2026-10-11）：`created → active → completed ／ expired`
- **允许**：AI 提交任务、系统校验合法性、月度推进（含出发）、到期状态变化、**回奏容器**；
- **不做**：自动判断调查结果、自动产生证据、自动成案、自动处罚（`resolve_audit` 一律不调用）。

验收重点：① 生命周期正确且幂等；② 回奏只做**容器＋引用校验**（引擎绝不建案）；
         ③ 存档兼容（含 M36-1 旧任务规范化）；④ 财政/POP 零耦合；⑤ 无自动成案/自动完成。
"""
import copy
import json
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import (INSPECTION_MAX_ACTIVE_TASKS,  # noqa: E402
                          INSPECTION_MAX_ACTIVE_TIER_DEFAULT)
from core import money  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.inspection import (ensure_inspection_schema, enqueue_inspection,  # noqa: E402
                             file_inspection_report, inspection_capacity,
                             inspection_readout, inspection_task_list, inspection_tick)
from core.settlement import run_monthly_settlement  # noqa: E402


def _seed(s, route, n=4):
    """夹具：在岗 → 待阙（保持 `officials` 总量，POP 不变量成立）。"""
    pool = s.prefectures[route]["pops"]["官僚"]
    move = min(int(n), int(pool.get("on_post", 0) or 0))
    pool["on_post"] = int(pool.get("on_post", 0) or 0) - move
    pool["waiting"] = int(pool.get("waiting", 0) or 0) + move


def _route_with_pool(s, n=4):
    from core.domains.administration import officialdom as _od
    route = next(iter(s.prefectures))
    _seed(s, route, n)
    ok, bad = _od.check_invariants(s)
    assert ok, f"夹具不得破坏官员不变量：{bad}"
    return route


def _dispatch(s, task_id=0):
    """推进一期：`created → active`（出发）。"""
    s.month = 1 + (s.month % 12)
    inspection_tick(s)
    return s.inspection_tasks[task_id]


def _snapshot(s):
    return {"money": money.m_all(s),
            "prefs": copy.deepcopy(s.prefectures),
            "stats": copy.deepcopy(dict(s.statistics or {})),
            "cases": copy.deepcopy(getattr(s, "audit_cases", {}) or {}),
            "pop": getattr(s, "population", None)}


# ---------------------------------------------------------------- 生命周期

def test_lifecycle_created_active_completed():
    """全生命周期：受理（created）→ 出发（active）→ 回奏（completed）；计数正确。"""
    s = new_game()
    rk = _route_with_pool(s)
    r = enqueue_inspection(s, rk, "查粮")
    assert r["ok"] and r["task"]["status"] == "created"
    assert inspection_readout(s)["status_counts"] == {
        "created": 1, "active": 0, "completed": 0, "expired": 0}
    t = _dispatch(s)
    assert t["status"] == "active" and t["dispatched_period"]
    assert t["remaining"] == t["window_months"] == 2, "出发当月不扣窗口"
    assert inspection_capacity(s)["created"] == 0 and inspection_capacity(s)["active"] == 1
    rr = file_inspection_report(s, t["id"], summary="河南仓廪账实不符")
    assert rr["ok"] and rr["report"]["late"] is False
    assert t["status"] == "completed" and t["report"]["summary"]
    assert s.inspection_agent_state == {"started": 1, "done": 1, "expired": 0}
    assert inspection_readout(s)["status_counts"]["completed"] == 1


def test_window_accounting_and_expiry_after_dispatch():
    """窗口自**出发次月**起扣；归零 → `expired`（超期未回）；`remaining` 单调递减。"""
    s = new_game()
    rk = _route_with_pool(s)
    tid = enqueue_inspection(s, rk, "查粮")["task"]["id"]      # 窗口 2 月
    s.year, s.month = 990, 3
    assert inspection_tick(s) == {"dispatched": 1, "advanced": 0, "expired": 0}
    assert s.inspection_tasks[0]["dispatched_period"] == "990-3"
    seq = []
    for m in (4, 5, 6):
        s.month = m
        inspection_tick(s)
        seq.append(s.inspection_tasks[0]["remaining"])
    assert seq == [1, 0, 0], f"窗口自出发次月起扣：{seq}"
    t = s.inspection_tasks[0]
    assert t["status"] == "expired" and t["settled_period"] == "990-5"
    assert s.inspection_agent_state["expired"] == 1
    assert s.inspection_agent_state["done"] == 0, "超期**不等于**回奏"


def test_tick_idempotent_and_no_auto_complete():
    """同期重复 tick 幂等；**无自动化**：任务不会自行 `completed`。"""
    s = new_game()
    rk = _route_with_pool(s)
    enqueue_inspection(s, rk, "查赋")
    s.year, s.month = 990, 3
    assert inspection_tick(s) == {"dispatched": 1, "advanced": 0, "expired": 0}
    assert inspection_tick(s) == {"dispatched": 0, "advanced": 0, "expired": 0}
    assert s.inspection_tasks[0]["remaining"] == 3, "同期幂等：出发期不重复处理"
    for _ in range(8):
        s.month = 1 + (s.month % 12)
        inspection_tick(s)
    assert {t["status"] for t in s.inspection_tasks} == {"expired"}, "只会 expired，不会自动 completed"
    assert s.inspection_agent_state["done"] == 0


# ---------------------------------------------------------------- 回奏容器（只做容器＋引用校验）

def test_report_legality_and_reference_check():
    """回奏合法性：任务存在／已出发／不重复；`case_id` 必须**已存在**（引擎不建案）。"""
    s = new_game()
    rk = _route_with_pool(s)
    tid = enqueue_inspection(s, rk, "查粮")["task"]["id"]
    assert file_inspection_report(s, "no-such-task")["ok"] is False
    assert file_inspection_report(s, tid)["ok"] is False, "尚未出发不可回奏"
    _dispatch(s)
    # 悬空案卷引用：拒绝（**不**因此建案）
    r = file_inspection_report(s, tid, summary="x", case_id="case-不存在")
    assert r["ok"] is False and "案卷" in r["reason"]
    assert (getattr(s, "audit_cases", None) or {}) == {}, "引擎绝不建案"
    # 已存在案卷：允许引用（引用校验通过）
    s.audit_cases["case-ok"] = {"id": "case-ok", "status": "open"}
    before_case = copy.deepcopy(s.audit_cases["case-ok"])
    r = file_inspection_report(s, tid, summary="实情", case_id="case-ok")
    assert r["ok"] and r["report"]["case_id"] == "case-ok"
    assert s.audit_cases["case-ok"] == before_case, "回奏只引用，不得改动案卷"
    # 不重复回奏
    assert file_inspection_report(s, tid)["ok"] is False
    assert s.inspection_agent_state["done"] == 1


def test_report_late_flag_and_summary_bound():
    """超期后回奏：**允许但标注 `late=True`**（不改写历史）；`summary` 截断上限。"""
    s = new_game()
    rk = _route_with_pool(s)
    tid = enqueue_inspection(s, rk, "查粮")["task"]["id"]
    s.year, s.month = 990, 3
    for m in (3, 4, 5, 6):
        s.month = m
        inspection_tick(s)
    assert s.inspection_tasks[0]["status"] == "expired"
    r = file_inspection_report(s, tid, summary="长" * 900)
    assert r["ok"] and r["report"]["late"] is True
    assert len(r["report"]["summary"]) == 500, "回奏正文须截断（容器不得无界膨胀）"
    assert s.inspection_tasks[0]["status"] == "completed"
    assert s.inspection_agent_state == {"started": 1, "done": 1, "expired": 1}


# ---------------------------------------------------------------- 无自动化 / 零财政耦合

def test_no_auto_case_no_auto_evidence_no_auto_penalty():
    """**零扰动对照**：同种子 12 期结算，有巡检任务局 vs 无任务局 ⇒ 经济结果**逐位一致**。

    同时断言：**不**成案、**不**产生证据、任务**不会**自行 `completed`、`done` 恒为 0。
    """
    a = new_game()
    b = new_game()
    rk_a, rk_b = _route_with_pool(a), _route_with_pool(b)
    assert rk_a == rk_b
    assert enqueue_inspection(a, rk_a, "查赋")["ok"], "A 局有在途巡按任务"
    for _ in range(6):                             # 6 期已覆盖「受理→出发→超期」全程
        a.month = b.month = 1 + (a.month % 12)
        run_monthly_settlement(a, seed_offset=0)
        run_monthly_settlement(b, seed_offset=0)
    assert money.m_all(a) == money.m_all(b), "监察在场不得改变任何财政结果"
    assert a.prefectures == b.prefectures, "监察不得改变逐路/POP 状态"
    assert dict(a.statistics or {}) == dict(b.statistics or {}), "监察不得写统计"
    assert (getattr(a, "audit_cases", None) or {}) == {}, "不得自动成案"
    assert {t["status"] for t in a.inspection_tasks} <= {"created", "active", "expired"}
    assert a.inspection_agent_state["done"] == 0, "无回奏则 done 恒为 0"


def test_zero_coupling_across_full_lifecycle():
    """全生命周期（受理→出发→回奏）对 money/POP/statistics/案卷**零写入**。"""
    s = new_game()
    rk = _route_with_pool(s)
    before = _snapshot(s)
    tid = enqueue_inspection(s, rk, "查赋", secret=True)["task"]["id"]
    _dispatch(s)
    s.month = 1 + (s.month % 12)
    inspection_tick(s)
    assert file_inspection_report(s, tid, summary="回报")["ok"]
    assert money.m_all(s) == before["money"]
    assert s.prefectures == before["prefs"]
    assert dict(s.statistics or {}) == before["stats"]
    assert (getattr(s, "audit_cases", None) or {}) == before["cases"]
    assert getattr(s, "population", None) == before["pop"]
    after = _snapshot(s)
    inspection_readout(s)
    inspection_capacity(s)
    inspection_task_list(s)
    assert _snapshot(s) == after, "只读接口不得有副作用"


# ---------------------------------------------------------------- 容量 / 存档兼容 / 源码边界

def test_capacity_occupancy_by_status():
    """名额占用：`created`＋`active` 占用；`completed`／`expired` **释放**名额。"""
    s = new_game()
    rk = _route_with_pool(s)
    cap = inspection_capacity(s)["max_active_tasks"]
    tid1 = enqueue_inspection(s, rk, "查粮")["task"]["id"]
    assert inspection_capacity(s)["occupied"] == 1, "受理即占名额"
    _dispatch(s)
    assert inspection_capacity(s)["active"] == 1 and inspection_capacity(s)["created"] == 0
    file_inspection_report(s, tid1)
    assert inspection_capacity(s)["occupied"] == 0, "回奏后释放名额"
    enqueue_inspection(s, rk, "查粮")
    for _ in range(cap + 2):
        s.month = 1 + (s.month % 12)
        inspection_tick(s)                          # 出发 1 期 ＋ 窗口自次月起扣
    assert s.inspection_tasks[1]["status"] == "expired"
    assert inspection_capacity(s)["occupied"] == 0, "超期后释放名额"


def test_capacity_tier_is_explicit_only():
    """档位**只由调用方显式传入**：民怨/吏怨等状态**不得**自动改变上限。"""
    s = new_game()
    assert inspection_capacity(s)["tier"] == INSPECTION_MAX_ACTIVE_TIER_DEFAULT
    assert inspection_capacity(s, tier="strong")["max_active_tasks"] == \
        INSPECTION_MAX_ACTIVE_TASKS["强监察"]
    s.unrest = 90
    for p in s.prefectures.values():
        p["unrest"] = 95
        p.setdefault("clerks_detail", {})["grievance"] = 50
    assert inspection_capacity(s)["max_active_tasks"] == \
        INSPECTION_MAX_ACTIVE_TASKS[INSPECTION_MAX_ACTIVE_TIER_DEFAULT], \
        "民怨高不得自动升档（档位属 AI 决策）"


def test_save_load_and_legacy_task_normalization():
    """存档：含回奏的任务往返；**M36-1 旧任务**被规范化、未知状态归一为 active。"""
    from core.save_load import _slot_path, load_game, save_game
    s = new_game()
    rk = _route_with_pool(s)
    tid = enqueue_inspection(s, rk, "查粮")["task"]["id"]
    _dispatch(s)
    file_inspection_report(s, tid, summary="存档回报")
    # M36-1 形态旧任务（无 report/created_period，status=active）
    s.inspection_tasks.append({"id": "legacy-x", "route": rk, "kind": "查赋",
                               "secret": False, "window_months": 3, "remaining": 2,
                               "started_turn": 0, "started_period": "990-1",
                               "settled_turn": None, "status": "active"})
    # 未知状态（当归一为 active，**不**猜成 completed）
    s.inspection_tasks.append({"id": "weird-y", "route": rk, "kind": "查粮",
                               "status": "banana", "remaining": 2, "window_months": 2})
    ensure_inspection_schema(s)
    assert s.inspection_tasks[1]["report"] is None
    assert s.inspection_tasks[1]["created_period"] == "990-1"
    assert s.inspection_tasks[2]["status"] == "active", "未知状态归一为 active"
    assert save_game(s, slot=73)
    s2 = load_game(73)
    assert s2.inspection_tasks[0]["report"]["summary"] == "存档回报"
    assert s2.inspection_tasks[0]["status"] == "completed"
    assert len(s2.inspection_tasks) == 3
    if os.path.exists(_slot_path(73)):
        os.remove(_slot_path(73))


def test_source_boundary_lifecycle():
    """源码边界：不调用 `resolve_audit(`；**不写入** `audit_cases`；结算**只**接线 tick。"""
    with open(os.path.join(_GAME_ROOT, "core", "inspection.py"), "r", encoding="utf-8") as f:
        src = f.read()
    assert "resolve_audit(" not in src
    for forbidden in ("settlement_common", "settlement_finance", "pop_bridge",
                      "pop_structure", "money", "audit_case"):
        assert f"from core.{forbidden}" not in src and f"import {forbidden}" not in src
    assert "audit_cases[" not in src and "audit_cases.pop" not in src, \
        "监察模块不得写入案卷（只做只读引用校验）"
    with open(os.path.join(_GAME_ROOT, "core", "settlement.py"), "r", encoding="utf-8") as f:
        settle = f.read()
    assert "inspection_tick" in settle
    for auto in ("enqueue_inspection", "file_inspection_report"):
        assert auto not in settle, f"结算不得自动调用 {auto}"



