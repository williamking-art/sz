# -*- coding: utf-8 -*-
"""M1a：机构派系分布（只读）16 条验收。

契约：`党争机制_实现契约速查表_2026-10-18.md` §4。
"""
import copy
from types import SimpleNamespace

import pytest

from core import commands
from core.faction_distribution import distribution_of, institution_distribution


def _org(posts, holders, abolished=False):
    return {"posts": posts, "holders": holders, "abolished": abolished}


def _state(orgs, factions=None, turn=7):
    return SimpleNamespace(central_orgs=orgs, factions=factions or {}, turn=turn)


@pytest.fixture(scope="module")
def real_state():
    return commands.new_game()


# 1
def test_libu_real_distribution(real_state):
    org = institution_distribution(real_state)["orgs"]["吏部"]
    assert org["defined"] is True
    assert org["posts_total"] == 2
    assert org["filled_posts"] == 1
    assert org["faction_share"] == pytest.approx({"新党": 0.5})
    assert org["vacant_share"] == pytest.approx(0.5)
    assert org["unaffiliated_share"] == pytest.approx(0.0)
    assert org["concurrent_discount_share"] == pytest.approx(0.0)


# 2
def test_hubu_real_concurrent_distribution(real_state):
    org = institution_distribution(real_state)["orgs"]["户部"]
    assert org["defined"] is True
    assert org["posts_total"] == 3
    assert org["filled_posts"] == 2
    assert org["faction_share"] == pytest.approx({"中立派": 0.5})
    assert org["vacant_share"] == pytest.approx(1.0 / 3.0)
    assert org["concurrent_discount_share"] == pytest.approx(0.5 / 3.0)
    assert org["concurrent_holders"] == ["王古"]

    detail = {d["post"]: d for d in org["holders_detail"]}
    assert detail["户部尚书"]["is_primary"] is True
    assert detail["户部尚书"]["concurrent"] is True
    assert detail["户部尚书"]["faction_counted_weight"] == pytest.approx(1.0)
    assert detail["户部侍郎"]["holder"] == ""
    assert detail["户部侍郎"]["faction_counted_weight"] == 0.0
    assert detail["抵当所提举"]["is_primary"] is False
    assert detail["抵当所提举"]["concurrent"] is True
    assert detail["抵当所提举"]["faction_counted_weight"] == pytest.approx(0.5)
    assert detail["抵当所提举"]["concurrent_discount_weight"] == pytest.approx(0.5)


# 3
def test_menxia_real_distribution(real_state):
    org = institution_distribution(real_state)["orgs"]["门下省"]
    assert org["faction_share"] == pytest.approx({"旧党": 1.0})
    assert org["vacant_share"] == pytest.approx(0.0)


# 4
def test_zhongshu_real_distribution(real_state):
    org = institution_distribution(real_state)["orgs"]["中书省"]
    assert org["faction_share"] == pytest.approx({"中立派": 1.0})


# 5
def test_all_posts_vacant_is_defined_with_vacant_one():
    s = _state({"X": _org([{"title": "a"}, {"title": "b"}], {"a": "", "b": ""})})
    org = distribution_of(s, "X")
    assert org["defined"] is True
    assert org["filled_posts"] == 0
    assert org["vacant_share"] == pytest.approx(1.0)
    assert org["faction_share"] == {}


# 6
def test_no_posts_definition_is_undefined():
    s = _state({"X": {"posts": [], "holders": {}}})
    org = distribution_of(s, "X")
    assert org["defined"] is False
    assert org["vacant_share"] is None
    assert "no_posts_defined" in org["notes"]

    s2 = _state({"Y": {"holders": {}}})
    assert distribution_of(s2, "Y")["defined"] is False


# 7
def test_abolished_org_is_excluded():
    s = _state({
        "A": _org([{"title": "a"}], {"a": "邓洵武"}, abolished=True),
        "B": _org([{"title": "b"}], {"b": "王古"}),
    })
    rep = institution_distribution(s)
    assert "A" not in rep["orgs"]
    assert rep["excluded_orgs"] == ["A"]
    assert "B" in rep["orgs"]


# 8
def test_unaffiliated_holder_goes_to_unaffiliated_share():
    s = _state({"X": _org([{"title": "a"}], {"a": "路人甲"})})
    org = distribution_of(s, "X")
    assert org["faction_share"] == {}
    assert org["unaffiliated_share"] == pytest.approx(1.0)
    assert org["vacant_share"] == pytest.approx(0.0)


# 9
def test_same_person_in_two_orgs_counted_per_org():
    s = _state({
        "A": _org([{"title": "a"}], {"a": "邓洵武"}),
        "B": _org([{"title": "b"}], {"b": "邓洵武"}),
    })
    rep = institution_distribution(s)
    assert rep["orgs"]["A"]["faction_share"] == pytest.approx({"新党": 1.0})
    assert rep["orgs"]["B"]["faction_share"] == pytest.approx({"新党": 1.0})


# 10
def test_pure_read_does_not_mutate_state():
    s = commands.new_game()
    before_orgs = copy.deepcopy(s.central_orgs)
    before_factions = copy.deepcopy(s.factions)
    institution_distribution(s)
    assert s.central_orgs == before_orgs
    assert s.factions == before_factions


# 11
def test_unaffiliated_concurrent_holder():
    s = _state({
        "X": _org([{"title": "a"}, {"title": "b"}],
                   {"a": "路人甲", "b": "路人甲"})
    })
    org = distribution_of(s, "X")
    assert org["faction_share"] == {}
    assert org["unaffiliated_share"] == pytest.approx(0.75)
    assert org["concurrent_discount_share"] == pytest.approx(0.25)
    assert org["vacant_share"] == pytest.approx(0.0)


# 12
def test_three_posts_same_holder():
    s = _state({
        "X": _org([{"title": "a"}, {"title": "b"}, {"title": "c"}],
                   {"a": "邓洵武", "b": "邓洵武", "c": "邓洵武"})
    })
    org = distribution_of(s, "X")
    assert org["faction_share"] == pytest.approx({"新党": 2.0 / 3.0})
    assert org["concurrent_discount_share"] == pytest.approx(1.0 / 3.0)
    assert org["vacant_share"] == pytest.approx(0.0)
    assert org["concurrent_holders"] == ["邓洵武"]


# 13
def test_two_concurrent_holders_primary_by_posts_order():
    s = _state({
        "X": _org(
            [{"title": "p0"}, {"title": "p1"}, {"title": "p2"}, {"title": "p3"}],
            {"p0": "邓洵武", "p1": "王古", "p2": "邓洵武", "p3": "王古"},
        )
    })
    org = distribution_of(s, "X")
    assert org["faction_share"] == pytest.approx({"新党": 0.375, "中立派": 0.375})
    assert org["concurrent_discount_share"] == pytest.approx(0.25)
    detail = {d["post"]: d for d in org["holders_detail"]}
    assert detail["p0"]["is_primary"] is True
    assert detail["p1"]["is_primary"] is True
    assert detail["p2"]["is_primary"] is False
    assert detail["p3"]["is_primary"] is False


# 14
def test_empty_and_duplicate_post_titles():
    s_empty = _state({"X": {"posts": [], "holders": {}}})
    assert distribution_of(s_empty, "X")["defined"] is False

    s_dup = _state({"X": _org([{"title": "a"}, {"title": "a"}], {"a": ""})})
    org = distribution_of(s_dup, "X")
    assert org["defined"] is False
    assert org["error"] == "duplicate_post_title"


# 15
def test_detail_sums_match_shares_and_conservation():
    s = commands.new_game()
    rep = institution_distribution(s)
    for name, org in rep["orgs"].items():
        if not org["defined"]:
            continue
        total = org["posts_total"]
        detail = org["holders_detail"]
        assert sum(d["faction_counted_weight"] for d in detail) / total == pytest.approx(
            sum(org["faction_share"].values())
        )
        assert sum(d["unaffiliated_weight"] for d in detail) / total == pytest.approx(
            org["unaffiliated_share"]
        )
        assert sum(d["concurrent_discount_weight"] for d in detail) / total == pytest.approx(
            org["concurrent_discount_share"]
        )
        assert sum(d["acting_discount_weight"] for d in detail) / total == pytest.approx(
            org["acting_discount_share"]
        )
        total_share = (
            sum(org["faction_share"].values())
            + org["vacant_share"]
            + org["unaffiliated_share"]
            + org["concurrent_discount_share"]
            + org["acting_discount_share"]
        )
        assert total_share == pytest.approx(1.0), name


# 16
def test_output_is_isolated_and_deterministic():
    s = commands.new_game()
    a = institution_distribution(s)
    b = institution_distribution(s)
    assert a == b

    org = a["orgs"]["吏部"]
    org["faction_share"]["新党"] = 999.0
    org["holders_detail"].append({"post": "hack"})
    org["concurrent_holders"].append("hack")

    c = institution_distribution(s)
    assert c["orgs"]["吏部"]["faction_share"] == pytest.approx({"新党": 0.5})
    assert len(c["orgs"]["吏部"]["holders_detail"]) == 2
    assert c["orgs"]["吏部"]["concurrent_holders"] == []

