# -*- coding: utf-8 -*-
"""质量放行门 · 天道落地档作用于诏令数值效果（2026-10-20）。

口径：**只有天道判了落地档**才缩放；未判 ⇒ 系数 1.0（零变更）。

钉住：
1. 无 `_decree_ai` ⇒ `landing_scale == 1.0`；
2. 天道判「半数」⇒ 效果按 0.5 缩放（prestige/treasury/faction_change 等）；
3. 「未办」⇒ 效果归零；「全办」⇒ 原值；
4. 非法档位 ⇒ 1.0（不崩）；
5. 缩放后日志留痕（含 ×系数）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.politics.edict_closure import landing_scale  # noqa: E402


class _S:
    def __init__(self, level=None, prestige=60):
        self.prestige = prestige
        if level:
            self._decree_ai = {"landing_level": level}


def test_no_slot_means_identity():
    assert landing_scale(_S(), {"decree_id": "d1", "effects": {}}) == 1.0


def test_half_level_halves():
    assert landing_scale(_S("半数"), {"decree_id": "d1"}) == 0.5


def test_none_level_zero_and_full():
    assert landing_scale(_S("未办"), {"decree_id": "d1"}) == 0.0
    assert landing_scale(_S("全办"), {"decree_id": "d1"}) == 1.0


def test_invalid_level_is_identity():
    s = _S()
    s._decree_ai = {"landing_level": "随便"}
    assert landing_scale(s, {"decree_id": "d1"}) == 1.0


def test_effect_scaling_applied_and_logged():
    """直接调 _apply_decree_effect：天道判半数 ⇒ 皇威增量减半并写日志。"""
    from core.settlement_decree import _apply_decree_effect

    class _Fake:
        prestige = 60

        def __init__(self):
            self._decree_ai = {"landing_level": "半数"}
            self.applied = []

        def change_prestige(self, d, reason=""):
            self.applied.append(int(d))
            self.prestige += int(d)

    s = _Fake()
    log = []
    _apply_decree_effect(s, {"decree_id": "d1", "title": "加威", "effects": {"prestige": 10}}, log)
    assert s.applied == [5], s.applied
    assert any("落地档" in x for x in log), log


def test_effect_unscaled_without_level():
    from core.settlement_decree import _apply_decree_effect

    class _Fake2:
        prestige = 60

        def __init__(self):
            self.applied = []

        def change_prestige(self, d, reason=""):
            self.applied.append(int(d))

    s = _Fake2()
    _apply_decree_effect(s, {"decree_id": "d2", "title": "加威", "effects": {"prestige": 10}}, [])
    assert s.applied == [10], s.applied