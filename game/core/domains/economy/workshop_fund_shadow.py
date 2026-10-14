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


def feed_price(state=None) -> Optional[float]:
    """**粮料（`grain_feed`）基准价口径单点** —— M69（Jev choose **甲 0.992**）。

    口径：配方里的 `grain_feed` 是「**从太仓扣的粮料**」（`WORKSHOP_RECIPES` 注释：
    加工型消耗依托建筑）⇒ **粮料即粮**，其基准价**复用既有粮价单点**
    `core.building_jobs.song_job_cfg()['grain_price0']`（与 M52 家计影子的粮基准价**同源**，
    因为 `MATERIAL_PRICE_BASE` **确实没有粮维**）。

    ⚠️ **只用于读数**（`recipe_cost` 采购预算 / G-4 到位率）；**不改任何仿真数值**。
    单点不可读 ⇒ `None`（**缺失≠0**，不回落 0）。

    🔴 M70：**复用** `livelihood_shadow.grain_base_price`（同一单点）——原实现在 M52 里
    把按政权分档的 `grain_price0` **求和**得 5.8（3.6× 误差），已修为按政权取档（宋 ⇒ 1.6）。
    """
    try:
        from core.domains.economy.livelihood_shadow import grain_base_price
        return grain_base_price()
    except Exception:                                       # noqa: BLE001
        log.warning("workshop_fund_shadow: 粮价单点不可用", exc_info=True)
        return None


def working_capital_budget(state) -> Dict[str, Any]:
    """**G-4 工坊营运资金 · 影子预算**（只读、**零数值**；用户 2026-10-08 裁决口径）。

    🔴 **口径（逐字取自裁决）**：出资＝**实际货主**（`owner`）从其**已有账户**划入，**纳入 `M_ALL`
    并记录转账**（**禁影子记账/凭空注资**）；**开办额度 ＝ 一个月预计工资义务 ＋ 一个生产周期原料预算**，
    **受货主可用余额限制**，**不足 ⇒ 不启动或缩产**；支付顺序 ① **先预留工资预算** → ② 余款采购
    （**只按实际成交扣款**，未成交**解冻**）。

    🔴 **只是影子**（`stage="shadow"`）：**不写 state、不改结算、不划钱** ⇒ 同种子 A/B 应恒等。
    ⚠️ **工资义务在作坊维度无权威口径**（`JOBS_PER_LEVEL` 不含作坊；Jev 裁丁 0.446）⇒ **额度不可定义**（如实）。
    """
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"stage": "shadow", "rows": [], "reason": "无 workshops（缺失≠0）"}
    rows: List[Dict[str, Any]] = []
    tot_procure = 0
    n_procure = 0
    for wid in ws:
        row = ws.get(wid) if isinstance(ws.get(wid), dict) else {}
        owner = row.get("owner") or row.get("owner_ref")
        pc = recipe_cost(state, wid)
        procure = pc.get("cost")
        if isinstance(procure, (int, float)) and not isinstance(procure, bool):
            tot_procure += int(procure)
            n_procure += 1
        rows.append({
            "workshop": wid, "owner": owner,
            "procure_budget": (None if procure is None else int(procure)),
            "procure_reason": pc.get("reason"),
            "wage_budget": None,
            "wage_reason": ("作坊维度**无工资义务权威口径**（`JOBS_PER_LEVEL` 只登记建筑；"
                            "Jev 裁丁 0.446）⇒ 一个月工资义务**不可定义**（不拿建筑口径硬套）"),
            "quota": None,
            "quota_reason": "额度含『一个月工资义务』项 ⇒ 该项不可定义 ⇒ **额度不可定义（缺失≠0）**",
            "verdict": ("undefined" if owner is None else "budget_undefined"),
        })
    return {
        "stage": "shadow",
        "rows": rows[:20],
        "workshop_count": len(rows),
        "procure_total": (tot_procure if n_procure == len(rows) else None),
        "procure_readable_count": n_procure,
        "wage_budget": None,
        "quota": None,
        "conservation_plan": (
            "**接线的守恒方案（先方案、后接线）**：① 出资＝货主**既有账户**（`owner` 指向的 POP/国库/"
            "内帑/地方府库）⇒ 属**转账**而非注资（付款方减少、收款方增加 ⇒ **`M_ALL` 恒等**）；"
            "② 每笔划转**必须登记转账**，否则破坏货币恒等式（M0–M3）；③ 采购**只按实际成交扣款**、"
            "未成交**解冻**（预留不离开货主账户）；④ **不足 ⇒ 不启动或缩产**（不借钱、不透支、不凭空注资）；"
            "⑤ 无 owner / 余额 / 买方 / 地点 ⇒ **停工或显示未定义**。"),
        "note": ("G-4 **影子预算**（裁决要求『先做影子预算，不接正式结算』）：**只读、零数值**；"
                 "原料预算取 `recipe_cost`（既有单点）；**工资义务如实未定义** ⇒ **额度与不足判定一并不可定义**。"),
    }


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
        if dim == "ration_weight":
            continue                    # **非物料**（配给权重）⇒ 本就无价，跳过是对的
        qn = _num(q)
        if qn is None or qn <= 0:
            continue
        # 🔴 M68（Jev choose 甲 0.892）：**不得静默跳过无价维**。
        #   原先此处 `if dim in ("grain_feed", "ration_weight"): continue` ⇒ 酒坊/畜栏
        #   （配方只有 `grain_feed`）直接**返回 cost=0 且 ok=True**（与本文档头「缺价维 ⇒ None」
        #   自相矛盾，违反 §3-3 缺失≠0）：实测把 **80 座**作坊的需求算成 0，
        #   且使 M58 报的「采购需求 22,000,000」**低估**（漏了这 80 座）。
        #   现改为：有量的维一律登记；**无基准价 ⇒ 记入 `missing` 并使整项 `cost=None`**。
        px = _num(_P.get(dim))
        price_source = "MATERIAL_PRICE_BASE"
        if px is None and dim == "grain_feed":
            # 🔴 M69（Jev 甲 0.992）：**粮料即粮** ⇒ 复用既有粮价单点（只动读数）
            px = feed_price(state)
            price_source = "core.building_jobs.song_job_cfg()['grain_price0']"
        dims[str(dim)] = {"qty": qn, "price": px, "price_source": price_source,
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


def funding_summary(state) -> Dict[str, Any]:
    """**产权资金到位率汇总**（只读；M71）——把"谁养得起作坊"压成一张可复跑的表。

    含：① 各**候选载体**的池与到位率（复用 `owner_candidates_shadow.survey_owner_candidates`）；
    ② **G-4 逐路**到位率的分位（官营/民营：可算路数、中位、最低、满覆盖路数）。
    供**多时点取证**（开局／6 月／12 月）直接调用；**任一侧不可读 ⇒ `None`**（缺失≠0）。
    """
    out: Dict[str, Any] = {"carriers": [], "g4": {}, "procure_need": None}
    try:
        from core.domains.economy import owner_candidates_shadow as ocs
        need = ocs.procure_need(state)
        out["procure_need"] = need.get("value")
        out["unreadable_workshops"] = need.get("unreadable_count", 0)
        for c in ocs.survey_owner_candidates(state)["candidates"]:
            out["carriers"].append({"key": c["key"], "label": c["label"], "pool": c["pool"],
                                    "cover": c["procure_cover"],
                                    "parallel_ledger_violation": c["parallel_ledger_violation"]})
    except Exception:                                       # noqa: BLE001
        log.warning("funding_summary: 载体表不可读", exc_info=True)
    try:
        g = owner_funding_by_route(state)
        for side in ("gov", "merchant"):
            covers = sorted(r[side]["cover"] for r in g["routes"]
                            if r[side]["cover"] is not None)
            n = len(covers)
            out["g4"][side] = {
                "routes": n,
                "min": covers[0] if n else None,
                "median": covers[n // 2] if n else None,
                "max": covers[-1] if n else None,
                "full": sum(1 for c in covers if c >= 1.0),
                "undefined": sum(1 for r in g["routes"] if r[side]["cover"] is None),
            }
    except Exception:                                       # noqa: BLE001
        log.warning("funding_summary: 逐路表不可读", exc_info=True)
    return out


def owner_funding_by_route(state) -> Dict[str, Any]:
    """**G-4 逐路资金到位率**（只读；M68）——用 M66 登记的货主把"全国池影子"升级成**逐路可用数字**。

    口径
    ----
    * 官营作坊（`owner == "local:<路>"`）：营运资金池 = 该路**地方府库治所真账**
      （`local_treasury_bridge.aggregate_seat_local_treasury`；未下沉 ⇒ `None`，**不回落 0**）；
    * 民营作坊（`owner == "pop:<路>:商人"`）：资金池 = 该路**商人 POP wealth**
      （`pop_bridge.pop_get(pdata, "商人", "wealth")`，真账单点）；
    * 需求 = Σ 该路该类作坊的 `recipe_cost`（既有基准价；**缺价维 ⇒ None**）；
    * 到位率 = `min(1, pool / need)`；任一侧不可读 ⇒ `None`（**缺失≠0**，不臆造）。
    * ⚠️ **只是读数**：不划钱、不改 balance、不动作坊产出（为 D 线"营运资金划入"提供依据）。
    """
    prefs = getattr(state, "prefectures", None)
    ws = getattr(state, "workshops", None)
    if not isinstance(prefs, dict) or not isinstance(ws, dict):
        return {"reason": "无 prefectures/workshops", "routes": [], "total": None}
    rows: List[Dict[str, Any]] = []
    for route in prefs:
        gov_need = 0.0
        gov_n = 0
        mer_need = 0.0
        mer_n = 0
        unreadable: List[str] = []
        for wid, row in ws.items():
            owner = (row or {}).get("owner") or (row or {}).get("owner_ref")
            if not owner:
                continue
            if owner == f"local:{route}":
                pass
            elif owner == f"pop:{route}:商人":
                pass
            else:
                continue                                  # 属于别的路（或未登记形态）
            rep = recipe_cost(state, wid)
            if rep.get("cost") is None:
                unreadable.append(wid)
                continue
            if owner.startswith("local:"):
                gov_need += float(rep["cost"])
                gov_n += 1
            else:
                mer_need += float(rep["cost"])
                mer_n += 1
        if gov_n == 0 and mer_n == 0:
            continue

        def _pool(kind: str):
            try:
                pdata = prefs.get(route)
                if kind == "local":
                    from core.foundation.ledger.local_treasury_bridge import (
                        aggregate_seat_local_treasury)
                    return aggregate_seat_local_treasury(pdata)
                from core.foundation.ledger.pop_bridge import pop_get
                return pop_get(pdata, "商人", "wealth")
            except Exception:                               # noqa: BLE001
                log.warning("owner_funding_by_route: 取池失败 route=%s kind=%s",
                            route, kind, exc_info=True)
                return None

        g_pool = _num(_pool("local"))
        m_pool = _num(_pool("pop"))
        rows.append({
            "route": route,
            "gov": {"workshops": gov_n, "need": int(gov_need) if gov_n else None,
                    "pool": None if g_pool is None else int(g_pool),
                    "cover": None if (g_pool is None or gov_need <= 0) else min(1.0, g_pool / gov_need)},
            "merchant": {"workshops": mer_n, "need": int(mer_need) if mer_n else None,
                         "pool": None if m_pool is None else int(m_pool),
                         "cover": None if (m_pool is None or mer_need <= 0) else min(1.0, m_pool / mer_need)},
            "unreadable_recipes": unreadable[:5],
        })
    rows.sort(key=lambda r: ((r["gov"]["cover"] if r["gov"]["cover"] is not None else 9.9),
                             (r["merchant"]["cover"] if r["merchant"]["cover"] is not None else 9.9)))
    return {"routes": rows, "route_count": len(rows),
            "worst": rows[0] if rows else None,
            "note": ("只读读数：官营看**地方府库真账**、民营看**本路商人 wealth**；"
                     "任一侧不可读 ⇒ None（缺失≠0）。**不划钱**")}


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
