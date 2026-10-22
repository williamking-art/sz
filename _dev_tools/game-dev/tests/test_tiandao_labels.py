# -*- coding: utf-8 -*-
"""回测标签：纯逻辑层（`core.ai.tiandao_labels`）+ 工具接线（`_dev_tools/game-dev/tools`）。

判据：
1. **帕累托支配**：唯一"全面不劣且至少一项更优"者才打标签；并列/互有胜负跳过；
   度量向量任一读数缺失 ⇒ 该试验弃用（不拿缺失当 0）。
2. **只改目标 objective**：`forced_record` 不污染其它 objective 的裁决/分布/强度。
3. **turn 对齐**：标签 `turn` 取观测副本的 `turn`（与 `decision_log` 同源）；
   用 `state.turn or (i+1)` 会在首月把 0 变成 1（falsy 坑）⇒ 错位 + 重复标签。
4. **分层**：纯逻辑层不得 import `core.settlement` / `core.commands` / `application`
   （由 `test_architecture_import_guard` 的 R2/R3 强制；结算驱动在工具里）。
5. **无副作用**：冻结观测后必须还原 `TianDaoFacade.observe_monthly`。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_GAME = Path(__file__).resolve().parents[3] / "game"
_TOOLS = Path(__file__).resolve().parents[1] / "tools"      # _dev_tools/game-dev/tools
for _p in (str(_GAME), str(_TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.ai import tiandao_labels as TL  # noqa: E402
from core.ai.tiandao_facade import TianDaoFacade  # noqa: E402


# ---------------------------------------------------------------- 纯函数
def test_pareto_best_unique_dominator():
    assert TL.pareto_best([(3.0,) * 5, (2.0,) * 5]) == 0


def test_pareto_best_none_when_tradeoff_or_tie():
    assert TL.pareto_best([(5.0, 1.0, 1.0, 1.0, 1.0),
                           (1.0, 5.0, 1.0, 1.0, 1.0)]) is None
    assert TL.pareto_best([(1.0,) * 5, (1.0,) * 5]) is None


def test_pareto_best_ignores_missing():
    assert TL.pareto_best([None, (2.0,) * 5, (1.0,) * 5]) == 1
    assert TL.pareto_best([None, None]) is None
    assert TL.pareto_best([(1.0,) * 5]) is None


def test_metric_vector_requires_all_readings():
    class _S:
        treasury = 10
        granary = 10
        prefectures = {"甲": {"local_treasury": 1, "unrest": 1, "refugees": 1}}

    assert TL.metric_vector(_S()) == (10.0, 1.0, 10.0, -1.0, -1.0)
    del _S.prefectures["甲"]["refugees"]
    assert TL.metric_vector(_S()) is None, "缺读数不得当 0 参与比较"


def test_forced_record_only_touches_target():
    rec = {"turn": 3,
           "decisions": {"merchant_trade_or_hoard": "ship"},
           "distributions": {"merchant_trade": {"ship": 0.5, "hoard": 0.3, "local_sell": 0.2},
                             "farmer_path": {"mortgage_land": 0.7, "flee_refugee": 0.3}},
           "strengths": {"recruit_refugees": 0.8}}
    out = TL.forced_record(rec, "farmer_path", "flee_refugee")
    assert out["distributions"]["farmer_path"] == {"flee_refugee": 1.0}
    assert out["decisions"]["merchant_trade_or_hoard"] == "ship"
    assert out["distributions"]["merchant_trade"] == rec["distributions"]["merchant_trade"]
    assert out["strengths"]["recruit_refugees"] == 0.8
    assert rec["distributions"]["farmer_path"]["mortgage_land"] == 0.7      # 原记录不被改
    g = TL.forced_record(rec, "recruit_refugees", True)
    assert g["strengths"]["recruit_refugees"] == 1.0
    assert g["decisions"][TL.method_of("recruit_refugees")] is True


def test_candidates_cover_registry():
    assert TL.candidates_of("farmer_path") == ["mortgage_land", "flee_refugee"]
    assert TL.candidates_of("waive_arrears") == [True, False]
    assert TL.candidates_of("appraisal") is None        # score 模式无分支
    assert TL.candidates_of("not_an_objective") is None


# ---------------------------------------------------------------- 注入式（快，不跑结算）
def _fake_state(turn=0):
    return SimpleNamespace(turn=turn, treasury=1_000.0, granary=10_000.0,
                           prefectures={"甲": {"local_treasury": 100.0,
                                               "unrest": 10.0, "refugees": 5.0}})


def _fake_runner(state, record, seed):
    """按强制分支改数值：强制 flee_refugee 时国库 +50（当作"更优"）。"""
    dist = (record.get("distributions") or {}).get("farmer_path") or {}
    if dist.get("flee_refugee") == 1.0:
        state.treasury += 50.0
    return state


def test_extract_month_labels_picks_unique_dominator():
    st = _fake_state()
    rec = {"turn": 0, "decisions": {}, "distributions": {}, "strengths": {}}
    labels, skipped = TL.extract_month_labels(
        st, rec, turn=0, seed=1, run_month=_fake_runner, objectives=["farmer_path"])
    assert len(labels) == 1 and labels[0]["outcome_dist"] == {"flee_refugee": 1.0}
    assert skipped == []


def test_extract_month_labels_skips_when_tie():
    def _flat(state, record, seed):
        return state                      # 两支结果相同 ⇒ 并列

    labels, skipped = TL.extract_month_labels(
        _fake_state(), {"turn": 0, "decisions": {}, "distributions": {}, "strengths": {}},
        turn=0, seed=1, run_month=_flat, objectives=["farmer_path"])
    assert labels == []
    assert skipped[0]["reason"] == "no_unique_pareto_best"


def test_extract_month_labels_marks_no_candidates():
    labels, skipped = TL.extract_month_labels(
        _fake_state(), {"turn": 0, "decisions": {}, "distributions": {}, "strengths": {}},
        turn=0, seed=1, run_month=_fake_runner, objectives=["appraisal"])
    assert labels == [] and skipped[0]["reason"] == "no_candidates"


def test_turn_alignment_uses_record_turn():
    """月份循环里 turn 必须取观测副本的 turn：首月是 0，不能被 falsy 判成 1。"""
    turns = {"i": 0}

    def make_state():
        return _fake_state(turn=0)

    def observe(state):
        t = turns["i"]
        return {"turn": t, "decisions": {}, "distributions": {}, "strengths": {}}

    def run_month(state, record, seed):
        # 保持"一支更优"，否则会被帕累托并列跳过（本用例只验 turn 对齐）
        _fake_runner(state, record, seed)
        turns["i"] = int(record.get("turn") or 0) + 1
        state.turn = turns["i"]
        return state

    res = TL.extract_labels(2, make_state=make_state, observe_monthly=observe,
                            run_month=run_month, seed=7,
                            objectives=["farmer_path"])
    got = [row["turn"] for row in res["labels"]]
    assert got == [0, 1], got
    assert len(got) == len(set(got)), "不得出现重复 (objective, turn)"


def test_months_validation():
    with pytest.raises(TL.LabelError):
        TL.extract_labels(0, make_state=_fake_state, observe_monthly=lambda s: {},
                          run_month=_fake_runner, seed=1)


# ---------------------------------------------------------------- 真工具端到端（1 月，慢）
def test_tool_generates_labels_and_feeds_backtest(tmp_path):
    import tiandao_labels as TOOL     # _dev_tools/game-dev/tools/tiandao_labels.py

    orig = TianDaoFacade.observe_monthly
    out = tmp_path / "labels.json"
    rc = TOOL.main(["--months", "1", "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["meta"]["generated_by"] == "game-dev/tools/tiandao_labels"
    assert data["meta"]["metric"] == list(TL.METRIC_NAMES)
    assert TianDaoFacade.observe_monthly.__func__ is orig.__func__, \
        "冻结观测必须还原（否则后续结算不再重新裁决）"

    from core.ai import tiandao_backtest as BT

    log_rows = [{"turn": row["turn"], "objective": row["objective"],
                 "verdict": next(iter((row.get("outcome_dist") or {"": 1.0}))),
                 "probability": 0.6, "defined": True, "provider": "tiandao_local"}
                for row in data["labels"]]
    if log_rows:
        rep = BT.summarize(log_rows, data["labels"])
        assert rep["labels_matched"] >= 1


def test_tool_bad_months_returns_two():
    import tiandao_labels as TOOL

    assert TOOL.main(["--months", "0"]) == 2


# ---------------------------------------------------------------- 分层
def test_pure_layer_does_not_import_orchestration():
    """纯逻辑层不得 import 结算/命令/应用层（守卫在别处也会拦，这里就近钉住）。"""
    import ast

    src = (_GAME / "core" / "ai" / "tiandao_labels.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned = ("core.settlement", "core.commands", "application")
    found = []
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
        for m in mods:
            if any(m == b or m.startswith(b + ".") for b in banned):
                found.append((node.lineno, m))
    assert not found, found
