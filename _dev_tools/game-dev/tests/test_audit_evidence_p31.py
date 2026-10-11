# -*- coding: utf-8 -*-
"""P3-1《监察案卷财政证据项》契约回归。

裁决要点：**只增加** `audit_case.evidence` 的财政证据类型（local_arrears／arrears_months／
official_gap／rumor_source）；**不改变财政、不改变欠给、不改变压力、不自动生成案件**——
只让**已经存在的勾校链**能够引用这些状态。

验收：校准门逐位一致；无 money 变化；无财政状态变化；evidence **可序列化**；旧存档可读取。
另：rumor 档位 ≠ 腐败判定 ≠ 案件结论（档位只进 `rumor_source` 观察层）。
"""
import copy
import json
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import money  # noqa: E402
from core.audit_case import case_is_evidenced, financial_evidence, resolve_audit  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.settlement_finance import _settle_local_expenditure  # noqa: E402


def _drive(s, rk, times=4):
    for _ in range(times):
        s.prefectures[rk]["local_treasury"] = 0
        _settle_local_expenditure(s, [])


def _force_truth(s, rk):
    """把保真度推到"查得实情"档（降低把持、提高渗透、密查）。"""
    s.prefectures[rk].setdefault("clerks_detail", {})["grip"] = 0.0
    for k in list(getattr(s, "spy_network", {}) or {}):
        s.spy_network[k] = 1.0
    return resolve_audit(s, rk, executor=None, secret=True)


def test_observe_only_evidence_has_no_real_items():
    """未查得实情 ⇒ 只给**观察层**（rumor_source）；真账项一律不得出现。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, 3)
    ev = financial_evidence(s, rk, include_real=False)
    assert ev["available"] is True
    assert "rumor_source" in ev
    for k in ("local_arrears", "arrears_months", "official_gap"):
        assert k not in ev, "真账项只允许在'查得实情'档随卷入"
    # 档位 ≠ 判定：只给档位/标签/信号，无"腐败/查实"字样
    assert isinstance(ev["rumor_source"]["tier"], int)
    assert "腐败" not in json.dumps(ev, ensure_ascii=False)


def test_real_items_match_existing_readouts():
    """真账项必须与既有读数同源（不另算）：欠给四科目／月数／上报-真账差。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, 4)
    ev = financial_evidence(s, rk, include_real=True)
    pops = s.prefectures[rk]["pops"]
    a = ev["local_arrears"]
    assert a["official_salary"] == int(pops["官僚"]["officials_salary_arrears"])
    assert a["clerk_pay"] == int(pops["官僚"]["clerks_pay_arrears"])
    assert a["runner_pay"] == int(pops["官僚"]["runners_pay_arrears"])
    assert a["public_supply"] == (int(pops["工匠"]["欠给"]) + int(pops["商人"]["欠给"]))
    assert a["total"] == sum(v for k, v in a.items() if k != "total")
    assert ev["arrears_months"]["max"] == s.arrears_months_summary()["clerk_pay"]["max"]
    gap = ev["official_gap"]
    assert gap["loss_report_total"] == int(s.tax_loss_readout()["report"]["total"])
    assert gap["real_diverted"] == int(s.statistics.get("land_tax_diverted", 0) or 0)
    assert gap["cover_overstatement"] == gap["loss_report_total"] - gap["real_diverted"]
    assert gap["collection_gap"]["gap"] == (int(s.statistics.get("land_tax_assessed", 0) or 0)
                                            - int(s.statistics.get("land_tax_collected", 0) or 0))
    assert gap["unacknowledged_arrears"] == a["total"]


def test_evidence_builder_is_readonly():
    """证据函数**只读**：money／欠给三层／压力／案卷均不得改动。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, 3)
    m0 = money.m_all(s)
    before = copy.deepcopy(s.prefectures)
    cases0 = copy.deepcopy(getattr(s, "audit_cases", {}))
    financial_evidence(s, rk, include_real=False)
    financial_evidence(s, rk, include_real=True)
    assert money.m_all(s) == m0, "证据项不得改变货币总量"
    assert copy.deepcopy(s.prefectures) == before, "证据项不得改欠给/压力/粮"
    assert copy.deepcopy(getattr(s, "audit_cases", {})) == cases0, "证据项不得生成案件"



def test_case_evidence_carries_financial_and_serializes():
    """成案（查得实情）后：案卷 `evidence.financial` 齐备、**可 JSON 序列化**、存读一致。"""
    from core.save_load import load_game, save_game
    s = new_game()
    rk = min(s.prefectures)
    _drive(s, rk, 4)
    res = _force_truth(s, rk)
    assert res["ok"] is True and res["fidelity"]["outcome"] == "查得实情", \
        f"测试前置未达成（保真度 {res['fidelity']}）"
    case = res["case"]
    fin = (case.get("evidence") or {}).get("financial") or {}
    assert fin, "查得实情档必须携带财政证据项"
    assert set(("local_arrears", "arrears_months", "official_gap",
                "rumor_source")) <= set(fin)
    json.dumps(case, ensure_ascii=False)          # 序列化不得抛错（含中文与嵌套 dict）
    assert case_is_evidenced(s, case["id"]), "既有抄没前置判据必须仍成立"
    assert save_game(s, slot=6)
    loaded = load_game(slot=6)
    assert loaded is not None
    c2 = (loaded.audit_cases or {}).get(case["id"])
    assert c2 is not None and c2["evidence"]["financial"]["route"] == rk
    assert c2["evidence"]["financial"]["local_arrears"] == fin["local_arrears"]


def test_old_case_without_financial_evidence_still_loads():
    """旧档兼容：案卷无 `financial` 键（旧结构）仍可载入，抄没前置判据不受影响。"""
    from core.save_load import load_game, save_game
    s = new_game()
    rk = min(s.prefectures)
    s.audit_cases = {"ac0-1": {"id": "ac0-1", "route": rk, "outcome": "查得实情",
                               "fidelity": 0.9, "executor": "", "secret": False,
                               "created_turn": 0, "status": "证据在握",
                               "evidence": {"kind": "账目异常", "grip": 0.4,
                                            "note": "旧结构（无 financial）"},
                               "judgement": None}}
    assert save_game(s, slot=6)
    loaded = load_game(slot=6)
    assert loaded is not None
    c = (loaded.audit_cases or {}).get("ac0-1")
    assert c is not None and c["evidence"]["kind"] == "账目异常"
    assert "financial" not in c["evidence"]
    assert case_is_evidenced(loaded, "ac0-1")
