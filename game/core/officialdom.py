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
    CLAN_GROWTH_ANNUAL, CLAN_OFFICE_RATIO, CLERK_PER_OFFICIAL, EXAM_INTERVAL_YEARS,
    OFFICIAL_SUB_KEYS, OFFICIAL_RETIRE_RATE_YEAR, RANK_UP_PER_YEAR, ROUTE_POST_QUOTA,
    SINECURE_PAY_RATIO, WAITING_PAY_RATIO, WAITING_SINECURE_MULT,
    YINBEN_PER_JIAOSI, YINBEN_PRESTIGE_REF,
)
from core import institution as _inst       # 编制参数单一权威源（阶段 C-7）

POP_CLASS = "官僚"
GENTRY_CLASS = "士绅"
RANK_INDEX_CAP = 1.5             # 磨勘指数上限（防 200 年后俸禄爆炸；对应品阶结构上浮 50%）


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


# ---------------------------------------------------------------- 差遣定员（岗位，非人）
def ensure_quota(state) -> int:
    """初始化/修复 `state.posts_quota` —— **差遣定员（岗位数）**，官制里唯一合法的非 POP 存量。

    口径（§六②）：`Σ central_orgs[*].posts`（中央机构岗位，随"新建官职/裁撤机构"变法变动）
                  ＋ `ROUTE_POST_QUOTA × 路数`（州/县/幕职/监当等路级定员），
                  再乘编制参数 `posts_quota_mult`（**定编宽严**，§12.3 杠杆 1）。
    只在 `posts_quota <= 0`（旧档/新局）时重算，之后由机构变法增量维护；
    参数改动时由 `rescale_quota()` 重算（玩家降定编 → 冗官立刻上升）。
    """
    cur = int(getattr(state, "posts_quota", 0) or 0)
    if cur > 0:
        return cur
    central = 0
    for o in (getattr(state, "central_orgs", {}) or {}).values():
        if o.get("abolished"):
            continue
        central += len(o.get("posts") or [])
    base = central + ROUTE_POST_QUOTA * len(state.prefectures)
    state.posts_quota = int(base * _inst.get(state, "posts_quota_mult"))
    return state.posts_quota


def rescale_quota(state) -> int:
    """按当前 `posts_quota_mult` 重算差遣定员（玩家改「定编宽严」后调用）。

    定编是**闸门**：调低 → 冗官率立刻上升（"定编 vs 在册"的差额就是冗官，§12.8）。
    """
    central = 0
    for o in (getattr(state, "central_orgs", {}) or {}).values():
        if o.get("abolished"):
            continue
        central += len(o.get("posts") or [])
    base = central + ROUTE_POST_QUOTA * len(state.prefectures)
    new = int(base * _inst.get(state, "posts_quota_mult"))
    old, state.posts_quota = int(getattr(state, "posts_quota", 0) or 0), new
    return new - old


# ---------------------------------------------------------------- 宗室（士绅子池，L2c）
def ensure_clan(state) -> int:
    """初始化士绅 POP 的 `clan`（宗室人口）子池；旧档按士绅 0.3% 一次性给初值（≈3,000）。

    宗室 ⊆ 士绅（官户/形势户一类），**不新开第 7 类 POP**（POP 挂载律 条 1）。
    """
    total = 0
    for p in state.prefectures.values():
        pop = (p.get("pops") or {}).get(GENTRY_CLASS)
        if not isinstance(pop, dict):
            continue
        if "clan" not in pop:
            pop["clan"] = int(int(pop.get("size", 0) or 0) * 0.003)
        total += max(0, int(pop.get("clan", 0) or 0))
    return total


def clan_total(state) -> int:
    return sum(max(0, int(((p.get("pops") or {}).get(GENTRY_CLASS) or {}).get("clan", 0) or 0))
               for p in state.prefectures.values())


# ---------------------------------------------------------------- 全国派生视图
def totals(state) -> Dict[str, int]:
    """全国官制派生视图（面板/统计用，不落存量字段）。

    `posts_quota` / `redundant` 也在内：定员是**岗位**数（唯一合法的非 POP 官制存量），
    冗官 = 官额 − 定员（§13.5 的有机定义：再生产循环的产出 > 差遣岗位需求）。
    """
    out = {"officials": 0, "clerks": 0, "on_post": 0, "waiting": 0, "sinecure": 0, "size": 0}
    for p in state.prefectures.values():
        out["officials"] += route_officials(p)
        out["clerks"] += route_clerks(p)
        out["on_post"] += subpool(p, "on_post")
        out["waiting"] += subpool(p, "waiting")
        out["sinecure"] += subpool(p, "sinecure")
        out["size"] += int(((p.get("pops") or {}).get(POP_CLASS) or {}).get("size", 0) or 0)
    out["posts_quota"] = int(getattr(state, "posts_quota", 0) or 0)
    out["redundant"] = max(0, out["officials"] - out["posts_quota"])
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


# ---------------------------------------------------------------- 结算子步
def _fill_vacancies(state, log) -> int:
    """每月：有阙则授职（待阙 → 在岗）。返回授职数。

    空缺 = `posts_quota − Σ在岗`。待阙再多，也只能补上真正空出来的岗位 ——
    **这是"冗官"的定义得以成立的地方**：产出（科举/恩荫/宗室）> 岗位需求。
    """
    quota = ensure_quota(state)
    on_post = sum(subpool(p, "on_post") for p in state.prefectures.values())
    vacancies = max(0, quota - on_post)
    if vacancies <= 0:
        return 0
    waiting = sum(subpool(p, "waiting") for p in state.prefectures.values())
    budget = min(vacancies, waiting)
    if budget <= 0:
        return 0
    # 按各路待阙数比例授职（谁待阙久/多，谁先得阙的粗糙代理）
    routes = [p for p in state.prefectures.values() if subpool(p, "waiting") > 0]
    tot_w = sum(subpool(p, "waiting") for p in routes) or 1
    done = 0
    for i, p in enumerate(routes):
        w = subpool(p, "waiting")
        give = (budget - done) if i == len(routes) - 1 else int(budget * w / tot_w)
        give = max(0, min(give, w))
        done += post_officials(p, give)
    if done:
        log.append(f"[铨选] 有阙 {vacancies}，授职 {done} 人（待阙仍 {waiting - done}）")
    return done


def _overflow_to_sinecure(state, log) -> int:
    """每月：待阙超过「定员 × WAITING_SINECURE_MULT × sinecure_mult」→ 超额转祠禄。

    这是宋代真实做法（祠禄宫观安置冗官），也把"待阙无限堆积"变成一个**有成本的状态**：
    祠禄虽不占阙，仍要发折俸。玩家调「祠禄比例」即调这个阈值（§12.3 杠杆 4）。返回转出数。
    """
    quota = ensure_quota(state)
    cap = int(quota * WAITING_SINECURE_MULT * _inst.get(state, "sinecure_mult"))
    waiting = sum(subpool(p, "waiting") for p in state.prefectures.values())
    if waiting <= cap:
        return 0
    excess = waiting - cap
    routes = [p for p in state.prefectures.values() if subpool(p, "waiting") > 0]
    tot_w = sum(subpool(p, "waiting") for p in routes) or 1
    done = 0
    for i, p in enumerate(routes):
        w = subpool(p, "waiting")
        take = (excess - done) if i == len(routes) - 1 else int(excess * w / tot_w)
        take = max(0, min(take, w))
        done += to_sinecure(p, take)
    if done:
        log.append(f"[祠禄] 待阙壅积（{waiting} 超限 {cap}），{done} 人改授宫观祠禄（折俸）")
    return done


def _annual_retire(state, log) -> int:
    """每年正月：在岗官按 `OFFICIAL_RETIRE_RATE_YEAR` 退出（致仕/死亡/罢黜），**回士绅**。

    ΣPOP 守恒：`官僚.officials ↓ n`、`官僚.size ↓ n`、`士绅.size ↑ n` ——
    这正是"士大夫再生产循环"的出口轴（§13.5）：官退休 → 变回地方士绅 →
    士绅子弟再考科举 → 又变官。
    """
    total = 0
    for p in state.prefectures.values():
        pop = (p.get("pops") or {}).get(POP_CLASS)
        if not isinstance(pop, dict):
            continue
        ensure_subpools(p)
        n = int(int(pop.get("on_post", 0)) * OFFICIAL_RETIRE_RATE_YEAR
                * _inst.get(state, "retire_mult"))
        if n <= 0:
            continue
        n = min(n, int(pop["on_post"]))
        pop["on_post"] = int(pop["on_post"]) - n
        pop["officials"] = int(pop["officials"]) - n
        pop["size"] = max(0, int(pop["size"]) - n)
        shen = (p.get("pops") or {}).get(GENTRY_CLASS)
        if isinstance(shen, dict):
            shen["size"] = int(shen.get("size", 0)) + n
        total += n
    if total:
        log.append(f"[致仕] {total} 员解职归乡（在岗 → 士绅，循环闭合）")
        state.recruit_log["致仕"] = state.recruit_log.get("致仕", 0) + total
    return total


def _annual_rank_up(state, log) -> None:
    """每年正月：磨勘 —— 品阶结构上浮 → 人均俸禄涨（`official_rank_index`，封顶 1.5）。

    玩家调「磨勘年限」即调这个速度（§12.3 杠杆 3）。
    """
    idx = float(getattr(state, "official_rank_index", 1.0) or 1.0)
    new = min(RANK_INDEX_CAP, idx * (1.0 + RANK_UP_PER_YEAR * _inst.get(state, "rank_up_mult")))
    if new > idx:
        state.official_rank_index = new
        log.append(f"[磨勘] 品阶结构上浮，人均俸禄指数 → {new:.4f}")


def _annual_clan(state, log) -> int:
    """每年：宗室人口复利增长（新增人丁记入士绅 size，属人口自然增减），并有一部分入官。

    宗室入官是**转移**（士绅 → 官僚），ΣPOP 守恒。
    """
    births = 0
    entered = 0
    for p in state.prefectures.values():
        shen = (p.get("pops") or {}).get(GENTRY_CLASS)
        if not isinstance(shen, dict):
            continue
        clan = max(0, int(shen.get("clan", 0) or 0))
        if clan <= 0:
            continue
        add = int(clan * CLAN_GROWTH_ANNUAL)
        if add > 0:
            shen["clan"] = clan + add
            shen["size"] = int(shen.get("size", 0)) + add     # 新增人丁（非转移）
            # **必须同步人口总账**：POP 挂载律 条 3 要求阶层变动「ΣPOP 守恒**或显式记为
            # 人口自然增减**」。只加 ΣPOP 而不加 state.population，会让身份式
            # `ΣPOP + 流民 == population` 在月内破裂（月尾 Step 10.5 的重对齐会把它掩盖成
            # "月末才一致"，但月内分配逻辑读到的是错的 population）。
            state.population = int(getattr(state, "population", 0) or 0) + add
            births += add
            clan += add
        n = int(clan * CLAN_OFFICE_RATIO)
        if n > 0:
            n = min(n, int(shen.get("size", 0)))
            if n > 0:
                shen["size"] = int(shen["size"]) - n          # 转移：士绅 → 官僚
                add_officials(p, n, "waiting")
                entered += n
    if births:
        log.append(f"[宗室] 宗室人口自然增长 {births} 人（复利 {CLAN_GROWTH_ANNUAL:.0%}/年）")
    if entered:
        log.append(f"[宗室] 宗室入官 {entered} 人（士绅 → 官僚，待阙）")
        state.recruit_log["宗室"] = state.recruit_log.get("宗室", 0) + entered
    return births


def _triennial_exam(state, log) -> int:
    """每 `EXAM_INTERVAL_YEARS` 年（科次年正月）：**一次科次**取士，落**待阙**池。

    形态修正（§15.2）：原实现是每月连续小额入仕（≈3,700 人/科次），现改为一次数百人。
    入仕来源按 `EXAM_HARD_POOR_SHARE` 拆为**寒门（农）**与**士绅子弟**，两者都是
    **POP 间转移**（ΣPOP 守恒），不是新增人口。

    `state.exam` 记录科次台账：`last_cohort`（本届取士数）、`cohorts`（历届 {year, size}）——
    这是「同年/座主」这类真实政治结构的载体（§15.4），后续可挂党争。
    """
    from content.data import EXAM_COHORT_SIZE, EXAM_HARD_POOR_SHARE

    if not (state.exam or {}).get("open"):
        log.append("[科举] 停科，本届不取士")
        state.exam["last_cohort"] = 0
        return 0

    tier = "中"
    try:
        ai = getattr(state, "_economy_ai", None) or {}
        if ai.get("科举"):
            tier = ai["科举"]
    except Exception:  # noqa: BLE001 — 档位缺失一律退化为"中"，不影响守恒
        tier = "中"
    target = int(EXAM_COHORT_SIZE.get(tier, EXAM_COHORT_SIZE["中"]))
    if target <= 0:
        state.exam["last_cohort"] = 0
        return 0

    rates = EXAM_HARD_POOR_SHARE.get(tier, 0.7)
    taken = 0
    hard_total = 0
    for p in state.prefectures.values():
        pops = p.get("pops") or {}
        nong, shen = pops.get("农"), pops.get("士绅")
        if not isinstance(nong, dict) or not isinstance(shen, dict):
            continue
        # 按各路人口占比分配取士额（京畿/膏腴路略多，这里用人口作代理）
        share = int(p.get("population", 0) or 0)
        if share <= 0:
            continue
        _all = sum(int(q.get("population", 0) or 0) for q in state.prefectures.values()) or 1
        quota = int(target * share / _all)
        if quota <= 0:
            continue
        hard = min(int(quota * rates), int(nong.get("size", 0)))
        elite = min(quota - hard, int(shen.get("size", 0)))
        if hard + elite <= 0:
            continue
        nong["size"] = int(nong["size"]) - hard          # 转移：农 → 官僚
        shen["size"] = int(shen["size"]) - elite          # 转移：士绅 → 官僚
        add_officials(p, hard + elite, "waiting")          # 新科进士先待阙（§13.5）
        taken += hard + elite
        hard_total += hard

    state.exam["last_cohort"] = taken
    if taken:
        state.exam.setdefault("cohorts", [])
        state.exam["cohorts"] = (list(state.exam["cohorts"]) + [
            {"year": int(getattr(state, "year", 0) or 0), "size": taken}])[-12:]
        state.recruit_log["科举"] = state.recruit_log.get("科举", 0) + taken
        log.append(f"[科举] 科次取士 {taken} 人（档位「{tier}」，寒门 {hard_total}／"
                   f"士绅子弟 {taken - hard_total}），皆入待阙")
    return taken


def _triennial_yinben(state, log) -> int:
    """每 3 年（郊祀之年正月）：恩荫 —— 士绅子弟荫补入官（**转移**，ΣPOP 守恒）。

    规模随皇威缩放：皇威越高，荫补越多（这是皇威的一个**真实财政代价**，
    也是"郊赉/恩荫"这类宋代财政大项在玩法上的表达）。
    """
    prestige = float(getattr(state, "prestige", 50) or 50)
    scale = max(0.2, min(3.0, prestige / YINBEN_PRESTIGE_REF))
    total = 0
    for p in state.prefectures.values():
        shen = (p.get("pops") or {}).get(GENTRY_CLASS)
        if not isinstance(shen, dict):
            continue
        n = int(int(shen.get("size", 0)) * YINBEN_PER_JIAOSI * scale
                * _inst.get(state, "yinben_mult"))
        if n <= 0:
            continue
        n = min(n, int(shen.get("size", 0)))
        shen["size"] = int(shen["size"]) - n
        add_officials(p, n, "waiting")
        total += n
    if total:
        log.append(f"[恩荫] 郊祀荫补 {total} 人入仕（士绅 → 官僚，随皇威 {prestige:.0f} 缩放）")
        state.recruit_log["恩荫"] = state.recruit_log.get("恩荫", 0) + total
    return total


def settle_officialdom(state, log: Optional[list] = None) -> Dict[str, int]:
    """每月官制结算步（排在**财政步之前**，使 `calc_official_*` 读到本月官额）。

    子步链（宋代官制设计 §七）：
      每月 —— ① 迁移修复 ② 不变量校验 ③ **待阙授职** ④ **超额转祠禄** ⑤ 镜像同步
      每年正月 —— ⑥ **致仕**（在岗 → 士绅）⑦ **磨勘**（品阶上浮 → 人均俸禄涨）
                  ⑧ **宗室**（复利 ＋ 入官）
      每 3 年正月 —— ⑨ **恩荫**（郊祀荫补，士绅 → 官僚）

    保守恒：③④⑥⑦ 不改变总人口；⑧ 的新增人丁显式记为人口自然增减；⑥⑧⑨ 的入仕/致仕
    走 POP 间转移，**ΣPOP 不变**（由 `tests/test_officialdom.py` 断言）。
    """
    log = log if log is not None else []
    fixed = ensure_all(state)
    if fixed:
        log.append(f"[官制] 修复 {fixed} 路官僚 POP 子池（旧档迁移/一致性纠偏）")

    ok, bad = check_invariants(state)
    if not ok:
        for p in state.prefectures.values():
            ensure_subpools(p)
        ok2, bad2 = check_invariants(state)
        log.append(f"[官制] 子池不变量违约 {len(bad)} 处已按 size 重摊"
                   f"（残余 {len(bad2)} 处）；首例：{bad[0]}")
        if not ok2:
            state.statistics["officialdom_invariant_fail"] = bad2

    ensure_quota(state)
    rescale_quota(state)        # 定编参数（posts_quota_mult）与机构变法每月重算定员
    ensure_clan(state)

    _fill_vacancies(state, log)
    _overflow_to_sinecure(state, log)

    month = int(getattr(state, "month", 1) or 1)
    year = int(getattr(state, "year", 1101) or 1101)
    if month == 1:
        _annual_retire(state, log)
        _annual_rank_up(state, log)
        _annual_clan(state, log)
        if (year - 1101) % EXAM_INTERVAL_YEARS == 0:      # 科次年（每 3 年一次，§15）
            _triennial_exam(state, log)
        if (year - 1101) % 3 == 0:                        # 郊祀之年（恩荫，§七）
            _triennial_yinben(state, log)

    sync_legacy_mirror(state)
    t = totals(state)
    t["clan"] = clan_total(state)
    t["rank_index"] = float(getattr(state, "official_rank_index", 1.0) or 1.0)
    state.statistics["rank_officials"] = t["officials"]
    state.statistics["clerks_total"] = t["clerks"]
    state.statistics["awaiting_posts"] = t["waiting"]
    state.statistics["sinecure_officials"] = t["sinecure"]
    state.statistics["posts_quota"] = t["posts_quota"]
    state.statistics["redundant_officials"] = max(0, t["officials"] - t["posts_quota"])
    return t
