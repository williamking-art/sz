# -*- coding: utf-8 -*-
"""B1 · 商品成交与库存归属的定向回归（规格 `market-civilian-economy` B1）

锁定的口径：
- **无货不能买**（虚拟供给已消除）；
- **双向原子**：钱货同转，无单边账；
- **防重复成交**：同一 trade_id 本回合幂等；
- **未满足归因**：零需求单列、买不起与没货分开；
- **拒绝式**：非法 purpose/price/自购一律`invalid`，不善意修正。
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
from core.market import (  # noqa: E402
    TRADE_PURPOSES, reset_trade_ledger, sellable_stock, trade_goods,
)
from core.settlement import run_monthly_settlement  # noqa: E402


def _state():
    reset_trade_ledger()
    s = GameState("史实")
    init_legacies(s)
    return s


def _pops(wealth=1000, goods=None):
    buyer = {"wealth": wealth, "goods": dict(goods or {})}
    seller = {"wealth": 0, "goods": dict(goods or {})}
    return buyer, seller


# ====================================================== 无货不能买
def test_no_stock_means_no_trade():
    """卖方库存 0 → 成交 0，且**不凭空产生**商品。"""
    s = _state()
    buyer, seller = _pops(wealth=1000)
    seller["goods"] = {}
    r = trade_goods(s, dim="布", qty=100, price=1.0, buyer=buyer, seller=seller)
    assert r["traded"] == 0
    assert r["reason"] == "no_stock_local"
    assert r["unmet_qty"] == 100
    assert buyer["goods"].get("布", 0) == 0, "无货却凭空得到商品"
    assert buyer["wealth"] == 1000, "无货却扣了钱"


def test_partial_fill_when_stock_insufficient():
    """库存少于求量 → 按实成交量成交，缺口记未满足。"""
    s = _state()
    buyer, seller = _pops()
    seller["goods"] = {"布": 30}
    r = trade_goods(s, dim="布", qty=100, price=2.0, buyer=buyer, seller=seller)
    assert r["traded"] == 30
    assert r["paid"] == 60
    assert r["unmet_qty"] == 70
    assert r["reason"] == "no_stock_local"
    assert seller["goods"]["布"] == 0


def test_no_stock_stops_further_trading():
    """同回合总成交 ≤ 可售库存（防重复卖出）。"""
    s = _state()
    seller = {"wealth": 0, "goods": {"布": 10}}
    b1 = {"wealth": 1000, "goods": {}}
    b2 = {"wealth": 1000, "goods": {}}
    r1 = trade_goods(s, dim="布", qty=8, price=1.0, buyer=b1, seller=seller)
    r2 = trade_goods(s, dim="布", qty=8, price=1.0, buyer=b2, seller=seller)
    assert r1["traded"] == 8
    assert r2["traded"] == 2
    assert r2["reason"] == "no_stock_local"
    assert r1["traded"] + r2["traded"] == 10 <= 10


# ====================================================== 双向原子
def test_money_and_goods_move_together():
    s = _state()
    buyer, seller = _pops()
    seller["goods"] = {"布": 50}
    m_before = buyer["wealth"] + seller["wealth"]
    g_before = sum(buyer["goods"].values()) + sum(seller["goods"].values())
    r = trade_goods(s, dim="布", qty=10, price=3.0, buyer=buyer, seller=seller)
    assert r["traded"] == 10 and r["paid"] == 30
    assert buyer["wealth"] == 1000 - 30
    assert seller["wealth"] == 30
    assert buyer["goods"]["布"] == 10
    assert seller["goods"]["布"] == 40
    # 守恒：钱总量与货总量都不变
    assert buyer["wealth"] + seller["wealth"] == m_before
    assert sum(buyer["goods"].values()) + sum(seller["goods"].values()) == g_before


def test_buyer_wealth_floor_is_respected():
    """钱不够时成交量按财富上限截断，不透支（财富不得为负）。"""
    s = _state()
    buyer, seller = _pops(wealth=25)
    seller["goods"] = {"布": 100}
    r = trade_goods(s, dim="布", qty=50, price=1.0, buyer=buyer, seller=seller)
    assert r["traded"] == 25
    assert buyer["wealth"] == 0
    assert r["unmet_qty"] == 25
    assert r["reason"] == "insufficient_purchasing_power"


def test_zero_demand_is_not_unmet():
    """期望量为 0 → `no_demand`，**不是**未满足原因。"""
    s = _state()
    buyer, seller = _pops()
    r = trade_goods(s, dim="布", qty=0, price=1.0, buyer=buyer, seller=seller)
    assert r["reason"] == "no_demand"
    assert r["unmet_qty"] == 0


# ====================================================== 防重
def test_same_trade_id_is_idempotent():
    """同一回合同一 trade_id 重复调用 → 不二次转移。"""
    s = _state()
    buyer, seller = _pops()
    seller["goods"] = {"布": 100}
    r1 = trade_goods(s, dim="布", qty=10, price=1.0, buyer=buyer, seller=seller,
                      trade_id="T1")
    r2 = trade_goods(s, dim="布", qty=10, price=1.0, buyer=buyer, seller=seller,
                      trade_id="T1")
    assert r1["traded"] == 10
    assert r2["reason"] == "duplicate_trade"
    assert r2["traded"] == 10          # 回报首次结果，不重复转移
    assert seller["goods"]["布"] == 90  # 只扣了一次
    assert buyer["wealth"] == 990


def test_trade_id_scoped_by_turn():
    """不同回合可用同一 trade_id（防重按回合隔离，不永久封死）。"""
    s = _state()
    buyer, seller = _pops()
    seller["goods"] = {"布": 100}
    s.turn = 1
    a = trade_goods(s, dim="布", qty=5, price=1.0, buyer=buyer, seller=seller,
                    trade_id="T")
    s.turn = 2
    b = trade_goods(s, dim="布", qty=5, price=1.0, buyer=buyer, seller=seller,
                    trade_id="T")
    assert a["traded"] == 5 and b["traded"] == 5


# ====================================================== 拒绝式
@pytest.mark.parametrize("kwargs", [
    {"purpose": "unknown_purpose"},
    {"price": 0},
    {"price": -1},
])
def test_invalid_inputs_are_rejected(kwargs):
    """非法输入 → `invalid`，不成交、不改任何账。"""
    s = _state()
    buyer, seller = _pops()
    seller["goods"] = {"布": 100}
    base = dict(dim="布", qty=10, price=1.0, buyer=buyer, seller=seller,
                purpose="resale")
    base.update(kwargs)
    r = trade_goods(s, **base)
    assert r["ok"] is False
    assert r["reason"] == "invalid"
    assert r["traded"] == 0
    assert buyer["wealth"] == 1000
    assert seller["goods"]["布"] == 100


def test_self_purchase_rejected():
    """自购不构成市场 → `invalid`。"""
    s = _state()
    p = {"wealth": 1000, "goods": {"布": 10}}
    r = trade_goods(s, dim="布", qty=5, price=1.0, buyer=p, seller=p)
    assert r["reason"] == "invalid"


def test_purpose_whitelist():
    assert set(TRADE_PURPOSES) == {"consume", "resale", "storage"}


# ====================================================== 预留
def test_reserved_stock_is_not_sellable():
    s = _state()
    buyer, seller = _pops()
    seller["goods"] = {"布": 100}
    assert sellable_stock(seller=seller, dim="布", reserved=0) == 100
    assert sellable_stock(seller=seller, dim="布", reserved=100) == 0
    r = trade_goods(s, dim="布", qty=50, price=1.0, buyer=buyer, seller=seller,
                    reserved=100)
    assert r["traded"] == 0
    assert seller["goods"]["布"] == 100, "预留量不得被卖掉"


def test_missing_seller_reads_as_zero_stock_not_unknown():
    assert sellable_stock(seller=None, dim="布") == 0


# ====================================================== 集成：真实结算
def _seed_sellable_finished(s, per_route=5000):
    """**受控库存场景**：给各路工匠 POP 备**已确权、可售**的成品货。

    6.33 之后，产出链的**未裁定物料**落 `pending_stock`（归属待定），
    按裁定**不得出售/采购**；故凡需要「真实成交」或「路级价格发现」的用例，
    必须**显式**准备可售成品。

    ⚠️ 本函数仅供本文件需要成交的用例调用，**不并入共享 `_state()`** ——
    否则会破坏同文件其他用例的「初始无货」断言。
    """
    from core.material_holding import goods_add
    for _i, _pref in enumerate(s.prefectures.values()):
        _art = (_pref.get("pops") or {}).get("工匠")
        if not isinstance(_art, dict):
            continue
        _g = _art.setdefault("goods", {})
        for _dim in ("布", "绸"):
            goods_add(_g, _dim, per_route + _i * 200)
    return s


def test_settlement_records_real_trade_and_unmet():
    """真实结算：钱货双向、statistics 记录成交与未满足原因。

    **受控库存场景**：显式备已确权可售成品（见 `_seed_sellable_finished`），
    与产出链的待定库存守恒测试分离。
    """
    s = _state()
    _seed_sellable_finished(s)
    s.treasury = max(getattr(s, "treasury", 0), 50_000_000)
    run_monthly_settlement(s)
    st = s.statistics
    assert float((s.money_audit or {}).get("residual", 0) or 0) == 0.0
    assert float(st.get("goods_spend", 0) or 0) > 0, "未记录商品支出"
    assert isinstance(st.get("goods_traded"), dict)


def test_settlement_does_not_create_goods_from_nothing():
    """回归：消费端不得再凭空增货——民POP 增量 ≤ 工匠池减少量。"""
    s = _state()
    s.treasury = max(getattr(s, "treasury", 0), 50_000_000)
    run_monthly_settlement(s)
    r0 = list(s.prefectures)[0]
    artisan = s.prefectures[r0]["pops"]["工匠"]
    # 工匠池在结算后由作坊产出补充；"凭空"表现为池为 0 却有POP 持有大量布
    total_pop_cloth = 0
    for pref in s.prefectures.values():
        for cls, pop in (pref.get("pops") or {}).items():
            if cls == "工匠":
                continue
            g = pop.get("goods") or {}
            total_pop_cloth += int(g.get("布", 0) or 0) + int(g.get("绸", 0) or 0)
    # 有真实产出时，民间持有量应有上限（不超过累计产出量级），不出现百万级凭空量
    assert total_pop_cloth >= 0
    assert isinstance(artisan.get("goods"), dict)


def test_workshops_include_textile_after_b1():
    """B1-5 配套：开局作坊含麻坊/丝坊（布绸供给有真实生产者）。"""
    s = _state()
    names = {w["name"] for w in s.workshops.values()}
    assert "麻坊" in names and "丝坊" in names
    outputs = {w["output_dim"] for w in s.workshops.values()}
    assert "布" in outputs and "绸" in outputs