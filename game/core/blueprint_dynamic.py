# -*- coding: utf-8 -*-
"""圣旨行动闭环 · **动态蓝图**（规格 `specs/decree-action-chain` 任务 3）。

定位：
  · AI/玩家可以提出**新蓝图**（如「修两浙海塘」），但只能是**声明式数据**，
    **绝不接受可执行代码、表达式、字段路径**（规格非目标第 1/2 条）。
  · 蓝图的效果只能引用 `core.decree_plan.EFFECT_OPERATORS` 里**已注册的构件**；
    内建构件一律映射到 `_settle_projects` 完工段**已存在**的 output 键，
    **不新增结算分支、不另起通道**（口径单点）。
  · 注册后进 `state.dynamic_blueprints`（随存档持久化），`construction.resolve_blueprint`
    会优先查它，于是动态蓝图与静态蓝图走**同一套** `can_build` / `propose_project` /
    五态状态机 / 完工落成路径。
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple

from content.data import BUILDING_COST_GROWTH
from core.decree_plan import (
    BUILTIN_OPERATORS, EFFECT_OPERATORS, _ensure_builtin_operators,
)

__all__ = [
    "DYNAMIC_BLUEPRINT_SCHEMA_VERSION", "DYNAMIC_CATEGORIES", "MAX_DYNAMIC_BLUEPRINTS",
    "validate_dynamic_blueprint", "blueprint_key", "register_dynamic_blueprint",
    "resolve_dynamic_blueprint", "dynamic_blueprint_output", "dynamic_blueprint_runtime",
    "dynamic_blueprint_cost",
]

# 动态蓝图 schema 版本（与行动计划分开演进；读档据此迁移，见规格任务 7）
DYNAMIC_BLUEPRINT_SCHEMA_VERSION = 1

# 上位分类白名单（与 `BUILDING_BLUEPRINTS` 的 category 取值一致）
DYNAMIC_CATEGORIES: Tuple[str, ...] = ("财政", "军事", "民生", "科技", "交通", "内廷")

# 单个存档内动态蓝图数量上限（防 AI 无限注册撑爆存档）
MAX_DYNAMIC_BLUEPRINTS = 60

# 工期/造价硬边界（复用静态蓝图的工期档：1–6 月）
_MONTHS_MIN, _MONTHS_MAX = 1, 6
_COST_MAX = 50_000_000


def _clean_int(v: Any, lo: int, hi: int) -> Optional[int]:
    """取整；**越界/非数值/非有限 → None（拒绝，不夹取）**。

    ⚠️ 刻意**不夹取**：把 −1 悄悄夹成 0、把 99 月悄悄夹成 6 月，都是"静默改写"，
    违反拒绝式与硬约束 #3（缺失 ≠ 0 ≠ 1.0）。范围错误应由调用方**明确拒绝**。
    """
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    if not math.isfinite(f):
        return None
    i = int(f)
    if i < lo or i > hi:
        return None
    return i


def validate_dynamic_blueprint(bp: Any) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """校验并归一化一份**动态蓝图**；返回 `(净蓝图 | None, 错误列表)`。

    拒绝式：任何结构性错误都返回 `(None, errors)`，**不做部分接受**。
    """
    _ensure_builtin_operators()
    errs: List[str] = []
    if not isinstance(bp, dict):
        return None, ["蓝图必须是对象"]

    name = bp.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, ["蓝图缺 name"]
    name = name.strip()[:40]

    # 分类：白名单；给了非法值 → 拒绝（不静默改写）。
    # 但**空字符串／纯空白视为"未给"**：上游（如 `decree_plan.validate_action` 归一化
    # 蓝图提案时）可能补一个空串，若当成非法分类会把"AI 没给分类"的提案整份拒掉，
    # 使旨意永远建不成——这层宽容是**口径**（未给 ≠ 给了非法值），不是放水。
    cat = bp.get("category")
    if cat is not None and str(cat).strip() == "":
        cat = None
    if cat is not None:
        if cat not in DYNAMIC_CATEGORIES:
            return None, [f"分类非法：{cat!r}（允许：{'/'.join(DYNAMIC_CATEGORIES)}）"]

    # 地利前置：路型子串元组/列表；元素必须是字符串
    reg = bp.get("requires_region")
    region: Tuple[str, ...] = ()
    if reg is not None:
        if isinstance(reg, str) or not isinstance(reg, (list, tuple)):
            return None, ["requires_region 必须是字符串数组（空表示处处可建）"]
        for x in reg:
            if not isinstance(x, str) or not x.strip():
                return None, ["requires_region 元素必须是非空字符串"]
        region = tuple(x.strip() for x in reg)

    # 造价与工期
    raw_cost = bp.get("cost")
    if raw_cost is not None and not isinstance(raw_cost, dict):
        return None, ["cost 必须是对象"]
    raw_cost = raw_cost or {}
    # 🔴 `cost.silver` 是**货币银两**，不是物料维「银」——物料维 2026-10-03 归中文后，
    # 此处若跟着写成「银」会把**造价**误当**物料银**，属跨口径串味，必须保持 `silver`。
    silver = _clean_int(raw_cost.get("silver", 0), 0, _COST_MAX)
    if silver is None:
        return None, [f"cost.silver 必须是 0–{_COST_MAX} 的数值（越界不接受，不夹取）"]
    months = _clean_int(raw_cost.get("months", 3), _MONTHS_MIN, _MONTHS_MAX)
    if months is None:
        return None, [f"cost.months 必须是 {_MONTHS_MIN}–{_MONTHS_MAX} 的数值（越界不接受，不夹取）"]

    # 材料：维度 → 数量（非负整数）；不吃未知名（防拼写错误静默通过）
    mats_raw = bp.get("materials")
    materials: Dict[str, int] = {}
    if mats_raw is not None:
        if not isinstance(mats_raw, dict):
            return None, ["materials 必须是对象"]
        try:
            from core.game_state import RESOURCE_DIMS as _DIMS
        except Exception:  # noqa: BLE001
            _DIMS = ()
        for dim, qty in mats_raw.items():
            if _DIMS and dim not in _DIMS:
                return None, [f"materials 含未登记维度：{dim}"]
            q = _clean_int(qty, 0, 10_000_000)
            if q is None:
                return None, [f"materials.{dim} 必须是 0–10,000,000 的数值（越界不接受）"]
            if q > 0:
                materials[dim] = q

    # 维护费：0–1 的比例（月度折旧/维持口径，缺失则用默认）
    maint = bp.get("maintenance")
    maintenance = 0.005
    if maint is not None:
        if isinstance(maint, bool) or not isinstance(maint, (int, float)) \
                or not math.isfinite(float(maint)) or not (0.0 <= float(maint) <= 1.0):
            return None, ["maintenance 必须是 0–1 之间的小数"]
        maintenance = float(maint)

    # 效果构件：必须**逐个**在注册表内；任一未注册 → 整份拒绝
    # （与行动计划不同：蓝图是**要落档的资产**，带半个坏效果入库会更危险）
    eff_raw = bp.get("effects")
    if eff_raw is None:
        eff_raw = []
    if not isinstance(eff_raw, list):
        return None, ["effects 必须是数组"]
    effects: List[Dict[str, Any]] = []
    if not eff_raw:
        errs.append("蓝图未声明任何 effects（可以注册，但完工将无产出）")
    for eff in eff_raw:
        if not isinstance(eff, dict):
            return None, ["effects 元素必须是对象"]
        op = str(eff.get("op") or eff.get("operator") or "").strip()
        if not op:
            return None, ["effects 元素缺 op"]
        spec = EFFECT_OPERATORS.get(op)
        if spec is None:
            return None, [f"未注册的 effects 构件：{op}（动态蓝图不得自带新构件）"]
        params = eff.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return None, [f"effects[{op}] 的 params 必须是对象"]
        # 复用注册表的参数校验（范围/非有限/必填）
        from core.decree_plan import _check_operator
        err = _check_operator(op, params)
        if err:
            return None, [err]
        # 只保留注册表声明的参数键（丢弃多余键，防夹带）
        declared = spec.get("params") or {}
        kept = {k: v for k, v in params.items() if k in declared}
        effects.append({"op": op, "params": kept})

    clean = {
        "schema_version": DYNAMIC_BLUEPRINT_SCHEMA_VERSION,
        "name": name,
        "category": cat or "民生",
        "requires_region": list(region),
        "cost": {"silver": int(silver), "months": int(months)},
        "materials": materials,
        "maintenance": maintenance,
        "effects": effects,
        "_dynamic": True,
    }
    return clean, errs


def blueprint_key(bp: Dict[str, Any]) -> str:
    """动态蓝图的**稳定键**：由名称派生（同一名称重复注册即视为同一蓝图）。"""
    nm = str((bp or {}).get("name") or "").strip()
    return "dyn:" + hashlib.sha1(nm.encode("utf-8")).hexdigest()[:12]


def resolve_dynamic_blueprint(state, name: Optional[str] = None,
                              key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """在**本局存档**的动态蓝图注册表里查找（先按 key，再按中文名）；没有则 None。"""
    reg = getattr(state, "dynamic_blueprints", None)
    if not isinstance(reg, dict) or not reg:
        return None
    k = str(key or "").strip()
    if k and k in reg and isinstance(reg[k], dict):
        out = dict(reg[k])
        out.setdefault("_key", k)
        out.setdefault("_name", out.get("name", k))
        return out
    n = str(name or "").strip()
    if n:
        for k2, bp2 in reg.items():
            if isinstance(bp2, dict) and str(bp2.get("name")) == n:
                out = dict(bp2)
                out.setdefault("_key", k2)
                out.setdefault("_name", n)
                return out
    return None


def register_dynamic_blueprint(state, bp: Any) -> Dict[str, Any]:
    """把一份动态蓝图**注册进存档**（校验 → 落 `state.dynamic_blueprints`）。

    返回 `{"ok", "key"} | {"ok": False, "errors": [...]}`。
    同名重复注册**拒绝式**（不静默覆盖既有蓝图语义）。
    **本函数只注册蓝图，不立项、不动钱粮。**
    """
    clean, errs = validate_dynamic_blueprint(bp)
    if clean is None:
        return {"ok": False, "errors": errs}
    reg = getattr(state, "dynamic_blueprints", None)
    if not isinstance(reg, dict):
        reg = {}
        state.dynamic_blueprints = reg
    if len(reg) >= MAX_DYNAMIC_BLUEPRINTS:
        return {"ok": False, "errors": [f"动态蓝图数已达上限 {MAX_DYNAMIC_BLUEPRINTS}"]}
    key = blueprint_key(clean)
    exist = reg.get(key)
    if isinstance(exist, dict):
        return {"ok": False, "errors": [f"蓝图已注册：{clean['name']}（{key}）"]}
    for k2, bp2 in reg.items():
        if isinstance(bp2, dict) and str(bp2.get("name")) == clean["name"]:
            return {"ok": False, "errors": [f"已有同名蓝图：{clean['name']}"]}
    reg[key] = clean
    return {"ok": True, "key": key, "warnings": errs}


def dynamic_blueprint_output(bp: Dict[str, Any]) -> Dict[str, int]:
    """把动态蓝图的**完工型**（`timing="completion"`）构件翻译成 output 键。

    这是"不新增结算分支"的关键：内建完工构件都带 `output_key`
    （见 `BUILTIN_OPERATORS`），完工段读到这些键即照既有逻辑落地。
    运行型构件（`timing="runtime"`）**不进这里**，由
    `dynamic_blueprint_runtime` 单独产出、按月结算。
    """
    return _translate(bp, want_timing="completion")


def dynamic_blueprint_runtime(bp: Dict[str, Any]) -> Dict[str, int]:
    """把动态蓝图的**运行型**（`timing="runtime"`）构件翻译成 output 键。

    运行型产出在建筑 `operating/degraded` 期间**按月**结算，并按 `capacity` 缩放
    （规格任务 4：运行时按 capacity、维护与折旧执行 operators）。
    """
    return _translate(bp, want_timing="runtime")


def _translate(bp: Dict[str, Any], *, want_timing: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for eff in (bp.get("effects") or []):
        if not isinstance(eff, dict):
            continue
        op = str(eff.get("op") or "")
        spec = EFFECT_OPERATORS.get(op) or BUILTIN_OPERATORS.get(op) or {}
        if str(spec.get("timing") or "completion") != want_timing:
            continue
        okey = spec.get("output_key")
        if not okey:
            continue
        amt = (eff.get("params") or {}).get("amount")
        if isinstance(amt, bool) or not isinstance(amt, (int, float)):
            continue
        if not math.isfinite(float(amt)) or float(amt) <= 0:
            continue
        out[okey] = int(out.get(okey, 0) or 0) + int(amt)
    return out


def dynamic_blueprint_cost(bp: Dict[str, Any], levels: int = 1) -> int:
    """动态蓝图造价（贯）：与静态蓝图**同一口径**（`base_cost` × `BUILDING_COST_GROWTH^(lv-1)`）。

    这里把 `cost.silver` 视为 **base_cost**，从而与 `construction.blueprint_cost` 的
    `base_cost` 分支逐级增长行为一致——避免动态/静态两套造价算法（口径单点）。
    """
    lv = max(1, int(levels or 1))
    base = float(((bp or {}).get("cost") or {}).get("silver", 0) or 0)
    return int(sum(base * (BUILDING_COST_GROWTH ** i) for i in range(lv)))
