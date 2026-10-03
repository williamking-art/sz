# -*- coding: utf-8 -*-
"""S6 逃籍腿 · 回归（用户 2026-10-01 口径裁决 · 二次细化）。

裁决要点：
  1. 逃籍人数由「**实际无法吃粮的人数**」**1:1 派生**，**不用 2%/0.2% 这类比例魔数**
     （上限 `FLEE_CAP_PER_ROUTE` 仅作爆版保护，非驱动项）；
  2. 「无法吃粮」= 需求 − **自有粮 ＋ 购粮能力**（`wealth / 粮价`）——买得到就不算饿；
     判据为**单点** `settlement_common.food_insecure_headcount`，
     `settlement_imperial`（逃籍）与 `settlement_granary`（饥荒逃农）**共用**；
  3. 税重/民怨是**独立机制**（逃税/逃乱，非逃饥），沿用原压力率口径，不受本次影响。

口径演进留痕：① 原式 `p["grain"] < population * 0.3` 量纲错配 → **0/20 死码**；
② 曾改为「逐路公储 `grain_months < 1 月」——但实测成都府路公储 0.79 月而户储
2.39 月，**没人真饿**却判逃籍（假逃籍）；③ 现改为缺粮人数驱动（开局实算
缺粮 75 万 / 1.0075 亿 = 0.74%，梯度连续）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import GRAIN_CONSUME_PER_CAPITA    # noqa: E402
from core.game_state import GameState               # noqa: E402
from core.legacy_mechanic import init_legacies        # noqa: E402
from core.settlement_common import (                 # noqa: E402
    FLEE_CAP_PER_ROUTE, food_insecure_headcount,
)
from core.settlement_imperial import _settle_hidden_pop  # noqa: E402


@pytest.fixture()
def state():
    s = GameState("史实")
    init_legacies(s)
    # 关掉税重/民怨两腿（独立机制），使本文件只考察缺粮腿
    s.commerce_tax_rate = 0.15
    s.population_satisfaction = 50
    return s


# ---------------------------------------------------------------- 工具
def _feed(s, months=3.0):
    """让所有人有饭吃（补自有粮 ＋ 钱）。"""
    for p in s.prefectures.values():
        for cls, slot in (p.get("pops") or {}).items():
            if not isinstance(slot, dict):
                continue
            per = float(GRAIN_CONSUME_PER_CAPITA.get(cls, 0.5))
            size = int(slot.get("size", 0) or 0)
            slot["grain"] = float(slot.get("grain", 0) or 0) + size * per * months
            slot["wealth"] = float(slot.get("wealth", 0) or 0) + size * per * months


def _starve(s, cls="农", months=0.0):
    """把某类 POP 的粮与钱清零（制造缺粮）。"""
    for p in s.prefectures.values():
        slot = (p.get("pops") or {}).get(cls)
        if isinstance(slot, dict):
            slot["grain"] = months
            slot["wealth"] = 0.0


def _hidden_of(s, name):
    return int((s.prefectures[name].get("pops", {}).get("农") or {}).get("hidden", 0) or 0)


def _hungry_total(s):
    """按单点口径独立复算全图缺粮人数。"""
    tot = 0
    for p in s.prefectures.values():
        h = food_insecure_headcount(p.get("pops") or {},
                                    float(p.get("grain_price", s.grain_price)))
        tot += int(h.get("total", 0) or 0)
    return tot


# ---------------------------------------------------------------- 单点口径
def test_headcount_helper_basics():
    """单点 helper：吃饱 → 0；清零 → 全员缺粮；买得到 → 不算饿。"""
    pops = {"农": {"size": 100, "grain": 0.0, "wealth": 0.0}}
    h = food_insecure_headcount(pops, 1.0)
    assert h["农"] == 100 and h["total"] == 100, "无粮无钱 → 全员吃不上饭"
    pops = {"农": {"size": 100, "grain": 1000.0, "wealth": 0.0}}
    assert food_insecure_headcount(pops, 1.0)["农"] == 0, "自有粮充足 → 0"
    # 购粮能力：粮价 1 贯/石，10 贯可买 10 石 = 20 人一个月的口粮（农 0.5 石/人）
    pops = {"农": {"size": 100, "grain": 0.0, "wealth": 10.0}}
    assert food_insecure_headcount(pops, 1.0)["农"] == 80, "买得到的不算饿"


def test_headcount_respects_per_capita():
    """人均需求按阶层取 `GRAIN_CONSUME_PER_CAPITA`（不是统一 0.5）。"""
    per_farmer = float(GRAIN_CONSUME_PER_CAPITA.get("农", 0.5))
    pops = {"农": {"size": 100, "grain": 0.0, "wealth": 100.0 * per_farmer}}
    assert food_insecure_headcount(pops, 1.0)["农"] == 0, "钱正好够一月口粮 → 不算饿"


def test_headcount_missing_price_not_treated_as_hungry():
    """价格缺失/非正 → 无缺粮（读数缺失**不当饿**，也不凭空造饥荒）。"""
    pops = {"农": {"size": 100, "grain": 0.0, "wealth": 0.0}}
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        assert food_insecure_headcount(pops, bad).get("total", 0) == 0, f"价格 {bad} 不得造饥荒"


def test_headcount_bad_input_safe():
    """`pops` 非 dict → 空结果（不抛）。"""
    assert food_insecure_headcount(None, 1.0) == {}
    assert food_insecure_headcount([], 1.0) == {}


# ---------------------------------------------------------------- 逃籍 = 缺粮人数 1:1
def test_flee_count_equals_hungry_count(state):
    """核心：**逐路**逃籍 ＝ `min(该路缺粮人数, 单路上限)`（1:1，无比例魔数）。"""
    _feed(state)
    _starve(state, "农")                       # 农缺粮（逃籍主体阶层）
    want = 0
    for n, p in state.prefectures.items():
        h = food_insecure_headcount(p.get("pops") or {},
                                    float(p.get("grain_price", state.grain_price)))
        want += min(int(h.get("total", 0) or 0), FLEE_CAP_PER_ROUTE)
    assert want > 0
    _settle_hidden_pop(state, [])
    # 用**实际逃籍人数**读数断言，而非 hidden 净变化（同一次调用里归籍会减 hidden）
    fled = int(state.statistics["hidden_flee_actual"])
    assert fled == want, f"逃籍 {fled:,} 应等于 Σmin(各路缺粮, {FLEE_CAP_PER_ROUTE:,}) = {want:,}"


def test_no_magic_ratio_in_source():
    """源码级反锁：**代码行**里不得再出现 2% / 0.2% / 0.008 这类逃逸魔数
    （注释里记录口径演进属正常，故只看非注释行）。"""
    import inspect
    from core import settlement_imperial as SI
    from core import settlement_granary as SG

    def _code_only(src: str) -> str:
        lines = []
        for ln in src.splitlines():
            t = ln.strip()
            if t.startswith("#") or t.startswith('"') or t.startswith("'"):
                continue
            lines.append(ln.split("  #")[0])
        return "\n".join(lines)

    isrc = _code_only(inspect.getsource(SI._settle_hidden_pop))
    assert "_sz * 0.02" not in isrc, "2% 单池上限魔数须移除（改为人数 1:1）"
    assert "0.008" not in isrc, "0.008 压力魔数须移除"
    gsrc = _code_only(inspect.getsource(SG))
    assert "* 0.002" not in gsrc, "0.2% 逃荒比例魔数须移除"
    assert "50_000" not in gsrc, "上限魔数应改用共享常量 FLEE_CAP_PER_ROUTE"


def test_flee_zero_when_everyone_fed(state):
    """反向：人人有饭 → 一人不逃（比例魔数时代这里也会按 2% 掉人）。"""
    _feed(state)
    before = sum(_hidden_of(state, n) for n in state.prefectures)
    _settle_hidden_pop(state, [])
    after = sum(_hidden_of(state, n) for n in state.prefectures)
    assert after <= before, f"吃饱时不得新增逃籍（{before:,} → {after:,}）"
    assert int(state.statistics["hidden_flee_hungry"]) == 0


def test_flee_scales_with_hunger_not_flat_rate(state):
    """梯度：缺粮越多逃得越多（人数驱动），而不是固定比例。"""
    _feed(state)
    _starve(state, "农", months=0.0)
    full_hungry = _hungry_total(state)
    b0 = sum(_hidden_of(state, n) for n in state.prefectures)
    _settle_hidden_pop(state, [])
    fled_full = sum(_hidden_of(state, n) for n in state.prefectures) - b0

    # 只让一半路缺粮 → 逃籍应显著少于全缺
    s2 = GameState("史实")
    init_legacies(s2)
    s2.commerce_tax_rate = 0.15
    s2.population_satisfaction = 50
    _feed(s2)
    names = list(s2.prefectures)
    for n in names[:len(names) // 2]:
        slot = s2.prefectures[n]["pops"]["农"]
        slot["grain"] = 0.0
        slot["wealth"] = 0.0
    half_hungry = _hungry_total(s2)
    b1 = sum(_hidden_of(s2, n) for n in s2.prefectures)
    _settle_hidden_pop(s2, [])
    fled_half = sum(_hidden_of(s2, n) for n in s2.prefectures) - b1
    assert full_hungry > half_hungry > 0
    assert fled_full > fled_half >= 0, "逃籍应随缺粮人数单调递增"


# ---------------------------------------------------------------- 购粮能力计入
def test_wealth_prevents_flight(state):
    """有钱买粮 → 不算缺粮 → 不逃（购粮通道已落地且守恒）。"""
    _feed(state)
    _starve(state, "农")
    # 给农补钱（够买 3 个月口粮），粮仍为 0
    for p in state.prefectures.values():
        slot = p["pops"]["农"]
        per = float(GRAIN_CONSUME_PER_CAPITA.get("农", 0.5))
        price = float(p.get("grain_price", state.grain_price))
        slot["wealth"] = int(slot["size"]) * per * 3.0 * price
    assert _hungry_total(state) == 0, "钱够买粮就不该算缺粮"
    b0 = sum(_hidden_of(state, n) for n in state.prefectures)
    _settle_hidden_pop(state, [])
    b1 = sum(_hidden_of(state, n) for n in state.prefectures)
    assert b1 <= b0, "买得到粮就不该逃籍"


# ---------------------------------------------------------------- 逐路
def test_per_route_application(state):
    """逐路施加：只有缺粮的路逃籍，吃饱的路不逃。"""
    _feed(state)
    target = next(iter(state.prefectures))
    slot = state.prefectures[target]["pops"]["农"]
    slot["grain"] = 0.0
    slot["wealth"] = 0.0
    before = {n: _hidden_of(state, n) for n in state.prefectures}
    _settle_hidden_pop(state, [])
    assert _hidden_of(state, target) > before[target], "缺粮路应逃籍"
    for n in state.prefectures:
        if n == target:
            continue
        assert _hidden_of(state, n) <= before[n], f"{n} 吃饱却逃籍了"


def test_conservation_still_holds(state):
    """加了缺粮腿之后，逐路局部守恒与总口守恒仍须成立。"""
    def _totals(st):
        pops = sum(int(v.get("size", 0) or 0)
                   for p in st.prefectures.values()
                   for v in p["pops"].values() if isinstance(v, dict))
        return pops, sum(_hidden_of(st, n) for n in st.prefectures)

    _feed(state)
    _starve(state, "农")
    p0, h0 = _totals(state)
    _settle_hidden_pop(state, [])
    p1, h1 = _totals(state)
    assert p1 + h1 == p0 + h0, "总口必须守恒（逃籍是内部转移）"
    from content.data_constants import PERSONS_PER_HOUSEHOLD as PPH
    assert state.land["hidden_households"] == h1 // PPH


# ---------------------------------------------------------------- 税重/民怨两腿仍在
def test_tax_and_unrest_legs_still_work(state):
    """反回归：缺粮腿改造**不得**废掉税重/民怨这两条独立机制（逃税/逃乱）。"""
    _feed(state)                                    # 无人缺粮 → 粮腿为 0
    assert _hungry_total(state) == 0
    state.commerce_tax_rate = 0.30                 # 税重
    state.population_satisfaction = 0               # 民怨
    b0 = sum(_hidden_of(state, n) for n in state.prefectures)
    _settle_hidden_pop(state, [])
    b1 = sum(_hidden_of(state, n) for n in state.prefectures)
    assert b1 > b0, "税重/民怨仍应产生逃籍（与缺粮无关的独立机制）"


# ---------------------------------------------------------------- 可诊断读数
def test_diagnostic_readings(state):
    """可诊断读数：缺粮总人数 ＋ 逐路分布（缺失≠静默）。"""
    _feed(state)
    _starve(state, "农")
    log = []
    _settle_hidden_pop(state, log)
    assert int(state.statistics["hidden_flee_hungry"]) > 0
    by_route = state.statistics["hidden_flee_by_route"]
    assert isinstance(by_route, dict) and by_route
    assert any("隐户" in x for x in log), f"应出逃籍日志：{log}"


def test_diagnostic_zero_when_fed(state):
    _feed(state)
    _settle_hidden_pop(state, [])
    assert int(state.statistics["hidden_flee_hungry"]) == 0
    assert state.statistics["hidden_flee_by_route"] == {}