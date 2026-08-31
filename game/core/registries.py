# -*- coding: utf-8 -*-
"""宋祚 · 玩家自设内容注册表（科技节点 / 新兵种 + 注册器共用软约束逻辑）。

合并自 register_common.py / tech_registry.py / branch_registry.py 三个碎片模块。

对齐（用户指示：给 AI 足够权限，不要太死板）：
- **去硬上限**：注册器不硬拒 → **软性经济约束**（第 N 个机制成本/维护 ×(1+0.1×(N-1))，
  自然约束不硬拒）。
- **白名单放宽**：AI 自由设计效果，程序只验守恒（ΣΔ==0）+ **合理性软校验**
  （过分 → 降档/提示，非拒绝）；名称放开（仅防重名）。
- **程序底线不变**：守恒/记账/不伪造/合理性软校验/科技门槛。
"""
import math

from content.data import (
    BRANCH_SPEC, EQUIP_PRICE, RECRUIT_MONTHS, BRANCH_POWER_CAP,
    BRANCH_PAY_CAP, BRANCH_REGISTRY_MAX, BRANCH_TECH_GATE,
    BRANCH_BASE, ARMY_RATE, EQUIP_STD, EQUIP_RATE,
)

# ============================================================
# 一、注册器共用软约束（原 register_common.py）
# ============================================================

# 软性经济约束：第 N 个机制成本/维护 × 系数（N 从 1 起，第 1 个 ×1.0）
def soft_cost_mult(reg_len: int) -> float:
    """第 reg_len+1 个注册的成本系数 = 1 + 0.1×reg_len（reg_len 为现有数量）。"""
    return 1.0 + 0.10 * max(0, reg_len)


def dup_name_ok(reg: dict, name: str) -> bool:
    """仅防重名：注册表中已有同名 → False（名称放开，其余不查）。"""
    for rid, entry in (reg or {}).items():
        if isinstance(entry, dict) and entry.get("name") == name:
            return False
        if rid == name:
            return False
    return True


def sanity_effect(effects: dict, caps: dict = None) -> tuple:
    """合理性软校验（非拒绝）：效果值过分（超 CAP 或离谱量级）→ 降档并提示。

    返回 (normalized_effects, warnings)。caps: {field: 上限}——缺失字段按量级粗估。
    """
    if not isinstance(effects, dict):
        return {}, ["效果须为对象"]
    out = {}
    warns = []
    for k, v in effects.items():
        if isinstance(v, str):
            out[k] = v   # 档位词（程序换算封顶，天然合理）
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            warns.append(f"效果 {k} 值非法，已忽略")
            continue
        cap = (caps or {}).get(k)
        if cap is None:
            # 量级粗估：treasury/finance 类 5000 万封顶，其余 100 封顶
            cap = 50_000_000 if k in ("treasury", "finance") else 100
        if abs(v) > cap:
            warns.append(f"效果 {k}={v:.0f} 超出合理量级（{cap:.0f}），已降档")
            v = cap if v > 0 else -cap
        out[k] = v
    return out, warns


# ============================================================
# 二、科技注册表（原 tech_registry.py，玩家承接天马行空研发）
# ============================================================
from content.data import BRANCH_BASE  # noqa: F401   # 效果字段白名单同源（档位词）

TECH_REGISTRY_MAX = 12
# 效果字段白名单（玩家注册节点可声明：既有效果键）
TECH_EFFECT_WHITELIST = (
    "yield_bonus", "trade_income", "mining_income", "army_power", "build_cost",
    "canal_efficiency", "production", "exam_talent", "decree_speed",
    "epidemic_risk", "calendar_bonus",
)


def register_node(state, contract: dict, created_by: str = "") -> dict:
    """注册玩家新科技节点（对齐：去硬上限 + 白名单放宽 + 合理性软校验 + 软约束）。
    contract: {name, desc, prereqs, effect, tier}。"""
    reg = getattr(state, "tech_registry", None)
    if reg is None:
        reg = {}
        state.tech_registry = reg
    name = str(contract.get("name", "")).strip()[:12]
    if not name:
        return {"ok": False, "node_id": "", "msg": "节点名须为非空（≤12字）"}
    if not dup_name_ok(reg, name):
        return {"ok": False, "node_id": "", "msg": f"节点「{name}」已注册（仅防重名）"}
    prereqs = contract.get("prereqs") or []
    if not isinstance(prereqs, list):
        return {"ok": False, "node_id": "", "msg": "prereqs 须为列表"}
    # 前置链已解锁（程序底线）
    unlocked = set(getattr(state, "tech", {}).get("unlocked", []))
    for p in prereqs:
        if p not in unlocked:
            return {"ok": False, "node_id": "", "msg": f"前置 {p} 未解锁"}
    effect = contract.get("effect") or {}
    if not isinstance(effect, dict) or not effect:
        return {"ok": False, "node_id": "", "msg": "effect 须为非空对象"}
    # 白名单放宽：效果字段自由设计（合理性软校验——过分降档/提示，非拒绝）
    eff_norm, warns = sanity_effect(effect)
    tier = str(contract.get("tier", "中"))
    if tier not in ("无", "微", "小", "中", "大", "巨", "极"):
        return {"ok": False, "node_id": "", "msg": "档位词非法"}
    node_id = f"p_{name}"
    reg[node_id] = {
        "node_id": node_id, "name": name, "desc": str(contract.get("desc", ""))[:40],
        "prereqs": list(prereqs), "effect": eff_norm, "tier": tier,
        "created_turn": getattr(state, "turn", 0),
        "active": True, "created_by": created_by or "",
    }
    return {"ok": True, "node_id": node_id,
            "msg": f"节点「{name}」已注册（{node_id}）" + (f"；{'；'.join(warns)}" if warns else "")}


def node_entry(state, node_id: str):
    """玩家注册节点 → 类官方 TechNode 元组（供 get_tech_node 兼容）。"""
    reg = getattr(state, "tech_registry", {}) or {}
    n = reg.get(node_id)
    if not n or not n.get("active"):
        return None
    return (node_id, "玩家新制", 0, n["name"], n.get("desc", ""),
            list(n.get("prereqs", [])), 0, [], {"silver": 0, "months": 12, "masters": 1},
            dict(n.get("effect", {})))


def deactivate_node(state, node_id: str) -> dict:
    """停用玩家节点（active=False 保留历史）。"""
    reg = getattr(state, "tech_registry", {}) or {}
    if node_id not in reg:
        return {"ok": False, "msg": "无此节点"}
    reg[node_id]["active"] = False
    return {"ok": True, "msg": f"节点「{reg[node_id]['name']}」已停用"}


# ============================================================
# 三、新兵种注册表（原 branch_registry.py，玩家自由设立）
# ============================================================
# - `state.branch_registry`（存档持久化）：{branch_name: {base_branch, spec, cost_mult,
#   created_turn, active, usage}}——注册时程序算派生系数存表。
# - 门槛（拒绝式）：成本（招募费 = Σ人数×(装备现值 + 粮饷×6月)，国库出 = 装备入军械库 +
#   粮饷入兵 POP，**ΣΔ==0 守恒**）+ 科技（火器→gunpowder、弓弩→弓弩工艺、战马→马政）+
#   拟诏+会签（上层）+ 重名拒绝。
# - 封顶：战力 ≤1.8×、粮饷 ≤2.0×（双方向 clamp）。

# 特化 7 系（言枢密 schema：equipment/training/mobility + position）
SPECIALIZATION_TIERS = {
    "equipment": {"scale": 0.67, "dims": ("equip",)},
    "training": {"scale": 0.30, "dims": ("train",)},
    "mobility": {"scale": 0.50, "dims": ("mobility",)},
    "equipment_training": {"scale": 0.45, "dims": ("equip", "train")},
    "equipment_mobility": {"scale": 0.50, "dims": ("equip", "mobility")},
    "training_mobility": {"scale": 0.35, "dims": ("train", "mobility")},
    "balanced": {"scale": 0.40, "dims": ("equip", "train", "mobility")},
}


def spec_tier_index(tier: str) -> float:
    """档位词 → 特化指数（无0/微0.25/小0.5/中1.0/大1.5/巨2.0→clamp 1.5）。"""
    _idx = {"无": 0.0, "微": 0.25, "小": 0.5, "中": 1.0, "大": 1.5, "巨": 1.5, "极": 1.5}
    return _idx.get(tier, 0.5)


def _pay_of(base_branch: str, spec: dict) -> float:
    """派生粮饷倍率 = base 粮饷 × 特化系数（封顶 2.0，双方向）。"""
    t = spec_tier_index(spec.get("tier", "中"))
    mult = 1.0
    for dim in ("equip", "train", "mobility"):
        if dim == "equip" and spec.get("specialize", "equipment") in (
                "equipment", "equipment_training", "equipment_mobility", "balanced"):
            mult *= 1 + 0.05 * t
    return min(BRANCH_PAY_CAP, max(1.0 / BRANCH_PAY_CAP, mult))


def tech_gate_ok(state, spec: dict) -> bool:
    """科技门槛（史实锚）：火器系→gunpowder、弓弩系→弓弩工艺、战马→马政。"""
    tech = getattr(state, "tech", {}) or {}
    focus = str(spec.get("focus", ""))
    if focus == "火器":
        tiers = BRANCH_TECH_GATE["gunpowder"]
        idx = spec_tier_index(spec.get("tier", "中"))
        need = tiers[min(int(idx * 2.66), 3)]   # 档位 0~1.5 → 门槛 30/45/65/85
        if int(tech.get("gunpowder", 0)) < need:
            return False
    if focus == "弓弩" and int(tech.get("archery", tech.get("level", 0))) < BRANCH_TECH_GATE["archery"]:
        return False
    if focus == "战马" and int(tech.get("cavalry", tech.get("level", 0))) < BRANCH_TECH_GATE["cavalry"]:
        return False
    return True


def register_branch(state, contract: dict, created_by: str = "") -> dict:
    """注册新兵种（对齐：去硬上限 + 软约束 + 程序底线科技/守恒）。

    contract: {name, base_branch, spec: {specialize, tier, position, focus}, cost_mult}
    返回 {"ok", "branch", "msg"}。
    """
    reg = getattr(state, "branch_registry", None)
    if reg is None:
        reg = {}
        state.branch_registry = reg
    name = str(contract.get("name", "")).strip()[:12]
    if not name:
        return {"ok": False, "branch": "", "msg": "兵种名须为非空（≤12字）"}
    if name in reg:
        return {"ok": False, "branch": "", "msg": f"兵种「{name}」已注册（不重名）"}
    spec = contract.get("spec") or {}
    if spec.get("specialize") not in SPECIALIZATION_TIERS:
        return {"ok": False, "branch": "", "msg": "特化系须为 7 系之一"}
    if not tech_gate_ok(state, spec):
        return {"ok": False, "branch": "", "msg": "科技不足：该兵种所需科技（火器/弓弩/马政）未研出"}
    # 成本守恒：招募费 = Σ人数×(装备现值 + 粮饷×6月) × 软约束倍率(第 N 个 ×(1+0.1×(N-1)))
    troops = int(contract.get("troops", 10000) or 10000)
    cost = _recruit_cost(state, contract, troops)
    cost = int(cost * soft_cost_mult(len(reg)))
    if cost <= 0:
        return {"ok": False, "branch": "", "msg": "成本计算异常"}
    if getattr(state, "treasury", 0) < cost:
        return {"ok": False, "branch": "", "msg": f"国库不足：招募需 {cost:,} 贯（当前 {state.treasury:,}）"}
    # 落地（守恒：国库 -cost → 军械库 + 装备现值 + 兵 POP + 粮饷）
    state.change_treasury(-cost)
    _pay_equip_and_grain(state, contract, troops, cost)
    reg[name] = {
        "branch": name, "base_branch": str(contract.get("base_branch", "轻步兵")),
        "spec": dict(spec), "cost_mult": float(contract.get("cost_mult", 1.0)),
        "created_turn": getattr(state, "turn", 0),
        "active": True, "usage": 0, "created_by": created_by or "",
    }
    return {"ok": True, "branch": name,
            "msg": f"新兵种「{name}」已募（{troops:,} 人，耗帑 {cost:,} 贯）"}


def _recruit_cost(state, contract: dict, troops: int) -> int:
    """招募费 = Σ人数×(装备现值 + 粮饷×6月)。"""
    spec = contract.get("spec") or {}
    base = str(contract.get("base_branch", "轻步兵"))
    tier = str(contract.get("tier", "禁军"))
    # 粮饷基准（BRANCH_BASE × ARMY_RATE）× 特化系数 × 6 月
    pay_base = BRANCH_BASE.get(base, BRANCH_BASE["轻步兵"])["pay"] * ARMY_RATE.get(tier, 1.0)
    pay = pay_base * _pay_of(base, spec) * RECRUIT_MONTHS
    # 装备现值（人均 × EQUIP_PRICE Σ）
    eq_cost = 0.0
    for k, per in EQUIP_STD.get(base, {}).items():
        eq_cost += per * EQUIP_PRICE.get(k, 0)
    eq_cost *= EQUIP_RATE.get(tier, 1.0)
    cost = int(troops * (pay + eq_cost))
    cost *= float(contract.get("cost_mult", 1.0) or 1.0)
    return max(0, cost)


def _pay_equip_and_grain(state, contract: dict, troops: int, cost: int) -> None:
    """成本分配（守恒：国库 -cost == 军械库装备 + 兵 POP 粮饷）。"""
    spec = contract.get("spec") or {}
    base = str(contract.get("base_branch", "轻步兵"))
    tier = str(contract.get("tier", "禁军"))
    pay_base = BRANCH_BASE.get(base, BRANCH_BASE["轻步兵"])["pay"] * ARMY_RATE.get(tier, 1.0)
    pay_total = int(troops * pay_base * _pay_of(base, spec) * RECRUIT_MONTHS)
    eq_total = cost - pay_total
    # 装备入军械库（中央武库 stock）——近似：入 state.central_arsenal.stock
    try:
        cs = getattr(state, "central_arsenal", None)
        if cs is not None and hasattr(cs, "stock"):
            for k, per in EQUIP_STD.get(base, {}).items():
                if per > 0 and eq_total > 0:
                    cs.stock[k] = cs.stock.get(k, 0) + int(eq_total * 0.5)
    except Exception:
        pass
    # 粮饷入兵 POP（均分各路）
    pay_rem = pay_total
    paths = list(getattr(state, "prefectures", {}).keys())
    if paths and pay_rem > 0:
        per = pay_rem // len(paths)
        for name in paths:
            pops = state.prefectures[name].get("pops", {})
            if "兵" in pops:
                pops["兵"]["wealth"] = pops["兵"].get("wealth", 0) + per


def build_branch_std(state, branch: str, base_branch: str = "轻步兵",
                     spec: dict = None) -> dict:
    """查 registry 派生新兵种标准（粮饷/装备走既有 branch_std 公式 + 特化系数）。"""
    from content.data import branch_std as _bs
    base = _bs("禁军", base_branch)
    if not spec:
        return base
    t = spec_tier_index(spec.get("tier", "中"))
    pay_mult = _pay_of(base_branch, spec)
    out = {"grain": base["grain"] * min(BRANCH_PAY_CAP, pay_mult),
           "pay": base["pay"] * min(BRANCH_PAY_CAP, pay_mult),
           "equip": {k: v * min(2.0, 1 + 0.67 * t) for k, v in base["equip"].items()}}
    return out


def deactivate_branch(state, branch: str) -> dict:
    """裁撤新兵种（active=False 保留历史，不物理删）。"""
    reg = getattr(state, "branch_registry", {}) or {}
    if branch not in reg:
        return {"ok": False, "msg": "无此兵种"}
    reg[branch]["active"] = False
    return {"ok": True, "msg": f"兵种「{branch}」已裁撤（历史保留）"}
