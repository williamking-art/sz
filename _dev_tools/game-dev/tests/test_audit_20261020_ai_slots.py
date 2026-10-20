# -*- coding: utf-8 -*-
"""2026-10-20 全审修复批 2 · 天道槽位 + AI 契约（P0-4 / R-AI-1..9）定向回归。

一条一条钉住全审报告的问题（`_dev_tools/game-docs/reviews/宋祚全审报告_2026-10-20.md`）：

- **P0-4** 天道档位槽 `_decree_ai`/`_decree_execute_ai`：生产者盖 `_turn`、prefetch/注入前清槽、
  消费端带 `_turn` 只认本回合（无 `_turn` 的历史测试槽保持兼容）——修前「Jev 失败后新诏
  沿用上一道诏的长期/拖延」；
- **R-AI-1** `_inject_one` 按 `inspect.signature` 适配（`decree_duration_decide(state)` 不再假 `contract_failed`）；
- **R-AI-2** `_ai_failures` 每回合重建（修前跨回合累积＝面板永久假警报）；
- **R-AI-3** `simple` 档第二轮回合仍用精简工具面（修前回弹全量 10 工具）；
- **R-AI-4** `narrative_guard` 单位表补 两/斤/匹/顷/亩 + 无单位中文量级至少 flagged；
- **R-AI-5** `jev_gate` 非有限读数：不得当「有据」、不得判「低」；
- **R-AI-6** 任一 provider 自愈预算 ≤ 32000（思考型判定按模型名/端点能力，不只看 URL）；
- **R-AI-8** provider 纪律：异常 `log.warning`、重复注册去重、改写 state 被检出并回滚；
- **R-AI-9** 非 str/NaN 档位不抛且不落「最有利/最完美」档；缺档 completion 报 `None`（未定义）。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


# ---------------------------------------------------------------------------
# 最小 state 替身
# ---------------------------------------------------------------------------
class _State:
    def __init__(self, turn=None, **kw):
        self.prestige = 70
        self.population_satisfaction = 55
        self.treasury = 1_000_000
        self.imperial_treasury = 0
        self.granary = 2_000_000
        self.population = 50_000_000
        self.posture = "守成"
        self.pending_decrees = []
        if turn is not None:
            self.turn = turn
        for k, v in kw.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# P0-4 · 旧槽不得冒充本回合的天道裁决
# ---------------------------------------------------------------------------
def test_stale_decree_slot_not_honored():
    """上一回合（`_turn` 不符）的档位槽必须按缺失处理 —— 修前会整包沿用。"""
    from core.domains.politics.decree_duration import (resolve_decree_duration,
                                                       resolve_decree_timing,
                                                       resolve_execution_attitude)
    from core.domains.politics.edict_closure import resolve_landing_level

    s = _State(turn=5)
    s._decree_ai = {"_turn": 4, "pace": "缓", "execution_timing": "长期",
                    "execution_attitude": "拖延", "landing_level": "未办",
                    "timing_note": "上一道诏的结论"}

    tm = resolve_decree_timing(s, "pay_reform")
    assert tm["timing"] == "immediate", tm
    assert "效果键" in tm["source"], tm

    att = resolve_execution_attitude(s, decree_kind="pay_reform")
    assert att["level"] is None and att["source"] == "缺档", att

    dur = resolve_decree_duration(s, decree_kind="pay_reform", ability=60, followup=0)
    assert dur["pace"] == "常" and "缺档" in dur["source"], dur
    assert dur["timing"] == "immediate" and dur["months"] == 1, dur
    assert dur["execution_completion"] is None, "缺档不得回落「最完美执行 1.00」"

    lvl = resolve_landing_level(s, {"decree_id": "d2", "title": "加薪诏"})
    assert lvl["level"] is None and lvl["value"] is None, lvl


def test_execute_slot_stale_not_honored():
    """`_decree_execute_ai` 同规矩：带旧 `_turn` 的任务优先级/落地档不得采信。"""
    from core.domains.politics.decree_duration import _pace_from_ai
    from core.domains.politics.edict_closure import resolve_landing_level

    s = _State(turn=5)
    s._decree_execute_ai = {"_turn": 4, "tasks": [{"priority": "高"}],
                            "landing_level": "全办", "execution_timing": "长期"}
    pace, src = _pace_from_ai(s)
    assert pace == "常" and "缺档" in src, (pace, src)
    assert resolve_landing_level(s, {"decree_id": "d3"})["level"] is None


def test_current_turn_slot_honored():
    """本回合 `_turn` 的槽照旧采信（门控不能把正常链路一起关掉）。"""
    from core.domains.politics.decree_duration import resolve_decree_timing

    s = _State(turn=7)
    s._decree_ai = {"_turn": 7, "execution_timing": "长期"}
    got = resolve_decree_timing(s, "pay_reform")
    assert got["timing"] == "long" and got["source"] == "天道", got


def test_legacy_slot_without_turn_still_honored():
    """无 `_turn` 的旧槽（历史测试/历史代码路径）保持兼容 —— 不得把存量语义打断。"""
    from core.domains.politics.decree_duration import resolve_decree_timing

    s = _State(turn=7)
    s._decree_ai = {"execution_timing": "长期"}
    got = resolve_decree_timing(s, "pay_reform")
    assert got["timing"] == "long" and got["source"] == "天道", got


def test_prefetch_clears_stale_slot_on_jev_failure(monkeypatch):
    """P0-4 复现：先有旧槽 → Jev 不可用 → 新诏必须回程序口径（旧槽已被清掉）。"""
    from ai import jev_gate
    from application.decree_prefetch import prefetch_decree_slots
    from core.domains.politics.decree_duration import resolve_decree_duration

    monkeypatch.setattr(jev_gate, "decide_choice", lambda *a, **k: None)   # Jev 不可用

    s = _State(turn=5)
    s.pending_decrees = [{"decree_id": "d2", "title": "加薪诏", "category": "诏令",
                          "effects": {"pay_reform": "常"}}]
    s._decree_ai = {"_turn": 4, "execution_timing": "长期", "pace": "缓",
                    "execution_attitude": "拖延", "landing_level": "未办"}

    assert prefetch_decree_slots(s) is None
    assert not hasattr(s, "_decree_ai"), "Jev 失败后旧槽必须已清（不得沿用上一道诏）"

    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=60, followup=0)
    assert got["timing"] == "immediate", got
    assert "效果键" in got["timing_source"], got


def test_prefetch_success_stamps_current_turn(monkeypatch):
    """生产者成功时给产出盖本回合戳（消费端据此判定新鲜度）。"""
    from ai import jev_gate
    from application.decree_prefetch import prefetch_decree_slots

    monkeypatch.setattr(
        jev_gate, "decide_choice",
        lambda ctx, ins, crit, **k: ({"choice": "长期", "probabilities": {}, "confidence": None}
                                     if "即时" in crit else None))

    s = _State(turn=9)
    s.pending_decrees = [{"decree_id": "d1", "title": "加薪诏", "category": "诏令",
                          "effects": {"pay_reform": "常"}}]
    got = prefetch_decree_slots(s)
    assert got and s._decree_ai["_turn"] == 9, s._decree_ai


def test_inject_one_clears_decree_slot_when_contract_fails():
    """`_inject_one` 注入前清槽：本次推演失败 ⇒ 槽位是「未判」，不是上一回合的结论。"""
    from application.agent_router import _inject_one

    s = _State(turn=3)
    s._decree_ai = {"_turn": 2, "execution_timing": "长期"}

    class _Fail:
        def decree_duration_decide(self, state):
            return None

    failures: list = []
    assert _inject_one(s, _Fail(), failures, "decree_duration") is None
    assert not hasattr(s, "_decree_ai"), "契约失败必须留下空槽（缺失≠沿用旧档）"
    assert failures and failures[0]["error"] == "contract_failed", failures


def test_inject_one_stamps_turn_on_success():
    """注入成功的天道槽也盖本回合戳（生产者在别处可能没盖）。"""
    from application.agent_router import _inject_one

    s = _State(turn=4)

    class _Ok:
        def decree_duration_decide(self, state):
            return {"execution_timing": "即时"}

    failures: list = []
    assert _inject_one(s, _Ok(), failures, "decree_duration") == "decree_duration"
    assert failures == []
    assert s._decree_ai["_turn"] == 4, s._decree_ai


# ---------------------------------------------------------------------------
# R-AI-1 · 按签名适配调用（decree_duration_decide 不再假失败）
# ---------------------------------------------------------------------------
def test_inject_one_adapts_state_only_signature(monkeypatch):
    """探针 P2 复现：`decree_duration_decide(self, state)` 只吃 state，必须成功注入。"""
    from ai import jev_gate
    from ai.contracts_decree import DecreeContractMixin
    from application.agent_router import _inject_one

    def fake_choice(ctx, instructions, criteria, *, question_key="q"):
        # 每个问题都取 criteria 的第一个档位（速/即时/奉行/全办），全部合法
        return {"choice": next(iter(criteria)), "probabilities": {}, "confidence": None}

    monkeypatch.setattr(jev_gate, "decide_choice", fake_choice)

    class _Client(DecreeContractMixin):
        pass

    s = _State(turn=2)
    s.pending_decrees = [{"title": "加薪诏", "category": "诏令",
                          "effects": {"pay_reform": "常"}}]
    failures: list = []
    assert _inject_one(s, _Client(), failures, "decree_duration") == "decree_duration"
    assert failures == [], failures
    assert s._decree_ai["pace"] == "速" and s._decree_ai["_turn"] == 2, s._decree_ai


def test_inject_one_signature_matrix():
    """三种既有签名都要继续工作（state 优先，posture-only / posture+state 不回归）。"""
    from application.agent_router import _inject_one

    s = _State(turn=1)
    seen = {}

    class _Fake:
        def survey_settle(self, posture):                       # 无 state 形参
            seen["survey"] = posture
            return {"ok": 1}

        def diplomacy_decide(self, posture, state=None):        # posture + 可选 state
            seen["diplomacy"] = (posture, state is s)
            return {"ok": 1}

        def decree_duration_decide(self, state):                # 只有 state
            seen["duration"] = state is s
            return {"execution_timing": "即时"}

    failures: list = []
    assert _inject_one(s, _Fake(), failures, "survey") == "survey"
    assert _inject_one(s, _Fake(), failures, "diplomacy") == "diplomacy"
    assert _inject_one(s, _Fake(), failures, "decree_duration") == "decree_duration"
    assert seen["survey"] == "守成", seen
    assert seen["diplomacy"] == ("守成", True), seen
    assert seen["duration"] is True, seen
    assert failures == [], failures


# ---------------------------------------------------------------------------
# R-AI-2 · `_ai_failures` 每回合重建
# ---------------------------------------------------------------------------
def test_ai_failures_rebuilt_each_turn():
    """两回合连跑：第 2 回合失败表只含本回合 agent；无失败时为空（修前会累积）。"""
    from application.agent_router import inject_woken_agents

    s = _State(turn=1)
    s._ai_failures = [{"agent": "stale_agent", "error": "old_turn_failure"}]

    class _Fail:
        def diplomacy_decide(self, posture, state=None):
            return {"_error": "AI_CONTRACT_FAILED"}

    inject_woken_agents(s, _Fail(), ["diplomacy"])
    assert [f["agent"] for f in s._ai_failures] == ["diplomacy"], s._ai_failures

    s.turn = 2

    class _Ok:
        def diplomacy_decide(self, posture, state=None):
            return {"tone": "平和"}

    injected = inject_woken_agents(s, _Ok(), ["diplomacy"])
    assert injected == ["diplomacy"]
    assert s._ai_failures == [], "第二回合无失败 ⇒ 失败表必须为空（不得留上月假警报）"


# ---------------------------------------------------------------------------
# R-AI-3 · simple 档第二轮回合不回弹全量工具面
# ---------------------------------------------------------------------------
def test_simple_mode_second_round_keeps_simple_tools(monkeypatch):
    from ai import client as ai_client_mod
    from ai.client import AIClient
    from ai.client_utils import SIMPLE_TOOL_SCHEMAS, _TOOL_SCHEMAS

    c = AIClient("k", "https://api.example.com/v1", "gemini-3.8-flash", enable_tools="simple")
    seen = []
    replies = [
        {"content": "", "tool_calls": [{"id": "t1",
                                        "function": {"name": "check_treasury",
                                                     "arguments": "{}"}}]},
        "第二轮正文",
    ]

    def fake_call(*a, **k):
        seen.append(k.get("tools"))
        return replies[len(seen) - 1]

    monkeypatch.setattr(c, "_call", fake_call)
    monkeypatch.setattr(ai_client_mod, "_tool_dispatch",
                        lambda state, tcs, agent: [("t1", "库银充裕")])

    out = c._tool_roundtrip("sys", "user", _State(), "三省", 0.4, 700)
    assert out == "第二轮正文"
    assert len(seen) == 2, seen
    assert len(seen[0]) == len(SIMPLE_TOOL_SCHEMAS)
    assert seen[1] is SIMPLE_TOOL_SCHEMAS, "第二轮回合工具面回弹全量（R-AI-3）"
    assert len(seen[1]) < len(_TOOL_SCHEMAS)


# ---------------------------------------------------------------------------
# R-AI-4 · 叙事数值守卫：单位表 + 无单位中文量级
# ---------------------------------------------------------------------------
def test_narrative_guard_flags_units_beyond_table():
    """探针 P5 三条：三千匹/五千两/增兵三百万 修前全部 flagged=False。"""
    from ai.narrative_guard import _build_numeric_ranges, _validate_narrative_numbers

    ranges = _build_numeric_ranges(_State())
    for text in ("市易得绢三千匹", "岁入银五千两", "增兵三百万"):
        out, flagged = _validate_narrative_numbers(text, ranges)
        assert flagged is True, f"{text} 未标 flagged（out={out!r}）"


def test_narrative_guard_keeps_in_range_and_rewrites_overflow():
    """既有行为不回归：区间内保留、区间外改写定性词；小额无锚单位不刷 flagged。"""
    from ai.narrative_guard import _validate_narrative_numbers

    ranges = {"贯": (0, 100), "石": (0, 1000)}
    text, flag = _validate_narrative_numbers("府库得五十贯，赈济三百石。", ranges)
    assert flag is False and "五十贯" in text and "三百石" in text

    text2, flag2 = _validate_narrative_numbers("府库得900万贯。", ranges)
    assert flag2 is True and "900万贯" not in text2

    _t3, flag3 = _validate_narrative_numbers("得绢三匹、银二两。", ranges)
    assert flag3 is False, "小额无锚单位不该刷 flagged（噪音）"


# ---------------------------------------------------------------------------
# R-AI-5 · Jev 非有限读数
# ---------------------------------------------------------------------------
def test_jev_review_actions_nan_is_not_supported(monkeypatch):
    """NaN 与阈值比较恒 False ⇒ 修前被当成「原文有据」（漏检）；现按依据不足。"""
    from ai import jev_gate

    monkeypatch.setattr(jev_gate, "load_config",
                        lambda: {"enabled": True, "threshold": 0.5, "api_key": "x"})
    monkeypatch.setattr(jev_gate, "_decide",
                        lambda cfg, ctx, qs: {"answers": {"a0": {"noul": float("nan")}}})

    extra = jev_gate.review_actions("圣旨原文", [{"title": "斩来使", "source_fragment": "斩来使"}])
    assert extra, "NaN 读数不得当作「有据」（必须进 unresolved）"
    assert extra[0]["source_fragment"] == "斩来使"
    assert "无法判断" in extra[0]["reason"], extra


def test_jev_irreversibility_nan_returns_none(monkeypatch):
    """NaN 不得落 `tier="低"`（危险方向）；非有限 ⇒ 缺失返回 None。"""
    from ai import jev_gate

    monkeypatch.setattr(jev_gate, "load_config",
                        lambda: {"enabled": True, "threshold": 0.5, "api_key": "x"})
    monkeypatch.setattr(jev_gate, "_decide",
                        lambda cfg, ctx, qs: {"answers": {"q": {"noul": float("nan")}}})

    assert jev_gate.assess_irreversibility("原文", {"actions": [{"title": "开战"}]}) is None


# ---------------------------------------------------------------------------
# R-AI-6 · 预算口径（自愈封顶 / 思考型判定不只看 URL）
# ---------------------------------------------------------------------------
def test_self_heal_budget_capped_for_any_provider(monkeypatch):
    """探针 P7 复现：非 Agnes 端点自愈可到 32760；现任一 provider ≤ 32000。"""
    from ai.client import AIClient

    c = AIClient("k", "https://api.a6api.com/v1", "gemini-3.8-flash")
    calls = []

    def fake_post(payload, timeout=30):
        calls.append(payload.get("max_tokens"))
        body = {"choices": [{"message": {"content": "" if len(calls) == 1 else "复活"}}],
                "usage": {"total_tokens": 1}}
        return 200, body, ""

    monkeypatch.setattr(c, "_post_with_retry", fake_post)
    assert c._call_impl("sys", "user", max_tokens=4095) == "复活"
    assert len(calls) == 2, calls
    assert calls[0] == 4095, "非思考型端点不得改写首轮预算（既有行为）"
    assert calls[1] <= 32000, f"自愈预算超出上限：{calls[1]}"
    assert calls[1] >= 8192, calls[1]


def test_thinking_floor_by_model_name_not_url(monkeypatch):
    """思考型判定按**模型名**：代理端点（URL 不含 agnes）挂思考型模型仍要 8192 下限。"""
    from ai.client import AIClient

    c = AIClient("k", "https://api.a6api.com/v1", "agnes-2.5-flash")
    seen = {}

    def fake_post(payload, timeout=30):
        seen.update(payload)
        return 200, {"choices": [{"message": {"content": "好"}}], "usage": {"total_tokens": 1}}, ""

    monkeypatch.setattr(c, "_post_with_retry", fake_post)
    c._call_impl("sys", "user", max_tokens=300)
    assert seen["max_tokens"] == 8192, seen


# ---------------------------------------------------------------------------
# R-AI-8 · provider 纪律（异常留痕 / 去重 / 只读 state）
# ---------------------------------------------------------------------------
def test_timing_provider_exception_warns_and_falls_back(caplog):
    from core.domains.politics import decree_duration as dd

    s = _State(turn=1)

    def boom(st, kind):
        raise RuntimeError("provider down")

    dd.register_timing_provider(boom)
    try:
        with caplog.at_level(logging.WARNING, logger="core.decree_duration"):
            tm = dd.resolve_decree_timing(s, "pay_reform")
        assert tm["timing"] == "immediate" and "效果键" in tm["source"], tm
        assert any("provider" in r.getMessage() and "抛错" in r.getMessage()
                   for r in caplog.records), [r.getMessage() for r in caplog.records]
    finally:
        dd._TIMING_PROVIDERS.clear()


def test_attitude_provider_cannot_write_state(caplog):
    """provider 必须只读：改 state 标量 ⇒ 结果丢弃 + 标量回滚 + warning（修前被采信）。"""
    from core.domains.politics import decree_duration as dd

    s = _State(turn=1)

    def sneaky(st, kind, bene):
        st.treasury = 999_999
        return {"execution_attitude": "奉行", "note": "偷改国库"}

    dd.register_attitude_provider(sneaky)
    try:
        with caplog.at_level(logging.WARNING, logger="core.decree_duration"):
            att = dd.resolve_execution_attitude(s, decree_kind="pay_reform")
        assert att["level"] is None, "改写 state 的 provider 结果必须丢弃"
        assert s.treasury == 1_000_000, "被改写的标量必须回滚"
        assert any("只读" in r.getMessage() for r in caplog.records), \
            [r.getMessage() for r in caplog.records]
    finally:
        dd._ATTITUDE_PROVIDERS.clear()


def test_register_provider_dedupes():
    """模块级 provider 列表跨局共享 ⇒ 重复注册必须去重（否则叠加串档）。"""
    from core.domains.politics import decree_duration as dd

    def fn(st, kind):
        return None

    dd._TIMING_PROVIDERS.clear()
    try:
        dd.register_timing_provider(fn)
        dd.register_timing_provider(fn)
        assert len(dd._TIMING_PROVIDERS) == 1
    finally:
        dd._TIMING_PROVIDERS.clear()


# ---------------------------------------------------------------------------
# R-AI-9 · 非 str / 非有限输入不抛、不落「最有利档」
# ---------------------------------------------------------------------------
def test_non_str_levels_do_not_raise():
    """`["长期"]` 这类非 str 档位修前抛 TypeError（critical 步整月回滚）。"""
    from core.domains.politics.decree_duration import resolve_decree_duration

    s = _State(turn=1)
    s._decree_ai = {"pace": ["常"], "execution_timing": ["长期"],
                    "execution_attitude": ["拖延"]}
    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=60, followup=0)
    assert got["timing"] == "immediate", "非 str 时效档视为缺失 ⇒ 回落效果键表"
    assert got["attitude"]["level"] is None
    assert got["pace"] == "常" and "缺档" in got["source"], got
    assert got["execution_completion"] is None


def test_nan_ability_and_prestige_not_best_tiers():
    """NaN 与阈值比较恒 False ⇒ 修前落「能力出众 ×0.80 / 皇威尚隆 ×0.85」最有利档。"""
    from core.domains.politics.decree_duration import resolve_decree_duration

    s = _State(turn=1)
    s.prestige = float("nan")
    got = resolve_decree_duration(s, ability=float("nan"), followup=0)
    assert got["breakdown"]["ability"]["mult"] == 1.00, got["breakdown"]["ability"]
    assert "非有限" in got["breakdown"]["ability"]["note"]
    assert got["breakdown"]["prestige"]["mult"] == 1.00, got["breakdown"]["prestige"]
    assert "非有限" in got["breakdown"]["prestige"]["note"]


def test_missing_attitude_completion_is_undefined_not_perfect():
    """缺档 completion 修前回落 1.00（最完美执行）＝伪造；现报 None（未定义）。"""
    from core.domains.politics.decree_duration import resolve_decree_duration

    got = resolve_decree_duration(_State(turn=1), decree_kind="pay_reform",
                                  ability=60, followup=0)
    assert got["execution_completion"] is None, got


def test_attitude_present_completion_unchanged():
    """有档位时完成度照旧（0.35/1.00），不因缺档改动而回归。"""
    from core.domains.politics.decree_duration import resolve_decree_duration

    s = _State(turn=1)
    s._decree_ai = {"execution_attitude": "拖延"}
    assert resolve_decree_duration(s, decree_kind="pay_reform", ability=60,
                                   followup=0)["execution_completion"] == 0.35
    s2 = _State(turn=1)
    s2._decree_ai = {"execution_attitude": "奉行"}
    assert resolve_decree_duration(s2, decree_kind="pay_reform", ability=60,
                                   followup=0)["execution_completion"] == 1.00


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
