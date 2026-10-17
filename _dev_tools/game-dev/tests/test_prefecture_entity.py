# -*- coding: utf-8 -*-
"""州府实体层定向回归（P0/A2 · 2026-10-02）。

守三件事：
1. **实体完整性**：137 治所 / 21 路，身份字段齐、有块者有数值、归入席**无值≠0**；
2. **恒等式**：`Σ(有块州府) + 路级 residual == 路级总量`（逐路逐维精确）；
3. **精度如实声明**：无锚点席必须标 `area_only`，覆盖率报告须点出"面积估计"边界
   （设计文档 §4.2 禁止按面积随意拆分，故不得把估计值当史料值）。
"""
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from content.data import PREFECTURE_INFO, PREFECTURE_LIST          # noqa: E402
from content.data_prefecture_demog import (                        # noqa: E402
    PREFECTURE_RESIDUAL, PREFECTURE_SEAT_COUNT, PREFECTURE_SEATS, SEAT_TO_CIRCUIT,
)
from content.demography import EXTRA_CIRCUIT_DEMOG, SONG_SEAT_WEIGHTS  # noqa: E402
from core import prefecture_entity as PE                           # noqa: E402

_DIMS = ("population", "households", "land", "grain", "monthly_tax")
#: 21 路 = 20 个经济路（`PREFECTURE_INFO`）＋ 非经济路（`EXTRA_CIRCUIT_DEMOG`，如黔中路）
_KNOWN_CIRCUITS = set(PREFECTURE_INFO) | set(EXTRA_CIRCUIT_DEMOG)


# ====================================================== 1 · 实体完整性
def test_seat_count_is_136_across_21_circuits():
    """136 席 / 21 路（2026-10-02 删除 `颍昌府` 在京畿路的**重复点**后，137→136）。"""
    seats = PE.all_seats()
    assert len(seats) == 136, f"治所应 136，实得 {len(seats)}"
    assert len({s["circuit"] for s in seats}) == 21
    assert PREFECTURE_SEAT_COUNT["seats"] == 136
    assert PREFECTURE_SEAT_COUNT["blocked"] + PREFECTURE_SEAT_COUNT["merged"] == 136


def test_every_song_circuit_has_seats():
    """20 个经济路都必须有下辖治所（否则该路无从下沉）。"""
    for c in PREFECTURE_LIST:
        assert PE.seats_of(c), f"{c} 无下辖治所"


def test_seat_identity_fields_present():
    for s in PE.all_seats():
        assert s["seat"], "治所名不可为空"
        assert s["circuit"] in _KNOWN_CIRCUITS, \
            f"{s['seat']} 的路 {s['circuit']} 不在已知 21 路"
        assert s["level"] in PE.SEAT_LEVELS, f"{s['seat']} 等级非法：{s['level']}"
        assert s["lon"] is not None and s["lat"] is not None, f"{s['seat']} 缺经纬"


def test_main_key_and_display_name_are_both_unique_after_dedup():
    """**主键与显示名都唯一**——这是删除 `颍昌府` 重复点后的**回归守卫**：

    一旦有人再往两条路里登记同名（且坐标相同的）治所，本用例即失败。
    背景：`颍昌府 (113.85,34.04)` 曾在京畿/京西**各登一次、坐标全等** ⇒
    同一地图府块被两条路各算一次（地理双计）；用户 2026-10-02 裁定删除重复点。
    """
    seats = PE.all_seats()
    ids = [s["seat_id"] for s in seats]
    names = [s["seat"] for s in seats]
    assert len(set(ids)) == len(seats), "主键必须唯一"
    assert len(set(names)) == len(seats), \
        f"显示名必须唯一，重名：{PE.duplicate_display_names()}"
    assert PE.duplicate_display_names() == {}, "不应再有跨路重名治所"
    # 坐标也不应两条路完全相同（重复点的直接特征）
    coords = [(s["lon"], s["lat"]) for s in seats]
    assert len(set(coords)) == len(seats), "存在坐标完全相同的两条治所（疑重复点）"


def test_display_name_is_not_accepted_as_key():
    """**主键必须是限定名 `路|治所`**：传裸显示名一律返回 `None`（不猜、不做模糊匹配）。"""
    for s in PE.all_seats()[:5]:
        assert PE.seat_entity(s["seat"]) is None
        assert PE.circuit_of(s["seat"]) is None
        assert PE.prefecture_demog(s["seat"]) is None
        # 限定名可用
        assert PE.seat_entity(s["seat_id"]) is not None


def test_blocked_seats_have_demog_and_merged_seats_do_not():
    """有块者必须有数值；省级归入席必须 `demog is None`（**不是 0**）。"""
    for s in PE.all_seats():
        if s["blocked"]:
            assert isinstance(s["demog"], dict), f"{s['seat']} 有块却无数值"
            assert s["demog"].get("population"), f"{s['seat']} 人口缺失"
        else:
            assert s["demog"] is None, f"{s['seat']} 归入席不得有数值"
            assert s["basis"] == PE.BASIS_MERGED


def test_unknown_seat_is_none_not_zero():
    """缺失 ≠ 0：未知治所一律 `None`。"""
    assert PE.seat_entity("不存在的府") is None
    assert PE.prefecture_demog("不存在的府") is None
    assert PE.circuit_of("不存在的府") is None
    assert PE.seats_of("不存在的路") == []
    assert PE.circuit_aggregate("不存在的路") is None


# ====================================================== 2 · 恒等式
@pytest.mark.parametrize("circuit", PREFECTURE_LIST)
def test_identity_children_plus_residual_equals_route(circuit):
    """`Σ(有块州府) + residual == 路级总量`（逐维）。"""
    base = PREFECTURE_INFO[circuit]
    rows = PREFECTURE_SEATS.get(circuit) or []
    if not rows:
        pytest.skip(f"{circuit} 无治所表")
    res = PREFECTURE_RESIDUAL.get(circuit) or {}
    for dim in _DIMS:
        pv = base.get(dim)
        if pv is None:
            continue
        got = sum(int(r.get(dim, 0) or 0) for r in rows if r.get("blocked")) \
            + int(res.get(dim, 0) or 0)
        assert abs(got - int(pv)) <= 1, f"{circuit}/{dim}: Σ{got} vs 父级 {pv}"


@pytest.mark.parametrize("circuit", PREFECTURE_LIST)
def test_circuit_aggregate_asserts_against_route(circuit):
    """`circuit_aggregate` 现算并与路级断言一致（路级不得成为第二份真账）。"""
    for dim in _DIMS:
        if PREFECTURE_INFO[circuit].get(dim) is None:
            continue
        assert PE.circuit_aggregate(circuit, dim) == int(PREFECTURE_INFO[circuit][dim])


def test_yields_identity():
    for circuit, base in PREFECTURE_INFO.items():
        rows = PREFECTURE_SEATS.get(circuit) or []
        if not rows:
            continue
        res = (PREFECTURE_RESIDUAL.get(circuit) or {}).get("yields") or {}
        for k, v in (base.get("yields") or {}).items():
            got = sum((r.get("yields") or {}).get(k, 0) or 0
                      for r in rows if r.get("blocked")) + int(res.get(k, 0) or 0)
            assert abs(got - int(v)) <= 1, f"{circuit}/yields.{k}: Σ{got} vs {v}"


# ====================================================== 3 · 精度如实声明
def test_basis_reflects_source_of_numbers():
    """`basis` 由**生成表单一来源**给出；四态取值合法，且史料席必须真有史料。

    ⚠️ 关键守卫：**未录史料的席不得被标成 `historical`**（否则面积估计会伪装成史料值）。
    """
    from content.data_households_hist import hist_households_of
    ok = {PE.BASIS_HISTORICAL, PE.BASIS_AREA_ANCHOR, PE.BASIS_AREA_ONLY, PE.BASIS_MERGED}
    for s in PE.all_seats():
        assert s["basis"] in ok, f"{s['seat']} basis 非法：{s['basis']}"
    # 标 historical 的席，**必须**在史料表里有崇宁户
    for s in PE.all_seats():
        if s["basis"] == PE.BASIS_HISTORICAL:
            assert hist_households_of(s["seat"]), \
                f"{s['seat']} 标了 historical 却无史料——不得伪装"
    # 回退到面积法的席：**有锚点须标 area_x_anchor，无锚点须标 area_only**（不得含糊）
    anchors = set(SONG_SEAT_WEIGHTS)
    for s in PE.all_seats():
        if not s["blocked"] or s["basis"] == PE.BASIS_HISTORICAL:
            continue
        expect = PE.BASIS_AREA_ANCHOR if s["seat"] in anchors else PE.BASIS_AREA_ONLY
        assert s["basis"] == expect, f"{s['seat']} basis 应为 {expect}"


def test_no_objection_marks_estimate_as_historical():
    """反向守卫：有史料但**该路席位不齐**时不得标 historical（混用两种口径）。"""
    from content.data_prefecture_demog import PREFECTURE_SEATS
    from content.data_households_hist import hist_households_of
    for circuit, rows in PREFECTURE_SEATS.items():
        blocked = [r for r in rows if r.get("blocked")]
        if not blocked:
            continue
        hist_rows = [r for r in blocked if r.get("basis") == PE.BASIS_HISTORICAL]
        if not hist_rows:
            continue
        # 一路之内要么全 historical、要么全非（不得掺半）
        assert len(hist_rows) == len(blocked), \
            f"{circuit} 部分席标 historical，部分未标——口径混用"
        for r in blocked:
            assert hist_households_of(r["name"]), f"{circuit}/{r['name']} 缺史料"


def test_historical_coverage_is_reported_honestly():
    """覆盖率报告须**如实报出史料覆盖率**与剩余面积估计数。"""
    rep = PE.coverage_report()
    assert rep["total_seats"] == 136
    assert rep["blocked"] + rep["merged"] == 136
    assert rep["historical_seats"] == rep["by_basis"].get(PE.BASIS_HISTORICAL, 0)
    assert 0 < rep["historical_seats"] < rep["blocked"], "史料应部分覆盖（未全覆盖）"
    assert rep["historical_coverage"] == pytest.approx(
        rep["historical_seats"] / rep["blocked"], abs=1e-4)
    note = rep["precision_note"]
    assert "面积估计" in note and "不得" in note, "必须声明面积估计边界"


def test_historical_ratio_matches_source_for_jingji():
    """**史料比例正确**：京畿路 `开封府` 占比应等于《宋史》崇宁户占比（±1%）。

    《宋史》京畿路四州崇宁户：开封府 261,117 / 郑州 30,976 / 滑州 26,522 / 陈州 32,094。
    """
    from content.data_households_hist import HIST_HOUSEHOLDS
    names = ["开封府", "郑州", "滑州", "陈州"]
    tot = sum(HIST_HOUSEHOLDS[n]["hu"] for n in names)
    want = HIST_HOUSEHOLDS["开封府"]["hu"] / tot
    ent = PE.seat_entity(PE.seat_id_of("京畿路", "开封府"))
    got = ent["demog"]["households"] / PREFECTURE_INFO["京畿路"]["households"]
    assert abs(got - want) < 0.01, f"史料比例未落实：{got:.4f} vs {want:.4f}"


def test_seat_to_circuit_index_matches_geo():
    """`SEAT_TO_CIRCUIT`（按显示名索引）与实体层同源（防两张表分叉）。

    显示名现已唯一（去重后），故可逐项比对。
    """
    for s in PE.all_seats():
        assert SEAT_TO_CIRCUIT[s["seat"]] == s["circuit"]
        assert PE.circuit_of(s["seat_id"]) == s["circuit"]


# ====================================================== 4 · 只读
def test_layer_is_read_only_no_state_touched():
    """本层只读：不依赖也不修改任何 `state`（纯 content 派生）。"""
    import inspect
    for fn in (PE.all_seats, PE.seats_of, PE.prefecture_demog,
               PE.circuit_aggregate, PE.coverage_report):
        src = inspect.getsource(fn)
        assert "state." not in src, f"{fn.__name__} 不得触碰 state"


# ====================================================== 5 · 迁移批次验收（阶段 2 · 第五包 · 2026-10-06）
def test_stub_reexports_same_objects_as_new_module():
    """旧路径为**薄转发**：每个符号与新实现**同一对象**（无复制实现）。"""
    from core import prefecture_entity as OLD
    from core.foundation.ledger import prefecture_entity as NEW
    assert OLD.__file__ != NEW.__file__
    # 2026-10-18 全审：以 `__all__` 为对外契约（私有缓存助手 lru_cache 等不计入），
    # 逐符号核验旧桩与新实现是**同一对象**（无复制实现）。
    names = sorted(NEW.__all__)
    assert len(names) == 16, f"对外符号数变化（迁移桩需同步）：{len(names)}"
    for n in names:
        assert getattr(OLD, n) is getattr(NEW, n), f"符号 {n} 非同一实现（疑似副本）"
    for key in ("all_seats", "seats_of", "seat_id_of", "circuit_of"):
        assert key in names, f"关键读口 {key} 不在对外契约内"


def test_pop_bridge_seat_weights_resolves_via_new_path():
    """`pop_bridge.seat_pop_weights` 的 lazy import 已改指新路径。

    ⚠️ 该函数把 import 包在 `try/except` 里**静默返回 []**——断路径不会炸 import，
    只会让拆分权重变空，故必须**断言非空**才算接通。
    """
    from core.foundation.ledger.pop_bridge import seat_pop_weights
    w = seat_pop_weights("京畿路")
    assert w, "权重为空 ⇒ lazy import 断链被 try/except 吞掉"
    assert all(isinstance(sid, str) and "|" in sid for sid, _pop in w)
    assert any(pop > 0 for _sid, pop in w)
