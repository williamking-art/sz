# -*- coding: utf-8 -*-
"""R-N-6：长期旨案卷月结失败必须累计持久计数（不能只 append 一行日志）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def test_longterm_settle_failure_increments_persistent_error_count(monkeypatch):
    import core.domains.politics.longterm_case as LC
    import core.settlement as S
    from core.commands import new_game

    s = new_game("史实")
    before = int(s.statistics.get("longterm_settle_errors", 0) or 0)

    def boom(state, task, log):
        raise RuntimeError("注入：案卷结算失败")

    # 保证一定进入案卷结算分支（不依赖 new_game 是否已有案卷化事务）
    monkeypatch.setattr(LC, "iter_case_tasks", lambda state: [{"task_id": "t1"}])
    monkeypatch.setattr(LC, "case_is_cased", lambda task: True)
    monkeypatch.setattr(LC, "monthly_case_settle", boom)
    S.run_monthly_settlement(s)
    after = int(s.statistics.get("longterm_settle_errors", 0) or 0)
    assert after == before + 1, (before, after)
