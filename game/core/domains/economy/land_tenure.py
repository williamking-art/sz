# -*- coding: utf-8 -*-
"""大宋二十一路田亩四分与租佃主客模型（单一权威源）。

## 规格与背景（M299 / Stage 2）

为解决《宋祚》底层田亩关系单薄、仅有虚拟 land 数字、缺乏宋代真实租佃社会承载的问题，
本模块建立符合北宋神宗熙丰变法至徽宗崇宁年间实情的四大田制结构与主客户模型：

1. **田亩四分不变量（逐路守恒）**：
   - `min_tian`（民田/主户私田）：自耕农与中小地主所有，承担国家夏秋两税、和买与折帛；
   - `guan_tian`（官田/公田/屯田/学田）：朝廷与州府转运司所有，招佃收租，用于养学、备边屯田；
   - `yin_tian`（庄园隐田/官僚隐匿田）：士绅官僚通过免役特权与诡名夹带隐匿的田亩，逃避赋役；
   - **严格不变量**：`min_tian + guan_tian + yin_tian == total_land`（不增不减，守恒封闭）。
2. **租佃主客动力学**：
   - `freeholders`（主户/自耕农）：拥有民田，自耕纳税，丰年积累，荒年卖田；
   - `tenants`（客户/佃农）：无地或失地农户，佃种官田（官佃）或庄园（私佃），依租率缴租；
   - 兼并流转：当底层赋税压迫过重时，主户破产沦为客户，甚至成为逃户/流民；
3. **方田均税清丈（Fangtian Survey）**：
   - 严厉清查豪强隐田，将 `yin_tian` 清丈后还原为 `min_tian`，扩大国家两税税基。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from content.data import PREFECTURE_LIST
from content.demography import EXTRA_CIRCUIT_DEMOG

__all__ = [
    "derive_circuit_tenure",
    "derive_national_tenure",
    "apply_fangtian_survey",
    "TENURE_KEYS",
]

TENURE_KEYS = ("min_tian", "guan_tian", "yin_tian")

# 北宋中后期各路田亩结构基准比率（民田约 68%、官田约 12%、庄园隐田约 20%）
_DEFAULT_RATIOS = {
    "min_tian": 0.68,
    "guan_tian": 0.12,
    "yin_tian": 0.20,
}


def _get_pref(state, circuit: str) -> Dict[str, Any]:
    """读取某路的 pref 对象；若无则查 EXTRA_CIRCUIT_DEMOG。"""
    prefs = getattr(state, "prefectures", None)
    if isinstance(prefs, dict):
        p = prefs.get(circuit)
        if isinstance(p, dict):
            return p
    if circuit in EXTRA_CIRCUIT_DEMOG:
        return EXTRA_CIRCUIT_DEMOG[circuit]
    return {}


def derive_circuit_tenure(state, circuit: str) -> Dict[str, Any]:
    """派生单一路的田亩四分与租佃主客账本（纯函数，只读）。

    保证严格守恒：
    min_tian + guan_tian + yin_tian == total_land
    """
    p = _get_pref(state, circuit)
    total_land = float(p.get("land", 0) or 0)
    if total_land <= 0:
        return {
            "circuit": circuit,
            "defined": False,
            "total_land": 0.0,
            "min_tian": 0.0,
            "guan_tian": 0.0,
            "yin_tian": 0.0,
            "freeholder_ratio": 0.0,
            "tenant_ratio": 0.0,
        }

    # 若该路已有持久化记录则读之，否则按基准比率初始化派生
    tenure_store = p.get("land_tenure")
    if isinstance(tenure_store, dict):
        min_t = float(tenure_store.get("min_tian", 0) or 0)
        guan_t = float(tenure_store.get("guan_tian", 0) or 0)
        yin_t = float(tenure_store.get("yin_tian", 0) or 0)
        # 守恒校验，若有微小残差则归入民田
        cur_sum = min_t + guan_t + yin_t
        if abs(cur_sum - total_land) > 1e-4 and cur_sum > 0:
            scale = total_land / cur_sum
            min_t *= scale
            guan_t *= scale
            yin_t *= scale
        elif cur_sum == 0:
            min_t = total_land * _DEFAULT_RATIOS["min_tian"]
            guan_t = total_land * _DEFAULT_RATIOS["guan_tian"]
            yin_t = total_land * _DEFAULT_RATIOS["yin_tian"]
    else:
        # 对齐历史已有 hidden_land（若有）
        raw_hidden = float(p.get("hidden_land", 0) or 0)
        if raw_hidden > 0 and raw_hidden < total_land:
            yin_t = raw_hidden
            rem = total_land - yin_t
            guan_t = rem * 0.15
            min_t = rem - guan_t
        else:
            min_t = total_land * _DEFAULT_RATIOS["min_tian"]
            guan_t = total_land * _DEFAULT_RATIOS["guan_tian"]
            yin_t = total_land * _DEFAULT_RATIOS["yin_tian"]

    # 主客人口结构：主户自耕农占农户约 60%~75%，客户佃农占 25%~40%
    pops = p.get("pops") or {}
    nong = pops.get("农") or {}
    nong_size = float(nong.get("size", 0) or 0)

    # 土地兼并度：隐田越高，自耕农流失越严重
    land_concentration = yin_t / total_land if total_land > 0 else 0.20
    freeholder_share = max(0.35, min(0.85, 0.85 - land_concentration * 0.8))
    tenant_share = 1.0 - freeholder_share

    freeholder_pops = float(round(nong_size * freeholder_share))
    tenant_pops = nong_size - freeholder_pops

    return {
        "circuit": circuit,
        "defined": True,
        "total_land": float(round(total_land, 1)),
        "min_tian": float(round(min_t, 1)),
        "guan_tian": float(round(guan_t, 1)),
        "yin_tian": float(round(yin_t, 1)),
        "land_concentration": float(round(land_concentration, 4)),
        "freeholder_pops": freeholder_pops,
        "tenant_pops": tenant_pops,
        "freeholder_share": float(round(freeholder_share, 4)),
        "tenant_share": float(round(tenant_share, 4)),
        "rent_rate": 0.45,  # 佃农平均地租率约 45% (对半分或四六分)
    }


def derive_national_tenure(state) -> Dict[str, Any]:
    """派生全宋二十一路田亩结构总览（纯函数，只读）。"""
    from core.domains.economy.macro_climate import ALL_CIRCUITS_21

    total_land_all = 0.0
    min_tian_all = 0.0
    guan_tian_all = 0.0
    yin_tian_all = 0.0
    circs: Dict[str, Dict[str, Any]] = {}

    for c in ALL_CIRCUITS_21:
        res = derive_circuit_tenure(state, c)
        circs[c] = res
        total_land_all += res["total_land"]
        min_tian_all += res["min_tian"]
        guan_tian_all += res["guan_tian"]
        yin_tian_all += res["yin_tian"]

    return {
        "circuits": circs,
        "summary": {
            "total_land": float(round(total_land_all, 1)),
            "min_tian": float(round(min_tian_all, 1)),
            "guan_tian": float(round(guan_tian_all, 1)),
            "yin_tian": float(round(yin_tian_all, 1)),
            "min_tian_ratio": float(round(min_tian_all / total_land_all, 4)) if total_land_all > 0 else 0.0,
            "guan_tian_ratio": float(round(guan_tian_all / total_land_all, 4)) if total_land_all > 0 else 0.0,
            "yin_tian_ratio": float(round(yin_tian_all / total_land_all, 4)) if total_land_all > 0 else 0.0,
        }
    }


def apply_fangtian_survey(state, circuit: str, intensity: float = 0.25) -> Dict[str, Any]:
    """执行方田均税清丈（受控写操作，遵守田亩总量守恒）。

    清丈原理：
    - 查出该路庄园隐田 `yin_tian` 的一部分（由 intensity 决定，通常 20%~30%）；
    - 将查出田亩归还为纳税 `min_tian`；
    - `yin_tian - delta`，`min_tian + delta`；
    - 同步更新既有镜像 `p["hidden_land"]`，保持总田亩 `land` 守恒不变量。
    """
    p = _get_pref(state, circuit)
    if not p or float(p.get("land", 0) or 0) <= 0:
        return {"ok": False, "reason": "empty_circuit"}

    cur = derive_circuit_tenure(state, circuit)
    yin_now = cur["yin_tian"]
    if yin_now <= 0:
        return {"ok": False, "reason": "no_hidden_land"}

    clamped_intensity = max(0.05, min(0.60, float(intensity)))
    # M324/P1：统一度量衡抗隐田漏报；传统体制 resistance=0 时与接线前逐位一致。
    from core.foundation.metrology import active_effects
    _resistance = float(active_effects(state).get("tax_leakage_resistance", 0.0) or 0.0)
    _effective_intensity = min(1.0, clamped_intensity + max(0.0, _resistance))
    cleared = float(round(yin_now * _effective_intensity, 1))
    new_yin = yin_now - cleared
    new_min = cur["min_tian"] + cleared

    # 写入路级持久化结构
    tenure_store = p.setdefault("land_tenure", {})
    tenure_store["min_tian"] = new_min
    tenure_store["guan_tian"] = cur["guan_tian"]
    tenure_store["yin_tian"] = new_yin
    # 兼容同步镜像
    p["hidden_land"] = new_yin

    return {
        "ok": True,
        "circuit": circuit,
        "cleared_land": cleared,
        "new_min_tian": new_min,
        "new_yin_tian": new_yin,
        "guan_tian": cur["guan_tian"],
        "total_land": cur["total_land"],
        "conserved": abs((new_min + cur["guan_tian"] + new_yin) - cur["total_land"]) < 1e-4,
    }
