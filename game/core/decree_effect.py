# -*- coding: utf-8 -*-
"""宋祚 · 诏令实际效果口径（core/decree_effect.py）—— **唯一权威**

依据用户定稿（2026-09-19）：

> 一道诏令的实际效果 = **吏治（强关联）** × 民心 / 文书效率（弱关联）
> **军队是加成而非必须**：诏令与军队**不是强关联**；但**也并非与民政诏令无关**——
> 玩家可以**调兵来确保赈济、赋役、清丈、科举等政令的强制施行**。
> **会签执行率本身就是吏治的表达**（官场配合度），故它也是"吏治"这一强关联项的组成部分。

三条通道（各自有唯一权威，本模块只做**组装**，不重算任何算法）：

| 通道 | 强度 | 来源（唯一权威） |
|---|---|---|
| 吏治 | **强**（唯一强关联） | 会签执行率 `GameState.calc_decree_execution_rate`（逐诏）＋ 吏胥折扣 `core/clerks.decree_execution_mult` |
| 民心 / 识字率 | 弱（幅度 ≤15%） | `state.population_satisfaction`（民心）＋ `state.literacy` / `prefectures[路]["literacy"]`（**识字率**，`core/domains/culture/literacy.py`） |
| 军队 | **条件加成** | `core/army_models.military_channels`：军政类**天然参与**；民政类**玩家调兵强制施行时**参与 |

**军队的精确口径（用户再修正 2026-09-19）**：`kind == "军政"` → 军队天然参与；
`kind == "民政"` → 默认不参与，但 `enforce_troops=True`（本回合确有调兵：事务记录里
`defense_lines.*.garrison` 变化，或诏令显式调兵）时作为**强制施行加成**参与。

边界：本模块只读（不写 state）；逐诏执行率需该诏的派系立场，故面板/AI 只能拿到
**官场配合度代理**（派系满意度），本模块如实标注 `official_support.proxy = True`，
**绝不把代理当成执行率**。
"""
from __future__ import annotations
from core.foundation.common.numeric import parse_number as _num, clamp as _clamp

import logging
from typing import Any, Dict, Optional

log = logging.getLogger("decree_effect")

__all__ = ["STRONG_CHANNEL", "MILITARY_ORGS", "MILITARY_KEYWORDS", "CIVIL_FLOOR",
           "decree_kind", "effect_channels", "decree_effect_mult"]

STRONG_CHANNEL = "clerks"           # 唯一强关联通道（吏治）
CIVIL_FLOOR = 0.85                  # 弱关联通道下限（民心/识字率最差时仍不至归零）
CIVIL_SAT_W = 0.10                  # 民心权重（弱）
CIVIL_LITERACY_W = 0.05             # **识字率**权重（弱）
ARMY_ENFORCE_BONUS = 0.30           # 军队"强制施行"最多补上的**效果缺口比例**（加成，非折扣）

# 军政/边事类判定：机构归属优先，其次标题/正文关键词（启发式，程序判定，可审计）
MILITARY_ORGS = ("枢密院", "兵部", "三衙", "殿前司", "马军司", "步军司")
MILITARY_KEYWORDS = ("调兵", "整军", "阅兵", "边", "戍", "烽", "堡", "寨", "军器",
                     "火器", "马政", "募兵", "裁军", "城防", "军饷", "军粮", "西军")


def decree_kind(org_hint: Optional[str] = None, text: str = "") -> str:
    """诏令类别：`"军政"` 或 `"民政"`（决定军队通道**是否**参与）。

    判据：机构归属命中 `MILITARY_ORGS`，或文本命中 `MILITARY_KEYWORDS`。
    刻意保守：宁可把诏令判成民政（军队不参与），也不把民政错判成军政——
    过度把军队塞进一切诏令，正是本次要纠正的错误。
    """
    if org_hint and any(o in str(org_hint) for o in MILITARY_ORGS):
        return "军政"
    t = str(text or "")
    if any(k in t for k in MILITARY_KEYWORDS):
        return "军政"
    return "民政"


def _official_support_proxy(state) -> Dict[str, Any]:
    """官场配合度**代理**（非执行率）：派系满意度按影响力加权。

    逐诏执行率 `calc_decree_execution_rate` 需要**该诏的派系立场**，盘面读数拿不到，
    故此处只给代理并显式标注 `proxy=True`——**禁止**把它当执行率使用。
    """
    facs = getattr(state, "factions", None) or {}
    num = den = 0.0
    worst = None
    worst_name = None
    for name, f in facs.items():
        if not isinstance(f, dict):
            continue
        sat = _num(f.get("satisfaction"), 50.0)
        inf = max(0.0, _num(f.get("influence"), 0.0))
        num += sat * inf
        den += inf
        if worst is None or sat < worst:
            worst, worst_name = sat, name
    if den <= 0:
        return {"proxy": True, "weighted": None, "min": None, "min_faction": None}
    return {"proxy": True, "weighted": round(num / den, 2),
            "min": round(worst, 2) if worst is not None else None,
            "min_faction": worst_name}


def _literacy_channel(state, route: Optional[str] = None) -> Optional[float]:
    """该路（或全国）**派生识字率**，取不到/非有限时返回 `None`（**不伪造、不回落 0**）。

    审查 S2：旧实现在读数缺失时用 `calc_arrival_rate() * 100` 兜底（实测造出 58.75）
    或 `50.0` 兜底 —— 那是**凭空造一个读数**，违反"缺失 ≠ 0 ≠ 1.0"。
    现按 `core.numeric.finite_or_undefined` 的"未定义"语义处理（单点口径）：
    缺失或 NaN/±Inf 一律 `None`，由调用方**显式标注该维度未定义**并只按已有项计算。
    """
    from core.foundation.common.numeric import finite_or_undefined as _fu
    lit = None
    try:
        from core.domains.culture.literacy import national_literacy, route_literacy
        lit = _fu(route_literacy(state, route) if route else national_literacy(state))
    except Exception as e:  # noqa: BLE001
        log.debug("decree_effect 取派生识字率失败：%s", e)
        lit = None
    if lit is None:
        lit = _fu(getattr(state, "literacy", None))
    return None if lit is None else _clamp(lit, 0.0, 100.0)


def _civil_mult(state, route: Optional[str] = None) -> Optional[float]:
    """**弱关联**通道（0.85–1.0）：民心 ＋ **识字率**。

    - 民心：逐路用该路 `public_support`（缺失回落全国 `population_satisfaction`）；
    - 识字率：**由该路各地各类 POP 自有 literacy 按人口加权派生**
      （`core.domains.culture.literacy.route_literacy`；全国则 `national_literacy`）——
      故 POP 结构/文教变化会立刻反映，无需等结算回写 `state.literacy`。
    幅度刻意压小：吏治才是强关联，民心/识字率不该主导诏令成败。

    审查 S2：识字率缺失时**不再伪造**（旧实现回落 `calc_arrival_rate()*100`）；
    该维度权重本就极小（`CIVIL_LITERACY_W = 0.05`），故缺失时只计民心项，
    并由 `effect_channels` 输出 `literacy_defined=False` 显式标注"该维度未定义"。
    """
    sat = None
    if route:
        p = (getattr(state, "prefectures", None) or {}).get(route)
        if isinstance(p, dict) and p.get("public_support") is not None:
            sat = _num(p.get("public_support"))
    if sat is None:
        sat = _num(getattr(state, "population_satisfaction", 50), 50.0)

    lit = _literacy_channel(state, route)
    val = CIVIL_FLOOR + CIVIL_SAT_W * _clamp(sat, 0.0, 100.0) / 100.0
    if lit is not None:
        val += CIVIL_LITERACY_W * lit / 100.0
    return round(_clamp(val, CIVIL_FLOOR, 1.0), 4)


def effect_channels(state, *, org_hint: Optional[str] = None, text: str = "",
                    route: Optional[str] = None, kind: Optional[str] = None,
                    enforce_troops: bool = False) -> Dict[str, Any]:
    """诏令实际效果的三通道读数（只读；**供面板 / AI 权衡 / 结算消费**）。

    `enforce_troops=True` 表示**玩家本回合调兵强制施行**该诏令（民政诏令的关键杠杆：
    「调兵确保赈济/赋役/清丈/科举落地」）。军政类诏令天然参与，不受该参数影响。

    返回：
      `strong`              = `"clerks"`（唯一强关联通道）
      `clerks_mult`         = 吏胥折扣**本体**（强关联；`core/clerks.decree_execution_mult`）
      `clerks_compliance`   = 知州遵从反应（天道，`{"verdict","mult",...}`；无 route 或不可算 ⇒ `None`）
      `official_support`    = 官场配合度**代理**（会签执行率的盘面近似；`proxy=True`）
      `civil_mult`          = 民心/识字率弱关联系数（0.85–1.0）
      `kind`                = `"军政"` / `"民政"`
      `military`            = `{..., "applies": bool, "enforced": bool}`
      `effect_mult`         = `clerks_mult × clerks_compliance × civil_mult`（军队参与时再补缺口）

    🔴 **口径分层（2026-10-17 修复）**：`clerks_mult` 只表示**吏胥折扣**，不得把遵从度乘进去
    （否则该读数的含义被悄悄改写，撞掉既有验收）。遵从度单列在 `clerks_compliance`，
    在**合成 `effect_mult` 时**作为吏治通道内部的输入参与——通道仍是三条，没有新增乘数。
    """
    kind = kind or decree_kind(org_hint, text)
    clerks_mult = None
    clerks_scope = "全国"
    clerks_view: Dict[str, Any] = {}
    clerks_compliance: Optional[Dict[str, Any]] = None
    try:
        from core.clerks import decree_execution_mult, route_decree_mult, totals
        clerks_view = totals(state) or {}
        # Q12 已决·乙：给了 route 且该路 `clerks_detail` 可用 → 走**该路**把持度；
        # 否则回落全国口径（对无 route 调用方零影响）。
        _rm = route_decree_mult(state, route) if route else None
        base_clerk = _rm if _rm is not None else decree_execution_mult(state)
        if base_clerk is not None:
            # 🔴 **`clerks_mult` = 吏胥折扣本体**（口径不变，既有单点用例锁定）。
            # 2026-10-17 修复：上一版把「知州遵从度」乘进 clerks_mult，把这条读数的
            # 语义从"吏胥折扣"改成了"吏胥折扣×遵从度"，撞掉既有验收
            # （test_finance_reform_p4::test_route_grip_discount_and_scope 期望 0.79 实得 0.8295）。
            # 现改为：**读数保持纯净**，遵从度作为**合成层**的吏治输入（见下方 base 计算）。
            clerks_mult = round(_clamp(_num(base_clerk, 1.0), 0.0, 1.0), 4)
            clerks_scope = f"按路（{route}）" if route else "全国"
        else:
            clerks_mult = None
    except Exception as e:  # noqa: BLE001
        log.warning("decree_effect 取吏治折扣失败：%s", e)

    # 天道遵从度（吏治通道**内部**的输入；只在合成层生效，不改 clerks_mult 读数）
    if clerks_mult is not None and route:
        try:
            from core.ai.tiandao_facade import TianDaoFacade
            pdata = (getattr(state, "prefectures", {}) or {}).get(route, {})
            from core.domains.administration.circuit_officials import get_circuit_officials
            c_info = get_circuit_officials(state, route)
            pref_official = c_info.get("officials", {}).get("prefect", {})
            compliance_ctx = {
                "route": route,
                "gov": pref_official,
                "unrest": (pdata.get("unrest") if isinstance(pdata, dict) else None),
                "treasury": (pdata.get("local_treasury") if isinstance(pdata, dict) else None),
                "org_hint": org_hint,
            }
            comp = TianDaoFacade.circuit_decree_compliance(compliance_ctx)
            clerks_compliance = comp if comp.get("defined") else None

            # 2026-10-17 祖宗家法知通互掣：凡兵民钱谷文书非通判连署不得施行
            # 口径规范（B-3 审计整改）：
            # 连署因子 cs_factor = 0.35 + 0.65 * 连署率 ∈ [0.35, 1.00] 作为二级乘数调节遵从度。
            # 缺失值处理：显式判定 is True；若 countersigned 为 None，防御性回落为 True。
            try:
                from core.domains.administration.prefect_officials import get_prefect_officials
                po_dict = get_prefect_officials(state)
                route_seats = [v for v in po_dict.values() if v.get("circuit") == route] if isinstance(po_dict, dict) else []
                if route_seats:
                    signed_count = sum(1 for s in route_seats if (s.get("countersigned") if s.get("countersigned") is not None else True))
                    signed_ratio = signed_count / len(route_seats)
                    cs_factor = 0.35 + 0.65 * signed_ratio
                    if clerks_compliance and "mult" in clerks_compliance:
                        clerks_compliance["mult"] = round(float(clerks_compliance["mult"]) * cs_factor, 4)
                        clerks_compliance["countersign_ratio"] = round(signed_ratio, 2)
            except Exception as _e_cs:
                log.debug("decree_effect 知通连署率提取跳过：%s", _e_cs)
        except Exception as e:  # noqa: BLE001
            log.debug("decree_effect 计算天道路级遵从度失败（本通道未计入）：%s", e)
            clerks_compliance = None

    applies = (kind == "军政") or bool(enforce_troops)
    if kind == "军政":
        reason = "军政/边事类诏令（军队天然参与）"
    elif enforce_troops:
        reason = "民政诏令，本回合调兵强制施行（军队加成参与）"
    else:
        reason = "民政诏令，未调兵（军队不参与）"
    # 若玩家既未调兵、非军政类，也主动传了强制意图之外的 route → 仍按未参与处理
    military: Dict[str, Any] = {"applies": applies, "enforced": bool(enforce_troops),
                                "mult": None, "reason": reason}
    army_mult = None
    if applies:
        try:
            from core.domains.military.army_models import military_channels
            row = military_channels(state, route) if route else military_channels(state)
            if row:
                # **统一钳位**（2026-09-19 测试项审查）：显示值与公式值必须同源，
                # 否则面板可能显示 ×1.4 而结算按 ×1.0 截断，玩家对不上账。
                army_mult = _clamp(_num(row.get("enforcement_mult"), 1.0), 0.0, 1.0)
                military.update({"mult": round(army_mult, 4), "morale": row.get("morale"),
                                 "arrears": row.get("arrears"), "route": route})
        except Exception as e:  # noqa: BLE001
            log.debug("decree_effect 取军政读数失败：%s", e)
        if army_mult is None:
            # 军队参与但无驻军读数 → 通道缺失（**不**回落 1.0 假装无事），面板显示"未定义"
            military["reason"] = reason + "；但无驻军读数（未计入）"

    civil = _civil_mult(state, route)
    lit_read = _literacy_channel(state, route)     # 审查 S2：不再伪造，缺失即 None
    # **缺失 ≠ 完美**（2026-09-19 报告评审修正）：吏治折扣取不到时不得回落 1.0
    # （那等于默认"吏治完美"，与用户口径"缺失值禁止回落 0/1.0 假装无事"冲突）。
    # 此时 `defined=False` 且 `effect_mult=None`，由调用方决定是否按"无折扣"结算**并留痕**。
    defined = clerks_mult is not None
    compliance_mult: Optional[float] = None
    if clerks_compliance is not None:
        compliance_mult = _clamp(_num(clerks_compliance.get("mult"), 1.0), 0.0, 2.0)
    if not defined:
        base = None
        mult = None
    else:
        # 吏治**通道**（唯一强关联）＝ 吏胥折扣 × 知州遵从度；再乘弱关联（民心/识字率）
        base = _num(clerks_mult, 1.0) * _num(civil, 1.0)
        if compliance_mult is not None:
            base = base * compliance_mult
        mult = base
        if military["applies"] and army_mult is not None:
            # **加成**（非折扣）：军队把"因吏治/民心而办不到的那部分"向上补——
            # 军心可靠（army_mult 高）补得越多，最多补 ARMY_ENFORCE_BONUS（30%）的缺口。
            # 故"调兵强制施行"必然不差于不调兵（用户口径：军队是可选杠杆，不是负担）。
            mult = base + (1.0 - _clamp(base, 0.0, 1.0)) * ARMY_ENFORCE_BONUS * _clamp(army_mult, 0.0, 1.0)
    return {
        "strong": STRONG_CHANNEL,
        "defined": defined,
        "kind": kind,
        "clerks_mult": clerks_mult,
        # 🔴 `clerks_mult` 是**吏胥折扣本体**（不含遵从度）；遵从度单列，供面板/诊断分开看
        "clerks_compliance": clerks_compliance,
        # Q12（V1.3 §7）：吏治折扣口径——"全国"或"按路（<路名>）"
        "clerks_scope": clerks_scope,
        "clerks": {"grievance": clerks_view.get("grievance"),
                   "grip": clerks_view.get("grip"),
                   "quality": clerks_view.get("quality")},
        "official_support": _official_support_proxy(state),
        "civil_mult": civil,
        # 审查 S2：识字率维度是否**有读数**（False = 未定义，面板应显示"未定义"而非伪造值）
        "literacy_defined": lit_read is not None,
        "literacy": _literacy_of(state, route),
        "military": military,
        "effect_mult": None if mult is None else round(_clamp(mult, 0.0, 2.0), 4),
        "note": _note(kind, clerks_mult, civil, military, army_mult, route, clerks_compliance),
    }


def _literacy_of(state, route: Optional[str]):
    """该路（或全国）识字率读数（只读；**缺失或非有限为 None**，不伪造、不回落 0）。"""
    from core.foundation.common.numeric import finite_or_undefined as _fu
    if route:
        p = (getattr(state, "prefectures", None) or {}).get(route)
        if isinstance(p, dict) and p.get("literacy") is not None:
            v = _fu(p.get("literacy"))
            return None if v is None else round(v, 2)
    v = _fu(getattr(state, "literacy", None))
    return None if v is None else round(v, 2)


def _note(kind: str, clerks_mult, civil, military, army_mult, route,
          clerks_compliance=None) -> str:
    """人类可读一行（面板与 AI 权衡共用；**不掺入任何未定义的数**）。"""
    bits = []
    if clerks_mult is not None:
        bits.append(f"吏治（强）折扣 ×{clerks_mult:.2f}")
    if clerks_compliance is not None:
        bits.append(f"知州遵从（{clerks_compliance.get('verdict')}）×{clerks_compliance.get('mult'):.2f}")
    if civil is not None:
        bits.append(f"民心/识字率（弱）×{civil:.2f}")
    if not military.get("applies"):
        bits.append("军队不参与（民政诏令，未调兵）")
    elif army_mult is not None:
        where = f"{route}" if route else "全国"
        tag = "军政类" if kind == "军政" else "调兵强制"
        bits.append(f"军队督行（{tag}，{where}）×{army_mult:.2f}")
    else:
        bits.append("军队督行：无驻军读数（未计入）")
    return "；".join(bits)


def decree_effect_mult(state, *, org_hint: Optional[str] = None, text: str = "",
                       route: Optional[str] = None, kind: Optional[str] = None,
                       enforce_troops: bool = False) -> Optional[float]:
    """诏令实际效果系数（单点；结算与局势推进均调用本函数）。

    **返回 `None` 表示"吏治读数缺失、无法定义"**（不回落 1.0 假装完美）；
    调用方须显式决定是否按"无折扣"处理，并留下可诊断记录。
    """
    return effect_channels(state, org_hint=org_hint, text=text, route=route,
                           kind=kind, enforce_troops=enforce_troops)["effect_mult"]
