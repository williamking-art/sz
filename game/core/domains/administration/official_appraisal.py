# -*- coding: utf-8 -*-
"""北宋三级官制差遣、知通互掣与三年磨勘考课体系（单一权威源）。

## 规格与背景（M300 / Stage 3）

落实北宋严密的官僚运作逻辑与人事考评体系：

1. **三级官僚职官架构（中枢 → 监司 → 州府）**：
   - **中枢宰执**：中书门下（同平章事、参知政事）、枢密院（知枢密院事）、尚书六部与御史台；
   - **21路监司（四大监司）**：
     - **帅司**（安抚使司）：专统兵马防务；
     - **漕司**（转运使司）：掌管财赋度支、赋税转漕；
     - **宪司**（提刑使司）：主管司法风纪、勘察疑狱；
     - **仓司**（提举常平司）：负责常平仓、青苗息米、农田水利。
   - **州府知通（知通互掣）**：
     - **知州/知府**：一州之长，统摄政刑；
     - **通判**：天子耳目，“与知州通判州事”，凡兵民钱谷文书非通判连署不得施行，
       且具专折奏事之权，与知州形成相互监督牵制。
2. **三年磨勘考课机制（考课法）**：
   - 考评周期：三年一磨勘；
   - 考评维度（四善三最）：
     - 治绩：民田垦辟、常税督办、赋役平允；
     - 治平：流民安辑、民怨控制、盗贼不生；
     - 风纪：清慎公平、无赃赎罪愆。
   - 评定四档：
     - **上考**（优等）：迁转官资，政务效能增进，晋升中枢或要冲路府；
     - **中考**（常格）：秩满量移或平调留任；
     - **下考**（殿罚）：罚俸折秩，黜降偏远路分；
     - **除授宫观祠禄（冷冻退出机制）**：
       - 对政争失势、考课极劣或弹劾罢黜之官，除授“提举洞霄宫”、“管勾玉局观”等宫观祠禄官；
       - 转入 `sinecure` 子池，享有半俸，但解除监司与路府实权，实现士大夫政治的安全退出。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.domains.economy.macro_climate import ALL_CIRCUITS_21
from core.domains.administration import officialdom as _officialdom
from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add

__all__ = [
    "derive_circuit_intendants",
    "derive_prefecture_officials",
    "run_triennial_appraisal",
    "assign_sinecure_retirement",
    "CIRCUIT_INTENDANT_TYPES",
]

# 四大监司名目
CIRCUIT_INTENDANT_TYPES = ["帅司_安抚使", "漕司_转运使", "宪司_提刑使", "仓司_常平使"]


def _get_pref(state, circuit: str) -> Dict[str, Any]:
    prefs = getattr(state, "prefectures", None)
    if isinstance(prefs, dict):
        p = prefs.get(circuit)
        if isinstance(p, dict):
            return p
    return {}


def derive_circuit_intendants(state, circuit: str) -> Dict[str, Any]:
    """派生单一路的四大监司编制、长官人事与运转效能（只读纯函数）。"""
    p = _get_pref(state, circuit)
    if not p:
        return {"circuit": circuit, "defined": False}

    guan = (p.get("pops") or {}).get("官僚") or {}
    on_post = int(guan.get("on_post", 0) or 0)

    # 各路监司完备度（在岗官额越足，监司运转越充分）
    readiness = min(1.0, max(0.4, on_post / 80.0)) if on_post > 0 else 0.5

    from core.domains.administration.circuit_officials import get_circuit_officials
    c_info = get_circuit_officials(state, circuit)
    offs = c_info.get("officials", {})

    intendants = {
        "帅司": {
            "title": offs.get("shuai", {}).get("official_title", "安抚使"),
            "name": offs.get("shuai", {}).get("name", "未定"),
            "faction": offs.get("shuai", {}).get("faction", "中立派"),
            "rank": offs.get("shuai", {}).get("rank", "正三品"),
            "readiness": readiness,
            "effectiveness": offs.get("shuai", {}).get("effectiveness", readiness),
            "focus": "沿边防务与禁厢军操演",
        },
        "漕司": {
            "title": offs.get("cao", {}).get("official_title", "转运使"),
            "name": offs.get("cao", {}).get("name", "未定"),
            "faction": offs.get("cao", {}).get("faction", "中立派"),
            "rank": offs.get("cao", {}).get("rank", "从三品"),
            "readiness": readiness,
            "effectiveness": offs.get("cao", {}).get("effectiveness", readiness),
            "focus": "两税经总钱征纳与漕运上供",
        },
        "宪司": {
            "title": offs.get("xian", {}).get("official_title", "提刑使"),
            "name": offs.get("xian", {}).get("name", "未定"),
            "faction": offs.get("xian", {}).get("faction", "旧党"),
            "rank": offs.get("xian", {}).get("rank", "从四品"),
            "readiness": readiness,
            "effectiveness": offs.get("xian", {}).get("effectiveness", readiness),
            "focus": "按察司疑狱与刑名风宪",
        },
        "仓司": {
            "title": offs.get("cang", {}).get("official_title", "提举常平使"),
            "name": offs.get("cang", {}).get("name", "未定"),
            "faction": offs.get("cang", {}).get("faction", "新党"),
            "rank": offs.get("cang", {}).get("rank", "正五品"),
            "readiness": readiness,
            "effectiveness": offs.get("cang", {}).get("effectiveness", readiness),
            "focus": "常平积谷与青苗水利",
        },
    }

    return {
        "circuit": circuit,
        "defined": True,
        "on_post_officials": on_post,
        "readiness": float(round(readiness, 2)),
        "intendants": intendants,
    }


def derive_prefecture_officials(state, circuit: str) -> Dict[str, Any]:
    """派生单一路下州府知通互掣配置、在任长官与监督状态（只读纯函数）。

    通判与知州职权互掣：通判有同签与监察专折之权。
    若通判缺员，则知州独揽大权，吏治腐败与贪墨风险上升；
    知通齐备，则相互防闲，狱讼平允。
    """
    p = _get_pref(state, circuit)
    if not p:
        return {"circuit": circuit, "defined": False}

    guan = (p.get("pops") or {}).get("官僚") or {}
    on_post = int(guan.get("on_post", 0) or 0)

    # 是否配齐通判
    has_vice_prefect = on_post >= 20
    check_and_balance = 1.0 if has_vice_prefect else 0.65

    from core.domains.administration.circuit_officials import get_circuit_officials
    c_info = get_circuit_officials(state, circuit)
    offs = c_info.get("officials", {})

    pref_official = offs.get("prefect", {})
    vice_official = offs.get("vice_prefect", {})

    return {
        "circuit": circuit,
        "defined": True,
        "has_vice_prefect": has_vice_prefect,
        "check_and_balance_ratio": check_and_balance,
        "prefect": pref_official,
        "vice_prefect": vice_official,
        "mechanism": "通判非连署不发，专折纠劾无所避忌" if has_vice_prefect else "通判缺员，长官独断监察缺位",
    }


def run_triennial_appraisal(state, log: Optional[List[str]] = None) -> Dict[str, Any]:
    """三年一任磨勘考课（受控写操作）。

    评估 21 路长官政绩：
    1. 督税农桑（上考）：增加全国政务效能；
    2. 贪酷亏空（下考）：削夺阶官，罚俸罚铜；
    3. 治平不力或派系倾轧失败者：除授宫观祠禄（安全冷冻）。
    """
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats

    unrest_pool = stats.get("organic_unrest_pool", {})

    promoted_circuits = []
    demoted_circuits = []
    sinecure_count = 0

    for c in ALL_CIRCUITS_21:
        p = _get_pref(state, c)
        if not p:
            continue
        guan = (p.get("pops") or {}).get("官僚")
        if not isinstance(guan, dict):
            continue

        c_unrest = float(unrest_pool.get(c, 0.0) or 0.0)
        on_post = int(guan.get("on_post", 0) or 0)

        # 考课定等
        if c_unrest < 20.0 and on_post > 0:
            # 上考（政平民和）
            promoted_circuits.append(c)
        elif c_unrest > 60.0:
            # 下考（民变流民滋生，考课劣等）
            demoted_circuits.append(c)
            # 劣等官吏挤入祠禄闲职
            weed_out = max(1, int(on_post * 0.08))
            _officialdom.weed_out_officials(p, weed_out)
            sinecure_count += weed_out

    # 全局行政效能调整
    current_eff = float(stats.get("administrative_efficiency", 1.0) or 1.0)
    if len(promoted_circuits) >= 12:
        new_eff = min(1.35, current_eff + 0.04)
        if isinstance(log, list):
            log.append(f"🏅【磨勘考课·大考定绩】三年官吏考课蒇事：{len(promoted_circuits)} 路考定上考擢升，天下政务通畅！")
    elif len(demoted_circuits) >= 6:
        new_eff = max(0.70, current_eff - 0.05)
        if isinstance(log, list):
            log.append(f"⚠️【磨勘考课·重勘黜降】三年考课：{len(demoted_circuits)} 路考列下考殿罚，地方监司知通多有殿罚降资！")
    else:
        new_eff = current_eff
        if isinstance(log, list):
            log.append(f"📋【磨勘考课·平允转官】三年磨勘考第告成，各路监司知州按常格磨勘迁转，{sinecure_count} 人除授宫观祠禄。")

    stats["administrative_efficiency"] = float(round(new_eff, 3))
    stats["last_appraisal_turn"] = int(getattr(state, "turn", 0) or 0)

    return {
        "promoted_circuits": promoted_circuits,
        "demoted_circuits": demoted_circuits,
        "sinecure_assigned": sinecure_count,
        "administrative_efficiency": new_eff,
    }


def assign_sinecure_retirement(
    state,
    circuit: str,
    count: int,
    reason: str = "政争冷冻/年老乞休",
    log: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """特旨除授宫观祠禄（安全退出机制）。

    将指定官员解除差遣实权，除授崇福宫、景灵宫、玉局观等祠禄闲职。
    从在岗池（`on_post`）转入祠禄池（`sinecure`），享受折半月俸，不占监司要缺。
    """
    p = _get_pref(state, circuit)
    if not p:
        return {"circuit": circuit, "assigned": 0}

    guan = (p.get("pops") or {}).get("官僚")
    if not isinstance(guan, dict):
        return {"circuit": circuit, "assigned": 0}

    _officialdom.ensure_subpools(p)
    on_post = int(guan.get("on_post", 0) or 0)
    actual = min(count, on_post)
    if actual <= 0:
        return {"circuit": circuit, "assigned": 0}

    # 在岗 -> 祠禄
    if _pop_obj_add(state, guan, "on_post", -actual) is None:
        guan["on_post"] = int(guan.get("on_post", 0)) - actual
    if _pop_obj_add(state, guan, "sinecure", actual) is None:
        guan["sinecure"] = int(guan.get("sinecure", 0)) + actual

    if isinstance(log, list):
        log.append(f"🕊️【除授祠禄】朝议决断：{circuit} {actual} 名重臣奉敕判除提举宫观祠禄闲职（{reason}），退居二线。")

    return {
        "circuit": circuit,
        "assigned": actual,
        "on_post_remaining": int(guan.get("on_post", 0)),
        "sinecure_current": int(guan.get("sinecure", 0)),
    }
