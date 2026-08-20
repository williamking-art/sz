# -*- coding: utf-8 -*-
"""宋祚 · 建筑-时代交互（言枢密方案，告别纯数值）。

- **era_state 五维**（economy_center/culture/commerce/military/urban，0-100，认知层档位
  兴/平/衰 程序定幅迁移 ERA_TREND_SHIFT）。
- **上行调制**（整体发展 → 建筑）：国库充足+景气中/大 → 建造速度 ×1.3、新建筑解锁
  （ERA_UP_LINK）；国库紧张/钱荒/灾荒 → 新建抑制（复用 projects 缺料停滞）；战乱/灾荒
  事件 → 建筑毁损（level 降、记 destroyed/ruined）；政策取向 → 建筑成本调制。
- **下行联动**（建筑 → 整体发展）：水利/常平仓 → economy_center、学校 → culture、
  市舶/商铺 → commerce、军营/城防 → military、农田/庄园 → economy_center——乘数走既有
  公式，累积到 era_state 五维（ERA_BUILDING_LINK）。
- **记忆记录**：建筑实体（type=building）+ 兴衰事件（建于/毁于/荒废/重修）写记忆图谱。
"""
from content.data import (
    ERA_DIMENSIONS, ERA_TREND_SHIFT, ERA_BUILDING_LINK, ERA_UP_LINK,
)


def era_trend(era_state: dict, dim: str) -> str:
    """认知层档位词：≥70 兴 / 40-69 平 / <40 衰。"""
    v = era_state.get(dim, 50)
    return "兴" if v >= 70 else "衰" if v < 40 else "平"


def era_migrate(era_state: dict, dim: str, trend: str, region: str = "") -> int:
    """era_state 按 trend 程序定幅迁移（兴/平/衰 ±10），clamp [0,100]。"""
    if dim not in ERA_DIMENSIONS:
        return era_state.get(dim, 50)
    shift = ERA_TREND_SHIFT.get(trend, 0)
    v = max(0, min(100, era_state.get(dim, 50) + shift))
    era_state[dim] = v
    return v


def settle_era_links(state, log):
    """下行联动：建筑（政府 projects + POP buildings）累积到 era_state 五维。"""
    era = state.era_state
    # 政府建筑（projects 中建筑类；兼容 list/dict 结构）按 effect 映射维度
    projects = getattr(state, "projects", None)
    if isinstance(projects, dict):
        _projs = list(projects.values())
    elif isinstance(projects, list):
        _projs = list(projects)
    else:
        _projs = []
    for proj in _projs:
        if not isinstance(proj, dict):
            continue
        btype = proj.get("type", "") or proj.get("name", "")
        dim = ERA_BUILDING_LINK.get(btype)
        if dim:
            lv = int(proj.get("level", 1))
            era[dim] = max(0, min(100, era.get(dim, 50) + lv))
    # POP 建筑（各路）
    for p in state.prefectures.values():
        for bt, lv in (p.get("buildings") or {}).items():
            dim = ERA_BUILDING_LINK.get(bt)
            if dim:
                era[dim] = max(0, min(100, era.get(dim, 50) + int(lv)))
    return era


def build_speed_mod(state) -> float:
    """上行调制：国库充足+景气中/大 → 建造速度 ×1.3；国库紧张/钱荒/灾荒 → 抑制 ×0.7
    （抑制优先于加速——钱荒/紧张时景气再好也不大兴土木）。"""
    treasury = getattr(state, "treasury", 0)
    shortage = getattr(state, "coin", {}).get("shortage", 0.3)
    boom = (getattr(state, "_economy_ai", None) or {}).get("景气", "中")
    if treasury < 200_000 or shortage >= 0.6:
        return 0.7
    if treasury >= 1_000_000 and boom in ("中", "大", "巨", "极"):
        return ERA_UP_LINK["build_speed_boost"]
    return 1.0


def damage_buildings(state, log, reason="战乱"):
    """战乱/灾荒 → 建筑毁损（level 降、记 destroyed/ruined；史实：金兵毁宫室/水利失修）。"""
    from memory.memory_graph import MemoryGraph
    damaged = 0
    for p in state.prefectures.values():
        b = p.get("buildings") or {}
        for bt, lv in list(b.items()):
            if lv > 1:
                b[bt] = lv - 1
                damaged += 1
            elif lv == 1:
                del b[bt]
                damaged += 1
    if damaged:
        state.era_building_log.append({"turn": state.turn, "event": f"毁于{reason}", "count": damaged})
        log.append(f"[时代] {reason}：{damaged} 处建筑受损/毁损")
    # 记忆图谱：兴衰事件（毁损）
    try:
        g = getattr(state, "memory", None)
        if g is not None:
            g.add_entity(f"event_era_{state.turn}_{reason}", "event", f"{reason}建筑毁损",
                         turn=getattr(state, "turn", 0))
    except Exception:
        pass
    return damaged


def record_building_memory(state, btype, region, event, turn=0):
    """记忆记录：建筑实体（type=building）+ 兴衰事件（建于/毁于/荒废/重修）。"""
    try:
        g = getattr(state, "memory", None)
        if g is None:
            return
        g.add_entity(f"building_{btype}_{region}", "institution", f"{region}{btype}",
                     {"type": "building"}, turn=turn)
        g.add_relation(f"building_{btype}_{region}", f"era_{event}", "produces",
                       weight=1.0, turn=turn, note=event)
    except Exception:
        pass


def era_brief(state) -> str:
    """时代叙事（认知层档位，脱敏）：「{dim}兴/平/衰」。"""
    return "；".join(f"{d}{era_trend(state.era_state, d)}" for d in ERA_DIMENSIONS)


# ---------------- 建筑跟随科技（用户指示） ----------------
def building_unlocked(state, btype: str) -> bool:
    """科技解锁判定：TECH_BUILDING_MAP 无对应（基础建筑）→ 恒可建；
    有对应（火器作坊/市舶司/铁作/学校高级）→ 副指标/level 达阈值才可建。
    （对齐「蓝图库只列现在真造得出的」设计）"""
    from content.data import TECH_BUILDING_MAP
    for key, (bt, th) in TECH_BUILDING_MAP.items():
        if bt != btype:
            continue
        tech = getattr(state, "tech", {}) or {}
        if key in ("hydraulics", "gunpowder", "iron"):
            return int(tech.get(key, 0)) >= th
        return int(tech.get("level", 0)) >= th
    return True   # 基础建筑恒可建


def building_level_cap(state, btype: str) -> int:
    """科技升级上限：建筑 Lv 上限 = f(科技等级)（level 每 20 → +1 Lv，clamp 1~5）；
    科技低 → 建筑只能低 Lv，研出对应科技 → 解锁高 Lv。"""
    from content.data import BUILDING_LEVEL_CAP_STEP
    tech = getattr(state, "tech", {}) or {}
    return max(1, min(5, 1 + int(tech.get("level", 0)) // BUILDING_LEVEL_CAP_STEP))


def tech_build_bonus(state) -> float:
    """建筑反馈科技：学校/书院 → 科技研发加速（月 tech level 加成，已有机制扩展）。"""
    from content.data import ERA_BUILDING_LINK
    bonus = 0.0
    # 政府学校建筑 + POP 无（学校为政府类）
    projects = getattr(state, "projects", None)
    if isinstance(projects, dict):
        _projs = list(projects.values())
    elif isinstance(projects, list):
        _projs = list(projects)
    else:
        _projs = []
    for proj in _projs:
        if isinstance(proj, dict) and (proj.get("type") in ("学校", "书院")):
            bonus += int(proj.get("level", 1)) * 0.05
    return min(1.0, bonus)


# ---------------- 新旧产业规模化 + AI/大臣感知（用户指示） ----------------
def calc_industry_scale(state):
    """产业规模统计（程序）：旧/新产业规模 = Σ(建筑数量×等级)、结构 = 新产业占比。"""
    from content.data import INDUSTRY_CLASS
    old_set, new_set = set(INDUSTRY_CLASS["old"]), set(INDUSTRY_CLASS["new"])
    old_scale = new_scale = 0
    # 政府 projects
    projects = getattr(state, "projects", None)
    if isinstance(projects, dict):
        _projs = list(projects.values())
    elif isinstance(projects, list):
        _projs = list(projects)
    else:
        _projs = []
    for proj in _projs:
        if not isinstance(proj, dict):
            continue
        bt = proj.get("type", "") or proj.get("name", "")
        lv = int(proj.get("level", 1))
        if bt in old_set:
            old_scale += lv
        elif bt in new_set:
            new_scale += lv
    # POP buildings
    for p in state.prefectures.values():
        for bt, lv in (p.get("buildings") or {}).items():
            if bt in old_set:
                old_scale += int(lv)
            elif bt in new_set:
                new_scale += int(lv)
    total = old_scale + new_scale
    share = new_scale / total if total > 0 else 0.0
    return {"old_scale": old_scale, "new_scale": new_scale,
            "total": total, "share": share}


def industry_share_word(share: float) -> str:
    """产业结构认知层档位词（脱敏）：纯旧产业/新芽初萌/新旧并立/新产业主导。"""
    from content.data import INDUSTRY_SHARE_TIERS
    for word, threshold in INDUSTRY_SHARE_TIERS:
        if share >= threshold:
            return word
    return "纯旧产业"


def industry_brief(state) -> str:
    """认知层感知（AI/大臣可见，脱敏档位）：「旧产业 N / 新产业 N / 结构档位」。"""
    sc = calc_industry_scale(state)
    return (f"产业：旧{sc['old_scale']} 新{sc['new_scale']} "
            f"（{industry_share_word(sc['share'])}）")


def settle_industry_shift(state, log):
    """新旧产业交互：新产业兴起 → 旧产业相对衰落（转型阵痛叙事）；记忆图谱记录产业变迁。"""
    sc = calc_industry_scale(state)
    if sc["new_scale"] <= 0 or sc["old_scale"] <= 0:
        return sc
    # 转型阵痛：旧产业相对衰落（POP 商品消费率微降？简化：log 叙事 + era 认知）
    log.append(f"[产业] {industry_share_word(sc['share'])}——旧产业 {sc['old_scale']}，新产业 {sc['new_scale']}")
    # 记忆图谱：产业变迁记录（新产业建筑建于 X 年、扩张）
    try:
        g = getattr(state, "memory", None)
        if g is not None:
            g.add_entity(f"industry_{state.turn}", "event", f"新产业{sc['new_scale']}·旧产业{sc['old_scale']}",
                         turn=getattr(state, "turn", 0))
    except Exception:
        pass
    return sc
