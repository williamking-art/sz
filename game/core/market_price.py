# -*- coding: utf-8 -*-
"""B2 · 商品价格发现与口径分离（规格 `market-civilian-economy` B2-4 / B2-5）

## 为什么有这个模块

B0 台账与 B1 落地过程暴露两处价格口径问题：

1. **`GOODS_PRICE` 被当作消费成交价使用**——但它在 `content/data.py:1099` 的定义是
   **"外销单价（贯/单位）"**。B1 消费端复用它做买卖价，属**口径混用**
   （外销价 ≠ 民间零售价），本模块分离之；
2. **`MATERIAL_PRICE_BASE` 是静态表、从不随供需浮动**——宋境没有商品价格发现机制，
   "价格响应供需"（《建议》§5.1、§9 阶段 2）完全缺位。

## 口径（B2-4/B2-5）

1. **四类价格分开，不得互相顶替**：
   | 价格 | 含义 | 载体 |
   |---|---|---|
   | 基准价 | 长期估值锚 | `MATERIAL_PRICE_BASE`（**只读，不得就地改写**） |
   | 成交价 | 本月实际成交均价 | `state.dynamic_prices[dim]` |
   | 官定/官购价 | 政府定价或采购价 | 调用方显式传入 |
   | 外销价 | 存量外销结算价 | `GOODS_PRICE`（维持原义**仅用于外销**） |
2. **价格按供需缓动、有上下界、单月涨跌封顶**：
   - 目标价 = 基准价 × 压力指数（`(需求−供给)/供给` 的有界函数）；
   - 复用 `core.game_state_econ.cap_monthly_price`（**纯函数**、单位为**相对变动率**）；
   - **不受冲击的地区不跳价**（压力为 0 → 目标＝基准 → 封顶后不动）。
3. **月度成交均价可回写**：`record_trade_price` 供结算侧登记，供下月计算。
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from core.foundation.common.numeric import finite_number as _num

__all__ = [
    "PRICE_SCHEMA_VERSION", "PRICE_BOUNDS", "price_pressure",
    "discover_price", "record_trade_price", "effective_buy_price",
    "pref_good_key", "seat_good_key",
    "record_seat_trade_price", "discover_seat_price",
]

#: 价格发现结构版本
PRICE_SCHEMA_VERSION = 1

#: 价格相对基准价的**上下界**（倍数）。低于 0.5× 或高于 2.0× 视为异常，
#: 由供需模型在边界处饱和，不用无限指数放大。
PRICE_BOUNDS = (0.5, 2.0)

#: 供需缺口的涨价斜率（B2-R2）：`倍数 = 1 + 缺口占比 × PRESSURE_GAIN`。
#: 1.0 ⇒ 完全缺货时恰好触及2× 上界；供需刚好满足时为 1.0（不涨不跌）。
PRESSURE_GAIN = 1.0

#: 单月相对涨跌封顶（复用既有 `PRICE_LEVEL_MONTHLY_CAP` 量级，可按需调）
DEFAULT_MONTHLY_CAP = 0.15


def _base_price(dim: str, state=None) -> Optional[float]:
    """基准价（只读）。缺失返回 `None`——**不作 0**，由调用方决定是否启用该商品。

    B4-2（2026-11 接线）：已登记但**未解锁**的新材（水泥/钢筋等架空后世材料）
    **不可定价** → 返回 `None`（不是价 0、不是"缺货"）。
    `state is None` 时（纯函数路径如 `discover_price`）无法按局判定，
    此时不做解锁检查，由 `effective_buy_price`（已接 state）负责。
    """
    from content.data import MATERIAL_PRICE_BASE
    base = _num((MATERIAL_PRICE_BASE or {}).get(dim), None)
    if state is not None:
        try:
            from core.domains.construction.material_tech import (effective_material_price,
                                            resolve_material_tech)
            if resolve_material_tech(dim) is not None:
                # **仅对已登记的新材**做解锁检查（水泥/钢筋等架空后世材料）。
                # 未登记的普通商品（布/绸/木/石…）不参与此钩子——否则会把
                # 全市场都判成"未解锁"而无法定价（`effective_material_price`
                # 对未注册材料返回 None，那是新材语义，不适用于普通商品）。
                return effective_material_price(state, dim, base)
        except Exception:                # noqa: BLE001 — 钩子不可用时用基准价，不阻断
            return base
    return base


def price_pressure(demand_qty: Optional[float], supply_qty: Optional[float]) -> Optional[float]:
    """供需压力 → 目标价格**倍数**（1.0 为基准价）。

    **口径（B2-R2 修正）**：分母是**期望需求**（`demand_qty`），**不是可售供给**。
    原因：`supply_qty` 是**月末剩余可售量**——"有货"不等于"卖光"，
    拿它当分母会让"供给充足"被误判成"供给过剩"而系统性压价。
    正确读法：**卖得越多（成交/需求占比越高），价格越向基准上方漂**。

    - `fill = min(1, supply/demand)`：供给能满足期望需求的比例（0~1）；
    - 供给为 0 且有需求 → `None`（**无货不可定价**，由 `trade_goods` 的
      `no_stock_local` 表达"没买到"，不是"价格无限高"）；
    - 两者都缺（不可读）→ `None`，**不臆造 1.0**。
    """
    d = _num(demand_qty)
    s = _num(supply_qty)
    if d is None or s is None:
        return None
    if d <= 0:
        return 1.0                       # 无需求：回归基准
    if s <= 0:
        return None                      # 无可售供给：价格无意义
    # 满足率：1.0 = 供给能满足全部期望需求（→ 基准价，不涨不跌）
    fill = min(1.0, s / d)
    # 缺口越大，价格越高于基准（有界，PRESSURE_GAIN 控制斜率）
    shortfall = 1.0 - fill
    mult = 1.0 + shortfall * PRESSURE_GAIN
    return min(PRICE_BOUNDS[1], max(PRICE_BOUNDS[0], mult))


def discover_price(*, dim: str, demand_qty: Optional[float],
                   supply_qty: Optional[float],
                   prev_price: Optional[float],
                   monthly_cap: float = DEFAULT_MONTHLY_CAP) -> Dict[str, Any]:
    """本月价格发现：基准价 × 供需压力 →封顶缓动 → 本月有效成交价。

    **纯函数**（不写 `state`）；`record_trade_price` 负责登记。
    返回 `{dim, price, base_price, pressure, cap_applied, reason}`。
    `price is None` 表示**不可定价**（基准缺失或无供给），调用方须显式处理。
    """
    base = _base_price(dim)
    if base is None:
        return {"schema_version": PRICE_SCHEMA_VERSION, "dim": dim, "price": None,
                "base_price": None, "pressure": None, "cap_applied": False,
                "reason": "no_base_price"}
    press = price_pressure(demand_qty, supply_qty)
    if press is None:
        return {"schema_version": PRICE_SCHEMA_VERSION, "dim": dim, "price": None,
                "base_price": base, "pressure": None, "cap_applied": False,
                "reason": ("no_supply" if _num(supply_qty) is not None
                           and _num(supply_qty) <= 0 else "unknown_pressure")}
    target = base * press
    from core.game_state_econ import cap_monthly_price
    prev = _num(prev_price)
    if prev is None or prev <= 0:
        price = target                       # 首月无上期价 → 直接用目标（封顶无从施加）
        cap_applied = False
    else:
        price = cap_monthly_price(prev, target, monthly_cap)
        cap_applied = abs(price - target) > 1e-9
    # 绝对边界（相对基准价），防止 cap 与基准差太远
    price = min(base * PRICE_BOUNDS[1], max(base * PRICE_BOUNDS[0], price))
    return {"schema_version": PRICE_SCHEMA_VERSION, "dim": dim, "price": round(price, 6),
            "base_price": base, "pressure": round(press, 6),
            "cap_applied": cap_applied, "reason": "ok"}


def pref_good_key(pref: Any, dim: str) -> str:
    """**路（府州）级商品键**（B2-R2）：`f"{路名}|{商品}"`，如 `"京畿路|布"`。

    B2-R2 要求把需求/供给/成交均价/动态价的键统一为 `(路, 商品)`。
    旧结构（只按 `dim`）会让"多路累计需求"与"单路库存"配对，
    也让未受冲击的路随全局价一起跳价——已废弃。

    **命名纪律**：参数名用 `pref`（prefecture 缩写）而**不用 `route`**——
    本仓库另有**真义路线**的 `route`（外邦行军路线 `state.routes`、行军 path），
    同名不同义极易踩坑。这里的"路"是 `state.prefectures` 的键（行政区）。
    """
    return f"{pref}|{dim}"


def _lookup_dynamic(state, pref: Any, dim: str) -> Optional[float]:
    """读动态价：**先查本路键**，再回退旧的全局键（存档迁移兼容）。

    回退是**只读兼容**：旧档只有全局键时不丢数据，但**新写入一律路级**。
    """
    slot = getattr(state, "dynamic_prices", None)
    if not isinstance(slot, dict):
        return None
    v = _num(slot.get(pref_good_key(pref, dim)))
    if v is not None:
        return v
    # 旧档兼容（B2-R2 迁移）：先查标注为"无路归属"的旧全局价
    legacy = getattr(state, "dynamic_prices_legacy", None)
    if isinstance(legacy, dict):
        lv = _num(legacy.get(dim))
        if lv is not None:
            return lv
    # 更老的存档：全局键直接混在 dynamic_prices 里（无 `|`）
    return _num(slot.get(dim))


def record_trade_price(state, dim: str, *, paid: float, qty: float,
                       pref: Any = None,
                       key: str = "dynamic_prices") -> Optional[float]:
    """登记本月成交均价 → `state.dynamic_prices["<路>|<商品>"]`（**动态价槽**）。

    **不得改写 `MATERIAL_PRICE_BASE`**（基准表是长期锚，改了就无法校准/回档）。
    成交额或量为 0 → 返回 `None`（均价无意义），不写 0 冒充均价。
    `pref` 缺省时退回**全局键**（旧行为，仅供无路上下文的老调用方）。
    """
    p = _num(paid)
    q = _num(qty)
    if p is None or q is None or q <= 0:
        return None
    avg = p / q
    # 成交额为 0 → 均价 0 是**无效价格**（非"免费"），不写入动态价槽
    # （否则后续 `effective_buy_price` 会取到 0 价，凭空送货）。
    if avg <= 0:
        return None
    slot = getattr(state, key, None)
    if not isinstance(slot, dict):
        slot = {}
        setattr(state, key, slot)          # 动态价槽；存档迁移见 tasks
    dkey = pref_good_key(pref, dim) if pref is not None else dim
    prev = _num(slot.get(dkey))
    slot[dkey] = round(avg if prev is None else (prev + avg) / 2.0, 6)
    return slot[dkey]


# ── 治所级价格发现（G-5 · 2026-10-04） ──
#
# 现状（实测）：价格发现已有**路级**实现（B2-R2 键 `"路|商品"`，见 `pref_good_key`），
# 但 `market_price` 里「治所」命中 0 次 ⇒ **州府桶里的货共用本路一个价**，
# 「运没运到」对价格**不可观测**。
#
# 做法：键再扩一段 ⇒ `"路|治所|商品"`。
#   · 治所段缺失的旧键 `"路|商品"` 仍可读（**向后兼容**，旧档不必迁移）；
#   · 写入一律带治所段（新口径），符合「写入只走新载体」的既有纪律；
#   · 州府没成交过 ⇒ 该治所**无键** ⇒ 回落本路价（回落而非填 0，缺失≠0）。
#
# 命名纪律沿用 `pref_good_key`：本仓库的 `route` 指外邦行军路线，与行政区无关，勿混用。

SEAT_KEY_SEP = "|"


def seat_good_key(pref: Any, seat: Any, dim: str) -> str:
    """**治所级商品键**：`"<路>|<治所>|<商品>"`，如 `"京畿路|开封府|木"`。

    `seat` 传完整治所 id（`"京畿路|开封府"`）或**只传治所名**（`"开封府"`）都可用 ——
    内部只取最后一段，避免同一治所因传法不同产生两个键。
    """
    if seat is None:
        return pref_good_key(pref, dim)
    s = str(seat).split(SEAT_KEY_SEP)[-1] if SEAT_KEY_SEP in str(seat) else str(seat)
    return "%s%s%s%s%s" % (pref, SEAT_KEY_SEP, s, SEAT_KEY_SEP, dim)


def _lookup_seat_price(state, pref: Any, seat: Any, dim: str) -> Optional[float]:
    """读治所级动态价：先治所键，再**回落本路键**（旧档兼容）；都没有 ⇒ `None`。

    回落而非填 0：治所本月无成交**不代表**没有价格，属「缺失≠0」。
    """
    if state is None or seat is None:
        return None
    slot = getattr(state, "dynamic_prices", None)
    if not isinstance(slot, dict):
        return None
    v = _num(slot.get(seat_good_key(pref, seat, dim)))
    if v is not None:
        return v
    return _lookup_dynamic(state, pref, dim)


def record_seat_trade_price(state, dim: str, *, paid: float, qty: float,
                             pref: Any, seat: Any,
                             key: str = "dynamic_prices") -> Optional[float]:
    """登记**治所级**成交均价 → `state.dynamic_prices["路|治所|商品"]`。

    与 `record_trade_price` 同口径：成交额/量为 0 ⇒ `None`（不写 0 冒充均价）；
    **不得改写 `MATERIAL_PRICE_BASE`**（基准表是长期锚）。
    """
    p = _num(paid)
    q = _num(qty)
    if p is None or q is None or q <= 0:
        return None
    avg = p / q
    if avg <= 0:
        return None
    slot = getattr(state, key, None)
    if not isinstance(slot, dict):
        slot = {}
        setattr(state, key, slot)
    dkey = seat_good_key(pref, seat, dim)
    prev = _num(slot.get(dkey))
    slot[dkey] = round(avg if prev is None else (prev + avg) / 2.0, 6)
    return slot[dkey]


def discover_seat_price(*, dim: str, pref: Any, seat: Any,
                        demand_qty: Optional[float], supply_qty: Optional[float],
                        prev_price: Optional[float],
                        monthly_cap: float = DEFAULT_MONTHLY_CAP) -> Dict[str, Any]:
    """**治所级**价格发现：`discover_price` 的治所版（同一压力模型与边界）。

    `prev_price` 缺省时依次回落：治所成交均价 → 本路动态价 → 基准价。
    返回结构与 `discover_price` 一致（含 `seat`），便于同一套断言复用。
    """
    prev = prev_price
    if prev is None:
        prev = _lookup_seat_price(None, pref, seat, dim)
    r = discover_price(dim=dim, demand_qty=demand_qty, supply_qty=supply_qty,
                       prev_price=prev, monthly_cap=monthly_cap)
    r["pref"] = pref
    r["seat"] = seat
    r["key"] = seat_good_key(pref, seat, dim)
    return r


def effective_buy_price(*, dim: str, state=None,
                        gov_price: Optional[float] = None,
                        pref: Any = None,
                        use_dynamic: bool = True) -> Dict[str, Any]:
    """取民间**实际买入价**：官定价优先，其次**本路**动态成交价，最后基准价。

    显式区分四种价格（口径分离，B2-5）：调用方须知道自己拿的是哪一类。
    返回 `{price, kind, reason}`，其中 `kind ∈ {official, dynamic, base, none}`。
    `pref` ＝ 路名（`state.prefectures` 的键）；**不用 `route`**（见 `pref_good_key`命名说明）。
    """
    g = _num(gov_price)
    if g is not None and g > 0:
        return {"price": g, "kind": "official", "reason": "官定/官购价优先"}
    if use_dynamic and state is not None:
        dyn = _lookup_dynamic(state, pref, dim)
        if dyn is not None and dyn > 0:
            scope = "本路" if pref is not None else "全局"
            return {"price": dyn, "kind": "dynamic",
                    "reason": f"{scope}动态成交均价（B2-R2 路级键）"}
    base = _base_price(dim, state=state)     # B4-2：未解锁新材在此判 `None`
    if base is not None:
        return {"price": base, "kind": "base", "reason": "无动态价，回落基准价"}
    return {"price": None, "kind": "none", "reason": "无可用价格（缺失，不作 0）"}