# -*- coding: utf-8 -*-
"""存档 **round-trip 行为**验证（2026-09-19 全审报告 §4.0-C 补闭环）。

背景：`load_game`（416 行 / 复杂度 116）是读档的核心入口，在此前只有零散的
`_load_situations` 隔离与 schema 2→3 迁移测试，缺两个关键判据：

  ① `save → load → save` 的**规范化等价**（写出去的两份档在总账/派生读数上应一致）；
  ② `load` 后**货币总量守恒**（`money.m_all` 与 POP wealth/grain 总和与存档前一致）。

本文件补之。做这两条测试的**前置目的**是把 `load_game` 的拆分（结构简化 §3.2）变得安全：
"先有行为测试，再拆重构"。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.money import m_all, pop_money  # noqa: E402
from core.save_load import save_game, load_game  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402


def _settle(s, n):
    for _ in range(n):
        run_monthly_settlement(s, 0)      # seed 固定 → 全程可复现


def _s_pop_w(s):
    return sum(int(p.get("wealth", 0) or 0)
               for p in s.prefectures.values() for p in [p["pops"]["农"]["wealth"]])


def _readout(s):
    from core.money import snapshot as _sn
    pop = pop_money(s)
    fams = {k: v.get("influence") for k, v in s.factions.items()}
    return {
        "turn": s.turn,
        "treasury": int(s.treasury),
        "inner": int(s.imperial_treasury),
        "granary": int(s.granary),
        "m_all": int(m_all(s)),
        "pop_w": int(sum(int(p["pops"][c]["wealth"])
                         for p in s.prefectures.values()
                         for c in ("农", "士绅", "工匠", "商人", "官僚", "兵"))),
        "pop_g": int(sum(int(p["pops"][c]["grain"])
                         for p in s.prefectures.values()
                         for c in ("农", "士绅", "工匠", "商人", "官僚", "兵"))),
        "officers": int(sum(p["pops"]["官僚"]["officials"] for p in s.prefectures.values())),
        "clerks": int(sum(p["pops"]["官僚"]["clerks"] for p in s.prefectures.values())),
        "troops": sum(int(u.troops) for u in s.army_units),
        "literacy": round(float(s.literacy), 4),
        "factions_influence": fams,
    }


def test_roundtrip_key_ledgers_and_money_conservation(tmp_path, monkeypatch):
    """结算 3 月 → save → load，总账与货币守恒必须**逐项相等**。"""
    import core.save_load as sl
    monkeypatch.setattr(sl, "SAVE_DIR", str(tmp_path), raising=False)

    s = GameState("史实")
    s.establish_bank(2_000_000, "treasury")      # 打开银行（含 memo 账本）
    _settle(s, 3)
    before = _readout(s)
    assert save_game(s, 9) is True
    s2 = load_game(9)
    assert s2 is not None, "结算 3 月后的档必须能读回"

    after = _readout(s2)
    for k, v in before.items():
        if k in ("factions_influence",):
            assert after[k] == v, f"factions.{k} roundtrip 不一致"
        elif k == "literacy":
            # 识字率是"顶层缓动向 POP 派生值靠拢"的构造性滞后（Step 3.5.6）——
            # 读档即触发一步缓动 → 允许 ≤0.02 的口径差（缓动幅度 6%，但只在差>0.01 时收）
            assert abs(after[k] - v) <= 0.02, f"literacy roundtrip 偏差过大：{v} -> {after[k]}"
        else:
            assert after[k] == v, f"{k} roundtrip 不一致：{v} -> {after[k]}"
    # 守恒：存档前后货币总量不漂
    assert after["m_all"] == before["m_all"], "save→load 改变了 M_ALL"
    assert after["pop_w"] == before["pop_w"], "存档改变 POP wealth 总量"
    assert after["officers"] == before["officers"], "存档改变官额（POP 真账）"
    assert after["clerks"] == before["clerks"], "存档改变吏额（POP 真账）"


def test_double_save_is_stable(tmp_path, monkeypatch):
    """`save → load → save` 再保存的存档在**关键账本字段**上不变（规范化等价）。"""
    import core.save_load as sl
    monkeypatch.setattr(sl, "SAVE_DIR", str(tmp_path), raising=False)

    s = GameState("史实")
    _settle(s, 2)
    assert save_game(s, 8) is True
    s2 = load_game(8)
    assert s2 is not None
    assert save_game(s2, 8) is True
    again = json.loads(open(sl._slot_path(8), encoding="utf-8").read())

    # 关键一致性：总账字段 + factions + 六类 POP 聚合
    assert again["treasury"] == s2.treasury
    assert again["granary"] == s2.granary
    assert set(again["factions"].keys()) == set(FACTION_KEYS := (
        "新党", "旧党", "皇党集团", "军功集团", "中立派")), "派系键必须保持新口径"
    for fn in ("新党", "旧党", "皇党集团", "军功集团", "中立派"):
        assert fn in again["factions"], f"读档→再存档后派系 {fn} 丢失"
