# -*- coding: utf-8 -*-
"""大宋二十一路荒地池、官方屯田与民间自发垦荒双轨模型（单一权威源）。

## 规格与背景（M313 / 玩家意志与土地内生化闭环）

针对现代玩家在推进治国与工业化过程中，必将推行大规模垦荒的要求，
本模块建立官方屯田营田与民间自发辟荒的双轨动力学：

1. **二十一路荒地池（wasteland）**：
   - 历史事实：宋代并非全境熟田，北方边陲（河北/河东/陕西）有大量旷土荒原，
     南方（两江/荆湖/两淮/两广/闽峡）有大量草荡、湖滩、山荒待辟。
   - 严格守恒：开垦土地必定来源于荒地池，`wasteland` 减少，熟田增加。

2. **官方垦荒 vs 民间自发垦荒（双轨产权与账目差异）**：
   - **官方垦荒（Government Reclamation）**：
     - 来源：玩家降旨屯田营田、工部/转运司出资兴修圩田陂塘、招抚流民垦殖；
     - 资金：由国库 `treasury` 或内帑 `imperial_treasury` 真实拨款买耕牛、给种粮；
     - 产权归属：计入官田/屯田（`guan_tian`）；
     - 收益：产粮全额纳租上解朝廷太仓。朝廷完全知情，账目清晰。
   - **民间自发垦荒（Civilian Spontaneous Reclamation）**：
     - 动力：人口增长、人地矛盾加剧、粮价高涨带来暴利、或轻徭薄赋激发农民积极性；
     - 资金与劳力：民间农户 POP 自行出资投劳，或流民自耕自垦；
     - 产权归属：自耕农自垦归民田（`min_tian`）；豪强占山围湖盗垦则沦为庄园隐田（`yin_tian`）；
     - 朝廷账目：地方官吏与豪强勾结隐瞒，朝廷只能得到带漏报率的模糊申报，绝大多数被瞒报逃税。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from content.data_geo_tables import PREFECTURE_INFO
from core.domains.economy.land_tenure import derive_circuit_tenure
from core.domains.economy.macro_climate import ALL_CIRCUITS_21

log = logging.getLogger(__name__)

__all__ = [
    "CIRCUIT_WASTELAND_BASE",
    "init_circuit_wasteland",
    "get_circuit_wasteland",
    "reclaim_land_government",
    "reclaim_land_civilian_spontaneous",
    "derive_national_reclamation_summary",
]

#: 21 路初始可开垦荒地池（亩）。北方边陲与南方荒山湿地潜力巨大
CIRCUIT_WASTELAND_BASE: Dict[str, float] = {
    "京畿路": 4500000.0,
    "京西路": 7200000.0,
    "京东东路": 6800000.0,
    "京东西路": 5900000.0,
    "河北路": 16000000.0,
    "河东路": 11000000.0,
    "陕西路": 15000000.0,
    "两浙路": 8500000.0,    # 围湖造田、海涂圩田
    "江南东路": 9500000.0,   # 圩田、山林坡地
    "江南西路": 12000000.0,  # 赣水流域梯田与草荡
    "淮南东路": 8000000.0,   # 滨海荡地
    "淮南西路": 7500000.0,
    "荆湖北路": 11000000.0,  # 洞庭湖围垸圩田
    "荆湖南路": 13000000.0,  # 湘江流域蛮荒山谷
    "福建路": 6000000.0,    # 梯田海涂
    "成都府路": 5500000.0,
    "利州路": 4800000.0,
    "夔州路": 5200000.0,
    "广南东路": 10500000.0,
    "广南西路": 9800000.0,
}


def init_circuit_wasteland(state) -> None:
    """初始化 21 路荒地池（幂等）。"""
    if state is None:
        return
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return

    for r in ALL_CIRCUITS_21:
        if r not in prefs:
            continue
        p = prefs[r]
        if "wasteland" not in p or p["wasteland"] is None:
            base_w = CIRCUIT_WASTELAND_BASE.get(r, 6000000.0)
            p["wasteland"] = float(base_w)


def get_circuit_wasteland(state, circuit: str) -> float:
    """获取某路当前可开垦荒地存量（亩）。"""
    init_circuit_wasteland(state)
    prefs = getattr(state, "prefectures", {})
    p = prefs.get(circuit, {})
    return float(p.get("wasteland", 0.0) or 0.0)


def reclaim_land_government(
    state,
    circuit: str,
    target_mu: float,
    silver_funding: float,
    labor_corvee: int = 0,
) -> Dict[str, Any]:
    """官方屯田垦荒（由朝廷下旨出资与派役组织，受控写操作）。

    - 消耗：国库拨款（每开垦 1 亩荒地需折银约 0.8 贯作为牛具、农具与种子费）；
    - 来源：扣减 `p["wasteland"]`；
    - 去向：落入官田 `p["guan_tian"]` 或 `p["land"]` 增量；
    - 账目：朝廷全额知情，产粮直接补充官仓太仓。
    """
    init_circuit_wasteland(state)
    prefs = getattr(state, "prefectures", {})
    p = prefs.get(circuit)
    if not p:
        return {"ok": False, "reason": f"未找到该路：{circuit}"}

    avail_w = float(p.get("wasteland", 0.0) or 0.0)
    if avail_w <= 0:
        return {"ok": False, "reason": "该路已无荒地可供官方垦殖", "reclaimed_mu": 0}

    # 资金与劳力制约（每亩基础垦造工本 0.8 贯）
    mu_by_fund = silver_funding / 0.8 if silver_funding > 0 else 0
    actual_mu = min(target_mu, avail_w, mu_by_fund)
    actual_mu = round(actual_mu, 1)

    if actual_mu <= 0:
        return {"ok": False, "reason": "拨款不足或目标亩数为零", "reclaimed_mu": 0}

    cost_silver = int(round(actual_mu * 0.8))

    # 1. 扣减荒地池，增加该路土地
    p["wasteland"] = round(avail_w - actual_mu, 1)
    p["land"] = float(p.get("land", 0.0) or 0.0) + actual_mu
    p["guan_tian"] = float(p.get("guan_tian", 0.0) or 0.0) + actual_mu

    # 2. 真实扣减朝廷国库
    cur_t = float(getattr(state, "treasury", 0.0) or 0.0)
    state.treasury = int(round(max(0.0, cur_t - cost_silver)))

    return {
        "ok": True,
        "circuit": circuit,
        "reclaimed_mu": actual_mu,
        "cost_silver": cost_silver,
        "target_tenure": "guan_tian",
        "remaining_wasteland": p["wasteland"],
    }


def reclaim_land_civilian_spontaneous(
    state,
    circuit: str,
    clerk_grip: float = 0.45,
    grain_price: float = 1.0,
) -> Dict[str, Any]:
    """民间自发垦荒（月度根据人口压力、粮价刺激与流民动力自发开垦）。

    - 动力：粮价越高（>1.2）或农民人数越多，辟荒动力越强；
    - 来源：扣减 `p["wasteland"]`；
    - 去向分化（受豪强隐占与吏治把持度影响）：
      - 自耕农私垦（民田 `min_tian`）：占比 1.0 - (0.35 + grip * 0.35)；
      - 豪强强占隐匿（庄园隐田 `yin_tian`）：占比 0.35 + grip * 0.35；
    - 朝廷视界：朝廷仅能获得地方奏报中带漏报率的估算区间。
    """
    init_circuit_wasteland(state)
    prefs = getattr(state, "prefectures", {})
    p = prefs.get(circuit)
    if not p:
        return {"reclaimed_total": 0.0}

    avail_w = float(p.get("wasteland", 0.0) or 0.0)
    if avail_w <= 0:
        return {"reclaimed_total": 0.0}

    # 读取农户人口规模
    pops = p.get("pops", {})
    nong_pop = pops.get("农", {}) if isinstance(pops, dict) else {}
    nong_size = int(nong_pop.get("size", 0) or 0)

    if nong_size <= 0:
        return {"reclaimed_total": 0.0}

    # 自发开垦基础速率：每万丁农户每月辟荒 120 亩，受粮价刺激
    price_factor = max(0.5, min(2.5, grain_price / 1.0))
    spontaneous_mu = (nong_size / 10000.0) * 120.0 * price_factor
    actual_mu = min(avail_w, round(spontaneous_mu, 1))

    if actual_mu <= 0:
        return {"reclaimed_total": 0.0}

    # 荒地转化为耕地
    p["wasteland"] = round(avail_w - actual_mu, 1)
    p["land"] = float(p.get("land", 0.0) or 0.0) + actual_mu

    # 分流：自耕农入籍民田 vs 豪强侵占入隐田
    yin_ratio = max(0.20, min(0.70, 0.30 + clerk_grip * 0.40))
    yin_mu = round(actual_mu * yin_ratio, 1)
    min_mu = round(actual_mu - yin_mu, 1)

    p["min_tian"] = float(p.get("min_tian", 0.0) or 0.0) + min_mu
    p["yin_tian"] = float(p.get("yin_tian", 0.0) or 0.0) + yin_mu

    # 朝廷奏报申报估算（隐田部分大多被隐匿）
    reported_mu_est = round(min_mu * (1.0 - clerk_grip * 0.20), 1)

    return {
        "circuit": circuit,
        "reclaimed_total": actual_mu,
        "to_min_tian": min_mu,
        "to_yin_tian": yin_mu,
        "reported_to_court_est": reported_mu_est,
        "concealment_rate": round(yin_mu / actual_mu, 3),
        "remaining_wasteland": p["wasteland"],
    }


def derive_national_reclamation_summary(state) -> Dict[str, Any]:
    """全国垦荒潜力与各路荒地汇总（只读派生）。"""
    init_circuit_wasteland(state)
    prefs = getattr(state, "prefectures", {})

    total_w = 0.0
    by_circuit: Dict[str, float] = {}
    for r in ALL_CIRCUITS_21:
        p = prefs.get(r, {})
        w = float(p.get("wasteland", 0.0) or 0.0)
        total_w += w
        by_circuit[r] = w

    return {
        "total_national_wasteland": round(total_w, 1),
        "by_circuit": by_circuit,
        "circuits_covered": len(by_circuit),
    }
