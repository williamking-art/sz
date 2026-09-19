# -*- coding: utf-8 -*-
"""局势结算审查修复回归（2026-09-19）：P1-5 终态效果原子提交 / P1-6 progress_cost / P1-7 deadline。

锁定三件事（对应审查报告「必须补充的回归测试」第 1/2/3 条）：
  1. 终态效果**原子提交**：效果未落地时不得写 resolved/failed（不假完成），
     保留 active + `pending_terminal`，下月可重试并最终真实落地；
  2. `progress_cost` 是**推进费用**：只有扣费成功才推进 bar；资源不足 / 守恒破坏
     一律不推进（不得"先推进后扣费"）；与 `ongoing_cost`（扣不起整月 deferred）语义分离；
  3. `deadline`：`turn >= deadline` 仍未 resolve → 逾期失败并应用 `effect_on_fail`；
     优先级固定 `fail_condition > resolve_condition > deadline`（`turn == deadline`
     仍可 resolve，是"最后机会"回合）。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState                    # noqa: E402
from core.legacy_mechanic import init_legacies           # noqa: E402
from core.situation_settle import settle_situations      # noqa: E402
from core.situations import (                            # noqa: E402
    deadline_reached, make_record, validate_record,
)


def _state():
    s = GameState("史实")
    init_legacies(s)
    return s


COND_ALWAYS = {"metric": "region.unrest", "arg": "陕西路", "op": ">=", "value": 0}
COND_NEVER = {"metric": "region.unrest", "arg": "陕西路", "op": ">=", "value": 10 ** 9}
PAIR = {"treasury": -100000, "prefectures.陕西路.pops.农.wealth": 100000}
BAD_PATH = {"prefectures.*.unrest": 50}          # 未注册落点 → 必被拒


def _rec(s, *, origin_turn=None, **over):
    """默认：无持续代价、无失败条件、达成条件恒假（隔离到本文件关注的通道）。"""
    over.setdefault("ongoing_cost", None)
    over.setdefault("fail_condition", None)
    over.setdefault("resolve_condition", COND_NEVER)
    return make_record("陕西流寇起", "shaanxi_bandits",
                       (s.turn - 1) if origin_turn is None else origin_turn, **over)


def _grade(s, rec, grade="good"):
    s._situation_grades = {rec["id"]: {"grade": grade, "narrative": ""}}


def _farm(s):
    return s.prefectures["陕西路"]["pops"]["农"]["wealth"]


# =====================================================================
# P1-5 · 终态效果原子提交
# =====================================================================
def test_terminal_effect_failure_is_not_a_fake_completion():
    s = _state()
    rec = _rec(s, resolve_condition=COND_ALWAYS)
    rec["effect_on_resolve"] = dict(BAD_PATH)   # 绕过建单校验 → 模拟落地期才失败
    s.situations.append(rec)
    unrest0 = s.prefectures["陕西路"]["unrest"]
    out = settle_situations(s, [], 0)
    assert rec["status"] == "active", "效果未落地不得写终态（假完成）"
    assert rec["pending_terminal"] == "resolved", "须记住待落地的终态意图"
    assert out["resolved"] == 0 and out["effect_pending"] == 1
    assert out["errors"], "未落地的终态效果必须留可诊断错误"
    assert s.prefectures["陕西路"]["unrest"] == unrest0, "被拒效果不得改动状态"


def test_terminal_effect_can_be_retried_next_turn():
    s = _state()
    rec = _rec(s, resolve_condition=COND_ALWAYS)
    rec["effect_on_resolve"] = dict(BAD_PATH)   # 绕过建单校验 → 模拟落地期才失败
    s.situations.append(rec)
    out1 = settle_situations(s, [], 0)
    assert rec["status"] == "active" and out1["effect_pending"] == 1

    rec["effect_on_resolve"] = {"prestige": 7}           # 修好效果源
    before = s.prestige
    s.turn += 1
    out2 = settle_situations(s, [], 0)
    assert rec["status"] == "resolved" and rec["pending_terminal"] is None
    assert out2["resolved"] == 1 and not out2["errors"]
    assert s.prestige == before + 7, "重试成功后效果必须真实落地"


def test_pending_effect_is_idempotent_within_turn():
    s = _state()
    rec = _rec(s, resolve_condition=COND_ALWAYS)
    rec["effect_on_resolve"] = dict(BAD_PATH)   # 绕过建单校验 → 模拟落地期才失败
    s.situations.append(rec)
    settle_situations(s, [], 0)
    out2 = settle_situations(s, [], 0)
    assert out2["settled"] == 0 and out2["effect_pending"] == 0, "同回合不得重复尝试"


# =====================================================================
# P1-6 · progress_cost（推进费用）
# =====================================================================
def test_progress_cost_charged_only_when_advancing():
    s = _state()
    rec = _rec(s, progress_cost=dict(PAIR), bar_value=0)
    s.situations.append(rec)
    _grade(s, rec)
    t0, f0 = s.treasury, _farm(s)
    out = settle_situations(s, [], 0)
    assert rec["bar_value"] == 5, "扣费成功才推进（good → +5）"
    assert s.treasury == t0 - 100000 and _farm(s) == f0 + 100000, "推进费用成对划转"
    assert (s.treasury - t0) + (_farm(s) - f0) == 0, "money 组 ΣΔ 必须为 0"
    assert out["stalled"] == 0


def test_progress_cost_insufficient_funds_stalls_without_advancing():
    s = _state()
    rec = _rec(s, progress_cost={"treasury": -10 ** 12,
                                 "prefectures.陕西路.pops.农.wealth": 10 ** 12})
    s.situations.append(rec)
    _grade(s, rec)
    t0 = s.treasury
    out = settle_situations(s, [], 0)
    assert rec["bar_value"] == 0, "资源不足不得推进"
    assert out["stalled"] == 1 and out["deferred"] == 0, "推进费用失败不算整月 deferred"
    assert s.treasury == t0, "不得静默扣"
    assert any("停滞" in str(t.get("text")) for t in rec["timeline"])


def test_progress_cost_conservation_break_stalls():
    s = _state()
    rec = _rec(s, progress_cost={"treasury": -100000})     # 单边 → 守恒硬拒绝
    s.situations.append(rec)
    _grade(s, rec)
    t0 = s.treasury
    out = settle_situations(s, [], 0)
    assert rec["bar_value"] == 0 and out["stalled"] == 1
    assert s.treasury == t0


def test_no_progress_cost_keeps_backward_compatible_advance():
    s = _state()
    rec = _rec(s)                                        # progress_cost=None
    s.situations.append(rec)
    _grade(s, rec)
    out = settle_situations(s, [], 0)
    assert rec["bar_value"] == 5 and out["stalled"] == 0, "未定义推进费用不得阻碍推进"


def test_ongoing_cost_shortage_defers_before_progress_cost():
    """持续代价不足 → 整月 deferred，**不**进入推进费用环节（语义分离）。"""
    s = _state()
    rec = _rec(s, ongoing_cost={"treasury": -10 ** 12,
                                "prefectures.陕西路.pops.农.wealth": 10 ** 12},
               progress_cost=dict(PAIR), bar_value=3)
    s.situations.append(rec)
    _grade(s, rec)
    out = settle_situations(s, [], 0)
    assert out["deferred"] == 1 and out["stalled"] == 0
    assert rec["bar_value"] == 3


# =====================================================================
# P1-7 · deadline
# =====================================================================
def test_deadline_reached_semantics():
    assert deadline_reached({"deadline": None}, 99) is False
    assert deadline_reached({}, 5) is False
    assert deadline_reached({"deadline": 5}, 4) is False
    assert deadline_reached({"deadline": 5}, 5) is True
    assert deadline_reached({"deadline": 5}, 6) is True
    assert deadline_reached({"deadline": "坏值"}, 6) is False, "非法值按未定义处理（不抛）"
    assert deadline_reached({"deadline": True}, 6) is False


def test_deadline_overdue_fails_and_applies_fail_effect():
    s = _state()
    rec = _rec(s, deadline=s.turn, effect_on_fail={"prestige": -3})
    s.situations.append(rec)
    before = s.prestige
    out = settle_situations(s, [], 0)
    assert rec["status"] == "failed" and out["failed"] == 1
    assert s.prestige == before - 3, "逾期失败必须应用 effect_on_fail"


def test_deadline_equal_turn_still_resolves():
    s = _state()
    rec = _rec(s, deadline=s.turn, resolve_condition=COND_ALWAYS,
               effect_on_resolve={"prestige": 2})
    s.situations.append(rec)
    before = s.prestige
    out = settle_situations(s, [], 0)
    assert rec["status"] == "resolved", "turn == deadline 是最后机会：resolve 优先"
    assert out["resolved"] == 1 and s.prestige == before + 2


def test_deadline_vs_fail_condition_fail_wins():
    s = _state()
    rec = _rec(s, deadline=s.turn, fail_condition=COND_ALWAYS,
               effect_on_fail={"prestige": -1})
    s.situations.append(rec)
    out = settle_situations(s, [], 0)
    assert rec["status"] == "failed" and out["failed"] == 1, "fail_condition 优先于 deadline"


def test_deadline_not_reached_keeps_active():
    s = _state()
    rec = _rec(s, deadline=s.turn + 3)
    s.situations.append(rec)
    out = settle_situations(s, [], 0)
    assert rec["status"] == "active" and out["failed"] == 0


def test_deadline_overdue_with_unlanded_effect_keeps_active_for_retry():
    """P1-5 × P1-7：逾期判失败但失败效果落不了地 → 不假完成、留待重试。"""
    s = _state()
    rec = _rec(s, deadline=s.turn)
    rec["effect_on_fail"] = {"prefectures.*.unrest": 9}   # 落地期必失败
    s.situations.append(rec)
    out = settle_situations(s, [], 0)
    assert rec["status"] == "active" and rec["pending_terminal"] == "failed"
    assert out["effect_pending"] == 1 and out["failed"] == 0


def test_validate_record_deadline_and_pending_terminal():
    s = _state()
    rec = _rec(s)
    assert validate_record(dict(rec, deadline=5)) == []
    assert any("deadline" in e for e in validate_record(dict(rec, deadline="x")))
    assert validate_record(dict(rec, pending_terminal="resolved")) == []
    assert any("pending_terminal" in e
               for e in validate_record(dict(rec, pending_terminal="weird")))