# -*- coding: utf-8 -*-
"""质量放行门 · V3 建筑分级升级（2026-10-19）。

V3 口径：建筑有等级、每级一份产能；升级要**建材 + 工钱 + 工期**，建造限流。
本门钉住：
1. 等级倍率 = 1 + (level−1)×BONUS（≤1 或缺失 ⇒ 1.0）；
2. 升级条件逐项给 reason（无此建筑/已满级/同路在建/建材不足/银不足）；
3. 开工**扣建材与地方府库银**并登记库存流水；不足时**不动账**；
4. 工期满 ⇒ 等级 +1（走桥；未下沉回落保形态），队列清空、留完成记录；
5. 同路同时只允许 1 项在建（限流）；
6. 结算钩子：队列空时零行为变更（日志无「营造」）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

import content.data_constants as dc  # noqa: E402
from core.domains.construction import building_upgrade as BU  # noqa: E402
from core.foundation.ledger.building_bridge import norm_level  # noqa: E402

ROUTE = "京畿路"
NAME = "水利"


def _state_full():
    """新局 + 备足建材/银（构造前置；不改任何被测逻辑）。

    2026-10-20 全审：地方府库真账在治所，路级 `local_treasury` 是派生镜像；
    构造前置必须经 `local_treasury_bridge` 写（直写镜像会被下一次走桥写入校正，
    测试会读到“没有扣款”的假象）。
    """
    from core.commands import new_game
    from core.foundation.ledger import local_treasury_bridge as LTB

    s = new_game()
    for dim in ("木", "石", "铁"):
        s.resources.setdefault(dim, {"stock": 0})
        s.resources[dim]["stock"] = 1000
    assert LTB.local_treasury_set(s, ROUTE, 200000) is not None, "舆图/治所未下沉？"
    return s


def test_level_multiplier():
    assert BU.level_multiplier(0) == 1.0
    assert BU.level_multiplier(1) == 1.0
    assert abs(BU.level_multiplier(2) - 1.15) < 1e-9
    assert abs(BU.level_multiplier(5) - (1 + 4 * dc.BUILDING_LEVEL_OUTPUT_BONUS)) < 1e-9
    assert BU.level_multiplier(None) == 1.0


def test_missing_building_is_refused():
    s = _state_full()
    r = BU.upgrade_requirement(s, ROUTE, "不存在的建筑")
    assert r["ok"] is False and r["reason"] == "building_missing"


def test_level_max_is_refused():
    s = _state_full()
    lv = int(dc.BUILDING_LEVEL_MAX)
    s.prefectures[ROUTE]["buildings"][NAME] = lv
    # 建筑真账可能已下沉到治所：镜像由 Σ 派生，必须同时改治所真账
    for sid, srow in (s.prefectures[ROUTE].get("seats") or {}).items():
        bmap = (srow or {}).get("buildings")
        if isinstance(bmap, dict) and NAME in bmap:
            bmap[NAME] = lv
    r = BU.upgrade_requirement(s, ROUTE, NAME)
    assert r["ok"] is False and r["reason"] == "level_max"


def test_insufficient_materials_refused_without_charging():
    s = _state_full()
    s.resources["木"]["stock"] = 0
    t0 = int(s.prefectures[ROUTE]["local_treasury"])
    r = BU.upgrade_requirement(s, ROUTE, NAME)
    assert r["ok"] is False and r["reason"] == "insufficient_木"
    out = BU.start_upgrade(s, ROUTE, NAME)
    assert out["ok"] is False
    assert int(s.prefectures[ROUTE]["local_treasury"]) == t0


def test_insufficient_silver_refused():
    s = _state_full()
    from core.foundation.ledger import local_treasury_bridge as LTB
    LTB.local_treasury_set(s, ROUTE, 0)
    r = BU.upgrade_requirement(s, ROUTE, NAME)
    assert r["ok"] is False and r["reason"] == "insufficient_silver"


def test_start_charges_materials_and_silver():
    s = _state_full()
    req = BU.upgrade_requirement(s, ROUTE, NAME)
    assert req["ok"], req
    wood0 = int(s.resources["木"]["stock"])
    silver0 = int(s.prefectures[ROUTE]["local_treasury"])
    out = BU.start_upgrade(s, ROUTE, NAME)
    assert out["ok"], out
    assert int(s.resources["木"]["stock"]) == wood0 - req["materials"]["木"]
    assert int(s.prefectures[ROUTE]["local_treasury"]) == silver0 - req["silver"]
    assert len(s.building_construction) == 1


def test_route_busy_limits_concurrency():
    s = _state_full()
    assert BU.start_upgrade(s, ROUTE, NAME)["ok"]
    r = BU.upgrade_requirement(s, ROUTE, "常平仓")
    assert r["ok"] is False and r["reason"] == "route_busy"


def test_advance_completes_and_raises_level():
    s = _state_full()
    before = norm_level((s.prefectures[ROUTE]["buildings"] or {}).get(NAME))
    req = BU.upgrade_requirement(s, ROUTE, NAME)
    assert BU.start_upgrade(s, ROUTE, NAME)["ok"]
    for _ in range(req["months"] - 1):
        assert BU.advance_building_construction(s) == []
        assert s.building_construction, "未到期不得清队列"
    done = BU.advance_building_construction(s)
    assert done and done[0]["level"] == int(before) + 1, done
    assert s.building_construction == []
    assert norm_level((s.prefectures[ROUTE]["buildings"] or {}).get(NAME)) == int(before) + 1
    assert s.building_upgrades_done


def test_settlement_hook_is_inert_when_queue_empty():
    from core.commands import new_game
    from core.settlement import run_monthly_settlement

    s = new_game()
    assert not (getattr(s, "building_construction", None) or [])
    log = run_monthly_settlement(s)
    assert not [x for x in log if "营造" in str(x)], "队列空不得有营造日志"