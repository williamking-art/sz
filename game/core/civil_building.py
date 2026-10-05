# -*- coding: utf-8 -*-
"""宋祚 · 民间营造触发（规格 `market-civilian-economy` **B4-7**）。

> 本模块**尚未接线**到 `settlement.py`（由 Lead 统一接线）。建议接线位置见本文件的
> `WIRING_HINT` 常量与 `apply_civil_construction` 的 docstring。

## 一、要治的病（B4-7 原文）

> **B4-7** 民间营造触发：民居/商铺/货栈随人口、拥挤、损坏、经营扩张而建
> （**不做成"每回合每人建一次"**，§6.1）。

即：民居/商铺/货栈这类**民间建筑**应随四类动因**自发建造**，而不是只由玩家立项
（`state.projects`）或开局存量（`game_state._init_agri_buildings` 只配 `水利`/`常平仓`）
产生。此前"宋境民间造房"这条链**完全不存在**。

## 二、四类动因的判据与量级（全部**纯派生**，不改任何状态）

所有动因统一折算成 **"需要的建筑级数"**（fractional levels，1 级 = 一个营建批次），
这样四者**同量纲可加**，读数可直接比较"谁贡献大"。`pressure = Σ 四动因`，
`need_lv = min(level_cap, ceil(pressure))`。

| 动因 | 判据 | 量级公式 | 缺失语义 |
|---|---|---|---|
| **人口增长** `population` | 本路 **实有人口**（ΣPOP `size`，POP 挂载律）按月净自然增长率 `content.data.POP_GROWTH_RATE` 增量，增量人口需要新容量 | `pop × POP_GROWTH_RATE ÷ capacity_per_lv` | POP `size` 任一类读不到 ⇒ **undefined** |
| **拥挤** `crowding` | 现有人口超出「存量容量 × 拥挤容许比」的部分 | `max(0, pop − capacity × CROWDING_OCCUPANCY_LIMIT) ÷ capacity_per_lv`；`capacity == 0` 时即 `pop ÷ capacity_per_lv` | 同上 |
| **损坏** `decay` | 已建该建筑**满一个年久失修周期**（`decay_cycle_months`）即应重修一级；越老需要的重建级数越多（长年失修 ⇒ 近乎重建）。**不满一周期不欠账** | `age_months // decay_cycle_months`（整周期），钳到 `level_cap`；`lv ≤ 0` ⇒ `0.0`（**实测无房可坏**，不是缺失） | 该建筑条目读不到 `built_month` ⇒ **undefined**（不回落 0） |
| **经营扩张** `expansion` | 本路经营主体的财富已能支撑更多"铺/栈"，超出该建筑**现有等级**所能承载的部分 | `max(0, ⌊metric ÷ expansion_wealth_per_lv⌋ − current_lv)`，`metric` 取本路 POP `wealth`（既有槽位，不另立账本） | 该 POP `wealth` 读不到 ⇒ **undefined** |

- 每个建筑在注册表里**声明自己响应哪些动因**（`drivers`）；未声明者贡献 `0.0`
  且 `applicable=False`（例如货栈不居住人口 ⇒ 人口/拥挤对它无意义）。
- **不做成"每回合每人建一次"**：`pressure` 是**级数**而非人数，且每月
  **最多升 1 级**（`CIVIL_LEVELS_PER_MONTH`），另受 `level_cap`（Lv1-5 约定）与
  真实料/钱/工时到位率三者共同节流。
- ⚠️ **`need_lv` 的语义是「需要增建/重修的级数」，不是「目标总级数」**——
  四动因算出的都已是**相对现有存量**的缺口（拥挤减去存量容量、扩张减去现等级），
  因此判据是 `pressure ≥ CIVIL_TRIGGER_THRESHOLD`，**不得**再拿 `need_lv` 与
  `current_lv` 比较（会把已建存量重复计入，改建永远不发生）。

### 已知刻意的退化：Lv1-5 上限下的早期饱和

全路人口 ≈ 700 万，而项目约定建筑等级为 **Lv1-5**。若 `capacity_per_lv` 取
百万量级，则拥挤动因在开局数月内即把该建筑顶到 `level_cap`，此后
`decision="no_build" / reason="at_level_cap"`——这是**上限本身**的正确结果，
不是失效；读数仍逐项报告四动因贡献，便于面板显示"压力来源"。
要放宽只能由 Lead 调 `CIVIL_BUILDING_SPECS[*]["level_cap"]`。

## 三、消耗与落点（**建造必须真实消耗资源，禁止凭空造房**）

| 成本 | 落点 | 有无钱腿 |
|---|---|---|
| **料** | `state.resources[dim]["stock"]` **真扣**（`timber`/`stone`，B4-1 建材口径） | 无（B4-6 的「官仓领料」路径：同一主体内部调拨，只记 `base_material_cost` **基准估价**，不重复计价） |
| **钱（工钱）** | 本路出资阶层 `wealth` → **本路 `工匠` `wealth`**，经 `GameState.transfer_money` 路级守恒划转 | **有付款对手方**（工匠实收） |
| **工时** | 本路 `工匠 size × content.data.PROJECT_LABOR_RATIO`（与 `_settle_projects` 同源口径）；**只累加 `state.statistics["civil_labor_hours"]`** | — |

- **绝不新建人口**：全程不写任何 POP 的 `size`。
- **钱守恒**：只做 POP↔POP 划转 ⇒ `Σwealth + 国库 + 内帑` 恒定，**凭空建房必失败**
  （无钱即 `no_build/coin_short`）。
- **落点**：既有槽位 `prefectures[路]["buildings"][名称]`，**不另建建筑账本**：
  - 非岗位类建筑写 **`{"lv": n, "built_month": m}`**（结构写法，`built_month` 是
    该建筑**本级落成年月**的绝对月序，仅供损坏动因读龄；统一读口
    `core.building_jobs.building_level` 兼容标量与结构两种写法，
    `building_jobs.evolve_building_levels._set` 早已用同一写法）。
  - 岗位类建筑写**标量** `n`（与 `settlement_tech._settle_projects` 宋侧实际写法一致）。
  - **开局已有的 `水利`/`常平仓` 必须被容忍**：它们既不是本注册表的建筑、也不带
    `built_month`；本模块**只按注册表名枚举**，绝不做"遍历所有建筑"的隐含假设，
    也不假定 `buildings == {}`。

## 四、`undefined` 语义（拒绝式 · 缺失 ≠ 0 ≠ 1.0）

读数三态：

| `decision` | 含义 |
|---|---|
| `"build"` | 该建（已同时验证料/工时/钱到位） |
| `"no_build"` | **实测**不该建（无压力 / 等级封顶 / 缺料 / 缺工时 / 缺钱 / 岗位类未开闸） |
| `"undefined"` | **需求或代价依据读不到**（POP `size`/`wealth` 缺失、月序读不到、`built_month` 缺失、仓库存量读不到、造价基准价不可读、非法输入） |

- `undefined` 时**四动因值一律 `None`**（**不回落 0/1.0 假装无事**），并给 `reason`。
- 「料不足」「钱不足」「工时不足」是**实测事实**⇒ `no_build`，**不是** `undefined`；
  「仓里有没有这一维」读不到才是 `undefined`（否则"未知"会被当成"没有"）。
- 非法**注册表条目**（非有限值/负值/缺字段/通道矛盾）⇒ `raise CivilRegistryError`；
  非法**入参**（`state=None` / `pref` 非非空 str / 未知建筑名）⇒ `TypeError`/`ValueError`。

## 五、与岗位类建筑的关系（**重要**）

`content/data_constants.POP_BUILDING_TYPES = (农田, 自耕农庄, 地主农庄, 工坊, 商铺, 庄园)`
是**岗位类建筑**表：其成员进入 `core/building_jobs.SONG_JOBS_PER_LEVEL` 的岗位分配
（`商铺` = 每级 **40 个商人岗**），与 `allocate_employment` / `apply_employment_flow`
的就业基线联动。因此：

- 本模块默认自动触发的两项 —— **`民居`、`货栈` 是非岗位类**（不进岗位表、
  不改变就业基线、不触发空岗拉）；
- **`商铺` 作为岗位类登记，但默认不开闸**：`apply_civil_construction(allow_job_class=False)`
  时它只出读数（`no_build / job_class_opt_in_required`），**不写入**。
  由 Lead 显式传 `allow_job_class=True` 才落地，届时写**标量**等级
  （`estate_mechanic.pop_building_effect` 对 `POP_BUILDING_TYPES` 成员做 `int(lv)`，
  标量是唯一安全写法）。
- 注册表校验强制：`name ∈ POP_BUILDING_TYPES` ⇒ `job_class` 必须为 `True`
  （防止有人把岗位类建筑当非岗位类写进本模块而悄悄改了就业基线）；
  `job_class=True` ⇒ `write_form` 必须为 `"scalar"`。

## 六、已知建模缺口（本模块如实标注，未擅自修补）

1. **料只有官仓一条腿**：B4-1 `core/material_market.py` 尚未接线（tasks §9 状态表：
   "B4-1 接线被建模缺口阻塞"），故民间自建的料只能从 `state.resources` 直取，
   **没有货款腿**（等于民间免费取官仓料）。B4-1 接线后应改为
   `material_market.buy_material(..., buyer="pop")`（POP 自购、货款入卖方 `wealth`）。
2. **参数未做长局校准**：`capacity_per_lv` / `decay_cycle_months` /
   `expansion_wealth_per_lv` / 工价均为**参数待裁**（tasks §6「参数待裁」），
   量级按开局人口与财富（士绅 ~1.37e7 / 商人 ~2.28e6 / 工匠 ~1.14e6 贯每路）
   选取，**未做 60/240 月实测**；校准前不得据此宣称 B4 放行门通过。
3. 新增的 `民居`/`货栈` 会进入 `settlement_officialdom._settle_upkeep` 的
   资产折算（`POP_BUILDING_VALUE × level × ASSET_MAINTAIN_RATE`）——这是**既有通道**，
   不是本模块新建的账本；即"民间造房 ⇒ 后续月度维持费上升"。

## 七、口径单点

- 四动因算法只在 `route_civil_trigger` 一处；`apply_civil_construction` **不复制算法**，
  只负责"逐路逐建筑调用读数 → 决策为 `build` 时调用 `build_civil_building`"。
- 造价/单价口径全部来自 `core/construction_cost.base_material_cost`
  （B4-3 单一真源），本模块**不自行估价**。
- 工时口径复用 `content.data.PROJECT_LABOR_RATIO`，等级读口复用
  `core.building_jobs.building_level`，钱走 `GameState.transfer_money`。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "CIVIL_BUILDING_SPECS",
    "CIVIL_DRIVERS", "DRIVER_LABELS",
    "CIVIL_TRIGGER_THRESHOLD", "CIVIL_LEVELS_PER_MONTH", "CROWDING_OCCUPANCY_LIMIT",
    "CIVIL_STAT_KEYS", "CIVIL_MATERIAL_SOURCE", "CIVIL_WAGE_RECIPIENT",
    "CIVIL_BLOCKED_STAT",
    "CivilBuildingError", "CivilRegistryError",
    "register_civil_building", "resolve_civil_building",
    "abs_month_index", "route_civil_trigger", "route_civil_demand",
    "build_civil_building", "apply_civil_construction",
    "WIRING_HINT",
]

# =============================================================================
# 一、模块级常量
# =============================================================================

#: 四类动因（顺序即读数与日志展示顺序）。
CIVIL_DRIVERS = ("population", "crowding", "decay", "expansion")

#: 动因中文名（面板/日志）。
DRIVER_LABELS = {
    "population": "人口增长",
    "crowding": "拥挤",
    "decay": "损坏",
    "expansion": "经营扩张",
}

#: `pressure`（需要的级数）达到该阈值才判"该建"。1.0 = 至少缺一级。
CIVIL_TRIGGER_THRESHOLD = 1.0

#: **每月最多升几级**（§6.1「不做成每回合每人建一次」的硬节流）。
CIVIL_LEVELS_PER_MONTH = 1

#: 拥挤容许比：人口超过「存量容量 × 该系数」的部分才算拥挤。
CROWDING_OCCUPANCY_LIMIT = 1.0

#: 料源通道（**只有官仓直取一条腿**——B4-1 建材市场未接线，见 §六·1）。
CIVIL_MATERIAL_SOURCE = "warehouse_issue"

#: 工钱收款方：恒为**本路 `工匠`**（营造/修缮服务，与 `content.data.UPKEEP_PAY_TO`
#: 表达的"维护支出付给工匠/商人"同一主体；本模块是单笔工时、不分摊，故收款方唯一）。
CIVIL_WAGE_RECIPIENT = "工匠"

#: 🔴 **故意**引入的未知建材维度白名单（见注册校验处说明）。
#: 目前只用于验证「基准价缺失 ⇒ 读数为 `None`（未定义）」这条口径。
#: 新增前须确认：**不是**拼写错误。
UNKNOWN_MATERIAL_DIM_ALLOWLIST = frozenset({"未定价材"})

#: 建材**卖方**（B4-1 收窄版 B · 2026-11）：恒为**本路 `商人`**——
#: 建材由 `production_chain.BUILDING_MATERIAL_DIMS` 交付到商人 `goods`，
#: 本模块经 `material_market`（`carrier="pop"`）向其**真付货款**采购。
#: ⚠️ 买方必须避开本值：某些建筑（如 `商铺`）的 `payers[0]` 也是 `商人`，
#: 照用会构成 `material_market` 判定的**自购自卖**（`self_dealing`）而被拒。
CIVIL_MATERIAL_SELLER = "商人"

#: 阻断原因 → 统计键后缀（`civil_blocked_*`；旧档缺键按读数累加器处理）。
CIVIL_BLOCKED_STAT = {
    "material_short": "civil_blocked_material",
    "labor_short": "civil_blocked_labor",
    "coin_short": "civil_blocked_coin",
    "no_pressure": "civil_blocked_pressure",
    "at_level_cap": "civil_blocked_level_cap",
    "job_class_opt_in_required": "civil_blocked_job_class",
}

#: 统计键（全部落既有 `state.statistics`，随档整表保存；物料按维度另记）。
CIVIL_STAT_KEYS = (
    "civil_levels_built",            # 建成级数
    "civil_coin_paid",               # 工钱实付（贯）
    "civil_material_value",          # 基准估价（无货款腿，仅估值登记）
    "civil_labor_hours",             # 工时消耗
    "civil_undefined_routes",        # 读数未定义的路数（本月）
) + tuple(sorted(set(CIVIL_BLOCKED_STAT.values())))

#: 接线建议（只读常量，供 Lead 参考；**本模块不自行接线**）。
WIRING_HINT = (
    "建议接线位置：`settlement.py::run_monthly_settlement` 中，"
    "`_settle_workshops(state, log)` 之后、`_settle_upkeep(state, log)`（Step 3.9）之前，"
    "包在 try/except 里（与 Step 3.5.2 农业效果同款容错壳）。理由："
    "① 晚于 Step 4.4 `settle_production_chain` ⇒ 本月入仓的建材可当月用；"
    "② 晚于 Step 3 `_settle_economy` ⇒ 人口/阶层流动先于民间造房落账；"
    "③ **早于 `_settle_upkeep`** ⇒ 本月新造的民居/货栈当月即进资产维持费"
    "（`POP_BUILDING_VALUE × level`），不产生\"造完当月免维护\"的口径漏洞；"
    "④ 早于 Step 4.5 之后的粮市/财政步 ⇒ 同月即可反映为民间财富的流出。"
    "建议接线代码（3 行）："
    "  try:\n"
    "      from core.civil_building import apply_civil_construction\n"
    "      apply_civil_construction(state, log)\n"
    "  except Exception as _cb_e:  # noqa: BLE001 — 民间营造失败不阻断结算\n"
    "      log.append(f\"[营造][WARN] 民间营造触发结算失败：{_cb_e!r}\")"
)


# =============================================================================
# 二、注册表：民间建筑 → 动因响应与成本
# =============================================================================
# 字段：
#   label              中文名（面板/日志）
#   drivers            响应哪些动因（子集 of CIVIL_DRIVERS）；未列者贡献 0
#   job_class          是否为**岗位类**建筑（POP_BUILDING_TYPES 成员，与就业基线联动）
#   write_form         "dict" → `{"lv": n, "built_month": m}`；"scalar" → `n`
#   capacity_per_lv    每级可容人口（居住类；=0/缺省表示不居住）
#   stock_per_lv       每级材料用量（真扣 `state.resources[dim]["stock"]`）
#   labor_per_lv       每级工匠工时
#   wage_per_labor_hour 工价（贯/工时）
#   payers             出资阶层顺序（`wealth` → 本路 `工匠.wealth`，有付款对手方）
#   level_cap          等级上限（项目约定 Lv1-5）
#   decay_cycle_months 年久失修周期（月）：满一个周期即应重修一级
#   expansion_metric   经营扩张度量所在 POP 类（读其 `wealth`）；None = 本建筑不随扩张
#   expansion_wealth_per_lv 每级所需经营财富
CIVIL_BUILDING_SPECS: Dict[str, Dict[str, Any]] = {
    # ---- 非岗位类：默认自动触发，不改变就业基线 ----
    "民居": {
        "label": "民居", "drivers": ("population", "crowding", "decay"),
        "job_class": False, "write_form": "dict",
        # 一级 = 一个营建批次（一坊/一厢）。**Lv5 应能覆盖该路开局人口**，
        # 否则"拥挤"指标会**永久为红且玩家无计可施**（违反 UI 可解释性：
        # 玩家无法回答"为什么办不动"——因为根本办不动）。
        # 实测（2026-11 校准）：该路开局人口≈693 万且 240 月内**下降**（至 ≈481 万），
        # 故 Lv5 容量取 750 万 > 693 万 ⇒ 拥挤信号**可响应**：
        # 人口增长时转红、建房后转绿，而不是钉死为红。
        # 建成Lv5 之后的循环由**损坏重修**（decay_cycle_months）与
        # `settlement_tech` 的玩家工程接棒，不靠"永远不够住"驱动。
        "capacity_per_lv": 1_500_000,
        "stock_per_lv": {"木": 120, "石": 40},
        "labor_per_lv": 4_000.0, "wage_per_labor_hour": 1.5,
        "payers": ("士绅", "商人", "工匠", "农"),
        "level_cap": 5, "decay_cycle_months": 120,
        "expansion_metric": None, "expansion_wealth_per_lv": 0.0,
        "note": "居住类：随人口增长与拥挤新建，随年久失修重修；不随经营扩张。",
    },
    "货栈": {
        "label": "货栈", "drivers": ("expansion", "decay"),
        "job_class": False, "write_form": "dict",
        "capacity_per_lv": 0,          # 货栈不居住人口 ⇒ 人口/拥挤动因对其不适用
        "stock_per_lv": {"木": 150, "石": 60},
        "labor_per_lv": 3_000.0, "wage_per_labor_hour": 1.5,
        "payers": ("商人", "士绅", "工匠", "农"),
        "level_cap": 5, "decay_cycle_months": 96,
        "expansion_metric": "商人", "expansion_wealth_per_lv": 1_800_000,
        "note": "货运类：随本路商人财富（经营扩张）增建，随年久失修重修；不居住人口。",
    },
    # ---- 岗位类：登记但默认不开闸（见 §五）----
    "商铺": {
        "label": "商铺", "drivers": ("expansion",),
        "job_class": True, "write_form": "scalar",
        # 商铺是 `POP_BUILDING_TYPES` 成员 = `SONG_JOBS_PER_LEVEL["商铺"] = {"商人": 40}`
        # ⇒ 每级 40 个商人岗，会改 `allocate_employment` / `apply_employment_flow` 的
        # **就业基线**。故默认 `allow_job_class=False`，只出读数不写入；
        # 由 Lead 显式开闸，且只能写标量等级（`pop_building_effect` 做 `int(lv)`）。
        "capacity_per_lv": 0,
        "stock_per_lv": {"木": 80, "石": 20},
        "labor_per_lv": 2_000.0, "wage_per_labor_hour": 1.5,
        "payers": ("商人", "士绅", "工匠"),
        "level_cap": 5, "decay_cycle_months": 120,
        "expansion_metric": "商人", "expansion_wealth_per_lv": 1_200_000,
        "note": "⚠️ 岗位类（每级 40 商人岗）：默认不开闸，开闸即改就业基线。",
    },
}


class CivilBuildingError(ValueError):
    """民间营造入参/口径非法。**拒绝式**：不静默兜底。"""


class CivilRegistryError(CivilBuildingError):
    """注册表条目非法（缺字段/负值/非有限值/通道矛盾/岗位类标记冲突）。"""


# =============================================================================
# 三、注册表访问
# =============================================================================

def _pop_building_types() -> tuple:
    """`POP_BUILDING_TYPES`（岗位类建筑权威表）——惰性取，避免模块级 import 环。"""
    from content.data_constants import POP_BUILDING_TYPES
    return tuple(POP_BUILDING_TYPES)


def _num(value: Any, field: str, key: str) -> float:
    """注册表数值校验：**拒绝式**。非有限/负数/非数值 ⇒ raise。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CivilRegistryError(
            f"CIVIL_BUILDING_SPECS[{key!r}].{field} 必须是数值，得 {value!r}")
    v = float(value)
    if not math.isfinite(v):
        raise CivilRegistryError(
            f"CIVIL_BUILDING_SPECS[{key!r}].{field} 非有限值 {value!r}"
            f"（不得回落 0/1.0）")
    if v < 0:
        raise CivilRegistryError(f"CIVIL_BUILDING_SPECS[{key!r}].{field} 为负 {value!r}")
    return v


def _validate_spec(key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise CivilRegistryError(f"注册表条目 {key!r} 必须是 dict")
    drivers = entry.get("drivers")
    if not isinstance(drivers, (tuple, list)) or not drivers:
        raise CivilRegistryError(f"注册表条目 {key!r} 缺 drivers")
    for d in drivers:
        if d not in CIVIL_DRIVERS:
            raise CivilRegistryError(f"注册表条目 {key!r} 含未知动因 {d!r}")

    cap = _num(entry.get("level_cap", 0), "level_cap", key)
    if cap < 1:
        raise CivilRegistryError(
            f"注册表条目 {key!r} 的 level_cap={cap} 须 ≥1（等级是非负整数口径）")
    entry["level_cap"] = int(cap)

    _num(entry.get("capacity_per_lv", 0), "capacity_per_lv", key)
    _num(entry.get("labor_per_lv", 0), "labor_per_lv", key)
    _num(entry.get("wage_per_labor_hour", 0), "wage_per_labor_hour", key)
    if ("population" in drivers or "crowding" in drivers) \
            and float(entry.get("capacity_per_lv", 0) or 0) <= 0:
        raise CivilRegistryError(
            f"注册表条目 {key!r} 响应人口/拥挤却 capacity_per_lv ≤ 0"
            f"（无容量口径 ⇒ 判据不可定义，**不得回落 0**）")

    stock = entry.get("stock_per_lv") or {}
    if not isinstance(stock, dict):
        raise CivilRegistryError(f"注册表条目 {key!r} 的 stock_per_lv 必须是 dict")
    for dim, q in stock.items():
        if not isinstance(dim, str) or not dim:
            raise CivilRegistryError(f"注册表条目 {key!r} 的材料维度非法 {dim!r}")
        # 🔴 配置里的维度名**必须**取自 `material_holding.MATERIAL_DIMS`。
        # 配置表自然要写维度名（那是数据不是算法），但**拼错必须报错**，
        # 否则该建筑会永远走"缺料"分支而**静默失效**。
        #
        # ⚠️ **例外**：`UNKNOWN_MATERIAL_DIM_ALLOWLIST` 里显式登记的维度
        # （如测试用的 `未定价材`，用于验证"基准价缺失 ⇒ 读数未定义"口径）
        # **不在此拦**——那不是拼写错误，而是**故意**引入的未知维度。
        # ⇒ 拦"疑似拼错"，不拦"明知故犯"，两者语义不同。
        from core.material_holding import MATERIAL_DIMS
        if dim not in MATERIAL_DIMS and dim not in UNKNOWN_MATERIAL_DIM_ALLOWLIST:
            raise CivilRegistryError(
                f"注册表条目 {key!r} 的材料维度 {dim!r} 不在 MATERIAL_DIMS "
                f"{MATERIAL_DIMS} 内（建材口径 E-1；`粮` 等请走 pops[].grain）。"
                f"若确为故意引入的未知维度，请登记进 UNKNOWN_MATERIAL_DIM_ALLOWLIST")
        _num(q, f"stock_per_lv[{dim}]", key)
    if not stock:
        raise CivilRegistryError(
            f"注册表条目 {key!r} 无材料用量（零料造房 = 凭空造房，**禁止**）")

    payers = entry.get("payers")
    if not isinstance(payers, (tuple, list)) or not payers:
        raise CivilRegistryError(
            f"注册表条目 {key!r} 缺 payers（钱必须有付款对手方，不得凭空出资）")
    for c in payers:
        if not isinstance(c, str) or not c:
            raise CivilRegistryError(f"注册表条目 {key!r} 的出资阶层非法 {c!r}")

    if "decay" in drivers:
        cycle = _num(entry.get("decay_cycle_months", 0), "decay_cycle_months", key)
        if cycle <= 0:
            raise CivilRegistryError(
                f"注册表条目 {key!r} 响应损坏却 decay_cycle_months ≤ 0"
                f"（无周期 ⇒ 年限不可判定）")
        entry["decay_cycle_months"] = int(cycle)
    if "expansion" in drivers:
        metric = entry.get("expansion_metric")
        if not isinstance(metric, str) or not metric:
            raise CivilRegistryError(
                f"注册表条目 {key!r} 响应经营扩张却缺 expansion_metric"
                f"（无度量 ⇒ **不得臆造归属**）")
        per_lv = _num(entry.get("expansion_wealth_per_lv", 0),
                      "expansion_wealth_per_lv", key)
        if per_lv <= 0:
            raise CivilRegistryError(
                f"注册表条目 {key!r} 的 expansion_wealth_per_lv ≤ 0")

    # ---- 岗位类纪律（§五）：与 `POP_BUILDING_TYPES` 必须一致 ----
    job_class = entry.get("job_class", False)
    if not isinstance(job_class, bool):
        raise CivilRegistryError(f"注册表条目 {key!r} 的 job_class 必须是 bool")
    is_pop_building = key in _pop_building_types()
    if is_pop_building and not job_class:
        raise CivilRegistryError(
            f"注册表条目 {key!r} 属 POP_BUILDING_TYPES（岗位类，与 "
            f"`building_jobs.SONG_JOBS_PER_LEVEL` 岗位基线联动）却标 job_class=False"
            f"——会静默改就业基线，**必须**显式标 True")
    form = entry.get("write_form", "dict")
    if form not in ("dict", "scalar"):
        raise CivilRegistryError(
            f"注册表条目 {key!r} 的 write_form={form!r} 非法（dict/scalar）")
    if job_class and form != "scalar":
        raise CivilRegistryError(
            f"注册表条目 {key!r} 是岗位类却声明 write_form={form!r}——"
            f"`estate_mechanic.pop_building_effect` 对 POP_BUILDING_TYPES 成员做 "
            f"`int(lv)`，结构写法会 TypeError；岗位类**只能写标量**")
    return entry


def register_civil_building(key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """动态登记一种民间建筑。

    非法条目**拒绝并抛 `CivilRegistryError`**（缺字段/负值/非有限值/动因矛盾/
    岗位类标记与 `POP_BUILDING_TYPES` 冲突/岗位类非标量写法），不静默写入半个条目。
    成功返回登记后的条目（同一对象）。
    """
    if not isinstance(key, str) or not key.strip():
        raise CivilRegistryError(f"注册键非法：{key!r}")
    entry = _validate_spec(key, entry)
    CIVIL_BUILDING_SPECS[key] = entry
    return entry


def resolve_civil_building(key: Any) -> Optional[Dict[str, Any]]:
    """建筑名 → 注册条目；未注册返回 `None`（调用方须拒绝，**不得兜底成中性规格**）。"""
    if not isinstance(key, str) or not key:
        return None
    return CIVIL_BUILDING_SPECS.get(key)


# =============================================================================
# 四、读数辅助
# =============================================================================

def _finite(v: Any) -> Optional[float]:
    """有限数值或 `None`（`bool`/`NaN`/`inf`/非数值一律 `None`）。"""
    if v is None or isinstance(v, bool):
        return None
    if not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _ge0(v: Any) -> Optional[float]:
    """非负有限数值或 `None`（负值 ⇒ 读数非法 ⇒ 走 `undefined`）。"""
    f = _finite(v)
    if f is None or f < 0:
        return None
    return f


def abs_month_index(state: Any, month: Optional[int] = None) -> Optional[int]:
    """绝对月序 = `year × 12 + month`（自增、跨年连续，**不需要开局锚点**）。

    读写两端用同一公式 ⇒ `built_month` 与"当月"永远同量纲。
    `year`/`month` 读不到（或非有限）⇒ `None`（调用方判 `undefined`，**不回落 0**）。
    """
    if month is not None:
        m = _finite(month)
        return None if m is None else int(m)
    y = _finite(getattr(state, "year", None))
    mo = _finite(getattr(state, "month", None))
    if y is None or mo is None:
        return None
    return int(y) * 12 + int(mo)


def _pop_total(p: Dict[str, Any]) -> Tuple[Optional[float], List[str]]:
    """本路**实有人口** = ΣPOP `size`（POP 挂载律：不另立人口账本）。

    任一 POP 的 `size` 缺失/非有限/负 ⇒ 返回 `(None, missing)`，调用方判 `undefined`。
    """
    pops = p.get("pops")
    if not isinstance(pops, dict) or not pops:
        return None, ["pops_missing"]
    total = 0.0
    missing: List[str] = []
    for cls, pop in sorted(pops.items()):
        if not isinstance(pop, dict):
            missing.append(f"pop:{cls}:malformed")
            continue
        sz = _ge0(pop.get("size"))
        if sz is None:
            missing.append(f"pop:{cls}:size_missing")
            continue
        total += sz
    if missing:
        return None, missing
    return total, []


def _labor_capacity(p: Dict[str, Any]) -> Tuple[Optional[float], List[str]]:
    """本路可征用**工匠工时** = `工匠 size × PROJECT_LABOR_RATIO`（与 `_settle_projects` 同源）。"""
    from content.data import PROJECT_LABOR_RATIO
    pops = p.get("pops")
    artisan = (pops or {}).get("工匠") if isinstance(pops, dict) else None
    if not isinstance(artisan, dict):
        return None, ["pop:工匠:missing"]
    sz = _ge0(artisan.get("size"))
    if sz is None:
        return None, ["pop:工匠:size_missing"]
    return float(sz) * float(PROJECT_LABOR_RATIO), []


_TRIGGER_KEYS = (
    "pref", "building", "defined", "decision", "reason", "drivers",
    "driver_basis", "applicable", "pressure", "need_lv", "current_lv",
    "level_cap", "at_level_cap", "population", "capacity", "occupancy",
    "job_class", "job_class_opt_in", "cost", "afford", "missing",
)


def _undefined(pref: Any, building: Any, reason: str,
               missing: Optional[List[str]] = None,
               extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """未定义读数：四动因与所有代价值一律 `None`（**不回落 0/1.0**）。"""
    out: Dict[str, Any] = {k: None for k in _TRIGGER_KEYS}
    out.update({
        "pref": pref if isinstance(pref, str) else None,
        "building": building if isinstance(building, str) else None,
        "defined": False,
        "decision": "undefined",
        "reason": reason,
        "drivers": {d: None for d in CIVIL_DRIVERS},
        "driver_basis": {d: "读数未定义，不估算" for d in CIVIL_DRIVERS},
        "applicable": {d: False for d in CIVIL_DRIVERS},
        "at_level_cap": False,
        "job_class_opt_in": False,
        "cost": {k: None for k in ("base_material_value", "wage", "materials",
                                   "labor_hours", "unresolved", "missing_price")},
        "afford": {},
        "missing": list(missing or []),
    })
    if extra:
        out.update(extra)
    return out


# =============================================================================
# 五、读数：某路某民间建筑的营造触发（纯派生，不写任何状态）
# =============================================================================

def route_civil_trigger(state, pref: str, building: str, *,
                        month: Optional[int] = None,
                        allow_job_class: bool = False,
                        labor_used: float = 0.0) -> Dict[str, Any]:
    """某路某民间建筑**该不该建**的纯读数（三态：`build` / `no_build` / `undefined`）。

    参数：
      · `month`：覆盖绝对月序（测试用；默认由 `year`/`month` 派生）。
      · `allow_job_class`：是否允许写入**岗位类**建筑（默认 `False`，见 §五）。
      · `labor_used`：本月该路**已**消耗的工时（同月多建筑共用工时池）。

    非法入参（`state=None` / `pref` 非非空 str / `building` 未注册）⇒ `TypeError`/`ValueError`。
    """
    if state is None:
        raise TypeError("state 不能为 None")
    if not isinstance(pref, str) or not pref:
        raise ValueError(f"pref 必须是非空 str（收到 {pref!r}）")
    if not isinstance(building, str) or not building:
        raise ValueError(f"building 必须是非空 str（收到 {building!r}）")
    spec = resolve_civil_building(building)
    if spec is None:
        raise ValueError(
            f"民间建筑 {building!r} 未在 CIVIL_BUILDING_SPECS 登记"
            f"（**不得兜底成中性规格**）")
    prefs = getattr(state, "prefectures", None)
    if prefs is None:
        raise ValueError("state.prefectures 缺失（state 未初始化？）")
    if not isinstance(prefs, dict):
        raise TypeError(f"state.prefectures 应为 dict，得 {type(prefs).__name__}")

    p = prefs.get(pref)
    if not isinstance(p, dict):
        return _undefined(pref, building, "unknown_pref",
                          missing=[f"pref:{pref}:not_in_state.prefectures"],
                          extra={"level_cap": int(spec["level_cap"]),
                                 "job_class": bool(spec.get("job_class"))})

    job_class = bool(spec.get("job_class"))
    opt_in = bool(allow_job_class)
    # 等级统一读口（兼容标量 / {"lv": n} 两种既存写法；保留 0=裁撤）
    from core.building_jobs import building_level as _bld_lv
    buildings = p.get("buildings")
    if buildings is None:
        # **缺失 ≠ 空**：没有 `buildings` 键不等于"该路没有房"，
        # 而等于"读不到存量"⇒ 判 undefined（否则会把未知当成 0 而凭空造房/覆盖）。
        return _undefined(pref, building, "route_buildings_missing",
                          missing=["route_buildings_missing"],
                          extra={"level_cap": int(spec["level_cap"]),
                                 "job_class": bool(spec.get("job_class"))})
    if not isinstance(buildings, dict):
        return _undefined(pref, building, "route_buildings_malformed",
                          missing=["route_buildings_malformed"],
                          extra={"level_cap": int(spec["level_cap"]),
                                 "job_class": bool(spec.get("job_class"))})
    missing_b: List[str] = []
    cur_lv = _bld_lv(buildings.get(building), 0)
    level_cap = int(spec["level_cap"])
    drivers = tuple(spec["drivers"])

    # ---- 读数 1：人口（POP 挂载律：ΣPOP size）----
    pop_now, pop_missing = _pop_total(p)
    if pop_now is None:
        return _undefined(pref, building, "population_missing",
                          missing=missing_b + pop_missing,
                          extra={"current_lv": cur_lv, "level_cap": level_cap,
                                 "job_class": job_class})

    # ---- 读数 2：绝对月序（损坏动因的年限依据）----
    now = abs_month_index(state, month)
    decay_applies = "decay" in drivers
    if decay_applies and now is None:
        return _undefined(pref, building, "month_counter_missing",
                          missing=missing_b + ["year_or_month_missing"],
                          extra={"current_lv": cur_lv, "level_cap": level_cap,
                                 "population": pop_now, "job_class": job_class})

    # ---- 四动因（单位：需要的级数；不适用者 0.0 且 applicable=False）----
    cap_per_lv = float(spec.get("capacity_per_lv", 0) or 0)
    capacity = float(cur_lv) * cap_per_lv if cap_per_lv > 0 else 0.0
    values: Dict[str, float] = {}
    basis: Dict[str, str] = {}
    applicable: Dict[str, bool] = {}

    # ① 人口增长：本月人口净增量需要的容量
    if "population" in drivers:
        from content.data import POP_GROWTH_RATE
        growth = pop_now * float(POP_GROWTH_RATE)
        values["population"] = growth / cap_per_lv
        basis["population"] = (
            f"实有人口 {int(pop_now):,} × 月增长率 {float(POP_GROWTH_RATE):.4%} "
            f"= 新增 {int(growth):,} 口 ÷ 每级容量 {int(cap_per_lv):,}")
        applicable["population"] = True
    else:
        values["population"] = 0.0
        basis["population"] = "本建筑不响应人口增长"
        applicable["population"] = False

    # ② 拥挤：超出「存量容量 × 容许比」的部分
    if "crowding" in drivers:
        over = pop_now - capacity * CROWDING_OCCUPANCY_LIMIT
        values["crowding"] = max(0.0, over) / cap_per_lv
        occ = (pop_now / capacity) if capacity > 0 else None
        basis["crowding"] = (
            f"实有人口 {int(pop_now):,} vs 存量容量 {int(capacity):,} "
            f"（占用率 {'无存量' if occ is None else f'{occ:.2f}'}，容许比 "
            f"{CROWDING_OCCUPANCY_LIMIT:.2f}）")
        applicable["crowding"] = True
    else:
        values["crowding"] = 0.0
        basis["crowding"] = "本建筑不响应拥挤"
        applicable["crowding"] = False

    # ③ 损坏：满一个失修周期即需重修一级（越老需要的重建级数越多）
    if "decay" in drivers:
        entry = (buildings or {}).get(building)
        if cur_lv <= 0:
            values["decay"] = 0.0
            basis["decay"] = "本路尚无该建筑（实测无可损坏存量）"
        else:
            built = entry.get("built_month") if isinstance(entry, dict) else None
            b = _finite(built)
            if b is None:
                return _undefined(
                    pref, building, "decay_age_missing",
                    missing=missing_b + [f"building:{building}:built_month_missing"],
                    extra={"current_lv": cur_lv, "level_cap": level_cap,
                           "population": pop_now, "job_class": job_class})
            age = now - int(b)
            if age < 0:
                return _undefined(
                    pref, building, "decay_age_invalid",
                    missing=missing_b + [f"building:{building}:built_month_invalid"],
                    extra={"current_lv": cur_lv, "level_cap": level_cap,
                           "population": pop_now, "job_class": job_class})
            cycle = int(spec["decay_cycle_months"])
            # 「满一个失修周期才需重修一级」⇒ 用**整周期**（floor），不满一周期不欠账
            need = (age // cycle) if age > 0 else 0
            values["decay"] = float(min(need, level_cap))
            basis["decay"] = (f"现存 Lv{cur_lv}，已历 {age} 月"
                              f"（失修周期 {cycle} 月）⇒ 需重修 {values['decay']:.0f} 级")
        applicable["decay"] = True
    else:
        values["decay"] = 0.0
        basis["decay"] = "本建筑不响应损坏"
        applicable["decay"] = False

    # ④ 经营扩张：经营财富可支撑的级数 − 该建筑现有等级
    if "expansion" in drivers:
        metric_cls = str(spec["expansion_metric"])
        pops = p.get("pops")
        holder = (pops or {}).get(metric_cls) if isinstance(pops, dict) else None
        metric = _ge0(holder.get("wealth")) if isinstance(holder, dict) else None
        if metric is None:
            return _undefined(
                pref, building, "expansion_metric_unknown",
                missing=missing_b + [f"pop:{metric_cls}:wealth_missing"],
                extra={"current_lv": cur_lv, "level_cap": level_cap,
                       "population": pop_now, "job_class": job_class})
        per_lv = float(spec["expansion_wealth_per_lv"])
        supported = int(metric // per_lv)
        values["expansion"] = float(max(0, supported - cur_lv))
        basis["expansion"] = (f"本路 {metric_cls} 财富 {int(metric):,} 贯 ÷ "
                              f"每级 {int(per_lv):,} 贯 = 可支撑 {supported} 级，"
                              f"现存 {cur_lv} 级 ⇒ 缺 {values['expansion']:.0f} 级")
        applicable["expansion"] = True
    else:
        values["expansion"] = 0.0
        basis["expansion"] = "本建筑不响应经营扩张"
        applicable["expansion"] = False

    # 逐动因钳到 `level_cap`（**单项动因不能要求超过等级上限的级数**），
    # 钳后的值即为**该动因实际的贡献**，故 `pressure == Σ drivers` 恒成立。
    for d in CIVIL_DRIVERS:
        raw = float(values.get(d, 0.0))
        clamped = max(0.0, min(float(level_cap), raw))
        if raw > level_cap:
            basis[d] += f"（算得 {raw:.2f} 级，超等级上限，钳到 {level_cap} 级）"
        values[d] = clamped
    pressure = sum(values[d] for d in CIVIL_DRIVERS)
    # `need_lv` = **需要增建/重修的级数**（各动因已是"相对现有存量的缺口"，
    # **不含**现有等级；故判定是 `pressure ≥ 阈值`，**不是** `need_lv > cur_lv`，
    # 否则会把已建存量重复计入而让改建永远不发生）。
    need_lv = min(level_cap, int(math.ceil(pressure - 1e-9)))

    # ---- 读数 3：造价（B4-3 单一真源 `base_material_cost`）----
    from core.construction_cost import base_material_cost
    materials = {d: float(q) for d, q in (spec.get("stock_per_lv") or {}).items()}
    cost = base_material_cost(materials=materials, state=state)
    labor_hours = float(spec.get("labor_per_lv", 0) or 0)
    wage = int(round(labor_hours * float(spec.get("wage_per_labor_hour", 0) or 0)))
    cost_view = {
        "base_material_value": None if cost["unresolved"] else round(cost["total"], 4),
        "wage": wage,
        "materials": {d: int(round(q)) for d, q in materials.items()},
        "labor_hours": round(labor_hours, 4),
        "unresolved": bool(cost["unresolved"]),
        "missing_price": list(cost["missing_price"]),
    }
    if cost["unresolved"]:
        # 基准价不可读 ⇒ 造价不可判定（`base_material_cost` 明确"不按 0 计价"）
        # ⇒ 缺失 ≠ 0 ⇒ 判 undefined，不回落成"造价 0 的免费房"。
        return _undefined(pref, building, "material_price_unresolved",
                          missing=missing_b + [f"price_missing:{d}" for d in cost["missing_price"]],
                          extra={"current_lv": cur_lv, "level_cap": level_cap,
                                 "population": pop_now, "capacity": capacity,
                                 "driver_basis": basis, "applicable": applicable,
                                 "job_class": job_class, "cost": cost_view})

    # ---- 读数 4：三项支付能力（**先判"读不到"，再判"不够"**）----
    res = getattr(state, "resources", None)
    material_short: Dict[str, float] = {}
    unknown: List[str] = []
    for dim, need_q in materials.items():
        slot = (res or {}).get(dim) if isinstance(res, dict) else None
        stock = _ge0(slot.get("stock")) if isinstance(slot, dict) else None
        if stock is None:
            unknown.append(f"resource:{dim}:stock_unknown")
            continue
        if stock < need_q:
            material_short[dim] = need_q - stock
    labor_avail, labor_missing = _labor_capacity(p)
    if labor_avail is None:
        unknown.extend(labor_missing)
    remaining_labor = None if labor_avail is None else max(0.0, labor_avail - float(labor_used))
    payer_pool = 0
    payer_unknown: List[str] = []
    pops = p.get("pops")
    for cls in spec["payers"]:
        holder = (pops or {}).get(cls) if isinstance(pops, dict) else None
        w = _ge0(holder.get("wealth")) if isinstance(holder, dict) else None
        if w is None:
            payer_unknown.append(f"pop:{cls}:wealth_unknown")
            continue
        payer_pool += int(w)

    if unknown or payer_unknown:
        return _undefined(
            pref, building,
            "material_stock_unknown" if unknown else "payer_wealth_unknown",
            missing=missing_b + unknown + payer_unknown,
            extra={"current_lv": cur_lv, "level_cap": level_cap,
                   "population": pop_now, "capacity": capacity,
                   "driver_basis": basis, "applicable": applicable,
                   "job_class": job_class, "cost": cost_view})

    labor_short = None if remaining_labor is None else max(0.0, labor_hours - remaining_labor)
    coin_short = max(0, wage - payer_pool)
    # 🔴 归属待定（6.33）：**只读单列**，**不并入** `material_short` ——
    # 下一行 `not material_short` 会决定 `no_build`（L841），若把待定料算进去
    # 就等于让「归属未定」的料**触发立项采购**，违反 6.33「不得采购/投料」。
    # 本字段仅用于向玩家**解释**「为什么缺料」：料其实在，只是货主未定。
    _pend_unavail: Dict[str, int] = {}
    _ps_all = getattr(state, "pending_stock", None)
    if isinstance(_ps_all, dict):
        for _slot_all in _ps_all.values():
            if not isinstance(_slot_all, dict):
                continue
            for _d_all, _e_all in _slot_all.items():
                if not isinstance(_e_all, dict):
                    continue
                if _e_all.get("owner_status") == "已确权":
                    continue
                if _d_all in materials:
                    _pend_unavail[_d_all] = _pend_unavail.get(_d_all, 0) + int(_e_all.get("qty", 0) or 0)
    afford = {
        "materials_ok": not material_short,
        "material_short": {d: round(v, 4) for d, v in material_short.items()},
        # 6.33：单列「有量但归属待定、不可用」的料（**不参与任何判定**）
        "pending_unavailable": dict(_pend_unavail),
        "labor_ok": labor_short <= 0,
        "labor_available": None if remaining_labor is None else round(remaining_labor, 4),
        "labor_short": None if labor_short is None else round(labor_short, 4),
        "money_ok": coin_short <= 0,
        "wage": wage,
        "payer_pool": payer_pool,
        "coin_short": coin_short,
        "material_source": CIVIL_MATERIAL_SOURCE,
        "labor_consumed_by_others": round(float(labor_used), 4),
    }

    at_cap = cur_lv >= level_cap
    occ = (pop_now / capacity) if capacity > 0 else None
    common = {
        "pref": pref, "building": building, "defined": True, "reason": "",
        "drivers": {k: round(float(v), 4) for k, v in values.items()},
        "driver_basis": basis, "applicable": applicable,
        "pressure": round(pressure, 4), "need_lv": need_lv,
        "current_lv": cur_lv, "level_cap": level_cap, "at_level_cap": at_cap,
        "population": int(pop_now), "capacity": int(capacity), "occupancy": occ,
        "job_class": job_class, "job_class_opt_in": opt_in,
        "cost": cost_view, "afford": afford, "missing": list(missing_b),
    }

    # ---- 决策（优先级：封顶 > 无压力 > 岗位类未开闸 > 缺料 > 缺工时 > 缺钱）----
    if at_cap:
        return {**common, "decision": "no_build", "reason": "at_level_cap"}
    if pressure < CIVIL_TRIGGER_THRESHOLD:
        # `pressure` 已是「相对现有存量的缺口级数」，**不再与 cur_lv 比较**
        # （否则已建存量会被重复计入，改建永远不发生）。
        return {**common, "decision": "no_build", "reason": "no_pressure"}
    if job_class and not opt_in:
        return {**common, "decision": "no_build", "reason": "job_class_opt_in_required"}
    if material_short:
        return {**common, "decision": "no_build", "reason": "material_short"}
    if labor_short and labor_short > 0:
        return {**common, "decision": "no_build", "reason": "labor_short"}
    if coin_short > 0:
        return {**common, "decision": "no_build", "reason": "coin_short"}
    return {**common, "decision": "build", "reason": "pressure"}


def route_civil_demand(state, pref: str, *, month: Optional[int] = None,
                       allow_job_class: bool = False) -> Dict[str, Any]:
    """一路全部已登记民间建筑的触发读数（**纯读数，不写任何状态**）。

    返回 `{pref, defined, buildings: {名: 触发读数}, undefined: [名], reason}`；
    某建筑 `undefined` 不影响其它建筑（**逐项隔离**，不整体回滚）。
    """
    if state is None:
        raise TypeError("state 不能为 None")
    if not isinstance(pref, str) or not pref:
        raise ValueError(f"pref 必须是非空 str（收到 {pref!r}）")
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        raise TypeError(f"state.prefectures 应为 dict，得 {type(prefs).__name__}")
    out: Dict[str, Any] = {"pref": pref, "defined": False, "reason": "",
                           "buildings": {}, "undefined": []}
    if not isinstance(prefs.get(pref), dict):
        out["reason"] = "unknown_pref"
        return out
    for name in CIVIL_BUILDING_SPECS:
        t = route_civil_trigger(state, pref, name, month=month,
                                allow_job_class=allow_job_class)
        out["buildings"][name] = t
        if not t["defined"]:
            out["undefined"].append(name)
    out["defined"] = True
    return out


# =============================================================================
# 六、写入点：真实消耗（钱/料/工时）后才落地建筑
# =============================================================================

def _stat_add(state, key: str, value: float) -> None:
    """`state.statistics` 累加（既有容器，随档整表保存；旧档缺键按读数累加器处理）。"""
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        return
    stats[key] = float(stats.get(key, 0) or 0) + float(value)


def _pay_wage(state, pref: str, payers: tuple, pay_to: str, wage: int
              ) -> Tuple[int, List[Tuple[str, int]]]:
    """本路出资阶层 `wealth` → **本路 `pay_to` `wealth`**（`transfer_money` 守恒划转）。

    返回 `(实付, 已划出明细)`。**全或无**：若逐档划出不足 `wage`，按逆序原路退回，
    返回 0 —— 杜绝"扣了料却没付到工钱"的半笔账。
    """
    if wage <= 0:
        return 0, []
    tm = getattr(state, "transfer_money", None)
    if not callable(tm):
        return 0, []
    p = (getattr(state, "prefectures", None) or {}).get(pref) or {}
    pops = p.get("pops") or {}
    plan: List[Tuple[str, int]] = []
    remaining = int(wage)
    for cls in payers:
        if remaining <= 0:
            break
        slot = pops.get(cls)
        have = _ge0(slot.get("wealth")) if isinstance(slot, dict) else None
        if have is None:
            continue
        take = int(min(int(have), remaining))
        if take <= 0:
            continue
        plan.append((cls, take))
        remaining -= take
    if remaining > 0:
        return 0, []                       # 出资池不足 ⇒ 分文不动
    paid = 0
    done: List[Tuple[str, int]] = []
    for cls, amt in plan:
        moved = int(tm(f"pop:{pref}:{cls}", f"pop:{pref}:{pay_to}", amt) or 0)
        done.append((cls, moved))
        paid += moved
    if paid < wage:
        for cls, moved in reversed(done):
            if moved > 0:
                tm(f"pop:{pref}:{pay_to}", f"pop:{pref}:{cls}", moved)
        return 0, []
    return paid, done


def build_civil_building(state, pref: str, building: str, *,
                         month: Optional[int] = None,
                         allow_job_class: bool = False,
                         log: Optional[list] = None) -> Dict[str, Any]:
    """**建成**一路某民间建筑：先真实扣料、再真付工钱、最后落既有建筑槽位。

    纪律：
      · **全或无**：料/工时/钱任一不到位 ⇒ 什么都不写、不扣料、不付钱；
      · **钱必有对手方**：出资阶层 `wealth` → 本路 `工匠 wealth`（`transfer_money`）；
      · **不新建人口**：全程不写任何 POP `size`；工时只进 `statistics`；
      · 落点是既有 `prefectures[路]["buildings"][名]`，**不另建建筑账本**；
      · 每月**最多升 `CIVIL_LEVELS_PER_MONTH` 级**（本函数一次只升一级）。

    返回 `{ok, reason, ...}`；`ok=False` 时 `reason` 与触发读数一致，**无任何写入**。
    """
    logs = log if isinstance(log, list) else []
    trigger = route_civil_trigger(state, pref, building, month=month,
                                  allow_job_class=allow_job_class)
    if trigger["decision"] != "build":
        return {"ok": False, "reason": trigger["reason"], "trigger": trigger,
                "pref": pref, "building": building}

    spec = resolve_civil_building(building)
    p = (getattr(state, "prefectures", None) or {})[pref]
    materials = trigger["cost"]["materials"]
    # 注：不再取 `state.resources`——B4-1 收窄版 B 后建材由商人持有，料成本走市场。

    # ---- 落点容器：先确认 `buildings` 槽可写，**再**动钱（杜绝"付了钱写不进去"）----
    buildings = p.get("buildings")
    if not isinstance(buildings, dict):
        if buildings is not None:
            return {"ok": False, "reason": "route_buildings_malformed",
                    "trigger": trigger, "pref": pref, "building": building}
        buildings = {}
        p["buildings"] = buildings

    # ---- 成本 1：料（🔴 口径 C-c：只从**本地州府仓**取，取不到即缺料）----
    # 🔴 **不再直读 `state.resources[dim]["stock"]`**（那是全国总账，读它等于
    # "料可凭空调用"）⇒ 物流失去意义。判定与扣料**共用同一个读口**
    # `material_holding_for_circuit()`，杜绝 §14.2 障碍 2 的口径分叉。
    from core.material_holding import material_holding_for_circuit
    take: Dict[str, int] = {}
    for dim, need_q in materials.items():
        have = material_holding_for_circuit(state, pref, dim)
        if have is None or have < need_q:
            # 兜底（读数刚判过、此处再核一次）：分文不动、不扣料
            return {"ok": False, "reason": "material_stock_unknown" if have is None
                    else "material_short", "trigger": trigger,
                    "pref": pref, "building": building}
        take[dim] = int(need_q)

    # ---- 成本 2：钱（工钱，出资阶层 → 本路工匠；全或无，失败即原路退回）----
    # ⚠️ C-c 下**料款与工钱彻底分离**：取料**不再付钱**（料在州府仓里是实物调拨），
    # 故这里只剩工钱一笔，**不会与出资阶层抢钱**（§14.2 障碍 1 消解）。
    wage = int(trigger["afford"]["wage"])
    pay_to = CIVIL_WAGE_RECIPIENT          # 工钱收款方恒为本路工匠（营造/修缮服务）
    paid, legs = _pay_wage(state, pref, tuple(spec["payers"]), pay_to, wage)
    if paid < wage:
        return {"ok": False, "reason": "coin_short", "trigger": trigger,
                "pref": pref, "building": building}

    # ---- 落料：从**本地州府仓**实扣（不再动全国总账）----
    from core.material_holding import consume_for_circuit
    for dim, qty in take.items():
        got = consume_for_circuit(state, pref, dim, qty)
        if got < qty:
            # 理论上不会发生（上面刚判过）；真发生则**不吞掉**，如实报缺料
            return {"ok": False, "reason": "material_short", "trigger": trigger,
                    "pref": pref, "building": building}

    # ---- 落点：既有 `prefectures[路]["buildings"][名]` 槽位 ----
    from core.building_jobs import building_level as _bld_lv
    old_lv = _bld_lv(buildings.get(building), 0)
    new_lv = min(int(spec["level_cap"]),
                 old_lv + max(1, int(CIVIL_LEVELS_PER_MONTH)))
    if spec.get("write_form") == "scalar":
        buildings[building] = int(new_lv)          # 岗位类：标量（int(lv) 兼容）
    else:
        now = abs_month_index(state, month)
        entry = buildings.get(building)
        if isinstance(entry, dict):
            entry["lv"] = int(new_lv)
            entry["built_month"] = now
        else:
            buildings[building] = {"lv": int(new_lv), "built_month": now}

    # ---- 统计（全部落既有 `state.statistics`）----
    labor_hours = float(trigger["cost"]["labor_hours"] or 0.0)
    value = float(trigger["cost"]["base_material_value"] or 0.0)
    _stat_add(state, "civil_levels_built", 1)
    _stat_add(state, "civil_coin_paid", paid)
    _stat_add(state, "civil_material_value", value)
    _stat_add(state, "civil_labor_hours", labor_hours)
    for dim, qty in take.items():
        _stat_add(state, f"civil_material_used_{dim}", qty)

    reason_txt = "、".join(
        f"{DRIVER_LABELS[d]}{float(trigger['drivers'][d]):.2f}级"
        for d in CIVIL_DRIVERS if trigger["drivers"][d])
    logs.append(
        f"[营造] {pref}·{building} Lv{old_lv}→Lv{new_lv}："
        f"扣{ '、'.join(f'{d}{q}' for d, q in take.items()) }、"
        f"工钱 {paid:,} 贯（→{pay_to}）、工时 {labor_hours:.0f}"
        f"；动因：{reason_txt}")

    return {"ok": True, "reason": "built", "pref": pref, "building": building,
            "lv": int(new_lv), "delta_lv": int(new_lv) - int(old_lv),
            "coin_paid": int(paid), "coin_legs": [{"from": c, "amount": a}
                                                  for c, a in legs],
            "material_used": dict(take),
            "base_material_value": value, "labor_hours": round(labor_hours, 4),
            "trigger": trigger}


def apply_civil_construction(state, log: Optional[list] = None, *,
                             month: Optional[int] = None,
                             allow_job_class: bool = False) -> Dict[str, Any]:
    """月度民间营造触发：**逐路逐建筑**读数 → 判 `build` 者真实扣料/付钱/落点。

    纪律：
      · 算法不在此复制（`route_civil_trigger` 是唯一判据实现）；
      · 同路多建筑**共用当月工时池**（`labor_used` 逐项扣减），不超征；
      · 逐建筑 `undefined` 只计数与留痕，不阻断其它建筑（**逐项隔离**）。

    参数：
      · `month`：覆盖绝对月序（测试用；默认读 `state.year`/`state.month`）。
      · `allow_job_class`：是否允许建**岗位类**民间建筑（默认 `False`，见模块 §五）。

    返回本月汇总 dict（`levels_built` / `coin_paid` / `material_used` /
    `material_value` / `labor_hours` / `built` / `blocked` / `undefined_routes`）。
    """
    logs = log if isinstance(log, list) else []
    if state is None:
        raise TypeError("state 不能为 None")
    prefs = getattr(state, "prefectures", None)
    if prefs is None:
        raise ValueError("state.prefectures 缺失（state 未初始化？）")
    if not isinstance(prefs, dict):
        raise TypeError(f"state.prefectures 应为 dict，得 {type(prefs).__name__}")

    summary: Dict[str, Any] = {
        "levels_built": 0, "coin_paid": 0, "material_used": {},
        "material_value": 0.0, "labor_hours": 0.0, "built": [],
        "blocked": {}, "undefined_routes": 0, "routes_with_build": 0,
    }
    blocked_count = {"material_short": 0, "labor_short": 0, "coin_short": 0,
                     "no_pressure": 0, "at_level_cap": 0,
                     "job_class_opt_in_required": 0}

    for pref, p in prefs.items():
        if not isinstance(p, dict):
            summary["undefined_routes"] += 1
            continue
        labor_used = 0.0
        for name in CIVIL_BUILDING_SPECS:
            trig = route_civil_trigger(state, pref, name, month=month,
                                       allow_job_class=allow_job_class,
                                       labor_used=labor_used)
            if not trig["defined"]:
                summary["undefined_routes"] += 1
                summary["blocked"].setdefault(pref, {})[name] = {
                    "decision": "undefined", "reason": trig["reason"]}
                logs.append(f"[营造] {pref}·{name} 读数未定义（{trig['reason']}），不建")
                continue
            if trig["decision"] != "build":
                summary["blocked"].setdefault(pref, {})[name] = {
                    "decision": "no_build", "reason": trig["reason"]}
                blocked_count[trig["reason"]] = blocked_count.get(trig["reason"], 0) + 1
                continue
            out = build_civil_building(state, pref, name, month=month,
                                       allow_job_class=allow_job_class, log=logs)
            if not out.get("ok"):
                summary["blocked"].setdefault(pref, {})[name] = {
                    "decision": "no_build", "reason": out.get("reason")}
                blocked_count[out.get("reason", "unknown")] = \
                    blocked_count.get(out.get("reason", "unknown"), 0) + 1
                continue
            labor_used += float(out["labor_hours"])
            summary["levels_built"] += int(out["delta_lv"])
            summary["coin_paid"] += int(out["coin_paid"])
            summary["material_value"] += float(out["base_material_value"])
            summary["labor_hours"] += float(out["labor_hours"])
            for dim, q in out["material_used"].items():
                summary["material_used"][dim] = \
                    summary["material_used"].get(dim, 0.0) + float(q)
            summary["built"].append({
                "pref": pref, "building": name, "lv": out["lv"],
                "coin_paid": out["coin_paid"], "material_used": out["material_used"],
                "labor_hours": out["labor_hours"],
                "drivers": trig["drivers"], "pressure": trig["pressure"],
            })
            summary["routes_with_build"] += 1

    for reason, key in CIVIL_BLOCKED_STAT.items():
        if blocked_count.get(reason):
            _stat_add(state, key, blocked_count[reason])
    if summary["undefined_routes"]:
        _stat_add(state, "civil_undefined_routes", summary["undefined_routes"])
    return summary