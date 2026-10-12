# -*- coding: utf-8 -*-
"""M41c 逐月 Δ 与残差 —— 定向回归（纯函数）。

锁定：逐保管方/逐维差额 · 可加三方的 net（**不含待定**）· 任一侧不可读 ⇒ None（缺失≠0）·
**`flows` 未提供 ⇒ 该维 residual=None 并进 unclosed**（**不把"没有账"当"残差 0"**）·
残差为 0 的判定与 tol。
"""

from core.domains.economy import stock_identity as si


def _snap(pop=None, res=None, tr=None, pend=None, readable=True):
    return {"schema_version": si.SCHEMA_VERSION,
            "by_custody": {"pop_goods": pop, "national_resources": res,
                           "in_transit": tr, "pending_stock": pend},
            "all_readable": readable}


# ------------------------------------------------------------------ 1. Δ
def test_delta_per_custody_and_net_excludes_pending():
    prev = _snap(pop={"木": 10.0}, res={"木": 100.0}, tr={}, pend={"木": 5.0})
    curr = _snap(pop={"木": 14.0}, res={"木": 120.0}, tr={"木": 3.0}, pend={"木": 9.0})
    d = si.stock_delta(prev, curr)
    assert d["by_custody"]["pop_goods"]["木"] == 4.0
    assert d["by_custody"]["national_resources"]["木"] == 20.0
    assert d["by_custody"]["in_transit"]["木"] == 3.0
    assert d["by_custody"]["pending_stock"]["木"] == 4.0          # 单列（便于发现待定池变动）
    assert d["net"]["木"] == 27.0                                 # 4 + 20 + 3（**不含**待定 4）
    assert d["all_readable"] is True


def test_delta_none_when_side_unreadable():
    prev = _snap(pop={"木": 1.0}, res=None, tr={})
    curr = _snap(pop={"木": 2.0}, res={"木": 1.0}, tr={})
    d = si.stock_delta(prev, curr)
    assert d["all_readable"] is False
    assert d["net"]["木"] is None                                 # 缺失≠0
    assert d["by_custody"]["national_resources"]["木"] is None
    assert si.stock_delta(None, curr)["net"] == {}


# ------------------------------------------------------------------ 2. 残差
def test_residual_with_flows_closes():
    prev = _snap(pop={"木": 0.0}, res={"木": 0.0}, tr={})
    curr = _snap(pop={"木": 7.0}, res={"木": 0.0}, tr={})
    rep = si.residual_report(prev, curr, flows={"木": 7.0})
    assert rep["residual"]["木"] == 0.0
    assert rep["nonzero"] == [] and rep["unclosed"] == []
    assert rep["ok"] is True


def test_residual_without_flows_is_unclosed_not_zero():
    prev = _snap(pop={"木": 0.0}, res={"木": 0.0}, tr={})
    curr = _snap(pop={"木": 7.0}, res={"木": 0.0}, tr={})
    rep = si.residual_report(prev, curr)                          # 不提供流量账
    assert rep["flows_provided"] is False
    assert rep["residual"]["木"] is None
    assert rep["unclosed"] == ["木"]
    assert rep["ok"] is False                                     # **不能**当成"恒等式成立"


def test_residual_flags_nonzero():
    prev = _snap(pop={"木": 0.0}, res={"木": 0.0}, tr={})
    curr = _snap(pop={"木": 10.0}, res={"木": 0.0}, tr={})
    rep = si.residual_report(prev, curr, flows={"木": 6.0})
    assert rep["residual"]["木"] == 4.0
    assert rep["nonzero"] == ["木"] and rep["ok"] is False


def test_residual_tolerates_float_noise():
    prev = _snap(pop={"木": 0.0}, res={"木": 0.0}, tr={})
    curr = _snap(pop={"木": 1.0000001}, res={"木": 0.0}, tr={})
    rep = si.residual_report(prev, curr, flows={"木": 1.0})
    assert rep["nonzero"] == []                                   # 容差内视为闭合
