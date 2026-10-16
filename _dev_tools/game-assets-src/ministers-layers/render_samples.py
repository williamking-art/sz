# -*- coding: utf-8 -*-
"""批量渲染三位代表性北宋大臣的真实工笔立绘。"""
import os
import sys

# 确保能 import game 模块
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
GAME_DIR = os.path.join(ROOT, "game")
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.content.ministers.paperdoll.controller import MinisterAudienceController
from game.content.ministers.paperdoll.engine import PaperdollRenderEngine

engine = PaperdollRenderEngine()
samples_dir = os.path.join(ROOT, "game", "content", "ministers", "paperdoll", "samples")
brain_dir = r"C:\Users\william\.gemini\antigravity\brain\21dc1567-8824-46b3-91a5-6021d8db2a9f"

ministers = [
    {
        "id": "cai_jing",
        "name": "蔡京",
        "age": 70,
        "rank": "从一品 尚书左仆射",
        "traits": ["理财", "专权"]
    },
    {
        "id": "zhong_shizhong",
        "name": "种师中",
        "age": 48,
        "rank": "正四品 经略安抚使",
        "traits": ["将帅", "刚毅"]
    },
    {
        "id": "new_scholar_ouyang",
        "name": "欧阳澈",
        "age": 25,
        "rank": "从八品 承务郎",
        "traits": ["直谏", "清俊"]
    }
]

for m in ministers:
    ctrl = MinisterAudienceController.create_for_minister(
        minister_id=m["id"],
        name=m["name"],
        age=m["age"],
        rank=m["rank"],
        traits=m["traits"]
    )
    png_path_sample = os.path.join(samples_dir, f"{m['id']}_real_gongbi.png")
    png_path_brain = os.path.join(brain_dir, f"{m['id']}_real_gongbi.png")
    
    engine.render_to_png(ctrl.profile, png_path_sample)
    engine.render_to_png(ctrl.profile, png_path_brain)
    print(f"Rendered real gongbi PNG for {m['name']} -> {png_path_sample}")
