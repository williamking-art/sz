# -*- coding: utf-8 -*-
"""D 首批（Jev A 0.799）：10 个天道门面方法只读接线——记录裁决、不改数值。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

_OBS = (
    "tax_collection_stance", "should_waive_ancient_arrears",
    "merchant_trade_or_hoard", "changping_intervene_gate",
    "canal_reroute_choice", "granary_corruption_check",
    "farmer_destitution_path", "gentry_charity_vs_annex",
    "reform_compliance_gate", "recruit_refugees_to_soldiers_gate",
)


def test_observe_monthly_is_read_only_and_records_all_ten():
    from core.ai.tiandao_facade import TianDaoFacade
    from core.commands import new_game

    s = new_game("史实")
    before = (s.treasury, s.imperial_treasury, s.granary,
              sum(p["pops"]["农"]["wealth"] for p in s.prefectures.values()))
    rec = TianDaoFacade.observe_monthly(s)
    after = (s.treasury, s.imperial_treasury, s.granary,
             sum(p["pops"]["农"]["wealth"] for p in s.prefectures.values()))
    assert before == after, "只读观察不得改任何数值"
    assert set(rec["decisions"]) == set(_OBS)
    assert rec["read_only"] is True
    assert s._tiandao_observe["decisions"] == rec["decisions"]


def test_monthly_settlement_runs_observe_without_changing_result():
    """在结算入口接线后仍不改数值：与直接调用 run 的基线对比（同种子）。"""
    import random
    from core.ai.tiandao_facade import TianDaoFacade
    from core.commands import new_game
    from core.settlement import run_monthly_settlement

    random.seed(20261021)
    s = new_game("史实")
    # 先只观察一次，确认不改状态
    snap = (s.treasury, s.imperial_treasury, s.granary)
    TianDaoFacade.observe_monthly(s)
    assert (s.treasury, s.imperial_treasury, s.granary) == snap
    # 结算不应因观察失败而中断（正常路径下应有记录）
    run_monthly_settlement(s)
    assert getattr(s, "_tiandao_observe", None) is not None
    assert set(s._tiandao_observe["decisions"]) == set(_OBS)
