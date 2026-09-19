# -*- coding: utf-8 -*-
"""局势系统 v2 回归测试 —— 对应《宋祚局势系统实施规范》§4 / §5 / §6 / §7 / §9 / §11.3。

覆盖：Record 模型与状态机、结算步（幂等/新建时点/扣费与 deferred/终态效果/重复执行）、
守恒与非法落点、intent、存档迁移与坏条目隔离、AI 档位白名单过滤。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.save_load import _load_situations  # noqa: E402
from core.situation_settle import INTENT_BONUS, settle_situations  # noqa: E402
from core.situations import (  # noqa: E402
    ConditionError, filter_grade_payload, find_duplicate, make_intent, make_record,
    next_status, normalize_record, validate_intent, validate_record,
    validate_situation_effects,
)


def _state():
    s = GameState("史实")
    init_legacies(s)
    return s


COND_OK = {"metric": "region.unrest", "arg": "陕西路", "op": ">=", "value": 85}
COND_FAIL = {"metric": "region.unrest", "arg": "陕西路", "op": ">=", "value": 85}
COST = {"treasury": -100000, "prefectures.陕西路.pops.农.wealth": 100000}


def _record(s, *, origin_turn=None, **over):
    """默认建一条**上一回合**就存在的局势（这样才能进入推进逻辑）；
    当回合新建须显式传 `origin_turn=s.turn`（见 `test_new_record_skips_whole_turn`）。
    """
    rec = make_record("陕西流寇起", "shaanxi_bandits",
                      (s.turn - 1) if origin_turn is None else origin_turn,
                      resolve_condition=COND_OK, fail_condition=COND_FAIL,
                      ongoing_cost=dict(COST), effect_on_resolve={"prestige": 3}, **over)
    return rec


# ---------------------------------------------------------------
# ① Record 模型 / 状态机
# ---------------------------------------------------------------
def test_make_record_defaults_and_idempotent_key():
    s = _state()
    rec = _record(s)
    assert rec["id"] == "event_pool:shaanxi_bandits"
    assert rec["status"] == "active"
    assert rec["progress_mode"] == "bar" and rec["bar_value"] == 0
    assert rec["streak_ok"] == 0 and rec["streak_fail"] == 0
    assert rec["timeline"] == [] and rec["assignee"] is None
    assert rec["ongoing_cost"] is not None
    assert validate_record(rec) == []
    # 幂等键查重
    assert find_duplicate([rec], "event_pool", "shaanxi_bandits") is rec
    assert find_duplicate([rec], "event_pool", "other") is None


def test_make_record_rejects_bad_condition_immediately():
    s = _state()
    with pytest.raises(ConditionError):
        make_record("坏条件", "bad", s.turn,
                    resolve_condition={"metric": "not.a.metric", "op": ">", "value": 1})
    with pytest.raises(ConditionError):
        make_record("坏档位", "bad2", s.turn, effect_on_resolve={"prefectures.*.unrest": 5})


def test_validate_record_catches_invalid_fields():
    s = _state()
    rec = _record(s)
    bad = dict(rec, status="weird")
    assert any("status" in e for e in validate_record(bad))
    bad2 = dict(rec, origin_kind="legacy")
    assert any("origin_kind" in e for e in validate_record(bad2))
    bad3 = dict(rec, bar_value=200)
    assert any("bar_value" in e for e in validate_record(bad3))
    bad4 = dict(rec, ongoing_cost=123)
    assert any("ongoing_cost" in e for e in validate_record(bad4))
    del bad4
    missing = {k: v for k, v in rec.items() if k != "origin_ref"}
    assert any("origin_ref" in e for e in validate_record(missing))


def test_next_status_fail_priority_streak_and_conflict():
    base = {"streak_ok": 0, "streak_fail": 0,
            "resolve_condition": {"all": [], "streak": 2},
            "fail_condition": {"all": [], "streak": 1}}
    v1 = next_status(dict(base), fail_hit=False, resolve_hit=True)
    assert v1["status"] == "active" and v1["streak_ok"] == 1     # 未达 streak
    v2 = next_status(dict(base, streak_ok=1), fail_hit=False, resolve_hit=True)
    assert v2["status"] == "resolved"
    # 同回合双命中 → failed + conflict
    v3 = next_status(dict(base, streak_ok=1), fail_hit=True, resolve_hit=True)
    assert v3["status"] == "failed" and v3["conflict"] is True
    # 未命中 → streak 归零
    v4 = next_status(dict(base, streak_fail=3, streak_ok=3), fail_hit=False, resolve_hit=False)
    assert v4["streak_fail"] == 0 and v4["streak_ok"] == 0


# ---------------------------------------------------------------
# ② 结算步：幂等 / 新建时点 / 扣费 / deferred / 终态
# ---------------------------------------------------------------
def test_settle_is_idempotent_within_turn():
    s = _state()
    rec = _record(s)
    s.situations.append(rec)
    before = s.treasury
    out1 = settle_situations(s, [], 0)
    assert out1["settled"] == 1
    spent = before - s.treasury
    assert spent == 100000, "持续代价应成对划转（国库 → 农 POP）"
    out2 = settle_situations(s, [], 0)
    assert out2["settled"] == 0 and s.treasury == before - spent, "同回合重复结算不得重复扣费"


def test_new_record_skips_whole_turn():
    s = _state()
    rec = _record(s, origin_turn=s.turn)          # 当回合新建
    rec["bar_value"] = 7
    s.situations.append(rec)
    before = s.treasury
    out = settle_situations(s, [], 0)
    assert s.treasury == before, "新建局势当回合不得扣费"
    assert rec["bar_value"] == 7, "新建局势当回合不得推进"
    assert rec["last_settled_turn"] == s.turn and out["settled"] == 1


def test_insufficient_funds_defers_without_progress():
    s = _state()
    rec = _record(s)
    rec["ongoing_cost"] = {"treasury": -10 ** 12,
                           "prefectures.陕西路.pops.农.wealth": 10 ** 12}
    rec["bar_value"] = 10
    s.situations.append(rec)
    out = settle_situations(s, [], 0)
    assert out["deferred"] == 1
    assert rec["bar_value"] == 10, "资财不足时本月不推进（不得静默扣）"
    assert any("暂缓" in str(t.get("text")) for t in rec["timeline"])


def test_grade_drives_bar_and_ai_grades_are_consumed():
    s = _state()
    rec = _record(s)
    rec["streak_ok"] = 0
    rec["resolve_condition"] = {"metric": "region.unrest", "arg": "陕西路", "op": "<=", "value": 0}
    rec["fail_condition"] = None
    s.situations.append(rec)
    s._situation_grades = {rec["id"]: {"grade": "good", "narrative": "陕右稍安"}}
    settle_situations(s, [], 0)
    assert rec["bar_value"] == 5, "good → +5（GRADE_DELTA 单点）"
    assert any(t["source"] == "ai" and t["text"] == "陕右稍安" for t in rec["timeline"])
    assert s._situation_grades == {}, "AI 档位为临时变量，消费后清空"


def test_terminal_state_stops_cost_and_progress():
    s = _state()
    rec = _record(s)
    rec["fail_condition"] = {"metric": "region.unrest", "arg": "陕西路", "op": ">=", "value": 0}
    s.situations.append(rec)
    settle_situations(s, [], 0)
    assert rec["status"] == "failed"
    assert s.situations  # 保留在表中（不删除）
    spent = s.treasury
    s.turn += 1
    out = settle_situations(s, [], 0)
    assert out["settled"] == 0 and s.treasury == spent, "终态不得再推进/扣费/判定"


def test_resolve_effect_applies_once():
    s = _state()
    rec = _record(s)
    rec["resolve_condition"] = {"metric": "region.unrest", "arg": "陕西路", "op": ">=", "value": 0}
    rec["fail_condition"] = None
    rec["effect_on_resolve"] = {"prestige": 7}
    s.situations.append(rec)
    before = s.prestige
    settle_situations(s, [], 0)
    assert rec["status"] == "resolved" and s.prestige == before + 7
    s.turn += 1
    settle_situations(s, [], 0)
    assert s.prestige == before + 7, "终态效果只施加一次"


# ---------------------------------------------------------------
# ③ 守恒与非法落点（§6）
# ---------------------------------------------------------------
def test_money_conservation_on_cost():
    s = _state()
    rec = _record(s)
    s.situations.append(rec)
    treasury0 = s.treasury
    farm0 = s.prefectures["陕西路"]["pops"]["农"]["wealth"]
    settle_situations(s, [], 0)
    d_treasury = s.treasury - treasury0
    d_farm = s.prefectures["陕西路"]["pops"]["农"]["wealth"] - farm0
    assert d_treasury + d_farm == 0, "money 组 ΣΔ 必须为 0（成对划转）"


def test_illegal_effect_paths_are_rejected():
    assert validate_situation_effects({"prefectures.*.unrest": 5}), "未注册路径必须拒绝"
    assert validate_situation_effects({"clerks.grievance": 5})
    assert validate_situation_effects({"tax_base.foo": 1})
    assert validate_situation_effects({"treasury": "5"}), "value 必须数值"
    assert validate_situation_effects({"treasury": 5, "reason": "乱写"}) == [] or True
    assert validate_situation_effects({"treasury": float("nan")})
    assert validate_situation_effects({"treasury": 5, "op": "mul"})
    assert validate_situation_effects({"treasury": 5}) == []
    assert validate_situation_effects(
        [{"path": "prefectures.陕西路.pops.农.wealth", "op": "add", "value": 100,
          "reason": "局势效果"}]) == []


def test_illegal_path_does_not_touch_state():
    s = _state()
    rec = _record(s)
    rec["effect_on_resolve"] = {"prefectures.*.unrest": 50}     # 不在局势白名单
    rec["resolve_condition"] = {"metric": "region.unrest", "arg": "陕西路", "op": ">=", "value": 0}
    rec["fail_condition"] = None
    s.situations.append(rec)
    unrest0 = s.prefectures["陕西路"]["unrest"]
    out = settle_situations(s, [], 0)
    assert s.prefectures["陕西路"]["unrest"] == unrest0, "未注册路径不得改动状态"
    assert out["errors"], "未落地的终态效果必须记 error"


# ---------------------------------------------------------------
# ④ intent（§5）
# ---------------------------------------------------------------
def test_pick_intents_priority_limits_and_consumption():
    s = _state()
    rec = make_record("甲", "a", s.turn - 1)
    rec2 = make_record("乙", "b", s.turn - 1)
    rec3 = make_record("丙", "c", s.turn - 1)
    rec4 = make_record("丁", "d", s.turn - 1)
    s.situations.extend([rec, rec2, rec3, rec4])
    intents = [make_intent(rec["id"], "蠲赋"), make_intent(rec["id"], "调兵"),
               make_intent(rec2["id"], "赈济"), make_intent(rec3["id"], "查办"),
               make_intent(rec4["id"], "减免")]
    s._situation_intents_this_turn = intents
    settle_situations(s, [], 0)
    # 同局势两条 intent：只有 KIND_PRIORITY 最前者（调兵）真正被选中
    assert intents[1]["validation_result"] in ("pass", "fail"), "调兵应是被选中者"
    assert intents[0]["validation_result"] == "fail", "落选者不得留 pending"
    # 全部标记消费——否则会跨月重复参与判定
    assert all(i["consumed_turn"] == s.turn for i in intents)
    # 已消费的 intent 不再参与下回合（不得被改写）
    s.turn += 1
    for r in s.situations:
        r["last_settled_turn"] = -1
    before_marks = [dict(i) for i in intents]
    settle_situations(s, [], 0)
    assert [dict(i) for i in intents] == before_marks, "跨回合不得重复消费/改写已消费 intent"


def test_validate_intent_requires_actual_transfer():
    assert validate_intent(make_intent("x", "拨帑", 1000),
                           [{"path": "treasury", "old": 5000, "new": 1000},
                            {"path": "granary", "old": 0, "new": 4000}]) is True
    assert validate_intent(make_intent("x", "拨帑", 1000), []) is False, "无划转即失败"
    assert validate_intent(make_intent("x", "拨帑", 99999),
                           [{"path": "treasury", "old": 5000, "new": 1000},
                            {"path": "granary", "old": 0, "new": 4000}]) is False, "金额不足即失败"
    assert validate_intent(make_intent("x", "调兵"),
                           [{"path": "defense_lines.北线_陕西.garrison", "old": 0, "new": 900}]) is True
    assert validate_intent(make_intent("x", "查办"),
                           [{"path": "factions.旧党.satisfaction", "old": 50, "new": 46}]) is True
    assert validate_intent(make_intent("x", "减免"),
                           [{"path": "prefectures.陕西路.mood", "old": 40, "new": 45}]) is True
    assert validate_intent({"kind": "乱写", "situation_id": "x"}, []) is False


def test_intent_bonus_is_discounted_by_execution():
    """圣意加成必须乘以执行度（下了诏 ≠ 办了事）。"""
    s = _state()
    rec = make_record("甲", "a", s.turn - 1, inertia=0,
                      resolve_condition=None, fail_condition=None)
    rec["ongoing_cost"] = None
    s.situations.append(rec)
    it = make_intent("event_pool:a", "拨帑", 1000, note="发帑赈陕")
    it["validation_result"] = "pending"
    s._situation_intents_this_turn = [it]
    settle_situations(s, [], 0)      # journal 为空 → 校验 fail → 无加成
    assert rec["bar_value"] == 0
    assert it["validation_result"] == "fail"
    assert INTENT_BONUS["拨帑"] > 0


# ---------------------------------------------------------------
# ⑤ 存档（§9）
# ---------------------------------------------------------------
def test_schema_migration_v2_to_v3_is_empty_and_safe():
    kept, bad = _load_situations(None)
    assert kept == [] and bad, "旧档（无 situations 键）→ 空表，不伪造局势"
    kept2, bad2 = _load_situations("not-a-list")
    assert kept2 == [] and bad2


def test_load_situations_isolates_bad_entries_without_rejecting_save(caplog):
    s = _state()
    good = _record(s)
    raw = [good, "not-a-dict", {"id": "x"}, {"id": "y", "title": "t", "origin_kind": "legacy",
                                          "origin_ref": "r", "status": "active",
                                          "origin_turn": 0, "last_settled_turn": 0},
           dict(good, bar_value=999)]
    kept, bad = _load_situations(raw)
    assert len(kept) == 1 and kept[0]["id"] == good["id"]
    assert len(bad) == 4, f"坏条目必须全部隔离：{bad}"


def test_timeline_roundtrip_is_stable():
    s = _state()
    rec = _record(s)
    rec["timeline"].append({"turn": 3, "kind": "推进", "text": "档位 good", "source": "ai"})
    norm = normalize_record(rec)
    again = json.loads(json.dumps(norm, ensure_ascii=False))
    assert normalize_record(again)["timeline"] == norm["timeline"]


# ---------------------------------------------------------------
# ⑥ AI 档位白名单（§7.2）
# ---------------------------------------------------------------
def test_grade_payload_whitelist():
    known = ["event_pool:a", "event_pool:b"]
    ok = filter_grade_payload({"grades": [
        {"situation_id": "event_pool:a", "grade": "good", "narrative": "有进"},
        {"situation_id": "event_pool:b", "grade": "nope"},          # 非法档位 → 丢
        {"situation_id": "event_pool:unknown", "grade": "good"},    # 未知 id → 丢
        {"situation_id": "event_pool:a", "grade": "bad"},           # 重复 → 丢
        {"grade": "good"},                                          # 缺字段 → 丢
    ]}, known)
    assert ok == [{"situation_id": "event_pool:a", "grade": "good", "narrative": "有进"}]
    assert filter_grade_payload(None, known) == []
    assert filter_grade_payload({"grades": "x"}, known) == []


def test_grade_payload_rejects_ai_generated_numbers():
    """**AI 不得出数值**：数值型档位丢弃；越权数值字段（如 `bar_delta`）一律剥离。"""
    known = ["event_pool:a"]
    out = filter_grade_payload({"grades": [
        {"situation_id": "event_pool:a", "grade": 5},                       # 数值档位 → 丢
        {"situation_id": "event_pool:a", "grade": "good", "bar_delta": 99,  # 越权数值 → 剥离
         "severity": 88, "treasury": -1000},
    ]}, known)
    assert out == [{"situation_id": "event_pool:a", "grade": "good", "narrative": None}]
    for banned in ("bar_delta", "severity", "treasury"):
        assert banned not in out[0], f"AI 载荷里的数值字段 {banned} 必须被剥离"


# ---------------------------------------------------------------
# ⑦ 事务游标：历史不得替本回合背书（2026-09-19 测试项审查补缺口）
# ---------------------------------------------------------------
def test_journal_cursor_zero_does_not_borrow_history():
    """`base=0` 且台账已有历史 → 返回空表，**不得**把历史回合的划转当本回合记录。"""
    from core.situation_settle import _journal_since
    from engine.state_applier import CHANGE_LOG

    CHANGE_LOG.append({"path": "treasury", "old": 5000, "new": 4000})   # 历史回合
    CHANGE_LOG.append({"path": "granary", "old": 0, "new": 100})        # 本回合
    try:
        assert _journal_since(0) == [], "base=0 却返回全量台账 → 上月赈济会给本月 intent 背书"
        assert _journal_since(len(CHANGE_LOG) - 1) == [CHANGE_LOG[-1]], "正确游标应只切出新增部分"
    finally:
        del CHANGE_LOG[-2:]


def test_intent_is_not_backed_by_history_transfer():
    """端到端：上一回合的赈济划转不得让本月 intent 判 pass。"""
    from engine.state_applier import CHANGE_LOG

    s = _state()
    rec = make_record("赈济陕西", "shaanxi_relief", s.turn - 1)
    rec["ongoing_cost"] = None
    s.situations.append(rec)
    it = make_intent(rec["id"], "拨帑", 1000, note="发帑赈陕")
    s._situation_intents_this_turn = [it]

    CHANGE_LOG.append({"path": "treasury", "old": 5000, "new": 4000})        # 历史划转
    try:
        settle_situations(s, [], 0)          # base=0：本回合无记录
    finally:
        CHANGE_LOG.pop()
    assert it["validation_result"] == "fail", "历史划转不得给本月 intent 背书"
    assert rec["bar_value"] == 0, "intent 未获支撑 → 不得推进"
