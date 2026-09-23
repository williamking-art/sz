# -*- coding: utf-8 -*-
"""AI provider 网关行为与回退**叠加**测试（2026-09-19 测试项审查补缺口）。

覆盖此前无测试的三条真实路径：
  ① Agnes 端点 max_tokens **下限 8192 / 上限 32000**（思考型模型：低于下限会拿到半截 JSON）；
  ② **空响应自愈**（content 为空且预算偏小 → 加倍重发一次，且重发同样计费）；
  ③ **结算模式 × 兜底 provider 叠加**（结算期间主 provider 失败 → 仍能回退，且两层
     scope 退出后 provider 严格还原）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.client import AIClient  # noqa: E402

AGNES = ("k-ag", "https://apihub.agnes-ai.com/v1", "agnes-3.0-flash")
A6 = ("k-a6", "https://api.a6api.com/v1", "gemini-3.8-flash")


def _ok(content="好"):
    return 200, {"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 1}}, ""


def test_agnes_max_tokens_has_floor_and_ceiling(monkeypatch):
    c = AIClient(*AGNES)
    seen = {}

    def fake_post(payload, timeout=30):
        seen.update(payload)
        return _ok()
    monkeypatch.setattr(c, "_post_with_retry", fake_post)

    c._call_impl("sys", "user", max_tokens=300)
    assert seen["max_tokens"] == 8192, "Agnes 小额预算必须抬到下限 8192（否则半截 JSON）"

    c._call_impl("sys", "user", max_tokens=999_999)
    assert seen["max_tokens"] == 32000, "Agnes 网关上限保护 32000"


def test_non_agnes_endpoint_is_not_clamped(monkeypatch):
    c = AIClient(*A6)
    seen = {}

    def fake_post(payload, timeout=30):
        seen.update(payload)
        return _ok()
    monkeypatch.setattr(c, "_post_with_retry", fake_post)

    c._call_impl("sys", "user", max_tokens=300)
    assert seen["max_tokens"] == 300, "非 Agnes 端点不得改写预算"


def test_empty_response_self_heal_doubles_budget(monkeypatch):
    """空正文 → 加倍预算重发一次；仍为空才算失败。"""
    c = AIClient(*A6)
    calls = []

    def fake_post(payload, timeout=30):
        calls.append(payload.get("max_tokens"))
        if len(calls) == 1:
            return _ok("")
        return _ok("复活内容")
    monkeypatch.setattr(c, "_post_with_retry", fake_post)

    out = c._call_impl("sys", "user", max_tokens=300)
    assert out == "复活内容"
    assert len(calls) == 2 and calls[1] > calls[0], "自愈必须加大预算重发"


def test_empty_response_stays_empty_when_heal_fails(monkeypatch):
    """自愈也拿不到内容 → 返回空串（由上层判契约失败），**不伪造**。"""
    c = AIClient(*A6)
    monkeypatch.setattr(c, "_post_with_retry", lambda payload, timeout=30: _ok(""))
    assert c._call_impl("sys", "user", max_tokens=300) == ""


def test_settlement_mode_stacks_with_fallback(monkeypatch):
    """结算 provider 失败时仍能回退兜底；两层 scope 退出后 provider 严格还原。"""
    c = AIClient(AGNES[0], AGNES[1], AGNES[2],
                 settle_api_key="k-s", settle_base_url="https://api.agnes.example/v1",
                 settle_model="settle-model",
                 fallback_api_key=A6[0], fallback_base_url=A6[1], fallback_model=A6[2])
    seen = []

    def impl(*a, **k):
        seen.append(c.model)
        if c.model == "settle-model":
            raise RuntimeError("结算 provider 挂")
        return "兜底内容"
    c._call_impl = impl

    with c.settlement_mode():
        assert c.model == "settle-model"
        out = c._call("sys")
    assert out == "兜底内容"
    assert seen == ["settle-model", A6[2]]
    assert (c.model, c.api_key) == (AGNES[2], AGNES[0]), "两层 scope 必须全部还原"


def test_fallback_not_used_when_json_mode_contract_satisfied(monkeypatch):
    """主 provider 已给出可解析 JSON → 不得触发回退（避免无谓双倍计费）。"""
    c = AIClient(AGNES[0], AGNES[1], AGNES[2],
                 fallback_api_key=A6[0], fallback_base_url=A6[1], fallback_model=A6[2])
    seen = []

    def impl(*a, **k):
        seen.append(c.model)
        return '{"report": "主 provider 完成"}'
    c._call_impl = impl
    out = c._call("sys", json_mode=True)
    assert out == '{"report": "主 provider 完成"}'
    assert seen == [AGNES[2]] and c.fallback_hits == 0


def test_first_attempt_uses_primary_provider_not_fallback():
    """回退不得"抢先"：**首次**请求必须是主 provider（Agnes）。"""
    c = AIClient(AGNES[0], AGNES[1], AGNES[2],
                 fallback_api_key=A6[0], fallback_base_url=A6[1], fallback_model=A6[2])
    seq = []

    def impl(*a, **k):
        seq.append((c.model, c.chat_url))
        return "ok"
    c._call_impl = impl
    assert c._call("sys") == "ok"
    assert seq[0][0] == AGNES[2] and "agnes" in seq[0][1]
    assert c.fallback_hits == 0


def test_project_config_is_agnes_first_and_modern():
    """项目配置口径（用户 2026-09-22 定稿）：主/结算 = Agnes `agnes-3.0-flash`；
    **无 fallback 字段**（a6api 回退已从开发期结算验证移除——client.py 以
    `fallback_model` 非空为回退开关，缺字段即永不回退，主失败走程序兜底）；
    不得出现旧世代模型名（违反「只用最新/次新」）。"""
    import json
    cfg_path = os.path.join(_GAME_ROOT, "ai_config.json")
    if not os.path.exists(cfg_path):
        pytest.skip("未配置 ai_config.json")
    cfg = json.loads(open(cfg_path, encoding="utf-8").read())
    assert cfg.get("model") == "agnes-3.0-flash", cfg.get("model")
    assert "agnes" in str(cfg.get("base_url", "")), cfg.get("base_url")
    assert not cfg.get("fallback_model"), \
        "fallback 已按用户口径移除（client.py：fallback_model 非空才回退）"
    blob = json.dumps(cfg, ensure_ascii=False)
    legacy = ("gemini-2.5", "gemini-3-pro-preview", "gpt-4o", "gpt-4.1", "claude-3",
              "grok-3", "grok-4.3", "agnes-2.5")
    bad = [m for m in legacy if m in blob]
    assert not bad, f"配置含旧世代模型（违反「只用最新/次新」）：{bad}"
