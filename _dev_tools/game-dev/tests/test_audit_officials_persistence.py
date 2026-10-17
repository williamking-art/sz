# -*- coding: utf-8 -*-
"""P1-6 官员册唯一性/持久化/旧档重建回归（audit-ai-admin · 2026-10-17）。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import commands as cmd                                # noqa: E402
from core.domains.administration.circuit_officials import (    # noqa: E402
    appoint_circuit_official,
)
from core.domains.administration.prefect_officials import (    # noqa: E402
    appoint_prefect_official,
)
from core.foundation.persistence.migrations import ensure_official_books  # noqa: E402
from core.game_state import GameState                           # noqa: E402
from core.save_load import _slot_path, load_game, save_game     # noqa: E402


def _people(s):
    pf = []
    for entry in (s.prefect_officials or {}).values():
        for slot in ("prefect", "subprefect"):
            holder = entry.get(slot) or {}
            if isinstance(holder, dict) and holder.get("person_id"):
                pf.append(holder)
    cb = []
    for entry in (s.circuit_officials or {}).values():
        for holder in (entry.get("officials") or {}).values():
            if isinstance(holder, dict) and holder.get("person_id"):
                cb.append(holder)
    return pf, cb


def test_officials_unique_person_ids_and_names_cross_books():
    """P1-6：272 州府任命 + 126 路级岗位 person_id/姓名唯一，跨册也不撞。"""
    s = cmd.new_game("史实")
    pf, cb = _people(s)
    assert len(pf) == 272, f"prefect 任命数 {len(pf)}"
    assert len(cb) == 126, f"circuit 任命数 {len(cb)}"

    pf_ids = [p["person_id"] for p in pf]
    cb_ids = [c["person_id"] for c in cb]
    pf_names = [p["name"] for p in pf]
    cb_names = [c["name"] for c in cb]
    assert len(set(pf_ids)) == 272 and len(set(cb_ids)) == 126
    assert len(set(pf_names)) == 272, "prefect 册仍有同名多岗"
    assert len(set(cb_names)) == 126, "circuit 册仍有同名多岗"
    assert not (set(pf_ids) & set(cb_ids)), "跨册 person_id 重复"
    assert not (set(pf_names) & set(cb_names)), "跨册姓名重复"

    # 历史人物保留并标记；生成者必须有 historical=False
    assert any(p.get("historical") is True for p in pf)
    assert any(c.get("historical") is True for c in cb)
    assert any(p.get("historical") is False for p in pf)
    assert any(c.get("historical") is False for c in cb)


def test_new_game_official_books_are_initialized_explicitly():
    s = cmd.new_game("史实")
    assert len(s.prefect_officials) == 136
    assert len(s.circuit_officials) == 21


def test_save_load_roundtrip_keeps_appointments_countersign_person_id():
    """P1-6：save/load 后任免、countersign、person_id 逐字段一致。"""
    s = cmd.new_game("史实")
    seat_id = next(iter(s.prefect_officials))
    pf_res = appoint_prefect_official(s, seat_id, "prefect", {
        "name": "测试知州甲", "faction": "中立派", "integrity": 0.91,
        "ability": 0.77, "traits": ["刚直"], "historical": True,
    })
    assert pf_res.get("ok") is True
    route = next(iter(s.circuit_officials))
    cb_res = appoint_circuit_official(s, route, "cao", {
        "name": "测试转运乙", "faction": "旧党", "rank": "从三品",
        "integrity": 0.88, "ability": 0.81, "traits": ["清正"],
        "historical": True,
    })
    assert cb_res is True

    pf_holder = s.prefect_officials[seat_id]["prefect"]
    cb_holder = s.circuit_officials[route]["officials"]["cao"]
    assert pf_holder.get("person_id") and cb_holder.get("person_id")
    countersigned = s.prefect_officials[seat_id].get("countersigned")

    assert save_game(s, 5) is True
    try:
        s2 = load_game(5)
        assert s2 is not None
        pf2 = s2.prefect_officials[seat_id]["prefect"]
        cb2 = s2.circuit_officials[route]["officials"]["cao"]
        for key in ("name", "person_id", "historical", "faction", "integrity", "ability"):
            assert pf2.get(key) == pf_holder.get(key), f"prefect.{key} 未往返"
            assert cb2.get(key) == cb_holder.get(key), f"circuit.{key} 未往返"
        assert s2.prefect_officials[seat_id].get("countersigned") == countersigned
    finally:
        try:
            os.remove(_slot_path(5))
        except OSError:
            pass


def test_old_state_without_books_rebuilds_idempotently():
    """P1-6：旧档无两册键 -> 幂等重建；二次调用不覆盖已生成任免。"""
    s = GameState("史实")
    assert not isinstance(getattr(s, "prefect_officials", None), dict)
    assert not isinstance(getattr(s, "circuit_officials", None), dict)

    first = ensure_official_books(s)
    assert first == {"prefect_officials": 136, "circuit_officials": 21}
    _pf, _cb = _people(s)
    assert not (set(p["person_id"] for p in _pf) & set(c["person_id"] for c in _cb)), \
        "迁移重建后跨册 person_id 重复"
    seat_id = next(iter(s.prefect_officials))
    first_holder = dict(s.prefect_officials[seat_id]["prefect"])
    first_obj = s.prefect_officials

    second = ensure_official_books(s)
    assert second == {"prefect_officials": 136, "circuit_officials": 21}
    assert s.prefect_officials is first_obj, "二次迁移覆盖了已有官员册对象"
    assert s.prefect_officials[seat_id]["prefect"] == first_holder

def test_load_save_with_empty_books_rebuilds_from_migration():
    """旧档没有/空两册键：load 后由 ensure_official_books 重建且可重复读档。"""
    s = GameState("史实")
    s.prefect_officials = {}
    s.circuit_officials = {}
    assert save_game(s, 5) is True
    try:
        loaded = load_game(5)
        assert loaded is not None
        assert len(loaded.prefect_officials) == 136
        assert len(loaded.circuit_officials) == 21
        pf, cb = _people(loaded)
        assert len({p["person_id"] for p in pf}) == 272
        assert len({c["person_id"] for c in cb}) == 126
    finally:
        try:
            os.remove(_slot_path(5))
        except OSError:
            pass

def test_explicit_appointment_on_bare_state_creates_book():
    """显式任免入口不得只改临时派生副本：须把 136 席写入 state。"""
    from core.foundation.ledger.prefecture_entity import all_seats
    s = GameState("史实")
    assert not isinstance(getattr(s, "prefect_officials", None), dict)
    seat_id = all_seats()[0].get("seat_id") or f"{all_seats()[0].get('circuit')}|{all_seats()[0].get('seat')}"
    res = appoint_prefect_official(s, seat_id, "prefect", {
        "name": "显式任免甲", "integrity": 0.80, "ability": 0.70,
        "faction": "中立派", "traits": ["循良"], "historical": True,
    })
    assert res.get("ok") is True, res
    assert len(s.prefect_officials) == 136
    holder = s.prefect_officials[seat_id]["prefect"]
    assert holder["name"] == "显式任免甲"
    assert holder.get("person_id")
