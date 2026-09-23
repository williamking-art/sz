# -*- coding: utf-8 -*-
"""利益集团二期+三期回归：人员进出口（科举座主门生/恩荫/致仕/祠禄/荐举）+ 转投。

锁定：
  1. 入口 — 本榜进士随座主入派、荫补者随父辈派系，只改 `state.faction_split` 占比；
  2. 出口 — 致仕把官僚立场结构带入士绅；祠禄定向挤退失势派系；
  3. 转投 — 低满意度派系成员零和转向高满意度派系；
  4. 硬约束 — `state.faction_split` 唯一写入点 = `core.faction_split.set_split`；
     只改比率（Σ=1），**不新开人口账本**（人仍在同一 POP 的 size 里）。
"""
import ast
import os
import sys
import warnings
from pathlib import Path

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FACTION_NAMES  # noqa: E402
from core.faction_metrics import faction_power  # noqa: E402
from core.faction_settle import settle_factions_from_pop  # noqa: E402
from core.faction_split import (  # noqa: E402
    blend_entrants, defect_toward_satisfaction, exit_faction_members, set_split,
    shift_split, split_of,
)
from core.game_state import GameState  # noqa: E402
from core.officialdom import (  # noqa: E402
    _annual_retire, _examiner_faction, _gentry_total, _officials_total,
    _overflow_to_sinecure, _triennial_exam, _triennial_yinben,
    recruit_by_recommendation, settle_officialdom,
)
from core.settlement import run_monthly_settlement  # noqa: E402


def _s():
    return GameState("史实")


def _pop_total(s):
    """全国在籍人口 = Σ六类 POP size + 流民（与 test_pop_identity 同口径）。"""
    return (sum(pop["size"] for p in s.prefectures.values() for pop in p["pops"].values())
            + s.refugee_count)


def _sum_ok(state, cls):
    sp = split_of(state, cls)
    assert sp, cls
    assert abs(sum(sp.values()) - 1.0) < 1e-9, (cls, sp)
    assert all(0.0 <= v <= 1.0 for v in sp.values()), (cls, sp)
    return sp


# ================================================================
# 入口 · 科举座主门生
# ================================================================
def test_exam_cohort_joins_examiner_faction_exactly():
    """门生随座主入派：只改占比，且严格等于加权并流公式 (cur·base + n)/(base+n)。"""
    s = _s()
    s.exam["examiner_faction"] = "旧党"
    base = _officials_total(s)
    before = dict(_sum_ok(s, "官僚"))
    n = _triennial_exam(s, [])
    assert n > 0
    after = _sum_ok(s, "官僚")
    expect_old = (before.get("旧党", 0.0) * base + n) / (base + n)
    assert abs(after["旧党"] - expect_old) < 1e-9
    factor = base / (base + n)
    for f, v in before.items():
        if f != "旧党":
            assert abs(after[f] - v * factor) < 1e-9, f
    assert s.exam["last_examiner_faction"] == "旧党"


def test_exam_records_cohort_examiner_ledger():
    """科次台账要带座主派系（「同年/座主」载体），前端/AI 可读。"""
    s = _s()
    s.exam["examiner_faction"] = "新党"
    n = _triennial_exam(s, [])
    last = s.exam["cohorts"][-1]
    assert last["size"] == n and last["examiner_faction"] == "新党"
    assert n > 0


def test_closed_exam_leaves_split_untouched():
    s = _s()
    s.exam["open"] = False
    before = dict(split_of(s, "官僚"))
    assert _triennial_exam(s, []) == 0
    assert split_of(s, "官僚") == before


def test_examiner_faction_resolution_order():
    """座主解析：显式派系 > 显式人名 > 礼部在任者 > 朝堂声量最大者。"""
    s = _s()
    assert _examiner_faction(s) == "旧党"          # 默认：声量最大（韩忠彦等旧党在朝）
    s.central_orgs["礼部"]["holders"]["礼部尚书"] = "蔡京"   # 新党
    assert _examiner_faction(s) == "新党"
    s.exam["examiner"] = "童贯"                    # 皇党集团，人名优先于机构
    assert _examiner_faction(s) == "皇党集团"
    s.exam["examiner_faction"] = "中立派"         # 显式派系优先于一切
    assert _examiner_faction(s) == "中立派"


def test_exam_flow_conserves_pop_and_adds_no_ledger():
    """入口流动不新增人口账本：ΣPOP 不变，只有立场占比变。"""
    s = _s()
    s.exam["examiner_faction"] = "新党"
    p0 = _pop_total(s)
    off0 = _officials_total(s)
    n = _triennial_exam(s, [])
    assert n > 0
    assert _pop_total(s) == p0, "科举派系流动破了 ΣPOP"
    assert _officials_total(s) == off0 + n, "取士应仅落官僚 POP 的人数（转移）"
    _sum_ok(s, "官僚")


# ================================================================
# 入口 · 恩荫 / 荐举
# ================================================================
def test_yinben_inherits_father_faction_split_exactly():
    """荫补者随父辈派系：来派结构 = 士绅立场分布，严格按并流公式并入官僚。"""
    s = _s()
    set_split(s, "士绅", {"旧党": 0.8, "中立派": 0.2})
    base = _officials_total(s)
    before = dict(_sum_ok(s, "官僚"))
    n = _triennial_yinben(s, [])
    assert n > 0
    after = _sum_ok(s, "官僚")
    for f, share in (("旧党", 0.8), ("中立派", 0.2)):
        expect = (before.get(f, 0.0) * base + share * n) / (base + n)
        assert abs(after[f] - expect) < 1e-9, f


def test_yinben_conserves_pop():
    s = _s()
    p0 = _pop_total(s)
    n = _triennial_yinben(s, [])
    assert n > 0 and _pop_total(s) == p0
    _sum_ok(s, "官僚")


def test_recommendation_interface_transfers_pop_and_follows_patron():
    """荐举接口：士绅 → 官僚待阙（ΣPOP 守恒），受荐者随举主派系入派。"""
    s = _s()
    route = next(iter(s.prefectures))
    pref = s.prefectures[route]
    p0 = _pop_total(s)
    base = _officials_total(s)
    before = dict(_sum_ok(s, "官僚"))
    n = recruit_by_recommendation(s, pref, 50, "蔡京")     # 新党
    assert n > 0
    assert _pop_total(s) == p0, "荐举破了 ΣPOP"
    after = _sum_ok(s, "官僚")
    expect = (before.get("新党", 0.0) * base + n) / (base + n)
    assert abs(after["新党"] - expect) < 1e-9
    assert s.recruit_log.get("举荐") == n


# ================================================================
# 出口 · 致仕 / 祠禄
# ================================================================
def test_retire_carries_bureaucrat_faction_into_gentry():
    """致仕出口：官僚侧按比例退出（占比不变），士绅侧按官僚派系结构并入。"""
    s = _s()
    set_split(s, "官僚", {"新党": 0.7, "旧党": 0.3})
    gbase = _gentry_total(s)
    gbefore = dict(_sum_ok(s, "士绅"))
    bbefore = dict(_sum_ok(s, "官僚"))
    n = _annual_retire(s, [])
    assert n > 0
    gafter = _sum_ok(s, "士绅")
    for f, share in bbefore.items():
        expect = (gbefore.get(f, 0.0) * gbase + share * n) / (gbase + n)
        assert abs(gafter[f] - expect) < 1e-9, f
    bafter = _sum_ok(s, "官僚")
    assert set(bafter) == set(bbefore)
    for f, v in bbefore.items():
        assert abs(bafter[f] - v) < 1e-9, f


def test_retire_conserves_pop():
    s = _s()
    p0 = _pop_total(s)
    n = _annual_retire(s, [])
    assert n > 0 and _pop_total(s) == p0


def test_sinecure_exit_leans_on_weakest_faction_and_is_conserving():
    """祠禄出口：失势（满意度最低）派系被定向挤退；人数侧待阙→祠禄，官额不变。"""
    s = _s()
    for p in s.prefectures.values():
        pop = p["pops"]["官僚"]
        ensure = int(pop.get("waiting", 0) or 0)
        pop["waiting"] = ensure + 5000
        pop["officials"] = int(pop.get("officials", 0)) + 5000
        pop["size"] = int(pop.get("size", 0)) + 5000
    off_before = int(sum(p["pops"]["官僚"].get("officials", 0) for p in s.prefectures.values()))
    before = dict(_sum_ok(s, "官僚"))
    weakest = min(before, key=lambda f: s.factions[f]["satisfaction"])
    done = _overflow_to_sinecure(s, [])
    assert done > 0
    after = _sum_ok(s, "官僚")
    assert after[weakest] < before[weakest], "失势派系应被祠禄定向挤出"
    off_after = int(sum(p["pops"]["官僚"].get("officials", 0) for p in s.prefectures.values()))
    assert off_after == off_before, "祠禄是子池转移，官额不得变"


# ================================================================
# 三期 · 转投（零和）
# ================================================================
def test_defection_moves_low_satisfaction_to_high():
    s = _s()
    set_split(s, "官僚", {"新党": 0.5, "旧党": 0.5})
    before = dict(_sum_ok(s, "官僚"))
    out = defect_toward_satisfaction(s, {"新党": 90.0, "旧党": 10.0},
                                     rate=0.02, min_gap=2.0)
    assert "官僚" in out
    after = _sum_ok(s, "官僚")
    assert after["旧党"] < before["旧党"] and after["新党"] > before["新党"]
    moved = out["官僚"]["moved"]
    assert 0 < moved <= 0.02 * before["旧党"] + 1e-12, "月迁出不得超过 rate×源占比"


def test_defection_gap_below_threshold_is_noop():
    s = _s()
    set_split(s, "官僚", {"新党": 0.5, "旧党": 0.5})
    before = dict(split_of(s, "官僚"))
    assert defect_toward_satisfaction(s, {"新党": 51.0, "旧党": 50.0},
                                      rate=0.02, min_gap=2.0) == {}
    assert split_of(s, "官僚") == before


def test_defection_skips_single_faction_class():
    s = _s()
    before = dict(split_of(s, "兵"))
    out = defect_toward_satisfaction(s, {n: 80.0 for n in s.factions})
    assert "兵" not in out and split_of(s, "兵") == before


def test_defection_is_zero_sum_over_all_classes():
    s = _s()
    before = {c: dict(split_of(s, c)) for c in s.faction_split}
    defect_toward_satisfaction(s, {n: float(i * 20) for i, n in enumerate(s.factions)})
    for c, b in before.items():
        a = _sum_ok(s, c)
        assert abs(sum(a.values()) - sum(b.values())) < 1e-9
        assert set(a) == set(b), "转投不得凭空增删派系"
        for f in b:
            if a[f] > b[f]:
                assert a[f] - b[f] <= 0.02 * b[f] + 1e-12


def test_settle_factions_triggers_defection_only_through_set_split(monkeypatch):
    """转投必须经唯一写入点 set_split；不得绕过它直改 state.faction_split。"""
    import core.faction_split as FS
    s = _s()
    calls = []
    orig = FS.set_split

    def _spy(state, pop_class, split):
        calls.append(pop_class)
        return orig(state, pop_class, split)

    monkeypatch.setattr(FS, "set_split", _spy)
    ident = id(s.faction_split)
    settle_factions_from_pop(s)
    assert "官僚" in calls, "低满意度派系的转投未走 set_split"
    assert id(s.faction_split) == ident, "不得替换 state.faction_split 对象"


# ================================================================
# 纯函数守恒
# ================================================================
def test_blend_entrants_is_ratio_only_and_conserves_pop():
    s = _s()
    p0 = _pop_total(s)
    before = dict(split_of(s, "官僚"))
    out = blend_entrants(s, "官僚", 1000.0, {"新党": 200})
    assert abs(sum(out.values()) - 1.0) < 1e-12
    assert abs(out["新党"] - (before.get("新党", 0.0) * 1000 + 200) / 1200) < 1e-12
    assert _pop_total(s) == p0
    assert blend_entrants(s, "官僚", 1000.0, {"不存在的集团": 5}) == split_of(s, "官僚")


def test_exit_faction_members_renormalises_and_sums_one():
    s = _s()
    set_split(s, "官僚", {"新党": 0.6, "旧党": 0.4})
    out = exit_faction_members(s, "官僚", "旧党", 0.1)
    assert abs(out["旧党"] - 0.3 / 0.9) < 1e-12
    assert abs(out["新党"] - 0.6 / 0.9) < 1e-12
    assert abs(sum(out.values()) - 1.0) < 1e-12


def test_shift_split_is_zero_sum_and_clamped():
    s = _s()
    set_split(s, "官僚", {"新党": 0.6, "旧党": 0.4})
    out = shift_split(s, "官僚", "新党", "旧党", 0.1)
    assert abs(out["新党"] - 0.5) < 1e-12 and abs(out["旧党"] - 0.5) < 1e-12
    out2 = shift_split(s, "官僚", "旧党", "新党", 99.0)   # 超量 → 钳到现有占比
    assert out2.get("旧党", 0.0) < 1e-12, "被搬空的派系占比应为 0（占比表会丢弃 0 项）"
    assert abs(out2["新党"] - 1.0) < 1e-12
    assert abs(sum(out2.values()) - 1.0) < 1e-12


# ================================================================
# 端到端：守恒 + 唯一写入点 + 无平行账本
# ================================================================
def test_pipeline_keeps_split_conserved_and_pop_aligned():
    s = _s()
    for _ in range(24):
        run_monthly_settlement(s, seed_offset=3)
        for cls in list(s.faction_split.keys()):
            _sum_ok(s, cls)
    assert _pop_total(s) == s.population, "月末人口总账未对齐"


def test_split_keys_are_primary_keys_not_display_names():
    s = _s()
    settle_officialdom(s, [])
    settle_factions_from_pop(s)
    for cls, sp in s.faction_split.items():
        for k in sp:
            assert k in FACTION_NAMES, (cls, k)


def test_no_parallel_faction_population_or_wealth_ledger():
    s = _s()
    settle_factions_from_pop(s)
    for name in ("faction_population", "faction_wealth", "faction_grain"):
        assert not hasattr(s, name)
    for f in s.factions.values():
        for name in ("population", "size", "wealth", "grain"):
            assert name not in f, f"集团不得存人口/钱粮账本字段：{name}"
    # 集团人数只作派生读数（faction_metrics 现算），不落存量。
    assert "population" in faction_power(s, "新党")


def _faction_split_writes_outside_module(root):
    """AST 审计：除 faction_split.py 外不得对 state.faction_split 做下标赋值/原地变更。"""
    def _is_fs(v):
        if isinstance(v, ast.Attribute):
            return v.attr == "faction_split"
        if isinstance(v, ast.Subscript):
            return _is_fs(v.value)
        return False

    bad = []
    for path in Path(root).rglob("*.py"):
        if path.name == "faction_split.py":
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and _is_fs(t.value):
                    bad.append(f"{path}:{node.lineno}")
            if isinstance(node, ast.Call):
                f = node.func
                if (isinstance(f, ast.Attribute)
                        and f.attr in ("update", "clear", "pop", "setdefault", "__setitem__")
                        and _is_fs(f.value)):
                    bad.append(f"{path}:{node.lineno} .{f.attr}()")
    return bad


def test_state_faction_split_unique_writer_static_guard():
    assert _faction_split_writes_outside_module(_GAME_ROOT) == []