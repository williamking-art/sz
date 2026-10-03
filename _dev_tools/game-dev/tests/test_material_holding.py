# -*- coding: utf-8 -*-
"""建材**商品化**（E-1）定向回归 —— 2026-10-02。

用户裁定 **C / C-c / E-1**：
- **C**：施工侧只从本地取料，取不到即缺料（物流才有意义）；
- **C-c**：缺料**不得**由系统自动代买/凭空补；
- **E-1**：「**建材也是商品啊**」⇒ 建材是商品，存量落在**商人 POP `goods`**。

本组锁五件事：

1. **商品化**：建材只在商人 `goods`，**无第二处账本**（仓明细层已退役）；
2. **搬运守恒**：`supply_merchant_materials()` 只是搬运，**总量守恒、幂等**；
3. **缺失 ≠ 0**：无商人 / 无该维度 ⇒ `None`，**不回落 0**；
4. **缺料不静默**：扣不足返回**实扣量**；**不跨路借料**；
5. **维度合并**：`铁`/`石`/`木` ⇄ `iron`/`stone`/`timber` 单一翻译点。
"""
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState                                  # noqa: E402
from core.legacy_mechanic import init_legacies                         # noqa: E402
from core.material_holding import (                                    # noqa: E402
    MATERIAL_DIMS, consume_for_circuit, consume_for_seat, goods_amount,
    holding_report, material_holding_for_circuit, material_holding_for_seat,
    merchant_goods, seat_holding_report, seat_slot, seat_weights_of_circuit,
    supply_merchant_materials, to_material_dim, trade_material,
)
from core.production_chain import settle_production_chain              # noqa: E402

R1, R2 = "京畿路", "两浙路"


def _state(with_stock=True):
    s = GameState("史实")
    init_legacies(s)
    if with_stock:
        settle_production_chain(s, [])
        supply_merchant_materials(s)
    return s


def _mg(s, route):
    return merchant_goods(s, route)


def _set(s, route, dim, qty):
    """把该路该维**总量**设为 `qty`（覆盖语义，便于测"无料"）。

    🔴 2026-10-03：建材已按 `goods[治所][dim]` 州府桶存放，故「设为 qty」
    必须**先清空该维的全部州府桶**再写扁平区——否则旧值仍留在桶里，
    「设为 0」并不真的无料（这正是命名空间迁移期夹具必须跟的原因）。
    """
    g = _mg(s, route)
    for k in [k for k in g if "|" in k and isinstance(g.get(k), dict)]:
        g[k].pop(dim, None)
    g[dim] = int(qty)


def _stock(s, dim):
    return int((s.resources.get(dim) or {}).get("stock", 0) or 0)


def _sum_goods(s, dim):
    """Σ **全部 POP**（不只商人）的建材。

    ⚠️ 成交可在**任意 POP** 间发生（同路市集里买方可能是士绅），
    只统计商人会漏掉买方那一份，误判成"货丢了"。
    """
    tot = 0
    for r in s.prefectures.values():
        for pop in (r.get("pops") or {}).values():
            if isinstance(pop, dict):
                tot += int((pop.get("goods") or {}).get(dim, 0) or 0)
    return tot


def _sum_wealth(s):
    tot = float(getattr(s, "treasury", 0) or 0) + \
        float(getattr(s, "imperial_treasury", 0) or 0)
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                tot += float(pop.get("wealth", 0) or 0)
    return tot


# ====================================================== 1 · 商品化
def test_materials_are_carried_in_merchant_goods():
    """🔴 E-1：建材是**商品**，由商人 POP `goods` 承载。"""
    s = _state()
    goods = _mg(s, R1)
    assert goods is not None, "本路应有商人 POP"
    for dim in MATERIAL_DIMS:
        assert dim in goods, f"{dim} 应在商人 goods 里（商品化）"


def test_warehouse_detail_layer_is_retired():
    """🔴 **无平行账本**：仓明细 `by_pref` 必须已退役（POP 挂载律）。"""
    s = _state(with_stock=False)
    for dim in MATERIAL_DIMS:
        cell = s.resources.get(dim) or {}
        assert "by_pref" not in cell, \
            f"{dim} 的仓明细层 by_pref 未退役 ⇒ 与 POP goods 构成平行账本"


def test_reading_materials_does_not_mutate():
    """只读口不得改数据。"""
    s = _state()
    snap = holding_report(s)
    for _ in range(3):
        for r in s.prefectures:
            material_holding_for_circuit(s, r, "木")
    assert holding_report(s) == snap


# ====================================================== 2 · 搬运守恒
def test_supply_conserves_total():
    """🔴 搬运守恒：`Σ(商人建材) == resources[dim]["stock"]`（不凭空增物）。"""
    s = _state()
    rep = holding_report(s)
    assert rep["ok"], rep["dims"]
    for dim in MATERIAL_DIMS:
        assert rep["dims"][dim]["merchant_total"] == _stock(s, dim), \
            f"{dim}: 商人持有应等于仓总量"


def test_supply_is_idempotent():
    """重复调用**不叠加**（按差额补足）。"""
    s = _state()
    first = holding_report(s)
    supply_merchant_materials(s)
    supply_merchant_materials(s)
    assert holding_report(s) == first, "重复搬运不得膨胀"


def test_supply_skips_routes_without_merchant():
    """无商人的路不参与分配，其份额留在总账（**不按比例代填**）。"""
    s = _state(with_stock=False)
    for dim in MATERIAL_DIMS:
        s.resources.setdefault(dim, {"stock": 1000, "cap": 1000})
    prefs = s.prefectures
    some_route = next(iter(prefs))
    (prefs[some_route].get("pops") or {}).pop("商人", None)
    supply_merchant_materials(s)
    assert merchant_goods(s, some_route) is None or \
        "木" not in (merchant_goods(s, some_route) or {})


# ====================================================== 3 · 缺失 ≠ 0
def test_missing_merchant_is_none_not_zero():
    """🔴 无商人 POP ⇒ 读数 `None`，**不是 0**。"""
    s = _state()
    (s.prefectures[R1].get("pops") or {}).pop("商人", None)
    assert material_holding_for_circuit(s, R1, "木") is None


def test_missing_dim_is_none():
    """维度槽不存在 ⇒ `None`。

    🔴 2026-10-03：建材按 `goods[治所]` 桶存放，故「删掉该维」须同时删扁平项**与各桶内该维**，
    否则桶里的旧值仍会被 `goods_amount()` 读出来。
    """
    s = _state()
    g = _mg(s, R1)
    g.pop("铁", None)
    for k in [k for k in g if "|" in k and isinstance(g.get(k), dict)]:
        g[k].pop("铁", None)
    assert material_holding_for_circuit(s, R1, "铁") is None


def test_unknown_route_is_none():
    s = _state()
    assert material_holding_for_circuit(s, "不存在路", "木") is None


def test_non_material_dim_rejected():
    s = _state()
    with pytest.raises(KeyError):
        material_holding_for_circuit(s, R1, "绸")


# ====================================================== 4 · 缺料不静默 / 不越路
def test_consume_returns_shortfall_not_silent():
    """🔴 扣不足返回**实扣量**，不静默吞掉。"""
    s = _state()
    _set(s, R1, "木", 40)
    got = consume_for_circuit(s, R1, "木", 300)
    assert got == 40
    assert material_holding_for_circuit(s, R1, "木") == 0


def test_consume_does_not_borrow_from_other_routes():
    """🔴 **不跨路借料**：本路无料时取 0（"运没运到"必须可观测）。"""
    s = _state()
    _set(s, R1, "木", 0)          # 本路无料
    _set(s, R2, "木", 99999)       # 别路堆满
    assert consume_for_circuit(s, R1, "木", 100) == 0
    assert material_holding_for_circuit(s, R2, "木") == 99999, "别路料须原样不动"


def test_consume_zero_amount_is_noop():
    s = _state()
    _set(s, R1, "石", 500)
    assert consume_for_circuit(s, R1, "石", 0) == 0
    assert material_holding_for_circuit(s, R1, "石") == 500


def test_consume_never_goes_negative():
    s = _state()
    _set(s, R1, "铁", 10)
    consume_for_circuit(s, R1, "铁", 999)
    assert material_holding_for_circuit(s, R1, "铁") == 0


# ====================================================== 5 · 维度合并
@pytest.mark.parametrize("cn,en", [("铁", "铁"), ("石", "石"), ("木", "木")])
def test_raw14_chinese_names_translate(cn, en):
    assert to_material_dim(cn) == en


def test_english_name_passes_through():
    assert to_material_dim("木") == "木"


def test_non_material_chinese_name_returns_none():
    """`粮` 走 `pops[].grain`，**不得臆断**映射成建材。"""
    assert to_material_dim("粮") is None
    assert to_material_dim("") is None


# ====================================================== 6 · 成交（复用 trade_goods）
def _two_merchants(s):
    """同路的**两个不同 POP**（买方士绅 / 卖方商人）。

    🔴 C-c 护栏：`trade_material` **拒绝跨州府**（跨路请用
    `core.material_trade.sell_material_across` 走真实在途），
    故同路成交用例必须用同路的不同 POP，否则是自成交。
    """
    return (s.prefectures[R1]["pops"]["士绅"],
            s.prefectures[R1]["pops"]["商人"])


def test_trade_conserves_goods_and_money():
    """🔴 成交后：`ΣPOP goods` 与 `ΣPOP wealth` **都不变**（只是转移）。"""
    s = _state()
    buyer, seller = _two_merchants(s)
    buyer["wealth"] = 100000.0
    seller["wealth"] = 0.0
    _set(s, R1, "木", 1000)
    g0, w0 = _sum_goods(s, "木"), _sum_wealth(s)

    res = trade_material(s, buyer_pop=buyer, seller_pop=seller,
                         dim="木", qty=100, price=2.0)
    assert res["traded"] == 100
    assert res["paid"] == 200
    assert _sum_goods(s, "木") == g0, "成交不得增删建材"
    assert _sum_wealth(s) == w0, "成交不得创造/销毁钱"
    assert res["material_delta"]["sum"] == 0


def test_trade_self_dealing_rejected():
    s = _state()
    m, _ = _two_merchants(s)
    with pytest.raises(ValueError):
        trade_material(s, buyer_pop=m, seller_pop=m, dim="木",
                       qty=1, price=1.0)


def test_trade_unmet_qty_returned():
    """买不够时 `unmet_qty` **原样返回**，不静默丢弃。"""
    s = _state()
    buyer, seller = _two_merchants(s)
    buyer["wealth"] = 30.0            # 只够买 15（单价 2）
    seller["wealth"] = 0.0
    _set(s, R1, "木", 1000)
    res = trade_material(s, buyer_pop=buyer, seller_pop=seller,
                         dim="木", qty=100, price=2.0)
    assert res["traded"] == 15
    assert res["unmet_qty"] == 85


def test_trade_rejects_non_material_dim():
    s = _state()
    buyer, seller = _two_merchants(s)
    with pytest.raises(KeyError):
        trade_material(s, buyer_pop=buyer, seller_pop=seller, dim="绸",
                       qty=1, price=1.0)


def test_trade_many_times_conserves():
    s = _state()
    buyer, seller = _two_merchants(s)
    buyer["wealth"] = 1_000_000.0
    seller["wealth"] = 0.0
    _set(s, R1, "木", 5000)
    _set(s, R1, "木", 0)
    g0, w0 = _sum_goods(s, "木"), _sum_wealth(s)
    for i in range(20):
        trade_material(s, buyer_pop=buyer, seller_pop=seller, dim="木",
                       qty=37, price=1.5, trade_id=f"t{i}")
    assert _sum_goods(s, "木") == g0
    assert _sum_wealth(s) == w0


# ====================================================== 州府级建材归属（2026-10-03 州府桶）
def test_supply_attributes_materials_into_goods_seat_buckets():
    """供给的新量按**州府人口**拆进 `goods[治所]` 桶，且总量守恒。

    迁移期口径：总量 = 扁平项 + Σ州府桶；供给只写**桶**，不双写扁平区。
    """
    s = _state()
    rep = seat_holding_report(s)
    assert rep["ok"] is True, f"州府桶报告异常：{rep['rows'][:3]}"
    moved = sum(r["seat_sum"] for r in rep["rows"])
    assert moved > 0, "供给后应有州府归属（桶全空＝钩子没生效）"
    for r in rep["rows"]:
        assert r["seat_sum"] >= 0 and r["flat"] >= 0, f"出现负存量：{r}"
        assert r["total"] == r["seat_sum"] + r["flat"]
    for circuit in (R1, R2):
        goods = merchant_goods(s, circuit)
        buckets = [k for k in goods if "|" in k and isinstance(goods[k], dict)]
        assert buckets, f"{circuit} 商人 goods 缺州府桶"
        # 桶之和 == 读数总量（证明没双计）
        per = sum(int(goods[b].get("木", 0) or 0) for b in buckets)
        assert per == goods_amount(goods, "木"), \
            f"{circuit} 桶之和 {per} != goods_amount {goods_amount(goods, '木')}（疑似双计）"


def test_seat_holding_reads_and_unknown_seat_is_none():
    """**缺失≠0**：未注册治所 ⇒ `None`（不臆造归属、不回落 0）。"""
    s = _state()
    weights = seat_weights_of_circuit(R1)
    assert weights, f"{R1} 应有治所人口权重"
    seat_id = weights[0][0]
    v = material_holding_for_seat(s, seat_id, "木")
    assert isinstance(v, int) and v > 0, f"{seat_id} 应有归属量，实得 {v!r}"
    assert material_holding_for_seat(s, "不存在|某州", "木") is None
    with pytest.raises(KeyError):
        material_holding_for_seat(s, seat_id, "绸")


def test_consume_for_seat_is_local_and_leaves_other_seats_intact():
    """州府扣料：只动**本治所桶**、返回实扣量，**不碰**别的治所与扁平区。"""
    s = _state()
    weights = seat_weights_of_circuit(R1)
    seat_id = weights[0][0]
    other_id = weights[1][0] if len(weights) > 1 else None
    have = material_holding_for_seat(s, seat_id, "木")
    other_before = (material_holding_for_seat(s, other_id, "木")
                    if other_id else None)
    take = min(10, have)
    got = consume_for_seat(s, seat_id, "木", take)
    assert got == take, f"实扣量应等于申请量：{got} != {take}"
    assert material_holding_for_seat(s, seat_id, "木") == have - got
    if other_id:
        assert material_holding_for_seat(s, other_id, "木") == other_before, \
            "扣 A 治所却动了 B 治所（桶之间应彼此独立）"
    over = consume_for_seat(s, seat_id, "木", 10 ** 9)
    assert over == have - got, f"扣不足应返回实扣量而非需求量：{over}"
    assert material_holding_for_seat(s, seat_id, "木") == 0


def test_seat_level_change_does_not_alter_other_circuits():
    """🔴 加法式保证：州府级扣料后，**路级口径变动恰好等于扣量，且不牵连异路**。"""
    s = _state()
    seat_id = seat_weights_of_circuit(R1)[0][0]
    r2_before = material_holding_for_circuit(s, R2, "木")
    r1_before = material_holding_for_circuit(s, R1, "木")
    consume_for_seat(s, seat_id, "木", 7)
    assert material_holding_for_circuit(s, R2, "木") == r2_before, "异路被牵连"
    assert material_holding_for_circuit(s, R1, "木") == r1_before - 7
    assert holding_report(s)["ok"] is True, "搬运守恒被破坏"
    assert seat_holding_report(s)["ok"] is True