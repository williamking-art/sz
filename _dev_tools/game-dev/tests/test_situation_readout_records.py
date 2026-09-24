# -*- coding: utf-8 -*-
"""批 2 · 局势 readout 投影 state.situations + 开局种子挂载。

验收（对应方案批 2）：玩家打开面板 3 秒答出「怎么算赢 / 怎么算崩 / 不动会怎样」。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.situations import build_situation_readout  # noqa: E402


def test_new_game_seeds_three_opening_situations():
    """new_game 挂载开局三条局势（幂等键 event_pool:*）。"""
    from core.commands import new_game
    s = new_game("史实")
    assert isinstance(s.situations, list)
    ids = {r.get("id") for r in s.situations if isinstance(r, dict)}
    assert "event_pool:huashigang_minyuan" in ids
    assert "event_pool:dongnan_caikui" in ids
    assert "event_pool:liaoshi_bianbei" in ids


def test_readout_projects_records_with_public_conditions():
    """readout 含 record 来源条目，且成败/持续代价/双向语义明文公开。"""
    from content.situation_seeds import seed_initial_situations
    s = GameState("史实")
    seed_initial_situations(s, turn=0)
    out = build_situation_readout(s)
    items = [r for r in out["items"] if r.get("source") == "record"]
    assert len(items) == 3, f"应投影 3 条 record，实际 {len(items)}"
    titles = {r["title"] for r in items}
    assert titles == {"花石纲民怨", "东南财政亏空", "辽事边备"}
    for r in items:
        assert r.get("resolve_condition_text"), f"{r['title']} 缺达成条件文案"
        assert r.get("fail_condition_text"), f"{r['title']} 缺失败条件文案"
        assert r.get("ongoing_text"), f"{r['title']} 缺持续代价文案"
        assert r.get("bar_good_meaning"), f"{r['title']} 缺推进语义"
        assert r.get("bar_bad_meaning"), f"{r['title']} 缺恶化语义"
        assert r.get("bar_value") is not None
        assert 0 <= int(r["bar_value"]) <= 100
        assert r.get("status") == "active"
        # 执行通道应下发（record 来源参与「下了诏≠办了解释」）
        assert "execution_channels" in r


def test_readout_record_severity_reflects_bar():
    """bar 越低越严重（与 legacy 同则：未推进 → 更紧迫）。"""
    from content.situation_seeds import seed_initial_situations
    s = GameState("史实")
    created = seed_initial_situations(s, turn=0)
    created[0]["bar_value"] = 10   # 花石纲：更未推进
    created[1]["bar_value"] = 90   # 东南财政：接近解除
    out = build_situation_readout(s)
    by_title = {r["title"]: r for r in out["items"] if r.get("source") == "record"}
    assert by_title["花石纲民怨"]["severity"] > by_title["东南财政亏空"]["severity"]


def test_new_game_seed_idempotent_via_readout():
    """重复 new_game 不炸；readout 始终只 3 条 record（幂等键去重）。"""
    from core.commands import new_game
    from content.situation_seeds import seed_initial_situations
    s = new_game("史实")
    seed_initial_situations(s, turn=1)   # 再次 seed 应跳过
    out = build_situation_readout(s)
    items = [r for r in out["items"] if r.get("source") == "record"]
    assert len(items) == 3
