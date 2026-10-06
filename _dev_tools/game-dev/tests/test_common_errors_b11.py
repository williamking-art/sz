# -*- coding: utf-8 -*-
"""第十一包回归：`AIRuntimeError` 自 `core/errors.py` 迁入 `foundation/common/errors.py`。

`errors` 是 `common/` 的第二件（§106）。这个模块的价值全在"**零依赖**"上——
它存在的理由就是"不导入任何业务模块，供各层共享"，所以守卫里最硬的一条是③。
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

OLD = 'core.errors'
NEW = 'core.foundation.common.errors'


def test_stub_surface_exact():
    """桩的公开面必须是**恰好** `{AIRuntimeError}`——不多不少。"""
    stub = importlib.import_module(OLD)
    now = {n for n in dir(stub) if not n.startswith('__')}
    assert now == {'AIRuntimeError'}, f"公开面变了：{sorted(now)}"


def test_old_path_is_same_object():
    assert getattr(importlib.import_module(OLD), 'AIRuntimeError') is \
        getattr(importlib.import_module(NEW), 'AIRuntimeError'), \
        "旧路径不是同一对象（桩复制了类定义 ⇒ 两份异常，except 会漏）"


def test_new_module_has_zero_imports():
    """本模块必须**一条 import 都没有**（它存在的理由就是不碰业务模块）。

    迁移时手滑加一行 `from content.data import AI_ERROR_CODES` 不会报错，
    但会把 `common → content` 之外的依赖引进基础层，且可能重新造出循环导入。
    """
    p = os.path.join(_GAME_ROOT, 'core', 'foundation', 'common', 'errors.py')
    tree = ast.parse(io.open(p, encoding='utf-8', errors='replace').read())
    imports = [ast.unparse(n) for n in tree.body
               if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not imports, f"零依赖前提被破坏，出现 import：{imports}"


def test_exception_semantics_unchanged():
    E = getattr(importlib.import_module(NEW), 'AIRuntimeError')
    assert issubclass(E, RuntimeError)
    assert str(E()) == '' and E().code == '', '默认构造语义变了'
    e = E('超时', code='AI_TIMEOUT')
    assert e.code == 'AI_TIMEOUT' and isinstance(e.args[0], str)
    assert E('x', code=None).code == '', 'code 传 None 应回落空串，不是 None'
    try:
        raise E('boom', code='AI_NETWORK')
    except RuntimeError as got:                 # 上层按 RuntimeError 捕获的既有路径必须在
        assert got.code == 'AI_NETWORK'
    else:
        raise AssertionError('异常未抛出')

    class Sub(E):
        pass

    assert Sub('y', code='Z').code == 'Z'


def test_production_no_longer_imports_old_errors_path():
    """生产侧 8 处已改指新路径；旧路径只留给测试与兼容门面。"""
    offenders = []
    for dp, dn, fn in os.walk(_GAME_ROOT):
        if '__pycache__' in dp:
            continue
        for f in fn:
            if not f.endswith('.py'):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, _GAME_ROOT).replace(os.sep, '/')
            if rel == 'core/errors.py':          # 桩自身
                continue
            tree = ast.parse(io.open(p, encoding='utf-8', errors='replace').read())
            for n in ast.walk(tree):
                mods = []
                if isinstance(n, ast.ImportFrom):
                    mods = [n.module or '']
                elif isinstance(n, ast.Import):
                    mods = [a.name for a in n.names]
                for m in mods:
                    if m == OLD or m.startswith(OLD + '.'):
                        offenders.append('%s:%d' % (rel, n.lineno))
    assert not offenders, "生产代码仍 import 旧路径 core.errors：\n" + "\n".join(offenders)
