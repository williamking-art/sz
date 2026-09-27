# -*- coding: utf-8 -*-
"""宋侧「就业驱动的阶层流动」回归（设计 §3.6 / §15.1 决策 #6：失业推＋空岗拉＋回农兜底）。

被测：
  · `core.building_jobs.apply_employment_flow`（宋侧岗位缺口驱动迁移）；
  · `core.building_jobs.song_job_cfg`（宋侧岗位口径 = POP_BUILDING_TYPES 四类）；
  · `core.settlement_econ._settle_economy` 内的接线（第 2b 段，串行于城市化/回乡之后）。

断言要点：
  (i)   无建筑（新局基线）→ **零迁移**，不写任何 econ_audit 痕迹；
  (ii)  有工坊空岗且农富余 → 农→工匠，量 == min(农闲×率, 空岗) 且 ≤ 空岗，ΣPOP 不变；
  (iii) 岗位裁撤/减少 → 工/商→农回流，ΣPOP 不变（**该分支宋侧默认关闭**，用例显式开启验证）；
  (iv)  月迁移有上限（`JOB_FLOW_RATE`）且不会把任一 POP 抽成负数；
  (v)   与既有城市化/回乡通道协同：本通道串行其后，**当月同路只有一个方向**。

纪律：迁移只改 农/工匠/商人 三类 `size`，`ΣΔ == 0`（整数尾差归迁出方）。
"""
import os
import random
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import POP_BUILDING_TYPES  # noqa: E402
from core.building_jobs import (  # noqa: E402
    SONG_JOBS_PER_LEVEL, SONG_JOB_SHARE_DEFAULT,
    allocate_employment, apply_employment_flow, live_job_buildings, song_job_cfg,
)
from core.game_state import GameState  # noqa: E402
from core.settlement_econ import _settle_economy  # noqa: E402

CFG = song_job_cfg()
# 「失业推」在宋侧默认关闭（见 `building_jobs.SONG_JOB_PUSH_UNEMPLOYED`：宋侧岗位容量远小于
# 非农人口，无条件失业推 60 月会把非农抽掉约 70%）。验证**该分支实现**的用例显式开启，
# 使"分支语义"与"当前默认策略"分开受测。
CFG_PUSH = dict(CFG, JOB_FLOW_UNEMPLOYED_PUSH=True)
# 岗位数走**扁平兼容口径** `CFG["JOBS_PER_LEVEL"]`（= Σ职位；B0 多职位化后仍保持该语义）；
# 多职位明细在 `CFG["BUILDING_POSITIONS"]`，由 `test_building_multi_position.py` 覆盖。
_WORKSHOP_JPL = int(CFG["JOBS_PER_LEVEL"]["工坊"])
_SHOP_JPL = int(CFG["JOBS_PER_LEVEL"]["商铺"])
_MANOR_JPL = int(CFG["JOBS_PER_LEVEL"]["庄园"])
_FARM_JPL = int(CFG["JOBS_PER_LEVEL"]["农田"])
_FLOW_RATE = float(CFG["JOB_FLOW_RATE"])


def _pops(nong=200_000, art=100, mer=2_500):
    """六类 POP（量级贴近宋侧一路的真实规模）。"""
    return {"农": {"size": nong}, "工匠": {"size": art}, "商人": {"size": mer},
            "士绅": {"size": 100}, "官僚": {"size": 50}, "兵": {"size": 300}}


def _total(pops):
    return sum(int(v.get("size", 0) or 0) for v in pops.values())


def _flow(pops, buildings, prov=None, cfg=None):
    prov = prov if prov is not None else {"pops": pops}
    before = _total(pops)
    st = apply_employment_flow(prov, pops, buildings, CFG if cfg is None else cfg)
    assert _total(pops) == before, f"ΣPOP 破裂：{before} → {_total(pops)}"
    return st


# ---------------------------------------------------------------
# 口径本身：宋侧四类 POP 建筑
# ---------------------------------------------------------------
def test_song_job_cfg_covers_pop_building_types():
    """宋侧岗位口径须覆盖 `POP_BUILDING_TYPES`（农田/工坊/商铺/庄园），农田豁免岗位。"""
    assert set(SONG_JOBS_PER_LEVEL) == set(POP_BUILDING_TYPES)
    assert set(CFG["JOBS_PER_LEVEL"]) == set(POP_BUILDING_TYPES)
    assert int(CFG["JOBS_PER_LEVEL"]["农田"]) == 0, "农田走粮维豁免岗位制"
    assert CFG["BUILDING_WORKER"]["工坊"] == "工匠"
    assert CFG["BUILDING_WORKER"]["商铺"] == "商人"
    assert CFG["BUILDING_WORKER"]["农田"] == "农" and CFG["BUILDING_WORKER"]["庄园"] == "农"
    # 不外邦建筑（桑麻田/牧场/矿场）混入宋侧岗位表
    assert "牧场" not in CFG["JOBS_PER_LEVEL"] and "矿场" not in CFG["JOBS_PER_LEVEL"]
    # 返回新 dict（不污染外邦 EXTERNAL_ECON，也不被调用侧就地改动污染）
    local = song_job_cfg()
    local["JOBS_PER_LEVEL"]["工坊"] = 99999
    assert int(song_job_cfg()["JOBS_PER_LEVEL"]["工坊"]) == _WORKSHOP_JPL
    assert int(CFG["JOBS_PER_LEVEL"]["工坊"]) == _WORKSHOP_JPL


# ---------------------------------------------------------------
# (i) 新局基线：无建筑 → 零迁移
# ---------------------------------------------------------------
def test_no_buildings_zero_migration():
    """(i) 无建筑（新局 `buildings == {}`）→ 三类 size 逐字不变、迁移读数全 0。

    这是「新局行为不变」的硬前提：`buildings` 空 → 通道整体不生效。
    非岗位表建筑（如 `市舶司`，政府工程）同样不得驱动迁移。
    """
    for bld in ({}, None, {"市舶司": 2}):
        pops = _pops()
        snap = {k: v["size"] for k, v in pops.items()}
        st = _flow(pops, bld)
        assert st["moved_to_artisan"] == st["moved_to_merchant"] == 0, bld
        assert st["returned_to_farm"] == 0, bld
        assert st["farm_idle"] == 0 and st["artisan_vacancy"] == 0, bld
        assert {k: v["size"] for k, v in pops.items()} == snap, f"零迁移被破坏：{bld!r}"


def test_farm_only_building_has_zero_jobs():
    """`农田` 粮维豁免岗位（岗位恒 0）：不坐岗、不成岗序 → 不驱动迁移。"""
    pops = _pops(nong=200_000, art=2_000, mer=300)
    bld = {"农田": {"lv": 5}}
    assert int(CFG["JOBS_PER_LEVEL"]["农田"]) == 0
    staffed = allocate_employment(pops, bld, CFG, "宋")
    assert int(staffed.get("农田", 0)) == 0, "农田不得占岗"
    st = _flow(pops, bld)
    assert st["moved_to_artisan"] == st["moved_to_merchant"] == 0, "无岗位 → 不拉"
    assert st["artisan_vacancy"] == 0 and st["merchant_vacancy"] == 0
    assert st["farm_idle"] == int(200_000 * SONG_JOB_SHARE_DEFAULT), "农田不在农职岗序"


def test_new_game_settlement_buildings_empty_and_flow_dormant():
    """(i) 新局（`GameState('史实')`）各路 `buildings` 为空 → 接线存在但不迁移。"""
    s = GameState("史实")
    assert all(not (p.get("buildings") or {}) for p in s.prefectures.values()), \
        "新局 POP 建筑应为空（基线前提）"
    random.seed(11)
    t0 = sum(v["size"] for p in s.prefectures.values() for v in p["pops"].values())
    pop0 = s.population
    _settle_economy(s, [])
    t1 = sum(v["size"] for p in s.prefectures.values() for v in p["pops"].values())
    growth = s.population - pop0
    # 唯一人口外部输入是自然增长（每路 int 截断 ≤ 路数）
    assert abs((t1 - t0) - growth) <= 20, f"人口恒等断裂：ΔP={t1 - t0} growth={growth}"
    for name, p in s.prefectures.items():
        assert "job_flow" not in (p.get("econ_audit") or {}), \
            f"{name}：无建筑时不得写岗位流动痕迹（新局基线不得漂移）"


# ---------------------------------------------------------------
# (ii) 空岗拉：农 → 工匠/商人
# ---------------------------------------------------------------
def test_vacancy_pulls_farmers_to_artisan_matching_gap():
    """(ii) 工坊 lv2（320 岗）而工匠仅 100 → 农→工匠，量 == min(农闲×2%, 空岗)。"""
    pops = _pops(nong=200_000, art=100, mer=2_500)
    bld = {"工坊": {"lv": 2}}
    staffed = allocate_employment(pops, bld, CFG, "宋")
    assert staffed["工坊"] == 100, "工匠仅 100 → 只能坐满 100 个岗位"
    farm_staffed = sum(int(staffed.get(bt, 0) or 0)
                       for bt, wk in CFG["BUILDING_WORKER"].items() if wk == "农")
    farm_idle = int(200_000 * SONG_JOB_SHARE_DEFAULT) - farm_staffed
    vacancy = 2 * _WORKSHOP_JPL - 100

    st = _flow(pops, bld)
    expect = min(int(farm_idle * CFG["JOB_FLOW_RATE"]), vacancy)
    assert st["artisan_vacancy"] == vacancy
    assert st["moved_to_artisan"] == expect, f"迁移量与岗位缺口不符：{st}"
    assert st["moved_to_artisan"] <= vacancy, "迁移不得超岗位空缺"
    assert st["moved_to_merchant"] == 0
    assert st["returned_to_farm"] == 0, "同月不得双向迁移"
    assert pops["农"]["size"] == 200_000 - expect
    assert pops["工匠"]["size"] == 100 + expect


def test_vacancy_split_between_artisan_and_merchant_is_exact():
    """(ii) 工坊+商铺同时有空缺 → 按空缺比例分摊，且分摊后总量恰等于迁移量。"""
    pops = _pops(nong=200_000, art=50, mer=20)
    bld = {"工坊": {"lv": 2}, "商铺": {"lv": 3}}
    st = _flow(pops, bld)
    a_v, m_v = st["artisan_vacancy"], st["merchant_vacancy"]
    assert (a_v, m_v) == (2 * _WORKSHOP_JPL - 50, 3 * _SHOP_JPL - 20)
    farm_idle = int(200_000 * SONG_JOB_SHARE_DEFAULT)
    assert st["moved_to_artisan"] + st["moved_to_merchant"] \
        == min(int(farm_idle * _FLOW_RATE), a_v + m_v)
    assert st["moved_to_artisan"] <= a_v and st["moved_to_merchant"] <= m_v
    assert pops["工匠"]["size"] == 50 + st["moved_to_artisan"]
    assert pops["商人"]["size"] == 20 + st["moved_to_merchant"]


def test_no_vacancy_no_pull_even_if_farm_idle():
    """(ii) 无空岗（工坊已被工匠坐满）→ 空岗拉不发生（区别于外邦「无岗也转商」）。"""
    pops = _pops(nong=200_000, art=400_000, mer=2_500)
    bld = {"工坊": {"lv": 1}}
    st = _flow(pops, bld)
    assert st["artisan_vacancy"] == 0
    assert st["moved_to_artisan"] + st["moved_to_merchant"] == 0


def test_shop_only_pulls_to_merchant():
    """(ii) 只有商铺 → 农闲转商人（不凭空转工匠）。"""
    pops = _pops(nong=200_000, art=100, mer=10)
    st = _flow(pops, {"商铺": {"lv": 2}})
    assert st["merchant_vacancy"] == 2 * _SHOP_JPL - 10
    assert st["moved_to_artisan"] == 0
    assert st["moved_to_merchant"] == min(
        int(int(200_000 * SONG_JOB_SHARE_DEFAULT) * _FLOW_RATE), 2 * _SHOP_JPL - 10)
    assert pops["商人"]["size"] == 10 + st["moved_to_merchant"]


# ---------------------------------------------------------------
# (iii) 失业推：工/商 → 农回流
# ---------------------------------------------------------------
def test_layoff_returns_artisans_to_farm():
    """(iii) 岗位全部裁撤（lv=0）→ 工/商按 2% 回流农，ΣPOP 不变。"""
    pops = _pops(nong=200_000, art=3_000, mer=2_500)
    st = _flow(pops, {"工坊": {"lv": 0}}, cfg=CFG_PUSH)   # 岗位 0 = 已裁撤（需显式开失业推）
    idle = 3_000 + 2_500
    assert abs(st["returned_to_farm"] - int(idle * _FLOW_RATE)) <= 1
    assert st["moved_to_artisan"] == st["moved_to_merchant"] == 0, "同月不得双向迁移"
    assert pops["农"]["size"] == 200_000 + st["returned_to_farm"]
    assert pops["工匠"]["size"] + pops["商人"]["size"] == idle - st["returned_to_farm"]


def test_shop_removal_returns_merchants_to_farm():
    """(iii) 商铺裁撤 → 商人回流农；工坊未被裁 → 在岗工匠留下。

    农池取小且工坊坐满工匠（无空岗）以隔离「空岗拉」：本用例只验失业推。
    """
    pops = _pops(nong=50, art=200, mer=900)
    bld = {"工坊": {"lv": 1}, "商铺": {"lv": 0}}
    live, has_jb = live_job_buildings(bld, CFG)
    assert has_jb and set(live) == {"工坊"}, "`lv=0` 商铺是「有岗位建筑但岗位归零」"
    staffed = allocate_employment(pops, live, CFG, "宋")
    assert staffed.get("工坊") == _WORKSHOP_JPL, "lv1 工坊坐满即无空岗"
    idle = 900                                    # 工匠全在岗；商铺裁撤后 900 商人全失业
    st = _flow(pops, bld, cfg=CFG_PUSH)
    assert st["artisan_vacancy"] == 0 and st["merchant_vacancy"] == 0, "无空岗可拉 → 只走失业推"
    assert st["returned_to_farm"] == int(idle * _FLOW_RATE), "回流 = 未在岗 × 月率"
    assert st["moved_to_artisan"] == st["moved_to_merchant"] == 0, "同月不得双向迁移"
    assert pops["工匠"]["size"] == 200, "在岗工匠不参与回流"
    assert pops["商人"]["size"] == 900 - st["returned_to_farm"]
    assert pops["农"]["size"] == 50 + st["returned_to_farm"]


def test_partial_shrink_returns_only_unstaffed():
    """(iii) 岗位**减少**（工坊 lv5→lv1）：在岗者留下，只有未在岗者回流。"""
    pops = _pops(nong=200_000, art=3_000, mer=2_500)
    bld = {"工坊": {"lv": 1}}
    staffed = allocate_employment(pops, bld, CFG, "宋")
    assert staffed["工坊"] == _WORKSHOP_JPL, "lv1 工坊只坐得下 1 级岗位"
    st = _flow(pops, bld, cfg=CFG_PUSH)
    idle_art = 3_000 - _WORKSHOP_JPL
    idle = idle_art + 2_500
    assert abs(st["returned_to_farm"] - int(idle * _FLOW_RATE)) <= 1
    assert st["returned_to_farm"] <= idle, "回流不得超出未在岗人数"
    # 回流按未在岗比例分摊；在岗的 160 名工匠**不参与**（不把在岗者迁走）
    assert _WORKSHOP_JPL <= pops["工匠"]["size"] < 3_000
    assert pops["工匠"]["size"] + pops["商人"]["size"] \
        == 3_000 + 2_500 - st["returned_to_farm"]
    assert pops["农"]["size"] == 200_000 + st["returned_to_farm"]


def test_song_default_disables_unemployed_push():
    """默认策略（宋侧）：岗位全裁撤也**不发生**「失业推」回流——避免 2%/月复利抽干非农。

    量级证据：宋侧「工匠约 40 万 vs 一座工坊 160 岗」，无条件失业推 60 月非农 **−70%**。
    该分支并未删除：显式置 `JOB_FLOW_UNEMPLOYED_PUSH=True` 即恢复（下面给出对照断言）。
    """
    pops = _pops(nong=200_000, art=40_000, mer=25_000)
    before = {k: int(v["size"]) for k, v in pops.items()}
    st = _flow(pops, {"工坊": {"lv": 0}, "商铺": {"lv": 0}})       # 岗位全裁撤
    assert st["returned_to_farm"] == 0, "默认策略下不得发生无条件失业回流"
    assert (st["moved_to_artisan"], st["moved_to_merchant"]) == (0, 0)
    assert all(int(v["size"]) == before[k] for k, v in pops.items()), "默认策略下三类 size 不变"
    # 对照：显式开启后，同一场景恢复「按未在岗 × 月率」的回流语义
    pops2 = _pops(nong=200_000, art=40_000, mer=25_000)
    st2 = _flow(pops2, {"工坊": {"lv": 0}, "商铺": {"lv": 0}}, cfg=CFG_PUSH)
    assert st2["returned_to_farm"] == int((40_000 + 25_000) * _FLOW_RATE)


# ---------------------------------------------------------------
# (iv) 上限与下限：月迁移有上限、不抽成负数
# ---------------------------------------------------------------
def test_monthly_rate_cap_and_no_negative_pop():
    """(iv) 迁移 ≤ 率上限（`JOB_FLOW_RATE`）、极小池仍受 `max(1, …)` 兜底、不抽成负数。"""
    # ① 极小未在岗数（率取整为 0）→ `max(1, …)` 兜底仍推 1，且不超未在岗总数
    pops = _pops(nong=200_000, art=3, mer=0)
    st = _flow(pops, {"工坊": {"lv": 0}, "商铺": {"lv": 0}}, cfg=CFG_PUSH)
    assert st["returned_to_farm"] == 1, "未在岗 3 人 × 2% < 1 → 兜底推 1"
    assert pops["工匠"]["size"] == 2
    assert all(int(v["size"]) >= 0 for v in pops.values())

    # ② 农池为 0 的小局：只走失业推，且源 POP 不被抽负
    pops = _pops(nong=2, art=1, mer=1)
    st = _flow(pops, {"工坊": {"lv": 5}, "商铺": {"lv": 5}})
    assert all(int(v["size"]) >= 0 for v in pops.values()), f"出现负 POP：{pops}"
    assert st["moved_to_artisan"] + st["moved_to_merchant"] == 0, "农池为 0 → 不拉"
    assert st["returned_to_farm"] <= 1

    # ③ 极小农池下也要能拉：农 10（池 3）→ 迁移 ≤ 3 且 ≤ 空岗；源 POP 不被抽负
    pops = _pops(nong=10, art=0, mer=0)
    st = _flow(pops, {"工坊": {"lv": 1}})
    assert 1 <= st["moved_to_artisan"] <= min(3, _WORKSHOP_JPL)
    assert pops["农"]["size"] == 10 - st["moved_to_artisan"]
    assert all(int(v["size"]) >= 0 for v in pops.values())


@pytest.mark.parametrize("bld", [
    {"工坊": {"lv": 5}}, {"商铺": {"lv": 5}}, {"庄园": {"lv": 5}},
    {"工坊": {"lv": 5}, "商铺": {"lv": 5}, "农田": {"lv": 5}, "庄园": {"lv": 5}},
])
def test_rate_cap_over_many_months_and_conservation(bld):
    """(iv) 连续 12 月：每月迁移 ≤ 迁移源×率，ΣPOP 逐月不变，size 恒非负。"""
    pops = _pops(nong=200_000, art=3_000, mer=2_500)
    total0 = _total(pops)
    rng = random.Random(7)
    for _ in range(12):
        src = pops["农"]["size"] + pops["工匠"]["size"] + pops["商人"]["size"]
        st = apply_employment_flow({"pops": pops}, pops, bld, CFG, rng=rng)
        moved = st["moved_to_artisan"] + st["moved_to_merchant"] + st["returned_to_farm"]
        assert moved <= src, f"迁移超源：{moved} > {src}"
        assert _total(pops) == total0, "ΣPOP 漂移"
        assert all(int(v["size"]) >= 0 for v in pops.values())
    # 长跑后三类仍守恒（结构性不变量）
    assert pops["农"]["size"] + pops["工匠"]["size"] + pops["商人"]["size"] \
        == 200_000 + 3_000 + 2_500


def test_legacy_scalar_building_format_supported():
    """旧档口径 `{名: 座数}`（宋侧既有 buildings 写入格式）同样驱动迁移。"""
    pops_a, pops_b = _pops(nong=200_000, art=100, mer=2_500), \
        _pops(nong=200_000, art=100, mer=2_500)
    st_d = _flow(pops_a, {"工坊": {"lv": 2}})
    st_s = _flow(pops_b, {"工坊": 2})
    assert st_s == st_d, "`{lv}` 与旧 `座数` 口径应等价"


# ---------------------------------------------------------------
# (v) 接线：串行于城市化/回乡之后，不双计
# ---------------------------------------------------------------
def test_settlement_wiring_is_serial_and_single_direction(monkeypatch):
    """(v) `_settle_economy` 接线：本通道在既有城市化/回乡之后执行；同路同月单向、ΣPOP 守恒。

    用 monkeypatch 包装调用点以取「调用前/后」逐字快照——既证明接线真的被执行，
    又不受同一步内人口自然增长分摊的干扰。
    """
    import core.settlement_econ as se

    seen = []
    real = se.apply_employment_flow

    def _wrap(p, pops, buildings, cfg, *a, **kw):
        before = {k: int(v.get("size", 0) or 0) for k, v in pops.items()}
        st = real(p, pops, buildings, cfg, *a, **kw)
        after = {k: int(v.get("size", 0) or 0) for k, v in pops.items()}
        seen.append((dict(st), before, after, buildings))
        return st

    monkeypatch.setattr(se, "apply_employment_flow", _wrap)

    s = GameState("史实")
    p = s.prefectures["两浙路"]
    p["buildings"] = {"工坊": 2, "商铺": 1}        # 旧（座数）格式：宋侧现状写入格式
    # 人为压缩非农 POP 以**造出真实空岗**：宋侧真实量级下（工匠数十万 vs 工坊 320 岗）
    # 岗位常年坐满、空岗恒为 0，空岗拉不会发生 —— 本用例要验证的是「接线与守恒」，
    # 故显式造出空岗；"真实量级下不动"这一事实由 `test_song_default_disables_unemployed_push`
    # 与长局探针覆盖。
    p["pops"]["工匠"]["size"] = 10
    p["pops"]["商人"]["size"] = 5
    random.seed(11)
    _settle_economy(s, [])
    assert seen, "接线未被执行（防『写了没接上』）"
    # 只有「本月有建筑」的路才会走到迁移分支（其余路 buildings 为空 → 全 0 读数）
    active = [(st, b, a) for st, b, a, bld in seen if bld]
    assert active, f"有建筑的 两浙路 必须进入岗位流动分支：{seen[:3]}"
    moved_any = 0
    for st, before, after in active:
        moved = st["moved_to_artisan"] + st["moved_to_merchant"]
        back = st["returned_to_farm"]
        # 不变量：两方向**串行互斥** → 同路同月绝不同时为正
        assert not (moved > 0 and back > 0), f"同路同月双向迁移：{st}"
        # 宋侧默认关闭「失业推」（SONG_JOB_PUSH_UNEMPLOYED=False）→ 本场景不得回流
        assert back == 0, f"默认策略下不得发生失业回流：{st}"
        moved_any += moved
        # 只动 农/工匠/商人，且逐字守恒
        for k in before:
            if k not in ("农", "工匠", "商人"):
                assert after[k] == before[k], f"{k} size 被岗位流动改动"
        assert (after["农"] - before["农"]) + (after["工匠"] - before["工匠"]) \
            + (after["商人"] - before["商人"]) == 0, f"ΣPOP 不守恒：{st}"
        assert after["农"] == before["农"] - moved + back
        if st["moved_to_artisan"]:
            assert after["工匠"] - before["工匠"] == st["moved_to_artisan"]
        if st["moved_to_merchant"]:
            assert after["商人"] - before["商人"] == st["moved_to_merchant"]
        if back:
            assert after["工匠"] <= before["工匠"] and after["商人"] <= before["商人"]
    # 审计痕迹（有迁移才写）
    assert moved_any > 0, "工坊有真实空岗 → 应至少发生一次农→工匠迁移（防『接了没生效』）"
    flow = (p.get("econ_audit") or {}).get("job_flow")
    assert flow, "有工坊空岗时必须留下岗位流动痕迹"


def test_employment_flow_moves_wealth_conservingly():
    """迁移**带财富/粮**（B1d-b：人均连续），但 `Σwealth`/`Σgrain` 跨池**不变**（纯内部转移）。

    2026-09-27 语义变更：原实现"只搬人、钱粮不动"会让迁出/迁入池**人均**失真
    （一次大流动即造成人均假信号，污染消费/生计/派系读数），故改为按**人均份额**随迁；
    本用例锁定"随迁但守恒"，防止改回"净身出户"或凭空造钱。
    """
    pops = _pops()
    for v in pops.values():
        v["wealth"] = 1234
        v["grain"] = 567
    w0 = sum(v["wealth"] for v in pops.values())
    g0 = sum(v["grain"] for v in pops.values())
    apply_employment_flow({"pops": pops}, pops, {"工坊": {"lv": 3}}, CFG)
    assert sum(v["wealth"] for v in pops.values()) == w0, "wealth 总量必须守恒（不得凭空增减）"
    assert sum(v["grain"] for v in pops.values()) == g0, "grain 总量必须守恒"
    assert any(v["wealth"] != 1234 for v in pops.values()), "应有池的财富随人迁移而变化"
