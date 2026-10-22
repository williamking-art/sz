# -*- coding: utf-8 -*-
"""地方官吏催科严厉度决策门面（Clerk Enforcement Decision）。

定位：
- 采用天道引擎（`EmbeddedJevEngine` → `TianDaoEngine`）驱动微观决策；
- 知州性格（清廉度、务实度）、灾情、民怨、府库充盈度作为决策上下文；
- 裁定催科倾向：strict（严厉催科）、moderate（常典奉公）、lenient（宽减抚恤）；
- 降级保护：零开销纯本地兜底，绝不抛异常阻断结算流程；脱敏优先，不暴露底层概率。

🔴 2026-10-21 L1 契约统一（本模块的三处实质修复）
--------------------------------------------------
审计实测发现本模块与天道引擎**各自都把「吏治 + 灾情」算了一遍**，构成重复计入：
纯 softmax 给 `lenient` 0.458，引擎再加偏置后 0.57。本批改为**职责切分**：

* **本模块的 `criteria` 只放结构先验**（府库吃紧 ⇒ 偏严；民怨偏高 ⇒ 偏宽）。
  吏治（integrity）与灾情（disaster）**一律交给引擎的 `tax_stance` 分支**，不再重复编码。
* 上下文一律走 `core.ai.tiandao_facts` 的 canonical 键（缺失= None、量纲固定），
  不再自造 `gov` 嵌套键。
* **灾情量纲统一**：`state.disaster_severity` 是 0~5 的**灾级**，本模块对外一律用 0~1 强度。
  地方级 `prefecture["disaster_level"]` 若存在则按 0~1 强度解释；若给出 >1 的值，按"仍是
  1~5 灾级"折算（历史上 `contracts_settle` 的灾级就是 1~5，两种口径都兼容）。
  此前本模块把 1~5 直接塞给引擎、被引擎钳成 1.0 ⇒ **灾级 1 与灾级 5 等价**。

兜底：任何异常 ⇒ 常典（moderate），并 `logging.warning(..., exc_info=True)`。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from core.ai.embedded_jev import EmbeddedJevEngine
from core.ai.tiandao_facts import canonicalize, normalize_disaster, to_engine_context

log = logging.getLogger("songzuo.ai.clerk")

__all__ = ["ClerkDecision", "decide_clerk_enforcement",
           "CLERK_FISCAL_TREASURY_MIN", "CRITERIA_STRICT_BASE", "CRITERIA_LENIENT_BASE",
           "CRITERIA_MODERATE_BASE", "CRITERIA_FISCAL_WEIGHT", "CRITERIA_UNREST_WEIGHT",
           "CRITERIA_UNREST_THRESHOLD"]

# ---------------------------------------------------------------------------
# 结构先验参数（**微观域参数，登记在此单一处**；与引擎的 tax_stance 偏置互不重叠）
# ---------------------------------------------------------------------------
#: 路库"见底"线（贯）。实测路级 `local_treasury` 区间 270,000–1,950,000（新局），
#: 故 200,000 表示"确实吃紧"；旧实现用 `treasury < 50000` 对国库量级（5,000,000）永不触发。
CLERK_FISCAL_TREASURY_MIN = 200_000.0
#: strict 基础分（常典基准 0.40 之下略低，便于"库空/贪酷"把它顶上来）
CRITERIA_STRICT_BASE = 0.30
#: lenient 基础分
CRITERIA_LENIENT_BASE = 0.30
#: moderate（守常）基础分
CRITERIA_MODERATE_BASE = 0.40
#: 府库吃紧对 strict 的加权
CRITERIA_FISCAL_WEIGHT = 0.30
#: 民怨偏高对 lenient 的加权
CRITERIA_UNREST_WEIGHT = 0.20
#: 民怨偏高判定线（0~100）
CRITERIA_UNREST_THRESHOLD = 30.0


class ClerkDecision:
    """官吏催科倾向决策结果。"""

    def __init__(self, mode: str, mult: float, mood_delta: float, note: str):
        self.mode = mode             # "strict" | "moderate" | "lenient"
        self.mult = mult             # 征敛金额乘数（如 1.20, 1.00, 0.80）
        self.mood_delta = mood_delta # 对本路民心的冲击（如 -1.0, 0.0, +0.5）
        self.note = note             # 决策说明

    def __repr__(self) -> str:
        return f"<ClerkDecision mode={self.mode} mult={self.mult:.2f} mood_delta={self.mood_delta:+.1f}>"


def _route_disaster(state: Any, prefecture: Dict[str, Any]) -> float | None:
    """灾情强度：地方级字段优先，缺失回落到全 state 的 `disaster_severity`（灾级/5）。

    归一实现**单一出处** = `core.ai.tiandao_facts.normalize_disaster`
    （0~1 原样；>1 视为 1~5 灾等 ⇒ /5；非数值 ⇒ None）。此前本模块与
    `merchant_decision` 各存一份逐字节相同的实现，被跨文件重复实现守卫拦下。
    """
    local = normalize_disaster(prefecture.get("disaster_level"))
    if local is not None:
        return local
    return normalize_disaster(
        getattr(state, "disaster_severity", None) if state is not None else None)


def decide_clerk_enforcement(state: Any, prefecture: Dict[str, Any]) -> ClerkDecision:
    """为指定府路裁定本月官吏催科倾向。"""
    if not isinstance(prefecture, dict) or not prefecture:
        return ClerkDecision(mode="moderate", mult=1.00, mood_delta=0.0, note="空上下文默认常典")
    try:
        # 1. 提取客观情境特征（缺失一律 None，由引擎按 fail-closed 处理）
        mood_raw = prefecture.get("mood")
        unrest = None
        if mood_raw is not None and not isinstance(mood_raw, bool):
            try:
                unrest = max(0.0, min(100.0, 100.0 - float(mood_raw)))
            except (TypeError, ValueError):
                unrest = None

        disaster = _route_disaster(state, prefecture)

        # 知州属性（若该路有守臣）；**缺失不冒充 0.6**
        gov = prefecture.get("governor") or prefecture.get("official")
        gov = gov if isinstance(gov, dict) else {}
        integrity = gov.get("integrity")
        diligence = gov.get("diligence")

        # 财力：**路库优先**（催科是路级事务），其次才是国库
        local_treasury = prefecture.get("local_treasury")
        treasury = local_treasury if local_treasury is not None else getattr(state, "treasury", None)

        # 2. 上下文一律走 canonical facts（引擎只认登记键）
        facts = canonicalize({
            "unrest": unrest,
            "disaster": disaster,
            "integrity": integrity,
            "diligence": diligence,
            "local_treasury": local_treasury,
            "treasury": treasury,
        })
        ctx: Dict[str, Any] = to_engine_context(facts)

        # 3. 结构先验**只放**府库与民怨；吏治/灾情交给引擎 tax_stance 分支（不重复计入）
        fiscal_pressure = 0.0
        if treasury is not None:
            fiscal_pressure = 1.0 if float(treasury) < CLERK_FISCAL_TREASURY_MIN else 0.0
        criteria = {
            "strict": CRITERIA_STRICT_BASE + fiscal_pressure * CRITERIA_FISCAL_WEIGHT,
            "lenient": CRITERIA_LENIENT_BASE + (
                CRITERIA_UNREST_WEIGHT if (unrest is not None
                                           and unrest > CRITERIA_UNREST_THRESHOLD) else 0.0),
            "moderate": CRITERIA_MODERATE_BASE,
        }

        res = EmbeddedJevEngine.choose(
            state_context=ctx,
            instructions="裁定地方官吏催科严厉度",
            criteria=criteria,
            objective="tax_stance",
        )
        choice = res.get("verdict") or "moderate"

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
