# -*- coding: utf-8 -*-
"""条件 DSL 与档位映射的回归测试 —— 对应《宋祚局势系统实施规范》§3.1–§3.4、§4.2.1、§11.3。

DSL 是**纯函数**（不接收 state、不写字段），故 v1 即可全量落地并断言。
"""
import logging
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.situations import (  # noqa: E402
    GRADE_DELTA, SNAPSHOT_METRICS, advance_bar, evaluate, grade_delta, used_metrics,
    validate_condition,
)
from core.situation_metrics import build_metric_snapshot  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402


def _snap():
    s = GameState("史实")
    init_legacies(s)
    # `treasury` 是注册表内的无参 metric，但不属局势 v1 快照清单 → 测试自行加入
    snap, errors = build_metric_snapshot(s, list(SNAPSHOT_METRICS) + ["treasury"])
    assert not errors, errors[:3]
    assert None in snap["metrics"]["treasury"]
    return snap


# ---------------------------------------------------------------
# 结构校验
# ---------------------------------------------------------------
def test_empty_groups():
    assert evaluate({"all": []}, {}) is True
    assert evaluate({"any": []}, {}) is False
    assert validate_condition({"all": []}) == []
    assert validate_condition({"any": []}) == []


def test_ops_are_whitelisted():
    for op in (">=", "<=", ">", "<", "==", "!="):
        assert validate_condition({"metric": "treasury", "op": op, "value": 1}) == [], op
    errs = validate_condition({"metric": "treasury", "op": "~=", "value": 1})
    assert errs and "非法 op" in errs[0]


def test_depth_limit_is_three():
    def nest(n):
        node = {"metric": "treasury", "op": ">", "value": 0}
        for _ in range(n):
            node = {"all": [node]}
        return node
    assert validate_condition(nest(3)) == []
    assert any("嵌套深度" in e for e in validate_condition(nest(4)))


def test_streak_only_at_root():
    ok = {"all": [{"metric": "treasury", "op": ">", "value": 0}], "streak": 2}
    assert validate_condition(ok) == []
    bad = {"all": [{"all": [{"metric": "treasury", "op": ">", "value": 0}], "streak": 1}]}
    assert any("仅允许出现在根节点" in e for e in validate_condition(bad))


def test_unregistered_metric_and_missing_arg_rejected():
    assert any("未注册 metric" in e
               for e in validate_condition({"metric": "not.a.metric", "op": ">", "value": 0}))
    # region.public_support 必填 arg
    assert any("需要 arg" in e
               for e in validate_condition({"metric": "region.public_support", "op": ">", "value": 0}))
    # 未知键与 NaN
    assert any("未知键" in e
               for e in validate_condition({"metric": "treasury", "op": ">", "value": 0, "foo": 1}))
    assert any("NaN" in e
               for e in validate_condition({"metric": "treasury", "op": ">", "value": float("nan")}))
    assert any("不得同时出现" in e
               for e in validate_condition({"all": [], "any": []}))


# ---------------------------------------------------------------
# 判定语义
# ---------------------------------------------------------------
def test_all_ops_evaluate_correctly():
    snap = _snap()
    sup = snap["metrics"]["region.public_support"]["河北路"]
    assert evaluate({"metric": "region.public_support", "arg": "河北路", "op": "==", "value": sup}, snap)
    assert evaluate({"metric": "region.public_support", "arg": "河北路", "op": "!=", "value": sup + 1}, snap)
    assert evaluate({"metric": "region.public_support", "arg": "河北路", "op": ">=", "value": sup}, snap)
    assert evaluate({"metric": "region.public_support", "arg": "河北路", "op": "<=", "value": sup}, snap)
    assert not evaluate({"metric": "region.public_support", "arg": "河北路", "op": ">", "value": sup}, snap)


def test_all_any_semantics():
    snap = _snap()
    t = {"metric": "treasury", "op": ">=", "value": 0}
    f = {"metric": "treasury", "op": "<", "value": -1}
    assert evaluate({"all": [t, f]}, snap) is False
    assert evaluate({"any": [t, f]}, snap) is True
    assert evaluate({"all": [t, {"any": [f, t]}]}, snap) is True


def test_missing_value_is_false_and_warns(caplog):
    snap = _snap()
    with caplog.at_level(logging.WARNING, logger="situations"):
        # 无驻军的路 → army.morale 缺失
        assert evaluate({"metric": "army.morale", "arg": "利州路", "op": ">", "value": 0}, snap) is False
        # 值为 None 的列
        snap2 = {"metrics": {"treasury": {None: None}}}
        assert evaluate({"metric": "treasury", "op": ">", "value": 0}, snap2) is False
        # 未注册 metric（未进快照）
        assert evaluate({"metric": "not.a.metric", "op": ">", "value": 0}, snap) is False
    assert caplog.text.count("缺失值") >= 2


def test_type_mismatch_is_false_not_exception():
    snap = {"metrics": {"region.mood": {"河北路": "五十"}}}
    assert evaluate({"metric": "region.mood", "arg": "河北路", "op": ">", "value": 50}, snap) is False
    assert evaluate({"metric": "region.mood", "arg": "河北路", "op": "==", "value": "五十"}, snap) is True


def test_evaluate_does_not_mutate_snapshot():
    snap = _snap()
    before = repr(snap)
    evaluate({"all": [{"metric": "treasury", "op": ">", "value": 1}]}, snap)
    assert repr(snap) == before


def test_used_metrics_extraction():
    cond = {"all": [
        {"metric": "treasury", "op": ">", "value": 0},
        {"any": [{"metric": "region.unrest", "arg": "陕西路", "op": ">", "value": 50},
                 {"metric": "treasury", "op": "<", "value": -1}]},
    ], "streak": 2}
    assert used_metrics(cond) == ["region.unrest", "treasury"]
    assert used_metrics({"all": []}) == []


# ---------------------------------------------------------------
# 档位 → Δbar 与推进（§4.2.1）
# ---------------------------------------------------------------
def test_grade_delta_table_is_single_source():
    assert GRADE_DELTA == {"verybad": -8, "bad": -4, "normal": 0, "good": 5, "verygood": 10}
    for g, d in GRADE_DELTA.items():
        assert grade_delta(g) == d
    assert grade_delta("nonsense") == 0        # 非法档位 → 兜底 normal


def test_advance_bar_clamps_and_applies_execution_discount():
    assert advance_bar(50, "good") == 55
    assert advance_bar(98, "verygood") == 100
    assert advance_bar(2, "verybad") == 0
    # 玩家意图加成按执行度打折：下了诏 ≠ 办了事
    assert advance_bar(50, "normal", intent_bonus=10, execution_mult=0.5) == 55
    assert advance_bar(50, "normal", intent_bonus=10, execution_mult=1.0) == 60
    # 缺省 1.0 不改变既有语义
    assert advance_bar(50, "normal", intent_bonus=10) == 60
    # inertia 照加（可为负）
    assert advance_bar(50, "normal", inertia=-3) == 47
    # 脏输入不炸
    assert advance_bar("x", "good") == 5
