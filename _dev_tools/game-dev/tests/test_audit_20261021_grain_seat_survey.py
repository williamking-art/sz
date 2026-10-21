# -*- coding: utf-8 -*-
"""H 首批（Jev A 0.996）：治所级 legacy grain vs goods 米麦 只读对账/映射。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def _fp(s) -> str:
    txt = json.dumps(s.prefectures, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def test_seat_grain_survey_read_only_and_mapping():
    from core.commands import new_game
    from core.foundation.ledger.grain_ledger import survey_grain_seats

    s = new_game("史实")
    before = _fp(s)
    rep = survey_grain_seats(s)
    assert _fp(s) == before, "只读对账不得改 prefectures"
    assert rep["read_only"] is True
    assert rep["seat_count"] > 0 and rep["pop_count"] > 0
    assert rep["migration_state"] in ("未迁移", "部分迁移", "已迁移")
    assert rep["mapping"][0]["from"] == "pops[].grain"
    assert rep["mapping"][0]["to_dim"] == "米"
    assert rep["mapping"][0]["split"] is False
    # 严格计数：四态之和 == POP 数
    assert rep["both"] + rep["legacy_only"] + rep["goods_only"] + rep["neither"] == rep["pop_count"]


def test_seat_grain_survey_counts_legacy_only_initially():
    from core.commands import new_game
    from core.foundation.ledger.grain_ledger import survey_grain_seats

    s = new_game("史实")
    rep = survey_grain_seats(s)
    # 开局 goods 无粮桶：应至少有一个 legacy_only POP（不按 0/已迁移 冒充）
    assert rep["legacy_only"] > 0
    assert rep["sum_legacy_grain"] > 0
    assert rep["migrated_pops"] == 0
    assert rep["mismatch_count"] == 0
