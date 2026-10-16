# -*- coding: utf-8 -*-
"""北宋官员 2D 换装布娃娃（Paper Doll）标准透明装备部件生成与提取引擎。

严格遵循 RPG 装备与布娃娃换装系统工业标准：
- 画布基准：810×1080 3:4 比例，老绢本底色 #C4A877；
- 每一个图层皆为尺寸严格为 810×1080 的透明 PNG (RGBA)；
- 层叠顺序（自下而上）：
  1. Base Doll (素体)
  2. Face (五官面貌)
  3. Beard (胡须髯口)
  4. Robe (官袍)
  5. Belt (革带)
  6. Fish Pouch (佩鱼)
  7. Held Hu (朝笏)
  8. Futou (幞头帽子)
- 零切刀、零渐变、纯 alpha_composite 物理贴装，100% 绝对一致比例大半身像。
"""
from __future__ import annotations

import os
import sys
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

BG_SILK = (196, 168, 119)  # #C4A877
CANVAS_W = 810
CANVAS_H = 1080

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sz/
MINISTER_DIR = os.path.join(MODULE_DIR, "game", "content", "ministers")
LAYERS_DIR = os.path.join(MINISTER_DIR, "layers")


def extract_transparent_robe_from_body(body_rgb_path: str, out_robe_path: str):
    """从 body 图层中提取纯透明袍服图层（去除背景绢底与头面区域）。"""
    im = Image.open(body_rgb_path).convert("RGBA")
    arr = np.array(im)
    h, w, _ = arr.shape

    # 背景差分计算（老绢底约 196, 168, 119）
    # 使用四角与顶部背景检测
    bg_ref = np.array([196, 168, 119], dtype=float)
    diff = np.sqrt(np.sum((arr[:, :, :3].astype(float) - bg_ref)**2, axis=2))

    # 前景掩码
    alpha = np.zeros((h, w), dtype=np.uint8)
    fg = diff > 22
    alpha[fg] = 255

    # 领口以上（头部区域 y < 350）置为透明，保留衣服身躯
    # y < 360 为脖子和头部区域，若为素体露出，保留衣服领口边缘
    alpha[:330, :] = 0
    # 柔化边缘 1px
    alpha_im = Image.fromarray(alpha, mode="L").filter(ImageFilter.GaussianBlur(0.8))

    arr[:, :, 3] = np.array(alpha_im)
    robe_im = Image.fromarray(arr, mode="RGBA")
    robe_im.save(out_robe_path, "PNG")


def extract_transparent_futou(head_rgba_path: str, out_futou_path: str):
    """从头部图层中精准提取漆纱幞头（帽顶与左右展脚，去除面部五官与胡须）。"""
    im = Image.open(head_rgba_path).convert("RGBA")
    arr = np.array(im)
    h, w, _ = arr.shape

    # 幞头为黑色/极深墨色，且位于顶部区域 (y < 260，两翼展脚可延伸到两侧)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    is_black_futou = (r < 75) & (g < 75) & (b < 75) & (a > 100)
    
    # 过滤出帽子区域：y < 260 的深色，或者两侧横向展角 (x < 280 or x > 530) 且 y < 300
    is_hat_zone = (np.arange(h)[:, None] < 255) | (((np.arange(w)[None, :] < 280) | (np.arange(w)[None, :] > 530)) & (np.arange(h)[:, None] < 310))
    futou_mask = is_black_futou & is_hat_zone

    out_alpha = np.zeros((h, w), dtype=np.uint8)
    out_alpha[futou_mask] = 255

    # 边缘平滑
    alpha_im = Image.fromarray(out_alpha, mode="L").filter(ImageFilter.GaussianBlur(0.8))
    arr[:, :, 3] = np.array(alpha_im)

    futou_im = Image.fromarray(arr, mode="RGBA")
    futou_im.save(out_futou_path, "PNG")


def extract_transparent_face(head_rgba_path: str, out_face_path: str):
    """从头部图层中提取纯净五官面模（去除黑帽与外部透明，保留面容）。"""
    im = Image.open(head_rgba_path).convert("RGBA")
    arr = np.array(im)
    h, w, _ = arr.shape

    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    # 面部肤色区域
    is_skin = (r > 130) & (g > 85) & (b > 60) & (r > g) & (g > b) & (a > 100)
    # 面部中央区域 y in [220, 420], x in [300, 510]
    face_zone = (np.arange(h)[:, None] >= 220) & (np.arange(h)[:, None] <= 420) & (np.arange(w)[None, :] >= 290) & (np.arange(w)[None, :] <= 520)
    
    face_mask = is_skin & face_zone
    out_alpha = np.zeros((h, w), dtype=np.uint8)
    out_alpha[face_mask] = 255

    # 连通膨胀与羽化
    alpha_im = Image.fromarray(out_alpha, mode="L").filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(2.0))
    arr[:, :, 3] = np.array(alpha_im)

    face_im = Image.fromarray(arr, mode="RGBA")
    face_im.save(out_face_path, "PNG")


def build_doll_mannequins():
    """构建标准大半身像基础人形素体（Dolls Mannequins）。"""
    dolls_dir = os.path.join(LAYERS_DIR, "dolls")
    os.makedirs(dolls_dir, exist_ok=True)

    # 基础持笏素体：包含标准肤色的脖颈与双手端持朝笏骨架
    chihu_doll_path = os.path.join(dolls_dir, "doll_chihu.png")
    im = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    # 颈项与胸肩人体素体打底（标准宋代士大夫比例）
    skin_color = (215, 185, 145, 255)
    skin_shadow = (195, 160, 125, 255)

    # 脖颈 y: 250..370
    draw.polygon([(365, 260), (445, 260), (455, 370), (355, 370)], fill=skin_color)
    # 喉结与锁骨微阴影
    draw.polygon([(395, 330), (415, 330), (405, 355)], fill=skin_shadow)

    # 双手端笏位置 y: 550..660, x: 360..450
    # 左手与右手握持形态
    draw.rounded_rectangle([(370, 580), (440, 650)], radius=15, fill=skin_color, outline=skin_shadow, width=2)
    im.save(chihu_doll_path, "PNG")

    # 基础拱手素体：两手环抱合拢
    gongshou_doll_path = os.path.join(dolls_dir, "doll_gongshou.png")
    im_g = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw_g = ImageDraw.Draw(im_g)
    draw_g.polygon([(365, 260), (445, 260), (455, 370), (355, 370)], fill=skin_color)
    draw_g.rounded_rectangle([(350, 570), (460, 640)], radius=20, fill=skin_color, outline=skin_shadow, width=2)
    im_g.save(gongshou_doll_path, "PNG")
    print(f"Built dolls mannequins in {dolls_dir}")


def build_belts_pouches_held():
    """构建独立革带、鱼袋、朝笏透明装备图层。"""
    belts_dir = os.path.join(LAYERS_DIR, "belts")
    pouches_dir = os.path.join(LAYERS_DIR, "pouches")
    held_dir = os.path.join(LAYERS_DIR, "held")
    os.makedirs(belts_dir, exist_ok=True)
    os.makedirs(pouches_dir, exist_ok=True)
    os.makedirs(held_dir, exist_ok=True)

    # 1. 革带 (y ≈ 690..730, x: 260..550)
    # 荔枝金带
    im_gold_belt = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_gold_belt)
    # 带身黑皮底
    draw.rounded_rectangle([(270, 695), (540, 725)], radius=6, fill=(35, 30, 25, 255))
    # 金荔枝金銙 (Gold Plaques)
    for bx in range(290, 530, 28):
        draw.rounded_rectangle([(bx, 698), (bx + 20, 722)], radius=3, fill=(218, 175, 55, 255), outline=(170, 130, 30, 255), width=2)
    im_gold_belt.save(os.path.join(belts_dir, "belt_gold.png"), "PNG")

    # 起雀花银带
    im_silver_belt = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_silver_belt)
    draw.rounded_rectangle([(270, 695), (540, 725)], radius=6, fill=(35, 30, 25, 255))
    for bx in range(290, 530, 28):
        draw.rounded_rectangle([(bx, 698), (bx + 20, 722)], radius=3, fill=(215, 220, 225, 255), outline=(160, 165, 175, 255), width=2)
    im_silver_belt.save(os.path.join(belts_dir, "belt_silver.png"), "PNG")

    # 乌角铜带（低品）
    im_horn_belt = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_horn_belt)
    draw.rounded_rectangle([(270, 695), (540, 725)], radius=6, fill=(28, 25, 22, 255))
    for bx in range(290, 530, 28):
        draw.rounded_rectangle([(bx, 700), (bx + 18, 720)], radius=2, fill=(80, 70, 60, 255), outline=(50, 45, 40, 255), width=1)
    im_horn_belt.save(os.path.join(belts_dir, "belt_horn.png"), "PNG")

    # 特赐羊脂白玉带
    im_jade_belt = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_jade_belt)
    draw.rounded_rectangle([(270, 695), (540, 725)], radius=6, fill=(35, 30, 25, 255))
    for bx in range(290, 530, 28):
        draw.rounded_rectangle([(bx, 698), (bx + 20, 722)], radius=3, fill=(245, 248, 245, 255), outline=(200, 205, 200, 255), width=2)
    im_jade_belt.save(os.path.join(belts_dir, "belt_jade.png"), "PNG")

    # 2. 鱼袋 (y ≈ 720..810, x ≈ 485..535，系垂于右腰侧)
    # 金鱼袋
    im_gold_pouch = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_gold_pouch)
    # 悬挂紫带
    draw.line([(500, 715), (500, 740)], fill=(75, 35, 75, 255), width=4)
    # 纯金錾花鱼袋囊
    draw.rounded_rectangle([(485, 740), (515, 805)], radius=6, fill=(218, 175, 55, 255), outline=(160, 120, 25, 255), width=2)
    # 金鱼符浮雕装饰
    draw.ellipse([(492, 755), (508, 785)], fill=(240, 200, 75, 255), outline=(180, 140, 30, 255), width=1)
    im_gold_pouch.save(os.path.join(pouches_dir, "pouch_gold.png"), "PNG")

    # 银鱼袋
    im_silver_pouch = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_silver_pouch)
    draw.line([(500, 715), (500, 740)], fill=(120, 30, 30, 255), width=4)
    draw.rounded_rectangle([(485, 740), (515, 805)], radius=6, fill=(215, 220, 225, 255), outline=(150, 155, 165, 255), width=2)
    draw.ellipse([(492, 755), (508, 785)], fill=(235, 240, 245, 255), outline=(170, 175, 185, 255), width=1)
    im_silver_pouch.save(os.path.join(pouches_dir, "pouch_silver.png"), "PNG")

    # 3. 朝笏 (y ≈ 430..680, x ≈ 395..415，垂直端捧胸前)
    # 象牙朝笏
    im_ivory_hu = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_ivory_hu)
    # 光润象牙手板，上微敛，中平直，下微敛
    draw.polygon([(398, 430), (412, 430), (414, 675), (396, 675)], fill=(245, 240, 225, 255), outline=(205, 195, 175, 255))
    im_ivory_hu.save(os.path.join(held_dir, "held_ivory.png"), "PNG")

    # 透润象牙玉笏 (高品)
    im_jade_hu = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_jade_hu)
    draw.polygon([(397, 425), (413, 425), (415, 680), (395, 680)], fill=(248, 250, 242, 255), outline=(215, 225, 210, 255))
    im_jade_hu.save(os.path.join(held_dir, "held_jade_ivory.png"), "PNG")

    # 质朴槐木手板 (低品)
    im_wood_hu = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_wood_hu)
    draw.polygon([(398, 435), (412, 435), (414, 670), (396, 670)], fill=(125, 90, 55, 255), outline=(85, 55, 30, 255))
    im_wood_hu.save(os.path.join(held_dir, "held_wood.png"), "PNG")

    print(f"Built belts, pouches, held items in {LAYERS_DIR}")


def build_beards():
    """构建独立胡须髯口透明图层 (Beards)。"""
    beards_dir = os.path.join(LAYERS_DIR, "beards")
    os.makedirs(beards_dir, exist_ok=True)

    # 1. 无须 (beard_none)
    im_none = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    im_none.save(os.path.join(beards_dir, "beard_none.png"), "PNG")

    # 2. 修整短髭 (beard_short) y in 355..375
    im_short = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_short)
    draw.arc([(385, 350), (425, 375)], start=200, end=340, fill=(45, 40, 35, 230), width=4)
    im_short.save(os.path.join(beards_dir, "beard_short.png"), "PNG")

    # 3. 三绺美髯 (beard_three_tuft) y in 355..470
    im_three = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_three)
    # 上唇短髭
    draw.arc([(385, 350), (425, 375)], start=200, end=340, fill=(45, 40, 35, 240), width=4)
    # 下巴三绺长髯（中绺与左右两绺）
    draw.polygon([(400, 390), (410, 390), (407, 470), (403, 470)], fill=(40, 35, 30, 230))
    draw.polygon([(380, 385), (388, 385), (378, 440), (373, 440)], fill=(40, 35, 30, 200))
    draw.polygon([(422, 385), (430, 385), (437, 440), (432, 440)], fill=(40, 35, 30, 200))
    im_three.save(os.path.join(beards_dir, "beard_three_tuft.png"), "PNG")

    # 4. 文人山羊胡 (beard_goatee)
    im_goatee = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_goatee)
    draw.arc([(390, 352), (420, 372)], start=200, end=340, fill=(45, 40, 35, 220), width=3)
    draw.polygon([(401, 392), (409, 392), (406, 435), (404, 435)], fill=(45, 40, 35, 230))
    im_goatee.save(os.path.join(beards_dir, "beard_goatee.png"), "PNG")

    # 5. 花白长髯 (beard_long_grey)
    im_grey = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im_grey)
    draw.polygon([(398, 385), (412, 385), (409, 490), (401, 490)], fill=(180, 180, 185, 230))
    draw.polygon([(375, 380), (385, 380), (373, 455), (368, 455)], fill=(180, 180, 185, 200))
    draw.polygon([(425, 380), (435, 380), (442, 455), (437, 455)], fill=(180, 180, 185, 200))
    im_grey.save(os.path.join(beards_dir, "beard_long_grey.png"), "PNG")

    print(f"Built beards in {beards_dir}")


def extract_all_standard_layers():
    """从已有的 body_*.png 和 head_*.png 提取全套透明组件。"""
    # 提取 robes
    robes_dir = os.path.join(LAYERS_DIR, "robes")
    os.makedirs(robes_dir, exist_ok=True)
    for pose in ["chihu", "gongshou", "longxiu"]:
        for tier in ["zi", "fei", "lv", "qing", "shi", "qinwang"]:
            src = os.path.join(LAYERS_DIR, f"body_{pose}_{tier}.png")
            dst = os.path.join(robes_dir, f"robe_{pose}_{tier}.png")
            if os.path.isfile(src):
                extract_transparent_robe_from_body(src, dst)

    # 提取 futou
    futou_dir = os.path.join(LAYERS_DIR, "futou")
    os.makedirs(futou_dir, exist_ok=True)
    # 用 head_scholar 提取短角，用 head_round 提取平角，用 head_square 提取长角
    if os.path.isfile(os.path.join(LAYERS_DIR, "head_scholar.png")):
        extract_transparent_futou(os.path.join(LAYERS_DIR, "head_scholar.png"), os.path.join(futou_dir, "futou_short.png"))
    if os.path.isfile(os.path.join(LAYERS_DIR, "head_round.png")):
        extract_transparent_futou(os.path.join(LAYERS_DIR, "head_round.png"), os.path.join(futou_dir, "futou_mid.png"))
    if os.path.isfile(os.path.join(LAYERS_DIR, "head_square.png")):
        extract_transparent_futou(os.path.join(LAYERS_DIR, "head_square.png"), os.path.join(futou_dir, "futou_long.png"))

    # 提取 faces
    faces_dir = os.path.join(LAYERS_DIR, "faces")
    os.makedirs(faces_dir, exist_ok=True)
    for f_model in ["scholar", "round", "square"]:
        src = os.path.join(LAYERS_DIR, f"head_{f_model}.png")
        dst = os.path.join(faces_dir, f"face_{f_model}.png")
        if os.path.isfile(src):
            extract_transparent_face(src, dst)

    # 构建素体、腰带、鱼袋、朝笏、胡须
    build_doll_mannequins()
    build_belts_pouches_held()
    build_beards()
    print("All standard paper doll layers built successfully!")


if __name__ == "__main__":
    extract_all_standard_layers()
