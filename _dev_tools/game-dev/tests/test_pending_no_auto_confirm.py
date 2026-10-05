# -*- coding: utf-8 -*-
"""甲（史实局）守卫：**不编造归属** —— 无默认分配、无自动确权。

用户 2026-10-05 裁定：
- **甲为史实局依据**；目前**无可用数据源** ⇒ **暂不做第二阶段确权转记**；
- 相关人口与产出**继续标记** unclassified / 归属待定，**不编造分配比例**；
- 乙（玩法情景）**另做**，须先提具体规则、标注假设、与史实局数据**分开**。
"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

from core.game_state import GameState
from core.legacy_mechanic import init_legacies
from core.material_holding import HOLDER_MAP, resolve_holder
from core.production_chain import pending_total, settle_production_chain
from core.settlement import run_monthly_settlement


def _state(months=0):
    s = GameState('shishi')
    init_legacies(s)
    s.treasury = 50_000_000
    settle_production_chain(s, [])
    for _ in range(months):
        s.treasury = max(s.treasury, 50_000_000)
        run_monthly_settlement(s)
    return s


def test_pending_never_auto_confirmed_after_settlement():
    s = _state(months=3)
    seen = 0
    for slot in (s.pending_stock or {}).values():
        for ent in slot.values():
            seen += 1
            assert ent['owner'] is None, ('auto-confirmed', ent)
            assert ent['owner_status'] == '\u5f52\u5c5e\u5f85\u5b9a', ent
            assert ent.get('evidence_ref') is None, ('fabricated evidence', ent)
    assert seen > 0


def test_no_auto_confirm_api_exists():
    import core.production_chain as PC
    names = [n for n in dir(PC) if not n.startswith('__')]
    bad = [n for n in names if 'confirm' in n.lower() or 'transfer_pending' in n.lower()]
    assert not bad, ('no phase-2 entry should exist: %s' % bad)


def test_holder_map_has_no_default_or_wildcard():
    for k in HOLDER_MAP:
        assert k not in ('*', 'default', 'any'), ('wildcard', k)


def test_undecided_dims_stay_missing():
    for dim in ('\u6728', '\u77f3', '\u836f\u6750', '\u679c', '\u8336'):
        assert dim not in HOLDER_MAP, ('decided without evidence: %s' % dim)
        assert resolve_holder(dim) is None, dim


def test_no_default_economic_affiliation_created():
    s = _state(months=2)
    leaked = []
    for rk, pf in s.prefectures.items():
        for cls, pop in (pf.get('pops') or {}).items():
            if not isinstance(pop, dict):
                continue
            if pop.get('economic_affiliation'):
                leaked.append((rk, cls))
    assert not leaked, ('fabricated affiliation slices: %s' % leaked[:5])


def test_pending_nonzero_proving_blocker_is_data():
    s = _state()
    assert pending_total(s) > 0