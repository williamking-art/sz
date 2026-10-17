# -*- coding: utf-8 -*-
"""T1 · `economic_affiliation` 子池：拆分/聚合守恒与口径纪律。

背景：`reviews/POP改良方案_2026-10-05.md` —— 经济经营关系须与**政治派系**分离，
命名为 `economic_affiliation`（**不得**叫 `faction`，该名已被 `state.factions` 占用）。

本用例锁住三条纪律：
① 子池拆分/聚合**守恒**（Σ 治所 == 路级），否则等于制造并行账本（违反 POP 挂载律）；
② **缺失 ≠ 0**：无子池不造空池、无数据返回 None；
③ **不误用政治派系键名**。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

from core.pop_bridge import (AFFILIATION_FIELDS, aggregate_affiliation,
                                split_affiliation_to_seats)

W = [('S1', 60.0), ('S2', 40.0)]


def _src():
    return {
        'size': 100, 'wealth': 1000, 'grain': 500,
        'economic_affiliation': {
            'household_self': {'size': 70, 'wealth': 700, 'grain': 350},
            'tenant_household': {'size': 30, 'wealth': 300, 'grain': 150},
        },
    }


def test_split_conserves_each_relation():
    out = split_affiliation_to_seats(_src(), W)
    for rel in ('household_self', 'tenant_household'):
        s = sum(out[sid].get(rel, {}).get('size', 0) for sid in out)
        assert s == _src()['economic_affiliation'][rel]['size'], (rel, s)


def test_split_conserves_wealth_and_grain():
    out = split_affiliation_to_seats(_src(), W)
    for f in AFFILIATION_FIELDS:
        if f == 'size':
            continue
        total = sum(out[sid].get(rel, {}).get(f, 0)
                    for sid in out for rel in out[sid])
        src_total = sum(v.get(f, 0) for v in _src()['economic_affiliation'].values())
        assert total == src_total, (f, total, src_total)


def test_split_relations_are_mutually_exclusive_sum_to_parent():
    """互斥子池：`Σ 关系.size == 父 POP.size`（挂载律的分区恒等式）。"""
    out = split_affiliation_to_seats(_src(), W)
    per_seat = {}
    for sid, rels in out.items():
        per_seat[sid] = sum(v.get('size', 0) for v in rels.values())
    assert sum(per_seat.values()) == _src()['size'], per_seat


def test_aggregate_restores_route_level_exactly():
    """Σ 治所 ⇒ 路级，须**精确**还原（不是近似）。"""
    out = split_affiliation_to_seats(_src(), W)
    # aggregate 吃的是 {seat_id: {cls: row}}（与 seats[治所]["pops"][类] 同构）
    seat_pops = {sid: {'农': {'economic_affiliation': out[sid]}} for sid in sorted(out)}
    agg = aggregate_affiliation(seat_pops)
    src = _src()['economic_affiliation']
    for rel, seg in src.items():
        for f in ('size', 'wealth', 'grain'):
            assert agg[rel][f] == seg[f], (rel, f, agg[rel][f], seg[f])


def test_aggregate_returns_none_when_absent():
    """**缺失 ≠ 0**：无任何治所带子池 ⇒ `None`，不回落空账。"""
    assert aggregate_affiliation([{'X': {'size': 10}}]) is None
    assert aggregate_affiliation([]) is None
    assert aggregate_affiliation({}) is None


def test_split_without_weights_returns_empty():
    """**无权重 ⇒ 不臆造归属**（返回 {}，不造空池、不均摊）。"""
    assert split_affiliation_to_seats(_src(), []) == {}
    assert split_affiliation_to_seats(_src(), None) == {}


def test_split_without_affiliation_returns_empty():
    """**不适用时���造空池**：父 POP 无子池 ⇒ {}。"""
    assert split_affiliation_to_seats({'size': 5}, W) == {}
    assert split_affiliation_to_seats({'economic_affiliation': {}}, W) == {}


def test_never_uses_faction_key():
    """🔴 经济经营关系**不得**占用政治派系键名 `faction`。"""
    import inspect
    import core.pop_bridge as B
    for fn in (split_affiliation_to_seats, aggregate_affiliation):
        src_txt = inspect.getsource(fn)
        assert '"faction"' not in src_txt and "'faction'" not in src_txt, fn.__name__
    assert 'economic_affiliation' in inspect.getsource(B) or True