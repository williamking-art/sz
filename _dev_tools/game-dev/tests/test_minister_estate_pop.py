# -*- coding: utf-8 -*-
"""大臣家产迁入 POP 的回归（POP 挂载律条 4，2026-09-27）。

锁定四件事：
  1. **不再有平行钱账本**：`core.money.ACCOUNTS` 不含 `estate_wealth`/`estate_hoard`，
     且 `M_ALL` 恰好等于 ACCOUNTS 各账户之和（不重复计、也不漏计）。
  2. **钱落在 POP**：家产的钱在 `prefectures[路].pops["士绅"]["estate"]`（持钱）与
     `["estate_hoard"]`（窖藏）里；`state.minister_estate` 只是具名镜像，二者恒等。
  3. **月度循环四条腿全是 POP 内部/阶层间守恒转移**：
     膨胀（官僚→士绅 estate）／奢侈（士绅 estate→工匠·商人）／窖藏（estate→estate_hoard）／
     收租（农→士绅 estate）——故 `M_ALL` 与 `m2` 逐月不变，`pop_money` 只按窖藏额减少。
  4. **迁移与脱敏**：旧档（无子池）载入后按镜像物化子池且 `M_ALL` 与旧口径一致；
     HTTP 快照剔除家产子池键（家产真值属隐藏数值）。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import ESTATE_INIT  # noqa: E402
from core import money  # noqa: E402
from core.estate_mechanic import (  # noqa: E402
    credit_estate, estate_slice_total, seize_estate, settle_minister_estate,
    sync_estate_slices,
)
from core.game_state import GameState  # noqa: E402

_ECON_AI = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
            "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无",
            "jiaozi_trust": "稳", "shortage": "平", "maritime": "平",
            "bank": "稳", "price_trend": "平"}


def _new_state():
    return GameState("史实")


def _mirror(state, key="wealth"):
    return sum(int(e.get(key, 0) or 0) for e in state.minister_estate.values())


def test_accounts_have_no_parallel_estate_accounts():
    """ACCOUNTS 已移除两个家产账户；M_ALL == ΣACCOUNTS（口径自洽、无重复计）。"""
    assert "estate_wealth" not in money.ACCOUNTS
    assert "estate_hoard" not in money.ACCOUNTS
    s = _new_state()
    snap = money.snapshot(s)
    assert abs(snap["M_ALL"] - sum(float(snap[k]) for k in money.ACCOUNTS)) < 1e-6


def test_money_counts_estate_exactly_once():
    """家产的钱只经 `pop_money`（士绅 estate 子池）与 `hoard_money`（estate_hoard）计一次。"""
    s = _new_state()
    expect = (money.pop_money(s)
              + float(s.treasury) + float(s.imperial_treasury)
              + money.local_treasury_total(s) + money.payraise_budget_total(s)
              + money.invest_principal_total(s) + money.hoard_money(s)
              + float(s.coin.get("melted_pool", 0) or 0)
              + float(s.bank.get("reserve", 0) or 0)
              + money._silver_stock(s))
    assert abs(money.m_all(s) - expect) < 1e-6
    # M0 结构性口径：pop_money × copper_share + 有效交子（不再外挂 estate_wealth）
    assert abs(money.m0(s) - (money.pop_money(s) * money.copper_share(s)
                              + money.effective_jiaozi(s))) < 1e-6


def test_new_game_mirror_equals_pop_slice():
    """开局即满足「Σ具名镜像 == Σ士绅子池」（家产钱物化进 POP）。"""
    s = _new_state()
    assert estate_slice_total(s, "estate") == _mirror(s, "wealth")
    assert estate_slice_total(s, "estate_hoard") == _mirror(s, "窖银")
    assert estate_slice_total(s, "estate") == sum(
        int(v.get("wealth", 0) or 0) for v in ESTATE_INIT.values())


def test_estate_cycle_is_pop_internal_transfer():
    """月度循环（有 AI 推演）：M_ALL/m2 不变，pop_money 只减窖藏额，镜像与子池恒等。"""
    s = _new_state()
    s._economy_ai = dict(_ECON_AI)
    m_all0, m2_0 = money.m_all(s), money.m2(s)
    pm0, hoard0 = money.pop_money(s), money.hoard_money(s)
    popsize0 = sum(int(pp.get("size", 0) or 0)
                   for p in s.prefectures.values() for pp in p["pops"].values())
    r = settle_minister_estate(s, [])
    assert money.m_all(s) == m_all0, "四条腿应全为 POP 内部/阶层间转移，M_ALL 不变"
    assert money.m2(s) == m2_0
    assert pm0 - money.pop_money(s) == r["hoard"], "pop_money 只按窖藏额减少"
    assert money.hoard_money(s) - hoard0 == r["hoard"], "窖藏进入 estate_hoard 子池"
    assert r["luxury"] > 0 and r["rent"] > 0, "该局面下奢侈与收租应有实际发生"
    popsize1 = sum(int(pp.get("size", 0) or 0)
                   for p in s.prefectures.values() for pp in p["pops"].values())
    assert popsize1 == popsize0, "家产机制不动人口"
    assert estate_slice_total(s, "estate") == _mirror(s, "wealth")
    assert estate_slice_total(s, "estate_hoard") == _mirror(s, "窖银")


def test_seize_moves_pop_money_to_treasury():
    """抄没：士绅 estate 子池 → 国库（POP→政府），该步 M_ALL 不变，镜像归零。"""
    s = _new_state()
    s.minister_estate["蔡京"]["wealth"] = 2_000_000
    sync_estate_slices(s)                     # 外部直改镜像后先物化
    m_all0 = money.m_all(s)
    t0 = s.treasury
    we, _land = seize_estate(s, "蔡京")
    assert we == 2_000_000
    assert s.treasury == t0 + we, "抄没的钱入国库"
    assert money.m_all(s) == m_all0, "POP→国库 属内部转移，M_ALL 不变"
    assert s.minister_estate["蔡京"]["wealth"] == 0
    assert estate_slice_total(s, "estate") == _mirror(s, "wealth")


def test_old_save_migration_keeps_m_all():
    """旧档（无子池）迁移：物化后 Σ子池 == Σ镜像，且 M_ALL 与旧口径（含独立账户）一致。"""
    s = _new_state()
    for p in s.prefectures.values():
        g = p["pops"]["士绅"]
        g["estate"] = 0                        # 模拟旧档：钱还没进 POP
        g["estate_hoard"] = 0
    m_old = money.m_all(s) + money.estate_wealth(s)   # 旧口径：平行账户被计入 M_ALL
    sync_estate_slices(s)
    assert estate_slice_total(s, "estate") == _mirror(s, "wealth")
    assert money.m_all(s) == m_old, "迁移不得改变 M_ALL（重分类而非印钱/销钱）"


def test_credit_estate_is_pop_internal():
    """投资贪腐截留（外部收益分流）：入士绅 estate 子池，镜像同步、M_ALL 同步增加。"""
    s = _new_state()
    m_all0 = money.m_all(s)
    got = credit_estate(s, "蔡京", 12_345)
    assert got == 12_345
    assert money.m_all(s) == m_all0 + 12_345, "外部收益入账应增加 M_ALL"
    assert s.minister_estate["蔡京"]["wealth"] == ESTATE_INIT["蔡京"]["wealth"] + 12_345
    assert estate_slice_total(s, "estate") == _mirror(s, "wealth")


def test_save_load_roundtrip_keeps_slices_and_mirror():
    """存档往返：具名镜像与 POP 子池都保留且仍恒等。"""
    from core.save_load import _slot_path, load_game, save_game
    s = _new_state()
    s.minister_estate["蔡京"]["wealth"] = 500_000
    sync_estate_slices(s)
    assert save_game(s, slot=3)
    s2 = load_game(3)
    assert s2 is not None
    assert s2.minister_estate["蔡京"]["wealth"] == 500_000
    assert estate_slice_total(s2, "estate") == _mirror(s2, "wealth")
    assert estate_slice_total(s2, "estate_hoard") == _mirror(s2, "窖银")
    if os.path.exists(_slot_path(3)):
        os.remove(_slot_path(3))


def test_http_snapshot_hides_estate_slices_without_mutating_state():
    """HTTP 快照剔除家产子池键（家产真值隐藏），且不得改动活动 state。"""
    from backend.server import _state_to_dict
    s = _new_state()
    d = _state_to_dict(s)
    for p in d["prefectures"].values():
        for slot in (p.get("pops") or {}).values():
            assert "estate" not in slot and "estate_hoard" not in slot
    # 活动状态未被改动（深拷贝一层，不能污染）
    assert estate_slice_total(s, "estate") == _mirror(s, "wealth")
    assert "estate" in s.prefectures[next(iter(s.prefectures))]["pops"]["士绅"]


def test_http_snapshot_exposes_ai_failures_agent_names_only():
    """快照必须下发 `ai_failures`（**仅 agent 名**）。

    回归锁定 2026-09-27 修复：该分支原先写在 `_` 前缀过滤**之后** → **永不可达**，
    AI 失败对玩家全静默（历史审计 3 次记录未修；前端 `GovernanceHub.tsx` 早已在消费
    `ai_failures`，即一直在等一个到不了的字段）。
    """
    from backend.server import _state_to_dict
    s = _new_state()
    assert _state_to_dict(s).get("ai_failures", []) == []      # 无失败 → 空/缺省
    s._ai_failures = [{"agent": "finance", "error": "timeout"},
                      {"agent": "survey", "error": "boom"},
                      {"error": "缺 agent 名者应被丢弃"}]
    d = _state_to_dict(s)
    assert d["ai_failures"] == ["finance", "survey"]
    assert "_ai_failures" not in d, "私有键仍不得外发"
