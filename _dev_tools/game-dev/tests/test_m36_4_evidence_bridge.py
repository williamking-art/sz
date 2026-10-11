# -*- coding: utf-8 -*-
"""M36-4《证据形成衔接》契约回归（**接入发现链，不是扩大监察能力**）。

裁决（2026-10-11）：D9＝**B＋B-2**（察访可提涉嫌事项 → 进发现链二级「怀疑」，**不成案**）；
D10＝**甲**（决策方判断 → `resolve_audit()` → `financial_evidence()`，**察访完成不自动查账**，
`audit_fidelity` 四输入冻结：`corruption × grip × spy_network × secret`）；
D11＝**维持现状**（player/official 账面；court 汇总/账面；inspector 需密查或 `oversight≥门限` 得真账；
ai/system 全知；**察访身份 ≠ 自动全知**）。

最终链路：察访提供发现 → 决策方决定是否推进 → 审计系统负责证据 → 审理系统负责判断。
原六项契约（本文件逐条对应）：
  ① 奏报不产怀疑　② 奏报不产案卷　③ 只有决策方显式行动才成案
  ④ 权限矩阵逐格　⑤ 口径单点守卫　⑥ 财政隔离对照（长期保留）
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
from core.audit_case import (record_report_suspicion, resolve_audit)  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.inspection import (enqueue_inspection, file_inspection_report,  # noqa: E402
                             inspection_readout, inspection_tick)
from core.settlement import run_monthly_settlement  # noqa: E402


def _seed(s, route, n=4):
    pool = s.prefectures[route]["pops"]["官僚"]
    move = min(int(n), int(pool.get("on_post", 0) or 0))
    pool["on_post"] = int(pool.get("on_post", 0) or 0) - move
    pool["waiting"] = int(pool.get("waiting", 0) or 0) + move
    return route


def _run_to_filed(s, kind="查赋", secret=False, text="仓廪账实不符", file=True):
    """受理→出发→（可选）奏报；返回 (task_id, route)。`file=False` 留给调用方自行奏报。"""
    route = next(iter(s.prefectures))
    _seed(s, route)
    r = enqueue_inspection(s, route, kind, secret=secret)
    assert r["ok"], r.get("reason")
    tid = r["task"]["id"]
    s.year, s.month = 990, 3
    inspection_tick(s)                                  # 出发
    if file:
        assert file_inspection_report(s, tid, summary="回报")["ok"]
    return tid, route


def _n_susp(s):
    return len(getattr(s, "discovery_suspicions", None) or [])


# ------------------------------------------------- ① 奏报不产怀疑

def test_filing_does_not_create_suspicion():
    """① **奏报 ≠ 自动怀疑**：`file_inspection_report` 前后 `discovery_suspicions` 条数不变。"""
    s = new_game()
    tid, _ = _run_to_filed(s)
    assert _n_susp(s) == 0, "奏报本身不得写入怀疑层（怀疑只由决策方显式桥接）"
    assert tid and s.inspection_tasks[0]["status"] == "completed"


def test_bridge_requires_filed_task_and_explicit_call():
    """桥接合法性：须**已奏报**；未奏报（created/active/expired）一律拒绝；空文本拒绝。"""
    s = new_game()
    route = next(iter(s.prefectures))
    _seed(s, route)
    # created（未出发）
    t0 = enqueue_inspection(s, route, "查粮")["task"]["id"]
    assert record_report_suspicion(s, t0, "账目有亏空")["ok"] is False
    assert _n_susp(s) == 0
    # active（已出发未奏报）
    s.year, s.month = 990, 3
    inspection_tick(s)
    assert record_report_suspicion(s, t0, "账目有亏空")["ok"] is False
    # expired（超期未奏报）
    for m in (4, 5, 6):
        s.month = m
        inspection_tick(s)
    assert s.inspection_tasks[0]["status"] == "expired"
    assert record_report_suspicion(s, t0, "账目有亏空")["ok"] is False
    assert _n_susp(s) == 0
    # 未知任务 / 空文本
    assert record_report_suspicion(s, "no-such", "账目有亏空")["ok"] is False
    tid, _ = _run_to_filed(s)
    assert record_report_suspicion(s, tid, "   ")["ok"] is False
    assert _n_susp(s) == 0, "空文本不静默伪造"


def test_bridge_writes_suspicion_layer_only():
    """桥接只写**怀疑层**（发现链二级）：`source="察访"`、带路名可追溯，不产案卷。"""
    s = new_game()
    tid, route = _run_to_filed(s)
    r = record_report_suspicion(s, tid, "仓廪账实不符、火耗过额")
    assert r["ok"], r.get("reason")
    recs = s.discovery_suspicions
    assert len(recs) == 1
    rec = recs[0]
    assert rec["source"] == "察访" and rec["route"] == route
    assert "查赋" in rec["text"] and route in rec["text"], "随卷入任务种类与路名（可追溯）"
    assert rec["keyword"], "命中财政疑虑关键词"
    assert (getattr(s, "audit_cases", None) or {}) == {}, "怀疑层不产案卷"
    # 任务容器记"已桥接"（只写自己的容器）
    assert s.inspection_tasks[0]["report"]["suspicion"]["source"] == "察访"
    assert tid not in inspection_readout(s)["suspicion_pending"]
    # 重复桥接：既有去重规则生效（不重复入卷）
    assert record_report_suspicion(s, tid, "仓廪账实不符、火耗过额")["ok"] is False
    assert len(s.discovery_suspicions) == 1


def test_non_fiscal_text_is_rejected_by_existing_rule():
    """非财政疑虑文本沿用既有规则被拒（不伪造怀疑）。"""
    s = new_game()
    tid, _ = _run_to_filed(s)
    r = record_report_suspicion(s, tid, "此地风景宜人")
    assert r["ok"] is False and "record_suspicion" in r["reason"]
    assert _n_susp(s) == 0


# ------------------------------------------------- ② 奏报不产案卷 · ③ 只有显式行动才成案

def test_filing_never_creates_case_even_with_case_reference():
    """② 奏报**不产案卷**（含"带已存在案卷引用"的情形）：`audit_cases` 不增。"""
    s = new_game()
    _run_to_filed(s)                       # 任务 1：已奏报
    s.audit_cases["case-x"] = {"id": "case-x", "status": "open"}
    before = copy.deepcopy(s.audit_cases)
    # 任务 1 重复奏报（带案卷引用）⇒ 拒绝，且案卷不变
    tid1 = s.inspection_tasks[0]["id"]
    assert file_inspection_report(s, tid1, summary="回报", case_id="case-x")["ok"] is False, \
        "同一任务不可重复奏报"
    assert s.audit_cases == before
    # 任务 2：带**已存在**案卷引用奏报 ⇒ 允许引用，但不得新增/改动案卷
    tid2, _ = _run_to_filed(s, file=False)
    assert file_inspection_report(s, tid2, summary="回报2", case_id="case-x")["ok"]
    assert s.audit_cases == before, "奏报只做引用校验，不得新增或改动案卷"
    assert record_report_suspicion(s, tid2, "账目有亏空")["ok"]
    assert s.audit_cases == before, "桥接怀疑层同样不产案卷"
    # 悬空引用 ⇒ 拒绝（且不得因此建案）
    tid3, _ = _run_to_filed(s, file=False)
    assert file_inspection_report(s, tid3, summary="回报3", case_id="case-不存在")["ok"] is False
    assert s.audit_cases == before


def test_only_explicit_audit_creates_case():
    """③ **只有决策方显式行动**才成案：跑 6 期结算＋奏报＋桥接 ⇒ 案卷仍空。"""
    s = new_game()
    tid, route = _run_to_filed(s)
    assert record_report_suspicion(s, tid, "账目有亏空、侵渔")["ok"]
    for _ in range(6):
        s.month = 1 + (s.month % 12)
        run_monthly_settlement(s, seed_offset=0)
    assert (getattr(s, "audit_cases", None) or {}) == {}, "察访完成不得自动查账（D10＝甲）"
    assert _n_susp(s) == 1, "怀疑层保留（供决策方判断）"
    # 决策方显式下诏勾校 ⇒ 成案（唯一点）
    res = resolve_audit(s, route, executor=None, secret=False)
    assert res["ok"] and res["case"]["id"] in s.audit_cases
    assert len(s.audit_cases) == 1


# ------------------------------------------------- ④ 权限矩阵逐格

def test_permission_matrix_viewer_by_cell():
    """④ 权限矩阵（D11＝维持现状）：逐格断言，**察访身份 ≠ 自动全知**。"""
    s = new_game()
    rk = next(iter(s.prefectures))
    s.prefectures[rk]["local_treasury"] = 0
    from core.settlement_finance import _settle_local_expenditure, _settle_finance
    _settle_local_expenditure(s, [])
    _settle_finance(s, [])
    # 账面侧 viewer：不给真账
    for viewer in ("player", "official", "court"):
        rep = s.fiscal_gap_report(viewer)
        assert rep["allow_real"] is False, f"{viewer} 不得见真账"
        assert set(rep["totals"]) == {"loss_report_total"}
    # 察访/监察：未达门限且非密查 ⇒ 不给真账
    rep = s.fiscal_gap_report("inspector", oversight=0.0)
    assert rep["allow_real"] is False, "察访身份不等于自动全知"
    # 达门限 或 密查 ⇒ 给真账
    assert s.fiscal_gap_report("inspector", oversight=FIN_ANOMALY_OVERSIGHT_LINE + 0.1)["allow_real"]
    assert s.fiscal_gap_report("inspector", oversight=0.0, secret=True)["allow_real"]
    # 全知
    assert s.fiscal_gap_report("ai")["allow_real"] and s.fiscal_gap_report("system")["allow_real"]


# ------------------------------------------------- ⑤ 口径单点守卫

def _code_only(src):
    import re
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    return "\n".join(ln.split("#")[0] for ln in src.splitlines())


def test_single_point_guards():
    """⑤ 口径单点＋方向守卫：
    - `core/inspection.py` **不 import** `audit_case`（监察不读司法；发现/取证不回流）；
    - 证据读数 `financial_evidence` 仍**只**被 `resolve_audit` 调用（不新增第二生产者）；
    - 桥接函数不得触碰 `financial_evidence`／`resolve_audit`／`audit_fidelity`。
    """
    insp = open(os.path.join(_GAME_ROOT, "core", "inspection.py"), encoding="utf-8").read()
    assert "from core.audit_case" not in insp and "import audit_case" not in insp, \
        "监察模块不得依赖审计链（方向：司法读监察，监察不读司法）"
    assert "financial_evidence" not in _code_only(insp), "证据读数不得在监察模块自算"

    ac = open(os.path.join(_GAME_ROOT, "core", "audit_case.py"), encoding="utf-8").read()
    code = _code_only(ac)
    # 证据读数**调用点**：仅 resolve_audit 内部一处（定义行不计）
    _ev_calls = [ln.strip() for ln in code.splitlines()
                 if "financial_evidence(state" in ln
                 and not ln.lstrip().startswith("def ")]
    assert len(_ev_calls) == 1, \
        f"financial_evidence 调用点应唯一（现 {len(_ev_calls)} 处：{_ev_calls}）"
    # 桥接函数体（截到下一个顶层 def）
    _start = code.index("def record_report_suspicion")
    _rest = code[_start + len("def record_report_suspicion"):]
    _end = _rest.find("\ndef ")
    bridge = _rest if _end < 0 else _rest[:_end]
    for banned in ("financial_evidence", "resolve_audit", "audit_fidelity",
                   "money", "statistics", "unrest", "grievance", "prefectures"):
        assert banned not in bridge, f"桥接函数不得触碰 {banned}（只做怀疑层适配）"
    assert "record_suspicion(" in bridge, "桥接必须委托既有怀疑唯一写入点"


def test_no_auto_path_from_settlement():
    """禁止自动：结算链**只**接线 `inspection_tick`，不得自动桥接/自动查账。"""
    settle = open(os.path.join(_GAME_ROOT, "core", "settlement.py"), encoding="utf-8").read()
    assert "inspection_tick" in settle
    for banned in ("record_report_suspicion", "record_suspicion",
                   "resolve_audit", "enqueue_inspection", "file_inspection_report"):
        assert banned not in settle, f"结算不得自动调用 {banned}（决策权归决策方）"


# ------------------------------------------------- ⑥ 财政隔离契约（长期保留）

def test_fiscal_isolation_control_with_bridge():
    """⑥ **财政隔离契约**：同种子 6 期，有任务局（含奏报＋桥接）vs 无任务局 ⇒ 逐位一致。"""
    a, b = new_game(), new_game()
    rk = _seed(a, next(iter(a.prefectures)))
    _seed(b, next(iter(b.prefectures)))
    r = enqueue_inspection(a, rk, "查赋")
    assert r["ok"]
    tid = r["task"]["id"]
    a.year, a.month = 990, 3
    inspection_tick(a)
    file_inspection_report(a, tid, summary="回报")
    record_report_suspicion(a, tid, "账目有亏空")
    for _ in range(6):
        a.month = b.month = 1 + (a.month % 12)
        run_monthly_settlement(a, seed_offset=0)
        run_monthly_settlement(b, seed_offset=0)
    assert money.m_all(a) == money.m_all(b), "察访＋怀疑层不得改变任何财政结果"
    assert a.prefectures == b.prefectures, "不得改变逐路状态"
    assert dict(a.statistics or {}) == dict(b.statistics or {})
    assert (getattr(a, "audit_cases", None) or {}) == (getattr(b, "audit_cases", None) or {})
    assert len(a.discovery_suspicions) == 1, "差异只在怀疑层（信息）"



