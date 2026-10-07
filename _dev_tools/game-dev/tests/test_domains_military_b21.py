# -*- coding: utf-8 -*-
"""第二十一包回归：开 `domains/military/`（`army_models`，§7 军事机制候选）。

本批除结构（①-③）外，还**同批销了一笔 §6 规则2 的账**（④）——四个私有名被四个跨模块
生产点直接取用，属"跨域读写私有内部函数"。销法照第十/十二包先例：在实现里加**公开别名**
（同一对象，非包装），把四个消费者改指公开名，旧 `_` 名保留为兼容别名。

 ① 桩面逐字等于迁移前冻结的 `dir()` 快照（36 个非 dunder 名，含 6 个私有名与 typing/dataclass 绑定名）；
 ② 逐名从实现转发且同一对象，桩内不许自带实现；`__all__` 是**原样拷贝**（本就只有 1 项，别"顺手补全"）；
 ③ 桩不是行为开关 + 全测试目录禁止把旧桩当 patch 提供方（AST 别名解析）；
 ④ 🔴 **新路径上不得有人取用私有名**（`_army_power`/`_army_power_total`/`_resolve_battle`/`_defense_line_for`）
    ——公开别名必须是同一对象，且生产代码一律用公开名；
 ⑤ 真实数据通道非空（content 表经新路径取到 35 支部队 / 7 项装备键 / 5 条防线 / 非空战力与月饷）；
 ⑥ 新落点零 `core` import（只 content + dataclasses/typing）。
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
OLD = "core.army_models"
NEW = "core.domains.military.army_models"

# 迁移前 dir() 冻结（_scratch/b21_surface_army.json，45 名去 9 个 dunder）
FROZEN_SURFACE = frozenset({
    "ARMY_UNIT_INIT", "ARMY_UNIT_SPLIT", "ArmyUnit", "CENTRAL_ARSENAL_INIT", "CentralArsenal",
    "ENFORCE_ARREARS_W", "ENFORCE_BASE", "ENFORCE_FLOOR", "ENFORCE_MORALE_W",
    "EQUIP_KEYS", "EQUIP_STD", "FRONTIER_MORALE_BONUS", "FRONTIER_ROUTES",
    "FRONTIER_TRAIN_BONUS", "Optional", "UNIT_TIER",
    "_DEFENSE_LINE_OF", "_army_power", "_army_power_total", "_defense_line_for",
    "_firearm_power_mult", "_org_names", "_resolve_battle", "_troops_weighted",
    "annotations", "branch_std", "build_army_units", "dataclass", "deposit_workshop",
    "distribute_arsenal", "field", "military_channels", "reorganize_xiang_to_jin",
    "unit_enforcement_mult", "unit_monthly_pay", "unit_tier_of",
})

IMPL_REL = "core/domains/military/army_models.py"

# 本批销账的四个私有名 → 公开接口
PROMOTED = {"army_power": "_army_power",
            "army_power_total": "_army_power_total",
            "resolve_battle": "_resolve_battle",
            "defense_line_for": "_defense_line_for"}


def _impl():
    return importlib.import_module(NEW)


def _non_dunder(mod):
    return {n for n in dir(mod) if not (n.startswith("__") and n.endswith("__"))}


def _iter_py(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


# ── ①-② 桩面 / 转发 / 同一性 ──────────────────────────────────────
def test_stub_surface_equals_frozen_snapshot():
    surface = _non_dunder(importlib.import_module(OLD))
    assert surface == FROZEN_SURFACE, (
        "公开面漂移 缺=%s 多=%s" % (sorted(FROZEN_SURFACE - surface),
                                    sorted(surface - FROZEN_SURFACE)))


def test_every_name_forwards_to_same_object():
    path = os.path.join(_GAME_ROOT, *OLD.split(".")) + ".py"
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    home = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                home[a.name] = n.module
    local_impl = [getattr(x, "name", "?") for x in tree.body
                  if isinstance(x, (ast.FunctionDef, ast.ClassDef))]
    assert not local_impl, f"桩内自带实现（第二份真相）：{local_impl}"
    impl = _impl()
    for name in _non_dunder(importlib.import_module(OLD)):
        assert home.get(name) == NEW, f"{OLD}.{name} 应由 {NEW} 转发，实际 {home.get(name)}"
        assert getattr(importlib.import_module(OLD), name) is getattr(impl, name)


def test_all_is_verbatim_copy_single_entry():
    """既有 `__all__` 本就只有 1 项（`from core.army_models import *` 只给 EQUIP_STD）。

    这是**迁移前的既有事实**，本批不"顺手补全"（那会扩大公开面）；桩里按纪律原样拷贝。
    """
    stub, impl = importlib.import_module(OLD), _impl()
    assert impl.__all__ == ["EQUIP_STD"], impl.__all__
    assert stub.__all__ == impl.__all__


def test_stub_is_not_a_behavior_switch(monkeypatch):
    stub, impl = importlib.import_module(OLD), _impl()
    orig = impl.build_army_units
    monkeypatch.setattr(stub, "build_army_units", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("不该被调到")))
    try:
        assert impl.build_army_units is orig
    finally:
        monkeypatch.undo()
    assert impl.build_army_units is orig


def test_no_test_patches_the_old_army_stub():
    tests = os.path.join(BASE, "_dev_tools", "game-dev", "tests")
    offenders = []
    for path in _iter_py(tests):
        try:
            tree = ast.parse(io.open(path, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        aliases = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    if a.name == OLD:
                        aliases.add(a.asname or a.name.split(".")[-1])
            elif isinstance(n, ast.ImportFrom) and (n.module or "") == "core":
                for a in n.names:
                    if a.name == "army_models":
                        aliases.add(a.asname or a.name)
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and getattr(n.func, "attr", "") in ("setattr", "delattr")
                    and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id in aliases):
                offenders.append("%s:%d" % (os.path.relpath(path, BASE).replace(os.sep, "/"),
                                            n.lineno))
    assert not offenders, "旧桩被当 patch 提供方：\n" + "\n".join(offenders)


# ── ④ §6 规则2 销账：公开别名同一对象 + 生产侧不得再用私有名 ────────
def test_public_aliases_are_same_objects():
    impl = _impl()
    for pub, priv in PROMOTED.items():
        assert hasattr(impl, pub), f"公开接口 {pub} 不存在"
        assert getattr(impl, pub) is getattr(impl, priv), (
            f"{pub} 应是 {priv} 的同一对象（别名），不是包装或复制")


def test_production_never_imports_private_names_from_new_home():
    """生产侧从新路径取私有名 = §6 规则2 违例（本批刚销账，不许回潮）。"""
    offenders = []
    for path in _iter_py(os.path.join(BASE, "game")):
        rel = os.path.relpath(path, BASE).replace(os.sep, "/")
        if rel in ("game/" + IMPL_REL, "game/core/army_models.py"):
            continue      # 实现自身可定义私有名；旧路径桩按公开面纪律必然转发私有名
        try:
            tree = ast.parse(io.open(path, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and (n.module or "") == NEW:
                for a in n.names:
                    if a.name.startswith("_"):
                        offenders.append("%s:%d %s" % (rel, n.lineno, a.name))
    assert not offenders, "跨域取用私有名（§6 规则2）：\n" + "\n".join(offenders)


# ── ⑤ 真实数据通道非空（经新路径） ───────────────────────────────
def test_real_channels_non_empty():
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    units = impl.build_army_units(s)
    assert len(units) == 35, f"开局部队数变了（{len(units)}），哨兵前提需重判"
    assert impl.unit_tier_of(units[0]) == "禁军"
    assert len(impl.EQUIP_KEYS) == 7 and len(impl._DEFENSE_LINE_OF) == 5
    ch = impl.military_channels(s)
    assert ch and ch["troops"] > 0 and ch["monthly_pay"] > 0, ch
    assert impl.military_channels(s, "京畿路"), "按路读数取不到"
    gun = s.tech.get("gunpowder", 20)
    assert round(impl.army_power_total(units, gun), 1) == 298950.0, "总战力基线变了"
    assert impl.unit_monthly_pay(units[0]) > 0
    assert impl.resolve_battle(100.0, 50.0) == (True, 10.0, False)


# ── ⑥ 新落点是叶子 ───────────────────────────────────────────────
def test_new_home_is_a_pure_content_leaf():
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
            if top in ("core", "engine", "ai", "backend", "memory"):
                offenders.append("%s:%d %s" % (IMPL_REL, n.lineno, m))
    assert not offenders, f"新落点出现 core/上层依赖：{offenders}"
