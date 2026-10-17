# -*- coding: utf-8 -*-
"""第十九包回归：开 `domains/administration/`（`institution`，§7 行政与官制候选第一项）。

本批钉四条不变量（前四条是结构，后三条是行为）：
 ① 桩面**逐字**等于迁移前冻结的 `dir()` 快照（23 个非 dunder 名，含 `_` 私有名与 typing 绑定名）；
 ② 每个名字都从实现模块转发且是**同一对象**，桩内不许自带实现；
 ③ 🔴 **共享的 spec 字典只有一份**：`_SPEC` / `INSTITUTION_PARAM_SPEC` / `TIER_STEP`
    经桩取与经实现取必须是同一对象（第十八包 `_TRADE_LEDGER` 的教训——桩只保住
    「名字与对象」，不保住「谁持有可变状态」）；
 ④ 🔴 **旧桩不是行为开关**：打在桩上的 patch 不影响实现（提供方 patch 必须打实现模块）；
    并常驻扫描：任何测试都不许再把 `core.institution` 当 patch 提供方；
 ⑤ 真实数据通道非空（`content.data` 14 个参数、`content.ministers.data` 的事权/机构表）
    ——断链常被 `try/except` 静默吞成空表（`_org_table` 就有这个 except）；
 ⑥ 事权约束行为不变：受约束参数无主体即拒、非掌权者拒、不受约束参数不看主体；
 ⑦ 新落点是叶子：只许 import `content.*`（不得 import `core` 业务层，也不得借私有符号）。
"""
import ast
import importlib
import io
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

BASE = os.path.dirname(_GAME_ROOT)
OLD = "core.institution"
NEW = "core.domains.administration.institution"

# 迁移前用 dir() 冻结的公开面（_scratch/b19_surface_institution.json，31 名去 8 个 dunder）
FROZEN_SURFACE = frozenset({
    "Any", "Dict", "Tuple", "INSTITUTION_PARAM_SPEC", "TIER_STEP",
    "_SPEC", "_EXECUTOR_KEYS",
    "_matter_of", "_org_table", "_authority_matters_of",
    "_executor_by_org", "_executor_by_post", "_executor_by_person",
    "all_params", "get", "clamp", "set_param", "set_by_delta",
    "resolve_executor", "check_authority", "apply_reform", "describe", "changed_count",
})

IMPL_REL = "core/domains/administration/institution.py"


def _non_dunder(mod):
    return {n for n in dir(mod) if not (n.startswith("__") and n.endswith("__"))}


def _forward_sources(mod_name):
    """桩自己 ImportFrom 语句里的 名字 → 来源模块。"""
    path = os.path.join(_GAME_ROOT, *mod_name.split(".")) + ".py"
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    home = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                home[a.name] = n.module
    return home, tree


# ── ① 公开面逐字不变 ──────────────────────────────────────────────
def test_stub_surface_equals_frozen_snapshot():
    surface = _non_dunder(importlib.import_module(OLD))
    assert surface == FROZEN_SURFACE, (
        "公开面漂移 缺=%s 多=%s" % (sorted(FROZEN_SURFACE - surface),
                                    sorted(surface - FROZEN_SURFACE)))


# ── ② 逐名转发 + 同一对象 + 桩无自带实现 ──────────────────────────
def test_every_name_forwards_to_same_object():
    home, tree = _forward_sources(OLD)
    local_impl = [getattr(x, "name", "?") for x in tree.body
                  if isinstance(x, (ast.FunctionDef, ast.ClassDef))
                  or (isinstance(x, ast.Assign)
                      and not all(getattr(t, "id", "").startswith("__")
                                  for t in x.targets))]
    assert not local_impl, f"桩内自带实现（第二份真相）：{local_impl}"
    impl = importlib.import_module(NEW)
    for name in _non_dunder(importlib.import_module(OLD)):
        assert home.get(name) == NEW, f"{OLD}.{name} 的转发来源应是 {NEW}，实际 {home.get(name)}"
        assert getattr(importlib.import_module(OLD), name) is getattr(impl, name)


# ── ③ 共享数据只有一份 ───────────────────────────────────────────
def test_spec_and_tier_tables_are_one_shared_object():
    from content.data import INSTITUTION_PARAM_SPEC
    stub, impl = importlib.import_module(OLD), importlib.import_module(NEW)
    assert stub._SPEC is impl._SPEC is INSTITUTION_PARAM_SPEC, (
        "_SPEC 出现了第二份字典：桩与实现的值域校验会各自漂移")
    assert stub.TIER_STEP is impl.TIER_STEP


# ── ④ 桩不是行为开关（常驻扫描：不许把旧桩当 patch 提供方） ────────
def test_stub_is_not_a_behavior_switch(monkeypatch):
    stub, impl = importlib.import_module(OLD), importlib.import_module(NEW)
    orig = impl.get

    def _boom(*a, **k):
        raise AssertionError("不该被调到")

    monkeypatch.setattr(stub, "get", _boom)
    try:
        assert impl.get is orig, "桩与实现已不是同一对象 ⇒ 桩被写成了第二份实现"
        assert stub.get is _boom
    finally:
        monkeypatch.undo()
    assert impl.get is orig


def _iter_py(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


def test_no_test_patches_the_old_institution_stub():
    """扫全测试目录：`monkeypatch.setattr(<绑定到 core.institution 的别名>, ...)` 一律禁止。

    别名要按**导入来源**解析（`from core import institution as inst` / `import core.institution
    as inst` 两种形态都算），按名字 grep 会得到假命中。
    """
    tests = os.path.join(BASE, "_dev_tools", "game-dev", "tests")
    offenders = []
    for path in _iter_py(tests):
        try:
            tree = ast.parse(io.open(path, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        aliases = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and (n.module or "") == "core":
                for a in n.names:
                    if a.name == "institution":
                        aliases.add(a.asname or a.name)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    if a.name == "core.institution":
                        aliases.add((a.asname or "institution"))
        if not aliases:
            continue
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") in ("setattr", "delattr")
                    and n.args and isinstance(n.args[0], ast.Name)
                    and n.args[0].id in aliases):
                offenders.append("%s:%d %s" % (
                    os.path.relpath(path, BASE).replace(os.sep, "/"), n.lineno, n.args[0].id))
    assert not offenders, (
        "旧桩被当成 patch 提供方（打在桩上不影响实现侧同名绑定）：\n" + "\n".join(offenders))


# ── ⑤ 真实数据通道非空（经新路径） ───────────────────────────────
def test_real_content_channels_are_non_empty():
    from core.game_state import GameState
    from content.data import INSTITUTION_PARAM_SPEC
    impl = importlib.import_module(NEW)
    s = GameState("史实")
    # 2026-10-17 审计校准：M324 新增 metrology_system_id 度量衡体制参数，参数表由 14 变为 15
    assert len(INSTITUTION_PARAM_SPEC) == 15, "参数表条数变了，本用例的哨兵前提需重判"
    assert len(impl.all_params(s)) == 15
    desc = impl.describe(s)
    assert len(desc) == 15 and impl.changed_count(s) == 0
    # 事权/机构表经**函数内** lazy import 取用，断链会被 except 吞成空表 → 必须实测非空
    orgs = impl._org_table(s)
    assert orgs and "户部" in orgs, f"_org_table 回退内容表拿到 {type(orgs).__name__} 空值"
    matters = impl._authority_matters_of(s, "户部")
    assert "官营放贷" in matters, f"户部事权集合缺「官营放贷」：{sorted(matters)}"


# ── ⑥ 事权约束与钳位行为不变 ─────────────────────────────────────
def test_authority_gating_unchanged():
    from core.game_state import GameState
    impl = importlib.import_module(NEW)
    s = GameState("史实")
    log = impl.apply_reform(s, {"didang_loan_rate": "中"})
    assert log and "拒绝" in log[0] and "未指定执行主体" in log[0], log
    ok, why = impl.check_authority(s, "didang_loan_rate", "枢密院")
    assert ok is False and "不掌" in why, why
    ok2, why2 = impl.check_authority(s, "didang_loan_rate", {"post": "抵当所提举"})
    assert ok2 is True, (ok2, why2)
    log2 = impl.apply_reform(s, {"didang_loan_rate": "中"}, "户部")
    assert log2 and "→" in log2[0], log2
    assert impl.get(s, "didang_loan_rate") == 0.05, (
        "0.01 加档 0.25 应被值域上限 0.05 钳住")
    # 不受事权约束的参数（如世袭比例）：任何主体（含无主体）都可改
    log3 = impl.apply_reform(s, {"hereditary_mult": "大"})
    assert log3 and "→" in log3[0], log3
    assert impl.get(s, "hereditary_mult") == 1.4


def test_unknown_key_still_rejected_without_raising():
    from core.game_state import GameState
    stub = importlib.import_module(OLD)
    s = GameState("史实")
    ok, why = stub.set_param(s, "不存在的参数", 1.0)
    assert ok is False and "白名单" in why
    assert stub.get(s, "不存在的参数", fallback=2.5) == 2.5


def test_new_home_is_a_leaf():
    """新落点只许 import content.*（业务层反向依赖就是 §6 硬规则1 违例）。"""
    tree = ast.parse(io.open(os.path.join(_GAME_ROOT, *IMPL_REL.split("/")),
                             encoding="utf-8").read())
    offenders = []
    for n in ast.walk(tree):
        mods = []
        if isinstance(n, ast.ImportFrom):
            mods = [n.module or ""]
        elif isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        for m in mods:
            top = m.split(".")[0]
            if top != "content" and not m.startswith("typing") and m != "":
                offenders.append("%s:%d %s" % (IMPL_REL, n.lineno, m))
    assert not offenders, f"新落点引入了 content 之外的依赖：{offenders}"
