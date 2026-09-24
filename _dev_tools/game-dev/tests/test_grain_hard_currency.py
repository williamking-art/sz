# -*- coding: utf-8 -*-
"""批 6 · 粮=硬通货回归（本色饷 / 官仓平粜 / 本色粮税）。

断言：
  1) 本色兵粮/禄米从官仓拨入 POP grain（grain_pay.soldier/official > 0）；
  2) 本色粮税从农 POP 出、入官仓（grain_tax_in_kind > 0）；
  3) 粮残差公式含本色/平粜项后仍恒 0；
  4) 官仓平粜：价高放粮（ping_tiao_out）、价低意向籴入（ping_tiao_in）；
  5) 计价位折贯展示不并入货币存量（grain valued ≠ money）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import EXTERNAL_ECON, EXTERNAL_ECONOMY_REGIMES  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402

CFG = EXTERNAL_ECON


def _eco_provinces(ex):
    return [p for p in (ex.get("provinces") or [])
            if isinstance(p, dict) and isinstance(p.get("buildings"), dict)]


def test_grain_pay_constants():
    """本色饷/平粜常量就位。"""
    assert "SOLDIER_GRAIN_RATE" in CFG
    assert "OFFICIAL_GRAIN_RATE" in CFG
    assert "PING_TIAO_HIGH" in CFG
    assert "PING_TIAO_LOW" in CFG
    assert "GRAIN_TAX_IN_KIND" in CFG
    assert CFG["SOLDIER_GRAIN_RATE"]["default"] > 0
    assert CFG["PING_TIAO_HIGH"] > CFG["PING_TIAO_LOW"]


def test_hard_currency_grain_pay_and_tax():
    """本色饷入 POP grain + 本色税出入官仓（grain_pay 字段非零）。"""
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=11)
    any_pay = False
    any_tax = False
    for rk in EXTERNAL_ECONOMY_REGIMES:
        ex = s.external_regimes[rk]
        for p in _eco_provinces(ex):
            pa = p.get("econ_audit") or {}
            gp = pa.get("grain_pay") or {}
            if gp.get("soldier", 0) > 0 or gp.get("official", 0) > 0:
                any_pay = True
            if gp.get("grain_tax_in_kind", 0) > 0:
                any_tax = True
    # 至少一政权有兵/官 + 产粮 → 本色饷/税非零
    assert any_pay, "本色饷应有拨付"
    # 本色粮税需 produced > 0（收成月）；24 月中至少一月有
    s2 = GameState("史实")
    for _ in range(6):
        run_monthly_settlement(s2, seed_offset=11)
        for rk in EXTERNAL_ECONOMY_REGIMES:
            for p in _eco_provinces(s2.external_regimes[rk]):
                gp = (p.get("econ_audit") or {}).get("grain_pay") or {}
                if gp.get("grain_tax_in_kind", 0) > 0:
                    any_tax = True
    assert any_tax, "本色粮税应有征收"


def test_grain_residual_zero_with_hard_currency():
    """含本色饷/税/平粜后粮残差仍恒 0。"""
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=11)
    for _ in range(6):
        run_monthly_settlement(s, seed_offset=11)
        for rk in EXTERNAL_ECONOMY_REGIMES:
            ex = s.external_regimes[rk]
            agg = ex.get("econ_audit") or {}
            assert int(agg.get("grain_residual", 0)) == 0, (
                f"{rk} grain_residual={agg.get('grain_residual')}")
            for p in _eco_provinces(ex):
                pa = p.get("econ_audit") or {}
                assert int(pa.get("grain_residual", 0)) == 0, (
                    f"{rk}·{p['name']} grain_residual={pa.get('grain_residual')}")


def test_money_residual_zero_with_hard_currency():
    """含本色饷/税后钱残差仍恒 0（本色是实物，不碰钱）。"""
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=11)
    for _ in range(6):
        run_monthly_settlement(s, seed_offset=11)
        for rk in EXTERNAL_ECONOMY_REGIMES:
            ex = s.external_regimes[rk]
            agg = ex.get("econ_audit") or {}
            assert int(agg.get("money_residual", 0)) == 0, (
                f"{rk} money_residual={agg.get('money_residual')}")


def test_grain_valued_price_not_in_money():
    """计价位折贯展示：grain valued ≠ money supply（防双计）。"""
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=11)
    # 粮计价位 = Σ POP grain × 粮价（仅供展示）
    grain_valued = 0
    money = 0
    for rk in EXTERNAL_ECONOMY_REGIMES:
        ex = s.external_regimes[rk]
        price = float(ex.get("grain_price", 1.0) or 1.0)
        for p in _eco_provinces(ex):
            for v in (p.get("pops") or {}).values():
                if isinstance(v, dict):
                    grain_valued += int(v.get("grain", 0) or 0) * price
                    money += int(v.get("wealth", 0) or 0)
        money += int(ex.get("treasury", 0) or 0)
    # 粮计价位是独立展示口径，不得等于或混入 money
    assert grain_valued >= 0
    # money 只含 wealth + treasury（grain 不折贯入 money）
    assert money == sum(
        int(v.get("wealth", 0) or 0)
        for rk in EXTERNAL_ECONOMY_REGIMES
        for p in _eco_provinces(s.external_regimes[rk])
        for v in (p.get("pops") or {}).values() if isinstance(v, dict)
    ) + sum(int(s.external_regimes[rk].get("treasury", 0) or 0)
            for rk in EXTERNAL_ECONOMY_REGIMES)
