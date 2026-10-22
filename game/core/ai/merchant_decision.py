# -*- coding: utf-8 -*-
"""商帮物资运作决策门面（Merchant Operation Decision）。

定位：
- 采用天道引擎（`EmbeddedJevEngine` → `TianDaoEngine`）驱动微观决策；
- 市场行情（地方级粮价 vs 全局价差）、常平仓存量、灾情作为决策上下文；
- 裁定运作倾向：hoard（居奇囤积）/ dump（乘时发粜）/ hold（守常观望）；
- 降级保护：任何异常 ⇒ 守常（hold），绝不抛异常阻断结算。

🔴 2026-10-21 L1 契约统一（本模块的两处实质修复）
--------------------------------------------------
1. **上下文曾完全没被读取**：本模块的选项词表是 `hoard/dump/hold`，而引擎的
   `merchant_trade` objective 是 `ship/hoard/local_sell` ⇒ 键名推断得出 `""`，
   引擎不加任何偏置。于是它辛苦构造的 `gap`/`stock` **一个都没被消费**。
   本批明确记为**「本模块 = 纯 softmax 归一，引擎不加偏置」**——判断逻辑全部留在
   `criteria` 里（这是有意的单一职责，不是遗漏），上下文仅作留痕/未来校准之用。
2. **灾情量纲统一**：`disaster_level` 若给出 >1 的值视为 1~5 灾级 ⇒ /5；缺失回落到
   `state.disaster_severity/5`。此前 1~5 直接进引擎会被钳成 1.0（灾级 1 与 5 等价）。
3. **常平仓"重仓"阈值量纲**：旧 `cp_stock > 50000`，而实测单路 `changping_stock` 为
   371,062–742,125 ⇒ **恒真**（`dump` 永远多 0.20，等于常量偏置）。
   改为按"重仓"量级登记参数，使不同路真的有差别。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from core.ai.embedded_jev import EmbeddedJevEngine
from core.ai.tiandao_facts import canonicalize, normalize_disaster

log = logging.getLogger("songzuo.ai.merchant")

__all__ = ["MerchantDecision", "decide_merchant_operation",
           "MERCHANT_CP_STOCK_HEAVY", "MERCHANT_LOW_PRICE", "MERCHANT_HIGH_PRICE",
           "MERCHANT_CALM_LOW", "MERCHANT_CALM_HIGH", "MERCHANT_DISASTER_HOARD"]

# ---------------------------------------------------------------------------
# 结构先验参数（**微观域参数，登记在此单一处**）
# ---------------------------------------------------------------------------
#: 常平仓"重仓"线（石）。实测单路 `changping_stock` 371,062–742,125，
#: 取 400,000 使"重仓压制商价"成为**有区分度的判据**（旧值 50,000 恒真 = 常量偏置）。
MERCHANT_CP_STOCK_HEAVY = 400_000.0
#: 谷贱线（贯/石）：低于此值商人惜售囤积
MERCHANT_LOW_PRICE = 0.7
#: 价高线（贯/石）：高于此值乘时发粜
MERCHANT_HIGH_PRICE = 1.6
#: 价格温和区间（守常观望）
MERCHANT_CALM_LOW = 0.8
MERCHANT_CALM_HIGH = 1.4
#: 灾情"初显"线（0~1 强度）：超过此值惜售防灾
MERCHANT_DISASTER_HOARD = 0.3


class MerchantDecision:
    """商帮物资运作决策结果。"""

    def __init__(self, action: str, tier: str, note: str):
        self.action = action  # "hoard" | "dump" | "hold"
        self.tier = tier      # "微" | "小" | "中" | "大"
        self.note = note      # 决策说明

    def __repr__(self) -> str:
        return f"<MerchantDecision action={self.action} tier={self.tier}>"


def _price(prefecture: Dict[str, Any], state: Any) -> float | None:
    """地方级粮价；缺失回落到全局价；**0 不吞**（显式 None 判断）。"""
    v = prefecture.get("grain_price")
    if v is None:
        v = getattr(state, "grain_price", None)
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def decide_merchant_operation(state: Any, prefecture: Dict[str, Any]) -> MerchantDecision:
    """为指定府路裁定本月商帮粮食与物资运作倾向。"""
    if not isinstance(prefecture, dict) or not prefecture:
        return MerchantDecision(action="hold", tier="小", note="空上下文默认守常")
    try:
        # 1. 市场行情特征
        price = _price(prefecture, state)
        global_price = getattr(state, "grain_price", None)
        try:
            global_price = float(global_price) if global_price is not None else None
        except (TypeError, ValueError):
            global_price = None
        gap = (price - global_price) if (price is not None and global_price is not None) else None

        cp_stock = prefecture.get("changping_stock")
        try:
            cp_stock = float(cp_stock) if cp_stock is not None and not isinstance(cp_stock, bool) else None
        except (TypeError, ValueError):
            cp_stock = None

        # 灾情归一单一出处 = `tiandao_facts.normalize_disaster`（0~1 原样；>1 视为 1~5 灾等 ⇒ /5）
        disaster = normalize_disaster(prefecture.get("disaster_level"))
        if disaster is None:
            disaster = normalize_disaster(getattr(state, "disaster_severity", None)
                                          if state is not None else None)

        # 2. 上下文入 canonical facts（留痕/未来校准用；本 objective 引擎不加偏置）
        ctx: Dict[str, Any] = {k: v for k, v in canonicalize({
            "gap": gap, "disaster": disaster, "changping_stock": cp_stock,
        }).items() if v is not None}

        # 3. 多属性先验权重（**判断逻辑全在这里**）
        criteria = {
            "hoard": 0.35
                     + (0.40 if (price is not None and price < MERCHANT_LOW_PRICE) else 0.0)
                     + (0.30 if (disaster is not None
                                 and disaster > MERCHANT_DISASTER_HOARD) else 0.0),
            "dump": 0.35
                    + (0.45 if (price is not None and price > MERCHANT_HIGH_PRICE) else 0.0)
                    + (0.20 if (cp_stock is not None
                                and cp_stock > MERCHANT_CP_STOCK_HEAVY) else 0.0),
            "hold": 0.30
                    + (0.30 if (price is not None
                                and MERCHANT_CALM_LOW <= price <= MERCHANT_CALM_HIGH) else 0.0),
        }

        res = EmbeddedJevEngine.choose(
            state_context=ctx,
            instructions="裁定商帮物资囤售投机",
            criteria=criteria,
        )
        choice = res.get("verdict") or "hold"

        if choice == "hoard":
            tier = "大" if (price is not None and price < 0.5) or (
                disaster is not None and disaster > 0.5) else "中"
            return MerchantDecision(
                action="hoard",
                tier=tier,
                note="谷贱收贮、防灾居奇",
            )
        elif choice == "dump":
            tier = "大" if (price is not None and price > 2.0) else "中"
            return MerchantDecision(
                action="dump",
                tier=tier,
                note="乘时发粜、高抬求售",
            )
        else:
            return MerchantDecision(
                action="hold",
                tier="小",
                note="市平待变、按规流转",
            )
    except Exception as e:
        log.warning("商帮决策降级至守常: %r", e, exc_info=True)
        return MerchantDecision(action="hold", tier="小", note="降级守常")
