# -*- coding: utf-8 -*-
"""M35-2《欠给时间化 · 身份压力接口 · 财政可见度完善》契约回归。

裁决口径（用户 2026-10-11）：
- **M35-2-A** 欠给**时间化**：金额（存量）与时间（连续欠给月数）**分离**；
  1 月欠给 ≠ 24 月欠给；支持旧档迁移。
- **M35-2-B** **身份压力接口**：`clerk_pressure`／`official_pressure` 由 金额·月数·grip·governance
  派生，**只提供状态**（不自动腐败、不生成剧本事件）。
- **M35-2-C** 财政可见度**读取规则**：保持 real/official/rumor 三层，但**不开放玩家直接读 real**
  （为审计/巡按/调查留接口）。
- 约束：不新增 POP；runner 保持 occupation 接口；不做收入拆分；不做自动腐败事件；新字段必须迁移。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.commands import new_game  # noqa: E402
from core.settlement_finance import _settle_local_expenditure  # noqa: E402


def _drive_arrears(s, route, times=1):
    """把某路府库抽干并推进 `times` 次支用步，逼出连续欠给。"""
    for _ in range(times):
        s.prefectures[route]["local_treasury"] = 0
        _settle_local_expenditure(s, [])


# ---------------- M35-2-A 欠给时间化 ----------------

def test_arrears_months_accumulate_and_amount_separate():
    """连续欠给：月数随月累进，金额同时累积（两者独立计数）。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive_arrears(s, rk, times=2)
    months = s.prefectures[rk]["arrears_months"]
    pool = s.prefectures[rk]["pops"]["官僚"]
    assert months["clerk_pay"] == 2.0, "连续欠给两月 ⇒ 月数 2"
    assert months["official_salary"] == 2.0
    assert int(pool["clerks_pay_arrears"]) > 0, "金额与时间分离：金额同时累积"
    # 再推进一月 → 3 月（与 D5′ 阈值同口径：≥3 月才触发后果）
    _drive_arrears(s, rk, times=1)
    assert s.prefectures[rk]["arrears_months"]["clerk_pay"] == 3.0


def test_arrears_months_clamp_at_cap():
    from content.data import LOCAL_ARREARS_MONTHS_CAP
    s = new_game()
    rk = min(s.prefectures)
    for _ in range(int(LOCAL_ARREARS_MONTHS_CAP) + 3):
        s.prefectures[rk]["local_treasury"] = 0
        _settle_local_expenditure(s, [])
    m = s.prefectures[rk]["arrears_months"]["clerk_pay"]
    assert m == float(LOCAL_ARREARS_MONTHS_CAP), "月数必须封顶（防长期溢出）"


def _zero_identity_arrears(s, route):
    """把该路身份欠给**清偿**（真账在 `seats`，路级 `pops` 只是派生镜像 ⇒ 必须清 seats）。"""
    from core.foundation.ledger.pop_bridge import sync_route_pops
    p = s.prefectures[route]
    pairs = (("官僚", "clerks_pay_arrears"), ("官僚", "officials_salary_arrears"),
             ("兵", "runners_pay_arrears"))
    for seat in (p.get("seats") or {}).values():
        if not isinstance(seat, dict):
            continue
        for cls, key in pairs:
            pool = (seat.get("pops") or {}).get(cls)
            if isinstance(pool, dict):
                pool[key] = 0
    sync_route_pops(p)                       # 刷新路级镜像
    for cls, key in pairs:                   # 未下沉档（回落路径）直接清路级
        pool = (p.get("pops") or {}).get(cls)
        if isinstance(pool, dict):
            pool[key] = 0


def test_arrears_months_decay_and_reset_on_repayment():
    """恢复期月数递减；身份欠给**清偿**（存量归零）→ 月数清零。"""
    s = new_game()
    rk = min(s.prefectures)
    _drive_arrears(s, rk, times=3)
    assert s.prefectures[rk]["arrears_months"]["clerk_pay"] == 3.0
    # 府库充裕（正常月）→ 无新欠 ⇒ 递减
    s.prefectures[rk]["local_treasury"] = 10 ** 9
    _settle_local_expenditure(s, [])
    assert s.prefectures[rk]["arrears_months"]["clerk_pay"] == 2.0, "无新欠应递减"
    # 清偿存量（清 seats 真账）⇒ 月数清零
    _zero_identity_arrears(s, rk)
    _settle_local_expenditure(s, [])
    m = s.prefectures[rk]["arrears_months"]
    assert m["clerk_pay"] == 0.0 and m["official_salary"] == 0.0, "清偿后月数清零"



# ---------------- M35-2-B 身份压力接口 ----------------

def test_pressure_monotonic_in_months_with_same_amount():
    """同额欠给下，**月数越长压力越高**（金额与时间分离的意义）。"""
    def _mk(months_val):
        s = new_game()
        rk = min(s.prefectures)
        s.prefectures[rk]["pops"]["官僚"]["clerks_pay_arrears"] = 20000   # **同额**
        s.prefectures[rk].setdefault("arrears_months", {})["clerk_pay"] = months_val
        return s.identity_pressures()["by_route"][rk]["clerk_pressure"]

    p1, p24 = _mk(1.0), _mk(24.0)
    assert p24 > p1, "同额欠给：欠得更久 ⇒ 压力更高"


def test_pressure_inputs_exposed_and_readonly():
    s = new_game()
    rk = min(s.prefectures)
    _drive_arrears(s, rk, times=2)
    view = s.identity_pressures()
    row = view["by_route"][rk]
    for k in ("clerk_pressure", "official_pressure", "runner_pressure", "inputs"):
        assert k in row
    for k in ("clerk_arrears", "clerk_months", "grip", "pay_ratio", "div"):
        assert k in row["inputs"], "压力必须暴露构成（AI 需要知道'为什么有压力'）"
    assert 0.0 <= row["clerk_pressure"] <= 100.0
    assert view["total"]["max_arrears_months"] >= 2.0
    import copy
    before = copy.deepcopy(s.prefectures)
    s.identity_pressures()
    assert copy.deepcopy(s.prefectures) == before, "压力接口只报状态，不得改动账本"


def test_arrears_months_summary_shape():
    s = new_game()
    rk = min(s.prefectures)
    _drive_arrears(s, rk, times=4)
    summ = s.arrears_months_summary()
    assert summ["clerk_pay"]["max"] >= 4.0
    assert summ["clerk_pay"]["routes_over_3"] >= 1
    assert summ["clerk_pay"]["longest_route"] == rk
    assert s.finance_readout()["local_arrears_months"]["clerk_pay"]["max"] >= 4.0


# ---------------- M35-2-C 财政可见度读取规则 ----------------

def test_player_view_hides_real_layer():
    """玩家视角**不含 real**；真账只在内部/AI 或"查得实情"时可见。"""
    from content.data import FIN_ANOMALY_OVERSIGHT_LINE
    s = new_game()
    player = s.fiscal_visibility_view()
    assert "real" not in player and "official" in player and "rumor" in player
    assert player["viewer"] == "player"
    assert "real" not in s.finance_readout()["fiscal_visibility"]
    assert "real" not in s.fiscal_visibility_view("audit", oversight=0.0)
    assert "real" in s.fiscal_visibility_view("audit",
                                              oversight=FIN_ANOMALY_OVERSIGHT_LINE + 0.1)
    assert "real" in s.fiscal_visibility_view("audit", oversight=0.0, secret=True)
    assert set(s.fiscal_visibility_view("ai")) >= {"real", "official", "rumor"}
    assert set(s.fiscal_visibility()) == {"real", "official", "rumor"}


def test_old_save_defaults_for_arrears_months():
    from core.save_load import load_game, save_game
    s = new_game()
    slot = 6
    for p in s.prefectures.values():
        p.pop("arrears_months", None)
    assert save_game(s, slot=slot)
    loaded = load_game(slot=slot)
    assert loaded is not None
    for p in loaded.prefectures.values():
        assert isinstance(p.get("arrears_months"), dict), "旧档必须补欠给月数容器"
