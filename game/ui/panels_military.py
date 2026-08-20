# -*- coding: utf-8 -*-
"""宋祚 · 军队实体层（兵额唯一真账 = ArmyUnit.troops）。

本模块是军政重构的"基础约定层"，被 core/game_state、core/game_state_econ、
core/settlement_steps、core/commands_policy、ui/panels_economy 等共同依赖。

核心约定：
  - ArmyUnit.branches（「军籍:兵种」复合键 Σ）是真实人数整数，全代码库唯一的兵额真账
    （troops property 兼容旧引用）。
  - 每路 1 支混合军队：一支军队下混合所有军籍×兵种；军籍在 branches 复合键内，
    unit.tier 保留主军籍（兵额占比最大）供快速读取；"西军"非独立军籍，即驻陕西边地的禁军。
  - strength（锐气）字段已废弃，战力统一由 _army_power(unit, gunpowder) 派生。
  - 粮、饷是独立账：calc_army_grain / calc_army_cash 按 branch_std(军籍,兵种) 按率结算
    （BRANCH_BASE × ARMY_RATE；见 core/game_state_econ）。
  - 装备人均配给：equip = Σ(人数 × EQUIP_STD[兵种] × EQUIP_RATE[军籍])。
  - 宋制番号（A7 史翰青素材）为只读展示层（army_name/org_arm/scale/serial），与兵额真账解耦。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from content.data import (
    ARMY_UNIT_INIT, ARMY_UNIT_SPLIT, UNIT_TIER, EQUIP_STD, branch_std,
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
    """一支军队的实体（用户定稿·每路禁/厢/乡各一支）。

    - branches 键 = 兵种名（如 {"重骑兵": 9000, "轻步兵": 6000}）；军籍由 tier 定（每支军队单一军籍）；
      同名兵种不同军籍粮饷/装备标准不同，查 branch_std(军籍, 兵种)。
    - 兵额唯一真账 = Σbranches（troops property）；装备按兵种配（equip 军队级合计）；粮饷按兵种分。
    """
    unit_id: str
    name: str                 # 完整番号（路·宋制番号）
    tier: str                 # 军籍：禁军/厢军/乡兵（每支军队单一军籍）
    branches: dict            # {兵种名: 人数}
    station: str
    defense_line: str
    morale: int
    training: int
    equip: dict = field(default_factory=dict)
    # 宋制番号命名层（A7 史翰青素材；只读展示，与兵额真账解耦）
    army_name: str = ""        # 宋制番号（禁军军号/厢军役种/乡兵史实名）
    org_arm: str = ""          # 所属司（禁军：殿前司/侍卫马军司/侍卫步军司；厢/乡空）
    scale: str = ""            # 编制（禁军=军、厢军=厢、乡兵=乡）
    serial: int = 0            # 序号（第 X 军/第 X 指挥）

    @property
    def troops(self) -> int:
        """兵额唯一真账 = Σ兵种人数（兼容旧 u.troops 引用）。"""
        return sum(self.branches.values())

    def _split_key(self, key: str):
        """branches 键 → (军籍, 兵种)：新模型键为兵种名（军籍由 tier 定）；
        兼容旧「军籍:兵种」复合键（存档迁移期）。"""
        return tuple(key.split(":", 1)) if ":" in key else (self.tier, key)

    def equip_rate(self) -> float:
        """装备配给率：实际装备 / 应配标准（按兵种加权，branch_std 军籍×兵种按率）。均值 0~1。"""
        if self.troops <= 0:
            return 0.0
        need = {}
        for key, n in self.branches.items():
            t, b = self._split_key(key)
            std = branch_std(t, b).get("equip", {})
            for k, per in std.items():
                if per > 0:
                    need[k] = need.get(k, 0) + n * per
        if not need:
            return 0.0
        covered = sum(min(self.equip.get(k, 0), v) for k, v in need.items())
        total = sum(need.values())
        return covered / total if total > 0 else 0.0


@dataclass
class CentralArsenal:
    """中央武库：7 项实物库存 + 工坊注入 / 诏令实拨。"""
    stock: dict = field(default_factory=lambda: dict(CENTRAL_ARSENAL_INIT))

    def deposit(self, items: dict) -> None:
        """工坊产出注入武库。"""
        for k, v in items.items():
            if k in self.stock:
                self.stock[k] = self.stock.get(k, 0) + int(v)

    def _equip_need(self, unit: ArmyUnit) -> dict:
        """该 unit 按「军籍:兵种」复合键加权的装备应配（branch_std 军籍×兵种按率）。"""
        need = {}
        for key, n in unit.branches.items():
            t, b = unit._split_key(key)
            std = branch_std(t, b).get("equip", {})
            for k, per in std.items():
                if per > 0:
                    need[k] = need.get(k, 0) + n * per
        return need

    def deficit_for(self, unit: ArmyUnit) -> dict:
        """该 unit 当前装备缺口（应配 - 现有），仅正差。"""
        out = {}
        for k, v in self._equip_need(unit).items():
            gap = int(v) - unit.equip.get(k, 0)
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
    """由 ARMY_UNIT_INIT × ARMY_UNIT_SPLIT × branch_std 生成实体。

    用户定稿·**每路禁/厢/乡各一支**：每路 3 支军队（各军籍单一），
    乡兵兵额=0 的路跳过（如东京）；每支 branches 键 = 兵种名（军籍由 tier 定），
    按 ARMY_UNIT_SPLIT[(tier, zone)] 拆该军籍兵种（余数归主兵种）；
    番号由 _org_names 挂（禁军军号/厢军役种/乡兵史实名）；装备按人均配给（branch_std）。
    """
    units: list[ArmyUnit] = []
    seq = 0
    for station, tiers in ARMY_UNIT_INIT.items():
        is_frontier = station in FRONTIER_ROUTES
        zone = "边地" if is_frontier else "内地"
        for tier, cnt in tiers.items():
            if cnt <= 0:
                continue
            split = ARMY_UNIT_SPLIT[(tier, zone)]
            main_branch = max(split, key=lambda b: split[b])
            branches: dict[str, int] = {}
            rem = cnt
            for b, ratio in split.items():
                t = int(cnt * ratio)
                if t > 0:
                    branches[b] = branches.get(b, 0) + t
                rem -= t
            branches[main_branch] = branches.get(main_branch, 0) + rem   # 余数归主兵种
            # 装备（人均配给 Σ 人数×标准）与素质（边地禁军上浮）
            equip: dict[str, int] = {}
            for b, n in branches.items():
                std = branch_std(tier, b).get("equip", {})
                for k, per in std.items():
                    if per > 0:
                        equip[k] = equip.get(k, 0) + int(n * per)
            base = UNIT_TIER[tier]
            train = min(100, base["train_base"] + (FRONTIER_TRAIN_BONUS if (tier == "禁军" and is_frontier) else 0))
            morale = min(100, base["morale_base"] + (FRONTIER_MORALE_BONUS if (tier == "禁军" and is_frontier) else 0))
            seq += 1
            army_name, org_arm, scale = _org_names(station, tier, is_frontier, seq)
            units.append(ArmyUnit(
                unit_id=f"u{seq:04d}",
                name=f"{station}·{army_name}",
                tier=tier,
                branches=branches,
                morale=morale,
                training=train,
                station=station,
                defense_line=_defense_line_for(station, tier),
                equip=equip,
                army_name=army_name,
                org_arm=org_arm,
                scale=scale,
                serial=seq,
            ))
    return units


def _org_names(station: str, tier: str, is_frontier: bool, seq: int):
    """按主军籍挂宋制番号（A7 素材）：
    - 禁军 → 「{军号}{厢别}{军序}军」如「捧日左厢第一军」，org_arm 按军号所属司；
    - 厢军 → 「{路}{役种}」（史实役种名）；
    - 乡兵 → 史实名（如「河北弓箭社」）。
    返回 (army_name, org_arm, scale)。
    """
    from content.data import ARMY_ORG
    _JIN_HAO_ORG = dict(ARMY_ORG["禁军_上四"])
    for _h in ARMY_ORG["禁军_殿前马"]:
        _JIN_HAO_ORG[_h] = "殿前司"
    for _h in ARMY_ORG["禁军_殿前步"]:
        _JIN_HAO_ORG[_h] = "殿前司"
    for _h in ARMY_ORG["禁军_马军司"]:
        _JIN_HAO_ORG[_h] = "侍卫马军司"
    for _h in ARMY_ORG["禁军_步军司"]:
        _JIN_HAO_ORG[_h] = "侍卫步军司"
    if tier == "禁军":
        # 军号池：边地优先上四军/精锐（史实：西军/北边防重地），内地普通军号；按序号轮转稳定
        if is_frontier:
            hao = ["捧日", "天武", "龙卫", "神卫", "骁骑", "云骑"][(seq - 1) % 6]
        else:
            hao = ["神勇", "宣武", "虎翼", "雄勇", "广捷", "神捷", "骁捷", "广锐"][(seq - 1) % 8]
        return f"{hao}左厢第{seq}军", _JIN_HAO_ORG.get(hao, "殿前司"), "军"
    if tier == "厢军":
        yz = ARMY_ORG["厢军_役种"].get(station, ("壮城", "桥道"))[0]
        return f"{station.replace('路', '')}{yz}", "", "厢"
    return ARMY_ORG["乡兵_名"].get(station, f"{station}保甲"), "", "乡"


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
    """该路厢军军队整编入禁军军队（决策动作，非自动；每路禁/厢/乡各一支模型）。

    - 该路「厢军」军队 branches（兵种名）按 ratio 并入「禁军」军队同兵种（总兵额守恒，ratio<1 裁汰）；
    - ratio=1.0 纯换旗；ratio<1 厢军按比例裁汰（剩余清零移除）；
    - 财政代价自动成立：同一批人从厢军标准变禁军标准，粮饷立即上涨（calc_army_grain/cash 按 tier 结算）。
    返回 {"ok": bool, "moved": int, "dissolved": int, "msg": str}。
    """
    xu = next((x for x in state.army_units if x.station == road and x.tier == "厢军"), None)
    ju = next((x for x in state.army_units if x.station == road and x.tier == "禁军"), None)
    if not xu:
        return {"ok": False, "moved": 0, "dissolved": 0, "msg": f"[整编] {road} 无厢军可整编，跳过"}
    if not ju:
        return {"ok": False, "moved": 0, "dissolved": 0, "msg": f"[整编] {road} 无禁军可接收，跳过"}
    ratio = max(0.0, min(1.0, float(ratio)))
    moved_total = 0
    for b, n in list(xu.branches.items()):
        mv = int(n * ratio)
        ju.branches[b] = ju.branches.get(b, 0) + mv
        xu.branches[b] = n - mv
        moved_total += mv
        if xu.branches[b] <= 0:
            del xu.branches[b]
    return {"ok": True, "moved": moved_total, "dissolved": 1,
            "msg": f"[整编] {road} 厢军整编入禁军 {moved_total} 人（ratio={ratio:.2f}）"}


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
    """直接显示真实数+千分位，无万进位。"""
    return f"{int(round(n)):,}{unit}"
