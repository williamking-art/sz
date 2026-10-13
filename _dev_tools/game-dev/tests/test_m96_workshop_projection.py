# -*- coding: utf-8 -*-
"""M96 作坊（经营记录）P2 投影 —— 定向回归。

锁定：① 规格原文「建筑/**经营记录**」⇒ 作坊投影与建筑投影**分列**；② 能算的算
（地点/owner/经营者/经营方式/配方）；③ **不能算的如实 undefined + reason**（尤其
**作坊岗位容量/实到**：M67 无权威来源 ⇒ **不按人口均分、不默认满员**）；④ 只读。
"""

import copy
import types

from core.domains.economy import entity_projection as ep


def _state(workshops):
    st = types.SimpleNamespace()
    st.workshops = workshops
    st.prefectures = {"路A": {"name": "路A", "seats": {"路A|首府": {"buildings": {}, "pops": {}}}}}
    return st


def test_workshop_computable_fields():
    st = _state({"丝坊_路A_0": {"name": "丝坊", "recipe": {"丝": 10000}, "output_dim": "绸",
                              "yield": 8000, "active": True, "owner": "pop:路A:商人"}})
    rep = ep.project_workshop(st, "丝坊_路A_0")
    f = rep["fields"]
    assert f["recipe"]["defined"] and f["recipe"]["value"] == {"丝": 10000}
    assert f["owner"]["defined"] and f["owner"]["value"] == "pop:路A:商人"
    assert f["operator"]["value"] == "pop:路A:商人"                 # M92 首期＝owner
    assert f["operation_mode"]["value"] == "民营雇工"                # pop:…:商人
    assert rep["defined_count"] == 7                              # +methods（M110 只读派生 active/available）
    assert rep["field_count"] == 14


def test_workshop_jobs_are_undefined_and_not_prorated():
    st = _state({"酒坊_路A_1": {"name": "酒坊", "recipe": {"grain_feed": 50000}, "owner": "local:路A"}})
    f = ep.project_workshop(st, "酒坊_路A_1")["fields"]
    assert f["jobs_capacity"]["defined"] is False and f["jobs_filled"]["defined"] is False
    assert "无权威来源" in f["jobs_capacity"]["reason"]
    assert "不按人口均分、不默认满员" in f["jobs_filled"]["reason"]


def test_unknown_workshop_is_honest():
    rep = ep.project_workshop(_state({}), "不存在_路A_0")
    assert rep["fields"] == {} and "缺失≠0" in rep["reason"]


def test_survey_workshop_projection_and_readonly():
    from core import commands
    s = commands.new_game()
    before = copy.deepcopy({k: dict(v) for k, v in (s.workshops or {}).items()})
    rep = ep.survey_workshop_projection(s)
    assert rep["workshops"] == 107
    assert rep["defined_ratio"]["owner"] == 1.0                   # M66 已全登记
    assert rep["defined_ratio"]["recipe"] == 1.0
    assert rep["defined_ratio"]["jobs_filled"] == 0.0             # M67：如实不可定义
    assert copy.deepcopy({k: dict(v) for k, v in (s.workshops or {}).items()}) == before
