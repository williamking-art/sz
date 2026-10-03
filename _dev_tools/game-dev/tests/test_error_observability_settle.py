# -*- coding: utf-8 -*-
"""结算 / 存档关键路径错误可观测性回归（审查任务书 **P2-3**）。

覆盖必修项（逐条对应任务书的"验收断言"）：

  M3  帝国支出部分分发后全额退款 = 造币 + 日志谎报（`settlement_imperial` / `settlement_common`）
  M6  预检异常被伪装成"资财不足"（`free_effect`）
  M7  整步结算被静默跳过（`settlement._settle_legacies/_settle_focus`、`settlement_econ`）
  M8  货币台账登记五处静默失败（`settlement` / `settlement_econ*` / `settlement_finance` /
      `settlement_granary`）
  M9  读档迁移静默失败（`save_load` 四处 ＋ 三处 warning 缺 slot/异常类型）
  M13 玩家发明节点读档后消失 ＋ `get_save_slots` 遇非对象顶层 500（反向缺口）
  M14 在研究进度被静默丢弃（`settlement_tech`）
  M15 银行信心缺失回落"完美"（`settlement_finance`）
  M2  自动存档失败静默（`commands.finish_turn`）
  应修 结算快照/回滚跳过字段不可查（`commands`）、局势快照失败被当作"条件未命中"
      （`situation_settle`）

原则（任务书总原则）：**预期可恢复错误必须留下足以定位问题的上下文，且不得把
数据写入失败 / 状态不一致 / 资源缺失伪装成成功**。故断言分两类：
  ① 故障路径 → 玩家可见结算 WARN ＋ 开发者日志（`caplog`，异常带 traceback）；
  ② 正常路径 → **不得出现这些 WARN**（防噪声）。
"""
import json
import logging
import os
import random
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.commands import finish_turn, new_game  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.save_load import _slot_path, get_save_slots, load_game, save_game  # noqa: E402


# =====================================================================
# 工具
# =====================================================================
def _boom(*_a, **_kw):
    raise RuntimeError("注入故障：boom")


def _state():
    """新局状态（不跑结算）：POP wealth / 国库均为真实初值。"""
    return GameState("史实")


def _pop_wealth(s, cls):
    return sum(int((p.get("pops") or {}).get(cls, {}).get("wealth", 0) or 0)
               for p in s.prefectures.values())


def _all_pop_wealth(s):
    return sum(int(pop.get("wealth", 0) or 0)
               for p in s.prefectures.values() for pop in (p.get("pops") or {}).values()
               if isinstance(pop, dict))


def _warns(log):
    return [x for x in log if "[WARN]" in x]


def _recs(caplog, name):
    return [r for r in caplog.records if r.name == name]


# =====================================================================
# M3 · 帝国支出：退款额必须用**实际已分发额**，日志必须写**实扣额**
# =====================================================================
def test_m3_imperial_partial_distribution_refunds_only_actual(monkeypatch, caplog):
    """分发中途抛错 → `Δtreasury + ΣΔPOP_wealth == 0`，且日志金额 == 实扣额。

    用假 `_distribute_cash` **先入账 1000 贯再抛错**模拟"部分已写"（原实现的真实
    故障形态）：若按 `paid - 0` 全额退款，则国库不减而民间多 1000（ΣΔ>0 = 造币）。
    """
    import core.settlement_imperial as si

    s = _state()
    random.seed(7)                       # 风险事件掷点确定化（本用例只测收支守恒）
    log = []
    t0, w0 = int(s.treasury), _all_pop_wealth(s)
    _route = sorted(s.prefectures)[0]
    _target = s.prefectures[_route]["pops"]["工匠"]

    def _fake_dist(state, amount, shares, applied=None):
        _target["wealth"] = int(_target["wealth"]) + 1000      # 已入账 1000
        if applied is not None:
            applied.append(1000)                              # 如实上报"实际已分发"
        raise RuntimeError("mid-way boom")                    # 中途抛错

    monkeypatch.setattr(si, "_distribute_cash", _fake_dist)
    act = {"location": "宫里", "mode": "公开", "action": "崇道修醮"}   # base_cost 50000
    with caplog.at_level(logging.WARNING, logger="settlement"):
        si._apply_imperial_action(s, act, log)

    t1, w1 = int(s.treasury), _all_pop_wealth(s)
    assert (t1 - t0) + (w1 - w0) == 0, \
        f"守恒断言失败：Δtreasury={t1 - t0} ΣΔPOP_wealth={w1 - w0}（ΣΔ 必须为 0）"
    assert t1 - t0 == -1000, "实扣额必须等于实际已分发额（1000），不是请求额 50000"

    _lines = [x for x in log if x.startswith("[皇帝] 宫里·公开·崇道修醮：")]
    assert _lines, f"皇帝支出行缺失：{log}"
    assert "国库支 1,000 贯" in _lines[0], f"日志金额必须 == 实扣额：{_lines[0]}"
    assert _warns(log), "分发异常必须落结算 WARN 行（玩家可见）"
    assert any(r.exc_info for r in _recs(caplog, "settlement")), \
        "分发异常必须有 logging traceback（开发者可定位）"


def test_m3_imperial_non_dict_pop_slot_stays_conserved(monkeypatch, caplog):
    """任务书口径：某路 `pops["工匠"]` 为非 dict → 不得造成 ΣΔ≠0，且日志如实。"""
    import core.settlement_imperial as si

    s = _state()
    random.seed(7)
    _route = sorted(s.prefectures)[0]
    s.prefectures[_route]["pops"]["工匠"] = "不是 dict"       # 坏槽（分发侧须安全跳过）
    log = []
    t0, w0 = int(s.treasury), _all_pop_wealth(s)
    act = {"location": "宫里", "mode": "公开", "action": "崇道修醮"}
    with caplog.at_level(logging.WARNING, logger="settlement"):
        si._apply_imperial_action(s, act, log)               # 不得抛错
    t1, w1 = int(s.treasury), _all_pop_wealth(s)
    assert (t1 - t0) + (w1 - w0) == 0, \
        f"坏 POP 槽不得破坏守恒：Δtreasury={t1 - t0} ΣΔPOP_wealth={w1 - w0}"


def test_m3_distribute_cash_is_atomic_no_partial_write():
    """`_distribute_cash` 两阶段：数值解析失败 → **零写入**（不再有"半截入账"窗口）。"""
    from core.settlement_common import _distribute_cash

    s = _state()
    roads = sorted(s.prefectures)
    # 让**后写入**的 商人 池带非法 wealth（老实现会先把 工匠 写完再炸）
    s.prefectures[roads[-1]]["pops"]["商人"]["wealth"] = "不是数字"
    before = {r: s.prefectures[r]["pops"]["工匠"]["wealth"] for r in roads}
    _m_before = {r: s.prefectures[r]["pops"]["商人"]["wealth"] for r in roads}
    with pytest.raises(ValueError):
        _distribute_cash(s, 10000, {"工匠": 0.4, "商人": 0.6})
    after = {r: s.prefectures[r]["pops"]["工匠"]["wealth"] for r in roads}
    _m_after = {r: s.prefectures[r]["pops"]["商人"]["wealth"] for r in roads}
    assert before == after, "分发失败必须零写入（否则国库全退而民间多钱 = 造币）"
    assert _m_before == _m_after, "商人池（含坏值槽）也必须零写入"


def test_m3_distribute_cash_success_is_conserved_and_reports_applied():
    from core.settlement_common import _distribute_cash

    s = _state()
    w0 = _pop_wealth(s, "工匠") + _pop_wealth(s, "商人")
    applied = []
    got = _distribute_cash(s, 10000, {"工匠": 0.4, "商人": 0.6}, applied=applied)
    w1 = _pop_wealth(s, "工匠") + _pop_wealth(s, "商人")
    assert got == 10000, "成功路径 Σ入账 == amount（尾差吃在末位）"
    assert sum(applied) == got, "`applied` 上报额必须等于返回值"
    assert w1 - w0 == 10000, "民间入账额必须等于返回的分发额"


# =====================================================================
# M6 · 预检异常 ≠ 资财不足
# =====================================================================
def test_m6_precheck_exception_is_not_reported_as_insufficient(caplog):
    from core.free_effect import _settle_free_effects

    s = _state()
    _route = sorted(s.prefectures)[0]
    s.prefectures[_route]["pops"]["商人"]["wealth"] = "坏值"     # → 预检 int() 抛错
    item = {"name": "试制新器", "mode": "ongoing", "duration": 3,
            "effects": {"treasury": 100}, "cost": {}, "executor": None}
    s.longterm_effects = [item]
    log = []
    with caplog.at_level(logging.WARNING, logger="free_effect"):
        _settle_free_effects(s, log)

    assert any("预检异常" in x for x in log), f"文案必须含「预检异常」：{log}"
    assert not any("资财不足" in x for x in log), \
        f"预检异常不得报成「资财不足」（把排查引向错误方向）：{log}"
    assert item.get("last_error"), "异常情形必须在条目上记 last_error（可诊断）"
    assert item["duration"] == 3, "暂缓月不得递减 duration"
    assert any(r.exc_info for r in _recs(caplog, "free_effect"))


def test_m6_genuinely_insufficient_still_says_insufficient():
    """反向：真的是资财不足时，文案仍是「资财不足」（不得被新哨兵语义吃掉）。"""
    from core.free_effect import _settle_free_effects

    s = _state()
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                pop["wealth"] = 0
    item = {"name": "试制新器", "mode": "ongoing", "duration": 3,
            "effects": {"treasury": 100}, "cost": {}, "executor": None}
    s.longterm_effects = [item]
    log = []
    _settle_free_effects(s, log)
    assert any("资财不足" in x for x in log), f"合法不足路径文案被改坏：{log}"
    assert not item.get("last_error"), "资财不足不是异常，不应留 last_error"


# =====================================================================
# M7 · 整步结算被静默跳过
# =====================================================================
@pytest.mark.parametrize("mod,fn,tag,call", [
    ("core.legacy_mechanic", "settle_legacies", "[帝国修正][WARN]", "legacies"),
    ("core.focus_mechanic", "settle_focus", "[国策][WARN]", "focus"),
])
def test_m7_whole_step_failure_is_visible(monkeypatch, caplog, mod, fn, tag, call):
    import importlib
    import core.settlement as settlement

    _m = importlib.import_module(mod)
    monkeypatch.setattr(_m, fn, _boom)
    s = _state()
    log = []
    with caplog.at_level(logging.WARNING, logger="settlement"):
        getattr(settlement, "_settle_" + call)(s, log)
    assert any(tag in x for x in log), f"整步跳过必须落结算 WARN（{tag}）：{log}"
    assert [r for r in _recs(caplog, "settlement") if r.exc_info], \
        "必须有 logging.exception（含 traceback）"


def test_m7_estate_and_investment_steps_are_visible(monkeypatch, caplog):
    import core.estate_mechanic as em
    import core.settlement_econ as se

    monkeypatch.setattr(em, "settle_minister_estate", _boom)
    monkeypatch.setattr(em, "settle_investments", _boom)
    s = _state()
    log = []
    with caplog.at_level(logging.WARNING, logger="settlement"):
        se._settle_extensions(s, log)          # 真实结算步（含家产/投资/时代联动）
    assert any("[家产][WARN]" in x for x in log), f"{log}"
    assert any("[投资][WARN]" in x for x in log), f"{log}"
    assert [r for r in _recs(caplog, "settlement") if r.exc_info]


def test_m7_normal_path_has_no_warn_noise(caplog):
    """正常路径**不得**出现任何 `[WARN]` 结算行，也不得有无谓 traceback（防噪声）。"""
    import core.settlement as settlement
    import core.settlement_econ as se

    s = _state()
    log = []
    with caplog.at_level(logging.WARNING, logger="settlement"):
        settlement._settle_legacies(s, log)
        settlement._settle_focus(s, log)
        settlement._settle_org_economy(s, log)
        se._settle_extensions(s, log)
    assert not _warns(log), f"正常路径出现 WARN 噪声：{_warns(log)}"
    assert not [r for r in _recs(caplog, "settlement") if r.exc_info], \
        "正常路径不得产生带 traceback 的日志"


# =====================================================================
# M8 · 货币台账登记失败必须可见（不得伪装成"对账残差/造币 bug"）
# =====================================================================
def test_m8_org_burn_flow_register_failure_is_visible(monkeypatch, caplog):
    import core.money as money
    from core.settlement import _settle_org_economy

    monkeypatch.setattr(money, "register_flow", _boom)
    s = _state()
    log = []
    with caplog.at_level(logging.WARNING, logger="settlement"):
        _settle_org_economy(s, log)            # 机构运营支出的 burn 登记
    assert s.money_audit.get("flow_errors"), "必须累计到 money_audit['flow_errors']"
    assert [r for r in _recs(caplog, "settlement") if "货币台账" in r.getMessage()], \
        "必须有一条 [货币台账] WARNING"
    assert [r for r in _recs(caplog, "settlement") if r.exc_info]


def test_m8_mint_flow_register_failure_is_visible(monkeypatch, caplog):
    import core.money as money
    from core.settlement_econ_helpers import _settle_mint

    monkeypatch.setattr(money, "register_flow", _boom)
    s = _state()
    s.price_level = 1.0
    s.coin["melted_pool"] = 100_000
    log = []
    with caplog.at_level(logging.WARNING, logger="settlement"):
        ok, _msg = _settle_mint(s, log, 10_000)
    assert ok, "台账登记失败不得改变铸钱本身的结果"
    assert s.money_audit.get("flow_errors")
    assert _warns(log), f"铸钱台账登记失败必须有玩家可见 WARN：{log}"


def test_m8_register_money_flow_helper_contract():
    """helper 自身契约：成功 → True 且不写 flow_errors；失败 → False + 记账。"""
    from core.settlement_common import register_money_flow

    s = _state()
    assert register_money_flow(s, "burn", 100, "自检") is True
    assert not s.money_audit.get("flow_errors")
    assert register_money_flow(s, "不存在的 kind", 100, "自检") is False   # register_flow 抛 ValueError
    assert s.money_audit["flow_errors"], "失败必须累计"
    assert s.money_audit["flow_errors"][0]["kind"] == "不存在的 kind"


# =====================================================================
# M9 / M13 · 读档迁移失败可见、发明节点不静默消失、槽位列表不 500
# =====================================================================
@pytest.mark.parametrize("target,attr,marker", [
    ("core.estate_mechanic", "sync_estate_slices", "sync_estate_slices"),
    ("core.settlement_imperial", "ensure_hidden_in_pops", "ensure_hidden_in_pops"),
    ("core.pop_structure", "ensure_farm_slices", "ensure_farm_slices"),
])
def test_m9_migration_failure_warns_with_slot_and_still_returns_state(
        monkeypatch, caplog, target, attr, marker):
    import importlib

    slot = 331
    s = new_game("史实")
    assert save_game(s, slot) is True
    _m = importlib.import_module(target)
    monkeypatch.setattr(_m, attr, _boom)

    with caplog.at_level(logging.WARNING, logger="save_load"):
        loaded = load_game(slot)
    assert loaded is not None, "迁移失败**不得拒档**（仍返回 state）"
    _hit = [r for r in _recs(caplog, "save_load")
            if marker in r.getMessage() and str(slot) in r.getMessage()]
    assert _hit, f"迁移失败必须 WARNING（含迁移名与 slot）：{[r.getMessage() for r in _recs(caplog, 'save_load')]}"
    assert any(r.exc_info for r in _hit), "迁移失败 warning 必须带 exc_info（可定位）"


def test_m13_generated_node_reregistration_failure_marks_failed_nodes(monkeypatch, caplog):
    """发明节点重注册失败 → 记 `tech["failed_nodes"]`（供 UI 标注）且**仍返回 state**。"""
    import core.asset_context as ac

    slot = 332
    s = new_game("史实")
    s.tech.setdefault("generated_nodes", {})["gid_test_1"] = {
        "node": tuple(str(i) for i in range(10)), "name": "测试发明"}
    assert save_game(s, slot) is True
    monkeypatch.setattr(ac, "_register_generated_node_global", _boom)

    with caplog.at_level(logging.WARNING, logger="save_load"):
        loaded = load_game(slot)
    assert loaded is not None, "节点重注册失败不得拒档"
    assert "gid_test_1" in (loaded.tech.get("failed_nodes") or []), \
        f"失败 gid 必须落 tech.failed_nodes：{loaded.tech.get('failed_nodes')}"
    assert [r for r in _recs(caplog, "save_load")
            if "生成科技节点重注册" in r.getMessage() and str(slot) in r.getMessage()]


def test_m13_get_save_slots_non_object_top_level_is_corrupt_not_500():
    """槽文件内容是数组/字符串 → 该槽标 corrupt，**不抛**（原 AttributeError 穿透 → 500）。"""
    slot = 5
    os.makedirs(os.path.dirname(_slot_path(slot)), exist_ok=True)
    with open(_slot_path(slot), "w", encoding="utf-8") as f:
        json.dump([], f)                       # 顶层是数组

    slots = get_save_slots()                    # 不得抛
    entry = [x for x in slots if x["slot"] == slot]
    assert entry, "坏槽不得从列表里消失"
    assert entry[0].get("corrupt") is True, f"坏槽必须标 corrupt：{entry[0]}"
    assert entry[0].get("time") == "存档损坏"


def test_m13_get_save_slots_string_top_level_is_corrupt():
    slot = 4
    os.makedirs(os.path.dirname(_slot_path(slot)), exist_ok=True)
    with open(_slot_path(slot), "w", encoding="utf-8") as f:
        json.dump("顶层是字符串", f, ensure_ascii=False)
    slots = get_save_slots()
    assert [x for x in slots if x["slot"] == slot][0].get("corrupt") is True


def test_m9_literacy_split_finance_warnings_carry_slot_and_type(monkeypatch, caplog):
    """识字率 / 立场占比 / 金融字段迁移的 warning 必须带 `slot=` 与异常类型。"""
    import core.faction_split as fs
    import core.literacy as lit

    slot = 333
    s = new_game("史实")
    assert save_game(s, slot) is True
    monkeypatch.setattr(lit, "init_literacy", _boom)
    monkeypatch.setattr(fs, "ensure_faction_split", _boom)
    monkeypatch.setattr(GameState, "ensure_finance_fields", _boom, raising=True)

    with caplog.at_level(logging.WARNING, logger="save_load"):
        assert load_game(slot) is not None
    _msgs = [r.getMessage() for r in _recs(caplog, "save_load") if r.exc_info]
    assert any("识字率" in m and f"slot={slot}" in m and "RuntimeError" in m for m in _msgs), _msgs
    assert any("立场占比" in m and f"slot={slot}" in m and "RuntimeError" in m for m in _msgs), _msgs
    assert any("金融字段" in m and f"slot={slot}" in m and "RuntimeError" in m for m in _msgs), _msgs


def test_m9_situations_load_failure_warns_with_slot(monkeypatch, caplog):
    """`situations` 载入异常 → warning 必须含 slot（原缺 slot，多槽排查时分不清哪一档）。"""
    slot = 334
    s = new_game("史实")
    assert save_game(s, slot) is True
    import core.save_load as sl
    monkeypatch.setattr(sl, "_load_situations", _boom)

    with caplog.at_level(logging.WARNING, logger="save_load"):
        loaded = load_game(slot)
    assert loaded is not None and loaded.situations == []
    assert any("situations" in r.getMessage() and f"slot={slot}" in r.getMessage()
               for r in _recs(caplog, "save_load"))


# =====================================================================
# M14 · 在研究进度不得被静默丢弃
# =====================================================================
def test_m14_research_lookup_exception_keeps_entry(monkeypatch, caplog):
    import core.registries as registries
    from core.settlement_tech import _settle_tech_research

    s = _state()
    _node_id = "不存在的攻关节点XYZ"
    s.tech["researching"] = {_node_id: {"progress": 42.0, "monthly_cost": 0,
                                       "months": 12, "masters": 1}}
    monkeypatch.setattr(registries, "node_entry", _boom)
    log = []
    with caplog.at_level(logging.WARNING, logger="settlement"):
        _settle_tech_research(s, log)

    assert _node_id in s.tech["researching"], \
        "查表**异常** ≠ 节点不存在：进度/经费/人才时间不得被丢"
    assert s.tech["researching"][_node_id]["progress"] == 42.0, "进度必须保留"
    assert any("查表失败" in x for x in log), f"必须落结算 WARN：{log}"
    assert [r for r in _recs(caplog, "settlement") if r.exc_info]


def test_m14_truly_unregistered_node_is_still_cleaned():
    """反向：节点**确实**不存在（无异常）→ 仍按原口径清理（不得因新分支漏清）。"""
    from core.settlement_tech import _settle_tech_research

    s = _state()
    _node_id = "彻底不存在的节点QQQ"
    s.tech["researching"] = {_node_id: {"progress": 1.0, "monthly_cost": 0, "months": 3}}
    log = []
    _settle_tech_research(s, log)
    assert _node_id not in s.tech["researching"]
    assert not _warns(log), f"正常清理不得产生 WARN：{log}"


# =====================================================================
# M15 · 银行信心缺失不得回落"完美"
# =====================================================================
def test_m15_bank_trust_unreadable_keeps_previous_overdue(monkeypatch, caplog):
    import core.money as money
    from core.settlement_finance import _settle_bank_credit

    s = _state()
    s.bank["established"] = True
    s.bank["overdue_rate"] = 0.123456
    monkeypatch.setattr(money, "jiaozi_run_pressure", _boom)
    log = []
    with caplog.at_level(logging.WARNING, logger="settlement"):
        _settle_bank_credit(s, log)

    assert abs(float(s.bank["overdue_rate"]) - 0.123456) < 1e-9, \
        "读数不可判定 → 沿用上月 overdue_rate（**不得**回落 1.0 伪造'无压力'）"
    assert [r for r in _recs(caplog, "settlement") if r.exc_info], "必须 WARNING + traceback"
    assert _warns(log), f"玩家侧也应有可见说明：{log}"


def test_m15_normal_path_still_updates_overdue():
    """反向：读数正常时口径**不变**（仍按公式更新，不因修复而冻结）。"""
    from core.settlement_finance import _settle_bank_credit

    s = _state()
    s.bank["established"] = True
    s.bank["overdue_rate"] = 0.0
    log = []
    _settle_bank_credit(s, log)
    assert float(s.bank["overdue_rate"]) > 0.0, "正常路径仍应按公式演化"


# =====================================================================
# M2 · 自动存档失败不得静默
# =====================================================================
def test_m2_autosave_exception_sets_save_error(monkeypatch, caplog):
    import core.save_load as sl

    monkeypatch.setattr(sl, "save_game", _boom)
    s = _state()
    s.month = 1                                # 触发自动存档分支
    with caplog.at_level(logging.ERROR, logger="finish_turn"):
        finish_turn(s)                         # 不得抛
    assert s.save_error, "失败必须置 state.save_error（供 UI 一次性提示）"
    assert [r for r in caplog.records
            if r.levelno >= logging.ERROR and "自动存档失败" in r.getMessage()], \
        f"必须有 ERROR：{[(r.name, r.getMessage()) for r in caplog.records]}"


def test_m2_autosave_returning_false_also_reports(monkeypatch, caplog):
    import core.save_load as sl

    monkeypatch.setattr(sl, "save_game", lambda *_a, **_k: False)
    s = _state()
    s.month = 1
    with caplog.at_level(logging.ERROR, logger="finish_turn"):
        finish_turn(s)
    assert s.save_error, "save_game 返回 False 同样是失败，必须记 error 并置 save_error"
    assert [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_m2_normal_autosave_clears_save_error():
    s = _state()
    s.month = 1
    s.save_error = "上一回合的陈旧错误"
    finish_turn(s)                             # 真实落盘（SAVE_DIR 由 conftest 重定向到 tmp）
    assert s.save_error == "", "成功一次后必须清掉陈旧提示"


# =====================================================================
# 应修 · 快照/回滚被跳过的字段可查；回滚失败必须 ERROR 且计数
# =====================================================================
def test_snapshot_records_skipped_fields():
    import threading

    from core.commands import _snapshot_state

    s = _state()
    s._obs_lock_probe = threading.Lock()      # 锁不可深拷贝（模拟连接/锁类字段）
    snap = _snapshot_state(s)
    assert isinstance(snap.get("__skipped__"), list)
    assert "__mem_turn__" in snap
    assert "_obs_lock_probe" in snap["__skipped__"], \
        f"被跳过的字段名必须可查（原实现 continue 后无任何痕迹）：{snap['__skipped__']}"


def test_restore_state_failure_is_counted_and_logged(caplog):
    from core.commands import _restore_state

    class _Boom:
        """赋值即抛错的属性描述符宿主（模拟 setattr 失败）。"""
        def __set__(self, obj, value):
            raise RuntimeError("setattr boom")

    s = _state()
    snap = {"treasury": 1, "__mem_turn__": None, "__skipped__": ["memory"]}
    setattr(GameState, "_obs_boom_attr", _Boom())   # 类级描述符（不改实例字典）
    snap["_obs_boom_attr"] = 123
    try:
        with caplog.at_level(logging.ERROR, logger="commands"):
            _restore_state(s, snap)
        assert s.treasury == 1, "可还原字段必须还原"
        _errs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("_obs_boom_attr" in r.getMessage() for r in _errs), \
            f"回滚失败必须 ERROR（原实现静默 continue）：{[r.getMessage() for r in _errs]}"
        assert any("不完整" in r.getMessage() for r in _errs), "必须统计失败字段数"
    finally:
        delattr(GameState, "_obs_boom_attr")


# =====================================================================
# 应修 · 局势：指标快照失败 → 跳过该条终态判定（不得当作"条件未命中"）
# =====================================================================
def _situation_state():
    from core.legacy_mechanic import init_legacies
    from core.situations import make_record

    s = GameState("史实")
    init_legacies(s)
    rec = make_record("陕西流寇起", "shaanxi_bandits", s.turn - 1,
                      resolve_condition={"metric": "region.unrest", "arg": "陕西路",
                                         "op": ">=", "value": 85},
                      fail_condition={"metric": "region.unrest", "arg": "陕西路",
                                      "op": ">=", "value": 85},
                      ongoing_cost=None, effect_on_resolve={"prestige": 3})
    rec["bar_value"] = 10
    s.situations = [rec]
    return s, rec


def test_situation_snapshot_failure_skips_terminal_judgment(monkeypatch, caplog):
    import core.situation_metrics as sm
    from core.situation_settle import settle_situations

    s, rec = _situation_state()
    monkeypatch.setattr(sm, "build_metric_snapshot", _boom)
    logs = []
    with caplog.at_level(logging.WARNING, logger="situation_settle"):
        out = settle_situations(s, logs, 0)

    assert rec["status"] == "active", "快照失败不得判终态（既非 resolved 也非 failed）"
    assert out["resolved"] == 0 and out["failed"] == 0
    assert any("跳过终态判定" in e for e in out["errors"]), \
        f"错误必须落 out['errors']：{out['errors']}"
    assert any("跳过终态判定" in x for x in logs), f"玩家可见日志：{logs}"
    assert any("取快照失败" in r.getMessage() for r in _recs(caplog, "situation_settle"))


def test_situation_snapshot_errors_surface_in_out_errors(caplog):
    """`build_metric_snapshot` 的逐项 errors 不得再被静默丢弃。"""
    from core.situation_settle import settle_situations
    from core.situations import make_record

    s = GameState("史实")
    rec = make_record("坏指标局势", "bad_metric", s.turn - 1,
                      resolve_condition={"metric": "region.unrest", "arg": "陕西路",
                                         "op": ">=", "value": 1},
                      ongoing_cost=None)
    # 模拟"能通过校验但事后坏掉"的条目：条件指向未注册 metric（安全网须记 error 而非静默）
    rec["resolve_condition"] = {"metric": "not.registered.metric", "op": ">", "value": 1}
    s.situations = [rec]
    logs = []
    with caplog.at_level(logging.WARNING, logger="situation_settle"):
        out = settle_situations(s, logs, 0)
    assert any("未注册" in e for e in out["errors"]), \
        f"快照逐项错误必须落 out['errors']（原实现丢弃 _errs）：{out['errors']}"


def test_situation_journal_unavailable_is_warned(monkeypatch, caplog):
    """`_journal_since` 台账不可读 → warning（原静默 return []，intent 全判 fail 而无人知）。"""
    from core.situation_settle import _journal_since

    import builtins
    _real_import = builtins.__import__

    def _bad_import(name, *a, **kw):
        if name == "engine.state_applier":
            raise ImportError("注入故障")
        return _real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _bad_import)
    with caplog.at_level(logging.WARNING, logger="situation_settle"):
        assert _journal_since(0) == []
    assert any("台账不可读" in r.getMessage() for r in _recs(caplog, "situation_settle"))
    assert any(r.exc_info for r in _recs(caplog, "situation_settle"))


def test_situation_reset_failure_is_warned(monkeypatch, caplog):
    """本回合档位/intent 瞬态未清空（下月会重复消费）→ warning + out['errors']。"""
    from core.situation_settle import settle_situations

    s, _rec = _situation_state()

    # 用类级属性描述符让 `state._situation_grades = {}` 抛错
    # （类属性须 setattr：`type(s).__dict__` 是 mappingproxy，不支持 setdefault）
    class _Boom:
        def __set__(self, obj, value):
            raise RuntimeError("setattr boom")

    setattr(GameState, "_situation_grades", _Boom())
    try:
        with caplog.at_level(logging.WARNING, logger="situation_settle"):
            out = settle_situations(s, [], 0)
        assert any("未清空" in e for e in out["errors"]), out["errors"]
        assert any("未清空" in r.getMessage() for r in _recs(caplog, "situation_settle"))
    finally:
        delattr(GameState, "_situation_grades")


# =====================================================================
# transfer_public_funds_to_pops：通道不可用 ≠ "拨了 0"
# =====================================================================
def test_transfer_channel_unavailable_is_distinguishable(monkeypatch):
    import builtins
    from core.settlement_common import MoneyChannelUnavailable, transfer_public_funds_to_pops

    s = _state()
    _real_import = builtins.__import__

    def _bad_import(name, *a, **kw):
        if name == "engine.state_applier":
            raise ImportError("注入故障")
        return _real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _bad_import)
    with pytest.raises(MoneyChannelUnavailable):
        transfer_public_funds_to_pops(s, 1000, {"工匠": 1.0}, "测试",
                                      raise_on_unavailable=True)
    # 非严格模式（范围外调用方）：保持旧语义 0，但**留 WARNING**
    assert transfer_public_funds_to_pops(s, 1000, {"工匠": 1.0}, "测试") == 0


# =====================================================================
# 结算侧公共留痕设施自身契约（去重 = 防噪声）
# =====================================================================
def test_note_settlement_error_dedups_per_turn(caplog):
    from core.settlement_common import note_settlement_error

    s = _state()
    s.turn = 5
    log = []
    with caplog.at_level(logging.WARNING, logger="settlement"):
        assert note_settlement_error(s, "k1", "测试", "第一次", log=log) is True
        assert note_settlement_error(s, "k1", "测试", "第二次（同回合同 key）", log=log) is False
        assert note_settlement_error(s, "k2", "测试", "另一条", log=log) is True
    assert len(_warns(log)) == 2, f"每回合每 key 最多一条：{log}"
    s.turn = 6
    assert note_settlement_error(s, "k1", "测试", "下回合可再记", log=log) is True
    assert len(_warns(log)) == 3
