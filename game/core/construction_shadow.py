# -*- coding: utf-8 -*-
"""建造部门影子模块（只读）—— **不接入正式结算**。

## 性质

「建造部门（民间/官有）+ 劳役落点」的影子实现：
验证「**劳役从哪来、代价是什么、与雇工怎么权衡**」。

- 纯函数 / 只读 —— 不写任何 state；
- 不被 settlement* 引用；
- 用途：跑自检、供接入前裁定参考。

## 用户裁定（2026-10-05）

「**还要加入建造部门，分民间跟官有，让劳役有落地的地方**」

## 🔴 复用既有量（**无新变量**）

| 既有 | 角色 |
|---|---|
| `pop_structure.service_ding_of(p)` | **劳役人口基数**（应役丁）|
| `工匠 POP.size` | **雇工来源** |
| `mood`（`clerks.py` 已有差役扰民先例）| **劳役的代价** |
| `役钱`（`settlement_finance`）| **与劳役互补**（纳钱免役）|

## 口径纪律

- **缺失 ≠ 0**：某路无劳力 ⇒ 返回 None，不臆造；
- **不得超征**：劳役 ≤ 应役丁 × 上限率；
- **劳役不付工钱**，但**必付民情代价**（不得白嫖）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "DEPARTMENTS", "HIRED_RATIO", "CORVEE_CAP_RATE", "CORVEE_MOOD_W",
    "default_wage_per_hour", "hired_capacity", "corvee_capacity",
    "labor_for", "wage_cost", "mood_penalty", "choose_channel",
    "DEPT_LABELS", "OFFICIAL_OWNERS", "dept_entity", "departments_of", "departments_of_seat", "departments_all", "departments_all_derived", "MODE_TRUTH", "MODE_DERIVED", "run_checks", "run_checks2", "run_checks3", "run_checks4", "run_checks5",
]

#: 两个建造部门（用户裁定）。
DEPARTMENTS = ("民间营造", "官有营造")

#: 雇工容量 = 工匠 POP.size × 此比例（玩法设定）。
HIRED_RATIO = 0.10

#: 劳役征发上限率（应役丁的几成）—— 玩法设定，**待标定**。
CORVEE_CAP_RATE = 0.30

#: 劳役扰民系数（对应 `clerks.MUSTER_MOOD_W = 0.20` 的思路）。
CORVEE_MOOD_W = 0.20

#: 默认工价（贯/工时）—— 玩法设定，**待标定**。
DEFAULT_WAGE_PER_HOUR = 0.02


def default_wage_per_hour() -> float:
    return DEFAULT_WAGE_PER_HOUR


def hired_capacity(craft_size: Optional[int]) -> Optional[float]:
    """**雇工**容量（工时）。`craft_size` 不可读 ⇒ `None`（缺失≠0）。"""
    if craft_size is None:
        return None
    return float(max(0, int(craft_size))) * HIRED_RATIO


def corvee_capacity(service_ding: Optional[int],
                    cap_rate: float = CORVEE_CAP_RATE) -> Optional[float]:
    """**劳役**可用量（人）。`service_ding` 不可读 ⇒ `None`。

    ⚠️ 上限率约束：**不得超征**（超征应另加误农时惩罚，本模块只给上限）。
    """
    if service_ding is None:
        return None
    r = max(0.0, min(1.0, float(cap_rate)))
    return float(max(0, int(service_ding))) * r


def labor_for(department: str, craft_size: Optional[int],
              service_ding: Optional[int], hired_hours: float = 0.0,
              corvee_ratio: float = 0.0) -> Dict[str, object]:
    """按**部门**给出劳力构成。

    - `民间营造`：**只用雇工**（付工钱）；
    - `官有营造`：**劳役（不付工钱）+ 雇工补足**（付工钱）。

    `corvee_ratio` = 希望用劳役顶替的比例（0~1）。
    """
    if department not in DEPARTMENTS:
        return {"ok": False, "reason": "unknown_department"}
    need = max(0.0, float(hired_hours))
    hired_cap = hired_capacity(craft_size)
    corvee_cap = corvee_capacity(service_ding)
    if department == "民间营造":
        if hired_cap is None:
            return {"ok": False, "reason": "no_craft_data"}
        take = min(need, hired_cap)
        return {"ok": take > 0, "dept": department, "hired": take, "corvee": 0.0,
                "unmet": need - take, "reason": "" if take > 0 else "no_hired_capacity"}
    # 官有营造
    if corvee_cap is None:
        return {"ok": False, "reason": "no_service_ding_data"}
    r = max(0.0, min(1.0, float(corvee_ratio)))
    want_corvee = need * r
    corvee = min(want_corvee, corvee_cap)
    rest = need - corvee
    hired = 0.0 if hired_cap is None else min(rest, hired_cap)
    return {"ok": (corvee + hired) > 0, "dept": department,
            "hired": hired, "corvee": corvee,
            "unmet": rest - hired,
            "corvee_capped": corvee >= corvee_cap - 1e-9,
            "reason": "" if (corvee + hired) > 0 else "no_labor"}


def wage_cost(hired_hours: float, wage_per_hour: Optional[float] = None) -> int:
    """雇工的**工钱**（贯）。**劳役不计入**（不付工钱）。"""
    w = default_wage_per_hour() if wage_per_hour is None else float(wage_per_hour)
    return int(round(max(0.0, float(hired_hours)) * max(0.0, w)))


def mood_penalty(corvee_used: float, service_ding: Optional[int],
                 mood_w: float = CORVEE_MOOD_W) -> Optional[float]:
    """**扰民代价**（`mood` 应下降多少）。

    - 无应役丁数据 ⇒ `None`（缺失≠0）；
    - 征发占应役丁比例越高 ⇒ 惩罚越大；；
    - **劳役为 0 ⇒ 惩罚 0**（不扰民）。
    """
    if service_ding is None:
        return None
    cap = float(max(0, int(service_ding)))
    if cap <= 0:
        return 0.0
    ratio = max(0.0, min(1.0, float(corvee_used) / cap))
    return float(round(ratio * float(mood_w) * 100.0, 4))


def choose_channel(hired_hours: float, craft_size: Optional[int],
                   service_ding: Optional[int], treasury_room: Optional[float],
                   mood_now: Optional[float],
                   wage_per_hour: Optional[float] = None) -> Dict[str, object]:
    """**雇工 vs 劳役**的权衡（只给判断，不做决策）。

    两难：
      · **雇工** —— 付工钱（贵），**不扰民**；
      · **劳役** —— 不付工钱（省），**扰民**（`mood` ↓）。

    本函数**只报告两条通道的代价**，供上层/玩家决策。
    """
    need = max(0.0, float(hired_hours))
    w = default_wage_per_hour() if wage_per_hour is None else float(wage_per_hour)
    hire_need = min(need, hired_capacity(craft_size) or 0.0)
    corvee_cap = corvee_capacity(service_ding)
    corvee_need = min(need, corvee_cap) if corvee_cap is not None else 0.0
    cost_hire = wage_cost(hire_need, w)
    penalty = mood_penalty(corvee_need, service_ding)
    affordable = None if treasury_room is None else max(0.0, float(treasury_room))
    return {
        "need": need,
        "hired": {"hours": hire_need, "money": cost_hire,
                  "mood_cost": 0.0,
                  "affordable": None if affordable is None else cost_hire <= affordable},
        "corvee": {"hours": corvee_need, "money": 0,
                   "mood_cost": penalty,
                   "capped": (corvee_cap is not None and corvee_need >= corvee_cap - 1e-9)},
        "mood_now": mood_now,
    }

def run_checks():
    """建造部门自检，返回 `[(项名, 通过?, 说明)]`。**纯只读**。"""
    out = []

    def add(n, ok, note=""):
        out.append((n, bool(ok), note))

    # 1 民间部门只用雇工
    a = labor_for("民间营造", 1000, 20000, 100.0)
    add("1 民间只用雇工", a["corvee"] == 0 and a["hired"] > 0, str({k: a[k] for k in ("hired", "corvee")}))

    # 2 官有部门可用劳役
    b = labor_for("官有营造", 1000, 20000, 100.0, 0.5)
    add("2 官有可用劳役", b["corvee"] > 0, "corvee=%.1f hired=%.1f" % (b["corvee"], b["hired"]))

    # 3 劳役不超上限（应役丁 × 上限率）
    c = labor_for("官有营造", 1000, 20000, 999999.0, 1.0)
    cap = corvee_capacity(20000)
    add("3 劳役不超上限", c["corvee"] <= cap + 1e-9, "%.1f <= %.1f" % (c["corvee"], cap))

    # 4 超征被截断并标记
    add("4 超征被截断", c["corvee_capped"] is True, str(c["corvee_capped"]))

    # 5 劳役不付工钱（工钱只按 hired 计）
    w1 = wage_cost(b["hired"])
    w_all = wage_cost(b["hired"] + b["corvee"])
    add("5 劳役不付工钱", w1 < w_all, "hired-only=%d  若全算=%d" % (w1, w_all))

    # 6 劳役有扰民代价
    p1 = mood_penalty(b["corvee"], 20000)
    add("6 劳役扰民", p1 and p1 > 0, "penalty=%.2f" % (p1 or 0))

    # 7 劳役为 0 ⇒ 惩罚 0
    add("7 无劳役无惩罚", mood_penalty(0.0, 20000) == 0.0, str(mood_penalty(0.0, 20000)))

    # 8 缺失 ≠ 0
    add("8 缺失≠0", hired_capacity(None) is None and corvee_capacity(None) is None
        and mood_penalty(10, None) is None, "craft/ding 缺失 ⇒ None")

    # 9 未知部门被拒
    add("9 未知部门被拒", labor_for("野部门", 1, 1)["ok"] is False, "unknown_department")

    # 10 劳役比例越高，扰民越大（单调）
    p_lo = mood_penalty(corvee_capacity(20000) * 0.2, 20000)
    p_hi = mood_penalty(corvee_capacity(20000) * 0.8, 20000)
    add("10 扰民随比例单调", (p_hi or 0) > (p_lo or 0), "20%%=%.2f  80%%=%.2f" % (p_lo or 0, p_hi or 0))

    # 11 权衡报告含两条通道
    ch = choose_channel(100.0, 1000, 20000, 99999.0, 50.0)
    add("11 权衡含双通道", "hired" in ch and "corvee" in ch
        and ch["corvee"]["money"] == 0 and ch["hired"]["mood_cost"] == 0.0,
        "雇工钱=%s 劳役钱=%s" % (ch["hired"]["money"], ch["corvee"]["money"]))

    # 12 省下的钱 = 劳役顶替的工钱
    add("12 劳役省钱", ch["corvee"]["hours"] > 0 and wage_cost(ch["corvee"]["hours"]) > 0,
        "劳役 %.1f 工时 ⇒ 省 %d 贯" % (ch["corvee"]["hours"], wage_cost(ch["corvee"]["hours"])))

    return out

# ============================================================
# 建造部门**实体**（用户裁定：部门要有实体，让玩家感知得到）
# ============================================================

#: 部门实体的实体名（玩家面板显示用）。
DEPT_LABELS = {"民间营造": "民间营造", "官有营造": "官有营造"}

#: 官有营造的归属主体（部门本身也有归属）。
OFFICIAL_OWNERS = ("local_gov", "state")


def dept_entity(department: str, owner_kind: str,
                  labor: Optional[int] = None,
                  artisans: Optional[int] = None,
                  monthly: Optional[Dict[str, float]] = None) -> Dict[str, object]:
    """**部门实体**（只读构造，不写 state）。

    玩家可感知的最小完整单元：
      · **名字**（`dept_id` + `label`）——
      · **归属**（`owner_kind`：民产/地方公产/国家公产）——
      · **规模**（`craftsmen`：归属工匠数；缺失 ⇒ `None`，**缺失≠0**）——
      · **月度产出**（`monthly`：完工/雇工工时/征役人日/工钱支出）。

    ⚠️ `monthly` 缺失 ⇒ 各产出字段为 `None`（**不伪造 0**）。
    """
    if department not in DEPARTMENTS:
        return {"ok": False, "reason": "unknown_department"}
    ok_owner = owner_kind in ("pop",) + OFFICIAL_OWNERS
    if not ok_owner:
        return {"ok": False, "reason": "unknown_owner_kind"}
    out: Dict[str, object] = {
        "ok": True, "dept_id": department, "label": DEPT_LABELS[department],
        "owner_kind": owner_kind, "labor": labor, "artisans": artisans,
        "official": department == "官有营造",
        "monthly": None, "built": None, "hired_hours": None,
        "corvee_days": None, "coin": None, "mood_cost": None,
    }
    if monthly is not None:
        out["monthly"] = {k: monthly.get(k) for k in
                           ("built", "hired_hours", "corvee_days", "coin", "mood_cost")}
        # 归属基准（承 §五「口径」）：保留上游标注，前端/测试可核对派生依据
        if "attribution" in monthly:
            out["monthly"]["attribution"] = monthly.get("attribution")
        out["built"] = monthly.get("built")
        out["hired_hours"] = monthly.get("hired_hours")
        out["corvee_days"] = monthly.get("corvee_days")
        out["coin"] = monthly.get("coin")
        out["mood_cost"] = monthly.get("mood_cost")
    return out


def departments_of(state: Dict[str, object]) -> List[Dict[str, object]]:
    """读出一路（或全国）的**部门实体列表**，供玩家面板消费。

    - 民间营造：`owner_kind="pop"`，规模＝该路 `工匠` POP；
    - 官有营造：`owner_kind="local_gov"`，规模＝该路工匠 + 应役丁；
    - **月度产出缺失时各字段为 None**（不伪造 0）。
    """
    prefs = state.get("prefectures") if isinstance(state, dict) else None
    if not isinstance(prefs, dict):
        return []
    out: List[Dict[str, object]] = []
    for route, p in prefs.items():
        if not isinstance(p, dict):
            continue
        lab = _labor_of(p)
        art = _artisans_of(p)
        ding = _service_ding_of(p)
        out.append(dept_entity("民间营造", "pop", labor=lab, artisans=art))
        _off = dept_entity("官有营造", "local_gov", labor=lab, artisans=art)
        _off["corvee_base"] = ding
        out.append(_off)
        out[-1]["route"] = route
        out[-2]["route"] = route
    return out


def _craftsmen_of(p: Dict[str, object]) -> Optional[int]:
    pops = p.get("pops")
    if not isinstance(pops, dict):
        return None
    c = pops.get("工匠")
    if not isinstance(c, dict):
        return None
    try:
        return int(c.get("size", 0) or 0)
    except Exception:  # noqa: BLE001
        return None


def _service_ding_of(p: Dict[str, object]) -> Optional[int]:
    pops = p.get("pops")
    if not isinstance(pops, dict):
        return None
    a = pops.get("农")
    if not isinstance(a, dict):
        return None
    try:
        return int(a.get("ding", 0) or 0)
    except Exception:  # noqa: BLE001
        return None

def run_checks2():
    """部门实体自检（第二批）。"""
    out = []

    def add(n, ok, note=""):
        out.append((n, bool(ok), note))

    # 13 实体四要素齐全
    e = dept_entity("官有营造", "local_gov", labor=100, monthly={"built": 2})
    add("13 实体四要素", all(k in e for k in ("dept_id", "label", "owner_kind", "labor", "monthly")),
        "label=%s owner=%s craft=%s" % (e["label"], e["owner_kind"], e["labor"]))

    # 14 官有标记
    c = dept_entity("民间营造", "pop")
    add("14 官有标记", e["official"] is True and c["official"] is False, "民间=False 官有=True")

    # 15 未知部门/归属被拒
    add("15 非法输入被拒", dept_entity("野部门", "pop")["ok"] is False
        and dept_entity("民间营造", "山寨")["ok"] is False, "unknown_department/owner")

    # 16 月度产出缺失 ⇒ None（不伪造 0）
    n = dept_entity("民间营造", "pop", labor=None)
    add("16 产出缺失≠0", n["built"] is None and n["monthly"] is None and n["labor"] is None,
        "built=None monthly=None craft=None")

    # 17 逐路枚举（2 路 x 2 部门）
    st = {"prefectures": {"A": {"pops": {"工匠": {"size": 4}, "农": {"size": 10, "ding": 100}}},
                              "B": {"pops": {"工匠": {"size": 2}, "农": {"size": 5, "ding": 50}}}}}
    ds = departments_of(st)
    add("17 逐路枚举", len(ds) == 4 and ds[0]["route"] == "A", "2 路 x 2 = %d" % len(ds))

    # 18 官有规模 = 工匠 + 应役丁
    add("18 劳力取农·官有单列劳役基", ds[0]["labor"] == 10 and ds[1]["labor"] == 10
         and ds[1]["corvee_base"] == 100, "民间labor=%s 官有labor=%s corvee=%s" % (ds[0]["labor"], ds[1]["labor"], ds[1]["corvee_base"]))

    # 19 缺 POP ⇒ 规模 None
    ds2 = departments_of({"prefectures": {"C": {}}})
    add("19 缺数据⇒None", ds2[0]["labor"] is None and ds2[1]["labor"] is None, "C 路无 POP")

    # 20 空输入安全
    add("20 空输入安全", departments_of({}) == [] and departments_of({"prefectures": 1}) == [], "[]")

    return out

# ============================================================
# 部门实体 · **州府（治所）级**
#
# 用户裁定（2026-10-05）：「**要落到州府，而州府一级是自造，**
# 因为玩家是中央一级，一般不会管州府一级的事务」。
#
# => 治理语义：
#   · **玩家/中央**：直管**国家营建**与政令；**不碰**州府与民间；
#   · **州府（治所）**：**自造** —— 自行决定建什么/出资/产权，**只上报汇总**；
#   · **民间**：**自造** —— 自筹自发。
#
# => 故州府级部门实体是**汇总/呈现层**，**不是玩家指令层**。
# ============================================================

def departments_of_seat(seat: Dict[str, object], route: str,
                         seat_name: str) -> List[Dict[str, object]]:
    """**单个州府（治所）**的部门实体。

    - 两个部门（民间营造 / 官有营造）**各自独立**，**不按路汇总**；
    - 归属：民间＝`pop`；官有＝`local_gov`（州府自办）；
    - 规模：民间＝工匠；官有＝工匠 + 应役丁（**均为治所级**）；
    - 缺失 ⇒ `None`（**缺失≠0**，不借路级数据填充）。

    ⚠️ 若该治所无 POP 数据 ⇒ 仍返回两个实体，但规模为 `None`
    （**实体本身存在** ≠ **规模已知**，二者不可混）。
    """
    if not isinstance(seat, dict):
        return []
    lab = _labor_of(seat)
    art = _artisans_of(seat)
    ding = _service_ding_of(seat)
    out = [dept_entity("民间营造", "pop", labor=lab, artisans=art)]
    _off = dept_entity("官有营造", "local_gov", labor=lab, artisans=art)
    _off["corvee_base"] = ding
    out.append(_off)
    for e in out:
        e["route"] = route
        e["seat"] = seat_name
        e["level"] = "seat"
    return out


def departments_all(state: Dict[str, object]) -> Dict[str, object]:
    """全境**州府级**部门实体汇总（玩家面板消费）。

    返回 `{ok, seats_covered, departments, reason}`：

    - `seats_covered`：实际覆盖的**治所数**（无 `seats` ⇒ **0**，**不回落路级**）；
    - `departments`：每治所 2 个实体；
    - `reason`：无 `seats` 时给 `no_seats`（**缺失≠0，不伪造**）。

    🔴 **不回落路级**：甲方案要求州府为真账，路级实体与本口径冲突，
    故宁可返回空并说明原因。
    """
    prefs = state.get("prefectures") if isinstance(state, dict) else None
    if not isinstance(prefs, dict):
        return {"ok": False, "reason": "no_prefectures",
                "seats_covered": 0, "departments": []}
    depts: List[Dict[str, object]] = []
    covered = 0
    for route, p in prefs.items():
        if not isinstance(p, dict):
            continue
        seats = p.get("seats")
        if not isinstance(seats, dict) or not seats:
            continue
        for seat_name, seat in seats.items():
            got = departments_of_seat(seat, route, seat_name)
            if got:
                covered += 1
                depts.extend(got)
    if covered == 0:
        return {"ok": False, "reason": "no_seats",
                "seats_covered": 0, "departments": []}
    return {"ok": True, "reason": "", "seats_covered": covered,
            "departments": depts}

def run_checks3():
    """州府级部门实体自检（第三批）。"""
    out = []

    def add(n, ok, note=""):
        out.append((n, bool(ok), note))

    st = {"prefectures": {"A": {"seats": {"s1": {"pops": {"工匠": {"size": 3}, "农": {"size": 8, "ding": 90}}}}}}}
    r = departments_all(st)
    add("21 州府级枚举", r["ok"] and r["seats_covered"] == 1 and len(r["departments"]) == 2,
        "1 治所 x 2 = %d" % len(r["departments"]))

    e0, e1 = r["departments"][0], r["departments"][1]
    add("22 带治所坐标", e0["route"] == "A" and e0["seat"] == "s1" and e0["level"] == "seat",
        "route=%s seat=%s level=%s" % (e0["route"], e0["seat"], e0["level"]))

    add("23 劳力两部门同值+官有单列劳役基", e0["labor"] == 8 and e1["labor"] == 8
         and e1["corvee_base"] == 90, "民间=%s 官有=%s corvee=%s" % (e0["labor"], e1["labor"], e1["corvee_base"]))

    n = departments_all({"prefectures": {"A": {}}})
    add("24 无seats⇒空且说明", (not n["ok"]) and n["reason"] == "no_seats" and n["seats_covered"] == 0,
        "reason=%s（**不回落路级**）" % n["reason"])

    add("25 无prefectures⇒空", departments_all({})["reason"] == "no_prefectures", "no_prefectures")

    ds = departments_of_seat({}, "B", "s9")
    add("26 空治所仍有两实体", len(ds) == 2 and ds[0]["labor"] is None,
        "实体存在但规模未知 ⇒ None")

    add("27 非dict治所⇒空", departments_of_seat(None, "B", "s9") == [], "[]")

    add("28 两部门不合并", ds[0]["dept_id"] != ds[1]["dept_id"] and ds[0]["owner_kind"] == "pop"
        and ds[1]["owner_kind"] == "local_gov", "民间=pop 官有=local_gov")

    return out

#: 汇总模式（玩家/前端据此区分**真账**与**派生**）。
MODE_TRUTH = "truth"      # 州府级真账（seats 存在）
MODE_DERIVED = "derived"  # **派生**（按人口权重拆路级值；不改任何账本）


def departments_all_derived(state: Dict[str, object],
                             circuit: str, p: Dict[str, object]
                             ) -> List[Dict[str, object]]:
    """**派生**某路的州府级部门实体（**只读，不写 state**）。

    用途：给「**尚未下沉 `seats`**」的档（含所有新局）提供**玩家可见**的部门实体，
    **不触碰真账**，因而**零风险**。

    口径：
    · **复用既有权重** `pop_bridge.seat_pop_weights(circuit)`（按治所 `demog.population`）
      与 `pop_bridge._split_int`（**尾差归权重最大者，Σ 精确守恒**）——
      **不另写比例算法**（承「口径单点」）；
    · 路级无治所权重 ⇒ **返回空**并给 `no_weights`（**不臆造归属**）；
    · 路级 POP 读不到 ⇒ 各治所规模为 `None`（**缺失≠0**）；
    · **Σ 各治所规模 == 路级总量**（守恒，可自检）。
    """
    try:
        from core.foundation.ledger.pop_bridge import seat_pop_weights, _split_int
    except Exception:  # noqa: BLE001
        return []
    weights = seat_pop_weights(circuit)
    if not weights:
        return []
    labor_total = _labor_of(p)
    art_total = _artisans_of(p)
    ding_total = _service_ding_of(p)
    by_seat_labor = _split_int(labor_total, weights) if labor_total else {}
    by_seat_art = _split_int(art_total, weights) if art_total else {}
    by_seat_ding = _split_int(ding_total, weights) if ding_total else {}
    out: List[Dict[str, object]] = []
    for sid, _w in weights:
        lb = by_seat_labor.get(sid)
        ab = by_seat_art.get(sid)
        d = by_seat_ding.get(sid)
        e1 = dept_entity("民间营造", "pop", labor=lb, artisans=ab,
                         monthly=_seat_monthly(p, sid, lb, labor_total))
        e1.update({"route": circuit, "seat": sid, "level": "seat",
                   "mode": MODE_DERIVED, "derived": True})
        out.append(e1)
        e2 = dept_entity("官有营造", "local_gov", labor=lb, artisans=ab)
        e2["corvee_base"] = d
        e2.update({"route": circuit, "seat": sid, "level": "seat",
                   "mode": MODE_DERIVED, "derived": True})
        out.append(e2)
    return out


def _seat_monthly(p: Dict[str, object], seat_id: str,
                  seat_craft: Optional[int], route_craft: Optional[int]
                  ) -> Optional[Dict[str, object]]:
    """把**路级本月营造产出**按**该治所工匠占比**派生到治所。

    口径：
    · 路级 `dept_monthly` 缺失 ⇒ `None`（**缺失≠0**，不伪造「本月 0 产出」）|
    · 归属基准 = **工匠占比**（与规模拆分同源，口径一致）；
    · Σ 各治所 == 路级（**守恒**）|
    · **官有营造不派产出**：营造引擎目前只跑**民间**建筑
      （`dept_monthly.dept="民间营造"`），官有产出为 `None` 而**非 0**
      （避免把「未实现」显示成「没干活」）。
    """
    dm = p.get("dept_monthly")
    if not isinstance(dm, dict):
        return None
    if str(dm.get("dept")) != "民间营造":
        return None
    if not seat_craft or not route_craft:
        return None
    share = float(seat_craft) / float(route_craft)
    hours = float(dm.get("hired_hours") or 0.0) * share
    coin = int(round(float(dm.get("coin") or 0) * share))
    built = float(dm.get("built") or 0) * share
    return {"built": round(built, 3), "hired_hours": round(hours, 3),
            "coin": coin, "corvee_days": None, "mood_cost": None,
            "attribution": "labor_share"}

def run_checks4():
    """**派生**部门实体自检（第四批）。"""
    out = []

    def add(n, ok, note=""):
        out.append((n, bool(ok), note))

    st = {"prefectures": {"京畿路": {"pops": {"工匠": {"size": 30}, "农": {"size": 100, "ding": 900}}}}}
    p = st["prefectures"]["京畿路"]
    ds = departments_all_derived(st, "京畿路", p)
    add("29 派生可枚举", len(ds) > 0 and all(e["level"] == "seat" for e in ds), "%d 实体" % len(ds))

    add("30 标为派生", all(e.get("derived") is True for e in ds), "derived=True")

    add("31 mode=derived", all(e.get("mode") == MODE_DERIVED for e in ds), MODE_DERIVED)

    civ = [e for e in ds if e["dept_id"] == "民间营造"]
    off = [e for e in ds if e["dept_id"] == "官有营造"]
    add("32 Σ民间劳力守恒", sum(e["labor"] for e in civ) == 100,
        "Σ=%d 路级=100" % sum(e["labor"] for e in civ))

    add("33 Σ官有劳力守恒", sum(e["labor"] for e in off) == 100,
        "Σ=%d 路级应=100+900=1000" % sum(e["labor"] for e in off))

    add("34 两部门同治所配对", len(civ) == len(off), "%d vs %d" % (len(civ), len(off)))

    add("35 无权重⇒空", departments_all_derived({}, "无此路", {}) == [], "[]")

    st2 = {"prefectures": {"京畿路": {}}}
    ds2 = departments_all_derived(st2, "京畿路", st2["prefectures"]["京畿路"])
    add("36 缺POP⇒规模None", len(ds2) > 0 and all(e["labor"] is None for e in ds2),
        "实体存在，规模=None（缺失≠0）")

    add("37 派生不改state", "seats" not in p, "state 未被写入")

    return out

def run_checks5():
    """**月度产出**入实体自检（第五批，含非零验证）。"""
    out = []

    def add(n, ok, note=""):
        out.append((n, bool(ok), note))

    st = {"prefectures": {"京畿路": {
        "pops": {"工匠": {"size": 30}, "农": {"size": 100, "ding": 900}},
        "dept_monthly": {"built": 10, "hired_hours": 5000.0, "coin": 3000,
                         "corvee_days": None, "mood_cost": None, "dept": "民间营造"},
    }}}
    p = st["prefectures"]["京畿路"]
    ds = departments_all_derived(st, "京畿路", p)
    civ = [e for e in ds if e["dept_id"] == "民间营造"]
    add("38 非零产出派发", len(civ) > 0 and any(e["monthly"]["hired_hours"] > 0 for e in civ),
        "%d 治所有产出" % len(civ))

    sh = sum(e["monthly"]["hired_hours"] for e in civ)
    add("39 工时Σ守恒", abs(sh - 5000.0) < 0.5, "Σ=%.3f 路级=5000" % sh)

    sc = sum(e["monthly"]["coin"] for e in civ)
    add("40 工钱Σ近似守恒", abs(sc - 3000) <= max(2, len(civ)), "Σ=%d 路级=3000" % sc)

    sb = sum(e["monthly"]["built"] for e in civ)
    add("41 建成Σ守恒", abs(sb - 10.0) < 0.05, "Σ=%.3f 路级=10" % sb)

    add("42 归属基准标注", all(e["monthly"]["attribution"] == "labor_share" for e in civ),
        "labor_share")

    off = [e for e in ds if e["dept_id"] == "官有营造"]
    add("43 官有产出=None", all(e["monthly"] is None for e in off),
        "None（未实现，非 0）")

    st2 = {"prefectures": {"京畿路": {"pops": {"工匠": {"size": 100}, "农": {"ding": 900}}}}}
    ds2 = departments_all_derived(st2, "京畿路", st2["prefectures"]["京畿路"])
    add("44 无产出⇒None", all(e["monthly"] is None for e in ds2),
        "缺失≠0")

    return out



# ============================================================
# 语义更正（2026-10-05，用户指出）
#
# 用户：「工匠可不止建筑工」「宋代匠人可不是一般建筑工，一般建筑工都属于劳力」
#        「通常由贫民务工」。
#
# 查证（building_jobs.py）：L38 SONG_JOB_CLASSES = (农, 工匠, 商人)；
#   L42 「工匠约 40 万 vs 一座工坊 160 岗」；L58 "工坊": {"工匠": 160}
#   => 本作「工匠」= **工坊里的手工业者**，**不是营造劳力**。
#
# => 本模块原以 工匠.size 作营造部门规模，**口径错误**，已更正：
#   劳力 = 农.size（贫民务工，营造主力）
#   匠人 = 工匠.size（约 40 万，工坊精细活，非营造劳力）
#   劳役 = service_ding_of（农的丁，原口径已正确）
# ============================================================

def _labor_of(p: Dict[str, object]) -> Optional[int]:
    """**劳力**（营造劳力）：取自 `农.size`（贫民/常民务工）。

    ⚠️ **不是** `工匠`（匠人是工坊手工业者，承用户 2026-10-05 更正）。
    """
    pops = p.get("pops")
    if not isinstance(pops, dict):
        return None
    nong = pops.get("农")
    if not isinstance(nong, dict):
        return None
    v = nong.get("size")
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    return int(max(0, v))


def _artisans_of(p: Dict[str, object]) -> Optional[int]:
    """**匠人**（工坊手工业者）：`工匠.size`。

    ⚠️ **不是营造劳力**；营造部门可请匠人做精细活，但**规模基准仍是劳力**。
    """
    pops = p.get("pops")
    if not isinstance(pops, dict):
        return None
    c = pops.get("工匠")
    if not isinstance(c, dict):
        return None
    v = c.get("size")
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    return int(max(0, v))