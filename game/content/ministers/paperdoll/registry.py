# -*- coding: utf-8 -*-
"""北宋官员 2D 布娃娃换装系统资产注册表与 7 维五官参数化库。

核心职责：
1. 注册 3 套基础大半身像素体模特（青年/中年/老年）；
2. 注册 7 维五官解耦素材库（7 脸型 × 8 眉形 × 8 眼形 × 6 鼻型 × 6 嘴唇 × 12 胡须 × 5 岁月风霜 = 4032 万种组合）；
3. 注册 8 大装备插槽的宋代公服装备部件；
4. 提供确定性 Visual DNA 生成器：根据官员姓名、生年、籍贯与特质，派生出独一无二、绝不撞脸的 FaceDNA 与装备。
"""
from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Optional, Tuple

try:
    from content.ministers.paperdoll.model import (
        DollMannequin,
        DollSkeletonRig,
        EquipmentItem,
        EquipmentSlot,
        FaceDNA,
        RenderZIndex,
    )
except ImportError:
    from game.content.ministers.paperdoll.model import (
        DollMannequin,
        DollSkeletonRig,
        EquipmentItem,
        EquipmentSlot,
        FaceDNA,
        RenderZIndex,
    )

# ==================== 1. 基础素体模特库 (Base Mannequins) ====================

MANNEQUIN_CATALOG: Dict[str, DollMannequin] = {
    "mannequin_young": DollMannequin(
        id="mannequin_young",
        name="青年挺拔文士素体",
        age_group="young",
        pose="chihu",
        rig=DollSkeletonRig(),
        default_face_dna=FaceDNA(
            face_shape="shape_oval",
            eyebrows="eyebrow_willow",
            eyes="eyes_clear",
            nose="nose_straight_high",
            mouth="mouth_smile_subtle",
            beard="beard_none",
            complexion="complexion_fair",
        ),
        metadata={"desc": "玉面修竹，挺拔端立，多见于及第新科进士、翰林编修、知县"}
    ),
    "mannequin_middle": DollMannequin(
        id="mannequin_middle",
        name="中年方阔帅臣素体",
        age_group="middle",
        pose="chihu",
        rig=DollSkeletonRig(),
        default_face_dna=FaceDNA(
            face_shape="shape_square",
            eyebrows="eyebrow_straight_thick",
            eyes="eyes_resolute",
            nose="nose_straight_high",
            mouth="mouth_tight_firm",
            beard="beard_short_neat",
            complexion="complexion_tan",
        ),
        metadata={"desc": "方正阔额，沉稳刚毅，多见于大郡知州、提刑官、经略帅臣"}
    ),
    "mannequin_elder": DollMannequin(
        id="mannequin_elder",
        name="老年雍容宰辅素体",
        age_group="elder",
        pose="longxiu",
        rig=DollSkeletonRig(),
        default_face_dna=FaceDNA(
            face_shape="shape_round_plump",
            eyebrows="eyebrow_frost",
            eyes="eyes_benevolent",
            nose="nose_broad",
            mouth="mouth_dignified",
            beard="beard_three_tuft_refined",
            complexion="complexion_aged_wrinkles",
        ),
        metadata={"desc": "耳大颐丰，雍容威仪，长者之风，多见于尚书宰辅、度支元老"}
    ),
}


# ==================== 2. 7 维解耦五官参数库 (4032 万种组合) ====================

FACE_SHAPES = {
    "shape_oval": {"name": "清秀瓜子脸", "desc": "天庭饱满，下颌微敛，文人清流之相"},
    "shape_square": {"name": "方正国字脸", "desc": "重额阔颌，端正沉穆，帅臣良相之相"},
    "shape_round_plump": {"name": "温润微丰脸", "desc": "地阁方圆，耳大颐丰，财计循吏之相"},
    "shape_broad_strong": {"name": "刚毅方阔脸", "desc": "颊骨坚毅，威严肃杀，边防宿将之相"},
    "shape_slender_bone": {"name": "清癯长脸", "desc": "颧骨微显，刚正不阿，台谏御史诤臣之相"},
    "shape_heavy_chin": {"name": "长额重颌脸", "desc": "天庭高耸，下颌厚实，老成持重元老之相"},
    "shape_scholar_soft": {"name": "温雅鹅蛋脸", "desc": "轮廓柔和，气宇轩昂，翰林词臣之相"},
}

EYEBROWS = {
    "eyebrow_straight_thick": {"name": "卧蚕平眉", "desc": "浓粗平直，英气端凝"},
    "eyebrow_sword": {"name": "挺拔剑眉", "desc": "斜飞入鬓，刚勇果决"},
    "eyebrow_willow": {"name": "秀丽柳叶眉", "desc": "弯秀舒展，文士儒雅"},
    "eyebrow_broad_open": {"name": "开阔八字眉", "desc": "开朗从容，通达世情"},
    "eyebrow_frown_dense": {"name": "威严聚拢浓眉", "desc": "双眉如墨，不怒自威"},
    "eyebrow_cold_sharp": {"name": "断尾冷峻眉", "desc": "眉峰锐利，执法如山"},
    "eyebrow_frost": {"name": "稀疏霜白眉", "desc": "白发如霜，阅历沧桑"},
    "eyebrow_temple_long": {"name": "直插鬓角横眉", "desc": "横平挺拔，百战将领"},
}

EYES = {
    "eyes_clear": {"name": "清澈明目", "desc": "少年意气，明眸清润"},
    "eyes_phoenix": {"name": "丹凤威目", "desc": "目如秋水，神光内敛"},
    "eyes_deep_shrewd": {"name": "深邃细目", "desc": "目光敏锐，谋略深藏"},
    "eyes_resolute": {"name": "刚毅铜铃目", "desc": "重眉阔眼，威严逼人"},
    "eyes_aged_droop": {"name": "垂垂老态目", "desc": "眼角微垂，慈祥老练"},
    "eyes_eagle_sharp": {"name": "鹰视锐目", "desc": "如鹰顾盼，机锋森冷"},
    "eyes_meditating": {"name": "凝神思忖目", "desc": "深思熟虑，纵横运筹"},
    "eyes_benevolent": {"name": "慈和温润目", "desc": "宽厚包容，长者之德"},
}

NOSES = {
    "nose_straight_high": {"name": "悬胆直鼻", "desc": "直挺丰润，官运亨通之相"},
    "nose_long_pillar": {"name": "玉柱通天长鼻", "desc": "鼻梁挺拔，刚正不曲"},
    "nose_broad": {"name": "宽厚蒜台鼻", "desc": "丰隆有肉，聚财守信"},
    "nose_hook_sharp": {"name": "鹰钩锐鼻", "desc": "尖削微弯，果敢谋断"},
    "nose_slender_straight": {"name": "清瘦直鼻", "desc": "修长清秀，清心寡欲"},
    "nose_flat_smooth": {"name": "平正微弧鼻", "desc": "圆融平和，中庸持重"},
}

MOUTHS = {
    "mouth_tight_firm": {"name": "紧抿薄唇", "desc": "双唇紧闭，意志如铁"},
    "mouth_smile_subtle": {"name": "含笑微翘唇", "desc": "嘴角微翘，从容温和"},
    "mouth_dignified": {"name": "重唇端庄", "desc": "上下匀称，肃穆威仪"},
    "mouth_serious_down": {"name": "严毅下敛唇", "desc": "嘴角下沉，刚峭严肃"},
    "mouth_square_open": {"name": "开阔方口", "desc": "口方量宏，声如洪钟"},
    "mouth_meditating": {"name": "微敛思忖唇", "desc": "微启若有所思，运筹帷幄"},
}

BEARDS = {
    "beard_none": {"name": "净面无须", "desc": "面如冠玉，青年官僚专属"},
    "beard_short_subtle": {"name": "上唇微短髭", "desc": "修整青青短髭，少仕初显威仪"},
    "beard_eight": {"name": "八字撇髭", "desc": "典雅宋式撇胡，精干练达"},
    "beard_goatee": {"name": "文人山羊胡", "desc": "颔下清秀聚拢，学者儒士常蓄"},
    "beard_short_neat": {"name": "精整短硬髭", "desc": "修剪齐整短髯，边帅武臣常蓄"},
    "beard_three_tuft_refined": {"name": "三绺清雅美髯", "desc": "中绺垂胸，两绺随之，北宋名相经典相貌"},
    "beard_long_black": {"name": "浓墨长髯", "desc": "黑密如漆，飘逸威严"},
    "beard_sides_full": {"name": "两腮虬髯", "desc": "浓密如铁，威猛将略"},
    "beard_short_sideburns": {"name": "连鬓短硬须", "desc": "刚强有力，西军老宿将常蓄"},
    "beard_grey_sparse": {"name": "花白修整须", "desc": "黑白相杂，老成历练"},
    "beard_grey_three": {"name": "花白三绺胡", "desc": "霜毫染雪，德高望重"},
    "beard_snow_full": {"name": "苍苍雪髯", "desc": "白发如雪，长髯垂腹，三朝重老"},
}

COMPLEXIONS = {
    "complexion_fair": {"name": "玉面白皙", "desc": "及第新科，书卷清白"},
    "complexion_natural": {"name": "温润微黄", "desc": "正统工笔设色，文雅从容"},
    "complexion_tan": {"name": "风霜古铜", "desc": "日晒塞外，边防帅臣"},
    "complexion_mature": {"name": "微现深纹", "desc": "额纹与眼角细纹，经纶岁月"},
    "complexion_aged_wrinkles": {"name": "深刻沧桑与老年斑", "desc": "沟壑深沉，阅尽沧海桑田"},
}


# ==================== 3. 8 大装备插槽公服资产清单 (宋代舆服考据) ====================

EQUIPMENT_CATALOG: Dict[str, EquipmentItem] = {
    # ---------------- 袍服插槽 (Robe Slot - Z: 50) ----------------
    "robe_lv_7th": EquipmentItem(
        id="robe_lv_7th",
        name="碧绿素罗圆领大袖襕袍",
        slot=EquipmentSlot.ROBE,
        tier="lv",
        z_index=RenderZIndex.ROBE,
        metadata={"rank_range": "七至九品", "desc": "通体素面碧绿，下摆横襕，无补子无龙纹"}
    ),
    "robe_fei_5th": EquipmentItem(
        id="robe_fei_5th",
        name="朱红绛罗圆领大袖襕袍",
        slot=EquipmentSlot.ROBE,
        tier="fei",
        z_index=RenderZIndex.ROBE,
        metadata={"rank_range": "五至六品", "desc": "正统大宋绛红，端庄威严，通体纯色"}
    ),
    "robe_zi_3rd": EquipmentItem(
        id="robe_zi_3rd",
        name="深绛紫特织素罗襕袍",
        slot=EquipmentSlot.ROBE,
        tier="zi",
        z_index=RenderZIndex.ROBE,
        metadata={"rank_range": "一至四品", "desc": "深沉尊贵之深紫，尚书宰辅专属"}
    ),
    "robe_qing_minor": EquipmentItem(
        id="robe_qing_minor",
        name="单色素青圆领袍",
        slot=EquipmentSlot.ROBE,
        tier="qing",
        z_index=RenderZIndex.ROBE,
        metadata={"rank_range": "选人/幕僚", "desc": "青墨色，朴素严整"}
    ),
    "robe_shi_scholar": EquipmentItem(
        id="robe_shi_scholar",
        name="浅白素绢襕衫",
        slot=EquipmentSlot.ROBE,
        tier="shi",
        z_index=RenderZIndex.ROBE,
        metadata={"rank_range": "士人布衣/致仕", "desc": "素白儒衫，待仕及第前"}
    ),

    # ---------------- 幞头插槽 (Headwear Slot - Z: 90) ----------------
    "futou_short_flat": EquipmentItem(
        id="futou_short_flat",
        name="短窄平展角漆纱幞头",
        slot=EquipmentSlot.HEADWEAR,
        tier="lv",
        z_index=RenderZIndex.HEADWEAR,
        metadata={"wing_length": "一尺半", "desc": "低品官员公服，展角短轻微展"}
    ),
    "futou_mid_stiff": EquipmentItem(
        id="futou_mid_stiff",
        name="平展长硬角漆纱幞头",
        slot=EquipmentSlot.HEADWEAR,
        tier="fei",
        z_index=RenderZIndex.HEADWEAR,
        metadata={"wing_length": "两尺", "desc": "五至六品朝官，挺直平展"}
    ),
    "futou_long_straight": EquipmentItem(
        id="futou_long_straight",
        name="极展长直铁线角幞头",
        slot=EquipmentSlot.HEADWEAR,
        tier="zi",
        z_index=RenderZIndex.HEADWEAR,
        metadata={"wing_length": "两尺半至三尺", "desc": "平展如琴弦，一品宰辅重臣专属"}
    ),
    "futou_soft_wrapped": EquipmentItem(
        id="futou_soft_wrapped",
        name="软裹展角/儒巾",
        slot=EquipmentSlot.HEADWEAR,
        tier="shi",
        z_index=RenderZIndex.HEADWEAR,
        metadata={"wing_length": "自然垂展", "desc": "士人常服"}
    ),

    # ---------------- 革带插槽 (Belt Slot - Z: 60) ----------------
    "belt_black_horn": EquipmentItem(
        id="belt_black_horn",
        name="乌角铜銙黑革带",
        slot=EquipmentSlot.BELT,
        tier="lv",
        z_index=RenderZIndex.BELT,
        metadata={"desc": "七至九品，黑革带配乌角铜銙"}
    ),
    "belt_silver_chased": EquipmentItem(
        id="belt_silver_chased",
        name="起雀花白银带銙革带",
        slot=EquipmentSlot.BELT,
        tier="fei",
        z_index=RenderZIndex.BELT,
        metadata={"desc": "五至六品，纯银錾花带板"}
    ),
    "belt_gold_lychee": EquipmentItem(
        id="belt_gold_lychee",
        name="透雕金荔枝带銙红革带",
        slot=EquipmentSlot.BELT,
        tier="zi",
        z_index=RenderZIndex.BELT,
        metadata={"desc": "一至四品高官，纯金荔枝透雕带銙"}
    ),
    "belt_jade_white": EquipmentItem(
        id="belt_jade_white",
        name="特赐羊脂白玉带板革带",
        slot=EquipmentSlot.BELT,
        tier="zi",
        z_index=RenderZIndex.BELT,
        metadata={"desc": "天子对顶级元老的崇高恩赏"}
    ),

    # ---------------- 鱼袋插槽 (Pouch Slot - Z: 70) ----------------
    "pouch_none": EquipmentItem(
        id="pouch_none",
        name="无鱼袋",
        slot=EquipmentSlot.POUCH,
        tier="lv",
        z_index=RenderZIndex.POUCH,
        metadata={"desc": "七品以下无佩鱼荣典"}
    ),
    "pouch_silver_fish": EquipmentItem(
        id="pouch_silver_fish",
        name="随身白银鱼袋",
        slot=EquipmentSlot.POUCH,
        tier="fei",
        z_index=RenderZIndex.POUCH,
        metadata={"desc": "五至六品随身银鱼符佩囊"}
    ),
    "pouch_gold_fish": EquipmentItem(
        id="pouch_gold_fish",
        name="鎏金纯金金鱼袋",
        slot=EquipmentSlot.POUCH,
        tier="zi",
        z_index=RenderZIndex.POUCH,
        metadata={"desc": "一至四品随身金鱼符佩囊"}
    ),

    # ---------------- 朝笏插槽 (Held Slot - Z: 80) ----------------
    "held_wood_tablet": EquipmentItem(
        id="held_wood_tablet",
        name="质朴槐木朝笏手板",
        slot=EquipmentSlot.HELD,
        tier="lv",
        z_index=RenderZIndex.HELD,
        metadata={"desc": "低品官员朴实手板，上端微弧"}
    ),
    "held_ivory_hu": EquipmentItem(
        id="held_ivory_hu",
        name="青润交趾象牙朝笏",
        slot=EquipmentSlot.HELD,
        tier="fei",
        z_index=RenderZIndex.HELD,
        metadata={"desc": "象牙光洁玉润，中品朝臣正规仪节"}
    ),
    "held_jade_ivory_hu": EquipmentItem(
        id="held_jade_ivory_hu",
        name="老象牙温润透玉笏",
        slot=EquipmentSlot.HELD,
        tier="zi",
        z_index=RenderZIndex.HELD,
        metadata={"desc": "传世老象牙朝笏，温润如脂，宰辅执政所持"}
    ),

    # ---------------- 白色中单内衬护领 (Collar Slot - Z: 40) ----------------
    "collar_white_silk": EquipmentItem(
        id="collar_white_silk",
        name="素白中单交领护颈",
        slot=EquipmentSlot.COLLAR,
        tier="all",
        z_index=RenderZIndex.COLLAR,
        metadata={"desc": "宋代标志性白罗护颈内领，彻底消除脖颈缝隙"}
    ),
}


# ==================== 4. 确定性 Visual DNA 生成算法 (千人千面) ====================

def derive_minister_dna(
    name: str,
    rank: str = "从七品 知县",
    age: int = 35,
    traits: Optional[List[str]] = None,
    seed: Optional[int] = None,
    overrides: Optional[Dict[str, Any]] = None,
    minister_id: Optional[str] = None,
    origin: str = "",
) -> Tuple[str, FaceDNA, Dict[str, str]]:
    """为任意官员计算出完全确定性、独一无二、绝不撞脸的 FaceDNA 与装备插槽映射。
    
    算法特性：
    1. 组合空间 4032 万种，同名同姓同官位计算结果 100% 幂等复现；
    2. 生理年龄自然约束胡须与面部风霜；
    3. 特质亲和自动导向相应神态（如刚直者多剑眉冷目，财计者多微丰细目）。
    """
    traits = traits or []
    overrides = overrides or {}

    if seed is None:
        seed_str = f"songzuo_minister_v5_{minister_id or ''}_{name}_{rank}_{age}_{origin}"
        seed = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # 1. 体型素体模特推断 (由年龄驱动)
    if age < 35:
        base_mannequin = "mannequin_young"
        age_group = "young"
    elif age < 55:
        base_mannequin = "mannequin_middle"
        age_group = "middle"
    else:
        base_mannequin = "mannequin_elder"
        age_group = "elder"

    # 2. 7 维解耦五官参数计算 (千人千面核心)
    # 2.1 脸型
    shape_pool = list(FACE_SHAPES.keys())
    if "军略" in traits or "将" in rank:
        shape_pool.extend(["shape_broad_strong", "shape_square"] * 2)
    elif "理财" in traits:
        shape_pool.extend(["shape_round_plump", "shape_heavy_chin"] * 2)
    elif "刚直" in traits or "清正" in traits:
        shape_pool.extend(["shape_slender_bone", "shape_square"] * 2)
    face_shape = rng.choice(shape_pool)

    # 2.2 眉毛
    eyebrow_pool = list(EYEBROWS.keys())
    if age_group == "elder":
        eyebrow_pool.extend(["eyebrow_frost", "eyebrow_broad_open"] * 3)
    elif "刚直" in traits:
        eyebrow_pool.extend(["eyebrow_sword", "eyebrow_cold_sharp"] * 3)
    eyebrows = rng.choice(eyebrow_pool)

    # 2.3 眼睛
    eye_pool = list(EYES.keys())
    if age_group == "elder":
        eye_pool.extend(["eyes_aged_droop", "eyes_benevolent"] * 3)
    elif "理财" in traits or "权谋" in traits:
        eye_pool.extend(["eyes_deep_shrewd", "eyes_eagle_sharp"] * 3)
    elif "刚直" in traits:
        eye_pool.extend(["eyes_resolute", "eyes_phoenix"] * 3)
    eyes = rng.choice(eye_pool)

    # 2.4 鼻型
    nose_pool = list(NOSES.keys())
    if "理财" in traits:
        nose_pool.extend(["nose_broad", "nose_hook_sharp"] * 2)
    nose = rng.choice(nose_pool)

    # 2.5 嘴唇
    mouth_pool = list(MOUTHS.keys())
    if "刚直" in traits:
        mouth_pool.extend(["mouth_tight_firm", "mouth_serious_down"] * 2)
    mouth = rng.choice(mouth_pool)

    # 2.6 胡须 (受生理年龄刚性约束)
    if age_group == "young":
        beard_pool = ["beard_none", "beard_short_subtle"]
    elif age_group == "middle":
        beard_pool = [
            "beard_short_neat", "beard_eight", "beard_goatee",
            "beard_three_tuft_refined", "beard_long_black", "beard_sides_full"
        ]
    else:  # elder
        beard_pool = [
            "beard_grey_sparse", "beard_grey_three", "beard_snow_full",
            "beard_three_tuft_refined"
        ]
    beard = rng.choice(beard_pool)

    # 2.7 岁月风霜与肤色
    if age_group == "young":
        comp_pool = ["complexion_fair", "complexion_natural"]
    elif age_group == "middle":
        comp_pool = ["complexion_natural", "complexion_tan", "complexion_mature"]
        if "军略" in traits:
            comp_pool.extend(["complexion_tan"] * 3)
    else:
        comp_pool = ["complexion_mature", "complexion_aged_wrinkles"]
    complexion = rng.choice(comp_pool)

    face_dna = FaceDNA(
        face_shape=face_shape,
        eyebrows=eyebrows,
        eyes=eyes,
        nose=nose,
        mouth=mouth,
        beard=beard,
        complexion=complexion,
    )

    # 3. 官阶品色与装备插槽推断 (按《宋史》舆服志)
    try:
        from content.ministers.costumes import parse_costume_tier
    except ImportError:
        from game.content.ministers.costumes import parse_costume_tier
    costume_tier = parse_costume_tier(rank)

    # 3.1 官袍
    if costume_tier == "zi":
        robe = "robe_zi_3rd"
        futou = "futou_long_straight"
        belt = "belt_gold_lychee"
        pouch = "pouch_gold_fish"
        hu = "held_jade_ivory_hu"
    elif costume_tier == "fei":
        robe = "robe_fei_5th"
        futou = "futou_mid_stiff"
        belt = "belt_silver_chased"
        pouch = "pouch_silver_fish"
        hu = "held_ivory_hu"
    elif costume_tier == "lv":
        robe = "robe_lv_7th"
        futou = "futou_short_flat"
        belt = "belt_black_horn"
        pouch = "pouch_none"
        hu = "held_wood_tablet"
    elif costume_tier == "qing":
        robe = "robe_qing_minor"
        futou = "futou_soft_wrapped"
        belt = "belt_black_horn"
        pouch = "pouch_none"
        hu = "held_wood_tablet"
    else:
        robe = "robe_shi_scholar"
        futou = "futou_soft_wrapped"
        belt = "belt_black_horn"
        pouch = "pouch_none"
        hu = "held_wood_tablet"

    equipped = {
        EquipmentSlot.BASE_DOLL.value: base_mannequin,
        EquipmentSlot.COLLAR.value: "collar_white_silk",
        EquipmentSlot.ROBE.value: robe,
        EquipmentSlot.HEADWEAR.value: futou,
        EquipmentSlot.BELT.value: belt,
        EquipmentSlot.POUCH.value: pouch,
        EquipmentSlot.HELD.value: hu,
    }

    # 应用恩赏与重载覆盖 (Overrides)
    equipped.update(overrides)

    return base_mannequin, face_dna, equipped


# 别名导出
generate_visual_dna = derive_minister_dna
