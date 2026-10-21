# -*- coding: utf-8 -*-
"""本地 Agent 决策（第一片：仓廪/漕运）—— 用程序+天道替代一次 LLM 往返。

只降低推演 token，不改变数值口径：
- 输入仍是 state（与 `granary_decide` 同源读数）；
- 输出仍是契约要求的三态/四态档位 + 短叙事；
- 默认关闭（`SONGZUO_LOCAL_AGENTS=1` 才启用），失败/缺读数 ⇒ 返回 None，调用方回落 LLM。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

__all__ = ["local_agents_enabled", "local_granary_decide", "local_decide"]

TIERS4 = ("微", "小", "中", "大")
LOSS_TIERS = ("无", "轻", "中", "重")


def local_agents_enabled() -> bool:
    return str(os.environ.get("SONGZUO_LOCAL_AGENTS", "")).strip().lower() in ("1", "true", "yes", "on")


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _tier_by_cut(v: Optional[float], cuts) -> str:
    if v is None:
        return "小"
    for limit, tier in cuts:
        if v <= limit:
            return tier
    return "大"


def local_granary_decide(state: Any) -> Optional[Dict[str, Any]]:
    """确定性仓廪档位；读数严重缺失时返回 None（交给 LLM/旧路径）。"""
    if state is None:
        return None
    granary = _num(getattr(state, "granary", None))
    cap = _num(getattr(state, "granary_cap", None))
    block = _num(getattr(state, "canal_block", None)) or 0.0
    disaster = _num(getattr(state, "disaster_severity", None)) or 0.0
    month = int(getattr(state, "month", 1) or 1)
    prefs = getattr(state, "prefectures", None) or {}
    unrest = 0.0
    prices = []
    for p in prefs.values() if isinstance(prefs, dict) else ():
        if not isinstance(p, dict):
            continue
        u = _num(p.get("unrest"))
        if u is not None:
            unrest = max(unrest, u)
        gp = _num(p.get("grain_price"))
        if gp is not None:
            prices.append(gp)

    # 漕运运期（3/6/9 月）且淤积低 ⇒ 入仓大；否则按淤积降档
    if month in (3, 6, 9) and block < 30:
        inflow = "大"
    else:
        inflow = _tier_by_cut(block, ((20, "中"), (50, "小"), (80, "微")))
    # 发仓：灾情/民怨/仓存低 ⇒ 出仓大
    pressure = max(disaster, min(100.0, unrest) / 20.0)
    if granary is not None and cap and cap > 0:
        ratio = granary / cap
        pressure = max(pressure, 1.0 - max(0.0, min(1.0, ratio)))
    outflow = "大" if pressure >= 3 else ("中" if pressure >= 1.5 else "小")
    # 平粜：粮价高于基准或灾情明显时加大
    base_price = _num(getattr(state, "grain_price", None))
    avg_price = (sum(prices) / len(prices)) if prices else None
    price_ratio = (avg_price / base_price) if (avg_price and base_price and base_price > 0) else None
    if price_ratio is None:
        price_stabilize = "中" if disaster > 0 else "小"
    elif price_ratio >= 1.5:
        price_stabilize = "大"
    elif price_ratio >= 1.2:
        price_stabilize = "中"
    else:
        price_stabilize = "小"
    # 军粮：驻军多/边事紧 ⇒ 大（用军费/兵力近似；缺失不臆造）
    troops = 0
    for u in (getattr(state, "army_units", None) or []):
        try:
            troops += int(getattr(u, "troops", 0) or 0)
        except Exception:  # noqa: BLE001
            continue
    army_supply = "大" if troops >= 200_000 else ("中" if troops >= 80_000 else "小")
    # 仓储损耗：天道/程序档位（灾/贪腐重 ⇒ 重；监察强 ⇒ 轻；默认中）
    corruption = getattr(state, "corruption", None)
    avg_corr = 0.0
    if isinstance(corruption, dict) and corruption:
        vals = [float(v) for v in corruption.values() if isinstance(v, (int, float))]
        avg_corr = sum(vals) / len(vals) if vals else 0.0
    if disaster >= 3 or avg_corr >= 0.6:
        storage_loss = "重"
    elif disaster <= 0 and avg_corr <= 0.2:
        storage_loss = "轻"
    else:
        storage_loss = "中"

    return {
        "granary": {"inflow": inflow, "outflow": outflow,
                    "price_stabilize": price_stabilize,
                    "army_supply": army_supply, "storage_loss": storage_loss},
        "narrative": "本地仓漕推演：%s入仓、%s发仓、平粜%s、军粮%s、仓储%s。" % (
            inflow, outflow, price_stabilize, army_supply, storage_loss),
        "_source": "local_tiandao",
    }


_LOCAL = {"granary": local_granary_decide}


def local_decide(agent_id: str, state: Any) -> Optional[Dict[str, Any]]:
    fn = _LOCAL.get(str(agent_id))
    if fn is None or not local_agents_enabled():
        return None
    try:
        return fn(state)
    except Exception:  # noqa: BLE001 —— 本地失败必须回落 LLM/旧路径
        import logging
        logging.getLogger("local_agent").warning("本地 %s 决策失败", agent_id, exc_info=True)
        return None
