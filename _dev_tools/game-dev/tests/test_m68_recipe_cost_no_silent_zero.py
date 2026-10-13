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


def test_grain_feed_only_workshop_never_silently_zero():
    """M68 的契约（**不静默 0**）在 M69 定价后仍成立：无价维要么走**声明的单点**、要么 `None`。

    M69（Jev 甲 0.992）已给 `grain_feed` 指定口径单点 ⇒ 现在应为**数值 + 价源可追**；
    若单点不可读则须 `None`（该分支由 `test_m69_feed_price_basis.py` 锁定）。
    """
    st = _state({"酒坊_路A_1": {"recipe": {"grain_feed": 50000}}})
    rep = wfs.recipe_cost(st, "酒坊_路A_1")
    d = rep["dims"]["grain_feed"]
    if rep["cost"] is None:
        assert "grain_feed" in rep["missing_price"] and d["price"] is None
    else:
        assert rep["cost"] > 0 and d["price"] is not None
        assert d["price_source"], "有价就必须能追到价源（不得凭空出现）"
    assert "不可定义" in (rep["reason"] or "") or rep["cost"] > 0


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


def test_real_new_game_workshops_are_all_priced_after_m69():
    """真实新局：M69 定价后 **107 座全部可算**（此前 80 座粮料作坊被静默算成 0 / 后为 None）。"""
    from core import commands
    s = commands.new_game()
    kinds = {}
    for wid in s.workshops:
        t = wid.split("_")[0]
        kinds.setdefault(t, wfs.recipe_cost(s, wid)["cost"])
    assert all(v is not None for v in kinds.values()), kinds
    need = __import__("core.domains.economy.owner_candidates_shadow",
                      fromlist=["x"]).procure_need(s)
    assert need["value"] is not None and need["unreadable_count"] == 0
