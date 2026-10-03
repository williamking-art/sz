# -*- coding: utf-8 -*-
"""圣旨行动闭环 · **计划/工程实际状态读数**（规格 `specs/decree-action-chain` 任务 5/6）。

一个读数、两个消费者（**口径单点**，前端与 AI 都不许各自重算）：
  · **AI**：`render_briefing_text()` 注入推演，使其看到**真实**工程/事务状态与阻力；
  · **UI**：后端 `/api/readouts` 的 `plan` 字段，拟旨面板据此展示行动拆解与因果回看。

规格要求（`requirements.md:25`）：**必须区分四个层级**，不得混写——
  ① 旨意**受理**（decree accepted）
  ② 执行**推进**（execution advance，长事务进度）
  ③ 工程**告成**（construction completion）
  ④ 效果**生效**（effect applied）
`phases` 字段把这四层**分行列出**；任何"已完工/已生效"的表述都必须能指回这里。

**只读**：本模块不建工程、不改账、不写状态（纯派生视图）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["PHASE_LABELS", "build_plan_readout", "render_briefing_text"]

#: 四层级标签（单点；面板与 AI 文案共用，禁止各自硬编码）
PHASE_LABELS: Dict[str, str] = {
    "accepted": "旨意受理",
    "advancing": "执行推进",
    "completed": "工程告成",
    "effective": "效果生效",
}


def _proj_status_label(status: Any) -> str:
    """工程状态 → 中文（复用 `decree_plan.ACTION_STATUS`，缺失则如实标未定义）。"""
    try:
        from core.decree_plan import ACTION_STATUS
    except Exception:  # noqa: BLE001
        ACTION_STATUS = {}
    s = str(status or "").strip()
    if not s:
        return "未定义"
    return ACTION_STATUS.get(s) or s


def build_plan_readout(state, route: Optional[str] = None) -> Dict[str, Any]:
    """构建计划/工程读数（只读、脱敏、有界）。

    `route` 给定时只收该路的工程（面板按路过滤）；None 则全收（上限 40 条）。
    """
    out: Dict[str, Any] = {
        "phases": {k: [] for k in PHASE_LABELS},
        "phase_labels": dict(PHASE_LABELS),
        "projects": [],
        "unsupported_tasks": [],
        "unresolved": [],
        "counts": {},
    }

    # ---- ① 旨意受理：待办与在办诏令 ----
    for d in list(getattr(state, "pending_decrees", None) or [])[:20]:
        if isinstance(d, dict):
            out["phases"]["accepted"].append({
                "kind": "decree", "title": str(d.get("title") or "")[:40],
                "id": str(d.get("id") or "")[:32],
                "note": "已受理，待结算执行",
            })

    # ---- ② 执行推进：长期事务/密令进度（**政治轨道**，不等于效果开关）----
    for queue, secret in ((getattr(state, "longterm_public", None), False),
                          (getattr(state, "longterm_secret", None), True)):
        for t in (queue or [])[:20]:
            if not isinstance(t, dict):
                continue
            out["phases"]["advancing"].append({
                "kind": "secret_task" if secret else "task",
                "title": str(t.get("task_name") or t.get("title") or "")[:40],
                "progress": round(float(t.get("progress", 0) or 0), 1),
                "outcome": t.get("outcome"),
                "note": str(t.get("last_change") or "")[:120],
            })

    # ---- ③ 工程告成 + ④ 效果生效：工程台账（唯一真源 `state.projects`）----
    projs = getattr(state, "projects", None)
    if isinstance(projs, dict):
        items = list(projs.items())
        rows: List[Dict[str, Any]] = []
        for pid, p in items:
            if not isinstance(p, dict):
                continue
            p_route = str(p.get("route") or p.get("prefecture") or "")
            if route is not None and p_route != str(route):
                continue
            status = p.get("status")
            rows.append({
                "pid": str(pid)[:64],
                "name": str(p.get("name") or p.get("type") or "工程")[:40],
                "route": p_route[:20],
                "status": status,
                "status_label": _proj_status_label(status),
                "progress": int(p.get("progress", 0) or 0),
                "capacity": round(float(p.get("capacity", 0) or 0), 3),
                "dynamic": bool(p.get("_dynamic")),
                # ④ 效果生效：完工 output（一次性）与运行期产出（按月 ×capacity）分列
                "output": p.get("output") if isinstance(p.get("output"), dict) else {},
                "runtime": p.get("_runtime") if isinstance(p.get("_runtime"), dict) else {},
                "effects": [dict(e) for e in (p.get("_effects") or [])][:8],
                # 因果回看：来源蓝图键
                "source_blueprint": str(p.get("blueprint_key") or "")[:64],
            })
            if status in ("operating", "degraded"):
                out["phases"]["completed"].append({
                    "kind": "project", "pid": str(pid)[:64],
                    "title": rows[-1]["name"], "route": p_route[:20],
                    "note": f"已告成（产能 {rows[-1]['capacity']:.0%}）",
                })
                if rows[-1]["output"] or rows[-1]["runtime"]:
                    out["phases"]["effective"].append({
                        "kind": "project_effect", "pid": str(pid)[:64],
                        "title": rows[-1]["name"],
                        "note": ("完工一次性：" + "、".join(rows[-1]["output"])
                                 if rows[-1]["output"] else "")
                                + ("；运行期：" + "、".join(rows[-1]["runtime"])
                                   if rows[-1]["runtime"] else ""),
                    })
            elif status == "proposed":
                out["phases"]["accepted"].append({
                    "kind": "project", "pid": str(pid)[:64],
                    "title": rows[-1]["name"], "route": p_route[:20],
                    "note": "已立项待拨款（拟议）",
                })
            elif status == "building":
                out["phases"]["advancing"].append({
                    "kind": "project", "pid": str(pid)[:64],
                    "title": rows[-1]["name"], "route": p_route[:20],
                    "progress": int(p.get("progress", 0) or 0),
                    "note": "营建中",
                })
        rows.sort(key=lambda x: (-int(x.get("progress", 0) or 0), str(x.get("name"))))
        out["projects"] = rows[:40]

    # ---- 未绑定程序侧落点的事务（规格任务 4 的成果，UI 应显式列出）----
    stats = getattr(state, "statistics", None)
    if isinstance(stats, dict):
        lst = stats.get("task_unsupported_list")
        if isinstance(lst, list):
            out["unsupported_tasks"] = [dict(x) for x in lst if isinstance(x, dict)][-10:]
        out["counts"]["unsupported_total"] = int(stats.get("task_unsupported", 0) or 0)
        out["counts"]["runtime_yield"] = float(stats.get("project_runtime_yield", 0) or 0)

    out["counts"].update({
        k: len(v) for k, v in out["phases"].items()
    })
    out["counts"]["projects"] = len(out["projects"])
    out["counts"]["dynamic_blueprints"] = len(getattr(state, "dynamic_blueprints", None) or {})
    return out


def render_briefing_text(readout: Dict[str, Any], *, max_lines: int = 14) -> str:
    """把读数渲染成**紧凑、脱敏**的提示词片段（供 AI 推演注入）。

    只给档位/状态词与有界计数，**不给内部路径、不给可被 AI 回写的字段名**。
    空读数返回空串（不编造"一切正常"）。
    """
    if not isinstance(readout, dict):
        return ""
    lines: List[str] = []
    rows = readout.get("projects") or []
    if rows:
        lines.append("【在建/已成工程（真实状态）】")
        for p in rows[:max_lines]:
            seg = f"· {p.get('route', '')}·{p.get('name', '')}：{p.get('status_label', '')}"
            if p.get("status") in ("building", "proposed"):
                seg += f" {int(p.get('progress', 0) or 0)}%"
            if p.get("status") in ("operating", "degraded"):
                seg += f"（产能 {float(p.get('capacity', 0) or 0):.0%}）"
            outs = p.get("output") or {}
            rts = p.get("runtime") or {}
            if outs or rts:
                seg += "；产出 " + "、".join(list(outs) + list(rts))
            lines.append(seg)
    uns = readout.get("unsupported_tasks") or []
    if uns:
        lines.append("【议毕但无程序侧落点的事务（**不得称其告成或已生效**）】")
        for u in uns[:5]:
            lines.append(f"· {str(u.get('name') or '')[:24]}（待支持）")
    adv = (readout.get("phases") or {}).get("advancing") or []
    if adv:
        lines.append("【在办事项（政治推进轨道，非效果开关）】")
        for a in adv[:6]:
            prog = f" {a.get('progress')}%" if a.get("progress") is not None else ""
            lines.append(f"· {str(a.get('title') or '')[:24]}{prog}")
    return "\n".join(lines)
