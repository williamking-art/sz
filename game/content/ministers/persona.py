# -*- coding: utf-8 -*-
"""宋祚 · 大臣 persona 模块（Phase 3b，言枢密方案已审；量纲按用户决定改 **0-100 满值**，
中性 50，覆盖此前 1-10 折中）。

- **PERSONA 表**：6 维人格（刚直/权谋/聚敛/忠君/胆识/冒险，**0-100**，中性 50）+
  interests + baseline_stance + style + speech；缺省从 MINISTERS.traits 关键词派生
  （兼容既有 35+ 条，不动原数据结构；派生基线全 50）。
- **立场演化**（程序化）：stance_score = 50 基线 + 派系满意度×0.25 + 影响力×0.15 +
  事件×0.25 + 皇威×0.15 + 民心×0.10 + 国运×0.10（权重 sum=1.0）；
  性格**乘法调制**：mod = (1−0.5×刚直/100)×(1+0.5×(权谋−50)/100)×
  (1+0.4×(胆识−50)/100)×(1+0.3×(冒险−50)/100)，
  Δstance = Σdrives×mod clamp[−20,+20]（Σdrives = 驱动对中性的偏离）；
  忠君：皇威驱动 ×(1+1.0×忠君/100)、背弃 ×(1−0.8×忠君/100)；
  聚敛：财政利益向量 ±0.01×聚敛×方向（_POLICY_INTEREST）。
- **危险度**（乘法式）：(影响力/100)×((100−满意度)/100)×(1−0.7×皇威/100)×
  (0.5+1.5×权谋/100)，范围 [0,2.0]（权谋系数 0.5~2.0）；触发 P=clamp(危险度×0.5,0,0.6)。
- **阳奉阴违概率式**：危险度 P 每月随机触发；刚直≥70 且 score<45 → 直言力诤。
- **召对注入** `_build_persona_prompt`：**loyalty 数值绝不注入**（只给档位词姿态）。
"""
import random

from content.ministers.data import MINISTERS

# ---- 6 维人格（0-100，中性 50） ----
_PERSONA_DIMENSIONS = ("刚直", "权谋", "聚敛", "忠君", "胆识", "冒险")

# 立场演化权重（蔡权衡复核定稿，sum=1.0）
_WEIGHTS = {
    "派系_满意度": 0.25, "派系_影响力": 0.15, "事件": 0.25,
    "皇威": 0.15, "民心": 0.10, "国运": 0.10,
}
# 事件调制（每类对 stance 的偏移，0~1 事件强度）
_EVENT_MOD = {"变法": 6.0, "党争": -4.0, "贬黜": -8.0, "晋升": 5.0, "承诺": 3.0}
# 聚敛事件驱动内财政类政策利益向量（查图谱 note 命中 → 偏移 ±0.01×聚敛×方向）
_POLICY_INTEREST = {"加税": -1, "裁费": -1, "查贪": -1, "市舶": 1, "盐利": 1, "工程": 1}

# 缺省派生关键词 → 6 维基数（基线全 50 中性；关键词差值 ×10 映射 0-100）
_TRAIT_KEYWORDS = {
    "老成": {"刚直": 30, "忠君": 60}, "调停": {"刚直": 20, "权谋": 40},
    "守正": {"刚直": 70, "忠君": 70}, "权谋": {"权谋": 80}, "善变": {"权谋": 70, "冒险": 50},
    "理财": {"聚敛": 60, "胆识": 50}, "贪": {"聚敛": 90}, "聚敛": {"聚敛": 90},
    "忠": {"忠君": 80}, "直": {"刚直": 70}, "诤": {"刚直": 80},
    "勇": {"胆识": 70}, "悍": {"胆识": 70, "冒险": 60}, "险": {"冒险": 70},
    "变": {"冒险": 60, "权谋": 50}, "锐": {"胆识": 60, "冒险": 60},
}

# 显式 PERSONA 表（0-100，核心大臣精写；其余缺省派生）
PERSONA = {
    "蔡京": {"刚直": 15, "权谋": 85, "聚敛": 80, "忠君": 60, "胆识": 60, "冒险": 70,
             "interests": ["理财", "变法", "权位"], "baseline_stance": "变法",
             "style": "权谋深沉，善揣圣意", "speech": "陛下圣明，臣敢不效命！"},
    "韩忠彦": {"刚直": 70, "权谋": 40, "聚敛": 30, "忠君": 80, "胆识": 50, "冒险": 30,
               "interests": ["调停", "旧法", "名节"], "baseline_stance": "守旧",
               "style": "老成持重，调和鼎鼐", "speech": "愿陛下持重，徐图善政。"},
    "曾布": {"刚直": 40, "权谋": 70, "聚敛": 50, "忠君": 60, "胆识": 60, "冒险": 60,
             "interests": ["理财", "新政", "党争"], "baseline_stance": "变法",
             "style": "善变多谋，左右逢源", "speech": "新政之利，臣尝亲见。"},
    "章惇": {"刚直": 80, "权谋": 70, "聚敛": 40, "忠君": 60, "胆识": 80, "冒险": 70,
             "interests": ["变法", "党争", "边功"], "baseline_stance": "变法",
             "style": "刚愎自用，睚眦必报", "speech": "陛下若用臣，当以十年为期！"},
    "陈瓘": {"刚直": 90, "权谋": 20, "聚敛": 10, "忠君": 90, "胆识": 80, "冒险": 50,
             "interests": ["名节", "谏诤", "正论"], "baseline_stance": "守旧",
             "style": "骨鲠敢言，不避斧钺", "speech": "臣虽万死，不敢不言！"},
    "童贯": {"刚直": 20, "权谋": 75, "聚敛": 70, "忠君": 85, "胆识": 70, "冒险": 70,
             "interests": ["边功", "权位", "财货"], "baseline_stance": "好战",
             "style": "深宫近幸，手握兵权", "speech": "臣愿为陛下开疆拓土！"},
    "种师道": {"刚直": 70, "权谋": 30, "聚敛": 20, "忠君": 90, "胆识": 80, "冒险": 40,
               "interests": ["边务", "名节", "社稷"], "baseline_stance": "守边",
               "style": "老成宿将，稳如泰山", "speech": "守边之要，在稳不在躁。"},
    "司马光": {"刚直": 90, "权谋": 20, "聚敛": 20, "忠君": 70, "胆识": 80, "冒险": 30,
               "interests": ["名节", "旧法", "正论"], "baseline_stance": "守旧",
               "style": "端方持正，守祖宗法", "speech": "祖宗之法不可变也。"},
    "王安石": {"刚直": 75, "权谋": 40, "聚敛": 40, "忠君": 60, "胆识": 70, "冒险": 60,
               "interests": ["理财", "变法", "兴学"], "baseline_stance": "变法",
               "style": "拗相公，百折不回", "speech": "天变不足畏，祖宗不足法，人言不足恤。"},
}


def _derive_personality(name: str) -> dict:
    """缺省派生：从 MINISTERS.traits/trait_ids 关键词匹配 6 维基数（基线全 50 中性）。"""
    fig = MINISTERS.get(name, {})
    dims = {"刚直": 50, "权谋": 50, "聚敛": 50, "忠君": 50, "胆识": 50, "冒险": 50}
    keys = []
    for t in (fig.get("trait_ids") or []):
        keys.append(str(t))
    for t in str(fig.get("traits", "")).replace("/", " ").split():
        keys.append(t)
    for k in keys:
        for kw, mod in _TRAIT_KEYWORDS.items():
            if kw in k:
                for d, v in mod.items():
                    dims[d] = max(0, min(100, dims[d] + (v - 50)))
    return dims


def get_persona(name: str) -> dict:
    """取大臣 persona（显式表优先，否则派生；全部补全 6 维）。"""
    p = dict(PERSONA.get(name, {}))
    if not p:
        p = _derive_personality(name)
    else:
        # 显式表缺维补缺省
        dims = _derive_personality(name)
        for d in _PERSONA_DIMENSIONS:
            if d not in p:
                p[d] = dims[d]
    p.setdefault("interests", ["朝政"])
    p.setdefault("baseline_stance", "守成")
    p.setdefault("style", "循例奉公")
    p.setdefault("speech", "臣谨奉诏。")
    return p


# ---------------- 立场演化（程序化，蔡权衡复核定稿） ----------------
def stance_evolution(state, name: str, turn: int = 0) -> dict:
    """stance = 50 基线 + 派系满意度×0.25 + 影响力×0.15 + 事件×0.25 + 皇威×0.15
    + 民心×0.10 + 国运×0.10（权重 sum=1.0）；性格**乘法调制** + 聚敛财政利益向量
    + 忠君皇威放大/背弃。返回 {"score", "stance", "posture", "factors"}；
    演化史写图谱 stance（带时间戳），不注入 loyalty 数值。
    """
    # 只对在朝大臣生效（史实修复：司马光/王安石 1086 年已卒，不在 MINISTERS 在朝——
    # persona 保留为史实参考，但**不参与运行时演化/产业调制**）
    try:
        if state.minister_status(name) != "active":
            return {"score": 50, "stance": "观望", "factors": [],
                    "posture": "恭顺奉行"}
    except Exception:
        pass
    p = get_persona(name)
    fig = MINISTERS.get(name, {})
    faction = fig.get("faction", "中枢")
    score = 50.0  # baseline 中性
    factors = []
    prestige = getattr(state, "prestige", 50)

    # 派系（满意度/影响力，0-100 → 权重偏移）
    sat = state.factions.get(faction, {}).get("satisfaction", 50)
    inf = state.factions.get(faction, {}).get("influence", 50)
    score += (sat - 50) * _WEIGHTS["派系_满意度"]
    score += (inf - 50) * _WEIGHTS["派系_影响力"]
    factors.append(f"派系{sat}")

    # 事件（查记忆图谱 stance/变法/党争/贬黜/晋升/承诺）
    event_delta = 0.0
    try:
        rows = state.memory.query(name, rtypes=("stance", "supports", "opposes", "promises"),
                                  time_window=60, top_k=12)
        for r in rows:
            note = r[4] or ""
            for ev, mod in _EVENT_MOD.items():
                if ev in note:
                    event_delta += mod * 0.15
                    break
    except Exception:
        pass
    score += event_delta * _WEIGHTS["事件"]
    if event_delta:
        factors.append("事" + ("+" if event_delta > 0 else "") + str(int(event_delta)))

    # 盘面：皇威/民心/国运（各权重，sum 0.15+0.10+0.10）
    disk = 0.0
    disk += (prestige - 50) * _WEIGHTS["皇威"]
    disk += (getattr(state, "population_satisfaction", 50) - 50) * _WEIGHTS["民心"]
    disk += (getattr(state, "national_mood", 50) - 50) * _WEIGHTS["国运"] \
        if hasattr(state, "national_mood") else 0.0
    score += disk
    if abs(disk) > 0.5:
        factors.append("盘" + ("+" if disk > 0 else "") + str(int(disk)))

    # 性格调制（乘法式，0-100 量纲，用户决定）：mod 乘驱动总和，Δstance clamp ±20
    drives = score - 50   # Σdrives：驱动（派系/事件/盘面）对中性的偏离
    mod = ((1 - 0.5 * p["刚直"] / 100.0) * (1 + 0.5 * (p["权谋"] - 50) / 100.0) *
           (1 + 0.4 * (p["胆识"] - 50) / 100.0) * (1 + 0.3 * (p["冒险"] - 50) / 100.0))
    delta = max(-20.0, min(20.0, drives * mod))
    score = 50 + delta

    # 聚敛：事件驱动内财政类政策利益向量（查图谱 note：加税/裁费/查贪=−1、市舶/盐利/工程=+1）
    policy_delta = 0.0
    try:
        rows = state.memory.query(name, rtypes=("stance", "supports", "opposes", "produces"),
                                  time_window=60, top_k=12)
        for r in rows:
            note = r[4] or ""
            for pol, direction in _POLICY_INTEREST.items():
                if pol in note:
                    policy_delta += direction * 0.01 * p["聚敛"]
                    break
    except Exception:
        pass
    score += policy_delta
    if policy_delta:
        factors.append("利" + ("+" if policy_delta > 0 else "") + str(int(policy_delta)))

    # 忠君：皇威驱动 ×(1+1.0×忠君/100)、背弃 ×(1−0.8×忠君/100)
    if prestige >= 60:
        score *= (1 + 1.0 * p["忠君"] / 100.0)
    elif prestige < 40:
        score *= (1 - 0.8 * p["忠君"] / 100.0)

    # 新旧产业立场（用户指示）：守旧大臣抵制新产业（「奇技淫巧」）、开明大臣力推
    # （「富国强兵之基」）——立场演化随产业结构调制（认知层占比，非精确值）
    try:
        from core.era_mechanic import calc_industry_scale
        _sc = calc_industry_scale(state)
        if _sc["new_scale"] > 0:
            _share = _sc["share"]
            if p["baseline_stance"] in ("守旧", "守边", "守成"):
                score -= _share * 10
                if p["刚直"] >= 70:
                    score -= _share * 5     # 守旧刚直 → 更强抵制（奇技淫巧）
            elif p["baseline_stance"] in ("变法", "理财", "好战"):
                score += _share * 10
    except Exception:
        pass

    score = max(0, min(100, int(score)))
    stance = ("激进" if score >= 70 else "支持" if score >= 55 else
              "观望" if score >= 45 else "抵触" if score >= 30 else "敌对")
    # 立场演化史写入图谱（带时间戳，供召对/拟旨相关历史引用）
    try:
        state.memory.add_entity(f"minister_{name}", "minister", name, turn=turn)
        state.memory.upsert_relation(f"minister_{name}", "朝政", "stance",
                                     weight=1.0 + score / 100.0, turn=turn,
                                     note=f"{stance}·{'/'.join(factors)}")
    except Exception:
        pass
    return {"score": score, "stance": stance, "factors": factors,
            "posture": _posture(state, name, p, score)}


def _posture(state, name: str, p: dict, score: int) -> str:
    """阳奉阴违（概率式）：危险度 P=clamp(危险度×0.5,0,0.6) 每月随机触发；
    刚直≥70 且 score<45 → 直言力诤（保留）。"""
    if p["刚直"] >= 70 and score < 45:
        return "直言力诤"           # 刚直者满意度低也直谏
    danger = danger_rating(state, name)
    p_trigger = max(0.0, min(0.6, danger * 0.5))
    if random.random() < p_trigger:
        return "阳奉阴违"           # 明面恭顺暗里拆台
    if score < 35:
        return "消极敷衍"
    if score >= 70:
        return "推心置腹"
    return "恭顺奉行"


def danger_rating(state, name: str) -> float:
    """危险度（乘法式，0-100 量纲）：
    危险度 = (影响力/100)×((100−满意度)/100)×(1−0.7×皇威/100)×(0.5+1.5×权谋/100)，
    范围 [0,2.0]（权谋系数 0.5~2.0，冒险/聚敛不参与）。
    只对在朝大臣生效（已故/不在朝 → 0）。"""
    try:
        if state.minister_status(name) != "active":
            return 0.0
    except Exception:
        pass
    p = get_persona(name)
    fig = MINISTERS.get(name, {})
    faction = fig.get("faction", "中枢")
    sat = state.factions.get(faction, {}).get("satisfaction", 50)
    inf = state.factions.get(faction, {}).get("influence", 50)
    prestige = getattr(state, "prestige", 50)
    d = ((inf / 100.0) * ((100 - sat) / 100.0) * (1 - 0.7 * prestige / 100.0)
         * (0.5 + 1.5 * p["权谋"] / 100.0))
    # 大臣家产阈值（家产≥100万 → 危险度 +0.15，怕抄没）
    try:
        from core.estate_mechanic import estate_persona_mod
        d += estate_persona_mod(state, name)["danger_bonus"]
    except Exception:
        pass
    return max(0.0, min(2.0, round(d, 3)))


# ---------------- 召对注入 ----------------
def _build_persona_prompt(state, name: str, turn: int = 0) -> str:
    """召对 persona 注入文本（身份锚点/立场基线/盘面姿态/图谱相关历史/忠诚隐藏姿态词）。

    **loyalty 数值绝不注入**——只给档位词姿态（明面恭顺/直言力诤等）。
    只对在朝大臣生效：已故/不在朝 → 返回空（不注入召对，史实参考不参与运行时）。"""
    try:
        if state.minister_status(name) != "active":
            return ""
    except Exception:
        pass
    p = get_persona(name)
    fig = MINISTERS.get(name, {})
    ev = stance_evolution(state, name, turn)
    mem_hint = ""
    try:
        rows = state.memory.query(name, time_window=0, top_k=8)
        mem_hint = state.memory.summarize(rows, max_chars=100)
    except Exception:
        pass
    danger = danger_rating(state, name)
    parts = [
        f"【身份】{fig.get('role', '朝中大臣')}，性格：{p['style']}",
        f"【立场基线】{p['baseline_stance']}（当前 {ev['stance']}）",
        f"【盘面姿态】{ev['posture']}",
    ]
    if mem_hint:
        parts.append(f"【相关历史】{mem_hint}")
    if danger >= 0.7:
        parts.append("（陛下宜留意此人动向）")
    elif danger >= 0.5:
        parts.append("（此人不可全信）")
    return "\n".join(parts)


__all__ = ["PERSONA", "get_persona", "stance_evolution", "danger_rating",
           "_build_persona_prompt"]
