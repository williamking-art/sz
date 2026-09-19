# -*- coding: utf-8 -*-
"""宋祚 · 州路简报（core/region_brief.py）—— **只读派生视图**

依据：`_dev_tools/game-docs/docs/游戏机制说明.md`（州县/民生/粮储口径）与
《明末力挽狂澜》可解释面板经验（`D:\\codebuddy\\MingSalvageSim_经验与宋祚改善建议.md` §4）。

## 纪律（POP 挂载律，见《游戏机制说明》§五）
1. 本模块**只读**：不写任何 POP `size/wealth/grain`、不写国库/内帑/州县字段；
2. 不新建与 POP 平行的独立存量账本——所有数字都是既有派生函数
   （`calc_monthly_tax_income` / `calc_army_cash` / `calc_army_grain`）与州县既有字段的组合；
3. 供 `/api/readouts`（薄壳）与前端「州县」面板消费；**算法单点在此**，前端不复制。

## 多模型复审后的修正（gemini-3.8-flash + gpt-6-astra，2026-09-19）
- `_num` 改用 `math.isfinite`：`inf/-inf` 不再漏进 `int()` 与 JSON（gpt-6-astra A1）；
- 派生函数返回值做类型校验，坏返回不再炸 `build_region_brief`（A2）；
- POP/州县脏数据（非 dict、None）全程容错（A3）；
- `grain_months` 取消 `99` 哨兵：仅在**无口粮需求**时为 `None`，否则给真实月数（A6/gemini-1）；
- **粮储安全垫把驻军月粮计入分母**（gemini-D1）：大军驻扎的路不再"虚假乐观"；
- 全国税额以**核心派生值**为权威，逐路求和仅作诊断（A4/D2）；
- 派生失败不再静默归零：`readout_status` 标记 `ok|partial` 并记 warning（A8/D3/D5）；
- 排序加次级键，前后端同分顺序一致（D4）；
- 指标统一规范化到业务值域（0–100 / ≥0），原因文本随之可信（A5/D1）。
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Tuple

from content.data import GRAIN_CONSUME_PER_CAPITA, PREFECTURE_LIST
from core.numeric import parse_number as _num, clamp as _clamp

log = logging.getLogger("region_brief")

__all__ = ["build_region_brief", "route_risk"]


def _route_literacy(state, name: str):
    """该路识字率（派生自**各地 POP 自有** literacy；取不到 → None，**不伪造**）。"""
    try:
        from core.literacy import route_literacy
        return route_literacy(state, name)
    except Exception:  # noqa: BLE001
        return None

# 风险分权重（按"失衡致命度"排序；动乱与民心为主因）
_W_UNREST = 1.0          # 动乱本身（0–100）
_W_SUPPORT = 1.2         # 民心不足（低于 50 起算）
_W_GENTRY = 0.6          # 士绅抵抗（高于 30 起算）
_W_DEFENSE = 0.8         # 城防不足（低于 40 起算）
_W_GRAIN = 45.0          # 口粮/军粮不足 1 个月时的惩罚（断粮即溃，权重须显著）

RISK_SAFE = 30
RISK_WARN = 60

_SAFE_MONTHS = 12.0      # 安全垫 ≥12 个月视为充裕（不再加分）


def _as_map(v: Any) -> Dict[str, Any]:
    """派生函数返回值归一化（None/列表/标量 → 空字典）。"""
    return v if isinstance(v, dict) else {}


def route_risk(row: Dict[str, Any]) -> Dict[str, Any]:
    """州路风险分（0–100，高=危险）+ 触发原因。

    纯函数、无副作用；输入若有脏值先规范化再计分，故：
    - 分数恒在 [0,100]；
    - `grain_months` 为 None（无口粮需求）时不扣分；0 表示断粮，按最重处理。
    """
    unrest = _clamp(_num(row.get("unrest")), 0.0, 100.0)
    support = _clamp(_num(row.get("public_support"), 50.0), 0.0, 100.0)
    gentry = _clamp(_num(row.get("gentry_resistance"), 30.0), 0.0, 100.0)
    defense = _clamp(_num(row.get("city_defense"), 40.0), 0.0, 100.0)
    raw_months = row.get("grain_months")
    months = None if raw_months is None else max(0.0, _num(raw_months, _SAFE_MONTHS))

    score = unrest * _W_UNREST
    score += max(0.0, 50.0 - support) * _W_SUPPORT
    score += max(0.0, gentry - 30.0) * _W_GENTRY
    score += max(0.0, 40.0 - defense) * _W_DEFENSE
    if months is not None and months < 1.0:
        score += (1.0 - months) * _W_GRAIN
    score = _clamp(score, 0.0, 100.0)

    hints: List[str] = []
    if unrest >= 50:
        hints.append(f"动乱{unrest:.0f}")
    if support < 40:
        hints.append(f"民心仅{support:.0f}")
    if gentry >= 60:
        hints.append(f"士绅阻力{gentry:.0f}")
    if defense < 30:
        hints.append(f"城防仅{defense:.0f}")
    if months is not None and months < 1.0:
        hints.append(f"粮储不足（{months:.2f}月）")
    if not hints:
        hints.append("诸项尚平")

    label = "安" if score < RISK_SAFE else ("警" if score < RISK_WARN else "危")
    return {"risk_score": round(score, 1), "risk_label": label, "risk_hints": hints}


def build_region_brief(state) -> Dict[str, Any]:
    """构建州路简报（**只读**）。

    返回 `{"routes": [...], "top_risk": [...], "nation": {...}, "readout_status": "ok"|"partial"}`。
    `readout_status` 为 `partial` 时表示某个核心派生函数失败（已记 warning），
    此时对应字段回落为 0/空——**面板据此提示"读数不完整"，不与"确实为 0"混淆**。
    """
    errors: List[str] = []

    def _derive(label: str, fn) -> Tuple[float, Dict[str, Any]]:
        """调用核心派生函数并做**完整校验**：异常、非有限总额、坏映射结构都要记 partial。

        复审意见（gpt-6-astra C1）：只捕获异常不够——返回 `(inf, {})` / `(None, {})` 时
        `_num` 会静默转 0 而不记错，`readout_status` 会误判为 ok。
        """
        try:
            total, by_route = fn()
        except Exception as e:  # noqa: BLE001  只读视图不得因单点派生失败而整体 500
            errors.append(f"{label}: {type(e).__name__}")
            log.warning("region_brief 派生异常（%s）：%s", label, e)
            return 0.0, {}
        bad = False
        try:
            tf = float(total)
            if not math.isfinite(tf):
                bad = True
        except (TypeError, ValueError, OverflowError):
            bad = True
        if not isinstance(by_route, dict):
            bad = True
        if bad:
            errors.append(f"{label}: bad_return")
            log.warning("region_brief 派生返回非法（%s）：total=%r by_route=%s",
                        label, total, type(by_route).__name__)
            return 0.0, {}
        return tf, by_route

    tax_total, tax_by_route = _derive("tax", state.calc_monthly_tax_income)
    army_cash_total, army_cash_by_route = _derive("army_cash", state.calc_army_cash)
    army_grain_total, army_grain_by_route = _derive("army_grain", state.calc_army_grain)
    # 核心总额同样钳非负（复审 gpt-6-astra A5：负的军粮/军饷不得抵消或反向计入国家统计）
    tax_total = max(0.0, _num(tax_total))
    army_cash_total = max(0.0, _num(army_cash_total))
    army_grain_total = max(0.0, _num(army_grain_total))

    prefectures = state.prefectures if isinstance(getattr(state, "prefectures", None), dict) else {}

    routes: List[Dict[str, Any]] = []
    tax_raw: Dict[str, float] = {}
    for name in PREFECTURE_LIST:
        p = prefectures.get(name)
        p = p if isinstance(p, dict) else {}
        pops = _as_map(p.get("pops"))

        # 人口与口粮月耗（民口 + 驻军口粮）——军粮计入分母：大军驻扎的路粮储压力更大
        pop_total = 0
        grain_need = 0.0
        for k, v in pops.items():
            n = int(_num((v or {}).get("size") if isinstance(v, dict) else 0))
            pop_total += n
            grain_need += n * _num(GRAIN_CONSUME_PER_CAPITA.get(k, 0.5), 0.5)
        if pop_total <= 0:
            pop_total = int(_num(p.get("population")))
            # 复审（gemini C1）：无 POP 细分但有总人口时，口粮需求不能丢，否则安全垫虚高
            if pop_total > 0 and grain_need <= 0:
                grain_need = pop_total * 0.5          # 平民口径 0.5 石/人·月
        # 复审（gpt-6-astra A5）：军粮负值会反向抵消需求，须钳到非负
        army_grain = max(0.0, _num(army_grain_by_route.get(name)))
        grain_need_total = grain_need + army_grain

        stock = max(0.0, _num(p.get("storage")) + _num(p.get("changping_stock")))
        months = round(max(0.0, stock / grain_need_total), 2) if grain_need_total > 0 else None

        raw_tax = _num(tax_by_route.get(name))
        tax_raw[name] = raw_tax
        _lit = _route_literacy(state, name)
        row: Dict[str, Any] = {
            "name": name,
            "display_name": str(p.get("name") or name),
            "controlled_by": str(p.get("controlled_by") or "宋"),
            "households": int(_num(p.get("households"))),
            "population": pop_total,
            "land": int(_num(p.get("land"))),
            "hidden_land": int(_num(p.get("hidden_land"))),
            "mood": round(_clamp(_num(p.get("mood")), 0, 100), 1),
            "govern": round(_clamp(_num(p.get("govern")), 0, 100), 1),
            "public_support": round(_clamp(_num(p.get("public_support"), _num(p.get("mood"), 50.0)), 0, 100), 1),
            "gentry_resistance": round(_clamp(_num(p.get("gentry_resistance"), 30.0), 0, 100), 1),
            "city_defense": round(_clamp(_num(p.get("city_defense"), 40.0), 0, 100), 1),
            "unrest": round(_clamp(_num(p.get("unrest")), 0, 100), 1),
            "fiscal": round(_clamp(_num(p.get("fiscal"), 50.0), 0, 100), 1),
            # 识字率（2026-09-19 新增，core/literacy.py）：**各地 POP 自有**识字率按
            # 人口加权的派生读——政令能否"写下去、读得懂"的弱关联项
            "literacy": (round(_clamp(_num(_lit, 0.0), 0, 100), 1) if _lit is not None else None),
            "grain_year": round(max(0.0, _num(p.get("grain"))), 0),
            "grain_stock": round(stock, 0),
            "grain_months": months,
            "tax_month": round(raw_tax, 2),                                # 展示值（诊断用求和）
            "army_cash_month": round(max(0.0, _num(army_cash_by_route.get(name))), 2),
            "army_grain_month": round(army_grain, 1),
        }
        row.update(route_risk(row))
        routes.append(row)

    # 全国税额以**核心派生值**为权威（逐路展示值求和仅作诊断）
    routes_sum = round(sum(r["tax_month"] for r in routes), 2)
    if tax_total > 0 and abs(routes_sum - round(tax_total, 2)) > 1e-6:
        log.debug("region_brief：逐路展示值求和 %.2f 与核心派生 %.2f 存在舍入差（正常）",
                  routes_sum, tax_total)
    # 复审（gemini B1）：占比用**未舍入**原始值算，避免"占比之和≠1"
    for r in routes:
        r["tax_share"] = round(tax_raw[r["name"]] / tax_total, 4) if tax_total > 0 else 0.0

    # 复审（gemini C2）：敌占/未控州县不进"内政预警"与全国加权，避免失真
    mine = [r for r in routes if r["controlled_by"] in ("宋", "")] or routes
    foreign = [r for r in routes if r not in mine]
    ranked = sorted(mine, key=lambda r: (-r["risk_score"], r["name"]))   # 稳定次级键
    pop_sum = sum(r["population"] for r in mine)
    nation = {
        "routes": len(routes),
        "routes_mine": len(mine),
        "routes_foreign": len(foreign),
        "population": pop_sum,
        "households": sum(r["households"] for r in mine),
        "land": sum(r["land"] for r in mine),
        "grain_stock": round(sum(r["grain_stock"] for r in mine), 0),
        "tax_month": round(tax_total, 2),                              # 权威：核心派生值
        "tax_month_routes_sum": routes_sum,                            # 诊断：逐路展示值之和
        # 复审（gpt-6-astra C2）：军饷/军粮与税额同策略——核心总额为权威，逐路求和作诊断
        "army_cash_month": round(army_cash_total, 2),
        "army_cash_routes_sum": round(sum(r["army_cash_month"] for r in routes), 2),
        "army_grain_month": round(army_grain_total, 1),
        "army_grain_routes_sum": round(sum(r["army_grain_month"] for r in routes), 1),
        "public_support_weighted": round(
            sum(r["public_support"] * r["population"] for r in mine) / max(1, pop_sum), 2),
        "risk_counts": {
            "安": sum(1 for r in mine if r["risk_label"] == "安"),
            "警": sum(1 for r in mine if r["risk_label"] == "警"),
            "危": sum(1 for r in mine if r["risk_label"] == "危"),
        },
    }
    return {
        "routes": routes,
        "top_risk": ranked[:5],
        "nation": nation,
        "readout_status": "partial" if errors else "ok",
        "readout_errors": errors,
    }
