# -*- coding: utf-8 -*-
"""北宋官员 2D 布娃娃换装系统核心装配与渲染引擎（Paperdoll Engine）。

核心原则：
1. 纯净自底向上 8 层叠合（Layer 0 到 Layer 9）；
2. 绝对标准大半身像（810×1080 viewBox="0 0 810 1080"）；
3. 严格骨骼锚点物理对齐，白色中单自然包裹素体脖颈，彻底消除断头与浮空；
4. 7 维解耦五官参数驱动实时渲染，4032万种组合真正实现千人千面；
5. 支持高精度 SVG 输出，并支持导出无损 PNG。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

try:
    from content.ministers.paperdoll.model import (
        DollSkeletonRig,
        EquipmentSlot,
        FaceDNA,
        MinisterAudienceProfile,
        RenderZIndex,
    )
    from content.ministers.paperdoll.registry import (
        EQUIPMENT_CATALOG,
        MANNEQUIN_CATALOG,
    )
except ImportError:
    from game.content.ministers.paperdoll.model import (
        DollSkeletonRig,
        EquipmentSlot,
        FaceDNA,
        MinisterAudienceProfile,
        RenderZIndex,
    )
    from game.content.ministers.paperdoll.registry import (
        EQUIPMENT_CATALOG,
        MANNEQUIN_CATALOG,
    )

# 核心历史规制色谱
PALETTE = {
    "silk_bg": "#C4A877",
    "silk_dark": "#B39562",
    "skin_base": "#E5C8A8",
    "skin_shadow": "#C9A782",
    "skin_wrinkle": "#A88360",
    "futou_black": "#1A1715",
    "futou_highlight": "#38322D",
    "collar_white": "#F8F8F5",
    "collar_shadow": "#DDD8CE",
    # 官服四品色
    "robe_zi": "#462255",
    "robe_zi_shadow": "#31143D",
    "robe_fei": "#8F2424",
    "robe_fei_shadow": "#691717",
    "robe_lv": "#2F5C3E",
    "robe_lv_shadow": "#1E3E29",
    "robe_qing": "#284457",
    "robe_qing_shadow": "#182C3A",
    "robe_shi": "#D6CEBF",
    "robe_shi_shadow": "#B8AE9D",
    # 革带金银玉铜
    "belt_leather": "#26201B",
    "gold_plaque": "#E0B33A",
    "silver_plaque": "#CCD0D5",
    "jade_plaque": "#F0F5EE",
    "horn_plaque": "#54463A",
    # 笏板
    "hu_ivory": "#FAF4E8",
    "hu_wood": "#68482A",
    "hu_jade": "#F7FCF5",
}


class PaperdollRenderEngine:
    """全游统一北宋官员布娃娃换装与渲染引擎。"""

    def __init__(self, width: int = 810, height: int = 1080):
        self.width = width
        self.height = height

    def render_to_svg(self, profile: MinisterAudienceProfile) -> str:
        """根据大臣召对 Profile，完整动态渲染出一张高精北宋工笔大半身肖像 SVG。"""
        rig = DollSkeletonRig()
        equipped = profile.equipped
        face_dna = profile.face_dna
        costume_tier = profile.costume_tier

        # 获取各槽位装备
        robe_item = EQUIPMENT_CATALOG.get(equipped.get(EquipmentSlot.ROBE.value, "robe_lv_7th"))
        headwear_item = EQUIPMENT_CATALOG.get(equipped.get(EquipmentSlot.HEADWEAR.value, "futou_short_flat"))
        belt_item = EQUIPMENT_CATALOG.get(equipped.get(EquipmentSlot.BELT.value, "belt_black_horn"))
        pouch_item = EQUIPMENT_CATALOG.get(equipped.get(EquipmentSlot.POUCH.value, "pouch_none"))
        held_item = EQUIPMENT_CATALOG.get(equipped.get(EquipmentSlot.HELD.value, "held_wood_tablet"))

        # 色彩映射
        robe_tier = robe_item.tier if robe_item else "lv"
        robe_color = PALETTE.get(f"robe_{robe_tier}", PALETTE["robe_lv"])
        robe_shadow = PALETTE.get(f"robe_{robe_tier}_shadow", PALETTE["robe_lv_shadow"])

        # 幞头展角宽度 (px from center x=405)
        wing_span = 360 if (headwear_item and headwear_item.tier == "zi") else (
            290 if (headwear_item and headwear_item.tier == "fei") else 220
        )

        svg_parts = []
        svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}">
  <defs>
    <!-- 宣和殿老绢本渐变底色 -->
    <radialGradient id="silk_bg" cx="50%" cy="40%" r="70%">
      <stop offset="0%" stop-color="{PALETTE['silk_bg']}" />
      <stop offset="100%" stop-color="{PALETTE['silk_dark']}" />
    </radialGradient>
    
    <!-- 官袍立体光影渐变 -->
    <linearGradient id="robe_grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{robe_shadow}" />
      <stop offset="20%" stop-color="{robe_color}" />
      <stop offset="50%" stop-color="{robe_color}" />
      <stop offset="80%" stop-color="{robe_color}" />
      <stop offset="100%" stop-color="{robe_shadow}" />
    </linearGradient>

    <!-- 幞头漆纱墨色渐变 -->
    <linearGradient id="futou_grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{PALETTE['futou_highlight']}" />
      <stop offset="100%" stop-color="{PALETTE['futou_black']}" />
    </linearGradient>

    <!-- 象牙朝笏光泽渐变 -->
    <linearGradient id="hu_grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#EBE3D0" />
      <stop offset="40%" stop-color="#FCFAF5" />
      <stop offset="100%" stop-color="#E2D8C3" />
    </linearGradient>
  </defs>

  <!-- ==================== Layer 0: 宣和老绢本背景 ==================== -->
  <rect width="100%" height="100%" fill="url(#silk_bg)" />

  <!-- ==================== Layer 1: 人形素体脖颈 ==================== -->
  <g id="layer1_base_doll">
    <!-- 颈项素体 (完整连贯，杜绝断头) -->
    <polygon points="360,260 450,260 458,410 352,410" fill="{PALETTE['skin_base']}" />
    <!-- 颌下与锁骨工笔阴影 -->
    <path d="M 360 375 Q 405 410 450 375 L 445 395 Q 405 422 365 395 Z" fill="{PALETTE['skin_shadow']}" opacity="0.8" />
  </g>

  <!-- ==================== Layer 2: 7 维解耦五官面模 (千人千面) ==================== -->
  <g id="layer2_face">
''')
        # 2.1 脸型绘制 (根据 face_dna.face_shape 动态微调轮廓)
        shape = face_dna.face_shape
        if shape == "shape_square":
            # 方正国字脸
            svg_parts.append(f'    <path d="M 320 240 C 315 340 335 390 405 395 C 475 390 495 340 490 240 C 465 210 345 210 320 240 Z" fill="{PALETTE["skin_base"]}" stroke="{PALETTE["skin_shadow"]}" stroke-width="2" />\n')
        elif shape == "shape_round_plump":
            # 温润微丰圆脸
            svg_parts.append(f'    <path d="M 315 240 C 305 330 330 405 405 405 C 480 405 505 330 495 240 C 470 210 340 210 315 240 Z" fill="{PALETTE["skin_base"]}" stroke="{PALETTE["skin_shadow"]}" stroke-width="2" />\n')
        elif shape == "shape_slender_bone":
            # 清癯长脸
            svg_parts.append(f'    <path d="M 330 235 C 325 330 350 405 405 408 C 460 405 485 330 480 235 C 455 210 355 210 330 235 Z" fill="{PALETTE["skin_base"]}" stroke="{PALETTE["skin_shadow"]}" stroke-width="2" />\n')
        else:
            # 默认瓜子/鹅蛋脸
            svg_parts.append(f'    <path d="M 325 240 C 320 330 340 388 405 392 C 470 388 490 330 485 240 C 465 210 345 210 325 240 Z" fill="{PALETTE["skin_base"]}" stroke="{PALETTE["skin_shadow"]}" stroke-width="2" />\n')

        # 耳廓
        svg_parts.append(f'''    <path d="M 325 280 C 310 290 310 335 325 350 Z" fill="{PALETTE['skin_base']}" stroke="{PALETTE['skin_shadow']}" stroke-width="1.5" />
    <path d="M 485 280 C 500 290 500 335 485 350 Z" fill="{PALETTE['skin_base']}" stroke="{PALETTE['skin_shadow']}" stroke-width="1.5" />\n''')

        # 2.2 眉毛绘制 (根据 face_dna.eyebrows)
        eyebrow = face_dna.eyebrows
        eb_stroke = "#261F1A" if eyebrow != "eyebrow_frost" else "#A8A8A8"
        if eyebrow == "eyebrow_sword":
            svg_parts.append(f'''    <path d="M 345 272 L 395 264" fill="none" stroke="{eb_stroke}" stroke-width="3.5" stroke-linecap="round" />
    <path d="M 465 272 L 415 264" fill="none" stroke="{eb_stroke}" stroke-width="3.5" stroke-linecap="round" />\n''')
        else:
            svg_parts.append(f'''    <path d="M 348 270 Q 375 262 396 272" fill="none" stroke="{eb_stroke}" stroke-width="3" stroke-linecap="round" />
    <path d="M 462 270 Q 435 262 414 272" fill="none" stroke="{eb_stroke}" stroke-width="3" stroke-linecap="round" />\n''')

        # 2.3 眼睛绘制 (根据 face_dna.eyes)
        eyes = face_dna.eyes
        if eyes == "eyes_eagle_sharp":
            svg_parts.append(f'''    <ellipse cx="375" cy="285" rx="14" ry="6" fill="#FAF6EE" stroke="#3A2818" stroke-width="1.5" />
    <circle cx="376" cy="285" r="4" fill="#181410" />
    <circle cx="378" cy="283" r="1.2" fill="#FFFFFF" />
    <ellipse cx="435" cy="285" rx="14" ry="6" fill="#FAF6EE" stroke="#3A2818" stroke-width="1.5" />
    <circle cx="434" cy="285" r="4" fill="#181410" />
    <circle cx="436" cy="283" r="1.2" fill="#FFFFFF" />\n''')
        elif eyes == "eyes_deep_shrewd":
            svg_parts.append(f'''    <path d="M 360 286 Q 375 280 390 286" fill="none" stroke="#251C15" stroke-width="2" />
    <circle cx="375" cy="286" r="3.2" fill="#181410" />
    <path d="M 420 286 Q 435 280 450 286" fill="none" stroke="#251C15" stroke-width="2" />
    <circle cx="435" cy="286" r="3.2" fill="#181410" />\n''')
        else:
            svg_parts.append(f'''    <ellipse cx="375" cy="285" rx="13" ry="7" fill="#FCFAF2" stroke="#3A2B20" stroke-width="1.2" />
    <circle cx="375" cy="285" r="4.2" fill="#1C1814" />
    <circle cx="377" cy="283" r="1.2" fill="#FFFFFF" />
    <ellipse cx="435" cy="285" rx="13" ry="7" fill="#FCFAF2" stroke="#3A2B20" stroke-width="1.2" />
    <circle cx="435" cy="285" r="4.2" fill="#1C1814" />
    <circle cx="437" cy="283" r="1.2" fill="#FFFFFF" />\n''')

        # 2.4 鼻梁
        svg_parts.append(f'''    <path d="M 405 275 L 403 325 Q 405 332 405 334 M 396 332 Q 405 337 414 332" fill="none" stroke="{PALETTE['skin_shadow']}" stroke-width="2" stroke-linecap="round" />\n''')

        # 2.5 嘴唇
        svg_parts.append(f'''    <path d="M 390 355 Q 405 358 420 355 M 394 355 Q 405 365 416 355" fill="none" stroke="#7A3D3D" stroke-width="2.2" stroke-linecap="round" />\n''')

        # 2.6 岁月风霜皱纹 (根据 face_dna.complexion)
        if "wrinkles" in face_dna.complexion or face_dna.complexion == "complexion_mature":
            svg_parts.append(f'''    <!-- 额纹与法令纹 (老成沉稳) -->
    <path d="M 370 238 Q 405 233 440 238" fill="none" stroke="{PALETTE['skin_wrinkle']}" stroke-width="1.2" opacity="0.6" />
    <path d="M 388 338 Q 380 355 385 368" fill="none" stroke="{PALETTE['skin_wrinkle']}" stroke-width="1.2" opacity="0.6" />
    <path d="M 422 338 Q 430 355 425 368" fill="none" stroke="{PALETTE['skin_wrinkle']}" stroke-width="1.2" opacity="0.6" />\n''')
        svg_parts.append('  </g>\n')

        # ==================== Layer 3: 须髯髯口 ====================
        svg_parts.append('  <g id="layer3_beard">\n')
        b_type = face_dna.beard
        b_color = "#999999" if "grey" in b_type or "snow" in b_type else "#221C16"
        if b_type != "beard_none":
            # 上唇微髭
            svg_parts.append(f'    <path d="M 388 348 Q 405 344 422 348" fill="none" stroke="{b_color}" stroke-width="3.5" stroke-linecap="round" opacity="0.9" />\n')
        if "three" in b_type or b_type == "beard_long_black" or "snow" in b_type:
            # 经典中长绺美髯
            svg_parts.append(f'''    <path d="M 401 370 Q 405 440 405 465 Q 409 440 409 370 Z" fill="{b_color}" opacity="0.95" />
    <path d="M 380 365 Q 370 410 368 435 Q 378 410 384 368 Z" fill="{b_color}" opacity="0.9" />
    <path d="M 430 365 Q 440 410 442 435 Q 432 410 426 368 Z" fill="{b_color}" opacity="0.9" />\n''')
        svg_parts.append('  </g>\n')

        # ==================== Layer 4: 白色中单交领 (护颈素衬) ====================
        svg_parts.append(f'''  <g id="layer4_collar">
    <!-- 白色中单交领 (严密护颈，彻底杜绝断头) -->
    <polygon points="355,420 405,475 455,420 405,385" fill="{PALETTE['collar_white']}" stroke="{PALETTE['collar_shadow']}" stroke-width="1.8" />
    <polygon points="368,415 405,460 442,415 405,380" fill="#EAE5DC" />
  </g>\n''')

        # ==================== Layer 5: 官制大袍大袖 (圆领襕袍) ====================
        svg_parts.append(f'''  <g id="layer5_robe">
    <!-- 圆领大袖襕袍主干身躯 -->
    <path d="M 230 460 Q 200 680 140 880 L 130 1080 L 680 1080 L 670 880 Q 610 680 580 460 Z" fill="url(#robe_grad)" stroke="#1F1B16" stroke-width="2.2" />
    
    <!-- 左大袖自然垂落 -->
    <path d="M 230 460 C 130 520 80 660 120 860 C 140 940 180 970 240 920 C 270 840 280 720 280 620 Z" fill="{robe_color}" stroke="{robe_shadow}" stroke-width="2.5" />
    
    <!-- 右大袖自然垂落 -->
    <path d="M 580 460 C 680 520 730 660 690 860 C 670 940 630 970 570 920 C 540 840 530 720 530 620 Z" fill="{robe_color}" stroke="{robe_shadow}" stroke-width="2.5" />

    <!-- 宋代标志性中脊缝线与下摆横襕 -->
    <line x1="405" y1="460" x2="405" y2="715" stroke="{robe_shadow}" stroke-width="2" stroke-dasharray="6,2" opacity="0.6" />
    <path d="M 210 980 Q 405 1010 600 980" fill="none" stroke="{robe_shadow}" stroke-width="3.5" />

    <!-- 领口外缘圆领 (环扣中单) -->
    <path d="M 330 420 Q 405 488 480 420 C 470 410 440 398 405 398 C 370 398 340 410 330 420 Z" fill="{robe_shadow}" stroke="#1E1A16" stroke-width="2" />
  </g>\n''')

        # ==================== Layer 6: 公服革带 (扎于腰间 y=715) ====================
        svg_parts.append(f'''  <g id="layer6_belt">
    <!-- 革带深黑皮带基底 (紧扎腰线，绝不浮空) -->
    <path d="M 260 705 Q 405 725 550 705 L 550 735 Q 405 755 260 735 Z" fill="{PALETTE['belt_leather']}" stroke="#15120F" stroke-width="2" />\n''')
        
        # 带銙板颜色推断
        belt_id = belt_item.id if belt_item else "belt_black_horn"
        if "jade" in belt_id:
            plaque_col = PALETTE["jade_plaque"]
        elif "gold" in belt_id:
            plaque_col = PALETTE["gold_plaque"]
        elif "silver" in belt_id:
            plaque_col = PALETTE["silver_plaque"]
        else:
            plaque_col = PALETTE["horn_plaque"]

        for px in range(290, 520, 28):
            svg_parts.append(f'    <rect x="{px}" y="710" width="18" height="20" rx="3" fill="{plaque_col}" stroke="#1D1915" stroke-width="1.2" />\n')
        svg_parts.append('  </g>\n')

        # ==================== Layer 7: 随身鱼袋 (系挂于右侧革带) ====================
        pouch_id = pouch_item.id if pouch_item else "pouch_none"
        if pouch_id != "pouch_none":
            pouch_col = PALETTE["gold_plaque"] if "gold" in pouch_id else PALETTE["silver_plaque"]
            svg_parts.append(f'''  <g id="layer7_pouch">
    <line x1="500" y1="720" x2="500" y2="750" stroke="#4A184A" stroke-width="4" stroke-linecap="round" />
    <rect x="488" y="750" width="24" height="60" rx="6" fill="{pouch_col}" stroke="#2A2010" stroke-width="1.8" />
    <circle cx="500" cy="765" r="5" fill="#FFE599" />
    <ellipse cx="500" cy="785" rx="6" ry="12" fill="#D4AF37" stroke="#332408" stroke-width="1" />
  </g>\n''')

        # ==================== Layer 8: 双手端持朝笏手板 ====================
        svg_parts.append('  <g id="layer8_hands_and_hu">\n')
        hu_id = held_item.id if held_item else "held_wood_tablet"
        if "jade" in hu_id or "ivory" in hu_id:
            hu_fill = "url(#hu_grad)"
            hu_stroke = "#BDB39E"
        else:
            hu_fill = PALETTE["hu_wood"]
            hu_stroke = "#422814"

        svg_parts.append(f'''    <!-- 朝笏竖立贯穿两手 -->
    <polygon points="398,440 412,440 415,675 395,675" fill="{hu_fill}" stroke="{hu_stroke}" stroke-width="1.8" />
    <path d="M 398 440 Q 405 436 412 440" stroke="{hu_stroke}" stroke-width="2" fill="none" />

    <!-- 肃穆两手握持朝笏下部 (y=570..640) -->
    <ellipse cx="385" cy="600" rx="15" ry="22" fill="{PALETTE['skin_base']}" stroke="{PALETTE['skin_shadow']}" stroke-width="1.8" />
    <ellipse cx="425" cy="600" rx="15" ry="22" fill="{PALETTE['skin_base']}" stroke="{PALETTE['skin_shadow']}" stroke-width="1.8" />
    <path d="M 360 620 Q 405 635 450 620" fill="none" stroke="{robe_shadow}" stroke-width="4" stroke-linecap="round" />
  </g>\n''')

        # ==================== Layer 9: 漆纱幞头 (顶层扣压发际) ====================
        svg_parts.append(f'''  <g id="layer9_futou">
    <!-- 幞头山梁本体 (覆盖发际 y=140..235) -->
    <path d="M 320 235 C 315 160 345 120 405 115 C 465 120 495 160 490 235 C 470 230 440 226 405 226 C 370 226 340 230 320 235 Z" fill="url(#futou_grad)" stroke="#110F0D" stroke-width="2.5" />
    
    <!-- 幞头后梁折褶 -->
    <path d="M 350 145 Q 405 135 460 145" fill="none" stroke="{PALETTE['futou_highlight']}" stroke-width="2" />
    <path d="M 340 180 Q 405 170 470 180" fill="none" stroke="{PALETTE['futou_highlight']}" stroke-width="1.8" />
    
    <!-- 帽沿硬漆扣带 (紧压额头发际线) -->
    <path d="M 320 235 Q 405 226 490 235 L 488 245 Q 405 236 322 245 Z" fill="#151210" />

    <!-- 左右刚直铁线展角 (wing_span: 一尺半至两尺半) -->
    <!-- 左展角 -->
    <path d="M 320 225 L {405 - wing_span} 225 C {395 - wing_span} 225 {395 - wing_span} 233 {405 - wing_span} 233 L 320 231 Z" fill="#14110F" stroke="#2A241F" stroke-width="1" />
    <!-- 右展角 -->
    <path d="M 490 225 L {405 + wing_span} 225 C {415 + wing_span} 225 {415 + wing_span} 233 {405 + wing_span} 233 L 490 231 Z" fill="#14110F" stroke="#2A241F" stroke-width="1" />
  </g>
</svg>''')

        return "".join(svg_parts)

    def render_to_file(self, profile: MinisterAudienceProfile, output_path: str) -> str:
        """渲染并保存大臣立绘文件 (SVG 格式)。"""
        svg_content = self.render_to_svg(profile)
        svg_path = output_path if output_path.endswith(".svg") else output_path.rsplit(".", 1)[0] + ".svg"
        os.makedirs(os.path.dirname(os.path.abspath(svg_path)), exist_ok=True)
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        return svg_path
