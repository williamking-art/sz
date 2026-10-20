# -*- coding: utf-8 -*-
"""宋祚 · 财政与货币信用（从 settlement_steps.py 拆出，零行为变更）。

银行信贷、交子界制、熔铜、稳定器回收、税收与积欠、存款存量收敛。"""
from __future__ import annotations

import logging
import random

from content.data import (
    COMMERCE_TAX_RATE_MIN,
    COMMERCE_TAX_RATE_MAX,
    TAX_COEFF_MIN,
    TAX_COEFF_MAX,
    TAX_POLL_RATIO,
    COMMERCE_TAX_RATE_DEFAULT,
    MONTHLY_EXP_CIVIL_BASE,
    SUI_GONG_ANNUAL,
    ARREARS_COLLECT_RATE,
    OFFICIAL_SERVICE_TAX_RATIO,
)

from core.domains.economy.settlement_econ_helpers import (
    _distribute_pop_wealth,
)

# 🔴 方案乙（2026-10-04 用户裁定：POP 实体下沉州府级）：POP **写入**一律走桥接层，
# 由它先落州府真账、再刷新路级派生镜像，杜绝「镜像与真账漂移」。
# 存量**读取**仍走路级 `pops`（它是由桥接维护的镜像，无需逐处改写）。
# ⚠️ 若本模块的州府级 `seats` 尚未建立（未下沉），桥接返回 None 并回落原写法。
from core.foundation.ledger.pop_bridge import (pop_add as _pop_add, pop_set as _pop_set,
                             pop_obj_add as _pop_obj_add, pop_obj_set as _pop_obj_set)
# 粮写入同样走 G-3 桥接（写只落一个载体，绝不双写）
from core.foundation.ledger.grain_bridge import grain_add as _grain_add

_fin_log = logging.getLogger("settlement")

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

    from core.foundation.ledger.money import m_all as _m_all
    from core.foundation.ledger.money import register_flow as _reg_flow
    from core.domains.administration import institution as _inst
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
    #
    # 审查 P2-3 / M15：原实现读数失败回落 `trust_conf = 1.0` —— 那是"零挤兑压力"的
    # **伪造值**，且对玩家有利（信心满 → 放贷/坏账口径全部偏向宽松）；更糟的是它与
    # "确实无压力"完全同值，事后无从分辨。现改为 `None`（**不可判定**）＋沿用上月
    # `overdue_rate`（存量延续，不凭空造出一个有利读数）＋WARNING/traceback。
    trust_conf = None
    try:
        from core.foundation.ledger.money import jiaozi_run_pressure as _jz_run
        trust_conf = 1.0 - max(0.0, min(1.0, float(_jz_run(state))))
    except Exception:  # noqa: BLE001 — 只读派生失败不阻断结算，但**不得**伪造"无压力"
        _fin_log.warning("[银行] 交子挤兑压力读数失败，本月沿用上月逾期率"
                         "（不回落 1.0 伪造无压力）", exc_info=True)
    target = str(b.get("target") or "")
    pop_name = target if target in ("农", "士绅", "工匠", "商人", "官僚", "兵") else "商人"

    # ---- 1) 坏账核销（先于放贷，防坏账继续计息）----
    bad_debt = 0
    loans0 = int(b.get("loans", 0) or 0)
    _prev_overdue = max(0.0, min(1.0, float(b.get("overdue_rate", 0) or 0)))
    if trust_conf is None:
        overdue = _prev_overdue          # 不可判定 → 沿用上月值（存量延续）
        if isinstance(log, list):
            log.append("[银行][WARN] 挤兑压力不可判定，本月逾期率沿用上月值"
                       f"（{_prev_overdue:.4f}）")
    else:
        overdue = max(0.0, min(1.0, _prev_overdue * 0.5
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
            _nw = w - take
            if _pop_obj_set(state, slot, "wealth", _nw) is None:
                slot["wealth"] = _nw
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
        # trust_conf=None（读数不可判定）→ 放贷信心因子取 0：**不假装"无压力"**而
        # 照常放贷（那正是 M15 的畸形收益）；本月信贷收缩，下月读数恢复即复原。
        _conf_for_lend = 0.0 if trust_conf is None else trust_conf
        _want = int(min(lendable, int(reserve * LEND * _conf_for_lend)))
        if _want > 0 and _pool_now > 0:
            _lent = 0
            for slot in pools:
                w = int(slot.get("wealth", 0) or 0)
                add = int(_want * w / _pool_now)
                _nw = w + add
                if _pop_obj_set(state, slot, "wealth", _nw) is None:
                    slot["wealth"] = _nw
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
                _nw = w - take
                if _pop_obj_set(state, slot, "wealth", _nw) is None:
                    slot["wealth"] = _nw
                interest += take
            if interest > 0:
                reserve += interest
                b["reserve"] = reserve
                state.statistics["bank_interest_income"] = (
                    state.statistics.get("bank_interest_income", 0) + interest)
                log.append(f"[银行] 收息 {interest:,}贯（归银行留存，不作财政收入）")

    # ---- 5) 挤兑压力（准备金不足兑付存款 + 信用不足 → 压力）----
    # trust_conf=None（不可判定）→ **沿用上月值**（与逾期率同一处理原则），
    # 既不伪造"无压力"，也不另造一条新公式。
    req_all = int(int(b.get("deposits", 0) or 0) * BANK_RESERVE_RATIO_MIN)
    if trust_conf is not None:
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
    # 🔴 2026-10-20 全审 P0-1（A-1）：**必须逐治所真账扣减**，不得读路级镜像再
    # `pop_obj_set` 回写——路级 `pops` 是派生镜像；若本回合有治所级直写（外贸进口
    # 付款等）尚未刷镜像，用镜像值重铺治所会把已扣的钱整额「复活」（实测 12 月
    # 凭空造币 +13,470,432）。未下沉（裸 GameState/旧档）才回退旧写法。
    from core.foundation.ledger.pop_bridge import refresh_route_class
    _melted = 0
    for p in state.prefectures.values():
        seats = (p or {}).get("seats") or {}
        if not seats:
            for pop in (p.get("pops") or {}).values():
                w = float(pop.get("wealth", 0))
                if w > 0:
                    _take = int(w * MELT_RATE)
                    if _take > 0:
                        _nw = max(0, w - _take)
                        if _pop_obj_set(state, pop, "wealth", _nw) is None:
                            pop["wealth"] = _nw
                        _melted += _take
            continue
        touched = set()
        for srow in seats.values():
            for cls, pop in ((srow or {}).get("pops") or {}).items():
                w = float(pop.get("wealth", 0) or 0)
                if w <= 0:
                    continue
                _take = int(w * MELT_RATE)
                if _take <= 0:
                    continue
                pop["wealth"] = w - _take          # 治所真账（唯一权威）
                _melted += _take
                touched.add(cls)
        for cls in touched:
            refresh_route_class(p, cls)            # O(1) 刷镜像，不重铺其他治所
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
            # 🟢 M42a：逐维流量登记（熔铜池溢出**入国家仓**；测量仪器，失败不中断）
            if _taken > 0:
                from core.domains.economy import stock_flow as _sf
                _sf.record_in(state, COPPER_RESOURCE_DIM, _taken, reason="melt_pool_overflow")
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
    """国库结算——财政计征已在 Step 4（_settle_finance）完成，此处不得重复计征。

    2026-09-26 起 Step 5 承载**封桩分层代价通道**（`core/hoard_settle.settle_hoard`，
    货币规范 §12.2/§12.3）：C2 侵渔（封桩→吏私囊，守恒划转非计征）＋ C3/C4
    「帑藏充溢」事件压力（Step 7 事件步之前当月生效）。占位步由此转正为
    「库存结算」语义，步骤编号与 _STEPS 镜像不变。
    """
    from core.domains.economy.hoard_settle import settle_hoard  # 延迟导入（避免顶层环）
    settle_hoard(state, log)
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
        _bw = int(b.get("wealth", 0) or 0) - pay
        if _pop_obj_set(state, b, "wealth", _bw) is None:
            b["wealth"] = _bw
        _bg = int(b.get("grain", 0) or 0) + g
        if _grain_add(b, _bg - int(b.get("grain", 0) or 0), state) is None:
            b["grain"] = _bg
        paid += pay
        gave += g

    # 若因逐户封顶导致实际成交少于计划：以实际为准（粮随钱走，双向精确守恒）
    if gave > grain:
        gave = grain
    _fg = int(farm.get("grain", 0) or 0) - gave
    if _grain_add(farm, -gave, state) is None:
        farm["grain"] = _fg
    _fw = int(farm.get("wealth", 0) or 0) + paid
    if _pop_obj_set(state, farm, "wealth", _fw) is None:
        farm["wealth"] = _fw
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
        if _pop_obj_add(state, _pop, "wealth", _gv) is None:
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


def _book_tax_loss(state, amount: int) -> None:
    """P2 账面：把侵渔额以「损耗」类目记入**官方账目** `statistics["tax_loss_report"]`。

    真账＝吏囊（官僚 POP wealth，已在 `_settle_land_tax_color` 落地）；
    账面＝火耗类损耗（本函数）——**账实落差**即「贪吏做账」的可观测形态。
    拆分系数 `FIN_LOSS_COVER`（分散多科目更不易察觉）；**总和精确等于 amount**（尾差归火耗）。
    """
    if amount <= 0:
        return
    from content.data import FIN_LOSS_COVER
    rep = state.statistics.setdefault(
        "tax_loss_report",
        {"运输损耗": 0, "地方耗费": 0, "火耗": 0, "杂费": 0, "total": 0})
    for _k in ("运输损耗", "地方耗费", "火耗", "杂费", "total"):
        rep.setdefault(_k, 0)
    _given = 0
    for _k, _w in FIN_LOSS_COVER.items():
        if _k == "火耗":
            continue
        _part = int(amount * _w)
        rep[_k] = int(rep.get(_k, 0) or 0) + _part
        _given += _part
    rep["火耗"] = int(rep.get("火耗", 0) or 0) + (amount - _given)   # 尾差归火耗
    rep["total"] = int(rep.get("total", 0) or 0) + amount


def _settle_land_tax_color(state, log) -> dict:
    """田赋折色（P1 双层税基·三率分流；Q3 甲：**仅此税种**换新模型）。

    流程：应征 assessed（全额税基 × 征收率）→ 逐户实收（`[农×自耕份额]＋[士绅×地主份额]`，
    与旧扣缴同规则：保底豁免／欠税／农粜粮完税）→ 按该路**归一三率**三分：

      中央 ＝ paid × transfer   （返回给调用方 → 并入 actual_tax → 国库）
      留州 ＝ paid × keep       （直接入 `prefectures[路]["local_treasury"]`）
      侵渔 ＝ paid × div        （直接入该路官僚 POP wealth；无官僚池时转归中央并留痕）

    尾差（≤2 贯/路）归中央（保护 transfer，V1.3 §3.4）。欠税**追缴段**仍在其余税种
    的逐户扣缴循环内统一运行（本函数不重复追缴，防双收）。

    守恒：`Δ(POP wealth) ＋ 留州 ＋ 侵渔 ＋ 中央(返回) ≡ 0`（纯转移；粜粮完税为钱粮互换）。
    """
    from content.data import MIN_WEALTH_FLOOR_RATIO, PER_CAPITA_MONTH_GRAIN
    # P6（2026-10-19）：被非宋政权**全占**的路不计田赋；默认全宋 ⇒ 判定恒真（零变更）
    try:
        from core.foundation.ledger.region_registry import song_route_active
        _active = {_rk for _rk in state.prefectures if song_route_active(state, _rk)}
    except Exception:  # noqa: BLE001
        _active = set(state.prefectures)
    chan = state.calc_land_tax_channels()
    assessed = int(chan["assessed_total"])
    paid_by_route = {_rk: 0 for _rk in state.prefectures}
    if assessed > 0 and state.prefectures:
        _tot_land = sum(p.get("land", 1) for _rk, p in state.prefectures.items() if _rk in _active) or 1
        _self_share = (sum(p.get("self_farm_land", 0) for _rk, p in state.prefectures.items() if _rk in _active)
                       / _tot_land)
        _gentry_share = (sum(p.get("gentry_land", 0) for _rk, p in state.prefectures.items() if _rk in _active)
                         / _tot_land)
        # 税从 POP 征（钱守恒）：二税折色按田亩归属拆分——农担自耕田、士绅担地主田
        _agent_charge = {"农": int(assessed * _self_share),
                         "士绅": int(assessed * _gentry_share)}
        for _agent, _tc_total in _agent_charge.items():
            if _tc_total <= 0:
                continue
            _total_wealth = sum(p["pops"][_agent]["wealth"]
                                for _rk, p in state.prefectures.items() if _rk in _active)
            if _total_wealth <= 0:
                continue
            for _rk, _p in state.prefectures.items():
                if _rk not in _active:
                    continue
                _pop = _p["pops"][_agent]
                _deduct = int(_tc_total * (_pop["wealth"] / _total_wealth))
                _min_wealth = int(_pop["size"] * PER_CAPITA_MONTH_GRAIN * state.grain_price)
                _min_wealth = int(_min_wealth * MIN_WEALTH_FLOOR_RATIO)
                _paid = min(_deduct, max(0, _pop["wealth"] - _min_wealth))
                if _agent == "农" and _deduct - _paid > 0:
                    # 农「粜粮完税」（与旧扣缴同规则；本路士绅/商人买粮，钱粮双向守恒）
                    _paid += _settle_tax_grain_sale(state, _p, _deduct - _paid)
                _short = _deduct - _paid
                if _short > 0:
                    if _pop_obj_add(state, _pop, "欠税", _short) is None:
                        _pop["欠税"] = _pop.get("欠税", 0) + _short
                if _paid > 0:
                    if _pop_obj_add(state, _pop, "wealth", -_paid) is None:
                        _pop["wealth"] -= _paid
                    paid_by_route[_rk] += _paid
    central = local_total = div_total = 0
    local_by_route, div_by_route = {}, {}
    central_by_route = {}
    for _rk, _paid in paid_by_route.items():
        if _paid <= 0:
            continue
        _t, _k, _d = state.finance_split(_rk)
        _l = int(_paid * _k)
        _dv = int(_paid * _d)
        _c = _paid - _l - _dv                       # 尾差归中央（保护 transfer）
        _pd = state.prefectures.get(_rk) or {}
        if _l > 0:
            # 🟢 主线 B（M37b）：地方府库写点走桥（未下沉 ⇒ None ⇒ 回落原写法）
            from core.foundation.ledger import local_treasury_bridge as _ltb
            if _ltb.local_treasury_add(state, _rk, _l) is None:
                _pd["local_treasury"] = int(_pd.get("local_treasury", 0) or 0) + _l
            local_total += _l
            local_by_route[_rk] = _l
        if _dv > 0:
            _guan = (_pd.get("pops") or {}).get("官僚")
            if isinstance(_guan, dict):
                if _pop_obj_add(state, _guan, "wealth", _dv) is None:
                    _guan["wealth"] = int(_guan.get("wealth", 0) or 0) + _dv
                div_total += _dv
                div_by_route[_rk] = _dv
            else:
                # 无接收池：不得销毁 → 转归中央并留痕（可诊断）
                _c += _dv
                log.append(f"[田赋] {_rk} 侵渔无接收池（官僚 POP 缺失），该路侵渔份额转归中央")
        central += _c
        central_by_route[_rk] = central_by_route.get(_rk, 0) + _c
    # ---- M34-①（裁决 2026-10-11 · **财政顺序改造**）：地方必要支出**优先层** ----
    # 宋代口径是「**地方先养活行政/治安/水利** → 剩余上供中央」，不是「中央先拿走大头」。
    # 故：本路责任科目的**现实应支**（`calc_local_expenditure().by_route[路]["due_eff"]`，
    # 已含玩家保障倍数与官员有效使用率）从**中央解送额**中**优先划出**给本路府库；
    # 上限＝中央本应得（不透支、守恒不破：central+local+div ≡ collected 仍成立）。
    # 国库因此**少收，但同额少付**（见 `_settle_finance` 人员腿抵减 / `_settle_upkeep` 水利排除）。
    _required_landed = 0
    required_by_route = {}
    if state.prefectures:
        try:
            _req = state.calc_local_expenditure()["by_route"]
        except Exception as _e:                     # noqa: BLE001 — 读数失败不得阻断结账
            _req = {}
            log.append(f"[地方经费] 必要支出扣除层读数失败（{type(_e).__name__}），本轮不扣除")
        for _rk in list(central_by_route):
            _need = int((_req.get(_rk) or {}).get("due_eff", 0))
            _move = min(_need, central_by_route[_rk])
            if _move <= 0:
                continue
            _pd = state.prefectures.get(_rk)
            if not isinstance(_pd, dict):
                continue
            # 🟢 主线 B（M37b）：地方府库写点走桥（未下沉 ⇒ None ⇒ 回落原写法）
            from core.foundation.ledger import local_treasury_bridge as _ltb
            if _ltb.local_treasury_add(state, _rk, _move) is None:
                _pd["local_treasury"] = int(_pd.get("local_treasury", 0) or 0) + _move
            central_by_route[_rk] -= _move
            central -= _move
            local_total += _move
            local_by_route[_rk] = local_by_route.get(_rk, 0) + _move
            _required_landed += _move
            required_by_route[_rk] = required_by_route.get(_rk, 0) + _move
    _st = state.statistics
    _collected = sum(paid_by_route.values())
    _st["land_tax_assessed"] = int(_st.get("land_tax_assessed", 0) or 0) + assessed
    _st["land_tax_collected"] = int(_st.get("land_tax_collected", 0) or 0) + _collected
    _st["land_tax_central"] = int(_st.get("land_tax_central", 0) or 0) + central
    _st["land_tax_local"] = int(_st.get("land_tax_local", 0) or 0) + local_total
    _st["land_tax_diverted"] = int(_st.get("land_tax_diverted", 0) or 0) + div_total
    # M34-①（财政顺序）：地方必要支出**优先层**划出额（含在 `land_tax_local` 内，单列留痕）
    _st["land_tax_required"] = int(_st.get("land_tax_required", 0) or 0) + _required_landed
    # M34-④：**本月**结账快照（供面板/比率读数；累计值另见 land_tax_*）
    _st["land_tax_last"] = {
        "turn": int(getattr(state, "turn", 0) or 0),
        "assessed": assessed, "collected": _collected,
        "central": central, "local": local_total, "diverted": div_total,
        "required": _required_landed,
    }
    log.append(f"[田赋] 折色应征 {assessed:,}贯 → 实收 {_collected:,}贯；三分："
               f"上供 {central:,}／留州 {local_total:,}／侵渔 {div_total:,}"
               + (f"；其中地方必要支出优先划出 {_required_landed:,}贯" if _required_landed else "")
               + (f"（豁免/欠税 {assessed - _collected:,}）" if _collected < assessed else ""))
    return {"assessed": assessed, "collected": _collected, "central": central,
            "local": local_total, "diverted": div_total,
            "required_landed": _required_landed,
            "required_by_route": required_by_route,
            "by_route": paid_by_route, "local_by_route": local_by_route,
            "div_by_route": div_by_route}


def _settle_local_extra_income(state, log) -> dict:
    """地方附加收入（M34-① · **D6′ 裁决**）：坊场钱／经制钱／杂税——**独立收入池**直接入府库。

    - **不并入 `keep`**（不动三分模型）：地方自有财源，不经上供（`田赋 → 三分` 与
      `附加收入 → local_treasury` 两条平行）；
    - **从本路民间 POP 征收**（坊郭户＝工匠/商人；乡村杂派＝农），走 `transfer_money` 单点划转
      ⇒ 守恒（ΣΔ==0、不造币）；POP 现钱不足则**按可付截断**（地方自征，不记欠税）；
    - 派生于**既有量**：工商月产出（工匠+商人 size × `CRAFT_OUTPUT_PER_CAPITA`）× 本路**征收率**；
      经制钱另挂田赋折色**应征**（`calc_land_tax_channels`）；
    - **接口**：`LOCAL_EXTRA_ENABLED` 总开关（诏令/改革可关或加强）；三率常量初值·待校准门定值。
    """
    from content.data import (CRAFT_OUTPUT_PER_CAPITA, LOCAL_EXTRA_ENABLED,
                              LOCAL_EXTRA_FANGFANG_SHARE, LOCAL_EXTRA_JINGZHI_SHARE,
                              LOCAL_EXTRA_ZASHUI_SHARE)
    if not LOCAL_EXTRA_ENABLED:
        return {"total": 0, "by_route": {}, "by_kind": {}}
    ch = (state.calc_land_tax_channels() or {}).get("by_route", {})
    total = 0
    by_kind = {"坊场钱": 0, "经制钱": 0, "杂税": 0}
    by_route = {}
    _payers = {"坊场钱": (("工匠", 0.5), ("商人", 0.5)),
               "经制钱": (("商人", 0.6), ("工匠", 0.4)),
               "杂税": (("农", 1.0),)}
    for name, p in state.prefectures.items():
        if not isinstance(p, dict):
            continue
        pops = p.get("pops") if isinstance(p.get("pops"), dict) else {}
        if not pops:
            continue

        def _sz(cls):
            row = pops.get(cls)
            return int((row or {}).get("size", 0) or 0) if isinstance(row, dict) else 0

        _commerce = (_sz("工匠") + _sz("商人")) * float(CRAFT_OUTPUT_PER_CAPITA)
        _rate = float(state.calc_collection_rate(name))
        _assessed = int((ch.get(name) or {}).get("assessed", 0) or 0)
        _dues = {
            "坊场钱": int(_commerce * float(LOCAL_EXTRA_FANGFANG_SHARE) * _rate),
            "经制钱": int(_assessed * float(LOCAL_EXTRA_JINGZHI_SHARE)),
            "杂税": int(_commerce * float(LOCAL_EXTRA_ZASHUI_SHARE) * _rate),
        }
        route_got = 0
        for kind, amt in _dues.items():
            if amt <= 0:
                continue
            given = 0
            shares = _payers[kind]
            for _i, (_cls, _w) in enumerate(shares):
                part = amt - given if _i == len(shares) - 1 else int(amt * _w)
                if part <= 0:
                    continue
                given += state.transfer_money(f"pop:{name}:{_cls}", f"local:{name}", part)
            by_kind[kind] += given
            route_got += given
        if route_got > 0:
            by_route[name] = route_got
            total += route_got
    if total > 0:
        state.statistics["local_extra_income"] = \
            int(state.statistics.get("local_extra_income", 0) or 0) + total
        _bk = state.statistics.get("local_extra_by_kind")
        _bk = dict(_bk) if isinstance(_bk, dict) else {}
        for k, v in by_kind.items():
            if v:
                _bk[k] = int(_bk.get(k, 0) or 0) + v
        state.statistics["local_extra_by_kind"] = _bk
        log.append(f"[地方附加] 坊场钱/经制钱/杂税入府库 {total:,}贯（{len(by_route)} 路）")
    return {"total": total, "by_route": by_route, "by_kind": by_kind}


def _settle_local_expenditure(state, log) -> dict:
    """州郡府库支用（M34-① 批次 1）：**地方官员有效使用**府库资金。

    依据（用户裁决 2026-10-11）：① 财政顺序＝「地方先养活行政/治安/水利 → 剩余上供中央」
    （资金来自 `_settle_land_tax_color` 的**必要支出优先层**）；② 地方政府/官员要能
    **有效使用**府库资金——支用不是纯公式烧钱，而受该路**治理状况**调节：
    有效使用率 `efficacy = 1 − 把持度×w₁ − 欠俸×w₂ − 侵渔`（见 `calc_local_expenditure`）。

    流程（逐路）：现实应支 `due_eff`（＝责任应支 × 玩家保障倍数 × 有效使用率）→ 计划
    `plan_eff = min(due_eff, 府库×cap)` → 按科目比例**逐笔 `transfer_money` 划给本路民间 POP**
    （`official_salary` 官员俸禄／`clerk_pay` 胥吏雇钱 → 官僚；`runner_pay` 衙役雇钱 → 兵；
    `public_supply` 公用钱 → 工匠 40%＋商人 60%）→ 未付部分记
    `statistics["local_arrears"]`（总额）与 `["local_arrears_by_kind"]`（**史实科目分类**），
    并落到**债权人 POP 的 `欠给` 子池**（与 `欠税` 对称；见 §9.10）。

    效果：治安（`runner_pay`）实付按 `LOCAL_EXP_SECURITY_UNREST_PER_POINT` 压该路 `unrest`。

    守恒（POP 挂载律 ⑤）：府库减额 ≡ 民间 POP 增额（`transfer_money` 单点划转，ΣΔ==0）。
    **不并入**国库 `total_out`（不同主体）；国库**同额少付**见 `_settle_finance` 人员腿抵减
    与 `_settle_upkeep` 的水利资产排除（防双重支付）。
    """
    from content.data import (LOCAL_ARREARS_CLERK_MONTHS,
                              LOCAL_ARREARS_DECAY_STEP,
                              LOCAL_ARREARS_GRIEVANCE_STEP,
                              LOCAL_ARREARS_GRIP_STEP,
                              LOCAL_ARREARS_MONTHS_CAP,
                              LOCAL_ARREARS_MORALE_INIT,
                              LOCAL_ARREARS_MORALE_STEP,
                              LOCAL_ARREARS_OFFICIAL_MONTHS,
                              LOCAL_ARREARS_PUBLIC_MONTHS,
                              LOCAL_ARREARS_RUNNER_MONTHS,
                              LOCAL_ARREARS_UNREST_STEP,
                              LOCAL_EXP_ACTIVE_KINDS, LOCAL_EXP_CENTRAL_OFFSET,
                              LOCAL_EXP_PAY_TIERS, LOCAL_EXP_REIMB_SHARE,
                              LOCAL_EXP_SECURITY_UNREST_PER_POINT)
    kinds = tuple(LOCAL_EXP_ACTIVE_KINDS)          # 史实科目（单点词表来自 content）
    _IDENTITY_WEALTH = {"official_salary": "officials_wealth",
                        "clerk_pay": "clerks_wealth"}      # M35-A 记账层
    _IDENTITY_ARREARS = {"official_salary": ("官僚", "officials_salary_arrears"),
                         "clerk_pay": ("官僚", "clerks_pay_arrears"),
                         # 🟢 M35-C-1：役人身份欠给挂**官僚桶**（兵侧字段保留一版兼容）
                         "runner_pay": ("官僚", "runners_pay_arrears")}   # M35-B 身份欠给
    _payout = {"official_salary": (("官僚", 1.0),),          # 官员俸禄 → 官僚
               "clerk_pay": (("官僚", 1.0),),                # 胥吏雇钱 → 官僚（M35 起可分身份层）
               # 🟢 M35-C-1（裁决 D3）：衙役雇钱**改挂官僚桶**（役人由州县支给；衙役非军人）
               "runner_pay": (("官僚", 1.0),),
               "public_supply": (("工匠", 0.4), ("商人", 0.6))}   # 公用钱（营造/水利服务）
    _personnel_kinds = ("official_salary", "clerk_pay", "runner_pay")
    # 🟢 M35-C-1：役人雇钱**记账层**字段（累计流量；不改 POP wealth 真账、不进 m_all）
    _OCCUPATION_INCOME = {"runner_pay": "occupation_income_runner"}
    empty = {"paid": 0, "by_kind": {k: 0 for k in kinds}, "arrears": 0,
             "arrears_by_kind": {k: 0 for k in kinds},
             "arrears_by_identity": {k: 0 for k in ("official_salary", "clerk_pay",
                                                    "runner_pay", "soldier_pay")},
             "papered": 0, "personnel_reimb": 0, "by_route": {}}
    try:
        plan = state.calc_local_expenditure()
    except Exception as _e:                        # noqa: BLE001 — 读数失败不得阻断结账
        log.append(f"[地方经费] 支用读数失败（{type(_e).__name__}），本月不支用")
        return empty
    paid_by_kind = {k: 0 for k in kinds}
    arrears_by_kind = {k: 0 for k in kinds}         # 欠支**分科目**（M34-① 分类欠支）
    # 🟢 M35-B：欠给**身份化**（官员欠俸／胥吏欠钱／衙役欠钱／士卒欠饷＝0，接口留白）
    arrears_by_identity = {k: 0 for k in ("official_salary", "clerk_pay",
                                          "runner_pay", "soldier_pay")}
    papered = 0                                     # 一体发钞下并入交子口径的人员腿
    personnel_reimb = 0
    arrears = 0
    by_route = {}
    _paper_pay = getattr(state, "pay_system", {}).get("mode") == "一体发钞"
    for name, row in plan["by_route"].items():
        due_eff = int(row.get("due_eff", 0))
        target = int(row.get("plan_eff", 0))
        base = {k: int(row.get(k, 0)) for k in kinds}
        tot_base = sum(base.values())
        if due_eff <= 0 or tot_base <= 0:
            continue
        alloc = {k: 0 for k in kinds}
        _p_route = state.prefectures.get(name)
        _p_pops_ref = (_p_route or {}).get("pops") if isinstance(_p_route, dict) else None

        def _pools_now():
            """**每次重新取**路级 POP 镜像：桥接写入会替换镜像对象，缓存引用会失效。"""
            _pp = state.prefectures.get(name)
            return (_pp.get("pops") or {}) if isinstance(_pp, dict) else {}
        # 现实应支 `due_k_eff` ＝ 该科目应支 × (现实应支/责任应支)（已含保障倍数与有效使用率），
        # 尾差给占比最大的科目，保证 Σ due_k_eff ≡ due_eff。**与预算无关**，供欠支/欠月数使用。
        _ratio = (float(due_eff) / float(tot_base)) if tot_base > 0 else 0.0
        due_k_eff = {k: int(base[k] * _ratio) for k in kinds}
        _kbig = max(base, key=lambda k: base[k])
        due_k_eff[_kbig] += due_eff - sum(due_k_eff.values())
        if target > 0:
            # **D7′ 刚性等级**：先按级序把"现实应支"逐级足额，现金用尽后下位级才欠。
            _budget = target
            for _tier in LOCAL_EXP_PAY_TIERS:
                for k in _tier:
                    if k not in alloc or _budget <= 0:
                        continue
                    _give = min(due_k_eff[k], _budget)
                    alloc[k] += _give
                    _budget -= _give
            for k in kinds:                     # 级序未列出的科目（三级/新增）按剩余预算兜底
                if _budget <= 0:
                    break
                if k in [kk for _t in LOCAL_EXP_PAY_TIERS for kk in _t]:
                    continue
                _give = min(due_k_eff[k], _budget)
                alloc[k] += _give
                _budget -= _give
        due_k_eff_used = due_k_eff
        route_paid = 0
        # 🔴 2026-10-20：公用采购「**缺料未成交**」的部分不是欠支。
        # 国家没买到料 ⇒ 不欠任何债权人；旧实现把这段未执行额当欠支（并因
        # `_kind_short` 只按 alloc 算而把差额甩给最大科目 ⇒ 身份欠给虚增）。
        _voided_public = 0
        for k in kinds:
            amt = alloc[k]
            if amt <= 0:
                continue
            # 一体发钞（交子）：人员腿（行政/治安）随俸禄同口径——**不动府库铜钱**
            # （否则同月既发交子又发现钱＝双发造币，见 `test_paper_pay_no_copper_mint`）；
            # 非人员腿（水利营造：工匠/商人服务）仍付现钱。
            if _paper_pay and k in _personnel_kinds:
                papered += amt
                paid_by_kind[k] += amt
                route_paid += amt
                continue
            if k == "public_supply":
                from core.domains.economy.procurement import execute_public_supply_procurement
                proc_res = execute_public_supply_procurement(state, name, amt)
                given = int(proc_res.get("paid_total", 0))
                if given <= 0:
                    # 缺料/无钱 ⇒ 本单未成交：预算额记为「未执行」，不进欠支
                    _voided_public += int(amt)
                    continue
                if given < amt:
                    _voided_public += int(amt) - given
                paid_by_kind[k] += given
                route_paid += given
                continue
            shares = _payout[k]
            given = 0
            for _i, (_cls, _w) in enumerate(shares):
                part = amt - given if _i == len(shares) - 1 else int(amt * _w)
                if part <= 0:
                    continue
                given += state.transfer_money(f"local:{name}", f"pop:{name}:{_cls}", part)
            if given <= 0:
                continue
            paid_by_kind[k] += given
            route_paid += given
            # 🟢 M35-A（身份经济记账层）：官俸→`officials_wealth`／吏禄→`clerks_wealth`
            # 🟢 M35-C-1（occupation 层）：役人雇钱→`occupation_income_runner`（累计流量，不封顶）
            _ident = _IDENTITY_WEALTH.get(k)
            _occ = _OCCUPATION_INCOME.get(k)
            if _occ is not None:
                _pool_occ = _pools_now().get("官僚")
                if isinstance(_pool_occ, dict):
                    if _pop_obj_add(state, _pool_occ, _occ, given) is None:
                        _pool_occ[_occ] = int(_pool_occ.get(_occ, 0) or 0) + given
            if _ident is not None:
                _pool2 = _pools_now().get("官僚")
                if isinstance(_pool2, dict):
                    _pool2.setdefault("officials_wealth", 0)
                    _pool2.setdefault("clerks_wealth", 0)
                    _used = int(_pool2.get("officials_wealth", 0) or 0) \
                        + int(_pool2.get("clerks_wealth", 0) or 0)
                    _room = max(0, int(_pool2.get("wealth", 0) or 0) - _used)
                    _add = min(given, _room)
                    if _add > 0:
                        if _pop_obj_add(state, _pool2, _ident, _add) is None:
                            _pool2[_ident] = int(_pool2.get(_ident, 0) or 0) + _add
            if k in _personnel_kinds:
                personnel_reimb += given
            if k == "runner_pay":
                _p = state.prefectures.get(name)
                if isinstance(_p, dict):
                    _drop = given / float(LOCAL_EXP_SECURITY_UNREST_PER_POINT)
                    _p["unrest"] = max(0.0, round(float(_p.get("unrest", 0) or 0) - _drop, 2))
        # 欠支基准＝**应支** `due_eff`（府库不足或 cap 截断都算欠支，不得静默消失）
        # 但「缺料未成交」的公用采购额要先从应支里扣除（见 `_voided_public`）。
        if _voided_public > 0:
            _cut = min(int(_voided_public), int(due_eff))
            due_eff -= _cut
            if "public_supply" in due_k_eff_used:
                due_k_eff_used["public_supply"] = max(
                    0, int(due_k_eff_used["public_supply"]) - _cut)
        short = due_eff - route_paid
        arrears += short
        _kind_short = {k: 0 for k in kinds}
        if short > 0:
            # M34-①（POP 挂载律）：欠支必须落到**债权人 POP** 的 `欠给` 子池
            # （与 `欠税` 对称：欠税＝POP 欠国家，欠给＝国家欠 POP）；
            # **D7′**：逐科目未付＝该科目现实应支 − 实付（刚性级序下低位科目先欠）。
            _p = state.prefectures.get(name)
            _pops = _pools_now()
            if isinstance(_pops, dict):
                _kind_short = {k: max(0, due_k_eff_used[k] - alloc[k]) for k in kinds}
                _diff = short - sum(_kind_short.values())
                if _diff:
                    _kbig2 = max(base, key=lambda k: base[k])
                    _kind_short[_kbig2] = max(0, _kind_short[_kbig2] + _diff)
                for k in kinds:
                    amt_k = _kind_short[k]
                    if amt_k <= 0:
                        continue
                    arrears_by_kind[k] += amt_k
                    # 🟢 M35-B（欠给身份化）：身份字段——官欠俸／吏欠钱／衙役欠钱
                    _ia = _IDENTITY_ARREARS.get(k)
                    if _ia is not None:
                        _icls, _ikey = _ia
                        _ipool = _pops.get(_icls)
                        if isinstance(_ipool, dict):
                            if _pop_obj_add(state, _ipool, _ikey, amt_k) is None:
                                _ipool[_ikey] = int(_ipool.get(_ikey, 0) or 0) + amt_k
                        arrears_by_identity[k] += amt_k
                    _shares = _payout[k]
                    _given = 0
                    for _i, (_cls, _w) in enumerate(_shares):
                        part = (amt_k - _given if _i == len(_shares) - 1
                                else int(amt_k * _w))
                        _pool = _pops.get(_cls)
                        if not isinstance(_pool, dict) or part <= 0:
                            continue
                        if _pop_obj_add(state, _pool, "欠给", part) is None:
                            _pool["欠给"] = int(_pool.get("欠给", 0) or 0) + part
                        _given += part
        by_route[name] = {"target": target, "paid": route_paid, "arrears": short,
                          "due_eff": due_eff, "arrears_by_kind": _kind_short,
                          "due_k_eff": due_k_eff_used}
        # 🟢 M35-2-A **欠给时间化**（金额与时间分离）：连续欠给月数按月累进／恢复递减；
        #    身份欠给**已清偿**（存量归零）→ 月数清零。1 月欠给与 24 月欠给风险不同。
        if isinstance(_p_route, dict):
            _am = _p_route.get("arrears_months")
            _am = dict(_am) if isinstance(_am, dict) else {}
            for k in kinds:
                _due_k = int(due_k_eff_used.get(k, 0) or 0)
                if _due_k <= 0:
                    continue
                _unpaid_k = int(_kind_short.get(k, 0) or 0)
                _prev = float(_am.get(k, 0.0) or 0.0)
                if _unpaid_k > 0:
                    _am[k] = min(LOCAL_ARREARS_MONTHS_CAP, _prev + 1.0)
                else:
                    _am[k] = max(0.0, _prev - 1.0)
            # 身份层存量归零 ⇒ 视为已清偿，月数清零（"补发即缓解"）
            _pool3 = _pools_now()
            for _cls3, _akey, _k3 in (("官僚", "officials_salary_arrears", "official_salary"),
                                      ("官僚", "clerks_pay_arrears", "clerk_pay"),
                                      ("官僚", "runners_pay_arrears", "runner_pay")):
                _pp3 = _pool3.get(_cls3)
                if isinstance(_pp3, dict) and int(_pp3.get(_akey, 0) or 0) <= 0:
                    _am[_k3] = 0.0
            _p_route["arrears_months"] = _am
    # ---- D5′ 欠费闭环（分层触发）：只写"压力/士气/把持"状态量（**AI/事件的接口**）----
    _pressure = {"clerks_over3": 0, "runners_over3": 0,
                 "officials_over6": 0, "public_over6": 0}
    for name, d in by_route.items():
        _p = state.prefectures.get(name)
        if not isinstance(_p, dict):
            continue
        _aw = d.get("arrears_by_kind") or {}
        _dk = d.get("due_k_eff") or {}

        def _months(k):
            _due = int(_dk.get(k, 0) or 0)
            return (float(_aw.get(k, 0) or 0) / _due) if _due > 0 else 0.0

        if _months("clerk_pay") >= LOCAL_ARREARS_CLERK_MONTHS:
            _cd = _p.get("clerks_detail")
            if isinstance(_cd, dict):
                _cd["grip"] = min(1.0, float(_cd.get("grip", 0.0) or 0.0)
                                  + LOCAL_ARREARS_GRIP_STEP)
                _cd["grievance"] = (float(_cd.get("grievance", 0.0) or 0.0)
                                    + LOCAL_ARREARS_GRIEVANCE_STEP)
            _pressure["clerks_over3"] += 1
        if _months("runner_pay") >= LOCAL_ARREARS_RUNNER_MONTHS:
            _p["unrest"] = min(100.0, round(float(_p.get("unrest", 0) or 0)
                                            + LOCAL_ARREARS_UNREST_STEP, 2))
            _pressure["runners_over3"] += 1
        if _months("official_salary") >= LOCAL_ARREARS_OFFICIAL_MONTHS:
            _p["official_morale"] = max(0.0, round(
                float(_p.get("official_morale", LOCAL_ARREARS_MORALE_INIT)
                      or LOCAL_ARREARS_MORALE_INIT) - LOCAL_ARREARS_MORALE_STEP, 2))
            _pressure["officials_over6"] += 1
        if _months("public_supply") >= LOCAL_ARREARS_PUBLIC_MONTHS:
            _p["public_decay_pressure"] = round(
                float(_p.get("public_decay_pressure", 0) or 0) + LOCAL_ARREARS_DECAY_STEP, 2)
            _pressure["public_over6"] += 1
    if any(_pressure.values()):
        state.statistics["local_arrears_pressure"] = _pressure
        log.append(f"[地方经费] 欠给分层后果：胥吏≥3月 {_pressure['clerks_over3']} 路／"
                   f"衙役≥3月 {_pressure['runners_over3']} 路／"
                   f"官员≥6月 {_pressure['officials_over6']} 路／"
                   f"公用≥6月 {_pressure['public_over6']} 路")
    # **D1′ 中央抵减口径**：责任转移（1.0）——逐科目 `central_offset`（可分别设定，
    # 0.5 中间值留制度改），再乘全局 `LOCAL_EXP_REIMB_SHARE`。地方代付多少，国库少发多少。
    _reimb = 0.0
    for k in _personnel_kinds:
        _off = float((LOCAL_EXP_CENTRAL_OFFSET or {}).get(k, 1.0))
        _reimb += float(paid_by_kind[k]) * _off
    personnel_reimb = int(_reimb * min(1.0, max(0.0, float(LOCAL_EXP_REIMB_SHARE))))
    if arrears > 0:
        state.statistics["local_arrears"] = \
            int(state.statistics.get("local_arrears", 0) or 0) + arrears
        # 分科目欠支（史实口径：official_salary 官员俸禄／clerk_pay 胥吏雇钱／
        # runner_pay 衙役雇钱／public_expense 公用钱——批 1 先有前三项中的两项＋公用）
        _bak = state.statistics.get("local_arrears_by_kind")
        _bak = dict(_bak) if isinstance(_bak, dict) else {}
        for k, v in arrears_by_kind.items():
            if v:
                _bak[k] = int(_bak.get(k, 0) or 0) + v
        state.statistics["local_arrears_by_kind"] = _bak
        # 🟢 M35-B：身份层级欠给累计（官员欠俸／胥吏欠钱／衙役欠钱／士卒欠饷）
        _bai = state.statistics.get("local_arrears_by_identity")
        _bai = dict(_bai) if isinstance(_bai, dict) else {}
        for k, v in arrears_by_identity.items():
            if v:
                _bai[k] = int(_bai.get(k, 0) or 0) + v
        state.statistics["local_arrears_by_identity"] = _bai
    paid_total = sum(paid_by_kind.values())
    if paid_total > 0:
        state.statistics["local_expense_paid"] = \
            int(state.statistics.get("local_expense_paid", 0) or 0) + paid_total
    log.append(f"[地方经费] 支用 {paid_total:,}贯（官俸 {paid_by_kind['official_salary']:,}／"
               f"吏禄 {paid_by_kind['clerk_pay']:,}／衙役 {paid_by_kind['runner_pay']:,}／"
               f"公用 {paid_by_kind['public_supply']:,}）"
               + (f"；交子口径 {papered:,}贯" if papered else "")
               + (f"；欠支 {arrears:,}贯（府库不足）" if arrears else ""))
    return {"paid": paid_total, "by_kind": paid_by_kind, "arrears": arrears,
            "arrears_by_kind": arrears_by_kind,
            "arrears_by_identity": arrears_by_identity,
            "papered": papered, "personnel_reimb": personnel_reimb, "by_route": by_route}


def repay_local_arrears(state, route: str = "", amount: int = 0, source: str = "coffer",
                        kinds=None, log=None, executor=None, strict=None) -> dict:
    """欠给**补发**（M35-3）：财政改善 → 补发欠给 → 压力下降 → 治理恢复的**接口**（**不自动调用**）。

    纪律（裁决 2026-10-11）：
      · **不直接改欠给**：资金一律经 `GameState.transfer_money`（映射 `money.ACCOUNTS`）划转，
        Σ 货币守恒（府库/国库/POP 同在 `m_all` 内）；欠给字段只在**同一笔划转成功后**同步冲减；
      · **来源优先级**：`source="coffer"`（路级府库 surplus，默认）→ `source="treasury"`
        （中央拨款：先 `treasury → local:<路>`，再补发，保持"地方支出"主体性）；
      · **顺序＝D7′ 刚性等级**（`LOCAL_EXP_PAY_TIERS`），`kinds` 可显式指定以体现**制度选择**
        （**不做自动公平分配**）；
      · **效果**：只减 欠给／月数／压力；**不**降 corruption/grip/unrest（"欠钱解决 ≠ 立即清廉"）。
    """
    from content.data import (ARREARS_KEEP_TREASURY, LOCAL_EXP_PAY_TIERS,
                              LOCAL_REPAY_ENABLED, LOCAL_REPAY_KEEP_MONTHS,
                              LOCAL_REPAY_MONTHS_RELIEF)
    _log = log if log is not None else []
    if not LOCAL_REPAY_ENABLED:
        return {"repaid": 0, "by_kind": {}, "by_route": {}, "source": source,
                "skipped": "disabled"}
    _authority_mode = ""
    if source == "treasury":
        if executor:
            from core.authority_gate import check_matter_authority
            _ok, _why = check_matter_authority(state, executor, "度支调度")
            if not _ok:
                return {"repaid": 0, "by_kind": {}, "by_route": {},
                        "source": source, "skipped": "authority_denied",
                        "reason": _why}
            _authority_mode = "actor_position"
        else:
            from core.permission_model import authority_strict
            _strict = authority_strict(state) if strict is None else bool(strict)
            if _strict:
                return {"repaid": 0, "by_kind": {}, "by_route": {},
                        "source": source, "skipped": "authority_denied",
                        "reason": "未指定执行主体（严格模式）"}
            state.statistics["legacy_unchecked_fiscal"] = int(
                state.statistics.get("legacy_unchecked_fiscal", 0) or 0) + 1
            _authority_mode = "legacy_unchecked_fiscal"
    _payout = {"official_salary": (("官僚", 1.0),), "clerk_pay": (("官僚", 1.0),),
               "runner_pay": (("兵", 1.0),),
               "public_supply": (("工匠", 0.4), ("商人", 0.6))}
    _ident_field = {"official_salary": "officials_salary_arrears",
                    "clerk_pay": "clerks_pay_arrears",
                    "runner_pay": "runners_pay_arrears"}
    order = list(kinds) if kinds else [k for _t in LOCAL_EXP_PAY_TIERS for k in _t]
    try:
        due = state.calc_local_expenditure().get("by_route", {})
    except Exception:                       # noqa: BLE001 — 读数失败不得阻断补发
        due = {}

    def _pools_now(name):
        pp = state.prefectures.get(name)
        return (pp.get("pops") or {}) if isinstance(pp, dict) else {}

    def _has_arrears(p):
        for pool in (p.get("pops") or {}).values():
            if isinstance(pool, dict) and int(pool.get("欠给", 0) or 0) > 0:
                return True
        return False

    def _cap(k, cls, pool, w):
        cap = int(pool.get("欠给", 0) or 0)
        cap = int(cap * w) if w < 1.0 else cap
        _f = _ident_field.get(k)
        if _f:
            cap = min(cap, int(pool.get(_f, 0) or 0))
        return max(0, cap)

    def _dec(state_, name, k, cls, got, w):
        """同步冲减：池 `欠给`／身份字段／统计三层；按科目缓解月数（**不触碰 grip/unrest**）。"""
        p = state_.prefectures.get(name)
        if not isinstance(p, dict):
            return
        pool = _pools_now(name).get(cls)
        if isinstance(pool, dict):
            _f = _ident_field.get(k)
            if _f:
                _cur_f = int(pool.get(_f, 0) or 0)
                _new = max(0, _cur_f - got)
                if _pop_obj_add(state_, pool, _f, _new - _cur_f) is None:
                    pool[_f] = _new
            _cur = int(pool.get("欠给", 0) or 0)
            _newd = max(0, _cur - got)
            if _pop_obj_add(state_, pool, "欠给", _newd - _cur) is None:
                pool["欠给"] = _newd
        st = state_.statistics
        st["local_arrears"] = max(0, int(st.get("local_arrears", 0) or 0) - got)
        for _key in ("local_arrears_by_kind", "local_arrears_by_identity"):
            _d = st.get(_key)
            if isinstance(_d, dict) and k in _d:
                _d[k] = max(0, int(_d.get(k, 0) or 0) - got)
                st[_key] = _d
        _am = p.get("arrears_months")
        if isinstance(_am, dict) and k in _am:
            _pool_after = _pools_now(name).get(cls)
            _ident_after = (int(_pool_after.get(_ident_field[k], 0) or 0)
                            if (isinstance(_pool_after, dict) and k in _ident_field) else None)
            if _ident_after is not None and _ident_after <= 0:
                _am[k] = 0.0                       # 该身份已清偿 ⇒ 月数清零
            else:
                _am[k] = max(0.0, float(_am.get(k, 0.0) or 0.0)
                             - float(LOCAL_REPAY_MONTHS_RELIEF))
            p["arrears_months"] = _am

    # --- M35-3 repay main loop ---
    routes = [route] if route else [n for n, p in state.prefectures.items()
                                    if isinstance(p, dict) and _has_arrears(p)]
    repaid_by_kind, by_route = {}, {}
    total = 0
    for name in routes:
        p = state.prefectures.get(name)
        if not isinstance(p, dict):
            continue
        if source == "treasury":
            # 中央拨款：先拨到该路府库（一笔守恒划转，保持"地方支出"主体性）
            avail = max(0, int(getattr(state, "treasury", 0) or 0)
                        - int(ARREARS_KEEP_TREASURY))
            if amount:
                avail = min(avail, int(amount))
            if avail <= 0:
                continue
            avail = state.transfer_money("treasury", f"local:{name}", avail)
        else:
            # 路级府库 surplus：留出 LOCAL_REPAY_KEEP_MONTHS 个月的运营金再补发
            _due_eff = float((due.get(name) or {}).get("due_eff", 0) or 0)
            _keep = int(_due_eff * float(LOCAL_REPAY_KEEP_MONTHS))
            avail = max(0, int(p.get("local_treasury", 0) or 0) - _keep)
            if amount:
                avail = min(avail, int(amount))
        route_paid = 0
        for k in order:
            if avail <= 0:
                break
            for _cls, _w in _payout.get(k, ()):
                if avail <= 0:
                    break
                pool = _pools_now(name).get(_cls)
                if not isinstance(pool, dict):
                    continue
                _cap_k = _cap(k, _cls, pool, _w)
                if _cap_k <= 0:
                    continue
                got = state.transfer_money(f"local:{name}", f"pop:{name}:{_cls}",
                                           min(avail, _cap_k))
                if got <= 0:
                    continue
                avail -= got
                route_paid += got
                repaid_by_kind[k] = repaid_by_kind.get(k, 0) + got
                _dec(state, name, k, _cls, got, _w)
        if route_paid > 0:
            by_route[name] = route_paid
            total += route_paid
    if total > 0:
        state.statistics["local_arrears_repaid"] = \
            int(state.statistics.get("local_arrears_repaid", 0) or 0) + total
        _log.append(f"[欠给补发] {source} → 补发 {total:,}贯（{len(by_route)} 路）")
    result = {"repaid": total, "by_kind": repaid_by_kind, "by_route": by_route,
              "source": source,
              "skipped": "" if total else "no_surplus_or_no_arrears"}
    if source == "treasury":
        result["authority_mode"] = _authority_mode
    return result

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
    # 役钱（徭役代役钱）：税基＝**应役丁**（B1b）——农的丁 × (1 − 佃农占比)；
    # 佃农（客户）无国税/摊派、坊郭户（工匠/商人）不服乡村差役、官户（士绅/官僚）免役、兵免；
    # 坊郭户的科配负担并入工商税（commerce_tax）；隐户不落籍（既不在 size、也不在 ding）。
    from core.foundation.ledger.pop_structure import service_ding_total
    _service_ding = service_ding_total(state)
    poll_tax = int((_service_ding * TAX_POLL_RATIO / 12) * arrival * tax_coeff)
    maritime_tax = int((state.calc_maritime_trade() / 12.0) *
                       (state.maritime.get("tariff", 0.10) if state.maritime.get("open") else 0.0) *
                       arrival * tax_coeff)
    monthly_tax = commerce_tax + poll_tax + maritime_tax
    state.tax_breakdown = {"commerce": commerce_tax, "poll": poll_tax, "maritime": maritime_tax,
                           "official_service": 0}

    # ---- 田赋折色（P1 双层税基·三率分流；Q3 甲：仅此税种换新模型）----
    # 旧径：`calc_monthly_tax_income` 把 arrival 乘进税基——POP 少付、国库少收、截留无落点。
    # 新径：全额税基 → 征收率 → 实收 → 归一三率三分（上供／留州／侵渔，各有落点）。
    # 读数（econ summary / region_brief）暂留旧径，P2「账面系统」统一改造（终稿附 A.2）。
    _land_tax = _settle_land_tax_color(state, log)
    # P2 账面：侵渔额以「损耗」类目入官方账目（真账=吏囊，账面=火耗类损耗；账实落差即"做账"）
    _book_tax_loss(state, int(_land_tax["diverted"]))
    tax_color_total = int(_land_tax["assessed"])      # 展示/日志口径＝应征
    salt_coin = state.calc_salt_coin(arrival)
    material_coin = 0.0
    monthly_tax_full = monthly_tax + tax_color_total + salt_coin + material_coin  # 目标收入（展示/预期）

    # 其余税种征收（旧路径不变·Q3 甲）：役钱→农；工商税→工匠60%+商人40%；盐课+市舶→商人。
    # 士绅保留 0 额条目：让「欠税追缴段」对士绅 POP 照旧运行（行为等价）。
    from content.data import PER_CAPITA_MONTH_GRAIN
    _tax_agents = {
        "农": poll_tax,
        "士绅": 0,
        # 蔡权衡裁决（工匠外销收入源）：工商税工匠份额 0.6→0.5（工匠税负减轻，配合外销变现防破产）
        "工匠": int(commerce_tax * 0.5),
        "商人": int(commerce_tax * 0.5) + int(salt_coin) + maritime_tax,
    }
    # 田赋折色中央份额先入账；其余税种在下方逐户扣缴中累加（实收→国库管道不变）
    actual_tax = float(_land_tax["central"])
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
                if _pop_obj_add(state, _pop, "欠税", _short) is None:
                    _pop["欠税"] = _pop.get("欠税", 0) + _short
            if _pop_obj_add(state, _pop, "wealth", -_paid) is None:
                _pop["wealth"] -= _paid
            actual_tax += _paid   # 累计实际到库税额（保底豁免部分不入库，钱不凭空生）
            # A1 追缴段：紧随税征，按「可支付余力（wealth - 保底线）× ARREARS_COLLECT_RATE」回收欠税
            _recoverable = max(0, _pop["wealth"] - _min_wealth)
            _recover = min(_pop.get("欠税", 0), int(_recoverable * ARREARS_COLLECT_RATE))
            if _recover > 0:
                if _pop_obj_add(state, _pop, "wealth", -_recover) is None:
                    _pop["wealth"] -= _recover
                if _pop_obj_add(state, _pop, "欠税", -_recover) is None:
                    _pop["欠税"] = _pop.get("欠税", 0) - _recover
                actual_tax += _recover

    # ---- M34-① D6′：地方附加收入（独立池，直接入府库）——须在支用腿**之前**入账 ----
    _settle_local_extra_income(state, log)
    # ---- M34-① 批次 1：州郡府库支用（财政顺序改造的**支出腿**；地方官员有效使用）----
    # 必须早于俸禄发放：地方已代付的官俸/兵饷份额需在下文**同额抵减**国库支出（防双重支付）。
    _local_exp = _settle_local_expenditure(state, log)
    _local_reimb = (0 if state.pay_system.get("mode") == "一体发钞"
                    else int(_local_exp.get("personnel_reimb", 0) or 0))

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
    else:
        expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
        # 2026-09-27：原 `cash_out = cash_pay` 赋值后未使用——已删

    corruption_cash_ded, corruption_grain_loss = state.calc_corruption_deduction()
    clerk_gap_total, _ = state.calc_clerk_gap()
    # ---- 审查 M2（用户 2026-10-01 定稿 (a)）：加俸预算 = **真实分账基金**----
    # 原实现：`池 -= used` **且** `total_out += used`，而 `used` 无 POP 入账腿
    #（加俸实际经 `clerk_cash` → `_paid_personnel` 从国库发）⇒ **同一笔钱记两次支出**，
    #   实测月残差 = −2× 消耗（消耗 1 万/月时残差 −2 万/月）。
    # 现口径（完整的「拨入—支出—收款」路径）：
    #   拨入：`commands.allocate_payraise` 国库 → 池（已有）
    #   支出：本月发放**只**从池扣，金额按 `min(池, 吏俸缺口+1万)` 且以**实付**为准
    #   收款：同额经 `transfer_public_funds_to_pops`（受管管线）落到**官僚 POP wealth**
    #   ⇒ 池是钱、`total_out` **不再含它**（避免与国库发薪重复计支出）。
    from content.data import PAYRAISE_PAY_TO
    from core.settlement_common import (
        MoneyChannelUnavailable, note_settlement_error, transfer_public_funds_to_pops,
    )
    _payraise_want = min(state.payraise_budget, int(clerk_gap_total) + 10_000)
    payraise_used = 0
    if _payraise_want > 0:
        try:
            payraise_used = transfer_public_funds_to_pops(
                state, _payraise_want, PAYRAISE_PAY_TO, "加俸月给：诸路官吏俸给",
                source_account="payraise_budget", raise_on_unavailable=True)
        except MoneyChannelUnavailable as _e:
            # 通道坏了 ≠ 池里没钱：显式区分并留痕（不得静默记成"未发放"）
            note_settlement_error(
                state, "payraise_channel", "财政",
                f"加俸发放通道不可用，本月未发（{type(_e).__name__}）", log=log)
    # 注意：**不再手工扣池**。`transfer_public_funds_to_pops` 内部已把
    #   `{path:"payraise_budget", op:"add", value:-实付额}` 交给受管管线执行，
    #   且只在**部分可用**时按 `allocated`（实付额）等额扣减。此处若再
    #   `pool -= payraise_used` 就是**同一条腿扣两次**（与本条修复的原缺陷同类：
    #   池是钱，池的减少只能发生一次、且必须由受管管线记账）。
    #   余额非负由 `state_applier.NON_NEG_PREFIXES` 的 `payraise_budget` 兜住。
    if payraise_used > 0:
        log.append(f"[加俸] 本月应发 {_payraise_want:,} 贯（实付 {payraise_used:,}）"
                   f"给诸路官吏，池余 {int(state.payraise_budget):,} 贯")

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
        # 审查 P2-3 / M8：原静默 `pass` → 岁币外流未登记会被对账算成"凭空销毁"残差。
        from core.settlement_common import register_money_flow
        register_money_flow(state, "burn", int(sui_gong), "岁币岁赐外流")
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
        if _pop_set(_p, "兵", "size", 0) is None:
            _p["pops"]["兵"]["size"] = 0
    for _u in state.army_units:
        if _u.station in state.prefectures and _u.troops > 0:
            _sd = state.prefectures[_u.station]
            if _pop_add(_sd, "兵", "size", _u.troops) is None:
                _sd["pops"]["兵"]["size"] += _u.troops
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
    # M34-① 批次 1：地方已代付的官俸/兵饷份额 → **国库同额少付**（不同主体、不双计；
    # 省下的钱留在国库，正是"地方先养活行政"对中央的减负）。
    _credits_due = max(0, (0 if _paper_pay else personnel_cash) + _civil_back
                       + int(corruption_cash_ded) - _local_reimb)
    _cash_available = max(0, int(state.treasury) + int(actual_tax) - int(sui_gong))
    _pay_scale = 1.0 if _credits_due <= 0 else min(1.0, _cash_available / float(_credits_due))
    _paid_personnel = int((0 if _paper_pay else personnel_cash) * _pay_scale)
    # M34-① 抵减：地方已代付的官俸/兵饷份额（防双重支付）
    _paid_personnel = max(0, _paid_personnel - _local_reimb)
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
                _nw = max(0, _p["pops"]["官僚"]["wealth"] - _take)
                if _pop_set(_p, "官僚", "wealth", _nw) is None:
                    _p["pops"]["官僚"]["wealth"] = _nw
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
                 + _paid_corruption + sui_gong)   # 审查 M2：不再含 payraise_used
    # （加俸已由预算池支付并直接落入官僚 POP，不再是国库支出；计入此处即为重复计账）
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
                _nw = max(0, _art["wealth"] - _take)
                if _pop_obj_set(state, _art, "wealth", _nw) is None:
                    _art["wealth"] = _nw
                _wine_left -= _take
            if _mer["size"] > 0:
                _take = int(_wine_tax_cash * 0.4 * _mer["size"] / _mer_total)
                _take = min(_take, int(_mer["wealth"] * 0.10))
                _nw = max(0, _mer["wealth"] - _take)
                if _pop_obj_set(state, _mer, "wealth", _nw) is None:
                    _mer["wealth"] = _nw
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
    # 🔴 2026-10-17 修复：天道财政安全垫线要的是**本月货币支出**真值。
    # 旧实现只写了读方（`TianDaoFacade.dynamic_treasury_crisis_line` 读
    # `statistics["last_monthly_expense"]`）却**全库没有写入方** ⇒ 该线恒等于
    # 校准基准 5,000,000，"去魔数"实际是空转。现于本处落真实月度支出。
    state.statistics["last_monthly_expense"] = int(total_out)

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

    from core.ai.tiandao_facade import TianDaoFacade
    # 天道动态财政安全垫线：月支出 × 3 个月刚性安全垫（读数见上方
    # `statistics["last_monthly_expense"]`；缺失时才回落校准基准 5,000,000，
    # 来源可由 `TianDaoFacade.crisis_line_source` 诊断）。
    crisis_line = TianDaoFacade.dynamic_treasury_crisis_line(state)
    # B3：判据由「负国库」改为「累计亏空深度」（国库禁穿底，负值不可达）。
    if state.deficit_depth() > crisis_line:
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
    from core.domains.administration import institution as _inst
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
            _nw = w + add
            if _pop_obj_set(state, slot, "wealth", _nw) is None:
                slot["wealth"] = _nw
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


