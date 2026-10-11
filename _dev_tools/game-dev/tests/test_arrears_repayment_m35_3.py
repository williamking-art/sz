# -*- coding: utf-8 -*-
"""M35-3《欠给补发与恢复机制》契约回归。

裁决口径（用户 2026-10-11）：建立「财政改善 → 补发欠给 → 压力下降 → 治理恢复」闭环。
- **接口**：`repay_local_arrears()`（**不自动调用**）；**不直接改欠给**——资金走账户划转
  （`money.ACCOUNTS` 口径），Σ 货币守恒；
- **来源**：① 路级府库 surplus（默认）② 中央拨款（`source="treasury"`）；
- **顺序**：沿用 D7′ 刚性等级（一级 clerk_pay/runner_pay/public_supply → 二级 official_salary），
  **不做自动公平分配**；
- **效果**：只减 欠给／月数／压力；**不**降 corruption/grip/unrest（"欠钱解决 ≠ 立即清廉"）。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import money  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.settlement_finance import (  # noqa: E402
    _settle_finance, _settle_local_expenditure, repay_local_arrears)


def _drive(s, rk, times=4):
    for _ in range(times):
        s.prefectures[rk]["local_treasury"] = 0
        _settle_local_expenditure(s, [])


def _arrears(s, rk, kind):
    pops = s.prefectures[rk]["pops"]
    return {"official_salary": int(pops["官僚"].get("officials_salary_arrears", 0) or 0),
            "clerk_pay": int(pops["官僚"].get("clerks_pay_arrears", 0) or 0),
            "runner_pay": int(pops["兵"].get("runners_pay_arrears", 0) or 0)}[kind]


def _pop_wealth(s):
    return sum(int((v or {}).get("wealth", 0) or 0)
               for p in s.prefectures.values()
               for v in (p.get("pops") or {}).values() if isinstance(v, dict))


def test_repayment_conserves_money_and_reduces_arrears():
    """补发＝真实资金流转：Σ 货币守恒；欠给减少、月数下降、压力下降。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, times=4)
    assert _arrears(s, rk, "clerk_pay") > 0
    months0 = s.prefectures[rk]["arrears_months"]["clerk_pay"]
    pressure0 = s.identity_pressures()["by_route"][rk]["clerk_pressure"]
    s.prefectures[rk]["local_treasury"] = 10 ** 9          # 先注资（测试侧），再取基准
    arr0 = int(s.statistics["local_arrears"])
    m0, wealth0 = money.m_all(s), _pop_wealth(s)

    ret = repay_local_arrears(s, route=rk)
    assert ret["repaid"] > 0
    assert money.m_all(s) == m0, "补发必须 Σ 货币守恒（账户划转，不造币）"
    assert _pop_wealth(s) > wealth0, "补发的钱必须落到债权人 POP"
    assert int(s.statistics["local_arrears"]) < arr0, "欠给总额必须减少"
    assert s.prefectures[rk]["arrears_months"]["clerk_pay"] <= months0, "月数须下降"
    assert (s.identity_pressures()["by_route"][rk]["clerk_pressure"] < pressure0), \
        "压力是派生量 ⇒ 补发后应下降"
    assert int(s.prefectures[rk]["local_treasury"]) < 10 ** 9


def test_repayment_does_not_lower_grip_or_unrest():
    """补发**不直接**降腐败/把持/动乱（欠钱解决 ≠ 官吏立即清廉）。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, times=4)
    grip0 = float((s.prefectures[rk].get("clerks_detail") or {}).get("grip", 0.0) or 0.0)
    unrest0 = float(s.prefectures[rk].get("unrest", 0.0) or 0.0)
    s.prefectures[rk]["local_treasury"] = 10 ** 9
    repay_local_arrears(s, route=rk)
    assert float((s.prefectures[rk].get("clerks_detail") or {}).get("grip", 0.0) or 0.0) \
        == grip0, "补发不得直接降把持度"
    assert float(s.prefectures[rk].get("unrest", 0.0) or 0.0) == unrest0, \
        "补发不得直接降动乱"


def test_repayment_does_not_touch_population_or_grain():
    """六桶人口/粮耗不受影响（补发只动 wealth 与欠给账）。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, times=3)
    snap = {cls: (int(pool.get("size", 0) or 0), int(pool.get("grain", 0) or 0))
            for cls, pool in s.prefectures[rk]["pops"].items()
            if isinstance(pool, dict)}
    s.prefectures[rk]["local_treasury"] = 10 ** 9
    repay_local_arrears(s, route=rk)
    for cls, pool in s.prefectures[rk]["pops"].items():
        if isinstance(pool, dict):
            assert (int(pool.get("size", 0) or 0), int(pool.get("grain", 0) or 0)) == snap[cls], \
                f"{cls} 人口/粮耗不得被补发改动"



def test_repayment_follows_d7_priority():
    """**顺序＝D7′ 刚性等级**：现金有限时，一级（clerk_pay）先得，二级（official_salary）才及。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, times=4)
    assert _arrears(s, rk, "clerk_pay") > 0 and _arrears(s, rk, "official_salary") > 0
    s.prefectures[rk]["local_treasury"] = 10 ** 9
    ret = repay_local_arrears(s, route=rk, amount=1000)          # 只够一级
    assert ret["by_kind"].get("clerk_pay", 0) == 1000, "有限现金必须先补一级（胥吏雇钱）"
    assert ret["by_kind"].get("official_salary", 0) == 0, "二级（官俸）不得越级"
    # 显式 kinds 体现**制度选择**（不做自动公平分配）
    s.prefectures[rk]["local_treasury"] = 10 ** 9
    ret2 = repay_local_arrears(s, route=rk, amount=500, kinds=["official_salary"])
    assert ret2["by_kind"].get("official_salary", 0) == 500
    assert ret2["by_kind"].get("clerk_pay", 0) == 0


def test_treasury_source_conserves_and_reaches_pops():
    """中央拨款来源：国库→府库→POP；Σ 货币守恒；欠给减少。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, times=3)
    s.treasury = max(int(s.treasury), 10 ** 7)               # 先注资（测试侧），再取基准
    m0, wealth0 = money.m_all(s), _pop_wealth(s)
    arr0 = int(s.statistics["local_arrears"])
    tre1 = int(s.treasury)
    ret = repay_local_arrears(s, route=rk, source="treasury", amount=2000)
    assert ret["repaid"] > 0 and ret["source"] == "treasury"
    assert money.m_all(s) == m0, "中央拨款补发同样必须 Σ 守恒"
    assert int(s.treasury) < tre1, "国帑须实付（而非凭空）"
    assert _pop_wealth(s) > wealth0 and int(s.statistics["local_arrears"]) < arr0


def test_repayment_not_called_automatically():
    """**暂不自动调用**：常规月度结算不得自行补发（由诏令/AI 显式触发）。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, times=3)
    repaid0 = int(s.statistics.get("local_arrears_repaid", 0) or 0)
    s.prefectures[rk]["local_treasury"] = 10 ** 9        # 即便府库充裕
    _settle_finance(s, [])
    assert int(s.statistics.get("local_arrears_repaid", 0) or 0) == repaid0, \
        "结算不得自动补发欠给（须显式调用 repay_local_arrears）"


def test_recovery_capacity_readout():
    """AI 接口：可补发额／欠给规模／优先级齐备；且为只读。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, times=3)
    cap = s.arrears_recovery_capacity()
    row = cap["by_route"][rk]
    for k in ("coffer_surplus", "treasury_available", "arrears_by_kind",
              "arrears_total", "months", "pressure", "priority"):
        assert k in row
    assert row["priority"][0] == "clerk_pay", "优先级＝D7′ 级序（一级在前）"
    assert cap["total"]["arrears_total"] > 0
    assert cap["total"]["routes_over_3_months"] >= 1
    assert s.finance_readout()["arrears_recovery_capacity"]["total"]["arrears_total"] > 0
    before = copy.deepcopy(s.prefectures)
    s.arrears_recovery_capacity()
    assert copy.deepcopy(s.prefectures) == before, "补发能力读数必须只读"


def test_repayment_survives_save_load():
    """存档兼容：欠给/月数/累计补发经存读往返保持一致（无新增 schema）。"""
    from core.save_load import load_game, save_game
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, times=3)
    s.prefectures[rk]["local_treasury"] = 10 ** 9
    repay_local_arrears(s, route=rk)
    slot = 6
    assert save_game(s, slot=slot)
    loaded = load_game(slot=slot)
    assert loaded is not None
    assert int(loaded.statistics.get("local_arrears", 0) or 0) == \
        int(s.statistics.get("local_arrears", 0) or 0)
    assert int(loaded.statistics.get("local_arrears_repaid", 0) or 0) == \
        int(s.statistics.get("local_arrears_repaid", 0) or 0)
    lp = loaded.prefectures.get(rk) or {}
    assert (lp.get("arrears_months") or {}) == (s.prefectures[rk].get("arrears_months") or {})
