# -*- coding: utf-8 -*-
"""圣旨生命周期：天道遵从度 × 吏治通道、法统门禁（P0 修复批 · 2026-10-17）。

口径要点（用户 2026-09-19 定稿 + 2026-10-17 修复）：
· 吏治是**唯一强关联**通道，`clerks_mult` = **吏胥折扣本体**（不得被遵从度改写，
  否则既有单点用例 test_finance_reform_p4::test_route_grip_discount_and_scope 被撞掉）；
· 知州遵从度作为**吏治通道内部输入**，在 `effect_mult` 的合成层参与；
· 军队是条件加成（补缺口），调兵绝不劣于不调兵。
"""
import pytest

from application.game_init import new_game
from core.clerks import route_decree_mult
from core.decree_confirm import confirm_decree
from core.decree_effect import effect_channels
from core.minister_agent import ensure_actor


@pytest.fixture()
def state():
    return new_game("史实")


def test_clerks_mult_stays_pure_discount(state):
    """`clerks_mult` 必须**只**等于按路吏胥折扣（遵从度单列，不进这个读数）。"""
    route = "京东东路"
    res = effect_channels(state, kind="民政", route=route)
    expected = route_decree_mult(state, route)
    assert res["clerks_scope"] == f"按路（{route}）"
    if expected is not None:
        assert res["clerks_mult"] == pytest.approx(round(max(0.0, min(1.0, expected)), 4))
    assert "clerks_compliance" in res


def test_compliance_enters_composition_layer(state):
    """遵从度（若可算）必须体现在 `effect_mult`，而不是 `clerks_mult`。"""
    route = "京东东路"
    res = effect_channels(state, kind="民政", route=route)
    comp = res.get("clerks_compliance")
    if comp is None:
        pytest.skip("该路无在任知州读数，遵从度未计入（合法降级）")
    base = res["clerks_mult"] * res["civil_mult"]
    assert res["effect_mult"] == pytest.approx(round(min(2.0, base * comp["mult"]), 4), abs=1e-4)


def test_national_call_has_no_compliance_multiplier(state):
    res = effect_channels(state, kind="民政")
    assert res["clerks_scope"] == "全国"
    assert res["clerks_compliance"] is None
    assert res["strong"] == "clerks"


def test_army_enforce_never_worse(state):
    no_troops = effect_channels(state, kind="民政", enforce_troops=False)
    troops = effect_channels(state, kind="民政", enforce_troops=True)
    assert troops["effect_mult"] >= no_troops["effect_mult"]
    assert troops["military"]["enforced"] is True


def test_authority_gate_blocks_and_allows(state):
    """法统门禁：掌「官营放贷」事权者放行，谏官越权阻断。"""
    ensure_actor(state, "王古", authority=0.85)
    legal = {
        "id": "dec_legal_auth_1",
        "title": "行抵当法平抑息银",
        "effects": {"didang_loan_rate": 0.03},
        "addressees": ["王古"],
    }
    res_legal = confirm_decree(state, "dec_legal_auth_1", "王古", decree=legal, record=True)
    assert res_legal["status"] == "confirmed"
    assert res_legal["authorized"] is True

    ensure_actor(state, "陈瓘", authority=0.75)
    illegal = {
        "id": "dec_illegal_auth_1",
        "title": "令谏官管勾抵当所",
        "effects": {"didang_loan_rate": 0.03},
        "addressees": ["陈瓘"],
    }
    res_illegal = confirm_decree(state, "dec_illegal_auth_1", "陈瓘", decree=illegal, record=True)
    assert res_illegal["status"] == "unauthorized"
    assert res_illegal["authorized"] is False
    assert res_illegal["reason"] == "authority_violation"
