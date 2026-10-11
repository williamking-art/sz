# -*- coding: utf-8 -*-
"""M35-C-2《役人粮耗统一接入》契约回归。

裁决要点（D2 甲）：役人**计粮**，公式 `runner_count × GRAIN_CONSUME_PER_CAPITA[官僚]`，
**不新增粮桶**、**不进六桶粮耗**（作为 occupation 附加需求，归挂靠桶）；
**7 处口径必须统一**（禁止各模块自算）——单点＝`core/foundation/ledger/occupation.py`。
守恒要求：`runner_count=0` 与接入前**完全一致**；役人>0 ⇒ 人口需求↑、粮耗↑、粮价可轻微变化、
**money 不发生无来源变化**、六桶 size 不变。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import GRAIN_CONSUME_PER_CAPITA  # noqa: E402
from core import money  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.foundation.ledger.occupation import (  # noqa: E402
    effective_size, food_need_of, occupation_food_need)
from core.income_readout import income_source_readout  # noqa: E402
from core.region_brief import build_region_brief  # noqa: E402
from core.settlement_common import food_insecure_headcount  # noqa: E402


def _set_runners(s, per_route):
    """经**治所真账**赋值役人（seats 为准），并刷新路级镜像。"""
    from core.foundation.ledger.pop_bridge import sync_route_pops
    for _n, p in s.prefectures.items():
        seats = p.get("seats") or {}
        rows = [(sid, sd) for sid, sd in seats.items()
                if isinstance(((sd.get("pops") or {}).get("官僚")), dict)]
        if not rows:
            guan = (p.get("pops") or {}).get("官僚")
            if isinstance(guan, dict):
                guan["runner_count"] = int(guan.get("runner_count", 0) or 0) + per_route
            continue
        sizes = [max(1, int((sd["pops"]["官僚"]).get("size", 0) or 0)) for _sid, sd in rows]
        tot = sum(sizes)
        assigned = 0
        for i, (_sid, sd) in enumerate(rows):
            pool = sd["pops"]["官僚"]
            part = per_route - assigned if i == len(rows) - 1 else int(per_route * sizes[i] / tot)
            pool["runner_count"] = int(pool.get("runner_count", 0) or 0) + part
            assigned += part
        sync_route_pops(p)


# ---------------- ① 零役人 ⇒ 与接入前完全一致 ----------------

def test_zero_runner_is_identical_to_pre_integration():
    s = new_game()
    rk = min(s.prefectures)
    pops = s.prefectures[rk]["pops"]
    for cls, pool in pops.items():
        if not isinstance(pool, dict):
            continue
        per = float(GRAIN_CONSUME_PER_CAPITA.get(cls, 0.5))
        assert food_need_of(pops, cls) == int(pool.get("size", 0) or 0) * per, \
            f"{cls}：零役人时需求必须等于 size×人均（与接入前完全一致）"
        assert effective_size(pops, cls) == int(pool.get("size", 0) or 0)
    assert occupation_food_need(pops) == 0.0


# ---------------- ② 役人>0 ⇒ 人口需求↑、粮耗↑（7 处口径一致） ----------------

def test_runner_increases_need_in_all_calibres():
    s = new_game()
    rk = min(s.prefectures)
    pops = s.prefectures[rk]["pops"]
    need0 = food_need_of(pops, "官僚")
    hungry0 = food_insecure_headcount(pops, float(s.grain_price))["total"]
    b0 = build_region_brief(s)
    route0 = next(r for r in b0["routes"] if r["name"] == rk)
    months0 = route0.get("grain_months")
    _set_runners(s, 3000)
    pops = s.prefectures[rk]["pops"]
    need1 = food_need_of(pops, "官僚")
    assert need1 > need0, "役人须产生口粮需求（归挂靠桶）"
    assert occupation_food_need(pops) == 3000 * float(
        GRAIN_CONSUME_PER_CAPITA.get("官僚", 0.5))
    hungry1 = food_insecure_headcount(pops, float(s.grain_price))["total"]
    assert hungry1 >= hungry0, "多出的人口不得凭空消失（需求侧只增不减）"
    b1 = build_region_brief(s)
    route1 = next(r for r in b1["routes"] if r["name"] == rk)
    assert route1.get("grain_months") is not None
    if months0 is not None:
        assert route1["grain_months"] <= months0, "口粮需求上升 ⇒ 粮储月数不得增加"



# ---------------- ③ 统一口径：禁止各模块自算役人粮耗（源码级口径检查） ----------------

def test_no_module_self_computes_occupation_food_need():
    """7 处接入点**一律经** `occupation` 单点；不得再出现 `size × 人均` 自算式。"""
    import io
    import re
    root = os.path.join(_GAME_ROOT, "core")
    targets = ["settlement_common.py", "settlement_granary.py", "settlement_econ.py",
               "region_brief.py", "income_readout.py", "market_readout.py"]
    pat = re.compile(r"size[^\n]*\*\s*(float\()?GRAIN_CONSUME_PER_CAPITA|"
                     r"GRAIN_CONSUME_PER_CAPITA[^\n]*\*\s*[^\n]*size")
    offenders = []
    for fn in targets:
        path = os.path.join(root, fn)
        if not os.path.exists(path):
            continue
        src = io.open(path, encoding="utf-8").read()
        for m in pat.finditer(src):
            line = src[:m.start()].count("\n") + 1
            offenders.append(f"{fn}:{line}")
    assert not offenders, f"下列位置仍在自行相乘（应按 occupation 单点口径）：{offenders}"


# ---------------- ④ money 无无来源变化 ＋ 六桶 size 不变 ＋ 人口不重复 ----------------

def test_runner_integration_money_neutral_and_no_size_change():
    s = new_game()
    rk = min(s.prefectures)
    _set_runners(s, 2500)
    m0 = money.m_all(s)
    before = copy.deepcopy(s.prefectures)
    food_insecure_headcount(s.prefectures[rk]["pops"], float(s.grain_price))
    build_region_brief(s)
    income_source_readout(s, routes=[rk])
    s.population_breakdown()
    assert money.m_all(s) == m0, "役人粮耗接入不得改变货币总量"
    for cls in ("农", "士绅", "工匠", "商人", "官僚", "兵"):
        assert int(s.prefectures[rk]["pops"][cls].get("size", 0) or 0) == \
            int(before[rk]["pops"][cls].get("size", 0) or 0), f"{cls} size 不得变"
    bd = s.population_breakdown()
    assert bd["in_registry_total"] == bd["size_total"] + bd["occupation_total"]
    assert bd["occupation_total"] == sum(
        int((((p.get("pops") or {}).get("官僚") or {}).get("runner_count", 0) or 0))
        for p in s.prefectures.values())


# ---------------- ⑤ 一个结算月：人口字段含役人、财政无异常 ----------------

def test_settlement_month_with_runners_is_consistent():
    """完整月度结算后：人口字段 ＝ Σsize ＋ Σoccupation ＋ 流民（**含役人且不重复**）。"""
    from core.settlement import run_monthly_settlement
    s = new_game()
    _set_runners(s, 2500)
    occ = s.population_breakdown()["occupation_total"]
    assert occ == 50000, "20 路 × 2500 役人"
    run_monthly_settlement(s, seed_offset=7)
    bd = s.population_breakdown()
    assert s.population == max(10_000_000, bd["size_total"] + bd["occupation_total"]
                               + bd["refugees"]), "人口口径必须含役人且不重复增加"
    assert bd["occupation_total"] == 50000, "役人计数不得被结算改动"
    assert int(s.treasury) >= 0, "财政不得异常（国库不得为负）"
