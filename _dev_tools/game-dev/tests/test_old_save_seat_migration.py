# -*- coding: utf-8 -*-
"""方案乙旧档迁移：载入无 `seats` 的旧档后，POP 真账应下沉到州府级且逐字段守恒。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

from core.game_state import GameState
from core.pop_bridge import (POP_CLASSES, aggregate_seat_pops,
                                assert_pops_consistent, SPLIT_FIELDS,
                                survey_pops)
from core.save_load import _migrate_pops_to_seats

NONG = POP_CLASSES[0]   # POP 挂载律第一类（农）——用常量避免中文字面量


def _fresh_state():
    s = GameState('史实')
    for _rt, _pd in s.prefectures.items():
        _pd.pop('seats', None)
    return s


def test_old_save_gains_seats():
    s = _fresh_state()
    assert not any(pd.get('seats') for pd in s.prefectures.values()), 'precondition'
    migrated = _migrate_pops_to_seats(s)
    assert migrated == len(s.prefectures)
    for rt, pd in s.prefectures.items():
        assert pd.get('seats'), rt


def test_migration_conserves_every_field():
    s = _fresh_state()
    before = {rt: {c: dict(pd['pops'][c]) for c in pd['pops']
                   if isinstance(pd['pops'][c], dict)}
              for rt, pd in s.prefectures.items()}
    _migrate_pops_to_seats(s)
    for rt, pd in s.prefectures.items():
        for cls, src in before[rt].items():
            agg = aggregate_seat_pops(pd, cls)
            assert agg is not None, (rt, cls)
            for f in SPLIT_FIELDS:
                a = src.get(f)
                b = agg.get(f)
                if isinstance(a, (int, float)) and not isinstance(a, bool):
                    assert int(b) == int(a), (rt, cls, f, b, a)


def test_migration_is_idempotent():
    s = _fresh_state()
    _migrate_pops_to_seats(s)
    snap = {rt: {sid: dict(sp.get('pops', {}).get(NONG, {}))
                 for sid, sp in (pd.get('seats') or {}).items()}
            for rt, pd in s.prefectures.items()}
    again = _migrate_pops_to_seats(s)
    assert again == 0
    for rt, pd in s.prefectures.items():
        for sid, sp in (pd.get('seats') or {}).items():
            assert sp.get('pops', {}).get(NONG, {}) == snap[rt][sid], (rt, sid)


def test_migration_leaves_consistency_clean():
    s = _fresh_state()
    _migrate_pops_to_seats(s)
    bad = []
    for rt, pd in s.prefectures.items():
        bad += [x for x in assert_pops_consistent(pd)]
    assert not bad, bad[:3]
    assert survey_pops(s)['字段失配'] == []


def test_route_mirror_matches_truth_after_migration():
    s = _fresh_state()
    _migrate_pops_to_seats(s)
    for rt, pd in s.prefectures.items():
        assert not assert_pops_consistent(pd), rt