# -*- coding: utf-8 -*-
"""阶段 C-5（吏制）回归测试：吏额脱离官×8 · 吏禄→陋规 · 把持度 · 吏怨 ·「冗而不足」。

设计依据：`_dev_tools/game-docs/docs/宋代官制与三冗设计.md` §16（＋政务量 §11 的务实子集）。
实现单一权威源：`core/clerks.py`。

被断言的缺陷（修复前实证 §16.2）：
  · 吏额 `clerks = officials × 8` —— **静态常数**，不随政务量变动；
  · 吏禄 3.5 贯/月 vs 生计线 7.2 贯/月，**吏禄不足没有任何后果**；
  · 把持度 / 吏怨 / 陋规**三个机制全部不存在** —— 吏只是"每月领 2 贯的人数"。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import clerks as ck  # noqa: E402
from core import money  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402
from content.data import EXACTION_MAX_SHARE  # noqa: E402

_ECO = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
        "窖银": "小", "城市化": "中", "回乡": "无", "科举": "中"}


def _pop_total(s):
    return (sum(pop["size"] for p in s.prefectures.values() for pop in p["pops"].values())
            + s.refugee_count)


def _run(s, months, seed=7):
    for _ in range(months):
        s._economy_ai = _ECO
        run_monthly_settlement(s, seed_offset=seed)
    return s


def _pool_wealth(s, route, keys=("农", "工匠", "商人")):
    p = s.prefectures[route]
    return sum(int(p["pops"][k]["wealth"]) for k in keys)


# ---------------------------------------------------------------- 吏额
def test_quota_is_workload_driven_and_zero_change_at_start():
    """吏额基数由**开局吏额**锚定（零数值变更），此后由政务量驱动而非常数 `官 × 8`。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    base = {r: int(p["pops"]["官僚"]["clerks"]) for r, p in s.prefectures.items()}
    total_clerk0 = sum(base.values())
    _run(s, 1, seed=7)
    t = ck.totals(s)
    assert t["quota"] == total_clerk0, f"开局编制应等于开局吏额：{t['quota']} vs {total_clerk0}"

    # 人为抬高某路政务量（人口翻倍）→ 该路编制应上升
    r0 = "两浙路"
    p = s.prefectures[r0]
    w_before = p["clerks_detail"]["quota"]
    p["population"] = int(p["population"] * 3)
    ck.settle_clerks(s, [])
    assert p["clerks_detail"]["quota"] > w_before, \
        f"政务量上升后编制未变：{w_before} → {p['clerks_detail']['quota']}"


def test_staffing_change_conserves_pop_and_swaps_with_farmers():
    """吏额增减必须与 `农` POP **对转**：ΣPOP 守恒，且两者反向变化。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    p = s.prefectures["两浙路"]
    p0 = _pop_total(s)
    farm0 = int(p["pops"]["农"]["size"])
    clerk0 = int(p["pops"]["官僚"]["clerks"])
    # 把编制抬到远超现额 → 下月必然扩编（编制惯性）
    p["clerks_detail"]["establishment"] = clerk0 + 5_000
    p["clerks_detail"]["quota"] = clerk0 + 5_000
    ck.settle_clerks(s, [])
    farm1 = int(p["pops"]["农"]["size"])
    clerk1 = int(p["pops"]["官僚"]["clerks"])
    assert clerk1 > clerk0, "编制上调后吏额未增"
    assert farm1 < farm0, "扩吏未从农户口抽调"
    assert farm1 - farm0 == -(clerk1 - clerk0), "吏/农未等额对转"
    assert _pop_total(s) == p0, f"吏额调整破了 ΣPOP：{p0} → {_pop_total(s)}"

    # 反向：裁编 → 吏回农，ΣPOP 仍守恒
    farm2, clerk2 = farm1, clerk1
    p["clerks_detail"]["establishment"] = clerk1 - 5_000
    p["clerks_detail"]["quota"] = clerk1 - 5_000
    ck.settle_clerks(s, [])
    farm3 = int(p["pops"]["农"]["size"])
    clerk3 = int(p["pops"]["官僚"]["clerks"])
    assert clerk3 < clerk2 and farm3 > farm2
    assert farm3 - farm2 == -(clerk3 - clerk2)
    assert _pop_total(s) == p0, f"裁吏破了 ΣPOP：{p0} → {_pop_total(s)}"


def test_redundant_clerks_arise_from_entitlement_growth():
    """**冗吏**来自编制自我膨胀（世袭/请托，"吏额有增无损"），不来自政务量增长。"""
    s = _run(GameState("史实"), 240, seed=7)
    t = ck.totals(s)
    assert t["establishment"] > t["quota"], \
        f"编制存量应超过当期需求（冗吏）：{t['establishment']} vs {t['quota']}"
    assert t["redundant"] > 0, "冗吏为 0——编制自我膨胀未生效"
    assert 0 < t["redundant_rate"] < 0.5, f"冗吏率异常：{t['redundant_rate']}"


# ---------------------------------------------------------------- 陋规（守恒）
def test_extortion_is_conserving_transfer(monkeypatch):
    """陋规是**纯转移**：民间三池 −X，官僚 POP wealth +X，ΔM_ALL == 0。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    p = s.prefectures["两浙路"]
    m0 = money.m_all(s)
    before = _pool_wealth(s, "两浙路")
    bureau0 = int(p["pops"]["官僚"]["wealth"])
    r = ck._extort(s, p, [])
    assert r["taken"] > 0, "吏禄不足却未产生陋规"
    after = _pool_wealth(s, "两浙路")
    bureau1 = int(p["pops"]["官僚"]["wealth"])
    assert before - after == r["taken"], "民间扣减额与记录额不符"
    assert bureau1 - bureau0 == r["taken"], "陋规未全额进入官僚 POP"
    assert money.m_all(s) - m0 == 0, "陋规改变了 M_ALL（造币或销毁）"


def test_extortion_capped_by_pool_and_never_negative():
    """民间池枯竭时抽取受 `EXACTION_MAX_SHARE` 限制，且不穿底、不造币。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    p = s.prefectures["两浙路"]
    for k in ("农", "工匠", "商人"):
        p["pops"][k]["wealth"] = 100
    m0 = money.m_all(s)
    r = ck._extort(s, p, [])
    assert r["taken"] <= int(300 * EXACTION_MAX_SHARE) + 3, f"抽取越界：{r['taken']}"
    assert all(int(p["pops"][k]["wealth"]) >= 0 for k in ("农", "工匠", "商人"))
    assert money.m_all(s) - m0 == 0


def test_extortion_lowers_mood():
    """陋规的**真正代价**是民心：抽得越多，民心掉得越多。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    p = s.prefectures["两浙路"]
    mood0 = float(p["mood"])
    ck._extort(s, p, [])
    assert float(p["mood"]) < mood0, f"陋规未损伤民心：{mood0} → {p['mood']}"


# ---------------------------------------------------------------- 吏怨 / 把持度
def test_grievance_tracks_structural_pay_gap_and_persists():
    """吏怨由**制度性俸薄**驱动：缺俸时为正且不归零；俸禄补足后回落。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    p = s.prefectures["两浙路"]
    d = p["clerks_detail"]
    d["grievance"] = 0.0
    for _ in range(40):
        ck._extort(s, p, [])
    assert d["grievance"] > 1.0, f"吏禄不足却无吏怨：{d['grievance']}"
    assert d["grievance"] < 100.0


def test_high_pay_reduces_grievance(monkeypatch):
    """反证：把吏禄提到生计线以上 → 缺口归零 → 吏怨回落（"花钱买治理"成立）。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    p = s.prefectures["两浙路"]
    d = p["clerks_detail"]
    for _ in range(60):
        ck._extort(s, p, [])
    high = float(d["grievance"])
    monkeypatch.setattr(ck, "CLERK_PAY_PER_MONTH", 20.0)     # 吏禄远超生计线
    for _ in range(80):
        ck._extort(s, p, [])
    assert float(d["grievance"]) < high, \
        f"提高吏禄后吏怨未回落：{high:.1f} → {d['grievance']:.1f}"


def test_grip_discounts_decree_execution():
    """把持度 → 诏令执行率折扣（§16.4 吏强官弱），且把持越高折扣越大。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    for p in s.prefectures.values():
        p["clerks_detail"]["grip"] = 0.10
    m_low = ck.decree_execution_mult(s)
    for p in s.prefectures.values():
        p["clerks_detail"]["grip"] = 0.70
    m_high = ck.decree_execution_mult(s)
    assert m_low < 1.0 and m_high < m_low, f"把持度未压低执行率：{m_low} → {m_high}"


def test_effective_capacity_and_quality_label():
    """「冗而不足」：有效吏力 = 吏数 × (1 − 吏怨/100) < 吏数；四档定性随把持/吏怨变化。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    for p in s.prefectures.values():
        p["clerks_detail"]["grievance"] = 40.0
        p["clerks_detail"]["grip"] = 0.5
    t = ck.totals(s)
    assert t["effective"] < t["clerks"], "有效吏力未低于吏数"
    assert abs(t["effective"] - int(t["clerks"] * 0.6)) <= t["clerks"] // 20
    assert t["quality"] in ("案牍清明", "吏习其事", "吏胥弄权", "吏弊丛生")
    for p in s.prefectures.values():
        p["clerks_detail"]["grievance"] = 80.0
        p["clerks_detail"]["grip"] = 0.8
    assert ck.totals(s)["quality"] == "吏弊丛生"


def test_backlog_gain_replaces_random_with_capacity_shortfall():
    """积压增量改由 `W − C_eff` 驱动：吏怨越高，净积压越大（不再是无载体随机）。"""
    s = GameState("史实")
    ck.ensure_detail(s)
    r = "两浙路"
    p = s.prefectures[r]
    p["clerks_detail"]["grievance"] = 0.0
    low = ck.backlog_gain(s, r)
    p["clerks_detail"]["grievance"] = 95.0
    high = ck.backlog_gain(s, r)
    assert high > low >= 0.0, f"吏怨未推高积压：{low} → {high}"


def test_settle_clerks_runs_and_reports():
    """月度结算确实执行吏制步，且派生指标齐全（防"写了没接上"）。"""
    s = GameState("史实")
    log = _run(GameState("史实"), 1, seed=7) and None
    s._economy_ai = _ECO
    lg = run_monthly_settlement(s, seed_offset=7)
    assert any("吏制" in str(x) or "吏禄" in str(x) or "吏额" in str(x) for x in lg), \
        "月结算日志未见吏制记录"
    for key in ("clerks_total", "clerks_quota", "clerks_redundant", "clerks_grip",
                "clerks_grievance", "clerks_extortion", "clerks_quality"):
        assert key in s.statistics, f"statistics 缺 {key}"
    assert s.statistics["clerks_total"] > 0
