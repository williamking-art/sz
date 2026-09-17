# -*- coding: utf-8 -*-
"""T14 HUD 悬浮收支栏数据测试：flow_summary 常项/一次性分类与日志解析。

覆盖：
  1) 开局 state：国库常项（tax_breakdown 三项）、内帑常项（酒课+抽成）、余额；
  2) [财政] 日志解析（月入/月支/结余/亏空）与一次性条目提取（皇帝/岁币归属）；
  3) 真实结算一次后 build_flow_summary 数据非空（月入/月支/累计）；
  4) 悬浮栏内容生成（treasury/imperial lines）结构合法（脱敏、可显示）。
"""
import os
import sys

import pytest

# game 根（测试已迁 _dev_tools/game-dev/tests；game 根 = G:\sz\game）
_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.flow_summary import build_flow_summary  # noqa: E402


def _new_state():
    return GameState("史实")


def test_opening_summary_shape():
    """开局：国库常项（tax_breakdown 三项）、内帑常项（酒课+抽成）、余额/累计字段齐全。"""
    s = _new_state()
    fs = build_flow_summary(s)
    t = fs["treasury"]
    assert {l for l, _v in t["regular_in"]} <= {"工商税", "役钱", "市舶税"}
    assert t["month_in"] >= 0 and t["month_out"] >= 0
    assert "total_in" in t and "total_out" in t
    im = fs["imperial"]
    assert any(l == "酒课" for l, _v in im["regular_in"])
    assert im["balance"] == s.imperial_treasury


def test_finance_log_parse():
    """[财政] 日志解析：月入/科目/月支/结余或亏空。"""
    s = _new_state()
    s.settlement_log.append([
        "[财政] 货币月入 1000000贯（工商税60万 役钱20万 市舶20万） 支 800000贯 结余 200000贯",
        "[田赋] 两税本色征收粮 100000石，分储诸路仓廪",
    ])
    fs = build_flow_summary(s)
    t = fs["treasury"]
    assert t["month_in"] == 1_000_000
    assert t["month_out"] == 800_000
    assert "工商税" in t["inc_parts"]


def test_one_off_extraction():
    """一次性条目提取与归属（皇帝内帑→imperial、岁币→treasury）。"""
    s = _new_state()
    s.settlement_log.append([
        "[皇帝] 京城·微服·微行市井：内帑支 20000 贯",
        "[岁币] 岁币岁赐 1000000贯，纳贡以安边",
        "[枢密] 征发军资 350000 贯",
    ])
    fs = build_flow_summary(s)
    t = fs["treasury"]
    imp = fs["imperial"]
    assert any(lab == "皇帝行止" and fund == "imperial" for lab, _v, fund in t["one_off"])
    assert any(lab == "岁币" and fund == "treasury" for lab, _v, fund in t["one_off"])
    assert any(lab == "皇帝行止" for lab, _v, _f in imp["one_off"])


def test_after_settlement_summary():
    """真实结算一次后：月入/月支/累计有值（悬浮栏有数据可显示）。"""
    from core.commands import settle_local
    s = _new_state()
    s._economy_ai = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
                     "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无"}
    settle_local(s)
    fs = build_flow_summary(s)
    t = fs["treasury"]
    assert t["month_in"] > 0 or t["month_out"] > 0, "结算后财政应有收支"
    assert t["total_in"] > 0


def test_tooltip_lines_ui():
    """悬浮收支栏（Tk 废弃后迁移）：Web TopBar 有国库/内帑明细构建器且不含隐藏字段。"""
    _fe = os.path.join(_GAME_ROOT, "..", "game", "frontend", "src",
                       "renderer", "hud", "TopBar.tsx")
    if not os.path.exists(_fe):
        return  # 前端工程不在本机（可选目录）→ 跳过
    with open(_fe, encoding="utf-8") as f:
        src = f.read()
    assert "getTreasuryDetail" in src and "getPrivyDetail" in src, \
        "TopBar 应含国库/内帑明细构建器"
    assert "loyalty" not in src.lower() and "corruption" not in src.lower(), \
        "悬浮栏不得含隐藏字段"
