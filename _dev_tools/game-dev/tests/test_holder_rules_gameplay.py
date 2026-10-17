# -*- coding: utf-8 -*-
"""货主规则（玩法设定轨 Y）守卫：逐维有据可查、来源标记不被误读。

用户 2026-10-05 裁定（Y）：用**合理可调的游戏规则**定货主；
**保留「玩法设定」来源标记**，避免以后被误读成史实数据。
"""
import os
import sys

# 2026-10-17 全审：去掉机器绝对路径，按仓库相对位置推导（干净 clone 可跑）
_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from content.data_constants import RAW_DIMS
from core.game_state import GameState
from core.legacy_mechanic import init_legacies
from core.material_holding import (HOLDER_IMPERIAL, HOLDER_MAP, HOLDER_PROVENANCE,
                                   HOLDER_TREASURY, resolve_holder)
from core.production_chain import pending_total, settle_production_chain

ALLOWED_PROV = {'\u53f2\u5b9e\u00b7\u5b9a\u6027', '\u73a9\u6cd5\u8bbe\u5b9a'}


def test_every_raw_dim_has_declared_holder():
    for d in RAW_DIMS:
        assert d in HOLDER_MAP, ('\u672a\u58f0\u660e\u8d27\u4e3b\uff1a%s' % d)


def test_every_declared_holder_has_provenance():
    """🔴 每个货主规则**必须**带来源标记，防被误读成史实。"""
    for d in HOLDER_MAP:
        assert d in HOLDER_PROVENANCE, ('\u7f3a\u6765\u6e90\u6807\u8bb0\uff1a%s' % d)
        assert HOLDER_PROVENANCE[d] in ALLOWED_PROV, (d, HOLDER_PROVENANCE[d])


def test_provenance_marks_gameplay_rules_frankly():
    """🔴 玩法设定须**如实标注**（不得冒充史实）。"""
    gameplay = [d for d, p in HOLDER_PROVENANCE.items() if p == '\u73a9\u6cd5\u8bbe\u5b9a']
    assert gameplay, '\u5e94\u5b58\u5728\u73a9\u6cd5\u8bbe\u5b9a\u6761\u76ee'
    # 丝/麻/蔗/果 等农家产物为简化分配，须标玩法设定
    for d in ('\u4e1d', '\u9ebb', '\u8517', '\u679c'):
        assert HOLDER_PROVENANCE.get(d) == '\u73a9\u6cd5\u8bbe\u5b9a', d


def test_state_monopoly_dims_go_treasury():
    for d in ('\u76d0', '\u94c1'):
        assert resolve_holder(d) == HOLDER_TREASURY, d


def test_mountain_dims_go_imperial():
    """山泽之利归**皇家经营**（承 §6.25）。"""
    for d in ('\u6728', '\u77f3', '\u836f\u6750'):
        assert resolve_holder(d) == HOLDER_IMPERIAL, d
        assert HOLDER_PROVENANCE[d] == '\u53f2\u5b9e\u00b7\u5b9a\u6027', d


def test_truly_unknown_dim_still_missing():
    """表**之外**的维仍 Missing（不回落）—— 规则是**声明式**的，不是默认。"""
    for d in ('\u4e0d\u5b58\u5728\u7684\u7ef4', 'x', ''):
        assert resolve_holder(d) is None, d


def test_no_auto_confirm_api_exists():
    import core.production_chain as PC
    bad = [n for n in dir(PC) if not n.startswith('__')
           and ('confirm' in n.lower() or 'transfer_pending' in n.lower())]
    assert not bad, bad


def test_all_production_is_now_attributed():
    """Y 轨下：逐维有货主 ⇒ **不再有待定积压**（这是规则生效的证据）。"""
    s = GameState('\u53f2\u5b9e')
    init_legacies(s)
    settle_production_chain(s, [])
    assert pending_total(s) == 0, ('\u4ecd\u6709\u5f85\u5b9a\uff1a%d' % pending_total(s))


def test_no_default_economic_affiliation_created():
    s = GameState('\u53f2\u5b9e')
    init_legacies(s)
    settle_production_chain(s, [])
    leaked = []
    for rk, pf in s.prefectures.items():
        for cls, pop in (pf.get('pops') or {}).items():
            if isinstance(pop, dict) and pop.get('economic_affiliation'):
                leaked.append((rk, cls))
    assert not leaked, leaked[:5]