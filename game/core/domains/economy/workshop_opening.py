# -*- coding: utf-8 -*-
"""作坊**开局/存量补座**（产能批 · 主线 P1 真瓶颈）—— 纯逻辑、**确定性、幂等**。

依据（全部已裁/已测，见 `_dev_tools/handover/decisions/`）：
* 旋钮＝**作坊数量**（`M181`/`M173` Jev 乙 0.591）
* 量级＝**温和 ~10%**（`M181` Jev 甲 0.450）⇒ 丝坊 **7 → 约 28 座**
* 公式＝**线性**（`M185` 实测：单座 `yield=8000`、参数全同 ⇒ 产能＝座数×8000/轮）
* 分布＝**按丝产能加权**（`M186` Jev 丁 0.388）：按 `prefectures[路]['yields']['丝']` 份额，
  **最大余数法**（`Σ == extra`），只落**丝禀赋 > 0** 的路，**确定性可复现**

纪律
----
* **幂等**：`open_extra_workshops` 只**补差**（按路统计已有 `丝坊_<路>_*` 键），重复调用不再增座。
* **不改 `yield`**（改的是**数量**，与旋钮一致）· **不造钱物**（仅建作坊实例，钱货不动）。
* **口径单点**：实例模板取自 `content.data.WORKSHOP_RECIPES["丝坊"]`（不复制参数）。
* **本模块不自行接线**：调用点由 `game_state.__init__` 与幂等迁移负责（另行一批）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

SILK_TYPE = "丝坊"
DEFAULT_TARGET_TOTAL = 28              # 绝对目标：7 → 28 座（Jev 甲 ~10%；M185/M186）
DEFAULT_EXTRA = DEFAULT_TARGET_TOTAL - 7   # 兼容别名：相对开局的增量（21）

__all__ = ["SILK_TYPE", "DEFAULT_EXTRA", "silk_share_plan", "existing_silk_count",
           "open_extra_workshops"]


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def existing_silk_count(state) -> Dict[str, int]:
    """每路已有丝坊座数（键前缀 `丝坊_<路>_`；路名取自 `state.prefectures`，**不遍历别的表**）。"""
    prefs = getattr(state, "prefectures", None) or {}
    out: Dict[str, int] = {str(r): 0 for r in prefs}
    for k in (getattr(state, "workshops", None) or {}):
        if not str(k).startswith(SILK_TYPE + "_"):
            continue
        rest = str(k)[len(SILK_TYPE) + 1:]
        route = rest.rsplit("_", 1)[0] if "_" in rest else rest
        if route in out:
            out[route] += 1
    return out


def silk_share_plan(state, extra: int = DEFAULT_EXTRA) -> Dict[str, int]:
    """按**丝禀赋份额**把 `extra` 座分配为 `{路: 新增座数}`（**Σ == extra**，最大余数法）。

    只落 `yields['丝'] > 0` 的路；无可分配路 ⇒ 返回 `{}`（**不臆造**）。
    """
    prefs = getattr(state, "prefectures", None) or {}
    weights: List[tuple] = []
    for route, p in prefs.items():
        y = (p or {}).get("yields") or {}
        w = _num(y.get("丝"))
        if w and w > 0:
            weights.append((str(route), float(w)))
    if not weights or extra <= 0:
        return {}
    weights.sort(key=lambda kv: (-kv[1], kv[0]))        # 确定性：权重降序 + 路名打破并列
    total = sum(w for _r, w in weights) or 1.0
    exact = [(r, float(extra) * w / total) for r, w in weights]
    base = {r: int(v) for r, v in exact}
    rem = int(extra) - sum(base.values())
    if rem > 0:
        order = sorted(exact, key=lambda kv: (-(kv[1] - int(kv[1])), kv[0]))
        for r, _v in order[:rem]:
            base[r] += 1
    return {r: v for r, v in base.items() if v > 0}


def open_extra_workshops(state, target_total: int = DEFAULT_TARGET_TOTAL) -> int:
    """**幂等补座**：把丝坊**总量**提到 `target_total`（**绝对值**，默认 28 = 7 + 21），
    按丝份额分布；返回**本次新增**座数。

    * **绝对目标 ⇒ 天然幂等**：一旦 `Σ现有 ≥ target_total` ⇒ 本次新增 **0**（重复调用不再增座）。
    * 分布按 `target_total` 的份额（`silk_share_plan`），再减各路已有；**配平保证
      `Σ新增 == max(0, target_total − Σ现有)`**（无丝路上的既有座不参与分布，差额补/扣见下）。
    * 实例模板取 `WORKSHOP_RECIPES["丝坊"]`（口径单点）· 键名沿用 `丝坊_<路>_<序号>`。
    """
    target_total = int(target_total)
    have = existing_silk_count(state)
    desired_add = max(0, target_total - sum(have.values()))
    if desired_add == 0:
        return 0
    plan = silk_share_plan(state, target_total)
    if not plan:
        return 0
    need = {r: int(w) - int(have.get(r, 0)) for r, w in plan.items()}
    # 🔴 **对称配平**：保证 Σ(新增) **恒等于 desired_add**
    #  · 正缺口（无丝路上的既有座未进计划）⇒ 补到权重最高的有丝路
    #  · 负缺口（计划内已含足量）⇒ 从"新增最少"的路**扣减**（确定性顺序）
    _yld = lambda r: float((state.prefectures[r].get("yields") or {}).get("丝", 0))
    order_hi = sorted(plan, key=lambda r: (-_yld(r), r))
    gap = desired_add - sum(v for v in need.values() if v > 0)
    i = 0
    while gap > 0 and order_hi:
        r = order_hi[i % len(order_hi)]
        need[r] = max(0, need.get(r, 0)) + 1
        gap -= 1
        i += 1
    while gap < 0:
        cand = [r for r in sorted(need, key=lambda r: (need[r], r)) if need[r] > 0]
        if not cand:
            break
        need[cand[0]] -= 1
        gap += 1
    try:
        from content.data import WORKSHOP_RECIPES
        tmpl = dict(WORKSHOP_RECIPES[SILK_TYPE])
    except Exception:                                        # noqa: BLE001
        log.warning("作坊补座：丝坊模板不可读 ⇒ 不补（缺失≠0）", exc_info=True)
        return 0
    added = 0
    store = getattr(state, "workshops", None)
    if not isinstance(store, dict):
        return 0
    for route, want in sorted(need.items()):
        for i in range(max(0, int(want))):
            idx = int(have.get(route, 0)) + i
            key = f"{SILK_TYPE}_{route}_{idx}"
            while key in store:                              # 键冲突 ⇒ 顺延（幂等且不覆盖既有）
                idx += 1
                key = f"{SILK_TYPE}_{route}_{idx}"
            store[key] = {**tmpl, "active": True}
            added += 1
    return added
