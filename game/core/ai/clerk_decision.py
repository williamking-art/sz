# -*- coding: utf-8 -*-
"""地方官吏催科严厉度决策门面（Clerk Enforcement Decision）。

定位：
- 采用 EmbeddedJevEngine 驱动微观决策；
- 知州性格（清廉度、务实度）、灾情、民怨、府库充盈度作为决策上下文；
- 裁定催科倾向：strict（严厉催科）、moderate（常典奉公）、lenient（宽减抚恤）；
- 降级保护：零开销纯本地兜底，绝不抛异常阻断结算流程；脱敏优先，不暴露底层概率。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.ai.embedded_jev import EmbeddedJevEngine

log = logging.getLogger("songzuo.ai.clerk")

__all__ = ["ClerkDecision", "decide_clerk_enforcement"]


class ClerkDecision:
    """官吏催科倾向决策结果。"""

    def __init__(self, mode: str, mult: float, mood_delta: float, note: str):
        self.mode = mode             # "strict" | "moderate" | "lenient"
        self.mult = mult             # 征敛金额乘数（如 1.20, 1.00, 0.80）
        self.mood_delta = mood_delta # 对本路民心的冲击（如 -1.0, 0.0, +0.5）
        self.note = note             # 决策说明

    def __repr__(self) -> str:
        return f"<ClerkDecision mode={self.mode} mult={self.mult:.2f} mood_delta={self.mood_delta:+.1f}>"


def decide_clerk_enforcement(state: Any, prefecture: Dict[str, Any]) -> ClerkDecision:
    """为指定府路裁定本月官吏催科倾向。"""
    if not isinstance(prefecture, dict) or not prefecture:
        return ClerkDecision(mode="moderate", mult=1.00, mood_delta=0.0, note="空上下文默认常典")
    try:
        # 1. 提取客观情境特征
        mood = float(prefecture.get("mood", 55.0) or 55.0)
        unrest = max(0.0, 100.0 - mood)
        disaster = float(prefecture.get("disaster_level", 0.0) or 0.0)
        
        # 知州官员属性（若该路有守臣）
        gov = prefecture.get("governor") or prefecture.get("official") or {}
        integrity = float(gov.get("integrity", 0.6) if isinstance(gov, dict) else 0.6)
        diligence = float(gov.get("diligence", 0.6) if isinstance(gov, dict) else 0.6)

        # 地方与国库财力
        treasury = float(getattr(state, "treasury", 100000) or 0)
        fiscal_pressure = 1.0 if treasury < 50000 else 0.0

        ctx: Dict[str, Any] = {
            "unrest": unrest,
            "disaster": disaster,
            "gov": {"integrity": integrity, "diligence": diligence},
            "treasury": treasury,
        }

        # 2. 构造多选一先验权重
        # strict: 严官/贪酷/库空时上升；lenient: 灾荒/清廉/民怨高时上升；moderate: 稳健中庸
        criteria = {
            "strict": 0.30 + fiscal_pressure * 0.30 + (1.0 - integrity) * 0.20,
            "lenient": 0.30 + (disaster * 0.40) + (integrity * 0.20) + (0.20 if unrest > 30 else 0.0),
            "moderate": 0.40,
        }

        res = EmbeddedJevEngine.choose(
            state_context=ctx,
            instructions="裁定地方官吏催科严厉度",
            criteria=criteria,
        )
        choice = res.get("verdict", "moderate")

        if choice == "strict":
            return ClerkDecision(
                mode="strict",
                mult=1.20,
                mood_delta=-1.2,
                note="库藏吃紧、吏员严厉追呼，催征倍急",
            )
        elif choice == "lenient":
            return ClerkDecision(
                mode="lenient",
                mult=0.80,
                mood_delta=0.8,
                note="体恤民艰、按户停息追督，宽恩抚民",
            )
        else:
            return ClerkDecision(
                mode="moderate",
                mult=1.00,
                mood_delta=0.0,
                note="守常奉公，照簿按程督理",
            )
    except Exception as e:
        log.warning("官吏催科决策降级至常典: %r", e, exc_info=True)
        return ClerkDecision(mode="moderate", mult=1.00, mood_delta=0.0, note="降级常典")
