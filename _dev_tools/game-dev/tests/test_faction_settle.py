# -*- coding: utf-8 -*-
"""利益集团方案第 3 步回归：月结算后由 POP 派生（core/faction_settle.py 为唯一写入点）。"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FACTION_POP_BASIS  # noqa: E402
from core.faction_metrics import all_faction_power  # noqa: E402
from core.faction_settle import (  # noqa: E402
    COH_CONVERGE, SAT_CONVERGE, cohesion_target, satisfaction_target,
    settle_factions_from_pop,
)
from core.game_state import GameState  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402
from core.settlement_steps import _settle_factions  # noqa: E402


def _s():
    return GameState("史实")


def test_influence_is_derived_from_pop_each_month():
    s = _s()
    # influence 公式含 0.10×cohesion，而本步会同时更新 cohesion；
    # 故与本步「开始前」的派生快照比较，而不是写回后的实时重算。
    powers_before = all_faction_power(s)
    out = settle_factions_from_pop(s)
    assert out, "必须至少派生一个集团"
    for name, o in out.items():
        assert o["influence"] == powers_before[name]["influence"], name
        assert s.factions[name]["influence"] == powers_before[name]["influence"], name


def test_step2_no_longer_randomly_walks_faction_numbers():
    """Step 2 不得再随机游走：无 AI 契约时三个读数必须原封不动。"""
    s = _s()
    before = {n: (f["influence"], f["satisfaction"], f["cohesion"])
              for n, f in s.factions.items()}
    _settle_factions(s, [])
    for n, f in s.factions.items():
        assert (f["influence"], f["satisfaction"], f["cohesion"]) == before[n], n


def test_event_delta_is_consumed_once():
    s = _s()
    base = s.factions["新党"]["satisfaction"]
    s.factions["新党"]["_event_delta"] = 12.0
    settle_factions_from_pop(s)
    assert "_event_delta" not in s.factions["新党"], "冲击必须被消化，不得残留反复生效"
    first = s.factions["新党"]["satisfaction"]
    settle_factions_from_pop(s)
    assert s.factions["新党"]["satisfaction"] <= first, "第二次不得再受同一次冲击"
    assert base != first


def test_satisfaction_and_cohesion_move_toward_derived_target():
    s = _s()
    name = "西军集团"
    spec = FACTION_POP_BASIS[name]
    s.factions[name]["satisfaction"] = 0.0
    s.factions[name]["cohesion"] = 0.0
    tgt_sat = satisfaction_target(s, name, spec, s.factions[name])
    tgt_coh = cohesion_target(s, name, spec, s.factions[name])
    settle_factions_from_pop(s)
    assert abs(s.factions[name]["satisfaction"] - tgt_sat * SAT_CONVERGE) < 0.05
    assert abs(s.factions[name]["cohesion"] - tgt_coh * COH_CONVERGE) < 0.05


def test_settle_writes_neither_pop_nor_treasury():
    s = _s()
    pop_before = sum(p["pops"][c]["size"] for p in s.prefectures.values()
                     for c in p["pops"])
    wealth_before = sum(p["pops"][c]["wealth"] for p in s.prefectures.values()
                        for c in p["pops"])
    tr_before = s.treasury
    settle_factions_from_pop(s)
    assert sum(p["pops"][c]["size"] for p in s.prefectures.values()
               for c in p["pops"]) == pop_before
    assert sum(p["pops"][c]["wealth"] for p in s.prefectures.values()
               for c in p["pops"]) == wealth_before
    assert s.treasury == tr_before


def test_pipeline_runs_faction_derivation_and_stays_in_range():
    s = _s()
    for _ in range(24):
        run_monthly_settlement(s, 0)
    for name, f in s.factions.items():
        for k in ("influence", "satisfaction", "cohesion"):
            assert 0.0 <= f[k] <= 100.0, (name, k, f[k])