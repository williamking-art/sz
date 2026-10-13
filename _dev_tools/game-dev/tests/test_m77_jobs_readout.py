# -*- coding: utf-8 -*-
"""M77 岗位**只读读数**（P2 缺口 1 第一切片）—— 定向回归。

锁定：① 容量＝`JOBS_PER_LEVEL` **原值**，标量**不臆造等级缩放**；② 所需阶层＝`BUILDING_WORKER`；
③ **实到一律 `None` + reason**（无就业实例 ⇒ 不得默认全员就业/满产）；④ 未登记建筑类型 ⇒
`None`（**不是 0 岗位**）；⑤ 真实开局 20 路**无岗位建筑** ⇒ 容量与实到均 `undefined`（如实）；
⑥ 只读。
"""

import copy
import types

from core.domains.economy import jobs_readout as jr


def _state(buildings_by_seat):
    st = types.SimpleNamespace()
    st.prefectures = {"路A": {"name": "路A", "seats": buildings_by_seat}}
    return st


def test_scalar_config_is_not_level_scaled():
    cap = jr.capacity_of("自耕农庄", 3)
    assert cap["capacity"] == 160.0                      # **原值**，不乘等级
    assert cap["level_scaling"] == "undefined"
    assert jr.capacity_of("自耕农庄", 1)["capacity"] == 160.0


def test_unknown_building_is_none_not_zero():
    cap = jr.capacity_of("谜之建筑", 1)
    assert cap["capacity"] is None and "缺失≠0" in cap["reason"]
    assert jr.class_of("谜之建筑")["class"] is None


def test_class_single_point():
    assert jr.class_of("工坊")["class"] == "工匠"
    assert jr.class_of("商铺")["class"] == "商人"
    assert jr.class_of("农田")["class"] == "农"


def test_seat_jobs_reports_capacity_but_never_filled():
    st = _state({"A|甲": {"buildings": {"工坊": 1}}})
    rep = jr.seat_jobs(st, "路A", "A|甲")
    row = rep["rows"][0]
    assert row["capacity"] == (jr.capacity_of("工坊", 1)["capacity"])
    assert row["class"] == "工匠"
    assert row["filled"] is None and "无就业实例" in row["filled_reason"]   # **不默认全员就业**
    assert rep["filled_total"] is None and rep["capacity_total"] == int(row["capacity"])


def test_unreadable_seat_is_none():
    rep = jr.seat_jobs(_state({}), "路A", "不存在")
    assert rep["rows"] == [] and rep["capacity_total"] is None and "缺失≠0" in rep["reason"]


def test_real_opening_has_no_job_buildings_so_all_undefined():
    """真实开局：20 路的 buildings 只有 水利/常平仓（**都不是岗位建筑**）⇒ 容量与实到皆 undefined。"""
    from core import commands
    s = commands.new_game()
    rep = jr.survey_jobs(s)
    assert rep["capacity_total"] is None and rep["filled_total"] is None
    assert rep["readable_routes"] == 0
    assert "无就业实例" in rep["filled_reason"]


def test_readonly():
    st = _state({"A|甲": {"buildings": {"工坊": 1}}})
    before = copy.deepcopy(st.__dict__)
    jr.seat_jobs(st, "路A", "A|甲")
    jr.survey_jobs(st)
    assert copy.deepcopy(st.__dict__) == before
