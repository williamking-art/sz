# -*- coding: utf-8 -*-
"""抵当所（官营信贷）权限与旋钮端到端回归。

用户口径（2026-09-19）：旋钮不是"定义"，而是**权限**——跟**部门/官职**，人是载体；
经圣旨由掌权者执行。本文件锁定：
  1. 「官营放贷」事权归**户部**，且户部 authority 含它；
  2. 官职「抵当所提举」存在且有 holder（人不载权，换人不换权）；
  3. 5 个旋钮在 `INSTITUTION_PARAM_SPEC` 且值域受约束；
  4. 经既有改革通道（`free_effect` 的 institution）可改，未知键拒绝；
  5. 吸储**饱和**（不抽干民间 wealth）——240 月压力测试的核心结论。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import BANK_INFO, INSTITUTION_PARAM_SPEC  # noqa: E402
from content.ministers.data import AUTHORITY_MATTERS, CENTRAL_ORG_INFO  # noqa: E402
from core import institution as _inst  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402

_DIDANG_KNOBS = ("didang_reserve_ratio", "didang_loan_rate", "didang_loan_share",
                 "didang_deposit_share", "didang_deposit_cap")


def test_authority_belongs_to_org_and_office_not_person():
    """权限跟部门/官职：事权 owner=户部；户部 authority 含它；官职「抵当所提举」有 holder。"""
    assert AUTHORITY_MATTERS.get("官营放贷", {}).get("owner") == "户部", "官营放贷须归户部"
    hb = CENTRAL_ORG_INFO["户部"]
    assert "官营放贷" in hb["authority"], "户部 authority 须含官营放贷"
    titles = [p["title"] for p in hb["posts"]]
    assert "抵当所提举" in titles, "须有官职「抵当所提举」"
    assert hb["holders"].get("抵当所提举"), "该官职须有任职者（人是载体）"


def test_didang_knobs_declared_with_bounds():
    for k in _DIDANG_KNOBS:
        spec = INSTITUTION_PARAM_SPEC.get(k)
        assert isinstance(spec, dict), f"缺旋钮 {k}"
        assert spec["min"] < spec["max"] and "label" in spec


def test_knobs_adjustable_via_existing_reform_channel():
    """经既有改革通道调整（玩家/AI 同一入口）；未知键逐项拒绝。"""
    s = GameState("史实")
    before = _inst.get(s, "didang_loan_rate")
    log = _inst.apply_reform(s, {"didang_loan_rate": "=0.03"})
    assert log, "应留痕"
    assert _inst.get(s, "didang_loan_rate") == 0.03, "绝对值调整未生效"
    assert before != 0.03
    log2 = _inst.apply_reform(s, {"didang_not_exist": 1})
    assert any("拒绝" in x for x in log2), "未知键须拒绝"


def test_deposit_is_saturated_not_draining_pop_wealth():
    """吸储饱和：240 月后存款 ≤ 目标阶层财富 × cap（原无上限会抽干民间）。"""
    s = GameState("史实")
    s.establish_bank(2_000_000, "treasury")
    cap = float(_inst.get(s, "didang_deposit_cap", 0.30))
    for _ in range(240):
        run_monthly_settlement(s, 0)
    deposits = int(s.bank.get("deposits", 0) or 0)
    target = str(s.bank.get("target") or "商人")
    pool_w = sum(int((p.get("pops") or {}).get(target, {}).get("wealth", 0) or 0)
                 for p in s.prefectures.values())
    assert deposits <= int(pool_w * cap) + 1, (
        f"存款 {deposits:,} 超过上限 {int(pool_w * cap):,}（民间被抽干）")
    assert deposits > 0, "抵当所应确实吸储"


def test_bank_settlement_keeps_conservation_assertion():
    """抵当所月度结算含守恒自断言：不得凭空造币。"""
    s = GameState("史实")
    s.establish_bank(2_000_000, "treasury")
    for _ in range(12):
        run_monthly_settlement(s, 0)      # 内含 assert，抛错即失败
    assert s.bank.get("established")