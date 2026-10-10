# -*- coding: utf-8 -*-
"""P2 账面系统（V1.3 终稿 §5）：`tax_loss_report` 落账、面板读数、度支录章与信息差闸门。

验收对应：§12 断言 7（账面/真账对核）＋ 账面自洽 ＋ 月报叙事钩子可触发。
"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

from core.commands import new_game
from core.monthly_gazette import CHAPTER_ORDER, build_monthly_gazette
from core.settlement_finance import _settle_finance
from content.data import FIN_LOSS_NORM


def _set_loss(s, total, assessed=100_000):
    s.statistics["land_tax_assessed"] = assessed
    s.statistics["tax_loss_report"] = {"运输损耗": int(total * 0.25),
                                       "地方耗费": int(total * 0.10),
                                       "火耗": 0, "杂费": int(total * 0.05),
                                       "total": total}
    rep = s.statistics["tax_loss_report"]
    rep["火耗"] = total - rep["运输损耗"] - rep["地方耗费"] - rep["杂费"]


# ---------------- 账面落账（账面 = 侵渔包装；四类目和 ≡ total） ----------------

def test_book_loss_matches_diverted_and_categories_sum():
    s = new_game()
    _settle_finance(s, [])
    rep = s.statistics["tax_loss_report"]
    # 断言 7 的操作形态：账面损耗 == 真账侵渔（逐月对核）
    assert rep["total"] == s.statistics["land_tax_diverted"]
    assert (rep["运输损耗"] + rep["地方耗费"] + rep["火耗"] + rep["杂费"]) == rep["total"]
    # 掩护拆分单调（火耗最大，尾差归此）
    assert rep["火耗"] >= rep["运输损耗"] >= rep["地方耗费"] >= rep["杂费"]


def test_book_loss_accumulates_monthly():
    s = new_game()
    _settle_finance(s, [])
    t1 = s.statistics["tax_loss_report"]["total"]
    d1 = s.statistics["land_tax_diverted"]
    _settle_finance(s, [])
    assert s.statistics["tax_loss_report"]["total"] == t1 + (
        s.statistics["land_tax_diverted"] - d1)


# ---------------- 面板读数（finance_readout） ----------------

def test_finance_readout_exposes_land_tax_and_loss():
    s = new_game()
    _settle_finance(s, [])
    ro = s.finance_readout()
    assert ro["land_tax"]["diverted"] == s.statistics["land_tax_diverted"]
    assert ro["land_tax"]["assessed"] == s.statistics["land_tax_assessed"]
    assert ro["tax_loss"]["total"] == s.statistics["tax_loss_report"]["total"]
    assert ro["tax_loss"]["status"] in ("正常", "耗损偏重", "耗损异常")


# ---------------- 信息差三级（一/二级；三级留 P3） ----------------

def test_loss_status_gate_by_oversight():
    s = new_game()
    # 耗率 9% ≥ 常例×1.5（3%）→ 超常
    _set_loss(s, 9_000)
    s.oversight = 0.10
    assert s.tax_loss_readout()["status"] == "耗损偏重"       # 监察不足：只报偏重
    s.oversight = 0.90
    assert s.tax_loss_readout()["status"] == "耗损异常"       # 监察能力高：升至异常
    # 耗率 1% < 3% → 正常
    _set_loss(s, 1_000)
    assert s.tax_loss_readout()["status"] == "正常"
    # 无损耗 → 正常
    _set_loss(s, 0)
    assert s.tax_loss_readout()["status"] == "正常"


# ---------------- 度支录章（月报钩子） ----------------

def test_gazette_finance_chapter_present_and_self_consistent():
    s = new_game()
    _settle_finance(s, [])
    g = build_monthly_gazette(s, year=1102, month=5)
    assert "度支录" in CHAPTER_ORDER
    fin = next(c for c in g["chapters"] if c["title"] == "度支录")
    text = "\n".join(fin["lines"])
    assert "田赋折色" in text and "耗损" in text
    # 账面自洽：账目行同时给出应征与三路去向（上供/留州/耗损）
    assert "上供" in text and "留州" in text
    assert isinstance(g.get("finance_raw"), dict) and g["finance_raw"]


def test_gazette_loss_hook_triggers_by_oversight():
    s = new_game()
    _set_loss(s, 7_000)          # 耗率 7% ≥ 3% → 超常
    s.oversight = 0.90
    g = build_monthly_gazette(s, year=1102, month=5)
    fin = next(c for c in g["chapters"] if c["title"] == "度支录")
    text = "\n".join(fin["lines"])
    assert "耗损异常" in text and "御史台" in text

    s2 = new_game()
    _set_loss(s2, 7_000)
    s2.oversight = 0.10
    g2 = build_monthly_gazette(s2, year=1102, month=5)
    fin2 = next(c for c in g2["chapters"] if c["title"] == "度支录")
    text2 = "\n".join(fin2["lines"])
    assert "偏重" in text2 and "异常" not in text2


def test_gazette_finance_uses_month_delta():
    """第二月账目行取**增量**（与上月 finance_raw 比对），不重复累计。"""
    from core.settlement import run_monthly_settlement
    s = new_game()
    run_monthly_settlement(s, seed_offset=2)
    run_monthly_settlement(s, seed_offset=2)
    g2 = s.monthly_gazette[-1]
    assert isinstance(g2.get("finance_raw"), dict)
    prev = s.monthly_gazette[-2].get("finance_raw") if len(s.monthly_gazette) >= 2 else None
    if prev:
        d_assessed = g2["finance_raw"]["assessed"] - prev["assessed"]
        fin = next(c for c in g2["chapters"] if c["title"] == "度支录")
        text = "\n".join(fin["lines"])
        if d_assessed > 0:
            assert f"{d_assessed:,}" in text
