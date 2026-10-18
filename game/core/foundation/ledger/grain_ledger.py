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

#: 仓储损耗档位（天道裁决，2026-10-18 用户裁定：「粮的损耗不是有天道系统来裁决多寡吗」）
STORAGE_LOSS_TIERS = ("无", "轻", "中", "重")


def storage_loss_rate(tier: object = None) -> float:
    """**仓储月损耗率**：天道给档位 → 程序查表换算率（AI 不给数）。

    · 返回 SPARROW_RAT × STORAGE_LOSS_TIER_MULT[tier]；
    · 档位缺失/未知 ⇒ 按默认档（「中」= 1.2%，与改前行为完全一致）；
    · 不做隐式换算、不写账，只算率。
    """
    from content.data import SPARROW_RAT, STORAGE_LOSS_TIER_DEFAULT, STORAGE_LOSS_TIER_MULT

    t = str(tier) if isinstance(tier, str) else ""
    mult = STORAGE_LOSS_TIER_MULT.get(t)
    if mult is None:
        mult = STORAGE_LOSS_TIER_MULT[STORAGE_LOSS_TIER_DEFAULT]
    return float(SPARROW_RAT) * float(mult)


def assert_loss_tiers_sane() -> list:
    """档位表自检：默认档存在、倍率非负且随档位单调不减。返回问题清单。"""
    from content.data import STORAGE_LOSS_TIER_DEFAULT, STORAGE_LOSS_TIER_MULT

    issues = []
    if STORAGE_LOSS_TIER_DEFAULT not in STORAGE_LOSS_TIER_MULT:
        issues.append("默认档不在档位表中")
    prev = None
    for t in STORAGE_LOSS_TIERS:
        v = STORAGE_LOSS_TIER_MULT.get(t)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            issues.append(f"档位 {t} 缺少数值倍率")
            continue
        if v < 0:
            issues.append(f"档位 {t} 倍率为负：{v}")
        if prev is not None and v < prev:
            issues.append(f"档位 {t} 倍率低于上一档（应单调不减）")
        prev = v
    return issues


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
    # 2026-10-18：按**类目**判定（粮 = 米/麦/面…），不硬编码成员集合
    try:
        from content.data_constants import GRAIN_CLASS
        from core.foundation.ledger.goods_class import class_total

        return class_total(goods, GRAIN_CLASS) is not None
    except Exception:  # noqa: BLE001
        return False


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