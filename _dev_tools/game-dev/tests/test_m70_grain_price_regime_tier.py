# -*- coding: utf-8 -*-
"""M70 粮价单点「按政权求和」缺陷修复 —— 定向回归。

🔴 原实现 `_grain_base_price()` 用 `_flatten_sum` 解析**按政权分档**的
`song_job_cfg()["grain_price0"]` ⇒ 返回 **5.8 = 2.2+2.0+1.6**（三档之和），误差 **3.6×**。
现按 Jev **甲 0.996** 修为：**取本政权档**（无专档 ⇒ `default`）并**提升为公开单点**
`grain_base_price(regime=None)`，`workshop_fund_shadow.feed_price` 复用同一单点。
"""

from core.domains.economy import livelihood_shadow as ls
from core.domains.economy import workshop_fund_shadow as wfs


def test_grain_price_is_regime_tier_not_sum():
    v = ls.grain_base_price()
    assert v == 1.6, f"宋（无专档 ⇒ default）应为 1.6，实际 {v}（求和缺陷会得 5.8）"
    assert v != 5.8


def test_regime_tiers_resolve():
    assert ls.grain_base_price("游牧帝国") == 2.2
    assert ls.grain_base_price("党项蕃国") == 2.0
    assert ls.grain_base_price("西南属国") == 1.6      # 无该档 ⇒ default
    assert ls.grain_base_price("宋") == 1.6


def test_backward_compat_alias_still_works():
    assert ls._grain_base_price() == ls.grain_base_price()


def test_feed_price_reuses_the_same_single_point():
    assert wfs.feed_price() == ls.grain_base_price() == 1.6


def test_scalar_shaped_config_is_tolerated(monkeypatch):
    """兼容标量写法（将来若把该键改成裸数）。"""
    monkeypatch.setattr(ls, "_num", ls._num)             # 保持原样，仅确保不炸
    import core.building_jobs as bj
    real = bj.song_job_cfg()

    def fake():
        cfg = dict(real)
        cfg["grain_price0"] = 1.25
        return cfg
    monkeypatch.setattr(bj, "song_job_cfg", fake)
    assert ls.grain_base_price() == 1.25


def test_missing_tier_returns_none_not_zero(monkeypatch):
    import core.building_jobs as bj
    real = bj.song_job_cfg()

    def fake():
        cfg = dict(real)
        cfg["grain_price0"] = {"游牧帝国": 2.2}          # 无 default / 宋
        return cfg
    monkeypatch.setattr(bj, "song_job_cfg", fake)
    assert ls.grain_base_price() is None                 # **缺失≠0**，绝不求和、不回落 0
