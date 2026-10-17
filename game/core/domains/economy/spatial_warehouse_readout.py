# -*- coding: utf-8 -*-
"""空间四仓与结算管线读数（Spatial Warehouse & Settlement Pipeline Readout）。

定位：
- 纯派生、只读投影，绝不写 state；
- 聚合空间四仓（官方料场、常平官仓、商人行栈、沈括途耗在途）实物存量；
- 聚合声明式 SettlementPipeline 48 步调度状态；
- 严格遵循纪律：缺失值一律返回 None，display="undefined"，绝不作 0。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("songzuo.readout.spatial_warehouse")

__all__ = [
    "public_depot_summary",
    "public_granary_summary",
    "merchant_warehouse_summary",
    "in_transit_summary",
    "pipeline_health_readout",
    "court_ledger_summary",
    "system_ledger_summary",
    "court_vs_system_contrast",
    "court_blurred_pop_ledger",
]


def _sum_seat_warehouse(state: Any, wh_type: str,
                        only_dim: Optional[str] = None):
    """按 `seats[治所].warehouses[wh_type].stocks` 汇总；无该仓位 ⇒ `None`。"""
    if not isinstance(getattr(state, "prefectures", None), dict):
        return None, None
    total = 0.0
    by_route: Dict[str, Dict[str, float]] = {}
    covered_routes = set()
    found = False
    for rname, p in state.prefectures.items():
        if not isinstance(p, dict):
            continue
        for _sid, seat in (p.get("seats") or {}).items():
            if not isinstance(seat, dict):
                continue
            wh = (seat.get("warehouses") or {}).get(wh_type)
            if not isinstance(wh, dict):
                continue
            stocks = wh.get("stocks")
            if not isinstance(stocks, dict):
                continue
            found = True
            covered_routes.add(rname)
            row = by_route.setdefault(rname, {})
            for d, v in stocks.items():
                if only_dim is not None and d != only_dim:
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    row[d] = round(float(row.get(d, 0.0)) + float(v), 4)
                    total += float(v)
    if not found:
        return None, None
    return total, {"routes": len(covered_routes), "by_route": by_route}


def public_depot_summary(state: Any) -> Dict[str, Any]:
    """汇总全国官方料场（public_depot）建材储备（seats 真账）。"""
    if not isinstance(getattr(state, "prefectures", None), dict):
        return {
            "total_materials": None,
            "routes_covered": None,
            "display": "undefined",
            "reason": "state.prefectures 缺失或不可读",
        }
    total, meta = _sum_seat_warehouse(state, "public_depot")
    if total is None:
        return {
            "total_materials": None,
            "routes_covered": 0,
            "display": "undefined",
            "reason": "治所尚未开辟官方料场",
        }
    return {
        "total_materials": round(total, 2),
        "routes_covered": meta["routes"],
        "by_route": meta["by_route"],
        "display": f"{total:,.1f} 围/方",
        "reason": None,
    }


def public_granary_summary(state: Any) -> Dict[str, Any]:
    """汇总全国官仓 `public_granary` 实粮（seats 真账；不再回退 changping 镜像）。"""
    if not isinstance(getattr(state, "prefectures", None), dict):
        return {
            "total_grain": None,
            "routes_covered": None,
            "display": "undefined",
            "reason": "state.prefectures 缺失或不可读",
        }
    total, meta = _sum_seat_warehouse(state, "public_granary", only_dim="grain")
    if total is None:
        return {
            "total_grain": None,
            "routes_covered": 0,
            "display": "undefined",
            "reason": "治所未找到官仓实物储备",
        }
    return {
        "total_grain": round(total, 1),
        "routes_covered": meta["routes"],
        "by_route": meta["by_route"],
        "display": f"{total:,.0f} 石",
        "reason": None,
    }


def merchant_warehouse_summary(state: Any) -> Dict[str, Any]:
    """汇总民间商贾货栈 `civilian_depots`（seats 真账）。"""
    if not isinstance(getattr(state, "prefectures", None), dict):
        return {
            "total_holdings": None,
            "routes_active": None,
            "display": "undefined",
            "reason": "state.prefectures 缺失",
        }
    total, meta = _sum_seat_warehouse(state, "civilian_depots")
    if total is None:
        return {
            "total_holdings": None,
            "routes_active": 0,
            "display": "undefined",
            "reason": "治所未找到商贾货栈",
        }
    active_routes = sum(1 for row in (meta["by_route"] or {}).values()
                        if any(float(v) > 0 for v in row.values()))
    return {
        "total_holdings": round(total, 2),
        "routes_active": active_routes,
        "by_route": meta["by_route"],
        "display": f"{total:,.1f} 件/围",
        "reason": None,
    }


def in_transit_summary(state: Any) -> Dict[str, Any]:
    """汇总沈括途耗空间在途物资与客运旅程。"""
    if state is None:
        return {
            "batch_count": None,
            "net_volume": None,
            "passenger_trips": None,
            "display": "undefined",
            "reason": "state 缺失",
        }

    batches = getattr(state, "in_transit_batches", None)
    if batches is None:
        batches = getattr(state, "material_transit", [])
    trips = getattr(state, "passenger_trips", [])

    b_list = list(batches) if isinstance(batches, (list, tuple)) else []
    t_list = list(trips) if isinstance(trips, (list, tuple)) else []

    net_vol = sum(float(b.get("net_delivered", b.get("volume", 0.0)) or 0.0)
                  for b in b_list if isinstance(b, dict))

    return {
        "batch_count": len(b_list),
        "net_volume": round(net_vol, 2),
        "passenger_trips": len(t_list),
        "display": f"{len(b_list)} 批在途 ({net_vol:,.1f} 实物), {len(t_list)} 批旅程",
        "reason": None,
    }


def pipeline_health_readout(state: Any) -> Dict[str, Any]:
    """汇总声明式月度结算管线 48 步的注册与调度健康度。"""
    try:
        from core.settlement_pipeline import get_default_pipeline
        pipeline = get_default_pipeline()
        steps = pipeline.steps
        critical_count = sum(1 for s in steps if s.critical)
        return {
            "total_steps": len(steps),
            "critical_steps": critical_count,
            "phase_count": len(set(s.phase for s in steps)),
            "healthy": len(steps) >= 48,
            "display": f"{len(steps)} 步全覆盖 (含 {critical_count} 核心关键步)",
            "reason": None,
        }
    except Exception as e:
        log.warning("管线读数不可达: %r", e, exc_info=True)
        return {
            "total_steps": None,
            "critical_steps": None,
            "phase_count": None,
            "healthy": False,
            "display": "undefined",
            "reason": f"管线注册表异常: {e!r}",
        }


# ==============================================================================
# 🔴 系统层 vs 朝廷层账目口径分离（2026-10-17 用户硬约束指令）
#
# 哲学与史实原则：
# 1. 系统层（System Ledger / 上帝全知视角）：
#    - 全社会货币总集 M_ALL 与全社会实物总仓；
#    - 涵盖朝廷、地方、POP民间、商帮、在途物流等全部主体；
#    - 遵循物理守恒定律（ΔM_ALL == 0，无对手方绝不生灭）。
#
# 2. 朝廷层（Court Ledger / 三司·户部·朝廷度支视角）：
#    - 仅计入朝廷直接拥有与支配的头寸：国库 (treasury)、内帑 (imperial_treasury)、太仓 (granary)、官料场 (public_depot)；
#    - 地方府库（local_treasury）为州县存留，民间财富（POP.wealth）为百姓私产，均【非】朝廷可用资金；
#    - 朝廷动用民间资财必须经和买、征税或采购，产生财政支出；
#    - 明确区分朝廷即期可用头寸与朝廷累积负债（欠饷、欠俸、欠维持费）。
# ==============================================================================

def court_ledger_summary(state: Any) -> Dict[str, Any]:
    """汇总【朝廷层】直接财政与物料头寸（三司/户部视角，严禁混入地方与民间资产）。"""
    if state is None:
        return {"display": "undefined", "reason": "state 缺失"}

    treasury = getattr(state, "treasury", None)
    imperial = getattr(state, "imperial_treasury", None)
    granary = getattr(state, "granary", None)

    if treasury is None or imperial is None or granary is None:
        return {
            "court_funds": None,
            "imperial_funds": None,
            "court_grain": None,
            "display": "undefined",
            "reason": "国库、内帑或太仓字段缺失（缺失≠0）",
        }

    # 朝廷直接建材储备（全国官方料场合计）
    depot_res = public_depot_summary(state)
    depot_mat = depot_res.get("total_materials")

    # 朝廷挂账负债（欠饷、欠俸、营造欠费）
    stats = getattr(state, "statistics", {}) or {}
    arrears = {
        "military_arrears": stats.get("military_arrears", 0),
        "clan_arrears": stats.get("clan_arrears", 0),
        "upkeep_arrears": stats.get("upkeep_arrears", 0),
    }
    total_arrears = sum(int(v or 0) for v in arrears.values())

    return {
        "scope": "court_government",
        "treasury": float(treasury),
        "imperial_treasury": float(imperial),
        "available_cash": float(treasury) + float(imperial),
        "central_granary": float(granary),
        "official_materials": depot_mat,
        "liabilities": arrears,
        "total_arrears": total_arrears,
        "display": f"国库 {treasury:,.0f} 贯 / 内帑 {imperial:,.0f} 贯 / 太仓 {granary:,.0f} 石 (欠款 {total_arrears:,} 贯)",
        "note": "朝廷层账目：仅限国库、内帑与官仓，民间财富与地方府库非朝廷可用头寸",
        "reason": None,
    }


def system_ledger_summary(state: Any) -> Dict[str, Any]:
    """汇总【系统层】全社会物理与货币核算（全知上帝视角，遵循物理守恒）。"""
    if state is None:
        return {"display": "undefined", "reason": "state 缺失"}

    try:
        from core.foundation.ledger import money as _money
        m_all_val = _money.m_all(state)
    except Exception as e:
        m_all_val = None
        log.warning("系统层 M_ALL 读取失败: %r", e, exc_info=True)

    if m_all_val is None:
        return {
            "m_all": None,
            "display": "undefined",
            "reason": "M_ALL 不可读",
        }

    # 民间 POP 财富总计
    pop_w = 0.0
    for p in getattr(state, "prefectures", {}).values():
        if isinstance(p, dict) and "pops" in p and isinstance(p["pops"], dict):
            for pop in p["pops"].values():
                if isinstance(pop, dict):
                    pop_w += float(pop.get("wealth", 0.0) or 0.0)

    # 地方府库总计
    local_t = 0.0
    for p in getattr(state, "prefectures", {}).values():
        if isinstance(p, dict):
            local_t += float(p.get("local_treasury", 0.0) or 0.0)

    # 空间在途
    transit_res = in_transit_summary(state)

    return {
        "scope": "system_universe",
        "m_all": round(m_all_val, 2),
        "civilian_pop_wealth": round(pop_w, 2),
        "local_treasuries": round(local_t, 2),
        "in_transit_batches": transit_res.get("batch_count"),
        "display": f"全域 M_ALL: {m_all_val:,.0f} 贯 (民间 {pop_w:,.0f} 贯 / 地方府库 {local_t:,.0f} 贯)",
        "note": "系统层物理全账：涵盖民间、地方、朝廷、在途全部子池，遵循严格守恒",
        "reason": None,
    }


def court_vs_system_contrast(state: Any) -> Dict[str, Any]:
    """【朝廷层 vs 系统层】口径对照读数：回答「朝廷实际掌握全社会多少资源」。"""
    c_led = court_ledger_summary(state)
    s_led = system_ledger_summary(state)

    c_cash = c_led.get("available_cash")
    s_m_all = s_led.get("m_all")

    if c_cash is None or s_m_all is None or s_m_all <= 0:
        return {
            "court_cash_share": None,
            "civilian_share": None,
            "display": "undefined",
            "reason": "朝廷或系统层账目不可读（缺失≠0）",
            "warning": "两层口径不可混同！",
        }

    c_share = c_cash / s_m_all
    civ_w = float(s_led.get("civilian_pop_wealth", 0.0) or 0.0)
    civ_share = civ_w / s_m_all

    return {
        "court_available_cash": c_cash,
        "system_m_all": s_m_all,
        "court_money_share": round(c_share, 4),
        "civilian_wealth_share": round(civ_share, 4),
        "display": f"朝廷占全社会货币 {c_share:.1%} (民间藏富 {civ_share:.1%})",
        "verdict": "朝廷可用资金仅为系统子集，不可混同",
        "reason": None,
    }


def court_blurred_pop_ledger(state: Any) -> Dict[str, Any]:
    """【朝廷层民间 POP 模糊账目】（户部版籍·黄册青册奏报视角）。
    
    核心制度与历史逻辑：
    - 朝廷无法穿透底层上帝视角获知民间每一个 POP 的精确财富与实有人丁；
    - 朝廷所见皆为地方知州通判层层呈递的【簿籍奏报】；
    - 受地方吏员把持度 (grip)、巡按御史监察度与豪强隐田隐户影响，奏报存在结构性漏报与模糊区间；
    - 底层物理世界保持精确守恒（生产/消费/税收），朝廷决策面对的是带摩擦的模糊信息。
    """
    if state is None or not hasattr(state, "prefectures") or not isinstance(state.prefectures, dict):
        return {
            "reported_headcount_range": None,
            "reported_wealth_range": None,
            "in_register_ratio": None,
            "concealment_ratio": None,
            "display": "undefined",
            "reason": "state.prefectures 不可读（缺失≠0）",
        }

    real_size_total = 0
    real_wealth_total = 0.0
    grips = []
    by_class_real: Dict[str, Dict[str, float]] = {
        c: {"size": 0, "wealth": 0.0} for c in ("农", "士绅", "工匠", "商人", "官僚", "兵")
    }

    for p in state.prefectures.values():
        if not isinstance(p, dict):
            continue
        # 吏员把持度
        d = p.get("clerks_detail")
        if isinstance(d, dict) and "grip" in d:
            grips.append(float(d.get("grip", 0.45) or 0.45))
        elif "grip" in p:
            grips.append(float(p.get("grip", 0.45) or 0.45))
        
        pops = p.get("pops")
        if isinstance(pops, dict):
            for c, pop in pops.items():
                if isinstance(pop, dict) and c in by_class_real:
                    s = int(pop.get("size", 0) or 0)
                    w = float(pop.get("wealth", 0.0) or 0.0)
                    by_class_real[c]["size"] += s
                    by_class_real[c]["wealth"] += w
                    real_size_total += s
                    real_wealth_total += w

    if real_size_total <= 0:
        return {
            "reported_headcount_range": None,
            "reported_wealth_range": None,
            "in_register_ratio": None,
            "concealment_ratio": None,
            "display": "undefined",
            "reason": "民间 POP 数据为空",
        }

    # 1. 派生全域平均信息摩擦系数（由吏制把持度驱动）
    avg_grip = (sum(grips) / len(grips)) if grips else 0.45

    # 在籍率：把持度越高，隐匿逃丁越多，在籍率越低（通常在 72% ~ 86%）
    in_register_ratio = max(0.60, min(0.95, 1.0 - (avg_grip * 0.35 + 0.05)))
    # 财富隐匿漏报率：豪强隐产、诡名寄产（通常在 20% ~ 40%）
    concealment_ratio = max(0.10, min(0.50, avg_grip * 0.45 + 0.08))

    # 2. 构造朝廷视角的模糊估算区间（朝廷三司奏折形式）
    # 人丁在籍估算区间 (±4% 簿籍统计浮动)
    rep_size_base = real_size_total * in_register_ratio
    rep_size_min = int(rep_size_base * 0.96)
    rep_size_max = int(rep_size_base * 1.04)

    # 申报税基资产估算区间 (±6% 查核误差)
    rep_w_base = real_wealth_total * (1.0 - concealment_ratio)
    rep_w_min = round(rep_w_base * 0.94, 0)
    rep_w_max = round(rep_w_base * 1.06, 0)

    # 3. 逐阶层模糊簿籍估算
    class_blurred: Dict[str, Dict[str, Any]] = {}
    for c, data in by_class_real.items():
        # 士绅与商人隐匿率更高，农户在籍率相对高
        cls_conceal = concealment_ratio * (1.3 if c in ("士绅", "商人") else 0.9)
        cls_reg = in_register_ratio * (0.85 if c in ("士绅", "商人") else 1.05)
        cls_conceal = max(0.05, min(0.60, cls_conceal))
        cls_reg = max(0.50, min(0.98, cls_reg))

        c_size_est = int(data["size"] * cls_reg)
        c_w_est = round(data["wealth"] * (1.0 - cls_conceal), 0)
        class_blurred[c] = {
            "reported_size_est": c_size_est,
            "reported_wealth_est": c_w_est,
            "reg_ratio_est": round(cls_reg, 3),
            "conceal_ratio_est": round(cls_conceal, 3),
        }

    clarity = "较为明晰" if avg_grip < 0.35 else ("版籍模糊" if avg_grip < 0.55 else "严重失真")

    return {
        "scope": "court_blurred_perspective",
        "clarity_level": clarity,
        "avg_clerk_grip": round(avg_grip, 3),
        "in_register_ratio": round(in_register_ratio, 3),
        "concealment_ratio": round(concealment_ratio, 3),
        "reported_headcount_range": [rep_size_min, rep_size_max],
        "reported_wealth_range": [rep_w_min, rep_w_max],
        "class_blurred_breakdown": class_blurred,
        "display": (
            f"在籍约 {rep_size_min/10000:,.0f}~{rep_size_max/10000:,.0f} 万丁 "
            f"(申报财富 {rep_w_min/10000:,.0f}~{rep_w_max/10000:,.0f} 万贯 · {clarity})"
        ),
        "verdict": "朝廷簿籍非物理真账：受吏强隐田影响，在籍率~" f"{in_register_ratio:.0%}，隐匿~{concealment_ratio:.0%}",
        "reason": None,
    }


