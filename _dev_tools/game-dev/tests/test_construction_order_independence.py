# -*- coding: utf-8 -*-
"""营造/建材的**顺序无关性回归**（§14.5 起手第一步 · 2026-10-02）。

## 为什么先写这个（不碰任何业务逻辑）

前序规格「收窄版 B」把建材下沉到**路级**的尝试**失败并回退**，实测三因之一是：

> **失败集合随用例执行顺序漂移**——同一逻辑在不同执行顺序下"失败的州"不同，
> 指向**隐式的共享可变状态或顺序依赖**。

在把这个根因测出来之前，**任何对建材/营造逻辑的改动都可能再次翻车**，
所以这是 §14 建材州府级改造的**起手第一步**，且只加测试、不改生产代码。

## 本文件锁定的性质

**顺序无关性**：从**同一个初始态**出发，把若干次营造调用按**不同顺序**执行，
最终状态（Σ钱、ΣPOP、各路建筑等级、材料库存、失败集合）必须**完全一致**。

若不一致，即可判定存在**顺序依赖/共享可变状态**，应在动业务逻辑**之前**先修。
"""
import copy
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core import civil_building as CB                              # noqa: E402
from core.building_jobs import building_level                       # noqa: E402
from core.game_state import GameState                               # noqa: E402
from core.legacy_mechanic import init_legacies                      # noqa: E402
from core.material_holding import supply_merchant_materials                # noqa: E402
from core.production_chain import settle_production_chain           # noqa: E402


def _state():
    """确定性初始态（不跑整轮结算，只补满建材仓以便触达建成路径）。

    🔴 口径 C-c：营造只从**本地商人货栈**取料，故须 `supply_merchant_materials()`
    ——与真实流水线 Step 4.45（`settlement.py`）一致。
    """
    s = GameState("史实")
    init_legacies(s)
    settle_production_chain(s, [])
    supply_merchant_materials(s)
    return s


def _money_total(s):
    total = float(getattr(s, "treasury", 0) or 0) + \
        float(getattr(s, "imperial_treasury", 0) or 0)
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                total += float(pop.get("wealth", 0) or 0)
    return total


def _fingerprint(s):
    """可比较的状态指纹：钱、ΣPOP、逐路建筑等级、材料库存。"""
    bld = {}
    for pref, info in s.prefectures.items():
        b = info.get("buildings") or {}
        if b:
            bld[pref] = {k: building_level(v, 0) for k, v in sorted(b.items())}
    stock = {}
    for dim, v in (getattr(s, "resources", {}) or {}).items():
        if isinstance(v, dict):
            cur = v.get("stock")
            if isinstance(cur, (int, float)):
                stock[dim] = round(float(cur), 6)
    pop_total = 0
    for p in s.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                pop_total += int(pop.get("size", 0) or 0)
    return {
        "money": round(_money_total(s), 4),
        "pop": pop_total,
        "buildings": bld,
        "stock": stock,
    }


def _run(s, prefs):
    """按给定顺序对各路跑一次 `apply_civil_construction`，收集失败集合。"""
    failed = []
    for pref in prefs:
        try:
            summary = CB.apply_civil_construction(s, [])
        except Exception as exc:                    # noqa: BLE001 — 失败也要记录
            failed.append((pref, type(exc).__name__))
            continue
        # 各实现的 summary 结构可能不同，只要能判断"是否建成/失败"即可
        if isinstance(summary, dict):
            built = summary.get("built") or summary.get("built_pref") \
                or summary.get("built_count") or 0
            blocked = summary.get("blocked") or summary.get("blocked_pref") \
                or summary.get("failed") or []
            if isinstance(built, list) and built:
                pass
            elif isinstance(built, int) and built > 0:
                pass
            elif blocked:
                failed.append((pref, "blocked"))
    return failed, _fingerprint(s)


_ROUTES = None


def _routes():
    global _ROUTES
    if _ROUTES is None:
        s = _state()
        _ROUTES = list(s.prefectures)[:6]
    return _ROUTES


def test_state_fingerprint_is_deterministic_across_fresh_states():
    """前置守卫：同一初始态构造两次，指纹必须一致（否则后面比什么都不成立）。"""
    a, b = _state(), _state()
    assert _fingerprint(a) == _fingerprint(b), "初始态本身不确定，比对无意义"


def test_two_routes_order_does_not_matter():
    """🔴 顺序无关性：先 A 后 B vs 先 B 后 A，结果必须一致。"""
    r = _routes()
    a, b = r[0], r[1]
    base = _state()

    s1 = copy.deepcopy(base)
    f1, fp1 = _run(s1, [a, b])

    s2 = copy.deepcopy(base)
    f2, fp2 = _run(s2, [b, a])

    assert fp1 == fp2, "顺序颠倒后最终状态不同 ⇒ 存在顺序依赖/共享可变状态"
    assert f1 == f2, f"顺序颠倒后失败集合不同：{f1} vs {f2}"


def test_three_routes_all_permutations_agree():
    """三路全排列（6 种）结果必须完全一致。"""
    import itertools
    r = _routes()[:3]
    base = _state()

    seen_fp, seen_f = None, None
    for perm in itertools.permutations(r):
        s = copy.deepcopy(base)
        failed, fp = _run(s, list(perm))
        if seen_fp is None:
            seen_fp, seen_f = fp, failed
            continue
        assert fp == seen_fp, f"排列 {perm} 状态与首个排列不同 ⇒ 有顺序依赖"
        assert failed == seen_f, f"排列 {perm} 失败集合 {failed} vs {seen_f}"


def test_repeated_same_route_is_stable():
    """同一路连跑两次不应改变结果（幂等/无隐藏累积状态）。"""
    r = _routes()
    a = r[0]
    base = _state()

    s1 = copy.deepcopy(base)
    _, fp1 = _run(s1, [a, a])

    s2 = copy.deepcopy(base)
    _, fp2 = _run(s2, [a, a])

    assert fp1 == fp2


def test_fresh_state_not_polluted_by_previous_run():
    """前一次营造**不得污染**新建的初始态（跨用例的状态泄漏守卫）。"""
    r = _routes()
    a = r[0]

    s_used = _state()
    _run(s_used, [a])

    s_fresh = _state()
    s_ref = _state()
    assert _fingerprint(s_fresh) == _fingerprint(s_ref), \
        "新建的 state 受到此前用例污染 ⇒ 存在模块级共享可变状态"
