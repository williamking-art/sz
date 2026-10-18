# -*- coding: utf-8 -*-
"""P0a：authority_gate actor 判权（权限挂在职位上）。"""
import ast
import copy
import io
import os

from core import authority_gate, commands
from core.authority_gate import check_decree_authority, check_matter_authority
from core.decree_confirm import (
    STATUS_UNAUTHORIZED,
    STATUS_UNDEFINED,
    confirm_decree,
)
from core.domains.administration import institution as inst


def _state():
    return commands.new_game()


def test_incumbent_minister_holds_matter():
    s = _state()
    ok, actor = check_matter_authority(s, "王古", "官营放贷")
    assert ok is True and actor == "王古"


def test_non_lead_post_holder_inherits_org_matter():
    s = _state()
    s.central_orgs["户部"]["holders"]["户部侍郎"] = "李四"
    ok, actor = check_matter_authority(s, {"post": "户部侍郎"}, "官营放贷")
    assert ok is True and actor == "李四"


def test_vacant_post_is_rejected():
    s = _state()
    ok, _ = check_matter_authority(s, {"post": "户部侍郎"}, "官营放贷")
    assert ok is False


def test_non_holder_is_rejected():
    s = _state()
    ok, _ = check_matter_authority(s, "路人甲", "官营放贷")
    assert ok is False


def test_cross_department_is_rejected():
    s = _state()
    assert check_matter_authority(s, "王古", "官吏铨选")[0] is False
    assert check_matter_authority(s, "邓洵武", "官营放贷")[0] is False


def test_dismissal_removes_permission_and_reappointment_restores():
    s = _state()
    holders = s.central_orgs["户部"]["holders"]
    holders["户部侍郎"] = "李四"
    assert check_matter_authority(s, {"post": "户部侍郎"}, "官营放贷")[0] is True
    holders["户部侍郎"] = ""
    assert check_matter_authority(s, {"post": "户部侍郎"}, "官营放贷")[0] is False
    holders["户部侍郎"] = "李四"
    assert check_matter_authority(s, {"post": "户部侍郎"}, "官营放贷")[0] is True


def test_org_resolves_to_first_incumbent_and_empty_org_rejects():
    s = _state()
    assert check_matter_authority(s, {"org": "户部"}, "官营放贷")[0] is True
    for title in list(s.central_orgs["户部"]["holders"]):
        s.central_orgs["户部"]["holders"][title] = ""
    ok, reason = check_matter_authority(s, {"org": "户部"}, "官营放贷")
    assert ok is False
    assert "无法解析承办人" in reason


def test_rejection_does_not_mutate_state():
    s = _state()
    before = (
        copy.deepcopy(s.central_orgs),
        copy.deepcopy(getattr(s, "factions", {})),
        copy.deepcopy(getattr(s, "statistics", {})),
    )
    check_matter_authority(s, "李清臣", "调兵")
    assert s.central_orgs == before[0]
    assert getattr(s, "factions", {}) == before[1]
    assert getattr(s, "statistics", {}) == before[2]


def test_decree_confirm_authority_exception_is_fail_closed(monkeypatch):
    s = _state()
    s.central_orgs["门下省"]["holders"]["门下侍郎"] = "李清臣"
    decree = {
        "decree_id": "d_gate_fail", "title": "改编制", "category": "变法",
        "addressees": ["李清臣"],
        "effects": {"institution": {"posts_quota_mult": 1.2}},
    }

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated authority_gate failure")

    monkeypatch.setattr(authority_gate, "check_decree_authority", _boom)
    out = confirm_decree(s, "d_gate_fail", "李清臣", decree=decree, record=True)
    assert out["status"] in (STATUS_UNDEFINED, STATUS_UNAUTHORIZED), out
    assert out.get("authorized") is False
    assert out.get("withheld") is True


def test_high_prestige_does_not_bypass_authority():
    s = _state()
    s.prestige = 100
    assert check_matter_authority(s, "王古", "官吏铨选")[0] is False


def test_legacy_gate_unchanged_and_unknown_key_passes():
    s = _state()
    assert inst.check_authority(s, "didang_loan_rate", "枢密院")[0] is False
    assert inst.check_authority(
        s, "didang_loan_rate", {"post": "抵当所提举"}
    )[0] is True
    assert check_decree_authority(s, "not_a_known_key", "路人甲") == (True, "")


def test_institution_still_has_no_core_imports():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))),
        "game", "core", "domains", "administration", "institution.py",
    )
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    offenders = []
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
        elif isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        for m in mods:
            if m.startswith("core."):
                offenders.append(m)
    assert not offenders, offenders

