# -*- coding: utf-8 -*-
"""第十八包回归：`market` / `hoard_settle` / `regime_fiscal` 并入 `domains/economy/`。

`market` 带**模块级可变台账** `_TRADE_LEDGER`（防同一 `trade_id` 重复成交）。
这类状态放在桩后面有两种失效方式，都要有断言挡着：
 ① 桩与实现各自持有一份 dict ⇒ 台账形同虚设（重复成交会被放行）；
 ② 测试在**桩**上重新绑定 `_TRADE_LEDGER = {}` ⇒ 实现看不到，清台账变成假动作。
本文件④锁住"同一个 dict + 经桩 reset 生效"，并明确禁止 ②。
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

MAP = {
    'core.market': 'core.domains.economy.market',
    'core.hoard_settle': 'core.domains.economy.hoard_settle',
    'core.regime_fiscal': 'core.domains.economy.regime_fiscal',
}
IMPL_FILES = ('core/domains/economy/market.py', 'core/domains/economy/hoard_settle.py',
              'core/domains/economy/regime_fiscal.py')
MIN_SURFACE = {'core.market': 15, 'core.hoard_settle': 13, 'core.regime_fiscal': 11}


def _names(m):
    return sorted(n for n in dir(m) if not n.startswith('__'))


def test_stub_surface_and_identity():
    for old, new in MAP.items():
        stub, impl = importlib.import_module(old), importlib.import_module(new)
        names = _names(stub)
        assert len(names) >= MIN_SURFACE[old], f"{old} 公开面缩到 {len(names)} 名"
        src = io.open(os.path.join(_GAME_ROOT, *old.split('.')) + '.py', encoding='utf-8').read()
        home = {}
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.ImportFrom) and n.module:
                home.update({a.name: n.module for a in n.names})
        for x in names:
            assert home.get(x) == new, f"{old}.{x} 来源应是 {new}，实际 {home.get(x)}"
            assert getattr(stub, x) is getattr(impl, x)


def test_new_homes_import_only_downward():
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
    assert not priv, f"跨模块借用私有符号（§6 规则2）：{priv}"


def test_trade_ledger_is_one_shared_dict():
    """台账必须是**同一个 dict 对象**，且经桩调用 reset 能清掉实现侧状态。"""
    stub = importlib.import_module('core.market')
    impl = importlib.import_module('core.domains.economy.market')
    assert stub._TRADE_LEDGER is impl._TRADE_LEDGER, "防重台账被复制成两份 ⇒ 重复成交会放行"
    impl._TRADE_LEDGER[('k', 't-probe')] = {'ok': True}
    assert ('k', 't-probe') in stub._TRADE_LEDGER, "经桩看不到实现侧台账 ⇒ 桩成了第二份状态"
    stub.reset_trade_ledger()
    assert not impl._TRADE_LEDGER, "经桩 reset 没清掉实现台账 ⇒ 测试隔离会失效"


def test_trade_goods_moves_goods_and_money_once():
    """唯一成交入口的守恒与防重：一次成交两边都动，重复 `trade_id` 不得二次放行。"""
    from core.game_state import GameState
    m = importlib.import_module('core.domains.economy.market')
    m.reset_trade_ledger()
    s = GameState("史实")
    buyer = {"goods": {"木": 0}, "wealth": 100000}
    seller = {"goods": {"木": 500}, "wealth": 0}
    out = m.trade_goods(s, dim="木", qty=100, price=10.0, buyer=buyer, seller=seller,
                        purpose="resale", trade_id="b18-probe-1")
    assert out.get('ok'), f"成交被拒：{out}"
    assert buyer["goods"]["木"] == 100 and seller["goods"]["木"] == 400, f"货未双向挪动：{out}"
    assert buyer["wealth"] == 99000 and seller["wealth"] == 1000, "钱未按价划转"
    again = m.trade_goods(s, dim="木", qty=100, price=10.0, buyer=buyer, seller=seller,
                          purpose="resale", trade_id="b18-probe-1")
    assert not again.get('ok'), f"同一 trade_id 被二次放行（防重台账失效）：{again}"
    assert buyer["goods"]["木"] == 100, "重复成交仍改了库存"


def test_sellable_stock_semantics():
    m = importlib.import_module('core.domains.economy.market')
    assert m.sellable_stock(seller=None, dim="木") == 0, "卖方不存在应 0（不是 None 也不是负数）"
    assert m.sellable_stock(seller={"goods": {"木": 300}}, dim="木", reserved=120) == 180
    assert m.sellable_stock(seller={"goods": {"木": 50}}, dim="木", reserved=999) >= 0, \
        "预留超过持仓时不得给负库存"
