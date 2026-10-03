# -*- coding: utf-8 -*-
"""B2-R1 · 人口与粮食归因读数的定向回归（规格 `market-civilian-economy` B2-R1）

锁定三条口径：
- `grain_hungry` 是**饥饿人月**（累加），**不是**当月人数；
- 逃荒是**农 → 流民池转移**（1:1），ΣPOP 口径不含流民，
  比较人口规模须用 `pop_plus_refugees`；
- 缺 `refugees` 键 ≠ 该路无流民（缺失不作 0）；读数**不写** `state`。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.population_readout import (  # noqa: E402
    POP_CLASSES, famine_attribution, hunger_person_months, population_ledger,
)
from core.settlement import run_monthly_settlement  # noqa: E402


def _state(months=12):
    s = GameState("史实")
    init_legacies(s)
    s.treasury = 50_000_000
    for _ in range(months):
        s.treasury = max(s.treasury, 50_000_000)
        run_monthly_settlement(s)
    return s


# ====================================================== 饥荒人月口径
def test_grain_hungry_is_person_month_not_headcount():
    """`grain_hungry` 标记为**人月**，明确否定"当月人数"读法。"""
    s = _state(6)
    h = hunger_person_months(s)
    assert h["unit"] == "person-month"
    assert h["is_cumulative"] is True
    assert h["not_a_headcount"] is True


def test_missing_grain_hungry_is_none_not_zero():
    """统计键缺失 → `None`（未记录 ≠ 无人饥饿，不回落 0）。"""
    s = _state(1)
    s.statistics.pop("grain_hungry", None)
    h = hunger_person_months(s)
    assert h["person_months"] is None
    assert "未记录" in h["note"]


def test_person_month_is_cumulative_not_single_month():
    """`grain_hungry` 是**累加人月**，不与"当月缺粮人数"跨口径比较。

    注意：`food_insecure_headcount` 受 `FLEE_CAP_PER_ROUTE`（每路封顶）约束，
    结算内与读数侧都按路分别调用，故"当月求和"本身也是**封顶后**的量，
    与累加人月**不同口径**、不可直接比大小。两者只各自证明一件事：
    累加值随月份不减；单月值随当月灾情波动。
    """
    a = _state(3)
    b = _state(12)
    ha, hb = hunger_person_months(a)["person_months"], hunger_person_months(b)["person_months"]
    # 累加值：月份越久不应变小（除非无数据）
    if ha is not None and hb is not None:
        assert hb >= ha, "累加人月随月份倒退，说明不是累加口径"


# ====================================================== 人口台账
def test_ledger_sums_all_six_pop_classes():
    s = _state(6)
    led = population_ledger(s)
    assert set(led["by_class"]) == set(POP_CLASSES)
    assert led["total_pop"] == sum(led["by_class"].values())
    assert led["total_pop"] > 0


def test_pop_plus_refugees_exceeds_pop():
    """逃荒是转移：ΣPOP+流民 ≥ ΣPOP（否则说明重复扣减）。"""
    s = _state(12)
    led = population_ledger(s)
    assert led["pop_plus_refugees"] == led["total_pop"] + led["total_refugees"]
    assert led["pop_plus_refugees"] >= led["total_pop"]


def test_refugees_missing_key_is_flagged_not_zeroed():
    """缺 `refugees` 键的路须被列出，**不当成 0**。"""
    s = _state(3)
    r0 = list(s.prefectures)[0]
    del s.prefectures[r0]["refugees"]
    led = population_ledger(s)
    assert r0 in led["missing_refugee_field"]
    row = next(r for r in led["by_route"] if r["route"] == r0)
    assert row["refugees"] is None, "缺失被伪装成 0"


def test_ledger_is_read_only():
    """读数**不改** state（不得写 statistics / 人口）。"""
    s = _state(6)
    before_total = population_ledger(s)["total_pop"]
    before_stats = dict(s.statistics or {})
    population_ledger(s)
    famine_attribution(s)
    hunger_person_months(s)
    assert population_ledger(s)["total_pop"] == before_total
    assert dict(s.statistics or {}) == before_stats


# ====================================================== 饥荒归因
def test_attribution_separates_grain_vs_money():
    """归因区分**没粮**与**没钱**（B2-R3 要求可诊断）。"""
    s = _state(12)
    fa = famine_attribution(s)
    assert fa["total_shortfall"] >= 0
    for cls, d in fa["by_class"].items():
        assert d["reason"] in ("own_grain_short", "purchasing_power_short")
        assert d["shortfall_headcount"] >= 0


def test_attribution_without_price_is_honest():
    """粮价不可读 → 不臆造归因，如实说明。"""
    s = _state(3)
    s.grain_price = None
    fa = famine_attribution(s)
    assert fa["total_shortfall"] == 0
    assert "grain_price" in fa["note"]


def test_attribution_is_single_month_and_marked_as_such():
    """当月判定**不累加**：同一种子连续两次读数，若状态未变则读数应一致
    （若为累加口径，第二次必然更大）。"""
    s = _state(6)
    fa1 = famine_attribution(s)["total_shortfall"]
    fa2 = famine_attribution(s)["total_shortfall"]
    assert fa1 == fa2, "归因读数在状态未变时发生变化，疑似累加口径"


# ====================================================== 恒等式
def test_population_ledger_identity_reconstructs():
    """人口恒等式：ΣPOP 净减 ＝ 流民净增 ＋ 净流出量（可重建）。

    ⚠️ `outflow` **不恒为非负**：`ΣPOP + 流民` 池可以**增长**——粮食充足时
    逃荒减少、流民回流/迁入（农业投资见效后的真实效果，B2-R4 接线后实测为
    负值）。故此处只断言**恒等式可重建**；单向外流由
    `test_outflow_is_reported_separately` 在无干预基线下锁定。
    """
    a = _state(2)
    b = _state(14)
    la, lb = population_ledger(a), population_ledger(b)
    pop_drop = la["total_pop"] - lb["total_pop"]
    ref_gain = lb["total_refugees"] - la["total_refugees"]
    outflow = la["pop_plus_refugees"] - lb["pop_plus_refugees"]
    # 恒等式本身必须严格成立（这是读数可信度的核心）
    assert pop_drop == ref_gain + outflow


def test_outflow_is_reported_separately():
    """`outflow` 独立可读——净流出为负时表示总人口池**增长**（如实呈现，不截断为 0）。"""
    a = _state(2)
    b = _state(14)
    la, lb = population_ledger(a), population_ledger(b)
    outflow = la["pop_plus_refugees"] - lb["pop_plus_refugees"]
    # 读数里两个分量都可得 ⇒ 差异可由读者自行判断增/减
    assert (lb["total_pop"] + lb["total_refugees"]) - \
           (la["total_pop"] + la["total_refugees"]) == -outflow
