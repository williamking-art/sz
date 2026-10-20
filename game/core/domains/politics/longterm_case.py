# -*- coding: utf-8 -*-
"""长期旨「案卷化」（2026-10-20，参考外部 UI）。

参考结构（外部游戏「时局案卷」）：
    案号 / 承办人(六维) / 承办人授权(专款·余额·出库·赐专断之权·逐月自理) /
    案卷底册(种类·局势·状态·来源引据·立项回合·最近推进·严重度·关联地区·派系·可撤性) /
    当前阶段(见底→推进中→终前→达成) + 进度百分比 + 自然推进/需推动 + 预计还需 /
    当前影响(持续效果，如皇威−1/月) / 案情摘要 / 推进日志(逐月：落账+叙事) /
    达成后的目标 / 失败后的代价。

本模块只做**案卷那层**（字段、授权、专款、持续效果、日志、达成/失控），
进度推进仍归 longterm_task（不另立账本）。

纪律：
- 缺失一律 None（不假装 0）；专款必须从国库/内帑真实扣减（守恒）；
- 持续效果只接受白名单键（prestige/treasury/population_satisfaction），走既有单点；
- 幂等：字段补齐、授权重复调用都不叠加；日志有上限。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

__all__ = ["CASE_PHASES", "CLOSED_OUTCOMES", "MONTHLY_EFFECT_KEYS", "ensure_case_fields",
           "ensure_task_id", "ensure_task_ids_in_state", "iter_case_tasks",
           "authorize_case", "monthly_case_settle", "case_readout", "case_is_cased",
           "CASE_LOG_KEEP"]

#: 案卷阶段（与参考 UI 对齐：见底/推进中/终前/达成；失控单列）
CASE_PHASES = ("见底", "推进中", "终前", "达成", "失控")

#: 允许的「每月持续效果」键（其余拒绝，防未知键乱写）
MONTHLY_EFFECT_KEYS = ("prestige", "treasury", "population_satisfaction")

#: 推进日志保留条数
CASE_LOG_KEEP = 12

#: 赐专断之权的代价（2026-10-20）：提速 +15%，但每月承办人贪腐上升、民心下滑。
#: **按案封顶**（Jev 裁定 B，0.793）：单案累计民心最多 −10、贪腐最多 +0.08 后不再累加——
#: 60 月回放实测无上限版本 14 个月就把民心打到 0，代价过重失真。
DISCRETION_SPEED_MULT = 1.15
DISCRETION_CORRUPTION_MONTH = 0.008
DISCRETION_SATISFACTION_MONTH = -1
DISCRETION_CORRUPTION_CAP = 0.08      # 单案累计上限（正数）
DISCRETION_SATISFACTION_CAP = 10       # 单案累计上限（正数，实际按 −N 应用）

#: 进度 → 阶段（与 longterm_task._stage 的语义对齐，但用参考 UI 的档位名）
def phase_of(progress: Optional[float]) -> str:
    try:
        p = float(progress or 0)
    except (TypeError, ValueError):
        return "见底"
    if p >= 100:
        return "达成"
    if p >= 75:
        return "终前"
    if p > 0:
        return "推进中"
    return "见底"


def ensure_case_fields(state, task: Dict[str, Any]) -> Dict[str, Any]:
    """幂等补齐案卷字段（旧档安全默认；缺失保持 None/空，不编造数值）。"""
    if not isinstance(task, dict):
        return {}
    ensure_task_id(task)                 # C-14：缺 id 时确定性补齐（与读档同一算法）
    def _set(k, v):
        if k not in task:
            task[k] = v
    _set("case_no", None)
    _set("severity", None)
    _set("source_ref", None)
    _set("opened_turn", None)
    _set("last_advance_turn", None)
    _set("linked_region", None)
    _set("linked_factions", [])
    _set("cancellable", True)
    _set("budget", {"total": 0, "remaining": 0, "pool": "treasury"})
    _set("discretion", False)
    _set("monthly_effects", [])
    _set("monthly_cost", 0)
    _set("outcome_effects", [])
    _set("fail_effects", [])
    _set("progress_log", [])
    _set("phase", phase_of(task.get("progress")))
    return task


def _pool_change(state, pool: str, delta: int) -> bool:
    """从国库/内帑扣（delta<0）或退（delta>0）；不足返回 False（不动账）。"""
    if delta == 0:
        return True
    if pool == "imperial_treasury":
        have = int(getattr(state, "imperial_treasury", 0) or 0)
        if delta < 0 and have < -delta:
            return False
        state.change_imperial_treasury(delta)
        return True
    have = int(getattr(state, "treasury", 0) or 0)
    if delta < 0 and have < -delta:
        return False
    state.change_treasury(delta)
    return True


#: 已结案（告成/待支持/罢废/失控）后不再扣专款、不再落月度效果
CLOSED_OUTCOMES = ("告成", "待支持", "受阻罢废", "失控", "失败")


def iter_case_tasks(state) -> List[Dict[str, Any]]:
    """遍历**三处**事务队列（在办公开/在办密令/**结案归档**），按 id 去重。

    为什么需要归档：事务议毕后会被移出在办队列，但案卷（专款/持续效果/结案落账）
    仍需读得到——否则长局里案卷会"失忆"。
    """
    seen = set()
    out: List[Dict[str, Any]] = []
    for attr in ("longterm_public", "longterm_secret", "longterm_cases_archive"):
        for t in (getattr(state, attr, None) or []):
            if not isinstance(t, dict):
                continue
            tid = str(t.get("id") or "")
            if tid and tid in seen:
                continue
            if tid:
                seen.add(tid)
            out.append(t)
    return out


def ensure_task_id(task: Dict[str, Any]) -> str:
    """旧档事务缺 `id` 时补**确定性** id（同内容同 id，幂等）。

    C-14（2026-10-20 可选层）：旧档 task 无 id ⇒ 首轮结算前 `authorize_case`/案卷页
    按 id 命中不到（situations 投影也会跳过）。id 由 case_no/标题/立项回合派生，
    不使用随机数（读档多次结果一致）。
    """
    if not isinstance(task, dict):
        return ""
    tid = str(task.get("id") or "").strip()
    if tid:
        return tid
    seed = "|".join(str(task.get(k) or "") for k in
                    ("case_no", "title", "opened_turn", "linked_region"))
    task["id"] = "ltc_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return str(task["id"])


def ensure_task_ids_in_state(state) -> int:
    """为三处长期事务队列补齐 id（读档/结算前幂等调用）；返回被补条数。"""
    seen = set()
    fixed = 0
    for attr in ("longterm_public", "longterm_secret", "longterm_cases_archive"):
        for t in (getattr(state, attr, None) or []):
            if not isinstance(t, dict):
                continue
            raw = str(t.get("id") or "").strip()
            tid = ensure_task_id(t)
            if not raw:
                fixed += 1
            n = 1
            base = tid
            while tid in seen:
                n += 1
                tid = f"{base}-{n}"
            if tid != t.get("id"):
                t["id"] = tid
            seen.add(tid)
    return fixed


def case_is_cased(task: Dict[str, Any]) -> bool:
    """是否已案卷化（有案号/专款/月费/持续效果）——未案卷化的旧事务不参与月度结算。"""
    if not isinstance(task, dict):
        return False
    budget = task.get("budget") if isinstance(task.get("budget"), dict) else {}
    return bool(task.get("case_no") or (budget.get("total") or 0)
                or (task.get("monthly_cost") or 0)
                or (task.get("monthly_effects") or [])
                or (task.get("outcome_effects") or []))

def _pool_have(state, pool: str) -> int:
    """该池当前可用余额（只读；pool 只认国库/内帑）。"""
    if pool == "imperial_treasury":
        return int(getattr(state, "imperial_treasury", 0) or 0)
    return int(getattr(state, "treasury", 0) or 0)


def _next_case_no(state) -> str:
    """案号（幂等：任务已带 case_no 时调用方不覆盖）。后缀按已立案卷数递增。"""
    n = 0
    for _q in (getattr(state, "longterm_public", None) or [],
               getattr(state, "longterm_secret", None) or []):
        for _t in _q:
            if isinstance(_t, dict) and _t.get("case_no"):
                n += 1
    return "LT-%03d-%02d" % (int(getattr(state, "turn", 0) or 0), n + 1)


def authorize_case(state, task: Dict[str, Any], *, budget: int = 0,
                   pool: str = "treasury", discretion: bool = False,
                   monthly_cost: int = 0) -> Dict[str, Any]:
    """批专款 + 赐专断之权（幂等：重复授权不重复拨款）。

    🔴 口径（2026-10-20 全审 P0-3 / Jev 甲 0.575）：**授权只登记额度、不即时扣库**；
    每月 `monthly_case_settle` 按 `monthly_cost` 从国库/内帑**实扣**并递减 remaining。
    原实现「授权全额扣库 + 月结再扣一次、remaining 只做备忘」＝双扣 + 账外余额
    （钱离开国库却不在任何账户，违反钱粮落点/单账本硬约束）。
    `budget.remaining` 是**支出额度上限**（不是货币账户），专款耗尽即 blocked。
    """
    ensure_case_fields(state, task)
    if task.get("_authorized_once"):
        return {"ok": False, "reason": "已授权过（重复授权不重复拨款）", "task": task}
    amount = int(budget or 0)
    cost = int(monthly_cost or 0)
    if amount < 0:
        return {"ok": False, "reason": "专款不得为负"}
    if cost < 0:
        return {"ok": False, "reason": "月费不得为负"}
    if amount and _pool_have(state, pool) < amount:
        return {"ok": False, "reason": "府库不足，未拨款", "short": amount}
    task["budget"] = {"total": amount, "remaining": amount, "pool": pool}
    task["discretion"] = bool(discretion)
    task["monthly_cost"] = cost
    if task.get("opened_turn") is None:
        task["opened_turn"] = int(getattr(state, "turn", 0) or 0)
    if not task.get("case_no"):
        task["case_no"] = _next_case_no(state)
    task["_authorized_once"] = True
    return {"ok": True, "budget": task["budget"], "discretion": task["discretion"],
            "case_no": task["case_no"]}


def _apply_effect(state, key: str, amount: float) -> bool:
    if key not in MONTHLY_EFFECT_KEYS:
        return False
    try:
        v = int(round(float(amount)))
    except (TypeError, ValueError):
        return False
    if v == 0:
        return True
    if key == "prestige":
        state.change_prestige(v, "长期旨·持续效果")
    elif key == "treasury":
        state.change_treasury(v)
    else:
        state.population_satisfaction = int(getattr(state, "population_satisfaction", 50) or 50) + v
    return True


def monthly_case_settle(state, task: Dict[str, Any], log: Optional[list] = None, *,
                        narrative: str = "", progress: Optional[float] = None) -> Dict[str, Any]:
    """月度案卷结算：扣专款 → 落持续效果 → 写推进日志 → 判达成/失控。

    已结案（CLOSED_OUTCOMES）⇒ 直接返回 closed（不再扣专款、不再落效果），
    避免"议毕仍在烧钱/刷日志"。
    """
    ensure_case_fields(state, task)
    log = log if isinstance(log, list) else []
    if task.get("_closed"):
        return {"ok": True, "closed": True, "blocked": None, "applied": [],
                "phase": task.get("phase"), "outcome": task.get("outcome"), "entry": None}
    turn = int(getattr(state, "turn", 0) or 0)
    applied: List[Dict[str, Any]] = []
    blocked = None

    cost = int(task.get("monthly_cost") or 0)
    budget = task.get("budget") if isinstance(task.get("budget"), dict) else {}
    remaining = int(budget.get("remaining") or 0)
    if cost < 0:
        blocked = "月费不得为负"
    elif cost > 0:
        if remaining < cost:
            blocked = "专款耗尽，本月推行受阻"
        else:
            # P0-3：月费是**唯一**真实扣库点，并递减支出额度上限。
            # 复审补丁（2026-10-20）：扣款失败必须 blocked——否则「额度已减、效果照落、
            # 国库却没扣」＝免费推行（开局国库常低于月费，实测可触发）。
            if not _pool_change(state, str(budget.get("pool") or "treasury"), -cost):
                blocked = "府库不足，本月未能拨付"
            else:
                budget["remaining"] = remaining - cost
                task["budget"] = budget

    if not blocked:
        for eff in (task.get("monthly_effects") or []):
            if not isinstance(eff, dict):
                continue
            if _apply_effect(state, str(eff.get("key") or ""), eff.get("amount", 0)):
                applied.append({"key": eff["key"], "amount": eff.get("amount", 0)})

    if progress is not None:
        try:
            task["progress"] = max(0.0, min(100.0, float(progress)))
        except (TypeError, ValueError):
            pass
    task["phase"] = phase_of(task.get("progress"))
    # C-10（2026-10-20 可选层）：blocked 月未真正推进 ⇒ 不得更新 last_advance_turn
    # （否则面板显示"本月已推进"，而专款/效果都没落地）。
    if not blocked:
        task["last_advance_turn"] = turn

    # 天道叙事（2026-10-20）：结算只读 state._longterm_ai 槽位（AI 前置注入，结算期零 HTTP）。
    if not narrative:
        slot = getattr(state, "_longterm_ai", None)
        if isinstance(slot, dict):
            for it in (slot.get("items") or []):
                if isinstance(it, dict) and str(it.get("id") or "") == str(task.get("id") or ""):
                    narrative = str(it.get("narrative") or "")
                    break
    # 赐专断之权的代价（2026-10-20）：每月承办人贪腐上升、民心下滑（受挫月同样计）
    dis_cost = None
    if task.get("discretion"):
        used = task.get("_discretion_used")
        if not isinstance(used, dict):
            used = {"corruption": 0.0, "satisfaction": 0}
        room_corr = max(0.0, DISCRETION_CORRUPTION_CAP - float(used.get("corruption") or 0.0))
        room_sat = max(0, DISCRETION_SATISFACTION_CAP - int(used.get("satisfaction") or 0))
        d_corr = min(DISCRETION_CORRUPTION_MONTH, room_corr)
        d_sat = min(abs(DISCRETION_SATISFACTION_MONTH), room_sat)
        dis_cost = {"corruption": round(d_corr, 4), "satisfaction": -d_sat,
                    "capped": (room_corr <= 0 and room_sat <= 0)}
        used["corruption"] = round(float(used.get("corruption") or 0.0) + d_corr, 4)
        used["satisfaction"] = int(used.get("satisfaction") or 0) + d_sat
        task["_discretion_used"] = used
        name = str(task.get("minister") or "")
        if name and d_corr > 0:
            try:
                from content.ministers.stats import get_or_create_official_stats
                prof = get_or_create_official_stats(state, name)
                prof["corruption"] = round(min(1.0, float(prof.get("corruption") or 0.0)
                                               + d_corr), 4)
                dis_cost["handler"] = name
                dis_cost["corruption_now"] = prof["corruption"]
            except Exception:  # noqa: BLE001
                dis_cost["handler"] = None
        # 注意：民心可能是 0（合法值），不能用 or 默认（0 是 falsy ⇒ 会被误判成缺失）
        _cur_sat = getattr(state, "population_satisfaction", None)
        if _cur_sat is not None and d_sat > 0:
            try:
                state.population_satisfaction = max(0, int(_cur_sat) - d_sat)
            except (TypeError, ValueError):
                pass
    entry = {"turn": turn, "narrative": str(narrative or "")[:200],
             "applied": applied, "blocked": blocked, "discretion": dis_cost}
    plog = task.setdefault("progress_log", [])
    plog.append(entry)
    if len(plog) > CASE_LOG_KEEP:
        del plog[:len(plog) - CASE_LOG_KEEP]

    outcome = None
    # 失控代价（2026-10-20）：罢废时把 fail_effects 落账一次（幂等，防重复扣）
    if str(task.get("outcome") or "") in ("受阻罢废", "失控", "失败") and not task.get("_fail_applied"):
        for eff in (task.get("fail_effects") or []):
            if isinstance(eff, dict):
                _apply_effect(state, str(eff.get("key") or ""), eff.get("amount", 0))
        task["_fail_applied"] = True
        task["phase"] = "失控"
        outcome = "失控"
        log.append("[案卷] " + str(task.get("case_no") or task.get("id") or "") + " 失控，代价已落账")
    # 达成奖励只发给**真正告成**（outcome=告成）的案卷：
    # 「待支持」（进度满但无程序落点）不算成，不得发赏——避免"议毕就领赏"。
    if str(task.get("outcome") or "") == "告成" and not task.get("_outcome_applied"):
        for eff in (task.get("outcome_effects") or []):
            if isinstance(eff, dict):
                _apply_effect(state, str(eff.get("key") or ""), eff.get("amount", 0))
        task["_outcome_applied"] = True
        outcome = "达成"
        log.append("[案卷] " + str(task.get("case_no") or task.get("id") or "") + " 达成")
    # 结案：议毕/告成/罢废/失控 之后不再扣专款、不再落月度效果（归档保留案卷读数）
    if str(task.get("outcome") or "") in CLOSED_OUTCOMES:
        task["_closed"] = True
    return {"ok": blocked is None, "blocked": blocked, "applied": applied,
            "phase": task["phase"], "outcome": outcome, "entry": entry}


def _task_advance_readout(state, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """推进可解释读数（基数×难度×吏治×立场×军队；含阻碍与圣旨支持）。

    口径单点：longterm_task.build_readout；失败返回 None（缺失不假装）。
    """
    try:
        from core.longterm_task import build_readout
        r = build_readout(state, task)
    except Exception:  # noqa: BLE001
        return None
    ob = r.get("obstruction") or {}
    return {
        "stage": r.get("stage"),
        "progress": r.get("progress"),
        "forecast": r.get("forecast") or {},
        "blockers": list(ob.get("blockers") or []),
        "supporters": list(r.get("supporters") or []),
        "opposers": list(r.get("opposers") or []),
        "support_net": r.get("support_net"),
        "support_bonus": r.get("support_bonus"),
        "stance_mult": r.get("stance_mult"),
        "decree_count": r.get("decree_count"),
        "stall_months": r.get("stall_months"),
        "months": r.get("months"),
        "outcome": r.get("outcome"),
    }


def _eta_months(adv: Optional[Dict[str, Any]]) -> Optional[int]:
    """预计还需月数：剩余进度 ÷ 本月推进速度（向上取整）；读数缺失 ⇒ None（不猜）。"""
    if not isinstance(adv, dict):
        return None
    try:
        pct = float(adv.get("progress"))
    except (TypeError, ValueError):
        return None
    fc = adv.get("forecast") if isinstance(adv.get("forecast"), dict) else {}
    try:
        rate = float(fc.get("advance_pct"))
    except (TypeError, ValueError):
        return None
    if rate <= 0 or pct >= 100:
        return None
    import math
    return int(math.ceil((100.0 - pct) / rate))


def case_readout(state, task: Dict[str, Any]) -> Dict[str, Any]:
    """面板只读载荷（字段对齐参考 UI；缺失一律 None）。"""
    ensure_case_fields(state, task)
    _adv = _task_advance_readout(state, task)
    budget = task.get("budget") if isinstance(task.get("budget"), dict) else {}
    handler_name = task.get("minister")
    stats = None
    if handler_name:
        try:
            from content.ministers.stats import (ATTRIBUTE_NAMES,
                                                 get_or_create_official_stats)
            prof = get_or_create_official_stats(state, handler_name)
            attrs = dict(prof.get("attrs") or {})
            potential = dict(prof.get("potential") or {})
            stats = {
                "attrs": {k: attrs.get(k) for k in ATTRIBUTE_NAMES} or None,
                "potential": {k: potential.get(k) for k in ATTRIBUTE_NAMES} or None,
                "attr_names": dict(ATTRIBUTE_NAMES),
                "loyalty": prof.get("loyalty"), "corruption": prof.get("corruption"),
                "traits": list(prof.get("traits") or []),
                "faction": prof.get("faction"),
            }
        except Exception:  # noqa: BLE001
            stats = None
    _auth = None
    if task.get("_authorized_once"):
        _auth = {"budget_total": budget.get("total"),
                 "budget_remaining": budget.get("remaining"),
                 "pool": budget.get("pool"), "monthly_cost": task.get("monthly_cost"),
                 "discretion": bool(task.get("discretion"))}
    # 阶段语义：待支持（议毕无落点）与失控不得显示成「达成」；其余按进度映射。
    _outcome = str(task.get("outcome") or "")
    _phase = task.get("phase") or phase_of(task.get("progress"))
    if _outcome == "待支持":
        _phase = "待支持"
    elif _outcome in ("受阻罢废", "失控", "失败"):
        _phase = "失控"
    return {
        "case_no": task.get("case_no"),
        "title": task.get("task_name") or task.get("title"),
        "kind": task.get("category") or task.get("topic_label"),
        "status": "进行中" if _phase not in ("达成", "失控", "待支持") else _phase,
        "severity": task.get("severity"),
        "source_ref": task.get("source_ref"),
        "opened_turn": task.get("opened_turn"),
        "last_advance_turn": task.get("last_advance_turn"),
        "linked_region": task.get("linked_region"),
        "linked_factions": list(task.get("linked_factions") or []),
        "cancellable": bool(task.get("cancellable", True)),
        "handler": {"name": handler_name, "org": task.get("org_hint"), "stats": stats},
        # 缺失≠0（2026-10-20 全审 C-4）：未授权时整块返回 None，面板显示「未授权/未定义」；
        # 不再回落 0/0/treasury 让玩家误读成「专款 0 万两」。
        "authorization": _auth,
        "progress": {"percent": task.get("progress"), "phase": _phase,
                     "target": 100},

        # 本作特色：推进可解释（算式/阻碍/圣旨支持/立场），来自 longterm_task 单点，
        # 不在此复制算法。
        "advance": _adv,
        "eta_months": _eta_months(_adv),
        "monthly_effects": list(task.get("monthly_effects") or []),
        "progress_log": list(task.get("progress_log") or []),
        "outcome_effects": list(task.get("outcome_effects") or []),
        "fail_effects": list(task.get("fail_effects") or []),
    }
