# -*- coding: utf-8 -*-
"""宋祚 · 国策树机制（core/focus_mechanic.py）

参考《明末：捞金模拟器》的国策树（focus）：五大分支（政务/军事/科学/内卫/税务），
带权力等级、互斥分支、解锁建筑与长期效果，替代/补充现有零散施政。

与 state.MAJOR_POLICIES / REFORM_TYPES 不同，国策树是「五大分支、权力等级、
互斥、解锁建筑」的全新体系。本模块只做定义 + 结算推进 + 解锁判定，不写状态；
由 settlement.run_monthly_settlement 在 Step 6.9 之后调用。

设计原则：
- 每分支节点带 power_level（权力等级），高等级节点需前置节点已解锁；
- 互斥分支：政务 vs 军事（重文轻武 vs 重武轻文），选择一方则另一方对应节点降权；
- 解锁建筑：节点解锁后写入 state.tech["assets"] 或 state.central_orgs 相关字段；
- 长期效果：节点解锁后月度施加确定性修正（非守恒字段），不破坏经济守恒。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. 国策树定义（FOCUS_TREE）
#    每分支：{branch_key, branch_name, nodes: {node_key: {name, desc, power_level,
#            prereq(前置节点), unlock(解锁建筑/效果), effect(长期效果), exclusive_with}}}
# ---------------------------------------------------------------------------

FOCUS_TREE = {
    "govern": {
        "name": "政务",
        "desc": "整饬吏治，裁汰冗费，以固朝纲。",
        "nodes": {
            "g1_centralize": {
                "name": "中央集权",
                "desc": "收揽权柄，政令出于中枢。",
                "power_level": 1,
                "prereq": None,
                "unlock": "吏治清明",
                "effect": "govern_eff",
            },
            "g2_reform": {
                "name": "官制改革",
                "desc": "厘正官制，裁汰冗员。",
                "power_level": 2,
                "prereq": "g1_centralize",
                "unlock": "新官制",
                "effect": "govern_eff",
            },
            "g3_curtail": {
                "name": "裁汰冗费",
                "desc": "省浮节流，以实府库。",
                "power_level": 3,
                "prereq": "g2_reform",
                "unlock": "省费令",
                "effect": "govern_eff",
            },
        },
    },
    "military": {
        "name": "军事",
        "desc": "整军经武，修城固垒，以御外侮。",
        "nodes": {
            "m1_garrison": {
                "name": "整军经武",
                "desc": "整饬军旅，充实边备。",
                "power_level": 1,
                "prereq": None,
                "unlock": "边军",
                "effect": "military_eff",
            },
            "m2_fortify": {
                "name": "修城固垒",
                "desc": "增修城防，坚壁清野。",
                "power_level": 2,
                "prereq": "m1_garrison",
                "unlock": "城防",
                "effect": "military_eff",
            },
            "m3_war_machine": {
                "name": "军备军器",
                "desc": "广造军器，火器军用。",
                "power_level": 3,
                "prereq": "m2_fortify",
                "unlock": "军器监",
                "effect": "military_eff",
            },
        },
    },
    "science": {
        "name": "科学",
        "desc": "兴百工，修历法，奖掖技艺。",
        "nodes": {
            "s1_tech": {
                "name": "兴百工",
                "desc": "奖掖工匠，兴修水利机械。",
                "power_level": 1,
                "prereq": None,
                "unlock": "工坊",
                "effect": "science_eff",
            },
            "s2_calendar": {
                "name": "修历法",
                "desc": "校勘历法，精于天文。",
                "power_level": 2,
                "prereq": "s1_tech",
                "unlock": "司天监",
                "effect": "science_eff",
            },
            "s3_west": {
                "name": "西学东渐",
                "desc": "聘西洋匠，开机器局。",
                "power_level": 3,
                "prereq": "s2_calendar",
                "unlock": "机器局",
                "effect": "science_eff",
            },
        },
    },
    "internal": {
        "name": "内卫",
        "desc": "设密司，整肃言路，密探天下。",
        "nodes": {
            "i1_spy": {
                "name": "设皇城司",
                "desc": "设皇城司，刺探内外。",
                "power_level": 1,
                "prereq": None,
                "unlock": "皇城司",
                "effect": "internal_eff",
            },
            "i2_censor": {
                "name": "整肃言路",
                "desc": "整肃台谏，钳制异论。",
                "power_level": 2,
                "prereq": "i1_spy",
                "unlock": "御史台",
                "effect": "internal_eff",
            },
            "i3_control": {
                "name": "密探天下",
                "desc": "密探遍布，防患未然。",
                "power_level": 3,
                "prereq": "i2_censor",
                "unlock": "密探网",
                "effect": "internal_eff",
            },
        },
    },
    "tax": {
        "name": "税务",
        "desc": "清丈田亩，盐铁专卖，一条鞭法。",
        "nodes": {
            "t1_land_survey": {
                "name": "清丈田亩",
                "desc": "检括隐田，厘正田赋。",
                "power_level": 1,
                "prereq": None,
                "unlock": "清册",
                "effect": "tax_eff",
            },
            "t2_salt_iron": {
                "name": "盐铁专卖",
                "desc": "盐铁官营，利归公帑。",
                "power_level": 2,
                "prereq": "t1_land_survey",
                "unlock": "盐铁司",
                "effect": "tax_eff",
            },
            "t3_single_whip": {
                "name": "一条鞭法",
                "desc": "田赋折银，一条鞭征。",
                "power_level": 3,
                "prereq": "t2_salt_iron",
                "unlock": "一条鞭",
                "effect": "tax_eff",
            },
        },
    },
}

# 互斥分支：选择政务则军事降权，反之亦然（重文轻武 vs 重武轻文）
MUTUAL_EXCLUSIVE = {
    "govern": "military",
    "military": "govern",
}

# 分支 → 长期效果施加函数
_BRANCH_EFFECTS = {
    "govern": "govern_eff",
    "military": "military_eff",
    "science": "science_eff",
    "internal": "internal_eff",
    "tax": "tax_eff",
}


# ---------------------------------------------------------------------------
# 2. 初始化与查询
# ---------------------------------------------------------------------------

def init_focus_tree(state) -> None:
    """开局初始化国策树：全部分支未解锁，权力等级 0。"""
    state.focus_tree = {}
    for branch, spec in FOCUS_TREE.items():
        state.focus_tree[branch] = {
            "name": spec["name"],
            "desc": spec["desc"],
            "nodes": {
                nk: {
                    "name": nd["name"],
                    "desc": nd["desc"],
                    "power_level": 0,          # 0=未解锁，1~3=已解锁等级
                    "unlocked": False,
                    "unlock": nd.get("unlock", ""),
                }
                for nk, nd in spec["nodes"].items()
            },
        }


def can_unlock(state, branch: str, node_key: str) -> tuple:
    """判断某节点是否可解锁。返回 (可解锁, 原因)。"""
    branch_spec = FOCUS_TREE.get(branch)
    if not branch_spec:
        return False, "无此分支"
    node_spec = branch_spec["nodes"].get(node_key)
    if not node_spec:
        return False, "无此节点"
    cur = state.focus_tree.get(branch, {}).get("nodes", {}).get(node_key, {})
    if cur.get("unlocked"):
        return False, "已解锁"
    # 前置节点
    prereq = node_spec.get("prereq")
    if prereq:
        pre = state.focus_tree.get(branch, {}).get("nodes", {}).get(prereq, {})
        if not pre.get("unlocked"):
            return False, f"需先解锁「{FOCUS_TREE[branch]['nodes'][prereq]['name']}」"
    # 互斥分支：若互斥分支已解锁同等级或更高，则不可解锁
    mutex = MUTUAL_EXCLUSIVE.get(branch)
    if mutex:
        mutex_nodes = state.focus_tree.get(mutex, {}).get("nodes", {})
        if any(n.get("unlocked") for n in mutex_nodes.values()):
            return False, f"与「{FOCUS_TREE[mutex]['name']}」分支互斥"
    return True, ""


def unlock_focus(state, branch: str, node_key: str) -> dict:
    """解锁国策节点。返回结果字典 {ok, msg, unlock}。"""
    ok, reason = can_unlock(state, branch, node_key)
    if not ok:
        return {"ok": False, "message": reason}
    node_spec = FOCUS_TREE[branch]["nodes"][node_key]
    cur = state.focus_tree[branch]["nodes"][node_key]
    cur["unlocked"] = True
    cur["power_level"] = node_spec["power_level"]
    # 施加解锁效果（写入 tech.assets / 相关字段）
    _apply_unlock(state, branch, node_key, node_spec)
    return {"ok": True, "message": f"已解锁：{node_spec['name']}", "unlock": node_spec.get("unlock", "")}


def _apply_unlock(state, branch, node_key, node_spec) -> None:
    """解锁建筑/长期效果：写入 state.tech.assets 或相关字段。"""
    unlock = node_spec.get("unlock", "")
    if not unlock:
        return
    # 写入科技资产（建筑/器物统一）
    try:
        state.tech.setdefault("assets", {})[f"focus_{branch}_{node_key}"] = {
            "name": unlock,
            "kind": "focus_building",
            "branch": branch,
            "node": node_key,
        }
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 3. 月度结算（长期效果施加）
# ---------------------------------------------------------------------------

def settle_focus(state, log) -> None:
    """月度结算：对已解锁节点施加长期效果（确定性修正，非守恒字段）。"""
    if not state.focus_tree:
        return
    for branch, bspec in state.focus_tree.items():
        for nk, node in bspec.get("nodes", {}).items():
            if not node.get("unlocked"):
                continue
            eff = _BRANCH_EFFECTS.get(branch)
            if eff:
                _apply_branch_effect(state, log, branch, eff, node)


def _apply_branch_effect(state, log, branch, eff, node) -> None:
    """按分支施加长期效果（确定性修正，非守恒字段）。"""
    try:
        if branch == "govern":
            # 政务：裁汰冗费，财政减耗
            state.statistics["total_expense"] = max(
                0, state.statistics.get("total_expense", 0) - 5000)
        elif branch == "military":
            # 军事：军备增强（城防/军器）
            for line in state.defense_lines.values():
                line["fortification"] = min(100, line.get("fortification", 0) + 1)
        elif branch == "science":
            # 科学：技术积累提升
            state.tech["level"] = min(100, state.tech.get("level", 0) + 1)
        elif branch == "internal":
            # 内卫：民心微损（密探高压），但防患
            state.population_satisfaction = max(0, state.population_satisfaction - 1)
        elif branch == "tax":
            # 税务：清隐田，隐漏率下降
            state.land["hidden_rate"] = max(0.05, state.land.get("hidden_rate", 0.35) - 0.01)
    except Exception:
        pass


def focus_summary(state) -> dict:
    """返回国策树摘要（供 UI / 简报展示）。"""
    out = {}
    for branch, bspec in state.focus_tree.items():
        unlocked = [n for n in bspec.get("nodes", {}).values() if n.get("unlocked")]
        out[branch] = {
            "name": bspec["name"],
            "desc": bspec["desc"],
            "unlocked_count": len(unlocked),
            "total": len(bspec.get("nodes", {})),
            "unlocked": [n.get("name", "") for n in unlocked],
        }
    return out


__all__ = [
    "FOCUS_TREE", "MUTUAL_EXCLUSIVE", "init_focus_tree", "can_unlock",
    "unlock_focus", "settle_focus", "focus_summary",
]