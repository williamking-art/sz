# -*- coding: utf-8 -*-
"""AI 调用报文契约测试：messages 必须含 user 角色（供应商兼容性）。

背景（2026-09-19 实测）：部分 OpenAI 兼容网关要求 messages 内必须有 user 消息，
只发 system 会被拒 —— Agnes 返回 HTTP 400「No user query found in messages.」；
a6api 的 gemini 系列则表现为契约失败。宋祚原实现 `_call(system, user_prompt="")`
在无 history 时只发 system，于是换供应商即整体失败。此处锁死该报文契约。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.client import AIClient  # noqa: E402


class _Capture:
    """拦截底层 HTTP，捕获实际下发的 payload，不发起真实请求。"""

    def __init__(self):
        self.payloads = []

    def __call__(self, payload, timeout=30):
        self.payloads.append(payload)
        return 200, {"choices": [{"message": {"content": "ok"}}]}, None


@pytest.fixture()
def client(monkeypatch):
    c = AIClient(api_key="sk-test", base_url="https://example.invalid/v1", model="test-model")
    cap = _Capture()
    monkeypatch.setattr(c, "_post_with_retry", cap, raising=False)
    c._capture = cap          # type: ignore[attr-defined]
    return c


def _roles(payload):
    return [m.get("role") for m in payload.get("messages", [])]


def test_messages_always_contain_user_when_prompt_empty(client):
    """空 user_prompt（历史规则只在 system 里）时，仍须补一条 user 占位。"""
    client._call("你是枢密使，请按规程输出 JSON。", "")
    assert client._capture.payloads, "应发出至少一次请求"
    roles = _roles(client._capture.payloads[0])
    assert roles[0] == "system"
    assert "user" in roles, f"messages 必须含 user 角色（实测网关要求），实际={roles}"


def test_user_prompt_preserved_when_present(client):
    """有 user_prompt 时原样下发，不被占位替换。"""
    client._call("sys", "国库几何？")
    payload = client._capture.payloads[0]
    users = [m for m in payload["messages"] if m.get("role") == "user"]
    assert len(users) == 1 and users[0]["content"] == "国库几何？"


def test_history_keeps_user_requirement(client):
    """带 history 但 history 中无 user 时，同样须补 user。"""
    client._call("sys", "", history=[{"role": "assistant", "content": "臣谨奏"}])
    roles = _roles(client._capture.payloads[0])
    assert "user" in roles


def test_explicit_messages_are_not_rewritten(client):
    """显式传入 messages 时不由本函数改写（调用方负责契约）。"""
    msgs = [{"role": "system", "content": "s"}]
    client._call("ignored", "", messages=msgs)
    assert client._capture.payloads[0]["messages"] is msgs
