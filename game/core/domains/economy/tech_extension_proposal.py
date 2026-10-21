# -*- coding: utf-8 -*-
"""AI 科技维度/蓝图扩展提案的**只读校验骨架**（I 首批，Jev A 0.967）。

定位：C0 契约冻结前的纯函数校验器 —— **不注册、不写 state、不碰科技表/存档/结算**。
只回答「这份提案结构是否可被后续审批/注册接受」，不回答「是否该批准」。
缺失语义：缺字段报 error/warning，**不补默认 0/空效果**。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

__all__ = ["validate_tech_extension_proposal", "ALLOWED_TOP", "KNOWN_NODE_KEYS"]

ALLOWED_TOP = ("proposal_id", "source", "technology_extension", "blueprint_proposals",
               "unresolved", "status")
KNOWN_NODE_KEYS = ("id", "name", "prerequisites", "research", "effect_refs", "description")


def validate_tech_extension_proposal(proposal: Any,
                                     existing_ids: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """校验科技扩展提案（**纯只读**）。

    返回 `{ok, errors, warnings, dimension_id, node_ids}`；`ok=False` 时调用方必须拒绝，
    不得"剔除坏项后缩小提案"悄悄通过。`existing_ids` = 已发布的科技/维度 id（撞 id ⇒ error）。
    检查项：顶层结构、维度 id/name、节点 id/name 唯一、前置引用存在、依赖无环、
    研究字段类型/非负、蓝图提案 kind/version 齐全、未知字段 warning。
    """
    errors: List[str] = []
    warnings: List[str] = []
    existing: Set[str] = {str(x) for x in (existing_ids or ())}

    if not isinstance(proposal, dict):
        return {"ok": False, "errors": ["proposal 必须是 dict"],
                "warnings": [], "dimension_id": None, "node_ids": []}

    for k in proposal:
        if k not in ALLOWED_TOP:
            warnings.append(f"未知顶层字段：{k}（不自动采纳）")

    te = proposal.get("technology_extension")
    if not isinstance(te, dict):
        errors.append("technology_extension 缺失或非 dict")
        te = {}
    dim = te.get("dimension")
    dimension_id = None
    if not isinstance(dim, dict):
        errors.append("technology_extension.dimension 缺失或非 dict")
    else:
        dimension_id = dim.get("id")
        if not isinstance(dimension_id, str) or not dimension_id.strip():
            errors.append("dimension.id 缺失/非字符串")
        elif dimension_id in existing:
            errors.append(f"dimension.id 与已发布 id 冲突：{dimension_id}")
        if not isinstance(dim.get("name"), str) or not str(dim.get("name") or "").strip():
            errors.append("dimension.name 缺失/空")

    nodes = te.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("technology_extension.nodes 必须是非空 list")
        nodes = []

    node_ids: List[str] = []
    prereq: Dict[str, List[str]] = {}
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errors.append(f"nodes[{i}] 非 dict")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid.strip():
            errors.append(f"nodes[{i}].id 缺失/非字符串")
            continue
        if nid in node_ids:
            errors.append(f"节点 id 重复：{nid}")
        if nid in existing:
            errors.append(f"节点 id 与已发布 id 冲突：{nid}")
        node_ids.append(nid)
        if not isinstance(n.get("name"), str) or not str(n.get("name") or "").strip():
            errors.append(f"节点 {nid} name 缺失/空")
        for k in n:
            if k not in KNOWN_NODE_KEYS:
                warnings.append(f"节点 {nid} 未知字段：{k}")
        p = n.get("prerequisites", [])
        if not isinstance(p, list) or any(not isinstance(x, str) for x in p):
            errors.append(f"节点 {nid} prerequisites 必须是字符串 list")
            p = []
        prereq[nid] = list(p)
        research = n.get("research")
        if research is not None:
            if not isinstance(research, dict):
                errors.append(f"节点 {nid} research 必须是 dict")
            else:
                for rk in ("cost", "duration_months"):
                    if rk in research:
                        v = research[rk]
                        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                            errors.append(f"节点 {nid} research.{rk} 必须是非负数")
        eff = n.get("effect_refs")
        if eff is not None and (not isinstance(eff, list)
                                or any(not isinstance(x, str) for x in eff)):
            errors.append(f"节点 {nid} effect_refs 必须是字符串 list")

    # 前置引用：已发布或同一提案
    known: Set[str] = set(node_ids) | existing
    for nid, ps in prereq.items():
        for p in ps:
            if p not in known:
                errors.append(f"节点 {nid} 前置引用不存在：{p}")

    # 环检测（同一提案内）
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in node_ids}

    def _dfs(u: str, stack: List[str]) -> None:
        color[u] = GREY
        for v in prereq.get(u, []):
            if v not in color:
                continue
            if color[v] == GREY:
                errors.append("前置依赖成环：" + " -> ".join(stack + [u, v]))
                return
            if color[v] == WHITE:
                _dfs(v, stack + [u])
        color[u] = BLACK

    for n in node_ids:
        if color.get(n) == WHITE:
            _dfs(n, [])

    bps = proposal.get("blueprint_proposals", [])
    if bps is not None and not isinstance(bps, list):
        errors.append("blueprint_proposals 必须是 list")
    for i, b in enumerate(bps or []):
        if not isinstance(b, dict):
            errors.append(f"blueprint_proposals[{i}] 非 dict")
            continue
        kind = b.get("kind")
        if kind not in ("new", "upgrade"):
            errors.append(f"blueprint_proposals[{i}].kind 必须为 new/upgrade")
        if not isinstance(b.get("blueprint_id"), str) or not b.get("blueprint_id"):
            errors.append(f"blueprint_proposals[{i}].blueprint_id 缺失")
        if kind == "new":
            if not isinstance(b.get("definition"), dict) or not b.get("definition"):
                errors.append(f"blueprint_proposals[{i}] new 缺 definition")
        elif kind == "upgrade":
            from_v, to_v = b.get("from_version"), b.get("to_version")
            if not isinstance(from_v, int) or isinstance(from_v, bool) or from_v < 1:
                errors.append(f"blueprint_proposals[{i}] upgrade.from_version 必须正整数")
            if not isinstance(to_v, int) or isinstance(to_v, bool) or to_v <= (from_v or 0):
                errors.append(f"blueprint_proposals[{i}] upgrade.to_version 必须大于 from_version")

    return {"ok": not errors, "errors": errors,
            "warnings": warnings, "dimension_id": dimension_id,
            "node_ids": node_ids, "read_only": True}
