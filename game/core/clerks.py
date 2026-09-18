# -*- coding: utf-8 -*-
"""吏制（宋代官制与三冗设计 §16）—— 吏是「不可见的执行层」。

## 为什么单独一个模块

吏与官是**两种制度存在**：官三年一任、回避本籍、不熟地方；吏世代本地、熟稔案牍、
掌握簿书。审计实证（§16.2）现行模型里**吏制的三个关键机制全部缺失**——
吏只是一个"每月领 2 贯的人数"：

| 缺口 | 现状 | 后果 |
|---|---|---|
| 吏额 | `clerks = officials × CLERK_PER_OFFICIAL`（静态常数） | 不随政务量变动，**冗吏无从表达** |
| 吏禄水平 | 2.0 贯 + 本色 1.5 石 ≈ **3.5 贯/月**，而户均 4 口需 **7.2 贯/月** | 吏禄不足**没有任何后果** |
| 把持度 / 吏怨 | 不存在 | 政令扭曲、阳奉阴违均无法表达 |

本模块补齐：**吏额由政务量驱动**（编制惯性）、**吏禄不足 → 陋规 → 民怨**、
**把持度 → 政令执行打折**、**吏怨 → 「冗而不足」悖论**。

## 守恒纪律（POP 挂载律）

- 吏的"人"落在 `pops["官僚"]["clerks"]` 子池（§13.4 官/吏分账）；
  吏额增减一律与 `农` POP **对转**（差役/募吏来源），**ΣPOP 守恒**。
- **陋规是纯转移**：从本路 `农`/`工匠`/`商人` 的 `wealth` 取，全额入 `官僚` POP 的 `wealth`
  （吏所得）。`ΔM_ALL == 0`，不造币、不销毁。民心的下降才是真正的社会成本。
"""
from typing import Any, Dict, List, Optional

from content.data import (
    BACKLOG_GAIN_MAX, CLERK_ADJUST_RATE, CLERK_ENTITLEMENT_GROWTH, CLERK_GRAIN_PER_MONTH,
    CLERK_PAY_PER_MONTH, CLERK_STAFFING_ALPHA, CLERK_SUBSISTENCE_CASH,
    DECREE_GRIP_W, EXACTION_MAX_SHARE, EXACTION_MOOD_DIVISOR, EXACTION_RATE,
    GRIP_BASE, GRIP_DECAY_TOWARD, GRIP_HEREDITARY_W, GRIP_COVERAGE_W, GRIP_MAX,
    GRIEVANCE_ADJUST, GRIEVANCE_MIN_FLOOR, GRIEVANCE_COVERAGE_RELIEF,
    W_POP_BASE, W_LITIGATION_BASE, W_LITIGATION_UNREST_W, W_LAND_BASE, W_ORG_EACH,
    W_OFFICIAL_BASE, W_GARRISON_BASE,
)

POP_CLASS = "官僚"
GENTRY_CLASS = "士绅"
FARM_CLASS = "农"
_EXACTION_POOLS = ("农", "工匠", "商人")


# ---------------------------------------------------------------- 初始化
def ensure_detail(state) -> int:
    """幂等补齐每路的 `clerks_detail`（§16.10：`pay_ratio` 钩子早已存在，其余为新增）。

    旧档迁移：`actual = 官僚.clerks`、`quota = actual`、`grip = GRIP_BASE`、
    `grievance = 0`、`source_mix = {"差役":0.6,"募吏":0.4}`、`hereditary = 0.4`。
    `w0` 记该路**开局政务量**，用于 `(W/W₀)^α` 弹性校准（§11.5）。
    """
    fixed = 0
    for p in state.prefectures.values():
        pop = (p.get("pops") or {}).get(POP_CLASS) or {}
        actual = max(0, int(pop.get("clerks", 0) or 0))
        d = p.get("clerks_detail")
        if not isinstance(d, dict):
            d = {}
            p["clerks_detail"] = d
            fixed += 1
        d.setdefault("actual", actual)
        d.setdefault("quota", actual)
        d.setdefault("establishment", actual)
        d.setdefault("grip", GRIP_BASE)
        d.setdefault("grievance", 0.0)
        d.setdefault("source_mix", {"差役": 0.6, "募吏": 0.4})
        d.setdefault("hereditary", 0.4)
        d.setdefault("extortion", 0)
        if not d.get("w0"):
            d["w0"] = max(1.0, route_workload(state, p))
        # `k` = 每吏月办件数（§11.5 校准锚点：`k = W₀ / 吏额`）。有了它，"需求"
        # `C_req = W / k` 与"有效处理能力" `C_eff = 吏数 × k × (1 − 吏怨/100)`
        # 才在同一量纲上可比，从而算出 §16.6 的「冗而不足」。
        if not d.get("k"):
            d["k"] = max(1e-9, float(d["w0"]) / max(1, actual))
    return fixed


# ---------------------------------------------------------------- 政务量 W（§11 的务实子集）
def route_workload(state, p: Dict[str, Any]) -> float:
    """本路**政务量 W**（案牍件/月，§11.4 分项表的务实子集）。

    只取**全部映射到现有字段**且权重最高者（§11.4 的权重原则：C/D 最高、I 随冗官自动增长、
    G 随民怨正反馈）：

    | 代号 | 分项 | 字段 |
    |---|---|---|
    | A | 民政基础 | `population`（每 10 万人 1 件） |
    | G | 刑狱词讼 | `population` × (1 + 民怨系数)（每 50 万人 1 件） |
    | B | 田赋户籍 | `land + hidden_land`（每百万亩 1 件） |
    | D | 机构事权 | 本路所辖机构分支数 × 每机构 1 件 |
    | I | 人事铨选 | 本路官额（每 100 官 1 件） |
    | J | 军需后勤 | 本路驻军（每 10 万兵 1 件） |

    诏令类（C）、长期政务（E）、工程（F）、财政（H）、外交（K）、科举（L）在本子集中
    **未计入**——它们或为全国性、或增量很小；`C` 的玩家杠杆作用已在 `_settle_decrees`
    的执行率与积压惩罚中体现，不在吏额公式里二次计入。
    """
    pop = float(p.get("population", 0) or 0)
    unrest = float(p.get("unrest", 15) or 15)
    mood = float(p.get("mood", 55) or 55)
    _grievance = max(0.0, (55.0 - mood) / 55.0)          # 民怨系数 0~1
    land = float(p.get("land", 0) or 0) + float(p.get("hidden_land", 0) or 0)
    orgs = len(p.get("branches") or [])
    offs = float(((p.get("pops") or {}).get(POP_CLASS) or {}).get("officials", 0) or 0)
    garrison = float(p.get("garrison", 0) or 0)

    w = pop / W_POP_BASE
    w += pop * (1.0 + W_LITIGATION_UNREST_W * (unrest / 40.0) + _grievance) / W_LITIGATION_BASE
    w += land / W_LAND_BASE
    w += orgs * W_ORG_EACH
    w += offs / W_OFFICIAL_BASE
    w += garrison / W_GARRISON_BASE
    return max(1.0, w)


# ---------------------------------------------------------------- 吏额（脱离「官×8」）
def _adjust_staffing(state, log: List[str]) -> int:
    """吏额向**编制存量**（`establishment`）缓慢靠拢，**编制惯性** `CLERK_ADJUST_RATE`/月。

    增吏（差役/募吏）从 `农` POP 抽调；减吏则回乡。**ΣPOP 严格守恒**。
    返回全国净增吏数（负为减）。
    """
    net = 0
    for p in state.prefectures.values():
        pop = (p.get("pops") or {}).get(POP_CLASS)
        nong = (p.get("pops") or {}).get(FARM_CLASS)
        if not isinstance(pop, dict) or not isinstance(nong, dict):
            continue
        d = p["clerks_detail"]
        actual = int(pop.get("clerks", 0) or 0)
        quota = int(d.get("establishment", d.get("quota", actual)) or 0)
        diff = quota - actual
        if diff == 0:
            d["actual"] = actual
            continue
        step = int(diff * CLERK_ADJUST_RATE)
        if step == 0:
            step = 1 if diff > 0 else -1
        if step > 0:
            step = min(step, int(nong.get("size", 0)))            # 来源：农户
            if step <= 0:
                continue
            nong["size"] = int(nong["size"]) - step
        else:
            step = max(step, -actual)                              # 不得裁到负数
            if step == 0:
                continue
            nong["size"] = int(nong.get("size", 0)) + (-step)      # 去向：回乡
        pop["clerks"] = actual + step
        pop["size"] = max(0, int(pop.get("size", 0)) + step)
        d["actual"] = actual + step
        net += step
    if net:
        log.append(f"[吏额] 幕职吏员{'增' if net > 0 else '减'} {abs(net)} 人"
                   f"（政务量驱动，编制惯性 {CLERK_ADJUST_RATE:.0%}/月；差额与农户口对转）")
    return net


# ---------------------------------------------------------------- 吏禄 → 陋规 → 民怨（§16.5）
def _extort(state, p: Dict[str, Any], log: List[str]) -> Dict[str, float]:
    """本路吏禄不足 → 陋规取偿。**纯转移**：民间三池 wealth → 官僚 POP wealth。

    返回 {desired, taken, coverage, gap_ratio}。
    """
    pop = (p.get("pops") or {}).get(POP_CLASS)
    if not isinstance(pop, dict):
        return {"desired": 0.0, "taken": 0.0, "coverage": 0.0, "gap_ratio": 0.0}
    clerks = float(pop.get("clerks", 0) or 0)
    d = p["clerks_detail"]
    if clerks <= 0:
        return {"desired": 0.0, "taken": 0.0, "coverage": 1.0, "gap_ratio": 0.0}

    name = next((k for k, v in state.prefectures.items() if v is p), "")
    pr = float(state.calc_pay_ratio(name)) if name else 1.0
    grain_price = float(getattr(state, "grain_price", 1.0) or 1.0)
    # 吏实得（折色等价，贯/人/月）：俸钱 + 本色禄米折钱，乘地方财力充足率
    received = (CLERK_PAY_PER_MONTH + CLERK_GRAIN_PER_MONTH * grain_price) * pr
    # **制度性俸薄**才是主因（§16.2：官吏待遇比 15:1，吏所得仅及家庭口粮一半），
    # `pay_ratio` 只是第二重。故用"维持生计线"作缺口基准，而非"应发额"。
    gap_ratio = max(0.0, min(1.0, 1.0 - received / max(0.01, CLERK_SUBSISTENCE_CASH)))
    desired = clerks * max(0.0, CLERK_SUBSISTENCE_CASH - received) * EXACTION_RATE

    # 可抽取上限：民间三池按比例，且遵守"单月最多抽 EXACTION_MAX_SHARE"
    pools = {}
    for k in _EXACTION_POOLS:
        q = (p.get("pops") or {}).get(k)
        if isinstance(q, dict):
            pools[k] = max(0, int(q.get("wealth", 0) or 0))
    total_pool = sum(pools.values())
    cap = int(total_pool * EXACTION_MAX_SHARE)
    take = int(min(desired, cap))
    if take <= 0:
        d["extortion"] = 0
        d["grievance"] = _next_grievance(d, gap_ratio, 0.0)
        return {"desired": desired, "taken": 0.0, "coverage": 0.0, "gap_ratio": gap_ratio}

    # 精确分配：民间池按财富占比扣，末位吃尾差；全额入官僚 POP wealth
    given = 0
    keys = list(pools.keys())
    for i, k in enumerate(keys):
        q = p["pops"][k]
        share = (take - given) if i == len(keys) - 1 else int(take * pools[k] / max(1, total_pool))
        share = max(0, min(share, int(q.get("wealth", 0) or 0)))
        q["wealth"] = int(q.get("wealth", 0) or 0) - share
        given += share
    pop["wealth"] = int(pop.get("wealth", 0) or 0) + given

    coverage = given / max(1.0, desired)
    d["extortion"] = given
    d["grievance"] = _next_grievance(d, gap_ratio, coverage)
    # 民心代价（真正的社会成本）：按陋规相对于本路人口的强度折算
    if given > 0:
        pen = min(1.5, given / max(1.0, float(p.get("population", 0) or 0)) / EXACTION_MOOD_DIVISOR)
        p["mood"] = max(0.0, float(p.get("mood", 55) or 55) - pen)
    return {"desired": desired, "taken": float(given), "coverage": coverage,
            "gap_ratio": gap_ratio}


def _next_grievance(d: Dict[str, Any], gap_ratio: float, coverage: float) -> float:
    """吏怨（0–100）向目标值缓动。

    目标由**制度性俸薄**（`gap_ratio`）决定；陋规能缓解一部分（`coverage`），
    但**不可能归零**——靠陋规吃饭终究不是体面收入，这正是宋代吏治的死结（§16.5）。
    """
    target = 100.0 * gap_ratio * (1.0 - GRIEVANCE_COVERAGE_RELIEF * min(1.0, coverage))
    target = max(GRIEVANCE_MIN_FLOOR, min(100.0, target))
    cur = float(d.get("grievance", 0.0) or 0.0)
    return max(0.0, min(100.0, cur + (target - cur) * GRIEVANCE_ADJUST))


# ---------------------------------------------------------------- 把持度（吏强官弱，§16.4）
def _next_grip(d: Dict[str, Any], coverage: float) -> float:
    """把持度 0–1：由**世袭比例**（世代本地、掌握簿书）与**陋规补足率**（有动力把持）驱动。"""
    hereditary = float(d.get("hereditary", 0.4) or 0.0)
    target = GRIP_BASE + GRIP_HEREDITARY_W * hereditary + GRIP_COVERAGE_W * min(1.0, coverage)
    target = max(0.0, min(GRIP_MAX, target))
    cur = float(d.get("grip", GRIP_BASE) or GRIP_BASE)
    return max(0.0, min(GRIP_MAX, cur + (target - cur) * GRIP_DECAY_TOWARD))


# ---------------------------------------------------------------- 全国派生视图 / 杠杆
def totals(state) -> Dict[str, Any]:
    """全国吏制派生视图（面板/统计/后端用，**只读**）。"""
    clerks = quota = establishment = 0
    extortion = 0.0
    grip_w = 0.0
    griev_w = 0.0
    for p in state.prefectures.values():
        d = p.get("clerks_detail") or {}
        c = max(0, int(((p.get("pops") or {}).get(POP_CLASS) or {}).get("clerks", 0) or 0))
        clerks += c
        quota += int(d.get("quota", c) or 0)
        establishment += int(d.get("establishment", d.get("quota", c)) or 0)
        extortion += float(d.get("extortion", 0) or 0)
        grip_w += float(d.get("grip", GRIP_BASE) or GRIP_BASE) * c
        griev_w += float(d.get("grievance", 0.0) or 0.0) * c
    n = max(1, clerks)
    grip = grip_w / n
    grievance = griev_w / n
    # 冗吏 = 编制存量 − 当期需求（§11.3：吏实际 − C_req；编制是它的 sticky 代理）
    redundant = max(0, establishment - quota)
    return {
        "clerks": clerks,
        "quota": quota,                     # 当期**需求** C_req
        "establishment": establishment,      # **编制存量**（世袭/请托 → 有增无损）
        "redundant": redundant,
        "redundant_rate": round(redundant / max(1, quota), 4),
        "grip": round(grip, 4),
        "grievance": round(grievance, 2),
        "extortion": int(extortion),
        # 有效吏力 = 吏数 × (1 − 吏怨/100)：**"冗而不足"的载体**（§16.6）
        "effective": int(clerks * (1.0 - grievance / 100.0)),
        "decree_mult": round(max(0.3, 1.0 - DECREE_GRIP_W * grip), 4),
        "quality": clerk_quality(grip, grievance),
    }


def clerk_quality(grip: float, grievance: float) -> str:
    """吏治定性四档（§16.9）：案牍清明 → 吏习其事 → 吏胥弄权 → 吏弊丛生。"""
    if grip < 0.25 and grievance < 25:
        return "案牍清明"
    if grip < 0.45 and grievance < 50:
        return "吏习其事"
    if grip < 0.65 or grievance < 75:
        return "吏胥弄权"
    return "吏弊丛生"


def decree_execution_mult(state) -> float:
    """把持度对**诏令执行率**的折扣（§16.4：「实际执行率 = 官效率 × (1 − 把持度 × w)」）。

    这是给审计 J-2「叙事说办了、数值没动」一个**有原因、可诊断、可治理**的载体：
    回执仍是"已施行"，但效果打折，且原因可在面板查到「该路吏胥把持，政令不畅」。
    """
    return float(totals(state)["decree_mult"])


def backlog_gain(state, route: str) -> float:
    """本路本月**净积压增量**（§11.6 第一行：把 `random.randint(0,3)` 换成 `W − C`）。

    `C_eff = 吏数 × k × (1 − 吏怨/100)`（§16.6）——吏数够但吏怨高，有效处理能力反而不足，
    于是「冗吏」与「积压」并存。返回值归一到与旧随机项同一量级（0 ~ BACKLOG_GAIN_MAX）。
    """
    p = state.prefectures.get(route)
    if not isinstance(p, dict):
        return 0.0
    d = p.get("clerks_detail") or {}
    if not d:
        return 0.0
    clerks = float(((p.get("pops") or {}).get(POP_CLASS) or {}).get("clerks", 0) or 0)
    grievance = float(d.get("grievance", 0.0) or 0.0)
    k = float(d.get("k", 0.0) or 0.0)
    w = route_workload(state, p)
    if k <= 0 or w <= 0:
        return 0.0
    capacity = clerks * k * (1.0 - grievance / 100.0)
    short = max(0.0, w - capacity)
    return min(float(BACKLOG_GAIN_MAX), short / w * float(BACKLOG_GAIN_MAX))


# ---------------------------------------------------------------- 结算步
def settle_clerks(state, log: Optional[list] = None) -> Dict[str, Any]:
    """每月吏制结算步（排在**财政步之前**：俸禄/贪腐要读本月吏额与吏怨）。

    子步：
      ① 旧档 `clerks_detail` 迁移修复
      ② **吏额由政务量驱动**（`quota ∝ W^α`），按**编制惯性**向编制靠拢（与农户口对转）
      ③ **吏禄不足 → 陋规**（民间三池 → 官僚 POP，纯转移）＋ **民心代价** ＋ **吏怨缓动**
      ④ **把持度**（世袭 ＋ 陋规补足率）缓动
      ⑤ 写入 `statistics` 派生指标供面板/后端/AI 读取

    守恒：② 是 ΣPOP 守恒的人头对转；③ 的金额 `ΔM_ALL == 0`（不造币、不销毁）。
    """
    log = log if log is not None else []
    fixed = ensure_detail(state)
    if fixed:
        log.append(f"[吏制] 修复 {fixed} 路 clerks_detail（旧档迁移）")

    # ---- ② 吏额：政务量 → 需求；需求 ＋ 编制惯性 → 编制存量；编制存量 ← 吏额 ----
    alpha = CLERK_STAFFING_ALPHA
    base_total = 0
    for p in state.prefectures.values():
        d = p["clerks_detail"]
        w = route_workload(state, p)
        d["w"] = w
        w0 = max(1.0, float(d.get("w0", w) or w))
        # ① 当期**需求** C_req = 开局吏额 × (W/W₀)^α，α<1 表示规模经济
        d["quota"] = max(1, int(round(int(d.get("_base", 0) or 0) * (w / w0) ** alpha)))
        base_total += int(d.get("_base", 0) or 0)

    # 首月把「开局吏额」记为基数（`_base`），保证 t=0 时 quota == 开局吏额（零数值变更）
    if base_total == 0:
        for p in state.prefectures.values():
            d = p["clerks_detail"]
            d["_base"] = int(d.get("actual", 0) or 0)
            d["quota"] = int(d["_base"])
            d["establishment"] = int(d["_base"])
        log.append("[吏制] 记录吏额基数（此后编制由政务量驱动）")

    # ② **编制存量**（sticky）：不低于当期需求，且因**世袭/请托**自我膨胀 ——
    #    「吏额有增无损」。**冗吏 = 编制存量 − 当期需求**，这才是"冗吏"的真正来源
    #    （若只让吏额追着需求跑，工作总量只增不减的局里永远不会出现冗吏）。
    for p in state.prefectures.values():
        d = p["clerks_detail"]
        c_req = max(1, int(d["quota"]))
        est = max(1, int(d.get("establishment", c_req) or c_req))
        est = int(est * (1.0 + CLERK_ENTITLEMENT_GROWTH))
        d["establishment"] = max(c_req, est)
    _adjust_staffing(state, log)

    # ---- ③④ 吏禄 → 陋规 → 民怨；把持度 ----
    nat_extort = 0.0
    for p in state.prefectures.values():
        r = _extort(state, p, log)
        nat_extort += r["taken"]
        p["clerks_detail"]["grip"] = _next_grip(p["clerks_detail"], r["coverage"])

    t = totals(state)
    # 吏额在本步发生了变化 → 必须刷新**派生镜像**（`p["clerks"]` 的唯一写入点仍是
    # `officialdom.sync_legacy_mirror`；此处只是让它晚一步再刷一次，避免镜像落后 1 个月）。
    from core.officialdom import sync_legacy_mirror
    sync_legacy_mirror(state)
    state.statistics["clerks_total"] = t["clerks"]
    state.statistics["clerks_quota"] = t["quota"]
    state.statistics["clerks_redundant"] = t["redundant"]
    state.statistics["clerks_grip"] = t["grip"]
    state.statistics["clerks_grievance"] = t["grievance"]
    state.statistics["clerks_extortion"] = t["extortion"]
    state.statistics["clerks_quality"] = t["quality"]
    if t["extortion"] > 0:
        log.append(f"[吏禄] 陋规取偿 {t['extortion']:,} 贯（吏禄不足 → 民间盘剥；"
                   f"吏怨 {t['grievance']:.1f} 把持度 {t['grip']:.2f}）")
    return t
