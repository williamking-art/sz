# -*- coding: utf-8 -*-
"""识字率设定测试（`core/literacy.py`，2026-09-19 新增；用户口径：**各地 POP 自有**）。

守护：① POP 挂载（识字率挂在 `prefectures[路].pops[阶层].literacy`，是比率指标而非账本）；
② 阶级差异（官僚/士绅 ≫ 工商 ≫ 兵/农）与**逐路差异**（地区调制）；
③ 缓动不跳变；④ 作为诏令效果的**弱关联项**（幅度 ≤15%）；⑤ 只读边界与存档往返。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import GRAIN_CONSUME_PER_CAPITA, PREFECTURE_LIST  # noqa: E402
from core.decree_effect import effect_channels  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.literacy import (  # noqa: E402
    LITERACY_CAP, LITERACY_CONVERGE, LITERACY_FLOOR, POP_LITERACY_BASE, init_literacy,
    literacy_target, national_literacy, pop_literacy, route_literacy, settle_literacy,
)

CLASSES = tuple(GRAIN_CONSUME_PER_CAPITA)


def _state():
    s = GameState("史实")
    init_legacies(s)
    return s


def test_literacy_is_attached_to_every_pop_of_every_route():
    """识字率必须挂在**各地各类 POP** 上（不是路级字段、更不是全国字段）。"""
    s = _state()
    for route in PREFECTURE_LIST:
        pops = s.prefectures[route]["pops"]
        for cls in CLASSES:
            v = pops[cls].get("literacy")
            assert isinstance(v, (int, float)), f"{route}|{cls} 缺 literacy"
            assert LITERACY_FLOOR <= v <= LITERACY_CAP, f"{route}|{cls}={v}"
        assert "literacy" not in s.prefectures[route], "识字率不应是路级字段（POP 自有）"


def test_class_literacy_ordering():
    """阶级序：官僚 > 士绅 > 商人 > 工匠 > 兵 ≥ 农（读书人基础不同）。"""
    s = _state()
    for route in PREFECTURE_LIST:
        v = {c: pop_literacy(s, route, c) for c in CLASSES}
        assert v["官僚"] > v["士绅"] > v["商人"] > v["工匠"] > v["兵"], (route, v)
        assert v["兵"] >= v["农"], (route, v)
    assert POP_LITERACY_BASE["官僚"] == 92.0 and POP_LITERACY_BASE["农"] == 5.0


def test_literacy_differs_across_routes_and_classes():
    s = _state()
    route_vals = {r: route_literacy(s, r) for r in PREFECTURE_LIST}
    assert len(set(round(v, 1) for v in route_vals.values())) > 1, "各路识字率应有差异"
    # 同一路内各阶级差异必须显著（否则设定形同虚设）
    r = "京畿路"
    assert pop_literacy(s, r, "士绅") - pop_literacy(s, r, "农") > 40


def test_init_is_idempotent_and_keeps_existing():
    s = _state()
    s.prefectures["河北路"]["pops"]["农"]["literacy"] = 7.5
    assert init_literacy(s) == 0, "已有值不应被覆盖"
    assert s.prefectures["河北路"]["pops"]["农"]["literacy"] == 7.5


def test_settle_literacy_moves_slowly_toward_target():
    s = _state()
    route, cls = "陕西路", "农"
    pop = s.prefectures[route]["pops"][cls]
    pop["literacy"] = 1.0
    target = literacy_target(s, route, cls, s.prefectures[route])
    settle_literacy(s, [])
    new = pop["literacy"]
    assert new > 1.0, "目标更高时必须上升"
    assert new < target, "缓动：一步不得直接到目标"
    assert new == pytest.approx(round(1.0 + (target - 1.0) * LITERACY_CONVERGE, 2), abs=0.02)


def test_national_and_route_literacy_are_pop_weighted():
    s = _state()
    assert s.literacy == pytest.approx(national_literacy(s), abs=0.01)
    # 路级加权：士绅人口占比越高，路级识字率越接近士绅水平
    route = "京畿路"
    p = s.prefectures[route]
    before = route_literacy(s, route)
    p["pops"]["士绅"]["size"] = int(p["pops"]["士绅"]["size"] * 50) + 10_000
    assert route_literacy(s, route) > before


def test_literacy_is_weak_channel_for_decrees():
    """识字率只影响弱关联项（≤15%）。"""
    s = _state()
    for p in s.prefectures.values():
        for pop in p["pops"].values():
            pop["literacy"] = 1.0
    low = effect_channels(s, text="清丈田亩")["effect_mult"]
    for p in s.prefectures.values():
        for pop in p["pops"].values():
            pop["literacy"] = 95.0
    high = effect_channels(s, text="清丈田亩")["effect_mult"]
    assert high > low, "识字率提高应小幅改善诏令效果"
    assert high / low <= 1.15, "识字率是弱关联，不得主导诏令成败"
    assert effect_channels(s, text="清丈田亩")["literacy"] is not None


def _strip_literacy(obj):
    """深拷贝并剔除所有 `literacy` 键（用于"只改 literacy"的只读断言）。"""
    if isinstance(obj, dict):
        return {k: _strip_literacy(v) for k, v in obj.items() if k != "literacy"}
    if isinstance(obj, list):
        return [_strip_literacy(x) for x in obj]
    return obj


def test_settle_literacy_only_touches_literacy():
    s = _state()
    before = (
        json.dumps(_strip_literacy(s.prefectures), sort_keys=True, ensure_ascii=False, default=str),
        s.treasury, s.granary, s.population_satisfaction, s.prestige,
        json.dumps(getattr(s, "factions", {}), sort_keys=True, ensure_ascii=False, default=str),
    )
    settle_literacy(s, [])
    after = (
        json.dumps(_strip_literacy(s.prefectures), sort_keys=True, ensure_ascii=False, default=str),
        s.treasury, s.granary, s.population_satisfaction, s.prestige,
        json.dumps(getattr(s, "factions", {}), sort_keys=True, ensure_ascii=False, default=str),
    )
    assert before == after, "识字率步只应改 POP 的 literacy 字段"


def test_literacy_survives_save_roundtrip():
    s = _state()
    settle_literacy(s, [])
    payload = json.loads(json.dumps({"literacy": s.literacy, "prefectures": s.prefectures},
                                    ensure_ascii=False, default=str))
    assert payload["literacy"] == s.literacy
    for route in PREFECTURE_LIST:
        for cls in CLASSES:
            assert payload["prefectures"][route]["pops"][cls]["literacy"] == \
                s.prefectures[route]["pops"][cls]["literacy"]


def test_literacy_readout_exposes_every_pop():
    from core.situations import build_situation_readout
    s = _state()
    out = build_situation_readout(s)
    assert out["readout_status"] == "ok", out["readout_errors"]
    lit = out["pop_channels"]["literacy"]
    assert set(lit["nation"]) == set(CLASSES)
    assert lit["nation"]["官僚"] > lit["nation"]["农"]
    assert set(lit["by_route"]) == set(PREFECTURE_LIST)
    for route, row in lit["by_route"].items():
        assert set(row) == set(CLASSES), route
