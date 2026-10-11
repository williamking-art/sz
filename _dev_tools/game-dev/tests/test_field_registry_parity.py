# -*- coding: utf-8 -*-
"""B-1 字段单点注册 · 一致性差分测试（L0 自检 / L1 集合 / L1.5 顺序 / L2 谓词 / L3 管道）。

期望值**全部**取自 `b1_field_registry_golden.py`：迁移前实现（commit 见其
`GOLDEN_SOURCE`）的**实跑冻结**数据。纪律：不得用未验证的预期替换 golden。

阶段语义：
  · B-1a（影子期）：`state_applier` 仍持字面量 ⇒ 与派生集合**多重集相等**；
  · B-1b（切换后）：`state_applier` 的名字必须与 `field_registry` **同一对象**（单点生效）。
    本模块两种情况都断言"与 golden 相等"，并在接线后额外断言同一性，防"半切"。
"""
from __future__ import annotations

import copy
import os
import random
import sys
from collections import Counter

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))            # game-dev
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(_HERE)), "game"))  # game/
sys.path.insert(0, _HERE)                             # tests（golden 数据模块）

from core.game_state import GameState  # noqa: E402
import engine.field_registry as fr  # noqa: E402
import engine.state_applier as sa  # noqa: E402
import b1_field_registry_golden as G  # noqa: E402

VIEWS = ["VALID_PATHS", "NON_NEG_PREFIXES", "MONEY_PATHS", "GRAIN_PATHS",
         "RANGE_100_FIELDS", "CLAMP_01_FIELDS"]
PRED_NAMES = ["path_ok", "non_neg", "range100", "clamp01", "group"]


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _state():
    return GameState("史实")


def _canon(state):
    return {
        "treasury": state.treasury,
        "imperial_treasury": state.imperial_treasury,
        "granary": state.granary,
        "prestige": state.prestige,
        "population_satisfaction": state.population_satisfaction,
    }


def _predicates(p):
    """与探针逐字一致：异常折叠为 EXC:<类型>，非 str 的 group 记 N/A。"""
    out = {}
    for name, fn in (("path_ok", sa._path_ok), ("non_neg", sa._is_non_neg),
                     ("range100", sa._is_range100), ("clamp01", sa._is_clamp01)):
        try:
            out[name] = fn(p)
        except Exception as e:  # noqa: BLE001
            out[name] = "EXC:%s" % type(e).__name__
    try:
        out["group"] = sa._group_of(p) if isinstance(p, str) else "N/A"
    except Exception as e:  # noqa: BLE001
        out["group"] = "EXC:%s" % type(e).__name__
    return out


def _build_scenarios(road, fac):
    """与 `_scratch/b1_baseline_probe.py::build_scenarios` 逐字一致（golden 输入）。"""
    return [
        ("S1_set_single", [("a", [{"path": "prestige", "op": "set", "value": 50, "reason": "r1"}])]),
        ("S2_pair_money_closed", [("a", [
            {"path": "treasury", "op": "add", "value": -1000, "reason": "税征"},
            {"path": "prefectures.%s.pops.商人.wealth" % road, "op": "add", "value": 1000, "reason": "税征"},
        ])]),
        ("S3_single_sided_fix", [("a", [
            {"path": "treasury", "op": "add", "value": 5000, "reason": "市舶税入账"}])]),
        ("S4_single_sided_no_keyword", [("a", [
            {"path": "treasury", "op": "add", "value": -100, "reason": "无关键词单边"}])]),
        ("S5_underflow", [("a", [
            {"path": "treasury", "op": "add", "value": -9000000000, "reason": "穿底探针"},
            {"path": "prefectures.%s.pops.士绅.wealth" % road, "op": "add", "value": 9000000000, "reason": "穿底探针"},
        ])]),
        ("S6_nonconserved_underflow", [("a", [
            {"path": "prefectures.%s.refugees" % road, "op": "add", "value": -999999, "reason": "流民安置"}])]),
        ("S7_wildcard_fix_prorate", [("a", [
            {"path": "treasury", "op": "add", "value": 1234, "reason": "市舶税"}])]),
        ("S8_multi_agent_merge", [
            ("a1", [{"path": "treasury", "op": "add", "value": 10, "reason": "a1"},
                    {"path": "granary", "op": "set", "value": 7, "reason": "a1"}]),
            ("a2", [{"path": "treasury", "op": "add", "value": 20, "reason": "a2"},
                    {"path": "granary", "op": "set", "value": 9, "reason": "a2"}]),
        ]),
        ("S9_cascade_noop", [("a", [
            {"path": "prefectures.%s.pops.农.wealth" % road, "op": "add", "value": 1, "reason": "cascade 探针"},
            {"path": "prefectures.%s.pops.农.grain" % road, "op": "add", "value": -1, "reason": "cascade 探针"},
            {"path": "prefectures.%s.pops.士绅.grain" % road, "op": "add", "value": 1, "reason": "cascade 探针"},
        ])]),
        ("S10_push_numeric", [("a", [{"path": "prestige", "op": "push", "value": 5, "reason": "push 探针"}])]),
        ("S11_range100_set_over", [("a", [
            {"path": "prestige", "op": "set", "value": 200, "reason": "越界 set"}])]),
        ("S12_range100_add_negative", [("a", [
            {"path": "population_satisfaction", "op": "add", "value": -5, "reason": "负增量"}])]),
        ("S13_era_state_prefix", [("a", [
            {"path": "era_state.art", "op": "add", "value": 3, "reason": "前缀通道探针"}])]),
        ("S14_pop_class7_rejected", [("a", [
            {"path": "prefectures.%s.pops.吏.wealth" % road, "op": "add", "value": 1, "reason": "第7类探针"}])]),
        ("S15_money_missing_source_hard_reject", [("a", [
            {"path": "prefectures.%s.pops.农.wealth" % road, "op": "add", "value": 777, "reason": "孤立入账"}])]),
    ]


def _run_scenario(raw):
    st = _state()
    sa.reset_change_log()
    before = _canon(st)
    res, exc = None, None
    try:
        res = sa.applier_pipeline(st, copy.deepcopy(raw))
    except Exception as e:  # noqa: BLE001
        exc = "%s: %s" % (type(e).__name__, e)
    after = _canon(st)
    return {
        "exception": exc,
        "applied": None if res is None else [[x["path"], x["old"], x["new"]] for x in res["applied"]],
        "rejected": None if res is None else res["rejected"],
        "conservation_failed": None if res is None else res.get("conservation_failed"),
        "changelog": len(sa.CHANGE_LOG),
        "state_delta": {k: [before[k], after[k]] for k in before if before[k] != after[k]},
    }


def _wired_names():
    """已接线的集合名（`state_applier.X is field_registry.X`）。"""
    return {v for v in VIEWS if getattr(sa, v) is getattr(fr, v)}


# ---------------------------------------------------------------------------
# L0 · 声明自检（正向）
# ---------------------------------------------------------------------------
def test_registry_selfcheck_passes():
    assert fr.validate_registry() == [], "真实声明必须通过自检"


def test_registry_shape_and_counts():
    assert len(fr.RULES) == 38
    d = fr.derive()
    assert sum(len(v) for v in d.values()) == 84
    assert {k: len(v) for k, v in d.items()} == {
        "VALID_PATHS": 35, "NON_NEG_PREFIXES": 24, "MONEY_PATHS": 9,
        "GRAIN_PATHS": 5, "RANGE_100_FIELDS": 11, "CLAMP_01_FIELDS": 0,
    }


def test_derived_types_stay_list():
    """类型必须与迁移前一致（list），避免任何 API 类型变化。"""
    for v in VIEWS:
        assert type(getattr(fr, v)) is list


# ---------------------------------------------------------------------------
# L0 · 负向：缺元数据 / 错分类 / 非法值必须报错（不得静默放行）
# ---------------------------------------------------------------------------
_N = fr.Kind.NUMERIC
_X = fr.Kind.NON_NUMERIC
_M = fr.Cons.MONEY
_G = fr.Cons.GRAIN
_E = fr.Cons.EXEMPT


def _ok_rule(**kw):
    base = dict(path="a.b", kind=_N, cons=_E, writable=True)
    base.update(kw)
    return fr.PathRule(**base)


def test_negative_missing_cons():
    errs = fr.validate_registry([fr.PathRule("a", _N, None)])
    assert any("cons 必须是 Cons" in e for e in errs), errs


def test_negative_cons_wrong_type():
    errs = fr.validate_registry([fr.PathRule("a", _N, "money")])
    assert any("cons 必须是 Cons" in e for e in errs), errs


def test_negative_kind_wrong_type():
    errs = fr.validate_registry([fr.PathRule("a", "numeric", _E)])
    assert any("kind 必须是 Kind" in e for e in errs), errs


def test_negative_bool_field_wrong_type():
    errs = fr.validate_registry([_ok_rule(writable=1)])
    assert any("writable 必须是 bool" in e for e in errs), errs


def test_negative_str_field_wrong_type():
    errs = fr.validate_registry([_ok_rule(exempt_reason=123)])
    assert any("exempt_reason 必须是 str/None" in e for e in errs), errs


def test_negative_path_empty_and_interior_empty_segment():
    assert any("path 格式非法" in e for e in fr.validate_registry([fr.PathRule("", _N, _E)]))
    assert any("path 格式非法" in e for e in fr.validate_registry([fr.PathRule("a..b", _N, _E)]))


def test_negative_path_non_str():
    errs = fr.validate_registry([fr.PathRule(None, _N, _E)])
    assert any("path 必须是 str" in e for e in errs), errs


def test_negative_path_trailing_dot_is_allowed():
    """尾点前缀（唯一一例 `era_state.`）是合法形态，不得被当空段拒绝。"""
    assert fr.validate_registry([fr.PathRule("era_state.", _N, _E, writable=True)]) == []


def test_negative_duplicate_same_semantics():
    r = fr.PathRule("a", _N, _E)
    errs = fr.validate_registry([r, r])
    assert any("重复声明" in e for e in errs), errs


def test_negative_duplicate_different_semantics():
    errs = fr.validate_registry([fr.PathRule("a", _N, _E), fr.PathRule("a", _N, _M, writable=True)])
    assert any("语义不一致" in e for e in errs), errs


def test_negative_max100_without_non_neg():
    """RANGE_100 ⊆ NON_NEG 不变式：只标 max_100 不标 non_neg ⇒ 双错（行内 + 跨集合关系）。"""
    errs = fr.validate_registry([_ok_rule(max_100=True, non_neg=False)])
    assert any("RANGE_100_FIELDS ⊆ NON_NEG_PREFIXES 不成立" in e for e in errs), errs


def test_negative_max100_and_clamp01():
    errs = fr.validate_registry([_ok_rule(max_100=True, non_neg=True, clamp01=True)])
    assert any("不得同时 max_100 与 clamp01" in e for e in errs), errs


def test_negative_non_numeric_with_numeric_meta():
    errs = fr.validate_registry([_ok_rule(kind=_X, non_neg=True)])
    assert any("NON_NUMERIC 不得带" in e for e in errs), errs


def test_negative_tuple_control_by_is_the_real_non_numeric_row():
    rows = [r for r in fr.RULES if r.kind is _X]
    assert [r.path for r in rows] == ["prefectures.*.controlled_by"]


def test_negative_money_not_writable():
    """MONEY ⊆ VALID 不变式：守恒组必须在白名单内。"""
    errs = fr.validate_registry([fr.PathRule("a", _N, _M, writable=False)])
    assert any("守恒组必须在白名单内" in e for e in errs), errs
    assert any("MONEY_PATHS ⊆ VALID_PATHS 不成立" in e for e in errs), errs


def test_negative_money_word_exempt_requires_reason():
    """关键词只触发"必须写理由"，不决定分类。"""
    errs = fr.validate_registry([_ok_rule(path="prefectures.foo.treasury_pool")])
    assert any("必须给 exempt_reason" in e for e in errs), errs


def test_negative_money_word_with_reason_passes():
    assert fr.validate_registry(
        [_ok_rule(path="prefectures.foo.treasury_pool", exempt_reason="只承载非负判定")]) == []


def test_negative_keyword_never_assigns_conservation():
    """命中语义词的规则在给了理由后，cons 仍必须是声明者写的 EXEMPT（不被自动改写）。"""
    r = _ok_rule(path="waste_reform.savings", exempt_reason="冻结")
    assert r.cons is _E
    assert fr.derive([r])["MONEY_PATHS"] == [] and fr.derive([r])["GRAIN_PATHS"] == []


def test_negative_rules_not_sequence():
    assert fr.validate_registry(None) == ["rules 必须是 list/tuple，得到 NoneType"]
    assert fr.validate_registry({"a": 1})[0].startswith("rules 必须是 list/tuple")


# ---------------------------------------------------------------------------
# L1 · 集合层：与迁移前 golden 多重集相等（顺序见 L1.5）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("view", VIEWS)
def test_l1_multiset_equals_golden(view):
    assert Counter(getattr(fr, view)) == Counter(G.SIX_COLLECTIONS_OLD[view])


@pytest.mark.parametrize("view", VIEWS)
def test_l1_state_applier_equals_golden(view):
    """B-1a：state_applier 字面量与 golden 多重集相等；B-1b：与派生物同一对象。"""
    assert Counter(getattr(sa, view)) == Counter(getattr(G, "SIX_COLLECTIONS_OLD")[view])


def test_l1_wiring_is_all_or_nothing():
    """防"半切"：六个集合要么全接线、要么全未接线。"""
    wired = _wired_names()
    assert wired in (set(), set(VIEWS)), "半接线状态：%s" % sorted(wired)


def test_l1_order_rule_is_scoped_by_ruling():
    """顺序验收**按集合分别执行**（用户 2026-10-12 追认，见 `decisions/B1-order-relaxation.json`）。

    · `VALID_PATHS` / `MONEY_PATHS` / `GRAIN_PATHS`：**字符串与顺序均须一致**（严格）。
    · `CLAMP_01_FIELDS`：必须仍为空且与原行为一致。
    · `NON_NEG_PREFIXES` / `RANGE_100_FIELDS`：**只要求多重集相同**；语义不变由 L1.5 洗牌不变性证明
      （顺序不可由单一声明复现：约束图存在 4 节点环，见 design.md §2.3）。

    🔴 **未来限制**：这不是普遍豁免。若将来有任何代码开始依赖后两套集合的**迭代顺序**，
    必须重新评估契约——届时须把它们移入 `STRICT_ORDER` 并补行为证据。
    """
    strict = ["VALID_PATHS", "MONEY_PATHS", "GRAIN_PATHS"]
    loose = ["NON_NEG_PREFIXES", "RANGE_100_FIELDS"]
    for v in strict:
        assert list(getattr(fr, v)) == list(G.SIX_COLLECTIONS_OLD[v]), \
            "%s 必须字符串与顺序均一致（追认仅放宽两套集合）" % v
    assert list(fr.CLAMP_01_FIELDS) == list(G.SIX_COLLECTIONS_OLD["CLAMP_01_FIELDS"]) == [], \
        "CLAMP_01_FIELDS 必须仍为空"
    for v in loose:
        assert Counter(getattr(fr, v)) == Counter(G.SIX_COLLECTIONS_OLD[v]), v
    # 收紧面：除追认的两套外，不得再出现第三套顺序分歧（防"顺手多放宽一套"）
    divergent = {v for v in VIEWS if list(getattr(fr, v)) != list(G.SIX_COLLECTIONS_OLD[v])}
    assert divergent == set(loose), divergent


# ---------------------------------------------------------------------------
# L1.5 · 顺序不变性（放宽顺序比较的**前提证据**）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [1, 7, 20261012])
def test_l15_shuffle_invariance_predicates(seed, monkeypatch):
    rng = random.Random(seed)
    for view in VIEWS:
        cur = list(getattr(fr, view))
        rng.shuffle(cur)
        monkeypatch.setattr(sa, view, cur)
    monkeypatch.setattr(sa, "_RANGE_100_SET", set(sa.RANGE_100_FIELDS))
    monkeypatch.setattr(sa, "_CLAMP_01_SET", set(sa.CLAMP_01_FIELDS))
    # ⚠️ 不能用 dict(PREDICATE_GOLDEN)：样本含 list/dict 值，键不可哈希。
    mismatches = []
    for p, want in G.PREDICATE_GOLDEN:
        got = _predicates(p)
        if got != want:
            mismatches.append((p, got, want))
    assert not mismatches, "洗牌后谓词改变：%r" % (mismatches[:5],)


@pytest.mark.parametrize("seed", [3, 99])
def test_l15_shuffle_invariance_pipeline(seed, monkeypatch):
    rng = random.Random(seed)
    for view in VIEWS:
        cur = list(getattr(fr, view))
        rng.shuffle(cur)
        monkeypatch.setattr(sa, view, cur)
    monkeypatch.setattr(sa, "_RANGE_100_SET", set(sa.RANGE_100_FIELDS))
    monkeypatch.setattr(sa, "_CLAMP_01_SET", set(sa.CLAMP_01_FIELDS))
    scen = dict(_build_scenarios(G.CONTEXT["road"], G.CONTEXT["faction"]))
    for name in ("S1_set_single", "S2_pair_money_closed", "S4_single_sided_no_keyword"):
        assert _run_scenario(scen[name]) == G.PIPELINE_GOLDEN[name], name


# ---------------------------------------------------------------------------
# L2 · 谓词层：与迁移前实跑 golden 逐条一致
# ---------------------------------------------------------------------------
def test_l2_predicate_parity_with_golden():
    mismatches = []
    for p, want in G.PREDICATE_GOLDEN:
        got = _predicates(p)
        if got != want:
            mismatches.append((p, got, want))
    assert not mismatches, "谓词与 golden 不一致：%r" % (mismatches[:5],)


def test_l2_loose_prefix_divergence_is_locked():
    """E1 冻结：`granary` 的宽松前缀命中 `granary_cap`（白名单不放行，非负判定命中）。"""
    assert sa._is_non_neg("granary_cap") is True
    assert sa._path_ok("granary_cap") is False


def test_l2_wildcard_nonneg_still_covers_class7():
    """两条 NON_NEG 通配行仍在（比白名单宽）——E2 冻结，不得收窄。"""
    assert sa._is_non_neg("prefectures.%s.pops.吏.wealth" % G.CONTEXT["road"]) is True
    assert sa._path_ok("prefectures.%s.pops.吏.wealth" % G.CONTEXT["road"]) is False


# ---------------------------------------------------------------------------
# L3 · 管道层：与迁移前实跑 golden 逐字段一致
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(G.PIPELINE_GOLDEN.keys()))
def test_l3_pipeline_parity_with_golden(name):
    scen = dict(_build_scenarios(G.CONTEXT["road"], G.CONTEXT["faction"]))
    assert name in scen, "golden 场景 %s 在本模块无对应输入（输入漂移）" % name
    assert _run_scenario(scen[name]) == G.PIPELINE_GOLDEN[name]


def test_l3_rollback_matches_golden():
    """中间层缺失 → KeyError → 逆序回滚 → CHANGE_LOG 不追加。

    该路径历史审计记载从未真正执行过；本用例的期望取自**迁移前实现的实跑记录**
    （见 golden `ROLLBACK_GOLDEN`）。若旧实现不符预期，应登记独立缺陷，不得借 B-1 修复。
    """
    expected = G.ROLLBACK_GOLDEN
    st = _state()
    sa.reset_change_log()
    before = _canon(st)
    log_before = len(sa.CHANGE_LOG)
    changes = [
        {"path": "treasury", "op": "add", "value": -100, "reason": "回滚探针：钱组出腿"},
        {"path": "imperial_treasury", "op": "add", "value": 100, "reason": "回滚探针：钱组入腿"},
        {"path": "prefectures.%s.mood" % G.CONTEXT["missing_road"], "op": "add", "value": 1,
         "reason": "回滚探针：中间层缺失"},
    ]
    returned, exc_type = None, None
    try:
        returned = sa.applier_pipeline(st, [("probe", changes)])
    except Exception as e:  # noqa: BLE001
        exc_type = type(e).__name__
    after = _canon(st)

    assert exc_type == expected["exception_type"] == "KeyError"
    assert returned is expected["returned"] is None, "异常应向上抛（不返回字典）"
    assert expected["state_restored"] is True
    assert before == after, "前两条写入必须被逆序回滚"
    assert {k: [before[k], after[k]] for k in before if before[k] != after[k]} == expected["field_diff"] == {}
    assert log_before == len(sa.CHANGE_LOG) == expected["changelog_before"] == expected["changelog_after"] == 0


# ---------------------------------------------------------------------------
# L0 · 运行时可达性（真状态实例化；禁止源码正则）
# ---------------------------------------------------------------------------
def test_reachability_all_writable_paths_locate():
    st = _state()
    exercised, not_exercised = [], []
    for r in fr.RULES:
        if not r.writable:
            continue
        concrete = _materialize(st, r.path)
        if concrete is None:
            not_exercised.append(r.path)
            continue
        for p in concrete:
            container = sa._locate_path(st, p)[0]
            assert container is not None, "声明可写但寻址不可达（宣告了不存在的能力）：%s" % p
            exercised.append(p)
    assert len(exercised) >= 30, "可达性检查样本过少（%d），疑似空转" % len(exercised)
    # 未行使项必须由"容器为空"解释（新局 legacies 为空），不得是其他原因
    for path in not_exercised:
        head = path.split(".")[0]
        box = getattr(st, head, None)
        assert isinstance(box, dict) and not box, "未行使但容器非空：%s（容器 %r）" % (path, box)


def _materialize(state, pattern):
    """把声明路径具体化；容器为空时返回 None（=未行使）。"""
    if pattern.endswith("."):
        box = getattr(state, pattern[:-1], None)
        return ["%s%s" % (pattern, k) for k in sorted(box)] if isinstance(box, dict) and box else None
    if "*" not in pattern:
        return [pattern]
    parts = pattern.split(".")
    box = getattr(state, parts[0], None)
    if not isinstance(box, dict) or not box:
        return None
    out = []
    for k in sorted(box):
        out.append(".".join(k if p == "*" else p for p in parts))
    return out


def test_golden_provenance_is_recorded():
    """期望值必须可溯源到一次真实实跑。"""
    assert G.GOLDEN_SOURCE["commit"], G.GOLDEN_SOURCE
    assert G.GOLDEN_SOURCE["generated_at"], G.GOLDEN_SOURCE
    assert len(G.SIX_COLLECTIONS_OLD) == 6
    assert len(G.SAMPLE_PATHS) == len(G.PREDICATE_GOLDEN) == 64
    assert len(G.PIPELINE_GOLDEN) == 15
