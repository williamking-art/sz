# -*- coding: utf-8 -*-
"""M36.7-B3 **1101 年历史人物候选库**（内容层；**只登记，不导入在朝名单**）。

用户提供约 200 人名册（2026-10-11），并要求**三维严格分离**：
- `historical_status_at_1101`：**在世**（A 候选／B 待核／C 已故／D 后续时代）
- `office_status`：**在任/在册/可否参与廷议**（来源＝既有 `MINISTERS`；本模块**不写**）
- `game_domains`：适合参与的政务领域（与在职状态**无关**）

**铁律**（由测试钉住）：
1. **不得批量导入**：本模块**不修改** `MINISTERS`，不给任何人设 `in_office=True`；
2. **不编造**：`birth_year`/`death_year`/`historical_offices` 未核验 ⇒ `None`／`unknown`；
   本轮 `historical_status_at_1101` 只据**用户名册分组**给出，一律带 `verify=True`；
3. **C/D 组不得入选廷议**（"适合军事廷议" ≠ "1101 年在世"）；
4. `game_domains` 只允许 `DOMAIN_ENUM` 内取值；未核定 ⇒ 空集。
"""
from typing import Any, Dict, List, Optional, Tuple

from content.ministers.data import MINISTERS
from content.ministers.registry import DOMAIN_ENUM

__all__ = ["ROSTER_SCHEMA_FIELDS", "STATUS_AT_1101", "GROUP_STATUS", "ROSTER_1101",
           "roster_entry", "roster_by_status", "roster_duplicates",
           "roster_candidates_1101", "roster_note"]

#: 用户指定的九字段（数据表契约）
ROSTER_SCHEMA_FIELDS: Tuple[str, ...] = (
    "name", "birth_year", "death_year", "historical_offices", "political_alignment",
    "game_domains", "historical_status_at_1101", "in_office", "source_notes")

STATUS_AT_1101: Tuple[str, ...] = ("candidate", "not_default_active", "pre_deceased",
                                   "later_era", "unknown")
#: 名册分组 → 1101 状态（用户分组语义；一律待逐人校勘）
GROUP_STATUS: Dict[int, str] = {1: "candidate",            # A：开局优先核验候选
                                2: "not_default_active",   # B：在世但不应默认在朝
                                3: "pre_deceased",         # C：北宋前中期已故名臣
                                4: "later_era"}            # D：徽宗后期/南宋初 后续时代

#: 第一组（A）：开局优先核验候选——带领域（据用户名册「适合的游戏职责」映射；未核定留空）
_G1: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("韩忠彦", ("personnel",)), ("曾布", ("finance", "military")), ("蔡卞", ("personnel",)),
    ("许将", ("personnel",)), ("邓洵武", ("personnel",)), ("黄履", ("finance",)),
    ("林希", ("culture",)), ("赵挺之", ("personnel",)), ("吕惠卿", ("finance",)),
    ("蔡京", ("finance",)), ("章惇", ("military",)), ("蔡确", ("personnel",)),
    ("王珪", ("culture",)), ("吕大防", ("finance",)), ("范纯仁", ("agri",)),
    ("梁焘", ("personnel",)), ("王岩叟", ("personnel",)), ("郑雍", ("personnel",)),
    ("孙永", ("agri",)), ("韩维", ("culture",)), ("吕公著", ("personnel",)),
    ("司马光", ("finance", "culture")), ("文彦博", ("personnel",)),
    ("富弼", ("agri", "diplomacy")), ("韩琦", ("military",)), ("王安石", ("finance",)),
    ("曾公亮", ("military",)), ("欧阳修", ("culture",)), ("苏颂", ("works", "culture")),
    ("章楶", ("military",)), ("王韶", ("military",)), ("种谔", ("military",)),
    ("折可适", ("military",)), ("游师雄", ("military",)),
    ("韩维", ("culture",)),          # ← 用户名册第 20/#29 两见（**保留重复，不擅自合并**）
)
#: 第二组（B）：外任/退居（在世但不默认在朝）
_G2: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("苏轼", ("agri", "culture")), ("苏辙", ("finance",)), ("黄庭坚", ("culture",)),
    ("秦观", ("culture",)), ("晁补之", ("culture",)), ("张耒", ("culture",)),
    ("陈师道", ("culture",)), ("李格非", ("culture",)), ("刘安世", ("personnel",)),
    ("朱光庭", ("personnel",)), ("范祖禹", ("culture",)), ("赵瞻", ("personnel",)),
    ("傅尧俞", ("personnel",)), ("王存", ("personnel",)), ("吕陶", ("personnel",)),
    ("范百禄", ("personnel",)), ("刘挚", ("personnel",)), ("王觌", ("personnel",)),
    ("赵君锡", ("personnel",)), ("孙觉", ("culture",)), ("程颐", ("culture",)),
    ("程颢", ("culture",)), ("张载", ("culture",)), ("邵雍", ("culture",)),
    ("周敦颐", ("culture",)), ("胡瑗", ("culture",)), ("孙复", ("culture",)),
    ("石介", ("culture",)), ("李觏", ("culture", "finance")), ("张方平", ("finance",)),
)
#: 第三组（C：北宋前中期已故名臣）／第四组（D：徽宗后期与南宋初）——**仅登记姓名**（不设领域，免误用）
_G3: Tuple[str, ...] = ("范仲淹", "包拯", "狄青", "寇准", "王旦", "吕夷简", "晏殊", "宋祁",
                        "宋庠", "田况", "庞籍", "韩亿", "王曾", "陈尧佐", "陈执中", "章得象",
                        "宋绶", "杨亿", "王禹偁", "田锡", "寇瑊", "李沆", "向敏中", "毕士安",
                        "王钦若", "丁谓", "曹利用", "王继忠", "杨业", "杨延昭", "曹彬", "潘美",
                        "李继隆", "王超", "曹玮", "任福", "葛怀敏", "范雍", "尹洙", "欧阳发",
                        "曾巩", "梅尧臣", "苏舜钦", "石延年", "蔡襄", "余靖", "王素", "孙沔",
                        "杜衍", "范讽", "韩绛", "吕公弼", "王雱", "赵抃", "唐介", "王安礼",
                        "李宪", "王中正", "郭逵", "刘昌祚",
                        # 用户名册第三组内**与前组重见**者（保留重复，不合并；供 roster_duplicates 报告）
                        "韩维", "文彦博", "富弼", "韩琦", "王安石", "吕惠卿", "曾布", "章惇",
                        "蔡确", "王珪", "吕大防", "刘挚", "范纯仁", "司马光", "包拯", "王韶",
                        "种谔", "章楶", "折可适", "游师雄")
_G4: Tuple[str, ...] = ("李纲", "宗泽", "岳飞", "韩世忠", "张俊", "刘光世", "吴玠", "吴璘",
                        "杨沂中", "刘锜", "张浚", "赵鼎", "吕颐浩", "秦桧", "赵构", "赵昚",
                        "赵惇", "赵扩", "韩侂胄", "史弥远", "真德秀", "魏了翁", "朱熹", "张栻",
                        "陆九渊", "陈亮", "叶适", "辛弃疾", "陆游", "杨万里", "范成大", "洪适",
                        "洪遵", "周必大", "王淮", "葛邲", "陈俊卿", "虞允文", "张孝祥", "赵汝愚",
                        "史浩", "楼钥", "李焘", "徐梦莘", "王应麟", "袁枢", "洪迈", "罗愿",
                        "陈傅良", "薛季宣", "陈宓", "袁燮", "李心传", "赵汝适",
                        "陈亮")          # ← 用户名册第 171/#185 两见（保留重复）


def _entry(name: str, group: int, domains: Tuple[str, ...]) -> Dict[str, Any]:
    """构造一条候选档案（来源＝用户名册；**未核验字段一律 `None`／`unknown`，不编造**）。"""
    fig = MINISTERS.get(name) or {}
    return {"name": name,
            "birth_year": fig.get("born"),                 # 仅既有登记者有；否则 None
            "death_year": None,                            # 名册未提供 ⇒ 待校勘
            "historical_offices": None,                    # 待逐人史实校勘
            "political_alignment": fig.get("faction") or None,
            "game_domains": tuple(d for d in domains if d in DOMAIN_ENUM),
            "historical_status_at_1101": GROUP_STATUS.get(group, "unknown"),
            "in_office": fig.get("in_office") if fig else None,   # **只读**既有；本模块不写
            "verify": True,                                # 用户明示：待逐人史实校勘
            "source_notes": f"用户名册 第{group}组（待逐人史实校勘）"}


ROSTER_1101: Tuple[Dict[str, Any], ...] = tuple(
    [_entry(n, 1, d) for n, d in _G1] + [_entry(n, 2, d) for n, d in _G2]
    + [_entry(n, 3, ()) for n in _G3] + [_entry(n, 4, ()) for n in _G4])


def roster_entry(name: str) -> Optional[Dict[str, Any]]:
    """按名取档（只读，浅拷贝）。"""
    for e in ROSTER_1101:
        if e["name"] == name:
            return dict(e)
    return None


def roster_by_status(status: str) -> List[Dict[str, Any]]:
    """按 1101 状态取档（只读）。"""
    return [dict(e) for e in ROSTER_1101 if e["historical_status_at_1101"] == status]


def roster_duplicates() -> Dict[str, int]:
    """名册内重复姓名计数（用户已提示存在重复；**只报告，不擅自合并**）。"""
    counts: Dict[str, int] = {}
    for e in ROSTER_1101:
        counts[str(e["name"])] = counts.get(str(e["name"]), 0) + 1
    return {k: v for k, v in counts.items() if v > 1}


def roster_conflicts() -> Dict[str, List[str]]:
    """**同名多状态**冲突（重复人物的必然产物）：返回 `{name: [status...]}`。

    规则：数据自相矛盾 ⇒ 视为 **unknown ⇒ 一律不入候选**（不猜哪个对，待逐人校勘）。
    """
    seen: Dict[str, set] = {}
    for e in ROSTER_1101:
        seen.setdefault(str(e["name"]), set()).add(str(e["historical_status_at_1101"]))
    return {k: sorted(v) for k, v in seen.items() if len(v) > 1}


def roster_candidates_1101(state=None, issue_domains=(), max_n: int = 3) -> Dict[str, Any]:
    """**开局可用候选**＝1101 候选状态 ∧ **既有登记且在朝**（`MINISTERS.in_office is True`）。

    B／C／D 组、未在朝者、**同名多状态（重复且矛盾）者**一律排除
    （"适合某领域" ≠ "在世" ≠ "在朝"；矛盾数据 ⇒ unknown ⇒ 不入选）。
    返回 `{participants, blocked_by_status, blocked_by_office, blocked_by_conflict, rule}`；**只读**。
    """
    want = set(d for d in (issue_domains or []) if d in DOMAIN_ENUM)
    conflicts = roster_conflicts()
    participants: List[Dict[str, Any]] = []
    blocked_status: List[Dict[str, str]] = []
    blocked_office: List[Dict[str, str]] = []
    blocked_conflict: List[Dict[str, Any]] = []
    for e in ROSTER_1101:
        name = str(e["name"])
        st = e["historical_status_at_1101"]
        if name in conflicts:
            blocked_conflict.append({"name": name, "statuses": conflicts[name]})
            continue
        if st != "candidate":
            blocked_status.append({"name": name, "status": st})
            continue
        if e["in_office"] is not True:
            blocked_office.append({"name": name,
                                   "reason": "不在册或非在朝（in_office 未 True）"})
            continue
        if want and not (set(e["game_domains"]) & want):
            continue
        participants.append({"name": name, "domains": list(e["game_domains"]),
                             "selected_by": "roster_candidate"})
    return {"participants": participants[: int(max_n)],
            "blocked_by_status": blocked_status, "blocked_by_office": blocked_office,
            "blocked_by_conflict": blocked_conflict,
            "conflicts": conflicts,
            "rule": ("1101 候选 ∧ 既有登记 ∧ in_office=True 方可入选；"
                     "B/C/D 组、未在朝者、**同名多状态者**一律排除（不因领域适配而例外）"),
            "note": "候选库只登记；**不导入**在朝名单，不设 in_office"}


def roster_note() -> str:
    """候选库自述（供台账/UI 引用）。"""
    def _n(st: str) -> int:
        return len([e for e in ROSTER_1101 if e["historical_status_at_1101"] == st])
    return (f"候选库 {len(ROSTER_1101)} 人（用户名册）：A={_n('candidate')}／"
            f"B={_n('not_default_active')}／C={_n('pre_deceased')}／D={_n('later_era')}；"
            f"重复姓名 {sorted(roster_duplicates())}；未核验字段一律 None/unknown")


