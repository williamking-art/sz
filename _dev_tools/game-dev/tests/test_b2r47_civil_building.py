# -*- coding: utf-8 -*-
"""B4-7 · 民间营造触发的定向回归（规格 `market-civilian-economy` B4-7）。

锁定九件事：

1. **三态判定**：该建 / 不该建（实测）/ 未定义（依据读不到），三者互不混淆；
2. **四动因可读**：人口 / 拥挤 / 损坏 / 经营扩张各自贡献多少级数、判据可诊断；
3. **钱货守恒**：建造前后 `ΣPOP wealth + 国库 + 内帑` **逐文相等**（凭空建房必失败）；
4. **料真扣且无料不建房**：真扣**本路商人货栈** `pops["商人"]["goods"][dim]`（E-1），缺料时**分文不动**；
5. **无钱不建房 / 无工时不建房**：出资池不足 ⇒ 零写入；
6. **不新建人口**：全程 ΣPOP `size` 逐类不变（工时只进 `statistics`）；
7. **读数是纯派生**：`route_civil_trigger` 不改任何 state（逐槽位快照比对）；
8. **容忍开局既有 `水利`/`常平仓`**：非注册表键不被误读、不被覆盖、不被要求补字段；
9. **拒绝式**：非法入参 `TypeError`/`ValueError`，非法注册条目 `CivilRegistryError`，
   且 `undefined` 的动因值一律 `None`（**不回落 0/1.0**）。

接线说明：本模块**尚未接线**到 `settlement.py`（由 Lead 统一接线），
接入位置见 `civil_building.WIRING_HINT`。
"""
import copy
import math
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import civil_building as C                        # noqa: E402
from core.building_jobs import building_level                # noqa: E402
from core.game_state import GameState                       # noqa: E402
from core.legacy_mechanic import init_legacies                # noqa: E402
from core.material_holding import (MATERIAL_DIMS, goods_amount,       # noqa: E402
                                supply_merchant_materials)
from core.production_chain import settle_production_chain     # noqa: E402
from content.data_constants import POP_BUILDING_TYPES        # noqa: E402


# =============================================================================
# 夹具与工具
# =============================================================================

def _state():
    """全新开局（确定性：不跑结算）。

    ⚠️ 开局 `buildings` **不是空**——`game_state._init_agri_buildings` 已给每路配
    `水利`/`常平仓`（资产类、无岗位、无科技绑定）。用例必须容忍这两个既有键。
    建材仓由 `settle_production_chain` 补满（否则 timber/stone 开局为 0，
    永远走"缺料"分支，测不到建成路径）。

    🔴 **口径 C-c（2026-10-02）**：营造**只从本地州府仓取料**，故还须
    `supply_merchant_materials()` 把仓里的料**搬进商人货栈**——这正是真实结算流水线
    Step 4.45 所做的事（`settlement.py`）。手工夹具不跑流水线，必须显式补上，
    否则一律走"缺料"分支。
    """
    s = GameState("史实")
    init_legacies(s)
    settle_production_chain(s, [])
    # 6.33：未裁定维（含木石）落**归属待定槽**，不得采购；
    # 故显式准备**已确权、可用的库存**，供营造/农事用例使用。
    for _d in ("木", "石"):
        _sl = s.resources.setdefault(_d, {"stock": 0, "cap": 50_000})
        if int(_sl.get("stock", 0) or 0) <= 0:
            _sl["stock"] = 10_000
    supply_merchant_materials(s)
    return s


def _pref(s, idx=0):
    return list(s.prefectures)[idx]


def _lv(s, pref, name):
    """建筑等级统一读口（兼容标量 / {"lv": n} 两种既存写法）。"""
    return building_level(s.prefectures[pref]["buildings"].get(name), 0)


def _money_total(s):
    """Σ钱：国库 + 内帑 + 全部路 POP `wealth`。本模块**不得改变**它。"""
    total = float(getattr(s, "treasury", 0) or 0) + \
        float(getattr(s, "imperial_treasury", 0) or 0)
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                total += float(pop.get("wealth", 0) or 0)
    return total


def _pop_sizes(s, pref):
    """该路六类 POP `size`（逐类），用于"不新建人口"断言。"""
    return {cls: int(pop.get("size", 0) or 0)
            for cls, pop in (s.prefectures[pref].get("pops") or {}).items()
            if isinstance(pop, dict)}


def _stock(s, dim, qty, pref=None):
    """给某路备料（国家仓口径）。

    ⚠️ 2026-11 变更回退：曾试把料改放**商人 `goods`**（B4-1 收窄版 B），
    但该方案未收敛已回退（见 tasks.md），故恢复"料在国家仓"的既有口径。
    `pref` 参数保留为无用占位，避免调用方签名不兼容。
    """
    s.resources.setdefault(dim, {"stock": 0, "cap": 50_000})["stock"] = int(qty)


def _rich(s, pref, classes=("士绅", "商人", "工匠", "农")):
    """给该路若干阶层塞钱（保证只被"料/工时"卡住，不被钱卡住）。"""
    for cls in classes:
        s.prefectures[pref]["pops"][cls]["wealth"] = 10_000_000


def _set_mat(s, pref, dim, qty):
    """设定本路商人货栈的建材**总量**（E-1：建材是商品，料在这里）。

    🔴 2026-10-03：建材按 `goods[治所][dim]` 州府桶存放，故须**先清该维全部桶**
    再写扁平项——否则「设为 0」并不真的无料（真实库存仍留在桶里）。
    """
    g = s.prefectures[pref]["pops"]["商人"]["goods"]
    for k in [k for k in g if "|" in k and isinstance(g.get(k), dict)]:
        g[k].pop(dim, None)
    g[dim] = int(qty)


@pytest.fixture
def s():
    return _state()


@pytest.fixture(autouse=True)
def _registry_guard():
    """用例若临时注册建筑，退出时恢复注册表（不污染其他用例）。"""
    snapshot = dict(C.CIVIL_BUILDING_SPECS)
    yield
    C.CIVIL_BUILDING_SPECS.clear()
    C.CIVIL_BUILDING_SPECS.update(snapshot)


# =============================================================================
# 1 · 注册表与岗位类纪律
# =============================================================================

def test_registry_has_three_civil_buildings():
    assert set(C.CIVIL_BUILDING_SPECS) >= {"民居", "货栈", "商铺"}


def test_non_job_buildings_are_marked(s):
    """民居/货栈是**非岗位类**：不进 `POP_BUILDING_TYPES`，不改就业基线。"""
    for name in ("民居", "货栈"):
        assert C.CIVIL_BUILDING_SPECS[name]["job_class"] is False
        assert name not in POP_BUILDING_TYPES


def test_shop_is_job_class_and_written_as_scalar():
    """商铺属 `POP_BUILDING_TYPES`（每级 40 商人岗）⇒ 必须标 job_class 且只写标量。"""
    spec = C.CIVIL_BUILDING_SPECS["商铺"]
    assert "商铺" in POP_BUILDING_TYPES
    assert spec["job_class"] is True
    assert spec["write_form"] == "scalar"


def test_abs_month_index_is_monotone_across_years(s):
    s.year, s.month = 1101, 12
    a = C.abs_month_index(s)
    s.year, s.month = 1102, 1
    assert C.abs_month_index(s) == a + 1
    s.month = None
    assert C.abs_month_index(s) is None          # 缺失 → None，不回落 0


# =============================================================================
# 2 · 三态：该建
# =============================================================================

def test_trigger_says_build(s):
    pref = _pref(s)
    t = C.route_civil_trigger(s, pref, "民居")
    assert t["defined"] is True
    assert t["decision"] == "build"
    assert t["reason"] == "pressure"
    assert t["need_lv"] > t["current_lv"] == 0


def test_trigger_reports_all_four_drivers_with_basis(s):
    """四动因**各自贡献多少**（级数）+ 可诊断判据，一个都不少。"""
    pref = _pref(s)
    t = C.route_civil_trigger(s, pref, "民居")
    assert set(t["drivers"]) == set(C.CIVIL_DRIVERS)
    for d in C.CIVIL_DRIVERS:
        assert isinstance(t["drivers"][d], float)
        assert math.isfinite(t["drivers"][d])
        assert t["driver_basis"][d]
    assert t["pressure"] == pytest.approx(sum(t["drivers"].values()), rel=1e-3)


def test_population_and_crowding_dominate_for_dwellings(s):
    """民居：人口增长与拥挤是居住类主驱动；两者皆由 POP `size` 派生。"""
    pref = _pref(s)
    t = C.route_civil_trigger(s, pref, "民居")
    assert t["drivers"]["population"] > 0
    assert t["drivers"]["crowding"] > 0
    assert t["applicable"]["population"] and t["applicable"]["crowding"]
    assert t["population"] == sum(_pop_sizes(s, pref).values())


def test_non_residential_ignores_population_and_crowding(s):
    """货栈不居住人口 ⇒ 人口/拥挤动因**不适用**（0.0 + applicable=False），不臆造。"""
    pref = _pref(s)
    t = C.route_civil_trigger(s, pref, "货栈")
    assert t["drivers"]["population"] == 0.0
    assert t["drivers"]["crowding"] == 0.0
    assert t["applicable"]["population"] is False
    assert t["applicable"]["crowding"] is False


def test_expansion_driver_follows_merchant_wealth(s):
    """经营扩张：读本路商人 `wealth`（既有 POP 槽位，不另立账本）。"""
    pref = _pref(s)
    spec = C.CIVIL_BUILDING_SPECS["货栈"]
    s.prefectures[pref]["pops"]["商人"]["wealth"] = spec["expansion_wealth_per_lv"] * 2
    t = C.route_civil_trigger(s, pref, "货栈")
    assert t["drivers"]["expansion"] == pytest.approx(2.0)


def test_decay_driver_grows_with_age(s):
    """损坏：年久失修 —— 每满一个失修周期才欠一级重修账。"""
    pref = _pref(s)
    spec = C.CIVIL_BUILDING_SPECS["民居"]
    s.prefectures[pref]["buildings"]["民居"] = {
        "lv": 1, "built_month": C.abs_month_index(s)}
    assert C.route_civil_trigger(s, pref, "民居")["drivers"]["decay"] == 0.0
    s.year += 1                                   # 12 月后仍不足一个周期(120 月)
    assert C.route_civil_trigger(s, pref, "民居")["drivers"]["decay"] == 0.0
    s.year += 30                                  # 12+360=372 月 ⇒ 372//120 = 3 级
    d = C.route_civil_trigger(s, pref, "民居")["drivers"]["decay"]
    assert d == pytest.approx(372 // spec["decay_cycle_months"])


# =============================================================================
# 3 · 三态：不该建（实测事实）
# =============================================================================

def test_no_build_when_level_capped(s):
    """等级封顶是**实测**状态 ⇒ `no_build`，不是缺失。"""
    pref = _pref(s)
    spec = C.CIVIL_BUILDING_SPECS["民居"]
    s.prefectures[pref]["buildings"]["民居"] = {"lv": spec["level_cap"],
                                                 "built_month": C.abs_month_index(s)}
    t = C.route_civil_trigger(s, pref, "民居")
    assert t["decision"] == "no_build"
    assert t["reason"] == "at_level_cap"
    assert t["at_level_cap"] is True


def test_no_build_when_no_pressure(s):
    """无营造压力：货栈的扩张动因为 0（商人财富不足）⇒ 不建。"""
    pref = _pref(s)
    s.prefectures[pref]["pops"]["商人"]["wealth"] = 0
    t = C.route_civil_trigger(s, pref, "货栈")
    assert t["decision"] == "no_build"
    assert t["reason"] == "no_pressure"
    assert t["pressure"] == 0.0


def test_no_build_when_material_short(s):
    """缺料是**实测**事实（仓里确实只有 0 根木）⇒ 不建，不是 undefined。"""
    pref = _pref(s)
    _rich(s, pref)
    _stock(s, "木", 0)
    t = C.route_civil_trigger(s, pref, "民居")
    assert t["decision"] == "no_build"
    assert t["reason"] == "material_short"
    assert t["afford"]["materials_ok"] is False
    assert t["afford"]["material_short"]["木"] > 0


def test_no_build_when_coin_short(s):
    """无钱 ⇒ 不建（**不是**凭空建房）。"""
    pref = _pref(s)
    for cls, pop in s.prefectures[pref]["pops"].items():
        pop["wealth"] = 0
    t = C.route_civil_trigger(s, pref, "民居")
    assert t["decision"] == "no_build"
    assert t["reason"] == "coin_short"
    assert t["afford"]["money_ok"] is False
    assert t["afford"]["coin_short"] == t["afford"]["wage"] > 0


def test_no_build_when_labor_short(s):
    """无工匠 ⇒ 无工时 ⇒ 不建（工时不凭空生成）。"""
    pref = _pref(s)
    _rich(s, pref)
    s.prefectures[pref]["pops"]["工匠"]["size"] = 0
    t = C.route_civil_trigger(s, pref, "民居")
    assert t["decision"] == "no_build"
    assert t["reason"] == "labor_short"
    assert t["afford"]["labor_available"] == 0.0


def test_labor_pool_is_shared_within_the_month(s):
    """同路多建筑**共用当月工时池**：已耗尽的池子不再放行下一项。"""
    pref = _pref(s)
    _rich(s, pref)
    from content.data import PROJECT_LABOR_RATIO
    need = float(C.CIVIL_BUILDING_SPECS["民居"]["labor_per_lv"])
    cap = float(s.prefectures[pref]["pops"]["工匠"]["size"]) * float(PROJECT_LABOR_RATIO)
    t = C.route_civil_trigger(s, pref, "民居", labor_used=cap - need + 1)
    assert t["decision"] == "no_build"
    assert t["reason"] == "labor_short"
    assert t["afford"]["labor_consumed_by_others"] == pytest.approx(cap - need + 1)


def test_job_class_not_built_without_opt_in(s):
    """岗位类建筑（商铺）默认**只出读数不写入**，由 Lead 显式开闸。"""
    pref = _pref(s)
    t = C.route_civil_trigger(s, pref, "商铺")
    assert t["decision"] == "no_build"
    assert t["reason"] == "job_class_opt_in_required"
    assert "商铺" not in s.prefectures[pref]["buildings"]


def test_job_class_builds_only_with_opt_in(s):
    pref = _pref(s)
    t = C.route_civil_trigger(s, pref, "商铺", allow_job_class=True)
    assert t["decision"] == "build"
    out = C.build_civil_building(s, pref, "商铺", allow_job_class=True)
    assert out["ok"] is True
    # 标量写法：`estate_mechanic.pop_building_effect` 对 POP_BUILDING_TYPES 做 int(lv)
    assert s.prefectures[pref]["buildings"]["商铺"] == 1
    from core.estate_mechanic import pop_building_effect
    assert pop_building_effect(s.prefectures[pref]["buildings"]) == pytest.approx(1.05)


# =============================================================================
# 4 · 三态：未定义（缺失 ≠ 0 ≠ 1.0）
# =============================================================================

def _assert_undefined(t, reason):
    assert t["defined"] is False
    assert t["decision"] == "undefined"
    assert t["reason"] == reason
    assert t["missing"], "未定义读数必须带可诊断 missing"
    # 缺失 ≠ 0 ≠ 1.0：四动因一律 None
    for d in C.CIVIL_DRIVERS:
        assert t["drivers"][d] is None, f"{d} 回落了数值而不是 None"
    assert t["pressure"] is None
    assert t["need_lv"] is None


def test_unknown_pref_is_undefined(s):
    _assert_undefined(C.route_civil_trigger(s, "不存在的路", "民居"),
                      "unknown_pref")


def test_missing_buildings_slot_is_undefined(s):
    """`buildings` 键缺失 ≠ "该路没有房" ⇒ undefined（否则会把未知当成 0 而凭空造房）。"""
    pref = _pref(s)
    del s.prefectures[pref]["buildings"]
    _assert_undefined(C.route_civil_trigger(s, pref, "民居"),
                      "route_buildings_missing")


def test_missing_pop_size_is_undefined(s):
    pref = _pref(s)
    del s.prefectures[pref]["pops"]["农"]["size"]
    _assert_undefined(C.route_civil_trigger(s, pref, "民居"),
                      "population_missing")


def test_negative_pop_size_is_undefined(s):
    """负值是非法读数 ⇒ undefined，**不**当 0 处理。"""
    pref = _pref(s)
    s.prefectures[pref]["pops"]["农"]["size"] = -1
    _assert_undefined(C.route_civil_trigger(s, pref, "民居"),
                      "population_missing")


def test_missing_built_month_is_undefined(s):
    """已有民居但读不到 `built_month` ⇒ 损坏年限不可判定 ⇒ undefined（不回落 0）。"""
    pref = _pref(s)
    s.prefectures[pref]["buildings"]["民居"] = {"lv": 2}
    t = C.route_civil_trigger(s, pref, "民居")
    _assert_undefined(t, "decay_age_missing")
    assert "building:民居:built_month_missing" in t["missing"]


def test_missing_month_counter_is_undefined(s):
    pref = _pref(s)
    s.prefectures[pref]["buildings"]["民居"] = {"lv": 1, "built_month": 13213}
    s.year = None
    _assert_undefined(C.route_civil_trigger(s, pref, "民居"),
                      "month_counter_missing")


def test_missing_resource_slot_is_undefined(s):
    """仓里**有没有这一维**读不到 ⇒ undefined（否则"未知"会被当成"没有"）。"""
    pref = _pref(s)
    s.resources.pop("木", None)
    _assert_undefined(C.route_civil_trigger(s, pref, "民居"),
                      "material_stock_unknown")


def test_missing_payer_wealth_is_undefined(s):
    pref = _pref(s)
    del s.prefectures[pref]["pops"]["士绅"]["wealth"]
    _assert_undefined(C.route_civil_trigger(s, pref, "民居"),
                      "payer_wealth_unknown")


def test_missing_material_price_is_undefined(s):
    """基准价不可读 ⇒ 造价不可判定 ⇒ undefined（**不**回落成"造价 0 的免费房"）。"""
    pref = _pref(s)
    C.register_civil_building("验价棚", {
        "label": "验价棚", "drivers": ("expansion",),
        "job_class": False, "write_form": "dict",
        "stock_per_lv": {"未定价材": 5},
        "labor_per_lv": 10.0, "wage_per_labor_hour": 1.0,
        "payers": ("士绅",), "level_cap": 3,
        "expansion_metric": "商人", "expansion_wealth_per_lv": 1_000_000,
    })
    t = C.route_civil_trigger(s, pref, "验价棚")
    _assert_undefined(t, "material_price_unresolved")
    assert t["cost"]["missing_price"] == ["未定价材"]


def test_undefined_route_builds_nothing(s):
    """读数未定义 ⇒ `build_civil_building` / `apply_civil_construction` 均零写入。"""
    pref = _pref(s)
    before = copy.deepcopy(s.prefectures[pref])
    money = _money_total(s)
    del s.prefectures[pref]["pops"]["农"]["size"]
    out = C.build_civil_building(s, pref, "民居")
    assert out["ok"] is False
    assert out["reason"] == "population_missing"
    assert _money_total(s) == money
    # 人口读数缺失只影响该路 POP，buildings 未被写
    assert s.prefectures[pref]["buildings"] == before["buildings"]


def test_route_civil_demand_isolates_undefined_per_building(s):
    """逐项隔离：民居未定义不妨碍货栈出读数。"""
    pref = _pref(s)
    s.prefectures[pref]["buildings"]["民居"] = {"lv": 1}
    d = C.route_civil_demand(s, pref)
    assert d["defined"] is True
    assert "民居" in d["undefined"]
    assert d["buildings"]["货栈"]["defined"] is True


# =============================================================================
# 5 · 读数是纯派生
# =============================================================================

def test_trigger_does_not_mutate_state(s):
    pref = _pref(s)
    _rich(s, pref)
    before = {
        "pref": copy.deepcopy(s.prefectures[pref]),
        "res": copy.deepcopy(s.resources),
        "stats": copy.deepcopy(s.statistics),
        "treasury": s.treasury,
        "imperial": s.imperial_treasury,
        "money": _money_total(s),
        "pops": copy.deepcopy(
            {c: dict(p) for c, p in s.prefectures[pref]["pops"].items()}),
    }
    for name in C.CIVIL_BUILDING_SPECS:
        C.route_civil_trigger(s, pref, name)
        C.route_civil_trigger(s, pref, name, allow_job_class=True)
    C.route_civil_demand(s, pref)
    assert s.prefectures[pref] == before["pref"]
    assert s.resources == before["res"]
    assert s.statistics == before["stats"]
    assert s.treasury == before["treasury"]
    assert s.imperial_treasury == before["imperial"]
    assert _money_total(s) == before["money"]
    assert s.prefectures[pref]["pops"] == before["pops"]


# =============================================================================
# 6 · 建成：真实消耗（钱/料/工时）与落点
# =============================================================================

def qty_get(res, dim):
    return int(res.get(dim, 0) or 0)


def _mat_total(s, dim):
    """🔴 全域 Σ 建材（`apply_civil_construction` 遍历**所有路**，
    单路基准会错位，故必须按全域合计比对）。"""
    from core.material_holding import goods_amount, merchant_goods
    return sum(int(goods_amount(merchant_goods(s, r), dim) or 0)
               for r in s.prefectures)


def _mgoods(s, pref):
    """本路**商人 POP `goods`**（E-1：建材是商品，存量在这里）。"""
    return s.prefectures[pref]["pops"]["商人"]["goods"]


def test_build_deducts_materials_for_real(s):
    pref = _pref(s)
    _rich(s, pref)
    spec = C.CIVIL_BUILDING_SPECS["民居"]
    # 🔴 E-1：建材是商品，扣减落在**本路商人货栈**，仓总账不再变动
    from core.material_holding import goods_amount
    before = {d: goods_amount(_mgoods(s, pref), d) or 0 for d in spec["stock_per_lv"]}
    out = C.build_civil_building(s, pref, "民居")
    assert out["ok"] is True
    for dim, qty in spec["stock_per_lv"].items():
        assert goods_amount(_mgoods(s, pref), dim) == before[dim] - qty, \
            f"{dim} 未从本路商人货栈实扣"


def test_build_conserves_money_and_pays_artisans(s):
    """**钱必有付款对手方**：出资阶层 wealth → 本路工匠 wealth，Σ 钱逐文不变。"""
    pref = _pref(s)
    _rich(s, pref)
    money_before = _money_total(s)
    art_before = s.prefectures[pref]["pops"]["工匠"]["wealth"]
    out = C.build_civil_building(s, pref, "民居")
    assert out["ok"] is True
    assert _money_total(s) == money_before, "凭空建房：Σ钱增加"
    assert s.prefectures[pref]["pops"]["工匠"]["wealth"] == \
        art_before + out["coin_paid"]
    assert sum(leg["amount"] for leg in out["coin_legs"]) == out["coin_paid"]


def test_build_without_money_changes_nothing(s):
    """无钱 ⇒ `ok=False`，且**分文不动、料不扣、房不建**。"""
    pref = _pref(s)
    for pop in s.prefectures[pref]["pops"].values():
        pop["wealth"] = 0
    money = _money_total(s)
    res = copy.deepcopy(s.resources)
    blds = copy.deepcopy(s.prefectures[pref]["buildings"])
    out = C.build_civil_building(s, pref, "民居")
    assert out["ok"] is False and out["reason"] == "coin_short"
    assert _money_total(s) == money
    assert s.resources == res
    assert s.prefectures[pref]["buildings"] == blds


def test_build_without_material_changes_nothing(s):
    pref = _pref(s)
    _rich(s, pref)
    # 🔴 E-1：料在**本路商人货栈**（仓总账不再是消费来源）
    _set_mat(s, pref, "木", 10)
    money = _money_total(s)
    blds = copy.deepcopy(s.prefectures[pref]["buildings"])
    out = C.build_civil_building(s, pref, "民居")
    assert out["ok"] is False and out["reason"] == "material_short"
    assert _money_total(s) == money, "缺料时不得先付工钱"
    assert goods_amount(_mgoods(s, pref), "木") == 10, "缺料时不得先扣料"
    assert s.prefectures[pref]["buildings"] == blds


def test_build_never_creates_population(s):
    """工时只进 statistics：**绝不新建人口**。"""
    pref = _pref(s)
    _rich(s, pref)
    before = _pop_sizes(s, pref)
    out = C.build_civil_building(s, pref, "民居")
    assert out["ok"] is True
    assert _pop_sizes(s, pref) == before
    assert out["labor_hours"] > 0
    assert s.statistics["civil_labor_hours"] == pytest.approx(out["labor_hours"])


def test_build_writes_existing_slot_and_keeps_agri_buildings(s):
    """落点是既有 `buildings` 槽位；开局 `水利`/`常平仓` **原样保留**。"""
    pref = _pref(s)
    _rich(s, pref)
    before = copy.deepcopy(s.prefectures[pref]["buildings"])
    assert "水利" in before and "常平仓" in before
    out = C.build_civil_building(s, pref, "民居")
    assert out["ok"] is True
    blds = s.prefectures[pref]["buildings"]
    assert blds["水利"] == before["水利"]
    assert blds["常平仓"] == before["常平仓"]
    assert blds["民居"] == {"lv": 1, "built_month": C.abs_month_index(s)}
    # 统一读口兼容结构写法
    assert _lv(s, pref, "民居") == 1
    # 未登记的既有键不出现在读数的缺失诊断里（不被误判成缺口）
    t = C.route_civil_trigger(s, pref, "民居")
    assert t["missing"] == []


def test_existing_agri_buildings_alone_do_not_make_pressure(s):
    """开局 `水利`/`常平仓` 不是民间建筑 ⇒ 不参与拥挤容量、不被要求补字段。"""
    pref = _pref(s)
    t = C.route_civil_trigger(s, pref, "民居")
    assert t["defined"] is True
    assert t["capacity"] == 0
    assert t["missing"] == []


def test_civil_buildings_feed_existing_upkeep_channel(s):
    """新增的民居/货栈走**既有**资产维持费通道（`POP_BUILDING_VALUE × level`），
    不是新账本；且结构写法不得让 `_settle_upkeep` 崩（它用统一读口 `building_level`）。"""
    from core.settlement_officialdom import _settle_upkeep
    pref = _pref(s)
    _rich(s, pref)
    log = []
    s.treasury = 200_000_000
    before = _settle_upkeep(s, list(log))
    assert C.build_civil_building(s, pref, "民居")["ok"] is True
    after = _settle_upkeep(s, list(log))
    assert after > before, "民间造房后月度维持费应上升（走既有通道）"


def test_civil_buildings_do_not_disturb_pop_building_effect(s):
    """民居/货栈不在 `POP_BUILDING_TYPES` ⇒ 不进 `pop_building_effect` 的岗位乘数
    （结构写法也不会被 `int(lv)` 打挂）。"""
    from core.estate_mechanic import pop_building_effect
    pref = _pref(s)
    _rich(s, pref)
    C.build_civil_building(s, pref, "民居")
    C.build_civil_building(s, pref, "货栈")
    assert pop_building_effect(s.prefectures[pref]["buildings"]) == 1.0


def test_monthly_throttle_and_level_cap(s):
    """每月最多升 1 级，且不超过 `level_cap`（§6.1「不做成每回合每人建一次」）。

    ⚠️ 本例要测的是**节流与上限**，不是"有没有压力"。故显式把该路人口抬到
    `level_cap × capacity_per_lv` 以上，使拥挤动因在整轮循环内持续存在——
    否则一旦容量参数调大（如民居 120 万→150 万/级），Lv4 即解除拥挤、
    返回 `no_pressure`，本例会因**压力消失**而失败，与节流/上限无关。
    这样本例便**独立于容量参数调优**。
    """
    pref = _pref(s)
    _rich(s, pref)
    spec = C.CIVIL_BUILDING_SPECS["民居"]
    need = int(spec["capacity_per_lv"] * spec["level_cap"] * 1.5)
    cur = sum(int(v.get("size", 0) or 0) for v in (s.prefectures[pref].get("pops") or {}).values())
    if cur < need:                      # 抬高人口（不新建账本，只改既有 POP size）
        bump = need - cur
        tgt = s.prefectures[pref]["pops"]["农"]
        tgt["size"] = int(tgt.get("size", 0) or 0) + bump
    for i in range(1, spec["level_cap"] + 1):
        out = C.build_civil_building(s, pref, "民居")
        assert out["ok"] is True, f"第 {i} 级应可建（reason={out.get('reason')}）"
        assert out["lv"] == i, "一次只升一级"
        assert out["delta_lv"] == 1
    assert _lv(s, pref, "民居") == spec["level_cap"]
    last = C.build_civil_building(s, pref, "民居")
    assert last["ok"] is False and last["reason"] == "at_level_cap"


def test_build_updates_built_month_on_rebuild(s):
    pref = _pref(s)
    _rich(s, pref)
    C.build_civil_building(s, pref, "民居")
    first = s.prefectures[pref]["buildings"]["民居"]["built_month"]
    s.year += 25
    C.build_civil_building(s, pref, "民居")
    entry = s.prefectures[pref]["buildings"]["民居"]
    assert entry["lv"] == 2
    assert entry["built_month"] > first


def test_build_records_material_value_as_estimate_only(s):
    """基准估价只作估值登记，**不**是第二笔货款（B4-6「不得双计」）。"""
    pref = _pref(s)
    _rich(s, pref)
    money = _money_total(s)
    out = C.build_civil_building(s, pref, "民居")
    assert out["base_material_value"] > 0
    # 料从官仓直取 ⇒ 无货款腿 ⇒ Σ钱只因工钱在 POP 之间转移，**总量分文不减**
    assert _money_total(s) == money
    assert out["coin_paid"] > 0
    assert out["base_material_value"] != out["coin_paid"]
    assert s.statistics["civil_material_value"] == pytest.approx(
        out["base_material_value"])


# =============================================================================
# 7 · 月度批量：守恒与节流
# =============================================================================

def test_apply_civil_construction_conserves_money_and_population(s):
    money = _money_total(s)
    artisans = {pref: int(p["pops"]["工匠"].get("wealth", 0) or 0)
                for pref, p in s.prefectures.items()}
    sizes = {pref: _pop_sizes(s, pref) for pref in s.prefectures}
    res = {d: _mat_total(s, d) for d in MATERIAL_DIMS}   # E-1：全域 Σ 建材
    summary = C.apply_civil_construction(s, [])
    assert summary["levels_built"] > 0, "开局应至少建出一批民间建筑"
    # Σ钱**逐文守恒**（工钱只在 POP 之间划转），凭空建房必使此式不成立
    assert _money_total(s) == money
    # 工钱有付款对手方：本路工匠实收（Σ 不变但分布变了）
    grew = sum(int(p["pops"]["工匠"].get("wealth", 0) or 0) - artisans[pref]
               for pref, p in s.prefectures.items())
    assert grew == summary["coin_paid"] > 0
    for pref, before in sizes.items():
        assert _pop_sizes(s, pref) == before, f"{pref} 人口被改动"
    for d in MATERIAL_DIMS:
        if d in summary["material_used"]:
            assert _mat_total(s, d) == qty_get(res, d) - int(summary["material_used"][d])


def test_apply_civil_construction_never_builds_job_class_by_default(s):
    s2 = C.apply_civil_construction(s, [])
    assert s2["levels_built"] > 0
    for pref, p in s.prefectures.items():
        assert "商铺" not in p["buildings"], "岗位类默认不得自动写入"
    C.apply_civil_construction(s, [], allow_job_class=True)   # 返回值不用，只看副作用
    assert any("商铺" in p["buildings"] for p in s.prefectures.values())


def test_apply_civil_construction_logs_and_blocks(s):
    log = []
    summary = C.apply_civil_construction(s, log)
    assert any("[营造]" in line for line in log)
    assert summary["blocked"], "未建成的建筑必须有可审计的阻断原因"
    for pref, items in summary["blocked"].items():
        for name, info in items.items():
            assert info["decision"] in ("no_build", "undefined")
            assert info["reason"]


def test_apply_civil_construction_is_idempotent_on_materials(s):
    """再跑一次：已到等级上限的路不再耗料（无重复扣减）。"""
    C.apply_civil_construction(s, [])
    res = {d: _mat_total(s, d) for d in MATERIAL_DIMS}   # E-1：全域 Σ 建材
    s2 = C.apply_civil_construction(s, [])
    for d in MATERIAL_DIMS:
        assert _mat_total(s, d) == qty_get(res, d) - int(s2["material_used"].get(d, 0))


def test_civil_statistics_keys_are_registered(s):
    C.apply_civil_construction(s, [])
    for key in ("civil_levels_built", "civil_coin_paid", "civil_material_value",
                "civil_labor_hours"):
        assert key in s.statistics
    assert isinstance(s.statistics, dict)


# =============================================================================
# 8 · 拒绝式：非法入参与非法注册条目
# =============================================================================

@pytest.mark.parametrize("bad_state,exc", [(None, TypeError)])
def test_invalid_state_raises(bad_state, exc):
    with pytest.raises(exc):
        C.route_civil_trigger(bad_state, "两浙路", "民居")


def test_invalid_pref_raises(s):
    with pytest.raises(ValueError):
        C.route_civil_trigger(s, "", "民居")
    with pytest.raises(ValueError):
        C.route_civil_trigger(s, None, "民居")


def test_unregistered_building_raises(s):
    """未注册建筑**拒绝**（不得兜底成中性规格）。"""
    with pytest.raises(ValueError):
        C.route_civil_trigger(s, "两浙路", "不存在的建筑")


def test_malformed_prefectures_raises(s):
    s.prefectures = []
    with pytest.raises(TypeError):
        C.route_civil_trigger(s, "两浙路", "民居")
    with pytest.raises(TypeError):
        C.apply_civil_construction(s, [])


def test_missing_prefectures_raises(s):
    s.prefectures = None
    with pytest.raises(ValueError):
        C.route_civil_trigger(s, "两浙路", "民居")


@pytest.mark.parametrize("bad", [
    {"drivers": ("expansion",), "stock_per_lv": {"木": -1}, "payers": ("士绅",),
     "level_cap": 3, "expansion_metric": "商人", "expansion_wealth_per_lv": 1},
    {"drivers": ("expansion",), "stock_per_lv": {"木": float("nan")},
     "payers": ("士绅",), "level_cap": 3, "expansion_metric": "商人",
     "expansion_wealth_per_lv": 1},
    {"drivers": ("expansion",), "payers": ("士绅",), "level_cap": 3,
     "expansion_metric": "商人", "expansion_wealth_per_lv": 1},          # 缺 stock_per_lv
    {"drivers": ("population",), "stock_per_lv": {"木": 1}, "payers": ("士绅",),
     "level_cap": 3, "capacity_per_lv": 0},                             # 人口动因无容量口径
    {"drivers": ("decay",), "stock_per_lv": {"木": 1}, "payers": ("士绅",),
     "level_cap": 3},                                                    # 损坏动因无周期
    {"drivers": ("expansion",), "stock_per_lv": {"木": 1}, "payers": ("士绅",),
     "level_cap": 3, "expansion_wealth_per_lv": 1},                      # 扩张动因无度量
    {"drivers": ("bogus",), "stock_per_lv": {"木": 1}, "payers": ("士绅",),
     "level_cap": 3},                                                    # 未知动因
    {"drivers": ("expansion",), "stock_per_lv": {"木": 1}, "level_cap": 3,
     "expansion_metric": "商人", "expansion_wealth_per_lv": 1},          # 缺 payers
    {"drivers": ("expansion",), "stock_per_lv": {"木": 1}, "payers": ("士绅",),
     "level_cap": 0, "expansion_metric": "商人", "expansion_wealth_per_lv": 1},
])
def test_registry_rejects_invalid_entries(bad):
    with pytest.raises(C.CivilRegistryError):
        C.register_civil_building("验收房", bad)
    assert "验收房" not in C.CIVIL_BUILDING_SPECS


def test_registry_rejects_job_class_mismatch():
    """`POP_BUILDING_TYPES` 成员必须显式标 `job_class=True`（防静默改就业基线）。"""
    with pytest.raises(C.CivilRegistryError):
        C.register_civil_building("农田", {
            "drivers": ("expansion",), "stock_per_lv": {"木": 1},
            "payers": ("农",), "level_cap": 3, "job_class": False,
            "expansion_metric": "商人", "expansion_wealth_per_lv": 1})


def test_registry_rejects_job_class_dict_write():
    """岗位类只能写标量（`pop_building_effect` 做 `int(lv)`）。"""
    with pytest.raises(C.CivilRegistryError):
        C.register_civil_building("商铺", dict(
            C.CIVIL_BUILDING_SPECS["商铺"], write_form="dict"))


def test_register_valid_civil_building_round_trip(s):
    pref = _pref(s)
    _rich(s, pref)
    spec = {"label": "柴棚", "drivers": ("expansion",), "job_class": False,
            "write_form": "dict", "stock_per_lv": {"木": 10},
            "labor_per_lv": 100.0, "wage_per_labor_hour": 1.0,
            "payers": ("商人",), "level_cap": 2,
            "expansion_metric": "商人", "expansion_wealth_per_lv": 1_000_000}
    C.register_civil_building("柴棚", spec)
    t = C.route_civil_trigger(s, pref, "柴棚")
    assert t["decision"] == "build"
    # 🔴 E-1：料在**本路商人货栈**，且开局是**按商人规模分摊**所得
    # （不是整仓 50,000），故基准取扣前实测值
    from core.material_holding import goods_amount
    t_before = goods_amount(_mgoods(s, pref), "木") or 0
    out = C.build_civil_building(s, pref, "柴棚")
    assert out["ok"] is True and out["lv"] == 1
    assert s.prefectures[pref]["buildings"]["柴棚"]["lv"] == 1
    assert goods_amount(_mgoods(s, pref), "木") == t_before - 10


def test_resolve_civil_building_returns_none_for_unknown():
    assert C.resolve_civil_building("没有这个") is None
    assert C.resolve_civil_building(None) is None