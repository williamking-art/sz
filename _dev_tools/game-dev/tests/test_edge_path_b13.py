# -*- coding: utf-8 -*-
"""第十三包回归：`distribute_cash` 接口化 + 两条边改直认真实家。

阶段 1 文档原把 `asset_context:176` / `focus_mechanic:445` 标成"读数应从读数服务取"，
实测两者取用的都是**守恒写通道**（`transfer_public_funds_to_pops` / `_distribute_cash`）。
按错标签做成只读服务会直接破 `ΣΔ == 0`，所以本文件的重点是③④**守恒语义**，不是 import 通不通。
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

SC = importlib.import_module('core.settlement_common')
SS = importlib.import_module('core.settlement_steps')


def test_public_name_is_single_implementation():
    assert 'distribute_cash' in [n.name for n in ast.parse(
        io.open(os.path.join(_GAME_ROOT, 'core', 'settlement_common.py'),
               encoding='utf-8').read()).body if isinstance(n, ast.FunctionDef)]
    assert SC._distribute_cash is SC.distribute_cash, "旧名必须是别名，不是第二份实现"
    assert SS._distribute_cash is SC.distribute_cash, "经编排器再导出的也须同一对象"


def test_callers_import_from_real_home():
    """两条边不再绕道结算编排器取写原语。"""
    for rel in ('core/focus_mechanic.py', 'core/asset_context.py'):
        tree = ast.parse(io.open(os.path.join(_GAME_ROOT, *rel.split('/')),
                                 encoding='utf-8').read())
        via_steps = [ast.unparse(n) for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom)
                     and (n.module or '').endswith('settlement_steps')
                     and any(a.name in ('_distribute_cash', 'distribute_cash',
                                         'transfer_public_funds_to_pops') for a in n.names)]
        assert not via_steps, f"{rel} 仍从 settlement_steps 取写原语：{via_steps}"
    assert not hasattr(importlib.import_module('core.focus_mechanic'), '_distribute_cash')


def test_distribute_cash_conserves_exactly():
    """守恒：Σ入账 == amount（末位吃尾差），且 `applied` 逐笔如实上报实际入账。"""
    from core.game_state import GameState
    s = GameState("史实")
    applied = []
    before = sum(int((p.get("pops") or {}).get(c, {}).get("wealth", 0) or 0)
                 for p in s.prefectures.values() for c in ("工匠", "商人")
                 if isinstance((p.get("pops") or {}).get(c), dict))
    got = SC.distribute_cash(s, 10_000, {"工匠": 0.4, "商人": 0.6}, applied=applied)
    after = sum(int((p.get("pops") or {}).get(c, {}).get("wealth", 0) or 0)
                for p in s.prefectures.values() for c in ("工匠", "商人")
                if isinstance((p.get("pops") or {}).get(c), dict))
    assert got == 10_000, f"应全额分发 10000，实际 {got}"
    assert after - before == got, f"ΣPOP 增量 {after - before} != 分发额 {got}（凭空造币/丢钱）"
    assert sum(applied) == got, f"applied 合计 {sum(applied)} != {got}（退款依据会错）"


def test_zero_and_missing_pool_semantics():
    assert SC.distribute_cash(None, 0, {"工匠": 1.0}) == 0, "amount<=0 应返回 0"
    from core.game_state import GameState
    s = GameState("史实")
    for p in s.prefectures.values():
        (p.get("pops") or {}).pop("工匠", None)
        (p.get("pops") or {}).pop("商人", None)
    assert SC.distribute_cash(s, 5000, {"工匠": 1.0}) == 0, "无接收池应分发 0，不得凭空记数"


def test_reverse_edge_doc_matches_code():
    """阶段 1 文档的**表行**必须不再把这两条写成"读数"——错标会直接指导下一次错误重构。

    只查表行（以 `| \`模块\`` 开头），否则正文里提到模块名的普通句子会被误判。
    """
    doc = os.path.normpath(os.path.join(_GAME_ROOT, "..", "_dev_tools", "game-docs", "specs",
                                        "cross-cutting", "阶段1_依赖图与循环依赖.md"))
    rows = {}
    for ln in io.open(doc, encoding='utf-8').read().splitlines():
        for mod in ('asset_context', 'focus_mechanic'):
            if ln.startswith('| `%s`' % mod):
                rows[mod] = ln
    assert set(rows) == {'asset_context', 'focus_mechanic'}, f"表行没找到：{sorted(rows)}"
    for mod, ln in rows.items():
        assert '守恒写' in ln, f"{mod} 表行缺实测性质标注（仍可能被当读数倒置）：{ln[:90]}"
        assert 'transfer_public_funds_to_pops' in ln or 'distribute_cash' in ln, (
            f"{mod} 表行没写明真实取用符号：{ln[:90]}")
