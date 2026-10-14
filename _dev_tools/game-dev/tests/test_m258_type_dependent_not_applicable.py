# -*- coding: utf-8 -*-
"""M258 P2 `not_applicable` 的**类型相关假设锁**。

背景（M236/M238/M256 审计暴露）：`NOT_APPLICABLE_BUILDING` 含 `jobs_capacity` / `jobs_filled`，
但它们在**语义上是"类型相关"的**——`reason` 原文写的是「**该建筑非岗位建筑**（`JOBS_PER_LEVEL` 未登记）」。
⇒ 该归类**只在「开局建筑集全部是非岗位建筑」时成立**。

本用例把该前提**钉成断言**：
* 若全部建筑的 `jobs_capacity` 都 `undefined` ⇒ 归类成立（当前实况）；
* 🔴 若**出现任何**建筑的 `jobs_capacity` **有值**（即出现岗位类建筑）⇒ **本用例失败**，
  并提示后续维护者：**必须把 `jobs_capacity` / `jobs_filled` 从 `NOT_APPLICABLE_BUILDING`
  移出（改判为"适用"）**，或把该常量改为**按建筑类型**判定 —— 否则就绪度双口径会**系统性低估**。
"""

import random

from core import commands
from core.domains.economy import entity_projection as ep

#: 类型相关、需随建筑类型判定的字段（见 `NOT_APPLICABLE_BUILDING` 的注释）
TYPE_DEPENDENT = ("jobs_capacity", "jobs_filled")


def _all_buildings(s):
    for route, p in s.prefectures.items():
        for seat, srow in (p.get("seats") or {}).items():
            for name in ((srow or {}).get("buildings") or {}):
                yield route, seat, name


def test_type_dependent_fields_are_all_undefined_in_opening_set():
    """假设锁：开局建筑集里 `jobs_capacity`/`jobs_filled` **必须全部 undefined**。

    失败 ⇒ 出现了岗位类建筑 ⇒ **`NOT_APPLICABLE_BUILDING` 需改（见模块 docstring）**。
    """
    random.seed(20261013)
    s = commands.new_game()
    defined_seen = []
    n = 0
    for route, seat, name in _all_buildings(s):
        n += 1
        f = ep.project_building(s, route, seat, name)["fields"]
        for k in TYPE_DEPENDENT:
            if (f.get(k) or {}).get("defined"):
                defined_seen.append((route, seat, name, k))
    assert n > 0, "样例集为空 ⇒ 用例前置不成立"
    assert not defined_seen, (
        "出现岗位类建筑（{} 处，例：{}）⇒ 必须把 jobs_capacity/jobs_filled 从 "
        "NOT_APPLICABLE_BUILDING 移出或改为按建筑类型判定，否则就绪度双口径会系统性低估"
        .format(len(defined_seen), defined_seen[0])
    )


def test_type_dependent_entries_are_marked_as_type_related():
    """`NOT_APPLICABLE_BUILDING` 里这两个字段的**理由文本**必须标注「类型相关」。"""
    for k in TYPE_DEPENDENT:
        reason = ep.NOT_APPLICABLE_BUILDING.get(k) or ""
        assert "类型相关" in reason, (k, reason)
