# -*- coding: utf-8 -*-
"""M177 外贸派生记账 `trade_ledger` —— 定向回归（**纯函数、零接线**）。

锁定：① **守恒**（Σ货值 ≡ 总量，含最大余数法的边界）；② **不新增账本**（无 BANNED 键）；
③ **路名纪律**（∈ `state.prefectures`，防 `黔中路` 幽灵路）；④ **不臆造**（无可用路/政权/总量 ⇒
`legs=[]` + reason）；⑤ **只读**（调用前后 state 不变）；⑥ 与 `ROUTE_WATERWAY` 21 vs 20 的
差异**不影响**（本模块只用 `state.prefectures`）。
"""

import copy

from core import commands
from core.domains.economy import trade_ledger as tl


def _state():
    return commands.new_game()


def test_conservation_exact():
    s = _state()
    for total in (1, 7, 123456, 10_000_000, 28_400_000):
        rep = tl.allocate_legs(s, total, month=100)
        assert rep["legs"], total
        assert sum(x["goods_value"] for x in rep["legs"]) == total, total
        assert tl.assert_guards(rep["legs"], s, total) == []


def test_no_parallel_ledger_and_route_discipline():
    s = _state()
    rep = tl.allocate_legs(s, 999_999, month=5)
    for leg in rep["legs"]:
        assert not (tl.BANNED_KEYS & set(leg))
        assert leg["route"] in s.prefectures
        assert set(leg) <= set(tl.LEG_FIELDS)


def test_missing_is_not_zero():
    s = _state()
    for bad_total in (0, -1, None):
        rep = tl.allocate_legs(s, bad_total, month=1)
        assert rep["legs"] == [] and rep["reason"], bad_total
    # 全部路产能为 0 的假状态 ⇒ 也不分配（不臆造）
    class _S:
        prefectures = {"路A": {"yields": {}}, "路B": {"yields": {"盐": 0}}}
    rep2 = tl.allocate_legs(_S(), 1000, month=1)
    assert rep2["legs"] == [] and rep2["reason"]


def test_readonly_and_weight_basis_documented():
    s = _state()
    before = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    rep = tl.allocate_legs(s, 500_000, month=3)
    assert "产能" in rep["weight_basis"] and "不臆造" in rep["weight_basis"]
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before
