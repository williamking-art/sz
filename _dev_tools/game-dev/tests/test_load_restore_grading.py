# -*- coding: utf-8 -*-
"""M25 · 读档恢复失败分级（2026-10-07 用户裁定）。

失败按**范围**分级，而不是一律 fail-fast：

| 层级 | 处理 |
|---|---|
| 整档结构 / 必需状态损坏、恢复服务自身失败 | **fail-fast**：读档失败，**不返回部分恢复的 state** |
| **单条**动态蓝图内容校验失败 | 只丢弃该条并留痕，其余合法蓝图继续恢复 |
| 子段 schema 高于支持版本 | 只拒绝该子段并留痕，整档继续 |

🔴 **内容校验失败 ≠ 恢复服务故障** —— 前者可能只错一条，整档丢弃会连带废掉
玩家所有合法蓝图；后者继续下去只会得到一个残缺档案。
"""
import json
import sys

import pytest

from application.load_game import RestoreServiceError, load_game, restore_dynamic_blueprints
from core.commands import new_game
from core.save_load import _slot_path, save_game


def _legal_blueprint(name="海塘"):
    """合法样本必须**走真实校验器**，不手写 —— 否则测的是我自己的假样本。"""
    from core.blueprint_dynamic import validate_dynamic_blueprint

    bp = {
        "name": name, "category": "民生",
        "cost": {"silver": 120_000, "months": 2},
        "effects": [{"op": "仓容", "params": {"amount": 50_000}}],
    }
    clean, errs = validate_dynamic_blueprint(bp)
    assert not errs, f"合法样本意外不合法：{errs}"
    return clean


def _evil_blueprint(name="dyn:evil"):
    return {
        "schema_version": 1, "name": name, "category": "民生",
        "cost": {"silver": 1, "months": 1}, "materials": {}, "maintenance": 0.005,
        "effects": [{"op": "凭空造银", "params": {"amount": 1}}], "_dynamic": True,
    }


# ====================================================== 整档级：fail-fast
def test_restore_service_failure_aborts_and_returns_no_state(monkeypatch):
    """**恢复服务自身失败** ⇒ 抛错且**不返回部分恢复的 state**。"""
    import core.blueprint_dynamic as bd

    def _boom(*_a, **_k):
        raise RuntimeError("故意失败：模拟蓝图域服务不可用")

    monkeypatch.setattr(bd, "register_dynamic_blueprint", _boom)
    s = new_game("史实")

    with pytest.raises(RestoreServiceError) as ei:
        restore_dynamic_blueprints(s, {"dynamic_blueprints": {"dyn:x": _legal_blueprint()}}, 1)
    err = ei.value
    assert err.slot == 1, "必须带槽位，便于定位"
    assert err.stage, "必须带失败阶段"
    assert isinstance(err.__cause__, RuntimeError), "cause 应为原始异常（保留堆栈）"


def test_schema_version_table_failure_is_service_error(monkeypatch):
    """版本表取不到 = **服务故障**（非内容问题）⇒ 整档 fail-fast。"""
    import core.save_load as sl

    def _boom():
        raise RuntimeError("故意失败：版本表不可得")

    monkeypatch.setattr(sl, "_plan_schema_versions", _boom)
    s = new_game("史实")

    with pytest.raises(RestoreServiceError):
        restore_dynamic_blueprints(s, {"dynamic_blueprints": {}}, 7)


# ====================================================== 单条级：丢弃并留痕
def test_single_bad_blueprint_dropped_others_restored(caplog):
    """**一条**坏蓝图只丢它自己，**合法蓝图必须继续恢复**。"""
    s = new_game("史实")
    data = {"dynamic_blueprints": {
        "dyn:evil": _evil_blueprint(),
        "dyn:ok1": _legal_blueprint("dyn:ok1"),
        "dyn:ok2": _legal_blueprint("dyn:ok2"),
    }}

    with caplog.at_level("WARNING", logger="save_load"):
        n = restore_dynamic_blueprints(s, data, 1)

    assert "dyn:evil" not in (s.dynamic_blueprints or {}), "坏蓝图必须丢弃"
    assert n == 2, f"两条合法蓝图应恢复，实得 {n}"
    assert any("dyn:evil" in r.getMessage() for r in caplog.records), "丢弃必须留痕（含键名）"


def test_tampered_blueprint_does_not_fail_whole_load():
    """**读档调用层面**：单条坏蓝图不得让整档读不出来（规格任务 3）。"""
    s = new_game("史实")
    s.dynamic_blueprints["dyn:evil"] = _evil_blueprint()
    assert save_game(s, 92) is True

    s2 = load_game(92)

    assert s2 is not None, "单条坏蓝图**不得**导致整档失败"
    assert "dyn:evil" not in (s2.dynamic_blueprints or {})


# ====================================================== 子段级：只拒绝该段
def test_higher_schema_section_refused_but_save_loads():
    """超版本子段只拒绝该段，**整档继续**（规格任务 7）。"""
    s = new_game("史实")
    s.dynamic_blueprints["dyn:ok"] = _legal_blueprint()
    assert save_game(s, 93) is True
    p = _slot_path(93)
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    raw["plan_schemas"] = {"dynamic_blueprint": 99}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)

    s2 = load_game(93)

    assert s2 is not None, "拒绝子段不应导致整档拒绝"
    assert not s2.dynamic_blueprints, "超版本子段应被拒绝"


def test_current_format_roundtrip_keeps_blueprints():
    """当前格式往返**必须保留合法蓝图**（不许因分级而丢）。"""
    from core.blueprint_dynamic import blueprint_key

    s = new_game("史实")
    bp = _legal_blueprint()
    s.dynamic_blueprints[blueprint_key(bp)] = bp
    assert save_game(s, 94) is True

    s2 = load_game(94)

    assert s2 is not None
    assert len(s2.dynamic_blueprints or {}) == 1, "合法蓝图往返必须保留"
    assert bp["name"] in {v.get("name") for v in s2.dynamic_blueprints.values()}


# ====================================================== 版本常量：不得静默回落
def test_schema_version_import_failure_is_logged_not_silent(caplog, monkeypatch):
    """版本常量导入失败 → **记 error + 回落值为 0**，**不得静默回落到 1**。

    原实现回落到 1，会让**本程序写的档被自己当成旧 schema 读回**，
    超版本门（高于支持版本则拒载该段）形同虚设。回落 0 < 任何真实版本，使门保持生效。
    """
    import importlib
    import sys
    import core.save_load as sl

    for name in ("core.blueprint_dynamic", "core.decree_plan", "core.plan_commit"):
        monkeypatch.setitem(sys.modules, name, None)
    importlib.reload(sl)

    with caplog.at_level("ERROR", logger="save_load"):
        v = sl._plan_schema_versions()

    assert v == {"decree_plan": 0, "dynamic_blueprint": 0, "plan_action": 0}, v
    assert any(r.levelname == "ERROR" for r in caplog.records), "必须记 error（静默回落禁止）"
    assert any(r.exc_info for r in caplog.records), "error 必须带堆栈，事后可定位"

    importlib.reload(sl)


def test_real_schema_versions_are_positive():
    """实际常量必须为**正整数**（否则超版本门会误拒合法档）。"""
    from core.save_load import _plan_schema_versions

    v = _plan_schema_versions()
    assert v, "版本表不应为空"
    for k, ver in v.items():
        assert isinstance(ver, int) and ver > 0, f"{k} 版本非正整数：{ver!r}"
