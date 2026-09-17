# -*- coding: utf-8 -*-
"""落地改进批测试：召对预过滤/缓存 / AI 失败分级（叙事模板兜底）/ 并行上下文共享。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.commands import _prefilter_dialogue, _dialogue_cache_hit  # noqa: E402


def _new_state():
    return GameState("史实")


def test_prefilter_dialogue():
    """召对预过滤：常用诏令 → 本地模板（AI 只处理非常规）。"""
    s = _new_state()
    hit = _prefilter_dialogue("蔡京", "朕欲调兵守边")
    assert hit and "奉诏" in hit
    hit2 = _prefilter_dialogue("韩忠彦", "赈灾开仓")
    assert hit2 and "赈济" in hit2
    # 非常规输入 → None（走 AI）
    assert _prefilter_dialogue("蔡京", "卿对王安石变法有何高见？") is None


def test_dialogue_cache_hit():
    """召对缓存：重复同话题（相似度>0.85）→ 复用上次回复。"""
    s = _new_state()
    s.dialogue_history.append(("朕", "卿觉得今岁河工如何？"))
    s.dialogue_history.append(("蔡京", "臣以为当先固堤防。"))
    hit = _dialogue_cache_hit(s, "蔡京", "卿觉得今岁河工如何？")   # 高度相似
    assert hit == "臣以为当先固堤防。"
    # 不同话题 → None
    assert _dialogue_cache_hit(s, "蔡京", "卿对西北战事怎么看？") is None


def test_dialogue_cache_structured_and_stats():
    """召对缓存升级：结构化键命中（近 N 回合）+ 统计计数（省 token 可量化）。"""
    from core.commands import _dialogue_stats, _dialogue_cache_hit
    s = _new_state()
    s.dialogue_history.append(("朕", "卿觉得今岁河工如何？"))
    s.dialogue_history.append(("蔡京", "臣以为当先固堤防。"))
    # 首次：相似度 fallback 命中 → 计数
    assert _dialogue_cache_hit(s, "蔡京", "卿觉得今岁河工如何？") == "臣以为当先固堤防。"
    st = _dialogue_stats(s)
    assert st["cache_hits"] == 1 and st["ai_calls"] == 0
    # 再次同话题：结构化缓存直接命中（不调 AI）
    assert _dialogue_cache_hit(s, "蔡京", "卿觉得今岁河工如何？") == "臣以为当先固堤防。"
    assert _dialogue_stats(s)["cache_hits"] == 2
    # 不同话题 → 未命中（走 AI 路径）
    assert _dialogue_cache_hit(s, "蔡京", "卿对西北战事怎么看？") is None


def test_prefilter_stats_via_audience():
    """预过滤命中统计：audience_dialogue 命中模板 → prefilter_hits++、不调 AI（省 token）。"""
    from core.commands import audience_dialogue, _dialogue_stats

    class _AI:
        available = True
        calls = 0

        def dialogue(self, *a, **k):
            self.calls += 1
            return {"reply": "臣谨奏。"}

    s = _new_state()
    fake = _AI()
    # 预过滤命中（发内帑 → 模板），不调 AI
    reply = audience_dialogue(s, "蔡京", "朕欲发内帑以济度支", fake)
    assert "内帑" in reply
    st = _dialogue_stats(s)
    assert st["prefilter_hits"] == 1 and st["ai_calls"] == 0 and fake.calls == 0
    # 非常规输入 → 走 AI（ai_calls++）
    reply2 = audience_dialogue(s, "蔡京", "卿对王安石变法有何高见？", fake)
    assert reply2 == "臣谨奏。"
    st2 = _dialogue_stats(s)
    assert st2["ai_calls"] == 1 and fake.calls == 1
    # AI 回复后写缓存：同话题再次提问 → 缓存命中不调 AI
    reply3 = audience_dialogue(s, "蔡京", "卿对王安石变法有何高见？", fake)
    assert reply3 == "臣谨奏。"
    st3 = _dialogue_stats(s)
    assert st3["cache_hits"] >= 1 and fake.calls == 1  # AI 不再被调


def test_narrative_fallback_templates():
    """AI 失败分级降级：叙事类本地模板兜底（非 AI 伪造，带 _fallback 标记）；推演类仍拒绝式。

    注：模板为确定性轮换多句式（narrative_fallback._pick），不断言具体文案（跨进程
    str hash 不稳定），只断言兜底存在 + 非伪造标记。
    """
    from ai.client import _narrative_fallback
    r = _narrative_fallback("report")
    assert "report" in r and r["report"] and r.get("_fallback")
    d = _narrative_fallback("dialogue", "蔡京")
    assert "reply" in d and d["reply"] and d.get("_fallback")
    n = _narrative_fallback("narrative")
    assert "narrative" in n and n["narrative"] and n.get("_fallback")
    # 未知 kind → _ai_unavailable（拒绝式标记）
    u = _narrative_fallback("economy")
    assert u.get("_error")


def test_cumulative_diff_injected():
    """并行上下文共享：run_settlement_ai 注入其他 Agent 上轮摘要。"""
    from core.async_ai import run_settlement_ai, _cumulative_diff
    s = _new_state()
    s._economy_ai = {"景气": "大"}
    s._diplomacy_ai = {"attitude": "小"}
    diff = _cumulative_diff(s)
    assert "上轮各司推演" in diff and "景气大" in diff and "外交小" in diff

    class _AI:
        def __init__(self):
            self.available = True
            self.last_posture = ""

        def economy_decide(self, posture):
            self.last_posture = posture
            return {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
                    "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无",
                    "jiaozi_trust": "稳", "shortage": "平", "maritime": "平",
                    "bank": "稳", "price_trend": "平"}

    fake = _AI()
    fut = run_settlement_ai(fake, "base", s, ["economy"], ui=None, on_success=None, on_error=None)
    fut.result(timeout=10)
    assert "上轮各司推演" in fake.last_posture

def test_prefilter_new_categories():
    """预过滤扩类（A 建议）：建新军/研科技/外交/营造 低误伤高频类别命中。"""
    assert "奉诏" in _prefilter_dialogue("蔡京", "朕欲建军新军")
    assert "奉诏" in _prefilter_dialogue("韩忠彦", "研制火器")
    assert "奉诏" in _prefilter_dialogue("曾布", "遣使议和")
    assert "奉诏" in _prefilter_dialogue("童贯", "营造艮岳")


def test_prefilter_mis_hit_guard():
    """误伤缓解（B 建议）：讨论类（利弊/之辩/高见/何如/如何）跳过走 AI；>40 字复杂不预过滤。"""
    assert _prefilter_dialogue("蔡京", "减税与加征之辩，卿以为如何") is None
    assert _prefilter_dialogue("蔡京", "三舍法兴学利弊，愿闻其详") is None
    assert _prefilter_dialogue("蔡京", "市舶之利恐伤海商，卿有何高见") is None
    long_decree = "朕欲蠲免京东西路今岁秋税之半，以纾民困，并着转运司核实灾伤分数，具以条奏，毋得扰民，钦此。"
    assert len(long_decree) > 40
    assert _prefilter_dialogue("蔡京", long_decree) is None


def test_topic_key_normalized():
    """主题词归一（D 建议）：同话题不同措辞 → 同一主题词 → 缓存命中。"""
    from core.commands import _topic_key
    assert _topic_key("卿觉得今岁河工如何？") == _topic_key("今岁河工，卿以为如何？") == "河工"
    assert _topic_key("朕欲议变法之利弊") == "变法"


def test_ai_result_cache(monkeypatch):
    """AI 结果缓存扩展：拟旨/解析/推演按 状态 hash + 输入 缓存复用（同输入同朝局不重调 AI）。"""
    from ai.client import AIClient
    client = AIClient.__new__(AIClient)
    client.available = True
    calls = {"n": 0}
    monkeypatch.setattr(client, "_call",
                        lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1), '{"ok": 1}')[1])
    monkeypatch.setattr(client, "_postprocess", lambda raw, v, fb, **k: raw)
    # 同输入同朝局：第二次命中缓存不重调
    assert client._cached_call("parse", "朝局A", "sys", "user", 0.3, 900,
                               json_mode=True, input_key="诏A") is not None
    assert client._cached_call("parse", "朝局A", "sys", "user", 0.3, 900,
                               json_mode=True, input_key="诏A") is not None
    assert calls["n"] == 1
    # 不同输入（input_key）→ 不互撞，重调
    client._cached_call("parse", "朝局A", "sys", "user", 0.3, 900,
                        json_mode=True, input_key="诏B")
    assert calls["n"] == 2
    # 不同朝局（state_hash）→ 不互撞
    client._cached_call("parse", "朝局B", "sys", "user", 0.3, 900,
                        json_mode=True, input_key="诏A")
    assert calls["n"] == 3
    # 缓存统计
    st = client.cache_stats()
    assert st["hits"] == 1 and st["misses"] == 3
