# -*- coding: utf-8 -*-
"""质量放行门 · 多段运输 dispatch_along（G-3 P5c）。

语义：按最短路径 + 指定方式建**一个**在途批次；源立刻扣、钱只在终点到期入账、
中途不落账户（刻意简化，避免中转仓平账）；超出单批运力 ⇒ 明确 `over_capacity` 并给分批数。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.money_transport import (  # noqa: E402
    arrive_money_due, dispatch_along, money_in_transit, money_transit_total)

CAPITAL = "京畿路|开封府"
JIANGNAN = "两浙路|杭州"
SHANXI = "陕西路|熙州"


def _state():
    from core.commands import new_game

    s = new_game()
    dst = s.prefectures["两浙路"]["seats"][JIANGNAN]
    dst["local_treasury"] = 1000
    return s


def _advance(state, months):
    for _ in range(int(months)):
        if int(getattr(state, "month", 1)) >= 12:
            state.month = 1
            state.year = int(getattr(state, "year", 1101)) + 1
        else:
            state.month = int(getattr(state, "month", 1)) + 1


def test_land_dispatch_records_path_and_arrives_at_end():
    s = _state()
    dst = s.prefectures["两浙路"]["seats"][JIANGNAN]
    src0 = int(s.treasury)
    dst0 = int(dst["local_treasury"])
    r = dispatch_along(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=400, to_seat=JIANGNAN, mode="land")
    assert r["ok"], r
    assert int(s.treasury) == src0 - 400, "源必须立刻扣"
    batch = r["batch"]
    assert batch["mode"] == "land" and batch["path"][0] == CAPITAL and batch["path"][-1] == JIANGNAN
    assert batch["legs"], "多段批次必须带分段时刻表"
    assert int(dst["local_treasury"]) == dst0, "未到不得入账"
    assert money_transit_total(s) == 400
    _advance(s, int(r["days"]))
    arrived = arrive_money_due(s)
    assert len(arrived) == 1, arrived
    assert int(dst["local_treasury"]) == dst0 + 400
    assert money_transit_total(s) == 0
    assert src0 - 400 + dst0 + 400 == src0 + dst0, "守恒"


def test_water_takes_longer_but_same_delivery():
    s = _state()
    r = dispatch_along(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=400, to_seat=JIANGNAN, mode="water")
    assert r["ok"], r
    assert r["mode"] == "water"
    assert r["days"] >= 1
    assert r["capacity"] >= 1000, "水运运力应显著大于陆运"


def test_unavailable_mode_is_explicit():
    s = _state()
    r = dispatch_along(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=10, to_seat=SHANXI, mode="water")
    assert not r["ok"] and r["reason"] == "not_waterway", r


def test_over_capacity_reports_batches_needed():
    s = _state()
    r = dispatch_along(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=500_000, to_seat=JIANGNAN, mode="land")
    assert not r["ok"] and r["reason"] == "over_capacity", r
    assert r["capacity"] == 500 and r["batches_needed"] == 1000, r


def test_insufficient_funds_and_escort_fee():
    s = _state()
    # 先造「余额不足」：把国库压到 600（>500 单批运力、< 需要的 2000）
    s.treasury = 600
    r = dispatch_along(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=800, to_seat=JIANGNAN, mode="land")
    assert not r["ok"] and r["reason"] == "over_capacity", r
    r2 = dispatch_along(s, frm_kind="treasury", to_kind="local_treasury",
                        amount=500, to_seat=JIANGNAN, mode="land", escort_fee=200)
    assert not r2["ok"] and r2["reason"] == "insufficient_funds", r2
    src0 = int(s.treasury)
    ok = dispatch_along(s, frm_kind="treasury", to_kind="local_treasury",
                        amount=100, to_seat=JIANGNAN, mode="land", escort_fee=10)
    assert ok["ok"], ok
    assert int(s.treasury) == src0 - 110, "押运费必须一并从源扣除"
    assert int(ok["batch"]["escort_fee"]) == 10
    assert money_in_transit(s)[0]["qty"] == 100, "押运费不得计入在途本金"