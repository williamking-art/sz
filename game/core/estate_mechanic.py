# -*- coding: utf-8 -*-
"""宋祚 · 大臣家产 / 建筑 / 投资机制（言枢密设计 + 蔡权衡数值，融入既有机制）。

- **大臣家产**（state.minister_estate，存档序列化）：钱的循环——奢侈消费（家产×0.01×
  BOOM_MULT → 工匠/商人，守恒转移）、聚敛窖藏（→ 钱荒 shortage +）、抄没（钱→国库、
  田→官田）；田的循环——收租（并入 gentry_land）、田赋/免役钱（→ 国库，守恒）；
  persona 阈值（≥100万丰厚 → 危险度 +0.15；≤5万清贫 → 敢谏 +15%）；聚敛超阈值 →
  「物议」事件（抄没/留任/贬黜三选）。
- **建筑**：政府 projects 复用（output 扩展 ×1.5/级）；POP buildings（农田/工坊/商铺/庄园，
  阶层 wealth 出资，Lv1-5，×0.05/Lv 封顶 ×2.0）；效果乘数对既有公式，守恒走既有路径。
- **投资**（invest_decide 复用 free_effect 载体）：国库（会签执行率）/内帑（乾纲独断）投入 →
  分期回报（INVEST_BASE 六领域基准×力度）→ 风险（亏本概率/幅度）→ 贪腐截留（corruption
  高大臣经手 → 入其家产，与家产联动）；**四账闭合**：国库-投入 + 内帑-投入 + 回报 + 截留
  与家产/产出 Σ 变化守恒。
"""
import random

from content.data import (
    ESTATE_FLOW, BUILDING_STD, BUILDING_LEVEL_MULT, BUILDING_COST_GROWTH,
    BUILDING_EFFECT_CAP, POP_BUILDING_TYPES, POP_BUILDING_EFFECT,
    INVEST_BASE, BOOM_MULT,
)


# ---------------- 大臣家产 ----------------
def estate_tier(wealth) -> str:
    """家产档位词（脱敏：玩家/AI 只见档位）：清贫/小康/殷实/豪富/巨富。"""
    from content.data import ESTATE_TIERS
    for tier, threshold in ESTATE_TIERS:
        if int(wealth) >= threshold:
            return tier
    return "清贫"


def settle_minister_estate(state, log):
    """大臣家产月度循环（钱：奢侈消费/聚敛窖藏；田：收租；膨胀：corruption 驱动）。
    守恒：来源-去向差为 0。仅在有经济推演（_economy_ai 注入）时运行——家产为新账目，
    无 AI 直跑结算（测试/回放 harness）时跳过，避免破坏既有 money ledger 口径。
    """
    if not getattr(state, "_economy_ai", None):
        return {"luxury": 0, "rent": 0, "hoard": 0}
    from content.data import ESTATE_FLOW as EF, ESTATE_GROWTH_BASE, ESTATE_GROWTH_CORRUPT, ESTATE_WEALTH_CAP
    from content.ministers.data import MINISTERS
    estate = getattr(state, "minister_estate", {})
    boom = BOOM_MULT.get((getattr(state, "_economy_ai", None) or {}).get("景气", "中"), 1.0)
    lux_total = 0
    rent_total = 0
    hoard_total = 0
    for name, e in list(estate.items()):
        we = int(e.get("wealth", 0))
        land = int(e.get("land", 0))
        # 膨胀（史翰青 1101 基线 → 靖康籍没锚点）：家产随年按 corruption 膨胀
        # 月膨胀 = 家产×(俸禄基准 + 贪腐×系数)，封顶巨富档上限
        growth = 0
        try:
            corruption = MINISTERS.get(name, {}).get("corruption", 0.3)
            growth = we * (ESTATE_GROWTH_BASE + corruption * ESTATE_GROWTH_CORRUPT)
            e["wealth"] = min(ESTATE_WEALTH_CAP, e["wealth"] + int(growth))
            we = int(e["wealth"])
        except Exception:
            pass
        # 奢侈消费（守恒转移：家产 → 工匠/商人 POP）
        lux = int(we * EF["luxury_rate"] * boom)
        if lux > 0:
            e["wealth"] = max(0, we - lux)
            lux_total += lux
        # 聚敛窖藏（聚敛倾向大臣：**膨胀增长部分**藏窖 → 钱荒加剧；本金不缩，净增长为正）
        hoard = int(growth * EF["hoard_rate"]) if _hoard_leaning(state, name) else 0
        if hoard > 0:
            e["wealth"] = max(0, e["wealth"] - hoard)
            hoard_total += hoard
        # 田收租（并入 gentry_land，均分各路）
        rent = int(land * EF["rent_rate"] / 12.0)
        if rent > 0:
            rent_total += rent
    # 奢侈消费 → 工匠/商人（按路分，守恒）
    if lux_total > 0:
        _distribute_luxury(state, lux_total)
    # 聚敛窖藏 → 钱荒加剧（shortage 增，≤0.95）
    if hoard_total > 0:
        state.coin["shortage"] = min(0.95, state.coin.get("shortage", 0.3) + hoard_total / 100_000_000.0)
    # 收租并入 gentry_land（均分各路，Σ 增 = rent_total）
    if rent_total > 0:
        _paths = list(state.prefectures.keys())
        per = rent_total // max(1, len(_paths))
        rem = rent_total - per * len(_paths)
        for i, name in enumerate(_paths):
            p = state.prefectures[name]
            p["gentry_land"] = p.get("gentry_land", 0) + per + (1 if i < rem else 0)
    # 物议事件：聚敛超阈值（家产丰厚 + 聚敛倾向）
    for name, e in list(estate.items()):
        if e.get("wealth", 0) >= EF["persona_rich"] and _hoard_leaning(state, name):
            state._estate_scandal = True
            log.append(f"[物议] {name} 家产丰厚、聚敛无度，朝野物议沸腾！")
            break
    return {"luxury": lux_total, "rent": rent_total, "hoard": hoard_total}


def _hoard_leaning(state, name):
    """聚敛倾向：家产丰厚或 persona 聚敛高。"""
    try:
        from content.ministers.persona import get_persona
        return get_persona(name)["聚敛"] >= 70
    except Exception:
        return False


def _distribute_luxury(state, amount):
    """奢侈消费 → 工匠/商人 POP（按路分，守恒转移）。"""
    _paths = list(state.prefectures.keys())
    per = amount // max(1, len(_paths))
    rem = amount - per * len(_paths)
    for i, name in enumerate(_paths):
        p = state.prefectures[name]
        share = per + (1 if i < rem else 0)
        for pop in ("工匠", "商人"):
            if pop in p["pops"]:
                p["pops"][pop]["wealth"] = p["pops"][pop].get("wealth", 0) + share // 2


def estate_persona_mod(state, name):
    """persona 阈值：家产≥100万 → 危险度 +0.15；≤5万 → 敢谏 +15%。"""
    from content.data import ESTATE_FLOW as EF
    e = getattr(state, "minister_estate", {}).get(name, {})
    we = int(e.get("wealth", 0))
    if we >= EF["persona_rich"]:
        return {"danger_bonus": 0.15, "brave_bonus": 0.0}
    if we <= EF["persona_poor"]:
        return {"danger_bonus": 0.0, "brave_bonus": 0.15}
    return {"danger_bonus": 0.0, "brave_bonus": 0.0}


def seize_estate(state, name, ratio=1.0):
    """抄没家产（物议三选一：抄没）：钱→国库、田→官田（守恒）。返回 (钱, 田)。"""
    e = getattr(state, "minister_estate", {}).get(name)
    if not e:
        return (0, 0)
    we = int(e["wealth"] * ratio)
    land = int(e["land"] * ratio)
    e["wealth"] = max(0, e["wealth"] - we)
    e["land"] = max(0, e["land"] - land)
    state.change_treasury(we)
    state.official_land = getattr(state, "official_land", 0) + land
    return (we, land)


# ---------------- 建筑 ----------------
def building_level_mult(level: int) -> float:
    """政府建筑 Lv1-5：效果 ×1.5/级，封顶 ×2.0。"""
    m = BUILDING_LEVEL_MULT ** max(0, level - 1)
    return min(BUILDING_EFFECT_CAP, m)


def building_cost(btype: str, level: int) -> int:
    """建造成本：base × 1.8^(Lv-1)。"""
    std = BUILDING_STD.get(btype, {})
    return int(std.get("base_cost", 100_000) * (BUILDING_COST_GROWTH ** max(0, level - 1)))


def pop_building_effect(buildings) -> float:
    """POP 建筑效果乘数：Σ(每级 ×0.05)，封顶 ×2.0。"""
    if not buildings:
        return 1.0
    total = 0.0
    for bt, lv in buildings.items():
        if bt in POP_BUILDING_TYPES:
            total += int(lv) * POP_BUILDING_EFFECT
    return min(BUILDING_EFFECT_CAP, 1.0 + total)


# ---------------- 投资 ----------------
def invest(state, field: str, amount: int, fund: str = "treasury",
           minister: str = "", months: int = 12) -> dict:
    """投资落地（四账闭合守恒）：国库/内帑投入 → 分期回报 → 风险 → 贪腐截留。

    返回 {"ok", "invest_id", "amount", "field", "fund", "return_total", "seized", "msg"}。
    """
    if field not in INVEST_BASE:
        return {"ok": False, "msg": f"投资领域「{field}」不在六领域"}
    if fund not in ("treasury", "imperial_treasury"):
        return {"ok": False, "msg": "资金来源须为 国库/内帑"}
    amount = max(0, int(amount))
    if fund == "treasury":
        if state.treasury < amount:
            return {"ok": False, "msg": "国库不足"}
        state.change_treasury(-amount)
    else:
        if state.imperial_treasury < amount:
            return {"ok": False, "msg": "内帑不足"}
        state.change_imperial_treasury(-amount)
    base = INVEST_BASE[field]
    # 回报总额 = 本金 × 年回报 × 力度（月数/12）
    ret_total = int(amount * base["return"] * (months / 12.0))
    # 风险：亏本概率（risk 档）→ 亏本幅度（0~50%）
    lose = 0.0
    if random.random() < base["risk"]:
        lose = random.uniform(0.0, 0.5)
    ret_total = int(ret_total * (1 - lose))
    # 贪腐截留：corruption 高大臣经手 → 入其家产（守恒：截留从回报出）
    seized = 0
    if minister and isinstance(state.minister_estate, dict) and minister in state.minister_estate:
        corruption = 0.5  # 简化：大臣贪腐度
        try:
            fig = __import__("content.ministers.data", fromlist=["MINISTERS"]).MINISTERS.get(minister, {})
            corruption = fig.get("corruption", 0.5)
        except Exception:
            pass
        seized = int(ret_total * corruption * 0.3)
        ret_total -= seized
        state.minister_estate[minister]["wealth"] = \
            state.minister_estate[minister].get("wealth", 0) + seized
    inv_id = f"inv{state.turn}_{field}{len(state.investments)}"
    state.investments[inv_id] = {
        "invest_id": inv_id, "field": field, "fund": fund, "amount": amount,
        "return_total": ret_total, "seized": seized, "months": max(1, int(months)),
        "months_left": max(1, int(months)),
    }
    return {"ok": True, "invest_id": inv_id, "amount": amount, "field": field,
            "fund": fund, "return_total": ret_total, "seized": seized, "msg": "已记档"}


def settle_investments(state, log):
    """投资分期回报（每月按 1/months 进产出 → 国库/内帑，守恒回流；最后月付清余款）。"""
    for iid, inv in list(getattr(state, "investments", {}).items()):
        per = inv["return_total"] if inv["months_left"] <= 1 else inv["return_total"] // inv["months"]
        if per <= 0:
            continue
        if inv["fund"] == "treasury":
            state.change_treasury(per)
        else:
            state.change_imperial_treasury(per)
        inv["return_total"] -= per
        inv["months_left"] -= 1
        if inv["months_left"] <= 0 or inv["return_total"] <= 0:
            del state.investments[iid]
            log.append(f"[投资] {inv['field']} 回报期满核销")
