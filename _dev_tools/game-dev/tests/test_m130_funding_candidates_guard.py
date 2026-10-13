# -*- coding: utf-8 -*-
"""M130 D 线**候选资金契约守卫**：六候选固定 · 到位率＝min(1,池/需求) · 不可读必带原因 · 只读。

背景：`owner_candidates_shadow` 是 **N1（营运资金来源）裁定的唯一数据依据**，其数字此前是
**手工核对**的（M69 就抓到过"漏算 80 座作坊 ⇒ 需求 22,000,000 偏低、应为 28,400,000"）。
本用例把它的**可自洽部分**机器化：候选集合固定、**到位率公式自洽**、池/原因二择、只读。
"""

import copy

from core import commands
from core.domains.economy import owner_candidates_shadow as oc


def _months(state, n=6):
    import core.settlement as S
    for _ in range(n):
        S.run_monthly_settlement(state)
    return state


def test_candidate_set_and_cover_formula_are_consistent():
    s = _months(commands.new_game())
    rep = oc.survey_owner_candidates(s)
    cands = rep["candidates"]
    assert len(cands) == 6, [c.get("key") for c in cands]          # 六候选固定（M58/66）
    need_row = rep.get("procure_need")
    # 🔴 形状即契约：`{value, reason, unreadable…}`（不是裸数）——本次守卫当场钉住
    assert isinstance(need_row, dict) and "value" in need_row and "reason" in need_row, need_row
    need = need_row["value"]
    assert isinstance(need, (int, float)) and need > 0, need_row
    for c in cands:
        assert c.get("key") and c.get("label"), c
        pool, cover = c.get("pool"), c.get("procure_cover")
        reason = c.get("pool_reason")
        # 池不可读 ⇒ 必须有原因（缺失≠0，不臆造）
        if pool is None:
            assert reason, c.get("key")
            assert cover is None, c.get("key")
            continue
        assert isinstance(pool, (int, float)) and pool >= 0, (c.get("key"), pool)
        assert reason is None, (c.get("key"), reason)
        # **到位率公式自洽**：min(1, 池/需求)
        expect = min(1.0, float(pool) / float(need))
        assert cover is not None and abs(float(cover) - expect) < 1e-9, \
            (c.get("key"), cover, expect)
        assert 0.0 <= float(cover) <= 1.0, (c.get("key"), cover)
        assert c.get("pool_source"), c.get("key")                   # 单点来源必须写明
        assert c.get("profit_to"), c.get("key")                     # 利润去向必须写明
        assert c.get("parallel_ledger_violation") in (True, False)


def test_candidate_survey_is_readonly_and_need_is_stable():
    s = _months(commands.new_game())
    before = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    a = oc.survey_owner_candidates(s)
    b = oc.survey_owner_candidates(s)
    assert a.get("procure_need") == b.get("procure_need")           # 纯函数（同态两次一致）
    assert a.get("wage_need") == b.get("wage_need")
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before
