# -*- coding: utf-8 -*-
"""官制 × POP 的单一权威源（宋代官制与三冗设计 §13.3/§13.4/§13.5）。

## 为什么要这个模块

审查实证的双账缺陷：`prefectures[].officials`（开局 `户数 × 0.00135` 派生后**永不变化**）
与 `pops["官僚"].size`（随科举/裁汰流动）是**两本账**。30 个月实跑：官僚 POP **+23.1%**，
而 `officials` **+0.0%** —— 于是"养更多官、一分钱不多花"，冗官机制无从承载。

## 本模块的角色（POP 挂载律）

- **唯一人头账 = `pops["官僚"]`**。本模块只做三件事：**派生读**、**受控流动**、**镜像同步**。
- 子池结构（官/吏分账，见 §13.4——原 `×9` 混装是错的）：

```
pops["官僚"] = {
  "size": N,              # == officials + clerks        （不变量 ①）
  "officials": N1,        # 官（身份子池）
  "clerks":    N2,        # 吏（身份子池）
  "on_post":   N1a,       # 官·在岗（有差遣）→ 全俸      ┐
  "waiting":   N1b,       # 官·待阙（守选）  → 半俸      ├ Σ == officials（不变量 ②）
  "sinecure":  N1c,       # 官·祠禄（宫观官）→ 折俸      ┘
  "wealth": ..., "grain": ...,
}
```

- `state.rank_officials` / `clerks_total` / `awaiting_posts` / `sinecure_officials` 等**只读派生视图**
  由 `GameState` 上的方法提供，**不落存量字段**。

## 与旧字段的关系（`prefectures[].officials` / `[].clerks`）

Rust 并行后端（`songzuo_server/src/settle.rs`）与旧存档仍按**人头**读这两个字段，故保留为
**派生镜像**：由 `sync_legacy_mirror()` 在每月结算末**唯一写入**，任何其他代码**不得写**它们。
等价的付款权数另镜像为 `p["official_units"]`（在岗 1.0 / 待阙 0.5 / 祠禄 0.5），
供后续把子池计价同步进 Rust（**已知并行后端平价缺口**：Rust 目前仍按人头 × 全俸估算官俸）。
"""
from typing import Any, Dict, Optional, Tuple

from content.data import (
    CLERK_PER_OFFICIAL, OFFICIAL_SUB_KEYS, SINECURE_PAY_RATIO, WAITING_PAY_RATIO,
)

POP_CLASS = "官僚"


# ---------------------------------------------------------------- 初始化 / 修复
def ensure_subpools(pref: Dict[str, Any]) -> bool:
    """幂等地补齐某路的官僚 POP 子池（旧档迁移 / 缺字段修复）。

    返回是否发生过写入。迁移口径（§六）：
      `officials = 旧 p["officials"]`（无则 `round(size / (1+CLERK_PER_OFFICIAL))`）
      `clerks    = size - officials`（优先取旧 `p["clerks"]`，再钳到非负）
      `on_post = officials`，`waiting = sinecure = 0`（旧档无待阙/祠禄概念）
    """
    pops = pref.get("pops") or {}
    pop = pops.get(POP_CLASS)
    if not isinstance(pop, dict):
        return False

    size = max(0, int(pop.get("size", 0) or 0))
    changed = False

    if "officials" not in pop:
        legacy = pref.get("officials")
        if legacy is None:
            legacy = round(size / (1 + CLERK_PER_OFFICIAL))
        pop["officials"] = max(0, int(legacy))
        changed = True
    if "clerks" not in pop:
        legacy = pref.get("clerks")
        if legacy is None:
            legacy = size - int(pop["officials"])
        pop["clerks"] = max(0, int(legacy))
        changed = True

    off = int(pop["officials"])
    cle = int(pop["clerks"])

    # size 是权威；子池之和若与 size 不符，以 size 为准重新分摊（保持官/吏比例）
    if off + cle != size:
        tot = off + cle
        if tot > 0:
            new_off = round(size * off / tot)
        else:
            new_off = round(size / (1 + CLERK_PER_OFFICIAL))
        new_off = max(0, min(size, int(new_off)))
        pop["officials"], pop["clerks"] = new_off, size - new_off
        off, cle = pop["officials"], pop["clerks"]
        changed = True

    for key in ("on_post", "waiting", "sinecure"):
        if key not in pop:
            pop[key] = off if key == "on_post" else 0
            changed = True

    # 不变量 ②：三池之和 == officials。以 officials 为准重摊。
    s = int(pop["on_post"]) + int(pop["waiting"]) + int(pop["sinecure"])
    if s != off:
        pop["on_post"], pop["waiting"], pop["sinecure"] = off, 0, 0
        changed = True
    for key in OFFICIAL_SUB_KEYS:
        if int(pop.get(key, 0)) < 0:
            pop[key] = 0
            changed = True
    return changed


def ensure_all(state) -> int:
    """对全国各路补齐子池，返回修复的路数。"""
    fixed = 0
    for p in state.prefectures.values():
        if ensure_subpools(p):
            fixed += 1
    return fixed


# ---------------------------------------------------------------- 派生读（只读）
def route_officials(pref: Dict[str, Any]) -> int:
    """本路官数（派生读）。POP 优先；旧档缺子池时回落到旧字段。"""
    pop = (pref.get("pops") or {}).get(POP_CLASS) or {}
    if "officials" in pop:
        return max(0, int(pop.get("officials", 0) or 0))
    return max(0, int(pref.get("officials", 0) or 0))


def route_clerks(pref: Dict[str, Any]) -> int:
    """本路吏数（派生读）。"""
    pop = (pref.get("pops") or {}).get(POP_CLASS) or {}
    if "clerks" in pop:
        return max(0, int(pop.get("clerks", 0) or 0))
    return max(0, int(pref.get("clerks", 0) or 0))


def route_pay_units(pref: Dict[str, Any]) -> float:
    """本路**官·付款权数**：在岗 1.0、待阙 WAITING_PAY_RATIO、祠禄 SINECURE_PAY_RATIO。

    这是官俸总额的真正乘数——「待阙堆成山」也要花钱，只是花半俸（§13.6）。
    """
    pop = (pref.get("pops") or {}).get(POP_CLASS) or {}
    if not any(k in pop for k in ("on_post", "waiting", "sinecure")):
        return float(route_officials(pref))          # 旧档无子池：按全部在岗计价
    return (float(pop.get("on_post", 0) or 0)
            + float(pop.get("waiting", 0) or 0) * WAITING_PAY_RATIO
            + float(pop.get("sinecure", 0) or 0) * SINECURE_PAY_RATIO)


def subpool(pref: Dict[str, Any], key: str) -> int:
    pop = (pref.get("pops") or {}).get(POP_CLASS) or {}
    return max(0, int(pop.get(key, 0) or 0))


# ---------------------------------------------------------------- 全国派生视图
def totals(state) -> Dict[str, int]:
    """全国官制派生视图（面板/统计用，不落存量字段）。"""
    out = {"officials": 0, "clerks": 0, "on_post": 0, "waiting": 0, "sinecure": 0, "size": 0}
    for p in state.prefectures.values():
        out["officials"] += route_officials(p)
        out["clerks"] += route_clerks(p)
        out["on_post"] += subpool(p, "on_post")
        out["waiting"] += subpool(p, "waiting")
        out["sinecure"] += subpool(p, "sinecure")
        out["size"] += int(((p.get("pops") or {}).get(POP_CLASS) or {}).get("size", 0) or 0)
    return out


# ---------------------------------------------------------------- 受控流动（迁入/迁出）
def add_officials(pref: Dict[str, Any], n: int, pool: str = "waiting") -> int:
    """新增 `n` 名官入本路官僚 POP，默认落入 `waiting`（待阙）——新科进士不会立刻有差遣。

    `pool ∈ {"on_post", "waiting", "sinecure"}`。返回实际新增数。
    调用方负责**对手方**的 POP 减少（农/士绅迁出）或显式的人丁自然增减，以保 ΣPOP 守恒。
    """
    n = int(n)
    if n <= 0:
        return 0
    pop = (pref.get("pops") or {}).get(POP_CLASS)
    if not isinstance(pop, dict):
        return 0
    ensure_subpools(pref)
    if pool not in ("on_post", "waiting", "sinecure"):
        pool = "waiting"
    pop["officials"] = int(pop["officials"]) + n
    pop[pool] = int(pop[pool]) + n
    pop["size"] = int(pop["size"]) + n
    return n


def remove_officials(pref: Dict[str, Any], n: int, prefer=("sinecure", "waiting", "on_post")) -> int:
    """裁减 `n` 名官，按 `prefer` 顺序优先裁祠禄/待阙（**裁冗先从冗处裁**）。返回实际裁减数。

    不触碰 `clerks`（吏的增减是 §16 吏制的独立议题）。
    """
    n = int(n)
    if n <= 0:
        return 0
    pop = (pref.get("pops") or {}).get(POP_CLASS)
    if not isinstance(pop, dict):
        return 0
    ensure_subpools(pref)
    cut = 0
    for key in prefer:
        if cut >= n:
            break
        room = min(int(pop.get(key, 0)), n - cut)
        if room > 0:
            pop[key] = int(pop[key]) - room
            cut += room
    pop["officials"] = int(pop["officials"]) - cut
    pop["size"] = max(0, int(pop["size"]) - cut)
    return cut


def post_officials(pref: Dict[str, Any], n: int) -> int:
    """授职：把 `n` 名待阙转为在岗（有阙才授）。返回实际授职数。"""
    n = int(n)
    if n <= 0:
        return 0
    pop = (pref.get("pops") or {}).get(POP_CLASS)
    if not isinstance(pop, dict):
        return 0
    ensure_subpools(pref)
    move = min(n, int(pop.get("waiting", 0)))
    if move > 0:
        pop["waiting"] = int(pop["waiting"]) - move
        pop["on_post"] = int(pop["on_post"]) + move
    return move


def to_sinecure(pref: Dict[str, Any], n: int) -> int:
    """待阙超阈值 → 转祠禄（宫观官）：仍食折俸，但不占差遣。返回实际转出数。"""
    n = int(n)
    if n <= 0:
        return 0
    pop = (pref.get("pops") or {}).get(POP_CLASS)
    if not isinstance(pop, dict):
        return 0
    ensure_subpools(pref)
    move = min(n, int(pop.get("waiting", 0)))
    if move > 0:
        pop["waiting"] = int(pop["waiting"]) - move
        pop["sinecure"] = int(pop["sinecure"]) + move
    return move


# ---------------------------------------------------------------- 镜像同步（唯一写入点）
def sync_legacy_mirror(state) -> None:
    """把 POP 派生量写入旧字段镜像 —— **本函数是 `p["officials"]`/`p["clerks"]` 的唯一写入点**。

    存在理由：Rust 并行后端与旧存档按人头读这两个字段。镜像若允许别处写，双账立刻复活。
    """
    for p in state.prefectures.values():
        ensure_subpools(p)
        p["officials"] = route_officials(p)
        p["clerks"] = route_clerks(p)
        p["official_units"] = route_pay_units(p)


# ---------------------------------------------------------------- 不变量
def check_invariants(state) -> Tuple[bool, list]:
    """校验两条不变量，返回 (是否全部成立, 违约描述列表)。供结算日志与测试共用。"""
    bad = []
    for name, p in state.prefectures.items():
        pop = (p.get("pops") or {}).get(POP_CLASS) or {}
        if not pop:
            continue
        size = int(pop.get("size", 0) or 0)
        off = int(pop.get("officials", 0) or 0)
        cle = int(pop.get("clerks", 0) or 0)
        if off + cle != size:
            bad.append(f"{name}: size({size}) != officials({off}) + clerks({cle})")
        s = (int(pop.get("on_post", 0) or 0) + int(pop.get("waiting", 0) or 0)
             + int(pop.get("sinecure", 0) or 0))
        if s != off:
            bad.append(f"{name}: officials({off}) != on_post+waiting+sinecure({s})")
    return (not bad), bad


# ---------------------------------------------------------------- 结算步
def settle_officialdom(state, log: Optional[list] = None) -> Dict[str, int]:
    """每月官制结算步：**迁移修复 → 不变量校验 → 镜像同步**。

    当前只做 C-1/C-2 的基础职责（消灭双账、维持子池一致性、刷新镜像）。
    后续增量（科举入仕、恩荫、磨勘、致仕、待阙授职）在同一函数内扩展。
    必须排在**财政步之前**，使 `calc_official_*` 读到本月的官额。
    """
    log = log if log is not None else []
    fixed = ensure_all(state)
    if fixed:
        log.append(f"[官制] 修复 {fixed} 路官僚 POP 子池（旧档迁移/一致性纠偏）")

    ok, bad = check_invariants(state)
    if not ok:
        # 自愈：以 size 为准重摊，并记录（不静默）
        for name, p in state.prefectures.items():
            ensure_subpools(p)
        ok2, bad2 = check_invariants(state)
        log.append(f"[官制] 子池不变量违约 {len(bad)} 处已按 size 重摊"
                   f"（残余 {len(bad2)} 处）；首例：{bad[0]}")
        if not ok2:
            state.statistics["officialdom_invariant_fail"] = bad2

    sync_legacy_mirror(state)
    t = totals(state)
    state.statistics["rank_officials"] = t["officials"]
    state.statistics["clerks_total"] = t["clerks"]
    state.statistics["awaiting_posts"] = t["waiting"]
    state.statistics["sinecure_officials"] = t["sinecure"]
    return t
