# -*- coding: utf-8 -*-
"""审计量纲回放脚本（确定性，不依赖 GUI）。

经真实主循环 `advance_month` + `settle_turn` 推进时间，每轮真实快照，
输出 N 月太仓/国库/内帑/粮价/民心/流民/通胀轨迹，供经济审计使用。

与旧版区别（修复 P0 失真）：
- 旧版手动 `state.year/month = (1000+i//12, ...)` 覆盖结算内部自推的时间，
  导致 year 冻结且双推冲突；现改为纯经 advance_month+settle_turn 推进，不覆盖时间。
- trajectory 改为每轮真实快照（旧版用最终态重复写 12 遍）。
"""
import sys, os, json, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 审计环境注入：core/settlement.py 历史缺 from typing import Any，不改源码，注入 builtins 绕过
import builtins
if not hasattr(builtins, "Any"):
    builtins.Any = object()

from content.data import PREFECTURE_INFO, PREFECTURE_LIST, START_YEAR
from core.game_state import GameState
from core.commands import advance_month, settle_turn

MONTHS = 36  # 覆盖 1101→1104，含按年触发事件（方腊/宋江/金军南侵等）


def main():
    random.seed(2026)
    state = GameState("史实")

    # ---- 静态总量核算（口径裁决用）----
    sums = {
        "prefecture_count": 0,
        "households": 0.0,
        "land_wan_mu": 0.0,
        "grain_wan_shi": 0.0,      # grain 字段（石/年 = land×ROAD_YIELD，年总产）
        "population": 0.0,
        "garrisons": 0.0,
        "officials": 0.0,
        "clerks": 0.0,
    }
    for name in PREFECTURE_LIST:
        info = PREFECTURE_INFO[name]
        p = state.prefectures[name]
        sums["prefecture_count"] += 1
        sums["households"] += p.get("households", 0)
        sums["land_wan_mu"] += p.get("land", 0)
        sums["grain_wan_shi"] += p.get("grain", 0)
        sums["population"] += p.get("population", 0)
        sums["officials"] += p.get("officials", 0)
        sums["clerks"] += p.get("clerks", 0)

    # 兵额真账已迁移到 army_units（troops 为人数）
    sums["garrisons"] = sum(u.troops for u in state.army_units) / 1.0

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
              "TAX_COEFF_MIN", "TAX_COEFF_MAX", "HOARD_CAP_MULT", "START_MONEY_BOOST",
              "ARREARS_COLLECT_RATE"]:
        if hasattr(D, c):
            print(f"{c} = {getattr(D, c)}")

    print(f"\n===== 月度轨迹（{MONTHS} 个月，经 advance_month+settle_turn 真实推进）=====")
    hdr = "月 | 年-月 | 太仓(石) | 国库(贯) | 内帑(贯) | 粮价 | 民心 | 流民 | 交子 | 货币供给"
    print(hdr)
    trajectory = []
    for i in range(MONTHS):
        events = advance_month(state)        # 触发当月事件（推进前）
        log, _ = settle_turn(state, None)    # 结算（内部自推 year/month），捕获日志
        # 打印财政/民生关键日志行
        for line in log:
            if any(k in line for k in ("[财政]", "[民生]", "[岁币]", "[军粮]")):
                print(f"  [{i+1:2d}|{state.year}-{state.month:02d}] {line}")
        gp = state.grain_price
        ms = getattr(state, "population_satisfaction", None)
        ref = getattr(state, "refugees", 0)
        jz = getattr(state, "jiaozi", {}).get("issued", 0) if isinstance(getattr(state, "jiaozi", None), dict) else 0
        msupply = getattr(state, "money_supply", 0)
        snap = {
            "idx": i,
            "year": state.year, "month": state.month,
            "granary": state.granary, "treasury": state.treasury,
            "inner": state.imperial_treasury, "grain_price": gp,
            "satisfaction": ms, "refugees": ref,
            "jiaozi": jz, "money_supply": msupply,
            "events": [e.get("title") for e in events],
        }
        trajectory.append(snap)
        print(f"{i+1:2d} | {state.year}-{state.month:02d} | {state.granary:8.0f} | "
              f"{state.treasury:11.0f} | {state.imperial_treasury:9.0f} | {gp:5.2f} | "
              f"{ms} | {ref:7.0f} | {jz:9.0f} | {msupply:11.0f}")

    print("\n===== 年内累计 =====")
    print(f"总入(货币): {state.statistics['total_income']:.0f}贯")
    print(f"总支(货币): {state.statistics['total_expenditure']:.0f}贯")
    print(f"内帑总入: {state.statistics.get('total_inner_income',0):.0f}贯")
    print(f"税率: 工商{state.tax_breakdown}")

    # 货币/通胀漂移
    start_ms = D.MONEY_SUPPLY_START if hasattr(D, "MONEY_SUPPLY_START") else None
    drift = (state.money_supply - start_ms) / start_ms * 100 if start_ms else None
    print(f"\n===== 货币与通胀 =====")
    print(f"开局货币供给: {start_ms}  36月末: {state.money_supply:.0f}  漂移: {drift:+.1f}%" if drift is not None else "MONEY_SUPPLY_START 缺失")

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
    print(f"军粮: {ag:.1f}石/月 军饷: {ac:.1f}贯/月")
    print(f"官禄: {og:.2f}石/月 官俸: {oc:.1f}贯/月")
    print(f"吏禄: {cg:.2f}石/月 吏俸: {cc:.1f}贯/月")
    print(f"贪腐扣减: 钱{cd:.1f}贯/月 粮{cgl:.1f}石/月")
    mg_total, mg_by = mg
    print(f"全国月粮产 calc_monthly_grain: 总额={mg_total:.0f}石/月")
    ti_total, ti_by = ti
    print(f"二税折色 calc_monthly_tax_income: 总额={ti_total:.0f}贯/月")

    out = {
        "static_sums": sums,
        "trajectory": trajectory,
        "start_year": START_YEAR,
        "final": {
            "granary": state.granary, "treasury": state.treasury,
            "inner": state.imperial_treasury, "grain_price": state.grain_price,
            "satisfaction": ms, "refugees": ref, "money_supply": state.money_supply,
        },
    }
    with open(os.path.join(os.path.dirname(__file__), "audit_dimension_replay.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n已写出 audit_dimension_replay.json")


if __name__ == "__main__":
    main()
