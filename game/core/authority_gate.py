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

__all__ = ["check_matter_authority", "check_decree_authority"]


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

