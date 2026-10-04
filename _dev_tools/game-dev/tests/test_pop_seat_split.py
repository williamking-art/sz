# -*- coding: utf-8 -*-
"""**州府级 POP 基座（方案乙）** 定向回归（2026-10-04）。

用户裁定 POP 实体下沉州府级：真账在 `prefectures[路]["seats"][治所]["pops"]`，
路级 `pops` 降为只读派生聚合（Σ 治所）。

本组锁住核心不变式：**拆分/聚合逐字段精确守恒**，不丢一人一钱。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState                    # noqa: E402
from core.pop_bridge import (POP_CLASSES, SPLIT_FIELDS,   # noqa: E402
                             aggregate_seat_pops, split_pops_to_seats, survey_pops)


def _split_all():
    s = GameState("史实")
    for route, pdata in s.prefectures.items():
        split_pops_to_seats(pdata, route)
    return s


def test_split_is_field_exact_conserving():
    """🔴 核心：Σ治所 必须**逐字段**等于路级原值（不丢一人一钱）。"""
    s = _split_all()
    r = survey_pops(s)
    assert not r["字段失配"], "字段失配：%s" % r["字段失配"][:5]
    assert r["已下沉路由"] == r["路由数"]


def test_split_creates_seats_for_every_route():
    s = _split_all()
    for route, pdata in s.prefectures.items():
        assert pdata.get("seats"), "%s 未拆出治所" % route


def test_split_is_idempotent():
    """重复调用不得二次拆分（否则 size 翻倍）。"""
    s = GameState("史实")
    route = next(iter(s.prefectures))
    pdata = s.prefectures[route]
    n1 = split_pops_to_seats(pdata, route)
    before = pdata["seats"][next(iter(pdata["seats"]))]["pops"]["农"]["size"]
    n2 = split_pops_to_seats(pdata, route)
    after = pdata["seats"][next(iter(pdata["seats"]))]["pops"]["农"]["size"]
    assert n1 == n2
    assert before == after, "重复拆分导致 size 变化：%s -> %s" % (before, after)


def test_aggregate_returns_none_when_not_sunk():
    """缺失 ≠ 0：未下沉时聚合返回 None（表示"未下沉"），不回落成空账。"""
    s = GameState("史实")
    pdata = s.prefectures[next(iter(s.prefectures))]
    assert aggregate_seat_pops(pdata, "农") is None


def test_all_six_pop_classes_present():
    """6 类 POP 都要下沉（挂载律：人只落这 6 类）。"""
    s = _split_all()
    pdata = s.prefectures[next(iter(s.prefectures))]
    for cls in POP_CLASSES:
        seat = next(iter(pdata["seats"].values()))
        assert cls in (seat["pops"] or {}), "治所缺 POP 类 %s" % cls


def test_original_route_pops_untouched():
    """下沉不修改路级原账（它仍是派生视图的对照基准）。"""
    s = GameState("史实")
    route = next(iter(s.prefectures))
    pdata = s.prefectures[route]
    snap = {c: dict(pdata["pops"][c]) for c in POP_CLASSES if c in pdata["pops"]}
    split_pops_to_seats(pdata, route)
    for cls, row in snap.items():
        assert pdata["pops"][cls] == row, "下沉改动了路级原账 %s" % cls
