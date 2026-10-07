# -*- coding: utf-8 -*-
"""B5-5 · 密令泄露推演：按**真实知情范围与传递路径**推演，替代固定概率

规格：`market-civilian-economy` §7 B5-5「密令泄露按**真实知情范围/传递路径**推演，
替代固定概率」。要顶替的是 `core/settlement_decree.py:188` 的
`if random.random() < 0.2` —— 那行与「谁知情、怎么知道的」毫无关系。

## 一、知情范围模型（**不建平行账本**）

知情范围的**唯一权威**是 `core/minister_agent.py` 里**逐人各自的记忆**
（`state.minister_agents[*].memory`）。本模块**不另立人物表、不另立知情名单**：

| 层级 | 谁知道什么 | 落在哪 | 怎么读回来 |
|---|---|---|---|
| `密令`（MEMORY_KIND_SECRET） | **正文**（获授权承办者） | 授权人自己的记忆条目 | `recall()` |
| `密令风声`（MEMORY_KIND_HEARSAY） | **只知"有此密令"**，不知内容 | 被知会者/听闻者的记忆条目 | `recall()` |
| 无人知情 | —— | —— | **不建模**（不枚举"谁不知道"，缺省 `unaware=None`） |

因此：

- **知集合是派生的**：`knowledge_of()` 扫描**每个人自己的**记忆条目（`source` 前缀
  `密令:<decree_id>`）汇总，**不维护第二本名单**（POP 挂载律：与既有状态不平行）；
- **未授权者看不到正文**：`read_secret_decree()` 只在授权人的记忆里取正文，
  他人得到 `may_read_body=False` + `body=None`（**不是空串、不是占位符**）；
- **沉默 ≠ 知情**：没在廷议里的人不在任何名单里，`knowledge_of` 不会把他算成「知情但沉默」。

## 二、传递路径模型（泄露风险从哪来）

泄露不是掷一枚常量骰子。风险由**三组真实读数**相乘得到（口径单点，权重皆在本模块常量表）：

```
exposure(接触) = 途径固有暴露度(途径) × 接触频次(接触) × 泄压(知情者) × 接触度(知情者)
泄露风险       = 1 − Π(1 − exposure_i)        （任一环节泄出即泄露；可加、可辨、可追溯）
```

| 因素 | 读数来源 | 缺失时 |
|---|---|---|
| **途径**（`奏对`/`廷议`/`私谒`/`公文抄送`/`被监听`） | `CHANNEL_EXPOSURE_BASE` | 未知途径 → **拒绝**该接触 |
| **接触频次** | 调用方给的真实接触（谁在场、多密切） | 非法数值 → **拒绝** |
| **泄压** | `MINISTERS[人]` 的 `loyalty`/`corruption`/`trait_ids` | 人不在名册 → `pressure=None` → **该接触风险未定义（挂起）** |
| **接触度** | `minister_agent` 的 `authority`；未定义时改用 `state.central_orgs` 的掌事权这一**另有的真实读数** | 标 `basis_undefined`，不回落 1.0 |

`被监听` 的固有暴露度是 `1.0`：**话已被听见不是概率问题**，是已发生的事实。
这与"某人在某条路上会不会说出去"是两类事件，故本模块也把
**「外泄给未授权者」** 与 **「被台谏察觉」** 分开判——原先那行 `0.2` 把两件事糊成一件。

## 三、泄露后知情集合**真实传播**

`simulate_leak()` 沿**调用方给的真实路径链**逐跳推进：

- 只有**已经知情**的人才能外传（未知者的接触记 `skipped_not_aware`，不猜）；
- 泄出的人经 `minister_agent.remember(..., source="密令:<id>·<途径>·甲→乙")` 落进**自己**的记忆，
  记忆的 `source` 即**传递路径**，可回放；
- 他随后在路径链上的接触，用**他自己的**泄压继续推演（真实的**二次传播**）；
- **泄密有轻重**：`公文抄送`/`被监听` 泄出**正文**，其余途径默认只流出「风声」，
  暴露分还要再高出一档（`BODY_LEAK_MARGIN`）才泄正文。

## 四、落档策略

**只写 `minister_agent` 的既有通道**，不新增 `state.*` 字段（`save_load.py` 白名单固定，
新字段会丢档）：

- 知情范围 → 各人自己的记忆条目（`minister_agents[*].memory`，随档持久）；
- 泄出链 → 新知情者的记忆条目，`source` 记传递路径（**逐人可追溯**）；
- 风险读数（`exposure_profile`/`assess_leak`）→ **纯函数返回值，不落 state**
  （读数不得改状态；`assess_leak` 绝不写记忆）。

## 五、纪律

- **缺失 ≠ 0 ≠ 1.0**：名册查不到人 → `pressure=None` → `exposure=None` →
  该接触 `outcome="undefined"`（挂起待读数），**不按 0 记"无人泄"、不按 1.0 记"必泄"**；
- **拒绝式**：空 `decree_id`、空授权名单、未知途径、非法频次、`witness==holder`
  明确报错或记原因，不静默放行；
- **逐人隔离**：任何人只读自己的记忆（`recall(state, aid, ...)`），
  推演他人泄压只读 `MINISTERS` 的**静态立场**，不读别人的记忆内容；
- **后台数值**：`loyalty`/`corruption` 是 `content/ministers/data.py` 明令的
  "仅在 AI 推演与后台结算中使用"隐值，本模块只在 `assess_leak` 的风险读数里用，
  面向玩家的文案请取 `GameState._loyalty_band` 那一档。
- 参数名用 `channel`/`witness`/`holder`/`path`；**不用 `route`**（仓库里 `route` ＝外邦行军路线）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

from content.ministers.data import MINISTERS
from core.domains.administration.minister_agent import actor_ids_of, can_act, recall, remember

__all__ = [
    "CHANNEL_AUDIENCE", "CHANNEL_COUNCIL", "CHANNEL_PRIVATE",
    "CHANNEL_DOC_COPY", "CHANNEL_EAVESDROP", "CHANNELS",
    "CHANNEL_EXPOSURE_BASE", "CHANNEL_CARRIES_BODY", "BODY_LEAK_MARGIN",
    "MEMORY_KIND_SECRET", "MEMORY_KIND_HEARSAY", "SOURCE_PREFIX",
    "TRAIT_LEAK_BIAS", "LEAK_THRESHOLD", "W_LOYALTY", "W_CORRUPTION",
    "sealing_source", "transfer_source", "seal_secret_decree",
    "read_secret_decree", "knowledge_of", "standing_of",
    "posts_of", "holds_matter", "exposure_profile", "assess_leak",
    "simulate_leak",
]

# ============================================================
# 途径（知情范围模型的第一维：消息怎么流动）
# ============================================================
CHANNEL_AUDIENCE = "奏对"          # 面陈：单独奏对，接触面最窄
CHANNEL_COUNCIL = "廷议"          # 群臣在列，最易外溢
CHANNEL_PRIVATE = "私谒"           # 私下游说，接触最少而最易结党
CHANNEL_DOC_COPY = "公文抄送"     # 案牍抄送：知情人随抄送链一路扩散
CHANNEL_EAVESDROP = "被监听"      # 并无"接触"可言：话已经被听见

CHANNELS = (CHANNEL_AUDIENCE, CHANNEL_COUNCIL, CHANNEL_PRIVATE,
            CHANNEL_DOC_COPY, CHANNEL_EAVESDROP)

#: 途径固有暴露度（只描述"这条途径本身有多外露"，不含任何人情；口径单点）
CHANNEL_EXPOSURE_BASE = {
    CHANNEL_AUDIENCE: 0.22,
    CHANNEL_COUNCIL: 0.46,
    CHANNEL_PRIVATE: 0.14,
    CHANNEL_DOC_COPY: 0.34,
    CHANNEL_EAVESDROP: 1.00,     # 已被听见：不是概率问题
}

#: 哪些途径会把**正文**带出去（其余途径默认只泄"风声"）
CHANNEL_CARRIES_BODY = (CHANNEL_DOC_COPY, CHANNEL_EAVESDROP)

#: 风声途径要泄出正文，暴露分还需再高出这一档
BODY_LEAK_MARGIN = 0.35

#: 实质外泄的暴露分阈值（口径单点；可调）
LEAK_THRESHOLD = 0.50

# ============================================================
# 记忆种类与 source 前缀（知情范围的落档口径，与 minister_agent 对齐）
# ============================================================
MEMORY_KIND_SECRET = "密令"          # 持有正文
MEMORY_KIND_HEARSAY = "密令风声"    # 只知"有此密令"
SOURCE_PREFIX = "密令:"

# ============================================================
# 泄压（人物立场 → 会不会把话递出去）
# ============================================================
W_LOYALTY = 1.30        # (1 - loyalty)：死忠者压得住
W_CORRUPTION = 0.70     # corruption：贪墨者借机攀附
PRESSURE_FLOOR = 0.05   # 再死忠也非无漏（模型下限，**不是**缺失兜底）

#: 特质 → 泄压增减（content/ministers/data.TRAITS 的机制侧注记，不改内容表）
TRAIT_LEAK_BIAS = {
    "聚敛": 0.22, "揽权": 0.18, "权谋": 0.16, "阿附": 0.14,
    "才艺": 0.06, "变法": 0.06, "理财": 0.04,
    "怯懦": 0.10, "调停": -0.04, "军略": -0.02, "忠勇": -0.10,
    "清正": -0.16, "刚直": -0.18,
}

#: 权限越高越招人接近（接触度加成）
AUTHORITY_ATTRACT = 0.60

#: 掌这类事权者天然接触机密（接触度加成）
SECRET_MATTERS = ("军国机要", "禁中庶务", "内廷", "草诏", "内制",
                  "调兵", "边防", "官制", "人事除授", "朝政决策")

#: 掌这类事权者一旦接触即为「台谏察觉」（区别于外泄给未授权者）
WATCH_MATTERS = ("言路", "谏诤", "监察百官", "弹劾", "诏令封驳", "政令审议")


# ============================================================
# 内部工具
# ============================================================
def _num(v: Any) -> Optional[float]:
    """有限数值化；`None`/非数/非有限一律 `None`（缺失不作 0、不作 1.0）。"""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


def _org_table(state) -> Dict[str, Any]:
    """机构活账：`state.central_orgs` 优先，回退内容表（与 `core.institution` 同口径）。"""
    orgs = getattr(state, "central_orgs", None)
    if isinstance(orgs, dict) and orgs:
        return orgs
    try:
        from content.ministers.data import CENTRAL_ORG_INFO
        return CENTRAL_ORG_INFO
    except Exception:  # noqa: BLE001 - 内容表缺失不应让结算路径崩
        return {}


def _matters_of(state, org_name: str) -> List[str]:
    """某机构当前掌有的事权（机构表 ＋ 事权表 owner 反查）。"""
    out: List[str] = []
    org = _org_table(state).get(org_name)
    if isinstance(org, dict):
        out += [str(m) for m in (org.get("authority") or [])]
        out += [str(m) for m in (org.get("matter_keys") or [])]
    matters = getattr(state, "authority_matters", None)
    if not isinstance(matters, dict) or not matters:
        try:
            from content.ministers.data import AUTHORITY_MATTERS
            matters = AUTHORITY_MATTERS
        except Exception:  # noqa: BLE001
            matters = {}
    for m, info in (matters or {}).items():
        if isinstance(info, dict) and info.get("owner") == org_name:
            out.append(str(m))
    seen, uniq = set(), []
    for m in out:
        if m and m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq


def posts_of(state, actor_id: str) -> Optional[List[Dict[str, str]]]:
    """该人在中枢担任的官职（`[{org, post}]`）。

    **不建人物↔官职对照表**：直接反查既有 `state.central_orgs` 的 `holders`
    （权限跟官职、不跟人）。查不到返回 `[]`（该人不在中枢任职），
    名册与中枢表都没有该人时返回 `None`（**读数缺失**）。
    """
    aid = str(actor_id or "").strip()
    if not aid:
        return []
    orgs = _org_table(state)
    hits: List[Dict[str, str]] = []
    for oname, org in orgs.items():
        if not isinstance(org, dict) or org.get("abolished"):
            continue
        for post, holder in (org.get("holders") or {}).items():
            if str(holder or "").strip() == aid:
                hits.append({"org": str(oname), "post": str(post)})
    if hits:
        return hits
    if aid not in MINISTERS:
        return None
    return []


def holds_matter(state, actor_id: str, matter: str) -> Optional[bool]:
    """该人是否掌某事权。读数缺失（人不在名册也不在中枢）→ `None`。"""
    key = str(matter or "").strip()
    if not key:
        return None
    posts = posts_of(state, actor_id)
    if posts is None:
        return None
    for hit in posts:
        if key in _matters_of(state, hit["org"]):
            return True
    if str(actor_id or "").strip() in MINISTERS:
        return False
    return None


def standing_of(actor_id: str, holdings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """该人的**立场读数**（loyalty/corruption/traits/faction/in_office）。

    `holdings` 可由调用方补齐（如已在朝中调整过的忠诚度）。
    读不到的字段一律 `None`——**不回落 0（"最不可信"）也不回落 0.5（"照算一半"）**。
    """
    aid = str(actor_id or "").strip()
    fig = MINISTERS.get(aid) or {}
    if not isinstance(fig, dict):
        fig = {}
    extra = (holdings or {}).get(aid) if isinstance(holdings, dict) else None
    extra = extra if isinstance(extra, dict) else {}

    def pick(key):
        v = extra.get(key)
        if v is None:
            v = fig.get(key)
        return v

    return {
        "actor_id": aid,
        "in_roster": aid in MINISTERS,
        "faction": pick("faction"),
        "loyalty": _num(pick("loyalty")),
        "corruption": _num(pick("corruption")),
        "trait_ids": list(pick("trait_ids") or []) if (pick("trait_ids") is not None) else None,
        "office_role": pick("role"),
        "is_minister": aid in MINISTERS,
    }


def _pressure(standing: Dict[str, Any]) -> Optional[float]:
    """泄压（0~1 倾向值）；立场读数缺失 → `None`（不猜）。"""
    loyalty = standing.get("loyalty")
    corruption = standing.get("corruption")
    if loyalty is None or corruption is None:
        return None
    raw = (1.0 - float(loyalty)) * W_LOYALTY + float(corruption) * W_CORRUPTION
    traits = standing.get("trait_ids")
    if traits is not None:
        raw += sum(float(TRAIT_LEAK_BIAS.get(str(t), 0.0)) for t in traits)
    else:
        # 特质读数缺失：该项不计（并非"此人无特质"），并让调用方看到 undefined
        return None
    return max(PRESSURE_FLOOR, min(1.0, raw))


def _attract(state, actor_id: str) -> tuple:
    """接触度倍率与缺失项：`(倍率, basis_undefined)`。

    权限（`minister_agent` 的 `authority`）已定义 → 直接用；
    **未定义**时改用"掌何事权"这一**另有的真实读数**推定，并标 `authority_undefined`
    （**不回落 1.0 当作"权限正常"**）。
    """
    undefined = []
    actor = (getattr(state, "minister_agents", None) or {}).get(str(actor_id or "").strip())
    auth = _num((actor or {}).get("authority")) if isinstance(actor, dict) else None
    if auth is not None:
        return 1.0 + AUTHORITY_ATTRACT * auth, undefined
    undefined.append("holder_authority")
    posts = posts_of(state, actor_id)
    if posts is None:
        return 1.0, undefined          # 无任何可据的真实读数 → 仍给基准，但缺失已标
    for hit in posts:
        if any(m in SECRET_MATTERS for m in _matters_of(state, hit["org"])):
            return 1.0 + AUTHORITY_ATTRACT, undefined
    return 1.0, undefined


def sealing_source(decree_id: str) -> str:
    """授权下旨时的 `source`（可转述的正式来源）。"""
    return f"{SOURCE_PREFIX}{str(decree_id or '').strip()}"


def transfer_source(decree_id: str, channel: str, holder: str, witness: str) -> str:
    """外泄/转述时的 `source`：**传递路径本身**（回放得出一条链）。"""
    return (f"{SOURCE_PREFIX}{str(decree_id or '').strip()}·{str(channel or '').strip()}"
            f"·{str(holder or '').strip()}→{str(witness or '').strip()}")


def _decree_id(decree: Any) -> str:
    if isinstance(decree, dict):
        for k in ("decree_id", "id", "task_id"):
            v = str(decree.get(k) or "").strip()
            if v:
                return v
        return str(decree.get("title") or "").strip()
    return str(decree or "").strip()


def _decree_body(decree: Any) -> str:
    if not isinstance(decree, dict):
        return ""
    for k in ("body", "desc", "text", "content", "title"):
        v = decree.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


# ============================================================
# ① 立密令：建立知情范围（授权者得正文，被知会者只得风声）
# ============================================================
def seal_secret_decree(state, decree: Any, *, authorized: Iterable[str],
                       informed: Iterable[str] = (), channel: str = CHANNEL_AUDIENCE,
                       turn: Optional[int] = None) -> Dict[str, Any]:
    """下密令并**建立知情范围**。授权者得**正文**，被知会者只知"有此密令"。

    - `authorized` 不可为空：密令没有承办人等于没有密令；
    - 落档**只走** `minister_agent.remember`（各人自己的记忆），**不建第二本知情名单**；
    - 被知会者的条目**不含正文**（这是"未授权者看不到正文"的地基）。
    """
    did = _decree_id(decree)
    if not did:
        raise ValueError("密令须有 decree_id/id/title（拒绝：无名密令无法界定知情范围）")
    if channel not in CHANNELS:
        raise ValueError(f"未知传递途径「{channel}」（白名单：{'、'.join(CHANNELS)}）")

    auth_ids: List[str] = []
    for aid in (authorized or []):
        name = str(aid or "").strip()
        if not name:
            raise ValueError("authorized 含空 actor_id（拒绝：不新建无名官员）")
        if name not in auth_ids:
            auth_ids.append(name)
    if not auth_ids:
        raise ValueError("authorized 不可为空（拒绝：一道密令必有其承办人）")

    body = _decree_body(decree)
    t = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))

    for name in auth_ids:
        remember(state, name, kind=MEMORY_KIND_SECRET, text=body, turn=t,
                 source=sealing_source(did))

    heard: List[str] = []
    for aid in (informed or []):
        name = str(aid or "").strip()
        if not name:
            raise ValueError("informed 含空 actor_id（拒绝）")
        if name in auth_ids or name in heard:
            continue
        heard.append(name)
        remember(state, name, kind=MEMORY_KIND_HEARSAY,
                 text=f"[{did}] 有密令一道（未授权，不知正文）", turn=t,
                 source=transfer_source(did, channel, "上", name))

    return {
        "decree_id": did,
        "turn": t,
        "authorized": list(auth_ids),
        "informed": list(heard),
        "channel": channel,
        "body_length": len(body),
        "not_in_roster": [n for n in auth_ids + heard if n not in MINISTERS],
    }


# ============================================================
# ② 读知情范围（**派生**，不落第二本账）
# ============================================================
def _entries_of(state, actor_id: str, decree_id: str) -> List[Dict[str, Any]]:
    """该人**自己**关于此密令的记忆条目（逐人隔离：只读本人）。"""
    out = []
    prefix = sealing_source(decree_id)
    for e in recall(state, actor_id):
        if not isinstance(e, dict):
            continue
        src = str(e.get("source") or "")
        if not src.startswith(prefix):
            continue
        out.append(e)
    return out


def knowledge_of(state, decree_id: str, *, roster: Optional[Iterable[str]] = None
                 ) -> Dict[str, Any]:
    """由此密令派生的**知情集合**（授权／只闻风声／谁也不知情）。

    - 只扫 `state.minister_agents` 里**已建立**的人（不臆造全集）；
    - `roster` 给了才算 `unaware`（未给则 `unaware=None`：**不枚举"谁不知道"**）；
    - 每人的知情途径取自其记忆 `source`（**逐人可追溯**）。
    """
    did = str(decree_id or "").strip()
    if not did:
        raise ValueError("decree_id 不能为空（拒绝：不猜密令）")

    authorized: List[str] = []
    heard: List[str] = []
    per_actor: Dict[str, Any] = {}
    for aid in actor_ids_of(state):
        entries = _entries_of(state, aid, did)
        if not entries:
            continue
        has_body = any(e.get("kind") == MEMORY_KIND_SECRET for e in entries)
        (authorized if has_body else heard).append(aid)
        per_actor[aid] = {
            "has_body": has_body,
            "kinds": sorted({str(e.get("kind")) for e in entries}),
            "via": sorted({str(e.get("source") or "") for e in entries}),
            "turns": sorted({int(e.get("turn", 0) or 0) for e in entries}),
        }

    unaware = None
    if roster is not None:
        known = set(authorized) | set(heard)
        unaware = [str(n).strip() for n in roster
                   if str(n or "").strip() and str(n).strip() not in known]

    return {
        "decree_id": did,
        "authorized": sorted(authorized),
        "heard_only": sorted(heard),
        "unaware": (sorted(unaware) if unaware is not None else None),
        "per_actor": per_actor,
        "known_count": len(authorized) + len(heard),
    }


def read_secret_decree(state, actor_id: str, decree_id: str) -> Dict[str, Any]:
    """按**该人的知情范围**读密令。

    未授权者：`may_read_body=False`、`body=None`、`reason="hearsay_only"`
    —— 知道"有此密令"，**看不到正文**（不是空串、不是占位、不是"暂无内容"）。
    """
    aid = str(actor_id or "").strip()
    did = str(decree_id or "").strip()
    if not aid or not did:
        raise ValueError("actor_id 与 decree_id 均不可为空（拒绝）")
    entries = _entries_of(state, aid, did)
    if not entries:
        actor = (getattr(state, "minister_agents", None) or {}).get(aid)
        reason = "unknown_actor" if not isinstance(actor, dict) else "unknown_decree"
        return {"actor_id": aid, "decree_id": did, "may_read_body": False,
                "body": None, "reason": reason, "via": [], "turns": []}
    body_entries = [e for e in entries if e.get("kind") == MEMORY_KIND_SECRET]
    via = sorted({str(e.get("source") or "") for e in entries})
    turns = sorted({int(e.get("turn", 0) or 0) for e in entries})
    if body_entries:
        return {"actor_id": aid, "decree_id": did, "may_read_body": True,
                "body": str(body_entries[-1].get("text") or ""), "reason": "authorized",
                "via": via, "turns": turns}
    return {"actor_id": aid, "decree_id": did, "may_read_body": False, "body": None,
            "reason": "hearsay_only", "via": via, "turns": turns}


# ============================================================
# ③ 真实传递路径 → 暴露剖面（纯读数）
# ============================================================
def _normalize_contacts(contacts: Optional[Iterable[Any]]) -> List[Dict[str, Any]]:
    """规范化接触表；非法项抛错（拒绝式，不静默丢弃）。"""
    rows: List[Dict[str, Any]] = []
    for c in (contacts or []):
        if not isinstance(c, dict):
            raise ValueError(f"contact 须为对象（拒绝）：{c!r}")
        channel = str(c.get("channel") or "").strip()
        if channel not in CHANNELS:
            raise ValueError(f"未知传递途径「{channel}」（白名单：{'、'.join(CHANNELS)}）")
        freq = _num(c.get("frequency", 1))
        if freq is None:
            raise ValueError(f"接触频次须为有限数值（拒绝）：{c.get('frequency')!r}")
        if freq <= 0:
            raise ValueError("接触频次须 > 0（拒绝：没有接触就谈不上传递）")
        holder = str(c.get("holder") or "").strip()
        witness = c.get("witness")
        witness = str(witness).strip() if witness is not None else None
        if not holder:
            raise ValueError("contact 须指明知情者 holder（拒绝：不猜谁知情）")
        if witness is not None and not witness:
            witness = None
        if witness == holder:
            raise ValueError(f"接触「{holder}」以自身为旁听者（拒绝：自传不算泄露路径）")
        rows.append({"holder": holder, "channel": channel, "witness": witness,
                     "frequency": freq})
    return rows


def _default_contacts(state, did: str, audience: Optional[Iterable[str]],
                      channels: Optional[Iterable[str]]) -> List[Dict[str, Any]]:
    """未给接触表时，按**既有真实读数**推一条默认传递路径：

    - 给了 `audience`（在场名单）：每个知情者 × 每个未授权在场者，各按一路途径；
    - 未给：只知"谁知情、经哪条途径得知"（取自其记忆 `source`），
      旁听者留空（`witness=None`）——**暴露可算，但泄给谁不猜**。
    """
    know = knowledge_of(state, did)
    holders = list(know["authorized"])
    chans = [c for c in (channels or (CHANNEL_COUNCIL,)) if c in CHANNELS] or [CHANNEL_COUNCIL]
    if audience is not None:
        aud = [str(n).strip() for n in audience if str(n or "").strip()]
        rows = []
        for h in holders:
            for w in aud:
                if w == h or w in know["authorized"]:
                    continue
                for c in chans:
                    rows.append({"holder": h, "channel": c, "witness": w, "frequency": 1.0})
        return rows

    rows = []
    for h in holders:
        vias = know["per_actor"].get(h, {}).get("via") or []
        seen = set()
        for src in vias:
            parts = str(src).split("·")
            ch = parts[1] if len(parts) > 1 else ""
            if ch not in CHANNELS or ch in seen:
                continue
            seen.add(ch)
            rows.append({"holder": h, "channel": ch, "witness": None,
                         "frequency": float(max(1, len(vias)))})
        if not seen:
            rows.append({"holder": h, "channel": CHANNEL_AUDIENCE, "witness": None,
                         "frequency": 1.0})
    return rows


def exposure_profile(state, decree_id: str, *, contacts: Optional[Iterable[Any]] = None,
                     holdings: Optional[Dict[str, Any]] = None,
                     audience: Optional[Iterable[str]] = None,
                     channels: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """**逐条**传递路径的暴露剖面（纯读数：绝不改 state）。

    每一行给出：途径固有暴露度、接触频次、知情者泄压、接触度、**暴露分**
    （`None` ＝ 读数缺失、挂起待补），以及旁听者是否**掌台谏事权**（决定"被察觉"）。
    """
    did = str(decree_id or "").strip()
    if not did:
        raise ValueError("decree_id 不能为空（拒绝）")
    know = knowledge_of(state, did)
    rows_in = (_normalize_contacts(contacts) if contacts is not None
               else _default_contacts(state, did, audience, channels))

    rows: List[Dict[str, Any]] = []
    for c in rows_in:
        holder = c["holder"]
        st = standing_of(holder, holdings)
        pressure = _pressure(st)
        attract, attract_undef = _attract(state, holder)
        base = float(CHANNEL_EXPOSURE_BASE[c["channel"]])
        freq = float(c["frequency"])
        witness = c["witness"]
        detects = None if witness is None else holds_matter(state, witness, "言路")
        if detects is False:
            # 掌的是别的监察事权也算台谏
            for m in WATCH_MATTERS[1:]:
                hit = holds_matter(state, witness, m)
                if hit is True:
                    detects = True
                    break
        undefined = []
        if pressure is None:
            undefined.append("holder_standing")
        undefined += attract_undef
        exposure = None if pressure is None else base * freq * pressure * attract
        if exposure is not None:
            exposure = round(min(1.0, max(0.0, exposure)), 4)
        rows.append({
            "holder": holder,
            "channel": c["channel"],
            "witness": witness,
            "frequency": freq,
            "channel_base": base,
            "pressure": None if pressure is None else round(pressure, 4),
            "attract": round(attract, 4),
            "exposure": exposure,
            "defined": exposure is not None,
            "witness_watches": detects,
            "basis_undefined": undefined,
            "holder_in_roster": bool(st.get("in_roster")),
        })

    defined = [r for r in rows if r["defined"]]
    surv = 1.0
    for r in defined:
        surv *= (1.0 - float(r["exposure"]))
    watch_rows = [r for r in rows if r["defined"] and r["witness"]
                  and r["witness_watches"] is True]

    # 缺失不作 0：只要有**一条**接触读数未定义，总风险就是**未定义**，
    # 只另给一个**明示的下界**（不是"实际风险"）。全未定义时上下界都无。
    lower = None if not defined else round(1.0 - surv, 4)
    complete = bool(defined) and len(defined) == len(rows)
    det_lower = None if not defined else round(
        1.0 - _prod([1.0 - float(r["exposure"]) for r in watch_rows]), 4)

    return {
        "decree_id": did,
        "known_count": know["known_count"],
        "authorized": know["authorized"],
        "heard_only": know["heard_only"],
        "contacts": rows,
        "defined_contacts": len(defined),
        "undefined_contacts": len(rows) - len(defined),
        "leak_risk": lower if complete else None,
        "leak_risk_lower_bound": lower,
        "leak_risk_defined": complete,
        "detection_risk": det_lower if complete else None,
        "detection_risk_lower_bound": det_lower,
        "peak_holder": None if not defined else max(defined, key=lambda r: r["exposure"])["holder"],
        "peak_channel": None if not defined else max(defined, key=lambda r: r["exposure"])["channel"],
    }


def _prod(values: Iterable[float]) -> float:
    out = 1.0
    for v in values:
        out *= v
    return out


def assess_leak(state, decree_id: str, *, threshold: float = LEAK_THRESHOLD,
                **kw) -> Dict[str, Any]:
    """泄露风险读数（**纯函数**：不改 state，不写记忆）。

    与 `exposure_profile` 同源，另加两件事：
    - `predicted_paths`：哪几条接触已过 `threshold`（**可追溯到具名的人与途径**）；
    - `outcome`：全未定义 → `"undefined"`（挂起）；有未定义且有过线 → `"partial"`。
    """
    kw = dict(kw)
    thr = kw.pop("threshold", threshold)
    prof = exposure_profile(state, decree_id, **kw)
    threshold = LEAK_THRESHOLD if thr is None else float(thr)
    body_margin = BODY_LEAK_MARGIN
    predicted = []
    for r in prof["contacts"]:
        if not r["defined"]:
            continue
        e = float(r["exposure"])
        if e >= threshold:
            predicted.append({
                "holder": r["holder"], "witness": r["witness"],
                "channel": r["channel"], "exposure": e,
                "carries_body": (r["channel"] in CHANNEL_CARRIES_BODY
                                 or e >= threshold + body_margin),
                "detectable": r["witness_watches"] is True,
            })
    if not prof["defined_contacts"]:
        outcome = "undefined"
    elif prof["undefined_contacts"]:
        outcome = "partial" if predicted else "undefined_partial"
    else:
        outcome = "assessed"
    out = dict(prof)
    out["threshold"] = threshold
    out["predicted_paths"] = predicted
    out["outcome"] = outcome
    return out


# ============================================================
# ④ 泄露落地：知情集合沿真实路径**真传播**
# ============================================================
def simulate_leak(state, decree_id: str, *, contacts: Optional[Iterable[Any]] = None,
                  holdings: Optional[Dict[str, Any]] = None,
                  audience: Optional[Iterable[str]] = None,
                  channels: Optional[Iterable[str]] = None,
                  threshold: float = LEAK_THRESHOLD, max_leaks: int = 3,
                  rng: Any = None, turn: Optional[int] = None) -> Dict[str, Any]:
    """沿**真实传递路径**推演泄露并**真实传播知情集合**（写入 `minister_agent` 记忆）。

    - 逐跳推进：知情者在外泄后即成为新的知情者，其后各跳用**他自己**的泄压；
    - **不传正文者只落"风声"**（`MEMORY_KIND_HEARSAY`），正文另需过一道更严的门槛；
    - 未知情者的接触记 `skipped_not_aware`（**不猜他知情**）；
    - 立场读数缺失的接触记 `undefined`（**不按"无人泄"结案**）；
    - `rng` 缺省＝**确定性**（暴露分过线即泄）；给了则按 `rng.random() < exposure`
      判，用于长局跑路径多样性（`rng` 由调用方注入，本模块不自己 `random.random()`）。
    """
    did = str(decree_id or "").strip()
    if not did:
        raise ValueError("decree_id 不能为空（拒绝）")
    thr = _num(threshold)
    if thr is None or thr <= 0:
        raise ValueError("threshold 须为正有限数（拒绝）")
    cap = int(max_leaks) if isinstance(max_leaks, int) and max_leaks > 0 else 3

    prof = assess_leak(state, did, contacts=contacts, holdings=holdings,
                       audience=audience, channels=channels, threshold=thr)
    know = knowledge_of(state, did)
    with_body = set(know["authorized"])
    heard = set(know["heard_only"])
    # 正文取自授权人的记忆（**知情范围的唯一权威**），不是另存的密令档案
    body = None
    for aid in know["authorized"]:
        got = read_secret_decree(state, aid, did)
        if got["may_read_body"] and got["body"]:
            body = got["body"]
            break

    t = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))
    chain: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    undefined: List[Dict[str, Any]] = []
    detected_by: List[str] = []

    for row in prof["contacts"]:
        holder, channel, witness = row["holder"], row["channel"], row["witness"]
        if holder not in with_body and holder not in heard:
            skipped.append({"holder": holder, "channel": channel, "witness": witness,
                            "reason": "skipped_not_aware"})
            continue
        if not row["defined"]:
            undefined.append({"holder": holder, "channel": channel, "witness": witness,
                              "basis_undefined": row["basis_undefined"]})
            continue
        if witness is None:
            skipped.append({"holder": holder, "channel": channel, "witness": None,
                            "reason": "no_witness_identified"})
            continue
        if len(chain) >= cap:
            skipped.append({"holder": holder, "channel": channel, "witness": witness,
                            "reason": "leak_cap_reached"})
            continue
        exposure = float(row["exposure"])
        fires = exposure >= thr if rng is None else float(rng()) < exposure
        if not fires:
            continue
        carries = (channel in CHANNEL_CARRIES_BODY or exposure >= thr + BODY_LEAK_MARGIN)
        if body is None or not carries:
            remember(state, witness, kind=MEMORY_KIND_HEARSAY,
                     text=f"[{did}] 有密令一道（未授权，不知正文）", turn=t,
                     source=transfer_source(did, channel, holder, witness))
            heard.add(witness)
        else:
            remember(state, witness, kind=MEMORY_KIND_SECRET, text=body, turn=t,
                     source=transfer_source(did, channel, holder, witness))
            with_body.add(witness)
        chain.append({"holder": holder, "channel": channel, "witness": witness,
                      "exposure": exposure, "turn": t,
                      "carried": "body" if (body is not None and carries) else "hearsay"})
        if row["witness_watches"] is True and witness not in detected_by:
            detected_by.append(witness)

    after = knowledge_of(state, did)
    return {
        "decree_id": did,
        "turn": t,
        "leaked": bool(chain),
        "body_leaked": any(c["carried"] == "body" for c in chain),
        "chain": chain,
        "new_knower_ids": sorted((with_body | heard) - set(know["authorized"]) - set(know["heard_only"])),
        "new_body_holder_ids": sorted(with_body - set(know["authorized"])),
        "detected": bool(detected_by),
        "detected_by": sorted(detected_by),
        "skipped": skipped,
        "undefined": undefined,
        "leak_risk": prof["leak_risk"],
        "outcome": prof["outcome"],
        "knowledge_after": after,
        "authority": {aid: can_act(state, aid) for aid in sorted(with_body | heard)},
    }
