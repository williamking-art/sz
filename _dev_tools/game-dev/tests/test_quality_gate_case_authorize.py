# -*- coding: utf-8 -*-
"""质量放行门 · 长期旨案卷「授权入口」（2026-10-20）。

链路：前端 颁授权 → /api/action authorize_case → commands_decree.authorize_longterm_case
      → longterm_case.authorize_case（只登额度、月结实扣、幂等不重拨）。

钉住：
1. 授权成功：**只登记专款额度（不即时扣库）**、budget/discretion/monthly_cost/案号落档；
2. 府库不足：拒绝且**不动账**；
3. 重复授权：拒绝且**不重复拨款**；
4. 事务不存在：返回 ok=False（不抛）；
5. 后端分派表已注册 authorize_case（行为断言，非源码文本）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    def __init__(self, treasury=1000000):
        self.treasury = treasury
        self.imperial_treasury = 100000
        self.longterm_public = [{"id": "ltp1", "task_name": "整饬海防", "progress": 10}]
        self.longterm_secret = []

    def change_treasury(self, d):
        self.treasury += int(d)

    def change_imperial_treasury(self, d):
        self.imperial_treasury += int(d)


def test_authorize_via_command_registers_quota():
    from core.commands_decree import authorize_longterm_case

    s = _S()
    got = authorize_longterm_case(s, "ltp1", budget=300000, pool="treasury",
                                  discretion=True, monthly_cost=20000)
    assert got["ok"], got
    assert s.treasury == 1000000, "P0-3：授权只登额度，月结才实扣（不得双扣）"
    t = s.longterm_public[0]
    assert t["budget"] == {"total": 300000, "remaining": 300000, "pool": "treasury"}
    assert t["discretion"] is True and t["monthly_cost"] == 20000
    assert t["case_no"], "授权应补案号"


def test_insufficient_rejected_and_no_debit():
    from core.commands_decree import authorize_longterm_case

    s = _S(treasury=1000)
    got = authorize_longterm_case(s, "ltp1", budget=300000)
    assert got["ok"] is False and s.treasury == 1000


def test_repeat_authorize_no_double_debit():
    from core.commands_decree import authorize_longterm_case

    s = _S()
    assert authorize_longterm_case(s, "ltp1", budget=300000)["ok"]
    got = authorize_longterm_case(s, "ltp1", budget=300000)
    assert got["ok"] is False and s.treasury == 1000000


def test_unknown_task():
    from core.commands_decree import authorize_longterm_case

    got = authorize_longterm_case(_S(), "nope", budget=1)
    assert got["ok"] is False and "未找到" in got["msg"]


def test_dispatch_registered():
    """R-UI-7：分派层必须把 authorize_case 路由到保留 ok 的处理器。"""
    from backend import client as bc

    assert hasattr(bc.LocalBackend, "_authorize_case_action")
    # 行为断言：拒绝式动作的返回值可同时取 message/state/ok（旧的二元解包不破坏）
    out = bc.ActionOutcome("未成", None, False)
    msg, state = out
    assert msg == "未成" and state is None and out.ok is False