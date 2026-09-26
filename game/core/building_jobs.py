# -*- coding: utf-8 -*-
"""宋祚 · 建筑-岗位-就业模型（批 4 · 外邦省域产业链设计 §3）。

**定位**：三政权（辽/西夏/大理）省域经济的产出骨架——6 类建筑、岗位轨就业、
两轨制产出（轨 A 粮不占岗 / 轨 B 13 维原料+成品走岗位）、等级演化（去折旧）。

纪律（设计 §1 总原则）：
- POP 挂载律：钱/人只挂 POP；实物只挂州/府 `resources` 或政权 `resources_regime`；
- 产量是唯一增量；等级加成、灾害折产都作用于产量，不另开账本；
- 整数尾差归末位建筑/最大池，守恒断言进回归；
- 上岗人数是月度视图，**不改 POP `size`**（就业流动另走 `JOB_FLOW_RATE` 阶层迁移）。
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "jobs_of", "allocate_employment", "produce_grain_track",
    "produce_job_track", "evolve_building_levels", "job_flow_unemployed",
    "pay_wages_from_revenue", "pay_construction_cost", "apply_bankruptcy",
    "song_job_cfg", "apply_employment_flow", "live_job_buildings",
]

_LV_MIN_DEFAULT = 1
_LV_MAX_DEFAULT = 5

# ---------------------------------------------------------------------------
# 宋侧岗位口径（宋祚 · 就业驱动阶层流动 §宋侧接线）
# ---------------------------------------------------------------------------
# 为何不写进 content/data*.py：本表是**岗位模型的宋侧标定**，与外邦
# `content/data_external.EXTERNAL_ECON` 的 6 类建筑表分属两套建筑命名
# （宋侧 `POP_BUILDING_TYPES` = 农田/工坊/商铺/庄园）。为不改动
# `content/data_constants.py`（边界：并行改动），此处就近定义；待「停用词/常量表」
# 统一（单源化）时再迁出——迁移时须同时改 `song_job_cfg` 一处即可。
SONG_JOB_CLASSES = ("农", "工匠", "商人")
SONG_JOB_SHARE_DEFAULT = 0.35          # 农可上岗比例上限（农田+庄园用工上限）
SONG_JOB_FLOW_RATE = 0.02              # 月迁移率（与 `JOB_FLOW_RATE` 同口径）
SONG_JOBS_PER_LEVEL = {                # 岗位数 = lv × 每级岗位（农田 0——粮维豁免岗位制）
    "农田": 0, "工坊": 160, "商铺": 40, "庄园": 120,
}
SONG_BUILDING_WORKER = {               # 岗位归属 POP（农职岗 / 工匠岗 / 商人岗）
    "农田": "农", "庄园": "农", "工坊": "工匠", "商铺": "商人",
}
SONG_JOB_QUEUE_FARM = ("农田", "庄园")
SONG_JOB_QUEUE_ARTISAN = ("工坊",)     # 只有工匠岗进工匠岗序（商铺是商人岗，见下）
SONG_JOB_QUEUE_MERCHANT = ("商铺",)    # 商人岗序（`allocate_employment` 兜底按 worker 类型喂池）

_SONG_BASECFG: Optional[dict] = None


def song_job_cfg() -> dict:
    """宋侧岗位配置（含外邦同名字段作并集兜底）。

    返回**新 dict**（每次调用独立），调用侧可自由增改而不污染全局；
    `JOBS_PER_LEVEL`/`BUILDING_WORKER`/`JOB_QUEUE_*` 均以宋侧标定为权威。
    """
    global _SONG_BASECFG
    if _SONG_BASECFG is None:
        base: dict = {}
        try:                                   # 外邦表作并集兜底（缺字段时不 KeyError）
            from content.data_external import EXTERNAL_ECON as _EXT
            base = dict(_EXT)
        except Exception:                      # noqa: BLE001
            base = {}
        _SONG_BASECFG = base
    cfg = dict(_SONG_BASECFG)
    cfg["JOBS_PER_LEVEL"] = dict(SONG_JOBS_PER_LEVEL)
    cfg["BUILDING_WORKER"] = dict(SONG_BUILDING_WORKER)
    cfg["JOB_QUEUE_FARM"] = tuple(SONG_JOB_QUEUE_FARM)
    cfg["JOB_QUEUE_ARTISAN"] = tuple(SONG_JOB_QUEUE_ARTISAN)
    cfg["JOB_QUEUE_MERCHANT"] = tuple(SONG_JOB_QUEUE_MERCHANT)
    share = dict((_SONG_BASECFG.get("JOB_SHARE") or {}))
    share["宋"] = SONG_JOB_SHARE_DEFAULT
    share["default"] = SONG_JOB_SHARE_DEFAULT
    cfg["JOB_SHARE"] = share
    # 显式口径：宋侧调用不以 rtype 取 share（`allocate_employment` 优先读此项），
    # 避免「调用侧漏传 rtype → 回落到外邦 default(0.25)」的静默偏差。
    cfg["JOB_SHARE_OVERRIDE"] = SONG_JOB_SHARE_DEFAULT
    cfg["JOB_FLOW_RATE"] = SONG_JOB_FLOW_RATE
    return cfg


def _lv(entry: Any) -> int:
    """建筑条目 → 等级；兼容旧 `{名: 座数}`（座数当 lv 用，≤5 封顶）。"""
    if isinstance(entry, dict):
        try:
            return int(entry.get("lv", 1) or 1)
        except (TypeError, ValueError):
            return _LV_MIN_DEFAULT
    try:
        return max(_LV_MIN_DEFAULT, min(_LV_MAX_DEFAULT, int(entry or 1)))
    except (TypeError, ValueError):
        return _LV_MIN_DEFAULT


def jobs_of(buildings: dict, cfg: dict) -> Dict[str, int]:
    """各类建筑岗位数 = lv × JOBS_PER_LEVEL（粮田 0——粮维豁免岗位制）。"""
    jpl = cfg.get("JOBS_PER_LEVEL") or {}
    out: Dict[str, int] = {}
    for bt, entry in (buildings or {}).items():
        if bt not in jpl:
            continue
        out[bt] = max(0, _lv(entry) * int(jpl.get(bt, 0) or 0))
    return out


def allocate_employment(pops: dict, buildings: dict, cfg: dict,
                        rtype: str = "") -> Dict[str, int]:
    """优先队列就业分配（§3.3）：返回 {建筑类型: 在岗数}。

    - 农职岗序：牧场 → 桑麻田 → 林果蔗田（竞争农剩余劳动力，上限 `JOB_SHARE`）；
    - 工匠岗序：工坊 → 矿场（全量工匠可上岗）；
    - 商人岗序：`JOB_QUEUE_MERCHANT`（宋侧 `商铺`；外邦未配置 → 空表，行为不变）；
    - 同月内不重复计入；余工 = 未上岗人数（派生读数，不落账）。
    """
    jobs = jobs_of(buildings, cfg)
    worker_of = cfg.get("BUILDING_WORKER") or {}
    # `JOB_SHARE_OVERRIDE`（宋侧显式入参口径）优先；否则按 rtype 取表
    _ov = cfg.get("JOB_SHARE_OVERRIDE")
    job_share = float(_ov) if _ov is not None else float(
        (cfg.get("JOB_SHARE") or {}).get(rtype,
        (cfg.get("JOB_SHARE") or {}).get("default", 0.25)))
    staffed: Dict[str, int] = {bt: 0 for bt in jobs}

    # 农剩余劳动力（口粮之外可投入）
    nong_sz = int((pops.get("农") or {}).get("size", 0) or 0)
    farm_pool = int(nong_sz * job_share)
    for bt in cfg.get("JOB_QUEUE_FARM") or ():
        if bt not in jobs or jobs[bt] <= 0 or farm_pool <= 0:
            continue
        n = min(jobs[bt], farm_pool)
        staffed[bt] = n
        farm_pool -= n

    # 工匠全量
    art_sz = int((pops.get("工匠") or {}).get("size", 0) or 0)
    art_pool = art_sz
    for bt in cfg.get("JOB_QUEUE_ARTISAN") or ():
        if bt not in jobs or jobs[bt] <= 0 or art_pool <= 0:
            continue
        n = min(jobs[bt], art_pool)
        staffed[bt] = n
        art_pool -= n

    # 商人岗序（宋侧 `商铺`；外邦未配置 → 空表，行为不变）
    mer_sz = int((pops.get("商人") or {}).get("size", 0) or 0)
    mer_pool = mer_sz
    for bt in cfg.get("JOB_QUEUE_MERCHANT") or ():
        if bt not in jobs or jobs[bt] <= 0 or mer_pool <= 0:
            continue
        n = min(jobs[bt], mer_pool)
        staffed[bt] = n
        mer_pool -= n

    # 显式按 worker 类型兜底（防岗序表漏项）
    for bt, j in jobs.items():
        if staffed.get(bt, 0) > 0 or j <= 0:
            continue
        wk = worker_of.get(bt, "")
        if wk == "农":
            if farm_pool > 0:
                n = min(j, farm_pool)
                staffed[bt] = n
                farm_pool -= n
        elif wk == "工匠":
            if art_pool > 0:
                n = min(j, art_pool)
                staffed[bt] = n
                art_pool -= n
        elif wk == "商人":
            if mer_pool > 0:
                n = min(j, mer_pool)
                staffed[bt] = n
                mer_pool -= n
    return staffed


def produce_grain_track(pops: dict, buildings: dict, cfg: dict,
                        gy: float, rtype: str = "") -> int:
    """轨 A——生计轨（粮，全员有效，不占岗）：农 size × 人均粮 × 粮田效率乘数。

    返回本月产粮（int）；写入农 POP `grain`（调用侧负责 eaten/市场，本函数只产）。
    灾害折产由调用侧把 `gy` 打折后传入。
    """
    nong = pops.get("农")
    if not isinstance(nong, dict):
        return 0
    sz = int(nong.get("size", 0) or 0)
    if sz <= 0:
        return 0
    farm_lv = _lv((buildings or {}).get("粮田", 1))
    eff = 1.0 + float(cfg.get("FARM_LV_EFF", 0.05)) * max(0, farm_lv - 1)
    g = int(sz * float(gy) * eff)
    nong["grain"] = int(nong.get("grain", 0) or 0) + g
    return g


def produce_job_track(pops: dict, buildings: dict, cfg: dict,
                      rtype: str = "", staffed: Optional[Dict[str, int]] = None,
                      resources: Optional[dict] = None,
                      goods_pool: Optional[dict] = None) -> Dict[str, int]:
    """轨 B——岗位轨（其余 13 维原料 + 全部成品）：Σ staffed × 单位产出 × 等级加成。

    - 原料维（13 维）→ `resources`（州/府物资仓，调用侧传入 dict）；
    - 成品维（工坊配方产物）→ `goods_pool`（工匠 goods 池，调用侧传入 dict）。
    返回 {维: 本月产量}；整数尾差归末位建筑（本实现按建筑序累加，自然落在末位）。
    """
    if staffed is None:
        staffed = allocate_employment(pops, buildings, cfg, rtype)
    table = (cfg.get("PER_WORKER_OUTPUT") or {}).get(
        rtype, (cfg.get("PER_WORKER_OUTPUT") or {}).get("default", {}))
    lv_bonus = float(cfg.get("LV_OUTPUT_BONUS", 0.05))
    produced: Dict[str, int] = {}
    raw_dims = set(cfg.get("RAW_DIMS") or ())
    for bt in table:
        n = int(staffed.get(bt, 0) or 0)
        if n <= 0:
            continue
        lv = _lv((buildings or {}).get(bt, 1))
        mult = 1.0 + lv_bonus * max(0, lv - 1)
        for dim, rate in (table.get(bt) or {}).items():
            q = int(n * float(rate) * mult)
            if q <= 0:
                continue
            produced[dim] = produced.get(dim, 0) + q
            # 原料进州/府仓；成品进工匠 goods 池（单一产出通道原则）
            if dim in raw_dims and isinstance(resources, dict):
                resources[dim] = int(resources.get(dim, 0) or 0) + q
            elif isinstance(goods_pool, dict):
                goods_pool[dim] = int(goods_pool.get(dim, 0) or 0) + q
    return produced


def evolve_building_levels(prov: dict, cfg: dict, *, surplus: bool = False,
                           famine: bool = False, arrears: bool = False,
                           staffed: Optional[Dict[str, int]] = None,
                           idle_streak: Optional[Dict[str, int]] = None,
                           rng: Optional[random.Random] = None
                           ) -> List[dict]:
    """建筑等级演化（§3.4 · 去折旧）：升级/降级都是事件，不是时间衰减。

    - 升级：省域上月结余 > 0 且当月无饥荒 → 月 `BUILDING_UPGRADE_PROB` 概率择一类 lv+1；
    - 降级：① 灾荒 → 随机一类 lv−1；② 欠饷 → 牧场/工坊优先 lv−1；
            ③ 持续空置（在岗率 <40% 连续 3 月）→ 该类 lv−1；
    - 节流：同一州/府同月最多 1 次降级事件；
    - 返回 `[{type, Δlv, reason}]` 供 `econ_audit["building_lv_changes"]`。
    """
    R = rng or random
    buildings = prov.get("buildings") or {}
    if not buildings:
        return []
    jpl = cfg.get("JOBS_PER_LEVEL") or {}
    lv_min = int(cfg.get("BUILDING_LV_MIN", _LV_MIN_DEFAULT))
    lv_max = int(cfg.get("BUILDING_LV_MAX", _LV_MAX_DEFAULT))
    changes: List[dict] = []
    downgraded = False

    def _set(bt: str, new_lv: int, reason: str, delta: int) -> None:
        nonlocal downgraded
        entry = buildings.get(bt)
        if isinstance(entry, dict):
            entry["lv"] = new_lv
        else:
            buildings[bt] = {"lv": new_lv}
        changes.append({"type": bt, "delta_lv": delta, "reason": reason})
        if delta < 0:
            downgraded = True

    # ③ 持续空置降级（先于灾荒/欠饷，原因最具体）
    if isinstance(idle_streak, dict) and isinstance(staffed, dict):
        idle_months = int(cfg.get("BUILDING_IDLE_MONTHS", 3))
        idle_rate = float(cfg.get("BUILDING_IDLE_RATE", 0.4))
        for bt, streak in list(idle_streak.items()):
            if streak < idle_months or downgraded:
                continue
            jobs = max(1, _lv(buildings.get(bt, 1)) * int(jpl.get(bt, 0) or 0))
            rate = int(staffed.get(bt, 0) or 0) / jobs if jobs else 0
            if rate < idle_rate:
                cur = _lv(buildings.get(bt, 1))
                if cur > lv_min:
                    _set(bt, cur - 1, "持续空置", -1)

    # ① 灾荒降级（随机一类）
    if famine and not downgraded:
        cands = [bt for bt in buildings if _lv(buildings[bt]) > lv_min]
        if cands:
            bt = R.choice(cands)
            _set(bt, _lv(buildings[bt]) - 1, "灾荒", -1)

    # ② 欠饷降级（牧场/工坊优先）
    if arrears and not downgraded:
        for bt in ("牧场", "工坊"):
            if bt in buildings and _lv(buildings[bt]) > lv_min:
                _set(bt, _lv(buildings[bt]) - 1, "欠饷", -1)
                break

    # 升级（结余>0 且无饥荒；月 5% 概率择一类）
    if surplus and not famine and R.random() < float(cfg.get("BUILDING_UPGRADE_PROB", 0.05)):
        cands = [bt for bt in buildings if _lv(buildings[bt]) < lv_max]
        if cands:
            bt = R.choice(cands)
            _set(bt, _lv(buildings[bt]) + 1, "结余营造", +1)

    return changes


def job_flow_unemployed(pops: dict, staffed: Dict[str, int], cfg: dict,
                        buildings: dict, rtype: str = "",
                        rng: Optional[random.Random] = None) -> Dict[str, int]:
    """就业驱动的阶层流动（§3.6）：失业农→工匠/商人；失业工匠→农（生计兜底）。

    约束：Σ六类 size 守恒（整数尾差归迁出方）；返回 `{flow_out, flow_in, unemployed}`。
    **不改 total**——只在农/工匠/商人三类间迁移 size。
    """
    R = rng or random
    rate = float(cfg.get("JOB_FLOW_RATE", 0.02))
    if rate <= 0:
        return {"flow_out": 0, "flow_in": 0, "unemployed": 0}
    worker_of = cfg.get("BUILDING_WORKER") or {}
    job_share = float((cfg.get("JOB_SHARE") or {}).get(rtype,
                      (cfg.get("JOB_SHARE") or {}).get("default", 0.25)))

    nong = pops.get("农")
    art = pops.get("工匠")
    mer = pops.get("商人")
    if not isinstance(nong, dict) or not isinstance(art, dict):
        return {"flow_out": 0, "flow_in": 0, "unemployed": 0}

    # 失业数：可上岗 − 实际在岗（农剩余劳动力池 / 工匠全量）
    farm_jobs = sum(int(staffed.get(bt, 0) or 0)
                    for bt, wk in worker_of.items() if wk == "农")
    art_jobs = sum(int(staffed.get(bt, 0) or 0)
                   for bt, wk in worker_of.items() if wk == "工匠")
    nong_sz = int(nong.get("size", 0) or 0)
    art_sz = int(art.get("size", 0) or 0)
    farm_idle = max(0, int(nong_sz * job_share) - farm_jobs)
    art_idle = max(0, art_sz - art_jobs)

    flow_out = 0
    # 失业农 → 工匠/商人（若该省有空岗或商路）
    if farm_idle > 0 and isinstance(mer, dict):
        move = int(farm_idle * rate)
        if move > 0:
            # 有工坊空岗 → 转工匠；否则转商人
            art_open = sum(max(0, _lv(buildings.get(bt, 1)) * int((cfg.get("JOBS_PER_LEVEL") or {}).get(bt, 0) or 0)
                               - int(staffed.get(bt, 0) or 0))
                           for bt, wk in worker_of.items() if wk == "工匠")
            target = art if art_open > 0 else mer
            nong["size"] = nong_sz - move
            target["size"] = int(target.get("size", 0) or 0) + move
            flow_out = move

    # 失业工匠 → 农（生计兜底：回农即回口粮轨）
    flow_in = 0
    if art_idle > 0:
        move = int(art_idle * rate)
        if move > 0:
            art2 = int(art.get("size", 0) or 0)
            nong2 = int(nong.get("size", 0) or 0)
            move = min(move, art2)
            art["size"] = art2 - move
            nong["size"] = nong2 + move
            flow_in = move

    total_unemp = farm_idle + art_idle
    return {"flow_out": flow_out, "flow_in": flow_in, "unemployed": total_unemp}


# ---------------------------------------------------------------------------
# 宋侧接线：就业驱动的阶层流动（与既有城市化/回乡通道协同，不双计）
# ---------------------------------------------------------------------------
def live_job_buildings(buildings: Optional[dict], cfg: dict,
                       lv_min: Optional[int] = None) -> Tuple[Dict[str, Any], bool]:
    """筛出「本月真在册且岗位 > 0」的岗位建筑，返回 `(live, has_job_building)`。

    - `live`：`{建筑类型: 条目}`——只含**岗位表内**（`JOBS_PER_LEVEL` ∩ `BUILDING_WORKER`）
      且**未倒闭、`lv >= lv_min`** 的条目；可直接喂 `allocate_employment`。
    - `has_job_building`：本月是否存在**岗位建筑条目**（无论 `lv` 是否为 0）——
      用于区分两种「没岗位」：① 根本没有岗位建筑（新局 `{}`／只有政府工程）→ 通道不生效；
      ② 有岗位建筑但 `lv == 0`（裁撤/毁损）→ 岗位归零，失业推应当生效。
    - `lv == 0` 必须**显式判零**：`_lv()` 按「缺省 1」口径把 0 归一为 1（`or 1`），
      直接用它会漏掉裁撤（设计 §3.4「降级/倒闭是事件」）。
    """
    worker_of = cfg.get("BUILDING_WORKER") or {}
    jpl = cfg.get("JOBS_PER_LEVEL") or {}
    _min = _LV_MIN_DEFAULT if lv_min is None else int(lv_min)
    live: Dict[str, Any] = {}
    has_job_building = False
    for bt, entry in (buildings or {}).items():
        if bt not in jpl or bt not in worker_of:
            continue                              # 非岗位表建筑（政府工程/外邦建筑）
        if isinstance(entry, dict) and entry.get("closed"):
            continue                              # 倒闭建筑不计岗位（同 job 模式口径）
        has_job_building = True
        raw_lv = entry.get("lv") if isinstance(entry, dict) else entry
        if raw_lv is None:
            raw_lv = 1
        if int(raw_lv) < _min:
            continue                              # 岗位归零：不进 live，但仍是「有岗位建筑」
        live[bt] = entry
    return live, has_job_building


def apply_employment_flow(p: dict, pops: dict, buildings: Optional[dict],
                          cfg: dict, rng: Optional[random.Random] = None
                          ) -> Dict[str, int]:
    """宋侧「岗位缺口驱动」阶层流动：农 ↔ 工匠/商人，逐路执行（ΣPOP 守恒）。

    设计依据：`外邦省域产业链设计_2026-09-22.md` §3.6 与 §15.1 决策 #6
    「加就业驱动（**失业推＋空岗拉＋回农兜底**）」。与外邦 `job_flow_unemployed`
    的差别（为何另开函数而不改它）：
      · 外邦是**省域**视图，「无空岗也转商」是省域口径；宋侧要求「岗位不足时
        不迁移、只补缺口」（空岗拉），故另立；
      · 外邦调用点已上链，改其语义会漂移外邦长局守恒基线。

    规则（两方向**串行**，同一路同一月只有一个方向 → 不存在同一人两次迁移）：
      ① **空岗拉**：目标岗空缺 = `lv×JOBS_PER_LEVEL − 在岗`（按 POP 归属建筑，
         `allocate_employment` 优先队列）；农闲 = `int(农 size × JOB_SHARE) − 农在岗`。
         `农闲>0` 且有空缺 → `min(农闲×JOB_FLOW_RATE, 空缺)` 农转工/商，按两类
         空缺比例分摊（整数尾差归商）；
      ② **失业推（回农兜底）**：① 不成立（无农闲或无空缺）时，工匠/商人中
         「未进任何岗位」者按 `JOB_FLOW_RATE` 回流农轨领口粮——这是生计安全阀
         （非农不产粮，无岗者只能买粮）。

    与既有通道**协同而不双计**：既有 `_settle_economy` 的城市化/回乡通道是
    「景气驱动」的量（先走），本通道**串行于其后**、只补「岗位缺口驱动」的差额；
    两方向互斥，故净额既非两侧相加、也不会把同一人算两次。

    守恒：只改 农/工匠/商人 三类 `size`，且逐字 `Δ农 + Δ工匠 + Δ商人 == 0`
    （`Σ六类 size` 不变）；每个迁移量都钳到来源 POP 的 `size`，不会抽成负数。

    返回 `{moved_to_artisan, moved_to_merchant, returned_to_farm, farm_idle,
    artisan_vacancy, merchant_vacancy}`（迁移量全 0 = 本月无岗位驱动迁移）。
    """
    _zero = {"moved_to_artisan": 0, "moved_to_merchant": 0,
             "returned_to_farm": 0, "farm_idle": 0,
             "artisan_vacancy": 0, "merchant_vacancy": 0}
    bld = buildings or {}
    if not bld:
        return dict(_zero)                       # 新局（buildings 空）→ 零迁移：基线不变
    _rate = float(cfg.get("JOB_FLOW_RATE", 0.0) or 0.0)
    if _rate <= 0:
        return dict(_zero)
    nong, art, mer = pops.get("农"), pops.get("工匠"), pops.get("商人")
    if not isinstance(art, dict):
        return dict(_zero)
    # 岗位只认「岗位表里有名且实际有 lv 建筑」的类型（结构 `{lv}` 与旧 `座数` 兼容）
    worker_of = cfg.get("BUILDING_WORKER") or {}
    jpl = cfg.get("JOBS_PER_LEVEL") or {}
    lv_min = int(cfg.get("BUILDING_LV_MIN", _LV_MIN_DEFAULT))
    live, has_job_building = live_job_buildings(bld, cfg, lv_min=lv_min)
    if not has_job_building:
        # 本月**没有任何岗位建筑条目**（新局 `buildings == {}`、或只有政府工程建筑）
        # → 零迁移。这是「新局行为逐字不变」的硬前提。
        # 注意：`live` 为空但 `has_job_building` 为真（`{"工坊": {"lv": 0}}` = 岗位被裁撤）
        # **不是**零迁移场景——那正是失业推（工/商→农）该生效的地方。
        return dict(_zero)

    share_tbl = cfg.get("JOB_SHARE") or {}
    _ov = cfg.get("JOB_SHARE_OVERRIDE")
    job_share = float(_ov) if _ov is not None else float(
        share_tbl.get("宋", share_tbl.get("default", 0.0)) or 0.0)
    staffed = allocate_employment(pops, live, cfg, "宋")

    nong_sz = int(nong.get("size", 0) or 0) if isinstance(nong, dict) else 0
    art_sz = int(art.get("size", 0) or 0)
    mer_sz = int(mer.get("size", 0) or 0) if isinstance(mer, dict) else 0

    def _pool_jobs(wk: str) -> Tuple[int, int]:
        """该 worker 类型的（岗位, 在岗）。"""
        jobs_n = sum(_lv(live[bt]) * int(jpl.get(bt, 0) or 0)
                     for bt, w in worker_of.items() if w == wk and bt in live)
        staff_n = sum(int(staffed.get(bt, 0) or 0)
                      for bt, w in worker_of.items() if w == wk)
        return jobs_n, staff_n

    farm_jobs, farm_staffed = _pool_jobs("农")
    artisan_jobs, artisan_staffed = _pool_jobs("工匠")
    merchant_jobs, merchant_staffed = _pool_jobs("商人")

    farm_pool = int(nong_sz * job_share)
    farm_idle = max(0, farm_pool - farm_staffed)
    artisan_vacancy = max(0, artisan_jobs - artisan_staffed)
    merchant_vacancy = max(0, merchant_jobs - merchant_staffed)
    # 非农失业 = 未进任何岗位的那部分（口径同设计 §3.6「未进工坊/矿场」）
    art_idle = max(0, art_sz - artisan_staffed)
    mer_idle = max(0, mer_sz - merchant_staffed)

    stats = {"moved_to_artisan": 0, "moved_to_merchant": 0, "returned_to_farm": 0,
             "farm_idle": farm_idle, "artisan_vacancy": artisan_vacancy,
             "merchant_vacancy": merchant_vacancy}

    if farm_idle > 0 and (artisan_vacancy > 0 or merchant_vacancy > 0) \
            and isinstance(mer, dict):
        # ① 空岗拉：农闲 → 工匠/商人，只补**真实空缺**（无空缺不迁移——与
        #    外邦「无空岗也转商」不同：宋侧既有城市化通道已管景气流向，本通道只补缺口）
        move = int(min(farm_idle, max(1, int(farm_idle * _rate))))
        take = min(move, farm_idle, nong_sz, artisan_vacancy + merchant_vacancy)
        if take <= 0:
            return stats
        open_total = artisan_vacancy + merchant_vacancy
        to_art = min(artisan_vacancy, int(take * artisan_vacancy / open_total))
        to_mer = take - to_art                      # 整数尾差归商（开店门槛低）
        to_art = min(to_art, artisan_vacancy)
        to_mer = min(to_mer, merchant_vacancy)
        if to_mer < 0:
            to_mer = 0
        applied = to_art + to_mer
        if applied <= 0:
            return stats
        nong["size"] = nong_sz - applied
        if to_art > 0:
            art["size"] = art_sz + to_art
        if to_mer > 0:
            mer["size"] = mer_sz + to_mer
        stats["moved_to_artisan"] = to_art
        stats["moved_to_merchant"] = to_mer
        return stats

    # ② 失业推（生计兜底）：本月无农闲（或空岗拉未落地）而工匠/商人**未进任何岗位**
    #    → 按 `JOB_FLOW_RATE` 回流农轨领口粮。口径同设计 §3.6「失业工匠 → 农」
    #    ＝「未进工坊/矿场」，即没有岗位容纳的那部分非农人口（生计安全阀）；
    #    回流按未在岗比例分摊，上限制到来源 POP size（不得抽成负数）。
    pool_sz = art_sz + mer_sz
    idle_sz = art_idle + mer_idle
    if idle_sz <= 0 or pool_sz <= 0 or not isinstance(nong, dict):
        return stats
    back = min(int(min(idle_sz, max(1, int(idle_sz * _rate)))), pool_sz)
    if back <= 0:
        return stats
    from_art = min(art_idle, int(back * art_idle / idle_sz))
    from_mer = min(mer_idle, back - from_art)
    applied = from_art + from_mer
    if applied <= 0:
        return stats
    if from_art > 0:
        art["size"] = art_sz - from_art
    if from_mer > 0:
        mer["size"] = mer_sz - from_mer
    nong["size"] = nong_sz + applied
    stats["returned_to_farm"] = applied
    return stats


# ---------------------------------------------------------------------------
# 批 4 余下：工资发放 / 营造出资回流 / 轻量倒闭（§6.1–§6.3）
# ---------------------------------------------------------------------------

def pay_wages_from_revenue(pops: dict, buildings: dict, cfg: dict,
                           staffed: Dict[str, int], revenue: int,
                           rtype: str = "") -> Dict[str, int]:
    """雇佣与发薪（§6.1）：建筑营收 → 工资池 → 在岗 POP wealth。

    - 工资池 = min(revenue, Σ 在岗工 × WAGE_RATE[type][岗位])；
    - 发薪按建筑类型分给对应 worker POP（农/工匠），**只有上岗者分**；
    - 欠薪记 `arrears`（返回值），在岗工只拿实发（revenue 不足时按比例折）；
    - 钱守恒：Σ 发薪 + 欠薪 == 工资应付；revenue 超出工资池的部分返回 `profit`
      （由调用侧转士绅 POP 或商人运费分成，**不在此烧钱**）。
    """
    wages_tbl = (cfg.get("WAGE_RATE") or {}).get(
        rtype, (cfg.get("WAGE_RATE") or {}).get("default", {}))
    worker_of = cfg.get("BUILDING_WORKER") or {}
    # 工资应付 = Σ staffed[bt] × wage[bt]
    owed_by_worker: Dict[str, int] = {}
    total_owed = 0
    for bt, n in staffed.items():
        if n <= 0:
            continue
        wage = float(wages_tbl.get(bt, 1.0))
        owed = int(n * wage)
        if owed <= 0:
            continue
        wk = worker_of.get(bt, "工匠")
        owed_by_worker[wk] = owed_by_worker.get(wk, 0) + owed
        total_owed += owed

    paid_total = 0
    arrears = 0
    scale = 1.0 if total_owed <= 0 else min(1.0, revenue / total_owed)
    for wk, owed in owed_by_worker.items():
        slot = pops.get(wk)
        if not isinstance(slot, dict):
            continue
        paid = int(owed * scale)
        if paid > 0:
            slot["wealth"] = int(slot.get("wealth", 0) or 0) + paid
            paid_total += paid
    arrears = max(0, total_owed - paid_total)
    profit = max(0, revenue - paid_total)
    return {"wages_paid": paid_total, "wages_owed": total_owed,
            "arrears_building": arrears, "profit": profit}


def pay_construction_cost(pops: dict, cfg: dict, building_type: str,
                          new_lv: int, treasury: dict,
                          gentry_key: str = "士绅",
                          artisan_key: str = "工匠") -> Dict[str, int]:
    """营造费与出资（§3.5 · 外邦禁 burn）：升级费全额**转给工匠 POP wealth**。

    出资顺序：① 本省士绅 POP wealth；② 不足 → 政权 treasury 补（调用侧传入
    `treasury` dict（如 `{"amount": n}`）或直接传 state 片段）。
    返回 `{cost, from_gentry, from_treasury, funded}`；`funded=False` 表示出资不足未落地。
    """
    cost_tbl = cfg.get("BUILDING_COST") or {}
    growth = float(cfg.get("BUILDING_COST_GROWTH", 1.35))
    base = float(cost_tbl.get(building_type, 10000))
    cost = int(base * (growth ** max(0, int(new_lv) - 1)))
    gentry = pops.get(gentry_key)
    artisan = pops.get(artisan_key)
    if not isinstance(artisan, dict):
        return {"cost": cost, "from_gentry": 0, "from_treasury": 0, "funded": False}
    g_have = int(gentry.get("wealth", 0) or 0) if isinstance(gentry, dict) else 0
    t_have = int(treasury.get("amount", 0) or 0) if isinstance(treasury, dict) else 0
    from_g = min(g_have, cost)
    from_t = min(t_have, cost - from_g)
    funded = (from_g + from_t) >= cost
    if not funded:
        return {"cost": cost, "from_gentry": 0, "from_treasury": 0, "funded": False}
    if isinstance(gentry, dict) and from_g > 0:
        gentry["wealth"] = g_have - from_g
    if isinstance(treasury, dict) and from_t > 0:
        treasury["amount"] = t_have - from_t
    # 全额转给工匠（含 treasury 补出部分）——不得注销/burn
    artisan["wealth"] = int(artisan.get("wealth", 0) or 0) + cost
    return {"cost": cost, "from_gentry": from_g, "from_treasury": from_t, "funded": True}


def apply_bankruptcy(prov: dict, cfg: dict, arrears_building: int,
                     staffed: Optional[Dict[str, int]] = None,
                     rng: Optional[random.Random] = None) -> List[dict]:
    """轻量倒闭（§6.3）：连续 2 月欠薪 → 解雇 20% 在岗 + lv−1；lv=0 且欠薪 → closed。

    - `prov["building_arrears_streak"]` 记连续欠薪月数（dict[建筑类型]）；
    - `prov["buildings"][bt]["closed"] = True` 标记倒闭（岗位 0）；
    - 恢复：省域结余 + 无欠薪 → 士绅可重新出资 → lv1（`pay_construction_cost` 负责出资）。
    返回 `[{type, action, detail}]` 供 audit。
    """
    R = rng or random
    buildings = prov.get("buildings") or {}
    if not buildings:
        return []
    streak = prov.setdefault("building_arrears_streak", {})
    lv_min = int(cfg.get("BUILDING_LV_MIN", _LV_MIN_DEFAULT))
    events: List[dict] = []

    if arrears_building > 0:
        for bt in buildings:
            streak[bt] = int(streak.get(bt, 0) or 0) + 1
    else:
        for bt in buildings:
            streak[bt] = 0

    for bt in list(buildings.keys()):
        entry = buildings[bt]
        if not isinstance(entry, dict):
            continue
        if entry.get("closed"):
            continue
        s = int(streak.get(bt, 0) or 0)
        if s < 2:
            continue
        cur = _lv(entry)
        # 解雇 20% 在岗工（月度视图，不改 size——由 job_flow 阶层迁移消化）
        if isinstance(staffed, dict) and staffed.get(bt, 0) > 0:
            layoff = int(staffed[bt] * 0.2)
            if layoff > 0:
                staffed[bt] = max(0, staffed[bt] - layoff)
                events.append({"type": bt, "action": "layoff", "detail": f"欠薪裁员 {layoff}"})
        if cur > lv_min:
            entry["lv"] = cur - 1
            events.append({"type": bt, "action": "downgrade", "detail": "连续欠薪降级"})
        elif cur <= lv_min and arrears_building > 0:
            entry["closed"] = True
            entry["lv"] = 0
            events.append({"type": bt, "action": "closed", "detail": "lv=0 且持续欠薪，倒闭"})
        streak[bt] = 0   # 事件后清零，重新计连续月
    return events
