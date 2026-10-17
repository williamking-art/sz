# -*- coding: utf-8 -*-
"""三年周期人事闭环接线（M300）：科举大比 + 磨勘考课（2026-10-18 全审）。

锁三件事：
1. 科次年正月触发 imperial_exam 全流程（解试→省试→殿试），同一年不重复开科；
2. 第 18/54… 回合触发磨勘考课，同回合不重复；
3. 触发失败只记 personnel_cycle_error + WARN，不静默、不阻断官制结算。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from application.game_init import new_game  # noqa: E402
from core.domains.administration.settlement_officialdom import (  # noqa: E402
    _settle_officialdom,
)


def test_exam_cycle_triggers_in_exam_year_and_is_idempotent():
    s = new_game("史实")
    s.year, s.month = 1104, 1          # (1104-1101)%3 == 0 ⇒ 科次年
    log = []
    _settle_officialdom(s, log)
    detail = (s.exam or {}).get("last_cohort_detail")
    assert detail and detail.get("taken", 0) > 0, "科次年正月应开科取士"
    assert int(detail.get("year", 0) or 0) == 1104
    assert any("御试唱名" in x or "科举" in x for x in log), log

    cohorts = len((s.exam or {}).get("cohorts") or [])
    _settle_officialdom(s, log)
    assert len((s.exam or {}).get("cohorts") or []) == cohorts, "同一年不得重复开科"


def test_exam_cycle_does_not_trigger_off_year():
    s = new_game("史实")
    s.year, s.month = 1102, 1          # 非科次年
    before = (s.exam or {}).get("last_cohort_detail")
    _settle_officialdom(s, [])
    assert (s.exam or {}).get("last_cohort_detail") == before, "非科次年不得开科"


def test_appraisal_cycle_triggers_at_turn_18_and_is_idempotent():
    s = new_game("史实")
    s.turn = 18
    s.statistics.pop("last_appraisal_turn", None)
    log = []
    _settle_officialdom(s, log)
    assert s.statistics.get("last_appraisal_turn") == 18, "第 18 回合应触发磨勘"
    assert any("三年考课" in x for x in log), log

    before = s.statistics.get("last_appraisal_turn")
    _settle_officialdom(s, log)
    assert s.statistics.get("last_appraisal_turn") == before, "同回合不得重复磨勘"


def test_appraisal_cycle_does_not_trigger_off_cycle():
    s = new_game("史实")
    s.turn = 17
    s.statistics.pop("last_appraisal_turn", None)
    _settle_officialdom(s, [])
    assert not s.statistics.get("last_appraisal_turn"), "第 17 回合不应磨勘"


def test_exam_failure_is_recorded_not_silent(monkeypatch):
    s = new_game("史实")
    s.year, s.month = 1104, 1
    s.statistics.pop("personnel_cycle_error", None)

    import core.domains.administration.imperial_exam as ie

    def _boom(*a, **k):
        raise RuntimeError("模拟科举失败")

    monkeypatch.setattr(ie, "run_triennial_exam_full", _boom)
    log = []
    _settle_officialdom(s, log)          # 不应抛出
    assert "exam:" in str(s.statistics.get("personnel_cycle_error", ""))
    assert any("科举" in x and "WARN" in x for x in log), log
    assert int((s.exam or {}).get("last_exam_year", 0) or 0) != 1104, "失败不得记成已开科"