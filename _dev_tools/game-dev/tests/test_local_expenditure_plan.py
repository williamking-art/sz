# -*- coding: utf-8 -*-
"""M34-① 地方支出 V2 **只读预报层** 契约回归（钱账未接线，见开工门台账）。

背景：州郡府库 `prefectures[路]["local_treasury"]` 现状**只有流入与平籴**（买粮＝资产形态
转换），**消费性支用＝0**（行政/治安/水利/救灾/仓廪一条都没接）。V2 先落**只读预报层**：
`GameStateEconMixin.calc_local_expenditure()` 把"若接线将要花多少"提前算出——
五科目应支 → 预算封顶 → 计划额 → 缺口，**只报不记**（不写府库/POP/statistics）。

本文件断言（不写前端源码文本断言）：
1. 恒等式：`due ≡ Σ五科目`、`cap ≡ ⌊府库 × cap_share⌋`、`plan ≡ min(due, cap)`、
   `shortfall ≡ due − plan`、总额 ≡ Σ逐路；
2. 科目①行政 ≡ 本路官俸 × `LOCAL_EXP_ADMIN_SHARE`（挂既有派生量，不新造税基）；
3. 按可付截断：府库为 0 的路 → `plan == 0` 且 `shortfall == due`（穷路不得凭空支付）；
4. 救灾只在**灾月·灾路**出现（`disaster_severity>0` 且路命中 `disaster_region`）；
5. `finance_readout()["local_expenditure"]` 与派生同源，且**不并入 `total_out`**（不双计）；
6. 只读纪律：两个入口调用前后，国库/府库/POP/statistics 深快照一致。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import pytest  # noqa: E402

from content.data import (LOCAL_EXP_ADMIN_SHARE, LOCAL_EXP_CAP_SHARE,  # noqa: E402
                          LOCAL_EXP_RELIEF_PER_CAPITA)
from core.game_state import GameState  # noqa: E402

_KINDS = ("official_salary", "clerk_pay", "runner_pay", "public_supply",
          "granary", "relief")


def _state():
    return GameState("史实")


def _snapshot(s):
    return {
        "treasury": int(getattr(s, "treasury", 0) or 0),
        "stats": copy.deepcopy(dict(s.statistics)),
        "prefs": copy.deepcopy(s.prefectures),
    }


def test_plan_identity_and_fields():
    s = _state()
    plan = s.calc_local_expenditure()
    for k in ("cap_share", "disaster", "by_kind", "total_due", "total_plan",
              "total_shortfall", "by_route"):
        assert k in plan, f"缺字段 {k}"
    assert plan["cap_share"] == pytest.approx(LOCAL_EXP_CAP_SHARE)
    assert set(plan["by_kind"]) == set(_KINDS)
    sum_due = 0
    for name, row in plan["by_route"].items():
        assert row["due"] == sum(row[k] for k in _KINDS), f"{name} due ≠ Σ科目"
        assert row["cap"] == int(row["coffer"] * LOCAL_EXP_CAP_SHARE), f"{name} cap 口径不符"
        assert row["plan"] == min(row["due"], row["cap"]), f"{name} plan ≠ min(due, cap)"
        assert row["shortfall"] == row["due"] - row["plan"], f"{name} 缺口等式不成立"
        sum_due += row["due"]
    assert plan["total_due"] == sum_due
    assert plan["total_plan"] == sum(r["plan"] for r in plan["by_route"].values())
    assert plan["total_shortfall"] == plan["total_due"] - plan["total_plan"]
    # 开局：五科目应支 > 0（费率初值下每条通道都有量），缺口＝due−plan ≥ 0
    assert plan["total_due"] > 0 and plan["total_shortfall"] >= 0


def test_official_salary_kind_tracks_official_cash_share():
    """科目① 官员俸禄必须挂**既有派生量**（本路官俸 × 份额），不得新造税基。"""
    s = _state()
    _, by_route = s.calc_official_cash()
    plan = s.calc_local_expenditure()
    for name, row in plan["by_route"].items():
        assert row["official_salary"] == int(by_route.get(name, 0) * LOCAL_EXP_ADMIN_SHARE), \
            f"{name} 官员俸禄应支与官俸口径不同源"


def test_clerk_pay_kind_tracks_route_clerks():
    """科目② 胥吏雇钱必须挂**既有派生量**（本路吏额 × 吏月俸 × 份额）。"""
    from content.data import CLERK_PAY_PER_MONTH, LOCAL_EXP_CLERK_SHARE
    from core.domains.administration import officialdom as _officialdom
    s = _state()
    plan = s.calc_local_expenditure()
    for name, row in plan["by_route"].items():
        expect = int(float(_officialdom.route_clerks(s.prefectures[name]))
                     * CLERK_PAY_PER_MONTH * LOCAL_EXP_CLERK_SHARE)
        assert row["clerk_pay"] == expect, f"{name} 胥吏雇钱与吏额口径不同源"


def test_poor_route_is_capped_and_records_shortfall():
    """府库为空的路：`plan == 0`（不凭空支付），缺口全额记入 `shortfall`（只报不记）。"""
    s = _state()
    poor = min(s.prefectures)
    s.prefectures[poor]["local_treasury"] = 0
    row = s.calc_local_expenditure()["by_route"][poor]
    assert row["due"] > 0
    assert row["cap"] == 0 and row["plan"] == 0
    assert row["shortfall"] == row["due"]


def test_relief_only_in_disaster_route():
    s = _state()
    base = s.calc_local_expenditure()
    assert base["disaster"] == {"severity": 0, "region": ""}
    assert all(r["relief"] == 0 for r in base["by_route"].values()), "非灾月不得有救灾应支"
    assert base["by_kind"]["relief"] == 0

    hit = min(s.prefectures)
    s.disaster_severity = 3
    s.disaster_region = hit
    plan = s.calc_local_expenditure()
    assert plan["disaster"] == {"severity": 3, "region": hit}
    pop = sum(int((v or {}).get("size", 0) or 0)
              for v in (s.prefectures[hit].get("pops") or {}).values()
              if isinstance(v, dict))
    assert plan["by_route"][hit]["relief"] == int(pop * LOCAL_EXP_RELIEF_PER_CAPITA * 3)
    assert all(plan["by_route"][n]["relief"] == 0
               for n in plan["by_route"] if n != hit), "非灾路不得分摊救灾"
    assert plan["by_kind"]["relief"] > 0


def test_readout_exposes_plan_without_double_count(monkeypatch):
    """读数暴露计划额，但 `total_out` 必须与计划额**无关**（地方/中央不同主体，不得双计）。"""
    s = _state()
    out = s.finance_readout()
    assert out["local_expenditure"] == s.calc_local_expenditure()
    assert out["local_expenditure"]["total_plan"] > 0
    baseline_out = out["total_out"]

    huge = copy.deepcopy(out["local_expenditure"])
    huge["total_plan"] = 10 ** 9
    monkeypatch.setattr(s, "calc_local_expenditure", lambda: huge)
    out2 = s.finance_readout()
    assert out2["local_expenditure"]["total_plan"] == 10 ** 9
    assert out2["total_out"] == baseline_out, "地方支出计划额不得并入国库 total_out"


def test_plan_layer_is_readonly():
    s = _state()
    before = _snapshot(s)
    s.calc_local_expenditure()
    s.finance_readout()
    assert _snapshot(s) == before, "预报层必须只读：不得改动国库/府库/POP/statistics"
