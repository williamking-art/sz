# -*- coding: utf-8 -*-
"""阶段 C（官制完善）回归测试：消灭双账 · 身份子池 · 铨选阀门 · 出口轴 · ΣPOP 守恒。

设计依据：`_dev_tools/game-docs/docs/宋代官制与三冗设计.md` §六/§七/§13.3/§13.4/§13.5。
实现单一权威源：`core/officialdom.py`；本文件只断言**可观测行为与守恒**。

被断言的缺陷（修复前实证）：
  · `p["officials"]`（户数 × 0.00135，永不变化）与 `pops["官僚"].size`（随流动变化）**双账**：
    30 月实跑官僚 POP **+23.1%** 而 `officials` **+0.0%** → "养更多官、一分钱不多花"。
  · 裁汰冗员原实现直接 `size -= cut`，被裁的人**凭空消失**（破 ΣPOP 守恒）。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import money, officialdom as od  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402
from core.settlement_steps import _settle_clan  # noqa: E402
from content.data import (  # noqa: E402
    CLAN_PAY_PER_MONTH, ROUTE_POST_QUOTA, WAITING_SINECURE_MULT,
)

_ECO = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
        "窖银": "小", "城市化": "中", "回乡": "无", "科举": "中"}


def _pop_total(s):
    return (sum(pop["size"] for p in s.prefectures.values() for pop in p["pops"].values())
            + s.refugee_count)


def _gentry_wealth(s):
    return sum(p["pops"]["士绅"].get("wealth", 0) for p in s.prefectures.values())


def _run(s, months, seed=7):
    for _ in range(months):
        s._economy_ai = _ECO
        run_monthly_settlement(s, seed_offset=seed)
    return s


# ---------------------------------------------------------------- C-1 双账消灭
def test_mirror_follows_pop_no_drift():
    """旧字段 `p["officials"]`/`["clerks"]` 是**派生镜像**，30 月后必须与 POP 子池逐路相等。"""
    s = _run(GameState("史实"), 30)
    for name, p in s.prefectures.items():
        assert p["officials"] == od.route_officials(p), f"{name}: 镜像漂移 (官)"
        assert p["clerks"] == od.route_clerks(p), f"{name}: 镜像漂移 (吏)"


def test_officials_now_grow_with_pop():
    """修复目标：官额与官俸必须随官僚 POP 增长（修复前 officials 恒 +0.0%、俸禄恒定）。"""
    s = GameState("史实")
    off0 = od.totals(s)["officials"]
    cash0, _ = s.calc_official_cash()
    _run(s, 30, seed=7)
    off1 = od.totals(s)["officials"]
    cash1, _ = s.calc_official_cash()
    assert off1 > off0, f"官额未增长：{off0} → {off1}"
    assert cash1 > cash0, f"官俸未增长（双账仍在）：{cash0:.0f} → {cash1:.0f}"


def test_subpool_invariants_hold_over_time():
    """两条不变量 30 月恒成立：size == officials+clerks；officials == on_post+waiting+sinecure。"""
    s = _run(GameState("史实"), 30)
    ok, bad = od.check_invariants(s)
    assert ok, f"子池不变量违约：{bad[:3]}"
    t = od.totals(s)
    assert t["size"] == t["officials"] + t["clerks"]
    assert t["officials"] == t["on_post"] + t["waiting"] + t["sinecure"]


def test_old_save_without_subpools_migrates_and_self_heals():
    """旧档缺子池 → `ensure_subpools` 按 `size` 与旧字段迁移，且不变量立即可用。"""
    s = GameState("史实")
    p = s.prefectures["两浙路"]
    pop = p["pops"]["官僚"]
    for k in ("officials", "clerks", "on_post", "waiting", "sinecure"):
        pop.pop(k, None)
    assert od.ensure_subpools(p) is True
    ok, bad = od.check_invariants(s)
    assert ok, f"迁移后不变量仍违约：{bad}"
    assert pop["officials"] + pop["clerks"] == pop["size"]

    # 人为破坏不变量 → ensure 自愈
    pop["on_post"] += 12345
    ok2, _ = od.check_invariants(s)
    assert not ok2
    od.ensure_subpools(p)
    ok3, bad3 = od.check_invariants(s)
    assert ok3, f"自愈失败：{bad3}"


# ---------------------------------------------------------------- C-2 计价
def test_post_pay_units_weighting():
    """付款权数：在岗 1.0、待阙 `WAITING_PAY_RATIO`、祠禄 `SINECURE_PAY_RATIO`；
    官俸 == 权数 × 单价 × 磨勘指数。

    权数从常量读（不写死 0.5）——「待阙俸率」是**历史↔游戏性取中**的校准旋钮，
    测试应锁**公式**而非某个取值，否则每次调参都要改测试。
    """
    from content.data import SINECURE_PAY_RATIO, WAITING_PAY_RATIO
    s = GameState("史实")
    p = s.prefectures["两浙路"]
    pop = p["pops"]["官僚"]
    off = int(pop["officials"])
    pop["on_post"], pop["waiting"], pop["sinecure"] = off // 2, off // 4, off - off // 2 - off // 4
    expect = (off // 2 + WAITING_PAY_RATIO * (off // 4)
              + SINECURE_PAY_RATIO * pop["sinecure"])
    assert abs(od.route_pay_units(p) - expect) < 1e-9
    cash, by_route = s.calc_official_cash()
    from content.data import OFFICIAL_PAY_PER_MONTH
    assert abs(by_route["两浙路"]
               - od.route_pay_units(p) * OFFICIAL_PAY_PER_MONTH * s.official_rank_index) < 1e-6


def test_rank_index_raises_pay_and_is_capped():
    """磨勘：品阶上浮抬高人均俸禄，且有封顶（防 200 年后爆炸）。"""
    from core.officialdom import RANK_INDEX_CAP, _annual_rank_up
    s = GameState("史实")
    cash0, _ = s.calc_official_cash()
    _annual_rank_up(s, [])
    cash1, _ = s.calc_official_cash()
    assert cash1 > cash0, "磨勘未抬高俸禄"
    for _ in range(500):
        _annual_rank_up(s, [])
    assert s.official_rank_index <= RANK_INDEX_CAP + 1e-9, "磨勘指数未封顶"


# ---------------------------------------------------------------- C-3 铨选阀门
def test_posts_quota_is_derived_from_orgs_and_routes():
    """差遣定员 = 中央机构岗位 ＋ 路级定员 × 路数（岗位，非人——唯一合法的非 POP 官制存量）。"""
    s = GameState("史实")
    q = od.ensure_quota(s)
    central = sum(len(o.get("posts") or []) for o in s.central_orgs.values() if not o.get("abolished"))
    assert q == central + ROUTE_POST_QUOTA * len(s.prefectures)
    assert od.ensure_quota(s) == q, "ensure_quota 必须幂等"


def test_waiting_is_bounded_by_two_valves():
    """待阙不得无界堆积：有阙授职 ＋ 超额转祠禄，双阀把待阙压在「定员 × 系数」附近。"""
    s = GameState("史实")
    # 注入巨量待阙，模拟恩荫/科举长期超产
    for p in s.prefectures.values():
        pop = p["pops"]["官僚"]
        od.ensure_subpools(p)
        pop["waiting"] += 5_000
        pop["officials"] += 5_000
        pop["size"] += 5_000
    _run(s, 3)
    t = od.totals(s)
    cap = int(s.posts_quota * WAITING_SINECURE_MULT)
    assert t["waiting"] <= cap + 200, f"待阙 {t['waiting']} 未被阀门压住（上限 {cap}）"
    assert t["sinecure"] > 0, "超额待阙未转为祠禄"
    assert t["on_post"] <= s.posts_quota, "在岗数不得超定员"


def test_retire_transfers_to_gentry_and_conserves_pop():
    """致仕（出口轴）：在岗 → 士绅，ΣPOP 严格不变（修复"被裁的人凭空消失"）。"""
    from core.officialdom import _annual_retire
    s = GameState("史实")
    p0 = _pop_total(s)
    off0 = od.totals(s)["officials"]
    shen0 = sum(p["pops"]["士绅"]["size"] for p in s.prefectures.values())
    n = _annual_retire(s, [])
    assert n > 0
    assert od.totals(s)["officials"] == off0 - n
    assert sum(p["pops"]["士绅"]["size"] for p in s.prefectures.values()) == shen0 + n
    assert _pop_total(s) == p0, f"致仕破了 ΣPOP：{p0} → {_pop_total(s)}"


def test_yinben_conserves_pop():
    """恩荫（入口轴）：士绅 → 官僚待阙，ΣPOP 不变。"""
    from core.officialdom import _triennial_yinben
    s = GameState("史实")
    p0 = _pop_total(s)
    w0 = od.totals(s)["waiting"]
    n = _triennial_yinben(s, [])
    assert n > 0
    assert od.totals(s)["waiting"] == w0 + n
    assert _pop_total(s) == p0, f"恩荫破了 ΣPOP：{p0} → {_pop_total(s)}"


def test_clan_growth_is_explicit_population_and_office_transfer():
    """宗室：复利新增人丁**显式**记入人口总账；入官是士绅 → 官僚的转移（ΣPOP 守恒）。"""
    from core.officialdom import _annual_clan
    s = GameState("史实")
    od.ensure_clan(s)
    clan0 = od.clan_total(s)
    pop0 = s.population
    p0 = _pop_total(s)
    off0 = od.totals(s)["officials"]
    shen0 = sum(p["pops"]["士绅"]["size"] for p in s.prefectures.values())
    births = _annual_clan(s, [])
    assert births > 0
    assert od.clan_total(s) > clan0, "宗室未复利增长"
    # 新增人丁必须同时进 population（否则身份式 ΣPOP+流民 == population 在月内破裂）
    assert s.population == pop0 + births, f"宗室人丁未记入人口总账：{pop0} → {s.population}"
    # ΣPOP 只应因“人丁自然增长”增加 births；宗室入官是转移，不得额外增减
    assert _pop_total(s) == p0 + births, f"宗室入官破了 ΣPOP：{p0} → {_pop_total(s)}"
    # 入官是 士绅 → 官僚 的转移：官僚侧增加，士绅侧等额减少（已扣除新生的 births）
    entered = od.totals(s)["officials"] - off0
    shen_delta = sum(p["pops"]["士绅"]["size"] for p in s.prefectures.values()) - shen0
    assert entered > 0, "宗室未入官"
    assert shen_delta == births - entered, \
        f"入官转移两侧不等额：士绅Δ={shen_delta} 应={births}-{entered}"


def test_clan_stipend_is_conserving_transfer():
    """宗室俸禄（L2c sink）：内帑 −paid、士绅 wealth +paid、ΔM_ALL == 0；内帑不足按实付。"""
    s = GameState("史实")
    od.ensure_clan(s)
    s.imperial_treasury = 10_000_000
    m0, w0, imp0 = money.m_all(s), _gentry_wealth(s), s.imperial_treasury
    paid = _settle_clan(s, [])
    clan = od.clan_total(s)
    assert paid == int(clan * CLAN_PAY_PER_MONTH)
    assert s.imperial_treasury == imp0 - paid
    assert _gentry_wealth(s) - w0 == paid, "宗室俸禄必须全额落到士绅 POP wealth"
    assert money.m_all(s) - m0 == 0, "内帑 → 士绅 是纯转移，不得改变 M_ALL"
    assert s.statistics.get("clan_arrears", 0) == 0

    # 内帑枯竭：按实付、不穿底、欠支入科目
    s.imperial_treasury = 1
    m1 = money.m_all(s)
    paid2 = _settle_clan(s, [])
    assert paid2 == 1 and s.imperial_treasury == 0
    assert s.statistics["clan_arrears"] == int(clan * CLAN_PAY_PER_MONTH) - 1
    assert money.m_all(s) - m1 == 0


def test_reduce_office_returns_officials_to_gentry():
    """诏令「裁汰冗员」：被裁的官回**士绅**（ΣPOP 守恒），且优先裁祠禄/待阙。"""
    from core.settlement_steps import _apply_decree_effect
    s = GameState("史实")
    p = s.prefectures["两浙路"]
    pop = p["pops"]["官僚"]
    od.ensure_subpools(p)
    pop["on_post"], pop["waiting"], pop["sinecure"] = 100, 100, 100
    pop["officials"], pop["size"] = 300, 300 + int(pop["clerks"])
    p0 = _pop_total(s)
    shen0 = p["pops"]["士绅"]["size"]
    sin0, wait0 = pop["sinecure"], pop["waiting"]

    _apply_decree_effect(s, {"effects": {"reduce_office": 100_000}}, [])

    assert _pop_total(s) == p0, "裁汰冗员破了 ΣPOP（被裁者凭空消失）"
    assert p["pops"]["士绅"]["size"] > shen0, "被裁官员未回流士绅"
    # 裁冗先从冗处裁：祠禄与待阙先减，在岗尽量不动
    assert pop["sinecure"] < sin0 or pop["waiting"] < wait0
    ok, bad = od.check_invariants(s)
    assert ok, f"裁汰后子池不变量违约：{bad}"


# ---------------------------------------------------------------- C-4 免役税基
def test_poll_tax_base_is_farm_pop_only():
    """役钱税基 = `农` POP（乡村主户）；`士绅`/`官僚`/`兵` 免役，不在税基内。"""
    s = GameState("史实")
    tb = s.tax_base_summary()
    farm = sum(p["pops"]["农"]["size"] for p in s.prefectures.values())
    exempt = sum(p["pops"][k]["size"] for p in s.prefectures.values()
                 for k in ("士绅", "官僚", "兵"))
    assert tb["taxable_pop"] == farm
    assert tb["exempt_pop"] == exempt
    total = sum(pop["size"] for p in s.prefectures.values() for pop in p["pops"].values())
    assert abs(tb["taxable_share"] + tb["exempt_share"] - (farm + exempt) / total) < 1e-6


def test_exempt_share_grows_poll_base_shrinks_over_time():
    """§13.6「最有价值的一条」：冗官膨胀 → 免役人口↑ → **役钱税基萎缩**。

    这条链此前完全不可观测（役钱只报一个数）。现在必须能同时看到：
    免役占比上升、纳税（农）占比下降、役钱随税基下降。
    """
    s = GameState("史实")
    tb0 = s.tax_base_summary()
    _run(s, 240, seed=7)
    tb1 = s.tax_base_summary()
    assert tb1["exempt_share"] > tb0["exempt_share"], \
        f"免役占比未上升：{tb0['exempt_share']} → {tb1['exempt_share']}"
    assert tb1["taxable_share"] < tb0["taxable_share"], \
        f"纳税占比未下降：{tb0['taxable_share']} → {tb1['taxable_share']}"
    assert tb1["poll_tax"] < tb0["poll_tax"], \
        f"役钱未随税基萎缩：{tb0['poll_tax']} → {tb1['poll_tax']}"
    assert tb1["redundant_officials"] > 0


def test_official_service_tax_recorded_and_conserving():
    """官户助役钱：实收额入 `tax_breakdown["official_service"]`，且**只从官僚 POP wealth 扣**。

    口径纪律：实收 ≤ 应纳，不得凭空生钱（`_tax_left` 反映欠缴）。
    """
    s = GameState("史实")
    _run(s, 1, seed=7)
    got = int((s.tax_breakdown or {}).get("official_service", -1))
    assert got >= 0, "助役钱未入 tax_breakdown 科目（原先只有支出侧、玩家看不到）"
    from content.data import OFFICIAL_SERVICE_TAX_RATIO
    off_cash, _ = s.calc_official_cash()
    clk_cash, _ = s.calc_clerk_cash()
    nominal = int((off_cash + clk_cash) * OFFICIAL_SERVICE_TAX_RATIO)
    assert 0 <= got <= nominal, f"助役钱实收越界：{got} 应纳上限 {nominal}"


def test_tax_base_summary_is_read_only_view():
    """派生视图必须与 POP 权威源一致（不得成为第二本账）。"""
    s = _run(GameState("史实"), 12, seed=7)
    tb = s.tax_base_summary()
    t = od.totals(s)
    assert tb["officials"] == t["officials"]
    assert tb["awaiting_posts"] == t["waiting"]
    assert tb["redundant_officials"] == max(0, t["officials"] - t["posts_quota"])



# ---------------------------------------------------------------- C-6 科举离散科次
def test_exam_is_discrete_cohort_not_monthly_drip():
    """科举是**离散科次**（每 3 年一次、一次数百人），不是每月连续小额入仕。

    科次月：官额 = −致仕 ＋ 取士（净增，且量级为数百）；
    非科次的正月：官额只有致仕（净减）。
    """
    from content.data import EXAM_COHORT_SIZE

    s = GameState("史实")
    s._economy_ai = {"科举": "中"}
    off0 = od.totals(s)["officials"]
    _run(s, 1, seed=7)                       # 1101-01：科次年正月
    off1 = od.totals(s)["officials"]
    cohort = int((s.exam or {}).get("last_cohort", 0))
    assert cohort > 0, "科次年正月未取士"
    assert off1 > off0, f"科次月官额应净增：{off0} → {off1}"
    assert abs(cohort - EXAM_COHORT_SIZE["中"]) <= EXAM_COHORT_SIZE["中"] * 0.35, \
        f"一届取士额偏离设定量级：{cohort} vs 目标 {EXAM_COHORT_SIZE['中']}"
    assert len(s.exam.get("cohorts", [])) == 1, "未记录科次台账（同年载体）"

    # 非科次年（1102-01）只有致仕 → 官额净减
    off_a = od.totals(s)["officials"]
    _run(s, 12, seed=7)                      # 1102-01
    off_b = od.totals(s)["officials"]
    assert off_b < off_a, f"非科次年正月官额应只减（致仕）：{off_a} → {off_b}"
    assert len(s.exam["cohorts"]) == 1, "非科次年不应产生新科次"


def test_exam_cohort_conserves_pop_and_lands_in_waiting():
    """科次取士是 农/士绅 → 官僚 的**转移**（ΣPOP 守恒），且落在**待阙**池。"""
    from core.officialdom import _triennial_exam
    s = GameState("史实")
    s._economy_ai = {"科举": "中"}
    p0 = _pop_total(s)
    w0 = od.totals(s)["waiting"]
    off0 = od.totals(s)["officials"]
    n = _triennial_exam(s, [])
    assert n > 0
    t = od.totals(s)
    assert t["officials"] == off0 + n
    assert t["waiting"] == w0 + n, "新科进士应先待阙（不会立刻有差遣）"
    assert _pop_total(s) == p0, f"科次破了 ΣPOP：{p0} → {_pop_total(s)}"
    ok, bad = od.check_invariants(s)
    assert ok, f"科次后子池不变量违约：{bad}"


# ---------------------------------------------------------------- 长局综合
def test_officialdom_240_month_trajectory():
    """240 月：官额与官俸显著增长、待阙有界、祠禄承接、人口账零偏差、子池不变量恒成立。

    这是"冗官"作为机制的端到端验收（§13.5 有机定义：产出 > 差遣需求）。
    """
    s = GameState("史实")
    off0 = od.totals(s)["officials"]
    cash0, _ = s.calc_official_cash()
    worst = 0
    for _ in range(240):
        s._economy_ai = _ECO
        run_monthly_settlement(s, seed_offset=7)
        worst = max(worst, abs(_pop_total(s) - s.population))
        ok, bad = od.check_invariants(s)
        assert ok, f"月 {s.turn} 子池不变量违约：{bad[:2]}"

    t = od.totals(s)
    cash1, _ = s.calc_official_cash()
    assert t["officials"] > off0 * 1.5, f"冗官未膨胀：{off0} → {t['officials']}"
    assert t["redundant"] > 0, "冗官（产出超差遣需求）应 > 0"
    assert t["waiting"] <= int(s.posts_quota * WAITING_SINECURE_MULT) + 200
    assert t["sinecure"] > 0
    assert cash1 > cash0 * 1.2, f"官俸未随冗官增长：{cash0:.0f} → {cash1:.0f}"
    assert worst == 0, f"人口总账出现偏差：{worst}"
    assert not s.game_over
