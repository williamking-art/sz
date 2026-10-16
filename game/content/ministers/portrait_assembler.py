# -*- coding: utf-8 -*-
"""北宋官员公服 RPG 模块化立绘装配引擎与多脸谱复用框架。

## 规格与背景（Jev 裁定：JEV-台账-模块化官员公服立绘装配引擎与多脸谱复用重构-2026-10-16）

解决北宋职官系统数百位官员（中枢43位、21路监司126席位、136州府知通272席位、后期科举及第知县）
仅有 43 张固定脸的问题。将立绘彻底解耦为 8 大可复用模块化图层：
1. 底色：院体工笔老绢本底色纹理（#C4A877）；
2. 身躯：姿态（持笏/拱手/拢袖/端立）× 服色（紫/绯/绿/青/士人/亲王）；
3. 脸模：脸型（清瘦/方正/温润/清俊/清癯）× 年龄（青年/中年/老成）；
4. 髯口：独立胡须层（无须/短髭/山羊胡/三绺美髯/长黑髯/花白须/苍白长髯）；
5. 幞头：漆纱幞头展脚（极展长直角两尺半/平展长角两尺/短平角一尺半/软裹折角）；
6. 革带：带銙（白玉带/荔枝金带/起雀花银带/乌角铜带）；
7. 佩饰：鱼袋（金鱼袋/银鱼袋/无鱼袋）；
8. 手持：朝笏（透润象牙玉笏/青润象牙笏/质朴槐木笏）。

通过官员 Visual DNA 算法对任意非名臣进行确定性装配，产生 360 万+ 种严合宋制的生动组合；
对 43 位中枢历史名臣则优先锁定其历史考据工笔头面。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("portrait_assembler")

# 目录路径定义
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
LAYERS_DIR = os.path.join(MODULE_DIR, "layers")
COMPOSED_DIR = os.path.join(MODULE_DIR, "portraits", "_composed")

# 43 位中枢历史名臣列表（专属脸模豁免）
from content.ministers.stats import HISTORICAL_MINISTER_STATS

# 脸型模型定义（Face Base）
FACE_MODELS = {
    "scholar": {
        "name": "清俊修竹",
        "desc": "玉面明眸，清俊俊朗，多见于新科及第少年进士、翰林词臣",
        "suitable_ages": ["young", "middle"],
        "trait_affinity": ["才艺", "文雅", "清流"],
    },
    "slender": {
        "name": "清瘦刚骨",
        "desc": "颧骨微显，面容清矍，刚正不阿，典型台谏御史与清修诤臣",
        "suitable_ages": ["young", "middle", "elder"],
        "trait_affinity": ["刚直", "清正", "敢言", "风宪"],
    },
    "square": {
        "name": "方正刚毅",
        "desc": "面如重枣，重眉阔目，威严肃杀，典型边防将领、帅司与提刑官",
        "suitable_ages": ["middle", "elder"],
        "trait_affinity": ["军略", "忠勇", "果断", "宿将"],
    },
    "round": {
        "name": "温润雍容",
        "desc": "面容丰腴，耳大颐丰，富态从容，多见于度支转运官、内省重臣与循吏",
        "suitable_ages": ["middle", "elder"],
        "trait_affinity": ["理财", "聚敛", "吏干", "调停"],
    },
    "veteran": {
        "name": "苍老清癯",
        "desc": "须眉染霜，沟壑深沉，阅尽沧桑，典型历经数朝的三朝元老与耆宿知州",
        "suitable_ages": ["elder"],
        "trait_affinity": ["老成", "持重", "老练"],
    },
}

# 髯口胡须层（Beard）
BEARDS = {
    "none": {"name": "无须净面", "suitable_ages": ["young"]},
    "short": {"name": "修整短髭", "suitable_ages": ["young", "middle"]},
    "goatee": {"name": "文士山羊胡", "suitable_ages": ["middle", "elder"]},
    "three_tuft": {"name": "三绺美髯", "suitable_ages": ["middle", "elder"]},
    "long_black": {"name": "浓密长墨髯", "suitable_ages": ["middle"]},
    "long_grey": {"name": "花白长髯", "suitable_ages": ["elder"]},
    "long_white": {"name": "苍髯如雪", "suitable_ages": ["elder"]},
}

# 漆纱幞头展脚（Headwear）
FUTOU_TIERS = {
    "long":  {"name": "极展长直铁线角", "desc": "长两尺半至三尺，平展如弦，一品宰执与枢密重臣专用"},
    "mid":   {"name": "平展长硬脚",     "desc": "长两尺余，横平挺秀，五至六品中品朝官与大郡知府"},
    "short": {"name": "短窄平角",       "desc": "长一尺半，轻便微展，七至九品通判知县公服"},
    "soft":  {"name": "软裹展角/儒巾",  "desc": "自然垂展，士人常服与待仕进士使用"},
}

# 官袍服色（Robes）
ROBE_TIERS = {
    "zi":      {"name": "绛紫素罗襕袍", "ranks": "一至四品"},
    "fei":     {"name": "朱红绛罗襕袍", "ranks": "五至六品"},
    "lv":      {"name": "碧绿素罗襕袍", "ranks": "七至九品"},
    "qing":    {"name": "青色单色素袍", "ranks": "选人/流外"},
    "qinwang": {"name": "亲王深赤服",   "ranks": "宗室皇子"},
    "shi":     {"name": "浅白素绢襕衫", "ranks": "士人白身/致仕"},
}

# 5 大核心 3D 动作姿态（3D Poses）
POSES = ["chihu", "gongshou", "longxiu", "fuxu", "anjian"]

# 3D 转 2D 布娃娃人形模板库（Dolls Catalog）
DOLL_CATALOG = {
    # 青年层（20~35 岁 · 少壮及第）
    "doll_y_scholar":   {"age_group": "young",  "face": "scholar", "desc": "清俊修竹，玉面无须，儒雅英挺，书卷之气"},
    "doll_y_resolute":  {"age_group": "young",  "face": "square",  "desc": "少年意气，英武方额，浓眉目朗，刚毅敢为"},
    "doll_y_pragmatic": {"age_group": "young",  "face": "round",   "desc": "朴厚精整，端庄温润，循序渐进"},

    # 中年层（36~50 岁 · 骨干中坚）
    "doll_m_slender":   {"age_group": "middle", "face": "slender", "desc": "清瘦刚直，双眸如炬，蓄文人短髭，铁骨御史"},
    "doll_m_square":    {"age_group": "middle", "face": "square",  "desc": "方阔重颌，浓眉直鼻，蓄刚正美髯，经略帅臣"},
    "doll_m_round":     {"age_group": "middle", "face": "round",   "desc": "丰腴温润，耳大颐满，蓄精修短髭，财赋度支"},
    "doll_m_counselor": {"age_group": "middle", "face": "scholar", "desc": "眉清目秀，深思熟虑，纵横机变机敏谋士"},

    # 老年层（51~75+ 岁 · 耆宿元老）
    "doll_e_veteran":   {"age_group": "elder",  "face": "veteran", "desc": "苍老清癯，额刻沧桑，长髯飘逸雪白，一代宗师"},
    "doll_e_round":     {"age_group": "elder",  "face": "round",   "desc": "雍容从容，天庭饱满，三绺花白美髯，元老宰辅"},
    "doll_e_iron":      {"age_group": "elder",  "face": "square",  "desc": "白发苍苍而目光如铁，老当益壮，百战宿将"},
}


def derive_official_visual_dna(name: str, rank: str = "", costume_tier: str = "",
                               traits: Optional[List[str]] = None,
                               age: int = 42,
                               favor_equipment: Optional[Dict[str, Any]] = None,
                               seed: Optional[int] = None) -> Dict[str, Any]:
    """为任意官员生成唯一且确定性的视觉装配 DNA（Visual DNA）。
    
    43 位历史名臣保留专属头面，其余官员由种子哈希算法衍生出独一无二的
    3D转2D布娃娃人形底模（Doll）与动作姿态，并严格按官阶/恩赏穿戴宋代服饰部件。
    """
    traits = traits or []
    favor_equipment = favor_equipment or {}

    # 1. 确定服色层级（costume_tier）
    if not costume_tier:
        from content.ministers.costumes import parse_costume_tier
        costume_tier = parse_costume_tier(rank)

    # 2. 检查是否为 43 位历史名臣
    is_historical = name in HISTORICAL_MINISTER_STATS

    # 3. 确定性种子计算
    if seed is None:
        seed = int(hashlib.md5(f"songzuo_dna_{name}_{rank}".encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # 4. 年龄段划分（青年/中年/老年）
    if age < 35:
        age_group = "young"
    elif age < 52:
        age_group = "middle"
    else:
        age_group = "elder"

    # 5. 脸型与布娃娃匹配
    if is_historical:
        face_model = f"hist_{name}"
        beard = "historical"
        doll_id = f"hist_{name}"
    else:
        # 按特质偏好评分
        candidates = []
        for f_key, f_spec in FACE_MODELS.items():
            if age_group not in f_spec["suitable_ages"]:
                continue
            weight = 10
            for t in traits:
                if any(aff in t for aff in f_spec["trait_affinity"]):
                    weight += 25
            candidates.extend([f_key] * weight)
        face_model = rng.choice(candidates) if candidates else "slender"

        # 胡须匹配（受年龄与脸型约束）
        beard_candidates = []
        for b_key, b_spec in BEARDS.items():
            if age_group in b_spec["suitable_ages"]:
                weight = 10
                if face_model == "scholar" and b_key in ("none", "short"):
                    weight += 20
                elif face_model == "square" and b_key in ("short", "long_black"):
                    weight += 20
                elif age_group == "elder" and b_key in ("long_grey", "long_white", "goatee"):
                    weight += 30
                beard_candidates.extend([b_key] * weight)
        beard = rng.choice(beard_candidates) if beard_candidates else "short"

        # 分配布娃娃底模 ID
        doll_candidates = [
            d_id for d_id, d_spec in DOLL_CATALOG.items()
            if d_spec["age_group"] == age_group and d_spec["face"] == face_model
        ]
        doll_id = rng.choice(doll_candidates) if doll_candidates else f"doll_{age_group}_{face_model}"

    # 6. 3D 动作姿态推断（持笏/拱揖/长袖/抚须/按剑）
    if any(k in rank for k in ("帅", "经略", "节度", "统制", "将")):
        # 武将/帅臣偏向按剑持节与持笏
        pose_pool = ["anjian", "chihu", "gongshou"]
    elif any(k in rank for k in ("尚书", "门下", "中书", "宰相", "仆射", "参政")):
        # 宰执重臣偏向长袖雍容与抚须深思
        pose_pool = ["longxiu", "fuxu", "chihu"]
    elif any(k in rank for k in ("台", "谏", "御史", "给事", "提刑")):
        # 言官台谏法吏偏向拱手作揖与持笏
        pose_pool = ["chihu", "gongshou"]
    elif age_group == "elder":
        # 老臣长者偏向抚须与长袖
        pose_pool = ["fuxu", "longxiu", "gongshou"]
    elif age_group == "young":
        # 青年及第新官偏向持笏与拱手
        pose_pool = ["chihu", "gongshou"]
    else:
        pose_pool = POSES
    pose = rng.choice(pose_pool)

    # 7. 部件与恩赏覆盖
    # 幞头
    if costume_tier in ("zi", "qinwang"):
        futou = "long"
    elif costume_tier == "fei":
        futou = "mid"
    elif costume_tier == "lv":
        futou = "short"
    else:
        futou = "soft"

    # 腰带
    if "waist" in favor_equipment:
        belt_raw = favor_equipment["waist"].get("name", "")
        if "玉" in belt_raw:
            belt = "jade"
        elif "金" in belt_raw:
            belt = "gold"
        elif "银" in belt_raw:
            belt = "silver"
        else:
            belt = "horn"
    else:
        if costume_tier == "zi":
            belt = "gold"
        elif costume_tier == "fei":
            belt = "silver"
        else:
            belt = "horn"

    # 鱼袋
    if "accessory" in favor_equipment:
        acc_raw = favor_equipment["accessory"].get("name", "")
        if "金鱼" in acc_raw:
            fish = "gold"
        elif "银鱼" in acc_raw:
            fish = "silver"
        else:
            fish = "none"
    else:
        if costume_tier == "zi":
            fish = "gold"
        elif costume_tier == "fei":
            fish = "silver"
        else:
            fish = "none"

    # 朝笏
    if "held" in favor_equipment:
        h_raw = favor_equipment["held"].get("name", "")
        if "玉" in h_raw or "老象牙" in h_raw:
            hu = "jade_ivory"
        elif "象牙" in h_raw:
            hu = "ivory"
        else:
            hu = "wood"
    else:
        if costume_tier == "zi":
            hu = "jade_ivory"
        elif costume_tier == "fei":
            hu = "ivory"
        else:
            hu = "wood"

    dna_dict = {
        "name": name,
        "is_historical": is_historical,
        "doll_id": doll_id,
        "age": age,
        "age_group": age_group,
        "face_model": face_model,
        "beard": beard,
        "costume_tier": costume_tier,
        "pose": pose,
        "futou": futou,
        "belt": belt,
        "fish_pouch": fish,
        "hu_tablet": hu,
        "dna_hash": hashlib.md5(f"{name}_{doll_id}_{face_model}_{beard}_{costume_tier}_{pose}_{futou}_{belt}_{fish}_{hu}".encode("utf-8")).hexdigest()[:12],
    }
    return dna_dict


def assemble_official_portrait(dna: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """根据官员 Visual DNA 进行 8 大独立透明装备槽位动态装配并输出。
    
    输出规格：严格统一 810×1080 3:4 比例大半身像，院体工笔老绢本底色 (#C4A877)。
    标准 RPG 纸娃娃层叠流水线（从底到顶）：
      1. 老绢底画布 (Silk Canvas)
      2. 基础人形素体 (Base Doll)
      3. 五官面模 (Face Model)
      4. 胡须髯口 (Beard)
      5. 官制袍服 (Robe)
      6. 公服革带 (Belt)
      7. 随身鱼袋 (Fish Pouch)
      8. 朝笏手板 (Held Hu)
      9. 漆纱幞头官帽 (Futou Hat)
    """
    name = dna.get("name", "官员")
    dna_hash = dna.get("dna_hash", "default")
    is_historical = dna.get("is_historical", False)
    costume_tier = dna.get("costume_tier", "lv")
    pose = dna.get("pose", "chihu")
    face_model = dna.get("face_model", "scholar")
    beard = dna.get("beard", "none")
    futou = dna.get("futou", "short")
    belt = dna.get("belt", "horn")
    fish_pouch = dna.get("fish_pouch", "none")
    hu_tablet = dna.get("hu_tablet", "wood")

    os.makedirs(COMPOSED_DIR, exist_ok=True)
    if not output_path:
        output_path = os.path.join(COMPOSED_DIR, f"{name}_{dna_hash}.png")

    # 优先复用缓存
    if os.path.isfile(output_path):
        return output_path

    try:
        from PIL import Image
    except ImportError:
        log.warning("PIL 未安装，无法执行图像分层拼合")
        return ""

    canvas_w, canvas_h = 810, 1080
    bg_color = (196, 168, 119)  # #C4A877 老绢本底色

    # 1. 创建绢底画布
    composed_img = Image.new("RGBA", (canvas_w, canvas_h), (*bg_color, 255))

    def _composite_layer(sub_dir: str, filename: str) -> bool:
        """安全复合单个透明装备图层。"""
        p = os.path.join(LAYERS_DIR, sub_dir, filename)
        if os.path.isfile(p):
            try:
                layer_im = Image.open(p).convert("RGBA")
                if layer_im.size != (canvas_w, canvas_h):
                    layer_im = layer_im.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
                composed_img.alpha_composite(layer_im)
                return True
            except Exception as e:
                log.warning(f"复合图层失败 {p}: {e}")
        return False

    # 2. 检查是否使用模块化独立装备图层 (Paper Doll Architecture)
    doll_file = f"doll_{pose}.png" if os.path.isfile(os.path.join(LAYERS_DIR, "dolls", f"doll_{pose}.png")) else "doll_chihu.png"
    has_doll = _composite_layer("dolls", doll_file)

    # 3. 挂载五官面貌 (Face Model)
    if is_historical:
        # 名臣专属头面
        hist_head = os.path.join(LAYERS_DIR, f"head_{name}.png")
        if os.path.isfile(hist_head):
            head_im = Image.open(hist_head).convert("RGBA")
            if head_im.size != (canvas_w, canvas_h):
                head_im = head_im.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
            composed_img.alpha_composite(head_im)
    else:
        # 通用官员面模
        face_file = f"face_{face_model}.png"
        if not _composite_layer("faces", face_file):
            _composite_layer("faces", "face_scholar.png")

        # 4. 挂载胡须 (Beard)
        beard_file = f"beard_{beard}.png"
        _composite_layer("beards", beard_file)

    # 5. 挂载官制袍服 (Robe)
    robe_file = f"robe_{pose}_{costume_tier}.png"
    if not _composite_layer("robes", robe_file):
        # 兜底旧图层
        body_file = f"body_{pose}_{costume_tier}.png"
        body_path = os.path.join(LAYERS_DIR, body_file)
        if not os.path.isfile(body_path):
            body_path = os.path.join(LAYERS_DIR, f"body_chihu_{costume_tier}.png")
        if os.path.isfile(body_path):
            old_body = Image.open(body_path).convert("RGBA")
            if old_body.size != (canvas_w, canvas_h):
                old_body = old_body.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
            composed_img.alpha_composite(old_body)

    # 6. 挂载公服革带 (Belt)
    _composite_layer("belts", f"belt_{belt}.png")

    # 7. 挂载随身鱼袋 (Fish Pouch)
    if fish_pouch and fish_pouch != "none":
        _composite_layer("pouches", f"pouch_{fish_pouch}.png")

    # 8. 挂载朝笏手板 (Held Hu)
    _composite_layer("held", f"held_{hu_tablet}.png")

    # 9. 挂载漆纱幞头 (Futou Hat - 顶层，帽口自然压在额前发际线上)
    if not is_historical:
        _composite_layer("futou", f"futou_{futou}.png")

    # 10. 保存为无损 PNG（与绢底完全贴合，标准 810×1080）
    final_rgb = Image.new("RGB", (canvas_w, canvas_h), bg_color)
    final_rgb.paste(composed_img, (0, 0), composed_img)
    final_rgb.save(output_path, "PNG")
    log.info(f"成功装配纯透明装备层叠官员立绘: {output_path} (DNA: {dna_hash})")

    return output_path


def generate_modular_component_prompts() -> Dict[str, Any]:
    """生成用于 AI 生图工具批量生产独立可复用美术部件的 Prompt 矩阵。"""
    prompts = {
        "face_bases": {},
        "futou": {},
        "beards": {},
        "belts": {},
        "fish_pouches": {},
        "hu_tablets": {},
    }

    style_prefix = "Traditional Chinese Northern Song Dynasty court portrait, gongbi painting on antique raw silk canvas (#C4A877), isolated element on pure transparent background, masterwork brushwork, museum artifact realism"

    # 脸模 Prompts
    for f_key, f_spec in FACE_MODELS.items():
        prompts["face_bases"][f_key] = {
            "name": f_spec["name"],
            "desc": f_spec["desc"],
            "prompt_en": f"{style_prefix}, head and neck portrait of a Song Dynasty male scholar official, {f_spec['desc']}, highly refined facial expression, calm and dignified, strictly no hat, bald or topknot on clean transparent background --ar 3:4 --style raw --v 6.1",
            "prompt_cn": f"北宋院体工笔设色绢本。宋代官员头部肖像，{f_spec['desc']}，神态沉稳肃穆，不戴官帽，透明背景，大师级线条。",
        }

    # 幞头展脚 Prompts
    for f_tier, f_info in FUTOU_TIERS.items():
        prompts["futou"][f_tier] = {
            "name": f_info["name"],
            "prompt_en": f"{style_prefix}, authentic Northern Song Dynasty black lacquered gauze futou hat, {f_info['desc']}, horizontal stiff flat wings, isolated object on pure transparent background, museum grade historical costume accuracy --ar 3:4 --style raw",
            "prompt_cn": f"北宋漆纱幞头官帽，{f_info['desc']}，左右展脚刚直平展，纯黑细纱蒙裱，透明背景。",
        }

    # 鱼袋 Prompts
    prompts["fish_pouches"]["gold"] = {
        "name": "金鱼袋",
        "prompt_en": f"{style_prefix}, Northern Song court official golden fish pouch (yudai), ornate chased pure gold leather pouch with fish tally, hanging strap, museum relic --ar 1:1 --style raw",
        "prompt_cn": "北宋一至四品紫袍金鱼袋，纯金錾花皮匣佩囊，挂带完备，宋代符契规制，透明底。",
    }
    prompts["fish_pouches"]["silver"] = {
        "name": "银鱼袋",
        "prompt_en": f"{style_prefix}, Northern Song court official silver fish pouch (yudai), chased sterling silver plaques, white silver fish tally, hanging strap --ar 1:1 --style raw",
        "prompt_cn": "北宋五至六品绯袍银鱼袋，白银锁扣皮匣佩囊，透明底。",
    }

    # 朝笏 Prompts
    prompts["hu_tablets"]["ivory"] = {
        "name": "青润象牙朝笏",
        "prompt_en": f"{style_prefix}, Northern Song Dynasty ivory hu tablet, smooth lustrous off-white elephant tusk, held vertically in court ceremonies --ar 1:3 --style raw",
        "prompt_cn": "北宋交趾象牙朝笏手板，质地光润平挺，微有弧度，透明底。",
    }
    prompts["hu_tablets"]["wood"] = {
        "name": "质朴槐木笏",
        "prompt_en": f"{style_prefix}, Northern Song Dynasty plain locust wood hu tablet, simple dark grain wood court tablet --ar 1:3 --style raw",
        "prompt_cn": "北宋低品官员槐木质朴手板，木纹朴实端整，透明底。",
    }

    return prompts
