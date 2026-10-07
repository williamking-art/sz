# -*- coding: utf-8 -*-
"""第十四包回归：开 `domains/diplomacy/`（`treaty` + `external_view`）。

叶子资格是**实测**出来的（顶层 import 只有 `content.data`），不是按文件名猜的——
第十三包刚因为按名字判写错过一次文档，所以这里把"实测"落成常驻断言。
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

PAIRS = {
    'core.diplomacy_treaty': 'core.domains.diplomacy.treaty',
    'core.external_view': 'core.domains.diplomacy.external_view',
}
# 迁移前冻结的旧路径公开面（`_scratch/b14_surface_before.json` 同内容，此处内联避免依赖临时文件）
EXPECTED_SURFACE = {
    'core.diplomacy_treaty': ['DIPLO_ATT_CAP', 'DOWRY_BASE', 'SUI_GONG_MULT', 'TRADE_INCOME',
                              'TREATY_TYPES', 'WAR_RISK_BOOST', '_DIPLO_ATT', '_att_delta',
                              'apply_treaty'],
    'core.external_view': ['EXTERNAL_PROVINCES', 'EXTERNAL_REGIMES',
                           '_EXTERNAL_PROVINCES_DEFAULT', 'external_pop_view',
                           'external_provinces'],
}


def test_stub_surface_exact():
    for old, expected in EXPECTED_SURFACE.items():
        m = importlib.import_module(old)
        now = sorted(n for n in dir(m) if not n.startswith('__'))
        assert now == sorted(expected), (
            "%s 公开面变了：缺 %s / 多 %s" % (
                old, sorted(set(expected) - set(now)), sorted(set(now) - set(expected))))


def test_all_names_same_object_including_privates():
    """私有名也必须同一对象——本仓有测试直取私有符号的先例，转发漏了就是静默断链。"""
    bad = []
    for old, new in PAIRS.items():
        mo, mn = importlib.import_module(old), importlib.import_module(new)
        for n in EXPECTED_SURFACE[old]:
            if getattr(mo, n) is not getattr(mn, n):
                bad.append('%s.%s' % (old, n))
    assert not bad, "以下名字旧路径与新实现不是同一对象：%s" % bad


def test_moved_files_have_no_business_imports():
    """新落点仍是叶子：只准 import `content*` 与 stdlib/typing。"""
    for rel in ('core/domains/diplomacy/treaty.py', 'core/domains/diplomacy/external_view.py'):
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


def test_production_does_not_import_old_paths():
    offenders = []
    for dp, dn, fn in os.walk(_GAME_ROOT):
        if '__pycache__' in dp:
            continue
        for f in fn:
            if not f.endswith('.py'):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, _GAME_ROOT).replace(os.sep, '/')
            if rel in ('core/diplomacy_treaty.py', 'core/external_view.py'):
                continue                      # 桩自身
            try:
                tree = ast.parse(io.open(p, encoding='utf-8', errors='replace').read())
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                mods = ([n.module] if isinstance(n, ast.ImportFrom)
                        else [a.name for a in n.names]) if isinstance(
                    n, (ast.ImportFrom, ast.Import)) else []
                for m in mods:
                    if m in PAIRS:
                        offenders.append('%s:%d %s' % (rel, n.lineno, m))
    assert not offenders, "生产代码仍 import 旧路径（判据④回退）：\n" + "\n".join(offenders)


def test_apply_treaty_real_channel_changes_state():
    """真实通道非空：签约要真的改好感并给出契约字段，不是"能 import 就算通"。"""
    from core.game_state import GameState
    treaty = importlib.import_module('core.domains.diplomacy.treaty')
    s = GameState("史实")
    target = next((k for k in (s.external or {}).keys()), None)
    assert target is not None, "前置不成立：新局没有外邦条目"
    before = dict(s.external.get(target) or {})
    got = treaty.apply_treaty(s, target, "和亲")
    assert isinstance(got, dict) and {'ok', 'msg', 'attitude_delta', 'cost'} <= set(got), (
        f"返回契约变了：{sorted(got) if isinstance(got, dict) else got!r}")
    assert got['ok'], f"和亲应被接受，实际拒绝：{got['msg']}"
    after = dict(s.external.get(target) or {})
    assert after != before, "apply_treaty 未改动外邦状态（好感通道断链会静默通过）"
    unknown = treaty.apply_treaty(s, target, "不存在的协议")
    assert not unknown['ok'], "未知协议必须**拒绝**，不得静默当成功"


def test_external_view_returns_nonempty():
    """视图必须真取到数据：`EXTERNAL_REGIMES` 表名一改就会静默返回空，只验 import 通不算数。"""
    from core.game_state import GameState
    ev = importlib.import_module('core.domains.diplomacy.external_view')
    s = GameState("史实")
    names = sorted(ev.EXTERNAL_REGIMES or {})
    assert names, "EXTERNAL_REGIMES 空表——content 侧改名/挪表会在这里先炸，不留到界面"
    sample = next((n for n in names if ev.external_provinces(s, n)), None)
    assert sample is not None, "所有势力的 external_provinces 都返回空 ⇒ 派生通道断了"
    rows = ev.external_provinces(s, sample)
    assert isinstance(rows, list) and rows and {'name', 'weight', 'population'} <= set(rows[0]), (
        f"省份派生形状变了：{rows[:1]}")
    view = ev.external_pop_view(s, sample)
    assert isinstance(view, dict) and view.get('name') == sample, f"简版视图异常：{view}"
    for k in ('population', 'power', 'army'):
        assert k in view, f"视图缺字段 {k}（面板会显示 undefined）：{sorted(view)}"
