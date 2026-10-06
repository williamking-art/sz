# -*- coding: utf-8 -*-
"""宋祚 · 农业供给与收入反馈（规格 `market-civilian-economy` **B2-R4**）。

> 本模块**尚未接线**到 `settlement.py`（由 Lead 统一接线）。建议接线位置见本文件的
> `WIRING_HINT` 常量与 `apply_agri_effects` 的 docstring。

## 一、要治的病（B2-R4 原文）

> 把农业投资作为首选长期修复：土地/水利/农具等经可执行工程或科技方案提高实际粮食产出、
> 减少损耗或运输瓶颈；新增产出需有土地/材料/劳务/维护成本，收入归真实生产/销售主体。
> **不得先给 POP 加财富数值。**

现状实测（2026-11 工作区）：

1. `core/settlement_econ._settle_land_local` 收获月（3/6/9）按 `prefectures[路]["grain"] / 3`
   把年产粮分给农/士绅/太仓/内帑；`p["grain"]` 只按 **1.002/月**自然增长
   （`settlement_econ.py:327`），**与该路田亩、投资、工程、科技全都无关**。
2. 科技节点的 `yield_bonus`（如 `M1_noria`、`C4_fertilizer`）经
   `core/asset_context._apply_effect_delta` 写进 `state.land["yield"]`，而该系数
   **只作用于税基**（`game_state_econ.calc_monthly_grain` / `calc_monthly_tax_income`），
   **不改变任何一石实物粮**。⇒ 玩家花钱修水利、点科技，**粮不会多一石**。
3. 故 240 月复验里"农业投资救不了粮市"不是参数问题，而是**因果链缺口**：
   投资 → 实物增产的通道不存在。

## 二、本模块的口径（硬约束逐条对照）

| 约束 | 落地方式 |
|---|---|
| **POP 挂载律** | 新增产出一律落 `prefectures[路].pops["农"]["grain"]`（与 `_settle_land_local` 收获分配**同一落点**）。**本模块从不凭空写任何 POP 的 `wealth`、从不改任何 POP 的 `size`**（劳务按工时口径消耗，只记 `statistics`）。 | |
| **收入归真实主体** | 农户财富来自**既有粮市撮合**（`settlement_granary._settle_granary` 净头寸撮合）：增产粮 → 可售余粮 ↑ → 买粮的 POP `wealth` −／农 `wealth` +。**本模块唯一的 wealth 写入**是维护费经 `transfer_money` 的**路级划转**（国库 → 本路工匠/商人）；农的 wealth 增长**只能**由粮市撮合产生。 |
| **新增产出必须有成本** | 四项成本**先扣后产**：土地（`state.land["wasteland"]` → 本路 `p["land"]` 真实转移）、材料（`state.resources[dim]["stock"]` 真扣）、劳务（工匠工时）、维护费（国库 → **本路**工匠/商人，`GameState.transfer_money` 路级守恒划转，同 `_settle_land_local` 一条鞭税）。任一不足按**最短板同比例降效**，绝不先产后补账。 |
| **缺失 ≠ 0 ≠ 1.0** | 路不存在／无农 POP／无 `p["grain"]` 基数／等级读数缺失 ⇒ 读数返回 `defined=False` 且效果值 **`None`**，并附 `reason`；**不回落 0.0/1.0 假装无事**。`buildings` 键整体缺失按"缺失"记（`missing` 列表），不当成"零投资"。 |
| **拒绝式处理非法输入** | `route`/`state` 类型非法、注册表条目含 NaN/负值 ⇒ `raise TypeError/ValueError`（不静默跳过）。 |
| **口径单点** | 效果表 = 本模块 `AGRI_UPGRADE_EFFECTS`；覆盖算法 = `route_agri_effect` 单一实现，`apply_agri_effects` 不复制算法，只调用它。 |
| **无平行账本** | 全部流量登记进既有 `state.statistics["agri_*"]` 与既有 `pops[].grain` / `state.resources` / `state.land`。 |

## 三、三个效果通道

| 通道 | 含义 | 本模块提供 | 由谁消费（**Lead 接线**） |
|---|---|---|---|
| `yield_mult` | 实际粮食**增产** | `apply_agri_effects` **直接落账**（收获月） | 本模块内（已实现） |
| `loss_reduction` | 存粮**霉耗/损耗降低** | `effective_spoil_rate(state, route, base_rate)` | `settlement_granary` 农储霉耗段（第 533-540 行） |
| `transport_relief` | 漕运**瓶颈缓解**（`canal_block` 百分点） | `effective_canal_block(state, base_block=None)` | `settlement_granary` 漕运段（第 88 行 `canal_eff`） |

后两个是**钩子函数（hook）**：本模块只算值、不改既有文件；Lead 决定是否接线。

## 四、迁移策略

* **无 schema 迁移**：全部落点是既有字段
  （`pops[].grain` / `resources[].stock` / `state.land` / `p["land"]` / `state.statistics`）。
  `state.statistics` 在 `save_load.py:213` 整表序列化 ⇒ 新 `agri_*` 键自动随档保存，
  旧档缺这些键时读侧 `get(..., 0)` 属**读数累加器**（非模拟状态），不算"缺失伪装"。
* **幂等**：`_stat_add` 只做累加，不做"存量修正"，重复调用不炸；
  真正的月度防重由调用步序保证（每月一次）。
* **旧档缺 `p["land"]`**：读数按缺失处理（`_coverage` 记 `land=missing` ⇒ 土地成本
  到位率 0 ⇒ 该路本月不产），不默认 0（否则会凭空把荒田全转成在册田亩）。

## 五、参数表（**暂置本模块**，Lead 后续并入 `content/data_constants.py`）

见 `AGRI_UPGRADE_EFFECTS` 与本文件上部常量块。每条都有注释说明来源与量级依据。
参数**方向性**已定（投资 → 增产/减损/缓解），**数值**待 60/240 月实测校准；
校准前不得据此宣称 B2 平衡验收通过。
"""
from __future__ import annotations

# 🔴 G-3（2026-10-04）：POP 粮写入走 `grain_bridge`（写只落一个载体，绝不双写）。
# 未下沉时桥接返回 None，调用方回落原写法。
from core.foundation.ledger.grain_bridge import grain_add as _grain_add

import math
from typing import Any, Dict, List, Optional

__all__ = [
    "AGRI_UPGRADE_EFFECTS",
    "AGRI_HARVEST_MONTHS",
    "AGRI_LEVEL_CAP",
    "AGRI_LOSS_REDUCTION_CAP",
    "AGRI_TRANSPORT_RELIEF_CAP",
    "AgriUpgradeError",
    "apply_agri_effects",
    "effective_canal_block",
    "effective_spoil_rate",
    "register_agri_upgrade",
    "resolve_agri_upgrade",
    "route_agri_effect",
    "WIRING_HINT",
]

# =============================================================================
# 一、模块级常量（参数表；Lead 并入 content/data_constants.py 时请保持同名同义）
# =============================================================================

#: 收获月（三运期：春 3 / 夏 6 / 秋 9）。**与 `_settle_land_local._harvest`、
#: `game_state_econ.calc_monthly_grain` 同一节奏**，不得单开一套农时。
AGRI_HARVEST_MONTHS = (3, 6, 9)

#: 年度增产在每个收获月的分摊份额（1/3），保证「年增产 = 年产 × yield_mult」。
AGRI_HARVEST_SHARE = 1.0 / float(len(AGRI_HARVEST_MONTHS))

#: 单项农业投资的等级上限（对齐 `BUILDING_LEVEL_CAP`/`era_mechanic.building_level_cap` 的 Lv1-5）。
AGRI_LEVEL_CAP = 5

#: 损耗降幅封顶 50%：**不得把霉耗归零**（归零＝删掉既有消耗口径，是另一种造假）。
AGRI_LOSS_REDUCTION_CAP = 0.5

#: 全国 `canal_block` 缓解封顶（百分点）。`canal_block` 是 0-100 的淤塞度。
AGRI_TRANSPORT_RELIEF_CAP = 30.0

#: 维护费模式枚举：
#:   · ``"asset_maintenance"`` —— 运维**已由 `_settle_upkeep` 按"资产折算造价×0.5%/月"
#:     全局计"覆盖**（官造建筑/官营设施走这条），本项 `upkeep_per_lv` 须为 0，
#:     **避免与资产维持费重复收费**；
#:   · ``"incremental"`` —— **增量专项运维**（农具修理、犊料、渠泥清淤的物料工钱），
#:     由国库另付、经 `GameState.transfer_money` 真实转给**本路**工匠/商人。
AGRI_MAINTENANCE_MODES = ("asset_maintenance", "incremental")

#: 接线建议（只读常量，供 Lead 与面板提示；**本模块不自行接线**）。
WIRING_HINT = (
    "结算步顺序建议：_settle_economy → _settle_land_local →【apply_agri_effects】→ "
    "_settle_region_deepen → … → _settle_projects → _settle_upkeep → "
    "_settle_granary → …。理由：(1) 紧随收获分配/田赋之后，增产不二次计税、"
    "口径与「田赋按核定田亩」不冲突；(2) 早于 _settle_granary 的粮市撮合 ⇒ "
    "同月即可形成可售粮与农户售粮收入（数季内见效）；"
    "(3) 晚于 _settle_economy ⇒ 人口/阶层流动先于增产落账。"
    "损耗与运输两个钩子须在 _settle_granary 内消费（Lead 接线）。"
)

#: 统计键（全部落既有 `state.statistics`，随档整表保存）
#: 物料按维度另记 `agri_material_used_<dim>`（如 `agri_material_used_木`）。
AGRI_STAT_KEYS = (
    "agri_grain_produced",      # 实物增产（石）——粮账恒等式的"产"项，须可登记
    "agri_upkeep_paid",         # 维护费实付（贯）
    "agri_land_cultivated",     # 开垦（亩）
    "agri_labor_hours",         # 劳务消耗（工时）
    "agri_effect_lost_ratio",   # 因成本不足而损失的应得效果比例（Σ(1−到位率)）
    "agri_undefined_routes",    # 读数未定义的路数（本月）
)

# =============================================================================
# 二、注册表：农业投资键 → 效果与成本
# =============================================================================
# 键的解析顺序（`resolve_agri_upgrade`）：
#   1. `prefectures[路]["buildings"]` 的**建筑名**（`_settle_projects` 完工登记时写的键）
#   2. `state.projects[*]` 的 `blueprint_key` / `name` / `type`
#   3. 本表 `aliases`（同一效果的不同书写）
#
# ⚠️ 去重纪律：一条效果**只按一个通道**计。同名建筑已登记在 `prefectures[路]["buildings"]`
# 时，`state.projects` 里的同名工程**不再重复计入**（记入 `duplicates`，可审计）。
#
# 字段：
#   label            中文名（面板/日志）
#   category         分类（irrigation/fertilizer/farm/storage/…）
#   sources          允许的生效通道：("building",) / ("project",) / ("tech",)
#   aliases          同效果的其它书写（蓝图键、工程 type 名…）
#   yield_mult       每级增产比例（乘算，0.05 = +5%/级）
#   loss_reduction   每级损耗降幅（乘算，封顶 AGRI_LOSS_REDUCTION_CAP）
#   transport_relief 每级对 `canal_block` 的缓解（百分点）
#   land_per_lv      每级需**新开垦**亩数（土地成本；从 `state.land["wasteland"]` 真实划出）
#   material_per_lv  每级月度运维物料（真扣 `state.resources[dim]["stock"]`）
#   labor_per_lv     每级月度工匠工时（劳务成本）
#   maintenance_mode "asset_maintenance" → upkeep_per_lv 必须为 0
#                    "incremental"      → 本项自付运维费（国库 → 工匠/商人）
#   upkeep_per_lv    每级月度维护费（贯）
#   tech_node/deploy_building  仅 `sources=("tech",)`：节点 id 与其部署建筑名（路级归属依据）
AGRI_UPGRADE_EFFECTS: Dict[str, Dict[str, Any]] = {
    # ---- 官造建筑（`content/data.BUILDING_STD` 已有"水利/常平仓"，非新增建筑）----
    "水利": {
        "label": "水利", "category": "irrigation", "sources": ("building",),
        "yield_mult": 0.050, "loss_reduction": 0.010, "transport_relief": 2.0,
        "land_per_lv": 2_000,
        "material_per_lv": {"木": 60, "石": 40},
        "labor_per_lv": 40.0,
        # 官造水利：营建款已在 `_settle_projects` 付过、月度运维已在 `_settle_upkeep`
        # 按造价统一计 ⇒ 此处**不另计**（防重复收费）。
        "maintenance_mode": "asset_maintenance", "upkeep_per_lv": 0,
    },
    "常平仓": {
        "label": "常平仓", "category": "storage", "sources": ("building",),
        "yield_mult": 0.000, "loss_reduction": 0.030, "transport_relief": 0.0,
        "land_per_lv": 0,
        "material_per_lv": {"木": 40},
        "labor_per_lv": 20.0,
        "maintenance_mode": "asset_maintenance", "upkeep_per_lv": 0,
    },
    # ---- 科技蓝图建筑（`BUILDING_BLUEPRINTS["C4_fertilizer"]["name"] == "肥料局"）----
    "肥料局": {
        "label": "肥料局", "category": "fertilizer",
        "sources": ("building", "project"),
        "aliases": ("C4_fertilizer",),
        "yield_mult": 0.030, "loss_reduction": 0.000, "transport_relief": 0.0,
        "land_per_lv": 500,
        "material_per_lv": {"木": 30},
        "labor_per_lv": 30.0,
        "maintenance_mode": "asset_maintenance", "upkeep_per_lv": 0,
    },
    # ---- POP 自有农庄（`content/data_constants.POP_BUILDING_TYPES`）----
    # 民间自办设施：营建款由阶层 wealth 自出、**不进 `_settle_upkeep` 的官造资产口径**
    # （该步对 POP 建筑按 `POP_BUILDING_VALUE` 统一计一次，故仍走 asset_maintenance）；
    # 增量专项运维（农具修理/渠泥/犊料）单列，走国库补助 → 工匠/商人。
    "农田": {
        "label": "农田", "category": "farm", "sources": ("building",),
        "yield_mult": 0.020, "loss_reduction": 0.005, "transport_relief": 0.0,
        "land_per_lv": 500,
        "material_per_lv": {"木": 20},
        "labor_per_lv": 10.0,
        "maintenance_mode": "incremental", "upkeep_per_lv": 60,
    },
    "自耕农庄": {
        "label": "自耕农庄", "category": "farm", "sources": ("building",),
        "yield_mult": 0.025, "loss_reduction": 0.008, "transport_relief": 0.0,
        "land_per_lv": 800,
        "material_per_lv": {"木": 30},
        "labor_per_lv": 20.0,
        "maintenance_mode": "incremental", "upkeep_per_lv": 90,
    },
    "地主农庄": {
        "label": "地主农庄", "category": "farm", "sources": ("building",),
        "yield_mult": 0.020, "loss_reduction": 0.008, "transport_relief": 0.0,
        "land_per_lv": 800,
        "material_per_lv": {"木": 30},
        "labor_per_lv": 20.0,
        "maintenance_mode": "incremental", "upkeep_per_lv": 90,
    },
    # ---- 科技节点（无实体建筑可登记，靠部署建筑的等级 × 全国 adoption 分摊到路）----
    "水排筒车": {
        "label": "水排筒车", "category": "irrigation", "sources": ("tech",),
        "tech_node": "M1_noria", "deploy_building": "水排筒车",
        "yield_mult": 0.020, "loss_reduction": 0.005, "transport_relief": 0.0,
        "land_per_lv": 1_000,
        "material_per_lv": {"木": 25},
        "labor_per_lv": 25.0,
        "maintenance_mode": "asset_maintenance", "upkeep_per_lv": 0,
    },
}

#: 别名 → 规范键（`resolve_agri_upgrade` 用；由 `_build_alias_index` 惰性构建）
_ALIAS_INDEX: Optional[Dict[str, str]] = None


class AgriUpgradeError(ValueError):
    """注册表条目非法（缺字段/负值/非有限值/通道矛盾）。**拒绝式**：不静默跳过。"""


# =============================================================================
# 三、注册表访问
# =============================================================================

def _build_alias_index() -> Dict[str, str]:
    global _ALIAS_INDEX
    if _ALIAS_INDEX is not None:
        return _ALIAS_INDEX
    idx: Dict[str, str] = {}
    for key, entry in AGRI_UPGRADE_EFFECTS.items():
        idx[str(key)] = key
        for a in (entry.get("aliases") or ()):
            idx[str(a)] = key
    _ALIAS_INDEX = idx
    return idx


def _num(value: Any, field: str, key: str) -> float:
    """数值校验：**拒绝式**。非有限/负数 ⇒ raise（不回落 0/1.0）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgriUpgradeError(
            f"AGRI_UPGRADE_EFFECTS[{key!r}].{field} 必须是数值，得 {value!r}")
    v = float(value)
    if not math.isfinite(v):
        raise AgriUpgradeError(
            f"AGRI_UPGRADE_EFFECTS[{key!r}].{field} 非有限值 {value!r}（不得回落 0/1.0）")
    if v < 0:
        raise AgriUpgradeError(f"AGRI_UPGRADE_EFFECTS[{key!r}].{field} 为负 {value!r}")
    return v


def _validate_entry(key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise AgriUpgradeError(f"注册表条目 {key!r} 必须是 dict")
    srcs = entry.get("sources")
    if not isinstance(srcs, (tuple, list)) or not srcs:
        raise AgriUpgradeError(f"注册表条目 {key!r} 缺 sources")
    for s in srcs:
        if s not in ("building", "project", "tech"):
            raise AgriUpgradeError(f"注册表条目 {key!r} 的 sources 含未知通道 {s!r}")
    mode = entry.get("maintenance_mode")
    if mode not in AGRI_MAINTENANCE_MODES:
        raise AgriUpgradeError(
            f"注册表条目 {key!r} 的 maintenance_mode={mode!r} 非法"
            f"（应为 {AGRI_MAINTENANCE_MODES}）")
    upd = _num(entry.get("upkeep_per_lv", 0), "upkeep_per_lv", key)
    if mode == "asset_maintenance" and upd != 0:
        raise AgriUpgradeError(
            f"注册表条目 {key!r} 声明 asset_maintenance 却带 upkeep_per_lv={upd}"
            f"（会与 _settle_upkeep 的资产维持费重复收费）")
    mat = entry.get("material_per_lv") or {}
    if not isinstance(mat, dict):
        raise AgriUpgradeError(f"注册表条目 {key!r} 的 material_per_lv 必须是 dict")
    for dim, q in mat.items():
        if not isinstance(dim, str) or not dim:
            raise AgriUpgradeError(f"注册表条目 {key!r} 的物料维度非法 {dim!r}")
        # 🔴 配置里的维度名**必须**取自 `material_holding.MATERIAL_DIMS`
        # （建材口径 E-1）。配置表自然要写维度名（那是数据不是算法），
        # 但**拼错必须报错**，否则该升级会永远走"缺料"分支而**静默失效**。
        from core.foundation.ledger.material_holding import MATERIAL_DIMS
        if dim not in MATERIAL_DIMS:
            raise AgriUpgradeError(
                f"注册表条目 {key!r} 的物料维度 {dim!r} 不在 MATERIAL_DIMS "
                f"{MATERIAL_DIMS} 内（建材口径 E-1；`粮` 等请走 pops[].grain）")
        _num(q, f"material_per_lv[{dim}]", key)
    for field in ("yield_mult", "loss_reduction", "transport_relief",
                  "land_per_lv", "labor_per_lv"):
        _num(entry.get(field, 0), field, key)
    if "tech" in srcs:
        for field in ("tech_node", "deploy_building"):
            if not entry.get(field):
                raise AgriUpgradeError(
                    f"注册表条目 {key!r} 走 tech 通道但缺 {field}（无部署路径 ⇒ "
                    f"无法把全国 adoption 归属到路，**不得臆造归属**）")
    return entry


def register_agri_upgrade(key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """动态注册一条农业投资效果（B4/B5 新蓝图行动入口）。

    非法条目**拒绝并抛 `AgriUpgradeError`**（含非有限值/负值/通道矛盾/tech 缺部署路径），
    不静默写入半个条目。成功返回登记后的条目（同一对象，便于就地微调）。
    """
    if not isinstance(key, str) or not key.strip():
        raise AgriUpgradeError(f"注册键非法：{key!r}")
    _validate_entry(key, entry)
    AGRI_UPGRADE_EFFECTS[key] = entry
    _invalidate_alias_index()
    return entry


def _invalidate_alias_index() -> None:
    global _ALIAS_INDEX
    _ALIAS_INDEX = None


def resolve_agri_upgrade(key: Any) -> Optional[Dict[str, Any]]:
    """投资键 → 注册条目；未注册返回 `None`（调用方须记入 `unregistered`，**不得兜底成中性值**）。"""
    if not isinstance(key, str) or not key:
        return None
    canon = _build_alias_index().get(key)
    if canon is None:
        return None
    return AGRI_UPGRADE_EFFECTS.get(canon)


# =============================================================================
# 四、读数：某路农业投资效果（纯派生，不写任何状态）
# =============================================================================

_READOUT_KEYS = (
    "route", "defined", "reason", "annual_grain", "yield_mult", "loss_reduction",
    "transport_relief", "applied_ratio", "cover", "upkeep_coin", "labor_hours",
    "material", "land_mu", "sources", "missing", "unregistered", "duplicates",
    "carriers_readable",
)


def _undefined(route: Any, reason: str) -> Dict[str, Any]:
    """未定义读数：效果值一律 `None`（**不回落 0.0/1.0**），并带可诊断 `reason`。"""
    out = {k: None for k in _READOUT_KEYS}
    out.update({
        "route": route if isinstance(route, str) else None,
        "defined": False,
        "reason": reason,
        "sources": [],
        "missing": [],
        "unregistered": [],
        "duplicates": [],
        "carriers_readable": 0,
    })
    return out


def _finite_or_none(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    if not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _collect_sources(state, route: str, p: Dict[str, Any]):
    """枚举该路已登记/可读的三类载体（建筑 / 工程 / 科技节点）。

    返回 `(sources, missing, unregistered, duplicates, carriers_readable)`：
      · sources        —— 可计入效果者 `{"key","label","source","lv","channel"}`
      · missing        —— 载体存在但**读数缺失**（不得当 0/1.0）
      · unregistered   —— 该路有农业外观的建筑/工程但**未在注册表登记**（可诊断）
      · duplicates     —— 已由建筑计入、同名工程被去重（审计用）
      · carriers_readable —— 至少一个载体成功读取（否则整路读数 defined=False）
    """
    sources: List[Dict[str, Any]] = []
    missing: List[str] = []
    unregistered: List[str] = []
    duplicates: List[str] = []
    readable = 0

    from core.building_jobs import building_level as _bld_lv

    # ---- 载体 1：路级建筑 ----
    buildings = p.get("buildings")
    if isinstance(buildings, dict):
        readable += 1
        for name, entry in buildings.items():
            reg = resolve_agri_upgrade(name)
            if reg is None:
                continue                      # 非农业投资（官署/学校/军营…），不计不报
            if "building" not in reg["sources"]:
                continue
            lv = _bld_lv(entry, 0)             # 统一读口，保留 0（裁撤=无效果）
            if lv <= 0:
                continue
            lv = min(int(lv), AGRI_LEVEL_CAP)
            sources.append({"key": name, "label": reg.get("label") or name,
                            "source": "building", "lv": lv, "channel": name})
    elif buildings is None:
        missing.append("route_buildings_missing")
    else:
        missing.append("route_buildings_malformed")

    # ---- 载体 2：本路工程 ----
    projects = getattr(state, "projects", None)
    if isinstance(projects, dict):
        readable += 1
        canon_index = _build_alias_index()
        seen_regs = {canon_index.get(s["key"]) for s in sources
                     if canon_index.get(s["key"]) is not None}
        for pid, proj in projects.items():
            if not isinstance(proj, dict):
                missing.append(f"project:{pid}:malformed")
                continue
            if str(proj.get("route") or proj.get("prefecture") or "") != route:
                continue
            status = proj.get("status")
            if status == "abandoned" or proj.get("abandoned"):
                continue
            if not (status in ("operating", "degraded") or proj.get("done")):
                continue                      # 未建成不生效
            reg = (resolve_agri_upgrade(proj.get("blueprint_key"))
                   or resolve_agri_upgrade(proj.get("name"))
                   or resolve_agri_upgrade(proj.get("type")))
            if reg is None:
                key_txt = str(proj.get("blueprint_key") or proj.get("name")
                              or proj.get("type") or "")
                if key_txt:
                    unregistered.append(f"project:{pid}:{key_txt}")
                continue
            if "project" not in reg["sources"]:
                continue
            canon = proj.get("blueprint_key") or proj.get("name") or proj.get("type")
            # 去重按**注册表规范键**（蓝图键与建筑名可能指向同一条效果）
            if canon_index.get(str(canon)) in seen_regs:
                duplicates.append(f"project:{pid}:{canon}")
                continue                      # 已由路级建筑计入 → 不重复
            cap = _finite_or_none(proj.get("capacity"))
            if cap is None:
                # **不回落 1.0**：产能读数缺失 ⇒ 该工程本月不计入效果，并留痕。
                missing.append(f"project:{pid}:capacity_missing")
                continue
            levels = _finite_or_none(proj.get("levels"))
            if levels is None:
                levels = 1.0 if proj.get("levels") is None else None
            if levels is None:
                missing.append(f"project:{pid}:levels_invalid")
                continue
            lv = min(levels * cap, float(AGRI_LEVEL_CAP))
            if lv <= 0:
                continue
            sources.append({"key": str(canon), "label": reg.get("label") or str(canon),
                            "source": "project", "lv": round(lv, 4), "channel": str(canon)})
    elif projects is None:
        missing.append("state_projects_missing")
    else:
        missing.append("state_projects_malformed")

    # ---- 载体 3：科技节点（按部署建筑等级 × 全国 adoption 分摊到路）----
    tech = getattr(state, "tech", None)
    if isinstance(tech, dict):
        readable += 1
        assets = tech.get("assets")
        if not isinstance(assets, dict):
            assets = {}
            missing.append("tech_assets_missing")
        for key, reg in AGRI_UPGRADE_EFFECTS.items():
            if "tech" not in reg["sources"]:
                continue
            node = str(reg["tech_node"])
            rec = assets.get(node)
            if rec is None:
                continue                      # 未解锁 = 实测无部署，非缺失
            if not isinstance(rec, dict):
                missing.append(f"tech:{node}:record_malformed")
                continue
            adoption = _finite_or_none(rec.get("adoption"))
            if adoption is None:
                missing.append(f"tech:{node}:adoption_missing")
                continue
            if adoption <= 0:
                continue
            deploy_lv = _bld_lv((buildings or {}).get(reg["deploy_building"], 0), 0)
            if deploy_lv <= 0:
                continue                      # 本路未部署 ⇒ 无路级归属（不臆造）
            lv = min(float(deploy_lv) * adoption, float(AGRI_LEVEL_CAP))
            if lv <= 0:
                continue
            sources.append({"key": key, "label": reg.get("label") or key,
                            "source": "tech", "lv": round(lv, 4), "channel": node})
    elif tech is None:
        missing.append("state_tech_missing")
    else:
        missing.append("state_tech_malformed")

    # 未登记的**路级建筑**：仅登记看起来像农业的（避免把官署/学校报成缺口）
    if isinstance(buildings, dict):
        for name in buildings:
            reg = resolve_agri_upgrade(name)
            if reg is None and str(name) in _AGRI_LOOKALIKE_NAMES:
                unregistered.append(f"building:{name}")

    return sources, missing, unregistered, duplicates, readable


#: 农业外观的建筑/工程名（用于把「有农业投资痕迹但未注册」报出来；刻意短小，不猜。
_AGRI_LOOKALIKE_NAMES = frozenset({
    "农田", "农具", "农具坊", "水排筒车", "肥料局", "常平仓", "水利", "陂塘", "渠",
    "自耕农庄", "地主农庄", "官营农具场", "义仓",
})


def route_agri_effect(state, route: str) -> Dict[str, Any]:
    """某路**农业投资效果的纯读数**（不写任何状态）。

    返回 dict，键见 `_READOUT_KEYS`：
      · `defined=False` ⇒ 效果值为 `None`，看 `reason`（缺失 ≠ 0 ≠ 1.0）；
      · `defined=True` 且 `sources == []` ⇒ **实测无农业投资**（不是缺失），
        此时 `yield_mult/loss_reduction/transport_relief` 均为 `0.0`；
      · `applied_ratio` = 四项成本的**最短板到位率**（0~1），未产出部分即降效部分。

    非法输入（`route` 非 str / `state.prefectures` 非 dict）⇒ 抛 `TypeError`/`ValueError`。
    """
    if state is None:
        raise TypeError("state 不能为 None")
    if not isinstance(route, str) or not route:
        raise ValueError(f"route 必须是非空 str（收到 {route!r}）")
    prefs = getattr(state, "prefectures", None)
    if prefs is None:
        raise ValueError("state.prefectures 缺失（state 未初始化？）")
    if not isinstance(prefs, dict):
        raise TypeError(f"state.prefectures 应为 dict，得 {type(prefs).__name__}")

    p = prefs.get(route)
    if not isinstance(p, dict):
        return _undefined(route, "unknown_route")

    pops = p.get("pops")
    if not isinstance(pops, dict) or not isinstance(pops.get("农"), dict):
        return _undefined(route, "no_farmer_pop")

    annual = _finite_or_none(p.get("grain"))
    if annual is None or annual <= 0:
        # 增产基数读不到 ⇒ 增产效果**不可判定**（不回落 0）
        return _undefined(route, "no_route_grain_baseline")

    sources, missing, unregistered, duplicates, readable = _collect_sources(state, route, p)
    if readable == 0:
        return _undefined(route, "no_readable_carriers")
    if not sources and missing:
        # 有农业投资的痕迹但**等级/部署读数全部缺失** ⇒ 效果不可判定。
        # 注意：`missing` 必须带出去（`_undefined` 会清空它），否则可诊断性丢失。
        out = _undefined(route, "all_investment_levels_missing")
        out["missing"] = list(missing)
        out["unregistered"] = list(unregistered)
        return out

    # ---- 汇总（成本与效果都按等级线性；乘算通道在上层合成）----
    ym = lr = tr = 0.0
    upkeep = 0.0
    labor = 0.0
    land = 0.0
    material: Dict[str, float] = {}
    for s in sources:
        reg = AGRI_UPGRADE_EFFECTS.get(s["key"]) or resolve_agri_upgrade(s["key"])
        if reg is None:                                   # 理论上不可达（已登记过）
            missing.append(f"source:{s['key']}:registry_vanished")
            continue
        lv = float(s["lv"])
        ym += _num(reg.get("yield_mult", 0), "yield_mult", s["key"]) * lv
        lr += _num(reg.get("loss_reduction", 0), "loss_reduction", s["key"]) * lv
        tr += _num(reg.get("transport_relief", 0), "transport_relief", s["key"]) * lv
        upkeep += _num(reg.get("upkeep_per_lv", 0), "upkeep_per_lv", s["key"]) * lv
        labor += _num(reg.get("labor_per_lv", 0), "labor_per_lv", s["key"]) * lv
        land += _num(reg.get("land_per_lv", 0), "land_per_lv", s["key"]) * lv
        for dim, q in (reg.get("material_per_lv") or {}).items():
            material[dim] = material.get(dim, 0.0) + _num(q, "material_per_lv", s["key"]) * lv

    lr = min(lr, AGRI_LOSS_REDUCTION_CAP)
    tr = min(tr, AGRI_TRANSPORT_RELIEF_CAP)
    upkeep_i = int(round(upkeep))
    land_mu = int(round(land))

    cover = _coverage(state, p, material, labor, land_mu, upkeep_i)
    ratio = min(cover["material"], cover["labor"], cover["land"], cover["upkeep"]) \
        if (material or labor or land_mu or upkeep_i) else 1.0
    ratio = max(0.0, min(1.0, ratio))

    return {
        "route": route,
        "defined": True,
        "reason": "",
        "annual_grain": int(annual),
        "yield_mult": round(ym, 6),
        "loss_reduction": round(lr, 6),
        "transport_relief": round(tr, 4),
        "applied_ratio": round(ratio, 6),
        "cover": {k: round(float(v), 6) for k, v in cover.items()},
        "upkeep_coin": upkeep_i,
        "labor_hours": round(labor, 4),
        "material": {k: round(v, 4) for k, v in material.items()},
        "land_mu": land_mu,
        "sources": sources,
        "missing": missing,
        "unregistered": unregistered,
        "duplicates": duplicates,
        "carriers_readable": readable,
    }


def _coverage(state, p: Dict[str, Any], material: Dict[str, float],
              labor: float, land_mu: int, upkeep_i: int) -> Dict[str, float]:
    """四项成本的到位率（各自独立，调用方取**最短板**）。不足即降效，绝不凭空补。"""
    # 材料
    # 🔴 口径 C-c（2026-10-02）：只从**本地州府仓**取料，取不到即缺料。
    # 不再直读 `state.resources[dim]["stock"]`——那是全国总账，读它等于
    # "料可凭空调用"，**物流便失去意义**。判定与落扣**共用**同一个读口。
    from core.foundation.ledger.material_holding import material_holding_for_circuit
    mat_cover = 1.0
    circuit = p.get("name") or p.get("circuit") or ""
    for dim, need in material.items():
        if need <= 0:
            continue
        stock = material_holding_for_circuit(state, circuit, dim) \
            if circuit else None
        if stock is None:
            mat_cover = 0.0
            break
        mat_cover = min(mat_cover, max(0.0, float(stock) / float(need)))
    # 劳务（工匠工时；与 `_settle_projects` 同源口径：可征用工时 = 工匠 size × 比例）
    labor_cover = 1.0
    if labor > 0:
        from content.data import PROJECT_LABOR_RATIO
        pops = p.get("pops") or {}
        artisan = pops.get("工匠") if isinstance(pops, dict) else None
        size = _finite_or_none(artisan.get("size")) if isinstance(artisan, dict) else None
        avail = (float(size) * float(PROJECT_LABOR_RATIO)) if size else 0.0
        labor_cover = max(0.0, min(1.0, avail / float(labor))) if labor > 0 else 1.0
    # 土地（`state.land["wasteland"]` 荒田 → 本路 `p["land"]` 在册田亩）
    land_cover = 1.0
    if land_mu > 0:
        land = getattr(state, "land", None)
        waste = _finite_or_none(land.get("wasteland")) if isinstance(land, dict) else None
        # 目标田亩读数缺失 ⇒ 无法做"转移"（否则会凭空增加在册田亩）⇒ 到位率 0
        target = _finite_or_none(p.get("land"))
        if target is None or waste is None:
            land_cover = 0.0
        else:
            land_cover = max(0.0, min(1.0, float(waste) / float(land_mu)))
    # 维护费（国库可支付额）
    upkeep_cover = 1.0
    if upkeep_i > 0:
        tre = _finite_or_none(getattr(state, "treasury", None))
        upkeep_cover = max(0.0, min(1.0, (tre or 0.0) / float(upkeep_i)))
    return {"material": mat_cover, "labor": labor_cover,
            "land": land_cover, "upkeep": upkeep_cover}


# =============================================================================
# 五、写入点：月度农业结算（增产落账 + 四项成本）
# =============================================================================

def _stat_add(state, key: str, value: float) -> None:
    """`state.statistics` 累加（既有容器，随档整表保存；旧档缺键按读数累加器处理）。"""
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        return
    stats[key] = float(stats.get(key, 0) or 0) + float(value)


def apply_agri_effects(state, log: Optional[list] = None, *,
                       month: Optional[int] = None) -> Dict[str, Any]:
    """月度农业结算：**先扣四项成本，再按收获月把增产的粮落进本路农 POP**。

    纪律：
      · **顺序**：土地 → 材料 → 劳务 → 维护费 → 增产；任一不足按最短板同比例降效；
      · **绝不先产后补账**：成本不到位时增产按比例缩，`applied_ratio` 与统计同步；
      · **只写** `state.land` / `state.resources` / `prefectures[路].pops["农"]["grain"]`
        / `state.statistics`；**从不写任何 POP 的 wealth / size**；
      · **不凭空**：材料只扣仓里有���、土地只划荒田、维护费只付国库有的。

    参数：
      · `month`：覆盖收获月判定（默认读 `state.month`）；测试可显式传入。
    返回本月汇总 dict（`grain_produced` / `upkeep_paid` / `land_cultivated` /
    `material_used` / `labor_hours` / `routes_with_effect` / `undefined_routes` /
    `harvest_month` / `lost_ratio`）。
    """
    logs = log if isinstance(log, list) else []
    if state is None:
        raise TypeError("state 不能为 None")
    prefs = getattr(state, "prefectures", None)
    if prefs is None:
        raise ValueError("state.prefectures 缺失（state 未初始化？）")
    if not isinstance(prefs, dict):
        raise TypeError(f"state.prefectures 应为 dict，得 {type(prefs).__name__}")

    m = month if month is not None else getattr(state, "month", None)
    mi = None if m is None else _finite_or_none(m)
    harvest = mi is not None and int(mi) in AGRI_HARVEST_MONTHS

    summary = {
        "harvest_month": harvest,
        "month": None if mi is None else int(mi),
        "grain_produced": 0,
        "upkeep_paid": 0,
        "land_cultivated": 0,
        "material_used": {},
        "labor_hours": 0.0,
        "routes_with_effect": 0,
        "undefined_routes": 0,
        "lost_ratio": 0.0,
        "routes": {},
    }

    from content.data import UPKEEP_PAY_TO

    land = getattr(state, "land", None)   # 建材已改走商人货栈（E-1），不再需要 res

    for route, p in prefs.items():
        if not isinstance(p, dict):
            summary["undefined_routes"] += 1
            continue
        eff = route_agri_effect(state, route)
        if not eff["defined"]:
            summary["undefined_routes"] += 1
            summary["routes"][route] = {"defined": False, "reason": eff["reason"]}
            logs.append(f"[农业] {route} 效果读数未定义（{eff['reason']}），本月不计产出")
            continue
        ratio = float(eff["applied_ratio"])
        sources = eff["sources"]
        summary["routes"][route] = {
            "defined": True, "sources": len(sources),
            "applied_ratio": ratio, "yield_mult": eff["yield_mult"],
            "unregistered": list(eff["unregistered"]),
        }
        if not sources or ratio <= 0:
            if sources and ratio <= 0:
                summary["lost_ratio"] += 1.0
                logs.append(f"[农业] {route} 成本全缺（到位率 0），本月无产出")
            continue

        # ---- 成本 1：土地（荒田 → 本路在册田亩，真实转移）----
        want_land = int(round(eff["land_mu"] * ratio))
        if want_land > 0:
            waste = _finite_or_none(land.get("wasteland")) if isinstance(land, dict) else None
            take = max(0, min(want_land, int(waste) if waste is not None else 0))
            if take > 0:
                land["wasteland"] = int(land["wasteland"]) - take
                p["land"] = int(p.get("land", 0) or 0) + take
                summary["land_cultivated"] += take
                _stat_add(state, "agri_land_cultivated", take)
                land_ratio = take / float(want_land)
                if land_ratio < 1.0:
                    ratio *= land_ratio

        # ---- 成本 2：材料（真扣物资仓；逐路竞争同一批料，先到先得）----
        # ⚠️ **回退（2026-11）**：曾试经 `material_market` 向商人真付货款
        # （B4-1 收窄版 B），同因未收敛而回退（见 tasks.md）。
        for dim, need in (eff["material"] or {}).items():
            if need <= 0:
                continue
            want = need * ratio
            if want <= 0:
                continue
            # 🔴 口径 C-c：从**本地州府仓**实扣（`consume_for_circuit` 与
            # `_coverage` 的判定**共用同一读口**，杜绝口径分叉）。
            from core.foundation.ledger.material_holding import consume_for_circuit
            take = consume_for_circuit(state, route, dim, int(round(want)))
            if take > 0:
                summary["material_used"][dim] = \
                    summary["material_used"].get(dim, 0.0) + take
                _stat_add(state, f"agri_material_used_{dim}", take)

        # ---- 成本 3：劳务（工匠工时；只记统计，**不改 POP size**）----
        want_labor = float(eff["labor_hours"]) * ratio
        used = 0.0
        if want_labor > 0:
            from content.data import PROJECT_LABOR_RATIO
            artisan = ((p.get("pops") or {}) or {}).get("工匠")
            size = _finite_or_none(artisan.get("size")) if isinstance(artisan, dict) else None
            avail = (float(size) * float(PROJECT_LABOR_RATIO)) if size else 0.0
            used = max(0.0, min(want_labor, avail))
            if used > 0:
                summary["labor_hours"] += used
                _stat_add(state, "agri_labor_hours", used)
            if used < want_labor:
                ratio *= (used / want_labor) if want_labor > 0 else 0.0
        used_labor = used

        # ---- 成本 4：维护费（国库 → 本路工匠/商人，既有路级守恒划转通道）----
        paid_this_route = 0
        want_upkeep = int(round(float(eff["upkeep_coin"]) * ratio))
        if want_upkeep > 0:
            paid_this_route = _pay_upkeep(state, route, want_upkeep, UPKEEP_PAY_TO)
            summary["upkeep_paid"] += paid_this_route
            if paid_this_route > 0:
                _stat_add(state, "agri_upkeep_paid", paid_this_route)
            if paid_this_route < want_upkeep:
                ratio *= (paid_this_route / want_upkeep) if want_upkeep > 0 else 0.0

        if ratio < 1.0:
            summary["lost_ratio"] += (1.0 - ratio)
            _stat_add(state, "agri_effect_lost_ratio", 1.0 - ratio)

        if ratio <= 0:
            continue

        # ---- 产出：收获月按 1/3 年增产落本路农 POP（非收获月不产粮）----
        extra = 0
        if harvest and eff["yield_mult"] > 0:
            extra = int(round(eff["annual_grain"] * float(eff["yield_mult"])
                              * ratio * AGRI_HARVEST_SHARE))
            if extra > 0:
                nong = p["pops"]["农"]
                if _grain_add(nong, extra, state) is None:
                    nong["grain"] = int(nong.get("grain", 0) or 0) + extra
                summary["grain_produced"] += extra
                _stat_add(state, "agri_grain_produced", extra)
        summary["routes_with_effect"] += 1
        if extra > 0 or eff["yield_mult"] > 0:
            logs.append(
                f"[农业] {route} 到位率 {ratio:.0%}：开垦 {want_land} 亩、"
                f"工时 {used_labor:.0f}、维护 {paid_this_route} 贯 "
                f"⇒ 增产 {extra} 石（{len(sources)} 项投资，增产率 "
                f"{float(eff['yield_mult']):.1%}）")

    summary["lost_ratio"] = round(float(summary["lost_ratio"]), 6)
    if summary["undefined_routes"]:
        _stat_add(state, "agri_undefined_routes", summary["undefined_routes"])
    return summary


def _pay_upkeep(state, route: str, want: int, shares: Dict[str, float]) -> int:
    """增量维护费：**路级**支付（国库 → 本路工匠/商人），返回实付额。

    走 `GameState.transfer_money`（`settlement_econ._settle_land_local` 一条鞭税同款
    路级划转通道，守恒、目标不可写即 0）：维护本路农田的是本路工/商，钱**不外流到
    无关的路**。按 `shares` 顺序把**余额**逐档切分，末档吃尾差；任一目标不可写
    或国库不足 ⇒ 该档少付，余额留国库（不销毁、不凭空），由 `applied_ratio` 体现降效。
    """
    if want <= 0:
        return 0
    tm = getattr(state, "transfer_money", None)
    if not callable(tm):
        return 0
    items = [(c, float(s)) for c, s in (shares or {}).items() if float(s) > 0]
    if not items:
        return 0
    paid = 0
    for i, (cls, share) in enumerate(items):
        remain_frac = sum(s for _, s in items[i:])
        if remain_frac <= 0:
            break
        v = int(round((want - paid) * (share / remain_frac)))
        if v <= 0:
            continue
        paid += int(tm("treasury", f"pop:{route}:{cls}", v) or 0)
    return max(0, min(paid, want))


# =============================================================================
# 六、钩子：损耗降低 / 运输瓶颈缓解（**由 Lead 决定是否接线**，本模块只算值）
# =============================================================================

def effective_spoil_rate(state, route: str, base_rate: Any) -> Optional[float]:
    """农存粮霉耗率钩子：`base_rate × (1 − 有效损耗降幅)`。

    供 `settlement_granary` 农储霉耗段消费（第 533-540 行 `FARMER_SPOIL_RATE` 处）。
    返回 `None` 表示**读数未定义**（route 非法/缺基数/未登记投资）——调用方须按
    "缺失"处理，**不得回落成原始 `base_rate` 或 0.0 假装无事**。
    """
    if base_rate is None:
        return None                      # 缺失：不给"原始值"，避免掩盖
    br = _finite_or_none(base_rate)
    if br is None or br < 0:
        return None
    eff = route_agri_effect(state, route)
    if not eff["defined"]:
        return None
    red = float(eff["loss_reduction"]) * float(eff["applied_ratio"])
    red = max(0.0, min(AGRI_LOSS_REDUCTION_CAP, red))
    return max(0.0, float(br) * (1.0 - red))


def effective_canal_block(state, base_block: Any = None) -> Optional[float]:
    """漕运瓶颈钩子：`max(0, base_block − 全国农业投资缓解量)`（单位：百分点）。

    `state.canal_block` 是**全国**淤塞度（0-100），故本钩子把**各路**农业投资的
    `transport_relief × 到位率` 汇总（封顶 `AGRI_TRANSPORT_RELIEF_CAP`）后抵扣。
    供 `settlement_granary` 漕运段消费（第 88 行 `canal_eff` 计算处）。

    返回 `None` 表示 `base_block`/读数缺失（调用方不得回落 0/1.0）。
    """
    bb = _finite_or_none(base_block) if base_block is not None \
        else _finite_or_none(getattr(state, "canal_block", None))
    if bb is None:
        return None
    relief = 0.0
    for route in (getattr(state, "prefectures", {}) or {}):
        eff = route_agri_effect(state, route)
        if not eff["defined"]:
            continue                      # 缺失路不贡献，也不伪装成 0 效果的路
        relief += float(eff["transport_relief"]) * float(eff["applied_ratio"])
    relief = max(0.0, min(AGRI_TRANSPORT_RELIEF_CAP, relief))
    return max(0.0, float(bb) - relief)
