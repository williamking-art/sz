# -*- coding: utf-8 -*-
"""B2-R4 · 农业供给与收入反馈的定向回归（规格 `market-civilian-economy` B2-R4）。

锁定六件事（与 B2-R4「放行证据」一一对应）：

1. **投资 → 实物增产 → 可售粮 → 农户收入** 的因果链真的闭合（不靠给 POP 加财富）；
2. **无投资地区不凭空变化**（读数为 `defined=True` + 实测 0.0，而非"缺失伪装成 0"）；
3. **材料/工资/粮食/钱账守恒**（Σ 资源、Σ 田亩、Σ 钱、Σ 粮恒等式）；
4. **POP 得失可追溯**（本模块绝不改任何 POP `size`／`wealth`，收入全部有对手方）；
5. **非法输入拒绝式处理**；
6. **缺失 ≠ 0 ≠ 1.0**（读数缺失返回 `None`/`defined=False`，不回落 0/1.0）。

接线说明：本模块**尚未接线**到 `settlement.py`（由 Lead 统一接线），
端到端用例按「`apply_agri_effects` → `run_monthly_settlement`」顺序驱动，
用于验证因果链本身；正式接线顺序见 `settlement_agri.WIRING_HINT`。
"""
import os
import random
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import settlement_agri as A                      # noqa: E402
from core.game_state import GameState                     # noqa: E402
from core.legacy_mechanic import init_legacies            # noqa: E402
from core.material_holding import supply_merchant_materials     # noqa: E402
from core.production_chain import settle_production_chain  # noqa: E402
from core.settlement_granary import _settle_granary       # noqa: E402
import core.settlement as S                                # noqa: E402


# =============================================================================
# 夹具
# =============================================================================

def _state():
    """全新开局（确定性：不跑结算，字段即开局值）。

    ⚠️ 2026-10-11：开局 `buildings` **不再为空**——为让农业投资有可作用对象，
    `game_state._init_agri_buildings` 配置了农业基础设施（见 B2-R4 接线补缺）。
    因此需要"零投资基线"的测试必须显式调`_state_no_agri()`，
    否则会在**开局存量之上**叠加，量级对不上。

    🔴 口径 C-c（2026-10-02）：农业物料**只从本地州府仓取**，故须
    `settle_production_chain`（补满建材仓——**开局 stock 为 0**）＋
    `supply_merchant_materials`（搬进商人货栈），与真实流水线
    Step 4.4/4.45（`settlement.py`）一致。手工夹具不跑流水线，必须显式补，
    否则材料覆盖率恒为 0（最短板降效 → 维护费/产出全被压成 0）。
    """
    s = GameState("史实")
    init_legacies(s)
    settle_production_chain(s, [])
    supply_merchant_materials(s)
    s.treasury = 50_000_000
    s.statistics.setdefault("upkeep_arrears", 0)
    return s


def _state_no_agri():
    """**零农业投资基线**：清空全部路的 `buildings`。

    用于精确测量"给定投资 → 增量效果"的测试，避免与开局存量叠加。
    """
    s = _state()
    for p in s.prefectures.values():
        p["buildings"] = {}
    return s


def _route(s, idx=0):
    return list(s.prefectures)[idx]


def _stock(s, dim, qty, route=None):
    """设某维建材存量。

    🔴 **E-1**（2026-10-02「建材也是商品啊」）：建材是**商品**，存量落在
    **本路商人 POP `goods`**，故给定 `route` 时写**商人货栈**。
    不给 `route` 则只设仓总账（仅供不涉消费的用例）。
    """
    s.resources.setdefault(dim, {"stock": 0, "cap": 50000})["stock"] = qty
    if route:
        goods = s.prefectures[route]["pops"]["商人"]["goods"]
        # 🔴 2026-10-03：建材按 `goods[治所][dim]` 州府桶存放，「设为 0」须先清桶，
        # 否则真实库存留在桶里，「无料」用例会假通过（ratio 变 1.0）。
        for k in [k for k in goods if "|" in k and isinstance(goods.get(k), dict)]:
            goods[k].pop(dim, None)
        goods[dim] = int(qty)


def _invest(s, route, name, lv=1, stock=50_000):
    """给某路加一项**已登记**的农业投资，并保证料/钱充足（便于单测效果量级）。"""
    s.prefectures[route].setdefault("buildings", {})[name] = lv
    for dim in A.AGRI_UPGRADE_EFFECTS[name]["material_per_lv"]:
        _stock(s, dim, stock, route=route)
    s.treasury = max(int(s.treasury), 10_000_000)


def _money_total(s):
    """Σ 钱（国库 + 内帑 + 全部路 POP wealth）。本模块不得改变它。"""
    total = float(getattr(s, "treasury", 0) or 0) + \
        float(getattr(s, "imperial_treasury", 0) or 0)
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                total += float(pop.get("wealth", 0) or 0)
    return total


def _grain_total(s):
    total = 0.0
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                total += float(pop.get("grain", 0) or 0)
    return total


def _pop_total(s):
    total = 0
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                total += int(pop.get("size", 0) or 0)
    return total


def _land_total(s):
    return int(s.land.get("wasteland", 0) or 0) + \
        sum(int(p.get("land", 0) or 0) for p in s.prefectures.values())


def _res_total(s):
    """Σ**建材**存量。

    🔴 **E-1**（2026-10-02）：建材是**商品**，扣减落在**各路商人 POP `goods`**，
    仓总账不再随消费变动 ⇒ 此处统计商人货栈，才是"材料真被扣"的证据。
    """
    from core.material_holding import MATERIAL_DIMS, merchant_goods
    tot = 0.0
    for r in s.prefectures:
        goods = merchant_goods(s, r)
        if not goods:
            continue
        for dim in MATERIAL_DIMS:
            tot += float(goods.get(dim, 0) or 0)
    return tot


def _micro_route(s, route):
    """把某路改成**供给受限**的微型市场：农户余粮少、买户缺口大且有钱。

    供给受限时，新增产量才会真的变成"可售粮 + 农户现金收入"
    （需求饱和时增产卖不掉，是市场约束而非本模块失效）。
    """
    p = s.prefectures[route]
    p["grain_price"] = 1.0
    pops = p["pops"]
    pops["农"].update(size=1_000, grain=5_000, wealth=100)
    pops["士绅"].update(size=8_000, grain=0, wealth=10_000_000)
    pops["工匠"].update(size=5_000, grain=0, wealth=10_000_000)
    pops["商人"].update(size=5_000, grain=0, wealth=10_000_000)
    pops["官僚"].update(size=100, grain=100, wealth=0)
    pops["兵"].update(size=100, grain=100, wealth=0)
    # 年产缩到与微型规模相称，使"年增产"与"农户持粮"同一量级
    p["grain"] = 60_000
    return p


# =============================================================================
# 1 · 因果链：低成本投入 → 产量/可售粮/农户收入提高
# =============================================================================

def test_investment_raises_physical_output_in_harvest_month():
    """水利 Lv1 ⇒ 本路实物增产 = 年产 × 注册增产率 × 到位率 ÷ 3（收获月）。"""
    s = _state_no_agri()
    r = _route(s)
    p = _micro_route(s, r)
    reg = A.AGRI_UPGRADE_EFFECTS["水利"]
    _invest(s, r, "水利", 1)

    eff = A.route_agri_effect(s, r)
    assert eff["defined"] is True
    assert eff["applied_ratio"] == 1.0, f"成本应全额到位：{eff['cover']}"
    assert eff["yield_mult"] == pytest.approx(reg["yield_mult"])

    g0 = p["pops"]["农"]["grain"]
    before = _grain_total(s)
    summ = A.apply_agri_effects(s, [], month=3)
    expect = int(round(60_000 * reg["yield_mult"] * 1.0 * A.AGRI_HARVEST_SHARE))
    assert summ["grain_produced"] == expect
    assert p["pops"]["农"]["grain"] - g0 == expect
    assert _grain_total(s) - before == expect, "本步只应新增注册过的产粮"
    # 登记进 statistics（粮账恒等式的"产"项可对账）
    assert float(s.statistics["agri_grain_produced"]) == pytest.approx(float(expect))


def test_no_harvest_month_produces_no_grain_but_still_pays_cost():
    """非收获月**不凭空产粮**，但维护费照付（成本纪律：先扣后产）。"""
    s = _state_no_agri()
    r = _route(s)
    _invest(s, r, "农田", 1)                 # "农田" 走 incremental 维护费
    before_grain = _grain_total(s)
    summ = A.apply_agri_effects(s, [], month=4)
    assert summ["harvest_month"] is False
    assert summ["grain_produced"] == 0
    assert _grain_total(s) == before_grain
    assert summ["upkeep_paid"] > 0, "非收获月也必须付增量维护费"


def test_farmer_income_and_sellable_grain_rise_after_investment():
    """**核心放行证据**：投资区农户售粮收入 > 对照区（钱粮经既有粮市撮合）。"""
    def run(invest):
        s = _state_no_agri()
        r = _route(s)
        p = _micro_route(s, r)
        if invest:
            _invest(s, r, "水利", 1)
        w0 = p["pops"]["农"]["wealth"]
        A.apply_agri_effects(s, [], month=3)
        random.seed(99)
        _settle_granary(s, [])
        return p["pops"]["农"]["wealth"] - w0

    ctrl, invested = run(False), run(True)
    assert invested > ctrl, f"投资后农户收入未提高：对照 {ctrl} vs 投资 {invested}"
    # 增产 1,000 石、单价 1.0 贯 ⇒ 收入增量应与之同量级（供给受限下全额变现）
    assert invested - ctrl >= 500, f"农户收入增量与增产不匹配：{invested - ctrl}"


def test_multi_season_end_to_end_yield_and_income_up():
    """数季（6 月）端到端：投资路产量/可售粮/农户收入均高于同种子对照。"""
    def run(invest, months=6):
        random.seed(4242)
        s = _state_no_agri()
        r = _route(s)
        p = s.prefectures[r]
        if invest:
            p.setdefault("buildings", {})["水利"] = 1
        for i in range(months):
            s.treasury = max(s.treasury, 20_000_000)
            _stock(s, "timber", 50_000)
            _stock(s, "stone", 50_000)
            A.apply_agri_effects(s, [], month=s.month)
            random.seed(1000 + i)
            S.run_monthly_settlement(s)
        return (p["pops"]["农"]["wealth"], p["pops"]["农"]["grain"],
                float(s.statistics.get("agri_grain_produced", 0) or 0))

    cw, cg, cp = run(False)
    iw, ig, ip = run(True)
    assert ip > 0, "投资路未登记任何增产"
    assert cp == 0.0, "对照路不该有增产"
    assert ig > cg, f"投资路可售粮未增加：{ig} vs {cg}"
    assert iw > cw, f"投资路农户收入未增加：{iw} vs {cw}"


# =============================================================================
# 2 · 无投资地区不凭空变化
# =============================================================================

def test_route_without_investment_is_measured_zero_not_missing():
    s = _state_no_agri()
    r = _route(s)
    eff = A.route_agri_effect(s, r)
    assert eff["defined"] is True, "无投资是**实测 0**，不是缺失"
    assert eff["sources"] == []
    assert eff["yield_mult"] == 0.0 and eff["loss_reduction"] == 0.0
    assert eff["transport_relief"] == 0.0
    assert eff["applied_ratio"] == 1.0

    p = s.prefectures[r]
    g0, w0 = p["pops"]["农"]["grain"], p["pops"]["农"]["wealth"]
    summ = A.apply_agri_effects(s, [], month=3)
    assert summ["routes"][r]["sources"] == 0
    assert p["pops"]["农"]["grain"] == g0
    assert p["pops"]["农"]["wealth"] == w0
    assert float(s.statistics.get("agri_grain_produced", 0) or 0) == 0.0


def test_unregistered_agri_looking_building_is_reported_not_ignored():
    """农业外观但**未登记**的建筑 → 进 `unregistered`（可诊断），不产生效果。"""
    s = _state_no_agri()
    r = _route(s)
    s.prefectures[r].setdefault("buildings", {})["农具坊"] = 2
    eff = A.route_agri_effect(s, r)
    assert eff["defined"] is True
    assert eff["yield_mult"] == 0.0
    assert any("农具坊" in u for u in eff["unregistered"]), eff["unregistered"]


def test_project_and_building_same_effect_are_not_double_counted():
    """同一效果既有路级建筑又有工程 → 只计一次（工程进 `duplicates`）。"""
    s = _state_no_agri()
    r = _route(s)
    _invest(s, r, "肥料局", 1)
    s.projects["p1"] = {
        "name": "肥料局", "blueprint_key": "C4_fertilizer", "route": r,
        "status": "operating", "capacity": 1.0, "levels": 2,
    }
    eff = A.route_agri_effect(s, r)
    assert len(eff["sources"]) == 1, f"重复计入：{eff['sources']}"
    assert eff["sources"][0]["source"] == "building"
    assert any("p1" in d for d in eff["duplicates"]), eff["duplicates"]


def test_operating_project_without_registered_key_contributes_nothing():
    s = _state_no_agri()
    r = _route(s)
    s.projects["p2"] = {"name": "官署", "route": r, "status": "operating",
                         "capacity": 1.0, "levels": 1}
    eff = A.route_agri_effect(s, r)
    assert eff["yield_mult"] == 0.0 and eff["sources"] == []


# =============================================================================
# 3 · 守恒：材料 / 工资 / 土地 / 粮食 / 钱
# =============================================================================

def test_materials_are_really_deducted_and_land_is_a_pure_transfer():
    s = _state_no_agri()
    r = _route(s)
    _invest(s, r, "水利", 1, stock=100_000)
    reg = A.AGRI_UPGRADE_EFFECTS["水利"]

    mat_before = _res_total(s)
    land_before = _land_total(s)
    waste_before = s.land["wasteland"]
    p_land_before = s.prefectures[r]["land"]

    A.apply_agri_effects(s, [], month=3)

    used = sum(reg["material_per_lv"].values())
    assert _res_total(s) == pytest.approx(mat_before - used), "材料未真扣"
    assert s.land["wasteland"] == waste_before - reg["land_per_lv"]
    assert s.prefectures[r]["land"] == p_land_before + reg["land_per_lv"]
    assert _land_total(s) == land_before, "土地必须只是转移，不得凭空增加"
    assert float(s.statistics["agri_material_used_timber"]) == \
        pytest.approx(float(reg["material_per_lv"]["timber"]))


def test_money_is_conserved_upkeep_goes_to_real_artisans_and_merchants():
    s = _state_no_agri()
    r = _route(s)
    _invest(s, r, "农田", 1)                 # incremental 维护费
    p = s.prefectures[r]
    art0 = p["pops"]["工匠"]["wealth"]
    mer0 = p["pops"]["商人"]["wealth"]
    tre0 = s.treasury
    total0 = _money_total(s)

    summ = A.apply_agri_effects(s, [], month=3)

    paid = summ["upkeep_paid"]
    assert paid > 0, "增量维护费未实付"
    assert s.treasury == tre0 - paid
    assert p["pops"]["工匠"]["wealth"] + p["pops"]["商人"]["wealth"] - (art0 + mer0) == paid
    assert _money_total(s) == pytest.approx(total0), "钱账不守恒"


def test_labor_is_recorded_but_no_pop_is_created_or_removed():
    s = _state_no_agri()
    r = _route(s)
    _invest(s, r, "水利", 1)
    size0 = _pop_total(s)
    summ = A.apply_agri_effects(s, [], month=3)
    assert summ["labor_hours"] > 0, "劳务成本未消耗"
    assert float(s.statistics["agri_labor_hours"]) == pytest.approx(summ["labor_hours"])
    assert _pop_total(s) == size0, "本模块不得新增/转移任何 POP 人口"


def test_grain_delta_equals_registered_production_only():
    s = _state_no_agri()
    r = _route(s)
    _invest(s, r, "水利", 1)
    before = _grain_total(s)
    summ = A.apply_agri_effects(s, [], month=3)
    assert _grain_total(s) - before == pytest.approx(float(summ["grain_produced"]))


def test_cost_shortfall_degrades_proportionally_and_never_free():
    """料不足 ⇒ 按最短板降效；产出随比例缩，**不出现零成本增产**。"""
    s = _state_no_agri()
    r = _route(s)
    s.prefectures[r].setdefault("buildings", {})["水利"] = 1
    _stock(s, "timber", 30, route=r)           # 需 60 timber ⇒ 料只有一半
    _stock(s, "stone", 40, route=r)
    s.treasury = 10_000_000

    eff = A.route_agri_effect(s, r)
    assert eff["cover"]["material"] == pytest.approx(0.5)
    assert eff["applied_ratio"] == pytest.approx(0.5)

    reg = A.AGRI_UPGRADE_EFFECTS["水利"]
    annual = int(s.prefectures[r]["grain"])
    full = int(round(annual * reg["yield_mult"] * A.AGRI_HARVEST_SHARE))
    half = int(round(annual * reg["yield_mult"] * 0.5 * A.AGRI_HARVEST_SHARE))
    summ = A.apply_agri_effects(s, [], month=3)
    assert summ["grain_produced"] == half < full
    assert summ["lost_ratio"] > 0


def test_no_materials_no_output_at_all():
    s = _state_no_agri()
    r = _route(s)
    s.prefectures[r].setdefault("buildings", {})["水利"] = 1
    _stock(s, "timber", 0, route=r)
    _stock(s, "stone", 0, route=r)
    eff = A.route_agri_effect(s, r)
    assert eff["applied_ratio"] == 0.0
    summ = A.apply_agri_effects(s, [], month=3)
    assert summ["grain_produced"] == 0


def test_money_audit_residual_stays_zero_over_seasons():
    """钱账守恒的全局口径：跑 12 月后货币对账残差仍为 0。"""
    random.seed(31337)
    s = _state_no_agri()
    r = _route(s)
    s.prefectures[r].setdefault("buildings", {})["农田"] = 2
    for _ in range(12):
        s.treasury = max(s.treasury, 20_000_000)
        _stock(s, "timber", 50_000)
        A.apply_agri_effects(s, [], month=s.month)
        random.seed(7000 + _)
        S.run_monthly_settlement(s)
    assert float((s.money_audit or {}).get("residual", 0) or 0) == 0.0


# =============================================================================
# 4 · POP 挂载律：收入归真实主体、财富变化必有对手方
# =============================================================================

def test_module_never_writes_pop_wealth_directly():
    """本模块只增粮、只付维护费；**任何 POP wealth 的变化都来自维护费转移**。"""
    s = _state_no_agri()
    r = _route(s)
    _invest(s, r, "农田", 1)

    def snapshot():
        return {(route, cls): float(pop.get("wealth", 0) or 0)
                for route, p in s.prefectures.items()
                for cls, pop in p["pops"].items()}

    before = snapshot()
    summ = A.apply_agri_effects(s, [], month=3)
    after = snapshot()
    delta = sum(after[k] - before[k] for k in after)
    assert summ["upkeep_paid"] > 0
    assert delta == pytest.approx(summ["upkeep_paid"]), \
        "POP wealth 的净变化必须等于维护费实付（其余来源只能是粮市/财政既有通道）"


def test_farmer_wealth_gain_has_a_counterparty():
    """农户因售粮得到的财富，同额来自买粮 POP 的财富减少（钱粮双向）。"""
    s = _state_no_agri()
    r = _route(s)
    p = _micro_route(s, r)
    _invest(s, r, "水利", 1)
    before = {k: float(v.get("wealth", 0) or 0) for k, v in p["pops"].items()}
    A.apply_agri_effects(s, [], month=3)
    random.seed(5)
    _settle_granary(s, [])
    after = {k: float(v.get("wealth", 0) or 0) for k, v in p["pops"].items()}
    assert after["农"] > before["农"], "农户售粮未获收入"
    buyers = sum(after[k] - before[k] for k in after if k != "农")
    assert buyers < 0, "农户收入必须有出钱的对手方"
    assert (after["农"] - before["农"]) + buyers == pytest.approx(0.0, abs=2.0)


# =============================================================================
# 5 · 非法输入：拒绝式处理
# =============================================================================

def test_illegal_route_argument_raises():
    s = _state_no_agri()
    with pytest.raises(ValueError):
        A.route_agri_effect(s, "")
    with pytest.raises(ValueError):
        A.route_agri_effect(s, 123)
    with pytest.raises(ValueError):
        A.route_agri_effect(s, None)
    with pytest.raises(TypeError):
        A.route_agri_effect(None, "京畿路")


def test_uninitialised_state_raises():
    class _Bad:
        prefectures = None

    with pytest.raises(ValueError):
        A.route_agri_effect(_Bad(), "京畿路")
    with pytest.raises(ValueError):
        A.apply_agri_effects(_Bad(), [])

    class _Bad2:
        prefectures = ["不是 dict"]

    with pytest.raises(TypeError):
        A.apply_agri_effects(_Bad2(), [])


def test_register_rejects_illegal_entries():
    base = {"sources": ("building",), "maintenance_mode": "asset_maintenance",
            "upkeep_per_lv": 0, "yield_mult": 0.1}
    with pytest.raises(A.AgriUpgradeError):      # asset_maintenance 却带运维费 → 重复收费
        A.register_agri_upgrade("坏条目A", dict(base, upkeep_per_lv=100))
    with pytest.raises(A.AgriUpgradeError):      # NaN 不得回落 0/1.0
        A.register_agri_upgrade("坏条目B", dict(base, yield_mult=float("nan")))
    with pytest.raises(A.AgriUpgradeError):      # inf
        A.register_agri_upgrade("坏条目C", dict(base, yield_mult=float("inf")))
    with pytest.raises(A.AgriUpgradeError):      # 负值
        A.register_agri_upgrade("坏条目D", dict(base, land_per_lv=-1))
    with pytest.raises(A.AgriUpgradeError):      # 未知通道
        A.register_agri_upgrade("坏条目E", dict(base, sources=("magic",)))
    with pytest.raises(A.AgriUpgradeError):      # 非法维护模式
        A.register_agri_upgrade("坏条目F", dict(base, maintenance_mode="白嫖"))
    with pytest.raises(A.AgriUpgradeError):      # tech 通道缺部署路径（无法归属到路）
        A.register_agri_upgrade("坏条目G",
                                dict(base, sources=("tech",), tech_node="X"))
    with pytest.raises(A.AgriUpgradeError):      # 非数值
        A.register_agri_upgrade("坏条目H", dict(base, yield_mult="很高"))
    with pytest.raises(A.AgriUpgradeError):      # 空键
        A.register_agri_upgrade("  ", dict(base))
    for k in ("坏条目A", "坏条目B", "坏条目C", "坏条目D", "坏条目E",
              "坏条目F", "坏条目G", "坏条目H"):
        assert k not in A.AGRI_UPGRADE_EFFECTS, f"非法条目被写入注册表：{k}"


def test_register_accepts_valid_dynamic_blueprint():
    """B4/B5 新蓝图行动的注册入口：合法条目可注册、可被读数消费。"""
    s = _state_no_agri()
    r = _route(s)
    try:
        A.register_agri_upgrade("陂塘", {
            "label": "陂塘", "category": "irrigation", "sources": ("building",),
            "yield_mult": 0.04, "loss_reduction": 0.02, "transport_relief": 0.0,
            "land_per_lv": 1_000, "material_per_lv": {"timber": 50},
            "labor_per_lv": 30.0,
            "maintenance_mode": "asset_maintenance", "upkeep_per_lv": 0,
        })
        _invest(s, r, "陂塘", 1)
        eff = A.route_agri_effect(s, r)
        assert eff["yield_mult"] == pytest.approx(0.04)
    finally:
        A.AGRI_UPGRADE_EFFECTS.pop("陂塘", None)
        A._invalidate_alias_index()
    assert A.resolve_agri_upgrade("陂塘") is None


def test_shipped_registry_entries_are_self_consistent():
    """出厂注册表自身合法（asset_maintenance 条目不得带 upkeep，避免与维持费重复收费）。"""
    for key, entry in A.AGRI_UPGRADE_EFFECTS.items():
        A._validate_entry(key, entry)
        assert entry["maintenance_mode"] in A.AGRI_MAINTENANCE_MODES
        if entry["maintenance_mode"] == "asset_maintenance":
            assert float(entry.get("upkeep_per_lv", 0)) == 0.0


# =============================================================================
# 6 · 缺失 ≠ 0 ≠ 1.0
# =============================================================================

def test_unknown_route_is_undefined_with_none_effects():
    s = _state_no_agri()
    eff = A.route_agri_effect(s, "不存在的路")
    assert eff["defined"] is False
    assert eff["reason"] == "unknown_route"
    for f in ("yield_mult", "loss_reduction", "transport_relief", "applied_ratio",
              "annual_grain", "upkeep_coin", "material"):
        assert eff[f] is None, f"{f} 缺失时应为 None，不得回落 0"


def test_missing_grain_baseline_is_undefined_not_zero():
    s = _state_no_agri()
    r = _route(s)
    s.prefectures[r]["buildings"]["水利"] = 1
    del s.prefectures[r]["grain"]
    eff = A.route_agri_effect(s, r)
    assert eff["defined"] is False
    assert eff["reason"] == "no_route_grain_baseline"
    assert eff["yield_mult"] is None


def test_non_finite_grain_baseline_treated_as_missing():
    s = _state_no_agri()
    r = _route(s)
    s.prefectures[r]["buildings"]["水利"] = 1
    s.prefectures[r]["grain"] = float("nan")
    eff = A.route_agri_effect(s, r)
    assert eff["defined"] is False
    assert eff["reason"] == "no_route_grain_baseline"


def test_missing_farmer_pop_is_undefined():
    s = _state_no_agri()
    r = _route(s)
    s.prefectures[r]["pops"].pop("农")
    eff = A.route_agri_effect(s, r)
    assert eff["defined"] is False
    assert eff["reason"] == "no_farmer_pop"


def test_missing_buildings_key_is_recorded_as_missing_not_zero_investment():
    """`buildings` 键整体缺失 ⇒ 记为**缺失**（不当"零投资"）；其它载体仍可读时读数照常定义。"""
    s = _state_no_agri()
    r = _route(s)
    s.projects["p4"] = {"name": "肥料局", "blueprint_key": "C4_fertilizer",
                        "route": r, "status": "operating", "capacity": 1.0,
                        "levels": 1}
    _stock(s, "timber", 50_000)
    del s.prefectures[r]["buildings"]
    eff = A.route_agri_effect(s, r)
    assert "route_buildings_missing" in eff["missing"]
    assert eff["defined"] is True          # 工程载体仍可读
    assert eff["yield_mult"] == pytest.approx(
        A.AGRI_UPGRADE_EFFECTS["肥料局"]["yield_mult"])


def test_only_missing_carriers_means_effect_is_undefined_not_zero():
    """所有载体读数都缺 ⇒ 效果 `None`（不可判定），**不得回落 0.0 假装"无投资"**。"""
    s = _state_no_agri()
    r = _route(s)
    del s.prefectures[r]["buildings"]
    s.projects = None
    eff = A.route_agri_effect(s, r)
    assert eff["defined"] is False
    assert eff["reason"] in ("no_readable_carriers", "all_investment_levels_missing")
    assert eff["yield_mult"] is None


def test_project_missing_capacity_is_not_defaulted_to_one():
    """工程 `capacity` 缺失 ⇒ 不回落 1.0：效果判为**不可判定**（`None`），并留痕。"""
    s = _state_no_agri()
    r = _route(s)
    s.projects["p3"] = {"name": "肥料局", "blueprint_key": "C4_fertilizer",
                        "route": r, "status": "operating", "levels": 2}
    _stock(s, "timber", 50_000)
    eff = A.route_agri_effect(s, r)
    assert any("capacity_missing" in m for m in eff["missing"]), eff["missing"]
    assert eff["sources"] == []
    assert eff["defined"] is False
    assert eff["yield_mult"] is None, "不得回落成 0.0（那会把『读不到』说成『无效果』）"


def test_project_capacity_one_is_read_as_measured_value_not_default():
    """`capacity=1.0` 是**实测值**：与缺失语义不同，效果照常计入。"""
    s = _state_no_agri()
    r = _route(s)
    s.projects["p3"] = {"name": "肥料局", "blueprint_key": "C4_fertilizer",
                        "route": r, "status": "operating", "capacity": 1.0,
                        "levels": 2}
    _stock(s, "timber", 50_000)
    eff = A.route_agri_effect(s, r)
    assert eff["defined"] is True
    assert eff["yield_mult"] == pytest.approx(
        A.AGRI_UPGRADE_EFFECTS["肥料局"]["yield_mult"] * 2)


def test_all_carriers_unreadable_means_undefined():
    class _S:
        prefectures = {"甲路": {"grain": 1000,
                                "pops": {"农": {"size": 1, "grain": 1000}}}}
    s = _S()
    s.land = {"wasteland": 0}
    s.resources = {}
    s.statistics = {}
    eff = A.route_agri_effect(s, "甲路")
    assert eff["defined"] is False
    assert eff["reason"] == "no_readable_carriers"
    assert eff["yield_mult"] is None


def test_missing_route_land_baseline_blocks_land_transfer():
    """旧档缺 `p["land"]` ⇒ 土地成本到位率 0（宁可不产，也不凭空增在册田亩）。"""
    s = _state_no_agri()
    r = _route(s)
    _invest(s, r, "水利", 1)
    del s.prefectures[r]["land"]
    eff = A.route_agri_effect(s, r)
    assert eff["cover"]["land"] == 0.0
    assert eff["applied_ratio"] == 0.0
    summ = A.apply_agri_effects(s, [], month=3)
    assert summ["grain_produced"] == 0
    assert summ["land_cultivated"] == 0


def test_missing_wasteland_pool_blocks_land_transfer():
    s = _state_no_agri()
    r = _route(s)
    _invest(s, r, "水利", 1)
    del s.land["wasteland"]
    eff = A.route_agri_effect(s, r)
    assert eff["cover"]["land"] == 0.0
    assert A.apply_agri_effects(s, [], month=3)["land_cultivated"] == 0


# =============================================================================
# 7 · 钩子：损耗降低 / 运输瓶颈缓解（Lead 接线用）
# =============================================================================

def test_spoil_rate_hook_lowers_loss_and_never_zeroes_it():
    s = _state_no_agri()
    r = _route(s)
    base = 0.02
    assert A.effective_spoil_rate(s, r, base) == pytest.approx(base)   # 无投资
    _invest(s, r, "常平仓", 2)
    got = A.effective_spoil_rate(s, r, base)
    assert got < base, "常平仓未降低损耗"
    assert got > 0.0, "损耗不得被归零（归零＝删掉既有消耗口径）"
    assert got == pytest.approx(base * (1 - 0.03 * 2))


def test_spoil_rate_hook_returns_none_on_missing_reading():
    s = _state_no_agri()
    r = _route(s)
    assert A.effective_spoil_rate(s, "不存在的路", 0.02) is None
    assert A.effective_spoil_rate(s, r, None) is None
    assert A.effective_spoil_rate(s, r, float("nan")) is None


def test_canal_block_hook_relieves_bottleneck_with_cap():
    s = _state_no_agri()
    s.canal_block = 60
    for r in s.prefectures:
        _invest(s, r, "水利", 5)
    got = A.effective_canal_block(s)
    assert got < 60.0, "农业投资未缓解漕运瓶颈"
    assert got >= 60.0 - A.AGRI_TRANSPORT_RELIEF_CAP, "缓解量须受封顶"
    # 缓解量不得把淤塞度压成负数
    assert A.effective_canal_block(s, 10.0) == 0.0


def test_canal_block_hook_returns_none_when_base_missing():
    s = _state_no_agri()
    s.canal_block = None
    assert A.effective_canal_block(s) is None


# =============================================================================
# 8 · 科技通道：路级归属必须有部署依据（不臆造归属）
# =============================================================================

def test_tech_node_scales_by_adoption_and_route_deployment():
    s = _state_no_agri()
    r = _route(s)
    entry = A.AGRI_UPGRADE_EFFECTS["水排筒车"]
    s.prefectures[r].setdefault("buildings", {})[entry["deploy_building"]] = 2
    _stock(s, "timber", 50_000)
    s.tech.setdefault("unlocked", [])
    if entry["tech_node"] not in s.tech["unlocked"]:
        s.tech["unlocked"].append(entry["tech_node"])
    s.tech.setdefault("assets", {})[entry["tech_node"]] = {"adoption": 0.5}

    eff = A.route_agri_effect(s, r)
    src = [x for x in eff["sources"] if x["source"] == "tech"]
    assert src, "科技通道未生效"
    assert src[0]["lv"] == pytest.approx(1.0)          # 2 级 × 0.5 adoption
    assert eff["yield_mult"] == pytest.approx(entry["yield_mult"] * 1.0)


def test_tech_node_without_route_deployment_has_no_route_attribution():
    """全国 adoption ≠ 该路得利；无部署建筑 ⇒ **不臆造路级归属**。"""
    s = _state_no_agri()
    r = _route(s)
    entry = A.AGRI_UPGRADE_EFFECTS["水排筒车"]
    s.tech.setdefault("assets", {})[entry["tech_node"]] = {"adoption": 1.0}
    eff = A.route_agri_effect(s, r)
    assert not [x for x in eff["sources"] if x["source"] == "tech"]
    assert eff["yield_mult"] == 0.0


def test_tech_node_missing_adoption_is_recorded_not_defaulted():
    s = _state_no_agri()
    r = _route(s)
    entry = A.AGRI_UPGRADE_EFFECTS["水排筒车"]
    s.prefectures[r].setdefault("buildings", {})[entry["deploy_building"]] = 1
    s.tech.setdefault("assets", {})[entry["tech_node"]] = {}      # adoption 缺失
    eff = A.route_agri_effect(s, r)
    assert any("adoption_missing" in m for m in eff["missing"]), eff["missing"]
    assert not [x for x in eff["sources"] if x["source"] == "tech"]


# =============================================================================
# 9 · 接线断言（接线已完成，此处由临时守卫转为**永久**回归）
# =============================================================================

def test_agri_effects_is_wired_into_settlement_pipeline():
    """`settlement.py` 已调用 `apply_agri_effects`。

    原为临时守卫 `test_NOT_YET_wired_into_settlement_pipeline`（接线前必过、接线后必败），
    Lead 完成统一接线后已删除；此处改为**永久**断言，防止后续误删接线。
    """
    import inspect
    import core.settlement as mod
    src = inspect.getsource(mod)
    assert "apply_agri_effects" in src, "农业效果接线被误删"


def test_agri_hooks_are_wired_into_granary():
    """两个钩子（霉耗率/ 漕运阻断）已接进 `settlement_granary`。

    缺任一钩子，`loss_reduction` / `transport_relief` 只是注册表里的声明。
    """
    import inspect
    import core.settlement_granary as mod
    src = inspect.getsource(mod)
    assert "effective_spoil_rate" in src, "霉耗钩子未接线"
    assert "effective_canal_block" in src, "漕运钩子未接线"


def test_export_policy_is_wired_into_granary():
    """R6 外销已换单点（`export_decision`），不再就地 `_cap`/`min` 重复口径。"""
    import inspect
    import core.settlement_granary as mod
    src = inspect.getsource(mod)
    assert "export_decision" in src, "外销未换单点"
    assert "EXPORT_STOCK_MONTHS" not in src, "外销仍在结算层复制库存上限口径"
