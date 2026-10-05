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

#: 🔴 G-3 片5（2026-10-04）：`grain` 已列入 `pop_bridge.SPLIT_FIELDS`（可加：粮是总量），
#: 故路级 POP 的粮写入必须**下沉到州府**，否则路级值会与 Σ治所**静默分叉**。
#: 本模块因此接受**可选 `state`**：给了就委派 `pop_bridge`（先落州府、再刷路级镜像）；
#: 没给则沿用原载体解析（迁移未完成的调用点仍走 legacy，行为等价）。


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


def _delegate(state, pop: Optional[dict], value: int) -> Optional[int]:
    """把覆盖写**下沉到州府**（`pop_bridge`）。pop 非路级下沉 POP ⇒ `None`（未下沉）。

    返回 `None` 表示「没下沉/没登记」，调用方**必须**据此回落原写法。
    """
    from core.pop_bridge import locate_pops, pop_obj_set
    pdata, _cls = locate_pops(state, pop)
    if pdata is None:
        return None
    return pop_obj_set(state, pop, "grain", int(value))


def grain_set(pop: Optional[dict], value: int, state=None) -> None:
    """**写（覆盖）**：按载体写，二者只写其一，绝不双写。

    给了 `state` 且该 POP 属于已下沉的路 ⇒ **下沉到州府**（路由级改为派生镜像）。
    """
    if not isinstance(pop, dict):
        return
    if state is not None and _delegate(state, pop, value) is not None:
        return
    if grain_target(pop) == "goods":
        pop.setdefault("goods", {})[GRAIN_MIGRATION_DIM] = int(value)
    else:
        pop["grain"] = int(value)


def grain_add(pop: Optional[dict], delta: int, state=None) -> int:
    """**写（增量）**：读 → 加 → 覆盖写回。返回写后值；无基线时按 0 起算并**如实建载体**。"""
    cur = grain_get(pop)
    if cur is None:
        cur = 0
    nxt = max(0, cur + int(delta))
    grain_set(pop, nxt, state)
    return nxt


def backfill_grain_to_seats(pdata: dict, circuit: str) -> int:
    """**G-3 片5 回填**：把路级 `pops[类]["grain"]` 存量**下沉到各治所**。

    背景：H 裁定甲要求粮走 `goods[治所][米/麦]` 州府桶，使「运没运到」对粮可观测。
    本函数在**迁移/开局下沉之后**调用：按治所人口权重拆分路级粮（尾差归权重最大者），
    **Σ治所与路级原值精确相等**，随后由 `sync_route_pops` 把路级刷新为派生镜像。

    **幂等**：治所已有粮（`grain` 键存在且非 None）时**跳过**该治所 ⇒ 二次调用不会重复加。
    返回本次回填的治所数。
    """
    from core.pop_bridge import (POP_CLASSES, _split_int, seat_pop_weights)
    seats = (pdata or {}).get("seats") or {}
    if not seats:
        return 0
    w = seat_pop_weights(str(circuit))
    if not w:
        return 0                       # 无治所人口权重 ⇒ 不臆造归属
    done = 0
    for cls in POP_CLASSES:
        src = (pdata.get("pops") or {}).get(cls)
        if not isinstance(src, dict):
            continue
        legacy = src.get("grain")
        if not isinstance(legacy, (int, float)) or isinstance(legacy, bool):
            continue                   # 缺失 ≠ 0：无存量可回填
        legacy = int(legacy)
        parts = _split_int(legacy, w)
        for sid, _pop in w:
            row = ((seats.get(sid) or {}).get("pops") or {}).get(cls)
            if not isinstance(row, dict):
                continue
            if isinstance(row.get("grain"), (int, float)) and not isinstance(row.get("grain"), bool):
                continue               # 已回填 ⇒ 幂等跳过
            row["grain"] = int(parts.get(sid, 0))
            done += 1
    return done

__all__ = ["grain_get", "grain_set", "grain_add", "grain_target",
           "backfill_grain_to_seats"]
