# -*- coding: utf-8 -*-
"""宋祚 · AI 事实脱敏模块

设计哲学：脱敏不是"为藏而藏"，而是模拟现实信息混沌——
  1. 区间脱敏：给 AI 带噪声的模糊量级（"约四百万至六百万缗"），
     而非纯档位（"充裕"）。AI 知道量级可做有依据的判断，但区间
     内的不确定性使其无法精确计算最优解——这才是真实的决策混沌。
  2. 认知层滞后：经济读数走 economy_knowledge（上月快照），
     模拟古代奏报延迟。AI 看到的不是实时数而是"上个月户部奏报"。
  3. 机构信息壁垒：召对大臣时按其机构注入不同精度——户部尚书
     报财政较准、枢密使报军务较准，跨领域则泛化。模拟术业有专攻。
  4. 噪声注入：区间中心每次读取随机偏移，模拟传闻失真。

纯档位（"充裕/空虚"）反而让 AI 更刻板——同一档位永远映射同一
tier_to_value，AI 回答趋于一致。带噪声的区间让 AI 每次"看到的"
略有不同，决策自然发散——这才是"模拟现实的混沌"。
"""
import json
import random as _rng
from content.data import (
    desensitize_prestige, desensitize_arrival,
    desensitize_satisfaction, desensitize_treasury,
    get_prestige_level,
)


# ============================================================
# 区间脱敏核心：把精确值转为"约X至Y"的模糊区间
# ============================================================
def _fmt_amount(value: float, unit: str = "缗") -> str:
    """把大数格式化为万/亿单位（奏报口吻）。"""
    av = abs(value)
    if av >= 100_000_000:
        return f"{value/100_000_000:.1f}亿{unit}"
    if av >= 10_000:
        return f"{value/10_000:.0f}万{unit}"
    return f"{value:.0f}{unit}"


def desensitize_band(value, base_unit: str = "缗", width_pct: float = 0.20,
                     jitter_pct: float = 0.05, lag_value=None) -> str:
    """把精确值转为带噪声的模糊区间字符串。

    参数：
      value        — 真实精确值（脱敏对象）
      base_unit    — 单位（缗/石/口/人）
      width_pct    — 区间半宽占值的百分比（0.20=±20%，即区间宽 40%）
      jitter_pct   — 每次读取的额外随机偏移（模拟传闻失真）
      lag_value    — 认知层滞后值（上月快照）；若提供则用此为区间中心，
                     使 AI 看到的是"上月奏报"而非实时值

    返回如 "约四百至六百万缗" 或 "约八万石（上月奏报）"。
    特例：value<=0 时不做区间，直接返回定性（"库空如洗"等）。
    """
    src = lag_value if lag_value is not None else value
    if src <= 0:
        return "几无余财" if base_unit == "缗" else f"几无{base_unit}"
    # 噪声偏移：每次读取区间中心略有不同
    jitter = 1.0 + _rng.uniform(-jitter_pct, jitter_pct)
    center = src * jitter
    half = abs(src) * width_pct
    lo = max(0, center - half)
    hi = center + half
    tag = "（上月奏报）" if lag_value is not None else ""
    return f"约{_fmt_amount(lo, base_unit)}至{_fmt_amount(hi, base_unit)}{tag}"


# 机构 → 信息精度映射（召对时按大臣所司注入不同精度）
# 值为 (领域, width_pct)：该机构对对应领域的区间更窄（更准）
_ORG_PRECISION = {
    "户部":     {"treasury": 0.08, "granary": 0.10, "refugee": 0.15},
    "仓部":     {"granary": 0.08, "treasury": 0.12},
    "兵部":     {"army": 0.08, "defense": 0.10},
    "枢密院":   {"army": 0.06, "defense": 0.08, "external": 0.10},
    "工部":     {"resource": 0.10, "project": 0.12},
    "吏部":     {"official": 0.10},
    "礼部":     {"exam": 0.10},
    "翰林学士院": {"exam": 0.12},
}


def _org_width(org_name: str, domain: str, default: float = 0.25) -> float:
    """按机构取某领域的区间宽度（越窄越准）。非本行领域用 default。"""
    return _ORG_PRECISION.get(org_name, {}).get(domain, default)


def desensitize_state(state_summary: dict, org_name: str = "") -> dict:
    """将 GameState 摘要脱敏为叙事可读的状态描述。

    org_name：召对大臣所司机构名（如"户部"/"枢密院"）。提供时按机构
    信息壁垒调整精度——本行领域区间更窄（更准），跨领域更宽（更模糊）。
    模拟"术业有专攻"造成的认知差异。
    """
    sensitive = {}

    # 时间
    sensitive["时间"] = state_summary.get("time", "未知")

    # 皇威脱敏（皇威是皇帝亲历，不脱敏为区间，仍用等级描述）
    prestige = state_summary.get("prestige", {})
    sensitive["皇威"] = {
        "等级": prestige.get("level", "平平"),
        "描述": prestige.get("desc", "平平"),
    }

    # 皇帝健康脱敏（同上，龙体用定性）
    health = state_summary.get("health", 75)
    if health >= 80:
        sensitive["龙体"] = "圣躬安泰"
    elif health >= 60:
        sensitive["龙体"] = "偶有小恙"
    elif health >= 40:
        sensitive["龙体"] = "龙体欠安"
    elif health >= 20:
        sensitive["龙体"] = "病体沉重"
    else:
        sensitive["龙体"] = "龙驭垂危"

    # 国库脱敏——区间脱敏（户部奏报较准，他人较宽）
    treasury = state_summary.get("treasury", {})
    _treasury_val = treasury.get("amount", 0)
    _treasury_lag = state_summary.get("treasury_lagged")
    _tw = _org_width(org_name, "treasury")
    sensitive["国库"] = desensitize_band(_treasury_val, "缗", width_pct=_tw, lag_value=_treasury_lag)
    # 仍附定性描述供叙事口吻
    sensitive["国库定性"] = treasury.get("desc", "勉强维持")

    # 内帑脱敏（区间，精度低于国库——内帑更隐秘）
    imperial = state_summary.get("imperial_treasury", {})
    _imp_val = imperial.get("amount", 0)
    _imp_lag = state_summary.get("imperial_treasury_lagged")
    sensitive["内帑"] = desensitize_band(_imp_val, "缗", width_pct=0.30, lag_value=_imp_lag)

    # 到账率脱敏（定性——到账率本身已是派生估算，区间化意义不大）
    arrival = state_summary.get("arrival_rate", {})
    sensitive["税收到账"] = arrival.get("desc", "不足五成")

    # 朝堂派系脱敏（势力用区间，态度用定性——态度是主观判断无精确数）
    factions = state_summary.get("factions", {})
    sensitive["朝堂"] = {}
    for fname, finfo in factions.items():
        _inf = finfo.get("influence", 50)
        sensitive["朝堂"][fname] = {
            "势力": desensitize_band(_inf, "", width_pct=0.20, jitter_pct=0.03),
            "对君态度": finfo.get("sat_desc", "大体认可"),
        }

    # 外部脱敏——国力用区间（军务机构较准），关系用定性
    external = state_summary.get("external", {})
    _ew = _org_width(org_name, "external")
    sensitive["边境"] = {}
    for ename, einfo in external.items():
        power = einfo.get("power", 50)
        attitude = einfo.get("attitude", 50)
        if attitude >= 70:
            rel = "友善"
        elif attitude >= 40:
            rel = "一般"
        elif attitude >= 20:
            rel = "敌视"
        else:
            rel = "仇敌"
        pow_band = desensitize_band(power, "", width_pct=_ew, jitter_pct=0.04)
        sensitive["边境"][ename] = f"国力{pow_band}，关系{rel}"

    # 民情脱敏——流民用区间（不再泄露精确数；户部/按察使较准）
    _ref = state_summary.get("refugee_count", 0)
    _ref_lag = state_summary.get("refugee_count_lagged")
    _rw = _org_width(org_name, "refugee")
    sensitive["民情"] = {
        "民心": state_summary.get("pop_sat_desc", "大体认可"),
        "流民": desensitize_band(_ref, "口", width_pct=_rw, lag_value=_ref_lag) if _ref > 0 else "无",
    }
    # 注意：desensitize_state 已用区间脱敏，不再泄露精确流民数。
    # 唯一精确出口是 check_treasury 工具（需消耗诏令带宽，模拟皇帝亲勾代价）。

    # 军务脱敏——兵力用区间（枢密院/兵部较准）
    military = state_summary.get("military", {})
    _total_troops = sum(u.get("troops", 0) for u in military.get("armies", {}).values())
    _aw = _org_width(org_name, "army")
    if _total_troops > 0:
        sensitive["军力"] = desensitize_band(_total_troops, "人", width_pct=_aw, jitter_pct=0.03)
    else:
        sensitive["军力"] = "军籍未详"

    # 诏令资源（仍用定性——带宽是皇帝亲历额度，非奏报对象）
    bw = state_summary.get("decree_bandwidth", 6)
    pend = state_summary.get("pending_decrees", 0)
    if bw >= 9:
        bw_desc = "充裕"
    elif bw >= 6:
        bw_desc = "从容"
    elif bw >= 3:
        bw_desc = "局促"
    else:
        bw_desc = "捉襟见肘"
    pend_desc = "积压如山" if pend >= 4 else ("稍有积案" if pend >= 1 else "案牍清爽")
    sensitive["政令资源"] = {
        "圣旨额度": bw_desc,
        "待执行": pend_desc,
    }

    # 太仓脱敏——区间（仓部/户部较准）
    granary_ext = state_summary.get("granary_ext", {})
    _granary_val = state_summary.get("granary_amount", 0)
    _granary_lag = state_summary.get("granary_lagged")
    _gw = _org_width(org_name, "granary")
    sensitive["太仓"] = desensitize_band(_granary_val, "石", width_pct=_gw, lag_value=_granary_lag) if _granary_val > 0 else "太仓告罄"
    sensitive["太仓定性"] = granary_ext.get("granary", "仓廪未详")

    # 米价趋势（基于认知层近月比较，给定性涨跌 + 区间量级）
    sensitive["米价"] = _desensitize_grain_trend(state_summary.get("grain_price", 1.0),
                                                 state_summary.get("grain_price_prev", None))
    # 附米价区间（让 AI 知道当前米价量级，而非仅涨跌方向）
    _gp = state_summary.get("grain_price", 1.0)
    sensitive["米价区间"] = desensitize_band(_gp, "贯/石", width_pct=0.15, jitter_pct=0.03)

    # 皇帝个人
    personal = state_summary.get("personal", {})
    art = personal.get("art", 85)
    tao = personal.get("taoism", 25)
    pleas = personal.get("pleasure", 30)
    sensitive["天子好尚"] = []
    if art >= 80:
        sensitive["天子好尚"].append("酷爱书画")
    if tao >= 60:
        sensitive["天子好尚"].append("笃信道教")
    if pleas >= 60:
        sensitive["天子好尚"].append("喜好宴游")

    return sensitive


def _desensitize_influence(influence: int) -> str:
    """影响力脱敏"""
    if influence >= 90:
        return "权倾朝野"
    elif influence >= 70:
        return "势力强劲"
    elif influence >= 50:
        return "中流砥柱"
    elif influence >= 30:
        return "势单力薄"
    elif influence >= 10:
        return "苟延残喘"
    return "几近消亡"


def _desensitize_grain_trend(price: float, prev) -> str:
    """米价趋势脱敏：仅给定性涨跌档位，不暴露精确价格。

    prev 为认知层上一期米价；None 时退化为按当前价绝对档位。
    """
    if prev is None:
        if price >= 1.6:
            return "米珠薪桂"
        elif price >= 1.2:
            return "粮价渐昂"
        elif price >= 0.8:
            return "米价适中"
        else:
            return "谷贱伤农"
    ratio = price / prev if prev > 0 else 1.0
    if ratio >= 1.15:
        return "米价腾涌"
    elif ratio >= 1.03:
        return "米价渐昂"
    elif ratio >= 0.97:
        return "米价持稳"
    elif ratio >= 0.85:
        return "米价稍落"
    else:
        return "米价大跌"


def desensitize_for_ai(state, org_name: str = "") -> str:
    """将完整 GameState 转为 AI 可读的脱敏文本。

    org_name：召对大臣所司机构（如"户部"）。提供时按机构信息壁垒
    调整精度——本行领域区间更窄（奏报更准），跨领域更宽。
    """
    summary = state.get_state_summary()
    ds = desensitize_state(summary, org_name=org_name)
    return json.dumps(ds, ensure_ascii=False, indent=2)
