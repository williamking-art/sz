# -*- coding: utf-8 -*-
"""天道/Jev 与 DecisionService 的适配层（P1 第一片，只读）。

本批（2026-10-21 L1）在原有「只读 + 有界日志」之上补三件事，**都不改结算数值**：

1. **objective 覆盖补齐**：`decree_compliance`（引擎有分支、生产在用 `decree_effect.py:202`，
   却一直没进注册表 ⇒ 进不了 registry/日志）与 `appraisal`（考课，score 模式）登记入表。
2. **`score` 模式**：`TianDaoDecisionEngine.decide` 原先只有 gate/choose 两个分支，
   考课一律返回「未适配 mode：score」⇒ 考课裁决永远进不了决策日志。现补上。
3. **`ObjectiveDef.thresholds` 接线**：该字段自 P0 起就是**死字段**（`build_registry` 只填
   `criteria`，`decide` 从不下传），阈值只能靠 `TianDaoEngine.gate` 的默认 0.50。
   现由 `THRESHOLDS` 单一登记并下传——**默认值仍是 0.50，不改变既有判定**。

另：`decide_and_log` 的记录新增 `facts_digest`（`core.ai.tiandao_facts` 的稳定摘要），
让「同一局面 → 同一裁决」可被离线回测比对；仍是只追加、不参与结算。

契约纪律（不变）
----------------
* 只读：不写账本、不改结算、不联网；
* 有界：`MAX_LOG` 环形截尾；
* fail-closed：登记表里没有的 objective 显式记 reason 并返回 None，**不猜一个结果**。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from core.ai.tiandao_engine import TianDaoEngine
from core.foundation.kernel.decision import (
    DecisionCache, DecisionRequest, DecisionResult, DecisionService,
)
from core.foundation.kernel.objectives import ObjectiveDef, ObjectiveRegistry

log = logging.getLogger(__name__)

__all__ = ["TianDaoDecisionEngine", "build_registry", "build_service",
           "decide_and_log", "SPECS", "THRESHOLDS", "SCORE_LEVELS", "MAX_LOG",
           "NON_OBSERVED_OBJECTIVES"]

MAX_LOG = 200

#: objective -> (mode, options, criteria, condition)
#: ⚠️ 元组形状是既有契约（`test_p1_tiandao_decision_adapter.py` 按 `[1]` 取 options），
#: 新增 score 模式的 facts/levels 分别走 `SCORE_LEVELS` 与 `THRESHOLDS`，不要改元组长度。
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
    # —— 2026-10-21 L1 补登 ——
    #: 引擎有分支、`core/decree_effect.py:202` 在生产消费，但此前未登记 ⇒ 进不了日志
    "decree_compliance": ("choose",
                          ("vigorous", "compliant", "passive", "defiant"),
                          {"vigorous": 0.25, "compliant": 0.50,
                           "passive": 0.20, "defiant": 0.05},
                          "知州诏令遵从度"),
    #: 考课：score 模式（levels 见 SCORE_LEVELS；options 必须为空，ObjectiveDef 会校验）
    "appraisal": ("score", (), {}, "知州三年磨勘四善三最考课"),
}

#: score 模式的档位表（**必须按「差 → 好」排列**，见 `TianDaoEngine.score` 契约）
SCORE_LEVELS: Dict[str, Tuple[str, ...]] = {
    "appraisal": ("下考", "中考", "上考"),
}

#: objective -> 闸门阈值。**单一登记点**；未登记者用引擎默认 0.50。
#: 本批全部保持 0.50（=引擎默认），登记的目的是让"以后要按 objective 定阈值"有唯一入口，
#: 而不是散落在调用点。改动此表等于改判定，必须同步定向回归。
#: **不进月度观测/决策日志**的 objective（2026-10-22 审查 E5：差集必须显式声明）。
#: 为什么需要这张表：`SPECS` 是所有权重的登记处（13 项），而 `observe_monthly` 只观测
#: 11 项——差额若不明写，就会被读成「漏登」。这两项都需要**逐对象上下文**，
#: 不是月度状态级裁决，故由各自管道按需评估（不写 `decision_log`，回测对它们 N/A）。
NON_OBSERVED_OBJECTIVES: Dict[str, str] = {
    "appraisal": "score 模式，需逐官上下文（三年磨勘四善三最），由考课管道按需评估",
    "decree_compliance": "choose 模式，需逐地政令上下文（circuit_decree_compliance），"
                          "由诏令结算按需评估",
}

THRESHOLDS: Dict[str, float] = {
    "waive_arrears": 0.50,
    "changping_open": 0.50,
    "granary_corruption": 0.50,
    "reform_compliance": 0.50,
    "recruit_refugees": 0.50,
}


@dataclass
class TianDaoDecisionEngine:
    """实现 `DecisionService.engine.decide(request)`。"""

    def decide(self, request: DecisionRequest) -> DecisionResult:
        spec = SPECS.get(request.objective)
        if spec is None:
            # 显式 fail-closed：登记表里没有 ⇒ 不猜（调用方据此判"未判"）
            return DecisionResult(objective=request.objective, defined=False,
                                  reason="未登记的天道 objective：%s" % request.objective)
        mode, options, criteria, condition = spec
        ctx = request.facts.get("state_context")
        if ctx is None:
            ctx = dict(request.facts)

        if mode == "gate":
            kwargs: Dict[str, Any] = {"objective": request.objective}
            thr = THRESHOLDS.get(request.objective)
            if thr is not None:
                kwargs["threshold"] = float(thr)
            raw = TianDaoEngine.gate(ctx, condition, **kwargs)
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

        if mode == "score":
            levels = SCORE_LEVELS.get(request.objective) or tuple(options)
            raw = TianDaoEngine.score(ctx, condition, levels)
            return DecisionResult(
                objective=request.objective,
                # 考课把「档位词」放 verdict、「综合分」放 probability（0~1，非概率语义）
                verdict=raw.get("level"),
                probability=raw.get("score"),
                defined=bool(raw.get("defined")), basis=raw,
                provider=str(raw.get("provider") or "tian_dao"),
                reason="" if raw.get("defined") else "无依据（fail-closed）", raw=raw)

        return DecisionResult(objective=request.objective, defined=False,
                              reason="未适配 mode：%s" % mode)


def build_registry() -> ObjectiveRegistry:
    reg = ObjectiveRegistry()
    for oid, (mode, options, criteria, _cond) in SPECS.items():
        thr = THRESHOLDS.get(oid)
        reg.register(ObjectiveDef(
            oid, mode,
            # score 模式不允许带 options（ObjectiveDef 会抛 ObjectiveError）
            options=(tuple(options) if mode != "score" else ()),
            facts=(), criteria=dict(criteria), domain="tiandao",
            thresholds=({} if thr is None else {"gate": float(thr)}),
        ))
    return reg


def build_service(logger=None, cache: Optional[DecisionCache] = None) -> DecisionService:
    return DecisionService(engine=TianDaoDecisionEngine(), registry=build_registry(),
                           logger=logger, cache=cache)


def _facts_digest(state_context: Any) -> Optional[str]:
    """事实摘要（失败返回 None，**不得**用空串冒充）。"""
    try:
        from core.ai.tiandao_facts import facts_digest
        return facts_digest(state_context)
    except Exception:  # noqa: BLE001 —— 摘要失败不得影响裁决/日志
        log.warning("facts_digest 计算失败（不影响裁决）", exc_info=True)
        return None


def decide_and_log(state: Any, objective: str, state_context: Mapping[str, Any],
                   turn: Optional[int] = None) -> Optional[DecisionResult]:
    """只读调用并追加 `state.decision_log`；任何异常 fail-closed，不影响结算。"""
    if objective not in SPECS:
        log.warning("decide_and_log: 未登记的 objective=%s（已跳过，不猜结果）", objective)
        return None
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
            options=tuple(SPECS[objective][1]),
            seed=int(turn if turn is not None
                     else getattr(state, "turn", 0) or 0),
            turn=int(turn if turn is not None else getattr(state, "turn", 0) or 0))
        res = svc.decide(req)
    except Exception:  # noqa: BLE001 —— 观测失败不得影响结算
        log.warning("决策日志写入失败：%s", objective, exc_info=True)
        return None
    log_rows = getattr(state, "decision_log", None)
    if isinstance(log_rows, list):
        log_rows.append({
            "turn": req.turn, "objective": objective, "verdict": res.verdict,
            "probability": res.probability, "defined": res.defined,
            "provider": res.provider, "seed": req.seed, "cached": bool(res.cached),
            # 同一局面可复算的稳定摘要（离线回测/回放比对用）
            "facts_digest": _facts_digest(state_context),
        })
        if len(log_rows) > MAX_LOG:
            del log_rows[:-MAX_LOG]
    return res
