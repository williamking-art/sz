# -*- coding: utf-8 -*-
"""M68 `recipe_cost` 静默 0 缺陷修复 —— 定向回归。

背景：原实现 `if dim in ("grain_feed", "ration_weight"): continue` ⇒ 酒坊/畜栏
（配方**只有** `grain_feed`）走到 `total=0, ok=True` ⇒ **静默返回 0**（与其 docstring
「缺价维 ⇒ None」矛盾，违反 §3-3 缺失≠0）。实测把 **80 座**作坊需求算成 0。
现按 Jev **甲 0.892**：有量的维一律登记，**无基准价 ⇒ 整项 `cost=None` + `missing_price` 列出**。
"""

from core.domains.economy import workshop_fund_shadow as wfs


def _state(workshops):
    import types
    st = types.SimpleNamespace()
    st.workshops = workshops
    st.prefectures = {}
    return st


def test_grain_feed_only_workshop_is_undefined_not_zero():
    st = _state({"酒坊_路A_1": {"recipe": {"grain_feed": 50000}}})
    rep = wfs.recipe_cost(st, "酒坊_路A_1")
    assert rep["cost"] is None, "无粮基准价单点 ⇒ 采购预算**不可定义**（不得静默 0）"
    assert "grain_feed" in rep["missing_price"]
    assert rep["dims"]["grain_feed"] == {"qty": 50000.0, "price": None, "value": None}
    assert "缺失≠0" in rep["reason"] or "不可定义" in rep["reason"]


def test_priced_recipe_still_computes():
    st = _state({"麻坊_路A_1": {"recipe": {"麻": 10000}}})
    rep = wfs.recipe_cost(st, "麻坊_路A_1")
    assert isinstance(rep["cost"], int) and rep["cost"] > 0
    assert rep["missing_price"] == []


def test_ration_weight_is_not_a_material():
    st = _state({"工坊_路A_1": {"recipe": {"麻": 10000, "ration_weight": 0.5}}})
    rep = wfs.recipe_cost(st, "工坊_路A_1")
    assert rep["cost"] is not None and rep["missing_price"] == []   # 权重维**不算缺价**
    assert "ration_weight" not in rep["dims"]


def test_real_new_game_jiufang_and_chulan_are_undefined():
    """真实新局：酒坊/畜栏（各 40 座）**必须**是 `cost=None`（此前被静默算成 0）。"""
    from core import commands
    s = commands.new_game()
    kinds = {}
    for wid in s.workshops:
        t = wid.split("_")[0]
        kinds.setdefault(t, wfs.recipe_cost(s, wid)["cost"])
    assert kinds["酒坊"] is None and kinds["畜栏"] is None
    assert isinstance(kinds["麻坊"], int) and isinstance(kinds["丝坊"], int)
    # 下游 M58 `procure_need` 必须如实变"不可定义"（而不是漏算 80 座后给个偏小的数）
    need = __import__("core.domains.economy.owner_candidates_shadow",
                      fromlist=["x"]).procure_need(s)
    assert need["value"] is None and need["unreadable_count"] == 80
