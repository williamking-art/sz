# -*- coding: utf-8 -*-
"""M42c 恒等式闭合回归：跑真实流水，**全国仓**逐维残差必须为 0。

这是 P1 第一句「逐月复原货币与商品库存恒等式」在**全国仓这条链**上的验收：
`Δ(全国仓, dim) == 流量账净额(dim)`（逐维），且**没有"有 Δ 但无账"的维**（unclosed 为空）。

固定随机种子 ⇒ 可复现；只读判定（不改数值）。
⚠️ 若将来新增了未经登记的入/出仓写点，本用例会红——**这正是它的用途**（把"账漏了"变成可执行断言）。
"""

import random

from core import commands
from core.domains.economy import stock_flow as sf
from core.domains.economy import stock_identity as si


def _cumulative_flows(state, custody=sf.CUSTODY_NATIONAL):
    """跨全月桶累计净流量（**直接用模块 API**——避免助手自己维护一套分桶形态解析）。"""
    return sf.cumulative_flows(state, custody=custody)


def test_national_warehouse_identity_closes_over_pipeline():
    import core.settlement as S

    random.seed(20261013)
    s = commands.new_game()
    first = si.stock_snapshot(s)
    for _ in range(3):
        S.run_monthly_settlement(s)
    last = si.stock_snapshot(s)

    flows = _cumulative_flows(s)
    rep = sf.residual_for_custody(first, last, "national_resources", flows=flows)

    moved = {d for d, v in (rep["residual"] or {}).items()
             if isinstance(v, (int, float)) and abs(v) > 1e-6}
    assert rep["nonzero"] == [], f"有维残差非 0：{rep['nonzero']}（全表 {rep['residual']}）"
    assert rep["unclosed"] == [], f"有维无账（有 Δ 但未登记）：{rep['unclosed']}"
    assert moved == set(), moved
    assert rep["ok"] is True


def test_money_residual_zero_over_pipeline():
    import core.settlement as S

    random.seed(20261013)
    s = commands.new_game()
    for _ in range(2):
        S.run_monthly_settlement(s)
    mon = si.money_identity(s)
    assert mon["available"] is True
    assert mon["residual"] is not None and abs(mon["residual"]) < 1e-6
