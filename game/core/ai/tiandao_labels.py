# -*- coding: utf-8 -*-
"""回测标签的**纯逻辑层**（反事实回放的判定与度量，2026-10-22）。

分层说明（为什么这里不 import 结算）
------------------------------------
本模块只做"给定状态与观测副本，怎么判标签"的纯逻辑；
**驱动结算/读档/建新局由调用方注入**（见 `_dev_tools/game-dev/tools/tiandao_labels.py`，
那是离线工具）。这样 `core/ai` 不会反向依赖 `core.settlement` / `core.commands` /
`application`——`test_architecture_import_guard` 的 R2/R3 规则禁止越层，且明确要求
"现在就该改代码，不要往 _FROZEN_UPLINK 加行"。

标签口径：**帕累托支配，不设权重**
----------------------------------
对某月某 objective：把每个候选分支强制跑一个月，度量向量
`(国库, Σ地方府库, 太仓, −Σ民怨, −Σ流民)`（越大越好，缺一项则弃该试验）；
**只有唯一**分支"全面不劣且至少一项更优"才打标签，并列/互有胜负 ⇒ 跳过。
⇒ 标签含义是「事后看，本月哪种做法让国计民生更好」，是**代理真值**（proxy），
能度量校准与排序，不证明因果，也不含长期后果。
"""
from __future__ import annotations

import copy
import logging
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

__all__ = [
    "LabelError", "METRIC_NAMES", "GATE_BRANCHES",
    "metric_vector", "pareto_best", "forced_record", "candidates_of",
    "extract_month_labels", "extract_labels", "frozen_observe",
]

#: 度量向量各分量（**越大越好**；全为既有读数）
METRIC_NAMES: Tuple[str, ...] = (
    "treasury", "local_treasury", "granary", "neg_unrest", "neg_refugees",
)

#: gate 的候选分支（True = 放行）
GATE_BRANCHES: Tuple[bool, ...] = (True, False)

#: `run_month(state, record, seed)` —— 由调用方注入（通常是跑一个月结算）
RunMonth = Callable[[Any, Mapping[str, Any], int], Any]


class LabelError(RuntimeError):
    """标签生成的结构性错误（参数/环境），由 CLI 转成退出码 2。"""


def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


# ---------------------------------------------------------------------------
# 度量与判定
# ---------------------------------------------------------------------------
def metric_vector(state: Any) -> Optional[Tuple[float, ...]]:
    """月末五维度量；任一必需读数缺失 ⇒ `None`（**不拿缺失当 0** 参与比较）。"""
    treasury = _num(getattr(state, "treasury", None))
    granary = _num(getattr(state, "granary", None))
    if treasury is None or granary is None:
        return None
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, Mapping) or not prefs:
        return None
    local, unrest, refugees = 0.0, 0.0, 0.0
    for p in prefs.values():
        if not isinstance(p, Mapping):
            continue
        lt, u, r = (_num(p.get("local_treasury")), _num(p.get("unrest")),
                    _num(p.get("refugees")))
        if lt is None or u is None or r is None:
            return None
        local += lt
        unrest += u
        refugees += r
    return (treasury, local, granary, -unrest, -refugees)


def pareto_best(vectors: Sequence[Optional[Tuple[float, ...]]]) -> Optional[int]:
    """唯一帕累托支配者的下标；无支配者/多方并列 ⇒ `None`。

    "全面不劣且至少一项更优"——无需给钱/粮/民怨/流民拍权重，
    也不会把"一维暴涨换另一维崩塌"判成最优。
    """
    idx = [i for i, v in enumerate(vectors) if v is not None]
    if len(idx) < 2:
        return None
    winners: List[int] = []
    for i in idx:
        vi = vectors[i]
        assert vi is not None
        better_somewhere = False
        ok = True
        for j in idx:
            if j == i:
                continue
            vj = vectors[j]
            assert vj is not None
            if any(a < b for a, b in zip(vi, vj)):
                ok = False
                break
            if any(a > b for a, b in zip(vi, vj)):
                better_somewhere = True
        if ok and better_somewhere:
            winners.append(i)
    return winners[0] if len(winners) == 1 else None


# ---------------------------------------------------------------------------
# 观测副本：强制与冻结
# ---------------------------------------------------------------------------
def _empty_record(turn: int = 0) -> Dict[str, Any]:
    return {"turn": turn, "read_only": True, "decisions": {},
            "distributions": {}, "strengths": {}}


def method_of(objective: str) -> Optional[str]:
    """objective id → 门面方法名（观测副本 `decisions` 按方法名存）。"""
    from core.ai.tiandao_facade import TianDaoFacade

    for method, obj in (getattr(TianDaoFacade, "OBSERVE_OBJECTIVES", {}) or {}).items():
        if obj == objective:
            return method
    return None


# 兼容旧名（测试与外部脚本用过 `_method_of`）
_method_of = method_of


def forced_record(record: Mapping[str, Any], objective: str,
                  option: Any) -> Dict[str, Any]:
    """在既有副本上**只**把该 objective 改成"强制 option"（其它 objective 原样）。"""
    rec: Dict[str, Any] = {
        "turn": record.get("turn", 0),
        "read_only": True,
        "decisions": dict(record.get("decisions") or {}),
        "distributions": {k: dict(v) if isinstance(v, Mapping) else v
                          for k, v in (record.get("distributions") or {}).items()},
        "strengths": dict(record.get("strengths") or {}),
    }
    method = method_of(objective)
    if isinstance(option, bool):
        if method:
            rec["decisions"][method] = option
        rec["strengths"][objective] = 1.0 if option else 0.0
    else:
        if method:
            rec["decisions"][method] = str(option)
        rec["distributions"][objective] = {str(option): 1.0}
    return rec


def candidates_of(objective: str) -> Optional[List[Any]]:
    """该 objective 的候选分支；不在观测清单（如 `appraisal`）⇒ None。"""
    from core.ai.tiandao_decision import SPECS

    spec = SPECS.get(objective)
    if not spec:
        return None
    mode, options = spec[0], spec[1]
    if method_of(objective) is None:
        return None
    if mode == "gate":
        return list(GATE_BRANCHES)
    if mode == "choose":
        return list(options)
    return None                     # score 模式：无分支可反事实对比


def observed_objectives() -> List[str]:
    """当前纳入观测的 objective（sorted，供默认遍历）。"""
    from core.ai.tiandao_facade import TianDaoFacade

    return sorted((getattr(TianDaoFacade, "OBSERVE_OBJECTIVES", {}) or {}).values())


@contextmanager
def frozen_observe():
    """冻结观测：`observe_monthly` 不再重观测（保留调用方注入的副本）。

    为什么必须冻结：月结 Step 0 会重新观察并**覆盖** `state._tiandao_observe`，
    不冻结的话"强制某分支"会在第一步就被真实观测冲掉（反事实实验失效）。
    """
    from core.ai.tiandao_facade import TianDaoFacade

    orig = TianDaoFacade.observe_monthly.__func__

    def _noop(cls, state):
        rec = getattr(state, "_tiandao_observe", None)
        return rec if isinstance(rec, dict) else _empty_record()

    TianDaoFacade.observe_monthly = classmethod(_noop)
    try:
        yield
    finally:
        TianDaoFacade.observe_monthly = classmethod(orig)


# ---------------------------------------------------------------------------
# 单月 / 多月（结算驱动由 `run_month` 注入）
# ---------------------------------------------------------------------------
def extract_month_labels(state_before: Any, record: Mapping[str, Any],
                         *, turn: int, seed: int, run_month: RunMonth,
                         objectives: Optional[Iterable[str]] = None,
                         ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """对一个月做反事实回放，返回 `(labels, skipped)`。"""
    labels: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    targets = list(objectives) if objectives is not None else observed_objectives()
    for obj in targets:
        cands = candidates_of(obj)
        if not cands:
            skipped.append({"objective": obj, "turn": turn, "reason": "no_candidates"})
            continue
        vectors: List[Optional[Tuple[float, ...]]] = []
        for opt in cands:
            trial = copy.deepcopy(state_before)
            try:
                run_month(trial, forced_record(record, obj, opt), seed)
            except Exception as exc:  # noqa: BLE001 —— 单次试验失败不废整批标签
                log.warning("反事实试验失败 obj=%s opt=%s turn=%s：%r", obj, opt, turn, exc)
                vectors.append(None)
                continue
            vectors.append(metric_vector(trial))
        best = pareto_best(vectors)
        if best is None:
            skipped.append({"objective": obj, "turn": turn,
                            "reason": "no_unique_pareto_best"})
            continue
        opt = cands[best]
        if isinstance(opt, bool):
            labels.append({"objective": obj, "turn": turn, "outcome": bool(opt)})
        else:
            labels.append({"objective": obj, "turn": turn,
                           "outcome_dist": {str(opt): 1.0}})
    return labels, skipped


def extract_labels(months: int, *, make_state: Callable[[], Any],
                   observe_monthly: Callable[[Any], Mapping[str, Any]],
                   run_month: RunMonth, seed: int,
                   objectives: Optional[Iterable[str]] = None,
                   source: str = "new_game",
                   ) -> Dict[str, Any]:
    """跑 `months` 个月产标签；返回与 `tiandao_backtest.load_labels` 兼容的结构。

    `make_state` / `observe_monthly` / `run_month` 均为注入：`make_state()` 造/读初始局，
    `observe_monthly(state)` 产该月自然观测副本，`run_month(state, record, seed)` 推进一个月。
    """
    if not isinstance(months, int) or months <= 0:
        raise LabelError("months 必须为正整数")
    state = make_state()
    all_labels: List[Dict[str, Any]] = []
    all_skipped: List[Dict[str, Any]] = []
    for i in range(months):
        record = observe_monthly(state)
        # 🔴 turn 取**观测副本里的 turn**（与 decision_log 同源）。用 `state.turn or (i+1)`
        # 会在首月把 0 变成 1（Python falsy 坑）⇒ 标签与日志错位并产生重复标签。
        turn = int(record.get("turn") or getattr(state, "turn", 0) or 0)
        labels, skipped = extract_month_labels(
            copy.deepcopy(state), record, turn=turn, seed=seed + i,
            run_month=run_month, objectives=objectives)
        all_labels.extend(labels)
        all_skipped.extend(skipped)
        run_month(state, record, seed + i)      # 真实推进（用自然副本）
    return {
        "labels": all_labels,
        "meta": {
            "generated_by": "game-dev/tools/tiandao_labels",
            "months": months,
            "seed": seed,
            "source": source,
            "metric": list(METRIC_NAMES),
            "metric_note": "越大越好；唯一帕累托支配者才打标签，并列/互有胜负跳过",
            "label_count": len(all_labels),
            "skipped_count": len(all_skipped),
            "skipped": all_skipped[:200],
        },
    }
