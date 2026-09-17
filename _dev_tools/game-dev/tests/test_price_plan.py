# -*- coding: utf-8 -*-
"""物价方案断言测试（蔡权衡 8 项）：常平回收守恒 / 换界销毁记 statistics / 熔化 / 俸禄指数化 / 物价区间。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import (  # noqa: E402
    PRICE_TARGET_SUPER, PRICE_FLOOR_HARD, PRICE_CEIL_HARD, MELT_RATE,
    JIAOZI_TERM, JIAOZI_REDEEM_FEE, CHANGPING_CAP_RATIO,
    CHANGPING_BUY_BUDGET_RATIO, CHANGPING_SELL_RATIO,
)
from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def test_constants():
    """物价方案常量（T9 定稿）：目标 [1.2,2.5]、断言 [0.8,2.8]、常平扩容、界制、熔化。"""
    assert PRICE_TARGET_SUPER == (1.2, 2.5)
    assert PRICE_FLOOR_HARD == 0.8 and PRICE_CEIL_HARD == 2.8
    assert CHANGPING_CAP_RATIO == 1.0
    assert CHANGPING_BUY_BUDGET_RATIO == 0.50
    assert CHANGPING_SELL_RATIO == 0.60
    assert JIAOZI_TERM == 36 and abs(JIAOZI_REDEEM_FEE - 0.05) < 1e-9
    assert abs(MELT_RATE - 0.001) < 1e-9


def test_coin_melt_pop_wealth():
    """私铸熔化真实化：POP 铜钱 wealth 0.1%/月扣减（不碰国库/内帑）。"""
    from core.settlement_steps import _settle_melt_copper
    s = _new_state()
    t0 = s.treasury
    it0 = s.imperial_treasury
    w0 = sum(p["pops"]["农"]["wealth"] for p in s.prefectures.values())
    _settle_melt_copper(s, [])
    w1 = sum(p["pops"]["农"]["wealth"] for p in s.prefectures.values())
    assert w1 < w0   # 熔化扣减
    assert s.treasury == t0 and s.imperial_treasury == it0   # 国家持币不熔化


def test_jiaozi_redeem_statistics():
    """换界销毁：到界按在发额 5% 销毁并记 statistics。"""
    from core.settlement_steps import _settle_jiaozi_cycle
    s = _new_state()
    s.jiaozi["issued"] = 10_000_000
    s.jiaozi["age"] = JIAOZI_TERM - 1
    s.statistics.setdefault("jiaozi_redeemed", 0)
    issued0 = s.jiaozi["issued"]
    _settle_jiaozi_cycle(s, [])
    assert s.jiaozi["issued"] == issued0 - int(issued0 * JIAOZI_REDEEM_FEE)
    assert s.statistics.get("jiaozi_redeemed", 0) >= int(issued0 * JIAOZI_REDEEM_FEE)


def test_changping_recycle_conservation():
    """常平回收守恒：常平储与地方府库反向变动（平粜储减府库增 / 平籴储增府库减——钱粮互换，ΣΔ==0）。"""
    from core.settlement_steps import _settle_granary
    s = _new_state()
    p = s.prefectures["两浙路"]
    p["changping_stock"] = 100_000
    p["local_treasury"] = 200_000
    cs0, lt0 = p["changping_stock"], p["local_treasury"]
    _settle_granary(s, [])
    d_cs = p["changping_stock"] - cs0
    d_lt = p["local_treasury"] - lt0
    # 守恒方向：常平储与府库反向（平粜储减府库增 / 平籴储增府库减）
    assert (d_cs > 0 and d_lt < 0) or (d_cs < 0 and d_lt > 0), \
        f"常平回收方向异常：储{d_cs:+d} 府库{d_lt:+d}"


def test_price_level_range_replay():
    """物价水平全程 ∈[0.8,2.8]（防触 3.0 恶性通胀）——60 月常规回放。"""
    from core.settlement import run_monthly_settlement
    s = _new_state()
    price_min, price_max = 99.0, 0.0
    for m in range(60):
        run_monthly_settlement(s, seed_offset=2026)
        price_min = min(price_min, s.price_level)
        price_max = max(price_max, s.price_level)
    assert PRICE_FLOOR_HARD <= price_min and price_max <= PRICE_CEIL_HARD, \
        f"60月物价水平区间 [{price_min:.2f},{price_max:.2f}] 超 [0.8,2.8]"


def test_imperial_treasury_not_recycled():
    """内帑膨胀不触发回收（设计保留）：换界/熔化不碰内帑。"""
    from core.settlement_steps import _settle_jiaozi_cycle, _settle_melt_copper
    s = _new_state()
    s.imperial_treasury = 200_000_000   # 2 亿（膨胀）
    it0 = s.imperial_treasury
    s.jiaozi["issued"] = 5_000_000
    s.jiaozi["age"] = JIAOZI_TERM - 1
    _settle_jiaozi_cycle(s, [])
    _settle_melt_copper(s, [])
    assert s.imperial_treasury == it0   # 内帑不参与回收（设计）
