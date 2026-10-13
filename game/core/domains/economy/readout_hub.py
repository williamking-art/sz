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
    drill = {"已就绪字段": ready, "逐字段率": ratio, "建筑数": rep.get("buildings"), "drill": src}
    return len(ready), None, drill


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
            "drill_down": drill or spec["source"],
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
