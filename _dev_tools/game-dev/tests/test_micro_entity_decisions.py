# -*- coding: utf-8 -*-
"""测试微观主体决策门面（官吏催科严厉度与商帮物资运作）。

验证目标：
1. 官吏决策逻辑（清廉爱民与灾荒倾向 lenient；库空且贪酷倾向 strict；平稳倾向 moderate）；
2. 商帮决策逻辑（谷贱防灾倾向 hoard；高价求售倾向 dump；平稳观望倾向 hold）；
3. 容错降级保护：在输入畸形或异常时，100% 优雅降级且不崩溃；
4. 真实月度结算中的 POP 挂载与货币守恒闭环（ΔM_ALL == 0）。
"""
import pytest
from application.game_init import new_game
from core.ai.clerk_decision import decide_clerk_enforcement, ClerkDecision
from core.ai.merchant_decision import decide_merchant_operation, MerchantDecision
from core.domains.administration.settlement_officialdom import _settle_clerks
from core.settlement_econ import _settle_civilian_hoard
from core.foundation.ledger.pop_bridge import pop_obj_add


def test_clerk_decision_logic():
    """验证官吏催科倾向在不同情境下的理性裁定。"""
    state = new_game()
    p = state.prefectures["两浙路"]

    # 1. 灾情严重且官员清廉 -> 倾向宽恩抚民 (lenient)
    p["disaster_level"] = 0.8
    p["mood"] = 30.0
    p["governor"] = {"integrity": 0.9, "diligence": 0.8}
    dec_lenient = decide_clerk_enforcement(state, p)
    assert dec_lenient.mode == "lenient"
    assert dec_lenient.mult < 1.0
    assert dec_lenient.mood_delta > 0

    # 2. 国库极度亏空且官员廉洁度低 -> 倾向严厉催科 (strict)
    state.treasury = 5000
    p["disaster_level"] = 0.0
    p["mood"] = 70.0
    p["governor"] = {"integrity": 0.2, "diligence": 0.9}
    dec_strict = decide_clerk_enforcement(state, p)
    assert dec_strict.mode == "strict"
    assert dec_strict.mult > 1.0
    assert dec_strict.mood_delta < 0

    # 3. 畸形输入 -> 优雅降级 (moderate)
    dec_fallback = decide_clerk_enforcement(None, {})
    assert dec_fallback.mode == "moderate"
    assert dec_fallback.mult == 1.0


def test_merchant_decision_logic():
    """验证商帮物资投机在不同物价与仓储下的理性博弈。"""
    state = new_game()
    rname = next(iter(state.prefectures.keys()))
    p = state.prefectures[rname]

    # 1. 粮价极低 (0.4) 且丰收 -> 囤粮居奇 (hoard)
    p["grain_price"] = 0.4
    state.grain_price = 0.4
    p["disaster_level"] = 0.0
    dec_hoard = decide_merchant_operation(state, p)
    assert dec_hoard.action == "hoard"

    # 2. 粮价高企 (2.2) -> 乘时发粜 (dump)
    p["grain_price"] = 2.2
    state.grain_price = 1.0
    dec_dump = decide_merchant_operation(state, p)
    assert dec_dump.action == "dump"

    # 3. 畸形输入 -> 优雅降级 (hold)
    dec_fallback = decide_merchant_operation(None, {})
    assert dec_fallback.action == "hold"


def test_clerk_settlement_conservation():
    """验证官吏催科在结算执行中的货币绝对守恒（ΔM_ALL == 0）。"""
    from core import money
    state = new_game()
    log = []

    m0 = money.m_all(state)
    _settle_clerks(state, log)
    m1 = money.m_all(state)

    # 陋规是从民间三池到官僚池的纯转移，国库/内帑不变，M_ALL 完全守恒
    assert abs(m1 - m0) < 1e-4, f"官吏催科结算破坏全局货币守恒: ΔM = {m1 - m0}"


def test_civilian_hoard_conservation():
    """验证商帮/士绅囤抛在微观决策驱动下的 POP 挂载与账本平衡。"""
    from core import money
    state = new_game()
    log = []

    # 模拟未配置外部全局 AI（触发微观决策门面）
    state._economy_ai = {}

    m0 = money.m_all(state)
    _settle_civilian_hoard(state, log)
    m1 = money.m_all(state)

    # 囤抛为民间内部钱粮互换，M_ALL 完全守恒
    assert abs(m1 - m0) < 1e-4, f"商帮物资运作破坏全局货币守恒: ΔM = {m1 - m0}"
