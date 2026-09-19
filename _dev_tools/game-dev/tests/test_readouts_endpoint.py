# -*- coding: utf-8 -*-
"""`/api/readouts` **薄壳端点**测试（2026-09-19 测试项审查补缺口）。

此前只有 3 处文本命中 `/api/`，端点层几乎无覆盖；而本端点正是
`regions` / `situations`（含 `pop_channels` / `faction_channels`）的对外出口——
薄壳一旦漏字段或序列化炸掉，前端的局势面板会整体空白。

方法（本机无 httpx，FastAPI TestClient 不可用）：直接调用端点函数 + 伪造 `Request`，
并把模块级 `_state` 注入测试用 GameState。
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


class _FakeRequest:
    """最小 Request 替身：只提供 _require_auth 会读到的字段（本机回环视为已鉴权）。"""

    class _Client:
        host = "127.0.0.1"

    client = _Client()
    headers = {}
    method = "GET"
    url = "http://127.0.0.1:8000/api/readouts"


@pytest.fixture()
def server_state(monkeypatch):
    import backend.server as S
    s = GameState("史实")
    init_legacies(s)
    monkeypatch.setattr(S, "_state", s, raising=False)
    return S, s


def test_readouts_shell_exposes_regions_and_situations(server_state):
    S, s = server_state
    data = S.api_readouts(_FakeRequest())
    assert isinstance(data, dict)
    assert "regions" in data and isinstance(data["regions"], dict)
    assert "situations" in data, "局势投影必须由本端点对外提供"
    sit = data["situations"]
    assert isinstance(sit.get("items"), list)
    assert "pop_channels" in sit, "六类心气 + 识字率必须随局势一并下发"
    assert "faction_channels" in sit, "集团 ⊆ POP 必须随局势一并下发"


def test_readouts_payload_is_json_serialisable(server_state):
    """薄壳返回值必须可 JSON 序列化（None/NaN/对象泄漏都会让前端整体失败）。"""
    S, _s = server_state
    data = S.api_readouts(_FakeRequest())
    text = json.dumps(data, ensure_ascii=False, default=str)
    assert "NaN" not in text and "Infinity" not in text, "响应不得含非有限值"
    assert len(text) > 100


def test_readouts_situations_survive_with_a_record(server_state):
    """带一条局势 Record 时，薄壳不得因序列化丢字段。"""
    S, s = server_state
    from core.situations import make_record
    s.situations.append(make_record(
        "陕西流寇起", "shaanxi_bandits", -1,
        resolve_condition={"metric": "region.unrest", "arg": "陕西路", "op": "<=", "value": 30},
        fail_condition={"metric": "region.unrest", "arg": "陕西路", "op": ">=", "value": 85},
        ongoing_cost={"treasury": -1000, "prefectures.陕西路.pops.农.wealth": 1000}))
    data = S.api_readouts(_FakeRequest())
    assert data["situations"]["readout_status"] in ("ok", "partial")
    # 只读端点不得改动 state
    assert len(s.situations) == 1 and s.situations[0]["status"] == "active"


def test_readouts_regions_has_literacy_field(server_state):
    """州路读数必须带识字率（人口加权的 POP 自有值）——面板民生栏依赖它。"""
    S, s = server_state
    data = S.api_readouts(_FakeRequest())
    routes = (data.get("regions") or {}).get("routes") or []
    assert routes, "州路读数不应为空"
    row = routes[0]
    assert "literacy" in row, "州路读数缺 literacy（识字率设定未接通面板）"
    assert row["literacy"] is None or 0 <= row["literacy"] <= 100
