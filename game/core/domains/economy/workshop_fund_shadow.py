# -*- coding: utf-8 -*-
"""G-4 工坊经营资金**影子预算**（主线 D 第一切片） —— M51。

规格（`reviews/未落地设计裁定与实施路线.md` §主线D）：
> 先做影子预算，**不接正式结算**。实际货主从已有账户划入营运资金，先冻结工资义务，
> 再冻结采购预算；成交才扣款，到货后加工，有买方才记销售收入，工资不足记欠付。
> 做到什么程度：**资金来源、地点、货主、工资、采购、到货、销售都可追踪；M_ALL 守恒；
> 无 owner、余额、买方或地点时停工或显示未定义**。

本模块**只做前四项的读数**（货主 / 资金 / 工资义务 / 采购预算；Jev choose A 0.831），
**不写任何 state、不接正式结算**。

口径（硬约束对照）
------------------
* 🔴 **产权模型不存在**（实测：`owner_kind`/`owner_ref` 除 `construction_shadow` 外全仓无）
  ⇒ 「实际货主」**无权威来源** ⇒ 按规格「**无 owner ⇒ 停工或显示未定义**」，
  本模块对每个作坊报 **`status="undefined_no_owner"`**，**不臆造货主**
  （若将来 `state.workshops[wid]` 出现 `owner`/`owner_kind`，则优先读它——前向兼容）。
* **地点**：键内嵌路名 ⇒ 复用 `seat_goods_readout.route_of_workshop`（单点解析）；
  判不出 ⇒ `None`（**不臆造地点**）。
* **工资义务**：作坊**不在** `JOBS_PER_LEVEL`（那是"建筑"表）⇒ 无岗位数
  ⇒ **`None` + reason**（**不拿建筑岗位数硬套作坊**）。工价单点仍报出（既有 `WAGE_RATE`）。
* **采购预算**：Σ(配方量 × `MATERIAL_PRICE_BASE`)；**任一维无基准价 ⇒ `None` + 列出缺价维**
  （不臆造价）。
* **资金来源**：**候选池三档并列**（国库 / 全国工匠 / 全国士绅+商人），**不预选**。
* **M_ALL 守恒**：只读 ⇒ 报告前后 `m_all` 并断言相等（规格要求）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

__all__ = [
    "SCHEMA_VERSION", "SHADOW_FIELDS", "owner_of", "workshop_route",
    "wage_obligation", "recipe_cost", "funding_candidates", "workshop_shadow",
    "survey_workshop_fund_shadow",
]

#: 规格要求的可追踪项（**逐项给出 `None` 或值 + reason**，不做"缺就跳过"）
SHADOW_FIELDS = ("funding_source", "location", "owner", "wage", "purchase",
                 "arrival", "sales")

#: 第二轮及以后才做的项（本批**明确不做**，如实标态而不是留空）
LATER_FIELDS = ("arrival", "sales", "settlement_deduction", "arrears")


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def owner_of(state, wid: str) -> Dict[str, Any]:
    """作坊**货主**解析：优先读 `state.workshops[wid]` 的产权字段；缺失 ⇒ **未定义**。"""
    ws = (getattr(state, "workshops", None) or {}).get(wid)
    if not isinstance(ws, dict):
        return {"owner": None, "defined": False, "reason": "作坊不存在"}
    for k in ("owner", "owner_ref"):
        if ws.get(k):
            return {"owner": ws.get(k), "defined": True, "reason": None,
                    "kind": ws.get("owner_kind")}
    return {"owner": None, "defined": False,
            "reason": ("产权模型未实现：`state.workshops[wid]` 无 owner/owner_ref，"
                       "core 内 `owner_kind`/`owner_ref` 仅见于 construction_shadow ⇒ "
                       "按规格『无 owner ⇒ 停工或显示未定义』报未定义，**不臆造货主**")}


def workshop_route(state, wid: str) -> Optional[str]:
    """作坊所属路（键内嵌路名，复用单点解析）；判不出 ⇒ `None`。"""
    try:
        from core.domains.economy.seat_goods_readout import route_of_workshop
        return route_of_workshop(state, wid)
    except Exception:                                       # noqa: BLE001
        log.warning("workshop_fund_shadow: 路名解析不可用", exc_info=True)
        return None


def wage_obligation(state, wid: str) -> Dict[str, Any]:
    """作坊**工资义务**：作坊不在 `JOBS_PER_LEVEL` ⇒ 岗位数不可读 ⇒ **`None` + reason**。"""
    ws = (getattr(state, "workshops", None) or {}).get(wid)
    if not isinstance(ws, dict):
        return {"jobs": None, "rate": None, "obligation": None, "reason": "作坊不存在"}
    name = str(ws.get("name") or "")
    try:
        from core.domains.economy.wage_gate_readout import wage_rate_for
        rate = wage_rate_for(name)
    except Exception:                                       # noqa: BLE001
        rate = None
    return {"jobs": None, "rate": rate, "obligation": None,
            "reason": ("作坊 `%s` 不在 `JOBS_PER_LEVEL`（岗位表只登记建筑：农田/庄园/工坊/商铺…）"
                       "⇒ 岗位数与工资义务**不可定义**；不拿建筑岗位数硬套作坊"
                       % (name or wid))}


def recipe_cost(state, wid: str) -> Dict[str, Any]:
    """作坊**采购预算**：Σ(配方量 × 既有基准价)；缺价维 ⇒ `None` + 列出。"""
    ws = (getattr(state, "workshops", None) or {}).get(wid)
    if not isinstance(ws, dict):
        return {"cost": None, "dims": {}, "missing_price": [], "reason": "作坊不存在"}
    recipe = ws.get("recipe") or {}
    try:
        from content.data import MATERIAL_PRICE_BASE as _P
    except Exception:                                       # noqa: BLE001
        try:
            from content.data_external import MATERIAL_PRICE_BASE as _P   # type: ignore
        except Exception:                                   # noqa: BLE001
            _P = None
    if not isinstance(_P, dict):
        return {"cost": None, "dims": {}, "missing_price": [],
                "reason": "无 MATERIAL_PRICE_BASE（基准价单点不可读）⇒ 不臆造估价"}
    dims: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    total = 0.0
    ok = True
    for dim, q in recipe.items():
        if dim in ("grain_feed", "ration_weight"):
            continue
        qn = _num(q)
        if qn is None or qn <= 0:
            continue
        px = _num(_P.get(dim))
        dims[str(dim)] = {"qty": qn, "price": px,
                          "value": None if px is None else round(qn * px, 4)}
        if px is None:
            missing.append(str(dim))
            ok = False
            continue
        total += qn * px
    return {"cost": int(round(total)) if ok else None, "dims": dims,
            "missing_price": missing,
            "reason": None if ok else "部分维无基准价 ⇒ 采购预算**不可定义**（不臆造）"}


def funding_candidates(state) -> Dict[str, Optional[int]]:
    """**候选资金来源三档并列**（国库 / 全国工匠 / 全国士绅+商人）；不可读 ⇒ `None`。"""
    out: Dict[str, Optional[int]] = {}
    tre = _num(getattr(state, "treasury", None))
    out["treasury"] = None if tre is None else int(tre)
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        out["artisan"] = None
        out["gentry_merchant"] = None
        return out
    for key, classes in (("artisan", ("工匠",)), ("gentry_merchant", ("士绅", "商人"))):
        tot = 0
        readable = False
        for pdata in prefs.values():
            pops = (pdata or {}).get("pops") if isinstance(pdata, dict) else None
            if not isinstance(pops, dict):
                continue
            for cls in classes:
                w = _num((pops.get(cls) or {}).get("wealth") if isinstance(pops.get(cls), dict)
                         else None)
                if w is not None:
                    tot += int(w)
                    readable = True
        out[key] = tot if readable else None
    return out


def workshop_shadow(state, wid: str) -> Dict[str, Any]:
    """单个作坊的影子预算读数（**只读**）：规格七项逐项给值或 `None` + reason。"""
    ws = (getattr(state, "workshops", None) or {}).get(wid)
    if not isinstance(ws, dict):
        return {"wid": wid, "status": "not_found", "missing": ["workshop"]}
    own = owner_of(state, wid)
    route = workshop_route(state, wid)
    wage = wage_obligation(state, wid)
    buy = recipe_cost(state, wid)
    missing = []
    if not own["defined"]:
        missing.append("owner")
    if route is None:
        missing.append("location")
    if wage["obligation"] is None:
        missing.append("wage")
    if buy["cost"] is None:
        missing.append("purchase")
    # 🔴 规格：无 owner / 余额 / 买方 / 地点 ⇒ **停工或显示未定义**
    status = "undefined" if missing else "shadow_ready"
    return {"wid": wid, "name": ws.get("name"), "active": bool(ws.get("active")),
            "status": status, "owner": own, "location": route,
            "wage": wage, "purchase": buy,
            "funding_source_candidates": funding_candidates(state),
            "missing": sorted(missing), "not_in_this_batch": list(LATER_FIELDS)}


def survey_workshop_fund_shadow(state) -> Dict[str, Any]:
    """全局影子读数 + **M_ALL 守恒断言**（只读，故守恒恒成立；报告前后值）。"""
    try:
        from core.foundation.ledger import money as _money
        m_all_before = _money.m_all(state)
    except Exception:                                       # noqa: BLE001
        _money = None
        m_all_before = None
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"schema_version": SCHEMA_VERSION, "workshops": 0, "reason": "无 state.workshops"}
    rows = {wid: workshop_shadow(state, wid) for wid in ws}
    defined = [w for w, v in rows.items() if v.get("status") == "shadow_ready"]
    no_owner = [w for w, v in rows.items() if "owner" in (v.get("missing") or [])]
    no_route = [w for w, v in rows.items() if "location" in (v.get("missing") or [])]
    m_all_after = None
    if _money is not None:
        try:
            m_all_after = _money.m_all(state)
        except Exception:                                   # noqa: BLE001
            m_all_after = None
    return {"schema_version": SCHEMA_VERSION, "workshops": len(ws),
            "shadow_ready": len(defined), "undefined_no_owner": len(no_owner),
            "undefined_no_location": len(no_route),
            "funding_source_candidates": funding_candidates(state),
            "conservation": {"m_all_before": m_all_before, "m_all_after": m_all_after,
                             "ok": (None if (m_all_before is None or m_all_after is None)
                                    else bool(m_all_before == m_all_after))},
            "sample": dict(list(rows.items())[:3])}
