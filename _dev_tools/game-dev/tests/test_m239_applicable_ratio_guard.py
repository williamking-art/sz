# -*- coding: utf-8 -*-
"""M239 P2 就绪度**口径修正**的定向用例（M238 落地）。

锁定四件事：
① `applicable_fields` 与 `not_applicable` **互补且并集 == FIELDS**；
② `not_applicable` 的每一项，**投影里该字段确实 `defined=False` 且带 `reason`**（M233 纪律的机械化检查：
   「不适用」必须有官方理由，不能凭空删字段）；
③ `applicable_overall` 的**分母是适用集**（与全 14 分母的 `defined_ratio` 口径可区分）；
④ **兼容**：`defined_by_field` / `defined_ratio` 仍存在且仍为全 14 字段口径。
"""

import random

from core import commands
from core.domains.economy import entity_projection as ep


def _s():
    random.seed(20261013)
    return commands.new_game()


def _check_complement(rep, na_const):
    ap = set(rep["applicable_fields"])
    na = set(rep["not_applicable"])
    assert ap & na == set(), (ap & na)
    assert ap | na == set(ep.FIELDS), (set(ep.FIELDS) - (ap | na))
    assert na == set(na_const), na


def test_building_complement_and_constants():
    rep = ep.survey_entity_projection(_s())
    _check_complement(rep, ep.NOT_APPLICABLE_BUILDING)
    assert rep["applicable_fields"] == [k for k in ep.FIELDS if k not in ep.NOT_APPLICABLE_BUILDING]


def test_workshop_complement_and_constants():
    rep = ep.survey_workshop_projection(_s())
    _check_complement(rep, ep.NOT_APPLICABLE_WORKSHOP)
    assert len(rep["applicable_fields"]) == len(ep.FIELDS) - len(ep.NOT_APPLICABLE_WORKSHOP)


def test_not_applicable_entries_have_reason_in_projection():
    """「不适用」的每一项，投影里必须 `defined=False` **且 reason 非空**（不许凭空归类）。"""
    s = _s()
    route = next(iter(s.prefectures))
    seat = next(iter(s.prefectures[route]["seats"]))
    bname = next(iter(s.prefectures[route]["seats"][seat].get("buildings") or {"水利": 1}))
    f = ep.project_building(s, route, seat, bname)["fields"]
    for k in ep.NOT_APPLICABLE_BUILDING:
        row = f.get(k) or {}
        assert row.get("defined") is False, (k, row)
        assert row.get("reason"), (k, row)                     # 必须有官方理由
    wid = next(iter(s.workshops))
    fw = ep.project_workshop(s, wid)["fields"]
    for k in ep.NOT_APPLICABLE_WORKSHOP:
        row = fw.get(k) or {}
        assert row.get("defined") is False, (k, row)
        assert row.get("reason"), (k, row)


def test_applicable_overall_uses_applicable_denominator():
    """`applicable_overall` 分母＝适用集（与 14 分母的 `defined_ratio` 可区分）。"""
    for rep, na in ((ep.survey_entity_projection(_s()), ep.NOT_APPLICABLE_BUILDING),
                    (ep.survey_workshop_projection(_s()), ep.NOT_APPLICABLE_WORKSHOP)):
        total = rep.get("buildings") or rep.get("workshops")
        ap = rep["applicable_fields"]
        num = sum(1 for k in ap for _ in range(int(round((rep["applicable_ratio"][k] or 0) * total))))
        assert rep["applicable_overall"] == round(num / (total * len(ap)), 4)
        # 兼容：全 14 口径仍在
        assert isinstance(rep["defined_by_field"], dict) and isinstance(rep["defined_ratio"], dict)
        assert set(rep["defined_ratio"]) == set(ep.FIELDS)
