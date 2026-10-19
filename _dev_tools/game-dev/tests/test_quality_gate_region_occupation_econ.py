# -*- coding: utf-8 -*-
"""P5.6 占领经济后果（2026-10-19；用户裁定：损失比例由天道裁决）。

链条：天道出掠夺烈度档位（无/轻/中/重/极重）→ 程序换算损失/残破（架构纪律）。
缺档兜底：按攻城方式（受降/围城/力攻/屠城）程序推导；再缺 ⇒ 中性中 且标明来源。

本门用独立 fixture（不依赖 new_game）：
1. 天道档位生效（极重 ⇒ 财富 −30%、残破 0.45、source=天道）；
2. 无天道档 + 受降 ⇒ 轻（−4%），source=程序推导；
3. 无天道档、无攻城方式 ⇒ 中（−9%）且 source 明确（不是精确值）；
4. provider 注入优先于程序推导；
5. 无档时不再出现旧的固定 −15%（防写死回潮）；
6. 掠夺=损失财富50%，同源；残破遗留+逐月恢复+封顶。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.diplomacy import regime_intake as ri  # noqa: E402


class _S:
    def __init__(self, severity=None):
        self._occupation_ai = {"loot_severity": severity, "note": "测试"} if severity else {}
        self.regions = {
            "p0_a": {"level": "T1", "name": "甲州", "owner": "辽", "owner_at_init": "辽",
                     "parent": "p0", "land": 1000,
                     "pop": {"农": {"size": 100000, "wealth": 1000000, "grain": 500000}}},
        }
        self.external_regimes = {"辽": {"treasury": 0}, "金": {"treasury": 0}}
        self.prefectures = {}


def _run(s, capture_type=""):
    return ri.apply_occupation_damage(s, ["p0_a"], to_regime="金", capture_type=capture_type)


def test_heaven_severity_drives_loss():
    s = _S(severity="极重")
    out = _run(s)
    assert out["severity"] == "极重" and out["severity_source"] == "天道"
    pop = s.regions["p0_a"]["pop"]["农"]
    assert pop["size"] == 94000
    assert pop["wealth"] == 700000
    assert pop["grain"] == 350000
    assert s.regions["p0_a"]["devastation"] == 0.45
    assert s.external_regimes["金"]["treasury"] == 150000


def test_light_severity():
    s = _S(severity="轻")
    out = _run(s)
    assert out["severity"] == "轻"
    assert s.regions["p0_a"]["pop"]["农"]["wealth"] == 960000
    assert s.regions["p0_a"]["devastation"] == 0.80


def test_capture_type_fallback_when_no_heaven():
    s = _S()
    out = _run(s, capture_type="受降")
    assert out["severity"] == "轻"
    assert "程序推导" in out["severity_source"]
    assert s.regions["p0_a"]["pop"]["农"]["wealth"] == 960000


def test_neutral_fallback_marks_source():
    s = _S()
    out = _run(s)
    assert out["severity"] == "中"
    assert "兜底" in out["severity_source"]


def test_no_hardcoded_fifteen_percent():
    s = _S()
    out = _run(s)
    assert s.regions["p0_a"]["pop"]["农"]["wealth"] != 850000
    assert out["severity"] != "重"


def test_provider_injection_beats_fallback():
    s = _S()
    ri.register_occupation_severity_provider(lambda st, ids: {"loot_severity": "重", "note": "provider"})
    try:
        out = _run(s)
        assert out["severity"] == "重"
        assert "provider" in out["severity_source"]
        assert s.regions["p0_a"]["pop"]["农"]["wealth"] == 850000
    finally:
        ri._PROVIDERS.clear()


def test_loot_equals_half_lost_wealth():
    s = _S(severity="重")
    out = _run(s)
    assert out["lost"]["wealth"] == 150000
    assert out["loot"] == 75000
    assert s.external_regimes["金"]["treasury"] == out["loot"]


def test_devastation_kept_and_recovery_caps():
    s = _S(severity="重")
    _run(s)
    assert s.regions["p0_a"]["devastation"] == 0.60
    for _ in range(4):
        ri.recover_devastation(s)
    assert s.regions["p0_a"]["devastation"] == 1.0