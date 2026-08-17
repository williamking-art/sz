# -*- coding: utf-8 -*-
"""宋祚 · 月度结算主流程

原 1602 行文件已按功能拆分为：
  - settlement_steps.py       Step 1~11 各结算函数
  - settlement_reform.py      机构改制后果推演（reform_org 类圣旨）
  - settlement_extensions.py 五层承接层月度钩子 + MECHANISMS 注册表

本文件仅保留 run_monthly_settlement 主流程，并 re-export 供其它模块
（commands / tests / verify_ai_connect 等）直接 import 的符号，保持兼容。
"""
import random
from typing import Any

from content.data import (
    TREASURY_CRISIS_LINE, TREASURY_COLLAPSE_LINE,
)
from core.game_state import _next_month

from core.settlement_steps import (
    _settle_decrees, _apply_decree_effect,
    _settle_factions,
    _settle_economy, _settle_land_local, _settle_extensions,
    _settle_longterm_decrees, _simulate_external,
    _settle_granary,
    _settle_finance,
    _settle_projects, _settle_workshops,
    _settle_treasury,
    _evaluate_timeline_breaks,
    _settle_military_diplomacy,
    _settle_events,
    _normalize_disaster_region, _settle_disaster,
    _settle_emperor_personal,
    _settle_hidden,
)
from core.settlement_extensions import (
    MECHANISMS,
    _settle_mechanisms, _settle_tech, _settle_org_economy,
)
from core.settlement_reform import settle_reform

# 兼容旧调用方可能直接引用这些符号
__all__ = [
    "run_monthly_settlement",
    "settle_reform",
    "_apply_decree_effect",
    "_normalize_disaster_region",
    "MECHANISMS",
]


# ------------------------------------------------------------
# 主流水线
# ------------------------------------------------------------
def run_monthly_settlement(state, seed_offset: int = 0) -> list:
    """执行月度结算，返回本轮结算日志列表。

    seed_offset 用于确定性复现：以 (state.turn + seed_offset) 派生随机种子，
    使相同回合+offset 的结算结果可复现，为 dev/replay 回放与平衡 A/B 对比打基础。
    """
    random.seed(state.turn * 1000003 + seed_offset)
    log = []

    # 更新年号
    state.update_era_name()
    from core.asset_context import era_switch
    era_switch(state)

    # ---- Step 0: 破产兜底（在其它步骤补血国库前，先按真实库藏判定）----
    if state.treasury < TREASURY_COLLAPSE_LINE:
        state.game_over = True
        state.game_result = "国用耗竭，天下鼎沸——大宋府库空虚，纲纪尽弛"
        log.append("[民生] 国库崩坏至不可复救，国用耗竭，天下鼎沸！")
        return log
    if state.treasury < TREASURY_CRISIS_LINE and not any(
            e.get("title") == "库藏空虚" for e in state.active_events):
        state.population_satisfaction = max(0, state.population_satisfaction - 2)
        log.append("[民生] 库藏空虚，中外忧惧，民怨渐起")
        crisis = {
            "title": "库藏空虚",
            "category": "crisis",
            "desc": "国库亏空日深，府库空虚，中外忧惧。陛下当决断出处：",
            "choices": [
                {"text": "增征商税，权宜聚财", "effects": {"commerce_tax": 0.30}},
                {"text": "裁汰冗费，省浮节流", "effects": {"curtail_waste": 1}},
                {"text": "发内帑，以私蓄济公",
                 "effects": {"treasury": min(state.imperial_treasury, 5000000),
                             "imperial_treasury": -min(state.imperial_treasury, 5000000)}},
                {"text": "卖度牒，权宜救急", "effects": {"treasury": 1000000}},
            ],
        }
        state.active_events.append({"title": crisis["title"], "message": crisis["desc"], "choices": crisis["choices"]})

    # ---- Step 1: 诏令执行 ----
    _settle_decrees(state, log)

    # ---- Step 2: 派系结算 ----
    _settle_factions(state, log)

    # ---- Step 3: 经济（人口→田土→工商） ----
    _settle_economy(state, log)

    # ---- Step 3.5: 田亩与地方州县 ----
    _settle_land_local(state, log)

    # ---- Step 3.6: 扩展维度自然演进（金融/科举/科技/外交） ----
    _settle_extensions(state, log)

    # ---- Step 3.7: 长期拟旨（公开 / 密令）推进与外部政权简单模拟 ----
    _settle_longterm_decrees(state, log)
    _simulate_external(state, log)

    # ---- Step 3.8: 仓廪漕运 ----
    _settle_granary(state, log)

    # ---- Step 4: 财政 ----
    _settle_finance(state, log)

    # ---- Step 4.5: 工程 / 制作系统 ----
    _settle_projects(state, log)
    _settle_workshops(state, log)

    # ---- Step 5: 国库 ----
    _settle_treasury(state, log)

    # ---- Step 6: 军事/外交 ----
    _settle_military_diplomacy(state, log)

    # ---- Step 6.5: 历史改写位评估 ----
    _evaluate_timeline_breaks(state, log)

    # ---- Step 6.8: 五层承接层月度钩子 ----
    _settle_mechanisms(state, log)      # 层②机制槽：纯加成/减耗
    _settle_tech(state, log)            # 层③研发管线：资源×时间×人才推进
    _settle_org_economy(state, log)     # 层④机构经济生命周期：受崩盘线约束

    # ---- Step 7: 事件压力 ----
    _settle_events(state, log)

    # ---- Step 8: 灾荒 ----
    _settle_disaster(state, log)

    # ---- Step 9: 皇帝个人 ----
    _settle_emperor_personal(state, log)

    # ---- Step 10: 隐藏状态 ----
    _settle_hidden(state, log)

    # ---- Step 11: 记录与回合推进 ----
    # 将月份/年份推进收敛到结算函数内部，确保与 Rust 后端（settle.rs）的推进位置一致，
    # 避免 commands 层再次推进导致双端月份各推一次的漂移。
    state.settlement_log.append(log)
    state.turn += 1
    state.year, state.month = _next_month(state.year, state.month)
    state.update_era_name()

    return log
