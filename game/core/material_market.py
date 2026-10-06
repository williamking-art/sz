# -*- coding: utf-8 -*-
"""B4-1 · 建材实物化：有来源的本地建材市场（规格 `market-civilian-economy` B4-1）

## 为什么有这个模块

B4-3/4/5/6 已把「造价＝Σ材料×单价」「凹函数加速」「赶工预算独立」「三种取材路径
分别记账」落到 `core/construction_cost.py` 与 `settlement_tech._settle_projects`，
但**材料本身仍然没有市场**（实测）：

1. 工程领料走 `state.resources[dim]["stock"]` 的**直接扣减**——是"扣库存"，
   **没有买方、没有价格、没有货款接收方**；
2. `MATERIAL_PRICE_BASE` 里已有 `timber=50`/`stone=30`/`iron=250`，
   但这张表**只作估值锚，从不参与成交**（B2-5：基准价不得改写）；
3. B4-1 的验收断言要求「材料**有来源、有货款接收方、有实物消耗**（三方对账）」。

本模块补的就是这一段：**把建材做成有来源、可成交、可对账的本地市场**。

## 一、口径（硬约束对齐）

1. **成交唯一入口**：所有建材成交都经`core/market.py::trade_goods`
   （双向原子、三重上限 `成交量 ≤ min(需求量, 购买力, 可售量)`、`trade_id` 幂等）。
   **本模块不另写第二套成交算法**；只做「取价 → 校验 → 调用 → 写回真实槽位」。
2. **价格单点**：一律 `core/market_price.py::effective_buy_price`
   （官定 > **本路动态成交均价** > 基准价）。本路动态价的键是
   `pref_good_key(pref, dim)`＝`"京畿路|木"`，成交后由 `record_trade_price`
   回写该键（**不改基准表**）。
3. **参数名纪律**：一律用 `pref`（prefecture，`state.prefectures` 的键），
   **不用 `route`**——本仓库另有真义路线的 `route`（`state.routes`、行军路径）。
4. **钱货只落既有槽位**（POP 挂载律）：买方只能是
   `state.treasury`（国库）或某个路级 POP 的 `wealth`；卖方只能是
   `state.resources[dim]["stock"]`（仓储/官仓）或某个路级 POP 的 `goods`。
   **本模块不新建任何存量账本**：所有可售量都是从既有槽位**派生**的视图，
   成交结果直接写回原槽位。
5. **缺失 ≠ 0 ≠ 1.0**：仓储槽位缺 `stock`、材料缺基准价、POP 缺 `goods`
   一律返回 `None` ＋ `known=False`/`reason`，**绝不回落 0/1.0 假装有货或没钱**。
6. **拒绝式处理非法输入**：负量/非数值/小数建材量/未知材料/不存在的路或持有人
   一律 `ok=False, reason="invalid"`，**不做善意修正**。

## 二、单位与计量（不得含糊）

`state.resources[dim]["stock"]` 的单位由 `content.data_constants.RAW_UNITS` 决定，
市场**采购单位**由本模块 `MATERIAL_SPECS` 声明，两者用显式系数换算：

| dim | 名称 | 市场采购单位 | 库存单位（仓） | 换算 `units_per_stock` | 来源 |
|---|---|---|---|---|---|
| `timber` | 木 | **材** | 根（`RAW_UNITS`） | 1.0（1 材 = 1 根） | 仓储 + 路级 POP 持货 |
| `stone` | 石 | **方** | 方（`RAW_UNITS`） | 1.0（1 方 = 1 方） | 仓储 + 路级 POP 持货 |
| `iron` | 铁 | **斤** | 斤（`RAW_UNITS`） | 1.0（1 斤 = 1 斤） | 仓储 + 路级 POP 持货 |
| `brick` | 砖 | 块 | — | — | **尚未建模，不可成交** |

- **系数声明为「参数待裁」**（《建议》§12-4）：当前三材均为 1.0，
  因为仓库存量口径（根/方/斤）与营建采购口径（材/方/斤）本就一致；
  若日后改为按方尺计料，只改 `MATERIAL_SPECS` 的系数即可，
  **代码与测试都不需要改**（测试锁的是换算*关系*，不是具体数值）。
- **价格按库存单位报价**（`MATERIAL_PRICE_BASE` 挂在 `RAW_UNITS` 单位上），
  交给 `trade_goods` 的**单件价＝库存单位价 ÷ `units_per_stock`**
  （1 采购单位 = `1 / units_per_stock` 个库存单位），换算只在 `material_price`
  一处发生（口径单点）。
- **建材不可分割**：`divisible=False` 的材料必须整数计量，`1.5 材` 一律拒绝
  （不让 `trade_goods` 的 `int(round())` 静默取整）。
- **不接受中文别名**：`RAW_DIMS_14`（外邦 14 维）里`石`/`木`是另一套语义，
  为免跨子系统混料，`materials` 的键必须是**仓储维度名**（`timber`/`stone`/`iron`），
  写`"木"`一律 `unknown_material`。
- **金银铜不作为建材**：它们是「计价/货币资产」而非实物材料（tasks §6 参数待裁），
  故**不**注册进 `MATERIAL_SPECS`；要变成营造材料必须显式 `register_material_spec`。

## 三、可替代性（显式声明，不得静默换料）

1. 替代关系写在 `MATERIAL_SUBSTITUTES`（**单一声明表**），每条含
   `to`（替代材）、`acceptability`（`1` 单位替代材可折抵多少原材功能量，`∈(0,1]`）、
   `reason`（为什么能替代）。
2. **两道闸门**才允许替代：① 调用方**显式传** `allow_substitutes=[...]`；
   ② 替代材必须在 `MATERIAL_SUBSTITUTES` 里**已声明**。
   默认 `allow_substitutes=None` ⇒ **一材不换**，缺口如实记为`unmet`。
3. 每次替代都写进 `substitutions[]`（`requested_dim / provided_dim / qty /
   acceptability / accepted / reason`），可审计；**不接受"悄悄换成别的料"**。
4. 接受度非法（`≤0` 或 `>1`）⇒ 该条替代被**拒绝**并如实标注，不按 1.0 兜底。

## 四、取材路径（B4-6 的三条路径在本模块中的对应）

| 渠道 | 买方 | 卖方（货来源） | 货款去向 | `channel` |
|---|---|---|---|---|
| ① 市场购料 | 路级 POP（民间自建） | 路级 POP 持货 | 卖方 POP `wealth` | `market_purchase` |
| ① 市场购料 | 国库（官营造） | 路级 POP 持货（民间商户） | 商户 POP `wealth` | `market_purchase` |
| ① 市场购料 | 路级 POP | 仓储（官仓售料） | **国库** `state.treasury` | `market_purchase` |
| ② 官仓领料 | 国库 | 仓储 | **无货款**（同一主体内部调拨），只记基准估价 | `warehouse_issue` |
| ③ 民间自建 | POP | POP | 卖方 POP `wealth` | `market_purchase` |

- **②官仓领料不是成交**，故**不调**`trade_goods`（该函数强制 `buyer≠seller`，
  自购自卖本就不是市场）；它由 `issue_material` 显式实现，**没有任何钱腿**，
  只把货从 `state.resources[dim]["stock"]` 扣出并回报**基准估价**——
  这样 ① 与 ② **分别记账、不会双计**（B4-6）。
- **国库买官仓＝自购自卖，直接拒绝**（`reason="self_dealing"`），防止左手倒右手
  造货币或造货。

## 五、迁移策略（不动存量字段，不新增账本）

1. **不新增任何 `state` 字段**：`reserved="projects"` 时预留量由既有
   `state.projects[*]["_mat_left_<dim>"]`（在营工程剩余申领）**派生**，
   本模块只读、不写工程台账。
2. **接线由调用方决定**（本模块**不自行接线**）：最小接入是 `settlement_tech`
   在现有「扣仓储」之前调一次 `settle_material_purchase`，把购到的料落进
   `state.resources[dim]["stock"]`，其余结算逻辑一行不动（详见 Lead 的接入建议）。
3. **旧档兼容**：`state.resources` 缺该 dim 槽 ⇒ `known=False/None`（**不自动建槽**、
   不凭空生成库存）；`dynamic_prices` 无路级键 ⇒ 回落基准价（`price_kind="base"`）。
4. **新材启用**（B4-2「科技 ≠ 免费材料」）：先在
   `content.data_constants.register_raw_material(dim, unit, price)` 注册
   **维度＋单位＋基准价**，再 `register_material_spec` 声明
   **采购单位／换算系数／来源**，二者缺一即**不可成交**（`no_source`/`no_base_price`）。

## 六、只读读数（不改任何状态）

`material_market_readout` 按 `market_readout.py` 的范式给面板逐材列出
单位／存量／预留／可售／价格与价格口径／可替代项／可成交性，
**纯派生、失败不抛、有界截断**，与 `inventory_ledger` 同风格。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from core.market import sellable_stock, trade_goods
from core.market_price import (
    discover_price, effective_buy_price, pref_good_key, record_trade_price,
)

__all__ = [
    "MATERIAL_SCHEMA_VERSION",
    "MATERIAL_SPECS", "MATERIAL_SUBSTITUTES",
    "CARRIERS", "BUYERS", "CHANNELS", "MaterialReason",
    "material_spec", "register_material_spec",
    "convert_stock_to_market", "convert_market_to_stock",
    "material_stock", "project_reservations", "material_supply",
    "material_price", "project_material_price",
    "quote_material", "buy_material", "issue_material",
    "settle_material_purchase", "material_market_readout",
]

#: 读数/成交结果结构版本
MATERIAL_SCHEMA_VERSION = 1

#: 卖方货载（carrier）：仓储槽位 or 路级 POP 持货
CARRIERS = ("warehouse", "pop")
#: 买方（buyer）：国库 or 路级 POP
BUYERS = ("treasury", "pop")
#: 渠道（channel）：市场购料 vs 官仓领料（B4-6 的①②，两条路径分别记账）
CHANNELS = ("market_purchase", "warehouse_issue")


class MaterialReason:
    """结果字段常量（供调用方/面板引用，避免各处硬编码字符串）。"""

    OK = "ok"
    NO_DEMAND = "no_demand"                     # 需求为 0（不是未满足原因）
    NO_STOCK = "no_stock_local"                 # 本地无货（无虚拟供给）
    NO_MONEY = "insufficient_purchasing_power"  # 购买力/预算不足
    UNKNOWN_STOCK = "unknown_stock"             # 存量**未定义**（≠0）
    UNKNOWN_MATERIAL = "unknown_material"       # 未注册建材
    NO_SOURCE = "no_source"                     # 已登记但无来源（如未建模的砖）
    NO_BASE_PRICE = "no_base_price"             # 缺基准价（≠0 价）
    UNKNOWN_PRICE = "unknown_price"             # 价格不可定价
    INVALID = "invalid"                         # 拒绝式：非法输入
    DUPLICATE = "duplicate_trade"               # 同回合同 trade_id 幂等拦截
    SELF_DEALING = "self_dealing"               # 国库买官仓＝自购自卖
    NO_SELLER = "no_seller"                     # 卖方持有人不存在
    NO_BUYER = "no_buyer"                       # 买方持有人不存在


# ====================================================== 材料规格（单位/来源/换算）
#: 建材规格**单一声明表**。`units_per_stock`＝`1 库存单位 = 多少采购单位`。
#: `tradable=False` 表示"已登记但**尚无来源**"，一律拒绝成交（不凭空产出）。
MATERIAL_SPECS: Dict[str, Dict[str, Any]] = {
    "木": {
        "name": "木", "unit": "材", "stock_unit": "根", "units_per_stock": 1.0,
        "divisible": False, "tradable": True,
        "source": "仓储 state.resources['木']（官仓/仓储，全国口径）＋ 路级 POP 持货",
        "note": "仓按根本仓、营建按材计价：1 材 = 1 根（换算系数参数待裁）",
    },
    "石": {
        "name": "石", "unit": "方", "stock_unit": "方", "units_per_stock": 1.0,
        "divisible": False, "tradable": True,
        "source": "仓储 state.resources['石']（官仓/仓储，全国口径）＋ 路级 POP 持货",
        "note": "仓按方、营建按方计价：1 方 = 1 方（换算系数参数待裁）",
    },
    "铁": {
        "name": "铁", "unit": "斤", "stock_unit": "斤", "units_per_stock": 1.0,
        "divisible": False, "tradable": True,
        "source": "仓储 state.resources['铁']（官仓/仓储，全国口径）＋ 路级 POP 持货",
        "note": "五金铁料（铁钉/铁件）：1 斤 = 1 斤",
    },
    "brick": {
        "name": "砖", "unit": "块", "stock_unit": "块", "units_per_stock": 1.0,
        "divisible": False, "tradable": False,
        "source": "尚未建模：全库无 brick 仓储维度、无生产链、无基准价",
        "note": "B4-2「科技 ≠ 免费材料」：砖须先注册维度＋基准价＋来源才可成交",
    },
}

#: **显式**替代声明表：`原材 -> [(替代材, 接受度, 理由), ...]`。
#: 只有本表声明过的替代材才可能被启用，且**必须**调用方显式放行
#: （`settle_material_purchase(allow_substitutes=[...])`）。
MATERIAL_SUBSTITUTES: Dict[str, Tuple[Dict[str, Any], ...]] = {
    "石": ({"to": "木", "acceptability": 0.6,
               "reason": "石料不足时以木料替代（土木混合夯筑/木骨）：1 材折抵 0.6 方"},),
    "木": ({"to": "石", "acceptability": 0.5,
                "reason": "木料不足时以石料替代（砖石代木梁/柱础）：1 方折抵 0.5 材"},),
}


def _num(v: Any) -> Optional[float]:
    """安全取数：非数值/NaN/Inf → `None`（**不回落 0**，缺失≠0）。"""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _exact_int(v: Any) -> Optional[int]:
    """整数化**严格**版：带小数或非数值 → `None`（拒绝，不静默取整）。"""
    f = _num(v)
    if f is None:
        return None
    if abs(f - round(f)) > 1e-9:
        return None
    return int(round(f))


def _read_int(v: Any) -> Optional[int]:
    """读存量（与 `market._int` 同源：四舍五入）；非数值 → `None`。"""
    f = _num(v)
    return None if f is None else int(round(f))


# ====================================================== 规格与单位换算
def material_spec(dim: Any) -> Optional[Dict[str, Any]]:
    """取建材规格（只读）。未知 dim → `None`（**不新建规格**，缺失不作 0）。"""
    if not isinstance(dim, str) or not dim:
        return None
    spec = MATERIAL_SPECS.get(dim)
    return dict(spec) if isinstance(spec, dict) else None


def register_material_spec(dim: str, *, name: str, unit: str,
                           stock_unit: str, units_per_stock: float,
                           source: str, divisible: bool = False,
                           tradable: bool = True, note: str = "") -> Dict[str, Any]:
    """注册一种建材的**单位/来源/换算**（B4-1/B4-2 启用闸门）。

    **刻意不写 `MATERIAL_PRICE_BASE`**：价格是 `market_price` 的单点口径，
    新材的价格须由 `content.data_constants.register_raw_material(dim, unit, price)`
    写入基准表，本函数只声明单位与来源。
    已存在的 dim 默认**拒绝覆盖**（`duplicate_material`），避免静默改口径。
    """
    if not isinstance(dim, str) or not dim:
        raise ValueError("register_material_spec 需要非空 dim")
    if dim in MATERIAL_SPECS:
        return {"ok": False, "reason": "duplicate_material", "dim": dim,
                "detail": f"建材 {dim!r} 已登记；改口径请显式改 MATERIAL_SPECS"}
    ratio = _num(units_per_stock)
    if ratio is None or ratio <= 0:
        return {"ok": False, "reason": "invalid", "dim": dim,
                "detail": "units_per_stock 必须是 > 0 的有限数值（缺失≠1.0）"}
    if not unit or not stock_unit or not source:
        return {"ok": False, "reason": "invalid", "dim": dim,
                "detail": "unit / stock_unit / source 必须显式声明（不得含糊）"}
    MATERIAL_SPECS[dim] = {
        "name": str(name or dim), "unit": str(unit), "stock_unit": str(stock_unit),
        "units_per_stock": float(ratio), "divisible": bool(divisible),
        "tradable": bool(tradable), "source": str(source), "note": str(note or ""),
    }
    return {"ok": True, "dim": dim, "spec": dict(MATERIAL_SPECS[dim])}


def convert_stock_to_market(dim: str, stock_qty: Any) -> Optional[float]:
    """库存单位 → 市场采购单位。未知 dim/非法量 → `None`（**不回落 0**）。"""
    spec = material_spec(dim)
    q = _num(stock_qty)
    if spec is None or q is None:
        return None
    return q * float(spec["units_per_stock"])


def convert_market_to_stock(dim: str, market_qty: Any) -> Optional[float]:
    """市场采购单位 → 库存单位（`state.resources[dim]["stock"]` 的口径）。"""
    spec = material_spec(dim)
    q = _num(market_qty)
    if spec is None or q is None:
        return None
    return q / float(spec["units_per_stock"])


# ====================================================== 存量与可售（纯派生）
def material_stock(state, dim: str) -> Optional[int]:
    """**已确权**仓储存量（`state.resources[dim]["stock"]`）。

    ⚠️ **不含归属待定库存**（`state.pending_stock`，6.33 用户裁定）：
    待定料**存放地 ≠ 货主**，按裁定**不得**被采购/出售/投料/计税，
    故本函数（市场采购与可售判定的入口）**刻意不读它**。
    待定实物量另行由 `production_chain.pending_total(state, dim)` 读取，
    并在 `market_readout.inventory_ledger` 中以 `pending` 单列呈现。

    - `state.resources` 非 dict、或该 dim 槽缺失、或槽内无 `stock` 键
      ⇒ 返回 `None`（**未定义**，**不是 0**；也不自动建槽、不凭空生成库存）。
    """
    res = getattr(state, "resources", None)
    if not isinstance(res, dict):
        return None
    slot = res.get(dim)
    if not isinstance(slot, dict):
        return None
    return _read_int(slot.get("stock"))


def _pop_of(state, pref: Any, pop_cls: Any) -> Optional[dict]:
    """取路级 POP 字典；路或阶层缺失 → `None`（**不臆造持有人**）。"""
    if not isinstance(pref, str) or not pref:
        return None
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    pf = prefs.get(pref)
    pops = pf.get("pops") if isinstance(pf, dict) else None
    if not isinstance(pops, dict):
        return None
    pop = pops.get(pop_cls)
    return pop if isinstance(pop, dict) else None


def _pop_stock(pop: Optional[dict], dim: str) -> Optional[int]:
    """POP 持货存量；POP 不存在或**无 `goods` 槽**（旧档）→ `None`（≠0）。

    🔴 2026-10-03：建材按 `goods[治所][dim]` 州府桶存放，须走 `goods_amount()`
    读「扁平项 + Σ桶」，裸取 `goods.get(dim)` 会把已入库的料读成 0。
    """
    if not isinstance(pop, dict):
        return None
    goods = pop.get("goods")
    if not isinstance(goods, dict):
        return None
    from core.foundation.ledger.material_holding import goods_amount
    v = goods_amount(goods, dim)
    return _read_int(v if v is not None else 0)


def project_reservations(state, dim: Optional[str] = None) -> Dict[str, int]:
    """在营工程对材料的**预留申领**（派生视图，不写工程台账）。

    口径：`state.projects[*]["_mat_left_<dim>"]` 是"尚未领足的材料"，
    在建（`status="building"`）期间构成对仓储的合法申领；
    仓储是**全国口径**，故不按路过滤（跨路也占用同一批货）。
    `dim=None` 返回全部材料的预留表。
    """
    out: Dict[str, int] = {}
    projects = getattr(state, "projects", None)
    if not isinstance(projects, dict):
        return out
    for proj in projects.values():
        if not isinstance(proj, dict) or proj.get("status") != "building":
            continue
        for key, val in (proj or {}).items():
            if not str(key).startswith("_mat_left_"):
                continue
            mdim = str(key)[len("_mat_left_"):]
            if dim is not None and mdim != dim:
                continue
            left = _num(val)
            if left is None or left <= 0:
                continue
            out[mdim] = out.get(mdim, 0) + int(round(left))
    return out


def _resolve_reserved(state, reserved: Any, dim: str) -> Optional[int]:
    """预留量解析：`int` 显式 / `"projects"` 派生 / 其他 → `None`（非法）。"""
    if reserved is None:
        return 0
    if isinstance(reserved, str):
        if reserved != "projects":
            return None
        return int(project_reservations(state, dim).get(dim, 0))
    r = _num(reserved)
    if r is None or r < 0:
        return None
    return int(round(r))


def material_supply(state, *, pref: Any, dim: str, carrier: str = "warehouse",
                    seller_pop: str = "商人", reserved: Any = 0) -> Dict[str, Any]:
    """给定路的**可售量**（派生：真实持仓 − 预留），并如实标注持仓来源。

    ⚠️ 口径诚实：`carrier="warehouse"` 时持仓来自 `state.resources`
    （**全国仓储**，不是本路民间库存）；本路只是**计价与结算的域**，
    `scope` 字段会如实写明，不把官仓冒充本路市集（tasks §1.1）。

    返回 `{dim, carrier, scope, holder, stock, reserved, sellable, unit,
    stock_unit, sellable_unit, known, reason, note}`；
    - `stock` / `sellable` 一律是**库存单位**（与 `state.resources` 同口径）；
      `sellable_unit` 才是市场采购单位——**两者不得混用**；
    - `stock`/`sellable` 为 `None` ⇒ **未定义**（缺失≠0）。
    """
    spec = material_spec(dim)
    base = {
        "schema_version": MATERIAL_SCHEMA_VERSION, "dim": dim, "carrier": carrier,
        "scope": None, "holder": None, "stock": None, "reserved": None,
        "sellable": None, "unit": (spec or {}).get("unit"),
        "stock_unit": (spec or {}).get("stock_unit"), "sellable_unit": None,
        "known": False, "reason": MaterialReason.UNKNOWN_MATERIAL, "note": None,
    }
    if spec is None:
        return base
    if carrier not in CARRIERS:
        base.update(reason=MaterialReason.INVALID, known=False,
                    note=f"carrier 非法：{carrier!r}（允许：{CARRIERS}）")
        return base
    rsv = _resolve_reserved(state, reserved, dim)
    if rsv is None:
        base.update(reason=MaterialReason.INVALID, known=False,
                    note=f"reserved 非法：{reserved!r}（整数或 'projects'）")
        return base
    base["reserved"] = rsv
    if carrier == "warehouse":
        stock = material_stock(state, dim)
        base.update(scope="national_warehouse", holder="state.resources",
                    note=spec.get("source"))
    else:
        pop = _pop_of(state, pref, seller_pop)
        stock = _pop_stock(pop, dim)
        base.update(scope="route_pop", holder=f"{pref}|{seller_pop}",
                    note=f"路级 {seller_pop} POP 持货（民间现货）")
        if pop is None:
            base.update(reason=MaterialReason.NO_SELLER, note=
                        f"卖方持有人 {pref!r}/{seller_pop!r} 不存在（不臆造卖方）")
            return base
    base["stock"] = stock
    if stock is None:
        base.update(reason=MaterialReason.UNKNOWN_STOCK,
                    note="存量未定义（槽位缺失或旧档无 stock）——不是 0")
        return base
    # 可售量口径**单点**在 `market.sellable_stock`（持仓 − 预留），本模块不重算
    sellable = sellable_stock(seller={"goods": {dim: int(stock)}}, dim=dim,
                              reserved=int(rsv))
    base.update(sellable=sellable, known=True, reason=MaterialReason.OK,
                sellable_unit=convert_stock_to_market(dim, sellable))
    return base


# ====================================================== 价格（口径单点：market_price）
def material_price(state=None, *, pref: Any, dim: str,
                   gov_price: Optional[float] = None,
                   use_dynamic: bool = True) -> Dict[str, Any]:
    """建材**本路买入价**（含单位换算）。

    复用 `market_price.effective_buy_price`（官定 > 本路动态 > 基准），
    再按 `units_per_stock` 把「库存单位价」折算为「市场采购单位单价」
    （1 采购单位 = `1/units_per_stock` 库存单位）——**全模块唯一的换算点**。
    价格不可定价时 `unit_price=None`（**不按 0 价成交**）。
    """
    spec = material_spec(dim)
    out = {
        "schema_version": MATERIAL_SCHEMA_VERSION, "dim": dim,
        "unit": (spec or {}).get("unit"), "stock_unit": (spec or {}).get("stock_unit"),
        "units_per_stock": (spec or {}).get("units_per_stock"),
        "price_per_stock": None, "unit_price": None,
        "price_kind": None, "price_reason": None, "dynamic_key": None,
        "reason": MaterialReason.UNKNOWN_MATERIAL,
    }
    if spec is None:
        out["price_reason"] = "未注册建材（无单位声明，拒绝成交）"
        return out
    out["dynamic_key"] = pref_good_key(pref, dim)
    r = effective_buy_price(dim=dim, state=state, gov_price=gov_price,
                            pref=pref, use_dynamic=use_dynamic)
    price = _num(r.get("price"))
    out.update(price_kind=r.get("kind"), price_reason=r.get("reason"))
    if price is None or price <= 0:
        out.update(reason=MaterialReason.NO_BASE_PRICE,
                   price_reason=r.get("reason") or "无可用价格（缺失，不作 0）")
        return out
    out.update(price_per_stock=price,
               unit_price=round(price / float(spec["units_per_stock"]), 6),
               reason=MaterialReason.OK)
    return out


def project_material_price(state, *, pref: Any, dim: str,
                           demand_qty: Optional[float],
                           supply_qty: Optional[float]) -> Dict[str, Any]:
    """本月**价格发现**预测（纯函数，不写 `state`）。

    复用 `market_price.discover_price`，上期价取**本路**动态价（路级键
    `pref_good_key(pref, dim)`）；不可定价时 `price=None`（无货不可定价，
    由 `trade_goods` 的 `no_stock_local` 表达"没买到"，不是"价格无限高"）。
    """
    cur = material_price(state=state, pref=pref, dim=dim)
    prev = cur.get("price_per_stock") if cur.get("price_kind") == "dynamic" else None
    r = discover_price(dim=dim, demand_qty=demand_qty, supply_qty=supply_qty,
                       prev_price=prev)
    r = dict(r)
    r["dynamic_key"] = pref_good_key(pref, dim)
    r["unit"] = (material_spec(dim) or {}).get("unit")
    return r


# ====================================================== 报价（只读）
def quote_material(state, *, pref: Any, dim: str, qty: Optional[Any] = None,
                   carrier: str = "warehouse", seller_pop: str = "商人",
                   reserved: Any = 0, gov_price: Optional[float] = None) -> Dict[str, Any]:
    """**只读**报价：可售量＋本路买入价＋单位＋可替代项（**不改任何状态**）。

    面板与调用方预检都用它；真正的成交入口是 `buy_material`/`settle_material_purchase`。
    """
    spec = material_spec(dim)
    out = {
        "schema_version": MATERIAL_SCHEMA_VERSION, "dim": dim,
        "name": (spec or {}).get("name"), "unit": (spec or {}).get("unit"),
        "stock_unit": (spec or {}).get("stock_unit"), "requested": None,
        "supply": None, "price": None, "tradeable": False,
        "reason": MaterialReason.UNKNOWN_MATERIAL, "detail": None,
        "substitutes": [], "warnings": [],
    }
    if spec is None:
        out["detail"] = f"未注册建材：{dim!r}（键须为仓储维度名，不接受中文别名）"
        return out
    if not spec.get("tradable", True):
        out.update(reason=MaterialReason.NO_SOURCE,
                   detail=f"{spec.get('name')} 尚无来源（{spec.get('source')}）")
    sup = material_supply(state, pref=pref, dim=dim, carrier=carrier,
                          seller_pop=seller_pop, reserved=reserved)
    out["supply"] = sup
    px = material_price(state=state, pref=pref, dim=dim, gov_price=gov_price)
    out["price"] = {k: px.get(k) for k in
                    ("unit_price", "price_per_stock", "price_kind", "price_reason",
                     "dynamic_key", "reason")}
    # 可替代项：只列**已声明**的替代材；启用仍需调用方显式放行
    for rule in MATERIAL_SUBSTITUTES.get(dim, ()):
        acc = _num(rule.get("acceptability"))
        out["substitutes"].append({
            "to": rule.get("to"), "acceptability": acc, "reason": rule.get("reason"),
            "declared": True, "enabled": False,
            "note": "仅声明；settle_material_purchase(allow_substitutes=[...]) 才启用",
        })
    if qty is not None:
        want = _exact_int(qty) if not spec.get("divisible", False) else _num(qty)
        if want is None or want < 0:
            out.update(reason=MaterialReason.INVALID, detail="qty 非法（需非负数值）")
            return out
        out["requested"] = want
    # 不可成交原因按**固定优先级**判定，避免"无来源"被"缺基准价"顶掉：
    #   非法输入 → 无来源 → 持有人缺失 → 缺价 → 存量未定义 → 无货
    sup_reason = sup.get("reason")
    if not spec.get("tradable", True):
        pass                                   # 保持 no_source（优先级最高）
    elif sup_reason == MaterialReason.INVALID:
        out.update(reason=MaterialReason.INVALID, detail=sup.get("note"))
    elif sup_reason == MaterialReason.NO_SELLER:
        out.update(reason=MaterialReason.NO_SELLER, detail=sup.get("note"))
    elif px.get("reason") == MaterialReason.NO_BASE_PRICE:
        out.update(reason=MaterialReason.NO_BASE_PRICE,
                   detail="缺基准价（缺失≠0）：先在 MATERIAL_PRICE_BASE 注册基准价")
    elif sup_reason == MaterialReason.UNKNOWN_STOCK:
        out.update(reason=MaterialReason.UNKNOWN_STOCK, detail=sup.get("note"))
    elif sup.get("sellable") is not None and sup["sellable"] <= 0:
        out.update(reason=MaterialReason.NO_STOCK,
                   detail="本地无可售量（无货不能买，绝不虚拟供给）")
    out["tradeable"] = (out["reason"] == MaterialReason.OK)
    return out


# ====================================================== 成交（唯一入口：trade_goods）
def _line_base(dim: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": MATERIAL_SCHEMA_VERSION, "dim": dim,
        "name": spec.get("name"), "unit": spec.get("unit"),
        "stock_unit": spec.get("stock_unit"),
        "units_per_stock": spec.get("units_per_stock"),
        "requested": 0, "traded": 0, "paid": 0, "value": 0.0, "unmet_qty": 0,
        # 替代当量：`covered` 是"折算成原材功能量"的覆盖数（与 `traded` 同单位），
        # `substitute_qty` 是替代材本身的成交数（**另一种单位，不可与 traded 相加**）。
        "covered": 0.0, "substitute_qty": 0,
        "unit_price": None, "price_kind": None,
        "channel": None, "carrier": None, "seller": None, "buyer": None,
        # `applied=True` 表示**本次调用真的动了 state**。
        # `duplicate_trade` 时 `trade_goods` 会回传首次结果但**不转移**，
        # 此时 `applied=False`——写回逻辑必须据此跳过，否则二次扣款/二次发货。
        "applied": False, "first_result": None,
        "reason": MaterialReason.OK, "detail": None, "substitution": [],
    }


def buy_material(state, *, pref: Any, dim: str, qty: Any,
                 buyer: str = "treasury", buyer_pop: str = "士绅",
                 carrier: str = "pop", seller_pop: str = "商人",
                 reserved: Any = 0, gov_price: Optional[float] = None,
                 trade_id: Optional[str] = None) -> Dict[str, Any]:
    """**建材成交**（单材原子）：钱↔货双向转移，全部经 `trade_goods`。

    - `buyer="treasury"` ⇒ 钱从 `state.treasury` 出；货落**仓储**（工程预留入库）；
    - `buyer="pop"` ⇒ 钱从该 POP 的 `wealth` 出；货落该 POP 的 `goods`；
    - `carrier="warehouse"` ⇒ 卖方是仓储（`state.resources`），货款回**国库**；
      与 `buyer="treasury"` 同时出现＝**自购自卖**，直接拒绝；
    - `carrier="pop"` ⇒ 卖方是路级 POP（`seller_pop`，默认商人），货款进其 `wealth`。

    返回字段与 `trade_goods` 对齐（`ok/traded/paid/unmet_qty/reason/tail_delta`），
    另加 `seller/buyer/value/unit_price`。**未满足量单独返回，不静默丢弃**。
    """
    spec = material_spec(dim)
    out = _line_base(dim, spec or {"name": None, "unit": None, "stock_unit": None,
                                   "units_per_stock": None})
    out.update(buyer=buyer, carrier=carrier)
    if spec is None:
        return _reject(out, MaterialReason.UNKNOWN_MATERIAL,
                       f"未注册建材：{dim!r}（须为仓储维度名）")
    if not spec.get("tradable", True):
        return _reject(out, MaterialReason.NO_SOURCE,
                       f"{spec.get('name')} 尚无来源：{spec.get('source')}")
    if buyer not in BUYERS:
        return _reject(out, MaterialReason.INVALID, f"buyer 非法：{buyer!r}（允许：{BUYERS}）")
    if carrier not in CARRIERS:
        return _reject(out, MaterialReason.INVALID, f"carrier 非法：{carrier!r}（允许：{CARRIERS}）")
    if buyer == "treasury" and carrier == "warehouse":
        return _reject(out, MaterialReason.SELF_DEALING,
                       "国库买官仓＝自购自卖，不构成市场；官府取官仓料请用 issue_material")
    if not isinstance(pref, str) or not pref.strip():
        return _reject(out, MaterialReason.INVALID, "pref（路名）必须是非空字符串")
    want = _exact_int(qty) if not spec.get("divisible", False) else _num(qty)
    if want is None:
        return _reject(out, MaterialReason.INVALID,
                       f"qty 非法：{qty!r}（建材按整数「{spec.get('unit')}」计量，不静默取整）")
    if want < 0:
        return _reject(out, MaterialReason.INVALID, f"qty 不得为负：{qty!r}")
    out["requested"] = want
    px = material_price(state=state, pref=pref, dim=dim, gov_price=gov_price)
    out["unit_price"] = px.get("unit_price")
    out["price_kind"] = px.get("price_kind")
    if px.get("reason") != MaterialReason.OK:
        return _reject(out, MaterialReason.NO_BASE_PRICE,
                       f"价格不可定价（缺失≠0）：{px.get('price_reason')}")
    if want == 0:
        out.update(ok=True, reason=MaterialReason.NO_DEMAND, unmet_qty=0,
                   detail="需求为 0 不是未满足")
        return out

    # ---- 持有人解析（缺失 ⇒ 拒绝，绝不臆造持有人）
    rsv = _resolve_reserved(state, reserved, dim)
    if rsv is None:
        return _reject(out, MaterialReason.INVALID, f"reserved 非法：{reserved!r}")
    # 预留量来自工程台账（`_mat_left_*`，**库存单位**）⇒ 换算到市场采购单位
    reserved_market = int(round(convert_stock_to_market(dim, rsv) or 0.0))
    if buyer == "pop" and carrier == "pop" and buyer_pop == seller_pop:
        return _reject(out, MaterialReason.INVALID,
                       "买方与卖方是同一 POP（自购不构成市场）")
    if buyer == "pop":
        bpop = _pop_of(state, pref, buyer_pop)
        if bpop is None:
            return _reject(out, MaterialReason.NO_BUYER,
                           f"买方 {pref!r}/{buyer_pop!r} 不存在")
        buyer_holder = bpop                              # 真实 POP：货原地入其 goods
        out["buyer"] = f"{pref}|{buyer_pop}"
        dest = None
    else:
        t = _num(getattr(state, "treasury", None))
        if t is None:
            return _reject(out, MaterialReason.INVALID, "state.treasury 不可读（缺失≠0）")
        buyer_holder = {"wealth": int(round(t)), "goods": {}}
        out["buyer"] = "state.treasury"
        dest = "warehouse"                               # 官府购料入仓储（工程预留）
    if carrier == "warehouse":
        slot = _resource_slot(state, dim)
        if slot is None:
            return _reject(out, MaterialReason.UNKNOWN_STOCK,
                           f"仓储槽位 state.resources[{dim!r}] 不可读（不自动建槽）")
        stock = _read_int(slot.get("stock"))
        if stock is None:
            return _reject(out, MaterialReason.UNKNOWN_STOCK,
                           "仓储槽位无 stock（未定义≠0）")
        t = _num(getattr(state, "treasury", None))
        if t is None:
            return _reject(out, MaterialReason.INVALID, "state.treasury 不可读（缺失≠0）")
        # 卖方视图按**市场采购单位**表达（`trade_goods` 的成交量也在该单位），
        # 成交后再换算回库存单位写回——换算只在 `material_*` 系列发生一次。
        seller_market_qty = convert_stock_to_market(dim, stock)
        if seller_market_qty is None:
            return _reject(out, MaterialReason.INVALID, "单位换算不可读")
        seller_holder = {"wealth": int(round(t)),
                         "goods": {dim: int(round(seller_market_qty))}}
        out["seller"] = "state.resources"
        seller_kind = "warehouse"
    else:
        spop = _pop_of(state, pref, seller_pop)
        if spop is None:
            return _reject(out, MaterialReason.NO_SELLER,
                           f"卖方 {pref!r}/{seller_pop!r} 不存在")
        goods = spop.get("goods")
        if not isinstance(goods, dict):
            return _reject(out, MaterialReason.UNKNOWN_STOCK,
                           f"卖方 {pref!r}/{seller_pop!r} 无 goods 槽（旧档缺失≠0）")
        # POP 持货同样是**库存单位**（RAW_UNITS 口径）⇒ 同样先换算再成交
        from core.foundation.ledger.material_holding import goods_amount
        _sv = goods_amount(goods, dim)
        sp_qty = convert_stock_to_market(dim, _read_int(_sv if _sv is not None else 0))
        if sp_qty is None:
            return _reject(out, MaterialReason.INVALID, "单位换算不可读")
        seller_holder = {"wealth": int(round(_num(spop.get("wealth")) or 0.0)),
                         "goods": {dim: int(round(sp_qty))}}
        out["seller"] = f"{pref}|{seller_pop}"
        seller_kind = "pop"

    # ---- 唯一成交入口（双向原子 / 三重上限 / trade_id 幂等）
    r = trade_goods(state, dim=dim, qty=want, price=float(px["unit_price"]),
                    buyer=buyer_holder, seller=seller_holder,
                    purpose=("storage" if carrier == "warehouse" else "resale"),
                    trade_id=trade_id, reserved=int(reserved_market))
    out.update(ok=bool(r.get("ok")), traded=int(r.get("traded") or 0),
               paid=int(r.get("paid") or 0), unmet_qty=int(r.get("unmet_qty") or 0),
               tail_delta=r.get("tail_delta", 0), channel=CHANNELS[0],
               applied=bool(r.get("ok")) and int(r.get("traded") or 0) > 0,
               reason=r.get("reason"), detail=r.get("detail"))

    # ---- 写回真实槽位（视图 → 既有字段；不新建账本）
    if out["applied"]:
        # 卖方视图里是**市场采购单位**；真实槽位（仓储 stock / POP goods）里是
        # **库存单位** ⇒ 写回前必须换算，否则非 1:1 系数时库存账不平。
        rest_market = float(seller_holder["goods"].get(dim, 0) or 0)
        rest_stock = convert_market_to_stock(dim, rest_market)
        # 换算尾差**登记**（非整数系数时每笔 ≤1 库存单位），不静默吞掉
        out["stock_tail"] = round(rest_stock - int(round(rest_stock)), 6)
        if seller_kind == "warehouse":
            # 官仓售料：货出仓储、货款进国库（钱货两条腿都落既有槽位）
            state.treasury = int(seller_holder["wealth"])
            slot["stock"] = max(0, int(round(rest_stock)))
        else:
            # 民间售料：货出商户 goods、货款进该商户 wealth（真实 POP 槽位）
            spop["wealth"] = int(seller_holder["wealth"])
            spop["goods"][dim] = max(0, int(round(rest_stock)))
        if buyer == "treasury":
            treasury = _num(getattr(state, "treasury", None))
            state.treasury = int(round(treasury if treasury is not None else 0.0)
                                 - out["paid"])
            if dest == "warehouse":
                dslot = _resource_slot(state, dim)
                if dslot is not None:
                    add_stock = convert_market_to_stock(dim, out["traded"]) or 0.0
                    dslot["stock"] = int(_read_int(dslot.get("stock")) or 0) \
                        + int(round(add_stock))
        # 路级动态成交均价（`pref_good_key(pref, dim)`＝"路|商品"；**不改基准表** B2-5）。
        # 领料（无货款）不登记：均价 0 是无效价格，不是"免费"。
        if out["paid"] > 0:
            record_trade_price(state, dim, pref=pref, paid=float(out["paid"]),
                               qty=float(out["traded"]))
    out["value"] = round(out["traded"] * float(px["unit_price"]), 4)
    return out


def issue_material(state, *, pref: Any, dim: str, qty: Any,
                   reserved: Any = 0,
                   gov_price: Optional[float] = None) -> Dict[str, Any]:
    """**官仓领料**（B4-6 路径②）：从仓储扣货，**无任何钱腿**，只记基准估价。

    为什么**不调** `trade_goods`：该函数强制 `buyer≠seller`，
    而"国库从官仓领料"是**同一主体的内部调拨**，本就不是市场成交。
    走独立通道正是为了让①市场购料与②官仓领料**分别记账、不得双计**（B4-6）。

    货的去向是**工程台账**（`proj["_mat_left_<dim>"]`），本函数只负责从仓储
    扣出并回报数量，**不代改工程台账**（避免新建材料账本）。
    """
    spec = material_spec(dim)
    out = _line_base(dim, spec or {"name": None, "unit": None, "stock_unit": None,
                                   "units_per_stock": None})
    out.update(buyer="state.treasury", carrier="warehouse",
               seller="state.resources", channel=CHANNELS[1])
    if spec is None:
        return _reject(out, MaterialReason.UNKNOWN_MATERIAL, f"未注册建材：{dim!r}")
    if not spec.get("tradable", True):
        return _reject(out, MaterialReason.NO_SOURCE,
                       f"{spec.get('name')} 尚无来源：{spec.get('source')}")
    want = _exact_int(qty) if not spec.get("divisible", False) else _num(qty)
    if want is None or want < 0:
        return _reject(out, MaterialReason.INVALID, f"qty 非法：{qty!r}")
    out["requested"] = want
    px = material_price(state=state, pref=pref, dim=dim, gov_price=gov_price)
    out["unit_price"] = px.get("unit_price")
    out["price_kind"] = px.get("price_kind")
    if want == 0:
        out.update(ok=True, reason=MaterialReason.NO_DEMAND, detail="需求为 0 不是未满足")
        return out
    slot = _resource_slot(state, dim)
    stock = None if slot is None else _read_int(slot.get("stock"))
    if stock is None:
        return _reject(out, MaterialReason.UNKNOWN_STOCK,
                       f"仓储槽位 state.resources[{dim!r}] 无可读 stock（缺失≠0）")
    rsv = _resolve_reserved(state, reserved, dim)
    if rsv is None:
        return _reject(out, MaterialReason.INVALID, f"reserved 非法：{reserved!r}")
    # 库存单位 → 市场采购单位（`traded`/`unmet` 一律以采购单位回报）
    avail_market = convert_stock_to_market(dim, sellable_stock(
        seller={"goods": {dim: int(stock)}}, dim=dim, reserved=int(rsv)))
    want_market = convert_stock_to_market(dim, want)
    if avail_market is None or want_market is None:
        return _reject(out, MaterialReason.INVALID, "单位换算不可读")
    avail = int(avail_market)
    traded = min(int(want_market), avail)
    if traded <= 0:
        out.update(ok=True, reason=MaterialReason.NO_STOCK, unmet_qty=int(want_market),
                   detail="官仓无可领量（无货不能领）")
        return out
    left_stock = convert_market_to_stock(dim, stock - traded)
    slot["stock"] = max(0, int(round(left_stock)))
    out.update(ok=True, traded=traded, paid=0, applied=True,
               unmet_qty=int(want_market) - traded,
               reason=(MaterialReason.OK if want_market - traded <= 0
                       else MaterialReason.NO_STOCK),
               detail="领料无货款（内部调拨）；value 仅作基准估价，不与采购款双计")
    out["stock_tail"] = round(left_stock - slot["stock"], 6)
    if px.get("unit_price") is not None:
        out["value"] = round(traded * float(px["unit_price"]), 4)
    return out


def _reject(out: Dict[str, Any], reason: str, detail: str) -> Dict[str, Any]:
    """拒绝式：标红原因，**不动任何金额/数量**，且不计入有效需求。

    被拒的输入**不是"有效需求"**（`requested` 归 0），否则零成交会被
    误读成"没人要"或"买不到"——非法输入必须单独可归因。
    """
    out.update(ok=False, reason=reason, detail=detail,
               requested=0, traded=0, paid=0, value=0.0, unmet_qty=0,
               covered=0.0, substitute_qty=0)
    return out


def _resource_slot(state, dim: str) -> Optional[dict]:
    res = getattr(state, "resources", None)
    if not isinstance(res, dict):
        return None
    slot = res.get(dim)
    return slot if isinstance(slot, dict) else None


def _acquire(state, *, pref: Any, dim: str, qty: Any, buyer: str, buyer_pop: str,
             carrier: str, seller_pop: str, reserved: Any,
             gov_price: Optional[float], trade_id: Optional[str]) -> Dict[str, Any]:
    """**渠道分流**（口径单点）：国库取官仓料＝领料，其余＝市场购料。

    两条路径**分别记账**（B4-6）：
    - `buyer="treasury"` ＋ `carrier="warehouse"` → `issue_material`（**无钱腿**，
      预留量对该工程自身申领不生效，避免自锁）；
    - 其余一切组合 → `buy_material`（真实成交，钱货双向）。
    替代材也走本函数，保证"主材与替代材同渠道"，不出现一半领料一半购料。
    """
    if buyer == "treasury" and carrier == "warehouse":
        return issue_material(state, pref=pref, dim=dim, qty=qty,
                              reserved=(0 if reserved == "projects" else reserved),
                              gov_price=gov_price)
    return buy_material(state, pref=pref, dim=dim, qty=qty, buyer=buyer,
                        buyer_pop=buyer_pop, carrier=carrier,
                        seller_pop=seller_pop, reserved=reserved,
                        gov_price=gov_price, trade_id=trade_id)


# ====================================================== 工程购料/领料结算
def settle_material_purchase(state, *, pref: Any, materials: Any,
                             budget: Optional[float] = None,
                             buyer: str = "treasury", buyer_pop: str = "士绅",
                             carrier: str = "warehouse", seller_pop: str = "商人",
                             reserved: Any = "projects",
                             allow_substitutes: Any = None,
                             gov_price: Optional[float] = None,
                             trade_prefix: Optional[str] = None,
                             record: bool = True) -> Dict[str, Any]:
    """工程/营造**一次性购料或领料**（B4-1＋B4-6）。

    参数
    ----
    `materials`：`{dim: 采购量}`（量以**市场采购单位**计，须整数）。
    `budget`：本次**总预算**（贯）；`None`＝不限（仍受购买力上限约束）。
        预算按**声明顺序**逐项分配（先到先得），不做隐式按比例摊分。
    `reserved`：`int` 显式预留 / `"projects"` 派生在营工程申领（默认）。
        ⚠️ 若本次采购**正是为某在建工程补料**，请显式传 `reserved=0`
        ——该工程的 `_mat_left_*` 已在项目台账记账，重复预留会自锁。
    `allow_substitutes`：`None`＝**不替代**（默认，缺口如实记 unmet）；
        传 `[dim, ...]` 才允许，且替代材还须在 `MATERIAL_SUBSTITUTES` 声明过。

    返回 `{ok, reason, pref, channel, lines, substitutions, totals, money, warnings}`，
    逐线可对账：`requested / traded / paid / value / unmet_qty / channel /
    seller / buyer / substitution[]`。
    """
    out: Dict[str, Any] = {
        "schema_version": MATERIAL_SCHEMA_VERSION, "pref": pref, "ok": False,
        "reason": MaterialReason.INVALID, "detail": None,
        "buyer": buyer, "carrier": carrier, "channel": None,
        "lines": [], "substitutions": [],
        "totals": {"requested": 0, "traded": 0, "paid": 0, "value": 0.0,
                   "unmet": 0, "covered": 0.0, "substitute_qty": 0,
                   "budget": budget},
        "money": {"payer": None, "paid": 0, "receiver": None},
        "warnings": [],
    }
    # ---- 拒绝式校验（非法输入不成交、不改状态）
    if not isinstance(pref, str) or not pref.strip():
        out["detail"] = "pref（路名）必须是非空字符串"
        return out
    if not isinstance(materials, dict) or not materials:
        out["detail"] = "materials 须为非空 {dim: qty} 字典"
        return out
    if buyer not in BUYERS or carrier not in CARRIERS:
        out["detail"] = f"buyer/carrier 非法（允许 buyer={BUYERS}, carrier={CARRIERS}）"
        return out
    budget_left = None
    if budget is not None:
        bf = _num(budget)
        if bf is None or bf < 0:
            out["detail"] = f"budget 非法：{budget!r}（须 ≥0 的有限数值；缺失≠0）"
            return out
        budget_left = bf
    allow: Optional[Tuple[str, ...]] = None
    if allow_substitutes is not None:
        if (not isinstance(allow_substitutes, (list, tuple))
                or any(not isinstance(d, str) or not d for d in allow_substitutes)):
            out["detail"] = "allow_substitutes 须为 [dim, ...] 列表（None＝不替代）"
            return out
        allow = tuple(allow_substitutes)

    turn = getattr(state, "turn", None)
    prefix = trade_prefix or f"mat:{turn}"
    stats = getattr(state, "statistics", None)
    if record and not isinstance(stats, dict):
        out["warnings"].append("state.statistics 非 dict：本月不登记建材读数（不新建账本）")
        record = False

    channels = set()
    receivers = set()
    for idx, (dim, want_raw) in enumerate(materials.items()):
        spec = material_spec(dim)
        if spec is None:
            line = _line_base(dim if isinstance(dim, str) else str(dim),
                              {"name": None, "unit": None, "stock_unit": None,
                               "units_per_stock": None})
            _reject(line, MaterialReason.UNKNOWN_MATERIAL,
                    f"未注册建材：{dim!r}（键须为仓储维度名，不接受中文别名）")
            out["lines"].append(line)
            continue
        line = _line_base(dim, spec)
        line["requested"] = want_raw if isinstance(want_raw, (int, float)) else None
        want = _exact_int(want_raw) if not spec.get("divisible", False) else _num(want_raw)
        if want is None or want < 0:
            _reject(line, MaterialReason.INVALID,
                    f"采购量非法：{want_raw!r}（建材按整数「{spec.get('unit')}」计量）")
            out["lines"].append(line)
            continue
        #已登记但**无来源**（如未建模的砖）⇒ 一律拒绝，**不凭空产出、不按 0 价成交**。
        # 审查修复：原先缺此分支，无来源材料会继续往下走并被归成 `no_demand`
        # （把"此世无此物"误报成"没人要"），与`quote_material` 的口径也不一致。
        if not spec.get("tradable", True):
            _reject(line, MaterialReason.NO_SOURCE,
                    f"{spec.get('name')} 尚无来源：{spec.get('source')}")
            out["lines"].append(line)
            continue
        px = material_price(state=state, pref=pref, dim=dim, gov_price=gov_price)
        line["unit_price"] = px.get("unit_price")
        line["price_kind"] = px.get("price_kind")
        if px.get("reason") != MaterialReason.OK:
            _reject(line, MaterialReason.NO_BASE_PRICE,
                    f"价格不可定价（缺失≠0）：{px.get('price_reason')}")
            out["lines"].append(line)
            continue
        if want == 0:
            line.update(ok=True, reason=MaterialReason.NO_DEMAND,
                        detail="需求为 0 不是未满足")
            out["lines"].append(line)
            continue

        # 预算封顶：先到先得（声明顺序），预算不足则压低本次求购量
        cap = want
        if budget_left is not None and px["unit_price"] > 0:
            cap = min(cap, int(budget_left // float(px["unit_price"])))

        # 渠道分流：国库取官仓料＝领料（B4-6 路径②，无钱腿）；其余＝市场购料
        is_issue = (buyer == "treasury" and carrier == "warehouse")
        if is_issue:
            out["warnings"].append(
                f"{pref}/{dim}：国库自官仓领料走 `warehouse_issue`（无货款），"
                "与市场购料分别记账、不双计")
        r = _acquire(state, pref=pref, dim=dim, qty=cap, buyer=buyer,
                     buyer_pop=buyer_pop, carrier=carrier, seller_pop=seller_pop,
                     reserved=reserved, gov_price=gov_price,
                     trade_id=f"{prefix}:{pref}:{idx}:{dim}")
        if r.get("reason") == MaterialReason.DUPLICATE:
            # 幂等拦截：**本次没有成交**，不得计入货款/成交/预算
            r = dict(r)
            r["first_result"] = {"traded": r.get("traded"), "paid": r.get("paid")}
            r.update(traded=0, paid=0, value=0.0, unmet_qty=int(want),
                     covered=0.0, substitute_qty=0)

        # ---- 显式替代（两道闸门：调用方放行 ＋ 声明表已登记）
        line.update(r)                                  # 单材成交结果并入本线
        line["requested"] = want                         # 请求量回填（`r` 里是预算封顶后求购量）
        line["substitution"] = []
        record_line(stats, r, record)
        if budget_left is not None:
            budget_left -= int(_num(r.get("paid")) or 0)
        shortfall = float(max(0, int(want) - int(line.get("traded") or 0)))
        sub_records: List[Dict[str, Any]] = []
        if shortfall > 0:
            for rule in MATERIAL_SUBSTITUTES.get(dim, ()):
                to_dim = rule.get("to")
                acc = _num(rule.get("acceptability"))
                rec = {"requested_dim": dim, "provided_dim": to_dim,
                       "acceptability": acc, "qty": 0, "covered": 0.0,
                       "accepted": False, "reason": None, "rule_reason": rule.get("reason")}
                if allow is None:
                    rec["reason"] = "not_allowed"      # 调用方未放行 ⇒ 绝不静默换料
                elif to_dim not in allow:
                    rec["reason"] = "not_allowed"
                elif acc is None or not (0 < acc <= 1):
                    rec["reason"] = "invalid_acceptability"   # 不按 1.0 兜底
                elif material_spec(to_dim) is None or \
                        not (material_spec(to_dim) or {}).get("tradable", True):
                    rec["reason"] = MaterialReason.NO_SOURCE
                else:
                    need = int(math.ceil(shortfall / acc))
                    sub_cap = need
                    if budget_left is not None:
                        sub_px = material_price(state=state, pref=pref, dim=to_dim,
                                                gov_price=gov_price)
                        upx = sub_px.get("unit_price")
                        sub_cap = need
                        if upx is not None and upx > 0 and budget_left > 0:
                            sub_cap = min(need, int(budget_left // float(upx)))
                    if sub_cap <= 0:
                        rec["reason"] = MaterialReason.NO_MONEY
                    else:
                        sr = _acquire(state, pref=pref, dim=to_dim, qty=sub_cap,
                                      buyer=buyer, buyer_pop=buyer_pop,
                                      carrier=carrier, seller_pop=seller_pop,
                                      reserved=reserved, gov_price=gov_price,
                                      trade_id=f"{prefix}:{pref}:{idx}:{dim}~{to_dim}")
                        rec.update(qty=int(sr.get("traded") or 0),
                                   paid=int(sr.get("paid") or 0),
                                   reason=(None if int(sr.get("traded") or 0) > 0
                                           else sr.get("reason")),
                                   accepted=int(sr.get("traded") or 0) > 0)
                        if rec["accepted"]:
                            rec["covered"] = round(int(sr["traded"]) * acc, 6)
                            shortfall = max(0.0, shortfall - rec["covered"])
                            # 替代材**不并入 traded**（不同单位）；只累加当量与花费
                            line["covered"] = round(
                                float(line.get("covered") or 0.0) + rec["covered"], 6)
                            line["substitute_qty"] = int(
                                line.get("substitute_qty") or 0) + int(sr["traded"])
                            line["paid"] = int(line.get("paid") or 0) + int(sr.get("paid") or 0)
                            line["value"] = round(
                                float(_num(line.get("value")) or 0.0)
                                + float(_num(sr.get("value")) or 0.0), 4)
                            line["unmet_qty"] = int(math.ceil(shortfall))
                            line["reason"] = (MaterialReason.OK if shortfall <= 0
                                              else line.get("reason"))
                            if budget_left is not None:
                                budget_left -= int(sr.get("paid") or 0)
                            if sr.get("channel"):
                                channels.add(sr["channel"])
                            if sr.get("seller") and sr.get("channel") == CHANNELS[0]:
                                receivers.add(sr["seller"])
                            record_line(stats, sr, record)
                sub_records.append(rec)
                out["substitutions"].append(rec)
                if shortfall <= 0:
                    break
        line["substitution"] = sub_records

        if line.get("channel"):
            channels.add(line["channel"])
        if line.get("seller") and line.get("channel") == CHANNELS[0]:
            # 只有**市场购料**才有货款接收方；领料是内部调拨，不记收款人
            receivers.add(line["seller"])
        out["lines"].append(line)

    # ---- 汇总（读视图；不在别处重复记账）
    tot = out["totals"]
    for line in out["lines"]:
        tot["requested"] += int(_num(line.get("requested")) or 0)
        tot["traded"] += int(_num(line.get("traded")) or 0)
        tot["paid"] += int(_num(line.get("paid")) or 0)
        tot["unmet"] += int(_num(line.get("unmet_qty")) or 0)
        tot["covered"] = round(tot["covered"] + float(_num(line.get("covered")) or 0.0), 6)
        tot["substitute_qty"] += int(_num(line.get("substitute_qty")) or 0)
        tot["value"] = round(tot["value"] + float(_num(line.get("value")) or 0.0), 4)
    tot["budget_spent"] = tot["paid"]
    tot["budget_unused"] = (None if budget is None
                            else round(float(budget) - tot["paid"], 4))
    out["money"] = {
        "payer": ("state.treasury" if buyer == "treasury" else f"{pref}|{buyer_pop}"),
        "paid": tot["paid"],
        "receiver": (", ".join(sorted(receivers)) if receivers
                     else "无（官仓领料＝内部调拨，无货款）"),
    }
    out["channel"] = ",".join(sorted(channels)) if channels else None
    unmet = tot["unmet"]
    traded = tot["traded"]
    # 归因优先级：**不可判定/非法 > 无货无钱 > 零需求单列 > 部分 > ok**
    reasons = [line.get("reason") for line in out["lines"]]
    reason = MaterialReason.OK
    for cand in (MaterialReason.INVALID, MaterialReason.UNKNOWN_MATERIAL,
                 MaterialReason.NO_SOURCE, MaterialReason.NO_BASE_PRICE,
                 MaterialReason.UNKNOWN_STOCK, MaterialReason.NO_SELLER,
                 MaterialReason.NO_BUYER, MaterialReason.SELF_DEALING,
                 MaterialReason.NO_STOCK, MaterialReason.NO_MONEY,
                 MaterialReason.DUPLICATE):
        if cand in reasons:
            reason = cand
            break
    else:
        if tot["requested"] <= 0:
            # 零需求**单列**：不是未满足原因（与 `market.trade_goods` 的 no_demand 同口径）
            reason = MaterialReason.NO_DEMAND
        elif unmet > 0:
            reason = "partial"
    out["reason"] = reason
    out["ok"] = traded > 0 and unmet <= 0 and reason == MaterialReason.OK
    if record and isinstance(stats, dict) and (traded > 0 or tot["paid"] > 0):
        stats["material_traded"] = float(stats.get("material_traded", 0) or 0) + traded
        stats["material_paid"] = float(stats.get("material_paid", 0) or 0) + tot["paid"]
        stats["material_value"] = float(stats.get("material_value", 0) or 0) + tot["value"]
        stats["material_unmet"] = float(stats.get("material_unmet", 0) or 0) + unmet
    return out


def record_line(stats: Any, line: Dict[str, Any], record: bool) -> None:
    """把单笔成交登记进**既有** `state.statistics` 读数槽（非账本）。"""
    if not record or not isinstance(stats, dict):
        return
    traded = int(_num(line.get("traded")) or 0)
    paid = int(_num(line.get("paid")) or 0)
    dim = str(line.get("dim"))
    if traded <= 0 and paid <= 0:
        return
    qt = stats.setdefault("material_qty_by_dim", {})
    if isinstance(qt, dict):
        qt[dim] = qt.get(dim, 0) + traded
    if paid > 0:
        pt = stats.setdefault("material_paid_by_dim", {})
        if isinstance(pt, dict):
            pt[dim] = pt.get(dim, 0) + paid


# ====================================================== 只读读数（面板用）
def material_market_readout(state, *, pref: Any = None, dims: Any = None,
                            carrier: str = "warehouse", seller_pop: str = "商人",
                            reserved: Any = "projects",
                            max_items: int = 60) -> Dict[str, Any]:
    """建材市场读数（**纯派生只读**，不改任何模拟行为）。

    返回 `{rows, dimensions, totals, warnings}`；每行含单位/存量/预留/可售/
    价格与价格口径/可替代项/可成交性。与 `market_readout.inventory_ledger` 同范式：
    缺失给 `None` 并在 `warnings` 说明，**不用 0 冒充"没有货"**。
    """
    warnings: List[str] = []
    specs = MATERIAL_SPECS
    if dims is not None:
        if not isinstance(dims, (list, tuple, set)):
            return {"schema_version": MATERIAL_SCHEMA_VERSION, "rows": [],
                    "dimensions": [], "totals": {}, "warnings": ["dims 非法"],
                    "truncated": 0}
        wanted = [d for d in dims if isinstance(d, str) and d in specs]
        for d in dims:
            if isinstance(d, str) and d not in specs:
                warnings.append(f"未注册建材：{d!r}（已跳过）")
        specs = {d: specs[d] for d in wanted}
    rows: List[Dict[str, Any]] = []
    for dim, spec in specs.items():
        if pref is not None and not isinstance(pref, str):
            warnings.append("pref 非法（非字符串），按路级读数不可用处理")
            break
        try:
            q = quote_material(state, pref=pref, dim=dim, carrier=carrier,
                               seller_pop=seller_pop, reserved=reserved)
        except Exception as exc:                   # noqa: BLE001 — 读数不阻断结算
            warnings.append(f"{dim} 读数失败：{exc}")
            continue
        rows.append(q)
    totals = {
        "tradeable_dims": sum(1 for r in rows if r.get("tradeable")),
        "note": "可售量＝既有持仓 − 预留的**派生视图**；本模块不新建存量账本",
    }
    return {
        "schema_version": MATERIAL_SCHEMA_VERSION,
        "pref": pref, "carrier": carrier,
        "rows": rows[:max_items],
        "dimensions": sorted(rows and [r["dim"] for r in rows] or []),
        "totals": totals,
        "truncated": max(0, len(rows) - max_items),
        "warnings": warnings,
    }