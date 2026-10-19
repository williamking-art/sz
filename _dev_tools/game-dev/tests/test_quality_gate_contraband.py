# -*- coding: utf-8 -*-
"""质量放行门 · P7 禁榷（出口禁榷品拦截），2026-10-18。

规则：`CONTRABAND_DIMS` 只禁**出口**；进口不禁；拦截必须留 reason 归因。
走私现状：需商人持有货（P8）才有货可走——现在只拦截并标 `smuggling: pending_p8`，**不凭空造私货**。

本门钉住：
1. 出口禁榷品 ⇒ forbidden + reason `contraband:<dim>`；
2. 出口普通品 ⇒ 放行；
3. **进口**禁榷品 ⇒ 放行（只禁出境）；
4. 结算里禁榷腿被 blocked 且**不动库存**；
5. 普通腿照常成交（不被误伤）；
6. 开关关闭时无变化（P5 回归保护）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

import content.data_constants as dc  # noqa: E402
from core.domains.economy import trade_legs as TL  # noqa: E402


def _state():
    from core.commands import new_game

    return new_game()


def test_contraband_dims_are_all_forbidden_on_export():
    assert dc.CONTRABAND_DIMS, "禁榷清单为空"
    for dim in dc.CONTRABAND_DIMS:
        v = TL.contraband_check({"dim": dim, "direction": "export"})
        assert v["forbidden"] is True, dim
        assert v["reason"] == f"contraband:{dim}"
        assert v["smuggling"] == "pending_p8"


def test_normal_goods_pass():
    for dim in ("茶", "丝绸", "香药"):
        assert TL.contraband_check({"dim": dim, "direction": "export"})["forbidden"] is False


def test_import_of_contraband_is_not_blocked():
    """只禁出境：外邦铜钱/铁进来不管。"""
    v = TL.contraband_check({"dim": "铁", "direction": "import"})
    assert v["forbidden"] is False and v["reason"] is None


def test_settle_blocks_contraband_leg_and_keeps_stock(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 1)
    dim = "官铸铜钱"
    s.resources[dim] = {"stock": 800, "cap": 10 ** 9}
    r = TL.settle_foreign_trade(s, month=1, dry_run=False)
    assert r.get("contraband_blocked", 0) > 0, "重商出口篮里应有禁榷品"
    bad = [x for x in r["rows"] if str(x.get("j", {}).get("reason", "")).startswith("contraband:")]
    assert bad and all(x["direction"] == "export" for x in bad)
    assert float(s.resources[dim]["stock"]) == 800, "禁榷腿不得动库存"


def test_normal_legs_still_execute(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 1)
    # 用**有利润**的出口品（茶对西夏/吐蕃是负毛利，V3 会把路线关停）
    from core.foundation.ledger.material_holding import goods_add, merchant_goods
    goods_add(merchant_goods(s, "两浙路"), "精品瓷器", 5000)
    r = TL.settle_foreign_trade(s, month=1, dry_run=False)
    ok_rows = [x for x in r["rows"] if x.get("j") is None]
    assert ok_rows, "普通货腿必须照常执行"
    from core.foundation.ledger.material_holding import goods_amount
    assert int(goods_amount(merchant_goods(s, "两浙路"), "精品瓷器") or 0) < 5000


def test_switch_off_still_noop(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 0)
    r = TL.settle_foreign_trade(s, month=1)
    assert r["enabled"] is False