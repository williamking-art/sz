# -*- coding: utf-8 -*-
"""宋祚 · 各项施政 policy 指令族（拆分自 core/commands.py）"""
import random
from typing import Any
from core.game_state import GameState
from core.settlement import run_monthly_settlement
from core.errors import AIRuntimeError
from content.data import (
    desensitize_satisfaction, desensitize_shortage,
    desensitize_talent, desensitize_tech, desensitize_trust,
)

def start_project(state: GameState, pid: str, project: dict) -> str:
    """发起一项工程（如新建仓储/加固边备/兴酒坊）。

    project 结构示例：
      {"name": "新建仓储", "type": "granary", "progress": 0, "speed": 12,
       "cost_material": {"timber": 30, "stone": 20}, "cost_coin": 200000,
       "output": {"granary_cap_add": 500}}
    """
    if not isinstance(state.projects, dict):
        state.projects = {}
    project.setdefault("progress", 0)
    project.setdefault("done", False)
    state.projects[pid] = project
    return f"已兴工「{project.get('name', pid)}」，物料齐备则次月推进。"

def start_workshop(state: GameState, wid: str, workshop: dict) -> str:
    """发起一座作坊（如酒坊：粮→酒）。

    workshop 结构示例：
      {"name": "酒坊", "recipe": {"grain_feed": 50}, "output_dim": "wine",
       "yield": 30, "active": True}
    """
    if not isinstance(state.workshops, dict):
        state.workshops = {}
    workshop.setdefault("active", True)
    state.workshops[wid] = workshop
    return f"已设「{workshop.get('name', wid)}」，供料则次月产作。"

def _state_summary_min(state):
    """给 AI 的精简脱敏态势字符串（避免超长）。"""
    s = state.get_state_summary()
    fin = s.get("finance_ext", {})
    ex = s.get("exam_ext", {})
    te = s.get("tech_ext", {})
    return (
        f"时间：{s['time']}；皇威：{s['prestige']['desc']}；"
        f"国库：{s['treasury']['desc']}；民心：{s['pop_sat_desc']}；"
        f"金融：交子{fin.get('jiaozi_trust','')}、{fin.get('coin_shortage','')}、{fin.get('maritime_open','')}；"
        f"工商征{fin.get('commerce_tax','')}；"
        f"科举：{ex.get('open','')}（{ex.get('mode','')}）、人才{ex.get('talent','')}；"
        f"科技：{te.get('level','')}；外交：{s.get('diplomacy_ext',{}).get('alliance','')}；"
        f"金态度：{state.external.get('金',{}).get('attitude',50)}，"
        f"辽态度：{state.external.get('辽',{}).get('attitude',50)}，"
        f"西夏态度：{state.external.get('西夏',{}).get('attitude',50)}。"
    )


