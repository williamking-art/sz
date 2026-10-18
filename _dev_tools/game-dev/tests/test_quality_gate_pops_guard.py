# -*- coding: utf-8 -*-
"""质量放行门 · POP 守卫（B-2a）。

对应设计：`_dev_tools/game-docs/specs/cross-cutting/B2_守卫与质量放行门_设计与取证_2026-10-12.md`
（A1/A2/A3/A4/A6/A8 与 N2/N3/N7/N8）。本文件**只是门的用例**，不改生产语义。

门要回答的问题：**"账本状态是否合规"**，而不是"守卫代码是否存在"。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

import pytest

from core.foundation.ledger.pop_bridge import (  # noqa: E402
    _GuardedPops,
    assert_pops_consistent,
    install_all_guards,
    pops_guard_violation_details,
    pops_guard_violations,
    reset_pops_guard,
    set_pops_guard_trace,
    survey_pops,
    uninstall_all_guards,
)

MONTHS = int(os.environ.get("SONGZUO_GATE_MONTHS", "15"))


def _new_state():
    from core.commands import new_game

    return new_game()


def _pops_types(state) -> set:
    return {type(p.get("pops")) for p in state.prefectures.values()}


def _guard_would_install(state) -> int:
    """N8：证明守卫**装得上**（>0 路），否则"零违规"是空转。"""
    reset_pops_guard()
    n = install_all_guards(state)
    uninstall_all_guards(state)
    reset_pops_guard()
    return int(n)


def _run_gated(months: int, inject_at: int | None = None):
    """在 `SONGZUO_POPS_GUARD=1` 语义下跑 `settle_local`，逐月收集违规。"""
    from core.commands import settle_local
    import core.commands as cmds

    state = _new_state()
    per_month: list[list] = []
    real_rms = cmds.run_monthly_settlement

    def _rms(st, *a, **k):
        if inject_at is not None and len(per_month) == inject_at:
            # N7 注入：绕过桥接，直接写路级镜像（应被守卫抓到）
            pdata = next(iter(st.prefectures.values()))
            pops = pdata.get("pops") or {}
            cls = next(iter(pops))
            pops[cls] = dict(pops[cls])
        return real_rms(st, *a, **k)

    import core.commands as _c

    _c.run_monthly_settlement = _rms
    try:
        for _ in range(months):
            settle_local(state)
            per_month.append(list(pops_guard_violations()))
    finally:
        _c.run_monthly_settlement = real_rms
    return state, per_month


def test_gate_guard_is_not_a_no_op():
    """A3/N8：守卫确实能装（>0 路），否则后续"零违规"不可信。"""
    state = _new_state()
    assert _guard_would_install(state) > 0, "守卫装配路数为 0 ⇒ 门是空转"


def test_gate_zero_route_pops_violations(monkeypatch):
    """A1/A2/A3：生产开关下连跑 ≥15 月，逐月零违规且账本一致。"""
    monkeypatch.setenv("SONGZUO_POPS_GUARD", "1")
    state, per_month = _run_gated(MONTHS)

    assert len(per_month) == MONTHS
    bad = [(i + 1, v) for i, v in enumerate(per_month) if v]
    assert not bad, f"正常局出现路级直写（第几月, 违规）：{bad[:3]}"

    # A2：真账/镜像逐路一致，且巡检无字段失配
    mismatched = [r for r, p in state.prefectures.items() if assert_pops_consistent(p)]
    assert not mismatched, f"路级与治所不一致：{mismatched[:5]}"
    survey = survey_pops(state)
    assert not survey.get("字段失配"), f"survey_pops 报字段失配：{survey.get('字段失配')}"
    # N3：还原与零违规是两件事，分别断言
    assert _GuardedPops not in _pops_types(state), "结算后路级 pops 必须还原为 plain dict"


def test_gate_detects_injected_direct_write(monkeypatch):
    """A4/N7：注入一处绕过桥接的路级直写 ⇒ 门必须变红（非空转证明）。"""
    monkeypatch.setenv("SONGZUO_POPS_GUARD", "1")
    state, per_month = _run_gated(3, inject_at=1)
    caught = [v for v in per_month if v]
    assert caught, "注入路级直写后仍未记录违规 ⇒ 门是假绿"
    assert _GuardedPops not in _pops_types(state), "异常路径也不得残留守卫子类"


def test_gate_violation_attribution_is_readable(monkeypatch):
    """A6：开启归因后，违规明细含 file/line/function（只测试期开启）。"""
    monkeypatch.setenv("SONGZUO_POPS_GUARD", "1")
    import core.foundation.ledger.pop_bridge as pb

    real_reset = pb.reset_pops_guard

    def _reset_keep_trace():
        # settle_local 每月开跑前会 reset（连带关掉归因），这里在 reset 后重新开启
        real_reset()
        pb.set_pops_guard_trace(True)

    monkeypatch.setattr(pb, "reset_pops_guard", _reset_keep_trace)
    try:
        # 只跑 1 月：settle_local 每次开跑前会 reset 守卫记账，跨月会把上月明细清掉
        _state, per_month = _run_gated(1, inject_at=0)
        details = pb.pops_guard_violation_details()
    finally:
        monkeypatch.undo()
        real_reset()
    assert any(per_month), "注入后应记录违规"
    assert details, "违规明细为空，归因不可用"
    first = details[0]
    for key in ("file", "line", "function"):
        assert key in first, f"归因字段缺失：{key}（实际 {sorted(first)}）"
    assert int(first["line"]) > 0


def test_gate_default_env_keeps_plain_dict(monkeypatch):
    """A5：缺省（不设 env）行为不变——不装守卫、不残留子类。"""
    monkeypatch.delenv("SONGZUO_POPS_GUARD", raising=False)
    from core.commands import settle_local

    state = _new_state()
    turn0 = state.turn
    settle_local(state)
    assert state.turn == turn0 + 1
    assert _GuardedPops not in _pops_types(state)
