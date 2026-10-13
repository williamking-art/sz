# -*- coding: utf-8 -*-
"""M68 G-4 **逐路资金到位率**（只读）—— 定向回归。

锁定：官营看**地方府库真账**、民营看**本路商人 wealth** · 需求 = Σ`recipe_cost`（缺价维 ⇒ `None`）·
任一侧不可读 ⇒ 到位率 `None`（**缺失≠0**）· 其它路的作坊**不串路** · **零写入** · 真实新局 20 路逐路有读数。
"""

import copy
import types

from core.domains.economy import workshop_fund_shadow as wfs


def _state(workshops, routes=("路A",)):
    st = types.SimpleNamespace()
    st.workshops = workshops
    st.prefectures = {}
    for r in routes:
        st.prefectures[r] = {"name": r,
                             "seats": {"%s|首府" % r: {"pops": {}, "local_treasury": 1000}}}
    return st


def test_gov_and_merchant_pools_are_separate(monkeypatch):
    import core.domains.economy.workshop_fund_shadow as m
    monkeypatch.setattr(m, "recipe_cost", lambda state, wid: {"cost": 100})
    st = _state({"酒坊_路A_1": {"owner": "local:路A"},
                 "麻坊_路A_2": {"owner": "pop:路A:商人"},
                 "酒坊_路B_1": {"owner": "local:路B"}}, routes=("路A", "路B"))
    rep = m.owner_funding_by_route(st)
    a = next(r for r in rep["routes"] if r["route"] == "路A")
    assert a["gov"]["workshops"] == 1 and a["gov"]["need"] == 100
    assert a["merchant"]["workshops"] == 1 and a["merchant"]["need"] == 100
    b = next(r for r in rep["routes"] if r["route"] == "路B")
    assert b["gov"]["workshops"] == 1 and b["merchant"]["workshops"] == 0   # **不串路**
    assert b["merchant"]["need"] is None


def test_missing_pool_yields_none_not_zero(monkeypatch):
    import core.domains.economy.workshop_fund_shadow as m
    monkeypatch.setattr(m, "recipe_cost", lambda state, wid: {"cost": 100})
    st = _state({"麻坊_路A_1": {"owner": "pop:路A:商人"}})
    st.prefectures["路A"]["pops"] = {}                        # 无商人 POP ⇒ wealth 不可读
    rep = m.owner_funding_by_route(st)
    a = rep["routes"][0]
    assert a["merchant"]["cover"] is None                     # **缺失≠0**
    assert a["merchant"]["pool"] is None


def test_unreadable_recipe_is_reported(monkeypatch):
    import core.domains.economy.workshop_fund_shadow as m
    monkeypatch.setattr(m, "recipe_cost",
                        lambda state, wid: {"cost": None if wid.startswith("坏") else 50})
    st = _state({"酒坊_路A_1": {"owner": "local:路A"}, "坏坊_路A_2": {"owner": "local:路A"}})
    rep = m.owner_funding_by_route(st)
    a = rep["routes"][0]
    assert a["gov"]["workshops"] == 1 and a["gov"]["need"] == 50
    assert a["unreadable_recipes"] == ["坏坊_路A_2"]          # **留痕**，不当 0


def test_rows_sorted_worst_first(monkeypatch):
    import core.domains.economy.workshop_fund_shadow as m
    monkeypatch.setattr(m, "recipe_cost", lambda state, wid: {"cost": 1000})
    st = _state({"酒坊_路A_1": {"owner": "local:路A"},
                 "酒坊_路B_1": {"owner": "local:路B"}}, routes=("路A", "路B"))
    st.prefectures["路B"]["seats"]["路B|首府"]["local_treasury"] = 100_000   # B 路富
    rep = m.owner_funding_by_route(st)
    assert rep["worst"]["route"] == "路A"                     # 最差排最前
    assert rep["routes"][0]["gov"]["cover"] <= rep["routes"][-1]["gov"]["cover"]


def test_real_game_has_per_route_readings():
    from core import commands
    s = commands.new_game()
    rep = wfs.owner_funding_by_route(s)
    assert rep["route_count"] >= 18, rep["route_count"]
    row = rep["routes"][0]
    assert row["gov"]["workshops"] >= 0 and row["merchant"]["workshops"] >= 0
    assert rep["worst"] is not None


def test_readonly():
    from core import commands
    s = commands.new_game()
    before = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    wfs.owner_funding_by_route(s)
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before
