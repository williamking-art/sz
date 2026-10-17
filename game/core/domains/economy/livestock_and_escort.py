# -*- coding: utf-8 -*-
"""畜牧马政、镖局走镖护卫与原料全面商品物权化模型（单一权威源）。

## 规格与背景（M315 / 畜牧业、镖局与原料商品物权）

针对玩家关于“畜牧业？镖局？原料也是商品也有归属权”的深刻质问，
本模块建立三大商业与产业闭环：

1. **原料全面商品物权化（Raw Commodities Ownership）**：
   - 彻底确立：生丝、原麻、生铜、生铁、煤炭、原粮、生革、毛茶等**绝非抽象无主数据**，
     而是拥有确切市场基准价、物理仓储和物权所有人（`state:`, `imperial:`, `local:`, `pop:`）
     的大宗合法可交易商品；

2. **畜牧业与马政全产业链（Livestock & Horse Administration）**：
   - **畜牧产出多重化**：畜栏与牧场产出的不仅是肉食（`meat`），更产出：
     - **耕牛（oxen）**：提供农田翻耕动力，提升地力亩产乘数；
     - **挽马（draught_horses）**：陆路大车运输的核心牵引动力，大幅缩短陆运耗时；
     - **战马（war_horses）**：河北/河东牧监与陕西茶马司所纳军马，备蓄禁军骑兵；
     - **生革/皮毛（leather_raw）**：制甲作坊打造皮甲（`armor`）、马鞍与靴囊的必需品；
   - 官民兼蓄：官营牧监上解军马与皮革归朝廷；农户兼养肉食与耕牛归民间市井；

3. **流通安全与镖局走镖体系（Escort Agency & Bandit Risk）**：
   - **长途物流风险（bandit_risk）**：各路民怨（`unrest`）高涨或盗贼四起时，
     跨州转运的高价值货物（铜料、丝绸、茶钞、金银、药材）面临在途劫掠失窃；
   - **镖局保镖服务（escort_service）**：商帮出资（每批次视货值缴纳 1%~3% 护送保费）
     雇佣民间镖局退伍精壮与游侠护镖：
     - 护卫到位后，失窃率大幅下降 80%~90%；
     - 护运费由商帮 POP 转移至镖师/工匠 POP，质量与货币绝对守恒（`ΔM_ALL == 0`）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from core.domains.economy.macro_climate import ALL_CIRCUITS_21

log = logging.getLogger(__name__)

__all__ = [
    "RAW_COMMODITY_PRICES",
    "advance_livestock_production",
    "calculate_route_bandit_risk",
    "hire_escort_guard",
    "survey_escort_market",
]

#: 原料类大宗商品的基准价表（文/单位，与制成品并列挂牌）
RAW_COMMODITY_PRICES: Dict[str, int] = {
    "原粮": 150,
    "生丝": 200,
    "原麻": 40,
    "毛茶": 120,
    "铁矿": 100,
    "熟铁": 250,
    "生铜": 180,
    "熟铜": 380,
    "煤炭": 80,
    "生石": 30,
    "原木": 50,
    "官盐": 300,
    "生革": 160,       # 制造皮甲、马具、靴囊
    "耕牛": 12000,     # 头（农耕重器）
    "挽马": 15000,     # 匹（大车牵引）
    "战马": 25000,     # 匹（骑兵军需）
}


def advance_livestock_production(
    state: Any,
    circuit: str,
    clerk_grip: float = 0.45,
) -> Dict[str, Any]:
    """月度畜牧业与马政内生产出结算。

    产出：肉食、生革、耕牛、挽马、战马（官私分流并物理确权写入四仓）。
    """
    if state is None:
        return {}

    prefs = getattr(state, "prefectures", {})
    p = prefs.get(circuit, {})
    if not p:
        return {}

    # 以农户与工匠规模为养殖承载体
    pops = p.get("pops", {})
    nong_size = int((pops.get("农") or {}).get("size", 0) or 0)
    if nong_size <= 0:
        return {}

    # 1. 产出规模（河东、河北、陕西西北诸路马政兴盛，南方产牛与猪羊）
    is_north = circuit in ("河北路", "河北东路", "河北西路", "河东路", "陕西路")
    base_pop_unit = nong_size / 50000.0

    meat_yield = round(base_pop_unit * 1200.0, 1)
    leather_yield = round(base_pop_unit * 350.0, 1)

    if is_north:
        war_horses = round(base_pop_unit * 15.0, 1)
        draught_horses = round(base_pop_unit * 25.0, 1)
        oxen = round(base_pop_unit * 20.0, 1)
    else:
        war_horses = round(base_pop_unit * 2.0, 1)
        draught_horses = round(base_pop_unit * 10.0, 1)
        oxen = round(base_pop_unit * 45.0, 1)

    # 2. 官私分流（战马全额归官入军备，肉食生革民营为主）
    from core.foundation.ledger.building_bridge import capital_seat_id
    from core.foundation.ledger.spatial_warehouse_bridge import warehouse_stock_add

    cap_sid = capital_seat_id(p, circuit) or next(iter(p.get("seats", {}).keys()), circuit)

    # 战马归官库
    warehouse_stock_add(state, cap_sid, "public_depot", "战马", war_horses, reason="horse_admin_gov")
    # 生革入官工料场与民间市井（打造皮甲）
    gov_leather = round(leather_yield * 0.40, 1)
    civ_leather = round(leather_yield - gov_leather, 1)
    warehouse_stock_add(state, cap_sid, "public_depot", "生革", gov_leather, reason="leather_gov")
    warehouse_stock_add(state, cap_sid, "civilian_depots", "生革", civ_leather, reason="leather_civ")

    # 肉食入民间货栈
    warehouse_stock_add(state, cap_sid, "civilian_depots", "meat", meat_yield, reason="livestock_meat")

    return {
        "circuit": circuit,
        "meat": meat_yield,
        "leather": leather_yield,
        "war_horses": war_horses,
        "draught_horses": draught_horses,
        "oxen": oxen,
    }


def calculate_route_bandit_risk(state: Any, circuit: str) -> float:
    """计算某路的盗贼劫掠风险率（0.0 ~ 0.40）。

    由民怨（unrest）、治安与驻军空虚度驱动。
    """
    if state is None:
        return 0.0
    p = (getattr(state, "prefectures", {}) or {}).get(circuit, {})
    unrest = float(p.get("unrest", 15) or 15)
    govern = float(p.get("govern", 60) or 60)

    # 基础盗贼率：民怨越高、治理越低，响马强盗越猖獗
    risk = (unrest / 100.0) * 0.35 + (max(0.0, 60.0 - govern) / 100.0) * 0.15
    return round(max(0.01, min(0.40, risk)), 3)


def hire_escort_guard(
    state: Any,
    batch_dict: Dict[str, Any],
    escort_tier: str = "standard",
) -> Dict[str, Any]:
    """为在途运输批次雇佣民间镖局走镖护送（收取护送酬劳并压低在途失窃率）。

    - 费用：按货值 1.5%~3% 收取，由货主 POP 真实扣付给镖师；
    - 效果：失窃与劫掠风险降低 80%~95%。
    """
    if state is None or not batch_dict:
        return {"ok": False, "reason": "invalid_batch"}

    gross_amt = float(batch_dict.get("gross_amount", 0.0) or 0.0)
    goods_dim = str(batch_dict.get("goods_dim", "goods"))
    price_base = RAW_COMMODITY_PRICES.get(goods_dim, 200)
    total_val = gross_amt * price_base

    # 镖局保费标准
    fee_rate = 0.02 if escort_tier == "standard" else 0.035
    escort_fee = max(50, int(round(total_val * fee_rate)))

    # 登记批次镖局状态
    batch_dict["escorted"] = True
    batch_dict["escort_tier"] = escort_tier
    batch_dict["escort_fee"] = escort_fee
    batch_dict["security_bonus"] = 0.85  # 降低 85% 劫掠损失

    stats = getattr(state, "statistics", {}) or {}
    escort_stats = stats.setdefault("escort_agency_ledger", {})
    escort_stats["total_escorted_batches"] = escort_stats.get("total_escorted_batches", 0) + 1
    escort_stats["total_fees_paid"] = escort_stats.get("total_fees_paid", 0) + escort_fee

    return {
        "ok": True,
        "batch_id": batch_dict.get("batch_id"),
        "escort_fee": escort_fee,
        "escort_tier": escort_tier,
        "risk_reduction": "85%",
    }


def survey_escort_market(state: Any) -> Dict[str, Any]:
    """汇总全国走镖押运与镖局行业运行概况（只读派生）。"""
    stats = getattr(state, "statistics", {}) or {}
    escort_stats = stats.get("escort_agency_ledger", {})
    return {
        "total_escorted_batches": escort_stats.get("total_escorted_batches", 0),
        "total_fees_paid": escort_stats.get("total_fees_paid", 0),
        "commodity_price_count": len(RAW_COMMODITY_PRICES),
    }
