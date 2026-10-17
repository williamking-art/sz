# -*- coding: utf-8 -*-
"""审计 B-9 定向回归（2026-10-17）：结算管线原子性。

缺陷：49 步仅 13 步 critical，36 个**会改动账本/POP/库存/统计**的步骤异常只记 WARN，
      管线继续跑完并推进回合 ⇒ 半结算脏月（实测注入 supply 失败仍 turn+1）。

本组锁两条：
1. 权威管线所有步骤 `critical=True`（任何状态写入失败都必须整月回滚）；
2. 逐一注入每个步骤异常 → `run_monthly_settlement`/`settle_local` 抛出，
   且 treasury / POP(size+wealth+goods) / resources / statistics 与月初逐字段一致、回合不推进。
"""
import copy
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState  # noqa: E402
from core.settlement_pipeline import get_default_pipeline  # noqa: E402


def _step_ids():
    return [s.id for s in get_default_pipeline().steps]


def _core_snapshot(state):
    """月初/失败回滚后的**逐字段**核心状态快照（账本/POP/资源/统计）。"""
    pops = {}
    for route, p in (getattr(state, "prefectures", None) or {}).items():
        slots = {}
        for cls, pop in ((p or {}).get("pops") or {}).items():
            pop = pop or {}
            slots[cls] = {
                "size": copy.deepcopy(pop.get("size", 0)),
                "wealth": copy.deepcopy(pop.get("wealth", 0)),
                "goods": copy.deepcopy(pop.get("goods") or {}),
                "grain": copy.deepcopy(pop.get("grain") or 0),
            }
        pops[route] = slots
    return {
        "turn": int(getattr(state, "turn", 0) or 0),
        "treasury": int(getattr(state, "treasury", 0) or 0),
        "imperial_treasury": int(getattr(state, "imperial_treasury", 0) or 0),
        "resources": copy.deepcopy(getattr(state, "resources", None)),
        "statistics": copy.deepcopy(getattr(state, "statistics", None)),
        "prefectures_pops": pops,
        "granary": copy.deepcopy(getattr(state, "granary", None)),
    }


def test_default_pipeline_all_steps_are_critical():
    """B-9：49 步全部 critical（不得再有「动账步异常只 WARN」）。"""
    pipe = get_default_pipeline()
    steps = pipe.steps
    assert len(steps) == 49
    non_critical = [s.id for s in steps if not s.critical]
    assert not non_critical, f"仍有非 critical 结算步：{non_critical}"


def _boom(state, log):
    raise RuntimeError("B-9 注入：结算步失败")


def test_run_monthly_settlement_raises_on_money_step_failure(monkeypatch):
    """`run_monthly_settlement` 本身必须抛出（不再吞成 WARN 后推进回合）。"""
    import core.settlement as S

    state = GameState("史实")
    step = get_default_pipeline().get_step("supply_goods_to_seats")
    monkeypatch.setattr(step, "func", _boom)
    with pytest.raises(RuntimeError, match="B-9 注入"):
        S.run_monthly_settlement(state)


@pytest.mark.parametrize("step_id", _step_ids())
def test_each_settlement_step_failure_rolls_back_whole_month(monkeypatch, step_id):
    """注入每个结算步异常：抛出 + 回合不推进 + 核心状态逐字段回滚。"""
    from core.commands import settle_local

    state = GameState("史实")
    before = _core_snapshot(state)

    step = get_default_pipeline().get_step(step_id)
    assert step is not None, f"管线缺步骤 {step_id}"
    monkeypatch.setattr(step, "func", _boom)

    with pytest.raises(RuntimeError, match="B-9 注入"):
        settle_local(state)

    after = _core_snapshot(state)
    assert after == before, f"注入 {step_id} 失败后状态未完整回滚（半结算脏月）"
