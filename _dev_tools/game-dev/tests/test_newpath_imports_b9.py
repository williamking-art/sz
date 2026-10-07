# -*- coding: utf-8 -*-
"""第九包回归：阶段2 判据④（生产调用改指新路径）的常驻守卫。

本批实测踩到的 bug 类：`core.material_holding` 的符号**分两个新家**
（账本项 → `foundation/ledger/`，丙批二的 3 个交易项 → `domains/economy/`），
按模块整体改道会把 `commodity_dims` 指到 ledger，运行时才 `cannot import name`
——首跑全量 50 个测试文件红就是这么来的。所以这里把判定**常驻化**：

 ① `game/` 内每一处 `from core.foundation.* / core.domains.* import X`，X 必须真在该模块上；
 ② 生产代码不得再 import 已迁模块的旧桩路径（判据④不回退）；
 ③ 旧桩路径仍必须把名字转发到**同一个对象**（兼容面没坏）。

①②是静态元测试（扫 AST + import 校验），③是运行时同一性。
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

BASE = os.path.dirname(_GAME_ROOT)          # 仓库根 sz/
NEW_PREFIX = ('core.foundation.', 'core.domains.')

# 已迁模块的旧桩路径（生产侧一律不得再引用）
MIGRATED_OLD = [
    'core.money', 'core.pop_bridge', 'core.grain_bridge', 'core.pop_structure',
    'core.prefecture_entity', 'core.grain_ledger', 'core.material_holding',
    'core.numeric',
    # 第十一包补入：core/errors.py 的实现已迁 foundation/common/errors.py
    'core.errors',
    # 第十四包补入：外交域两模块实现已迁 core/domains/diplomacy/
    'core.diplomacy_treaty', 'core.external_view',
    # 第十五包补入：经济域两模块实现已迁 core/domains/economy/
    'core.dynamic_price', 'core.demand',
    # 第十六包补入：生产域两模块实现已迁 core/domains/production/
    'core.production_chain', 'core.farm_procurement',
    # 第十七包补入：政治域两模块实现已迁 core/domains/politics/
    'core.faction_split', 'core.faction_voice',
]


def _py_files(root):
    for dp, dn, fn in os.walk(root):
        if '__pycache__' in dp:
            continue
        for f in fn:
            if f.endswith('.py'):
                yield os.path.join(dp, f)


def _imports(path):
    tree = ast.parse(io.open(path, encoding='utf-8', errors='replace').read())
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            out.append((n.module, [a.name for a in n.names], n.lineno))
        elif isinstance(n, ast.Import):
            out.append((None, [a.name for a in n.names], n.lineno))
    return out


# ── ① 新路径 import 的名字必须真实存在（防"指错家"） ─────────────────
def test_new_path_import_names_resolve():
    broken = []
    checked = 0
    for p in _py_files(_GAME_ROOT):
        for mod, names, ln in _imports(p):
            if not mod or not mod.startswith(NEW_PREFIX):
                continue
            m = importlib.import_module(mod)
            for nm in names:
                if nm == '*':
                    continue
                checked += 1
                if not hasattr(m, nm):
                    broken.append('%s:%d ← %s.%s' % (
                        os.path.relpath(p, BASE).replace(os.sep, '/'), ln, mod, nm))
    assert checked > 60, f"扫描到 {checked} 个新路径导入名，太少，疑扫错目录"
    assert not broken, "以下 import 的名字不在其声明的模块上：\n" + "\n".join(broken)


# ── ② 生产侧不得再引用已迁模块的旧桩路径 ────────────────────────────
def test_production_no_longer_imports_migrated_old_paths():
    # 桩自身与包内实现不算调用方
    stub_paths = {os.path.normpath(os.path.join(_GAME_ROOT, 'core', '%s.py' % o.split('.')[-1]))
                  for o in MIGRATED_OLD}
    hits = []
    for p in _py_files(_GAME_ROOT):
        if os.path.normpath(p) in stub_paths:
            continue
        for mod, names, ln in _imports(p):
            target = mod or (names[0] if names else '')
            if target in MIGRATED_OLD:
                hits.append('%s:%d %s' % (
                    os.path.relpath(p, BASE).replace(os.sep, '/'), ln, target))
            for a in names:
                if '%s.%s' % (mod or '', a) in MIGRATED_OLD:
                    hits.append('%s:%d %s.%s' % (
                        os.path.relpath(p, BASE).replace(os.sep, '/'), ln, mod, a))
    assert not hits, "生产代码仍引用旧桩路径（判据④回退）：\n" + "\n".join(hits)


# ── ③ 旧桩路径的兼容面：同一对象，不是第二份实现 ────────────────────
def test_old_stubs_forward_to_same_objects():
    """不变量：桩面 ⊆ 实现面、逐名同一对象、且**桩自己不定义任何实现**。

    两处容易判反：
    · 不是"桩必须覆盖实现的所有名字"——桩转发的是旧路径当年的公开面；
    · 不是"一个桩对应一个实现模块"——`core.material_holding` **分两家**
      （账本项在 `foundation/ledger/`，丙批二的 3 个交易项在 `domains/economy/`）。
      所以每个名字的"家"要从**桩自己的转发语句**里取，不能手抄映射表。
    """
    stubs = ['core.money', 'core.pop_bridge', 'core.grain_bridge', 'core.pop_structure',
             'core.prefecture_entity', 'core.grain_ledger', 'core.material_holding',
             'core.numeric', 'core.errors',
             'core.diplomacy_treaty', 'core.external_view',
             'core.dynamic_price', 'core.demand',
             'core.production_chain', 'core.farm_procurement',
             'core.faction_split', 'core.faction_voice']
    bad = []
    n = 0
    for old in stubs:
        path = os.path.join(_GAME_ROOT, *old.split('.')) + '.py'
        tree = ast.parse(io.open(path, encoding='utf-8').read())
        home = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or '').startswith(NEW_PREFIX):
                for a in node.names:
                    home[a.name] = node.module
        # 桩不得自带实现（函数/类/赋值都算第二份真相）
        local = [getattr(x, 'name', '?') for x in tree.body
                 if isinstance(x, (ast.FunctionDef, ast.ClassDef))
                 or (isinstance(x, ast.Assign) and not _is_dunder(x))]
        if local:
            bad.append('%s 桩内自带实现：%s' % (old, local))
        mo = importlib.import_module(old)
        for name in [x for x in dir(mo) if not x.startswith('__')]:
            n += 1
            if name not in home:
                bad.append('%s.%s 没有转发来源（桩面与转发语句不符）' % (old, name))
                continue
            mn = importlib.import_module(home[name])
            if not hasattr(mn, name):
                bad.append('%s.%s 声称来自 %s，但该模块没有它' % (old, name, home[name]))
            elif getattr(mo, name) is not getattr(mn, name):
                bad.append('%s.%s 不是同一对象（疑复制实现）' % (old, name))
    assert not bad, "兼容面断裂：\n" + "\n".join(bad[:10])
    assert n > 50, f"仅比对 {n} 个名字，疑比对面过窄"


def _is_dunder(assign):
    return all(isinstance(t, ast.Name) and t.id.startswith('__') for t in assign.targets)


# ── ④ 分流模块必须按"符号→真实家"解析，不许整体改道 ────────────────
def test_split_module_symbols_have_exact_homes():
    """`core.material_holding` 分两个家：账本项在 ledger，3 个交易项在 domains/economy。

    本批的 bug 就是把这个桩**整体**指向 ledger。这条把"分流事实"钉在生产侧读数上：
    交易三项的真实家必须是 `core.domains.economy.material_trade_ops`。
    """
    impl = importlib.import_module('core.foundation.ledger.material_holding')
    trade = importlib.import_module('core.domains.economy.material_trade_ops')
    stub = importlib.import_module('core.material_holding')
    for nm in ('commodity_dims', 'supply_merchant_materials', 'trade_material'):
        assert not hasattr(impl, nm), (
            f'{nm} 竟也在 ledger 实现里 —— 分流前提变了，本用例与改道脚本都要重判')
        assert getattr(stub, nm) is getattr(trade, nm), f'{nm} 应来自 material_trade_ops'
