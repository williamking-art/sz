# -*- coding: utf-8 -*-
"""质量放行门 · 交通方式能力判定（G-3 P5b）。

用户 2026-10-18 批准水运资格表走 A（可配置设定表）。本门钉住：
1. 方式表自洽（速度/运力/费率合法）；
2. `land`：可达即可运，天数 == 路由天数（速度 1.0）；
3. `water`：需全路径路都在 WATER_ROUTE_CIRCUITS + 漕淤 ≤ 阈值 + 有漕船；内陆路 ⇒ not_waterway；
4. `sea`：需开海政策 + 沿海路；未开海 ⇒ sea_not_open；
5. `post`：只允许轻货（cargo 白名单），运大宗钱粮 ⇒ cargo_not_allowed；
6. 未知方式/未知治所/不连通 ⇒ 明确 reason，不回落；
7. 反例自证：每类失败 reason 互不相同（不是同一个兜底）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_constants import (  # noqa: E402
    POST_CARGO_KINDS, TRANSPORT_MODES)
from core.transport import (  # noqa: E402
    available_modes, route_days, route_path, transport_capability)

CAPITAL = "京畿路|开封府"
JIANGNAN = "两浙路|杭州"
SHANXI = "陕西路|熙州"
ISLAND = "广南西路|琼州"


def _state():
    from core.commands import new_game

    return new_game()


def test_mode_table_is_sane():
    assert TRANSPORT_MODES, "方式表为空 ⇒ 门是空转"
    for m, spec in TRANSPORT_MODES.items():
        assert spec.get("name"), f"{m} 缺中文名"
        assert float(spec.get("speed", 0)) > 0, f"{m} 速度非正"
        assert int(spec.get("capacity", 0)) > 0, f"{m} 运力非正"
        assert float(spec.get("cost_per_km", 0)) >= 0, f"{m} 费率为负"


def test_land_uses_route_days():
    s = _state()
    r = transport_capability(s, CAPITAL, "京西路|河南府", "land")
    assert r["ok"] and r["days"] == route_days(CAPITAL, "京西路|河南府")
    far = transport_capability(s, CAPITAL, JIANGNAN, "land")
    assert far["ok"] and far["hops"] >= 2
    assert far["days"] == route_path(CAPITAL, JIANGNAN)["days"]


def test_water_requires_waterway_circuits():
    s = _state()
    ok = transport_capability(s, CAPITAL, JIANGNAN, "water")
    assert ok["ok"], f"汴河—淮南—两浙 应可水运：{ok}"
    inland = transport_capability(s, CAPITAL, SHANXI, "water")
    assert not inland["ok"] and inland["reason"] == "not_waterway", inland


def test_water_blocked_by_canal_or_no_barges():
    s = _state()
    s.canal_block = 90
    blocked = transport_capability(s, CAPITAL, JIANGNAN, "water")
    assert not blocked["ok"] and blocked["reason"] == "canal_blocked", blocked
    s.canal_block = 0
    s.statistics = dict(getattr(s, "statistics", {}) or {})
    s.statistics["barges_pool"] = 0
    no_barge = transport_capability(s, CAPITAL, JIANGNAN, "water")
    assert not no_barge["ok"] and no_barge["reason"] == "no_barges", no_barge


def test_sea_is_open_by_default_and_closable_by_policy():
    """2026-10-18 用户质疑后的口径：史实海运本开 ⇒ **缺失 = 开放**；显式禁海才关闭。"""
    s = _state()
    on = transport_capability(s, "两浙路|台州", "福建路|福州", "sea")
    assert on["ok"], f"默认应可海运：{on}"
    s.transport_policy = {"open_sea": False}
    off = transport_capability(s, "两浙路|台州", "福建路|福州", "sea")
    assert not off["ok"] and off["reason"] == "sea_closed_by_policy", off


def test_post_allows_only_light_cargo():
    s = _state()
    light = next(iter(POST_CARGO_KINDS))
    ok = transport_capability(s, CAPITAL, JIANGNAN, "post", cargo=light)
    assert ok["ok"], ok
    grain = transport_capability(s, CAPITAL, JIANGNAN, "post", cargo="grain")
    assert not grain["ok"] and grain["reason"] == "cargo_not_allowed", grain


def test_failures_are_explicit_and_distinct():
    s = _state()
    reasons = {
        "mode": transport_capability(s, CAPITAL, JIANGNAN, "airplane").get("reason"),
        "unknown": transport_capability(s, "不存在路|不存在州", JIANGNAN, "land").get("reason"),
        "unreachable": transport_capability(s, "两浙路|台州", ISLAND, "land").get("reason"),
        "cargo": transport_capability(s, CAPITAL, JIANGNAN, "post", cargo="grain").get("reason"),
    }
    assert reasons["mode"] == "unknown_mode"
    assert reasons["unknown"] == "unknown_seat"
    assert reasons["unreachable"] == "unreachable"
    assert reasons["cargo"] == "cargo_not_allowed"
    assert len(set(reasons.values())) == 4, f"失败原因必须可区分：{reasons}"


def test_available_modes_lists_all():
    s = _state()
    modes = available_modes(s, CAPITAL, JIANGNAN)
    assert set(modes) == set(TRANSPORT_MODES), modes.keys()
    assert modes["land"]["ok"] is True