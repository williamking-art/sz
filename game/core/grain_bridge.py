# -*- coding: utf-8 -*-
"""🔴 **G-3 读写桥** —— `pops[].grain` ⇄ `goods[治所][米]` 的**单点过渡层**。

## 为什么是桥而不是逐点改

`pops[].grain` 有 **写入 262 / 读取 128** 处。若逐点改，会在某个中间态出现
「写 `goods`、读 `.grain`」的**双源不一致** —— 余额会静默漂移且无人察觉。

过渡期做法：

1. **读**全部走本模块（`grain_get`），迁移未完成时自动回落到旧字段 `.grain`；
2. **写**全部走本模块（`grain_add` / `grain_set`），已迁移载体落 `goods[米]`、
   未迁移载体仍落 `.grain`，**由同一函数保证两者不会各写一半**；
3. 全部调用点改完后（写入 0 / 读取 0），`.grain` 字段整体退役。

🔴 **双写禁令**：任一时刻**不得**同时改 `goods[米]` 与 `.grain` —— 
桥接层保证「同一载体二选一」，杜绝双账。
"""
from typing import Optional

from core.grain_ledger import GRAIN_MIGRATION_DIM, has_grain_bucket


def grain_get(pop: Optional[dict]) -> Optional[int]:
    """**读**：已迁移载体读 `goods[米麦]`，未迁移回落到旧 `.grain`。缺失 ⇒ `None`。"""
    if not isinstance(pop, dict):
        return None
    if has_grain_bucket(pop):
        goods = pop.get("goods") or {}
        tot = 0
        has = False
        for d in ("米", "麦"):
            v = goods.get(d)
            if isinstance(v, (int, float)):
                has = True
                tot += int(v)
        if has:
            return tot
    g = pop.get("grain")
    return int(g) if isinstance(g, (int, float)) else None


def grain_target(pop: Optional[dict]) -> str:
    """该 POP 的粮当前落在哪个载体：`"goods"` 或 `"legacy"`。"""
    return "goods" if has_grain_bucket(pop) else "legacy"


def grain_set(pop: Optional[dict], value: int) -> None:
    """**写（覆盖）**：按载体写，二者只写其一，绝不双写。"""
    if not isinstance(pop, dict):
        return
    if grain_target(pop) == "goods":
        pop.setdefault("goods", {})[GRAIN_MIGRATION_DIM] = int(value)
    else:
        pop["grain"] = int(value)


def grain_add(pop: Optional[dict], delta: int) -> int:
    """**写（增量）**：读 → 加 → 覆盖写回。返回写后值；无基线时按 0 起算并**如实建载体**。"""
    cur = grain_get(pop)
    if cur is None:
        cur = 0
    nxt = max(0, cur + int(delta))
    grain_set(pop, nxt)
    return nxt


__all__ = ["grain_get", "grain_set", "grain_add", "grain_target"]
