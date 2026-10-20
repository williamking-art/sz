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


def test_update_state_paths_filtered_by_valid_paths():
    """R-AI-7：越界 path 在解析工具调用时即被过滤并标记（不复制白名单）。"""
    import json

    from ai.client_utils import filter_update_state_changes, parse_tool_calls

    kept, rejected = filter_update_state_changes([
        {"path": "treasury", "op": "set", "reason": "合法"},
        {"path": "factions.新党.power", "op": "add", "value": 1, "reason": "越界"},
    ])
    assert [c["path"] for c in kept] == ["treasury"]
    assert [c["path"] for c in rejected] == ["factions.新党.power"]

    resp = {"tool_calls": [{"id": "c1", "function": {
        "name": "update_state",
        "arguments": json.dumps({"changes": [
            {"path": "evil.path", "op": "set", "reason": "越界"}]})}}]}
    out = parse_tool_calls(resp)
    args = out[0]["arguments"]
    assert args["changes"] == [] and args["_rejected_changes"], args


def test_old_task_without_id_gets_stable_id():
    """C-14：旧档事务缺 id → 读档/结算前确定性补齐（同内容同 id、幂等）。"""
    from core.domains.politics.longterm_case import ensure_task_ids_in_state

    class _S:
        pass

    s = _S()
    t = {"title": "旧案", "opened_turn": 2, "progress": 0}
    s.longterm_public = [t]
    s.longterm_secret = []
    s.longterm_cases_archive = []
    assert ensure_task_ids_in_state(s) == 1
    first = str(t.get("id") or "")
    assert first.startswith("ltc_"), first
    assert ensure_task_ids_in_state(s) == 0
    assert t["id"] == first


def test_decree_prefetch_last_result_is_state_scoped():
    """A 补记：诊断副本按 state 隔离，跨局不串档。"""
    from application.decree_prefetch import last_result

    class _S:
        pass

    a, b = _S(), _S()
    a._decree_prefetch_last = {"ok": True, "slots": {"pace": "速"}}
    b._decree_prefetch_last = {"ok": False, "slots": None}
    assert last_result(a) == {"ok": True, "slots": {"pace": "速"}}
    assert last_result(b) == {"ok": False, "slots": None}
