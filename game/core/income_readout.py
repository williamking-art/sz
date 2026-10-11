# -*- coding: utf-8 -*-
"""B2-R5 · 农民与商人市场参与：**收入来源读数 ＋ 市场再进入判定**（纯派生、只读）

对应规格 `specs/market-civilian-economy` §4 B2-R5：

> 农/商人若在常态下退出布帛等可选市场，可以是需求结果，但须允许其通过粮食交易、
> 运输/仓储服务、作坊/农业岗位获得收入与重新进入市场；不以"人人必须消费布帛"为目标。
> 放行证据：长局分别观察各 POP 收入来源、基本粮食满足和可选品成交；
> **消费退出不会被误报成饥饿，重新获得收入后需求能响应。**

## 为什么有这个模块（实测背景，不是推测）

1. `content/data_constants.py:430` `SUBSISTENCE_LINE["农"]=0.15` 贯，而实测
   农家人均 wealth 约 **0.11 贯** ⇒ `demand_release` 恒 0 ⇒ 农户**结构性买不起
   可选商品**；同表 `SUBSISTENCE_LINE["商人"]=2.0` 贯，商人人均亦长期在下方。
2. `core/population_readout.famine_attribution` 的归因主因是
   `purchasing_power_short`（**有钱买不到粮的镜像：没钱**）——
   与第 1 条同源：**没有收入通道，就没有粮食购买力**。
3. 故"可选品成交为 0"在当前局里**既可能是消费退出（正确结果）**，
   也可能是**收入通道断裂**（须修）。二者**必须可分辨**，
   否则面板会把"没收入"读成"温饱线以下所以不买"，把因果讲反。

## 本模块提供的三件事

| 函数 | 回答什么 |
|---|---|
| `income_source_readout` | **这个 POP 阶层的钱从哪来**（按路 × 按阶层 × 五类收入来源） |
| `purchasing_power_readout` | 该阶层**当前的购买力**与"温饱线以上还差多少" |
| `market_reentry` | **重新获得收入后，可选商品需求能否响应**（与 `demand_release` 同口径） |
| `consumption_exit_vs_hunger` | **消费退出 ≠ 饥饿**（两者并列，绝不互相推导） |

## 三条纪律（违反即返工）

### 1 · 纯派生只读，**不新建账本**（POP 挂载律）

- 一切输出都是 `state` 现有字段的**投影**：钱只读 `pops[阶层].wealth`，
  粮只读 `pops[阶层].grain`，官钱只读 `treasury` / `imperial_treasury` /
  `prefectures[路].local_treasury`；
- **绝不**写 `state`、**绝不**写 `statistics`、**绝不**新增与 POP 平行的收入账本；
  本模块返回的 `realized`（已实现收入）**只允许来自既有权威记录键**，
  读不到就给 `None` ＋ 原因（见下）。

### 2 · 缺失 ≠ 0 ≠ 1.0

- 字段缺失 / 不可读 → `None`，并在 `reason`／`warnings` 说明；
- **分母为 0 不除零**：`size == 0` ⇒ `per_capita_wealth = None`（不是 0 贯/人）；
  `grain_need == 0` ⇒ `grain_self_sufficiency = None`（不是"完全自给"）；
- **非法输入拒绝式**（`ValueError`）：未知路 / 未知阶层 / 负数或非有限的注入收入
  / 非正 `max_rows` —— 不静默纠正、不回落默认值。

### 3 · `capacity`（通道容量）与 `realized`（实发额）**必须分列**

本仓库的实发收入**没有按 `(路, 阶层, 收入来源)` 落统计的权威字段**
（逐条见 `INCOME_SOURCES` 的 `code_path` 与各 slot 的 `reason`）。
把"能卖多少"说成"卖了多少钱"就是臆造。故每条来源一律给出：

- `capacity`：从**权威存量字段**纯派生的**可参与上限**（`bound="upper_bound"`）；
- `realized`：**只读既有记录键**；没有记录键 → `None` ＋ `reason`，
  **不用 0 冒充"本月没赚到钱"**；
- `realized_window="cumulative-national"` 的项（如 `granary_stats["grain_market_trade"]`、
  `statistics["export_income"]`、`statistics["goods_spend"]`）是
  **全国累加值**，读数显式标注窗口，**不得**与单月或单阶层直接比大小。

> 这是 B0-3 已确立的同一原则（`market_readout.demand_diagnosis` 报 `unknown`
> ＋ 警告，不臆造分类）。本模块沿用它，不新造一套更宽松的说法。

## 口径单点（不重算既有算法）

- 可选品需求的余量释放 → **读** `core.domains.economy.demand.demand_release`（本模块**不改** `demand.py`）；
- 可售量 → **读** `core.domains.economy.market.sellable_stock`（B1 唯一成交入口的同源口径）；
- 买入价 → **读** `core.market_price.effective_buy_price`（四类价格分离）；
- 吃不上饭的人数 → **读** `core.settlement_common.food_insecure_headcount`
  （经 `core.population_readout.famine_attribution`）；
- 月口粮需求 → **读** `content.data.GRAIN_CONSUME_PER_CAPITA`（不另立一份）；
- 温饱线/余量尺度 → **读** `content.data.SUBSISTENCE_LINE` / `SUBSISTENCE_SCALE`。

## 本模块**不**做的事

- 不改模拟行为、不加收入、不调温饱线、不复活虚拟直产；
- 不判断"该不该消费布帛"——B2-R5 明示"不以人人必须消费布帛为目标"，
  本模块只回答"**有没有收入通道**"和"**有了收入需求会不会动**"；
- 不把外销价（`content.data.GOODS_PRICE`，外销结算价）当民间买入价（B2-5 口径分离）。

## 代码事实快照（截至本文件落地时实测，随代码演进须复核）

1. `core.domains.economy.dynamic_price.civil_logistics` / `gov_logistics`（运费结算，宋/外邦通用签名）
   在 `game/` 下**无调用方** ⇒ 运输/仓储服务收入通道**已定义但未接线**；
2. `core.building_jobs.pay_wages_from_revenue` 的唯一调用方是
   `core/settlement_econ.py:849`（**外邦 regime** 路径），宋境
   `prefectures[路]` 无岗位/工钱记录 ⇒ 工资实发额**无宋境权威字段**；
3. `state.workshops` 的键名含路名（如 `麻坊_京畿路_2`），但
   `core/settlement_econ.py:1609-1634` 明确"作坊产出是**全局**记账、不分路"，
   成品按各路**工匠 size 占比**分派 ⇒ **作坊收入无法按路归因**（读数给 `None` ＋ 原因）；
4. `statistics["goods_spend"] / ["goods_traded"] / ["goods_unmet"] /
   ["price_demand"] / ["basics_unmet"]` 均**逐月累加、无月度清零**
   （`settlement_granary.py:323-336`）⇒ 只能当**累计**证据，不可当单月流量。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "INCOME_READOUT_SCHEMA_VERSION", "POP_CLASSES",
    "INCOME_SOURCES", "SOURCE_KEYS", "SOURCE_LABELS", "SOURCE_CODE_PATHS",
    "income_source_readout", "purchasing_power_readout",
    "market_reentry", "consumption_exit_vs_hunger", "build_income_readout",
]

#: 读数结构版本（供存档/面板判断读数是否同构）
INCOME_READOUT_SCHEMA_VERSION = 1

#: 6 类 POP（权威键序见 `content.data.GRAIN_CONSUME_PER_CAPITA`；勿在此另立一份）
POP_CLASSES: Tuple[str, ...] = ("农", "士绅", "工匠", "商人", "官僚", "兵")

#: 五类收入来源：`(key, 中文标签, 实现落点)`。
#: 顺序即面板展示顺序（先实物、后服务、再营生、最后官府）。
INCOME_SOURCES: Tuple[Tuple[str, str, str], ...] = (
    ("grain_sale", "售粮收入",
     "core.settlement_granary:425-505 粮市撮合；core.settlement_common"
     ":_changping_trade(平籴)/:_state_grain_trade(和籴)；"
     "core.settlement_econ:_settle_civilian_hoard(士绅售粮付农户)"),
    ("wage_labor", "工资/工钱（营生就业）",
     "core.building_jobs.pay_wages_from_revenue（唯一调用方 core.settlement_econ:849，"
     "属外邦 regime 路径）"),
    ("logistics_service", "运输/仓储服务收入",
     "core.domains.economy.dynamic_price.civil_logistics / gov_logistics（运费结算）"),
    ("workshop_agriculture_job", "作坊/农业岗位收入",
     "core.settlement_econ:_settle_workshops 成品维 → 工匠 goods 池 → "
     "core.domains.economy.market.trade_goods 成交"),
    ("public_grant_relief", "官府给付/赈济",
     "core.settlement_common:distribute_cash / transfer_public_funds_to_pops；"
     "core.free_effect._apply_money_delta(工赈)；granary_stats['relief']（粮，非钱）"),
)

SOURCE_KEYS: Tuple[str, ...] = tuple(k for k, _lab, _p in INCOME_SOURCES)
SOURCE_LABELS: Dict[str, str] = {k: lab for k, lab, _p in INCOME_SOURCES}
SOURCE_CODE_PATHS: Dict[str, str] = {k: p for k, _lab, p in INCOME_SOURCES}


# ============================================================== 数值与取值工具

def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    """安全取数：非数值/缺失/非有限 → `default`（默认 `None`，**不回落 0**）。"""
    if v is None or isinstance(v, bool):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


def _int(v: Any, default: Optional[int] = None) -> Optional[int]:
    f = _num(v, None)
    return default if f is None else int(round(f))


def _cfg(name: str, default: Any = None) -> Any:
    """读 `content.data` 的参数表（`demand.py::_cfg` 同源；**不另立一份**）。"""
    from content import data as _d
    val = getattr(_d, name, None)
    return default if val is None else val


def _grain_need_per_capita(cls: str) -> Optional[float]:
    tbl = _cfg("GRAIN_CONSUME_PER_CAPITA", {}) or {}
    return _num(tbl.get(cls), None)


def _subsistence(cls: str) -> Tuple[Optional[float], Optional[float]]:
    """`(温饱线, 余量尺度)`；**未给该阶层配置温饱线 → (None, scale)**
    （`demand_release` 此时返回 1.0，即"无门槛"——本读数如实给 `None`，不臆造阈值）。"""
    line_tbl = _cfg("SUBSISTENCE_LINE", {}) or {}
    return _num(line_tbl.get(cls), None), _num(_cfg("SUBSISTENCE_SCALE", 30.0), 30.0)


def _goods_demand(cls: str) -> Dict[str, float]:
    tbl = _cfg("GOODS_DEMAND", {}) or {}
    row = tbl.get(cls)
    return dict(row) if isinstance(row, dict) else {}


def _prefs(state) -> Optional[Dict[str, Any]]:
    p = getattr(state, "prefectures", None)
    return p if isinstance(p, dict) else None


def _check_scope(state, routes: Optional[Sequence[str]],
                 classes: Optional[Sequence[str]]) -> Tuple[Optional[Dict[str, Any]],
                                                            List[str], List[str]]:
    """校验并归一 `routes` / `classes`；**未知键拒绝式**（`ValueError`）。"""
    prefs = _prefs(state)
    if prefs is None:
        return None, list(POP_CLASSES), []
    if routes is None:
        sel = list(prefs.keys())
    else:
        if isinstance(routes, str):
            raise ValueError(f"routes 须为路名序列，不得为单个字符串：{routes!r}")
        sel = [str(r) for r in routes]
        unknown = [r for r in sel if r not in prefs]
        if unknown:
            raise ValueError(f"未知路名 {unknown}；state.prefectures 现有键：{sorted(prefs)[:8]}…")
    if classes is None:
        cls_sel = list(POP_CLASSES)
    else:
        if isinstance(classes, str):
            raise ValueError(f"classes 须为阶层名序列，不得为单个字符串：{classes!r}")
        cls_sel = [str(c) for c in classes]
        unknown_c = [c for c in cls_sel if c not in POP_CLASSES]
        if unknown_c:
            raise ValueError(f"未知 POP 阶层 {unknown_c}；合法值：{list(POP_CLASSES)}")
    return prefs, sel, cls_sel


def _grain_price(pref: Optional[dict], state) -> Tuple[Optional[float], str]:
    """本路粮价 → `(价, 来源说明)`；本路无值回退 `state.grain_price`（结算同口径）。"""
    if isinstance(pref, dict):
        v = _num(pref.get("grain_price"), None)
        if v is not None:
            return v, "prefectures[路].grain_price"
    v = _num(getattr(state, "grain_price", None), None)
    return v, ("state.grain_price" if v is not None else "unreadable")


def _slot(key: str, *, available: Optional[bool], capacity: Dict[str, Any],
          capacity_bound: Optional[str], realized: Optional[float],
          record_key: Optional[str], record_window: Optional[str],
          reason: str, note: str = "") -> Dict[str, Any]:
    """统一 slot 结构；`realized is None` 时 `reason` **必填**（不得静默 0）。"""
    if realized is None and not reason:
        raise AssertionError(f"income_readout: 来源 {key} 的 realized 为 None 时必须给 reason")
    return {
        "key": key,
        "label": SOURCE_LABELS.get(key, key),
        "code_path": SOURCE_CODE_PATHS.get(key, ""),
        "available": available,
        "capacity": capacity,
        "capacity_bound": capacity_bound,
        "realized": realized,
        "record_key": record_key,
        "record_window": record_window,
        "reason": reason if realized is None else "",
        "note": note,
    }


# ============================================================== 各来源的纯派生

def _slot_grain_sale(state, pref: Optional[dict], pop: dict, cls: str) -> Dict[str, Any]:
    """售粮收入：本路自有粮扣口粮后的**可售上限**（`bound="upper_bound"`）。

    农另有**安全垫保底**：`settlement_granary.py:436-438` 农户可售
    `= grain − 2×need`（保留 1 个月口粮不卖），非农可售 `= grain − need`。
    """
    grain = _int(pop.get("grain"), None)
    per = _grain_need_per_capita(cls)
    size = _int(pop.get("size"), None)
    # 🟢 M35-C-2：粮需按**有效人口**（桶 size ＋ 职业附加 occupation）——单点口径
    from core.foundation.ledger.occupation import food_need_of_pool
    need = (None if (per is None or size is None)
            else int(food_need_of_pool(pop, cls, per)))
    price, price_src = _grain_price(pref, state)
    if grain is None or need is None:
        saleable = None
    elif cls == "农":
        saleable = max(0, grain - 2 * need)
    else:
        saleable = max(0, grain - need)
    value_bound = (None if (saleable is None or price is None) else saleable * price)
    available = None if saleable is None else bool(saleable > 0)
    return _slot(
        "grain_sale",
        available=available,
        capacity={
            "own_grain_stone": grain,
            "monthly_need_stone": need,
            "saleable_grain_stone": saleable,
            "grain_price": price,
            "grain_price_source": price_src,
            "saleable_value_upper_bound": value_bound,
            "farmer_safety_floor": (cls == "农"),
        },
        capacity_bound="upper_bound",
        realized=None,
        record_key=None,
        record_window=None,
        reason=("本路 POP 售粮**实发额无权威记录字段**：粮市撮合"
                "（settlement_granary.py:488-505）只把实付额落到买卖双方 wealth，"
                "未按阶层落统计；全国侧仅有 granary_stats['grain_market_trade']"
                "（**累计成交量·石**，非金额、非分层级），见 national_evidence。"
                "常平平籴/和籴亦同（_changping_trade/_state_grain_trade 只返回值，"
                "不入统计）。"),
        note=("容量＝可售粮×本路粮价的**上限**，不是实发收入；"
              "实发取决于当月撮合与买方支付能力。" if cls == "农" else
              "容量＝可售粮×本路粮价的**上限**，不是实发收入。"),
    )


def _slot_wage_labor(state, pref: Optional[dict], pop: dict, cls: str) -> Dict[str, Any]:
    """工资/工钱：读本路建筑表判断**岗位是否存在**；实发额无宋境权威字段。"""
    if not isinstance(pref, dict) or "buildings" not in pref:
        jobs, bcount, bnote = None, None, "本路无 `buildings` 键（缺失 ≠ 无岗位）"
    else:
        b = pref.get("buildings")
        if not isinstance(b, dict):
            jobs, bcount, bnote = None, None, "本路 `buildings` 非 dict（不可读）"
        elif not b:
            jobs, bcount, bnote = 0, 0, "本路建筑表为空字典（确实无岗位）"
        else:
            bcount = len(b)
            staffed = [e.get("staffed") for e in b.values() if isinstance(e, dict)]
            if staffed and all(isinstance(x, (int, float)) for x in staffed):
                jobs = int(sum(int(x or 0) for x in staffed))
                bnote = "本路建筑表带 `staffed` 岗位数"
            else:
                jobs = None
                bnote = ("本路建筑表非空但**无 `staffed` 岗位字段**（`allocate_employment` "
                         "每次调用现算、不落档）⇒ 岗位数不可读，缺失≠0")
    return _slot(
        "wage_labor",
        available=(None if jobs is None else bool(jobs > 0)),
        capacity={"jobs_staffed": jobs, "buildings_count": bcount,
                  "wage_pool_upper_bound": None, "buildings_note": bnote},
        capacity_bound=None,
        realized=None,
        record_key=None,
        record_window=None,
        reason=("工资**实发额无宋境权威记录字段**：`pay_wages_from_revenue` 的唯一调用方是"
                "core/settlement_econ.py:849（外邦 regime 路径），其返回值只落在该 regime 的"
                "暂存 `st['wages']`（settlement_econ.py:1097），"
                "`prefectures[路]` 无对应字段；工资率表 `WAGE_RATE` 亦只在外邦配置"
                "（content/data_external.py）。"),
    )


def _slot_logistics(state, pref: Optional[dict], pop: dict, cls: str) -> Dict[str, Any]:
    """运输/仓储服务收入：宋境路级**距离/费率未建模**，实发额无记录 ⇒ 如实不可判定。"""
    return _slot(
        "logistics_service",
        available=None,
        capacity={
            "distance_km": None,
            "freight_rate": None,
            "terrain": None,
            "value_upper_bound": None,
            "canal_block_state": _int(getattr(state, "canal_block", None), None),
            "pref_changping_stock": (_int(pref.get("changping_stock"), None)
                                     if isinstance(pref, dict) else None),
        },
        capacity_bound=None,
        realized=None,
        record_key=None,
        record_window=None,
        reason=("运费收入**无按路/按阶层权威记录**：`core.domains.economy.dynamic_price.civil_logistics / "
                "gov_logistics` 需要 `distance_km × terrain × war` 算费率，"
                "宋境路级**无距离字段**；且该两函数在 `game/` 下**无调用方**"
                "（通道已定义但未接线）⇒ 本路实发额不可判定，报 `None` 而非 0。"
                "`granary_stats['canal_in'/'canal_loss']` 是**漕运粮量（石）**，"
                "不是运费收入，不得当作钱。"),
    )


def _slot_workshop(state, pref: Optional[dict], pop: dict, cls: str) -> Dict[str, Any]:
    """作坊/农业岗位收入：工匠侧读**可售成品池**（容量上限）；其余阶层如实不可判定。"""
    from core.domains.economy.market import sellable_stock
    from core.market_price import effective_buy_price
    route = None
    if isinstance(pref, dict):
        # 路名由调用方注入（见 income_source_readout），此处只用到 pop 自身
        route = pref.get("_readout_route_name")
    goods = pop.get("goods") if isinstance(pop.get("goods"), dict) else {}
    per_dim: Dict[str, Any] = {}
    vals: List[float] = []
    # 2026-10-03：只遍历**商品维**（`goods` 另含 `治所→{dim:n}` 州府桶）。
    from core.domains.economy.material_trade_ops import commodity_dims
    for dim in sorted(commodity_dims(goods)):
        qty = sellable_stock(seller=pop, dim=dim)
        px = effective_buy_price(dim=dim, state=state, pref=route).get("price")
        val = (None if (px is None or px <= 0) else qty * float(px))
        per_dim[dim] = {"sellable_qty": qty, "buy_price": px, "value_upper_bound": val}
        if val is not None:
            vals.append(val)
    # 一件都算不出 ⇒ None（缺失≠0：可能是价格不可读，不是"池子空"）
    total_bound = (sum(vals) if vals else None)
    ws_table = getattr(state, "workshops", None)
    is_artisan_pool = (cls == "工匠")
    return _slot(
        "workshop_agriculture_job",
        available=(None if total_bound is None else bool(total_bound > 0)),
        capacity={
            "goods_pool_by_dim": per_dim,
            "goods_pool_value_upper_bound": total_bound,
            "workshop_table_present": isinstance(ws_table, dict),
            "workshop_table_is_route_keyed": (
                isinstance(ws_table, dict) and any("_" in k for k in list(ws_table)[:1])),
            "staff_table": "prefectures[路].buildings",
        },
        capacity_bound=("upper_bound" if is_artisan_pool else None),
        realized=None,
        record_key=None,
        record_window=None,
        reason=(
            "工钱/农业岗位实发额**无按路按阶层权威字段**：`pay_wages_from_revenue` 只在外邦"
            "路径调用（settlement_econ.py:849）；宋境 `prefectures[路]` 无岗位表落档。"
            if not is_artisan_pool else
            "成品销售实发额**无按路按阶层权威字段**：`state.workshops` 的键名含路名"
            "（如 `麻坊_京畿路_2`），但 settlement_econ.py:1609-1634 明确『作坊产出是"
            "**全局**记账、不分路』，成品按各路**工匠 size 占比**分派到 goods 池 ⇒ "
            "**收入无法按路归因**。全国侧仅有 `statistics['export_income']`"
            "（**累计外销变现·贯**，100% 归工匠，无路归属），见 national_evidence。"),
        note=("容量＝本路工匠可售成品池×本路买入价的**上限**；外销另计（外部钱入）。"
              if is_artisan_pool else ""),
    )


def _slot_public(state, pref: Optional[dict], pop: dict, cls: str) -> Dict[str, Any]:
    """官府给付/赈济：读**可拨付预算**（本路府库/国库/内帑）；实发额无分层记录。"""
    lt = (_int(pref.get("local_treasury"), None) if isinstance(pref, dict) else None)
    tr = _int(getattr(state, "treasury", None), None)
    imp = _int(getattr(state, "imperial_treasury", None), None)
    cp = (_int(pref.get("changping_stock"), None) if isinstance(pref, dict) else None)
    return _slot(
        "public_grant_relief",
        available=None,
        capacity={
            "pref_local_treasury": lt,
            "state_treasury": tr,
            "state_imperial_treasury": imp,
            "pref_changping_stock_stone": cp,
            "grant_pool_upper_bound": lt,       # 本路可拨付上限＝本路府库
        },
        capacity_bound="upper_bound",
        realized=None,
        record_key=None,
        record_window=None,
        reason=("官府给付实发额**无按路按阶层权威记录**：营造/修缮服务费、工赈、加俸、"
                "宗室俸禄分别走 `distribute_cash` / `free_effect._apply_money_delta` / "
                "`transfer_public_funds_to_pops`，均**只写 POP wealth，不落统计**。"
                "赈济是**粮**不是钱：`granary_stats['relief']` 为累计发粮（石），"
                "且经 `settlement_granary._settle_disaster` 主要回补**流民/农户**"
                "（粮账），不得计为钱收入。"),
    )


_SLOTTERS = {
    "grain_sale": _slot_grain_sale,
    "wage_labor": _slot_wage_labor,
    "logistics_service": _slot_logistics,
    "workshop_agriculture_job": _slot_workshop,
    "public_grant_relief": _slot_public,
}


# ============================================================== 全国累计证据（非分层实发）

def _national_evidence(state) -> Dict[str, Any]:
    """**全国累加**的权威记录键（窗口已标注，**不得**与单月/分层级比大小）。

    这些是"确实记过"的证据；它们**不是**某路某阶层的实发收入，
    故只在 `national_evidence` 单列，**不填进**逐行 `realized`。
    """
    gs = getattr(state, "granary_stats", None)
    gs = gs if isinstance(gs, dict) else None
    st = getattr(state, "statistics", None)
    st = st if isinstance(st, dict) else None
    ev: Dict[str, Any] = {
        "window": "cumulative-national",
        "note": ("以下均为**全国累加**值（无月度清零），**不是**单月流量、"
                 "**不是**按路/按阶层实发额；不可与 capacity 上限或单月数字比大小。"),
        "items": {},
    }
    for key, owner, unit in (
        ("grain_market_trade", "granary_stats", "石（粮市撮合成交量）"),
        ("relief", "granary_stats", "石（赈济发粮，非钱）"),
        ("workshop_feed", "granary_stats", "石（作坊耗粮）"),
        ("canal_in", "granary_stats", "石（漕运入粮，非运费收入）"),
        ("canal_loss", "granary_stats", "石（漕运损耗）"),
        ("export_income", "statistics", "贯（外销变现，100% 归工匠，无路归属）"),
        ("goods_spend", "statistics", "贯（可选品成交额累计）"),
        ("workshop_finished_goods", "statistics", "件（成品维产出累计）"),
    ):
        src = gs if owner == "granary_stats" else st
        present = isinstance(src, dict) and key in src
        ev["items"][key] = {
            "owner": f"state.{owner}",
            "value": (_num(src.get(key), None) if present else None),
            "unit": unit,
            "present": present,
            "per_route": False,
            "per_class": False,
        }
    return ev


# ============================================================== 1 · 收入来源拆分读数

def income_source_readout(state, *, routes: Optional[Sequence[str]] = None,
                          classes: Optional[Sequence[str]] = None,
                          max_rows: Optional[int] = None) -> Dict[str, Any]:
    """按**路 × 阶层**拆分收入来源（回答"这个 POP 阶层的钱从哪来"）。

    返回
    ----
    ```
    {schema_version, source_keys, source_labels,
     by_route: [{route, by_class: {cls: {size, wealth, grain, per_capita_wealth,
                                         sources: {key: slot}}},
                 open_channels: [key], total_wealth}],
     by_class_totals: {cls: {size, wealth, open_channels, source_keys_open}},
     national_evidence, truncated: {...}, warnings: [...], note}
    ```

    **每条来源都同时给 `capacity`（可参与容量，`bound` 标注精确/上限）
    与 `realized`（实发额，只读既有记录键）**；`realized` 读不到一律 `None` ＋ `reason`。

    - `routes` / `classes` 缺省＝全部；**未知路/阶层 → `ValueError`**；
    - `max_rows` 非正 → `ValueError`；超出时截断并如实报 `truncated`；
    - **不改 `state`、不改 `statistics`**。
    """
    if max_rows is not None:
        m = _int(max_rows, None)
        if m is None or m <= 0:
            raise ValueError(f"max_rows 须为正整数或 None，收到 {max_rows!r}")
        max_rows = m
    prefs, sel_routes, sel_classes = _check_scope(state, routes, classes)
    warnings: List[str] = []
    if prefs is None:
        return {
            "schema_version": INCOME_READOUT_SCHEMA_VERSION,
            "source_keys": list(SOURCE_KEYS), "source_labels": dict(SOURCE_LABELS),
            "by_route": [], "by_class_totals": {},
            "national_evidence": _national_evidence(state),
            "truncated": {"routes": 0, "note": "无路可列。"},
            "warnings": ["state.prefectures 缺失或非 dict：收入来源不可读"],
            "note": "缺 state.prefectures ⇒ 无路/阶层可拆，**不回落 0**。",
        }

    by_route: List[Dict[str, Any]] = []
    totals: Dict[str, Any] = {}
    truncated_routes = 0
    shown = list(sel_routes) if max_rows is None else list(sel_routes[:max_rows])
    truncated_routes = max(0, len(sel_routes) - len(shown))
    for r in shown:
        pref = prefs.get(r)
        pops = pref.get("pops") if isinstance(pref, dict) else None
        if not isinstance(pops, dict):
            warnings.append(f"{r}: 无 `pops` 子字典（缺失，**不当 0 人**）")
            by_route.append({"route": r, "by_class": {}, "open_channels": [],
                             "total_wealth": None, "readable": False})
            continue
        # 供 `_slot_workshop` 读本路价（`effective_buy_price` 需要路名）
        _pref_view = dict(pref) if isinstance(pref, dict) else {}
        _pref_view["_readout_route_name"] = r
        by_c: Dict[str, Any] = {}
        r_open: List[str] = []
        r_wealth: Optional[int] = 0
        for cls in sel_classes:
            pop = pops.get(cls)
            if not isinstance(pop, dict):
                by_c[cls] = None          # 缺失≠0：该路无此阶层记录
                warnings.append(f"{r}/{cls}: 无该阶层 POP 记录（缺失，**不当 0 人**）")
                continue
            size = _int(pop.get("size"), None)
            wealth = _int(pop.get("wealth"), None)
            srcs = {k: _SLOTTERS[k](state, _pref_view, pop, cls) for k in SOURCE_KEYS}
            opens = [k for k, s in srcs.items() if s.get("available") is True]
            r_open.extend(opens)
            if r_wealth is not None and wealth is not None:
                r_wealth += wealth
            else:
                r_wealth = None
            per_capita = (None if (size is None or size <= 0 or wealth is None)
                          else wealth / float(size))
            row = {
                "size": size, "wealth": wealth,
                "grain": _int(pop.get("grain"), None),
                "per_capita_wealth": per_capita,
                "per_capita_note": ("size ≤ 0 或不可读 ⇒ 人均财富为 None（**不除零、不回落 0**）"
                                    if per_capita is None else ""),
                "sources": srcs,
                "open_channels": opens,
            }
            by_c[cls] = row
            t = totals.setdefault(cls, {"size": 0, "wealth": 0, "open_channels": set(),
                                        "size_readable": True, "wealth_readable": True})
            if size is None:
                t["size_readable"] = False
            else:
                t["size"] += size
            if wealth is None:
                t["wealth_readable"] = False
            else:
                t["wealth"] += wealth
            t["open_channels"].update(opens)
        by_route.append({
            "route": r, "by_class": by_c,
            "open_channels": sorted(set(r_open)),
            "total_wealth": r_wealth, "readable": True,
        })
    totals_out: Dict[str, Any] = {}
    for cls, t in totals.items():
        totals_out[cls] = {
            "size": (t["size"] if t["size_readable"] else None),
            "wealth": (t["wealth"] if t["wealth_readable"] else None),
            "open_channels": sorted(t["open_channels"]),
            "open_channel_count": len(t["open_channels"]),
            "size_readable": t["size_readable"],
            "wealth_readable": t["wealth_readable"],
        }
    return {
        "schema_version": INCOME_READOUT_SCHEMA_VERSION,
        "source_keys": list(SOURCE_KEYS),
        "source_labels": dict(SOURCE_LABELS),
        "source_code_paths": dict(SOURCE_CODE_PATHS),
        "by_route": by_route,
        "by_class_totals": totals_out,
        "national_evidence": _national_evidence(state),
        "truncated": {"routes": truncated_routes,
                      "note": "阶层维度不截断（全 6 类恒列出）；`max_rows` 只限路数。"},
        "warnings": warnings,
        "note": ("本读数是**派生视图**，不含任何新增账本：`realized` 只读既有权威记录键，"
                 "读不到即 `None` ＋ `reason`（**不用 0 冒充没赚到钱**）；"
                 "`capacity` 是容量上限，**不是**实发收入。"),
    }


# ============================================================== 2 · 购买力读数

def purchasing_power_readout(state, *, routes: Optional[Sequence[str]] = None,
                              classes: Optional[Sequence[str]] = None
                              ) -> Dict[str, Any]:
    """每阶层的**购买力**与"离温饱线还差多少"（余量释放**读** `demand.demand_release`）。

    返回 `{by_route: [{route, by_class: {cls: row}}], by_class_totals, warnings, note}`，
    `row = {size, wealth, per_capita_wealth, subsistence_line, subsistence_scale,
    gap_to_subsistence, release, release_source, above_subsistence,
    grain_price, monthly_grain_need_stone, own_grain_stone,
    grain_self_sufficiency, food_purchasing_ability_stone, income_channels_open}`。

    - `release` 口径**完全委托** `core.domains.economy.demand.demand_release`（本模块不改 `demand.py`）；
    - `size ≤ 0` ⇒ `per_capita_wealth=None`、`release=None`（**不除零**）；
    - `monthly_grain_need_stone ≤ 0` ⇒ `grain_self_sufficiency=None`（不是"完全自给"）。
    """
    from core.domains.economy.demand import demand_release
    prefs, sel_routes, sel_classes = _check_scope(state, routes, classes)
    warnings: List[str] = []
    if prefs is None:
        return {"by_route": [], "by_class_totals": {}, "warnings":
                ["state.prefectures 缺失：购买力不可读"], "note": "缺失不作 0。"}
    by_route: List[Dict[str, Any]] = []
    tot: Dict[str, Any] = {}
    for r in sel_routes:
        pref = prefs.get(r)
        pops = pref.get("pops") if isinstance(pref, dict) else None
        if not isinstance(pops, dict):
            warnings.append(f"{r}: 无 `pops`（缺失，**不当 0 人**）")
            by_route.append({"route": r, "by_class": {}, "readable": False})
            continue
        by_c: Dict[str, Any] = {}
        for cls in sel_classes:
            pop = pops.get(cls)
            if not isinstance(pop, dict):
                by_c[cls] = None
                continue
            size = _int(pop.get("size"), None)
            wealth = _int(pop.get("wealth"), None)
            grain = _int(pop.get("grain"), None)
            # 人均财富按 4 位小数**先取整再**参与口径计算：读数自身即可复算
            # （否则调用方用读出的值重算 `demand_release` 会与本行对不上）。
            per_cap_raw = (None if (size is None or size <= 0 or wealth is None)
                           else wealth / float(size))
            per_cap = (None if per_cap_raw is None else round(per_cap_raw, 4))
            line, scale = _subsistence(cls)
            gap = (None if (per_cap is None or line is None) else per_cap - line)
            rel = demand_release(cls, per_cap)          # ← 口径单点：读，不改
            per = _grain_need_per_capita(cls)
            # 🟢 M35-C-2：粮需按**有效人口**（含职业附加）——单点口径
            from core.foundation.ledger.occupation import food_need_of_pool
            need = (None if (per is None or size is None)
                    else int(food_need_of_pool(pop, cls, per)))
            price, _src = _grain_price(pref, state)
            self_suff = (None if (need is None or need <= 0 or grain is None)
                         else round(min(1.0, grain / float(need)), 4))
            buyable = (None if (wealth is None or price is None or price <= 0)
                       else round(wealth / price, 4))
            row = {
                "size": size, "wealth": wealth, "grain": grain,
                "per_capita_wealth": per_cap,
                "subsistence_line": line,
                "subsistence_scale": scale,
                "subsistence_configured": cls in (_cfg("SUBSISTENCE_LINE", {}) or {}),
                "gap_to_subsistence": None if gap is None else round(gap, 4),
                "release": rel,
                "release_source": "core.domains.economy.demand.demand_release",
                "above_subsistence": (None if rel is None else bool(rel > 0)),
                "grain_price": price,
                "monthly_grain_need_stone": need,
                "own_grain_stone": grain,
                "grain_self_sufficiency": self_suff,
                "food_purchasing_ability_stone": buyable,
                "food_purchasing_ability_source": (
                    "wealth / 本路粮价（与 core.settlement_common.food_insecure_headcount "
                    "的 `buyable` 同口径：钱能买多少粮）"),
            }
            by_c[cls] = row
            t = tot.setdefault(cls, {"size": 0, "wealth": 0, "per_cap_w": 0.0,
                                     "size_readable": True, "wealth_readable": True,
                                     "withheld": 0, "released": 0, "unknown": 0})
            if size is None:
                t["size_readable"] = False
            else:
                t["size"] += size
            if wealth is None:
                t["wealth_readable"] = False
            else:
                t["wealth"] += wealth
            if per_cap is not None:
                t["per_cap_w"] += per_cap
            if rel is None:
                t["unknown"] += 1
            elif rel > 0:
                t["released"] += 1
            else:
                t["withheld"] += 1
        by_route.append({"route": r, "by_class": by_c, "readable": True})
    tot_out: Dict[str, Any] = {}
    for cls, t in tot.items():
        cap = t["size"] if t["size_readable"] else 0
        if not t["size_readable"]:
            note = "size 不可读（缺失）⇒ 人均财富 None（**不回落 0**）"
        elif cap <= 0:
            note = "各路 size 全为 0（无人口）⇒ 人均财富 None（**不除零、不造 0/1.0**）"
        else:
            note = ("**加权**人均＝Σ(各路人均)/路数（非 Σwealth/Σsize，"
                    "各路 size 不同时二者不等价）")
        tot_out[cls] = {
            "size": t["size"] if t["size_readable"] else None,
            "wealth": t["wealth"] if t["wealth_readable"] else None,
            "per_capita_wealth": (round(t["per_cap_w"] / cap, 4) if cap > 0 else None),
            "per_capita_note": note,
            "routes_released": t["released"],
            "routes_withheld": t["withheld"],
            "routes_release_unknown": t["unknown"],
        }
    return {
        "by_route": by_route,
        "by_class_totals": tot_out,
        "warnings": warnings,
        "note": ("`release` 口径**完全委托** `core.domains.economy.demand.demand_release`"
                 "（温饱线 × 余量释放）；本读数**不改** `demand.py`。"
                 "`per_capita_wealth` 在 size ≤ 0 时为 None（**不除零**）。"),
    }


# ============================================================== 3 · 市场再进入判定

def _check_income(income: Any) -> Optional[float]:
    """反事实注入收入校验：**拒绝式**（负数/非数值/非有限 → `ValueError`）。"""
    if income is None:
        return None
    if isinstance(income, bool) or not isinstance(income, (int, float)):
        raise ValueError(f"income 须为数值（贯）或 None，收到 {income!r}")
    f = float(income)
    if f != f or f in (float("inf"), float("-inf")):
        raise ValueError(f"income 须为有限数，收到 {income!r}")
    if f < 0:
        raise ValueError(f"income（贯）不得为负，收到 {income!r}")
    return f


def _reentry_row(state, route: str, cls: str, pop: dict, income: Optional[float]
                 ) -> Dict[str, Any]:
    """单个 (路, 阶层) 的再进入判定（**纯反事实**：不改 state）。"""
    from core.domains.economy.demand import demand_release, resolve_purchase_plan
    from core.domains.economy.market import sellable_stock
    from core.market_price import effective_buy_price

    size = _int(pop.get("size"), None)
    wealth = _int(pop.get("wealth"), None)
    # 与 `purchasing_power_readout` 同口径：人均先按 4 位小数取整再参与计算
    per_cap = (None if (size is None or size <= 0 or wealth is None)
               else round(wealth / float(size), 4))
    rel_now = demand_release(cls, per_cap)
    wealth_after = (None if (wealth is None or income is None) else wealth + income)
    per_cap_after = (None if (size is None or size <= 0 or wealth_after is None)
                     else round(wealth_after / float(size), 4))
    rel_after = (demand_release(cls, per_cap_after) if per_cap_after is not None else None)

    pref_dem = _goods_demand(cls)
    prices: Dict[str, Any] = {}
    base_prices: Dict[str, Any] = {}
    for dim in pref_dem:
        prices[dim] = effective_buy_price(dim=dim, state=state, pref=route).get("price")
        base_prices[dim] = effective_buy_price(
            dim=dim, state=None, pref=route, use_dynamic=False).get("price")
    held = pop.get("goods") if isinstance(pop.get("goods"), dict) else {}
    # 卖方＝本路工匠（宋境商品唯一真实卖方，见 settlement_granary.py:274/318）
    seller = None
    pops = ((getattr(state, "prefectures", None) or {}).get(route) or {}).get("pops")
    if isinstance(pops, dict) and isinstance(pops.get("工匠"), dict):
        seller = pops.get("工匠")
    supply = {d: sellable_stock(seller=seller, dim=d) for d in pref_dem}
    no_stock_dims = [d for d, q in supply.items() if q <= 0]

    plan_now = resolve_purchase_plan(
        cls=cls, pop_size=max(0, size or 0), per_capita_wealth=per_cap,
        pref=pref_dem, held=held, prices=prices, base_prices=base_prices, budget=wealth)
    plan_after = (None if per_cap_after is None else resolve_purchase_plan(
        cls=cls, pop_size=max(0, size or 0), per_capita_wealth=per_cap_after,
        pref=pref_dem, held=held, prices=prices, base_prices=base_prices,
        budget=wealth_after))

    if income is None:
        verdict, blocking = "not_assessed", "income_not_specified"
    elif rel_after is None:
        verdict, blocking = "not_assessed", "per_capita_wealth_unreadable"
    elif plan_after is None:
        verdict, blocking = "not_assessed", "plan_unavailable"
    elif rel_after <= 0:
        # 注入收入后仍**在温饱线以下** ⇒ 收入不是唯一闸门，需求不响应
        verdict, blocking = "still_withheld", "below_subsistence"
    elif not plan_after["items"]:
        # 闸门已越过但仍无购买项：被耐用品已足 / 无目标品类挡住，**不是钱的问题**
        verdict = "still_withheld"
        blocking = plan_after.get("reason") or "no_target_demand"
    elif rel_now is not None and rel_now > 0:
        # 本来就已越过温饱线 ⇒ 注入收入**不是**"再进入"的必要条件
        verdict, blocking = "already_released", None
    else:
        # 原本被温饱线挡住，注入收入后闸门越过且产生购买项 ⇒ **需求可响应**
        verdict, blocking = "responsive", None
    return {
        "route": route, "cls": cls,
        "size": size, "wealth": wealth,
        "income_coin_assumed": income,
        "wealth_after": wealth_after,
        "per_capita_wealth_now": per_cap,
        "per_capita_wealth_after": per_cap_after,
        "release_now": rel_now,
        "release_after": rel_after,
        "release_source": "core.domains.economy.demand.demand_release",
        "plan_now": (None if plan_now is None else {
            "release": plan_now.get("release"), "no_demand": plan_now.get("no_demand"),
            "reason": plan_now.get("reason"),
            "item_kinds": sorted({i.get("kind") for i in plan_now.get("items", [])})}),
        "plan_after": (None if plan_after is None else {
            "release": plan_after.get("release"), "no_demand": plan_after.get("no_demand"),
            "reason": plan_after.get("reason"),
            "item_kinds": sorted({i.get("kind") for i in plan_after.get("items", [])})}),
        "local_sellable_by_dim": supply,
        "supply_blocker_dims": no_stock_dims,
        "supply_blocked": bool(no_stock_dims) and bool(pref_dem),
        "verdict": verdict,
        "blocking": blocking,
        "notes": (["注入收入只作**反事实**评估：读数**不写** state，也不代表当月已发生。"] +
                  (["本路本阶层所需商品**无货**（`no_stock_local`）：恢复收入也买不到，"
                    "须修供给而非购买力。"] if no_stock_dims and pref_dem else [])),
    }


def market_reentry(state, *, routes: Optional[Sequence[str]] = None,
                   classes: Optional[Sequence[str]] = None,
                   income: Optional[float] = None) -> Dict[str, Any]:
    """**市场再进入判定**：重新获得收入后，可选商品需求能否响应（与 `demand_release` 同口径）。

    `income`（贯）为**反事实注入额**（如"本月售粮得 X 贯"或"获得一份工钱"），
    读数把它**只用于评估**，**不落 state、不改 statistics**。

    返回 `{income_coin_assumed, by_route: [{route, by_class: {cls: row}}],
    verdicts: {responsive/still_withheld/not_assessed: n}, warnings, note}`，
    `verdict ∈ {"responsive", "already_released", "still_withheld", "not_assessed"}`：
    - `responsive`：原本被温饱线挡住，注入收入后余量释放**越过门槛**且
      `resolve_purchase_plan` 产出购买项 ⇒ **需求能响应**；
    - `already_released`：注入前**已**越过温饱线 ⇒ 收入**不是**闸门，本次注入不构成
      "再进入"（如实标明，避免把本来就买的人算成"被收入救回"）；
    - `still_withheld`：仍被**温饱线**（`blocking="below_subsistence"`）或
      无目标品类挡住 ⇒ 收入不足以越过门槛；
    - `not_assessed`：`income` 未给 / 人均财富不可读 ⇒ **不臆造**。

    `supply_blocked` 单独标出"有收入但本路无货"，使**收入问题与供给问题可分辨**。
    """
    inc = _check_income(income)
    prefs, sel_routes, sel_classes = _check_scope(state, routes, classes)
    warnings: List[str] = []
    if prefs is None:
        return {"income_coin_assumed": inc, "by_route": [], "verdicts": {},
                "warnings": ["state.prefectures 缺失：再进入判定不可读"],
                "note": "缺失不作 0/1.0。"}
    by_route: List[Dict[str, Any]] = []
    verdicts: Dict[str, int] = {}
    for r in sel_routes:
        pref = prefs.get(r)
        pops = pref.get("pops") if isinstance(pref, dict) else None
        if not isinstance(pops, dict):
            warnings.append(f"{r}: 无 `pops`（缺失）")
            by_route.append({"route": r, "by_class": {}, "readable": False})
            continue
        by_c: Dict[str, Any] = {}
        for cls in sel_classes:
            pop = pops.get(cls)
            if not isinstance(pop, dict):
                by_c[cls] = None
                continue
            row = _reentry_row(state, r, cls, pop, inc)
            by_c[cls] = row
            verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1
        by_route.append({"route": r, "by_class": by_c, "readable": True})
    return {
        "income_coin_assumed": inc,
        "by_route": by_route,
        "verdicts": verdicts,
        "warnings": warnings,
        "note": ("需求响应口径**完全委托** `core.domains.economy.demand.demand_release` / "
                 "`resolve_purchase_plan`（本模块**不改** `demand.py`）；"
                 "买入价读 `core.market_price.effective_buy_price`（本路路级价），"
                 "可售量读 `core.domains.economy.market.sellable_stock`。"
                 "`income` 是**反事实**假设值，不落 state。"),
    }


# ============================================================== 4 · 消费退出 ≠ 饥饿

def consumption_exit_vs_hunger(state, *, routes: Optional[Sequence[str]] = None
                               ) -> Dict[str, Any]:
    """把**消费退出**与**饥饿**并列读出，**互不推导**（B2-R5 放行证据之二）。

    | 概念 | 唯一口径 | 含义 |
    |---|---|---|
    | `consumption_exit` | `demand_release` == 0 | 可选商品**不买了**（**正确的需求结果**） |
    | `hunger_headcount` | `food_insecure_headcount` | **吃不上饭**人数（逃荒触发源） |

    纪律：
    - **可选品成交为 0 是消费退出，不得读成饥饿**；两者同时成立时**并列**输出，
      `misreport_risk=True` 提醒"勿用其一替代另一"；
    - `hunger` 只认 `core.settlement_common.food_insecure_headcount`
      （含 `purchasing_power_short` 归因）；
      粮价不可读时 `hunger=None` ＋ 原因（**不回落 0**）；
    - 饥饿人数**受 `FLEE_CAP_PER_ROUTE` 逐路封顶**（同 `famine_attribution`），
      不可与累加人月 `statistics["grain_hungry"]` 比大小。
    """
    from core.population_readout import famine_attribution
    prefs, sel_routes, _sel_classes = _check_scope(state, routes, None)
    warnings: List[str] = []
    if prefs is None:
        return {"by_class": {}, "optional_market_evidence": None,
                "hunger_evidence": None,
                "warnings": ["state.prefectures 缺失：无法区分消费退出与饥饿"],
                "note": "缺失不作 0。"}
    price = _num(getattr(state, "grain_price", None), None)
    price_ok = price is not None and price > 0
    if not price_ok:
        warnings.append("state.grain_price 不可读/非正 → 饥饿维度**不可判定**（报 None，不回落 0）")
    att: Dict[str, Any] = {}
    if price_ok:
        try:
            att = famine_attribution(state) or {}
        except Exception as exc:                          # noqa: BLE001 — 读数不阻断
            warnings.append(f"famine_attribution 执行失败：{exc}")
            att = {}
    att_by_class = att.get("by_class") if isinstance(att.get("by_class"), dict) else {}
    att_note = str(att.get("note", "") or "")
    # `famine_attribution` 有两条"降级为不可判定"的早退路径（粮价不可读 /
    # `food_insecure_headcount` 不可用或抛错）——此时 `by_class` 也是空，
    # **必须**与"真的没人缺粮"区分开，否则把不可判定读成 0。
    att_degraded = any(m in att_note for m in ("不可用", "执行失败", "不可判定"))

    # 消费退出：按路×阶层用 `demand_release` 判定（`size ≤ 0` ⇒ 不可判定）
    exit_rows: Dict[str, Any] = {}
    for r in sel_routes:
        pref = prefs.get(r)
        pops = pref.get("pops") if isinstance(pref, dict) else None
        if not isinstance(pops, dict):
            continue
        for cls in POP_CLASSES:
            pop = pops.get(cls)
            if not isinstance(pop, dict):
                continue
            size = _int(pop.get("size"), None)
            wealth = _int(pop.get("wealth"), None)
            per_cap = (None if (size is None or size <= 0 or wealth is None)
                       else wealth / float(size))
            from core.domains.economy.demand import demand_release
            rel = demand_release(cls, per_cap)
            slot = exit_rows.setdefault(cls, {
                "routes_total": 0, "routes_withheld": 0, "routes_released": 0,
                "routes_unknown": 0, "withheld_routes": [],
                "per_capita_wealth_min": None, "per_capita_wealth_max": None,
            })
            slot["routes_total"] += 1
            if rel is None:
                slot["routes_unknown"] += 1
                continue
            if rel > 0:
                slot["routes_released"] += 1
                continue
            slot["routes_withheld"] += 1
            slot["withheld_routes"].append(r)
            if per_cap is not None:
                lo, hi = slot["per_capita_wealth_min"], slot["per_capita_wealth_max"]
                slot["per_capita_wealth_min"] = per_cap if lo is None else min(lo, per_cap)
                slot["per_capita_wealth_max"] = per_cap if hi is None else max(hi, per_cap)

    st = getattr(state, "statistics", None)
    st = st if isinstance(st, dict) else None
    gsp = _num(st.get("goods_spend"), None) if isinstance(st, dict) else None
    gtr = st.get("goods_traded") if isinstance(st, dict) else None
    opt_ev = {
        "goods_spend": gsp,
        "goods_traded": (dict(gtr) if isinstance(gtr, dict) else None),
        "record_window": "cumulative-national",
        "zero_means": ("累计成交额为 0 ⇒ 至今**无**可选品成交；"
                       "**不是**饥饿证据（累积口径，非当月）"),
        "present": isinstance(st, dict) and "goods_spend" in st,
    }
    hung_ev = {
        "source": ("core.settlement_common.food_insecure_headcount"
                   "（经 population_readout.famine_attribution）"),
        "grain_price": price,
        "grain_price_readable": price_ok,
        "capped_per_route": True,
        "capped_note": ("`food_insecure_headcount` 受 FLEE_CAP_PER_ROUTE 逐路封顶；"
                        "`total_shortfall` 是**封顶后**求和，不可与 "
                        "`statistics['grain_hungry']`（累加人月）比大小。"),
        "attribution_note": att.get("note", ""),
    }
    by_class: Dict[str, Any] = {}
    for cls in POP_CLASSES:
        ex = exit_rows.get(cls, {"routes_total": 0, "routes_withheld": 0,
                                 "routes_released": 0, "routes_unknown": 0,
                                 "withheld_routes": [],
                                 "per_capita_wealth_min": None,
                                 "per_capita_wealth_max": None})
        hungry = None
        reason = None
        h_reason = None
        if not price_ok:
            reason = "grain_price_unreadable"
        elif att_degraded:
            reason = "famine_attribution_degraded"
            warnings.append(
                "famine_attribution 走了不可判定早退路径 ⇒ 饥饿维度报 None，"
                "**不回落 0**（见 attribution_note）")
        else:
            slot = att_by_class.get(cls)
            if isinstance(slot, dict):
                hungry = _int(slot.get("shortfall_headcount"), None)
                h_reason = slot.get("reason")
            else:
                # `famine_attribution` 只登记 hungry>0 的阶层；此处缺席是
                # **"当月该阶层无人缺粮"的合法 0**，不是缺失。
                hungry = 0
                h_reason = "no_shortfall_this_month"
        consumption_exit = (ex["routes_withheld"] > 0) if ex["routes_total"] > 0 else None
        by_class[cls] = {
            "consumption_exit": consumption_exit,
            "consumption_exit_reason": (
                None if consumption_exit is None else
                ("all_routes_withheld" if ex["routes_withheld"] == ex["routes_total"]
                 else "some_routes_withheld")),
            "consumption_exit_detail": ex,
            "hunger_headcount": hungry,
            "hunger_reason": h_reason,
            "hunger_unavailable_reason": reason,
            "hunger_source": hung_ev["source"],
            "coexist": (None if (consumption_exit is None or hungry is None)
                        else bool(consumption_exit and hungry > 0)),
            "misreport_risk": (None if (consumption_exit is None or hungry is None)
                               else bool(consumption_exit and hungry <= 0)),
            "misreport_note": ("消费退出且当月无人缺粮：可选品 0 成交**纯属消费退出**，"
                               "读数**不得**报成饥饿（反之饥饿也不得读成消费退出）。"),
        }
    return {
        "by_class": by_class,
        "optional_market_evidence": opt_ev,
        "hunger_evidence": hung_ev,
        "warnings": warnings,
        "note": ("**消费退出 ≠ 饥饿**：可选品成交为 0 由 `demand_release` 解释"
                 "（温饱线闸门，是**正确的需求结果**）；饥饿由 "
                 "`food_insecure_headcount` 解释（逃荒触发源）。"
                 "两者是**不同口径**，必须并列读，任何一方都不得推导另一方。"),
    }


# ============================================================== 组合入口

def build_income_readout(state, *, routes: Optional[Sequence[str]] = None,
                         classes: Optional[Sequence[str]] = None,
                         max_rows: Optional[int] = None,
                         income: Optional[float] = None) -> Dict[str, Any]:
    """B2-R5 总入口：收入来源拆分 ＋ 购买力 ＋ 再进入判定 ＋ 消费退出/饥饿分离。

    **纯派生只读**；任一子读数失败不抛异常，改为在 `warnings` 留痕（缺失不作 0）。
    """
    out: Dict[str, Any] = {
        "schema_version": INCOME_READOUT_SCHEMA_VERSION,
        "year": _int(getattr(state, "year", None), None),
        "month": _int(getattr(state, "month", None), None),
        "turn": _int(getattr(state, "turn", None), None),
    }
    warnings: List[str] = []
    plans = (("income_sources", lambda: income_source_readout(
                  state, routes=routes, classes=classes, max_rows=max_rows)),
             ("purchasing_power", lambda: purchasing_power_readout(
                  state, routes=routes, classes=classes)),
             ("reentry", lambda: market_reentry(
                  state, routes=routes, classes=classes, income=income)),
             ("consumption_vs_hunger", lambda: consumption_exit_vs_hunger(
                  state, routes=routes)))
    for key, fn in plans:
        try:
            out[key] = fn()
        except Exception as exc:                          # noqa: BLE001 — 读数不阻断
            out[key] = {"error": str(exc)}
            warnings.append(f"{key} 读数失败：{exc}")
    out["warnings"] = warnings
    out["read_only"] = True
    out["note"] = ("B2-R5 收入来源与市场再进入读数（**纯派生、不新建账本**）；"
                   "口径单点：`core.domains.economy.demand` / `core.domains.economy.market` / `core.market_price` / "
                   "`core.population_readout` 均只被**读取**，本模块不改它们。")
    return out
