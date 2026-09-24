# -*- coding: utf-8 -*-
"""批 2 · 局势系统 v1 开局种子回归：成败条件全公开 + 幂等。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from content.situation_seeds import INITIAL_SITUATIONS, seed_initial_situations  # noqa: E402


def test_seed_three_opening_situations_with_public_conditions():
    """开局三条局势：成败条件明文公开、持续代价非空、bar 进度在 0–100。"""
    s = GameState("史实")
    created = seed_initial_situations(s, turn=0)
    assert len(created) == 3, f"应创建 3 条开局局势，实际 {len(created)}"
    titles = {r["title"] for r in created}
    assert titles == {"花石纲民怨", "东南财政亏空", "辽事边备"}
    for rec in created:
        assert rec.get("resolve_condition"), f"{rec['title']} 缺达成条件"
        assert rec.get("fail_condition"), f"{rec['title']} 缺失败条件"
        assert rec.get("ongoing_cost"), f"{rec['title']} 缺持续代价"
        assert 0 <= int(rec.get("bar_value", 0)) <= 100
        assert rec.get("progress_mode") == "bar"
        assert rec.get("status") == "active"
        # 双向语义标签（明末 §3.4：推进=什么好、恶化=什么坏）
        assert rec.get("bar_good_meaning"), f"{rec['title']} 缺推进语义"
        assert rec.get("bar_bad_meaning"), f"{rec['title']} 缺恶化语义"


def test_seed_is_idempotent():
    """幂等：重复 seed 不覆盖玩家进度、不重复建条。"""
    s = GameState("史实")
    first = seed_initial_situations(s, turn=0)
    assert len(first) == 3
    first[0]["bar_value"] = 77  # 模拟玩家推进
    second = seed_initial_situations(s, turn=1)
    assert second == [], "重复 seed 应跳过已存在局势"
    assert len(s.situations) == 3
    assert s.situations[0]["bar_value"] == 77, "不得覆盖玩家进度"


def test_initial_situations_spec_complete():
    """种子规格自检：每条都带 resolve/fail/ongoing/双向语义。"""
    assert len(INITIAL_SITUATIONS) == 3
    for spec in INITIAL_SITUATIONS:
        for key in ("resolve_condition", "fail_condition", "ongoing_cost",
                    "bar_good_meaning", "bar_bad_meaning"):
            assert spec.get(key), f"{spec['title']} 缺 {key}"
