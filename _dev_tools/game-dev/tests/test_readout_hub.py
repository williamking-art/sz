# -*- coding: utf-8 -*-
"""M54 统一读数索引 —— 定向回归。

锁定：每项必备 `{label,value,display,unit,source,drill_down,reason}` · **不可读 ⇒ `display=="undefined"`，
绝不显示 0** · 单个读数抛异常**不拖垮整表**（该项转 undefined + reason，且**留痕**）· 只读 ·
`frontend_wired=False`（**不谎报已接前端**）。
"""

import copy
import types

import pytest

from core.domains.economy import readout_hub as hub


def _bare_state():
    return types.SimpleNamespace()          # 什么都没有 ⇒ 多数读数应 undefined


def test_every_readout_has_required_fields_and_never_zero_for_undefined():
    rep = hub.collect(_bare_state())
    assert rep["readouts"], "读数表不得为空"
    for key, row in rep["readouts"].items():
        for f in ("label", "value", "display", "unit", "source", "drill_down", "reason"):
            assert f in row, f"{key} 缺字段 {f}"
        assert row["source"] and row["drill_down"]
        if row["value"] is None:
            assert row["display"] == "undefined", f"{key} 不可读却显示 {row['display']!r}"
            assert row["display"] != "0"                      # P5：缺失不显示 0
            assert row["reason"], f"{key} 不可读但没给 reason"
        else:
            assert row["display"] != "undefined"


def test_frontend_is_not_claimed():
    rep = hub.collect(_bare_state())
    assert rep["frontend_wired"] is False                     # 不谎报"已接前端"
    assert "前端面板未接" in rep["note"]


def test_one_failing_readout_does_not_break_table(monkeypatch):
    def _boom(state):
        raise RuntimeError("模拟读数失败")
    monkeypatch.setattr(hub, "READOUTS", tuple(
        [dict(s) for s in hub.READOUTS[:2]]
        + [{"key": "boom", "label": "会炸的读数", "unit": "-", "fn": _boom, "source": "test:boom"}]
    ))
    rep = hub.collect(_bare_state())
    assert set(rep["readouts"]) == {hub.READOUTS[0]["key"], hub.READOUTS[1]["key"], "boom"}
    bad = rep["readouts"]["boom"]
    assert bad["value"] is None and bad["display"] == "undefined"
    assert "计算失败" in bad["reason"]


def test_undefined_summary_lists_reasons():
    rep = hub.undefined_summary(_bare_state())
    assert rep["count"] == len(rep["undefined"])
    assert rep["total"] == len(hub.READOUTS)
    assert all(isinstance(v, str) and v for v in rep["undefined"].values())


def test_index_matches_collect_and_is_readonly(monkeypatch):
    monkeypatch.setattr(hub, "READOUTS", tuple(hub.READOUTS[:3]))
    st = _bare_state()
    before = copy.deepcopy(st.__dict__)
    rows = hub.index(st)
    assert [r["key"] for r in rows] == [s["key"] for s in hub.READOUTS]
    assert copy.deepcopy(st.__dict__) == before               # **零写入**


def test_collect_keys_filter(monkeypatch):
    keys = [hub.READOUTS[0]["key"], hub.READOUTS[2]["key"]]
    rep = hub.collect(_bare_state(), keys=keys)
    assert set(rep["readouts"]) == set(keys)
    assert rep["ok_count"] + rep["undefined_count"] == 2
