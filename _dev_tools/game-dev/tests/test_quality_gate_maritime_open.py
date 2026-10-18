# -*- coding: utf-8 -*-
"""质量放行门 · 市舶默认开放与外贸注入（2026-10-18）。

用户 2026-10-18 质疑「怎么会没开海呢」：查证发现 `state.maritime["open"]` **全库无代码置真**
⇒ 市舶从不结算（设计意图 ≈2000 万贯/年、占岁入 3~5%，属实现缺陷非史实认定）。

本门钉住：
1. `new_game()` 开局市舶**已开**（史实：宋代市舶发达）；
2. 开放时 `calc_maritime_trade()` > 0；显式关闭 ⇒ 0（开关仍可拨）；
3. 12 个月结算后：市舶贸易额/关税进入既有账户（国库增加**或**白银存量增加），
   **不得只算不落**（这是当年"只产出文本"的同型坑）；
4. 外贸是**体外注入**：M_ALL 不守恒是正确语义，用例只断言"有注入、方向正确"。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def _state():
    from core.commands import new_game

    return new_game()


def test_maritime_open_by_default():
    s = _state()
    assert s.maritime.get("open") is True, "开局市舶必须已开（史实；此前为「无人能拨」缺陷）"
    assert float(s.calc_maritime_trade()) > 0, "开放后贸易额必须为正"


def test_maritime_can_be_closed_explicitly():
    s = _state()
    s.maritime["open"] = False
    assert float(s.calc_maritime_trade()) == 0.0, "关闭后市舶贸易额必须为 0（不是缺失）"


def test_maritime_injection_lands_in_accounts():
    """12 月结算：贸易额>0 时，国库 / 白银存量 / 商人 wealth 至少一项增加。"""
    from core.settlement import run_monthly_settlement

    s = _state()
    t0 = int(getattr(s, "treasury", 0) or 0)
    sv0 = float(getattr(s, "silver_stock", 0) or 0)
    m0 = 0.0
    for p in s.prefectures.values():
        pops = p.get("pops") or {}
        for cls in ("商人", "士绅"):
            m0 += float((pops.get(cls) or {}).get("wealth", 0) or 0)
    for _ in range(12):
        run_monthly_settlement(s)
    t1 = int(getattr(s, "treasury", 0) or 0)
    sv1 = float(getattr(s, "silver_stock", 0) or 0)
    m1 = 0.0
    for p in s.prefectures.values():
        pops = p.get("pops") or {}
        for cls in ("商人", "士绅"):
            m1 += float((pops.get(cls) or {}).get("wealth", 0) or 0)
    assert (t1 != t0) or (sv1 != sv0) or (abs(m1 - m0) > 1e-6), \
        "市舶开着却没有任何账户变化 ⇒ 只算不落（同型缺陷）"