# -*- coding: utf-8 -*-
"""M86 P2 建筑实例只读投影 —— 定向回归。

锁定：① 规格 14 字段**枚举齐**；② **能算的算**（等级/岗位容量/实到）；③ **不能算的如实 undefined + reason**
（owner/operator/完工月/经营方式/配方/库存栏/收入去向）；④ **不得默认全员就业/满产**；⑤ 只读。
"""

import copy
import types

from core.domains.economy import entity_projection as ep


def _state(buildings, pops=None):
    st = types.SimpleNamespace()
    st.prefectures = {"路A": {"name": "路A", "seats": {
        "A|甲": {"buildings": buildings, "pops": pops or {"工匠": {"size": 1000, "wealth": 5000}}}}}}
    return st


def test_fields_cover_spec_enumeration():
    assert len(ep.FIELDS) == 14
    assert {"blueprint", "seat", "level", "completed_month", "owner", "operator", "maintenance",
            "operation_mode", "methods", "jobs_capacity", "jobs_filled", "recipe", "io_stock",
            "income_to"} == set(ep.FIELDS)


def test_computable_fields_are_computed():
    st = _state({"工坊": 2})
    rep = ep.project_building(st, "路A", "A|甲", "工坊", 2)
    assert rep["fields"]["level"]["defined"] and rep["fields"]["level"]["value"] == 2
    assert rep["fields"]["jobs_capacity"]["defined"], "容量应可算（lv × 每级）"
    assert rep["fields"]["jobs_filled"]["defined"], "实到应可算（M78 纯函数）"
    assert rep["defined_count"] == 4                      # seat/level/jobs_capacity/jobs_filled


def test_undefined_fields_are_honest_and_explained():
    st = _state({"工坊": 1})
    rep = ep.project_building(st, "路A", "A|甲", "工坊", 1)
    f = rep["fields"]
    for k in ("blueprint", "completed_month", "owner", "operator", "maintenance",
              "operation_mode", "methods", "recipe", "io_stock", "income_to"):
        assert f[k]["defined"] is False, k
        assert f[k]["reason"], k                          # **必须有原因**（不静默）
    assert "real_opening" not in f
    assert "不得用默认全员就业" in rep["note"]


def test_non_job_building_yields_undefined_capacity():
    st = _state({"水利": 2, "常平仓": 2})                  # 真实开局的两种建筑（都非岗位建筑）
    rep = ep.project_building(st, "路A", "A|甲", "水利", 2)
    assert rep["fields"]["jobs_capacity"]["defined"] is False
    assert "非岗位建筑" in rep["fields"]["jobs_capacity"]["reason"]


def test_real_game_survey_ratio_and_readonly():
    from core import commands
    s = commands.new_game()
    before = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    rep = ep.survey_entity_projection(s)
    assert rep["buildings"] == 40                          # 20 路 × 2 座（水利/常平仓）
    ratio = rep["defined_ratio"]
    assert ratio["level"] == 1.0 and ratio["seat"] == 1.0
    assert ratio["jobs_capacity"] == 0.0                   # 非岗位建筑 ⇒ 容量不可算（如实）
    assert ratio["owner"] == 0.0 and ratio["income_to"] == 0.0
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before
