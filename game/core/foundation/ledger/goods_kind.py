# -*- coding: utf-8 -*-
"""商品属性（kind）与加工链的单点访问层。

## 口径（用户 2026-10-18 裁定）

- 「粮」是**属性**，不是固定成员名单：`is_grain(dim)` 只看 `COMMODITY_KINDS[dim] == "粮"`；
- 面是**中间产物**：既属粮（能进粮仓），又在 `PROCESS_CHAINS` 里（能继续加工）——两者不冲突；
- 新增一种粮 = 数据表加一行，**不动代码**；未登记维 ⇒ 返回 None（**缺失 ≠ 默认是粮**）。

## 纪律

1. 禁止在别处硬编码 `"米"/"麦"` 判断是不是粮——一律走 `is_grain`；
2. 加工链 `rate=None` 表示**未核定**：引擎不得做隐式换算（要产出必须显式给率）；
3. `GOODS_DIMS` 里每个维都必须有 kind（`assert_kinds_cover_dims()` 由门钉住）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "kind_of", "is_grain", "grain_dims", "chain_of", "chain_inputs",
    "chain_rate", "assert_kinds_cover_dims", "assert_chain_refs_known",
]


def _kinds() -> Dict[str, str]:
    from content.data_constants import COMMODITY_KINDS

    return COMMODITY_KINDS or {}


def _chains() -> Dict[str, dict]:
    from content.data_constants import PROCESS_CHAINS

    return PROCESS_CHAINS or {}


def kind_of(dim: str) -> Optional[str]:
    """商品维的类别（粮/原料/成品/军需…）；未登记 ⇒ None。"""
    return _kinds().get(dim)


def is_grain(dim: str) -> bool:
    """是否粮类。**缺失不是粮**（返回 False，不抛错）。"""
    from content.data_constants import GRAIN_KIND

    return kind_of(dim) == GRAIN_KIND


def grain_dims(active_only: bool = False) -> List[str]:
    """全部粮维（`active_only=True` 只返回已立商品维的，如排除「面」）。"""
    from content.data_constants import GRAIN_KIND

    out = [d for d, k in _kinds().items() if k == GRAIN_KIND]
    if not active_only:
        return out
    from core.foundation.ledger.goods_class import is_active

    return [d for d in out if is_active(d)]


def chain_of(dim: str) -> Optional[dict]:
    """该维的加工链定义（不是中间产物 ⇒ None）。"""
    return _chains().get(dim)


def chain_inputs(dim: str) -> Dict[str, float]:
    """加工该维所需的输入（{维: 数量}）；无链 ⇒ {}。"""
    c = chain_of(dim) or {}
    return dict(c.get("inputs") or {})


def chain_rate(dim: str) -> Optional[float]:
    """产出率；**None = 未核定，禁止隐式换算**。"""
    c = chain_of(dim) or {}
    r = c.get("rate")
    return float(r) if isinstance(r, (int, float)) and not isinstance(r, bool) else None


def assert_kinds_cover_dims() -> List[str]:
    """每个 GOODS_DIMS 维都必须有 kind。返回问题清单（空 = 干净）。"""
    from content.data_constants import GOODS_DIMS

    return [d for d in GOODS_DIMS if d not in _kinds()]


def assert_chain_refs_known() -> List[str]:
    """加工链引用的输入/产出维必须都已登记 kind。返回问题清单（空 = 干净）。"""
    issues: List[str] = []
    for out_dim, spec in _chains().items():
        if out_dim not in _kinds():
            issues.append(f"链产出 {out_dim} 未登记 kind")
        r = spec.get("rate")
        if r is not None and not (isinstance(r, (int, float)) and not isinstance(r, bool)):
            issues.append(f"链 {out_dim} 的 rate 非数值：{r!r}")
        for in_dim in (spec.get("inputs") or {}):
            if in_dim not in _kinds():
                issues.append(f"链 {out_dim} 的输入 {in_dim} 未登记 kind")
    return issues