# -*- coding: utf-8 -*-
"""Jev 决策闸门定向回归（game/ai/jev_gate.py + contracts_decree 接线）。

锁定四条边界（都是"不做就会出事"的）：
  1. **默认禁用**：无配置 → 整层关闭，主流程行为不变；
  2. **一次调用**：N 个动作打包成 1 次 Jev 调用（省钱是设计要点，退化成 N 次要被抓）；
  3. **失败不变更**：Jev 报错/超时/返回垃圾 → 计划原样返回，绝不抛进主流程；
  4. **脱敏**：玩家可见的 reason 只有档位词，**不得出现数字**。
"""

import re

import pytest

from ai import jev_gate
from ai.contracts_decree import DecreeContractMixin


@pytest.fixture
def jev_on(monkeypatch, tmp_path):
    """把 Jev 打开，并把配置路径指到不存在的位置（避免读本机真实 ai_config.json）。"""
    monkeypatch.setenv("SONGZUO_JEV_ENABLED", "1")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key-not-real")
    monkeypatch.setattr("ai.client_utils.resolve_ai_config_path",
                        lambda *a, **k: str(tmp_path / "no-such-ai-config.json"))
    return tmp_path


@pytest.fixture
def jev_off(monkeypatch, tmp_path):
    monkeypatch.delenv("SONGZUO_JEV_ENABLED", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr("ai.client_utils.resolve_ai_config_path",
                        lambda *a, **k: str(tmp_path / "no-such-ai-config.json"))


EDICT = "朕欲于两浙路兴修水利，以利农桑。"
ACTIONS = [
    {"source_fragment": "朕欲于两浙路兴修水利", "title": "两浙路兴修水利"},
    {"source_fragment": "", "title": "顺便裁撤三司"},          # 原文无据（应被复核挑出）
]


# ---------------------------------------------------------------- 1. 默认禁用
def test_disabled_by_default(jev_off):
    assert jev_gate.load_config() is None
    assert jev_gate.enabled() is False
    assert jev_gate.review_actions(EDICT, ACTIONS) is None
    assert jev_gate.assess_irreversibility(EDICT, {"actions": ACTIONS}) is None


def test_disabled_leaves_plan_untouched(jev_off):
    from ai.contracts_decree import _append_jev_review
    plan = {"decree_id": "d1", "actions": ACTIONS, "unresolved": [{"source_fragment": "a", "reason": "b"}]}
    out = _append_jev_review(EDICT, plan)
    assert out["unresolved"] == [{"source_fragment": "a", "reason": "b"}]


# ---------------------------------------------------------------- 2. 一次调用
def test_review_packs_all_actions_into_single_call(jev_on, monkeypatch):
    calls = []

    def fake_decide(cfg, state, questions):
        calls.append({"state": state, "questions": questions})
        # 第一个动作有据（p 高），第二个无据（p 低）
        return {"answers": {"a0": {"type": "noul", "noul": 0.92},
                            "a1": {"type": "noul", "noul": 0.07}},
                "usage": {"input_tokens": 10, "output_tokens": 2}}

    monkeypatch.setattr(jev_gate, "_decide", fake_decide)
    extra = jev_gate.review_actions(EDICT, ACTIONS)

    assert len(calls) == 1, "N 个动作必须打包成一次调用"
    assert set(calls[0]["questions"]) == {"a0", "a1"}
    assert calls[0]["state"] == EDICT
    assert len(extra) == 1
    assert extra[0]["source_fragment"] == ""
    assert extra[0]["reason"] == jev_gate._REASON_LOW


def test_reason_has_no_digits(jev_on, monkeypatch):
    """脱敏：玩家可见文案里不得出现概率数字。"""
    monkeypatch.setattr(jev_gate, "_decide",
                        lambda cfg, s, q: {"answers": {"a0": {"noul": 0.01},
                                                       "a1": {"noul": 0.01}}})
    extra = jev_gate.review_actions(EDICT, ACTIONS)
    assert extra and all(not re.search(r"\d", e["reason"]) for e in extra)


def test_high_support_produces_nothing(jev_on, monkeypatch):
    monkeypatch.setattr(jev_gate, "_decide",
                        lambda cfg, s, q: {"answers": {"a0": {"noul": 0.99},
                                                       "a1": {"noul": 0.88}}})
    assert jev_gate.review_actions(EDICT, ACTIONS) is None


# ---------------------------------------------------------------- 3. 失败不变更
@pytest.mark.parametrize("bad", [None, {}, {"answers": None}, {"answers": {"a0": "x"}}])
def test_bad_response_yields_none(jev_on, monkeypatch, bad):
    monkeypatch.setattr(jev_gate, "_decide", lambda cfg, s, q: bad)
    assert jev_gate.review_actions(EDICT, ACTIONS) is None


def test_gate_exception_does_not_escape(jev_on, monkeypatch):
    from ai.contracts_decree import _append_jev_review

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(jev_gate, "review_actions", boom)
    plan = {"decree_id": "d1", "actions": ACTIONS, "unresolved": []}
    assert _append_jev_review(EDICT, plan)["unresolved"] == []


# ---------------------------------------------------------------- 4. 真实链路
class _StubClient(DecreeContractMixin):
    """只桩掉 LLM 两端，让 decree_action_plan 的**真实后处理链路**跑起来。"""

    def _call(self, *a, **k):          # noqa: D102
        return "{}"

    def _postprocess(self, raw, validate, fallback, retry_prompt=None, **k):  # noqa: D102
        return {"decree_id": "d1",
                "actions": list(ACTIONS),
                "unresolved": [],
                "narrative": "按语"}


def test_decree_action_plan_appends_review_findings(jev_on, monkeypatch):
    entry = {"source_fragment": "", "reason": jev_gate._REASON_LOW}
    monkeypatch.setattr(jev_gate, "review_actions", lambda text, acts: [entry])
    plan = _StubClient().decree_action_plan(EDICT, routes=["两浙路"], decree_id="d1")
    assert entry in plan["unresolved"]


def test_decree_action_plan_unchanged_when_gate_off(jev_off):
    plan = _StubClient().decree_action_plan(EDICT, routes=["两浙路"], decree_id="d1")
    assert plan["unresolved"] == []
    assert plan["actions"] == ACTIONS


def test_decree_action_plan_survives_gate_boom(jev_on, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(jev_gate, "review_actions", boom)
    plan = _StubClient().decree_action_plan(EDICT, routes=["两浙路"], decree_id="d1")
    assert plan["decree_id"] == "d1" and plan["unresolved"] == []
