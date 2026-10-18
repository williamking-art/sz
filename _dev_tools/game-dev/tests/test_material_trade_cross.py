# -*- coding: utf-8 -*-
"""**跨州府建材成交**回归（P0 · 2026-10-02）。

钱与货**两腿分离**：钱成交即付（守恒划转），货走 `transport.dispatch` 进在途，
`arrive_month` 才入账。这是 C-c「只从本地取、取不到即缺料」在市场侧的落实。

本组锁：
1. **钱立即付、货未到不入账**（最核心）；
2. `ΣPOP wealth` 与 `ΣPOP goods`（含在途）**均守恒**；
3. **钱货两清或两不做**：付款失败 ⇒ 批次退回、货回卖方；
4. **同路走市集、跨路走物流**，两条路互不串门；
5. 拒绝式：未知维度／无货／购买力不足／同路误用。
"""
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core import transport                                        # noqa: E402
from core.game_state import GameState                             # noqa: E402
from core.legacy_mechanic import init_legacies                    # noqa: E402
from core.material_holding import (                               # noqa: E402
    goods_amount, merchant_goods, supply_merchant_materials, trade_material,
)
from core.material_trade import sell_material_across               # noqa: E402
from core.production_chain import settle_production_chain         # noqa: E402

# 🔴 R1/R2 必须**跨路且有直达道路**（实测 is_adjacent=True，耗时 1 月）：
# 「不做全图任意互通」后，两两任意两路已不可发货。
R1, R2 = "京畿路", "京西路"
SEAT_R1, SEAT_R2 = "京畿路|开封府", "京西路|河南府"   # 实测相邻的治所对


def _state():
    s = GameState("史实")
    init_legacies(s)
    settle_production_chain(s, [])
    supply_merchant_materials(s)
    _set_month(s, 10)
    return s


def _clear_buckets(goods):
    """清空该 POP `goods` 里的全部州府桶（迁移期夹具用）。"""
    for k in [k for k in goods if "|" in k and isinstance(goods.get(k), dict)]:
        goods[k].clear()


def _sum_wealth(s):
    return sum(float(p.get("wealth", 0) or 0)
               for r in s.prefectures.values()
               for p in (r.get("pops") or {}).values() if isinstance(p, dict))


def _sum_goods(s, dim):
    """全路该维总量（走 `goods_amount`：扁平项 + Σ州府桶）。"""
    from core.material_holding import goods_amount
    return sum(int(goods_amount(merchant_goods(s, r), dim) or 0)
               for r in s.prefectures)


def _transit_qty(s, dim):
    return sum(int(b.get("qty", 0) or 0) for b in transport.in_transit(s)
               if b.get("dim") == dim)


def _set_month(s, a):
    """把**绝对月序** `a` 写成真实字段 `year`/`month`（1..12）。

    🔴 `abs_month_index = year*12 + month`，逆运算须精确；
    余 0 时退到前一年 12 月，保证 `month` 落在合法区间。
    """
    a = int(a)
    y, m = a // 12, a % 12
    if m == 0:
        y, m = y - 1, 12
    s.year = int(y)
    s.month = int(m)


def _prep(s, dim, qty_seller, qty_buyer, wealth_buyer):
    g1 = merchant_goods(s, R1)
    g2 = merchant_goods(s, R2)
    # 🔴 2026-10-03：建材按 `goods[治所][dim]` 州府桶存放，「布置成 N」必须**先清该维桶**，
    # 否则真实库存留在桶里，测试前提（如「R2 缺料」）不成立。
    # 🔴 2026-10-05（Y 轨货主规则上线后）：
    # ① 原料现在**入仓**，而 `material_holding_for_circuit` **也读仓库**；
    # ② `supply_merchant_materials` 已把仓料分摊给**所有路**的商人。
    # ⇒ 若只清 R1/R2 的桶，「R2 缺料」前提不成立，且卖家选择会挑到
    #   其他有货路而失败。故本夹具须**清空全路同维桶 + 归零仓库**，
    #   确保「只有 R1 有货」这一受控场景成立。
    for _rk in s.prefectures:
        _g = merchant_goods(s, _rk)
        if isinstance(_g, dict):
            _clear_buckets(_g)
            _g.pop(dim, None)
    _slot = s.resources.get(dim)
    if isinstance(_slot, dict):
        _slot["stock"] = 0
    g1[dim] = int(qty_seller)
    g2[dim] = int(qty_buyer)
    s.prefectures[R1]["pops"]["商人"]["wealth"] = 0.0
    s.prefectures[R2]["pops"]["商人"]["wealth"] = float(wealth_buyer)


# ====================================================== 核心：钱付、货在途
def test_money_paid_now_goods_arrive_later():
    """🔴 核心：钱**成交即付**，货**在途**，未到不入买方账。"""
    s = _state()
    _prep(s, "木", 1000, 0, 100000)
    w0 = _sum_wealth(s)
    buyer_before = int(goods_amount(merchant_goods(s, R2), "木") or 0)

    res = sell_material_across(s, seller_route=R1, buyer_route=R2,
                               dim="木", qty=300, price=2.0)
    assert res["ok"] and res["shipped"] == 300 and res["paid"] == 600
    assert res["arrive_month"] > 10, "跨路不应当月到货"

    assert _sum_wealth(s) == w0, "钱只是转移，Σ 必须守恒"
    assert float(s.prefectures[R2]["pops"]["商人"]["wealth"]) == 100000.0 - 600, \
        "买方**立刻**付钱（不等货到）"
    assert float(s.prefectures[R1]["pops"]["商人"]["wealth"]) == 600.0, \
        "卖方**立刻**收钱（不必等货到）"
    assert int(goods_amount(merchant_goods(s, R2), "木") or 0) == buyer_before, \
        "🔴 未到货不得计入买方货栈"
    assert _transit_qty(s, "木") == 300


def test_goods_arrive_then_credited():
    """到月份才入账。"""
    s = _state()
    _prep(s, "木", 1000, 0, 100000)
    res = sell_material_across(s, seller_route=R1, buyer_route=R2,
                               dim="木", qty=300, price=2.0)
    _set_month(s, int(res["arrive_month"]))
    transport.arrive_due(s)
    assert int(goods_amount(merchant_goods(s, R2), "木") or 0) == 300
    assert _transit_qty(s, "木") == 0, "到货后批次应清空"


def test_total_goods_conserved_including_transit():
    """🔴 `Σ货`（含在途）守恒——无凭空增删。"""
    s = _state()
    _prep(s, "石", 800, 50, 100000)
    g0 = _sum_goods(s, "石") + _transit_qty(s, "石")
    for i in range(5):
        sell_material_across(s, seller_route=R1, buyer_route=R2,
                             dim="石", qty=100, price=1.0, trade_id=f"x{i}")
    g1 = _sum_goods(s, "石") + _transit_qty(s, "石")
    assert g1 == g0, f"Σ货应守恒：{g0} → {g1}"


def test_money_conserved_over_many_trades():
    """`ΣPOP wealth` 多笔成交后守恒。"""
    s = _state()
    _prep(s, "铁", 5000, 0, 1_000_000)
    w0 = _sum_wealth(s)
    for i in range(10):
        sell_material_across(s, seller_route=R1, buyer_route=R2,
                             dim="铁", qty=50, price=3.0, trade_id=f"y{i}")
    assert _sum_wealth(s) == w0


# ====================================================== 钱货两清或两不做
def test_insufficient_purchasing_power_nothing_happens():
    """🔴 购买力不足 ⇒ 货不动、批次不建、钱不变。"""
    s = _state()
    _prep(s, "木", 1000, 0, 10)             # 只够买 5（单价2）
    w0 = _sum_wealth(s)
    res = sell_material_across(s, seller_route=R1, buyer_route=R2,
                               dim="木", qty=300, price=2.0)
    assert res["ok"] is False and res["reason"] == "insufficient_purchasing_power"
    assert _transit_qty(s, "木") == 0, "不得留下半笔在途"
    assert _sum_wealth(s) == w0, "不得留下半笔钱"
    assert int(goods_amount(merchant_goods(s, R1), "木") or 0) == 1000, "货须留在卖方"


def test_payment_failure_refunds_batch():
    """🔴 付款失败 ⇒ 批次撤回、货回卖方（钱货两清或两不做）。"""
    s = _state()
    _prep(s, "木", 1000, 0, 100000)

    def boom(*a, **k):
        raise RuntimeError("模拟付款失败")

    s.transfer_money = boom
    res = sell_material_across(s, seller_route=R1, buyer_route=R2,
                               dim="木", qty=200, price=1.0)
    assert res["ok"] is False and res["reason"] == "payment_failed"
    assert res["refunded_batch"] is True
    assert _transit_qty(s, "木") == 0, "失败须撤批次"
    assert int(goods_amount(merchant_goods(s, R1), "木") or 0) == 1000, "货须回卖方"


# ====================================================== 两条路互不串门
def test_same_circuit_rejected_here():
    """2026-10-18 口径修正：判据按**治所**——同路但未给治所 ⇒ seat_required；
    同路同 治所 ⇒ same_seat（市集内瞬时成交，不该走物流）。"""
    s = _state()
    res = sell_material_across(s, seller_route=R1, buyer_route=R1,
                               dim="木", qty=1, price=1.0)
    assert res["ok"] is False and res["reason"] == "seat_required"
    r2 = sell_material_across(s, seller_route=R1, buyer_route=R1,
                              dim="木", qty=1, price=1.0,
                              frm_seat="京畿路|开封府", to_seat="京畿路|开封府")
    assert r2["ok"] is False and r2["reason"] == "same_seat"


def test_trade_material_rejects_cross_circuit():
    """🔴 `trade_material` 必须**拒绝**跨州府（否则就是瞬移，物流无意义）。"""
    s = _state()
    a = s.prefectures[R1]["pops"]["商人"]
    b = s.prefectures[R2]["pops"]["商人"]
    a["wealth"] = 100000.0
    b["wealth"] = 0.0
    from core.material_holding import goods_amount
    _clear_buckets(a["goods"])
    a["goods"]["木"] = 500
    with pytest.raises(ValueError) as ei:
        trade_material(state=s, buyer_pop=b, seller_pop=a,
                       dim="木", qty=10, price=1.0)
    assert "不得瞬移" in str(ei.value)
    assert goods_amount(a["goods"], "木") == 500, "被拒后货须原样不动"


def test_trade_material_still_works_within_circuit():
    """同路市集成交**不受影响**（买卖双方须是**不同** POP，否则是自成交）。"""
    s = _state()
    buyer = s.prefectures[R1]["pops"]["士绅"]      # 同路、不同阶层 ⇒ 不同 POP
    seller = s.prefectures[R1]["pops"]["商人"]
    buyer["wealth"] = 100000.0
    seller["wealth"] = 0.0
    _clear_buckets(buyer.setdefault("goods", {}))
    _clear_buckets(seller["goods"])
    buyer["goods"]["木"] = 0
    seller["goods"]["木"] = 500
    res = trade_material(state=s, buyer_pop=buyer, seller_pop=seller,
                         dim="木", qty=100, price=1.0)
    assert res["ok"] and res["traded"] == 100
    assert int(goods_amount(buyer["goods"], "木") or 0) == 100, "同路应即时到手"
    assert float(buyer["wealth"]) == 99900.0
    assert float(seller["wealth"]) == 100.0


# ====================================================== 拒绝式
def test_invalid_dim_rejected():
    s = _state()
    res = sell_material_across(s, seller_route=R1, buyer_route=R2,
                               dim="绸", qty=1, price=1.0)
    assert res["ok"] is False and res["reason"] == "invalid_dim"


def test_invalid_price_rejected():
    s = _state()
    _prep(s, "木", 100, 0, 1000)
    res = sell_material_across(s, seller_route=R1, buyer_route=R2,
                               dim="木", qty=1, price=0)
    assert res["ok"] is False and res["reason"] == "invalid_price"


def test_no_stock_rejected_without_money_moved():
    s = _state()
    _prep(s, "木", 0, 0, 100000)
    w0 = _sum_wealth(s)
    res = sell_material_across(s, seller_route=R1, buyer_route=R2,
                               dim="木", qty=10, price=1.0)
    assert res["ok"] is False and res["reason"] == "no_stock_local"
    assert _sum_wealth(s) == w0


def test_missing_merchant_pop_is_reported():
    """无商人 POP ⇒ 如实报错，不臆断（缺失≠0）。"""
    s = _state()
    s.prefectures[R2]["pops"].pop("商人", None)
    res = sell_material_across(s, seller_route=R1, buyer_route=R2,
                               dim="木", qty=10, price=1.0)
    assert res["ok"] is False and res["reason"] == "no_buyer_pop"


def test_zero_qty_is_no_demand():
    s = _state()
    _prep(s, "木", 100, 0, 1000)
    res = sell_material_across(s, seller_route=R1, buyer_route=R2,
                               dim="木", qty=0, price=1.0)
    assert res["ok"] is True and res["reason"] == "no_demand"


# ====================================================== 补货决策（让物流跑起来）
def test_procure_buys_when_below_floor():
    """🔴 本地料低于阈值 ⇒ 自动下单（钱即付、货在途）。"""
    from core.material_trade import procure_materials
    s = _state()
    _prep(s, "木", 5000, 0, 1_000_000)      # R1 料足、R2 缺
    res = procure_materials(s, stock_floor=1000)
    assert res["bought"], f"应下单：{res}"
    assert int(goods_amount(merchant_goods(s, R2), "木") or 0) == 0, \
        "下单后货仍在途，买方**不得**立刻到手"
    assert _transit_qty(s, "木") > 0

