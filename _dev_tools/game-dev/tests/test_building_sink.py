# -*- coding: utf-8 -*-
"""M38a 建筑（buildings）下沉桥 —— 定向回归。

口径（Jev 2026-10-13）：路级 = **Σ 各治所等级**（choose A 0.429）；下沉初始分配 = **首府承载**
（choose A 0.894）⇒ 迁移后路级 Σ 与**原值逐字相等**。

锁定边界：
  1. 首府承载：全部既有等级落首府治所，其余治所空 `{}`；
  2. **Σ 恒等**：迁移后路级 == 原值（逐建筑名）；
  3. 幂等：已下沉不覆盖；重跑返回 0；
  4. 缺失≠0：未下沉 ⇒ 聚合 `None`、写桥 `None`（调用方回落）；
  5. 首府判定：`SEAT_LEVELS` 序（京府＞府＞州＞军＞部），同级取人口权重大者；判不出退回首键。
"""

import types

import pytest

from core.foundation.ledger import building_bridge as bb

KEY = bb.SEAT_KEY


def _state(routes):
    return types.SimpleNamespace(prefectures=routes)


@pytest.fixture
def cap(monkeypatch):
    """把首府判定打桩成可控值（生产口径不变）。"""
    def _patch(mapping):
        monkeypatch.setattr(bb, "capital_seat_id", lambda pdata, route: mapping.get(route))
    return _patch


# ------------------------------------------------------------------ 1. 首府承载 + 守恒
def test_sink_puts_all_levels_on_capital(cap):
    cap({"路A": "S1"})
    s = _state({"路A": {"buildings": {"水利": 2, "工坊": 1},
                        "seats": {"S1": {}, "S2": {}}}})
    assert bb.sink_buildings_to_seats(s) == 1
    seats = s.prefectures["路A"]["seats"]
    assert seats["S1"][KEY] == {"水利": 2, "工坊": 1}
    assert seats["S2"][KEY] == {}
    # 路级 == 原值（逐字）
    assert s.prefectures["路A"][KEY] == {"水利": 2, "工坊": 1}
    assert bb.is_sunk(s.prefectures["路A"])


def test_sink_preserves_route_total_exactly(cap):
    cap({"路B": "S9"})
    s = _state({"路B": {"buildings": {"桑田": 3, "果园": 5},
                        "seats": {"S9": {}, "S8": {}, "S7": {}}}})
    before = dict(s.prefectures["路B"]["buildings"])
    bb.sink_buildings_to_seats(s)
    assert bb.seat_buildings_total(s.prefectures["路B"]) == before


def test_sink_skips_route_without_levels(cap):
    cap({"路C": "S1"})
    s = _state({"路C": {"buildings": {}, "seats": {"S1": {}}}})
    assert bb.sink_buildings_to_seats(s) == 0
    assert not bb.is_sunk(s.prefectures["路C"])


def test_sink_skips_when_no_capital(cap):
    cap({"路D": None})
    s = _state({"路D": {"buildings": {"水利": 1}, "seats": {"S1": {}}}})
    assert bb.sink_buildings_to_seats(s) == 0


# ------------------------------------------------------------------ 2. 幂等
def test_sink_is_idempotent(cap):
    cap({"路E": "S1"})
    s = _state({"路E": {"buildings": {"水利": 2}, "seats": {"S1": {}, "S2": {}}}})
    assert bb.sink_buildings_to_seats(s) == 1
    assert bb.sink_buildings_to_seats(s) == 0
    assert s.prefectures["路E"]["seats"]["S1"][KEY] == {"水利": 2}


def test_sink_does_not_overwrite_existing_truth(cap):
    cap({"路F": "S1"})
    s = _state({"路F": {"buildings": {"水利": 9},
                        "seats": {"S1": {KEY: {"水利": 4}}, "S2": {KEY: {}}}}})
    assert bb.sink_buildings_to_seats(s) == 0
    assert s.prefectures["路F"]["seats"]["S1"][KEY] == {"水利": 4}


# ------------------------------------------------------------------ 3. 缺失≠0
def test_aggregate_none_when_not_sunk():
    assert bb.aggregate_seat_buildings({"buildings": {"水利": 1}, "seats": {"S1": {}}}) is None
    assert bb.aggregate_seat_buildings({"buildings": {"水利": 1}}) is None
    assert bb.aggregate_seat_buildings(None) is None


def test_building_add_none_when_not_sunk():
    s = _state({"路G": {"buildings": {"水利": 1}, "seats": {"S1": {}}}})
    assert bb.building_add(s, "路G", "工坊", 1) is None
    assert bb.building_level(s, "路G", "工坊") is None


# ------------------------------------------------------------------ 4. 写桥
def test_building_add_lands_on_capital_and_refreshes_mirror(cap):
    cap({"路H": "S1"})
    s = _state({"路H": {"buildings": {"水利": 2}, "seats": {"S1": {}, "S2": {}}}})
    bb.sink_buildings_to_seats(s)

    assert bb.building_add(s, "路H", "工坊", 2) == 2            # 首府新增
    assert bb.building_add(s, "路H", "水利", 1) == 3            # 累加（与 settlement_tech 同语义）
    seats = s.prefectures["路H"]["seats"]
    assert seats["S1"][KEY] == {"水利": 3, "工坊": 2}
    assert s.prefectures["路H"][KEY] == {"水利": 3, "工坊": 2}   # 镜像 = Σ
    assert bb.building_level(s, "路H", "水利") == 3


def test_building_add_honours_explicit_seat(cap):
    cap({"路I": "S1"})
    s = _state({"路I": {"buildings": {"水利": 1}, "seats": {"S1": {}, "S2": {}}}})
    bb.sink_buildings_to_seats(s)
    assert bb.building_add(s, "路I", "仓廪", 1, seat_id="S2") == 1
    seats = s.prefectures["路I"]["seats"]
    assert seats["S2"][KEY] == {"仓廪": 1}
    assert seats["S1"][KEY] == {"水利": 1}
    assert s.prefectures["路I"][KEY] == {"水利": 1, "仓廪": 1}


def test_building_add_rejects_bad_seat(cap):
    cap({"路J": "S1"})
    s = _state({"路J": {"buildings": {"水利": 1}, "seats": {"S1": {}}}})
    bb.sink_buildings_to_seats(s)
    assert bb.building_add(s, "路J", "工坊", 1, seat_id="不存在") is None


# ------------------------------------------------------------------ 5. 对账
def test_survey_reports_mismatch():
    s = _state({
        "路K": {"buildings": {"水利": 5}, "seats": {"S1": {KEY: {"水利": 2}}}},
        "路L": {"buildings": {"水利": 1}, "seats": {"S2": {}}},          # 未下沉
    })
    rep = bb.survey_buildings(s)
    assert rep["路由数"] == 2
    assert rep["已下沉路由"] == 1
    assert rep["未下沉路由"] == 1
    assert len(rep["字段失配"]) == 1
    assert rep["字段失配"][0]["建筑"] == "水利"
    assert rep["字段失配"][0]["路级"] == 5
    assert rep["字段失配"][0]["Σ治所"] == 2


# ------------------------------------------------------------------ 6. 首府判定
def test_capital_prefers_best_grade(monkeypatch):
    monkeypatch.setattr(bb, "_seats_of", lambda route: [
        {"seat_id": "路M|某州", "level": "州"},
        {"seat_id": "路M|某府", "level": "府"},
    ])
    pdata = {"seats": {"路M|某州": {}, "路M|某府": {}}}
    assert bb.capital_seat_id(pdata, "路M") == "路M|某府"          # 府 优于 州


def test_capital_tiebreak_by_population(monkeypatch):
    monkeypatch.setattr(bb, "_seats_of", lambda route: [
        {"seat_id": "路N|甲", "level": "州"},
        {"seat_id": "路N|乙", "level": "州"},
    ])
    monkeypatch.setattr(bb, "_seats_map", bb._seats_map)          # 保持原实现
    import core.foundation.ledger.pop_bridge as pb
    monkeypatch.setattr(pb, "seat_pop_weights", lambda route: [("路N|甲", 1.0), ("路N|乙", 9.0)])
    pdata = {"seats": {"路N|甲": {}, "路N|乙": {}}}
    assert bb.capital_seat_id(pdata, "路N") == "路N|乙"           # 同级取人口多者


def test_capital_falls_back_to_first_seat(monkeypatch):
    monkeypatch.setattr(bb, "_seats_of", lambda route: [])
    pdata = {"seats": {"路O|甲": {}, "路O|乙": {}}}
    assert bb.capital_seat_id(pdata, "路O") == "路O|甲"           # 判不出 ⇒ 确定性首键
