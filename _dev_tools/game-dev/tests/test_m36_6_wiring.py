# -*- coding: utf-8 -*-
"""M36.6《AI 决策接线收口》契约回归：**复用现有设施，不新增朝议层**。

四项（用户裁定 2026-10-11）：
 ① **大臣决策事实视图**（只读事实；不改权限；人格/忠诚不折算能力；不替大臣决策）
 ② **统一决策表达与提案映射**（`decision_record → payload.proposal` **仅五项**，不扩张执行载荷）
 ③ **保留人类决策与唯一桥接**（`record_report_suspicion` 唯一；`resolve_audit→financial_evidence` 单点不变）
 ④ **接入批红结果与执行反馈**（复用既有草稿/会签/批红链路；approve→会签生效；force→中旨；无新通道）
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.validators import to_proposal_payload  # noqa: E402
from core import money  # noqa: E402
from core.commands import approve_ai_action, new_game, reject_ai_action  # noqa: E402
from core.ministers_selection import (_fmt_decision_facts_block,  # noqa: E402
                                      minister_decision_facts)


def _seed(s, route, n=4):
    pool = s.prefectures[route]["pops"]["官僚"]
    move = min(int(n), int(pool.get("on_post", 0) or 0))
    pool["on_post"] = int(pool.get("on_post", 0) or 0) - move
    pool["waiting"] = int(pool.get("waiting", 0) or 0) + move
    return route


# ------------------------------------------------- ① 大臣决策事实视图

def test_decision_facts_are_readonly_and_neutral():
    """仅给事实：无推荐/优先级；**不**透出私德数值；调用**零写入**。"""
    s = new_game()
    before = (copy.deepcopy(s.prefectures), money.m_all(s), dict(s.statistics or {}),
              copy.deepcopy(getattr(s, "ai_pending_actions", [])),
              copy.deepcopy(s.inspection_tasks))
    facts = minister_decision_facts(s, "韩忠彦", viewer="official")
    block = _fmt_decision_facts_block(facts)
    assert set(facts) >= {"minister", "viewer", "inspection", "feedback", "pending",
                          "fiscal_context", "note"}
    # 只扫**数据体**（`note` 是说明文案，本身会写"不含推荐"）
    body = {k: v for k, v in facts.items() if k != "note"}
    for banned in ("loyalty", "corruption", "urgent", "推荐", "最优"):
        assert banned not in str(body), f"事实视图数据不得含 {banned}"
    for banned in ("宜", "推荐", "应当"):
        assert banned not in block, f"事实块不得含建议语（{banned}）"
    after = (s.prefectures, money.m_all(s), dict(s.statistics or {}),
             getattr(s, "ai_pending_actions", []), s.inspection_tasks)
    assert before[0] == after[0] and before[1] == after[1] and before[2] == after[2]
    assert before[3] == after[3] and before[4] == after[4], "事实视图不得写状态"


def test_decision_facts_permission_unchanged():
    """权限矩阵不变：`official` 只见账面；`inspector` 未密查/未达门限亦只见账面（D11 未动）。"""
    s = new_game()
    assert minister_decision_facts(s, viewer="official")["fiscal_context"]["allow_real"] is False
    assert minister_decision_facts(s, viewer="inspector")["fiscal_context"]["allow_real"] is False
    # 密查（走既有 ai_decision_view 语义）才见真账
    from core.inspection import ai_decision_view
    assert ai_decision_view(s, viewer="inspector", secret=True)["fiscal_context"]["allow_real"] is True


# ------------------------------------------------- ② 提案映射（仅五项）

def test_proposal_mapping_only_five_fields():
    """`decision_record → payload.proposal` **仅五项**；其余字段不得映射（不扩张执行载荷）。"""
    rec = {"issue_id": "I1", "proposer": "曾布",
           "facts_refs": ["inspection_view.capacity.free"],
           "inferences": [{"text": "x", "based_on": [], "speculative": True}],
           "unknowns": ["y"], "position": "宜先核其账",
           "alternatives": [{"option": "a", "why_not": "b"}],
           "risks": [{"category": "execution", "text": "名额有限"}],
           "authorization_required": "needs_approval", "executable": True,
           "executable_reason": "", "expected": "可明实情"}
    out = to_proposal_payload(rec, title="请核某路账目", summary="短述")
    prop = out["payload"]["proposal"]
    assert set(prop) == {"rationale", "evidence_refs", "risks", "authorization",
                         "expected", "title", "summary"}, "仅五项＋题名/短述"
    assert prop["rationale"] == rec["position"] and prop["authorization"] == "needs_approval"
    for not_mapped in ("inferences", "unknowns", "alternatives", "executable", "action_kind"):
        assert not_mapped not in prop, f"不得映射 {not_mapped}（须另裁）"
    assert out["missing"] == []
    # 缺项不编造：缺 ⇒ 省略并在 missing 列出
    out2 = to_proposal_payload({"position": "仅一句主张"})
    assert set(out2["payload"]["proposal"]) == {"rationale"}
    assert set(out2["missing"]) == {"evidence_refs", "risks", "authorization", "expected"}


def test_proposal_payload_passes_through_existing_channel():
    """映射结果可作既有 `enqueue_ai_action` 的 payload；**不改**批红规则、不被执行层读取。"""
    s = new_game()
    rk = _seed(s, next(iter(s.prefectures)))
    rec = {"position": "宜核其账", "facts_refs": ["inspection_view.capacity.free"],
           "risks": [{"category": "execution", "text": "名额有限"}],
           "authorization_required": "needs_approval", "expected": "可明实情"}
    out = to_proposal_payload(rec)
    aid = s.enqueue_ai_action("inspect_dispatch", "请核某路", "短述",
                              {"route": rk, "kind": "查赋", **out["payload"]},
                              proposer="曾布")
    item = [a for a in s.get_ai_pending("*") if a["id"] == aid][0]
    assert "proposal" in item["payload"], "proposal 随既有容器存放"
    assert s.inspection_tasks == [], "提案不执行"
    msg = approve_ai_action(s, aid)
    assert "批红" in msg and len(s.inspection_tasks) == 1, "仍走既有单点执行"


# ------------------------------------------------- ③ 唯一桥接 / 单点（冻结）

def test_unique_bridge_and_single_points_unchanged():
    """冻结项未改：`record_report_suspicion` 仍唯一桥接；`resolve_audit→financial_evidence` 单点不变。"""
    ac = open(os.path.join(_GAME_ROOT, "core", "audit_case.py"), encoding="utf-8").read()
    assert ac.count("def record_report_suspicion") == 1
    assert ac.count("def record_suspicion") == 1
    code = "\n".join(ln.split("#")[0] for ln in ac.splitlines())
    ev = [ln for ln in code.splitlines()
          if "financial_evidence(state" in ln and not ln.lstrip().startswith("def ")]
    assert len(ev) == 1, "证据读数调用点仍唯一（resolve_audit 内）"
    dec = open(os.path.join(_GAME_ROOT, "core", "settlement_decree.py"), encoding="utf-8").read()
    assert dec.count("resolve_audit(") == 1, "成案仍只经 audit_route"
    sel = open(os.path.join(_GAME_ROOT, "core", "ministers_selection.py"), encoding="utf-8").read()
    for banned in ("record_report_suspicion", "resolve_audit", "enqueue_inspection(",
                   "approve_ai_action", "apply_finance_reform"):
        assert banned not in sel, f"事实/选人层不得触碰 {banned}"


# ------------------------------------------------- ④ 批红结果与执行反馈

def test_feedback_recorded_without_auto_action():
    """处置结果记为**事实**（既有容器）；不自动重试/升级/注入提示词（P3）。"""
    s = new_game()
    rk = _seed(s, next(iter(s.prefectures)))
    aid = s.enqueue_ai_action("inspect_dispatch", "请遣官", "x",
                              {"route": rk, "kind": "查粮"}, proposer="曾布")
    approve_ai_action(s, aid)
    item = [a for a in s.get_ai_pending("*") if a["id"] == aid][0]
    assert item["status"] == "approved"
    assert item["feedback"]["outcome"] == "executed" and item["feedback"]["period"]
    assert len(s.inspection_tasks) == 1, "执行仍只走既有单点（未新增通道）"
    # 驳回：记 rejected，且**零世界变更**
    n_before = len(s.inspection_tasks)
    aid2 = s.enqueue_ai_action("inspect_dispatch", "请再遣", "y",
                               {"route": rk, "kind": "查粮"}, proposer="曾布")
    reject_ai_action(s, aid2)
    item2 = [a for a in s.get_ai_pending("*") if a["id"] == aid2][0]
    assert item2["status"] == "rejected" and item2["feedback"]["outcome"] == "rejected"
    assert len(s.inspection_tasks) == n_before, "驳回不得改变世界"
    # 失败（非法参数）：outcome=failed，且不产任务
    aid3 = s.enqueue_ai_action("inspect_dispatch", "非法", "z",
                              {"route": "不存在的路", "kind": "查粮"}, proposer="曾布")
    approve_ai_action(s, aid3)
    item3 = [a for a in s.get_ai_pending("*") if a["id"] == aid3][0]
    assert item3["status"] == "rejected" and item3["feedback"]["outcome"] == "failed"
    assert item3["feedback"]["reason"], "失败须带原因（不得标为已完成）"
    # P3：反馈不进提示词块（事实块只给观察量与计数）
    block = _fmt_decision_facts_block(minister_decision_facts(s, "曾布"))
    assert "驳回" not in block and "批红" not in block, "处置反馈不得自动注入提示词"


def test_facts_block_wired_into_audience_and_council():
    """接线守卫：召对与廷议**都**注入事实块；且不改召对机制与既有流程。"""
    court = open(os.path.join(_GAME_ROOT, "ai", "contracts_court.py"), encoding="utf-8").read()
    assert court.count("_build_decision_facts_context") >= 2, "召对与廷议均应注入事实块"
    cu = open(os.path.join(_GAME_ROOT, "ai", "client_utils.py"), encoding="utf-8").read()
    assert "def _build_decision_facts_context" in cu
    assert "minister_decision_facts" in cu
    # 事实块出现在 prompt 组装里（廷议）与 sys_p（召对）
    assert "facts_line" in court and "sys_p += _build_decision_facts_context" in court



