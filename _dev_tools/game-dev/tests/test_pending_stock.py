# -*- coding: utf-8 -*-
"""6.33 待定库存：拆分/隔离/守恒（**用清表制造 Missing**，不依赖具体维未裁定）。

⚠️ Y 轨（2026-10-05）后逐维已有货主 ⇒ 正常局面**不再有待定**。
本文件通过**临时清空 `HOLDER_MAP`** 复现 Missing 路径，以持续守护该机制。
"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

import pytest

from core import material_holding as MH
from core.game_state import GameState
from core.legacy_mechanic import init_legacies
from core.production_chain import pending_total, settle_production_chain


@pytest.fixture
def blank_holders():
    """临时清空货主表 ⇒ 所有维走 Missing ⇒ 进待定槽。"""
    saved = dict(MH.HOLDER_MAP)
    MH.HOLDER_MAP.clear()
    yield
    MH.HOLDER_MAP.clear()
    MH.HOLDER_MAP.update(saved)


def _state():
    s = GameState('\u53f2\u5b9e')
    init_legacies(s)
    return s


def test_pending_slot_exists_and_is_empty_at_init():
    assert _state().pending_stock == {}


def test_missing_holder_goes_to_pending_not_warehouse(blank_holders):
    s = _state()
    settle_production_chain(s, [])
    assert pending_total(s) > 0, '\u5e94\u6709\u7269\u6599\u843d\u5f85\u5b9a\u69fd'
    res = sum(int((r or {}).get('stock', 0) or 0) for r in (s.resources or {}).values())
    assert res == 0, 'Missing \u4e0d\u5f97\u5165\u56fd\u5e93\uff08\u5b9e\u5f97 %d\uff09' % res


def test_pending_entries_carry_owner_none_and_status(blank_holders):
    s = _state()
    settle_production_chain(s, [])
    seen = 0
    for slot in (s.pending_stock or {}).values():
        for ent in slot.values():
            seen += 1
            assert ent['owner'] is None, ent
            assert ent['owner_status'] == '\u5f52\u5c5e\u5f85\u5b9a', ent
            assert 'evidence_ref' in ent, ent
    assert seen > 0


def test_pending_total_excludes_confirmed(blank_holders):
    s = _state()
    settle_production_chain(s, [])
    before = pending_total(s)
    assert before > 0
    ent = None
    for slot in (s.pending_stock or {}).values():
        for e in slot.values():
            ent = e
            break
        if ent:
            break
    ent['owner'] = 'pop:\u519c:household_self'
    ent['owner_status'] = '\u5df2\u786e\u6743'
    assert pending_total(s) == before - ent['qty']


def test_conservation_holds_with_pending(blank_holders):
    """🔴 实物守恒：总产出 == 国库 + 待定。"""
    s = _state()
    produced = settle_production_chain(s, [])
    res = sum(int((r or {}).get('stock', 0) or 0) for r in (s.resources or {}).values())
    assert sum(produced.values()) == res + pending_total(s), (
        sum(produced.values()), res, pending_total(s))


def test_pending_not_consumed_by_workshops(blank_holders):
    from core.settlement_steps import _settle_workshops
    s = _state()
    settle_production_chain(s, [])
    p0 = pending_total(s)
    _settle_workshops(s, [])
    assert pending_total(s) == p0


def test_normal_rules_produce_no_pending():
    """Y 轨：逐维有货主 ⇒ 正常局面待定为 0。"""
    s = _state()
    settle_production_chain(s, [])
    assert pending_total(s) == 0