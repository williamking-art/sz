# -*- coding: utf-8 -*-
"""B0 建筑-多职位岗位槽回归（2026-09-27 用户口径："一个建筑不是只有一个职位的"）。

被测：`core.building_jobs` 的多职位读口与分配器
  · `_positions_of` / `jobs_by_position`：`{建筑: {职位: 岗位数}}`；兼容外邦**扁平**写法；
  · `jobs_of`：仍返回**扁平总量**（= Σ职位）——既有调用者语义不变；
  · `allocate_employment_detail`：**一个建筑可横跨多个 POP 类**
    （地主农庄 = `农` 的佃农岗 ＋ `士绅` 的地主岗）；
  · `allocate_employment`：兼容签名 = 明细合计；
  · `live_job_buildings`：新建筑名（自耕农庄/地主农庄）可上岗；「庄园」为旧档别名同构。

守恒：分配只读 `size`、不落账（余工 = 派生读数）；本文件不改任何 POP 数。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import POP_BUILDING_TYPES  # noqa: E402
from content.data_external import EXTERNAL_ECON as EXT  # noqa: E402
from core.building_jobs import (  # noqa: E402
    SONG_JOBS_PER_LEVEL, SONG_POSITION_CLASS, _positions_of,
    allocate_employment, allocate_employment_detail,
    jobs_by_position, jobs_of, live_job_buildings, song_job_cfg,
)

CFG = song_job_cfg()


def _pops(nong=100_000, art=1_000, mer=1_000, shen=5_000):
    return {"农": {"size": nong}, "工匠": {"size": art}, "商人": {"size": mer},
            "士绅": {"size": shen}, "官僚": {"size": 100}, "兵": {"size": 200}}


def test_positions_readout_and_flat_compat():
    """宋侧嵌套表；外邦扁平表回落为「单一职位 = `BUILDING_WORKER` 的 POP 类」。"""
    assert _positions_of("自耕农庄", CFG) == {"自耕农": 120, "富农": 20, "贫农": 20}
    assert _positions_of("地主农庄", CFG) == {"佃农": 100, "地主": 20}
    assert _positions_of("农田", CFG) == {}, "生计轨不占岗"
    flat = dict(EXT)
    pos = _positions_of("工坊", flat)
    assert list(pos) == ["工匠"], f"外邦扁平方应回落为单职位：{pos}"
    assert pos["工匠"] == int(flat["JOBS_PER_LEVEL"]["工坊"])


def test_jobs_by_position_and_total_semantics():
    """`jobs_by_position` 出明细，`jobs_of` 仍是**扁平总量**（向后兼容）。"""
    bld = {"自耕农庄": {"lv": 2}, "地主农庄": 1, "农田": {"lv": 3}}
    detail = jobs_by_position(bld, CFG)
    assert detail["自耕农庄"] == {"自耕农": 240, "富农": 40, "贫农": 40}
    assert detail["地主农庄"] == {"佃农": 100, "地主": 20}
    assert detail["农田"] == {}
    assert jobs_of(bld, CFG) == {"自耕农庄": 320, "地主农庄": 120, "农田": 0}


def test_one_building_spans_two_pop_classes():
    """地主农庄：佃农岗由**农**填、地主岗由**士绅**填；士绅池不足只影响地主岗。"""
    d = allocate_employment_detail(_pops(shen=5_000), {"地主农庄": {"lv": 1}}, CFG)
    assert d["地主农庄"] == {"佃农": 100, "地主": 20}
    d2 = allocate_employment_detail(_pops(shen=7), {"地主农庄": {"lv": 1}}, CFG)
    assert d2["地主农庄"] == {"佃农": 100, "地主": 7}, "地主岗受士绅池限制，且不挤占佃农岗"


def test_farm_positions_share_one_pool():
    """自耕农庄三职位同属 `农` 池：池不足时按岗位序填满即止（不超池、不跨池）。"""
    d = allocate_employment_detail(_pops(nong=100), {"自耕农庄": {"lv": 1}}, CFG)
    slots = d["自耕农庄"]
    assert sum(slots.values()) == 35, f"农池 = 100×0.35 = 35 应填满即止：{slots}"
    assert slots["自耕农"] == 35 and slots["富农"] == 0 and slots["贫农"] == 0


def test_flat_legacy_cfg_equivalence():
    """外邦扁平配置（单职位）走兼容路径：`allocate_employment` == 明细合计。"""
    pops = {"农": {"size": 100_000}, "工匠": {"size": 500}}
    bld = {"矿场": {"lv": 1}, "工坊": {"lv": 1}}
    flat = dict(EXT)
    total = allocate_employment(pops, bld, flat, "辽")
    detail = allocate_employment_detail(pops, bld, flat, "辽")
    assert total == {bt: sum(v.values()) for bt, v in detail.items()}
    assert total.get("矿场", 0) + total.get("工坊", 0) <= 500, "工匠池 500 不得超额上岗"


def test_live_job_buildings_new_names_and_alias():
    """新建筑名可上岗；「庄园」旧档别名同构；`lv==0` 显式判零（无 live 但仍是岗位建筑）。"""
    live, has = live_job_buildings({"自耕农庄": {"lv": 2}, "地主农庄": 0, "庄园": 1}, CFG)
    assert has and set(live) == {"自耕农庄", "庄园"}
    live2, has2 = live_job_buildings({"自耕农庄": {"lv": 0}}, CFG)
    assert has2 and live2 == {}, "裁撤建筑不计岗位，但仍是「有岗位建筑」"
    live3, has3 = live_job_buildings({}, CFG)
    assert not has3 and live3 == {}


def test_building_types_and_job_table_keys_in_sync():
    """建筑集三处一致：POP_BUILDING_TYPES == 岗位表键 == 扁平兼容键。"""
    assert set(CFG["JOBS_PER_LEVEL"]) == set(SONG_JOBS_PER_LEVEL) == set(POP_BUILDING_TYPES)
    assert set(CFG["POSITION_CLASS"]) == set(SONG_POSITION_CLASS)
    # 每个职位都能归属到六类之一（否则分配器会把它当成孤儿槽）
    from content.data import GRAIN_CONSUME_PER_CAPITA
    assert set(SONG_POSITION_CLASS.values()) <= set(GRAIN_CONSUME_PER_CAPITA)
