# -*- coding: utf-8 -*-
"""B2-R6 · 外销与国内供给优先序（**口径单点**，规格 `market-civilian-economy` B2-R6）

## 为什么有这个模块

`tasks.md` §4 B2-R6 的指控（**实测事实**，同 §B2 待决问题 #3）：

B1 把宋境商品消费改成**真实成交**（`core/market.trade_goods`：扣钱 ⇄ 扣工匠 goods 池）后，
`settlement_granary.py` §3.5 存货外销段的触发条件 `_stock > _cap` **常常不成立**
（工匠池被国内成交抽空），`statistics["export_income"]` 于是**从未被写入**，
读数侧表现为 `None`。

规格同时裁定：**不要求**恢复旧 60 月 `export_income = 37.44M**（旧消费曾无卖方扣货，
旧外销收入可能与**虚拟内销共用同一份产能**）。真正要保证的是三条：

1. **国内有效需求优先**：先满足国内成交，超出本地承诺需求与合理库存的**真实剩余**才外销；
2. **同一批实物不得既内销又外销**；
3. **三态可区分**：`0`＝有记录、确无余货；`None`＝未记录/未定义；正数＝真实外销（钱货守恒＋登记来源）。

本模块把"能不能外销、外销多少、为什么"收成**一个纯函数**＋**一个写入口**，
结算层只负责取数与传参（不再就地重算口径）。

## 口径（B2-R6）

### 1. 优先序公式（单点）

```text
free    = max(0, stock − reserved_for_domestic)      # stock = 内销真成交后的真实库存
surplus = max(0, free  − stock_cap)                  # stock_cap = month_prod × EXPORT_STOCK_MONTHS
qty     = min(surplus, month_prod × EXPORT_RATE)     # 月外销上限（不倾倒库存）
income  = qty × price                                # price 来自 GOODS_PRICE（外销单价）
```

- `stock` **必须是内销之后的真实库存**。这是"不重复出售"的**结构性保证**：
  本模块从不读取月内销前的库存、也**不自行扣减**内销量（再扣一次就是重复扣减），
  所以已内销的货在物理上不可能再进入外销量。
- 调用方另传 `domestic_sold_qty`（本月本路本商品内销成交量）**仅供台账核对**；
  再传 `stock_before_domestic` 时会做交叉校验：`domestic_sold_qty > stock_before_domestic`
  直接**拒绝**（同一批货不可能卖出超过期初库存）。
- `reserved_for_domestic`＝`domestic_commitment_qty`：本路本商品**已形成但未成交**的
  国内需求（承诺需求预留）。**"国内优先"的显式体现**：有未满足需求 ⇒ 这批货先留国内。
  该字段当前结算尚未按 `(路, 商品)` 记录（`statistics["goods_unmet"]` 只按原因分桶），
  故缺省 0，并在 `warnings` 里**如实标注"未记录"**——"未记录"≠"没有未满足需求"。
- 取整一律 `int()` 截断，与 `settlement_granary.py` §3.5 现实现**逐项等价**
  （接线是"同一口径换单点"，**不是调参**）。

### 2. 三态语义（`None` ≠ `0` ≠ 正数）

| 值 | 语义 | `defined` | 触发条件 |
|---|---|---|---|
| `None` | **未记录/未定义** | `False` | 库存 / 月产 / 外销单价 / 策略参数缺失或不可读 |
| `0` | **有记录、确无余货** | `True` | 无产出、无库存、未超库存上限、国内未满足需求优先 |
| `>0` | **真实外销**（钱货守恒＋来源登记） | `True` | `qty > 0` |

非法输入（负数、NaN/Inf、bool、维度缺失、内销量超期初库存）**一律拒绝**：
`ok=False`、不改任何账、`detail` 说明原因——**不"善意修正"、不回落 0**。

### 3. 钱货守恒与来源登记（POP 挂载律）

- 货：`seller["goods"][dim] −= qty`（**POP 持仓**，与内销同一个池，**不新建账本**）；
- 钱：`seller["wealth"] += income`（**同一 POP 的 wealth**，即 POP 挂载点）；
- 来源：`register_money_flow(state, "external", income, "外销变现·<dim>")`
  ——外销是**体外注入**（货出宋境、钱入），**不是**内部划转；
- 写前复核：`apply_export_decision` 在写入前再核一次池中存量，不足则**整笔不发生**，
  不留单边账（与 `trade_goods` 的双向原子性一致）。

本模块只向 `statistics` 写**流量读数**（`export_month` / `export_income` / `export_qty` /
`export_decisions`，与既有 `goods_spend` / `goods_traded` 同类），
**不是与 POP 平行的钱粮账本**，不得当存量相加（POP 挂载律第 4 条）。

### 4. 与既有 `export_income` 口径的关系（易错点）

`state.statistics` **整局不清零**（`core/game_state.py:756` 建局时初始化，无按月重置），
故既有 `export_income` 是**累计**口径：

- 累计键**只在真实外销时累加**（现状不变，不制造假 0）；
- "本月确无外销 = 0"**无法**表达为累计值 0（累计 0 只在"整局从未外销"时成立），
  故新增 **`export_month`**（本月读数，携带 `income` 三态 ＋ `defined` ＋ `undefined_count`）；
- `export_month_readout` / `export_cumulative_readout` 各自把三态讲清楚，
  并能区分"本月判定过、确无余货"与"本月根本没判定/登记"。

## 命名纪律

参数用 `pref`（prefecture）**不用 `route`**——本仓库另有**真义路线**的 `route`
（外邦行军路线 `state.routes`），同名不同义极易踩坑（与 `core/market_price.pref_good_key`
一致）。`route_key` 字段复用 `pref_good_key` 的 `(路, 商品)` 口径（B2-R2）。

## 迁移策略

1. **不改** §3.5 既有触发语义（`min(存量−上限, 月产×0.3)`）：本模块公式与之**逐项等价**，
   接线是换单点而不是改参数，故不改变任何既有月度的结算结果。
2. 接线点：`settlement_granary.py` §3.5（`settlement_granary.py:375-403`）
   ——`export_decision` 取代就地 `if _stock > _cap` 判断，
   `apply_export_decision` 取代手写的 goods/wealth/`register_money_flow` 三行。
3. §3.5 现用**重估月产**（`工匠 size × 系数 × 生产力度`）作为库存上限基数，
   而非 `_settle_workshops` 登记的真实产出（真实产出只有整局合计
   `statistics["workshop_finished_goods"]`，无 `(路, 商品)` 粒度）。
   将来换成真实产出**只需改调用方传参**，本模块不动。
4. `domestic_commitment_qty` 待 `statistics["goods_unmet"]` 升级为 `(路, 商品)` 键后
   由调用方补传；在此之前 `warnings` 持续提示"承诺需求未记录"（缺失≠0）。
5. 未实施项：海商/外邦买方的**议价与批量**机制、跨路调拨后外销（当前只按本路逐路判定）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Optional

__all__ = [
    "EXPORT_POLICY_SCHEMA_VERSION", "ExportReason", "REASON_TEXT",
    "export_unit_price", "export_policy_params", "read_artisan_stock",
    "export_decision", "apply_export_decision", "summarize_export",
    "export_month_readout", "export_cumulative_readout",
]

#: 外销决策读数结构版本
EXPORT_POLICY_SCHEMA_VERSION = 1

#: 本月外销结算读数在 `state.statistics` 中的键（**流量读数**，非存量账本）
STAT_MONTH_KEY = "export_month"
#: 累计外销收入键（沿用既有键；只在真实外销时累加）
STAT_CUMULATIVE_KEY = "export_income"


class ExportReason:
    """外销决策原因常量（**三态语义的唯一取值表**，勿硬编码字符串）。"""

    #: 有真实剩余 → 外销（income > 0）
    EXPORTED = "exported"
    #: 有记录·库存为 0（income = 0）
    NO_STOCK = "no_stock"
    #: 有记录·本月无产出（income = 0）
    NO_PRODUCTION = "no_production"
    #: 有记录·未超库存上限（income = 0）
    NO_SURPLUS = "no_exportable_surplus"
    #: 有记录·国内未满足需求优先，货留国内（income = 0）
    DOMESTIC_PRIORITY = "domestic_demand_priority"

    #: 未记录·库存未知（income = None）
    UNDEFINED_STOCK = "undefined_stock"
    #: 未记录·月产未知（income = None）
    UNDEFINED_PRODUCTION = "undefined_production"
    #: 未记录·外销单价未知（income = None）
    UNDEFINED_PRICE = "undefined_price"
    #: 未记录·策略参数（EXPORT_STOCK_MONTHS / EXPORT_RATE）不可读（income = None）
    UNDEFINED_PARAMS = "undefined_policy_params"

    ALL = (
        EXPORTED, NO_STOCK, NO_PRODUCTION, NO_SURPLUS, DOMESTIC_PRIORITY,
        UNDEFINED_STOCK, UNDEFINED_PRODUCTION, UNDEFINED_PRICE, UNDEFINED_PARAMS,
    )

    #: 三态分组：哪些原因算"未定义"（income 必须是 None）
    UNDEFINED = (UNDEFINED_STOCK, UNDEFINED_PRODUCTION, UNDEFINED_PRICE, UNDEFINED_PARAMS)
    #: 三态分组：哪些原因是"有记录的 0"
    RECORDED_ZERO = (NO_STOCK, NO_PRODUCTION, NO_SURPLUS, DOMESTIC_PRIORITY)


#: 原因 → 中文可解释文本（结算日志/面板直接引用，避免各处自编文案）
REASON_TEXT: Dict[str, str] = {
    ExportReason.EXPORTED: "有真实剩余库存，已外销变现（货出宋境、钱入，来源已登记）",
    ExportReason.NO_STOCK: "工匠库存为 0：无可出口余货（本月外销 0，有记录）",
    ExportReason.NO_PRODUCTION: "本月无产出：外销上限为 0，无可出口余货（本月外销 0，有记录）",
    ExportReason.NO_SURPLUS: "库存未超合理库存上限：无可出口余货（本月外销 0，有记录）",
    ExportReason.DOMESTIC_PRIORITY: "国内有效需求优先：已为未满足的国内需求预留，无可出口余货"
                                   "（本月外销 0，有记录）",
    ExportReason.UNDEFINED_STOCK: "库存未记录：外销收入未定义（不等于 0）",
    ExportReason.UNDEFINED_PRODUCTION: "月产未记录：外销收入未定义（不等于 0）",
    ExportReason.UNDEFINED_PRICE: "外销单价未记录：外销收入未定义（不等于 0）",
    ExportReason.UNDEFINED_PARAMS: "外销策略参数不可读：外销收入未定义（不等于 0）",
}


# --------------------------------------------------------------------------
# 数值工具：非有限值过滤 + 截断取整（口径与 core/market._num/_int 对齐）
# --------------------------------------------------------------------------
def _is_number(v: Any) -> bool:
    """`v` 是否是**有限实数**（`None` / `bool` / NaN / Inf / 非数值 一律 False）。"""
    if v is None or isinstance(v, bool):
        return False
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    return float(v) if _is_number(v) else default


def _trunc(v: Any) -> int:
    """`int()` 截断（**不是** round）——与既有 §3.5 实现的取整方式一致。"""
    return int(float(v))


def _blank_decision(dim: Any, pref: Optional[str]) -> Dict[str, Any]:
    route_key = None
    if isinstance(pref, str) and pref and isinstance(dim, str) and dim:
        try:
            from core.market_price import pref_good_key
            route_key = pref_good_key(pref, dim)
        except Exception:                                   # noqa: BLE001 — 读数不阻断
            route_key = f"{pref}|{dim}"
    return {
        "schema_version": EXPORT_POLICY_SCHEMA_VERSION,
        "ok": False, "defined": False, "export": False,
        "dim": dim if isinstance(dim, str) else None,
        "pref": pref, "route_key": route_key,
        "qty": 0, "income": None, "price": None,
        "reason": None, "reason_text": None, "detail": None,
        "inputs": {}, "ledger": {}, "flow_registration": None,
        "statistics_patch": {}, "warnings": [],
    }


# --------------------------------------------------------------------------
# 单点参数与价格读数（口径源仍在 content/data，本模块不复制常量）
# --------------------------------------------------------------------------
def export_policy_params() -> Dict[str, Optional[float]]:
    """读外销策略参数（**唯一口径源** = `content.data`）。

    返回 `{"stock_months":…, "export_rate":…}`；不可读时对应项为 `None`
    （→ 调用方得"未定义"，**不回落默认值**，避免凭默认值伪造结论）。
    """
    out: Dict[str, Optional[float]] = {"stock_months": None, "export_rate": None}
    try:
        import content.data as _cd
    except Exception:                                       # noqa: BLE001
        return out
    out["stock_months"] = _num(getattr(_cd, "EXPORT_STOCK_MONTHS", None))
    out["export_rate"] = _num(getattr(_cd, "EXPORT_RATE", None))
    return out


def export_unit_price(dim: str) -> Optional[float]:
    """外销单价（口径源 = `content.data.GOODS_PRICE`，标注即"外销单价"）。

    缺失维度返回 `None`（→ 决策判 `undefined_price`），**不回落 0**。
    """
    try:
        import content.data as _cd
    except Exception:                                       # noqa: BLE001
        return None
    return _num((getattr(_cd, "GOODS_PRICE", None) or {}).get(dim))


def read_artisan_stock(state, pref: str, dim: str) -> Optional[int]:
    """读某路工匠 `goods` 池中某商品的**真实存量**（**纯读，不写**）。

    任一环节缺失（无 state / 无该路 / 无工匠 / 无 goods 槽 / 该维度无键）
    → `None`（未记录），**不回落 0**（"没这条记录"≠"确实一件都没有"）。
    """
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict) or not isinstance(pref, str):
        return None
    p = prefs.get(pref)
    if not isinstance(p, dict):
        return None
    pops = p.get("pops")
    artisan = pops.get("工匠") if isinstance(pops, dict) else None
    if not isinstance(artisan, dict):
        return None
    goods = artisan.get("goods")
    if not isinstance(goods, dict):
        return None
    if dim not in goods:
        return None
    q = goods.get(dim)
    return _trunc(q) if _is_number(q) else None


# --------------------------------------------------------------------------
# 决策（纯函数：不读 state、不写任何东西）
# --------------------------------------------------------------------------
def export_decision(
    *,
    dim: str,
    stock: Any,
    month_prod: Any,
    price: Any = None,
    domestic_sold_qty: Any = 0,
    stock_before_domestic: Any = None,
    domestic_commitment_qty: Any = None,
    pref: Optional[str] = None,
    stock_months: Any = None,
    export_rate: Any = None,
) -> Dict[str, Any]:
    """判定"真实可外销余量"，返回**是否外销、数量、钱、来源登记与可解释原因**。

    参数
    ----
    `dim`：商品维（布/绸…），非空字符串。
    `stock`：**内销真成交之后**工匠池里的真实存量（B1 起 `trade_goods` 已扣卖方）。
        这是"同一批货不既内销又外销"的**结构性保证**入口：已内销的货不在 `stock` 里。
    `month_prod`：本月产出（调用方给真实值或既有重估值皆可）；`None` → 未定义。
    `price`：外销单价；`None` → 未定义（调用方可用 `export_unit_price(dim)`）。
    `domestic_sold_qty`：本月本路本商品**内销成交量**（仅台账核对，不参与扣减）。
    `stock_before_domestic`：可选，月初/内销前存量；给出时与 `domestic_sold_qty` 交叉校验。
    `domestic_commitment_qty`：可选，本路本商品**未满足的国内需求**（承诺需求预留）。
        `None` → 按 0 计算，但 `warnings` 明确标注"承诺需求未记录"（缺失≠0）。
    `pref` / `stock_months` / `export_rate`：路名（**不叫 route**，见命名纪律）与策略参数
        （缺省从 `content.data` 读）。

    返回
    ----
    `{ok, defined, export, qty, income, price, reason, reason_text, detail,
      inputs, ledger, flow_registration, statistics_patch, warnings}`

    三态：`income is None` ⇔ `defined is False`（未记录/未定义）；
    `income == 0` ⇔ `defined is True` 且确无余货；`income > 0` ⇔ 真实外销。
    `ok=False` 表示**非法输入被拒**，此时不改任何账、不产出统计建议。
    """
    d = _blank_decision(dim, pref)

    # ---- 0) 维度校验
    if not isinstance(dim, str) or not dim.strip():
        d["detail"] = f"dim 非法：{dim!r}（须为非空商品维字符串）"
        return d

    # ---- 1) 数值校验：拒绝式（不"善意修正"，不回落 0）
    def _reject(name: str, v: Any) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        if not _is_number(v):
            d["detail"] = f"{name} 非法：{v!r}（须为有限实数；None 表示未记录）"
            return d
        if float(v) < 0:
            d["detail"] = f"{name} 非法：{v!r}（不得为负）"
            return d
        return None

    for _name, _v in (("stock", stock), ("month_prod", month_prod),
                      ("domestic_sold_qty", domestic_sold_qty),
                      ("stock_before_domestic", stock_before_domestic),
                      ("domestic_commitment_qty", domestic_commitment_qty),
                      ("stock_months", stock_months), ("export_rate", export_rate)):
        if _reject(_name, _v) is not None:
            return d
    if _is_number(price) and float(price) <= 0:
        d["detail"] = f"price 非法：{price!r}（外销单价须 > 0，与 trade_goods 同口径）"
        return d

    # ---- 2) 双卖交叉校验：内销量不可能超过内销前存量
    if (_is_number(stock_before_domestic) and _is_number(domestic_sold_qty)
            and _trunc(domestic_sold_qty) > _trunc(stock_before_domestic)):
        d["detail"] = (f"内销量 {_trunc(domestic_sold_qty)} 超过内销前存量 "
                       f"{_trunc(stock_before_domestic)}：同一批货不可能既内销又外销")
        return d

    # ---- 3) 策略参数（缺省自 content.data 读；不可读 → 未定义，不回落默认值）
    _params = export_policy_params()
    _months = _num(stock_months, _params["stock_months"])
    _rate = _num(export_rate, _params["export_rate"])

    d["inputs"] = {
        "stock": stock, "month_prod": month_prod, "price": price,
        "domestic_sold_qty": domestic_sold_qty,
        "stock_before_domestic": stock_before_domestic,
        "domestic_commitment_qty": domestic_commitment_qty,
        "stock_months": _months, "export_rate": _rate,
    }

    # ---- 4) 未定义分支：income = None（**不是 0**）
    undefined_seq = (
        (stock is None, ExportReason.UNDEFINED_STOCK),
        (month_prod is None, ExportReason.UNDEFINED_PRODUCTION),
        (_months is None or _rate is None, ExportReason.UNDEFINED_PARAMS),
        (price is None, ExportReason.UNDEFINED_PRICE),
    )
    for hit, reason in undefined_seq:
        if hit:
            # 注意：未定义**不是**非法输入 —— 决策本身合法，只是结论不可判定，
            # 故 ok=True（`ok=False` 专留给被拒绝的非法输入，含义不可混用）。
            d["ok"] = True
            d["defined"] = False
            d["reason"] = reason
            d["reason_text"] = REASON_TEXT[reason]
            d["detail"] = "关键输入未记录：外销收入未定义（income=None，不回落 0）"
            d["ledger"] = {"no_double_sale": True,
                           "stock_after_domestic": _trunc(stock) if _is_number(stock) else None,
                           "exported_qty": 0}
            return d

    # ---- 5) 已定义分支：国内优先 → 合理库存 → 月度外销上限
    _stock = _trunc(stock)
    _mp = _trunc(month_prod)
    _px = float(price)
    _sold = _trunc(domestic_sold_qty or 0)

    _commit_known = _is_number(domestic_commitment_qty)
    _commit = _trunc(domestic_commitment_qty) if _commit_known else 0
    _reserved = max(0, min(_commit, _stock))       # 预留不得吃掉不存在的货
    if _commit > _stock:
        d["warnings"].append(
            f"承诺需求 {_commit} 超过现存库存 {_stock}：预留已按 {_stock} 截断")
    _free = max(0, _stock - _reserved)
    _cap = _trunc(_mp * _months)
    _surplus = max(0, _free - _cap)
    _rate_cap = _trunc(_mp * _rate)
    # 末位 `min(..., _stock)`：结构性防重复出售（外销量永不超过内销后的真实存量）
    _qty = max(0, min(_surplus, _rate_cap, _stock))

    if _qty > 0:
        _reason = ExportReason.EXPORTED
    elif _stock <= 0:
        _reason = ExportReason.NO_STOCK
    elif _mp <= 0:
        _reason = ExportReason.NO_PRODUCTION
    elif _reserved > 0 and _surplus <= 0:
        _reason = ExportReason.DOMESTIC_PRIORITY
    else:
        _reason = ExportReason.NO_SURPLUS

    _income = _trunc(_qty * _px) if _qty > 0 else 0

    d.update(
        ok=True, defined=True, export=_qty > 0,
        qty=_qty, income=_income, price=_px,
        reason=_reason, reason_text=REASON_TEXT[_reason],
        detail=None,
        ledger={
            # 数量台账（可核对"外销 ⊆ 内销后真实库存"）
            "stock_after_domestic": _stock,
            "domestic_sold_qty": _sold,
            "reserved_for_domestic": _reserved,
            "free_after_reserve": _free,
            "stock_cap": _cap,
            "surplus_over_cap": _surplus,
            "rate_cap": _rate_cap,
            "exported_qty": _qty,
            "stock_left_after_export": _stock - _qty,
            "no_double_sale": bool(_qty <= _stock),
            "money_in": _income,
            "goods_out": _qty,
        },
        flow_registration=({"kind": "external", "amount": _income,
                            "reason": f"外销变现·{dim}"} if _qty > 0 else None),
        statistics_patch={
            STAT_MONTH_KEY: {
                "income": _income, "defined": True, "qty": _qty,
                "by_dim": {d["route_key"] or dim: _qty},
                "reasons": [_reason],
            },
            "export_decisions": {_reason: 1},
            **({STAT_CUMULATIVE_KEY: _income} if _income > 0 else {}),
        },
    )
    if _qty > 0 and float(price) != _trunc(_px):
        d["warnings"].append(
            "外销单价为非整数：按四舍五入计收入，尾差归外销方（不销毁钱）")
    if not _commit_known:
        d["warnings"].append(
            "承诺需求（未满足国内需求）未按 (路, 商品) 记录，按 0 处理；"
            "**未记录 ≠ 没有未满足需求**（缺失≠0）")
    return d


# --------------------------------------------------------------------------
# 执行（唯一写入口；钱货只落 POP 持仓 + 货币流水台账）
# --------------------------------------------------------------------------
def _stats_dict(state) -> Optional[dict]:
    s = getattr(state, "statistics", None)
    return s if isinstance(s, dict) else None


def _merge_month(stats: dict, patch: dict, turn: Any) -> None:
    """把本月读数**并入** `statistics["export_month"]`（同月多路/多商品累加）。"""
    prev = stats.get(STAT_MONTH_KEY)
    rec = {"turn": turn, "income": 0, "qty": 0, "defined": True,
           "undefined_count": 0, "by_dim": {}, "reasons": []}
    if isinstance(prev, dict) and prev.get("turn") == turn:
        rec["income"] = _num(prev.get("income"), 0.0) or 0.0
        rec["qty"] = _trunc(prev.get("qty") or 0)
        rec["defined"] = bool(prev.get("defined"))
        rec["undefined_count"] = _trunc(prev.get("undefined_count") or 0)
        bd = prev.get("by_dim")
        if isinstance(bd, dict):
            rec["by_dim"].update({k: _trunc(v or 0) for k, v in bd.items()})
        rs = prev.get("reasons")
        if isinstance(rs, list):
            rec["reasons"] = [str(x) for x in rs]
    if not patch.get("defined"):
        rec["undefined_count"] += 1
        rec["defined"] = False
        rec["income"] = None          # 有未定义判定 ⇒ 本月收入不可判定（不回落 0）
    else:
        rec["income"] = float(rec["income"] or 0.0) + float(patch.get("income") or 0)
        rec["qty"] += _trunc(patch.get("qty") or 0)
        for k, v in (patch.get("by_dim") or {}).items():
            rec["by_dim"][k] = _trunc(rec["by_dim"].get(k, 0)) + _trunc(v)
    # reasons 合并：**两个分支都要做**。
    # 审查修复：原先只在 `else`（已定义）分支合并，导致未定义判定
    # （如 `UNDEFINED_PRICE`）的 reason 被吞——读数说"不可判定"却不给出**原因**。
    for r in (patch.get("reasons") or []):
        if r not in rec["reasons"]:
            rec["reasons"].append(r)
    # 归一：只要本月出现过未定义判定 ⇒ 收入**不可判定**（income 必须是 None）。
    # 否则会出现"income=0 却 defined=False"这种自相矛盾的读数（部分求和伪装确定值）。
    if rec["undefined_count"] > 0:
        rec["defined"] = False
        rec["income"] = None
    stats[STAT_MONTH_KEY] = rec


def apply_export_decision(
    state,
    decision: Dict[str, Any],
    *,
    seller: Optional[dict] = None,
    register_flow: bool = True,
    log: Optional[list] = None,
    record_month: bool = True,
    record_cumulative: bool = True,
) -> Dict[str, Any]:
    """执行一个 `export_decision`（**唯一写入口**）：钱货双向转移 + 来源登记 + 读数登记。

    - 决策非法（`ok=False`）／未定义（`defined=False`）⇒ **不改任何账**；
    - 决策为零外销 ⇒ 只登记"确无余货"的原因与本月读数（`income=0`，**有记录**）；
    - 写前复核：此刻池中不足计划外销量 ⇒ **整笔不发生**（不留单边账）。

    返回 `{applied, dim, qty, income, reason, detail, registered, month_recorded}`。
    """
    out: Dict[str, Any] = {"applied": False, "dim": None, "qty": 0, "income": 0,
                           "reason": (decision or {}).get("reason") if isinstance(decision, dict) else None,
                           "detail": None, "registered": None, "month_recorded": False}
    if not isinstance(decision, dict) or not decision.get("ok"):
        out["detail"] = "决策非法或未通过校验：未发生任何转移"
        return out
    dim = decision.get("dim")
    out["dim"] = dim

    stats = _stats_dict(state)

    # ---- 未定义：登记"未定义"这一事实，但**绝不把 income 写成 0**
    if not decision.get("defined"):
        out["detail"] = (f"{decision.get('reason_text') or '决策未定义'}："
                         "不外销，income 保持 None（不回落 0）")
        if stats is not None:
            _merge_month(stats, {"income": None, "defined": False, "qty": 0,
                                 "by_dim": {}, "reasons": [decision.get("reason")]},
                         getattr(state, "turn", None))
            _bump_reason(stats, decision.get("reason"))
            out["month_recorded"] = True
        if isinstance(log, list):
            log.append(f"[外销] {out['detail']}")
        return out

    # ---- 零外销：有记录地写 0（这是规格要求的"确无余货"，不是"未记录"）
    if not decision.get("export"):
        out["detail"] = decision.get("reason_text") or "无可出口余货"
        if stats is not None:
            if record_month:
                _merge_month(stats, decision.get("statistics_patch", {}).get(STAT_MONTH_KEY, {}),
                             getattr(state, "turn", None))
                out["month_recorded"] = True
            _bump_reason(stats, decision.get("reason"))
        if isinstance(log, list):
            log.append(f"[外销] {out['detail']}")
        return out

    qty = _trunc(decision.get("qty") or 0)
    income = _trunc(decision.get("income") or 0)
    out.update(qty=qty, income=income)

    # ---- 货的一腿：写前复核，不足则整笔不发生
    if not isinstance(seller, dict):
        out["detail"] = "seller 非 POP 字典：外销未发生（不新建账本）"
        return out
    goods = seller.get("goods")
    if not isinstance(goods, dict) or dim not in goods:
        out["detail"] = f"工匠池无 `{dim}` 槽位：外销未发生（缺失≠0）"
        return out
    have = _trunc(goods.get(dim) or 0)
    if have < qty:
        out["detail"] = (f"写前复核失败：工匠池现存 {have} < 计划外销 {qty}，"
                         "整笔不发生（货未动、钱未动）")
        return out

    # ---- 钱的一腿：POP wealth（POP 挂载点）＋ 来源登记
    # 🟢 M45 家族第 5 处（2026-10-13）：`seller` 是**路级镜像行**（调用方从 `p["pops"]` 取），
    #   直写 `goods[...]` / `seller["wealth"]` 会被 `sync_route_pops` 覆盖。
    #   M47 让各路的货留在本路后，本路径才真的跑起来 ⇒ 潜伏缺陷暴露（守卫 trace 直指此文件）。
    #   未下沉/找不到 ⇒ None ⇒ **回落原写法**（行为不变）。
    from core.foundation.ledger import pop_bridge as _pb
    _sub = _pb.pop_goods_sub(state, seller, dim, qty)
    if _sub is None:
        goods[dim] = have - qty
        _sub = qty
    if _pb.pop_obj_add(state, seller, "wealth", income) is None:
        seller["wealth"] = max(0, _trunc(seller.get("wealth") or 0)) + income
    if _sub:
        from core.domains.economy import stock_flow as _sf
        _sf.record_out(state, dim, _sub, reason="export_sell", custody=_sf.CUSTODY_POP)
    out["applied"] = True

    if register_flow:
        from core.settlement_common import register_money_flow
        out["registered"] = bool(register_money_flow(
            state, "external", income, f"外销变现·{dim}"))

    if stats is not None:
        if record_month:
            _merge_month(stats, decision.get("statistics_patch", {}).get(STAT_MONTH_KEY, {}),
                         getattr(state, "turn", None))
            out["month_recorded"] = True
        _bump_reason(stats, decision.get("reason"))
        if record_cumulative and income > 0:
            prev = stats.get(STAT_CUMULATIVE_KEY)
            base = 0.0 if prev is None else (_num(prev, 0.0) or 0.0)
            stats[STAT_CUMULATIVE_KEY] = base + float(income)
        qd = stats.setdefault("export_qty", {})
        key = decision.get("route_key") or str(dim)
        qd[key] = _trunc(qd.get(key, 0)) + qty

    if isinstance(log, list):
        log.append(f"[外销] {dim} 外销 {qty} 单位·{income} 贯"
                   f"（{'/'.join(str(r) for r in (decision.get('statistics_patch', {}).get(STAT_MONTH_KEY, {}) or {}).get('reasons', []))}）")
    return out


def _bump_reason(stats: dict, reason: Any) -> None:
    if not reason:
        return
    bucket = stats.setdefault("export_decisions", {})
    if isinstance(bucket, dict):
        bucket[str(reason)] = _trunc(bucket.get(str(reason), 0)) + 1


# --------------------------------------------------------------------------
# 读数（纯派生、只读）
# --------------------------------------------------------------------------
def summarize_export(decisions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总一批决策（**纯派生，不写 state**）。

    `income`＝已定义决策之和；**只要有一个未定义决策**即返回 `None` 并给出
    `undefined_count`（不可判定的月份不许被"部分求和"伪装成确定值）。
    """
    total = 0.0
    qty = 0
    undefined = 0
    invalid = 0
    by_reason: Dict[str, int] = {}
    n = 0
    for d in (decisions or []):
        if not isinstance(d, dict):
            continue
        n += 1
        r = str(d.get("reason"))
        by_reason[r] = by_reason.get(r, 0) + 1
        if not d.get("ok"):
            invalid += 1
            continue
        if not d.get("defined"):
            undefined += 1
            continue
        total += float(d.get("income") or 0)
        qty += _trunc(d.get("qty") or 0)
    income: Optional[float] = None if (undefined or invalid) else total
    return {
        "schema_version": EXPORT_POLICY_SCHEMA_VERSION,
        "decisions": n,
        "income": income,
        "qty": qty,
        "defined": not (undefined or invalid),
        "undefined_count": undefined,
        "invalid_count": invalid,
        "by_reason": by_reason,
        "note": ("存在未定义/被拒决策，本期外销收入不可判定（None ≠ 0）"
                 if (undefined or invalid) else "全部决策已定义"),
    }


def _tri_state(raw: Any, scope: str, missing_note: str) -> Dict[str, Any]:
    val = _num(raw)
    if raw is None or val is None:
        return {"schema_version": EXPORT_POLICY_SCHEMA_VERSION, "scope": scope,
                "income": None, "defined": False, "state": "unrecorded",
                "note": missing_note}
    if val == 0:
        return {"schema_version": EXPORT_POLICY_SCHEMA_VERSION, "scope": scope,
                "income": 0, "defined": True, "state": "recorded_zero",
                "note": "有记录：确无外销收入（0）"}
    return {"schema_version": EXPORT_POLICY_SCHEMA_VERSION, "scope": scope,
            "income": val, "defined": True, "state": "recorded_income",
            "note": "有记录：存在真实外销收入（钱货守恒，来源已登记为体外注入）"}


def export_month_readout(state) -> Dict[str, Any]:
    """**本月**外销三态读数（只读）：`recorded_income` / `recorded_zero` / `unrecorded`。

    本月 `income` 出现 `None` 只可能来自"存在未定义判定"，此时 `undefined_count > 0`。
    """
    rec = (getattr(state, "statistics", None) or {}).get(STAT_MONTH_KEY)
    if not isinstance(rec, dict):
        return _tri_state(None, "month",
                          f"statistics 无 `{STAT_MONTH_KEY}` 键：本月外销判定未登记"
                          "（未记录 ≠ 确无外销）")
    out = _tri_state(rec.get("income"), "month",
                     f"`{STAT_MONTH_KEY}.income` 未记录且存在未定义判定：不可判定")
    if not rec.get("defined"):
        out["defined"] = False
        out["state"] = "undefined"
    out.update(turn=rec.get("turn"), qty=_trunc(rec.get("qty") or 0),
               undefined_count=_trunc(rec.get("undefined_count") or 0),
               by_dim=rec.get("by_dim") if isinstance(rec.get("by_dim"), dict) else {},
               reasons=[str(r) for r in (rec.get("reasons") or [])])
    return out


def export_cumulative_readout(state) -> Dict[str, Any]:
    """**累计**外销收入三态读数（只读；`statistics` 整局不清零，故为累计口径）。

    累计键只在**真实外销**时累加 ⇒ 累计 `0` 等价于"整局从未外销"，
    **不能**用来表达"本月无外销"（那是 `export_month_readout` 的职责）。
    """
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict) or STAT_CUMULATIVE_KEY not in stats:
        return _tri_state(None, "cumulative",
                          f"statistics 无 `{STAT_CUMULATIVE_KEY}` 键：整局外销收入未记录"
                          "（未记录 ≠ 零外销；请看 export_month_readout 判断本月是否判定过）")
    out = _tri_state(stats.get(STAT_CUMULATIVE_KEY), "cumulative", "累计外销收入不可读")
    if out["income"] == 0:
        out["note"] = "有记录：整局累计为 0 ＝ 从未发生过外销"
    return out
