# -*- coding: utf-8 -*-
"""批 4 · 建筑-岗位-就业模型回归（外邦省域产业链设计 §3）。

断言：
  1) 6 类建筑结构 `{type: {"lv": n}}`（三政权省域）；
  2) 岗位数 = lv × JOBS_PER_LEVEL（粮田 0——粮维豁免）；
  3) 优先队列就业不超岗位、不重复计入；
  4) 轨 A 粮产出 = 农 size × gy × 粮田效率；
  5) 轨 B 产出进州/府 resources（原料）/ 工匠 goods（成品）；
  6) 等级演化：灾荒降级、结余升级、空置降级有 audit 痕迹；
  7) 外邦两池守恒仍恒 0（新模型不破守恒）。
"""
import os
import random
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import EXTERNAL_ECON, EXTERNAL_ECONOMY_REGIMES  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.building_jobs import (  # noqa: E402
    allocate_employment, evolve_building_levels, jobs_of,
    produce_grain_track, produce_job_track, job_flow_unemployed,
    pay_wages_from_revenue, pay_construction_cost, apply_bankruptcy,
)
from core.settlement import run_monthly_settlement  # noqa: E402

CFG = EXTERNAL_ECON


def _eco_provinces(ex):
    return [p for p in (ex.get("provinces") or [])
            if isinstance(p, dict) and isinstance(p.get("buildings"), dict)]


def test_six_building_types_with_lv_structure():
    """三政权省域建筑为 6 类 `{type: {lv}}` 结构。"""
    s = GameState("史实")
    for rk in EXTERNAL_ECONOMY_REGIMES:
        ex = s.external_regimes[rk]
        provs = _eco_provinces(ex)
        assert provs, f"{rk} 无省域建筑"
        for p in provs:
            b = p["buildings"]
            assert isinstance(b, dict) and b, f"{rk}·{p['name']} buildings 空"
            types = set(b.keys())
            assert "粮田" in types, f"{rk}·{p['name']} 缺粮田"
            for bt, entry in b.items():
                assert isinstance(entry, dict) and "lv" in entry, (
                    f"{rk}·{p['name']}·{bt} 非 {{lv}} 结构：{entry!r}")
                assert 0 <= int(entry["lv"]) <= 5


def test_jobs_formula_and_grain_exempt():
    """岗位数 = lv × JOBS_PER_LEVEL；粮田岗位恒 0（粮维豁免）。"""
    buildings = {"粮田": {"lv": 3}, "工坊": {"lv": 2}, "矿场": {"lv": 1}}
    jobs = jobs_of(buildings, CFG)
    assert jobs["粮田"] == 0, "粮田不得占岗"
    assert jobs["工坊"] == 2 * int(CFG["JOBS_PER_LEVEL"]["工坊"])
    assert jobs["矿场"] == 1 * int(CFG["JOBS_PER_LEVEL"]["矿场"])


def test_employment_priority_queue_no_overstaff():
    """优先队列就业：在岗 ≤ 岗位；同月不重复计入。"""
    pops = {"农": {"size": 10000}, "工匠": {"size": 500}}
    buildings = {"粮田": {"lv": 2}, "牧场": {"lv": 2}, "桑麻田": {"lv": 2},
                  "林果蔗田": {"lv": 1}, "工坊": {"lv": 2}, "矿场": {"lv": 1}}
    staffed = allocate_employment(pops, buildings, CFG, "游牧帝国")
    jobs = jobs_of(buildings, CFG)
    for bt, n in staffed.items():
        assert 0 <= n <= jobs.get(bt, 0), f"{bt} 在岗 {n} 超岗位 {jobs.get(bt)}"
    # 农岗合计 ≤ JOB_SHARE × 农 size
    share = CFG["JOB_SHARE"]["游牧帝国"]
    farm_in = sum(n for bt, n in staffed.items()
                  if CFG.get("BUILDING_WORKER", {}).get(bt) == "农")
    assert farm_in <= int(10000 * share) + 1
    # 工匠岗合计 ≤ 工匠 size
    art_in = sum(n for bt, n in staffed.items()
                 if CFG.get("BUILDING_WORKER", {}).get(bt) == "工匠")
    assert art_in <= 500


def test_track_a_grain_uses_farm_lv():
    """轨 A：产粮 = 农 size × gy × (1+0.05×(lv−1))。"""
    pops = {"农": {"size": 1000, "grain": 0}}
    buildings = {"粮田": {"lv": 3}}
    g = produce_grain_track(pops, buildings, CFG, gy=1.0, rtype="游牧帝国")
    expect = int(1000 * 1.0 * (1 + 0.05 * 2))
    assert g == expect, f"产粮 {g} ≠ {expect}"
    assert pops["农"]["grain"] == expect


def test_track_b_produces_raw_and_goods():
    """轨 B：原料进 resources、成品进 goods 池；产量 = staffed × rate × 等级加成。"""
    pops = {"农": {"size": 5000}, "工匠": {"size": 200, "goods": {}}}
    buildings = {"粮田": {"lv": 1}, "桑麻田": {"lv": 2}, "工坊": {"lv": 2},
                  "矿场": {"lv": 1}, "牧场": {"lv": 1}, "林果蔗田": {"lv": 1}}
    resources = {}
    goods_pool = pops["工匠"]["goods"]
    staffed = allocate_employment(pops, buildings, CFG, "党项蕃国")
    prod = produce_job_track(pops, buildings, CFG, "党项蕃国",
                             staffed=staffed, resources=resources,
                             goods_pool=goods_pool)
    assert prod, "轨 B 应有产出"
    raw_dims = set(CFG["RAW_DIMS"])
    for dim, q in prod.items():
        if dim in raw_dims:
            assert resources.get(dim, 0) >= q, f"原料 {dim} 未入 resources"
        else:
            assert goods_pool.get(dim, 0) >= q, f"成品 {dim} 未入 goods 池"


def test_evolve_famine_downgrades_and_surplus_upgrades():
    """等级演化：灾荒必降 1 类；结余+无饥荒按概率升级（用 rng 锁定）。"""
    prov = {"buildings": {"粮田": {"lv": 3}, "工坊": {"lv": 2}, "牧场": {"lv": 2}}}
    rng = random.Random(42)
    chg = evolve_building_levels(prov, CFG, surplus=False, famine=True,
                                  arrears=False, rng=rng)
    assert chg and chg[0]["delta_lv"] == -1 and chg[0]["reason"] == "灾荒"
    # 升级：强制 rng 使 random() < prob
    prov2 = {"buildings": {"粮田": {"lv": 1}, "工坊": {"lv": 1}}}

    class _AlwaysUp:
        def random(self):
            return 0.0

        def choice(self, seq):
            return seq[0]

    chg2 = evolve_building_levels(prov2, CFG, surplus=True, famine=False,
                                   arrears=False, rng=_AlwaysUp())
    assert chg2 and chg2[0]["delta_lv"] == +1


def test_job_flow_conserves_total_pop():
    """就业流动 Σsize 守恒。"""
    pops = {"农": {"size": 10000}, "工匠": {"size": 800}, "商人": {"size": 200},
            "士绅": {"size": 100}, "官僚": {"size": 50}, "兵": {"size": 300}}
    total0 = sum(int(v.get("size", 0) or 0) for v in pops.values())
    buildings = {"粮田": {"lv": 1}, "牧场": {"lv": 1}, "工坊": {"lv": 1}}
    staffed = allocate_employment(pops, buildings, CFG, "西南属国")
    job_flow_unemployed(pops, staffed, CFG, buildings, rtype="西南属国",
                        rng=random.Random(7))
    total1 = sum(int(v.get("size", 0) or 0) for v in pops.values())
    assert total1 == total0, f"Σsize 破裂：{total0} → {total1}"


def test_external_two_pool_still_conserves_with_jobs():
    """新模型下外邦两池守恒仍恒 0（24 月抽样 6 月）。"""
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=11)
    for _ in range(6):
        run_monthly_settlement(s, seed_offset=11)
        for rk in EXTERNAL_ECONOMY_REGIMES:
            ex = s.external_regimes[rk]
            agg = ex.get("econ_audit") or {}
            assert int(agg.get("money_residual", 0)) == 0, (
                f"{rk} money_residual={agg.get('money_residual')}")
            assert int(agg.get("grain_residual", 0)) == 0, (
                f"{rk} grain_residual={agg.get('grain_residual')}")
            for p in _eco_provinces(ex):
                pa = p.get("econ_audit") or {}
                assert int(pa.get("money_residual", 0)) == 0
                assert int(pa.get("grain_residual", 0)) == 0


def test_pay_wages_from_revenue_and_arrears():
    """工资发放：营收足额 → 全发 + 利润归调用侧；营收不足 → 按比例折 + arrears。"""
    pops = {"农": {"size": 500, "wealth": 0}, "工匠": {"size": 200, "wealth": 0},
            "士绅": {"size": 50, "wealth": 0}}
    buildings = {"牧场": {"lv": 2}, "工坊": {"lv": 2}, "粮田": {"lv": 1}}
    staffed = {"牧场": 100, "工坊": 200}
    # 应付 = 100×1.5 + 200×1.2 = 390（游牧）
    st = pay_wages_from_revenue(pops, buildings, CFG, staffed, revenue=500,
                                rtype="游牧帝国")
    assert st["wages_owed"] == 390
    assert st["wages_paid"] == 390
    assert st["arrears_building"] == 0
    assert st["profit"] == 110
    assert pops["农"]["wealth"] > 0 and pops["工匠"]["wealth"] > 0
    # 营收不足
    pops2 = {"农": {"size": 500, "wealth": 0}, "工匠": {"size": 200, "wealth": 0}}
    st2 = pay_wages_from_revenue(pops2, buildings, CFG, staffed, revenue=100,
                                 rtype="游牧帝国")
    assert st2["wages_paid"] < st2["wages_owed"]
    assert st2["arrears_building"] > 0


def test_pay_construction_cost_to_artisan_no_burn():
    """营造费全额转工匠 POP（含 treasury 补出），不得注销。"""
    pops = {"士绅": {"size": 100, "wealth": 50000},
            "工匠": {"size": 50, "wealth": 0}}
    treasury = {"amount": 30000}
    cost_info = pay_construction_cost(pops, CFG, "工坊", new_lv=2,
                                       treasury=treasury)
    assert cost_info["funded"]
    assert cost_info["from_gentry"] + cost_info["from_treasury"] == cost_info["cost"]
    assert pops["工匠"]["wealth"] == cost_info["cost"], "营造费须全额入工匠"
    # 出资不足
    pops2 = {"士绅": {"size": 10, "wealth": 100}, "工匠": {"size": 10, "wealth": 0}}
    t2 = {"amount": 0}
    info2 = pay_construction_cost(pops2, CFG, "工坊", new_lv=3, treasury=t2)
    assert not info2["funded"]


def test_apply_bankruptcy_layoff_and_closed():
    """轻量倒闭：连续 2 月欠薪 → 裁员+降级；lv=1 且持续欠薪 → closed。"""
    prov = {"buildings": {"工坊": {"lv": 2}, "粮田": {"lv": 1}},
            "building_arrears_streak": {}}
    staffed = {"工坊": 200, "粮田": 0}
    ev1 = apply_bankruptcy(prov, CFG, arrears_building=50, staffed=staffed)
    assert ev1 == [], "第 1 月欠薪不触发倒闭"
    assert prov["building_arrears_streak"]["工坊"] == 1
    ev2 = apply_bankruptcy(prov, CFG, arrears_building=50, staffed=staffed)
    assert ev2 and any(e["action"] == "downgrade" for e in ev2)
    assert prov["buildings"]["工坊"]["lv"] == 1
    # 再连续欠薪 → lv=1 降无可降 → closed
    apply_bankruptcy(prov, CFG, arrears_building=50, staffed=staffed)
    ev3 = apply_bankruptcy(prov, CFG, arrears_building=50, staffed=staffed)
    assert any(e["action"] == "closed" for e in ev3), f"应倒闭：{ev3}"
    assert prov["buildings"]["工坊"].get("closed") is True
