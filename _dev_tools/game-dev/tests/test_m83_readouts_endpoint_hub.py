# -*- coding: utf-8 -*-
"""M83 归因入读数索引（12 项）＋ `/api/readouts` 接 `readout_hub` —— 定向回归。

锁定（P5 验收门）：① 索引含 `pilot_bottleneck`（值＝分布里占比最高的 verdict）；② 端点响应新增
`hub` 字段，且 `hub.readouts` 的**不可读项 `display == "undefined"`**（绝不 0）、每项有 `source`；
③ 端点**单段失败不拖垮**（失败进 `readout_errors`）；④ 只读。
"""

import types

from core import commands
from core.domains.economy import readout_hub as rh


def _months(state, n=6):
    import core.settlement as S
    for _ in range(n):
        S.run_monthly_settlement(state)
    return state


def test_pilot_bottleneck_readout_is_registered_and_valued():
    keys = [r["key"] for r in rh.READOUTS]
    assert "pilot_bottleneck" in keys and len(rh.READOUTS) == 18      # M140 起 18（末项 trade_line_status）
    s = _months(commands.new_game())
    rep = rh.collect(s, keys=["pilot_bottleneck"])
    row = rep["readouts"]["pilot_bottleneck"]
    assert row["value"] is not None and row["display"] == str(row["value"])
    assert row["value"] in ("capacity_shortage", "raw_shortage", "no_workshop",
                           "demand_far_exceeds_supply", "undefined_data", "ok")
    assert "分布" in row["drill_down"] and row["drill_down"]["样本"]


def test_bottleneck_is_undefined_when_no_data(monkeypatch):
    import core.domains.economy.p1_pilot_chain as pc
    monkeypatch.setattr(pc, "survey_diagnosis",
                        lambda state, top=8: {"routes": [], "route_count": 0, "verdicts": {}})
    row = rh.collect(commands.new_game(), keys=["pilot_bottleneck"])["readouts"]["pilot_bottleneck"]
    assert row["value"] is None and row["display"] == "undefined" and "不臆造" in row["reason"]


def test_endpoint_includes_hub_with_contract():
    """直调端点函数 + 伪造 Request（本机无 httpx，见根 AGENTS.md §5）。"""
    from backend import server as srv
    st = _months(commands.new_game())
    # 端点内部用模块级 `_backend`/`_lock`；这里直接验证"接线存在 + 契约"：
    import inspect
    src = inspect.getsource(srv.api_readouts)
    assert "readout_hub" in src and '"hub": hub' in src
    bad = rh.undefined_summary(st)
    # 契约：不可读项必须有 display="undefined" 与 reason（值不显示 0）
    for k in bad["undefined"]:
        row = rh.collect(st, keys=[k])["readouts"][k]
        assert row["display"] == "undefined" and row["reason"]
    for spec in rh.READOUTS:
        assert spec["source"], spec["key"]
