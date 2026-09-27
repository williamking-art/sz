# -*- coding: utf-8 -*-
"""宋祚 · 州路简报（core/region_brief.py）—— **只读派生视图**

依据：`_dev_tools/game-docs/docs/游戏机制说明.md`（州县/民生/粮储口径）与
《明末力挽狂澜》可解释面板经验（`_dev_tools/game-docs/reviews/MingSalvageSim_经验与宋祚改善建议.md` §4）。

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

__all__ = ["build_region_brief", "route_risk", "build_prefecture_brief",
           "hidden_surveyed", "route_military_summary"]


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


# ============================================================
# 治安（**正极性**）与隐田脱敏 —— 2026-09-27 用户口径
# ============================================================
_SECURITY_BANDS = ((80.0, "太平"), (60.0, "尚可"), (40.0, "多事"), (0.0, "不靖"))
_HIDDEN_BANDS = ((0.30, "隐匿极重"), (0.20, "隐匿较重"), (0.10, "隐匿尚轻"), (0.0, "隐匿轻微"))
_HIDDEN_SURVEYED_RATIO = 0.20      # 与 legacy_mechanic._clear_hidden_land 同门槛
_HIDDEN_POP_COARSE = 50_000        # 隐户约值粗化粒度（"朝廷只知约数"）
_PREF_DEMOG = None


def _security(unrest: Any) -> float:
    """**治安 = 100 − 动乱**（正极性：越高越好）。

    用户口径（2026-09-27）："治安的数值越高肯定治安越好" —— 故不得把 `unrest`
    直接标成"治安"（极性相反）。阈值与既有 `content.data.PROJECT_SECURITY_UNREST = 60`
    对齐：治安 < 40 ⇔ 动乱 > 60 ⇔ 工程降效（同一含义，只换极性）。
    """
    return round(100.0 - _clamp(_num(unrest), 0.0, 100.0), 1)


def _security_label(unrest: Any) -> str:
    s = _security(unrest)
    for lo, word in _SECURITY_BANDS:
        if s >= lo:
            return word
    return "不靖"


def _hidden_pop_est(pops: Dict[str, Any]) -> int:
    """隐户口数**约值**：粗化到 5 万（"朝廷只知约数"），供面板展示。"""
    nong = _as_map((pops or {}).get("农"))
    raw = max(0.0, _num(nong.get("hidden")))
    return int(round(raw / _HIDDEN_POP_COARSE) * _HIDDEN_POP_COARSE)


def hidden_surveyed(p: Dict[str, Any]) -> bool:
    """该路是否**已清丈**（隐匿率 < 0.2）。

    **单一判据**：读数（`_hidden_fields`）与快照脱敏（`backend/server.py::_prefs_desensitized`）
    共用本函数，避免两处阈值漂移。
    """
    land = max(0.0, _num(p.get("land") if isinstance(p, dict) else 0))
    hid = max(0.0, _num(p.get("hidden_land") if isinstance(p, dict) else 0))
    denom = land + hid
    return ((hid / denom) if denom > 0 else 0.0) < _HIDDEN_SURVEYED_RATIO


def _hidden_fields(p: Dict[str, Any]) -> Dict[str, Any]:
    """隐田字段：**未清丈只下发约值**，清丈后才给真数（脱敏）。

    用户口径：朝廷只知约值、清丈才知真数（POP 改良 §4.3）。
    清丈判据 = 隐匿率 < 0.2（与 `legacy_mechanic._clear_hidden_land` 同门槛，路级口径）。
    约值粗化到 **50 万亩**，故无法反推真值；`hidden_land` 仅在已清丈时出现。
    """
    land = max(0.0, _num(p.get("land")))
    hid = max(0.0, _num(p.get("hidden_land")))
    denom = land + hid
    ratio = (hid / denom) if denom > 0 else 0.0
    surveyed = hidden_surveyed(p)
    out: Dict[str, Any] = {
        "surveyed": surveyed,
        "hidden_land_band": next(w for lo, w in _HIDDEN_BANDS if ratio >= lo),
        "hidden_land_est": int(round(hid / 500_000.0) * 500_000),   # 约值（粗化）
    }
    if surveyed:
        out["hidden_land"] = int(hid)                               # 清丈后才给真数
    return out


# ============================================================
# 州府级档案（P0，2026-09-27 方案 §4）
# ============================================================
def _pref_demog() -> Dict[str, Any]:
    """州府级静态底盘（content/demography.py 为单一权威源）；懒加载 + 容错。"""
    global _PREF_DEMOG
    if _PREF_DEMOG is None:
        try:
            from content.demography import prefecture_demog
            _PREF_DEMOG = prefecture_demog() or {}
        except Exception as e:            # noqa: BLE001
            log.warning("region_brief：州府级底盘不可用：%s", e)
            _PREF_DEMOG = {}
    return _PREF_DEMOG


def _circuit_to_route() -> Dict[str, str]:
    """行政路（CIRCUIT_INFO 键）→ 游戏单位路（state.prefectures 键）。"""
    out: Dict[str, str] = {}
    try:
        from content.geo_admin import CIRCUIT_INFO
        for circ, info in CIRCUIT_INFO.items():
            gu = (info or {}).get("game_unit")
            if gu:
                out[circ] = str(gu)
    except Exception:                     # noqa: BLE001
        log.warning("region_brief：CIRCUIT_INFO 不可用，州府级档案降级为空")
    return out


def build_prefecture_brief(state) -> Dict[str, Any]:
    """州府级档案：把**路级实数**按 demography 份额分到府/州（只读派生）。

    纪律：
      ① **不新增账本**：府级只做份额分配，Σ府 == 路级（尾差归最大府，与
         `settlement_econ_helpers._distribute_pop_wealth` 同口径）；
      ② 路级动态量（治安/城防/民心/士绅抵抗/识字率）**不分配到府** —— 它们在数据上
         本就只有路级值，面板以"（全路）"标注直显，避免把派生值当真状态；
      ③ 隐田/隐户沿用 `_hidden_fields` 的约值口径。
    返回 {"prefectures": [...], "audit": {...}}；`audit.violations` 非空即守恒被破坏。
    """
    routes = {r["name"]: r for r in build_region_brief(state).get("routes", [])}
    c2r = _circuit_to_route()
    static = _pref_demog()

    members: Dict[str, List[Dict[str, Any]]] = {}
    for pref, d in sorted(static.items()):
        circ = str((d or {}).get("circuit") or "")
        route = c2r.get(circ)
        if not route or route not in routes:
            continue
        members.setdefault(route, []).append({
            "name": pref, "circuit": circ, "route": route,
            "population": int(_num((d or {}).get("population"))),
            "households": int(_num((d or {}).get("households"))),
            "land": int(_num((d or {}).get("land"))),
            "grain": int(_num((d or {}).get("grain"))),
            "monthly_tax": int(_num((d or {}).get("monthly_tax"))),
        })

    DIMS = (("population", "population"), ("households", "households"),
            ("land", "land"), ("grain_year", "grain"), ("tax_month", "monthly_tax"))
    out: List[Dict[str, Any]] = []
    violations: List[str] = []
    for route, group in sorted(members.items()):
        row = routes[route]
        for out_key, stat_key in DIMS:
            target = row[out_key]
            total_stat = sum(float(m[stat_key]) for m in group) or 0.0
            biggest = max(group, key=lambda m: float(m[stat_key]))
            assigned = 0.0
            for m in group:
                share = (float(m[stat_key]) / total_stat) if total_stat > 0 else 1.0 / len(group)
                val = int(target * share) if out_key != "tax_month" else round(target * share, 2)
                m[out_key] = val
                assigned += val
            rest = round(target - assigned, 2 if out_key == "tax_month" else 6)
            biggest[out_key] = (round(biggest[out_key] + rest, 2) if out_key == "tax_month"
                                else int(biggest[out_key] + rest))
            got = sum(float(m[out_key]) for m in group)
            if abs(got - float(target)) > (0.02 if out_key == "tax_month" else 0.5):
                violations.append(f"{route}.{out_key}: Σ府={got} ≠ 路级={target}")
        for m in group:
            m["share"] = round(float(m["population"]) / max(1.0, float(row["population"])), 4)
            out.append(m)

    return {
        "prefectures": out,
        "audit": {
            "routes": len(members),
            "prefectures": len(out),
            "violations": violations,
        },
    }


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
            # 隐田：**未清丈只下发约值**（真值留服务端）；清丈（隐匿率<0.2）后才给真数
            **_hidden_fields(p),
            # 隐户**约值**（真值属隐藏数值，未清丈快照不下发；清丈后才给真数）
            "hidden_pop_est": _hidden_pop_est(pops),
            "mood": round(_clamp(_num(p.get("mood")), 0, 100), 1),
            "govern": round(_clamp(_num(p.get("govern")), 0, 100), 1),
            "public_support": round(_clamp(_num(p.get("public_support"), _num(p.get("mood"), 50.0)), 0, 100), 1),
            "gentry_resistance": round(_clamp(_num(p.get("gentry_resistance"), 30.0), 0, 100), 1),
            "city_defense": round(_clamp(_num(p.get("city_defense"), 40.0), 0, 100), 1),
            "unrest": round(_clamp(_num(p.get("unrest")), 0, 100), 1),
            # 治安 = 100 − 动乱（**正极性**：越高越好）；单一权威在此派生，前端不自算。
            # 与 data.PROJECT_SECURITY_UNREST=60 对齐：治安<40 ⇔ 工程降效。
            "security": _security(p.get("unrest")),
            "security_label": _security_label(p.get("unrest")),
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

# ============================================================
# 省级军政（P1，2026-09-27 方案 §3）
# ============================================================
def route_military_summary(state, route: str | None = None) -> Dict[str, Any]:
    """省级军政（**只读派生**）：按路聚合 `army_units` 实体。

    - 兵额唯一真账 = `ArmyUnit.troops`（= Σbranches；勿在别处另求和，避免漂移）；
    - 军饷/军粮**复用** `build_region_brief` 的逐路核心派生（`army_cash_month`/`army_grain_month`），
      不重复调用 `calc_army_*`；
    - `route=None` → **全国总览**（逐路行 + 合计）；否则给该路军表 + 该路汇总；
    - 只读：不写 `army_units`、不写任何 POP/国库。
    """
    def _unit_row(u) -> Dict[str, Any]:
        br = getattr(u, "branches", None)
        br = br if isinstance(br, dict) else {}
        try:
            troops = int(getattr(u, "troops", 0) or 0)
        except Exception:                 # noqa: BLE001
            troops = 0
        return {
            "unit_id": str(getattr(u, "unit_id", "") or ""),
            "name": str(getattr(u, "name", "") or ""),
            "army_name": str(getattr(u, "army_name", "") or ""),
            "tier": str(getattr(u, "tier", "") or ""),
            "station": str(getattr(u, "station", "") or ""),
            "defense_line": str(getattr(u, "defense_line", "") or ""),
            "troops": max(0, troops),
            "morale": int(_num(getattr(u, "morale", 0))),
            "training": int(_num(getattr(u, "training", 0))),
            "arrears": max(0, int(_num(getattr(u, "arrears", 0)))),
            "branches": {str(k): max(0, int(_num(v))) for k, v in br.items()},
        }

    all_units = [u for u in (getattr(state, "army_units", None) or [])]
    rows = [_unit_row(u) for u in all_units]
    if route:
        rows = [r for r in rows if r["station"] == route]

    brief = {r.get("name"): r for r in build_region_brief(state).get("routes", [])}
    by_route: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_route.setdefault(r["station"] or "（未列路）", []).append(r)

    route_rows: List[Dict[str, Any]] = []
    for name in sorted(by_route):
        us = by_route[name]
        br = brief.get(name) or {}
        troops = sum(u["troops"] for u in us)
        morale = (sum(u["morale"] * u["troops"] for u in us) / troops) if troops > 0 else 0.0
        route_rows.append({
            "route": name,
            "units": len(us),
            "troops": troops,
            "morale_weighted": round(morale, 1),
            "arrears": sum(u["arrears"] for u in us),
            "cash_month": br.get("army_cash_month"),
            "grain_month": br.get("army_grain_month"),
            "city_defense": br.get("city_defense"),
            "security": br.get("security"),
            "security_label": br.get("security_label"),
            "controlled_by": br.get("controlled_by"),
        })
    nation = {
        "routes": len(route_rows),
        "units": sum(r["units"] for r in route_rows),
        "troops": sum(r["troops"] for r in route_rows),
        "arrears": sum(r["arrears"] for r in route_rows),
        "cash_month": round(sum(_num(r["cash_month"]) for r in route_rows), 2),
        "grain_month": round(sum(_num(r["grain_month"]) for r in route_rows), 1),
    }
    if route:
        hit = next((r for r in route_rows if r["route"] == route), None)
        return {
            "route": route,
            "units": rows,
            "summary": hit or {"route": route, "units": 0, "troops": 0, "morale_weighted": 0.0,
                               "arrears": 0, "cash_month": None, "grain_month": None,
                               "city_defense": None, "security": None, "security_label": None},
            "nation": nation,
        }
    return {"route": None, "routes": route_rows, "nation": nation}
