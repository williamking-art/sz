# -*- coding: utf-8 -*-
"""天道门面 → 财政/变法数值：**概率连续**（B1-a，2026-10-22）。

背景（外部审查阻断项 B1）：`core/ai/README.md` 契约第 14 条禁止「argmax 档位 → 查固定倍率表」，
要求 choose 走 `observe_mix`（方向取概率差）、gate 走 `observe_strength`（超阈强度）、
缺失 ⇒ 中性、允许种子派生的 `jitter`。本批把财政域 3 个消费点改成连续：

- ① `settlement_finance._tax_stance_factor`
     `factor = 1 + TAX_STANCE_MAX_DELTA(0.03) × (p_strict − p_lenient) × jitter`
- ② `settlement_finance._arrears_waiver_ratio`（原 `_arrears_waiver_active`）
     `ratio = observe_strength("waive_arrears") ∈ [0,1]`；核销 `int(存量×0.10×ratio)`、
     追缴 `×(1−ratio)`
- ③ `settlement_decree._reform_compliance_factor`
     `factor = 0.5 + 0.5 × observe_strength("reform_compliance")`

两条硬要求（Lead 指定）：
1. **缺失语义不得悄悄改变**：无 `_tiandao_observe` ⇒ 与改前**逐字节一致**（下 `_PRE_CHANGE_SHA`
   是改前实测指纹）；唯一刻意的变更 = "只有 verdict、没有 strengths/distributions 的旧副本"
   现在按「未观测到强度 ⇒ 中性」处理（不把布尔断重回填成倍率，否则恢复档位表）。
2. **中性 ⇒ 精确恒等**：概率差 0 / 强度 0 时不吃 `jitter`（D2），且行为与缺失同支。
"""
import hashlib
import json
import random

import pytest

from application.game_init import new_game
from core.ai.tiandao_effects import jitter
from core.settlement_decree import (
    REFORM_COMPLIANCE_FLOOR,
    _apply_decree_effect,
    _reform_compliance_factor,
)
from core.settlement_finance import (
    TAX_STANCE_JITTER_ENTROPY,
    TAX_STANCE_MAX_DELTA,
    WAIVER_WRITEOFF_CAP,
    _arrears_waiver_ratio,
    _settle_finance,
    _settle_land_tax_color,
    _tax_stance_factor,
)

# ============================================================================
# 2026-10-22 改前基线指纹（本批改动**之前**实测；`_snap` 与基线脚本同口径）
# 用途：钉住「无观测副本 ⇒ 与改前逐字节一致」。若其它域数值改动导致漂移，按同口径重测。
# ============================================================================
_SEED = 20261022
_PRE_CHANGE_SHA = {
    "land_tax_norecord": "6862cf12d9981b7a7b50e3e1025f7f1fe6d4460e8475b13b02a6590ce674bfdf",
    "finance_norecord": "48903783bc2a521fb12f0db465dcd4f8291d3453fa53c6ff2a4460da06a0f63f",
    "finance_arrears_norecord":
        "7f3ead13c0e3d9490b5d95fa1198185054bd55124a7789c96f9076fef930346d",
    "reform_norecord": "8eca54a1a9cdc8d8d225439ddf6f2ae597dbea3fb61d874d0c859d3f1c3d2e9b",
}


# ---------------------------------------------------------------- helpers
class _S:
    """空 state（无 `_tiandao_observe`）。"""


def _mk(record=None, turn=5):
    s = _S()
    s.turn = turn
    if record is not None:
        s._tiandao_observe = record
    return s


def _tax_dist(strict, moderate, lenient):
    return {"distributions": {"tax_stance": {"strict": strict, "moderate": moderate,
                                            "lenient": lenient}}}


def _strength(objective, p):
    return {"strengths": {objective: p}}


def _pops(obj):
    return {c: dict(v) for c, v in (obj or {}).items() if isinstance(v, dict)}


def _snap(state, extra=None):
    rows = {"treasury": state.treasury,
            "imperial": getattr(state, "imperial_treasury", None),
            "granary": getattr(state, "granary", None),
            "finance": dict(getattr(state, "finance", {}) or {}),
            "tax_breakdown": dict(getattr(state, "tax_breakdown", {}) or {}),
            "pref": {}, "extra": extra}
    for n, p in state.prefectures.items():
        row = {k: p.get(k) for k in ("local_treasury", "grain", "storage", "mood", "unrest")}
        row["pops"] = _pops(p.get("pops"))
        rows["pref"][n] = row
    blob = json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _run_land_tax(record=None):
    random.seed(_SEED)
    s = new_game()
    if record is not None:
        s._tiandao_observe = record
    res = _settle_land_tax_color(s, [])
    return _snap(s, {k: res[k] for k in sorted(res) if isinstance(res[k], (int, float))}), res


def _run_finance(record=None, arrears=0):
    """无裁决/带记录各跑一遍月度财政，返回 (指纹, state, log)。

    ⚠️ `arrears` 用**路级直写**：这与改前基线脚本同口径（只用于"逐字节一致"钉），
    不代表真账——语义断言请用 `_run_finance_bridged`（欠税经 `pop_bridge` 落州府真账）。
    """
    random.seed(_SEED)
    s = new_game()
    if arrears:
        for p in s.prefectures.values():
            p["pops"]["农"]["欠税"] = arrears
    if record is not None:
        s._tiandao_observe = record
    log = []
    _settle_finance(s, log)
    return _snap(s, {"log_len": len(log), "logs": log}), s, log


def _total_arrears(state):
    return sum(int(p["pops"]["农"].get("欠税", 0) or 0) for p in state.prefectures.values())


def _run_finance_bridged(record=None, arrears=1_000_000):
    """语义用：欠税经 `pop_bridge` 写入（州府真账 + 刷新路级镜像），避免"直写镜像被撤销"。"""
    from core.foundation.ledger.pop_bridge import pop_obj_add

    random.seed(_SEED)
    s = new_game()
    for p in s.prefectures.values():
        pop_obj_add(s, p["pops"]["农"], "欠税", arrears)
    if record is not None:
        s._tiandao_observe = record
    log = []
    _settle_finance(s, log)
    return s, log


def _run_reform(record=None):
    random.seed(_SEED)
    s = new_game()
    if record is not None:
        s._tiandao_observe = record
    log = []
    _apply_decree_effect(s, {"effects": {"finance_rates": {"collection_rate": 0.10}}}, log)
    return _snap(s, {"log_len": len(log), "logs": log}), s, log


def _waive_total(log):
    """从蠲免日志里取回核销总量（无蠲免日志 ⇒ 0）。"""
    for line in log:
        if "蠲免" in line and "核销欠税存量" in line:
            num = line.split("核销欠税存量")[-1].strip().split(" ")[0].replace(",", "")
            return int(num)
    return 0


# ============================================================================
# ① 中性 ⇒ 精确恒等（不吃扰子）
# ============================================================================
def test_tax_stance_zero_probability_diff_is_exactly_one_across_turns():
    """(p_strict == p_lenient) ⇒ factor **恰为 1.0**，且不随回合抖动（D2：扰子只乘增量）。"""
    for turn in range(0, 13):
        s = _mk(_tax_dist(0.3, 0.4, 0.3), turn=turn)
        assert _tax_stance_factor(s) == 1.0, turn
    # 至少一个回合上扰子非 1 —— 证明上面的"不吃扰子"不是因为扰子恒为 1
    assert any(jitter(_mk(turn=t), "tax_stance", "全国", TAX_STANCE_JITTER_ENTROPY) != 1.0
               for t in range(0, 13))


def test_tax_stance_missing_and_partial_mix_are_neutral():
    """无副本 / 无 distributions / 只观测到一端 ⇒ 1.0（不补 0 当"确定不选"）。"""
    assert _tax_stance_factor(_S()) == 1.0
    assert _tax_stance_factor(_mk({})) == 1.0
    assert _tax_stance_factor(_mk({"decisions": {"tax_collection_stance": "strict"}})) == 1.0
    assert _tax_stance_factor(_mk({"distributions": {"tax_stance": {"strict": 0.9}}})) == 1.0
    assert _tax_stance_factor(_mk({"distributions": {"tax_stance": {"lenient": 0.9}}})) == 1.0
    assert _tax_stance_factor(_mk({"distributions": {"other": {"a": 1.0}}})) == 1.0


def test_waiver_ratio_zero_at_or_below_threshold():
    """缺失 / 恰在判定线 / 低于判定线 ⇒ 0.0（= 不蠲免，与改前"无记录"同支）。"""
    assert _arrears_waiver_ratio(_S()) == 0.0
    assert _arrears_waiver_ratio(_mk({})) == 0.0
    assert _arrears_waiver_ratio(_mk(_strength("waive_arrears", 0.50))) == 0.0
    assert _arrears_waiver_ratio(_mk(_strength("waive_arrears", 0.49))) == 0.0
    assert _arrears_waiver_ratio(_mk(_strength("waive_arrears", 0.0))) == 0.0


def test_reform_factor_one_when_missing_and_turn_invariant():
    """缺失 ⇒ 1.0；同一强度不随回合变（无扰子），且强度 0 恰为 floor 0.5。"""
    assert _reform_compliance_factor(_S()) == 1.0
    assert _reform_compliance_factor(_mk({})) == 1.0
    assert _reform_compliance_factor(
        _mk({"decisions": {"reform_compliance_gate": True}})) == 1.0
    vals = {_reform_compliance_factor(_mk(_strength("reform_compliance", 0.8), turn=t))
            for t in range(0, 13)}
    assert vals == {0.8}
    assert _reform_compliance_factor(_mk(_strength("reform_compliance", 0.5))) \
        == REFORM_COMPLIANCE_FLOOR


def test_neutral_settlement_is_byte_identical_to_pre_change():
    """无观测副本 / 概率差 0 / 强度 0 ⇒ 三条结算路径的状态指纹 == **改前实测值**。"""
    sha, _ = _run_land_tax()
    assert sha == _PRE_CHANGE_SHA["land_tax_norecord"]
    # 中性概率（严格差 0）必须与"无副本"完全同路
    sha2, _ = _run_land_tax(_tax_dist(0.3, 0.4, 0.3))
    assert sha2 == sha

    sha3, _, log3 = _run_finance()
    assert sha3 == _PRE_CHANGE_SHA["finance_norecord"]
    sha4, _, log4 = _run_finance(_strength("waive_arrears", 0.5))
    assert sha4 == sha3 and _waive_total(log4) == 0 and not any("蠲免" in x for x in log4)

    sha5, _, _ = _run_finance(arrears=1_000_000)
    assert sha5 == _PRE_CHANGE_SHA["finance_arrears_norecord"]

    sha6, _, _ = _run_reform()
    assert sha6 == _PRE_CHANGE_SHA["reform_norecord"]


def test_verdict_only_legacy_record_is_now_neutral_and_documented():
    """**刻意变更**（已报告）：只有 verdict、没有概率块的旧副本 ⇒ 中性（= 无副本）。

    理由：把布尔断重回填成倍率就是 B1 禁止的「档位 → 固定倍率表」。生产路径
    `observe_monthly` 与 `decisions` 同批写 `strengths`/`distributions`，故实机等价。
    """
    _, v_strict = _run_land_tax({"decisions": {"tax_collection_stance": "strict"}})
    _, none = _run_land_tax()
    assert v_strict["assessed"] == none["assessed"]
    assert _tax_stance_factor(_mk({"decisions": {"tax_collection_stance": "strict"}})) == 1.0

    _, _, log_reform = _run_reform({"decisions": {"reform_compliance_gate": False}})
    _, _, log_none = _run_reform()
    assert not any("天道新政遵从度" in x for x in log_reform)
    assert log_reform == log_none
    assert _reform_compliance_factor(
        _mk({"decisions": {"reform_compliance_gate": False}})) == 1.0

    assert _arrears_waiver_ratio(
        _mk({"decisions": {"should_waive_ancient_arrears": True}})) == 0.0


# ============================================================================
# ② 同档不同概率 ⇒ 幅度不同（B1 的核心：档位不再是开关）
# ============================================================================
def test_tax_stance_same_argmax_different_probability_different_magnitude():
    """同为 strict 占优（同一"档位"），概率差不同 ⇒ 幅度不同；且随概率差单调。"""
    _lo = _tax_stance_factor(_mk(_tax_dist(0.50, 0.30, 0.20), turn=5))
    _hi = _tax_stance_factor(_mk(_tax_dist(0.90, 0.05, 0.05), turn=5))
    assert _lo > 1.0 and _hi > 1.0
    assert _hi > _lo, (_lo, _hi)
    # 同 turn ⇒ 同一扰子，故幅度差完全由概率差造成
    assert abs((_hi - 1.0) - TAX_STANCE_MAX_DELTA * 0.85
               * jitter(_mk(turn=5), "tax_stance", "全国", TAX_STANCE_JITTER_ENTROPY)) < 1e-12
    assert abs((_lo - 1.0) - TAX_STANCE_MAX_DELTA * 0.30
               * jitter(_mk(turn=5), "tax_stance", "全国", TAX_STANCE_JITTER_ENTROPY)) < 1e-12
    # 反向：lenient 概率差 ⇒ 因子 < 1
    _down = _tax_stance_factor(_mk(_tax_dist(0.05, 0.05, 0.90), turn=5))
    assert _down < 1.0
    # 扰动是确定性的：同 (回合, 目标, 地点) 同结果
    assert _hi == _tax_stance_factor(_mk(_tax_dist(0.90, 0.05, 0.05), turn=5))


def test_tax_stance_assessed_continuous_at_settlement_level():
    """结算级：strict 占优 ⇒ 应征额↑、lenient 占优 ⇒ ↓、中性 ⇒ 与无副本一致（连续，非跳档）。"""
    _, base = _run_land_tax()
    _, mid = _run_land_tax(_tax_dist(0.50, 0.30, 0.20))
    _, strong = _run_land_tax(_tax_dist(0.90, 0.05, 0.05))
    _, weak = _run_land_tax(_tax_dist(0.20, 0.30, 0.50))
    assert base["assessed"] < mid["assessed"] < strong["assessed"]
    assert weak["assessed"] < base["assessed"]


def test_reform_same_gate_true_different_probability_different_magnitude():
    """同为 gate 通过（p>0.5），p=0.6 与 p=0.95 的改革幅度不同，且线性于 p。"""
    f6 = _reform_compliance_factor(_mk(_strength("reform_compliance", 0.6)))
    f95 = _reform_compliance_factor(_mk(_strength("reform_compliance", 0.95)))
    assert 0.5 < f6 < f95 < 1.0
    assert f6 == pytest.approx(0.6)
    assert f95 == pytest.approx(0.95)

    random.seed(_SEED)
    s1 = new_game()
    s1._tiandao_observe = _strength("reform_compliance", 0.6)
    b1 = float(s1.finance["collection_rate"])
    _apply_decree_effect(s1, {"effects": {"finance_rates": {"collection_rate": 0.10}}}, [])
    d6 = float(s1.finance["collection_rate"]) - b1

    random.seed(_SEED)
    s2 = new_game()
    s2._tiandao_observe = _strength("reform_compliance", 0.95)
    b2 = float(s2.finance["collection_rate"])
    _apply_decree_effect(s2, {"effects": {"finance_rates": {"collection_rate": 0.10}}}, [])
    d95 = float(s2.finance["collection_rate"]) - b2

    assert abs(d6 - 0.06) < 1e-9 and abs(d95 - 0.095) < 1e-9
    assert d95 > d6


def test_waiver_same_gate_true_different_probability_different_writeoff():
    """同为门闸通过，p=0.6(强度0.2) 与 p=0.9(强度0.8) 的核销额不同，且 ≈ 强度比例。"""
    r6 = _arrears_waiver_ratio(_mk(_strength("waive_arrears", 0.6)))
    r9 = _arrears_waiver_ratio(_mk(_strength("waive_arrears", 0.9)))
    assert r6 == pytest.approx(0.2) and r9 == pytest.approx(0.8)

    s6, log6 = _run_finance_bridged(_strength("waive_arrears", 0.6))
    s9, log9 = _run_finance_bridged(_strength("waive_arrears", 0.9))
    w6, w9 = _waive_total(log6), _waive_total(log9)
    assert w6 > 0 and w9 > w6
    # 核销额 ≈ 强度比例（逐 POP 取整 ⇒ 允许 ≤ 2×POP 数的取整误差：0.8/0.2 = 4 倍）
    _n_pop = sum(1 for p in s6.prefectures.values() for _ in p["pops"])
    assert abs(w9 - w6 * 4) <= 2 * _n_pop, (w6, w9)
    # 强度越高 ⇒ 核销越多 ⇒ 期末欠税越少（同初始欠税、同 seed；此处分母是核销而非追缴）
    assert _total_arrears(s9) < _total_arrears(s6)
    # 无蠲免（强度 0）⇒ 期末欠税最高，且无蠲免日志
    s0, log0 = _run_finance_bridged(_strength("waive_arrears", 0.5))
    assert _waive_total(log0) == 0 and not any("蠲免" in x for x in log0)
    assert _total_arrears(s0) > _total_arrears(s6)


def test_waiver_magnitude_capped_by_constant():
    """核销上限 = 存量 × WAIVER_WRITEOFF_CAP × 强度（强度 1.0 才 10%，永不超过）。"""
    assert WAIVER_WRITEOFF_CAP == 0.10
    s, log = _run_finance_bridged(_strength("waive_arrears", 1.0))
    total_stock = 20 * 1_000_000
    _w = _waive_total(log)
    assert 0 < _w <= int(total_stock * WAIVER_WRITEOFF_CAP * 1.05)
    # 强度 1.0 ⇒ 本月追缴归零（只余取整残差）⇒ 期末欠税 ≥ 期初 × (1 − 10%)（新增欠税只会更高）
    assert _total_arrears(s) >= int(total_stock * (1 - WAIVER_WRITEOFF_CAP))


# ============================================================================
# ③ 只读 / 确定性 / 契约守卫
# ============================================================================
def test_consumers_are_read_only_and_deterministic():
    """三个消费点不写 state（只读裁决副本），且同输入同输出。"""
    rec = {"distributions": {"tax_stance": {"strict": 0.6, "moderate": 0.3, "lenient": 0.1}},
           "strengths": {"waive_arrears": 0.8, "reform_compliance": 0.7}}
    s = _mk(rec, turn=9)
    before = json.dumps(rec, sort_keys=True)
    f1 = (_tax_stance_factor(s), _arrears_waiver_ratio(s), _reform_compliance_factor(s))
    f2 = (_tax_stance_factor(s), _arrears_waiver_ratio(s), _reform_compliance_factor(s))
    assert f1 == f2
    assert json.dumps(s._tiandao_observe, sort_keys=True) == before


def test_no_fixed_multiplier_table_remains():
    """源码级守卫：三个消费点不再直接读 decisions 的布尔/档位词（不得回退成档位表）。"""
    import inspect
    from core import settlement_decree, settlement_finance

    for fn in (settlement_finance._tax_stance_factor,
               settlement_finance._arrears_waiver_ratio,
               settlement_decree._reform_compliance_factor):
        src = inspect.getsource(fn)
        assert "observe_strength" in src or "observe_mix" in src, fn.__name__
    # 旧档位表的两条特征值不得再出现（严格/宽和、未执行×0.5 的硬编码）
    fin_src = inspect.getsource(settlement_finance._tax_stance_factor)
    assert "1.03" not in fin_src and "0.97" not in fin_src
    dec_src = inspect.getsource(settlement_decree._reform_compliance_factor)
    assert "return 0.5" not in dec_src
