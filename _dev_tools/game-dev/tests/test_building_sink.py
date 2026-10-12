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


# ------------------------------------------------------------------ 7. 条目形态（built_month）
def test_norm_level_forms():
    assert bb.norm_level(2) == 2
    assert bb.norm_level({"lv": 3}) == 3
    assert bb.norm_level({"closed": True, "lv": 5}) == 0          # 倒闭 ⇒ 0（building_jobs 语义）
    assert bb.norm_level({"built_month": 4}) is None              # 无 lv ⇒ 读不出（缺失≠0）
    assert bb.norm_level(None) is None
    assert bb.norm_level(True) is None                            # bool 不算等级


def test_sink_preserves_dict_form_and_built_month(cap):
    """`civil_building` 写的 `{"lv":n,"built_month":m}` 必须**原样**搬到治所，不得归一成 int。"""
    cap({"路P": "S1"})
    s = _state({"路P": {"buildings": {"货栈": {"lv": 2, "built_month": 7}, "工坊": 1},
                        "seats": {"S1": {}, "S2": {}}}})
    assert bb.sink_buildings_to_seats(s) == 1
    seats = s.prefectures["路P"]["seats"]
    assert seats["S1"][KEY]["货栈"] == {"lv": 2, "built_month": 7}
    assert seats["S1"][KEY]["工坊"] == 1
    assert seats["S2"][KEY] == {}
    mirror = s.prefectures["路P"][KEY]
    assert mirror["工坊"] == 1                                    # 标量仍标量
    assert mirror["货栈"] == {"lv": 2, "built_month": 7}           # 字典仍字典


def test_aggregate_keeps_dict_form_and_oldest_month(cap):
    """多治所聚合：Σ 等级；`built_month` 取**最老者**（推演口径，逐治所真账各留原值）。"""
    cap({"路Q": "S1"})
    s = _state({"路Q": {"buildings": {"货栈": {"lv": 1, "built_month": 9}},
                        "seats": {"S1": {}, "S2": {}}}})
    bb.sink_buildings_to_seats(s)
    assert bb.building_set(s, "路Q", "货栈", {"lv": 3, "built_month": 4}, seat_id="S2") is not None
    assert s.prefectures["路Q"][KEY]["货栈"] == {"lv": 4, "built_month": 4}
    assert bb.seat_buildings_total(s.prefectures["路Q"]) == {"货栈": 4}
    # 逐治所真账各自保留原 built_month
    seats = s.prefectures["路Q"]["seats"]
    assert seats["S1"][KEY]["货栈"]["built_month"] == 9
    assert seats["S2"][KEY]["货栈"]["built_month"] == 4


def test_building_add_keeps_built_month_on_dict_entry(cap):
    cap({"路R": "S1"})
    s = _state({"路R": {"buildings": {"货栈": {"lv": 1, "built_month": 5}},
                        "seats": {"S1": {}}}})
    bb.sink_buildings_to_seats(s)
    assert bb.building_add(s, "路R", "货栈", 1) == 2
    assert s.prefectures["路R"]["seats"]["S1"][KEY]["货栈"] == {"lv": 2, "built_month": 5}


def test_building_add_writes_dict_when_built_month_given(cap):
    cap({"路S": "S1"})
    s = _state({"路S": {"buildings": {"工坊": 1}, "seats": {"S1": {}}}})
    bb.sink_buildings_to_seats(s)
    assert bb.building_add(s, "路S", "货栈", 1, built_month=11) == 1
    assert s.prefectures["路S"]["seats"]["S1"][KEY]["货栈"] == {"lv": 1, "built_month": 11}
    assert s.prefectures["路S"][KEY]["货栈"] == {"lv": 1, "built_month": 11}


def test_building_set_raw_write_and_gate(cap):
    cap({"路T": "S1"})
    s = _state({"路T": {"buildings": {"货栈": 1}, "seats": {"S1": {}}}})
    assert bb.building_set(s, "路T", "货栈", {"lv": 2}) is None    # 未下沉 ⇒ None
    bb.sink_buildings_to_seats(s)
    assert bb.building_set(s, "路T", "货栈", {"lv": 3, "built_month": 2}) == {"lv": 3, "built_month": 2}
    assert bb.building_set(s, "路T", "货栈", {"built_month": 1}) is None   # 无 lv ⇒ 拒绝


def test_closed_entry_counts_zero():
    s = _state({"路U": {"buildings": {"货栈": {"closed": True, "lv": 3}},
                        "seats": {"S1": {}}}})
    bb.sink_buildings_to_seats(s)
    assert bb.seat_buildings_total(s.prefectures["路U"]) == {"货栈": 0}


# ------------------------------------------------------------------ 8. 删除语义（era_mechanic 降级用）
def test_building_remove_deletes_key_not_zero(cap):
    """原文是 `del b[bt]`（删键）——桥必须同样**删键**，不能留 0（否则 `in` 判据改变）。"""
    cap({"路V": "S1"})
    s = _state({"路V": {"buildings": {"货栈": 1, "工坊": 2}, "seats": {"S1": {}, "S2": {}}}})
    bb.sink_buildings_to_seats(s)

    assert bb.building_remove(s, "路V", "货栈") is True
    seats = s.prefectures["路V"]["seats"]
    assert "货栈" not in seats["S1"][KEY]
    assert "货栈" not in s.prefectures["路V"][KEY]              # 镜像同步删键
    assert bb.building_remove(s, "路V", "货栈") is False         # 没删到
    assert bb.building_remove(s, "路V", "工坊") is True
    assert s.prefectures["路V"][KEY] == {}


def test_building_remove_none_when_not_sunk():
    s = _state({"路W": {"buildings": {"货栈": 1}, "seats": {"S1": {}}}})
    assert bb.building_remove(s, "路W", "货栈") is None


