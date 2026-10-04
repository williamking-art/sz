# -*- coding: utf-8 -*-
"""路级 `pops` 只读守卫：证明「写入已全部桥接化」，并锁定剩余直写字段的基线。"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

import pytest

from core.game_state import GameState
from core.pop_bridge import (POP_CLASSES, install_all_guards, pops_guard_violations,
                                reset_pops_guard, split_pops_to_seats,
                                sync_route_pops)

SETTLE = None


def _sunk_with_guard():
    s = GameState('史实')
    for rt, pd in s.prefectures.items():
        split_pops_to_seats(pd, rt)
        sync_route_pops(pd)
    install_all_guards(s)
    reset_pops_guard()
    return s


def _run(s, rounds):
    from core.settlement_steps import (_settle_land_local, _settle_finance,
                                       _settle_granary, _settle_officialdom,
                                       _settle_clerks, _settle_emperor_personal)
    log = []
    for _ in range(rounds):
        for fn in (_settle_land_local, _settle_finance, _settle_granary,
                   _settle_officialdom, _settle_clerks, _settle_emperor_personal):
            fn(s, log)


def test_guard_catches_direct_write():
    """守卫**必须真能抓到**直写（否则下面的零违规是假象）。"""
    s = _sunk_with_guard()
    rt = list(s.prefectures)[0]
    s.prefectures[rt]['pops']['\u519c']['size'] = 12345
    v = pops_guard_violations()
    assert v, '守卫没抓到直接写入 —— 守卫本身失效'
    assert any('size' in x for x in v), v[:2]


def test_guard_ignores_bridge_refresh():
    """桥接自身的镜像刷新**不算**违规。"""
    s = _sunk_with_guard()
    from core.pop_bridge import pop_add
    rt = list(s.prefectures)[0]
    cls = POP_CLASSES[0]
    assert pop_add(s.prefectures[rt], cls, 'size', 7) is not None
    assert not pops_guard_violations(), pops_guard_violations()[:3]


#: 已知仍在直写的字段（尚未下沉）。空 => 全部字段已走桥接。
#: grain      → G-3 待办：粮尚未回填 goods[\u7c73]，pops[].grain 仍是真载体
#: 其余        → 官制身份子池 / 宗族（计划 §6.11 未裁定项）
KNOWN_LEGACY_WRITES = {'grain', 'officials', 'clerks', 'on_post',
                       'waiting', 'sinecure', 'clan'}


def test_no_unexpected_direct_writes():
    """🔴 长局中**不得出现基线之外**的直写字段。

    这是「写入已全部桥接化」的**可执行**守卫：新增一行绕过桥接的直写会在这里炸掉。
    """
    s = _sunk_with_guard()
    _run(s, 3)
    v = pops_guard_violations()
    hit = set()
    for item in v:
        if "['" in item:
            hit.add(item.split("['", 1)[1].split("']", 1)[0])
    unexpected = hit - KNOWN_LEGACY_WRITES
    assert not unexpected, '出现基线外的直写字段：%s' % sorted(unexpected)


def test_identity_subpools_and_clan_are_the_remaining_ones():
    """记录当前真实剩余面（粮 + 身份子池 + 宗族），防止"\u9759\u9ed8\u5931\u8d25"\u3002"""
    s = _sunk_with_guard()
    _run(s, 3)
    v = pops_guard_violations()
    hit = set()
    for item in v:
        if "['" in item:
            hit.add(item.split("['", 1)[1].split("']", 1)[0])
    assert hit, '预期仍有未下沉字段的直写；若为空说明基线该更新了'
    assert hit <= KNOWN_LEGACY_WRITES, sorted(hit)