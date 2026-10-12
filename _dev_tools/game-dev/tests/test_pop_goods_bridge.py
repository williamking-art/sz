# -*- coding: utf-8 -*-
"""M43/M44 治所级商品写口 —— 定向回归。

锁定：`pop_goods_add` 落**治所真账**并刷镜像（未下沉 ⇒ None）· `pop_goods_decay` 逐治所
按月核销并**返回逐维核销表**（未下沉 ⇒ 空表）· 写后**镜像 == Σ治所**（不再被 sync 覆盖）。
"""

import types

import pytest

from core.foundation.ledger import pop_bridge as pb


def _pdata(seats, name="路A"):
    return {"name": name, "seats": seats,
            "pops": {"工匠": {"size": 0, "goods": {}}}}


# ------------------------------------------------------------------ pop_goods_add
def test_add_writes_seat_truth_and_refreshes_mirror(monkeypatch):
    monkeypatch.setattr(pb, "seat_pop_weights", lambda route: [("A|甲", 1.0), ("A|乙", 3.0)])
    p = _pdata({"A|甲": {"pops": {"工匠": {"goods": {}}}},
                "A|乙": {"pops": {"工匠": {"goods": {}}}}})
    n = pb.pop_goods_add(p, "工匠", "绸", 10)
    assert n == 10
    # 缺省落到**权重最大**的治所
    assert p["seats"]["A|乙"]["pops"]["工匠"]["goods"]["绸"] == 10
    assert "绸" not in p["seats"]["A|甲"]["pops"]["工匠"]["goods"]
    # 镜像已刷新 == Σ治所（**不再需要次月 sync 才一致**）
    assert p["pops"]["工匠"]["goods"]["绸"] == 10


def test_add_honours_explicit_seat_and_accumulates(monkeypatch):
    monkeypatch.setattr(pb, "seat_pop_weights", lambda route: [])
    p = _pdata({"A|甲": {"pops": {"工匠": {"goods": {"绸": 5}}}}})
    assert pb.pop_goods_add(p, "工匠", "绸", 3, seat_id="A|甲") == 8
    assert p["pops"]["工匠"]["goods"]["绸"] == 8


def test_add_returns_none_when_not_sunk(monkeypatch):
    monkeypatch.setattr(pb, "seat_pop_weights", lambda route: [])
    assert pb.pop_goods_add({"name": "路X"}, "工匠", "绸", 1) is None      # 无 seats
    assert pb.pop_goods_add(_pdata({"A|甲": {"pops": {}}}), "工匠", "绸", 1) is None  # 无该类
    assert pb.pop_goods_add(_pdata({"A|甲": {"pops": {"工匠": {}}}}), "工匠", "绸", 0) is None


# ------------------------------------------------------------------ pop_goods_decay
def test_decay_per_seat_and_returns_map():
    p = _pdata({"A|甲": {"pops": {"工匠": {"goods": {"绸": 100, "布": 10}}}},
                "A|乙": {"pops": {"工匠": {"goods": {"绸": 40}}}}})
    got = pb.pop_goods_decay(p, "工匠", 0.05)
    # 逐治所独立取整
    assert p["seats"]["A|甲"]["pops"]["工匠"]["goods"]["绸"] == 95
    assert p["seats"]["A|乙"]["pops"]["工匠"]["goods"]["绸"] == 38
    assert got["绸"] == (100 - 95) + (40 - 38)
    assert got["布"] == 1
    # 镜像同步
    assert p["pops"]["工匠"]["goods"]["绸"] == 95 + 38


def test_decay_empty_when_not_sunk_or_no_goods():
    assert pb.pop_goods_decay({"name": "路X"}, "工匠", 0.05) == {}          # 无 seats
    p = _pdata({"A|甲": {"pops": {"工匠": {}}}})
    assert pb.pop_goods_decay(p, "工匠", 0.05) == {}                        # 无 goods


def test_decay_is_idempotent_per_call_shape():
    p = _pdata({"A|甲": {"pops": {"工匠": {"goods": {"绸": 100}}}}})
    pb.pop_goods_decay(p, "工匠", 0.05)
    pb.pop_goods_decay(p, "工匠", 0.05)
    # 第二次在 95 的基础上再核销 ⇒ 单调下降（不是幂等，是"每月一次"的累积语义）
    assert p["seats"]["A|甲"]["pops"]["工匠"]["goods"]["绸"] == 90
    assert p["pops"]["工匠"]["goods"]["绸"] == 90
