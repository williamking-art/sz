# -*- coding: utf-8 -*-
"""机构派系分布（M1a，只读，2026-10-18）。

契约见 `_dev_tools/game-docs/specs/cross-cutting/党争机制_实现契约速查表_2026-10-18.md` §4。

纪律：
- **纯只读**：不写 state、不新增字段、不调用任何写桥；
- 数据源只用 `central_orgs.posts/holders/abolished` + `MINISTERS.faction`；
- 五类份额守恒：
  `faction + vacant + unaffiliated + concurrent_discount + acting_discount = 1.0`；
- 缺失 ≠ 0 ≠ 1：无岗位定义输出 `defined=False`、`vacant_share=None`；
- 同一人在同一机构多岗：主职全额、每个次职 0.5 派系/未归属 + 0.5 兼任折损。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from content.ministers.data import MINISTERS

__all__ = ["institution_distribution", "distribution_of"]


def _known_factions(state: Any) -> Set[str]:
    """已登记派系集合（静态五派 + 运行时动态派系）。"""
    from content.data import FACTION_NAMES

    known = {str(x) for x in (FACTION_NAMES or [])}
    facs = getattr(state, "factions", None) or {}
    if isinstance(facs, dict):
        known |= {str(k) for k in facs}
    return known


def _post_title(post: Any) -> str:
    if isinstance(post, dict):
        return str(post.get("title") or "").strip()
    if isinstance(post, str):
        return post.strip()
    return ""


def _empty_org(
    *,
    defined: bool,
    error: Optional[str] = None,
    notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "defined": defined,
        "posts_total": 0,
        "filled_posts": 0,
        "vacant_share": None if not defined else 0.0,
        "unaffiliated_share": 0.0,
        "concurrent_discount_share": 0.0,
        "acting_discount_share": 0.0,
        "faction_share": {},
        "holders_detail": [],
        "concurrent_holders": [],
        "notes": list(notes or []),
    }
    if error:
        out["error"] = error
    return out


def _org_distribution(state: Any, org: Dict[str, Any]) -> Dict[str, Any]:
    posts = org.get("posts")
    if not isinstance(posts, list) or not posts:
        return _empty_org(defined=False, notes=["no_posts_defined"])

    titles = [_post_title(p) for p in posts]
    if any(not t for t in titles):
        return _empty_org(
            defined=False, error="invalid_post_entry", notes=["post_title_missing"]
        )
    if len(set(titles)) != len(titles):
        return _empty_org(
            defined=False, error="duplicate_post_title", notes=["duplicate_post_title"]
        )

    holders = org.get("holders")
    if not isinstance(holders, dict):
        holders = {}
    known = _known_factions(state)
    total = len(titles)

    # 人 -> 其在机构内的岗位下标（用于主职/兼任判定）
    holder_posts: Dict[str, List[int]] = {}
    for idx, title in enumerate(titles):
        holder = str(holders.get(title) or "").strip()
        if holder:
            holder_posts.setdefault(holder, []).append(idx)

    detail: List[Dict[str, Any]] = []
    concurrent_holders: List[str] = []
    faction_weights: Dict[str, float] = {}
    vacant = 0.0
    unaffiliated = 0.0
    concurrent_discount = 0.0
    acting_discount = 0.0
    filled = 0

    for idx, title in enumerate(titles):
        holder = str(holders.get(title) or "").strip()
        faction: Optional[str] = None
        if holder:
            fig = MINISTERS.get(holder) or {}
            raw_faction = fig.get("faction")
            faction = str(raw_faction).strip() if raw_faction else None

        is_primary = bool(
            holder and holder_posts.get(holder) and holder_posts[holder][0] == idx
        )
        concurrent = bool(holder and len(holder_posts.get(holder, [])) > 1)
        if concurrent and holder not in concurrent_holders:
            concurrent_holders.append(holder)

        post_weight = 1.0
        faction_w = 0.0
        unaff_w = 0.0
        disc_w = 0.0
        if not holder:
            vacant += post_weight
        else:
            filled += 1
            share = 1.0 if is_primary else 0.5
            if faction and faction in known:
                faction_w = share
                faction_weights[faction] = faction_weights.get(faction, 0.0) + share
            else:
                unaff_w = share
                unaffiliated += share
            if not is_primary:
                disc_w = 0.5
                concurrent_discount += 0.5

        detail.append(
            {
                "post": title,
                "holder": holder,
                "faction": faction,
                "post_weight": post_weight,
                "faction_counted_weight": faction_w,
                "unaffiliated_weight": unaff_w,
                "concurrent_discount_weight": disc_w,
                "acting_discount_weight": 0.0,
                "is_primary": is_primary,
                "concurrent": concurrent,
                "acting": False,
            }
        )

    return {
        "defined": True,
        "posts_total": total,
        "filled_posts": filled,
        "vacant_share": vacant / total,
        "unaffiliated_share": unaffiliated / total,
        "concurrent_discount_share": concurrent_discount / total,
        "acting_discount_share": acting_discount / total,
        "faction_share": {
            fac: weight / total for fac, weight in sorted(faction_weights.items())
        },
        "holders_detail": detail,
        "concurrent_holders": concurrent_holders,
        "notes": [],
    }


def distribution_of(state: Any, org_name: str) -> Dict[str, Any]:
    """单机构派系分布（只读）；未知/废置机构返回 `defined=False`。"""
    orgs = getattr(state, "central_orgs", None) or {}
    org = orgs.get(org_name) if isinstance(orgs, dict) else None
    if not isinstance(org, dict):
        return _empty_org(defined=False, error="unknown_org", notes=["org_not_found"])
    if org.get("abolished"):
        return _empty_org(defined=False, error="abolished", notes=["org_abolished"])
    return _org_distribution(state, org)


def institution_distribution(state: Any) -> Dict[str, Any]:
    """全部中枢机构的派系分布（纯只读、确定性、无副作用）。

    返回：`{as_of_turn, weight_mode, acting_supported, excluded_orgs, orgs}`。
    """
    orgs = getattr(state, "central_orgs", None) or {}
    out_orgs: Dict[str, Any] = {}
    excluded: List[str] = []
    if isinstance(orgs, dict):
        for org_name in sorted(orgs):
            org = orgs.get(org_name)
            if not isinstance(org, dict):
                continue
            if org.get("abolished"):
                excluded.append(str(org_name))
                continue
            out_orgs[str(org_name)] = _org_distribution(state, org)
    return {
        "as_of_turn": int(getattr(state, "turn", 0) or 0),
        "weight_mode": "headcount",
        "acting_supported": False,
        "excluded_orgs": excluded,
        "orgs": out_orgs,
    }

