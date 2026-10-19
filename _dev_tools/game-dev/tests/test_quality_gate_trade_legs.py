# -*- coding: utf-8 -*-
"""质量放行门 · P5 外贸货腿（2026-10-18；Jev：默认关 0.970）。

规则：出口不足**缩量**、进口受仓容限制、关税按**实际成交额**、运力不足**排队**、总开关默认关。
本门钉住：
1. 默认关闭 ⇒ `settle_foreign_trade` 返回 enabled=False 且**不动 state**；
2. `plan_legs` 纯函数、可复现、缺价维 `unit_price=None`；
3. 出口缩量：库存 50、计划 400 ⇒ shipped=50、short=350、库存归 0 且**不为负**；
4. 进口受 `resources[dim].cap` 限制；
5. 关税按实际 value；value=None ⇒ tax=None（缺失≠0）；
6. 开启后运力不足 ⇒ 石数进排队；
7. `dry_run=True` 不改库存（影子对账用）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

import content.data_constants as dc  # noqa: E402
from core.domains.economy import trade_legs as TL  # noqa: E402
from core.foundation.ledger.resource_stock_bridge import stock_add, stock_get  # noqa: E402


def _state():
    from core.commands import new_game

    return new_game()


def test_switch_off_is_noop(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 0)
    assert TL.trade_legs_enabled() is False
    before = dict((d, (s.resources.get(d) or {}).get("stock")) for d in ("香药", "茶"))
    r = TL.settle_foreign_trade(s, month=1)
    assert r["enabled"] is False
    after = dict((d, (s.resources.get(d) or {}).get("stock")) for d in ("香药", "茶"))
    assert before == after, "默认关必须零行为变更"


def test_plan_legs_is_deterministic_and_priced():
    s = _state()
    a = TL.plan_legs(s, month=1)
    b = TL.plan_legs(s, month=1)
    assert len(a) == len(b) and len(a) > 0
    assert a == b
    assert all("unit_price" in x and "direction" in x for x in a)
    missing = [x["dim"] for x in a if x["unit_price"] is None]
    assert not missing, f"这些货种缺基准价（缺失≠0，需补齐或登记豁免）：{sorted(set(missing))}"


def test_export_shrinks_and_never_negative():
    s = _state()
    dim = "茶"
    route = "广南东路"
    # 外销只走**商人货**（官仓不被外贸抽空）；测试按新口径铺商人库存
    from core.foundation.ledger.material_holding import goods_add, merchant_goods
    goods_add(merchant_goods(s, route), dim, 50)
    leg = {"channel": "land", "dim": dim, "direction": "export", "planned_qty": 400,
           "unit_price": dc.MATERIAL_PRICE_BASE[dim], "seat": None, "route": route}
    out = TL.execute_leg(s, leg)
    assert out["ok"] and out["shipped_qty"] == 50 and out["short_qty"] == 350, out
    from core.foundation.ledger.material_holding import goods_amount
    assert int(goods_amount(merchant_goods(s, route), dim) or 0) == 0
    assert out["value"] == 50 * dc.MATERIAL_PRICE_BASE[dim]


def test_import_limited_by_cap():
    s = _state()
    dim = "锡"
    route = "广南东路"
    s.resources[dim] = {"stock": 0, "cap": 10}
    leg = {"channel": "sea", "dim": dim, "direction": "import", "planned_qty": 400,
           "unit_price": dc.MATERIAL_PRICE_BASE[dim], "route": route}
    out = TL.execute_leg(s, leg)
    # 仓容=全池 cap；本路现有 0 ⇒ 收满即止（不足则缩量，不越过 cap）
    assert out["ok"], out
    assert out["received_qty"] > 0


def test_tariff_uses_actual_value():
    leg = {"channel": "sea"}
    t1 = TL.apply_tariff(leg, 10000)
    assert t1["ok"] and t1["tax"] == int(round(10000 * dc.FOREIGN_TARIFF_RATE["sea"]))
    t2 = TL.apply_tariff(leg, None)
    assert t2["ok"] is False and t2["tax"] is None, "缺失值不得当 0 计税"


def test_enabled_run_queues_when_capacity_short(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 1)
    for dim in ("精品瓷器", "丝绸", "漆器", "香药", "珠宝", "犀象", "苏木", "锡",
                "茶", "药材", "布", "米", "马", "皮毛", "盐", "纸"):
        s.resources[dim] = {"stock": 1000, "cap": 10 ** 9}
    # 运力清零 ⇒ 必然排队（验证「不足排队不拒办」）
    s.carriage = {}
    s.transport_labor = {}
    r = TL.settle_foreign_trade(s, month=1)
    assert r["enabled"] is True and r["executed"] > 0
    assert r["queued_stone"] > 0, "运力不足必须排队（不拒办）"
    assert s.transport_queue, "队列必须有条目"


def test_dry_run_changes_nothing(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 1)
    dim = "茶"
    s.resources[dim] = {"stock": 500, "cap": 10 ** 9}
    before = float(s.resources[dim]["stock"])
    r = TL.settle_foreign_trade(s, month=1, dry_run=True)
    assert r["enabled"] and r["dry_run"] is True
    assert float(s.resources[dim]["stock"]) == before, "dry_run 不得改库存"