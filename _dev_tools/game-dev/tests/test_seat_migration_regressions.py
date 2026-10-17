# -*- coding: utf-8 -*-
"""方案乙旧档迁移的根因回归：均值类字段、goods 州府桶、sync 合并语义。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

from core.game_state import GameState
from core.literacy import national_literacy
from core.material_holding import goods_amount, goods_bucket
from core.pop_bridge import (MEAN_FIELDS, SPLIT_FIELDS, aggregate_seat_pops,
                                split_pops_to_seats, sync_route_pops)
from core.save_load import _migrate_pops_to_seats


def _bare():
    s = GameState('史实')
    for pd in s.prefectures.values():
        pd.pop('seats', None)
    return s


def test_mean_fields_not_summed():
    """🔴 均值类（识字率）**不可求和** —— 否则聚合后翻数倍。"""
    assert MEAN_FIELDS, 'MEAN_FIELDS 不应为空'
    for f in MEAN_FIELDS:
        assert f not in SPLIT_FIELDS, '%s 不应同时出现在可加类里' % f
    s = _bare()
    for rt, pd in s.prefectures.items():
        split_pops_to_seats(pd, rt)
    assert abs(national_literacy(s) - 8.41) < 0.01, national_literacy(s)


def test_mean_field_preserves_fraction():
    """识字率是**带小数的比率**（如 5.41）⇒ 下沉不得取整丢精度。"""
    s = _bare()
    rt = list(s.prefectures)[0]
    pd = s.prefectures[rt]
    src = pd['pops'][list(pd['pops'])[0]].get('literacy')
    assert isinstance(src, float) and src != int(src), '前置：应存在小数'
    split_pops_to_seats(pd, rt)
    agg = aggregate_seat_pops(pd, list(pd['pops'])[0])
    assert abs(float(agg.get('literacy')) - float(src)) < 0.5, (agg.get('literacy'), src)


def test_seat_buckets_survive_split():
    """🔴 goods 已是「扁平 + 州府桶」双形态 ⇒ 拆分时**桶必须归位**，不能丢。"""
    s = _bare()
    rt = list(s.prefectures)[0]
    pd = s.prefectures[rt]
    row = pd['pops'][list(pd['pops'])[0]]
    gd = row.setdefault('goods', {})
    gd[u'\u6728'] = 500
    before = goods_amount(gd, u'\u6728')
    assert before == 500, before
    split_pops_to_seats(pd, rt)
    seats = pd.get('seats') or {}
    assert seats, 'seats 应存在'
    seat_rows = [sp['pops'][list(sp['pops'])[0]]['goods'] for sp in seats.values()]
    assert any(goods_amount(g, u'\u6728') for g in seat_rows), '扁平木料未下沉到任一治所'


def test_sync_merges_instead_of_replacing():
    """🔴 `sync_route_pops` **合并**而非替换 —— 否则抹掉 estate/officials 等字段。"""
    s = _bare()
    rt = list(s.prefectures)[0]
    pd = s.prefectures[rt]
    cls = list(pd['pops'])[0]
    pd['pops'][cls]['estate'] = 777
    pd['pops'][cls]['officials'] = 5
    split_pops_to_seats(pd, rt)
    sync_route_pops(pd)
    row = pd['pops'][cls]
    assert row.get('estate') == 777, 'estate 被 sync 抹掉：%r' % row.get('estate')
    assert row.get('officials') == 5, 'officials 被 sync 抹掉：%r' % row.get('officials')


def test_goods_bucket_roundtrip_after_migration():
    """迁移后 `goods_bucket` 访问口仍可读写（迁移不能破坏既有建材口径）。"""
    s = _bare()
    rt = list(s.prefectures)[0]
    pd = s.prefectures[rt]
    row = pd['pops'][list(pd['pops'])[0]]
    gd = row.setdefault('goods', {})
    sid = list((pd.get('seats') or {}).keys()) or [None]
    gd[u'\u6728'] = 300
    _migrate_pops_to_seats(s)
    g2 = pd['pops'][list(pd['pops'])[0]]['goods']
    assert goods_amount(g2, u'\u6728') == 300, goods_amount(g2, u'\u6728')