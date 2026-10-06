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