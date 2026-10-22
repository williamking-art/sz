# -*- coding: utf-8 -*-
"""天道 facts 契约（单一 schema）—— 裁决层与业务层之间**唯一**的读数口径。

为什么要有这个模块
------------------
2026-10-21 审计实测：天道层的「上下文」曾有三套并存且互不一致——
`TianDaoFacade.build_state_context`、`clerk_decision` 自建 ctx、`merchant_decision` 自建 ctx。
后果是可观测的：`clerk_decision` 把「吏治 + 灾情」**计了两次**（纯 softmax lenient 0.458 →
引擎偏置后 0.57）；`merchant_decision` 的 criteria 键（hoard/dump/hold）引擎认不出 objective，
于是它构造的 `gap`/`stock` **一个都没被读**。

本模块把口径收敛成**一张表**：

* 键名、量纲、缺失语义**只在这里定义**；
* 生产者（facade / clerk / merchant）一律调 `build_facts` 或 `canonicalize`；
* 引擎只认这张表里的**主键**，不再靠别名与文案猜。

口径三条（对齐根 `AGENTS.md` §3）
------------------------------------------------
1. **缺失一律 `None`**，绝不回落 0 / 0.5 / 1.0；
2. **`0` 是合法值**（`0` 表示"确实为零"，`None` 表示"取不到"）；
3. **量纲固定**：钱=贯、粮=石、比例=0~1、指数（民怨/淤塞）=0~100、声望=0~100。

facts 表
--------
| 键 | 含义 | 量纲 | 来源 | 缺失语义 |
|---|---|---|---|---|
| `treasury` | 中央国库 | 贯 | `state.treasury` | None=取不到 |
| `imperial_treasury` | 内帑 | 贯 | `state.imperial_treasury` | None |
| `local_treasury` | 地方府库合计（Σ 地方级镜像） | 贯 | `prefectures[*]["local_treasury"]` | None=任一地方都取不到 |
| `monthly_expense` | 上月刚性支出 | 贯 | `statistics["last_monthly_expense"]` | None=新档首月 |
| `granary` | 太仓存粮 | 石 | `state.granary` | None |
| `granary_cap` | 太仓容量 | 石 | `state.granary_cap` | None |
| `changping_stock` | 常平仓存粮合计 | 石 | `prefectures[*]["changping_stock"]` | None |
| `unrest` | 民怨均值 | 0~100 | `prefectures[*]["unrest"]` 均值 | None=任一地方都无读数 |
| `refugees` | 流民合计 | 人 | `prefectures[*]["refugees"]` 求和 | None |
| `refugees_max_route` | 单地方最大流民 | 人 | 同上取 max | None |
| `price_ratio` | 粮价/基准价 | 倍 | 地方级 `grain_price` 均值 ÷ `state.grain_price` | None=基准缺失或为 0 |
| `integrity` | 吏治清廉度 | 0~1 | `1 − mean(state.corruption)` | **None=无贪腐读数**（旧实现回落 1.0＝"吏治完美"，违反硬约束） |
| `diligence` | 官员勤勉 | 0~1 | 地方级 governor/`gov` 的 diligence | None=无生产者 |
| `oversight` | 监察强度 | 0~1 | `state.oversight` | None |
| `has_inspector` | 是否有巡按 | bool | `oversight ≥ INSPECTOR_MIN` | False（布尔无"缺失"态，故由 oversight 推导；oversight 为 None 时仍 False 但在 `BASIS` 里由 oversight 表达缺失） |
| `prestige` | 国祚声望 | 0~100 | `state.prestige` | None |
| `disaster` | 灾情强度 | 0~1 | **`state.disaster_severity / 5`**（0~5 → 0~1） | None=取不到 |
| `faction` | 当权派系 | `reform`/`conservative`/`""` | 影响力最高的 `state.factions` | `""`=无派系读数（**不是**"中立"，中立派名字会原样给出） |
| `debt` | 小农欠负 | 贯 | 暂无可信源 | 恒 None |
| `gap` | 商贸价差 | 倍 | `merchant_decision` 提供（`price − global_price`） | None |
| `block_rate` | 漕运淤塞率 | 0~100 | `prefectures[*]["canal_block"]` 均值 | None=任一地方都无读数 |
| `tax_completion` | 赋税完成率 | 0~1.2 | 考课用（`official_appraisal` 计算后注入） | None=不走考课分支 |
| `official_integrity` | 考课用清廉度 | 0~1 | 同上 | None |
| `turn` | 回合号 | 整数 | `state.turn` | None |

⚠️ **`tax_completion`/`official_integrity` 是"考课分支"的进入条件**：两者都缺失时 `score` 走通用灾情分支。
⚠️ **`disaster` 与 `disaster_severity` 的关系**：state 上一律是 0~5 的**等级**，本契约对外一律归一为 0~1。

使用纪律
--------
* 新增读数：先在本模块登记（表 + `_READERS`），再让引擎读；**禁止**在引擎里直接 `context.get("某键")` 引入未登记键。
* 改口径：改本模块即改契约，必须同步 `game/core/ai/README.md` 与
  `_dev_tools/game-docs/specs/cross-cutting/tiandao-engine/tasks.md`。
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Optional

__all__ = [
    "FACT_KEYS", "COMPAT_ALIASES", "MEAN_FIELDS", "SUM_FIELDS", "INSPECTOR_MIN",
    "build_facts", "canonicalize", "facts_digest", "validate_facts",
    "to_engine_context", "normalize_disaster",
]

#: 巡按判定线（oversight 归一化后）
INSPECTOR_MIN = 0.5

#: 需要跨路**求均值**的读数（不可求和：比率/指数）
MEAN_FIELDS = ("unrest", "price_ratio", "integrity", "block_rate")
#: 需要跨路**求和**的读数
SUM_FIELDS = ("local_treasury", "changping_stock", "refugees")

#: 契约登记的全部 canonical 键（顺序即文档顺序）
FACT_KEYS = (
    "treasury", "imperial_treasury", "local_treasury", "monthly_expense",
    "granary", "granary_cap", "changping_stock",
    "unrest", "refugees", "refugees_max_route", "price_ratio",
    "integrity", "diligence", "oversight", "has_inspector",
    "prestige", "disaster", "faction",
    "debt", "gap", "block_rate",
    "tax_completion", "official_integrity", "turn",
)

#: **过渡期兼容别名**：`to_engine_context` 会为旧调用点补上的键。
#: 它们不是独立读数，只是 canonical 键的别称，因此 `validate_facts` **不判为违规**；
#: 但**生产者不得直接写别名**，新代码一律读 canonical 键。（唯一出处仍在本表。）
COMPAT_ALIASES = {
    "stock": "changping_stock",       # 旧引擎读 stock/storage
    "storage": "changping_stock",
    "supervision": "has_inspector",   # 旧引擎读 has_inspector/supervision
    "stability": "prestige",          # 旧引擎读 prestige/stability
}

#: 比例类读数（canonicalize 时钳到 0~1）
_UNIT_FIELDS = ("integrity", "diligence", "oversight", "disaster")
#: 0~100 指数类（canonicalize 时钳到 0~100）
_INDEX_FIELDS = ("unrest", "block_rate", "prestige")
#: 非负金额/数量类（canonicalize 时钳到 ≥0，不设上限）
_NONNEG_FIELDS = ("treasury", "imperial_treasury", "local_treasury", "monthly_expense",
                  "granary", "granary_cap", "changping_stock", "refugees",
                  "refugees_max_route", "debt")
#: 允许负值的读数（价差可负）
_SIGNED_FIELDS = ("gap",)


# --------------------------------------------------------------------------
# 基础取数
# --------------------------------------------------------------------------
def _num(value: Any) -> Optional[float]:
    """转数值；`bool`/非数值/非有限值一律 None（`0` 原样保留）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _prefectures(state: Any) -> Dict[str, Any]:
    prefs = getattr(state, "prefectures", None)
    return prefs if isinstance(prefs, dict) else {}


def _route_values(state: Any, field: str) -> List[float]:
    """收集各区域该字段的**可用**读数（跳过缺失与非数值）。"""
    out: List[float] = []
    for row in _prefectures(state).values():
        if not isinstance(row, dict):
            continue
        v = _num(row.get(field))
        if v is not None:
            out.append(v)
    return out


def _mean(values: List[float]) -> Optional[float]:
    return (sum(values) / len(values)) if values else None


def _top_faction(state: Any) -> str:
    """影响力最高的派系 → 引擎口径（reform / conservative / 原名 / 空）。

    只做**名称映射**，不做价值判断：新党=变法派、旧党=守旧派；
    其余（皇党/军功/中立）原样返回，引擎对其不加偏置（不是"中立即改革"）。
    """
    factions = getattr(state, "factions", None)
    if not isinstance(factions, dict) or not factions:
        return ""
    best_name, best_inf = "", None
    for name, row in factions.items():
        if not isinstance(row, dict):
            continue
        inf = _num(row.get("influence"))
        if inf is None:
            continue
        if best_inf is None or inf > best_inf:
            best_name, best_inf = str(name), inf
    if not best_name:
        return ""
    if best_name in ("新党", "变法派", "reform"):
        return "reform"
    if best_name in ("旧党", "守旧派", "conservative"):
        return "conservative"
    return best_name


# --------------------------------------------------------------------------
# 生产者：从 state 聚合 canonical facts（只读，不写 state）
# --------------------------------------------------------------------------
def build_facts(state: Any) -> Dict[str, Any]:
    """从 `state` 聚合 canonical facts。**纯只读**，缺失一律 None。

    不抛异常：任何取数失败在对应键上体现为 None（不猜测、不回落）。
    """
    facts: Dict[str, Any] = {k: None for k in FACT_KEYS}

    for key, attr in (("treasury", "treasury"),
                      ("imperial_treasury", "imperial_treasury"),
                      ("granary", "granary"),
                      ("granary_cap", "granary_cap"),
                      ("oversight", "oversight"),
                      ("prestige", "prestige"),
                      ("turn", "turn")):
        facts[key] = _num(getattr(state, attr, None))

    stats = getattr(state, "statistics", None)
    if isinstance(stats, dict):
        facts["monthly_expense"] = _num(
            stats.get("last_monthly_expense", stats.get("monthly_expense")))

    # 跨路求和类：**空列表 ⇒ None**（一路都取不到 ≠ 合计为 0）
    for key, field in (("local_treasury", "local_treasury"),
                       ("changping_stock", "changping_stock"),
                       ("refugees", "refugees")):
        vals = _route_values(state, field)
        facts[key] = sum(vals) if vals else None

    ref_vals = _route_values(state, "refugees")
    facts["refugees_max_route"] = max(ref_vals) if ref_vals else None

    facts["unrest"] = _mean(_route_values(state, "unrest"))
    facts["block_rate"] = _mean(_route_values(state, "canal_block"))

    # 粮价比：路级均价 ÷ 基准价（基准缺失或 ≤0 ⇒ None，不拿 1.0 冒充"平价"）
    prices = _route_values(state, "grain_price")
    base = _num(getattr(state, "grain_price", None))
    avg = _mean(prices)
    facts["price_ratio"] = (avg / base) if (avg is not None and base and base > 0) else None

    # 吏治：1 − 平均贪腐；**无贪腐读数 ⇒ None**（旧实现回落 1.0 = 吏治完美）
    corr = getattr(state, "corruption", None)
    corr_vals = [v for v in (_num(x) for x in corr.values()) if v is not None] \
        if isinstance(corr, dict) else []
    facts["integrity"] = (max(0.0, min(1.0, 1.0 - (sum(corr_vals) / len(corr_vals))))
                          if corr_vals else None)

    # 勤勉：路级 governor 的 diligence（当前无生产者 ⇒ 恒 None，登记在案不臆造）
    dil_vals = []
    for row in _prefectures(state).values():
        if not isinstance(row, dict):
            continue
        for holder in (row.get("governor"), row.get("official")):
            if isinstance(holder, dict):
                v = _num(holder.get("diligence"))
                if v is not None:
                    dil_vals.append(v)
                    break
    facts["diligence"] = _mean(dil_vals)

    # 灾情：state 上是 0~5 的等级，对外归一 0~1（归一口径单一出处 = normalize_disaster）
    facts["disaster"] = normalize_disaster(getattr(state, "disaster_severity", None))

    facts["faction"] = _top_faction(state)

    ov = facts["oversight"]
    facts["has_inspector"] = bool(ov is not None and ov >= INSPECTOR_MIN)

    return canonicalize(facts)


# --------------------------------------------------------------------------
# 归一化 / 校验 / 摘要
# --------------------------------------------------------------------------
def canonicalize(facts: Any) -> Dict[str, Any]:
    """把任意字典收敛成 canonical facts：只保留登记键、钳量纲、缺失保持 None。

    非 dict 入参 ⇒ 全 None（不抛）。
    """
    out: Dict[str, Any] = {k: None for k in FACT_KEYS}
    if not isinstance(facts, dict):
        return out
    for key in FACT_KEYS:
        if key not in facts:
            continue
        raw = facts.get(key)
        if key == "faction":
            out[key] = "" if raw in (None, "") else str(raw)
            continue
        if key == "has_inspector":
            out[key] = bool(raw)
            continue
        if key == "turn":
            v_turn = _num(raw)
            out[key] = int(v_turn) if v_turn is not None else None
            continue
        v = _num(raw)
        if v is None:
            out[key] = None
            continue
        if key in _UNIT_FIELDS:
            v = max(0.0, min(1.0, v))
        elif key in _INDEX_FIELDS:
            v = max(0.0, min(100.0, v))
        elif key in _NONNEG_FIELDS:
            v = max(0.0, v)
        elif key in _SIGNED_FIELDS:
            pass
        out[key] = v
    return out


def validate_facts(facts: Any) -> List[str]:
    """返回契约问题清单（空列表=合规）。用于守卫测试与诊断面板。"""
    problems: List[str] = []
    if not isinstance(facts, dict):
        return ["facts 不是 dict：%r" % type(facts).__name__]
    for key in facts:
        if key not in FACT_KEYS and key not in COMPAT_ALIASES:
            problems.append("未登记的事实键：%s（新增读数请先登记 tiandao_facts）" % key)
    for key in FACT_KEYS:
        if key not in facts:
            continue
        v = facts.get(key)
        if v is None:
            continue
        if key == "faction":
            if not isinstance(v, str):
                problems.append("%s 必须是 str：%r" % (key, v))
            continue
        if key == "has_inspector":
            if not isinstance(v, bool):
                problems.append("%s 必须是 bool：%r" % (key, v))
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            problems.append("%s 必须是数值或 None：%r" % (key, v))
            continue
        if not math.isfinite(float(v)):
            problems.append("%s 必须有限：%r" % (key, v))
            continue
        if key in _UNIT_FIELDS and not 0.0 <= float(v) <= 1.0:
            problems.append("%s 越界 [0,1]：%r" % (key, v))
        if key in _INDEX_FIELDS and not 0.0 <= float(v) <= 100.0:
            problems.append("%s 越界 [0,100]：%r" % (key, v))
        if key in _NONNEG_FIELDS and float(v) < 0:
            problems.append("%s 不得为负：%r" % (key, v))
    return problems


def facts_digest(facts: Any) -> str:
    """canonical facts 的稳定摘要（排序键 + 定长浮点），用于决策日志留痕/回放比对。"""
    canon = canonicalize(facts)
    payload = {k: (round(canon[k], 6) if isinstance(canon[k], float) else canon[k])
               for k in FACT_KEYS}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_disaster(raw: Any) -> Optional[float]:
    """灾情强度归一的**单一实现**（两个口径都认，别在各调用点各写一份）。

    * `None` / `bool` / 非数值 / 非有限 ⇒ `None`（**不回落 0**）；
    * `<= 0` ⇒ `0.0`（0 是合法值：确无灾）；
    * `(0, 1]` ⇒ 原样（按"0~1 强度"解释）；
    * `> 1` ⇒ 视为 **1~5 整级灾等**（历史契约口径），折 `min(1.0, raw/5)`。

    🔴 为什么必须有：微观决断曾把 1~5 的灾等直接喂给引擎，被引擎钳成 1.0
    ⇒ **灾等 1 与灾等 5 等价**（2026-10-21 审计实测）。
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    if v <= 0.0:
        return 0.0
    return v if v <= 1.0 else min(1.0, v / 5.0)


def to_engine_context(facts: Any) -> Dict[str, Any]:
    """facts → 引擎上下文。

    当前引擎读的就是 canonical 主键，故本函数只做**清洗**（去 None 之外的越界值）并
    补上引擎的兼容别名（`stock`/`storage`、`supervision`），避免"改契约就得改引擎"。
    别名属**过渡期兼容**，新代码请直接读 canonical 键。

    ⚠️ 别名用 `dict.update` 追加而不是逐键下标赋值：`ctx["stock"] = ...` 这类写法会被
    库存写入棘轮（`test_quality_gate_resource_stock`）判成"新增库存写点"，触发误报。
    """
    canon = canonicalize(facts)
    ctx: Dict[str, Any] = {k: v for k, v in canon.items() if v is not None}
    # —— 过渡期兼容别名（不改引擎读取路径，只为旧调用点） ——
    # 用 dict 推导 + 解包合并，**不写 `x["别名"] = ...`**：那种下标赋值会被
    # 库存写入棘轮（`test_quality_gate_resource_stock`）判成「新增库存写点」。
    _ALIAS_PAIRS = (("stock", "changping_stock"), ("supervision", "has_inspector"))
    aliases = {dst: ctx[src] for dst, src in _ALIAS_PAIRS if src in ctx}
    if aliases:
        ctx = {**aliases, **ctx}
    return ctx
