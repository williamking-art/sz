# -*- coding: utf-8 -*-
"""G-5 治所级价格发现：键格式、回落、缺失≠0、向后兼容。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

from core.market_price import (discover_seat_price, pref_good_key,
                                record_seat_trade_price, seat_good_key)

J = 'JINGJI'
SEAT = 'KAIFENG'
MU = '\u6728'          # 必须用**真实维名**：_base_price 查 MATERIAL_PRICE_BASE


class _S:
    pass


def test_seat_key_format():
    assert seat_good_key(J, SEAT, MU) == 'JINGJI|KAIFENG|木'


def test_seat_key_normalises_full_seat_id():
    assert seat_good_key(J, 'JINGJI|KAIFENG', MU) == seat_good_key(J, 'KAIFENG', MU)


def test_seat_none_falls_back_to_route_key():
    assert seat_good_key(J, None, MU) == pref_good_key(J, MU)


def test_record_and_read_seat_price():
    s = _S()
    v = record_seat_trade_price(s, MU, paid=100.0, qty=10.0, pref=J, seat=SEAT)
    assert v == 10.0, v
    assert s.dynamic_prices['JINGJI|KAIFENG|木'] == 10.0


def test_record_zero_qty_returns_none():
    s = _S()
    assert record_seat_trade_price(s, MU, paid=10.0, qty=0.0, pref=J, seat=SEAT) is None
    assert not hasattr(s, 'dynamic_prices')


def test_zero_avg_not_written_as_price():
    s = _S()
    assert record_seat_trade_price(s, MU, paid=0.0, qty=10.0, pref=J, seat=SEAT) is None
    assert 'JINGJI|KAIFENG|木' not in getattr(s, 'dynamic_prices', {})


def test_old_route_key_readable_as_fallback():
    """**向后兼容**：旧档只有 `"路|商品"` 键时，治所读价应回落到它。"""
    s = _S()
    s.dynamic_prices = {pref_good_key(J, MU): 7.0}
    r = discover_seat_price(dim=MU, pref=J, seat=SEAT,
                           demand_qty=10.0, supply_qty=10.0, prev_price=None)
    assert r['price'] is not None, r
    assert r['seat'] == SEAT and r['pref'] == J


def test_missing_demand_supply_returns_unpriceable():
    """缺失 ⇒ **不可定价**（`price is None`），不是价格 0、也不是基准价。"""
    s = _S()
    r = discover_seat_price(dim=MU, pref=J, seat=SEAT,
                           demand_qty=None, supply_qty=None, prev_price=5.0)
    assert r['price'] is None, r


def test_zero_supply_is_unpriceable():
    s = _S()
    r = discover_seat_price(dim=MU, pref=J, seat=SEAT,
                           demand_qty=10.0, supply_qty=0.0, prev_price=5.0)
    assert r['price'] is None, r


def test_shortage_raises_price_within_bounds():
    """供给不足 ⇒ 涨价；且**有界**（不无限放大）。"""
    s = _S()
    r = discover_seat_price(dim=MU, pref=J, seat=SEAT,
                           demand_qty=100.0, supply_qty=10.0, prev_price=5.0)
    assert r['price'] is not None and r['price'] > 5.0, r
    assert r['pressure'] <= 2.0, r