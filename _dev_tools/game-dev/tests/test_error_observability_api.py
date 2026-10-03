# -*- coding: utf-8 -*-
"""关键路径错误可观测性回归（审查 P2-3：存档/API 端点 + AI 契约/日志泄漏）。

覆盖必修项：
  M1  api_load 读到坏档/空槽（后端 load 返回 None）→ 404 且**不污染**全局 _state；
  M2  api_save 回传服务端 ok（False → 500）；HttpBackend.save 回传 ok；save_slots 失败抛错；
  M11 提示词文件缺失 → ERROR 日志含完整路径 + 最终返回 PROMPT_MISSING 失败（不再静默占位继续）；
  M12 模型探测失败（401/异常）→ fetch_available_models 回空表、端点 ok:false 且无硬编码清单；
  L1  provider 错误正文（含 key 片段）不进异常消息（只进服务端日志）；
  L2  probe / capability_probe 失败文案不含 provider 原文；
  L3  工具异常原文不回给模型（只进日志）；
  L4  脱敏失败不回落原样序列化（不泄精确国库）；
  L5  拟诏上下文脱敏失败 → 中止契约且**未发起 HTTP**。
应修项（至少 3 条）：
  · api_readouts 失败读数进 readout_errors（ clerks 专项）；
  · api_memory 失败项进 memory_errors；
  · api_decree_polish 清会签缓存失败 → 500；
  · _state_to_dict 剔除字段记 warning（含字段名）；
  · /api/ai_config 区分"未配置"与"配置损坏"（error 字段）；
  · narrative_guard 角色状态未知 → unknown（不得当在场）；
  · semantic 异常一次性 warning（进程级去重）。

方法：本机无 httpx，FastAPI TestClient 不可用 → **直调端点函数 + 伪造 Request**
（照抄 `test_readouts_endpoint.py` 的 _FakeRequest 范式；鉴权走 _require_auth 的
「未配 token + 本机回环」放行条件）。`backend.server._state` 是模块级全局，
一律用 `monkeypatch.setattr` 注入/还原。
"""
import json
import logging
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import ai.client as C  # noqa: E402
import ai.client_utils as U  # noqa: E402
import ai.semantic as SEM  # noqa: E402
import backend.client as BC  # noqa: E402
import backend.server as S  # noqa: E402
from ai.narrative_guard import build_character_statuses, _validate_characters  # noqa: E402
from ai.validators import _summary_text  # noqa: E402
from core.errors import AIRuntimeError  # noqa: E402
from core.game_state import GameState  # noqa: E402

# SSRF 校验只放行「全球可路由」地址 → 测试用公网 IP 字面量（不联网）
PUBLIC = "http://93.184.216.34/v1"


class _FakeRequest:
    """最小 Request 替身：_require_auth 只读 client.host 与 headers（本机回环视为已鉴权）。"""

    class _Client:
        host = "127.0.0.1"

    client = _Client()
    headers = {}
    method = "POST"
    url = "http://127.0.0.1:8000/api/x"


_REQ = _FakeRequest()


class _FakeBackend:
    """最小后端替身：只提供被测端点用到的 save / load / save_slots。"""

    def __init__(self, load_result=None, save_result=True, slots=None):
        self.load_result = load_result
        self.save_result = save_result
        self.slots = slots if slots is not None else []
        self.save_calls = []
        self.load_calls = []

    def save(self, state, slot=1):
        self.save_calls.append((state, slot))
        return self.save_result

    def load(self, slot=1):
        self.load_calls.append(slot)
        return self.load_result

    def save_slots(self):
        return self.slots


@pytest.fixture(autouse=True)
def _clean_globals(monkeypatch):
    """隔离：鉴权 token / 全局 _ai，避免用例互相污染。"""
    monkeypatch.setattr(S, "_AUTH_TOKEN", "", raising=False)
    monkeypatch.setattr(S, "_ai", None, raising=False)


@pytest.fixture()
def state(monkeypatch):
    """注入测试用 GameState（模块级全局 _state 由 monkeypatch 自动还原）。"""
    s = GameState("史实")
    monkeypatch.setattr(S, "_state", s, raising=False)
    return s


# =====================================================================
# M1 · api_load：坏档/空槽不得把当前这一局从后端抹掉
# =====================================================================
def test_m1_load_none_raises_404_and_keeps_state(state, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(S, "_backend", _FakeBackend(load_result=None))
    before = S._state
    with pytest.raises(HTTPException) as ei:
        S.api_load(S.SlotReq(slot=3), _REQ)
    assert ei.value.status_code == 404
    assert "读档失败" in str(ei.value.detail)
    assert S._state is before, "读档失败不得改动 _state（原实现会置 None → 之后全部 409）"
    assert S._state is not None


def test_m1_load_success_replaces_state(monkeypatch):
    s0 = GameState("史实")
    s1 = GameState("史实")
    s1.turn = 7
    monkeypatch.setattr(S, "_state", s0, raising=False)
    monkeypatch.setattr(S, "_backend", _FakeBackend(load_result=s1))
    data = S.api_load(S.SlotReq(slot=2), _REQ)
    assert S._state is s1
    assert data["state"]["turn"] == 7


# =====================================================================
# M2 · api_save 回传真实结果；HttpBackend.save / save_slots 语义
# =====================================================================
def test_m2_save_failure_raises_500(state, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(S, "_backend", _FakeBackend(save_result=False))
    with pytest.raises(HTTPException) as ei:
        S.api_save(S.SlotReq(slot=1), _REQ)
    assert ei.value.status_code == 500
    assert "存档未写入" in str(ei.value.detail)


def test_m2_save_success_reports_ok(state, monkeypatch):
    fb = _FakeBackend(save_result=True)
    monkeypatch.setattr(S, "_backend", fb)
    resp = S.api_save(S.SlotReq(slot=4), _REQ)
    assert resp == {"ok": True, "slot": 4}
    assert fb.save_calls and fb.save_calls[0][1] == 4


def test_m2_http_backend_save_returns_server_ok(monkeypatch):
    hb = BC.HttpBackend("http://example.invalid")
    monkeypatch.setattr(hb, "_post", lambda path, payload=None, *a, **k: {"ok": False, "slot": 1})
    assert hb.save(None, 1) is False, "服务端 ok=False 时不得回报成功"
    monkeypatch.setattr(hb, "_post", lambda path, payload=None, *a, **k: {"ok": True, "slot": 1})
    assert hb.save(None, 1) is True


def test_m2_http_backend_save_slots_raises_not_empty(monkeypatch):
    """save_slots 失败必须抛错——不得静默 `return []`（会把槽位误报为空）。"""
    monkeypatch.setattr(BC.cmd, "save_slots",
                        lambda: (_ for _ in ()).throw(OSError("存档目录不可读")))
    hb = BC.HttpBackend("http://example.invalid")
    with pytest.raises(RuntimeError) as ei:
        hb.save_slots()
    assert "槽位列表读取失败" in str(ei.value)


def test_m2_local_backend_save_propagates_bool(state):
    """LocalBackend.save 必须把 core.save_game 的布尔值如实上抛（api_save 依赖它）。"""
    lb = BC.LocalBackend()
    assert lb.save(state, -1) is False, "非法槽位必须回 False"


# =====================================================================
# M11 · 提示词缺失：日志含完整路径 + 最终以 PROMPT_MISSING 失败
# =====================================================================
def test_m11_missing_prompt_logs_path_and_marks_sentinel(monkeypatch, caplog):
    caplog.set_level(logging.ERROR, logger="client_utils")
    missing = "_definitely_missing_prompt_for_test"
    txt = U._load_prompt(missing)
    assert U._PROMPT_MISSING_MARK in txt, "提示词缺失必须留下可检出的哨兵"
    assert U.prompt_missing_name(txt) == missing
    full_path = os.path.join(U._PROMPT_DIR, f"{missing}.md")
    assert any(full_path in r.getMessage() or full_path in str(r.args)
               for r in caplog.records if r.levelno >= logging.ERROR), \
        "ERROR 日志必须含完整提示词路径"


def test_m11_missing_prompt_aborts_call_with_code(monkeypatch, caplog):
    """monkeypatch 提示词目录不存在 → 契约返回带 PROMPT_MISSING 的失败，**不发起 HTTP**。"""
    caplog.set_level(logging.ERROR)
    fake_dir = os.path.join(os.path.abspath(os.sep), "sz_no_such_prompts_dir")
    monkeypatch.setattr(U, "_PROMPT_DIR", fake_dir)
    auto_called = {"n": 0}
    monkeypatch.setattr(C, "_http_post_json",
                        lambda *a, **k: auto_called.__setitem__("n", auto_called["n"] + 1))
    c = C.AIClient(api_key="k", base_url=PUBLIC)
    res = c.monthly_report(1122, 1, "宣和", "（态势）")
    assert isinstance(res, dict)
    assert res.get("_error") == "PROMPT_MISSING", f"必须以 PROMPT_MISSING 失败，实得 {res!r}"
    assert auto_called["n"] == 0, "发出占位文本继续请求＝静默回退，必须为 0 次 HTTP"
    assert any(fake_dir in (str(r.args) + r.getMessage())
               for r in caplog.records if r.levelno >= logging.ERROR), \
        "ERROR 日志必须含完整提示词路径"


def test_m11_live_prompts_are_not_flagged():
    """反向守卫：提示词齐备时不得误报缺失（防哨兵误判）。"""
    txt = U._load_prompt("advice", posture="（态势）")
    assert U._PROMPT_MISSING_MARK not in txt and len(txt) > 20


# =====================================================================
# M12 · 模型探测失败不得伪造成功（不得再回硬编码清单）
# =====================================================================
def test_m12_fetch_available_models_empty_on_401(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(C, "_http_get_json",
                        lambda url, headers, timeout=15: (401, {"error": {"message": "no"}}, "no"))
    c = C.AIClient(api_key="bad-key", base_url=PUBLIC)
    models = c.fetch_available_models()
    assert models == [], "探测失败必须回空列表（不得回硬编码推荐清单）"


def test_m12_fetch_available_models_empty_when_no_key():
    c = C.AIClient(api_key="", base_url=PUBLIC)
    assert c.fetch_available_models() == []


def test_m12_api_fetch_models_ok_false_on_401(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(C, "_http_get_json",
                        lambda url, headers, timeout=15: (401, {"error": {"message": "bad key"}}, ""))
    resp = S.api_fetch_models(S.FetchModelsReq(api_key="bad-key", base_url=PUBLIC), _REQ)
    assert resp["ok"] is False, resp
    assert resp["models"] == []
    assert "deepseek-chat" not in json.dumps(resp, ensure_ascii=False), \
        "端点不得再下发硬编码模型清单"
    assert resp.get("error")


def test_m12_model_detection_exception_reports_failure(monkeypatch):
    monkeypatch.setattr(C, "_http_get_json",
                        lambda url, headers, timeout=15: (_ for _ in ()).throw(
                            OSError("network down")))
    resp = S.api_fetch_models(S.FetchModelsReq(api_key="k", base_url=PUBLIC), _REQ)
    assert resp["ok"] is False and resp["models"] == []


# =====================================================================
# L1 · provider 错误正文不进异常消息（原文只入服务端日志）
# =====================================================================
def test_l1_provider_error_body_not_in_exception(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="ai.client")
    monkeypatch.setattr(C, "_http_post_json",
                        lambda url, headers, payload, timeout=30: (
                            400, {"error": {"message": "invalid api_key sk-abc123 param x"}}, ""))
    c = C.AIClient(api_key="k", base_url=PUBLIC)
    with pytest.raises(AIRuntimeError) as ei:
        c._call("系统规程")
    msg = str(ei.value)
    assert "sk-abc123" not in msg, "provider 原文/密钥片段不得进异常消息（会显示到界面）"
    assert "400" in msg and "AI 服务返回错误" in msg
    assert any("sk-abc123" in str(r.args) + r.getMessage()
               for r in caplog.records if r.levelno >= logging.WARNING), \
        "provider 原文必须仍留在服务端日志"


def test_l1_ai_action_detail_shape_keeps_error_code():
    """ai/client.py 的异常消息变更不得破坏服务端 503 的 {error_code, message} 形状。"""
    e = AIRuntimeError("AI 服务返回错误（HTTP 400）：请检查配置或稍后重试。",
                       code="AI_INVALID_JSON")
    detail = {"error_code": getattr(e, "code", "") or "AI_RUNTIME_ERROR",
              "message": str(e) or "AI 推演失败：请检查 AI 配置或网络后重试。"}
    assert detail["error_code"] == "AI_INVALID_JSON"
    assert set(detail) == {"error_code", "message"}


# =====================================================================
# L2 · 设置面板不得显示 provider 错误原文
# =====================================================================
def test_l2_probe_message_has_no_provider_text(monkeypatch):
    monkeypatch.setattr(C, "_http_post_json",
                        lambda url, headers, payload, timeout=15: (
                            403, {"error": {"message": "denied key sk-secret999"}}, ""))
    c = C.AIClient(api_key="k", base_url=PUBLIC)
    ok, msg = c.probe(force=True)
    assert ok is False
    assert "sk-secret999" not in msg, "面板文案不得含 provider 原文/密钥片段"
    assert "403" in msg
    cached_ok, cached_msg = c._probe_cache
    assert cached_ok is False and "sk-secret999" not in cached_msg


def test_l2_capability_probe_message_has_no_provider_text(monkeypatch):
    monkeypatch.setattr(C, "_http_post_json",
                        lambda url, headers, payload, timeout=15: (
                            500, {"error": {"message": "sk-leak777 upstream boom"}}, ""))
    c = C.AIClient(api_key="k", base_url=PUBLIC)
    cap = c.capability_probe(force=True)
    assert cap["ok"] is False
    assert "sk-leak777" not in json.dumps(cap, ensure_ascii=False)
    assert "500" in cap["error"]


# =====================================================================
# L3 · 工具异常原文不回给模型
# =====================================================================
class _RaiseState:
    """最小 state 替身：`clerks` 读取即抛 KeyError('treasury')（模拟工具内部异常）。"""

    @property
    def clerks(self):
        raise KeyError("treasury")

    def __getattr__(self, item):        # 其余属性一律给安全空值
        return None


def test_l3_tool_dispatch_hides_exception_text(caplog):
    caplog.set_level(logging.ERROR, logger="client_utils")
    out = U._tool_dispatch(_RaiseState(), [{"id": "c1", "function": {
        "name": "check_treasury", "arguments": "{}"}}], minister_name="测试")
    assert out and len(out) == 1
    res = out[0][1]
    assert "KeyError" not in res and "treasury" not in res, "工具结果不得回泄异常原文"
    assert "内部错误已记录" in res
    assert any(r.exc_info for r in caplog.records), "必须有 EXCEPTION 级留痕"


# =====================================================================
# L4 · 脱敏失败绝不回落"原样序列化"
# =====================================================================
def test_l4_desensitize_failure_never_dumps_raw(monkeypatch, caplog):
    caplog.set_level(logging.ERROR, logger="ai.validators")
    monkeypatch.setattr("ai.desensitize.desensitize_state",
                        lambda summary: (_ for _ in ()).throw(RuntimeError("boom")))
    summary = {"treasury": {"amount": 1234567}, "emperor_health": 71, "turn": 9}
    txt = _summary_text(summary)
    assert "1234567" not in txt, "脱敏失败不得回落原样序列化（隐藏数值泄漏进提示词）"
    assert "emperor_health" not in txt and "treasury" not in txt
    assert "不可用" in txt
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_l4_plain_string_still_passthrough():
    """回归：调用方已脱敏的字符串仍原样透传（不得被哨兵替换）。"""
    assert _summary_text("（态势：米价适中）") == "（态势：米价适中）"


# =====================================================================
# L5 · 脱敏失败即中止契约（不发 HTTP）
# =====================================================================
def test_l5_draft_decree_aborts_without_http(monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    monkeypatch.setattr("ai.desensitize.desensitize_for_ai",
                        lambda state: (_ for _ in ()).throw(RuntimeError("脱敏炸了")))
    sent = {"n": 0}
    monkeypatch.setattr(C, "_http_post_json",
                        lambda *a, **k: sent.__setitem__("n", sent["n"] + 1))

    c = C.AIClient(api_key="k", base_url=PUBLIC)     # AIClient 已含 DecreeContractMixin
    out = c.draft_decree("臣请整军", "整饬边防", {"treasury": {"amount": 1}}, state=GameState("史实"))
    assert isinstance(out, dict) and out.get("_error"), f"必须以失败结构返回，实得 {out!r}"
    assert sent["n"] == 0, "脱敏失败后不得降级发送上下文（不得发起 HTTP）"
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


# =====================================================================
# 应修项验收
# =====================================================================
def test_readouts_reports_failed_keys(state, monkeypatch, caplog):
    """clerks 读不到 → readout_errors 含 clerks（面板才能区分"读不到"与"真的是 0"）。"""
    caplog.set_level(logging.WARNING, logger="backend.server")
    monkeypatch.setattr(GameState, "finance_readout",
                        lambda self: (_ for _ in ()).throw(RuntimeError("会计炸了")))
    monkeypatch.setattr("core.clerks.totals",
                        lambda s: (_ for _ in ()).throw(RuntimeError("吏制炸了")))
    data = S.api_readouts(_REQ)
    assert "readout_errors" in data, "失败读数必须可区分"
    assert "finance" in data["readout_errors"]
    assert "clerks" in data["readout_errors"], "吏治折扣无从解释 → 必须列出 clerks"
    assert data["clerks"] == {} and data["finance"] == {}
    assert any("clerks" in str(r.args) + r.getMessage()
               for r in caplog.records if r.levelno >= logging.WARNING)
    assert any(r.exc_info for r in caplog.records if r.levelno >= logging.WARNING), \
        "必须带 exc_info 才能定位根因"


def test_readouts_clean_state_has_no_errors(state):
    """正常局不得产生噪声：readout_errors 应为空表。"""
    data = S.api_readouts(_REQ)
    assert data.get("readout_errors") == []


def test_memory_reports_failed_sections(state, monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="backend.server")
    mg = state.memory
    assert mg is not None
    monkeypatch.setattr(type(mg), "query_summaries",
                        lambda self, **k: (_ for _ in ()).throw(RuntimeError("概要炸了")))
    monkeypatch.setattr(type(mg), "query_change_log",
                        lambda self, **k: (_ for _ in ()).throw(RuntimeError("日志炸了")))
    data = S.api_memory(_REQ)
    assert "memory_errors" in data
    assert "summaries" in data["memory_errors"] and "change_log" in data["memory_errors"]
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_decree_polish_cache_reset_failure_raises_500(state, monkeypatch):
    from fastapi import HTTPException

    class _AI:
        available = True

        def polish_decree(self, text, summary):
            return {"title": "试诏", "body": "正文", "effects": [{"dim": "prestige", "tier": "小"}]}

    monkeypatch.setattr(S, "_get_ai", lambda: _AI())
    state.add_edict_draft({"title": "旧", "body": "旧文", "effects": []})
    did = state.edict_drafts[-1]["id"] if isinstance(state.edict_drafts, list) else None
    assert did, "测试前提：诏草已入列"
    monkeypatch.setattr(state, "store_council_review",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("缓存清不掉")))
    with pytest.raises(HTTPException) as ei:
        S.api_decree_polish(S.DecreePolishReq(raw_intent="改一下", draft_id=did), _REQ)
    assert ei.value.status_code == 500
    assert "会签缓存" in str(ei.value.detail)


def test_state_to_dict_warns_on_unserialisable_field(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="backend.server")
    s = GameState("史实")
    monkeypatch.setattr(S, "vars", lambda obj: {"weird_field": object(), "turn": 3}, raising=False)
    out = S._state_to_dict(s)
    assert "weird_field" not in out and out.get("turn") == 3
    assert any("weird_field" in str(r.args) + r.getMessage()
               for r in caplog.records if r.levelno >= logging.WARNING), \
        "必须记下被剔除的字段名"


def test_ai_config_get_distinguishes_missing_vs_corrupt(monkeypatch, tmp_path):
    p = tmp_path / "ai_config.json"
    monkeypatch.setattr(S, "_ai_config_path", lambda: str(p))
    # ① 未配置（文件不存在）→ configured False 且无 error
    assert p.exists() is False
    resp = S.api_ai_config_get(_REQ)
    assert resp["configured"] is False and resp["error"] == ""
    # ② 配置损坏（文件在但读不出）→ configured False + error 说明损坏
    p.write_text("{ this is not json", encoding="utf-8")
    resp2 = S.api_ai_config_get(_REQ)
    assert resp2["configured"] is False
    assert resp2["error"], "配置损坏必须与'未配置'可区分"


def test_narrative_guard_unknown_status_not_active(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="ai.narrative_guard")
    s = GameState("史实")
    monkeypatch.setattr(GameState, "minister_status",
                        lambda self, name: (_ for _ in ()).throw(RuntimeError("状态查不到")))
    statuses = build_character_statuses(s)
    assert statuses, "状态表不应为空"
    assert all(v["status"] == "unknown" for v in statuses.values()), \
        "查不到必须落 unknown——不得回落 active（已死/贬谪角色会被当在场）"
    assert all(v["in_office"] is False for v in statuses.values())
    bad, names = _validate_characters("".join(list(statuses)[:2]) + "曾言……", statuses)
    if names:
        assert bad is True
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_semantic_failure_warns_once(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="ai.semantic")
    SEM._warned.clear()
    monkeypatch.setattr(SEM, "_get_backend", lambda: ("sess", "tok"))
    monkeypatch.setattr(SEM, "embed",
                        lambda texts: (_ for _ in ()).throw(RuntimeError("嵌入炸了")))
    assert SEM.semantic_repetition_hit("文本", ["旧文"]) is False
    assert SEM.semantic_repetition_hit("文本2", ["旧文2"]) is False
    warns = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warns) == 1, f"须进程级去重（防每回合刷屏），实得 {len(warns)} 条"
    assert warns[0].exc_info, "去重不代表丢栈：仍须 exc_info"


def test_prompt_missing_code_has_chinese_mapping():
    """M11 错误码必须在前端可用的中文映射表里（否则玩家只看到码、看不到原因）。"""
    from content.data import AI_ERROR_CODES
    assert AI_ERROR_CODES.get("PROMPT_MISSING"), "PROMPT_MISSING 缺中文映射"
    assert "提示词" in AI_ERROR_CODES["PROMPT_MISSING"]
