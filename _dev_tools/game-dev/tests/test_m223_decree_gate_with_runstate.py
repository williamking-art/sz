# -*- coding: utf-8 -*-
"""M223 P3 批 5：复述门**需建档的四条用例**（造官员运行态后过门；**仍不接主链**）。

解锁依据（M222 实测）：`minister_agent.can_act` 需 ①actor 在 `_actor_store`（＝`state.minister_agents`）
②`status == MINISTER_STATUS_IN_OFFICE` ③`authority` 为 >0 数值；且 `decree.addressees` 非空时 `aid` 须在其中。

建档用**公开入口** `minister_agent.ensure_actor(state, aid, *, posts, authority)`（幂等、不覆盖记忆）；
若其默认状态非在朝，则按**公开常量** `MINISTER_STATUS_IN_OFFICE` 置为在朝（测试夹具，不改产品代码）。
"""

import copy

from core import commands
from core import decree_confirm as dc
from core.domains.administration import minister_agent as ma

AID = sorted(dc.MINISTERS)[0] if getattr(dc, "MINISTERS", None) else "司马光"


def _state_with_actor():
    import random
    random.seed(20261013)
    s = commands.new_game()
    ma.ensure_actor(s, AID, posts=["参知政事"], authority=5)          # 公开建档入口
    s.minister_agents[AID]["status"] = ma.MINISTER_STATUS_IN_OFFICE    # 确保在朝（判据②）
    return s


def _decree():
    return {"decree_id": "TEST-D2", "title": "开仓赈济", "body": "诏京畿路开常平仓赈济",
            "visibility": "公", "addressees": [AID]}                    # 受命＝该官（过判据④）


def test_actor_can_act_after_ensure():
    """前置自检：建档＋在朝＋authority>0 ⇒ `can_act.ok is True`。"""
    s = _state_with_actor()
    gate = ma.can_act(s, AID)
    assert gate["ok"] is True, gate


def test_gate_authorized_and_consistent_recitation_passes():
    """① 一致 ⇒ **放行**：`authorized=True`、三列表空、`withheld=False`。"""
    s = _state_with_actor()
    d = _decree()
    rec = dc.compose_recitation(dc.canonical_decree(d))
    out = dc.confirm_decree(s, d["decree_id"], AID, decree=d, recitation=rec)
    assert out["authorized"] is True, out
    assert out["withheld"] is False
    assert out["mismatched"] == [] and out["missing"] == [] and out["unsupported"] == []


def test_gate_mismatched_recitation_is_not_passed():
    """② 不符 ⇒ **不得放行**（`mismatched` 非空；不静默通过）。"""
    s = _state_with_actor()
    d = _decree()
    rec = copy.deepcopy(dc.compose_recitation(dc.canonical_decree(d)))
    rec["body"] = "（改坏）"
    out = dc.confirm_decree(s, d["decree_id"], AID, decree=d, recitation=rec)
    assert "body" in out["mismatched"], out


def test_gate_not_recited_is_not_passed():
    """③ 未复述（无记录且不传复述、`record=False`）⇒ **不得放行**（`recited=False`）。"""
    s = _state_with_actor()
    d = _decree()
    out = dc.confirm_decree(s, d["decree_id"], AID, decree=d, recitation=None)
    assert out["recited"] is False, out
    assert not (out["mismatched"] == [] and out["missing"] == [] and out["unsupported"] == []
                and out.get("authorized") is True and out.get("recorded") is True), out


def test_gate_ai_candidate_cannot_pass():
    """④ 防伪：`backfill_candidates` 的候选**直接**当复述 ⇒ **不得放行**。"""
    s = _state_with_actor()
    d = _decree()
    cands = dc.backfill_candidates(s)
    rec = None
    if cands and isinstance(cands[0], dict):
        rec = cands[0].get("elements") if isinstance(cands[0].get("elements"), dict) else None
    if not isinstance(rec, dict):
        rec = {"body": "AI 候选（非承办者复述）"}
    out = dc.confirm_decree(s, d["decree_id"], AID, decree=d, recitation=rec)
    assert not (out["mismatched"] == [] and out["missing"] == [] and out["unsupported"] == []), out
