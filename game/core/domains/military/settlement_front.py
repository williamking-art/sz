# -*- coding: utf-8 -*-
from __future__ import annotations

import random

"""
宋祚 · 金军南侵战役结算。

> 由 core/settlement_imperial.py 按域拆出（2026-10-07 用户裁定「拆开」）。
> 归 military 域：只管边关战役（战场结算 / 伤亡分摊 / 防线告破），不含帝王行动与隐户归籍。
"""


def _settle_front_battle(state, log):
    """金军南侵：沿边诸军 vs 金军 power，伤亡按战力占比分摊，尾差归主将部。"""
    jin = state.external["金"]
    if jin.get("invasion_will", 0) >= 90 and state.year >= 1122:
        if random.random() < 0.08:
            from core.domains.military.army_models import army_power, army_power_total, resolve_battle
            jin["invasion_will"] = 80
            gunpowder = state.tech.get("gunpowder", 20)
            front_routes = ("河北路", "河东路", "陕西路")
            front_units = [u for u in state.army_units if u.station in front_routes]
            my_power = army_power_total(front_units, gunpowder)
            jin_power = state.external["金"]["power"]
            win, loss_power, breach = resolve_battle(my_power, jin_power)
            # 按各 unit 战力占比把 loss_power 分摊成真实伤亡（向下取整，余数归主将部）
            casualty = 0
            if my_power > 0 and loss_power > 0 and front_units:
                powers = [army_power(u, gunpowder) for u in front_units]
                total_p = sum(powers)
                # 总伤亡人数 = 沿线总兵力 × (loss_power/my_power)
                total_troops = sum(u.troops for u in front_units)
                total_cas = int(total_troops * (loss_power / my_power))
                assigned = 0
                # 主将部 = 战力最大的 unit（余数归它）
                main_idx = max(range(len(front_units)), key=lambda i: powers[i])
                for i, u in enumerate(front_units):
                    if i == main_idx:
                        continue
                    part = int(total_cas * (powers[i] / total_p)) if total_p > 0 else 0
                    part = min(part, u.troops)
                    u.add_troops(-part)
                    assigned += part
                rest = min(total_cas - assigned, front_units[main_idx].troops)
                front_units[main_idx].add_troops(-max(0, rest))
                casualty = assigned + max(0, rest)
            if breach:
                for line in ("北线_太原真定", "北线_陕西"):
                    if line in state.defense_lines:
                        f0 = state.defense_lines[line].get("fortification", 0)
                        state.defense_lines[line]["fortification"] = max(0, min(100, int(f0 * 0.5)))
            if win:
                log.append(f"[紧急] 金军大举南下！沿边诸军力战却敌，伤亡约{casualty}人")
            else:
                log.append(f"[紧急] 金军大举南下！沿边诸军败绩，防线告破，伤亡约{casualty}人")
            state._derive_defense_lines()
