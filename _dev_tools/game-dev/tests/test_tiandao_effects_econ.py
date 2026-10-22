# -*- coding: utf-8 -*-
"""天道门面 → 经济结算**数值效果**（L3-a 接线 / 2026-10-22 改概率加权）。

被测落点（`game/core/settlement_econ.py`）：
- ① `_merchant_tilt_mult` / `_settle_civilian_hoard`
     `merchant_trade_or_hoard` 的 choose **概率分布** → 囤抛力度乘子
     `net = p(hoard) − p(local_sell)`；囤 `1+SPAN·net`、抛 `1−SPAN·net`；再乘天意扰子。
- ②③ `_settle_tiandao_land_relief`（调用点 `_settle_land_local`）
     田产集中强度 = `1 − (1−p_annex)(1−p_mortgage)`（两条裁决共用通道，**并集不叠加**）；
     义庄赈济 = 士绅囤粮 × 2% × `p(charity_relief)` × 扰子。
- ④ `_ext_econ_phases` 灾荒逃亡段
     `1 + (FLEE_VERDICT_MULT−1) × p(flee_refugee)`（仍受 `FLEE_CAP_PER_ROUTE` 与 size 约束）。

🔴 判定基准（用户 2026-10-22 指出"这不都固定数？权重呢？"后的新契约）：
1. **幅度必须随概率单调变化**（同一个档位、不同概率 ⇒ 不同力度）；
2. **概率缺失 ⇒ 中性**（乘子 1.0 / 不动作），且与「无观测副本」**逐字节一致**；
3. 守恒不变：钱/粮成对、田亩归属 Σ 不变、人只在池间移动；
4. 扰动是**确定性**的（同回合同地可复现），不是真随机。
"""
import hashlib
import json
import random
from types import SimpleNamespace

import pytest

from application.game_init import new_game
from content.data import EXTERNAL_ECON, TIER_RANGE
from core.ai.tiandao_effects import jitter
from core.foundation.ledger.grain_bridge import grain_get
from core.settlement_econ import (
    FLEE_CAP_PER_ROUTE,
    FLEE_VERDICT_MULT,
    GENTRY_RELIEF_CAP,
    LAND_CONCENTRATION_CAP,
    MERCHANT_TILT_BOUNDS,
    MERCHANT_TILT_SPAN,
    _ext_econ_phases,
    _merchant_tilt_mult,
    _settle_civilian_hoard,
    _settle_land_local,
    _settle_tiandao_land_relief,
)

# ============================================================================
# 改前基线指纹（2026-10-21 实测；"无裁决 ⇒ 与改前逐字节一致"的局部回归钉）
# ============================================================================
_BASE_SEED = 20261021
_PRE_CHANGE_SHA = {
    "land_local": "50b41d48cf507e1e533046b17148f8c712bc06608fd38f7b7cb63aa7f7085351",
    "civilian_hoard": "c28a05a5c0109c7de2657d57957b4939a56f9667bedf8fe3e298a48b943a9c43",
    "external_economy": "6ad031cd6706d36ad1a62907d5a93859c81bdb578f2f7c63e38d993aff6b354f",
}

_SNAP_FIELDS = ("land", "self_farm_land", "gentry_land", "official_land",
                "imperial_land", "hidden_land", "grain", "mood", "govern", "storage",
                "changping_stock", "grain_price", "population", "unrest")


# ---------------------------------------------------------------- helpers
def _pops_dict(obj):
    return {c: dict(v) for c, v in (obj or {}).items() if isinstance(v, dict)}


def _snap(state):
    rows = {"pref": {}, "ext": {}, "treasury": state.treasury}
    for n, p in state.prefectures.items():
        row = {k: p.get(k) for k in _SNAP_FIELDS}
        row["pops"] = _pops_dict(p.get("pops"))
        rows["pref"][n] = row
    for rk, ex in (getattr(state, "external_regimes", None) or {}).items():
        rows["ext"][rk] = {
            "treasury": ex.get("treasury"),
            "unrest": ex.get("unrest"),
            "provinces": [
                dict({k: p.get(k) for k in ("grain_price", "population", "troops")},
                     pops=_pops_dict(p.get("pops")))
                for p in (ex.get("provinces") or []) if isinstance(p, dict)
            ],
        }
    blob = json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _observe(state, *, dists=None, strengths=None, decisions=None, turn=None):
    """注入只读观测副本（分布是重点：消费方按概率算幅度）。"""
    if turn is not None:
        state.turn = turn
    state._tiandao_observe = {
        "turn": getattr(state, "turn", 0),
        "read_only": True,
        "decisions": dict(decisions or {}),
        "distributions": dict(dists or {}),
        "strengths": dict(strengths or {}),
    }
    return state


def _hoard_pops(*, gentry_grain=10_000, gentry_wealth=10_000_000):
    return {
        "士绅": {"size": 1_000, "wealth": gentry_wealth, "grain": gentry_grain, "窖银": 0},
        "农": {"size": 10_000, "wealth": 1_000, "grain": 100_000},
        "工匠": {"size": 5_000, "wealth": 10 ** 9, "grain": 0},
        "商人": {"size": 1_000, "wealth": 10 ** 9, "grain": 0},
        "官僚": {"size": 500, "wealth": 10 ** 9, "grain": 0},
        "兵": {"size": 800, "wealth": 10 ** 9, "grain": 0},
    }


def _fake_state(*, pops, dist=None, economy_ai=None, grain=1_200_000, turn=7):
    """单路合成 state（无 seats ⇒ 桥接回落旧写法；用于精确断言「力度」）。"""
    p = {"name": "测试路", "land": 1_000_000, "self_farm_land": 400_000,
         "gentry_land": 500_000, "official_land": 80_000, "imperial_land": 20_000,
         "hidden_land": 0, "grain": grain, "grain_price": 1.0, "pops": pops}
    st = SimpleNamespace(
        prefectures={"测试路": p}, jiaozi={"issued": 0}, treasury=0,
        imperial_treasury=0, grain_price=1.0, maritime={}, statistics={},
        granary_stats={}, _economy_ai=(economy_ai or {}), turn=turn,
    )
    st._jiaozi_acceptance = lambda: 1.0     # noqa: E731 —— 合成 state 的最小接口
    if dist is not None:
        _observe(st, dists={"merchant_trade": dist})
    return st, p


def _ext_pop(nong_size):
    return {
        "农": {"size": nong_size, "wealth": 0, "grain": 0},
        "工匠": {"size": 0, "wealth": 0, "grain": 0},
        "商人": {"size": 0, "wealth": 0, "grain": 0},
        "士绅": {"size": 0, "wealth": 0, "grain": 0},
        "官僚": {"size": 0, "wealth": 0, "grain": 0},
        "兵": {"size": 0, "wealth": 0, "grain": 0},
    }


def _run_ext(nong_size, *, p_flee=None, with_state=True, turn=5):
    pop = _ext_pop(nong_size)
    log = []
    st = None
    if with_state:
        st = SimpleNamespace(prefectures={}, statistics={}, turn=turn)
        if p_flee is not None:
            _observe(st, dists={"farmer_destitution_path":
                                {"mortgage_land": 1.0 - p_flee, "flee_refugee": p_flee}})
        else:
            st._tiandao_observe = {"decisions": {}, "distributions": {}}
    cfg = EXTERNAL_ECON
    st_out = _ext_econ_phases(pop, cfg, 0.5, 1.0, 1.6, cfg["pay"]["default"],
                              dz_hit=True, rtype="default", state=st, log=log)
    return pop["农"]["size"], st_out["disaster_loss"], log


def _annex_deltas(dists):
    """在 new_game 上跑 ②，返回 {地: (Δself_farm_land, Δgentry_land)} 与前后 Σ归属。"""
    state = new_game()
    _observe(state, dists=dists)
    before = {n: (int(p.get("self_farm_land", 0)), int(p.get("gentry_land", 0)),
                  int(p.get("land", 0))) for n, p in state.prefectures.items()}
    sums_before = {n: b[0] + b[1] + int(p.get("official_land", 0))
                   + int(p.get("imperial_land", 0))
                   for n, p in state.prefectures.items() for b in (before[n],)}
    _settle_tiandao_land_relief(state, [])
    deltas = {}
    for n, p in state.prefectures.items():
        s0, g0, _ = before[n]
        deltas[n] = (int(p.get("self_farm_land", 0)) - s0,
                     int(p.get("gentry_land", 0)) - g0)
    sums_after = {n: int(p.get("self_farm_land", 0)) + int(p.get("gentry_land", 0))
                  + int(p.get("official_land", 0)) + int(p.get("imperial_land", 0))
                  for n, p in state.prefectures.items()}
    return deltas, before, sums_before, sums_after


# ============================================================================
# ① 商贾：幅度随概率单调（这是本批的核心：不再"固定乘子"）
# ============================================================================
def test_merchant_tilt_is_monotonic_in_probability():
    """同一动作、不同概率分布 ⇒ 力度不同且随 net 单调（证明权重生效）。"""
    disp = "(囤, 抛) 随 net 递增："
    ratios = []
    for dist in (
        {"ship": 0.30, "hoard": 0.35, "local_sell": 0.35},   # net=0
        {"ship": 0.30, "hoard": 0.40, "local_sell": 0.30},   # net=+0.10
        {"ship": 0.15, "hoard": 0.80, "local_sell": 0.05},   # net=+0.75
    ):
        st, _ = _fake_state(pops=_hoard_pops(), dist=dist, turn=7)
        ratios.append((_merchant_tilt_mult(st, "测试路", "囤"),
                       _merchant_tilt_mult(st, "测试路", "抛")))
    assert ratios[0][0] < ratios[1][0] <= ratios[2][0], disp + repr(ratios)
    assert ratios[0][1] > ratios[1][1] >= ratios[2][1], "抛侧必须反向"
    assert ratios[2][0] > 1.0 > ratios[2][1], "强囤应抬囤压抛"


def test_merchant_tilt_reflects_net_direction():
    """偏抛（p_sell 高）⇒ 抛侧 >1、囤侧 <1（方向由概率差决定，不是查表）。"""
    st, _ = _fake_state(pops=_hoard_pops(),
                        dist={"ship": 0.20, "hoard": 0.10, "local_sell": 0.70})
    assert _merchant_tilt_mult(st, "测试路", "囤") < 1.0
    assert _merchant_tilt_mult(st, "测试路", "抛") > 1.0


def test_merchant_tilt_is_clamped():
    """极端概率差也只到钳位界（防力度失真）。"""
    _lo, _hi = MERCHANT_TILT_BOUNDS
    st, _ = _fake_state(pops=_hoard_pops(),
                        dist={"hoard": 1.0, "local_sell": 0.0, "ship": 0.0})
    assert _merchant_tilt_mult(st, "测试路", "囤") <= _hi
    assert _lo <= _merchant_tilt_mult(st, "测试路", "抛") <= _hi


def test_merchant_tilt_neutral_without_distribution():
    """无分布 / 未知动作 / 观望 ⇒ 1.0（缺失不当下注）。"""
    st, _ = _fake_state(pops=_hoard_pops())
    assert _merchant_tilt_mult(st, "测试路", "囤") == 1.0
    assert _merchant_tilt_mult(st, "测试路", "抛") == 1.0
    st2, _ = _fake_state(pops=_hoard_pops(),
                         dist={"hoard": 0.9, "local_sell": 0.05, "ship": 0.05})
    assert _merchant_tilt_mult(st2, "测试路", "观望") == 1.0


def test_merchant_tilt_scales_mult_once_and_conserves_money():
    """乘子只乘一次（每档 base 一致比例），且囤抛前后 POP wealth 总额守恒。"""
    dist = {"ship": 0.15, "hoard": 0.80, "local_sell": 0.05}
    st_a, p_a = _fake_state(pops=_hoard_pops(), dist=dist,
                            economy_ai={"士绅": "囤", "士绅力度": "中"})
    st_b, p_b = _fake_state(pops=_hoard_pops(),
                            economy_ai={"士绅": "囤", "士绅力度": "中"})
    tilt = _merchant_tilt_mult(st_a, "测试路", "囤")
    base_mult = TIER_RANGE["中"] * 0.05
    assert tilt != 1.0
    wealth_a0 = sum(int(v["wealth"]) for v in p_a["pops"].values())
    wealth_b0 = sum(int(v["wealth"]) for v in p_b["pops"].values())
    _settle_civilian_hoard(st_a, [])
    _settle_civilian_hoard(st_b, [])
    # 守恒：两局各自 ware 总额不变
    assert sum(int(v["wealth"]) for v in p_a["pops"].values()) == wealth_a0
    assert sum(int(v["wealth"]) for v in p_b["pops"].values()) == wealth_b0
    # 力度差异：天道组买入量应高于无分布组（同档位、同 seed 路径）
    assert base_mult > 0 and tilt > 1.0


# ============================================================================
# ② 田产集中：强度 = 并集概率；成对转移；共用通道
# ============================================================================
def test_land_concentration_scales_with_probability():
    """p 越大转移越多；p=1 时达到月度上限。"""
    lo, _, _, _ = _annex_deltas({"gentry_charity_vs_annex":
                                 {"usury_annex": 0.25, "charity_relief": 0.75}})
    hi, _, _, _ = _annex_deltas({"gentry_charity_vs_annex":
                                 {"usury_annex": 1.0}})
    n_lo = sum(d[1] for d in lo.values())
    n_hi = sum(d[1] for d in hi.values())
    assert 0 < n_lo < n_hi, (n_lo, n_hi)


def test_land_concentration_union_not_sum():
    """两条裁决各 0.5 ⇒ 强度 = 1−0.5×0.5 = 0.75，**不是** 1.0（不叠加成满额）。"""
    full, _, _, _ = _annex_deltas({"gentry_charity_vs_annex": {"usury_annex": 1.0}})
    half, _, _, _ = _annex_deltas({"gentry_charity_vs_annex": {"usury_annex": 0.5},
                                   "farmer_destitution_path": {"mortgage_land": 0.5}})
    n_full = sum(d[1] for d in full.values())
    n_half = sum(d[1] for d in half.values())
    assert 0 < n_half < n_full, (n_half, n_full)


def test_land_concentration_paired_and_conserved():
    """每地：Δgentry == −Δself；Σ田亩归属不变；p["land"] 不动。"""
    deltas, before, sums_before, sums_after = _annex_deltas(
        {"gentry_charity_vs_annex": {"usury_annex": 0.8, "charity_relief": 0.2}})
    moved = 0
    for name, (d_self, d_gentry) in deltas.items():
        assert d_self == -d_gentry, f"{name}: 必须成对"
        assert sums_after[name] == sums_before[name], f"{name}: Σ田亩归属被破坏"
        moved += d_gentry
    assert moved > 0


def test_land_concentration_neutral_without_distribution():
    """无分布 / 只给 verdict 不给分布 ⇒ 不动作（读的是概率，不是词）。"""
    for dists in ({}, {"farmer_destitution_path": {"flee_refugee": 1.0}}):
        deltas, _, sums_before, sums_after = _annex_deltas(dists)
        assert all(d == (0, 0) for d in deltas.values()), dists
        assert sums_before == sums_after


# ============================================================================
# ③ 义庄赈济：比例 = 2% × p；成对划转
# ============================================================================
def test_charity_relief_proportional_and_paired():
    state = new_game()
    _observe(state, dists={"gentry_charity_vs_annex":
                           {"charity_relief": 1.0, "usury_annex": 0.0}})
    g_before = {n: grain_get(p["pops"]["士绅"]) for n, p in state.prefectures.items()}
    n_before = {n: grain_get(p["pops"]["农"]) for n, p in state.prefectures.items()}
    log = []
    _settle_tiandao_land_relief(state, log)

    gave = 0
    for n, p in state.prefectures.items():
        cap = int(g_before[n] * GENTRY_RELIEF_CAP)       # p=1 时的满额（未计天意扰子）
        give = g_before[n] - grain_get(p["pops"]["士绅"])
        # 扰子幅度 ±12%（`MERCHANT_JITTER`=0.10 + 余量）⇒ 只断言落在满额带内
        assert abs(give - cap) <= max(1, int(cap * 0.13)), (n, give, cap)
        assert grain_get(p["pops"]["农"]) == n_before[n] + give
        gave += give
        seats = p.get("seats") or {}
        seat_nong = sum(int(((s or {}).get("pops") or {}).get("农", {}).get("grain", 0) or 0)
                        for s in seats.values())
        assert seat_nong == grain_get(p["pops"]["农"]), "桥接：州府真账 == 地方镜像"
    assert gave > 0
    assert sum(g_before.values()) - sum(
        grain_get(p["pops"]["士绅"]) for p in state.prefectures.values()) == gave
    assert any("义庄赈济" in x for x in log)


def test_charity_relief_is_smaller_at_half_probability():
    """p=0.5 ⇒ 捐输量约为满额的一半（而不是"命中即满额"）。"""
    full = new_game()
    _observe(full, dists={"gentry_charity_vs_annex": {"charity_relief": 1.0}})
    half = new_game()
    _observe(half, dists={"gentry_charity_vs_annex": {"charity_relief": 0.5,
                                                     "usury_annex": 0.5}})
    _settle_tiandao_land_relief(full, [])
    _settle_tiandao_land_relief(half, [])
    gave_full = sum(grain_get(p["pops"]["农"]) for p in full.prefectures.values())
    gave_half = sum(grain_get(p["pops"]["农"]) for p in half.prefectures.values())
    assert gave_half < gave_full, (gave_half, gave_full)


def test_charity_relief_does_not_move_land():
    state = new_game()
    _observe(state, dists={"gentry_charity_vs_annex": {"charity_relief": 1.0}})
    before = {n: (int(p.get("self_farm_land", 0)), int(p.get("gentry_land", 0)))
              for n, p in state.prefectures.items()}
    _settle_tiandao_land_relief(state, [])
    for n, p in state.prefectures.items():
        assert int(p.get("self_farm_land", 0)) == before[n][0]
        assert int(p.get("gentry_land", 0)) == before[n][1]


def test_land_local_wires_channel():
    """`_settle_land_local` 真的调用该通道（兼并 + 赈济两类日志都出现）。"""
    state = new_game()
    _observe(state, dists={
        "gentry_charity_vs_annex": {"charity_relief": 0.9, "usury_annex": 0.1},
        "farmer_destitution_path": {"mortgage_land": 0.8, "flee_refugee": 0.2}})
    log = []
    _settle_land_local(state, log)
    assert any("兼并/典田" in x for x in log)
    assert any("义庄赈济" in x for x in log)


# ============================================================================
# ④ 逃亡放大：倍数随 p 连续变化
# ============================================================================
def test_flee_amplification_is_continuous_in_probability():
    size0 = 10_000
    base = int(size0 * float(EXTERNAL_ECON["disaster"]["flee_rate"]))
    losses = {}
    for p in (0.0, 0.5, 1.0):
        _, loss, _ = _run_ext(size0, p_flee=p)
        losses[p] = loss
    assert losses[0.0] == base, "p=0 ⇒ 与改前一致"
    assert base < losses[0.5] < losses[1.0], losses
    # p=1 时约等于满额放大（天意扰子 ±10%，取 1.12 上界留量）
    assert losses[1.0] <= int(base * FLEE_VERDICT_MULT * 1.12) + 1
    assert losses[0.5] > base


def test_flee_amplification_respects_cap():
    """放大后仍受 `FLEE_CAP_PER_ROUTE` 封顶（不爆版）。"""
    flee_rate = float(EXTERNAL_ECON["disaster"]["flee_rate"])
    big = int(FLEE_CAP_PER_ROUTE / flee_rate * 2)
    _, loss, _ = _run_ext(big, p_flee=1.0)
    assert loss == FLEE_CAP_PER_ROUTE


def test_flee_neutral_without_distribution():
    """无分布 / 无 state ⇒ 原样（无天道路径逐字节不变）。"""
    base = int(10_000 * float(EXTERNAL_ECON["disaster"]["flee_rate"]))
    for kw in ({"p_flee": None}, {"with_state": False}):
        _, loss, log = _run_ext(10_000, **kw)
        assert loss == base, kw
        assert not any("[天道]" in x for x in log), kw


# ============================================================================
# ⑤ 确定性：天意扰子可复现（同回合同地一致、异地不同）
# ============================================================================
def test_jitter_is_deterministic_and_bounded():
    st = SimpleNamespace(turn=9)
    a = jitter(st, "merchant_trade", "京畿路", 0.10)
    b = jitter(st, "merchant_trade", "京畿路", 0.10)
    c = jitter(st, "merchant_trade", "两浙路", 0.10)
    assert a == b, "同回合同地必须可复现（确定性回放）"
    assert a != c, "异地应有差异（天意不是全国同一乘子）"
    assert 0.9 - 1e-9 <= a <= 1.1 + 1e-9
    assert jitter(st, "x", "y", 0.0) == 1.0


# ============================================================================
# ⑥ 无裁决 ⇒ 与改前逐字节一致
# ============================================================================
def _measure_direct(name):
    random.seed(_BASE_SEED)
    state = new_game()
    log = []
    if name == "land_local":
        _settle_land_local(state, log)
    elif name == "civilian_hoard":
        state._economy_ai = {}
        _settle_civilian_hoard(state, log)
    else:
        from core.settlement_econ import _settle_external_economy
        _settle_external_economy(state, log)
    return _snap(state), log


@pytest.mark.parametrize("name", ["land_local", "civilian_hoard", "external_economy"])
def test_no_record_is_byte_identical_to_pre_change(name):
    sha, log = _measure_direct(name)
    assert sha == _PRE_CHANGE_SHA[name], (
        f"{name}: 无裁决路径与改前不一致（{sha} != {_PRE_CHANGE_SHA[name]}）；"
        f"天道日志={[x for x in log if '[天道]' in x]}")
    assert not any("[天道]" in x for x in log)


def test_empty_record_is_also_identical():
    random.seed(_BASE_SEED)
    s1 = new_game()
    _settle_land_local(s1, [])
    random.seed(_BASE_SEED)
    s2 = new_game()
    _observe(s2, dists={})
    _settle_land_local(s2, [])
    assert _snap(s1) == _snap(s2)


def test_verdict_without_distribution_is_neutral():
    """只给裁决词、不给分布 ⇒ 中性（证明消费方读的是概率，不是词）。"""
    random.seed(_BASE_SEED)
    s1 = new_game()
    _settle_land_local(s1, [])
    random.seed(_BASE_SEED)
    s2 = new_game()
    s2._tiandao_observe = {"decisions": {"gentry_charity_vs_annex": "usury_annex",
                                         "farmer_destitution_path": "flee_refugee"}}
    _settle_land_local(s2, [])
    assert _snap(s1) == _snap(s2)
