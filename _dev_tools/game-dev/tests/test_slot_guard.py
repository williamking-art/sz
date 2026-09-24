# -*- coding: utf-8 -*-
"""存档槽位合法性守卫（第四轮全审）。

槽位约定（见 core/save_load.py 的 SLOT_MIN 注释，**勿擅自收窄**）：
  0     = 自动存档槽（`finish_turn` 每年正月与终局写入）
  1–5   = 玩家可见槽（`get_save_slots` 只列这些）
  >5    = 测试/临时槽（多个回归用例刻意用 6/7/8/9/99 做隔离）

故本处只守「非负整数」这一条底线：曾提议钳到 1–5，但那会打断自动存档
（slot=0）并炸掉一批用例，已否决，在此留测试用例固化该结论。
"""
import os
import sys

import pytest

from core import save_load as sl


def test_slot_zero_is_auto_save_slot():
    """槽 0 是生产自动存档槽，必须可写可读（钳到 1–5 会打断它）。"""
    assert sl._slot_ok(0) is True


def test_high_slots_allowed_for_isolation():
    """>5 的槽供测试隔离，必须可写（用例确实用到 6/7/8/9/99）。"""
    for s in (6, 7, 8, 9, 99):
        assert sl._slot_ok(s) is True


def test_negative_slot_rejected():
    assert sl._slot_ok(-1) is False
    assert sl._slot_ok(-99) is False


def test_non_int_slot_rejected():
    """类型注入兜底：HTTP 层 Pydantic 已挡，此处挡内部调用。"""
    for bad in ("1", 1.5, None, [1], {"slot": 1}):
        assert sl._slot_ok(bad) is False, f"{bad!r} 不应通过槽位校验"
    # bool 是 int 子类，但语义上不是合法槽位
    assert sl._slot_ok(True) is False


def test_save_game_rejects_bad_slot(state_like):
    """非法槽位 → 返回 False 且不写盘。"""
    assert sl.save_game(state_like, -1) is False
    assert sl.save_game(state_like, "7") is False
    assert not any(n.startswith("slot_-") for n in os.listdir(sl.SAVE_DIR))


def test_load_game_bad_slot_returns_none_without_raise():
    """读档是高频探测路径：非法槽位与缺档同口径返回 None，不抛。"""
    assert sl.load_game(-1) is None
    assert sl.load_game("7") is None


def test_save_load_roundtrip_still_works(state_like):
    """守卫不得误伤正常读写。"""
    assert sl.save_game(state_like, 3) is True
    assert sl.load_game(3) is not None


@pytest.fixture
def state_like(tmp_path):
    """最小可存档状态：用真实 GameState 避免 save_game 内部接口漂移。"""
    sys.path  # 保持 game/ 在 sys.path（conftest 已注入）
    from core.game_state import GameState
    st = GameState(difficulty="史实")
    st.turn = 1
    yield st
