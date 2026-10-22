# -*- coding: utf-8 -*-
"""内嵌决策引擎/门面的**向下兼容**契约测试（原 `embedded_*` 名称与签名）。

历史：这两模块已升级为 `TianDaoEngine` / `TianDaoFacade`，本文件锁定
① 旧类名仍可 import；② `provider` 契约值为 `tiandao_local`（2026-10-17 重命名，
全库无生产消费方；Jev 裁定 p=0.994）；③ 生产调用方用的**关键字签名**仍然可用。

⚠️ 旧版三条断言是"枚举成员/恒真"式的（`x in ("a","b")`、`verdict is False or prob>0.3`），
对任何实现恒真，正是它让"门面恒定档位"瞒过全量回归。现改为**带方向**的断言。
"""
import pytest

from core.ai.decision_facade import EmbeddedDecisionFacade
from core.ai.embedded_jev import EmbeddedJevEngine


def test_provider_contract_value():
    res = EmbeddedJevEngine.gate({"disaster": 0.9, "unrest": 80.0}, "是否准予蠲免")
    assert res["provider"] == "tiandao_local"
    assert res["probability"] > 0.60
    assert res["verdict"] is True

    choose_res = EmbeddedJevEngine.choose(
        {"treasury": 1_500_000, "monthly_expense": 400_000}, "劳役政策",
        {"corvee": 0.5, "hired": 0.5})
    assert choose_res["provider"] == "tiandao_local"
    assert choose_res["verdict"] == "hired"


def test_legacy_keyword_arguments_still_accepted():
    """`clerk_decision` / `merchant_decision` 用 `state_context=` 关键字调用。"""
    res = EmbeddedJevEngine.choose(
        state_context={"treasury": 1_500_000, "monthly_expense": 400_000},
        instructions="劳役政策",
        criteria={"corvee": 0.5, "hired": 0.5},
    )
    assert res["verdict"] == "hired"


def test_corruption_gate_is_decidable():
    """旧断言 `verdict is False or prob > 0.30` 恒真 ⇒ 什么都没测。"""
    corrupt = EmbeddedJevEngine.gate(
        {"supervision": False, "gov": {"integrity": 0.1}}, "是否存在雀鼠耗贪墨")
    honest = EmbeddedJevEngine.gate(
        {"supervision": True, "gov": {"integrity": 0.95}}, "是否存在雀鼠耗贪墨")
    assert corrupt["verdict"] is True
    assert corrupt["probability"] > honest["probability"]
    assert honest["verdict"] is False


# =============================================================================
# 门面六域：每条断言都带方向（不再只断言"落在枚举里"）
# =============================================================================
def test_facade_fiscal_domain():
    stance = EmbeddedDecisionFacade.tax_collection_stance(
        {"disaster": 0.9, "unrest": 80, "gov": {"integrity": 0.9}})
    assert stance in ("strict", "moderate", "lenient")
    waive = EmbeddedDecisionFacade.should_waive_ancient_arrears(
        {"disaster": 0.9, "unrest": 90.0})
    assert waive is True


def test_facade_market_domain():
    ship = EmbeddedDecisionFacade.merchant_trade_or_hoard({"gap": 3.0, "disaster": 0.1})
    assert ship == "ship"
    open_gate = EmbeddedDecisionFacade.changping_intervene_gate(
        {"price_ratio": 1.9, "stock": 50000})
    assert open_gate is True
    closed_gate = EmbeddedDecisionFacade.changping_intervene_gate(
        {"price_ratio": 1.1, "stock": 50000})
    assert closed_gate is False


def test_facade_logistics_domain():
    # 旧断言用 8000/200 贯，量纲比真实路库低 2 个数量级，且会把 corvee 分支夹成死分支；
    # 2026-10-21 L1 参数外置后改按真实量纲（路库 27万~195万贯；月支 40 万 ⇒ 3 个月线）。
    assert EmbeddedDecisionFacade.labor_service_policy(
        {"treasury": 1_500_000, "monthly_expense": 400_000}) == "hired"
    assert EmbeddedDecisionFacade.labor_service_policy(
        {"treasury": 300_000, "monthly_expense": 400_000}) == "corvee"
    blocked = EmbeddedDecisionFacade.canal_reroute_choice({"block_rate": 95})
    assert blocked in ("overland_cart", "borrow_grain")


def test_facade_social_domain():
    assert EmbeddedDecisionFacade.farmer_destitution_path(
        {"debt": 5000, "disaster": 1.0, "unrest": 90}) == "flee_refugee"
    assert EmbeddedDecisionFacade.gentry_charity_vs_annex(
        {"disaster": 1.0, "unrest": 80}) == "charity_relief"


def test_facade_governance_domain():
    assert EmbeddedDecisionFacade.reform_compliance_gate(
        {"faction": "新党", "gov": {"diligence": 0.9}, "prestige": 80}) is True
    assert EmbeddedDecisionFacade.reform_compliance_gate(
        {"faction": "旧党", "gov": {"diligence": 0.1}, "prestige": 0}) is False


def test_facade_military_domain():
    assert EmbeddedDecisionFacade.recruit_refugees_to_soldiers_gate(
        {"refugees": 8000, "unrest": 60}) is True
    assert EmbeddedDecisionFacade.recruit_refugees_to_soldiers_gate(
        {"refugees": 0, "unrest": 0}) is False


def test_facade_without_basis_is_conservative():
    """门面方法拿不到任何读数时不得凭空判"是"。"""
    assert EmbeddedDecisionFacade.granary_corruption_check({}) is False
    assert EmbeddedDecisionFacade.should_waive_ancient_arrears({}) is False
    assert EmbeddedDecisionFacade.changping_intervene_gate({}) is False
