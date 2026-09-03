# -*- coding: utf-8 -*-
"""宋祚 · 帝国修正机制（core/legacy_mechanic.py）

参考《明末：捞金模拟器》的「帝国修正（legacies）」：开局即存在的条件式长期修正符，
带明确消除条件，让开局有历史包袱与破局目标。

与 state.longterm_effects（玩家主动发起）不同，legacies 是「开局即存在、条件式、
带消除条件」的历史包袱。本模块只做定义 + 月度结算 + 消除条件判定，不写状态；
由 settlement.run_monthly_settlement 在 Step 6.8 之后调用。

设计原则：
- 效果施加走**非守恒字段**（税率/民心/财政/满意度等），不破坏 state_applier 经济守恒；
- 消除条件判定基于 state 现有字段（factions/land/tech/财政/民心等），O(legacies 数) 轻量；
- AI 缺失时程序兜底不伪造：仅按定义施加确定性效果。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. 帝国修正定义（LEGACY_DEFS）
#    每项：{key, name, desc, effect(月度施加), clear_condition(消除条件), clear_desc}
#    effect 为可调用函数 (state, log) -> None，施加确定性修正（非守恒字段）。
#    clear_condition 为可调用函数 (state) -> bool，判定是否满足消除条件。
# ---------------------------------------------------------------------------

# 消除条件辅助：读取 state 字段的容错取值
def _num(state, path, default=0.0):
    """按点分路径读取 state 数值字段（容错，缺省返回 default）。"""
    cur = state
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part, default)
        else:
            cur = getattr(cur, part, default)
    try:
        return float(cur)
    except (TypeError, ValueError):
        return default


def _clear_new_party(state) -> bool:
    """新党专权消除：新旧党争缓和（无单一派系影响力独大）。"""
    # 若存在 faction_conflict 字段且为 0，或新党影响力 < 阈值，则消除
    conflict = _num(state, "faction_conflict", 0)
    if conflict > 0:
        return False
    # 无派系冲突字段时，检查派系影响力是否趋于平衡（最大影响力 < 60）
    try:
        infs = [f.get("influence", 0) for f in state.factions.values()]
        return max(infs) < 60 if infs else True
    except Exception:
        return False


def _clear_redundant_officials(state) -> bool:
    """冗官冗费消除：变法节流已施行（waste_reform.active）。"""
    try:
        return bool(state.waste_reform.get("active"))
    except Exception:
        return False


def _clear_hidden_land(state) -> bool:
    """隐田蔽课消除：清丈田亩后隐漏率下降（land.hidden_rate < 0.2）。"""
    return _num(state, "land.hidden_rate", 0.35) < 0.2


def _clear_liao_xia_border(state) -> bool:
    """辽夏边患消除：边境军备充足（defense_lines 总 garrison 充足）。"""
    try:
        total_garrison = sum(
            v.get("garrison", 0) for v in state.defense_lines.values())
        return total_garrison >= 200000
    except Exception:
        return False


def _clear_huashigang(state) -> bool:
    """花石纲民怨消除：民心恢复（population_satisfaction >= 60）。"""
    return _num(state, "population_satisfaction", 0) >= 60


# 效果施加（确定性修正，非守恒字段）
def _eff_new_fund(state, log):
    """新党专权：士绅不满 +，朝局党争 +。"""
    state.population_satisfaction = max(0, state.population_satisfaction - 1)
    log.append("[修正] 新党专权：党争纷纭，士绅离心，民心微损")


def _eff_redundant_officials(state, log):
    """冗官冗费：财政负担加重（俸给支出上浮）。"""
    # 通过 state 的财政字段施加（非守恒，走结算函数）
    state.statistics["total_expense"] = state.statistics.get("total_expense", 0) + 20000
    log.append("[修正] 冗官冗费：俸给浩繁，府库日耗")


def _eff_hidden_land(state, log):
    """隐田蔽课：赋税流失，财政减收。"""
    state.statistics["total_income"] = max(0, state.statistics.get("total_income", 0) - 15000)
    log.append("[修正] 隐田蔽课：田赋隐匿，岁入有亏")


def _eff_liao_xia_border(state, log):
    """辽夏边患：军费压力，边境不安。"""
    state.statistics["total_expense"] = state.statistics.get("total_expense", 0) + 30000
    log.append("[修正] 辽夏边患：边烽有警，军费浩繁")


def _eff_huashigang(state, log):
    """花石纲民怨：东南民怨，民心受损。"""
    state.population_satisfaction = max(0, state.population_satisfaction - 1)
    log.append("[修正] 花石纲扰民，东南骚动，民怨渐起")


LEGACY_DEFS = {
    "new_party_dominance": {
        "key": "new_party_dominance",
        "name": "新党专权",
        "desc": "元祐更化以来，新党把持朝政，党争纷纭，士绅离心。",
        "effect": _eff_new_fund,
        "clear_cond": _clear_new_party,
        "clear_desc": "调和新旧党争，使党争缓和（faction_conflict 归零）。",
    },
    "redundant_officials": {
        "key": "redundant_officials",
        "name": "冗官冗费",
        "desc": "官冗于上，吏冗于下，俸给浩大，府库日耗。",
        "effect": _eff_redundant_officials,
        "clear_cond": _clear_redundant_officials,
        "clear_desc": "裁汰冗官冗费（施行 curtail_waste）。",
    },
    "hidden_land": {
        "key": "hidden_land",
        "name": "隐田蔽课",
        "desc": "豪强隐田，赋税隐匿，国课有亏。",
        "effect": _eff_hidden_land,
        "clear_cond": _clear_hidden_land,
        "clear_desc": "清丈田亩，检括隐田（施行 land_survey）。",
    },
    "liao_xia_border": {
        "key": "liao_xia_border",
        "name": "辽夏边患",
        "desc": "北有契丹，西有夏贼，边烽有警，军费劲繁。",
        "effect": _eff_liao_xia_border,
        "clear_cond": _clear_liao_xia_border,
        "clear_desc": "整军经武（border_garrison）或与辽夏和议（peace_treaty）。",
    },
    "huashigang_grievance": {
        "key": "huashigang_grievance",
        "name": "花石纲民怨",
        "desc": "东南花石纲扰民，民怨沸腾，隐田蔽课。",
        "effect": _eff_huashigang,
        "clear_cond": _clear_huashigang,
        "clear_desc": "停罢花石纲（stop_huashigang）或民心恢复至 60 以上。",
    },
}


# ---------------------------------------------------------------------------
# 2. 初始化与结算
# ---------------------------------------------------------------------------

def init_legacies(state) -> None:
    """开局初始化帝国修正（legacies）：全部生效，进度 0。"""
    state.legacies = {}
    for key, spec in LEGACY_DEFS.items():
        state.legacies[key] = {
            "key": key,
            "name": spec["name"],
            "desc": spec["desc"],
            "clear_desc": spec["clear_desc"],
            "active": True,
            "progress": 0.0,   # 0~1，消除进度（供 UI 展示）
            "cleared": False,
        }


def settle_legacies(state, log) -> None:
    """月度结算：对每个生效 legacy 施加效果，并判定消除条件。

    返回：无（直接写 state 与 log）。log 为 list，追加结算日志。
    """
    if not state.legacies:
        return
    for key, spec in LEGACY_DEFS.items():
        entry = state.legacies.get(key)
        if not entry or not entry.get("active"):
            continue
        # 施加效果
        try:
            spec["effect"](state, log)
        except Exception:
            pass
        # 判定消除条件
        try:
            cleared = spec["clear_cond"](state)
        except Exception:
            cleared = False
        if cleared:
            entry["active"] = False
            entry["cleared"] = True
            entry["progress"] = 1.0
            log.append(f"[修正] 消除：{spec['name']}——{spec['clear_desc']}")
        else:
            # 进度估算：基于关键字段的近似进度（供 UI 展示）
            entry["progress"] = _estimate_progress(key, state)


def _estimate_progress(key: str, state) -> float:
    """估算消除进度（0~1），供 UI 展示。基于关键状态字段的近似。"""
    if key == "new_party_dominance":
        try:
            infs = [f.get("influence", 0) for f in state.factions.values()]
            return max(0.0, min(1.0, 1.0 - (max(infs) if infs else 0) / 60.0))
        except Exception:
            return 0.0
    if key == "redundant_officials":
        try:
            return 1.0 if state.waste_reform.get("active") else 0.0
        except Exception:
            return 0.0
    if key == "hidden_land":
        return max(0.0, min(1.0, (0.35 - _num(state, "land.hidden_rate", 0.35)) / 0.15))
    if key == "liao_xia_border":
        try:
            total = sum(v.get("garrison", 0) for v in state.defense_lines.values())
            return max(0.0, min(1.0, total / 200000.0))
        except Exception:
            return 0.0
    if key == "huashigang_grievance":
        return max(0.0, min(1.0, _num(state, "population_satisfaction", 0) / 60.0))
    return 0.0


def active_legacies(state) -> list:
    """返回当前生效的 legacies 列表（供 UI / 简报展示）。"""
    return [e for e in state.legacies.values() if e.get("active")]


def cleared_legacies(state) -> list:
    """返回已消除的 legacies 列表。"""
    return [e for e in state.legacies.values() if e.get("cleared")]


__all__ = [
    "LEGACY_DEFS", "init_legacies", "settle_legacies",
    "active_legacies", "cleared_legacies",
]