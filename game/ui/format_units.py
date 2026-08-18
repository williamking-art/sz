"""单位展示工具：后台真实单位（去万），展示层大数自动「万」表述。

后台单位基线（存储/计算一律真实单位，不带"万"，避免 ×10000 换算错位）：
  - 货币 = 贯
  - 粮   = 石
  - 户数 = 户
  - 田亩 = 亩
  - 人口 = 口
  - 官/吏/兵 = 人

展示层换算规则：≥1 万自动用「X万单位」（如 500万贯、80.9万石、2000万户），
<1 万用真实数千分位；米价等小数（贯/石）原样显示。
"""
from __future__ import annotations


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
