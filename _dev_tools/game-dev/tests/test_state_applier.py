# -*- coding: utf-8 -*-
"""engine/state_applier 合并逻辑与验证层测试。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from engine.state_applier import (
    validate_changes, merge_changes, apply_to_state,
    applier_pipeline, CHANGE_LOG, validate_conservation, apply_conservation_fix,
)


def _s():
    return GameState("史实")


def test_merge_add_accumulate():
    """同一 path 多个 add → 累加。"""
    merged = merge_changes([
        ("finance", [{"path": "treasury", "op": "add", "value": 500000, "reason": "市舶税"}]),
        ("military", [{"path": "treasury", "op": "add", "value": -200000, "reason": "军费"}]),
    ])
    treasury = [m for m in merged if m["path"] == "treasury"][0]
    assert treasury["op"] == "add" and treasury["value"] == 300000
    assert treasury["source_agent"] == "merge"


def test_merge_set_then_add():
    """同一 path 有 set 又有 add → 先 set 再 add。"""
    merged = merge_changes([
        ("finance", [{"path": "prefectures.两浙路.mood", "op": "set", "value": 60, "reason": "设基准"}]),
        ("relief", [{"path": "prefectures.两浙路.mood", "op": "add", "value": 10, "reason": "赈济"}]),
    ])
    mood = [m for m in merged if m["path"] == "prefectures.两浙路.mood"]
    assert mood[0]["op"] == "set" and mood[0]["value"] == 60   # 先 set
    assert mood[1]["op"] == "add" and mood[1]["value"] == 10   # 后 add


def test_validate_rejects_illegal():
    """验证层：非法 path / 缺 reason / 负数拒绝。"""
    valid, errors = validate_changes([
        {"path": "god_mode", "op": "set", "value": 1, "reason": "x"},      # 非法 path
        {"path": "treasury", "op": "set", "value": 100, "reason": ""},    # 缺 reason
        {"path": "treasury", "op": "set", "value": -1, "reason": "负"},   # 负数
        {"path": "treasury", "op": "mul", "value": "big", "reason": "x"}, # 类型错
    ])
    assert len(valid) == 0
    assert len(errors) == 4


def test_validate_clamp01():
    """T2：wealth/satisfaction/influence 非 0-1 比率（clamp 01 已清空——守恒边界修复）。"""
    valid, _ = validate_changes([
        {"path": "factions.新党.satisfaction", "op": "set", "value": 5, "reason": "低满意度"},
    ])
    assert valid[0]["value"] == 5   # satisfaction 0-100，不再 clamp 到 [0,1]


# 2026-09-18 整理（决策 1）：原 `test_cascade_faction_power` 已**删除**。
# 它测的是 `factions.*.power` 的 cascade 规则，而该规则已正式废弃：
#   ① `factions.*.power` 不在 VALID_PATHS 白名单（`validate_changes` 会先拒绝该路径）；
#   ② `FactionState` 本身没有 `power` 字段（只有 influence/satisfaction/cohesion）。
# 即该规则**永不触发**，用例却仍断言它存在 —— 属过期测试。
# 白纸化决策记录见 `engine/state_applier.py:286-292`。


def test_pipeline_apply_log():
    """完整管道：写库 + 变更日志（path/old/new/reason/source_agent）。"""
    s = _s()
    t0 = s.treasury
    before = len(CHANGE_LOG)
    r = applier_pipeline(s, [
        ("finance", [
            {"path": "treasury", "op": "add", "value": 100000, "reason": "商税"},
            {"path": "prefectures.两浙路.pops.商人.wealth", "op": "add",
             "value": -100000, "reason": "商税征"},
        ]),
        ("military", [
            {"path": "treasury", "op": "add", "value": -40000, "reason": "军饷"},
            {"path": "prefectures.两浙路.pops.官僚.wealth", "op": "add",
             "value": 40000, "reason": "俸给划转"},
        ]),
    ])
    assert s.treasury - t0 == 60000          # 100000 - 40000（合并后）
    assert len(r["applied"]) == 3            # treasury + 商人 + 官僚（成对守恒，无补记账）
    new_logs = CHANGE_LOG[before:]
    treasury_recs = [r for r in new_logs if r["path"] == "treasury"]
    assert treasury_recs
    rec = treasury_recs[0]
    assert rec["path"] == "treasury"
    assert rec["new"] == rec["old"] + 60000
    assert rec["reason"] and rec["source_agent"] == "merge"


def test_pipeline_rejected_collected():
    """非法 changes → rejected 收集返回（供 AI 重试），合法照常执行。"""
    s = _s()
    t0 = s.treasury
    r = applier_pipeline(s, [
        ("finance", [
            {"path": "treasury", "op": "add", "value": 50000, "reason": "税入"},
            {"path": "prefectures.两浙路.pops.商人.wealth", "op": "add",
             "value": -50000, "reason": "税征"},
            {"path": "bad_path", "op": "set", "value": 1, "reason": "非法"},
        ]),
    ])
    assert s.treasury - t0 == 50000          # 合法成对执行
    assert len(r["rejected"]) == 1           # 非法收集


def test_conservation_reject_single_sided():
    """守恒：单边钱变更（无来源）→ 拒绝。"""
    ok, errs = validate_conservation([
        {"path": "treasury", "op": "add", "value": 100000, "reason": "凭空"},
    ])
    assert not ok
    assert any("money" in e for e in errs)


def test_conservation_reason_fix():
    """守恒：reason 驱动补记账（抄没 → 士绅 wealth 补来源）。"""
    fixes = apply_conservation_fix([
        {"path": "treasury", "op": "add", "value": 100000, "reason": "抄没蔡京家产"},
    ])
    assert fixes and fixes[0]["path"] == "prefectures.*.pops.士绅.wealth"
    assert fixes[0]["value"] == -100000
    ok, _ = validate_conservation([
        {"path": "treasury", "op": "add", "value": 100000, "reason": "抄没"},
        fixes[0],
    ])
    assert ok


def test_conservation_pair_pass():
    """守恒：成对转移（来源=去向）→ 通过。"""
    ok, errs = validate_conservation([
        {"path": "treasury", "op": "add", "value": 100000, "reason": "税"},
        {"path": "prefectures.两浙路.pops.商人.wealth", "op": "add",
         "value": -100000, "reason": "税征"},
    ])
    assert ok and not errs


def test_conservation_exempt_state():
    """守恒：状态字段（mood）豁免。"""
    ok, _ = validate_conservation([
        {"path": "prefectures.两浙路.mood", "op": "set", "value": 70, "reason": "赈济"},
    ])
    assert ok


# ---------------- T2 补测试（蔡权衡复核守恒边界） ----------------
def test_t2_wildcard_expand():
    """T2 P0：`*` 通配在写入前展开为每路一条（不死路径）。"""
    from engine.state_applier import _expand_wildcards
    s = _s()
    out = _expand_wildcards(s, [
        {"path": "prefectures.*.pops.士绅.wealth", "op": "add", "value": -100,
         "reason": "抄没", "source_agent": "cascade"},
    ])
    assert len(out) == len(s.prefectures)
    assert all("*" not in c["path"] for c in out)
    assert any("河北路" in c["path"] for c in out)


def test_t2_set_mul_remove_rejected():
    """T2：守恒路径禁止 set/mul/remove（须 add 成对变更）。"""
    ok, errs = validate_conservation([
        {"path": "treasury", "op": "set", "value": 100, "reason": "设基准"},
    ])
    assert not ok and any("禁止 set" in e for e in errs)
    ok2, errs2 = validate_conservation([
        {"path": "prefectures.两浙路.pops.农.wealth", "op": "mul", "value": 1.1, "reason": "倍"},
    ])
    assert not ok2 and any("禁止 mul" in e for e in errs2)
    ok3, _ = validate_conservation([
        {"path": "prefectures.两浙路.mood", "op": "set", "value": 70, "reason": "豁免"}])
    assert ok3   # 豁免字段 set 允许


def test_t2_bureaucrat_soldier_in_money_group():
    """T2：官僚/兵 入 MONEY_PATHS（俸禄接收方）。"""
    from engine.state_applier import _group_of
    assert _group_of("prefectures.两浙路.pops.官僚.wealth") == "money"
    assert _group_of("prefectures.两浙路.pops.兵.wealth") == "money"
    ok, errs = validate_conservation([
        {"path": "treasury", "op": "add", "value": -40000, "reason": "俸给"},
        {"path": "prefectures.两浙路.pops.兵.wealth", "op": "add",
         "value": 40000, "reason": "俸给划转"},
    ])
    assert ok and not errs


def test_t2_reason_fix_extension():
    """T2：CASCADE_REASON_FIX 扩展（役钱→农、田赋→农/士绅、俸禄→官僚、酒课→工匠）。"""
    from engine.state_applier import apply_conservation_fix
    fixes = apply_conservation_fix([
        {"path": "treasury", "op": "add", "value": 100000, "reason": "役钱"},
        {"path": "treasury", "op": "add", "value": 50000, "reason": "田赋"},
        {"path": "treasury", "op": "add", "value": -30000, "reason": "俸禄"},
        {"path": "treasury", "op": "add", "value": 20000, "reason": "酒课"},
    ])
    paths = [f["path"] for f in fixes]
    assert any("农.wealth" in p for p in paths)      # 役钱 → 农
    assert any("农.wealth" in p for p in paths)      # 田赋 → 农
    assert any("官僚.wealth" in p for p in paths)    # 俸禄 → 官僚
    assert any("工匠.wealth" in p for p in paths)    # 酒课 → 工匠


def test_t2_hard_reject_conservation():
    """T2：补记账后仍不闭合 → 硬拒绝（不落地 + rejected + conservation_failed）。"""
    s = _s()
    t0 = s.treasury
    r = applier_pipeline(s, [
        ("finance", [
            {"path": "treasury", "op": "add", "value": 100000, "reason": "凭空钱"},
        ]),
    ])
    assert s.treasury == t0           # 不落地
    assert r.get("conservation_failed") is True
    assert any("守恒失败" in e or "禁止" in e for e in r["rejected"])


def test_t2_seize_field_grain_group():
    """T2：抄没田 → 官田加（grain 组补记账）。"""
    from engine.state_applier import apply_conservation_fix, validate_conservation
    fixes = apply_conservation_fix([
        {"path": "prefectures.两浙路.grain", "op": "add", "value": -1000, "reason": "抄没田"},
    ])
    assert any("storage" in f["path"] for f in fixes)
    ok, _ = validate_conservation([
        {"path": "prefectures.两浙路.grain", "op": "add", "value": -1000, "reason": "抄没田"},
        fixes[0],
    ])
    assert ok


def test_underflow_reject_no_mint():
    """审查 P0-6：非负守恒路径 add 穿底 → 整单硬拒绝，clamp 截断不再净造币。"""
    s = _s()
    s.treasury = 50
    r = applier_pipeline(s, [
        ("a", [
            {"path": "treasury", "op": "add", "value": -100, "reason": "军饷划转"},
            {"path": "prefectures.京畿路.pops.兵.wealth", "op": "add",
             "value": 100, "reason": "军饷入账"},
        ]),
    ])
    assert r.get("conservation_failed") is True
    assert s.treasury == 50          # 未截断造币
    # 足额成对仍正常落地
    s2 = _s()
    t0 = s2.treasury
    r2 = applier_pipeline(s2, [
        ("b", [
            {"path": "treasury", "op": "add", "value": -100000, "reason": "军饷划转"},
            {"path": "prefectures.京畿路.pops.兵.wealth", "op": "add",
             "value": 100000, "reason": "军饷入账"},
        ]),
    ])
    assert not r2.get("conservation_failed")
    assert s2.treasury == t0 - 100000


if __name__ == "__main__":
    import inspect
    for name, obj in sorted(globals().items()):
        if name.startswith("test_") and inspect.isfunction(obj):
            obj()
            print(f"PASS {name}")
    print("全部通过")
