# -*- coding: utf-8 -*-
"""M36.7-B+ **大臣通用选人与档案事实**（只读；规则驱动，**无任何硬编码人名**）。

通用性要求（用户 2026-10-11 修正）：
- 人物**动态**进入候选集（按登记＋在任状态），不得在代码里写死名单；
- 人物差异由**档案数据**驱动（职责→domain／登记标签／派系），不为个人写专属分支；
- **属性缺失**逐字段识别 `unknown`（不等于 0／无／负面）；
- 议题变化共用**同一接口**；**人物总数与单次会签人数分离**（`max_n` 由议题决定）；
- 只读：不写任何状态、不授予权限、不触发审批或执行。

与既有设施的关系：
- `state.org_ministers(org)`（机构归属选人，**既有**）→ 本模块是**职责/domain 驱动**的补充；
- `state.minister_status(name)` 缺省返回 `active`（对不在册/未记录者亦然）⇒ **本模块不采用**该缺省，
  而以 `MINISTERS` 登记＋`in_office` 为准，缺则记入 `unknown`。
"""
from typing import Any, Dict, Iterable, List, Tuple

from content.ministers.data import MINISTERS
from content.ministers.registry import (DOMAIN_ENUM, domains_of_role,
                                        is_central_role, is_registered_trait)

__all__ = ["minister_registry_facts", "select_participants", "council_participants"]


def _unknown_fields(fig: Dict[str, Any]) -> List[str]:
    """逐字段识别未知（缺失即 `unknown`，**不得**按 0/无/负面处理）。"""
    miss: List[str] = []
    if not str(fig.get("role") or "").strip():
        miss.append("role")
    if not str(fig.get("faction") or "").strip() or str(fig.get("faction")) == "无":
        miss.append("faction")
    if not (fig.get("trait_ids") or []):
        miss.append("trait_ids")
    if not str(fig.get("nobility") or "").strip():
        miss.append("nobility")
    if fig.get("in_office") is None:
        miss.append("in_office")
    return miss


def minister_registry_facts(state=None) -> Dict[str, Dict[str, Any]]:
    """**全量**档案事实（只读）：动态读 `MINISTERS`，不预置名单，无人数上限。

    每项：`{role, faction, rank, trait_ids(已登记者), traits_unregistered, nobility,
    in_office, domains, domains_note, unknown_fields}`。
    **不含** `loyalty`/`corruption` 数值（§17 数值不外泄）。
    """
    out: Dict[str, Dict[str, Any]] = {}
    for name, fig in (MINISTERS or {}).items():
        if not isinstance(fig, dict):
            continue
        domains, note = domains_of_role(fig.get("role"))
        tids = list(fig.get("trait_ids") or [])
        out[str(name)] = {
            "role": str(fig.get("role") or ""),
            "faction": str(fig.get("faction") or ""),
            "rank": str(fig.get("rank") or ""),
            "trait_ids": [t for t in tids if is_registered_trait(t)],
            "traits_unregistered": [t for t in tids if not is_registered_trait(t)],
            "nobility": str(fig.get("nobility") or ""),
            "in_office": fig.get("in_office"),
            "domains": list(domains),
            "domains_note": note,
            "unknown_fields": _unknown_fields(fig),
        }
    return out


def select_participants(state, issue_domains: Iterable[str] = (), *, max_n: int = 3,
                        require_in_office: bool = True,
                        include_central_fallback: bool = True) -> Dict[str, Any]:
    """按**规则**为某议题选参与大臣（只读；**不得**硬编码人名）。

    资格（Q 要求）：① `MINISTERS` 在册；② `in_office is True`（`require_in_office` 时）；
    ③ 不在册/缺 `in_office` ⇒ 记入 `unknown`（**不**当 False，也**不**当 True）。

    选取顺序（可解释）：
    1. `domains ∩ issue_domains ≠ ∅` ⇒ `selected_by="domain"`（同域内按登记名序，确定性）；
    2. 若不足 `max_n` 且 `include_central_fallback` ⇒ 以**中枢关键词**判定的重臣补足，
       标 `selected_by="central"`（**规则化**补足，非指定某人）；
    3. 仍不足 ⇒ **就是不足**（返回实际人数，**不**凑数、**不**编造）。

    返回 `{participants, excluded, unknown, issue_domains, max_n, rule}`；`participants` 每项
    `{name, role, faction, trait_ids, domains, selected_by}`。
    """
    want = [d for d in (issue_domains or []) if d in DOMAIN_ENUM]
    bad = [d for d in (issue_domains or []) if d not in DOMAIN_ENUM]
    facts = minister_registry_facts(state)
    participants: List[Dict[str, Any]] = []
    excluded: List[Dict[str, str]] = []
    unknown: List[Dict[str, str]] = []

    def _take(name: str, f: Dict[str, Any], by: str) -> None:
        participants.append({"name": name, "role": f["role"], "faction": f["faction"],
                             "trait_ids": f["trait_ids"], "domains": f["domains"],
                             "selected_by": by})

    for name, f in facts.items():
        if f.get("in_office") is None:
            unknown.append({"name": name, "reason": "in_office 未记录 ⇒ unknown"})
            continue
        if require_in_office and f.get("in_office") is not True:
            excluded.append({"name": name, "reason": "不在朝（in_office=False）"})
            continue
        if want and set(f["domains"]) & set(want):
            _take(name, f, "domain")
        elif not want:
            # 未给议题域：不猜，全部记入 excluded（由调用方明确议题域）
            excluded.append({"name": name, "reason": "issue_domains 为空 ⇒ 不参与（不猜职责）"})
    if len(participants) < int(max_n) and include_central_fallback:
        picked = {p["name"] for p in participants}
        for name, f in facts.items():
            if len(participants) >= int(max_n):
                break
            if name in picked or f.get("in_office") is not True:
                continue
            if is_central_role(f["role"]):
                _take(name, f, "central")
    return {"participants": participants[: int(max_n)],
            "excluded": excluded, "unknown": unknown,
            "issue_domains": want, "invalid_domains": bad, "max_n": int(max_n),
            "rule": ("domains 命中优先 → 不足则中枢重臣补足（规则化）→ 仍不足即不足（不凑数）；"
                     "在册＋in_office=True 方可入选；缺 in_office 记 unknown"),
            "fields_exposed": ("name/role/faction/trait_ids(已登记)/domains/selected_by"
                               "（不含 loyalty/corruption 数值）")}


def council_participants(state, org_key: str = "", issue_domains: Iterable[str] = (), *,
                         max_n: int = 0) -> Dict[str, Any]:
    """**廷议参与者**（M36.7-C 最小适配：**只限员**；只读；不改流程、不新建机制）。

    规则（可解释、确定性）：
    1. **优先复用既有** `state.org_ministers(org_key)`（机构驱动；已按 `loyalty` 在册者过滤）；
    2. 不足 `max_n` ⇒ 用 `select_participants(..., issue_domains)` **规则化补足**（去重）；
    3. **一律截断到 `max_n`**（限员生效）；缺员即缺员，**不凑数**。

    返回 `{org_key, participants, capped, shortfall, source, max_n, note}`；
    `source` 记每人的来源（`org`＝机构在任／`domain`＝职责域补足／`central`＝中枢补足）。
    """
    from content.data import COUNCIL_MAX_PARTICIPANTS
    limit = int(max_n or COUNCIL_MAX_PARTICIPANTS or 3)
    picked: List[Dict[str, Any]] = []
    names: List[str] = []
    org_names: List[str] = []
    if org_key:
        try:
            org_names = [str(n) for n in (state.org_ministers(org_key) or [])]
        except Exception:                  # noqa: BLE001 — 机构读数不可用不影响补足
            org_names = []
    for n in org_names:
        if n not in names:
            names.append(n)
    for n in names[:limit]:
        f = minister_registry_facts(state).get(n)
        picked.append({"name": n, "selected_by": "org",
                       "role": (f or {}).get("role", ""), "faction": (f or {}).get("faction", ""),
                       "domains": (f or {}).get("domains", [])})
    capped = len(names) > limit
    shortfall = max(0, limit - len(picked))
    if shortfall:
        add = select_participants(state, issue_domains, max_n=shortfall,
                                  require_in_office=True)
        for p in add["participants"]:
            if p["name"] in {x["name"] for x in picked}:
                continue
            picked.append(p)
            if len(picked) >= limit:
                break
    return {"org_key": str(org_key or ""),
            "participants": picked[:limit],
            "capped": capped or len(picked) >= limit,
            "shortfall": max(0, limit - len(picked)),
            "source": {p["name"]: p.get("selected_by", "") for p in picked[:limit]},
            "max_n": limit,
            "note": ("优先机构在任者 → 不足则按职责域规则化补足 → 一律截断到 max_n；"
                     "缺员不凑数；不含私德数值")}
