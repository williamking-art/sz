# -*- coding: utf-8 -*-
"""导出前端所需静态常量为 JSON（React 面板迁移用，一次性工具）。

运行：python _scratch/export_constants.py > frontend/src/renderer/data/constants.json
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game"))

from content.data import (
    FACTION_NAMES, FACTION_INIT, YAMEN_LIST, YAMEN_INFO,
    PREFECTURE_LIST, PREFECTURE_INFO, TECH_NODES, TECH_LINES,
    BUILDING_STD, BUILDING_BLUEPRINTS, IMPERIAL_ACTION_MATRIX,
    IMPERIAL_LOCATIONS, IMPERIAL_MODES,
)

out = {
    "faction_names": list(FACTION_NAMES),
    "faction_init": {k: dict(v) for k, v in FACTION_INIT.items()},
    "yamen_list": list(YAMEN_LIST),
    "yamen_info": {k: dict(v) for k, v in YAMEN_INFO.items()},
    "prefecture_list": list(PREFECTURE_LIST),
    "tech_lines": list(TECH_LINES),
    "tech_nodes": [
        {
            "id": n[0], "line": n[1], "era": n[2], "name": n[3], "desc": n[4],
            "prereq": list(n[5]) if isinstance(n[5], (list, tuple)) else n[5],
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
_target = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "renderer", "data", "constants.json")
with open(_target, "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"[export] written → {_target}", file=sys.stderr)
