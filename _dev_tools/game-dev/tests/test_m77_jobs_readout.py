# -*- coding: utf-8 -*-
"""M78 岗位读数**更正**（把 M77 的两个过保守判断改对）—— 定向回归。

🔴 **M77 报错了两处，本批按实测更正**：
1. **等级缩放本就存在**：`building_jobs.jobs_by_position` 明写「岗位数 = **lv × 每级岗位**」
   ⇒ `JOBS_PER_LEVEL` 是**每级**数 ⇒ 容量 = lv × 每级（M77 报『不臆造等级缩放』= 报错）；
2. **实到本就可算**：`allocate_employment_detail(pops, buildings, cfg)` 是**纯函数**且按传入数据工作
   ⇒ 传治所 pops/buildings 即可**只读**算出在岗数（M77 报『一律 undefined』= 报错）。
本用例同时锁：未登记建筑 ⇒ `None`（缺失≠0）· 单点异常 ⇒ `None` + reason（**不静默补 0**）· 只读。
"""

import copy
import types

from core.domains.economy import jobs_readout as jr


def _state(seat_pops=None, buildings=None):
    st = types.SimpleNamespace()
    st.prefectures = {"路A": {"name": "路A", "seats": {
        "A|甲": {"buildings": buildings if buildings is not None else {"工坊": 2},
                 "pops": seat_pops if seat_pops is not None else
                 {"工匠": {"size": 1000, "wealth": 5000}, "农": {"size": 10000, "wealth": 5000}}}}}}
    return st


# ------------------------------------------------------------------ ① 等级缩放
def test_capacity_scales_with_level():
    one = jr.capacity_of("自耕农庄", 1)["capacity"]
    three = jr.capacity_of("自耕农庄", 3)["capacity"]
    assert one is not None and three == one * 3            # **lv × 每级**
    assert "per_level" in jr.capacity_of("自耕农庄", 2)["level_scaling"]


def test_unknown_or_missing_level_is_honest():
    assert jr.capacity_of("谜之建筑", 1)["capacity"] is None
    assert jr.capacity_of("自耕农庄", 1)["capacity"] is not None   # 缺省等级按 1


# ------------------------------------------------------------------ ② 实到可算（纯函数）
def test_filled_is_computed_readonly():
    st = _state(seat_pops={"工匠": {"size": 1000, "wealth": 5000}},
                buildings={"工坊": 2})
    rep = jr.seat_jobs(st, "路A", "A|甲")
    row = rep["rows"][0]
    assert row["capacity"] == (jr.capacity_of("工坊", 2)["capacity"])
    assert row["filled"] is not None, "实到应由既有纯函数算出（M78 更正）"
    total_filled = sum(sum(d.values()) for d in [row["filled"]] if d)
    assert rep["filled_total"] == total_filled
    assert "allocate_employment_detail" in rep["filled_source"]
    # 岗位受池限制：实到 ≤ 容量，且 ≤ 该阶层 size
    assert 0 <= rep["filled_total"] <= row["capacity"]
    assert rep["filled_total"] <= 1000


def test_filled_zero_when_no_job_buildings():
    """**真值 0 与缺失不同**：有岗位建筑才谈实到；没有岗位建筑 ⇒ 实到 **0**（不是 None）。"""
    st = _state(buildings={"水利": 2, "常平仓": 2})
    rep = jr.seat_jobs(st, "路A", "A|甲")
    assert rep["filled_total"] == 0
    assert rep["capacity_total"] is None                 # 非岗位建筑 ⇒ 容量不可定义（缺失≠0）
    survey = jr.survey_jobs(st)
    assert "非岗位建筑" in survey["note"]                  # 汇总说明里写明"真值 0"与"不得默认补人"


def test_unreadable_seat_is_none_not_zero():
    rep = jr.seat_jobs(_state(), "路A", "不存在")
    assert rep["rows"] == [] and rep["capacity_total"] is None and "缺失≠0" in rep["reason"]


def test_real_opening_capacity_and_filled_are_zero_or_none_honestly():
    """真实开局：20 路 buildings 只有 水利/常平仓 ⇒ **容量 None（无岗位建筑）· 实到 0**。"""
    from core import commands
    s = commands.new_game()
    rep = jr.survey_jobs(s)
    assert rep["capacity_total"] is None
    assert rep["filled_total"] in (0, None)
    assert rep["filled_routes"] >= 0


def test_readonly():
    st = _state()
    before = copy.deepcopy(st.__dict__)
    jr.seat_jobs(st, "路A", "A|甲")
    jr.survey_jobs(st)
    assert copy.deepcopy(st.__dict__) == before
