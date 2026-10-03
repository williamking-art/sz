# -*- coding: utf-8 -*-
"""P1-1 回归：长期事务支持模型（事务需支持、圣旨影响支持与阻力、结果由执行过程决定）。

审查任务书验收条件（`game/游戏审查整改实施指南.md` P1-1）：
  1. 事务进展**可追溯到相关支持变化或执行结果**，不再只随时间自动完成；
  2. 对同一事务颁不同对象/内容的圣旨，在**支持、成本或推进结果**上产生可解释差异；
  3. 无支持 / 支持增加 / 支持流失 / 结案 / 旧存档读取 均有针对性回归；
  4. 前端可清楚呈现；失败、延迟或受阻时**不伪报成功**。

另按审查基准 §6 的实证缺陷模式，本文件额外锁三条"防回退"断言：
  · 缺失值不得回落成"完美"（吏治读数缺失 → 不推进 + 明写"未定义"）；
  · 不用 `or` 判空吞掉合法的 0/空；
  · POP 挂载律：事务推进**不得**动 POP 人口与钱粮（只动政治支持标量与成效度）。
"""
import os
import random
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState                                   # noqa: E402
from core import longterm_task as lt                                    # noqa: E402
from core.settlement_decree import _settle_decrees, _settle_longterm_decrees  # noqa: E402


def _state():
    return GameState("史实")


def _task(name="清丈隐田", months=18, **kw):
    t = {"task_name": name, "title": name, "months": months, "progress": 0,
         "minister": "章惇"}
    t.update(kw)
    return t


# ============================================================
# ① 旧存档兼容：幂等补齐 + 坏条目隔离
# ============================================================
def test_schema_migration_is_idempotent_and_isolates_bad_entries():
    s = _state()
    s.longterm_public = [{"task_name": "某事"}, "坏条目", {"title": "另一事"}]
    s.longterm_secret = [{"task_name": "密事"}]
    r1 = lt.normalize_tasks(s)
    assert r1["isolated"] == 1, "非 dict 条目应被隔离"
    assert r1["migrated"] == 3, "3 件正常事务应被补齐"
    assert len(s.longterm_public) == 2 and len(s.longterm_secret) == 1
    assert [t["id"] for t in s.longterm_public] == ["ltp1", "ltp2"]
    assert s.longterm_secret[0]["id"] == "lts1"
    for t in s.longterm_public + s.longterm_secret:
        for k in ("goal", "success_condition", "support_bonus", "support_log",
                  "outcome", "last_change", "decree_history"):
            assert k in t, f"旧档事务缺字段 {k}"
    # 幂等：再跑一次不得再"迁移"
    r2 = lt.normalize_tasks(s)
    assert r2["migrated"] == 0 and r2["isolated"] == 0
    # 读档路径（旧档 dict → load）不得崩
    from core.save_load import load_game  # noqa: F401  仅确认可导入（真实读档在 test_persistence_safety）


def test_legacy_task_without_progress_advances_from_zero_not_from_or_default():
    """`x or -1` 类缺陷防回退：progress 合法的 0 不得被当成"缺失"。"""
    s = _state()
    s.longterm_public = [{"task_name": "某事", "progress": 0, "months": 18}]
    log = []
    _settle_longterm_decrees(s, log)
    t = s.longterm_public[0]
    assert t["progress"] > 0, "progress 为 0（合法值）时应正常推进，不得被 or 吞成缺失"


# ============================================================
# ② 进展可追溯到执行结果与支持变化（非按时间自动完成）
# ============================================================
def test_progress_is_caused_by_execution_and_support_not_by_time():
    s = _state()
    s.longterm_public = [_task()]
    log = []
    _settle_longterm_decrees(s, log)
    t = s.longterm_public[0]
    assert 0 < t["progress"] < 100, "一个月不得自动满进度"
    assert "吏治" in t["last_change"] and "立场" in t["last_change"], \
        f"最近变化须写明因果（执行能力×立场），实得：{t['last_change']}"
    assert t["readout"]["forecast"]["advance_pct"] is not None
    assert t["readout"]["obstruction"]["defined"] is True
    assert t["readout"]["support_log"], "须留下支持/推进流水"


def test_advance_speed_follows_execution_capability(monkeypatch):
    """吏治越差（执行折扣越低）→ 同月推进越少；证明"结果由执行过程决定"。"""
    import core.decree_effect as de

    def _run(mult):
        real = de.effect_channels

        def _fake(state, **kw):
            row = real(state, **kw)
            row["effect_mult"] = mult
            row["clerks_mult"] = mult
            return row
        monkeypatch.setattr(de, "effect_channels", _fake)
        s = _state()
        s.longterm_public = [_task()]
        _settle_longterm_decrees(s, [])
        return s.longterm_public[0]["progress"]

    slow = _run(0.3)
    fast = _run(0.9)
    assert fast > slow, f"执行能力更高应推进更多（0.9→{fast} vs 0.3→{slow}）"


def test_missing_clerks_reading_does_not_fake_progress(monkeypatch):
    """缺失 ≠ 完美：吏治读数缺失（`effect_mult=None`）→ 不推进 + 明写"未定义"。"""
    import core.decree_effect as de
    real = de.effect_channels

    def _fake(state, **kw):
        row = real(state, **kw)
        row["effect_mult"] = None
        row["clerks_mult"] = None
        row["defined"] = False
        return row

    monkeypatch.setattr(de, "effect_channels", _fake)
    s = _state()
    s.longterm_public = [_task(progress=10)]
    log = []
    _settle_longterm_decrees(s, log)
    t = s.longterm_public[0]
    assert t["progress"] == 10, "读数缺失时禁止推进（不得回落 1.0 假装吏治完美）"
    assert "未定义" in t["last_change"], t["last_change"]
    assert t["readout"]["obstruction"]["defined"] is False
    assert any("未定义" in ln for ln in log)


# ============================================================
# ③ 支持方 / 阻力方来自既有声明表（不编造）
# ============================================================
def test_declared_stance_derives_supporters_and_opposers_from_pop_basis():
    s = _state()
    t = _task("方田均税·清丈隐田")
    st = lt.stance_of(s, t)
    assert st["declared"] is True and st["topic"] == "land_survey"
    opp = {o["name"] for o in st["opposers"]}
    assert "旧党" in opp, "清丈隐田使士绅受损 → 元祐旧臣与保守士绅（旧党）应为阻力方"
    assert all("声明" in o["reason"] for o in st["opposers"]), "理由须写明所依据的声明"
    # 军功集团（兵/官僚）与清丈无 POP 得失交集 → 不得被编造成支持者或阻力方
    assert "军功集团" not in opp
    assert st["net"] <= 0.0 or st["oppose_influence"] > 0


def test_military_topic_makes_military_faction_supporter():
    from content.data import REFORM_POP_BASIS
    s = _state()
    st = lt.stance_of(s, _task("整军经武·边备军器"))
    assert st["declared"] is True and st["topic"] in REFORM_POP_BASIS
    assert "整军" in st["topic_label"]
    assert "军功集团" in {x["name"] for x in st["supporters"]}
    assert st["net"] > 0


def test_undeclared_task_says_undeclared_instead_of_inventing_supporters():
    s = _state()
    st = lt.stance_of(s, _task("修缮某处无名祠庙"))
    assert st["topic"] is None
    assert st["supporters"] == [] and st["opposers"] == []
    assert "未声明立场" in st["note"]


def test_red_line_hit_marks_public_opposition_without_false_positive():
    """红线启发式取"首二字动宾头 + 末二字对象"，避免把「推行新法」误判为新党红线。"""
    _新党红线 = {"red_lines": ["废署新法", "追夺绍述之政"]}
    assert lt._redline_hit("推行新法以富国", _新党红线) is None
    assert lt._redline_hit("废署新法、尽罢绍述", _新党红线) == "废署新法"


# ============================================================
# ④ 圣旨：影响支持、有成本、不保证成功、对事务有可解释差异
# ============================================================
def _issue(s, kind, tid=None, target="章惇"):
    t = s.longterm_public[0] if s.longterm_public else None
    return lt.issue_task_decree(s, tid or (t["id"] if t else "nope"), kind, target)


def test_task_decree_goes_through_real_decree_channel_and_costs_prestige():
    s = _state()
    s.longterm_public = [_task()]
    lt.normalize_tasks(s)
    p0 = s.prestige
    msg = _issue(s, "督行")
    assert "不保其必成" in msg, msg
    assert len(s.pending_decrees) == 1, "督行诏须占诏令带宽（走既有通道，不得绕过）"
    d = s.pending_decrees[0]
    assert d["task_id"] == s.longterm_public[0]["id"]
    assert d["task_decree"]["kind"] == "督行"
    assert s.prestige < p0, "颁诏须有政治代价"
    assert s.longterm_public[0]["progress"] == 0, "颁旨本身不得直接加进度（≠ 自动成功）"


def test_decree_success_increases_support_and_records_cause(monkeypatch):
    s = _state()
    s.longterm_public = [_task()]
    lt.normalize_tasks(s)
    _issue(s, "督行")
    monkeypatch.setattr(random, "random", lambda: 0.0)     # 执行率内 → 必施行
    log = []
    _settle_decrees(s, log)
    t = s.longterm_public[0]
    assert t["support_bonus"] > 0, "已施行的圣旨应带来支持增量"
    assert t["decree_history"][-1]["executed"] is True
    assert "圣旨" in t["last_change"] and "支持" in t["last_change"]
    assert t["progress"] == 0, "圣旨只影响支持，不直接推进成效"


def test_decree_failure_gives_no_support(monkeypatch):
    """颁旨 ≠ 成功：执行受阻 → 支持增量为 0（且留痕可见）。"""
    s = _state()
    s.longterm_public = [_task()]
    lt.normalize_tasks(s)
    _issue(s, "督行")
    monkeypatch.setattr(random, "random", lambda: 0.999)   # 执行率外 → 必受阻
    log = []
    _settle_decrees(s, log)
    t = s.longterm_public[0]
    assert t["support_bonus"] == 0.0
    assert t["decree_history"][-1]["executed"] is False
    assert "支持未增" in t["decree_history"][-1]["note"]
    assert any("支持" in ln for ln in log)


def test_three_kinds_differ_in_cost_queue_and_support_multiplier(monkeypatch):
    """同一事务三种颁旨方式在**成本、通道、支持增量**上确有差异（可解释）。"""
    results = {}
    for kind in ("督行", "调兵督行", "御笔中旨"):
        s = _state()
        s.longterm_public = [_task()]
        lt.normalize_tasks(s)
        p0 = s.prestige
        msg = _issue(s, kind)
        results[kind] = {
            "cost": p0 - s.prestige,
            "queue": "secret" if s.pending_secret_decrees else "public",
            "msg": msg,
        }
        monkeypatch.setattr(random, "random", lambda: 0.0)
        _settle_decrees(s, [])
        results[kind]["support"] = s.longterm_public[0]["support_bonus"]
        results[kind]["troops"] = s.longterm_public[0]["troops_enforced_turn"] == s.turn
    assert results["督行"]["cost"] < results["御笔中旨"]["cost"], "中旨政治代价应更高"
    assert results["督行"]["queue"] == "public"
    assert results["御笔中旨"]["queue"] == "secret", "御笔中旨走密旨通道（绕会签）"
    assert results["调兵督行"]["support"] > results["督行"]["support"] > \
        results["御笔中旨"]["support"], "三种通道的支持增量应有可解释差异"
    assert results["调兵督行"]["troops"] is True, "调兵督行须让军队通道本月参与"
    assert results["督行"]["troops"] is False


def test_secret_task_rejects_troop_enforcement():
    s = _state()
    s.longterm_secret = [_task("密查某事")]
    lt.normalize_tasks(s)
    msg = lt.issue_task_decree(s, s.longterm_secret[0]["id"], "调兵督行")
    assert "密令不可调兵" in msg


def test_support_bonus_is_capped_and_decays(monkeypatch):
    s = _state()
    s.longterm_public = [_task()]
    lt.normalize_tasks(s)
    t = s.longterm_public[0]
    monkeypatch.setattr(random, "random", lambda: 0.0)
    for _ in range(6):
        _issue(s, "督行")
        _settle_decrees(s, [])
    assert t["support_bonus"] <= lt.SUPPORT_BONUS_CAP + 1e-9, "支持不得无限叠加"
    before = t["support_bonus"]
    _settle_longterm_decrees(s, [])
    assert t["support_bonus"] < before, "支持须逐月衰减（圣意需持续）"


# ============================================================
# ⑤ 结案（告成 / 罢废）与"不伪报"
# ============================================================
def test_completion_closes_task_with_log():
    s = _state()
    s.longterm_public = [_task(progress=99)]
    log = []
    _settle_longterm_decrees(s, log)
    assert s.longterm_public == [], "满成效应结案出队"
    assert any("告成" in ln for ln in log), log


def test_stall_leads_to_abort_with_reason(monkeypatch):
    """连续无实质推进 → 罢废（失败条件可解释），不得永远挂着假装在办。"""
    import core.decree_effect as de
    real = de.effect_channels

    def _zero(state, **kw):
        row = real(state, **kw)
        row["effect_mult"] = 0.0
        row["clerks_mult"] = 0.0
        return row

    monkeypatch.setattr(de, "effect_channels", _zero)
    s = _state()
    s.longterm_public = [_task()]
    log = []
    for _ in range(lt.STALL_MONTHS_FAIL):
        _settle_longterm_decrees(s, log)
    assert s.longterm_public == [], "连月无进展应罢废销案"
    assert any("罢废" in ln for ln in log), log
    assert any("原因" in ln for ln in log), "罢废须写明原因"


def test_single_bad_task_does_not_break_month_and_is_not_silently_successful(monkeypatch):
    """单件异常按件隔离：不中断整月结算，也**不伪报**推进。"""
    s = _state()
    good = _task("良事")
    bad = _task("恶事")
    s.longterm_public = [bad, good]
    lt.normalize_tasks(s)

    real = lt.monthly_advance

    def _flaky(state, task, log_list, **kw):
        if task is bad:
            raise RuntimeError("模拟内部错误")
        return real(state, task, log_list, **kw)

    monkeypatch.setattr(lt, "monthly_advance", _flaky)
    log = []
    _settle_longterm_decrees(s, log)
    assert len(s.longterm_public) == 2, "坏条目应保留待查，不得静默删档"
    assert bad["progress"] == 0 and "异常" in bad["last_change"]
    assert good["progress"] > 0, "同一月其余事务仍须正常推进"
    assert any("结算异常" in ln for ln in log)


# ============================================================
# ⑥ POP 挂载律：事务推进不得动人口/钱粮
# ============================================================
def test_advance_touches_no_pop_or_money():
    s = _state()
    s.longterm_public = [_task()]
    lt.normalize_tasks(s)

    def _snapshot():
        pops = sum(int((p.get("pops") or {}).get(c, {}).get("size", 0) or 0)
                   for p in s.prefectures.values()
                   for c in ("农", "士绅", "工匠", "商人", "官僚", "兵"))
        return pops, int(s.treasury), int(s.granary)

    before = _snapshot()
    _settle_longterm_decrees(s, [])
    assert _snapshot() == before, "事务推进只应改政治支持标量与成效度，不得动 POP 与钱粮"


# ============================================================
# ⑦ 通道验证：前端 action("issue_task_decree") → 分派表 → 单一实现
# ============================================================
def test_command_channel_dispatch_reaches_longterm_task():
    from backend.client import LocalBackend

    s = _state()
    s.longterm_public = [_task()]
    lt.normalize_tasks(s)
    tid = s.longterm_public[0]["id"]
    backend = LocalBackend()
    msg, s2 = backend.action(s, "issue_task_decree",
                             {"task_id": tid, "kind": "督行", "target": "章惇"}, None)
    assert s2 is s, "本地模式应返回同一 state 对象"
    assert "督行" in msg and len(s.pending_decrees) == 1
    assert s.pending_decrees[0]["task_id"] == tid


def test_unknown_task_or_kind_is_refused_clearly():
    s = _state()
    s.longterm_public = [_task()]
    lt.normalize_tasks(s)
    assert "无此在办事务" in lt.issue_task_decree(s, "不存在的id", "督行")
    assert "未知颁旨方式" in lt.issue_task_decree(s, s.longterm_public[0]["id"], "乱来")
    assert s.pending_decrees == [] and s.pending_secret_decrees == []


def test_decree_for_closed_task_is_reported_not_silently_dropped(monkeypatch):
    s = _state()
    s.longterm_public = [_task()]
    lt.normalize_tasks(s)
    _issue(s, "督行")
    s.longterm_public = []                     # 事务已结案
    monkeypatch.setattr(random, "random", lambda: 0.0)
    log = []
    _settle_decrees(s, log)
    assert any("已结案" in ln or "不存在" in ln for ln in log), log
