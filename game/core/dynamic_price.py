# -*- coding: utf-8 -*-
"""宋祚 · 动态价格 + 物流分账（批 7 · 外邦省域产业链设计 §8/§9）。

**动态价格**（§8.1）：
  商品价 = 基准价 × clamp(demand/supply, 0.5, 1.5)；月度涨跌上限 ±20%。
  意愿需求用**上月价**算（一元延迟）；供给 = 仓存量 + 本月产量。

**物流分账**（§9）：
  运费是钱、跟距离地理相关；民间账（商路：POP→POP）/ 政府账（官路：treasury→POP）。
  运费 > 价差 → 不运（摩擦下限，§8.2/§9.4）。

纪律：
- 金属 ≠ 钱（§4.3）：金/银/铜/铁是实物存量，不得自动折算 treasury；
- 运费守恒：付费方 wealth −N、承运方 wealth +N（民间）或 treasury −N、承运方 +N（政府）；
- 整数尾差归最大付费/承运方；`logistics_abandoned` 记放弃调拨。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

__all__ = ["update_goods_prices", "logistics_rate", "civil_logistics",
           "gov_logistics", "LOGISTICS_TIERS"]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def update_goods_prices(prev_prices: Dict[str, float], demand: Dict[str, float],
                        supply: Dict[str, float], produced: Dict[str, float],
                        cfg: dict) -> Dict[str, float]:
    """动态商品价（§8.1）：基准价 × clamp(demand/supply, 0.5, 1.5)，月涨跌 ≤ ±20%。

    - `demand` 用**上月价**算（调用侧负责一元延迟）；
    - `supply` = 仓存量 + `produced`（本月产量）；
    - 返回 `{good: 新价}`；缺基准价的 good 跳过（不编造）。
    """
    base_tbl = cfg.get("GOODS_BASE_PRICE") or {}
    band = cfg.get("PRICE_BAND") or (0.5, 1.5)
    lo, hi = float(band[0]), float(band[1])
    month_cap = float(cfg.get("PRICE_MONTH_CAP", 0.20))
    out: Dict[str, float] = {}
    for g, base in base_tbl.items():
        d = float(demand.get(g, 0) or 0)
        s = float(supply.get(g, 0) or 0) + float(produced.get(g, 0) or 0)
        if s <= 0:
            ratio = hi   # 供给为 0 → 价格上限
        else:
            ratio = d / s if d > 0 else lo
        target = float(base) * _clamp(ratio, lo, hi)
        prev = float(prev_prices.get(g, base) or base)
        # 月度涨跌上限 ±20%
        delta = _clamp(target - prev, -prev * month_cap, prev * month_cap)
        out[g] = round(prev + delta, 4)
    return out


# 物流费率档位（§9.1）：贯/万单位/趟（阈值为距离上限）
LOGISTICS_TIERS: Tuple[Tuple[float, float], ...] = (
    (50.0, 0.5),           # 州/府内（≤50km）
    (300.0, 1.5),          # ≤300km
    (1000.0, 3.0),         # 300–1000km
    (3000.0, 6.0),         # 1000–3000km
    (float("inf"), 10.0),  # >3000km
)


def logistics_rate(distance_km: float, terrain: str = "平川",
                   at_war: bool = False, cfg: Optional[dict] = None) -> float:
    """单位物流费率（贯/万单位/趟）= 距离档位 × 地形 × 战乱。"""
    base = 10.0
    for thr, rate in LOGISTICS_TIERS:
        if distance_km <= thr:
            base = rate
            break
    if cfg:
        t_tbl = cfg.get("TERRAIN_MULT") or {}
        base *= float(t_tbl.get(terrain, 1.0))
        if at_war:
            base *= float(cfg.get("WAR_MULT", 1.5))
    return base


def civil_logistics(buyer_pop: dict, seller_merchant_pop: dict,
                    quantity: int, distance_km: float,
                    terrain: str = "平川", at_war: bool = False,
                    cfg: Optional[dict] = None) -> Dict[str, int]:
    """民间账（商路）：求购方 POP wealth → 货源方商人 POP wealth（不碰 treasury）。

    运费 = quantity/万 × 费率(distance)；付不起 → 放弃调拨（`abandoned=True`）。
    返回 `{fee, abandoned}`；运费守恒（buyer −fee、merchant +fee）。
    """
    rate = logistics_rate(distance_km, terrain, at_war, cfg)
    fee = max(1, int(quantity / 10000.0 * rate))
    buyer_wealth = int(buyer_pop.get("wealth", 0) or 0)
    if buyer_wealth < fee:
        return {"fee": 0, "abandoned": True}
    buyer_pop["wealth"] = buyer_wealth - fee
    seller_merchant_pop["wealth"] = int(seller_merchant_pop.get("wealth", 0) or 0) + fee
    return {"fee": fee, "abandoned": False}


def gov_logistics(treasury: dict, carrier_pop: dict,
                  quantity: int, distance_km: float,
                  terrain: str = "平川", at_war: bool = False,
                  cfg: Optional[dict] = None) -> Dict[str, int]:
    """政府账（官路/漕运）：政权 treasury → 起运州/府工匠/商人 POP（§9.3）。

    标的首期为军粮/禄米；运费 = quantity/万 × 费率(distance)。
    返回 `{fee, abandoned}`；treasury 不足 → 放弃（不 burn）。
    """
    rate = logistics_rate(distance_km, terrain, at_war, cfg)
    fee = max(1, int(quantity / 10000.0 * rate))
    t_amt = int(treasury.get("amount", 0) or 0) if isinstance(treasury, dict) else 0
    if t_amt < fee:
        return {"fee": 0, "abandoned": True}
    if isinstance(treasury, dict):
        treasury["amount"] = t_amt - fee
    carrier_pop["wealth"] = int(carrier_pop.get("wealth", 0) or 0) + fee
    return {"fee": fee, "abandoned": False}
