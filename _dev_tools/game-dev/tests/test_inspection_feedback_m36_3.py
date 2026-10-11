# -*- coding: utf-8 -*-
"""M36-3《反馈观察层》契约回归（**记录政治后果，不判断监察结果**）。

裁决（2026-10-11）：采用**方案①（暴露/戒备，复用 grip／文书修饰／P3-4）＋适量方案②（风闻，同量纲观察量）**，
**不采用方案③**（无成功率／查出概率／阻力数值，**不**固定加时、**不**降成功率）。

写入口径：**只写** `state.inspection_feedback`（累计观察量）；对 `grip`／`rumor_tier`／P3-4 backlash
**只读引用**；**不得**影响 money／tax／grain／POP／occupation／官员属性／案卷。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import (INSPECTION_FEEDBACK_CAUTION_PUBLIC,  # noqa: E402
                          INSPECTION_FEEDBACK_CAUTION_SECRET,
                          INSPECTION_FEEDBACK_KEYS, INSPECTION_FEEDBACK_LOG_CAP)
from core import money  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.inspection import (ensure_inspection_feedback_schema, enqueue_inspection,  # noqa: E402
                             file_inspection_report, inspection_feedback_readout,
                             inspection_tick)
from core.settlement import run_monthly_settlement  # noqa: E402


def _seed(s, route, n=4):
    pool = s.prefectures[route]["pops"]["官僚"]
    move = min(int(n), int(pool.get("on_post", 0) or 0))
    pool["on_post"] = int(pool.get("on_post", 0) or 0) - move
    pool["waiting"] = int(pool.get("waiting", 0) or 0) + move


def _route_with_pool(s, n=4):
    from core.domains.administration import officialdom as _od
    route = next(iter(s.prefectures))
    _seed(s, route, n)
    ok, bad = _od.check_invariants(s)
    assert ok, f"夹具不得破坏官员不变量：{bad}"
    return route


def _obs(s):
    return dict(inspection_feedback_readout(s)["observables"])


def _run_to_expire(s, kind="查粮", secret=False):
    """受理→出发→推进至超期；返回 task id。"""
    tid = enqueue_inspection(s, _route_with_pool(s), kind, secret=secret)["task"]["id"]
    s.year, s.month = 990, 3
    for m in range(3, 12):
        s.month = m
        inspection_tick(s)
        if s.inspection_tasks[0]["status"] == "expired":
            break
    return tid


# ---------------------------------------------------------------- 容器 / 幂等

def test_feedback_container_defaults_and_idempotent():
    """新局反馈容器默认空；`ensure_..._schema` 幂等（可对脏档自愈）。"""
    s = new_game()
    ensure_inspection_feedback_schema(s)
    fb = inspection_feedback_readout(s)
    assert fb["interpretation"] == "record-only", "本层明确不做成败判定"
    assert set(fb["observables"]) == set(INSPECTION_FEEDBACK_KEYS)
    assert fb["observables"] == {k: 0.0 for k in INSPECTION_FEEDBACK_KEYS}
    assert fb["events"] == 0 and fb["recent"] == []
    s.inspection_feedback = None
    ensure_inspection_feedback_schema(s)
    assert isinstance(s.inspection_feedback, dict) and s.inspection_feedback["events"] == 0


def test_dispatch_feedback_public_vs_secret():
    """① 出发：明查＝戒备↑（地方知中央关注）；密查＝**短期戒备较低**；二者均不产生暴露。"""
    a, b = new_game(), new_game()
    enqueue_inspection(a, _route_with_pool(a), "查粮")
    enqueue_inspection(b, _route_with_pool(b), "查粮", secret=True)
    for s in (a, b):
        s.year, s.month = 990, 3
        inspection_tick(s)
    oa, ob = _obs(a), _obs(b)
    assert oa["local_caution"] == INSPECTION_FEEDBACK_CAUTION_PUBLIC
    assert ob["local_caution"] == INSPECTION_FEEDBACK_CAUTION_SECRET
    assert ob["local_caution"] < oa["local_caution"], "密查短期戒备应低于明查"
    for o in (oa, ob):
        assert o["exposure"] == 0.0, "出发本身不构成暴露（观察量）"
        assert o["rumor_change"] == 0.0, "风闻反馈不在出发时产生"
    assert a.inspection_feedback["events"] == b.inspection_feedback["events"] == 1


def test_expiry_feedback_secret_rebounds_harder():
    """①+② 超期：密查的 exposure／official_pressure／rumor_change **均高于**明查（暴露后反弹）。"""
    a, b = new_game(), new_game()
    _run_to_expire(a, secret=False)
    _run_to_expire(b, secret=True)
    assert a.inspection_tasks[0]["status"] == b.inspection_tasks[0]["status"] == "expired"
    oa, ob = _obs(a), _obs(b)
    for k in ("exposure", "official_pressure", "rumor_change"):
        assert ob[k] > oa[k], f"密查超期反弹应更明显：{k} {ob[k]} vs {oa[k]}"
    assert a.inspection_feedback["by_route"], "逐路累计须记录"
    assert inspection_feedback_readout(a)["recent"][-1]["event"] == "expired"


def test_filed_feedback_public_vs_secret_and_late():
    """② 回奏：明查风闻微升、密查走漏少；**迟回**（原 expired）额外记 exposure/pressure。"""
    a, b, c = new_game(), new_game(), new_game()
    for s, sec in ((a, False), (b, True)):              # 如期回奏（明查 / 密查）
        tid = enqueue_inspection(s, _route_with_pool(s), "查粮", secret=sec)["task"]["id"]
        s.year, s.month = 990, 3
        inspection_tick(s)                              # 出发
        assert file_inspection_report(s, tid, summary="回报")["ok"]
    oa, ob = _obs(a), _obs(b)
    assert oa["rumor_change"] > ob["rumor_change"], "明查回奏的民间/官场议论变化应更大"
    assert ob["exposure"] == 0.0, "密查如期回奏：走漏少（无暴露增量）"
    tid = _run_to_expire(c, secret=True)                # 迟回：先超期再回奏
    before = _obs(c)
    assert file_inspection_report(c, tid, summary="迟回")["ok"]
    after = _obs(c)
    assert after["exposure"] > before["exposure"], "迟回＝更可能走漏（观察量）"
    assert after["official_pressure"] > before["official_pressure"]


def test_feedback_does_not_interpret_outcome():
    """**不做成败判定**：回奏是否携带案卷引用，**不改**任何反馈量（同行为同反馈）。"""
    x, y = new_game(), new_game()
    for s, with_case in ((x, False), (y, True)):
        tid = enqueue_inspection(s, _route_with_pool(s), "查粮")["task"]["id"]
        s.year, s.month = 990, 3
        inspection_tick(s)
        if with_case:
            s.audit_cases["case-1"] = {"id": "case-1", "status": "open"}
            file_inspection_report(s, tid, summary="有案卷", case_id="case-1")
        else:
            file_inspection_report(s, tid, summary="无案卷")
    assert _obs(x) == _obs(y), "反馈量只取决于监察行为，不取决于（未解释的）结果"
    assert x.inspection_feedback["events"] == y.inspection_feedback["events"] == 2


def test_recent_log_is_bounded():
    """`recent` 有界（容器不得无界膨胀）。"""
    s = new_game()
    rk = _route_with_pool(s)
    n = INSPECTION_FEEDBACK_LOG_CAP + 6
    for i in range(n):
        tid = enqueue_inspection(s, rk, "查粮")["task"]["id"]
        s.year, s.month = 990, 1 + (i % 12)
        inspection_tick(s)
        file_inspection_report(s, tid, summary="x")
    assert len(s.inspection_feedback["recent"]) == INSPECTION_FEEDBACK_LOG_CAP
    assert s.inspection_feedback["events"] == 2 * n, "事件计数不受日志截断影响"


# ---------------------------------------------------------------- 冻结边界（零耦合）

def test_feedback_zero_coupling_and_no_auto_effects():
    """反馈层**只写自己的容器**：money／prefectures（含 grip/grievance/unrest）／statistics／案卷全不变。"""
    s = new_game()
    rk = _route_with_pool(s)
    before = {"money": money.m_all(s),
              "prefs": copy.deepcopy(s.prefectures),
              "stats": copy.deepcopy(dict(s.statistics or {})),
              "cases": copy.deepcopy(getattr(s, "audit_cases", {}) or {})}
    tid = enqueue_inspection(s, rk, "查赋", secret=True)["task"]["id"]
    s.year, s.month = 990, 3
    for m in (3, 4, 5, 6, 7, 8):
        s.month = m
        inspection_tick(s)
    file_inspection_report(s, tid, summary="回报")
    assert money.m_all(s) == before["money"], "反馈层不得改财政"
    assert s.prefectures == before["prefs"], "反馈层不得改逐路状态（含 grip/grievance/unrest）"
    assert dict(s.statistics or {}) == before["stats"]
    assert (getattr(s, "audit_cases", None) or {}) == before["cases"]
    assert s.inspection_feedback["events"] > 0, "反馈须确有记录"


def test_feedback_readout_is_readonly():
    """读数**只读**（含 context 里的 rumor_tier／grip／backlash 引用）。"""
    s = new_game()
    rk = _route_with_pool(s)
    tid = enqueue_inspection(s, rk, "查粮")["task"]["id"]
    s.year, s.month = 990, 3
    inspection_tick(s)
    before = {"fb": copy.deepcopy(s.inspection_feedback),
              "prefs": copy.deepcopy(s.prefectures),
              "money": money.m_all(s),
              "stats": copy.deepcopy(dict(s.statistics or {}))}
    for _ in range(3):
        ro = inspection_feedback_readout(s)
    assert s.inspection_feedback == before["fb"], "读数不得改容器"
    assert s.prefectures == before["prefs"]
    assert money.m_all(s) == before["money"]
    assert dict(s.statistics or {}) == before["stats"]
    assert set(ro) == {"observables", "events", "by_route", "recent",
                       "context", "interpretation", "note"}
    assert "rumor_tier" in ro["context"] and "grip_by_route" in ro["context"]
    assert tid and ro["context"]["backlash"] is not None, "P3-4 反向观察量作只读上下文复用"


def test_zero_disturbance_vs_control_game():
    """**财政隔离契约（长期保留）**：有任务局 vs 无任务局，同种子 6 期结算**逐位一致**。"""
    a, b = new_game(), new_game()
    rk = _route_with_pool(a)
    _route_with_pool(b)
    enqueue_inspection(a, rk, "查赋")
    for _ in range(6):
        a.month = b.month = 1 + (a.month % 12)
        run_monthly_settlement(a, seed_offset=0)
        run_monthly_settlement(b, seed_offset=0)
    assert money.m_all(a) == money.m_all(b)
    assert a.prefectures == b.prefectures
    assert dict(a.statistics or {}) == dict(b.statistics or {})
    assert (getattr(a, "audit_cases", None) or {}) == (getattr(b, "audit_cases", None) or {})
    assert a.inspection_feedback["events"] > 0, "A 局确有反馈记录（差异只在反馈容器内）"


def test_save_load_and_legacy_feedback_migration():
    """存档：反馈容器往返；**旧档缺 `inspection_feedback`** 时补默认并规范化。"""
    import json
    from core.save_load import _slot_path, load_game, save_game
    s = new_game()
    rk = _route_with_pool(s)
    tid = enqueue_inspection(s, rk, "查粮")["task"]["id"]
    s.year, s.month = 990, 3
    inspection_tick(s)
    file_inspection_report(s, tid, summary="回报")
    assert save_game(s, slot=74)
    s2 = load_game(74)
    assert s2.inspection_feedback["events"] == s.inspection_feedback["events"] == 2
    assert inspection_feedback_readout(s2)["observables"] == _obs(s)
    # 旧档（无该键）→ 补默认
    p = _slot_path(74)
    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)
    raw.pop("inspection_feedback", None)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    s3 = load_game(74)
    assert s3 is not None and s3.inspection_feedback["events"] == 0
    assert set(inspection_feedback_readout(s3)["observables"]) == set(INSPECTION_FEEDBACK_KEYS)
    if os.path.exists(p):
        os.remove(p)


def test_readout_exposed_in_finance_readout():
    """AI 读数出口：`finance_readout()["inspection_feedback"]`（与 P3-4 `inspection_backlash` 并列）。"""
    s = new_game()
    ro = s.finance_readout()
    assert "inspection_feedback" in ro and "inspection_backlash" in ro
    fb = ro["inspection_feedback"]
    assert fb["interpretation"] == "record-only"
    assert set(fb["observables"]) == set(INSPECTION_FEEDBACK_KEYS)


def _code_only(src):
    """剥掉文档串与注释，只留**可执行代码**（避免散文里的"禁止…阻力"造成假阳性）。"""
    import re
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    return "\n".join(ln.split("#")[0] for ln in src.splitlines())


def test_source_boundary_no_probability_or_penalty():
    """源码边界（**只看可执行代码**）：无成功率/概率/阻力；不 `resolve_audit`；**不写**吏治/统计/案卷。"""
    import re
    with open(os.path.join(_GAME_ROOT, "core", "inspection.py"), "r", encoding="utf-8") as f:
        src = f.read()
    code = _code_only(src)
    for banned in ("success_rate", "success_prob", "resolve_audit"):
        assert banned not in code, f"本层禁止在可执行代码中出现：{banned}"
    # 只读**引用** grip/clerks_detail 允许（作上下文）；**赋值写入**一律禁止
    for pat in (r'\["grip"\]\s*=', r'\["grievance"\]\s*=', r'\["unrest"\]\s*=',
                r'\.setdefault\("grip"', r'\["clerks_detail"\]\s*=',
                r'statistics\[[^\]]+\]\s*=', r'audit_cases\[[^\]]+\]\s*=',
                r'audit_cases\[\s*"[^"]+"\s*\]\s*='):
        assert not re.search(pat, code), f"本层不得写入该状态：{pat}"
    for forbidden in ("settlement_common", "settlement_finance", "pop_bridge",
                      "pop_structure", "money", "audit_case"):
        assert f"from core.{forbidden}" not in src and f"import {forbidden}" not in src


