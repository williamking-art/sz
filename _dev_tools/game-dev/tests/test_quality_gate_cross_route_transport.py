# -*- coding: utf-8 -*-
"""质量放行门 · 跨路交易必走交通（2026-10-18 用户要求）。

用户原话：「市场交易也要有交通，同州府的不管，但跨路的也要」。
现状口径（本门钉住，防回归）：
1. **跨路**：`material_trade.sell_material_across` 立刻扣源、建**在途批次**，目的货栈到期才入账；
   同路调用被拒（`same_circuit`），必须走同路市集；
2. **同路**：`material_trade_ops.trade_material` 瞬时成交（`trade_goods` 就地转移），**不产生在途批次**；
   跨路调用被 C-c 护栏拒绝；
3. 钱：跨路成交时由 `transfer_money` 立即划转（钱货两清的一方先付），货在途——**本门口径**；
4. 若将来把粮搬进 goods，同类规则同样适用（本门不覆盖，等 G-3 迁移后补）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.material_holding import (  # noqa: E402
    MATERIAL_DIMS, goods_add, goods_amount, merchant_goods)
from core.foundation.ledger.money_transport import money_transit_total  # noqa: E402
from core.transport import in_transit  # noqa: E402

SELLER_ROUTE, BUYER_ROUTE = "京畿路", "京西路"
SELLER_SEAT = "京畿路|开封府"
BUYER_SEAT = "京西路|河南府"


def _dim():
    dims = sorted(MATERIAL_DIMS)
    assert dims, "MATERIAL_DIMS 为空 ⇒ 门是空转"
    return dims[0]


def _state():
    from core.commands import new_game

    return new_game()


def _seed(state, route, seat, dim, qty):
    g = merchant_goods(state, route)
    assert g is not None, "商人货栈缺失"
    goods_add(g, dim, int(qty), seat_id=seat)
    return int(goods_amount(g, dim) or 0)


def _advance(state, months):
    for _ in range(int(months)):
        if int(getattr(state, "month", 1)) >= 12:
            state.month = 1
            state.year = int(getattr(state, "year", 1101)) + 1
        else:
            state.month = int(getattr(state, "month", 1)) + 1


def test_cross_route_goods_are_in_transit_not_instant():
    from core.material_trade import sell_material_across
    from core.transport import arrive_due

    s = _state()
    dim = _dim()
    _seed(s, SELLER_ROUTE, SELLER_SEAT, dim, 100)
    before_buyer = int(goods_amount(merchant_goods(s, BUYER_ROUTE), dim) or 0)
    n_batches = len(in_transit(s))
    r = sell_material_across(s, seller_route=SELLER_ROUTE, buyer_route=BUYER_ROUTE,
                             dim=dim, qty=10, price=1.0,
                             frm_seat=SELLER_SEAT, to_seat=BUYER_SEAT)
    assert r.get("ok"), r
    assert len(in_transit(s)) == n_batches + 1, "跨路成交必须建在途批次（不得瞬移）"
    assert int(goods_amount(merchant_goods(s, BUYER_ROUTE), dim) or 0) == before_buyer, \
        "未到期不得入买方货栈"
    _advance(s, int(getattr(s, "turn", 0) or 0) + 3)  # 至少 3 个月，覆盖多数路段
    arrive_due(s)
    assert int(goods_amount(merchant_goods(s, BUYER_ROUTE), dim) or 0) >= before_buyer + 10, \
        "到期必须入账"


def test_same_seat_is_rejected_but_same_route_other_seat_transports():
    """判据按**治所**：同路同治所 ⇒ 拒办（市集内瞬时）；同路不同治所 ⇒ 走交通。"""
    from core.material_trade import sell_material_across
    from core.transport import in_transit

    s = _state()
    dim = _dim()
    _seed(s, SELLER_ROUTE, SELLER_SEAT, dim, 100)
    r = sell_material_across(s, seller_route=SELLER_ROUTE, buyer_route=SELLER_ROUTE,
                             dim=dim, qty=10, price=1.0,
                             frm_seat=SELLER_SEAT, to_seat=SELLER_SEAT)
    assert not r.get("ok") and r.get("reason") == "same_seat", r

    # 同路不同治所（开封府 → 郑州，同属京畿路）⇒ 必须建在途批次
    other = "京畿路|郑州"
    n0 = len(in_transit(s))
    r2 = sell_material_across(s, seller_route=SELLER_ROUTE, buyer_route=SELLER_ROUTE,
                              dim=dim, qty=10, price=1.0,
                              frm_seat=SELLER_SEAT, to_seat=other)
    assert r2.get("ok"), r2
    assert len(in_transit(s)) == n0 + 1, "同路跨治所也必须走交通（不得瞬移）"


def test_same_route_market_is_instant_and_creates_no_batch():
    from core.domains.economy.material_trade_ops import trade_material
    from core.foundation.ledger.material_holding import merchant_of

    s = _state()
    dim = _dim()
    _seed(s, SELLER_ROUTE, SELLER_SEAT, dim, 100)
    merchant = merchant_of(s, SELLER_ROUTE)
    buyer = s.prefectures[SELLER_ROUTE]["pops"].get("士绅")
    assert isinstance(buyer, dict), "测试前置：士绅 POP 存在"
    n_batches = len(in_transit(s))
    r = trade_material(s, buyer_pop=buyer, seller_pop=merchant, dim=dim,
                       qty=5, price=1.0, purpose="resale")
    assert r.get("ok"), r
    assert len(in_transit(s)) == n_batches, "同路成交不得产生运输批次"


def test_money_transport_is_independent_of_goods_transport():
    """钱的在途与货的在途是两个队列：跨路货款立即划转，不产生「钱在途」。"""
    from core.material_trade import sell_material_across

    s = _state()
    dim = _dim()
    _seed(s, SELLER_ROUTE, SELLER_SEAT, dim, 100)
    before = money_transit_total(s)
    r = sell_material_across(s, seller_route=SELLER_ROUTE, buyer_route=BUYER_ROUTE,
                             dim=dim, qty=10, price=1.0,
                             frm_seat=SELLER_SEAT, to_seat=BUYER_SEAT)
    assert r.get("ok"), r
    assert money_transit_total(s) == before, "货款按现有口径立即划转，不产生钱在途"