# -*- coding: utf-8 -*-
"""圣旨行动闭环 · **主干提交**（规格 `specs/decree-action-chain` 任务 2 的跨提交幂等 ＋ 任务 3/4 的落点）。

分层（勿混）：
  · `core/decree_plan.py`  —— **只校验**（不建工程、不改账）；
  · `core/plan_commit.py`  —— **只提交**：把已通过校验的动作落到 `state.projects`／动态蓝图注册表，
    并维护 `state.plan_actions`（action id ↔ 工程 的登记表）。

**跨提交幂等**（本条补上的缺口）：同一 `action_id` 此前已提交过 → 本次**拒绝重复立项**，
理由与首次提交的工程 id 一并回报。此前只有"id 稳定 ＋ 同计划内去重"，
缺少"跨提交"这一层，重试仍可能建出第二份工程。

**只通过既有落点落地**：营建动作交 `construction.propose_projects`（同一 `state.projects`
台账、同一五态状态机）；带 `blueprint_proposal` 的先经动态蓝图校验并注册，再立项。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["PLAN_ACTION_SCHEMA_VERSION", "existing_action_ids", "commit_plan",
           "action_registry_of"]

#: `state.plan_actions` 的 schema 版本（随存档持久化，供读档迁移）
PLAN_ACTION_SCHEMA_VERSION = 1


def action_registry_of(state) -> Dict[str, Any]:
    """取（必要时初始化）action 登记表。**非 dict 一律重建**（坏档不阻断）。"""
    reg = getattr(state, "plan_actions", None)
    if not isinstance(reg, dict):
        reg = {}
        state.plan_actions = reg
    return reg


def existing_action_ids(state) -> set:
    """本局**已提交**过的 action id 集合（跨提交幂等的依据）。"""
    return set(action_registry_of(state).keys())


def commit_plan(state, plan: Any, *, route: Optional[str] = None) -> Dict[str, Any]:
    """校验并**提交**一份行动计划；返回逐项结果（含跨提交幂等裁决）。

    参数 `route`：可选，把整批动作强制落到该路（面板按路拟旨时用）；
    动作自带 `location_id` 时以动作为准。

    返回：
      `{ok, schema_version, decree_id, results[], summary, validation}`
    `results[]` 每项：`{id, status, kind, title, location_id, pid?, blueprint_key?, errors?}`；
    `status` 取值：`submitted` / `already_submitted` / `registered_only` / 校验器给出的
    `rejected`/`unsupported`/`unresolved`/`duplicate`。

    **幂等**：同一 action id 第二次提交 → `already_submitted`，**不重复立项**。
    """
    from core.decree_plan import DECREE_PLAN_SCHEMA_VERSION, validate_plan
    out: Dict[str, Any] = {
        "ok": False,
        "schema_version": DECREE_PLAN_SCHEMA_VERSION,
        "decree_id": "",
        "results": [],
        "summary": {},
        "validation": None,
    }
    v = validate_plan(plan, state=state)
    out["validation"] = {"ok": v.get("ok"), "summary": v.get("summary"),
                         "unresolved": v.get("unresolved")}
    out["decree_id"] = v.get("decree_id", "")
    if not v.get("ok"):
        # 校验没过就**不提交任何东西**（拒绝式；逐项原因在 validation 里）
        out["summary"] = {"reason": "计划未通过校验，未提交任何动作",
                          **({"detail": v["summary"].get("reason")}
                             if isinstance(v.get("summary"), dict)
                             and v["summary"].get("reason") else {})}
        out["results"] = [{"id": a.get("id"), "status": a.get("status"),
                           "kind": a.get("kind"), "title": a.get("title"),
                           "location_id": a.get("location_id"),
                           "errors": a.get("reasons")} for a in v.get("actions", [])]
        return out

    reg = action_registry_of(state)
    results: List[Dict[str, Any]] = []
    for a in v.get("actions", []):
        aid = str(a.get("id") or "")
        base = {"id": aid, "kind": a.get("kind"), "title": a.get("title"),
                "location_id": a.get("location_id")}
        st = a.get("status")
        if st != "proposed":
            # 未通过的动作**原样回报**（不尝试落地、不静默跳过）
            results.append({**base, "status": st, "errors": a.get("reasons")})
            continue
        if aid in reg:
            prev = reg.get(aid) or {}
            results.append({**base, "status": "already_submitted",
                            "pid": prev.get("pid"),
                            "errors": [f"该动作已于第 {prev.get('turn', '?')} 回合提交过"
                                       f"（工程 {prev.get('pid', '无')}），不重复立项"]})
            continue

        loc = str(route or a.get("location_id") or "")
        bp_key = None
        # ---- 营建：先注册动态蓝图（若有提案），再立项 ----
        if a.get("kind") == "营建":
            prop = a.get("blueprint_proposal")
            if isinstance(prop, dict):
                from core.blueprint_dynamic import register_dynamic_blueprint
                reg_res = register_dynamic_blueprint(state, prop)
                if not reg_res.get("ok"):
                    results.append({**base, "status": "rejected",
                                    "errors": reg_res.get("errors") or ["蓝图注册失败"]})
                    continue
                bp_key = reg_res.get("key")
            from core.construction import propose_projects
            names = [prop["name"]] if isinstance(prop, dict) else []
            if not names:
                results.append({**base, "status": "registered_only",
                                "blueprint_key": bp_key,
                                "errors": ["营建动作未给蓝图提案，仅登记、不立项"]})
                _mark(reg, aid, None, state, loc)
                continue
            pr = propose_projects(state, [loc], names[0], bp_key)
            item = (pr.get("results") or [{}])[0]
            if not item.get("ok"):
                results.append({**base, "status": "rejected",
                                "blueprint_key": bp_key,
                                "errors": item.get("errors") or ["立项失败"]})
                continue
            _mark(reg, aid, item.get("pid"), state, loc)
            results.append({**base, "status": "submitted", "pid": item.get("pid"),
                            "blueprint_key": bp_key})
            continue

        # ---- 非营建：本模块**不落数值**（军政/财政/民生/制度由各自既有通道处理）----
        # 只做登记，使其获得跨提交幂等身份；数值落地仍由调用方按既有口径执行。
        _mark(reg, aid, None, state, loc)
        results.append({**base, "status": "registered_only",
                        "errors": ["非营建动作已登记（幂等生效），数值落地由其既有通道执行"]})

    n_sub = sum(1 for r in results if r["status"] == "submitted")
    n_reg = sum(1 for r in results if r["status"] == "registered_only")
    n_dup = sum(1 for r in results if r["status"] == "already_submitted")
    n_bad = len(results) - n_sub - n_reg - n_dup
    out["ok"] = (n_sub + n_reg) > 0
    out["results"] = results
    out["summary"] = {"total": len(results), "submitted": n_sub,
                      "registered_only": n_reg, "already_submitted": n_dup,
                      "failed": n_bad}
    return out


def _mark(reg: Dict[str, Any], aid: str, pid: Optional[str], state, route: str) -> None:
    """登记 action id →（工程 id／回合／落点）。**只在成功落点后调用**。"""
    reg[aid] = {
        "schema_version": PLAN_ACTION_SCHEMA_VERSION,
        "pid": pid,
        "turn": int(getattr(state, "turn", 0) or 0),
        "route": str(route or ""),
    }
