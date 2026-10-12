# -*- coding: utf-8 -*-
"""M41a 市场缺失原因结构化契约 —— 定向回归。

锁定：五分组映射 · 缺失≠0（need/have 不可读留 None）· 未知码如实保留 ·
`from_trade_outcome` 只对"未满足"产 gap · `summarize` 归类计数 ·
**`trade_goods` 既有字段逐字不变**（加性改动，零行为变化）。
"""

from core.domains.economy import market, market_gap as mg


# ------------------------------------------------------------------ 1. 五分组
def test_group_of_maps_five_shortages():
    assert mg.group_of(mg.REASON_NO_MONEY) == "钱"
    assert mg.group_of(mg.REASON_NO_STOCK) == "货"
    assert mg.group_of(mg.REASON_NO_SELLER) == "货"
    assert mg.group_of(mg.REASON_NO_POST) == "岗位"
    assert mg.group_of(mg.REASON_NO_MATERIAL) == "料"
    assert mg.group_of(mg.REASON_STOCK_UNKNOWN) == "料"
    assert mg.group_of(mg.REASON_NOT_ARRIVED) == "运力"
    assert mg.group_of(mg.REASON_BLOCKED) == "运力"
    # 非短缺 ⇒ None
    for c in (mg.REASON_OK, mg.REASON_NO_DEMAND, mg.REASON_INVALID, mg.REASON_DUPLICATE):
        assert mg.group_of(c) is None


def test_reason_codes_cover_market_vocabulary():
    """契约必须**沿用** market 既有词汇（不重命名 ⇒ 零行为变化）。"""
    for c in market.TradeOutcome.ALL:
        assert c in mg.REASON_CODES, c


# ------------------------------------------------------------------ 2. 结构化缺口
def test_gap_shape_and_missing_not_zero():
    g = mg.gap(mg.REASON_NO_MONEY, need=100, have=0, source_id="pop:某路:农")
    assert g["code"] == mg.REASON_NO_MONEY
    assert g["group"] == "钱"
    assert g["need"] == 100 and g["have"] == 0
    assert g["source_id"] == "pop:某路:农"

    g2 = mg.gap(mg.REASON_NO_STOCK)                 # 量不可读
    assert g2["need"] is None and g2["have"] is None   # **缺失≠0**
    assert g2["source_id"] is None                      # 无依据不臆造


def test_gap_keeps_unknown_code():
    g = mg.gap("某个还没登记的原因")
    assert g["code"] == "某个还没登记的原因"            # 如实保留，不猜
    assert g["group"] is None


# ------------------------------------------------------------------ 3. 从成交结果派生
def test_from_trade_outcome_cases():
    assert mg.from_trade_outcome({"reason": "ok", "unmet_qty": 0}) is None
    assert mg.from_trade_outcome({"reason": "no_demand", "unmet_qty": 0}) is None
    assert mg.from_trade_outcome({"reason": "ok", "unmet_qty": 0, "detail": ""}) is None

    g = mg.from_trade_outcome({"reason": "no_stock_local", "unmet_qty": 7})
    assert g["group"] == "货" and g["need"] == 7
    g2 = mg.from_trade_outcome({"reason": "insufficient_purchasing_power",
                                "unmet_qty": 3, "detail": "钱不够"})
    assert g2["group"] == "钱" and g2["note"] == "钱不够"
    assert mg.from_trade_outcome(None) is None


# ------------------------------------------------------------------ 4. 汇总
def test_summarize_groups_and_empty():
    gs = [mg.gap(mg.REASON_NO_MONEY, need=5),
          mg.gap(mg.REASON_NO_STOCK, need=2),
          mg.gap(mg.REASON_NO_STOCK, need=1),
          mg.gap(mg.REASON_BLOCKED, need=9)]
    s = mg.summarize(gs)
    assert s["count"] == 4
    assert s["by_code"][mg.REASON_NO_STOCK] == 2
    assert s["by_group"] == {"钱": 1, "货": 2, "运力": 1}
    assert s["total_need"] == 17.0
    assert set(s["by_group_ordered"]) == set(mg.SHORTAGE_GROUPS)   # 五类总是给全（缺的显示 0）

    e = mg.summarize([])
    assert e["count"] == 0 and e["by_code"] == {} and e["total_need"] == 0.0


# ------------------------------------------------------------------ 5. 加性接入：既有字段不变
def _buyer_seller(wealth=100, stock=10):
    return {"wealth": wealth, "goods": {}}, {"wealth": 0, "goods": {"绸": stock}}


def test_trade_goods_existing_fields_unchanged_and_gap_attached():
    market.reset_trade_ledger()
    b1, s1 = _buyer_seller()
    got = market.trade_goods(None, dim="绸", qty=5, price=10, buyer=b1, seller=s1)

    market.reset_trade_ledger()
    b2, s2 = _buyer_seller()
    core = market._trade_goods_core(None, dim="绸", qty=5, price=10, buyer=b2, seller=s2)

    # 既有字段**逐字不变**（加性改动 ⇒ 零行为变化）
    for k in ("schema_version", "dim", "ok", "traded", "paid", "unmet_qty",
              "reason", "tail_delta", "price"):
        assert got.get(k) == core.get(k), k
    assert b1 == b2 and s1 == s2                      # 钱货转移结果一致
    assert "gap" in got

    # 缺钱场景 ⇒ gap 归"钱"
    market.reset_trade_ledger()
    b3, s3 = _buyer_seller(wealth=15)                  # 只买得起 1 件
    out = market.trade_goods(None, dim="绸", qty=5, price=10, buyer=b3, seller=s3)
    assert out["unmet_qty"] > 0
    assert out["gap"]["group"] == "钱"

    # 缺货场景 ⇒ gap 归"货"
    market.reset_trade_ledger()
    b4, s4 = _buyer_seller(stock=0)
    out2 = market.trade_goods(None, dim="绸", qty=5, price=10, buyer=b4, seller=s4)
    assert out2["gap"]["group"] == "货"

    # 成交 ⇒ 无 gap
    market.reset_trade_ledger()
    b5, s5 = _buyer_seller(stock=10)
    out3 = market.trade_goods(None, dim="绸", qty=3, price=10, buyer=b5, seller=s5)
    assert out3["ok"] and out3["gap"] is None
