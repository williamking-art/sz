# -*- coding: utf-8 -*-
"""北宋 21 路省路级四监司与路府知通人事底册与运转模型（单一权威源）。

## 规格与背景（M303）

落实北宋地方行政架构的核心支柱：
北宋无元明清之巡抚总督，路级权力由**四监司**（外台）相互分权制衡：
1. **帅司（经略安抚使司 / 安抚使司）**：掌兵马保甲、边防御敌、盗贼进剿；沿边领经略安抚使，内地领安抚使；
2. **漕司（都转运使司 / 转运使司）**：掌一路赋税经总钱、上供漕运、榷盐矾铁坑冶、度支仓廪；
3. **宪司（提点刑狱公事司）**：掌司法刑名、纠察官箴、按核冤狱、录囚辩谳；
4. **仓司（提举常平茶盐公事司）**：掌常平义仓积谷、平粜籴、农田水利、青苗免役钱及茶盐钞引。
5. **路治首府知通（知通互掣）**：
   - **知府 / 知州**：一路首府亲民长官，总摄民政；
   - **通判**：天子耳目，副贰知州，“凡兵民钱谷文书非通判连署不得施行”，专折奏事防闲长官。

本模块提供省路级主要官员的开局底册生成、状态读取、任免调动与考课联动。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from core.domains.economy.macro_climate import ALL_CIRCUITS_21
from core.domains.administration.prefect_officials import (
    OfficialNameAllocator, ensure_person_identity,
)

log = logging.getLogger("circuit_officials")

__all__ = [
    "get_circuit_officials",
    "init_all_circuit_officials",
    "appoint_circuit_official",
    "dismiss_circuit_official",
    "CIRCUIT_OFFICIAL_ROLES",
]

# 四监司与首府官职定义
CIRCUIT_OFFICIAL_ROLES = {
    "shuai": {"name": "帅司", "title_border": "经略安抚使", "title_inner": "安抚使", "rank": "正三品", "domain": "军政防务"},
    "cao":   {"name": "漕司", "title_border": "都转运使", "title_inner": "转运使", "rank": "从三品", "domain": "财赋漕运"},
    "xian":  {"name": "宪司", "title_border": "提点刑狱公事", "title_inner": "提点刑狱公事", "rank": "从四品", "domain": "司法风宪"},
    "cang":  {"name": "仓司", "title_border": "提举常平茶盐", "title_inner": "提举常平使", "rank": "正五品", "domain": "常平水利"},
    "prefect": {"name": "首府长官", "title_border": "知府", "title_inner": "知州", "rank": "正四品", "domain": "路治民政"},
    "vice_prefect": {"name": "首府通判", "title_border": "通判", "title_inner": "通判", "rank": "从六品", "domain": "监察同署"},
}

# 沿边诸路（安抚使升格为经略安抚使）
BORDER_CIRCUITS = {
    "河北东路", "河北西路", "河东路", "陕西路", "鄜延路", "环庆路", "泾原路", "熙河路", "秦凤路"
}

# 各路首府府名
CIRCUIT_CAPITALS = {
    "京畿路": "开封府", "京东东路": "青州", "京东西路": "应天府", "京西南路": "襄阳府", "京西北路": "河南府",
    "河北东路": "大名府", "河北西路": "定州", "河东路": "太原府", "陕西路": "京兆府",
    "淮南东路": "扬州", "淮南西路": "庐州", "两浙路": "杭州", "江南东路": "江宁府",
    "江南西路": "洪州", "荆湖北路": "江陵府", "荆湖南路": "潭州", "福建路": "福州",
    "成都府路": "成都府", "梓州路": "梓州", "利州路": "兴元府", "夔州路": "夔州",
    "广南东路": "广州", "广南西路": "桂州",
}

# 考据重臣与名臣在任指派（建中靖国元年 1101）
HISTORICAL_ASSIGNMENTS = {
    "京畿路": {
        "prefect": {"name": "吴居厚", "faction": "新党", "rank": "从三品", "integrity": 0.50, "ability": 0.85, "traits": ["聚敛", "吏干"]},
        "cao":     {"name": "王古", "faction": "中立派", "rank": "正二品", "integrity": 0.75, "ability": 0.80, "traits": ["理财", "慎密"]},
    },
    "两浙路": {
        "cao":     {"name": "唐恪", "faction": "中立派", "rank": "从三品", "integrity": 0.70, "ability": 0.78, "traits": ["干练", "理财"]},
        "shuai":   {"name": "童贯", "faction": "皇党集团", "rank": "正五品", "integrity": 0.40, "ability": 0.70, "traits": ["逢迎", "军略"]},
        "xian":    {"name": "江公望", "faction": "旧党", "rank": "从四品", "integrity": 0.88, "ability": 0.82, "traits": ["刚直", "守正"]},
    },
    "河东路": {
        "shuai":   {"name": "种师道", "faction": "军功集团", "rank": "正四品", "integrity": 0.85, "ability": 0.90, "traits": ["老成", "军略", "忠勇"]},
        "prefect": {"name": "章楶", "faction": "军功集团", "rank": "正二品", "integrity": 0.80, "ability": 0.88, "traits": ["边防", "宿将"]},
    },
    "京东东路": {
        "prefect": {"name": "张叔夜", "faction": "军功集团", "rank": "从六品", "integrity": 0.78, "ability": 0.82, "traits": ["忠勇", "守城"]},
        "xian":    {"name": "陈瓘", "faction": "旧党", "rank": "从四品", "integrity": 0.90, "ability": 0.85, "traits": ["刚直", "清正"]},
    },
    "陕西路": {
        "shuai":   {"name": "姚古", "faction": "军功集团", "rank": "正四品", "integrity": 0.75, "ability": 0.80, "traits": ["宿将", "勇毅"]},
    },
    "河北西路": {
        "shuai":   {"name": "刘法", "faction": "军功集团", "rank": "正四品", "integrity": 0.78, "ability": 0.86, "traits": ["骁勇", "善战"]},
    },
    "江南西路": {
        "prefect": {"name": "聂昌", "faction": "中立派", "rank": "从四品", "integrity": 0.72, "ability": 0.75, "traits": ["敢任事", "清介"]},
    },
    "福建路": {
        "xian":    {"name": "陈师锡", "faction": "旧党", "rank": "从四品", "integrity": 0.86, "ability": 0.80, "traits": ["切直", "清正"]},
    },
    "荆湖南路": {
        "prefect": {"name": "宗泽", "faction": "军功集团", "rank": "从六品", "integrity": 0.90, "ability": 0.88, "traits": ["忠勇", "抗金"]},
    },
}

# 默认官员名字池（北宋常见姓名与字号，用于未指定历史重臣的监司岗位）
_DEFAULT_NAME_POOLS = [
    ("王宗望", "旧党", ["清慎", "守法"]), ("李及", "旧党", ["端直", "循吏"]),
    ("赵瞻", "旧党", ["正派", "理财"]), ("范百禄", "旧党", ["文雅", "厚重"]),
    ("吕希绩", "旧党", ["守道", "奉公"]), ("苏辙", "旧党", ["文章", "通达"]),
    ("徐禧", "新党", ["变法", "聚敛"]), ("蔡卞", "新党", ["机敏", "附新"]),
    ("陆师闵", "新党", ["理财", "吏干"]), ("贾易", "新党", ["急切", "权谋"]),
    ("李夔", "中立派", ["敏悟", "练达"]), ("张询", "中立派", ["能算", "漕运"]),
    ("沈括", "中立派", ["博洽", "营造"]), ("宇文昌龄", "中立派", ["平恕", "明断"]),
    ("折可适", "军功集团", ["骁勇", "善谋"]), ("苗履", "军功集团", ["宿卫", "善射"]),
    ("王恩", "军功集团", ["严整", "步骑"]), ("刘仲武", "军功集团", ["持重", "果断"]),
]


def _build_default_circuit(circuit: str, index: int,
                           allocator: Optional[OfficialNameAllocator] = None) -> Dict[str, Any]:
    """为某一单路生成标准四监司与首府知通档案（P1-6：唯一 person_id/姓名）。"""
    is_border = circuit in BORDER_CIRCUITS
    capital_city = CIRCUIT_CAPITALS.get(circuit, "首府")
    historical = HISTORICAL_ASSIGNMENTS.get(circuit, {})
    allocator = allocator or OfficialNameAllocator()

    officials = {}
    
    # 逐一生成 6 个核心官职
    role_order = ["shuai", "cao", "xian", "cang", "prefect", "vice_prefect"]
    for step_i, r_key in enumerate(role_order):
        spec = CIRCUIT_OFFICIAL_ROLES[r_key]
        title = spec["title_border"] if is_border else spec["title_inner"]
        if r_key == "prefect":
            title = f"知{capital_city}军州事"
        elif r_key == "vice_prefect":
            title = f"{capital_city}通判"

        if r_key in historical:
            h_data = historical[r_key]
            _name, _pid, _hist = allocator.make(
                h_data["name"], prefix="cb", historical=True)
            officials[r_key] = {
                "role_key": r_key,
                "role_name": spec["name"],
                "official_title": title,
                "name": _name,
                "person_id": _pid,
                "faction": h_data.get("faction", "中立派"),
                "rank": h_data.get("rank", spec["rank"]),
                "domain": spec["domain"],
                "integrity": float(h_data.get("integrity", 0.70)),
                "ability": float(h_data.get("ability", 0.75)),
                "traits": list(h_data.get("traits", ["恪尽职守"])),
                "term_months": 12,
                "effectiveness": float(round((h_data.get("integrity", 0.7) + h_data.get("ability", 0.75)) / 2.0, 2)),
                "historical": _hist,
            }
        else:
            name_tuple = _DEFAULT_NAME_POOLS[(index * 7 + step_i) % len(_DEFAULT_NAME_POOLS)]
            _pref_name, faction, traits = name_tuple
            _name, _pid, _hist = allocator.make(
                _pref_name, prefix="cb", historical=True)
            integrity = 0.60 + ((index + step_i) % 5) * 0.06
            ability = 0.65 + ((index * 2 + step_i) % 5) * 0.05
            officials[r_key] = {
                "role_key": r_key,
                "role_name": spec["name"],
                "official_title": title,
                "name": _name,
                "person_id": _pid,
                "faction": faction,
                "rank": spec["rank"],
                "domain": spec["domain"],
                "integrity": float(round(integrity, 2)),
                "ability": float(round(ability, 2)),
                "traits": traits,
                "term_months": (index + step_i * 3) % 24 + 6,
                "effectiveness": float(round((integrity + ability) / 2.0, 2)),
                "historical": _hist,
            }

    return {
        "circuit": circuit,
        "capital": capital_city,
        "is_border": is_border,
        "officials": officials,
    }


def init_all_circuit_officials(state, *, store: bool = True,
                               reserved_names: Optional[set] = None,
                               reserved_ids: Optional[set] = None) -> Dict[str, Dict[str, Any]]:
    """初始化全国 21 路省路级四监司与知通官制底册。

    `store=False` 时只返回派生副本，不写 `state.circuit_officials`（供读函数兜底）。
    `reserved_names/ids` 与 prefect 册共享，保证跨册 person_id/姓名唯一（P1-6）。
    """
    c_officials = getattr(state, "circuit_officials", None)
    if isinstance(c_officials, dict) and len(c_officials) >= len(ALL_CIRCUITS_21):
        # 已存在册也要把其姓名/id 回填到 reserved，供后续调用者跨册分配
        for _entry in c_officials.values():
            if not isinstance(_entry, dict):
                continue
            for _holder in (_entry.get("officials") or {}).values():
                if not isinstance(_holder, dict):
                    continue
                if reserved_names is not None and _holder.get("name"):
                    reserved_names.add(str(_holder["name"]))
                if reserved_ids is not None and _holder.get("person_id"):
                    reserved_ids.add(str(_holder["person_id"]))
        return c_officials

    used_names = reserved_names if isinstance(reserved_names, set) else set(reserved_names or ())
    used_ids = reserved_ids if isinstance(reserved_ids, set) else set(reserved_ids or ())
    allocator = OfficialNameAllocator(used_names, used_ids)
    # 先预占全部历史指派姓名，防止默认池先消耗同名历史人物
    for _roles in HISTORICAL_ASSIGNMENTS.values():
        for _h in _roles.values():
            allocator.reserve(_h.get("name"))

    all_data = {}
    for idx, c in enumerate(ALL_CIRCUITS_21):
        all_data[c] = _build_default_circuit(c, idx, allocator)

    if store:
        state.circuit_officials = all_data
    return all_data


def get_circuit_officials(state, circuit: str) -> Dict[str, Any]:
    """读取单一路的省路级主要官员（**纯只读**；未初始化时返回派生副本）。

    P1-5：不再惰性写 `state.circuit_officials`；显式初始化由
    `application/game_init.init_official_books` 负责。
    """
    c_officials = getattr(state, "circuit_officials", None)
    if not isinstance(c_officials, dict) or circuit not in c_officials:
        from types import SimpleNamespace
        c_officials = init_all_circuit_officials(
            SimpleNamespace(circuit_officials={}), store=False)

    record = c_officials.get(circuit)
    if isinstance(record, dict):
        return record
    
    # 兜底生成
    idx = ALL_CIRCUITS_21.index(circuit) if circuit in ALL_CIRCUITS_21 else 0
    return _build_default_circuit(circuit, idx)


def appoint_circuit_official(
    state,
    circuit: str,
    role_key: str,
    official_data: Dict[str, Any],
    executor: Any = None,
) -> bool:
    """任命/改任某一省路级主官（受控写操作）。

    参数：
        circuit: 路名（如 "两浙路"）
        role_key: 官职键名（"shuai" / "cao" / "xian" / "cang" / "prefect" / "vice_prefect"）
        official_data: 官员字典（含 name, faction, rank, integrity, ability 等）
        executor: 可选承办主体；**不传 = 旧行为**；传了则必须掌「官吏铨选」
    """
    if circuit not in ALL_CIRCUITS_21 or role_key not in CIRCUIT_OFFICIAL_ROLES:
        return False
    from core.permission_model import personnel_authority
    ok, _label, _mode = personnel_authority(state, executor)
    if not ok:
        return False

    c_map = init_all_circuit_officials(state)
    circuit_entry = c_map.setdefault(circuit, _build_default_circuit(circuit, 0))
    offs = circuit_entry.setdefault("officials", {})

    spec = CIRCUIT_OFFICIAL_ROLES[role_key]
    is_border = circuit in BORDER_CIRCUITS
    title = spec["title_border"] if is_border else spec["title_inner"]
    if role_key == "prefect":
        title = f"知{circuit_entry.get('capital', '本州')}军州事"
    elif role_key == "vice_prefect":
        title = f"{circuit_entry.get('capital', '本州')}通判"

    name = str(official_data.get("name", "待命官员"))
    person_id = str(official_data.get("person_id") or "").strip()
    historical = bool(official_data.get("historical", False))
    if not person_id:
        name, person_id, historical = ensure_person_identity(
            state, name, prefix="cb", historical=historical)
    faction = str(official_data.get("faction", "中立派"))
    rank = str(official_data.get("rank", spec["rank"]))
    integ = float(official_data.get("integrity", 0.70))
    abil = float(official_data.get("ability", 0.70))
    traits = list(official_data.get("traits", ["慎密"]))

    offs[role_key] = {
        "role_key": role_key,
        "role_name": spec["name"],
        "official_title": title,
        "name": name,
        "person_id": person_id,
        "faction": faction,
        "rank": rank,
        "domain": spec["domain"],
        "integrity": float(round(integ, 2)),
        "ability": float(round(abil, 2)),
        "traits": traits,
        "term_months": 0,
        "effectiveness": float(round((integ + abil) / 2.0, 2)),
        "historical": historical,
    }
    return True


def dismiss_circuit_official(state, circuit: str, role_key: str, reason: str = "罢免",
                             executor: Any = None) -> Optional[Dict[str, Any]]:
    """罢免调离某一省路主官，暂时空缺由通判/判官权知代理。

    `executor` 不传 = 旧行为；传了则必须掌「官吏铨选」，否则返回 `None` 且不改 state。
    """
    from core.permission_model import personnel_authority
    ok, _label, _mode = personnel_authority(state, executor)
    if not ok:
        return None
    c_map = init_all_circuit_officials(state)
    circuit_entry = c_map.get(circuit)
    if not circuit_entry:
        return None
    offs = circuit_entry.get("officials", {})
    old = offs.get(role_key)
    if not old:
        return None

    spec = CIRCUIT_OFFICIAL_ROLES.get(role_key, {})
    offs[role_key] = {
        "role_key": role_key,
        "role_name": spec.get("name", "监司"),
        "official_title": f"权发遣{spec.get('name', '司事')}",
        "name": "（缺员·通判权知）",
        "person_id": None,
        "faction": "无",
        "rank": "从七品",
        "domain": spec.get("domain", "杂务"),
        "integrity": 0.50,
        "ability": 0.50,
        "traits": ["代拆代行"],
        "term_months": 0,
        "effectiveness": 0.40,
        "historical": False,
        "vacant": True,
        "dismiss_reason": reason,
    }
    return old
