# -*- coding: utf-8 -*-
"""官方屯田垦荒年度接线（2026-10-18 全审 P1-13）。

默认 `gov_reclamation_share=0` ⇒ 完全不动；设为 >0 后每年二月按国库比例
向荒地最多的路拨款：荒地↓、官田↑、国库→本路农/工匠 POP（ΔM_ALL=0）。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from application.game_init import new_game  # noqa: E402
from core import money  # noqa: E402
from core.domains.administration import institution as inst  # noqa: E402
from core.domains.administration.settlement_officialdom import (  # noqa: E402
    _settle_officialdom,
)
from core.domains.economy.land_reclamation import (  # noqa: E402
    get_circuit_wasteland, init_circuit_wasteland,
)


def _waste_all(s):
    return {c: get_circuit_wasteland(s, c) for c in s.prefectures}


def test_reclamation_is_off_by_default():
    s = new_game("史实")
    init_circuit_wasteland(s)
    s.month = 2
    before = _waste_all(s)
    t0 = int(s.treasury)
    _settle_officialdom(s, [])
    assert _waste_all(s) == before, "默认 share=0 不得自动垦荒"
    assert int(s.treasury) == t0


def test_reclamation_runs_in_february_when_share_enabled():
    s = new_game("史实")
    init_circuit_wasteland(s)
    s.month = 2
    # share=2%（户部度支调度事权）
    ok, msg = inst.set_param(s, "gov_reclamation_share", 0.02)
    assert ok, msg
    before_waste = sum(_waste_all(s).values())
    before_land = sum(float(p.get("guan_tian", 0) or 0) for p in s.prefectures.values())
    m0 = money.m_all(s)
    t0 = int(s.treasury)
    log = []
    _settle_officialdom(s, log)
    after_waste = sum(_waste_all(s).values())
    after_land = sum(float(p.get("guan_tian", 0) or 0) for p in s.prefectures.values())
    assert after_waste < before_waste, "应开垦荒地"
    assert after_land > before_land, "官田应增加"
    assert int(s.treasury) < t0, "国库应实际支出"
    assert int(s.treasury) >= t0 * 0.95, "支出不得超过 5% 上限（实付按比例）"
    assert money.m_all(s) == m0, "国库→农/工匠必须守恒（ΔM_ALL=0）"
    assert any("官方屯田" in x for x in log), log


def test_reclamation_does_not_run_off_month():
    s = new_game("史实")
    init_circuit_wasteland(s)
    s.month = 3
    inst.set_param(s, "gov_reclamation_share", 0.02)
    before = _waste_all(s)
    _settle_officialdom(s, [])
    assert _waste_all(s) == before, "非二月不得自动垦荒"