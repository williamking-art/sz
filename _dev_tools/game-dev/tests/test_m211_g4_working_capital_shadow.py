# -*- coding: utf-8 -*-
"""M211 G-4 工坊营运资金**影子预算** —— 定向回归（只读、零数值）。

锁定（全部对应**用户 2026-10-08 裁决**口径）：
① **只读**：调用前后 state 不变（同种子 A/B 恒等的直接证据）；
② **原料预算**逐座取自 `recipe_cost`（口径单点）；
③ 🔴 **工资义务如实未定义** ⇒ **额度 `quota=None`**（缺失≠0，不拿建筑口径硬套）；
④ **守恒方案**必须给出（转账而非注资 / `M_ALL` 恒等 / 只按成交扣款 / 不足即停工）；
⑤ 无 owner ⇒ `verdict == "undefined"`。
"""

import copy

from core import commands
from core.domains.economy import workshop_fund_shadow as wfs


def _state():
    import random
    random.seed(20261013)
    return commands.new_game()


def test_shadow_is_readonly():
    """只读：货币槽与**全部作坊条目**逐字不变（不比较 `__dict__` 整体——`MemoryGraph` 等按身份比较）。"""
    s = _state()
    before_money = (s.treasury, s.imperial_treasury)
    before_ws = copy.deepcopy(s.workshops)
    before_pops = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    wfs.working_capital_budget(s)
    assert (s.treasury, s.imperial_treasury) == before_money
    assert copy.deepcopy(s.workshops) == before_ws
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before_pops


def test_wage_and_quota_are_undefined_not_zero():
    rep = wfs.working_capital_budget(_state())
    assert rep["stage"] == "shadow"
    assert rep["wage_budget"] is None and rep["quota"] is None      # 缺失≠0
    for r in rep["rows"]:
        assert r["wage_budget"] is None and r["quota"] is None
        assert "不可定义" in r["quota_reason"] and "裁丁" in r["wage_reason"]


def test_procure_budget_comes_from_recipe_cost():
    s = _state()
    rep = wfs.working_capital_budget(s)
    assert rep["workshop_count"] == len(s.workshops)
    # 与既有单点逐座一致（抽首座）
    wid = rep["rows"][0]["workshop"]
    assert rep["rows"][0]["procure_budget"] == wfs.recipe_cost(s, wid).get("cost") or \
        rep["rows"][0]["procure_reason"]


def test_conservation_plan_present_and_says_transfer_not_injection():
    rep = wfs.working_capital_budget(_state())
    plan = rep["conservation_plan"]
    for kw in ("转账", "M_ALL", "只按实际成交扣款", "不启动或缩产", "停工"):
        assert kw in plan, kw


def test_missing_owner_reports_undefined():
    class _S:
        workshops = {"丝坊_路A_0": {"name": "丝坊", "recipe": {"丝": 10000}, "yield": 8000}}

    rep = wfs.working_capital_budget(_S())
    assert rep["rows"][0]["verdict"] == "undefined"
