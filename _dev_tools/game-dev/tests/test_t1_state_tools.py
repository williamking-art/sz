# -*- coding: utf-8 -*-
"""T1 测试：STATE_TOOL_SCHEMAS（3 工具）/ parse_tool_calls / _call tool_choice required。"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.client_utils import STATE_TOOL_SCHEMAS, parse_tool_calls  # noqa: E402


def test_state_tool_schemas_three_tools():
    """STATE_TOOL_SCHEMAS：update_state / query_state / trigger_event 三工具。"""
    names = [t["function"]["name"] for t in STATE_TOOL_SCHEMAS]
    assert names == ["update_state", "query_state", "trigger_event"]
    up = STATE_TOOL_SCHEMAS[0]["function"]
    chg = up["parameters"]["properties"]["changes"]["items"]["properties"]
    assert chg["op"]["enum"] == ["set", "add", "mul", "remove", "push"]
    assert "reason" in chg and "reason" in chg["path"] or "reason" in chg  # reason 必填
    assert "reason" in up["parameters"]["properties"]["changes"]["items"]["required"]
    assert "reason" in up["parameters"]["properties"]["changes"]["items"]["properties"]


def test_parse_tool_calls():
    """parse_tool_calls：提取 tool_calls → 结构化（name/arguments/call_id）。"""
    resp = {
        "content": "照办。",
        "tool_calls": [
            {"id": "c1", "function": {"name": "update_state",
                                      "arguments": json.dumps({
                                          "changes": [{"path": "treasury", "op": "add",
                                                       "value": 100000, "reason": "盐课增收"}],
                                          "narrative_hint": "榷盐丰稔。"})}},
            {"id": "c2", "function": {"name": "query_state", "arguments": '{"paths": ["treasury"]}'}},
        ],
    }
    calls = parse_tool_calls(resp)
    assert len(calls) == 2
    assert calls[0]["name"] == "update_state"
    assert calls[0]["arguments"]["changes"][0]["path"] == "treasury"
    assert calls[0]["arguments"]["changes"][0]["reason"] == "盐课增收"
    assert calls[1]["name"] == "query_state"
    assert calls[1]["arguments"]["paths"] == ["treasury"]
    # 无 tool_calls / 坏 arguments
    assert parse_tool_calls({}) == []
    assert parse_tool_calls({"tool_calls": [{"function": {"name": "x",
                                                          "arguments": "bad json"}}]})[0]["arguments"] == {}


def test_call_tool_choice_required_retry(monkeypatch):
    """_call tool_choice=required：AI 直接文本 → 丢弃重请求一次；仍无工具返回文本。"""
    from ai.client import AIClient
    client = AIClient.__new__(AIClient)
    client.available = True
    client.model = "test-model"
    client.api_key = "test-key"
    client.base_url = "https://x"
    client.json_mode = None
    client.tools_required_supported = True
    client._prev_texts = []
    client.token_usage = {"prompt": 0, "completion": 0, "calls": 0}
    client._cache = {}
    client._cache_hits = client._cache_misses = 0
    client.chat_url = "x"

    # 第一次调用返回纯文本（无 tool_calls）→ 重试返回带 tool_calls
    calls = {"n": 0}
    sent = {}

    def fake_post(url, headers, payload, timeout=30):
        sent["payload"] = payload
        calls["n"] += 1
        if calls["n"] == 1:
            return 200, {"choices": [{"message": {"content": "臣遵旨。"}}],
                         "usage": {}}, ""
        return 200, {"choices": [{"message": {"content": "", "tool_calls": [
            {"id": "t1", "function": {"name": "update_state",
                                      "arguments": '{"changes": [{"path": "treasury", "op": "add", "value": 1, "reason": "x"}]}'}}
        ]}}], "usage": {}}, ""

    monkeypatch.setattr("ai.client._http_post_json", fake_post)
    out = client._call("sys", "user", tools=STATE_TOOL_SCHEMAS, tool_choice="required")
    assert isinstance(out, dict) and out.get("tool_calls")
    assert calls["n"] == 2
    # 重试请求附提示
    last_msgs = sent["payload"]["messages"]
    assert any("请调用 update_state" in str(m.get("content", "")) for m in last_msgs)


def test_call_tool_choice_required_degrade(monkeypatch):
    """端点不支持 required → 探测降级（tools_required_supported=False + 回退 auto）。"""
    from ai.client import AIClient
    client = AIClient.__new__(AIClient)
    client.available = True
    client.model = "test-model"
    client.api_key = "test-key"
    client.base_url = "https://x"
    client.json_mode = None
    client.tools_required_supported = True
    client._prev_texts = []
    client.token_usage = {"prompt": 0, "completion": 0, "calls": 0}
    client._cache = {}
    client._cache_hits = client._cache_misses = 0
    client.chat_url = "x"
    calls = {"n": 0}
    sent = {}

    def fake_post(url, headers, payload, timeout=30):
        sent["payload"] = payload
        calls["n"] += 1
        if calls["n"] == 1:
            return 400, {"error": {"message": "tool_choice value required is not supported"}}, ""
        return 200, {"choices": [{"message": {"content": "ok"}}], "usage": {}}, ""

    monkeypatch.setattr("ai.client._http_post_json", fake_post)
    out = client._call("sys", "user", tools=STATE_TOOL_SCHEMAS, tool_choice="required")
    assert out == "ok"
    assert client.tools_required_supported is False
    assert calls["n"] == 2
    assert sent["payload"]["tool_choice"] == "auto"
