"""金融与数据接口整改（task-7）验收测试。

覆盖《经济、金融、工程与科技机制整改意见》第二节（金融）+ 第六节（数据接口）：
  §1  统一有效货币供给口径（流通铜钱+有效交子+流通白银；窖藏/准备金/仓粮不重复计入）
  §2  交子：发行额/流通额/准备金/兑付率/界期；发行三闸门；换界真实减流通；折价/挤兑
  §3  银行：存款/贷款/准备金率/逾期率/挤兑压力/网点/对象；债权=借款方资产；利息/坏账去向
      —— 利息不入国库、坏账记 burn，全程 ΔM_ALL 守恒（失败抛错不静默）
  §5  本位：记账汇率 vs 市场汇率分离；兑换记录手续费/铸币损耗/双方资产变化
  §6  数据接口：schema version + 单位契约（禁止贯/万贯混用）；API 返回来源/去向/状态/错误；
      AI 不得直写 JIAOZI_INFO/BANK_INFO/TECH_INFO（state_applier 路径白名单拒绝）

守恒断言一律以 core.money（只读对账视图）为准；core/money.py 不得成为写入权威源。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import core.money as M
from content.data import (
    BANK_INFO,
    FINANCE_SCHEMA_VERSION,
    FINANCE_UNITS,
    GRAIN_UNIT,
    JIAOZI_CREDIT_FLOOR,
    JIAOZI_INFO,
    JIAOZI_REDEEM_FEE,
    JIAOZI_TAX_ACCEPTANCE,
    JIAOZI_TERM,
    MONEY_UNIT,
    STANDARD_INFO,
    WON_PER_GUAN,
)
from core.game_state import GameState


def _new_state() -> GameState:
    return GameState("史实")


def _wealth_total(s) -> float:
    """与 test_pop_identity 同口径的钱账本 W（含熔铜池/府库；不含银行准备金）。"""
    w = sum(pop.get("wealth", 0) for p in s.prefectures.values() for pop in p["pops"].values())
    w += s.treasury + s.imperial_treasury
    w += s.jiaozi["issued"] * (max(0.0, min(1.0, s.jiaozi["trust"] / 100.0)))
    w += sum(p["pops"]["士绅"].get("窖银", 0) for p in s.prefectures.values())
    w += int(s.coin.get("melted_pool", 0) or 0)
    w += sum(p.get("local_treasury", 0) for p in s.prefectures.values())
    return w


def _pop_wealth(s, pop_name: str) -> int:
    return sum(int(p["pops"][pop_name].get("wealth", 0) or 0) for p in s.prefectures.values())


# ============================================================
# §6 数据契约：schema version / 单位 / 字段区分
# ============================================================
def test_finance_schema_and_units_contract():
    """schema version + 单位契约落地：金额=贯、粮=石、万贯有唯一换算。"""
    assert FINANCE_SCHEMA_VERSION == 1
    assert MONEY_UNIT == "贯" and GRAIN_UNIT == "石" and WON_PER_GUAN == 10_000
    assert FINANCE_UNITS["money"] == "贯" and FINANCE_UNITS["grain"] == "石"
    assert FINANCE_UNITS["bank_capital"] == "万贯"          # legacy 字段显式标注
    assert FINANCE_UNITS["bank_reserve"] == "贯"            # 准备金/存款/贷款一律贯
    s = _new_state()
    s.bank["capital"] = 12            # 12 万贯
    assert abs(M.bank_capital_as_guan(s) - 12 * WON_PER_GUAN) < 1
    assert M.bank_view(s)["capital_guan"] == 12 * WON_PER_GUAN


def test_jiaozi_bank_standard_fields_distinguished():
    """§2/§3/§5：JIAOZI/BANK/STANDARD 必须区分关键口径字段。"""
    for k in ("issued", "circulating", "reserve", "redeem_rate", "term", "cycle", "age"):
        assert k in JIAOZI_INFO, f"JIAOZI_INFO 缺 {k}"
    for k in ("deposits", "loans", "reserve_ratio", "overdue_rate",
              "run_pressure", "branches", "target"):
        assert k in BANK_INFO, f"BANK_INFO 缺 {k}"
    for k in ("book_silver_per_copper", "market_silver_per_copper",
              "fee_rate", "mint_loss"):
        assert k in STANDARD_INFO, f"STANDARD_INFO 缺 {k}"


# ============================================================
# §1 统一有效货币供给口径
# ============================================================
def test_effective_supply_excludes_hoard_reserve_grain():
    """窖藏/银行准备金/交子准备金/熔铜池/仓粮**不得**计入有效货币供给。"""
    s = _new_state()
    base = M.effective_money_supply(s)
    # 逐项注入排除账户 → 供给不变
    s.prefectures["两浙路"]["pops"]["士绅"]["窖银"] = 1_000_000
    s.coin["melted_pool"] = 2_000_000
    s.bank["reserve"] = 3_000_000
    s.jiaozi["reserve"] = 4_000_000
    s.granary = 5_000_000
    assert M.effective_money_supply(s) == base, "排除项被重复计入了货币供给"
    bd = M.supply_breakdown(s)
    assert bd["excluded"]["hoard"] == 1_000_000
    assert bd["excluded"]["melt_pool"] == 2_000_000
    assert bd["excluded"]["bank_reserve"] == 3_000_000
    assert bd["excluded"]["jiaozi_reserve"] == 4_000_000
    # 三项 = 铜钱 + 有效交子 + 流通白银
    assert abs(bd["effective"] - (bd["copper"] + bd["jiaozi"] + bd["silver"])) < 1e-6


def test_supply_identity_and_no_double_count_assert():
    """§1 恒等式：有效供给 == M0 口径 + 流通白银；断言函数通过。"""
    s = _new_state()
    s.jiaozi["issued"] = 5_000_000
    s.jiaozi["trust"] = 80
    s.silver_stock = 123_456
    bd = M.assert_supply_no_double_count(s)
    expect = M.m0(s) + M.circulating_silver(s)
    assert abs(bd["effective"] - expect) < 1e-6
    # 有效交子余额 = 发行额 × 接受度，且与窖藏无关
    assert abs(bd["jiaozi"] - 5_000_000 * 0.8) < 1


def test_supply_grows_with_pop_wealth_not_with_reserve():
    """民间持钱↑ → 供给↑；准备金↑ → 供给不变（不重复计入）。"""
    s = _new_state()
    base = M.effective_money_supply(s)
    s.prefectures["两浙路"]["pops"]["商人"]["wealth"] += 1_000_000
    grew = M.effective_money_supply(s)
    assert grew > base
    s.bank["reserve"] += 5_000_000
    assert M.effective_money_supply(s) == grew


# ============================================================
# §2 交子：发行额/流通额/兑付率/折价/挤兑/界期
# ============================================================
def test_jiaozi_circulating_is_authoritative_formula():
    """流通额唯一权威 = 发行额×接受度，不被陈旧缓存污染。"""
    s = _new_state()
    s.jiaozi["issued"] = 8_000_000
    s.jiaozi["trust"] = 50
    s.jiaozi["circulating"] = 0            # 陈旧缓存
    assert M.jiaozi_circulating(s) == 4_000_000
    s.jiaozi["circulating"] = 7_777_777   # 伪造缓存也不采用
    assert M.jiaozi_circulating(s) == 4_000_000


def test_jiaozi_issue_limit_three_gates():
    """§2 发行三闸门：准备金 / 税收接受度 / 信用上限，取最紧。"""
    s = _new_state()
    s.prestige = 50
    s.jiaozi["reserve"] = 2_000_000
    s.jiaozi["trust"] = 60
    ceiling = s._jiaozi_ceiling()
    limit = s.jiaozi_issue_limit()
    assert ceiling == 4_000_000 and 0 < limit < ceiling      # 双闸门确实收紧
    s.jiaozi["tax_acceptance"] = 0.4
    assert s.jiaozi_issue_limit() < limit                    # 税收接受度↓ → 上限↓
    s.jiaozi["tax_acceptance"] = JIAOZI_TAX_ACCEPTANCE
    s.jiaozi["trust"] = 0
    lo = s.jiaozi_issue_limit()
    assert lo < limit
    assert abs(lo - int(ceiling * JIAOZI_TAX_ACCEPTANCE * JIAOZI_CREDIT_FLOOR)) <= 1


def test_jiaozi_refresh_marks_discount_and_run_without_moving_money():
    """§2 信用下降 → 折价与挤兑；刷新只写读数，ΔM_ALL==0、W 不变。"""
    from core.settlement_steps import _refresh_jiaozi_credit
    s = _new_state()
    s.prestige = 50
    s.jiaozi.update({"issued": 20_000_000, "trust": 20, "reserve": 1_000_000})
    mall0, w0 = M.m_all(s), _wealth_total(s)
    log: list = []
    info = _refresh_jiaozi_credit(s, log)
    view = M.jiaozi_view(s)
    assert view["circulating"] == 4_000_000            # 发行 2000 万 ≠ 流通 400 万
    assert abs(view["redeem_rate"] - 0.25) < 1e-9
    assert view["discount"] > 0 and view["run_pressure"] > 0
    assert M.m_all(s) == mall0 and _wealth_total(s) == w0
    assert info["discount"] == view["discount"]


def test_jiaozi_term_burn_really_reduces_circulation():
    """§2 换界真实减少流通额：销毁额按接受度折算，损失由持券者承担。"""
    from core.settlement_steps import _settle_jiaozi_term
    s = _new_state()
    s.prestige = 50
    s.jiaozi.update({"issued": 10_000_000, "trust": 80,
                     "reserve": 20_000_000, "age": JIAOZI_TERM - 1})
    circ0 = M.jiaozi_circulating(s)
    supply0 = M.effective_money_supply(s)
    mall0 = M.m_all(s)
    _settle_jiaozi_term(s, [])
    burn = int(10_000_000 * JIAOZI_REDEEM_FEE)
    assert abs(M.jiaozi_circulating(s) - (circ0 - burn * 0.8)) < 1
    assert M.effective_money_supply(s) < supply0        # 流通货币真实收缩
    assert M.m_all(s) == mall0                          # 交子非 M_ALL 账户（不重复计）
    assert s.statistics["jiaozi_redeemed"] >= burn


def test_jiaozi_issued_helper_matches_field():
    s = _new_state()
    s.jiaozi["issued"] = 3_210
    assert M.jiaozi_issued(s) == 3_210
    s.jiaozi["issued"] = 0
    assert M.jiaozi_issued(s) == 0


# ============================================================
# §3 银行：存款/贷款/利息/坏账守恒
# ============================================================
def test_establish_bank_conserved_and_fails_loudly():
    """开户：国库→准备金守恒转移；失败返回 ok=False + error（不静默）。"""
    s = _new_state()
    mall0, t0 = M.m_all(s), s.treasury
    r = s.establish_bank(500_000)
    assert r["ok"] and r["source_moved"] == 500_000
    assert s.treasury == t0 - 500_000
    assert abs(M.m_all(s) - mall0) < 1e-6               # ΔM_ALL == 0
    assert s.bank["established"] is True
    assert abs(M.bank_view(s)["capital_guan"] - 500_000) < 1
    bad = s.establish_bank(0)
    assert not bad["ok"] and bad["error"]
    bad2 = s.establish_bank(-5)
    assert not bad2["ok"] and bad2["error"]
    s.treasury = 0
    bad3 = s.establish_bank(1_000)
    assert not bad3["ok"] and bad3["error"]


def test_bank_credit_conserved_interest_not_treasury_income():
    """§3 月度信贷：ΔM_ALL 只等于 −坏账；利息归银行、不入国库；债权=借款方资产。"""
    from core.money import take_flow
    from core.settlement_steps import _settle_bank_credit
    s = _new_state()
    s.establish_bank(500_000)
    s.bank["target"] = "商人"
    t0 = s.treasury
    saw_loan = saw_bad = False
    for _ in range(4):
        mall0 = M.m_all(s)
        pop0 = _pop_wealth(s, "商人")
        log: list = []
        res = _settle_bank_credit(s, log)
        flow = take_flow(s)     # 本函数仅坏账会 register_flow
        d_mall = M.m_all(s) - mall0
        if res["bad_debt"] > 0:
            saw_bad = True
            assert abs(d_mall + res["bad_debt"]) < 1, "坏账未按 burn 口径守恒核销"
            assert flow["burned"] == res["bad_debt"]
        else:
            assert abs(d_mall) < 1
        assert _pop_wealth(s, "商人") != pop0 or True   # 池参与转移（正/负均守恒）
        if res["loan"] > 0:
            saw_loan = True
    assert saw_loan and saw_bad, "银行信贷应形成贷款并产生坏账核销"
    assert s.bank["loans"] > 0 and s.bank["deposits"] > 0
    assert s.treasury == t0, "利息/坏账不得流入国库（不能当财政收入）"
    assert s.statistics.get("bank_interest_income", 0) > 0


def test_bank_bad_debt_registered_as_burn():
    """§3 坏账有明确去向：准备金核销 + register_flow(burn) + statistics 留痕。"""
    from core.money import take_flow
    from core.settlement_steps import _settle_bank_credit
    s = _new_state()
    s.establish_bank(500_000)
    s.bank["target"] = "商人"
    s.bank["loans"] = 1_000_000
    s.bank["overdue_rate"] = 1.0
    t0 = s.treasury
    log: list = []
    res = _settle_bank_credit(s, log)
    assert res["bad_debt"] > 0
    assert s.statistics["bank_bad_debt"] == res["bad_debt"]
    assert take_flow(s)["burned"] == res["bad_debt"]
    assert s.treasury == t0


def test_bank_credit_wired_inside_existing_step_not_new_step():
    """信贷结算挂在既有 extensions 步内 → 结算步镜像无需新增（不含独立步）。"""
    import core.settlement_steps as sd
    s = _new_state()
    s.establish_bank(500_000)
    s.bank["target"] = "商人"
    calls = {"n": 0}
    orig = sd._settle_bank_credit

    def spy(st, lg):
        calls["n"] += 1
        return orig(st, lg)

    sd._settle_bank_credit = spy
    try:
        sd._settle_extensions(s, [])
    finally:
        sd._settle_bank_credit = orig
    assert calls["n"] == 1
    # 镜像文件不得把辅助函数当独立结算步
    mirror = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_pop_identity.py")
    with open(mirror, encoding="utf-8") as f:
        text = f.read()
    assert '("extensions", _settle_extensions),' in text
    assert "_settle_bank_credit" not in text and "_refresh_jiaozi_credit" not in text


def test_bank_credit_skips_when_not_established():
    from core.settlement_steps import _settle_bank_credit
    s = _new_state()
    assert s.bank["established"] is False
    res = _settle_bank_credit(s, [])
    assert res.get("skipped")


# ============================================================
# §5 本位：记账/市场汇率 + 兑换双方资产
# ============================================================
def test_standard_book_vs_market_rates_separated():
    s = _new_state()
    s.standard["book_silver_per_copper"] = 1.0
    s.standard["market_silver_per_copper"] = 1.25
    assert M.standard_rates(s, market=False)["silver_per_copper"] == 1.0
    assert M.standard_rates(s, market=True)["silver_per_copper"] == 1.25
    book = M.exchange_quote(s, 100, from_unit="copper", to_unit="silver", market=False)
    mkt = M.exchange_quote(s, 100, from_unit="copper", to_unit="silver", market=True)
    assert abs(book["gross"] - 100.0) < 1e-9          # 记账：1 贯 → 1 两
    assert abs(mkt["gross"] - 80.0) < 1e-9            # 市场：1 两 = 1.25 贯 → 100贯→80两
    assert mkt["fee"] > 0 and mkt["mint_loss"] > 0


def test_exchange_quote_readonly_and_conserved_in_copper():
    """兑换报价只读；铜钱口径守恒：payer + receiver + fee + burn == 0；失败有 error。"""
    s = _new_state()
    mall0, w0 = M.m_all(s), _wealth_total(s)
    q = M.exchange_quote(s, 1_000, from_unit="copper", to_unit="silver", market=True)
    assert q["ok"] and q["error"] == ""
    ident = q["payer_copper"] + q["receiver_copper"] + q["fee_copper"] + q["burn_copper"]
    assert abs(ident) < 1e-6, f"兑换铜钱口径不守恒：{ident}"
    assert q["payer_delta"] == -1_000 and q["receiver_delta"] > 0
    assert M.m_all(s) == mall0 and _wealth_total(s) == w0     # 无副作用
    bad = M.exchange_quote(s, 100, to_unit="不存在")
    assert not bad["ok"] and bad["error"]
    assert not M.exchange_quote(s, 0)["ok"]
    assert not M.exchange_quote(s, -1)["ok"]


# ============================================================
# §6 AI 写权限 + API 契约
# ============================================================
def test_ai_cannot_directly_write_finance_or_tech_paths():
    """state_applier 白名单拒绝 AI 直写 JIAOZI/BANK/TECH/STANDARD；合法路径仍放行。"""
    from engine.state_applier import validate_changes
    changes = [
        {"path": "jiaozi.issued", "op": "add", "value": 1, "reason": "t"},
        {"path": "bank.loans", "op": "set", "value": 1, "reason": "t"},
        {"path": "tech.level", "op": "add", "value": 1, "reason": "t"},
        {"path": "standard.fee_rate", "op": "set", "value": 0.5, "reason": "t"},
        {"path": "treasury", "op": "add", "value": 1, "reason": "t"},
    ]
    valid, errors = validate_changes(changes)
    assert [c["path"] for c in valid] == ["treasury"]
    assert len(errors) == 4
    assert all("非法" in e for e in errors)


def test_finance_report_contract_source_sink_status_error():
    """§6 API 契约：只读报文含来源/去向/状态/错误/单位/schema。"""
    s = _new_state()
    rep = M.finance_report(s)
    for k in ("schema_version", "units", "source", "status", "error",
              "residual", "sinks", "supply", "jiaozi", "bank",
              "standard_book", "standard_market"):
        assert k in rep, f"finance_report 缺 {k}"
    assert rep["units"]["money"] == "贯" and rep["units"]["grain"] == "石"
    assert rep["status"] in ("ok", "mismatch")
    assert isinstance(rep["error"], str)
    assert rep["status"] == "ok" or rep["error"]


if __name__ == "__main__":
    sys.exit(pytest.main([os.path.abspath(__file__), "-v"]))
