# -*- coding: utf-8 -*-
"""宋祚 · Step 8 灾荒结算子模块。

拆分自 core/settlement_steps.py：天灾结算与灾荒区域归一化。
主流程见 core/settlement.py；本模块被 settlement_steps re-export 保持调用兼容。
"""
import random

from content.data import DISASTER_RELIEF_GRAIN


def _normalize_disaster_region(state, region):
    """把灾荒 region 俗名归一到 prefectures 稳定键。"""
    if not region:
        return None
    if region in state.prefectures:
        return region
    for key, p in state.prefectures.items():
        if p.get("name") == region:
            return key
    for key, p in state.prefectures.items():
        name = p.get("name", key)
        if region in key or region in name:
            return key
    return None


def _settle_disaster(state, log):
    """天灾结算。灾荒时开仓赈济，耗太仓存粮；有粮则安民，无粮则民怨更重。

    12 步 agent 化 P1：有 _relief_ai 契约（按察使）时赈济量/流民按档位换算（10万~50万石、
    流民 ±5万~±30万），灾级 1~5 放大既有减产/粮价；无契约走既有 DISASTER_RELIEF_GRAIN。
    守恒铁律：赈济扣太仓/流民回流农 POP 由本步程序守恒（agent 只给档位词）。
    """
    _relief_ai = getattr(state, "_relief_ai", None)
    relief_grain = DISASTER_RELIEF_GRAIN
    if isinstance(_relief_ai, dict) and not _relief_ai.get("_error"):
        from core.settlement_steps import _P1_RELIEF
        relief_grain = _P1_RELIEF.get(_relief_ai.get("relief", "微"), DISASTER_RELIEF_GRAIN)
        # 灾级 1~5 放大既有公式（减产/粮价由灾荒触发方按 severity 处理）
        state.disaster_severity = max(1, min(5, int(_relief_ai.get("disaster_level", 1))))
    if state.disaster_severity > 0:
        state.disaster_severity = max(0, state.disaster_severity - 1)
        relief = min(relief_grain, state.granary)
        state.change_granary(-relief)
        state.granary_stats["relief"] += relief
        if relief >= relief_grain:
            state.population_satisfaction = max(0, min(100, state.population_satisfaction + 1))
            relieved = relief * 3000
            region = _normalize_disaster_region(state, state.disaster_region)
            if region is not None:
                local = state.prefectures[region].get("refugees", 0)
                used = min(relieved, local)
                state.prefectures[region]["refugees"] = max(0, local - used)
                # 人口守恒（QA 定位修复）：本地安置流民回流农 POP（流民→自耕农/佃户），
                # 防止"流民减少但人口凭空消失"；人口守恒：本地 used + 邻路 Σadd == 流民减少 == 农 POP 增加。
                state.prefectures[region]["pops"]["农"]["size"] += used
                spill = relieved - used
            else:
                used = 0
                spill = relieved
            if spill > 0:
                others = {k: v.get("refugees", 0) for k, v in state.prefectures.items()}
                tot = sum(others.values())
                if tot > 0:
                    for k, rv in others.items():
                        # add 受该路流民存量约束（min(rv)）：每路最多安置其全部流民，
                        # 防止赈济能力（relief×3000）远超流民存量时"超额安置"凭空创造人口。
                        add = min(int(spill * rv / tot), rv)
                        if add > 0:
                            state.prefectures[k]["refugees"] = max(0, state.prefectures[k]["refugees"] - add)
                            # 人口守恒（QA 定位修复）：溢邻路安置流民回流该路农 POP
                            state.prefectures[k]["pops"]["农"]["size"] += add
            log.append(f"[赈济·{region}] 开太仓发粟 {relief}石赈灾，本地流民稍安，余者溢邻路")
        else:
            state.population_satisfaction = max(0, state.population_satisfaction - 3)
            log.append(f"[饥馑] 太仓乏粟（仅发 {relief}石），饿殍渐现，逃荒者众！")
        log.append(f"[灾荒] {state.disaster_region} 持续，严重度 {state.disaster_severity}")

    if random.random() < 0.03:
        severity = random.randint(1, 5)
        region = random.choice(["河北", "京东", "两浙", "陕西", "河东", "荆湖"])
        state.disaster_severity = severity
        state.disaster_region = region
        state.population_satisfaction = max(0, state.population_satisfaction - severity * 2)
        road_key = _normalize_disaster_region(state, region)
        if road_key is not None:
            p = state.prefectures[road_key]
            add_ref = severity * 5000
            cap = int(p.get("population", 1_000_000) * 0.10)  # 人口(口)上限
            # BUG#2 修复（人口守恒，与 BUG#1 对称）：灾荒新发流民不再凭空增——
            # flee 受 add_ref、流民 cap 余量与农 POP size 三重约束；
            # 受灾农 POP 减少 flee（逃荒为流民），流民增加 flee，人口不凭空增减。
            room = max(0, cap - p.get("refugees", 0))
            flee = min(add_ref, room, p["pops"]["农"]["size"])
            p["pops"]["农"]["size"] -= flee
            p["refugees"] = p.get("refugees", 0) + flee
            # 灾荒减产：受灾路年产减产（8%/级），下次收获即少粮，体现"灾年减产"而非只涨价
            p["grain"] = int(p.get("grain", 0) * (1 - 0.08 * severity))
            log.append(f"[流民] {region}灾荒（{severity}级），本地流民骤增 {flee}，四散就食，田禾减产")
        log.append(f"[灾荒] {region}发生灾荒！严重度 {severity}")
        state.statistics["total_disasters"] += 1
