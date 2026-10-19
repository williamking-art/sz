# -*- coding: utf-8 -*-
"""宋祚 · 官制吏制与资产维持（从 settlement_steps.py 拆出，零行为变更）。

`_settle_officialdom` / `_settle_clerks` / `_settle_clan` / `_settle_upkeep`。"""
from __future__ import annotations

# 官制 × POP 的受控流动入口（官额/吏额/在岗/待阙/祠禄；禁止直接改 pops["官僚"]["size"]）
from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add
from core.domains.administration import officialdom as _officialdom

from core.settlement_common import (
    distribute_cash,
)

def _settle_clan(state, log):
    """宗室俸禄（L2c money sink，宋代官制设计 §8.2 / 技术方案「宗室俸禄」行）。

    口径：**内帑出账**（史实宗室赡养由内帑/宗正寺支给），全额转入 `士绅` POP 的 `wealth`。
      `内帑 −paid`，`Σ士绅.wealth +paid` → **ΔM_ALL == 0**（纯转移，不造币）。
    按实付：内帑不足时只支可支部分，缺口记 `statistics["clan_arrears"]`（与欠饷/欠费同构）。

    为什么这是最有价值的一层 sink：宗室人口按 **3%/年复利** 膨胀，无需玩家做任何事，
    时间本身就是支出增量；而砍宗室要付皇威代价 → 天然的艰难抉择。
    """
    from content.data import CLAN_PAY_PER_MONTH

    _clan_by_route = []
    total_clan = 0
    for p in state.prefectures.values():
        shen = (p.get("pops") or {}).get("士绅")
        n = int((shen or {}).get("clan", 0) or 0) if isinstance(shen, dict) else 0
        if n > 0:
            _clan_by_route.append((p, n))
            total_clan += n
    if total_clan <= 0:
        return 0

    due = int(total_clan * CLAN_PAY_PER_MONTH)
    available = max(0, int(getattr(state, "imperial_treasury", 0) or 0))
    paid = min(due, available)
    if paid < due:
        state.statistics["clan_arrears"] = state.statistics.get("clan_arrears", 0) + (due - paid)
        log.append(f"[宗室] 内帑不足以赡宗室，欠支 {due - paid:,} 贯"
                   f"（应支 {due:,}，实支 {paid:,}）")
    if paid <= 0:
        return 0

    state.imperial_treasury -= paid
    # 按各宗室人口比例精确分配（末位吃尾差，保证 Σ入账 == paid）
    given = 0
    for i, (p, n) in enumerate(_clan_by_route):
        shen = p["pops"]["士绅"]
        g = (paid - given) if i == len(_clan_by_route) - 1 else int(paid * n / total_clan)
        g = max(0, int(g))
        # U0001f534 2026-10-08：改走桥接。路级 `wealth` 在已下沉档中是**派生镜像**，
        #   直写会被 `sync_route_pops` 撤销（赋福钱**收不到**）。
        #   未下沉时返回 None → 回退原路径，行为不变。
        if _pop_obj_add(state, shen, "wealth", g) is None:
            shen["wealth"] = int(shen.get("wealth", 0) or 0) + g
        given += g
    if given != paid:                       # 极端兜底：分配残差退回内帑
        state.imperial_treasury += paid - given
    log.append(f"[宗室] 赡宗室 {given:,} 贯（宗室 {total_clan:,} 口 × {CLAN_PAY_PER_MONTH:.0f} 贯，内帑出）")
    return given


def _settle_clerks(state, log):
    """Step 3.97 吏制结算（薄封装，实现在 `core/clerks.py`——单一权威源）。

    吏额由**政务量**驱动（脱离「官 × 8」）、吏禄不足 → **陋规**（民间三池 → 官僚 POP 的
    纯转移，零货币残差）、**把持度**与**吏怨**缓动，并导出「有效吏力」与吏治四档。
    """
    from core import clerks as _clerks
    return _clerks.settle_clerks(state, log)


def _run_personnel_cycle(state, log):
    """三年周期人事闭环：磨勘考课（turn % 36 == 18）。

    2026-10-18 全审接线（M300）：
      · **科举**由 `officialdom` 的科次年正月触发，委托 `imperial_exam.run_triennial_exam_full`
        （解试→省试→殿试全流程；`last_exam_year` 幂等）；
      · **磨勘**在此按回合节律触发（第 18/54/… 回合），委托
        `official_appraisal.run_triennial_appraisal`（上考/中考/下考、罢黜与祠禄冷冻）。
    幂等：`statistics.last_appraisal_turn` 防止同回合重复触发。
    失败只记 WARN 与 `personnel_cycle_error`，不阻断当月其余官制结算（可诊断、不静默）。
    """
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats
    turn = int(getattr(state, "turn", 0) or 0)
    if turn <= 0:
        return

    # 科举不在此处：由 officialdom 科次年正月走 `_triennial_exam_wired`
    # → `imperial_exam.run_triennial_exam_full`（避免双开科）。
    if turn >= 18 and turn % 36 == 18:
        last_appr = int(stats.get("last_appraisal_turn", 0) or 0)
        if turn > last_appr:
            try:
                from core.domains.administration.official_appraisal import (
                    run_triennial_appraisal,
                )
                result = run_triennial_appraisal(state, log)
                stats["last_appraisal_turn"] = turn
                stats["last_appraisal_summary"] = {
                    k: result.get(k) for k in
                    ("promoted", "demoted", "sinecure", "grades")
                    if k in result
                }
                log.append(
                    f"[磨勘] 三年考课：升 {result.get('promoted', 0)} / "
                    f"降 {result.get('demoted', 0)} / 祠禄 {result.get('sinecure', 0)}")
            except Exception as e:  # noqa: BLE001
                stats["personnel_cycle_error"] = f"appraisal:{type(e).__name__}:{e}"
                log.append(f"[磨勘][WARN] 三年考课推进失败：{e!r}")


def _run_annual_reclamation(state, log):
    """年度官方屯田垦荒：每年二月按 `gov_reclamation_share` 从国库拨款。

    2026-10-18 全审 P1-13：`reclaim_land_government` 此前零生产调用。
    默认 share=0 ⇒ 完全不改变现状；设为 >0 后按荒地占比向各路拨款，
    国库 → 本路农/工匠 POP 的守恒转移（不造币/不毁币），荒地 → 官田。
    """
    if int(getattr(state, "month", 0) or 0) != 2:
        return
    from core.domains.administration import institution as _inst
    share = float(_inst.get(state, "gov_reclamation_share", 0.0) or 0.0)
    if share <= 0.0:
        return
    budget = int(max(0.0, float(getattr(state, "treasury", 0) or 0)) * share)
    if budget <= 0:
        return
    from core.domains.economy.land_reclamation import (
        init_circuit_wasteland, get_circuit_wasteland, reclaim_land_government,
    )
    init_circuit_wasteland(state)
    prefs = getattr(state, "prefectures", {}) or {}
    cands = [(c, float(get_circuit_wasteland(state, c) or 0.0)) for c in prefs]
    cands = [(c, w) for c, w in cands if w > 0.0]
    if not cands:
        return
    total_w = sum(w for _, w in cands) or 1.0
    total_mu = 0.0
    spent = 0
    for c, w in cands:
        b = int(budget * w / total_w)
        if b <= 0:
            continue
        res = reclaim_land_government(state, c, target_mu=w, silver_funding=b)
        if res.get("ok"):
            total_mu += float(res.get("reclaimed_mu", 0) or 0)
            spent += int(res.get("cost_silver", 0) or 0)
    if total_mu > 0:
        stats = getattr(state, "statistics", None)
        if not isinstance(stats, dict):
            stats = {}
            state.statistics = stats
        stats["gov_reclamation_mu"] = float(stats.get("gov_reclamation_mu", 0.0) or 0.0) + total_mu
        stats["gov_reclamation_spent"] = int(stats.get("gov_reclamation_spent", 0) or 0) + spent
        log.append(
            f"[垦荒] 官方屯田年度开垦 {total_mu:,.1f} 亩（工本 {spent:,} 贯，国库→本路农/工匠）")


def _settle_officialdom(state, log):
    """Step 3.95 官制结算（薄封装，实现在 `core/domains/administration/officialdom.py`——单一权威源）。

    职责：旧档子池迁移修复 → 不变量校验（size == officials + clerks；
    officials == on_post + waiting + sinecure）→ 派生镜像同步（`p["officials"]`/`["clerks"]`
    的唯一写入点）→ 把冗官关键指标写进 `state.statistics` 供面板与审计读取。
    末尾接三年周期人事闭环（磨勘）与年度官方垦荒。
    """
    try:
        from core.personnel_order import settle_personnel_orders
        settle_personnel_orders(state)
    except Exception as e:  # noqa: BLE001 — 单条人事令失败不得炸整月
        log.append(f"[人事令] 结算失败：{type(e).__name__}: {e}")
    try:
        from core.impeachment import settle_impeachment_cases
        settle_impeachment_cases(state)
    except Exception as e:  # noqa: BLE001 — 弹劾案件失败不得炸整月
        log.append(f"[弹劾] 案件结算失败：{type(e).__name__}: {e}")
    result = _officialdom.settle_officialdom(state, log)
    _run_personnel_cycle(state, log)
    _run_annual_reclamation(state, log)
    return result


def _settle_upkeep(state, log):
    """资产维持费（L1 money sink，阶段 B-3）：建筑/工程/作坊/军械/城防 按月计维护费。

    设计依据：`BUILDING_STD[*]["maintain"] = 0.5%/月` 早已写定但**从未被消费**（死数据）。
    本步把它接上，并补齐其余资产类型的折算基准（单一权威源见 `content/data.py`）。

    口径：
      资产折算造价 = Σ(政府工程按等级造价) ＋ Σ(POP 建筑按等级造价)
                    ＋ 作坊数 × WORKSHOP_VALUE ＋ 武库件数 × EQUIP_UNIT_VALUE
                    ＋ Σ城防点 × FORT_VALUE
      本月维持费   = 资产折算造价 × ASSET_MAINTAIN_RATE

    守恒与纪律（POP 挂载律）：
      · 支出从**国库**出账（`change_treasury(-paid)`）；
      · 全额**支付给民间**（营造/修缮服务：工匠 40% ＋ 商人 60%，`distribute_cash` 精确守恒）；
      · 国库不足时**只按实付**（不穿底、不造币），缺口记 `statistics["upkeep_arrears"]`
        —— 与军俸的「欠饷」、税收的「欠税」科目同构。
    返回本月实付额。
    """
    from content.data import (BUILDING_STD, BUILDING_COST_GROWTH, WORKSHOP_VALUE,
                              EQUIP_UNIT_VALUE, FORT_VALUE, POP_BUILDING_VALUE,
                              ASSET_MAINTAIN_RATE, UPKEEP_PAY_TO)
    # 编制参数（阶段 C-7 / 财力消耗设计 S-D6）：玩家可经政令**主动降维持费**（裁汰冗费）。
    from core.domains.administration import institution as _inst
    _maintain_rate = float(ASSET_MAINTAIN_RATE) * _inst.get(state, "asset_maintain_mult")

    def _lv_cost(std: dict, lv: int) -> float:
        return float(std["base_cost"]) * (BUILDING_COST_GROWTH ** (max(1, int(lv)) - 1))

    asset_value = 0.0
    # 0) M34-①（财政顺序）：**水利**资产维护改由**地方经费**承担
    #    （`_settle_local_expenditure` 的水利腿，同一折算式与费率）⇒ 此处排除，防双重支付。
    from content.data import LOCAL_EXP_LOCAL_MAINTAINED
    # 1) 政府工程（projects）：类型命中 BUILDING_STD 时按等级造价
    for _pj in (getattr(state, "projects", {}) or {}).values():
        if not isinstance(_pj, dict):
            continue
        _name = str(_pj.get("name") or _pj.get("type") or "")
        if _name in LOCAL_EXP_LOCAL_MAINTAINED:
            continue
        _std = BUILDING_STD.get(_name)
        if _std:
            asset_value += _lv_cost(_std, _pj.get("level", 1))
    # 2) POP 建筑（按路）：命中 BUILDING_STD 用其 base_cost，否则用 POP_BUILDING_VALUE
    #    等级经统一读口 `building_jobs.building_level`（兼容标量 2 与结构 {"lv": 2}；
    #    散落的 int(lv) 遇结构会 TypeError 且此处位于月度结算路径 —— 2026-09-27 加固）
    from core.building_jobs import building_level as _bld_lv
    for _p in state.prefectures.values():
        for _bt, _lv in ((_p.get("buildings") or {})).items():
            if str(_bt) in LOCAL_EXP_LOCAL_MAINTAINED:
                continue                     # 地方承担维护（M34-①）
            _std = BUILDING_STD.get(str(_bt))
            _level = _bld_lv(_lv, 1)
            if _std:
                asset_value += _lv_cost(_std, _level)
            else:
                asset_value += POP_BUILDING_VALUE * max(1, _level)
    # 3) 作坊（酒坊/畜栏…）：按名义造价
    asset_value += len(getattr(state, "workshops", {}) or {}) * float(WORKSHOP_VALUE)
    # 4) 中央武库：按件折价
    _ca = getattr(state, "central_arsenal", None)
    if _ca is not None:
        asset_value += sum((getattr(_ca, "stock", {}) or {}).values()) * float(EQUIP_UNIT_VALUE)
    # 5) 城防：按点折价
    asset_value += sum((l.get("fortification", 0) or 0)
                       for l in getattr(state, "defense_lines", {}).values()) * float(FORT_VALUE)

    due = int(asset_value * _maintain_rate)
    if due <= 0:
        return 0

    available = max(0, int(getattr(state, "treasury", 0) or 0))
    paid = min(due, available)
    if paid < due:
        state.statistics["upkeep_arrears"] = \
            state.statistics.get("upkeep_arrears", 0) + (due - paid)
        log.append(f"[维持] 营造修葺欠费 {due - paid:,} 贯"
                   f"（应支 {due:,}，实支 {paid:,}；帑藏不足）")
    if paid <= 0:
        return 0

    state.change_treasury(-paid)
    _given = distribute_cash(state, paid, UPKEEP_PAY_TO)
    if _given != paid:                      # 极端兜底：无工匠/商人池时余额退回国库
        state.change_treasury(paid - _given)
    log.append(f"[维持] 资产维持费 {paid:,} 贯（资产折算 {asset_value:,.0f} 贯 ×"
               f" {_maintain_rate:.1%}/月）")
    return paid


