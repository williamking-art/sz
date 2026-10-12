# -*- coding: utf-8 -*-
"""M46 州府级商品只读读数 —— 定向回归。

锁定：读**治所真账**（兼容 `{治所:{dim:n}}` 桶）· 未下沉 ⇒ `None`（缺失≠0）· 阶层维度不合并 ·
`seat_consistency` 能**发现镜像漂移**（真账 Σ ≠ 路级镜像）· 未下沉 ⇒ `ok=None`（不假装通过）·
`workshop_attribution` 按已知路名判定（不臆造）· **零写入**（前后深比较一致）。
"""

import copy
import types

import pytest

from core.domains.economy import seat_goods_readout as sg


def _state(seats=None, mirror=None, workshops=None, routes=("路A",)):
    st = types.SimpleNamespace()
    st.prefectures = {}
    for r in routes:
        st.prefectures[r] = {
            "name": r,
            "seats": (seats or {}).get(r, {}),
            "pops": {"工匠": {"goods": (mirror or {}).get(r, {})}},
        }
    if workshops is not None:
        st.workshops = workshops
    return st


# ------------------------------------------------------------------ 1. 真账读数
def test_seat_goods_reads_truth_and_handles_bucket_shape():
    st = _state(seats={"路A": {
        "A|甲": {"pops": {"工匠": {"goods": {"绸": 5}}, "商人": {"goods": {"A|甲": {"绸": 2}}}}},
        "A|乙": {"pops": {"工匠": {"goods": {"绸": 3, "布": 1}}}},
    }})
    got = sg.seat_goods(st, "路A")
    assert got["A|甲"]["工匠"] == {"绸": 5}
    assert got["A|甲"]["商人"] == {"绸": 2}          # 桶形态被摊平
    assert got["A|乙"]["工匠"] == {"绸": 3, "布": 1}
    assert sg.route_seat_totals(st, "路A")["A|乙"] == {"绸": 3, "布": 1}


def test_seat_goods_none_when_not_sunk():
    st = _state(seats={"路A": {}})                    # 无 seats
    assert sg.seat_goods(st, "路A") is None
    # 全库视图：**未下沉的路显式 None**（不静默省略——"没有 seats" ≠ "有 seats 但没货"）
    assert sg.seat_goods(st) == {"路A": None}
    assert sg.seat_goods(types.SimpleNamespace()) is None
    assert sg.seat_goods(st, "不存在的路") is None


# ------------------------------------------------------------------ 2. 一致性自检
def test_consistency_detects_mirror_drift():
    # 真账 Σ = 8，镜像 = 5 ⇒ 必须报出
    st = _state(seats={"路A": {"A|甲": {"pops": {"工匠": {"goods": {"绸": 8}}}}}},
                mirror={"路A": {"绸": 5}})
    rep = sg.seat_consistency(st)
    assert rep["ok"] is False and rep["checked"] >= 1
    m = rep["mismatches"][0]
    assert (m["route"], m["cls"], m["dim"], m["seat_sum"], m["mirror"], m["diff"]) == \
        ("路A", "工匠", "绸", 8, 5, -3)


def test_consistency_ok_when_equal():
    st = _state(seats={"路A": {"A|甲": {"pops": {"工匠": {"goods": {"绸": 8}}}}}},
                mirror={"路A": {"绸": 8}})
    rep = sg.seat_consistency(st)
    assert rep["ok"] is True and rep["mismatches"] == []


def test_consistency_none_when_not_sunk():
    rep = sg.seat_consistency(_state(seats={"路A": {}}))
    assert rep["ok"] is None and "未下沉" in (rep["reason"] or "")


# ------------------------------------------------------------------ 3. 作坊可归属率
def test_workshop_attribution():
    st = _state(workshops={"麻坊_路A_1": {}, "丝坊_路B_2": {}, "无名坊": {}},
                routes=("路A", "路B"))
    wa = sg.workshop_attribution(st)
    assert (wa["total"], wa["attributable"]) == (3, 2)
    assert wa["unattributed"] == ["无名坊"]
    assert abs(wa["ratio"] - 2 / 3) < 1e-9
    assert sg.workshop_attribution(types.SimpleNamespace())["ratio"] is None


# ------------------------------------------------------------------ 4. 只读 + 总读数
def test_survey_is_readonly():
    st = _state(seats={"路A": {"A|甲": {"pops": {"工匠": {"goods": {"绸": 8}}}}}},
                mirror={"路A": {"绸": 8}}, workshops={"麻坊_路A_1": {}})
    before = copy.deepcopy({"p": st.prefectures, "w": st.workshops})
    rep = sg.survey_seat_goods(st)
    assert before == {"p": st.prefectures, "w": st.workshops}
    assert rep["sunk"] is True and rep["routes"] == 1 and rep["seats"] == 1
    assert rep["dims"] == ["绸"] and rep["consistency"]["ok"] is True
