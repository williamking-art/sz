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
    "DEPT_LABELS", "OFFICIAL_OWNERS", "dept_entity", "departments_of", "departments_of_seat", "departments_all", "run_checks", "run_checks2", "run_checks3",
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
                  craftsmen: Optional[int] = None,
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
        "owner_kind": owner_kind, "craftsmen": craftsmen,
        "official": department == "官有营造",
        "monthly": None, "built": None, "hired_hours": None,
        "corvee_days": None, "coin": None, "mood_cost": None,
    }
    if monthly is not None:
        out["monthly"] = {k: monthly.get(k) for k in
                           ("built", "hired_hours", "corvee_days", "coin", "mood_cost")}
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
        crafts = _craftsmen_of(p)
        ding = _service_ding_of(p)
        out.append(dept_entity("民间营造", "pop", craftsmen=crafts))
        out.append(dept_entity("官有营造", "local_gov",
                               craftsmen=None if crafts is None else crafts + (ding or 0)))
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
    e = dept_entity("官有营造", "local_gov", craftsmen=100, monthly={"built": 2})
    add("13 实体四要素", all(k in e for k in ("dept_id", "label", "owner_kind", "craftsmen", "monthly")),
        "label=%s owner=%s craft=%s" % (e["label"], e["owner_kind"], e["craftsmen"]))

    # 14 官有标记
    c = dept_entity("民间营造", "pop")
    add("14 官有标记", e["official"] is True and c["official"] is False, "民间=False 官有=True")

    # 15 未知部门/归属被拒
    add("15 非法输入被拒", dept_entity("野部门", "pop")["ok"] is False
        and dept_entity("民间营造", "山寨")["ok"] is False, "unknown_department/owner")

    # 16 月度产出缺失 ⇒ None（不伪造 0）
    n = dept_entity("民间营造", "pop", craftsmen=None)
    add("16 产出缺失≠0", n["built"] is None and n["monthly"] is None and n["craftsmen"] is None,
        "built=None monthly=None craft=None")

    # 17 逐路枚举（2 路 x 2 部门）
    st = {"prefectures": {"A": {"pops": {"工匠": {"size": 10}, "农": {"ding": 100}}},
                              "B": {"pops": {"工匠": {"size": 5}, "农": {"ding": 50}}}}}
    ds = departments_of(st)
    add("17 逐路枚举", len(ds) == 4 and ds[0]["route"] == "A", "2 路 x 2 = %d" % len(ds))

    # 18 官有规模 = 工匠 + 应役丁
    add("18 官有含丁", ds[0]["craftsmen"] == 10 and ds[1]["craftsmen"] == 110,
        "民间=%s 官有=%s（工匠+丁）" % (ds[0]["craftsmen"], ds[1]["craftsmen"]))

    # 19 缺 POP ⇒ 规模 None
    ds2 = departments_of({"prefectures": {"C": {}}})
    add("19 缺数据⇒None", ds2[0]["craftsmen"] is None and ds2[1]["craftsmen"] is None, "C 路无 POP")

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
    crafts = _craftsmen_of(seat)
    ding = _service_ding_of(seat)
    out = [dept_entity("民间营造", "pop", craftsmen=crafts)]
    out.append(dept_entity("官有营造", "local_gov",
                           craftsmen=None if crafts is None else crafts + (ding or 0)))
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

    st = {"prefectures": {"A": {"seats": {"s1": {"pops": {"工匠": {"size": 8}, "农": {"ding": 90}}}}}}}
    r = departments_all(st)
    add("21 州府级枚举", r["ok"] and r["seats_covered"] == 1 and len(r["departments"]) == 2,
        "1 治所 x 2 = %d" % len(r["departments"]))

    e0, e1 = r["departments"][0], r["departments"][1]
    add("22 带治所坐标", e0["route"] == "A" and e0["seat"] == "s1" and e0["level"] == "seat",
        "route=%s seat=%s level=%s" % (e0["route"], e0["seat"], e0["level"]))

    add("23 官有规模=工匠+丁", e0["craftsmen"] == 8 and e1["craftsmen"] == 98,
        "民间=%s 官有=%s" % (e0["craftsmen"], e1["craftsmen"]))

    n = departments_all({"prefectures": {"A": {}}})
    add("24 无seats⇒空且说明", (not n["ok"]) and n["reason"] == "no_seats" and n["seats_covered"] == 0,
        "reason=%s（**不回落路级**）" % n["reason"])

    add("25 无prefectures⇒空", departments_all({})["reason"] == "no_prefectures", "no_prefectures")

    ds = departments_of_seat({}, "B", "s9")
    add("26 空治所仍有两实体", len(ds) == 2 and ds[0]["craftsmen"] is None,
        "实体存在但规模未知 ⇒ None")

    add("27 非dict治所⇒空", departments_of_seat(None, "B", "s9") == [], "[]")

    add("28 两部门不合并", ds[0]["dept_id"] != ds[1]["dept_id"] and ds[0]["owner_kind"] == "pop"
        and ds[1]["owner_kind"] == "local_gov", "民间=pop 官有=local_gov")

    return out