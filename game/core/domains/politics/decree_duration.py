# -*- coding: utf-8 -*-
"""诏令生效月数（2026-10-20，天道档位化 batch4；用户裁定：多因素 + AI 判断空间）。

用户原话：「多方面因素影响，天道，主持官员能力，皇威，后续跟进等等」
追加：「还要给ai判断的空间，例如给官员加薪这种，还有敢拖的吗」。

口径：
    months = clamp( round( base(天道节奏档) × 执行态度 × 能力 × 皇威 × 跟进 ), 3, 36 )

- **天道执行态度**（新增，AI 判断"谁敢拖"）：奉行 / 依违 / 阳奉阴违 / 拖延
  → ×1.00 / 1.15 / 1.35 / 1.60；AI 还可给一句叙事（谁在拖、为何拖）；
- **天道节奏**：速/常/缓 → 6/12/18；
- **主持官员能力**：<40 ×1.25 / 40–69 ×1.00 / ≥70 ×0.80；
- **皇威**：<40 ×1.20 / 40–79 ×1.00 / ≥80 ×0.85；
- **后续跟进**：0 ×1.10 / 1 ×0.95 / ≥2 ×0.85。

AI 判断空间的用法（例）：
- 加薪诏（利官）⇒ 官员多「奉行」，但皇威不振/吏治败坏时可能「依违」乃至「拖延」；
- 裁冗诏（损官）⇒ 常「阳奉阴违」；皇威鼎盛 + 强力主持才「奉行」。

纪律：天道只出档位 + 叙事；系数表集中本模块；缺档 ⇒ ×1.00 并标明"天道未判"。

槽位纪律（2026-10-20 全审 P0-4 / R-AI-8 / R-AI-9）：
- `state._decree_ai` / `state._decree_execute_ai` 是**运行时槽位**：生产者（`ai.contracts_decree`、
  `application.decree_prefetch`、`application.agent_router`）在注入前清槽、产出后盖 `_turn`；
  本模块消费时对**带 `_turn` 的槽位只认本回合**（`slot_is_current`）——旧槽不得冒充本回合的天道裁决
  （缺失 ≠ 沿用上次结论）。无 `_turn` 的旧槽（历史测试替身）保持兼容。
- 扩展点 `register_timing_provider` / `register_attitude_provider` **仅插件/测试用**：
  现有生产代码**零注册方**（全审 R-AI-8 实测）。provider 必须是**纯函数**（只读 state）：
  抛异常 → `log.warning` 后跳过；改写 state 标量 → 检出、回滚、丢弃结果。
"""
from __future__ import annotations

import contextlib
import logging
import math
from typing import Any, Dict, Optional

log = logging.getLogger("core.decree_duration")

__all__ = ["BASE_MONTHS", "PRIORITY_TO_PACE", "ATTITUDE_LEVELS", "ATTITUDE_MULT",
           "resolve_decree_duration", "resolve_execution_attitude", "duration_breakdown",
           "FACTOR_WEIGHTS", "MULT_MIN", "MULT_MAX",
           "DECREE_TIMING", "TIMING_BY_EFFECT", "ATTITUDE_COMPLETION",
           "classify_decree_timing", "TIMING_LEVELS", "resolve_decree_timing",
           "register_timing_provider", "register_attitude_provider",
           "slot_is_current"]

BASE_MONTHS: Dict[str, int] = {"速": 6, "常": 12, "缓": 18}
PRIORITY_TO_PACE: Dict[str, str] = {"高": "速", "中": "常", "低": "缓"}
ATTITUDE_LEVELS = ("奉行", "依违", "阳奉阴违", "拖延")
ATTITUDE_MULT: Dict[str, float] = {"奉行": 1.00, "依违": 1.15, "阳奉阴违": 1.35, "拖延": 1.60}
MONTHS_MIN, MONTHS_MAX = 3, 36

#: 诏令时效：即时（本回合办妥）/ 短期（1–3 月）/ 长期（工程型）
DECREE_TIMING = ("immediate", "short", "long")

#: 天道可判的时效档位 → 内部时效
TIMING_LEVELS = {"即时": "immediate", "短期": "short", "长期": "long"}

#: 效果键 → 时效（未列出默认 long，避免把工程当儿戏）
TIMING_BY_EFFECT = {
    "pay_reform": "immediate", "commerce_tax": "immediate", "single_whip": "immediate",
    "prestige": "immediate", "treasury": "immediate", "imperial_treasury": "immediate",
    "population_satisfaction": "immediate", "faction_change": "immediate",
    "defense_bonus": "immediate", "he_mi": "immediate", "grain_stabilize": "immediate",
    "canal_dredge": "short", "relief": "short", "settle_refugees": "short",
    "army_strength": "short",
    "reduce_office": "long", "curtail_waste": "long", "land_survey": "long",
    "anti_corruption": "long", "granary_reform": "long", "military_supply": "long",
}

#: 即时诏令的「执行完成度」（拖延体现为打折，而非拖成长期）
ATTITUDE_COMPLETION = {"奉行": 1.00, "依违": 0.85, "阳奉阴违": 0.60, "拖延": 0.35}

#: 因素权重（显式，和=1）：加权几何平均的指数，决定各因素话语权
FACTOR_WEIGHTS = {"attitude": 0.40, "ability": 0.25, "prestige": 0.20, "followup": 0.15}

#: 总乘数夹取（防数值爆炸；与加权几何平均共同构成双保险）
MULT_MIN, MULT_MAX = 0.55, 1.90


# ---------------------------------------------------------------------------
# 槽位回合戳（P0-4）：带 `_turn` 的槽位只认本回合；无 `_turn` 的旧槽保持兼容
# ---------------------------------------------------------------------------
def _as_str(v) -> Optional[str]:
    """档位读取：非 str（list/dict/int…）一律视为缺失。

    原实现直接拿槽位值做 **dict 成员判断**（`lvl in TIMING_LEVELS`、`slot.get(att) in ATTITUDE_MULT`），
    遇到 `["长期"]` 这类非 str 会抛 `TypeError: unhashable type: 'list'` —— 该函数在结算
    critical 步（改制/裁冗）里被调用，异常会让**整月结算回滚**（R-AI-9 实锤）。
    """
    return v if isinstance(v, str) else None


def _state_turn(state) -> Optional[int]:
    try:
        t = getattr(state, "turn", None)
        return int(t) if t is not None else None
    except (TypeError, ValueError):
        return None


def slot_is_current(state, slot) -> bool:
    """槽位是否属于**本回合**（或同一批诏令跨回合执行时仍有效）。

    - 非 dict → 不可用；
    - 未盖 `_turn`（历史测试替身/旧槽） → **兼容**，照旧采信；
    - 盖了 `_turn` 且与 `state.turn` 不等 → 先看 `_decree_ids`（稳定 id，O6 2026-10-20）：
      该批诏令仍在待行/执行则**保留裁决**；有 id 但活集合无 id（旧档）再回落
      `_decree_titles`（题名可重名，仅作无 id 时的兼容）；
      都不匹配 ⇒ 按**残留**不采信（缺失 ≠ 沿用上次结论）；
    - 盖了 `_turn` 但拿不到当前回合 → 保守不采信（有戳却无法核对 ⇒ 按缺失）。
    """
    if not isinstance(slot, dict):
        return False
    stamped = slot.get("_turn")
    if stamped is None:
        return True
    cur = _state_turn(state)
    if cur is None:
        return False
    try:
        if int(stamped) == cur:
            return True
    except (TypeError, ValueError):
        return False
    # 复审补丁（2026-10-20）：跨回合但**同一批诏令仍在待行/执行**时保留裁决。
    # 复述门挂起、M2a 待定会让诏令跨回合执行；若只认严格同回合，会把这批诏令
    # 仍有效的天道时效/态度/落地档丢掉（回退程序表，属误伤）。
    # O6：优先按 **decree_id** 匹配（题名可重名；同名不同诏不得互相采信）。
    ids = slot.get("_decree_ids")
    if isinstance(ids, (list, tuple)) and ids:
        live_ids = set()
        for _attr in ("pending_decrees", "pending_secret_decrees", "active_decrees"):
            for _d in (getattr(state, _attr, None) or []):
                if isinstance(_d, dict):
                    _did = str(_d.get("decree_id") or "").strip()
                    if _did:
                        live_ids.add(_did)
        if live_ids:
            return any(str(_i).strip() in live_ids for _i in ids)
    titles = slot.get("_decree_titles")
    if isinstance(titles, (list, tuple)) and titles:
        live = set()
        for _attr in ("pending_decrees", "pending_secret_decrees", "active_decrees"):
            for _d in (getattr(state, _attr, None) or []):
                if isinstance(_d, dict):
                    _t = str(_d.get("title") or "").strip()
                    if _t:
                        live.add(_t)
        if any(str(_t).strip() in live for _t in titles):
            return True
    return False


#: provider 必须**只读** state；这里拷一份指纹用于检出「provider 偷偷写 state」。
#: 标量字段直接取值；容器字段深拷贝（2026-10-20 O2：provider 改嵌套结构也能检出，
#: 回滚时把整个容器恢复为快照）。
_STATE_PROBE_FIELDS = ("treasury", "imperial_treasury", "granary", "prestige", "population")
_STATE_PROBE_DEEP_FIELDS = ("coin", "jiaozi", "factions")


def _state_probe(state) -> dict:
    import copy

    snap = {}
    for k in _STATE_PROBE_FIELDS:
        try:
            snap[k] = getattr(state, k, None)
        except Exception:  # noqa: BLE001
            snap[k] = None
    for k in _STATE_PROBE_DEEP_FIELDS:
        try:
            snap[k] = copy.deepcopy(getattr(state, k, None))
        except Exception:  # noqa: BLE001
            snap[k] = None
    return snap


def _guard_state_readonly(state, before: dict, what: str) -> bool:
    """provider 调用后核对 state 未被改写；被改写则回滚并返回 False（丢弃结果）。"""
    after = _state_probe(state)
    if after == before:
        return True
    changed = [k for k in before if before[k] != after.get(k)]
    log.warning("%s 改写了只读 state（%s）——结果已丢弃，字段已回滚（provider 必须是纯函数）",
                what, changed)
    for k in changed:
        with contextlib.suppress(Exception):   # 回滚失败不回抛：本函数只负责"丢弃结果"
            setattr(state, k, before[k])
    return False


def _ability_mult(ability: Optional[float]) -> tuple:
    if ability is None:
        return 1.00, "主持官员未指定"
    try:
        a = float(ability)
    except (TypeError, ValueError):
        return 1.00, "主持官员能力非数值"
    if not math.isfinite(a):
        # NaN 与任何阈值比较恒 False ⇒ 原实现落「能力出众」（×0.80，最有利档）＝伪造
        return 1.00, "主持官员能力读数非有限"
    if a < 40:
        return 1.25, "能力偏低"
    if a < 70:
        return 1.00, "能力中等"
    return 0.80, "能力出众"


def _prestige_mult(prestige: Optional[float]) -> tuple:
    try:
        p = float(prestige)
    except (TypeError, ValueError):
        return 1.00, "皇威缺失"
    if not math.isfinite(p):
        # 同上：NaN 不得落「皇威尚隆」（×0.85，最有利档）
        return 1.00, "皇威读数非有限"
    if p < 40:
        return 1.20, "皇威不振"
    if p < 80:
        return 1.00, "皇威平平"
    return 0.85, "皇威尚隆"


def _followup_mult(followup: Optional[int]) -> tuple:
    try:
        n = int(followup or 0)
    except (TypeError, ValueError):
        n = 0
    if n >= 2:
        return 0.85, "催办密集"
    if n == 1:
        return 0.95, "有催办"
    return 1.10, "无后续跟进"


def _pace_from_ai(state) -> tuple:
    slot = getattr(state, "_decree_ai", None)
    if slot_is_current(state, slot):
        pace = _as_str(slot.get("pace"))
        if pace in BASE_MONTHS:
            return pace, "天道"
    ex = getattr(state, "_decree_execute_ai", None)
    if slot_is_current(state, ex):
        tasks = ex.get("tasks") if isinstance(ex.get("tasks"), list) else []
        rank = {"高": 3, "中": 2, "低": 1}
        best = None
        for t in tasks:
            if not isinstance(t, dict):
                continue
            pr = _as_str(t.get("priority"))
            if pr in rank and (best is None or rank[pr] > rank[best]):
                best = pr
        if best is not None:
            return PRIORITY_TO_PACE[best], "天道(任务优先级)"
    return "常", "缺档默认常(天道未给节奏)"


def resolve_execution_attitude(state, *, decree_kind: str = "",
                               beneficiary: str = "") -> Dict[str, Any]:
    """天道判断执行态度（"谁敢拖"）。返回 {level, mult, note, source}。"""
    slot = getattr(state, "_decree_ai", None)
    got = slot if slot_is_current(state, slot) else {}
    att = _as_str(got.get("execution_attitude"))
    src = "天道"
    note = got.get("attitude_note") or ""
    if att not in ATTITUDE_LEVELS:
        ex = getattr(state, "_decree_execute_ai", None)
        if slot_is_current(state, ex):
            att2 = _as_str(ex.get("execution_attitude"))
            if att2 in ATTITUDE_LEVELS:
                att, src = att2, "天道(执行契约)"
                note = ex.get("attitude_note") or ""
    if att not in ATTITUDE_LEVELS:
        for fn in reversed(_ATTITUDE_PROVIDERS):
            before = _state_probe(state)
            try:
                cand = fn(state, decree_kind, beneficiary)
            except Exception:  # noqa: BLE001 — 可选层：provider 出错不得阻断结算
                log.warning("执行态度 provider 抛错（已忽略，回落效果键表）", exc_info=True)
                continue
            if not _guard_state_readonly(state, before, "执行态度 provider"):
                continue
            ok = _as_str(cand.get("execution_attitude")) if isinstance(cand, dict) else None
            if ok in ATTITUDE_LEVELS:
                att = ok
                src = "天道(provider)"
                note = cand.get("note") or ""
                break
    if att in ATTITUDE_LEVELS:
        return {"level": att, "mult": ATTITUDE_MULT[att], "note": note, "source": src}
    return {"level": None, "mult": 1.00,
            "note": "天道未判执行态度" + (f"（{beneficiary}）" if beneficiary else ""),
            "source": "缺档"}


_ATTITUDE_PROVIDERS: list = []


def register_attitude_provider(fn) -> None:
    """注册执行态度档位提供者（**仅插件/测试用**；现有生产代码零注册方，全审 R-AI-8）。

    纪律：
    - provider 必须是**纯函数**：只读 `state`，不得写任何 state 字段（写标量会被
      `_guard_state_readonly` 检出、回滚并丢弃结果）；
    - 抛异常 → `log.warning(..., exc_info=True)` 后跳过（静默 continue 会让"谁在拖"
      的 provider 长期坏死而无人知）；
    - 重复注册同一函数 → 忽略（模块级列表跨局/跨测试共享，叠加注册会串档）。
    """
    if not callable(fn):
        log.warning("register_attitude_provider 收到非可调用对象，已忽略：%r", fn)
        return
    if any(f is fn for f in _ATTITUDE_PROVIDERS):
        log.warning("register_attitude_provider 重复注册（同一函数），已忽略")
        return
    _ATTITUDE_PROVIDERS.append(fn)


def classify_decree_timing(decree_kind: str) -> tuple:
    """效果键 → (时效, 依据)。未知键按 long（工程型）处理并注明。"""
    k = str(decree_kind or "").strip()
    if k in TIMING_BY_EFFECT:
        return TIMING_BY_EFFECT[k], "按效果键"
    return "long", "未知效果键，按长期工程处理"

def resolve_decree_timing(state, decree_kind: str = "") -> Dict[str, Any]:
    """**谁定时效**：天道档位优先（即时/短期/长期）；缺档按效果键表；未知键按长期。

    设计意图（用户裁定）：「圣旨发出，推演AI要能判断是走即时，还是长期局势」。
    例：加薪通常是即时，但朝局崩坏时 AI 可判为长期拉锯（拖而不办）。
    """
    slot = getattr(state, "_decree_ai", None)
    current = slot if slot_is_current(state, slot) else None
    lvl = _as_str(current.get("execution_timing")) if current is not None else None
    note = (current.get("timing_note") if current is not None else "") or ""
    src = "天道"
    if lvl not in TIMING_LEVELS:
        ex = getattr(state, "_decree_execute_ai", None)
        ex = ex if slot_is_current(state, ex) else None
        ex_lvl = _as_str(ex.get("execution_timing")) if isinstance(ex, dict) else None
        if ex_lvl in TIMING_LEVELS:
            lvl = ex_lvl
            note = ex.get("timing_note") or ""
            src = "天道(执行契约)"
    if lvl not in TIMING_LEVELS:
        for fn in reversed(_TIMING_PROVIDERS):
            before = _state_probe(state)
            try:
                cand = fn(state, decree_kind)
            except Exception:  # noqa: BLE001 — 可选层：provider 出错不得阻断结算
                log.warning("时效 provider 抛错（已忽略，回落效果键表）", exc_info=True)
                continue
            if not _guard_state_readonly(state, before, "时效 provider"):
                continue
            cand_lvl = _as_str(cand.get("execution_timing")) if isinstance(cand, dict) else None
            if cand_lvl in TIMING_LEVELS:
                lvl = cand_lvl
                note = cand.get("note") or ""
                src = "天道(provider)"
                break
    if lvl in TIMING_LEVELS:
        return {"timing": TIMING_LEVELS[lvl], "source": src, "note": note, "level": lvl}
    timing, reason = classify_decree_timing(decree_kind)
    return {"timing": timing, "source": "程序(效果键表)", "note": reason, "level": None}


_TIMING_PROVIDERS: list = []


def register_timing_provider(fn) -> None:
    """注册时效档位提供者（**仅插件/测试用**；现有生产代码零注册方，全审 R-AI-8）。

    纪律同 `register_attitude_provider`：纯函数（只读 state）、异常必须留痕、
    重复注册去重（模块级列表跨局共享 ⇒ 叠加会串档）。
    """
    if not callable(fn):
        log.warning("register_timing_provider 收到非可调用对象，已忽略：%r", fn)
        return
    if any(f is fn for f in _TIMING_PROVIDERS):
        log.warning("register_timing_provider 重复注册（同一函数），已忽略")
        return
    _TIMING_PROVIDERS.append(fn)

def resolve_decree_duration(state, *, ability: Optional[float] = None,
                            followup: Optional[int] = None,
                            prestige: Optional[float] = None,
                            decree_kind: str = "", beneficiary: str = "") -> Dict[str, Any]:
    """返回 {months, base, pace, attitude, breakdown, source}；**纯函数**（无随机）。"""
    pace, source = _pace_from_ai(state)
    base = BASE_MONTHS[pace]
    att = resolve_execution_attitude(state, decree_kind=decree_kind, beneficiary=beneficiary)
    am, an = _ability_mult(ability)
    pm, pn = _prestige_mult(state.prestige if prestige is None else prestige)
    fm, fn = _followup_mult(followup)
    _tm = resolve_decree_timing(state, decree_kind)
    timing, timing_reason = _tm["timing"], _tm["note"]
    w = FACTOR_WEIGHTS
    # （权重显式、和=1 ⇒ 结果落在各因素区间内；再对总乘数夹取，双重防爆）
    mult = ((att["mult"] ** w["attitude"]) * (am ** w["ability"])
            * (pm ** w["prestige"]) * (fm ** w["followup"]))
    mult = max(MULT_MIN, min(MULT_MAX, mult))
    raw = base * mult
    if timing == "immediate":
        # 即时诏令：本回合办妥（monhts=1）；拖延不打月数，而是**execution_completion 打折**
        months = 1
    elif timing == "short":
        months = max(1, min(3, int(round(3 * mult))))
    else:
        months = max(MONTHS_MIN, min(MONTHS_MAX, int(round(raw))))
    # 缺档（天道未判态度）时**不回落 1.00**（= 最完美执行）：缺失就报 None，面板/复盘
    # 显示"未定义"（R-AI-9；消费方 settlement_decree 只把它写进 `pay_system` 作复盘读数、
    # 不参与数值运算，故 None 安全）。非 str 档位同样按缺失处理（防 dict.get TypeError）。
    _att_lvl = _as_str(att.get("level"))
    completion = ATTITUDE_COMPLETION.get(_att_lvl) if _att_lvl in ATTITUDE_COMPLETION else None
    return {
        "months": months,
        "base": base,
        "pace": pace,
        "source": source,
        "timing": timing,
        "timing_source": _tm["source"],
        "timing_reason": timing_reason,
        "execution_completion": completion,
        "attitude": att,
        "breakdown": {
            "attitude": {"mult": att["mult"], "note": att["note"], "source": att["source"]},
            "ability": {"mult": am, "note": an, "value": ability},
            "prestige": {"mult": pm, "note": pn,
                         "value": getattr(state, "prestige", prestige)},
            "followup": {"mult": fm, "note": fn, "value": followup},
            "weighted_mult": round(mult, 4),
            "weights": dict(w),
            "raw": round(raw, 2),
        },
    }


def duration_breakdown(state, **kw) -> Dict[str, Any]:
    return resolve_decree_duration(state, **kw)
