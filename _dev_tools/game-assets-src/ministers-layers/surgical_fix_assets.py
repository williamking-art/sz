# -*- coding: utf-8 -*-
"""精准修复北宋官员换装系统图层切片：
1. 提取单根完整象牙朝笏与槐木朝笏（剔除文字残渣，绝对孤立透明）；
2. 官袍圆领精准挖孔（确保人脸与脖颈白绢中单自然露出）；
3. 素体与官袍边界对齐（消除背后露出的白袖）；
4. 幞头帽底对齐发际线（消除悬空黑洞）。
"""
import os
import numpy as np
from PIL import Image, ImageFilter

BRAIN_DIR = r"C:\Users\william\.gemini\antigravity\brain\21dc1567-8824-46b3-91a5-6021d8db2a9f"
LAYERS_ROOT = r"sz/game/content/ministers/paperdoll/layers"

TARGET_W, TARGET_H = 810, 1080


def extract_white_alpha(img: Image.Image, threshold: float = 20.0) -> Image.Image:
    raw = img.convert("RGB")
    arr = np.array(raw, dtype=np.float32)
    diff = np.sqrt(np.sum((255.0 - arr) ** 2, axis=2))
    alpha = np.clip((diff - threshold) / 25.0, 0.0, 1.0) * 255.0
    alpha_img = Image.fromarray(alpha.astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(1.0))
    rgba = raw.convert("RGBA")
    rgba.putalpha(alpha_img)
    return rgba


def clean_hu_tablets():
    """精确提取完整的象牙笏与槐木笏。"""
    p_acc = os.path.join(BRAIN_DIR, "accessories_song_1792147651780.jpg")
    acc = Image.open(p_acc)
    
    # 象牙笏位于左半边上方 x=[80, 440], y=[120, 840]
    crop_ivory = acc.crop((80, 120, 440, 840))
    rgba_ivory = extract_white_alpha(crop_ivory, threshold=20.0)
    bbox_i = rgba_ivory.getbbox()
    if bbox_i:
        rgba_ivory = rgba_ivory.crop(bbox_i)
        
    # 槐木笏位于右半边上方 x=[540, 930], y=[290, 820]
    crop_wood = acc.crop((540, 290, 930, 820))
    rgba_wood = extract_white_alpha(crop_wood, threshold=20.0)
    bbox_w = rgba_wood.getbbox()
    if bbox_w:
        rgba_wood = rgba_wood.crop(bbox_w)

    # 缩放到标准 810x1080 空间中：居中 x=405，高约 450px，持于胸前 (y=430~880)
    for name, item in [("hu_ivory", rgba_ivory), ("hu_wood", rgba_wood)]:
        iw, ih = item.size
        target_h = 460
        scale = target_h / float(ih)
        tw, th = int(iw * scale), int(ih * scale)
        scaled = item.resize((tw, th), Image.Resampling.LANCZOS)
        
        canvas = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
        # 居中对齐
        px = 405 - tw // 2
        py = 430
        canvas.paste(scaled, (px, py), scaled)
        
        out_p = os.path.join(LAYERS_ROOT, "held", f"{name}.png")
        canvas.save(out_p, "PNG", optimize=True)
        print(f"Cleaned {name} saved to: {out_p}")


def fix_robes_and_dolls():
    """修复官袍领口与素体边界。"""
    robes = {
        "robe_zi": os.path.join(BRAIN_DIR, "robe_zi_1792147581814.jpg"),
        "robe_fei": os.path.join(BRAIN_DIR, "robe_fei_1792147602168.jpg"),
        "robe_lv": os.path.join(BRAIN_DIR, "robe_lv_1792147622666.jpg")
    }

    for rkey, rpath in robes.items():
        raw = Image.open(rpath).convert("RGB")
        raw_scaled = raw.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
        arr = np.array(raw_scaled, dtype=np.float32)
        diff = np.sqrt(np.sum((255.0 - arr) ** 2, axis=2))
        alpha = np.clip((diff - 15.0) / 25.0, 0.0, 1.0) * 255.0

        # 精确圆领挖孔：头部 y < 330 必须全部镂空，留下人脸；
        # y 在 [330, 480] 之间，中心 x=405，挖出圆领U形口
        for y in range(TARGET_H):
            for x in range(TARGET_W):
                if y < 330:
                    alpha[y, x] = 0.0
                elif y < 470 and abs(x - 405) < 120:
                    # 领口开弧
                    norm_y = (y - 330) / 140.0
                    norm_x = abs(x - 405) / 120.0
                    if norm_x ** 2 + norm_y ** 2 < 1.0:
                        alpha[y, x] = 0.0

        alpha_img = Image.fromarray(alpha.astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(1.0))
        rgba = raw_scaled.convert("RGBA")
        rgba.putalpha(alpha_img)

        out_r = os.path.join(LAYERS_ROOT, "robes", f"{rkey}.png")
        rgba.save(out_r, "PNG", optimize=True)
        print(f"Fixed robe {rkey} saved to: {out_r}")

    # 清空 pouch 里的垃圾木头切片，放入纯净全透明占位（因为官袍自带金银鱼袋）
    for pkey in ["pouch_gold", "pouch_silver"]:
        empty = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
        empty_p = os.path.join(LAYERS_ROOT, "pouches", f"{pkey}.png")
        empty.save(empty_p, "PNG")
        print(f"Cleared {pkey} (built-in on robe belt)")


def fix_futou_position():
    """修复幞头定位，端正扣在头顶发际线 (y=260)。"""
    futous = {
        "futou_long": (os.path.join(BRAIN_DIR, "futou_long_v3_1792147538203.jpg"), 780, 270),
        "futou_short": (os.path.join(BRAIN_DIR, "futou_short_1792147560777.jpg"), 540, 265)
    }

    for fkey, (fpath, width, target_bottom) in futous.items():
        raw = Image.open(fpath).convert("RGB")
        rgba = extract_white_alpha(raw, threshold=15.0)
        bbox = rgba.getbbox()
        if bbox:
            rgba = rgba.crop(bbox)

        fw, fh = rgba.size
        scale = width / float(fw)
        new_w, new_h = int(fw * scale), int(fh * scale)
        scaled = rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
        px = 405 - new_w // 2
        py = target_bottom - new_h
        canvas.paste(scaled, (px, py), scaled)

        out_f = os.path.join(LAYERS_ROOT, "futou", f"{fkey}.png")
        canvas.save(out_f, "PNG", optimize=True)
        print(f"Fixed futou {fkey} saved to: {out_f}")


def fix_doll_boundaries():
    """裁剪素体身躯，确保素体的白衣不会超出官服外沿。"""
    dolls = ["doll_young", "doll_middle", "doll_elder"]
    for dname in dolls:
        dpath = os.path.join(LAYERS_ROOT, "dolls", f"{dname}.png")
        img = Image.open(dpath).convert("RGBA")
        
        # 将两侧多余白袖（x < 130 或 x > 680，且 y > 450）淡化/消除，避免从官袍后露出来
        arr = np.array(img)
        for y in range(450, TARGET_H):
            for x in range(TARGET_W):
                if x < 120 or x > 690:
                    arr[y, x, 3] = 0
                    
        cleaned = Image.fromarray(arr, mode="RGBA")
        cleaned.save(dpath, "PNG", optimize=True)
        print(f"Fixed doll boundary for {dname}")


if __name__ == "__main__":
    print("=== 开始精准外科手术式图层重构 ===")
    clean_hu_tablets()
    fix_robes_and_dolls()
    fix_futou_position()
    fix_doll_boundaries()
    print("=== 图层外科修复完成 ===")
