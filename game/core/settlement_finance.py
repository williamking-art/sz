# -*- coding: utf-8 -*-
"""宋祚 · 财政与货币信用（从 settlement_steps.py 拆出，零行为变更）。

银行信贷、交子界制、熔铜、稳定器回收、税收与积欠、存款存量收敛。"""
from __future__ import annotations

import random

from content.data import (
    COMMERCE_TAX_RATE_MIN,
    COMMERCE_TAX_RATE_MAX,
    TAX_COEFF_MIN,
    TAX_COEFF_MAX,
    TAX_POLL_RATIO,
    COMMERCE_TAX_RATE_DEFAULT,
    PAY_CASH_BASE,
    MONTHLY_EXP_CIVIL_BASE,
    SUI_GONG_ANNUAL,
    ARREARS_COLLECT_RATE,
    OFFICIAL_SERVICE_TAX_RATIO,
)

from core.settlement_econ_helpers import (
    _distribute_pop_wealth,
)

def _refresh_jiaozi_credit(state, log):
    """刷新交子数据契约读数（第二节§2）：流通额 / 兑付率 / 折价 / 挤兑压力。

    **守恒**：本函数不移动任何 POP/国库/内帑/银行账户 —— ΔW == ΔM_ALL == 0，
    只把「发行额 × 接受度」的既有派生量显式落为 `jiaozi["circulating"]`，使**发行额**
    与**流通额**在数据层可区分；折价/挤兑由「兑付率不足 × 信用不足」派生，损失由持券者
    承担（有效交子余额按 trust 缩水，货币供给实际收缩，不凭空补足）。
    """
    from content.data import JIAOZI_RUN_RESERVE_LINE, JIAOZI_RUN_TRUST_LINE
    jz = state.jiaozi
    issued = float(jz.get("issued", 0) or 0)
    trust = max(0.0, min(100.0, float(jz.get("trust", 0) or 0)))
    circulating = int(issued * trust / 100.0)          # 流通额 = 发行额 × 接受度
    reserve = float(jz.get("reserve", 0) or 0)
    redeem_rate = (reserve / circulating) if circulating > 0 else 1.0
    discount = 0.0
    run_pressure = 0.0
    if issued > 0:
        discount = max(0.0, min(1.0, (1.0 - min(1.0, redeem_rate)) * (1.0 - trust / 100.0)))
        run_pressure = max(0.0, min(1.0,
            (1.0 if redeem_rate < JIAOZI_RUN_RESERVE_LINE else 0.0) * 0.5
            + max(0.0, JIAOZI_RUN_TRUST_LINE - trust) / max(JIAOZI_RUN_TRUST_LINE, 1e-9) * 0.5))
    jz["circulating"] = circulating
    jz["redeem_rate"] = round(redeem_rate, 6)
    jz["discount"] = round(discount, 6)
    jz["run_pressure"] = round(run_pressure, 6)
    jz["credit_ceiling"] = round(trust / 100.0, 6)
    if discount > 0 or run_pressure > 0:
        log.append(f"[交子] 流通 {circulating:,}贯 兑付率 {redeem_rate:.2f} "
                   f"折价 {discount:.0%} 挤兑压力 {run_pressure:.0%}")
    return {"circulating": circulating, "redeem_rate": redeem_rate,
            "discount": discount, "run_pressure": run_pressure}


def _settle_bank_credit(state, log):
    """银行信贷月度结算（第二节§3）：吸储 / 放贷 / 收息 / 坏账，**全部守恒转移**。

    守恒（函数内自断言，失败抛错 → 由上层事务回滚，绝不静默成功）：
      - 吸储：POP wealth −= D，bank.reserve += D          ⇒ ΔM_ALL == 0
      - 放贷：POP wealth += L，bank.reserve −= L          ⇒ ΔM_ALL == 0
              （贷款同时形成**债权** loans 与**借款方资产** POP wealth）
      - 收息：POP wealth −= I，bank.reserve += I          ⇒ ΔM_ALL == 0
              （利息归**银行留存**，明确不入国库、不作财政收入）
      - 坏账：bank.reserve −= W + register_flow(burn)      ⇒ ΔM_ALL == −W（去向明确）
    信用传导（第二节§4）：交子挤兑压力↑ → 逾期率↑ → 可贷额↓（信贷收缩）。
    """
    from content.data import (
        BANK_DEPOSIT_MONTH_SHARE,
        BANK_LOAN_MONTH_SHARE,
        BANK_LOAN_RATE,
        BANK_RESERVE_RATIO_MIN,
    )

    from core.money import m_all as _m_all
    from core.money import register_flow as _reg_flow
    from core import institution as _inst
    b = state.bank
    if not bool(b.get("established", False)):
        return {"ok": True, "skipped": "银行未设"}
    # 五个旋钮经既有「编制改革接口」取值（玩家诏令 / AI 提案可改；缺省回退常量）
    RATIO = _inst.get(state, "didang_reserve_ratio", BANK_RESERVE_RATIO_MIN)
    RATE = _inst.get(state, "didang_loan_rate", BANK_LOAN_RATE)
    LEND = _inst.get(state, "didang_loan_share", BANK_LOAN_MONTH_SHARE)
    DEP = _inst.get(state, "didang_deposit_share", BANK_DEPOSIT_MONTH_SHARE)
    CAP = _inst.get(state, "didang_deposit_cap", 0.30)
    mall0 = _m_all(state)
    # 信用信心：交子挤兑压力越大，信贷越收缩、违约越多（§4 传导链）
    trust_conf = 1.0
    try:
        from core.money import jiaozi_run_pressure as _jz_run
        trust_conf = 1.0 - max(0.0, min(1.0, float(_jz_run(state))))
    except Exception:  # noqa: BLE001 — 只读派生失败不阻断结算
        trust_conf = 1.0
    target = str(b.get("target") or "")
    pop_name = target if target in ("农", "士绅", "工匠", "商人", "官僚", "兵") else "商人"

    # ---- 1) 坏账核销（先于放贷，防坏账继续计息）----
    bad_debt = 0
    loans0 = int(b.get("loans", 0) or 0)
    overdue = max(0.0, min(1.0, float(b.get("overdue_rate", 0) or 0) * 0.5
                            + 0.005 + 0.30 * (1.0 - trust_conf)))
    b["overdue_rate"] = round(overdue, 6)
    reserve = int(b.get("reserve", 0) or 0)
    if loans0 > 0 and overdue > 0:
        bad_debt = int(min(loans0, int(loans0 * overdue), reserve))
        if bad_debt > 0:
            b["loans"] = loans0 - bad_debt
            reserve -= bad_debt
            b["reserve"] = reserve
            _reg_flow(state, "burn", bad_debt, "银行贷款坏账核销")
            state.statistics["bank_bad_debt"] = state.statistics.get("bank_bad_debt", 0) + bad_debt
            log.append(f"[银行] 坏账核销 {bad_debt:,}贯（准备金承担，不入国库）")

    # ---- 目标阶层 POP 池 ----
    pools, total_w = [], 0
    for _p in state.prefectures.values():
        slot = (_p.get("pops") or {}).get(pop_name)
        if isinstance(slot, dict):
            w = int(slot.get("wealth", 0) or 0)
            if w > 0:
                pools.append(slot)
                total_w += w

    # ---- 2) 吸储（POP wealth → 准备金；存款为银行负债 memo）----
    # 饱和上限（2026-09-19 压力测试修复）：原按月 5% **无上限**，240 月复利后把民间
    # wealth 抽走 1.46 亿贯（货币退出流通、放贷萎缩）。现按"存款 ≤ 目标阶层财富 × CAP"封顶。
    _cap_total = int(total_w * CAP) if total_w > 0 else 0
    _room = max(0, _cap_total - int(b.get("deposits", 0) or 0))
    deposit = int(min(total_w * DEP, _room)) if total_w > 0 else 0
    if deposit > 0:
        _taken = 0
        for slot in pools:
            w = int(slot.get("wealth", 0) or 0)
            take = min(int(deposit * w / max(total_w, 1)), w)
            slot["wealth"] = w - take
            _taken += take
        if _taken > 0:
            reserve += _taken
            b["reserve"] = reserve
            b["deposits"] = int(b.get("deposits", 0) or 0) + _taken
            log.append(f"[银行] 吸收{pop_name}存款 {_taken:,}贯（入准备金，非铸币）")

    # ---- 3) 放贷（准备金 → 借款方资产；同时记债权；比例/准备金率/信心三重约束）----
    loan = 0
    req = int(int(b.get("deposits", 0) or 0) * max(BANK_RESERVE_RATIO_MIN, RATIO))
    lendable = max(0, reserve - req)
    if lendable > 0 and pools:
        _pool_now = sum(int(s.get("wealth", 0) or 0) for s in pools)
        _want = int(min(lendable, int(reserve * LEND * trust_conf)))
        if _want > 0 and _pool_now > 0:
            _lent = 0
            for slot in pools:
                w = int(slot.get("wealth", 0) or 0)
                add = int(_want * w / _pool_now)
                slot["wealth"] = w + add
                _lent += add
            if _lent > 0:
                loan = _lent
                reserve -= _lent
                b["reserve"] = reserve
                b["loans"] = int(b.get("loans", 0) or 0) + _lent
                log.append(f"[银行] 放贷 {_lent:,}贯与{pop_name}（债权=借款方资产）")

    # ---- 4) 收息（借款方财富 → 准备金；归银行留存，不入国库）----
    interest = 0
    _loans_now = int(b.get("loans", 0) or 0)
    if _loans_now > 0 and pools:
        _pool_now = sum(int(s.get("wealth", 0) or 0) for s in pools)
        _want = min(int(_loans_now * RATE), _pool_now)
        if _want > 0 and _pool_now > 0:
            for slot in pools:
                w = int(slot.get("wealth", 0) or 0)
                take = min(int(_want * w / _pool_now), w)
                slot["wealth"] = w - take
                interest += take
            if interest > 0:
                reserve += interest
                b["reserve"] = reserve
                state.statistics["bank_interest_income"] = (
                    state.statistics.get("bank_interest_income", 0) + interest)
                log.append(f"[银行] 收息 {interest:,}贯（归银行留存，不作财政收入）")

    # ---- 5) 挤兑压力（准备金不足兑付存款 + 信用不足 → 压力）----
    req_all = int(int(b.get("deposits", 0) or 0) * BANK_RESERVE_RATIO_MIN)
    b["run_pressure"] = round(max(0.0, min(1.0,
        (1.0 - trust_conf) * 0.5
        + (1.0 if int(b.get("reserve", 0) or 0) < req_all else 0.0) * 0.5)), 6)

    # ---- 守恒断言（失败不得静默；抛错由上层原子回滚）----
    mall1 = _m_all(state)
    if abs((mall1 - mall0) + bad_debt) > 1:
        raise AssertionError(
            f"银行信贷货币账本断裂：ΔM_ALL={mall1 - mall0:+,.0f}"
            f"（应等于 −坏账 {-bad_debt:+,.0f}）")
    return {"ok": True, "deposit": deposit, "loan": loan,
            "interest": interest, "bad_debt": bad_debt}


def _settle_jiaozi_term(state, log):
    """交子界制：满一界换发新钞（5% 工墨费销毁）+ 超界作废（销币，抑通胀）。

    守恒：销毁额 = issued × JIAOZI_REDEEM_FEE（退出流通，不入任何账户）；
    换界不新增发行（以旧换新，issued 保持流通额）。
    """
    from content.data import JIAOZI_TERM, JIAOZI_REDEEM_FEE
    jz = state.jiaozi
    if jz.get("issued", 0) <= 0:
        return
    jz["age"] = jz.get("age", jz.get("term_progress", 0)) + 1
    if jz["age"] < JIAOZI_TERM:
        return
    # 到界：换发新钞，5% 工墨费销毁（销币），issued 缩水；统计留痕
    _burn = int(jz["issued"] * JIAOZI_REDEEM_FEE)
    jz["issued"] = max(0, jz["issued"] - _burn)
    jz["cycle"] = jz.get("cycle", 0) + 1
    jz["age"] = 0
    jz["redeemed_total"] = jz.get("redeemed_total", jz.get("burned_total", 0)) + _burn
    state.statistics["jiaozi_redeemed"] = state.statistics.get("jiaozi_redeemed", 0) + _burn
    # 注：jiaozi["issued"] 是**负债科目、不在 ACCOUNTS**，销毁不改变 M_ALL——
    # 故此处**不登记** register_flow（登记会在每界凭空制造 +burn 正残差）。
    log.append(f"[交子] 第{jz['cycle']}界届满，换发新钞，工墨费销毁 {_burn}贯（销币抑价）")


def _settle_coin_melt(state, log):
    """私铸熔化真实化：民间铜钱逐月真实熔化扣减（退出流通，抑通胀）。

    各 POP wealth 按 MELT_RATE 比例扣减（0.1%/月）；扣减额**转入熔铜池**
    （state.coin["melted_pool"]，钱变铜料，守恒成立不凭空消失）；熔铜池**不在
    money 公式**（calc_price_level 只加 pop_wealth/treasury/imperial/jiaozi/silver），
    故真实退出流通；熔铜池供铸钱（_settle_mint 从池取料，闭环）。
    不碰国库/内帑（国家持币不熔化）。
    """
    # 审查修复（A1）：COPPER_RESOURCE_DIM 只在 _settle_mint 内局部导入，本函数
    # 熔铜池溢出分支（下方 >1 亿贯）却直接使用该名 → 一旦触发即 NameError，
    # 中断整月结算。此处与 _settle_mint 一致一并导入。
    from content.data import MELT_RATE, COPPER_RESOURCE_DIM
    if MELT_RATE <= 0:
        return
    _melted = 0
    for p in state.prefectures.values():
        for pop in p.get("pops", {}).values():
            w = float(pop.get("wealth", 0))
            if w > 0:
                _take = int(w * MELT_RATE)
                if _take > 0:
                    pop["wealth"] = max(0, w - _take)
                    _melted += _take
    if _melted > 0:
        # 熔铜池：钱变铜料（守恒），不在 money 公式（退出流通）
        # 注：此为 M_ALL 内部转移（POP wealth 减少 = melted_pool 增加，ΔM_ALL == 0），
        # **不是真实销毁**，故不登记 register_flow。真实销毁只在铜料真正离库时发生
        # （_settle_mint 消耗 resources["铜"] 或建筑消耗），届时由调用方登记。
        state.coin["melted_pool"] = state.coin.get("melted_pool", 0) + _melted
        state.statistics["coin_melted"] = state.statistics.get("coin_melted", 0) + _melted
        # 熔铜池出口（备选·蔡权衡）：池 > 阈值（1 亿贯）→ 自动入 resources["铜"]
        # （防只进不出；铜料可被铸钱/建筑消耗回流）
        _pool = state.coin.get("melted_pool", 0)
        if _pool > 100_000_000:
            _overflow = _pool - 100_000_000
            state.coin["melted_pool"] = 100_000_000
            _res = getattr(state, "resources", None)
            if _res is None:
                _res = {}
                state.resources = _res
            # 审查修复（schema 破坏 + 口径断链）：原写 _res["铜"] = int，而
            # state.resources 的 schema 是 {dim: {"stock","cap"}} → 引入非 dict 值，
            # 任何 resources[x]["stock"] 形式的访问一旦命中即崩；且 "铜" 不在
            # RESOURCE_DIMS、铸钱侧只认 COPPER_RESOURCE_DIM(=iron) → 该铜料
            # 永不会被消耗。现并入铸钱所用铜料维（按 cap 截断，余量留池）。
            _slot = _res.get(COPPER_RESOURCE_DIM)
            if not isinstance(_slot, dict):
                _slot = {"stock": 0, "cap": 0}
                _res[COPPER_RESOURCE_DIM] = _slot
            _cap = int(_slot.get("cap", 0) or 0)
            _cur = int(_slot.get("stock", 0) or 0)
            _room = max(0, _cap - _cur) if _cap > 0 else _overflow
            _taken = min(_overflow, _room)
            _slot["stock"] = _cur + _taken
            # 未入仓者仍留熔铜池（不凭空消失）
            state.coin["melted_pool"] = 100_000_000 + (_overflow - _taken)
            state.statistics["copper_recycled"] = (
                state.statistics.get("copper_recycled", 0) + _taken)
        log.append(f"[私铸] 民间铜钱熔化 {_melted}贯（铸器外流，入熔铜池）")


# 兼容别名（并行契约曾用 _settle_melt_copper/_settle_jiaozi_cycle；保留双向可用）

_settle_jiaozi_cycle = _settle_jiaozi_term


_settle_melt_copper = _settle_coin_melt


def _settle_stabilizer_recycle(state, log):
    """稳定器净回收公式（T9 定稿·蔡权衡）：月销币目标 = money × (price−1.2)/price × 0.5。

    通道联动：平粜吸钱入 local_treasury（货币回收，不碰内帑）→ 评估回收目标达成度；
    local_treasury 不在 money 公式（calc_price_level 只计 pop_wealth+treasury+imperial），
    故平粜回收**真实退出流通**（不回流物价公式），是纯销币通道。
    """
    from content.data import STABILIZER_RECYCLE_RATE, CHANGPING_PRICE_TARGET_LOW
    _price = state.grain_price
    if _price <= CHANGPING_PRICE_TARGET_LOW:
        return
    # 回收目标只基于**民间持币**（POP wealth）——内帑/国库膨胀不触发回收（T9 定稿：
    # 内帑抽流通不影响物价公式分母，故不参与销币目标；民间购买力才是通胀之源）。
    _money = 0.0
    for _p in state.prefectures.values():
        for _pop in _p.get("pops", {}).values():
            _money += max(0.0, float(_pop.get("wealth", 0)))
    _target = int(_money * (_price - CHANGPING_PRICE_TARGET_LOW) / max(_price, 1e-6) * STABILIZER_RECYCLE_RATE)
    if _target <= 0:
        return
    # 评估：本月经常平平粜实际回收（local_treasury 增量）——仅记录达成度（不强制追平，
    # 由粜量扩容与交子换界/熔化通道共同作用；物价封顶由 calc_price_level 的 PRICE_CEIL_HARD 保证）
    _recycled = int(getattr(state, "_stabilizer_recycled", 0) or 0)
    state.statistics["stabilizer_target"] = state.statistics.get("stabilizer_target", 0) + _target
    state.statistics["stabilizer_recycled"] = state.statistics.get("stabilizer_recycled", 0) + _recycled
    if _recycled >= _target:
        log.append(f"[稳定器] 净回收目标 {_target}贯已达成（销币抑价）")


def _settle_treasury(state, log):
    """国库结算——**占位（无操作）**：国库收支已在 Step 4（_settle_finance）完成。

    保留空实现仅为维持 settlement 主流程的步骤编号（Step 5）与导入稳定性；
    此处不得再写任何财政逻辑（避免与 Step 4 重复计征）。
    """
    return None


def _settle_tax_grain_sale(state, p, need: int) -> int:
    """农户「粜粮完税」：现金不足时向本路 `士绅`/`商人` 卖粮换钱，用于缴纳当期税。

    ## 为什么需要它（历史↔游戏性取中）

    实证：农户 POP 现金恒低于「1 月口粮折价 × 保底系数」，于是**役钱与自耕田折色
    全部记为欠税且永不回收**（60 月累计农欠税 4,399 万贯）——农税通道整体是死账。
    这既不史实（免役钱、二税折色本是**现钱**之征，农户卖粮完税是常态），
    也不好玩（"三冗 → 加征 → 民怨"这条链在农户一侧根本传导不到）。

    ## 守恒（两条同时成立）

    - **钱**：`士绅/商人.wealth → 农.wealth`，Σ钱 不变，`ΔM_ALL == 0`（不造币）；
    - **粮**：`农.grain → 士绅/商人.grain`，Σ粮 不变（不凭空生粮）。

    买主是**豪强/粮商**（史实如此），不是朝廷——所以它不是"国库自己给自己付钱"的循环。

    ## 约束

    - 仅在**现金不足**时触发，且只补当期缺口；
    - 卖后须留 `FARMER_TAX_GRAIN_KEEP_MONTHS` 个月口粮；
    - 单月最多卖农存粮的 `TAX_GRAIN_SALE_MAX_SHARE`。

    返回实际换得、可用于缴税的现钱（贯）。
    """
    from content.data import (FARMER_TAX_GRAIN_KEEP_MONTHS, PER_CAPITA_MONTH_GRAIN,
                              TAX_GRAIN_SALE_ENABLED, TAX_GRAIN_SALE_MAX_SHARE)

    if not TAX_GRAIN_SALE_ENABLED or need <= 0:
        return 0
    pops = p.get("pops") or {}
    farm = pops.get("农")
    if not isinstance(farm, dict):
        return 0
    price = float(getattr(state, "grain_price", 1.0) or 1.0)
    if price <= 0:
        return 0

    keep = int(int(farm.get("size", 0) or 0) * PER_CAPITA_MONTH_GRAIN
               * FARMER_TAX_GRAIN_KEEP_MONTHS)
    cap_month = int(int(farm.get("grain", 0) or 0) * TAX_GRAIN_SALE_MAX_SHARE)
    sellable = max(0, min(int(farm.get("grain", 0) or 0) - keep, cap_month))
    if sellable <= 0:
        return 0

    # 卖多少粮够补缺口
    want_grain = int(need / price) + 1
    grain = min(sellable, want_grain)
    if grain <= 0:
        return 0

    # 买方：本路 士绅 ＋ 商人，按持钱比例（买不起则按实际成交）
    buyers = [(k, pops.get(k)) for k in ("士绅", "商人")]
    buyers = [(k, b) for k, b in buyers if isinstance(b, dict) and int(b.get("wealth", 0) or 0) > 0]
    if not buyers:
        return 0
    avail = sum(int(b.get("wealth", 0) or 0) for _, b in buyers)
    cost = min(int(grain * price), avail)
    grain = min(grain, int(cost / price))
    if grain <= 0 or cost <= 0:
        return 0

    # 分钱（末位吃尾差，Σ付出 == cost）；分粮（末位吃尾差，Σ得粮 == grain）
    paid = 0
    gave = 0
    n = len(buyers)
    for i, (_k, b) in enumerate(buyers):
        pay = (cost - paid) if i == n - 1 else int(cost * int(b.get("wealth", 0) or 0) / max(1, avail))
        pay = max(0, min(pay, int(b.get("wealth", 0) or 0)))
        g = (grain - gave) if i == n - 1 else int(grain * int(b.get("wealth", 0) or 0) / max(1, avail))
        g = max(0, g)
        b["wealth"] = int(b.get("wealth", 0) or 0) - pay
        b["grain"] = int(b.get("grain", 0) or 0) + g
        paid += pay
        gave += g

    # 若因逐户封顶导致实际成交少于计划：以实际为准（粮随钱走，双向精确守恒）
    if gave > grain:
        gave = grain
    farm["grain"] = int(farm.get("grain", 0) or 0) - gave
    farm["wealth"] = int(farm.get("wealth", 0) or 0) + paid
    state.statistics["tax_grain_sale"] = state.statistics.get("tax_grain_sale", 0) + paid
    state.granary_stats["tax_grain_sold"] = \
        state.granary_stats.get("tax_grain_sold", 0) + gave
    return paid


def _settle_arrears_repayment(state, log):
    """结余**补发积欠**（史实：丰年补发积欠俸饷）。

    为什么需要：取中校准后国帑在长局中转为丰裕（240 月 4,682 万贯），而
    `statistics["pay_arrears"]`（按实付产生的欠饷欠俸）仍在**单向累积** ——
    「国库满、军队欠饷」是玩家一眼能看出的自相矛盾。史实上朝廷在宽裕时确实补发积欠。

    守恒：**国库 → 兵/官僚 POP `wealth`**，纯转移（`ΔM_ALL == 0`），不造币；
    同时按同一比例冲减各军 `ArmyUnit.arrears`，保持「Σ各军欠饷 ↔ `pay_arrears`」同源。

    仅动用**超出应急安全库存**的结余，且单月只补 `ARREARS_REPAY_SHARE`——
    避免"一丰就花光"，也避免把它变成自动清零欠饷的假机制。
    """
    from content.data import ARREARS_KEEP_TREASURY, ARREARS_REPAY_SHARE

    arrears = int(state.statistics.get("pay_arrears", 0) or 0)
    if arrears <= 0:
        return 0
    usable = max(0, int(state.treasury or 0) - int(ARREARS_KEEP_TREASURY))
    amount = int(min(usable * ARREARS_REPAY_SHARE, arrears))
    if amount <= 0:
        return 0

    state.change_treasury(-amount)

    _total_army = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values())
    _total_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values())
    _scale = _total_army + _total_guan
    if _scale <= 0:                      # 无接收方：退回国库，不静默销毁
        state.change_treasury(amount)
        return 0
    _army_amt = int(amount * _total_army / _scale)
    _guan_amt = amount - _army_amt
    # 分配给兵/官僚 POP。权重把"兵总额/官僚总额"的分配与"按 size 摊到各路"**合成一次**，
    # 末位吃尾差 → `Σ入账 == amount` 精确成立（不再有分配残差需要退回国库）。
    _receivers = []
    for _p in state.prefectures.values():
        _b, _g = _p["pops"]["兵"], _p["pops"]["官僚"]
        if _total_army > 0 and int(_b.get("size", 0) or 0) > 0:
            _receivers.append((_b, int(_b["size"]) * _army_amt / _total_army))
        if _total_guan > 0 and int(_g.get("size", 0) or 0) > 0:
            _receivers.append((_g, int(_g["size"]) * _guan_amt / _total_guan))
    _tot_w = sum(_w for _, _w in _receivers)
    if _tot_w <= 0:                      # 无接收方：退回国库，不静默销毁
        state.change_treasury(amount)
        return 0
    _given = 0
    for _i, (_pop, _w) in enumerate(_receivers):
        _gv = (amount - _given) if _i == len(_receivers) - 1 else int(amount * _w / _tot_w)
        _gv = max(0, _gv)
        _pop["wealth"] = int(_pop.get("wealth", 0) or 0) + _gv
        _given += _gv

    # 冲减各军欠饷（同源同减；军饷欠额大，按剩余欠饷比例摊还）
    _unit_due = {}
    for _u in state.army_units:
        _d = float(getattr(_u, "arrears", 0) or 0)
        if _d > 0:
            _unit_due[_u.unit_id or id(_u)] = _d
    _due_total = sum(_unit_due.values())
    if _due_total > 0:
        for _u in state.army_units:
            _k = _u.unit_id or id(_u)
            if _k in _unit_due:
                _u.arrears = max(0, int(getattr(_u, "arrears", 0))
                                 - int(_army_amt * _unit_due[_k] / _due_total))

    state.statistics["pay_arrears"] = max(0, arrears - amount)
    state.statistics["arrears_repaid"] = state.statistics.get("arrears_repaid", 0) + amount
    log.append(f"[补发] 帑藏稍丰，补发积欠 {amount:,} 贯"
               f"（欠饷余额 {state.statistics['pay_arrears']:,}）")
    return amount


def _settle_finance(state, log):
    """月度税收与支出结算。国库只收货币税（工商+丁口）+ 一条鞭折银 + 折变；
    田赋本色为实物入粮仓。支出含折色俸禄（随 pay_system）与岁币岁赐。"""
    arrival = state.calc_arrival_rate()
    shortage = state.coin.get("shortage", 0.3)
    tax_coeff = TAX_COEFF_MIN + (TAX_COEFF_MAX - TAX_COEFF_MIN) * (1 - shortage)

    # 工商税基 POP 化：工匠/商人产值流量 = (工匠+商人)size × 人均产值（替代 calc_commerce 凭空 3.5 亿）
    # 产值流量不随 POP 财富存量下降（避免"税抽干财富→税基萎缩"的负反馈螺旋）
    from content.data import CRAFT_OUTPUT_PER_CAPITA
    _commerce_monthly = 0.0
    for _p in state.prefectures.values():
        _commerce_monthly += (_p["pops"]["工匠"]["size"] + _p["pops"]["商人"]["size"]) * CRAFT_OUTPUT_PER_CAPITA
    rate = max(COMMERCE_TAX_RATE_MIN, min(COMMERCE_TAX_RATE_MAX,
                                          getattr(state, "commerce_tax_rate", COMMERCE_TAX_RATE_DEFAULT)))
    commerce_tax = int(_commerce_monthly * rate * arrival * tax_coeff)
    # 役钱（徭役代役钱）：只从农 POP 征（乡村民户负担徭役）；坊郭户（工匠/商人）不服乡村差役、
    # 官户（士绅/官僚）免役、兵免。坊郭户的科配负担并入工商税（commerce_tax）。
    _farm_pop = sum(p["pops"]["农"]["size"] for p in state.prefectures.values())
    poll_tax = int((_farm_pop * TAX_POLL_RATIO / 12) * arrival * tax_coeff)
    maritime_tax = int((state.calc_maritime_trade() / 12.0) *
                       (state.maritime.get("tariff", 0.10) if state.maritime.get("open") else 0.0) *
                       arrival * tax_coeff)
    monthly_tax = commerce_tax + poll_tax + maritime_tax
    state.tax_breakdown = {"commerce": commerce_tax, "poll": poll_tax, "maritime": maritime_tax,
                           "official_service": 0}

    tax_color_total, tax_color_by = state.calc_monthly_tax_income(tax_coeff)
    salt_coin = state.calc_salt_coin(arrival)
    material_coin = 0.0
    monthly_tax_full = monthly_tax + tax_color_total + salt_coin + material_coin  # 目标收入（展示/预期）

    # 税从 POP 征（钱守恒）：役钱→农；二税折色按田亩归属拆分（农担自耕田、士绅担地主田）；工商税→工匠60%+商人40%；盐课+市舶→商人
    from content.data import PER_CAPITA_MONTH_GRAIN
    _tot_land = sum(p.get("land", 1) for p in state.prefectures.values()) or 1
    _self_share = sum(p.get("self_farm_land", 0) for p in state.prefectures.values()) / _tot_land
    _gentry_share = sum(p.get("gentry_land", 0) for p in state.prefectures.values()) / _tot_land
    _tax_agents = {
        "农": poll_tax + int(tax_color_total * _self_share),
        "士绅": int(tax_color_total * _gentry_share),
        # 蔡权衡裁决（工匠外销收入源）：工商税工匠份额 0.6→0.5（工匠税负减轻，配合外销变现防破产）
        "工匠": int(commerce_tax * 0.5),
        "商人": int(commerce_tax * 0.5) + int(salt_coin) + maritime_tax,
    }
    actual_tax = 0.0
    for _agent, _tax_total in _tax_agents.items():
        _total_wealth = sum(p["pops"][_agent]["wealth"] for p in state.prefectures.values())
        if _total_wealth <= 0:
            continue
        for _p in state.prefectures.values():
            _pop = _p["pops"][_agent]
            _deduct = int(_tax_total * (_pop["wealth"] / _total_wealth))
            _min_wealth = int(_pop["size"] * PER_CAPITA_MONTH_GRAIN * state.grain_price)  # 保留1个月口粮钱，不足则欠税
            # 平衡修复（蔡权衡）：保底豁免 × MIN_WEALTH_FLOOR_RATIO（0.75）——农可多缴 25%
            # 仍保生存底线（豁免线×0.5 验证），缓解「粮价下跌→农穷→税豁免」链
            from content.data import MIN_WEALTH_FLOOR_RATIO
            _min_wealth = int(_min_wealth * MIN_WEALTH_FLOOR_RATIO)
            _paid = min(_deduct, max(0, _pop["wealth"] - _min_wealth))
            # ---- 农「粜粮完税」（历史↔游戏性取中）----
            # 农户现金不足时卖粮给本路士绅/商人换钱完税（钱粮双向守恒）。
            # 原实现只把缺口记成欠税，而农户现金恒在保底线之下 → 欠税永不回收、
            # 农税通道整体死掉（60 月累计 4,399 万贯）。
            if _agent == "农" and _deduct - _paid > 0:
                _sold = _settle_tax_grain_sale(state, _p, _deduct - _paid)
                _paid += _sold
            _short = _deduct - _paid
            if _short > 0:
                # A1：缺口记入欠税科目（替代原直接蒸发），后续逐月追缴；存档兼容见 save_load 迁移
                _pop["欠税"] = _pop.get("欠税", 0) + _short
            _pop["wealth"] -= _paid
            actual_tax += _paid   # 累计实际到库税额（保底豁免部分不入库，钱不凭空生）
            # A1 追缴段：紧随税征，按「可支付余力（wealth - 保底线）× ARREARS_COLLECT_RATE」回收欠税
            _recoverable = max(0, _pop["wealth"] - _min_wealth)
            _recover = min(_pop.get("欠税", 0), int(_recoverable * ARREARS_COLLECT_RATE))
            if _recover > 0:
                _pop["wealth"] -= _recover
                _pop["欠税"] = _pop.get("欠税", 0) - _recover
                actual_tax += _recover

    wr = getattr(state, "waste_reform", None) or {}
    if wr.get("active"):
        step = max(10_000, int(wr["target"] / max(1, wr["months_left"])))
        if random.random() < 0.85:
            wr["savings"] = min(wr["target"], wr["savings"] + step)
        else:
            wr["savings"] = max(0, wr["savings"] - step)
        wr["months_left"] -= 1
        wr["progress"] = min(100, int(wr["savings"] / max(1, wr["target"]) * 100))
        if wr["months_left"] <= 0 or wr["savings"] >= wr["target"]:
            wr["active"] = False
            wr["savings"] = wr["target"]
            wr["progress"] = 100
            log.append(f"[变法] {'裁汰冗员' if wr['kind']=='reduce_office' else '省浮费'}告成，浮费月省 {wr['savings']:.0f}贯")
        elif wr["progress"] % 30 == 0:
            log.append(f"[变法] {'裁汰冗员' if wr['kind']=='reduce_office' else '省浮费'}推进中，用度稍省（月省 {wr['savings']:.0f}贯）")
    waste_savings = int(wr.get("savings", 0))

    pay = state.pay_system.get("cash_ratio", 0.5)
    cash_pay = int(PAY_CASH_BASE * pay)
    # C（A1）：真俸额先算，一体发钞时按真俸额单发交子（替代固定 cash_pay，防"纸钞+现金"双发）
    army_cash_total, _ = state.calc_army_cash()
    official_cash_total, _ = state.calc_official_cash()
    clerk_cash_total, _ = state.calc_clerk_cash()
    personnel_cash = int(army_cash_total + official_cash_total + clerk_cash_total)
    # 官户免役钱（史实免役法·调参定案）：助役钱 = 俸钱总额 × OFFICIAL_SERVICE_TAX_RATIO
    # （基于名义俸禄，指数化前计算，扣缴见俸禄发放后）
    official_service_tax = int((official_cash_total + clerk_cash_total) * OFFICIAL_SERVICE_TAX_RATIO)
    # ---- C-4 免役 → 税基口径（§13.6「冗官经 POP 侵蚀税基」这条链的显式化与可观测化）----
    # 役钱只从 `农` POP 征（乡村主户服徭役）；`士绅`（形势户）、`官僚`（官户）、`兵` 免役。
    # 官府并非全无所得：官户纳**助役钱**（上方 official_service_tax）。
    # 冗官膨胀的两条财政后果因此同时在场：
    #   ① 免除差役的人口↑ → **役钱税基萎缩**（科举寒门从农迁出，农 POP 直接变小）；
    #   ② 助役钱随俸禄总额↑ → 部分**自我补偿**（但只有 5%，远不足以抵消俸禄本身）。
    # 这里把两者记入 `tax_breakdown` / `statistics`，让玩家与 AI 都能看见"税基在缩"。
    _exempt_gentry = sum(p["pops"]["士绅"]["size"] for p in state.prefectures.values())
    _exempt_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values())
    _exempt_army = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values())
    _exempt_pop = _exempt_gentry + _exempt_guan + _exempt_army
    _taxable_pop = sum(p["pops"]["农"]["size"] for p in state.prefectures.values())
    _all_pop = _taxable_pop + _exempt_pop + sum(
        p["pops"]["工匠"]["size"] + p["pops"]["商人"]["size"] for p in state.prefectures.values())
    state.statistics["poll_base_pop"] = _taxable_pop          # 役钱税基（人）
    state.statistics["exempt_pop"] = _exempt_pop              # 免役人口（人）
    state.statistics["exempt_share"] = round(_exempt_pop / max(1, _all_pop), 6)
    state.statistics["poll_tax_nominal"] = poll_tax
    # T9 俸禄指数化（Step 4）：粮价 > PAY_INDEX_BASE 时俸禄 ×(1 + PAY_INDEX_STEP×超额)，
    # 抵补官吏/兵卒购买力（粮价通胀时俸禄随涨，防吏治崩坏）；超额 = 粮价 − 基准。
    # P1-1 守恒修复：发放给兵/官僚的俸禄与国库支出同源（同用指数化后金额），
    # 差额不再凭空消失（此前国库扣指数化俸禄、POP 只收未指数化 → 每月货币黑洞）。
    from content.data import PAY_INDEX_BASE, PAY_INDEX_STEP
    _pay_index = 1.0
    if state.grain_price > PAY_INDEX_BASE:
        _pay_index = 1.0 + PAY_INDEX_STEP * (state.grain_price - PAY_INDEX_BASE)
        personnel_cash = int(personnel_cash * _pay_index)
    army_pay = int(army_cash_total * _pay_index)
    official_pay = int((official_cash_total + clerk_cash_total) * _pay_index)
    # 一体发钞：俸禄以交子支付（国库不出现金、POP 不增铜钱）。此标志在两处消费：
    # 俸禄落账（下方 POP wealth）与支出计账（effective_cash_out），必须一致。
    _paper_pay = state.pay_system.get("mode") == "一体发钞"
    if _paper_pay:
        state.jiaozi["issued"] += personnel_cash          # 交子按真俸额发行（单发，替代固定 cash_pay）
        state.jiaozi["trust"] = max(0, state.jiaozi["trust"] - 2)
        expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
        cash_out = 0
    else:
        expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
        cash_out = cash_pay

    corruption_cash_ded, corruption_grain_loss = state.calc_corruption_deduction()
    clerk_gap_total, _ = state.calc_clerk_gap()
    payraise_used = min(state.payraise_budget, int(clerk_gap_total) + 10_000)
    state.payraise_budget = max(0, state.payraise_budget - payraise_used)

    sui_gong = 0
    _sui_parts = []   # [(政权, 银绢折钱额)]——岁币落账（2026-09-19）：钱入对应政权库藏
    _mult = getattr(state, "_sui_gong_mult", None) or {}
    if state.external.get("辽", {}).get("attitude", 50) >= 60:
        _amt = int(SUI_GONG_ANNUAL * 0.6 / 12 * _mult.get("辽", 1.0))   # 岁币倍率（外交协议）
        if _amt > 0:
            _sui_parts.append(("辽", _amt))
    if state.external.get("西夏", {}).get("attitude", 50) >= 60:
        _amt = int(SUI_GONG_ANNUAL * 0.4 / 12 * _mult.get("西夏", 1.0))
        if _amt > 0:
            _sui_parts.append(("西夏", _amt))
    sui_gong = sum(_a for _, _a in _sui_parts)
    # 阶段 B-2：岁币岁赐是**真实外流**（钱付与辽/西夏，退出本经济体），
    # 登记为销毁通道，使对账残差不再把它误算成"凭空销毁"。
    # 2026-09-19 岁币落账：外邦库藏**不在宋 ACCOUNTS**，对宋 M_ALL 而言口径不变
    # （仍为 burn）；同时把每笔岁币记入对应政权 treasury，由
    # `_settle_external_economy`（紧随本步）当月参与辽/夏的税饷/粮市循环——
    # 岁币从此有可见去向，辽夏经济与宋同构（test_external_economy.py）。
    if sui_gong > 0:
        try:
            from core.money import register_flow as _reg_flow
            _reg_flow(state, "burn", int(sui_gong), "岁币岁赐外流")
        except Exception:  # noqa: BLE001
            pass
        _ext_regimes = getattr(state, "external_regimes", {}) or {}
        for _rk, _amt in _sui_parts:
            _ex = _ext_regimes.get(_rk)
            if isinstance(_ex, dict):
                _ex["treasury"] = int(_ex.get("treasury", 0) or 0) + _amt
                _ex.setdefault("econ_stats", {})
                _ex["econ_stats"]["tribute_in"] = int(
                    _ex["econ_stats"].get("tribute_in", 0) or 0) + _amt

    # 兵 POP size 重聚合（兵额唯一真账 = army_units.troops 求和，避免增募/伤亡后 POP 漂移）
    for _p in state.prefectures.values():
        _p["pops"]["兵"]["size"] = 0
    for _u in state.army_units:
        if _u.station in state.prefectures and _u.troops > 0:
            state.prefectures[_u.station]["pops"]["兵"]["size"] += _u.troops
    # 收支双向落地：国库俸禄钱 → 兵/官僚 POP 钱（闭环，不凭空消失）
    _total_soldiers = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values()) or 1
    _total_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values()) or 1
    # 守恒修复（一体发钞）：俸禄已以交子支付，POP 铜钱不得再增。
    # 原实现无条件给 POP 记铜钱，而同月既发行等额交子、国库又不支出 →
    # 一笔俸禄记两次且凭空造币（货币总账逐月污染）。此处以 _paper_pay 门控。
    # ---- 阶段 B-3：按实付 ＋ 欠饷（修审查 A-2「穿底造币」）----
    # 军俸提至史实水平后（1,349 万贯/年），国库常有力不能及之月。原实现是：
    # POP **全额**收俸禄，而国库侧 `max(0, _avail)` 把差额钳掉、只记 `deficit_depth`
    # → 等于**凭空造币**（月度对账实测残差 +894,491/月，game_over 提前触发）。
    # 现先算支付能力，按比例实付，短付部分记「欠饷/欠俸」科目（与既有「欠税」科目对称）。
    # 语义：宁可欠着（欠饷 → 军心/官僚怨望的后继机制），也绝不凭空造币。
    _civil_back = max(0, expenditure)
    _credits_due = (0 if _paper_pay else personnel_cash) + _civil_back + int(corruption_cash_ded)
    _cash_available = max(0, int(state.treasury) + int(actual_tax) - int(sui_gong))
    _pay_scale = 1.0 if _credits_due <= 0 else min(1.0, _cash_available / float(_credits_due))
    _paid_personnel = int((0 if _paper_pay else personnel_cash) * _pay_scale)
    _paid_civil = int(_civil_back * _pay_scale)
    _paid_corruption = int(int(corruption_cash_ded) * _pay_scale)
    _arrears = _credits_due - (_paid_personnel + _paid_civil + _paid_corruption)
    if _arrears > 0:
        state.statistics["pay_arrears"] = state.statistics.get("pay_arrears", 0) + _arrears
        log.append(f"[财政] 帑藏不足：欠饷欠俸 {_arrears:,} 贯（本月实付率 {_pay_scale:.0%}）")

    # ---- 欠饷落到**各军**（阶段 B-3，用户要求）----
    # 把「军队部分的短付额」按各军本月应发军饷比例分摊，累加到 `ArmyUnit.arrears`。
    # 这样玩家点开任一军，都能看到该军被欠了多少（欠饷 → 军心/士气的后继机制挂点）。
    # 守恒无关（只是把已经发生的短付**记录**到编制单位，不再移动任何钱）。
    if not _paper_pay and _pay_scale < 1.0 and army_pay > 0:
        from content.data import branch_std as _bstd
        _unit_due = {}
        for _u in state.army_units:
            if _u.tier == "乡兵":          # 乡兵无饷（自备），不参与欠饷分摊
                continue
            _due = 0.0
            for _b, _n in (_u.branches or {}).items():
                _due += _n * _bstd(_u.tier, _b)["pay"]
            if _due > 0:
                _unit_due[_u.unit_id] = _due
        _due_total = sum(_unit_due.values()) or 1.0
        _army_due = float(army_pay)
        _army_paid = _army_due - _army_due * _pay_scale
        for _u in state.army_units:
            _due = _unit_due.get(_u.unit_id, 0.0)
            if _due > 0:
                _u.arrears = int(getattr(_u, "arrears", 0)) + int(_army_paid * _due / _due_total)

    # 官户免役钱（史实免役法·调参定案）：官户纳助役钱 = 俸钱总额 × 0.05，
    # 从官僚 POP wealth 按 size 扣缴入国库（钱守恒：官僚交钱、国库收钱，不凭空生钱）
    # 审查 P0：wealth 不足时只按实收入账（_tax_left 反映欠缴，不再全额造币）
    if official_service_tax > 0:
        _tax_left = official_service_tax
        for _p in state.prefectures.values():
            if _p["pops"]["官僚"]["size"] > 0:
                _take = int(official_service_tax * _p["pops"]["官僚"]["size"] / max(_total_guan, 1))
                _take = min(_take, int(_p["pops"]["官僚"]["wealth"]))
                _p["pops"]["官僚"]["wealth"] = max(0, _p["pops"]["官僚"]["wealth"] - _take)
                _tax_left -= _take
        actual_tax += official_service_tax - max(0, _tax_left)
        # 助役钱实收额入账（原先只并入 actual_tax、无科目，玩家看不到"官户也在纳钱"）
        _ost_actual = int(official_service_tax - max(0, _tax_left))
        state.tax_breakdown["official_service"] = _ost_actual
        state.statistics["official_service_tax"] = _ost_actual
    else:
        state.tax_breakdown["official_service"] = 0

    # 收支双向落地：国库俸禄钱 → 兵/官僚 POP 钱（闭环；金额取**实付额**，见上）
    # 守恒修复（一体发钞）：俸禄已以交子支付，POP 铜钱不得再增（_paper_pay 门控）。
    # 残差修正：逐府 int() 分摊截断曾使 Σcredit < 实付额（无对手方销毁 ~50贯/月），
    # 改用尾差归最大府的守恒分摊 _distribute_pop_wealth，保证 Σcredit == 实付额。
    if not _paper_pay and _paid_personnel > 0:
        _ratio_army = army_pay / max(army_pay + official_pay, 1.0)
        _army_paid = int(_paid_personnel * _ratio_army)
        _off_paid = _paid_personnel - _army_paid
        _distribute_pop_wealth(state, _army_paid, "兵", _total_soldiers)
        _distribute_pop_wealth(state, _off_paid, "官僚", _total_guan)
    # 支出回流（A1 定案·修货币漂移斜率 -13%→-3.5%）：常费不再纯蒸发 → 工匠 40% + 商人 60%（按 size 分摊，
    # 政府花钱买营造/服务/商品，钱进民间）；贪腐扣减 → 官僚 wealth（隐性聚敛，可抄没）；岁币保留销币（真实外流）。
    # 以上三项同样按 **实付额** 落地（`_pay_scale`），保证"扣==收"。
    _total_artisan = sum(p["pops"]["工匠"]["size"] for p in state.prefectures.values()) or 1
    _total_merchant = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
    if _paid_civil > 0:
        _civ_artisan = int(_paid_civil * 0.4)
        _distribute_pop_wealth(state, _civ_artisan, "工匠", _total_artisan)
        _distribute_pop_wealth(state, _paid_civil - _civ_artisan, "商人", _total_merchant)
    if _paid_corruption > 0:
        _distribute_pop_wealth(state, _paid_corruption, "官僚", _total_guan)
    # 一体发钞时俸禄由交子支付（国库不发现金）；否则按**实付** personnel 计出
    if _paper_pay:
        effective_cash_out = 0
    else:
        effective_cash_out = _paid_personnel
    total_out = (_paid_civil + effective_cash_out
                 + _paid_corruption + payraise_used + sui_gong)
    net = monthly_tax_full - total_out
    # 实际到库净额：保底豁免的税不入国库（钱不凭空生），故用 actual_tax 替代目标 monthly_tax_full
    actual_net = actual_tax - total_out

    treasury_before = state.treasury
    imp_share, wine_coin = state.calc_imperial_treasury(actual_net)
    # 酒课税改造（加消耗完整定案）：酒课（60万贯/月）从工匠 60% / 商人 40% wealth 扣缴入内帑
    # （钱守恒转移，修复现行 wine_coin 凭空入内帑的漏洞；酿酒耗粮另在 Step 3.8 从农存粮扣）
    _wine_tax_cash = int(wine_coin)
    if _wine_tax_cash > 0:
        _art_total = sum(p["pops"]["工匠"]["size"] for p in state.prefectures.values()) or 1
        _mer_total = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
        _wine_left = _wine_tax_cash
        for _p in state.prefectures.values():
            _art, _mer = _p["pops"]["工匠"], _p["pops"]["商人"]
            if _art["size"] > 0:
                _take = int(_wine_tax_cash * 0.6 * _art["size"] / _art_total)
                # P0 修复（蔡权衡·工匠 wealth 归零）：扣缴上限 = 工匠 wealth 的 5%/月
                # （超时代酒课膨胀时扣缴抽干工匠 → 税基崩；上限保工匠生存底线）
                _take = min(_take, int(_art["wealth"] * 0.05))
                _art["wealth"] = max(0, _art["wealth"] - _take)
                _wine_left -= _take
            if _mer["size"] > 0:
                _take = int(_wine_tax_cash * 0.4 * _mer["size"] / _mer_total)
                _take = min(_take, int(_mer["wealth"] * 0.10))
                _mer["wealth"] = max(0, _mer["wealth"] - _take)
                _wine_left -= _take
        # 实征入账（审查 P0：禁止全额入内帑造币）——短征不记入内帑
        _wine_tax_cash = max(0, _wine_tax_cash - max(0, _wine_left))
    # 国库保持整数贯：actual_net 为 float（各 calc_* 乘积），入账前截断
    # B3 修复：国库禁止穿底，不足部分记入**累计亏空深度**（破产两档线的唯一判据），
    # 有结余时优先冲抵历史亏空，余下才进国库。
    _deficit_used = 0
    _avail = state.treasury + int(actual_net) - int(imp_share)
    _prior_deficit = int(getattr(state, "treasury_deficit", 0) or 0)
    if _avail < 0:
        state.treasury_deficit = _prior_deficit + (-_avail)
        _avail = 0
    elif _prior_deficit > 0:
        _deficit_used = min(_prior_deficit, _avail)
        state.treasury_deficit = _prior_deficit - _deficit_used
        _avail -= _deficit_used
    else:
        state.treasury_deficit = 0
    state.treasury = max(0, int(_avail))
    state.imperial_treasury = max(0, state.imperial_treasury + int(imp_share) + int(_wine_tax_cash))
    state.statistics["total_income"] += int(actual_tax)
    state.statistics["total_expenditure"] += total_out

    # 恒等式：未穿底时 Δtreasury == actual_net − imp − 冲抵亏空额；
    # 穿底钳到 0（差额已入 treasury_deficit）时 Δ == -treasury_before
    _delta = state.treasury - treasury_before
    _expect = actual_net - int(imp_share)
    _floored = state.treasury == 0 and (treasury_before + _expect) < 0
    assert _floored or abs(_delta - _expect + _deficit_used) < 1, \
        f"财政恒等断裂：Δtreasury={_delta} actual_net={actual_net} imp={int(imp_share)}"

    # 结余补发积欠（在恒等式校验**之后**执行：它是独立的一笔守恒转移，不改财政恒等）
    _settle_arrears_repayment(state, log)

    inc_parts = f"工商{commerce_tax:.0f}+役钱{poll_tax:.0f}+二税折色{tax_color_total:.0f}+盐课{salt_coin:.0f}"
    if maritime_tax > 0:
        inc_parts += f"+市舶{maritime_tax:.0f}"
    if net < 0:
        log.append(f"[财政] 货币月入 {actual_tax:.0f}贯（{inc_parts}） 支 {total_out:.0f}贯 亏空 {abs(actual_net):.0f}贯（宜折变补之）")
    else:
        log.append(f"[财政] 货币月入 {actual_tax:.0f}贯（{inc_parts}） 支 {total_out:.0f}贯 结余 {actual_net:.0f}贯")
    if sui_gong > 0:
        log.append(f"[岁币] 岁币岁赐 {sui_gong:.0f}贯，纳贡以安边")
        # 审查补齐（外交纪事面板恒空的根因）：本项支付原先只入结算流水，不写
        # state.diplomacy_log —— 而该字段在全库**再无任何写入方**，故面板永久空白
        # （前端它处亦有"（纪事阙文）"兜底文案，正是为此）。
        _dlog = getattr(state, "diplomacy_log", None)
        if isinstance(_dlog, list):
            _parts = []
            if _mult.get("辽", 1.0):
                _parts.append("辽")
            if _mult.get("西夏", 1.0):
                _parts.append("西夏")
            _dlog.append({
                "year": int(getattr(state, "year", 0) or 0),
                "month": int(getattr(state, "month", 0) or 0),
                "text": f"输岁币岁赐 {int(sui_gong)}贯（{'、'.join(_parts) or '北境'}），纳贡以安边",
            })

    from content.data import TREASURY_CRISIS_LINE
    # B3：判据由「负国库」改为「累计亏空深度」（国库禁穿底，负值不可达）。
    if state.deficit_depth() > TREASURY_CRISIS_LINE:
        state.population_satisfaction = max(0, state.population_satisfaction - 2)
        log.append("[民生] 国库亏空严重，民怨渐起")

    corrupt_targets = []
    for org_key in ("户部",):
        o = state.central_orgs.get(org_key)
        if o and o.get("lead"):
            corrupt_targets.append(o["lead"])
    if corrupt_targets:
        stress = (state.land.get("hidden_rate", 0.0) - 0.3) + (-net / 1_000_000 if net < 0 else 0)
        drift = max(-0.01, min(0.02, stress * 0.05))
        for name in corrupt_targets:
            if name in state.corruption:
                state.corruption[name] = max(0.0, min(1.0, state.corruption[name] + drift))


def _settle_bank_stock(state, log) -> None:
    """**Step 10.6**：银行（抵当所）存款**存量**月末硬收敛（2026-09-19 修复）。

    存款上限 = 目标阶层 POP 财富 × `didang_deposit_cap`（旋钮，默认 0.30）。

    **为什么必须放在全部结算步之后**：原"吸储饱和"修复只约束**当月吸储流量**
    （`_settle_bank` 内的 `_room`），而存款是历史累积、从不回落；且 `wealth` 在银行步
    之后仍会被赋税/俸禄/物价等步骤继续改变 → 银行步内按当时 wealth 收敛，月末实测仍超限
    （240 月压力测试：存款 15,541,569 贯 vs 上限 5,897,845 贯；仅按银行步内财富收敛仍差 1,489 贯）。

    收敛分两段，**都不破坏货币守恒**：
      ① 准备金足够 → **回吐**给目标阶层（`reserve` → POP `wealth`，成对转移）；
      ② 不足（钱已贷出在 `loans` 里）→ 超额部分由「存款负债」**重分类**为
         「已投放资金」memo（`disbursed`）：不动 `reserve`/`wealth`，货币总量不变，
         只是账面科目重分类 —— 不假装那部分钱仍是可提取的民间存款。
    """
    b = getattr(state, "bank", None)
    if not isinstance(b, dict) or not b.get("established"):
        return
    from core import institution as _inst
    target = str(b.get("target") or "")
    pop_name = target if target in ("农", "士绅", "工匠", "商人", "官僚", "兵") else "商人"
    pools = []
    for _p in (getattr(state, "prefectures", None) or {}).values():
        slot = (_p.get("pops") or {}).get(pop_name)
        if isinstance(slot, dict) and int(slot.get("wealth", 0) or 0) > 0:
            pools.append(slot)
    if not pools:
        return
    cap_ratio = float(_inst.get(state, "didang_deposit_cap", 0.30))
    w_final = sum(int(s.get("wealth", 0) or 0) for s in pools)
    if w_final <= 0:
        return
    cap = int(w_final * cap_ratio)
    dep = int(b.get("deposits", 0) or 0)
    if dep <= cap:
        return

    # ① 准备金够 → 回吐（成对：reserve ↓ / POP wealth ↑）
    reserve = int(b.get("reserve", 0) or 0)
    give = min(dep - cap, reserve)
    if give > 0:
        returned = 0
        for _idx, slot in enumerate(pools):
            w = int(slot.get("wealth", 0) or 0)
            add = (give - returned) if _idx == len(pools) - 1 else int(give * w / max(1, w_final))
            add = max(0, min(add, give - returned))
            slot["wealth"] = w + add
            returned += add
        if returned > 0:
            b["reserve"] = reserve - returned
            b["deposits"] = dep - returned
            log.append(f"[银行] 月末存款存量超上限，回吐 {returned:,}贯与{pop_name}（防抽干民间）")
            # 回吐抬高财富 → 上限随之上抬，重算后再判是否需要重分类
            w_final = sum(int(s.get("wealth", 0) or 0) for s in pools)
            cap = int(w_final * cap_ratio)
            dep = int(b.get("deposits", 0) or 0)

    # ② 准备金不足（钱已贷出）→ 超额部分重分类为「已投放资金」memo（不动货币）
    if dep > cap:
        excess = dep - cap
        b["deposits"] = cap
        b["disbursed"] = int(b.get("disbursed", 0) or 0) + excess
        log.append(f"[银行] 月末存款存量超上限，{excess:,}贯由存款负债转列「已投放资金」"
                   f"（账面重分类，货币总量不变）")


