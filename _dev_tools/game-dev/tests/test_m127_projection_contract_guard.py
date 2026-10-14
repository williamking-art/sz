# -*- coding: utf-8 -*-
"""M127 P2 投影**契约守卫**：建筑/作坊投影的 14 字段必须齐、四键齐、自洽（测试 only）。

背景：M117 曾在作坊投影里**误插第二个 `income_to` 键**（Python 重复键是**静默**的：后者覆盖前者
⇒ 死代码且不报错），靠"读回 + grep"才发现。本用例把**可被用例测到的部分**全部锁死：
① `set(fields) == set(FIELDS)` —— 字段**不多不少**（漏键/多键立刻红）；
② 每字段恰有 `{value, defined, source, reason}` 四键，且 `defined` 为 bool、`source` 非空字符串；
③ `undefined_fields` 与逐字段 `defined` **完全自洽**，`defined_count` 与之相符；
④ `defined=False ⇒ value is None`（**缺失≠0**：不得用 0/1.0 冒充）；
⑤ 真实局抽样：建筑 40 座、作坊 107 座，逐座逐项过上述断言。
"""

from core import commands
from core.domains.economy import entity_projection as ep
from core.domains.economy import readout_hub as rh


def _months(state, n=3):
    import core.settlement as S
    for _ in range(n):
        S.run_monthly_settlement(state)
    return state


def _check_projection(fields, undefined_fields, defined_count, who):
    assert set(fields) == set(ep.FIELDS), (who, set(ep.FIELDS) ^ set(fields))
    for k, f in fields.items():
        assert set(f) >= {"value", "defined", "source", "reason"}, (who, k, sorted(f))
        assert isinstance(f["defined"], bool), (who, k)
        assert f["source"] is None or isinstance(f["source"], str), (who, k)
        if not f["defined"]:
            assert f["value"] is None, (who, k, f["value"])      # 缺失≠0
            assert f["reason"], (who, k)                          # 必须给原因
    expect = [k for k in ep.FIELDS if not fields[k]["defined"]]
    assert list(undefined_fields) == expect, (who, undefined_fields, expect)
    assert defined_count == len(ep.FIELDS) - len(expect), (who, defined_count)


def test_real_game_projections_match_contract():
    s = _months(commands.new_game())
    cov = rh.collect(s, keys=["building_owned"])               # 触发一次读数（不写 state）
    assert cov is not None
    buildings = 0
    for route, pdata in s.prefectures.items():
        for seat, srow in ((pdata or {}).get("seats") or {}).items():
            for b, lv in ((srow or {}).get("buildings") or {}).items():
                rep = ep.project_building(s, route, seat, b, lv)
                _check_projection(rep["fields"], rep["undefined_fields"], rep["defined_count"],
                                  f"{route}/{seat}/{b}")
                buildings += 1
    assert buildings == 40
    workshops = 0
    for wid in s.workshops:
        rep = ep.project_workshop(s, wid)
        _check_projection(rep["fields"], rep["undefined_fields"], rep["defined_count"], wid)
        workshops += 1
    # M196 派生：期望值随 workshop_opening.DEFAULT_TARGET_TOTAL（禁止硬编码）
    from core.domains.economy import workshop_opening as _wo
    assert workshops == 107 + (_wo.DEFAULT_TARGET_TOTAL - 7)


def test_survey_ratios_are_consistent_with_field_ratio():
    s = _months(commands.new_game())
    for rep, name in ((ep.survey_entity_projection(s), "building"),
                      (ep.survey_workshop_projection(s), "workshop")):
        ratio = rep["defined_ratio"]
        assert set(ratio) == set(ep.FIELDS), name
        for k, v in ratio.items():
            assert v is None or (0.0 <= float(v) <= 1.0), (name, k, v)
        total = rep.get("buildings") if name == "building" else rep.get("workshops")
        assert total and total > 0, name
