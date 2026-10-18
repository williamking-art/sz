# -*- coding: utf-8 -*-
"""商品类目（词条）单点访问层 —— 「粮」不是一维，而是类目。

## 为什么存在

用户 2026-10-18 裁定：「不是应该新建词条来定义吗？米面麦不都是粮」。
旧口径只有 `GRAIN_DIMS = [米, 麦]` 两个并列维，**没有「粮」这个词条**，
于是 G-3 迁移只能写死「旧档 grain 全额记入米」——把「粮」与「米」混为一谈。

本模块是类目口径的**唯一访问点**（数据在 `content/data_constants.GOODS_CLASSES`）：
- 查类目、查成员、查某维属哪个类目；
- 类目合计（派生视图）＝ Σ 成员值，**缺失成员跳过**（缺失 ≠ 0）；
- 类目写入：落到 `default_member`（旧档无分项时的记账落点）。

## 纪律

1. 不得在别处硬编码「米+麦 = 粮」这类成员集合——一律走 `members()`；
2. `active=False` 的成员**尚未立商品维**（如「面」），既不进 `GOODS_DIMS` 也不参与交易，
   但类目合计时会**跳过**它们（不当作 0，也不报错）；
3. 一个商品维至多属一个类目（`assert_exclusive()` 守卫）；
4. 换算率（如 麦→面）**当前为空**：未核定前禁止隐式换算。
"""
from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "class_names", "class_of", "members", "class_total", "class_add",
    "assert_exclusive", "default_member",
]


def _classes() -> Dict[str, dict]:
    from content.data_constants import GOODS_CLASSES

    return GOODS_CLASSES or {}


def class_names() -> List[str]:
    """全部类目名（词条）。"""
    return list(_classes())


def class_of(dim: str) -> Optional[str]:
    """某商品维所属类目；不属于任何类目 ⇒ None（不是错误）。"""
    for name, spec in _classes().items():
        if dim in (spec.get("members") or []):
            return name
    return None


def members(cls: str, active_only: bool = False) -> List[str]:
    """类目成员；`active_only=True` 只返回已立商品维的成员。"""
    spec = _classes().get(cls) or {}
    ms = list(spec.get("members") or [])
    if not active_only:
        return ms
    act = spec.get("active") or {}
    return [m for m in ms if act.get(m, True)]


def default_member(cls: str) -> Optional[str]:
    """旧档无分项时的记账落点。"""
    spec = _classes().get(cls) or {}
    m = spec.get("default_member")
    return m if m in (spec.get("members") or []) else None


def class_total(goods, cls: str) -> Optional[int]:
    """类目合计（派生视图）：Σ 成员值。

    · 一个成员都没有 ⇒ **None**（缺失 ≠ 0）；
    · 非数值成员（州府桶 dict / 布尔）⇒ **跳过**（不得参与算术）。
    """
    if not isinstance(goods, dict):
        return None
    total = 0
    seen = False
    for m in members(cls):
        v = goods.get(m)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        total += int(v)
        seen = True
    return total if seen else None


def class_add(goods, cls: str, qty: int, member: Optional[str] = None) -> Optional[int]:
    """类目写入：默认落 `default_member`；返回写入后该成员的值。

    只做**成员维**的加减，成员选择必须显式或走默认——不做隐式换算。
    """
    if not isinstance(goods, dict):
        return None
    m = member or default_member(cls)
    if not m or m not in members(cls):
        return None
    cur = goods.get(m)
    cur = int(cur) if isinstance(cur, (int, float)) and not isinstance(cur, bool) else 0
    new = cur + int(qty)
    goods[m] = new
    return new


def assert_exclusive() -> List[str]:
    """不变式自检：一个商品维至多属一个类目。返回违规描述列表（空 = 干净）。"""
    issues: List[str] = []
    owner: Dict[str, str] = {}
    for name, spec in _classes().items():
        for m in spec.get("members") or []:
            if m in owner and owner[m] != name:
                issues.append(f"{m} 同时属于 {owner[m]} 与 {name}")
            owner[m] = name
    return issues
