# -*- coding: utf-8 -*-
"""质量放行门 · 钱走交通层（G-3 P4a）。

用户 2026-10-18：「钱也要能押运，这样交子的存在就有意义了」。
本门钉住：立刻扣源 / 余额不足不建批次 / 未到不入账 / 到期入账 / 守恒 / 非法参数显式失败。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.money_transport import (  # noqa: E402
    arrive_money_due, dispatch_money, money_in_transit, money_transit_total)

CAPITAL = "京畿路|开封府"
DEST = "京西路|河南府"


def _route_of(seat_id: str) -> str:
    return seat_id.split("|", 1)[0]


def _seat(state, seat_id: str):
    p = (state.prefectures or {}).get(_route_of(seat_id)) or {}
    seats = p.get("seats") or {}
    return seats.get(seat_id)


def _state():
    from core.commands import new_game

    s = new_game()
    dst = _seat(s, DEST)
    assert isinstance(dst, dict), f"测试前置：目的地治所 {DEST} 必须存在"
    dst["local_treasury"] = 1000
    return s


def _advance_months(state, months: int):
    """只推年月（不动结算），专测在途到期语义。"""
    for _ in range(int(months)):
        if int(getattr(state, "month", 1)) >= 12:
            state.month = 1
            state.year = int(getattr(state, "year", 1101)) + 1
        else:
            state.month = int(getattr(state, "month", 1)) + 1


def test_dispatch_deducts_and_records_in_transit():
    s = _state()
    t0 = int(s.treasury)
    r = dispatch_money(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=500, to_seat=DEST)
    assert r["ok"], r
    assert int(s.treasury) == t0 - 500, "发货必须立刻扣源"
    assert money_transit_total(s) == 500
    assert all(b.get("cargo_kind") == "money" for b in money_in_transit(s))


def test_insufficient_funds_builds_no_batch():
    s = _state()
    before = money_transit_total(s)
    r = dispatch_money(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=int(s.treasury) + 1, to_seat=DEST)
    assert not r["ok"] and r["reason"] == "insufficient_funds"
    assert money_transit_total(s) == before, "失败不得留下在途批次"


def test_not_due_is_not_credited():
    s = _state()
    dst = _seat(s, DEST)
    dst0 = int(dst["local_treasury"])
    r = dispatch_money(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=500, to_seat=DEST)
    assert r["ok"], r
    assert int(r["days"]) > 0, "跨路必须有天数（不瞬移）"
    assert arrive_money_due(s) == [], "未到期不得入账"
    assert int(dst["local_treasury"]) == dst0


def test_due_is_credited_and_conserved():
    s = _state()
    src = _seat(s, CAPITAL)
    assert isinstance(src, dict), "测试前置：源治所必须存在"
    src["local_treasury"] = 5000
    dst = _seat(s, DEST)
    total0 = 5000 + int(dst["local_treasury"])

    r = dispatch_money(s, frm_kind="local_treasury", to_kind="local_treasury",
                       amount=500, frm_seat=CAPITAL, to_seat=DEST)
    assert r["ok"], r
    days = int(r["days"])
    assert days > 0
    assert int(src["local_treasury"]) == 4500
    assert int(dst["local_treasury"]) == 1000
    assert 4500 + 1000 + money_transit_total(s) == total0

    _advance_months(s, days)
    arrived = arrive_money_due(s)
    assert len(arrived) == 1, f"应有一批到账：{arrived}"
    assert int(dst["local_treasury"]) == 1500
    assert money_transit_total(s) == 0
    assert 4500 + 1500 == total0, "到账后总量必须仍等于期初"


def test_bad_holder_or_route_is_explicit():
    s = _state()
    assert not dispatch_money(s, frm_kind="somewhere", to_kind="local_treasury",
                              amount=10, to_seat=DEST)["ok"]
    r = dispatch_money(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=10, to_seat="不存在路|不存在州")
    assert not r["ok"] and r["reason"] == "unknown_destination"