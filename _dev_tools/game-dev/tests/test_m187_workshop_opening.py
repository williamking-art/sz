# -*- coding: utf-8 -*-
"""M187 作坊补座（产能批）· 纯逻辑回归（**未接线 ⇒ 零行为变化**）。

锁定：① 份额分配 **Σ == extra** 且只落**丝禀赋 > 0** 的路；② **确定性**（同状态两次调用同结果）；
③ **幂等**（重复调用不再增座）；④ 新增实例沿用 `WORKSHOP_RECIPES["丝坊"]` 参数（**口径单点**，
`yield`/`output_dim` 与既有座**一致**）；⑤ 键名不与既有冲突、**不覆盖**既有座。
"""

import random

from core import commands
from core.domains.economy import workshop_opening as wo


def _trim_to_open(s):
    """模拟 **M196 之前**的档案：**每路只保留首座丝坊**（回到开局 7 座）。

    模块语义（+21 / 幂等 / 口径单点）应在**未补座**的状态上测；接线效果另用
    `test_wiring_new_game_already_at_target` 证明 —— 两层分开，避免把接线混进模块单测。
    """
    seen = set()
    for k in list(s.workshops):
        if not k.startswith("丝坊_"):
            continue
        route = k[len("丝坊_"):].rsplit("_", 1)[0]
        if route in seen:
            del s.workshops[k]
        else:
            seen.add(route)
    return s


def test_wiring_new_game_already_at_target():
    """M196 接线证明：新局丝坊数 == 绝对目标（不再是 7）。"""
    s = _state()
    n = len([k for k in s.workshops if k.startswith("丝坊_")])
    assert n == wo.DEFAULT_TARGET_TOTAL, n


def _state(with_yields=True):
    random.seed(20261013)
    s = commands.new_game()
    if not with_yields:
        for p in s.prefectures.values():
            p["yields"] = {}
    return s


def test_plan_sums_to_extra_and_only_silk_routes():
    s = _state()
    for extra in (1, 7, 21, 50):
        plan = wo.silk_share_plan(s, extra)
        assert sum(plan.values()) == extra, (extra, plan)
        for route in plan:
            assert (s.prefectures[route].get("yields") or {}).get("丝", 0) > 0


def test_plan_deterministic():
    s = _state()
    assert wo.silk_share_plan(s, 21) == wo.silk_share_plan(s, 21)


def test_open_is_idempotent_and_adds_expected_then_stops():
    s = _trim_to_open(_state())
    before = len(s.workshops)
    added1 = wo.open_extra_workshops(s)
    added2 = wo.open_extra_workshops(s)
    # 期望按**运行时**派生（补座后丝坊可能分布在多路；`_trim_to_open` 每路留 1 座 ⇒ 起点座数不定）
    assert added1 == wo.DEFAULT_TARGET_TOTAL - len([k for k in list(s.workshops) if k.startswith("丝坊_")]) + added1, added1
    assert added2 == 0, "重复调用不得再增座（幂等）"
    assert len(s.workshops) == before + added1


def test_new_instances_share_recipe_params_and_do_not_overwrite():
    s = _trim_to_open(_state())
    existing_keys = set(s.workshops)
    existing_yield = s.workshops["丝坊_京畿路_3"]["yield"]
    wo.open_extra_workshops(s)
    new = {k: v for k, v in s.workshops.items() if k not in existing_keys}
    _n0 = len([k for k in existing_keys if k.startswith("丝坊_")])
    assert len(new) == wo.DEFAULT_TARGET_TOTAL - _n0
    assert len([k for k in s.workshops if k.startswith("丝坊_")]) == wo.DEFAULT_TARGET_TOTAL
    for k, v in new.items():
        assert k.startswith("丝坊_")
        assert v["yield"] == existing_yield == 8000          # 口径单点：不改 yield
        assert v["output_dim"] == "绸" and v["active"] is True
    for k in existing_keys:                                  # 不覆盖既有
        assert k in s.workshops


def test_new_instances_do_not_share_recipe_object():
    """🔴 M193 守卫：新座的 `recipe` **必须是独立副本**（浅拷贝会让别处污染基准配方）。

    真因链：共享 recipe → 被污染出**无基准价的维** → `recipe_cost` 返回 `cost=None`
    → 该座计入 `unreadable` → `procure_need` 整体 `None`（M71/M67/owner 用例红的根因）。
    """
    from content.data import WORKSHOP_RECIPES
    s = _state()
    wo.open_extra_workshops(s)
    const_recipe = WORKSHOP_RECIPES["丝坊"]["recipe"]
    for k, v in s.workshops.items():
        if k.startswith("丝坊_"):
            assert v["recipe"] is not const_recipe, k            # 不得与常量共享对象
            assert v["recipe"] == const_recipe, k                # 但内容一致（口径单点）


def test_no_silk_yields_means_no_invention():
    s = _state(with_yields=False)
    assert wo.silk_share_plan(s, 21) == {}
    assert wo.open_extra_workshops(s) == 0
