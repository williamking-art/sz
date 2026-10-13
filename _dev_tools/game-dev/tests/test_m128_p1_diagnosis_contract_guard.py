# -*- coding: utf-8 -*-
"""M128 P1 归因**契约守卫**：每条归因必带证据、优先级与枚举不得漂移（测试 only）。

背景：M82 的核心承诺是「**每条归因必须带证据数字**，证据不足只报 `undefined_data`（不臆造）」，
但当时只针对**合成路径**做了 6 条用例；本用例把它变成**真实局全覆盖**的契约：
① `verdict` ∈ 固定枚枚举（漂移立刻红）；
② `reasons` 非空，每条含 `{code, note, evidence}`，且 `evidence` **非空**、`note` 非空；
③ **`reasons[0]["code"] == verdict`**（主瓶颈＝优先级最高者）；
④ **优先级次序**：`undefined_data < no_workshop < raw_shortage < capacity_shortage
   < demand_far_exceeds_supply < ok`（在 reasons 里只能沿该序出现）；
⑤ `coverage_by_output` ∈ [0,1] 或 None；⑥ `survey_diagnosis` 的 `verdicts` 计数与 `route_count`
   自洽、`vees` 排序按 gap 降序；⑦ **只读**（前后深拷一致）。
"""

import copy

from core import commands
from core.domains.economy import p1_pilot_chain as pc

CODES = ["undefined_data", "no_workshop", "raw_shortage", "capacity_shortage",
         "demand_far_exceeds_supply", "ok"]


def _months(state, n=6):
    import core.settlement as S
    for _ in range(n):
        S.run_monthly_settlement(state)
    return state


def test_diagnosis_contract_on_real_game():
    s = _months(commands.new_game())
    rep = pc.survey_diagnosis(s)
    assert rep["routes"], "应有可归因的路"
    for r in rep["routes"]:
        assert r["verdict"] in CODES, r["verdict"]
        assert r["reasons"], r["route"]
        for reason in r["reasons"]:
            assert set(reason) >= {"code", "note", "evidence"}, reason
            assert reason["code"] in CODES, reason
            assert reason["note"], reason
            assert reason["evidence"], (r["route"], reason["code"])      # **必带证据**
        assert r["reasons"][0]["code"] == r["verdict"], r["route"]        # 主瓶颈＝最高优先级
        order = [CODES.index(x["code"]) for x in r["reasons"]]
        assert order == sorted(order), (r["route"], [x["code"] for x in r["reasons"]])
        cov = r.get("coverage_by_output")
        assert cov is None or 0.0 <= float(cov) <= 1.0 + 1e-9, cov


def test_survey_diagnosis_counts_and_order_are_consistent():
    s = _months(commands.new_game())
    rep = pc.survey_diagnosis(s)
    assert sum((rep.get("verdicts") or {}).values()) == rep["route_count"]
    gaps = [(r["evidence"].get("gap") or 0) for r in rep["routes"]]
    assert gaps == sorted(gaps, reverse=True), gaps


def test_diagnosis_is_readonly():
    s = _months(commands.new_game())
    before = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    for route in s.prefectures:
        pc.diagnose_route(s, route)
    pc.survey_diagnosis(s)
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before
