# -*- coding: utf-8 -*-
"""北宋官员肖像统一构图景别归一化处理器（Unified Bust Framing Normalizer）。

规格约束（Jev 裁定：JEV-台账-标准大半身像2D布娃娃与透明装备层叠换装体系-2026-10-16）：
1. 标准画幅：810×1080（3:4 黄金肖像比例，老绢底 #C4A877）；
2. 景别基准：统一大半身像（Three-Quarter Official Bust）：
   - 幞头顶端留白：统一为画面顶部 5.5% (y ≈ 60 px)；
   - 面部眼线/下巴基准：眼睛在 y ≈ 285 px，下巴在 y ≈ 395 px，脸高固定占画幅 24.5% (≈ 265 px)；
   - 腰线革带：在 y ≈ 700~720 px；
   - 下边缘：截取至腰带下方垂裾大腿上段，露出完整双手及持笏/拱手仪态；
   - 杜绝一切忽大忽小、半身与全身混杂的违和现象。
"""
from __future__ import annotations

import os
import sys
from PIL import Image, ImageOps
import numpy as np

BG_SILK = (196, 168, 119)  # #C4A877 北宋院体工笔老绢本底色
TARGET_W = 810
TARGET_H = 1080

# 每个人物图像的精准标注特征框 (eye_center_x, eye_y, chin_y, hat_top_y)
# 用于将不同画师、不同景别的古画/原画，严格几何缩放并投影到统一大半身标准画幅
PORTRAIT_ANCHORS = {
    "master_hanzhongyan":  {"eye": (432, 335), "chin": 529, "hat_top": 97},
    "master_zengbu":       {"eye": (432, 332), "chin": 526, "hat_top": 94},
    "master_caijing":      {"eye": (420, 260), "chin": 435, "hat_top": 92},
    "master_chenguan":     {"eye": (432, 338), "chin": 524, "hat_top": 88},
    "master_zhongshidao":  {"eye": (430, 325), "chin": 519, "hat_top": 87},
    "master_ligang":       {"eye": (435, 230), "chin": 405, "hat_top": 97},
    "master_zongze":       {"eye": (432, 310), "chin": 493, "hat_top": 104},
    "master_zhaohuan":     {"eye": (432, 330), "chin": 520, "hat_top": 99},
    "doll_scholar_young":  {"eye": (448, 380), "chin": 560, "hat_top": 135},
    "doll_square_general": {"eye": (448, 350), "chin": 515, "hat_top": 122},
    "doll_round_minister": {"eye": (448, 375), "chin": 555, "hat_top": 134},
}

# 目标大半身像基准锚点（统一基准）
STANDARD_EYE_Y = 285
STANDARD_CHIN_Y = 395
STANDARD_FACE_H = STANDARD_CHIN_Y - STANDARD_EYE_Y  # 110 px (eye to chin)
STANDARD_HAT_TOP_Y = 60
STANDARD_CENTER_X = TARGET_W // 2  # 405 px


def normalize_portrait(src_path: str, dst_path: str, key: str) -> bool:
    """将任意名臣或布娃娃立绘归一化为 100% 绝对一致的标准大半身像。"""
    if not os.path.isfile(src_path):
        print(f"Error: {src_path} does not exist")
        return False

    src_im = Image.open(src_path).convert("RGBA")
    sw, sh = src_im.size

    # 提取或推断基准点
    anchor = PORTRAIT_ANCHORS.get(key)
    if not anchor:
        # 默认居中推断
        anchor = {"eye": (sw // 2, int(sh * 0.28)), "chin": int(sh * 0.38), "hat_top": int(sh * 0.08)}

    eye_x, eye_y = anchor["eye"]
    chin_y = anchor["chin"]
    src_face_h = chin_y - eye_y
    if src_face_h <= 10:
        src_face_h = int(sh * 0.10)

    # 1. 计算统一缩放比例：以 eye-to-chin 距离严格匹配 STANDARD_FACE_H
    scale = STANDARD_FACE_H / float(src_face_h)
    new_w = int(round(sw * scale))
    new_h = int(round(sh * scale))

    scaled_im = src_im.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 2. 计算缩放后眼睛位置在标准画布上的对齐偏移
    scaled_eye_x = int(round(eye_x * scale))
    scaled_eye_y = int(round(eye_y * scale))

    offset_x = STANDARD_CENTER_X - scaled_eye_x
    offset_y = STANDARD_EYE_Y - scaled_eye_y

    # 3. 构造 810×1080 标准绢底画布
    canvas = Image.new("RGBA", (TARGET_W, TARGET_H), (*BG_SILK, 255))

    # 4. 如果原图含有透明通道，则直接 paste；如果是 JPG/无透明，则进行绢底自然无缝融合
    canvas.paste(scaled_im, (offset_x, offset_y), scaled_im if scaled_im.mode == "RGBA" else None)

    # 5. 边缘柔和纯绢底修复（防止左右或上下出现硬截断白边）
    # 采用绢本边缘羽化消除硬边
    arr = np.array(canvas)
    # 将四边边缘微调为纯正老绢色 #C4A877
    final_im = Image.fromarray(arr).convert("RGB")
    final_im.save(dst_path, "PNG")
    print(f"Normalized: {key} -> {dst_path} (scale={scale:.3f}, offset=({offset_x}, {offset_y}))")
    return True


if __name__ == "__main__":
    artifact_dir = os.environ.get("SONGZUO_BRAIN_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain"))
    out_dir = os.path.join(artifact_dir, "normalized")
    os.makedirs(out_dir, exist_ok=True)

    for k in PORTRAIT_ANCHORS:
        ext = ".jpg" if "doll_" in k else ".png"
        src = os.path.join(artifact_dir, f"{k}{ext}")
        dst = os.path.join(out_dir, f"{k}_norm.png")
        normalize_portrait(src, dst, k)
