# -*- coding: utf-8 -*-
"""第十包回归：ledger 私有符号提升为显式接口（销架构方案 §6 规则 2 偏离）。

守的是一条**规则**而不是两个名字：跨包（`domains/*`、`foundation/*` 之间）
不得 import 下划线开头的他模块符号。本批之前 `material_trade_ops` 借了
`_attribute_to_seats` / `_route_of`，正是这条的已知偏离。
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

LEDGER = 'core.foundation.ledger.material_holding'
TRADE = 'core.domains.economy.material_trade_ops'
PAIRS = {'_attribute_to_seats': 'attribute_to_seats', '_route_of': 'route_of'}


# ── ① 公开接口存在、进 __all__、旧私有名是同对象别名 ──────────────
def test_public_names_exist_and_are_aliased():
    m = importlib.import_module(LEDGER)
    for old, new in PAIRS.items():
        assert hasattr(m, new), f"缺少显式接口 {new}"
        assert new in m.__all__, f"{new} 未进 __all__（不算显式接口）"
        assert getattr(m, old) is getattr(m, new), f"{old} 与 {new} 不是同一对象（别名写坏了）"


# ── ② 旧桩公开面守恒：既不丢下划线名，也不得多出公开名 ────────────
def test_stub_surface_unchanged():
    stub = importlib.import_module('core.material_holding')
    for old, new in PAIRS.items():
        assert hasattr(stub, old), f"桩丢了旧名 {old}（dir() 公开面被缩小）"
        assert not hasattr(stub, new), (
            f"桩不该新增 {new}——兼容入口的公开面必须与迁移前一致，"
            "悄悄扩大 API 会让'旧路径=旧面'这个前提失效")
        assert getattr(stub, old) is getattr(importlib.import_module(LEDGER), new)


# ── ③ 跨包不得借用他模块私有符号（规则 2 的常驻守卫） ─────────────
# 同包内的私有借用**单独登记为已知欠账**，只要求"不得新增"。
# 第十二包（2026-10-07）已把唯一一条销干净：`grain_bridge` 改读 `pop_bridge.split_int`
# （`_split_int` 仅作兼容别名保留）。清单留空**本身就是验收判据**——
# 将来谁再借同包私有符号，这条用例会直接红。
KNOWN_SAME_PKG_DEBT = set()


def test_no_cross_package_private_imports():
    cross, same = [], []
    for sub in ('core/domains', 'core/foundation', 'core/workflows'):
        root = os.path.join(_GAME_ROOT, *sub.split('/'))
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            if '__pycache__' in dp:
                continue
            for f in fn:
                if not f.endswith('.py'):
                    continue
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, _GAME_ROOT).replace(os.sep, '/')
                pkg = os.path.dirname(rel).replace('/', '.')      #  importer 所在包
                tree = ast.parse(io.open(p, encoding='utf-8', errors='replace').read())
                for n in ast.walk(tree):
                    if not isinstance(n, ast.ImportFrom) or not (n.module or '').startswith(
                            ('core.foundation.', 'core.domains.', 'core.workflows.')):
                        continue
                    src_pkg = '.'.join(n.module.split('.')[:-1])   # 被导入模块所在包
                    for a in n.names:
                        if not a.name.startswith('_') or a.name == '__future__':
                            continue
                        item = '%s:%d from %s import %s' % (rel, n.lineno, n.module, a.name)
                        (same if src_pkg == pkg else cross).append(item)
    assert not cross, (
        "跨包借用他模块私有符号（架构方案 §6 规则 2 违例，须接口化）：\n" + "\n".join(cross))
    extra = sorted(set(same) - KNOWN_SAME_PKG_DEBT)
    assert not extra, "同包私有借用出现**新增**（欠账只能减不能加）：\n" + "\n".join(extra)


# ── ④ 真实通道非空：接口化后分配仍然发生 ─────────────────────────
def test_attribute_to_seats_still_attributes():
    """必须用**真实 state 的商人 POP**：裸 dict 拿不到州府权重 ⇒ 合法地返回 0。

    本用例连错两版才立住，两条都值得记：
    ① 拿 `{"goods": {}}` 断言非空是**前提错**（权重来自 `seat_weights_of_circuit(路名)`，
       裸 dict 场景下取不到 ⇒ 归 0），不是实现坏；
    ② POP 的物料命名空间键名是 **`goods`**，里面**商品维**才是中文（`木`/`盐`…）——
       断成 `pop["货"]` 会得到空样本假红。
    """
    from core.game_state import GameState
    m = importlib.import_module(LEDGER)
    state = GameState("史实")
    route = next((r for r in state.prefectures
                  if m.merchant_of(state, r) is not None), None)
    assert route is not None, "前置不成立：新局取不到任何路的商人 POP"
    pop = m.merchant_of(state, route)
    n = m.attribute_to_seats(pop, route, "木", 100)
    assert n == 100, (
        f"attribute_to_seats 返回 {n}（应精确归属 100）—— 接口化后分配断链或权重取不到")
    goods = pop.get("goods") or {}          # POP 物料命名空间键名是 `goods`（中文的是**商品维**名）
    buckets = {k: v for k, v in goods.items()
               if m.is_seat_bucket_key(str(k)) and isinstance(v, dict)}
    assert buckets, f"没有州府桶键（goods 键样本：{list(goods)[:4]}）"
    got = sum(int(v.get("木", 0) or 0) for v in buckets.values())
    assert got == 100, f"Σ治所桶「木」应精确等于 100，实际 {got}（守恒破了）"


def test_route_of_matches_by_identity_only():
    m = importlib.import_module(LEDGER)
    pop = {"名": "商人甲"}
    prefs = {"京畿路": {"pops": {"k": pop}}}
    assert m.route_of(prefs, pop) == "京畿路"
    assert m.route_of(prefs, {"名": "商人甲"}) is None, (
        "按**对象同一性**匹配是口径：内容相同但不同对象不得认作同一 POP")
