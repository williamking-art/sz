# -*- coding: utf-8 -*-
"""地基断言（2026-09-27，先量后改的那三条）：

  A. 结算**不污染全局随机流**，且同回合+同 offset **仍可复现**；
  B. `money._num` 对 inf/-inf/nan **回落默认**（防非法 JSON 与面板显示 inf）；
  C. 倒闭粮田的产粮**与 lv1 等价**（把"实测结论"变成回归网：若有人改成 building_level
     而动了平衡，这条会提醒他这是有意为之的口径）。
"""
import math
import os
import random
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import money                                    # noqa: E402
from core.building_jobs import produce_grain_track        # noqa: E402
from core.game_state import GameState                     # noqa: E402
from core.settlement import run_monthly_settlement        # noqa: E402


def test_settlement_does_not_pollute_global_rng():
    """**地基 A**：结算前后，全局随机流的后续取值必须一致（对外零副作用）。"""
    random.seed(12345)
    baseline = [random.random() for _ in range(3)]

    random.seed(12345)
    run_monthly_settlement(GameState("史实"), seed_offset=0)
    after = [random.random() for _ in range(3)]

    assert baseline == after, (
        "结算污染了全局随机流：调用方/其它模块的随机不再独立"
        f"\n  未跑结算 {baseline}\n  跑过结算 {after}")


def test_settlement_still_reproducible_per_turn():
    """**地基 A（另一半）**：还原不得破坏"同回合+同 offset 可复现"这一回放基础。"""
    l1 = run_monthly_settlement(GameState("史实"), seed_offset=7)
    l2 = run_monthly_settlement(GameState("史实"), seed_offset=7)
    assert l1 == l2, "同回合同 offset 的结算日志应完全一致（replay/A-B 的前提）"


def test_money_num_rejects_non_finite():
    """**地基 B**：非有限值回落默认（否则读数出 inf、JSON 出 Infinity/NaN）。"""
    for bad in (float("inf"), float("-inf"), float("nan")):
        got = money._num(bad, 7.0)
        assert isinstance(got, float) and math.isfinite(got) and got == 7.0, \
            f"_num({bad!r}) 应为 7.0，实得 {got!r}"
    assert money._num("abc", 7.0) == 7.0 and money._num(None, 7.0) == 7.0
    assert money._num(3.5, 7.0) == 3.5, "正常值不得被改"


def test_money_readout_stays_finite_with_inf_injection():
    """**地基 B（端到端）**：把 inf 灌进 state 后，读数仍是有限值（不会漏到 API/存档）。"""
    s = GameState("史实")
    s.jiaozi = {"issued": float("inf"), "circulating": float("nan")}
    for fn in ("jiaozi_issued",):
        v = getattr(money, fn)(s)
        assert math.isfinite(v), f"{fn} 返回了非有限值 {v!r}"


def test_closed_farmland_is_equivalent_to_level_one_by_design():
    """**地基 C（把实测结论固化成网）**：倒闭粮田与 lv1 **等价**（不惩罚），lv5 才高。

    早先审计写"倒闭建筑仍计产"，实测为误判：`eff = 1 + 0.05*max(0, lv-1)` 使 lv0 ≡ lv1。
    本断言的作用：若有人把该读点改成 `building_level`（closed→0）并**改动平衡**，
    这条会失败并提醒"这是有意口径，改动需另行拍板"。
    """
    pops = {"农": {"size": 100_000, "grain": 0}}
    cfg = {"FARM_LV_EFF": 0.05}
    g1 = produce_grain_track({"农": {"size": 100_000, "grain": 0}}, {"粮田": 1}, cfg, 1.0)
    gc = produce_grain_track({"农": {"size": 100_000, "grain": 0}},
                             {"粮田": {"lv": 0, "closed": True}}, cfg, 1.0)
    g5 = produce_grain_track({"农": {"size": 100_000, "grain": 0}}, {"粮田": 5}, cfg, 1.0)
    assert gc == g1, f"倒闭粮田应等同 lv1（当前 g1={g1} gc={gc}）"
    assert g5 > g1, "等级加成应随等级上升"
    assert pops  # 传入的 pops 不被本函数修改语义（占位，避免未用告警）
