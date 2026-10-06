# -*- coding: utf-8 -*-
"""外贸货腿影子模块（只读）—— **不接入正式结算**。

## 性质

宋 ↔ 外邦贸易的**货腿**影子实现：验证「出口扣货 + 进口加货 + 运费 + 钱流」**四者对账**。

- 纯函数 / 只读 —— 不写任何 state；
- 不被 settlement* 引用；
- 用途：跑守恒自检、供接入前裁定参考。

## 用户裁定（2026-10-05）

1. 先做**已有外邦**（辽/西夏/吐蕃/大理/高丽/日本），中亚/欧洲作**抽象化身**；
2. **商人优先**（出口货源先取商人 goods，不足才动官仓）；
3. **计入物流成本**（复用既有 LOGISTICS_FEE 等）；
4. **海贸成本单列**（结构不同：固定 + 低单位费率 + 海损）。

## 口径纪律

- **缺失 ≠ 0 ≠ 1.0**：无货 ⇒ 不成交（返回 None/0），不凭空给货；
- **不新开账本**：钱只走既有 `transfer_money(pop:<路>:商人 → …)` 思路；
- **不留半笔账**：先验货源与资金，全部满足才成交。
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

__all__ = [
    "LOGISTICS_FEE", "TERRAIN_MULT", "WAR_MULT", "SEA_FREIGHT",
    "DISTANCE_BAND", "REGIME_IMPORTS", "ABSTRACT_TRADERS",
    "land_freight", "sea_freight", "export_quote", "import_quote",
    "run_checks",
]

#: 陆路物流费率（贯/万单位/趟）—— **复用既有口径**（`data_external.EXTERNAL_ECON` 同值）。
LOGISTICS_FEE = {"intra": 0.5, "d300": 1.5, "d1000": 3.0, "d3000": 6.0, "far": 10.0}

#: 地形倍数（既有口径）。
TERRAIN_MULT = {"山越": 1.5, "草原": 1.2, "平川": 1.0}

#: 战乱倍数：`_at_war` 或 **attitude < 30**（既有口径）。
WAR_MULT = 1.5

#: 海路运费（**结构不同于陆路**：固定 + 低单位费率 + 海损）。
#: ⚠️ 数值为**玩法设定**，待标定；本模块只定**结构**。
SEA_FREIGHT = {
    "fixed": 50.0,     # 每趟固定（船舶/港口/报关）
    "per_wan": 0.8,    # 贯/万单位 —— 低于陆路 far(10.0)
    "loss": 0.05,      # 海损/风险率（真实货物损耗，须单独计入对账）
}

#: 各伙伴的**陆路距离档**（海路伙伴另走 `sea_freight`）。
DISTANCE_BAND: Dict[str, str] = {
    "辽": "d300", "西夏": "d1000", "吐蕃": "d1000",
    "大理": "d3000", "高丽": "d3000", "日本": "far",
}

#: 各伙伴的**出口去向 / 进口货种**（依史实；玩法设为可用集）。
#: ⚠️ 「进口货种」中的维若游戏内**不存在**，接入时须先补维或降级。
REGIME_IMPORTS: Dict[str, Tuple[str, ...]] = {
    "辽": ("马", "皮毛", "药材"),
    "西夏": ("马", "青盐", "药材"),
    "吐蕃": ("马", "药材"),
    "大理": ("马", "麝香"),
    "高丽": ("人参", "布", "纸"),
    "日本": ("硫黄", "漆器"),
}

#: 海路伙伴（走 `sea_freight`）。
SEA_TRADERS = ("日本", "高丽")

#: 抽象化身（中亚/欧洲）——**不建 POP**，只作贸易对手。
ABSTRACT_TRADERS: Dict[str, Tuple[str, ...]] = {
    "中亚": ("香料", "良马", "玉石"),
    "欧洲": ("香料", "珠宝", "玻璃"),
}


def land_freight(qty: int, band: str, terrain: str = "平川",
                 attitude: int = 50) -> Optional[int]:
    """陆路运费（贯）。`band` 未知 ⇒ **None**（缺失≠0）。"""
    rate = LOGISTICS_FEE.get(band)
    if rate is None:
        return None
    t = TERRAIN_MULT.get(terrain, 1.0)
    fee = int(qty) / 10000.0 * rate * t
    if int(attitude) < 30:
        fee *= WAR_MULT
    return int(round(fee))


def sea_freight(qty: int, storm: bool = False) -> Dict[str, float]:
    """海路运费与海损。返回 `{fee, loss_qty}`（**结构不同于陆路**）。

    - `fee` = 固定 + 单位费率（**近程不划算、远程占优**）；
    - `loss_qty` = 真实货物损耗（**须单独计入对账**，不与运费混淆）。
    """
    q = int(qty)
    fee = SEA_FREIGHT["fixed"] + q / 10000.0 * SEA_FREIGHT["per_wan"]
    if storm:
        fee *= 1.5
    loss = q * SEA_FREIGHT["loss"] * (1.5 if storm else 1.0)
    return {"fee": float(round(fee, 2)), "loss_qty": int(round(loss))}


def export_quote(merchant_have: int, warehouse_have: int, buyer_demand: int,
                 unit_price: float, buyer_wealth: float,
                 freight: Optional[int]) -> Dict[str, object]:
    """出口报价（**商人优先**）。返回成交量 / 扣货构成 / 需付金额。

    口径：
      · 货源 = **商人 goods 优先**，不足才取**官仓**；
      · 成交量 = min(供得上, 对方需求, 对方付得起)；
      · 运费由**买方**承担（计入应付）；
      · 任何一项不足 ⇒ 不成交（**不凭空给货**）。
    """
    if freight is None:
        return {"ok": False, "reason": "no_freight_band"}
    up = float(unit_price or 0.0)
    if up <= 0:
        return {"ok": False, "reason": "no_price"}
    supply = int(merchant_have) + int(warehouse_have)
    if supply <= 0:
        return {"ok": False, "reason": "no_stock"}
    want = min(int(buyer_demand), supply)
    # 对方付得起：货款 + 运费
    affordable = int(max(0.0, float(buyer_wealth) - float(freight)) / up)
    qty = min(want, affordable)
    if qty <= 0:
        return {"ok": False, "reason": "insufficient_purchasing_power"}
    from_merchant = min(int(qty), int(merchant_have))
    from_warehouse = int(qty) - from_merchant
    return {
        "ok": True,
        "qty": int(qty),
        "from_merchant": int(from_merchant),
        "from_warehouse": int(from_warehouse),
        "goods_value": int(round(qty * up)),
        "freight": int(freight),
        "payable": int(round(qty * up)) + int(freight),
    }


def import_quote(merchant_room: int, buyer_wealth: float, unit_price: float,
                 seller_supply: int, freight: Optional[int]) -> Dict[str, object]:
    """进口报价（**商人优先**：进口货入商人 goods）。

    成交量 = min(对方可供, 商人容量, 宋方付得起)；运费由**宋方买方**承担。
    """
    if freight is None:
        return {"ok": False, "reason": "no_freight_band"}
    up = float(unit_price or 0.0)
    if up <= 0:
        return {"ok": False, "reason": "no_price"}
    supply = int(seller_supply)
    if supply <= 0:
        return {"ok": False, "reason": "no_supply"}
    room = int(merchant_room)
    if room <= 0:
        return {"ok": False, "reason": "no_room"}
    affordable = int(max(0.0, float(buyer_wealth) - float(freight)) / up)
    qty = min(supply, room, affordable)
    if qty <= 0:
        return {"ok": False, "reason": "insufficient_purchasing_power"}
    return {
        "ok": True,
        "qty": int(qty),
        "goods_value": int(round(qty * up)),
        "freight": int(freight),
        "payable": int(round(qty * up)) + int(freight),
    }


def run_checks():
    """跑货腿影子自检，返回 `[(项名, 通过?, 说明)]`。**纯只读**。"""
    out = []

    def add(n, ok, note=""):
        out.append((n, bool(ok), note))

    # 1 陆路档位单调递增
    vals = [land_freight(1_000_000, b) for b in ("intra", "d300", "d1000", "d3000", "far")]
    add("1 陆路运费档单调", all(a < b for a, b in zip(vals, vals[1:])), str(vals))

    # 2 未知档位 ⇒ None（缺失≠0）
    add("2 未知档位None", land_freight(1000, "no_such_band") is None, "缺失≠0")

    # 3 WAR_MULT 生效（attitude<30）—— 用大数量避免舍入掩盖
    a = land_freight(1_000_000, "d300", attitude=50)
    b = land_freight(1_000_000, "d300", attitude=20)
    add("3 关系恶化运费×1.5", abs(b - a * WAR_MULT) <= 1, "%s -> %s" % (a, b))

    # 4 海路结构：固定 + 低单位费率（远程占优）
    s_small = sea_freight(10_000)["fee"]
    s_big = sea_freight(1_000_000)["fee"]
    l_big = land_freight(1_000_000, "far")
    add("4 海路远程占优", s_big < l_big, "sea %.1f < land far %d" % (s_big, l_big))
    add("4b 海路近程不占优", s_small > land_freight(10_000, "d300"),
        "sea %.1f > land d300 %d" % (s_small, land_freight(10_000, "d300")))

    # 5 海损单独计（不与运费混淆）
    r = sea_freight(100_000)
    add("5 海损单独", r["loss_qty"] > 0 and "loss_qty" in r, "loss=%d fee=%.1f" % (r["loss_qty"], r["fee"]))

    # 6 出口：商人优先
    # 商人优先 = **先榨干商人**，仅余额取官仓（不是“只用商人”）
    q = export_quote(100, 900, 1000, 1.0, 1e9, 10)
    add("6 出口商人优先",
        q.get("ok") and q["from_merchant"] == min(q["qty"], 100)
        and q["from_warehouse"] == q["qty"] - q["from_merchant"],
        str({k: q.get(k) for k in ("qty", "from_merchant", "from_warehouse")}))

    # 7 出口：商人不足才取官仓
    q2 = export_quote(100, 900, 500, 1.0, 1e9, 10)
    add("7 不足取官仓", q2.get("ok") and q2["from_merchant"] == 100 and q2["from_warehouse"] == 400,
        str({k: q2.get(k) for k in ("qty", "from_merchant", "from_warehouse")}))

    # 8 出口：无货 ⇒ 不成交（不凭空给货）
    q3 = export_quote(0, 0, 1000, 1.0, 1e9, 10)
    add("8 无货不成交", not q3.get("ok"), q3.get("reason"))

    # 9 出口：买不起 ⇒ 不成交（运费计入应付）
    q4 = export_quote(1000, 0, 1000, 10.0, 5.0, 1000)
    add("9 买不起不成交", not q4.get("ok"), q4.get("reason"))

    # 10 扣货量 == 报价量（无凭空）
    q5 = export_quote(300, 700, 600, 2.0, 1e9, 50)
    add("10 扣货等于报价量", (q5["from_merchant"] + q5["from_warehouse"]) == q5["qty"],
        "%d+%d=%d" % (q5["from_merchant"], q5["from_warehouse"], q5["qty"]))

    # 11 进口：容量约束
    i1 = import_quote(100, 1e9, 1.0, 1000, 10)
    add("11 进口受容量约束", i1.get("ok") and i1["qty"] == 100, str(i1.get("qty")))

    # 12 应付 = 货款 + 运费
    i2 = import_quote(1000, 1e9, 3.0, 1000, 77)
    add("12 应付含运费", i2["payable"] == i2["goods_value"] + i2["freight"],
        "%d = %d + %d" % (i2["payable"], i2["goods_value"], i2["freight"]))

    return out