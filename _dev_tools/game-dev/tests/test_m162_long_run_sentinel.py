# -*- coding: utf-8 -*-
"""P6 **长局质量门哨兵**（M162 · 校准/放行阶段首个可交付物）。

依据：`specs/economy/unified-civilian-market/tasks.md` §8（P6）——
「先跑**确定性账本/交易断言**，再跑**固定种子短局和 60/240 月长局**」。

本哨兵默认跑 **12 月**（保持全量回归快），设 `SONGZUO_LONG_RUN=1` 时跑 **60 月**：
```powershell
$env:SONGZUO_LONG_RUN="1"; & $py -m pytest _dev_tools/game-dev/tests/test_m162_long_run_sentinel.py -q
```

锁定四件事（**长局后仍须成立**）：
1. **结算不抛异常**（60 月连续结算）
2. **货币恒等式**：`m_all == Σ accounts`（残差 0；10 账户）
3. **POP 守恒**：逐路 `Σ治所 == 路级`（抽查 农 `size`/`wealth`）
4. **读数契约**：`readout_hub` 全项 `display` 规则 + `drill_down` 为 `dict|None`（长局后仍合规）
"""

import os
import random

from core import commands
from core.domains.economy import readout_hub as rh
from core.domains.economy import stock_identity as si


def _run(state, months):
    import core.settlement as S
    for _ in range(months):
        S.run_monthly_settlement(state)
    return state


def _months():
    """档位：默认 **12 月**（保持全量回归快）· `SONGZUO_LONG_RUN=60` 或 `=1` ⇒ **60 月** ·
    `SONGZUO_LONG_RUN=240` ⇒ **240 月**（P6 第二层；单次约 3 分钟，实测 184s 四项全过）。"""
    v = str(os.environ.get("SONGZUO_LONG_RUN", "")).strip()
    if v == "240":
        return 240
    if v in ("1", "60"):
        return 60
    return 12


def _fresh():
    random.seed(20261013)
    return commands.new_game()


def test_long_run_settlement_does_not_raise():
    s = _run(_fresh(), _months())                       # 任一月抛异常即红
    assert len(s.prefectures) == 20


def test_long_run_money_identity_residual_is_zero():
    s = _run(_fresh(), _months())
    mi = si.money_identity(s)
    assert mi.get("available") is True, mi
    assert abs(float(mi["m_all"]) - float(mi["accounts_sum"])) < 1e-6, mi
    # 2026-10-20 全审 P0-1：上面的恒等式只是「M_ALL == Σ账户」的**静态**恒等式；
    # 造币/销毁的唯一判据是**月际对账残差**（旧版缺这条 ⇒ 12 月 +13,470,432 漏网）。
    cum = float((s.money_audit or {}).get("cum_residual") or 0.0)
    assert abs(cum) < 1.0, f"月度对账累计残差 {cum:+,.0f} 贯（存在无对手方的造币/销毁）"


def test_long_run_pop_conservation_seat_sum_equals_route():
    s = _run(_fresh(), _months())
    bad = []
    for route, p in s.prefectures.items():
        seats = p.get("seats") or {}
        for fld in ("size", "wealth"):
            seat_sum = sum(float((sr.get("pops") or {}).get("农", {}).get(fld, 0) or 0)
                           for sr in seats.values())
            route_val = float(((p.get("pops") or {}).get("农") or {}).get(fld, 0) or 0)
            if abs(seat_sum - route_val) > 1e-6:
                bad.append((route, fld, seat_sum, route_val))
    assert bad == [], bad                                  # 真账==Σ治所（POP 挂载律）


def test_long_run_readout_contract_holds():
    s = _run(_fresh(), _months())
    rep = rh.collect(s)
    assert len(rep["readouts"]) == len(rh.READOUTS)
    for k, v in rep["readouts"].items():
        assert isinstance(v["display"], str), k
        assert isinstance(v.get("drill_down"), (dict, type(None))), (k, type(v.get("drill_down")))
        if v["value"] is None:
            assert v["display"] == "undefined" and v["reason"], k
    assert rep["undefined_count"] <= 3, rh.undefined_summary(s)   # 长局不应出现"大面积缺失"


def test_long_run_with_pm_switch_preserves_invariants():
    """半程切换生产方式（燃料替换）后，长局仍守恒、不崩、读数合规。

    2026-10-18 平衡批次：PM 现在会改**投入配方**（煤炭↔木炭、蒸汽/工场额外消耗）。
    本用例锁「切 PM 的长期副作用」：货币恒等式、POP 挂载律、资源非负有限、读数契约。
    """
    import math

    from core.domains.economy.production_methods import switch_pm
    from core.foundation.ledger.building_bridge import capital_seat_id

    s = _fresh()
    months = _months()
    half = max(1, months // 2)
    _run(s, half)

    switched = 0
    for route, p in s.prefectures.items():
        seat = capital_seat_id(p, route)
        if not seat:
            continue
        for building, pm_id in (
            ("冶铁作坊", "pm_smelting_charcoal"),
            ("冶铁工场", "pm_smelting_charcoal"),
            ("官窑瓷坊", "pm_ceramics_charcoal"),
        ):
            if switch_pm(s, route, str(seat), building, pm_id):
                switched += 1
    assert switched > 0, "半程应至少切换一路的生产方式"

    _run(s, months - half)

    mi = si.money_identity(s)
    assert mi.get("available") is True, mi
    assert abs(float(mi["m_all"]) - float(mi["accounts_sum"])) < 1e-6, mi

    bad = []
    for route, p in s.prefectures.items():
        seats = p.get("seats") or {}
        for fld in ("size", "wealth"):
            seat_sum = sum(float((sr.get("pops") or {}).get("农", {}).get(fld, 0) or 0)
                           for sr in seats.values())
            route_val = float(((p.get("pops") or {}).get("农") or {}).get(fld, 0) or 0)
            if abs(seat_sum - route_val) > 1e-6:
                bad.append((route, fld, seat_sum, route_val))
    assert bad == [], bad

    for dim, cell in (s.resources or {}).items():
        stock = float((cell or {}).get("stock", 0) or 0)
        assert math.isfinite(stock), (dim, stock)
        assert stock >= 0, (dim, stock)
    assert math.isfinite(float(s.treasury))

    rep = rh.collect(s)
    assert len(rep["readouts"]) == len(rh.READOUTS)
    for k, v in rep["readouts"].items():
        assert isinstance(v["display"], str), k
        assert isinstance(v.get("drill_down"), (dict, type(None))), (k, type(v.get("drill_down")))