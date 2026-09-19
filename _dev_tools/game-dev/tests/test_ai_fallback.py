# -*- coding: utf-8 -*-
"""AI provider 策略测试：**Agnes 优先、a6api 兜底**（用户定稿 2026-09-19）。

不联网：用替身替换 `_call_impl`，验证"未能完成 → 自动回退兜底 provider、退出还原、
只在回退内重发一次"，以及"未配兜底时行为与从前一致"。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.client import AIClient  # noqa: E402

MAIN = ("sk-main", "https://apihub.agnes-ai.com/v1", "agnes-2.5-flash")
FB = ("sk-fb", "https://api.a6api.com/v1", "gemini-3.8-flash")


def _client(with_fallback=True):
    return AIClient(MAIN[0], MAIN[1], MAIN[2],
                    fallback_api_key=FB[0] if with_fallback else "",
                    fallback_base_url=FB[1] if with_fallback else "",
                    fallback_model=FB[2] if with_fallback else "")


def test_provider_scope_switches_and_restores():
    c = _client()
    assert c.model == MAIN[2] and c.api_key == MAIN[0]
    with c._provider_scope("fallback"):
        assert c.model == FB[2] and c.api_key == FB[0]
        assert c.chat_url.startswith(FB[1])
    assert (c.model, c.api_key) == (MAIN[2], MAIN[0])
    assert c.chat_url.startswith(MAIN[1])


def test_usable_raw_judgement():
    assert AIClient._usable_raw("") is False
    assert AIClient._usable_raw(None) is False
    assert AIClient._usable_raw("   ") is False
    assert AIClient._usable_raw("史笔一段") is True
    assert AIClient._usable_raw("not-json", json_mode=True) is False
    assert AIClient._usable_raw('{"a": 1}', json_mode=True) is True
    assert AIClient._usable_raw({"tool_calls": [{"id": "1"}]}) is True


def test_fallback_on_exception():
    """主 provider 抛异常（超时/连接失败）→ 自动由兜底完成。"""
    c = _client()
    calls = []

    def impl(*a, **k):
        calls.append((c.model, a[0][:10] if a else ""))
        if c.model == MAIN[2]:
            raise RuntimeError("agnes 超时")
        return "兜底完成的史笔"

    c._call_impl = impl
    out = c._call("系统规程", "用户", json_mode=False)
    assert out == "兜底完成的史笔"
    assert [m for m, _ in calls] == [MAIN[2], FB[2]]
    assert c.fallback_hits == 1
    assert c.model == MAIN[2], "回退后必须还原主 provider"


def test_fallback_on_empty_and_bad_json():
    c = _client()
    state = {"n": 0}

    def impl(*a, **k):
        state["n"] += 1
        if c.model == MAIN[2]:
            return ""                      # 空正文（思考型模型预算不足的典型症状）
        return '{"report": "兜底"}'

    c._call_impl = impl
    assert c._call("sys", json_mode=True) == '{"report": "兜底"}'
    assert c.fallback_hits == 1

    c2 = _client()
    def impl2(*a, **k):
        return "半截 JSON {" if c2.model == MAIN[2] else '{"ok": 1}'
    c2._call_impl = impl2
    assert c2._call("sys", json_mode=True) == '{"ok": 1}'
    assert c2.fallback_hits == 1


def test_no_fallback_configured_keeps_old_behaviour():
    c = _client(with_fallback=False)
    calls = []
    c._call_impl = lambda *a, **k: (calls.append(c.model), "主完成")[1]
    assert c._call("sys", json_mode=False) == "主完成"
    assert calls == [MAIN[2]] and c.fallback_hits == 0

    c2 = _client(with_fallback=False)
    def boom(*a, **k):
        raise RuntimeError("主失败")
    c2._call_impl = boom
    with pytest.raises(RuntimeError):
        c2._call("sys")


def test_fallback_failure_raises_primary_error():
    """主因更贴近玩家配置（Agnes 未配好），故抛出主因而非兜底错。"""
    c = _client()

    def impl(*a, **k):
        if c.model == MAIN[2]:
            raise RuntimeError("主因：agnes 鉴权失败")
        raise RuntimeError("兜底也失败")
    c._call_impl = impl
    with pytest.raises(RuntimeError, match="主因"):
        c._call("sys")


def test_no_recursive_fallback():
    """回退内部不得再回退（避免双倍调用与栈式切换）。"""
    c = _client()
    seen = []

    def impl(*a, **k):
        seen.append(c.model)
        return "" if c.model == MAIN[2] else "兜底内容"
    c._call_impl = impl
    c._call("sys")
    assert seen.count(MAIN[2]) == 1 and seen.count(FB[2]) == 1


def test_config_roundtrip_carries_fallback(tmp_path, monkeypatch):
    c = _client()
    monkeypatch.setattr(AIClient, "_config_path", staticmethod(lambda: str(tmp_path / "ai_config.json")))
    assert c.save_config() is True
    import json
    data = json.loads((tmp_path / "ai_config.json").read_text(encoding="utf-8"))
    assert data["model"] == MAIN[2]
    assert data["fallback_model"] == FB[2] and data["fallback_base_url"] == FB[1]
    back = AIClient.load_saved()
    assert back is not None
    assert back.model == MAIN[2] and back.fallback_model == FB[2]
