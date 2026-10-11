# -*- coding: utf-8 -*-
"""M36.5 **察访诏令载荷执行点**（世界执行层；把决策层的行动载荷交既有单点执行）。

**为什么单独一个模块**：`core/inspection.py` 必须保持"监察不读司法"——
它的源码守卫（M36-1～4 契约）禁止出现 `from core.audit_case`／成案标识符。
而「涉嫌事项 → 怀疑层」必须调用司法侧的 `audit_case.record_report_suspicion`（唯一桥接），
故把这一类**执行层接线**放在本模块：它同时依赖 `core.inspection`（察访单点）与
`core.audit_case`（怀疑层唯一桥接），**只做结构校验＋调用**，不含任何判断与推荐。

纪律：
- `resolve_audit` **不在此处**，仍只经 `settlement_decree` 的 `audit_route`（唯一成案入口）；
- 非法载荷记日志但不抛异常（不打断整月结算）；
- 结算主链（`settlement.py`）**不得**调用本模块（源码测试钉住）。
"""
from typing import Any, Dict, List, Optional

__all__ = ["apply_inspect_decree_payload"]

_PAYLOAD_KEYS = ("inspect_dispatch", "inspect_report", "inspect_allege")


def apply_inspect_decree_payload(state, effects: dict,
                                 log: Optional[list] = None) -> List[str]:
    """执行察访诏令载荷（结构校验 → 既有单点）：

    - `inspect_dispatch {route, kind, secret}` → `inspection.enqueue_inspection()`（授差遣）
    - `inspect_report {task_id, summary}` → `inspection.file_inspection_report()`（奏报）
    - `inspect_allege {task_id, text}` → `audit_case.record_report_suspicion()`（唯一桥接，不建案）

    返回已执行的动作名列表。
    """
    from content.data import INSPECTION_KINDS
    from core.inspection import enqueue_inspection, file_inspection_report
    if not isinstance(effects, dict):
        return []
    done: List[str] = []
    _log = log.append if isinstance(log, list) else (lambda _t: None)

    # ---- ① 授差遣 ----
    if "inspect_dispatch" in effects:
        _p = effects.get("inspect_dispatch")
        if isinstance(_p, str):
            _p = {"route": _p}
        if isinstance(_p, dict):
            _route = str(_p.get("route", ""))
            _kind = str(_p.get("kind", ""))
            if _route not in (getattr(state, "prefectures", None) or {}):
                _log(f"[察访] 授差遣未成：路名不存在（{_route}）")
            elif _kind not in tuple(INSPECTION_KINDS or ()):
                _log(f"[察访] 授差遣未成：本批未开放的任务种类（{_kind}）")
            else:
                _r = enqueue_inspection(state, _route, _kind, secret=bool(_p.get("secret")))
                if _r.get("ok"):
                    done.append("inspect_dispatch")
                    _log(f"[察访] 授差遣：{_route} {_kind}"
                         f"{'（密访）' if _r['task'].get('secret') else ''}"
                         f"，限 {_r['task']['window_months']} 月")
                else:
                    _log(f"[察访] 授差遣未成：{_r.get('reason')}")
        else:
            _log("[察访] 载荷非法（inspect_dispatch 须为路名或 {route,kind,secret}），未执行")

    # ---- ② 奏报（改变任务终态；宜经批红，此处为已获准的正式执行）----
    if "inspect_report" in effects:
        _p = effects.get("inspect_report")
        if isinstance(_p, dict):
            _r = file_inspection_report(state, str(_p.get("task_id", "")),
                                        summary=str(_p.get("summary", "")),
                                        case_id=_p.get("case_id"))
            if _r.get("ok"):
                done.append("inspect_report")
                _log(f"[察访] 奏报已录：{_r['task'].get('route')} {_r['task'].get('kind')}")
            else:
                _log(f"[察访] 奏报未成：{_r.get('reason')}")
        else:
            _log("[察访] 载荷非法（inspect_report 须为 {task_id, summary}），未执行")

    # ---- ③ 涉嫌事项 → 怀疑层（唯一桥接；不建案）----
    if "inspect_allege" in effects:
        _p = effects.get("inspect_allege")
        if isinstance(_p, dict):
            from core.audit_case import record_report_suspicion
            _r = record_report_suspicion(state, str(_p.get("task_id", "")),
                                         str(_p.get("text", "")),
                                         source=str(_p.get("source") or "察访"))
            if _r.get("ok"):
                done.append("inspect_allege")
                _log(f"[察访] 涉嫌事项入怀疑层：{_r['suspicion'].get('route')}"
                     f"（命中「{_r['suspicion'].get('keyword')}」）")
            else:
                _log(f"[察访] 涉嫌事项未入怀疑层：{_r.get('reason')}")
        else:
            _log("[察访] 载荷非法（inspect_allege 须为 {task_id, text}），未执行")
    return done


def has_inspect_payload(effects: Any) -> bool:
    """载荷里是否含察访动作键（供执行点分流判断）。**只读**。"""
    return isinstance(effects, dict) and any(k in effects for k in _PAYLOAD_KEYS)
