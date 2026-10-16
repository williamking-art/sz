# -*- coding: utf-8 -*-
"""宋代官员服饰装备系统（RPG Equipment System）。

基于北宋元丰改制后的正统公服/常服制度，将官员外观结构化为 6 大装备槽位：
- 头部（Head）：展脚幞头（直脚漆纱）
- 身躯（Torso）：圆领大袖襕袍（纯色素面无纹）
- 腰间（Waist）：革带与带銙（黑角/铜/银/金/玉）
- 佩饰（Accessory）：随身鱼袋（无/银鱼袋/金鱼袋）
- 手持（Held）：朝笏（竹木/象牙）
- 足部（Feet）：乌皮靴（黑革薄底平头六缝靴）

品级三档：
- 低品（lv）：七至九品（绿袍、短展脚幞头、角铜带、无鱼袋、木笏、乌皮靴）
- 中品（fei）：五至六品（绯袍、平展长脚幞头、银銙带、银鱼袋、初阶象笏、乌皮靴）
- 高品（zi）：一至四品（紫袍、极展长脚幞头、金玉带、金鱼袋、通透象牙笏、鹿皮乌靴）

严禁使用：明代补子、龙纹、明清官帽、厚白戏靴等时代错位元素。
"""
from __future__ import annotations

from typing import Dict, Any, Optional

# 装备部件定义
EQUIPMENT_TIERS: Dict[str, Dict[str, Any]] = {
    "lv": {
        "tier_key": "lv",
        "rank_name": "低品公服（七至九品）",
        "color_name": "青绿",
        "head": {
            "name": "短展脚漆纱幞头",
            "desc": "竹篾软铁为骨，黑细纱蒙裱，两侧展脚短窄微平，平直内敛。",
            "material": "漆纱/竹篾",
            "tier": "低品",
        },
        "robe": {
            "name": "碧绿素面圆领襕袍",
            "desc": "草绿/豆绿单色素罗，宽袖圆领，下摆有一道横襕，纯素无纹，绝无补子与龙纹。",
            "color": "#2E7D32",
            "material": "素罗",
            "tier": "低品",
        },
        "belt": {
            "name": "黑角铜銙革带",
            "desc": "黑熟皮带身，镶缀质朴乌角与青铜方圆带板，朴实规整。",
            "material": "乌角/青铜/黑革",
            "tier": "低品",
        },
        "fish_pouch": {
            "name": "空缺（不入佩鱼之列）",
            "desc": "宋制七品以下官员不佩鱼袋。",
            "material": "无",
            "tier": "无",
        },
        "hu_tablet": {
            "name": "削槐质朴木笏",
            "desc": "槐木或厚竹磨制而成，平头直刃，天然木纹，双手肃立端奉。",
            "material": "槐木/竹",
            "tier": "低品",
        },
        "boots": {
            "name": "薄底乌皮六缝靴",
            "desc": "熟牛皮缝制，黑漆面，薄革底，平头微圆。",
            "material": "牛皮",
            "tier": "低品",
        },
    },
    "fei": {
        "tier_key": "fei",
        "rank_name": "中品公服（五至六品）",
        "color_name": "朱绯",
        "head": {
            "name": "平展硬脚黑漆幞头",
            "desc": "铁线展脚平直刚挺，长两尺余，水平横展，漆黑如镜。",
            "material": "铁线/漆纱",
            "tier": "中品",
        },
        "robe": {
            "name": "朱红纯素圆领襕袍",
            "desc": "正红/绛红精织素面罗，宽袖大领，通体纯色，无任何方块补子或刺绣。",
            "color": "#C62828",
            "material": "绛罗",
            "tier": "中品",
        },
        "belt": {
            "name": "隐花银銙黑革带",
            "desc": "黑鹿皮革带，排缀十三至十九枚雕花白银带銙，起雀花纹。",
            "material": "白银/鹿皮",
            "tier": "中品",
        },
        "fish_pouch": {
            "name": "白银鱼袋（银鱼符）",
            "desc": "革带右侧悬挂皮质鱼袋囊，底缀白银锁扣，内贮银鱼符，标志五六品章服。",
            "material": "白银/熟皮",
            "tier": "中品",
        },
        "hu_tablet": {
            "name": "青润微直象牙朝笏",
            "desc": "产自交趾真象牙，质密如脂，牙白微润，平整修长。",
            "material": "象牙",
            "tier": "中品",
        },
        "boots": {
            "name": "熟羊皮平底乌皮靴",
            "desc": "软熟黑羊皮面，内衬白绢，六缝合纳，漆黑笔挺。",
            "material": "羊皮",
            "tier": "中品",
        },
    },
    "zi": {
        "tier_key": "zi",
        "rank_name": "高品公服（一至四品）",
        "color_name": "紫金",
        "head": {
            "name": "极展长直角黑纱幞头",
            "desc": "熟铜铁线精撑，平直如弦，长达二尺半至三尺，横平挺括，极显威仪。",
            "material": "精铜/漆细纱",
            "tier": "高品",
        },
        "robe": {
            "name": "深绛紫特织素面襕袍",
            "desc": "沉稳深邃紫罗，通体纯素，典雅至极，走动时折射内敛丝缎反光，无任何杂饰。",
            "color": "#4A148C",
            "material": "特织绛紫罗",
            "tier": "高品",
        },
        "belt": {
            "name": "荔枝金带 / 羊脂白玉带",
            "desc": "朱红革身缀纯金透雕荔枝带銙，或温润羊脂白玉带板，极品重臣之器。",
            "material": "纯金/白玉/红革",
            "tier": "高品",
        },
        "fish_pouch": {
            "name": "鎏金金鱼袋（紫袍金鱼）",
            "desc": "悬挂于右肋，囊裹金丝绣，佩纯金鱼符与金锁扣，特赐重臣顶级荣典。",
            "material": "纯金/金丝皮囊",
            "tier": "高品",
        },
        "hu_tablet": {
            "name": "透润老象牙玉笏",
            "desc": "整根老象牙心雕琢，两头微阔，微弧通透，温润如羊脂玉，端奉心口。",
            "material": "极品老象牙",
            "tier": "高品",
        },
        "boots": {
            "name": "精熟鹿皮乌缎靴",
            "desc": "熟鹿皮为里，黑羽缎为面，轻软笔挺，薄平黑底。",
            "material": "鹿皮/乌缎",
            "tier": "高品",
        },
    },
    "shi": {
        "tier_key": "shi",
        "rank_name": "在野白襕衫（士人）",
        "color_name": "素白",
        "head": {
            "name": "折上巾 / 东坡巾",
            "desc": "士人布巾或东坡巾，文雅洒脱。",
            "material": "黑布/漆纱",
            "tier": "布衣",
        },
        "robe": {
            "name": "象牙白素面襕衫",
            "desc": "本色白细布长衫，圆领大袖，底缀一道青黑横襕。",
            "color": "#F5F5F5",
            "material": "棉麻/细绢",
            "tier": "布衣",
        },
        "belt": {
            "name": "青丝大带",
            "desc": "青黑丝绦博带，垂双穗于前。",
            "material": "丝绦",
            "tier": "布衣",
        },
        "fish_pouch": {"name": "无", "desc": "士人无鱼袋", "material": "无", "tier": "无"},
        "hu_tablet": {"name": "无（持书卷）", "desc": "手持手卷或折扇", "material": "纸/竹", "tier": "布衣"},
        "boots": {"name": "青布平底履", "desc": "方头青黑布鞋", "material": "布", "tier": "布衣"},
    },
    "qinwang": {
        "tier_key": "qinwang",
        "rank_name": "宗室亲王礼服",
        "color_name": "皇紫金",
        "head": {
            "name": "长平展脚金花幞头",
            "desc": "漆纱长平展脚幞头，冠侧缀贴金翠叶饰件。",
            "material": "纯金/漆纱",
            "tier": "宗室",
        },
        "robe": {
            "name": "深紫素面宗亲襕袍",
            "desc": "深紫天蚕特织大袖袍，端严尊贵。",
            "color": "#311B92",
            "material": "天蚕素罗",
            "tier": "宗室",
        },
        "belt": {
            "name": "御赐金镶玉带",
            "desc": "纯金錾花包羊脂白玉带板。",
            "material": "纯金/白玉",
            "tier": "宗室",
        },
        "fish_pouch": {
            "name": "特赐重金鱼袋",
            "desc": "镂空云凤纹纯金鱼袋。",
            "material": "纯金",
            "tier": "宗室",
        },
        "hu_tablet": {
            "name": "极品玉笏 / 象笏",
            "desc": "羊脂白玉或极品大象牙笏。",
            "material": "羊脂玉",
            "tier": "宗室",
        },
        "boots": {
            "name": "六缝黑缎靴",
            "desc": "精熟鹿皮为里，黑缎为面。",
            "material": "鹿皮/黑缎",
            "tier": "宗室",
        },
    },
}

# 严禁词校验
TABOO_KEYWORDS = ("补子", "buzi", "mandarin square", "龙纹", "龙袍", "dragon", "补服", "顶戴", "花翎", "乌纱折角")


def parse_costume_tier(rank_str: str) -> str:
    """按宋代官品换算公服服色档位（lv / fei / zi / shi / qinwang）。"""
    if not rank_str:
        return "shi"
    r = str(rank_str).strip()
    if any(k in r for k in ("亲王", "宗室", "赵")):
        return "qinwang"
    if any(k in r for k in ("一品", "二品", "三品", "四品", "太师", "太傅", "太保", "宰相", "参知政事", "枢密", "尚书")):
        return "zi"
    if any(k in r for k in ("五品", "六品", "知府", "知州", "侍郎", "给事中", "郎中", "员外郎")):
        return "fei"
    if any(k in r for k in ("七品", "八品", "九品", "知县", "县丞", "主簿", "通判", "选人", "幕职", "监当")):
        return "lv"
    return "lv"


def get_official_equipment(rank: Optional[str] = None, tier: Optional[str] = None) -> Dict[str, Any]:
    """返回对应官员品级的全套 6 槽位装备字典。"""
    t = tier or parse_costume_tier(rank or "")
    cfg = EQUIPMENT_TIERS.get(t, EQUIPMENT_TIERS["lv"])
    return {
        "tier": t,
        "rank_name": cfg["rank_name"],
        "color_name": cfg["color_name"],
        "slots": {
            "head": cfg["head"],
            "robe": cfg["robe"],
            "belt": cfg["belt"],
            "fish_pouch": cfg["fish_pouch"],
            "hu_tablet": cfg["hu_tablet"],
            "boots": cfg["boots"],
        },
    }


def generate_costume_prompt(tier: str, pose: str = "zheng") -> Dict[str, str]:
    """生成用于 AI 生图（Midjourney / FLUX / SD）的完整提示词及负面提示词。"""
    cfg = EQUIPMENT_TIERS.get(tier, EQUIPMENT_TIERS["lv"])
    robe_desc = cfg["robe"]["desc"]
    head_desc = cfg["head"]["desc"]
    belt_desc = cfg["belt"]["desc"]
    fish_desc = cfg["fish_pouch"]["desc"]
    hu_desc = cfg["hu_tablet"]["desc"]

    pos_cn = (
        f"北宋院体工笔设色绢本肖像。一位北宋{cfg['rank_name']}官员，半身立像。身穿{robe_desc}，"
        f"头戴{head_desc}，腰束{belt_desc}，{fish_desc}，双手端持{hu_desc}。"
        f"通体纯色素雅，绝无任何胸前补子刺绣，无龙纹，古朴赭黄绢本底色，宋画严谨写实气韵。"
    )

    color_en = {"lv": "pea-green", "fei": "scarlet-crimson", "zi": "deep purple-violet", "shi": "ivory-white", "qinwang": "imperial purple"}.get(tier, "green")
    wings_en = {"lv": "stiff straight thin horizontal flat wings", "fei": "long perfectly horizontal flat stiff wings", "zi": "extremely long horizontal flat stiff wings stretching wide"}.get(tier, "horizontal flat wings")
    belt_en = {"lv": "black leather belt with plain dark horn plaques, no fish pouch", "fei": "leather belt with chased sterling silver plaques, silver fish pouch", "zi": "crimson belt with carved pure gold plaques, golden fish pouch"}.get(tier, "leather belt")
    hu_en = {"lv": "slender wooden hu tablet", "fei": "off-white ivory hu tablet", "zi": "gently curved exquisite white ivory tablet"}.get(tier, "hu tablet")

    pos_en = (
        f"Traditional Chinese Northern Song Dynasty court portrait, gongbi painting on aged antique raw silk canvas. "
        f"A half-length portrait of a Song Dynasty civil official wearing an authentic plain solid {color_en} round-collar robe (lanpao), "
        f"wide sleeves, pure monochrome fabric with strictly NO chest patches, NO buzi, NO dragon embroidery. "
        f"Wearing a formal Song lacquered futou hat with {wings_en}. "
        f"Fastened around waist is an authentic {belt_en}. "
        f"Both hands hold a {hu_en} in front of chest. "
        f"Museum artifact quality, historical realism, masterwork brushwork --ar 3:4 --style raw --v 6.1"
    )

    neg_en = (
        "buzi, mandarin square, embroidered chest patch, chest emblem, dragon robe, dragon embroidery, "
        "golden dragon, qilin, Ming dynasty hat, Qing dynasty hat, official hat with tassels, official hat with peacock feather, "
        "curved wing hat, white thick boot soles, modern hanfu, fantasy, blurry, low quality"
    )

    return {
        "tier": tier,
        "pose": pose,
        "prompt_cn": pos_cn,
        "prompt_en": pos_en,
        "negative_en": neg_en,
    }


def verify_costume_historical_integrity(text: str) -> bool:
    """历史合规性校验：若文案或描述包含明清补子、龙纹等违规字样，返回 False。"""
    t = (text or "").lower()
    for kw in TABOO_KEYWORDS:
        if kw.lower() in t:
            return False
    return True


# ============================================================
# 皇帝恩赏章服部件定义（Imperial Bestowals & Slot Overrides）
# 史实北宋章服与官阶双轨：天子可特赐紫、特赐绯、赐金鱼袋、赐玉带、赐象笏等荣典
# ============================================================
FAVOR_BESTOWALS: Dict[str, Dict[str, Any]] = {
    "赐紫": {
        "key": "赐紫",
        "name": "赐紫金鱼袋",
        "desc": "特赐身着高品深绛紫襕袍，佩纯金鱼袋，享一至四品重臣章服荣典（借紫）。",
        "custom_tier": "zi",
        "slot_overrides": {
            "robe": EQUIPMENT_TIERS["zi"]["robe"],
            "fish_pouch": EQUIPMENT_TIERS["zi"]["fish_pouch"],
        },
        "loyalty_delta": 0.15,
        "prestige_delta": 2,
        "treasury_cost": 500,
    },
    "赐绯": {
        "key": "赐绯",
        "name": "赐绯银鱼袋",
        "desc": "特赐身着中品朱红纯素襕袍，佩白银鱼袋，标志跻身朝省中坚（借绯）。",
        "custom_tier": "fei",
        "slot_overrides": {
            "robe": EQUIPMENT_TIERS["fei"]["robe"],
            "fish_pouch": EQUIPMENT_TIERS["fei"]["fish_pouch"],
        },
        "loyalty_delta": 0.10,
        "prestige_delta": 1,
        "treasury_cost": 200,
    },
    "赐金鱼袋": {
        "key": "赐金鱼袋",
        "name": "特赐鎏金金鱼袋",
        "desc": "革带右侧加佩纯金鱼袋，彰显天子腹心之重臣恩遇。",
        "slot_overrides": {
            "fish_pouch": EQUIPMENT_TIERS["zi"]["fish_pouch"],
        },
        "loyalty_delta": 0.08,
        "prestige_delta": 1,
        "treasury_cost": 150,
    },
    "赐银鱼袋": {
        "key": "赐银鱼袋",
        "name": "特赐白银鱼袋",
        "desc": "革带右侧佩白银鱼囊，赐予拔擢初显之亲民能臣。",
        "slot_overrides": {
            "fish_pouch": EQUIPMENT_TIERS["fei"]["fish_pouch"],
        },
        "loyalty_delta": 0.05,
        "prestige_delta": 1,
        "treasury_cost": 100,
    },
    "赐玉带": {
        "key": "赐玉带",
        "name": "御赐十三銙羊脂白玉带",
        "desc": "天子近臣无上荣典，红鞓皮排缀十三枚温润羊脂白玉带板。",
        "slot_overrides": {
            "belt": {
                "name": "御赐羊脂白玉带",
                "desc": "红鞓皮排缀十三枚温润羊脂白玉带板，起暗地云气纹，近臣绝顶恩遇。",
                "material": "羊脂白玉/红革",
                "tier": "特赐",
            },
        },
        "loyalty_delta": 0.12,
        "prestige_delta": 2,
        "treasury_cost": 800,
    },
    "赐象笏": {
        "key": "赐象笏",
        "name": "御赐透润老象牙玉笏",
        "desc": "御赐老象牙心通透玉笏，端奉胸前，出入禁省顾问朝政。",
        "slot_overrides": {
            "hu_tablet": EQUIPMENT_TIERS["zi"]["hu_tablet"],
        },
        "loyalty_delta": 0.06,
        "prestige_delta": 1,
        "treasury_cost": 300,
    },
    "赐金花幞头": {
        "key": "赐金花幞头",
        "name": "御赐长平展脚金花幞头",
        "desc": "宫廷特制漆纱长平展脚幞头，冠侧缀贴金翠叶饰件，皇城亲幸荣典。",
        "slot_overrides": {
            "head": EQUIPMENT_TIERS["qinwang"]["head"],
        },
        "loyalty_delta": 0.08,
        "prestige_delta": 1,
        "treasury_cost": 400,
    },
}

FAVOR_ALIASES: Dict[str, str] = {
    "赐紫金鱼袋": "赐紫",
    "借紫": "赐紫",
    "赐绯银鱼袋": "赐绯",
    "借绯": "赐绯",
    "赐玉带": "赐玉带",
    "赐白玉带": "赐玉带",
    "白玉带": "赐玉带",
    "赐象笏": "赐象笏",
    "象笏": "赐象笏",
    "金鱼袋": "赐金鱼袋",
    "银鱼袋": "赐银鱼袋",
}


def get_or_init_minister_equipment(state: Optional[Any], minister_name: str, rank: Optional[str] = None) -> Dict[str, Any]:
    """获取大臣装备全套 6 槽位配置（包含基础官品部件与皇帝特赐覆盖部件）。
    
    规则：
    1. 基础部件按官品推导（低品绿、中品绯、高品紫）；
    2. 若官员职位变动，优先取运行时 current_rank；
    3. 若官员受天子恩赐（如赐紫金鱼袋、赐白玉带等），从 state.minister_equipment 叠加覆盖；
    4. 无需独立UI界面，数据与立绘自然呈现。
    """
    from content.ministers.data import MINISTERS
    fig = MINISTERS.get(minister_name, {})

    equip_store = getattr(state, "minister_equipment", None) if state is not None else None
    if state is not None and not isinstance(equip_store, dict):
        state.minister_equipment = {}
        equip_store = state.minister_equipment

    m_record = equip_store.setdefault(minister_name, {
        "bestowals": [],
        "slot_overrides": {},
        "custom_tier": None,
        "current_rank": None,
    }) if equip_store is not None else {}

    if rank is not None:
        eff_rank = rank
    elif m_record.get("current_rank"):
        eff_rank = m_record["current_rank"]
    else:
        eff_rank = fig.get("rank") or ""

    natural_tier = parse_costume_tier(eff_rank)
    base_eq = get_official_equipment(rank=eff_rank, tier=natural_tier)

    if state is None:
        return base_eq

    # 判定有效服色档位（若受特赐借紫/借绯且自然官品尚不足以穿对应公服）
    active_tier = natural_tier
    if m_record.get("custom_tier"):
        custom_t = m_record["custom_tier"]
        tier_weight = {"zi": 3, "fei": 2, "lv": 1, "shi": 0, "qinwang": 4}
        if tier_weight.get(custom_t, 0) >= tier_weight.get(natural_tier, 0):
            active_tier = custom_t
            base_eq = get_official_equipment(tier=active_tier)

    # 覆盖特赐槽位
    final_slots = dict(base_eq["slots"])
    for slot_name, item in m_record.get("slot_overrides", {}).items():
        if item:
            final_slots[slot_name] = item

    return {
        "tier": active_tier,
        "rank_name": EQUIPMENT_TIERS.get(active_tier, {}).get("rank_name", base_eq["rank_name"]),
        "color_name": EQUIPMENT_TIERS.get(active_tier, {}).get("color_name", base_eq["color_name"]),
        "slots": final_slots,
        "bestowals": list(m_record.get("bestowals", [])),
        "custom_tier": m_record.get("custom_tier"),
    }


def refresh_minister_equipment_on_reassignment(state: Any, minister_name: str, new_rank: str) -> Dict[str, Any]:
    """官员职位变动时自动更新公服基础部件，但皇帝特赐恩赏部件持续保留。
    
    设计要求：不需要 UI 界面显示，官员职位变动时由官品驱动自动刷新基础部件，
    而皇帝恩赐的玉带、金鱼袋、金花幞头、借紫/借绯等独立特赐件自动保留并继续挂载。
    """
    if state is None:
        return get_official_equipment(rank=new_rank)

    equip_store = getattr(state, "minister_equipment", None)
    if not isinstance(equip_store, dict):
        state.minister_equipment = {}
        equip_store = state.minister_equipment

    m_record = equip_store.setdefault(minister_name, {
        "bestowals": [],
        "slot_overrides": {},
        "custom_tier": None,
        "current_rank": None,
    })

    # 记录运行期新职衔官阶
    m_record["current_rank"] = new_rank

    # 若新官品的自然服色已达到或超过 custom_tier（如升为一品高官），则自然服色生效，借服转正
    natural_tier = parse_costume_tier(new_rank)
    tier_weight = {"zi": 3, "fei": 2, "lv": 1, "shi": 0, "qinwang": 4}
    if m_record.get("custom_tier"):
        if tier_weight.get(natural_tier, 0) >= tier_weight.get(m_record["custom_tier"], 0):
            m_record["custom_tier"] = None

    return get_or_init_minister_equipment(state, minister_name, rank=new_rank)


def bestow_costume_item(state: Any, minister_name: str, favor_kind: str) -> Dict[str, Any]:
    """皇帝恩赏官员服饰部件/特赐章服。

    不需要 UI 独立界面，由天子圣旨/中旨或朝会恩赏触发。
    增益忠诚度、消耗内帑或国库、提升皇威，并沉淀入记忆库与履历。
    """
    if not favor_kind:
        return {"ok": False, "msg": "恩赏名目不可为空"}

    norm_kind = FAVOR_ALIASES.get(favor_kind, favor_kind)
    cfg = FAVOR_BESTOWALS.get(norm_kind)
    if not cfg:
        available = "、".join(FAVOR_BESTOWALS.keys())
        return {"ok": False, "msg": f"未知恩赏项「{favor_kind}」，可选恩赏：{available}"}

    equip_store = getattr(state, "minister_equipment", None)
    if not isinstance(equip_store, dict):
        state.minister_equipment = {}
        equip_store = state.minister_equipment

    m_record = equip_store.setdefault(minister_name, {
        "bestowals": [],
        "slot_overrides": {},
        "custom_tier": None,
    })

    # 审查修复（重复赐予白扣钱）：原实现只防「重复入册」，不防「重复扣钱」——
    # 实测连赐三次「赐紫」：忠诚 0.85 第一次即顶 1.0，后两次仍各扣 500 贯、
    # 仍回报「恩眷优渥」。现改为同一件已赐过即拒绝，杜绝无声损耗与虚假回执。
    if cfg["name"] in m_record["bestowals"]:
        return {"ok": False,
                "msg": f"{minister_name}已蒙赐{cfg['name']}，不必重叠恩赏（同物不再加恩）"}

    cost = cfg.get("treasury_cost", 0)
    # 优先扣内帑（皇帝私库赏赐），内帑不足扣国库。
    # 审查修复：原写 `state.inner_treasury` —— **该属性不存在**（getattr 恒 0），
    # 分支永不成立 → 实际永远扣国库，与注释相反（实测内帑 1,000,000 分文未动）；
    # 且直改属性绕过统一通道、无非负保护。现改用
    # `change_imperial_treasury` / `change_treasury`（二者皆 clamp 非负）。
    if getattr(state, "imperial_treasury", 0) >= cost:
        state.change_imperial_treasury(-cost)
    elif getattr(state, "treasury", 0) >= cost:
        state.change_treasury(-cost)
    else:
        return {"ok": False, "msg": f"库藏空虚（需 {cost} 贯），不足以备办御赐重礼"}

    # 记录恩赏
    m_record["bestowals"].append(cfg["name"])

    # 覆盖槽位部件
    for slot_k, item in cfg.get("slot_overrides", {}).items():
        m_record["slot_overrides"][slot_k] = item

    if cfg.get("custom_tier"):
        m_record["custom_tier"] = cfg["custom_tier"]

    # 忠诚度提升
    loyalty_map = getattr(state, "loyalty", None)
    if isinstance(loyalty_map, dict) and minister_name in loyalty_map:
        old_loyalty = loyalty_map[minister_name]
        loyalty_map[minister_name] = min(1.0, round(old_loyalty + cfg.get("loyalty_delta", 0.1), 3))

    # 皇威增长
    if hasattr(state, "change_prestige"):
        state.change_prestige(cfg.get("prestige_delta", 1))

    # 记入短期政务日志
    log_msg = f"官家御赐【{minister_name}】{cfg['name']}，恩眷优渥，百僚咸服。"
    if hasattr(state, "short_term_log"):
        state.short_term_log.append({
            "turn": getattr(state, "turn", 0),
            "kind": "honor",
            "title": f"御赐{minister_name}{cfg['name']}",
            "note": log_msg,
            "year": getattr(state, "year", 1101),
            "month": getattr(state, "month", 1),
        })

    # 记忆图谱沉淀。
    # 审查修复：原写 `state.memory_graph`（**该属性不存在**，应为 `state.memory`）
    # 且调 `add_memory`（**MemoryGraph 无此方法**）→ 三重错位又被 except 静默吞掉，
    # 恩赏从不进记忆库，履历断层（日后推演不知此人受过恩典）。
    # 现改用既有 API `record_decision`（decision 实体 + involves 关联 + 大臣绑定）。
    mg = getattr(state, "memory", None)
    if mg is not None and hasattr(mg, "record_decision"):
        try:
            mg.record_decision(
                f"御赐{minister_name}{cfg['name']}",
                {"章服恩赏": cfg["name"],
                 "忠诚": "+%.2f" % cfg.get("loyalty_delta", 0.1)},
                minister=minister_name,
                turn=getattr(state, "turn", 0),
                note="天子御赐章服，优容厚加宠遇",
            )
        except Exception as _e:  # noqa: BLE001
            # 不再静默：写入失败要留痕（原 pass 使其永久不可见）
            import logging as _lg
            _lg.getLogger("costumes").warning("恩赏未入记忆库：%r", _e)

    refreshed = get_or_init_minister_equipment(state, minister_name)
    return {
        "ok": True,
        "msg": log_msg,
        "minister": minister_name,
        "favor": cfg["name"],
        "equipment": refreshed,
    }
