# -*- coding: utf-8 -*-
"""M91 P2 第一片：建筑**归属**登记（`building_meta`；保形态、幂等、零数值变化）—— 定向回归。

锁定：① 规则**逐条给依据**（水利/常平仓 → `local:<路>`），**未登记类型不写**（留 undefined）；
② **保形态**：`buildings` 标量**一字不动**；③ 幂等且**不覆盖**；④ 零数值变化（只新增元数据）；
⑤ 真实新局：40 座建筑全部登记、`entity_projection` 的 **owner 就绪度由 0 → 1.0**。
"""

import copy
import types

from core.domains.economy import building_owner as bo


def _state(buildings, routes=("路A",)):
    st = types.SimpleNamespace()
    st.prefectures = {}
    for r in routes:
        st.prefectures[r] = {"name": r, "seats": {"%s|首府" % r: {"buildings": dict(buildings)}}}
    return st


def test_rules_have_basis_and_local_owner():
    assert set(bo.OWNER_BY_TYPE) >= {"水利", "常平仓"}
    for b, (_kind, basis) in bo.OWNER_BY_TYPE.items():
        assert basis, b
    r = bo.owner_for("路A", "水利")
    assert r["defined"] and r["owner"] == "local:路A"


def test_unknown_type_is_not_guessed():
    r = bo.owner_for("路A", "谜之建筑")
    assert r["defined"] is False and "未登记归属规则" in r["reason"]


def test_assign_is_idempotent_never_overwrites_and_keeps_shape():
    st = _state({"水利": 2, "常平仓": 3})
    before_buildings = copy.deepcopy(st.prefectures["路A"]["seats"]["路A|首府"]["buildings"])
    rep = bo.assign_building_owners(st)
    assert rep["assigned"] == 2 and rep["undefined"] == 0
    seat = st.prefectures["路A"]["seats"]["路A|首府"]
    assert seat["building_meta"]["水利"]["owner"] == "local:路A"
    # **保形态**：buildings 一字不动
    assert seat["buildings"] == before_buildings == {"水利": 2, "常平仓": 3}
    # 幂等
    assert bo.assign_building_owners(st)["assigned"] == 0
    # 不覆盖既有值
    seat["building_meta"]["水利"]["owner"] = "imperial"
    bo.assign_building_owners(st)
    assert seat["building_meta"]["水利"]["owner"] == "imperial"


def test_unknown_building_is_skipped_not_written():
    st = _state({"怪建筑": 1})
    rep = bo.assign_building_owners(st)
    assert rep["assigned"] == 0 and rep["undefined"] == 1
    assert "怪建筑" not in (st.prefectures["路A"]["seats"]["路A|首府"]["building_meta"])


def test_real_new_game_all_buildings_owned_and_readiness_rises():
    from core import commands
    from core.domains.economy import entity_projection as ep
    s = commands.new_game()                                  # 新局已走 init_building_owners
    cov = bo.survey_building_owners(s)
    assert cov["total"] == 40 and cov["with_owner"] == 40 and cov["undefined_rule"] == 0
    ratio = ep.survey_entity_projection(s)["defined_ratio"]
    assert ratio["owner"] == 1.0, ratio                      # P2 就绪度：owner 0 → 1.0
    assert ratio["seat"] == 1.0 and ratio["level"] == 1.0


def test_migration_helper_is_idempotent_and_load_safe():
    from core.foundation.persistence.migrations import assign_building_owners
    from core import commands
    s = commands.new_game()
    assert assign_building_owners(s)["assigned"] == 0        # 新局已登记 ⇒ 幂等
