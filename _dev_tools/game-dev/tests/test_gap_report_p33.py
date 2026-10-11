# -*- coding: utf-8 -*-
"""P3-3《差额报表复核》契约回归（**只读接口；不进入月报**）。

复核三类差额（口径单点复用 `audit_case.financial_evidence`）与两条恒等式；
权限遵循信息差：玩家/地方官/中央**只看账面侧**，真账差额需监察（oversight≥门限或密查）。
边界冻结：**不得**把监察字段扩散进 `settlement_common` 或 POP 层。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FIN_ANOMALY_OVERSIGHT_LINE  # noqa: E402
from core import money  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.settlement_finance import _settle_finance, _settle_local_expenditure  # noqa: E402

import pytest  # noqa: E402


def test_player_view_has_no_real_fields():
    """玩家/地方官/中央：只给账面侧（无 real 差额、无逐路真账、无恒等式结论）。"""
    s = new_game()
    for viewer in ("player", "official", "court"):
        rep = s.fiscal_gap_report(viewer)
        assert rep["allow_real"] is False
        for row in rep["by_route"].values():
            assert set(row) == {"route", "loss_report_total"}, f"{viewer} 不得见真账差额"
        assert set(rep["totals"]) == {"loss_report_total"}
        assert "note" in rep["identities"]


def test_inspector_sees_real_and_identities():
    """监察足额或密查：给真账差额与恒等式复核结论。"""
    s = new_game()
    rk = min(s.prefectures)
    s.prefectures[rk]["local_treasury"] = 0
    _settle_local_expenditure(s, [])
    _settle_finance(s, [])
    rep = s.fiscal_gap_report("inspector", oversight=FIN_ANOMALY_OVERSIGHT_LINE + 0.1)
    assert rep["allow_real"] is True
    row = rep["by_route"][rk]
    for k in ("real_diverted", "cover_overstatement", "unacknowledged_arrears",
              "local_arrears", "collection_gap"):
        assert k in row
    assert row["cover_overstatement"] == row["loss_report_total"] - row["real_diverted"]
    ident = rep["identities"]
    assert ident["three_way_identity"] is True, "三分恒等式必须成立"
    assert ident["collection_le_assessed"] is True
    # 密查亦可见
    assert s.fiscal_gap_report("inspector", oversight=0.0, secret=True)["allow_real"] is True
    # AI/系统全知
    assert s.fiscal_gap_report("ai")["allow_real"] is True


def test_report_is_readonly_and_absent_from_gazette():
    """只读：不改 money/财政状态/案卷；**不进月报**（月报条目数不变）。"""
    s = new_game()
    rk = min(s.prefectures)
    s.prefectures[rk]["local_treasury"] = 0
    _settle_local_expenditure(s, [])
    m0 = money.m_all(s)
    prefs0 = copy.deepcopy(s.prefectures)
    stats0 = copy.deepcopy(dict(s.statistics))
    cases0 = copy.deepcopy(getattr(s, "audit_cases", {}))
    gaz0 = len(getattr(s, "monthly_gazette", []) or [])
    for viewer in ("player", "official", "court", "inspector", "ai"):
        s.fiscal_gap_report(viewer)
    assert money.m_all(s) == m0, "差额报表不得改变货币总量"
    assert copy.deepcopy(s.prefectures) == prefs0, "不得改财政状态/POP/欠给"
    assert copy.deepcopy(dict(s.statistics)) == stats0, "不得写统计"
    assert copy.deepcopy(getattr(s, "audit_cases", {})) == cases0, "不得生成案卷"
    assert len(getattr(s, "monthly_gazette", []) or []) == gaz0, "差额报表不进月报"


# ---------------- P3-4 巡按反向观察量 ----------------

def test_inspection_backlash_public_vs_secret():
    """公开勾校 ⇒ 吏怨/动乱小幅上升；**密查**扰民按系数折算（更小）。"""
    from content.data import (INSPECTION_BACKLASH_GRIEVANCE,
                              INSPECTION_BACKLASH_SECRET_MULT,
                              INSPECTION_BACKLASH_UNREST)
    from core.audit_case import resolve_audit
    s = new_game()
    rk = min(s.prefectures)
    s.prefectures[rk].setdefault("clerks_detail", {})["grievance"] = 0.0
    s.prefectures[rk]["unrest"] = 0.0
    resolve_audit(s, rk, executor=None, secret=False)
    g1 = float(s.prefectures[rk]["clerks_detail"]["grievance"])
    u1 = float(s.prefectures[rk]["unrest"])
    assert abs(g1 - INSPECTION_BACKLASH_GRIEVANCE) < 1e-9
    assert abs(u1 - INSPECTION_BACKLASH_UNREST) < 1e-9
    # 密查：折算系数（更小）
    s2 = new_game()
    rk2 = min(s2.prefectures)
    s2.prefectures[rk2].setdefault("clerks_detail", {})["grievance"] = 0.0
    s2.prefectures[rk2]["unrest"] = 0.0
    resolve_audit(s2, rk2, executor=None, secret=True)
    assert float(s2.prefectures[rk2]["clerks_detail"]["grievance"]) == \
        pytest.approx(INSPECTION_BACKLASH_GRIEVANCE * INSPECTION_BACKLASH_SECRET_MULT)
    assert s2.finance_readout()["inspection_backlash"]["actions"] == 1


def test_inspection_backlash_changes_no_finance():
    """纪律：反向观察量**不改财政**——money／欠给三层／身份压力／三分财政均不变。"""
    from core.audit_case import resolve_audit
    s = new_game()
    rk = min(s.prefectures)
    s.prefectures[rk]["local_treasury"] = 0
    _settle_local_expenditure(s, [])
    m0 = money.m_all(s)
    arr0 = copy.deepcopy(s.statistics.get("local_arrears_by_identity") or {})
    press0 = copy.deepcopy(s.identity_pressures())
    tres0, local0 = int(s.treasury), int(s.prefectures[rk]["local_treasury"])
    fin0 = copy.deepcopy(s.finance)
    resolve_audit(s, rk, executor=None, secret=True)
    assert money.m_all(s) == m0, "监察不得改变货币总量"
    assert copy.deepcopy(s.statistics.get("local_arrears_by_identity") or {}) == arr0, \
        "监察不得改变欠给"
    assert copy.deepcopy(s.identity_pressures()) == press0, "监察不得改变身份压力"
    assert int(s.treasury) == tres0 and int(s.prefectures[rk]["local_treasury"]) == local0
    assert copy.deepcopy(s.finance) == fin0, "监察不得改变三分财政参数"


def test_no_inspection_fields_leak_into_frozen_layers():
    """边界冻结：监察/差额字段**不得**扩散进 `settlement_common` 或 POP 层。"""
    import io
    root = os.path.join(_GAME_ROOT, "core")
    frozen = ["settlement_common.py", "foundation/ledger/pop_bridge.py",
              "foundation/ledger/occupation.py", "foundation/ledger/pop_structure.py"]
    bad_words = ("audit_case", "fiscal_gap_report", "financial_evidence",
                 "rumor_tier", "audit_cases")
    offenders = []
    for rel in frozen:
        path = os.path.join(root, *rel.split("/"))
        if not os.path.exists(path):
            continue
        src = io.open(path, encoding="utf-8").read()
        for w in bad_words:
            if w in src:
                offenders.append(f"{rel}:{w}")
    assert not offenders, f"监察字段扩散到冻结层：{offenders}"
