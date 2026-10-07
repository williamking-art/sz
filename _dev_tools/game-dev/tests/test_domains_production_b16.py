# -*- coding: utf-8 -*-
"""第十六包回归：开 `domains/production/`（`production_chain` + `farm_procurement`）。

除桩面/同一性外，本文件钉两件事：
 🔴 **跨域调用只准用公开名**（`production_chain` 走 `material_trade_ops.commodity_dims`）；
 🔴 **产出口径与入仓不是一回事**——`settle_production_chain` 返回的是**封顶前**产量，
    写仓被 `cap` 截断；把它当入仓量会凭空多出一截（实测新局 16,205,802 vs 9,433,738）。
    另：`pending_stock` 是"归属待定"槽，**不并入** `state.resources`。
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
    'core.production_chain': 'core.domains.production.production_chain',
    'core.farm_procurement': 'core.domains.production.farm_procurement',
}
SURFACE = {
    'core.production_chain': ['BUILDING_MATERIAL_DIMS', 'Dict', 'Optional',
                              'PRODUCTION_BUILDING_MULT', '_BUILDING_LV_MAX', '_DEFAULT_CAP',
                              '_building_mult', '_pick_seat', '_write_pending',
                              '_write_warehouse', 'annotations',
                              'goods_direct_production_backup', 'pending_total',
                              'settle_production_chain'],
    'core.farm_procurement': ['Dict', 'FARM_PRICE_RATIO', 'FARM_PROCURE_DIMS', 'List',
                              'MERCHANT_BUY_RATIO', 'MERCHANT_SPEND_SHARE', 'Optional',
                              'PROCURE_MAX_TREASURY_SHARE', 'PROCURE_TARGET_MONTHS',
                              '_seat_of', '_take_goods', '_workshop_demand', 'annotations',
                              'procure_from_farmers', 'sell_surplus_to_merchants'],
}
IMPL_FILES = ('core/domains/production/production_chain.py',
              'core/domains/production/farm_procurement.py')


def test_stub_surface_exact():
    for old, expected in SURFACE.items():
        now = sorted(n for n in dir(importlib.import_module(old)) if not n.startswith('__'))
        assert now == sorted(expected), (
            "%s 公开面变了：缺 %s / 多 %s" % (
                old, sorted(set(expected) - set(now)), sorted(set(now) - set(expected))))


def test_every_name_same_object_including_privates():
    bad = []
    for old, new in MAP.items():
        mo, mn = importlib.import_module(old), importlib.import_module(new)
        bad += ['%s.%s' % (old, n) for n in SURFACE[old]
                if not hasattr(mn, n) or getattr(mo, n) is not getattr(mn, n)]
    assert not bad, "旧路径与新实现不是同一对象：%s" % bad


def test_new_home_is_a_leaf_or_public_only():
    """新落点只准引 `content` / `core.foundation.*` / `core.domains.*`，且**跨域不得取下划线名**。"""
    offenders, cross = [], []
    for rel in IMPL_FILES:
        tree = ast.parse(io.open(os.path.join(_GAME_ROOT, *rel.split('/')),
                                encoding='utf-8').read())
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module:
                top = n.module.split('.')[0]
                if top in ('engine', 'ai', 'memory', 'backend') or top == 'core' and n.module.split('.')[1] not in ('foundation', 'domains'):
                    offenders.append('%s:%d %s' % (rel, n.lineno, n.module))
                if n.module.startswith('core.domains.'):
                    priv = [a.name for a in n.names if a.name.startswith('_')]
                    if priv:
                        cross.append('%s:%d %s ← %s' % (rel, n.lineno, n.module, priv))
    assert not offenders, f"新落点出现上层/业务 import：{offenders}"
    assert not cross, f"跨域借用了私有符号（§6 规则2）：{cross}"


def test_settle_production_chain_respects_caps():
    """按**实测代码事实**断言（本用例第一版是凭想象写的，两条都不成立，见下）。

    实测三条：
    ① `settle_production_chain` 返回的 `{dim: 本月产量}` 是**封顶前**口径 ⇒
       `Σproduced ≥ ΔΣresources.stock`（新局 16,205,802 vs 入仓 9,433,738），
       **不是**"产出 == 入仓"；拿它当入仓量会凭空多出 677 万。
    ② 写仓受 `cap` 截断，**不得击穿**（盐 300 万即顶在 cap 上）。
    ③ 本局没有未裁定归属的路 ⇒ 在途（`pending_stock`）**保持 0**，
       绝不因为"生产了"就冒数出来。
    """
    from core.game_state import GameState
    pc = importlib.import_module('core.domains.production.production_chain')
    s = GameState("史实")
    assert pc.pending_total(s) == 0, f"新局在途应为 0，实际 {pc.pending_total(s)}"
    before = {k: int((v or {}).get("stock", 0) or 0)
              for k, v in (s.resources or {}).items() if isinstance(v, dict)}
    out = pc.settle_production_chain(s, [])
    assert isinstance(out, dict) and out, "新局产出链应无量，返回却为空——疑前置不成立"

    after = {k: int((v or {}).get("stock", 0) or 0)
             for k, v in (s.resources or {}).items() if isinstance(v, dict)}
    delta = sum(max(0, after[k] - before.get(k, 0)) for k in after)
    assert sum(out.values()) >= delta, f"Σproduced {sum(out.values())} < 入仓 {delta}（口径关系被改）"

    for k, v in (s.resources or {}).items():
        if not isinstance(v, dict):
            continue
        stock, cap = int(v.get("stock", 0) or 0), int(v.get("cap", 0) or 0)
        assert stock >= before.get(k, stock), f"{k} 库存倒退：{before.get(k)} → {stock}"
        if cap:
            assert stock <= cap, f"{k} 击穿 cap：stock={stock} > cap={cap}"
    assert pc.pending_total(s) == 0, "无未裁定归属的路时不该冒用在途数"


def test_unknown_dim_is_not_fabricated():
    """未知维度不得被臆造成一项产出（缺失 ≠ 有值，也 ≠ 0 条记录）。"""
    from core.game_state import GameState
    pc = importlib.import_module('core.domains.production.production_chain')
    s = GameState("史实")
    assert pc.pending_total(s, "不存在维度") == 0
    out = pc.settle_production_chain(s, [])
    assert "不存在维度" not in out, f"凭空多出产出项：{sorted(out)}"
    dims = pc.BUILDING_MATERIAL_DIMS
    assert dims, "BUILDING_MATERIAL_DIMS 空表 ⇒ 生产链会静默失效"
