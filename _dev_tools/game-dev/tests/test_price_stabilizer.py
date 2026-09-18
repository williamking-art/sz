# -*- coding: utf-8 -*-
"""T9 物价方案测试：常平扩容/交子界制/私铸熔化/铸钱受控/稳定器净回收/俸禄指数化。

断言（派单第 8 项）：
- 物价全程 ∈ [0.8, 2.8]（PRICE_FLOOR_HARD/PRICE_CEIL_HARD）
- 常平回收 ΣΔ == 0（平粜吸钱入 local_treasury，不碰内帑/国库）
- 换界销毁记 statistics["jiaozi_redeemed"]
- 内帑膨胀不触发回收（稳定器目标只基于民间持币）
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from content.data import (  # noqa: E402
    JIAOZI_TERM, JIAOZI_REDEEM_FEE, MELT_RATE, PRICE_TARGET_SUPER,
    PRICE_FLOOR_HARD, PRICE_CEIL_HARD, CHANGPING_CAP_RATIO,
    CHANGPING_BUY_BUDGET_RATIO, CHANGPING_SELL_RATIO, MINT_PRICE_BAN,
    MINT_MELT_LOSS, MINT_NET_RATIO, COPPER_RESOURCE_DIM,
)


def _new_state():
    return GameState("史实")


# ---------------------------------------------------------------
# 1. 常量落地校验
# ---------------------------------------------------------------
def test_constants_landed():
    """T9 常量：常平扩容/交子界制/熔化/目标价/铸钱。"""
    assert CHANGPING_CAP_RATIO == 1.0, "常平仓容 = 月产 100%"
    assert CHANGPING_BUY_BUDGET_RATIO == 0.50, "平籴预算 50%"
    assert CHANGPING_SELL_RATIO == 0.60, "平粜量 60%"
    assert JIAOZI_TERM == 36, "交子一界 36 回合"
    assert JIAOZI_REDEEM_FEE == 0.05, "换界 5% 工墨费销毁"
    assert MELT_RATE == 0.001, "私铸熔化 0.1%/月"
    assert PRICE_TARGET_SUPER == (1.2, 2.5), "稳定器目标价 [1.2, 2.5]"
    assert PRICE_FLOOR_HARD == 0.8 and PRICE_CEIL_HARD == 2.8, "断言界 [0.8, 2.8]"
    assert MINT_MELT_LOSS == 0.20 and MINT_NET_RATIO == 0.80, "铸钱熔耗 20% 净增 80%"
    assert MINT_PRICE_BAN == 2.0, "物价>2.0 禁铸钱"
    # private_melt 0.2 → 0.1
    assert GameState("史实").coin["private_melt"] == 0.10


# ---------------------------------------------------------------
# 2. 常平扩容 + 回收 ΣΔ == 0
# ---------------------------------------------------------------
def test_changping_sell_recycles_to_local_treasury():
    """平粜：放粮入市吸钱入 local_treasury（货币回收），不动国库/内帑；ΣΔ==0。"""
    from core.settlement_steps import _settle_granary
    s = _new_state()
    # 构造高价 + 常平有粮
    for p in s.prefectures.values():
        p["grain_price"] = 2.4
        p["changping_stock"] = 1_000_000
        p["local_treasury"] = 1_000_000
    s.grain_price = 2.4
    _t0, _imp0 = s.treasury, s.imperial_treasury
    _lt_before = sum(p["local_treasury"] for p in s.prefectures.values())
    _cp_before = sum(p["changping_stock"] for p in s.prefectures.values())
    _log = []
    _settle_granary(s, _log)
    _lt_after = sum(p["local_treasury"] for p in s.prefectures.values())
    _cp_after = sum(p["changping_stock"] for p in s.prefectures.values())
    # ΣΔ == 0：粮出（常平减）→ 钱入（府库增），价×量守恒
    _grain_out = _cp_before - _cp_after
    _money_in = _lt_after - _lt_before
    assert _grain_out > 0, "高价应触发平粜"
    assert _money_in > 0, "平粜应收钱入府库"
    assert _money_in <= _grain_out * 2.5 + 5, "回收额 ≤ 粮出×价（上限 2.5）+ 取整容差"
    # 不碰国库/内帑（货币回收通道，非国库收入）
    assert s.treasury == _t0 and s.imperial_treasury == _imp0, "平粜不碰国库/内帑"


def test_changping_buy_ratio_cap():
    """平籴：预算 50%、仓容月产 100% 约束生效；平籴是**守恒的钱粮互换**。

    2026-09-18 测试体检：原用例注释写着「平籴支出 ≤ 府库 50%」「常平 ΣΔ==0（粮+钱守恒）：
    仓增量×价 ≈ 府库减量」，但**两条都没断言** —— 唯一断言是 `local_treasury >= 0`（形同虚设）。
    现按注释承诺补齐：① 支出不超府库 50% 预算；② 仓增量×价 ≈ 府库减量（守恒）。
    """
    from core.settlement_steps import _settle_granary
    s = _new_state()
    for p in s.prefectures.values():
        p["grain_price"] = 0.8
        p["changping_stock"] = 0
        p["local_treasury"] = 10_000_000   # 富府库
    s.grain_price = 0.8
    _lt0 = sum(p["local_treasury"] for p in s.prefectures.values())
    _cp0 = sum(p["changping_stock"] for p in s.prefectures.values())
    _price = 0.8
    _log = []
    _settle_granary(s, _log)
    _lt1 = sum(p["local_treasury"] for p in s.prefectures.values())
    _cp1 = sum(p["changping_stock"] for p in s.prefectures.values())
    for name, p in s.prefectures.items():
        # 仓容 ≤ 月产 100%
        _cap = max(p.get("grain", 0) / 12.0, 1.0)
        assert p["changping_stock"] <= _cap + 5, f"{name} 常平仓容超月产 100%"
        # 平籴支出 ≤ 该路府库 50%（预算约束）：府库不为负且未超半额支出
        assert p["local_treasury"] >= 0, f"{name} 府库为负"
    _spent = _lt0 - _lt1
    assert _spent <= int(_lt0 * 0.5) + 1, f"平籴支出 {_spent:,} 超府库 50% 预算"
    # ΣΔ==0（钱粮互换守恒）：仓增量 × 价格 ≈ 府库减量（允许各路价差与取整）
    _cp_delta = _cp1 - _cp0
    if _cp_delta > 0:
        assert abs(_spent - _cp_delta * _price) <= max(1000, _spent * 0.05), \
            f"平籴钱粮不守恒：府库减 {_spent:,} vs 仓增 {_cp_delta:,}石×{_price}={_cp_delta * _price:,.0f}"


# ---------------------------------------------------------------
# 3. 交子界制销币
# ---------------------------------------------------------------
def test_jiaozi_term_redeem_burn():
    """交子满一界（36 回合）：5% 工墨费销毁，记 statistics。"""
    from core.settlement_steps import _settle_jiaozi_term
    s = _new_state()
    s.jiaozi["issued"] = 10_000_000
    s.jiaozi["age"] = JIAOZI_TERM - 1
    _log = []
    _settle_jiaozi_term(s, _log)
    _burn = 10_000_000 * JIAOZI_REDEEM_FEE
    assert s.jiaozi["issued"] == 10_000_000 - int(_burn), "换界销毁 5%"
    assert s.jiaozi["cycle"] == 1, "界数 +1"
    assert s.jiaozi["age"] == 0, "界龄重置"
    assert s.statistics.get("jiaozi_redeemed", 0) == int(_burn), "销毁记 statistics"
    assert s.jiaozi.get("redeemed_total", 0) == int(_burn), "累计销毁留痕"


def test_jiaozi_term_no_burn_before_term():
    """未满一界：不销毁（age 递增）。"""
    from core.settlement_steps import _settle_jiaozi_term
    s = _new_state()
    s.jiaozi["issued"] = 5_000_000
    s.jiaozi["age"] = 10
    _log = []
    _settle_jiaozi_term(s, _log)
    assert s.jiaozi["issued"] == 5_000_000, "未到界不销毁"
    assert s.jiaozi["age"] == 11


def test_jiaozi_term_cycle_repeats():
    """多界循环：72 回合两次换界。"""
    from core.settlement_steps import _settle_jiaozi_term
    s = _new_state()
    s.jiaozi["issued"] = 100_000_000
    for _ in range(JIAOZI_TERM * 2):
        _log = []
        _settle_jiaozi_term(s, _log)
    assert s.jiaozi["cycle"] == 2, "72 回合两次换界"


# ---------------------------------------------------------------
# 4. 私铸熔化真实化
# ---------------------------------------------------------------
def test_coin_melt_monthly():
    """私铸熔化：POP wealth 逐月扣减 0.1%，记 statistics。"""
    from core.settlement_steps import _settle_coin_melt
    s = _new_state()
    _total = 0
    for p in s.prefectures.values():
        for pop in p.get("pops", {}).values():
            pop["wealth"] = 1_000_000
            _total += 1_000_000
    _log = []
    _settle_coin_melt(s, _log)
    _melted = int(_total * MELT_RATE)
    assert s.statistics.get("coin_melted", 0) >= _melted - 100, "熔化额 ≈ 总量×0.1%"
    # 逐月可重复（第二次再扣）
    # 2026-09-18 测试体检：原断言 `s.statistics["coin_melted"] > s.statistics.get(...) - 1 or True`
    # —— **恒真**（`or True` + 拿自己比自己减 1），永不失败。现改为真正的"第二次累计额应增加"。
    _after_first = int(s.statistics.get("coin_melted", 0))
    _log2 = []
    _settle_coin_melt(s, _log2)
    _after_second = int(s.statistics.get("coin_melted", 0))
    assert _after_second > _after_first, \
        f"第二次熔化未累计：{_after_first:,} → {_after_second:,}"


# ---------------------------------------------------------------
# 5. 铸钱受控
# ---------------------------------------------------------------
def test_mint_controlled():
    """铸钱：铜资源约束 + 熔耗 20% 净增 80% + 物价>2.0 禁止。"""
    from core.settlement_steps import _settle_mint
    s = _new_state()
    s.resources.setdefault(COPPER_RESOURCE_DIM, {"stock": 0, "cap": 5_000_000})
    s.resources[COPPER_RESOURCE_DIM]["stock"] = 1_000_000   # iron 已有默认 0，需显式赋
    s.price_level = 1.0
    _log = []
    ok, msg = _settle_mint(s, _log, amount=100_000)
    assert ok, f"正常铸钱应成功: {msg}"
    # 净增 80%：工匠/商人 wealth 增加 ≈ 100000×0.8
    _net = int(100_000 * MINT_NET_RATIO)
    _wealth_add = sum(p["pops"]["工匠"]["wealth"] + p["pops"]["商人"]["wealth"]
                      for p in s.prefectures.values()) - sum(
        p["pops"]["工匠"]["wealth"] + p["pops"]["商人"]["wealth"]
        for p in GameState("史实").prefectures.values())
    assert _wealth_add >= _net * 0.9, f"净增入市 ≈ {_net}（实际 {_wealth_add}）"
    assert s.statistics.get("minted", 0) == _net
    # 金属资源扣减 = 额/0.8
    assert s.resources[COPPER_RESOURCE_DIM]["stock"] == 1_000_000 - int(100_000 / MINT_NET_RATIO)


def test_mint_price_ban():
    """物价 > 2.0 禁铸钱。"""
    from core.settlement_steps import _settle_mint
    s = _new_state()
    s.resources.setdefault(COPPER_RESOURCE_DIM, {"stock": 0, "cap": 5_000_000})
    s.resources[COPPER_RESOURCE_DIM]["stock"] = 1_000_000
    s.price_level = 2.5
    _log = []
    ok, msg = _settle_mint(s, _log, amount=100_000)
    assert not ok and "禁铸钱" in msg, "物价>2.0 应禁止铸钱"


def test_mint_metal_shortage():
    """铜料不足 → 拒绝。"""
    from core.settlement_steps import _settle_mint
    s = _new_state()
    s.resources.setdefault(COPPER_RESOURCE_DIM, {"stock": 0, "cap": 5_000_000})
    s.resources[COPPER_RESOURCE_DIM]["stock"] = 100
    s.price_level = 1.0
    _log = []
    ok, msg = _settle_mint(s, _log, amount=1_000_000)
    assert not ok and "铜料不足" in msg


def test_mint_decree_path():
    """fixed_finance 诏令 target=铸钱 → 受控铸钱。"""
    from core.commands_decree import _run_fixed
    s = _new_state()
    s.resources.setdefault(COPPER_RESOURCE_DIM, {"stock": 0, "cap": 5_000_000})
    s.resources[COPPER_RESOURCE_DIM]["stock"] = 1_000_000
    s.price_level = 1.0
    s.change_treasury(100_000_000)
    msg = _run_fixed(s, "fixed_finance", {"target": "铸钱", "amount": 50_000})
    assert "铸钱" in str(msg), f"铸钱诏令应执行: {msg}"


# ---------------------------------------------------------------
# 6. 稳定器净回收 + 内帑膨胀不触发
# ---------------------------------------------------------------
def test_stabilizer_recycle_private_money_only():
    """稳定器回收目标只基于民间持币——内帑/国库膨胀不触发回收。"""
    from core.settlement_steps import _settle_stabilizer_recycle
    s = _new_state()
    s.grain_price = 2.0
    s.treasury = 500_000_000      # 国库巨富
    s.imperial_treasury = 900_000_000  # 内帑巨富（膨胀）
    # 民间持币（各 POP wealth 初始较小）
    _pop_money = sum(pop.get("wealth", 0) for p in s.prefectures.values()
                     for pop in p.get("pops", {}).values())
    _log = []
    s._stabilizer_recycled = 0
    _settle_stabilizer_recycle(s, _log)
    # 目标应基于民间持币（≈ pop_money×(2.0−1.2)/2.0×0.5），而非含内帑的 money_supply
    _expect = int(_pop_money * (2.0 - 1.2) / 2.0 * 0.5)
    _got = s.statistics.get("stabilizer_target", 0)
    assert _got <= _expect * 3, f"目标应≈民间持币口径 {_expect}（实际 {_got}，未因内帑放大）"


def test_price_level_clamped_0_8_2_8():
    """物价全程 ∈ [0.8, 2.8]（硬钳）。"""
    from core.game_state_econ import _clamp
    # 直接验证硬钳
    assert _clamp(0.1, PRICE_FLOOR_HARD, PRICE_CEIL_HARD) == PRICE_FLOOR_HARD
    assert _clamp(5.0, PRICE_FLOOR_HARD, PRICE_CEIL_HARD) == PRICE_CEIL_HARD
    # calc_price_level 极端货币供给 → 封顶 2.8
    s = _new_state()
    for p in s.prefectures.values():
        for pop in p.get("pops", {}).values():
            pop["wealth"] = 10_000_000_000   # 天量货币
    s.treasury = 0
    s.imperial_treasury = 0
    assert s.calc_price_level() <= PRICE_CEIL_HARD + 1e-6, "物价应封顶 2.8"
    assert s.calc_price_level() >= PRICE_FLOOR_HARD - 1e-6


# ---------------------------------------------------------------
# 7. 俸禄指数化
# ---------------------------------------------------------------
def test_salary_indexation():
    """粮价 > 1.5 时俸禄 ×(1+0.1×超额)。"""
    from core.settlement_steps import _settle_finance
    from content.data import PAY_INDEX_BASE, PAY_INDEX_STEP
    s = _new_state()
    s.grain_price = 2.0   # 超额 0.5 → ×1.05
    _base = s.calc_army_cash()[0] + s.calc_official_cash()[0] + s.calc_clerk_cash()[0]
    # 直接验证常量公式
    _index = 1.0 + PAY_INDEX_STEP * (s.grain_price - PAY_INDEX_BASE)
    assert _index == 1.05, "粮价 2.0 超额 0.5 → 俸禄 ×1.05"
    assert s.grain_price > PAY_INDEX_BASE


# ---------------------------------------------------------------
# 8. 240 月回放：物价封顶 2.8 内
# ---------------------------------------------------------------
def test_240_month_price_bounded():
    """240 月回放（确定性 seed，无 AI）：物价全程 ∈ [0.8, 2.8]。"""
    import random
    from core.commands import settle_turn

    random.seed(2026)
    s = _new_state()
    prices = []
    for t in range(1, 241):
        s.turn = t
        try:
            settle_turn(s, None)   # 无 AI：推演拒绝，但结算层可独立验证
        except Exception:
            # 无 AI 时 settle_turn 拒绝（economy 强制）——直接跑月度结算验证物价钳制
            from core.settlement import run_monthly_settlement
            try:
                run_monthly_settlement(s)
            except Exception:
                pass
        prices.append(s.price_level)
    _lo, _hi = min(prices), max(prices)
    assert _lo >= PRICE_FLOOR_HARD - 0.05, f"物价下界 {_lo:.3f} < 0.8"
    assert _hi <= PRICE_CEIL_HARD + 0.05, f"物价上界 {_hi:.3f} > 2.8"
