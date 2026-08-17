# -*- coding: utf-8 -*-
"""宋祚 · 军队实体层（兵额唯一真账 = ArmyUnit.troops）。

本模块是军政重构的"基础约定层"，被 core/game_state、core/game_state_econ、
core/settlement_steps、core/commands_policy、ui/panels_economy 等共同依赖。

核心约定：
  - ArmyUnit.troops 是真实整数（人），全代码库唯一的兵额真账。
  - 军籍（禁军/厢军/乡兵）由番号编码，并存于 unit.tier 字段供快速读取；
    "西军"非独立军籍，即驻陕西边地的禁军。
  - strength（锐气）字段已废弃，战力统一由 _army_power(unit, gunpowder) 派生。
  - 粮、饷是独立账：calc_army_grain / calc_army_cash 各自按 UNIT_TIER 的
    grain_mult / pay_mult 结算（见 core/game_state_econ）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from content.data import (
    ARMY_UNIT_INIT, ARMY_UNIT_SPLIT, UNIT_TIER, EQUIP_STD,
    FRONTIER_ROUTES, FRONTIER_TRAIN_BONUS, FRONTIER_MORALE_BONUS,
    CENTRAL_ARSENAL_INIT,
)

# 7 项装备实物键（顺序即存档/显示顺序）
EQUIP_KEYS = ["枪刀", "弓弩", "火器", "战马", "盔甲", "舟船", "器械"]


# ============================================================
# 数据类
# ============================================================
@dataclass
class ArmyUnit:
    """一支军队的实体。troops 为真实人数整数，是兵额唯一真账。"""
    unit_id: str
    name: str                 # 番号（自身编码军籍/驻地/兵种）
    tier: str                 # 军籍：禁军/厢军/乡兵（由番号编码，冗余存一份便于读取）
    branch: str               # 兵种（重骑兵/轻步兵/…）
    troops: int               # 真实人数（人），允许任意零头
    morale: int               # 士气 0~100
    training: int             # 训练度 0~100
    station: str              # 驻地路（如 陕西路）
    defense_line: str         # 所属防线（如 北线_陕西）
    equip: dict = field(default_factory=dict)   # 7 项装备实物数（件/张/匹/领/艘/具）

    def equip_rate(self) -> float:
        """装备配给率：实际装备 / 应配标准（按当前兵额）。均值 0~1。"""
        if self.troops <= 0 or not self.equip:
            return 0.0
        std = EQUIP_STD.get(self.branch, {})
        if not std:
            return 0.0
        ratios = []
        for k, per in std.items():
            if per <= 0:
                continue
            need = self.troops * per
            ratios.append(min(1.0, self.equip.get(k, 0) / need) if need > 0 else 1.0)
        return sum(ratios) / len(ratios) if ratios else 0.0


@dataclass
class CentralArsenal:
    """中央武库：7 项实物库存 + 工坊注入 / 诏令实拨。"""
    stock: dict = field(default_factory=lambda: dict(CENTRAL_ARSENAL_INIT))

    def deposit(self, items: dict) -> None:
        """工坊产出注入武库。"""
        for k, v in items.items():
            if k in self.stock:
                self.stock[k] = self.stock.get(k, 0) + int(v)

    def deficit_for(self, unit: ArmyUnit) -> dict:
        """该 unit 当前装备缺口（应配 - 现有），仅正差。"""
        out = {}
        std = EQUIP_STD.get(unit.branch, {})
        for k, per in std.items():
            if per <= 0:
                continue
            need = int(unit.troops * per)
            gap = need - unit.equip.get(k, 0)
            if gap > 0:
                out[k] = gap
        return out

    def distribute(self, unit: ArmyUnit, items: Optional[dict] = None) -> dict:
        """按缺口从武库实拨到 unit 装备（非每回合自动，由诏令显式触发）。

        返回实际拨发量 dict；武库不足者按现有量拨发（部分满足）。
        items 为 None 时按 unit 全缺口拨发；否则按指定 items 拨发（受武库约束）。
        """
        want = items if items is not None else self.deficit_for(unit)
        granted = {}
        for k, need in want.items():
            if k not in self.stock:
                continue
            take = min(int(need), self.stock.get(k, 0))
            if take <= 0:
                continue
            self.stock[k] -= take
            unit.equip[k] = unit.equip.get(k, 0) + take
            granted[k] = take
        return granted


# ============================================================
# 构建 / 派生
# ============================================================
# 防线归属：军籍 × 驻地 → 防区（与旧 _derive_defense_lines 口径一致）
_DEFENSE_LINE_OF = {
    ("河北路",): "北线_太原真定",
    ("河东",): "北线_太原真定",
    ("陕西路",): "北线_陕西",
    ("京西路",): "中线_黄河渡口",
    ("东京开封府",): "中线_黄河渡口",   # 东京厢军入中线；禁军余部入内线，见下
}


def _defense_line_for(station: str, tier: str) -> str:
    """某驻地某军籍实体归属的防线（与旧聚合口径对齐）。"""
    if station == "东京开封府":
        # 东京禁军余部归内线_东京城防；厢军随中线
        return "内线_东京城防" if tier == "禁军" else "中线_黄河渡口"
    if station == "京西路":
        return "中线_黄河渡口" if tier in ("禁军", "厢军") else "内线_东京城防"
    return _DEFENSE_LINE_OF.get((station,), "中线_黄河渡口")


def unit_tier_of(unit: ArmyUnit) -> str:
    """由番号/字段解析军籍（禁军/厢军/乡兵）。"""
    return unit.tier


def _branch_name_cn(branch: str) -> str:
    return branch


def build_army_units(state) -> list[ArmyUnit]:
    """由 ARMY_UNIT_INIT × ARMY_UNIT_SPLIT × UNIT_TIER × EQUIP_STD 生成实体。

    - troops 原样为真实人数整数（已是"人"单位，不再 ×10000）。
    - 拆兵种按比例向下取整，累计余数归占比最大的主将部，保证
      Σ branch_troops == 该军籍总兵额 精确成立。
    - 边地禁军按 FRONTIER_*_BONUS 上浮训练/士气。
    """
    gunpowder = getattr(state, "tech", {}).get("gunpowder", 20)
    units: list[ArmyUnit] = []
    seq = 0
    for station, tiers in ARMY_UNIT_INIT.items():
        is_frontier = station in FRONTIER_ROUTES
        zone = "边地" if is_frontier else "内地"
        for tier, total in tiers.items():
            if total <= 0:
                continue
            base = UNIT_TIER[tier]
            split = ARMY_UNIT_SPLIT[(tier, zone)]
            # 主将部 = 占比最大的兵种（余数归它）
            main_branch = max(split, key=lambda b: split[b])
            # 先按比例向下取整分配，余数累计
            rem = total
            branch_troops: dict[str, int] = {}
            for b, ratio in split.items():
                t = int(total * ratio)
                branch_troops[b] = t
                rem -= t
            branch_troops[main_branch] += rem   # 余数归主将部
            # 素质基线（边地禁军上浮）
            if tier == "禁军" and is_frontier:
                train = min(100, base["train_base"] + FRONTIER_TRAIN_BONUS)
                morale = min(100, base["morale_base"] + FRONTIER_MORALE_BONUS)
            else:
                train = base["train_base"]
                morale = base["morale_base"]
            for b, t in branch_troops.items():
                if t <= 0:
                    continue
                seq += 1
                std = EQUIP_STD[b]
                equip = {k: int(t * per) for k, per in std.items()}
                # 主将部番号标注"将/主"，厢军/乡兵标注建制
                if tier == "禁军":
                    suffix = "将" if b == main_branch else "营"
                elif tier == "厢军":
                    suffix = "厢"
                else:
                    suffix = "乡兵"
                name = f"{station}{seq:02d}{suffix}（{b}）"
                dline = _defense_line_for(station, tier)
                units.append(ArmyUnit(
                    unit_id=f"u{seq:04d}",
                    name=name,
                    tier=tier,
                    branch=b,
                    troops=t,
                    morale=morale,
                    training=train,
                    station=station,
                    defense_line=dline,
                    equip=equip,
                ))
    return units


# ============================================================
# 战力 / 战斗 / 火器
# ============================================================
def _firearm_power_mult(gunpowder: int) -> float:
    """火器代际对战力的加成系数（随 tech.gunpowder 提升）。"""
    # 突火枪(20)→1.0；火铳(40)→1.08；火枪(65)→1.18；燧发枪(85)→1.30
    if gunpowder >= 85:
        return 1.30
    if gunpowder >= 65:
        return 1.18
    if gunpowder >= 40:
        return 1.08
    return 1.0


def _army_power(unit: ArmyUnit, gunpowder: int) -> float:
    """单支军队战力：兵力 × 装备配给均值 × 士气/100 × 训练度/100 × 火器系数。

    统一口径，取代旧 ARMY_INIT.strength；靖康判定/评价/AI 叙事/战斗均用此。
    """
    if unit.troops <= 0:
        return 0.0
    equip_rate = unit.equip_rate()
    firearm = _firearm_power_mult(gunpowder)
    return (unit.troops * equip_rate
            * (unit.morale / 100.0) * (unit.training / 100.0) * firearm)


def _army_power_total(units, gunpowder: int) -> float:
    return sum(_army_power(u, gunpowder) for u in units)


def _resolve_battle(defender_power: float, attacker_power: float):
    """线性比例战斗模型。

    返回 (胜负, 我方伤亡人数 int, 破防 bool)。
    胜负由 power 对比决定：守方 power 高则胜、低则破防。
    伤亡按"败方损失更重"的线性比例估算，具体分摊到各 unit 由调用方
    按 _army_power 占比执行（此处只给总伤亡）。
    """
    if defender_power <= 0 and attacker_power <= 0:
        return (True, 0, False)
    total = defender_power + attacker_power
    if total <= 0:
        return (True, 0, False)
    # 守方胜率 ~ 守/总；败方伤亡比例随差距放大
    def_winrate = defender_power / total
    win = def_winrate >= 0.5
    # 我方（守方）伤亡：败则重、胜则轻
    if win:
        loss_ratio = 0.05 + (1 - def_winrate) * 0.15   # 胜：5%~12.5%
        breach = False
    else:
        loss_ratio = 0.20 + (0.5 - def_winrate) * 0.60  # 败：20%~50%
        breach = True
    # 伤亡人数 = 我方总兵力 × 比例（兵力由调用方据 units 推，这里返比例×兵额的近似由上层给）
    # 为解耦，返回以"power"为单位的伤亡，调用方再按 troops/power 反算人数
    loss_power = defender_power * loss_ratio
    return (win, loss_power, breach)


# ============================================================
# 整编（厢军 → 禁军）：策略层决策动作
# ============================================================
def reorganize_xiang_to_jin(state, road: str, ratio: float = 1.0) -> dict:
    """该路厢军实体整编入禁军主将部（决策动作，非自动）。

    - ratio=1.0 纯换旗（总兵额守恒）；ratio<1 裁汰（总兵额减少）。
    - 厢军 troops×ratio（向下取整，零头归禁军主将部）并入该路禁军主将部；
      厢军实体 troops 清零后从实体列表移除（直接撤建制，不保留空壳）。
    - 财政代价自动成立：整编后同一批人从厢军(×0.9/0.5)变禁军(×1.0/1.0)，
      粮饷立即上涨（由 calc_army_grain/cash 逐实体结算体现），本函数不写粮饷。
    返回 {"ok": bool, "moved": int, "dissolved": int, "msg": str}。
    """
    units = state.army_units
    xiang = [u for u in units if u.station == road and u.tier == "厢军"]
    jin = [u for u in units if u.station == road and u.tier == "禁军"]
    if not xiang:
        return {"ok": False, "moved": 0, "dissolved": 0,
                "msg": f"[整编] {road} 无厢军可整编，跳过"}
    if not jin:
        return {"ok": False, "moved": 0, "dissolved": 0,
                "msg": f"[整编] {road} 无禁军主将部可接收，跳过"}
    ratio = max(0.0, min(1.0, float(ratio)))
    # 禁军主将部 = 该路禁军中 troops 最大者（接收方）
    main_jin = max(jin, key=lambda u: u.troops)
    moved_total = 0
    dissolved = 0
    for xu in xiang:
        mv = int(xu.troops * ratio)
        # 零头（troops×ratio 的小数部分）归禁军主将部
        frac = xu.troops * ratio - mv
        mv_total = mv + (1 if frac >= 0.5 else 0)
        main_jin.troops += mv_total
        moved_total += mv_total
        # 装备按比例随人划转（向下取整）
        for k in EQUIP_KEYS:
            ep = xu.equip.get(k, 0)
            tr = int(ep * ratio)
            main_jin.equip[k] = main_jin.equip.get(k, 0) + tr
            xu.equip[k] = ep - tr
        xu.troops = 0
        dissolved += 1
    # 移除被清零的厢军实体
    state.army_units = [u for u in units if not (u.station == road and u.tier == "厢军" and u.troops == 0)]
    return {"ok": True, "moved": moved_total, "dissolved": dissolved,
            "msg": f"[整编] {road} 撤厢军{dissolved}部、并禁军{moved_total}人（ratio={ratio:.2f}）"}


# ============================================================
# 武库链路（工坊注入 / 诏令拨发）
# ============================================================
def deposit_workshop(state, items: dict) -> None:
    """工坊月度产出入中央武库（非直接发军队）。"""
    state.central_arsenal.deposit(items)


def distribute_arsenal(state, unit: ArmyUnit, items: Optional[dict] = None) -> dict:
    """玩家诏令：按缺口从中央武库实拨到某支军队装备。"""
    return state.central_arsenal.distribute(unit, items)


# ============================================================
# 自适应显示
# ============================================================
def _fmt_count(n: float, unit: str) -> str:
    """<10000 显示 'n 单位'，否则 'x.x 万单位'。"""
    if n < 10000:
        return f"{int(round(n))}{unit}"
    return f"{n/10000:.1f}万{unit}"
