# -*- coding: utf-8 -*-
"""宋祚 · 蓝图前置校验（core/construction.py）—— **只读纯函数**

定位（2026-09-19 用户指正后调整）：**不是**营建通道。营建（建筑从蓝图到落地的
"扣费 + 落等级"）应走**既有工程系统**（`state.projects` + `_settle_projects` 五态状态机）
与统一立项端口（`core.asset_context`）。

本模块只回答一个问题：**这座蓝图此刻能不能在这条路开工**，供工程立项/面板/AI 共用：
- 蓝图登记（`BUILDING_BLUEPRINTS` 优先，回落 `BUILDING_STD`）
- 科技前置（`need_node` 是否已解锁）
- **地利前置**（`requires_region` vs 该路路型）—— 仿明末 `requires_region_tags`
- 造价可支（国库）

**不含任何写操作**：不扣费、不写 `prefectures[*]["buildings"]`、不碰 `state.projects`。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from content.data import (
    BUILDING_BLUEPRINTS, BUILDING_COST_GROWTH, BUILDING_STD,
    blueprint_region_ok,
)
from core.foundation.common.numeric import parse_number as _num

log = logging.getLogger("construction")

__all__ = ["resolve_blueprint", "blueprint_cost", "can_build", "propose_project",
           "propose_projects"]


def resolve_blueprint(name: str, key: Optional[str] = None,
                      state=None) -> Optional[Dict[str, Any]]:
    """按**蓝图键**或**中文名**解析蓝图；未登记 None。

    查找顺序（规格任务 3）：
      **本局存档的动态蓝图** → 科技蓝图 `BUILDING_BLUEPRINTS` → 政府建筑 `BUILDING_STD`。

    `state` 为 None 时**跳过**动态蓝图（保持既有调用方行为不变；静态语义不变）。
    动态蓝图与静态蓝图返回**同一形状**的 dict，故下游 `can_build` / `propose_project` /
    五态状态机 / 完工落成**无需分支**。
    """
    # ---- 1) 存档内动态蓝图优先（本局特有的旨意产物）----
    if state is not None:
        try:
            from core.blueprint_dynamic import resolve_dynamic_blueprint
            dyn = resolve_dynamic_blueprint(state, name, key)
            if dyn is not None:
                return dyn
        except Exception:  # noqa: BLE001 — 动态蓝图不可用时不得阻断静态解析
            log.warning("[蓝图] 动态蓝图解析失败，回落静态表", exc_info=True)

    # ---- 2) 科技蓝图（静态）----
    k = str(key or "").strip()
    if k and k in BUILDING_BLUEPRINTS:
        bp = dict(BUILDING_BLUEPRINTS[k])
        bp.setdefault("_key", k)
        bp.setdefault("_name", bp.get("name", k))
        return bp
    n = str(name or "").strip()
    if not n:
        return None
    for k2, bp2 in BUILDING_BLUEPRINTS.items():
        if str(bp2.get("name")) == n:
            out = dict(bp2)
            out.setdefault("_key", k2)
            out.setdefault("_name", n)
            return out
    # ---- 3) 政府建筑（静态）----
    if n in BUILDING_STD:
        out = dict(BUILDING_STD[n])
        out.setdefault("_key", n)
        out.setdefault("_name", n)
        return out
    return None


def blueprint_cost(bp: Dict[str, Any], levels: int = 1) -> int:
    """造价（贯）：基础建筑/动态蓝图按 `base_cost` × 等级增长；科技蓝图取 `cost.silver`。

    动态蓝图走**同一口径**：其 `cost.silver` 即 base_cost，逐级 ×`BUILDING_COST_GROWTH`。
    """
    lv = max(1, int(levels or 1))
    if bp.get("_dynamic"):
        base = float((bp.get("cost") or {}).get("silver", 0) or 0)
        return int(sum(base * (BUILDING_COST_GROWTH ** i) for i in range(lv)))
    if "base_cost" in bp:
        base = float(bp.get("base_cost", 0) or 0)
        return int(sum(base * (BUILDING_COST_GROWTH ** i) for i in range(lv)))
    return int(_num((bp.get("cost") or {}).get("silver"), 0.0)) * lv


def _region_ok(state, p: Dict[str, Any], bp: Dict[str, Any]) -> Tuple[bool, str]:
    """地利前置校验（**动态蓝图必须单独走这里**）。

    ⚠️ 坑：静态用的 `blueprint_region_ok(route_type, key)` 只查 `BUILDING_BLUEPRINTS`，
    动态蓝图的 key 不在其中 → 它会**返回 True（处处可建）**，从而把动态蓝图声明的
    `requires_region` **静默绕过**。故此处对动态蓝图直接按其自身声明判定。
    """
    need = bp.get("requires_region") or ()
    if bp.get("_dynamic"):
        if not need:
            return True, ""
        t = str(p.get("type") or "")
        ok = any(str(n) in t for n in need)
        return (ok, "" if ok else
                f"地利不合：该蓝图须 {('/'.join(map(str, need)))}，"
                f"而 {p.get('type')} 为「{p.get('type')}」")
    if not blueprint_region_ok(p.get("type"), bp.get("_key") or ""):
        need2 = bp.get("requires_region") or ()
        return False, (f"地利不合：该蓝图须 {('/'.join(map(str, need2)))}，"
                       f"而该路为「{p.get('type')}」")
    return True, ""


def can_build(state, route: str, name: str,
              key: Optional[str] = None) -> Tuple[bool, List[str]]:
    """营建前置校验（**只读**）；返回 `(可否, 原因列表)`。

    依次检查：蓝图登记 / 路存在 / 科技前置未解锁 / **地利不合** / 国库不足。
    调用方（工程立项 / 面板 / AI）据返回值决定是否允许开工，**不得跳过本校验**。
    """
    errs: List[str] = []
    bp = resolve_blueprint(name, key, state)
    if bp is None:
        return False, [f"蓝图未登记：{name or key}（无图纸可依，不得静默开工）"]
    prefs = getattr(state, "prefectures", None) or {}
    p = prefs.get(str(route))
    if not isinstance(p, dict):
        return False, [f"路不存在：{route}"]

    need_node = bp.get("need_node")
    if need_node:
        tech = getattr(state, "tech", None) or {}
        if str(need_node) not in set(tech.get("unlocked") or []):
            errs.append(f"科技前置未解锁：{need_node}")

    # ---- B4-2 新材解锁门槛（2026-11 接线）----
    # 蓝图材料含**未解锁的新材**（水泥/钢筋等架空后世材料）⇒ 拒绝立项。
    # 口径：**不可用 ≠ 缺料排队**——未解锁是"此世尚未有此物"，不是"存货不足"。
    try:
        from core.domains.construction.material_tech import material_availability, resolve_material_tech
        for _dim in (bp.get("materials") or {}):
            if resolve_material_tech(_dim) is None:
                continue                       # 非登记新材，沿用既有材料口径
            _av = material_availability(state, _dim)
            if _av.get("available") is not True:
                errs.append(f"建材未解锁：{_dim}"
                            f"（{_av.get('reason') or _av.get('status')}）")
    except Exception as _mce:         # noqa: BLE001
        # 钩子不可用**不阻断立项**（缺的是"新材门槛"这一附加校验，
        # 不是工程本身不可建）；拒绝式只针对"确知未解锁"。
        pass

    _rok, _rerr = _region_ok(state, p, bp)
    if not _rok:
        errs.append(_rerr)

    cost = blueprint_cost(bp, 1)
    if cost > 0 and int(getattr(state, "treasury", 0) or 0) < cost:
        errs.append(f"国库不足：需 {cost:,} 贯")
    return (not errs), errs


def propose_project(state, route: str, name: str, key: Optional[str] = None,
                    levels: int = 1) -> Dict[str, Any]:
    """**营建立项**：把蓝图转成 `state.projects` 条目（`status="proposed"`），
    交由既有工程系统（`_settle_projects` 五态状态机）逐月推进——**本函数不落建筑**，
    完工落成由 `_settle_projects` 在 `progress>=100` 时写入 `prefectures[route]["buildings"]`。

    校验复用 `can_build`（蓝图登记 / 科技前置 / **地利前置** / 国库）；
    失败**拒绝式**：不立项、不改状态，返回可读原因。

    返回 `{"ok", "pid", "months", "cost"}` 或 `{"ok": False, "errors": [...]}`。
    """
    ok, errs = can_build(state, route, name, key)
    if not ok:
        return {"ok": False, "errors": errs}
    bp = resolve_blueprint(name, key, state)
    lv = max(1, int(levels or 1))
    cost = blueprint_cost(bp, lv)
    # 工期：科技/动态蓝图取 cost.months；政府建筑无 months → 缺省 6 月（与旧行为一致）
    months = int((bp.get("cost") or {}).get("months") or 6)
    bname = str(bp.get("_name") or name)
    projs = getattr(state, "projects", None)
    if not isinstance(projs, dict):
        projs = {}
        state.projects = projs
    pid = f"bp:{route}:{bp.get('_key')}"
    for p2 in projs.values():                       # 去重：同路同名在办/拟议不重复立项
        if (isinstance(p2, dict) and str(p2.get("name")) == bname
                and str(p2.get("route") or p2.get("prefecture")) == str(route)
                and p2.get("status") not in ("abandoned",)):
            return {"ok": False, "errors": [f"{route} 已有「{bname}」工程在案（{p2.get('status')}）"]}
    # 动态蓝图：把已注册构件翻译成 `_settle_projects` 完工段**已支持**的 output 键
    #（不新增结算分支）；静态蓝图保持原样（其 effect 由科技 adoption 承担，避免重复计入）
    _output: Dict[str, Any] = {}
    _runtime: Dict[str, Any] = {}
    if bp.get("_dynamic"):
        try:
            from core.blueprint_dynamic import (
                dynamic_blueprint_output, dynamic_blueprint_runtime,
            )
            _output = dynamic_blueprint_output(bp)     # 完工一次性
            _runtime = dynamic_blueprint_runtime(bp)   # 运行期按月 ×capacity
        except Exception:  # noqa: BLE001
            log.warning("[营建] 动态蓝图效果翻译失败，按无产出立项", exc_info=True)
    projs[pid] = {
        "name": bname, "type": bname, "status": "proposed",
        "route": route, "blueprint_key": bp.get("_key"), "levels": lv,
        "fund_cost": cost, "cost_coin": cost,
        "cost_material": dict(bp.get("materials") or {}), "craft_hours": 0.0,
        "speed": max(1, int(round(100.0 / max(1, months)))),   # 工期 = 蓝图 months（1-6）
        "progress": 0, "proposed_months": 0,
        # 完工效果：动态蓝图落已注册构件的产出；静态蓝图留空（由科技 adoption 承担）
        "output": _output,
        # 运行期产出（规格任务 4）：按月 ×capacity 结算；守恒通道见 _settle_projects
        "_runtime": _runtime,
        # 动态蓝图标记 + 效果清单（供面板/因果回看；不参与结算）
        "_dynamic": bool(bp.get("_dynamic")),
        "_effects": [dict(e) for e in (bp.get("effects") or [])],
    }
    return {"ok": True, "pid": pid, "months": months, "cost": cost, "name": bname}


def propose_projects(state, routes, name: str, key: Optional[str] = None,
                     levels: int = 1) -> Dict[str, Any]:
    """**一旨多址立项**（规格任务 3）：同一蓝图在多个路各生成**独立 project**。

    返回 `{"ok", "results": [{"route", "ok", "pid"|"errors"}...], "summary": {...}}`。
    · 逐路**独立预检与立项**：一路失败不影响其余路（逐项结果即可诊断）；
    · 同一路在同一批里重复出现 → 第二条按 already-in-plan 拒（不重复立项）；
    · `state.projects` 仍是**唯一**工程台账（不新建平行账本）；
    · 任一路成功 → `ok=True`（部分成功也如实回报，不伪装全成）。
    """
    if isinstance(routes, str):
        routes = [routes]
    if not isinstance(routes, (list, tuple)) or not routes:
        return {"ok": False, "results": [], "summary": {"reason": "未给出任何地点"}}
    results: List[Dict[str, Any]] = []
    done: set = set()
    for r in routes:
        route = str(r or "").strip()
        if not route:
            results.append({"route": route, "ok": False, "errors": ["地点为空"]})
            continue
        if route in done:
            results.append({"route": route, "ok": False,
                            "errors": [f"{route} 在本批旨意中重复出现，不重复立项"]})
            continue
        done.add(route)
        res = propose_project(state, route, name, key, levels)
        item: Dict[str, Any] = {"route": route, "ok": bool(res.get("ok"))}
        if res.get("ok"):
            item.update({"pid": res.get("pid"), "months": res.get("months"),
                         "cost": res.get("cost"), "name": res.get("name")})
        else:
            item["errors"] = res.get("errors") or ["立项失败"]
        results.append(item)
    ok_n = sum(1 for x in results if x["ok"])
    return {
        "ok": ok_n > 0,
        "results": results,
        "summary": {"total": len(results), "succeeded": ok_n,
                    "failed": len(results) - ok_n,
                    "cost_total": sum(int(x.get("cost", 0) or 0) for x in results if x["ok"])},
    }
