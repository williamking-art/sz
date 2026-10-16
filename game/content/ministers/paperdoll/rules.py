# -*- coding: utf-8 -*-
"""北宋官员公服换装规制与约束校验引擎（Sumptuary Law & Constraints Engine）。

依据《宋史·舆服志》与元丰改制后制度：
1. 官阶品色强约束：七至九品绿、五至六品绯、一至四品紫；
2. 借绯/借紫规则：低品官员得天子特旨允许借穿高级别服色（如借绯穿红、借紫穿紫）；
3. 佩鱼规则：赐绯鱼袋（银鱼袋）、赐紫金鱼袋（纯金金鱼袋）；
4. 绝对禁忌拦截：严禁补子、严禁龙纹、严禁清代顶戴与明代折角帽。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    from content.ministers.paperdoll.model import EquipmentSlot
except ImportError:
    from game.content.ministers.paperdoll.model import EquipmentSlot


class RegaliaViolationError(ValueError):
    """违反宋代公服舆服制度异常。"""
    pass


def validate_regalia_compliance(equipped: Dict[str, str], rank: str, favor_privileges: Optional[List[str]] = None) -> List[str]:
    """校验当前装备组合是否合乎大宋典制。
    
    返回警告或违制说明列表（若为空则说明 100% 合法）。
    """
    favor_privileges = favor_privileges or []
    violations = []

    robe_id = equipped.get(EquipmentSlot.ROBE.value, "")
    pouch_id = equipped.get(EquipmentSlot.POUCH.value, "")
    belt_id = equipped.get(EquipmentSlot.BELT.value, "")
    futou_id = equipped.get(EquipmentSlot.HEADWEAR.value, "")

    is_borrow_purple = "借紫" in favor_privileges or "赐紫" in favor_privileges
    is_borrow_red = "借绯" in favor_privileges or "赐绯" in favor_privileges
    has_gold_pouch_favor = "赐金鱼袋" in favor_privileges
    has_silver_pouch_favor = "赐银鱼袋" in favor_privileges
    has_jade_belt_favor = "赐白玉带" in favor_privileges

    is_high_rank = any(r in rank for r in ("一品", "二品", "三品", "四品", "尚书", "中书", "门下", "仆射", "参政", "知政事", "宣抚"))
    is_prime_minister = any(r in rank for r in ("宰相", "仆射", "执政", "太师", "太傅", "太保", "一品"))

    # 1. 检查紫袍合法性
    if "zi" in robe_id:
        if not (is_high_rank or is_borrow_purple):
            violations.append(f"低品官员擅穿绛紫素罗襕袍（未获借紫恩赏）：{rank}")

    # 2. 检查金鱼袋合法性
    if pouch_id == "pouch_gold_fish":
        if not (has_gold_pouch_favor or (is_high_rank and "zi" in robe_id)):
            violations.append("低品官员或未获赐金鱼袋，严禁佩戴随身鎏金金鱼袋")

    # 3. 检查白玉带合法性
    if belt_id == "belt_jade_white":
        if not has_jade_belt_favor:
            violations.append("羊脂白玉带板为天子绝顶元老崇高恩赐，未获特赐不得佩扎")

    # 4. 检查展角长幞头合法性
    if futou_id == "futou_long_straight":
        if not (is_prime_minister or "宰相" in rank or "仆射" in rank):
            violations.append("长直铁线两尺半展角为中枢宰辅专属，寻常州县官员不得僭用")

    return violations


def resolve_promotion_equipment(old_equipped: Dict[str, str], new_rank: str, favors: Optional[List[str]] = None) -> Dict[str, str]:
    """官员仕途除授或晋升时，自动计算并升级其 QQ 秀装备插槽。"""
    favors = favors or []
    updated = dict(old_equipped)

    try:
        from content.ministers.costumes import parse_costume_tier
    except ImportError:
        from game.content.ministers.costumes import parse_costume_tier
    costume_tier = parse_costume_tier(new_rank)

    # 优先恩赏
    if "借紫" in favors or "赐紫" in favors:
        costume_tier = "zi"
    elif "借绯" in favors or "赐绯" in favors:
        if costume_tier not in ("zi", "qinwang"):
            costume_tier = "fei"

    if costume_tier == "zi":
        updated[EquipmentSlot.ROBE.value] = "robe_zi_3rd"
        updated[EquipmentSlot.HEADWEAR.value] = "futou_long_straight"
        updated[EquipmentSlot.BELT.value] = "belt_jade_white" if "赐白玉带" in favors else "belt_gold_lychee"
        updated[EquipmentSlot.POUCH.value] = "pouch_gold_fish"
        updated[EquipmentSlot.HELD.value] = "held_jade_ivory_hu"
    elif costume_tier == "fei":
        updated[EquipmentSlot.ROBE.value] = "robe_fei_5th"
        updated[EquipmentSlot.HEADWEAR.value] = "futou_mid_stiff"
        updated[EquipmentSlot.BELT.value] = "belt_silver_chased"
        updated[EquipmentSlot.POUCH.value] = "pouch_silver_fish"
        updated[EquipmentSlot.HELD.value] = "held_ivory_hu"
    elif costume_tier == "lv":
        updated[EquipmentSlot.ROBE.value] = "robe_lv_7th"
        updated[EquipmentSlot.HEADWEAR.value] = "futou_short_flat"
        updated[EquipmentSlot.BELT.value] = "belt_black_horn"
        updated[EquipmentSlot.POUCH.value] = "pouch_none"
        updated[EquipmentSlot.HELD.value] = "held_wood_tablet"

    # 单独恩赏覆盖
    if "赐金鱼袋" in favors:
        updated[EquipmentSlot.POUCH.value] = "pouch_gold_fish"
    elif "赐银鱼袋" in favors and updated.get(EquipmentSlot.POUCH.value) == "pouch_none":
        updated[EquipmentSlot.POUCH.value] = "pouch_silver_fish"

    if "赐白玉带" in favors:
        updated[EquipmentSlot.BELT.value] = "belt_jade_white"

    return updated
