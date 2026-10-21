# -*- coding: utf-8 -*-
"""决策目标注册表（objective registry）—— P0 零行为。

目标必须是显式的：id/mode/options/facts/阈值/权重；不再靠中文子串或键名隐式分派。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

__all__ = ["ObjectiveError", "ObjectiveDef", "ObjectiveRegistry", "MODES"]

MODES = ("gate", "choose", "score", "dice")


class ObjectiveError(ValueError):
    """目标定义非法/未注册。"""


@dataclass(frozen=True)
class ObjectiveDef:
    objective_id: str
    mode: str
    options: Sequence[str] = field(default_factory=tuple)
    facts: Sequence[str] = field(default_factory=tuple)
    thresholds: Mapping[str, float] = field(default_factory=dict)
    criteria: Mapping[str, float] = field(default_factory=dict)
    domain: str = "generic"
    version: int = 1

    def __post_init__(self) -> None:
        oid = str(self.objective_id or "").strip()
        if not oid:
            raise ObjectiveError("objective_id 不能为空")
        if self.mode not in MODES:
            raise ObjectiveError("未知 mode：%r（应为 %s）" % (self.mode, "/".join(MODES)))
        if self.mode in ("gate", "score", "dice"):
            if self.options:
                raise ObjectiveError("%s 模式不应带 options" % self.mode)
        else:
            if not self.options:
                raise ObjectiveError("choose 模式必须至少一个 option")
            if len(set(self.options)) != len(self.options):
                raise ObjectiveError("options 不能重复")
        if any(not isinstance(x, str) or not x for x in self.facts):
            raise ObjectiveError("facts 必须是非空字符串列表")
        for key, value in self.criteria.items():
            if not isinstance(key, str) or not key:
                raise ObjectiveError("criteria 键必须是非空字符串")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ObjectiveError("criteria 权重必须是数值：%s" % key)


class ObjectiveRegistry:
    """进程内目标表；pack 加载后可批量注册。"""

    def __init__(self) -> None:
        self._items: Dict[str, ObjectiveDef] = {}

    def register(self, obj: ObjectiveDef, *, replace: bool = False) -> None:
        if not isinstance(obj, ObjectiveDef):
            raise ObjectiveError("只能注册 ObjectiveDef")
        if obj.objective_id in self._items and not replace:
            raise ObjectiveError("目标已注册：%s" % obj.objective_id)
        self._items[obj.objective_id] = obj

    def get(self, objective_id: str) -> ObjectiveDef:
        try:
            return self._items[str(objective_id)]
        except KeyError as exc:
            raise ObjectiveError("未注册目标：%r" % (objective_id,)) from exc

    def has(self, objective_id: str) -> bool:
        return str(objective_id) in self._items

    def ids(self) -> List[str]:
        return sorted(self._items)

    def validate_request(self, objective_id: str, facts: Mapping[str, Any],
                         options: Optional[Iterable[str]] = None) -> None:
        obj = self.get(objective_id)
        missing = [f for f in obj.facts if f not in (facts or {})]
        if missing:
            raise ObjectiveError("目标 %s 缺事实：%s" % (objective_id, ",".join(missing)))
        if obj.mode == "choose" and options is not None:
            bad = [o for o in options if o not in set(obj.options)]
            if bad:
                raise ObjectiveError("目标 %s 含未定义选项：%s" % (objective_id, ",".join(bad)))
