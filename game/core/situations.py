# -*- coding: utf-8 -*-
"""宋祚 · 局势投影层（core/situations.py）—— **v1：纯只读，不落库**

依据：《宋祚局势系统实施规范》§1.1 / §2 / §8 / §11.2。

## 纪律（硬）
1. **只读**：不新增任何 `state` 字段，不写 POP / 国库 / 内帑 / 州县 / 局势；
2. **只生成 `SituationReadout`（内存投影）**，对 `legacy` / `focus` / `free_effect` **不得**生成持久化
   Record —— 唯一权威源仍是各原模块（`legacy_mechanic` / `focus_mechanic` / `free_effect`）；
3. **缺失维度一律 `None`**（前端显示"未定义"），**禁止**字段语义顶替
   （不得把 `cost_per_month` 当持续代价、把 `clear_desc` 当"达成条件"）；
4. 不投影的来源按 `NON_PROJECTED_SOURCES` 显式列出（该常量为**代码事实**，测试直接读它，不复述文档）。

## 量纲注意（易错）
- `state.legacies[k].progress` 是 **0–1 的消除进度**；
- `state.active_focus.progress` 是 **0–100 的工期进度**。
  两者量纲不同，投影时分别换算，不得混用。

## POP 维度（宋祚核心，勿省略）
宋祚每路有 6 类 POP（农 / 士绅 / 工匠 / 商人 / 官僚 / 兵），各路的 `size`/`wealth`/`grain`
**互不相同**，另有子池（士绅 `clan` = 宗室、官僚 `clerks` = 吏）。
故 severity 不由"省均值"决定，而是由**该路 POP 结构**派生（最窘阶级相对加权均值的缺口），
并把这些差异以 `pop_highlights` 下发给面板解释——**同一事件在不同路得到不同严重度**。

## POP 的非经济维度 → **执行度**（勿只当经济数据）
POP 带来的模拟不止钱粮，至少还有四条非经济通道（各自有唯一权威，投影层只读不重算）：
  ① **吏治**（`core/clerks.py`）：吏怨 / 把持度 → 政令折扣 `decree_execution_mult`；
  ② **官制**（`core/officialdom.py`）：待阙堆积 / 冗官 → 「官多而事不举」；
  ③ **派系**（`state.factions[*].satisfaction`）：官员/士绅满意度 → 会签配合度；
  ④ **兵**（`core/army_models.military_channels`）：军心 / 训练 / 装备 / **欠饷** → 军队督行系数。
**下了诏 ≠ 办了事**：一道诏令的实际效果 = 会签执行率 × 吏治折扣 × 军队督行。
这些变数由 `execution_channels` / `pop_channels` 下发，**由 AI 权衡**（AI 给档位与叙事，
数值一律由程序按 core 内公式算）——投影层禁止自行发明系数。
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from content.data import GRAIN_CONSUME_PER_CAPITA, PREFECTURE_LIST
from core.numeric import parse_number as _finite, clamp as _clamp

log = logging.getLogger("situations")

__all__ = ["NON_PROJECTED_SOURCES", "build_situation_readout", "SEVERITY_RULES",
           "SNAPSHOT_METRICS", "ALLOWED_OPS", "MAX_CONDITION_DEPTH", "GRADE_DELTA",
           "ConditionError", "validate_condition", "used_metrics", "evaluate",
           "grade_delta", "advance_bar", "describe_condition",
           # v2
           "ORIGIN_KINDS", "RECORD_STATUSES", "TERMINAL_STATUSES", "PROGRESS_MODES",
           "RECORD_REQUIRED", "RECORD_DEFAULTS", "situation_key", "make_record",
           "validate_record", "normalize_record", "is_terminal", "find_duplicate",
           "next_status", "SITUATION_EFFECT_PATHS", "SITUATION_REASONS",
           "validate_situation_effects", "effects_to_changes",
           "INTENT_KINDS", "KIND_PRIORITY", "MAX_INTENTS_PER_TURN", "make_intent",
           "validate_intent", "pick_intents", "filter_grade_payload"]

# ---------------------------------------------------------------------------
# 不投影清单（代码常量；v2 若解除须同时删条目并补测试）
# ---------------------------------------------------------------------------
NON_PROJECTED_SOURCES: Dict[str, str] = {
    "decree": "active_decrees 月末整表替换缺陷（审查 A-13）未确认修复",
    "internal_effect": "无玩家可见语义（由来源侧 visible 标记控制）",
    "closed_event": "已结事件仅入朝报历史",
}

# ---------------------------------------------------------------------------
# severity 规则（确定性常量，便于断言与解释）
# ---------------------------------------------------------------------------
SEVERITY_RULES: Dict[str, Any] = {
    "legacy_min": 50,        # 已接近解除
    "legacy_span": 40,       # 未推进则 +40 → 上限 90
    "focus": 30,             # 在办大策：是进程，不是威胁
    "free_effect": 25,       # 长期诏：主动政策
    "event": 70,             # 活跃事件：需立即处置（再按地区/ POP 调整）
}

# v1 快照所需的 metric（POP 级 + 地区级 + **六类 POP 的非经济维度**；
# 见 situation_metrics 注册表与 POP_SENTIMENT_CHANNELS）
SNAPSHOT_METRICS: List[str] = [
    # 经济维度
    "region.unrest",
    "pop.wealth_per_capita",
    "pop.size",
    # 非经济维度：农（民心）/ 士绅（抵抗·窖藏） / 工匠·商人（市面·欠缴）
    "region.public_support",
    "region.gentry_resistance",
    "region.fiscal",
    # 识字率（2026-09-19 新增设定）：诏令效果的弱关联项之一
    "region.literacy",
    "literacy.national",
    "pop.literacy",
    "pop.arrears_ratio",
    "pop.hoard_ratio",
    # 非经济维度：官僚（冗官·待阙·派系满意度）
    "officials.redundant_rate",
    "officials.waiting_share",
    "faction.satisfaction",
    # 非经济维度：兵（军心·督行）与吏（吏怨·把持 → 政令折扣）
    "army.morale",
    "army.arrears",
    "army.enforcement_mult",
    "clerks.grievance",
    "clerks.grip",
    "clerks.execution_mult",
]

_PHASE_START = 1.0 / 3.0
_PHASE_MID = 2.0 / 3.0
_TIMELINE_LIMIT = 3


def _phase_from_ratio(ratio: Optional[float]) -> Optional[str]:
    """完成度 → 阶段（起 / 中 / 终前）；未知为 None。"""
    if ratio is None:
        return None
    r = _clamp(ratio, 0.0, 1.0)
    if r < _PHASE_START:
        return "起"
    return "中" if r < _PHASE_MID else "终前"


def _legacy_severity(progress01: float) -> int:
    """帝国修正：越未推进越严重（90 → 50）。"""
    p = _clamp(progress01, 0.0, 1.0)
    return int(round(SEVERITY_RULES["legacy_min"] + (1.0 - p) * SEVERITY_RULES["legacy_span"]))


def _fmt_cost(cost: Any) -> str:
    """把 cost dict 压成简短中文（只读展示，不做数值运算）。"""
    if not isinstance(cost, dict) or not cost:
        return "—"
    parts = []
    for k, v in list(cost.items())[:3]:
        try:
            num = float(v)
            parts.append(f"{k} {num:,.0f}")
        except (TypeError, ValueError):
            parts.append(f"{k} {v}")
    return "、".join(parts)


def _recent_log_timeline(state, needle: str) -> List[dict]:
    """从最近一月结算日志中筛出含 needle 的行（只读；最多 3 条）。"""
    if not needle:
        return []
    logs = getattr(state, "settlement_log", None) or []
    if not isinstance(logs, list) or not logs:
        return []
    turn = int(_finite(getattr(state, "turn", 0)))
    out: List[dict] = []
    last = logs[-1]
    for line in (last if isinstance(last, list) else []):
        text = str(line)
        if needle in text:
            out.append({"turn": turn, "kind": "报", "text": text[:120], "source": "program"})
            if len(out) >= _TIMELINE_LIMIT:
                break
    return out


def _event_history_timeline(state, title: str) -> List[dict]:
    """事件历史中与该事件同名的最近条目（只读；最多 3 条）。"""
    hist = getattr(state, "event_history", None) or []
    out: List[dict] = []
    if not isinstance(hist, list):
        return out
    for ev in hist[-20:]:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("title") or "") == title:
            out.append({"turn": int(_finite(ev.get("turn"), 0)), "kind": "节点",
                        "text": str(ev.get("message") or ev.get("title") or "")[:120],
                        "source": "program"})
    return out[-_TIMELINE_LIMIT:]


# ---------------------------------------------------------------------------
# POP 结构派生（宋祚核心：各路 POP 不同 → 同一规则给出不同结果）
# ---------------------------------------------------------------------------
def _match_region(title: str) -> Optional[str]:
    """标题中是否出现某个州路名（用于把事件关联到地区读数）。"""
    if not title:
        return None
    best: Optional[str] = None
    for name in PREFECTURE_LIST:
        if name and name in title:
            if best is None or len(name) > len(best):
                best = name          # 取最长匹配，避免"京畿"命中"京畿路"的歧义
    return best


def _route_pop_stats(snapshot: dict, route: str) -> Optional[dict]:
    """某路的 POP 结构摘要（只读，来自快照；不重算）。

    - `poorest`/`richest`：人均财富最低/最高的阶级（仅在 `size>0` 的阶级间比较）；
    - `avg`：按 `size` 加权的人均财富。
    """
    metrics = (snapshot or {}).get("metrics") or {}
    wpc_table = metrics.get("pop.wealth_per_capita") or {}
    size_table = metrics.get("pop.size") or {}
    rows = []
    for key, wpc in wpc_table.items():
        if not isinstance(key, str) or "|" not in key or wpc is None:
            continue
        r, _, cls = key.partition("|")
        if r != route:
            continue
        size = _finite(size_table.get(key))
        if size <= 0:
            continue
        rows.append((cls, _finite(wpc), size))
    if not rows:
        return None
    rows.sort(key=lambda x: x[1])
    total_size = sum(r[2] for r in rows)
    avg = (sum(r[1] * r[2] for r in rows) / total_size) if total_size > 0 else 0.0
    return {"poorest": rows[0], "richest": rows[-1], "avg": avg}


def _pop_highlights(snapshot: dict, route: Optional[str]) -> Optional[List[str]]:
    """把该路 POP 结构压成两行中文（最窘/最丰），供面板解释"为何这条局势紧迫"。"""
    if not route:
        return None
    stats = _route_pop_stats(snapshot, route)
    if not stats:
        return None
    p_cls, p_wpc, _ = stats["poorest"]
    r_cls, r_wpc, _ = stats["richest"]
    return [f"{p_cls} 人均 {p_wpc:,.1f} 贯（最窘）",
            f"{r_cls} 人均 {r_wpc:,.1f} 贯（最丰）"]


def _metric(snapshot: dict, key: str, arg: Optional[str] = None):
    """从快照取 metric 值（一次取值；缺失 → None，不回落 0）。"""
    return ((snapshot or {}).get("metrics") or {}).get(key, {}).get(arg)


def _non_economic_stress(snapshot: dict, route: Optional[str]) -> float:
    """POP 非经济压力（0–18），用于事件严重度加成——**确定性、可解释**：

        吏怨   = 该路 `clerks.route_grievance`（缺失回落全国 `clerks.grievance`）
        军心   = 该路 `army.morale`（缺失回落全国 `army.morale`），越低越重
        士绅   = 该路 `region.gentry_resistance`

    语义：钱粮充足但**吏怨沸腾、军心涣散、士绅抗命**的路，同一起事件更紧迫
    （「民力已竭而官不能办」）。缺失维度按 0 计（不编造）。
    """
    stress = 0.0
    clerks = (snapshot or {}).get("clerks") or {}
    grie = _metric(snapshot, "clerks.route_grievance", route)
    if grie is None:
        grie = _metric(snapshot, "clerks.grievance")
    if grie is not None:
        stress += _clamp(_finite(grie), 0.0, 100.0) / 100.0 * 8.0
    morale = _metric(snapshot, "army.morale", route) if route else None
    if morale is None:
        army = (snapshot or {}).get("army") or {}
        morale = army.get("morale")
    if morale is not None:
        stress += (1.0 - _clamp(_finite(morale, 100.0), 0.0, 100.0) / 100.0) * 6.0
    gentry = _metric(snapshot, "region.gentry_resistance", route) if route else None
    if gentry is not None:
        stress += max(0.0, _clamp(_finite(gentry, 0.0), 0.0, 100.0) - 30.0) / 70.0 * 4.0
    if not clerks:
        stress = min(stress, 6.0)          # 吏制读数缺失时不得假装「吏怨极重」
    return round(stress, 2)


def _execution_channels(state, snapshot: dict, route: Optional[str],
                        text: str = "") -> Optional[dict]:
    """**诏令实际效果通道**（口径单点在 `core/decree_effect.py`，此处只做投影组装）。

    用户定稿（2026-09-19）：实际效果 = **吏治（强关联，唯一强关联）** × 民心/文书（弱）×
    [仅军政/边事类] 军队督行（**条件加成，不是必须**）。会签执行率本身即吏治的表达，
    故其盘面代理（派系满意度）随行下发并标注 `proxy`——**不伪造逐诏执行率**。
    """
    if state is None:
        return None
    try:
        from core.decree_effect import effect_channels
        ch = effect_channels(state, text=text, route=route)
    except Exception as e:  # noqa: BLE001
        log.warning("situations 取诏令效果通道失败：%s", e)
        return None
    mil = ch.get("military") or {}
    sup = ch.get("official_support") or {}
    return {
        # —— 强关联：吏治 ——
        "strong": ch.get("strong", "clerks"),
        "clerks_mult": ch.get("clerks_mult"),
        "clerks_grievance": (ch.get("clerks") or {}).get("grievance"),
        "clerks_grip": (ch.get("clerks") or {}).get("grip"),
        "clerks_quality": (ch.get("clerks") or {}).get("quality"),
        # 会签执行率的盘面代理（proxy=True：逐诏执行率需该诏立场，此处不得当执行率）
        "official_support": sup,
        # —— 弱关联：民心 / 文书到账 ——
        "civil_mult": ch.get("civil_mult"),
        # —— 条件加成：军队（仅军政/边事类）——
        "kind": ch.get("kind"),
        "military_mult": mil.get("mult"),
        "military_applies": bool(mil.get("applies")),
        "military_route": route,
        "military_reason": mil.get("reason"),
        # —— 合成 ——
        "combined_mult": ch.get("effect_mult"),
        "faction_min": sup.get("min"),
        "faction_min_name": sup.get("min_faction"),
        "note": ch.get("note", ""),
    }


def _literacy_block(snapshot: dict) -> dict:
    """**各地各类 POP 自有识字率**截面（按 size 加权的全国值 + 逐路逐类明细）。

    识字率是 POP 自有属性（`prefectures[路].pops[阶层].literacy`），故逐路逐类不同；
    全国值按各 POP `size` 加权**派生**（不落独立账本）。
    """
    table = ((snapshot or {}).get("metrics") or {}).get("pop.literacy") or {}
    size_table = ((snapshot or {}).get("metrics") or {}).get("pop.size") or {}
    nation: Dict[str, Any] = {}
    by_route: Dict[str, Dict[str, Any]] = {}
    classes = list(GRAIN_CONSUME_PER_CAPITA.keys()) if isinstance(GRAIN_CONSUME_PER_CAPITA, dict) else []
    for key, lit in table.items():
        if not isinstance(key, str) or "|" not in key:
            continue
        route, _, cls = key.partition("|")
        by_route.setdefault(route, {})[cls] = lit
        if lit is None:
            continue
        size = _finite(size_table.get(key))
        acc = nation.setdefault(cls, {"num": 0.0, "den": 0.0})
        acc["num"] += _finite(lit) * size
        acc["den"] += size
    nation_out: Dict[str, Any] = {}
    for cls, acc in nation.items():
        nation_out[cls] = round(acc["num"] / acc["den"], 2) if acc["den"] > 0 else None
    for cls in classes:
        nation_out.setdefault(cls, None)
    return {"nation": nation_out, "by_route": by_route}


def _pop_channels(snapshot: dict) -> dict:
    """**六类 POP 的非经济通道**截面（每类都有，不集中在官吏兵）。

    - `channels`：通道表本体（`POP_SENTIMENT_CHANNELS` + 吏子池），供前端/AI 读语义；
    - `nation`：全国截面（各类 primary + secondary）；
    - `by_route`：逐路 primary（**各省 POP 结构不同 → 心气不同**）。
    """
    from core.situation_metrics import CLERK_SENTIMENT_CHANNELS, POP_SENTIMENT_CHANNELS as _CH
    factions = (snapshot or {}).get("factions") or {}
    f_min = min(factions.values()) if factions else None
    f_min_name = min(factions, key=lambda k: factions[k]) if factions else None
    army_nation = (snapshot or {}).get("army") or {}
    clerks_view = (snapshot or {}).get("clerks") or {}

    def _route_primary(route: str) -> Dict[str, Any]:
        return {
            "农": _metric(snapshot, "region.public_support", route),
            "士绅": _metric(snapshot, "region.gentry_resistance", route),
            "工匠": _metric(snapshot, "region.fiscal", route),
            "商人": _metric(snapshot, "region.fiscal", route),
            "官僚": _metric(snapshot, "officials.redundant_rate"),
            "兵": _metric(snapshot, "army.morale", route),
            "吏": _metric(snapshot, "clerks.route_grievance", route),
            # 跨类指标（不属于某一 POP，但影响所有诏令的落地）：识字率
            "识字率": _metric(snapshot, "region.literacy", route),
        }

    def _agg(key: str) -> Optional[Dict[str, Any]]:
        """区域类指标的全国截面：只给「最低 / 均值」，**不**取 arg=None（那恒为缺失）。"""
        vals = [v for v in ((snapshot or {}).get("metrics") or {}).get(key, {}).values()
                if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if not vals:
            return None
        return {"最低": round(min(vals), 1), "均": round(sum(vals) / len(vals), 1)}

    routes = sorted((snapshot or {}).get("clerks_routes", {}) or {}) or list(PREFECTURE_LIST)
    return {
        "channels": {**_CH, "吏": dict(CLERK_SENTIMENT_CHANNELS)},
        "nation": {
            "农": {"民心": _agg("region.public_support")},
            "士绅": {"抵抗": _agg("region.gentry_resistance"),
                     "窖藏率": _agg("pop.hoard_ratio")},
            "工匠": {"市面": _agg("region.fiscal"), "欠缴率": _agg("pop.arrears_ratio")},
            "商人": {"市面": _agg("region.fiscal"), "欠缴率": _agg("pop.arrears_ratio")},
            "官僚": {"冗官率": _metric(snapshot, "officials.redundant_rate"),
                     "待阙率": _metric(snapshot, "officials.waiting_share"),
                     "最低派系满意度": f_min, "最低派系": f_min_name},
            "兵": {"军心": army_nation.get("morale"),
                   "欠饷": army_nation.get("arrears"),
                   "督行系数": army_nation.get("enforcement_mult")},
            "吏": {"吏怨": _metric(snapshot, "clerks.grievance"),
                   "把持度": _metric(snapshot, "clerks.grip"),
                   "有效吏力": clerks_view.get("effective"),
                   "政令折扣": _metric(snapshot, "clerks.execution_mult")},
            # 跨类指标（非某一 POP 专有）：识字率——政令"写得下去、读得懂"的基础
            "识字率": {"全国": _metric(snapshot, "literacy.national")},
        },
        # **各地各类 POP 自有识字率**（用户定稿：识字率是各地 POP 自有的属性）
        "literacy": _literacy_block(snapshot),
        "by_route": {r: _route_primary(r) for r in routes},
    }


def _event_severity(title: str, snapshot: dict) -> int:
    """事件严重度（确定性规则，体现各省 POP 差异）：

        severity = clamp(70 + (unrest − 50)×0.3 + pop_stress×20 + noneco_stress, 30, 100)

    - `pop_stress = clamp((该路加权人均财富 − 最窘阶级人均财富) / 加权人均, 0, 1)`（**经济**维度）；
    - `noneco_stress` = 吏怨 / 军心 / 士绅抵抗（**非经济**维度，见 `_non_economic_stress`）。
    标题未关联州路 → 只吃全国吏怨与军心（不编造地区维度）。
    """
    base = float(SEVERITY_RULES["event"])
    name = _match_region(title)
    if name is None:
        return int(round(_clamp(base + _non_economic_stress(snapshot, None), 30.0, 100.0)))
    metrics = (snapshot or {}).get("metrics") or {}
    unrest = (metrics.get("region.unrest") or {}).get(name)
    stats = _route_pop_stats(snapshot, name)
    stress = 0.0
    if stats and stats["avg"] > 0:
        stress = _clamp((stats["avg"] - stats["poorest"][1]) / stats["avg"], 0.0, 1.0)
    sev = base
    if unrest is not None:
        sev += (_finite(unrest) - 50.0) * 0.3
    sev += stress * 20.0
    sev += _non_economic_stress(snapshot, name)
    return int(round(_clamp(sev, 30.0, 100.0)))


# ---------------------------------------------------------------------------
# 各来源投影（严格对照规范 §2.1 映射表）
# ---------------------------------------------------------------------------
def _project_legacies(state, errors: List[str], snapshot: dict) -> List[dict]:
    legs = getattr(state, "legacies", None)
    if not isinstance(legs, dict):
        if legs is not None:
            errors.append("legacies: 结构非 dict，已跳过")
        return []
    out: List[dict] = []
    for key, entry in legs.items():
        if not isinstance(entry, dict):
            errors.append(f"legacies[{key}]: 条目非 dict，已跳过")
            continue
        progress01 = _clamp(_finite(entry.get("progress")), 0.0, 1.0)
        cleared = bool(entry.get("cleared"))
        active = bool(entry.get("active"))
        status = "resolved" if cleared else ("active" if active else "cancelled")
        name = str(entry.get("name") or key)
        clear_desc = entry.get("clear_desc")
        out.append({
            "id": f"legacy:{key}",
            "title": name,
            "source": "legacy",
            "status": status,
            "bar_value": int(round(progress01 * 100)),          # 0–1 → 0–100
            "resolve_condition_text": f"解除：{clear_desc}" if clear_desc else None,
            "fail_condition_text": None,                        # 未定义，不编造
            "ongoing_text": None,                               # 禁止把 effect 当持续代价
            "progress_text": None,
            "severity": _legacy_severity(progress01),
            "phase": _phase_from_ratio(progress01),
            "region_hint": None,
            "faction_hint": None,
            "pop_highlights": None,                             # 帝修不绑定单一路
            "timeline": _recent_log_timeline(state, name),
        })
    return out


def _project_focus(state, errors: List[str], snapshot: dict) -> List[dict]:
    af = getattr(state, "active_focus", None)
    if not isinstance(af, dict) or af.get("status") != "in_progress":
        return []
    progress100 = _clamp(_finite(af.get("progress")), 0.0, 100.0)   # 已于 0–100
    cost = _finite(af.get("cost_per_month"))
    return [{
        "id": f"focus:{af.get('node_key') or af.get('name') or 'unnamed'}",
        "title": str(af.get("name") or "国策"),
        "source": "focus",
        "status": "active",
        "bar_value": int(round(progress100)),
        "resolve_condition_text": None,
        "fail_condition_text": None,
        "ongoing_text": None,                               # focus 无持续代价
        "progress_text": f"月耗 {cost:,.0f} 贯",            # 推进成本 ≠ 持续代价
        "severity": SEVERITY_RULES["focus"],
        "phase": _phase_from_ratio(progress100 / 100.0),
        "region_hint": None,
        "faction_hint": None,
        "pop_highlights": None,
        "timeline": _recent_log_timeline(state, str(af.get("name") or "")),
    }]


def _project_longterm_effects(state, errors: List[str], snapshot: dict) -> List[dict]:
    items = getattr(state, "longterm_effects", None)
    if not isinstance(items, list):
        if items is not None:
            errors.append("longterm_effects: 结构非 list，已跳过")
        return []
    out: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            errors.append("longterm_effects: 条目非 dict，已跳过")
            continue
        name = str(item.get("name") or "长期制度")
        duration = int(_finite(item.get("duration"), 0))
        out.append({
            "id": f"free_effect:{name}",
            "title": name,
            "source": "free_effect",
            "status": "active",
            "bar_value": None,                                  # 无进度
            "resolve_condition_text": None,
            "fail_condition_text": None,
            "ongoing_text": None,                               # cost 是执行成本，不是持续代价
            "progress_text": f"执行成本 {_fmt_cost(item.get('cost'))}"
                             + ("（永久）" if duration == 0 else f"，余 {duration} 月"),
            "severity": SEVERITY_RULES["free_effect"],
            "phase": None,
            "region_hint": None,
            "faction_hint": None,
            "pop_highlights": None,
            "timeline": _recent_log_timeline(state, name),
        })
    return out


def _project_events(state, errors: List[str], snapshot: dict) -> List[dict]:
    evs = getattr(state, "active_events", None)
    if not isinstance(evs, list):
        if evs is not None:
            errors.append("active_events: 结构非 list，已跳过")
        return []
    out: List[dict] = []
    for ev in evs:
        if not isinstance(ev, dict):
            errors.append("active_events: 条目非 dict，已跳过")
            continue
        title = str(ev.get("title") or "事件")
        region = _match_region(title)
        out.append({
            # v1 只读投影：事件对象无稳定 id，暂以标题作 ref；
            # v2 立项须改用真实事件实例 id（规范 §1.4 幂等键）
            "id": f"event:{title}",
            "title": title,
            "source": "event",
            "status": "active",
            "bar_value": None,
            "resolve_condition_text": None,
            "fail_condition_text": None,
            "ongoing_text": None,
            "progress_text": None,
            "severity": _event_severity(title, snapshot),
            "phase": None,
            "region_hint": region,
            "faction_hint": None,
            "pop_highlights": _pop_highlights(snapshot, region),
            "timeline": _event_history_timeline(state, title),
        })
    return out


def _channel_highlights(snapshot: dict, route: Optional[str]) -> Optional[List[str]]:
    """POP **非经济**维度的两行中文摘要（与 `pop_highlights` 经济维度并列，供面板解释）。"""
    bits: List[str] = []
    grie = _metric(snapshot, "clerks.route_grievance", route) if route else None
    if grie is None:
        grie = _metric(snapshot, "clerks.grievance")
    mult = _metric(snapshot, "clerks.execution_mult")
    if grie is not None:
        tail = f"，政令折扣 ×{_finite(mult, 1.0):.2f}" if mult is not None else ""
        bits.append(f"吏怨 {_finite(grie):.1f}{tail}")
    army = (snapshot or {}).get("army_routes", {}).get(route or "") or (snapshot or {}).get("army") or {}
    if army.get("morale") is not None:
        bits.append(f"军心 {_finite(army.get('morale')):.0f}"
                    f"、欠饷 {int(_finite(army.get('arrears'))):,} 贯"
                    f"（督行 ×{_finite(army.get('enforcement_mult'), 1.0):.2f}）")
    gentry = _metric(snapshot, "region.gentry_resistance", route) if route else None
    if gentry is not None:
        bits.append(f"士绅抵抗 {_finite(gentry):.0f}")
    return bits[:3] or None


# ---------------------------------------------------------------------------
# 条件 DSL（规范 §3.1–§3.4）—— **纯函数：不接收 state、不访问全局、不写任何字段**
# ---------------------------------------------------------------------------
# v1 落地的理由：DSL 本身只是"判定语义 + 校验器"，不含任何状态写入；
# v2 的 `_settle_situations` 直接调用本段即可，无需再改语义（单一权威）。
ALLOWED_OPS: tuple = (">=", "<=", ">", "<", "==", "!=")
MAX_CONDITION_DEPTH = 3
_NODE_KEYS = ("metric", "arg", "op", "value")
_GROUP_KEYS = ("all", "any", "streak")

# 档位 → Δbar 唯一映射（规范 §4.2.1）
GRADE_DELTA: Dict[str, int] = {
    "verybad": -8, "bad": -4, "normal": 0, "good": 5, "verygood": 10,
}


class ConditionError(ValueError):
    """条件结构非法（建单期即拒绝，不建局势）。"""


def validate_condition(condition: Any, _depth: int = 0, _is_root: bool = True) -> List[str]:
    """校验条件结构（规范 §3.1/§3.2）；返回错误清单，空 = 合法。

    规则：`all`/`any` 二选一且为 list；`streak` **仅根节点**；嵌套深度 ≤ 3；
    `op` 属白名单；`metric` 必须已注册且参数齐备；节点键取白名单。
    """
    errs: List[str] = []
    from core.situation_metrics import METRICS

    if _depth > MAX_CONDITION_DEPTH:
        return [f"嵌套深度超过 {MAX_CONDITION_DEPTH}"]
    if not isinstance(condition, dict):
        return ["condition 必须是 dict"]
    groups = [k for k in ("all", "any") if k in condition]
    if len(groups) > 1:
        return ["`all` 与 `any` 不得同时出现"]
    if not groups:
        # 叶子节点
        unknown = [k for k in condition if k not in _NODE_KEYS]
        if unknown:
            errs.append(f"未知键：{unknown}")
        metric = condition.get("metric")
        if not isinstance(metric, str) or not metric:
            errs.append("缺少 metric")
        else:
            spec = METRICS.get(metric)
            if spec is None:
                errs.append(f"未注册 metric：{metric}")
            else:
                arg = condition.get("arg")
                if spec.required_arg and (arg is None or not isinstance(arg, str)):
                    errs.append(f"{metric} 需要 arg（{spec.arg_type}）")
                if arg is not None and not isinstance(arg, str):
                    errs.append("arg 必须是字符串")
        op = condition.get("op")
        if op not in ALLOWED_OPS:
            errs.append(f"非法 op：{op!r}（应为 {ALLOWED_OPS}）")
        if "value" not in condition:
            errs.append("缺少 value")
        else:
            v = condition.get("value")
            if not isinstance(v, (bool, str)) and not isinstance(v, (int, float)):
                errs.append("value 只能是 bool / str / 数值")
            elif isinstance(v, float) and not math.isfinite(v):
                errs.append("value 不得为 NaN/Infinity")
        return errs

    key = groups[0]
    items = condition.get(key)
    if not isinstance(items, list):
        errs.append(f"{key} 必须是 list")
        return errs
    for i, sub in enumerate(items):
        errs.extend(f"{key}[{i}]: {e}" for e in validate_condition(sub, _depth + 1, False))
    if "streak" in condition:
        if not _is_root:
            errs.append("`streak` 仅允许出现在根节点")
        else:
            s = condition.get("streak")
            if not isinstance(s, int) or isinstance(s, bool) or s < 1:
                errs.append("streak 必须是 ≥1 的整数")
    extra = [k for k in condition if k not in _GROUP_KEYS]
    if extra:
        errs.append(f"分组节点含未知键：{extra}")
    return errs


def used_metrics(condition: Any) -> List[str]:
    """条件树用到的 metric（去重、稳定升序）；供快照按需取值与诊断。"""
    found: List[str] = []

    def walk(node) -> None:
        if not isinstance(node, dict):
            return
        if "metric" in node:
            m = node.get("metric")
            if isinstance(m, str) and m not in found:
                found.append(m)
            return
        for key in ("all", "any"):
            for sub in (node.get(key) or []):
                walk(sub)
    walk(condition)
    return sorted(found)


def _snapshot_value(snapshot: Any, metric: str, arg):
    """从快照取 metric 值；结构非法或键缺失 → `(None, False 存在)`。"""
    table = (snapshot or {}).get("metrics") if isinstance(snapshot, dict) else None
    if not isinstance(table, dict):
        return None, False
    col = table.get(metric)
    if not isinstance(col, dict):
        return None, False
    if arg not in col:
        return None, False
    return col.get(arg), True


def evaluate(condition: Any, snapshot: Any) -> bool:
    """纯函数判定（规范 §3.3/§3.4）：不接收 state、不访问全局、不写状态。

    - 空 `all: []` → True；空 `any: []` → False；
    - **缺失值（metric 未注册 / arg 无键 / 值为 None）→ 该节点 False 并记 warning**
      （规范 §3.2 缺失策略：不静默取 0）；
    - 类型不可比（如数值 op 遇到字符串）→ False 并记 warning；
    - `streak` 由 v2 结算侧处理（本函数只判当次命中，不持计数器）。
    """
    if not isinstance(condition, dict):
        log.warning("evaluate：condition 非 dict → False")
        return False
    for key in ("all", "any"):
        if key in condition:
            items = condition.get(key)
            if not isinstance(items, list):
                log.warning("evaluate：%s 非 list → False", key)
                return False
            if key == "all":
                return all(evaluate(sub, snapshot) for sub in items)
            return any(evaluate(sub, snapshot) for sub in items)

    metric = condition.get("metric")
    arg = condition.get("arg")
    op = condition.get("op")
    want = condition.get("value")
    if not isinstance(metric, str) or op not in ALLOWED_OPS:
        log.warning("evaluate：节点缺 metric/非法 op → False")
        return False
    value, present = _snapshot_value(snapshot, metric, arg)
    if not present or value is None:
        log.warning("evaluate：缺失值 %s(%s) → False（不静默取 0）", metric, arg)
        return False
    try:
        if op == "==":
            return bool(value == want)
        if op == "!=":
            return bool(value != want)
        if isinstance(want, bool) or isinstance(value, (bool, str)):
            log.warning("evaluate：%s 用数值 op 比较非数值 → False", metric)
            return False
        lhs, rhs = float(value), float(want)
    except (TypeError, ValueError, OverflowError) as e:
        log.warning("evaluate：%s(%s) 取值/比较失败 %s → False", metric, arg, type(e).__name__)
        return False
    if not (math.isfinite(lhs) and math.isfinite(rhs)):
        log.warning("evaluate：%s(%s) 含非有限值 → False", metric, arg)
        return False
    if op == ">=":
        return lhs >= rhs
    if op == "<=":
        return lhs <= rhs
    if op == ">":
        return lhs > rhs
    return lhs < rhs


_METRIC_CN: Dict[str, str] = {
    "region.unrest": "动乱", "region.public_support": "民心",
    "region.gentry_resistance": "士绅阻力", "region.fiscal": "市面", "region.mood": "民情",
    "treasury": "国库", "pop.wealth_per_capita": "人均财富", "pop.size": "人口",
    "pop.wealth": "持钱", "pop.grain": "存粮", "pop.arrears_ratio": "欠缴率",
    "pop.hoard_ratio": "窖藏率", "clerks.grievance": "吏怨", "clerks.grip": "把持度",
    "clerks.execution_mult": "政令折扣", "clerks.effective": "有效吏力",
    "officials.redundant_rate": "冗官率", "officials.waiting_share": "待阙率",
    "officials.waiting": "待阙官", "army.morale": "军心", "army.arrears": "欠饷",
    "army.enforcement_mult": "军队督行", "army.troops": "兵额",
    "faction.satisfaction": "派系满意度",
}


def describe_condition(condition: Any) -> str:
    """把条件树渲染成**玩家可读的中文**（规范 §2.1 的"成败条件全公开"）。

    只描述**规则与阈值**（规则可以公开），**不掺入任何当前盘面读数**——阈值文字与
    真实读数无关，故不违反 §7.1"禁止注入当前真实读数"。示例：
        {"all":[{metric:region.unrest,arg:陕西路,op:"<=",value:30}],"streak":2}
        → "全部满足，且连续 2 月：陕西路 动乱 ≤ 30"
    """
    if not isinstance(condition, dict):
        return "未定义"
    for key, label in (("all", "全部满足"), ("any", "任一满足")):
        if key in condition:
            subs = condition.get(key) or []
            body = "；".join(describe_condition(s) for s in subs) or "（空）"
            streak = condition.get("streak")
            tail = f"，且连续 {int(streak)} 月" if isinstance(streak, int) and streak > 1 else ""
            return f"{label}{tail}：{body}"
    metric = condition.get("metric")
    arg = condition.get("arg")
    op = condition.get("op")
    value = condition.get("value")
    name = _METRIC_CN.get(metric, str(metric).split(".")[-1] if isinstance(metric, str) else "?")
    where = f"{arg} " if arg else ""
    return f"{where}{name} {op} {value}"


def grade_delta(grade: Any) -> int:
    """档位 → Δbar（规范 §4.2.1）；非法档位 → 0（normal）并记 warning，不改变状态。"""
    if grade in GRADE_DELTA:
        return GRADE_DELTA[grade]
    log.warning("grade_delta：非法档位 %r → 0（按 normal 兜底）", grade)
    return 0


def advance_bar(bar: Any, grade: Any, inertia: float = 0.0,
                intent_bonus: float = 0.0, execution_mult: float = 1.0) -> int:
    """推进进度条（纯函数，规范 §4.2）：`clamp(bar + Δ, 0, 100)`。

        Δ = GRADE_DELTA[grade] + inertia + intent_bonus × execution_mult

    `execution_mult` 即**执行度**（会签 × 吏治 × 军队督行，见 §3.6）：**下了诏 ≠ 办了事**——
    玩家的意图加成要按实际执行能力打折；缺省 1.0 不改变既有语义。
    """
    base = _clamp(_finite(bar), 0.0, 100.0)
    gd = grade_delta(grade) if grade is not None else 0     # 无 AI 档位 → 纯 inertia 漂移
    d = gd + _finite(inertia) + _finite(intent_bonus) * _clamp(_finite(execution_mult, 1.0), 0.0, 2.0)
    return int(round(_clamp(base + d, 0.0, 100.0)))


# ---------------------------------------------------------------------------
# v2 · SituationRecord（规范 §1.2 / §1.4）—— 纯数据模型与校验，不写任何 state
# ---------------------------------------------------------------------------
# 唯一落库的局势类型是 `event_pool`；`legacy`/`focus`/`free_effect` **只生成 Readout**，
# 绝不生成 Record（规范 §10 第 2 条：禁止双写）。
ORIGIN_KINDS: tuple = ("event_pool",)
RECORD_STATUSES: tuple = ("active", "resolved", "failed", "cancelled")
TERMINAL_STATUSES: tuple = ("resolved", "failed", "cancelled")
PROGRESS_MODES: tuple = ("bar", "goal")

RECORD_REQUIRED: tuple = ("id", "title", "origin_kind", "origin_ref", "status",
                          "origin_turn", "last_settled_turn")
RECORD_DEFAULTS: Dict[str, Any] = {
    "bar_value": 0,
    "progress_mode": "bar",
    "resolve_condition": None,
    "fail_condition": None,
    "ongoing_cost": None,
    "progress_cost": None,
    "effect_on_resolve": None,
    "effect_on_fail": None,
    "assignee": None,
    "region_hint": None,
    "faction_hint": None,
    "cancellable": True,
    "inertia": 0,
    "streak_ok": 0,
    "streak_fail": 0,
    "deadline": None,
    "origin_turn": 0,
    "last_settled_turn": 0,
    "timeline": None,
}


def situation_key(origin_kind: str, origin_ref: str) -> str:
    """幂等键 `origin_kind:origin_ref`（规范 §1.2；首批禁止 occurrence 后缀）。"""
    return f"{origin_kind}:{origin_ref}"


def make_record(title: str, origin_ref: str, origin_turn: int, *,
                origin_kind: str = "event_pool", id: Optional[str] = None,
                **overrides) -> dict:
    """建一条 SituationRecord（补默认、生成幂等 id）；结构非法则抛 `ConditionError`。

    条件字段（`resolve_condition` / `fail_condition`）在此**即刻校验**——建单期即拒绝，
    避免把坏条件留到结算期炸（规范 §3.1："建单即拒绝，不建局势并记 error"）。
    """
    rec: Dict[str, Any] = dict(RECORD_DEFAULTS)
    rec.update({
        "id": id or situation_key(origin_kind, origin_ref),
        "title": str(title),
        "origin_kind": origin_kind,
        "origin_ref": str(origin_ref),
        "status": "active",
        "origin_turn": int(origin_turn),
        "last_settled_turn": -1,          # -1：从未结算（保证 origin_turn==turn 时也跳过推进）
        "timeline": [],
    })
    rec.update(overrides)
    if rec.get("progress_mode") == "goal":
        rec["bar_value"] = 0
    errs = validate_record(rec)
    if errs:
        raise ConditionError("；".join(errs))
    return rec


def validate_record(rec: Any) -> List[str]:
    """SituationRecord 结构校验（规范 §1.2/§1.4 + §9 载入校验共用）。"""
    errs: List[str] = []
    if not isinstance(rec, dict):
        return ["record 必须是 dict"]
    for k in RECORD_REQUIRED:
        if k not in rec:
            errs.append(f"缺必填键 {k}")
    if "id" in rec and not isinstance(rec["id"], str):
        errs.append("id 必须是 str")
    if rec.get("origin_kind") not in ORIGIN_KINDS:
        errs.append(f"origin_kind 非法：{rec.get('origin_kind')!r}（首批仅 {ORIGIN_KINDS}）")
    if rec.get("status") not in RECORD_STATUSES:
        errs.append(f"status 非法：{rec.get('status')!r}")
    if rec.get("progress_mode") not in PROGRESS_MODES:
        errs.append(f"progress_mode 非法：{rec.get('progress_mode')!r}")
    for k in ("origin_turn", "last_settled_turn", "streak_ok", "streak_fail", "inertia"):
        v = rec.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                              or (isinstance(v, float) and not math.isfinite(v))):
            errs.append(f"{k} 必须是数值")
    bar = rec.get("bar_value")
    if bar is not None:
        if isinstance(bar, bool) or not isinstance(bar, (int, float)):
            errs.append("bar_value 必须是数值或 None")
        elif not math.isfinite(float(bar)) or not (0 <= float(bar) <= 100):
            errs.append("bar_value 必须落在 0–100")
    for k in ("ongoing_cost", "progress_cost"):
        v = rec.get(k)
        if v is not None and not isinstance(v, dict):
            errs.append(f"{k} 必须是 dict 或 None（None = 未定义，禁止用别的字段顶替）")
    for k in ("resolve_condition", "fail_condition"):
        v = rec.get(k)
        if v is not None:
            errs.extend(f"{k}: {e}" for e in validate_condition(v))
    for k in ("effect_on_resolve", "effect_on_fail"):
        v = rec.get(k)
        if v is not None:
            errs.extend(f"{k}: {e}" for e in validate_situation_effects(v))
    tl = rec.get("timeline")
    if tl is not None and not isinstance(tl, list):
        errs.append("timeline 必须是 list")
    return errs


def normalize_record(rec: Any) -> dict:
    """补默认值（不改动已有键）；供旧档载入与建单共用。"""
    out = dict(RECORD_DEFAULTS)
    if isinstance(rec, dict):
        out.update(rec)
    if out.get("timeline") is None:
        out["timeline"] = []
    if out.get("bar_value") is None and out.get("progress_mode") == "bar":
        out["bar_value"] = 0
    return out


def is_terminal(rec: Any) -> bool:
    return isinstance(rec, dict) and rec.get("status") in TERMINAL_STATUSES


def find_duplicate(records, origin_kind: str, origin_ref: str) -> Optional[dict]:
    """幂等键查重（规范 §1.4：同 `origin_kind:origin_ref` 已存在即跳过）。"""
    target = situation_key(origin_kind, origin_ref)
    for rec in (records or []):
        if isinstance(rec, dict) and rec.get("id") == target:
            return rec
    return None


def next_status(rec: dict, fail_hit: bool, resolve_hit: bool) -> Dict[str, Any]:
    """按 §3.4 判定顺序更新 streak 并返回 `{"status":…, "conflict":bool,
    "streak_ok":int, "streak_fail":int}`（**纯函数**，不改 record）。

    顺序：② fail 命中则 streak_fail+1 否则归零；③ 达 fail.streak → failed；
    ④ 否则 resolve 命中则 streak_ok+1 否则归零，达 resolve.streak → resolved；
    ⑤ 同回合双双达线 → failed，并标记 conflict（结算侧写 kind="冲突" 的 timeline）。
    """
    fc = rec.get("fail_condition") or {}
    rc = rec.get("resolve_condition") or {}
    fs = int(fc.get("streak", 1) or 1) if isinstance(fc, dict) else 1
    rs = int(rc.get("streak", 1) or 1) if isinstance(rc, dict) else 1

    streak_fail = (int(rec.get("streak_fail", 0) or 0) + 1) if fail_hit else 0
    streak_ok = (int(rec.get("streak_ok", 0) or 0) + 1) if resolve_hit else 0
    fail_reached = fail_hit and streak_fail >= max(1, fs)
    resolve_reached = resolve_hit and streak_ok >= max(1, rs)

    status = "active"
    if fail_reached:
        status = "failed"
    elif resolve_reached:
        status = "resolved"
    return {
        "status": status,
        "conflict": bool(fail_reached and resolve_reached),
        "streak_fail": streak_fail,
        "streak_ok": streak_ok,
    }


# ---------------------------------------------------------------------------
# v2 · 效果契约（规范 §6.2）—— 局势专用**收窄**白名单
# ---------------------------------------------------------------------------
# 与 `engine/state_applier.VALID_PATHS` 同一 path 形式；本表是它的**子集**（收窄而非另立）：
# 首批仅允许钱/粮/声望/民心五类落点；`unrest` / `public_support` / `gentry_resistance` /
# `fiscal` / 税率 / `clerks.*` / `tax_base.*` **不在**其中（后续单独评审再加入）。
SITUATION_EFFECT_PATHS: tuple = (
    "treasury",
    "imperial_treasury",
    "granary",
    "prefectures.*.storage",
    "prefectures.*.pops.农.wealth",
    "prefectures.*.pops.士绅.wealth",
    "prefectures.*.pops.工匠.wealth",
    "prefectures.*.pops.商人.wealth",
    "prefectures.*.pops.官僚.wealth",
    "prefectures.*.pops.兵.wealth",
    "prefectures.*.pops.农.grain",
    "prefectures.*.pops.士绅.grain",
    "prestige",
    "population_satisfaction",
)
# 局势效果 reason 枚举（规范 §6.2）
SITUATION_REASONS: tuple = ("局势代价", "局势效果", "赈济", "损耗")


def _path_in(path: str, table) -> bool:
    for pat in table:
        if pat == path:
            return True
        p_parts, w_parts = str(path).split("."), pat.split(".")
        if len(p_parts) == len(w_parts) and all(
                w == "*" or w == p for w, p in zip(w_parts, p_parts)):
            return True
    return False


def validate_situation_effects(effects: Any) -> List[str]:
    """校验局势效果表（`{path: 数值}` 或 `[{path, op, value}]`）；返回错误清单。

    只做**结构与白名单**校验；守恒与原子写入由 `engine/state_applier.applier_pipeline`
    统一负责（规范 §6.1：程序效果与 AI 效果调用同一批量事务 API）。
    """
    errs: List[str] = []
    items = effects
    if isinstance(effects, dict):
        items = [{"path": k, "op": "add", "value": v} for k, v in effects.items()]
    if not isinstance(items, list):
        return ["effects 必须是 dict 或 list"]
    for i, ch in enumerate(items):
        if not isinstance(ch, dict):
            errs.append(f"effects[{i}] 必须是 dict")
            continue
        path = ch.get("path")
        op = ch.get("op", "add")
        if not isinstance(path, str) or not path:
            errs.append(f"effects[{i}]: 缺 path")
        elif not _path_in(path, SITUATION_EFFECT_PATHS):
            errs.append(f"effects[{i}]: 未注册路径 {path!r}（首批白名单见 SITUATION_EFFECT_PATHS）")
        if op not in ("add", "set"):
            errs.append(f"effects[{i}]: op 只能是 add/set，得到 {op!r}")
        v = ch.get("value")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            errs.append(f"effects[{i}]: value 必须是数值")
        elif isinstance(v, float) and not math.isfinite(v):
            errs.append(f"effects[{i}]: value 不得为 NaN/Infinity")
        if ch.get("reason") and ch["reason"] not in SITUATION_REASONS:
            errs.append(f"effects[{i}]: reason 非法 {ch['reason']!r}（枚举 {SITUATION_REASONS}）")
    return errs


def effects_to_changes(effects: Any, reason: str = "局势效果",
                       source_agent: str = "situations") -> List[dict]:
    """局势效果 → `state_applier` changes 列表（供同一批量事务 API 消费）。"""
    items = effects
    if isinstance(effects, dict):
        items = [{"path": k, "op": "add", "value": v} for k, v in effects.items()]
    out = []
    for ch in (items or []):
        if not isinstance(ch, dict):
            continue
        out.append({
            "path": ch.get("path"),
            "op": ch.get("op", "add"),
            "value": ch.get("value"),
            "reason": ch.get("reason") or reason,
            "source_agent": source_agent,
        })
    return out


# ---------------------------------------------------------------------------
# v2 · 玩家意图 SituationIntent（规范 §5）—— 纯逻辑
# ---------------------------------------------------------------------------
INTENT_KINDS: tuple = ("调兵", "拨帑", "赈济", "查办", "减免", "蠲赋")
KIND_PRIORITY: List[str] = ["调兵", "拨帑", "赈济", "查办", "减免", "蠲赋"]   # 索引小者优先
MAX_INTENTS_PER_TURN = 3


def make_intent(situation_id: str, kind: str, amount: float = 0.0,
                note: str = "", decree_id: Optional[str] = None) -> dict:
    """生成一条 intent（写在诏令对象上；诏令携带才有效）。"""
    return {
        "situation_id": str(situation_id),
        "kind": str(kind),
        "amount": float(amount or 0.0),
        "note": str(note or ""),
        "decree_id": decree_id,
        "consumed_turn": None,
        "validation_result": "pending",
    }


def _delta_of_journal(ch: dict) -> float:
    try:
        return float(ch.get("new")) - float(ch.get("old"))
    except (TypeError, ValueError):
        return 0.0


def validate_intent(intent: Any, journal) -> bool:
    """校验 intent 是否被**本回合实际发生的划转**支撑（规范 §5.2）。

    `journal` = 本回合 `state_applier` 事务记录（`CHANGE_LOG` 的本回合切片）；
    **只读它，不得由最终 state 反推**（否则"玩家点了按钮"就会自证成功）。
    规则（无对应变化即 `False`）：
      · 拨帑 / 赈济：存在 ≥ amount 的钱粮**成对**划转（国库/内帑付出 ＋ 民间或仓廪收入）
      · 调兵：存在 `defense_lines.*.garrison` 的实际变化
      · 查办：存在派系满意度/影响力的下降
      · 减免 / 蠲赋：存在民心（`mood`/`public_support`）上升或隐漏率下降
    """
    if not isinstance(intent, dict):
        return False
    if intent.get("kind") not in INTENT_KINDS:
        return False
    if not isinstance(intent.get("situation_id"), str) or not intent["situation_id"]:
        return False
    amount = _finite(intent.get("amount"), 0.0)
    if amount < 0:
        return False
    rows = [c for c in (journal or []) if isinstance(c, dict)]
    kind = intent["kind"]

    def _outflow(prefixes) -> float:
        return sum(-_delta_of_journal(c) for c in rows
                   if isinstance(c.get("path"), str)
                   and any(c["path"] == p or c["path"].startswith(p + ".") for p in prefixes)
                   and _delta_of_journal(c) < 0)

    def _inflow(pred) -> float:
        return sum(_delta_of_journal(c) for c in rows
                   if isinstance(c.get("path"), str) and pred(c["path"])
                   and _delta_of_journal(c) > 0)

    if kind in ("拨帑", "赈济"):
        paid = _outflow(("treasury", "imperial_treasury"))
        got = _inflow(lambda p: p.startswith("prefectures.") and (
            ".pops." in p or p.endswith(".storage"))) + \
            sum(_delta_of_journal(c) for c in rows
                if c.get("path") == "granary" and _delta_of_journal(c) > 0)
        return paid >= amount > 0 and got > 0
    if kind == "调兵":
        return any(isinstance(c.get("path"), str)
                   and c["path"].startswith("defense_lines.")
                   and c["path"].endswith(".garrison")
                   and abs(_delta_of_journal(c)) > 0 for c in rows)
    if kind == "查办":
        return any(isinstance(c.get("path"), str) and c["path"].startswith("factions.")
                   and (_delta_of_journal(c) < 0) for c in rows)
    # 减免 / 蠲赋
    return any(isinstance(c.get("path"), str)
               and (c["path"].endswith(".mood") or c["path"].endswith(".public_support"))
               and _delta_of_journal(c) > 0 for c in rows) or \
        any(c.get("path") == "land.hidden_rate" and _delta_of_journal(c) < 0 for c in rows)


def filter_grade_payload(payload: Any, known_ids) -> List[dict]:
    """AI 档位载荷的**白名单过滤**（规范 §7.2 的单点实现，供 AI 契约与测试共用）。

    白名单字段只有 `situation_id` / `grade` / `narrative`；
    **未知 id / 非法档位 / 缺字段 / 重复 id / 越权字段 → 该条丢弃**（不改任何状态）。
    """
    if not isinstance(payload, dict):
        return []
    raw = payload.get("grades")
    if not isinstance(raw, list):
        return []
    known = {str(k) for k in (known_ids or [])}
    out: List[dict] = []
    seen = set()
    for g in raw:
        if not isinstance(g, dict):
            continue
        sid = str(g.get("situation_id", ""))
        grade = str(g.get("grade", "")).strip()
        if sid not in known or sid in seen or grade not in GRADE_DELTA:
            continue
        seen.add(sid)
        nar = g.get("narrative")
        nar = None if nar is None else str(nar)[:120]
        out.append({"situation_id": sid, "grade": grade, "narrative": nar})
    return out


def pick_intents(intents, turn: int) -> List[dict]:
    """本回合有效的 intent（规范 §5.3）：未消费 → 同局势取 KIND_PRIORITY 最前 →
    按 `(turn, decree_id, situation_id)` 稳定排序取全局前 3。
    """
    live = [i for i in (intents or [])
            if isinstance(i, dict) and i.get("consumed_turn") is None
            and i.get("kind") in INTENT_KINDS]
    best: Dict[str, dict] = {}
    for i in live:
        sid = str(i.get("situation_id"))
        cur = best.get(sid)
        if cur is None or KIND_PRIORITY.index(i["kind"]) < KIND_PRIORITY.index(cur["kind"]):
            best[sid] = i
    ordered = sorted(best.values(),
                     key=lambda i: (int(turn), str(i.get("decree_id") or ""),
                                    str(i.get("situation_id") or "")))
    return ordered[:MAX_INTENTS_PER_TURN]


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
def build_situation_readout(state) -> dict:
    """构建局势 Readout 列表（**只读**）。

    返回 `{"items": [...], "by_status": {...}, "pop_channels": {...},
    "readout_status": "ok"|"partial", "readout_errors": [...]}`。
    每个 item 额外带 `execution_channels`（会签配合 / 吏治折扣 / 军队督行）与
    `channel_highlights`（非经济维度摘要）——**下了诏 ≠ 办了事**，由 AI 权衡这些变数。
    排序：`severity` 降序，次级键 `id` 升序（稳定）。
    """
    errors: List[str] = []
    snapshot: dict = {"metrics": {}}
    try:
        from core.situation_metrics import build_metric_snapshot
        snapshot, snap_errors = build_metric_snapshot(state, SNAPSHOT_METRICS)
        errors.extend(snap_errors)
    except Exception as e:  # noqa: BLE001  metric 层失败 → severity 回落基准，不中断面板
        errors.append(f"metric_snapshot: {type(e).__name__}")
        log.warning("situations 取 metric 快照失败：%s", e)

    items: List[dict] = []
    for fn in (_project_legacies, _project_focus, _project_longterm_effects, _project_events):
        try:
            items.extend(fn(state, errors, snapshot))
        except Exception as e:  # noqa: BLE001  单来源失败不影响其他来源
            errors.append(f"{fn.__name__}: {type(e).__name__}")
            log.warning("situations 投影失败（%s）：%s", fn.__name__, e)

    # 执行通道逐项下发（帝修不是「执行」对象 → 保持 None，不假装有执行度）
    for r in items:
        route = r.get("region_hint")
        if r.get("source") in ("focus", "free_effect", "event"):
            r["execution_channels"] = _execution_channels(
                state, snapshot, route, str(r.get("title") or ""))
            r["channel_highlights"] = _channel_highlights(snapshot, route)
        else:
            r["execution_channels"] = None
            r["channel_highlights"] = None

    try:
        pop_channels = _pop_channels(snapshot)
    except Exception as e:  # noqa: BLE001  通道表失败不得中断面板
        errors.append(f"pop_channels: {type(e).__name__}")
        pop_channels = {}
    # 利益集团 ⊆ POP：每个集团下发其 POP 基本盘（含母集占比）与「改革催生的新集团」
    try:
        from core.faction_basis import build_faction_channels
        faction_channels = build_faction_channels(state)
        if not faction_channels.get("declared", True):
            errors.append("faction_basis: 有集团未声明 POP 基本盘")
    except Exception as e:  # noqa: BLE001
        errors.append(f"faction_channels: {type(e).__name__}")
        faction_channels = {}

    items.sort(key=lambda r: (-int(r.get("severity") or 0), str(r.get("id") or "")))

    by_status: Dict[str, int] = {}
    for r in items:
        s = str(r.get("status") or "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    return {
        "items": items,
        "by_status": by_status,
        "pop_channels": pop_channels,
        "faction_channels": faction_channels,
        "readout_status": "partial" if errors else "ok",
        "readout_errors": errors,
    }
