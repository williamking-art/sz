# -*- coding: utf-8 -*-
"""6.33 丙 · 面板可见性：待定料**单列**呈现，**不并入**任何可用量/合计。

用户裁定：只在能解释「归属待定」的位置单列数量；**不得**并入可用库存、
国库资产、可售量或合计库存，**不得**触发采购/投料/出售/计税。
"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

from core.game_state import GameState
from core.legacy_mechanic import init_legacies
from core.market_readout import demand_diagnosis, inventory_ledger
from core.material_market import material_stock
from core.production_chain import pending_total, settle_production_chain


def _state():
    s = GameState('史实')
    init_legacies(s)
    settle_production_chain(s, [])
    return s


# ============ inventory_ledger ============
def test_inventory_ledger_exposes_pending_key():
    r = inventory_ledger(_state())
    assert 'pending' in r
    assert 'pending_qty' in r['totals']


def test_pending_not_merged_into_warehouse_total():
    """🔴 待定量**不得**并入 `warehouse_stock`（可用库存）。"""
    r = inventory_ledger(_state())
    p = r['totals']['pending_qty']
    assert p > 0, '本例应有待定料'
    assert r['totals']['warehouse_stock'] < p, (
        r['totals']['warehouse_stock'], p)


def test_pending_not_merged_into_pop_goods():
    r = inventory_ledger(_state())
    assert r['totals']['pop_goods_qty'] == 0


def test_pending_rows_marked_unattributed():
    r = inventory_ledger(_state())
    assert r['pending'], '应有待定行'
    for row in r['pending']:
        assert row['holder_type'] == 'pending'
        assert row['holder_id'] is None, row
        assert row['purpose'] == 'unattributed', row
        assert row.get('route'), '应给出存放地'


# ============ demand_diagnosis ============
def test_demand_diagnosis_lists_pending_separately():
    s = _state()
    s.statistics['goods_spend'] = 100.0
    d = demand_diagnosis(s)
    assert 'pending_qty' in d['observed']
    assert d['observed']['pending_qty'] == pending_total(s)


def test_pending_does_not_set_warehouse_any_stock():
    """🔴 待定**不得**让 `warehouse_any_stock` 变 True（否则被当成有货可用）。"""
    s = GameState('史实')
    init_legacies(s)
    settle_production_chain(s, [])
    # 清空国库，只留待定
    for slot in (s.resources or {}).values():
        if isinstance(slot, dict):
            slot['stock'] = 0
    assert pending_total(s) > 0
    s.statistics['goods_spend'] = 100.0
    d = demand_diagnosis(s)
    assert d['observed']['warehouse_any_stock'] is False, (
        '待定料被误当成可用库存')
    assert d['observed']['pending_qty'] > 0


# ============ material_stock（采购/可售入口）============
def test_material_stock_invisible_for_pending_only_dim():
    """🔴 待定料**不得**经 `material_stock` 变为「可采购库存」。"""
    s = _state()
    for dim in ('麻', '木'):
        v = material_stock(s, dim)
        assert not v, (dim, v)
    assert pending_total(s) > 0