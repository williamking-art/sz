# -*- coding: utf-8 -*-
"""隐户入 POP 回归（方案 A，2026-09-27）。

背景：隐户（不落籍人口）原先是"**第 7 类动态人口池**"——`land.hidden_households`（户）
＋ `land.hidden_rem`（÷4 余数）。现按用户拍板的**方案 A** 并入 **`农` POP 的加法子池
`hidden`（口）**：POP 挂载律条 1（"人"必须落在 POP 上）与条 4（禁平行存量账本）。

本文件锁定：
  1. **开局物化**：`land` 初值 500 万户 → 各路 `农.hidden` 合计 2000 万口；`hidden_rem` 科目不存在；
  2. **在籍口径不变**：`state.population` 不含隐户（不落籍、不纳税）；
  3. 逃籍／归籍**逐路局部守恒**：`Σ六类 size ＋ Σ农.hidden` 不变；
  4. **镜像一致**：`land.hidden_households == Σ农.hidden // 4`（该键降为派生读数）；
  5. 需求侧口径不回归：与旧"镜像 × 4"等价（差 ≤3 口，来自户取整）；
  6. 旧档迁移：只有镜像、无子池 → `ensure_hidden_in_pops()` 幂等注入；
  7. **AI 不得直接改人口**：`land.hidden_households` 已移出 `state_applier.VALID_PATHS`。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data_constants import PERSONS_PER_HOUSEHOLD as PPH  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402
from core.settlement_imperial import (  # noqa: E402
    _hidden_people, _settle_hidden_pop, ensure_hidden_in_pops,
)


def _pops_total(st) -> int:
    return sum(int(pop.get("size", 0) or 0)
               for p in st.prefectures.values() for pop in p["pops"].values())


def _hidden_total(st) -> int:
    return sum(_hidden_people(p) for p in st.prefectures.values())


def _no_pressure(s):
    """关掉逃户压力源（税率/民怨/**缺粮**），以便单独观察归籍一侧。

    S6 经用户 2026-10-01 二次细化后，逃籍有**两条独立腿**：
      · 缺粮腿（人数驱动，无魔数）：`settlement_common.food_insecure_headcount`
        （自有粮 ＋ 购粮能力）判"吃不上饭的人数"，1:1 派生逃籍；
      · 税重/民怨腿（压力率驱动，沿用原口径）：由 `commerce_tax_rate` /
        `population_satisfaction` 折算。
    归籍单测必须**同时排除两条腿**，否则"清丈是否使隐户回流"会被逃籍反向抵消
    （实测：即使公储充足，只要某路有人吃不上饭，hidden 就不降反升）。
    故本助手除归零税重/民怨外，还把各路 POP 补粮补钱到"人人有饭可吃"。
    """
    from content.data import GRAIN_CONSUME_PER_CAPITA
    s.commerce_tax_rate = 0.15
    s.population_satisfaction = 50
    _no_grain_pressure(s, GRAIN_CONSUME_PER_CAPITA)


def _no_grain_pressure(s, per_capita=None):
    """把各路 POP 补到"人人有饭"（消除缺粮腿），并把公储补到≥1 个月。

    补**户存**是必需的：缺粮腿判的是 POP 自有粮 ＋ 购粮能力（不是公储）；
    公储一并补齐只是保持与旧版断言的语义连续。
    """
    if per_capita is None:
        from content.data import GRAIN_CONSUME_PER_CAPITA as per_capita
    try:
        _total, _by_route = s.calc_army_grain()
    except Exception:                                   # noqa: BLE001
        _by_route = {}
    for name, p in s.prefectures.items():
        for _k, _slot in (p.get("pops") or {}).items():
            if not isinstance(_slot, dict):
                continue
            per = float(per_capita.get(_k, 0.5))
            size = int(_slot.get("size", 0) or 0)
            # 自有粮补到 3 个月口粮（远超 1 个月，粮荒腿确定不触发）
            _slot["grain"] = max(float(_slot.get("grain", 0) or 0), size * per * 3.0)
        need = 0.0
        for _k, _v in (p.get("pops") or {}).items():
            if isinstance(_v, dict):
                need += int(_v.get("size", 0) or 0) * float(per_capita.get(_k, 0.5))
        need += max(0.0, float(_by_route.get(name, 0.0) or 0.0))
        if need > 0:
            _want = need * 2.0                          # 公储 2 个月，远离告急
            _cur = max(0.0, float(p.get("storage", 0) or 0)) \
                + max(0.0, float(p.get("changping_stock", 0) or 0))
            if _cur < _want:
                p["storage"] = int(_want - max(0.0, float(p.get("changping_stock", 0) or 0)))


def _full_pressure(s):
    s.commerce_tax_rate = 0.30          # 税重项（基准 0.15 以上才产生压力）
    s.population_satisfaction = 0       # 民怨项拉满


def test_new_game_materializes_hidden_into_pops():
    """开局：镜像户数被物化进 `农.hidden`；`hidden_rem` 余数科目消灭；在籍口径不变。"""
    s = GameState("史实")
    assert _hidden_total(s) == 5_000_000 * PPH, "设计锚：隐户 2500 万口（500 万户 × 户均 5 口）"
    assert s.land["hidden_households"] == 5_000_000
    assert "hidden_rem" not in s.land, "以口记账后不再需要户↔口余数科目"
    # 在籍口径不变：隐户**不计入** population。
    # 注：开局 `population`（1 亿）与 `Σsize`（1.0075 亿，含兵 75 万）本就不等，
    # 差额由首月 Step 10.5 校正——这是开局既有事实，与隐户无关（见 test_monthly_...）。
    assert s.population == 100_000_000
    assert s.population + _hidden_total(s) == 125_000_000, "总口 1.25 亿 = 在籍 1 亿 + 隐户 2500 万"


def test_flee_is_route_local_and_pop_conserving():
    """逃籍：来源池 size 减、同路 `农.hidden` 增；总口守恒；在籍 population 不被本步改写。"""
    s = GameState("史实")
    sizes0, hidden0, pop0 = _pops_total(s), _hidden_total(s), s.population
    _full_pressure(s)
    _settle_hidden_pop(s, [])
    hidden1 = _hidden_total(s)
    assert hidden1 > hidden0, "税重 + 民怨拉满应产生逃户"
    assert _pops_total(s) == sizes0 - (hidden1 - hidden0), "Σsize 与 hidden 此消彼长（逐路同额）"
    assert _pops_total(s) + hidden1 == sizes0 + hidden0, "总口守恒"
    assert s.population == pop0, "本步不改在籍人口（月末 Step 10.5 才校正）"
    assert s.land["hidden_households"] == hidden1 // PPH, "镜像 = Σhidden // 户均口数"


def test_return_to_registry_moves_hidden_back_to_farm():
    """归籍（清丈）：`农.hidden` 减、`农.size` 增，两侧同额，总口不变。"""
    s = GameState("史实")
    _full_pressure(s)
    _settle_hidden_pop(s, [])                 # 先造出一批隐户
    _no_pressure(s)                           # 关掉逃户一侧，隔离归籍
    sizes0, hidden0 = _pops_total(s), _hidden_total(s)
    s.land["survey"] = 1                      # 清丈 → 归籍率提高
    _settle_hidden_pop(s, [])
    hidden1 = _hidden_total(s)
    assert hidden1 < hidden0, "清丈应使隐户归籍"
    assert _pops_total(s) == sizes0 + (hidden0 - hidden1), "归籍人口全数回到 `农`（同额）"
    assert _pops_total(s) + hidden1 == sizes0 + hidden0, "总口守恒"
    assert s.land["hidden_households"] == hidden1 // PPH


def test_mirror_matches_subsystem_and_is_not_ai_writable():
    """镜像与子池一致；AI/大臣**不得**直接改人口（白名单已移除该键）。"""
    from engine.state_applier import VALID_PATHS
    assert "land.hidden_households" not in VALID_PATHS
    assert "land.hidden_rate" in VALID_PATHS, "税率隐漏率与人口无关，保留可写"
    s = GameState("史实")
    assert s.land["hidden_households"] == _hidden_total(s) // PPH


def test_legacy_save_migration_is_idempotent():
    """旧档（只有镜像、无子池）→ 幂等注入；重复调用不再变。"""
    s = GameState("史实")
    for p in s.prefectures.values():
        p["pops"]["农"]["hidden"] = 0          # 模拟旧档：人口未落在 POP 里
    s.land["hidden_households"] = 4_000_000
    assert ensure_hidden_in_pops(s) == 4_000_000 * PPH
    assert _hidden_total(s) == 4_000_000 * PPH
    assert ensure_hidden_in_pops(s) == 0, "幂等：已有子池则不动"
    assert _hidden_total(s) == 4_000_000 * PPH


def test_demand_side_equivalent_to_old_household_mirror():
    """需求侧口径（总口 = 在籍 + 隐户口）与"镜像 × 户均口数"等价，差仅来自户取整。"""
    s = GameState("史实")
    hp = _hidden_total(s)
    assert hp > 0
    assert abs(hp - s.land["hidden_households"] * PPH) <= PPH - 1


def test_monthly_settlement_absorbs_registry_into_population():
    """整月结算：Step 10.5 把归籍/逃籍净额吸收进在籍口径（`population == Σsize + 流民`）。"""
    s = GameState("史实")
    _full_pressure(s)
    run_monthly_settlement(s, 0)
    assert s.population == _pops_total(s) + s.refugee_count


# ---------------------------------------------------------------
# B1c：隐户**有生产**（隐田产出 70% 自留 / 30% 庇护士绅）且**自产自食**
# ---------------------------------------------------------------
def test_hidden_has_production_and_self_feeds():
    """跑 12 个月：隐户产出与消费都必须进台账（修"隐户只有消费没有生产"）。"""
    s = GameState("史实")
    s.treasury = 10 ** 9
    for _ in range(12):
        run_monthly_settlement(s, 0)
    assert s.statistics.get("hidden_produce", 0) > 0, "隐户仍未生产（B1c 未生效）"
    assert s.granary_stats.get("hidden_feed", 0) > 0, "隐户消费未入台账"


def test_hidden_land_split_ratio_is_tunable(monkeypatch):
    """隐田分成比例**可调**（行为测试）：自留 1.0 → 全记隐户生产；自留 0.0 → 零。"""
    import content.data_constants as dc

    def _produce(share: float) -> int:
        monkeypatch.setattr(dc, "HIDDEN_LAND_TENANT_SHARE", share)
        s = GameState("史实")
        s.treasury = 10 ** 9
        for _ in range(12):
            run_monthly_settlement(s, 0)
        return int(s.statistics.get("hidden_produce", 0))

    full = _produce(1.0)
    zero = _produce(0.0)
    assert full > 0 and zero == 0, f"分成比例未生效：自留 1.0={full}，自留 0.0={zero}"
