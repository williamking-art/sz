# -*- coding: utf-8 -*-
"""作坊**产权落点候选**只读盘点（主线 D/E 卡口） —— M58。

背景（M51 实测）：`owner_kind`/`owner_ref` 在 core 内**仅见于 `construction_shadow`** ⇒
**107 作坊全无货主**；`workshop_fund_shadow` 因此对每个作坊报 `status="undefined"`。
本模块**不动 state**，只把"谁持有作坊"的**候选载体**摆出来并算清后果
（Jev choose B 0.863：含"作坊自持"方案并**显式评估平行账本**）。

口径
----
* **货主 id 复用既有词表**（`material_holding.resolve_holder` 接受的形式）：
  `pop:<路>:<阶层>` · `state_treasury` · `imperial`；路级官府实体走
  `local:<路>`（真账在治所 `local_treasury`，读口＝`local_treasury_bridge`）。
* **资金池一律走既有单点**：国库 `state.treasury` · 内帑 `state.imperial_treasury` ·
  本路阶层 `pop_bridge.pop_get` · 地方府库 `aggregate_seat_local_treasury`。
  **不可读 ⇒ `None` + reason**（缺失≠0）。
* **采购需求**＝Σ 各作坊 `recipe_cost`（既有基准价）；**工资需求**在作坊维度**无权威条目**
  ⇒ `None` + reason（`JOBS_PER_LEVEL` 只登记建筑、`WAGE_RATE` 只登记 牧场/工坊/矿场）。
* 🔴 **"作坊自持"必须标为违规**：它需要一个与 POP 平行的存量载体（如
  `state.workshops[wid]["fund"]`）⇒ 违反 §3-1「禁与 POP 平行的账本」；
  模块给出**改造条件**而不是把它当可行方案。
* **只读**：不写 state、不给默认选择（口径待裁）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

#: 候选（**顺序即展示顺序**）；`parallel_ledger=True` 者**违规**，仅供对照
CANDIDATES: tuple = (
    {"key": "state_treasury", "label": "国库（中央）", "owner_id_form": "state_treasury",
     "profit_to": "国库", "parallel_ledger": False, "note": "既有账户，结算里最常用"},
    {"key": "imperial", "label": "内帑", "owner_id_form": "imperial",
     "profit_to": "内帑", "parallel_ledger": False,
     "note": "甲口径下与国库分理；用于皇室/专项支出"},
    {"key": "pop_gentry", "label": "本路士绅", "owner_id_form": "pop:<路>:士绅",
     "profit_to": "本路士绅 POP wealth", "parallel_ledger": False,
     "note": "符合 POP 挂载律；但士绅 wealth 同时是消费/奢侈支出的来源"},
    {"key": "pop_merchant", "label": "本路商人", "owner_id_form": "pop:<路>:商人",
     "profit_to": "本路商人 POP wealth", "parallel_ledger": False,
     "note": "更贴『经营主体』语义（商人本就持货经营）"},
    {"key": "local_route", "label": "路级官府（地方府库）", "owner_id_form": "local:<路>",
     "profit_to": "本路地方府库（治所真账）", "parallel_ledger": False,
     "note": "地方府库已州府化（M37），可承载官营作坊"},
    {"key": "workshop_self", "label": "作坊自持", "owner_id_form": "（无既有词表）",
     "profit_to": "作坊自身", "parallel_ledger": True,
     "note": ("🔴 **违反 §3-1 禁与 POP 平行的账本**：自持需要独立存量载体"
              "（如 `state.workshops[wid]['fund']`）。**改造条件**：把营运资金挂到既有载体"
              "（国库/内帑/POP wealth/地方府库），或把『持有者』登记为既有账户——"
              "否则每次结算都要在 POP 之外维护第二份存量账")},
)

__all__ = ["SCHEMA_VERSION", "CANDIDATES", "pool_of", "procure_need", "wage_need",
           "affordability", "survey_owner_candidates", "capital_gap_report",
           "plan_capital_allocation"]


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _prefs(state) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None)
    return prefs if isinstance(prefs, dict) else None


def pool_of(state, key: str, route: Optional[str] = None) -> Dict[str, Any]:
    """候选载体的**资金池**读数：`{value|None, reason, source}`。"""
    if key == "state_treasury":
        v = _num(getattr(state, "treasury", None))
        return {"value": None if v is None else int(v),
                "reason": None if v is not None else "国库不可读（缺失≠0）",
                "source": "state.treasury"}
    if key == "imperial":
        v = _num(getattr(state, "imperial_treasury", None))
        return {"value": None if v is None else int(v),
                "reason": None if v is not None else "内帑字段缺失（该局可能用甲口径分理）",
                "source": "state.imperial_treasury"}
    if key in ("pop_gentry", "pop_merchant"):
        cls = "士绅" if key == "pop_gentry" else "商人"
        prefs = _prefs(state)
        if prefs is None:
            return {"value": None, "reason": "无 prefectures", "source": "pop_bridge.pop_get"}
        routes = [route] if route else list(prefs)
        tot, readable = 0, False
        for r in routes:
            pdata = prefs.get(r)
            if not isinstance(pdata, dict):
                continue
            try:
                from core.foundation.ledger.pop_bridge import pop_get
                v = _num(pop_get(pdata, cls, "wealth"))
            except Exception:                               # noqa: BLE001
                log.warning("owner_candidates_shadow: pop_get 不可用", exc_info=True)
                v = None
            if v is not None:
                tot += int(v)
                readable = True
        return {"value": tot if readable else None,
                "reason": None if readable else f"{cls} wealth 不可读（缺失≠0）",
                "source": "pop_bridge.pop_get(pdata, '%s', 'wealth')" % cls}
    if key == "local_route":
        prefs = _prefs(state)
        if prefs is None:
            return {"value": None, "reason": "无 prefectures",
                    "source": "local_treasury_bridge.aggregate_seat_local_treasury"}
        routes = [route] if route else list(prefs)
        tot, readable = 0, False
        for r in routes:
            pdata = prefs.get(r)
            if not isinstance(pdata, dict):
                continue
            try:
                from core.foundation.ledger.local_treasury_bridge import (
                    aggregate_seat_local_treasury)
                v = _num(aggregate_seat_local_treasury(pdata))
            except Exception:                               # noqa: BLE001
                v = None
            if v is not None:
                tot += int(v)
                readable = True
        return {"value": tot if readable else None,
                "reason": None if readable else "地方府库未下沉或不可读（缺失≠0）",
                "source": "local_treasury_bridge.aggregate_seat_local_treasury(pdata)"}
    if key == "workshop_self":
        return {"value": None,
                "reason": ("作坊自持**没有既有载体**（不敢臆造一个新账本）⇒ 池不可读；"
                           "且该方案本身违反 §3-1（见候选 note 的改造条件）"),
                "source": "（无）"}
    return {"value": None, "reason": f"未知候选 {key!r}", "source": "（无）"}


def procure_need(state) -> Dict[str, Any]:
    """全部作坊的**采购预算合计**（Σ `workshop_fund_shadow.recipe_cost`）。"""
    try:
        from core.domains.economy import workshop_fund_shadow as wfs
    except Exception:                                       # noqa: BLE001
        return {"value": None, "unreadable": [], "reason": "workshop_fund_shadow 不可用"}
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"value": None, "unreadable": [], "reason": "无 workshops"}
    tot, unreadable = 0, []
    for wid in ws:
        rep = wfs.recipe_cost(state, wid)
        if rep.get("cost") is None:
            unreadable.append(wid)
        else:
            tot += int(rep["cost"])
    return {"value": tot if not unreadable else None, "unreadable": unreadable[:20],
            "unreadable_count": len(unreadable),
            "reason": None if not unreadable else "部分作坊缺基准价 ⇒ 合计不可定义（缺失≠0）"}


def wage_need(state) -> Dict[str, Any]:
    """作坊**工资需求**：Σ `workshop_fund_shadow.wage_obligation`（2026-10-21 影子工价表）。

    表未登记类型/工价不可读 ⇒ 合计 `None` + 未读清单（缺失≠0，不拿建筑口径硬套）。
    """
    try:
        from core.domains.economy import workshop_fund_shadow as wfs
    except Exception:                                       # noqa: BLE001
        return {"value": None, "unreadable": [], "reason": "workshop_fund_shadow 不可用"}
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"value": None, "unreadable": [], "reason": "无 workshops"}
    tot, unreadable = 0, []
    for wid in ws:
        rep = wfs.wage_obligation(state, wid)
        if rep.get("obligation") is None:
            unreadable.append(wid)
        else:
            tot += int(rep["obligation"])
    return {"value": tot if not unreadable else None,
            "unreadable": unreadable[:20], "unreadable_count": len(unreadable),
            "reason": None if not unreadable else "部分作坊工资义务不可读 ⇒ 合计不可定义（缺失≠0）",
            "source": "content.data_workshop_jobs"}


def capital_gap_report(state) -> Dict[str, Any]:
    """A G-4 P0：**逐路资金缺口**只读报告（Jev 首选货主 local_route 口径）。

    - 需求 = Σ(采购预算 + 工资义务)（任一作坊不可读 ⇒ 该路需求 `None`）；
    - 资金池 = `pool_of(state, "local_route", route)`（治所真账聚合）；
    - coverage = min(1, pool/need)（不可读/need≤0 ⇒ None）；shortfall = max(0, need-pool)；
    - 另给候选池总览（国库/士绅/商人）与全局需求；**只读、不预选、不接钱**。
    """
    from core.domains.economy import workshop_fund_shadow as wfs
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"read_only": True, "reason": "无 workshops", "routes": [],
                "candidates": [], "total_need": None}
    per_route: Dict[str, Dict[str, Any]] = {}
    for wid in ws:
        w = ws.get(wid) or {}
        name = str(w.get("name") or "")
        route = wfs.workshop_route(state, wid)
        buy = wfs.recipe_cost(state, wid)
        wage = wfs.wage_obligation(state, wid)
        r = route or "（判不出路）"
        row = per_route.setdefault(r, {"route": route, "workshops": 0,
                                       "procure_need": 0, "wage_need": 0,
                                       "unreadable": []})
        row["workshops"] += 1
        if buy.get("cost") is None or wage.get("obligation") is None:
            row["unreadable"].append(wid)
        else:
            row["procure_need"] += int(buy["cost"])
            row["wage_need"] += int(wage["obligation"])
    routes = []
    for r, row in sorted(per_route.items(), key=lambda kv: str(kv[0])):
        need = (None if row["unreadable"]
                else row["procure_need"] + row["wage_need"])
        pool = pool_of(state, "local_route", row["route"]) if row["route"] else {
            "value": None, "reason": "判不出路", "source": "（无）"}
        routes.append({
            "route": row["route"], "workshops": row["workshops"],
            "procure_need": row["procure_need"], "wage_need": row["wage_need"],
            "need": need, "unreadable": row["unreadable"][:10],
            "unreadable_count": len(row["unreadable"]),
            "local_pool": pool["value"], "pool_source": pool["source"],
            "coverage": affordability(pool["value"], need),
            "shortfall": (None if (pool["value"] is None or need is None)
                          else max(0, int(need - pool["value"]))),
        })
    total_need_ok = all(r["need"] is not None for r in routes) and bool(routes)
    total_need = sum(int(r["need"]) for r in routes) if total_need_ok else None
    cands = []
    for key in ("state_treasury", "imperial", "pop_gentry", "pop_merchant", "local_route"):
        p = pool_of(state, key)
        cands.append({"key": key, "pool": p["value"], "pool_source": p["source"],
                      "coverage": affordability(p["value"], total_need)})
    return {
        "schema_version": SCHEMA_VERSION, "read_only": True,
        "owner_choice": "local_route（Jev A 0.554）",
        "workshops": len(ws), "routes": routes,
        "route_count": len(routes),
        "total_need": total_need,
        "candidates": cands,
        "note": ("只读资金缺口；工资表为玩法设定（content/data_workshop_jobs.py），"
                 "接钱前需确认；不可读单路 = None，不按 0。"),
    }


def affordability(pool: Optional[float], need: Optional[float]) -> Optional[float]:
    """到位率 `min(1, pool/need)`；任一不可读或 need ≤ 0 ⇒ `None`（不臆造）。"""
    p, n = _num(pool), _num(need)
    if p is None or n is None or n <= 0:
        return None
    return min(1.0, p / n)


def plan_capital_allocation(state, owner_key: str = "local_route") -> Dict[str, Any]:
    """A P1 影子：按现有资金池做**贪心分配计划**（只读，不写账、不扣钱）。

    - 逐路取池（`owner_key` 支持 `local_route` / `state_treasury`）；
    - 作坊按 **wid 字典序** 处理（可复跑、无优先级臆造）；需求 = 采购+工资；
    - 池够 ⇒ `funded`；只够一部分 ⇒ `partial`（分配剩余全部）；不够 ⇒ `unfunded`；
    - 任一路池/需求不可读 ⇒ 该路 `undefined`，不按 0 分配；返回明细与汇总。
    """
    from core.domains.economy import workshop_fund_shadow as wfs
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"read_only": True, "reason": "无 workshops", "routes": [], "totals": {}}
    by_route: Dict[str, Dict[str, Any]] = {}
    for wid in sorted(ws):
        w = ws.get(wid) or {}
        route = wfs.workshop_route(state, wid)
        buy = wfs.recipe_cost(state, wid)
        wage = wfs.wage_obligation(state, wid)
        need = (int(buy["cost"]) + int(wage["obligation"])
                if buy.get("cost") is not None and wage.get("obligation") is not None else None)
        key = route or "（判不出路）"
        by_route.setdefault(key, {"route": route, "items": []})["items"].append(
            {"wid": wid, "name": w.get("name"), "need": need})

    routes = []
    totals = {"funded": 0, "partial": 0, "unfunded": 0, "undefined": 0,
              "allocated": 0, "required": 0}
    if owner_key == "state_treasury":
        global_pool = pool_of(state, "state_treasury")
        pool_ctx = {k: global_pool for k in by_route}
    else:
        pool_ctx = {k: pool_of(state, "local_route", v["route"]) if v["route"] else
                    {"value": None, "reason": "判不出路", "source": "（无）"}
                    for k, v in by_route.items()}
    for key in sorted(by_route, key=str):
        row = by_route[key]
        pool = pool_ctx[key]
        remaining = pool["value"]
        items = []
        for it in row["items"]:
            need = it["need"]
            if need is None:
                st, alloc = "undefined", None
            elif remaining is None:
                st, alloc = "undefined", None
            elif remaining >= need:
                st, alloc = "funded", need
                remaining -= need
            elif remaining > 0:
                st, alloc = "partial", remaining
                remaining = 0
            else:
                st, alloc = "unfunded", 0
            totals[st] += 1
            if alloc:
                totals["allocated"] += int(alloc)
            if need:
                totals["required"] += int(need)
            items.append(dict(it, status=st, allocated=alloc))
        routes.append({"route": row["route"], "pool": pool["value"],
                       "pool_source": pool["source"], "items": items})
    return {"schema_version": SCHEMA_VERSION, "read_only": True, "owner_key": owner_key,
            "routes": routes, "totals": totals,
            "note": ("贪心影子分配：按 wid 顺序、不写账不扣钱；"
                     "池/需求不可读 ⇒ undefined，不按 0 分配。")}


def survey_owner_candidates(state) -> Dict[str, Any]:
    """候选逐项盘点（**只读**）：池、到位率、利润去向、平行账本判定。不给默认选择。"""
    buy = procure_need(state)
    wage = wage_need(state)
    rows: List[Dict[str, Any]] = []
    for c in CANDIDATES:
        pool = pool_of(state, c["key"])
        rows.append({
            "key": c["key"], "label": c["label"], "owner_id_form": c["owner_id_form"],
            "pool": pool["value"], "pool_source": pool["source"], "pool_reason": pool["reason"],
            "profit_to": c["profit_to"],
            "procure_cover": affordability(pool["value"], buy["value"]),
            "wage_cover": affordability(pool["value"], wage["value"]),
            "parallel_ledger_violation": bool(c["parallel_ledger"]),
            "note": c["note"],
        })
    ws = getattr(state, "workshops", None)
    return {"schema_version": SCHEMA_VERSION,
            "workshops": len(ws) if isinstance(ws, dict) else 0,
            "procure_need": buy, "wage_need": wage,
            "candidates": rows,
            "violations": [r["key"] for r in rows if r["parallel_ledger_violation"]],
            "note": ("只读盘点，**不预选**：口径（谁持有作坊）属玩法裁定；"
                     "自持方案已标违规并给出改造条件")}
