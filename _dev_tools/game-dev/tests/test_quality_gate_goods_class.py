# -*- coding: utf-8 -*-
"""质量放行门 · 商品类目词条（粮 = 米/麦/面）。

对应用户 2026-10-18 裁定：「不是应该新建词条来定义吗？米面麦不都是粮」。
设计：数据定义在 content/data_constants.GOODS_CLASSES，访问层单点 =
core/foundation/ledger/goods_class.py。本门钉住三条不变式：

1. 定义自洽：默认成员必须存在且已立维；成员不得跨类目；
2. 类目合计：Σ 成员，缺失成员跳过（缺失 ≠ 0），非数值成员（州府桶/布尔）跳过；
3. 粮 = 类目：grain_ledger.grain_of 必须等于粮类目合计（现状米+麦，等价但不硬编码）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

from content.data_constants import GOODS_CLASSES, GRAIN_CLASS, GOODS_DIMS  # noqa: E402
from core.foundation.ledger import goods_class as gc  # noqa: E402


def test_definitions_are_self_consistent():
    """定义自洽：成员唯一、默认成员已立维、成员不跨类目。"""
    assert gc.class_names(), '没有任何类目定义 ⇒ 门是空转'
    assert gc.assert_exclusive() == [], f'成员跨类目：{gc.assert_exclusive()}'
    for name in gc.class_names():
        ms = gc.members(name)
        if not ms:
            # 聚合节点（如 商品）必须有子类目；预备类目（如 进口奢侈，维尚未立）必须有 pending_members
            pend = (GOODS_CLASSES[name].get('pending_members') or [])
            assert gc.children(name) or pend, \
                f'类目 {name} 既无成员、无子类目、也无 pending_members（空壳）'
            continue
        assert len(ms) == len(set(ms)), f'类目 {name} 成员重复：{ms}'
        if not gc.is_writable(name):
            # 聚合专用类目（如 食品）：只读合计，不承载写入，允许无 default_member
            assert gc.class_add({}, name, 5) is None, f'聚合类目 {name} 不得接受写入'
            continue
        dm = gc.default_member(name)
        assert dm in ms, f'类目 {name} 的默认成员 {dm} 不在成员内'
        active = (GOODS_CLASSES[name].get('active') or {})
        assert active.get(dm, True), f'类目 {name} 的默认成员 {dm} 尚未立商品维（active=False）'


def test_grain_members_are_declared():
    """粮类目必须包含 米/麦，且它们确实在商品目录里（否则类目与目录脱节）。"""
    ms = gc.members(GRAIN_CLASS)
    for must in ('米', '麦'):
        assert must in ms, f'粮类目缺少成员 {must}：{ms}'
        assert must in GOODS_DIMS, f'{must} 不在 GOODS_DIMS 中（类目与目录脱节）'
    for p in (GOODS_CLASSES[GRAIN_CLASS].get('pending_members') or []):
        assert p not in GOODS_DIMS, f'{p} 仍标记为未立维，却已进 GOODS_DIMS'


def test_class_total_sums_members_and_skips_missing():
    """类目合计 = Σ成员；缺失 ≠ 0；桶/布尔跳过。"""
    assert gc.class_total({}, GRAIN_CLASS) is None, '无任何成员时应为 None（缺失≠0）'
    assert gc.class_total({'米': 7}, GRAIN_CLASS) == 7
    assert gc.class_total({'米': 7, '麦': 5}, GRAIN_CLASS) == 12
    # 非数值成员（州府桶/布尔）必须跳过，而不是抛错或算成 0
    assert gc.class_total({'米': 3, '麦': {'某路|某州': 9}, '面': True}, GRAIN_CLASS) == 3
    # 成品粮（面）一旦有值也算粮（词条语义），但不影响未出现时的合计
    assert gc.class_total({'米': 1, '面': 100}, GRAIN_CLASS) == 101


def test_grain_of_equals_class_total():
    """粮的派生读口必须就是类目合计（不另立一套成员集合）。"""
    from core.foundation.ledger.grain_ledger import grain_of

    samples = [None, {}, {'米': 4}, {'麦': 6}, {'米': 4, '麦': 6}, {'米': 1, '面': 2}]
    for goods in samples:
        pop = None if goods is None else {'goods': goods}
        expected = None if goods is None else gc.class_total(goods, GRAIN_CLASS)
        assert grain_of(pop) == expected, f'goods={goods}'


def test_exclusivity_check_detects_injected_overlap():
    """反例（注入即红）：同一维度被塞进两个类目必须被自检抓到。"""
    fake = {
        '粮': {'members': ['米', '麦'], 'active': {}, 'default_member': '米'},
        'X': {'members': ['米'], 'active': {}, 'default_member': '米'},
    }
    import core.foundation.ledger.goods_class as mod

    orig = mod._classes
    try:
        mod._classes = lambda: fake  # type: ignore[assignment]
        issues = mod.assert_exclusive()
        assert issues, '跨类目未被识别 ⇒ 判据是空的'
    finally:
        mod._classes = orig  # type: ignore[assignment]