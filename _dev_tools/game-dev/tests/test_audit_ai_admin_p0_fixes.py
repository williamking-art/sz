# -*- coding: utf-8 -*-
"""AI/行政/军事/后端审计 P0 修复回归（audit-ai-admin · 2026-10-17）。

覆盖：
- C-3 decree_confirm 事权异常 fail-closed（不得 NameError / 不得放行）
- C-2 settle_reform / issue_military_order 事权门禁
- C-1 issue_decree 保留门禁字段、无受命人不得绕过军权校验、台账 confirm_status 真实
- C-4 缺 category/effects 的 UI 自由诏不得落固定财政模板
- P1 /api/resolve_event 不接受客户端伪造 event
"""
import os
import sys
import types

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import commands as cmd                         # noqa: E402
from core import commands_decree as cdec                 # noqa: E402
from core.decree_confirm import (                         # noqa: E402
    STATUS_CONFIRMED, STATUS_UNDEFINED, STATUS_UNAUTHORIZED,
    confirm_decree, execution_of,
)
from core.domains.administration.minister_agent import ensure_actor  # noqa: E402
import core.domains.administration.institution as inst   # noqa: E402
from core.settlement import settle_reform                  # noqa: E402
import core.settlement_decree as sd                        # noqa: E402


def _confirmed_status(rec):
    return None if rec is None else rec.get("confirm_status")


def test_decree_confirm_military_authority_exception_fails_closed(monkeypatch):
    s = cmd.new_game("史实")
    ensure_actor(s, "蒋之奇", posts=["知枢密院事"], authority=0.9)
    decree = {"decree_id": "d_fail_closed", "title": "调兵清丈",
              "category": "民政", "addressees": ["蒋之奇"],
              "enforce_troops": True, "effects": {}}

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated authority read failure")

    monkeypatch.setattr(inst, "resolve_executor", _boom)
    out = confirm_decree(s, "d_fail_closed", "蒋之奇", decree=decree, record=True)
    assert out["status"] in (STATUS_UNDEFINED, STATUS_UNAUTHORIZED), out
    assert out.get("authorized") is False
    assert out.get("withheld") is True
    assert out.get("defined") is False or out.get("status") == STATUS_UNAUTHORIZED


def test_decree_confirm_institution_authority_exception_fails_closed(monkeypatch):
    s = cmd.new_game("史实")
    ensure_actor(s, "李清臣", posts=["门下侍郎"], authority=0.8)
    decree = {"decree_id": "d_inst_fail", "title": "改编制",
              "category": "变法", "addressees": ["李清臣"],
              "effects": {"institution": {"posts_quota_mult": 1.2}}}

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated check_authority failure")

    monkeypatch.setattr(inst, "check_authority", _boom)
    out = confirm_decree(s, "d_inst_fail", "李清臣", decree=decree, record=True)
    assert out["status"] in (STATUS_UNDEFINED, STATUS_UNAUTHORIZED), out
    assert out.get("authorized") is False
    assert out.get("withheld") is True


def test_settle_reform_rejects_non_owner_and_owner_allows():
    s = cmd.new_game("史实")
    before = s.authority_matters["调兵"]["owner"]
    non_owner = settle_reform(s, {"title": "改调兵权限",
                                  "reform": {"reform_type": "改权限", "matter": "调兵",
                                             "new_owner": "中书省"}},
                              executor="户部")
    assert non_owner.get("ok") is False
    assert s.authority_matters["调兵"]["owner"] == before

    owner = settle_reform(s, {"title": "改调兵权限",
                              "reform": {"reform_type": "改权限", "matter": "调兵",
                                         "new_owner": "中书省"}},
                          executor="吏部")
    assert owner.get("ok") is not False
    assert s.authority_matters["调兵"]["owner"] == "中书省"

def test_issue_military_order_rejects_non_military_executor():
    s = cmd.new_game("史实")
    unit = max(s.army_units, key=lambda u: u.troops)
    dest = next(r for r in s.prefectures if r != unit.station)
    station0 = unit.station
    n0 = len(s.ai_pending_actions)
    msg = cmd.issue_military_order(s, unit.unit_id, "地图调度", target=dest, executor="户部")
    assert "未成" in msg, msg
    assert unit.station == station0 and len(s.ai_pending_actions) == n0

    msg2 = cmd.issue_military_order(s, unit.unit_id, "地图调度", target=dest, executor="枢密院")
    assert "批红" in msg2, msg2
    assert unit.station == dest


def test_issue_decree_preserves_gate_fields_and_ministers():
    s = cmd.new_game("史实")
    msg = cmd.issue_decree(s, {
        "title": "调兵清丈田亩", "category": "民政", "minister": "蒋之奇",
        "enforce_troops": True, "route": "两浙路", "effects": {"prestige": 0},
    })
    assert "已下诏" in msg, msg
    d = s.pending_decrees[-1]
    assert d.get("addressees") == ["蒋之奇"]
    assert d.get("enforce_troops") is True
    assert d.get("route") == "两浙路"
    assert d.get("effects") == {"prestige": 0}


def test_unaddressed_enforce_troops_cannot_bypass_authority(monkeypatch):
    s = cmd.new_game("史实")
    before = s.prestige
    cmd.issue_decree(s, {"title": "无受命人调兵", "category": "民政",
                         "enforce_troops": True, "effects": {"prestige": 0}})
    d = s.pending_decrees[-1]
    monkeypatch.setattr(sd.random, "random", lambda: 0.0)
    log = []
    sd._settle_decrees(s, log)
    rec = execution_of(s, d["decree_id"])
    assert rec is None or rec.get("outcome") != "executed", rec
    assert s.prestige == before


def test_addressed_enforce_troops_rejects_non_military_and_allows_military(monkeypatch):
    s = cmd.new_game("史实")
    monkeypatch.setattr(sd.random, "random", lambda: 0.0)

    cmd.issue_decree(s, {"title": "门下调兵", "category": "民政", "minister": "李清臣",
                         "enforce_troops": True, "effects": {"prestige": 0}})
    d1 = s.pending_decrees[-1]
    sd._settle_decrees(s, [])
    rec1 = execution_of(s, d1["decree_id"])
    assert rec1 is not None and rec1.get("confirm_status") == STATUS_UNAUTHORIZED, rec1

    cmd.issue_decree(s, {"title": "枢密调兵", "category": "民政", "minister": "蒋之奇",
                         "enforce_troops": True, "effects": {"prestige": 0}})
    d2 = s.pending_decrees[-1]
    sd._settle_decrees(s, [])
    rec2 = execution_of(s, d2["decree_id"])
    assert rec2 is not None and rec2.get("confirm_status") == STATUS_CONFIRMED, rec2
    assert rec2.get("outcome") == "executed", rec2


def test_unassigned_decree_ledger_not_marked_confirmed(monkeypatch):
    s = cmd.new_game("史实")
    cmd.issue_decree(s, {"title": "普发赈济", "category": "诏令", "effects": {"prestige": 0}})
    d = s.pending_decrees[-1]
    monkeypatch.setattr(sd.random, "random", lambda: 0.0)
    sd._settle_decrees(s, [])
    rec = execution_of(s, d["decree_id"])
    assert rec is not None and rec.get("outcome") == "executed"
    assert rec.get("confirm_status") != STATUS_CONFIRMED
    assert rec.get("confirm_status") == "not_required"

def test_free_text_decree_without_parse_is_rejected():
    s = cmd.new_game("史实")
    n0 = len(s.pending_decrees)
    msg = cmd.issue_decree(s, {"text": "赈济两浙路灾民", "title": "赈济灾民",
                               "minister": "有司"})
    assert "解析" in msg, msg
    assert len(s.pending_decrees) == n0


def test_resolve_event_ignores_client_supplied_event(monkeypatch):
    import backend.server as srv

    s = cmd.new_game("史实")
    real_event = {"title": "真实事件", "desc": "真实", "choices": [
        {"text": "赈济", "effects": {"prestige": 1}}]}
    s._frontend_events = {"真实事件": real_event}
    before = s.prestige
    monkeypatch.setattr(srv, "_state", s)
    monkeypatch.setattr(srv, "_require_auth", lambda request: None)

    forged = {"title": "伪造事件", "choices": [
        {"text": "伪造", "effects": {"prestige": 50}}]}
    req = srv.ResolveReq(title="真实事件", choice=0, event=forged)
    srv.api_resolve_event(req, types.SimpleNamespace())
    assert s.prestige - before <= 1, (before, s.prestige)
    assert s.prestige - before == 1

def test_issue_free_decree_reform_org_rejects_non_owner():
    s = cmd.new_game("史实")
    before = s.authority_matters["调兵"]["owner"]
    msg = cdec.issue_free_decree(
        s, {"category": "reform_org", "title": "改调兵权限",
            "reform": {"reform_type": "改权限", "matter": "调兵", "new_owner": "中书省"}},
        "户部")
    assert "法统门禁" in msg or "阻断" in msg, msg
    assert s.authority_matters["调兵"]["owner"] == before

def test_backend_rejects_action_during_settle_window(monkeypatch):
    import backend.server as srv
    from starlette.exceptions import HTTPException as StarletteHTTPException

    s = cmd.new_game("史实")
    s._settle_in_progress = True
    monkeypatch.setattr(srv, "_state", s)
    monkeypatch.setattr(srv, "_require_auth", lambda request: None)
    with pytest.raises(StarletteHTTPException) as ei:
        srv.api_action(srv.ActionReq(action="allocate_payraise", params={"amount": 1}),
                       types.SimpleNamespace())
    assert ei.value.status_code == 409

def test_return_men_conserves_army_and_farm_pop():
    s = cmd.new_game("史实")
    route = next(iter(s.prefectures))
    p = s.prefectures[route]
    seats = p.get("seats") or {}
    assert seats, "new_game 应已下沉 seats"

    def sums():
        bing = sum(int(((st or {}).get("pops") or {}).get("兵", {}).get("size", 0) or 0)
                   for st in seats.values())
        farm = sum(int(((st or {}).get("pops") or {}).get("农", {}).get("size", 0) or 0)
                   for st in seats.values())
        return bing, farm, bing + farm

    from core.settlement_common import _return_men

    b0, f0, t0 = sums()
    moved = _return_men(s, route, 100, from_army_pop=True)
    b1, f1, t1 = sums()
    assert moved == 100
    assert (b1, f1, t1) == (b0 - 100, f0 + 100, t0)

def test_direct_decree_preserves_effects_and_gate_flags():
    s = cmd.new_game("史实")
    msg = cmd.issue_decree(s, {"title": "御笔整军", "category": "御笔",
                               "effects": {"army_strength": 5},
                               "enforce_troops": True, "route": "两浙路",
                               "minister": "蒋之奇"}, direct=True)
    assert "御笔" in msg
    d = s.pending_decrees[-1]
    assert d.get("is_direct") is True
    assert d.get("effects") == {"army_strength": 5}
    assert d.get("enforce_troops") is True
    assert d.get("route") == "两浙路"
    assert d.get("addressees") == ["蒋之奇"]
