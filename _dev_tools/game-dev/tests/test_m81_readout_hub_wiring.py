# -*- coding: utf-8 -*-
"""M81 把 P1 链条与岗位读数接进 `readout_hub` —— 定向回归。

锁定（P5 验收门）：① 两项都在注册表里且**顺序在后**；② **有值 ⇒ display 是数值字符串**；
③ **不可读 ⇒ `display == "undefined"`（绝不显示 0）**且带 reason；④ `drill_down` 含来源；
⑤ 逐项失败隔离（单项异常不影响其它项）；⑥ 只读。
"""

import copy

from core import commands
from core.domains.economy import readout_hub as rh


def _state_with_months(state, months=6):
    import core.settlement as S
    for _ in range(months):
        S.run_monthly_settlement(state)
    return state


def test_two_new_readouts_are_registered_with_sources():
    keys = [r["key"] for r in rh.READOUTS]
    # 用**成员判定**（而非切片）⇒ 后续继续扩项不会误红（M83/M87 各扩过一次）
    for k in ("pilot_chain_gap", "jobs_capacity", "pilot_bottleneck", "p2_readiness"):
        assert k in keys, k
        row = next(r for r in rh.READOUTS if r["key"] == k)
        assert row["source"] and row["label"] and row["unit"]


def test_pilot_chain_gap_has_value_and_drill_down():
    s = _state_with_months(commands.new_game())
    rep = rh.collect(s, keys=["pilot_chain_gap"])
    row = rep["readouts"]["pilot_chain_gap"]
    assert row["value"] is not None and row["display"] == str(row["value"])
    assert "p1_pilot_chain" in str(row["drill_down"])


def test_jobs_capacity_is_undefined_not_zero_and_explained():
    s = _state_with_months(commands.new_game())
    rep = rh.collect(s, keys=["jobs_capacity"])
    row = rep["readouts"]["jobs_capacity"]
    assert row["value"] is None
    assert row["display"] == "undefined"                     # **绝不显示 0**
    assert "岗位建筑" in row["reason"] or "不可定义" in row["reason"]
    dd = row["drill_down"]                                   # 🔴 undefined 行也必须是 dict（本轮踩过）
    assert isinstance(dd, dict) and "jobs_readout" in str(dd.get("drill"))
    assert dd.get("实到（建筑岗位）") in (0, None)             # 实到与容量**分开呈现**


def test_all_readouts_shape_and_readonly():
    s = _state_with_months(commands.new_game())
    before = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    rep = rh.collect(s)
    assert len(rep["readouts"]) == len(rh.READOUTS) == 15      # 11→12(M83)→13(M87)→14(M94)→15(M97)
    assert rep["frontend_wired"] is False
    for k, v in rep["readouts"].items():
        assert set(v) >= {"label", "value", "display", "unit", "source", "reason"}
        if v["value"] is None:
            assert v["display"] == "undefined" and v["reason"], k
    bad = rh.undefined_summary(s)
    assert "jobs_capacity" in bad["undefined"]
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before
