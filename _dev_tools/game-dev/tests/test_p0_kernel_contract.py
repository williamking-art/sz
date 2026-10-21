# -*- coding: utf-8 -*-
"""P0 地基契约：pack / calendar / objectives / decision / state.meta（零行为）。"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.kernel.calendar import Calendar, sync_state
from core.foundation.kernel.decision import (
    DecisionRequest, DecisionResult, DecisionService,
)
from core.foundation.kernel.objectives import ObjectiveDef, ObjectiveError, ObjectiveRegistry
from core.foundation.kernel.pack import PackError, load_pack


def test_song_pack_manifest_loads():
    m = load_pack("song_1101")
    assert m.pack_id == "song_1101" and m.dynasty == "宋"
    assert m.start_year == 1101 and m.start_month == 1
    assert m.schema_version >= 1


def test_pack_rejects_unknown_and_invalid(tmp_path):
    try:
        load_pack("no_such_pack")
    except PackError as exc:
        assert "不存在" in str(exc)
    else:
        raise AssertionError("未知 pack 必须报错")
    d = tmp_path / "bad"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"pack_id": "bad"}), encoding="utf-8")
    try:
        load_pack("bad", root=tmp_path)
    except PackError as exc:
        assert "缺字段" in str(exc)
    else:
        raise AssertionError("缺字段必须报错")


def test_calendar_relative_cycles_and_advance():
    c = Calendar(start_year=1101, year=1101, month=12, era_name="建中靖国")
    assert c.year_index() == 0 and c.exam_cycle(3) is True
    c.year = 1102
    assert c.year_index() == 1 and c.exam_cycle(3) is False
    c.advance()
    assert (c.year, c.month) == (1103, 1)
    assert c.apply_era_names({1101: "建中靖国", 1102: "崇宁"}) == "崇宁"


def test_sync_state_mirrors_without_touching_state():
    class S:
        year, month, era_name = 1105, 7, "崇宁"
        calendar = Calendar(start_year=1101, year=1101, month=1)

    s = S()
    sync_state(s)
    assert (s.calendar.year, s.calendar.month, s.calendar.era_name) == (1105, 7, "崇宁")
    assert (s.year, s.month) == (1105, 7)


def test_objective_registry_and_decision_fail_closed():
    reg = ObjectiveRegistry()
    obj = ObjectiveDef("tax_stance", "choose", options=("strict", "moderate", "lenient"),
                       facts=("tax_base",), domain="fiscal")
    reg.register(obj)
    assert reg.ids() == ["tax_stance"]
    try:
        reg.get("missing")
    except ObjectiveError:
        pass
    else:
        raise AssertionError("未注册目标必须报错")
    svc = DecisionService(engine=None, registry=reg)
    r = svc.decide(DecisionRequest("tax_stance", {"tax_base": 1}, ("strict",)))
    assert isinstance(r, DecisionResult) and r.defined is False
    assert "未接决策引擎" in r.reason


def test_new_game_has_meta_calendar_and_decision_log():
    from core.commands import new_game

    s = new_game("史实")
    assert s.meta["pack_id"] == "song_1101"
    assert s.calendar is not None and s.calendar.start_year == 1101
    assert (s.calendar.year, s.calendar.month) == (s.year, s.month)
    assert isinstance(s.decision_log, list)


def test_live_engine_contract_and_logging():
    class Engine:
        def decide(self, request):
            return DecisionResult(objective=request.objective, verdict=request.options[0],
                                  probability=0.9, defined=True, provider="test")

    reg = ObjectiveRegistry()
    reg.register(ObjectiveDef("pick", "choose", options=("a", "b"), facts=("x",)))
    logged = []
    svc = DecisionService(engine=Engine(), registry=reg,
                          logger=lambda req, res: logged.append((req.objective, res.verdict)))
    r = svc.decide(DecisionRequest("pick", {"x": 1}, ("a",)))
    assert r.verdict == "a" and r.defined is True
    assert logged == [("pick", "a")]
