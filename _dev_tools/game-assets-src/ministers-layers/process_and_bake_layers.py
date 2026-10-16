# -*- coding: utf-8 -*-
"""北宋官员 2D 布娃娃换装系统图层处理与烘焙器（Layer Processing & Baking Pipeline）。

方案 B 权威图层规范：
1. 全员统一画布尺寸：810 × 1080 (3:4)
2. 统一骨骼锚点：
   - Head: (405, 230)
   - Collar: (405, 360)
   - Waist: y = 680
   - Pouch: (490, 710)
   - Chest: (405, 520)
3. 严格透明通道（RGBA）：边缘平滑无杂边、无断裂白洞。
"""
from __future__ import annotations

import os
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps

TARGET_W, TARGET_H = 810, 1080


def create_silk_background(output_path: str, width: int = TARGET_W, height: int = TARGET_H) -> None:
    """生成北宋院体工笔设色纯正宣和老绢本底色纹理 (#C4A877)。"""
    # 基础基色 #C4A877 = (196, 168, 119)
    base_color = np.array([196, 168, 119], dtype=np.float32)
    
    # 漫射径向渐变
    y, x = np.ogrid[:height, :width]
    cy, cx = height * 0.35, width * 0.5
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    radial_falloff = 1.0 - (dist / max_dist) * 0.12
    radial_falloff = np.clip(radial_falloff, 0.85, 1.05)
    
    # 微细绢丝纹理噪声
    np.random.seed(42)
    noise = np.random.normal(0.0, 3.5, (height, width, 1))
    
    img_data = base_color[None, None, :] * radial_falloff[:, :, None] + noise
    img_data = np.clip(img_data, 0, 255).astype(np.uint8)
    
    img = Image.fromarray(img_data, mode="RGB")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    print(f"老绢本宣和底色生成完成: {output_path}")


def extract_transparent_foreground(
    input_path: str,
    output_path: str,
    bg_color_type: str = "white",
    feather_radius: float = 1.5,
) -> None:
    """提取透明前景对象并保存为 RGBA PNG。"""
    img = Image.open(input_path).convert("RGB")
    arr = np.array(img, dtype=np.float32)

    if bg_color_type == "white":
        # 针对纯白或近白色背景抠除
        # 纯白: R>240, G>240, B>240
        diff = np.sqrt(np.sum((arr - 255.0) ** 2, axis=2))
        # 距离越小越透明
        alpha = np.clip((diff - 15.0) / 30.0, 0.0, 1.0) * 255.0
    elif bg_color_type == "silk":
        # 针对老绢底 (#C4A877 = 196, 168, 119) 抠除
        target_bg = np.array([196.0, 168.0, 119.0], dtype=np.float32)
        diff = np.sqrt(np.sum((arr - target_bg) ** 2, axis=2))
        alpha = np.clip((diff - 25.0) / 40.0, 0.0, 1.0) * 255.0
    else:
        alpha = np.full((arr.shape[0], arr.shape[1]), 255.0, dtype=np.float32)

    alpha_img = Image.fromarray(alpha.astype(np.uint8), mode="L")
    if feather_radius > 0:
        alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(feather_radius))

    rgba = img.convert("RGBA")
    rgba.putalpha(alpha_img)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    rgba.save(output_path, "PNG", optimize=True)
    print(f"透明图层处理完成: {output_path}")


def normalize_to_canvas(
    input_rgba_path: str,
    output_path: str,
    target_center: tuple[int, int],
    target_box: tuple[int, int, int, int] | None = None,
) -> None:
    """将图层缩放居中到 810×1080 画布并严格对齐锚点。"""
    src = Image.open(input_rgba_path).convert("RGBA")
    canvas = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))

    if target_box is not None:
        # 按指定框进行缩放
        tx, ty, tw, th = target_box
        resized = src.resize((tw, th), Image.Resampling.LANCZOS)
        canvas.paste(resized, (tx, ty), resized)
    else:
        # 按画布居中
        sw, sh = src.size
        scale = min(TARGET_W / sw, TARGET_H / sh)
        new_w, new_h = int(sw * scale), int(sh * scale)
        resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # 居中放置
        cx, cy = target_center
        px = cx - new_w // 2
        py = cy - new_h // 2
        canvas.paste(resized, (px, py), resized)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    canvas.save(output_path, "PNG", optimize=True)
    print(f"归一化图层完成: {output_path}")


if __name__ == "__main__":
    silk_out = os.path.join(
        os.path.dirname(__file__),
        "../../../game/content/ministers/paperdoll/layers/backgrounds/silk_raw.png",
    )
    create_silk_background(silk_out)
