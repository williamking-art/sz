# -*- coding: utf-8 -*-
"""第十五包回归：`dynamic_price` + `demand` 并入 `domains/economy/`。

本文件多做一件以前没做的事：把 **`inspect.getsource(旧路径)` 这类"读源码散文"的用法**
扫成常驻断言。第十三/十四包的桩面断言只盯 import 与对象同一性，而这类断言盯的是
**文件里写了什么话**——搬走实现后桩里没那段话，用例会假红（或更糟：悄悄失去约束力）。
"""
import ast
import importlib
import io
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
_TESTS = os.path.normpath(os.path.join(_GAME_ROOT, "..", "_dev_tools", "game-dev", "tests"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

MAP = {
    'core.dynamic_price': 'core.domains.economy.dynamic_price',
    'core.demand': 'core.domains.economy.demand',
}
SURFACE = {
    'core.dynamic_price': ['Dict', 'LOGISTICS_TIERS', 'Optional', 'Tuple', '_clamp',
                           'annotations', 'civil_logistics', 'gov_logistics',
                           'logistics_rate', 'update_goods_prices'],
    'core.demand': ['Any', 'Dict', 'Optional', '_cfg', '_num', 'annotations', 'basic_need',
                    'demand_release', 'durable_gap', 'price_sensitivity',
                    'resolve_purchase_plan', 'substitute_for'],
}


def _aliases(tree):
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out[a.asname or a.name.split('.')[0]] = a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                out[a.asname or a.name] = '%s.%s' % (n.module, a.name)
    return out


def test_stub_surface_exact():
    for old, expected in SURFACE.items():
        now = sorted(n for n in dir(importlib.import_module(old)) if not n.startswith('__'))
        assert now == sorted(expected), (
            "%s 公开面变了：缺 %s / 多 %s" % (
                old, sorted(set(expected) - set(now)), sorted(set(now) - set(expected))))


def test_every_name_same_object():
    bad = []
    for old, new in MAP.items():
        mo, mn = importlib.import_module(old), importlib.import_module(new)
        for n in SURFACE[old]:
            if not hasattr(mn, n) or getattr(mo, n) is not getattr(mn, n):
                bad.append('%s.%s' % (old, n))
    assert not bad, "旧路径与新实现不是同一对象：%s" % bad


def test_new_home_still_a_leaf():
    """新落点必须仍是叶子：只准 stdlib/typing/`__future__`/content。"""
    for rel in ('core/domains/economy/dynamic_price.py', 'core/domains/economy/demand.py'):
        tree = ast.parse(io.open(os.path.join(_GAME_ROOT, *rel.split('/')),
                                 encoding='utf-8').read())
        bad = []
        for n in ast.walk(tree):
            mods = ([n.module] if isinstance(n, ast.ImportFrom)
                    else [a.name for a in n.names]) if isinstance(
                n, (ast.ImportFrom, ast.Import)) else []
            for m in mods:
                if m and m.split('.')[0] in ('core', 'engine', 'ai', 'memory', 'backend') \
                        and not m.startswith('core.foundation'):
                    bad.append('%s:%s' % (n.lineno, m))
        assert not bad, f"{rel} 出现业务/上层 import（叶子资格破了）：{bad}"


def test_no_getsource_on_migrated_stub_anywhere():
    """**任何**文件都不许对已迁模块的旧桩取源码（拿到的是 6 行转发语句，约束力为零）。"""
    offenders = []
    for root in (_GAME_ROOT, _TESTS):
        for dp, dn, fn in os.walk(root):
            if '__pycache__' in dp:
                continue
            for f in fn:
                if not f.endswith('.py'):
                    continue
                p = os.path.join(dp, f)
                try:
                    tree = ast.parse(io.open(p, encoding='utf-8', errors='replace').read())
                except SyntaxError:
                    continue
                al = _aliases(tree)
                for n in ast.walk(tree):
                    if not (isinstance(n, ast.Call)
                            and ast.unparse(n.func).endswith('getsource') and n.args):
                        continue
                    a0 = n.args[0]
                    tgt = None
                    if isinstance(a0, ast.Name):
                        tgt = al.get(a0.id)
                    elif isinstance(a0, ast.Attribute):
                        b = ast.unparse(a0.value)
                        tgt = al.get(b)
                        if tgt:
                            tgt = '%s.%s' % (tgt, a0.attr)
                    if tgt and any(tgt == o or tgt.startswith(o + '.') for o in MAP):
                        offenders.append('%s:%d getsource(%s → %s)' % (
                            os.path.relpath(p, _GAME_ROOT).replace(os.sep, '/'),
                            n.lineno, ast.unparse(a0), tgt))
    assert not offenders, (
        "有代码对**已迁模块的旧桩**取源码（桩里没有实现与边界声明，这类断言已失效）：\n"
        + "\n".join(offenders))


def test_metal_is_not_money_statement_survives():
    """原用例的真实意图：金属≠钱的边界声明必须在**代码**里——现在必须在实现文件中。"""
    src = io.open(os.path.join(_GAME_ROOT, 'core', 'domains', 'economy', 'dynamic_price.py'),
                  encoding='utf-8').read()
    assert '金属' in src and 'treasury' in src, "搬迁把边界声明弄丢了"


def test_real_channels_are_nonempty():
    """真实通道非空 + **缺失值不作 0**（这两个模块的既有口径，搬迁不许把它搬丢）。"""
    dm = importlib.import_module('core.domains.economy.demand')
    dp = importlib.import_module('core.domains.economy.dynamic_price')

    assert dp.LOGISTICS_TIERS, "运价档位表空了"
    # 实测代码事实：地形/战乱系数**只在显式传 cfg 时**才生效，默认只按距离档位。
    assert dp.logistics_rate(50.0) == 0.5 and dp.logistics_rate(200.0) == 1.5
    assert dp.logistics_rate(600.0) > dp.logistics_rate(50.0), "档位应随距离单调上升"
    war = dp.logistics_rate(50.0, at_war=True, cfg={"WAR_MULT": 1.5})
    assert war == 0.75, f"传 cfg 时战乱应乘 WAR_MULT，实际 {war}"

    # 口径逐值实测：ratio = demand/supply = 2 → 带宽上限 1.5 → 目标 150；
    # 月涨跌上限 ±20% 把 +50 削成 +20 ⇒ 恰好 120.0（不是 150，也不是模糊的少涨一点）
    cfg = {"GOODS_BASE_PRICE": {"盐": 100.0, "茶": 50.0}}
    prices = dp.update_goods_prices({"盐": 100.0, "茶": 50.0},
                                    {"盐": 2.0, "茶": 0.5},
                                    {"盐": 1.0, "茶": 1.0},
                                    {"盐": 0.0, "茶": 0.0}, cfg)
    assert prices["盐"] == 120.0, f"应被月度上限削到 120.0，实际 {prices['盐']}"
    # 茶：ratio=0.5/1.0=0.5 → 带宽下界 0.5 → 目标 25；月跌幅上限 ±20% 把 −25 削成 −10 ⇒ 40.0
    assert prices["茶"] == 40.0, f"茶应按月跌幅上限落到 40.0，实际 {prices['茶']}"
    # 🔴 缺基准价的品必须**跳过**，不得编造一个价出来
    partial = dp.update_goods_prices({"糖": 10.0}, {"糖": 5.0}, {"糖": 1.0}, {}, cfg)
    assert "糖" not in partial, f"无基准价的品被编造出价格：{partial}"

    assert dm.demand_release("商人", None) is None, (
        "人均 wealth 不可读必须返回 None —— 缺失 ≠ 0 是项目硬约束，不得臆造余量")
    v = dm.demand_release("商人", 10 ** 9)
    assert isinstance(v, float) and 0.0 <= v <= 1.0, f"余量释放应落在 [0,1]，实际 {v}"
    assert dm.basic_need("农", "不存在的维度", 1000) is None, "未配置应 None，不是 0 条需求"
    got = dm.basic_need("农", "米", 1000)
    assert got is None or got >= 0, f"基本需求读数异常：{got}"
