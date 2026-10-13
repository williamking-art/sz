# -*- coding: utf-8 -*-
"""P1 试点纵向链条**只读读数**（试点＝绸：丝→绸） —— M80。

依据
----
* M79 选点：**绸（丝→绸）** 是唯一「作坊＋原料有货＋成品有货＋需求通道」四项齐全的链条；
* M47：成品按**作坊所属路**归属；M66：作坊已登记 `owner`；M74：需求＝`max(基本需求×余量释放, 耐用品缺口)`。

口径（**全部读既有容器，不新增账本、不改数值**）
------------------------------------------------
1. **原料/成品**：取**治所真账**（`seat_goods_readout.seat_goods` 的治所×阶层持有量）⇒ 逐路 Σ。
   **不得**按人口比例分派（台账 §三-1 已由 M47 修）。
2. **作坊**：`state.workshops`（键名含路名）⇒ 座数/`active`/`owner`（M66）/`recipe`/`yield`。
3. ⚠️ **作坊"在岗"不可得**：作坊**不在 `state.buildings`** 里 ⇒ M78 的实到机制（建筑岗位）
   **覆盖不到作坊**；而 M67 已实测「作坊岗位数**无权威来源**」⇒ 本读数**如实报 `undefined`**，
   **不按人口均分、不默认满员**（规格：缺字段标未定义）。
4. **理论上限**（标注为*上限*，不是预测）：若原料充足，`Σ 活跃作坊 (投入量 → yield)`；
   实际受原料约束 ⇒ 另给 `原料可支撑月数`（＝原料 ÷ 每轮投入），**不可解读为产量承诺**。
5. **需求与缺口**：逐治所 M74 口径求和；缺口＝需求 − 成品（**负值夹 0**）。
6. **缺失 ≠ 0**：任一段不可读 ⇒ 该段 `None` + reason，绝不填 0。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

#: 试点链条（M79 选定）
PILOT = {"workshop": "丝坊", "input_dim": "丝", "output_dim": "绸"}

__all__ = ["PILOT", "chain_of_route", "survey_pilot_chain"]


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _route_of_workshop(state, wid: str) -> Optional[str]:
    try:
        from core.domains.economy.seat_goods_readout import route_of_workshop
        return route_of_workshop(state, wid)
    except Exception:                                       # noqa: BLE001
        log.warning("p1_pilot_chain: 作坊路名解析不可用 wid=%s", wid, exc_info=True)
        return None


def _seat_stock_by_route(state) -> Optional[Dict[str, Dict[str, float]]]:
    """逐路 Σ 治所×阶层的持有量：`{路: {维: qty}}`（治所真账口径；不可读 ⇒ None）。"""
    try:
        from core.domains.economy.seat_goods_readout import seat_goods
        sg = seat_goods(state)
    except Exception:                                       # noqa: BLE001
        log.warning("p1_pilot_chain: seat_goods 不可用", exc_info=True)
        return None
    if not isinstance(sg, dict):
        return None
    out: Dict[str, Dict[str, float]] = {}
    for route, seats in sg.items():
        agg: Dict[str, float] = {}
        if isinstance(seats, dict):
            for classes in seats.values():
                if not isinstance(classes, dict):
                    continue
                for goods in classes.values():
                    if not isinstance(goods, dict):
                        continue
                    for dim, q in goods.items():
                        n = _num(q)
                        if n is not None:
                            agg[str(dim)] = agg.get(str(dim), 0.0) + n
        out[str(route)] = agg
    return out


def _route_demand(state, route: str, dim: str) -> Optional[float]:
    """逐治所 M74 口径需求求和；全不可读 ⇒ None。"""
    prefs = getattr(state, "prefectures", None)
    pdata = (prefs or {}).get(route) if isinstance(prefs, dict) else None
    seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
    if not isinstance(seats, dict):
        return None
    try:
        from core.domains.economy.seat_market_shadow import seat_demand
    except Exception:                                       # noqa: BLE001
        return None
    tot, ok = 0.0, False
    for seat in seats:
        rep = seat_demand(state, route, seat, dim)
        if rep.get("total") is not None:
            tot += float(rep["total"])
            ok = True
    return tot if ok else None


def chain_of_route(state, route: str) -> Dict[str, Any]:
    """该路的试点链条读数（只读）：原料 → 作坊 → 理论上限 → 成品 → 需求 → 缺口。"""
    stock = _seat_stock_by_route(state)
    raw = None if stock is None else (stock.get(route, {}) or {}).get(PILOT["input_dim"])
    out = None if stock is None else (stock.get(route, {}) or {}).get(PILOT["output_dim"])

    ws = getattr(state, "workshops", None)
    ws = ws if isinstance(ws, dict) else {}
    shops: List[Dict[str, Any]] = []
    owners: Dict[str, int] = {}
    for wid, row in ws.items():
        if str(wid).split("_")[0] != PILOT["workshop"]:
            continue
        if _route_of_workshop(state, wid) != route:
            continue
        row = row if isinstance(row, dict) else {}
        owner = row.get("owner") or row.get("owner_ref")
        owners[str(owner or "undefined")] = owners.get(str(owner or "undefined"), 0) + 1
        shops.append({"wid": wid, "active": row.get("active"),
                      "owner": owner, "recipe": row.get("recipe"),
                      "yield": row.get("yield"), "jobs": None,
                      "jobs_reason": ("作坊**不在 `state.buildings`** ⇒ M78 的建筑岗位实到**覆盖不到**作坊；"
                                      "且 M67 实测**作坊岗位数无权威来源** ⇒ 如实 undefined"
                                      "（**不按人口均分、不默认满员**）")})
    cap = None
    per_round = None
    if shops:
        try:
            per_round = _num((shops[0]["recipe"] or {}).get(PILOT["input_dim"]))
            yld = _num(shops[0]["yield"])
            if per_round and yld is not None:
                cap = per_round * 0 + yld * len(shops)      # 理论上限（每坊一轮的成品）
        except Exception:                                   # noqa: BLE001
            log.warning("p1_pilot_chain: 产能上限不可算 route=%s", route, exc_info=True)
            cap = None
    demand = _route_demand(state, route, PILOT["output_dim"])
    gap = None if (demand is None or out is None) else max(0.0, demand - out)
    return {
        "route": route, "pilot": dict(PILOT),
        "raw_input": None if raw is None else int(raw),
        "workshops": {"count": len(shops), "active": sum(1 for s in shops if s["active"] is True),
                      "owners": owners, "rows": shops[:8],
                      "per_round_input": per_round},
        "theoretical_output_cap_per_round": None if cap is None else int(cap),
        "cap_basis": "Σ活跃作坊 yield（**上限，非产量承诺**：实际受原料/在岗约束）",
        "finished_output": None if out is None else int(out),
        "demand": None if demand is None else int(demand),
        "gap": None if gap is None else int(gap),
        "undefined_fields": [k for k, v in (("workshop_jobs", None),
                                            ("raw_input", raw), ("finished_output", out),
                                            ("demand", demand)) if v is None],
        "note": ("只读；原料/成品取**治所真账**；需求走 **M74** 的 max 口径；"
                 "**作坊在岗如实 undefined**（M67：无权威来源；作坊不在 buildings 里）"),
    }


def diagnose_route(state, route: str) -> Dict[str, Any]:
    """该路试点链条的**原因链归因**（只读；回答 P5 的「**为何未运到**」）。

    每条归因**必须带证据数字**；证据不足 ⇒ 只报 `undefined_data`（**不臆造**）。
    判定优先级（先因后果）：`undefined_data` → `no_workshop` → `raw_shortage`
    → `capacity_shortage` → `demand_far_exceeds_supply` → `ok`。
    """
    ch = chain_of_route(state, route)
    ev: Dict[str, Any] = {
        "raw_input": ch["raw_input"], "per_round_input": ch["workshops"]["per_round_input"],
        "workshops": ch["workshops"]["count"], "active": ch["workshops"]["active"],
        "cap_per_round_total": ch["theoretical_output_cap_per_round"],
        "finished_output": ch["finished_output"], "demand": ch["demand"], "gap": ch["gap"],
    }
    reasons: List[Dict[str, Any]] = []

    def _add(code: str, note: str, evidence: Dict[str, Any]) -> None:
        reasons.append({"code": code, "note": note, "evidence": evidence})

    per = _num(ev["per_round_input"])
    raw = _num(ev["raw_input"])
    demand = _num(ev["demand"])
    out = _num(ev["finished_output"])
    cap = _num(ev["cap_per_round_total"])
    shops = int(ev["workshops"] or 0)

    if shops == 0:
        _add("no_workshop", "本路**没有该作坊** ⇒ 无产能（不是缺钱/缺料）", {"workshops": 0})
    if raw is None or per is None:
        _add("undefined_data", "原料或每轮投入不可读 ⇒ 归因不可判定（缺失≠0）",
             {"raw_input": ev["raw_input"], "per_round_input": ev["per_round_input"]})
    else:
        rounds = None if per <= 0 else raw / per
        if rounds is not None and rounds < 1:
            _add("raw_shortage", "原料**撑不满一轮** ⇒ 先缺料、后缺产能", 
                 {"raw_input": raw, "per_round_input": per, "rounds_supported": round(rounds, 3)})
    if cap is not None and demand is not None and cap < demand:
        _add("capacity_shortage", "产能上限**低于需求** ⇒ 即使满产也不够（瓶颈＝作坊数/单轮产出）",
             {"cap_per_round_total": cap, "demand": demand,
              "coverage_by_cap": None if demand <= 0 else round(cap / demand, 6)})
    if out is not None and demand is not None and demand > 0:
        cov = out / demand
        if cov < 0.1:
            _add("demand_far_exceeds_supply", "成品仅覆盖需求**不到一成** ⇒ 需求侧远大于现有供给",
                 {"finished_output": out, "demand": demand, "coverage_by_output": round(cov, 6)})
    if not reasons:
        _add("ok", "未发现结构性短缺（按现有证据）", {"finished_output": out, "demand": demand})
    verdict = reasons[0]["code"]
    return {"route": route, "pilot": dict(PILOT), "verdict": verdict, "primary": verdict,
            "reasons": reasons, "evidence": ev,
            "coverage_by_output": (None if (out is None or not demand) else round(out / demand, 6)),
            "note": ("只读归因；每条归因都带**证据数字**，证据不足只报 `undefined_data`；"
                     "**作坊在岗仍 undefined**（M67）")}


def survey_diagnosis(state, top: int = 8) -> Dict[str, Any]:
    """全图归因汇总（只读）：主要瓶颈分布 + 逐路明细（按缺口降序）。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"reason": "无 prefectures", "routes": []}
    rows = [diagnose_route(state, r) for r in prefs]
    rows = [r for r in rows if r["evidence"]["workshops"] or r["evidence"]["finished_output"]]
    rows.sort(key=lambda r: -(r["evidence"]["gap"] or 0))
    dist: Dict[str, int] = {}
    for r in rows:
        dist[r["verdict"]] = dist.get(r["verdict"], 0) + 1
    return {"routes": rows[:top], "route_count": len(rows), "verdicts": dist,
            "pilot": dict(PILOT),
            "note": "P1 原因链归因；`verdict` 为**主瓶颈**（优先级见 `diagnose_route`）"}


def survey_pilot_chain(state, top: int = 8) -> Dict[str, Any]:
    """全图试点链条汇总（只读）：按成品量排序，附未定义字段清单。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"reason": "无 prefectures", "routes": []}
    rows = [chain_of_route(state, r) for r in prefs]
    rows = [r for r in rows if r["workshops"]["count"] or r["finished_output"]]
    rows.sort(key=lambda r: -(r["finished_output"] or 0))
    return {"routes": rows[:top], "route_count": len(rows),
            "pilot": dict(PILOT),
            "totals": {
                "workshops": sum(r["workshops"]["count"] for r in rows),
                "finished_output": sum(r["finished_output"] or 0 for r in rows),
                "demand": sum(r["demand"] or 0 for r in rows),
                "gap": sum(r["gap"] or 0 for r in rows)},
            "note": "P1 试点（绸：丝→绸）纵向读数；**在岗 undefined**（M67）"}
