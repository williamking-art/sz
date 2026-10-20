# -*- coding: utf-8 -*-
"""2026-10-20 全审 · 前端/UI 合同回归（R-UI-1 / 3 / 4 / 6 / 7）。

覆盖（每条断言都对应报告里的一项验收）：
1. **R-UI-1 案卷页数据链**：`core.situations` 把 longterm 任务投影成 `id=task id` 的局势条目；
   `/api/readouts` 的 `situations.items` 与 `longterm_cases` 存在**同键 id**（此前交集为空，
   点开必报「案卷读数为空」）；投影严格只读、无 id 事务被隔离并留痕。
2. **R-UI-3 单位**：`commands_decree.authorize_longterm_case` 的 msg 用「贯」而非「万两」，
   与国库扣减同单位；案号随授权下发。
3. **R-UI-4 缺失≠0**：未授权 `case_readout.authorization is None`（不再回落 0/0/treasury）。
4. **R-UI-6 真五维**：`/api/readouts` 的 `ministers[name]` 下发 `attrs/potential/attr_names`，
   数值与 `content.ministers.stats` 单一来源一致（前端不再按人名 seed 伪随机）。
5. **R-UI-7 拒绝式动作保 ok**：`LocalBackend.action("authorize_case")` 回 `ActionOutcome.ok`；
   `/api/action` 响应体带 `ok`（成功/失败都带），而普通动作**不新增该字段**（旧契约不变）。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import PREFECTURE_LIST  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.situations import build_situation_readout  # noqa: E402


class _FakeRequest:
    """最小 Request 替身（本机回环 ⇒ `_require_auth` 放行；无需 httpx）。"""

    class _Client:
        host = "127.0.0.1"

    client = _Client()
    headers = {}
    method = "POST"
    url = "http://127.0.0.1:8000/api/action"


def _state_with_case(**task_overrides):
    """开局 state + 一条在办长期事务（R-UI-1 的被投影对象）。"""
    s = GameState("史实")
    init_legacies(s)
    route = PREFECTURE_LIST[0]
    task = {
        "id": "ltp1",
        "task_name": "整饬海防",
        "progress": 42,
        "minister": "韩忠彦",
        "linked_region": route,
        "linked_factions": ["主战"],
        "success_condition": "成效满 100%（按月由支持方/阻力方与执行能力推进）",
        "last_change": "本月推进 3.2%",
        "monthly_effects": [{"key": "prestige", "amount": -1}],
        "outcome_effects": [{"key": "prestige", "amount": 9}],
        "progress_log": [{"turn": 30, "narrative": "增烽堠八座", "applied": [], "blocked": None}],
    }
    task.update(task_overrides)
    s.longterm_public = [task]
    s.longterm_secret = []
    return s, route


def _server_state(monkeypatch, s):
    import backend.server as S
    monkeypatch.setattr(S, "_state", s, raising=False)
    return S


# ---------------------------------------------------------------
# ① R-UI-1：局势 ↔ 案卷同键
# ---------------------------------------------------------------
def test_situations_project_longterm_case_with_task_id():
    s, route = _state_with_case()
    out = build_situation_readout(s)
    cases = [r for r in out["items"] if r["source"] == "longterm_case"]
    assert len(cases) == 1, "longterm 任务必须被投影为局势条目（否则案卷页点开必空）"
    row = cases[0]
    assert row["id"] == "ltp1", "id 必须原样取 task id（案卷字典键），不得加 legacy: 之类前缀"
    assert row["title"] == "整饬海防"
    assert row["status"] == "active"
    assert row["bar_value"] == 42
    # severity 缺失时按既有确定性规则由进度派生（50 + (1-0.42)*40 ≈ 73），不是随机数
    assert row["severity"] == 73
    assert row["phase"] == "中"
    assert row["region_hint"] == route
    assert row["faction_hint"] == "主战"
    assert row["resolve_condition_text"].startswith("成效满 100%")
    assert row["timeline"] and row["timeline"][0]["text"] == "增烽堠八座"
    assert out["readout_status"] == "ok", out["readout_errors"]


def test_situations_projection_is_readonly():
    """投影不得改动 state（尤其不得调 case_readout 的幂等补齐/建承办人档案）。"""
    s, _route = _state_with_case()

    def snap():
        return json.dumps({
            "public": s.longterm_public,
            "secret": s.longterm_secret,
            "official_stats": getattr(s, "official_stats", None),
            "treasury": s.treasury,
            "prefectures": s.prefectures,
        }, sort_keys=True, ensure_ascii=False, default=str)

    before = snap()
    build_situation_readout(s)
    build_situation_readout(s)
    assert snap() == before, "局势投影必须只读：不得给事务补字段/建档案"


def test_case_without_id_is_isolated_not_fatal():
    s, _route = _state_with_case()
    s.longterm_secret = [{"task_name": "密查（旧档无 id）", "progress": 5}]
    out = build_situation_readout(s)
    assert [r["id"] for r in out["items"] if r["source"] == "longterm_case"] == ["ltp1"]
    assert out["readout_status"] == "partial"
    assert any("缺 id" in e for e in out["readout_errors"]), out["readout_errors"]


def test_readouts_endpoint_situations_and_longterm_cases_share_keys(monkeypatch):
    """R-UI-1 验收：有在办案卷时，`situations.items` 与 `longterm_cases` 存在同键 id。"""
    s, _route = _state_with_case()
    S = _server_state(monkeypatch, s)
    data = S.api_readouts(_FakeRequest())

    sit_ids = {str(it.get("id")) for it in (data["situations"]["items"] or [])}
    case_ids = set((data["longterm_cases"] or {}).keys())
    assert case_ids == {"ltp1"}
    assert sit_ids & case_ids == {"ltp1"}, (
        f"局势与案卷必须同键（否则点开案卷必报「案卷读数为空」）："
        f"situations={sorted(sit_ids)[:8]} cases={sorted(case_ids)}")

    # 同键合并生效：案卷读数从局势投影补齐了 severity/phase/timeline（单一来源）
    rd = data["longterm_cases"]["ltp1"]
    assert rd["severity"] == 73 and rd["phase"] == "中"
    assert rd["timeline"] and rd["timeline"][0]["text"] == "增烽堠八座"
    assert rd["progress"]["percent"] == 42
    json.dumps(data, ensure_ascii=False, default=str)   # 端点载荷必须可序列化


# ---------------------------------------------------------------
# ② R-UI-3：单位 = 贯（与国库扣减同单位）
# ---------------------------------------------------------------
def test_authorize_message_uses_guan_and_case_no():
    from core.commands_decree import authorize_longterm_case

    s, _route = _state_with_case()
    got = authorize_longterm_case(s, "ltp1", budget=300_000, pool="treasury",
                                  discretion=True, monthly_cost=20_000)
    assert got["ok"], got
    msg = got["msg"]
    assert "万两" not in msg, f"R-UI-3：专款文案不得再写「万两」（实扣单位是贯）：{msg}"
    assert "300,000 贯" in msg and "20,000 贯" in msg, msg
    assert "国库" in msg
    case_no = got.get("case_no") or ""
    assert case_no and case_no in msg, f"授权应下发并在文案中带上案号：{msg!r}"


# ---------------------------------------------------------------
# ③ R-UI-4：未授权 authorization = None（缺失≠0）
# ---------------------------------------------------------------
def test_unauthorized_case_readout_authorization_is_none():
    from core.domains.politics.longterm_case import case_readout

    s, _route = _state_with_case()
    rd = case_readout(s, s.longterm_public[0])
    assert rd["authorization"] is None, "未授权必须回 None（面板示「未授权」），不得回落 0"


def test_authorized_case_readout_authorization_has_values():
    from core.commands_decree import authorize_longterm_case
    from core.domains.politics.longterm_case import case_readout

    s, _route = _state_with_case()
    assert authorize_longterm_case(s, "ltp1", budget=300_000,
                                   monthly_cost=20_000, discretion=True)["ok"]
    auth = case_readout(s, s.longterm_public[0])["authorization"]
    assert isinstance(auth, dict), "已授权应回授权块（字段名不变）"
    assert auth["budget_total"] == 300_000 and auth["budget_remaining"] == 300_000
    assert auth["pool"] == "treasury" and auth["monthly_cost"] == 20_000
    assert auth["discretion"] is True


# ---------------------------------------------------------------
# ④ R-UI-6：readouts.ministers 下发真实五维（单一来源）
# ---------------------------------------------------------------
def test_readouts_ministers_carry_real_five_attrs(monkeypatch):
    from content.ministers.stats import (ATTRIBUTE_NAMES,
                                         get_or_create_official_stats)

    s, _route = _state_with_case()
    S = _server_state(monkeypatch, s)
    data = S.api_readouts(_FakeRequest())
    ministers = data.get("ministers") or {}
    assert ministers, "群臣档案必须下发（召对面板数据源）"

    name = "韩忠彦"
    assert name in ministers
    prof = get_or_create_official_stats(s, name)
    row = ministers[name]
    assert set(row.get("attr_names") or {}) == set(ATTRIBUTE_NAMES), row.get("attr_names")
    for k, cn in ATTRIBUTE_NAMES.items():
        assert row["attr_names"][k] == cn
        assert row["attrs"][k] == prof["attrs"][k], f"{name}.{k} 必须与单一来源一致"
        assert row["potential"][k] == prof["potential"][k]
        assert 0 <= row["attrs"][k] <= 100
    # 不再是 60–99 段的人名 seed 伪随机：至少一维明显低于伪随机下界
    assert min(row["attrs"].values()) < 60, row["attrs"]


# ---------------------------------------------------------------
# ⑤ R-UI-7：拒绝式动作保留 ok
# ---------------------------------------------------------------
def test_local_backend_action_outcome_keeps_ok():
    from backend.client import ActionOutcome, LocalBackend

    s, _route = _state_with_case()
    lb = LocalBackend()
    ok_res = lb.action(s, "authorize_case",
                       {"task_id": "ltp1", "budget": 1000, "pool": "treasury",
                        "discretion": False, "monthly_cost": 100})
    assert isinstance(ok_res, ActionOutcome)
    assert ok_res.ok is True
    msg, st = ok_res                      # 解包契约不变（msg, state）
    assert isinstance(msg, str) and st is s

    repeat = lb.action(s, "authorize_case", {"task_id": "ltp1", "budget": 1000})
    assert repeat.ok is False, "重复授权必须 ok=False（前端据此渲染失败态）"
    assert "已授权过" in repeat.message

    missing = lb.action(s, "authorize_case", {"task_id": "nope", "budget": 1})
    assert missing.ok is False and "未找到" in missing.message


def test_api_action_response_carries_ok_only_for_rejectable_actions(monkeypatch):
    s, _route = _state_with_case()
    S = _server_state(monkeypatch, s)

    ok_body = S.api_action(S.ActionReq(action="authorize_case",
                                       params={"task_id": "ltp1", "budget": 1000,
                                               "monthly_cost": 100}),
                           _FakeRequest())
    assert ok_body.get("ok") is True, "成功授权应回 ok=True"
    assert "贯" in ok_body["message"] and "万两" not in ok_body["message"]

    fail_body = S.api_action(S.ActionReq(action="authorize_case",
                                         params={"task_id": "ltp1", "budget": 1}),
                             _FakeRequest())
    assert fail_body.get("ok") is False, "重复授权（HTTP 200）必须回 ok=False"
    assert "已授权过" in fail_body["message"]

    # 普通动作不下发 ok（旧契约不变）：未知诏草 → 返回可读 msg，不抛
    other = S.api_action(S.ActionReq(action="reject_edict_draft",
                                     params={"draft_id": "no-such-draft"}),
                         _FakeRequest())
    assert "ok" not in other, "非拒绝式动作不得新增 ok 字段（避免前端误判）"
    assert other["message"]
