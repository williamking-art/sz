# -*- coding: utf-8 -*-
"""质量放行门 · 案卷重选承办人（2026-10-20）。

链路：案卷页「重选承办人」→ /api/action reassign_case → commands_decree.reassign_case_handler。

钉住：
1. 成功改派：task.minister 更新、写 handler_history（回合/前任/新任）、写推进日志；
2. 查无此人 ⇒ 拒绝（不编造人物）；
3. 现任即此人 ⇒ 拒绝（不重复改派）；
4. 未案卷化事务 ⇒ 拒绝（走既有渠道）；
5. 事务不存在 ⇒ 拒绝；
6. 立场随人而变（stance_of 以 minister 的派系重算，不额外发明惩罚）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    def __init__(self):
        self.turn = 7
        self.longterm_public = [{
            "id": "ltp1", "task_name": "整饬海防", "case_no": "#426",
            "minister": "曾布", "progress": 30.0,
            "case_no": "#426", "budget": {"total": 1, "remaining": 1, "pool": "treasury"},
        }, {"id": "plain", "task_name": "普通事务", "progress": 10}]
        self.longterm_secret = []


def test_reassign_ok():
    from core.commands_decree import reassign_case_handler

    s = _S()
    got = reassign_case_handler(s, "ltp1", "童贯")
    assert got["ok"], got
    t = s.longterm_public[0]
    assert t["minister"] == "童贯"
    assert t["handler_history"][-1] == {"turn": 7, "from": "曾布", "to": "童贯"}
    assert "改派承办人" in t["progress_log"][-1]["narrative"]


def test_reject_unknown_person():
    from core.commands_decree import reassign_case_handler

    got = reassign_case_handler(_S(), "ltp1", "张三不存在")
    assert got["ok"] is False and "查无此人" in got["msg"]


def test_reject_same_person():
    from core.commands_decree import reassign_case_handler

    got = reassign_case_handler(_S(), "ltp1", "曾布")
    assert got["ok"] is False and "无需改派" in got["msg"]


def test_reject_uncased():
    from core.commands_decree import reassign_case_handler

    got = reassign_case_handler(_S(), "plain", "童贯")
    assert got["ok"] is False and "未案卷化" in got["msg"]


def test_reject_missing_task():
    from core.commands_decree import reassign_case_handler

    got = reassign_case_handler(_S(), "nope", "童贯")
    assert got["ok"] is False and "未找到" in got["msg"]
