# -*- coding: utf-8 -*-
"""天道决策日志 · 离线回测器（纯函数 + CLI；零网络 / 零 state 写入 / 零第三方依赖）。

定位
----
把 `state.decision_log`（由 `core.ai.tiandao_decision.decide_and_log` 写入的**只读观测副本**）
读出来做**离线**校准评测：Brier 均方误差、可靠性分箱与 ECE、命中率、驱动值单调性。
本模块**只消费**记录，不生成记录、不碰 `GameState`、不写任何文件（CLI 只打印）。

记录 schema（**由写入端定义，本模块只读，不改中文键名**）::

    {"turn": int, "objective": str, "verdict": Any, "probability": float|None,
     "defined": bool, "provider": str, "seed": int, "cached": bool,
     "facts_digest": str|None}

缺键一律按"缺失"处理（`None`），**不回落 0/1.0**；`facts_digest` 当前写入端可能尚无。

为什么必须有标签文件（**不许拿 verdict 自证**）
------------------------------------------------
`verdict` 是引擎自己的结论；用它当 ground truth 算 Brier/命中率属于**自证**，
总能算出漂亮数字却证明不了任何校准质量。所以没有标签时本模块**只报**概率分布与
覆盖率，`brier` / `ece` / `hit_rate` 一律返回 `None` 并附 `*_reason`
（纪律：缺失 ≠ 0 ≠ 1.0，严禁回落 0 / 1.0）。

🔴 **标签从哪来（2026-10-22 起）**：`core.ai.tiandao_labels`（纯逻辑）＋
`_dev_tools/game-dev/tools/tiandao_labels.py`（结算驱动 + CLI）用**反事实回放**产出——
逐月对每个 objective 的每个候选分支强制跑一个月，只在「唯一帕累托支配」时打标签
（不设权重、并列跳过）。用法：
`python _dev_tools/game-dev/tools/tiandao_labels.py --months 12 --out labels.json`。
⚠️ 它是**代理真值**（"事后看哪种做法让国计民生更好"），能度量校准与排序，不证明因果；
覆盖率天然有限（互有胜负的月份不出标签），`label_coverage` 会如实报。

标签文件格式（JSON，UTF-8）::

    {"labels": [
      {"objective": "waive_arrears", "turn": 3, "outcome": true},
      {"objective": "tax_stance", "turn": 4,
       "outcome_dist": {"strict": 0.1, "moderate": 0.8, "lenient": 0.1}}
    ]}

- `outcome`（bool）—— gate 类 objective 的二元真值；
- `outcome_dist`（{选项: 概率}）—— choose 类 objective，命中判据 = `verdict == argmax(outcome_dist)`；
- 两者可同时给：Brier 用 `outcome`；只给 `outcome_dist` 时 choose 的 Brier 取
  「top-1 置信度（记录里的 `probability` = max 选项概率）vs top-1 是否正确」；
- 匹配键 = `(objective, turn)`；同键重复标签**不覆盖**（保留第一条，计入
  `duplicate_labels`，宁可报可疑也不静默覆盖）；
- 标签可只覆盖部分记录：`labels_matched` / `label_coverage` 如实报未覆盖比例。

CLI::

    python -m core.ai.tiandao_backtest <save.json> [--labels labels.json] [--json]

（`core` 是 `game/` 下的包 ⇒ 需在 `game/` 目录执行，或把 `game/` 放进 `PYTHONPATH`。）

- `<save.json>` 支持整份存档 `{"decision_log": [...]}` 与包了一层
  `{"data": {"decision_log": [...]}}` 的导出格式（也接受裸数组）；
- 文件读不到 / JSON 解析失败 / 无 `decision_log` 键 ⇒ **打印原因并以退出码 2 结束**
  （不是静默 0）；回测成功 ⇒ 0；参数用法错 ⇒ 2（argparse 自身语义）。

指标口径（全部纯函数，可单独调用）
----------------------------------
- `brier(pairs)`：`mean((p - y)^2)`，`p` 为预测概率、`y ∈ {0,1}`；空输入 ⇒ `None`；
- `reliability_bins(records, outcomes, bins=10)`：按 `p` 落入 `[lo, hi)`（最后一箱含 1.0）
  分箱，`gap = mean_p - hit_rate`（> 0 = 过度自信），`ece = Σ (n_i / N) · |gap_i|`，
  **空箱不计入**（既不出现在 bins 里，也不进 ECE 权重）；
- `hit_rate(records, outcomes)`：gate ⇒ `bool(verdict) == outcome`；choose ⇒
  `verdict == argmax(outcome_dist)`；`defined is False` 的记录**不参与**
  （fail-closed 的 `False` 不是预测，拿它充命中率等于给"没依据"刷分）；
- `monotonic_check(series)`：非严格单调（**并列不算违反**，含驱动值并列与概率并列），
  按驱动值升序比较；空/单点 ⇒ `monotonic=None`（不是 `True`）；
- `DIRECTION`：**只登记审计已证实**的期望方向，未证实的一律 `status="unknown"`
  （不许自己发明方向；新增须先在 `_dev_tools/game-docs/specs/cross-cutting/tiandao-engine/tasks.md`
  登记断言）。当前登记两条：
  · `unrest ↑ ⇒ waive_arrears.p ↑`（灾/怨越重越该蠲免；引擎 `0.30 + dis*0.35 + u*0.25`）；
  · `integrity ↑ ⇒ granary_corruption.p ↓`（`test_tiandao_engine_core.py::
    test_corruption_gate_reachable_and_monotonic` 已断言）。

无第三方依赖：只用标准库 `argparse/json/logging/math/sys`。
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "BacktestError", "DIRECTION", "MODE", "MAX_VIOLATIONS",
    "brier", "reliability_bins", "hit_rate", "monotonic_check",
    "expected_direction", "check_expected_direction",
    "summarize", "load_log", "load_labels", "format_report", "main",
]

_LOG = logging.getLogger("tiandao.backtest")

#: 单次 `monotonic_check` 最多保留的违反序对（防手改大档时 O(n²) 输出爆炸）。
MAX_VIOLATIONS = 200

#: objective → 引擎模式（镜像 `core.ai.tiandao_decision.SPECS` 的 mode 列；
#: 仅用于报告与概率口径标注，**不参与判定**。未登记的 objective 记 `unknown`）。
MODE: Dict[str, str] = {
    "tax_stance": "choose",
    "waive_arrears": "gate",
    "merchant_trade": "choose",
    "changping_open": "gate",
    "labor_policy": "choose",
    "canal_reroute": "choose",
    "granary_corruption": "gate",
    "farmer_path": "choose",
    "gentry_path": "choose",
    "reform_compliance": "gate",
    "recruit_refugees": "gate",
}

#: **审计已证实**的期望方向表：objective → {driver: {direction, verdict, status, evidence}}。
#:
#: `direction`：驱动值上升时概率的期望走向（"up"/"down"）；
#: `verdict`：该概率对应哪个结论（gate 用 True/False；choose 用选项名或 None=整体概率）；
#: 未登记的 objective/driver 由 `expected_direction()` 返回 `status="unknown"`。
DIRECTION: Dict[str, Dict[str, Dict[str, Any]]] = {
    "waive_arrears": {
        "unrest": {
            "direction": "up",
            "verdict": True,
            "status": "audited",
            "evidence": ("Lead 审计（2026-10-21）：民怨越重越该蠲免陈欠；"
                         "引擎 waive_arrears = 0.30 + disaster*0.35 + unrest*0.25 + 0.20*integrity"),
        },
    },
    "granary_corruption": {
        "integrity": {
            "direction": "down",
            "verdict": True,
            "status": "audited",
            "evidence": ("tiandao-engine tasks §4 #3：贪墨闸门改为 0.20 + 0.60*(1-integrity)；"
                         "断言 test_tiandao_engine_core.py::test_corruption_gate_reachable_and_monotonic"),
        },
    },
}

#: 无标签时统一的 reason 文案（严禁把"没有真值"说成"指标为 0"）。
_NO_LABEL_REASON = ("无外部标签（labels 缺失）：verdict 是引擎自己的结论，"
                    "拿它自证算 Brier/命中率无效；请提供 labels 文件")


class BacktestError(RuntimeError):
    """回测输入不可用（文件读不到 / 结构非法 / 无 decision_log 字段）。"""


# ═══════════════════════════════════════════════════════════════════════════
# 小工具：数值与标签归一（缺失一律 None，不回落 0/1.0）
# ═══════════════════════════════════════════════════════════════════════════
def _finite_float(value: Any) -> Optional[float]:
    """有限浮点；bool / 非数值 / NaN / ±inf ⇒ `None`（bool 是 int 子类，须先排除）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    f = float(value)
    return f if math.isfinite(f) else None


def _probability(record: Mapping[str, Any]) -> Optional[float]:
    """记录里的预测概率，仅接受 `[0, 1]` 闭区间内的有限数；否则 `None`（缺失）。"""
    p = _finite_float(record.get("probability"))
    if p is None or p < 0.0 or p > 1.0:
        return None
    return p


def _label_kind(label: Any) -> Optional[str]:
    """标签类别：`bool` ⇒ gate；`dict`（选项→概率）⇒ choose；其余 ⇒ `None`（不可用）。"""
    if isinstance(label, bool):
        return "gate"
    if isinstance(label, Mapping) and label:
        return "choose"
    return None


def _argmax(dist: Mapping[str, Any]) -> Optional[str]:
    """选项分布里概率最大的选项；坏值/空分布 ⇒ `None`（并列按选项名字典序定序，保证确定性）。"""
    best, best_v = None, None
    for key, raw in dist.items():
        v = _finite_float(raw)
        if v is None:
            continue
        if best is None or v > best_v or (v == best_v and str(key) < str(best)):
            best, best_v = str(key), v
    return best


def _outcome_view(outcomes: Any) -> Any:
    """把 `outcomes` 归一成两种视图，供 `_resolve_label` 消费：

    - `("map", {...})`：`{(objective, turn): label}`（标签文件归一形态）；
    - `("seq", [...])`：与 `records` **按下标对齐**的真值序列；
    - `None`：没有标签。

    `outcomes` 为 `list` 时会先判别元素是不是"标签行"（含 `objective`+`turn`）——
    是则按 `(objective, turn)` 匹配（避免把标签行误当"按序真值"），否则按下标对齐。
    """
    if outcomes is None:
        return None
    if isinstance(outcomes, Mapping):
        return ("map", outcomes)
    if isinstance(outcomes, (list, tuple)):
        if any(isinstance(x, Mapping) and "objective" in x and "turn" in x
               for x in outcomes):
            # `_label_map` 定义在后文（模块级函数，调用时已可用）
            label_map, _dup, _invalid = _label_map(outcomes)
            return ("map", label_map)
        return ("seq", outcomes)
    return None


def _resolve_label(view: Any, index: int, record: Mapping[str, Any]) -> Any:
    """按归一后的视图取一条记录的标签（缺失 ⇒ `None`，不臆造）。"""
    if view is None:
        return None
    kind, data = view
    if kind == "map":
        return data.get((record.get("objective"), record.get("turn")))
    return data[index] if index < len(data) else None


def _records(log: Any) -> List[Mapping[str, Any]]:
    """只保留 dict 记录（脏档里的非 dict 条目丢弃，不参与任何指标）。"""
    if not isinstance(log, (list, tuple)):
        return []
    return [r for r in log if isinstance(r, Mapping)]


# ═══════════════════════════════════════════════════════════════════════════
# 1) Brier 均方误差
# ═══════════════════════════════════════════════════════════════════════════
def brier(pairs: Iterable[Tuple[Any, Any]]) -> Optional[float]:
    """Brier 均方误差 = `mean((p - y)^2)`。

    - `pairs`：`[(p, outcome_bool), ...]`（`p` 须在 `[0,1]`；坏条目不参与）；
    - **空输入 ⇒ `None`**（不能返回 0 假装完美）；
    - 结果保留 6 位小数。
    """
    vals: List[float] = []
    for item in pairs or ():
        try:
            p_raw, y_raw = item
        except (TypeError, ValueError):
            continue
        p = _finite_float(p_raw)
        if p is None or p < 0.0 or p > 1.0:
            continue
        if isinstance(y_raw, bool):
            y = 1.0 if y_raw else 0.0
        else:
            yy = _finite_float(y_raw)
            if yy is None or yy not in (0.0, 1.0):
                continue
            y = yy
        vals.append((p - y) ** 2)
    if not vals:
        return None
    return round(sum(vals) / len(vals), 6)


def _brier_pair(record: Mapping[str, Any], label: Any) -> Tuple[Optional[Tuple[float, float]], str]:
    """从（记录，标签）导出 `(p, y)` 或 `(None, 原因)`。

    - gate 标签 `bool`：`y = 1.0/0.0`；
    - choose 标签 `dict`：`y = 1.0` 当且仅当 `verdict == argmax(outcome_dist)`，
      `p` 取记录里的 `probability`（写入端 = max 选项概率 ⇒ "top-1 置信度 vs 是否正确"）。
    """
    p = _probability(record)
    if p is None:
        return None, "probability 缺失或越界（非 [0,1] 有限数）"
    kind = _label_kind(label)
    if kind == "gate":
        return (p, 1.0 if label else 0.0), ""
    if kind == "choose":
        top = _argmax(label)
        if top is None:
            return None, "outcome_dist 无可用数值"
        return (p, 1.0 if str(record.get("verdict")) == top else 0.0), ""
    return None, "标签既非 bool 也非非空 outcome_dist"


def _scalar_pairs(records: Sequence[Mapping[str, Any]], outcomes: Any) -> Tuple[List[Tuple[float, float]], Dict[str, int]]:
    """批量导出 `(p, y)`；同时统计跳过原因（不静默丢弃）。"""
    pairs: List[Tuple[float, float]] = []
    skipped = {"no_label": 0, "unusable_label": 0, "no_probability": 0}
    view = _outcome_view(outcomes)
    for i, rec in enumerate(records):
        label = _resolve_label(view, i, rec)
        if label is None:
            skipped["no_label"] += 1
            continue
        pair, _reason = _brier_pair(rec, label)
        if pair is None:
            kind = _label_kind(label)
            if kind is None:
                skipped["unusable_label"] += 1
            else:
                skipped["no_probability"] += 1
            continue
        pairs.append(pair)
    return pairs, skipped


# ═══════════════════════════════════════════════════════════════════════════
# 2) 可靠性分箱 + ECE
# ═══════════════════════════════════════════════════════════════════════════
def reliability_bins(records: Sequence[Mapping[str, Any]], outcomes: Any,
                     bins: int = 10) -> Dict[str, Any]:
    """可靠性分箱表 + 期望校准误差（ECE，按样本数加权）。

    返回::

        {"bins": [{"index", "lo", "hi", "n", "mean_p", "hit_rate", "gap"}, ...],
         "ece": float|None, "n": int, "bins_requested": int,
         "ece_reason": str|None, "skipped": {...}}

    · 分箱区间 `[lo, hi)`，最后一箱含 `1.0`；**空箱不计入**（不出现在 `bins` 里）；
    · 每箱 `hit_rate` = 该箱内**真值=1 的实测频次**（可靠性图口径），
      **不是** `hit_rate()` 那个"预测命中率"——两者同名不同义，别混用；
    · `gap = mean_p - hit_rate`（> 0 过度自信、< 0 过度保守）；
    · `ece = Σ (n_i / N) · |gap_i|`，`N` = 实际入箱样本数；
    · 无可入箱样本 ⇒ `ece=None` + `ece_reason`（**不返回 0**）。
    """
    try:
        n_bins = int(bins)
    except (TypeError, ValueError):
        n_bins = 0
    if n_bins < 1:
        return {"bins": [], "ece": None, "n": 0, "bins_requested": bins,
                "ece_reason": "bins 非法（须为正整数）", "skipped": {}}

    pairs, skipped = _scalar_pairs(records, outcomes)
    if not pairs:
        return {"bins": [], "ece": None, "n": 0, "bins_requested": n_bins,
                "ece_reason": "无可校准样本（缺标签或缺概率）", "skipped": skipped}

    acc: Dict[int, List[Tuple[float, float]]] = {}
    for p, y in pairs:
        idx = min(n_bins - 1, int(p * n_bins))  # p == 1.0 ⇒ 末箱
        acc.setdefault(idx, []).append((p, y))

    rows: List[Dict[str, Any]] = []
    ece = 0.0
    total = 0
    for idx in sorted(acc):
        items = acc[idx]
        n = len(items)
        total += n
        mean_p = sum(p for p, _ in items) / n
        hit = sum(y for _, y in items) / n
        rows.append({
            "index": idx,
            "lo": round(idx / n_bins, 6),
            "hi": round((idx + 1) / n_bins, 6),
            "n": n,
            "mean_p": round(mean_p, 6),
            "hit_rate": round(hit, 6),
            "gap": round(mean_p - hit, 6),
        })
        ece += (n / len(pairs)) * abs(mean_p - hit)

    return {"bins": rows, "ece": round(ece, 6), "n": total,
            "bins_requested": n_bins, "ece_reason": None,
            "skipped": skipped}


# ═══════════════════════════════════════════════════════════════════════════
# 3) 命中率（gate / choose 两种口径）
# ═══════════════════════════════════════════════════════════════════════════
def hit_rate(records: Sequence[Mapping[str, Any]], outcomes: Any) -> Dict[str, Any]:
    """命中率：gate 比 `bool(verdict) == outcome`；choose 比 `verdict == argmax(outcome_dist)`。

    返回 `{"n", "hits", "rate", "gate_n", "choose_n", "skipped_undefined",
    "skipped_no_label", "skipped_unusable_label", "reason"}`。

    · `defined is False` 的记录**不参与**（fail-closed 的 `False` 不是预测）；
    · 无有效样本 ⇒ `rate=None` + `reason`（不是 0.0）。
    """
    n = hits = gate_n = choose_n = 0
    skipped = {"undefined": 0, "no_label": 0, "unusable_label": 0}
    view = _outcome_view(outcomes)
    for i, rec in enumerate(records):
        if rec.get("defined") is False:
            skipped["undefined"] += 1
            continue
        label = _resolve_label(view, i, rec)
        if label is None:
            skipped["no_label"] += 1
            continue
        kind = _label_kind(label)
        if kind == "gate":
            n += 1
            gate_n += 1
            if bool(rec.get("verdict")) == bool(label):
                hits += 1
        elif kind == "choose":
            top = _argmax(label)
            if top is None:
                skipped["unusable_label"] += 1
                continue
            n += 1
            choose_n += 1
            if str(rec.get("verdict")) == top:
                hits += 1
        else:
            skipped["unusable_label"] += 1

    if n == 0:
        return {"n": 0, "hits": 0, "rate": None, "gate_n": 0, "choose_n": 0,
                "skipped_undefined": skipped["undefined"],
                "skipped_no_label": skipped["no_label"],
                "skipped_unusable_label": skipped["unusable_label"],
                "reason": "无可用样本（需 defined=True 且带标签）"}
    return {"n": n, "hits": hits, "rate": round(hits / n, 6),
            "gate_n": gate_n, "choose_n": choose_n,
            "skipped_undefined": skipped["undefined"],
            "skipped_no_label": skipped["no_label"],
            "skipped_unusable_label": skipped["unusable_label"],
            "reason": None}


# ═══════════════════════════════════════════════════════════════════════════
# 4) 单调性
# ═══════════════════════════════════════════════════════════════════════════
def monotonic_check(series: Sequence[Tuple[Any, Any]]) -> Dict[str, Any]:
    """判断概率是否随驱动值单调（**非严格**：并列不算违反）。

    入参：`[(driver_value, probability), ...]`（驱动值须为有限数；概率须在 `[0,1]`；
    坏条目丢弃并在 `skipped` 里计数）。

    返回::

        {"monotonic": bool|None, "direction": "up"|"down"|None,
         "violations": [[i, j], ...], "n": int, "skipped": int,
         "violations_up": int, "violations_down": int,
         "truncated": bool, "ordered": bool, "reason": str|None}

    · 空 / 单点 ⇒ `monotonic=None`（**不是** `True`）；
    · 驱动值并列的序对不比较（并列允许任意概率）；
    · 违反序对的下标是**按驱动值升序重排后**的位置（`ordered=True` 恒成立）；
    · 两个方向都成立（如所有可比概率相同）⇒ `direction=None`（方向不可判定）；
    · `violations` 是**相邻驱动组**的违反序对（足以判定与定位，不会 O(n²) 膨胀）；
      超过 `MAX_VIOLATIONS` 时 **截断并置 `truncated=True`**（计数仍是真实值）。
    · 判定口径：按驱动值分组后，非降 ⇔ 每组 `max ≤` 下组 `min`（非增对称）
      —— 这样组内并列的任意概率不会误判，复杂度 O(n log n)。
    """
    items: List[Tuple[float, float]] = []
    skipped = 0
    for pair in series or ():
        try:
            d_raw, p_raw = pair
        except (TypeError, ValueError):
            skipped += 1
            continue
        d = _finite_float(d_raw)
        p = _finite_float(p_raw)
        if d is None or p is None or p < 0.0 or p > 1.0:
            skipped += 1
            continue
        items.append((d, p))

    if len(items) < 2:
        return {"monotonic": None, "direction": None, "violations": [], "n": len(items),
                "skipped": skipped, "violations_up": 0, "violations_down": 0,
                "truncated": False, "ordered": True,
                "reason": "样本不足（有效点 < 2）：无法判断单调"}

    ordered = sorted(items, key=lambda t: t[0])
    n = len(ordered)

    # 按驱动值分组：组内并列允许任意概率；单调性只需相邻组比较（O(n log n) 排序 + O(n) 扫描）
    groups: List[Dict[str, Any]] = []
    for idx, (d, pv) in enumerate(ordered):
        if groups and groups[-1]["driver"] == d:
            g = groups[-1]
            if pv > g["max"]:
                g["max"], g["max_idx"] = pv, idx
            if pv < g["min"]:
                g["min"], g["min_idx"] = pv, idx
        else:
            groups.append({"driver": d, "min": pv, "max": pv,
                           "min_idx": idx, "max_idx": idx})

    up_v: List[List[int]] = []       # 违反"非降"的相邻组对：本组 max > 下组 min
    down_v: List[List[int]] = []     # 违反"非增"的相邻组对：本组 min < 下组 max
    for a in range(len(groups) - 1):
        g_a, g_b = groups[a], groups[a + 1]
        if g_a["max"] > g_b["min"]:
            up_v.append([g_a["max_idx"], g_b["min_idx"]])
        if g_a["min"] < g_b["max"]:
            down_v.append([g_a["min_idx"], g_b["max_idx"]])

    # 「截断」语义：**任一侧**违反数超过 MAX_VIOLATIONS 就算截断（说明还有未列出的违反）
    truncated = len(up_v) > MAX_VIOLATIONS or len(down_v) > MAX_VIOLATIONS

    def _cap(rows: List[List[int]]) -> List[List[int]]:
        """截断到 MAX_VIOLATIONS 条（计数仍为真实值）。"""
        return rows[:MAX_VIOLATIONS] if len(rows) > MAX_VIOLATIONS else rows

    if not up_v and not down_v:
        return {"monotonic": True, "direction": None, "violations": [], "n": n,
                "skipped": skipped, "violations_up": 0, "violations_down": 0,
                "truncated": truncated, "ordered": True,
                "reason": "同时满足非降与非增（无可判别的方向）"}
    if not up_v:
        return {"monotonic": True, "direction": "up", "violations": [], "n": n,
                "skipped": skipped, "violations_up": 0, "violations_down": len(down_v),
                "truncated": truncated, "ordered": True, "reason": None}
    if not down_v:
        return {"monotonic": True, "direction": "down", "violations": [], "n": n,
                "skipped": skipped, "violations_up": len(up_v), "violations_down": 0,
                "truncated": truncated, "ordered": True, "reason": None}
    # 两个方向都有违反 ⇒ 非单调；violations 取违反更少的方向（两者都非空，保证可定位）
    chosen = up_v if len(up_v) <= len(down_v) else down_v
    return {"monotonic": False, "direction": None, "violations": _cap(chosen), "n": n,
            "skipped": skipped, "violations_up": len(up_v), "violations_down": len(down_v),
            "truncated": truncated, "ordered": True,
            "reason": "两个方向均存在违反；violations 取违反更少的方向（相邻组对）"}


# ═══════════════════════════════════════════════════════════════════════════
# 5) 期望方向表（只登记审计已证实的）
# ═══════════════════════════════════════════════════════════════════════════
def expected_direction(objective: str, driver: str) -> Dict[str, Any]:
    """查期望方向；未登记 ⇒ `status="unknown"`（**不猜方向**）。

    返回 `{"objective", "driver", "direction", "verdict", "status", "evidence", "reason"}`。
    """
    spec = (DIRECTION.get(str(objective)) or {}).get(str(driver))
    if not spec:
        return {"objective": objective, "driver": driver, "direction": None,
                "verdict": None, "status": "unknown", "evidence": None,
                "reason": ("该 objective/driver 的期望方向未经审计证实（勿凭空发明）；"
                           "新增方向须先在 tiandao-engine/tasks.md 登记断言")}
    return {"objective": objective, "driver": driver,
            "direction": spec.get("direction"), "verdict": spec.get("verdict"),
            "status": spec.get("status", "audited"), "evidence": spec.get("evidence"),
            "reason": None}


def check_expected_direction(objective: str, driver: str,
                             series: Sequence[Tuple[Any, Any]]) -> Dict[str, Any]:
    """把 `monotonic_check` 的结果与 `expected_direction` 对照。

    返回 `{..., "check": {...}, "agrees": bool|None, "reason"}`：
    `agrees=True` 表示实测方向与已审计方向一致；方向未知/样本不足 ⇒ `None`。
    """
    exp = expected_direction(objective, driver)
    chk = monotonic_check(series)
    agrees: Optional[bool] = None
    reason: Optional[str] = None
    if exp["status"] == "unknown":
        reason = exp["reason"]
    elif chk["monotonic"] is None:
        reason = chk["reason"]
    elif chk["monotonic"] is False:
        agrees = False
        reason = "概率随驱动值**非单调**，与任何期望方向都不符"
    elif chk["direction"] is None:
        reason = "可判方向为空（如全程并列）"
    else:
        agrees = (chk["direction"] == exp["direction"])
        if not agrees:
            reason = "实测方向 %s 与期望方向 %s 相反" % (chk["direction"], exp["direction"])
    return {"objective": objective, "driver": driver,
            "expected": exp, "check": chk, "agrees": agrees, "reason": reason}


# ═══════════════════════════════════════════════════════════════════════════
# 6) 汇总报告
# ═══════════════════════════════════════════════════════════════════════════
def _label_map(labels: Any) -> Tuple[Dict[Tuple[Any, Any], Any], List[Any], List[Any]]:
    """把标签归一成 `{(objective, turn): label}`；返回 (映射, 重复项, 非法项)。

    接受 `list[dict]` 或文件形态 `{"labels": [...]}`；条目必含 `objective` 与 `turn`，
    `outcome`（bool）/`outcome_dist`（dict）至少给一个。
    """
    rows: Sequence[Any] = []
    if isinstance(labels, Mapping):
        maybe = labels.get("labels")
        rows = maybe if isinstance(maybe, list) else []
    elif isinstance(labels, (list, tuple)):
        rows = labels

    out: Dict[Tuple[Any, Any], Any] = {}
    duplicates: List[Any] = []
    invalid: List[Any] = []
    for row in rows:
        if not isinstance(row, Mapping):
            invalid.append(row)
            continue
        obj = row.get("objective")
        turn = row.get("turn")
        if not isinstance(obj, str) or obj == "" or isinstance(turn, bool) or not isinstance(turn, int):
            invalid.append(row)
            continue
        if "outcome" in row:
            label: Any = bool(row.get("outcome"))
        elif isinstance(row.get("outcome_dist"), Mapping):
            label = dict(row["outcome_dist"])
        else:
            invalid.append(row)
            continue
        key = (obj, turn)
        if key in out:
            duplicates.append({"objective": obj, "turn": turn})
            continue  # 不覆盖：保留第一条，重复项单独报出
        out[key] = label
    return out, duplicates, invalid


def _prob_stats(probs: Sequence[float]) -> Optional[Dict[str, Any]]:
    if not probs:
        return None
    return {"n": len(probs), "min": round(min(probs), 6),
            "max": round(max(probs), 6),
            "mean": round(sum(probs) / len(probs), 6)}


def _prob_histogram(probs: Sequence[float], bins: int = 10) -> List[Dict[str, Any]]:
    """概率分布直方图（只数数，不需要标签）；空箱也保留以便看出分布形状。"""
    counts = [0] * bins
    for p in probs:
        counts[min(bins - 1, int(p * bins))] += 1
    return [{"lo": round(i / bins, 4), "hi": round((i + 1) / bins, 4), "n": counts[i]}
            for i in range(bins)]


def summarize(log: Any, labels: Any = None) -> Dict[str, Any]:
    """汇总回测报告：按 objective 分组给 `n / defined_n / brier / ece / 命中率 / 概率分布`。

    - `labels` 缺失（或全部非法）⇒ **只给分布与覆盖率**，`brier`/`ece`/`hit_rate`
      一律 `None` 并带 `*_reason`（绝不拿 verdict 自洽当 ground truth）；
    - `labels` 存在但只覆盖部分记录 ⇒ 指标按**已覆盖样本**计算，并报
      `labels_matched` / `label_coverage`（未覆盖比例不隐藏）；
    - 未知 objective 也单独成组（`mode="unknown"`），不丢弃。
    """
    records = _records(log)
    label_map, duplicates, invalid = _label_map(labels)
    has_labels = bool(label_map)

    groups: Dict[str, List[Mapping[str, Any]]] = {}
    for rec in records:
        obj = rec.get("objective")
        groups.setdefault(str(obj) if obj is not None else "", []).append(rec)

    objectives: Dict[str, Any] = {}
    matched_total = 0
    for obj in sorted(groups):
        rs = groups[obj]
        defined_n = sum(1 for r in rs if r.get("defined") is True)
        probs = [p for r in rs if (p := _probability(r)) is not None]
        providers: Dict[str, int] = {}
        for r in rs:
            prov = str(r.get("provider"))
            providers[prov] = providers.get(prov, 0) + 1
        verdicts: Dict[str, int] = {}
        for r in rs:
            v = str(r.get("verdict"))
            verdicts[v] = verdicts.get(v, 0) + 1

        entry: Dict[str, Any] = {
            "objective": obj,
            "mode": MODE.get(obj, "unknown"),
            "n": len(rs),
            "defined_n": defined_n,
            "defined_ratio": round(defined_n / len(rs), 6) if rs else None,
            "probability": _prob_stats(probs),
            "probability_kind": ("gate_probability" if MODE.get(obj) == "gate"
                                 else "max_option_probability" if MODE.get(obj) == "choose"
                                 else "unknown"),
            "probability_histogram": _prob_histogram(probs),
            "probability_missing": len(rs) - len(probs),
            "verdicts": verdicts,
            "providers": providers,
            "cached_n": sum(1 for r in rs if r.get("cached") is True),
            "labeled_n": 0,
            "labels_matched": 0,
            "label_coverage": None,
            "brier": None,
            "brier_reason": _NO_LABEL_REASON,
            "reliability": None,
            "ece": None,
            "ece_reason": _NO_LABEL_REASON,
            "hit_rate": None,
        }

        if has_labels:
            matched = sum(1 for r in rs
                          if (r.get("objective"), r.get("turn")) in label_map)
            matched_total += matched
            entry["labels_matched"] = matched
            entry["label_coverage"] = round(matched / len(rs), 6) if rs else None

            pairs, pair_skipped = _scalar_pairs(rs, label_map)
            entry["labeled_n"] = len(pairs)
            b = brier(pairs)
            entry["brier"] = b
            entry["brier_reason"] = (None if b is not None else
                                     "无可用于 Brier 的样本（缺标签或缺 probability）；"
                                     "跳过统计：" + json.dumps(pair_skipped, ensure_ascii=False))

            rel = reliability_bins(rs, label_map)
            entry["reliability"] = rel
            entry["ece"] = rel.get("ece")
            entry["ece_reason"] = rel.get("ece_reason")

            entry["hit_rate"] = hit_rate(rs, label_map)

        objectives[obj] = entry

    # 标签里对不上的条目（记录里没有同键）如实报出，别让标签静默丢失
    unmatched = []
    if has_labels:
        record_keys = {(r.get("objective"), r.get("turn")) for r in records}
        unmatched = [{"objective": k[0], "turn": k[1]}
                     for k in sorted(label_map, key=lambda t: (str(t[0]), str(t[1])))
                     if k not in record_keys]

    total = len(records)
    return {
        "records": total,
        "defined_records": sum(1 for r in records if r.get("defined") is True),
        "objectives": objectives,
        "labels_provided": has_labels,
        "labels_matched": matched_total,
        "label_coverage": (round(matched_total / total, 6)
                           if (has_labels and total) else None),
        "unmatched_labels": unmatched,
        "duplicate_labels": duplicates,
        "invalid_labels": len(invalid),
        "distribution_only": not has_labels,
        "note": (None if has_labels else
                 "无标签 ⇒ 仅报告概率分布与覆盖率；brier/ece/hit_rate 均为 None"
                 "（verdict 自洽不是 ground truth）"),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 7) 读档 / 读标签 / 文本报告 / CLI
# ═══════════════════════════════════════════════════════════════════════════
def load_log(path: str) -> List[Dict[str, Any]]:
    """从存档 JSON 读 `decision_log`（兼容三种形态）：

    - `{"decision_log": [...]}`（本程序存档）；
    - `{"data": {"decision_log": [...]}}`（后端/导出包一层）；
    - 裸数组 `[...]`（手工导出的日志切片）。

    读不到 / 解析失败 / 无该键 / 该键非 list ⇒ 抛 `BacktestError`（CLI 据此退出码 2）。
    只保留 dict 条目。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise BacktestError("读不到存档文件：%s（%s）" % (path, e)) from e
    except ValueError as e:
        raise BacktestError("存档不是合法 JSON：%s（%s）" % (path, e)) from e

    if isinstance(data, list):
        rows = data
    elif isinstance(data, Mapping):
        rows = data.get("decision_log")
        if rows is None:
            inner = data.get("data")
            if isinstance(inner, Mapping):
                rows = inner.get("decision_log")
        if rows is None:
            raise BacktestError(
                "存档里没有 decision_log 字段（%s）：旧档或非天道日志存档，无可回测" % path)
    else:
        raise BacktestError("存档顶层既非对象也非数组：%s" % path)

    if not isinstance(rows, list):
        raise BacktestError("decision_log 不是数组（实为 %s）：%s"
                            % (type(rows).__name__, path))
    return [dict(r) for r in rows if isinstance(r, Mapping)]


def load_labels(path: str) -> List[Dict[str, Any]]:
    """读标签文件（`{"labels": [...]}` 或裸数组），逐条做基本校验。

    结构非法（非对象/非数组/无 `labels`）⇒ 抛 `BacktestError`；
    单条非法 ⇒ 记 warning 后丢弃（不因一条坏标签废掉整份标签）。
    详见模块 docstring 的「标签文件格式」。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise BacktestError("读不到标签文件：%s（%s）" % (path, e)) from e
    except ValueError as e:
        raise BacktestError("标签文件不是合法 JSON：%s（%s）" % (path, e)) from e

    if isinstance(data, Mapping):
        rows = data.get("labels")
        if not isinstance(rows, list):
            raise BacktestError("标签文件缺 `labels` 数组：%s" % path)
    elif isinstance(data, list):
        rows = data
    else:
        raise BacktestError("标签文件顶层既非对象也非数组：%s" % path)

    kept: List[Dict[str, Any]] = []
    dropped = 0
    for row in rows:
        if not isinstance(row, Mapping):
            dropped += 1
            continue
        obj = row.get("objective")
        turn = row.get("turn")
        if not isinstance(obj, str) or obj == "" or isinstance(turn, bool) or not isinstance(turn, int):
            dropped += 1
            continue
        if "outcome" in row:
            kept.append({"objective": obj, "turn": turn, "outcome": bool(row["outcome"])})
        elif isinstance(row.get("outcome_dist"), Mapping):
            kept.append({"objective": obj, "turn": turn,
                         "outcome_dist": dict(row["outcome_dist"])})
        else:
            dropped += 1
    if dropped:
        _LOG.warning("标签文件 %s 有 %d 条非法条目被丢弃（保留 %d 条）",
                     path, dropped, len(kept))
    return kept


def _fmt(value: Any) -> str:
    """文本报告里的数值格式：`None` 一律显式写 `None`（不写 0）。"""
    if value is None:
        return "None"
    if isinstance(value, float):
        return "%.4f" % value
    return str(value)


def format_report(report: Mapping[str, Any]) -> str:
    """把 `summarize()` 的报告渲染成人类可读文本（CLI 默认输出）。"""
    lines: List[str] = []
    lines.append("天道决策日志回测 · 记录 %d 条（defined=%s）"
                 % (report.get("records", 0), report.get("defined_records", 0)))
    if report.get("distribution_only"):
        lines.append("注意：无标签，只报概率分布与覆盖率；Brier/ECE/命中率均为 None"
                     "（verdict 自洽不是 ground truth）")
    else:
        lines.append("标签覆盖率：%s（匹配 %d 条，未匹配标签 %d 条，重复标签 %d 条）"
                     % (_fmt(report.get("label_coverage")), report.get("labels_matched", 0),
                        len(report.get("unmatched_labels") or []),
                        len(report.get("duplicate_labels") or [])))
    for obj, e in sorted((report.get("objectives") or {}).items()):
        lines.append("")
        lines.append("== %s（mode=%s，n=%d，defined=%d，覆盖=%s）"
                     % (obj, e.get("mode"), e.get("n", 0), e.get("defined_n", 0),
                        _fmt(e.get("defined_ratio"))))
        stats = e.get("probability")
        if stats:
            lines.append("   概率分布：n=%d min=%s max=%s mean=%s（%s）"
                         % (stats["n"], _fmt(stats["min"]), _fmt(stats["max"]),
                            _fmt(stats["mean"]), e.get("probability_kind")))
        else:
            lines.append("   概率分布：无可用概率（缺失 %d 条）" % e.get("probability_missing", 0))
        lines.append("   verdict 分布：%s" % json.dumps(e.get("verdicts") or {},
                                                       ensure_ascii=False, sort_keys=True))
        if report.get("distribution_only"):
            lines.append("   Brier/ECE/命中率：None（%s）" % _NO_LABEL_REASON)
            continue
        lines.append("   Brier=%s（reason=%s）" % (_fmt(e.get("brier")),
                                                  e.get("brier_reason")))
        lines.append("   ECE=%s（reason=%s，样本 %s）"
                     % (_fmt(e.get("ece")), e.get("ece_reason"),
                        (e.get("reliability") or {}).get("n")))
        hr = e.get("hit_rate") or {}
        lines.append("   命中率=%s（%s/%s；gate=%s choose=%s；reason=%s）"
                     % (_fmt(hr.get("rate")), hr.get("hits"), hr.get("n"),
                        hr.get("gate_n"), hr.get("choose_n"), hr.get("reason")))
        bins = (e.get("reliability") or {}).get("bins") or []
        for b in bins:
            # 这里的 hit 是"箱内真值=1 的实测频次"（可靠性图口径），不是预测命中率
            lines.append("     bin[%s] %s~%s n=%s mean_p=%s 实测频次=%s gap=%s"
                         % (b["index"], _fmt(b["lo"]), _fmt(b["hi"]), b["n"],
                            _fmt(b["mean_p"]), _fmt(b["hit_rate"]), _fmt(b["gap"])))
    return "\n".join(lines)


def _harden_stdio() -> None:
    """把 stdout/stderr 切到 UTF-8（errors=replace），避免 Windows 中文控制台崩溃。

    实测（2026-10-21）：Windows 下 stdout 被管道重定向时默认按 cp936 编码，报告里的
    `⇒`（U+21D2）等非 GBK 字符会抛 `UnicodeEncodeError`，CLI 直接以退出码 1 崩掉
    ——而它本应只返回 0/2。**只动编码**，不动缓冲/换行语义；不支持 `reconfigure`
    的旧运行时静默跳过（本函数是防御性加固，不影响功能）。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 —— 旧运行时无 reconfigure：跳过，不影响功能
            pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI 入口：`python -m core.ai.tiandao_backtest <save.json> [--labels labels.json] [--json]`。

    返回退出码：`0` 成功；`2` 输入不可用（读不到/结构非法/无 decision_log）
    或参数用法错（argparse 语义）。**绝不静默返回 0。**
    """
    _harden_stdio()
    parser = argparse.ArgumentParser(
        prog="python -m core.ai.tiandao_backtest",
        description="天道决策日志离线回测（零网络、零 state 写入）")
    parser.add_argument("save", help="存档 JSON 文件（含 decision_log）")
    parser.add_argument("--labels", default=None, help="标签文件 JSON（可选）")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="以 JSON 输出报告")
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:  # argparse 用法错 → 沿用其退出码（通常 2）
        return int(exc.code or 0)

    try:
        log = load_log(args.save)
        labels = load_labels(args.labels) if args.labels else None
    except BacktestError as e:
        print("[回测器] 无法回测：%s" % e, file=sys.stderr)
        return 2

    report = summarize(log, labels)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":  # pragma: no cover —— CLI 直跑
    raise SystemExit(main())
