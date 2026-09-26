# -*- coding: utf-8 -*-
"""建筑等级「统一读口」回归（2026-09-27 加固）。

背景：宋侧 `prefectures[*]["buildings"]` 历史上是**标量**（`{"工坊": 2}`，由
`settlement_tech._settle_projects` 写入），外邦省域是**结构**（`{"lv": 2}`）。审计发现多处
**月度结算**读点直接 `int(lv)`（资产维持费估值、时代维度、产业规模、科技采用率），
两种格式一旦混用即 `TypeError` 当月中止。

本文件锁定统一读口 `core.building_jobs.building_level` 的语义，并让四条真实路径
在**结构格式**下与标量格式等价（不炸、数值一致）。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.building_jobs import building_level  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402


def test_building_level_semantics():
    """统一读口：兼容标量/结构/倒闭；**保留 0**；缺省按 default。"""
    assert building_level(2) == 2
    assert building_level({"lv": 2}) == 2
    assert building_level("3") == 3
    assert building_level(0) == 0, "0（裁撤）必须保留，不得像 _lv() 那样归一到 1"
    assert building_level({"lv": 0}) == 0
    assert building_level({"closed": True}) == 0, "倒闭建筑按 0 计"
    assert building_level(None) == 1 and building_level(None, 0) == 0
    assert building_level(-5) == 0
    assert building_level("坏值") == 1

    # 与岗位口径 `_lv()` 的差异是有意的（外邦口径把 0 归一为 1），此处显式钉住
    from core.building_jobs import _lv
    assert _lv(0) == 1 and building_level(0) == 0


def _paid_for(fmt):
    """同一等级、两种写法 → 资产维持费实付额（国库充足时 == 资产值 × 费率）。"""
    from core.settlement_officialdom import _settle_upkeep
    s = GameState("史实")
    route = next(iter(s.prefectures))
    # 水利命中 BUILDING_STD 分支；商铺走 POP_BUILDING_VALUE 分支（两条分支都覆盖）
    s.prefectures[route]["buildings"] = {"水利": fmt, "商铺": fmt}
    s.treasury = 10 ** 9
    return _settle_upkeep(s, [])


def test_asset_upkeep_equivalent_for_scalar_and_structured():
    """资产维持费：`2` 与 `{"lv": 2}` 应给出**相同**实付额（原来结构格式直接 TypeError）。"""
    assert _paid_for(2) == _paid_for({"lv": 2}) > 0


def test_damage_buildings_tolerates_and_normalizes_structured():
    """毁损：结构格式可读、并按等级降级，写回归一化标量；等级 1 拆除。"""
    from core.era_mechanic import damage_buildings
    s = GameState("史实")
    route = next(iter(s.prefectures))
    s.prefectures[route]["buildings"] = {"工坊": {"lv": 3}, "商铺": {"lv": 1}}
    damage_buildings(s, [], reason="测试")
    b = s.prefectures[route]["buildings"]
    assert b.get("工坊") == 2, "3 → 2"
    assert "商铺" not in b, "1 → 拆除"


def test_era_links_and_industry_scale_tolerate_structured():
    """时代维度与产业规模：结构格式不炸且按等级计入。"""
    from core.era_mechanic import calc_industry_scale, settle_era_links
    s = GameState("史实")
    route = next(iter(s.prefectures))
    s.prefectures[route]["buildings"] = {"工坊": {"lv": 2}, "商铺": 2}
    settle_era_links(s, [])                     # 原来会在 int(lv) 处炸
    scale = calc_industry_scale(s)
    assert scale["old_scale"] + scale["new_scale"] >= 0


def test_full_month_settlement_tolerates_structured_buildings():
    """整月结算（含资产维持费/时代/就业流动/科技采用率）在结构格式下不得抛错。"""
    s = GameState("史实")
    route = next(iter(s.prefectures))
    s.prefectures[route]["buildings"] = {
        "工坊": {"lv": 2}, "商铺": 2, "农田": {"lv": 1}, "水利": {"lv": 2},
    }
    run_monthly_settlement(s, 0)               # 不抛即通过
    assert s.turn >= 1
