# -*- coding: utf-8 -*-
"""6.33 面板可见性：待定料**单列**呈现，**不并入**任何可用量/合计。

Y 轨（2026-10-05）后逐维有货主 ⇒ 正常局面无待定；
本文件用**清空货主表**复现 Missing，以持续守护面板隔离。
"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

import pytest

from core import material_holding as MH
from core.game_state import GameState
from core.legacy_mechanic import init_legacies
from core.market_readout import demand_diagnosis, inventory_ledger
from core.material_market import material_stock
from core.production_chain import pending_total, settle_production_chain


@pytest.fixture
def blank_holders():
    saved = dict(MH.HOLDER_MAP)
    MH.HOLDER_MAP.clear()
    yield
    MH.HOLDER_MAP.clear()
    MH.HOLDER_MAP.update(saved)


def _state():
    s = GameState('\u53f2\u5b9e')
    init_legacies(s)
    return s


def test_inventory_ledger_exposes_pending_key(blank_holders):
    s = _state()
    settle_production_chain(s, [])
    r = inventory_ledger(s)
    assert 'pending' in r
    assert 'pending_qty' in r['totals']


def test_pending_not_merged_into_warehouse_total(blank_holders):
    s = _state()
    settle_production_chain(s, [])
    r = inventory_ledger(s)
    assert r['totals']['pending_qty'] > 0
    assert r['totals']['warehouse_stock'] == 0


def test_pending_rows_marked_unattributed(blank_holders):
    s = _state()
    settle_production_chain(s, [])
    r = inventory_ledger(s)
    assert r['pending']
    for row in r['pending']:
        assert row['holder_type'] == 'pending'
        assert row['holder_id'] is None, row
        assert row['purpose'] == 'unattributed', row
        assert row.get('route'), '\u5e94\u7ed9\u51fa\u5b58\u653e\u5730'


def test_demand_diagnosis_lists_pending_separately(blank_holders):
    s = _state()
    settle_production_chain(s, [])
    s.statistics['goods_spend'] = 100.0
    d = demand_diagnosis(s)
    assert d['observed']['pending_qty'] == pending_total(s) > 0


def test_pending_does_not_set_warehouse_any_stock(blank_holders):
    s = _state()
    settle_production_chain(s, [])
    s.statistics['goods_spend'] = 100.0
    d = demand_diagnosis(s)
    assert d['observed']['warehouse_any_stock'] is False, '\u5f85\u5b9a\u88ab\u8bef\u5f53\u53ef\u7528\u5e93\u5b58'
    assert d['observed']['pending_qty'] > 0


def test_material_stock_invisible_for_pending_only_dim(blank_holders):
    s = _state()
    settle_production_chain(s, [])
    for dim in ('\u9ebb', '\u6728'):
        assert not material_stock(s, dim), dim
    assert pending_total(s) > 0