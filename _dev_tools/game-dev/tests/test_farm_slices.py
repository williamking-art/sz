# -*- coding: utf-8 -*-
"""B1a 农「职位子池 + 丁口维度」回归（2026-09-27 用户口径）。

用户口径：
  · "设一个自耕农庄来容纳自耕农跟富农还有贫农，地主的农庄容纳佃农跟地主，
     一个建筑不是只有一个职位的啊" → 农按**职位**分槽；
  · "引入受抚养人口的概念，这样能贴合'户'这个概念" → 人口按**丁/口**二分。

锁定：
  1. 恒等式（逐路）：`自耕农+富农+贫农+佃农 == 农.size`、`ding+kou == 农.size`；
  2. 两套划分**正交**（两个边际，不做交叉表）；
  3. 隐户 `hidden` 是**加法**子池，**不参与**上述恒等式（不在籍）；
  4. 幂等：`ensure_farm_slices` 重复调用不改变数值；旧档（无子池）可迁移且守恒；
  5. `adjust_farm_slices`：`农.size` 变化后按**现有比例**同步，丁率保持；
  6. 人为破坏可被 `check_farm_invariants` 捕获（断言不是摆设）。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data_constants import (  # noqa: E402
    DING_RATIO, POLL_TAX_NOMINAL_SHARE, TAX_POLL_RATIO,
)
from core.game_state import GameState  # noqa: E402
from core.pop_structure import (  # noqa: E402
    FARM_POSITIONS, adjust_farm_slices, check_farm_invariants, ding_of,
    ensure_farm_slices, kou_of, seed_farm_slices, service_ding_of,
    service_ding_total,
)


def _nong(p):
    return p["pops"]["农"]


def _pos_sum(p):
    return sum(int(_nong(p).get(k, 0) or 0) for k in FARM_POSITIONS)


def test_new_game_slices_satisfy_both_identities():
    s = GameState("史实")
    assert check_farm_invariants(s) == [], check_farm_invariants(s)
    for p in s.prefectures.values():
        size = int(_nong(p)["size"])
        assert _pos_sum(p) == size
        assert ding_of(p) + kou_of(p) == size
        assert abs(ding_of(p) / max(size, 1) - DING_RATIO) < 0.01


def test_slices_are_idempotent():
    s = GameState("史实")
    before = {n: {k: int(_nong(p).get(k, 0) or 0) for k in FARM_POSITIONS + ("ding", "kou")}
              for n, p in s.prefectures.items()}
    assert ensure_farm_slices(s) == 0, "开局已一致，重复调用不应修整任何一路"
    for n, p in s.prefectures.items():
        assert {k: int(_nong(p).get(k, 0) or 0) for k in FARM_POSITIONS + ("ding", "kou")} == before[n]


def test_legacy_migration_redistributes_without_changing_size():
    """旧档（无子池）→ 幂等迁移；**只改子池不改 size**，两套恒等式随即成立。"""
    s = GameState("史实")
    sizes = {}
    for n, p in s.prefectures.items():
        sizes[n] = int(_nong(p)["size"])
        for k in FARM_POSITIONS + ("ding", "kou"):
            _nong(p).pop(k, None)
    assert ensure_farm_slices(s) == len(s.prefectures)
    assert check_farm_invariants(s) == []
    for n, p in s.prefectures.items():
        assert int(_nong(p)["size"]) == sizes[n], "迁移不得改动 size"
        assert _pos_sum(p) == sizes[n]


def test_adjust_keeps_proportion_and_ding_ratio():
    """`农.size` 变化（跨类流动/人口增减）→ 子池按现有比例同步，恒等式保持。"""
    s = GameState("史实")
    name = next(iter(s.prefectures))
    p = s.prefectures[name]
    nong = _nong(p)
    nong["size"] = int(nong["size"]) + 100_000          # 农 +10 万
    adjust_farm_slices(p)
    assert check_farm_invariants(s) == []
    assert int(nong["size"]) == _pos_sum(p)
    assert abs(ding_of(p) / int(nong["size"]) - DING_RATIO) < 0.01


def test_hidden_is_additive_and_orthogonal():
    """隐户（加法子池）增减**不影响**职位/丁口恒等式（不在籍、不参与划分）。"""
    s = GameState("史实")
    name = next(iter(s.prefectures))
    p = s.prefectures[name]
    size = int(_nong(p)["size"])
    _nong(p)["hidden"] = int(_nong(p).get("hidden", 0) or 0) + 50_000
    assert check_farm_invariants(s) == []
    assert _pos_sum(p) == size, "隐户不进职位恒等式"
    assert ding_of(p) + kou_of(p) == size


def test_checker_catches_broken_invariants():
    """断言有效：人为破坏恒等式必须被捕获（防"检查器恒真"）。"""
    s = GameState("史实")
    name = next(iter(s.prefectures))
    _nong(s.prefectures[name])["自耕农"] = int(_nong(s.prefectures[name])["自耕农"]) + 1
    bad = check_farm_invariants(s)
    assert any("Σ职位" in b for b in bad), bad
    seed_farm_slices(s.prefectures[name])                 # 复位
    assert check_farm_invariants(s) == []
    _nong(s.prefectures[name])["ding"] = int(_nong(s.prefectures[name])["ding"]) + 1
    bad2 = check_farm_invariants(s)
    assert any("丁+口" in b for b in bad2), bad2


# ---------------------------------------------------------------
# B1b 税负分层：役钱税基 = 应役丁（佃农免役）
# ---------------------------------------------------------------
def test_service_ding_excludes_tenants():
    """应役丁 = `ding × (1 − 佃农占比)`；佃农占比↑ → 税基↓（土地兼并的财政后果）。"""
    s = GameState("史实")
    p = s.prefectures[next(iter(s.prefectures))]
    nong = _nong(p)
    size, ding, tenant = int(nong["size"]), int(nong["ding"]), int(nong["佃农"])
    assert service_ding_of(p) == int(ding * (1.0 - tenant / size))
    nong["佃农"] = min(size, tenant + max(1, int(size * 0.1)))
    assert service_ding_of(p) < int(ding * (1.0 - tenant / size)), "佃农变多 ⇒ 应役丁变少"


def test_hidden_is_not_in_tax_base():
    """隐户不落籍：既不在 `size`、也不在 `ding` → 增减隐户**不影响**税基。"""
    s = GameState("史实")
    p = s.prefectures[next(iter(s.prefectures))]
    before = service_ding_total(s)
    _nong(p)["hidden"] = int(_nong(p).get("hidden", 0) or 0) + 500_000
    assert service_ding_total(s) == before


def test_poll_tax_amount_equal_to_b05_baseline():
    """**保绝对量**：B1b（税基=应役丁、税率 `TAX_POLL_RATIO`）与 B0.5（税基=农全额、税率 0.08）等额。

    这条锁定"(ii) 保财政绝对量"，防止后续调参把它悄悄改坏。
    """
    s = GameState("史实")
    farm = sum(p["pops"]["农"]["size"] for p in s.prefectures.values())
    new_amt = service_ding_total(s) * TAX_POLL_RATIO
    old_amt = farm * POLL_TAX_NOMINAL_SHARE
    assert abs(new_amt - old_amt) / old_amt < 0.01, \
        f"役钱绝对量漂移：新={new_amt:,.0f} 旧={old_amt:,.0f}"
