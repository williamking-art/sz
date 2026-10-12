# -*- coding: utf-8 -*-
"""建筑经营的「投入/工资/劳力」闸门**只读投影**（P2 第一条） —— M49。

P2 要求：「建筑**不因等级存在自动满产**；缺投入/工资/许可时**降产或停产**」。
宋境现状（2026-10-13 核实）：**已有缺料/缺粮降产**（`settlement_econ._settle_workshops`
的 `_input_scale`），**没有工资腿**（`building_jobs.pay_wages_from_revenue` 唯一调用方仍是
外邦路径）。本模块先给**可核对的读数**，不做数值改动（Jev choose C 0.561）。

口径
----
* **只读**：不写任何 state（用例深比较）。
* **岗位需求**：`prefectures[路]["buildings"]`（等级形态）× `building_jobs.song_job_cfg()`
  的 `JOBS_PER_LEVEL`——**复用既有单点**，不另立岗位表。
* **劳力供给**：`prefectures[路]["pops"][类]["size"]`（路级是治所真账的派生镜像 ✅ 读镜像是对的）。
* **缺工上界投影**：`产出乘数上界 = min(1, 供给 / 需求)`——口径写明是**未接线的上界**
  （真实接线还要看"缺工是否真导致降产"的玩法裁定；本模块只把量算清楚）。
* **工资需求与到位率**：工价取 `song_job_cfg()` 的 `WAGE_RATE`（若**缺失 ⇒ `None`**，
  并给 reason——**不臆造工价**）；付款池**并列三种口径**（国库 / 本路工匠 / 本路士绅+商人），
  **不给唯一答案**：口径未裁，读数只把选项摆出来。
* **缺失 ≠ 0**：无 `buildings` / 无岗位表条目 / 池不可读 ⇒ `None` + reason。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

__all__ = [
    "SCHEMA_VERSION", "PAYER_POOLS", "route_job_demand", "route_job_demand_detailed",
    "route_labor_supply", "wage_rate_for", "payer_pools", "project_route_gate",
    "survey_wage_gate",
]

#: 付款池候选（**并列展示，不预选**；口径未裁）
PAYER_POOLS = (
    ("treasury", "国库", None),
    ("artisan", "本路工匠", ("工匠",)),
    ("gentry_merchant", "本路士绅+商人", ("士绅", "商人")),
)


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _pdata(state, route: str) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    p = prefs.get(route)
    return p if isinstance(p, dict) else None


def _jobs_per_level() -> Optional[Dict[str, Any]]:
    try:
        from core.building_jobs import song_job_cfg
        cfg = song_job_cfg() or {}
        jpl = cfg.get("JOBS_PER_LEVEL")
        return jpl if isinstance(jpl, dict) else None
    except Exception:                                       # noqa: BLE001
        log.warning("wage_gate_readout: song_job_cfg 不可用", exc_info=True)
        return None


def wage_rate_for(building: str, regime: Optional[str] = None) -> Optional[float]:
    """**既有工价单点**：`song_job_cfg()['WAGE_RATE'][政权][建筑]`，缺政权档 ⇒ 回落 `default`。

    实测（2026-10-13）：该表**只登记外邦政权与 `default`**（宋侧无专门档）⇒ 宋境作坊
    按 `default` 兜底（工坊 1.5 贯/岗/月）。**两层都缺 ⇒ `None`**（不臆造工价）。
    """
    try:
        from core.building_jobs import song_job_cfg
        table = (song_job_cfg() or {}).get("WAGE_RATE")
        if not isinstance(table, dict):
            return None
        tiers = []
        if regime and isinstance(table.get(regime), dict):
            tiers.append(table[regime])
        if isinstance(table.get("default"), dict):
            tiers.append(table["default"])
        for tier in tiers:
            v = _num(tier.get(building))
            if v is not None:
                return v
        return None
    except Exception:                                       # noqa: BLE001
        return None


def _jobs_spec(building: str):
    """岗位表条目 → `("positions", {职位: 每级})` / `("total", 每级总岗数)` / `None`。

    🔴 **实测两种形态并存**（2026-10-13）：`song_job_cfg()['JOBS_PER_LEVEL']` 的值是
    **整数**（每级总岗数，如 `'工坊': 160`），而模块常量 `SONG_JOBS_PER_LEVEL` 是
    `{职位: 数}`（如 `'工坊': {'工匠': 160}`）。只认一种就会在真实局里**全部跳过**（踩过）。
    """
    jpl = _jobs_per_level()
    if jpl is None:
        return None
    spec = jpl.get(building)
    if isinstance(spec, dict) and spec:
        per = {str(k): v for k, v in spec.items() if _num(v)}
        if per:
            return ("positions", per)
        return None
    n = _num(spec)
    if n is not None and n > 0:
        return ("total", n)
    return None


def _worker_class_of(building: str) -> Optional[str]:
    """建筑 → 岗位所属 POP 类（既有表：`BUILDING_WORKER` / `SONG_POSITION_CLASS`）；不可知 ⇒ None。"""
    try:
        from core.building_jobs import song_job_cfg
        cfg = song_job_cfg() or {}
        bw = cfg.get("BUILDING_WORKER")
        if isinstance(bw, dict):
            v = bw.get(building)
            if isinstance(v, str):
                return v
    except Exception:                                       # noqa: BLE001
        pass
    return None


def route_job_demand_detailed(state, route: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """该路**分建筑**岗位需求 `{建筑: {jobs, positions, class, basis}}`；不可读 ⇒ `None`。"""
    p = _pdata(state, route)
    if p is None:
        return None
    bld = p.get("buildings")
    if not isinstance(bld, dict):
        return None
    if _jobs_per_level() is None:
        return None
    out: Dict[str, Dict[str, Any]] = {}
    for btype, entry in bld.items():
        spec = _jobs_spec(str(btype))
        if spec is None:
            continue
        lvn = _num(entry.get("lv") if isinstance(entry, dict) else entry)
        if lvn is None or lvn <= 0:
            continue
        kind, payload = spec
        if kind == "positions":
            positions = {pos: int(n * lvn) for pos, n in payload.items()}
            jobs = int(sum(positions.values()))
        else:
            positions = None
            jobs = int(payload * lvn)
        if jobs > 0:
            out[str(btype)] = {"jobs": jobs, "positions": positions,
                               "class": _worker_class_of(str(btype)), "basis": kind}
    return out


def route_job_demand(state, route: str) -> Optional[Dict[str, int]]:
    """该路**岗位需求** `{职位或阶层: 岗数}`（真实局多为"每级总岗数"形态 ⇒ 键为**建筑名**）。"""
    detailed = route_job_demand_detailed(state, route)
    if detailed is None:
        return None
    out: Dict[str, int] = {}
    for btype, d in detailed.items():
        if isinstance(d.get("positions"), dict):
            for pos, n in d["positions"].items():
                out[pos] = out.get(pos, 0) + int(n)
        else:
            key = d.get("class") or btype
            out[key] = out.get(key, 0) + int(d.get("jobs") or 0)
    return out


def route_labor_supply(state, route: str) -> Optional[Dict[str, int]]:
    """该路**劳力供给** `{职位/阶层: size}`（路级镜像＝治所真账派生 ✅ 读镜像是对的）。"""
    p = _pdata(state, route)
    if p is None:
        return None
    pops = p.get("pops")
    if not isinstance(pops, dict):
        return None
    out: Dict[str, int] = {}
    for cls, row in pops.items():
        n = _num((row or {}).get("size") if isinstance(row, dict) else None)
        if n is not None:
            out[str(cls)] = int(n)
    return out


def payer_pools(state, route: str) -> Dict[str, Optional[int]]:
    """三种付款池余额并列（**不预选**）：国库 / 本路工匠 / 本路士绅+商人。"""
    out: Dict[str, Optional[int]] = {}
    tre = _num(getattr(state, "treasury", None))
    out["treasury"] = None if tre is None else int(tre)
    p = _pdata(state, route)
    pops = (p or {}).get("pops") if isinstance(p, dict) else None
    for key, _label, classes in PAYER_POOLS:
        if classes is None:
            continue
        if not isinstance(pops, dict):
            out[key] = None
            continue
        tot = 0
        readable = False
        for cls in classes:
            row = pops.get(cls)
            w = _num(row.get("wealth") if isinstance(row, dict) else None)
            if w is not None:
                tot += int(w)
                readable = True
        out[key] = tot if readable else None
    return out


def project_route_gate(state, route: str) -> Dict[str, Any]:
    """该路闸门投影：需求 / 供给 / **缺工上界乘数** / 工价 / 各池与**到位率**（并列）。"""
    demand = route_job_demand(state, route)
    detailed = route_job_demand_detailed(state, route)
    supply = route_labor_supply(state, route)
    pools = payer_pools(state, route)
    # 工资需求＝Σ(建筑岗数 × 该建筑工价)；任一建筑工价缺失 ⇒ **该项不可算**（并列 reason）
    wage_need = None
    wage_detail: Dict[str, Any] = {}
    if detailed:
        tot = 0
        ok = True
        for btype, d in detailed.items():
            rate = wage_rate_for(btype)
            jobs = int(d.get("jobs") or 0)
            wage_detail[btype] = {"jobs": jobs, "rate": rate, "basis": d.get("basis")}
            if rate is None:
                ok = False
                continue
            tot += int(jobs * rate)
        wage_need = tot if ok else None
    reasons = []
    if demand is None:
        reasons.append("无 buildings 或无岗位表（需求不可读）")
    if supply is None:
        reasons.append("无 pops（供给不可读）")
    if detailed and wage_need is None:
        reasons.append("有建筑的工价单点缺失（WAGE_RATE[政权/建筑] 与 default 都没有）"
                       "⇒ 工资需求不可算，不臆造")
    # 缺工上界：需求职位 → 对应 POP 类（沿用 SONG_POSITION_CLASS 的既定映射）
    mult = None
    per_pos: Dict[str, Any] = {}
    if demand is not None and supply is not None:
        try:
            from core.building_jobs import SONG_POSITION_CLASS as _spc
        except Exception:                                   # noqa: BLE001
            _spc = {}
        ratios = []
        for pos, need in demand.items():
            if need <= 0:
                continue
            cls = (_spc or {}).get(pos, pos)
            have = supply.get(cls)
            r = None if have is None else min(1.0, float(have) / float(need))
            per_pos[pos] = {"need": need, "class": cls, "have": have, "ratio": r}
            if r is not None:
                ratios.append(r)
        mult = min(ratios) if ratios else None                # 最短板（与 _input_scale 同手法）
    cover = {}
    for key, _label, _classes in PAYER_POOLS:
        bal = pools.get(key)
        cover[key] = (None if (bal is None or wage_need is None or wage_need <= 0)
                      else min(1.0, bal / float(wage_need)))
    return {"route": route, "job_demand": demand, "labor_supply": supply,
            "per_position": per_pos, "labor_multiplier_upper_bound": mult,
            "wage_detail": wage_detail, "wage_need": wage_need, "pools": pools,
            "cover_by_pool": cover, "reasons": reasons}


def survey_wage_gate(state) -> Dict[str, Any]:
    """全局投影：逐路闸门 + 汇总（**零写入**）。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"schema_version": SCHEMA_VERSION, "routes": 0, "per_route": {},
                "reason": "无 prefectures（缺失≠0）"}
    per = {r: project_route_gate(state, r) for r in prefs}
    with_bld = [r for r, v in per.items() if v["job_demand"]]
    tight = [(r, v["labor_multiplier_upper_bound"]) for r, v in per.items()
             if v["labor_multiplier_upper_bound"] is not None
             and v["labor_multiplier_upper_bound"] < 1.0]
    return {"schema_version": SCHEMA_VERSION, "routes": len(per),
            "routes_with_jobs": len(with_bld),
            "routes_labor_tight": sorted(tight, key=lambda kv: kv[1])[:10],
            "wage_source": "song_job_cfg.WAGE_RATE[政权|default][建筑]",
            "per_route": per}
