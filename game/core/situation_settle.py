# -*- coding: utf-8 -*-
"""宋祚 · 局势结算步（core/situation_settle.py）—— 规范 §4 / §5 / §6 的实现

**本模块是 `state.situations` 的唯一写入点**（唯一权威），职责：

1. 按 §4.2 的**固定顺序**推进每条 active 局势：幂等 → 扣持续代价 → 档位 Δbar →
   streak → 终态判定 → 终态效果 → timeline；
2. 档位来源：AI（`state._situation_grades`，§7）或程序 `inertia`（AI 缺失不伪造）；
3. 扣费与效果一律走 `engine/state_applier.applier_pipeline`
   （路径白名单 + ΣΔ 守恒 + 原子写库 + 回滚）——**不另起第三套写状态通道**；
4. 玩家意图（§5）只读本回合事务记录校验，**不得由最终 state 反推**。

纪律：
- 终态不再推进、不再扣费、不再判定、不再执行效果；
- 资财不足 → 记 `deferred`，本月**不推进**（不得静默扣）；
- 新建局势（`origin_turn == turn`）当回合**整段跳过**；
- `last_settled_turn` 是幂等专用字段，与"推进"语义分离。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from core.situations import (
    GRADE_DELTA, MAX_INTENTS_PER_TURN, advance_bar, effects_to_changes, evaluate,
    is_terminal, next_status, pick_intents, used_metrics, validate_intent,
    validate_situation_effects,
)

log = logging.getLogger("situation_settle")

__all__ = ["INTENT_BONUS", "settle_situations", "current_execution_mult",
           "troops_mustered_this_turn", "TIMELINE_LIMIT"]

# 玩家意图档位（§5.1 通道 2 的**单点定义**）：intent 只作为"当月档位判定输入"，
# 且**必须**乘以执行度（§3.6：下了诏 ≠ 办了事）。
INTENT_BONUS: Dict[str, float] = {
    "调兵": 6.0, "拨帑": 5.0, "赈济": 5.0, "查办": 4.0, "减免": 4.0, "蠲赋": 4.0,
}

TIMELINE_LIMIT = 60          # timeline 只保留最近 N 条（长局防膨胀）


def current_execution_mult(state, text: str = "",
                           enforce_troops: bool = False) -> Optional[float]:
    """当前**诏令实际效果系数**（口径单点：`core/decree_effect.py`）。

    组成（用户定稿 2026-09-19）：
      `吏治（强）× 民心/识字率（弱）`；军队按**条件加成**参与——
      军政/边事类**天然参与**，民政类**玩家调兵强制施行（`enforce_troops`）时参与**。
    **返回 `None` = 吏治读数缺失、系数无法定义**（不回落 1.0 假装"吏治完美"）；
    调用方须显式选择策略并留痕（见 `settle_situations` 的 timeline 记录）。
    """
    try:
        from core.decree_effect import decree_effect_mult
        v = decree_effect_mult(state, text=text, enforce_troops=enforce_troops)
        return None if v is None else float(v)
    except Exception as e:  # noqa: BLE001
        log.warning("situation_settle 取诏令效果系数失败：%s", e)
        return None


def troops_mustered_this_turn(journal) -> bool:
    """本回合是否**确有调兵**（民政诏令借兵强制施行的判据）。

    依据 `state_applier` 事务记录里 `defense_lines.*.garrison` 的实际增减——
    这是"玩家真的调了兵"的客观痕迹，**不靠诏令自述**（§5.2 同一纪律）。
    """
    for ch in (journal or []):
        if not isinstance(ch, dict):
            continue
        path = ch.get("path")
        if not isinstance(path, str) or not path.startswith("defense_lines."):
            continue
        if not path.endswith(".garrison"):
            continue
        try:
            if abs(float(ch.get("new")) - float(ch.get("old"))) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _apply(state, changes: List[dict], agent: str) -> Tuple[bool, List[str]]:
    """先过**局势专用收窄白名单**（§6.2），再走**同一批量事务 API**：
    验证 → 守恒 → 原子写库（失败整批回滚）。

    收窄白名单必须在 applier 之前——applier 的 `VALID_PATHS` 更宽（含 `unrest` 等 AI 通道），
    若直接交给它，局势就能改到首批明确排除的落点（规范 §6.2 明令移出）。
    """
    if not changes:
        return True, []
    front_errors = validate_situation_effects(changes)
    if front_errors:
        return False, [f"落点未注册：{e}" for e in front_errors[:3]]
    try:
        from engine.state_applier import applier_pipeline
    except Exception as e:  # noqa: BLE001
        return False, [f"state_applier 不可用：{type(e).__name__}"]
    res = applier_pipeline(state, [(agent, changes)])
    if res.get("applied"):
        return True, []
    return False, [str(x) for x in (res.get("rejected") or res.get("errors") or ["未落地"])]


def _journal_since(base: int) -> List[dict]:
    """本回合的 `state_applier` 事务记录（只读切片；§5.2 唯一校验依据）。

    **`base == 0` 且台账已有历史条目时返回空表**——那说明调用方没有正确传游标，
    此时**绝不能**拿历史回合的划转替本回合意图背书（"上月的赈济给本月 intent 作证"）。
    台账本来就空（新局首回合）时同样返回空表。
    """
    try:
        from engine.state_applier import CHANGE_LOG
        n = len(CHANGE_LOG)
        start = max(0, int(base))
        if start == 0 and n > 0:
            log.warning("situation_settle：事务台账已有 %d 条历史却收到 base=0，"
                        "按「本回合无记录」处理（不拿历史背书）", n)
            return []
        return list(CHANGE_LOG[start:n])
    except Exception:  # noqa: BLE001
        return []


def _snapshot_for(state, rec: dict) -> dict:
    """按该条局势实际用到的 metric 取快照（一次取值，不读 state 之外的东西）。"""
    keys = sorted(set(used_metrics(rec.get("resolve_condition"))) |
                  set(used_metrics(rec.get("fail_condition"))))
    if not keys:
        return {"metrics": {}}
    try:
        from core.situation_metrics import build_metric_snapshot
        snap, _errs = build_metric_snapshot(state, keys)
        return snap
    except Exception as e:  # noqa: BLE001
        log.warning("situation_settle 取快照失败：%s", e)
        return {"metrics": {}}


def _push_timeline(rec: dict, entry: dict) -> None:
    tl = rec.get("timeline")
    if not isinstance(tl, list):
        tl = []
    tl.append(entry)
    if len(tl) > TIMELINE_LIMIT:
        del tl[: len(tl) - TIMELINE_LIMIT]
    rec["timeline"] = tl


def settle_situations(state, log_lines: Optional[list] = None,
                      journal_base: int = 0) -> Dict[str, Any]:
    """局势结算步（规范 §4.1：位于 Step 8 灾荒之后、Step 9 皇帝个人之前）。

    `journal_base` = 本回合开始时 `state_applier.CHANGE_LOG` 的长度（由管线传入），
    用于切出**本回合**事务记录供 intent 校验（§5.2）。
    """
    out = {"settled": 0, "resolved": 0, "failed": 0, "deferred": 0, "errors": []}
    logs = log_lines if isinstance(log_lines, list) else []
    records = getattr(state, "situations", None)
    if records is None:
        try:
            state.situations = []
        except Exception:  # noqa: BLE001
            return out
        records = state.situations
    if not isinstance(records, list) or not records:
        return out

    turn = int(getattr(state, "turn", 0) or 0)
    grades = getattr(state, "_situation_grades", None) or {}
    raw_intents = getattr(state, "_situation_intents_this_turn", None) or []
    intents = pick_intents(raw_intents, turn)
    journal = _journal_since(journal_base)
    ai_narratives: List[Tuple[str, str]] = []

    for rec in records:
        if not isinstance(rec, dict):
            out["errors"].append(f"record 非 dict：{type(rec).__name__}")
            continue
        if is_terminal(rec):
            continue
        # 注意：**不得**写 `rec.get("x", -1) or -1` —— 回合 0 是合法值，`0 or -1` 会吞成 -1，
        # 从而让「幂等」与「新建局势当回合跳过」双双失效（已由回归测试抓出）。
        _last = rec.get("last_settled_turn")
        _last = -1 if _last is None else int(_last)
        if _last >= turn:
            continue                                  # 幂等（§4.3）
        _origin = rec.get("origin_turn")
        _origin = -1 if _origin is None else int(_origin)
        skip_all = _origin == turn
        rid = str(rec.get("id") or "")
        grade_info = grades.get(rid) if isinstance(grades, dict) else None

        if not skip_all:
            # ---- ① 扣持续代价（成对划转；不足 → deferred，本月不推进）----
            cost = rec.get("ongoing_cost")
            if cost:
                ok, errs = _apply(state, effects_to_changes(cost, "局势代价", "situations_cost"),
                                  "situations_cost")
                if not ok:
                    out["deferred"] += 1
                    _push_timeline(rec, {"turn": turn, "kind": "报",
                                         "text": f"资财不足，本月暂缓（{'; '.join(errs[:2])}）",
                                         "source": "program"})
                    rec["last_settled_turn"] = turn
                    logs.append(f"[局势] {rec.get('title')}：资财不足，暂缓")
                    continue

            # ---- ② 档位 → Δbar（AI 档位或 inertia；intent 加成 × 执行度）----
            grade = None
            narrative = None
            if isinstance(grade_info, dict):
                grade = grade_info.get("grade")
                narrative = grade_info.get("narrative")
            bonus = 0.0
            used_intent = None
            for it in intents:
                if str(it.get("situation_id")) == rid:
                    it["validation_result"] = "pass" if validate_intent(it, journal) else "fail"
                    it["consumed_turn"] = turn
                    if it["validation_result"] == "pass":
                        bonus = INTENT_BONUS.get(str(it.get("kind")), 0.0)
                        used_intent = it
                    break
            old_bar = rec.get("bar_value")
            # 每条局势按其**自身性质**判定：军政类天然吃军队；民政局势若本回合确有调兵
            # （事务记录里 defense_lines.*.garrison 变化）则以军队强制施行 → 军队参与。
            enforce = troops_mustered_this_turn(journal)
            exec_mult = current_execution_mult(state, str(rec.get("title") or ""),
                                               enforce_troops=enforce)
            if exec_mult is None:
                # 吏治读数缺失：**不回落 1.0 假装无事**，按"无折扣"推进但明确留痕，
                # 使面板/AI 能看出这条推进是"缺折扣数据"而不是"吏治完美"。
                exec_mult = 1.0
                _push_timeline(rec, {"turn": turn, "kind": "报",
                                     "text": "吏治读数缺失，本月按无折扣推进（系数未定义）",
                                     "source": "program"})
            new_bar = advance_bar(old_bar, grade, inertia=rec.get("inertia", 0) or 0,
                                  intent_bonus=bonus, execution_mult=exec_mult)
            rec["bar_value"] = new_bar
            if grade is None:
                _push_timeline(rec, {"turn": turn, "kind": "推进",
                                     "text": f"程序推进：{old_bar} → {new_bar}（未接 AI 档位）",
                                     "source": "program"})
            else:
                _push_timeline(rec, {"turn": turn, "kind": "推进",
                                     "text": f"档位 {grade}：{old_bar} → {new_bar}",
                                     "source": "program"})
            if narrative:
                ai_narratives.append((rid, str(narrative)))
            if used_intent is not None:
                _push_timeline(rec, {"turn": turn, "kind": "谕",
                                     "text": f"圣意（{used_intent.get('kind')}）："
                                             f"{used_intent.get('note') or ''}"
                                             f"（执行度 ×{exec_mult:.2f}）",
                                     "source": "program"})

            # ---- ③ 终态判定（fail 优先；同回合双命中 → failed + 冲突）----
            snap = _snapshot_for(state, rec)
            fc, rc = rec.get("fail_condition"), rec.get("resolve_condition")
            fail_hit = bool(evaluate(fc, snap)) if fc else False
            resolve_hit = bool(evaluate(rc, snap)) if rc else False
            verdict = next_status(rec, fail_hit, resolve_hit)
            rec["streak_ok"] = verdict["streak_ok"]
            rec["streak_fail"] = verdict["streak_fail"]
            if verdict["conflict"]:
                _push_timeline(rec, {"turn": turn, "kind": "冲突",
                                     "text": "本月达成与失败条件同时命中，按 failed 处置",
                                     "source": "program"})
            if verdict["status"] != "active":
                rec["status"] = verdict["status"]
                kind = "终止"
                if verdict["status"] == "resolved":
                    out["resolved"] += 1
                    payload = rec.get("effect_on_resolve")
                else:
                    out["failed"] += 1
                    payload = rec.get("effect_on_fail")
                if payload:
                    ok, errs = _apply(state, effects_to_changes(payload, "局势效果", "situations"),
                                      "situations")
                    if not ok:
                        out["errors"].append(f"{rid}: 终态效果未落地（{'; '.join(errs[:2])}）")
                _push_timeline(rec, {"turn": turn, "kind": kind,
                                     "text": f"局势{'达成' if verdict['status'] == 'resolved' else '失败'}",
                                     "source": "program"})
                logs.append(f"[局势] {rec.get('title')}：{verdict['status']}")

        rec["last_settled_turn"] = turn
        out["settled"] += 1

    # consumed 标记：未被任何局势消费的 intent 也要落 consumed_turn（避免跨月重复消费），
    # 且未获支撑者记为 fail（不得留 pending 让下月替它背书）。
    for it in raw_intents:
        if isinstance(it, dict) and it.get("consumed_turn") is None:
            it["consumed_turn"] = turn
            if it.get("validation_result") == "pending":
                it["validation_result"] = "fail"

    # AI 叙事在**状态变更之后**一次性入 timeline（§7.3）
    for rid, narrative in ai_narratives:
        for rec in records:
            if isinstance(rec, dict) and str(rec.get("id")) == rid:
                _push_timeline(rec, {"turn": turn, "kind": "谕", "text": narrative,
                                     "source": "ai"})
                break
    try:
        state._situation_grades = {}
        state._situation_intents_this_turn = []
    except Exception:  # noqa: BLE001
        pass
    return out
