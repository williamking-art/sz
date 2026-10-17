# -*- coding: utf-8 -*-
"""八大实体多级产业链网络与田亩/地脉内生原料产出（单一权威源）。

## 规格与背景（M316 / 八大支柱实体产业链）

为彻底解决《宋祚》产业链过少、工坊谱系单薄、无法承载现代玩家向机械化与近代工业革命演进的根本痛点，
本模块建立八大实体多级产业链网络，使原料从 21 路田亩地力、地脉矿藏与牧场内生产出，
并经由工坊逐步加工为高附加值终端物资，物理确权写入治所物理四仓：

1. **原料田亩地力与地脉内生化**：
   - 粮食：在册主粮田亩 × 路级亩产 ÷ 12 月（原粮，酿酒与常平仓储备）；
   - 纤维：桑麻经济田亩（`CASH_CROP_LAND`）产出生丝与原麻；
   - 经济作物：两广、福建等路蔗田产出甘蔗原料（`sugar_cane`）；
   - 地脉矿产：铁矿、焦煤、生铜、海井池盐、山林木料与采石；
   - 伴生与化工原料：瓷土石料（`clay`）、矿脉伴生硫硝（`sulfur_niter`）；
   - 畜牧产出：牲畜生革（`hides_raw`）与肉食商品（`meat_raw`）。

2. **八大实体多级产业链网络（原料 → 中间品 → 终成品）**：
   - 1. **纤维纺织被服链**（`CHAIN_TEXTILE`）：生丝/原麻 → 缫丝织造为绸缎/布匹 → 加工为被服军衣；
   - 2. **黑色冶金重工链**（`CHAIN_METALLURGY`）：铁矿+焦煤 → 高炉冶炼为熟铁/铸铁 → 锻造兵刃器械与农具铁铧；
   - 3. **水陆动力机械链**（`CHAIN_MACHINERY`）：木材+熟铁 → 水排/大纺车齿轮/机械构件 → 船坞修造漕船海舶；
   - 4. **火药化工军器链**（`CHAIN_GUNPOWDER`）：硫硝+木材木炭 → 配制火药 → 浇铸突火枪/震天雷/火器弹药；
   - 5. **有色金属铸造链**（`CHAIN_NONFERROUS`）：生铜矿石 → 精炼高纯熟铜 → 铸钱监官铸铜钱（平抑钱荒）；
   - 6. **畜牧皮具传动链**（`CHAIN_LEATHER`）：牧场生革 → 硝制熟皮 → 制造军用皮甲/战马鞍鞯/机械传动带；
   - 7. **陶瓷琉璃外贸链**（`CHAIN_CERAMICS`）：瓷土+煤炭柴薪 → 官窑/民窑烧制精品瓷器 → 市舶司外销创汇；
   - 8. **农副食货文教链**（`CHAIN_FOOD_CULTURE`）：原粮酿酒、甘蔗制糖、原麻造纸、木石雕版印刷经籍书籍与印版。

3. **物理入仓与守恒律**：
   - 所有产出物理入治所四仓（官营 `public_depot` / `public_granary`，民间 `civilian_depots`）；
   - 原料消耗必定产出相应中间品或成品，严守进销存对账。
   - 🔴 B-4（2026-10-17 审计）：报表 `outputs` 只是**理论产量**；真实账本在
     `summary["stock_settlement"]`——先从治所四仓扣原料（`inputs[*].taken`），
     再按各路原料权重把成品写入物理仓（`outputs_booked[*]`），逐笔记 `ledger`。
     无治所物理仓或完全无料时 `mode=report_only` 并显式列出 `report_only_outputs`，
     **绝不把报表数字冒充仓存**。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from content.data_geo_tables import CASH_CROP_LAND, PREFECTURE_INFO, PREFECTURE_LIST, ROAD_YIELD
from content.demography import EXTRA_CIRCUIT_DEMOG
from core.domains.economy.land_tenure import derive_circuit_tenure
from core.domains.economy.macro_climate import ALL_CIRCUITS_21

__all__ = [
    "derive_raw_production",
    "settle_industry_chains",
    "CHAIN_TEXTILE",
    "CHAIN_METALLURGY",
    "CHAIN_MACHINERY",
    "CHAIN_GUNPOWDER",
    "CHAIN_NONFERROUS",
    "CHAIN_LEATHER",
    "CHAIN_CERAMICS",
    "CHAIN_FOOD_CULTURE",
    # 历史向后兼容别名
    "CHAIN_ARMAMENT",
    "CHAIN_SALT_TEA",
    "CHAIN_CONSTRUCTION",
]

CHAIN_TEXTILE = "纤维纺织被服链"
CHAIN_METALLURGY = "黑色冶金重工链"
CHAIN_MACHINERY = "水陆动力机械链"
CHAIN_GUNPOWDER = "火药化工军器链"
CHAIN_NONFERROUS = "有色金属铸造链"
CHAIN_LEATHER = "畜牧皮具传动链"
CHAIN_CERAMICS = "陶瓷琉璃外贸链"
CHAIN_FOOD_CULTURE = "农副食货文教链"

# 历史向后兼容别名
CHAIN_ARMAMENT = CHAIN_GUNPOWDER
CHAIN_SALT_TEA = CHAIN_FOOD_CULTURE
CHAIN_CONSTRUCTION = CHAIN_MACHINERY


def _get_pref(state, circuit: str) -> Dict[str, Any]:
    """读取某路的 pref 对象（无 state pref 时回落 EXTRA_CIRCUIT_DEMOG）。"""
    prefs = getattr(state, "prefectures", None)
    if isinstance(prefs, dict):
        p = prefs.get(circuit)
        if isinstance(p, dict):
            return p
    if circuit in EXTRA_CIRCUIT_DEMOG:
        return dict(EXTRA_CIRCUIT_DEMOG[circuit])
    return {}


def derive_raw_production(state, circuit: str) -> Dict[str, float]:
    """根据该路田亩地力、作物比例与地脉，派生当月内生原料产出（纯函数，只读）。

    产出完全由田亩、地脉矿藏与牧场内生驱动，告别静态死值。
    """
    if circuit not in ALL_CIRCUITS_21:
        return {}

    p = _get_pref(state, circuit)
    tenure = derive_circuit_tenure(state, circuit)
    total_land = tenure["total_land"]
    if total_land <= 0:
        return {}

    # 亩产系数：两浙/江南 2.5 石/亩，北方 1.0 石/亩
    yield_mult = float(ROAD_YIELD.get(circuit, 1.0))

    # 经济作物田比例（桑蚕、茶、麻、蔗等）
    crop_shares = CASH_CROP_LAND.get(circuit, {})
    total_cash_share = sum(crop_shares.values())
    grain_land = total_land * max(0.60, 1.0 - total_cash_share)

    # 1. 月度原粮产出（石/月）
    # 年产 = 粮田 × 亩产；月产 = 年产 / 12
    monthly_grain = (grain_land * yield_mult) / 12.0

    # 2. 经济作物内生产出（单位/月）
    # 丝（桑蚕）：宋代江浙 1 亩桑田年产经丝约 1.5 斤（折月产，年额对齐 PREFECTURE_INFO 450万斤）
    silk_share = float(crop_shares.get("丝", 0.0))
    monthly_silk = (total_land * silk_share * 1.5) / 12.0

    # 麻：1 亩麻田年产原麻约 1.0 斤
    hemp_share = float(crop_shares.get("麻", 0.0))
    monthly_hemp = (total_land * hemp_share * 1.0) / 12.0

    # 茶：1 亩茶园年产毛茶约 3.3 斤
    tea_share = float(crop_shares.get("茶", 0.0))
    monthly_tea = (total_land * tea_share * 3.3) / 12.0

    # 蔗：1 亩蔗田年产甘蔗约 5.0 斤（两广、福建等主产）
    cane_share = float(crop_shares.get("蔗", 0.0))
    monthly_cane = (total_land * cane_share * 5.0) / 12.0

    # 3. 矿产与林石内生产出：对接 mineral_deposit 真实地脉储量
    from core.domains.economy.mineral_deposit import (
        extract_circuit_minerals, DIM_COPPER, DIM_COAL, DIM_IRON, DIM_SALT, DIM_TIMBER, DIM_STONE
    )
    clerk_grip = float(p.get("clerks_detail", {}).get("grip", 0.45) if isinstance(p.get("clerks_detail"), dict) else (p.get("grip", 0.45) or 0.45))
    mine_res = extract_circuit_minerals(state, circuit, rate_mult=1.0, clerk_grip=clerk_grip)

    monthly_iron_ore = mine_res.get(DIM_IRON, {}).get("physical_extracted", 0.0)
    monthly_copper_ore = mine_res.get(DIM_COPPER, {}).get("physical_extracted", 0.0)
    monthly_coal = mine_res.get(DIM_COAL, {}).get("physical_extracted", 0.0)
    monthly_salt = mine_res.get(DIM_SALT, {}).get("physical_extracted", 0.0)
    monthly_timber = mine_res.get(DIM_TIMBER, {}).get("physical_extracted", 0.0)
    monthly_stone = mine_res.get(DIM_STONE, {}).get("physical_extracted", 0.0)

    # 瓷土石料（用于陶瓷琉璃）：约占采石总量的 20%
    monthly_clay = monthly_stone * 0.20
    # 矿石硫硝（用于火药化工）：约占采矿伴生石料的 10%
    monthly_sulfur_niter = monthly_stone * 0.10

    # 4. 畜牧业产出内生对接（生革与肉食）
    from core.domains.economy.livestock_and_escort import derive_circuit_livestock
    ls = derive_circuit_livestock(state, circuit)
    monthly_hides = float(ls.get("hides", 0.0))
    monthly_meat = float(ls.get("meat", 0.0))

    # 矿税现钱（坑冶课税二分抽一折钱）
    mine_tax_coin = sum(m.get("tax_coin", 0.0) for m in mine_res.values())

    return {
        "grain": float(round(monthly_grain, 1)),
        "silk_raw": float(round(monthly_silk, 1)),
        "hemp_raw": float(round(monthly_hemp, 1)),
        "tea_raw": float(round(monthly_tea, 1)),
        "sugar_cane": float(round(monthly_cane, 1)),
        "iron_ore": float(round(monthly_iron_ore, 1)),
        "copper_ore": float(round(monthly_copper_ore, 1)),
        "coal": float(round(monthly_coal, 1)),
        "salt_raw": float(round(monthly_salt, 1)),
        "timber": float(round(monthly_timber, 1)),
        "stone": float(round(monthly_stone, 1)),
        "clay": float(round(monthly_clay, 1)),
        "sulfur_niter": float(round(monthly_sulfur_niter, 1)),
        "hides_raw": float(round(monthly_hides, 1)),
        "meat_raw": float(round(monthly_meat, 1)),
        "mine_tax_coin": float(round(mine_tax_coin, 1)),
    }


# ---------------------------------------------------------------------------
# B-4（2026-10-17 审计）：八大链真实 **stock-to-stock** 记账
# ---------------------------------------------------------------------------
#: 报表产出键 → 物理仓商品维（**同一批货只入仓一次**；别名不重复登记）。
_OUTPUT_STOCK_DIM: Dict[str, str] = {
    "silk_cloth_pi": "绸",
    "cloth_pi": "布",
    "garments_pieces": "被服军衣",
    "iron_ingots": "铁锭",
    "steel_ingots": "钢锭",
    "timber_beams": "木方",
    "machinery_parts": "机械零件",
    "weapons_pieces": "兵刃器械",
    "barges_built": "漕船海舶",
    "gunpowder_jin": "火药",
    "firearms_pieces": "火器弹药",
    "copper_ingots": "铜锭",
    "coins_minted_guan": "官铸铜钱",
    "tanned_leather_jin": "熟皮",
    "saddle_armor_pieces": "鞍具皮甲",
    "fine_china_pieces": "精品瓷器",
    "sugar_jin": "糖",
    "paper": "纸",
    "ink_jin": "油墨",
    "books_printed": "印造书籍",
    "four_treasures_pieces": "文房四宝",
    "firewood_dan": "薪炭",
    "cooking_oil_jin": "食用油",
    "paste_vinegar_jin": "酱醋",
}

#: 报表中**同一批货**的别名键：与主键同量，**不再二次入仓**（否则同一批货记两次）。
_OUTPUT_ALIAS_OF: Dict[str, str] = {
    "refined_iron": "iron_ingots",       # 熟铁/铁锭同一炉次
    "refined_copper": "copper_ingots",   # 精炼熟铜/铜锭同一炉次
    "leather": "tanned_leather_jin",     # 皮革/熟皮同一批
    "paper_sheets": "paper",             # 纸张/纸同一批
}

#: 消费/贸易类成品入**民间货栈**；重工/军器/官铸入**官工料场**。
_CONSUMER_OUTPUT_KEYS = frozenset({
    "silk_cloth_pi", "cloth_pi", "sugar_jin", "paper", "ink_jin",
    "books_printed", "four_treasures_pieces", "firewood_dan",
    "cooking_oil_jin", "paste_vinegar_jin", "fine_china_pieces",
})

#: 现钱类报表项（入国库，不进商品仓；单独标注，不算"仅报表货物"）。
_MONETARY_OUTPUT_KEYS = frozenset({"monopoly_tax_coin", "mine_tax_coin"})

#: 原料扣仓顺序：官工料场 → 民间货栈 → 官廪 → 私窖（确定性，便于对账）。
_WAREHOUSE_TAKE_ORDER = ("public_depot", "civilian_depots", "public_granary", "private_storage")


def _iter_seat_slots(state) -> List[Tuple[str, str, Dict[str, Any]]]:
    """按 21 路 → 治所 ID 的确定顺序摊平物理仓位（只读遍历）。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return []
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for route in ALL_CIRCUITS_21:
        pdata = prefs.get(route)
        if not isinstance(pdata, dict):
            continue
        seats = pdata.get("seats")
        if not isinstance(seats, dict):
            continue
        for sid in sorted(seats):
            seat = seats.get(sid)
            if isinstance(seat, dict):
                out.append((route, str(sid), seat))
    return out


def _warehouse_available(state, dim: str) -> float:
    """全域治所四仓某维可用存量（只读；缺失按 0，不凭空空耗）。"""
    total = 0.0
    for _route, _sid, seat in _iter_seat_slots(state):
        whs = seat.get("warehouses")
        if not isinstance(whs, dict):
            continue
        for wtype in _WAREHOUSE_TAKE_ORDER:
            cell = whs.get(wtype)
            stocks = cell.get("stocks") if isinstance(cell, dict) else None
            if not isinstance(stocks, dict):
                continue
            v = stocks.get(dim)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                total += float(v)
    return total


def _warehouse_take(state, dim: str, want: float) -> float:
    """从全域治所四仓按确定顺序扣减原料，返回**实际扣减量**（不得为负/凭空）。"""
    remaining = max(0.0, float(want))
    if remaining <= 0:
        return 0.0
    from core.foundation.ledger.spatial_warehouse_bridge import warehouse_stock_add
    taken = 0.0
    for _route, sid, seat in _iter_seat_slots(state):
        if remaining <= 1e-9:
            break
        whs = seat.get("warehouses")
        if not isinstance(whs, dict):
            continue
        for wtype in _WAREHOUSE_TAKE_ORDER:
            if remaining <= 1e-9:
                break
            cell = whs.get(wtype)
            stocks = cell.get("stocks") if isinstance(cell, dict) else None
            if not isinstance(stocks, dict):
                continue
            avail = stocks.get(dim)
            if not isinstance(avail, (int, float)) or isinstance(avail, bool):
                continue
            avail = float(avail)
            if avail <= 0:
                continue
            take = min(avail, remaining)
            got = warehouse_stock_add(state, sid, wtype, dim, -take,
                                      reason="industry_chain_feed")
            if got is None:
                continue
            actual = max(0.0, avail - float(got))
            if actual <= 0:
                continue
            taken += actual
            remaining -= actual
    return taken


def _route_capital_seat(state, route: str) -> Optional[str]:
    """取某路承载成品的治所（首府优先、退化到确定顺序首座）；无治所 ⇒ None。"""
    prefs = getattr(state, "prefectures", None)
    pdata = prefs.get(route) if isinstance(prefs, dict) else None
    if not isinstance(pdata, dict):
        return None
    seats = pdata.get("seats")
    if not isinstance(seats, dict) or not seats:
        return None
    try:
        from core.foundation.ledger.building_bridge import capital_seat_id
        sid = capital_seat_id(pdata, route)
        if sid and sid in seats and isinstance(seats.get(sid), dict):
            return str(sid)
    except Exception:                                       # noqa: BLE001
        pass
    return str(sorted(seats)[0])


#: 产业链成品键 → 代表建筑（用于消费 M317/M318 生产方式相对倍率）。
#: 未列出的成品键（绸/布/糖/纸/熟皮/食用油等）回退 1.0，保持默认中性。
_OUTPUT_PM_BUILDING = {
    "iron_ingots": "冶铁工场", "steel_ingots": "冶铁工场",
    "weapons_pieces": "冶铁工场",
    "copper_ingots": "冶铁工场", "coins_minted_guan": "冶铁工场",
    "machinery_parts": "木作机械坊", "timber_beams": "木作机械坊",
    "barges_built": "造船作坊",
    "gunpowder_jin": "火药局", "firearms_pieces": "火器制造坊",
    "fine_china_pieces": "官窑瓷坊",
    "books_printed": "印造经籍局", "paper": "印造经籍局",
    "ink_jin": "印造经籍局", "four_treasures_pieces": "印造经籍局",
}


def _warehouse_add_distributed(state, dim: str, qty: float, wtype: str,
                               weights: Dict[str, float], reason: str,
                               pm_building: Optional[str] = None) -> float:
    """把成品按各路原料权重分派入该路首府治所指定仓位，返回实际入仓量。

    2026-10-18 全审：可选 `pm_building` ⇒ 按该路建筑的生产方式**相对倍率**
    缩放产出（默认 PM 恒 1.0，逐位不变；切换到更优 PM 则同投入多产出）。
    """
    q = float(qty)
    if q <= 0:
        return 0.0
    rows: List[Tuple[str, str, float]] = []
    for route in ALL_CIRCUITS_21:
        sid = _route_capital_seat(state, route)
        if sid is None:
            continue
        rows.append((route, sid, float((weights or {}).get(route, 0.0) or 0.0)))
    if not rows:
        return 0.0
    if not any(w > 0 for _r, _s, w in rows):
        rows = [(route, sid, 1.0) for route, sid, _w in rows]
    base_total = sum(w for _r, _s, w in rows)
    if base_total <= 0:
        return 0.0

    # 生产方式相对倍率（按路；默认 PM ⇒ 1.0）
    mults = {route: 1.0 for route, _sid, _w in rows}
    if pm_building:
        try:
            from core.domains.economy.production_methods import (
                relative_throughput_multiplier,
            )
            for route, sid, _w in rows:
                try:
                    m = relative_throughput_multiplier(state, route, sid, pm_building)
                except Exception:  # noqa: BLE001 — 单路失败回中性
                    m = 1.0
                mults[route] = max(0.0, float(m or 1.0))
        except Exception:  # noqa: BLE001 — 模块不可用 ⇒ 中性
            mults = {route: 1.0 for route, _sid, _w in rows}

    weighted = [(route, sid, w * mults.get(route, 1.0))
                for route, sid, w in rows]
    scaled_total = sum(w for _r, _s, w in weighted)
    if scaled_total <= 0:
        weighted = rows
        scaled_total = base_total
    # 总产出 = 理论量 × 加权平均倍率（默认 1.0 时与原实现逐位一致）
    total_q = q * (scaled_total / base_total)

    from core.foundation.ledger.spatial_warehouse_bridge import warehouse_stock_add
    parts: List[float] = []
    allocated = 0.0
    for route, _sid, w in weighted[:-1]:
        part = round(total_q * w / scaled_total, 4)
        parts.append(part)
        allocated += part
    parts.append(round(total_q - allocated, 4))     # 尾差归末位，Σ 精确
    added = 0.0
    for (route, sid, _w), part in zip(weighted, parts):
        if part <= 0:
            continue
        got = warehouse_stock_add(state, sid, wtype, dim, part, reason=reason)
        if got is not None:
            added += part
    return added


def _warehouse_weights(state, dims) -> Dict[str, float]:
    """各路参与加工的原料权重（扣料**前**取样，用于成品产地分摊）。"""
    weights: Dict[str, float] = {}
    for route, _sid, seat in _iter_seat_slots(state):
        whs = seat.get("warehouses")
        if not isinstance(whs, dict):
            continue
        sub = 0.0
        for wtype in _WAREHOUSE_TAKE_ORDER:
            cell = whs.get(wtype)
            stocks = cell.get("stocks") if isinstance(cell, dict) else None
            if not isinstance(stocks, dict):
                continue
            for dim in dims:
                v = stocks.get(dim)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    sub += float(v)
        if sub > 0:
            weights[route] = weights.get(route, 0.0) + sub
    return weights


def _estimate_chain_input_demand(outputs: Dict[str, Any]) -> Dict[str, float]:
    """由成品产出反推本月八大链的原料加工需求（用于覆盖度与「无料不产」）。

    口径：每个原料维按**主用途**估算（`max` 而非累加，避免把同一批麻在三链重复计入）。
    """
    def _q(key: str) -> float:
        v = outputs.get(key, 0.0)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0

    return {
        "silk_raw": _q("silk_cloth_pi") * 3.0,
        "hemp_raw": max(_q("cloth_pi") * 2.0,
                        _q("paper") * 5.0,
                        _q("cooking_oil_jin") * 20.0),
        "iron_ore": _q("iron_ingots") * 2.0,
        "copper_ore": _q("copper_ingots") / 0.7,
        "coal": _q("iron_ingots") + _q("fine_china_pieces") * 20.0,
        "timber": max(_q("timber_beams") / 0.8,
                      _q("gunpowder_jin") * 10.0,
                      _q("ink_jin") * 10.0,
                      _q("firewood_dan") / 0.3),
        "clay": _q("fine_china_pieces") * 10.0,
        "sulfur_niter": _q("gunpowder_jin") * 2.0,
        "hides_raw": _q("tanned_leather_jin") / 0.8,
        "sugar_cane": _q("sugar_jin") * 3.0,
        "stone": _q("four_treasures_pieces") * 40.0,
        "grain": _q("paste_vinegar_jin") * 75.0,
    }


def _apply_chain_stock_settlement(state, outputs: Dict[str, Any]) -> Dict[str, Any]:
    """把八大链报表产出落到**真实物理仓**：先扣原料、再入成品、逐笔记账。

    契约：
    * **有治所物理仓且原料覆盖度 > 0** ⇒ `mode=warehouse_stock_to_stock`：
      - `inputs[dim].taken > 0` 且从治所四仓真实扣减；
      - `outputs_booked[key].qty` 为真实入仓增量（≤ 报表量 × 覆盖度）；
      - `alias_of` 标明同批货的报表别名（不重复入仓）。
    * **无物理仓 / 完全无料** ⇒ `mode=report_only`：
      - **不伪造入仓**，把所有正产出键显式列入 `report_only_outputs`
        （审计口径：报表产出必须有仓存增量，或显式标注"仅报表"）。
    """
    positive = sorted(
        k for k, v in outputs.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) > 0
    )
    report: Dict[str, Any] = {
        "mode": "report_only",
        # 权威载体：治所物理四仓（与 `state.resources` 全国池**不并行记账**，
        # 避免同一批货在两个 custody 各记一次）。
        "authority": "seats[*].warehouses",
        "reason": "",
        "alias_of": dict(_OUTPUT_ALIAS_OF),
        "monetary_outputs": [k for k in positive if k in _MONETARY_OUTPUT_KEYS],
        "inputs": {},
        "outputs_booked": {},
        "report_only_outputs": [],
        "ledger": [],
    }
    slots = _iter_seat_slots(state)
    if not slots:
        report["reason"] = ("无治所物理仓（state.prefectures[*].seats 缺失）"
                            "⇒ 产出仅报表，不伪造入仓")
        report["report_only_outputs"] = [k for k in positive if k not in _MONETARY_OUTPUT_KEYS]
        return report

    demand = _estimate_chain_input_demand(outputs)
    available = {dim: _warehouse_available(state, dim) for dim in demand}
    coverage = 1.0
    for dim, need in demand.items():
        if need <= 0:
            continue
        avail = float(available.get(dim, 0.0) or 0.0)
        coverage = min(coverage, max(0.0, min(1.0, avail / need)))
    report["input_coverage"] = round(coverage, 6)
    if coverage <= 0:
        report["reason"] = ("当月物理仓无对应原料（input_coverage=0）"
                            "⇒ 产出仅报表，不凭空入仓")
        report["report_only_outputs"] = [k for k in positive if k not in _MONETARY_OUTPUT_KEYS]
        return report

    report["mode"] = "warehouse_stock_to_stock"
    report["note"] = ("outputs 为理论产量；outputs_booked 为实际入仓量"
                      "（按 input_coverage 同比缩放）。若二者不等，差额来自"
                      "当月物理原料不足/未下沉路线，已在 inputs/ledger 留痕，"
                      "**不得把理论产量当作仓存**。")
    # 1) 先扣原料（按各维需求，不超可用）
    # 成品产地权重用**工业原料**（排除 grain 这种民生大宗，避免权重被粮仓淹没）
    weights = _warehouse_weights(state, [d for d in demand if d != "grain"])
    for dim in sorted(demand):
        need = float(demand[dim])
        if need <= 0:
            continue
        # 按全局覆盖度同比扣料：产出只按 coverage 入仓，投入也必须同比例，
        # 不得出现「扣满原料却只入 90% 成品」的隐形成本黑洞。
        want = min(need * coverage, float(available.get(dim, 0.0) or 0.0))
        taken = _warehouse_take(state, dim, want)
        report["inputs"][dim] = {
            "requested": round(need, 4),
            "available_before": round(float(available.get(dim, 0.0) or 0.0), 4),
            "taken": round(taken, 4),
        }
        report["ledger"].append({
            "step": "input", "dim": dim,
            "requested": round(need, 4), "taken": round(taken, 4),
        })

    # 2) 再入成品（同一批货只入一次；别名不入仓）
    for key in sorted(_OUTPUT_STOCK_DIM):
        qty = outputs.get(key, 0.0)
        if not isinstance(qty, (int, float)) or isinstance(qty, bool) or float(qty) <= 0:
            continue
        booked = float(int(round(float(qty) * coverage)))
        if booked <= 0:
            report["report_only_outputs"].append(key)
            continue
        dim = _OUTPUT_STOCK_DIM[key]
        wtype = "civilian_depots" if key in _CONSUMER_OUTPUT_KEYS else "public_depot"
        added = _warehouse_add_distributed(
            state, dim, booked, wtype, weights, reason="industry_chain_output",
            pm_building=_OUTPUT_PM_BUILDING.get(key))
        report["outputs_booked"][key] = {
            "dim": dim, "warehouse": wtype, "qty": round(added, 4),
        }
        report["ledger"].append({
            "step": "output", "key": key, "dim": dim,
            "warehouse": wtype, "booked": round(added, 4),
        })

    # 3) 既非入仓键、也非别名、也非现钱的报表项 ⇒ 显式标注"仅报表"
    for key in positive:
        if key in _OUTPUT_STOCK_DIM or key in _OUTPUT_ALIAS_OF or key in _MONETARY_OUTPUT_KEYS:
            continue
        report["report_only_outputs"].append(key)
    return report


def settle_industry_chains(state, log: Optional[List[str]] = None) -> Dict[str, Any]:
    """月度产业链推进与工坊深加工结算（受控写操作）。

    推进八大实体产业链网络：
    1. 纤维纺织被服链：生丝/原麻 → 织造绸布 → 加工为被服军衣；
    2. 黑色冶金重工链：铁矿+焦煤 → 高炉冶炼生熟铁 → 锻造兵刃器械与工具；
    3. 水陆动力机械链：木材+熟铁 → 打造水力机械构件与平底漕船/远洋海舶；
    4. 火药化工军器链：硫硝+木炭 → 配制火药 → 铸造火器弹药；
    5. 有色金属铸造链：生铜矿石 → 精炼熟铜 → 铸钱监官铸铜钱；
    6. 畜牧皮具传动链：生革 → 硝制熟皮 → 制造鞍具皮甲与传动带；
    7. 陶瓷琉璃外贸链：瓷土+焦煤 → 烧制官窑精品瓷器 → 出海创汇；
    8. 农副食货文教链：原粮酿酒、甘蔗精糖、造纸印制经籍书册。

    返回当月全链条投入、产出与对账结果。
    """
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats

    chain_ledger = stats.setdefault("industry_chains_ledger", {})

    # 1. 汇总 21 路当月原料内生产量，并物理确权写入各路治所四仓（物流上游底座）
    from core.domains.economy.logistics_coupler import ingest_upstream_production
    nat_raw = {
        "grain": 0.0, "silk_raw": 0.0, "hemp_raw": 0.0, "tea_raw": 0.0,
        "sugar_cane": 0.0, "iron_ore": 0.0, "copper_ore": 0.0, "coal": 0.0,
        "salt_raw": 0.0, "timber": 0.0, "stone": 0.0, "clay": 0.0,
        "sulfur_niter": 0.0, "hides_raw": 0.0, "meat_raw": 0.0,
        "mine_tax_coin": 0.0,
    }
    for c in ALL_CIRCUITS_21:
        prod = derive_raw_production(state, c)
        for k, v in prod.items():
            nat_raw[k] = nat_raw.get(k, 0.0) + v
        # 物理确权入各路四仓
        ingest_upstream_production(state, c, prod)

    # 2. 八大实体产业链多级深加工转化

    # 2. 八大实体产业链多级深加工转化（中性中间物流转 + 链式装配）

    # ① 纤维与被服中性物（丝绸与布料）
    silk_cloth_produced = float(round(nat_raw["silk_raw"] / 3.0, 1))
    hemp_cloth_produced = float(round(nat_raw["hemp_raw"] / 2.0, 1))
    fabric_neutral = hemp_cloth_produced
    silk_neutral = silk_cloth_produced
    # 下游被服链式组装：消耗布料 + 丝绸 缝制 1 领被服军衣
    garments_produced = float(round(min(fabric_neutral * 0.20 / 10.0, silk_neutral * 0.10 / 2.0), 1))

    # ② 黑色冶金中性物：铁矿 + 焦煤 -> 铁锭（熟铁）与钢锭
    iron_melted = float(round(min(nat_raw["iron_ore"] / 2.0, nat_raw["coal"]), 1))
    iron_ingots_neutral = iron_melted
    steel_ingots_neutral = float(round(iron_ingots_neutral * 0.25, 1))  # 炒钢与百炼钢法精炼钢锭

    # ③ 木作与机械中性物：原木经水碓锯解为中性木方；铁锭+木方精锻为机械零件
    timber_beams_neutral = float(round(nat_raw["timber"] * 0.8, 1))
    machinery_parts_produced = float(round(min(timber_beams_neutral * 0.25 / 10.0, iron_ingots_neutral * 0.20 / 5.0), 1))

    # ④ 造船坞下游链式装配：消耗中性木方 + 铁锭 + 布料（麻帆）装配漕船海舶
    barges_built = float(round(min(timber_beams_neutral * 0.35 / 150.0, iron_ingots_neutral * 0.15 / 20.0, fabric_neutral * 0.10 / 15.0), 1))
    if barges_built > 0:
        c_block = int(getattr(state, "canal_block", 0) or 0)
        relief = min(4, max(1, int(barges_built / 500.0)))
        state.canal_block = max(0, c_block - relief)

    # ⑤ 火工与军器下游链式装配：硝石 + 硫磺 + 木炭 配火药；再结合钢锭、铜锭、木方制造火器
    gunpowder_produced = float(round(min(nat_raw["sulfur_niter"] / 2.0, nat_raw["timber"] * 0.10), 1))
    copper_refined = float(round(nat_raw["copper_ore"] * 0.7, 1))
    copper_ingots_neutral = copper_refined
    # 🔴 B-4（2026-10-17 审计）：旧实现把 `copper_refined` **额外**加进
    #   `state.resources["铜"]`，却从未扣减 `copper_ore`（双记 + 凭空造铜），
    #   且「铜」并非合法商品维（`RESOURCE_DIMS` 无此项）。
    #   现统一由下方 `_apply_chain_stock_settlement`：先扣治所四仓 `copper_ore`，
    #   再把 `铜锭` 写入物理仓（同一炉次只记一次）。
    # 火器下游链式消费：钢锭 + 铜锭 + 火药 + 木方 -> 突火枪/火器弹药
    firearms_produced = float(round(min(gunpowder_produced * 0.40 / 4.0, steel_ingots_neutral * 0.30 / 3.0, copper_ingots_neutral * 0.20 / 2.0, timber_beams_neutral * 0.05 / 2.0), 1))

    # ⑥ 兵刃器械下游装配：钢锭/铁锭 + 木方 -> 兵刃器械与农具铁铧
    weapons_produced = float(round(min(iron_ingots_neutral * 0.30 / 5.0, timber_beams_neutral * 0.10 / 2.0), 1))

    # ⑦ 官铸铜钱：铜锭 + 铁锭合铸
    coins_minted = float(round(min(copper_ingots_neutral * 0.40 / 10.0, iron_ingots_neutral * 0.10 / 2.0), 1))

    # ⑧ 畜牧皮革中性物与下游鞍具装配：生革硝制熟皮；熟皮+铁锭制造鞍具皮甲与传动带
    tanned_leather_produced = float(round(nat_raw["hides_raw"] * 0.8, 1))
    leather_neutral = tanned_leather_produced
    saddle_armor_produced = float(round(min(leather_neutral * 0.50 / 5.0, iron_ingots_neutral * 0.08 / 1.0), 1))

    # ⑨ 陶瓷琉璃规范配方：黏土（高岭土）+ 焦煤 烧造精品青白瓷
    fine_china_produced = float(round(min(nat_raw["clay"] / 10.0, nat_raw["coal"] * 0.20 / 4.0), 1))
    export_trade_tax_coin = float(round(fine_china_produced * 15.0, 1))

    # ⑩ 农副食货文教与民生七事：
    # 柴米油盐酱醋茶（民生刚需）+ 笔墨纸砚诗酒茶（文教消费）
    tea_tax_coin = float(round(nat_raw["tea_raw"] / 5.0, 1))
    salt_tax_coin = float(round(nat_raw["salt_raw"] / 10.0, 1))
    monopoly_tax_total = tea_tax_coin + salt_tax_coin + export_trade_tax_coin
    sugar_produced = float(round(nat_raw["sugar_cane"] / 3.0, 1))
    paper_produced = float(round(nat_raw["hemp_raw"] * 0.30 / 1.5, 1))
    paper_neutral = paper_produced

    # 松烟炼墨（油墨原料）
    ink_produced = float(round(nat_raw["timber"] * 0.05 * 2.0, 1))

    # 🔴 书籍规范配方：纯耗 纸张 + 油墨（雕版与铜活字为耐用固定资产，非每册消耗品）
    books_printed = float(round(min(paper_neutral * 0.60 / 8.0, (ink_produced * 0.50 / 2.0) if ink_produced > 0 else paper_neutral * 0.60 / 8.0), 1))

    # 笔墨纸砚（文房四宝）：纸张 + 油墨 + 石料（名砚）
    four_treasures_produced = float(round(min(paper_neutral * 0.20 / 4.0, (ink_produced * 0.20 / 2.0) if ink_produced > 0 else 1.0, nat_raw["stone"] * 0.05 / 2.0), 1))

    # 柴米油盐酱醋茶（民生七事产出）
    firewood_produced = float(round(nat_raw["timber"] * 0.20 + nat_raw["coal"] * 0.10, 1))      # 薪炭
    cooking_oil_produced = float(round(nat_raw["hemp_raw"] * 0.10 / 2.0, 1))                     # 食用油（麻油/菜籽油）
    paste_vinegar_produced = float(round(nat_raw["grain"] * 0.02 / 1.5, 1))                     # 酱醋调味品

    # 3. 结果入账与沉淀
    chain_summary = {
        "turn": int(getattr(state, "turn", 0) or 0),
        "raw_materials_produced": nat_raw,
        "outputs": {
            "silk_cloth_pi": silk_cloth_produced,
            "cloth_pi": hemp_cloth_produced,
            "garments_pieces": garments_produced,
            "refined_iron": iron_melted,
            "iron_ingots": iron_ingots_neutral,
            "steel_ingots": steel_ingots_neutral,
            "timber_beams": timber_beams_neutral,
            "machinery_parts": machinery_parts_produced,
            "weapons_pieces": weapons_produced,
            "barges_built": barges_built,
            "gunpowder_jin": gunpowder_produced,
            "firearms_pieces": firearms_produced,
            "refined_copper": copper_refined,
            "copper_ingots": copper_ingots_neutral,
            "coins_minted_guan": coins_minted,
            "tanned_leather_jin": tanned_leather_produced,
            "leather": leather_neutral,
            "saddle_armor_pieces": saddle_armor_produced,
            "fine_china_pieces": fine_china_produced,
            "sugar_jin": sugar_produced,
            "paper_sheets": paper_produced,
            "paper": paper_neutral,
            "ink_jin": ink_produced,
            "books_printed": books_printed,
            "four_treasures_pieces": four_treasures_produced,
            "firewood_dan": firewood_produced,
            "cooking_oil_jin": cooking_oil_produced,
            "paste_vinegar_jin": paste_vinegar_produced,
            "monopoly_tax_coin": monopoly_tax_total,
            "mine_tax_coin": nat_raw.get("mine_tax_coin", 0.0),
        },
        "chains": {
            CHAIN_TEXTILE: {
                "inputs": {"silk_raw": nat_raw["silk_raw"], "hemp_raw": nat_raw["hemp_raw"]},
                "outputs": {"silk_cloth": silk_cloth_produced, "cloth": hemp_cloth_produced, "garments": garments_produced},
            },
            CHAIN_METALLURGY: {
                "inputs": {"iron_ore": nat_raw["iron_ore"], "coal": nat_raw["coal"]},
                "outputs": {"refined_iron": iron_melted, "weapons": weapons_produced},
            },
            CHAIN_MACHINERY: {
                "inputs": {"timber": nat_raw["timber"], "stone": nat_raw["stone"], "refined_iron": iron_melted * 0.20},
                "outputs": {"machinery_parts": machinery_parts_produced, "barges": barges_built},
            },
            CHAIN_GUNPOWDER: {
                "inputs": {"sulfur_niter": nat_raw["sulfur_niter"], "timber": nat_raw["timber"] * 0.10},
                "outputs": {"gunpowder": gunpowder_produced, "firearms": firearms_produced},
            },
            CHAIN_NONFERROUS: {
                "inputs": {"copper_ore": nat_raw["copper_ore"]},
                "outputs": {"refined_copper": copper_refined, "coins_minted": coins_minted},
            },
            CHAIN_LEATHER: {
                "inputs": {"hides_raw": nat_raw["hides_raw"]},
                "outputs": {"tanned_leather": tanned_leather_produced, "saddle_armor": saddle_armor_produced},
            },
            CHAIN_CERAMICS: {
                "inputs": {"clay": nat_raw["clay"], "coal": nat_raw["coal"] * 0.20},
                "outputs": {"fine_china": fine_china_produced, "export_trade_tax_coin": export_trade_tax_coin},
            },
            CHAIN_FOOD_CULTURE: {
                "inputs": {"sugar_cane": nat_raw["sugar_cane"], "hemp_raw": nat_raw["hemp_raw"] * 0.30, "tea_raw": nat_raw["tea_raw"], "grain": nat_raw["grain"] * 0.02},
                "outputs": {
                    "sugar": sugar_produced,
                    "paper": paper_neutral,
                    "ink": ink_produced,
                    "books": books_printed,
                    "four_treasures": four_treasures_produced,
                    "firewood": firewood_produced,
                    "cooking_oil": cooking_oil_produced,
                    "paste_vinegar": paste_vinegar_produced,
                },
            },
        },
    }

    # 🔴 B-4：报表不是账本。产出必须真实入仓（或显式标注"仅报表"），
    #   原料必须先从物理仓扣减——逐笔写入 `chain_summary["stock_settlement"]`。
    chain_summary["stock_settlement"] = _apply_chain_stock_settlement(
        state, chain_summary["outputs"])

    chain_ledger[str(getattr(state, "turn", 0))] = chain_summary

    # 部分现钱增益真实并入国库税入（Jev 裁定方案 A：由各路商人 POP 扑买出资划转，严守 POP 挂载律与 ΔM_ALL == 0）
    if monopoly_tax_total > 0:
        tax_target = int(round(monopoly_tax_total * 0.15))
        prefs = getattr(state, "prefectures", {})
        merchant_pops = []
        if isinstance(prefs, dict):
            for p in prefs.values():
                if isinstance(p, dict) and "pops" in p and isinstance(p["pops"], dict):
                    m = p["pops"].get("商人")
                    if isinstance(m, dict):
                        merchant_pops.append(m)

        actual_paid = 0
        if merchant_pops and tax_target > 0:
            quota_per = tax_target // len(merchant_pops)
            rem = tax_target % len(merchant_pops)
            for i, pop in enumerate(merchant_pops):
                due = quota_per + (rem if i == len(merchant_pops) - 1 else 0)
                cur_w = float(pop.get("wealth", 0.0) or 0.0)
                paid = min(cur_w, float(due))
                if paid > 0:
                    from core.foundation.ledger.pop_bridge import pop_obj_add
                    if pop_obj_add(state, pop, "wealth", -int(paid)) is None:
                        pop["wealth"] = cur_w - paid
                    actual_paid += int(paid)

        if actual_paid > 0:
            treasury_now = float(getattr(state, "treasury", 0) or 0)
            state.treasury = int(round(treasury_now + actual_paid))

    if isinstance(log, list):
        log.append(f"[产业链] 本月八大实体产业链（全面深化升级四大产业链）网络推进：纺织得绢{int(silk_cloth_produced)}匹/被服{int(garments_produced)}领；"
                   f"冶金得熟铁{int(iron_melted)}斤/兵械{int(weapons_produced)}领；机械制构件{int(machinery_parts_produced)}件/漕船{int(barges_built)}艘；"
                   f"军工制火药{int(gunpowder_produced)}斤/火器{int(firearms_produced)}具；铸钱监铸钱{int(coins_minted)}贯；"
                   f"皮具坊得熟皮{int(tanned_leather_produced)}斤/鞍甲{int(saddle_armor_produced)}具；官窑烧瓷{int(fine_china_produced)}件；"
                   f"食货文教得砂糖{int(sugar_produced)}斤/经书{int(books_printed)}部；专卖外贸正税纳现钱{int(monopoly_tax_total)}贯。")

    return chain_summary
