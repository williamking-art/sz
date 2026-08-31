# -*- coding: utf-8 -*-
"""宋祚 · 大臣自设工具注册表（register_item 泛化，tool_registry 模式）。

对齐（用户指示：给 AI 足够权限，不要太死板）：
- **去硬上限**：原 TOOL_REGISTRY_MAX=16 移除 → 软性经济约束（第 N 个工具成本 ×(1+0.1×(N-1))）；
- **白名单放宽**：名称放开（仅防重名）；效果字段自由设计（程序只验守恒 + 合理性软校验，
  过分 → 降档/提示，非拒绝）；
- **程序底线不变**：成本 ≤ 存量、AI 无直写权（数值经换算封顶）、守恒/记账/不伪造。
- 执行：走 _tool_dispatch 式程序映射（effect_template → free_effect 契约落地）。
"""
from content.data import FREE_EFFECT_CAP
from core.registries import soft_cost_mult, dup_name_ok, sanity_effect

# 参数 schema 键白名单（工具参数只能声明这些——参数约束保留，非效果）
PARAM_KEYS = ("scope", "region", "rate", "months", "amount", "target")


def _tier_delta(value) -> bool:
    """delta 合法：档位词（可带+/-）或数值。"""
    if isinstance(value, str):
        return bool(value.lstrip("+-").strip())
    return isinstance(value, (int, float))


def register_tool(state, tool: dict, created_by: str = "") -> dict:
    """注册大臣自设工具（去硬上限 + 白名单放宽 + 软约束 + 合理性）。返回 {ok, tool_id, msg, warnings}。"""
    reg = getattr(state, "tool_registry", None)
    if reg is None:
        reg = {}
        state.tool_registry = reg
    name = str(tool.get("name", "")).strip()[:12]
    if not name:
        return {"ok": False, "tool_id": "", "msg": "工具名须为非空（≤12字）"}
    if not dup_name_ok(reg, name):
        return {"ok": False, "tool_id": "", "msg": f"工具「{name}」已注册（仅防重名）"}
    params = tool.get("parameters") or {}
    if not isinstance(params, dict):
        return {"ok": False, "tool_id": "", "msg": "parameters 须为对象"}
    for k in params:
        if k not in PARAM_KEYS:
            return {"ok": False, "tool_id": "", "msg": f"参数键「{k}」不在白名单（scope/region/rate/months/amount/target）"}
    eff = tool.get("effect_template") or {}
    if not isinstance(eff, dict) or not eff:
        return {"ok": False, "tool_id": "", "msg": "effect_template 须为非空对象"}
    # 白名单放宽：效果字段自由设计，只验类型 + 合理性（过分 → 降档/提示，非拒绝）
    for f, v in eff.items():
        if not _tier_delta(v):
            return {"ok": False, "tool_id": "", "msg": f"效果「{f}」须为档位词或数值"}
    eff_norm, warns = sanity_effect(eff, caps=FREE_EFFECT_CAP)
    # 软性经济约束：第 N 个工具成本 ×(1+0.1×(N-1))
    mult = soft_cost_mult(len(reg))
    cost = tool.get("cost") or {}
    if isinstance(cost, dict):
        cost = {k: int(float(v) * mult) for k, v in cost.items() if v}
        if cost.get("treasury", 0) > int(getattr(state, "treasury", 0)):
            return {"ok": False, "tool_id": "", "msg": "工具成本（含软约束倍率）超出当前国库"}
        if cost.get("granary", 0) > int(getattr(state, "granary", 0)):
            return {"ok": False, "tool_id": "", "msg": "工具成本（含软约束倍率）超出当前太仓"}
    # 注册
    tool_id = f"t{len(reg) + 1:02d}_{name}"
    reg[tool_id] = {
        "tool_id": tool_id, "name": name,
        "parameters": dict(params),
        "effect_template": eff_norm,
        "cost": dict(cost) if isinstance(cost, dict) else {},
        "cost": dict(cost) if isinstance(cost, dict) else {},
        "created_by": created_by or "",
        "usage": 0, "active": True,
    }
    return {"ok": True, "tool_id": tool_id, "msg": f"工具「{name}」已登记（{tool_id}）"}


def deactivate_tool(state, tool_id: str) -> dict:
    """注销工具（active=False 不物理删除）。"""
    reg = getattr(state, "tool_registry", {}) or {}
    if tool_id not in reg:
        return {"ok": False, "msg": "无此工具"}
    reg[tool_id]["active"] = False
    return {"ok": True, "msg": f"工具 {tool_id} 已停用"}


def execute_tool(state, tool_id: str, args: dict) -> list:
    """执行自设工具：effect_template + 参数 → free_effect 契约落地（拒绝式护栏复用）。

    AI 无直写权：数值经档位词/数值 → _apply_free_effect 白名单/CAP/cost 换算封顶。
    """
    reg = getattr(state, "tool_registry", {}) or {}
    t = reg.get(tool_id)
    if not t or not t.get("active"):
        return ["[工具] 未注册或已停用"]
    from core.free_effect import _apply_free_effect
    eff = dict(t.get("effect_template", {}))
    # 参数代入：rate/amount 等可作 cost 或档位占位（简化：直接取 template + cost）
    contract = {"mode": "once", "effects": eff, "cost": dict(t.get("cost") or {})}
    t["usage"] = t.get("usage", 0) + 1
    return _apply_free_effect(state, contract)
