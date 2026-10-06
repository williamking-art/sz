# -*- coding: utf-8 -*-
"""第十二包回归：`pop_bridge._split_int` → 显式接口 `split_int`（销同包私有欠账）。

`split_int` 是整个下沉链路的**守恒基元**（尾差归权重最大者 ⇒ Σ治所 == 路级原值），
POP 拆分、粮回填、归属子池都靠它。接口化最容易出的事故是"改了名、口径跟着漂"，
所以这里把语义逐条钉死，而不是只验 import 成功。
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

IMPL = importlib.import_module('core.foundation.ledger.pop_bridge')
STUB = importlib.import_module('core.pop_bridge')


def test_public_interface_and_alias():
    assert 'split_int' in IMPL.__all__, "未进 __all__ ⇒ 不算显式接口"
    assert IMPL._split_int is IMPL.split_int, "旧私有名必须是**同一对象**的别名，不许留第二份实现"
    src = io.open(os.path.join(_GAME_ROOT, 'core', 'foundation', 'ledger', 'pop_bridge.py'),
                  encoding='utf-8').read()
    tree = ast.parse(src)
    defs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert defs.count('split_int') == 1 and '_split_int' not in defs, (
        "桩外再存一份 def 就是双实现")


def test_stub_surface_not_shrunk():
    """改名**不得**缩小旧路径公开面：`_split_int` 还在，`split_int` 不该漏进来。"""
    names = {n for n in dir(STUB) if not n.startswith('__')}
    assert '_split_int' in names, "旧私有名从桩上消失 ⇒ 依赖它的历史 import 会断"
    assert 'split_int' not in names, "新接口名不该出现在旧路径（公开面必须与迁移前一致）"
    assert STUB._split_int is IMPL.split_int


def test_split_semantics_locked():
    """尾差归权重最大者、Σ 精确相等、零值与空权重的返回形状都不得漂。"""
    f = IMPL.split_int
    assert f(10, [('a', 1), ('b', 2)]) == {'a': 3, 'b': 7}
    assert f(10, [('a', 1), ('b', 1), ('c', 1)]) == {'a': 4, 'b': 3, 'c': 3} or \
           sum(f(10, [('a', 1), ('b', 1), ('c', 1)]).values()) == 10, "Σ 必须精确等于 total"
    for total in (7, 11, 999):
        for w in ([('x', 1), ('y', 2), ('z', 5)], [('x', 3)], [('x', 1), ('y', 1)]):
            assert sum(f(total, w).values()) == total, (total, w)
    # 🔴 零值/空权重的返回**形状**是调用方区分语义的依据
    assert f(0, [('a', 1), ('b', 2)]) == {'a': 0, 'b': 0}, 'total=0 应给每个治所 0，不是 {}'
    assert f(5, [('a', 0), ('b', 0)]) == {'a': 0, 'b': 0}, '权重和<=0 应给每个治所 0'
    assert f(5, []) == {}, '没有治可拆才是空表'


def test_grain_bridge_uses_public_name():
    gb = os.path.join(_GAME_ROOT, 'core', 'foundation', 'ledger', 'grain_bridge.py')
    tree = ast.parse(io.open(gb, encoding='utf-8').read())
    borrowed = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or '') == 'core.foundation.ledger.pop_bridge':
            borrowed += [a.name for a in n.names if a.name.startswith('_')]
    assert not borrowed, f"grain_bridge 仍在借 pop_bridge 私有符号：{borrowed}"
