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
                          FIN_AUDIT_SPY_W, FIN_SUSPICION_CAP,
                          FIN_SUSPICION_WINDOW_TURNS, GRIP_BASE, clamp as _clamp)

__all__ = ["audit_fidelity", "resolve_audit", "discovery_readout",
           "case_is_evidenced", "confiscate_by_case",
           "scan_fiscal_suspicion", "record_suspicion", "FIN_SUSPICION_KEYWORDS"]

#: 财政疑虑关键词（**单点声明**；启发式、可审计——命中即视为大臣"犯嘀咕"。
#: 与 `longterm_task._TOPIC_BRIDGE`／`decree_effect.MILITARY_KEYWORDS` 同姿态：
#: 单一处声明、可复核；仅用于发现链二级的"怀疑"提示，不改任何数值。）
FIN_SUSPICION_KEYWORDS: tuple = (
    "火耗", "亏空", "侵渔", "侵盗", "中饱", "截留", "贪墨", "贪吏", "贪",
    "账目", "簿籍", "亏欠", "逋欠", "挪移", "私派", "加征", "横敛", "把持",
    "吏弊",
)


def scan_fiscal_suspicion(text) -> Optional[str]:
    """文本是否含财政疑虑（返回命中关键词；无 → `None`）。**只读**，不改状态。"""
    t = str(text or "")
    for _k in FIN_SUSPICION_KEYWORDS:
        if _k in t:
            return _k
    return None


def record_suspicion(state, text, *, source: str, minister: Optional[str] = None,
                     route: Optional[str] = None,
                     turn: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """**唯一写入点**：AI 大臣/密探的财政疑虑奏报 → `state.discovery_suspicions`（发现链二级）。

    - 文本经 `scan_fiscal_suspicion` 过滤（非财政疑虑不入，返回 `None`）；
    - 去重（同源＋同人＋同文）；容量上限 `FIN_SUSPICION_CAP`（超限丢最旧）；
    - 返回写入条目；被拒（空文/非疑虑/重复）→ `None`（不静默伪造、不静默丢弃）。
    """
    t = str(text or "").strip()
    if not t:
        return None
    _kw = scan_fiscal_suspicion(t)
    if not _kw:
        return None
    items = getattr(state, "discovery_suspicions", None)
    if not isinstance(items, list):
        items = []
        state.discovery_suspicions = items
    _key = (str(source or ""), str(minister or ""), t[:60])
    for _it in items:
        if not isinstance(_it, dict):
            continue
        if (str(_it.get("source", "")), str(_it.get("minister", "")),
                str(_it.get("text", ""))[:60]) == _key:
            return None                      # 去重（同源同人同文）
    _turn = getattr(state, "turn", 0)
    try:
        _turn = int(_turn)
    except (TypeError, ValueError):
        _turn = 0
    rec = {"source": str(source or ""), "minister": str(minister or ""),
           "route": route or "", "text": t[:120], "keyword": _kw,
           "turn": int(turn) if turn is not None else _turn}
    items.append(rec)
    if FIN_SUSPICION_CAP > 0 and len(items) > FIN_SUSPICION_CAP:
        del items[:len(items) - FIN_SUSPICION_CAP]
    return rec


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
    # 二级「怀疑」：AI 大臣奏报（`record_suspicion` 唯一写入点）；**仅计窗口内**（M34-③）
    _turn_now = getattr(state, "turn", 0)
    try:
        _turn_now = int(_turn_now)
    except (TypeError, ValueError):
        _turn_now = 0
    suspicions = []
    for _s in (getattr(state, "discovery_suspicions", None) or []):
        if not isinstance(_s, dict):
            continue
        _st = _s.get("turn")
        _st = int(_st) if isinstance(_st, (int, float)) and not isinstance(_st, bool) else _turn_now
        if _turn_now - _st <= FIN_SUSPICION_WINDOW_TURNS:
            suspicions.append(dict(_s))
    cases = getattr(state, "audit_cases", None) or {}
    evidence = [dict(c) for c in cases.values()
                if isinstance(c, dict) and c.get("status") == "证据在握"]
    truths = [dict(c) for c in cases.values()
              if isinstance(c, dict) and c.get("judgement")]
    level = 4 if truths else (3 if evidence else (2 if suspicions else (1 if anomalies else 0)))
    return {"level": level, "anomalies": anomalies, "suspicions": suspicions,
            "evidence": evidence, "truths": truths}


def confiscate_by_case(state, case_id: Optional[str] = None, route: Optional[str] = None,
                       imperial_exception: bool = False,
                       log: Optional[list] = None) -> Dict[str, Any]:
    """Q11 抄没前置：财政贪墨**须先成案**（case_id＋evidence＋judgement）；皇权事件可例外。

    成案（`status=="证据在握"`）→ 抄没该路官僚私囊 `FIN_CONFISCATE_RATE` 比例入国库
    （守恒：官僚 wealth → treasury，ΣM_ALL 不变），并落 `judgement`（案卷转"已定案"）。
    无案/未成案 → 拒绝（可诊断）；例外通道须显式 `imperial_exception=True`（谋反/政变类）。
    """
    from content.data import FIN_CONFISCATE_RATE
    from core.foundation.ledger.pop_bridge import pop_obj_set as _pop_obj_set
    cases = getattr(state, "audit_cases", None) or {}
    rec = cases.get(case_id) if case_id else None
    if not imperial_exception:
        if not isinstance(rec, dict):
            return {"ok": False, "reason": "无案可抄：财政贪墨须先勾校成案（Q11）"}
        if rec.get("status") != "证据在握":
            return {"ok": False, "reason": f"案未成：{rec.get('status')}（Q11 须证据在握）"}
    _route = route or (rec or {}).get("route")
    prefs = getattr(state, "prefectures", None) or {}
    if not _route or _route not in prefs:
        return {"ok": False, "reason": "无有效路名（案卷缺 route）"}
    guan = (prefs[_route].get("pops") or {}).get("官僚")
    if not isinstance(guan, dict):
        return {"ok": False, "reason": f"{_route} 无官僚私囊可抄"}
    _wealth = int(guan.get("wealth", 0) or 0)
    seize = int(_wealth * FIN_CONFISCATE_RATE)
    if seize <= 0:
        return {"ok": False, "reason": f"{_route} 官僚私囊无余财可抄"}
    if _pop_obj_set(state, guan, "wealth", _wealth - seize) is None:
        guan["wealth"] = _wealth - seize
    state.change_treasury(seize)
    if isinstance(rec, dict):
        rec["judgement"] = f"抄没官僚私囊 {seize:,} 贯入国库（{_route}）"
        rec["status"] = "已定案"
    if log is not None:
        log.append(f"[抄没] {_route}：抄没官僚私囊 {seize:,} 贯入国库"
                   f"{'（皇权事件例外通道）' if imperial_exception else ''}")
    return {"ok": True, "seized": seize, "route": _route}
