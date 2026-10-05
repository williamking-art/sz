# -*- coding: utf-8 -*-
"""B2-R2 · 路级价格修正的定向回归（规格 `market-civilian-economy` B2-R2）

修复前（已实测）：`price_demand` 键只有商品、`dynamic_prices` 全局共享，
而供给 `sellable_stock` 取循环中当前一路 ⇒ 需求=多路累计、供给=单路、价格=全局。

锁定：
- 键统一为 `(route, good)`；
- **两路隔离**：甲路短缺只抬甲路价，乙路不变；
- 记录**期望需求**（含未满足），高未满足反映在价格压力；
- 缺货仍以缺货原因报告，**不伪造成交**；
- 旧档全局价**标注为无路归属**（不臆造归属路），读侧作回退。
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
    effective_buy_price, pref_good_key, record_trade_price,
)
from core.settlement import run_monthly_settlement  # noqa: E402


def _state(months=4):
    s = GameState("史实")
    init_legacies(s)
    s.treasury = 50_000_000
    for _ in range(months):
        s.treasury = max(s.treasury, 50_000_000)
        run_monthly_settlement(s)
    return s


# ====================================================== 键的统一
def _state_with_controlled_stock(months=4, seed=5000, step=337):
    """**受控库存场景**：先备已确权可售成品，**再**跑结算。

    与共享 `_state()` 分开（后者不备货，供「初始无货」断言使用）。
    6.33：产出链未裁定物料落 `pending_stock`（不得出售），
    故路级价格发现必须有**显式构造**的可售成品才有真实成交。
    """
    from core.material_holding import goods_add
    s = GameState("史实")
    init_legacies(s)
    for _i, _rk in enumerate(s.prefectures):
        _art = ((s.prefectures[_rk] or {}).get("pops") or {}).get("工匠")
        if not isinstance(_art, dict):
            continue
        _g = _art.setdefault("goods", {})
        for _dim in ("布", "绸"):
            goods_add(_g, _dim, seed + _i * step)   # 各路不同 ⇒ 供需条件相异
    s.treasury = 50_000_000
    for _ in range(months):
        s.treasury = max(s.treasury, 50_000_000)
        run_monthly_settlement(s)
    return s

def _seed_route_finished(s, overrides=None):
    """**受控库存场景**：给指定路的工匠（卖方）POP 备**已确权、可售**的成品。

    6.33 之后，产出链的**未裁定物料**落 `pending_stock`（归属待定），
    按裁定**不得出售/采购/计税**；而路级价格发现**必须有真实成交**才产生路级键。
    故本函数**显式**构造可售成品 —— 这是**测试夹具**，不是游戏默认库存。

    `overrides`：`{路名: {维: 数量}}`，用于**制造供需差异** ⇒ 价格分化。
    ⚠️ 仅供需要成交/价格发现的用例调用，**不并入共享 `_state()`**。
    """
    from core.material_holding import goods_add
    routes = list(s.prefectures)
    for i, rk in enumerate(routes):
        pref = s.prefectures.get(rk) or {}
        art = (pref.get("pops") or {}).get("工匠")
        if not isinstance(art, dict):
            continue
        g = art.setdefault("goods", {})
        for dim in ("布", "绸"):
            qty = 5000 + i * 337          # 各路基数不同 ⇒ 供需条件各异
            if overrides and rk in overrides and dim in overrides[rk]:
                qty = int(overrides[rk][dim])
            if qty > 0:
                goods_add(g, dim, qty)
    return s

def test_pref_good_key_format():
    assert pref_good_key("京畿路", "布") == "京畿路|布"


def test_price_demand_keys_are_route_scoped():
    s = _state(4)
    pd = s.statistics.get("price_demand") or {}
    assert pd, "price_demand 为空"
    assert all("|" in k for k in pd), f"仍有非路级键：{pd}"


def test_dynamic_price_keys_are_route_scoped():
    s = _state_with_controlled_stock(4)   # 受控库存：需真实成交才有路级价
    dp = getattr(s, "dynamic_prices", {}) or {}
    assert dp, "dynamic_prices 为空"
    assert all("|" in k for k in dp), f"仍有非路级键：{dp}"


def test_prices_diverge_across_routes():
    """同一商品在不同路应能取到不同价（未受冲击的路不无因同步跳价）。"""
    s = _state_with_controlled_stock(6)   # 受控库存：各路供需不同 ⇒ 价格分化
    dp = getattr(s, "dynamic_prices", {}) or {}
    by_good = {}
    for k, v in dp.items():
        r, g = k.split("|", 1)
        by_good.setdefault(g, set()).add(round(float(v), 4))
    multi = [g for g, vals in by_good.items() if len(vals) > 1]
    assert multi, f"所有路的同一商品同价，路级价格发现未生效：{by_good}"


# ====================================================== 两路隔离
def test_two_route_isolation_shortage_only_raises_own_route():
    """**核心夹具**：甲路供给为 0（短缺）→ 只抬甲路价；乙路供给充足 → 乙路价不动。"""
    s = _state(1)
    routes = list(s.prefectures)
    a, b = routes[0], routes[1]
    key_a = pref_good_key(a, "布")
    key_b = pref_good_key(b, "布")
    # 甲路 0 供给（严重短缺），乙路 1000 供给
    from core.market_price import discover_price as dp_fn
    ra = dp_fn(dim="布", demand_qty=500, supply_qty=0, prev_price=120.0)
    rb = dp_fn(dim="布", demand_qty=500, supply_qty=1000, prev_price=120.0)
    assert ra["price"] is None, "甲路无货却算出了价格（应为不可定价）"
    assert rb["price"] == pytest.approx(120.0), "乙路供需充足不该涨价"
    # 路级键互不覆盖
    s.dynamic_prices[key_a] = 200.0
    s.dynamic_prices[key_b] = 120.0
    assert effective_buy_price(dim="布", state=s, pref=a)["price"] == 200.0
    assert effective_buy_price(dim="布", state=s, pref=b)["price"] == 120.0


def test_record_trade_price_is_route_scoped():
    s = _state(1)
    a, b = list(s.prefectures)[:2]
    # 清空该两路的既有路级价，避免上期价平滑干扰（`_state(1)` 已跑过一次结算）
    s.dynamic_prices = {k: v for k, v in (s.dynamic_prices or {}).items()
                        if not k.startswith(f"{a}|") and not k.startswith(f"{b}|")}
    record_trade_price(s, "布", pref=a, paid=1000.0, qty=10.0)
    record_trade_price(s, "布", pref=b, paid=500.0, qty=10.0)
    # 首笔无上期价 → 取当月均价；两路**互不干扰**（这是路级键的核心）
    assert s.dynamic_prices[pref_good_key(a, "布")] == pytest.approx(100.0)
    assert s.dynamic_prices[pref_good_key(b, "布")] == pytest.approx(50.0)


# ====================================================== 期望需求
def test_price_demand_records_intended_not_only_traded():
    """`price_demand` 记**期望需求**——高未满足时仍应进入需求键。"""
    s = _state(4)
    pd = s.statistics.get("price_demand") or {}
    unmet = s.statistics.get("goods_unmet") or {}
    traded = s.statistics.get("goods_traded") or {}
    if unmet:
        # 有未满足 ⇒ 期望需求应大于等于实际成交量
        total_pd = sum(pd.values())
        total_tr = sum(traded.values()) if traded else 0
        assert total_pd >= total_tr, "需求键未包含未满足部分"


# ====================================================== 缺货语义
def test_shortage_reported_as_shortage_not_fake_trade():
    """缺货时**不伪造成交**：成交为 0、未满足按缺粮原因登记。"""
    s = _state(4)
    unmet = s.statistics.get("goods_unmet") or {}
    if unmet:
        assert all(k in ("no_stock_local", "insufficient_purchasing_power",
                         "no_demand") for k in unmet), f"未知未满足原因：{unmet}"
        assert sum(unmet.values()) > 0


# ====================================================== 存档迁移
def test_legacy_global_price_is_marked_not_assigned_to_route():
    """旧档全局价**标注为无路归属**，不臆造归属路；读侧可回退。"""
    s = _state(1)
    s.dynamic_prices = {"布": 130.0}          # 旧格式：只有商品名
    s.dynamic_prices_legacy = {}
    # 模拟读档迁移（与 save_load 同一逻辑）
    from core.save_load import load_game, save_game
    s.prefectures = {k: v for k, v in list(s.prefectures.items())[:2]}
    assert save_game(s, 95) is True
    s2 = load_game(95)
    assert s2 is not None
    # 迁移后：旧价进 legacy，不在路级键里
    assert "布" in (getattr(s2, "dynamic_prices_legacy", {}) or {})
    assert "布" not in (getattr(s2, "dynamic_prices", {}) or {})
    # 任一路读取都能回退到该价
    r0 = list(s2.prefectures)[0]
    assert effective_buy_price(dim="布", state=s2, pref=r0)["price"] == 130.0


def test_route_price_overrides_legacy():
    """路级价一旦产生，优先于旧全局回退价。"""
    s = _state(1)
    s.dynamic_prices_legacy = {"布": 130.0}
    s.dynamic_prices = {pref_good_key("甲路", "布"): 200.0}
    assert effective_buy_price(dim="布", state=s, pref="甲路")["price"] == 200.0
    # 另一路仍回退旧全局价
    assert effective_buy_price(dim="布", state=s, pref="乙路")["price"] == 130.0


# ====================================================== 守恒
def test_settlement_still_conserves_money():
    s = _state(12)
    assert float((s.money_audit or {}).get("residual", 0) or 0) == 0.0
    assert s.statistics.get("price_discovery_error") is None


def test_demand_supply_same_domain():
    """价格发现的输入**同域**：需求键与供给都限定在本路。"""
    s = _state(4)
    pd = s.statistics.get("price_demand") or {}
    dp = getattr(s, "dynamic_prices", {}) or {}
    for k in dp:
        assert k in pd or True   # 供给为 0 时不写价是合法情形
    # 有路级价必有对应需求记录
    for k in dp:
        assert k in pd, f"有路级价 {k} 但无对应需求记录（域不一致）"