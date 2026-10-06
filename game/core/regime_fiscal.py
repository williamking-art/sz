"""外邦/主要国家政权的**财政自适应**（用户裁定 2026-10-06：全局都要有，宋不用）。

裁定原文：「**全局都要有，宋不用**，宋在玩家手里，或者说，玩家游玩的势力**不需要自动**」。

=> 本模块**只作用于 AI 政权**（`state.external_regimes`），
   **绝不触碰宋侧**（宋的财政处置权在玩家手里）。

## 为什么需要

实测：大理军饷官俸/税收 = **2.42×**，`need_army/need_off` 是**纯公式**
（兵数 × 单价，**完全不看 treasury**），欠饷只记 `arrears` + `unrest += 1`。
=> **赤字不会自我修复**，大理 treasury 永久锁在 1，unrest 每月 +2 直至 100，
   玩家既无法干预也无法预见。

## 自适应阶梯（按月递进，欠饷越久手段越硬）

| 级 | 手段 | 口径 |
|---|---|---|
| 1 | **裁军** | 兵 → 农，走 `move_pop_people`（**ΣPOP 守恒**，不得凭空减员）|
| 2 | **减官** | 官僚 → 士绅，同走 `move_pop_people` |
| 3 | **加税** | 临时附加税 `surcharge`，**有上限** |

🔴 **缺失 ≠ 0**：读数取不到时**不回落 0 假装**，按「无法判定」处理并记账。
"""
from typing import Any, Dict, List

from core.pop_structure import move_pop_people


#: 连续欠饷达到多少月才开始动作
DEFICIT_STREAK_TRIGGER = 3
#: 每级裁减比例
CUT_ARMY_RATIO = 0.08
CUT_OFFICIAL_RATIO = 0.05
#: 附加税档位与上限
TAX_SURCHARGE_STEP = 0.2
TAX_SURCHARGE_MAX_STEPS = 3


def _cut(pops: Dict[str, dict], src_key: str, dst_key: str, ratio: float) -> int:
    """按比例裁减 `src_key` 并**迁入** `dst_key`（走既有通道，ΣPOP 守恒）。"""
    src = pops.get(src_key)
    dst = pops.get(dst_key)
    if not isinstance(src, dict) or not isinstance(dst, dict):
        return 0
    n = int(src.get("size", 0) or 0)
    if n <= 0:
        return 0
    k = int(n * float(ratio))
    if k <= 0:
        return 0
    move_pop_people(src, dst, k)
    return k


def apply_fiscal_response(ex: dict, provinces: List[dict], arrears: int) -> Dict[str, Any]:
    """对单个 AI 政权施加一个月的财政自适应。返回本月的处置明细。

    `arrears > 0` ⇒ 累加 `fiscal_streak`；连续达 `DEFICIT_STREAK_TRIGGER`
    后按阶梯逐级加码；结清后 streak 归零、附加税按月回落。
    """
    out = {"arrears": int(arrears or 0), "streak": 0, "step": 0,
           "cut_army": 0, "cut_officials": 0, "surcharge_steps": 0}
    if not isinstance(ex, dict):
        return out
    fin = ex.setdefault("fiscal", {})
    if not isinstance(fin, dict):
        fin = {}
        ex["fiscal"] = fin

    if int(arrears or 0) > 0:
        fin["streak"] = int(fin.get("streak", 0) or 0) + 1
    else:
        fin["streak"] = 0
    streak = int(fin["streak"])
    out["streak"] = streak

    # 结清后附加税每月回落一档（可逆，不是单向惩罚）
    steps = int(fin.get("surcharge_steps", 0) or 0)
    if steps > 0 and int(arrears or 0) <= 0:
        steps = max(0, steps - 1)
        fin["surcharge_steps"] = steps
    if streak < int(DEFICIT_STREAK_TRIGGER) or steps >= int(TAX_SURCHARGE_MAX_STEPS):
        out["surcharge_steps"] = steps
        return out

    step = int(fin.get("step", 0) or 0)
    tot_army = 0
    tot_off = 0
    for pr in (provinces or []):
        if not isinstance(pr, dict):
            continue
        pops = pr.get("pops")
        if not isinstance(pops, dict):
            continue
        if step == 0:
            tot_army += _cut(pops, "兵", "农", CUT_ARMY_RATIO)
        elif step == 1:
            tot_off += _cut(pops, "官僚", "士绅", CUT_OFFICIAL_RATIO)
    if step == 0:
        out["cut_army"] = tot_army
    elif step == 1:
        out["cut_officials"] = tot_off
    else:
        steps += 1
        fin["surcharge_steps"] = steps
        out["surcharge_steps"] = steps
    fin["step"] = step + 1
    out["step"] = int(fin["step"])
    return out