# -*- coding: utf-8 -*-
"""北宋 136 州府亲民官（知府/知州 + 通判）知通互掣与科举知县磨勘流转模型（单一权威源）。

## 规格与背景（M304）

落实北宋地方行政架构的核心亲民官层级：
1. **全国 136 州府席位（272 位在任亲民长官）**：
   - 每府设主官 1 名：**知府 / 知州 / 知军 / 知监**（中品绯袍，四至五品）；
   - 每府设副贰 1 名：**通判**（低品绿袍，六至七品）；
   - 与 `core.foundation.ledger.prefecture_entity.all_seats()`（136 个行政建制）严丝合缝对齐。
2. **知通公事连署制（分权制约核心）**：
   - 祖宗家法：“凡兵民钱谷文书，非通判连署不得施行”；
   - 若知府苛敛急躁而通判清廉鲠亮，通判拒不连署，行政效率骤降至 30%；
   - 若通判缺员，长官独断监察缺位，效率打折且滋生隐患；知通齐心则政通人和。
3. **科举知县池与三年磨勘改官池**：
   - 新科进士以知县、县丞起步（七至九品，绿袍公服）；
   - 入仕即在 `MemoryGraph` 挂载终身履历树与举主保任关系（`supports/guarantor`）；
   - 举主保任连坐：门生/荐举人因贪墨伏诛，举主连坐受罚夺秩。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from core.foundation.ledger.prefecture_entity import all_seats

log = logging.getLogger("prefect_officials")

__all__ = [
    "init_all_prefect_officials",
    "get_prefect_officials",
    "check_countersign",
    "appoint_prefect_official",
    "dismiss_prefect_official",
    "jinshi_to_county",
    "trigger_joint_liability",
]

# 常见举主重臣备选池
_CENTRAL_GUARANTORS = [
    "韩忠彦", "曾布", "李清臣", "赵挺之", "邓洵武", "王古", "蒋之奇", "陆佃", "陈次升"
]

# 地方亲民官名字库（保证生成多样性与历史宋味）
_PREFECT_NAMES = [
    ("苏轼", "旧党", ["文采", "刚直"], 0.85, 0.90),
    ("黄庭坚", "旧党", ["文士", "清正"], 0.88, 0.82),
    ("苏辙", "旧党", ["文章", "通达"], 0.82, 0.85),
    ("范百禄", "旧党", ["文雅", "厚重"], 0.78, 0.80),
    ("孔道辅", "旧党", ["刚直", "严正"], 0.90, 0.75),
    ("吕希绩", "旧党", ["守道", "奉公"], 0.80, 0.78),
    ("钱顗", "旧党", ["清廉", "风宪"], 0.86, 0.76),
    ("陈尧佐", "中立派", ["循良", "治水"], 0.78, 0.88),
    ("王及", "中立派", ["端直", "循吏"], 0.75, 0.80),
    ("胡宿", "旧党", ["老成", "持重"], 0.80, 0.82),
    ("范镇", "旧党", ["正派", "直言"], 0.84, 0.78),
    ("吴充", "中立派", ["守和", "调停"], 0.72, 0.75),
    ("蔡确", "新党", ["变法", "干练"], 0.40, 0.88),
    ("章惇", "新党", ["坚毅", "决断"], 0.45, 0.92),
    ("吕惠卿", "新党", ["变法", "才干"], 0.35, 0.86),
    ("李常", "旧党", ["笃实", "清慎"], 0.76, 0.74),
    ("孙觉", "旧党", ["纯厚", "学识"], 0.80, 0.72),
    ("程颐", "旧党", ["理学", "刚介"], 0.92, 0.65),
    ("陆佃", "旧党", ["守正", "调停"], 0.78, 0.80),
    ("温益", "新党", ["圆滑", "机变"], 0.42, 0.78),
]

_SUBPREFECT_NAMES = [
    ("李若水", "旧党", ["忠勇", "刚正"], 0.92, 0.80),
    ("陈东", "旧党", ["慷慨", "直谏"], 0.90, 0.72),
    ("欧阳澈", "旧党", ["抗直", "敢言"], 0.88, 0.70),
    ("汪伯彦", "新党", ["逢迎", "和戎"], 0.38, 0.65),
    ("黄潜善", "新党", ["阿附", "聚敛"], 0.32, 0.60),
    ("范宗尹", "中立派", ["敏悟", "通达"], 0.70, 0.75),
    ("杜充", "新党", ["苛虐", "残暴"], 0.20, 0.50),
    ("张浚", "中立派", ["志大", "规画"], 0.75, 0.82),
    ("胡铨", "旧党", ["万言", "鲠骨"], 0.94, 0.78),
    ("赵鼎", "中立派", ["持正", "经制"], 0.85, 0.85),
    ("尹焞", "旧党", ["清心", "守道"], 0.88, 0.68),
    ("谢克家", "中立派", ["通博", "吏干"], 0.72, 0.76),
    ("折彦质", "军功集团", ["将门", "果毅"], 0.78, 0.80),
    ("张守", "旧党", ["正色", "端凝"], 0.82, 0.78),
    ("吕好问", "旧党", ["忠良", "避谤"], 0.80, 0.75),
]


def _get_prefect_title_and_rank(level: str) -> Tuple[str, str]:
    """按州县级别推导正职长官差遣官名与官品。"""
    lvl = (level or "").strip()
    if lvl == "府":
        return "知府", "从三品"
    if lvl == "州":
        return "知州", "正四品"
    if lvl == "军":
        return "知军", "从五品"
    if lvl == "监":
        return "知监", "正六品"
    return "知州", "正四品"


def check_countersign(prefecture_data: Dict[str, Any]) -> Dict[str, Any]:
    """北宋知通公事连署核验（知通互掣）。
    
    规则：
    - 若通判缺员，长官独断，无监督，效率 0.7，隐患滋生；
    - 若知府贪劣（integrity < 0.45 或含聚敛/阿附特质）且通判风宪刚正（integrity >= 0.65），
      党见不同触发“通判拒签加赋文移”，公文阻滞，效率骤降至 0.3；
    - 否则正常连署施行，效率 1.0。
    """
    pref = prefecture_data.get("prefect") or {}
    vice = prefecture_data.get("subprefect") or {}

    if not vice or not vice.get("name"):
        prefecture_data["countersigned"] = True
        prefecture_data["efficiency"] = 0.70
        prefecture_data["friction_reason"] = "通判缺员，长官独断监察缺位"
        return prefecture_data

    if not pref or not pref.get("name"):
        prefecture_data["countersigned"] = False
        prefecture_data["efficiency"] = 0.40
        prefecture_data["friction_reason"] = "主官缺员，公事由通判署理"
        return prefecture_data

    p_integ = float(pref.get("integrity", 0.5))
    v_integ = float(vice.get("integrity", 0.5))
    p_traits = list(pref.get("traits", []))
    v_traits = list(vice.get("traits", []))
    p_fac = str(pref.get("faction", ""))
    v_fac = str(vice.get("faction", ""))

    is_corrupt_prefect = p_integ < 0.45 or any(t in p_traits for t in ("聚敛", "阿附", "搜括"))
    is_upright_vice = v_integ >= 0.65 or any(t in v_traits for t in ("刚直", "清正", "严正", "直谏"))

    if is_corrupt_prefect and is_upright_vice and p_fac != v_fac:
        prefecture_data["countersigned"] = False
        prefecture_data["efficiency"] = 0.30
        prefecture_data["friction_reason"] = "通判拒签加赋文移，公文阻滞互掣"
    else:
        prefecture_data["countersigned"] = True
        prefecture_data["efficiency"] = 1.0
        prefecture_data["friction_reason"] = "知通同舟并书施行"

    return prefecture_data


def init_all_prefect_officials(state, *, include_stats: bool = True,
                               store: bool = True,
                               reserved_names: Optional[set] = None,
                               reserved_ids: Optional[set] = None) -> Dict[str, Dict[str, Any]]:
    """初始化全国 136 州府席位知通人事底册。

    `include_stats=False`：纯读数兜底，不调用 `get_or_create_official_stats`（不写
    state.official_stats）；`store=False`：只返回派生结果，不写 state.prefect_officials。
    `game_init` 新局用默认参数做**显式初始化**；`get_prefect_officials` 的未初始化
    兜底使用 `store=False/include_stats=False`，保证读函数不再惰性写 state。
    """
    raw_dict = getattr(state, "prefect_officials", None)
    if not isinstance(raw_dict, dict):
        raw_dict = {}
        if store:
            state.prefect_officials = raw_dict

    # 跨册共享的 reserved 集合：已有条目 + 上游册已用姓名/person_id 都纳入。
    used_names = reserved_names if isinstance(reserved_names, set) else set(reserved_names or ())
    used_ids = reserved_ids if isinstance(reserved_ids, set) else set(reserved_ids or ())
    for _entry in raw_dict.values():
        if not isinstance(_entry, dict):
            continue
        for _slot in ("prefect", "subprefect"):
            _holder = _entry.get(_slot) or {}
            if isinstance(_holder, dict):
                if _holder.get("name"):
                    used_names.add(str(_holder["name"]))
                if _holder.get("person_id"):
                    used_ids.add(str(_holder["person_id"]))
    allocator = OfficialNameAllocator(used_names, used_ids)

    seats = all_seats()
    for idx, s in enumerate(seats):
        sid = s.get("seat_id") or f"{s.get('circuit')}|{s.get('seat')}"
        if sid in raw_dict:
            continue

        seat_name = s.get("seat", "州治")
        circuit = s.get("circuit", "各路")
        level = s.get("level", "州")
        p_title, p_rank = _get_prefect_title_and_rank(level)

        # 确定性指派
        p_idx = (idx * 7 + 3) % len(_PREFECT_NAMES)
        v_idx = (idx * 11 + 5) % len(_SUBPREFECT_NAMES)
        g_idx = (idx * 3 + 1) % len(_CENTRAL_GUARANTORS)

        p_name, p_fac, p_traits, p_integ, p_abil = _PREFECT_NAMES[p_idx]
        v_name, v_fac, v_traits, v_integ, v_abil = _SUBPREFECT_NAMES[v_idx]
        guarantor = _CENTRAL_GUARANTORS[g_idx]
        # P1-6：每个任命唯一 person_id；同名池重复时确定性生成新姓名，历史/池名优先保留。
        p_name, p_pid, p_hist = allocator.make(p_name, prefix="pf", historical=True)
        v_name, v_pid, v_hist = allocator.make(v_name, prefix="pf", historical=True)

        p_stat = v_stat = None
        if include_stats:
            from content.ministers.stats import get_or_create_official_stats, format_official_stats
            p_stat = get_or_create_official_stats(state, p_name, fallback_rank=p_rank)
            v_stat = get_or_create_official_stats(state, v_name, fallback_rank="从六品")

        entry: Dict[str, Any] = {
            "seat_id": sid,
            "seat": seat_name,
            "circuit": circuit,
            "level": level,
            "prefect": {
                "name": p_name,
                "person_id": p_pid,
                "historical": p_hist,
                "role": p_title,
                "rank": p_rank,
                "faction": p_fac,
                "integrity": p_integ,
                "ability": p_abil,
                "traits": p_traits,
                "attrs": (p_stat["attrs"] if p_stat else {}),
                "stats_summary": (format_official_stats(p_stat) if p_stat else ""),
                "tenure_months": 12 + (idx % 24),
                "guarantor": guarantor,
                "costume_tier": "fei",
            },
            "subprefect": {
                "name": v_name,
                "person_id": v_pid,
                "historical": v_hist,
                "role": "通判",
                "rank": "从六品",
                "faction": v_fac,
                "integrity": v_integ,
                "ability": v_abil,
                "traits": v_traits,
                "attrs": (v_stat["attrs"] if v_stat else {}),
                "stats_summary": (format_official_stats(v_stat) if v_stat else ""),
                "tenure_months": 6 + (idx % 30),
                "guarantor": guarantor,
                "costume_tier": "lv",
            },
            "countersigned": True,
            "efficiency": 1.0,
            "friction_reason": "知通并书施行",
        }
        check_countersign(entry)
        raw_dict[sid] = entry

    return raw_dict


def get_prefect_officials(state, seat_id: Optional[str] = None) -> Any:
    """查询指定或全量 136 州府席位（**纯只读**；未初始化时返回派生副本）。

    P1-5：旧实现会在此惰性 `init_all_prefect_officials(state)`，把 136 席写进
    state。现改为在临时命名空间构建、绝不回写；显式初始化由
    `application/game_init.init_official_books` 负责。
    """
    raw = getattr(state, "prefect_officials", None)
    if not isinstance(raw, dict) or len(raw) < 136:
        from types import SimpleNamespace
        raw = init_all_prefect_officials(
            SimpleNamespace(prefect_officials={}),
            include_stats=False, store=False)
    if seat_id:
        return raw.get(seat_id)
    return raw


def appoint_prefect_official(state, seat_id: str, role: str,
                             official_info: Dict[str, Any],
                             executor: Any = None) -> Dict[str, Any]:
    """任命或调换州府知通（显式写路径：先保证官员册存在于 state）。

    `executor` 不传 = 旧行为；传了则必须掌「官吏铨选」，否则返回 `ok=False` 且不改 state。
    """
    from core.permission_model import personnel_authority
    ok, reason, _mode = personnel_authority(state, executor)
    if not ok:
        return {"ok": False, "msg": f"事权不合法：{reason}", "reason": reason}
    raw = getattr(state, "prefect_officials", None)
    if not isinstance(raw, dict) or len(raw) < 136:
        init_all_prefect_officials(state)
        raw = state.prefect_officials
    po = raw.get(seat_id)
    if not po:
        return {"ok": False, "msg": f"未找到该州府席位：{seat_id}"}

    is_prefect = role in ("prefect", "知府", "知州", "知军", "知监")
    slot_key = "prefect" if is_prefect else "subprefect"

    old_holder = po.get(slot_key, {})
    new_holder = dict(official_info)
    _pref_name = str(new_holder.get("name") or "").strip()
    if not new_holder.get("person_id"):
        _name, _pid, _hist = ensure_person_identity(
            state, _pref_name, prefix="pf", historical=bool(new_holder.get("historical", False)))
        new_holder["name"] = _name
        new_holder["person_id"] = _pid
        new_holder["historical"] = _hist
    new_holder.setdefault("historical", bool(new_holder.get("historical", False)))
    new_holder["tenure_months"] = 0
    if is_prefect:
        p_title, p_rank = _get_prefect_title_and_rank(po.get("level", "州"))
        new_holder.setdefault("role", p_title)
        new_holder.setdefault("rank", p_rank)
        new_holder.setdefault("costume_tier", "fei")
    else:
        new_holder.setdefault("role", "通判")
        new_holder.setdefault("rank", "从六品")
        new_holder.setdefault("costume_tier", "lv")

    po[slot_key] = new_holder
    check_countersign(po)

    # 职位变动自动刷新公服基础部件，但皇帝恩赏特赐部件无感持续保留
    try:
        from content.ministers.costumes import refresh_minister_equipment_on_reassignment
        refresh_minister_equipment_on_reassignment(state, new_holder.get("name", ""), new_holder.get("rank", ""))
        from content.ministers.stats import get_or_create_official_stats, format_official_stats
        stat_prof = get_or_create_official_stats(state, new_holder.get("name", ""), fallback_rank=new_holder.get("rank", ""))
        new_holder.setdefault("attrs", stat_prof["attrs"])
        new_holder.setdefault("stats_summary", format_official_stats(stat_prof))
    except Exception:
        pass

    try:
        state.short_term_log.append({
            "turn": getattr(state, "turn", 0),
            "kind": "personnel",
            "title": f"除授{po.get('seat')}{new_holder.get('role')}",
            "note": f"起用{new_holder.get('name')}，更易原任{old_holder.get('name', '原缺')}",
            "year": getattr(state, "year", 1101),
            "month": getattr(state, "month", 1),
        })
    except Exception:
        pass

    return {
        "ok": True,
        "seat_id": seat_id,
        "seat": po.get("seat"),
        "role": new_holder.get("role"),
        "name": new_holder.get("name"),
        "countersigned": po.get("countersigned"),
        "efficiency": po.get("efficiency"),
    }


def dismiss_prefect_official(state, seat_id: str, role: str,
                             executor: Any = None) -> Dict[str, Any]:
    """罢免该州府知通，置为空缺待补（显式写路径）。

    `executor` 不传 = 旧行为；传了则必须掌「官吏铨选」，否则返回 `ok=False` 且不改 state。
    """
    from core.permission_model import personnel_authority
    ok, reason, _mode = personnel_authority(state, executor)
    if not ok:
        return {"ok": False, "msg": f"事权不合法：{reason}", "reason": reason}
    raw = getattr(state, "prefect_officials", None)
    if not isinstance(raw, dict) or len(raw) < 136:
        init_all_prefect_officials(state)
        raw = state.prefect_officials
    po = raw.get(seat_id)
    if not po:
        return {"ok": False, "msg": f"未找到该州府席位：{seat_id}"}

    is_prefect = role in ("prefect", "知府", "知州", "知军", "知监")
    slot_key = "prefect" if is_prefect else "subprefect"
    old = po.get(slot_key, {})
    po[slot_key] = {}
    check_countersign(po)
    return {"ok": True, "seat_id": seat_id, "dismissed": old.get("name", "")}


def jinshi_to_county(state, jinshi_list: List[Dict[str, Any]],
                     slot: Optional[int] = None) -> Dict[str, Any]:
    """科举进士下沉知县蓄水池，并在 MemoryGraph 中建立履历与举主保任边。"""
    assigned = []
    slot_id = slot if slot is not None else getattr(state, "slot", 0)

    try:
        from memory.memory_graph import get_memory_graph
        mem = get_memory_graph(slot_id)
    except Exception:
        mem = None

    for i, j in enumerate(jinshi_list or []):
        name = j.get("name", f"新科进士_{i}")
        county = j.get("county", f"第{i+1}县")
        guarantor = j.get("guarantor") or _CENTRAL_GUARANTORS[i % len(_CENTRAL_GUARANTORS)]

        # 全量量化档案生成（杜绝后期白板，五维+资质+特质经历计数器全覆盖）
        rank_type = j.get("exam_rank_type", "一甲" if i < 3 else ("二甲" if i < 15 else "三甲"))
        ex_dict = getattr(state, "exam", {}) if hasattr(state, "exam") else {}
        curr = j.get("curriculum", ex_dict.get("curriculum", "经律兼治") if isinstance(ex_dict, dict) else "经律兼治")
        
        from content.ministers.stats import generate_jinshi_official, format_official_stats
        profile = generate_jinshi_official(
            name=name,
            exam_rank_type=rank_type,
            curriculum=curr,
            origin_circuit=county,
            examiner_faction=guarantor,
        )
        if hasattr(state, "official_stats") and isinstance(state.official_stats, dict):
            state.official_stats[name] = profile

        info = {
            "name": name,
            "role": "知县",
            "rank": "从八品",
            "county": county,
            "guarantor": guarantor,
            "costume_tier": "lv",
            "faction": profile["faction"],
            "attrs": profile["attrs"],
            "potential": profile["potential"],
            "traits": profile["traits"],
            "stats_summary": format_official_stats(profile),
        }
        assigned.append(info)

        if mem:
            try:
                mem.add_entity(
                    name,
                    "minister",
                    name,
                    attrs={
                        "origin": profile.get("origin", "科举进士"),
                        "first_post": f"{county}知县",
                        "rank": "从八品",
                        "costume_tier": "lv",
                        "year": getattr(state, "year", 1101),
                        "attrs": profile["attrs"],
                        "traits": profile["traits"],
                        "stats_summary": format_official_stats(profile),
                    },
                )
                mem.add_relation(name, county, "governs", weight=1.0,
                                 note="初仕知县", turn=getattr(state, "turn", 0))
                mem.add_relation(guarantor, name, "supports", weight=1.0,
                                 note="保任举主", turn=getattr(state, "turn", 0))
                mem.save(slot_id)
            except Exception as e:
                log.warning("jinshi_to_county MemoryGraph 写入跳过: %s", e)

    return {"ok": True, "count": len(assigned), "assigned": assigned}


def trigger_joint_liability(state, official_name: str, crime: str = "贪墨",
                            slot: Optional[int] = None) -> List[str]:
    """举主保任同罪连坐：当地方官严重舞弊贪腐时，循 MemoryGraph 追索举主并受罚。"""
    penalized = []
    slot_id = slot if slot is not None else getattr(state, "slot", 0)

    try:
        from memory.memory_graph import get_memory_graph
        mem = get_memory_graph(slot_id)
        if mem:
            # 查找以 official_name 为目标、rtype 为 supports 或 note 含举主的边
            for r in mem.relations:
                if isinstance(r, dict):
                    if r.get("dst") == official_name and r.get("rtype") == "supports":
                        guarantor = r.get("src")
                        if guarantor and guarantor not in penalized:
                            penalized.append(guarantor)
    except Exception as e:
        log.warning("trigger_joint_liability 读取 MemoryGraph 异常: %s", e)

    for g in penalized:
        # 扣除皇威或记录过咎
        if hasattr(state, "change_prestige"):
            state.change_prestige(-1)
        try:
            state.short_term_log.append({
                "turn": getattr(state, "turn", 0),
                "kind": "decree",
                "title": f"举主连坐：{g}",
                "note": f"所保之臣{official_name}因{crime}事发，举主同坐罚铜夺秩",
                "year": getattr(state, "year", 1101),
                "month": getattr(state, "month", 1),
            })
        except Exception:
            pass

    return penalized

# ============================================================================
# P1-6：稳定 person_id + 确定性姓名分配器（跨两册共享，避免同名/同 id 多岗）
# ============================================================================
_SURNAME_POOL = tuple("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹")
_GIVEN_POOL = tuple((
    "承之", "道德", "仁义", "礼智", "守信", "温良", "恭俭", "文行", "忠孝",
    "廉明", "清和", "平安", "安定", "康宁", "福寿", "昌隆", "盛茂", "荣华",
    "富贵", "显达", "彦伯", "仲叔", "季公", "卿良", "元辅", "景行", "修远",
    "思齐", "守正", "持中", "克勤", "惟俭", "允文", "允武", "德彰", "善庆",
))


class OfficialNameAllocator:
    """确定性别名/姓名分配器（P1-6）。

    - 每个任命分配唯一 `person_id`，同一册内绝不重复；传入跨册 `reserved_names/
      reserved_ids` 时，跨册也保持唯一。
    - 历史/池内姓名优先保留；若已被占用则用「姓氏池 × 名字池」确定性组合补足。
    - 生成结果只依赖分配顺序与输入，跨进程/重开可复现。
    """

    def __init__(self, reserved_names=None, reserved_ids=None):
        self.names = reserved_names if isinstance(reserved_names, set) else set(reserved_names or ())
        self.ids = reserved_ids if isinstance(reserved_ids, set) else set(reserved_ids or ())
        self._counter = 0
        self._reserved_preferred = set()

    def reserve(self, name):
        """预占一个历史姓名（不占用 person_id，供后续 make(preferred=...) 使用）。"""
        if name and name not in self.names:
            self._reserved_preferred.add(str(name))

    def _generate_name(self) -> str:
        n_s, n_g = len(_SURNAME_POOL), len(_GIVEN_POOL)
        for k in range(10000):
            i = self._counter + k
            surname = _SURNAME_POOL[i % n_s]
            given = _GIVEN_POOL[(i * 7 + i // n_s) % n_g]
            name = surname + given
            if name not in self.names:
                return name
        # 极端兜底：加序号，保证函数不会返回重复/空
        base = _SURNAME_POOL[self._counter % n_s] + "承之"
        j = 2
        while f"{base}{j}" in self.names:
            j += 1
        return f"{base}{j}"

    def make(self, preferred=None, *, prefix="p", historical=False):
        """返回 `(name, person_id, historical)`；preferred 被占用时生成替代姓名。"""
        preferred = str(preferred).strip() if preferred else ""
        name = None
        if preferred and (preferred not in self.names or preferred in self._reserved_preferred):
            name = preferred
            self._reserved_preferred.discard(preferred)
        if name is None:
            name = self._generate_name()
        self.names.add(name)
        while True:
            pid = f"{prefix}_{self._counter:04d}"
            self._counter += 1
            if pid not in self.ids:
                break
        self.ids.add(pid)
        return name, pid, bool(historical and name == preferred)

def collect_used_official_names_ids(state):
    """跨两册收集已用姓名/person_id（供显式任免分配唯一 person_id）。"""
    names, ids = set(), set()
    prefects = getattr(state, "prefect_officials", None) or {}
    if isinstance(prefects, dict):
        for entry in prefects.values():
            if not isinstance(entry, dict):
                continue
            for slot in ("prefect", "subprefect"):
                holder = entry.get(slot) or {}
                if not isinstance(holder, dict):
                    continue
                if holder.get("name"):
                    names.add(str(holder["name"]))
                if holder.get("person_id"):
                    ids.add(str(holder["person_id"]))
    circuits = getattr(state, "circuit_officials", None) or {}
    if isinstance(circuits, dict):
        for entry in circuits.values():
            if not isinstance(entry, dict):
                continue
            for holder in (entry.get("officials") or {}).values():
                if not isinstance(holder, dict):
                    continue
                if holder.get("name"):
                    names.add(str(holder["name"]))
                if holder.get("person_id"):
                    ids.add(str(holder["person_id"]))
    return names, ids


def ensure_person_identity(state, preferred_name, *, prefix: str,
                           historical: bool = False):
    """显式任免前的唯一身份分配：返回 `(name, person_id, historical)`。"""
    names, ids = collect_used_official_names_ids(state)
    alloc = OfficialNameAllocator(names, ids)
    return alloc.make(preferred_name, prefix=prefix, historical=historical)
