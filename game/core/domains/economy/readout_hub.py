# -*- coding: utf-8 -*-
"""统一读数索引（主线A / P5 第一切片） —— M54。

规格（`specs/economy/unified-civilian-market/tasks.md` P5）：
> 每个显著读数**能下钻到来源**；读数缺失**不显示为 0**；玩家能回答「哪里短缺、为何未运到、
> 谁本来应供、旨意为何未办成、结果影响了谁」。

本模块把本会话落地的 **8 个只读读数模块**聚成一个入口（Jev choose A 0.855），**只读**：

* 每项给 `{label, value | None, display, unit, source, drill_down, reason}`；
* 🔴 **缺失一律 `display="undefined"` + `reason`**，**绝不显示 0**（P5 硬要求）；
* `source`＝`模块:函数`（可下钻到来源）；`drill_down`＝怎么取明细（参数/路径）；
* **单个读数失败不拖垮整表**：该项转 `undefined` + reason，并 `logging.warning(exc_info=True)`（不得静默）；
* ⚠️ 本批**只做后端索引**——**前端面板未接**（明写，不谎报"已显"）。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

__all__ = ["SCHEMA_VERSION", "READOUTS", "collect", "index", "undefined_summary"]


def _money_total(state) -> Tuple[Optional[float], Optional[str], str]:
    try:
        from core.foundation.ledger import money as _money
        v = _money.m_all(state)
    except Exception as e:                                  # noqa: BLE001
        return None, f"money.m_all 不可用：{type(e).__name__}", \
            "core.foundation.ledger.money.m_all(state)"
    if v is None:
        return None, "货币总量不可读（缺失≠0）", "core.foundation.ledger.money.m_all(state)"
    return float(v), None, "core.foundation.ledger.money.m_all(state)"


def _money_residual(state) -> Tuple[Optional[float], Optional[str], str]:
    src = "core.domains.economy.stock_identity.money_identity(state)['residual']"
    try:
        from core.domains.economy import stock_identity as si
        mon = si.money_identity(state)
    except Exception as e:                                  # noqa: BLE001
        return None, f"stock_identity 不可用：{type(e).__name__}", src
    r = mon.get("residual")
    if r is None:
        return None, "残差不可读（M_ALL 或账户不可读）", src
    return float(r), None, src


def _stock_readable_dims(state) -> Tuple[Optional[int], Optional[str], str]:
    src = "core.domains.economy.stock_identity.stock_snapshot(state)['dims']"
    try:
        from core.domains.economy import stock_identity as si
        snap = si.stock_snapshot(state)
    except Exception as e:                                  # noqa: BLE001
        return None, f"stock_snapshot 不可用：{type(e).__name__}", src
    dims = snap.get("dims")
    if dims is None:
        return None, "库存维不可读（缺失≠0）", src
    return len(dims), None, src


def _flow_dim_count(state) -> Tuple[Optional[int], Optional[str], str]:
    src = "core.domains.economy.stock_flow.coverage(state, all_months=True)"
    try:
        from core.domains.economy import stock_flow as sf
        cov = sf.coverage(state, all_months=True)
    except Exception as e:                                  # noqa: BLE001
        return None, f"stock_flow 不可用：{type(e).__name__}", src
    n = cov.get("dim_count")
    if n is None:
        return None, "流量账覆盖率不可读", src
    return int(n), None, src


def _seat_goods_consistency(state) -> Tuple[Optional[bool], Optional[str], str]:
    src = "core.domains.economy.seat_goods_readout.seat_consistency(state)"
    try:
        from core.domains.economy import seat_goods_readout as sgr
        rep = sgr.seat_consistency(state)
    except Exception as e:                                  # noqa: BLE001
        return None, f"seat_goods_readout 不可用：{type(e).__name__}", src
    ok = rep.get("ok")
    if ok is None:
        return None, str(rep.get("reason") or "一致性不可判定"), src
    return bool(ok), None, src


def _workshop_undefined(state) -> Tuple[Optional[int], Optional[str], str]:
    src = "core.domains.economy.workshop_fund_shadow.survey_workshop_fund_shadow(state)"
    try:
        from core.domains.economy import workshop_fund_shadow as wfs
        rep = wfs.survey_workshop_fund_shadow(state)
    except Exception as e:                                  # noqa: BLE001
        return None, f"workshop_fund_shadow 不可用：{type(e).__name__}", src
    if "workshops" not in rep:
        return None, str(rep.get("reason") or "作坊读数不可用"), src
    return int(rep["undefined_no_owner"]), None, src


def _livelihood_computable(state) -> Tuple[Optional[int], Optional[str], str]:
    src = "core.domains.economy.livelihood_shadow.survey_livelihood_shadow(state)"
    try:
        from core.domains.economy import livelihood_shadow as ls
        rep = ls.survey_livelihood_shadow(state)
    except Exception as e:                                  # noqa: BLE001
        return None, f"livelihood_shadow 不可用：{type(e).__name__}", src
    if "pop_rows" not in rep:
        return None, str(rep.get("reason") or "家计读数不可用"), src
    return int(rep["livelihood_computable"]), None, src


def _seat_market_pairs(state) -> Tuple[Optional[int], Optional[str], str]:
    src = "core.domains.economy.seat_market_shadow.survey_seat_market_shadow(state)"
    try:
        from core.domains.economy import seat_market_shadow as sms
        rep = sms.survey_seat_market_shadow(state, top=1)
    except Exception as e:                                  # noqa: BLE001
        return None, f"seat_market_shadow 不可用：{type(e).__name__}", src
    if "pairs_with_stock" not in rep:
        return None, str(rep.get("reason") or "治所级市场读数不可用"), src
    return int(rep["pairs_with_stock"]), None, src


def _labor_tight_routes(state) -> Tuple[Optional[int], Optional[str], str]:
    src = "core.domains.economy.wage_gate_readout.survey_wage_gate(state)['routes_labor_tight']"
    try:
        from core.domains.economy import wage_gate_readout as wg
        rep = wg.survey_wage_gate(state)
    except Exception as e:                                  # noqa: BLE001
        return None, f"wage_gate_readout 不可用：{type(e).__name__}", src
    if "routes" not in rep:
        return None, str(rep.get("reason") or "岗位读数不可用"), src
    return len(rep.get("routes_labor_tight") or []), None, src


def _pilot_chain_gap(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**P1 试点链条缺口**（绸，M80）：`value = 需求 − 成品`（夹 0）；不可读 ⇒ None + reason。

    下钻给出 成品/需求/作坊数 与**样本路**（回答"哪里短缺、为何未运到"）。
    """
    src = "core.domains.economy.p1_pilot_chain:survey_pilot_chain"
    try:
        from core.domains.economy import p1_pilot_chain as pc
        rep = pc.survey_pilot_chain(state)
    except Exception as e:                                  # noqa: BLE001
        log.warning("readout_hub: P1 试点链条读数失败", exc_info=True)
        return None, f"P1 试点链条读数异常：{type(e).__name__}", src
    totals = rep.get("totals") or {}
    gap = totals.get("gap")
    drill = {"成品": totals.get("finished_output"), "需求": totals.get("demand"),
             "作坊数": totals.get("workshops"), "样本路": (rep.get("routes") or [{}])[0].get("route")}
    # 🔴 M166：**无试点数据 ⇒ 缺口不可定义**（此前会返回 0 ⇒ 违反「缺失≠0」；由 M166 用例抓到）
    if not (rep.get("routes") or []):
        return None, "无试点数据（本局无作坊且无需求）⇒ 缺口不可定义（缺失≠0，不填 0）", {**drill, "drill": src}
    if gap is None:
        return None, "缺口不可读（原料/成品/需求任一段缺失 ⇒ 不填 0）", {**drill, "drill": src}
    return int(gap), None, {**drill, "drill": src}


def _jobs_capacity(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**岗位容量合计**（M77/M78）：开局只有 水利/常平仓（非岗位建筑）⇒ 容量 `None`（undefined）。

    ⚠️ `实到` 见 `drill_down.filled`（**建筑岗位**可算，M78）；**作坊在岗不在本项**（M67）。
    """
    src = "core.domains.economy.jobs_readout:survey_jobs"
    try:
        from core.domains.economy import jobs_readout as jr
        rep = jr.survey_jobs(state)
    except Exception as e:                                  # noqa: BLE001
        log.warning("readout_hub: 岗位读数失败", exc_info=True)
        return None, f"岗位读数异常：{type(e).__name__}", src
    cap = rep.get("capacity_total")
    drill = {"实到（建筑岗位）": rep.get("filled_total"), "有实到读数的路": rep.get("filled_routes"),
             "drill": src, "note": rep.get("note")}
    if cap is None:
        return None, "无岗位建筑（开局 buildings 只有 水利/常平仓）⇒ 容量不可定义（不填 0）", drill
    return int(cap), None, drill


def _pilot_bottleneck(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**P1 试点主瓶颈**（M82）：分布里**占比最高**的 verdict 名（字符串）；无数据 ⇒ None + reason。

    下钻给**逐 verdict 计数**与**样本路证据**（回答 P5 的「为何未运到」）。
    """
    src = "core.domains.economy.p1_pilot_chain:survey_diagnosis"
    try:
        from core.domains.economy import p1_pilot_chain as pc
        rep = pc.survey_diagnosis(state)
    except Exception as e:                                  # noqa: BLE001
        log.warning("readout_hub: P1 归因读数失败", exc_info=True)
        return None, f"P1 归因读数异常：{type(e).__name__}", src
    dist = rep.get("verdicts") or {}
    routes = rep.get("routes") or []
    drill = {"分布": dist, "路数": rep.get("route_count"),
             "样本": ({"路": routes[0]["route"], "verdict": routes[0]["verdict"],
                       "覆盖": routes[0].get("coverage_by_output")} if routes else None),
             "drill": src}
    if not dist:
        return None, "无归因数据（无作坊且无成品的路 ⇒ 不臆造瓶颈）", drill
    top = max(dist.items(), key=lambda kv: kv[1])[0]
    return top, None, drill


def _p2_readiness(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**P2 字段就绪度**（M86）：14 项里**已可定义**的字段数（`seat/level` 等）；不可读 ⇒ None。"""
    src = "core.domains.economy.entity_projection:survey_entity_projection"
    try:
        from core.domains.economy import entity_projection as ep
        rep = ep.survey_entity_projection(state)
    except Exception as e:                                  # noqa: BLE001
        log.warning("readout_hub: P2 就绪度读数失败", exc_info=True)
        return None, f"P2 就绪度异常：{type(e).__name__}", src
    ratio = rep.get("defined_ratio") or {}
    if not ratio or not rep.get("buildings"):
        return None, "无建筑 ⇒ 就绪度不可定义（缺失≠0）", {**ratio, "drill": src}
    ready = sorted([k for k, v in ratio.items() if v and v >= 1.0])
    # 🔴 M107：追加**样本原因**——给"首个未就绪字段"一条真实 reason（服务 P5「为何读不到」）
    sample = None
    try:
        prefs = getattr(state, "prefectures", {}) or {}
        for route, pdata in prefs.items():
            seats = (pdata or {}).get("seats") or {}
            for seat, srow in seats.items():
                for b, lv in ((srow or {}).get("buildings") or {}).items():
                    rep = ep.project_building(state, route, seat, b, lv)
                    if rep.get("undefined_fields"):
                        k = rep["undefined_fields"][0]
                        sample = {"field": k, "route": route, "seat": seat, "building": b,
                                  "reason": (rep["fields"].get(k) or {}).get("reason")}
                        break
                if sample:
                    break
            if sample:
                break
    except Exception:                                       # noqa: BLE001
        log.warning("readout_hub: P2 样本原因不可得", exc_info=True)
    drill = {"已就绪字段": ready, "逐字段率": ratio, "建筑数": rep.get("buildings"),
             "未就绪样本原因": sample, "drill": src}
    return len(ready), None, drill


def _building_owned(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**建筑归属已登记率**（M91–M93）：`with_owner / total`；无建筑 ⇒ None + reason。"""
    src = "core.domains.economy.building_owner:survey_building_owners"
    try:
        from core.domains.economy import building_owner as bo
        rep = bo.survey_building_owners(state)
    except Exception as e:                                  # noqa: BLE001
        log.warning("readout_hub: 建筑归属读数失败", exc_info=True)
        return None, f"建筑归属读数异常：{type(e).__name__}", src
    total = int(rep.get("total") or 0)
    if not total:
        return None, "无建筑 ⇒ 归属率不可定义（缺失≠0）", {**rep, "drill": src}
    ratio = round(int(rep.get("with_owner") or 0) / total, 4)
    return ratio, None, {**rep, "已登记率": ratio, "drill": src}


def _workshop_readiness(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**作坊（经营记录）字段就绪数**（M96）：14 项里可定义者；无作坊 ⇒ None（缺失≠0）。"""
    src = "core.domains.economy.entity_projection:survey_workshop_projection"
    try:
        from core.domains.economy import entity_projection as ep
        rep = ep.survey_workshop_projection(state)
    except Exception as e:                                  # noqa: BLE001
        log.warning("readout_hub: 作坊就绪度失败", exc_info=True)
        return None, f"作坊就绪度异常：{type(e).__name__}", src
    ratio = rep.get("defined_ratio") or {}
    if not rep.get("workshops") or not ratio:
        return None, "无作坊 ⇒ 就绪度不可定义（缺失≠0）", {**ratio, "drill": src}
    ready = sorted([k for k, v in ratio.items() if v and v >= 1.0])
    return len(ready), None, {"已就绪字段": ready, "逐字段率": ratio,
                              "作坊数": rep.get("workshops"), "drill": src}


def _p2_gaps(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**P2 未就绪原因分布**（M109，只读）：去重原因 → 涉及字段/实体数。

    值＝**去重原因条数**；下钻给逐原因明细与一条样本（服务 P5「**为何**读不到」）。
    无实体 ⇒ None + reason（缺失≠0）。
    """
    src = "core.domains.economy.entity_projection（建筑+作坊逐项投影）"
    try:
        from core.domains.economy import entity_projection as ep
    except Exception as e:                                  # noqa: BLE001
        return None, f"原因分布不可读：{type(e).__name__}", src
    by_reason: Dict[str, Dict[str, Any]] = {}
    entities = 0
    max_scan = 48                                          # 🔴 采样上限（性能门：全量 147 实体过慢）
    seen_routes = 0
    try:
        prefs = getattr(state, "prefectures", {}) or {}
        for route, pdata in prefs.items():
            for seat, srow in ((pdata or {}).get("seats") or {}).items():
                for b, lv in ((srow or {}).get("buildings") or {}).items():
                    if entities >= max_scan:
                        break
                    rep = ep.project_building(state, route, seat, b, lv)
                    entities += 1
                    for k in rep.get("undefined_fields") or []:
                        r = ((rep["fields"].get(k) or {}).get("reason") or "（无原因）")[:60]
                        d = by_reason.setdefault(r, {"fields": [], "count": 0})
                        d["count"] += 1
                        if k not in d["fields"]:
                            d["fields"].append(k)
                if entities >= max_scan:
                    break
            seen_routes += 1
            if entities >= max_scan:
                break
        for wid in (getattr(state, "workshops", None) or {}):
            if entities >= max_scan * 2:
                break
            rep = ep.project_workshop(state, wid)
            if not rep.get("fields"):
                continue
            entities += 1
            for k in rep.get("undefined_fields") or []:
                r = ((rep["fields"].get(k) or {}).get("reason") or "（无原因）")[:60]
                d = by_reason.setdefault(r, {"fields": [], "count": 0})
                d["count"] += 1
                if k not in d["fields"]:
                    d["fields"].append(k)
    except Exception:                                       # noqa: BLE001
        log.warning("readout_hub: P2 原因分布计算失败", exc_info=True)
        return None, "原因分布计算异常（已降级）", src
    if not entities:
        return None, "无建筑/作坊 ⇒ 原因分布不可定义（缺失≠0）", src
    return len(by_reason), None, {"原因数": len(by_reason), "已扫描实体": entities,
                                  "采样上限": max_scan, "扫描路数": seen_routes,
                                  "逐原因": by_reason, "drill": src}


def _d_funding_best(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**营运资金最佳候选到位率**（D 线 G-4 影子，只读）：候选池 ÷ 采购需求的最大值（夹 1.0）。

    值＝**最佳候选的到位率**；下钻给**逐候选到位率**与需求（服务 N1「钱从哪来」的裁定）。
    取不到 ⇒ None + reason（**缺失≠0**，不臆造）。
    """
    src = "core.domains.economy.owner_candidates_shadow:survey_owner_candidates"
    try:
        from core.domains.economy import owner_candidates_shadow as oc
        rep = oc.survey_owner_candidates(state)
    except Exception as e:                                  # noqa: BLE001
        log.warning("readout_hub: 营运资金候选盘点失败", exc_info=True)
        return None, f"营运资金盘点异常：{type(e).__name__}", src
    if not isinstance(rep, dict):
        return None, "盘点结果不可读（缺失≠0）", {"返回类型": type(rep).__name__, "drill": src}
    rows = rep.get("rows") or rep.get("candidates") or rep.get("items")
    if not isinstance(rows, list) or not rows:
        # 🔴 drill_down **必须是 dict**（M81/M124 两次踩：undefined 分支误传字符串）
        return None, "无候选行 ⇒ 到位率不可定义（缺失≠0）", {"返回键": sorted(rep.keys())[:12], "drill": src}
    pairs = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        v = r.get("procure_cover")
        if v is None:
            v = r.get("coverage")
        pairs.append((str(r.get("label") or r.get("key") or "?"), v,
                      r.get("wage_cover"), r.get("pool")))
    pairs = [(k, v, w, p) for (k, v, w, p) in pairs
             if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not pairs:
        return None, "候选到位率均不可读（缺失≠0，不臆造）", {"候选数": len(rows), "drill": src}
    pairs.sort(key=lambda t: -t[1])
    best = pairs[0]
    return (round(float(best[1]), 4), None,
            {"最佳候选": best[0],
             "逐候选到位率": {k: round(float(v), 4) for (k, v, _w, _p) in pairs},
             "逐候选工资到位率": {k: (None if w is None else round(float(w), 4))
                                 for (k, _v, w, _p) in pairs},
             "逐候选资金池": {k: p for (k, _v, _w, p) in pairs},
             "采购需求": (rep.get("procure_need") if isinstance(rep, dict) else None),
             "工资需求": (rep.get("wage_need") if isinstance(rep, dict) else None),
             "drill": src})


def _trade_line_status(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**主线 F 外贸：素材就绪度**（M140，只读·零数值）。

    值＝**齐备的素材项数**（政权进口表 / 海商 / 抽解商 / 水路源表）+ 纯函数可算证明；
    下钻给逐项条数、纯函数 dry 结果与 🔴 **真账缺口**（无逐笔容器）——**缺失≠0，不虚构外贸账**。
    """
    src = "core.domains.economy.trade_shadow（**纯函数影子，未接结算**）"
    try:
        from core.domains.economy import trade_shadow as ts
    except Exception as e:                                   # noqa: BLE001
        log.warning("readout_hub: 外贸模块不可读", exc_info=True)
        return None, f"外贸模块不可读：{type(e).__name__}", {"drill": src}
    detail: Dict[str, Any] = {}
    ready: List[str] = []
    for name in ("REGIME_IMPORTS", "SEA_TRADERS", "ABSTRACT_TRADERS", "ROUTE_WATERWAY"):
        v = getattr(ts, name, None)
        n = len(v) if hasattr(v, "__len__") else None
        detail[name] = n
        if v:
            ready.append(name)
    # 纯函数 dry 证明（**不触 state**）
    dry: Dict[str, Any] = {}
    for fn, args in (("land_freight", (1000, "近", "平川")),
                     ("sea_freight", (1000,)),
                     ("tax_split", (0.05,)),
                     ("condition_mult", (1.0,))):
        f = getattr(ts, fn, None)
        try:
            # 🔴 用「**未抛异常**」判定可算（真值判定会误报：如 `land_freight` 可能返回 0/空 dict）
            f(*args)
            dry[fn] = callable(f)
        except Exception:                                    # noqa: BLE001
            dry[fn] = False
    detail["纯函数可算"] = dry
    # 🔴 M180：**真账下钻**（主线 F 已接线 M179）——从 `state.trade_journal` 聚合（**只读**）
    try:
        j = getattr(state, "trade_journal", None) or []
        if isinstance(j, list) and j:
            per_route: Dict[str, float] = {}
            per_partner: Dict[str, float] = {}
            per_dim: Dict[str, float] = {}
            for leg in j:
                if not isinstance(leg, dict):
                    continue
                v = leg.get("goods_value")
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    continue
                per_route[str(leg.get("route"))] = per_route.get(str(leg.get("route")), 0.0) + float(v)
                per_partner[str(leg.get("partner"))] = per_partner.get(str(leg.get("partner")), 0.0) + float(v)
                per_dim[str(leg.get("dim"))] = per_dim.get(str(leg.get("dim")), 0.0) + float(v)
            detail["真账_笔数"] = len(j)
            detail["真账_货值合计"] = round(sum(per_dim.values()), 2)
            detail["真账_逐路货值"] = {k: round(v, 2) for k, v in
                                    sorted(per_route.items(), key=lambda kv: -kv[1])[:8]}
            detail["真账_逐政权货值"] = {k: round(v, 2) for k, v in
                                     sorted(per_partner.items(), key=lambda kv: -kv[1])[:8]}
            detail["真账_逐商品货值"] = {k: round(v, 2) for k, v in
                                     sorted(per_dim.items(), key=lambda kv: -kv[1])[:8]}
            detail["真账_来源"] = ("state.trade_journal（M176 容器 · M177 纯函数拆分 · **M179 接线**；"
                                 "**只记不二次入账**）")
        else:
            detail["真账_笔数"] = 0
            detail["真账_来源"] = ("`state.trade_journal` 为空 ⇒ 市舶未开"
                                 "（`state.maritime['open']`）或本局未产生外贸 ⇒ **不臆造外贸账**（缺失≠0）")
    except Exception:                                        # noqa: BLE001
        log.warning("readout_hub: 外贸真账下钻不可读（降级为仅素材就绪度）", exc_info=True)
    # ⚠️ M180 **更正**：M140 此处原写「**无逐笔容器**」——该描述在 M176/M179 之后**已过时**：
    # 逐笔容器（`trade_journal`）与接线均已落地 ⇒ 现可回答「哪一路、哪一货、跟谁、多少」。
    detail["真账现状"] = ("**逐笔真账已接线**（M176 容器 / M177 纯函数 / M179 接线）："
                        "可回答「哪一路、哪一货、跟谁、多少」；旧描述『无逐笔容器』**已作废**")
    detail["drill"] = src
    if not ready:
        return None, "外贸常量均不可读 ⇒ 素材就绪度不可定义（缺失≠0）", detail
    return len(ready), None, detail


def _fiscal_structure(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**财政结构：内帑/国库比**（M148，只读·零数值）。

    实测事实（M147）：内帑**持续增长**（1.0M → 3.85M → 5.93M，0/6/12 月）而国库**长期低位**
    （5.0M → 8.2万 → 12.4万）⇒ 「**钱在沉淀进内帑**」。本读数把该结构做成可复查数字。

    ⚠️ 国库 ≤ 0 ⇒ **比值不可定义**（除零）⇒ `None` + reason（**缺失≠0**，不返回 0/∞）。
    """
    src = "state.treasury / state.imperial_treasury（既有单点，无旁路）"
    try:
        t = getattr(state, "treasury", None)
        i = getattr(state, "imperial_treasury", None)
    except Exception as e:                                   # noqa: BLE001
        log.warning("readout_hub: 财政结构不可读", exc_info=True)
        return None, f"财政槽不可读：{type(e).__name__}", {"drill": src}
    detail = {"国库": t, "内帑": i, "drill": src}
    if not isinstance(t, (int, float)) or not isinstance(i, (int, float)):
        return None, "国库或内帑不可读 ⇒ 比值不可定义（缺失≠0）", detail
    if t <= 0:
        return None, f"国库为 {t}（≤0）⇒ 比值不可定义（**不返回 ∞/0**）", detail
    ratio = round(float(i) / float(t), 4)
    detail["内帑/国库"] = ratio
    detail["注"] = ("结构性事实（M147 实测）：内帑 0/6/12 月 = 1.0M/3.85M/5.93M（**持续增长**），"
                    "国库 = 5.0M/8.2万/12.4万（**长期低位**）⇒ 钱在沉淀进内帑")
    return ratio, None, detail


def _tax_scope_contrast(state) -> Tuple[Optional[Any], Optional[str], Any]:
    """**税收口径对照**（M152，只读·零数值）：`tax_breakdown`（4 目）vs **全税收**（含盐课·二税折色）。

    🔴 动因（M151 取证）：`tax_breakdown` **只覆盖 4 目**，而月度应征是**五科目**
    ⇒ 拿它当「全部税收」会**漏掉两项大额**（代码注释记录过历史误判：旧『名义岁入』>100% 正因分母缺这两项）。
    本读数把两套口径**并列**出来，值＝**差额（全税收 − tax_breakdown）**；不可读 ⇒ `None` + reason。
    """
    src = "state.tax_breakdown + state.tax_base_summary()（既有读口）"
    tb = getattr(state, "tax_breakdown", None) or {}
    if not isinstance(tb, dict):
        return None, "tax_breakdown 不可读（缺失≠0）", {"drill": src}
    base_sum = sum(float(v) for v in tb.values() if isinstance(v, (int, float)))
    detail: Dict[str, Any] = {"tax_breakdown_4目": {k: tb.get(k) for k in
                                                 ("commerce", "poll", "maritime", "official_service")},
                              "tax_breakdown_合计": base_sum, "drill": src}
    extra: Dict[str, Any] = {}
    missing: List[str] = []
    # 盐课：**公开方法**（M154 核实：`calc_salt_coin(arrival=1.0) -> float`，口径=**月盐课**
    # = Σ盐产量 × SALT_PROFIT_PER_JIN × price_factor × arrival × (人口/SALT_POP_BASE)）
    try:
        salt = state.calc_salt_coin()
        if isinstance(salt, (int, float)) and not isinstance(salt, bool):
            extra["calc_salt_coin（月盐课）"] = round(float(salt), 2)
    except Exception:                                        # noqa: BLE001
        log.warning("readout_hub: 盐课（calc_salt_coin）不可读", exc_info=True)
        missing.append("盐课 calc_salt_coin 调用异常")
    # 二税折色：**已有读口**——`statistics["land_tax_assessed"]`（应征口径；由 `_settle_land_tax_color`
    # 内部落表 ⇒ **读字典无副作用**）。⚠️ 更正 M155：此前说"无公开读口"**不准确**（我只是没查到 stats）
    try:
        st = getattr(state, "statistics", None) or {}
        lt = st.get("land_tax_assessed")
        if isinstance(lt, (int, float)) and not isinstance(lt, bool):
            extra["land_tax_assessed（二税折色·应征）"] = round(float(lt), 2)
        else:
            missing.append("二税折色（statistics 未含 land_tax_assessed）")
    except Exception:                                        # noqa: BLE001
        log.warning("readout_hub: 二税折色（statistics）不可读", exc_info=True)
        missing.append("二税折色（statistics 读取异常）")
    full = base_sum + sum(float(v) for v in extra.values()) if extra else None
    detail["额外科目（已可读）"] = extra or None
    detail["额外科目（仍缺读口）"] = missing or None
    detail["partial"] = bool(missing)                        # 🔴 部分口径：盐课有、二税折色缺
    detail["全税收口径合计（可读部分）"] = full
    detail["警示"] = ("**两套口径不可混用**：`tax_breakdown` 仅 4 目；任何「税收占比/到账率」"
                      "结论必须注明用哪套（M151 取证；历史误判见 `game_state_econ` 注释）。"
                      "另：**二税折色有地方分成**（`statistics.land_tax_local` 留州），"
                      "而 4 目**无**（M156 更正 M149/M150）")
    # 🔴 M157：**三率三分（上供/留州/侵渔）**归属落点（M156 实测；只在 statistics，读字典无副作用）
    try:
        st2 = getattr(state, "statistics", None) or {}
        split = {k: st2.get(k) for k in ("land_tax_assessed", "land_tax_collected",
                                         "land_tax_central", "land_tax_local",
                                         "land_tax_diverted", "land_tax_required")}
        detail["二税折色·三率三分"] = {k: v for k, v in split.items() if v is not None} or None
        detail["归属落点"] = {"上供 → 中央": st2.get("land_tax_central"),
                            "留州 → **地方**（地方确有分成）": st2.get("land_tax_local"),
                            "侵渔 → 吏（账实落差）": st2.get("land_tax_diverted")}
    except Exception:                                        # noqa: BLE001
        log.warning("readout_hub: 三率三分不可读（不影响主值）", exc_info=True)
    if full is None:
        return None, "全税收口径不可读（额外科目取不到）⇒ 差额不可定义（缺失≠0）", detail
    return round(float(full) - base_sum, 2), None, detail


#: 读数注册表（**顺序即展示顺序**）。 `fn` 返回 `(value|None, reason|None, drill_down)`。
READOUTS: Tuple[Dict[str, Any], ...] = (
    {"key": "money_total", "label": "货币总量（M_ALL）", "unit": "贯", "fn": _money_total,
     "source": "core.foundation.ledger.money:m_all"},
    {"key": "money_residual", "label": "货币恒等式残差（M_ALL − Σ账户）", "unit": "贯",
     "fn": _money_residual, "source": "core.domains.economy.stock_identity:money_identity"},
    {"key": "stock_dims", "label": "库存可读维数", "unit": "维", "fn": _stock_readable_dims,
     "source": "core.domains.economy.stock_identity:stock_snapshot"},
    {"key": "flow_dim_count", "label": "流量账已登记维数（全月桶）", "unit": "维",
     "fn": _flow_dim_count, "source": "core.domains.economy.stock_flow:coverage"},
    {"key": "seat_goods_consistent", "label": "州府商品真账↔镜像一致", "unit": "是/否",
     "fn": _seat_goods_consistency, "source": "core.domains.economy.seat_goods_readout:seat_consistency"},
    {"key": "workshop_undefined", "label": "工坊资金未定义数（无货主）", "unit": "座",
     "fn": _workshop_undefined, "source": "core.domains.economy.workshop_fund_shadow:survey_workshop_fund_shadow"},
    {"key": "livelihood_computable", "label": "家计可计算 POP 行数", "unit": "行",
     "fn": _livelihood_computable, "source": "core.domains.economy.livelihood_shadow:survey_livelihood_shadow"},
    {"key": "seat_market_pairs", "label": "有货的（治所×商品）对数", "unit": "对",
     "fn": _seat_market_pairs, "source": "core.domains.economy.seat_market_shadow:survey_seat_market_shadow"},
    {"key": "labor_tight_routes", "label": "缺工路数（岗位闸门乘数<1）", "unit": "路",
     "fn": _labor_tight_routes, "source": "core.domains.economy.wage_gate_readout:survey_wage_gate"},
    {"key": "pilot_chain_gap", "label": "P1 试点链条缺口（绸）", "unit": "匹",
     "fn": _pilot_chain_gap, "source": "core.domains.economy.p1_pilot_chain:survey_pilot_chain"},
    {"key": "jobs_capacity", "label": "岗位容量合计（建筑岗位）", "unit": "岗",
     "fn": _jobs_capacity, "source": "core.domains.economy.jobs_readout:survey_jobs"},
    {"key": "pilot_bottleneck", "label": "P1 试点主瓶颈（绸）", "unit": "类",
     "fn": _pilot_bottleneck, "source": "core.domains.economy.p1_pilot_chain:survey_diagnosis"},
    {"key": "p2_readiness", "label": "P2 字段已就绪数（共 14 项）", "unit": "项",
     "fn": _p2_readiness, "source": "core.domains.economy.entity_projection:survey_entity_projection"},
    {"key": "building_owned", "label": "建筑归属已登记率", "unit": "比",
     "fn": _building_owned, "source": "core.domains.economy.building_owner:survey_building_owners"},
    {"key": "workshop_readiness", "label": "作坊（经营记录）字段已就绪数（共 14 项）", "unit": "项",
     "fn": _workshop_readiness, "source": "core.domains.economy.entity_projection:survey_workshop_projection"},
    {"key": "p2_gaps", "label": "P2 未就绪原因条数（去重）", "unit": "条",
     "fn": _p2_gaps, "source": "core.domains.economy.entity_projection（建筑+作坊）"},
    {"key": "d_funding_best", "label": "营运资金最佳候选到位率（D 线影子）", "unit": "比",
     "fn": _d_funding_best, "source": "core.domains.economy.owner_candidates_shadow:survey_owner_candidates"},
    {"key": "trade_line_status", "label": "外贸素材就绪项数（主线 F）", "unit": "项",
     "fn": _trade_line_status, "source": "core.domains.economy.trade_shadow（纯函数影子）"},
    {"key": "fiscal_structure", "label": "财政结构：内帑/国库比", "unit": "倍",
     "fn": _fiscal_structure, "source": "state.treasury / state.imperial_treasury"},
    {"key": "tax_scope_contrast", "label": "税收口径差额（全口径 − tax_breakdown 4 目）", "unit": "贯",
     "fn": _tax_scope_contrast, "source": "state.tax_breakdown + state.tax_base_summary()"},
)


def collect(state, keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """汇总读数：每项 `{label, value|None, display, unit, source, drill_down, reason}`。

    `display`：有值 ⇒ 值的字符串；**不可读 ⇒ `"undefined"`（绝不显示 0）**。
    """
    wanted = set(keys) if keys else None
    rows: Dict[str, Any] = {}
    ok = undefined = 0
    for spec in READOUTS:
        if wanted is not None and spec["key"] not in wanted:
            continue
        try:
            value, reason, drill = spec["fn"](state)
        except Exception as e:                              # noqa: BLE001
            # 🔴 单个读数失败**不拖垮整表**；但**不得静默**（项目禁区）
            log.warning("readout_hub: 读数 %s 计算失败", spec["key"], exc_info=True)
            value, reason, drill = None, f"读数计算失败：{type(e).__name__}: {e}", ""
        if value is None:
            undefined += 1
        else:
            ok += 1
        rows[spec["key"]] = {
            "label": spec["label"], "unit": spec["unit"],
            "value": value,
            "display": "undefined" if value is None else str(value),
            "source": spec["source"],
            # 🔴 **单点归一化**：`drill_down` 只允许 dict —— 旧读数（M54 期 9 个）返回的是
            # 路径字符串，这里统一收进 `note`，避免"同一契约两种形状"（M81/M124/M125 三次踩）
            "drill_down": (drill if isinstance(drill, dict) else
                           ({"note": drill, "source": spec["source"]} if drill
                            else {"source": spec["source"]})),
            "reason": None if value is not None else (reason or "不可读（缺失≠0）"),
        }
    return {"schema_version": SCHEMA_VERSION, "readouts": rows,
            "ok_count": ok, "undefined_count": undefined,
            "frontend_wired": False,
            "note": "只读索引；**前端面板未接**（本批只做后端）；缺失一律 undefined，不显示 0"}


def index(state) -> List[Dict[str, Any]]:
    """列表形态（便于逐项遍历/下钻）。"""
    rep = collect(state)
    return [{"key": k, **v} for k, v in rep["readouts"].items()]


def undefined_summary(state) -> Dict[str, Any]:
    """只列**不可读**的读数与原因（给"读数为 undefined 时该怎么办"用）。"""
    rep = collect(state)
    bad = {k: v["reason"] for k, v in rep["readouts"].items() if v["value"] is None}
    return {"undefined": bad, "count": len(bad), "total": len(rep["readouts"])}
