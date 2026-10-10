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
# 新家前缀：`core.foundation.` / `core.domains.` 之外，`application.`（§1 目标代码树 + §5.2
# 应用层，如 `agent_router` 桩）与 `core.workflows.`（§1 流程编排层，第二十二包起有实现）
# 同样是合法落点，必须一起认，否则 ③ 会把合法桩误判成"无来源"。
NEW_PREFIX = ('core.foundation.', 'core.domains.', 'application.', 'core.workflows.')

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
    # 第十八包补入：经济域三模块实现已迁 core/domains/economy/
    'core.market', 'core.hoard_settle', 'core.regime_fiscal',
    # 第十九包补入：编制参数实现已迁 core/domains/administration/
    # （注意形态是 `from core import institution as _inst`，靠 mod.name 组合那条判据命中）
    'core.institution',
    # 第二十包补入：识字率实现已迁 core/domains/culture/
    'core.literacy',
    # 第二十一包补入：军队模型实现已迁 core/domains/military/
    'core.army_models',
    # 第二十二包补入：结算评价/终局判定实现已迁 core/workflows/（流程编排层首个实现）
    'core.evaluation',
    # ── 2026-10-09 台账对齐补录（非迁移批，Qoder）────────────────────────
    # 阶段 2 第 22~33 包 + 阶段 3 六包已把下列模块的实现迁出平铺（逐包细节见各自提交与
    # 各包 README，本表**只列模块名**，不复制第二份台账）。
    # 补录前实测：`game/core` 平铺纯转发桩 40 个，而本清单只声明 23 个
    # ⇒ 这 17 个模块的判据④（生产侧不得再引用旧桩）**当时没有任何常驻守卫覆盖**。
    # 判据本身由 `_scratch/b19_completion.py` 反向核对：桩集合 == 本清单，零差集。
    'core.minister_profile', 'core.flow_summary', 'core.legacy_mechanic',
    'core.monthly_gazette', 'core.minister_agent', 'core.agent_router',
    'core.crop_shadow', 'core.trade_shadow', 'core.regime_tech',
    'core.estate_mechanic', 'core.material_tech', 'core.registries',
    'core.settlement_officialdom', 'core.settlement_tech',
    'core.settlement_econ_helpers', 'core.settlement_agri', 'core.officialdom',
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
    # 判据③的对象集合**直接取 MIGRATED_OLD**，不再维护第二份清单：
    # 2026-10-09 实测发现本文件里 MIGRATED_OLD 与这份 stubs 已各自漂移
    # （前者 23 条 vs `game/core` 实际 40 个纯转发桩），说明"同一文件两份台账"就是错源。
    stubs = list(MIGRATED_OLD)
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
                if (old, name) in REBIND_CACHE_DEBT and _is_global_rebind_cache(mn, name):
                    continue      # 已登记且判据成立：惰性缓存被 global 重绑，桩侧必然停在旧绑定
                bad.append('%s.%s 不是同一对象（疑复制实现）' % (old, name))
    assert not bad, "兼容面断裂：\n" + "\n".join(bad[:10])
    assert n > 50, f"仅比对 {n} 个名字，疑比对面过窄"


# 🔴 **已登记欠账**：桩背后的 `global` 重绑型惰性缓存。
# 这类名字在实现里以 `global X; X = 新建对象` 惰性赋值（不是原地改），
# 所以桩里那份转发绑定**必然停在导入时的旧值**（这里是 `None`）——
# 与第十八包 `_TRADE_LEDGER`（原地改，桩与实现同一个对象）是两种不同的失效形态。
# ⚠️ 实测（2026-10-09，`_scratch/b22_rebind_probe.txt`）这处漂移**依赖导入顺序**：
#   · 若实现先被别的模块导入且缓存已建 ⇒ 桩再绑定时拿到同一个 dict ⇒ 判据**假绿**；
#   · 若桩先绑、缓存后建 ⇒ 桩永远停在 `None` ⇒ 判据红。
#   同一次全量里 material_tech 与 settlement_agri 两个桩的表现就不一致（前者当时还同、后者已分叉）。
#   ⇒ 这正是本登记存在的理由：**把它变成确定性豁免 + 显式静态判据**，而不是靠顺序碰运气。
# 销账动作（择一，属实现/口径变更，另立批次）：
#   ① 实现改原地更新 `_ALIAS_INDEX.clear()/update()`，让"同一对象"恒成立；
#   ② 或把该名字从旧路径转发面撤下（会改 `dir()` 公开面，需先裁定）。
# 现况风险面：生产侧已无任何模块引用这两个旧桩（判据②覆盖），
# 所以危害限于"测试经旧路径读缓存会拿到 None"——正因如此这条必须显式登记而不是放宽断言。
REBIND_CACHE_DEBT = {
    ('core.material_tech', '_ALIAS_INDEX'),      # domains/construction/material_tech.py:248
    ('core.settlement_agri', '_ALIAS_INDEX'),    # domains/production/settlement_agri.py:237
}


def _is_global_rebind_cache(mod, name):
    """静态判据：该模块里 `name` 确实被 `global` 声明过并整体重绑。"""
    try:
        tree = ast.parse(io.open(mod.__file__, encoding='utf-8',
                                 errors='replace').read())
    except (OSError, SyntaxError, AttributeError):
        return False
    declared, rebound = False, False
    for fn in [f for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for st in ast.walk(fn):
            if isinstance(st, ast.Global) and name in st.names:
                declared = True
            if isinstance(st, ast.Assign) and \
                    any(isinstance(t, ast.Name) and t.id == name for t in st.targets):
                rebound = True
    return declared and rebound


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
