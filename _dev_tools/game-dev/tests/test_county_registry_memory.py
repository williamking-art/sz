# -*- coding: utf-8 -*-
"""县制写入 MemoryGraph：县实体 + 编制 + 县官 governs + 父州府 belongs_to。"""
from memory.memory_graph import MemoryGraph, get_memory_graph
from core.county_registry import (
    COUNTY_POSTS,
    assign_county_official,
    county_eid,
    county_officials,
    county_of_official,
    ensure_county_establishment,
)
from core import commands
from core.domains.administration.prefect_officials import jinshi_to_county


def test_ensure_county_establishment():
    g = MemoryGraph()
    cid = ensure_county_establishment(
        g, "鄞县", route="两浙路", parent_seat_id="两浙路|杭州", turn=3)
    assert cid == county_eid("鄞县")
    ent = g.entities[cid]
    assert ent["type"] == "county"
    assert set(ent["attrs"]["posts"]) == {p["title"] for p in COUNTY_POSTS}
    assert ent["attrs"]["quotas"]["知县"] == 1
    assert ent["attrs"]["parent_seat_id"] == "两浙路|杭州"
    assert any(r["rtype"] == "belongs_to" and r["dst"] == "两浙路|杭州"
               for r in g.relations)


def test_ensure_county_is_idempotent():
    g = MemoryGraph()
    ensure_county_establishment(g, "鄞县", parent_seat_id="两浙路|杭州", turn=1)
    ensure_county_establishment(g, "鄞县", parent_seat_id="两浙路|杭州", turn=2)
    assert sum(1 for r in g.relations if r["rtype"] == "belongs_to") == 1
    assert len([e for e in g.entities.values() if e["type"] == "county"]) == 1


def test_assign_and_query_county_official():
    g = MemoryGraph()
    g.add_entity("minister_范仲淹", "minister", "范仲淹", {}, turn=0)
    assign_county_official(
        g, "范仲淹", "鄞县", post="知县",
        route="两浙路", parent_seat_id="两浙路|杭州", turn=3)
    holders = county_officials(g, "鄞县")
    assert [h["eid"] for h in holders] == ["minister_范仲淹"]
    assert county_of_official(g, "范仲淹") == "鄞县"


def test_county_registry_survives_memory_roundtrip():
    g = MemoryGraph()
    g.add_entity("minister_范仲淹", "minister", "范仲淹", {}, turn=0)
    assign_county_official(
        g, "范仲淹", "鄞县", post="知县",
        route="两浙路", parent_seat_id="两浙路|杭州", turn=3)
    g2 = MemoryGraph()
    g2.from_dict(g.to_dict())
    ent = g2.entities[county_eid("鄞县")]
    assert ent["type"] == "county"
    assert [h["eid"] for h in county_officials(g2, "鄞县")] == ["minister_范仲淹"]
    assert any(r["rtype"] == "belongs_to" for r in g2.relations)


def test_jinshi_to_county_writes_county_entity():
    s = commands.new_game()
    s.turn = 3
    res = jinshi_to_county(
        s,
        [{"name": "范仲淹", "county": "鄞县",
          "route": "两浙路", "parent_seat_id": "两浙路|杭州",
          "guarantor": "韩忠彦"}],
        slot=99,
    )
    assert res["ok"] is True
    g = get_memory_graph(99)
    cid = county_eid("鄞县")
    assert cid in g.entities and g.entities[cid]["type"] == "county"
    assert any(h["eid"] == "minister_范仲淹" for h in county_officials(g, "鄞县"))

