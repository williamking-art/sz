# -*- coding: utf-8 -*-
"""利益集团方案（2026-09-19）第 1 步回归：集团模型元数据与校验。

锁定：
  1. 全局表校验（别名唯一 / 重叠指向存在 / 子通道落在基本盘内）；
  2. **口径：集团名取「总集」，具体群体（西军、东南士人…）只能是 subchannels 子集**；
  3. 任意历史写法（旧名 / 推荐显示名 / 内部 ID）归一到同一权威键；
  4. 每个集团都能说明历史性质(kind)、POP 类、路线、子池与重叠关系（方案完成标准）。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import FACTION_DISPLAY_NAMES, FACTION_KINDS, FACTION_POP_BASIS  # noqa: E402
from core.faction_basis import (  # noqa: E402
    faction_display_name, resolve_faction_key, validate_faction_basis,
    validate_faction_table,
)
from core.game_state import GameState  # noqa: E402


def _spec(**over):
    base = {"pop_classes": ["官僚"], "pool": "officials", "routes": None,
            "subset_of": ["官僚"], "subset_kind": "pool"}
    base.update(over)
    return base


# ---------------------------------------------------------------- 全局表
def test_builtin_table_is_valid():
    assert validate_faction_table() == []


def test_display_name_is_superset_never_a_subset():
    """集团显示名必须是「总集」；具体群体只能作为 subchannels 子集出现。"""
    for key, spec in FACTION_POP_BASIS.items():
        disp = FACTION_DISPLAY_NAMES[key]
        subs = [x.get("name") for x in (spec.get("subchannels") or [])]
        assert disp not in subs, f"{key}: 显示名 {disp!r} 不得同时是自己的子集"
    # 具体断例：西军 / 东南士人 都被下沉为子集
    assert FACTION_DISPLAY_NAMES["西军集团"] == "军功集团"
    assert "西军" in [x["name"] for x in FACTION_POP_BASIS["西军集团"]["subchannels"]]
    assert FACTION_DISPLAY_NAMES["东南士人"] == "中立派"
    assert "东南士人" in [x["name"] for x in FACTION_POP_BASIS["东南士人"]["subchannels"]]
    # 宦官是子集，集团总集名为「皇党集团」
    assert FACTION_DISPLAY_NAMES["宦官集团"] == "皇党集团"
    assert "入内内侍省" in [
        x["name"] for x in FACTION_POP_BASIS["宦官集团"]["subchannels"]]
    assert resolve_faction_key("皇党集团") == "宦官集团"


def test_every_faction_states_history_pop_routes_pool_overlap():
    """方案完成标准：每个集团都能说明 历史性质 / POP 类 / 路线 / 子池 / 重叠。"""
    for key, spec in FACTION_POP_BASIS.items():
        assert spec.get("kind") in FACTION_KINDS, key
        assert spec.get("pop_classes"), key
        assert spec.get("subset_of"), key
        assert spec.get("subset_kind"), key
        assert isinstance(spec.get("aliases"), list) and spec["aliases"], key
        assert isinstance(spec.get("interests"), list) and spec["interests"], key
        assert "overlaps" in spec, key
        assert isinstance(spec.get("thresholds"), dict) and spec["thresholds"], key


# ---------------------------------------------------------------- 归一
def test_resolve_faction_key_normalises_every_writing():
    assert resolve_faction_key("新党") == "新党"
    assert resolve_faction_key("新法系") == "新党"
    assert resolve_faction_key("new_law_network") == "新党"
    assert resolve_faction_key("绍述派") == "新党"
    assert resolve_faction_key("军功集团") == "西军集团"
    assert resolve_faction_key("中立派") == "东南士人"
    assert resolve_faction_key("根本不存在的集团") is None
    assert faction_display_name("新党") == "新法系"
    assert faction_display_name("不存在的集团") == "不存在的集团"


# ---------------------------------------------------------------- 单条校验
def test_validate_rejects_bad_kind():
    assert any("kind" in e for e in validate_faction_basis("X", _spec(kind="not_a_kind")))


def test_validate_rejects_bad_interests():
    assert any("interests[0]" in e for e in validate_faction_basis(
        "X", _spec(interests=[{"pop_class": "农", "topic": "", "direction": 0}])))
    assert any("pop_class" in e for e in validate_faction_basis(
        "X", _spec(interests=[{"pop_class": "外星人", "topic": "t", "direction": 1}])))


def test_validate_rejects_bad_thresholds():
    assert any("population_share" in e for e in validate_faction_basis(
        "X", _spec(thresholds={"population_share": 1.5})))
    assert any("cohesion" in e for e in validate_faction_basis(
        "X", _spec(thresholds={"cohesion": -1})))


def test_validate_rejects_subchannel_outside_base():
    assert any("subchannels" in e for e in validate_faction_basis(
        "X", _spec(subchannels=[{"name": "错位", "pop_class": "农"}])))


def test_validate_allows_optional_metadata_to_be_absent():
    """元数据为**可选**：缺失不报错（保证既有/改革催生集团登记行为不变）。"""
    assert validate_faction_basis("X", _spec()) == []


# ---------------------------------------------------------------- 跨条校验
def test_table_rejects_conflicting_alias():
    tbl = {"甲": _spec(aliases=["通用名"]), "乙": _spec(aliases=["通用名"])}
    assert any("通用名" in e for e in validate_faction_table(tbl))


def test_table_rejects_alias_colliding_with_key():
    tbl = {"甲": _spec(aliases=["乙"]), "乙": _spec()}
    assert any("乙" in e for e in validate_faction_table(tbl))


def test_table_rejects_overlap_to_unknown_and_self():
    tbl = {"甲": _spec(overlaps=["不存在"]), "乙": _spec(overlaps=["乙"])}
    errs = validate_faction_table(tbl)
    assert any("不存在" in e for e in errs)
    assert any("自指" in e for e in errs)


# ---------------------------------------------------------------- 通道下发
def test_channels_expose_display_name_kind_and_subchannels():
    from core.faction_basis import build_faction_channels
    ch = build_faction_channels(GameState("史实"))
    assert ch["declared"] is True and ch["basis_errors"] == []
    row = ch["factions"]["西军集团"]
    assert row["display_name"] == "军功集团"
    assert row["kind"] == "military_command"
    assert "西军" in [x["name"] for x in row["subchannels"]]
    assert "边帅与军前文官" in [x["name"] for x in row["subchannels"]], "文官应可入军功集团"
    assert ch["display_names"]["新党"] == "新法系"