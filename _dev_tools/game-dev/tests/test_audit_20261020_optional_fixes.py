# -*- coding: utf-8 -*-
"""2026-10-20 可选层小修：C-10 blocked 不推进 + money_audit 初始 error_count + 队列坏条目。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def test_blocked_case_does_not_advance_last_turn():
    from core.domains.politics import longterm_case as LC
    from core.commands import new_game

    s = new_game("史实")
    task = {"id": "t1", "title": "测试案卷", "progress": 0}
    LC.ensure_case_fields(s, task)
    # 授权后把国库清空，使月结 blocked
    s.treasury = 0
    LC.authorize_case(s, task, budget=0, monthly_cost=100)
    out = LC.monthly_case_settle(s, task)
    assert out.get("blocked"), out
    assert task.get("last_advance_turn") is None, "blocked 月不得更新最后推进回合"


def test_money_audit_initial_error_count_is_zero():
    from core.commands import new_game

    s = new_game("史实")
    assert s.money_audit.get("error_count") == 0


def test_transport_queue_bad_qty_is_not_counted_or_crash_flush():
    from core.commands import new_game
    from core.transport import transport_flush_queue

    s = new_game("史实")
    s.transport_queue = [{"mode": "overland", "qty": "坏值", "kind": "goods"},
                         {"mode": "overland", "qty": 1.0, "kind": "goods",
                          "payload": {}}]
    # 坏条目不得让续发崩溃（修前 float("坏值") 直接抛）
    out = transport_flush_queue(s)
    assert isinstance(out, dict) and "pending" in out
