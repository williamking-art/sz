# -*- coding: utf-8 -*-
"""权限模型（M1b-3c）：**权限挂在职位上**。

- 任职某职位 = 拥有该职位的事权；免职/空缺 = 失去该事权；
- 部门只是职位的集合与默认归属，不是权限主体；
- 同一人兼多个职位 → 权限取并集；
- 无「特旨授予/委任/收回」独立层：**任命/免职就是权限变更的唯一途径**。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from content.ministers.data import MINISTERS

__all__ = [
    "resolve_actor", "post_permissions", "has_permission",
    "permission_holders", "permission_capture",
    "authority_strict", "personnel_authority",
]


def _orgs(state) -> Dict[str, Any]:
    orgs = getattr(state, "central_orgs", None)
    return orgs if isinstance(orgs, dict) else {}


def _post_title(post: Any) -> str:
    if isinstance(post, dict):
        return str(post.get("title") or "").strip()
    if isinstance(post, str):
        return post.strip()
    return ""


def _post_matter_keys(org: Dict[str, Any], post: Any) -> set:
    """该**职位**的事权：优先职位自带的 `matter_keys`，否则继承机构默认事权。"""
    if isinstance(post, dict) and post.get("matter_keys") is not None:
        return {str(x) for x in (post.get("matter_keys") or [])}
    return (
        {str(x) for x in (org.get("matter_keys") or [])}
        | {str(x) for x in (org.get("authority") or [])}
    )


def _holders_of_org(state, org_name: str) -> List[str]:
    org = _orgs(state).get(org_name)
    if not isinstance(org, dict) or org.get("abolished"):
        return []
    posts = org.get("posts")
    holders = org.get("holders")
    if not isinstance(posts, list) or not isinstance(holders, dict):
        return []
    out = []
    for post in posts:
        title = _post_title(post)
        if not title:
            continue
        holder = str(holders.get(title) or "").strip()
        if holder:
            out.append(holder)
    return out


def _holder_of_post(state, post_title: str) -> Optional[str]:
    title = str(post_title or "").strip()
    if not title:
        return None
    for org in _orgs(state).values():
        if not isinstance(org, dict) or org.get("abolished"):
            continue
        holders = org.get("holders")
        if isinstance(holders, dict) and title in holders:
            holder = str(holders.get(title) or "").strip()
            if holder:
                return holder
    return None


def _is_holder(state, name: str) -> bool:
    for org in _orgs(state).values():
        if not isinstance(org, dict) or org.get("abolished"):
            continue
        holders = org.get("holders")
        if isinstance(holders, dict):
            if name in {str(v or "").strip() for v in holders.values()}:
                return True
    return False


def resolve_actor(state, executor) -> Optional[str]:
    """把 executor（人/职位/机构/dict）解析为**具体的人**；解析不到返回 None。"""
    if isinstance(executor, dict):
        for key in ("holder", "person", "minister", "actor"):
            name = str(executor.get(key) or "").strip()
            if name:
                return name
        post = str(executor.get("post") or "").strip()
        if post:
            return _holder_of_post(state, post)
        org = str(executor.get("org") or "").strip()
        if org:
            holders = _holders_of_org(state, org)
            return holders[0] if holders else None
        return None
    text = str(executor or "").strip()
    if not text:
        return None
    if text in MINISTERS or _is_holder(state, text):
        return text
    holder = _holder_of_post(state, text)
    if holder:
        return holder
    holders = _holders_of_org(state, text)
    return holders[0] if holders else None


def post_permissions(state, actor: str) -> set:
    """该人**当前所有职位**的事权并集；免职/空缺即自然消失。"""
    name = str(actor or "").strip()
    if not name:
        return set()
    out = set()
    for org in _orgs(state).values():
        if not isinstance(org, dict) or org.get("abolished"):
            continue
        posts = org.get("posts")
        holders = org.get("holders")
        if not isinstance(posts, list) or not isinstance(holders, dict):
            continue
        for post in posts:
            title = _post_title(post)
            if not title:
                continue
            if str(holders.get(title) or "").strip() == name:
                out |= _post_matter_keys(org, post)
    return out


def has_permission(state, actor: str, matter: str) -> bool:
    """该人当前是否因**在任某职位**而持有某权限。"""
    key = str(matter or "").strip()
    return bool(key) and key in post_permissions(state, actor)


def permission_holders(state, matter: str) -> List[str]:
    """当前因在任职位而持有某权限的全部人（去重、排序）。"""
    key = str(matter or "").strip()
    if not key:
        return []
    holders = set()
    for org in _orgs(state).values():
        if not isinstance(org, dict) or org.get("abolished"):
            continue
        posts = org.get("posts")
        names = org.get("holders")
        if not isinstance(posts, list) or not isinstance(names, dict):
            continue
        for post in posts:
            title = _post_title(post)
            if not title:
                continue
            holder = str(names.get(title) or "").strip()
            if holder and key in _post_matter_keys(org, post):
                holders.add(holder)
    return sorted(holders)


def permission_capture(state, matter: str) -> Dict[str, float]:
    """某权限当前被哪些派系的人持有（人数占比；缺失派系归「未登记」）。"""
    holders = permission_holders(state, matter)
    weights: Dict[str, float] = {}
    for actor in holders:
        fig = MINISTERS.get(actor) or {}
        faction = str(fig.get("faction") or "未登记")
        weights[faction] = weights.get(faction, 0.0) + 1.0
    total = sum(weights.values())
    return {fac: w / total for fac, w in sorted(weights.items())} if total > 0 else {}


def authority_strict(state) -> bool:
    """M1b-3：严格模式开关（`state.authority_strict`；默认 False = 兼容旧行为）。"""
    return bool(getattr(state, "authority_strict", False))


def _bump_stat(state, key: str) -> None:
    stats = getattr(state, "statistics", None)
    if isinstance(stats, dict):
        stats[key] = int(stats.get(key, 0) or 0) + 1


def personnel_authority(state, executor, matter: str = "官吏铨选"):
    """人事入口的统一**权限**判定 → `(ok, actor_or_reason, mode)`。

    - 显式 executor：解析为具体人 → 其在任职位是否含该事权；
    - 未显式：取当前**在任持有人**（按职位）；
    - 无人持权：严格模式拒绝，兼容模式保留旧行为并计 `legacy_unchecked_personnel`。
    """
    key = str(matter or "").strip()
    if executor is not None:
        actor = resolve_actor(state, executor)
        if actor and has_permission(state, actor, key):
            return True, actor, "explicit"
        return False, f"「{actor or executor}」不掌「{key}」事权，拒绝", "rejected"
    holders = permission_holders(state, key)
    if holders:
        _bump_stat(state, "authority_auto_resolved_personnel")
        return True, holders[0], "auto"
    if authority_strict(state):
        return False, f"无法解析掌「{key}」的在任职位持有人", "rejected"
    _bump_stat(state, "legacy_unchecked_personnel")
    return True, "", "legacy_unchecked"

