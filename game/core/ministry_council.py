# -*- coding: utf-8 -*-
"""B5-6 · 朝议：官员**各自独立**意见 → 合议 → 玩家/制度裁决

规格：`market-civilian-economy` §7 B5-6「朝议：相关官员独立意见 → 合议 →
玩家/制度裁决；**不得**把多官员压成一个"朝廷综合回答""。

## 一、逐人独立意见（人是主体，领域分析只是输入）

`collect_opinions()` 对**每一位具名官员**单独生成一条意见，依据**只有他自己的**：

| 依据 | 读数来源 | 缺失时 |
|---|---|---|
| **职权** `posts` / 所掌事权 | `state.central_orgs` 反查（权限跟官职、不跟人），复用 `core.institution` 同口径 | 无官职 → 该项 `0.0`（真零：不在此位） |
| **权限** `authority` | `core.minister_agent` 的 `authority` | `None` → 意见照发（权限不定 ≠ 没意见），但标 `basis_undefined` 并另判 `may_carry` |
| **记忆** | **只读他自己**的 `recall()`（甲的私话绝不进乙的意见） | 无记忆 → `0.0`（真零：无前科） |
| **立场** | `MINISTERS[人]` 的 `faction`/`loyalty`/`corruption`/`trait_ids` | 名册查无此人 → 该项 `None` |

同名官员在同一局势下**可以得出不同主张**（各自派系/立场/职权不同），
且**主张可追溯到该人**：每条意见都带 `actor_id`、`post`、`basis`、`basis_undefined`。

## 二、合议：**保留分歧，不合并成一个答案**

`council()` 产出的是：

```
tally = {"赞成": ["韩忠彦"], "反对": ["陈瓘"], ...}   # 每一档都列具名的人
```

**刻意不提供**"朝廷综合意见/最终主张/consensus_text"这类单一字段：
把七嘴八舌压成一句话，就是 B5-6 明令禁止的"朝廷综合回答"。
只另给**可判定的布尔**（`unanimous`/`has_dissent`）与**分歧名单**（`dissent_ids`）——
它们**不替代**任何人的原话。

## 三、沉默 ≠ 忠诚支持

`intents_of()` 返回 `[]` **不等于赞成**。本模块把在场者分成三桶，互不冒充：

| 桶 | 含义 | 计入支持？ |
|---|---|---|
| `speaking_ids` | 发了具名意见的人 | 依其 `stance` |
| `silent_ids` | 在场、却**一个立场都给不出**（立场读数缺失，如名册查无此人） | **绝不计入** |
| `abstain_ids`（`stance="弃权"`） | 明言弃权（在野不入对等） | **绝不计入** |

支持比例只由 `support_ids` 的**具名人数**算，且返回值里同时给出分母
（`support_denominator`，**不含**保留与弃权），让调用方自己看见
"到场的、发声的、没表态的、弃权的"各有几人。

## 四、裁决口径（玩家/制度）

`adjudicate()` 只做**记账**，不代玩家拍板：

- `decided_by="institution"`（制度）：门下省掌「诏令封驳」者若力谏 → **封驳**（合议不过）；
  否则按具名票数定 `通过/驳回`；
- `decided_by="player"`（玩家）：以玩家所选为准，但**逐人**写明谁赞成、谁反对、
  谁保留、谁弃权、谁**根本没表态**（`silent_ids` 不写"赞成"），分歧名单随裁决留痕；
- 每人的**自己那条**意图状态随之落 `approved`/`rejected`/`pending`
  （`record_intent` 的 `status` 初值是 `proposed`——**不由叙事宣称已执行**）。

## 五、落档策略

**只走 `core/minister_agent` 的既有通道**（`save_load.py` 白名单固定，新 `state.*` 字段会丢档）：

- 逐人意见 → 各人自己的 `intents` 条目（`record_intent`，初值 `proposed`）；
- 逐人记忆 → 各人自己的 `memory` 条目（`source="朝议:<id>"`，可转述）；
- 裁决 → 就地改写**同一人自己那条**意图的 `status`，并给每人记一条裁决记忆；
- 场次计数 → `state.statistics["ministry_council_sessions"]`（**计数器**，随档持久）；
- **合议本身不另立人物账本**（POP 挂载律：不与 `state.minister_agents` 平行）。

## 六、纪律

- **纯读数不改 state**：`relevant_actors` / `collect_opinions` / `council` 全是纯函数，
  写动作只发生在显式的 `record_council` / `adjudicate`；
- **缺失 ≠ 0 ≠ 1.0**：读不到的立场项记 `None` 并进 `basis_undefined`，
  **不回落 0**（"此人不关心"是假的）；权限未定义 → 单独判、不擅自当成无权或有权；
- **拒绝式**：空议题、空名单、非法裁决项明确报错，不静默产出"一片拥护"；
- **后台数值**：`loyalty`/`corruption` 是内容表明令的隐值，意见里只出**定性档**
  （`loyalty_band`），原始数只用于算分（与 `GameState._loyalty_band` 同一口径）；
- 参数名用 `matter`/`posts`/`actor_ids`；**不用 `route`**（仓库里 `route` ＝外邦行军路线）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

from content.ministers.data import MINISTERS
from core.decree_confidential import holds_matter, posts_of
from core.minister_agent import (
    MINISTER_STATUS_IN_OFFICE,
    actor_view,
    can_act,
    intents_of,
    recall,
    record_intent,
    remember,
)

__all__ = [
    "STANCE_FOR", "STANCE_AGREE", "STANCE_RESERVE", "STANCE_AGAINST",
    "STANCE_URGE", "STANCE_VETO", "STANCE_ABSTAIN", "STANCES",
    "DECISION_APPROVE", "DECISION_REJECT", "DECISION_HOLD",
    "DECISION_VETO", "DECISION_FORCE", "DECISIONS",
    "VETO_MATTER", "COUNCIL_MEMORY_KIND", "relevant_actors",
    "collect_opinions", "council", "record_council", "adjudicate",
    "opinions_of",
]

# ============================================================
# 意见档位（**逐人**；合议只按档归人，不产生"综合意见"）
# ============================================================
STANCE_FOR = "赞成"        # 明确赞成并愿领办
STANCE_AGREE = "附议"      # 赞成但不主张承办
STANCE_RESERVE = "保留"    # 有条件／持保留（**不是**沉默）
STANCE_AGAINST = "反对"
STANCE_URGE = "力谏"      # 强烈反对
STANCE_VETO = "封驳"      # 仅掌「诏令封驳」事权者（门下省）可得
STANCE_ABSTAIN = "弃权"    # 明言不表态（如在野，本就不入对）

STANCES = (STANCE_FOR, STANCE_AGREE, STANCE_RESERVE, STANCE_AGAINST,
           STANCE_URGE, STANCE_VETO, STANCE_ABSTAIN)

#: 合议档位分界（`score` ≥ 下界）
BAND_FOR = 0.22
BAND_AGREE = 0.07
BAND_RESERVE = -0.07
BAND_AGAINST = -0.22

#: 掌此事权者才有封驳之权
VETO_MATTER = "诏令封驳"

#: 朝议记忆条目 kind（落 `minister_agent` 的既有记忆通道）
COUNCIL_MEMORY_KIND = "朝议"

# ============================================================
# 裁决项
# ============================================================
DECISION_APPROVE = "批准"
DECISION_REJECT = "驳回"
DECISION_HOLD = "留中"          # 不表态但也不否决（制度常态）
DECISION_VETO = "封驳"          # 门下省制度性否决
DECISION_FORCE = "御笔裁定"     # 玩家乾纲独断（越过合议，须留分歧痕）

DECISIONS = (DECISION_APPROVE, DECISION_REJECT, DECISION_HOLD,
             DECISION_VETO, DECISION_FORCE)

DECIDED_BY_PLAYER = "player"
DECIDED_BY_INSTITUTION = "institution"
DECIDED_BY = (DECIDED_BY_PLAYER, DECIDED_BY_INSTITUTION)

# ============================================================
# 意见打分（口径单点：权重与倾向表都在这里）
# ============================================================
W_FACTION = 1.00     # 事权×派系倾向（表值本身已带幅）
W_LOYALTY = 0.60     # (loyalty − 0.5) × 议题语调
W_CORRUPTION = 0.50  # 贪墨者在钱粮议题上偏向搜括
W_OFFICE = 0.15      # 职权所系，发言有责
W_CENSOR = 0.08      # 掌监察/言路者天然谨慎
W_MEMORY = 0.08      # 吃过亏的人更谨慎

#: 议题语调：+1＝求变（改制/新法），−1＝守成（赋税/漕运/仓储），`None`＝议题未定义
MATTER_TONE = {
    "官制": 1.0, "人事除授": 0.6, "朝政决策": 0.5,
    "赋税": -0.8, "国库": -0.6, "钱粮户籍": -0.7, "度支调度": -0.5,
    "盐铁专营": 0.4, "财政勾稽": 0.3, "官营放贷": 0.6,
    "工程营造": 0.5, "屯田": 0.3, "山泽": 0.2,
    "调兵": 0.7, "边防": 0.6, "军国机要": 0.6, "禁军": 0.4,
    "言路": 0.3, "谏诤": 0.3, "监察百官": 0.3, "弹劾": 0.3,
    "诏令封驳": 0.3, "政令审议": 0.2, "六部行政": 0.2, "政令奉行": 0.2,
    "礼仪": -0.2, "科举": 0.2, "外事": 0.3,
    "官吏铨选": 0.3, "官员考课": 0.3,
    "武官铨选": 0.2, "军籍": 0.2, "军需后勤": 0.2,
    "粮仓": -0.5, "漕运": -0.6, "市易": 0.4, "商税": 0.4,
}

#: 派系在某事权上的利害（正＝肯配合，负＝掣肘）
MATTER_FACTION_BIAS = {
    "赋税": {"旧党": -0.18, "新党": 0.22, "中立派": 0.08,
             "皇党集团": 0.02, "军功集团": -0.04, "无": None},
    "官营放贷": {"旧党": -0.20, "新党": 0.24, "中立派": 0.10,
                 "皇党集团": 0.06, "军功集团": -0.02, "无": None},
    "市易": {"旧党": -0.12, "新党": 0.20, "中立派": 0.12,
             "皇党集团": 0.08, "军功集团": -0.02, "无": None},
    "官制": {"旧党": -0.22, "新党": 0.20, "中立派": 0.06,
             "皇党集团": 0.02, "军功集团": -0.04, "无": None},
    "人事除授": {"旧党": -0.16, "新党": 0.18, "中立派": 0.06,
                 "皇党集团": 0.06, "军功集团": -0.02, "无": None},
    "调兵": {"旧党": -0.14, "新党": 0.12, "中立派": 0.06,
             "皇党集团": 0.08, "军功集团": 0.26, "无": None},
    "边防": {"旧党": -0.10, "新党": 0.10, "中立派": 0.06,
             "皇党集团": 0.04, "军功集团": 0.24, "无": None},
    "监察百官": {"旧党": 0.18, "新党": -0.18, "中立派": 0.04,
                 "皇党集团": -0.06, "军功集团": -0.02, "无": None},
    "言路": {"旧党": 0.20, "新党": -0.20, "中立派": 0.04,
             "皇党集团": -0.08, "军功集团": -0.02, "无": None},
    "诏令封驳": {"旧党": 0.10, "新党": -0.08, "中立派": 0.02,
                 "皇党集团": 0.04, "军功集团": 0.00, "无": None},
    "工程营造": {"旧党": -0.06, "新党": 0.16, "中立派": 0.08,
                  "皇党集团": 0.04, "军功集团": 0.02, "无": None},
    "国库": {"旧党": -0.14, "新党": 0.20, "中立派": 0.08,
             "皇党集团": 0.04, "军功集团": -0.02, "无": None},
    "内廷": {"旧党": -0.10, "新党": 0.10, "中立派": 0.04,
             "皇党集团": 0.26, "军功集团": 0.00, "无": None},
    "军国机要": {"旧党": -0.12, "新党": 0.12, "中立派": 0.04,
                 "皇党集团": 0.10, "军功集团": 0.22, "无": None},
}

#: 特质 → (利害领域, 倾向值)；领域为 None ＝与议题无关（真零）
TRAIT_COUNCIL_LEAN = {
    "刚直": ("通用", -0.12),
    "清正": ("通用", -0.10),
    "调停": ("通用", -0.04),
    "权谋": ("通用", 0.10),
    "揽权": ("通用", 0.12),
    "阿附": ("通用", 0.12),
    "变法": ("变更", 0.16),
    "聚敛": ("钱粮", 0.14),
    "理财": ("钱粮", 0.12),
    "忠勇": ("军务", 0.14),
    "军略": ("军务", 0.12),
    "怯懦": ("军务", -0.12),
    "才艺": (None, 0.0),
}

#: 属"此人自己的立场"的读数项；这四项**一项都没有**时不产出分数
#: （职权/言路/前科的 0 是"不担任此职/没吃过亏"的真零，**不能冒充立场**）
_STANCE_TERMS = ("faction_interest", "loyalty_to_throne",
                 "fiscal_interest", "trait_lean")

#: 事权 → 利害领域（用于把特质倾向挂到议题上）
_MATTER_DOMAIN = {
    "赋税": "钱粮", "国库": "钱粮", "钱粮户籍": "钱粮", "度支调度": "钱粮",
    "盐铁专营": "钱粮", "财政勾稽": "钱粮", "官营放贷": "钱粮", "商税": "钱粮",
    "市易": "钱粮", "粮仓": "钱粮", "漕运": "钱粮",
    "调兵": "军务", "边防": "军务", "军国机要": "军务", "禁军": "军务",
    "军籍": "军务", "军需后勤": "军务", "武官铨选": "军务",
    "官制": "变更", "人事除授": "变更", "科举": "变更", "屯田": "变更",
    "工程营造": "变更", "山泽": "变更",
}

_MONITOR_MATTERS = ("监察百官", "弹劾", "言路", "谏诤")

#: 议题既定，凡掌**审议链/监察链**事权者**必入对**（台谏在廷议上恒有发言权）。
#: 与议题"相关"不等于"只有办事的人能说话"——反对党也得能开口。
_COUNCIL_CORE_MATTERS = ("诏令封驳", "政令审议", "朝政决策", "六部行政",
                         "政令奉行", "监察百官", "弹劾", "言路", "谏诤")


# ============================================================
# 内部工具
# ============================================================
def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _loyalty_band(v: Optional[float]) -> Optional[str]:
    """忠诚度 → 定性档（与 `GameState._loyalty_band` 同口径；**不出数字**）。"""
    if v is None:
        return None
    if v >= 0.75:
        return "效忠"
    if v >= 0.55:
        return "顺从"
    if v >= 0.38:
        return "敷衍"
    return "离心"


def _agenda_title(agenda: Any) -> str:
    if isinstance(agenda, dict):
        for k in ("title", "topic", "text", "body"):
            v = str(agenda.get(k) or "").strip()
            if v:
                return v
        return ""
    return str(agenda or "").strip()


def _agenda_matter(agenda: Any, matter: Optional[str]) -> Optional[str]:
    if matter:
        return str(matter).strip()
    if isinstance(agenda, dict):
        v = str(agenda.get("matter") or "").strip()
        return v or None
    return None


def _in_office(state, aid: str) -> Optional[bool]:
    """在朝与否：Actor 运行态优先；无 Actor 则看名册与角色状态；都没有 → `None`。"""
    view = actor_view(state, aid)
    if view is not None:
        return view["status"] == MINISTER_STATUS_IN_OFFICE
    if aid in MINISTERS:
        ok = getattr(state, "is_minister_available", None)
        alive = True if not callable(ok) else bool(ok(aid))
        return bool(MINISTERS[aid].get("in_office")) and alive
    return None


def _orgs_of(state, aid: str) -> List[str]:
    posts = posts_of(state, aid)
    return sorted({p["org"] for p in posts}) if posts else []


def _matters_of(state, aid: str) -> List[str]:
    out: List[str] = []
    for oname in _orgs_of(state, aid):
        org = (getattr(state, "central_orgs", None) or {}).get(oname) or {}
        for m in list(org.get("authority") or []) + list(org.get("matter_keys") or []):
            if m and m not in out:
                out.append(str(m))
    return out


def _topic_hits(state, aid: str, title: str) -> int:
    """该人**自己**记忆里与本议题相关的条数（逐人隔离：绝不读他人记忆）。"""
    if not title:
        return 0
    keys = [w for w in str(title).replace("，", " ").replace("。", " ").split() if len(w) >= 2]
    if not keys:
        return 0
    hits = 0
    for e in recall(state, aid):
        text = str(e.get("text") or "") + " " + str(e.get("source") or "")
        if any(k in text for k in keys):
            hits += 1
    return hits


def _stance_of(score: Optional[float], can_veto: Optional[bool]) -> Optional[str]:
    if score is None:
        return None
    if can_veto is True and score < 0:
        return STANCE_VETO
    if score >= BAND_FOR:
        return STANCE_FOR
    if score >= BAND_AGREE:
        return STANCE_AGREE
    if score >= BAND_RESERVE:
        return STANCE_RESERVE
    if score >= BAND_AGAINST:
        return STANCE_AGAINST
    return STANCE_URGE


# ============================================================
# ① 相关官员（复用既有中枢活账，不另造名单）
# ============================================================
def relevant_actors(state, *, matter: Optional[str] = None,
                    orgs: Optional[Iterable[str]] = None,
                    roster: Optional[Iterable[str]] = None,
                    include_out_of_office: bool = False) -> List[Dict[str, Any]]:
    """入对的**相关官员**（依职权回话的那批人），逐人带 `posts`/`authority`/`matters`。

    - 取人口径复用 `state.central_orgs` 的 `holders`（权限跟官职不跟人）与
      `content.ministers.data.MINISTERS` 名册，**不另造人物表**；
    - `matter` 给了则取「掌该事权者」**＋审议/监察链**（门下、中书、尚书、台谏
      在廷议上恒有发言权；改过权限后按 `state.authority_matters` 动态判）；
    - `orgs` 给了则只取该机构在任者；两者皆无 → 取全部中枢在任者；
    - `roster` 限定候选名册（如某次廷议只召这几个人入对）；
    - 在野者默认不入对（`include_out_of_office=True` 才带上并逐人标 `in_office=False`）。
    """
    want_orgs = {str(o).strip() for o in (orgs or []) if str(o or "").strip()}
    only = {str(n).strip() for n in (roster or []) if str(n or "").strip()}
    owner = ""
    key = str(matter or "").strip()
    if key:
        getter = getattr(state, "matter_org", None)
        owner = str(getter(key) or "") if callable(getter) else ""

    seen: List[Dict[str, Any]] = []
    for aid in sorted(only) if only else sorted(_roster_candidates(state)):
        posts = posts_of(state, aid)
        if posts is None and aid not in MINISTERS:
            continue
        org_names = sorted({p["org"] for p in (posts or [])})
        if want_orgs and not (set(org_names) & want_orgs):
            continue
        matters = _matters_of(state, aid)
        if key:
            on_topic = (key in matters) or (owner and owner in org_names)
            in_chain = any(m in matters for m in _COUNCIL_CORE_MATTERS)
            if not (on_topic or in_chain):
                continue
        office = _in_office(state, aid)
        if office is False and not include_out_of_office:
            continue
        view = actor_view(state, aid)
        seen.append({
            "actor_id": aid,
            "posts": posts if posts is not None else [],
            "posts_defined": posts is not None,
            "orgs": org_names,
            "matters": matters,
            "authority": None if view is None else view.get("authority"),
            "authority_defined": bool(view is not None and view.get("authority") is not None),
            "in_office": office,
            "in_roster": aid in MINISTERS,
            "office_role": (MINISTERS.get(aid) or {}).get("role"),
        })
    return seen


def _roster_candidates(state) -> List[str]:
    """候选名册：中枢在任者 ∪ 已建立 Actor 者（**不臆造人物全集**）。"""
    out = set()
    orgs = getattr(state, "central_orgs", None)
    if isinstance(orgs, dict):
        for org in orgs.values():
            if not isinstance(org, dict) or org.get("abolished"):
                continue
            out.update(str(h).strip() for h in (org.get("holders") or {}).values()
                       if str(h or "").strip())
    try:
        from core.minister_agent import actor_ids_of
        out.update(actor_ids_of(state))
    except Exception:  # noqa: BLE001
        pass
    return sorted(out)


# ============================================================
# ② 逐人独立意见（纯读数）
# ============================================================
def collect_opinions(state, agenda: Any, *, actor_ids: Optional[Iterable[str]] = None,
                     matter: Optional[str] = None, orgs: Optional[Iterable[str]] = None,
                     holdings: Optional[Dict[str, Any]] = None,
                     rng: Any = None, turn: Optional[int] = None) -> Dict[str, Any]:
    """每位相关官员**各自**生成一条意见（**纯读数：不改 state、不写记忆**）。

    返回里 `opinions` 逐人可分辨，`silent_ids` 是「在场却未发一言」——
    **沉默不计入支持**，也不冒充忠诚。
    """
    title = _agenda_title(agenda)
    if not title:
        raise ValueError("朝议须有议题（str 或含 title 的对象；拒绝：不产'空合议'）")
    key = _agenda_matter(agenda, matter)

    if actor_ids is None:
        roster = [r["actor_id"] for r in relevant_actors(state, matter=key, orgs=orgs)]
    else:
        roster = [str(a or "").strip() for a in actor_ids]
        if any(not a for a in roster):
            raise ValueError("actor_ids 含空 id（拒绝：不新建无名官员）")
    if not roster:
        raise ValueError("无相关官员可入对（拒绝：不臆造'朝议一致'）")

    t = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))
    opinions: List[Dict[str, Any]] = []
    speaking: List[str] = []
    silent: List[str] = []
    undefined: List[str] = []

    for aid in roster:
        fig = MINISTERS.get(aid) or {}
        extra = (holdings or {}).get(aid) if isinstance(holdings, dict) else None
        extra = extra if isinstance(extra, dict) else {}

        def _val(field):
            v = extra.get(field)
            return v if v is not None else fig.get(field)

        view = actor_view(state, aid)
        office = _in_office(state, aid)
        posts = posts_of(state, aid)
        matters = _matters_of(state, aid)
        can_veto = holds_matter(state, aid, VETO_MATTER)
        monitors = [m for m in _MONITOR_MATTERS if m in matters]

        # —— 逐项打分：缺一项记一项，**不拿 0 顶替** ——
        terms: Dict[str, Optional[float]] = {}
        faction = _val("faction")
        if key:
            bias_map = MATTER_FACTION_BIAS.get(key)
            if bias_map is None:
                terms["faction_interest"] = None
            else:
                terms["faction_interest"] = bias_map.get(str(faction))
        else:
            terms["faction_interest"] = None

        tone = MATTER_TONE.get(key) if key else None
        loyalty = _num(_val("loyalty"))
        terms["loyalty_to_throne"] = (
            None if (loyalty is None or tone is None) else W_LOYALTY * (loyalty - 0.5) * tone)

        corruption = _num(_val("corruption"))
        domain = _MATTER_DOMAIN.get(key) if key else None
        if corruption is None or domain is None:
            terms["fiscal_interest"] = None
        else:
            terms["fiscal_interest"] = (
                0.0 if domain != "钱粮" else W_CORRUPTION * (corruption - 0.5))

        traits = _val("trait_ids")
        if traits is None:
            terms["trait_lean"] = None
        else:
            lean = 0.0
            for tr in traits:
                dom, val = TRAIT_COUNCIL_LEAN.get(str(tr), (None, 0.0))
                if dom is None or domain is None or dom == domain or dom == "通用":
                    lean += float(val)
            terms["trait_lean"] = lean

        terms["office_duty"] = W_OFFICE if (key and key in matters) else 0.0
        terms["censor_duty"] = -W_CENSOR if monitors else 0.0
        hits = _topic_hits(state, aid, title)
        terms["past_experience"] = -W_MEMORY * hits
        own_intents = [e for e in intents_of(state, aid, turn=t) if isinstance(e, dict)]

        # 权限**未定义**不改变他的主张，但必须留下"此处读数缺失"的痕；
        # 能不能**承办**是另一问（见 may_carry），不与"赞成/反对"混为一谈。
        authority = None if view is None else view.get("authority")
        basis_undef = [k for k, v in terms.items() if v is None]
        if authority is None:
            basis_undef.append("authority")

        # 立场读数（派系/忠诚/贪墨/特质）**一项都没有**时不给分数：
        # 职权与言路那几项的 0 是"此人不担任此职"的真零，**不能冒充他的立场**。
        stance_defined = [terms[k] for k in _STANCE_TERMS if terms.get(k) is not None]
        defined = [v for v in terms.values() if v is not None]
        if not stance_defined:
            basis_undef.append("stance_readings")
            score = None
        else:
            score = round(sum(defined), 4)
        confidence = (round(len(defined) / len(terms), 3) if terms else 0.0)

        # 边际带（|score| < BAND_AGREE）：可由调用方注入 rng 制造路径多样性；
        # 缺省 **确定性**（同一局势同一批人 → 同一意见）。
        if rng is not None and score is not None and abs(score) < BAND_AGREE:
            score = round(score + (float(rng()) - 0.5) * 2.0 * BAND_AGREE, 4)

        carry = can_act(state, aid)
        stance = _stance_of(score, can_veto)
        reasons: List[str] = []
        if office is False:
            stance = STANCE_ABSTAIN
            reasons.append("not_in_office")
        if score is None:
            stance = None
            reasons.append("no_defined_basis")
        if aid not in MINISTERS and posts is None:
            stance = None
            reasons.append("not_in_roster")

        op = {
            "actor_id": aid,
            "agenda": title,
            "matter": key,
            "stance": stance,
            "score": score,
            "confidence": confidence,
            "post": None if not posts else posts[0]["post"],
            "posts": posts if posts is not None else [],
            "orgs": _orgs_of(state, aid),
            "matters": matters,
            "authority": authority,
            "authority_defined": authority is not None,
            # 主张 ≠ 承办：能不能承办按 `can_act` 单独判（含 authority_undefined）
            "may_carry": bool(carry.get("ok")),
            "carry_block": None if carry.get("ok") else str(carry.get("reason") or ""),
            "faction": faction,
            "loyalty_band": _loyalty_band(loyalty),
            "in_office": office,
            "can_veto": can_veto,
            "basis": {k: (None if v is None else round(float(v), 4))
                      for k, v in terms.items()},
            "basis_undefined": basis_undef,
            "abstain_reasons": reasons,
            "evidence": {"own_memory_hits": hits,
                         # 自己这回合已登记的意图（**空列表不是赞成**）
                         "own_intent_count": len(own_intents),
                         "own_intents": [str(e.get("intent") or "") for e in own_intents]},
            "turn": t,
        }
        opinions.append(op)
        if stance is None:
            undefined.append(aid)
        else:
            speaking.append(aid)

    # 在场却未发一言者（`[]` ≠ 赞成）：单独一桶，绝不混进支持
    silent = sorted({a for a in roster if a not in speaking})
    return {
        "agenda": title,
        "matter": key,
        "turn": t,
        "roster": list(roster),
        "opinions": opinions,
        "speaking_ids": sorted(speaking),
        "silent_ids": silent,
        "undefined_ids": sorted(undefined),
        "abstain_ids": sorted(o["actor_id"] for o in opinions
                              if o["stance"] == STANCE_ABSTAIN),
    }


def opinions_of(result: Dict[str, Any], stance: Optional[str] = None) -> List[Dict[str, Any]]:
    """从合议结果里取**逐人**意见（可按档位筛）——调用方要"谁的什么主张"时用这个。"""
    rows = [o for o in (result.get("opinions") or []) if isinstance(o, dict)]
    if stance is None:
        return rows
    return [o for o in rows if o.get("stance") == stance]


# ============================================================
# ③ 合议（保留逐人分歧，**不产"综合意见"**）
# ============================================================
def council(state, agenda: Any, **kw) -> Dict[str, Any]:
    """合议：逐人意见 → 按档归人。

    刻意**没有**"朝廷综合意见/最终主张"这类单一字段——把七嘴八舌压成一句话，
    就是 B5-6 禁止的"朝廷综合回答"。只给可判定的布尔与**分歧名单**。
    """
    res = collect_opinions(state, agenda, **kw)
    opinions = res["opinions"]
    title = res["agenda"]
    turn = res["turn"]

    tally: Dict[str, List[str]] = {s: [] for s in STANCES}
    for o in opinions:
        if o["stance"] in tally:
            tally[o["stance"]].append(o["actor_id"])

    support_ids = tally[STANCE_FOR] + tally[STANCE_AGREE]
    oppose_ids = tally[STANCE_AGAINST] + tally[STANCE_URGE] + tally[STANCE_VETO]
    reserve_ids = tally[STANCE_RESERVE]
    abstain_ids = tally[STANCE_ABSTAIN]
    veto_ids = list(tally[STANCE_VETO])
    silent_ids = [a for a in res["silent_ids"] if a not in abstain_ids]

    counted = [s for s in STANCES if tally[s]]
    plurality = max(counted, key=lambda s: len(tally[s])) if counted else None
    dissent_ids = sorted(
        aid for s in counted if s != plurality for aid in tally[s])
    speaking = res["speaking_ids"]

    return {
        "council_id": f"朝议·{turn}·{title[:16]}",
        "agenda": title,
        "matter": res["matter"],
        "turn": turn,
        "opinions": opinions,
        "roster": res["roster"],
        "tally": tally,
        "speaking_ids": speaking,
        "silent_ids": silent_ids,
        "undefined_ids": res["undefined_ids"],
        "abstain_ids": abstain_ids,
        "support_ids": support_ids,
        "oppose_ids": oppose_ids,
        "reserve_ids": reserve_ids,
        "veto_ids": veto_ids,
        # `plurality` 只是"人数最多的那一档"的统计名，用来圈定谁在异议；
        # 它**不是**朝廷的主张——每个人的原话都在 `opinions` 里，一字未改。
        "plurality": plurality,
        "dissent_ids": dissent_ids,
        "distinct_stances": len(counted),
        "has_dissent": len(counted) > 1,
        "unanimous": len(counted) == 1 and len(speaking) == len(res["roster"]),
        "attended": len(res["roster"]),
        "spoke": len(speaking),
        "support_denominator": len(support_ids) + len(oppose_ids),
        "support_ratio": (round(len(support_ids) / (len(support_ids) + len(oppose_ids)), 4)
                          if (support_ids or oppose_ids) else None),
        # 合议本身不落 state；落档见 record_council / adjudicate
        "intent_refs": {},
    }


# ============================================================
# ④ 落档：逐人意图与记忆（只走 minister_agent 既有通道）
# ============================================================
def record_council(state, result: Dict[str, Any], *, record: bool = True) -> Dict[str, Any]:
    """把合议**逐人**落档：每人一条意图（初值 `proposed`）＋ 一条可转述记忆。

    - `record=False` → 纯记账，不写 state（默认写；调用方要"读而不落"时显式关掉）；
    - 意图条目按 `actor_id` 存进结果的 `intent_refs`，供 `adjudicate` 就地改状态。
    """
    opinions = [o for o in (result.get("opinions") or []) if isinstance(o, dict)]
    if not opinions:
        raise ValueError("合议结果无逐人意见（拒绝：不落'无人发言的合议'）")
    cid = str(result.get("council_id") or "朝议")
    turn = result.get("turn")
    written = {}
    for o in opinions:
        aid = str(o.get("actor_id") or "").strip()
        stance = o.get("stance")
        if not aid or stance is None:
            continue
        label = o.get("post") or o.get("office_role") or "在朝"
        intent = f"朝议「{o.get('agenda')}」：{stance}（{label}）"
        if not record:
            continue
        entry = record_intent(state, aid, intent=intent, action="朝议",
                              targets=o.get("orgs") or [],
                              expected=str(o.get("matter") or ""),
                              risk=f"confidence={o.get('confidence')}")
        remember(state, aid, kind=COUNCIL_MEMORY_KIND, text=intent, turn=turn,
                 source=f"{cid}")
        written[aid] = entry
    result.setdefault("intent_refs", {}).update(written)
    return {"council_id": cid, "recorded": sorted(written), "record": bool(record)}


# ============================================================
# ⑤ 裁决：玩家/制度（**不代玩家拍板**）
# ============================================================
def adjudicate(state, result: Dict[str, Any], *, decision: str,
               decided_by: str = DECIDED_BY_PLAYER, reason: str = "",
               actor_id: Optional[str] = None, turn: Optional[int] = None) -> Dict[str, Any]:
    """合议裁决并**逐人**记账（`approved`/`rejected`/`pending`/`silent`）。

    - 制度裁决（`decided_by="institution"`）：门下省封驳者力谏 → **合议不过**；
      否则按**具名**票数定 `通过/驳回/留中`；
    - 玩家裁决（`decided_by="player"`）：以玩家所选为准，但分歧名单与未表态者随裁决留痕；
    - `silent_ids`（未表态）**不会**被写成"赞成"——他们连意图条目都没有。
    """
    dec = str(decision or "").strip()
    if dec not in DECISIONS:
        raise ValueError(f"未知裁决「{dec}」（白名单：{'、'.join(DECISIONS)}）")
    who = str(decided_by or "").strip()
    if who not in DECIDED_BY:
        raise ValueError(f"未知裁决主体「{who}」（{'／'.join(DECIDED_BY)}）")
    opinions = [o for o in (result.get("opinions") or []) if isinstance(o, dict)]
    if not opinions:
        raise ValueError("合议结果无逐人意见（拒绝：不裁决'无人发言'的会）")

    veto_ids = list(result.get("veto_ids") or [])
    support_ids = list(result.get("support_ids") or [])
    oppose_ids = list(result.get("oppose_ids") or [])

    if who == DECIDED_BY_INSTITUTION:
        if veto_ids or dec == DECISION_VETO:
            outcome = "封驳不过"
        elif dec == DECISION_HOLD:
            outcome = "留中"
        elif dec == DECISION_APPROVE:
            outcome = "通过"
        elif dec == DECISION_REJECT:
            outcome = "驳回"
        elif support_ids and len(support_ids) > len(oppose_ids):
            outcome = "通过"
        elif oppose_ids and len(oppose_ids) > len(support_ids):
            outcome = "驳回"
        else:
            outcome = "留中"        # 分歧未消 → 制度上就是留中，**不强行多数**
    else:
        outcome = {"批准": "通过", "驳回": "驳回", "留中": "留中",
                   "封驳": "封驳不过", "御笔裁定": "御笔强裁"}[dec]

    by_actor: Dict[str, str] = {}
    refs = result.get("intent_refs") or {}
    cid = str(result.get("council_id") or "朝议")
    t = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))

    for o in opinions:
        aid = str(o.get("actor_id") or "").strip()
        stance = o.get("stance")
        if not aid or stance is None:
            continue
        if stance in (STANCE_FOR, STANCE_AGREE):
            st = "approved"
        elif stance in (STANCE_AGAINST, STANCE_URGE, STANCE_VETO):
            st = "rejected"
        else:
            st = "pending"
        by_actor[aid] = st
        ref = refs.get(aid)
        if isinstance(ref, dict):
            ref["status"] = st
        remember(state, aid, kind=COUNCIL_MEMORY_KIND,
                 text=f"「{o.get('agenda')}」裁决：{outcome}（本人{stance}）", turn=t,
                 source=f"{cid}·裁决·{who}")

    silent_ids = list(result.get("silent_ids") or [])
    stats = getattr(state, "statistics", None)
    if isinstance(stats, dict):
        stats["ministry_council_sessions"] = int(
            stats.get("ministry_council_sessions", 0) or 0) + 1

    return {
        "council_id": cid,
        "agenda": result.get("agenda"),
        "decision": dec,
        "decided_by": who,
        "decided_by_actor_id": actor_id,
        "outcome": outcome,
        "reason": str(reason or ""),
        "by_actor": by_actor,
        "approved_ids": sorted(a for a, s in by_actor.items() if s == "approved"),
        "rejected_ids": sorted(a for a, s in by_actor.items() if s == "rejected"),
        "pending_ids": sorted(a for a, s in by_actor.items() if s == "pending"),
        "dissent_ids": list(result.get("dissent_ids") or []),
        "veto_ids": veto_ids,
        "silent_ids": silent_ids,
        "attended": result.get("attended"),
        "spoke": result.get("spoke"),
        "turn": t,
    }
