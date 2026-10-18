# -*- coding: utf-8 -*-
"""P1a：F1 didang actor 预检 + F2 中央补发度支调度门。"""
import pytest

from core import commands
from core import free_effect as fe
from core.domains.administration import institution as inst
from core.settlement_finance import _settle_local_expenditure, repay_local_arrears


def _contract(executor, mode="once", cost=False):
    c = {
        "mode": mode,
        "effects": {"institution": {"didang_loan_rate": "=0.03"}},
        "executor": executor,
    }
    if mode == "ongoing":
        c["duration"] = 6
    if cost:
        c["cost"] = {"treasury": 100000}
    return c


def _arrears_state():
    s = commands.new_game()
    rk = min(s.prefectures)
    for _ in range(4):
        s.prefectures[rk]["local_treasury"] = 0
        _settle_local_expenditure(s, [])
    s.treasury = 10 ** 9
    return s, rk


def test_f1_authorized_didang_applies():
    s = commands.new_game()
    log = fe._apply_free_effect(s, _contract("王古"))
    assert inst.get(s, "didang_loan_rate") == pytest.approx(0.03), log


def test_f1_authority_precheck_runs_before_cost():
    s = commands.new_game()
    s.treasury = 10 ** 9
    before = int(s.treasury)
    log = fe._apply_free_effect(s, _contract("李清臣", cost=True))
    assert any("事权拒绝" in x for x in log), log
    assert int(s.treasury) == before
    assert inst.get(s, "didang_loan_rate") == pytest.approx(0.01)


def test_f1_non_holder_rejected_without_cost():
    s = commands.new_game()
    s.treasury = 10 ** 9
    before = int(s.treasury)
    log = fe._apply_free_effect(s, _contract("李清臣"))
    assert any("事权拒绝" in x for x in log), log
    assert inst.get(s, "didang_loan_rate") == pytest.approx(0.01)
    assert int(s.treasury) == before


def test_f1_vacant_post_rejected_then_filled():
    s = commands.new_game()
    s.treasury = 10 ** 9
    log = fe._apply_free_effect(s, _contract({"post": "户部侍郎"}))
    assert any("事权拒绝" in x for x in log), log
    s.central_orgs["户部"]["holders"]["户部侍郎"] = "李四"
    log2 = fe._apply_free_effect(s, _contract({"post": "户部侍郎"}))
    assert inst.get(s, "didang_loan_rate") == pytest.approx(0.03), log2


def test_f1_ongoing_loses_authority_next_month():
    s = commands.new_game()
    s.central_orgs["户部"]["holders"]["户部侍郎"] = "李四"
    log = fe._apply_free_effect(
        s, _contract({"post": "户部侍郎"}, mode="ongoing", cost=False))
    assert s.longterm_effects[-1]["authority_mode"] == "actor_position"
    assert inst.get(s, "didang_loan_rate") == pytest.approx(0.01)

    s.central_orgs["户部"]["holders"]["户部侍郎"] = ""
    log2 = []
    fe._settle_free_effects(s, log2)
    assert inst.get(s, "didang_loan_rate") == pytest.approx(0.01)
    assert s.longterm_effects[-1]["last_error"] == "authority_denied"
    assert s.longterm_effects[-1]["duration"] == 6
    assert log2


def test_f1_old_apply_reform_unchanged_and_marked_legacy():
    s = commands.new_game()
    log = inst.apply_reform(s, {"didang_loan_rate": "=0.04"}, "户部")
    assert inst.get(s, "didang_loan_rate") == pytest.approx(0.04)
    assert any("legacy_authority" in x for x in log), log

    s2 = commands.new_game()
    log2 = inst.apply_reform(s2, {"didang_loan_rate": "=0.04"}, "枢密院")
    assert inst.get(s2, "didang_loan_rate") == pytest.approx(0.01)
    assert any("legacy_authority" in x for x in log2), log2


def test_f1_rejection_does_not_increment_legacy_counter():
    s = commands.new_game()
    s.statistics["legacy_unchecked_fiscal"] = 0
    fe._apply_free_effect(s, _contract("李清臣"))
    assert int(s.statistics.get("legacy_unchecked_fiscal", 0) or 0) == 0


def test_f2_treasury_with_authorized_actor():
    s, rk = _arrears_state()
    ret = repay_local_arrears(
        s, route=rk, source="treasury", amount=2000, executor="王古")
    assert ret["repaid"] > 0
    assert ret["authority_mode"] == "actor_position"


def test_f2_treasury_with_non_holder_rejected():
    s, rk = _arrears_state()
    before = int(s.treasury)
    ret = repay_local_arrears(
        s, route=rk, source="treasury", amount=2000, executor="李清臣")
    assert ret["repaid"] == 0
    assert ret["skipped"] == "authority_denied"
    assert int(s.treasury) == before


def test_f2_treasury_without_executor_legacy_counts():
    s, rk = _arrears_state()
    before = int(s.statistics.get("legacy_unchecked_fiscal", 0) or 0)
    ret = repay_local_arrears(
        s, route=rk, source="treasury", amount=2000, strict=False)
    assert ret["repaid"] > 0
    assert ret["authority_mode"] == "legacy_unchecked_fiscal"
    assert int(s.statistics.get("legacy_unchecked_fiscal", 0) or 0) == before + 1


def test_f2_treasury_without_executor_strict_rejects():
    s, rk = _arrears_state()
    before = int(s.treasury)
    ret = repay_local_arrears(
        s, route=rk, source="treasury", amount=2000, strict=True)
    assert ret["repaid"] == 0
    assert ret["skipped"] == "authority_denied"
    assert int(s.treasury) == before


def test_f2_coffer_path_unchanged():
    s, rk = _arrears_state()
    s.prefectures[rk]["local_treasury"] = 10 ** 9
    ret = repay_local_arrears(s, route=rk, source="coffer")
    assert ret["repaid"] > 0
    assert "authority_mode" not in ret


def test_f2_invalid_route_keeps_semantics():
    s, _rk = _arrears_state()
    ret = repay_local_arrears(
        s, route="不存在", source="treasury", executor="王古")
    assert ret["repaid"] == 0
    assert ret["authority_mode"] == "actor_position"

