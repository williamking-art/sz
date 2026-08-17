# -*- coding: utf-8 -*-
"""效果字典 → 中文描述 的共享格式化工具。

原先不同界面各维护一份 `_format_effects`，name_map 并集不一致，
造成双份维护与口径漂移。此处收敛为单一权威源。
"""

# 效果键 → 中文名
_NAME_MAP = {
    "prestige": "皇威",
    "treasury": "国帑(万贯)",
    "imperial_treasury": "内帑(万贯)",
    "population_satisfaction": "民心",
    "external_jin": "金态度",
    "external_liao": "辽态度",
    "external_xixia": "西夏态度",
    "defense_bonus": "城防",
    "finance": "财利(万贯)",
    "talent": "人才",
    "tech": "科技",
    "army": "军力",
    "reform": "改制",
    "curtail_waste": "省浮费",
    "reduce_office": "裁汰冗员",
}


def iter_faction_change(effects) -> iter:
    """遍历 faction_change 内层 {派系名: 增减值} 条目（format/_judge 共用单一迭代源）。"""
    fc = (effects or {}).get("faction_change") or {}
    if isinstance(fc, dict):
        yield from fc.items()


def format_effects(effects: dict) -> str:
    """格式化效果描述（单一权威实现）。"""
    parts = []
    for k, v in (effects or {}).items():
        if k == "faction_change":
            for fn, fd in iter_faction_change(effects):
                sign = "+" if fd >= 0 else ""
                parts.append(f"{fn}{sign}{fd}")
        elif k == "commerce_tax":
            # 工商征率是设定值（0~1 小数），显示成百分比，不带 + 号
            parts.append(f"工商征率{(v * 100):.0f}%")
        elif k in _NAME_MAP:
            if k in ("treasury", "imperial_treasury"):
                v2 = v / 10000
                sign = "+" if v >= 0 else ""
                parts.append(f"{_NAME_MAP[k]}{sign}{v2:.0f}")
            elif k in ("curtail_waste", "reduce_office"):
                parts.append(f"{_NAME_MAP[k]}月省{v / 10000:.0f}万贯")
            else:
                sign = "+" if v >= 0 else ""
                parts.append(f"{_NAME_MAP[k]}{sign}{v}")
    return ", ".join(parts) if parts else "（无显著影响）"
