# -*- coding: utf-8 -*-
"""B-3 资产维持费（L1 money sink）回归测试。

设定与设计依据：
  · `BUILDING_STD[*]["maintain"] = 0.5%/月` 早已存在于 content/data.py 却从未被消费（死数据）；
  · `_settle_upkeep(state, log)` 把它接上，并补齐作坊 / 武库 / 城防的折算基准。

强制不变量（POP 挂载律 ⑤）：
  1) 守恒转移：Δ国库 + ΔΣPOPwealth == 0，且 ΔM_ALL == 0（钱不生不灭，只是从国库流向民间 POP）；
  2) 按实付不穿底：国库不足时只支可支部分，缺口进 `statistics["upkeep_arrears"]`；
  3) 支出随资产基座线性放大（造得越多、维持越贵——这才是对仓鼠型玩家的负反馈）；
  4) 月度结算中确实被执行（否则等于没接上）。
"""
import os
import sys

# 将 game 包根加入路径（脚本直接运行时）
_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import money  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402
from core.settlement_steps import _settle_upkeep  # noqa: E402
from content.data import (  # noqa: E402
    ASSET_MAINTAIN_RATE, EQUIP_UNIT_VALUE, FORT_VALUE, WORKSHOP_VALUE,
)

_ECO = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
        "窖银": "小", "城市化": "中", "回乡": "无", "科举": "中"}


def _pop_wealth(s):
    return sum(pop.get("wealth", 0) for p in s.prefectures.values()
               for pop in p["pops"].values())


def _due(s):
    """独立复算应付额（不复用被测代码的内部变量，避免自证）。"""
    from content.data import BUILDING_COST_GROWTH, BUILDING_STD, POP_BUILDING_VALUE

    def lvc(std, lv):
        return float(std["base_cost"]) * (BUILDING_COST_GROWTH ** (max(1, int(lv)) - 1))

    v = 0.0
    for pj in (getattr(s, "projects", {}) or {}).values():
        if isinstance(pj, dict):
            std = BUILDING_STD.get(str(pj.get("name") or pj.get("type") or ""))
            if std:
                v += lvc(std, pj.get("level", 1))
    for p in s.prefectures.values():
        for bt, lv in (p.get("buildings") or {}).items():
            std = BUILDING_STD.get(str(bt))
            v += lvc(std, lv) if std else POP_BUILDING_VALUE * max(1, int(lv or 1))
    v += len(getattr(s, "workshops", {}) or {}) * float(WORKSHOP_VALUE)
    ca = getattr(s, "central_arsenal", None)
    if ca is not None:
        v += sum((getattr(ca, "stock", {}) or {}).values()) * float(EQUIP_UNIT_VALUE)
    v += sum((l.get("fortification", 0) or 0)
             for l in getattr(s, "defense_lines", {}).values()) * float(FORT_VALUE)
    return int(v * ASSET_MAINTAIN_RATE)


def test_upkeep_is_a_conserving_transfer():
    """国库 → 民间 POP：Δ国库 + ΔΣPOPwealth == 0，ΔM_ALL == 0。"""
    s = GameState("史实")
    s.treasury = 500_000
    before = (_pop_wealth(s), s.treasury, money.m_all(s))

    paid = _settle_upkeep(s, [])

    assert paid > 0, "资产基座非空（作坊 + 武库 + 城防），应付额必须为正"
    assert paid == _due(s), "足额时实付 == 应付（按 0.5%/月 × 资产折算造价）"
    d_wealth = _pop_wealth(s) - before[0]
    d_treasury = s.treasury - before[1]
    assert d_treasury == -paid
    assert d_wealth == paid, "支出必须全额落到 POP wealth，不得经过任何影子账户"
    assert money.m_all(s) - before[2] == 0, "内部转移不应改变 M_ALL"
    assert s.statistics.get("upkeep_arrears", 0) == 0
    assert s.treasury >= 0


def test_upkeep_pays_only_available_and_records_arrears():
    """国库不足时按实付、不穿底、不造币；缺口进 upkeep_arrears。"""
    s = GameState("史实")
    s.treasury = 1
    due = _due(s)
    m_before = money.m_all(s)

    paid = _settle_upkeep(s, [])

    assert paid == min(due, 1) == 1
    assert s.treasury == 0, "不得透支成负数"
    assert s.statistics["upkeep_arrears"] == due - paid
    assert money.m_all(s) - m_before == 0, "欠费不是货币存量变化，只是未发生的转移"

    # 连续调用：零支出、零穿底、欠费继续累积
    # 第二次国库已为 0，故全额 due 计入欠费：累计 = (due - 1) + due
    paid2 = _settle_upkeep(s, [])
    assert paid2 == 0
    assert s.treasury == 0
    assert s.statistics["upkeep_arrears"] == 2 * due - 1


def test_upkeep_scales_with_asset_base():
    """资产基座越大，维持费越高（对囤积型玩法的负反馈核心）。"""
    s = GameState("史实")
    s.treasury = 50_000_000
    base_due = _due(s)

    s.workshops[f"_test_workshop_{len(s.workshops)}"] = {"type": "酒坊"}
    grown_due = _due(s)

    assert grown_due > base_due, "新增作坊必须抬高维持费"
    assert abs((grown_due - base_due) - WORKSHOP_VALUE * ASSET_MAINTAIN_RATE) <= 1, \
        "增量应恰为 作坊造价 × 0.5%/月（允许 int 截断 1 贯）"

    s.treasury = 50_000_000
    paid = _settle_upkeep(s, [])
    assert paid == grown_due


def test_upkeep_runs_inside_monthly_settlement():
    """月度结算必须真的调用到它（防"写了没接上"）。"""
    s = GameState("史实")
    s.treasury = 5_000_000
    s._economy_ai = _ECO
    upkeep_before = s.statistics.get("upkeep_arrears", 0)
    m_before = money.m_all(s)

    log = run_monthly_settlement(s, seed_offset=7)

    assert any("维持" in str(line) for line in log), \
        "月结算日志应出现 [维持] 记录，证明 Step 3.9 已接上"
    # 国库充足时不应新增欠费
    assert s.statistics.get("upkeep_arrears", 0) == upkeep_before
    # 整体月结算货币残差仍在容差内（维持费本身是零残差转移）
    assert abs(money.m_all(s) - m_before) < 20_000_000
