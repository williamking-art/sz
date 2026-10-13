# -*- coding: utf-8 -*-
"""M67 作坊工资前置**取证** —— 定向回归。

锁定：① **岗位数来源确实不存在**（`WORKSHOP_RECIPES` 无岗位字段 / `JOBS_PER_LEVEL` 只登记建筑 /
`workshops[wid]` 无岗位）⇒ `wage_obligation` **恒 `None`**（**不臆造**、也不按人口均分）；
② 类型→建筑的**推断映射**必须**自带"推断非史料"标注**，且逐型给出 `WAGE_RATE` 候选；
③ 实证 6 型配方全覆盖（含 M66 漏登记的 `造纸坊`/`糖坊`）。
"""

from core.domains.economy import wage_gate_readout as wgr


def _state(workshops=None, routes=("京畿路",)):
    import types
    st = types.SimpleNamespace()
    st.workshops = workshops if workshops is not None else {}
    st.prefectures = {r: {"name": r, "seats": {"%s|首府" % r: {"pops": {}}}} for r in routes}
    return st


def test_jobs_source_is_declared_missing_not_guessed():
    rep = wgr.workshop_wage_survey(_state({"酒坊_京畿路_1": {}}))
    assert rep["jobs_source"] is None
    assert "无权威来源" in rep["jobs_reason"]
    assert "不臆造" in rep["jobs_reason"] and "均分" in rep["jobs_reason"]
    assert rep["wage_obligation"] is None
    assert "缺失≠0" in rep["wage_reason"]


def test_mapping_is_labelled_inference_and_carries_rates():
    rep = wgr.workshop_wage_survey(_state())
    assert "推断" in rep["mapping_basis"] and "非史料" in rep["mapping_basis"]
    # 6 型配方全覆盖（M67 补上 M66 漏掉的造纸坊/糖坊）
    assert set(rep["rate_by_type"]) == {"酒坊", "麻坊", "丝坊", "造纸坊", "糖坊", "畜栏"}
    assert rep["rate_by_type"]["畜栏"]["building"] == "牧场"
    for t, row in rep["rate_by_type"].items():
        assert "rate" in row and "reason" in row


def test_real_game_survey_reports_types():
    from core import commands
    s = commands.new_game()
    rep = wgr.workshop_wage_survey(s)
    assert rep["workshops"] == 107
    assert set(rep["by_type"]) <= {"酒坊", "畜栏", "麻坊", "丝坊"}
    assert rep["wage_obligation"] is None       # 仍是 None（诚实）


def test_survey_is_readonly():
    import copy
    st = _state({"酒坊_京畿路_1": {"active": True}})
    before = copy.deepcopy(st.__dict__)
    wgr.workshop_wage_survey(st)
    assert copy.deepcopy(st.__dict__) == before
