# -*- coding: utf-8 -*-
"""M34-① 批次 1 **财政顺序改造** 契约回归（裁决 2026-10-11）。

背景与口径（用户裁决）：
1. 宋代是「**地方先养活行政/治安/水利 → 剩余上供中央**」，不是「中央先拿走大头」；
2. 地方政府/官员要能**有效使用**府库资金（支用受治理状况调节，不是纯公式烧钱）；
3. 开局按史实（保障倍数 1.0），但**留接口**：玩家集权可经 `finance_rates` 诏令效果 /
   `apply_finance_reform` 调整 `local_expense_mult`（负担保障）与四率。

本文件断言：
1. 优先层：`留州 ≡ keep 腿 ＋ 必要支出优先层`，且优先层 ≤ 中央解送额（不透支、守恒不破）；
2. 支出腿：`Δ府库 ≡ 流入 − 支用`；府库不得为负；缺口 == `statistics["local_arrears"]` 增量；
3. 守恒：支用 ΣPOP 增额 ≡ 府库减额（`transfer_money` 单点，不造币）；
4. 官员有效使用：把持度高 → 有效使用率低（`efficacy` 下降、现实应支 `due_eff` 变小）；
5. 留接口：`apply_finance_reform({"local_expense_mult": -x})` 生效并钳制；集权（下调）后
   优先层变小 → 中央上供相应变多（"地方少保障、中央多拿"）。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import pytest  # noqa: E402

from content.data import (LOCAL_EXP_MULT_BASE, LOCAL_EXP_MULT_MAX,  # noqa: E402
                          LOCAL_EXP_MULT_MIN)
from core.commands import new_game  # noqa: E402
from core.settlement_finance import (_settle_finance,  # noqa: E402
                                     _settle_land_tax_color,
                                     _settle_local_expenditure)


def _local_total(s):
    return sum(int(p.get("local_treasury", 0) or 0) for p in s.prefectures.values())


def _pop_total(s):
    return sum(int((v or {}).get("wealth", 0) or 0)
               for p in s.prefectures.values()
               for v in (p.get("pops") or {}).values() if isinstance(v, dict))


def test_priority_layer_lands_in_local_and_bounded():
    """优先层：逐路 留州 ＝ keep 腿 ＋ 优先层；总量 == 返回；不透支（≤ 中央腿）。"""
    s = new_game()
    ret = _settle_land_tax_color(s, [])
    for rk, l in ret["local_by_route"].items():
        _t, k, _d = s.finance_split(rk)
        assert l == int(ret["by_route"][rk] * k) + ret["required_by_route"].get(rk, 0)
    assert sum(ret["required_by_route"].values()) == ret["required_landed"]
    assert ret["central"] >= 0 and ret["central"] + ret["local"] + ret["diverted"] == ret["collected"]
    assert s.statistics["land_tax_last"]["required"] == ret["required_landed"]
    assert s.statistics["land_tax_required"] == ret["required_landed"]


def test_local_expenditure_draws_only_from_coffer():
    """支出腿：只从府库出（不为负）；ΣPOP 增额 ≡ 支用额；缺口记欠支科目。"""
    s = new_game()
    loc0, pop0 = _local_total(s), _pop_total(s)
    arr0 = int(s.statistics.get("local_arrears", 0) or 0)
    ret = _settle_local_expenditure(s, [])
    assert _local_total(s) >= 0
    assert _local_total(s) - loc0 == -ret["paid"], "府库减额必须等于支用额"
    assert _pop_total(s) - pop0 == ret["paid"], "支用必须全额落到民间 POP（不造币、不销毁）"
    assert ret["arrears"] >= 0
    assert (int(s.statistics.get("local_arrears", 0) or 0) - arr0) == ret["arrears"]


def test_government_efficacy_mediates_spending():
    """官员**有效使用**：把持度（grip）高 → 有效使用率下降 → 现实应支变小。"""
    s = new_game()
    rk = min(s.prefectures)
    base = s.calc_local_expenditure()["by_route"][rk]
    assert 0.0 < base["efficacy"] <= 1.0
    s.prefectures[rk]["clerks_detail"] = dict(s.prefectures[rk].get("clerks_detail") or {},
                                              grip=1.0)
    after = s.calc_local_expenditure()["by_route"][rk]
    assert after["efficacy"] < base["efficacy"], "吏治把持高必须压低有效使用率"
    assert after["due_eff"] <= base["due_eff"], "有效使用率下降必须反映到现实应支"


def test_settlement_conserves_and_local_delta_matches_flows():
    """全管线：Δ府库 ≡ 留州流入 − 支用；且全程府库不为负。"""
    s = new_game()
    loc0 = _local_total(s)
    paid0 = int(s.statistics.get("local_expense_paid", 0) or 0)
    _settle_finance(s, [])
    inflow = int(s.statistics["land_tax_local"])
    outflow = int(s.statistics.get("local_expense_paid", 0) or 0) - paid0
    assert _local_total(s) - loc0 == inflow - outflow
    assert _local_total(s) >= 0


def test_centralization_interface_moves_the_priority_layer():
    """留接口：集权（下调 `local_expense_mult`）→ 优先层变小（中央多拿）；钳制到 [MIN, MAX]。"""
    s = new_game()
    before = _settle_land_tax_color(s, [])["required_landed"]

    s2 = new_game()
    s2.apply_finance_reform({"local_expense_mult": -0.6})       # 集权：保障降到 0.4
    assert s2.finance["local_expense_mult"] == pytest.approx(LOCAL_EXP_MULT_BASE - 0.6)
    after = _settle_land_tax_color(s2, [])["required_landed"]
    assert after < before, "集权后地方优先层必须变小"

    s3 = new_game()
    out = s3.apply_finance_reform({"local_expense_mult": 9.0})   # 越界 → 钳到 MAX
    assert out["applied"]["local_expense_mult"] == 9.0
    assert s3.finance["local_expense_mult"] == pytest.approx(LOCAL_EXP_MULT_MAX)
    s4 = new_game()
    s4.apply_finance_reform({"local_expense_mult": -9.0})
    assert s4.finance["local_expense_mult"] == pytest.approx(LOCAL_EXP_MULT_MIN)


def test_expense_mult_missing_falls_back_to_historical_default():
    """旧档（无该键）→ 史实默认 1.0（幂等；不得因缺键而 0＝地方责任全收中央）。"""
    s = new_game()
    s.finance.pop("local_expense_mult", None)
    plan = s.calc_local_expenditure()
    assert plan["expense_mult"] == pytest.approx(LOCAL_EXP_MULT_BASE)
    assert plan["total_due_eff"] > 0
