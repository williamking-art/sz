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
    "WATER_FREIGHT", "OVER_TAX_SHARE", "STAY_TAX_SHARE",
    "condition_mult", "road_condition", "canal_condition",
    "ROUTE_WATERWAY", "WATERWAY_TIER_MULT", "waterway_tier", "water_freight_tiered",
    "water_freight", "tax_split", "tax_cost", "trade_total_cost", "trade_net",
    "run_checks", "run_checks2", "run_checks3",
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
                 freight: Optional[int], tax_rate: float = 0.0) -> Dict[str, object]:
    """出口报价（**商人优先**）。返回成交量 / 扣货构成 / 需付金额。

    口径：
      · 货源 = **商人 goods 优先**，不足才取**官仓**；
      · 成交量 = min(供得上, 对方需求, **税后**付得起)；
      · 应付 = 货款 + 运费 + **税**（`tax_rate` = `commerce_tax_rate`）；
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
    # 税后付得起：货款 + 运费 + 税（税率作用于成交额）
    _r = max(0.0, float(tax_rate or 0.0))
    affordable = int(max(0.0, float(buyer_wealth) - float(freight)) / (up * (1.0 + _r)))
    qty = min(want, affordable)
    if qty <= 0:
        return {"ok": False, "reason": "insufficient_purchasing_power"}
    from_merchant = min(int(qty), int(merchant_have))
    from_warehouse = int(qty) - from_merchant
    _gv = int(round(qty * up))
    _tax = tax_cost(_gv, _r)
    return {
        "ok": True,
        "qty": int(qty),
        "from_merchant": int(from_merchant),
        "from_warehouse": int(from_warehouse),
        "goods_value": _gv,
        "freight": int(freight),
        "tax": _tax,
        "payable": _gv + int(freight) + _tax,
    }


def import_quote(merchant_room: int, buyer_wealth: float, unit_price: float,
                 seller_supply: int, freight: Optional[int],
                 tax_rate: float = 0.0) -> Dict[str, object]:
    """进口报价（**商人优先**：进口货入商人 goods）。

    成交量 = min(对方可供, 商人容量, 宋方**税后**付得起)；
    应付 = 货款 + 运费 + **税**。
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
    _r = max(0.0, float(tax_rate or 0.0))
    affordable = int(max(0.0, float(buyer_wealth) - float(freight)) / (up * (1.0 + _r)))
    qty = min(supply, room, affordable)
    if qty <= 0:
        return {"ok": False, "reason": "insufficient_purchasing_power"}
    _gv = int(round(qty * up))
    _tax = tax_cost(_gv, _r)
    return {
        "ok": True,
        "qty": int(qty),
        "goods_value": _gv,
        "freight": int(freight),
        "tax": _tax,
        "payable": _gv + int(freight) + _tax,
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

# ============================================================
# 水运 / 交通状况 / 税务（2026-10-05 用户补充）
# ============================================================

#: 水运费率（贯/万单位）。**平坦低费率**（不按距离档）—— 内河/运河是「廉价大宗通道」。
#: ⚠️ 玩法设定，待标定。
WATER_FREIGHT = {"per_wan": 1.0}

#: 过税 : 住税 分解比例（**宋代史实 2% : 3%**）。
#: 二者之和 == commerce_tax_rate（**不新增税率旋钮**）。
OVER_TAX_SHARE = 0.4     # 过税（流通）
STAY_TAX_SHARE = 0.6     # 住税（销地）

#: 交通状况 → 成本倍数的下限/上限（完好 ×1.0，失修 ×2.0）。
COND_MULT_BEST = 1.0
COND_MULT_WORST = 2.0


def condition_mult(cond: float) -> float:
    """交通状况 → 成本倍数。`cond∈[0,1]`，1=完好、0=失修。

    - 完好 ⇒ ×1.0；
    - 失修 ⇒ ×2.0（`1/(0.5+0.5*0)`）；
    - 越修越便宜（**玩家修缮动机的数学来源**）。
    """
    c = max(0.0, min(1.0, float(cond)))
    return 1.0 / (0.5 + 0.5 * c)


def road_condition(road_lv: int = 0) -> float:
    """陆运交通状况（由**道路等级**给）。现无 `道路` 状态 ⇒ 默认 0（失修）。"""
    lv = max(0, int(road_lv))
    return max(0.0, min(1.0, lv / 5.0))


def canal_condition(canal_block: int = 0, water_lv: int = 0,
                    canal_efficiency: float = 0.0) -> float:
    """水运交通状况 = `1 − 阻塞/100` + 水利等级加成 + `canal_efficiency` 科技。

    - `canal_block`：**既有状态**（0 通畅 ~ 100 阻塞，`game_state.canal_block`）|
    - `water_lv`：**既有**「水利」建筑等级（`game_state.py:219`「疏浚漕运」）|
    - `canal_efficiency`：**既有科技效果**（`data_tech.py` 授予，**此前无人读**）。
    """
    base = 1.0 - max(0.0, min(100.0, float(canal_block))) / 100.0
    bonus = 0.05 * max(0, int(water_lv)) + max(0.0, float(canal_efficiency))
    return max(0.0, min(1.0, base + bonus))


def water_freight(qty: int, cond: float) -> Dict[str, float]:
    """水运运费（**平坦低费率 × 交通状况系数**）。"""
    base = int(qty) / 10000.0 * WATER_FREIGHT["per_wan"]
    return {"fee": float(round(base * condition_mult(cond), 2)), "cond": float(cond)}


def tax_split(tax_rate: float) -> Dict[str, float]:
    """把 `commerce_tax_rate` 按 **过税 : 住税 = 2 : 3**（史实）分解。"""
    r = max(0.0, float(tax_rate or 0.0))
    return {"over": r * OVER_TAX_SHARE, "stay": r * STAY_TAX_SHARE, "total": r}


def tax_cost(goods_value: int, tax_rate: float) -> int:
    """税务成本 = 成交额 × 税率（过税 + 住税）。**不新增旋钮**，复用 `commerce_tax_rate`。"""
    return int(round(int(goods_value) * max(0.0, float(tax_rate or 0.0))))


def trade_total_cost(goods_value: int, freight: int, tax_rate: float = 0.0) -> Dict[str, int]:
    """**贸易总成本三要素**：货款 + 运输 + 税务。"""
    tax = tax_cost(goods_value, tax_rate)
    return {"goods": int(goods_value), "freight": int(freight), "tax": tax,
            "total": int(goods_value) + int(freight) + tax}


def trade_net(sale_value: int, goods_value: int, freight: int,
              tax_rate: float = 0.0, threshold: int = 0) -> Dict[str, object]:
    """税后净利与**是否成交**（净利 ≤ 门槛 ⇒ 不走）。

    ⇒ **贸易决策从「税前」变为「税后」**（真实商人会做的判断）。
    """
    c = trade_total_cost(goods_value, freight, tax_rate)
    net = int(sale_value) - c["total"]
    return {"ok": net > int(threshold), "net": net, "cost": c}

def run_checks2():
    """水运 / 交通状况 / 税务 自检（第二批）。"""
    out = []

    def add(n, ok, note=""):
        out.append((n, bool(ok), note))

    # 13 交通状况系数：完好 ×1.0 / 失修 ×2.0
    add("13 交通系数 完好1.0失修2.0",
        abs(condition_mult(1.0) - COND_MULT_BEST) < 1e-9
        and abs(condition_mult(0.0) - COND_MULT_WORST) < 1e-9,
        "cond1=%.2f cond0=%.2f" % (condition_mult(1.0), condition_mult(0.0)))

    # 14 水运：失修 ⇒ 运费翻倍（玩家修缮动机）
    f_good = water_freight(1_000_000, 1.0)["fee"]
    f_bad = water_freight(1_000_000, 0.0)["fee"]
    add("14 失修水运翻倍", abs(f_bad - f_good * 2) < 1e-6, "%.1f -> %.1f" % (f_good, f_bad))

    # 15 水运状况受 block/水利/科技 影响
    c_bad = canal_condition(canal_block=100)
    c_ok = canal_condition(canal_block=0, water_lv=5, canal_efficiency=0.3)
    add("15 水运状况三因素", c_bad == 0.0 and c_ok == 1.0,
        "阻塞100=%.2f 通畅+水利5+科技0.3=%.2f" % (c_bad, c_ok))

    # 16 过税:住税 = 2:3 且合计 == 税率
    sp = tax_split(0.06)
    add("16 过税:住税=2:3", abs(sp["over"] / sp["total"] - OVER_TAX_SHARE) < 1e-9
        and abs(sp["total"] - 0.06) < 1e-9,
        "over=%.3f stay=%.3f total=%.3f" % (sp["over"], sp["stay"], sp["total"]))

    # 17 税务成本 = 成交额 × 税率
    add("17 税务成本线性", tax_cost(10000, 0.06) == 600, str(tax_cost(10000, 0.06)))

    # 18 税后应付 = 货款 + 运费 + 税
    q = export_quote(1000, 0, 1000, 10.0, 1e9, 50, tax_rate=0.06)
    add("18 应付三要素", q["payable"] == q["goods_value"] + q["freight"] + q["tax"],
        "%d = %d + %d + %d" % (q["payable"], q["goods_value"], q["freight"], q["tax"]))

    # 19 拉弗效应：税率高 ⇒ 成交量低
    w = 10000.0
    q_lo = export_quote(10**9, 0, 10**9, 10.0, w, 0, tax_rate=0.05)
    q_hi = export_quote(10**9, 0, 10**9, 10.0, w, 0, tax_rate=0.40)
    add("19 税率高则量低", q_lo["qty"] > q_hi["qty"],
        "5%%→%d  40%%→%d" % (q_lo["qty"], q_hi["qty"]))

    # 20 税后净利与成交判定
    n1 = trade_net(12000, 10000, 100, tax_rate=0.06)
    n2 = trade_net(10500, 10000, 100, tax_rate=0.06)
    add("20 税后净利判定", n1["ok"] and not n2["ok"],
        "净%d ok=%s / 净%d ok=%s" % (n1["net"], n1["ok"], n2["net"], n2["ok"]))

    return out

#: 逐路可航性三档（**依史实漕运水道**，非空间计算所得）。
#: 依据见 `_dev_tools/game-docs/specs/ROUTE_WATERWAY逐路可航性.md`（理由逐路注明）。
#: ⚠️ 「强」⇒ 水运可完全替代陆运；「有」⇒ 部分可用；「弱」⇒ 通航受限。
ROUTE_WATERWAY: Dict[str, Tuple[str, ...]] = {
    "强": ("京畿路", "京东西路", "两浙路", "江南东路", "淮南东路",
           "荆湖北路", "夔州路"),
    "有": ("京东东路", "京西路", "河北路", "江南西路", "淮南西路",
           "荆湖南路", "福建路", "成都府路", "利州路",
           "广南东路", "广南西路"),
    "弱": ("河东路", "陕西路", "黔中路"),
}

#: 可航档 → 水运成本倍数（弱档水道淤浅/礁险 ⇒ 优势变小）。
WATERWAY_TIER_MULT: Dict[str, float] = {"强": 1.0, "有": 1.3, "弱": 1.8}


def waterway_tier(route: str) -> Optional[str]:
    """该路可航档（**路级派生**：取该路已登记治所中的最高档）。

    真账＝**治所级**表 `waterway_seats.SEAT_WATERWAY`（由本模块史料表首府承载生成，
    见 `specs/transport/交通下沉州府级.md`）；本函数是**派生聚合**。
    治所级模块不可用/未覆盖 ⇒ **回落到本模块 `ROUTE_WATERWAY` 表**（可选层纪律：不得卡流程）。
    **未登记 ⇒ None**（承「缺失≠0」⇒ 不可水运）。
    """
    try:
        from core.domains.economy.waterway_seats import waterway_tier_route
        t = waterway_tier_route(route)
        if t is not None:
            return t
    except Exception:  # noqa: BLE001 — 可选层：失败回落原表
        pass
    for tier, routes in ROUTE_WATERWAY.items():
        if route in routes:
            return tier
    return None


def water_freight_tiered(qty: int, cond: float, route: str) -> Optional[Dict[str, float]]:
    """带**可航档**的水运报价。

    - 路未登记可航 ⇒ **None**（不臆造水路）；
    - 成本 = 基础费率 × 交通状况系数 × **档位倍数**（弱档更贵）。
    """
    tier = waterway_tier(route)
    if tier is None:
        return None
    base = water_freight(qty, cond)
    m = WATERWAY_TIER_MULT.get(tier, 1.0)
    fee = float(round(base["fee"] * m, 2))
    return {"fee": fee, "cond": float(cond), "tier": tier}


def run_checks3():
    """可航性自检（第三批）。"""
    out = []

    def add(n, ok, note=""):
        out.append((n, bool(ok), note))

    # 21 三档覆盖 21 路，无重复无遗漏
    allr = [r for rs in ROUTE_WATERWAY.values() for r in rs]
    add("21 三档无重无漏", len(allr) == len(set(allr)) == 21,
        "共 %d 路（去重 %d）" % (len(allr), len(set(allr))))

    # 22 京畿路 = 强（汴河漕运四河之首）
    add("22 京畿路强", waterway_tier("京畿路") == "强", str(waterway_tier("京畿路")))

    # 23 两浙路 = 强（江南运河/太湖）
    add("23 两浙路强", waterway_tier("两浙路") == "强", str(waterway_tier("两浙路")))

    # 24 河东路 = 弱（壶口龙门礁险）
    add("24 河东路弱", waterway_tier("河东路") == "弱", str(waterway_tier("河东路")))

    # 25 未登记路 ⇒ None（缺失≠0，不可水运）
    add("25 未登记不可水运", water_freight_tiered(10000, 1.0, "不存在路") is None, "None")

    # 26 档位倍率生效：强 < 有 < 弱
    a = water_freight_tiered(1_000_000, 1.0, "京畿路")
    b = water_freight_tiered(1_000_000, 1.0, "河北路")
    c = water_freight_tiered(1_000_000, 1.0, "河东路")
    add("26 档位倍率生效", a["fee"] < b["fee"] < c["fee"],
        "强%.0f < 有%.0f < 弱%.0f" % (a["fee"], b["fee"], c["fee"]))

    # 27 水运×交通状况 与 档位 独立可叠加
    d = water_freight_tiered(1_000_000, 0.0, "京畿路")
    add("27 失修翻倍(带档)", abs(d["fee"] - a["fee"] * 2) < 1e-6,
        "%.1f -> %.1f" % (a["fee"], d["fee"]))

    return out