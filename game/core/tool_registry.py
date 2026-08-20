# -*- coding: utf-8 -*-
"""宋祚 · 大臣自设工具注册表（三方案落地：工具注册护栏）。

- `state.tool_registry`（存档持久化）：{tool_id: {name, parameters, effect_template,
  created_by, usage, active}}。
- 注册护栏（拒绝式）：
  * 名称白名单（TOOL_NAME_WHITELIST，史实工具名）；
  * parameters schema 限制（键白名单 + 值类型）；
  * effect_template 护栏：field ∈ FREE_EFFECT_FIELD_WHITELIST、delta 档位词或 CAP 内、
    cost ≤ 存量、**AI 无直写权**（数值经 tier_to_value 换算封顶）；
  * 注册上限 16；复用/注销（active=False 不物理删）。
- 执行：走 _tool_dispatch 式程序映射（effect_template → free_effect 契约落地，
  经 core.free_effect._apply_free_effect 白名单/CAP/cost 拒绝式）。
"""
from content.data import FREE_EFFECT_FIELD_WHITELIST

TOOL_REGISTRY_MAX = 16

# 工具名白名单（史实/制度名，供 AI 提议取名）
TOOL_NAME_WHITELIST = (
    "保甲", "市易", "均输", "青苗", "免役", "方田", "水利", "漕运",
    "榷茶", "榷盐", "铸钱", "义仓", "常平", "贡院", "军器监", "牧监",
)

# 参数 schema 键白名单（工具参数只能声明这些）
PARAM_KEYS = ("scope", "region", "rate", "months", "amount", "target")

_EFFECT_WHITELIST = FREE_EFFECT_FIELD_WHITELIST


def _tier_delta(value) -> bool:
    """delta 合法：档位词（可带+/-）或数值在 CAP 内（数值封顶由 free_effect 换算，这里只判类型）。"""
    if isinstance(value, str):
        return value.lstrip("+-") in ("无", "微", "小", "中", "大")
    return isinstance(value, (int, float))


def register_tool(state, tool: dict, created_by: str = "") -> dict:
    """注册大臣自设工具（拒绝式护栏）。返回 {"ok": bool, "tool_id": str, "msg": str}。"""
    reg = getattr(state, "tool_registry", None)
    if reg is None:
        reg = {}
        state.tool_registry = reg
    if len(reg) >= TOOL_REGISTRY_MAX:
        return {"ok": False, "tool_id": "", "msg": f"工具注册已达上限 {TOOL_REGISTRY_MAX}"}
    name = str(tool.get("name", ""))
    if name not in TOOL_NAME_WHITELIST:
        return {"ok": False, "tool_id": "", "msg": f"工具名「{name}」不在白名单（保甲/市易/均输/青苗/免役/方田/水利/漕运/榷茶/榷盐/铸钱/义仓/常平/贡院/军器监/牧监）"}
    params = tool.get("parameters") or {}
    if not isinstance(params, dict):
        return {"ok": False, "tool_id": "", "msg": "parameters 须为对象"}
    for k in params:
        if k not in PARAM_KEYS:
            return {"ok": False, "tool_id": "", "msg": f"参数键「{k}」不在白名单（scope/region/rate/months/amount/target）"}
    eff = tool.get("effect_template") or {}
    if not isinstance(eff, dict) or not eff:
        return {"ok": False, "tool_id": "", "msg": "effect_template 须为非空对象"}
    for f, v in eff.items():
        if f not in _EFFECT_WHITELIST:
            return {"ok": False, "tool_id": "", "msg": f"效果字段「{f}」不在 free_effect 白名单"}
        if not _tier_delta(v):
            return {"ok": False, "tool_id": "", "msg": f"效果「{f}」须为档位词或数值（CAP 封顶）"}
    # cost 护栏：≤ 当前存量
    cost = tool.get("cost") or {}
    if isinstance(cost, dict):
        if cost.get("treasury") and int(cost["treasury"]) > int(getattr(state, "treasury", 0)):
            return {"ok": False, "tool_id": "", "msg": "工具成本超出当前国库"}
        if cost.get("granary") and int(cost["granary"]) > int(getattr(state, "granary", 0)):
            return {"ok": False, "tool_id": "", "msg": "工具成本超出当前太仓"}
    # 注册
    tool_id = f"t{len(reg) + 1:02d}_{name}"
    reg[tool_id] = {
        "tool_id": tool_id, "name": name,
        "parameters": dict(params),
        "effect_template": {k: v for k, v in eff.items()},
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
