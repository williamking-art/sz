# -*- coding: utf-8 -*-
"""M36.5《AI 决策接线》契约回归（**大臣判断／皇帝裁决／引擎执行**三层分离）。

裁定（2026-10-11）：
- **G1**：① 诏令载荷＝正式执行通道（`inspect_dispatch`／`inspect_report`／`inspect_allege`）；
  ② `ai_pending_actions`＝呈请—批红通道（呈请 ≠ 批准 ≠ 执行）；③ 行动计划 `op` 不独立执行。
  `resolve_audit` 仍只经 `audit_route`（唯一成案入口）。
- **G2**：UI 推荐（`briefing.build_briefing_actions`）与 **AI 中立事实视图**（`ai_decision_view`）分离；
  事实视图**不含**推荐/排序/`urgent`，并须**按 viewer 落实权限**（D11：AI 大臣 ≠ 全知）。

验收：① 读视图不改状态；② `settlement.py` 不自动调用 M36 行动/成案；③ 三层校验完整；
       ④ UI 行为兼容；⑤ 回归＋校准门；⑥ 单点不变（唯一桥接／唯一成案／`financial_evidence` 唯一调用点）。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FIN_ANOMALY_OVERSIGHT_LINE  # noqa: E402
from core import money  # noqa: E402
from core.briefing import build_briefing_actions  # noqa: E402
from core.commands import approve_ai_action, new_game  # noqa: E402
from core.inspection import (ai_decision_view, enqueue_inspection,  # noqa: E402
                             file_inspection_report, inspection_readout, inspection_tick)
from core.settlement import run_monthly_settlement  # noqa: E402
from core.settlement_decree import _apply_decree_effect  # noqa: E402


def _seed(s, route, n=4):
    pool = s.prefectures[route]["pops"]["官僚"]
    move = min(int(n), int(pool.get("on_post", 0) or 0))
    pool["on_post"] = int(pool.get("on_post", 0) or 0) - move
    pool["waiting"] = int(pool.get("waiting", 0) or 0) + move
    return route


def _dispatch_one(s, kind="查赋", secret=False):
    """授差遣→出发；返回 task_id。"""
    r = enqueue_inspection(s, _seed(s, next(iter(s.prefectures))), kind, secret=secret)
    assert r["ok"], r.get("reason")
    s.year, s.month = 990, 3
    inspection_tick(s)
    return r["task"]["id"]


def _decree(s, effects):
    """走**真实**诏令执行点（世界执行层）。"""
    log = []
    _apply_decree_effect(s, {"effects": effects}, log)
    return log


# ------------------------------------------------- ① 事实视图：只读、中立、含不可用原因

def test_decision_view_is_readonly_and_neutral():
    """读视图不改状态；**不含**推荐/排序/urgent；必须给出**不可用的具体原因**。"""
    s = new_game()
    before = (copy.deepcopy(s.prefectures), money.m_all(s),
              copy.deepcopy(dict(s.statistics or {})), copy.deepcopy(s.inspection_tasks))
    v = ai_decision_view(s, viewer="player")
    assert v["note"].startswith("中立事实视图")
    # 只扫**数据体**（`note` 是说明文案，本身会写"不含推荐"）
    _data = {k: vv for k, vv in v.items() if k != "note"}
    joined = str(_data)
    for banned in ("urgent", "推荐", "最优", "宜"):
        assert banned not in joined, f"事实视图数据不得含推荐语（{banned}）"
    for a in v["available_actions"]:
        assert set(a) == {"action", "params", "available", "reasons", "via"}, "行动项不含优先级/推荐字段"
    after = (s.prefectures, money.m_all(s), dict(s.statistics or {}), s.inspection_tasks)
    assert before[0] == after[0] and before[1] == after[1] and before[2] == after[2]
    assert before[3] == after[3], "读视图不得改任务容器"
    # 新局：候选池为 0 ⇒ 授差遣不可用，且给出原因（不是推荐替代方案）
    acts = {a["action"]: a for a in v["available_actions"]}
    assert acts["inspect_dispatch"]["available"] is False
    assert any("候选池" in r for r in acts["inspect_dispatch"]["reasons"])
    assert acts["inspect_report"]["available"] is False
    assert acts["inspect_allege"]["available"] is False
    assert acts["audit_route"]["available"] is True


def test_decision_view_availability_follows_state():
    """可得性随世界状态变化：有名额且有官 ⇒ 可授差遣；有在途 ⇒ 可奏报；已奏报未桥接 ⇒ 可提涉嫌。"""
    s = new_game()
    tid = _dispatch_one(s)
    v = ai_decision_view(s, viewer="player")
    acts = {a["action"]: a for a in v["available_actions"]}
    assert acts["inspect_dispatch"]["available"] is True
    assert acts["inspect_report"]["available"] is True, "有在途差遣 ⇒ 可奏报"
    assert tid in [t["id"] for t in v["tasks"]]
    assert v["suspicion_pending"] == [], "未奏报 ⇒ 不在待桥接清单"
    assert file_inspection_report(s, tid, summary="回报")["ok"]
    v2 = ai_decision_view(s, viewer="player")
    acts2 = {a["action"]: a for a in v2["available_actions"]}
    assert acts2["inspect_report"]["available"] is False
    assert acts2["inspect_allege"]["available"] is True
    assert tid in v2["suspicion_pending"], "已奏报未桥接 ⇒ 明确列为事实"
    assert set(v2["capacity"]) >= {"free", "occupied", "created", "active", "max_active_tasks"}


def test_decision_view_permission_by_viewer():
    """权限在入口落实：AI 大臣身份**不**升权（D11）。"""
    s = new_game()
    rk = next(iter(s.prefectures))
    s.prefectures[rk]["local_treasury"] = 0
    from core.settlement_finance import _settle_local_expenditure, _settle_finance
    _settle_local_expenditure(s, [])
    _settle_finance(s, [])
    for viewer in ("player", "official", "court"):
        assert ai_decision_view(s, viewer=viewer)["fiscal_context"]["allow_real"] is False
    assert ai_decision_view(s, viewer="inspector", oversight=0.0)["fiscal_context"]["allow_real"] is False, \
        "察访执行者未达门限且非密查 ⇒ 不见真账"
    assert ai_decision_view(s, viewer="inspector", secret=True)["fiscal_context"]["allow_real"] is True
    assert ai_decision_view(s, viewer="inspector",
                            oversight=FIN_ANOMALY_OVERSIGHT_LINE + 0.1)["fiscal_context"]["allow_real"]
    assert ai_decision_view(s, viewer="ai")["fiscal_context"]["allow_real"] is True


# ------------------------------------------------- ② 诏令载荷（正式执行通道）

def test_decree_payload_dispatch_report_allege():
    """三载荷走**真实诏令执行点**：授差遣 → 奏报 → 涉嫌入怀疑层；全程不产案卷。"""
    s = new_game()
    rk = _seed(s, next(iter(s.prefectures)))
    log = _decree(s, {"inspect_dispatch": {"route": rk, "kind": "查赋", "secret": True}})
    assert any("授差遣" in x for x in log), log
    tid = s.inspection_tasks[0]["id"]
    assert s.inspection_tasks[0]["secret"] is True
    assert (s.audit_cases or {}) == {}, "授差遣不产案卷"
    # 尚未出发 ⇒ 奏报未成
    log = _decree(s, {"inspect_report": {"task_id": tid, "summary": "x"}})
    assert any("未成" in x for x in log), log
    s.year, s.month = 990, 3
    inspection_tick(s)
    log = _decree(s, {"inspect_report": {"task_id": tid, "summary": "仓廪账实不符"}})
    assert any("奏报已录" in x for x in log), log
    log = _decree(s, {"inspect_allege": {"task_id": tid, "text": "账目有亏空、侵渔"}})
    assert any("入怀疑层" in x for x in log), log
    assert len(s.discovery_suspicions) == 1 and s.discovery_suspicions[0]["source"] == "察访"
    assert (s.audit_cases or {}) == {}, "涉嫌事项不入案卷"


def test_decree_payload_rejects_illegal_structure_and_semantics():
    """三层校验：结构非法／路名不存在／未开放种类／超名额 ⇒ 不执行且记日志，不打断结算。"""
    s = new_game()
    log = _decree(s, {"inspect_dispatch": 12345})
    assert any("载荷非法" in x for x in log)
    log = _decree(s, {"inspect_dispatch": {"route": "不存在的路", "kind": "查赋"}})
    assert any("路名不存在" in x for x in log)
    log = _decree(s, {"inspect_dispatch": {"route": next(iter(s.prefectures)), "kind": "查军务"}})
    assert any("未开放" in x for x in log)
    log = _decree(s, {"inspect_allege": {"task_id": "no-such", "text": "账目有亏空"}})
    assert any("未入怀疑层" in x for x in log)
    assert s.inspection_tasks == [] or all(t["status"] == "created" for t in s.inspection_tasks)
    assert len(s.inspection_tasks) == 0, "非法载荷不得留下任务"


def test_decree_payload_capacity_guard():
    """名额上限：达上限后继续授差遣 ⇒ 执行点拒绝（系统只校验合法性）。"""
    s = new_game()
    rk = _seed(s, next(iter(s.prefectures)), 14)
    cap = inspection_readout(s)["capacity"]["max_active_tasks"]
    for _ in range(cap):
        _decree(s, {"inspect_dispatch": {"route": rk, "kind": "查粮"}})
    assert len(s.inspection_tasks) == cap
    log = _decree(s, {"inspect_dispatch": {"route": rk, "kind": "查粮"}})
    assert any("未成" in x for x in log) and len(s.inspection_tasks) == cap


# ------------------------------------------------- ③ 呈请—批红（呈请 ≠ 批准 ≠ 执行）

def test_request_approval_flow():
    """呈请（pending）不改世界；**批红**才落到单点；驳回落空。"""
    s = new_game()
    rk = _seed(s, next(iter(s.prefectures)))
    aid = s.enqueue_ai_action("inspect_dispatch", "请遣官察访", "请授差遣察访某路",
                              {"route": rk, "kind": "查赋"}, proposer="某大臣")
    assert s.inspection_tasks == [], "呈请本身不得执行"
    v = ai_decision_view(s, viewer="player")
    assert [p["id"] for p in v["pending_requests"]] == [aid], "待批呈请是事实（可读）"
    msg = approve_ai_action(s, aid)
    assert "批红" in msg and len(s.inspection_tasks) == 1, "批红后落到既有单点"
    assert s.get_ai_pending("*")[0]["status"] == "approved"
    # 驳回：不执行
    aid2 = s.enqueue_ai_action("inspect_dispatch", "请遣官察访2", "x",
                               {"route": rk, "kind": "查粮"}, proposer="某大臣")
    from core.commands import reject_ai_action
    reject_ai_action(s, aid2)
    assert len(s.inspection_tasks) == 1, "驳回不得执行"
    assert s.get_ai_pending("*")[1]["status"] == "rejected"


def test_approve_illegal_request_rejected():
    """批红非法呈请 ⇒ 落到单点后被拒 ⇒ 状态 rejected（不静默成功）。"""
    s = new_game()
    aid = s.enqueue_ai_action("inspect_report", "请录奏报", "x",
                              {"task_id": "no-such", "summary": "y"}, proposer="某大臣")
    msg = approve_ai_action(s, aid)
    assert "未成" in msg
    item = [a for a in s.get_ai_pending("*") if a["id"] == aid][0]
    assert item["status"] == "rejected"


# ------------------------------------------------- ④ UI 兼容 ＋ 守卫

def test_ui_briefing_unchanged():
    """UI 推荐接口行为兼容（键与兜底不变）——与 AI 事实视图**分离**。"""
    s = new_game()
    acts = build_briefing_actions(s)
    assert acts and all(set(a) == {"key", "title", "desc", "goto", "urgent"} for a in acts)
    assert any(a["key"] == "decree" for a in acts), "兜底项仍在"


def test_guards_no_auto_and_single_points():
    """守卫：`settlement.py` 不自动调用；`audit_route` 仍是唯一成案载荷；单点不变。"""
    settle = open(os.path.join(_GAME_ROOT, "core", "settlement.py"), encoding="utf-8").read()
    for banned in ("enqueue_inspection", "file_inspection_report", "record_report_suspicion",
                   "apply_inspect_decree_payload", "resolve_audit"):
        assert banned not in settle, f"结算链不得出现 {banned}"
    dec = open(os.path.join(_GAME_ROOT, "core", "settlement_decree.py"), encoding="utf-8").read()
    assert dec.count("resolve_audit(") == 1, "resolve_audit 仍只由 audit_route 分支调用"
    insp = open(os.path.join(_GAME_ROOT, "core", "inspection.py"), encoding="utf-8").read()
    import re
    _insp_code = re.sub(r'"""(?:.|\n)*?"""', "", insp)
    _insp_code = "\n".join(ln.split("#")[0] for ln in _insp_code.splitlines())
    assert "resolve_audit(state" not in _insp_code, "监察层**代码**不得调用成案入口（文档/文案提及不算）"
    assert "import resolve_audit" not in _insp_code
    ac = open(os.path.join(_GAME_ROOT, "core", "audit_case.py"), encoding="utf-8").read()
    _code = "\n".join(ln.split("#")[0] for ln in ac.splitlines())
    _ev_calls = [ln.strip() for ln in _code.splitlines()
                 if "financial_evidence(state" in ln
                 and not ln.lstrip().startswith("def ")]
    assert len(_ev_calls) == 1, f"证据读数调用点仍唯一（现 {len(_ev_calls)} 处）"


def test_fiscal_isolation_with_wiring():
    """财政隔离契约（长期保留）：走完 授差遣→奏报→涉嫌 后的对照局逐位一致。"""
    a, b = new_game(), new_game()
    rk = _seed(a, next(iter(a.prefectures)))
    _seed(b, next(iter(b.prefectures)))
    _decree(a, {"inspect_dispatch": {"route": rk, "kind": "查赋"}})
    tid = a.inspection_tasks[0]["id"]
    # 2026-10-17 全审：对照组必须同历法；只改 a.year 会让统计里的
    # active_rebellions['year'] 天然不同，误报财政隔离失败。
    a.year, a.month = 990, 3
    b.year, b.month = 990, 3
    inspection_tick(a)
    _decree(a, {"inspect_report": {"task_id": tid, "summary": "回报"}})
    _decree(a, {"inspect_allege": {"task_id": tid, "text": "账目有亏空"}})
    for _ in range(6):
        a.month = b.month = 1 + (a.month % 12)
        run_monthly_settlement(a, seed_offset=0)
        run_monthly_settlement(b, seed_offset=0)
    assert money.m_all(a) == money.m_all(b)
    assert a.prefectures == b.prefectures
    assert dict(a.statistics or {}) == dict(b.statistics or {})
    assert (a.audit_cases or {}) == (b.audit_cases or {})
    assert len(a.discovery_suspicions) == 1, "差异只在怀疑层（信息）"


