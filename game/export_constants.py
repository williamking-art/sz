# -*- coding: utf-8 -*-
"""导出前端所需静态常量为 JSON（React 面板迁移用）。

运行（工作目录为 game/）：python export_constants.py
输出：frontend/src/renderer/data/constants.json
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from content.data import (
    FACTION_NAMES, FACTION_INIT, YAMEN_LIST, YAMEN_INFO,
    PREFECTURE_LIST, PREFECTURE_INFO, TECH_NODES, TECH_LINES,
    DIRECT_DECREE_MAX, SECRET_DECREE_MAX,
    BUILDING_STD, BUILDING_BLUEPRINTS, IMPERIAL_ACTION_MATRIX,
    IMPERIAL_LOCATIONS, IMPERIAL_MODES,
)

out = {
    "faction_names": list(FACTION_NAMES),
    "faction_init": {k: dict(v) for k, v in FACTION_INIT.items()},
    "yamen_list": list(YAMEN_LIST),
    "yamen_info": {k: dict(v) for k, v in YAMEN_INFO.items()},
    "prefecture_list": list(PREFECTURE_LIST),
    "direct_decree_max": DIRECT_DECREE_MAX,
    "secret_decree_max": SECRET_DECREE_MAX,
    "tech_lines": list(TECH_LINES),
    # 科技节点元组：(id, line, era, name, desc, prereq, need_level, need_sub, cost, effect)
    # 审查修复：原导出漏掉 need_level / need_sub → 前端 nodeStatus() 只校验 prereq，
    # 而后端 core/asset_context.node_prereqs_met() 还校验 level 与副指标 →
    # 面板显示「可研发」、点下去被后端拒（"前置未备，暂不可研"）。
    "tech_nodes": [
        {
            "id": n[0], "line": n[1], "era": n[2], "name": n[3], "desc": n[4],
            "prereq": list(n[5]) if isinstance(n[5], (list, tuple)) else n[5],
            "need_level": n[6],
            "need_sub": [list(x) for x in (n[7] or [])],
            "cost": n[-2] if len(n) >= 2 else None,
            "effect": n[-1],
        }
        for n in TECH_NODES
    ],
    "building_std": {k: dict(v) for k, v in BUILDING_STD.items()},
    "building_blueprints": {k: dict(v) for k, v in BUILDING_BLUEPRINTS.items()},
    "imperial_locations": list(IMPERIAL_LOCATIONS),
    "imperial_modes": list(IMPERIAL_MODES),
    "imperial_matrix": {
        loc: {
            mode: {
                act: {
                    "label": cell.get("label", act),
                    "desc": cell.get("desc", ""),
                    "base_cost": cell.get("base_cost", 0),
                    "fund": cell.get("fund", "treasury"),
                    "risk": cell.get("risk", "低"),
                    # 审查修复：漏导 bandwidth_cost → 前端拿不到该项，个人面板
                    # 「圣旨额度 -1（大驾在途，远程批奏）」提示恒不显示（该次行动
                    # 实际确会扣带宽）。
                    "bandwidth_cost": cell.get("bandwidth_cost", 0),
                    "era_gate": cell.get("era_gate"),
                    "prep": cell.get("prep", 0),
                    "distance": cell.get("distance", False),
                    "micro_once": cell.get("micro_once", False),
                    "base_effects": dict(cell.get("base_effects", {}) or {}),
                }
                for act, cell in acts.items()
            }
            for mode, acts in modes.items()
        }
        for loc, modes in IMPERIAL_ACTION_MATRIX.items()
    },
}

print(json.dumps(out, ensure_ascii=False, indent=1))

# 直接写文件（Windows stdout 默认 GBK，重定向会乱码）
_target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "src", "renderer", "data", "constants.json")
with open(_target, "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"[export] written → {_target}", file=sys.stderr)
