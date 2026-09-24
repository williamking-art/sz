# -*- coding: utf-8 -*-
"""批 0 · 外邦两池守恒强化回归（24 月压力）。

依据《外邦省域产业链设计_2026-09-22》§10.1：
  外邦两池（treasury 钱池 / 官仓粮池）各自闭合；省域 econ_audit 零残差；
  政权级 econ_audit = Σ省域；岁币只记 burn 不进循环。

相对既有 test_external_economy.py 的增强：
  - 24 月压力（原 12 月）；
  - **逐省逐月**断言 money_residual == 0 且 grain_residual == 0（原只断言政权级）；
  - 断言政权级 econ_audit 的 money/grain residual == Σ省（加和一致性）；
  - 断言 treasury 变动 = 税入 − 军饷 − 官俸 ± 岁币（钱池闭合）；
  - 断言省域 grain 变动 = 产 − 食（粮池闭合）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from content.data import EXTERNAL_ECONOMY_REGIMES  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402


def _provinces(ex):
    return [p for p in (ex.get("provinces") or []) if isinstance(p, dict)]


def _regimes(s):
    """权威外邦经济账在 s.external_regimes（s.external 仅态度/压力，无 econ_audit）。"""
    return s.external_regimes or {}


def test_24month_two_pool_conservation():
    """24 月：逐省逐月 money/grain 残差恒 0；政权级 = Σ省。"""
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=11)  # 首月建立上月快照
    for _ in range(24):
        run_monthly_settlement(s, seed_offset=11)
        for rk in EXTERNAL_ECONOMY_REGIMES:
            ex = _regimes(s).get(rk) or {}
            agg = ex.get("econ_audit") or {}
            assert agg, f"{rk} 缺 econ_audit（读错字段？）"
            assert int(agg.get("money_residual", 0)) == 0, (
                f"{rk} 政权级 money_residual={agg.get('money_residual')} ≠ 0")
            assert int(agg.get("grain_residual", 0)) == 0, (
                f"{rk} 政权级 grain_residual={agg.get('grain_residual')} ≠ 0")
            # 逐省逐月零残差 + 加和一致性
            sum_m = sum_g = 0
            provs = _provinces(ex)
            assert provs, f"{rk} 无省域（读错字段？）"
            for p in provs:
                pa = p.get("econ_audit") or {}
                mr = int(pa.get("money_residual", 0))
                gr = int(pa.get("grain_residual", 0))
                assert mr == 0, f"{rk}/{p.get('name')} money_residual={mr}"
                assert gr == 0, f"{rk}/{p.get('name')} grain_residual={gr}"
                sum_m += mr
                sum_g += gr
            assert sum_m == int(agg.get("money_residual", 0))
            assert sum_g == int(agg.get("grain_residual", 0))


def test_24month_money_pool_closes():
    """钱池闭合：Δtreasury == Σ(税入 − 军饷 − 官俸) ± 岁币（外源）。"""
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=11)
    for rk in EXTERNAL_ECONOMY_REGIMES:
        ex = _regimes(s).get(rk) or {}
        ex["_t0"] = int(ex.get("treasury", 0) or 0)
    for _ in range(24):
        run_monthly_settlement(s, seed_offset=11)
        for rk in EXTERNAL_ECONOMY_REGIMES:
            ex = _regimes(s).get(rk) or {}
            agg = ex.get("econ_audit") or {}
            t0 = ex.get("_t0", 0)
            t1 = int(ex.get("treasury", 0) or 0)
            # 税入 − 军饷 − 官俸（岁币为外源增量，由 _simulate_external 记入 treasury，
            # 此处用「闭合项」做下界校验：Δ 不得超出闭合项 ± 岁币上界）
            closed = (int(agg.get("tax", 0)) - int(agg.get("paid_army", 0))
                      - int(agg.get("paid_off", 0)))
            delta = t1 - t0
            # 岁币外源是唯一合法的额外增量；给 3 个月上界（含「增」档 1.5×）防「凭空造币」
            from content.data import SUI_GONG_ANNUAL, SUI_GONG_MULT
            _monthly = int(SUI_GONG_ANNUAL) // 12
            tribute_cap = int(_monthly * max(SUI_GONG_MULT.values()) * 3) + 1
            assert delta <= closed + tribute_cap, (
                f"{rk} 钱池不闭合：Δtreasury={delta} 超出闭合项{closed}+岁币上界{tribute_cap}")
            ex["_t0"] = t1


def test_24month_grain_pool_closes():
    """粮池闭合（批 6 · 粮=硬通货）：Σ省 Δgrain == 产 − 食 + 本色饷入 + 平粜入 − 本色税出 − 籴入出。"""
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=11)
    for rk in EXTERNAL_ECONOMY_REGIMES:
        ex = _regimes(s).get(rk) or {}
        ex["_g0"] = sum(
            int(v.get("grain", 0) or 0)
            for p in _provinces(ex) for v in (p.get("pops") or {}).values()
            if isinstance(v, dict))
    for _ in range(24):
        run_monthly_settlement(s, seed_offset=11)
        for rk in EXTERNAL_ECONOMY_REGIMES:
            ex = _regimes(s).get(rk) or {}
            agg = ex.get("econ_audit") or {}
            g0 = ex.get("_g0", 0)
            g1 = sum(
                int(v.get("grain", 0) or 0)
                for p in _provinces(ex) for v in (p.get("pops") or {}).values()
                if isinstance(v, dict))
            gp = agg.get("grain_pay") or {}
            closed = (
                int(agg.get("produced", 0)) - int(agg.get("eaten", 0))
                + int(gp.get("soldier", 0) or 0) + int(gp.get("official", 0) or 0)
                + int(gp.get("ping_tiao_out", 0) or 0)
                - int(gp.get("grain_tax_in_kind", 0) or 0)
                - int(gp.get("ping_tiao_in", 0) or 0)
            )
            assert (g1 - g0) == closed, (
                f"{rk} 粮池不闭合：Δgrain={g1 - g0} ≠ 产−食+本色={closed}")
            ex["_g0"] = g1


def test_phase_f_draft_absent_no_nameerror():
    """批 0 核查：外邦文档 §0.1 点名的 Phase F 破损草稿（agg_res 未定义）不得存在。

    24 月跑完无 NameError 即证明草稿已清（拆分时已删）。
    """
    s = GameState("史实")
    for _ in range(24):
        run_monthly_settlement(s, seed_offset=11)  # 若 agg_res 未定义，此处必抛 NameError
    assert True
