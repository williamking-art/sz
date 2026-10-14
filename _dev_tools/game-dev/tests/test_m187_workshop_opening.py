# -*- coding: utf-8 -*-
"""M187 作坊补座（产能批）· 纯逻辑回归（**未接线 ⇒ 零行为变化**）。

锁定：① 份额分配 **Σ == extra** 且只落**丝禀赋 > 0** 的路；② **确定性**（同状态两次调用同结果）；
③ **幂等**（重复调用不再增座）；④ 新增实例沿用 `WORKSHOP_RECIPES["丝坊"]` 参数（**口径单点**，
`yield`/`output_dim` 与既有座**一致**）；⑤ 键名不与既有冲突、**不覆盖**既有座。
"""

import random

from core import commands
from core.domains.economy import workshop_opening as wo


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
    s = _state()
    before = len(s.workshops)
    added1 = wo.open_extra_workshops(s)
    added2 = wo.open_extra_workshops(s)
    assert added1 == 21, added1
    assert added2 == 0, "重复调用不得再增座（幂等）"
    assert len(s.workshops) == before + 21


def test_new_instances_share_recipe_params_and_do_not_overwrite():
    s = _state()
    existing_keys = set(s.workshops)
    existing_yield = s.workshops["丝坊_京畿路_3"]["yield"]
    wo.open_extra_workshops(s)
    new = {k: v for k, v in s.workshops.items() if k not in existing_keys}
    assert len(new) == 21
    for k, v in new.items():
        assert k.startswith("丝坊_")
        assert v["yield"] == existing_yield == 8000          # 口径单点：不改 yield
        assert v["output_dim"] == "绸" and v["active"] is True
    for k in existing_keys:                                  # 不覆盖既有
        assert k in s.workshops


def test_no_silk_yields_means_no_invention():
    s = _state(with_yields=False)
    assert wo.silk_share_plan(s, 21) == {}
    assert wo.open_extra_workshops(s) == 0
