# -*- coding: utf-8 -*-
"""P3 发现系统（V1.3 终稿 §7）：保真度三档 / 勾校案卷 / 勾校诏令 / 四级阶梯 / 迁移。

保真度输入＝执行者 corruption × 目标路 clerks_detail.grip × spy_network × 是否密查（C3 初值）。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

from core.audit_case import (audit_fidelity, case_is_evidenced,
                             discovery_readout, resolve_audit)
from core.commands import new_game
from core.monthly_gazette import build_monthly_gazette
from content.data import FIN_AUDIT_SECRET_BONUS


def _route(s):
    return next(iter(s.prefectures))


def _set_grip(s, route, v):
    p = s.prefectures[route]
    d = p.get("clerks_detail")
    if not isinstance(d, dict):
        d = {}
        p["clerks_detail"] = d
    d["grip"] = v


# ---------------- 保真度三档 ----------------

def test_fidelity_three_tiers_by_inputs():
    s = new_game()
    r = _route(s)
    _set_grip(s, r, 0.10)
    fin = audit_fidelity(s, r, executor="陈瓘")          # 清廉（0.12）
    assert fin["outcome"] == "查得实情"
    fin2 = audit_fidelity(s, r, executor="蔡京")         # 贪墨（0.78）
    assert fin2["fidelity"] < fin["fidelity"]
    assert fin2["outcome"] == "查无实据"
    _set_grip(s, r, 0.60)                                # 高把持路 + 贪墨执行者
    assert audit_fidelity(s, r, executor="蔡京")["outcome"] == "反噬"


def test_fidelity_secret_bonus_and_missing_input_marked():
    s = new_game()
    r = _route(s)
    _set_grip(s, r, 0.30)
    a = audit_fidelity(s, r, executor="陈瓘", secret=False)
    b = audit_fidelity(s, r, executor="陈瓘", secret=True)
    assert abs((b["fidelity"] - a["fidelity"]) - FIN_AUDIT_SECRET_BONUS) < 1e-9
    c = audit_fidelity(s, r, executor="查无此人")         # 名册查无 → 缺失标注
    assert c["inputs"]["executor_corruption"] is None


# ---------------- 案卷 ----------------

def test_resolve_audit_writes_case_and_backfire():
    s = new_game()
    r = _route(s)
    _set_grip(s, r, 0.10)
    log = []
    res = resolve_audit(s, r, executor="陈瓘", log=log)
    assert res["ok"] and res["case"]["status"] == "证据在握"
    assert res["case"]["evidence"]["kind"] == "账目异常"
    assert case_is_evidenced(s, res["case"]["id"])
    assert any("[勾校]" in x for x in log)
    # 反噬：贪墨 + 高把持 → 皇威不升
    _set_grip(s, r, 0.60)
    p0 = s.prestige
    res2 = resolve_audit(s, r, executor="蔡京")
    assert res2["case"]["status"] == "反噬"
    assert s.prestige <= p0
    # 坏路名 → 拒绝（不伪造）
    assert resolve_audit(s, "不存在路", executor="陈瓘")["ok"] is False


def test_audit_decree_effect_wires_case_before_numeric_filter():
    """勾校诏令：载荷为路名/字典（非数值），必须**先于数值过滤**被处理。"""
    from core.settlement_decree import _apply_decree_effect
    s = new_game()
    r = _route(s)
    _set_grip(s, r, 0.10)
    log = []
    _apply_decree_effect(
        s, {"title": "勾校", "effects": {"audit_route": {"route": r, "executor": "陈瓘"}}}, log)
    assert any(c.get("status") == "证据在握" for c in s.audit_cases.values())
    _apply_decree_effect(s, {"title": "勾校", "effects": {"audit_route": r}}, log)   # 简写
    assert len(s.audit_cases) == 2


# ---------------- 四级阶梯 ----------------

def test_discovery_ladder_levels():
    s = new_game()
    assert discovery_readout(s)["level"] == 0            # 开局无异常
    s.statistics["land_tax_assessed"] = 100_000
    s.statistics["tax_loss_report"] = {"运输损耗": 0, "地方耗费": 0,
                                       "火耗": 9_000, "杂费": 0, "total": 9_000}
    assert discovery_readout(s)["level"] == 1            # 一级：财政异常
    s.discovery_suspicions = [{"minister": "陈瓘", "text": "钱粮与民情不符"}]
    assert discovery_readout(s)["level"] == 2            # 二级：AI 大臣怀疑
    r = _route(s)
    s.audit_cases["ac0-1"] = {"id": "ac0-1", "route": r, "status": "证据在握",
                              "created_turn": 0, "judgement": None}
    assert discovery_readout(s)["level"] == 3            # 三级：成案
    s.audit_cases["ac0-1"]["judgement"] = "查实侵渔"
    assert discovery_readout(s)["level"] == 4            # 四级：定案


# ---------------- 月报风闻（三级"证据"） ----------------

def test_gazette_surfaces_evidence_case_as_wind():
    s = new_game()
    r = _route(s)
    _set_grip(s, r, 0.10)
    resolve_audit(s, r, executor="陈瓘")
    g = build_monthly_gazette(s, year=1102, month=5)
    fin = next(c for c in g["chapters"] if c["title"] == "度支录")
    text = "\n".join(fin["lines"])
    assert "御史风闻" in text and r in text


# ---------------- 存档与缺省 ----------------

def test_audit_cases_roundtrip_and_defaults():
    from core.save_load import load_game, save_game
    s = new_game()
    r = _route(s)
    _set_grip(s, r, 0.10)
    resolve_audit(s, r, executor="陈瓘")
    assert save_game(s, 9) is True
    s2 = load_game(9)
    assert s2 is not None
    assert any(c.get("status") == "证据在握" for c in s2.audit_cases.values())
    assert new_game().audit_cases == {}                  # 缺省不臆造
