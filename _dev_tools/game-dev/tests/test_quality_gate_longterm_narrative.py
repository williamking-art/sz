# -*- coding: utf-8 -*-
"""质量放行门 · 长期旨天道叙事（2026-10-20）。

链路：AI 契约 longterm_narrative_decide（前置）→ state._longterm_ai
      → monthly_case_settle 只读槽位写进推进日志（结算期零 HTTP）。

钉住：
1. 生产者：合法响应 ⇒ 槽位被填；非法档位/id 不存在的条目**丢弃**；全无效 ⇒ 不写槽位；
2. 无事务 ⇒ 返回 None（不假装已判）；
3. 消费者：槽位有本事务叙事 ⇒ 写进 progress_log；无槽位 ⇒ 叙事为空（行为不变）；
4. 已注册为可唤醒 Agent 且 token 分组为「推演」；
5. 结算链不 import jev_gate / 不做同步 HTTP。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    def __init__(self, treasury=1000000):
        self.treasury = treasury
        self.imperial_treasury = 0
        self.prestige = 60
        self.population_satisfaction = 50
        self.turn = 12
        self.longterm_public = [{"id": "ltp1", "task_name": "整饬海防", "progress": 40}]
        self.longterm_secret = []

    def change_treasury(self, d):
        self.treasury += int(d)

    def change_imperial_treasury(self, d):
        self.imperial_treasury += int(d)

    def change_prestige(self, d, reason=""):
        self.prestige += int(d)


def _client(monkeypatched):
    from ai.client import AIClient

    c = AIClient()
    c._call = lambda *a, **k: monkeypatched   # 只替换网络调用，保留 _postprocess 校验
    return c


def test_producer_fills_slot():
    s = _S()
    raw = '{"items":[{"id":"ltp1","tier":"迟滞","narrative":"海防工事迟滞，烽堠未及齐备。"}],"narrative":"在办案卷缓进。"}'
    got = _client(raw).longterm_narrative_decide(s)
    assert got and s._longterm_ai["items"][0]["tier"] == "迟滞"
    assert "烽堠" in s._longterm_ai["items"][0]["narrative"]


def test_producer_drops_invalid_items():
    s = _S()
    raw = '{"items":[{"id":"nope","tier":"顺利","narrative":"虚构"},{"id":"ltp1","tier":"胡说","narrative":"x"}],"narrative":"y"}'
    assert _client(raw).longterm_narrative_decide(s) is None
    assert not hasattr(s, "_longterm_ai")


def test_producer_no_tasks():
    s = _S()
    s.longterm_public = []
    assert _client("{}").longterm_narrative_decide(s) is None


def test_consumer_uses_slot_narrative():
    from core.domains.politics.longterm_case import monthly_case_settle

    s = _S()
    s._longterm_ai = {"items": [{"id": "ltp1", "tier": "迟滞", "narrative": "海防迟滞。"}]}
    t = s.longterm_public[0]
    monthly_case_settle(s, t, [], progress=45)
    assert t["progress_log"][-1]["narrative"] == "海防迟滞。"


def test_consumer_without_slot_keeps_empty():
    from core.domains.politics.longterm_case import monthly_case_settle

    s = _S()
    t = s.longterm_public[0]
    monthly_case_settle(s, t, [], progress=45)
    assert t["progress_log"][-1]["narrative"] == ""


def test_registered_and_grouped():
    from ai.token_meter import token_group_of
    from application import agent_router as ar

    assert "longterm_narrative" in ar.AGENT_DEFS
    assert ar.AGENT_DEFS["longterm_narrative"]["method"] == "longterm_narrative_decide"
    assert token_group_of("longterm_narrative_decide") == "推演"


def test_settlement_no_sync_http():
    import inspect

    from core.domains.politics import longterm_case as lc

    src = inspect.getsource(lc)
    for banned in ("requests.", "httpx.", "urllib.request", "jev_gate"):
        assert banned not in src, banned