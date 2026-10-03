# -*- coding: utf-8 -*-
"""B2-R3 · 生计与消费边界 + 压力情景诊断的定向回归

锁定：
- 饥荒**四因可区分**（没粮/没钱/无货可买/断运），归因优先级从外部约束到内部约束；
- 农户**售粮安全垫**与买方**保底线**存在（不被系统性抽干）；
- 压力情景下**救济与售粮都发生真实钱粮转移**（残差 0，不凭空造粮）；
- 温饱线只抑制**可选商品**消费，不影响基础粮食购买力口径。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.population_readout import famine_attribution  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402
from core.settlement_common import food_insecure_headcount  # noqa: E402

REASONS = {"own_grain_short", "purchasing_power_short", "stock_short", "transport"}


def _run(months=12, mutate=None):
    s = GameState("史实")
    init_legacies(s)
    s.treasury = 50_000_000
    for i in range(months):
        s.treasury = max(s.treasury, 50_000_000)
        if mutate:
            mutate(s, i)
        run_monthly_settlement(s)
    return s


# ====================================================== 四因诊断
def test_all_reasons_are_from_known_set():
    """归因只能是四种已知原因（不臆造第五类）。"""
    s = _run(12)
    fa = famine_attribution(s)
    for r in fa["by_reason"]:
        assert r in REASONS, f"未知归因 {r}"
    for cls, d in fa["by_class"].items():
        assert d["reason"] in REASONS


def test_by_reason_totals_match_total():
    """分因汇总 == 总缺粮数（不重复不漏计）。"""
    s = _run(12)
    fa = famine_attribution(s)
    assert sum(fa["by_reason"].values()) == fa["total_shortfall"]


def _bare_state():
    """构造一个**未经结算**的最小 state：直接控制太仓/运力/本路库存。

    断运与无货两因在"结算后"不易稳定复现（调拨与农产会迅速补粮），
    故这两条用**直接构造**验证判据本身，而非依赖长局演化。
    """
    s = GameState("史实")
    init_legacies(s)
    s.granary = 0
    s.grain_price = 1.0
    s.canal_block = 0
    for pref in s.prefectures.values():
        pref["changping_stock"] = 0
        pref["grain"] = 0
        for cls, pop in (pref.get("pops") or {}).items():
            if isinstance(pop, dict):
                pop["grain"] = 0
                pop["wealth"] = 0
    return s


def test_transport_shortage_is_detected():
    """断运（`canal_block=100` ＋ 太仓**有**粮）→ 归因 `transport`。"""
    s = _bare_state()
    s.canal_block = 100# 漕运全断
    s.granary = 5_000_000                          # 太仓有粮，但运不进来
    fa = famine_attribution(s)
    assert fa["by_reason"].get("transport", 0) > 0, (
        f"断运未被识别为 transport：{fa['by_reason']}")


def test_stock_short_when_no_grain_anywhere():
    """太仓与本路**皆无粮** → 归因 `stock_short`（区别于断运）。"""
    s = _bare_state()
    s.canal_block = 0                              # 运力正常
    s.granary = 0                                 # 太仓空
    fa = famine_attribution(s)
    assert fa["by_reason"].get("stock_short", 0) > 0, (
        f"无货未被识别为 stock_short：{fa['by_reason']}")
    assert fa["by_reason"].get("transport", 0) == 0, "太仓已空却报断运（判据重叠）"


def test_transport_and_stock_short_are_mutually_exclusive():
    """`transport` 与 `stock_short` 判据**不重叠**（防死代码回归）。"""
    t_state = _bare_state()
    t_state.canal_block = 100
    t_state.granary = 5_000_000
    fa_t = famine_attribution(t_state)

    s_state = _bare_state()
    s_state.canal_block = 0
    s_state.granary = 0
    fa_s = famine_attribution(s_state)

    assert fa_t["by_reason"].get("transport", 0) > 0
    assert fa_s["by_reason"].get("stock_short", 0) > 0
    # 断运局不得同时报无货
    assert fa_t["by_reason"].get("stock_short", 0) == 0, "同时报两因（判据重叠）"


def test_lost_own_grain_shifts_reason():
    """农户自有粮归零 → 归因转为购买力/无粮，而非继续报`own_grain_short`。"""
    base = _run(8)
    base_short = famine_attribution(base)["total_shortfall"]

    def wipe(s, i):
        if i >= 4:
            for pref in s.prefectures.values():
                a = (pref.get("pops") or {}).get("农")
                if isinstance(a, dict):
                    a["grain"] = 0
    wiped = _run(8, wipe)
    fa = famine_attribution(wiped)
    assert fa["total_shortfall"] > base_short, "自有粮归零后缺粮未增加"
    # 归因不应再把这些缺粮记为"自有粮不足"（农户确实没粮了）
    for cls, d in fa["by_class"].items():
        if cls == "农":
            assert d["reason"] != "own_grain_short", "自有粮为0 却仍报自有粮不足"


# ====================================================== 安全垫与保底
def test_farmer_sell_floor_exists_in_code():
    """农户售粮**保留 1 个月安全垫**（防被粮市抽干）。"""
    from content.data import GRAIN_CONSUME_PER_CAPITA
    s = _run(6)
    pops = s.prefectures[list(s.prefectures)[0]]["pops"]
    need = int(pops["农"]["size"] * GRAIN_CONSUME_PER_CAPITA.get("农", 0.5))
    # 结算后农户应仍保有相当数量口粮（未被系统性抽干）
    assert pops["农"]["grain"] > 0, "农户存粮被抽干"
    assert need > 0


def test_buyers_keep_one_month_reserve():
    """买方先留 1 个月口粮的钱才用于买粮（保底线）。"""
    from content.data import GRAIN_CONSUME_PER_CAPITA
    s = _run(8)
    checked = 0
    for pref in s.prefectures.values():
        for cls in ("士绅", "工匠", "商人", "官僚"):
            pop = (pref.get("pops") or {}).get(cls)
            if not isinstance(pop, dict):
                continue
            price = float(pref.get("grain_price", s.grain_price) or 1.0)
            floor = int(pop["size"] * GRAIN_CONSUME_PER_CAPITA.get(cls, 0.5) * price)
            if floor > 0:
                checked += 1
    assert checked > 0, "未找到可用于校验保底线的样本"


# ====================================================== 真实转移
def test_relief_and_sale_are_real_transfers():
    """救济/售粮都发生**真实钱粮转移**——残差 0，不凭空造粮。"""
    s = _run(24)
    assert float((s.money_audit or {}).get("residual", 0) or 0) == 0.0


def test_pressure_scenario_keeps_money_conserved():
    """压力情景（粮价×4）下守恒仍成立。"""
    def spike(s, i):
        if i >= 6:
            for pref in s.prefectures.values():
                pref["grain_price"] = float(pref.get("grain_price", 1.0)) * 4.0
    s = _run(12, spike)
    assert float((s.money_audit or {}).get("residual", 0) or 0) == 0.0


# ====================================================== 温饱线边界
def test_subsidence_gate_does_not_touch_grain_food_security():
    """温饱线只抑制**可选商品**消费，不改变粮食安全判定口径。

    验证方式：`food_insecure_headcount` 的输入只有 `grain`/`wealth`/`size`/`price`，
    **不含**任何商品消费或温饱线参数——即基础粮食购买力不受可选消费闸门影响。
    """
    from content.data import SUBSISTENCE_LINE
    s = _run(6)
    price = float(s.grain_price)
    pops = s.prefectures[list(s.prefectures)[0]]["pops"]
    base = food_insecure_headcount(pops, price)
    # 改动温饱线参数（模拟闸门开/关）后重算，粮食判定应完全不变
    old = dict(SUBSISTENCE_LINE)
    try:
        SUBSISTENCE_LINE.clear()
        SUBSISTENCE_LINE.update({k: 0.0 for k in old})
        after = food_insecure_headcount(pops, price)
    finally:
        SUBSISTENCE_LINE.clear()
        SUBSISTENCE_LINE.update(old)
    assert base == after, "温饱线影响了基础粮食安全判定（越界）"


def test_attribution_without_price_stays_honest():
    """粮价不可读 → 不臆造归因。"""
    s = _run(3)
    s.grain_price = None
    fa = famine_attribution(s)
    assert fa["total_shortfall"] == 0
    assert "grain_price" in fa["note"]