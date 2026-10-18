# -*- coding: utf-8 -*-
"""🔴 **G-3 迁移基座** —— 把 `pops[].grain` 迁入 `goods[治所][米/麦]`（裁定 H·甲）。

## 背景与裁定

2026-10-04 用户授权「以史实和游戏性为先」自行裁决，**H 裁定为甲**：
粮与其它商品共用同一条 `goods[治所][dim]` 通道，`pops[].grain` 降为**只读派生视图**。

- **史实**：元丰七年诏「荐新米麦之属，皆取于市……其所无者，乃索之杂买务」，
  杂买务「掌和市百物，凡宫禁、官府所需，以时供纳」⇒ 宋官府粮秣本就走市场；
- **游戏性**：只有甲能让粮共用州府桶，`运没运到` 对粮可观测；
  选乙（保留 `.grain`）会形成双载体，打折「口径单点」。

## 为什么单独成模块

G-3 规模：`pops[].grain` **写入 262 处 / 读取 128 处 / 太仓 20 处**。
本模块**只提供迁移与对账的纯函数**，**不改任何调用点** ——
迁移必须分片推进、每片单独对账，一次性全改会静默漂移余额且难以回滚。

## 三条硬约束

1. **派生视图不得双写**：`grain` 只由 `goods` 求和派生，**任何写入必须落 `goods`**；
2. **缺失 ≠ 0**：旧档 POP 若无米麦库存，不得回落成「有粮」；
3. **不臆造拆分比例**：`grain` 是单一无单位总量（`ding` 性质），**无米/麦分项数据** ⇒
   迁移时**全额记入「米」**（北宋以粟米为 principal 税粮），并**如实记录**这是口径假设而非史料依据。
"""
from typing import Dict, List, Optional

#: 迁移目标维。见上文约束 3：单一无单位总量无米麦分项，全额入「米」。
GRAIN_MIGRATION_DIM = "米"


def grain_of(pop: Optional[dict]) -> Optional[int]:
    """**派生读口**：该 POP 的粮 = `goods[米] + goods[麦]`。

    迁移完成后 `pops[].grain` 即由本函数派生；迁移前 `goods` 无米麦 ⇒ 返回 `None`
    而**不是 0**（缺失 ≠ 0，见约束 2）。
    """
    if not isinstance(pop, dict):
        return None
    goods = pop.get("goods")
    if not isinstance(goods, dict):
        return None
    # 2026-10-18：粮是**类目词条**（GOODS_CLASSES），不在此硬编码「米+麦」成员集合。
    # 口径单点 = core/foundation/ledger/goods_class.py；成员增减只改数据定义。
    from content.data_constants import GRAIN_CLASS
    from core.foundation.ledger.goods_class import class_total

    return class_total(goods, GRAIN_CLASS)


def has_grain_bucket(pop: Optional[dict]) -> bool:
    """该 POP 的 `goods` 是否已承载粮（米/麦任一）。用于判定迁移是否已实施。"""
    if not isinstance(pop, dict):
        return False
    goods = pop.get("goods")
    if not isinstance(goods, dict):
        return False
    return any(isinstance(goods.get(d), (int, float)) for d in ("米", "麦"))


def survey_grain(state) -> Dict[str, object]:
    """**迁移前对账**：`{路由数, Σgrain, Σgoods米麦, POP数, 迁移状态}`。

    这是 G-3 的**验收锚点** —— 迁移前后须分别调用本函数并比对。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    sum_grain = 0
    sum_bucket = 0
    npop = 0
    migrated = 0
    for route, pdata in prefs.items():
        pops = (pdata or {}).get("pops") or {}
        for _name, pop in (pops.items() if isinstance(pops, dict) else ()):
            if not isinstance(pop, dict):
                continue
            npop += 1
            g = pop.get("grain")
            if isinstance(g, (int, float)):
                sum_grain += int(g)
            if has_grain_bucket(pop):
                migrated += 1
                v = grain_of(pop)
                if v:
                    sum_bucket += int(v)
    return {
        "路由数": len(prefs),
        "POP数": npop,
        "Σpops[].grain": sum_grain,
        "Σgoods[米麦]": sum_bucket,
        "已迁移POP": migrated,
        "state.granary": int(getattr(state, "granary", 0) or 0),
        "迁移状态": "未迁移" if migrated == 0 else ("部分迁移" if migrated < npop else "已迁移"),
    }


__all__ = ["GRAIN_MIGRATION_DIM", "grain_of", "has_grain_bucket", "survey_grain"]