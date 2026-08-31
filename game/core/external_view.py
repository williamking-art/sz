# -*- coding: utf-8 -*-
"""外部势力 POP 简版视图 + 省份派生（用户：POP 适配给外部势力 + 省份信息）。

- `external_pop_view(state, name)`：势力简版 POP 视图（人口/月税/地/粮 + 国力/军力）
  ——数据已存在（EXTERNAL_REGIMES），只聚合展示，不新增复杂六类；
- `external_provinces(name)`：按 EXTERNAL_PROVINCES 权重分摊势力人口/税到各省（派生）。
"""
from content.data import EXTERNAL_REGIMES, EXTERNAL_PROVINCES, _EXTERNAL_PROVINCES_DEFAULT


def external_pop_view(state, name: str) -> dict:
    """势力简版 POP 视图（外交面板展示用）。

    返回 {name, type, population, monthly_tax, land, grain, power, army}——
    population 为万口、monthly_tax 月税、power 国力（运行时动态）、army 军力近似。
    静态字段（人口/税/地/粮）来自 EXTERNAL_REGIMES；power/attitude 用 state.external 动态值。
    """
    reg_static = EXTERNAL_REGIMES.get(name)
    if not reg_static:
        return {}
    dyn = (getattr(state, "external", None) or {}).get(name) or {}
    population = int(reg_static.get("population", 0))
    power = int(dyn.get("power") or reg_static.get("power", 0))
    return {
        "name": name,
        "type": str(reg_static.get("type", "")),
        "population": population,          # 万口
        "monthly_tax": int(reg_static.get("monthly_tax", 0)),
        "land": int(reg_static.get("land", 0)),
        "grain": int(reg_static.get("grain", 0)),
        "power": power,
        "army": max(0, power * population // 10),   # 军力近似 = 国力×人口/10
    }


def external_provinces(state, name: str) -> list:
    """势力省份派生：按权重分摊人口/税（省为展示层）。

    返回 [{name, weight, population, monthly_tax}]（population 万口、税按权重）。
    """
    reg_static = EXTERNAL_REGIMES.get(name)
    if not reg_static:
        return []
    provs = EXTERNAL_PROVINCES.get(name, _EXTERNAL_PROVINCES_DEFAULT)
    population = int(reg_static.get("population", 0))
    monthly_tax = int(reg_static.get("monthly_tax", 0))
    out = []
    _acc_pop = 0
    _acc_tax = 0
    for i, (pname, weight) in enumerate(provs):
        if i == len(provs) - 1:
            # 尾差归末位（int 分摊截断不丢——Σ == 总量）
            _pop = population - _acc_pop
            _tax = monthly_tax - _acc_tax
        else:
            _pop = int(population * weight)
            _tax = int(monthly_tax * weight)
        _acc_pop += _pop
        _acc_tax += _tax
        out.append({"name": pname, "weight": weight,
                    "population": _pop, "monthly_tax": _tax})
    return out
