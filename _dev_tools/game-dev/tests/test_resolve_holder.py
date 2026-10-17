# -*- coding: utf-8 -*-
"""`resolve_holder`：只落到唯一账户；声明式规则（Y 轨）。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

from core import material_holding as MH
from core.material_holding import (HOLDER_IMPERIAL, HOLDER_MAP, HOLDER_TREASURY,
                                   resolve_holder)


def test_map_has_entries_and_provenance():
    assert HOLDER_MAP, '\u8d27\u4e3b\u8868\u4e0d\u5e94\u4e3a\u7a7a'
    assert '\u76d0' in HOLDER_MAP


def test_unknown_dim_returns_none():
    """表**之外**的维 ⇒ Missing（不回落、不默认）。"""
    for dim in ('\u4e0d\u5b58\u5728\u7684\u7ef4', 'zzz', ''):
        assert resolve_holder(dim) is None, dim


def test_treasury_mapping():
    assert resolve_holder('\u76d0') == HOLDER_TREASURY
    assert resolve_holder('\u94c1') == HOLDER_TREASURY


def test_imperial_mapping():
    assert resolve_holder('\u6728') == HOLDER_IMPERIAL
    assert resolve_holder('\u77f3') == HOLDER_IMPERIAL
    assert resolve_holder('\u836f\u6750') == HOLDER_IMPERIAL


def test_pop_mapping_requires_slice_evidence():
    """判为 POP 切片时，**须有切片证据**才给载体键。"""
    saved = dict(MH.HOLDER_MAP)
    MH.HOLDER_MAP['__t'] = 'household_self'
    try:
        assert resolve_holder('__t', producer_id='\u519c') is None
        r = resolve_holder('__t', producer_id='\u519c',
                           economic_affiliation={'household_self': {'size': 10}})
        assert r == 'pop:\u519c:household_self', r
        assert resolve_holder('__t', producer_id='\u519c',
                              economic_affiliation={'tenant_household': {'size': 3}}) is None
        assert resolve_holder('__t',
                              economic_affiliation={'household_self': {'size': 3}}) is None
    finally:
        MH.HOLDER_MAP.clear()
        MH.HOLDER_MAP.update(saved)


def test_contract_split_returns_none():
    """依契约分属多方 ⇒ 本函数无权归并，返回 Missing。"""
    assert resolve_holder('\u76d0', contract_id='C-1') is None


def test_unclassified_never_resolves_to_holder():
    saved = dict(MH.HOLDER_MAP)
    MH.HOLDER_MAP['__u'] = 'unclassified'
    try:
        assert resolve_holder('__u', producer_id='\u519c',
                              economic_affiliation={'unclassified': {'size': 5}}) is None
    finally:
        MH.HOLDER_MAP.clear()
        MH.HOLDER_MAP.update(saved)


def test_invalid_dim_returns_none():
    assert resolve_holder('') is None
    assert resolve_holder(None) is None