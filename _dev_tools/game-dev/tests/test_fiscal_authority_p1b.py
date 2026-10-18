# -*- coding: utf-8 -*-
"""P1b：财政 effect→事权注册表 + F3–F7 入口 actor 门。"""
import pytest

from core import commands
from core import authority_gate
from core.commands import approve_ai_action, enqueue_finance_proposal
from core.commands_decree import (
    issue_decree,
    issue_edict_from_review,
    issue_free_decree,
    issue_kouyu,
)


def _state():
    return commands.new_game()


ACTUAL_FISCAL_KEYS = {
    "audit_route": "财政勾稽",
    "relief": "度支调度",
    "he_mi": "度支调度",
    "military_supply": "度支调度",
    "grain_stabilize": "度支调度",
    "granary_reform": "度支调度",
    "single_whip": "赋税",
    "pay_reform": "度支调度",
    "curtail_waste": "度支调度",
    "reduce_office": "度支调度",
    "anti_corruption": "财政勾稽",
    "confiscate": "财政勾稽",
}


def test_fiscal_effect_registry_covers_required_keys():
    effects = {
        "treasury": 1000,
        "commerce_tax": 0.2,
        "finance_rates": 1,
        "audit_route": "两浙路",
        "confiscate": {},
        "institution": {"didang_loan_rate": "=0.03"},
    }
    matters = authority_gate.matters_for_effects(effects)
    assert set(matters) >= {"度支调度", "赋税", "财政勾稽", "官营放贷"}


@pytest.mark.parametrize("key,matter", sorted(ACTUAL_FISCAL_KEYS.items()))
def test_actual_fiscal_keys_registered(key, matter):
    assert matter in authority_gate.matters_for_effects({key: 1})


def test_finance_path_registry():
    changes = [
        {"path": "treasury", "op": "add", "value": -1},
        {"path": "commerce_tax", "op": "set", "value": 0.2},
        {"path": "audit.cases", "op": "add", "value": 1},
    ]
    matters = authority_gate.matters_for_finance_changes(changes)
    assert set(matters) >= {"度支调度", "赋税", "财政勾稽"}


def test_issue_free_decree_authorized_applies():
    s = _state()
    before = int(s.statistics.get("legacy_unchecked_fiscal", 0) or 0)
    msg = issue_free_decree(
        s,
        {"category": "free_edict", "title": "拨帑", "effects": {"treasury": 1000},
         "executor": "王古"},
        "陛下",
    )
    assert "未成" not in msg and "事权拒绝" not in msg, msg
    assert int(s.statistics.get("legacy_unchecked_fiscal", 0) or 0) == before


def test_issue_free_decree_non_holder_rejected():
    s = _state()
    msg = issue_free_decree(
        s,
        {"category": "free_edict", "title": "拨帑", "effects": {"treasury": 1000},
         "executor": "李清臣"},
        "陛下",
    )
    assert "事权拒绝" in msg, msg


def test_issue_kouyu_authorized():
    s = _state()
    msg = issue_kouyu(
        s,
        {"title": "减商税", "effects": [{"dim": "commerce_tax", "value": 0.2}],
         "executor": "王古"},
    )
    assert "口宣" in msg and "未发" not in msg, msg


def test_issue_kouyu_non_holder_rejected():
    s = _state()
    msg = issue_kouyu(
        s,
        {"title": "减商税", "effects": [{"dim": "commerce_tax", "value": 0.2}],
         "executor": "李清臣"},
    )
    assert "口宣未发" in msg, msg


def test_edict_review_org_hint_is_not_actor_and_executor_checked():
    s = _state()
    did = s.add_edict_draft({
        "title": "拨帑", "org_hint": "户部",
        "effects": [{"dim": "treasury", "value": 1000}],
    })
    before = int(s.statistics.get("legacy_unchecked_fiscal", 0) or 0)
    msg = issue_edict_from_review(s, did, decision="approve")
    assert "已准奏" in msg, msg
    assert int(s.statistics.get("legacy_unchecked_fiscal", 0) or 0) == before + 1

    did2 = s.add_edict_draft({
        "title": "拨帑2", "org_hint": "户部",
        "effects": [{"dim": "treasury", "value": 1000}],
    })
    msg2 = issue_edict_from_review(s, did2, decision="approve", executor="李清臣")
    assert "诏草未发" in msg2, msg2

    did3 = s.add_edict_draft({
        "title": "拨帑3", "org_hint": "户部",
        "effects": [{"dim": "treasury", "value": 1000}],
    })
    msg3 = issue_edict_from_review(s, did3, decision="approve", executor="王古")
    assert "已准奏" in msg3, msg3


def test_finance_proposal_authorized():
    s = _state()
    aid = enqueue_finance_proposal(
        s, title="拨帑", summary="国库→民间",
        changes=[
            {"path": "treasury", "op": "add", "value": -1000, "reason": "赈济"},
            {"path": "prefectures.京畿路.pops.士绅.wealth", "op": "add",
             "value": 1000, "reason": "赈济"},
        ],
        proposer="户部", executor="王古",
    )
    msg = approve_ai_action(s, aid)
    assert "已落地" in msg, msg


def test_finance_proposal_non_holder_rejected():
    s = _state()
    aid = enqueue_finance_proposal(
        s, title="拨帑", summary="国库→民间",
        changes=[
            {"path": "treasury", "op": "add", "value": -1000, "reason": "赈济"},
            {"path": "prefectures.京畿路.pops.士绅.wealth", "op": "add",
             "value": 1000, "reason": "赈济"},
        ],
        proposer="户部", executor="李清臣",
    )
    msg = approve_ai_action(s, aid)
    assert "财政事权拒绝" in msg, msg


def test_issue_decree_fiscal_effects_explicit_and_legacy():
    s = _state()
    n = len(s.pending_decrees)
    msg = issue_decree(
        s, {"title": "拨帑", "category": "民政", "effects": {"treasury": 1000},
            "executor": "王古"})
    assert "已下诏" in msg, msg
    assert len(s.pending_decrees) == n + 1

    n2 = len(s.pending_decrees)
    bad = issue_decree(
        s, {"title": "拨帑2", "category": "民政", "effects": {"treasury": 1000},
            "executor": "李清臣"})
    assert "事权不合法" in bad, bad
    assert len(s.pending_decrees) == n2

    before = int(s.statistics.get("legacy_unchecked_fiscal", 0) or 0)
    legacy = issue_decree(
        s, {"title": "拨帑3", "category": "民政", "effects": {"treasury": 1000}})
    assert "已下诏" in legacy, legacy
    assert int(s.statistics.get("legacy_unchecked_fiscal", 0) or 0) == before + 1


def test_issue_decree_multi_matter_single_executor():
    s = _state()
    ok = issue_decree(
        s, {"title": "财政组合", "category": "民政",
            "effects": {"treasury": 1000, "commerce_tax": 0.2},
            "executor": "王古"})
    assert "已下诏" in ok, ok

    bad = issue_decree(
        s, {"title": "财政组合2", "category": "民政",
            "effects": {"treasury": 1000, "commerce_tax": 0.2},
            "executor": "邓洵武"})
    assert "事权不合法" in bad, bad


def test_issue_decree_primary_plus_extra_fiscal_rejected():
    s = _state()
    msg = issue_decree(
        s, {"title": "铨选兼拨帑", "category": "民政",
            "primary_matter": "官吏铨选", "executor": "吏部",
            "effects": {"treasury": 1000}})
    assert "事权不合法" in msg, msg


def test_issue_decree_audit_route_actor_gate():
    s = _state()
    ok = issue_decree(
        s, {"title": "勾校两浙", "category": "民政",
            "effects": {"audit_route": "两浙路"}, "executor": "王古"})
    assert "已下诏" in ok, ok
    bad = issue_decree(
        s, {"title": "勾校两浙2", "category": "民政",
            "effects": {"audit_route": "两浙路"}, "executor": "李清臣"})
    assert "事权不合法" in bad, bad


def test_backend_edict_review_passes_executor():
    from game.backend.client import LocalBackend

    s = _state()
    did = s.add_edict_draft({
        "title": "拨帑", "org_hint": "户部",
        "effects": [{"dim": "treasury", "value": 1000}],
    })
    msg, _ = LocalBackend().action(
        s, "issue_edict_from_review",
        {"draft_id": did, "decision": "approve", "executor": "李清臣"},
    )
    assert "诏草未发" in msg, msg

