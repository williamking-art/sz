# -*- coding: utf-8 -*-
"""M74 治所级影子需求接入**耐用品通道**（口径 = **max**，非相加）—— 定向回归。

裁定：Jev 先 **A 0.953**（接耐用品通道）；合成口径 **乙 0.49998 vs 甲 0.363** ⇒
**实质平手**（乙压在 0.5 阈值下）⇒ 按 AGENTS.md「平手须自论证」，本实现取 **max**，理由：
① `durable_gap` 未配置该维 ⇒ `None` ⇒ **退化为原行为（零行为变化）**；
② 已配置时不会把"流量 + 存量缺口"重复计成双份。

🔴 **测试接缝**：`demand` 只在 **`_cfg(name)`** 里取配置（`from content import data` 后 `getattr`）
⇒ 用例必须 patch **`demand._cfg`**（真实读口），而不是 `content.data` 的属性（本轮先踩过：
patch 属性无效，导致期望值全错）。
另锁两条纪律：① `demand.durable_gap` 对 `held=None` 会**按 0 算**（缺口=全目标，违反缺失≠0）——
本模块**不改他人单点**，改为「持有不可读 ⇒ 该通道不可读」；② 签名是 `durable_gap(dim, size, held)`
（**第一个参数是维**，本轮曾误传阶层 ⇒ 通道恒 None）。
"""

import types

from core.domains.economy import seat_market_shadow as sm


def _patch_cfg(monkeypatch, *, basket=None, durable=None):
    from core.domains.economy import demand as dm
    table = {"BASIC_NEED_BASKET": basket or {}, "DURABLE_TARGET_STOCK": durable or {},
             "SUBSISTENCE_LINE": {}, "SUBSISTENCE_SCALE": 30.0}
    monkeypatch.setattr(dm, "_cfg", lambda name, default=None: table.get(name, default))


def _state(classes):
    st = types.SimpleNamespace()
    st.prefectures = {"路A": {"name": "路A", "seats": {"A|甲": {"pops": dict(classes)}}}}
    st.resources = {}
    return st


def test_durable_channel_raises_demand_to_max(monkeypatch):
    """`绸`：基本需求可读但远小于耐用品缺口 ⇒ 需求取**缺口**（max 的体现，不是相加）。"""
    _patch_cfg(monkeypatch, basket={"绸": 0.01}, durable={"绸": 5.0})
    st = _state({"工匠": {"size": 100, "wealth": 100_000, "goods": {"绸": 0}}})
    row = sm.seat_demand(st, "路A", "A|甲", "绸")["by_class"]["工匠"]
    assert row["channel"] == "basic+durable"
    assert row["basic_effective"] == 0.01 * 100 * 1.0        # 1.0（余量释放 1.0）
    assert row["durable_gap"] == 5.0 * 100 - 0               # 500
    assert row["effective"] == 500.0                        # **max**（相加会是 501）
    assert sm.seat_demand(st, "路A", "A|甲", "绸")["total"] == 500.0


def test_partial_holding_reduces_gap(monkeypatch):
    _patch_cfg(monkeypatch, basket={"绸": 0.01}, durable={"绸": 5.0})
    st = _state({"工匠": {"size": 100, "wealth": 100_000, "goods": {"绸": 400}}})
    row = sm.seat_demand(st, "路A", "A|甲", "绸")["by_class"]["工匠"]
    assert row["durable_gap"] == 100.0                      # 500 − 400，**自限**
    assert row["effective"] == 100.0


def test_unconfigured_durable_degrades_to_basic(monkeypatch):
    """**零行为变化**：耐用品未配置该维 ⇒ 退化为原行为（只算基本需求）。"""
    _patch_cfg(monkeypatch, basket={"布": 0.2}, durable={})
    st = _state({"农": {"size": 50, "wealth": 20_000, "goods": {"布": 0}}})
    row = sm.seat_demand(st, "路A", "A|甲", "布")["by_class"]["农"]
    assert row["durable_gap"] is None and row["channel"] == "basic"
    assert row["effective"] == row["basic_effective"] == 0.2 * 50 * 1.0


def test_unreadable_holding_does_not_inflate_demand(monkeypatch):
    """🔴 纪律：持有**不可读**（无 `goods` 桶）⇒ 耐用品通道不可读，**不得**按 0 算全目标。"""
    _patch_cfg(monkeypatch, basket={}, durable={"绸": 5.0})
    st = _state({"工匠": {"size": 100, "wealth": 100_000}})          # 没有 goods 桶
    rep = sm.seat_demand(st, "路A", "A|甲", "绸")
    assert rep["by_class"]["工匠"]["durable_gap"] is None
    assert rep["total"] is None                                       # 两通道都不可读 ⇒ 不可定义


def test_durable_only_channel_still_yields_demand(monkeypatch):
    """基本需求未配置、耐用品可读 ⇒ 需求**可定义**（走耐用品通道），不因前者缺而整项 None。"""
    _patch_cfg(monkeypatch, basket={}, durable={"绸": 2.0})
    st = _state({"工匠": {"size": 10, "wealth": 50_000, "goods": {"绸": 0}}})
    rep = sm.seat_demand(st, "路A", "A|甲", "绸")
    row = rep["by_class"]["工匠"]
    assert row["channel"] == "durable" and row["effective"] == 20.0
    assert rep["total"] == 20.0 and rep["partial"] is False


def test_partial_flag_when_some_class_unreadable(monkeypatch):
    """**可读部分合计 + `partial` 标记**（照 M52 先例）：某阶层无通道不得污染全所。"""
    _patch_cfg(monkeypatch, basket={}, durable={"绸": 2.0})
    st = _state({"工匠": {"size": 10, "wealth": 50_000, "goods": {"绸": 0}},
                 "农": {"size": 100, "wealth": 0, "goods": {}}})       # 农：两通道皆不可读
    rep = sm.seat_demand(st, "路A", "A|甲", "绸")
    assert rep["total"] == 20.0 and rep["partial"] is True
    assert rep["unreadable_classes"] == ["农"] and rep["readable_classes"] == 1
    assert "不得当作全所需求" in rep["note"]
