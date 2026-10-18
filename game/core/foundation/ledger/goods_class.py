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
    "assert_exclusive", "default_member", "is_active", "parent", "children",
    "members_deep", "class_total_deep", "assert_tree", "is_writable",
    "assert_no_class_in_keys",
]


def is_active(dim: str) -> bool:
    """该维**是否已立商品维**（在 GOODS_DIMS 内）。

    惰性判定：数据表定义位置早于 GOODS_DIMS，故不能把结果烤进 GOODS_CLASSES。
    """
    try:
        from content.data_constants import GOODS_DIMS
    except Exception:  # noqa: BLE001
        return True
    return dim in GOODS_DIMS


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
    # 数据里的 active 若为空 ⇒ 以 GOODS_DIMS 为准（惰性）
    return [m for m in ms if act.get(m, True) and is_active(m)]


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
    if not is_writable(cls):
        return None                      # 聚合类目（如 食品）不承载写入
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


def parent(cls: str) -> Optional[str]:
    """父类目；顶层 ⇒ None。"""
    spec = _classes().get(cls) or {}
    p = spec.get("parent")
    return p if p in _classes() else None


def children(cls: str) -> List[str]:
    """子类目（数据里声明的 existed 子类目）。"""
    spec = _classes().get(cls) or {}
    return [c for c in (spec.get("children") or []) if c in _classes()]


def members_deep(cls: str, active_only: bool = False) -> List[str]:
    """**递归**成员（自身成员 + 全部子类目成员），去重保序。

    ⚠️ 聚合纪律：一次求和的类目集合里**不得同时含父子**（否则同一维被加两次）。
    """
    out: List[str] = []
    seen = set()

    def _walk(name: str) -> None:
        for m in members(name, active_only=active_only):
            if m not in seen:
                seen.add(m)
                out.append(m)
        for c in children(name):
            _walk(c)

    _walk(cls)
    return out


def class_total_deep(goods, cls: str) -> Optional[int]:
    """**递归**类目合计（派生视图）：Σ 自身 + 全部子类目成员；无成员 ⇒ None。"""
    if not isinstance(goods, dict):
        return None
    total = 0
    seen = False
    for m in members_deep(cls):
        v = goods.get(m)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        total += int(v)
        seen = True
    return total if seen else None


def assert_tree() -> List[str]:
    """层级自检：无环、parent 与 children 互指一致、成员不跨类目重复。"""
    issues: List[str] = []
    cls_all = _classes()
    for name in cls_all:
        seen = set()
        cur = name
        while cur is not None:
            if cur in seen:
                issues.append(f"类目成环：{name} → … → {cur}")
                break
            seen.add(cur)
            cur = parent(cur)
    for name in cls_all:
        for c in children(name):
            if parent(c) != name:
                issues.append(f"父子不一致：{name} 声称子类目 {c}，但 {c}.parent={parent(c)}")
    for name in cls_all:
        for c in children(name):
            if c in (cls_all[name].get("members") or []):
                issues.append(f"{c} 既被列为 {name} 的成员又是子类目（语义冲突）")
    issues.extend(assert_exclusive())
    return issues


def is_writable(cls: str) -> bool:
    """该类目能否写入库存：父/聚合类目（writable=False）只能读合计，不能写。

    纪律：库存只落**维**；父类目没有 default_member，写入必然无处落账 ⇒ 拒绝。
    """
    spec = _classes().get(cls) or {}
    if spec.get("writable") is False:
        return False
    return bool(spec.get("default_member") or spec.get("members"))


def assert_no_class_in_keys(keys) -> List[str]:
    """库存键里出现**类目名** ⇒ 违反「类目不持库存」。返回违规键列表。"""
    names = set(_classes())
    return [k for k in (keys or []) if str(k) in names]

