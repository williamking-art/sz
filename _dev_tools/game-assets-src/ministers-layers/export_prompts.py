# -*- coding: utf-8 -*-
"""导出北宋官员公服 RPG 模块化生图提示词矩阵（JSON 任务清单）。"""
import json
import os
import sys

# 注入 game 路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SZ_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
GAME_DIR = os.path.join(SZ_ROOT, "game")
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)

from content.ministers.portrait_assembler import generate_modular_component_prompts


def main():
    prompts = generate_modular_component_prompts()
    out_file = os.path.join(CURRENT_DIR, "modular_prompts_tasks.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    print(f"[OK] 成功导出模块化生图任务提示词: {out_file}")
    print(f"包含部件分类: {list(prompts.keys())}")


if __name__ == "__main__":
    main()
