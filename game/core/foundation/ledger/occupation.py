# -*- coding: utf-8 -*-
"""occupation（职业）人口层 —— **M35-C 单点口径**（读侧并入；不新增 POP、不新增粮桶）。

裁决口径（D1 甲／D2 甲）：
- **人口**：六桶 `size` **不含**职业人口；在籍人口＝Σ六桶 size ＋ Σoccupation ＋ 流民；
- **粮耗**：职业人口**计粮**，但**归挂靠桶**（`HOST_POOL`），**不新增粮桶**；
- **纪律（M35-C-2）**：所有"人口粮需／饥饿判断／粮仓需求／购粮能力／市场与读数"一律经**本模块**取值，
  **禁止**各模块自行 `runner_count × GRAIN_CONSUME_PER_CAPITA`（否则必然多口径漂移）。

存储位置：职业计数＝`pops[挂靠桶]["<occupation>_count"]`（M35-C-1：`官僚.runner_count`），
真账在治所级 `seats`（经 `pop_bridge` 写入）；路级旧位 `prefectures[路]["runners"]` 仅作兼容回落。
"""
from typing import Any, Dict

#: 职业 → 挂靠桶（**单点映射**；新增职业只改这一处）
HOST_POOL: Dict[str, str] = {"runner": "官僚"}
#: 路级旧位字段（M35-1 接口留白；迁移后清零，以避免双源漂移）
LEGACY_ROUTE_FIELD = "runners"


def _i(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def occupation_counts(pops: Any) -> Dict[str, int]:
    """{职业: 计数}（口）——**职业人口单一取数点**；缺失/坏值 → 0（不伪造人口）。"""
    out: Dict[str, int] = {}
    if not isinstance(pops, dict):
        return out
    for occ, host in HOST_POOL.items():
        pool = pops.get(host)
        v = _i(pool.get(f"{occ}_count")) if isinstance(pool, dict) else 0
        out[occ] = max(0, v)
    return out


def occupation_count_for_pool(pops: Any, cls: str) -> int:
    """该类桶内的**职业附加人口**（口）：仅挂靠桶非零（`HOST_POOL` 单点）。"""
    if not isinstance(pops, dict) or not cls:
        return 0
    total = 0
    for occ, host in HOST_POOL.items():
        if host != cls:
            continue
        pool = pops.get(cls)
        if isinstance(pool, dict):
            total += max(0, _i(pool.get(f"{occ}_count")))
    return total


def effective_size(pops: Any, cls: str, size: Any = None) -> int:
    """**有效人口**（口）＝桶 `size` ＋ 该桶职业附加人口（"人头"口径统一入口）。"""
    if size is None:
        pool = (pops or {}).get(cls) if isinstance(pops, dict) else None
        size = (pool or {}).get("size", 0) if isinstance(pool, dict) else 0
    return max(0, _i(size)) + occupation_count_for_pool(pops, cls)


def food_need_of(pops: Any, cls: str, per_capita: Any = None) -> float:
    """该类（含职业附加）**月口粮需求**（石）＝`effective_size × 人均`（单点公式）。"""
    if per_capita is None:
        from content.data import GRAIN_CONSUME_PER_CAPITA
        per_capita = (GRAIN_CONSUME_PER_CAPITA or {}).get(cls, 0.5)
    try:
        per = float(per_capita or 0.0)
    except (TypeError, ValueError):
        per = 0.0
    if per <= 0:
        return 0.0
    return effective_size(pops, cls) * per


def effective_size_of_pool(pool: Any, cls: str) -> int:
    """**仅持有单池**的调用方（如读数槽函数）用的有效人口：池 `size` ＋ 该池职业附加。"""
    if not isinstance(pool, dict):
        return 0
    base = max(0, _i(pool.get("size")))
    if HOST_POOL.get("runner") == cls:
        base += max(0, _i(pool.get("runner_count")))
    return base


def food_need_of_pool(pool: Any, cls: str, per_capita: Any = None) -> float:
    """单池版月口粮需求（石）＝`effective_size_of_pool × 人均`（读数侧统一入口）。"""
    if per_capita is None:
        from content.data import GRAIN_CONSUME_PER_CAPITA
        per_capita = (GRAIN_CONSUME_PER_CAPITA or {}).get(cls, 0.5)
    try:
        per = float(per_capita or 0.0)
    except (TypeError, ValueError):
        per = 0.0
    if per <= 0:
        return 0.0
    return effective_size_of_pool(pool, cls) * per


def occupation_food_need(pops: Any) -> float:
    """**职业附加人口**的口粮需求（石）——单点派生（供读数与断言对照，不参与结算二次计算）。"""
    from content.data import GRAIN_CONSUME_PER_CAPITA
    counts = occupation_counts(pops)
    total = 0.0
    for occ, host in HOST_POOL.items():
        n = counts.get(occ, 0)
        if n <= 0:
            continue
        per = float((GRAIN_CONSUME_PER_CAPITA or {}).get(host, 0.5) or 0.5)
        total += n * per
    return total
