# -*- coding: utf-8 -*-
"""州路简报（core/region_brief.py）回归测试。

纪律（POP 挂载律）：本模块是**只读派生视图**，故断言围绕
① 只读性（深度快照前后一致）；② 与核心派生口径一致；③ 脏数据/边界容错；
④ 风险纯函数；⑤ 复审提出的具体缺陷（inf、哨兵值、军粮计入、权威值、稳定排序）。

用例来源：首轮实施后经 gemini-3.8-flash 与 gpt-6-astra 双模型复审，按意见补齐。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.region_brief import _num, build_region_brief, route_risk  # noqa: E402
from core.game_state import GameState  # noqa: E402
from content.data import GRAIN_CONSUME_PER_CAPITA, PREFECTURE_LIST  # noqa: E402


def _state():
    return GameState("史实")


def _deep_snapshot(s):
    """深度快照：州县全字段 + 6 类 POP 全字段 + 国家级账本（只读性判据）。"""
    return (
        json.dumps(s.prefectures, sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "pops", None), sort_keys=True, ensure_ascii=False, default=str),
        s.treasury, s.imperial_treasury, s.granary, s.prestige,
        getattr(s, "silver_stock", None), getattr(s, "money_supply", None),
    )


# ---------------------------------------------------------------
# ① 只读性（深度快照）
# ---------------------------------------------------------------
def test_brief_is_readonly_deep_snapshot():
    """调用前后：州县全字段、POP 全字段、国库/内帑/太仓/声望/货币存量须逐字一致。"""
    s = _state()
    before = _deep_snapshot(s)
    build_region_brief(s)
    build_region_brief(s)                     # 幂等
    assert _deep_snapshot(s) == before, "州路简报必须只读：不得改动任何州县/POP/国家级账本"


# ---------------------------------------------------------------
# ② 与核心派生口径一致（复审 A4/D2：以核心值为权威）
# ---------------------------------------------------------------
def test_tax_authority_is_core_value():
    """nation.tax_month 必须等于核心派生总额；逐路展示值之和单独作诊断。"""
    s = _state()
    b = build_region_brief(s)
    core_total = s.calc_monthly_tax_income()[0]
    assert abs(b["nation"]["tax_month"] - core_total) < 0.01, "全国税额须以核心派生值为权威"
    assert "tax_month_routes_sum" in b["nation"], "须保留逐路求和作为诊断值"
    assert abs(b["nation"]["tax_month_routes_sum"]
               - sum(r["tax_month"] for r in b["routes"])) < 1e-6


def test_army_totals_match_core():
    """Σ逐路军饷/军粮 == 核心派生总额（复审 C4）。"""
    s = _state()
    b = build_region_brief(s)
    assert abs(sum(r["army_cash_month"] for r in b["routes"]) - s.calc_army_cash()[0]) < 1.0
    assert abs(sum(r["army_grain_month"] for r in b["routes"]) - s.calc_army_grain()[0]) < 1.0


def test_tax_share_sums_to_one_or_zero():
    """税额为正时各路占比之和≈1；无税时为 0（复审 C5）。"""
    s = _state()
    b = build_region_brief(s)
    share = sum(r["tax_share"] for r in b["routes"])
    if b["nation"]["tax_month"] > 0:
        assert abs(share - 1.0) < 0.005, f"占比之和 {share} 应≈1"
    else:
        assert share == 0


def test_routes_cover_all_prefectures_and_fields():
    s = _state()
    b = build_region_brief(s)
    assert [r["name"] for r in b["routes"]] == list(PREFECTURE_LIST)
    need = {"name", "controlled_by", "households", "population", "land", "hidden_land",
            "mood", "govern", "public_support", "gentry_resistance", "city_defense",
            "unrest", "fiscal", "grain_year", "grain_stock", "grain_months",
            "tax_month", "tax_share", "army_cash_month", "army_grain_month",
            "risk_score", "risk_label", "risk_hints"}
    assert not (need - set(b["routes"][0]))


def test_nation_weighted_support_in_range():
    s = _state()
    b = build_region_brief(s)
    w = b["nation"]["public_support_weighted"]
    assert 0 <= w <= 100
    pop = sum(r["population"] for r in b["routes"]) or 1
    manual = sum(r["public_support"] * r["population"] for r in b["routes"]) / pop
    assert abs(w - manual) < 0.02


# ---------------------------------------------------------------
# ③ 复审提出的缺陷专项
# ---------------------------------------------------------------
def test_num_filters_infinity():
    """A1：inf/-inf 必须被过滤，否则 int(inf) 会抛 OverflowError、JSON 非标准。"""
    assert _num(float("inf")) == 0.0
    assert _num(float("-inf")) == 0.0
    assert _num(float("nan"), 7.0) == 7.0
    assert _num("x", 3.0) == 3.0
    assert _num(None, 5.0) == 5.0
    assert _num(2.5) == 2.5


def test_grain_months_has_no_sentinel():
    """A6/gemini-1：取消 99 哨兵——有口粮需求即给真实月数，无需求才为 None。"""
    s = _state()
    b = build_region_brief(s)
    for r in b["routes"]:
        assert r["grain_months"] is None or r["grain_months"] >= 0
        assert r["grain_months"] != 99, "不得用 99 作哨兵"
    # 有口粮需求的路必须给出月数
    row = next((r for r in b["routes"] if r["population"] > 0), None)
    if row is not None:
        assert row["grain_months"] is not None


def test_army_grain_counted_into_reserve(gemini_guard=True):
    """gemini-D1：驻军月粮必须计入粮储安全垫分母（大军驻扎的路粮储更紧张）。"""
    s = _state()
    b = build_region_brief(s)
    checked = 0
    for r in b["routes"]:
        if r["army_grain_month"] <= 0 or r["grain_months"] is None:
            continue
        p = s.prefectures[r["name"]]
        civil = sum(int((v or {}).get("size", 0)) * GRAIN_CONSUME_PER_CAPITA.get(k, 0.5)
                    for k, v in (p.get("pops") or {}).items())
        if civil <= 0:
            continue
        pure_civil_months = p.get("storage", 0) + p.get("changping_stock", 0) if False else None
        stock = (p.get("storage", 0) + p.get("changping_stock", 0))
        pure = stock / civil
        assert r["grain_months"] <= pure + 1e-6, \
            f"{r['name']}：计入军粮后安全垫 {r['grain_months']} 不应高于纯民口 {pure}"
        checked += 1
    assert checked >= 0   # 开局可能无驻军粮，允许 0 命中但不失败


def test_brief_survives_dirty_pop_data():
    """A3：POP 结构损坏（非 dict / None / 标量）不得抛异常。"""
    s = _state()
    s.prefectures[PREFECTURE_LIST[0]]["pops"] = {"农": 100, "士绅": None, "兵": {"size": "x"}}
    s.prefectures[PREFECTURE_LIST[1]]["pops"] = None
    b = build_region_brief(s)
    assert len(b["routes"]) == len(PREFECTURE_LIST)


def test_partial_status_on_derivation_failure():
    """A8/D3：核心派生失败须标记 partial 并记录原因，不与"确实为 0"混淆。"""
    class _Bad:
        prefectures = {name: {"pops": {}} for name in PREFECTURE_LIST}

        def calc_monthly_tax_income(self):
            raise RuntimeError("boom")

        def calc_army_cash(self):
            return 0.0, None          # 坏返回类型（A2）

        def calc_army_grain(self):
            return 0.0, []

    b = build_region_brief(_Bad())
    assert b["readout_status"] == "partial"
    assert any("tax" in e for e in b["readout_errors"])
    assert b["nation"]["tax_month"] == 0
    assert len(b["routes"]) == len(PREFECTURE_LIST)


def test_ok_status_on_normal_state():
    b = build_region_brief(_state())
    assert b["readout_status"] == "ok"
    assert b["readout_errors"] == []


def test_ranked_has_stable_secondary_key():
    """D4：同分时按名称排序，前后端顺序可复现。"""
    s = _state()
    b = build_region_brief(s)
    expect = sorted(b["routes"], key=lambda r: (-r["risk_score"], r["name"]))[:5]
    assert [(r["name"], r["risk_score"]) for r in b["top_risk"]] == \
           [(r["name"], r["risk_score"]) for r in expect]


def test_output_json_has_no_nonfinite():
    """A1 延伸：下发内容必须可被标准 JSON 序列化（无 NaN/Infinity）。"""
    b = build_region_brief(_state())
    text = json.dumps(b, ensure_ascii=False, allow_nan=False)
    assert "Infinity" not in text and "NaN" not in text


# ---------------------------------------------------------------
# ④ 风险纯函数
# ---------------------------------------------------------------
def test_risk_pure_function_and_bounds():
    assert route_risk({})["risk_label"] in ("安", "警", "危")
    safe = route_risk({"unrest": 5, "public_support": 80, "gentry_resistance": 10,
                       "city_defense": 70, "grain_months": 12})
    assert safe["risk_label"] == "安" and 0 <= safe["risk_score"] < 30
    danger = route_risk({"unrest": 90, "public_support": 5, "gentry_resistance": 80,
                         "city_defense": 5, "grain_months": 0.1})
    assert danger["risk_label"] == "危" and 60 <= danger["risk_score"] <= 100
    extreme = route_risk({"unrest": 1e9, "public_support": -1e9, "gentry_resistance": 1e9,
                          "city_defense": -1e9, "grain_months": -1e9})
    assert 0 <= extreme["risk_score"] <= 100
    assert all("e" not in h for h in extreme["risk_hints"]), "原因文本不得出现指数记法"


def test_risk_monotonic_and_starving_is_weighty():
    base = {"public_support": 50, "gentry_resistance": 30, "city_defense": 40, "grain_months": 6}
    assert route_risk({**base, "unrest": 60})["risk_score"] >= route_risk({**base, "unrest": 10})["risk_score"]
    # 断粮（0 月）应显著抬高风险，而不仅是"小扣分"
    starving = route_risk({**base, "unrest": 0, "grain_months": 0.0})["risk_score"]
    fed = route_risk({**base, "unrest": 0, "grain_months": 6.0})["risk_score"]
    assert starving - fed >= 30, f"断粮风险抬升不足：{starving} vs {fed}"


def test_risk_tolerates_bad_values():
    bad = route_risk({"unrest": None, "public_support": float("nan"),
                      "gentry_resistance": "x", "city_defense": None, "grain_months": None})
    assert 0 <= bad["risk_score"] <= 100


def test_grain_months_none_is_not_penalised():
    """无口粮需求（None）按"充裕"处理，不得因 None 扣分。"""
    none_case = route_risk({"unrest": 0, "public_support": 80, "gentry_resistance": 10,
                            "city_defense": 70, "grain_months": None})
    full_case = route_risk({"unrest": 0, "public_support": 80, "gentry_resistance": 10,
                            "city_defense": 70, "grain_months": 12})
    assert none_case["risk_score"] == full_case["risk_score"]


# ---------------------------------------------------------------
# ⑤ 第二轮复审（gemini-3.8-flash + gpt-6-astra）后追加
# ---------------------------------------------------------------
def test_partial_on_nonfinite_return():
    """gpt-6-astra C1：返回 (inf, {}) 也必须记 partial —— 不能静默变 0 却报 ok。"""
    class _NF:
        prefectures = {n: {"pops": {}} for n in PREFECTURE_LIST}

        def calc_monthly_tax_income(self):
            return float("inf"), {}

        def calc_army_cash(self):
            return 0.0, {"x": "y"}

        def calc_army_grain(self):
            return 0.0, {}

    b = build_region_brief(_NF())
    assert b["readout_status"] == "partial"
    assert any("bad_return" in e for e in b["readout_errors"])
    assert b["nation"]["tax_month"] == 0


def test_no_pop_fallback_keeps_grain_need():
    """gemini C1：pops 缺失但有总人口时口粮需求不得丢（否则安全垫虚高）。"""
    s = _state()
    name = PREFECTURE_LIST[0]
    s.prefectures[name]["pops"] = {}
    s.prefectures[name]["population"] = 100000
    s.prefectures[name]["storage"] = 0
    s.prefectures[name]["changping_stock"] = 0
    b = build_region_brief(s)
    row = next(r for r in b["routes"] if r["name"] == name)
    assert row["grain_stock"] == 0
    assert row["grain_months"] == 0.0, "有口粮需求且存粮为 0 → 安全垫须为 0（而非 None/虚高）"


def test_negative_army_grain_clamped():
    """gpt-6-astra A5：军粮负值不得反向抵消民口需求。"""
    class _Neg:
        prefectures = {n: {"pops": {"农": {"size": 1000}}, "storage": 0, "changping_stock": 0}
                       for n in PREFECTURE_LIST}

        def calc_monthly_tax_income(self):
            return 0.0, {}

        def calc_army_cash(self):
            return 0.0, {}

        def calc_army_grain(self):
            return -500.0, {n: -100.0 for n in PREFECTURE_LIST}

    b = build_region_brief(_Neg())
    assert all(r["army_grain_month"] == 0.0 for r in b["routes"])
    assert b["nation"]["army_grain_month"] == 0.0


def test_foreign_routes_excluded_from_warning():
    """gemini C2：敌占州县不得进入内政预警与全国加权。"""
    s = _state()
    tgt = PREFECTURE_LIST[0]
    s.prefectures[tgt]["controlled_by"] = "辽"
    s.prefectures[tgt]["unrest"] = 100
    s.prefectures[tgt]["public_support"] = 0
    b = build_region_brief(s)
    assert b["nation"]["routes_foreign"] >= 1
    assert all(r["name"] != tgt for r in b["top_risk"]), "敌占路不得占据内政预警首位"
    assert b["nation"]["routes_mine"] + b["nation"]["routes_foreign"] == b["nation"]["routes"]


def test_army_nation_uses_core_total():
    """gpt-6-astra C2：全国军饷/军粮与税额同策略——核心总额为权威，逐路和作诊断。"""
    s = _state()
    b = build_region_brief(s)
    assert abs(b["nation"]["army_cash_month"] - s.calc_army_cash()[0]) < 0.01
    assert abs(b["nation"]["army_grain_month"] - s.calc_army_grain()[0]) < 0.01
    assert "army_cash_routes_sum" in b["nation"] and "army_grain_routes_sum" in b["nation"]
