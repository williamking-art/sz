# -*- coding: utf-8 -*-
"""6.33 · 归属待定库存：待定料**不得泄漏**进国库资产路径，且实物守恒。"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

from core.game_state import GameState
from core.production_chain import pending_total, settle_production_chain


def _produced(state):
    return settle_production_chain(state, [])


def test_pending_slot_exists_and_is_empty_at_init():
    s = GameState('shishi')
    assert s.pending_stock == {}


def test_missing_holder_goes_to_pending_not_warehouse():
    """未裁定维 ⇒ 进**待定槽**，国库不得拿到它。"""
    s = GameState('shishi')
    _produced(s)
    assert pending_total(s) > 0, '应有物料落待定槽'
    res = {d: int((r or {}).get('stock', 0) or 0) for d, r in (s.resources or {}).items()}
    # 丝/麻/果/木/石/茶/蔗 未裁定 => 不得出现在国库
    for d in ('丝', '麻', '果', '木', '石', '茶', '蔗'):
        assert res.get(d, 0) == 0, (d, res.get(d))


def test_state_operator_dims_still_go_to_warehouse():
    """已裁定为国库的盐铁 ⇒ **仍入国家仓**（口径不变）。"""
    s = GameState('shishi')
    _produced(s)
    res = {d: int((r or {}).get('stock', 0) or 0) for d, r in (s.resources or {}).items()}
    assert res.get('盐', 0) > 0 and res.get('铁', 0) > 0


def test_physical_conservation_holds():
    """🔴 实物守恒：总产出 == 国库 + 待定（**不增不减**）。"""
    s = GameState('shishi')
    produced = _produced(s)
    res = sum(int((r or {}).get('stock', 0) or 0) for r in (s.resources or {}).values())
    assert sum(produced.values()) == res + pending_total(s)


def test_pending_not_moved_to_merchants():
    """🔴 待定料**不得**被供给搬运当国库资产发给商人。"""
    from core.material_holding import supply_goods_to_seats
    s = GameState('shishi')
    _produced(s)
    p0 = pending_total(s)
    supply_goods_to_seats(s)
    assert pending_total(s) == p0


def test_pending_not_consumed_by_workshops():
    """🔴 待定料**不得**供工坊采购/投料。"""
    from core.settlement_steps import _settle_workshops
    s = GameState('shishi')
    _produced(s)
    p0 = pending_total(s)
    _settle_workshops(s, [])
    assert pending_total(s) == p0


def test_pending_entries_carry_owner_none_and_status():
    """待定条目必须标 `owner=None` + `owner_status='归属待定'`。"""
    s = GameState('shishi')
    _produced(s)
    seen = 0
    for slot in (s.pending_stock or {}).values():
        for ent in slot.values():
            seen += 1
            assert ent['owner'] is None, ent
            assert ent['owner_status'] == '归属待定', ent
            assert 'evidence_ref' in ent, ent
    assert seen > 0


def test_pending_total_excludes_confirmed():
    """已确权条目**不计入**待定量（转记后应减少）。"""
    s = GameState('shishi')
    _produced(s)
    before = pending_total(s)
    ent = None
    for slot in (s.pending_stock or {}).values():
        for e in slot.values():
            ent = e
            break
        if ent:
            break
    ent['owner'] = 'pop:农:household_self'
    ent['owner_status'] = '已确权'
    assert pending_total(s) == before - ent['qty']