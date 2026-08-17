# -*- coding: utf-8 -*-
"""audit-data 量纲审计：确定性回放脚本（seed 固定，不依赖 GUI）。
输出：12 个月太仓/国库/盐课/酒课/粮价/各路加总表。
"""
import sys, os, json, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 审计环境注入：core/settlement.py 当前缺 from typing import Any（硬伤），不改源码，注入 builtins 绕过
import builtins
if not hasattr(builtins, "Any"):
    builtins.Any = object()

from content.data import PREFECTURE_INFO, PREFECTURE_LIST
from core.game_state import GameState
from core.settlement import run_monthly_settlement

def main():
    random.seed(2026)
    state = GameState("史实")

    # ---- 静态总量核算（口径裁决用）----
    sums = {
        "prefecture_count": 0,
        "households": 0.0,
        "land_wan_mu": 0.0,
        "grain_wan_shi": 0.0,      # grain 字段（原月产/或年产待裁）
        "grain_yield_wan_shi": 0.0,  # grain_yield 字段（万石/年）
        "population_wan": 0.0,
        "garrisons_wan": 0.0,
        "officials": 0.0,
        "clerks": 0.0,
    }
    for name in PREFECTURE_LIST:
        info = PREFECTURE_INFO[name]
        sums["prefecture_count"] += 1
        sums["households"] += info.get("households", 0)
        sums["land_wan_mu"] += info.get("land", 0)
        sums["grain_wan_shi"] += info.get("grain", 0)
        sums["grain_yield_wan_shi"] += info.get("grain_yield", 0)
        sums["population_wan"] += info.get("population", 0)
        sums["officials"] += info.get("officials", 0)
        sums["clerks"] += info.get("clerks", 0)

    # 兵额真账已迁移到 army_units（troops 为人数），此处由实体聚合（人→万）
    sums["garrisons_wan"] = sum(u.troops for u in state.army_units) / 10000.0

    print("===== 静态总量 =====")
    for k, v in sums.items():
        print(f"{k}: {v}")

    print("\n===== 系统常量 =====")
    from content import data as D
    for c in ["LAND_TAX_RATE", "LAND_TAX_RATE_BENEFIT", "MILITARY_GRAIN_MONTHLY",
              "OFFICIAL_GRAIN_MONTHLY", "OFFICIAL_GRAIN_PER_MONTH",
              "CLERK_GRAIN_PER_MONTH", "SOLDIER_GRAIN_PER_MONTH",
              "OFFICIAL_PAY_PER_MONTH", "SOLDIER_PAY_PER_MONTH", "CLERK_PAY_PER_MONTH",
              "CLERK_PER_OFFICIAL", "IMPERIAL_SHARE", "CORRUPTION_MULT", "CORRUPTION_FLOOR",
              "SUI_GONG_ANNUAL", "PER_CAPITA_MONTH_GRAIN", "GRANARY_START", "GRANARY_START_CAP",
              "CANAL_MONTHLY_RATE", "CANAL_LOSS_BASE", "CANAL_LOSS_CORRUPT_WEIGHT",
              "SPARROW_RAT", "PAY_CASH_BASE", "MONTHLY_EXP_CIVIL_BASE",
              "SALT_COIN_UNIT", "SALT_CAPACITY_BASE", "SALT_POP_BASE", "SALT_PRICE_FLOOR", "SALT_PRICE_CEIL",
              "WINE_COIN_BASE", "COMMERCE_TAX_RATE_DEFAULT",
              "ANNUAL_TAX_BASE", "TAX_POLL_RATIO", "TAX_COLOR_RATE",
              "MONEY_SUPPLY_START", "PRICE_LEVEL_BASE", "PRICE_LEVEL_MIN", "PRICE_LEVEL_MAX",
              "PRICE_VELOCITY", "GRAIN_PRICE_MIN", "GRAIN_PRICE_MAX",
              "DISASTER_RELIEF_GRAIN", "CHANGPING_HIGH", "CHANGPING_LOW",
              "TAX_COEFF_MIN", "TAX_COEFF_MAX"]:
        if hasattr(D, c):
            print(f"{c} = {getattr(D, c)}")

    print("\n===== 月度轨迹（12 个月）=====")
    hdr = "月 | 太仓(万石) | 国库(万贯) | 内帑(万贯) | 粮价(贯/石?) | 太仓月入/出"
    print(hdr)
    for i in range(12):
        state.year, state.month = (1000 + i // 12, i % 12 + 1)
        before_g = state.granary
        before_t = state.treasury
        log = run_monthly_settlement(state)
        dg = state.granary - before_g
        dt = state.treasury - before_t
        gp = state.grain_price
        # 找太仓入仓行
        gin = state.granary_stats.get("canal_in", 0) + state.granary_stats.get("tax", 0)
        gout = state.granary_stats.get("military", 0) + state.granary_stats.get("sparrow", 0)
        print(f"{i+1:2d} | {state.granary:6.0f} | {state.treasury/10000:9.0f} | "
              f"{state.imperial_treasury/10000:7.0f} | {gp:6.2f} | Δg={dg:+5.0f} Δt={dt/10000:+6.0f} "
              f"(入{gin:.0f}/出{gout:.0f})")

    print("\n===== 年内累计 =====")
    print(f"总入(货币): {state.statistics['total_income']/10000:.0f}万贯")
    print(f"总支(货币): {state.statistics['total_expenditure']/10000:.0f}万贯")
    print(f"内帑总入: {state.statistics.get('total_inner_income',0)/10000:.0f}万贯")
    print(f"税率: 工商{state.tax_breakdown}")

    print("\n===== 年度化估值 =====")
    monthly = state.statistics['total_income'] / 12.0
    print(f"月均货币入: {monthly/10000:.1f}万贯 → 年化 {monthly*12/10000:.0f}万贯")
    annual_color = 0
    print(f"盐课 SALT_COIN_UNIT={D.SALT_COIN_UNIT}（活基准：Σ盐产能×单位×price_factor×arrival）")
    print(f"酒课 WINE_COIN_BASE={D.WINE_COIN_BASE}万贯/月 → 年化 {D.WINE_COIN_BASE*12/10000:.0f}万贯")

    print("\n===== 各 calc_* 量纲快照（当月）=====")
    ag, agn = state.calc_army_grain()
    ac, acn = state.calc_army_cash()
    og, ogb = state.calc_official_grain()
    oc, ocb = state.calc_official_cash()
    cg, cgb = state.calc_clerk_grain()
    cc, ccb = state.calc_clerk_cash()
    cd, cgl = state.calc_corruption_deduction()
    mg = state.calc_monthly_grain()
    ti = state.calc_monthly_tax_income(1.0)
    print(f"军粮: {ag:.1f}万石/月(本色×pay={ag*state.pay_system.get('grain_ratio',0.5):.1f}) 军饷: {ac:.1f}万贯/月")
    print(f"官禄: {og:.2f}万石/月 官俸: {oc:.1f}万贯/月")
    print(f"吏禄: {cg:.2f}万石/月 吏俸: {cc:.1f}万贯/月")
    print(f"贪腐扣减: 钱{cd:.1f}万贯/月 粮{cgl:.1f}万石/月")
    mg_total, mg_by = mg
    print(f"全国月粮产 calc_monthly_grain: 总额={mg_total:.0f}万石/月 分路={ {k: round(v,1) for k,v in list(mg_by.items())[:3]} }...")
    ti_total, ti_by = ti
    print(f"二税折色 calc_monthly_tax_income: 总额={ti_total:.0f}万贯/月 分路={ {k: round(v,1) for k,v in list(ti_by.items())[:3]} }...")

    out = {
        "static_sums": sums,
        "trajectory": [
            {"month": i+1, "granary": state.granary, "treasury_wan": state.treasury/10000,
             "inner_wan": state.imperial_treasury/10000, "grain_price": state.grain_price}
            for i in range(12)
        ],
    }
    with open(os.path.join(os.path.dirname(__file__), "audit_dimension_replay.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n已写出 audit_dimension_replay.json")

if __name__ == "__main__":
    main()
