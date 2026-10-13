# -*- coding: utf-8 -*-
"""家计**影子校准** + 经济归属守恒读数（主线 E 第一切片） —— M52。

文档口径（`reviews/未完成事项落地实施计划_2026-10-04.md` §6.2x）：
```
家计(阶层, 派系, 治所) = Σ[ wealth + 存粮折价 + 生业应收 ] − Σ[ 口粮 + 租 + 税 + 役 ]
#   · 单位：贯；粮折价**必须用基准价**（不得用当月市价，以免自激）
#   · 🔴 任一分项不可读 ⇒ 家计 = None（**不是 0**；回落 0 会把"没数据"判成"赤贫"）
#   · 一个数值、三重读法（等第/贫富/生活水平）必须**同源**，不得各算一遍
#   · 五等：上户 ≥阈值4 ＞ 中户 ≥阈值3 ＞ 下户 ≥阈值2 ＞ 贫民 ≥阈值1 ＞ 无业/逃户
#   · **等第 ≠ 身份**（士绅可贫、官僚可穷）
```
本模块**只读**（Jev choose A 0.948），做两件事：

1. **家计影子**：把**可读分项**（`wealth`、存粮×基准价）单列出来，但**整项按规格报 `None`**
   —— 因为「生业应收」「口粮/租/税/役」在代码里**没有权威单点**（不臆造）。
   等第 `tier` **必须由调用方传入阈值**；缺省 ⇒ `None` + reason（**文档只给符号名 阈值1..4，无具体数值**）。
2. **经济归属守恒读数**：逐 `(路, 类)` 核 **Σ子池 == 父 POP**（逐字段），
   子池即既有 `economic_affiliation`（`pop_bridge.AFFILIATION_FIELDS`，独立通道）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

#: 五等（**判据顺序即文档顺序**：由上到下递减）
TIER_LABELS: Tuple[str, ...] = ("上户", "中户", "下户", "贫民", "无业/逃户")

#: 家计**收入侧**分项（文档顺序）
INCOME_ITEMS = ("wealth", "grain_value", "operating_receivable")
#: 家计**支出侧**分项（文档顺序）
EXPENSE_ITEMS = ("food", "rent", "tax", "corvee")

__all__ = [
    "SCHEMA_VERSION", "TIER_LABELS", "INCOME_ITEMS", "EXPENSE_ITEMS",
    "tier_of", "income_items", "expense_items", "livelihood",
    "affiliation_conservation", "survey_livelihood_shadow",
]


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _prefs(state) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None)
    return prefs if isinstance(prefs, dict) else None


def _pop_row(state, route: str, cls: str) -> Optional[Dict[str, Any]]:
    prefs = _prefs(state)
    if prefs is None:
        return None
    pdata = prefs.get(route)
    pops = (pdata or {}).get("pops") if isinstance(pdata, dict) else None
    if not isinstance(pops, dict):
        return None
    row = pops.get(cls)
    return row if isinstance(row, dict) else None


def _flatten_sum(v) -> Optional[float]:
    """数值直取；字典（下沉档的治所桶，如 `grain: {治所: 石}`）⇒ 递归求和；其它 ⇒ `None`。"""
    n = _num(v)
    if n is not None:
        return n
    if isinstance(v, dict):
        tot = 0.0
        seen = False
        for x in v.values():
            y = _flatten_sum(x)
            if y is not None:
                tot += y
                seen = True
        return tot if seen else None
    return None


def _pop_value(state, route: str, cls: str, field: str) -> Optional[float]:
    """读 POP 字段值：**优先既有单点 `pop_bridge.pop_get`**（真账聚合），回落原行（含桶摊平）。

    🔴 为什么不能直接读行：下沉档 `pops[类][字段]` 可能是**治所桶**（实测 `grain` 如此）
    ⇒ 直接 `float()` 得到 `None`，会把"有粮"误判成"不可读"（同一形态问题在 stock_identity 也踩过）。
    """
    try:
        from core.foundation.ledger.pop_bridge import pop_get
        prefs = _prefs(state)
        pdata = (prefs or {}).get(route)
        if isinstance(pdata, dict):
            v = pop_get(pdata, cls, field)
            n = _flatten_sum(v)
            if n is not None:
                return n
    except Exception:                                       # noqa: BLE001
        log.warning("livelihood_shadow: pop_get 不可用，回落直读", exc_info=True)
    row = _pop_row(state, route, cls)
    if row is None:
        return None
    return _flatten_sum(row.get(field))


def grain_base_price(regime: Optional[str] = None) -> Optional[float]:
    """粮的**基准价**（**口径单点**；文档：粮折价用基准价，**不得用当月市价**以免自激）。

    🔴 实测（2026-10-13，M70 修）：`song_job_cfg()["grain_price0"]` 是**按政权分档**的
    `dict`（`{'游牧帝国': 2.2, '党项蕃国': 2.0, 'default': 1.6}`）⇒ 必须**取本政权档**
    （无专档 ⇒ `default`）。**原实现用 `_flatten_sum` 求和得 5.8（= 2.2+2.0+1.6）**，
    误差 **3.6×**（污染 M52 家计的所有"粮折价"项，并会让 M69 的作坊采购预算虚高 3.6×）。
    正确范式照抄既有 `wage_rate_for(building, regime)`（按政权键 → `default` → `None`）。

    另：`MATERIAL_PRICE_BASE` **没有粮维**（只有 盐/茶/丝/麻/蔗/果/木/石/铁/wine）；
    `state.grain_price` 是**当月市价**，按文档**不得**用于折价。
    取不到 ⇒ `None`（**缺失≠0**，不回落 0）。
    """
    try:
        from core.building_jobs import song_job_cfg
        raw = (song_job_cfg() or {}).get("grain_price0")
    except Exception:                                       # noqa: BLE001
        log.warning("livelihood_shadow: 粮价单点不可读", exc_info=True)
        return None
    if isinstance(raw, dict):
        # **按政权取档**（不是求和！）：本政权 → 宋 → default
        for key in ([regime] if regime else []) + ["宋", "default"]:
            v = _num(raw.get(key)) if key else None
            if v is not None:
                return v
        return None                                         # 分档 dict 但无可用档 ⇒ None
    return _num(raw)                                        # 兼容标量写法


def _grain_base_price() -> Optional[float]:
    """**兼容别名**（旧内部名；M70 起正名为公开单点 `grain_base_price`）。"""
    return grain_base_price()


def tier_of(value: Optional[float], thresholds: Optional[Sequence[float]]) -> Dict[str, Any]:
    """家计 → **五等等第**。`thresholds` 必须给 4 个**升序**数（阈值1..4）；否则 ⇒ `None`。

    🔴 **阈值不臆造**：文档只给符号名，故缺省一律 `None` + reason。
    非法输入（长度≠4 / 非升序 / 非数值）⇒ **拒绝**（`ValueError`，与项目"拒绝式处理非法输入"一致）。
    """
    if thresholds is None:
        return {"tier": None,
                "reason": ("等第阈值未给：文档只给符号名「阈值1..阈值4」、**无具体数值** ⇒ "
                           "不臆造；须由调用方（口径裁定/校准）传入 4 个升序阈值")}
    th = list(thresholds)
    if len(th) != 4:
        raise ValueError(f"thresholds 须为 4 个数（阈值1..4），得 {len(th)} 个")
    try:
        vals = [float(x) for x in th]
    except (TypeError, ValueError) as e:
        raise ValueError(f"thresholds 必须都是数值：{e}") from e
    if any(vals[i] >= vals[i + 1] for i in range(3)):
        raise ValueError(f"thresholds 必须严格升序（阈值1<2<3<4），得 {vals}")
    if value is None:
        return {"tier": None, "reason": "家计不可计算（分项缺失）⇒ 等第未定义（缺失≠0）"}
    v = float(value)
    if v >= vals[3]:
        return {"tier": TIER_LABELS[0], "reason": None}
    if v >= vals[2]:
        return {"tier": TIER_LABELS[1], "reason": None}
    if v >= vals[1]:
        return {"tier": TIER_LABELS[2], "reason": None}
    if v >= vals[0]:
        return {"tier": TIER_LABELS[3], "reason": None}
    return {"tier": TIER_LABELS[4], "reason": None}


def income_items(state, route: str, cls: str) -> Dict[str, Any]:
    """收入侧**逐分项**读数：可读给值，不可读给 `None` + reason（**不臆造**）。"""
    row = _pop_row(state, route, cls)
    out: Dict[str, Any] = {"route": route, "cls": cls, "items": {}, "missing": []}
    if row is None:
        out["reason"] = "POP 行不存在（缺失≠0）"
        out["missing"] = list(INCOME_ITEMS)
        out["items"] = {k: None for k in INCOME_ITEMS}
        return out
    w = _pop_value(state, route, cls, "wealth")
    out["items"]["wealth"] = None if w is None else int(w)
    if w is None:
        out["missing"].append("wealth")
    grain = _pop_value(state, route, cls, "grain")
    px = _grain_base_price()
    if grain is None or px is None:
        out["items"]["grain_value"] = None
        out["missing"].append("grain_value")
    else:
        out["items"]["grain_value"] = int(round(grain * px))
    # 生业应收（工坊/田产等）：**代码内无权威单点** ⇒ 不臆造
    out["items"]["operating_receivable"] = None
    out["missing"].append("operating_receivable")
    out["reason"] = ("生业应收（工坊/田产收益）在代码内**无权威单点** ⇒ 该项不可读；"
                     "按文档『任一分项不可读 ⇒ 家计 = None』故家计不可计算（不臆造）")
    return out


def expense_items(state, route: str, cls: str) -> Dict[str, Any]:
    """支出侧**逐分项**读数：口粮/租/税/役 均**无权威单点** ⇒ 全 `None` + reason。"""
    row = _pop_row(state, route, cls)
    return {"route": route, "cls": cls,
            "items": {k: None for k in EXPENSE_ITEMS},
            "missing": list(EXPENSE_ITEMS),
            "reason": ("口粮/租/税/役 的**户级权威单点不存在**（现有税收在政权/路级，"
                       "非户级家计支出）⇒ 支出侧不可读；**不臆造**") if row is not None
                      else "POP 行不存在（缺失≠0）"}


def livelihood(state, route: str, cls: str,
               thresholds: Optional[Sequence[float]] = None) -> Dict[str, Any]:
    """家计影子读数（**只读**）：分项可读则单列；**整项按规格** `value=None` + 缺项清单。"""
    inc = income_items(state, route, cls)
    exp = expense_items(state, route, cls)
    missing = sorted(set(inc.get("missing") or []) | set(exp.get("missing") or []))
    readable = {k: v for k, v in (inc.get("items") or {}).items() if v is not None}
    partial = int(sum(readable.values())) if readable else None
    value = None                                     # 🔴 规格：任一分项不可读 ⇒ None
    tier = tier_of(value, thresholds)
    return {"route": route, "cls": cls, "value": value,
            "partial_income_sum": partial,
            "partial_note": ("**分项合计（wealth+存粮折价），不是家计**；不得当作家计使用"),
            "income": inc, "expense": exp, "missing": missing,
            "tier": tier["tier"], "tier_reason": tier["reason"]}


def affiliation_conservation(state) -> Dict[str, Any]:
    """经济归属守恒：逐 `(路, 类, 字段)` 核 **Σ子池 == 父 POP**（规格要求「份额和 == 父 POP」）。"""
    try:
        from core.foundation.ledger.pop_bridge import AFFILIATION_FIELDS
    except Exception:                                       # noqa: BLE001
        return {"ok": None, "reason": "AFFILIATION_FIELDS 不可用", "checked": 0, "mismatches": []}
    prefs = _prefs(state)
    if prefs is None:
        return {"ok": None, "reason": "无 prefectures", "checked": 0, "mismatches": []}
    checked = 0
    mismatches: List[Dict[str, Any]] = []
    classes_with_aff = 0
    for route, pdata in prefs.items():
        pops = (pdata or {}).get("pops") if isinstance(pdata, dict) else None
        if not isinstance(pops, dict):
            continue
        for cls, row in pops.items():
            if not isinstance(row, dict):
                continue
            aff = row.get("economic_affiliation")
            if not isinstance(aff, dict) or not aff:
                continue
            classes_with_aff += 1
            for field in AFFILIATION_FIELDS:
                s = 0.0
                seen = False
                for _rel, part in aff.items():
                    if isinstance(part, dict):
                        v = _num(part.get(field))
                        if v is not None:
                            s += v
                            seen = True
                parent = _num(row.get(field))
                if not seen and parent is None:
                    continue
                checked += 1
                if parent is None or abs(s - parent) > 1e-6:
                    mismatches.append({"route": route, "cls": cls, "field": field,
                                       "subpool_sum": int(s), "parent": None if parent is None
                                       else int(parent)})
    if classes_with_aff == 0:
        return {"ok": None, "reason": "全库无 economic_affiliation 子池（未登记归属）",
                "checked": 0, "mismatches": [], "classes_with_affiliation": 0}
    return {"ok": not mismatches, "checked": checked, "classes_with_affiliation": classes_with_aff,
            "mismatch_count": len(mismatches), "mismatches": mismatches[:50], "reason": None}


def survey_livelihood_shadow(state) -> Dict[str, Any]:
    """汇总：家计可计算数（预期 0 + 原因）· 等第已定数（无阈值 ⇒ 0）· 归属守恒。"""
    prefs = _prefs(state)
    if prefs is None:
        return {"schema_version": SCHEMA_VERSION, "reason": "无 prefectures（缺失≠0）"}
    n = computable = tier_known = 0
    sample = None
    for route, pdata in prefs.items():
        pops = (pdata or {}).get("pops") if isinstance(pdata, dict) else None
        if not isinstance(pops, dict):
            continue
        for cls in pops:
            rep = livelihood(state, route, cls)          # 不给阈值 ⇒ tier 一律 None
            n += 1
            if rep["value"] is not None:
                computable += 1
            if rep["tier"] is not None:
                tier_known += 1
            if sample is None:
                sample = rep
    return {"schema_version": SCHEMA_VERSION, "pop_rows": n,
            "livelihood_computable": computable, "tier_known": tier_known,
            "affiliation": affiliation_conservation(state),
            "partial_income_available": (None if not sample else sample["partial_income_sum"]),
            "sample": sample}
