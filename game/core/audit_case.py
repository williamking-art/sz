# -*- coding: utf-8 -*-
"""勾校案卷（P3 发现系统；V1.3 终稿 §7）。

- `audit_fidelity(state, route, executor, secret)`：**保真度三档**读数（C3 参数，小权重起步）；
  输入＝执行者 `corruption` × 目标路 `clerks_detail[路]["grip"]` × `spy_network` × 是否密查。
- `resolve_audit(...)`：勾校某路钱粮 → 产出**案卷**写入 `state.audit_cases`
  （`case_id ＋ evidence ＋ judgement`；Q11 抄没前置之"证据"）。
- `discovery_readout(state)`：**四级发现阶梯**（异常→怀疑→证据→真相；一/二级复用既有读数）。

纪律：只读输入、不伪造；缺失读数按**中值**处理并在 `inputs` 里显式标注（缺失 ≠ 0/1）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from content.data import (FIN_AUDIT_BACKFIRE_LINE, FIN_AUDIT_BASE,
                          FIN_AUDIT_EVIDENCE_LINE, FIN_AUDIT_GRIP_W,
                          FIN_AUDIT_INTEGRITY_W, FIN_AUDIT_SECRET_BONUS,
                          FIN_AUDIT_SPY_W, GRIP_BASE, clamp as _clamp)

__all__ = ["audit_fidelity", "resolve_audit", "discovery_readout",
           "case_is_evidenced"]


def _executor_corruption(state, executor: Optional[str]) -> Optional[float]:
    """执行者贪腐度（0-1）；查不到 → `None`（**不回落 0/1**）。"""
    if not executor:
        return None
    corr = getattr(state, "corruption", None) or {}
    v = corr.get(executor)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    try:
        from content.ministers import MINISTERS
        m = MINISTERS.get(executor) or {}
        v = m.get("corruption")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    except Exception:  # noqa: BLE001 — 名册不可用不阻断勾校
        pass
    return None


def _route_grip(state, route: str) -> Optional[float]:
    """目标路吏胥把持度（0-1）；`clerks_detail` 未建 → `None`。"""
    p = (getattr(state, "prefectures", None) or {}).get(route) or {}
    d = p.get("clerks_detail") or {}
    v = d.get("grip")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _spy_coverage(state, executor: Optional[str]) -> Optional[float]:
    """谍报覆盖（0-1）：优先执行者所属派系，否则取最高覆盖；`spy_network` 缺失 → `None`。"""
    sn = getattr(state, "spy_network", None) or {}
    vals = [float(v) for v in sn.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not vals:
        return None
    if executor:
        try:
            from content.ministers import MINISTERS
            fac = (MINISTERS.get(executor) or {}).get("faction")
            if fac and isinstance(sn.get(fac), (int, float)):
                return float(sn[fac])
        except Exception:  # noqa: BLE001
            pass
    return max(vals)


def audit_fidelity(state, route: str, executor: Optional[str] = None,
                   secret: bool = False) -> Dict[str, Any]:
    """保真度三档：返回 `{fidelity, outcome, inputs}`（C3 参数，小权重起步）。

    - `outcome ∈ {"查得实情", "查无实据", "反噬"}`；
    - 缺失读数按中值处理（`inputs` 内保留 `None`，供面板如实显示"读数缺失"）。
    """
    corr = _executor_corruption(state, executor)
    grip = _route_grip(state, route)
    spy = _spy_coverage(state, executor)
    corr_v = 0.5 if corr is None else corr
    grip_v = GRIP_BASE if grip is None else grip
    spy_v = 0.0 if spy is None else spy
    fid = (FIN_AUDIT_BASE
           + (1.0 - corr_v) * FIN_AUDIT_INTEGRITY_W
           - grip_v * FIN_AUDIT_GRIP_W
           + spy_v * FIN_AUDIT_SPY_W
           + (FIN_AUDIT_SECRET_BONUS if secret else 0.0))
    fid = float(_clamp(fid, 0.0, 1.0))
    if fid < FIN_AUDIT_BACKFIRE_LINE:
        outcome = "反噬"
    elif fid < FIN_AUDIT_EVIDENCE_LINE:
        outcome = "查无实据"
    else:
        outcome = "查得实情"
    return {"fidelity": round(fid, 4), "outcome": outcome,
            "inputs": {"executor_corruption": corr, "route_grip": grip,
                       "spy_coverage": spy, "secret": bool(secret)}}


def resolve_audit(state, route: str, executor: Optional[str] = None,
                  secret: bool = False, log: Optional[list] = None) -> Dict[str, Any]:
    """勾校某路钱粮 → 案卷（写入 `state.audit_cases`；Q11 抄没前置）。

    - "查得实情" → `status="证据在握"`、`evidence` 记该路把持度与账目异常（档位）；
    - "查无实据" → 假阴性（做账的胜利）；"反噬" → 查官被倒打一耙（皇威 −1）。
    """
    prefs = getattr(state, "prefectures", None) or {}
    if route not in prefs:
        return {"ok": False, "reason": f"路名不存在：{route}"}
    fin = audit_fidelity(state, route, executor=executor, secret=secret)
    turn = int(getattr(state, "turn", 0) or 0)
    cases = getattr(state, "audit_cases", None)
    if not isinstance(cases, dict):
        cases = {}
        state.audit_cases = cases
    cid = f"ac{turn}-{len(cases) + 1}"
    outcome = fin["outcome"]
    rec: Dict[str, Any] = {
        "id": cid, "route": route, "outcome": outcome,
        "fidelity": fin["fidelity"], "executor": executor or "",
        "secret": bool(secret), "created_turn": turn,
        "status": {"查得实情": "证据在握", "查无实据": "查无实据",
                   "反噬": "反噬"}[outcome],
        "evidence": None, "judgement": None,
    }
    if outcome == "查得实情":
        _grip = _route_grip(state, route)
        rec["evidence"] = {
            "kind": "账目异常",
            "grip": round(float(_grip if _grip is not None else GRIP_BASE), 3),
            "note": "簿籍不符、火耗过额（档位）",
        }
    cases[cid] = rec
    if outcome == "反噬":
        try:
            state.change_prestige(-1, "勾校反噬")
        except Exception:  # noqa: BLE001 — 皇威通道异常不阻断勾校
            pass
    if log is not None:
        log.append(f"[勾校] {route}：{outcome}（保真度 {fin['fidelity']:.2f}"
                   f"{'，密查' if secret else ''}）")
    return {"ok": True, "case": rec, "fidelity": fin}


def case_is_evidenced(state, case_id: str) -> bool:
    """该案是否"证据在握"（Q11 抄没前置判据；P4 消费）。"""
    c = (getattr(state, "audit_cases", None) or {}).get(case_id)
    return bool(isinstance(c, dict) and c.get("status") == "证据在握")


def discovery_readout(state) -> Dict[str, Any]:
    """四级发现阶梯（只读）：异常→怀疑→证据→真相。

    - 一级「异常」：账面耗损（P2 读数）＋ 民心低迷；
    - 二级「怀疑」：AI 大臣奏报（由 ai 层经 `state.discovery_suspicions` 注入；程序侧只读）；
    - 三级「证据」：案卷 `status=="证据在握"`；
    - 四级「真相」：案卷已定案（`judgement` 非空；P3/P4 深化）。
    """
    anomalies = []
    try:
        loss = state.tax_loss_readout()
    except Exception:  # noqa: BLE001 — 读数不可用不阻断
        loss = {"status": "正常", "total": 0}
    if loss.get("status") in ("耗损偏重", "耗损异常"):
        anomalies.append({"kind": "财政",
                          "text": f"账面耗损{loss['status']}（累计 {int(loss.get('total', 0)):,} 贯）"})
    try:
        _sat_v = getattr(state, "population_satisfaction", None)
        sat = 100.0 if _sat_v is None else float(_sat_v)
    except (TypeError, ValueError):
        sat = 100.0
    if sat < 40:
        anomalies.append({"kind": "民生", "text": "民心低迷，民困增加"})
    suspicions = [dict(s) for s in (getattr(state, "discovery_suspicions", None) or [])
                  if isinstance(s, dict)]
    cases = getattr(state, "audit_cases", None) or {}
    evidence = [dict(c) for c in cases.values()
                if isinstance(c, dict) and c.get("status") == "证据在握"]
    truths = [dict(c) for c in cases.values()
              if isinstance(c, dict) and c.get("judgement")]
    level = 4 if truths else (3 if evidence else (2 if suspicions else (1 if anomalies else 0)))
    return {"level": level, "anomalies": anomalies, "suspicions": suspicions,
            "evidence": evidence, "truths": truths}
