# -*- coding: utf-8 -*-
"""宋祚 · 官制吏制与资产维持（从 settlement_steps.py 拆出，零行为变更）。

`_settle_officialdom` / `_settle_clerks` / `_settle_clan` / `_settle_upkeep`。"""
from __future__ import annotations

# 官制 × POP 的受控流动入口（官额/吏额/在岗/待阙/祠禄；禁止直接改 pops["官僚"]["size"]）
from core import officialdom as _officialdom

from core.settlement_common import (
    _distribute_cash,
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


def _settle_officialdom(state, log):
    """Step 3.95 官制结算（薄封装，实现在 `core/officialdom.py`——单一权威源）。

    职责：旧档子池迁移修复 → 不变量校验（size == officials + clerks；
    officials == on_post + waiting + sinecure）→ 派生镜像同步（`p["officials"]`/`["clerks"]`
    的唯一写入点）→ 把冗官关键指标写进 `state.statistics` 供面板与审计读取。
    """
    return _officialdom.settle_officialdom(state, log)


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
      · 全额**支付给民间**（营造/修缮服务：工匠 40% ＋ 商人 60%，`_distribute_cash` 精确守恒）；
      · 国库不足时**只按实付**（不穿底、不造币），缺口记 `statistics["upkeep_arrears"]`
        —— 与军俸的「欠饷」、税收的「欠税」科目同构。
    返回本月实付额。
    """
    from content.data import (BUILDING_STD, BUILDING_COST_GROWTH, WORKSHOP_VALUE,
                              EQUIP_UNIT_VALUE, FORT_VALUE, POP_BUILDING_VALUE,
                              ASSET_MAINTAIN_RATE, UPKEEP_PAY_TO)
    # 编制参数（阶段 C-7 / 财力消耗设计 S-D6）：玩家可经政令**主动降维持费**（裁汰冗费）。
    from core import institution as _inst
    _maintain_rate = float(ASSET_MAINTAIN_RATE) * _inst.get(state, "asset_maintain_mult")

    def _lv_cost(std: dict, lv: int) -> float:
        return float(std["base_cost"]) * (BUILDING_COST_GROWTH ** (max(1, int(lv)) - 1))

    asset_value = 0.0
    # 1) 政府工程（projects）：类型命中 BUILDING_STD 时按等级造价
    for _pj in (getattr(state, "projects", {}) or {}).values():
        if not isinstance(_pj, dict):
            continue
        _std = BUILDING_STD.get(str(_pj.get("name") or _pj.get("type") or ""))
        if _std:
            asset_value += _lv_cost(_std, _pj.get("level", 1))
    # 2) POP 建筑（按路）：命中 BUILDING_STD 用其 base_cost，否则用 POP_BUILDING_VALUE
    for _p in state.prefectures.values():
        for _bt, _lv in ((_p.get("buildings") or {})).items():
            _std = BUILDING_STD.get(str(_bt))
            if _std:
                asset_value += _lv_cost(_std, _lv)
            else:
                asset_value += POP_BUILDING_VALUE * max(1, int(_lv or 1))
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
    _given = _distribute_cash(state, paid, UPKEEP_PAY_TO)
    if _given != paid:                      # 极端兜底：无工匠/商人池时余额退回国库
        state.change_treasury(paid - _given)
    log.append(f"[维持] 资产维持费 {paid:,} 贯（资产折算 {asset_value:,.0f} 贯 ×"
               f" {_maintain_rate:.1%}/月）")
    return paid


