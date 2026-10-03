# -*- coding: utf-8 -*-
"""宋祚 · 建材科技解锁注册表（规格 `market-civilian-economy` **B4-2**）。

> 本模块**尚未接线**到 `settlement.py`（由 Lead 统一接线）。
> 接线位置与顺序见本文件 `WIRING_HINT`，本文不改任何既有文件。

## 〇、要治的病（B4-2 原文）

> **B4-2 新材科技解锁**：未来若加入水泥/钢筋等新材，须通过**科技解锁配方/工艺/贸易**——
> **科技 ≠ 免费材料**（用户 2026-10-01 定论；全库现无此物）。

即：**建材不是「加一行数据就有」，也不是「价格 0 视为白给」或「缺货冒充未解锁」**。
一种新材在本作存在的唯一合法路径，是先被**解锁**（三种来源之一），
解锁之后才有配方、才有产地、才有价格、才能成交。

## 一、⚠️ 史实声明：新材是**架空后世材料**

**北宋（960–1127）没有水泥、没有钢筋。** 宋代构筑实际用的是
石灰（煅烧石灰石）、糯米灰浆、砖、石、木与锻铁条（铁楔、闸铁、桥铁），
混凝土类"素混凝土"亦仅见于城墙个别做法，与后世硅酸盐水泥不是一物。

⇒ 本注册表内 `水泥` / `钢筋` 两条**均显式标注 `fictional: True`**，
即**架空后世材料**，是游戏机制上的"科技解锁产物"，**不是北宋史实**。
本模块的职责恰恰是：**保证它们不被误当史实开局资源**——未解锁即不可用。

（若日后加入**有宋实录**的材料，如"石灰""麻刀灰"，应 `fictional: False`
并在 `note` 里写明宋代实物依据；注册表按同一结构接受，但两种标注都必填 `note`。）

## 二、三种解锁来源（都能表达，且**记录来源**）

| 来源 `source` | 语义 | 前置的语义要求 |
|---|---|---|
| `"tech"` | **科技节点解锁**：某科技节点点亮 ⇒ 掌握该材配方 | 必须声明主解锁节点 `tech_node`（且它在 `tech_nodes` 内） |
| `"craft"` | **工艺改进**：本土匠人在**既有作坊**里改良工艺、习得秘法 | 必须声明承载作坊 `workshops`（须是**解锁前就存在**的建筑，避免循环依赖）+ 至少 `min_sites` 处已建成 |
| `"trade"` | **贸易引入**：市舶/榷场/西学东渐把外来制品或图样带入 | 必须声明至少一项贸易渠道条件（`min_west` 西学东渐 或 `maritime` 市舶广开） |

来源写入解锁记录（`source` + `via` 具体载体），`material_unlocked_by()` 可回查。

## 三、前置条件与拒绝式

每条材料对每种来源各有一组前置 `tech_nodes` / `min_tech_level` / `min_year` /
`min_month` / `min_west` / `maritime` / `workshops` + `min_sites`。

* **校验注册表**：`register_material_tech`（以及模块常量表的导入自检）
  对非法条目**直接 raise `MaterialTechError`**，**不静默写入半个条目**——
  缺字段、未知来源键、未知字段（拼错即拒）、负值/非有限值、循环依赖（craft 指向自己解锁的作坊）、
  产地名不在 `PREFECTURE_LIST`、科技节点 id 不在 `TECH_NODES`，一律拒绝。
* **校验解锁**：`check_material_prereq(state, mat, source)` 是**纯读数**，
  返回 `{"ok", "reason", "detail", "missing", "defined"}`；`unlock_material()` 是唯一的写入口，
  前置不满足即 **raise 并带 `reason`**（拒绝式，不写半个记录）。

## 四、缺失 ≠ 0 ≠ 1.0（读数三态）

`material_unlock_status()` 返回四态，**绝不回落成布尔或 0**：

| `status` | 含义 | `is_material_unlocked()` |
|---|---|---|
| `"unlocked"` | 有合法解锁记录 | `True` |
| `"locked"` | 已登记但**实测未解锁**（无记录且科技节点确实未点亮） | `False` |
| `"unrecorded"` | **读数缺失**：存档无 `tech["materials"]` 容器，或记录畸形，或"节点已点亮却无记录"（需人工裁决，**不得臆断**） | `None` |
| `"unknown"` | 材料未在注册表登记（调用方须记 `unregistered`，**不得兜底成中性值**） | `None` |

* `None` 必须被调用方按 **fail-closed（不可用）** 处理，
  但**不得**当作 `False` 落账、也不得在界面上显示"未解锁"（应显示"未定义"）。
* `effective_material_price()`：未解锁 ⇒ 返回 `None`，
  **绝不是 0**（0 价＝白给，正是 B4-2 要治的病）；基准价本身缺失 ⇒ 同样 `None`；
  基准价非有限/为负 ⇒ 拒绝式 `raise ValueError`；
  **架空后世材料的基准价 0 ⇒ 也 `raise ValueError`**（内容表漏配不得降级成"白送材料"）。

## 五、落档策略（POP 挂载律 + 无平行账本）

* **注册表 `MATERIAL_TECH_UNLOCKS` 是纯模块常量**（静态数据，进程级共享，
  **不是账本**、不随存档变化、绝不按回合累加）。
* **解锁记录落 `state.tech["materials"][dim]`** —— `state.tech` 是**既有存档容器**
  （`save_load.py:275` `"tech": state.tech` 整表序列化、`:977` 整表恢复），
  本模块只在其下**新增一个子键**，**无 schema 迁移**、不新建顶层字段。
  旧档缺该子键 ⇒ 读侧判 `unrecorded`（缺失），**不是** `False`。
* **`unlock_material()` 另在 `state.resources[dim]` 补一个空槽**（`{"stock":0,"cap":0}`），
  该容器同样整表落档（`save_load.py:239`）⇒ 后续接线不必改 `data_constants`。
  **注意：本模块绝不调用 `content.data_constants.register_raw_material()`**（不改内容表）。
* **绝不写 POP**：本模块从不写任何 POP 的 `size` / `wealth` / `grain`，
  不写国库 / 内帑，不改任何 POP 平行账本（硬约束 §3.1）。
* **读数函数零写入**：`material_unlock_status` / `material_unlocked_by` /
  `material_sites` / `check_material_prereq` / `material_availability` /
  `effective_material_price` / `material_tradable` 全部是**纯读数**，不改 `state` 任何字段
  （连 `state.tech` 的容器都不创建）。唯一的写入口是 `unlock_material()`。
* **缓存失效**：别名索引 `_ALIAS_INDEX` 惰性构建；
  `register_material_tech()` 自动失效，并提供显式钩子 `invalidate_material_tech_cache()`
  （内容表热更 / 动态注册蓝图后调用）。

## 六、迁移策略

* **无 schema 迁移**：落点只有 `state.tech["materials"]` 与 `state.resources[dim]` 两个既有容器。
* **旧档兼容**：旧档 `state.tech` 无 `materials` 键 ⇒ 全表 `unrecorded`；
  接线时由 Lead 一次性回填（对已点亮对应科技节点的材料按 `"tech"` 来源补记，
  补记走 `unlock_material()` 同一校验，不手写记录）。
* **幂等**：`unlock_material()` 对已解锁材料**拒绝**（`reason="already_unlocked"`），
  不重复写来源；调用方先查 `is_material_unlocked()`。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "MATERIAL_TECH_UNLOCKS",
    "UNLOCK_SOURCES",
    "STATUS_UNLOCKED",
    "STATUS_LOCKED",
    "STATUS_UNRECORDED",
    "STATUS_UNKNOWN",
    "MATERIALS_RECORD_KEY",
    "MaterialTechError",
    "register_material_tech",
    "invalidate_material_tech_cache",
    "resolve_material_tech",
    "material_unlock_status",
    "is_material_unlocked",
    "material_unlocked_by",
    "material_sites",
    "check_material_prereq",
    "unlock_material",
    "unlock_materials_for_node",
    "material_availability",
    "effective_material_price",
    "material_tradable",
    "WIRING_HINT",
]

# =============================================================================
# 一、模块级常量
# =============================================================================

#: 解锁记录的落档键（**`state.tech` 的子键**，非顶层字段、非新账本）
MATERIALS_RECORD_KEY = "materials"

#: 三种解锁来源（**枚举封闭**：注册表出现别的键即拒绝）
UNLOCK_SOURCES = ("tech", "craft", "trade")

#: 状态枚举
STATUS_UNLOCKED = "unlocked"
STATUS_LOCKED = "locked"
STATUS_UNRECORDED = "unrecorded"
STATUS_UNKNOWN = "unknown"

#: 前置条件允许的字段（**白名单**：拼错字段即拒，不静默失效）
_PREREQ_FIELDS = (
    "tech_node", "tech_nodes", "min_tech_level", "min_year", "min_month",
    "min_west", "maritime", "workshops", "min_sites",
)

#: 接入建议（只读常量，供 Lead 与面板提示；**本模块不自行接线**）
WIRING_HINT = (
    "接线顺序建议：(1) 科技线——在 core/asset_context.unlock_node() 成功分支之后、"
    "同一次调用里调用 material_tech.unlock_material(state, dim, 'tech')"
    "（前置不满足会被拒并给出 reason，届时由 _settle_tech_research 记一条日志留痕，"
    "不要 try/except 静默吞掉）；"
    "(2) 贸易线——在市舶/榷场结算步（state.maritime['open'] 置真、state.tech['west'] 增长处）"
    "调用 unlock_material(state, dim, 'trade')；"
    "(3) 价格线——market_price 取 MATERIAL_PRICE_BASE[dim] 时先过 "
    "material_tech.effective_material_price(state, dim, base)，返回 None 即该材"
    "**不可交易**（不是价 0、不是缺货；架空材料若算出 0 价会直接 raise，"
    "说明内容表漏配 MATERIAL_PRICE_BASE，请补价而不是回落 0）；"
    "(4) 营造线——construction/settlement 的材料清单校验处加一步 "
    "material_tech.material_availability(state, dim)，不可用则拒绝立项并附 reason，"
    "**不得**当作缺料排队（缺料会照常完工是 B4-1 的验收红线）。"
    "顺序理由：解锁必须早于取价与立项，否则会出现『已解锁却仍按不可用计价』的一月滞后。"
)


# =============================================================================
# 二、注册表：新材 → 解锁来源与前置
# =============================================================================
# 字段：
#   label       中文名（面板/日志）
#   dim         物资维度键（`state.resources` 的键；**尚未登记进 content 维度表**，
#               由 Lead 用 `content.data_constants.register_raw_material` 接）
#   unit        单位（只作展示/配方口径；**不推导价格**）
#   fictional   True=架空后世材料（北宋无史实）；False=有宋代实物依据
#   note        **必填**：史实依据或架空声明（两种标注都必须写清）
#   aliases     同材的其它书写（别名索引，惰性构建 + 失效钩子）
#   workshop    承载作坊名（须是**解锁前既有**建筑，见 `_validate_entry` 的循环依赖检查）
#   sites       候选产地（**必须存在于 `PREFECTURE_LIST`**）
#   recipe      配方，**字段名与 `content.data_constants.WORKSHOP_RECIPES` 同构**
#               （name / recipe / output_dim / yield）⇒ 可直接并入作坊表
#   unlock      来源 → 前置（键必须 ⊆ `UNLOCK_SOURCES`）
#
# ⚠️ 数值说明：本表**只表达"能不能解锁/谁解锁"**，不含价格与产能
# （价格是 B4-1 建材实物化的参数待裁项，规格 §6 明示待裁；此处不臆定）。
MATERIAL_TECH_UNLOCKS: Dict[str, Dict[str, Any]] = {
    # ---- 架空后世材料 1：水泥（北宋无硅酸盐水泥，见本文件 §一）----
    "水泥": {
        "label": "水泥",
        "dim": "水泥",
        "unit": "石",
        "fictional": True,
        "note": "架空后世材料：北宋构筑用石灰、糯米灰浆与砖石，无硅酸盐水泥。"
                "水泥须经科技/工艺/贸易之一解锁后才有配方、产地与价格。",
        "aliases": ("portland_cement", "hydraulic_cement"),
        "workshop": "官营作坊",
        "sites": ("京畿路", "两浙路", "成都府路"),
        "recipe": {"name": "水泥窑", "recipe": {"stone": 100, "copper": 5},
                   "output_dim": "水泥", "yield": 40},
        "unlock": {
            # 科技：石灰黏土煅烧属「酸碱制取」一路，前置「砖石高炉」的煅烧技术
            "tech": {"tech_node": "C2_acid",
                     "tech_nodes": ("M4_furnace", "C2_acid"),
                     "min_tech_level": 70, "min_year": 1105},
            # 工艺改进：本土匠人在**既有官营作坊**内改良窑火配比（本地窑造，不涉外来）
            "craft": {"workshops": ("官营作坊",), "min_sites": 1,
                      "tech_nodes": ("M4_furnace",),
                      "min_tech_level": 66, "min_year": 1101},
            # 贸易引入：市舶/西学带入配比图样
            "trade": {"tech_nodes": ("C2_acid",), "min_tech_level": 72,
                      "min_west": 1, "maritime": True, "min_year": 1105},
        },
    },
    # ---- 架空后世材料 2：钢筋（宋代只有锻铁条，无炼钢轧制钢筋）----
    "钢筋": {
        "label": "钢筋",
        "dim": "钢筋",
        "unit": "斤",
        "fictional": True,
        "note": "架空后世材料：宋代铁骨为锻铁条（铁楔、闸铁、桥铁），"
                "无近代炼钢轧制的钢筋。钢筋须经科技/工艺/贸易之一解锁后方可生产或交易。",
        "aliases": ("rebar", "reinforcing_steel"),
        "workshop": "官营作坊",
        "sites": ("京畿路", "河北路", "利州路"),
        "recipe": {"name": "轧铁坊", "recipe": {"iron": 100, "copper": 2},
                   "output_dim": "钢筋", "yield": 45},
        "unlock": {
            # 科技：精炼钢 + 焦炭冶铁为前置（E3_steel 本身即 era4 的超时代节点）
            "tech": {"tech_node": "E3_steel",
                     "tech_nodes": ("E2_coke", "E3_steel"),
                     "min_tech_level": 82, "min_year": 1120},
            # 工艺改进：本土铁作坊试轧条铁（两处以上作坊方能成法）
            "craft": {"workshops": ("官营作坊",), "min_sites": 2,
                      "tech_nodes": ("E2_coke",),
                      "min_tech_level": 78, "min_year": 1110},
            # 贸易引入：外邦输入西铁条 + 轧制图样
            "trade": {"tech_nodes": ("E2_coke",), "min_tech_level": 80,
                      "min_west": 1, "maritime": True, "min_year": 1112},
        },
    },
}

#: 别名 → 规范键（惰性构建；`register_material_tech` / `invalidate_material_tech_cache` 失效）
_ALIAS_INDEX: Optional[Dict[str, str]] = None


class MaterialTechError(ValueError):
    """注册表条目非法，或解锁被前置条件拒绝。**拒绝式**：不静默写入半个条目。"""


# =============================================================================
# 三、注册表访问（照 `settlement_agri` 的注册表范式）
# =============================================================================

def _build_alias_index() -> Dict[str, str]:
    """惰性构建别名索引；**规范键/别名重复即 raise**（防止一条材被两条登记）。"""
    global _ALIAS_INDEX
    if _ALIAS_INDEX is not None:
        return _ALIAS_INDEX
    idx: Dict[str, str] = {}
    for key, entry in MATERIAL_TECH_UNLOCKS.items():
        idx[str(key)] = key
        for a in (entry.get("aliases") or ()):
            if str(a) in idx:
                raise MaterialTechError(
                    f"别名 {a!r} 重复：已指向 {idx[str(a)]!r}，又被 {key!r} 占用")
            idx[str(a)] = key
    _ALIAS_INDEX = idx
    return idx


def invalidate_material_tech_cache() -> None:
    """**缓存失效钩子**：动态注册材料 / 内容表热更后必须调用。"""
    global _ALIAS_INDEX
    _ALIAS_INDEX = None


def resolve_material_tech(key: Any) -> Optional[Dict[str, Any]]:
    """材料名/别名 → 注册条目；未注册返回 `None`（调用方须记 `unregistered`，**不得兜底成中性值**）。"""
    if not isinstance(key, str) or not key:
        return None
    canon = _build_alias_index().get(key)
    if canon is None:
        return None
    return MATERIAL_TECH_UNLOCKS.get(canon)


# =============================================================================
# 四、校验（拒绝式；非法条目 raise）
# =============================================================================

def _num(value: Any, field: str, key: str, *, integer: bool = False) -> float:
    """数值校验：**拒绝式**。非有限/负数/bool ⇒ raise（不回落 0/1.0）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MaterialTechError(f"注册表条目 {key!r} 的 {field} 必须是数值，得 {value!r}")
    v = float(value)
    if not math.isfinite(v):
        raise MaterialTechError(
            f"注册表条目 {key!r} 的 {field} 非有限值 {value!r}（不得回落 0/1.0）")
    if v < 0:
        raise MaterialTechError(f"注册表条目 {key!r} 的 {field} 为负 {value!r}")
    if integer and v != int(v):
        raise MaterialTechError(f"注册表条目 {key!r} 的 {field} 必须是整数，得 {value!r}")
    return v


def _int_in(value: Any, field: str, key: str, lo: int, hi: int) -> int:
    _num(value, field, key, integer=True)
    v = int(value)
    if not (lo <= v <= hi):
        raise MaterialTechError(f"注册表条目 {key!r} 的 {field}={v} 越界（须 {lo}~{hi}）")
    return v


def _str_tuple(value: Any, field: str, key: str, *, allow_empty: bool = False) -> Tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise MaterialTechError(f"注册表条目 {key!r} 的 {field} 必须是 tuple/list，得 {value!r}")
    if not value and not allow_empty:
        raise MaterialTechError(f"注册表条目 {key!r} 的 {field} 为空")
    out: List[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise MaterialTechError(f"注册表条目 {key!r} 的 {field} 含非法项 {item!r}")
        out.append(item)
    return tuple(out)


def _validate_prereq(key: str, source: str, req: Any) -> None:
    """单个来源的前置组校验。未知字段即拒（拼错静默失效是最难查的一类 bug）。"""
    if not isinstance(req, dict):
        raise MaterialTechError(f"注册表条目 {key!r} 的 unlock[{source!r}] 必须是 dict")
    for field in req:
        if field not in _PREREQ_FIELDS:
            raise MaterialTechError(
                f"注册表条目 {key!r} 的 unlock[{source!r}] 含未知前置字段 {field!r}"
                f"（合法字段：{_PREREQ_FIELDS}）")
    if "tech_nodes" in req:
        nodes = _str_tuple(req["tech_nodes"], f"unlock[{source!r}].tech_nodes", key)
        if "tech_node" in req:
            node = req["tech_node"]
            if not isinstance(node, str) or not node.strip():
                raise MaterialTechError(
                    f"注册表条目 {key!r} 的 unlock[{source!r}].tech_node 非法 {node!r}")
            if node not in nodes:
                raise MaterialTechError(
                    f"注册表条目 {key!r} 的 unlock[{source!r}].tech_node={node!r} "
                    f"不在 tech_nodes={nodes} 内（主解锁节点必须自身也是前置）")
    if "min_tech_level" in req:
        _num(req["min_tech_level"], f"unlock[{source!r}].min_tech_level", key)
    if "min_year" in req:
        _int_in(req["min_year"], f"unlock[{source!r}].min_year", key, 1, 100_000)
    if "min_month" in req:
        _int_in(req["min_month"], f"unlock[{source!r}].min_month", key, 1, 12)
    if "min_west" in req:
        _num(req["min_west"], f"unlock[{source!r}].min_west", key)
    if "maritime" in req and not isinstance(req["maritime"], bool):
        raise MaterialTechError(
            f"注册表条目 {key!r} 的 unlock[{source!r}].maritime 必须是 bool")
    if "min_sites" in req:
        _int_in(req["min_sites"], f"unlock[{source!r}].min_sites", key, 1, 999)
    # ---- 来源语义要求（三种来源都要能表达，且各自的前置语义必须齐备）----
    if source == "tech":
        if not req.get("tech_nodes"):
            raise MaterialTechError(
                f"注册表条目 {key!r} 走 tech 通道但缺 tech_nodes"
                f"（无前置节点 ⇒ 无法表达「科技解锁」，不得臆造）")
    elif source == "craft":
        if not req.get("workshops"):
            raise MaterialTechError(
                f"注册表条目 {key!r} 走 craft 通道但缺 workshops"
                f"（无承载作坊 ⇒ 无法表达「工艺改进」）")
        _str_tuple(req["workshops"], f"unlock[{source!r}].workshops", key)
    elif source == "trade":
        if "min_west" not in req and not req.get("maritime"):
            raise MaterialTechError(
                f"注册表条目 {key!r} 走 trade 通道但既无 min_west 也无 maritime"
                f"（无渠道条件 ⇒ 等于白给，违背「科技 ≠ 免费材料」）")


def _validate_entry(key: str, entry: Any, *, cross_check: bool = True) -> Dict[str, Any]:
    """注册表条目校验（拒绝式）。`cross_check=True` 时对 `content` 表做名实核对。"""
    if not isinstance(entry, dict):
        raise MaterialTechError(f"注册表条目 {key!r} 必须是 dict")
    for field in ("label", "dim", "unit"):
        v = entry.get(field)
        if not isinstance(v, str) or not v.strip():
            raise MaterialTechError(f"注册表条目 {key!r} 缺 {field} 或其值非法 {v!r}")
    if not isinstance(entry.get("fictional"), bool):
        raise MaterialTechError(
            f"注册表条目 {key!r} 的 fictional 必须是 bool"
            f"（True=架空后世材料 / False=宋代有实物依据；不得省略）")
    if not isinstance(entry.get("note"), str) or not entry["note"].strip():
        raise MaterialTechError(
            f"注册表条目 {key!r} 缺 note（架空/史实依据必填，防止后来者误当北宋史实）")
    if "aliases" in entry:
        for a in _str_tuple(entry["aliases"], "aliases", key):
            if a == key:
                raise MaterialTechError(f"注册表条目 {key!r} 的 aliases 不得含自身")
    ws = entry.get("workshop")
    if ws is not None and (not isinstance(ws, str) or not ws.strip()):
        raise MaterialTechError(f"注册表条目 {key!r} 的 workshop 非法 {ws!r}")
    sites = _str_tuple(entry.get("sites"), "sites", key)
    if len(set(sites)) != len(sites):
        raise MaterialTechError(f"注册表条目 {key!r} 的 sites 含重复路名 {sites}")

    # ---- 配方（字段名与 WORKSHOP_RECIPES 同构，可直接并入作坊表）----
    recipe = entry.get("recipe")
    if recipe is not None:
        if not isinstance(recipe, dict):
            raise MaterialTechError(f"注册表条目 {key!r} 的 recipe 必须是 dict")
        if not isinstance(recipe.get("name"), str) or not recipe["name"].strip():
            raise MaterialTechError(f"注册表条目 {key!r} 的 recipe.name 缺失")
        inputs = recipe.get("recipe")
        if not isinstance(inputs, dict) or not inputs:
            raise MaterialTechError(f"注册表条目 {key!r} 的 recipe.recipe 必须是非空 dict")
        for dim, qty in inputs.items():
            if not isinstance(dim, str) or not dim.strip():
                raise MaterialTechError(f"注册表条目 {key!r} 的 recipe 原料维度非法 {dim!r}")
            if _num(qty, f"recipe[{dim}]", key) <= 0:
                raise MaterialTechError(
                    f"注册表条目 {key!r} 的 recipe[{dim}] 必须为正（0 投入=凭空产料）")
        if recipe.get("output_dim") != entry["dim"]:
            raise MaterialTechError(
                f"注册表条目 {key!r} 的 recipe.output_dim={recipe.get('output_dim')!r} "
                f"与 dim={entry['dim']!r} 不一致")
        if _num(recipe.get("yield"), "recipe.yield", key) <= 0:
            raise MaterialTechError(f"注册表条目 {key!r} 的 recipe.yield 必须为正")

    # ---- 解锁来源与前置 ----
    unlock = entry.get("unlock")
    if not isinstance(unlock, dict) or not unlock:
        raise MaterialTechError(f"注册表条目 {key!r} 缺 unlock（材料必须有解锁路径）")
    for source, req in unlock.items():
        if source not in UNLOCK_SOURCES:
            raise MaterialTechError(
                f"注册表条目 {key!r} 的 unlock 含未知来源 {source!r}"
                f"（合法：{UNLOCK_SOURCES}）")
        _validate_prereq(key, source, req)

    if not cross_check:
        return entry

    # ---- 与 content 表名实核对（防表漂移；content 不可导入时跳过，不静默吞异常）----
    try:
        from content.data import PREFECTURE_LIST
    except Exception:                                    # noqa: BLE001 - content 未就绪时跳过
        return entry
    bad = [r for r in sites if r not in PREFECTURE_LIST]
    if bad:
        raise MaterialTechError(
            f"注册表条目 {key!r} 的 sites 含不存在于 PREFECTURE_LIST 的路：{bad}")
    if entry.get("workshop"):
        try:
            from content.data import BUILDING_STD
        except Exception:                                # noqa: BLE001
            BUILDING_STD = {}
        if BUILDING_STD and entry["workshop"] not in BUILDING_STD:
            raise MaterialTechError(
                f"注册表条目 {key!r} 的 workshop={entry['workshop']!r} 不在 BUILDING_STD"
                f"（工艺改进必须依托**解锁前既有**建筑，否则与解锁互为因果）")
    try:
        from content.data import get_tech_node
    except Exception:                                    # noqa: BLE001
        return entry
    for source, req in unlock.items():
        for nid in (req.get("tech_nodes") or ()):
            if get_tech_node(nid) is None:
                raise MaterialTechError(
                    f"注册表条目 {key!r} 的 unlock[{source!r}].tech_nodes 含"
                    f"不存在于 TECH_NODES 的节点 {nid!r}")
    return entry


def _validate_registry() -> None:
    """模块常量表导入自检：任一条目非法 ⇒ import 即失败（防"半张表"上线）。"""
    if not MATERIAL_TECH_UNLOCKS:
        raise MaterialTechError("MATERIAL_TECH_UNLOCKS 为空（材料表必须有内容）")
    for key, entry in MATERIAL_TECH_UNLOCKS.items():
        if not isinstance(key, str) or not key.strip():
            raise MaterialTechError(f"注册键非法：{key!r}")
        if entry.get("dim") != key:
            raise MaterialTechError(
                f"注册表条目 {key!r} 的 dim={entry.get('dim')!r} 与注册键不一致")
        _validate_entry(key, entry)
    _build_alias_index()


def register_material_tech(key: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """动态注册一种新材（B4-2 的扩展入口：新蓝图/新商品上线时调用）。

    非法条目**拒绝并抛 `MaterialTechError`**（缺字段/未知来源/未知前置字段/负值/
    非有限值/循环依赖/路名或节点 id 不存在），**不静默写入半个条目**。
    成功返回登记后的条目（同一对象），并**自动失效别名索引**。
    """
    if not isinstance(key, str) or not key.strip():
        raise MaterialTechError(f"注册键非法：{key!r}")
    if key in MATERIAL_TECH_UNLOCKS:
        raise MaterialTechError(f"注册键 {key!r} 已存在（重复登记会让来源记录分叉，请先改名）")
    _validate_entry(key, entry)
    MATERIAL_TECH_UNLOCKS[key] = entry
    invalidate_material_tech_cache()
    _build_alias_index()          # 立即自检别名冲突（冲突即 raise，此时条目已写入）
    return entry


# 导入即自检（内容表就绪时生效）
_validate_registry()


# =============================================================================
# 五、读数：解锁状态 / 来源 / 产地（**纯读数，零写入**）
# =============================================================================

_STATUS_KEYS = ("material", "label", "status", "defined", "reason",
                "source", "via", "year", "month", "turn",
                "allowed_sources", "fictional", "note")


def _fin(v: Any) -> Optional[float]:
    """有限数值读口：缺失/非数值/非有限/bool ⇒ `None`（**不回落 0 或 1.0**）。"""
    if v is None or isinstance(v, bool):
        return None
    if not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _tech_dict(state) -> Dict[str, Any]:
    tech = getattr(state, "tech", None)
    if not isinstance(tech, dict):
        raise ValueError("state.tech 缺失或非法（state 未初始化？）")
    return tech


def _status_stub(material: Any, status: str, reason: str, *,
                 entry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: None for k in _STATUS_KEYS}
    out.update({
        "material": material if isinstance(material, str) else None,
        "label": (entry or {}).get("label"),
        "status": status,
        "defined": status in (STATUS_UNLOCKED, STATUS_LOCKED),
        "reason": reason,
        "allowed_sources": tuple((entry or {}).get("unlock") or ()),
        "fictional": (entry or {}).get("fictional"),
        "note": (entry or {}).get("note"),
    })
    return out


def _tech_node_unlocked(state, node_id: str) -> Optional[bool]:
    """科技节点在本局是否已解锁；**读数缺失 ⇒ `None`**（不回落 False 假装未研）。

    `None` 仅用于"读不到"，调用方（`material_unlock_status`）据此把状态标成
    `unrecorded`，**不会**当成"未解锁"。
    """
    tech = _tech_dict(state)
    unlocked = tech.get("unlocked")
    if not isinstance(unlocked, (list, tuple)):
        return None
    return node_id in unlocked


def material_unlock_status(state, material: Any) -> Dict[str, Any]:
    """某材在本局的**解锁状态**（纯读数，不改 `state` 任何字段，含不建容器）。

    返回 `{"material","label","status","defined","reason","source","via",
    "year","month","turn","allowed_sources","fictional","note"}`，`status` 四态：

    * `unlocked`  —— 有合法记录，`defined=True`
    * `locked`    —— 已登记、**实测未解锁**（无记录且科技节点确实未点亮），`defined=True`
    * `unrecorded`—— **读数缺失**：存档无 `tech["materials"]` 容器 / 记录畸形 /
      「节点已点亮却无记录」（需人工裁决，不臆断）
    * `unknown`   —— 材料未在注册表登记（调用方须记 `unregistered`）

    非法输入（`state` 为 None / `state.tech` 非 dict）⇒ `raise TypeError/ValueError`。
    """
    if state is None:
        raise TypeError("state 不能为 None")
    entry = resolve_material_tech(material)
    if entry is None:
        return _status_stub(material, STATUS_UNKNOWN, "unregistered_material")

    dim = str(entry["dim"])
    tech = _tech_dict(state)
    if MATERIALS_RECORD_KEY not in tech:
        # 旧档 / 尚未接线：容器整个不存在 ⇒ **缺失**，不是"未解锁"
        return _status_stub(material, STATUS_UNRECORDED,
                            "record_container_missing", entry=entry)
    records = tech.get(MATERIALS_RECORD_KEY)
    if not isinstance(records, dict):
        return _status_stub(material, STATUS_UNRECORDED,
                            "record_container_malformed", entry=entry)

    if dim in records:
        rec = records[dim]
        if not isinstance(rec, dict):
            return _status_stub(material, STATUS_UNRECORDED,
                                f"record_malformed:{dim}", entry=entry)
        src = rec.get("source")
        if src not in UNLOCK_SOURCES:
            # 来源字段非法 ⇒ 不可判定（**不得**猜一个来源填上）
            return _status_stub(material, STATUS_UNRECORDED,
                                f"record_source_invalid:{src!r}", entry=entry)
        out = _status_stub(material, STATUS_UNLOCKED, "", entry=entry)
        out.update({
            "source": src,
            "via": rec.get("via"),
            "year": _int_or_none(rec.get("year")),
            "month": _int_or_none(rec.get("month")),
            "turn": _int_or_none(rec.get("turn")),
        })
        return out

    # 无记录：分「确凿未解锁」与「读不到」两态
    nodes = []
    for src, req in (entry.get("unlock") or {}).items():
        for nid in (req.get("tech_nodes") or ()):
            if nid not in nodes:
                nodes.append(nid)
    verdicts = [_tech_node_unlocked(state, nid) for nid in nodes]
    if any(v is True for v in verdicts):
        # 前置节点已点亮却没有解锁记录 ⇒ 记录缺失（**不是"未解锁"**）
        return _status_stub(
            material, STATUS_UNRECORDED,
            f"record_missing_but_tech_node_unlocked:{nodes}", entry=entry)
    if verdicts and any(v is None for v in verdicts):
        return _status_stub(
            material, STATUS_UNRECORDED,
            f"tech_unlocked_list_missing:{nodes}", entry=entry)
    return _status_stub(material, STATUS_LOCKED, "no_record", entry=entry)


def _int_or_none(v: Any) -> Optional[int]:
    f = _fin(v)
    return None if f is None else int(f)


def _fmt(v: Any) -> str:
    """reason 里的数值格式化：整数不带 `.0`（`tech_level_below:69<70`），便于稳定断言。"""
    f = _fin(v)
    if f is None:
        return "None"
    return str(int(f)) if float(f).is_integer() else str(f)


def is_material_unlocked(state, material: Any) -> Optional[bool]:
    """**三态**读数：`True` 已解锁 / `False` 已登记且实测未解锁 / `None` **读数未定义**。

    ⚠️ `None`（unrecorded / 未注册）**必须**被调用方按"不可用"处理（fail-closed），
    但**不得**当作 `False` 落账或在界面显示"未解锁"——应显示"未定义"。
    """
    status = material_unlock_status(state, material)["status"]
    if status == STATUS_UNLOCKED:
        return True
    if status == STATUS_LOCKED:
        return False
    return None


def material_unlocked_by(state, material: Any) -> Optional[Dict[str, Any]]:
    """解锁**来源**记录：`{"source","via","year","month","turn"}`；
    未解锁 / 读数未定义 / 未注册一律返回 `None`（**不返回中性来源**）。"""
    st = material_unlock_status(state, material)
    if st["status"] != STATUS_UNLOCKED:
        return None
    return {"source": st["source"], "via": st["via"],
            "year": st["year"], "month": st["month"], "turn": st["turn"]}


# =============================================================================
# 六、读数：可用产地
# =============================================================================

_SITES_KEYS = ("material", "status", "defined", "reason", "sites",
               "candidate_sites", "no_workshop_sites", "missing")


def material_sites(state, material: Any, *, require_unlock: bool = True) -> Dict[str, Any]:
    """某材的**产地**（纯读数）。

    返回：
      · `candidate_sites` —— 注册表声明且本局**确实存在**的路；
      · `sites`          —— 其中**承载作坊已建成**的路（真正可生产）；
        `require_unlock=False` 时（前置校验用）跳过解锁判断。
      · 未解锁 / 读数未定义 ⇒ `sites=None`、`defined=False`（**不是空列表**：
        "不可用"与"没有产地"是两回事）。
      · 某路 `buildings` 键缺失 ⇒ 该路进 `missing`，**不计入可用产地**（缺失≠没有）。
    """
    if state is None:
        raise TypeError("state 不能为 None")
    entry = resolve_material_tech(material)
    out: Dict[str, Any] = {k: None for k in _SITES_KEYS}
    out.update({"status": None, "defined": False, "reason": "",
                "sites": None, "candidate_sites": None,
                "no_workshop_sites": None, "missing": []})
    if entry is None:
        out["status"] = STATUS_UNKNOWN
        out["reason"] = "unregistered_material"
        return out

    st = material_unlock_status(state, material)
    out["status"] = st["status"]
    if require_unlock and st["status"] != STATUS_UNLOCKED:
        out["reason"] = st["status"] if not st["reason"] else \
            f"{st['status']}:{st['reason']}"
        return out

    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        raise ValueError("state.prefectures 缺失或非法（state 未初始化？）")

    declared = tuple(entry.get("sites") or ())
    candidates = [r for r in declared if r in prefs]
    missing_routes = [r for r in declared if r not in prefs]

    workshop = entry.get("workshop")
    usable: List[str] = []
    no_ws: List[str] = []
    missing: List[str] = []
    for route in candidates:
        b = prefs[route].get("buildings") if isinstance(prefs[route], dict) else None
        if not isinstance(b, dict):
            missing.append(f"route_buildings_missing:{route}")
            continue
        if workshop:
            lv = _fin(b.get(workshop))
            if lv is None:
                missing.append(f"workshop_level_missing:{route}:{workshop}")
                continue
            if lv <= 0:
                no_ws.append(route)
                continue
        usable.append(route)

    out.update({
        "material": str(entry["dim"]),
        "defined": True,
        "reason": "",
        "candidate_sites": candidates,
        "sites": usable,
        "no_workshop_sites": no_ws,
        "missing": missing + [f"unknown_route:{r}" for r in missing_routes],
    })
    return out


# =============================================================================
# 七、解锁：前置校验（读）+ 写入（唯一写入口）
# =============================================================================

def check_material_prereq(state, material: Any, source: Any) -> Dict[str, Any]:
    """某材在指定来源下的**前置校验**（纯读数，不写 `state`）。

    返回 `{"ok","defined","reason","detail","missing","allowed_sources"}`：
      · `ok=False` ⇒ `reason` 必填（如 `tech_node_missing:E3_steel` / `year_before:1101<1120`
        / `workshop_not_deployed:京畿路` / `tech_level_missing`）；
      · `defined=False` ⇒ 状态**读不到**（如 `tech_level_missing`、`prefectures_missing`），
        同样 `ok=False`（fail-closed），**不得**因读不到就放行或回落 0。
    `material` 未注册 / `source` 非法 ⇒ `raise MaterialTechError`。
    """
    if state is None:
        raise TypeError("state 不能为 None")
    entry = resolve_material_tech(material)
    if entry is None:
        raise MaterialTechError(f"未注册的材料 {material!r}（不得对未登记材质做前置校验）")
    if not isinstance(source, str) or source not in UNLOCK_SOURCES:
        raise MaterialTechError(
            f"解锁来源非法：{source!r}（合法：{UNLOCK_SOURCES}）")
    unlock = entry.get("unlock") or {}
    if source not in unlock:
        return {"ok": False, "defined": True,
                "reason": "source_not_allowed",
                "detail": {"allowed_sources": tuple(unlock)},
                "missing": ["source_not_allowed"],
                "allowed_sources": tuple(unlock)}
    return _prereq_check(state, entry, source, unlock[source])


def _prereq_check(state, entry: Dict[str, Any], source: str, req: Dict[str, Any]) -> Dict[str, Any]:
    """逐条前置核对。任一条不满足 ⇒ 立即返回首个 `reason`（fail-closed）。"""
    unlock = entry.get("unlock") or {}
    detail: Dict[str, Any] = {"allowed_sources": tuple(unlock)}
    missing: List[str] = []

    def _fail(reason: str, defined: bool = True) -> Dict[str, Any]:
        return {"ok": False, "defined": defined, "reason": reason,
                "detail": detail, "missing": missing,
                "allowed_sources": tuple(unlock)}

    tech = _tech_dict(state)
    detail["source"] = source

    # ---- 科技节点前置 ----
    nodes = tuple(req.get("tech_nodes") or ())
    if nodes:
        unlocked = tech.get("unlocked")
        if not isinstance(unlocked, (list, tuple)):
            missing.append("tech_unlocked_list_missing")
            return _fail("tech_unlocked_list_missing", defined=False)
        detail["tech_unlocked"] = sorted(set(str(u) for u in unlocked))
        for nid in nodes:
            try:
                from content.data import get_tech_node
            except Exception:                            # noqa: BLE001
                get_tech_node = None                # type: ignore[assignment]
            if get_tech_node is not None and get_tech_node(nid) is None:
                missing.append(f"tech_node_unknown:{nid}")
                return _fail(f"tech_node_unknown:{nid}", defined=False)
            if nid not in unlocked:
                missing.append(f"tech_node_missing:{nid}")
                return _fail(f"tech_node_missing:{nid}")

    # ---- 科技等级 ----
    if "min_tech_level" in req:
        lv = _fin(tech.get("level"))
        detail["tech_level"] = lv
        if lv is None:
            missing.append("tech_level_missing")
            return _fail("tech_level_missing", defined=False)
        if lv < float(req["min_tech_level"]):
            reason = f"tech_level_below:{_fmt(lv)}<{_fmt(req['min_tech_level'])}"
            missing.append(reason)
            return _fail(reason)

    # ---- 时间 ----
    if "min_year" in req:
        yr = _int_or_none(getattr(state, "year", None))
        detail["year"] = yr
        if yr is None:
            missing.append("year_missing")
            return _fail("year_missing", defined=False)
        if yr < int(req["min_year"]):
            missing.append(f"year_before:{yr}<{req['min_year']}")
            return _fail(f"year_before:{yr}<{req['min_year']}")
    if "min_month" in req:
        mo = _int_or_none(getattr(state, "month", None))
        detail["month"] = mo
        if mo is None:
            missing.append("month_missing")
            return _fail("month_missing", defined=False)
        if mo != int(req["min_month"]):
            missing.append(f"month_mismatch:{mo}!={req['min_month']}")
            return _fail(f"month_mismatch:{mo}!={req['min_month']}")

    # ---- 贸易渠道 ----
    if "min_west" in req:
        w = _fin(tech.get("west"))
        detail["west"] = w
        if w is None:
            missing.append("west_missing")
            return _fail("west_missing", defined=False)
        if w < float(req["min_west"]):
            reason = f"west_below:{_fmt(w)}<{_fmt(req['min_west'])}"
            missing.append(reason)
            return _fail(reason)
    if req.get("maritime"):
        mar = getattr(state, "maritime", None)
        opened = mar.get("open") if isinstance(mar, dict) else None
        detail["maritime_open"] = opened
        if opened is None:
            missing.append("maritime_state_missing")
            return _fail("maritime_state_missing", defined=False)
        if not opened:
            missing.append("maritime_closed")
            return _fail("maritime_closed")

    # ---- 工艺改进的承载作坊（解锁前既有建筑）----
    if source == "craft" or req.get("workshops"):
        want_sites = int(req.get("min_sites", 1) or 1)
        need = tuple(req.get("workshops") or ())
        if need:
            sites = material_sites(state, entry["dim"], require_unlock=False)
            if not sites["defined"]:
                missing.append(f"sites_undefined:{sites['reason']}")
                return _fail(f"sites_undefined:{sites['reason']}", defined=False)
            detail["sites_ready"] = sites["sites"]
            detail["workshops"] = need
            ws = entry.get("workshop")
            if ws is not None and ws not in need:
                missing.append(f"workshop_not_in_requirements:{ws}")
                return _fail(f"workshop_not_in_requirements:{ws}")
            if len(sites["sites"]) < want_sites:
                missing.append(f"sites_below:{len(sites['sites'])}<{want_sites}")
                return _fail(f"sites_below:{len(sites['sites'])}<{want_sites}")
        elif want_sites > 0:
            missing.append("workshops_missing")
            return _fail("workshops_missing", defined=False)

    return {"ok": True, "defined": True, "reason": "",
            "detail": detail, "missing": missing,
            "allowed_sources": tuple(unlock)}


def unlock_material(state, material: Any, source: str, *,
                    via: Optional[str] = None, ensure_slot: bool = True,
                    log: Optional[List[str]] = None) -> Dict[str, Any]:
    """**唯一的解锁写入口**：前置满足即落记录，否则**拒绝并 raise（带 reason）**。

    落点（无 schema 迁移，均为既有容器）：
      · `state.tech["materials"][dim]` = `{material,label,source,via,year,month,turn}`
        （`state.tech` 整表随档保存/恢复 ⇒ 新子键自动随档；旧档缺该键读侧判 `unrecorded`）
      · `state.resources[dim]` 补空槽 `{"stock":0,"cap":0}`（`ensure_slot=True`，
        该容器亦整表落档；**不**改 `content.data_constants` 的维度/价格表）

    拒绝情形（全部 `MaterialTechError`，`reason` 可诊断）：
      `unregistered_material` / `source_not_allowed` / `already_unlocked` /
      `<前置 reason>`。
    """
    if state is None:
        raise TypeError("state 不能为 None")
    entry = resolve_material_tech(material)
    if entry is None:
        raise MaterialTechError(f"未注册的材料 {material!r}（不得解锁未登记材质）")
    if not isinstance(source, str) or source not in UNLOCK_SOURCES:
        raise MaterialTechError(f"解锁来源非法：{source!r}（合法：{UNLOCK_SOURCES}）")

    st = material_unlock_status(state, material)
    if st["status"] == STATUS_UNLOCKED:
        raise MaterialTechError(
            f"{entry['dim']} 已解锁（来源 {st['source']}），重复解锁会让来源记录分叉")
    if st["status"] == STATUS_UNRECORDED and st["reason"].startswith(
            "record_missing_but_tech_node_unlocked"):
        raise MaterialTechError(
            f"{entry['dim']} 解锁状态无法判定（{st['reason']}），须先人工裁决，"
            f"**不得臆断为已解锁或未解锁**")

    check = check_material_prereq(state, entry["dim"], source)
    if not check["ok"]:
        raise MaterialTechError(
            f"{entry['dim']} 按「{source}」解锁被拒：{check['reason']}")

    req = (entry.get("unlock") or {})[source]
    dim = str(entry["dim"])
    rec_via = via
    if rec_via is None:
        if source == "tech":
            rec_via = req.get("tech_node")
        elif source == "craft":
            rec_via = (tuple(req.get("workshops") or ()) or (None,))[0]
        else:
            rec_via = "市舶" if req.get("maritime") else "西学东渐"
    if rec_via is not None and not isinstance(rec_via, str):
        raise MaterialTechError(f"{dim} 的解锁载体 via 非法 {rec_via!r}")

    tech = _tech_dict(state)
    records = tech.get(MATERIALS_RECORD_KEY)
    if records is None:
        records = {}
        tech[MATERIALS_RECORD_KEY] = records
    elif not isinstance(records, dict):
        raise MaterialTechError(
            f"state.tech[{MATERIALS_RECORD_KEY!r}] 畸形（{type(records).__name__}），"
            f"拒绝覆写（不得静默清空既有解锁记录）")

    if ensure_slot:
        res = getattr(state, "resources", None)
        if isinstance(res, dict) and dim not in res:
            res[dim] = {"stock": 0, "cap": 0}

    rec = {
        "material": dim,
        "label": entry["label"],
        "source": source,
        "via": rec_via,
        "year": _int_or_none(getattr(state, "year", None)),
        "month": _int_or_none(getattr(state, "month", None)),
        "turn": _int_or_none(getattr(state, "turn", None)),
    }
    records[dim] = rec
    invalidate_material_tech_cache()
    if isinstance(log, list):
        kind = "架空后世材料" if entry["fictional"] else "宋代实物材料"
        log.append(f"[建材] {entry['label']}（{kind}）经「{source}」解锁"
                   f"（载体：{rec_via}），此前该材不可生产、不可交易")
    return dict(rec)


# =============================================================================
# 八、钩子（供 market_price / construction 消费；**本模块不改这些文件**）
# =============================================================================

def unlock_materials_for_node(state, node_id: Any, *,
                              log: Optional[List[str]] = None) -> Dict[str, Any]:
    """某科技节点点亮后，按注册表解锁**以它为前置**的新材（Lead 科技线的单行接入点）。

    返回 `{"unlocked": [记录...], "skipped": [{"material","reason"}]}`：
      · `skipped` 逐条给出 `reason`（前置等级/时间未到、已解锁、状态无法判定…），
        调用方可原样记日志，**不得**静默丢成"没这事"；
      · 本函数**只解锁 `tech` 通道**（工艺/贸易通道各有各的触发点，不得在此偷跑）。

    非法 `node_id`（非 str）⇒ `raise TypeError`（拒绝式）。
    """
    if not isinstance(node_id, str) or not node_id.strip():
        raise TypeError(f"node_id 必须是非空 str（收到 {node_id!r}）")
    unlocked: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for key, entry in MATERIAL_TECH_UNLOCKS.items():
        req = (entry.get("unlock") or {}).get("tech")
        if not req:
            continue
        if node_id not in tuple(req.get("tech_nodes") or ()):
            continue
        if is_material_unlocked(state, key) is True:
            continue
        try:
            unlocked.append(unlock_material(state, key, "tech", log=log))
        except MaterialTechError as e:
            skipped.append({"material": str(entry["dim"]), "reason": str(e)})
    return {"unlocked": unlocked, "skipped": skipped}


def material_availability(state, material: Any) -> Dict[str, Any]:
    """某材的**可用性**（纯读数）。

    返回 `{"defined","available","status","reason","sites"}`：
      · `available` 三态：`True` 已解锁且有产地 / `False` 已登记但未解锁（或无产地）/
        `None` **读数未定义**（unrecorded / 未注册 / 产地读不到）。
      · `reason` 必填且可诊断；**未解锁绝不用"价格 0"或"缺货"伪装**。
    """
    st = material_unlock_status(state, material)
    base = {"defined": st["defined"], "available": None,
            "status": st["status"], "reason": st["reason"], "sites": None}
    if st["status"] == STATUS_UNKNOWN:
        base["reason"] = "unregistered_material"
        return base
    if st["status"] == STATUS_UNRECORDED:
        base["reason"] = f"unrecorded:{st['reason']}" if st["reason"] else "unrecorded"
        return base
    if st["status"] == STATUS_LOCKED:
        base["available"] = False
        base["reason"] = "not_unlocked"
        return base
    sites = material_sites(state, material)
    if not sites["defined"]:
        base["reason"] = f"sites_undefined:{sites['reason']}"
        return base
    base["sites"] = sites["sites"]
    base["available"] = bool(sites["sites"])
    base["reason"] = "" if base["available"] else "no_workshop_site"
    return base


def effective_material_price(state, material: Any, base_price: Any) -> Optional[float]:
    """价格钩子：**未解锁 ⇒ `None`，绝不是 0**（价 0 = 白给，是 B4-2 要治的病）。

    * 材料未注册 / 解锁状态读不到 ⇒ `None`（缺失 ≠ 0）；
    * `base_price` 为 `None` ⇒ `None`（缺失，不回落 0）；
    * `base_price` 非有限或为负 ⇒ `raise ValueError`（拒绝式，不静默当 0）；
    * **架空后世材料**（`fictional: True`）的 `base_price == 0` ⇒ `raise ValueError`
      （内容表漏配基准价就放行 0，等于把"科技解锁"降级成"白送材料"，正犯本条）；
    * 已解锁 ⇒ 返回 `float(base_price)`（供需涨价因子由 `market_price` 自行叠加，
      本钩子**只管"能不能定价"**，不改价制口径）。
    """
    entry = resolve_material_tech(material)
    st = material_unlock_status(state, material)
    if st["status"] != STATUS_UNLOCKED:
        return None
    if base_price is None:
        return None
    if isinstance(base_price, bool) or not isinstance(base_price, (int, float)):
        raise ValueError(f"base_price 必须是数值或 None，得 {base_price!r}")
    bp = float(base_price)
    if not math.isfinite(bp):
        raise ValueError(f"base_price 非有限值 {base_price!r}（不得回落 0）")
    if bp < 0:
        raise ValueError(f"base_price 为负 {base_price!r}（不得当 0 处理）")
    if bp == 0 and entry is not None and entry.get("fictional") is True:
        raise ValueError(
            f"{entry['dim']} 是架空后世材料，基准价不得为 0"
            f"（「科技 ≠ 免费材料」：0 价等于白送，须补 MATERIAL_PRICE_BASE）")
    return bp


def material_tradable(state, material: Any) -> Optional[bool]:
    """可否交易：`True` / `False`（已登记未解锁）/ `None`（**读数未定义**）。"""
    return material_availability(state, material)["available"]
