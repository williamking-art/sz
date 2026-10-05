# -*- coding: utf-8 -*-
"""**交通边与在途批次**定向回归（P0 · 2026-10-02）。

C-c 定的是「工地只从本地取、取不到即缺料」，理由是「这样物流才有意义」。
但发货若**瞬移**，"运没运到"就不可观测。`core/transport.py` 补上这一层。

本组锁：
1. **距离 → 耗时**是纯计算，可复算；同州府 0 耗时；未知州府 `None`；
2. 🚫 **不臆造路况**：`ROAD_QUALITY` 默认空，耗时按平地常数，且读数自述是**设定值**；
3. **发货即扣货**，**钱货两清或两不做**（扣不到就不建批次）；
4. 🔴 **未到不入账**——这是"运没运到"可观测的关键；
5. **批次可查**且与 `market_readout.in_transit` 结构对齐。
"""
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core import transport                                       # noqa: E402
from core.game_state import GameState                            # noqa: E402
from core.legacy_mechanic import init_legacies                   # noqa: E402
from core.material_holding import (                              # noqa: E402
    goods_amount, merchant_goods, supply_merchant_materials,
)
from core.production_chain import settle_production_chain        # noqa: E402

A = "京畿路|开封府"      # 京畿路治所
B = "京畿路|郑州"        # 同路另一治所
FAR = "两浙路|杭州"           # 远处：**无直达道路**（测"不通"）
NB = "京西路|河南府"         # **跨路相邻**（实测 is_adjacent=True，耗时 1 月）


def _state():
    s = GameState("史实")
    init_legacies(s)
    settle_production_chain(s, [])
    # 6.33：产出链的未裁定维（**含木石**）落**归属待定槽**，
    # 不得采购/发运；故此处**显式准备已确权、可用的库存**，供运输用例使用。
    for _d in ("木", "石"):
        _sl = s.resources.setdefault(_d, {"stock": 0, "cap": 50_000})
        if int(_sl.get("stock", 0) or 0) <= 0:
            _sl["stock"] = 10_000
    supply_merchant_materials(s)
    return s


def _nb_wealth(s):
    from core.prefecture_entity import split_seat_id
    c,_ = split_seat_id(NB)
    return s.prefectures[c]["pops"]["商人"]


def _give(s, seat_id, dim, qty):
    """把该路商人货栈的建材**总量**设为 `qty`（覆盖语义，便于测"无料"）。

    🔴 2026-10-03：建材已按 `goods[治所][dim]` 州府桶存放，故须**先清该维全部桶**
    再写扁平区，否则「设为 0」并不真的无料。
    """
    from core.prefecture_entity import split_seat_id
    circuit, _ = split_seat_id(seat_id)
    goods = merchant_goods(s, circuit)
    for k in [k for k in goods if "|" in k and isinstance(goods.get(k), dict)]:
        goods[k].pop(dim, None)
    goods[dim] = int(qty)


def _have(s, seat_id, dim):
    from core.prefecture_entity import split_seat_id
    circuit, _ = split_seat_id(seat_id)
    goods = merchant_goods(s, circuit)
    if goods is None:
        return None
    return goods_amount(goods, dim)


def _set_month(s, a):
    """把**绝对月序** `a` 写成真实字段 `year`/`month`（1..12）。

    🔴 逆运算必须精确：`abs_month_index = year*12 + month`，
    故 `year = a // 12`、`month = a % 12`（余 0 时退到前一年 12 月，
    保证 `month` 落在游戏合法的 1..12）。
    """
    a = int(a)
    y, m = a // 12, a % 12
    if m == 0:
        y, m = y - 1, 12
    s.year = int(y)
    s.month = int(m)


# ====================================================== 1 · 距离 → 耗时
def test_haversine_known_distance():
    """开封→杭州 大圆距离在合理量级（~700km 级）。"""
    km = transport.haversine_km(114.31, 34.80, 120.16, 30.28)
    assert 600 < km < 900, f"实际 {km:.0f} km"


def test_same_seat_is_zero_days():
    assert transport.route_days(A, A) == 0


def test_same_circuit_nearby_is_at_least_one_month():
    """同城府内不同治所：距离短，但**不做"同月到达"**（下限 1 月）。"""
    d = transport.route_days(A, B)
    assert d is not None and d >= 1


def test_far_route_takes_longer():
    """远路耗时 >= 近路（耗时随距离单调）；**无直达道路时跳过**（符合"不做全图互通"）。"""
    near = transport.route_days(A, B)
    far = transport.route_days(A, FAR)
    if far is None:
        pytest.skip("两地间无直达道路（相邻阈值外）——符合『不做全图互通』规格")
    assert far is not None and near is not None
    assert far >= near


def test_adjacency_threshold_blocks_far_pairs():
    """🔴 **不做全图任意互通**（规格 tasks.md:88）。

    超出 `ADJACENT_KM` 的两地**没有直达道路** ⇒ `route_days` 返回 `None`
    （"不通"），**不是**返回一个很大的天数。
    """
    assert transport.ADJACENT_KM > 0
    assert transport.is_adjacent(A, B) is True, "同路邻近治所应有路"
    assert transport.is_adjacent(A, FAR) is False
    assert transport.route_days(A, FAR) is None


def test_unknown_seat_adjacency_is_none():
    """未知州府 ⇒ `None`（读不出），**不判 True/False**。"""
    assert transport.is_adjacent(A, "不存在|某州") is None
    assert transport.route_days(A, "不存在|某州") is None


def test_adjacency_threshold_is_declared_setting_not_history():
    """⚠️ 阈值是**设定值非史料**——钉住这条声明，别让它被当成史料引用。"""
    src = open(transport.__file__, encoding="utf-8").read()
    assert "设定值" in src and "不是史料" in src, "相邻阈值须自述为设定值"


def test_unknown_seat_is_none_not_zero():
    """🔴 未登记州府 ⇒ `None`（缺失≠0）；回落 0 等于"瞬移"。"""
    assert transport.route_days(A, "不存在|某州") is None
    assert transport.route_days("不存在|某州", A) is None


def test_road_quality_defaults_empty():
    """🚫 不臆造路况：默认表为空，耗时按平地常数。"""
    assert transport.ROAD_QUALITY == {}, "无史料支撑的路况不得预填"
    assert transport.KM_PER_MONTH > 0


def test_transit_report_declares_setting_not_history():
    """读数必须自述是**设定值、非史料**。"""
    s = _state()
    rep = transport.transit_report(s)
    assert rep["implemented"] is True
    assert "非史料" in rep["note"] or "设定值" in rep["note"]


# ====================================================== 2 · 发货
def test_dispatch_deducts_immediately_and_creates_batch():
    """发货：**立刻扣货** + 建批次。"""
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    before = _have(s, A, "木")
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=300)
    assert res["ok"] and res["shipped"] == 300
    assert _have(s, A, "木") == before - 300, "发货须立刻扣源"
    assert len(transport.in_transit(s)) == 1


def test_dispatch_without_stock_creates_nothing():
    """🔴 钱货两清或两不做：扣不到货**不建批次**，不产生凭空在途。"""
    s = _state()
    _give(s, A, "木", 0)
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=100)
    # 目的地 NB 与 A **有路** ⇒ 这才轮得到查库存，验证"无货不建批次"
    assert transport.is_adjacent(A, NB) is True
    assert res["ok"] is False and res["reason"] == "no_stock_local"
    assert transport.in_transit(s) == [], "无货不得凭空生成在途"


def test_dispatch_to_unreachable_route_is_route_undefined():
    """🔴 **不通 ≠ 远**：超出相邻阈值应报 `route_undefined`，且**压根不扣货**。

    「不做全图任意互通」（规格 tasks.md:88）的实际效果：远地**发不出去**，
    货**仍留在卖方**，不会因为"路远"就凭空消失。
    """
    s = _state()
    _give(s, A, "木", 1000)
    res = transport.dispatch(s, frm=A, to=FAR, dim="木", qty=100)
    assert transport.is_adjacent(A, FAR) is False, "前提：FAR 与 A 无直达道路"
    assert res["ok"] is False and res["reason"] == "route_undefined"
    assert transport.in_transit(s) == [], "不通不得建批次"
    assert int((merchant_goods(s, "京畿路") or {})["木"]) == 1000, \
        "🔴 不通时货须留在卖方（扣了又没批次＝凭空消失）"


def test_dispatch_unknown_origin_rejected():
    s = _state()
    res = transport.dispatch(s, frm="不存在|某州", to=FAR, dim="木", qty=1)
    assert res["ok"] is False and res["reason"] == "unknown_origin"
    assert transport.in_transit(s) == []


def test_dispatch_zero_qty_is_no_demand():
    """期望量为 0 不是"未满足"（B0-3 口径）。"""
    s = _state()
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=0)
    assert res["ok"] and res["reason"] == "no_demand"


# ====================================================== 3 · 未到不入账（关键）
def test_goods_not_arrived_are_not_credited():
    """🔴 **未到不入账**——这是"运没运到"可观测的关键。"""
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    dst_before = _have(s, NB, "木")
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=300)
    assert res["arrive_month"] > 10, "跨路不应当月到达"

    arrived = transport.arrive_due(s)
    assert arrived == [], "未到期不得入账"
    assert _have(s, NB, "木") == dst_before, "目的地不得凭空增料"
    assert len(transport.in_transit(s)) == 1, "批次应仍在途"


def test_goods_arrive_after_due_month():
    """到月份才入账，且批次从在途移除。"""
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    dst_before = _have(s, NB, "木")
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=300)

    _set_month(s, res["arrive_month"])
    arrived = transport.arrive_due(s)
    assert len(arrived) == 1 and arrived[0]["qty"] == 300
    assert _have(s, NB, "木") == dst_before + 300
    assert transport.in_transit(s) == []


def test_arrive_due_is_idempotent_per_batch():
    """同一批次**不会重复入账**。"""
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=200)
    _set_month(s, res["arrive_month"])
    transport.arrive_due(s)
    after = _have(s, NB, "木")
    transport.arrive_due(s)
    transport.arrive_due(s)
    assert _have(s, NB, "木") == after, "重复调用不得重复入账"


def test_arrive_keeps_batch_when_destination_has_no_merchant():
    """目的地无商人货栈 ⇒ **保留批次**，不静默丢弃（缺失≠0）。"""
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=200)
    # 把**有路目的地** NB 的商人挪走
    s.prefectures["京西路"]["pops"].pop("商人", None)
    _set_month(s, res["arrive_month"])
    arrived = transport.arrive_due(s)
    assert arrived == []
    assert len(transport.in_transit(s)) == 1, "无法入账的批次须保留，不得丢弃"


# ====================================================== 4 · 台账结构
def test_transit_report_shape_matches_market_readout():
    """与 `market_readout.in_transit` 的结构对齐（原先 `implemented: False`）。"""
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 500)
    transport.dispatch(s, frm=A, to=NB, dim="木", qty=100)
    rep = transport.transit_report(s)
    for k in ("implemented", "items", "count"):
        assert k in rep, f"缺字段 {k}"
    assert rep["implemented"] is True
    assert rep["count"] == 1
    it = rep["items"][0]
    for k in ("from", "to", "dim", "qty", "arrive_month"):
        assert k in it


def test_state_has_no_month_index_field():
    """🔴 防回归：`GameState` **没有** `month_index` 字段。

    历史坑：本模块曾用 `getattr(state, "month_index", 0)` 取月份，
    而该字段**根本不存在** ⇒ 恒返回 0 ⇒ 在途批次的 `arrive_month`
    **永远等于发货当月** ⇒ **物流彻底失效**（所有货瞬间到达，
    正是 C-c 要防的事）。真字段是 `year`/`month`，经
    `abs_month_index()` 绝对化。本用例把该事实钉住。
    """
    s = _state()
    assert not hasattr(s, "month_index"), \
        "若将来真加了 month_index，请同步 transport._now 的口径"
    assert hasattr(s, "year") and hasattr(s, "month")


def test_dispatch_uses_real_calendar_not_zero():
    """🔴 发货月必须来自**真实日历**，而不是恒 0。"""
    from core.civil_building import abs_month_index
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=100)
    now = abs_month_index(s)
    assert res["ok"]
    assert res["arrive_month"] == now + res["days"], \
        f"到货月应由绝对月序推导：now={now} days={res['days']}"
    assert res["arrive_month"] > now, "跨路必须晚于发货月"


def test_undefined_calendar_refuses_to_dispatch():
    """🔴 时点未定义 ⇒ **拒绝建批次**（不猜、不回落 0），且**不扣货**。"""
    s = _state()
    _give(s, A, "木", 1000)
    s.year = None
    s.month = None
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=100)
    assert res["ok"] is False and res["reason"] == "time_undefined"
    assert transport.in_transit(s) == [], "时点未定义不得建批次"
    # 🔴 更重要：货**不得被扣掉**（扣了又没批次＝凭空消失）
    assert int((merchant_goods(s, "京畿路") or {})["木"]) == 1000


def test_state_carries_transit_book():
    """`GameState` 必须带 `material_transit`，否则存档往返会丢批次。"""
    s = _state()
    assert isinstance(getattr(s, "material_transit", None), list)


# ====================================================== 5 · 存档往返
def test_transit_survives_save_load_round_trip():
    """🔴 **存档往返不得丢在途**——否则货已从卖方扣掉却永远不到（凭空消失）。

    这是引入 `state.material_transit` 时自己标注过的前置，
    必须由用例守护，**不能靠"记得写"**。
    """
    from core.save_load import load_game, save_game
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    dst_before = _have(s, NB, "木")   # 目的地原有量（配货而来，非 0）
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=300)
    assert res["ok"] and res["arrive_month"] > 10
    src_before = _have(s, A, "木")

    assert save_game(s, slot=97)
    s2 = load_game(slot=97)

    book = getattr(s2, "material_transit", None)
    assert isinstance(book, list) and len(book) == 1, \
        f"在途批次未随存档往返：{book!r}"
    b = book[0]
    for k in ("from", "to", "dim", "qty", "arrive_month"):
        assert k in b, f"批次缺字段 {k}"
    assert b["qty"] == 300
    assert b["arrive_month"] == res["arrive_month"]
    assert _have(s2, A, "木") == src_before, "存档不得凭空改卖方存量"

    s2.year=1101; s2.month=1+(int(b["arrive_month"])%12)
    transport.arrive_due(s2)
    assert _have(s2, NB, "木") == dst_before + 300, "到货应叠加在原有量上"


def test_old_save_without_transit_key_loads_as_empty():
    """旧档**没有**该键 ⇒ 读成空列表，**不得拒档**。"""
    from core.save_load import load_game, save_game
    s = _state()
    assert save_game(s, slot=98)
    s2 = load_game(slot=98)
    assert getattr(s2, "material_transit", None) == []


# ====================================================== 4 · 州府级可观测（2026-10-03 · 方案 C）
def test_dispatch_batch_records_destination_circuit():
    """批次自带**路级归属**：「运到哪条路」不必反查州府索引。"""
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=300)
    assert res["ok"] and res["shipped"] == 300
    b = transport.in_transit(s)[0]
    assert b["from_circuit"] == "京畿路", f"源路归属错：{b['from_circuit']!r}"
    assert b["to_circuit"] == "京西路", f"目的路归属错：{b['to_circuit']!r}"


def test_transit_by_seat_is_conserved_against_dispatch():
    """🔴 `transit_by_seat` 按**目的地治所**汇总在途量，且 Σ == 实际发货量（守恒）。"""
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    r1 = transport.dispatch(s, frm=A, to=NB, dim="木", qty=300)
    r2 = transport.dispatch(s, frm=A, to=NB, dim="石", qty=120)
    rows = transport.transit_by_seat(s)
    assert NB in rows, f"在途读数缺目的地治所 {NB}：{rows!r}"
    row = rows[NB]
    assert row["circuit"] == "京西路"
    assert row["batches"] == 2
    assert row["qty"]["木"] == r1["shipped"]
    assert row["qty"]["石"] == r2["shipped"]
    total = sum(v["qty"][d] for v in rows.values() for d in v["qty"])
    assert total == r1["shipped"] + r2["shipped"], "州府级在途汇总与发货量不符（漏记/重复记）"


def test_arrived_batch_reports_destination_seat():
    """到货批次带出**落在哪个治所**——C-c「先运到才能用」缺的那一半可观测性。"""
    s = _state()
    _set_month(s, 10)
    _give(s, A, "木", 1000)
    res = transport.dispatch(s, frm=A, to=NB, dim="木", qty=300)
    _set_month(s, res["arrive_month"])
    arrived = transport.arrive_due(s)
    assert len(arrived) == 1
    a0 = arrived[0]
    assert a0["arrived_seat_id"] == NB, f"到货治所错：{a0['arrived_seat_id']!r}"
    assert a0["arrived_circuit"] == "京西路"
    assert a0["arrived_month"] == res["arrive_month"]
    assert transport.transit_by_seat(s) == {}, "到货后该治所不应仍在途"


def test_transit_by_seat_empty_is_empty_dict_not_zero():
    """**缺失 ≠ 0**：无在途批次 ⇒ `{}`，不得回落成「各州府在途 0」的假读数。"""
    s = _state()
    assert transport.in_transit(s) == []
    assert transport.transit_by_seat(s) == {}, "空在途应为空字典，而非 0 州府"
    rep = transport.transit_report(s)
    assert rep["by_seat"] == {} and rep["count"] == 0