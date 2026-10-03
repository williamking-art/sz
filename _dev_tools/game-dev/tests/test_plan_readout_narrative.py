# -*- coding: utf-8 -*-
"""圣旨行动闭环 · **任务 5/6** 定向回归：单点读数 ＋ 完成宣称核对 ＋ 叙事契约。

断言：
  A. 读数（core/plan_readout.py）：四层级分离、脱敏、有界、**只读**、与 AI/UI 同源；
  B. 完成宣称核对：未告成却说"告成"→ 改写真话；否定语境不误伤；属实宣称不动；
  C. 取材闭集注入真实工程状态；
  D. 叙事契约只收档位词，非法档位整单失败（拒绝式）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.client import AIClient  # noqa: E402
from ai.narrative_guard import (  # noqa: E402
    _build_source_closure, _validate_completion_claims,
)
from core.blueprint_dynamic import register_dynamic_blueprint  # noqa: E402
from core.construction import propose_project  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.plan_readout import PHASE_LABELS, build_plan_readout, render_briefing_text  # noqa: E402


def _state():
    s = GameState("史实")
    init_legacies(s)
    s.treasury = 5_000_000_000
    return s


def _bp(name="榷酒务"):
    return {"name": name, "category": "财政", "cost": {"银": 100_000, "months": 1},
            "effects": [{"op": "酒课", "params": {"amount": 20_000}}]}


# ====================================================== A. 单点读数
def test_phase_labels_separate_four_levels():
    """四层级必须都有独立标签（规格 requirements.md:25：不得混写）。"""
    assert set(PHASE_LABELS) == {"accepted", "advancing", "completed", "effective"}
    for k, v in PHASE_LABELS.items():
        assert v and v != PHASE_LABELS.get("accepted") or k == "accepted"


def test_readout_empty_state_is_wellformed():
    s = _state()
    r = build_plan_readout(s)
    assert isinstance(r, dict)
    for k in PHASE_LABELS:
        assert isinstance(r["phases"][k], list)
    assert r["projects"] == [] or isinstance(r["projects"], list)
    assert render_briefing_text(r) == "" or isinstance(render_briefing_text(r), str)


def test_readout_does_not_mutate_state():
    """读数**只读**：不得建工程、不改账、不改统计。"""
    s = _state()
    register_dynamic_blueprint(s, _bp())
    route = list(s.prefectures)[0]
    propose_project(s, route, "榷酒务")
    before = (len(s.projects), s.treasury, dict(s.statistics))
    build_plan_readout(s)
    render_briefing_text(build_plan_readout(s))
    assert len(s.projects) == before[0]
    assert s.treasury == before[1]
    assert dict(s.statistics) == before[2]


def test_readout_separates_proposed_building_completed():
    s = _state()
    register_dynamic_blueprint(s, _bp())
    route = list(s.prefectures)[0]
    pid = propose_project(s, route, "榷酒务")["pid"]
    r = build_plan_readout(s)
    # 拟议 → 受理层
    assert any(x.get("pid") == pid for x in r["phases"]["accepted"]), r["phases"]
    assert not any(x.get("pid") == pid for x in r["phases"]["completed"])
    # 营建中 → 推进层
    s.projects[pid]["status"] = "building"
    s.projects[pid]["progress"] = 40
    r2 = build_plan_readout(s)
    assert any(x.get("pid") == pid for x in r2["phases"]["advancing"])
    # 运行 → 告成层 ＋ 效果生效层
    s.projects[pid]["status"] = "operating"
    s.projects[pid]["capacity"] = 1.0
    r3 = build_plan_readout(s)
    assert any(x.get("pid") == pid for x in r3["phases"]["completed"])
    assert any(x.get("pid") == pid for x in r3["phases"]["effective"])


def test_readout_route_filter_and_provenance():
    s = _state()
    register_dynamic_blueprint(s, _bp())
    r0 = list(s.prefectures)[0]
    propose_project(s, r0, "榷酒务")
    r = build_plan_readout(s, route=r0)
    assert all(p["route"] == r0 for p in r["projects"])
    assert r["projects"][0]["source_blueprint"].startswith("dyn:"), "缺因果回看来源"
    assert r["projects"][0]["dynamic"] is True


def test_readout_lists_unsupported_tasks():
    s = _state()
    s.statistics["task_unsupported"] = 2
    s.statistics["task_unsupported_list"] = [
        {"name": "兴修水利三年", "turn": 5, "reason": "无程序侧落点"}]
    r = build_plan_readout(s)
    assert r["unsupported_tasks"], "未列出待支持事务"
    assert r["counts"]["unsupported_total"] == 2
    txt = render_briefing_text(r)
    assert "兴修水利三年" in txt and "待支持" in txt


def test_briefing_text_is_desensitized():
    """注入文本不得带内部状态路径/字段名（防 AI 回写）。"""
    s = _state()
    register_dynamic_blueprint(s, _bp())
    propose_project(s, list(s.prefectures)[0], "榷酒务")
    txt = render_briefing_text(build_plan_readout(s))
    for leak in ("state.", "prefectures.", "treasury", "_runtime", "blueprint_key"):
        assert leak not in txt, f"注入文本泄漏内部字段：{leak}"


def test_briefing_bounded():
    s = _state()
    for i in range(30):
        register_dynamic_blueprint(s, _bp(name=f"工程{i}"))
        propose_project(s, list(s.prefectures)[i % len(s.prefectures)], f"工程{i}")
    r = build_plan_readout(s)
    assert len(r["projects"]) <= 40
    assert len(render_briefing_text(r).splitlines()) <= 30


# ====================================================== B. 完成宣称核对
def test_false_completion_claim_is_rewritten():
    """工程仍在办却说"告成" → 改写为如实表述。"""
    readout = {"projects": [{"name": "海塘", "status": "building", "progress": 30}],
               "unsupported_tasks": []}
    new, flagged = _validate_completion_claims("两浙海塘告成，百姓感悦。", readout)
    assert flagged, "未拦下不实宣称"
    assert "告成" not in new or "尚未告成" in new
    assert "海塘尚未告成" in new, new


def test_true_completion_claim_is_kept():
    readout = {"projects": [{"name": "海塘", "status": "operating", "capacity": 1.0}]}
    new, flagged = _validate_completion_claims("两浙海塘告成。", readout)
    assert not flagged, f"属实宣称被误伤：{flagged}"
    assert new == "两浙海塘告成。"


def test_negation_context_not_touched():
    """「尚未完工」是实话，不得被改写。"""
    readout = {"projects": [{"name": "海塘", "status": "building"}], "unsupported_tasks": []}
    for txt in ("海塘尚未完工。", "海塘未完工，尚需时日。", "海塘未能落成。"):
        new, flagged = _validate_completion_claims(txt, readout)
        assert not flagged, f"否定语境被误伤：{txt} → {new}"
        assert new == txt


def test_generic_completion_claim_without_false_target_is_softened():
    readout = {"projects": [{"name": "海塘", "status": "building"}],
               "unsupported_tasks": [{"name": "某事"}]}
    new, flagged = _validate_completion_claims("诸事告成，天下大治。", readout)
    assert flagged
    assert "告成" not in new


def test_claim_check_without_readout_is_noop():
    txt = "海塘告成。"
    new, flagged = _validate_completion_claims(txt, None)
    assert new == txt and flagged == []


def test_claim_check_handles_multiple_claims():
    readout = {"projects": [{"name": "甲工程", "status": "building"},
                            {"name": "乙工程", "status": "building"}],
               "unsupported_tasks": []}
    new, flagged = _validate_completion_claims("甲工程告成，乙工程亦告成。", readout)
    assert len(flagged) == 2, flagged
    # 两处都改成了"尚未告成"，且不再残留任何未被否定的"告成"
    assert new.count("尚未告成") == 2, new
    assert new.replace("尚未告成", "").count("告成") == 0, new


# ====================================================== C. 取材闭集注入真实状态
def test_source_closure_includes_real_project_state():
    s = _state()
    register_dynamic_blueprint(s, _bp())
    pid = propose_project(s, list(s.prefectures)[0], "榷酒务")["pid"]
    s.projects[pid]["status"] = "building"
    s.projects[pid]["progress"] = 55
    closure = _build_source_closure(s)
    assert "榷酒务" in closure, "取材闭集未注入真实工程状态"
    assert "营建中" in closure or "55" in closure
    assert "不得说成完工" in closure, "缺硬约束提示"


def test_source_closure_marks_unsupported_tasks():
    s = _state()
    s.statistics["task_unsupported_list"] = [
        {"name": "兴修水利三年", "turn": 3, "reason": "x"}]
    closure = _build_source_closure(s)
    assert "兴修水利三年" in closure
    assert "待支持" in closure


# ====================================================== D. 叙事契约
class _StubNarrative(AIClient):
    def __init__(self, reply):
        super().__init__()
        self._reply = reply
        self.last_call = None

    def _call(self, *args, **kw):
        self.last_call = (args[0] if args else "", args[1] if len(args) > 1 else "")
        return self._reply


import json  # noqa: E402


def test_narrative_contract_accepts_tier_only():
    c = _StubNarrative(json.dumps({"tier": "小", "narrative": "两浙海塘尚在进行。"},
                                  ensure_ascii=False))
    out = c.decree_narrative_decide("【在建】两浙路·海塘：营建中 30%")
    assert not out.get("_error"), out
    assert out["tier"] == "小"
    assert out["narrative"]


@pytest.mark.parametrize("bad", [
    {"narrative": "无档位"},
    {"tier": "极大", "narrative": "x"},
    {"tier": "小"},
    {"tier": "", "narrative": "x"},
])
def test_narrative_contract_rejects_bad_tier(bad):
    c = _StubNarrative(json.dumps(bad, ensure_ascii=False))
    assert c.decree_narrative_decide("读数").get("_error"), f"应拒绝：{bad}"


def test_narrative_prompt_forbids_numbers_and_false_claims():
    c = _StubNarrative(json.dumps({"tier": "微", "narrative": "尚在进行"},
                                  ensure_ascii=False))
    c.decree_narrative_decide("读数")
    sys_p = c.last_call[0]
    assert "不得" in sys_p and "数字" in sys_p
    assert "未告成" in sys_p and "待支持" in sys_p


# ====================================================== E. 护栏**接线**（防死码）
def test_postprocess_actually_invokes_completion_guard():
    """护栏必须在真实 `_postprocess` 链路上生效（不是只导出没人调的函数）。"""
    s = _state()
    register_dynamic_blueprint(s, _bp())
    propose_project(s, list(s.prefectures)[0], "榷酒务")   # 拟议，未告成
    c = AIClient()
    raw = json.dumps({"narrative": "两浙路榷酒务告成，酒利大增。"}, ensure_ascii=False)
    out = c._postprocess(raw, lambda o: o if isinstance(o, dict) else None,
                         lambda: {"narrative": "fallback"}, state=s)
    assert not out.get("_error"), out
    assert "尚未告成" in out["narrative"], f"护栏未接线：{out['narrative']}"


def test_postprocess_guard_noop_without_state():
    """未传 state 时**跳过**核对（不猜、不误伤）——这是诚实的边界，须锁住。"""
    c = AIClient()
    raw = json.dumps({"narrative": "两浙路榷酒务告成。"}, ensure_ascii=False)
    out = c._postprocess(raw, lambda o: o if isinstance(o, dict) else None,
                         lambda: {"narrative": "fallback"})
    assert out["narrative"] == "两浙路榷酒务告成。"


def test_postprocess_keeps_true_claim_with_state():
    s = _state()
    register_dynamic_blueprint(s, _bp())
    pid = propose_project(s, list(s.prefectures)[0], "榷酒务")["pid"]
    s.projects[pid].update({"status": "operating", "progress": 100, "capacity": 1.0})
    c = AIClient()
    raw = json.dumps({"narrative": "两浙路榷酒务告成。"}, ensure_ascii=False)
    out = c._postprocess(raw, lambda o: o if isinstance(o, dict) else None,
                         lambda: {"narrative": "fallback"}, state=s)
    assert out["narrative"] == "两浙路榷酒务告成。"