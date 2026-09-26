# -*- coding: utf-8 -*-
"""打包后启动冒烟（PyInstaller 分发包等价面）——直调端点函数，无需 httpx/TestClient。

模拟分发包启动后的最小可用闭环：
  /health → /api/new_game → /api/readouts → /api/ai_config(GET) → /api/advance(503 契约)

回合推演是「全游戏级强制 AI → 拒绝式」，无 AI 时 /api/advance 必须回结构化
503（AI_NOT_CONFIGURED 等），不得 500 裸崩——这正是冒烟要钉死的契约。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)


class _FakeRequest:
    """最小 Request 替身：只提供 _require_auth 会读到的字段（本机回环视为已鉴权）。"""

    class _Client:
        host = "127.0.0.1"

    client = _Client()
    headers = {}
    method = "GET"
    url = "http://127.0.0.1:8000/api/smoke"


@pytest.fixture()
def server(monkeypatch):
    import backend.server as S
    monkeypatch.setattr(S, "_state", None, raising=False)
    return S


def test_health_endpoint(server):
    data = server.health()
    assert data["ok"] is True
    assert data["has_state"] is False


def test_new_game_then_readouts(server):
    S = server
    data = S.api_new_game(S.NewGameReq(difficulty="史实"), _FakeRequest())
    assert isinstance(data.get("state"), dict)
    assert S._state is not None

    ro = S.api_readouts(_FakeRequest())
    assert isinstance(ro, dict) and "situations" in ro

    cfg = S.api_ai_config_get(_FakeRequest())
    assert isinstance(cfg, dict)  # 未配置时也应返回结构化空配置，而非 500


def test_advance_without_ai_returns_structured_503(server, monkeypatch):
    """拒绝式契约：无 AI 时 advance 必须抛 503 ＋ error_code，不得裸 500。"""
    S = server
    # 隔离本机 ai_config.json（避免冒烟测试真联网）：强制注入不可用客户端
    from ai.client import AIClient
    monkeypatch.setattr(S, "_get_ai", lambda: AIClient())
    S.api_new_game(S.NewGameReq(difficulty="史实"), _FakeRequest())
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        S.api_advance(_FakeRequest())
    assert ei.value.status_code == 503
    detail = ei.value.detail
    assert isinstance(detail, dict) and detail.get("error_code")


def test_event_cards_and_situations_seed_after_new_game(server):
    """开局后：局势种子就位、事件账本容器就绪、改写位/待朱批位为空。"""
    S = server
    S.api_new_game(S.NewGameReq(difficulty="史实"), _FakeRequest())
    s = S._state
    assert isinstance(s.event_pressure, dict), "事件压力账本容器应已初始化"
    assert s.timeline == {} and s.pending_breaks == {}
    ro = S.api_readouts(_FakeRequest())
    assert isinstance(ro.get("situations"), dict)
