# -*- coding: utf-8 -*-
"""蓝图「仿明末模式」调整的回归锁定（2026-09-19）。

明末模式的建筑蓝图字段：category / branch / requires_region（地利前置）/
base_cost / build_months（1-6 月）/ outputs（产出词条）/ requires_tech。
本文件钉住宋祚蓝图（BUILDING_BLUEPRINTS）已按此结构声明，且工期落在明末档。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import (  # noqa: E402
    BLUEPRINT_BRANCHES, BLUEPRINT_CATEGORIES, BLUEPRINT_MONTHS_MAX,
    BLUEPRINT_MONTHS_MIN, BUILDING_BLUEPRINTS, TECH_NODE_DEPLOY,
    blueprint_region_ok,
)


def test_every_blueprint_declares_full_schema():
    assert BUILDING_BLUEPRINTS, "蓝图册不得为空"
    for key, bp in BUILDING_BLUEPRINTS.items():
        assert isinstance(bp, dict), key
        for f in ("name", "kind", "category", "branch", "cost", "outputs",
                  "requires_region", "need_node"):
            assert f in bp, f"{key} 缺字段 {f}"
        assert bp["category"] in BLUEPRINT_CATEGORIES, (key, bp["category"])
        assert bp["branch"] in BLUEPRINT_BRANCHES, (key, bp["branch"])
        assert isinstance(bp["cost"], dict) and bp["cost"].get("silver", 0) > 0, key
        assert isinstance(bp["requires_region"], (tuple, list)), key


def test_blueprint_build_months_stay_in_mingyang_band():
    """工期须落在明末档 1–6 月（原先 8–24 月过长）。"""
    for key, bp in BUILDING_BLUEPRINTS.items():
        m = int(bp["cost"].get("months", 0))
        assert BLUEPRINT_MONTHS_MIN <= m <= BLUEPRINT_MONTHS_MAX, (key, m)


def test_blueprint_outputs_are_structured_and_nonempty():
    for key, bp in BUILDING_BLUEPRINTS.items():
        outs = bp.get("outputs")
        assert isinstance(outs, list) and outs, f"{key} 产出词条不得为空"
        for o in outs:
            assert isinstance(o, dict) and str(o.get("kind") or "").strip(), (key, o)


def test_blueprint_region_requirement_is_checkable():
    """地利前置可校验：空要求 → 处处可建；有要求 → 按路型判定。"""
    # 任意蓝图在任意路型下都必须返回布尔（不得抛）
    for key in BUILDING_BLUEPRINTS:
        for rt in ("京畿要地", "沿海中产", "缘边贫瘠", ""):
            assert isinstance(blueprint_region_ok(rt, key), bool)
    # 无地利要求者处处可建
    free = [k for k, bp in BUILDING_BLUEPRINTS.items() if not bp.get("requires_region")]
    assert free, "至少应有无地利要求的蓝图"
    for k in free:
        assert blueprint_region_ok("随便什么型", k) is True
    # 有地利要求者：命中可建、未命中不可建
    gated = {k: bp for k, bp in BUILDING_BLUEPRINTS.items() if bp.get("requires_region")}
    for k, bp in gated.items():
        need = bp["requires_region"][0]
        assert blueprint_region_ok(str(need), k) is True
        assert blueprint_region_ok("完全不相干的路型", k) is False


def test_blueprint_keys_match_tech_deploy_nodes():
    """科技节点的「部署建筑」必须都取自蓝图册（避免声明漂移）。"""
    names = {bp["name"] for bp in BUILDING_BLUEPRINTS.values()}
    for nid, bname in TECH_NODE_DEPLOY.items():
        assert bname in names, f"{nid} 的部署建筑 {bname!r} 不在蓝图册"