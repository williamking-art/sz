# -*- coding: utf-8 -*-
"""北宋官员 2D 布娃娃换装系统全资产标准化烘焙脚本（Bake All Assets to 810x1080 Layers）。

严格遵循方案 B 骨骼规范与层级规范：
1. 画布标准：810 × 1080 (3:4)
2. 骨骼锚点对齐：
   - Head: (405, 230)
   - Collar: (405, 360)
   - Waist: y = 680
   - Pouch: (490, 710)
   - Chest: (405, 520)
3. 严格无损透明 PNG 图层导出。
"""
from __future__ import annotations

import os
import numpy as np
from PIL import Image, ImageFilter

BRAIN_DIR = r"C:\Users\william\.gemini\antigravity\brain\21dc1567-8824-46b3-91a5-6021d8db2a9f"
OUT_BASE = r"sz/game/content/ministers/paperdoll/layers"

TARGET_W, TARGET_H = 810, 1080


def extract_white_bg_alpha(img_path: str, threshold: float = 16.0, blur: float = 1.0) -> Image.Image:
    """从纯白背景图像中提取平滑透明 Alpha 通道。"""
    raw = Image.open(img_path).convert("RGB")
    arr = np.array(raw, dtype=np.float32)
    diff = np.sqrt(np.sum((255.0 - arr) ** 2, axis=2))
    alpha = np.clip((diff - threshold) / 25.0, 0.0, 1.0) * 255.0
    alpha_img = Image.fromarray(alpha.astype(np.uint8), mode="L")
    if blur > 0:
        alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(blur))
    rgba = raw.convert("RGBA")
    rgba.putalpha(alpha_img)
    return rgba


def bake_futou(src_path: str, out_path: str, scale_width: int, target_y: int) -> None:
    """烘焙幞头透明切片到 810×1080 画布。"""
    rgba = extract_white_bg_alpha(src_path, threshold=15.0, blur=1.0)
    
    # 裁剪到有内容区域
    bbox = rgba.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
        
    fw, fh = rgba.size
    scale = scale_width / float(fw)
    new_w, new_h = int(fw * scale), int(fh * scale)
    scaled = rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    canvas = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    # 中心位于 x=405，下缘位于 target_y 附近
    px = 405 - new_w // 2
    py = target_y - new_h
    canvas.paste(scaled, (px, py), scaled)
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    print(f"Baked Futou: {out_path} (size={canvas.size})")


def bake_robe(src_path: str, out_path: str) -> None:
    """烘焙大袖圆领襕袍透明切片到 810×1080 画布。"""
    rgba = extract_white_bg_alpha(src_path, threshold=15.0, blur=1.0)
    resized = rgba.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    resized.save(out_path, "PNG", optimize=True)
    print(f"Baked Robe: {out_path} (size={resized.size})")


def bake_accessories(src_path: str) -> None:
    """从配件合集中切片烘焙象牙笏、槐木笏、金鱼袋、银鱼袋。"""
    rgba = extract_white_bg_alpha(src_path, threshold=20.0, blur=1.0)
    w, h = rgba.size
    hw, hh = w // 2, h // 2
    
    quads = {
        "hu_ivory": (0, 0, hw, hh),
        "hu_wood": (hw, 0, w, hh),
        "pouch_gold": (0, hh, hw, h),
        "pouch_silver": (hw, hh, w, h),
    }
    
    for name, box in quads.items():
        crop = rgba.crop(box)
        bbox = crop.getbbox()
        if bbox:
            crop = crop.crop(bbox)
            
        canvas = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
        cw, ch = crop.size
        
        if "hu_" in name:
            # 朝笏缩放到高度约 340px，放置于双手之间 (405, 520) 附近
            scale = 340.0 / float(ch)
            tw, th = int(cw * scale), int(ch * scale)
            scaled = crop.resize((tw, th), Image.Resampling.LANCZOS)
            px = 405 - tw // 2
            py = 390  # 笏板顶端略微探出领口
            canvas.paste(scaled, (px, py), scaled)
            out_file = os.path.join(OUT_BASE, "held", f"{name}.png")
        else:
            # 鱼袋缩放到高度约 160px，悬挂于腰线右侧 (490, 710)
            scale = 160.0 / float(ch)
            tw, th = int(cw * scale), int(ch * scale)
            scaled = crop.resize((tw, th), Image.Resampling.LANCZOS)
            px = 510
            py = 660
            canvas.paste(scaled, (px, py), scaled)
            out_file = os.path.join(OUT_BASE, "pouches", f"{name}.png")
            
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        canvas.save(out_file, "PNG", optimize=True)
        print(f"Baked Accessory: {out_file} (size={canvas.size})")


def main():
    print("=== 开始批量烘焙北宋官员标准 810×1080 图层 ===")
    
    # 1. 幞头
    p_futou_long = os.path.join(BRAIN_DIR, "futou_long_v3_1792147538203.jpg")
    p_futou_short = os.path.join(BRAIN_DIR, "futou_short_1792147560777.jpg")
    
    # 长展角幞头：两脚长达两尺半，展宽 770px，底部对齐 y=275
    bake_futou(p_futou_long, os.path.join(OUT_BASE, "futou", "futou_long.png"), scale_width=770, target_y=280)
    # 短平角幞头：展宽约 500px，轻巧稳妥
    bake_futou(p_futou_short, os.path.join(OUT_BASE, "futou", "futou_short.png"), scale_width=500, target_y=270)
    
    # 2. 官袍
    p_robe_zi = os.path.join(BRAIN_DIR, "robe_zi_1792147581814.jpg")
    p_robe_fei = os.path.join(BRAIN_DIR, "robe_fei_1792147602168.jpg")
    p_robe_lv = os.path.join(BRAIN_DIR, "robe_lv_1792147622666.jpg")
    
    bake_robe(p_robe_zi, os.path.join(OUT_BASE, "robes", "robe_zi.png"))
    bake_robe(p_robe_fei, os.path.join(OUT_BASE, "robes", "robe_fei.png"))
    bake_robe(p_robe_lv, os.path.join(OUT_BASE, "robes", "robe_lv.png"))
    
    # 3. 配件
    p_acc = os.path.join(BRAIN_DIR, "accessories_song_1792147651780.jpg")
    bake_accessories(p_acc)
    
    print("=== 全部标准图层烘焙完成！ ===")


if __name__ == "__main__":
    main()
