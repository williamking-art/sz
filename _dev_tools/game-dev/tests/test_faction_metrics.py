# -*- coding: utf-8 -*-
"""利益集团方案第 2 步回归：POP 派生的规模 / 资源份额 / 影响力（只读纯函数）。

锁定：指标只能由 POP 派生、不写状态、子池按人数折算、粮价取既有口径、
共享 POP 不重复扣除（本模块只读）、旧 influence 仅作空基盘回退。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FACTION_POP_BASIS  # noqa: E402
from core.faction_metrics import (  # noqa: E402
    POWER_W_POP, POWER_W_RES, POWER_W_VOICE, POWER_W_INST, POWER_W_MIL, POWER_W_COH,
    all_faction_power, faction_power, faction_slice, local_grain_price,
    national_totals,
)
from core.game_state import GameState  # noqa: E402


def _s():
    return GameState("史实")


def test_weights_sum_to_one():
    assert abs((POWER_W_POP + POWER_W_RES + POWER_W_VOICE + POWER_W_INST
                + POWER_W_MIL + POWER_W_COH) - 1.0) < 1e-9


def test_local_grain_price_uses_existing_field():
    s = _s()
    route = next(iter(s.prefectures))
    assert local_grain_price(s, route) == s.prefectures[route]["grain_price"]
    s.prefectures[route]["grain_price"] = 2.0
    assert local_grain_price(s, route) == 2.0
    assert local_grain_price(s, None) == s.grain_price
    s.prefectures[route]["grain_price"] = 0      # 非正值 → 回落，不当 0 用
    assert local_grain_price(s, route) > 0


def test_metrics_are_read_only():
    s = _s()
    before = copy.deepcopy(s.factions)
    pops_before = {(r, c): s.prefectures[r]["pops"][c]["size"]
                   for r in s.prefectures for c in s.prefectures[r]["pops"]}
    all_faction_power(s)
    assert s.factions == before, "纯函数不得写回 factions"
    for r in s.prefectures:
        for c in s.prefectures[r]["pops"]:
            assert s.prefectures[r]["pops"][c]["size"] == pops_before[(r, c)], "POP 不得被改"


def test_faction_population_sums_slice_sizes():
    """集团人数 = 基数（officials 子池）× 立场占比（**非按地域切**）。"""
    from core.faction_split import split_of
    s = _s()
    sl = faction_slice(s, FACTION_POP_BASIS["新党"], "新党")
    officials = sum(max(0.0, s.prefectures[r]["pops"]["官僚"].get("officials") or 0)
                    for r in s.prefectures)
    share = split_of(s, "官僚")["新党"]
    assert abs(sl["population"] - officials * share) < 1e-6
    assert sl["population"] > 0
    # 官僚 POP 的 size 含吏，立场只落在「官」身上 → 切片必小于整个官僚 POP
    assert sl["population"] < sum(p["pops"]["官僚"]["size"] for p in s.prefectures.values())


def test_pool_resources_prorated_by_population_share():
    s = _s()
    route = next(iter(s.prefectures))
    pop = s.prefectures[route]["pops"]["官僚"]
    pop["officials"] = pop["size"]                       # 子池 = 父 POP → 全额
    full = faction_slice(s, FACTION_POP_BASIS["官官集团"] if False else
                         {"pop_classes": ["官僚"], "pool": "officials",
                          "routes": [route], "subset_of": ["官僚"], "subset_kind": "pool"})
    pop["officials"] = pop["size"] / 2                   # 子池 = 一半 → 按比例
    half = faction_slice(s, {"pop_classes": ["官僚"], "pool": "officials",
                             "routes": [route], "subset_of": ["官僚"], "subset_kind": "pool"})
    assert abs(full["resources"] - 2 * half["resources"]) < 1e-6
    assert abs(full["population"] - 2 * half["population"]) < 1e-6


def test_power_components_in_range():
    s = _s()
    for name, m in all_faction_power(s).items():
        for k in ("population_share", "resource_share", "institutional_access",
                  "military_leverage", "cohesion"):
            assert 0.0 <= m[k] <= 1.0, (name, k, m[k])
        assert 0.0 <= m["influence"] <= 100.0, (name, m["influence"])


def test_influence_is_derived_from_pop_not_old_field():
    """改 POP 存量（而非改旧 influence）必须改变派生值——"指标只能由 POP 派生"。"""
    s = _s()
    base = faction_power(s, "军功集团")["influence"]
    s.factions["军功集团"]["influence"] = 99      # 改旧字段 → 不得影响派生
    assert faction_power(s, "军功集团")["influence"] == base
    for r in ("陕西路", "河东路", "河北路"):
        p = s.prefectures.get(r)
        if p:
            p["pops"]["兵"]["size"] = float(p["pops"]["兵"]["size"]) * 3   # 改 POP → 必变
    assert faction_power(s, "军功集团")["influence"] != base


def test_fallback_to_old_influence_when_basis_empty():
    s = _s()
    s.factions["新党"]["influence"] = 77
    m = faction_power(s, "新党", {"pop_classes": ["官僚"], "pool": "officials",
                                          "routes": ["不存在的路"],
                                          "subset_of": ["官僚"], "subset_kind": "pool"})
    assert m["fallback"] is True and m["influence"] == 77


def test_split_shares_never_exceed_population():
    """同一 POP 上各派系立场占比之和 = 1；各派系切片之和不得超过该 POP 总量（不重复占人）。"""
    from core.faction_split import split_of
    s = _s()
    assert abs(sum(split_of(s, "官僚").values()) - 1.0) < 1e-9
    officials = sum(max(0.0, p["pops"]["官僚"].get("officials") or 0)
                    for p in s.prefectures.values())
    total = 0.0
    for n, spec in FACTION_POP_BASIS.items():
        if "官僚" in spec["pop_classes"]:
            sub = dict(spec)
            sub["pop_classes"] = ["官僚"]      # 只取该集团的「官僚部分」
            total += faction_slice(s, sub, n)["population"]
    assert total <= officials * 1.0001, (total, officials)


def test_national_totals_are_sums_over_all_pops():
    s = _s()
    nat = national_totals(s)
    expect_pop = sum(p["pops"][c]["size"] for p in s.prefectures.values()
                     for c in p["pops"])
    assert abs(nat["population"] - expect_pop) < 1e-6
    assert nat["resources"] > 0 and nat["officials"] > 0 and nat["troops"] > 0