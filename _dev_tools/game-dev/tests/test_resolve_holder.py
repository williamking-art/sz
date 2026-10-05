# -*- coding: utf-8 -*-
"""T2 · `resolve_holder`：只落到唯一账户，且**未裁定即 Missing**。

来自 `reviews/POP改良方案_2026-10-05.md` 与 `未完成设计对齐与改良方案_2026-10-05.md`：
持有者解析必须**只解析到一个账户**，且归属未裁定时返回 `Missing` ——
**不得**均摊、不得默认民营、不得从政治派系反推（POP改良方案 §2.1 第 5 条）。
"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

from core import material_holding as MH
from core.material_holding import (HOLDER_IMPERIAL, HOLDER_MAP, HOLDER_TREASURY,
                                   resolve_holder)


def test_map_is_intentionally_unset():
    """`HOLDER_MAP` 只登记**已裁定**的维；未裁定的维一律缺席（调用时得 Missing）。"""
    assert isinstance(HOLDER_MAP, dict)
    assert set(HOLDER_MAP) == {'盐', '铁', '丝', '麻', '蔗'}, sorted(HOLDER_MAP)


def test_unmapped_dim_returns_none():
    """未裁定的维 ⇒ Missing（`None`），**不回落**为任何一方。"""
    # 山泽类（木/石/药材）与果/茶/金/银/铜/马/牲畜 均**刻意未裁定**
    for dim in ('木', '石', '药材', '果', '茶', '金', '银', '铜', '马',
                '牲畜', '随便一个不存在的维'):
        assert dim not in HOLDER_MAP, ('不应已裁定：%s' % dim)
        assert resolve_holder(dim) is None, dim


def test_trade_dims_need_evidence_not_bare_dim():
    """已裁定为户内自营的维，**无切片证据时仍是 Missing**。"""
    for dim in ('丝', '麻', '蔗'):
        assert HOLDER_MAP.get(dim) == 'household_self', dim
        assert resolve_holder(dim) is None, dim
        r = resolve_holder(dim, producer_id='农',
                           economic_affiliation={'household_self': {'size': 9}})
        assert r == 'pop:农:household_self', (dim, r)


def test_treasury_mapping():
    MH.HOLDER_MAP['盐'] = 'state_operator'
    try:
        assert resolve_holder('盐') == HOLDER_TREASURY
    finally:
        MH.HOLDER_MAP.pop('盐', None)


def test_imperial_mapping():
    MH.HOLDER_MAP['药材'] = 'imperial_operator'
    try:
        assert resolve_holder('药材') == HOLDER_IMPERIAL
    finally:
        MH.HOLDER_MAP.pop('药材', None)


def test_pop_mapping_requires_evidence():
    MH.HOLDER_MAP['麻'] = 'household_self'
    try:
        # 无切片证据 ⇒ Missing（不得凭空归农）
        assert resolve_holder('麻', producer_id='农') is None
        # 证据齐备才给 POP 载体键
        r = resolve_holder('麻', producer_id='农',
                           economic_affiliation={'household_self': {'size': 10}})
        assert r == 'pop:农:household_self', r
        # 关系键不匹配 ⇒ Missing
        assert resolve_holder('麻', producer_id='农',
                              economic_affiliation={'tenant_household': {'size': 3}}) is None
        # 无阶层 ⇒ Missing
        assert resolve_holder('麻',
                              economic_affiliation={'household_self': {'size': 3}}) is None
    finally:
        MH.HOLDER_MAP.pop('麻', None)


def test_contract_split_returns_none():
    """依契约分属多方 ⇒ 本函数**无权归并**，返回 Missing 交调用方拆分。"""
    MH.HOLDER_MAP['木'] = 'estate_operator'
    try:
        assert resolve_holder('木', contract_id='C-123') is None
    finally:
        MH.HOLDER_MAP.pop('木', None)


def test_unclassified_never_resolves_to_holder():
    """`unclassified` ⇒ 一律 Missing（POP改良方案：不允许自动售卖）。"""
    MH.HOLDER_MAP['果'] = 'unclassified'
    try:
        assert resolve_holder('果', producer_id='农',
                              economic_affiliation={'unclassified': {'size': 5}}) is None
    finally:
        MH.HOLDER_MAP.pop('果', None)


def test_invalid_dim_returns_none():
    """缺失/非法维 ⇒ None（缺失≠0），不抛异常。"""
    assert resolve_holder('') is None
    assert resolve_holder(None) is None