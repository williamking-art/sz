# -*- coding: utf-8 -*-
"""G-3 片5：粮回填到州府级 —— 守恒、幂等、路级转为派生。"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

from core.game_state import GameState
from core.grain_bridge import (backfill_grain_to_seats, grain_add, grain_get,
                                 grain_set, grain_target)
from core.pop_bridge import (POP_CLASSES, SPLIT_FIELDS, aggregate_seat_pops,
                                assert_pops_consistent, split_pops_to_seats,
                                sync_route_pops)
from core.save_load import _migrate_pops_to_seats


def _sunk(backfilled=True):
    s = GameState('史实')
    for pd in s.prefectures.values():
        pd.pop('seats', None)
    _migrate_pops_to_seats(s)
    return s


def _seat_sum(pdata, cls):
    return sum(int(((sp.get('pops') or {}).get(cls) or {}).get('grain') or 0)
               for sp in (pdata.get('seats') or {}).values())


def test_grain_is_split_field():
    assert 'grain' in SPLIT_FIELDS, '粮必须可加下沉'


def test_backfill_conserves_grain_exactly():
    s = GameState('史实')
    orig = {rt: {c: int((row or {}).get('grain') or 0)
                 for c, row in (pd.get('pops') or {}).items()
                 if isinstance(row, dict)}
            for rt, pd in s.prefectures.items()}
    for pd in s.prefectures.values():
        pd.pop('seats', None)
    _migrate_pops_to_seats(s)
    for rt, pd in s.prefectures.items():
        for cls, exp in orig[rt].items():
            route = int((pd['pops'][cls] or {}).get('grain') or 0)
            assert route == exp, (rt, cls, route, exp)
            assert _seat_sum(pd, cls) == exp, (rt, cls, _seat_sum(pd, cls), exp)


def test_backfill_is_idempotent():
    s = _sunk()
    rt = list(s.prefectures)[0]
    pd = s.prefectures[rt]
    cls = POP_CLASSES[0]
    snap = _seat_sum(pd, cls)
    again = backfill_grain_to_seats(pd, rt)
    assert again == 0, '已回填的路不该再回填（会重复加）'
    assert _seat_sum(pd, cls) == snap, (snap, _seat_sum(pd, cls))


def test_route_grain_stays_consistent_with_seats():
    s = _sunk()
    bad = []
    for rt, pd in s.prefectures.items():
        bad += ['%s|%s' % (rt, x) for x in assert_pops_consistent(pd)]
    assert not bad, bad[:3]


def test_grain_write_with_state_lands_in_seats():
    """给了 state 的写入必须**下沉**，路级只是派生镜像。"""
    s = _sunk()
    rt = list(s.prefectures)[0]
    pd = s.prefectures[rt]
    cls = POP_CLASSES[0]
    before_seat = _seat_sum(pd, cls)
    before_route = int((pd['pops'][cls] or {}).get('grain') or 0)
    n = grain_add(pd['pops'][cls], 500, s)
    assert n == before_route + 500, (n, before_route)
    assert _seat_sum(pd, cls) == before_seat + 500, '写入未下沉到州府'
    assert int(pd['pops'][cls].get('grain') or 0) == n, '路级镜像未刷新'


def test_grain_write_without_state_keeps_legacy_behaviour():
    """不传 state（未登记的调用点）⇒ 行为与迁移前完全等价。"""
    s = _sunk()
    rt = list(s.prefectures)[0]
    pd = s.prefectures[rt]
    cls = POP_CLASSES[0]
    before_seat = _seat_sum(pd, cls)
    n = grain_add(pd['pops'][cls], 100)
    assert int(pd['pops'][cls].get('grain') or 0) == n
    assert _seat_sum(pd, cls) == before_seat, '未传 state 时不该动州府'