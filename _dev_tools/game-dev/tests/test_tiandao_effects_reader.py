# -*- coding: utf-8 -*-
"""天道裁决 → 数值效果：共享读取点契约测试（2026-10-21 接线批）。

钉死三条最容易退化的语义：
1. **缺失 ≠ False ≠ 默认档位**：无观测副本 / 无该门面 ⇒ `None`，调用方据此中性处理；
   而 `False` 是**真裁决**，必须与缺失区分（旧式 `bool(x)` 会把两者混为一谈）。
2. **白名单**：不在 `allowed` 里的值一律 `None`（改一个选项名不得静默改判定）。
3. **错误结构不冒充裁决**：门面失败时记录可能是 dict（`{"error": ...}`），不得当值用。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.ai.tiandao_effects import (  # noqa: E402
    gate_intensity, jitter, observe_bool, observe_mix, observe_strength,
    observe_verdict, observed_names,
)


class _S:
    """最小 state 桩（只带 `_tiandao_observe` 一个属性）。"""


def test_missing_record_is_none_not_false():
    s = _S()
    assert observe_verdict(s, "canal_reroute_choice", ("a", "b")) is None
    assert observe_bool(s, "recruit_refugees_to_soldiers_gate") is None
    assert observed_names(s) == ()


def test_false_verdict_is_distinguishable_from_missing():
    s = _S()
    s._tiandao_observe = {"decisions": {"gate": False}}
    assert observe_bool(s, "gate") is False          # 真裁决
    assert observe_bool(s, "absent") is None         # 缺失
    assert observe_bool(s, "gate") is not observe_bool(s, "absent")


def test_whitelist_rejects_unknown_option():
    s = _S()
    s._tiandao_observe = {"decisions": {"d": "wait_dredge", "e": "renamed_option"}}
    assert observe_verdict(s, "d", ("wait_dredge", "overland_cart")) == "wait_dredge"
    assert observe_verdict(s, "e", ("wait_dredge", "overland_cart")) is None


def test_error_shape_never_masquerades_as_verdict():
    s = _S()
    s._tiandao_observe = {"decisions": {"d": {"error": "ValueError"}}}
    assert observe_verdict(s, "d", ("x",)) is None
    assert observe_bool(s, "d") is None


def test_non_dict_record_and_non_dict_decisions_are_none():
    for bad in (None, [], "x", 3, {"decisions": "x"}, {"decisions": []}):
        s = _S()
        s._tiandao_observe = bad
        assert observe_verdict(s, "d", ("x",)) is None, bad
        assert observe_bool(s, "d") is None, bad


def test_allowed_must_be_nonempty_tuple():
    s = _S()
    with pytest.raises(ValueError):
        observe_verdict(s, "d", ())
    with pytest.raises(ValueError):
        observe_verdict(s, "d", ["x"])  # type: ignore[arg-type]


def test_module_is_read_only():
    """读取点不得写 state：调用前后属性与原始值不变。"""
    s = _S()
    s._tiandao_observe = {"decisions": {"d": "x", "g": True}}
    before = id(s._tiandao_observe), dict(s._tiandao_observe["decisions"])
    observe_verdict(s, "d", ("x",))
    observe_bool(s, "g")
    observed_names(s)
    after = id(s._tiandao_observe), dict(s._tiandao_observe["decisions"])
    assert before == after


# ---------------------------------------------------------------------------
# 强度 / 分布 / 天意机变（2026-10-22 概率加权契约）
# ---------------------------------------------------------------------------
def test_gate_intensity_is_superthreshold_and_monotonic():
    """刚过线≈0、逼近 1→1；低于阈值一律 0；缺失 ⇒ None。"""
    assert gate_intensity(None) is None
    assert gate_intensity(float("nan")) is None
    assert gate_intensity(0.40, 0.5) == 0.0
    vals = [gate_intensity(p, 0.5) for p in (0.51, 0.60, 0.75, 0.90, 0.99)]
    assert vals == sorted(vals)
    assert abs(vals[0] - 0.02) < 1e-9 and abs(vals[-1] - 0.98) < 1e-9


def test_observe_strength_reads_gate_probability():
    s = _S()
    s._tiandao_observe = {"strengths": {"gate": 0.9}}
    assert abs(observe_strength(s, "gate") - 0.8) < 1e-9      # 超阈归一
    assert observe_strength(s, "absent") is None
    assert observe_strength(_S(), "gate") is None


def test_observe_mix_whitelists_and_ignores_unknown():
    s = _S()
    s._tiandao_observe = {"distributions": {"d": {"a": 0.6, "b": 0.4, "zzz": 0.9}}}
    assert observe_mix(s, "d", ("a", "b")) == {"a": 0.6, "b": 0.4}
    assert observe_mix(s, "d", ("a",)) == {"a": 0.6}
    assert observe_mix(s, "absent", ("a",)) is None
    assert observe_mix(_S(), "d", ("a",)) is None


def test_jitter_is_deterministic_and_bounded():
    s = _S()
    s.turn = 9
    a = jitter(s, "obj", "place", 0.12)
    assert a == jitter(s, "obj", "place", 0.12)
    assert a != jitter(s, "obj", "other", 0.12)
    assert 0.88 - 1e-9 <= a <= 1.12 + 1e-9
    assert jitter(s, "obj", "place", 0.0) == 1.0


# ---------------------------------------------------------------------------
# S1：观测失败必须等价于「无记录」（不得残留上月副本）
# ---------------------------------------------------------------------------
def test_observe_failure_leaves_no_stale_record(monkeypatch):
    from core.ai.tiandao_facade import TianDaoFacade

    class _St:
        turn = 2

    st = _St()
    # 先伪造"上月成功观测"，再让本月取数抛错
    st._tiandao_observe = {"turn": 1, "decisions": {"changping_intervene_gate": True},
                           "distributions": {"merchant_trade": {"hoard": 0.9}},
                           "strengths": {"recruit_refugees": 0.9}}
    monkeypatch.setattr(TianDaoFacade, "build_state_context",
                        classmethod(lambda cls, state: (_ for _ in ()).throw(RuntimeError("boom"))))
    rec = TianDaoFacade.observe_monthly(st)
    assert rec["decisions"] == {} and rec["distributions"] == {} and rec["strengths"] == {}
    # 消费方必须按中性处理（None / 不动作），而不是沿用上月
    assert observe_strength(st, "recruit_refugees") is None
    assert observe_mix(st, "merchant_trade", ("ship", "hoard", "local_sell")) is None
    assert observe_verdict(st, "changping_intervene_gate", (True, False)) is None


# ---------------------------------------------------------------------------
# E5：SPECS 与「月度观测清单」的差集必须显式声明（不许静默漏登）
# ---------------------------------------------------------------------------
def test_specs_equals_observed_plus_declared_non_observed():
    from core.ai.tiandao_decision import NON_OBSERVED_OBJECTIVES, SPECS
    from core.ai.tiandao_facade import TianDaoFacade

    observed = set((TianDaoFacade.OBSERVE_OBJECTIVES or {}).values())
    declared = set(NON_OBSERVED_OBJECTIVES or {})
    assert set(SPECS) == observed | declared, (
        "SPECS 里有既不在月度观测、也没声明原因的 objective："
        + repr(set(SPECS) - observed - declared))
    assert not (observed & declared), "同一 objective 不能既观测又声明不观测"
    for obj, reason in (NON_OBSERVED_OBJECTIVES or {}).items():
        assert isinstance(reason, str) and len(reason) >= 8, obj


# ---------------------------------------------------------------------------
# F6：`jitter` 的 entropy 必须**显式传**（默认值 0.12 是跨域陷阱——各域口径不同，
#     漏传就会用别域的幅度，且不会有任何报错）
# ---------------------------------------------------------------------------
def test_no_jitter_call_relies_on_default_entropy():
    import ast

    root = Path(__file__).resolve().parents[3] / "game"
    offenders = []
    for py in root.rglob("*.py"):
        if "__pycache__" in str(py) or py.name == "tiandao_effects.py":
            continue
        try:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)   # 目标文件含正则反斜杠
                tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "jitter"):
                if len(node.args) + len(node.keywords) < 4:
                    offenders.append((py.name, node.lineno))
    assert not offenders, f"这些 jitter 调用没传 entropy：{offenders}"


# ---------------------------------------------------------------------------
# F7：效果层常数**锁值**（改数必须让测试变红，免得"悄悄改玩法标尺"）
# ---------------------------------------------------------------------------
def test_effect_constants_are_locked():
    from core.ai import tiandao_effects as FX
    from core import settlement_decree as DEC
    from core import settlement_econ as ECON
    from core import settlement_finance as FIN
    from core import settlement_granary as GR

    assert FX.FLEE_VERDICT_MULT == 1.5
    assert FX.FLEE_JITTER == 0.10
    assert FX.MERCHANT_TILT_BOUNDS == (0.85, 1.25)
    assert ECON.MERCHANT_TILT_SPAN == 0.30
    assert ECON.MERCHANT_JITTER == 0.10
    assert ECON.LAND_CONCENTRATION_CAP == 0.003
    assert ECON.GENTRY_RELIEF_CAP == 0.02
    assert GR.CANAL_ROUTE_LOSS_MULT == {"wait_dredge": 1.00, "overland_cart": 0.80,
                                        "borrow_grain": 0.90}
    assert GR.CANAL_JITTER == 0.05
    assert GR.RECRUIT_REFUGEE_CAP_PER_ROUTE == 2000
    assert GR.RECRUIT_JITTER == 0.12
    assert GR.GRANARY_CORRUPTION_MIN_FACTOR == 0.5
    assert FIN.TAX_STANCE_MAX_DELTA == 0.03
    assert DEC.REFORM_COMPLIANCE_FLOOR == 0.5
