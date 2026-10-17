# -*- coding: utf-8 -*-
"""大宋二十一路地脉矿藏储量、开采与铜煤真账（单一权威源）。

## 规格与背景（M313 / 玩家意志与工业革命前置底座）

针对《宋祚》长期以来矿产仅有静态 yields 抽象年额、缺失铜矿/石炭、
甚至铸钱曾被迫借用'铁'维度的根本痛点，本模块建立 21 路地脉矿藏实体：

1. **真实地脉矿藏（储量 Reserves 与月度开采上限 Capacity）**：
   - **铜矿（copper_ore）**：江南东路/江南西路（饶州德兴大铜矿、铅山胆水浸铜法）、河东路、福建路；
   - **石炭/焦煤（coal）**：河东路（太原/大同煤田）、河北路（磁州）、陕西路（永兴军石炭场）；
   - **铁矿（iron_ore）**：河北路、河东路、京东西路（徐州利国监）、福建路、江南西路；
   - **海井池盐（salt）**：河东解州池盐、两浙/淮东海盐、川峡井盐；
   - **林木（timber）与石料（stone）**：荆湖、川峡、两江之大山深林。

2. **双轨开采与朝廷课税（朝廷层 vs 系统层分离）**：
   - **系统层真账**：矿山实际储量逐月依开采量真实扣减（储量枯竭则产能自然归零），
     产出实物严格遵循质量守恒；
   - **朝廷层视界**：官办矿监产出全额上解太仓/官仓；民营坑冶（商贾承买/采户淘采）
     朝廷依规征收二分抽一的坑冶课税（矿课）。地方豪强瞒报私采受吏员把持度 grip 影响。

3. **铜料真账与铸钱并轨**：
   - 彻底提供标准的 `copper` 资源维度，为铸钱提供真实的物理铜料供给，
     告别以铁代铜。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "CIRCUIT_MINERAL_DEPOSITS",
    "init_circuit_minerals",
    "get_circuit_minerals",
    "extract_circuit_minerals",
    "derive_national_mineral_status",
    "DIM_COPPER",
    "DIM_COAL",
    "DIM_IRON",
    "DIM_SALT",
    "DIM_TIMBER",
    "DIM_STONE",
]

DIM_COPPER = "铜"
DIM_COAL = "coal"
DIM_IRON = "铁"
DIM_SALT = "盐"
DIM_TIMBER = "木"
DIM_STONE = "石"

#: 北宋 21 路真实地脉矿脉初始配置（初始储量 reserves 斤/根/方，月度基础开采上限 cap）
#: 史料基准：元丰年间坑冶课额、沈括《梦溪笔谈》、宋会要辑稿食货矿冶
CIRCUIT_MINERAL_DEPOSITS: Dict[str, Dict[str, Dict[str, float]]] = {
    "京畿路": {
        DIM_STONE: {"reserves": 50000000.0, "cap": 25000.0, "purity": 0.90},
        DIM_TIMBER: {"reserves": 20000000.0, "cap": 16000.0, "purity": 0.85},
    },
    "京西路": {
        DIM_IRON: {"reserves": 120000000.0, "cap": 42000.0, "purity": 0.65},
        DIM_COAL: {"reserves": 300000000.0, "cap": 60000.0, "purity": 0.80},
        DIM_STONE: {"reserves": 80000000.0, "cap": 42000.0, "purity": 0.90},
        DIM_TIMBER: {"reserves": 60000000.0, "cap": 42000.0, "purity": 0.90},
    },
    "京东东路": {
        DIM_IRON: {"reserves": 180000000.0, "cap": 83000.0, "purity": 0.70},
        DIM_SALT: {"reserves": 5000000000.0, "cap": 1600000.0, "purity": 0.95},
        DIM_STONE: {"reserves": 90000000.0, "cap": 33000.0, "purity": 0.90},
        DIM_TIMBER: {"reserves": 40000000.0, "cap": 25000.0, "purity": 0.85},
    },
    "京东西路": {
        # 徐州利国监（北宋最大铁冶枢纽之一）
        DIM_IRON: {"reserves": 250000000.0, "cap": 120000.0, "purity": 0.75},
        DIM_COAL: {"reserves": 200000000.0, "cap": 50000.0, "purity": 0.80},
        DIM_STONE: {"reserves": 60000000.0, "cap": 25000.0, "purity": 0.85},
        DIM_TIMBER: {"reserves": 30000000.0, "cap": 25000.0, "purity": 0.80},
    },
    "河北路": {
        # 磁州石炭、邢州铁冶
        DIM_IRON: {"reserves": 500000000.0, "cap": 290000.0, "purity": 0.75},
        DIM_COAL: {"reserves": 1500000000.0, "cap": 220000.0, "purity": 0.85},
        DIM_SALT: {"reserves": 3000000000.0, "cap": 1290000.0, "purity": 0.90},
        DIM_STONE: {"reserves": 120000000.0, "cap": 58000.0, "purity": 0.90},
        DIM_TIMBER: {"reserves": 50000000.0, "cap": 33000.0, "purity": 0.85},
    },
    "河东路": {
        # 解州池盐、太原大同优质石炭、晋城铁矿、河东铜山
        DIM_SALT: {"reserves": 8000000000.0, "cap": 5250000.0, "purity": 0.98},
        DIM_COAL: {"reserves": 3000000000.0, "cap": 350000.0, "purity": 0.90},
        DIM_IRON: {"reserves": 400000000.0, "cap": 210000.0, "purity": 0.75},
        DIM_COPPER: {"reserves": 80000000.0, "cap": 35000.0, "purity": 0.60},
        DIM_STONE: {"reserves": 150000000.0, "cap": 83000.0, "purity": 0.90},
        DIM_TIMBER: {"reserves": 90000000.0, "cap": 67000.0, "purity": 0.85},
    },
    "陕西路": {
        # 永兴军石炭场、凤翔木材、秦州石料
        DIM_COAL: {"reserves": 800000000.0, "cap": 120000.0, "purity": 0.80},
        DIM_IRON: {"reserves": 150000000.0, "cap": 42000.0, "purity": 0.65},
        DIM_SALT: {"reserves": 600000000.0, "cap": 240000.0, "purity": 0.85},
        DIM_TIMBER: {"reserves": 120000000.0, "cap": 50000.0, "purity": 0.90},
        DIM_STONE: {"reserves": 160000000.0, "cap": 83000.0, "purity": 0.90},
    },
    "两浙路": {
        # 两浙海盐甲天下、严州富春山林
        DIM_SALT: {"reserves": 6000000000.0, "cap": 1620000.0, "purity": 0.95},
        DIM_TIMBER: {"reserves": 180000000.0, "cap": 75000.0, "purity": 0.90},
        DIM_STONE: {"reserves": 90000000.0, "cap": 37500.0, "purity": 0.90},
    },
    "江南东路": {
        # 饶州德兴铜矿（天下第一大铜厂）、两淮海盐
        DIM_COPPER: {"reserves": 450000000.0, "cap": 280000.0, "purity": 0.80},
        DIM_SALT: {"reserves": 4000000000.0, "cap": 1050000.0, "purity": 0.92},
        DIM_TIMBER: {"reserves": 220000000.0, "cap": 100000.0, "purity": 0.92},
        DIM_STONE: {"reserves": 90000000.0, "cap": 33000.0, "purity": 0.90},
    },
    "江南西路": {
        # 信州铅山胆水浸铜、大余赣南铁山、大山林木
        DIM_COPPER: {"reserves": 350000000.0, "cap": 220000.0, "purity": 0.78},
        DIM_IRON: {"reserves": 220000000.0, "cap": 100000.0, "purity": 0.70},
        DIM_COAL: {"reserves": 250000000.0, "cap": 60000.0, "purity": 0.75},
        DIM_TIMBER: {"reserves": 300000000.0, "cap": 150000.0, "purity": 0.95},
        DIM_STONE: {"reserves": 100000000.0, "cap": 37500.0, "purity": 0.90},
    },
    "淮南东路": {
        DIM_SALT: {"reserves": 5500000000.0, "cap": 1620000.0, "purity": 0.95},
        DIM_TIMBER: {"reserves": 80000000.0, "cap": 42000.0, "purity": 0.85},
        DIM_STONE: {"reserves": 60000000.0, "cap": 25000.0, "purity": 0.85},
    },
    "淮南西路": {
        DIM_IRON: {"reserves": 80000000.0, "cap": 25000.0, "purity": 0.65},
        DIM_TIMBER: {"reserves": 100000000.0, "cap": 50000.0, "purity": 0.88},
        DIM_STONE: {"reserves": 70000000.0, "cap": 33000.0, "purity": 0.88},
    },
    "荆湖北路": {
        DIM_IRON: {"reserves": 90000000.0, "cap": 33000.0, "purity": 0.65},
        DIM_TIMBER: {"reserves": 260000000.0, "cap": 125000.0, "purity": 0.92},
        DIM_STONE: {"reserves": 90000000.0, "cap": 33000.0, "purity": 0.90},
    },
    "荆湖南路": {
        DIM_TIMBER: {"reserves": 320000000.0, "cap": 150000.0, "purity": 0.95},
        DIM_STONE: {"reserves": 90000000.0, "cap": 33000.0, "purity": 0.90},
        DIM_COPPER: {"reserves": 60000000.0, "cap": 20000.0, "purity": 0.65},
    },
    "福建路": {
        # 福建铜铁坑冶繁密、海盐兴盛
        DIM_COPPER: {"reserves": 120000000.0, "cap": 50000.0, "purity": 0.70},
        DIM_IRON: {"reserves": 180000000.0, "cap": 83000.0, "purity": 0.70},
        DIM_SALT: {"reserves": 2500000000.0, "cap": 640000.0, "purity": 0.92},
        DIM_TIMBER: {"reserves": 250000000.0, "cap": 125000.0, "purity": 0.95},
        DIM_STONE: {"reserves": 100000000.0, "cap": 42000.0, "purity": 0.90},
    },
    "成都府路": {
        # 川峡井盐、深山林石
        DIM_SALT: {"reserves": 1800000000.0, "cap": 483000.0, "purity": 0.90},
        DIM_TIMBER: {"reserves": 200000000.0, "cap": 100000.0, "purity": 0.92},
        DIM_STONE: {"reserves": 80000000.0, "cap": 29000.0, "purity": 0.90},
    },
    "利州路": {
        DIM_IRON: {"reserves": 100000000.0, "cap": 33000.0, "purity": 0.65},
        DIM_SALT: {"reserves": 500000000.0, "cap": 83000.0, "purity": 0.85},
        DIM_TIMBER: {"reserves": 180000000.0, "cap": 83000.0, "purity": 0.92},
        DIM_STONE: {"reserves": 90000000.0, "cap": 33000.0, "purity": 0.90},
    },
    "夔州路": {
        DIM_SALT: {"reserves": 800000000.0, "cap": 240000.0, "purity": 0.88},
        DIM_TIMBER: {"reserves": 250000000.0, "cap": 125000.0, "purity": 0.95},
        DIM_STONE: {"reserves": 100000000.0, "cap": 42000.0, "purity": 0.90},
    },
    "广南东路": {
        DIM_SALT: {"reserves": 2500000000.0, "cap": 640000.0, "purity": 0.92},
        DIM_TIMBER: {"reserves": 200000000.0, "cap": 100000.0, "purity": 0.90},
        DIM_STONE: {"reserves": 80000000.0, "cap": 33000.0, "purity": 0.90},
    },
    "广南西路": {
        DIM_IRON: {"reserves": 70000000.0, "cap": 25000.0, "purity": 0.65},
        DIM_SALT: {"reserves": 600000000.0, "cap": 158000.0, "purity": 0.85},
        DIM_TIMBER: {"reserves": 220000000.0, "cap": 125000.0, "purity": 0.92},
        DIM_STONE: {"reserves": 80000000.0, "cap": 33000.0, "purity": 0.90},
    },
}


def init_circuit_minerals(state) -> None:
    """初始化 21 路真实地脉矿藏结构（幂等，不覆盖现有存量）。"""
    if state is None:
        return
    minerals = getattr(state, "mineral_deposits", None)
    if not isinstance(minerals, dict):
        minerals = {}
        state.mineral_deposits = minerals

    for r, deposits in CIRCUIT_MINERAL_DEPOSITS.items():
        circuit_slot = minerals.setdefault(r, {})
        for dim, cfg in deposits.items():
            slot = circuit_slot.setdefault(dim, {})
            slot.setdefault("reserves", float(cfg["reserves"]))
            slot.setdefault("initial_reserves", float(cfg["reserves"]))
            slot.setdefault("cap", float(cfg["cap"]))
            slot.setdefault("purity", float(cfg["purity"]))
            slot.setdefault("extracted_total", 0.0)


def get_circuit_minerals(state, circuit: str) -> Dict[str, Dict[str, float]]:
    """读取某路的全部矿脉储量与开采状态。"""
    init_circuit_minerals(state)
    minerals = getattr(state, "mineral_deposits", {})
    return minerals.get(circuit, {})


def extract_circuit_minerals(
    state,
    circuit: str,
    rate_mult: float = 1.0,
    clerk_grip: float = 0.45,
) -> Dict[str, Dict[str, float]]:
    """月度开采地脉矿藏（受控写操作，依储量物理扣减并派生双轨账目）。

    返回开采明细：
    {
        dim: {
            "physical_extracted": float,  # 系统层物理真实开采量（严格扣减地脉储量）
            "gov_monopoly_share": float,  # 官营上解朝廷官仓量
            "market_private_share": float,# 民间流通量
            "tax_coin": float,            # 朝廷征收之坑冶课税现钱（二分抽一折钱）
            "remaining_reserves": float,  # 开采后地脉剩余真实储量
        }
    }
    """
    init_circuit_minerals(state)
    minerals = getattr(state, "mineral_deposits", {})
    c_mines = minerals.get(circuit, {})
    if not c_mines:
        return {}

    extracted_report: Dict[str, Dict[str, float]] = {}

    for dim, info in c_mines.items():
        res = float(info.get("reserves", 0.0) or 0.0)
        cap = float(info.get("cap", 0.0) or 0.0)
        purity = float(info.get("purity", 0.8) or 0.8)

        if res <= 0 or cap <= 0:
            extracted_report[dim] = {
                "physical_extracted": 0.0,
                "gov_monopoly_share": 0.0,
                "market_private_share": 0.0,
                "tax_coin": 0.0,
                "remaining_reserves": 0.0,
            }
            continue

        # 1. 系统层物理真实开采量（不能超过剩余储量）
        target_extract = cap * rate_mult
        actual_extract = min(res, target_extract)
        net_usable = actual_extract * purity

        # 扣减真实矿藏储量
        info["reserves"] = round(res - actual_extract, 1)
        info["extracted_total"] = round(float(info.get("extracted_total", 0.0)) + actual_extract, 1)

        # 2. 双轨分配与朝廷课税（官办 vs 民办分成，受吏员把持度 grip 影响）
        # 铜矿与海盐为大宋严厉专卖，官营上解比重大；石炭、铁矿、林木多有民采商办
        if dim in (DIM_COPPER, DIM_SALT):
            # 专卖重宗：官营占 70%，民间商贾包采 30%
            gov_share = net_usable * (0.80 - clerk_grip * 0.20)
            private_share = net_usable - gov_share
        else:
            # 煤、铁、木、石：官民兼采，官营 40%，民营 60%
            gov_share = net_usable * (0.50 - clerk_grip * 0.20)
            private_share = net_usable - gov_share

        # 朝廷课税（坑冶课/二分抽一，民营部分的 20% 折钱归朝廷）
        tax_coin = private_share * 0.20 * (1.0 - clerk_grip * 0.30)

        extracted_report[dim] = {
            "physical_extracted": round(net_usable, 1),
            "gov_monopoly_share": round(gov_share, 1),
            "market_private_share": round(private_share, 1),
            "tax_coin": round(tax_coin, 1),
            "remaining_reserves": info["reserves"],
        }

    return extracted_report


def derive_national_mineral_status(state) -> Dict[str, Any]:
    """派生全国矿藏储量与开采健康度总览（只读派生）。"""
    init_circuit_minerals(state)
    minerals = getattr(state, "mineral_deposits", {})

    totals: Dict[str, Dict[str, float]] = {}
    depleted_mines: List[str] = []

    for r, c_mines in minerals.items():
        for dim, info in c_mines.items():
            tot = totals.setdefault(dim, {"reserves": 0.0, "initial_reserves": 0.0, "monthly_cap": 0.0})
            res = float(info.get("reserves", 0.0) or 0.0)
            init_res = float(info.get("initial_reserves", 0.0) or 0.0)
            cap = float(info.get("cap", 0.0) or 0.0)
            tot["reserves"] += res
            tot["initial_reserves"] += init_res
            tot["monthly_cap"] += cap

            if init_res > 0 and res <= init_res * 0.05:
                depleted_mines.append(f"{r}:{dim}")

    return {
        "totals_by_dim": totals,
        "depleted_mines": depleted_mines,
        "depleted_count": len(depleted_mines),
    }
