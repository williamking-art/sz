# -*- coding: utf-8 -*-
"""抵当所（官营信贷）权限与旋钮端到端回归。

用户口径（2026-09-19）：旋钮不是"定义"，而是**权限**——跟**部门/官职**，人是载体；
经圣旨由掌权者执行。本文件锁定：
  1. 「官营放贷」事权归**户部**，且户部 authority 含它；
  2. 官职「抵当所提举」存在且有 holder（人不载权，换人不换权）；
  3. 5 个旋钮在 `INSTITUTION_PARAM_SPEC` 且值域受约束；
  4. 经既有改革通道（`free_effect` 的 institution）可改，未知键拒绝；
     **且须由掌「官营放贷」事权者执行**（机构/官职/任职人三种载体，未指定主体不能绕过）；
  5. 吸储**饱和**（不抽干民间 wealth）——240 月压力测试的核心结论。

用户口径（2026-09-19 turn 39/41）：「这些机制应该是做成权限或者工具让玩家通过**指定部门/人物**来执行，
而不是直接设定成定义」；「权限就是权限，跟的是**部门、官职**，**人只是载体**」（换人不换权）。
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
    """经既有改革通道调整（玩家/AI 同一入口，须指定执行主体）；未知键逐项拒绝。"""
    s = GameState("史实")
    before = _inst.get(s, "didang_loan_rate")
    log = _inst.apply_reform(s, {"didang_loan_rate": "=0.03"}, executor="户部")
    assert log, "应留痕"
    assert _inst.get(s, "didang_loan_rate") == 0.03, "绝对值调整未生效"
    assert before != 0.03
    log2 = _inst.apply_reform(s, {"didang_not_exist": 1}, executor="户部")
    assert any("拒绝" in x for x in log2), "未知键须拒绝"


# ---- 执行侧权限校验（用户口径：权限跟部门/官职，人是载体；圣旨须指定执行主体）----

def test_authority_executor_org_office_and_person_all_pass():
    """(i) 掌「官营放贷」的机构 / 官职 / 任职人（及三种 dict 写法）→ 生效并留痕。"""
    for executor in ("户部", "抵当所提举", "王古",
                     {"org": "户部"}, {"post": "抵当所提举"}, {"holder": "王古"}):
        s = GameState("史实")
        log = _inst.apply_reform(s, {"didang_loan_rate": "=0.03"}, executor=executor)
        assert _inst.get(s, "didang_loan_rate") == 0.03, f"{executor} 应可执行：{log}"
        assert any("0.03" in x for x in log), f"{executor} 应留痕：{log}"


def test_non_authority_executor_rejected_and_state_unchanged():
    """(ii) 非掌权者（他部机构 / 他部官职 / 无关之人）→ 逐项拒绝且状态不变。"""
    for executor in ("兵部", "礼部", "兵部尚书", "无名小卒",
                     {"org": "兵部"}, {"holder": "无名小卒"}):
        s = GameState("史实")
        before = _inst.get(s, "didang_loan_rate")
        log = _inst.apply_reform(s, {"didang_loan_rate": "=0.03"}, executor=executor)
        assert _inst.get(s, "didang_loan_rate") == before, f"{executor} 不应改到旋钮"
        assert any("拒绝" in x for x in log), log


def test_missing_executor_cannot_bypass():
    """(iii) 未指定执行主体 → 拒绝（玩家圣旨与 AI 提案走同一校验，不能绕过）。"""
    s = GameState("史实")
    before = _inst.get(s, "didang_loan_rate")
    log = _inst.apply_reform(s, {"didang_loan_rate": "=0.03"})
    assert _inst.get(s, "didang_loan_rate") == before
    assert any("未指定执行主体" in x for x in log), log


def test_vacant_office_cannot_execute():
    """官职载体须有人任职（人是载体）：户部侍郎空缺 → 该官职不得执行。"""
    s = GameState("史实")
    assert not str(s.central_orgs["户部"]["holders"].get("户部侍郎") or "").strip()
    before = _inst.get(s, "didang_loan_rate")
    log = _inst.apply_reform(s, {"didang_loan_rate": "=0.03"}, executor="户部侍郎")
    assert _inst.get(s, "didang_loan_rate") == before
    assert any("无人任职" in x for x in log), log


def test_power_follows_office_not_person():
    """换人不换权：holder 换人后，权随官职/机构走——新人可执行、无关之人被拒。"""
    s = GameState("史实")
    s.central_orgs["户部"]["holders"]["抵当所提举"] = "李四"
    log = _inst.apply_reform(s, {"didang_loan_rate": "=0.03"}, executor="李四")
    assert _inst.get(s, "didang_loan_rate") == 0.03, log

    s2 = GameState("史实")
    s2.central_orgs["户部"]["holders"]["抵当所提举"] = "李四"
    log2 = _inst.apply_reform(s2, {"didang_loan_rate": "=0.03"}, executor="张三")
    assert _inst.get(s2, "didang_loan_rate") == 0.01
    assert any("拒绝" in x for x in log2), log2

    # 官职载体本身不变（权在「抵当所提举」这个职位上）
    s3 = GameState("史实")
    s3.central_orgs["户部"]["holders"]["抵当所提举"] = "李四"
    _inst.apply_reform(s3, {"didang_loan_rate": "=0.03"}, executor="抵当所提举")
    assert _inst.get(s3, "didang_loan_rate") == 0.03


def test_params_without_authority_need_no_executor():
    """未标注 authority 的编制参数（六杠杆等）不受事权约束，照旧可直接改。"""
    s = GameState("史实")
    _inst.apply_reform(s, {"yinben_mult": "=1.4"})
    assert _inst.get(s, "yinben_mult") == 1.4


def test_free_effect_path_enforces_executor():
    """AI/诏令同一通道：`effects.institution` 经 free_effect 落地，执行侧校验一致。"""
    from core import free_effect as _fe

    ok = {"mode": "once", "effects": {"institution": {"didang_loan_rate": "=0.03"}},
          "executor": "户部"}
    assert _fe.validate_free_effect(ok) == ""
    s = GameState("史实")
    _fe._apply_free_effect(s, ok)
    assert _inst.get(s, "didang_loan_rate") == 0.03

    bad = {"mode": "once", "effects": {"institution": {"didang_loan_rate": "=0.03"}}}
    assert _fe.validate_free_effect(bad) == ""
    s2 = GameState("史实")
    log = _fe._apply_free_effect(s2, bad)
    assert _inst.get(s2, "didang_loan_rate") == 0.01, log
    assert any("执行主体" in x for x in log), log

    # executor 类型非法 → 整单拒绝（不落地）
    assert "executor" in _fe.validate_free_effect(
        {"mode": "once", "effects": {"institution": {"didang_loan_rate": "=0.03"}}, "executor": 123})


def test_longterm_effect_keeps_executor():
    """长期诏：执行主体随制度留存，月度复用仍校验（换人即随之失效）。"""
    from core import free_effect as _fe

    s = GameState("史实")
    _fe._apply_free_effect(s, {"mode": "ongoing", "duration": 6,
                               "effects": {"institution": {"didang_loan_rate": "=0.03"}},
                               "executor": "户部"})
    item = s.longterm_effects[-1]
    assert item.get("executor") == "户部"
    _fe._settle_free_effects(s, [])
    assert _inst.get(s, "didang_loan_rate") == 0.03



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