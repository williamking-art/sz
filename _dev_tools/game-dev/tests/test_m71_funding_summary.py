# -*- coding: utf-8 -*-
"""M71 `funding_summary`（多时点取证入口）—— 定向回归。

锁定：① 载体表含**正确分母**的到位率（M69/M70 修完后需求为 28,400,000 级）；② G-4 官营/民营分位齐备；
③ 不可读 ⇒ `None`（缺失≠0）；④ 只读。
"""

import copy

from core import commands
from core.domains.economy import workshop_fund_shadow as wfs
from core.domains.economy import owner_candidates_shadow as ocs


def test_summary_shape_and_values_at_opening():
    s = commands.new_game()
    rep = wfs.funding_summary(s)
    need = ocs.procure_need(s)
    # M196（产能批）：补座后基线——21 座新丝坊（配方 丝 10000）使开局采购需求 28,400,000 → 70,400,000。
    # 该值是 Σ各作坊 `recipe_cost` 的合计（无法由单一常量派生）⇒ 更新基线并注明来源。
    assert rep["procure_need"] == need["value"] == 70_400_000
    assert rep["unreadable_workshops"] == 0
    keys = {c["key"] for c in rep["carriers"]}
    assert keys >= {"state_treasury", "imperial", "pop_gentry", "pop_merchant", "local_route"}
    for side in ("gov", "merchant"):
        g = rep["g4"][side]
        assert g["routes"] >= 18 and g["min"] is not None and g["max"] is not None
        assert g["full"] <= g["routes"]


def test_summary_is_readonly():
    s = commands.new_game()
    before = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    wfs.funding_summary(s)
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before


def test_summary_is_honest_when_unreadable(monkeypatch):
    """需求不可读 ⇒ `procure_need=None`，且载体到位率随之 `None`（**不回落 0**）。"""
    import core.domains.economy.owner_candidates_shadow as m
    monkeypatch.setattr(m, "procure_need",
                        lambda state: {"value": None, "unreadable": [], "unreadable_count": 1,
                                       "reason": "测试"})
    s = commands.new_game()
    rep = wfs.funding_summary(s)
    assert rep["procure_need"] is None
    assert all(c["cover"] is None for c in rep["carriers"])
