# -*- coding: utf-8 -*-
"""AI/行政/军事/后端审计 P1 第二批修复回归（audit-ai-admin · 2026-10-17）。

覆盖：
- P1-3 准奏奏折 effects 档位 -> 数值不再归 0
- P1-5 effect_channels 只读：不得惰性写 prefect_officials/circuit_officials
- P1-9 HttpBackend.save_slots 必须请求服务端 /api/save_slots
- P1-11 unrest=None 不得 TypeError
- P1-12 countersigned 缺失不得当已签（ratio 不是 1.0，且 reason 可诊断）
"""
import os
import sys
import types

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import commands as cmd                                # noqa: E402
from core import commands_decree as cdec                        # noqa: E402
from core.decree_effect import effect_channels                  # noqa: E402
from core.game_state import GameState                           # noqa: E402
from core.settlement_military import _settle_military_diplomacy  # noqa: E402


def test_memorial_effects_not_zeroed_for_five_kinds():
    """P1-3：准奏草稿的 effect 经 effects_to_dict 后至少一个非 0。"""
    cases = {
        "finance": "treasury",
        "military": "defense_bonus",
        "governance": "population_satisfaction",
        "personnel": "prestige",
        "invention": "prestige",
    }
    s = GameState("史实")
    for kind, dim in cases.items():
        memo = {"kind": kind, "title": f"{kind}奏", "body": "请准",
                "effect_dim": dim, "effect_tier": "中"}
        eff = cdec._build_memorial_effects(memo)
        assert all(isinstance(v, str) for k, v in eff.items() if k != "faction_change"), \
            f"{kind} 生成 effects 应使用档位词：{eff}"
        numeric = cdec._draft_to_effects_dict(s, {"effects": eff})
        flat = [v for v in numeric.values() if isinstance(v, (int, float))]
        assert flat and any(abs(v) > 0 for v in flat), f"{kind} 准奏效果全归 0：{eff} -> {numeric}"
        assert numeric.get(dim, 0) != 0, f"{kind} 维度 {dim} 未落地：{numeric}"


def test_effect_channels_does_not_write_lazy_official_books():
    """P1-5：effect_channels 是只读读数，不得首次调用写 136/21 官册。"""
    s = GameState("史实")
    before_keys = set(vars(s))
    before_prefect = len(getattr(s, "prefect_officials", {}) or {})
    before_circuit = len(getattr(s, "circuit_officials", {}) or {})
    before_stats = len(getattr(s, "official_stats", {}) or {})
    effect_channels(s, kind="民政", route="两浙路")
    assert set(vars(s)) == before_keys, "effect_channels 新增了 state 属性"
    assert len(getattr(s, "prefect_officials", {}) or {}) == before_prefect
    assert len(getattr(s, "circuit_officials", {}) or {}) == before_circuit
    assert len(getattr(s, "official_stats", {}) or {}) == before_stats


def test_new_game_initializes_official_books_explicitly():
    """P1-5：新局应在 game_init 显式初始化两册，而不是等读数懒加载。"""
    s = cmd.new_game("史实")
    assert len(getattr(s, "prefect_officials", {}) or {}) == 136
    assert len(getattr(s, "circuit_officials", {}) or {}) == 21

def test_http_backend_save_slots_requests_server(monkeypatch):
    """P1-9：远程 save_slots 必须请求 /api/save_slots，不得读本地目录。"""
    from backend.client import HttpBackend

    calls = []
    be = HttpBackend("http://example.invalid")

    def _fake_post(path, payload=None, _attempt=0, _cold=False, **kwargs):
        calls.append((path, kwargs.get("_method")))
        return {"slots": [{"slot": 3, "label": "服务端档"}]}

    monkeypatch.setattr(be, "_post", _fake_post)
    slots = be.save_slots()
    assert calls == [("/api/save_slots", "GET")]
    assert slots == [{"slot": 3, "label": "服务端档"}]


def test_unrest_none_does_not_raise():
    """P1-11：unrest 键存在但值为 None 时不得 float(None) 崩溃。"""
    s = cmd.new_game("史实")
    unit = max(s.army_units, key=lambda u: u.troops)
    unit.arrears = 300000
    p = s.prefectures[unit.station]
    p["unrest"] = None
    log = []
    _settle_military_diplomacy(s, log)
    assert isinstance(p["unrest"], (int, float))
    assert p["unrest"] >= 20.0
    assert any("欠饷久滞" in x for x in log), log


def test_countersigned_missing_is_not_treated_as_signed():
    """P1-12：countersigned 缺失/None 不得默认已连署。"""
    s = cmd.new_game("史实")
    route = "两浙路"
    seats = [v for v in (s.prefect_officials or {}).values()
             if isinstance(v, dict) and v.get("circuit") == route]
    assert seats, "测试前提：两浙路应有州府席位"
    for st in seats:
        st.pop("countersigned", None)
    ch = effect_channels(s, kind="民政", route=route)
    comp = ch.get("clerks_compliance") or {}
    ratio = comp.get("countersign_ratio")
    assert ratio is not None, ch
    assert ratio < 1.0, f"缺失 countersigned 被当成已签：{comp}"
    assert comp.get("countersign_undefined", 0) >= len(seats), comp
    assert "缺失" in str(comp.get("countersign_reason", "")), comp

def test_accept_memorial_writes_nonzero_draft_effects():
    """P1-3：走真实 accept_memorial -> edict_draft 链路，草稿数值效果非 0。"""
    cases = {
        "finance": "treasury",
        "military": "defense_bonus",
        "governance": "population_satisfaction",
        "personnel": "prestige",
        "invention": "prestige",
    }
    s = cmd.new_game("史实")
    for kind, dim in cases.items():
        s.memorials = [{"kind": kind, "title": f"{kind}奏", "body": "请准",
                        "effect_dim": dim, "effect_tier": "中"}]
        res = cdec.accept_memorial(s, 0)
        assert res.get("ok") is True, res
        draft = s.get_edict_draft(res["draft_id"])
        numeric = cdec._draft_to_effects_dict(s, draft)
        assert numeric.get(dim, 0) != 0, f"{kind} 准奏草稿 {dim} 为 0：{draft}/{numeric}"
