# -*- coding: utf-8 -*-
"""党禁最小状态机（2026-10-19，奏折前执行层）。

- 状态写在 `state.factions[faction]["ban"]`，不新增顶层 `state.*`；
- 只影响：官方承办官资格（事故处理跳过被禁者）、faction `_event_delta` 一次性冲击；
- 不直接写 satisfaction/cohesion/influence；由 `faction_settle` 唯一消费；
- 一次性冲击只一次；维护月不重复扣；到期 +5 只一次。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from content.ministers.data import MINISTERS

__all__ = [
    "BAN_LEVELS", "start_faction_ban", "lift_faction_ban",
    "settle_faction_bans", "is_faction_banned", "is_official_banned",
    "banned_factions", "actor_faction", "active_ban",
]

BAN_LEVELS = {
    "轻": {"duration": 6, "satisfaction": -8, "grievance": 5, "cohesion": 3},
    "中": {"duration": 12, "satisfaction": -15, "grievance": 12, "cohesion": 8},
    "重": {"duration": 18, "satisfaction": -25, "grievance": 25, "cohesion": 15},
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _event_once(state, event_id: str, payload: Dict[str, Any]) -> bool:
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        return False
    ledger = stats.setdefault("political_event_ledger", {})
    if event_id in ledger:
        return False
    ledger[event_id] = dict(payload)
    return True


def actor_faction(state, actor) -> Optional[str]:
    """人物/actor dict → 派系键。"""
    if isinstance(actor, dict):
        fac = str(actor.get("faction") or "").strip()
        if fac:
            return fac
        actor = actor.get("name")
    name = str(actor or "").strip()
    fig = MINISTERS.get(name) if isinstance(MINISTERS, dict) else None
    if isinstance(fig, dict):
        fac = str(fig.get("faction") or "").strip()
        if fac:
            return fac
    # 地方/路级官员不在 MINISTERS 名册：从真账 holder 读 faction。
    for po in (getattr(state, "prefect_officials", None) or {}).values():
        if not isinstance(po, dict):
            continue
        for key in ("prefect", "subprefect"):
            row = po.get(key)
            if isinstance(row, dict) and str(row.get("name") or "") == name:
                fac = str(row.get("faction") or "").strip()
                if fac:
                    return fac
    for c in (getattr(state, "circuit_officials", None) or {}).values():
        offs = c.get("officials") if isinstance(c, dict) else None
        if not isinstance(offs, dict):
            continue
        for row in offs.values():
            if isinstance(row, dict) and str(row.get("name") or "") == name:
                fac = str(row.get("faction") or "").strip()
                if fac:
                    return fac
    prof = (getattr(state, "official_stats", None) or {}).get(name)
    if isinstance(prof, dict):
        fac = str(prof.get("faction") or (prof.get("attrs") or {}).get("faction") or "").strip()
        if fac:
            return fac
    return None


def active_ban(state, faction: str) -> Optional[Dict[str, Any]]:
    """活跃党禁控制块；未禁/已到期返回 None。"""
    key = str(faction or "").strip()
    if not key:
        return None
    f = (getattr(state, "factions", None) or {}).get(key)
    if not isinstance(f, dict):
        return None
    ban = f.get("ban")
    if not isinstance(ban, dict) or ban.get("status") != "active":
        return None
    end = ban.get("end_turn")
    turn = int(getattr(state, "turn", 0) or 0)
    return ban if end is None or turn < int(end) else None


def is_faction_banned(state, faction: str) -> bool:
    return active_ban(state, faction) is not None


def is_official_banned(state, actor) -> bool:
    fac = actor_faction(state, actor)
    return bool(fac and is_faction_banned(state, fac))


def banned_factions(state) -> List[str]:
    facs = getattr(state, "factions", None) or {}
    return [k for k in facs if is_faction_banned(state, k)]


def start_faction_ban(state, faction: str, level: str = "轻",
                      *, decree_id: str = "", turn: Optional[int] = None) -> Dict[str, Any]:
    """开始党禁：写 ban 控制块 + 一次性 `_event_delta`；不直接改 satisfaction。"""
    key = str(faction or "").strip()
    f = (getattr(state, "factions", None) or {}).get(key)
    if not isinstance(f, dict):
        return {"ok": False, "reason": "unknown_faction"}
    lv = str(level or "轻")
    spec = BAN_LEVELS.get(lv)
    if not spec:
        return {"ok": False, "reason": "unknown_level"}
    now = int(getattr(state, "turn", 0) or 0) if turn is None else int(turn)
    end = now + int(spec["duration"])
    f["ban"] = {
        "level": lv, "status": "active", "start_turn": now, "end_turn": end,
        "decree_id": str(decree_id or ""),
        "grievance_target": int(spec["grievance"]),
        "cohesion_bonus": int(spec["cohesion"]),
        "event_ids": [],
    }
    # 一次性 shock：只写 _event_delta，由 faction_settle 统一消费；单次 clamp ±12。
    shock = _clamp(float(spec["satisfaction"]), -12.0, 12.0)
    f["_event_delta"] = _clamp(float(f.get("_event_delta", 0.0) or 0.0) + shock,
                              -12.0, 12.0)
    # 剩余的 satisfaction 用持续 target 偏移表达；重级 -25 = -12 事件 + -13 target。
    f["ban"]["satisfaction_target"] = float(spec["satisfaction"]) - shock
    eid = f"faction_ban:{key}:{now}"
    if _event_once(state, eid, {"kind": "faction_ban_start", "faction": key,
                                "level": lv, "turn": now}):
        f["ban"]["event_ids"].append(eid)
    return {"ok": True, "faction": key, "level": lv,
            "start_turn": now, "end_turn": end}


def _expire(state, key: str, f: Dict[str, Any], reason: str) -> None:
    ban = f.get("ban")
    if not isinstance(ban, dict):
        return
    ban["status"] = "expired"
    ban["end_turn"] = int(getattr(state, "turn", 0) or 0)
    # 到期/解除 +5，只一次；仍只写 _event_delta。
    if not ban.get("bonus_applied"):
        f["_event_delta"] = _clamp(float(f.get("_event_delta", 0.0) or 0.0) + 5.0,
                                  -12.0, 12.0)
        ban["bonus_applied"] = True
    eid = f"faction_ban:{key}:end:{int(getattr(state, 'turn', 0) or 0)}"
    if _event_once(state, eid, {"kind": "faction_ban_end", "faction": key,
                                "reason": reason,
                                "turn": int(getattr(state, "turn", 0) or 0)}):
        ban.setdefault("event_ids", []).append(eid)


def lift_faction_ban(state, faction: str, reason: str = "解除") -> Dict[str, Any]:
    key = str(faction or "").strip()
    f = (getattr(state, "factions", None) or {}).get(key)
    if not isinstance(f, dict) or not isinstance(f.get("ban"), dict):
        return {"ok": False, "reason": "no_ban"}
    _expire(state, key, f, reason)
    return {"ok": True, "faction": key, "status": "expired"}


def settle_faction_bans(state) -> Dict[str, Any]:
    """回合固定点：到期自动解除；维护月不再扣。"""
    turn = int(getattr(state, "turn", 0) or 0)
    ended = []
    for key, f in list((getattr(state, "factions", None) or {}).items()):
        if not isinstance(f, dict):
            continue
        ban = f.get("ban")
        if not isinstance(ban, dict) or ban.get("status") != "active":
            continue
        end = ban.get("end_turn")
        if end is not None and turn >= int(end):
            _expire(state, key, f, "到期")
            ended.append(key)
    return {"ended": ended}

