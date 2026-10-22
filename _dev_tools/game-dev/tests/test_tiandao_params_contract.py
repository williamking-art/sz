# -*- coding: utf-8 -*-
"""天道引擎「参数外置」契约测试（L1-a · 2026-10-21）。

本文件锁的是**外置这件事本身**，不是某个数值：
1. 参数表可导入、规模够、**每个参数都有口径注释**（扫源码逐行断言）；
2. **外置真生效**：14 个参数组各取一个参数，改参数 ⇒ 引擎输出必须跟着变
   （防止"把常数搬进一个没人读的模块"这种假外置 / 死参数）；
3. B1 `score` 运算符优先级 + 缺失不得冒充满分；
4. B2 `granary_corruption` 无依据不得判贪墨；
5. B3 `labor_policy` 真实量纲（月数 / 路库量级绝对线）；
6. B4 未知 objective fail-closed（且旧式无 objective 调用仍可用）；
7. 纯函数：不读写 state-like 对象、不改入参 dict、零第三方依赖 / 不联网。

数值口径为什么是这些值，见 `game/content/data_tiandao.py` 每个字段的行尾注释；
本文件只断言"行为按参数表走"。
"""
import ast
import copy
import dataclasses
import inspect
import pathlib

import pytest

import core.ai.tiandao_engine as engine_module
from content.data_tiandao import (
    PARAMS, TianDaoParams, param_count, param_names,
)
from core.ai.tiandao_engine import CHOOSE_OBJECTIVES, GATE_OBJECTIVES, TianDaoEngine

_LEVELS = ("下考", "中考", "上考")

#: 参数表必须覆盖的 14 个 objective 分组前缀（任务 A 的分组契约）
REQUIRED_GROUPS = (
    "WAIVE_", "CHANGPING_", "CORRUPTION_", "REFUGEES_", "REFORM_", "GENERIC_",
    "TAX_", "LABOR_", "MERCHANT_", "DECREE_", "FARMER_", "GENTRY_", "CANAL_",
    "SCORE_",
)


# =============================================================================
# 1. 参数表本身：可导入 / 规模 / 每个参数有口径注释 / 分组齐全
# =============================================================================
def test_params_module_is_importable_and_large_enough():
    assert isinstance(PARAMS, TianDaoParams)
    assert param_count() >= 40, f"参数表只有 {param_count()} 项，外置不彻底"
    assert len(param_names()) == len(set(param_names())), "参数名重复"
    # 冻结：静态数据不得在运行期被就地改写（改参数只能用 replace 克隆）
    with pytest.raises(dataclasses.FrozenInstanceError):
        PARAMS.UNIT_SCALE = 2.0  # type: ignore[misc]


def test_every_param_group_is_present():
    names = param_names()
    missing = [g for g in REQUIRED_GROUPS if not any(n.startswith(g) for n in names)]
    assert not missing, f"缺少参数分组：{missing}"


def test_every_param_has_a_caliber_comment_in_source():
    """每个字段行必须带 `#` 注释写明口径（审计要求：不写口径 = 没交付）。"""
    src_path = pathlib.Path(
        engine_module.__file__).resolve().parents[2] / "content" / "data_tiandao.py"
    lines = src_path.read_text(encoding="utf-8").splitlines()
    field_lines = {}
    for line in lines:
        stripped = line.strip()
        # dataclass 字段形如 `NAME: type = value  # 口径：…`
        if not line.startswith("    ") or line.startswith("     ") or ":" not in stripped:
            continue
        head = stripped.split(":", 1)[0]
        if head.isupper() and head.replace("_", "").replace("0", "").isalpha():
            field_lines[head] = line
    assert set(field_lines) == set(param_names()), (
        "参数表源码字段与 dataclass 字段不一致："
        f"源码多={sorted(set(field_lines) - set(param_names()))} "
        f"源码少={sorted(set(param_names()) - set(field_lines))}")
    without_comment = [n for n, line in field_lines.items() if "#" not in line]
    assert not without_comment, f"这些参数没有口径注释：{without_comment}"
    assert "口径" in src_path.read_text(encoding="utf-8"), "参数表缺少「口径」说明文字"


def test_audit_flagged_params_are_marked_for_calibration():
    """审计认定为"随手拍 / 两处不一致"的参数必须带 `# 待校准` 标记。"""
    src = pathlib.Path(
        engine_module.__file__).resolve().parents[2] / "content" / "data_tiandao.py"
    text = src.read_text(encoding="utf-8")
    lines = {ln.split(":", 1)[0].strip(): ln for ln in text.splitlines()
             if ln.startswith("    ") and ":" in ln}
    flagged = [n for n in ("LABOR_ABSOLUTE_TREASURY", "MERCHANT_DISASTER_LINE",
                           "PRESTIGE_NEUTRAL", "SCORE_INTEGRITY_NEUTRAL")
               if "待校准" not in lines.get(n, "")]
    assert not flagged, f"审计点名的参数未标 `# 待校准`：{flagged}"
    assert text.count("待校准") >= 8, "待校准标记数量过少（审计认定的随手拍不止 8 处？请复核）"


# =============================================================================
# 2. 外置真生效（不是死参数）：每个分组各取一个参数，改参数 ⇒ 输出必须变
# =============================================================================
def _gate_prob(ctx, objective):
    return TianDaoEngine.gate(ctx, objective=objective)["probability"]


def _choose_prob(ctx, objective, option, criteria=None):
    base = criteria or {"corvee": 0.5, "hired": 0.5}
    return TianDaoEngine.choose(ctx, "", dict(base), objective=objective)["probabilities"][option]


#: (参数名, 覆盖值, 探针) —— 一行一个分组，确保 14 个 objective 组都有"活参数"证据
LIVE_PARAM_CASES = (
    ("WAIVE_BASE", 0.90,
     lambda: _gate_prob({"disaster": 0.0, "unrest": 0.0}, "waive_arrears")),
    ("CHANGPING_PRICE_TERM_MAX", 0.10,
     lambda: _gate_prob({"stock": 1000, "price_ratio": 3.0}, "changping_open")),
    ("CORRUPTION_SLOPE", 0.10,
     lambda: _gate_prob({"gov": {"integrity": 0.0}, "supervision": False},
                        "granary_corruption")),
    ("REFUGEES_FULL_MARK", 25000.0,
     lambda: _gate_prob({"refugees": 2500, "unrest": 0.0}, "recruit_refugees")),
    ("REFORM_BASE", 0.90,
     lambda: _gate_prob({"prestige": 0, "gov": {"diligence": 0.0}, "faction": ""},
                        "reform_compliance")),
    ("GENERIC_BASE", 0.90,
     lambda: _gate_prob({"prestige": 50}, "generic")),
    ("TAX_STRICT_BUMP", 2.0,
     lambda: _choose_prob({"gov": {"integrity": 0.2}}, "tax_stance", "strict",
                          {"strict": 0.35, "moderate": 0.50, "lenient": 0.15})),
    ("LABOR_HIRED_BIAS", 3.0,
     lambda: _choose_prob({"treasury": 1_500_000, "monthly_expense": 400_000},
                          "labor_policy", "hired")),
    ("MERCHANT_HOARD_BUMP", 3.0,
     lambda: _choose_prob({"disaster": 1.0}, "merchant_trade", "hoard",
                          {"ship": 0.40, "hoard": 0.35, "local_sell": 0.25})),
    ("DECREE_DEFIANT_CORRUPT_W", 3.0,
     lambda: _choose_prob({"gov": {"integrity": 0.0}, "treasury": 0.0, "unrest": 95},
                          "decree_compliance", "defiant",
                          {"vigorous": 0.25, "compliant": 0.50,
                           "passive": 0.20, "defiant": 0.05})),
    ("FARMER_DEBT_SLOPE", 1.5,
     lambda: _choose_prob({"debt": 1000}, "farmer_path", "flee_refugee",
                          {"mortgage_land": 0.70, "flee_refugee": 0.30})),
    ("GENTRY_DISASTER_CHARITY_BUMP", 3.0,
     lambda: _choose_prob({"disaster": 1.0}, "gentry_path", "charity_relief",
                          {"charity_relief": 0.40, "usury_annex": 0.60})),
    ("CANAL_OVERLAND_SLOPE", 3.0,
     lambda: _choose_prob({"block_rate": 50}, "canal_reroute", "overland_cart",
                          {"wait_dredge": 0.45, "overland_cart": 0.35,
                           "borrow_grain": 0.20})),
    ("SCORE_PEACE_W", 0.60,
     lambda: TianDaoEngine.score(
         {"tax_completion": 0.6, "unrest": 20.0, "official_integrity": 0.5},
         "考课", _LEVELS)["score"]),
)


@pytest.mark.parametrize("param_name,override,probe", LIVE_PARAM_CASES,
                         ids=[c[0] for c in LIVE_PARAM_CASES])
def test_param_change_moves_engine_output(monkeypatch, param_name, override, probe):
    """参数改掉后引擎输出**必须**跟着变——否则就是"搬进模块但没人读"的死参数。"""
    before = probe()
    monkeypatch.setattr(engine_module, "PARAMS",
                        dataclasses.replace(PARAMS, **{param_name: override}))
    after = probe()
    assert before != after, f"改 {param_name}={override} 后输出仍为 {before!r} ⇒ 死参数（外置未接线）"
    # 参数已还原（monkeypatch 自动回滚），再确认一次基线未漂移
    monkeypatch.undo()
    assert probe() == before


def test_param_table_is_the_only_entry_for_threshold_default():
    """gate 的 `threshold` 默认值必须与参数表登记的一致（签名不能改，故此处守护一致性）。"""
    sig = inspect.signature(TianDaoEngine.gate)
    assert sig.parameters["threshold"].default == PARAMS.GENERIC_THRESHOLD
    assert inspect.signature(TianDaoEngine.choose).parameters["temperature"].default \
        == PARAMS.CHOOSE_TEMPERATURE


# =============================================================================
# 3. B1：score 运算符优先级 + 缺失不得冒充满分
# =============================================================================
def test_score_with_nothing_is_undefined_not_perfect():
    """旧实测：`score({})` = 上考 1.0（缺失被当成"完美年景"）。"""
    res = TianDaoEngine.score({}, "年景", _LEVELS)
    assert res["defined"] is False
    assert res["score"] is None, "缺失不得回落成满分 1.0"
    assert res["level"] == ""


def test_score_unrest_is_not_dropped_when_disaster_missing():
    """旧运算符优先级 bug：`disaster is None` 时整项 unrest 被丢弃 ⇒ 民怨 160 仍评上考。

    旧实测：`score({"unrest":160})` = 上考 1.0（应为最差 0.0）。
    """
    res = TianDaoEngine.score({"unrest": 160}, "年景", _LEVELS)
    assert res["defined"] is True
    assert res["score"] < 0.5, f"民怨 160 却给了 {res['score']}（unrest 又被丢了？）"
    assert res["score"] == pytest.approx(0.0, abs=1e-6)
    assert res["level"] == "下考"


def test_score_averages_available_items_only():
    """两项都在 ⇒ 按可用项平均：灾情 0.0 与民怨 100% 各占一半 ⇒ 0.5。"""
    res = TianDaoEngine.score({"disaster": 0.0, "unrest": 100}, "年景", _LEVELS)
    assert res["score"] == pytest.approx(0.5, abs=1e-6)
    # 单项时不得再除以 2（旧式攒 0.0 占位再 /2 ⇒ 单项 0.0 会被算成 0.5）
    only_disaster = TianDaoEngine.score({"disaster": 0.0}, "年景", _LEVELS)
    assert only_disaster["score"] == pytest.approx(1.0, abs=1e-6)


def test_score_appraisal_without_tax_completion_is_undefined():
    """旧缺省 `tax_completion = 1.0`（"缺失=赋税完美"）⇒ 缺数据也评上考；现必须 undefined。"""
    res = TianDaoEngine.score({"official_integrity": 0.9}, "考课", _LEVELS)
    assert res["defined"] is False
    assert res["score"] is None


# =============================================================================
# 4. B2：granary_corruption 无依据不得判贪墨
# =============================================================================
def test_granary_corruption_without_integrity_is_undefined():
    """旧实测：`gate({"unrest":10}, objective="granary_corruption")` ⇒ prob=0.5 / verdict=True。

    危险方向：缺清廉度数据反而**判贪墨**（0.20+0.60*0.5 恰好撞 0.5 阈值）。
    """
    res = TianDaoEngine.gate({"unrest": 10}, objective="granary_corruption")
    assert res["defined"] is False
    assert res["probability"] is None
    assert res["verdict"] is False
    # 门面 bool 化后的消费口径（`granary_corruption_check` 取 ["verdict"]）也必须是"不判贪墨"
    assert TianDaoEngine.gate({"unrest": 10},
                              "是否存在雀鼠耗贪墨")["verdict"] is False


def test_granary_corruption_still_reachable_with_integrity():
    """B2 只去掉"缺依据"的判定，不得把闸门整体关掉（可达性 + 单调性 + 巡按压制仍要成立）。"""
    corrupt = TianDaoEngine.gate({"gov": {"integrity": 0.0}, "supervision": False},
                                 objective="granary_corruption")
    honest = TianDaoEngine.gate({"gov": {"integrity": 1.0}, "supervision": False},
                                objective="granary_corruption")
    suppressed = TianDaoEngine.gate({"gov": {"integrity": 0.0}, "supervision": True},
                                    objective="granary_corruption")
    assert corrupt["defined"] is True and corrupt["verdict"] is True
    assert honest["verdict"] is False
    assert suppressed["probability"] < corrupt["probability"], "巡按压制项被 B2 弄丢了"


# =============================================================================
# 5. B3：labor_policy 真实量纲（旧 treasury>=5000 比真实量级低 3 个数量级）
# =============================================================================
@pytest.mark.parametrize("ctx,expected", [
    ({"treasury": 1_500_000, "monthly_expense": 400_000}, "hired"),    # 3.75 个月
    ({"treasury": 300_000, "monthly_expense": 400_000}, "corvee"),     # 0.75 个月
    ({"local_treasury": 1_100_000, "monthly_expense": 400_000}, "corvee"),  # 2.75 个月（且走 local_treasury 键）
])
def test_labor_policy_real_scale_verdicts(ctx, expected):
    res = TianDaoEngine.choose(ctx, "劳役", {"corvee": 0.5, "hired": 0.5},
                               objective="labor_policy")
    assert res["verdict"] == expected, f"{ctx} ⇒ {res['probabilities']}"


def test_labor_policy_month_threshold_is_exactly_three_months():
    """边界口径：恰好 3.0 个月 ⇒ hired（`>= LABOR_HIRED_MIN_MONTHS`）。"""
    exact = TianDaoEngine.choose({"treasury": 1_200_000, "monthly_expense": 400_000},
                                 "劳役", {"corvee": 0.5, "hired": 0.5},
                                 objective="labor_policy")["verdict"]
    just_under = TianDaoEngine.choose({"treasury": 1_199_000, "monthly_expense": 400_000},
                                      "劳役", {"corvee": 0.5, "hired": 0.5},
                                      objective="labor_policy")["verdict"]
    assert exact == "hired"
    assert just_under == "corvee"


def test_labor_policy_absolute_fallback_uses_real_magnitude():
    """无月支出读数 ⇒ 用**路库见底线**（200,000 贯；Jev A 0.742）；
    旧 5,000 在这个量级下等于恒 hired（corvee 死分支），100 万≈路库中位又会让差役成常态。"""
    assert TianDaoEngine.choose({"treasury": 1_000_000}, "劳役",
                                {"corvee": 0.5, "hired": 0.5},
                                objective="labor_policy")["verdict"] == "hired"
    assert TianDaoEngine.choose({"local_treasury": 150_000}, "劳役",
                                {"corvee": 0.5, "hired": 0.5},
                                objective="labor_policy")["verdict"] == "corvee"


def test_labor_policy_zero_monthly_expense_falls_back_to_absolute():
    """`monthly_expense = 0` 是无效读数（不得当真去比较）⇒ 退绝对线。"""
    assert TianDaoEngine.choose({"treasury": 150_000, "monthly_expense": 0},
                                "劳役", {"corvee": 0.5, "hired": 0.5},
                                objective="labor_policy")["verdict"] == "corvee"


# =============================================================================
# 6. B4：未知 objective fail-closed（旧式无 objective 路径必须保留）
# =============================================================================
def test_unknown_gate_objective_fails_closed():
    """旧实测：`gate({"prestige":55}, objective="no_such_objective")` ⇒ defined=True / verdict=True。"""
    res = TianDaoEngine.gate({"prestige": 55}, objective="no_such_objective")
    assert res["defined"] is False
    assert res["probability"] is None
    assert res["verdict"] is False
    assert res["objective"] == "no_such_objective"


def test_unknown_choose_objective_fails_closed():
    res = TianDaoEngine.choose({"treasury": 1}, "x", {"a": 1.0, "b": 1.0},
                               objective="no_such_objective")
    assert res["defined"] is False
    assert res["probabilities"] == {}
    assert res["verdict"] == ""


def test_cross_mode_objective_is_also_fail_closed():
    """gate 里传 choose 类 objective（模式错挂）同样必须 fail-closed，不得静默走 generic。"""
    assert TianDaoEngine.gate({"prestige": 55},
                              objective=CHOOSE_OBJECTIVES[0])["defined"] is False
    assert TianDaoEngine.choose({"treasury": 1}, "", {"a": 1.0, "b": 1.0},
                                objective=GATE_OBJECTIVES[0])["defined"] is False


def test_legacy_inference_paths_still_work():
    """向后兼容：**未给** objective 时仍按旧文案 / 旧 criteria 键名推断（clerk / merchant 依赖）。"""
    by_text = TianDaoEngine.gate({"disaster": 0.9, "unrest": 80}, "是否准予蠲免陈年逋欠")
    assert by_text["defined"] is True
    assert by_text["objective"] == "waive_arrears"

    by_keys = TianDaoEngine.choose({"treasury": 1_500_000}, "劳役制度选择",
                                    {"corvee": 0.5, "hired": 0.5})
    assert by_keys["defined"] is True
    assert by_keys["objective"] == "labor_policy"
    assert by_keys["verdict"] == "hired"

    # 推断不出目标（任意 option id）时仍做基础 Softmax，不得因 B4 变成 fail-closed
    generic = TianDaoEngine.choose(None, "x", {"a": 0.1, "b": 0.2, "c": 0.3})
    assert generic["defined"] is True
    assert generic["objective"] == ""


# =============================================================================
# 7. 纯函数：不读写 state-like 对象、不改入参、零第三方依赖
# =============================================================================
class _TripwireState:
    """记录一切属性读写的桩对象：引擎若按属性读 / 写 state，这里会留痕。"""

    def __init__(self) -> None:
        object.__setattr__(self, "reads", [])
        object.__setattr__(self, "writes", [])

    def __getattr__(self, name):
        object.__getattribute__(self, "reads").append(name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        object.__getattribute__(self, "writes").append(name)
        object.__setattr__(self, name, value)


def test_engine_never_touches_state_like_objects():
    """纯函数契约：引擎不按属性读 state、更不写 state（桩对象上零读写 = 零副作用）。"""
    stub = _TripwireState()
    engine_calls = (
        lambda: TianDaoEngine.gate(stub, "是否准予蠲免"),
        lambda: TianDaoEngine.gate(stub, objective="granary_corruption"),
        lambda: TianDaoEngine.choose(stub, "劳役", {"corvee": 0.5, "hired": 0.5}),
        lambda: TianDaoEngine.choose(stub, "x", {"a": 1.0, "b": 1.0},
                                     objective="no_such_objective"),
        lambda: TianDaoEngine.score(stub, "考课", _LEVELS),
        lambda: TianDaoEngine.dice(7, 0.1),
    )
    for call in engine_calls:
        call()
    assert stub.reads == [], f"引擎按属性读了 state：{stub.reads}"
    assert stub.writes == [], f"引擎写了 state：{stub.writes}"


def test_engine_does_not_mutate_context_dict():
    """入参 dict（含嵌套 gov）在调用前后必须完全一致；同一入参重复调用结果必须相同。"""
    ctx = {"disaster": 0.7, "unrest": 55.0, "treasury": 1_500_000,
           "monthly_expense": 400_000, "price_ratio": 1.8, "stock": 20000,
           "refugees": 4000, "gov": {"integrity": 0.3, "diligence": 0.8},
           "supervision": False, "faction": "旧党", "prestige": 42, "debt": 800,
           "block_rate": 70, "gap": 1.5}
    snapshot = copy.deepcopy(ctx)
    criteria = {"corvee": 0.5, "hired": 0.5}
    criteria_snapshot = dict(criteria)

    results = (
        TianDaoEngine.gate(ctx, objective="waive_arrears"),
        TianDaoEngine.gate(ctx, objective="granary_corruption"),
        TianDaoEngine.gate(ctx, objective="reform_compliance"),
        TianDaoEngine.choose(ctx, "", dict(criteria), objective="labor_policy"),
        TianDaoEngine.choose(ctx, "", dict(criteria), objective="decree_compliance"),
        TianDaoEngine.score(ctx, "考课", _LEVELS),
    )
    assert ctx == snapshot, "引擎改写了入参 dict"
    assert criteria == criteria_snapshot, "引擎改写了 criteria dict"

    # 确定性：同一入参再跑一遍，结果必须逐字段相同
    again = (
        TianDaoEngine.gate(ctx, objective="waive_arrears"),
        TianDaoEngine.gate(ctx, objective="granary_corruption"),
        TianDaoEngine.gate(ctx, objective="reform_compliance"),
        TianDaoEngine.choose(ctx, "", dict(criteria), objective="labor_policy"),
        TianDaoEngine.choose(ctx, "", dict(criteria), objective="decree_compliance"),
        TianDaoEngine.score(ctx, "考课", _LEVELS),
    )
    assert results == again, "同一入参两次结果不同（非确定性）"


def test_engine_has_no_third_party_or_network_imports():
    """零第三方依赖 / 不联网：引擎模块的 import 必须只有标准库 math/typing + 参数表。"""
    tree = ast.parse(pathlib.Path(engine_module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    allowed = {"__future__", "math", "typing", "content.data_tiandao"}
    assert imported <= allowed, f"引擎引入了新的外部依赖：{sorted(imported - allowed)}"


def test_engine_signatures_are_unchanged():
    """对外签名一个字都不许改（首参兼容、gate/choose/score/dice 参数名与默认值）。"""
    expected = {
        "gate": (["context", "condition", "threshold", "objective", "kwargs"],
                 {"context": None, "condition": "", "threshold": 0.50,
                  "objective": None}),
        "choose": (["context", "instructions", "criteria", "temperature",
                    "objective", "kwargs"],
                   {"context": None, "instructions": "", "criteria": None,
                    "temperature": 0.8, "objective": None}),
        "score": (["context", "instructions", "levels", "kwargs"],
                  {"context": None, "instructions": "", "levels": ()}),
        "dice": (["seed", "entropy"], {"entropy": 0.05}),
    }
    for name, (param_names_expected, defaults) in expected.items():
        sig = inspect.signature(getattr(TianDaoEngine, name))
        assert list(sig.parameters) == param_names_expected, f"{name} 参数表被改了"
        for key, value in defaults.items():
            assert sig.parameters[key].default == value, f"{name}.{key} 默认值被改了"


def test_legacy_state_context_keyword_still_accepted():
    """`state_context=` 旧关键字兼容（clerk_decision / merchant_decision 走这条）。"""
    res = TianDaoEngine.gate(state_context={"disaster": 0.9, "unrest": 80},
                             condition="是否准予蠲免")
    assert res["defined"] is True
    with pytest.raises(TypeError):
        TianDaoEngine.gate({"disaster": 0.9}, "x", bogus=1)
