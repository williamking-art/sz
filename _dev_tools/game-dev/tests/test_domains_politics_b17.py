# -*- coding: utf-8 -*-
"""第十七包回归：开 `domains/politics/`（`split` + `voice`，§3.1 横切能力归位）。

除桩面/同一性外，钉两条：
 🔴 **桩不是行为开关**：patch 打在旧桩上的名字**不会**影响实现模块 ⇒ 想改运行时行为
    必须打实现模块（第九、十七包两次都是这么红过 / 预防的）。
 🔴 跨模块 import **不得出现下划线名**（§6 规则2）。
"""
import ast
import importlib
import io
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

MAP = {'core.faction_split': 'core.domains.politics.split',
       'core.faction_voice': 'core.domains.politics.voice'}
IMPL_FILES = ('core/domains/politics/split.py', 'core/domains/politics/voice.py')


def _surface(old):
    return sorted(n for n in dir(importlib.import_module(old)) if not n.startswith('__'))


def test_stub_surface_and_identity():
    """桩面非空、每个桩名都从实现模块转发且同一对象。"""
    for old, new in MAP.items():
        names = _surface(old)
        assert len(names) >= 15, f"{old} 公开面只剩 {len(names)} 名，疑桩写漏"
        mn = importlib.import_module(new)
        src = io.open(os.path.join(_GAME_ROOT, *old.split('.')) + '.py',
                      encoding='utf-8').read()
        home = {}
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    home[a.name] = n.module
        for x in names:
            assert home.get(x) == new, f"{old}.{x} 的转发来源应是 {new}，实际 {home.get(x)}"
            assert getattr(importlib.import_module(old), x) is getattr(mn, x)


def test_stub_is_not_a_behavior_switch(monkeypatch):
    """在桩上改名，实现模块**不受影响** ⇒ 行为类 patch 必须打实现。"""
    stub = importlib.import_module('core.faction_split')
    impl = importlib.import_module('core.domains.politics.split')
    orig = impl.split_of

    def _boom(*a, **k):
        raise AssertionError('不该被调到')

    monkeypatch.setattr(stub, 'split_of', _boom)
    assert impl.split_of is orig, "桩与实现已不是同一对象 ⇒ 桩被写成了第二份实现"
    try:                       # 经**桩**取到的名字已指向 boom，经实现取到的仍是原函数
        assert stub.split_of is _boom
    finally:
        monkeypatch.undo()
    assert impl.split_of is orig


def test_new_home_has_no_business_or_private_imports():
    offenders, priv = [], []
    for rel in IMPL_FILES:
        tree = ast.parse(io.open(os.path.join(_GAME_ROOT, *rel.split('/')),
                                encoding='utf-8').read())
        for n in ast.walk(tree):
            if not isinstance(n, ast.ImportFrom) or not n.module:
                continue
            top = n.module.split('.')[0]
            if top in ('engine', 'ai', 'memory', 'backend') or (
                    top == 'core' and n.module.split('.')[1] not in ('foundation', 'domains')):
                offenders.append('%s:%d %s' % (rel, n.lineno, n.module))
            if n.module.startswith(('core.foundation.', 'core.domains.')):
                priv += ['%s:%d %s ← %s' % (rel, n.lineno, n.module, a.name)
                         for a in n.names if a.name.startswith('_')]
    assert not offenders, f"新落点出现业务/上层 import：{offenders}"
    assert not priv, f"跨模块借用了私有符号（§6 规则2）：{priv}"


def test_split_object_identity_rule_preserved():
    """既有硬约束：`set_split` 不得替换 `state.faction_split` 对象（原地改）。"""
    from core.game_state import GameState
    sp = importlib.import_module('core.domains.politics.split')
    s = GameState("史实")
    ident = id(s.faction_split)
    sp.set_split(s, "官僚", {"新党": 0.5, "中立派": 0.5})
    assert id(s.faction_split) == ident, "set_split 替换了 state.faction_split 对象"
    assert sp.split_of(s, "官僚").get("新党") == pytest.approx(0.5)
