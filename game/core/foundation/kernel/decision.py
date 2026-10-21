# -*- coding: utf-8 -*-
"""决策服务契约 —— P0 零行为。

只定义 Request/Result/Service；不接任何现有结算，不写 state，不调网络。
后续阶段由 `TianDaoFacade` 实现 engine，并把结果写入 state.decision_log。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

from core.foundation.kernel.objectives import ObjectiveError, ObjectiveRegistry

__all__ = ["DecisionError", "DecisionRequest", "DecisionResult", "DecisionService"]


class DecisionError(ValueError):
    """决策请求/引擎非法。"""


@dataclass(frozen=True)
class DecisionRequest:
    objective: str
    facts: Mapping[str, Any] = field(default_factory=dict)
    options: Sequence[str] = field(default_factory=tuple)
    constraints: Mapping[str, Any] = field(default_factory=dict)
    seed: int = 0
    turn: int = 0
    actor: Optional[str] = None
    scope: Optional[str] = None


@dataclass(frozen=True)
class DecisionResult:
    objective: str
    verdict: Any = None
    probability: Optional[float] = None
    defined: bool = False
    basis: Mapping[str, Any] = field(default_factory=dict)
    provider: str = "tian_dao"
    reason: str = ""
    raw: Any = None

    @property
    def is_choice(self) -> bool:
        return isinstance(self.verdict, str)


class DecisionService:
    """薄调度：校验 objective/facts/options，再把请求交给 engine。

    `engine.decide(request) -> DecisionResult`；未接 engine 时必须 fail-closed
    （`defined=False`），不得猜一个结果。
    """

    def __init__(self, engine: Any = None,
                 registry: Optional[ObjectiveRegistry] = None,
                 logger: Optional[Callable[[DecisionRequest, DecisionResult], None]] = None) -> None:
        self.engine = engine
        self.registry = registry or ObjectiveRegistry()
        self.logger = logger

    def register(self, obj: Any, *, replace: bool = False) -> None:
        self.registry.register(obj, replace=replace)

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if not isinstance(request, DecisionRequest):
            raise DecisionError("request 必须是 DecisionRequest")
        obj = self.registry.get(request.objective)       # 未注册 ⇒ ObjectiveError
        self.registry.validate_request(request.objective, request.facts, request.options)
        if self.engine is None:
            result = DecisionResult(objective=request.objective, verdict=None,
                                    probability=None, defined=False,
                                    reason="未接决策引擎（fail-closed）")
        else:
            result = self.engine.decide(request)
            if not isinstance(result, DecisionResult):
                raise DecisionError("engine 必须返回 DecisionResult")
        if self.logger is not None:
            self.logger(request, result)
        return result
