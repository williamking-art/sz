# -*- coding: utf-8 -*-
"""召对派系注入回归测试（大臣派系 v1 修复）。

修复的两个 bug：
  1. 派系反查只认「派系领袖」→ 非领袖大臣一律落到「中枢」，persona 立场尽失；
     现优先按档案 `MINISTERS[*]["faction"]`（resolve_faction_key 归一）反查。
  2. `faction_stance` 被填成派系领袖**人名**（FACTION_INIT[faction]["leader"]）；
     现由该派系满意度派生「派系底色」档位词（不外泄数值）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.commands import (  # noqa: E402
    _faction_stance_word, audience_dialogue_prepare,
)
from core.game_state import GameState  # noqa: E402
from content.data import FACTION_INIT  # noqa: E402


def _new_state():
    return GameState("史实")


def _prepare(state, name):
    kwargs, note = audience_dialogue_prepare(state, name, "卿以为当何为先？")
    assert note is None, f"{name} 应可召对：{note}"
    return kwargs


# ------------------------------------------------------------
# 1) 派系反查：档案优先，领袖回退
# ------------------------------------------------------------
def test_nonleader_resolves_faction_from_archive():
    """赵挺之（旧党，非领袖）不得再落到「中枢」。"""
    st = _new_state()
    kwargs = _prepare(st, "赵挺之")
    assert kwargs["faction"] == "旧党"


def test_faction_from_archive_covers_all_ministers():
    """凡档案登记了合法派系的大臣，反查结果必须与档案一致。"""
    from content.ministers.data import MINISTERS
    st = _new_state()
    for name, fig in MINISTERS.items():
        if fig.get("faction") in st.factions:
            kwargs = _prepare(st, name)
            assert kwargs["faction"] == fig["faction"], f"{name} 派系反查错位"


def test_leader_fallback_when_archive_missing(monkeypatch):
    """档案缺失时回退按派系领袖反查（蔡京 = 新党领袖）。"""
    import content.ministers as cm
    monkeypatch.setattr(cm, "HISTORICAL_FIGURES", {})
    st = _new_state()
    kwargs = _prepare(st, "蔡京")
    assert kwargs["faction"] == "新党"


# ------------------------------------------------------------
# 2) 派系底色：档位词而非人名
# ------------------------------------------------------------
def test_faction_stance_is_word_not_name():
    st = _new_state()
    kwargs = _prepare(st, "赵挺之")
    stance = kwargs["faction_stance"]
    leader_names = {v["leader"] for v in FACTION_INIT.values()}
    assert stance not in leader_names, "派系底色不得是领袖人名"
    assert "本派" in stance


def test_faction_stance_word_thresholds():
    st = _new_state()
    assert "昂扬" in _faction_stance_word(st, "新党")      # 85
    assert "循例奉行" in _faction_stance_word(st, "中立派")  # 55
    assert "怨望" in _faction_stance_word(st, "旧党")       # 20


def test_faction_stance_tracks_satisfaction_change():
    """派系满意度跨过阈值时，底色档位词随之变化（玩家作为可感知）。"""
    st = _new_state()
    before = _faction_stance_word(st, "旧党")
    st.factions["旧党"]["satisfaction"] = 90
    after = _faction_stance_word(st, "旧党")
    assert before != after


def test_faction_stance_never_leaks_numbers():
    """底色词与整份 kwargs 注入不得出现满意度数值（脱敏铁律）。"""
    st = _new_state()
    kwargs = _prepare(st, "韩忠彦")
    sat = int(st.factions["旧党"]["satisfaction"])
    assert str(sat) not in kwargs["faction_stance"]
