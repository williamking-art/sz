# -*- coding: utf-8 -*-
"""质量放行门 · 商品属性 kind 与加工链（G-3 P0）。

用户 2026-10-18 裁定：「粮仓就是粮的仓库，不管是米面麦，还是红薯、玉米，都应该能存」。
⇒ 粮是**属性**（COMMODITY_KINDS），不是固定成员名单；面是**中间产物**（PROCESS_CHAINS）。

本门钉住：
1. 目录覆盖：GOODS_DIMS 每维都必须有 kind（未登记 = 门红，而不是静默当非粮）；
2. 属性一致：is_grain ⇔ kind==粮 ⇔ 类目成员（单一真源，不许两套名单）；
3. 中间产物：面 kind=粮 但未立商品维，且必须登记加工链；rate 未核定时为 None；
4. 链引用：链条引用的输入/产出维都必须已登记；
5. 派生读口：grain_of == Σ(所有 kind=粮 的维)，与类目合计一致；
6. 注入即红：未登记维不得被当成粮。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_constants import GOODS_CLASSES, GOODS_DIMS, GRAIN_CLASS  # noqa: E402
from core.foundation.ledger import goods_class as gc  # noqa: E402
from core.foundation.ledger import goods_kind as gk  # noqa: E402


def test_every_goods_dim_has_kind():
    """目录覆盖：GOODS_DIMS 每维都必须有 kind（新增商品忘了登记属性 ⇒ 红）。"""
    missing = gk.assert_kinds_cover_dims()
    assert not missing, f"这些商品维没有登记 kind：{missing}"


def test_kind_and_class_are_single_source():
    """属性与类目必须同源：is_grain 为真的维 == 粮类目成员。"""
    by_kind = sorted(d for d in gk._kinds() if gk.is_grain(d))
    by_class = sorted(gc.members(GRAIN_CLASS))
    assert by_kind == by_class, f"两套名单不一致：属性={by_kind} 类目={by_class}"


def test_intermediate_goods_is_grain_but_not_active():
    """面：属粮（能进粮仓），但未立商品维（还没有产线）；且必须在加工链上。"""
    assert gk.is_grain("面"), "面应属粮（粮仓要能存它）"
    assert not gc.is_active("面"), "面当前未立商品维，is_active 应为 False"
    assert "面" not in GOODS_DIMS, "面一旦立维，本用例需要按新口径更新"
    chain = gk.chain_of("面")
    assert chain, "面是中间产物，必须登记加工链"
    assert gk.chain_inputs("面"), "加工链缺输入（麦）"
    assert gk.chain_rate("面") is None, "无史料依据时 rate 必须为 None（禁止隐式换算）"


def test_chain_references_are_registered():
    """链条引用的输入/产出维都必须已登记 kind。"""
    issues = gk.assert_chain_refs_known()
    assert not issues, f"加工链引用问题：{issues}"


def test_grain_of_equals_sum_of_grain_kinds():
    """派生读口：grain_of == Σ(kind=粮 的维)，包含「面」这类未立维但已写入的值。"""
    from core.foundation.ledger.grain_ledger import grain_of

    dims = [d for d in gk._kinds() if gk.is_grain(d)]
    assert dims, "没有任何粮维 ⇒ 门是空转"
    for i, d in enumerate(dims):
        goods = {d: 10 + i}
        assert grain_of({"goods": goods}) == 10 + i, f"dim={d}"
    mixed = {d: 1 for d in dims}
    assert grain_of({"goods": mixed}) == len(dims)
    assert grain_of({"goods": {}}) is None, "无粮库存时应为 None（缺失≠0）"


def test_non_grain_dims_are_not_counted():
    """反例（注入即红）：盐/铁/木 不得被算进粮。"""
    from core.foundation.ledger.grain_ledger import grain_of

    for d in ("盐", "铁", "木", "布"):
        assert not gk.is_grain(d), f"{d} 不该是粮"
        assert grain_of({"goods": {d: 99}}) is None, f"{d} 被算进粮了"


def test_unknown_dim_is_not_grain():
    """未登记维**不是粮**（缺失 ≠ 默认是粮），并且必须能被门发现。"""
    assert gk.kind_of("红薯") is None, "明清作物未登记，kind 应为 None"
    assert not gk.is_grain("红薯")
    fake = dict(gk._kinds())
    fake.pop("米", None)
    orig = gk._kinds
    try:
        gk._kinds = lambda: fake  # type: ignore[assignment]
        assert "米" in gk.assert_kinds_cover_dims(), "缺 kind 的维必须被覆盖检测抓到"
    finally:
        gk._kinds = orig  # type: ignore[assignment]