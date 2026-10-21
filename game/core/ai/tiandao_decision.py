# -*- coding: utf-8 -*-
"""天道/Jev 与 DecisionService 的适配层（P1 第一片，只读）。

- 把现有 10 个观察 objective 显式登记（mode/options/criteria）；
- 调用 `TianDaoEngine` 并映射到 `DecisionResult`；
- `decide_and_log(state, ...)` 只追加 `state.decision_log`，**不改结算**。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from core.ai.tiandao_engine import TianDaoEngine
from core.foundation.kernel.decision import (
    DecisionCache, DecisionRequest, DecisionResult, DecisionService,
)
from core.foundation.kernel.objectives import ObjectiveDef, ObjectiveRegistry

__all__ = ["TianDaoDecisionEngine", "build_registry", "build_service",
           "decide_and_log", "SPECS", "MAX_LOG"]

MAX_LOG = 200

#: objective -> (mode, options, criteria, condition)
SPECS: Dict[str, Tuple[str, Sequence[str], Mapping[str, float], str]] = {
    "tax_stance": ("choose", ("strict", "moderate", "lenient"),
                   {"strict": 0.35, "moderate": 0.50, "lenient": 0.15}, "征管宽严倾向"),
    "waive_arrears": ("gate", (), {}, "是否准予蠲免陈年逋欠"),
    "merchant_trade": ("choose", ("ship", "hoard", "local_sell"),
                       {"ship": 0.40, "hoard": 0.35, "local_sell": 0.25}, "商贾经营抉择"),
    "changping_open": ("gate", (), {}, "是否平粜开仓压制粮价"),
    "labor_policy": ("choose", ("corvee", "hired"),
                     {"corvee": 0.50, "hired": 0.50}, "劳役制度选择"),
    "canal_reroute": ("choose", ("wait_dredge", "overland_cart", "borrow_grain"),
                      {"wait_dredge": 0.45, "overland_cart": 0.35,
                       "borrow_grain": 0.20}, "漕运改道决断"),
    "granary_corruption": ("gate", (), {}, "是否存在雀鼠耗贪墨虚报"),
    "farmer_path": ("choose", ("mortgage_land", "flee_refugee"),
                    {"mortgage_land": 0.70, "flee_refugee": 0.30}, "破产自耕农抉择"),
    "gentry_path": ("choose", ("charity_relief", "usury_annex"),
                    {"charity_relief": 0.40, "usury_annex": 0.60}, "士绅灾荒抉择"),
    "reform_compliance": ("gate", (), {}, "是否切实贯彻朝廷变法新政"),
    "recruit_refugees": ("gate", (), {}, "是否招募流民充为地方厢军"),
}


@dataclass
class TianDaoDecisionEngine:
    """实现 `DecisionService.engine.decide(request)`。"""

    def decide(self, request: DecisionRequest) -> DecisionResult:
        spec = SPECS.get(request.objective)
        if spec is None:
            return DecisionResult(objective=request.objective, defined=False,
                                  reason="未登记的天道 objective")
        mode, options, criteria, condition = spec
        ctx = request.facts.get("state_context")
        if ctx is None:
            ctx = dict(request.facts)
        if mode == "gate":
            raw = TianDaoEngine.gate(ctx, condition, objective=request.objective)
            return DecisionResult(
                objective=request.objective, verdict=raw.get("verdict"),
                probability=raw.get("probability"),
                defined=bool(raw.get("defined")), basis=raw,
                provider=str(raw.get("provider") or "tian_dao"),
                reason="" if raw.get("defined") else "无依据（fail-closed）", raw=raw)
        if mode == "choose":
            raw = TianDaoEngine.choose(ctx, condition, dict(criteria),
                                       objective=request.objective)
            probs = raw.get("probabilities") or {}
            return DecisionResult(
                objective=request.objective, verdict=raw.get("verdict"),
                probability=(max(probs.values()) if probs else None),
                defined=bool(raw.get("defined")), basis=raw,
                provider=str(raw.get("provider") or "tian_dao"),
                reason="" if raw.get("defined") else "无依据（fail-closed）", raw=raw)
        return DecisionResult(objective=request.objective, defined=False,
                              reason="未适配 mode：%s" % mode)


def build_registry() -> ObjectiveRegistry:
    reg = ObjectiveRegistry()
    for oid, (mode, options, criteria, _cond) in SPECS.items():
        reg.register(ObjectiveDef(oid, mode, options=tuple(options), facts=(),
                                  criteria=dict(criteria), domain="tiandao"))
    return reg


def build_service(logger=None, cache: Optional[DecisionCache] = None) -> DecisionService:
    return DecisionService(engine=TianDaoDecisionEngine(), registry=build_registry(),
                           logger=logger, cache=cache)


def decide_and_log(state: Any, objective: str, state_context: Mapping[str, Any],
                   turn: Optional[int] = None) -> Optional[DecisionResult]:
    """只读调用并追加 `state.decision_log`；任何异常 fail-closed，不影响结算。"""
    try:
        cache = getattr(state, "_decision_cache", None)
        if not isinstance(cache, DecisionCache):
            cache = DecisionCache()
            try:
                state._decision_cache = cache
            except Exception:  # noqa: BLE001 —— 不支持属性时退化为无缓存
                cache = None
        svc = build_service(cache=cache)
        req = DecisionRequest(
            objective=objective, facts={"state_context": dict(state_context or {})},
            options=tuple(SPECS[objective][1]), seed=int(turn if turn is not None
                                                         else getattr(state, "turn", 0) or 0),
            turn=int(turn if turn is not None else getattr(state, "turn", 0) or 0))
        res = svc.decide(req)
    except Exception:  # noqa: BLE001 —— 观测失败不得影响结算
        import logging
        logging.getLogger("tiandao").warning("决策日志写入失败：%s", objective, exc_info=True)
        return None
    log = getattr(state, "decision_log", None)
    if isinstance(log, list):
        log.append({
            "turn": req.turn, "objective": objective, "verdict": res.verdict,
            "probability": res.probability, "defined": res.defined,
            "provider": res.provider, "seed": req.seed, "cached": bool(res.cached),
        })
        if len(log) > MAX_LOG:
            del log[:-MAX_LOG]
    return res
