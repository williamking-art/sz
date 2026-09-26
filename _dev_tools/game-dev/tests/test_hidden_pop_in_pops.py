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
    """关掉逃户压力源（税率/民怨/灾荒），以便单独观察归籍一侧。"""
    s.commerce_tax_rate = 0.15
    s.population_satisfaction = 50


def _full_pressure(s):
    s.commerce_tax_rate = 0.30          # 税重项（基准 0.15 以上才产生压力）
    s.population_satisfaction = 0       # 民怨项拉满


def test_new_game_materializes_hidden_into_pops():
    """开局：镜像户数被物化进 `农.hidden`；`hidden_rem` 余数科目消灭；在籍口径不变。"""
    s = GameState("史实")
    assert _hidden_total(s) == 5_000_000 * 4, "设计锚：隐户 2000 万口"
    assert s.land["hidden_households"] == 5_000_000
    assert "hidden_rem" not in s.land, "以口记账后不再需要 ÷4 余数科目"
    # 在籍口径不变：隐户**不计入** population。
    # 注：开局 `population`（8000 万）与 `Σsize`（8075 万，含兵 75 万）本就不等，
    # 差额由首月 Step 10.5 校正——这是开局既有事实，与隐户无关（见 test_monthly_...）。
    assert s.population == 80_000_000
    assert s.population + _hidden_total(s) == 100_000_000, "总口 1 亿 = 在籍 8000 万 + 隐户 2000 万（设计锚）"


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
    assert s.land["hidden_households"] == hidden1 // 4, "镜像 = Σhidden // 4"


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
    assert s.land["hidden_households"] == hidden1 // 4


def test_mirror_matches_subsystem_and_is_not_ai_writable():
    """镜像与子池一致；AI/大臣**不得**直接改人口（白名单已移除该键）。"""
    from engine.state_applier import VALID_PATHS
    assert "land.hidden_households" not in VALID_PATHS
    assert "land.hidden_rate" in VALID_PATHS, "税率隐漏率与人口无关，保留可写"
    s = GameState("史实")
    assert s.land["hidden_households"] == _hidden_total(s) // 4


def test_legacy_save_migration_is_idempotent():
    """旧档（只有镜像、无子池）→ 幂等注入；重复调用不再变。"""
    s = GameState("史实")
    for p in s.prefectures.values():
        p["pops"]["农"]["hidden"] = 0          # 模拟旧档：人口未落在 POP 里
    s.land["hidden_households"] = 4_000_000
    assert ensure_hidden_in_pops(s) == 16_000_000
    assert _hidden_total(s) == 16_000_000
    assert ensure_hidden_in_pops(s) == 0, "幂等：已有子池则不动"
    assert _hidden_total(s) == 16_000_000


def test_demand_side_equivalent_to_old_household_mirror():
    """需求侧口径（总口 = 在籍 + 隐户口）与旧"镜像 × 4"等价，差仅来自户取整（≤3 口）。"""
    s = GameState("史实")
    hp = _hidden_total(s)
    assert hp > 0
    assert abs(hp - s.land["hidden_households"] * 4) <= 3


def test_monthly_settlement_absorbs_registry_into_population():
    """整月结算：Step 10.5 把归籍/逃籍净额吸收进在籍口径（`population == Σsize + 流民`）。"""
    s = GameState("史实")
    _full_pressure(s)
    run_monthly_settlement(s, 0)
    assert s.population == _pops_total(s) + s.refugee_count
