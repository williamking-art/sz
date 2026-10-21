# -*- coding: utf-8 -*-
"""H P0（只读）：迁移后总量投影，迁移前后 Σ 应相等（不写 state）。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def _fp(s) -> str:
    txt = json.dumps(s.prefectures, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def test_projection_is_readonly_and_total_neutral():
    from core.commands import new_game
    from core.foundation.ledger.grain_ledger import project_grain_migration

    s = new_game("史实")
    before = _fp(s)
    rep = project_grain_migration(s)
    assert _fp(s) == before, "投影不得改 prefectures"
    assert rep["read_only"] is True
    assert rep["pops"] > 0 and rep["to_migrate"] > 0
    assert rep["projected_delta"] == 0, rep
    assert rep["legacy_sum"] == rep["projected_sum"] > 0
    assert rep["target_dim"] == "米"


def test_projection_existing_bucket_kept():
    from core.foundation.ledger.grain_ledger import project_grain_migration

    class S:
        pass

    s = S()
    s.prefectures = {"路A": {"seats": {"a": {"pops": {
        "农": {"grain": 1000, "goods": {"米": 4, "麦": 6}},
    }}}}}
    rep = project_grain_migration(s)
    assert rep["already"] == 1 and rep["to_migrate"] == 0
    assert rep["projected_sum"] == 10
