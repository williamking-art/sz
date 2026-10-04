# -*- coding: utf-8 -*-
"""**方案乙 · settlement_finance 完整桥接化** 定向回归（2026-10-04）。

本模块 29 处 `pops` 访问中，全部**写入点**已接入 `pop_bridge`：
熔铜 / 银行(存款吸收·放贷·收息·回吐) / 税粮售卖 / 商业税发放 / 俸禄 /
欠税(计提·追缴) / 工匠商人酒课税 / 兵额重聚合 / 官僚缴税。

🔴 本组锁的是**下沉态长局不失配** —— 这正是此前报 72 处失配的缺陷。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState                     # noqa: E402
from core.pop_bridge import (assert_pops_consistent,       # noqa: E402
                             split_pops_to_seats, sync_route_pops)


def _sunk():
    s = GameState("史实")
    for rt, pd in s.prefectures.items():
        split_pops_to_seats(pd, rt)
        sync_route_pops(pd)
    return s


def test_no_drift_after_finance_settlements():
    """🔴 核心：12 次财政结算后，镜像与真账**零失配**（曾报 72 处）。"""
    from core.settlement_steps import _settle_finance
    s = _sunk()
    log = []
    for _ in range(12):
        _settle_finance(s, log)
    bad = []
    for rt, pd in s.prefectures.items():
        bad += ["%s|%s" % (rt, x) for x in assert_pops_consistent(pd)]
    assert not bad, "失配 %d 处：%s" % (len(bad), bad[:5])


def test_no_drift_across_several_modules():
    """跨模块长局（农业+财政）后仍不失配。"""
    from core.settlement_steps import _settle_finance, _settle_land_local
    s = _sunk()
    log = []
    for _ in range(6):
        _settle_land_local(s, log)
        _settle_finance(s, log)
    bad = []
    for rt, pd in s.prefectures.items():
        bad += ["%s|%s" % (rt, x) for x in assert_pops_consistent(pd)]
    assert not bad, "失配 %d 处：%s" % (len(bad), bad[:5])


def test_route_mirror_still_readable():
    """存量读取代码仍能读路级 pops（它是桥接维护的镜像）。"""
    s = _sunk()
    p = s.prefectures[next(iter(s.prefectures))]
    assert isinstance(p["pops"]["官僚"]["size"], int)
    assert p["pops"]["官僚"]["size"] > 0
