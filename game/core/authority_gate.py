# -*- coding: utf-8 -*-
"""Actor 判权门面（P0a，2026-10-18）。

- **唯一职责**：把 executor（人/职位/机构/dict）解析为具体 actor，
  再按 `permission_model` 的**职位权限**判定；
- 只读：不写 state、不读派系 satisfaction/influence/capture；
- 异常向上抛，由调用方 fail-closed（decree_confirm / settle_reform 等）；
- `institution.check_authority` 保留为参数型旧门面，不在本模块内改写。
"""
from __future__ import annotations

from typing import Any, Tuple

from core.permission_model import has_permission, resolve_actor

__all__ = [
    "check_matter_authority", "check_decree_authority",
    "matters_for_effects", "matters_for_finance_changes",
    "check_effects_authority",
]

# 财政 effect → 事权（单一来源；新增财政 effect 必须登记在这里）
FISCAL_EFFECT_MATTERS = {
    "treasury": "度支调度",
    "treasury_income": "国库",
    "treasury_spend": "度支调度",
    "commerce_tax": "赋税",
    "tax": "赋税",
    "land_tax": "赋税",
    "finance_rates": "度支调度",
    "granary": "国库",
    # 实际诏令/结算 handler 使用的键（2026-10-18 JEV P1b 复审补登）
    "audit_route": "财政勾稽",
    "relief": "度支调度",
    "he_mi": "度支调度",
    "military_supply": "度支调度",
    "grain_stabilize": "度支调度",
    "granary_reform": "度支调度",
    "single_whip": "赋税",
    "pay_reform": "度支调度",
    "curtail_waste": "度支调度",
    "reduce_office": "度支调度",
    "anti_corruption": "财政勾稽",
    "confiscate": "财政勾稽",
}

# 财政草案 change.path → 事权（按路径关键词）
FINANCE_PATH_MATTERS = {
    "treasury": "度支调度",
    "commerce_tax": "赋税",
    "tax": "赋税",
    "finance": "度支调度",
    "audit": "财政勾稽",
    "confiscate": "国库",
}


def matters_for_effects(effects) -> list:
    """从诏令/口谕 effects 提取财政事权（含 institution 参数的 authority）。"""
    if not isinstance(effects, dict):
        return []
    out = []
    inst = effects.get("institution")
    if isinstance(inst, dict):
        from content.data import INSTITUTION_PARAM_SPEC
        for key in inst:
            spec = INSTITUTION_PARAM_SPEC.get(str(key)) or {}
            matter = str(spec.get("authority") or "").strip()
            if matter and matter not in out:
                out.append(matter)
    for key in effects:
        matter = FISCAL_EFFECT_MATTERS.get(str(key))
        if matter and matter not in out:
            out.append(matter)
    return out


def matters_for_finance_changes(changes) -> list:
    """从财政草案 changes[*].path 提取事权。"""
    out = []
    for change in changes or []:
        if not isinstance(change, dict):
            continue
        path = str(change.get("path") or "")
        for token, matter in FINANCE_PATH_MATTERS.items():
            if token in path and matter not in out:
                out.append(matter)
    return out


def check_effects_authority(state, effects, executor):
    """财政 effects 的 actor 判权 → `(ok, actor_or_reason, matters)`。"""
    matters = matters_for_effects(effects)
    if not matters:
        return True, "", []
    if not executor:
        # 默认中性：无 executor 的旧调用保留，由调用方计 legacy_unchecked_fiscal。
        return True, "legacy_unchecked", matters
    actor = ""
    for matter in matters:
        ok, actor_or_reason = check_matter_authority(state, executor, matter)
        if not ok:
            return False, actor_or_reason, matters
        actor = actor_or_reason
    return True, actor, matters


def check_matter_authority(state, executor, matter: str) -> Tuple[bool, str]:
    """校验 executor 是否因**在任职位**持有某具体事权 → `(ok, actor_or_reason)`。"""
    key = str(matter or "").strip()
    if not key:
        return False, "未指定事权"
    actor = resolve_actor(state, executor)
    if not actor:
        return False, f"无法解析承办人（{executor!r}）"
    if not has_permission(state, actor, key):
        return False, f"「{actor}」不掌「{key}」事权，拒绝"
    return True, actor


def check_decree_authority(state, key: str, executor) -> Tuple[bool, str]:
    """参数/效果键 → 事权 → actor 判权；无 `authority` 字段的键恒放行。"""
    from core.domains.administration.institution import _matter_of

    matter = _matter_of(str(key or ""))
    if not matter:
        return True, ""
    return check_matter_authority(state, executor, matter)

