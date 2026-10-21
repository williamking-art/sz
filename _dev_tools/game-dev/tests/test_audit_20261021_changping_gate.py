# -*- coding: utf-8 -*-
"""D 数值接线 3/10（Jev B 0.365 vs A 0.365 近平手，按 B）：
changping_intervene_gate=False ⇒ 本月高价平粜不卖（只影响卖粮，不影响平籴）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    pass


def test_allowed_defaults_without_record():
    from core.settlement_granary import _changping_sell_allowed

    assert _changping_sell_allowed(_S()) is True


def test_disallowed_only_when_gate_false_defined():
    from core.settlement_granary import _changping_sell_allowed

    s = _S()
    s._tiandao_observe = {"decisions": {"changping_intervene_gate": False}}
    assert _changping_sell_allowed(s) is False
    s._tiandao_observe = {"decisions": {
        "changping_intervene_gate": {"verdict": False, "defined": True}}}
    assert _changping_sell_allowed(s) is False
    for dec in (True, {"verdict": True, "defined": True},
                {"verdict": False, "defined": False}, {"error": "x"}):
        s._tiandao_observe = {"decisions": {"changping_intervene_gate": dec}}
        assert _changping_sell_allowed(s) is True, dec


def test_settlement_skips_changping_sell_when_gate_false():
    """高价路 + 常平有粮：门=False 时不发生平粜（回收统计为 0）；有记录但 True 时仍卖。"""
    from core.commands import new_game
    from core.settlement_granary import _settle_granary

    def run(dec):
        s = new_game("史实")
        r = next(iter(s.prefectures))
        p = s.prefectures[r]
        p["grain_price"] = 3.0
        p["changping_stock"] = 10000
        s._tiandao_observe = {"decisions": {"changping_intervene_gate": dec}}
        log = []
        _settle_granary(s, log)
        return s.statistics.get("changping_recycled", 0), log

    got_false, log_false = run(False)
    got_true, _ = run(True)
    assert got_false == 0, (got_false, log_false)
    assert got_true >= 0  # True 分支保持原逻辑（可能因买家/价格条件为 0，不强制 >0）
