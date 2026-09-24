# -*- coding: utf-8 -*-
"""宋祚 · 结算共享守恒工具（从 settlement_steps.py 拆出，零行为变更）。

资金/人口守恒转移、粮贸配对、贪腐与粮价小工具、P1 档位常量。"""
from __future__ import annotations

from content.data import (
    GRAIN_PRICE_MIN,
    GRAIN_PRICE_MAX,
)

def _state_grain_trade(state, grain_amt: int, direction: str, price: float, log, tag: str) -> tuple:
    """政府粮食交易的守恒配对（审查 P0：杜绝「国库灭钱/太仓凭空得粮」幻影对手）。

    direction='buy'（和籴/入中/平籴——政府买粮入仓）：
        太仓 +grain、国库 -钱；民间（各路农/士绅等存粮 POP）售粮得钱。
        民间存粮不足 → 少买（实际买入量封顶）。
    direction='sell'（平粜/平准粜——政府卖粮收钱）：
        太仓 -grain、国库 +钱；民间买粮付钱（按可支付财富封顶，避免扣成负）。
    钱、粮两组合计 ΣΔ==0（政府仓 ↔ 民间账户成对划转）。
    返回 (实际 grain 量, 实际钱额)；grain 与钱的价格换算用当前 price。
    """
    pools = []
    for _p in getattr(state, "prefectures", {}).values():
        pops = _p.get("pops") if isinstance(_p, dict) else None
        if not isinstance(pops, dict):
            continue
        for pk in ("农", "士绅", "工匠", "商人", "官僚", "兵"):
            pp = pops.get(pk)
            if isinstance(pp, dict):
                pools.append(pp)
    if not pools:
        return 0, 0
    p = max(float(price), 0.1)
    if direction == "buy":
        # 仓容上限：太仓 change_granary 有 cap 封顶，先按余量限购（防钱付了粮被 cap 吞）
        _room = max(0, int(getattr(state, "granary_cap", 1 << 30)) - int(getattr(state, "granary", 0) or 0))
        # 按民间存粮从多到少征购
        total = 0
        money_paid = 0
        remain = min(int(grain_amt), _room)
        # 审查修复（潜伏造币）：原实现先给民间全额记账、再用 max(0, …) 截断国库
        # → 一旦 caller 未保证 money_paid ≤ 国库（新增调用方或价格下限变动），
        # 差额即凭空产生。此处把「国库可付额」提前作为钱腿硬上限，与 _changping_trade 同规。
        _cash_cap = int(getattr(state, "treasury", 0) or 0)
        for pp in sorted(pools, key=lambda x: -int(x.get("grain", 0) or 0)):
            if remain <= 0 or money_paid >= _cash_cap:
                break
            avail = int(pp.get("grain", 0) or 0)
            take = min(remain, avail)
            if take <= 0:
                continue
            if int(take * p) > _cash_cap - money_paid:      # 国库不足则少买
                take = int((_cash_cap - money_paid) / p)
                if take <= 0:
                    break
            pp["grain"] = avail - take
            _pay = int(take * p)
            pp["wealth"] = int(pp.get("wealth", 0) or 0) + _pay
            remain -= take
            total += take
            money_paid += _pay
        if total <= 0:
            return 0, 0
        state.change_granary(total)
        _treasury = getattr(state, "treasury", 0)
        state.treasury = max(0, _treasury - money_paid)
        log.append(f"[{tag}] 民间籴粮入仓 {total}石，散钱 {money_paid}贯与民")
        return total, money_paid
    # sell：按民间财富摊售（有钱才买得起；实际卖出量受民间可支付力限制）
    total = 0
    money_in = 0
    want = int(grain_amt)
    _buyers = [pp for pp in pools if int(pp.get("wealth", 0) or 0) > 0]
    if not _buyers:
        return 0, 0
    _total_w = sum(int(x.get("wealth", 0) or 0) for x in _buyers)
    for pp in _buyers:
        if want <= 0:
            break
        _share = min(1.0, (int(pp.get("wealth", 0) or 0)) / max(_total_w, 1))
        _alloc = min(want, int(grain_amt * _share))
        # 支付能力校验：买 _alloc 石需 _alloc*p 钱，不够则少买
        _can_afford = int((int(pp.get("wealth", 0) or 0)) // p)
        _alloc = min(_alloc, _can_afford)
        if _alloc <= 0:
            continue
        _cost = int(_alloc * p)
        pp["wealth"] = int(pp.get("wealth", 0) or 0) - _cost
        pp["grain"] = int(pp.get("grain", 0) or 0) + _alloc
        total += _alloc
        money_in += _cost
        want -= _alloc
    if total <= 0:
        return 0, 0
    state.change_granary(-total)
    state.treasury = getattr(state, "treasury", 0) + money_in
    log.append(f"[{tag}] 官仓粜粮 {total}石，回收 {money_in}贯")
    return total, money_in


def _changping_trade(pref, name, grain_amt, direction, price, log, tag):
    """州县常平仓粜籴的守恒配对（与 _state_grain_trade 同构；钱腿为本路府库）。

    审查修复背景：常平仓原实现只动 `changping_stock` / `local_treasury` 两个
    政府侧账户 —— 平粜放出的粮无买家（粮凭空消失）、回收的钱无付款方（钱凭空
    产生）；平籴买入的粮无卖家（粮凭空产生）、付出的钱无收款方（钱凭空消失）。
    现改为与本路民间 POP 成对划转，两侧合计 ΣΔ==0：

      direction='buy'（平籴·政府买粮入仓）：
          常平仓 +grain、本路府库 -钱；存粮 POP 售粮得钱。
          受「府库可付额」与「民间可售粮」双重封顶。
      direction='sell'（平粜·政府卖粮收钱）：
          常平仓 -grain、本路府库 +钱；有钱 POP 买粮付钱（按可支付力封顶）。

    返回 (实际粮量, 实际钱额)；两者皆 0 表示本次未成交易（调用方不应记动作）。
    """
    pools = []
    pops = pref.get("pops") if isinstance(pref, dict) else None
    if isinstance(pops, dict):
        for pk in ("农", "士绅", "工匠", "商人", "官僚", "兵"):
            pp = pops.get(pk)
            if isinstance(pp, dict):
                pools.append(pp)
    if not pools:
        return 0, 0
    _price = max(float(price), 0.1)

    if direction == "buy":
        _pay_cap = int(pref.get("local_treasury", 0) or 0)
        total = 0
        money = 0
        remain = int(grain_amt)
        for pp in sorted(pools, key=lambda x: -int(x.get("grain", 0) or 0)):
            if remain <= 0 or money >= _pay_cap:
                break
            avail = int(pp.get("grain", 0) or 0)
            take = min(remain, avail)
            _pay = int(take * _price)
            if _pay > _pay_cap - money:                     # 府库不足则少买
                take = int((_pay_cap - money) / _price)
                _pay = int(take * _price)
            if take <= 0:
                continue
            pp["grain"] = avail - take
            pp["wealth"] = int(pp.get("wealth", 0) or 0) + _pay
            remain -= take
            total += take
            money += _pay
        if total <= 0:
            return 0, 0
        pref["changping_stock"] = int(pref.get("changping_stock", 0) or 0) + total
        pref["local_treasury"] = _pay_cap - money
        log.append(f"[{tag}] {name}平籴入常平 {total}石，散钱 {money}贯与民")
        return total, money

    total = 0
    money = 0
    want = int(grain_amt)
    _buyers = [pp for pp in pools if int(pp.get("wealth", 0) or 0) > 0]
    if not _buyers:
        return 0, 0
    _tw = sum(int(x.get("wealth", 0) or 0) for x in _buyers)
    for pp in _buyers:
        if want <= 0:
            break
        _share = min(1.0, int(pp.get("wealth", 0) or 0) / max(_tw, 1))
        _alloc = min(want, int(grain_amt * _share))
        _alloc = min(_alloc, int(int(pp.get("wealth", 0) or 0) // _price))   # 买得起才买
        if _alloc <= 0:
            continue
        _cost = int(_alloc * _price)
        pp["wealth"] = int(pp.get("wealth", 0) or 0) - _cost
        pp["grain"] = int(pp.get("grain", 0) or 0) + _alloc
        total += _alloc
        money += _cost
        want -= _alloc
    if total <= 0:
        return 0, 0
    pref["changping_stock"] = max(0, int(pref.get("changping_stock", 0) or 0) - total)
    pref["local_treasury"] = int(pref.get("local_treasury", 0) or 0) + money
    log.append(f"[{tag}] {name}常平粜粮 {total}石，回收 {money}贯入府库")
    return total, money


def _levy_men(state, road: str, need: int) -> int:
    """自本路农户、其次流民中征补兵员（人守恒：农/流民 → 兵）。

    审查配套：诏令/事件的整军增兵若只 add_troops，则在 _settle_finance 以
    Σbranches 重聚合兵 POP、并把 ΣPOP 写回 population 之后，会表现为「凭空
    产生人口」（实测量级可达数万）。故增兵须有来源，且不足时按实有截断
    —— 宁少征，不造人。返回实际征得人数。
    """
    if need <= 0:
        return 0
    p = getattr(state, "prefectures", {}).get(road)
    if not isinstance(p, dict):
        return 0
    got = 0
    pops = p.get("pops") or {}
    farmer = pops.get("农") if isinstance(pops, dict) else None
    if isinstance(farmer, dict):
        take = min(need, int(farmer.get("size", 0) or 0))
        if take > 0:
            farmer["size"] = int(farmer.get("size", 0) or 0) - take
            got += take
    if got < need:                                   # 农户不足 → 再征流民
        ref = int(p.get("refugees", 0) or 0)
        take = min(need - got, ref)
        if take > 0:
            p["refugees"] = ref - take
            got += take
    return got


def _return_men(state, road: str, n: int) -> int:
    """裁汰兵力回流本路农户（人守恒：兵 → 农）；无农户时归流民池。

    与 _levy_men 对称：凡减少兵额（裁汰/整编）都应把人丁送回民户，
    否则 _settle_finance 以 Σbranches 重聚合兵 POP 时表现为人口凭空消失。
    """
    if n <= 0:
        return 0
    p = getattr(state, "prefectures", {}).get(road)
    if not isinstance(p, dict):
        return 0
    pops = p.get("pops") or {}
    farmer = pops.get("农") if isinstance(pops, dict) else None
    if isinstance(farmer, dict):
        farmer["size"] = int(farmer.get("size", 0) or 0) + n
    else:
        p["refugees"] = int(p.get("refugees", 0) or 0) + n
    return n


def _collect_from_pops(state, amount: int) -> int:
    """按人口比例向六类 POP 征收 `amount` 贯（买家支付），返回**实收**额。

    用途：把"产出型/外部型入账"改为**守恒转移**——POP 挂载律要求"凡钱必须落在
    POP wealth 或国库/内帑，且来源=去向"。用于修复审查 A-4（畜栏产肉原
    `imperial_treasury += 收入` 无买方 → 凭空造币）。

    语义：按 POP `size` 比例分摊；某池 wealth 不足时**按实收计，不补差额**——
    宁可少收，也绝不凭空造币。两轮征收（第二轮补齐首轮 int 截断余额）以保证
    在余额充足时能收满 `amount`，从而使"扣减额 == 入账额"精确成立。
    """
    amount = int(amount or 0)
    if amount <= 0:
        return 0
    pools = [(pp, float(pp.get("size", 0) or 0))
             for p in state.prefectures.values()
             for pp in (p.get("pops") or {}).values()]
    total_size = sum(sz for _, sz in pools) or 1.0
    taken = 0
    remaining = amount
    for pp, size in pools:                      # 第一轮：按人口比例
        if remaining <= 0:
            break
        if size <= 0:
            continue
        want = min(int(amount * size / total_size), remaining)
        avail = int(pp.get("wealth", 0) or 0)
        got = min(want, avail)
        if got > 0:
            pp["wealth"] = avail - got
            taken += got
            remaining -= got
    for pp, _sz in pools:                       # 第二轮：补齐 int 截断余额
        if remaining <= 0:
            break
        avail = int(pp.get("wealth", 0) or 0)
        got = min(remaining, avail)
        if got > 0:
            pp["wealth"] = avail - got
            taken += got
            remaining -= got
    return taken


def _distribute_cash(state, amount: int, shares: dict) -> int:
    """把 `amount` 贯按 `shares` {阶层: 占比} 精确分发给各路该阶层 POP wealth。

    末位（最后一个阶层 × 最后一支池）吃尾差，保证 **Σ入账 == amount**（精确守恒），
    从而与 `state.change_treasury(-paid)` 构成 `ΣΔ==0` 的守恒转移。
    返回实际分发额。
    """
    amount = int(amount or 0)
    if amount <= 0:
        return 0
    roads = list(state.prefectures.values())
    items = [(c, float(s)) for c, s in (shares or {}).items()]
    paid = 0
    for i, (cls, share) in enumerate(items):
        want = (amount - paid) if i == len(items) - 1 else int(amount * share)
        if want <= 0:
            continue
        pools = [(_p.get("pops") or {}).get(cls) for _p in roads]
        pools = [x for x in pools if isinstance(x, dict)]
        if not pools:
            continue
        _tot = sum(float(x.get("size", 0) or 0) for x in pools) or 1.0
        given = 0
        for j, x in enumerate(pools):
            g = (want - given) if j == len(pools) - 1 else int(
                want * float(x.get("size", 0) or 0) / _tot)
            g = max(0, int(g))
            x["wealth"] = int(x.get("wealth", 0) or 0) + g
            given += g
        paid += given
    return paid


def transfer_public_funds_to_pops(state, amount: int, shares: dict, reason: str,
                                  source_account: str = "treasury") -> int:
    """公共资金（国库/内帑）→ 民间 POP wealth 的**守恒转移**（走 applier_pipeline）。

    用于研发经费、工程款等**新增支出通道**：批量事务 + 路径白名单 + ΣΔ==0 + 原子回滚，
    绝不绕开另起第三套写状态通道（engine/state_applier 铁律）。

    口径：
      · 国库/内帑不足 → 按实付（返回 < amount，调用方须据实记录，不得静默成功）；
      · 接收方池缺失 → 余额退回，仅划转实到部分；
      · 守恒/穿底/落点非法 → applier 整批拒绝 → 返回 0（可诊断，不假装已付）。
    """
    amount = int(amount or 0)
    avail = max(0, int(getattr(state, source_account, 0) or 0))
    amount = min(amount, avail)
    if amount <= 0:
        return 0
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict) or not prefs:
        return 0
    roads = [r for r, p in prefs.items() if isinstance(p, dict)]
    if not roads:
        return 0
    changes = [{"path": source_account, "op": "add", "value": -amount,
                "reason": reason, "source_agent": "settlement"}]
    items = [(c, float(s)) for c, s in (shares or {}).items() if float(s) > 0]
    allocated = 0
    for i, (cls, share) in enumerate(items):
        want = (amount - allocated) if i == len(items) - 1 else int(amount * share)
        if want <= 0:
            continue
        pools = [r for r in roads
                 if isinstance((prefs[r].get("pops") or {}).get(cls), dict)]
        if not pools:
            continue
        given = 0
        for j, r in enumerate(pools):
            v = (want - given) if j == len(pools) - 1 else int(want / len(pools))
            if v <= 0:
                continue
            changes.append({"path": f"prefectures.{r}.pops.{cls}.wealth",
                            "op": "add", "value": v,
                            "reason": reason, "source_agent": "settlement"})
            given += v
        allocated += given
    if allocated <= 0:
        return 0
    changes[0]["value"] = -allocated
    try:
        from engine.state_applier import applier_pipeline
    except Exception:
        return 0
    res = applier_pipeline(state, [("settlement", changes)])
    if not (res.get("applied") or []):
        return 0
    return allocated


_TA = 5 / 3.0          # 大 → 巨 倍率（2.0/1.5）


_TB = 5 / 2.0          # 大 → 极 倍率（2.5/1.5）


def _tier7(v_tiny: int, v_small: int, v_mid: int, v_big: int,
           cap: int = None) -> dict:
    """构造七档换算表（无/微/小/中/大/巨/极）。

    巨/极由大档按 content.data.TIER_RANGE 比例外推；若给出 cap，则一律受其钳制
    （外交 attitude 原 CAP 8、兵额原 CAP 5 万不得因补档而被越过）。
    """
    big_j = int(v_big * _TA)
    big_k = int(v_big * _TB)
    if cap is not None:
        big_j = min(big_j, cap)
        big_k = min(big_k, cap)
    return {"无": 0, "微": v_tiny, "小": v_small, "中": v_mid, "大": v_big,
            "巨": big_j, "极": big_k}


_P1_ATT_DELTA = _tier7(3, 5, 6, 8, cap=8)      # 外交 attitude ±3~±8（CAP 8）


_P1_ARM_DELTA = _tier7(10000, 20000, 35000, 50000, cap=50000)   # 兵额 ±1万~±5万（CAP 5万）


_P1_TRAIN_DELTA = _tier7(2, 3, 5, 6)           # 训练/士气 ±2~±6


_P1_LEVY_COST = _tier7(100000, 200000, 350000, 500000)  # 征发 cost 10万~50万


_P1_RELIEF = _tier7(100000, 200000, 350000, 500000)     # 赈济 10万~50万石


_P1_REFUGEE = _tier7(50000, 120000, 200000, 300000)     # 流民 ±5万~±30万


def _avg_corruption(state):
    """全国理财主官平均贪腐度（后台隐藏，仅影响数值，绝不进 UI 文本）。"""
    names = []
    for org_key in ("户部",):
        o = state.central_orgs.get(org_key)
        if o and o.get("lead"):
            names.append(o["lead"])
    if not names:
        return 0.0
    vals = [state.corruption.get(n, 0.0) for n in names]
    return sum(vals) / len(vals)


def _recalc_region_price(state, name: str, extra_supply: float = 0.0) -> float:
    """按当月供需（年成月均 + 常平净粮流）重算当地粮价（贯/石）。

    价格体系内部允许"文"级精度（1 贯 = 1000 文，即 0.001 贯），
    仅用于价格推导与折银换算；国库/地方府库记账仍为整数贯。
    """
    from content.data import PER_CAPITA_MONTH_GRAIN
    p = state.prefectures.get(name)
    if not p:
        return state.grain_price
    need = p.get("population", 0) * PER_CAPITA_MONTH_GRAIN          # 月需求（石）
    supply = max(p.get("grain", 0) / 12.0 + extra_supply, 0.01)     # 月供应（石）
    ratio = max(0.5, min(2.0, need / supply))
    return max(GRAIN_PRICE_MIN, min(GRAIN_PRICE_MAX, state.grain_price * ratio))


