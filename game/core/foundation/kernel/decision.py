# -*- coding: utf-8 -*-
"""决策服务契约 —— P0 零行为。

只定义 Request/Result/Service；不接任何现有结算，不写 state，不调网络。
后续阶段由 `TianDaoFacade` 实现 engine，并把结果写入 state.decision_log。
"""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

from core.foundation.kernel.objectives import ObjectiveError, ObjectiveRegistry

__all__ = ["DecisionError", "DecisionRequest", "DecisionResult", "DecisionService",
           "DecisionCache"]


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
    cached: bool = False

    @property
    def is_choice(self) -> bool:
        return isinstance(self.verdict, str)


class DecisionCache:
    """按客观事实缓存决策结果（避免重复本地计算/重复外部 Jev 调用）。

    key = objective + facts + options + constraints + actor；**不含 turn/seed**
    （同一局面跨回合复用；若事实含 turn 则会自然区分）。只缓存 `defined=True`
    的结果，避免把"缺依据"固化成永久结论。
    """

    def __init__(self, maxsize: int = 512) -> None:
        self.maxsize = max(1, int(maxsize))
        self._items: "OrderedDict[str, DecisionResult]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(request: "DecisionRequest") -> str:
        payload = {
            "objective": request.objective,
            "facts": request.facts,
            "options": list(request.options or ()),
            "constraints": request.constraints,
            "actor": request.actor,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, request: "DecisionRequest") -> Optional[DecisionResult]:
        key = self.key(request)
        hit = self._items.get(key)
        if hit is None:
            self.misses += 1
            return None
        self.hits += 1
        self._items.move_to_end(key)
        return replace(hit, cached=True)

    def put(self, request: "DecisionRequest", result: DecisionResult) -> None:
        if not result.defined:
            return
        key = self.key(request)
        self._items[key] = replace(result, cached=False)
        self._items.move_to_end(key)
        while len(self._items) > self.maxsize:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()
        self.hits = self.misses = 0

    def stats(self) -> Dict[str, int]:
        return {"size": len(self._items), "hits": self.hits, "misses": self.misses}


class DecisionService:
    """薄调度：校验 objective/facts/options，再把请求交给 engine。

    `engine.decide(request) -> DecisionResult`；未接 engine 时必须 fail-closed
    （`defined=False`），不得猜一个结果。
    """

    def __init__(self, engine: Any = None,
                 registry: Optional[ObjectiveRegistry] = None,
                 logger: Optional[Callable[[DecisionRequest, DecisionResult], None]] = None,
                 cache: Optional[DecisionCache] = None) -> None:
        self.engine = engine
        self.registry = registry or ObjectiveRegistry()
        self.logger = logger
        self.cache = cache

    def register(self, obj: Any, *, replace: bool = False) -> None:
        self.registry.register(obj, replace=replace)

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if not isinstance(request, DecisionRequest):
            raise DecisionError("request 必须是 DecisionRequest")
        obj = self.registry.get(request.objective)       # 未注册 ⇒ ObjectiveError
        self.registry.validate_request(request.objective, request.facts, request.options)
        if self.cache is not None:
            hit = self.cache.get(request)
            if hit is not None:
                if self.logger is not None:
                    self.logger(request, hit)
                return hit
        if self.engine is None:
            result = DecisionResult(objective=request.objective, verdict=None,
                                    probability=None, defined=False,
                                    reason="未接决策引擎（fail-closed）")
        else:
            result = self.engine.decide(request)
            if not isinstance(result, DecisionResult):
                raise DecisionError("engine 必须返回 DecisionResult")
        if self.cache is not None:
            self.cache.put(request, result)
        if self.logger is not None:
            self.logger(request, result)
        return result
