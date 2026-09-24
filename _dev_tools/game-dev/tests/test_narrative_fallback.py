# -*- coding: utf-8 -*-
"""T8 AI 失败分级降级测试：叙事模板库（场景/分档/真值组装）+ 推演拒绝式。

原则：不伪造成功——模板只引用程序真值；推演类失败仍是明确错误标记。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from ai.narrative_fallback import (  # noqa: E402
    fallback_report, fallback_event, fallback_dialogue, fallback_advice,
    fallback_eval, fallback_narrative, fallback_decree, template_for,
)


def _new_state():
    return GameState("史实")


# ---------------------------------------------------------------
# 1. 模板库：各场景合法对象 + 明确标注"程序代拟"（非 AI 伪造）
# ---------------------------------------------------------------
def test_fallback_report_template():
    r = fallback_report(year=1101, month=3, era_name="建中靖国")
    assert "report" in r and r["_fallback"] is True
    assert "有司补录" in r["report"] or "起居注官" in r["report"] or "史官" in r["report"]
    assert "AI" not in r["report"], "模板不假装 AI 口吻"


def test_fallback_event_by_severity():
    """事件模板按 severity 分档（轻/中/重），非法 severity 兜底「中」。"""
    for sev in ("轻", "中", "重"):
        e = fallback_event("河决", sev)
        assert e["severity_hint"] == sev and e["narrative"] and e["scenes"] == []
    e_bad = fallback_event("河决", "极重")
    assert e_bad["severity_hint"] == "中", "非法 severity 兜底中"


def test_fallback_dialogue_and_advice():
    d = fallback_dialogue("蔡京", turn=5)
    assert "reply" in d and "蔡京" in d["reply"] and d["mood"] == "中"
    a = fallback_advice(turn=5)
    assert "advice" in a and a["advice"]
    assert all("AI" not in (d["reply"] + a["advice"]) for _ in (0,))


def test_fallback_eval_narrative_decree():
    e = fallback_eval(turn=10)
    assert "commentary" in e and e["commentary"], "结局模板应有 commentary"
    assert any(k in e["commentary"] for k in ("史臣", "国史", "论赞")), "模板明确程序代拟"
    n = fallback_narrative("yamen", turn=10)
    assert n["narrative"] and n["tone"] == "平实"
    d = fallback_decree("减江南赋税三成", is_secret=False)
    # 拟旨模板：合法 free_edict 契约 + effects=None（不代拟效果）+ _fallback 标志
    assert d["category"] == "free_edict" and d["exec_mode"] == "longterm"
    assert d["effects"] is None, "AI 未接入不代拟效果"
    assert d["body"] == "减江南赋税三成", "body 回显玩家诏意（真值）"
    assert d.get("_fallback") is True and d.get("_error") == "AI_NOT_CONFIGURED"


def test_template_for_unknown_kind_none():
    """未知 kind → None（调用方走拒绝式标记，不伪造）。"""
    assert template_for("economy") is None
    assert template_for("military") is None


# ---------------------------------------------------------------
# 2. 结构化真值组装：月报只引用程序真值（不伪造数字）
# ---------------------------------------------------------------
def test_fallback_report_uses_recent_facts():
    """月报模板引用 settlement_log 真值（已发生事实），不凭空编造。"""
    s = _new_state()
    s.settlement_log = [
        {"kind": "treasury", "title": "国库入账", "note": "+50万贯"},
        {"kind": "disaster", "title": "黄河决口", "note": "河北路"},
    ]
    r = fallback_report(state=s)
    txt = r["report"]
    assert "国库入账" in txt or "黄河决口" in txt, "应引用结算真值"
    assert "+50万贯" in txt or "河北路" in txt, "真值细节应保留（不伪造）"


def test_fallback_report_no_state_pure_template():
    """无 state → 纯固定句式（不含假数字）。"""
    r = fallback_report(year=1101, month=1, era_name="建中靖国")
    assert r["report"].startswith("（") and "本月要略" not in r["report"]


# ---------------------------------------------------------------
# 3. 分级验证：推演类拒绝式（不模板兜底）
# ---------------------------------------------------------------
def test_narrative_fallback_rejects_derive():
    """_narrative_fallback 对推演类 kind → _error 拒绝式标记（不伪造）。"""
    from ai.client import _narrative_fallback
    u = _narrative_fallback("economy")
    assert u.get("_error")
    assert _narrative_fallback("military").get("_error")
    assert _narrative_fallback("era").get("_error")


def test_narrative_fallback_narrative_scenes_contract():
    """模板对象满足上层消费契约（dict + 关键键）。"""
    from ai.client import _narrative_fallback
    r = _narrative_fallback("report")
    assert isinstance(r, dict) and "report" in r
    d = _narrative_fallback("dialogue", "蔡京")
    assert isinstance(d, dict) and {"reply", "mood", "intent_hint"} <= set(d.keys())
    n = _narrative_fallback("narrative")
    assert isinstance(n, dict) and "narrative" in n


# ---------------------------------------------------------------
# 4. 游戏可继续：AI 失败时叙事兜底、推演仍拒绝（settle 层）
# ---------------------------------------------------------------
class _BrokenAI:
    """推演失败 + 叙事失败的假 AI（验证分级：推演拒绝、叙事模板）。"""
    available = True

    def economy_decide(self, posture, state=None):
        return None   # 推演失败 → 拒绝式

    def monthly_report(self, year, month, era_name, posture):
        return {"_error": "AI_TIMEOUT", "_fallback": True}   # 叙事失败 → 模板


def test_settle_economy_rejects_on_derive_failure():
    """推演类（economy）失败 → 拒绝式：settle_turn 抛 AIRuntimeError，不结算。"""
    from core.commands import settle_turn
    from core.errors import AIRuntimeError
    s = _new_state()
    with pytest.raises(AIRuntimeError):
        settle_turn(s, _BrokenAI())


def test_monthly_report_template_fallback_in_settle():
    """叙事类（月报）失败 → 本地模板兜底（游戏可继续，report 非空非伪造）。"""
    from core.commands import _monthly_report_text
    s = _new_state()
    s.settlement_log = [{"kind": "treasury", "title": "国库入账", "note": "+50万贯"}]
    result = _monthly_report_text(s, _BrokenAI())
    txt = result.get("report", "") if isinstance(result, dict) else str(result)
    assert txt and ("有司补录" in txt or "起居注官" in txt or "史官" in txt)
    assert "国库入账" in txt, "模板应组装结算真值"


def test_event_narrative_template_on_failure():
    """事件叙事失败 → 模板兜底（不阻断事件处理）。"""
    from core.commands import resolve_event
    s = _new_state()
    s.active_events.append({"title": "黄河决口", "message": "河决"})

    class _EventBrokenAI:
        available = True
        def event_narrative(self, event_title, event_context):
            raise RuntimeError("AI 挂了")

    out = resolve_event(s, {"title": "黄河决口", "category": "灾荒"}, 0, _EventBrokenAI())
    assert "朝堂" in out, "事件处理不被 AI 失败阻断"
    assert "程序未及推演" in out or "事态骤起" in out or "史官" in out


def test_dialogue_template_on_failure():
    """召对叙事失败 → 模板兜底（大臣未及具奏，不伪造政见）。"""
    from core.commands import audience_dialogue
    s = _new_state()

    class _DialogueBrokenAI:
        available = True
        def dialogue(self, *args, **kwargs):
            raise RuntimeError("AI 挂了")

    out = audience_dialogue(s, "蔡京", "卿近来如何？", _DialogueBrokenAI())
    assert any(k in out for k in ("未及具奏", "未及", "条陈", "容稍后")), \
        "召对失败用模板而非报错（得到: %s）" % out


def test_conclude_template_on_failure():
    """结局叙事失败 → 模板兜底（程序评定数据仍在）。"""
    from core.commands import conclude

    class _EvalBrokenAI:
        available = True
        def final_eval(self, *args, **kwargs):
            raise RuntimeError("AI 挂了")

    s = _new_state()
    ev, ai_eval = conclude(s, _EvalBrokenAI())
    assert isinstance(ev, dict), "程序评定仍在"
    assert "史臣" in ai_eval or "国史" in ai_eval, "结局叙事用模板"


def test_agent_failures_recorded_not_silent():
    """被唤醒的推演 Agent 失败 → state._ai_failures 明确记录（不静默、不伪造槽位）。"""
    from core.agent_router import inject_woken_agents

    s = _new_state()
    s.treasury = -100  # 触发 finance 唤醒

    class _FailingAI:
        available = True
        def finance_decide(self, posture, state=None):
            raise RuntimeError("推演失败")
        def economy_decide(self, posture, state=None):
            return {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中"}

    injected = inject_woken_agents(s, _FailingAI(), ["finance"])
    assert injected == [], "失败的 Agent 不应注入槽位"
    failures = getattr(s, "_ai_failures", [])
    assert any(f["agent"] == "finance" for f in failures), "失败应记入 _ai_failures"
    assert not hasattr(s, "_finance_ai"), "不伪造推演槽位"
