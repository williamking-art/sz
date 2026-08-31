# -*- coding: utf-8 -*-
"""宋祚 · contract_adapter 契约统一映射（T5 契约统一，言枢密）。

把 34 个 AI 契约（推演类 *_decide + 叙事类）输出统一为 {changes, narrative} 双通道视图：

- **changes**：唯一改状态通道的**表达层**（{field, delta_tier, region?}）。实际落地仍由
  各契约既有结算逻辑消费（_economy_ai 等槽位 → 12 步结算）；adapter 提供统一视图，
  **不改任何契约 validate/返回值**（旧消费方零破坏）。
- **narrative**：AI 叙事文本（受 narrative_guard 护栏），从契约的叙事字段映射取。
- **narrative_hint**：组装辅助（当前留空，供 narrative_assembler 扩展）。

设计铁律：
- 映射表是**表达层权威**（契约字段 → changes 字段名），落地语义保留在契约自身；
- 未列出的契约走通用 fallback（全部顶层标量键透传为 changes），保证 34 契约全覆盖；
- free_effect_decide 自带 effects/cost 语义（已是 changes 载体），adapter 原样映射不重写。
"""
from __future__ import annotations

# 推演类契约 → 顶层字段清单（表达层：字段名 → changes {field, delta_tier}）
# 精确列出已实勘确认的契约；未列出者 to_changes 走通用 fallback（全部顶层标量键）。
CONTRACT_FIELD_MAP = {
    "economy_decide": (
        "景气", "士绅", "士绅力度", "生产", "窖银", "城市化", "回乡", "科举",
        "jiaozi_trust", "shortage", "maritime", "bank", "price_trend",
    ),
    "diplomacy_decide": ("attitude", "sui_gong", "alliance"),
    "military_decide": ("power", "army", "training", "morale", "levy"),
    "relief_decide": ("disaster_level", "relief", "refugee"),
    "invest_decide": ("field", "fund", "tier", "months"),
    "era_decide": ("era_change", "narrative"),
    "faction_decide": ("factions", "events", "narrative"),
    "land_local_decide": ("prefectures", "narrative"),
    "survey_settle": ("hidden_cleared", "gentry_returned", "outcome"),
    "free_effect_decide": (),   # effects/cost 为 dict/list，语义保留在契约自身（不拍平）
    # 叙事类契约：changes 恒空（叙事不改状态；dialogue 的 mood/intent 为记录字段非状态变更）
    "monthly_report": (), "event_narrative": (), "dialogue": (), "advice": (),
    "council_review": (), "parse_decree": (), "final_eval": (),
    # finance/treasury/granary_decide 字段以契约 validate 为准，走通用 fallback
}

# 叙事类字段（不进 changes：fallback 与显式映射均排除）
_NARRATIVE_KEYS = frozenset(
    {"narrative", "narrative_hint", "report", "reply", "advice", "commentary",
     "memo", "body", "scenes", "court_report", "gazette", "title", "desc"}
)

# 叙事类/含叙事契约 → narrative 取值字段（按优先级取首个非空字符串）
NARRATIVE_FIELD_MAP = {
    "monthly_report": ("report", "narrative"),
    "event_narrative": ("narrative",),
    "dialogue": ("reply",),
    "advice": ("advice",),
    "council_review": ("memo", "narrative"),
    "parse_decree": ("narrative", "body"),
    "final_eval": ("commentary",),
    "faction_decide": ("narrative",),
    "land_local_decide": ("narrative",),
    "era_decide": ("narrative",),
    "free_effect_decide": ("narrative",),
    "invest_decide": ("narrative",),
}


def _is_error(result) -> bool:
    """_error 标记（AI 缺失/契约失败）→ 统一空 changes + 透传 _error。"""
    return isinstance(result, dict) and bool(result.get("_error"))


def to_changes(contract_name: str, result) -> list:
    """契约输出 → changes 数组 [{field, delta_tier}]（表达层，不改落地路径）。

    - 嵌套结构（factions/events/prefectures/era_change/effects）不拍平——
      语义保留在契约自身，adapter 只做表达层统一；
    - 未列契约 → 全部顶层标量键透传（通用 fallback）。
    """
    if not isinstance(result, dict) or _is_error(result):
        return []
    fields = CONTRACT_FIELD_MAP.get(contract_name)
    if fields is None:
        fields = tuple(k for k, v in result.items()
                       if not isinstance(v, (dict, list)) and k not in _NARRATIVE_KEYS)
    changes = []
    for f in fields:
        if f in result and not isinstance(result[f], (dict, list)) and f not in _NARRATIVE_KEYS:
            changes.append({"field": f, "delta_tier": str(result[f])})
    return changes


def to_unified(contract_name: str, result) -> dict:
    """统一 {changes, narrative, narrative_hint} 视图（消费端用，不改原返回值）。

    叙事类 changes 默认空数组（叙事不改状态）；_error 契约透传 _error 标记（不伪造）。
    """
    if _is_error(result):
        return {"changes": [], "narrative": "", "narrative_hint": "",
                "_error": result.get("_error")}
    changes = to_changes(contract_name, result)
    narrative = ""
    if isinstance(result, dict):
        for k in NARRATIVE_FIELD_MAP.get(contract_name, ("narrative",)):
            v = result.get(k)
            if isinstance(v, str) and v.strip():
                narrative = v.strip()
                break
    return {"changes": changes, "narrative": narrative, "narrative_hint": ""}
