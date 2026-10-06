"""主要国家/外邦政权的**科技推进**（批 B）。

用户裁定（2026-10-06）：
- 「主要国家**跟宋一样机制**」⇒ 同一套 `TECH_NODES` 推进规则；
- 「科技树挂钩的建筑是一样的」⇒ 解锁结果供批 C 部署；
- 科技花费走**政权库银**（**由税收供血**），**不扣宋的国库、不扣任何 POP 账户**。

🔴 **口径**：
- 研究**按月摊销**成本（`银 / months`），逐月从政权 `treasury` 实扣；
- 库银不足 ⇒ **暂停研究**（记 `research_paused`），**不透支、不挂账、不回落 0 假装**；
- 本模块**只推进科技进度**，**不施加经济效果**（效果属批 C，避免一次动平衡）。
"""
from typing import Any, Dict, List, Optional, Tuple

from content.data import TECH_NODES


def _tech_nodes_index() -> Dict[str, dict]:
    """`TECH_NODES` 元组 → `{id: {...}}` 读口（构建一次，模块级缓存）。"""
    global _TECH_IDX
    if _TECH_IDX is None:
        out = {}
        for nd in (TECH_NODES or ()):
            try:
                nid = str(nd[0])
                out[nid] = {
                    "id": nid, "line": nd[1], "tier": nd[2], "name": nd[3],
                    "desc": nd[4], "requires": list(nd[5] or []),
                    "cost": dict(nd[8] or {}), "effects": dict(nd[9] or {}),
                }
            except (IndexError, TypeError, ValueError):
                continue
        _TECH_IDX = out
    return _TECH_IDX


_TECH_IDX: Optional[Dict[str, dict]] = None


def _starter_node_ids() -> List[str]:
    """免费起点节点 id（tier-0 且银与时长皆 0），开局即解锁，与宋侧一致。"""
    return sorted(n["id"] for n in _tech_nodes_index().values()
                  if int(n.get("tier", 1) or 0) == 0 and is_starter(n))


def is_starter(nd: dict) -> bool:
    """是否为 **tier-0 免费起点**（银与时长皆 0）—— 宋侧开局即有。

    实测 47 节点中有 **7 个**（M0_plow / M1_noria / E0_firewood / E1_coal /
    C0_alchemy / I0_block / H0_herbal）。
    """
    c = nd.get("cost") or {}
    return int(c.get("银", 0) or 0) <= 0 and int(c.get("months", 0) or 0) <= 0


def next_researchable(tech: dict) -> Optional[str]:
    """下一个**可研究**节点：前置**全部已解锁**、**非免费起点**、层级最低优先。

    🔴 无可研究节点 ⇒ 返回 `None`（不是 `""`）。
    🔴 免费起点**不入队列**（否则会「同月解锁且扣款 0」= 白嫖）。
    """
    idx = _tech_nodes_index()
    unlocked = set(tech.get("unlocked") or [])
    cands = [n for n in idx.values()
             if n["id"] not in unlocked
             and not is_starter(n)
             and all(r in unlocked for r in n["requires"])]
    if not cands:
        return None
    cands.sort(key=lambda n: (n["tier"], n["id"]))
    return cands[0]["id"]


def advance_regime_tech(ex: dict, *, months: int = 1) -> Dict[str, Any]:
    """推进某政权一个月的科技研究。返回 `{researching, spent, unlocked, paused}`。

    付款主体：**该政权自有 `ex["treasury"]`**（税收供血）。
    """
    tech = ex.get("tech")
    if not isinstance(tech, dict):
        return {"researching": None, "spent": 0, "unlocked": None, "paused": False}
    idx = _tech_nodes_index()
    out = {"researching": None, "spent": 0, "unlocked": None, "paused": False}

    cur = tech.get("researching")
    if not cur or cur not in idx:
        cur = next_researchable(tech)
        tech["researching"] = cur
        if not cur:
            return out
    nd = idx[cur]
    cost = nd.get("cost") or {}
    total_silver = int(cost.get("银", 0) or 0)
    total_months = max(1, int(cost.get("months", 1) or 1))
    per_month = total_silver / float(total_months)

    done = int(tech.get("progress_months", 0) or 0)
    if done >= total_months:
        tech.setdefault("unlocked", []).append(cur)
        tech["progress_months"] = 0
        tech["researching"] = next_researchable(tech)
        out["unlocked"] = cur
        return out

    treasury = int(ex.get("treasury", 0) or 0)
    if treasury < per_month:
        out["paused"] = True
        out["researching"] = cur
        return out
    treasury -= int(per_month)
    ex["treasury"] = treasury
    done += max(1, int(months))
    tech["progress_months"] = done
    out["spent"] = int(per_month)
    out["researching"] = cur
    if done >= total_months:
        if cur not in (tech.setdefault("unlocked", []) or []):
            tech["unlocked"].append(cur)
        tech["progress_months"] = 0
        tech["researching"] = next_researchable(tech)
        out["unlocked"] = cur
    return out


def deployable_nodes(tech: dict) -> List[str]:
    """已解锁且**可部署**的科技建筑节点 id（`TECH_NODE_DEPLOY` ∩ unlocked）。"""
    from content.data import TECH_NODE_DEPLOY
    unlocked = set(tech.get("unlocked") or [])
    return sorted(nid for nid in (TECH_NODE_DEPLOY or {}) if nid in unlocked)


def blueprint_of(node_id: str) -> Optional[dict]:
    """科技节点 → 建筑蓝图（`BUILDING_BLUEPRINTS`）。无蓝图 ⇒ `None`（不可判定）。"""
    from content.data import BUILDING_BLUEPRINTS, TECH_NODE_DEPLOY
    if node_id not in (TECH_NODE_DEPLOY or {}):
        return None
    bp = (BUILDING_BLUEPRINTS or {}).get(node_id)
    return dict(bp) if isinstance(bp, dict) else None


def deploy_cost(node_id: str) -> Optional[int]:
    """部署造价（贯）= 蓝图 `cost["银"]`。缺项 ⇒ `None`（不可判定，不按 0 假装）。"""
    bp = blueprint_of(node_id)
    if bp is None:
        return None
    c = bp.get("cost") or {}
    if "银" not in c:
        return None
    try:
        return int(c["银"])
    except (TypeError, ValueError):
        return None


def deploy_regime_building(ex: dict, node_id: str) -> Dict[str, Any]:
    """部署科技建筑。**付款主体 = 该政权自有 `ex["treasury"]`**（税收供血）。

    - 仅限**已解锁**且在 `TECH_NODE_DEPLOY` 中的节点；
    - 库银不足 ⇒ **不部署**（`ok=False, reason="insufficient"`），**不透支**；
    - 造价不可判定 ⇒ `reason="cost_unknown"`，**不按 0 假装免费**。
    """
    tech = ex.get("tech")
    out = {"ok": False, "reason": None, "node": node_id, "cost": 0, "name": None}
    if not isinstance(tech, dict):
        out["reason"] = "no_tech"
        return out
    if node_id not in deployable_nodes(tech):
        out["reason"] = "not_unlocked"
        return out
    if node_id in (tech.get("deployed") or []):
        out["reason"] = "already_deployed"
        return out
    cost = deploy_cost(node_id)
    if cost is None:
        out["reason"] = "cost_unknown"
        return out
    treasury = int(ex.get("treasury", 0) or 0)
    if treasury < cost:
        out["reason"] = "insufficient"
        return out
    ex["treasury"] = treasury - cost
    tech.setdefault("deployed", []).append(node_id)
    bp = blueprint_of(node_id) or {}
    out.update({"ok": True, "cost": cost, "name": bp.get("name") or node_id})
    return out


def monthly_maintenance(ex: dict) -> int:
    """已部署科技建筑的**月维护费**（贯）。

    ⚠️ 口径与宋侧一致：**按建筑造价的比例**（`TECH_NODE_MAINTENANCE`），
    而非按数量 —— 否则高级建筑维护费反而低于低级。
    """
    tech = ex.get("tech")
    if not isinstance(tech, dict):
        return 0
    from content.data import TECH_NODE_MAINTENANCE
    total = 0.0
    for nid in (tech.get("deployed") or []):
        rate = (TECH_NODE_MAINTENANCE or {}).get(nid)
        cost = deploy_cost(nid)
        if rate is None or cost is None:
            continue          # 缺项 ⇒ 该建筑不计维护（不回落 0 假装已算）
        total += float(cost) * float(rate)
    return int(total)


def charge_maintenance(ex: dict) -> Dict[str, Any]:
    """从政权库银扣月维护费；**不足则按现有库银扣到 0 并记欠额**（不凭空扣成负）。"""
    due = monthly_maintenance(ex)
    if due <= 0:
        return {"due": 0, "paid": 0, "unpaid": 0}
    treasury = int(ex.get("treasury", 0) or 0)
    paid = min(treasury, due)
    ex["treasury"] = treasury - paid
    return {"due": due, "paid": paid, "unpaid": due - paid}
