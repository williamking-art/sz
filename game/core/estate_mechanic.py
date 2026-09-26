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
# POP 挂载律条 4（2026-09-27 迁移完成）：家产的钱**物理上落在 `士绅` POP** 的加法子池：
#   · `prefectures[路].pops["士绅"]["estate"]`        家产持钱（计入 `money.pop_money`）
#   · `prefectures[路].pops["士绅"]["estate_hoard"]`  家产窖藏（计入 `money.hoard_money`）
# `state.minister_estate[name]`（wealth/窖银/land）是**具名镜像**：只作展示、persona 阈值与
# 事件判定用，**不是账本**；唯一写入点就是本模块的这几个助手。
# `sync_estate_slices()` 负责让「Σ镜像 == Σ子池」恒成立（开局物化 / 旧档迁移 / 外部直改兜底）。
_GENTRY = "士绅"


def _prefs(state):
    return getattr(state, "prefectures", {}) or {}


def _gentry_slot(p):
    """取某路的士绅 POP 槽（缺失返回 None，不新建结构）。"""
    pops = p.get("pops") if isinstance(p, dict) else None
    if not isinstance(pops, dict):
        return None
    slot = pops.get(_GENTRY)
    return slot if isinstance(slot, dict) else None


def _rows_with_slice(state, key="estate"):
    """[(路名, 士绅槽)]，且该路子池余额 > 0。"""
    out = []
    for rname, p in _prefs(state).items():
        g = _gentry_slot(p)
        if g is not None and int(g.get(key, 0) or 0) > 0:
            out.append((rname, g))
    return out


def estate_slice_total(state, key="estate") -> int:
    """Σ 士绅 POP 的家产子池（`estate` / `estate_hoard`）——家产的钱**真实所在**。"""
    return sum(int(g.get(key, 0) or 0)
               for p in _prefs(state).values()
               for g in [_gentry_slot(p)] if g is not None)


def _mirror_total(state, mirror_key="wealth") -> int:
    me = getattr(state, "minister_estate", None)
    if not isinstance(me, dict):
        return 0
    return sum(int((v or {}).get(mirror_key, 0) or 0)
               for v in me.values() if isinstance(v, dict))


def _inject_slice(state, amount: int, key="estate") -> int:
    """把 `amount` 注入士绅子池（按各路士绅 wealth 权重分摊，余数归最大路）。返回实注入额。"""
    amount = int(amount)
    if amount <= 0:
        return 0
    rows = [(rname, g) for rname, p in _prefs(state).items()
            for g in [_gentry_slot(p)] if g is not None]
    if not rows:
        return 0
    weights = [max(1, int(g.get("wealth", 0) or 0)) for _r, g in rows]
    top = max(range(len(rows)), key=lambda i: weights[i])
    total = sum(weights)
    got = 0
    for i, (_r, g) in enumerate(rows):
        part = amount - got if i == len(rows) - 1 else int(amount * weights[i] / total)
        if part <= 0:
            continue
        g[key] = int(g.get(key, 0) or 0) + part
        got += part
    if got != amount:      # 拾整尾差并入权重最大路，保证 Σ == amount
        rows[top][1][key] = int(rows[top][1].get(key, 0) or 0) + (amount - got)
        got = amount
    return got


def _withdraw_slice(state, amount: int, key="estate") -> int:
    """从士绅子池扣 `amount`（按各路子池余额权重），返回实扣额（不超过池内总额）。"""
    amount = int(amount)
    if amount <= 0:
        return 0
    rows = _rows_with_slice(state, key)
    pool = sum(int(g.get(key, 0) or 0) for _r, g in rows)
    if pool <= 0:
        return 0
    amount = min(amount, pool)
    taken = 0
    for i, (_r, g) in enumerate(rows):
        have = int(g.get(key, 0) or 0)
        part = min(have, amount - taken if i == len(rows) - 1
                   else int(amount * have / pool))
        if part <= 0:
            continue
        g[key] = have - part
        taken += part
    return taken


def sync_estate_slices(state) -> dict:
    """使「Σ具名镜像 == Σ士绅子池」成立（**幂等**）。返回各轴调整量。

    用途：① 开局把 `ESTATE_INIT` 镜像存量物化进 POP；② 旧档（无子池）载入迁移；
    ③ 外部直改镜像（测试/脚本）后的兜底对齐。正常结算路径下两者始终同步，本函数为 no-op。
    差额为正 → 注入 POP（不凭空消失、也不重复计入 M_ALL）；为负 → 从 POP 回收。
    """
    out = {}
    for key, mirror_key in (("estate", "wealth"), ("estate_hoard", "窖银")):
        delta = _mirror_total(state, mirror_key) - estate_slice_total(state, key)
        if delta > 0:
            _inject_slice(state, delta, key)
        elif delta < 0:
            _withdraw_slice(state, -delta, key)
        out[mirror_key] = delta
    return out


def _estate_income(state, name, src_class: str, want: int) -> int:
    """逐路：`src_class` 的 wealth → 同路士绅 `estate` 子池，镜像同步。返回实转入额。

    守恒：POP 内部转移（阶层间），ΣPOP 与 M_ALL 均不变；按 `ESTATE_WEALTH_CAP` 限幅。
    """
    from content.data import ESTATE_WEALTH_CAP
    e = (getattr(state, "minister_estate", {}) or {}).get(name)
    if not isinstance(e, dict):
        return 0
    want = int(want)
    room = max(0, int(ESTATE_WEALTH_CAP) - int(e.get("wealth", 0) or 0))
    want = min(want, room)
    if want <= 0:
        return 0
    got = 0
    for _r, p in _prefs(state).items():
        if got >= want:
            break
        src = (p.get("pops") or {}).get(src_class)
        g = _gentry_slot(p)
        if not isinstance(src, dict) or g is None:
            continue
        have = int(src.get("wealth", 0) or 0)
        take = min(have, want - got)
        if take <= 0:
            continue
        src["wealth"] = have - take
        g["estate"] = int(g.get("estate", 0) or 0) + take
        got += take
    if got:
        e["wealth"] = int(e.get("wealth", 0) or 0) + got
    return got


def credit_estate(state, name, amount: int) -> int:
    """**外部**收入入家产（投资贪腐截留等）：注入士绅 `estate` 子池 ＋ 镜像（封顶）。"""
    from content.data import ESTATE_WEALTH_CAP
    e = (getattr(state, "minister_estate", {}) or {}).get(name)
    if not isinstance(e, dict):
        return 0
    room = max(0, int(ESTATE_WEALTH_CAP) - int(e.get("wealth", 0) or 0))
    amount = min(int(amount), room)
    if amount <= 0:
        return 0
    got = _inject_slice(state, amount, "estate")
    e["wealth"] = int(e.get("wealth", 0) or 0) + got
    return got


def _estate_spend(state, name, want: int, mode: str = "luxury") -> int:
    """家产支出（逐路，**钱不出 POP**；镜像同步）。返回实支额。

    mode：
      · `luxury`   士绅 `estate` → 同路 `工匠`/`商人` wealth（对半，余数给商人；缺接收方→国库）
      · `treasury` 士绅 `estate` → 国库（抄没）
      · `hoard`    士绅 `estate` → 士绅 `estate_hoard`（窖藏，M_ALL 不变：仍在 M2）
    """
    e = (getattr(state, "minister_estate", {}) or {}).get(name)
    if not isinstance(e, dict):
        return 0
    if mode == "hoard":
        want = min(int(want), int(e.get("wealth", 0) or 0))
        spent = 0
        for _r, g in _rows_with_slice(state, "estate"):
            take = min(int(g.get("estate", 0) or 0), want - spent)
            if take <= 0:
                continue
            g["estate"] = int(g.get("estate", 0) or 0) - take
            g["estate_hoard"] = int(g.get("estate_hoard", 0) or 0) + take
            spent += take
            if spent >= want:
                break
        if spent:
            e["wealth"] = max(0, int(e.get("wealth", 0) or 0) - spent)
            e["窖银"] = int(e.get("窖银", 0) or 0) + spent
        return spent
    # luxury / treasury：按路逐笔支出
    want = min(int(want), int(e.get("wealth", 0) or 0))
    if want <= 0:
        return 0
    spent = 0
    for _r, p in _prefs(state).items():
        if spent >= want:
            break
        g = _gentry_slot(p)
        if g is None:
            continue
        take = min(int(g.get("estate", 0) or 0), want - spent)
        if take <= 0:
            continue
        g["estate"] = int(g.get("estate", 0) or 0) - take
        if mode == "treasury":
            state.change_treasury(take)
        else:
            pops = p.get("pops") or {}
            half = take // 2
            plan = [("工匠", half), ("商人", take - half)]
            paid = 0
            for target, got in plan:
                slot = pops.get(target)
                if isinstance(slot, dict) and got > 0:
                    slot["wealth"] = int(slot.get("wealth", 0) or 0) + got
                    paid += got
            if paid < take:      # 接收方缺失 → 退回国库（钱不凭空消失）
                state.change_treasury(take - paid)
        spent += take
    if spent:
        e["wealth"] = max(0, int(e.get("wealth", 0) or 0) - spent)
    return spent


def estate_tier(wealth) -> str:
    """家产档位词（脱敏：玩家/AI 只见档位）：清贫/小康/殷实/豪富/巨富。"""
    from content.data import ESTATE_TIERS
    for tier, threshold in ESTATE_TIERS:
        if int(wealth) >= threshold:
            return tier
    return "清贫"


def settle_minister_estate(state, log):
    """大臣家产月度循环（钱：奢侈消费/聚敛窖藏；田：收租；膨胀：corruption 驱动）。

    钱的四条腿**全部是 POP 内部/阶层之间的守恒转移**（2026-09-27 迁入 POP 后）：
      膨胀  `官僚.wealth` → 同路 `士绅.estate`        （阶层间转移：ΣPOP、M_ALL 均不变）
      奢侈  `士绅.estate` → 同路 `工匠`/`商人.wealth`  （同上；接收方缺失则退回国库）
      窖藏  `士绅.estate` → `士绅.estate_hoard`       （同 POP 内，钱仍在 M2）
      收租  `农.wealth`   → 同路 `士绅.estate`        （阶层间转移）
    仅在有经济推演（`_economy_ai` 注入）时运行——无 AI 直跑结算（测试/回放 harness）时跳过，
    以免破坏既有 money ledger 口径。
    """
    if not getattr(state, "_economy_ai", None):
        return {"luxury": 0, "rent": 0, "hoard": 0}
    from content.data import ESTATE_FLOW as EF, ESTATE_GROWTH_BASE, ESTATE_GROWTH_CORRUPT
    from content.ministers.data import MINISTERS
    estate = getattr(state, "minister_estate", {})
    if not isinstance(estate, dict):
        return {"luxury": 0, "rent": 0, "hoard": 0}
    sync_estate_slices(state)      # 兜底：外部直改镜像（脚本/测试）后先与子池对齐
    boom = BOOM_MULT.get((getattr(state, "_economy_ai", None) or {}).get("景气", "中"), 1.0)
    lux_total = 0
    rent_total = 0
    hoard_total = 0
    for name, e in list(estate.items()):
        if not isinstance(e, dict):
            continue
        land = int(e.get("land", 0) or 0)
        # 膨胀（史翰青 1101 基线 → 靖康籍没锚点）：月膨胀 = 家产×(俸禄基准 + 贪腐×系数)。
        # 来源 = 官僚 POP wealth 池（逐路转移），池不足/家产封顶则只计实收——禁止凭空铸币。
        corruption = 0.3
        try:
            corruption = MINISTERS.get(name, {}).get("corruption", 0.3)
        except Exception:  # noqa: BLE001
            pass
        want = int(int(e.get("wealth", 0) or 0)
                   * (ESTATE_GROWTH_BASE + corruption * ESTATE_GROWTH_CORRUPT))
        growth = _estate_income(state, name, "官僚", want)
        # 奢侈消费（守恒转移：家产 → 工匠/商人 POP，逐路同路支付）
        lux = _estate_spend(state, name,
                            int(int(e.get("wealth", 0) or 0) * EF["luxury_rate"] * boom),
                            "luxury")
        lux_total += lux
        # 聚敛窖藏（聚敛倾向大臣：**膨胀增长部分**藏窖 → 钱荒加剧；本金不缩）
        hoard = 0
        if _hoard_leaning(state, name):
            hoard = _estate_spend(state, name, int(growth * EF["hoard_rate"]), "hoard")
            hoard_total += hoard
        # 田收租（B4 修复口径不变）：由农 POP wealth 缴纳，按家产封顶剩余限幅，收不足只计实收
        rent = _estate_income(state, name, "农", int(land * EF["rent_rate"] / 12.0))
        rent_total += rent
    # 聚敛窖藏 → 钱荒加剧（shortage 增，≤0.95）
    if hoard_total > 0:
        state.coin["shortage"] = min(0.95, state.coin.get("shortage", 0.3) + hoard_total / 100_000_000.0)
    # 物议事件：聚敛超阈值（家产丰厚 + 聚敛倾向）
    for name, e in list(estate.items()):
        if (isinstance(e, dict) and e.get("wealth", 0) >= EF["persona_rich"]
                and _hoard_leaning(state, name)):
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
    """抄没家产（物议三选一：抄没）：钱→国库、田→官田（守恒）。返回 (钱, 田)。

    钱的口径（2026-09-27 迁移后）：从 `士绅.estate` 子池**逐路扣出 → 国库**
    （POP → 政府，M_ALL 不变）；`state.minister_estate` 镜像同步递减。
    """
    e = getattr(state, "minister_estate", {}).get(name)
    if not e:
        return (0, 0)
    sync_estate_slices(state)      # 家产钱已被外部直改镜像时先对齐子池
    land = int(int(e.get("land", 0) or 0) * ratio)
    we = _estate_spend(state, name, int(int(e.get("wealth", 0) or 0) * ratio), "treasury")
    e["land"] = max(0, int(e.get("land", 0) or 0) - land)
    # 审查修复（田账消失）：原写 state.official_land —— GameState 并无该属性，
    # 等于凭空造一个**顶层私有属性**（存档不落、也无任何消费方读取），抄没的田
    # 就此蒸发。真账在 prefectures[*].official_land（见 settlement 官田分成读取处）。
    # 因家产不记籍贯，此处按「现有官田最多之路」入账（无官田则入首路），使田可被
    # 继续耕作、参与分成；并记统计备审计。
    if land > 0:
        prefs = getattr(state, "prefectures", {}) or {}
        if prefs:
            _home = max(prefs.items(),
                        key=lambda kv: int((kv[1] or {}).get("official_land", 0) or 0))[0]
            prefs[_home]["official_land"] = (
                int(prefs[_home].get("official_land", 0) or 0) + land)
            try:
                state.statistics["seized_land"] = int(
                    state.statistics.get("seized_land", 0) or 0) + int(land)
            except Exception:
                pass
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
    if amount <= 0:
        return {"ok": False, "msg": "投资额须为正整数"}
    # 审查 P2-19 修复：months 原无校验，可放大回报（months=1200 → 回报≈本金×8，
    # 且回报无条件 change_treasury 入账 → 凭空铸币）。与 AI 契约口径（3~60 月）对齐。
    # 注：本函数当前尚无生产调用方（invest_decide 契约未接线），接线前须一并落实
    # 「回报来源守恒」（回报应来自产出端，而非国库→国库自增）。
    try:
        months = int(months)
    except (TypeError, ValueError):
        months = 12
    months = max(3, min(60, months))
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
    # 贪腐截留：corruption 高大臣经手 → 入其家产（守恒：截留从回报出，外部收益分流进 POP）
    seized = 0
    if minister and isinstance(state.minister_estate, dict) and minister in state.minister_estate:
        corruption = 0.5  # 简化：大臣贪腐度
        try:
            fig = __import__("content.ministers.data", fromlist=["MINISTERS"]).MINISTERS.get(minister, {})
            corruption = fig.get("corruption", 0.5)
        except Exception:
            pass
        seized_want = int(ret_total * corruption * 0.3)
        if seized_want > 0:
            ret_total -= seized_want
            # 家产封顶未入账的部分**留在回报里**（不凭空消失），入账的注入士绅 `estate` 子池
            seized = credit_estate(state, minister, seized_want)
            ret_total += seized_want - seized
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
        # 审查修复（永久滞留）：return_total 小于期数时整数除得 0，原 `continue`
        # 使该条目既不递减期数也不核销 → 永久留在 state.investments。
        # 现：末期一次付清余款；非末期按 0 计但仍递减期数，期满核销（余款不足
        # 一贯者明确记账丢弃，不静默留存）。
        if per <= 0 and inv["months_left"] <= 1:
            per = int(inv["return_total"])
        if per <= 0:
            inv["months_left"] -= 1
            if inv["months_left"] <= 0:
                _left = int(inv.get("return_total", 0) or 0)
                del state.investments[iid]
                log.append(f"[投资] {inv['field']} 期满核销"
                           + (f"（余款不足一贯，未付 {_left}）" if _left else ""))
            continue
        # 审查 P2-19 标注：投资回报属**外部经营收益**（与市舶关税 / 榷场月入同源的
        # 「外部钱入」），非国库→国库自增；此处按外部来源记账（statistics.invest_return）
        # 以便审计。⚠️ 接线前置条件：`invest()` 目前无生产调用方（见
        # core.agent_router.PENDING_CONTRACTS「_invest_ai」），接线前须先落实
        # 「回报来源上限」或明确外部收益口径。
        if inv["fund"] == "treasury":
            state.change_treasury(per)
        else:
            state.change_imperial_treasury(per)
        try:
            state.statistics["invest_return"] = int(
                state.statistics.get("invest_return", 0) or 0) + int(per)
        except Exception:
            pass
        inv["return_total"] -= per
        inv["months_left"] -= 1
        if inv["months_left"] <= 0 or inv["return_total"] <= 0:
            del state.investments[iid]
            log.append(f"[投资] {inv['field']} 回报期满核销")
