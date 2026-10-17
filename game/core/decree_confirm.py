# -*- coding: utf-8 -*-
"""B5-4 · 口谕复述确认 ＋ 同旨补录（**同一 `decree_id` 不重复执行**）

规格：`market-civilian-economy` §7 B5-4
「口谕补**复述确认** ＋ 同旨补录（**同一 `decree_id` 不重复执行**）」。

要补的是两个缺口，都不是"再加一个乘数"：

1. **领旨即执行**：此前 `commands_decree.issue_kouyu` / `issue_secret_decree` 把旨意丢进队列，
   月度结算直接 `_apply_decree_effect`，**受命人从未有机会说他听见的是什么**。
   本模块要求：**先复述、后承办**——没有可查的复述记录就没有确认，没有确认就不予承办。
2. **重下/重试会二次生效**：补录、重下旨、月度结算重入都可能对同一道旨再走一遍效果。
   本模块用**执行台账**把"这道 `decree_id` 已经怎样了"钉死，**只生效一次**。

---

## 一、复述口径（比的是什么）

复述是**结构化复述**：受命人把旨意拆成若干**要素**逐项说回来，本模块逐项比对
（`ELEMENTS`，口径单点，只此一处）：

| 要素 | 取自原旨的哪一处 | 比对口径 |
|---|---|---|
| `title` | `decree["title"]` | 归一空白后的**全等** |
| `body` | `body`/`desc`/`text`/`content` 首个非空 | 归一空白后的**全等** |
| `effects` | `decree["effects"]` | 键集合相同 ∧ 逐值数值归一后相等（`300000` == `300000.0`） |
| `visibility` | `is_secret`/`is_zhongzhi` → `公`/`密`/`中旨` | **全等** |
| `delivery` | `delivery`/`category`（诏令·密旨·中旨·口谕…） | **全等** |
| `addressees` | `addressees`/`target`/`targets` | 名单**集合相等**（缺 `decree` 未声明 → `None`） |

**刻意不做语义相似度猜测**：本模块没有"看起来差不多就算一致"的档位
（`KOUYU_DRIFT_CHANCE` 那种"假装弱效/走样"正是 B5-4 要废除的）。
调用方（AI 文案、玩家自撰）给出的复述若与原旨要素有一处对不上，
就是 `mismatch`，**逐项列出差在哪**，交人裁断，不静默通过。

`compose_recitation()` 可由程序按原旨生成一份标准复述（首次下旨时用），
它按构造必然一致——它的一致性来自"照抄原旨"，不来自"判定宽容"。

---

## 二、四态语义

`confirm_decree(...)["status"]` ∈ `STATUSES`，**互斥且穷尽**：

| 态 | 含义 | 判据 | 是否可承办 |
|---|---|---|---|
| `confirmed` | 已复述，且**逐要素与原旨一致**，且此人有权 | 比较全过 ＋ `can_act` 通过 ＋ 是受命人 | ✅ |
| `mismatch` | 有复述，但**与原旨不符**（含**漏复述**某要素、复述出原旨没有的要素） | `mismatched`/`missing`/`unsupported` 任一非空 | ❌ |
| `unauthorized` | 此人**无权/非受命人/不在名册** | `can_act` 失败（`unknown_actor`/`not_in_office`/`no_authority`）或 `not_addressee` | ❌ |
| `undefined` | **读数缺失**，不判 | 原旨查不到 / 权限 `None`（`authority_undefined`）/ 尚未复述 / 复述记录读不出要素 | ❌ |

**缺失 ≠ 0 ≠ 1.0 的落点**（本模块最要紧的一条）：

- 没复述 → `undefined`/`not_recited`，**不是** `confirmed`；
- 空复述 `{}` → 所有应有要素进 `missing` → `mismatch`，**不是** "复述了等于没复述所以过"；
- 权限 `None` → `undefined`/`authority_undefined`，**既不**按"有权"放行、
  **也不**按"无权"驳回（与 `minister_agent.can_act` 同口径，本模块只转述其裁决）；
- 原旨查不到 → `undefined`/`unknown_decree`，**不凭空造一道旨**去比对。

`unauthorized` 一支**不返回原旨内容**（`elements=[]`、`withheld=True`）：
未获授权者拿不到"这道旨说了什么"的读数，避免确认接口变成密旨泄露旁路。

---

## 三、幂等落点与跨回合保证

**两层落点，都是既有存档结构，不新增任何 `state.*` 属性**
（`save_load.py` 有白名单，新增字段必丢档）：

| 落什么 | 落在哪 | 为什么是它 |
|---|---|---|
| **复述记录**（他说了什么） | `state.minister_agents[aid].memory` 里 `kind="复述"`、`source="旨意:<id>·复述"` 的条目——**只经 `core.domains.administration.minister_agent.remember/recall`** | 逐人隔离（甲的复述不是乙亲闻）；`save_load` 逐条保留 `memory` 原样，读档后仍在 |
| **执行台账**（这道旨执行过没有、执行成什么样） | `state.statistics["decree_exec_ledger"]`：`{decree_id: {turn, by, digest, outcome, …}}` | `statistics` 在存档白名单内且**逐字往返**（`save_load:213` 存 / `:612` 读），无需改 `save_load.py` |

`core/minister_agent.py` **只读复用**（`can_act` / `recall` / `remember`）：
本模块**不复制**记忆与权限逻辑、**不另建人物表**（复用 `content.ministers.data.MINISTERS`）、
**不改**该文件。

**跨回合保证**：`backfill_decree()` 的裁决只依赖上面两层。下一回合（或读档后）再对同一
`decree_id` 补录，命中台账即返回 `replay=True`、`applied=False`，
并**如实转述首次的 `outcome`**（不重算、不重跑、不改写历史结论）。

**先占位后执行**：`backfill_decree` 拿到确认后**先把台账写成 `claimed`**，再调执行器。
这样即使执行途中崩溃/存档中断，重进也只会看到 `claimed` 而**不会二次执行**
（宁可不重复，不可重复执行）。`claimed` **不自动重试**，由调用方显式处置。

---

## 四、纪律

- **读数不改 state**：`canonical_decree` / `compose_recitation` / `render_recitation` /
  `compare_recitation` / `confirm_decree(..., record=False)` / `recitations_of` /
  `execution_of` / `backfill_candidates` **全是纯读数**；写路径只有两个：
  `record_recitation()`（写复述——`confirm_decree(record=True)` 是它的受控入口）
  与 `backfill_decree()`（先复述、再写台账）。其余一律不碰 `state`。
- **拒绝式**（不静默放行）：空 `decree_id`/`actor_id`、非对象的 `decree`/`recitation`、
  复述含未知要素、不可调用的 `executor` 一律 `ValueError`。
- **不代数值落地**：本模块**不碰钱粮与人口**（POP 挂载律），只管"能不能承办 / 办没办过"。
  `executor` 由调用方（`settlement`/`commands`）注入，**口径仍在既有通道**；
  不给 `executor` 时记 `registered_only`——只落幂等身份，数值仍走原路径。
- 参数名用 `pref` 语义（行政区）；**不用 `route`**（仓库里 `route` ＝外邦行军路线）。
- 本模块**不自行接线**到 `commands_decree.py` / `settlement_decree.py`（由 Lead 统一接）。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Dict, List, Optional

from content.ministers.data import MINISTERS
from core.domains.administration.minister_agent import can_act, recall, remember

__all__ = [
    "DECREE_CONFIRM_SCHEMA_VERSION", "LEDGER_STAT_KEY",
    "STATUS_CONFIRMED", "STATUS_MISMATCH", "STATUS_UNAUTHORIZED", "STATUS_UNDEFINED", "STATUS_VETO",
    "STATUSES", "OUTCOME_EXECUTED", "OUTCOME_REGISTERED_ONLY", "OUTCOME_FAILED",
    "OUTCOME_CLAIMED", "OUTCOME_VETOED", "OUTCOMES",
    "MEMORY_KIND_RECITE", "RECITE_SOURCE_PREFIX", "RECITE_SEP", "RECITE_HEAD",
    "ELEMENTS", "READABLE_MAX", "DECREE_QUEUES",
    "recite_source", "decree_id_of", "ensure_decree_id", "decree_of", "addressees_of",
    "canonical_decree", "decree_digest", "compose_recitation", "render_recitation",
    "record_recitation", "recitations_of", "latest_recitation",
    "compare_recitation", "confirm_decree",
    "exec_ledger_of", "execution_of", "record_execution", "backfill_decree", "backfill_candidates",
]

#: 本模块落档读数的结构版本（随 `decree_exec_ledger` 条目一起持久）
DECREE_CONFIRM_SCHEMA_VERSION = 1

#: **执行台账的落点**：`state.statistics` 下的一个子表。
#: 选它是因为它在 `save_load` 白名单内且逐字往返（存 `save_load:213` / 读 `:612`），
#: 本模块**不新增 `state.*` 属性**、**不改 `save_load.py`**。
LEDGER_STAT_KEY = "decree_exec_ledger"

# ============================================================
# 四态 / 四结果（口径常量）
# ============================================================
STATUS_CONFIRMED = "confirmed"          # 已复述且与原旨一致
STATUS_MISMATCH = "mismatch"            # 有复述但与原旨不符（含漏复述）
STATUS_UNAUTHORIZED = "unauthorized"    # 无权 / 非受命人 / 不在名册
STATUS_UNDEFINED = "undefined"          # 读数缺失，不判
STATUS_VETO = "veto"                    # 大臣力谏 / 给事中封还词头拒不奉诏
STATUSES = (STATUS_CONFIRMED, STATUS_MISMATCH, STATUS_UNAUTHORIZED, STATUS_UNDEFINED)

OUTCOME_EXECUTED = "executed"              # 已调执行器并成功返回
OUTCOME_REGISTERED_ONLY = "registered_only"  # 只落幂等身份，数值留给既有通道
OUTCOME_FAILED = "failed"                  # 执行器报错（已如实记账，不自动重试）
OUTCOME_CLAIMED = "claimed"                # 已占位未完成（崩溃留痕，不再执行第二次）
OUTCOME_VETOED = "vetoed"                  # 遭封驳停滞（已如实记账，不自动重试）
OUTCOMES = (OUTCOME_EXECUTED, OUTCOME_REGISTERED_ONLY,
            OUTCOME_FAILED, OUTCOME_CLAIMED)

# ============================================================
# 复述记录的记忆口径（与 `core/minister_agent` 的落档方式对齐）
# ============================================================
MEMORY_KIND_RECITE = "复述"        # 记忆条目的 kind
RECITE_SOURCE_PREFIX = "旨意:"     # source 前缀（可回放"这道旨是谁复述的"）
RECITE_HEAD = "〔复述〕"            # 正文可读前缀
RECITE_SEP = "‖"                   # 可读句与结构化部分的分隔符（取最后一个切分）
READABLE_MAX = 240                 # 可读句截断长度（结构化部分不截断，比对不丢真）

#: 复述要素（**口径单点**：只有这一处决定"复述要复述什么"）
ELEMENTS = ("title", "body", "effects", "visibility", "delivery", "addressees")

#: 诏令队列（查原旨与列待补录清单都按此顺序；都是既有存档结构）
DECREE_QUEUES = ("pending_decrees", "pending_secret_decrees", "active_decrees")

_WS = re.compile(r"\s+")


# ============================================================
# 内部：归一与解析
# ============================================================
def _req_id(v: Any, field: str) -> str:
    """非空标识（拒绝式：不臆造无名之旨 / 无名之官）。"""
    s = str(v if v is not None else "").strip()
    if not s:
        raise ValueError(f"{field} 不能为空（拒绝式）")
    return s


def _norm_text(v: Any) -> Optional[str]:
    """文本归一：去首尾、连续空白折一格；空 → `None`（缺失不作空串）。"""
    if not isinstance(v, str):
        return None
    t = _WS.sub(" ", v).strip()
    return t or None


def _canon_scalar(v: Any) -> Any:
    """效果值归一：数值取有限数（int/float 归一）；字符串去空白；其余原样。"""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        f = float(v)
        return round(f, 6) if math.isfinite(f) else None
    if isinstance(v, str):
        return _norm_text(v)
    return v


def _canon_effects(raw: Any) -> Optional[Dict[str, Any]]:
    """效果契约归一：键去空白并排序；非有限值落 `None`（不猜值）；空表 → `None`。"""
    if not isinstance(raw, dict) or not raw:
        return None
    out: Dict[str, Any] = {}
    for k, v in raw.items():
        key = str(k).strip()
        if not key:
            continue
        out[key] = _canon_scalar(v)
    return {k: out[k] for k in sorted(out)} or None


def _visibility_of(decree: Dict[str, Any]) -> Optional[str]:
    """可见性要素：`公` / `密` / `中旨`；原旨未声明 → `None`。"""
    v = _norm_text(decree.get("visibility"))
    if v:
        return v
    if "is_secret" in decree:
        if decree.get("is_secret"):
            return "中旨" if decree.get("is_zhongzhi") else "密"
        return "公"
    if decree.get("is_zhongzhi"):
        return "中旨"
    return None


def _first_text(decree: Dict[str, Any], keys) -> Optional[str]:
    for k in keys:
        v = _norm_text(decree.get(k))
        if v:
            return v
    return None


# ============================================================
# ① 原旨定位与规范化（纯读数）
# ============================================================
def decree_id_of(decree: Any) -> str:
    """取 `decree_id`；依次退 `id` → `task_id` → `title`；都没有 → `""`（缺失≠占位）。"""
    if isinstance(decree, dict):
        for k in ("decree_id", "id", "task_id", "title"):
            v = _norm_text(decree.get(k))
            if v:
                return v
        return ""
    return _norm_text(decree) or ""


def ensure_decree_id(state, decree: Dict[str, Any]) -> str:
    """**单点**：为旨意补齐确定性 `decree_id`，**就地写回**并返回。

    为什么需要（2026-11 实测缺陷）：`commands_decree` 的四条下旨路径
    （`issue_decree` / `issue_secret_decree` / `issue_kouyu` / `issue_edict_from_review`）
    **从不写 `decree_id` 也不写 `id`**，导致——
      - B5-5 `settlement_decree` 的 `if _did:` 恒假 ⇒ **密令泄露推演从未执行**；
      - `_secret_contacts` 恒返回 `[]`；
      - 去重集合`{d.get("id")}` 恒为空；
      - B5-4 的幂等锚缺失，同一旨意可被重复执行。

    口径（**必须确定性**）：
    - 已有 `decree_id` / `id` / `task_id` → 直接沿用（兼容旧档，**不得覆盖**）；
    - 否则 `"d{turn}-{n}"`，`n` 为该回合已占号 +1，**就地写入**；
    - ⚠️ **不含随机数与时间戳**——否则重读档得到不同 id，幂等立即失效。
    调用方应在**下达那一刻**调用（本函数是幂等锚的所有者；
    晚于此时才补会让此前按`title` 建立的知情范围查不到）。
    """
    if not isinstance(decree, dict):
        return ""
    for k in ("decree_id", "id", "task_id"):
        v = _norm_text(decree.get(k))
        if v:
            if not _norm_text(decree.get("decree_id")):
                decree["decree_id"] = v
            return v
    turn = int(getattr(state, "turn", 0) or 0)
    used = set()
    for attr in ("pending_decrees", "active_decrees", "pending_secret_decrees"):
        for d in (getattr(state, attr, None) or []):
            if isinstance(d, dict):
                v = _norm_text(d.get("decree_id"))
                if v:
                    used.add(v)
    # ⚠️ **已执行台账里的号也必须避开**：同回合内若"下发→结算消耗→再下发"，
    # 只看队列会让新旨复用旧号⇒ `backfill_decree` 误判为重放而**静默不执行**。
    for v in (exec_ledger_of(state) or {}):
        used.add(_norm_text(v))
    n = 1
    while f"d{turn}-{n}" in used:
        n += 1
    did = f"d{turn}-{n}"
    decree["decree_id"] = did
    return did


def decree_of(state, decree_id: str) -> Optional[Dict[str, Any]]:
    """在既有诏令队列中查原旨；查不到 → `None`（**不凭空造旨**）。

    返回的是队列里的**同一个对象**（只读用）——本模块不写它，调用方也不应改写。
    """
    did = _req_id(decree_id, "decree_id")
    for q in DECREE_QUEUES:
        for d in (getattr(state, q, None) or []):
            if isinstance(d, dict) and decree_id_of(d) == did:
                return d
    return None


def addressees_of(decree: Any) -> Optional[List[str]]:
    """受命人名单；原旨**未声明** → `None`（不猜这道旨该谁办）。"""
    if not isinstance(decree, dict):
        return None
    for k in ("addressees", "受命", "target", "targets"):
        v = decree.get(k)
        if isinstance(v, str):
            v = [v]
        if isinstance(v, (list, tuple, set)):
            names = [n for n in (_norm_text(x) for x in v) if n]
            if names:
                return sorted(set(names))
    return None


def canonical_decree(decree: Any) -> Dict[str, Any]:
    """原旨 → 复述比对基准（**纯派生**，不改 state；不抛"查不到"以外的事）。"""
    if not isinstance(decree, dict):
        raise ValueError("decree 须为对象（拒绝式）")
    return {
        "title": _norm_text(decree.get("title")),
        "body": _first_text(decree, ("body", "desc", "text", "content")),
        "effects": _canon_effects(decree.get("effects")),
        "visibility": _visibility_of(decree),
        "delivery": _norm_text(decree.get("delivery") or decree.get("category")),
        "addressees": addressees_of(decree),
    }


def decree_digest(canonical: Dict[str, Any]) -> str:
    """原旨指纹（sha1 前 12 位）：用来发现"**同一 id、内容却变了**"的重下。"""
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), default=str)
    return "dgc_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


# ============================================================
# ② 复述的生成与呈现
# ============================================================
def compose_recitation(canonical: Dict[str, Any]) -> Dict[str, Any]:
    """按原旨生成**标准复述**（只复述原旨确实写了的要素，不替它添内容）。"""
    if not isinstance(canonical, dict):
        raise ValueError("canonical 须为对象（拒绝式）")
    return {k: canonical[k] for k in ELEMENTS if canonical.get(k) is not None}


def _fmt(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def render_recitation(elements: Any) -> str:
    """复述 → 一句可读文言（供面板/叙事；**不**参与比对）。"""
    if not isinstance(elements, dict):
        return ""
    bits: List[str] = []
    if elements.get("title"):
        bits.append("题「%s」" % elements["title"])
    if elements.get("body"):
        bits.append("旨「%s」" % elements["body"])
    eff = elements.get("effects")
    if isinstance(eff, dict) and eff:
        bits.append("效 " + "、".join("%s=%s" % (k, _fmt(eff[k])) for k in sorted(eff)))
    if elements.get("visibility"):
        bits.append("见%s" % elements["visibility"])
    if elements.get("delivery"):
        bits.append("由%s" % elements["delivery"])
    ads = elements.get("addressees")
    if isinstance(ads, list) and ads:
        bits.append("命 " + "、".join(ads))
    return "；".join(bits)


def recite_source(decree_id: str) -> str:
    """复述记录的 `source`（可按它把"这道旨的复述"整串捞出来）。"""
    return "%s%s·复述" % (RECITE_SOURCE_PREFIX, _req_id(decree_id, "decree_id"))


def _parse_recitation(raw: Any) -> tuple:
    """复述正文 → (要素dict, 是否可读)。**读不出就报读不出**，不猜。"""
    if not isinstance(raw, str) or RECITE_SEP not in raw:
        return None, False
    tail = raw.rpartition(RECITE_SEP)[2]
    try:
        data = json.loads(tail)
    except (TypeError, ValueError):
        return None, False
    if not isinstance(data, dict):
        return None, False
    clean: Dict[str, Any] = {}
    for k, v in data.items():
        if k not in ELEMENTS or v is None:
            return None, False          # 记录被改过 → 不可信（不静默丢键）
        clean[k] = v
    return clean, True


# ============================================================
# ③ 复述记录：写（经 minister_agent）＋ 读（只读本人自己的）
# ============================================================
def record_recitation(state, decree_id: str, actor_id: str, elements: Any, *,
                      turn: Optional[int] = None) -> Dict[str, Any]:
    """把**该人自己**的复述落进他自己的记忆（`minister_agent.remember`）。

    本模块唯一的复述写入口；官员侧的记忆结构、权限、逐人隔离**一律由
    `core/minister_agent` 负责**，本模块不复制、不另立人物状态。
    """
    did = _req_id(decree_id, "decree_id")
    aid = _req_id(actor_id, "actor_id")
    if not isinstance(elements, dict):
        raise ValueError("复述要素须为对象（拒绝式）")
    unknown = sorted(set(map(str, elements)) - set(ELEMENTS))
    if unknown:
        raise ValueError("复述含未知要素 %s（允许：%s）" % ("、".join(unknown), "、".join(ELEMENTS)))
    clean = {k: v for k, v in elements.items() if v is not None}
    readable = render_recitation(clean)
    if len(readable) > READABLE_MAX:
        readable = readable[:READABLE_MAX] + "…"
    text = "%s%s%s%s" % (RECITE_HEAD, readable, RECITE_SEP,
                         json.dumps(clean, ensure_ascii=False, sort_keys=True))
    t = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))
    entry = remember(state, aid, kind=MEMORY_KIND_RECITE, text=text, turn=t,
                     source=recite_source(did))
    return {"decree_id": did, "actor_id": aid, "turn": t,
            "kind": MEMORY_KIND_RECITE, "source": entry.get("source"),
            "private": bool(entry.get("private", False)),
            "elements": clean, "readable": readable, "text": text}


def recitations_of(state, decree_id: str, actor_id: str) -> List[Dict[str, Any]]:
    """该人**自己**关于此旨的复述记录（**逐人隔离**：只读本人，不看别人的记忆）。

    `readable_parse=False` 表示这条记录读不出要素（记录被改/损坏）——
    **如实报读不出**，不按"复述过"放行。
    """
    did = _req_id(decree_id, "decree_id")
    aid = _req_id(actor_id, "actor_id")
    src = recite_source(did)
    out: List[Dict[str, Any]] = []
    for e in recall(state, aid, kind=MEMORY_KIND_RECITE):
        if not isinstance(e, dict) or str(e.get("source") or "") != src:
            continue
        raw = str(e.get("text") or "")
        parsed, ok = _parse_recitation(raw)
        out.append({
            "decree_id": did, "actor_id": aid,
            "turn": e.get("turn"), "kind": e.get("kind"),
            "source": e.get("source"),
            "private": bool(e.get("private", False)),
            "readable": raw.split(RECITE_SEP)[0] if ok else (_norm_text(raw)),
            "elements": parsed, "readable_parse": ok,
        })
    return out


def latest_recitation(state, decree_id: str, actor_id: str) -> Optional[Dict[str, Any]]:
    """最近一条复述记录；从未复述 → `None`（**不是**"复述过且无异议"）。"""
    rows = recitations_of(state, decree_id, actor_id)
    return rows[-1] if rows else None


# ============================================================
# ④ 逐要素比对（纯读数）
# ============================================================
def _same_value(key: str, exp: Any, rec: Any) -> bool:
    if key == "addressees":
        if not isinstance(exp, (list, tuple, set)) or not isinstance(rec, (list, tuple, set)):
            return False
        return sorted({str(x) for x in exp}) == sorted({str(x) for x in rec})
    if key == "effects":
        a, b = _canon_effects(exp), _canon_effects(rec)
        if a is None or b is None:
            return a is None and b is None
        return json.dumps(a, ensure_ascii=False, sort_keys=True) == \
            json.dumps(b, ensure_ascii=False, sort_keys=True)
    return _norm_text(exp) == _norm_text(rec) and _norm_text(exp) is not None


def compare_recitation(expected: Any, recited: Any) -> Dict[str, Any]:
    """逐要素比对 → `{ok, elements[], mismatched[], missing[], unsupported[]}`。

    - 原旨**未定义**某要素且复述也未提 → 不要求（`required=False`）；
    - 原旨未定义、复述却添了内容 → `unsupported`（**复述出原旨没有的东西**＝不符）；
    - 原旨有、复述没提 → `missing`（**漏复述**＝不符，不按"无异议"放过）；
    - 原旨有、复述有但值不同 → `mismatched`。
    """
    if not isinstance(expected, dict) or not isinstance(recited, dict):
        raise ValueError("expected/recited 均须为对象（拒绝式）")
    rows: List[Dict[str, Any]] = []
    mismatched: List[str] = []
    missing: List[str] = []
    unsupported: List[str] = []
    for k in ELEMENTS:
        exp = expected.get(k)
        rec = recited.get(k)
        if exp is None:
            ok = rec is None
            note = "原旨未写此项，无需复述" if ok else "原旨未写此项，却复述出了内容"
            required = False
            if not ok:
                unsupported.append(k)
        elif rec is None:
            ok = False
            note = "原旨有此项，复述漏了"
            required = True
            missing.append(k)
        else:
            ok = _same_value(k, exp, rec)
            note = "与原旨一致" if ok else "与原旨不符"
            required = True
            if not ok:
                mismatched.append(k)
        rows.append({"key": k, "required": required, "ok": ok,
                     "expected": exp, "recited": rec, "note": note})
    for k in sorted(set(map(str, recited)) - set(ELEMENTS)):
        # 复述里出现本口径根本不认的要素 → 也是"不符"，不静默忽略
        unsupported.append(k)
    return {"ok": not (mismatched or missing or unsupported), "elements": rows,
            "mismatched": mismatched, "missing": missing,
            "unsupported": sorted(set(unsupported))}


def _check_minister_veto(state, aid: str, decree: Dict[str, Any]) -> Optional[str]:
    """检查大臣是否对该诏令发起封驳力谏（拒不奉诏）。

    判定条件（有史料依据，不凭空捏造）：
    1. 显式指定反对名单或派系；
    2. 派系党争对立（旧党大臣执掌时遇激进新法，或新党遇废罢新法，忠诚度非盲从）；
    3. 恤民力谏（清廉守正大臣遇苛敛搜括、花石纲、造作局等聚敛大作）。
    """
    fig = (MINISTERS or {}).get(aid)
    if not isinstance(fig, dict):
        return None
    fac = str(fig.get("faction") or "")
    traits = str(fig.get("traits") or "")
    tids = set(fig.get("trait_ids") or [])
    loyalty = float(fig.get("loyalty", 0.5) if fig.get("loyalty") is not None else 0.5)

    title = str(decree.get("title") or "")
    cat = str(decree.get("category") or "")

    # 1. 显式反对名单
    if aid in (decree.get("veto_ministers") or []):
        return f"大臣「{aid}」上疏力谏：此旨有害社稷，誓不奉诏"
    if fac and fac in (decree.get("oppose_factions") or []):
        return f"「{fac}」重臣「{aid}」封还词头：党见不合，拒不遵行"

    # 2. 党争对立
    if fac == "旧党" and loyalty < 0.65:
        if cat in ("新法", "变法") or any(k in title for k in ("方田", "市易", "免役", "新法", "青苗", "均输")):
            return f"旧党重臣「{aid}」力谏封驳：新法扰民乱邦，祖宗成宪不可轻变"
    elif fac == "新党" and loyalty < 0.65:
        if any(k in title for k in ("废罢", "罢新法", "复旧制", "罢方田")):
            return f"新党执政「{aid}」抗疏力争：先帝绍述不可中道而废"

    # 3. 恤民抗谏
    if any(t in traits or t in tids for t in ("守正", "清廉", "刚直", "老成")) and loyalty < 0.80:
        if any(k in title for k in ("花石", "造作局", "应奉局", "进奉", "加征", "括田", "搜括")):
            return f"直臣「{aid}」伏阙力谏：搜括赋敛必致民变，乞收回成命"

    return None


# ============================================================
# ⑤ 复述确认（主流程；record=False 时是**纯读数**）
# ============================================================
def confirm_decree(state, decree_id: str, actor_id: str, *, decree: Any = None,
                   recitation: Any = None, record: bool = False,
                   turn: Optional[int] = None) -> Dict[str, Any]:
    """给定 `decree_id` 与受命人 → 四态裁决。

    - `decree` 不给时按 `decree_id` 在既有诏令队列里查（查不到 → `undefined`）；
    - `recitation` 给了 = 调用方/AI 递上来的复述；不给 = 读该人已存的复述记录；
    - `record=True` 才会写复述：**此前一条都没有**时按原旨生成一份标准复述落记
      （照抄原旨，不是"判定宽容"）；**已有记录则不重写**（同旨跨回合不反复"复述一次"）；
    - 已有记录但读不出要素（被改/损坏）→ `undefined`/`recitation_unreadable`，
      **不覆盖、不猜**（宁可要求重新下旨复述，也不拿坏记录冒充已复述）；
    - 未获授权时**不返回原旨内容**（`withheld=True`），避免确认接口变成密旨泄露旁路。
    """
    did = _req_id(decree_id, "decree_id")
    aid = _req_id(actor_id, "actor_id")
    if recitation is not None and not isinstance(recitation, dict):
        raise ValueError("recitation 须为对象（拒绝式：拿不准的自由文本不得当成复述）")
    if decree is not None and not isinstance(decree, dict):
        raise ValueError("decree 须为对象（拒绝式）")
    if record is not True and record is not False:
        raise ValueError("record 须为布尔（拒绝式）")
    t = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))

    out: Dict[str, Any] = {
        "schema_version": DECREE_CONFIRM_SCHEMA_VERSION,
        "decree_id": did, "actor_id": aid, "turn": t,
        "status": None, "reason": "", "message": "",
        "defined": True, "undefined_basis": [],
        "authorized": None, "can_act": None, "in_roster": aid in MINISTERS,
        "addressee_declared": None, "is_addressee": None,
        "recited": False, "recorded": False, "recitation_turn": None,
        "elements": [], "mismatched": [], "missing": [], "unsupported": [],
        "suggested_recitation": None, "withheld": False, "digest": None,
    }

    d = decree if decree is not None else decree_of(state, did)
    if not isinstance(d, dict):
        out.update(status=STATUS_UNDEFINED, reason="unknown_decree", defined=False,
                   undefined_basis=["decree"],
                   message="查无此旨（%s）：无原文可比对，**未复述、未确认**（不作成功）。" % did)
        return out

    canon = canonical_decree(d)
    out["digest"] = decree_digest(canon)
    addr = canon.get("addressees")
    out["addressee_declared"] = addr is not None
    if addr is not None:
        out["is_addressee"] = aid in addr
    if not out["in_roster"]:
        out["undefined_basis"].append("actor_roster")

    gate = can_act(state, aid)
    out["can_act"] = gate
    g_reason = str(gate.get("reason") or "")
    if g_reason == "unknown_actor":
        out.update(status=STATUS_UNAUTHORIZED, reason="unknown_actor", authorized=False,
                   withheld=True,
                   message="「%s」尚无官员 Agent 运行态（未建档），无从领旨确认"
                           "（其在名册与否见 in_roster=%s）。" % (aid, out["in_roster"]))
        return out
    if g_reason == "authority_undefined":
        out.update(status=STATUS_UNDEFINED, reason="authority_undefined", authorized=None,
                   defined=False, undefined_basis=out["undefined_basis"] + ["authority"],
                   withheld=True,
                   message="「%s」权限**未定义**：能否承办未决，"
                           "不得按有权放行、也不得按无权驳回。" % aid)
        return out
    if not gate.get("ok"):
        out.update(status=STATUS_UNAUTHORIZED, reason=g_reason or "no_authority",
                   authorized=False, withheld=True,
                   message="「%s」无权承办此旨（%s），不予确认。" % (aid, g_reason))
        return out
    if addr is not None and aid not in addr:
        out.update(status=STATUS_UNAUTHORIZED, reason="not_addressee", authorized=False,
                   withheld=True,
                   message="此旨受命于「%s」，「%s」非受命人，不得代为确认。"
                           % ("、".join(addr), aid))
        return out

    # 法统门禁守卫：若旨意指定调整制度参数或机构事权，调用 check_authority 深度核验
    effects = d.get("effects") or {}
    if isinstance(effects, dict):
        try:
            from core.domains.administration.institution import check_authority
            for p_key in effects.keys():
                auth_ok, auth_err = check_authority(state, p_key, aid)
                if not auth_ok:
                    out.update(status=STATUS_UNAUTHORIZED, reason="authority_violation",
                               authorized=False, withheld=True,
                               message=f"法统门禁阻断：{auth_err}")
                    return out
        except Exception as e:  # noqa: BLE001
            log.debug("decree_confirm 事权深度校验跳过：%s", e)

    out["authorized"] = True

    stored = latest_recitation(state, did, aid)
    if recitation is not None:
        cand: Optional[Dict[str, Any]] = {"elements": dict(recitation), "origin": "caller",
                                           "turn": t, "record": None}
    elif stored is not None and not stored["readable_parse"]:
        out.update(status=STATUS_UNDEFINED, reason="recitation_unreadable", defined=False,
                   undefined_basis=out["undefined_basis"] + ["recitation"],
                   recited=True,
                   message="「%s」的复述记录在，但读不出其复述了哪些要素（不猜）：须重新下旨复述。"
                           % aid)
        return out
    elif stored is not None:
        cand = {"elements": dict(stored["elements"]), "origin": "record",
                "turn": stored.get("turn"), "record": stored}
    elif record:
        # 首次下旨：按原旨生成**标准复述**并落记（照抄原旨，不靠"判定宽容"蒙混过关）
        cand = {"elements": compose_recitation(canon), "origin": "caller",
                "turn": t, "record": None}
    else:
        cand = None

    if cand is None:
        out.update(status=STATUS_UNDEFINED, reason="not_recited", defined=False,
                   undefined_basis=out["undefined_basis"] + ["recitation"],
                   recited=False, suggested_recitation=compose_recitation(canon),
                   message="「%s」尚未复述此旨：**未确认**（缺失≠确认），"
                           "须先留下复述记录方可承办。" % aid)
        return out

    if record:
        if cand["origin"] == "caller":
            saved = record_recitation(state, did, aid, cand["elements"], turn=t)
            out["recorded"] = True
            out["recitation_turn"] = saved["turn"]
        else:
            # 已有记录：**不重复写**（同一道旨跨回合不反复"复述一次"）
            out["recorded"] = False
            out["recitation_turn"] = cand.get("turn")
        out["recited"] = True
    else:
        out["recited"] = cand["origin"] == "record"
        out["recitation_turn"] = cand.get("turn")

    cmp_ = compare_recitation(canon, cand["elements"])
    out["elements"] = cmp_["elements"]
    out["mismatched"] = cmp_["mismatched"]
    out["missing"] = cmp_["missing"]
    out["unsupported"] = cmp_["unsupported"]
    if cmp_["ok"]:
        veto_reason = _check_minister_veto(state, aid, d)
        if veto_reason and not (d.get("override_by_sovereign") or d.get("is_zhongzhi") or d.get("is_direct")):
            out.update(status=STATUS_VETO, reason="minister_veto",
                       veto_reason=veto_reason,
                       message="「%s」封还词头拒不奉诏（%s）：不予承办。" % (aid, veto_reason))
        else:
            if veto_reason:
                out["overridden_by_sovereign"] = True
                out["sovereign_prestige_cost"] = 3
            out.update(status=STATUS_CONFIRMED, reason="recitation_matches",
                       message="「%s」已复述此旨，要素与原旨一致：可以承办。" % aid)
    else:
        bad = (cmp_["mismatched"] + cmp_["missing"] + cmp_["unsupported"])
        out.update(status=STATUS_MISMATCH, reason="recitation_diverges",
                   message="「%s」的复述与原旨不符（%s）：不予确认，不得据此承办。"
                           % (aid, "、".join(bad) or "未列明"))
    return out


# ============================================================
# ⑥ 执行台账（幂等锚）——`exec_ledger_of`/`execution_of` 是**纯读数**
# ============================================================
def exec_ledger_of(state) -> Dict[str, Any]:
    """读执行台账；**不写**（不因读而凭空造出 `state.statistics` 的新键）。"""
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        return {}
    led = stats.get(LEDGER_STAT_KEY)
    return led if isinstance(led, dict) else {}


def execution_of(state, decree_id: str) -> Optional[Dict[str, Any]]:
    """该 `decree_id` 的执行记录（**副本**，调用方改它不污染台账）；未执行 → `None`。"""
    did = _req_id(decree_id, "decree_id")
    rec = exec_ledger_of(state).get(did)
    return dict(rec) if isinstance(rec, dict) else None


def record_execution(state, decree_id: str, *,
                     by: str = "朝廷",
                     digest: Optional[str] = None,
                     title: Optional[str] = None,
                     confirm_status: str = STATUS_CONFIRMED,
                     outcome: str = OUTCOME_EXECUTED,
                     recitation_turn: Optional[int] = None,
                     turn: Optional[int] = None,
                     detail: Optional[str] = None,
                     error: Optional[str] = None) -> Dict[str, Any]:
    """向执行台账（state.statistics[LEDGER_STAT_KEY]）登记执行结果（口径单点）。

    供生产结算链（settlement_decree）在诏令执行完成或受阻时受控写入，
    确保同一 decree_id 拥有可追溯、防重放的权威台账。
    """
    did = _req_id(decree_id, "decree_id")
    t = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))
    entry: Dict[str, Any] = {
        "schema_version": DECREE_CONFIRM_SCHEMA_VERSION,
        "decree_id": did,
        "turn": t,
        "by": str(by or "朝廷").strip(),
        "digest": digest,
        "title": title,
        "confirm_status": confirm_status,
        "recitation_turn": recitation_turn if recitation_turn is not None else t,
        "outcome": outcome,
    }
    if detail:
        entry["detail"] = str(detail)[:200]
    if error:
        entry["error"] = str(error)[:100]
    led = _ledger_mut(state)
    led[did] = dict(entry)
    return entry


def _ledger_mut(state) -> Dict[str, Any]:
    """取（必要时初始化）执行台账——**唯一的台账写入口**。"""
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict):
        stats = {}
        state.statistics = stats
    led = stats.get(LEDGER_STAT_KEY)
    if not isinstance(led, dict):
        led = {}
        stats[LEDGER_STAT_KEY] = led
    return led


def backfill_candidates(state) -> List[Dict[str, Any]]:
    """队列里**尚无执行记录**的旨意（漏记/漏执行者）——纯读数，供月度结算逐条补录。"""
    led = exec_ledger_of(state)
    out: List[Dict[str, Any]] = []
    for q in DECREE_QUEUES:
        for d in (getattr(state, q, None) or []):
            if not isinstance(d, dict):
                continue
            did = decree_id_of(d)
            if not did or did in led:
                continue
            out.append({"decree_id": did, "queue": q,
                        "title": _norm_text(d.get("title")),
                        "turn_issued": d.get("turn_issued"),
                        "addressees": addressees_of(d),
                        "executed": False})
    return out


# ============================================================
# ⑦ 同旨补录（回补）：**同一 decree_id 只生效一次**
# ============================================================
def backfill_decree(state, decree: Any, actor_id: str, *,
                    executor: Any = None, recitation: Any = None,
                    turn: Optional[int] = None) -> Dict[str, Any]:
    """补录/回补一道旨意：先复述确认，再执行；**同一 `decree_id` 第二次只回报首次结果**。

    - 命中台账 → `applied=False`、`replay=True`，**不调执行器**，并把首次的
      `outcome`/`turn`/`by` **如实转述**（不重算、不改写历史结论）；
    - 未命中 → 走 `confirm_decree(record=True)`；非 `confirmed` 一律**不执行、不记账**，
      可在复述改正后重试（台账不占位）；
    - 确认通过 → **先占位 `claimed`** 再调 `executor`（崩溃也不会二次执行）；
      `executor` 报错 → 记 `failed` 并**如实回报**，**不自动重试**（是否重做由人决定）。

    `applied=True` 指的是「本次补录在台账上生效」；`outcome=registered_only` 时
    数值**尚未**落地（仍由调用方的既有通道负责），别读成「已执行完」——看 `outcome`。
    """
    aid = _req_id(actor_id, "actor_id")
    if executor is not None and not callable(executor):
        raise ValueError("executor 须可调用（拒绝式）")
    t = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))

    if isinstance(decree, str):
        d = decree_of(state, decree)
        did = _req_id(decree, "decree_id")
    elif isinstance(decree, dict):
        d = decree
        did = decree_id_of(decree)
        if not did:
            raise ValueError("decree 须有 decree_id/id/title（拒绝式：无名之旨无法界定幂等）")
    else:
        raise ValueError("decree 须为对象或 decree_id 字符串（拒绝式）")

    base: Dict[str, Any] = {
        "decree_id": did, "actor_id": aid, "turn": t,
        "applied": False, "idempotent": True, "replay": False,
        "status": None, "blocked_by": None, "outcome": None,
        "first": None, "confirm": None, "digest_changed": None, "message": "",
    }

    prev = execution_of(state, did)
    if prev is not None:
        prev_digest = prev.get("digest")
        base.update(replay=True, status=prev.get("confirm_status"),
                    outcome=prev.get("outcome"), first=prev,
                    digest_changed=(None if not isinstance(prev_digest, str)
                                    else decree_digest(canonical_decree(d)) != prev_digest)
                    if isinstance(d, dict) else None)
        drift = "（**注意：同一 id 的内容已变**，仍按 id 幂等、不再执行）" if base["digest_changed"] else ""
        base["message"] = ("此旨（%s）已于第 %s 回合由「%s」执行过（首次结果：%s）："
                           "**不重复执行**。%s"
                           % (did, prev.get("turn"), prev.get("by"),
                              prev.get("outcome"), drift))
        return base

    if not isinstance(d, dict):
        base.update(status=STATUS_UNDEFINED, blocked_by="unknown_decree",
                    message="查无此旨（%s）：无原文可比对，**不执行、不记账**。" % did)
        base["confirm"] = confirm_decree(state, did, aid, decree=None, turn=t)
        return base

    canon = canonical_decree(d)
    conf = confirm_decree(state, did, aid, decree=d, recitation=recitation,
                          record=True, turn=t)
    base["confirm"] = conf
    base["status"] = conf["status"]
    if conf["status"] != STATUS_CONFIRMED:
        base.update(blocked_by=conf["status"],
                    message="复述确认未过（%s）：**不执行、不记账**。%s"
                            % (conf["status"], conf["message"]))
        return base

    entry: Dict[str, Any] = {
        "schema_version": DECREE_CONFIRM_SCHEMA_VERSION,
        "decree_id": did, "turn": t, "by": aid,
        "digest": conf["digest"], "title": canon.get("title"),
        "confirm_status": STATUS_CONFIRMED,
        "recitation_turn": conf["recitation_turn"],
        "outcome": OUTCOME_CLAIMED,
    }
    led = _ledger_mut(state)
    led[did] = dict(entry)                 # 先占位：中途崩溃也只会看到 claimed
    if executor is None:
        entry["outcome"] = OUTCOME_REGISTERED_ONLY
        entry["detail"] = "未派执行器：只登记幂等身份，数值落地由既有通道按原口径执行"
    else:
        try:
            res = executor(state, d)
            entry["outcome"] = OUTCOME_EXECUTED
            if isinstance(res, str) and res.strip():
                entry["detail"] = res.strip()
        except Exception as e:            # noqa: BLE001 — 执行器报错不得静默、也不得重跑
            entry["outcome"] = OUTCOME_FAILED
            entry["error"] = type(e).__name__
            entry["error_detail"] = str(e)[:200]
            entry["detail"] = "执行器报错（已记账，**不自动重试**，是否重做由人决定）"
    led[did] = dict(entry)

    base.update(idempotent=False, outcome=entry["outcome"], first=dict(entry),
                applied=entry["outcome"] in (OUTCOME_EXECUTED, OUTCOME_REGISTERED_ONLY),
                message=("此旨（%s）已补录并执行：%s。" % (did, entry["outcome"])
                         if base["applied"] else
                         "此旨（%s）已补录，但执行未成（%s）：已记账，不自动重试。"
                         % (did, entry["outcome"])))
    return base
