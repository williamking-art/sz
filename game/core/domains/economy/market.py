# -*- coding: utf-8 -*-
"""B1 · 商品成交与库存归属（**口径单点**，对应规格 `market-civilian-economy` B1）

## 为什么有这个模块

B0 台账（`specs/market-civilian-economy/b0-inventory-ledger.md`）实测确认：
宋境 POP 消费走 `settlement_granary.py:280-285`——**扣钱后凭空给货**，
而外邦 `_ext_econ_phases` 才有真扣货。本模块提供**唯一的成交入口**，
把"钱货双向转移、成交量受真实可售量约束"固化为单点口径。

## 口径（B1-1/2/4/6）

1. **双向原子**：一次成交同时完成
   `买方 wealth −paid` ＋ `卖方 wealth +paid` ＋ `卖方 goods −q` ＋ `买方 goods +q`；
   **任一腿无法完成则整笔不成交**（不半成交、不留单边账）。
2. **可售量约束**：`成交量 ≤ min(请求量, 买方可支付, 卖方可售且非预留)`；
   **无货不能买**——短缺以未满足返回，**绝不虚拟供给**。
3. **未饱和需求归因**（B0-3 四分解）：区分
   `no_demand`（零需求）／`insufficient_purchasing_power`（没钱）／
   `no_stock_local`（无货）／`not_arrived`（未运到）。
   **涨价造成的买不起归入购买力不足**，不另计一类。
4. **防重**（B1-4）：同一 `trade_id` 在同一回合内**幂等**——重复调用返回首次结果，
   不二次转移（防回合重试造成重复成交）。
5. **尾差有主**（B1-6）：`int()` 截断产生的余数**记入 `tail_delta`**，
   对手方明确，**禁止无来源销毁/生成**。

## 库存归属（B1-3）

本模块**不合并**载体，而是要求调用方指明**用途**：
- `consume`：民间自用（POP 手持 goods）；
- `resale`：待售成品（工匠/商人 goods 池）；
- `storage`：仓储（`state.resources`）；**官仓不自动算民间可售**。

在途（`transit`）当前**未实现**，入参保留但会在无在途数据时报"未运到"。
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

__all__ = [
    "TRADE_SCHEMA_VERSION", "TRADE_PURPOSES",
    "sellable_stock", "trade_goods", "TradeOutcome",
]

#: 成交记录结构版本
TRADE_SCHEMA_VERSION = 1

#: 允许的库存用途（调用方必须声明，避免"哪批货能卖"靠猜）
TRADE_PURPOSES = ("consume", "resale", "storage")

#: 同一回合已成交记录：`{(turn, trade_id): outcome}`（防重复成交）
_TRADE_LEDGER: Dict[Tuple[Any, str], Dict[str, Any]] = {}


def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


def _int(v: Any, default: int = 0) -> int:
    f = _num(v, None)
    return default if f is None else int(round(f))


def sellable_stock(*, seller: Optional[dict], dim: str,
                   reserved: int = 0) -> int:
    """卖方**真实可售**库存：持仓 − 预留/自用/官用量。

    - `seller` 为 `None`（卖方不存在）→ **0**（不是"未知"，是确实没有库存）；
    - `reserved` 为已预留量（工程预留、官用等），从可售中扣除，**不复制库存**。
    """
    if not isinstance(seller, dict):
        return 0
    goods = seller.get("goods")
    if not isinstance(goods, dict):
        return 0
    qty = _int(goods.get(dim), 0)
    return max(0, qty - max(0, _int(reserved, 0)))


def _ledger_key(state, trade_id: str) -> Tuple[Any, str]:
    return (getattr(state, "turn", None), str(trade_id))


def _trade_goods_core(state, *, dim: str, qty: int, price: float,
                buyer: dict, seller: dict,
                purpose: str = "resale",
                buyer_goods_key: str = "goods",
                trade_id: Optional[str] = None,
                reserved: int = 0,
                ) -> Dict[str, Any]:
    """**唯一的商品成交入口**（B1-1/2/4/6）。

    参数
    ----
    `qty`：期望购买量；`price`：**单件**价格（贯）。
    `buyer` / `seller`：POP 字典（含 `wealth` 与 `goods`）。
    `purpose`：卖方该批货的用途，须在 `TRADE_PURPOSES` 内。
    `trade_id`：稳定交易 ID；给出时本回合**幂等**（重复调用返回首次结果）。

    返回
    ----
    `{ok, traded, paid, unmet_qty, reason, tail_delta, price}`
    其中 `reason` ∈ `ok` / `no_stock_local` / `insufficient_purchasing_power` /
    `no_demand` / `duplicate_trade` / `invalid`。

    **未满足量单独返回**，调用方据此归因（不静默丢弃）。
    """
    out = {"schema_version": TRADE_SCHEMA_VERSION, "dim": dim,
           "traded": 0, "paid": 0, "unmet_qty": 0, "reason": "ok",
           "tail_delta": 0, "price": _num(price, 0.0)}

    # ---- 前置校验（拒绝式，不做"善意修正"）
    if purpose not in TRADE_PURPOSES:
        out.update(ok=False, reason="invalid")
        out["detail"] = f"purpose 非法：{purpose!r}（允许：{TRADE_PURPOSES}）"
        return out
    if not isinstance(buyer, dict) or not isinstance(seller, dict):
        out.update(ok=False, reason="invalid")
        out["detail"] = "buyer/seller 必须是 POP 字典"
        return out
    if buyer is seller:
        out.update(ok=False, reason="invalid")
        out["detail"] = "buyer 与 seller 不能是同一持有者（自购不构成市场）"
        return out

    want = max(0, _int(qty, 0))
    unit_price = _num(price, None)
    if unit_price is None or unit_price <= 0:
        out.update(ok=False, reason="invalid")
        out["detail"] = f"price 非法：{price!r}（须 > 0）"
        return out

    # ---- 幂等：同一回合同一 trade_id 不重复成交（防回合重试）
    if trade_id:
        key = _ledger_key(state, trade_id)
        prev = _TRADE_LEDGER.get(key)
        if prev is not None:
            out.update(ok=False, reason="duplicate_trade", traded=prev["traded"],
                       paid=prev["paid"], unmet_qty=prev["unmet_qty"],
                       detail="该 trade_id 本回合已成交过，本次不重复转移")
            return out

    # ---- 零需求：期望量为 0 不是"未满足"（B0-3 口径）
    if want <= 0:
        out.update(ok=True, reason="no_demand", unmet_qty=0)
        return out

    # ---- 三重上限：可售量 / 购买力 / 需求量
    available = sellable_stock(seller=seller, dim=dim, reserved=reserved)
    buyer_wealth = max(0, _int(buyer.get("wealth"), 0))
    affordable = int(buyer_wealth // unit_price) if unit_price > 0 else 0

    trade_qty = min(want, available, affordable)
    if trade_qty <= 0:
        reason = ("no_stock_local" if available <= 0
                  else "insufficient_purchasing_power")
        out.update(ok=True, reason=reason, unmet_qty=want)
        if trade_id:
            _TRADE_LEDGER[_ledger_key(state, trade_id)] = dict(out)
        return out

    # ---- 双向原子转移（先算清，后写；写前再核一次卖方，防中途被改）
    paid = int(trade_qty * unit_price)
    seller_goods = seller.setdefault("goods", {})
    if _int(seller_goods.get(dim), 0) < trade_qty:      # 写前复核（并发/重入保护）
        out.update(ok=True, reason="no_stock_local", unmet_qty=want)
        if trade_id:
            _TRADE_LEDGER[_ledger_key(state, trade_id)] = dict(out)
        return out

    buyer.setdefault(buyer_goods_key, {})
    # 🟢 M45：财富与商品写入**必须走桥**（落治所真账 + 刷镜像）。
    #   原实现直写 buyer["wealth"]/seller["wealth"] 与双方 goods，而调用方传的是**路级镜像行**
    #   （`for … in p["pops"].items()`）⇒ 写入会被 `sync_route_pops` 覆盖
    #   （2026-10-13 守卫 trace 直指 market.py:180/:183）。
    #   `locate_pops` 认镜像行对象 ⇒ 桥可直接用；**未下沉 ⇒ None ⇒ 回落原写法**（行为不变）。
    from core.foundation.ledger import pop_bridge as _pb
    if _pb.pop_obj_add(state, buyer, "wealth", -paid) is None:
        buyer["wealth"] = buyer_wealth - paid
    if buyer_goods_key == "goods":
        # 桥只认标准 goods 槽；自定义槽名（少见）保持原写法
        # 2026-10-18 全审：原先把 (state, buyer, dim, qty) 传给 pdata 版 pop_goods_add
        # （签名不符 ⇒ 恒 None ⇒ 回落直写路级镜像，成交在月末对账时被抹掉）。
        # 改用按 POP 对象定位的 pop_obj_goods_add，真实落治所真账。
        if _pb.pop_obj_goods_add(state, buyer, dim, trade_qty) is None:
            buyer[buyer_goods_key][dim] = _int(buyer[buyer_goods_key].get(dim), 0) + trade_qty
    else:
        buyer[buyer_goods_key][dim] = _int(buyer[buyer_goods_key].get(dim), 0) + trade_qty
    # 卖方出货：从其**治所真账**按现有持仓占比扣、逐个夹紧 ≥0（无持仓治所不参与）
    if _pb.pop_obj_goods_sub(state, seller, dim, trade_qty) is None:
        seller_goods[dim] = _int(seller_goods.get(dim), 0) - trade_qty
    if _pb.pop_obj_add(state, seller, "wealth", paid) is None:
        seller["wealth"] = max(0, _int(seller.get("wealth"), 0)) + paid

    unmet = want - trade_qty
    out.update(ok=True, traded=trade_qty, paid=paid, unmet_qty=unmet,
               reason="ok" if unmet <= 0 else (
                   "no_stock_local" if available < want else
                   "insufficient_purchasing_power"))
    if trade_id:
        _TRADE_LEDGER[_ledger_key(state, trade_id)] = dict(out)
    return out


def reset_trade_ledger() -> None:
    """清空防重台账（仅测试与"新局"用；正常流程按 turn 自然隔离）。"""
    _TRADE_LEDGER.clear()


class TradeOutcome:
    """结果字段名常量（供调用方/面板引用，避免各处硬编码字符串）。"""

    OK = "ok"
    NO_DEMAND = "no_demand"
    NO_STOCK = "no_stock_local"
    NO_MONEY = "insufficient_purchasing_power"
    DUPLICATE = "duplicate_trade"
    INVALID = "invalid"

    ALL = (OK, NO_DEMAND, NO_STOCK, NO_MONEY, DUPLICATE, INVALID)


def trade_goods(state, *, dim: str, qty: int, price: float,
                buyer: dict, seller: dict,
                purpose: str = "resale",
                buyer_goods_key: str = "goods",
                trade_id: Optional[str] = None,
                reserved: int = 0,
                ) -> Dict[str, Any]:
    """**唯一的商品成交入口**（对外签名/语义**完全不变**；实现见 `_trade_goods_core`）。

    本层只做**一处加法**：给返回字典挂 `gap` ＝ **结构化缺失原因**（P1 · M41a 契约，
    见 `core.domains.economy.market_gap`）：成交 / 零需求 ⇒ `None`；未满足 ⇒
    `{code, group, need, have, source_id, note}`，`group` ∈ 钱/货/岗位/料/运力。
    既有字段（`ok/traded/paid/unmet_qty/reason/...`）**逐字不变**。

    ⚠️ **可选层**：挂 `gap` 失败**不得影响成交结果**（吞异常并留痕）。
    """
    out = _trade_goods_core(state, dim=dim, qty=qty, price=price, buyer=buyer,
                            seller=seller, purpose=purpose,
                            buyer_goods_key=buyer_goods_key,
                            trade_id=trade_id, reserved=reserved)
    try:
        from core.domains.economy import market_gap
        out["gap"] = market_gap.from_trade_outcome(out, need=qty)
    except Exception:  # noqa: BLE001 — 契约层失败不得影响成交
        import logging as _logging
        _logging.getLogger(__name__).warning("trade_goods: 挂 gap 失败（成交不受影响）",
                                             exc_info=True)
    return out