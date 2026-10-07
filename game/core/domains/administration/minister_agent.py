# -*- coding: utf-8 -*-
"""B5 · 官员个体 Agent 状态机（**不新建人物表**，规格 `market-civilian-economy` B5）

对应《建议》§3.3「官员 Agent 的身份模型」七项最小状态，以及 §7.1
「**人是主体，领域契约是能力**」的角色分层。

## 分层纪律（勿混）

| 层 | 职责 | 本模块 |
|---|---|---|
| **官员个体 Agent** | 行动主体：领旨/奏覆/支持/反对/承办/拖延 | ✅ 状态机与意图记录 |
| **领域分析能力** | 专业输入（税源/市场/军务分析） | ❌ 无官职、无派系利益、**无决定权** |
| **程序执行器** | 校验权限/预算/材料并落账 | ❌ 不在本模块 |

## 为什么复用而非重建

`GameState` 已有 `minister_memory` / `minister_status()` / `player_minister_status` /
`org_ministers`，`content.ministers.data.MINISTERS` 有 **43** 名具名人物。
本模块**只在 `state` 上挂 Agent 运行态**（身份/权限/记忆/意图），
**不另造人物表**（《建议》§3.3 范围声明的明确要求）。

## 纪律

- **逐人隔离**：记忆、意图、权限**按 `actor_id` 分开**，不合并为"朝廷综合意见"；
- **缺失 ≠ 0**：无记忆返回 `None`／空列表，**不臆造"忠诚支持"**；
- **权限只读**：权限由官职派生，模块内**不写**官职；
- **拒绝式**：非法 `actor_id` 明确报错，不静默新建"无名官员"。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = [
    "ACTOR_SCHEMA_VERSION", "MINISTER_STATUS_IN_OFFICE", "MINISTER_STATUS_OUT",
    "actor_ids_of", "ensure_actor", "actor_view", "remember",
    "recall", "record_intent", "intents_of", "can_act",
]

#: 官员 Agent 运行态结构版本
ACTOR_SCHEMA_VERSION = 1

#: 在朝 / 在野（《建议》§3.3「存活/在野/在朝」）
MINISTER_STATUS_IN_OFFICE = "in_office"
MINISTER_STATUS_OUT = "out_of_office"

#: §3.3 七项最小状态的字段名（缺一即为不合规 Actor）
ACTOR_MIN_FIELDS = (
    "actor_id", "status", "posts", "authority",
    "memory", "intents", "known_info",
)


def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


def _actor_store(state) -> Dict[str, Any]:
    """取（必要时初始化）官员 Agent 运行态容器。"""
    store = getattr(state, "minister_agents", None)
    if not isinstance(store, dict):
        store = {}
        state.minister_agents = store
    return store


def actor_ids_of(state) -> List[str]:
    """本局已建立 Agent 的官员 id 列表（**只列已建的**，不臆造全集）。"""
    return sorted(_actor_store(state).keys())


def ensure_actor(state, actor_id: str, *, posts: Optional[List[str]] = None,
                 authority: Optional[float] = None) -> Dict[str, Any]:
    """确保某官员有 Agent 运行态；**已存在则原样返回**（不覆盖记忆）。

    `authority`：官职权限（0~1），缺省 `None`（**未定义**，不是 0＝无权）。
    """
    aid = str(actor_id or "").strip()
    if not aid:
        raise ValueError("actor_id 不能为空（拒绝式：不新建无名官员）")
    store = _actor_store(state)
    actor = store.get(aid)
    if isinstance(actor, dict):
        return actor
    actor = {
        "schema_version": ACTOR_SCHEMA_VERSION,
        "actor_id": aid,
        "status": MINISTER_STATUS_IN_OFFICE,
        "posts": list(posts or []),
        "authority": authority,          # None = 未定义（非 0）
        "memory": [],                    # 本人只见自己的记忆
        "intents": [],
        "known_info": {},                # 信息可见边界（key:来源）
    }
    store[aid] = actor
    return actor


def actor_view(state, actor_id: str) -> Optional[Dict[str, Any]]:
    """官员的**只读**视图；未建立 → `None`（缺失≠0，不返回空壳冒充存在）。"""
    actor = _actor_store(state).get(str(actor_id or "").strip())
    if not isinstance(actor, dict):
        return None
    return {
        "actor_id": actor.get("actor_id"),
        "status": actor.get("status"),
        "posts": list(actor.get("posts") or []),
        "authority": actor.get("authority"),
        "memory_count": len(actor.get("memory") or []),
        "intent_count": len(actor.get("intents") or []),
        "has_undefined_authority": actor.get("authority") is None,
    }


def can_act(state, actor_id: str) -> Dict[str, Any]:
    """能否承办：须在朝 ＋ 权限已定义且 > 0。

    权限**未定义**（`None`）→ `ok=False` 且 `reason="authority_undefined"`
    （**不按"无权"或"有权"擅自判定**）。
    """
    actor = _actor_store(state).get(str(actor_id or "").strip())
    if not isinstance(actor, dict):
        return {"ok": False, "reason": "unknown_actor", "actor_id": actor_id}
    if actor.get("status") != MINISTER_STATUS_IN_OFFICE:
        return {"ok": False, "reason": "not_in_office", "actor_id": actor_id}
    auth = _num(actor.get("authority"))
    if auth is None:
        return {"ok": False, "reason": "authority_undefined", "actor_id": actor_id}
    if auth <= 0:
        return {"ok": False, "reason": "no_authority", "actor_id": actor_id}
    return {"ok": True, "reason": "ok", "actor_id": actor_id,
            "authority": auth}


def remember(state, actor_id: str, *, kind: str, text: str,
             turn: Optional[int] = None, source: Optional[str] = None) -> Dict[str, Any]:
    """写入**本人**记忆（《建议》§7.6：甲的私下谈话不是乙亲闻）。

    `source` 标注信息来自何处（供信息边界判定）；缺省 `None` = 本人亲历。
    """
    actor = ensure_actor(state, actor_id)
    entry = {
        "kind": str(kind or "note"),
        "text": str(text or ""),
        "turn": int(turn if turn is not None else (getattr(state, "turn", 0) or 0)),
        "source": source,
        "private": source is None,       # 本人亲历 ＝ 私密记忆
    }
    mem = actor.setdefault("memory", [])
    mem.append(entry)
    return entry


def recall(state, actor_id: str, *, kind: Optional[str] = None,
           include_private: bool = True) -> List[Dict[str, Any]]:
    """读取**本人**记忆；`kind` 可过滤。`include_private=False` 时排除非亲历条目
    （用于"向他人转述前先剔除私话"的场景）。"""
    actor = _actor_store(state).get(str(actor_id or "").strip())
    if not isinstance(actor, dict):
        return []
    out = []
    for e in (actor.get("memory") or []):
        if not isinstance(e, dict):
            continue
        if kind and e.get("kind") != kind:
            continue
        # include_private=False ⇒只要**可转述**的条目（有来源的公开信息），
        # 排除"本人亲历的私话"——语义不可写反，否则会把公开记忆清空。
        if not include_private and e.get("private", False):
            continue
        out.append(e)
    return out


def record_intent(state, actor_id: str, *, intent: str,
                  action: str = "上疏",
                  targets: Optional[List[str]] = None,
                  expected: Optional[str] = None,
                  risk: Optional[str] = None) -> Dict[str, Any]:
    """记录该官员本回合**自己的**意图（《建议》§7.2 逐人意图）。

    领域 Agent 的分析**不能**写进这里——本函数只接受具名 `actor_id`，
    保证"每项政策意图可归因到具体主事官员"。
    """
    actor = ensure_actor(state, actor_id)
    entry = {
        "turn": int(getattr(state, "turn", 0) or 0),
        "actor_id": actor.get("actor_id"),
        "action": str(action or "上疏"),
        "intent": str(intent or ""),
        "targets": list(targets or []),
        "expected": expected,
        "risk": risk,
        "status": "proposed",       # proposed → 批准/驳回；**不由叙事宣称**
    }
    intents = actor.setdefault("intents", [])
    intents.append(entry)
    return entry


def intents_of(state, actor_id: str, *, turn: Optional[int] = None) -> List[Dict[str, Any]]:
    """某官员的意图列表（可按回合过滤）。未建立 → `[]`（不是"没有异议"）。"""
    actor = _actor_store(state).get(str(actor_id or "").strip())
    if not isinstance(actor, dict):
        return []
    out = []
    for e in (actor.get("intents") or []):
        if not isinstance(e, dict):
            continue
        if turn is not None and int(e.get("turn", -1)) != int(turn):
            continue
        out.append(e)
    return out