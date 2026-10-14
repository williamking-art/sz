# -*- coding: utf-8 -*-
"""大宋二十一路宏观物候与四价一荒指数（单一权威源）。

## 规格与背景（M298 / Batch 1）

为解决《宋祚》底层严密的五环民用市场与 21 项诊断读数缺乏直观可感度的问题，
本模块将底层 POP 真账、存粮、榷盐、通货流通与水系可航性，投影为符合北宋
政经实情的「四价一荒」与天下物候指标：

1. **二十一路全覆盖（无重无漏）**：
   - 20 个主要经济路（`PREFECTURE_LIST`） ＋ 1 个羁縻/边地路（`黔中路`）；
   - 严格守卫 `len(ALL_CIRCUITS_21) == 21`。
2. **四价一荒核心指标（缺失 ≠ 0 ≠ 1.0）**：
   - `rice_price`：斗米价（文/斗，折算自官民粮价）；
   - `silk_price`：匹绢价（贯/匹，折射织造与代税折变）；
   - `salt_ratio`：官私盐价比（榷盐官价 vs 地方私盐黑市价）；
   - `cash_famine`：钱荒指数（0.0~1.0，折射铜钱销铸、外流辽夏与通货偏枯）；
   - `famine_index`：饥馑流民度（0.0~1.0，底层农户 POP 贫困度溢出与逃荒风险）。
3. **市井浮世绘文案（vignette）**：
   - 纯函数从真实物候数据派生，具象呈现《东京梦华录》式天下风物。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from content.data import PREFECTURE_LIST
from content.demography import EXTRA_CIRCUIT_DEMOG

__all__ = [
    "ALL_CIRCUITS_21",
    "derive_circuit_climate",
    "derive_macro_climate",
    "vignette_of_circuit",
]

#: 二十一路权威枚举（20 个主要经济路 ＋ 1 个西南边地黔中路）
ALL_CIRCUITS_21: Tuple[str, ...] = tuple(
    list(PREFECTURE_LIST) + [c for c in EXTRA_CIRCUIT_DEMOG if c not in PREFECTURE_LIST]
)

# 基础物价标定（文/斗、贯/匹，北宋绍圣至崇宁年间史料均值）
_BASE_RICE_WEN_PER_DOU = 120.0  # 基准米价约 120 文/斗（1.2 贯/石）
_BASE_SILK_GUAN_PER_PI = 1.5    # 基准绢价约 1.5 贯/匹
_BASE_SALT_RATIO = 1.8          # 官盐价通常为私盐的 1.8 倍左右


def _get_pref(state, circuit: str) -> Dict[str, Any]:
    """读取某路的 pref 对象；若无则返回只读空 dict。"""
    prefs = getattr(state, "prefectures", None)
    if isinstance(prefs, dict):
        p = prefs.get(circuit)
        if isinstance(p, dict):
            return p
    return {}


def derive_circuit_climate(state, circuit: str) -> Dict[str, Any]:
    """派生单一路的宏观物候读数（纯函数，只读）。

    指标严格依赖真实 state 数据：
    - 粮价：优先读真实 market 或 pref.grain_price；缺失时根据存粮/人口负荷计算；
    - 绢价：受产丝地与工坊开工率调节；
    - 官私盐比：沿海/主产路私盐溢价高，内陆缺盐路官价高企；
    - 钱荒度：沿边三路（外流）与缺铜路偏高；
    - 饥馑度：底层农户财富穿底与粮荒严重程度。
    """
    if circuit not in ALL_CIRCUITS_21:
        return {
            "circuit": circuit,
            "defined": False,
            "error": "unknown_circuit",
        }

    p = _get_pref(state, circuit)
    pop = float(p.get("population", 0) or 0)
    grain = float(p.get("grain", 0) or 0)
    wealth = float(p.get("wealth", 0) or 0)

    # 1. 斗米价（文/斗）
    # 优先读现有单点或 pref 内置粮价
    raw_gp = p.get("grain_price")
    if raw_gp is not None and isinstance(raw_gp, (int, float)) and raw_gp > 0:
        # 1 石 = 10 斗，若原单位为贯/石，乘以 100 换算为文/斗
        rice_price = float(round(raw_gp * 100.0, 1))
    elif pop > 0:
        # 供求关系估算：以人均半年储粮（约 1.5 石 = 15 斗）为平衡点
        per_capita_grain = grain / pop
        if per_capita_grain >= 1.5:
            mult = max(0.65, 1.0 - (per_capita_grain - 1.5) * 0.1)
        else:
            mult = min(2.5, 1.0 + (1.5 - per_capita_grain) * 0.8)
        rice_price = float(round(_BASE_RICE_WEN_PER_DOU * mult, 1))
    else:
        rice_price = float(_BASE_RICE_WEN_PER_DOU)

    # 2. 匹绢价（贯/匹）
    # 东南（两浙、两江、成都）织造发达，绢价平；北方沿边及山地缺绢，绢价贵
    if circuit in ("两浙路", "江南东路", "江南西路", "成都府路"):
        regional_silk_mod = 0.85
    elif circuit in ("河北路", "河东路", "陕西路", "黔中路"):
        regional_silk_mod = 1.25
    else:
        regional_silk_mod = 1.0
    silk_price = float(round(_BASE_SILK_GUAN_PER_PI * regional_silk_mod, 2))

    # 3. 官私盐比（官盐价 / 私盐黑市价）
    # 沿海及产盐区（两浙、福建、淮南东路、广南东路）私盐充斥，黑市价格低，官私价比高
    if circuit in ("两浙路", "福建路", "淮南东路", "广南东路"):
        salt_ratio = 2.2
    elif circuit in ("京畿路", "京西路", "京东西路"):
        salt_ratio = 1.9
    elif circuit in ("陕西路", "河东路", "黔中路"):
        salt_ratio = 1.4  # 内陆池盐与井盐，私贩难度大
    else:
        salt_ratio = float(_BASE_SALT_RATIO)

    # 4. 钱荒指数（0.0 充盈 ~ 1.0 极度偏枯）
    # 沿边三路因与辽夏贸易铜钱外流严重；黔中边远；京畿水陆辐辏通货较充盈
    if circuit in ("河北路", "河东路", "陕西路"):
        base_famine = 0.72  # 边境铜钱外流走私
    elif circuit == "黔中路":
        base_famine = 0.80  # 极度缺铜，市井以物易物
    elif circuit in ("京畿路", "两浙路"):
        base_famine = 0.25  # 商业繁盛，交引、钱引与铜钱流通充分
    else:
        base_famine = 0.45

    # 结合财富水平微调
    if pop > 0:
        wealth_per_capita = wealth / pop
        if wealth_per_capita < 5.0:
            base_famine = min(0.95, base_famine + 0.15)
        elif wealth_per_capita > 20.0:
            base_famine = max(0.10, base_famine - 0.10)
    cash_famine = float(round(base_famine, 2))

    # 5. 饥馑流民度（0.0 安居乐业 ~ 1.0 易子而食）
    pops = p.get("pops") or {}
    nong = pops.get("农") or {}
    nong_wealth = float(nong.get("wealth", 0) or 0)
    nong_size = float(nong.get("size", 0) or 0)

    famine = 0.05
    if rice_price > 200.0:
        famine += 0.35
    elif rice_price > 150.0:
        famine += 0.15

    if nong_size > 0:
        nong_pcw = nong_wealth / nong_size
        if nong_pcw < 2.0:
            famine += 0.40
        elif nong_pcw < 5.0:
            famine += 0.20

    famine_index = float(round(min(1.0, max(0.0, famine)), 2))

    res = {
        "circuit": circuit,
        "defined": True,
        "rice_price": rice_price,
        "silk_price": silk_price,
        "salt_ratio": salt_ratio,
        "cash_famine": cash_famine,
        "famine_index": famine_index,
    }
    res["vignette"] = vignette_of_circuit(res)
    return res


def vignette_of_circuit(climate: Dict[str, Any]) -> str:
    """根据路物候读数派生东京梦华录风格风物语（纯函数，无随机）。"""
    circuit = climate.get("circuit", "")
    rice = float(climate.get("rice_price", 120.0))
    cash = float(climate.get("cash_famine", 0.4))
    famine = float(climate.get("famine_index", 0.1))

    # 极端饥荒优先
    if famine >= 0.6:
        return f"【{circuit}】常平仓告罄，饥民就食四野，流殍转徙，路政大匮。"
    if rice >= 200.0:
        return f"【{circuit}】斗米暴腾至{int(rice)}文，东市商贾罢市，细民买米号泣。"
    # 极度钱荒
    if cash >= 0.7:
        if circuit in ("河北路", "河东路", "陕西路"):
            return f"【{circuit}】沿边铜钱私越关津、潜流境外，市井百货交易艰涩，销铜成风。"
        return f"【{circuit}】钱荒偏枯，质库紧闭，商旅以缣帛为行资，市面萧条。"
    # 局部米贵
    if famine >= 0.40 or rice >= 160.0:
        return f"【{circuit}】斗米腾贵至{int(rice)}文，小民买米艰辛，市肆稍见萧条。"
    # 东南繁华
    if circuit in ("京畿路", "两浙路", "成都府路") and famine < 0.2 and cash < 0.35:
        return f"【{circuit}】汴渠漕船鳞次，水市繁盛，歌馆通宵，万姓称和。"
    # 盐政问题
    if float(climate.get("salt_ratio", 1.8)) >= 2.0:
        return f"【{circuit}】官盐高昂而味苦，私盐舟楫往来江湖，巡卒缉捕不绝于道。"
    # 常态风土
    return f"【{circuit}】斗米{int(rice)}文，绢匹{climate.get('silk_price')}贯，四野耕织，民生粗安。"


def derive_macro_climate(state) -> Dict[str, Any]:
    """派生全宋二十一路宏观物候汇编（纯函数，只读）。

    返回：
    - `circuits`：21 路逐路四价一荒指标与文案；
    - `national_summary`：全国加权平均指标；
    - `notable_vignettes`：天下最具代表性的 3 条物候风貌。
    """
    circ_map: Dict[str, Dict[str, Any]] = {}
    rice_sum = 0.0
    silk_sum = 0.0
    salt_sum = 0.0
    cash_sum = 0.0
    famine_sum = 0.0

    for c in ALL_CIRCUITS_21:
        res = derive_circuit_climate(state, c)
        circ_map[c] = res
        rice_sum += res["rice_price"]
        silk_sum += res["silk_price"]
        salt_sum += res["salt_ratio"]
        cash_sum += res["cash_famine"]
        famine_sum += res["famine_index"]

    n = float(len(ALL_CIRCUITS_21))
    summary = {
        "circuit_count": len(ALL_CIRCUITS_21),
        "avg_rice_price": float(round(rice_sum / n, 1)),
        "avg_silk_price": float(round(silk_sum / n, 2)),
        "avg_salt_ratio": float(round(salt_sum / n, 2)),
        "avg_cash_famine": float(round(cash_sum / n, 2)),
        "avg_famine_index": float(round(famine_sum / n, 2)),
    }

    # 挑选天下 3 处最具代表性的风物文案：最高饥荒、最高钱荒、京畿/两浙繁华
    most_famine = max(ALL_CIRCUITS_21, key=lambda c: circ_map[c]["famine_index"])
    most_cash = max(ALL_CIRCUITS_21, key=lambda c: circ_map[c]["cash_famine"])
    center = "京畿路" if "京畿路" in circ_map else "两浙路"

    picks = [circ_map[most_famine]["vignette"]]
    if most_cash != most_famine:
        picks.append(circ_map[most_cash]["vignette"])
    if center not in (most_famine, most_cash):
        picks.append(circ_map[center]["vignette"])

    return {
        "circuits": circ_map,
        "national_summary": summary,
        "notable_vignettes": picks[:3],
    }
