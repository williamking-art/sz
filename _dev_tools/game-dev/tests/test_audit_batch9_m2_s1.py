# -*- coding: utf-8 -*-
"""批次 9 回归：**M2** 加俸预算真实分账基金 ＋ **S1** 一次性诏令接通效果单点。

用户 2026-10-01 定稿：
  · M2 → (a) 拨帑时国库转池；发放时**池扣款 + 官吏 POP 收到对应收入**；
         `payraise_used` **不再重复计入** `total_out`；同步修正 `finance_readout`
         与旧的"设计内非闭合科目"清单。
  · S1 → (a) 接通 `core.decree_effect` 效果单点**与调兵强制施行**；
         `None`/读数未定义时**挂起并标明原因**，**不得回落 1.0、不得用默认值假装执行**，
         数据可用后再结算；强制施行仍受既定 30% 上限约束。
"""
import inspect
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState                # noqa: E402
from core.legacy_mechanic import init_legacies        # noqa: E402
from core.money import m_all                          # noqa: E402
from core.settlement import run_monthly_settlement    # noqa: E402


def _new() -> GameState:
    s = GameState("史实")
    init_legacies(s)
    return s


# ================================================================ M2
def test_m2_payraise_spend_is_money_neutral():
    """核心验收（源自报告）：拨帑后逐月发放**不得**凭空销毁钱（残差 ≤1）。"""
    X = 2_000_000
    a, b = _new(), _new()
    b.change_treasury(-X)
    b.payraise_budget += X                       # M_ALL 中性注入（国库 → 池）
    m0a, m0b = m_all(a), m_all(b)
    for _ in range(2):
        run_monthly_settlement(a)
        run_monthly_settlement(b)
    assert abs((m_all(b) - m0b) - (m_all(a) - m0a)) <= 1, \
        "加俸发放改变了 M_ALL 总量 ⇒同一笔钱被扣两次"
    assert abs(b.money_audit["cum_residual"]) <= 1, b.money_audit["cum_residual"]


def test_m2_payrise_reaches_official_pop_wealth():
    """收款腿必须真的落到**官僚 POP wealth**（不再是"钱出系统"）。"""
    s = _new()
    s.treasury = 500_000_000
    s.payraise_budget = 20_000_000
    before_w = sum(int(p["pops"]["官僚"].get("wealth", 0) or 0)
                   for p in s.prefectures.values())
    pool0 = int(s.payraise_budget)
    run_monthly_settlement(s)
    after_w = sum(int(p["pops"]["官僚"].get("wealth", 0) or 0)
                  for p in s.prefectures.values())
    assert after_w > before_w, "官僚 POP 未收到加俸（收款腿缺失）"
    paid = pool0 - int(s.payraise_budget)
    assert paid > 0, "预算池未按实付扣减"
    assert int(s.payraise_budget) >= 0, "池余额不得为负"
    # 收款额不得超发：池减额是受管管线记账的唯一一次扣减
    assert paid <= 20_000_000


def test_m2_pool_decremented_once_not_twice():
    """反回归：池**只被扣一次**（划转内部已扣，结算侧不得再手工扣第二遍）。"""
    from core import settlement_finance as SF
    src = inspect.getsource(SF)
    assert "payraise_budget = max(0" not in src, \
        "结算侧仍在手工扣池 ⇒ 与受管管线重复扣减（同 M2 原缺陷）"
    s = _new()
    s.treasury = 500_000_000
    s.payraise_budget = 10_000_000
    pool0 = int(s.payraise_budget)
    run_monthly_settlement(s)
    paid = pool0 - int(s.payraise_budget)
    want = min(pool0, int(s.calc_clerk_gap()[0]) + 10_000)
    assert paid == want, f"池减 {paid:,} 应等于当月发放额 {want:,}（不多扣、不少扣）"


def test_m2_not_double_counted_in_total_out():
    """`total_out` 不得再含 `payraise_used`（否则与国库发薪重复）。"""
    from core import settlement_finance as SF
    src = inspect.getsource(SF)
    assert "payraise_used + sui_gong" not in src, "`total_out` 仍含 payraise_used（重复计账）"
    from core.game_state import GameState as _GS
    rsrc = inspect.getsource(_GS.finance_readout)
    assert "payraise_used + sui_gong" not in rsrc, "读数侧仍同款双计"


def test_m2_pool_in_money_conservation_group():
    """池必须进 `MONEY_PATHS` 守恒组，否则发放腿无对手方、过不了守恒校验。"""
    from engine.state_applier import MONEY_PATHS
    assert "payraise_budget" in MONEY_PATHS, \
        "payraise_budget 未纳入钱组守恒 ⇒ 池→POP 的发放会被判「缺来源」而整批拒绝"


def test_m2_pool_is_whitelisted_in_applier():
    """池升级为真实分账基金后必须进受管管线白名单（否则资金流绕过 applier）。"""
    from engine.state_applier import NON_NEG_PREFIXES, VALID_PATHS
    assert "payraise_budget" in VALID_PATHS, "payraise_budget 未登记为可写路径"
    assert "payraise_budget" in NON_NEG_PREFIXES, "池余额须受非负约束"


def test_m2_empty_pool_is_noop():
    """池为空 → 不发放、不报错（缺失≠0 不得凭空生钱）。"""
    s = _new()
    s.treasury = 500_000_000
    w0 = sum(int(p["pops"]["官僚"].get("wealth", 0) or 0)
             for p in s.prefectures.values())
    run_monthly_settlement(s)
    w1 = sum(int(p["pops"]["官僚"].get("wealth", 0) or 0)
             for p in s.prefectures.values())
    assert w1 >= w0 and int(s.payraise_budget) == 0


def test_m2_pop_identity_list_no_longer_marks_payraise_as_leak():
    """旧的"设计内非闭合科目"清单须把加俸移出（否则口径自相矛盾）。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_pop_identity.py")
    head = open(path, encoding="utf-8").read()[:2000]
    assert "移出" in head and "payraise" in head, "非闭合科目清单未更新"


# ================================================================ S1
def _decree(**kw):
    d = {"title": "_TEST", "effects": {}, "duration": 0, "org_hint": "户部",
         "faction_stances": {}, "id": "d-test"}
    d.update(kw)
    return d


def test_s1_consumes_single_point(monkeypatch):
    """S1：一次性诏令**必须**经 `core.decree_effect` 口径单点（旧实现调用次数 = 0）。"""
    import core.decree_effect as DE
    import core.settlement_decree as SD
    seen = []
    orig = DE.decree_effect_mult

    def _spy(state, **kw):
        seen.append(kw)
        return orig(state, **kw)

    monkeypatch.setattr(DE, "decree_effect_mult", _spy)
    s = _new()
    s.pending_decrees.append(_decree())
    SD._settle_decrees(s, [])
    assert seen, "一次性诏令未消费效果单点（口径单点仍被破）"


def test_s1_forwards_enforce_troops(monkeypatch):
    """S1：`enforce_troops`（调兵强制施行）必须透传到单点（否则 +30% 杠杆永不生效）。"""
    import core.decree_effect as DE
    import core.settlement_decree as SD
    seen = []
    orig = DE.decree_effect_mult

    def _spy(state, **kw):
        seen.append(dict(kw))
        return orig(state, **kw)

    monkeypatch.setattr(DE, "decree_effect_mult", _spy)
    s = _new()
    s.pending_decrees.append(_decree(enforce_troops=True))
    SD._settle_decrees(s, [])
    assert seen and seen[0].get("enforce_troops") is True, \
        "调兵强制施行未透传给单点"


def test_s1_none_suspends_decree_with_reason(monkeypatch):
    """S1：单点返回 None → **挂起**（不执行、不生效、留原因），不得回落 1.0。"""
    import core.decree_effect as DE
    import core.settlement_decree as SD
    monkeypatch.setattr(DE, "decree_effect_mult", lambda *a, **k: None)
    s = _new()
    s.pending_decrees.append(_decree(effects={"treasury": 1000}))
    log = []
    SD._settle_decrees(s, log)
    assert any(d.get("id") == "d-test" for d in s.pending_decrees), \
        "未定义的诏令应退回待办（挂起），不得被丢弃或执行"
    assert int(s.statistics.get("decree_effect_undefined", 0)) >= 1, \
        "应记录挂起计数（可诊断）"
    assert any("挂起" in x for x in log), f"日志应标明挂起原因：{log}"
    assert any("未定义" in x or "异常" in x for x in log), "日志须写明原因"


def test_s1_no_fallback_to_one_in_source():
    """S1 反锁：不得再出现 `_grip_effective = 1.0` 这类「缺失即完美」的回落。"""
    from core import settlement_decree as SD
    src = inspect.getsource(SD._settle_decrees)
    assert "_grip_effective" not in src, "旧的 `_grip_effective` 仍在"
    assert "= 1.0" not in src, "不得把缺失读数回落为 1.0（缺失≠完美）"


def test_s1_defined_mult_is_applied(monkeypatch):
    """S1：单点给出的系数真的参与结算（返回 0.5 与 1.0 的执行结果应不同）。"""
    import core.decree_effect as DE
    import core.settlement_decree as SD
    s = _new()
    s.pending_decrees.append(_decree())
    monkeypatch.setattr(DE, "decree_effect_mult", lambda *a, **k: 0.5)
    calls = []
    monkeypatch.setattr(SD, "_apply_decree_effect",
                        lambda st, d, lg: calls.append(d.get("id")))
    SD._settle_decrees(s, [])
    # 概率路径：只要 rate 明显 < 1，多次调用应出现"受阻"；此处只验单点确实影响 rate
    # （用源码断言锁定 `rate = rate * _eff_mult_v`）
    src = inspect.getsource(SD._settle_decrees)
    assert "rate = rate * _eff_mult_v" in src, "单点系数未乘入执行率"


def test_s1_army_enforce_cap_still_30pct():
    """S1：调兵强制施行的补足上限仍为 30%（`ARMY_ENFORCE_BONUS`）。"""
    from core.decree_effect import ARMY_ENFORCE_BONUS
    assert ARMY_ENFORCE_BONUS == pytest.approx(0.30)


def test_s1_normal_decree_still_executes(monkeypatch):
    """S1 反向：读数可用时诏令照常执行（挂起不得变成"永不执行"）。"""
    import core.decree_effect as DE
    import core.settlement_decree as SD
    executed = []
    monkeypatch.setattr(DE, "decree_effect_mult", lambda *a, **k: 1.0)
    monkeypatch.setattr(SD, "_apply_decree_effect",
                        lambda st, d, lg: executed.append(d.get("id")))
    s = _new()
    s.calc_decree_execution_rate = lambda *a, **k: 1.0     # 去掉概率干扰，确定性验证
    s.pending_decrees.append(_decree())
    SD._settle_decrees(s, [])
    assert executed == ["d-test"], f"读数可用时应执行，实际 {executed}"
    assert int(s.statistics.get("decree_effect_undefined", 0)) == 0