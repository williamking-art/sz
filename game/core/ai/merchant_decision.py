# -*- coding: utf-8 -*-
"""商帮跨路运作与物资投机决策门面（Merchant Operation Decision）。

定位：
- 采用 EmbeddedJevEngine 驱动微观商帮决策；
- 物价指数、跨路价差、常平仓储备水平驱动商贾运作；
- 裁定运作倾向：hoard（囤积居奇待涨）、dump（平抑抛售获利）、hold（稳健观望微调）；
- 严守实物与货币守恒：所有物资流转必须发生在货栈/POP真实账本之间；
- 降级保护：零开销纯本地兜底，绝不抛异常阻断结算流程。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.ai.embedded_jev import EmbeddedJevEngine

log = logging.getLogger("songzuo.ai.merchant")

__all__ = ["MerchantDecision", "decide_merchant_operation"]


class MerchantDecision:
    """商帮物资运作决策结果。"""

    def __init__(self, action: str, tier: str, note: str):
        self.action = action  # "hoard" | "dump" | "hold"
        self.tier = tier      # "微" | "小" | "中" | "大"
        self.note = note      # 决策说明

    def __repr__(self) -> str:
        return f"<MerchantDecision action={self.action} tier={self.tier}>"


def decide_merchant_operation(state: Any, prefecture: Dict[str, Any]) -> MerchantDecision:
    """为指定府路裁定本月商帮粮食与物资运作倾向。"""
    if not isinstance(prefecture, dict) or not prefecture:
        return MerchantDecision(action="hold", tier="小", note="空上下文默认守常")
    try:
        # 1. 提取市场行情特征
        price = float(prefecture.get("grain_price", getattr(state, "grain_price", 1.0)) or 1.0)
        global_price = float(getattr(state, "grain_price", 1.0) or 1.0)
        price_gap = price - global_price

        # 官府常平仓存粮（若官府大举平粜，商人不敢对抗官仓）
        cp_stock = float(prefecture.get("changping_stock", 0.0) or 0.0)
        disaster = float(prefecture.get("disaster_level", 0.0) or 0.0)

        ctx: Dict[str, Any] = {
            "price": price,
            "gap": price_gap,
            "disaster": disaster,
            "stock": cp_stock,
        }

        # 2. 构造多属性先验权重
        # hoard: 低价/丰收或旱涝初显商人惜售；dump: 高价出清或官仓压价时抛售；hold: 价格温和
        criteria = {
            "hoard": 0.35 + (0.40 if price < 0.7 else 0.0) + (0.30 if disaster > 0.3 else 0.0),
            "dump": 0.35 + (0.45 if price > 1.6 else 0.0) + (0.20 if cp_stock > 50000 else 0.0),
            "hold": 0.30 + (0.30 if 0.8 <= price <= 1.4 else 0.0),
        }

        res = EmbeddedJevEngine.choose(
            state_context=ctx,
            instructions="裁定商帮物资囤售投机",
            criteria=criteria,
        )
        choice = res.get("verdict", "hold")

        if choice == "hoard":
            tier = "大" if price < 0.5 or disaster > 0.5 else "中"
            return MerchantDecision(
                action="hoard",
                tier=tier,
                note="谷贱收贮、防灾居奇",
            )
        elif choice == "dump":
            tier = "大" if price > 2.0 else "中"
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
