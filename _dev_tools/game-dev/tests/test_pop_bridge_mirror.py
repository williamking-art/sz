# -*- coding: utf-8 -*-
"""**方案乙 · 派生镜像与字段桥接** 定向回归（2026-10-04）。

197 处 `pops` 直访里绝大多数是**读取**。若全改治所级遍历则工作面不可控，
故采用**派生镜像**：真账在州府级，路级 `pops` 是桥接层维护的镜像，
**所有写入走 `pop_set`/`pop_add`**，由它们保证「先落州府、再刷镜像」。

本组锁住：**写后镜像与真账恒等**，绝不漂移。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState                     # noqa: E402
from core.pop_bridge import (POP_CLASSES,                  # noqa: E402
                             aggregate_seat_pops, assert_pops_consistent,
                             pop_add, pop_get, pop_set,
                             split_pops_to_seats, sync_route_pops)


def _mk():
    s = GameState("史实")
    for rt, pd in s.prefectures.items():
        split_pops_to_seats(pd, rt)
        sync_route_pops(pd)
    return s


def test_mirror_matches_truth_after_split():
    s = _mk()
    for rt, pd in s.prefectures.items():
        assert not assert_pops_consistent(pd), "%s 镜像与真账失配" % rt


def test_pop_add_keeps_mirror_in_sync():
    s = _mk()
    pd = s.prefectures[next(iter(s.prefectures))]
    before = pop_get(pd, "官僚", "size")
    r = pop_add(pd, "官僚", "size", 1000)
    assert r == before + 1000
    assert pd["pops"]["官僚"]["size"] == r, "镜像未同步"
    assert pop_get(pd, "官僚", "size") == r, "真账未更新"
    assert not assert_pops_consistent(pd)


def test_pop_set_zero_propagates_to_all_seats():
    """写 0 必须铺到每个治所（不得只清一路、留下幽灵人口）。"""
    s = _mk()
    pd = s.prefectures[next(iter(s.prefectures))]
    pop_set(pd, "官僚", "size", 0)
    for sid, sv in pd["seats"].items():
        row = (sv.get("pops") or {}).get("官僚") or {}
        assert row.get("size") == 0, "%s 仍残留官僚 size" % sid


def test_negative_delta_floors_at_zero():
    s = _mk()
    pd = s.prefectures[next(iter(s.prefectures))]
    r = pop_add(pd, "官僚", "wealth", -(10 ** 9))
    assert r == 0, "扣减不得为负"
    assert pd["pops"]["官僚"]["wealth"] == 0


def test_all_routes_consistent_after_writes():
    s = _mk()
    for rt, pd in s.prefectures.items():
        pop_add(pd, "农", "wealth", 123)
        pop_set(pd, "兵", "size", 0)
    for rt, pd in s.prefectures.items():
        assert not assert_pops_consistent(pd), "%s 写入后失配" % rt


def test_aggregate_is_none_when_not_sunk():
    """缺失 ≠ 0：未下沉 ⇒ None，不回落空账。"""
    s = GameState("史实")
    pd = s.prefectures[next(iter(s.prefectures))]
    assert aggregate_seat_pops(pd, "农") is None
    assert pop_get(pd, "农", "size") is not None, "未下沉时应回落路级原账"
