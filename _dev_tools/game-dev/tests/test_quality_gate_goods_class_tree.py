# -*- coding: utf-8 -*-
"""质量放行门 · 商品类目层级制（2026-10-18 用户指出 + Jev 裁定 B 0.993）。

用户：「但粮不是食品的子集吗」——此前「平铺互斥」的说法作废，改为**类目层级**：
食品 ⊃ 粮 ⊃ {米, 麦, 面}。

本门钉住：
1. 层级自检干净（无环、parent/children 互指一致、成员不跨类目重复）；
2. 递归合计正确：食品(递归) = 粮 + 非粮食品；父子**不得同时相加**；
3. 库存只落维：类目名不得出现在库存键；聚合类目不可写；
4. 反例自证：注入成环/父子不一致必须被检出。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger import goods_class as gc  # noqa: E402


def test_tree_is_clean():
    issues = gc.assert_tree()
    assert not issues, "类目层级自检失败：\n" + "\n".join(issues)


def test_grain_is_subset_of_food():
    assert gc.parent("粮") == "食品", "粮的父类目必须是食品"
    food = set(gc.members_deep("食品"))
    grain = set(gc.members("粮"))
    assert grain and grain <= food, "粮成员必须全部包含在食品（递归）内"


def test_recursive_total_equals_children_plus_own():
    goods = {"米": 10, "麦": 5, "面": 3, "糖": 2, "meat": 7}
    food = gc.class_total_deep(goods, "食品")
    grain = gc.class_total(goods, "粮")
    own = sum(v for k, v in goods.items() if k in gc.members("食品"))
    assert food == (grain or 0) + own, f"食品递归合计应 = 粮 + 非粮食品：{food} vs {grain}/{own}"


def test_parent_and_child_must_not_be_summed_together():
    goods = {"米": 10}
    food = gc.class_total_deep(goods, "食品")
    grain = gc.class_total(goods, "粮")
    assert food == grain == 10
    assert food + grain == 20, "父子相加必然双计（本断言即『禁止同加』的证据）"


def test_aggregation_class_is_readonly():
    assert gc.is_writable("粮") is True, "粮可写（成员是具体维）"
    assert gc.is_writable("食品") is False, "食品是聚合类目，只读"
    assert gc.class_add({}, "食品", 10) is None, "聚合类目不得接受库存写入"


def test_class_names_not_in_stock_keys_helper():
    assert gc.assert_no_class_in_keys({"米": 1}) == []
    assert gc.assert_no_class_in_keys({"食品": 1, "米": 1}) == ["食品"]


def test_assert_tree_detects_cycle(monkeypatch):
    bad = {
        "A": {"kind": "类目", "parent": "B", "children": [], "members": ["x"]},
        "B": {"kind": "类目", "parent": "A", "children": [], "members": ["y"]},
    }
    monkeypatch.setattr(gc, "_classes", lambda: bad)
    issues = gc.assert_tree()
    assert any("成环" in i for i in issues), issues


def test_assert_tree_detects_parent_child_mismatch(monkeypatch):
    bad = {
        "P": {"kind": "类目", "parent": None, "children": ["C"], "members": []},
        "C": {"kind": "类目", "parent": None, "children": [], "members": ["x"]},
    }
    monkeypatch.setattr(gc, "_classes", lambda: bad)
    issues = gc.assert_tree()
    assert any("父子不一致" in i for i in issues), issues