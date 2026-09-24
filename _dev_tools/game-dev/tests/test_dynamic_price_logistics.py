# -*- coding: utf-8 -*-
"""批 7 · 动态价格 + 物流分账 + 14 维原料回归。

断言：
  1) 动态商品价：基准 × clamp(demand/supply, 0.5, 1.5)，月涨跌 ≤ ±20%；
  2) 供需比钳位生效（极低/极高需求）；
  3) 物流费率：距离档位 + 地形 + 战乱乘数；
  4) 民间物流：buyer −fee、merchant +fee（守恒）；付不起 → abandoned；
  5) 政府物流：treasury −fee、carrier +fee（守恒）；
  6) 14 维原料常量就位（含金/铜/银/牲畜/马/药材）；
  7) 金属 ≠ 钱边界声明（RAW_DIMS_14 含金属但不折算 treasury）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import EXTERNAL_ECON, RESOURCE_DIMS, RAW_DIMS  # noqa: E402
from content.data_constants import RAW_DIMS_14  # noqa: E402
from core.dynamic_price import (  # noqa: E402
    update_goods_prices, logistics_rate, civil_logistics, gov_logistics,
)

CFG = EXTERNAL_ECON


def test_14_raw_dims_declared():
    """14 维原料表就位（含金属四 + 农产五）。"""
    assert len(RAW_DIMS_14) == 14
    for dim in ("石", "木", "粮", "麻", "丝", "金", "铁", "铜", "银",
                "果", "牲畜", "药材", "马", "蔗"):
        assert dim in RAW_DIMS_14
    # 宋侧 RAW_DIMS 已扩到含新维
    for dim in ("gold", "copper", "silver", "livestock", "horses", "herbs"):
        assert dim in RAW_DIMS, f"宋侧 RAW_DIMS 缺 {dim}"
    # RESOURCE_DIMS 覆盖 RAW_DIMS
    for dim in RAW_DIMS:
        assert dim in RESOURCE_DIMS


def test_dynamic_price_clamp_and_cap():
    """动态价：钳位 [0.5, 1.5]、月涨跌 ≤ ±20%。"""
    base = {"布": 1.0, "绸": 6.0}
    cfg = {"GOODS_BASE_PRICE": base, "PRICE_BAND": (0.5, 1.5), "PRICE_MONTH_CAP": 0.20}
    # 需求远大于供给 → ratio 钳到 1.5
    out = update_goods_prices({"布": 1.0, "绸": 6.0},
                              demand={"布": 1000, "绸": 1000},
                              supply={"布": 1, "绸": 1},
                              produced={}, cfg=cfg)
    assert out["布"] <= 1.0 * 1.5 * 1.01, f"布价超钳位：{out['布']}"
    # 月涨跌 ≤ ±20%
    prev = {"布": 1.0}
    out2 = update_goods_prices(prev, demand={"布": 0}, supply={"布": 10000},
                               produced={}, cfg=cfg)
    assert 1.0 * 0.8 * 0.99 <= out2["布"] <= 1.0 * 1.2 * 1.01, (
        f"月涨跌超 ±20%：prev=1.0 → {out2['布']}")
    # 供给为 0 → 价格上限
    out3 = update_goods_prices({"布": 1.0}, demand={"布": 100},
                               supply={"布": 0}, produced={}, cfg=cfg)
    assert out3["布"] >= 1.0 * 1.2 * 0.99, f"供给 0 应推价：{out3['布']}"


def test_logistics_rate_tiers():
    """物流费率：距离档位 + 地形 + 战乱乘数。"""
    assert logistics_rate(10, "平川", False, CFG) == pytest.approx(0.5)
    assert logistics_rate(200, "平川", False, CFG) == pytest.approx(1.5)
    assert logistics_rate(500, "平川", False, CFG) == pytest.approx(3.0)
    assert logistics_rate(2000, "平川", False, CFG) == pytest.approx(6.0)
    assert logistics_rate(5000, "平川", False, CFG) == pytest.approx(10.0)
    # 地形乘数
    assert logistics_rate(200, "山越", False, CFG) == pytest.approx(1.5 * 1.5)
    assert logistics_rate(200, "草原", False, CFG) == pytest.approx(1.5 * 1.2)
    # 战乱乘数
    assert logistics_rate(200, "平川", True, CFG) == pytest.approx(1.5 * 1.5)


def test_civil_logistics_conserves():
    """民间物流：buyer −fee、merchant +fee（守恒）；付不起 → abandoned。"""
    buyer = {"wealth": 10000}
    merchant = {"wealth": 0}
    res = civil_logistics(buyer, merchant, quantity=50000,
                          distance_km=200, cfg=CFG)
    assert not res["abandoned"]
    assert res["fee"] > 0
    assert buyer["wealth"] == 10000 - res["fee"]
    assert merchant["wealth"] == res["fee"], "运费守恒"
    # 付不起
    buyer2 = {"wealth": 0}
    merchant2 = {"wealth": 0}
    res2 = civil_logistics(buyer2, merchant2, quantity=50000,
                           distance_km=200, cfg=CFG)
    assert res2["abandoned"]
    assert res2["fee"] == 0
    assert buyer2["wealth"] == 0 and merchant2["wealth"] == 0


def test_gov_logistics_conserves():
    """政府物流：treasury −fee、carrier +fee（守恒）。"""
    treasury = {"amount": 50000}
    carrier = {"wealth": 0}
    res = gov_logistics(treasury, carrier, quantity=100000,
                        distance_km=500, cfg=CFG)
    assert not res["abandoned"]
    assert res["fee"] > 0
    assert treasury["amount"] == 50000 - res["fee"]
    assert carrier["wealth"] == res["fee"]
    # treasury 不足
    t2 = {"amount": 0}
    c2 = {"wealth": 0}
    res2 = gov_logistics(t2, c2, quantity=100000, distance_km=500, cfg=CFG)
    assert res2["abandoned"]


def test_metal_not_money():
    """金属 ≠ 钱（§4.3）：金/银/铜/铁在 RAW_DIMS_14 但不得自动折算 treasury。"""
    for dim in ("金", "银", "铜", "铁"):
        assert dim in RAW_DIMS_14
    # 边界声明在模块 docstring / RAW_DIMS_14 注释（代码事实）
    import inspect
    import core.dynamic_price as dp
    src = inspect.getsource(dp)
    assert "金属" in src and "treasury" in src, "金属 ≠ 钱边界声明须在代码中"


def test_song_raw_dims_expanded():
    """宋侧 RAW_DIMS 已扩到 15 维（原 9 + 金/铜/银/牲畜/马/药材）。"""
    assert len(RAW_DIMS) >= 15
    assert "gold" in RAW_DIMS and "copper" in RAW_DIMS and "silver" in RAW_DIMS
    assert "livestock" in RAW_DIMS and "horses" in RAW_DIMS and "herbs" in RAW_DIMS
