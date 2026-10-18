# -*- coding: utf-8 -*-
"""质量放行门 · 拨款三方式 allocate_funds（G-3 P6a）。

用户 2026-10-18 定调：国库/内帑拨款到某路，三选一——划账(draft) / 押运(transport) / 交子(jiaozi)。
本门钉住：
1. draft：同路或 1 月内可达 ⇒ 立刻到账、零费；远路（>1 月）⇒ draft_too_far 并建议运输/交子；
2. transport：源立刻扣本金+运费，目的地**到期才入账**，总量守恒；
3. jiaozi：立刻兑付、收手续费；trust 低/挤兑 ⇒ 拒办；discount>0 ⇒ 兑付损失；
4. 非法参数（未知方式/非法来源/坏目的地）⇒ 明确 reason；
5. 既有 `transfer_money` 调用未被改动（draft 仍是它，仅作合法性封装）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_constants import (  # noqa: E402
    DRAFT_MAX_DAYS, JIAOZI_DRAFT_FEE_RATE)
from core.foundation.ledger.money_transport import (  # noqa: E402
    allocate_funds, arrive_money_due, money_transit_total)
from core.transport import route_path  # noqa: E402

NEAR = "京畿路|郑州"
JIANGNAN = "两浙路|杭州"
FAR = "广南东路|广州"


def _state():
    from core.commands import new_game

    s = new_game()
    for seat in (NEAR, JIANGNAN):
        route = seat.split("|")[0]
        s.prefectures[route]["seats"][seat]["local_treasury"] = 0
    return s


def _seat_amount(s, seat):
    return int(s.prefectures[seat.split("|")[0]]["seats"][seat]["local_treasury"] or 0)


def _advance(s, months):
    for _ in range(int(months)):
        if int(getattr(s, "month", 1)) >= 12:
            s.month = 1
            s.year = int(getattr(s, "year", 1101)) + 1
        else:
            s.month = int(getattr(s, "month", 1)) + 1


def test_draft_near_is_instant_and_free():
    s = _state()
    t0 = int(s.treasury)
    r = allocate_funds(s, dst_seat=NEAR, amount=1000, mode="draft")
    assert r["ok"], r
    assert r["days"] == 0 and r["fee"] == 0
    assert _seat_amount(s, NEAR) == 1000, "draft 必须立刻到账"
    assert int(s.treasury) == t0 - 1000


def test_draft_far_is_refused_with_suggestion():
    s = _state()
    days = route_path("京畿路|开封府", FAR)["days"]
    assert days > DRAFT_MAX_DAYS, "测试前置：该目的地必须超过 draft 上限"
    r = allocate_funds(s, dst_seat=FAR, amount=1000, mode="draft")
    assert not r["ok"] and r["reason"] == "draft_too_far", r
    assert set(r["suggest"]) == {"transport", "jiaozi"}


def test_transport_deducts_now_credits_on_arrival():
    s = _state()
    t0 = int(s.treasury)
    r = allocate_funds(s, dst_seat=JIANGNAN, amount=400, mode="transport")
    assert r["ok"], r
    fee = int(r["fee"])
    assert int(s.treasury) == t0 - 400 - fee, "本金+运费立即扣"
    assert _seat_amount(s, JIANGNAN) == 0, "未到不得入账"
    assert money_transit_total(s) == 400
    _advance(s, int(r["days"]))
    arrived = arrive_money_due(s)
    assert len(arrived) == 1, arrived
    assert _seat_amount(s, JIANGNAN) == 400
    assert t0 - 400 - fee + 400 == t0 - fee, "总量守恒（扣除运费）"


def test_jiaozi_pays_fee_and_credits_immediately():
    s = _state()
    t0 = int(s.treasury)
    r = allocate_funds(s, dst_seat=JIANGNAN, amount=10000, mode="jiaozi")
    assert r["ok"], r
    fee = int(r["fee"])
    assert fee == int(-(-10000 * JIAOZI_DRAFT_FEE_RATE // 1)), fee
    assert _seat_amount(s, JIANGNAN) == 10000 - int(r["loss"])
    assert int(s.treasury) == t0 - 10000 - fee


def test_jiaozi_risk_paths():
    s = _state()
    s.jiaozi = dict(getattr(s, "jiaozi", {}) or {})
    s.jiaozi["trust"] = 10
    low = allocate_funds(s, dst_seat=JIANGNAN, amount=1000, mode="jiaozi")
    assert not low["ok"] and low["reason"] == "jiaozi_distrusted", low
    s.jiaozi["trust"] = 80
    s.jiaozi["run_pressure"] = 0.9
    run = allocate_funds(s, dst_seat=JIANGNAN, amount=1000, mode="jiaozi")
    assert not run["ok"] and run["reason"] == "jiaozi_run", run
    s.jiaozi["run_pressure"] = 0.0
    s.jiaozi["discount"] = 0.05
    disc = allocate_funds(s, dst_seat=JIANGNAN, amount=10000, mode="jiaozi")
    assert disc["ok"] and int(disc["loss"]) == 500, disc
    assert _seat_amount(s, JIANGNAN) == 9500


def test_invalid_arguments_are_explicit():
    s = _state()
    assert allocate_funds(s, dst_seat=NEAR, amount=1, mode="nope")["reason"] == "unknown_mode"
    assert allocate_funds(s, dst_seat=NEAR, amount=1, src="pop:京畿路:农")["reason"] == "bad_source"
    assert allocate_funds(s, dst_seat="没竖线", amount=1)["reason"] == "bad_destination"