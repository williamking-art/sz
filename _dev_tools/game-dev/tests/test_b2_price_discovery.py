# -*- coding: utf-8 -*-
"""B2 · 价格发现与四类价格口径分离的定向回归（规格 `market-civilian-economy` B2-4/B2-5）

锁定：
- **供需持平不涨价**（中性 1.0）；紧缺涨、过剩跌；上下界饱和；
- **无货不可定价**（返回 `None` ＋ `no_supply`，不返回 ∞ 或 0）；
- **单月涨跌封顶**（复用 `cap_monthly_price`）＋ 绝对边界；
- **基准表不被改写**（动态价写入独立槽）；
- **四类价格分离**：官定价 > 动态成交价 > 基准价，缺失给 `None` 不作 0。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.market_price import (  # noqa: E402
    PRICE_BOUNDS, discover_price, effective_buy_price, price_pressure,
    record_trade_price,
)
from core.settlement import run_monthly_settlement  # noqa: E402


def _state():
    s = GameState("史实")
    init_legacies(s)
    return s


# ====================================================== 供需压力
def test_balanced_market_is_neutral():
    """供需持平 → 压力 1.0（**不涨不跌**）：持平不应涨价。"""
    assert price_pressure(100, 100) == pytest.approx(1.0, abs=1e-9)
    assert price_pressure(1, 1) == pytest.approx(1.0, abs=1e-9)


def test_shortage_raises_pressure_sufficient_supply_is_neutral():
    """缺口推高价格；**供给能满足期望需求时为基准价**（B2-R2 修正口径）。

    旧口径把"可售供给"当分母，导致"有货"被误判成"过剩"而系统性压价——
    已废止。现分母是**期望需求**：供给越能满足需求，价格越接近基准。
    """
    assert price_pressure(500, 100) > 1.0        # 只满足 20% → 涨价
    assert price_pressure(1000, 1000) == pytest.approx(1.0, abs=1e-9)  # 刚好满足 → 基准
    assert price_pressure(100, 1000) == pytest.approx(1.0, abs=1e-9)  # 供给过剩 → 仍基准（不跌价）


def test_zero_demand_is_neutral_not_crash():
    assert price_pressure(0, 100) == pytest.approx(1.0, abs=1e-9)


def test_no_supply_returns_none_not_infinity():
    """无可售供给 → 价格无意义（`None`），**不得**返回 ∞ 或 0 假装有个价。"""
    assert price_pressure(100, 0) is None
    assert price_pressure(100, -5) is None


def test_unknown_inputs_return_none():
    """缺失输入 → `None`，不臆造 1.0（缺失≠0）。"""
    assert price_pressure(None, 100) is None
    assert price_pressure(100, None) is None


def test_pressure_saturates_within_bounds():
    """极端供需差 → 压力在 PRICE_BOUNDS 内饱和，不无限放大。"""
    assert price_pressure(10_000_000, 1) <= PRICE_BOUNDS[1]
    assert price_pressure(1, 10_000_000) >= PRICE_BOUNDS[0]


# ====================================================== 价格发现
def test_discover_price_scales_with_base():
    """成交价随基准价走（基准是锚）。"""
    r = discover_price(dim="布", demand_qty=500, supply_qty=100, prev_price=None)
    assert r["base_price"] == 120.0
    assert r["price"] == pytest.approx(120.0 * r["pressure"], rel=1e-6)
    assert r["reason"] == "ok"


def test_discover_price_respects_monthly_cap():
    """单月涨跌封顶：上月 100、本月目标 300，也只能涨 `cap`。"""
    r = discover_price(dim="布", demand_qty=100_000, supply_qty=1,
                       prev_price=100.0, monthly_cap=0.15)
    assert r["price"] <= 100.0 * 1.15 + 1e-6, r
    assert r["cap_applied"] is True


def test_discover_price_first_month_has_no_cap():
    """首月无上期价 → 直接用目标，不伪称封顶。"""
    r = discover_price(dim="布", demand_qty=500, supply_qty=100, prev_price=None)
    assert r["cap_applied"] is False


def test_discover_price_without_supply_is_unpriceable():
    r = discover_price(dim="布", demand_qty=500, supply_qty=0, prev_price=120.0)
    assert r["price"] is None
    assert r["reason"] == "no_supply"


def test_discover_price_absolute_bounds_clamp():
    """即便逐月累积，也不得越出基准价的绝对边界。"""
    prev = 120.0
    for _ in range(20):
        r = discover_price(dim="布", demand_qty=10**7, supply_qty=1,
                           prev_price=prev, monthly_cap=1.0)
        prev = r["price"]
    assert prev <= 120.0 * PRICE_BOUNDS[1] + 1e-6
    assert prev >= 120.0 * PRICE_BOUNDS[0] - 1e-6


def test_unknown_dim_has_no_base_price():
    """未配置基准价的维度 → `None` ＋ `no_base_price`，**不回落 0**。"""
    r = discover_price(dim="不存在之物", demand_qty=10, supply_qty=1,
                       prev_price=None)
    assert r["price"] is None
    assert r["reason"] == "no_base_price"


# ====================================================== 动态价槽
def test_record_trade_price_writes_slot_not_base_table():
    """动态价写入 `state.dynamic_prices`，**基准表不被改写**。"""
    from content.data import MATERIAL_PRICE_BASE
    base_before = MATERIAL_PRICE_BASE.get("布")
    s = _state()
    avg = record_trade_price(s, "布", paid=1000.0, qty=10.0)
    assert avg == pytest.approx(100.0)
    assert s.dynamic_prices["布"] == pytest.approx(100.0)
    assert MATERIAL_PRICE_BASE.get("布") == base_before


def test_record_trade_price_zero_qty_returns_none():
    """成交为 0 → 均价无意义，返回 `None`，不写 0 冒充均价。"""
    s = _state()
    assert record_trade_price(s, "布", paid=100.0, qty=0.0) is None
    assert record_trade_price(s, "布", paid=0.0, qty=10.0) is None
    assert s.dynamic_prices == {}


# ====================================================== 四类价格分离
def test_official_price_wins_over_dynamic():
    """官定价优先于动态价。"""
    s = _state()
    s.dynamic_prices["布"] = 200.0
    r = effective_buy_price(dim="布", state=s, gov_price=150.0)
    assert r["kind"] == "official" and r["price"] == 150.0


def test_dynamic_used_when_no_official():
    s = _state()
    s.dynamic_prices["布"] = 200.0
    r = effective_buy_price(dim="布", state=s)
    assert r["kind"] == "dynamic" and r["price"] == 200.0


def test_falls_back_to_base_price():
    """无动态价 → 回落基准价，并如实标注 `kind`。"""
    s = _state()
    r = effective_buy_price(dim="布", state=s)
    assert r["kind"] == "base" and r["price"] == 120.0


def test_no_price_at_all_is_none_not_zero():
    """该维度既无动态价也无基准价 → `price is None`（**不作 0**）。"""
    s = _state()
    r = effective_buy_price(dim="不存在之物", state=s)
    assert r["kind"] == "none"
    assert r["price"] is None


def test_kind_is_always_reported():
    """每种取值都要标明是哪一类价格（口径分离，不得顶替）。"""
    s = _state()
    s.dynamic_prices["布"] = 200.0
    for kwargs in ({"gov_price": 150.0}, {}, {"use_dynamic": False}):
        r = effective_buy_price(dim="布", state=s, **kwargs)
        assert r["kind"] in ("official", "dynamic", "base", "none")
        assert r["reason"]


# ====================================================== 集成
def test_settlement_price_discovery_runs_and_conserves():
    """真实结算：价格发现执行、残差 0、基准表不变。"""
    from content.data import MATERIAL_PRICE_BASE
    base_before = dict(MATERIAL_PRICE_BASE)
    s = _state()
    s.treasury = max(getattr(s, "treasury", 0), 50_000_000)
    for _ in range(6):
        s.treasury = max(s.treasury, 50_000_000)
        run_monthly_settlement(s)
    assert float((s.money_audit or {}).get("residual", 0) or 0) == 0.0
    assert s.statistics.get("price_discovery_error") is None
    assert dict(MATERIAL_PRICE_BASE) == base_before, "基准价表被改写了"
    assert isinstance(s.dynamic_prices, dict)


def test_dynamic_prices_survive_save_load():
    """路级键（B2-R2 格式 `"<路>|<商品>"`）落档后原样读回。"""
    from core.save_load import load_game, save_game
    s = _state()
    s.dynamic_prices["京畿路|布"] = 240.0
    s.dynamic_prices["京畿路|绸"] = 800.0
    assert save_game(s, 96) is True
    s2 = load_game(96)
    assert s2 is not None
    assert s2.dynamic_prices.get("京畿路|布") == 240.0
    assert s2.dynamic_prices.get("京畿路|绸") == 800.0


def test_load_drops_invalid_prices_not_faking_base():
    """坏动态价丢弃留痕，**不回落基准价伪装成"无动态价"**。"""
    import json
    from core.save_load import _slot_path, load_game, save_game
    s = _state()
    s.dynamic_prices = {"布": 120.0}
    assert save_game(s, 97) is True
    p = _slot_path(97)
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    raw["dynamic_prices"] = {"布": -5.0, "绸": "坏值"}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    s2 = load_game(97)
    assert s2 is not None
    assert "布" not in s2.dynamic_prices
    assert "绸" not in s2.dynamic_prices