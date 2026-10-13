# -*- coding: utf-8 -*-
"""M69 粮料基准价口径（**粮料即粮**，复用既有粮价单点）—— 定向回归。

裁定：Jev **甲 0.992**——`grain_feed` 的基准价引用 `song_job_cfg()['grain_price0']`
（与 M52 家计影子同源；`MATERIAL_PRICE_BASE` 无粮维）。**只用于读数**。
"""

from core.domains.economy import workshop_fund_shadow as wfs


def _state(workshops):
    import types
    st = types.SimpleNamespace()
    st.workshops = workshops
    st.prefectures = {}
    return st


def test_feed_price_comes_from_existing_single_point():
    p = wfs.feed_price()
    assert p is not None and p > 0
    # **同源单点**：`grain_price0` 是按政权分档的 dict ⇒ 取本政权档（宋无专档 ⇒ default=1.6），
    # **不是**把它求和（M70 修的正是这个 3.6× 缺陷）
    from core.building_jobs import song_job_cfg
    assert p == song_job_cfg()["grain_price0"]["default"] == 1.6
    from core.domains.economy.livelihood_shadow import grain_base_price
    assert p == grain_base_price()                      # 与家计侧**同一单点**


def test_grain_feed_only_workshop_now_priced_with_source():
    st = _state({"酒坊_路A_1": {"recipe": {"grain_feed": 50000}}})
    rep = wfs.recipe_cost(st, "酒坊_路A_1")
    assert isinstance(rep["cost"], int) and rep["cost"] > 0
    assert rep["missing_price"] == []                    # 已可定价 ⇒ 不再缺价
    d = rep["dims"]["grain_feed"]
    assert d["price"] == wfs.feed_price()
    assert d["price_source"] == "core.building_jobs.song_job_cfg()['grain_price0']"   # **口径可追**
    assert d["value"] == round(50000 * d["price"], 4)


def test_missing_single_point_still_yields_none(monkeypatch):
    """单点不可读 ⇒ 仍 `None`（**缺失≠0**，不得回落 0）。"""
    monkeypatch.setattr(wfs, "feed_price", lambda state=None: None)
    st = _state({"酒坊_路A_1": {"recipe": {"grain_feed": 50000}}})
    rep = wfs.recipe_cost(st, "酒坊_路A_1")
    assert rep["cost"] is None and rep["missing_price"] == ["grain_feed"]


def test_real_game_all_workshops_now_priced():
    from core import commands
    s = commands.new_game()
    kinds = {}
    for wid in s.workshops:
        kinds.setdefault(wid.split("_")[0], wfs.recipe_cost(s, wid))
    assert all(r["cost"] is not None for r in kinds.values()), kinds
    from core.domains.economy import owner_candidates_shadow as ocs
    need = ocs.procure_need(s)
    assert need["value"] is not None and need["unreadable_count"] == 0   # 80 座不再"不可读"
