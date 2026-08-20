# -*- coding: utf-8 -*-
"""POP 恒等断言补强：人口总量守恒 / 全局钱粮账本 / 灾荒流民。

进度快照第八部分建议新增的 3 类断言（当前 tests/ 未覆盖）：
  1) Σ六类 POP size + 流民：迁移/回乡/科举/逃荒/安置各流动段守恒或符合明确公式；
  2) 全局钱账本 W 与粮账本 G：结算前后变化量 == 明确收支科目，不凭空生灭；
  3) 灾荒流民：农缺粮→逃荒、灾荒→流民骤增、安置→流民减且农增。

账本口径（本文件梳理，测试内唯一权威）：
  W = Σ六类POP wealth + treasury + imperial_treasury
      + 有效交子(issued×trust/100) + Σ士绅窖银
  G = Σ六类POP grain + granary + imperial_granary + Σstorage + Σchangping_stock
  P = Σ六类POP size + Σrefugees

明确科目（设计内，非闭合，已计入断言/报告）：
  - 财政净流出（三冗 expenditure / 贪腐 corruption / 岁币 sui_gong / 加俸 payraise）：钱出系统
  - 榷酒课 wine_coin：内帑凭空收入（wine_tax × (1+0.01×(tech.level-50))）
  - 机构预算 org_net：国库凭空收支（每机构 budget_in-budget_out）
  - 士绅囤抛：市场撮合（钱粮按价互换；任务点名"士绅卖粮造钱"）
  - 生产（收获月）/ 消费（月耗粮）：粮增减
  - 流民自然演化：refugees 按 absorb 公式增减（不扣农 POP，公式化）
  - 本色田赋：仅运期（3/6/9）征收入州仓（三运制），非运期为 0
"""
import os
import random
import sys

import pytest

# 将 game 包根加入路径（脚本直接运行时）
_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from content.data import (  # noqa: E402
    MONTHLY_EXP_CIVIL_BASE, SUI_GONG_ANNUAL, PER_CAPITA_MONTH_GRAIN,
)

# 与 run_monthly_settlement 完全一致的步骤序列（不含结尾 turn/month 推进）
from core.settlement_steps import (  # noqa: E402
    _settle_decrees, _settle_factions, _settle_economy, _settle_land_local,
    _settle_extensions, _settle_longterm_decrees, _simulate_external,
    _settle_granary, _settle_projects, _settle_workshops,
    _settle_treasury, _settle_military_diplomacy, _evaluate_timeline_breaks,
    _settle_events, _settle_disaster, _settle_emperor_personal, _settle_hidden,
)
from core.settlement_extensions import (  # noqa: E402
    _settle_mechanisms, _settle_tech, _settle_org_economy,
)
from core.settlement_finance import _settle_finance  # noqa: E402

_STEPS = [
    ("decrees", _settle_decrees),
    ("factions", _settle_factions),
    ("economy", _settle_economy),
    ("land_local", _settle_land_local),
    ("extensions", _settle_extensions),
    ("longterm", _settle_longterm_decrees),
    ("external", _simulate_external),
    ("granary", _settle_granary),
    ("finance", _settle_finance),
    ("projects", _settle_projects),
    ("workshops", _settle_workshops),
    ("treasury", _settle_treasury),
    ("military", _settle_military_diplomacy),
    ("timeline", _evaluate_timeline_breaks),
    ("mechanisms", _settle_mechanisms),
    ("tech", _settle_tech),
    ("org_economy", _settle_org_economy),
    ("events", _settle_events),
    ("disaster", _settle_disaster),
    ("emperor", _settle_emperor_personal),
    ("hidden", _settle_hidden),
]


def _new_state():
    return GameState("史实")


def _pop_total(s):
    """全国在籍人口 = Σ六类 POP size + 流民。"""
    return sum(pop["size"] for p in s.prefectures.values() for pop in p["pops"].values()) \
        + s.refugee_count


def _wealth_total(s):
    """钱账本 W。"""
    w = sum(pop.get("wealth", 0) for p in s.prefectures.values() for pop in p["pops"].values())
    w += s.treasury + s.imperial_treasury
    w += s.jiaozi["issued"] * (max(0.0, min(1.0, s.jiaozi["trust"] / 100.0)))
    w += sum(p["pops"]["士绅"].get("窖银", 0) for p in s.prefectures.values())
    return w


def _grain_total(s):
    """粮账本 G。"""
    g = sum(pop.get("grain", 0) for p in s.prefectures.values() for pop in p["pops"].values())
    g += s.granary + s.imperial_granary
    g += sum(p.get("storage", 0) for p in s.prefectures.values())
    g += sum(p.get("changping_stock", 0) for p in s.prefectures.values())
    return g


def _refugee_delta_formula(s):
    """_settle_economy 流民演化段的公式预期（absorb 用调用前状态）。"""
    total = 0
    for p in s.prefectures.values():
        local = p.get("refugees", 0)
        if local <= 0 and p.get("unrest", 15) < 20:
            continue
        mood = p.get("mood", 55)
        unrest = p.get("unrest", 15)
        govern = p.get("govern", 55)
        absorb = (mood - 50) * 0.001 + (40 - unrest) * 0.0008 + (govern - 50) * 0.0006
        total += int(local * absorb)
    return total


def _noop_hoard(st, lg):
    pass


def _audit(no_hoard=False, seed=0):
    """逐段结算审计（finance 步前预计算科目），返回 (state, rows, fin_exp, fin_wine, org_net)。

    rows = [(name, dW, dG, dP)]，dX 为该步**单步**变化（相对上一步）；
    fin_exp = finance 步前的 -(三冗+贪腐+岁币+加俸) 预期；fin_wine = finance 步后的酒课；
    org_net = org_economy 步后机构预算净值。
    """
    s = _new_state()
    random.seed(seed)
    from core.asset_context import era_switch
    s.update_era_name()
    era_switch(s)
    prev = (_wealth_total(s), _grain_total(s), _pop_total(s))
    rows = []
    fin_exp = None
    for name, fn in _STEPS:
        if name == "finance":
            # A1 定案·支出回流后：常费（→工匠/商人）与贪腐（→官僚）为内部转移不再减 W，
            # 真实外流仅剩岁币（sui）与加俸（payraise，仍蒸发）；酒课另计。
            sui = 0
            for k, frac in (("辽", 0.6), ("西夏", 0.4)):
                if s.external.get(k, {}).get("attitude", 0) >= 60:
                    sui += int(SUI_GONG_ANNUAL * frac / 12)
            payraise = min(s.payraise_budget, int(s.calc_clerk_gap()[0]) + 10_000)
            fin_exp = -(sui + payraise)
        fn(s, [])
        cur = (_wealth_total(s), _grain_total(s), _pop_total(s))
        rows.append((name, cur[0] - prev[0], cur[1] - prev[1], cur[2] - prev[2]))
        prev = cur
    fin_wine = s.wine_tax * (1.0 + 0.01 * (s.tech["level"] - 50))
    org_net = sum(o.get("net", 0) for o in s.central_orgs.values())
    return s, rows, fin_exp, fin_wine, org_net


# ------------------------------------------------------------
# 组 A：人口总量守恒
# ------------------------------------------------------------
def test_economy_pop_identity_formula():
    """Step 3 后 ΔP == growth + 流民演化公式（迁移/回乡/科举段闭合，无凭空增减）。"""
    s = _new_state()
    random.seed(11)
    p0 = _pop_total(s)
    growth0 = s.population
    delta_sum = _refugee_delta_formula(s)
    _settle_economy(s, [])
    growth = s.population - growth0
    assert abs((_pop_total(s) - p0) - (growth + delta_sum)) <= 20, \
        f"人口恒等断裂：ΔP={_pop_total(s)-p0} growth={growth} 流民公式={delta_sum}"


@pytest.mark.parametrize("boom", ["大", "微"])
def test_migration_boom_and_slump_conservation(boom):
    """城市化（景气大）与回乡（景气微）迁移段闭合：ΔP == growth + 流民公式。"""
    s = _new_state()
    s._economy_ai = {"景气": boom}
    random.seed(23)
    p0 = _pop_total(s)
    growth0 = s.population
    delta_sum = _refugee_delta_formula(s)
    _settle_economy(s, [])
    growth = s.population - growth0
    assert abs((_pop_total(s) - p0) - (growth + delta_sum)) <= 20, \
        f"迁移段丢人（景气={boom}）：ΔP={_pop_total(s)-p0} growth={growth} 流民公式={delta_sum}"


def test_exam_promotion_conservation():
    """科举入仕段闭合（Phase B 定稿·含寒门）：全人口守恒（ΣPOP 变化 == growth ± 12 路 int 截断）；
    科举内部转移守恒：官僚增 == 士绅减 + 寒门（农）减。隔离城市化/回乡只验科举流动。"""
    s = _new_state()
    s.exam["open"] = True
    s._economy_ai = {"景气": "中", "城市化": "无", "回乡": "无"}   # 隔离：只保留科举流动
    random.seed(29)
    g0 = sum(p["pops"]["士绅"]["size"] for p in s.prefectures.values())
    n0 = sum(p["pops"]["农"]["size"] for p in s.prefectures.values())
    b0 = sum(p["pops"]["官僚"]["size"] for p in s.prefectures.values())
    t0 = sum(pop["size"] for p in s.prefectures.values() for pop in p["pops"].values())
    p0_pop = s.population
    _settle_economy(s, [])
    growth = s.population - p0_pop
    g1 = sum(p["pops"]["士绅"]["size"] for p in s.prefectures.values())
    n1 = sum(p["pops"]["农"]["size"] for p in s.prefectures.values())
    b1 = sum(p["pops"]["官僚"]["size"] for p in s.prefectures.values())
    t1 = sum(pop["size"] for p in s.prefectures.values() for pop in p["pops"].values())
    # 全人口守恒：growth 是唯一外部输入，每路 int 截断累计 ≤ 路数
    assert abs((t1 - t0) - growth) <= 20, f"人口不守恒：ΔΣPOP={t1-t0} growth={growth}"
    # 科举内部转移：农增 = growth 分配 − 寒门入仕；官僚增 == 士绅减 + 寒门减
    _alloc = sum(int(growth * p.get("population", 1) / max(s.population, 1))
                 for p in s.prefectures.values())
    assert g0 - g1 >= 0, "士绅不应因科举增加"
    assert (b1 - b0) == (g0 - g1) + (_alloc - (n1 - n0)), \
        f"科举转移不守恒：Δ官僚={b1-b0} 士绅减={g0-g1} 寒门减={_alloc-(n1-n0)}"


def test_famine_flee_conservation():
    """农缺粮逃荒闭合：ΣΔ农 size == -ΣΔrefugees（_settle_granary 消费段）。"""
    s = _new_state()
    for p in s.prefectures.values():
        p["pops"]["农"]["grain"] = 0
    random.seed(7)
    f0 = sum(p["pops"]["农"]["size"] for p in s.prefectures.values())
    r0 = s.refugee_count
    _settle_granary(s, [])
    f1 = sum(p["pops"]["农"]["size"] for p in s.prefectures.values())
    r1 = s.refugee_count
    assert f1 < f0 and r1 > r0, "缺粮应逃荒（农减、流民增）"
    assert (f1 - f0) + (r1 - r0) == 0, f"逃荒丢人：Δ农={f1-f0} Δ流民={r1-r0}"


def test_refugee_natural_evolution_formula():
    """流民自然演化符合明确公式（absorb 驱动；治理差则凭空自增——钉住公式供团队知悉）。"""
    s = _new_state()
    for p in s.prefectures.values():
        p["mood"] = 70
        p["govern"] = 60
        p["unrest"] = 10
        p["refugees"] = 10_000
    random.seed(5)
    r0 = s.refugee_count
    delta_sum = _refugee_delta_formula(s)
    _settle_economy(s, [])
    assert s.refugee_count - r0 == delta_sum, \
        f"流民演化偏离公式：Δ={s.refugee_count-r0} 公式={delta_sum}"


# ------------------------------------------------------------
# 组 B：灾荒流民
# ------------------------------------------------------------
def test_disaster_outbreak_refugee_flow(monkeypatch):
    """灾荒发生 → 流民增 == 农减 == flee（flee=min(severity×5000, cap余量, 农size)），人口守恒。

    BUG#2 修复后：受灾农民逃荒为流民，不再凭空增；农 size 充足时 flee == severity×5000。
    """
    from core import settlement_disaster as _sd
    monkeypatch.setattr(_sd.random, "random", lambda: 0.0)      # 强制触发
    monkeypatch.setattr(_sd.random, "randint", lambda a, b: 5)  # severity=5
    monkeypatch.setattr(_sd.random, "choice", lambda seq: "河北")
    s = _new_state()
    region = _sd._normalize_disaster_region(s, "河北")
    assert region is not None
    r0 = s.prefectures[region].get("refugees", 0)
    n0 = s.prefectures[region]["pops"]["农"]["size"]
    cap = int(s.prefectures[region].get("population", 1_000_000) * 0.10)
    _sd._settle_disaster(s, [])
    add = 5 * 5000
    flee = min(add, max(0, cap - r0), n0)
    assert s.disaster_severity == 5 and s.disaster_region == "河北"
    # 流民增 == flee（农 size 充足时 flee == severity×5000）
    assert s.prefectures[region]["refugees"] - r0 == flee, \
        f"流民骤增量偏离公式：Δ流民={s.prefectures[region]['refugees']-r0} flee={flee}"
    # 农减 == flee（人口守恒：受灾农民→流民）
    assert n0 - s.prefectures[region]["pops"]["农"]["size"] == flee, \
        f"农 POP 减少量与流民增量不一致（人口不守恒）"


def test_disaster_relief_settlement_conservation(monkeypatch):
    """赈济安置应回流农 POP：流民减少且农 size 增加（任务断言 3）。

    参照：诏令 settle_refugees 已实现"流民→农"回流（test_decree_...），
    而 _settle_disaster 赈济段只减流民不增农 —— 预期失败，暴露真实 bug。
    """
    from core import settlement_disaster as _sd
    monkeypatch.setattr(_sd.random, "random", lambda: 0.5)  # 不触发新灾荒
    s = _new_state()
    s.disaster_severity = 2
    s.disaster_region = "两浙"
    s.granary = 100_000_000  # 充足，赈济足额
    region = _sd._normalize_disaster_region(s, "两浙")
    assert region is not None
    s.prefectures[region]["refugees"] = 100_000
    f0 = s.prefectures[region]["refugees"]
    n0 = s.prefectures[region]["pops"]["农"]["size"]
    _sd._settle_disaster(s, [])
    f1 = s.prefectures[region]["refugees"]
    n1 = s.prefectures[region]["pops"]["农"]["size"]
    assert f1 < f0, "赈济应减少流民"
    used = f0 - f1
    assert used > 0, "赈济应实际安置流民"
    # 任务断言：安置流民 → 农 size 增加（当前实现缺失 → 失败）
    assert n1 - n0 == used, \
        f"BUG: 赈济安置 {used} 流民未回流农 POP（Δ农={n1-n0}），人口凭空减少 {used}"


def test_decree_settle_refugees_conservation(monkeypatch):
    """对照参照：诏令 settle_refugees 安置流民 → 流民↓ == 农↑（已实现，须通过）。"""
    from core import settlement_steps as _m
    monkeypatch.setattr(_m.random, "random", lambda: 0.0)  # 诏令必执行
    s = _new_state()
    s.prefectures["两浙路"]["refugees"] = 10_000
    s.pending_decrees = [{
        "id": "ref1", "title": "安置流民",
        "effects": {"settle_refugees": 5000},
        "faction_stances": {}, "duration": 0,
    }]
    f0 = s.prefectures["两浙路"]["refugees"]
    n0 = s.prefectures["两浙路"]["pops"]["农"]["size"]
    _m._settle_decrees(s, [])
    f1 = s.prefectures["两浙路"]["refugees"]
    n1 = s.prefectures["两浙路"]["pops"]["农"]["size"]
    assert f0 - f1 == n1 - n0 > 0, f"诏令安置应回流守恒：Δ流民={f0-f1} Δ农={n1-n0}"


# ------------------------------------------------------------
# 组 C：全局钱粮守恒（禁用士绅囤抛 = 只保留账本内闭合 + 明确科目）
# ------------------------------------------------------------
def test_wealth_ledger_no_hoard(monkeypatch):
    """逐段钱账本恒等：禁用囤抛后，除 finance/org_economy 外各步 ΔW==0；
    finance 步 ΔW == -(岁币+加俸)（酒课税改造后为工匠/商人→内帑内部转移，不再凭空增 W；±50 int 截断）；
    org 步 == 机构预算；granary 步只许 int 截断小残差（只吞钱不造钱）。"""
    from core import settlement_steps as _m
    monkeypatch.setattr(_m, "_settle_civilian_hoard", _noop_hoard)
    s, rows, fin_exp, fin_wine, org_net = _audit(no_hoard=True)
    for name, dW, dG, dP in rows:
        if name == "finance":
            assert abs(dW - fin_exp) <= 50, \
                f"财政步钱账本断裂：ΔW={dW} 预期={fin_exp}"
        elif name == "org_economy":
            assert abs(dW - org_net) <= 1, f"机构预算未记账：ΔW={dW} org_net={org_net}"
        elif name == "workshops":
            # 畜栏产肉折钱入内帑（加消耗修正·依托建筑；太仓粮耗不在 W 账）
            assert abs(dW - s.granary_stats.get("meat_revenue", 0)) <= 1, \
                f"作坊步肉钱未记账：ΔW={dW} meat={s.granary_stats.get('meat_revenue',0)}"
        elif name == "granary":
            # int 截断残差（消费/奢侈/窖银回流舍入），只吞钱不造钱
            assert -300 <= dW <= 0, f"granary 步 ΔW={dW} 超出 int 截断容差"
        else:
            assert abs(dW) <= 1, f"步骤 {name} 钱账本凭空变化：ΔW={dW}"


def test_granary_ledger_no_hoard(monkeypatch):
    """粮账本（非运期 1 月）：太仓净出 == 雀鼠耗+本色俸禄+贪腐本色（±2）；
    州仓无新征（本色田赋仅运期）；POP 粮变化 ∈ [-月需求, 0]（无生产/田赋，不凭空增减）。"""
    from core import settlement_steps as _m
    monkeypatch.setattr(_m, "_settle_civilian_hoard", _noop_hoard)
    s = _new_state()
    random.seed(0)
    from core.asset_context import era_switch
    s.update_era_name()
    era_switch(s)
    g0 = s.granary
    pop_g0 = sum(pop.get("grain", 0) for p in s.prefectures.values() for pop in p["pops"].values())
    storage0 = sum(p.get("storage", 0) for p in s.prefectures.values())
    # Phase B：口粮按职业（GRAIN_CONSUME_PER_CAPITA），隐户消费另计
    from content.data import GRAIN_CONSUME_PER_CAPITA
    need_sum = sum(int(pop["size"] * GRAIN_CONSUME_PER_CAPITA.get(pn, 0.5))
                   for p in s.prefectures.values() for pn, pop in p["pops"].items())
    corr_grain = s.calc_corruption_deduction()[1]
    corr_actual_pre = min(int(corr_grain * s.pay_system.get("grain_ratio", 0.5)), s.granary)
    for name, fn in _STEPS:
        fn(s, [])
    g1 = s.granary
    pop_g1 = sum(pop.get("grain", 0) for p in s.prefectures.values() for pop in p["pops"].values())
    storage1 = sum(p.get("storage", 0) for p in s.prefectures.values())
    # 太仓净出 == 雀鼠耗 + 本色俸禄（military）+ 贪腐本色 + 作坊耗粮（酒坊/畜栏 grain_feed，加消耗修正）
    out_ledger = (s.granary_stats["sparrow"] + s.granary_stats["military"] + corr_actual_pre
                  + s.granary_stats.get("workshop_feed", 0))
    assert abs((g0 - g1) - out_ledger) <= 2, \
        f"太仓净出账本断裂：Δgranary={g0-g1} 出库={out_ledger}"
    # 非运期（1 月）本色田赋为 0 → 州仓无新征
    assert storage1 - storage0 == 0, "非运期州仓不应有本色田赋入库"
    # POP 粮变化边界：无生产月只减不增，且不超过「月需求 + 隐户 + 种粮」（加工型酿酒/饲料已改从太仓扣，
    # 不再动 POP 粮；粮市撮合为内部转移 Σ不变）
    hidden_feed = s.granary_stats.get("hidden_feed", 0)
    seed = s.granary_stats.get("seed_grain", 0)
    d_pop = pop_g1 - pop_g0
    seed = s.granary_stats.get("seed_grain", 0)
    spoil = s.granary_stats.get("farmer_spoil", 0)
    assert -need_sum - hidden_feed - seed - spoil <= d_pop <= 0, \
        f"POP 粮变化越界：Δ={d_pop} 月需求={need_sum} 隐户={hidden_feed} 种粮={seed} 霉耗={spoil}"


def test_harvest_month_land_tax_into_storage():
    """运期（3 月）田赋本色入州仓：0 < Δstorage ≤ Σ税粮（田亩演化使实际应征 ≤ 全量税粮）。"""
    s = _new_state()
    s.month = 3
    random.seed(4)
    _, grain_by = s.calc_monthly_grain()
    tax_total = sum(int(g) for g in grain_by.values())
    assert tax_total > 0, "运期本色田赋应大于 0"
    storage0 = sum(p.get("storage", 0) for p in s.prefectures.values())
    _settle_land_local(s, [])
    storage1 = sum(p.get("storage", 0) for p in s.prefectures.values())
    assert 0 < storage1 - storage0 <= tax_total, \
        f"本色田赋入库异常：Δstorage={storage1-storage0} 税粮总量={tax_total}"


def test_hoard_market_exchange_ledger():
    """士绅囤抛 = 市场撮合（B1 买方化 + 买方得粮）：全体 POP Δg 度量（士绅 -sold + 买方 +sold == 0），
    综合 ΔW + Σ(price×全体Δg) == 0（±int 截断），无净造钱/灭粮。
    先压回囤粮上限排除超上限核销干扰（核销为设计内单向损耗，由 hoard_net_direction 量级覆盖）。"""
    s = _new_state()
    random.seed(3)
    # 压回各路士绅囤粮上限（防超上限核销把粮凭空消掉、干扰市场撮合断言）
    for k, p in s.prefectures.items():
        land = max(float(p.get("land", 1)), 1.0)
        gl = float(p.get("gentry_land", 0)) + float(p.get("hidden_land", 0))
        cap = int(p.get("grain", 0) * gl / land * 0.2)
        p["pops"]["士绅"]["grain"] = min(p["pops"]["士绅"]["grain"], cap)
    from core.settlement_civilian import _settle_civilian_hoard
    W0 = _wealth_total(s)
    # 全体 POP grain 度量（士绅 + 各买方），而非只士绅
    g_before = {k: sum(pop.get("grain", 0) for pop in p["pops"].values()) for k, p in s.prefectures.items()}
    price = {k: p.get("grain_price", s.grain_price) for k, p in s.prefectures.items()}
    _settle_civilian_hoard(s, [])
    W1 = _wealth_total(s)
    res = 0.0
    for k, p in s.prefectures.items():
        dg = sum(pop.get("grain", 0) for pop in p["pops"].values()) - g_before[k]
        res += price[k] * dg
    assert abs((W1 - W0) + res) <= 40, \
        f"囤抛市场撮合断裂：ΔW={W1-W0} Σ(price×全体Δg)={res:.1f} 合计={W1-W0+res:.1f}"


def test_hoard_net_direction():
    """士绅囤抛不凭空造钱（B1 买方化）：净造钱 ≈ 0（±int 截断容差，旧 bug 为显著正值）；
    囤积/超上限核销方向为净耗粮（G 减），量级有上限防失控。"""
    _, rows_full, _, _, _ = _audit(no_hoard=False)
    _, rows_none, _, _, _ = _audit(no_hoard=True)
    dW_full = sum(r[1] for r in rows_full)
    dW_none = sum(r[1] for r in rows_none)
    dG_full = sum(r[2] for r in rows_full)
    dG_none = sum(r[2] for r in rows_none)
    hoard_w = dW_full - dW_none
    hoard_g = dG_full - dG_none
    assert abs(hoard_w) <= 100_000, f"士绅囤抛不应凭空造/灭钱：{hoard_w}"
    assert abs(hoard_g) <= 20000, f"囤抛段粮应有界（士绅囤抛方向随粮价，可小幅囤或抛）：{hoard_g}"
    assert abs(hoard_g) < 1e8, f"囤抛粮量级异常：{hoard_g}"


def test_global_ledger_total(monkeypatch):
    """整月总账（固定 seed 跑一月）：ΔW(无囤抛) == -(岁币+加俸)+机构预算（酒课为内部转移，±350 int 截断）；
    ΔP == growth + 流民公式（±20）。无未解释残差。"""
    from core import settlement_steps as _m
    monkeypatch.setattr(_m, "_settle_civilian_hoard", _noop_hoard)
    s, rows, fin_exp, fin_wine, org_net = _audit(no_hoard=True)
    dW = sum(r[1] for r in rows)
    dP = sum(r[3] for r in rows)
    # 加消耗修正：畜栏产肉折钱入内帑（meat_revenue，依托建筑；太仓粮耗不在 W 账）
    expected = fin_exp + org_net + s.granary_stats.get("meat_revenue", 0)
    assert abs(dW - expected) <= 350, \
        f"整月钱账本残差过大：ΔW={dW} 科目净值={expected}（差 {dW-expected}）"
    # 人口：growth + 流民公式（初始状态重算）
    growth = s.population - 80_000_000
    delta_pre = _refugee_delta_formula(_new_state())
    assert abs(dP - (growth + delta_pre)) <= 20, \
        f"整月人口残差过大：ΔP={dP} growth={growth} 流民公式={delta_pre}"


# ------------------------------------------------------------
# 组 D：交子超发 / 市舶利润（补充派单第 4 类断言）
# ------------------------------------------------------------
def test_jiaozi_overissue_trust_and_effective_collapse():
    """交子超发（issued > _jiaozi_ceiling）→ trust 下降、有效交子退出流通、钱荒加剧。

    公式：trust_after == min(100, max(0, trust_before - int(over/1e6×10×皇威因子)) + 1)；
    有效交子变化 == issued×(Δtrust)/100（精确守恒，非凭空）。
    """
    s = _new_state()
    s.prestige = 50
    s.jiaozi["issued"] = 10_000_000
    s.jiaozi["trust"] = 60
    s.jiaozi["reserve"] = 2_000_000
    ceiling = s._jiaozi_ceiling()
    over = s.jiaozi["issued"] - ceiling
    factor = 2.0 - s.prestige / 50.0
    trust_cut = int(over / 1_000_000 * 10 * max(0.0, factor))
    assert ceiling == 4_000_000 and trust_cut == 60, "超发基准构造失效"
    t0 = s.jiaozi["trust"]
    eff0 = s.jiaozi["issued"] * s._jiaozi_acceptance()
    sh0 = s.coin["shortage"]
    random.seed(13)
    _settle_extensions(s, [])
    t1 = s.jiaozi["trust"]
    eff1 = s.jiaozi["issued"] * s._jiaozi_acceptance()
    assert t1 == min(100, max(0, t0 - trust_cut) + 1), f"trust 崩坏公式不符：{t0}→{t1}"
    assert t1 < t0, "超发应使交子信用下降"
    assert eff1 < eff0, "超发后有效交子应退出流通（缩水）"
    assert abs((eff1 - eff0) - s.jiaozi["issued"] * (t1 - t0) / 100.0) < 1, \
        "有效交子变化应精确等于 issued×Δtrust/100"
    assert s.coin["shortage"] > sh0, "超发应加剧钱荒"


def test_jiaozi_overissue_money_supply_not_created():
    """超发不凭空增货币：有效交子退出流通 → 货币供给实际收缩（其余项未动）。"""
    s = _new_state()
    s.prestige = 50
    s.jiaozi["issued"] = 10_000_000
    s.jiaozi["trust"] = 60
    s.calc_price_level()
    ms0 = s.money_supply
    accept0 = s._jiaozi_acceptance()
    random.seed(13)
    _settle_extensions(s, [])
    s.calc_price_level()
    d_eff = s.jiaozi["issued"] * (s._jiaozi_acceptance() - accept0)
    melt = s.coin.get("private_melt", 0.2)
    assert s.money_supply < ms0, "超发不应凭空增加货币供给"
    assert abs(s.money_supply - (ms0 + d_eff * (1 - melt))) <= 1, \
        f"货币供给变化未精确归因于有效交子：Δ={s.money_supply-ms0} 预期={d_eff*(1-melt)}"


def test_jiaozi_moderate_issue_relieves_shortage():
    """适量发钞（issued ≤ ceiling）→ 钱荒缓解（shortage↓）、trust 恢复（+1）。"""
    s = _new_state()
    s.prestige = 50
    s.jiaozi["issued"] = 1_000_000  # ≤ 4M ceiling
    s.jiaozi["trust"] = 60
    assert s.jiaozi["issued"] <= s._jiaozi_ceiling()
    sh0 = s.coin["shortage"]
    t0 = s.jiaozi["trust"]
    random.seed(19)
    _settle_extensions(s, [])
    assert s.coin["shortage"] == max(0.1, sh0 - 0.005), "适量发钞应缓解钱荒"
    assert s.jiaozi["trust"] == min(100, t0 + 1), "适量发钞应恢复信用"


def test_maritime_trade_ledger_closed():
    """市舶贸易钱账本闭口：关税抽解入国库 + 商人 POP 得外贸利润，
    国库+商人所得 == 贸易额×(关税率 + (1-关税率)×0.3)（±12 路 int 分摊截断）。"""
    s = _new_state()
    s.maritime["open"] = True
    s.maritime["tariff"] = 0.10
    s.maritime["silver_in"] = 30
    random.seed(17)
    trade = s.calc_maritime_trade() / 12.0
    tariff = int(trade * 0.10)
    profit = int(trade * (1 - 0.10) * 0.3)
    assert trade > 0, "市舶开启后贸易额应大于 0"
    t0 = s.treasury
    w0 = sum(p["pops"]["商人"]["wealth"] for p in s.prefectures.values())
    _settle_extensions(s, [])
    dT = s.treasury - t0
    dW = sum(p["pops"]["商人"]["wealth"] for p in s.prefectures.values()) - w0
    assert dT == tariff, f"关税抽解入国库不符：Δtreasury={dT} 预期={tariff}"
    assert 0 < dW <= profit, f"商人利润不符：ΔΣ商人wealth={dW} 预期∈(0,{profit}]"
    # 闭口：国库+商人所得 == 贸易额×比例（分摊 int 截断 ≤ 12 路）
    assert abs((dT + dW) - (tariff + profit)) <= 12, \
        f"市舶账本未闭口：国库+商人={dT+dW} 预期={tariff+profit}"


def test_maritime_silver_enters_money_supply():
    """白银入货币：市舶开启时 silver_in 按 open 计入货币有效供给（×10000×开放标志）。"""
    s_open = _new_state()
    s_open.maritime["open"] = True
    s_open.maritime["silver_in"] = 30
    s_close = _new_state()
    s_close.maritime["open"] = False
    s_close.maritime["silver_in"] = 30
    s_open.calc_price_level()
    s_close.calc_price_level()
    melt = s_open.coin.get("private_melt", 0.2)
    silver = s_open.maritime["silver_in"] * 1 * 10000
    assert abs((s_open.money_supply - s_close.money_supply) - silver * (1 - melt)) <= 1, \
        "白银折钱未按 open×silver_in×10000 计入货币供给"


if __name__ == "__main__":
    test_economy_pop_identity_formula()
    test_migration_boom_and_slump_conservation("大")
    test_migration_boom_and_slump_conservation("微")
    test_exam_promotion_conservation()
    test_famine_flee_conservation()
    test_refugee_natural_evolution_formula()
    test_jiaozi_overissue_trust_and_effective_collapse()
    test_jiaozi_overissue_money_supply_not_created()
    test_jiaozi_moderate_issue_relieves_shortage()
    test_maritime_trade_ledger_closed()
    test_maritime_silver_enters_money_supply()
    print("POP IDENTITY (pop group) PASSED")
