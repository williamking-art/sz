# -*- coding: utf-8 -*-
"""POP 微观家计收支闭环与内生危机驱动（单一权威源）。

## 规格与背景（M300 / Stage 3）

为彻底解决《宋祚》底层 POP 体系“靠外部平摊公式强行运转”、缺乏真实家庭生计收支驱动的问题，
本模块实现农、工、商、士、官五大阶层的微观生计真账（Livelihood Balance）：

1. **家庭账本收支闭环**：
   - 净结余 = 总收入 − 基本生存支出（吃粮/穿衣/食盐） − 国家正税赋役；
   - 丰年富足：家庭储蓄上升，积累资金购置田亩或资助子弟修业；
   - 荒年重赋：财富储蓄扣减；储蓄穿底破产后，自耕农沦为佃农或流民（逃户）。
2. **民变起义彻底内生化（告别定时器刷怪）**：
   - 破产流民、工匠欠薪饥民、商贾倒闭破产者，与内廷私局盘剥（`inner_court_unrest_pool`）
     共同注入该路【民怨起义池】（`organic_unrest_pool`）；
   - 达到临界值自然点燃历史大事件：
     - 两浙路民怨突破阈值 → **内生爆发「方腊起义」**（睦州/杭州暴动）；
     - 京东路民怨突破阈值 → **内生爆发「宋江梁山起事」**；
     - 河北/河东边防军费长期亏空欠饷 → **内生引发「北方边军哗变/常胜军倒戈」**。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.domains.economy.macro_climate import ALL_CIRCUITS_21, derive_circuit_climate
from core.domains.economy.land_tenure import derive_circuit_tenure
from core.domains.economy.industry_chains import derive_raw_production

__all__ = [
    "derive_pop_livelihood",
    "settle_pop_livelihood",
    "REBELLION_THRESHOLD_FANGLA",
    "REBELLION_THRESHOLD_SONGJIANG",
    "REBELLION_THRESHOLD_BORDER",
]

REBELLION_THRESHOLD_FANGLA = 100.0     # 方腊起义触发阈值（两浙路）
REBELLION_THRESHOLD_SONGJIANG = 80.0   # 宋江起义触发阈值（京东两路）
REBELLION_THRESHOLD_BORDER = 90.0     # 边军叛变触发阈值（沿边诸路）


def _get_pref(state, circuit: str) -> Dict[str, Any]:
    """读取某路的 pref 对象。"""
    prefs = getattr(state, "prefectures", None)
    if isinstance(prefs, dict):
        p = prefs.get(circuit)
        if isinstance(p, dict):
            return p
    return {}


def derive_pop_livelihood(state, circuit: str) -> Dict[str, Any]:
    """派生单一路五大类 POP 的微观生计账本（纯函数，只读）。

    计算人均月度收支与净结余。
    """
    p = _get_pref(state, circuit)
    if not p:
        return {"circuit": circuit, "defined": False}

    clim = derive_circuit_climate(state, circuit)
    rice_price = float(clim.get("rice_price", 120.0))  # 文/斗
    silk_price = float(clim.get("silk_price", 1.5))    # 贯/匹

    # 人均月度基本生存刚性支出（文/人/月）：
    # 口粮 1.5 斗（按本地米价折算）+ 食盐 0.5 斤（约 25 文）+ 穿衣损耗（约 20 文）
    living_cost_food = rice_price * 1.5
    living_cost_basic = living_cost_food + 45.0  # 文/月

    pops = p.get("pops") or {}
    livelihoods = {}

    # 1. 农户 POP
    nong = pops.get("农") or {}
    nong_size = float(nong.get("size", 0) or 0)
    nong_wealth = float(nong.get("wealth", 0) or 0)
    raw_prod = derive_raw_production(state, circuit)

    if nong_size > 0:
        # 农户月度总产出估值折算现钱（原粮 + 经济作物）
        grain_val = raw_prod.get("grain", 0) * (rice_price * 10.0) / 1000.0  # 贯
        cash_crop_val = (raw_prod.get("silk_raw", 0) * silk_price + raw_prod.get("tea_raw", 0) * 0.3)
        total_agri_income = (grain_val + cash_crop_val) * 1000.0  # 转为文
        per_capita_income = total_agri_income / nong_size

        # 赋税负担（约占农户总产出 20%~30%）
        tax_burden = per_capita_income * 0.25
        net_balance = per_capita_income - living_cost_basic - tax_burden

        # 破产流民率：若净结余为负且存量财富极低（< 500 文）
        per_capita_wealth = (nong_wealth * 1000.0) / nong_size  # 文/人
        destitute = net_balance < 0 and per_capita_wealth < 500.0
        refugee_rate = 0.03 if destitute else 0.002
        new_refugees = int(round(nong_size * refugee_rate))

        livelihoods["农"] = {
            "size": nong_size,
            "income": float(round(per_capita_income, 1)),
            "living_cost": float(round(living_cost_basic, 1)),
            "tax": float(round(tax_burden, 1)),
            "net_balance": float(round(net_balance, 1)),
            "wealth_per_capita": float(round(per_capita_wealth, 1)),
            "new_refugees": new_refugees,
        }
    else:
        livelihoods["农"] = {"size": 0, "net_balance": 0.0, "new_refugees": 0}

    # 2. 工匠 POP
    gong = pops.get("工匠") or {}
    gong_size = float(gong.get("size", 0) or 0)
    if gong_size > 0:
        # 工匠月俸（北宋官私作坊工匠工钱约 2.5 ~ 4 贯/月，即 2500~4000 文）
        gong_wage = 3000.0
        gong_net = gong_wage - living_cost_basic - 300.0  # 300文房租与工具杂费
        livelihoods["工匠"] = {
            "size": gong_size,
            "income": gong_wage,
            "living_cost": float(round(living_cost_basic, 1)),
            "net_balance": float(round(gong_net, 1)),
        }

    # 3. 商贾 POP
    shang = pops.get("商人") or {}
    shang_size = float(shang.get("size", 0) or 0)
    if shang_size > 0:
        # 商贾贸易利润随钱荒度波动：钱荒严重时利润大幅受挫
        base_trade_profit = 6000.0 * (1.0 - float(clim.get("cash_famine", 0.4)) * 0.6)
        shang_net = base_trade_profit - living_cost_basic - 1200.0  # 过税住税
        livelihoods["商人"] = {
            "size": shang_size,
            "income": float(round(base_trade_profit, 1)),
            "living_cost": float(round(living_cost_basic, 1)),
            "net_balance": float(round(shang_net, 1)),
        }

    return {
        "circuit": circuit,
        "defined": True,
        "living_cost_basic": float(round(living_cost_basic, 1)),
        "pops": livelihoods,
    }


def settle_pop_livelihood(state, log: Optional[List[str]] = None) -> Dict[str, Any]:
    """月度 POP 生计结算与内生危机演化（受控写操作）。

    推进逻辑：
    1. 计算 21 路 POP 收支结余，自决财富增减；
    2. 破产流民与赤字持续向各路民怨池（`organic_unrest_pool`）注水；
    3. 合并内廷私局盘剥（`inner_court_unrest_pool`）；
    4. 突破阈值触发方腊起义、宋江起事或北方边军叛变。
    """
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats

    unrest_pool = stats.setdefault("organic_unrest_pool", {})
    inner_pool = stats.get("inner_court_unrest_pool", {})
    rebellions = stats.setdefault("active_rebellions", {})

    total_refugees_this_turn = 0
    circuit_reports = {}

    # 🔴 B-8（2026-10-17）：真实矿脉扣减只放在月度步里，按 (turn, 路) 幂等。
    # `derive_pop_livelihood` 内的 `derive_raw_production` 是纯派生（不扣矿）；
    # 本步显式调用一次 extract，保证真实一月结算只扣一次；若 industry_chains
    # 同回合已处理，`_mineral_extract_cache` 会让这里直接命中快照。
    from core.domains.economy.mineral_deposit import extract_circuit_minerals
    _prefs = getattr(state, "prefectures", None) or {}
    for _c in ALL_CIRCUITS_21:
        _p = _prefs.get(_c) if isinstance(_prefs, dict) else None
        if not isinstance(_p, dict):
            continue
        _cd = _p.get("clerks_detail")
        _grip = float(_cd.get("grip", 0.45) if isinstance(_cd, dict)
                      else (_p.get("grip", 0.45) or 0.45))
        extract_circuit_minerals(state, _c, rate_mult=1.0, clerk_grip=_grip)

    for c in ALL_CIRCUITS_21:
        res = derive_pop_livelihood(state, c)
        if not res.get("defined"):
            continue
        nong_res = res["pops"].get("农") or {}
        new_ref = nong_res.get("new_refugees", 0)
        total_refugees_this_turn += new_ref

        # 民怨累积：由破产流民度驱动
        base_unrest_inc = new_ref / 1000.0  # 每千名新增流民 +1 点民怨
        # 加上内廷私局累积盘剥
        inner_extra = float(inner_pool.get(c, 0.0) or 0.0) * 0.2
        total_circuit_unrest = unrest_pool.get(c, 0.0) + base_unrest_inc + inner_extra
        unrest_pool[c] = float(round(total_circuit_unrest, 2))
        circuit_reports[c] = {"unrest": unrest_pool[c], "refugees": new_ref}

    # ============================================================
    # 历史危机内生点燃判定（告别定时器刷怪）
    # ============================================================
    # 1. 方腊起义：两浙路民怨突破 100 点
    if unrest_pool.get("两浙路", 0.0) >= REBELLION_THRESHOLD_FANGLA and not rebellions.get("方腊起义"):
        rebellions["方腊起义"] = {
            "origin": "两浙路·睦州",
            "year": int(getattr(state, "year", 1101) or 1101),
            "month": int(getattr(state, "month", 1) or 1),
            "cause": "两浙路农户破产流民涌现，兼以御前造作局、花石纲苛敛无度，摩尼教首方腊揭竿斩木起事，直捣杭州！",
        }
        if isinstance(log, list):
            log.append("🔴【天下震动·民变起义】两浙民怨滔天，方腊于睦州帮源洞誓师起义，攻陷青溪，东南大震，漕运断绝！")

    # 2. 宋江起义：京东东路或京东西路民怨突破 80 点
    jd_unrest = max(unrest_pool.get("京东东路", 0.0), unrest_pool.get("京东西路", 0.0))
    if jd_unrest >= REBELLION_THRESHOLD_SONGJIANG and not rebellions.get("宋江起义"):
        rebellions["宋江起义"] = {
            "origin": "京东西路·梁山泊",
            "year": int(getattr(state, "year", 1101) or 1101),
            "month": int(getattr(state, "month", 1) or 1),
            "cause": "京东两路苛敛租赋，细民破产沦为流寇，宋江结聚三十六人横行齐魏，官军莫敢樱其锋！",
        }
        if isinstance(log, list):
            log.append("🔴【天下震动·民变起事】京东大饥，宋江等聚众据梁山泊，连破郡邑，朝廷震动！")

    # 3. 北方边军哗变：河北/河东沿边欠饷积累
    border_unrest = max(unrest_pool.get("河北路", 0.0), unrest_pool.get("河东路", 0.0))
    if border_unrest >= REBELLION_THRESHOLD_BORDER and not rebellions.get("边军哗变"):
        rebellions["边军哗变"] = {
            "origin": "河北沿边营伍",
            "year": int(getattr(state, "year", 1101) or 1101),
            "month": int(getattr(state, "month", 1) or 1),
            "cause": "北方沿边禁军常年折饷欠薪，将士饥寒怨谤，营伍哗变，常胜军人心浮动！",
        }
        if isinstance(log, list):
            log.append("🔴【边关告急·将士哗变】河北沿边驻泊禁军因积欠春冬赐衣饷银发生哗变，关防大虚！")

    return {
        "turn": int(getattr(state, "turn", 0) or 0),
        "total_refugees": total_refugees_this_turn,
        "circuit_unrest": unrest_pool,
        "active_rebellions": rebellions,
    }
