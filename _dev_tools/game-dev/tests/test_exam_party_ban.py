# -*- coding: utf-8 -*-
"""党禁×科举：考官被禁、取士额折扣、三舍限制、cohort ban_context。"""
from core import commands
from core.domains.administration.imperial_exam import (
    run_three_halls_assessment,
    run_triennial_exam_full,
)
from core.faction_ban import start_faction_ban


def _state():
    s = commands.new_game()
    s.exam["examiner_faction"] = "旧党"
    return s


def test_light_ban_blocks_banned_examiner():
    s = _state()
    start_faction_ban(s, "旧党", "轻", turn=0)
    detail = run_triennial_exam_full(s, tier="中")
    assert detail["examiner_faction"] is None
    assert detail["ban_context"]["examiner_blocked"] is True
    assert detail["taken"] > 0


def test_medium_ban_reduces_exam_quota_and_records_context():
    base = _state()
    d0 = run_triennial_exam_full(base, tier="中")
    s = _state()
    start_faction_ban(s, "旧党", "中", turn=0)
    d1 = run_triennial_exam_full(s, tier="中")
    assert d1["ban_context"]["quota_mult"] == 0.85
    assert d1["taken"] < d0["taken"]
    assert s.exam["cohorts"][-1]["ban_context"]["quota_mult"] == 0.85


def test_heavy_ban_blocks_three_halls():
    s = _state()
    start_faction_ban(s, "旧党", "重", turn=0)
    out = run_three_halls_assessment(s)
    assert out["graduates"] == 0
    assert out["status"] == "restricted_by_party_ban"
    assert out["ban_context"]["three_halls_blocked"] is True


def test_no_ban_no_context():
    s = _state()
    detail = run_triennial_exam_full(s, tier="中")
    assert detail["ban_context"] == {}

