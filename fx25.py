import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_transport_transit.py"
t=open(f,encoding="utf-8").read()
NEW='''def test_state_has_no_month_index_field():
    """🔴 防回归：`GameState` **没有** `month_index` 字段。

    历史坑：本模块曾用 `getattr(state, "month_index", 0)` 取月份，
    而该字段**根本不存在** ⇒ 恒返回 0 ⇒ 在途批次的 `arrive_month`
    **永远等于发货当月** ⇒ **物流彻底失效**（所有货瞬间到达，
    正是 C-c 要防的事）。真字段是 `year`/`month`，经
    `abs_month_index()` 绝对化。本用例把该事实钉住。
    """
    s = _state()
    assert not hasattr(s, "month_index"), \\
        "若将来真加了 month_index，请同步 transport._now 的口径"
    assert hasattr(s, "year") and hasattr(s, "month")


def test_dispatch_uses_real_calendar_not_zero():
    """🔴 发货月必须来自**真实日历**，而不是恒 0。"""
    from core.civil_building import abs_month_index
    s = _state()
    _set_month(s, 10)
    _give(s, A, "timber", 1000)
    res = transport.dispatch(s, frm=A, to=FAR, dim="timber", qty=100)
    now = abs_month_index(s)
    assert res["ok"]
    assert res["arrive_month"] == now + res["days"], \\
        f"到货月应由绝对月序推导：now={now} days={res['days']}"
    assert res["arrive_month"] > now, "跨路必须晚于发货月"


def test_undefined_calendar_refuses_to_dispatch():
    """🔴 时点未定义 ⇒ **拒绝建批次**（不猜、不回落 0），且**不扣货**。"""
    s = _state()
    _give(s, A, "timber", 1000)
    s.year = None
    s.month = None
    res = transport.dispatch(s, frm=A, to=FAR, dim="timber", qty=100)
    assert res["ok"] is False and res["reason"] == "time_undefined"
    assert transport.in_transit(s) == [], "时点未定义不得建批次"
    # 🔴 更重要：货**不得被扣掉**（扣了又没批次＝凭空消失）
    assert int((merchant_goods(s, "京畿路") or {})["timber"]) == 1000


def test_state_carries_transit_book():'''
t=t.replace("def test_state_carries_transit_book():", NEW, 1)
open(f,"w",encoding="utf-8").write(t)
print("ok")
