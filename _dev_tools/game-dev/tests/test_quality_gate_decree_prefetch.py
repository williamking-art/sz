# -*- coding: utf-8 -*-
"""质量放行门 · 下旨后确定性天道预取（2026-10-20）。

钉住：
1. 下旨成功后**必然尝试**一次预取（不依赖唤醒词）；
2. Jev 不可用 ⇒ 槽位不写、下旨**不失败**（返回消息照常）；
3. 预取的档位能被消费端读到（timing_source=天道）；
4. 非下旨动作**不触发**预取（只有 4 个下旨动作在名单里）；
5. 结算链不含预取调用（静态断言）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _FakeState:
    def __init__(self):
        self.prestige = 70
        self.population_satisfaction = 55
        self.pending_decrees = [{"decree_id": "d1", "title": "加薪诏", "category": "诏令",
                                 "effects": {"pay_reform": "常"}}]


def test_prefetch_fills_slot(monkeypatch):
    from ai import jev_gate
    from application.decree_prefetch import last_result, prefetch_decree_slots

    def fake(ctx, instructions, criteria, *, question_key="q"):
        for k in ("即时", "速", "奉行", "全办"):
            if k in criteria:
                return {"choice": k, "probabilities": {}, "confidence": None}
        return None

    monkeypatch.setattr(jev_gate, "decide_choice", fake)
    s = _FakeState()
    got = prefetch_decree_slots(s)
    assert got and s._decree_ai["execution_timing"] == "即时"
    assert last_result()["ok"] is True


def test_prefetch_failure_does_not_raise(monkeypatch):
    from ai import jev_gate
    from application.decree_prefetch import prefetch_decree_slots

    def boom(*a, **k):
        raise RuntimeError("jev down")

    monkeypatch.setattr(jev_gate, "decide_choice", boom)
    s = _FakeState()
    assert prefetch_decree_slots(s) is None   # 不抛、不写槽位
    assert not hasattr(s, "_decree_ai")


def test_consumer_reads_prefetched_slot(monkeypatch):
    from ai import jev_gate
    from application.decree_prefetch import prefetch_decree_slots
    from core.domains.politics.decree_duration import resolve_decree_duration

    monkeypatch.setattr(jev_gate, "decide_choice",
                        lambda ctx, ins, crit, **k: {"choice": "长期", "probabilities": {}, "confidence": None}
                        if "即时" in crit else None)
    s = _FakeState()
    prefetch_decree_slots(s)
    got = resolve_decree_duration(s, decree_kind="pay_reform", ability=60, followup=0)
    assert got["timing"] == "long" and got["timing_source"] == "天道"


def test_only_decree_actions_in_trigger_list():
    from backend import client as bc

    assert bc._DECREE_ISSUE_ACTIONS == frozenset({
        "issue_decree", "issue_secret_decree", "issue_edict_from_review", "issue_kouyu"})
    assert "settle_local" not in bc._DECREE_ISSUE_ACTIONS


def test_settlement_has_no_prefetch():
    import inspect

    from core import settlement_decree as sd
    from core import settlement as st

    for mod in (sd, st):
        assert "prefetch_decree_slots" not in inspect.getsource(mod)