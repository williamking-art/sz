# -*- coding: utf-8 -*-
"""天道裁决引擎契约测试（P0 修复批 · 2026-10-17）。

覆盖本批修复的 6 个 P0 缺陷，每条断言都指向一个**曾经真实存在**的退化：
1. 薄桩只换类名不换签名 ⇒ 关键字 `state_context=` 打爆调用方；
2. 无依据 `gate` 撞阈值**放行**（`gate(None) → True`）；
3. 清廉度 `0.0` 被 `or 0.6` 吞掉 ⇒ 贪墨闸门**数学上永不通过**且非单调；
4. 国祚声望 `0` 被 `or 50.0` 吞掉；
5. `score` 两分支单调方向相反（灾情越重反而评"上考"）；
6. Softmax 舍入残差 ⇒ 概率和 0.9999，"严格归一"是假的；
7. 三个 `choose` 目标在引擎里**没有分支** ⇒ 恒定档位；`defiant` 永不可达。
"""
import math

import pytest

from core.ai.embedded_jev import EmbeddedJevEngine
from core.ai.tiandao_engine import TianDaoEngine


# =============================================================================
# 1. 签名向下兼容（薄桩必须连签名一起兼容）
# =============================================================================
def test_legacy_keyword_signature_still_works():
    """旧调用方按 `state_context=` 传参必须仍然可用（clerk/merchant_decision 走这条）。"""
    res = EmbeddedJevEngine.choose(
        state_context={"treasury": 8000},
        instructions="征管宽严倾向",
        criteria={"strict": 0.35, "moderate": 0.50, "lenient": 0.15},
    )
    assert res["provider"] == "tiandao_local"
    assert res["verdict"] in ("strict", "moderate", "lenient")

    gate_res = EmbeddedJevEngine.gate(
        state_context={"disaster": 0.9, "unrest": 80},
        condition="是否准予蠲免陈年逋欠",
    )
    assert gate_res["defined"] is True


def test_unknown_kwarg_rejected_loudly():
    """未知关键字要**报错**，不得静默吞掉（否则调用方以为生效）。"""
    with pytest.raises(TypeError):
        TianDaoEngine.choose(None, "x", {"corvee": 0.5, "hired": 0.5}, bogus=1)


def test_alias_is_same_object():
    assert EmbeddedJevEngine is TianDaoEngine


# =============================================================================
# 2. 无依据不得放行
# =============================================================================
def test_gate_without_basis_never_passes():
    for ctx in (None, {}, "  "):
        res = TianDaoEngine.gate(ctx, "是否存在雀鼠耗贪墨")
        assert res["verdict"] is False, f"无依据却放行：{ctx!r}"
        assert res["basis_undefined"] is True
        assert res["defined"] is False
        assert res["probability"] is None, "缺失值不得回落成概率数字"


def test_gate_with_basis_is_defined():
    res = TianDaoEngine.gate({"disaster": 0.9, "unrest": 80.0, "gov": {"integrity": 0.9}},
                             "是否准予蠲免")
    assert res["defined"] is True
    assert res["basis_undefined"] is False
    assert res["verdict"] is True
    # 0.30 + 0.315 + 0.20 + 0.18 = 0.995 ⇒ 引擎按契约钳到 [0.01, 0.99]
    assert res["probability"] == pytest.approx(0.99, abs=1e-6)


# =============================================================================
# 3. 贪墨闸门：可达 + 单调（旧实现 max 0.4455 < 阈值 0.5 ⇒ 恒 False）
# =============================================================================
def test_corruption_gate_reachable_and_monotonic():
    corrupt = TianDaoEngine.gate({"supervision": False, "gov": {"integrity": 0.0}},
                                 "是否存在雀鼠耗贪墨")
    honest = TianDaoEngine.gate({"supervision": False, "gov": {"integrity": 1.0}},
                                "是否存在雀鼠耗贪墨")
    assert corrupt["verdict"] is True, "最贪且无巡按竟判不贪 —— 闸门不可达"
    assert honest["verdict"] is False
    # 单调：清廉度越低，贪墨概率越高（旧式 `or 0.6` 会让 0.0 比 0.1 更低）
    probs = [TianDaoEngine.gate({"supervision": False, "gov": {"integrity": i / 10}},
                                "是否存在雀鼠耗贪墨")["probability"]
             for i in range(0, 11)]
    assert probs == sorted(probs, reverse=True), f"贪墨概率不随清廉度单调变化：{probs}"


def test_corruption_suppressed_by_inspector():
    no_insp = TianDaoEngine.gate({"supervision": False, "gov": {"integrity": 0.2}},
                                 "是否存在雀鼠耗贪墨")["probability"]
    with_insp = TianDaoEngine.gate({"supervision": True, "gov": {"integrity": 0.2}},
                                    "是否存在雀鼠耗贪墨")["probability"]
    assert with_insp < no_insp


# =============================================================================
# 4. `0` 是合法值：声望 0 不得被当成缺省 50
# =============================================================================
def test_zero_prestige_is_not_swallowed():
    zero = TianDaoEngine.gate({"prestige": 0}, "其他是非")["probability"]
    mid = TianDaoEngine.gate({"prestige": 50}, "其他是非")["probability"]
    high = TianDaoEngine.gate({"prestige": 100}, "其他是非")["probability"]
    assert zero < mid < high
    assert zero == pytest.approx(0.50, abs=1e-6), "声望 0 被回落到缺省 50（or 吞 0）"


# =============================================================================
# 5. score 单调方向唯一（levels 必须「差→好」）
# =============================================================================
def test_score_levels_are_worst_first():
    levels = ["下考", "中考", "上考"]
    good = TianDaoEngine.score({"tax_completion": 1.2, "unrest": 10.0,
                                "official_integrity": 0.9}, "考课", levels)
    bad = TianDaoEngine.score({"tax_completion": 0.4, "unrest": 75.0,
                               "official_integrity": 0.2}, "考课", levels)
    assert good["level"] == "上考" and bad["level"] == "下考"
    assert good["score"] > bad["score"]


def test_score_disaster_branch_agrees_with_direction():
    """通用灾情分支也必须"越糟越低分"（旧实现相反，灾情 1.0 反评上考）。"""
    levels = ["下考", "中考", "上考"]
    calm = TianDaoEngine.score({"disaster": 0.0, "unrest": 0}, "年景", levels)
    dire = TianDaoEngine.score({"disaster": 1.0, "unrest": 100}, "年景", levels)
    assert calm["score"] > dire["score"]
    assert dire["level"] == "下考"


def test_score_without_context_is_undefined():
    res = TianDaoEngine.score(None, "考课", ["下考", "中考", "上考"])
    assert res["defined"] is False
    assert res["score"] is None


# =============================================================================
# 6. Softmax 严格归一 + 确定性
# =============================================================================
def test_softmax_sums_to_one_exactly():
    for criteria in (
        {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4},
        {f"o{i}": i * 0.37 for i in range(6)},
        {"corvee": 0.5, "hired": 0.5},
    ):
        res = TianDaoEngine.choose({"treasury": 8000}, "x", criteria)
        assert math.isclose(sum(res["probabilities"].values()), 1.0, abs_tol=1e-9), \
            f"概率和未归一：{res['probabilities']}"


def test_dice_deterministic_and_bounded():
    d1 = TianDaoEngine.dice(12345, 0.08)
    assert d1 == TianDaoEngine.dice(12345, 0.08)
    assert -0.08 <= d1 <= 0.08
    # 相邻种子的微扰必须**不相关**（旧 LCG 单轮实测相邻对差恒为 0.063269）
    seq = [TianDaoEngine.dice(n, 1.0) for n in range(1, 21)]
    diffs = [abs(seq[i + 1] - seq[i]) for i in range(len(seq) - 1)]
    assert max(diffs) > 0.1, f"相邻种子输出几乎相同（锯齿周期）：{seq[:6]}"
    assert len({round(v, 5) for v in seq}) == len(seq), "种子映射有碰撞"


# =============================================================================
# 7. 四个"没有分支 ⇒ 恒定档位"的抉择
# =============================================================================
def test_farmer_path_is_not_constant():
    calm = TianDaoEngine.choose({"debt": 0}, "破产小农", {"mortgage_land": 0.70,
                                                        "flee_refugee": 0.30},
                                objective="farmer_path")["verdict"]
    dire = TianDaoEngine.choose({"debt": 5000, "disaster": 1.0, "unrest": 90},
                                "破产小农", {"mortgage_land": 0.70, "flee_refugee": 0.30},
                                objective="farmer_path")["verdict"]
    assert calm == "mortgage_land"
    assert dire == "flee_refugee"


def test_gentry_path_is_not_constant():
    calm = TianDaoEngine.choose({"unrest": 10}, "士绅", {"charity_relief": 0.40,
                                                       "usury_annex": 0.60},
                                objective="gentry_path")["verdict"]
    famine = TianDaoEngine.choose({"disaster": 1.0, "unrest": 80}, "士绅",
                                  {"charity_relief": 0.40, "usury_annex": 0.60},
                                  objective="gentry_path")["verdict"]
    assert calm == "usury_annex"
    assert famine == "charity_relief"


def test_canal_reroute_is_not_constant():
    clear = TianDaoEngine.choose({"block_rate": 5}, "漕运",
                                 {"wait_dredge": 0.45, "overland_cart": 0.35,
                                  "borrow_grain": 0.20}, objective="canal_reroute")["verdict"]
    blocked = TianDaoEngine.choose({"block_rate": 95}, "漕运",
                                   {"wait_dredge": 0.45, "overland_cart": 0.35,
                                    "borrow_grain": 0.20}, objective="canal_reroute")["verdict"]
    assert clear == "wait_dredge"
    assert blocked in ("overland_cart", "borrow_grain")


def test_defiant_compliance_reachable():
    """四类遵从反应必须**都能被裁决出来**（旧实现 defiant 无偏置 ⇒ 永不出现）。"""
    res = TianDaoEngine.choose({"gov": {"integrity": 0.0}, "treasury": 0.0, "unrest": 95},
                               "路级遵从",
                               {"vigorous": 0.25, "compliant": 0.50,
                                "passive": 0.20, "defiant": 0.05},
                               objective="decree_compliance")
    assert res["verdict"] == "defiant"


# =============================================================================
# 8. 劳役抉择：读真实财力键、缺失不冒充"没钱"
# =============================================================================
def test_labor_policy_uses_real_treasury_key():
    hired = TianDaoEngine.choose({"treasury": 8000}, "劳役",
                                 {"corvee": 0.5, "hired": 0.5},
                                 objective="labor_policy")["verdict"]
    corvee = TianDaoEngine.choose({"local_treasury": 200}, "劳役",
                                  {"corvee": 0.5, "hired": 0.5},
                                  objective="labor_policy")["verdict"]
    assert hired == "hired"
    assert corvee == "corvee"


def test_labor_policy_missing_treasury_adds_no_bias():
    res = TianDaoEngine.choose({}, "劳役", {"corvee": 0.5, "hired": 0.5},
                               objective="labor_policy")
    probs = res["probabilities"]
    assert probs["corvee"] == pytest.approx(probs["hired"], abs=1e-6), \
        "缺失财力不得被当成『没钱』（旧实现恒判差役）"
