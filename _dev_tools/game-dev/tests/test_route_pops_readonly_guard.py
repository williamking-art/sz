# -*- coding: utf-8 -*-
"""路级 `pops` 只读守卫：证明「写入已全部桥接化」，并锁定剩余直写字段的基线。"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

import pytest

from core.game_state import GameState
from core.pop_bridge import (POP_CLASSES, install_all_guards, pops_guard_violations,
                                reset_pops_guard, split_pops_to_seats,
                                sync_route_pops)

SETTLE = None


def _sunk_with_guard():
    s = GameState('史实')
    for rt, pd in s.prefectures.items():
        split_pops_to_seats(pd, rt)
        sync_route_pops(pd)
    install_all_guards(s)
    reset_pops_guard()
    return s


def _run(s, rounds):
    from core.settlement_steps import (_settle_land_local, _settle_finance,
                                       _settle_granary, _settle_officialdom,
                                       _settle_clerks, _settle_emperor_personal)
    log = []
    for _ in range(rounds):
        for fn in (_settle_land_local, _settle_finance, _settle_granary,
                   _settle_officialdom, _settle_clerks, _settle_emperor_personal):
            fn(s, log)


def test_guard_catches_direct_write():
    """守卫**必须真能抓到**直写（否则下面的零违规是假象）。"""
    s = _sunk_with_guard()
    rt = list(s.prefectures)[0]
    s.prefectures[rt]['pops']['\u519c']['size'] = 12345
    v = pops_guard_violations()
    assert v, '守卫没抓到直接写入 —— 守卫本身失效'
    assert any('size' in x for x in v), v[:2]


def test_guard_ignores_bridge_refresh():
    """桥接自身的镜像刷新**不算**违规。"""
    s = _sunk_with_guard()
    from core.pop_bridge import pop_add
    rt = list(s.prefectures)[0]
    cls = POP_CLASSES[0]
    assert pop_add(s.prefectures[rt], cls, 'size', 7) is not None
    assert not pops_guard_violations(), pops_guard_violations()[:3]


#: 当前守卫覆盖的结算子步没有获准的遗留路级直写；新增字段必须继续保持空基线。
#: grain      → POP 真账已在 seats；路级 pops[].grain 是派生兼容镜像。
#: 身份子池、宗族已桥接；路级产粮基数不属于 POP 写账。
KNOWN_LEGACY_WRITES = set()


def test_no_unexpected_direct_writes():
    """🔴 长局中**不得出现基线之外**的直写字段。

    这是「写入已全部桥接化」的**可执行**守卫：新增一行绕过桥接的直写会在这里炸掉。
    """
    s = _sunk_with_guard()
    _run(s, 3)
    v = pops_guard_violations()
    hit = set()
    for item in v:
        if "['" in item:
            hit.add(item.split("['", 1)[1].split("']", 1)[0])
    unexpected = hit - KNOWN_LEGACY_WRITES
    assert not unexpected, '出现基线外的直写字段：%s' % sorted(unexpected)


def test_identity_subpools_and_clan_have_no_direct_writes():
    """断言已知 POP 字段在结算子步中无未桥接直写（当前遗留直写基线为空），防止"\u9759\u9ed8\u5931\u8d25"\u3002"""
    s = _sunk_with_guard()
    _run(s, 3)
    v = pops_guard_violations()
    hit = set()
    for item in v:
        if "['" in item:
            hit.add(item.split("['", 1)[1].split("']", 1)[0])
    assert hit <= KNOWN_LEGACY_WRITES, sorted(hit)


def test_full_monthly_settlement_keeps_route_pops_derived():
    """真实新局跑月结全管线：守卫零直写、路级镜像与州府真账一致。"""
    from core.commands import new_game
    from core.settlement import run_monthly_settlement
    from core.foundation.ledger.pop_bridge import assert_pops_consistent
    from core.domains.administration.officialdom import check_invariants

    state = new_game()
    assert install_all_guards(state) > 0
    reset_pops_guard()
    for _ in range(15):
        run_monthly_settlement(state)
        assert not pops_guard_violations(), pops_guard_violations()[:10]
        assert all(not assert_pops_consistent(p)
                   for p in state.prefectures.values())
        ok, bad = check_invariants(state)
        assert ok, bad[:10]


def test_player_military_recruitment_keeps_pop_truth_on_seats():
    """非月结玩家命令扩编：真账守恒，路级仅派生刷新。"""
    from core.commands import new_game, issue_military_order
    from core.foundation.ledger.pop_bridge import assert_pops_consistent

    state = new_game()
    assert install_all_guards(state) > 0
    units_by_tier = {}
    for unit in state.army_units:
        units_by_tier.setdefault(unit.tier, []).append(unit)
    unit = next(us[0] for us in units_by_tier.values() if us)
    route = unit.station if unit.station in state.prefectures else next(iter(state.prefectures))
    unit.station = route
    pdata = state.prefectures[route]
    pdata["refugees"] = 50_000
    state.treasury = max(state.treasury, 10_000_000)
    reset_pops_guard()

    before = {
        cls: sum(int(((seat.get("pops") or {}).get(cls) or {}).get("size", 0) or 0)
                 for seat in pdata["seats"].values())
        for cls in ("农", "兵")
    }
    message = issue_military_order(state, unit.unit_id, "扩编", scale=1)
    assert "增募" in message or "批红" in message
    assert not pops_guard_violations(), pops_guard_violations()[:10]

    after = {
        cls: sum(int(((seat.get("pops") or {}).get(cls) or {}).get("size", 0) or 0)
                 for seat in pdata["seats"].values())
        for cls in ("农", "兵")
    }
    assert after["农"] + after["兵"] == before["农"] + before["兵"]
    for cls in ("农", "兵"):
        assert int(pdata["pops"][cls]["size"]) == after[cls]
        assert not assert_pops_consistent(pdata)


def test_single_whip_tax_arrears_keeps_pop_truth_on_seats():
    """一条鞭法田赋折银欠税：真账落治所，路级镜像一致，守卫零直写。"""
    from core.commands import new_game
    from core.settlement_steps import _settle_land_local
    from core.foundation.ledger.pop_bridge import assert_pops_consistent, pop_get

    state = new_game()
    state.single_whip = True
    state.month = 3  # 收获月田赋结算
    r0 = next(iter(state.prefectures.values()))
    r0["pops"]["农"]["wealth"] = 0
    r0["pops"]["士绅"]["wealth"] = 0
    for seat in r0.get("seats", {}).values():
        seat["pops"]["农"]["wealth"] = 0
        seat["pops"]["士绅"]["wealth"] = 0

    assert install_all_guards(state) > 0
    reset_pops_guard()

    log = []
    _settle_land_local(state, log)
    assert not pops_guard_violations(), pops_guard_violations()[:10]

    nong_arrears = pop_get(r0, "农", "欠税")
    shen_arrears = pop_get(r0, "士绅", "欠税")
    assert nong_arrears > 0, "农户现金不足应产生欠税"
    assert shen_arrears > 0, "士绅现金不足应产生欠税"
    assert int(r0["pops"]["农"]["欠税"]) == nong_arrears
    assert int(r0["pops"]["士绅"]["欠税"]) == shen_arrears
    assert not assert_pops_consistent(r0)


def test_estate_settlement_keeps_pop_truth_on_seats():
    """启用家产经济循环：各转移/窖藏都写州府真账，不直写路级镜像。"""
    from application.game_init import new_game
    from core.domains.administration.estate_mechanic import (
        estate_slice_total, settle_minister_estate,
    )
    from core.foundation.ledger.pop_bridge import assert_pops_consistent

    state = new_game()
    from core import money

    state._economy_ai = {"景气": "中"}
    money_before = money.m_all(state)
    assert install_all_guards(state) > 0
    reset_pops_guard()

    result = settle_minister_estate(state, [])
    assert set(result) == {"luxury", "rent", "hoard"}
    assert not pops_guard_violations(), pops_guard_violations()[:20]

    for pdata in state.prefectures.values():
        assert not assert_pops_consistent(pdata)
    seat_estate = sum(
        int(((seat.get("pops") or {}).get("士绅") or {}).get("estate", 0) or 0)
        for pdata in state.prefectures.values()
        for seat in (pdata.get("seats") or {}).values()
    )
    seat_hoard = sum(
        int(((seat.get("pops") or {}).get("士绅") or {}).get("estate_hoard", 0) or 0)
        for pdata in state.prefectures.values()
        for seat in (pdata.get("seats") or {}).values()
    )
    assert seat_estate == estate_slice_total(state, "estate")
    assert seat_hoard == estate_slice_total(state, "estate_hoard")
    assert seat_estate == sum(int((row or {}).get("wealth", 0) or 0)
                              for row in state.minister_estate.values())
    assert seat_hoard == sum(int((row or {}).get("窖银", 0) or 0)
                             for row in state.minister_estate.values())
    assert money.m_all(state) == money_before, "家产月循环的 POP 内部转移不得改变 M_ALL"


def test_civilian_hoard_transfers_keep_pop_truth_on_seats():
    """士绅囤粮与市舶窖银：wealth/grain/窖银均只改州府真账。"""
    from application.game_init import new_game
    from core.settlement_econ import _settle_civilian_hoard
    from core.foundation.ledger.grain_bridge import grain_get
    from core.foundation.ledger.pop_bridge import assert_pops_consistent, pop_get

    state = new_game()
    state._economy_ai = {"士绅": "囤", "士绅力度": "大", "窖银": "无"}
    state.maritime = {"open": True, "silver_in": 10_000_000}
    for pdata in state.prefectures.values():
        pdata["grain_price"] = 0.2

    money_before = sum(
        int(((seat.get("pops") or {}).get(cls) or {}).get("wealth", 0) or 0)
        for pdata in state.prefectures.values()
        for seat in (pdata.get("seats") or {}).values()
        for cls in (seat.get("pops") or {})
    )
    grain_before = sum(
        int(grain_get((seat.get("pops") or {}).get("士绅") or {}) or 0)
        for pdata in state.prefectures.values()
        for seat in (pdata.get("seats") or {}).values()
    )
    silver_before = int(state.maritime["silver_in"])

    assert install_all_guards(state) > 0
    reset_pops_guard()
    _settle_civilian_hoard(state, [])
    assert not pops_guard_violations(), pops_guard_violations()[:20]

    money_after = sum(
        int(((seat.get("pops") or {}).get(cls) or {}).get("wealth", 0) or 0)
        for pdata in state.prefectures.values()
        for seat in (pdata.get("seats") or {}).values()
        for cls in (seat.get("pops") or {})
    )
    grain_after = sum(
        int(grain_get((seat.get("pops") or {}).get("士绅") or {}) or 0)
        for pdata in state.prefectures.values()
        for seat in (pdata.get("seats") or {}).values()
    )
    silver_after = int(state.maritime["silver_in"])

    assert money_after == money_before, "士绅囤粮买入只转移 POP 财富，不造币/灭币"
    assert grain_after > grain_before, "士绅囤粮应收到商品粮"
    assert silver_after < silver_before, "已开市舶时银入窖应从银池扣减"
    for pdata in state.prefectures.values():
        assert not assert_pops_consistent(pdata)
