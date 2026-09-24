# -*- coding: utf-8 -*-
"""批 3 · 月度奏章八章回归：章节完整率 100% + 必补三章 + 七言联。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.monthly_gazette import (  # noqa: E402
    CHAPTER_ORDER, GAZETTE_COUPLETS, build_monthly_gazette,
)


def test_chapter_order_complete():
    """八章固定顺序（章节完整率 100% 验收）。"""
    assert len(CHAPTER_ORDER) == 8
    assert CHAPTER_ORDER[0] == "诏书核销"
    assert CHAPTER_ORDER[-1] == "邦交"
    for must in ("长期局势", "密令动向", "人物历练"):
        assert must in CHAPTER_ORDER


def test_build_gazette_has_all_chapters_and_couplet():
    """组装产物含 8 章 + 七言联 + 差值摘要键；空月也有标题与占位行。"""
    s = GameState("史实")
    g = build_monthly_gazette(s, year=1102, month=3)
    assert g["year"] == 1102 and g["month"] == 3
    assert len(g["chapters"]) == 8
    titles = [c["title"] for c in g["chapters"]]
    assert titles == list(CHAPTER_ORDER)
    for c in g["chapters"]:
        assert isinstance(c["lines"], list) and len(c["lines"]) >= 1, f"{c['title']} 空章无占位"
    assert g["couplet"] in GAZETTE_COUPLETS
    assert isinstance(g["diff_summary"], list)


def test_situation_chapter_lists_records():
    """长期局势章：逐条列出开局三局势（bar + 双向语义）。"""
    from content.situation_seeds import seed_initial_situations
    s = GameState("史实")
    seed_initial_situations(s, turn=0)
    g = build_monthly_gazette(s, year=1102, month=3)
    sit = next(c for c in g["chapters"] if c["title"] == "长期局势")
    text = "\n".join(sit["lines"])
    assert "花石纲民怨" in text
    assert "东南财政亏空" in text
    assert "辽事边备" in text
    assert "进度" in text


def test_secret_chapter_lists_pending():
    """密令动向章：待发密令可见。"""
    s = GameState("史实")
    s.pending_secret_decrees = [{"title": "密查东南花石", "content": "…"}]
    g = build_monthly_gazette(s, year=1102, month=3)
    sec = next(c for c in g["chapters"] if c["title"] == "密令动向")
    assert any("密查东南花石" in ln for ln in sec["lines"])


def test_settlement_persists_monthly_gazette():
    """结算后 state.monthly_gazette 落账（最近月含八章）。"""
    from core.settlement import run_monthly_settlement
    s = GameState("史实")
    run_monthly_settlement(s, seed_offset=3)
    hist = s.monthly_gazette
    assert isinstance(hist, list) and len(hist) >= 1
    last = hist[-1]
    assert len(last["chapters"]) == 8
    assert last["couplet"]
