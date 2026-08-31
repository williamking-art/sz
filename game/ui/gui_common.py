# -*- coding: utf-8 -*-
"""宋祚 · GUI 共享常量与纯工具函数（供 gui.py 及各 panels_*.py 复用）。

合并原 ui/bars.py / ui/effects.py / ui/format_units.py 三个碎片模块，
避免「常量 + 共享辅助函数」在多文件间重复维护与委托间接。
"""

# ── 主题常量（宣纸朱红风）──
PAPER = "#f6ecd6"        # 主背景（宣纸）
PAPER2 = "#efe2c4"       # 次级背景
CARD = "#fffaf0"         # 卡片底（米白宣纸）
INK = "#2b1d12"          # 正文深褐
DIM = "#8a6b40"          # 次要文字（赭黄）
RED = "#8a2b22"          # 朱红（主色）
RED_D = "#6f201a"        # 深朱红（渐变/描边）
GOLD = "#caa24a"         # 描金
GREEN = "#5a7a3c"        # 吉（绿）
BORDER = "#d8c08a"       # 卡片描边
SEAL_BG = "#7a1f1f"      # 印章红

# 字体（Windows 优先楷体/雅黑）
KAI = "KaiTi"
SANS = "Microsoft YaHei"

DECREE_CATEGORIES = ["财政", "军事", "人事", "民生", "外交"]


# ============================================================
# 单位展示工具（原 ui/format_units.py）
# 后台真实单位（去万），展示层大数自动「万」表述。
# 后台单位基线（存储/计算一律真实单位，不带"万"，避免 ×10000 换算错位）：
#   货币=贯  粮=石  户数=户  田亩=亩  人口=口  官/吏/兵=人
# ============================================================
def _group(n: float) -> str:
    """整数千分位（四舍五入为整数）。"""
    return f"{int(round(n)):,}"


def _wan(n: float, unit: str) -> str:
    """大数万表述：≥1 万 → 「X万单位」/「X.X万单位」；<1 万 → 真实数千分位。"""
    if n is None:
        return "—"
    neg = "-" if n < 0 else ""
    a = abs(n)
    if a >= 10_000:
        wan = a / 10_000.0
        if wan >= 100:
            return f"{neg}{round(wan)}万{unit}"
        s = f"{wan:.1f}".rstrip("0").rstrip(".")
        return f"{neg}{s}万{unit}"
    return f"{neg}{_group(a)}{unit}"


# ---- 货币：贯 ----
GUAN_PER_WANGUAN = 10_000


def humanize_coin(guan: float) -> str:
    """货币：后台为贯，展示 ≥1万 换算为万贯。"""
    return _wan(guan, "贯")


def humanize_coin_wan(wanguan: float) -> str:
    """兼容旧调用：输入为万贯时转真实贯再显示。"""
    return humanize_coin((wanguan or 0) * GUAN_PER_WANGUAN)


def guan_from_wanguan(wanguan: float) -> float:
    """万贯 → 贯。"""
    return (wanguan or 0) * GUAN_PER_WANGUAN


# ---- 粮：石 ----
SHI_PER_WANSHI = 10_000


def humanize_grain(shi: float) -> str:
    """粮：后台为石，展示 ≥1万 换算为万石。"""
    return _wan(shi, "石")


def humanize_grain_wan(wan_shi: float) -> str:
    """兼容旧调用：输入为万石时转真实石再显示。"""
    return humanize_grain((wan_shi or 0) * SHI_PER_WANSHI)


def humanize_grain_price(guan_per_shi: float) -> str:
    """米价：内部 grain_price 即 贯/石（0.4~2.5），直接展示，不取倒数。"""
    if not guan_per_shi or guan_per_shi <= 0:
        return "—"
    return f"{guan_per_shi:.3f}贯/石"


# ---- 人口/户/田/官/吏：后台真实数，展示 ≥1万 换算为万 ----
def humanize_pop(population: float) -> str:
    return _wan(population, "口")


def humanize_households(households: float) -> str:
    return _wan(households, "户")


def humanize_land(land: float) -> str:
    return _wan(land, "亩")


def humanize_count(n: float, unit: str = "人") -> str:
    """通用大数（官/吏/兵等）：后台为真实人数，展示 ≥1万 换算为万。"""
    return _wan(n, unit)


# ============================================================
# 数值进度条（原 ui/bars.py）
# ============================================================
def _bar(value, width: int = 10) -> str:
    """数值进度条：三档填充字符（█/▓/▒）+ 空位 ░，阈值 70/40。"""
    v = max(0, min(width, int(value * width / 100)))
    if value >= 70:
        return "█" * v + "░" * (width - v)
    elif value >= 40:
        return "▓" * v + "░" * (width - v)
    return "▒" * v + "░" * (width - v)


# ============================================================
# 效果字典 → 中文描述（原 ui/effects.py）
# ============================================================
# 效果键 → 中文名
_NAME_MAP = {
    "prestige": "皇威",
    "treasury": "国帑(贯)",
    "imperial_treasury": "内帑(贯)",
    "population_satisfaction": "民心",
    "external_jin": "金态度",
    "external_liao": "辽态度",
    "external_xixia": "西夏态度",
    "defense_bonus": "城防",
    "finance": "财利(贯)",
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
                sign = "+" if v >= 0 else ""
                parts.append(f"{_NAME_MAP[k]}{sign}{humanize_coin(v)}")
            elif k in ("curtail_waste", "reduce_office"):
                parts.append(f"{_NAME_MAP[k]}月省{humanize_coin(v)}")
            else:
                sign = "+" if v >= 0 else ""
                parts.append(f"{_NAME_MAP[k]}{sign}{v}")
    return ", ".join(parts) if parts else "（无显著影响）"


def _format_effects(effects):
    """format_effects 的历史别名（panels 既有调用）。"""
    return format_effects(effects)


def _judge_effects(effects):
    """统计选项 effects 里增益/减益条目数（用于朱批色高亮）。"""
    good = bad = 0
    for k, v in (effects or {}).items():
        if k == "faction_change":
            for _fn, fd in iter_faction_change(effects):
                if fd >= 0:
                    good += 1
                else:
                    bad += 1
        else:
            if v > 0:
                good += 1
            elif v < 0:
                bad += 1
    return good, bad
