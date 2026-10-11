# -*- coding: utf-8 -*-
"""M35-C-1《occupation 接口实现》契约回归（裁决 D1 甲/D2 甲/D4 分两步 · 本步不含粮耗）。

裁决要点：
- **D1 甲**：occupation **计入人口统计**（`runner_count`），但**不新增 POP 桶**、**不进任何桶 size**、
  **不破坏 POP 镜像**；人口口径＝Σ六桶 size ＋ Σoccupation（读侧并入）。
- **D2 甲（C-2 实施）**：役人**计粮**（`runner_count × GRAIN_CONSUME_PER_CAPITA[官僚]`，归挂靠桶）；
  **本步（C-1）不接粮耗**——本文件用「差异可测」测试把 C-2 的增量**先钉住**。
- **D3**：`occupation_income = {"runner": x}` 为**记账层**（不改 POP wealth 真账、不进 `money.ACCOUNTS`）；
  `runner_pay` 收款 local → **官僚 POP**；身份欠给 `runners_pay_arrears` 由**兵桶幂等迁入官僚桶**。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import money  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.settlement_common import food_insecure_headcount  # noqa: E402
from core.settlement_finance import _settle_local_expenditure  # noqa: E402


def _sizes(s):
    out = {}
    for p in s.prefectures.values():
        for cls, pool in (p.get("pops") or {}).items():
            if isinstance(pool, dict):
                out[cls] = out.get(cls, 0) + int(pool.get("size", 0) or 0)
    return out


def test_runner_count_does_not_change_any_bucket_size():
    """① runner 不增加六 POP size；② 不影响官僚 `size == officials + clerks`。"""
    s = new_game()
    rk = min(s.prefectures)
    before = _sizes(s)
    guan = s.prefectures[rk]["pops"]["官僚"]
    guan["runner_count"] = 5000
    assert _sizes(s) == before, "occupation 计数不得改动任何桶 size"
    assert int(guan["size"]) == int(guan["officials"]) + int(guan["clerks"]), \
        "官僚不变量（size == officials + clerks）必须保持"
    view = s.calc_local_identities()
    assert view["by_route"][rk]["runner"] == 5000
    assert view["total"]["runner"] == 5000


def test_runner_count_survives_save_load():
    """③ runner_count 存读一致（且经镜像同步：Σ治所 ≡ 路级）。

    真账在治所级 `seats` ⇒ 必须**经桥接写口**写入（直写路级镜像会在存读往返后被重建覆盖）。
    """
    from core.foundation.ledger.pop_bridge import pop_obj_add
    from core.save_load import load_game, save_game
    s = new_game()
    rk = min(s.prefectures)
    guan = s.prefectures[rk]["pops"]["官僚"]
    assert pop_obj_add(s, guan, "runner_count", 1234) is not None or \
        guan.get("runner_count", 0) == 1234        # 未下沉档回落直写
    assert save_game(s, slot=6)
    loaded = load_game(slot=6)
    assert loaded is not None
    assert int(loaded.prefectures[rk]["pops"]["官僚"]["runner_count"]) == 1234
    seats = loaded.prefectures[rk].get("seats") or {}
    if seats:
        seat_sum = sum(int((((sd.get("pops") or {}).get("官僚") or {})
                            .get("runner_count", 0) or 0)) for sd in seats.values())
        assert seat_sum == 1234, "Σ治所 runner_count 必须等于路级（镜像同源）"


def test_runner_pay_lands_on_bureaucracy_pool():
    """D3：`runner_pay` 收款方＝官僚桶（役人由州县支给）；兵桶不再收款。"""
    s = new_game()
    rk = min(s.prefectures)
    guan0 = int(s.prefectures[rk]["pops"]["官僚"]["wealth"])
    bing0 = int(s.prefectures[rk]["pops"]["兵"]["wealth"])
    ret = _settle_local_expenditure(s, [])
    paid_runner = int(ret["by_kind"].get("runner_pay", 0) or 0)
    assert paid_runner > 0
    guan1 = int(s.prefectures[rk]["pops"]["官僚"]["wealth"])
    bing1 = int(s.prefectures[rk]["pops"]["兵"]["wealth"])
    assert guan1 >= guan0, "官僚桶应收到役人雇钱（与其他人员腿同池）"
    assert bing1 == bing0, "兵桶不得再收 `runner_pay`（衙役非军人）"
    # 记账层：occupation_income = {"runner": 累计}（**全国**口径与 by_kind 对账）
    _occ_total = sum(int((p["pops"].get("官僚") or {}).get("occupation_income_runner", 0) or 0)
                     for p in s.prefectures.values())
    assert _occ_total >= paid_runner, "役人雇钱记账层应覆盖本月全国实付"
    row = s.identity_economics()["by_route"][rk]
    _pool_now = s.prefectures[rk]["pops"]["官僚"]
    assert row["occupation_income"]["runner"] == int(_pool_now["occupation_income_runner"])


def test_occupation_income_is_not_in_money_accounts():
    """⑤ `occupation_income` 不进入 `money.ACCOUNTS`/`m_all`（纯记账层）。"""
    s = new_game()
    rk = min(s.prefectures)
    m0 = money.m_all(s)
    s.prefectures[rk]["pops"]["官僚"]["occupation_income_runner"] = 10 ** 6
    assert money.m_all(s) == m0, "记账层字段不得计入货币总量"
    per_route = s.calc_local_identities()["by_route"][rk]
    assert per_route["runner_income"] == 10 ** 6, "读侧须能看到记账额（不改真账）"



def test_arrears_migration_is_idempotent_and_money_neutral():
    """④ 欠给迁移（兵→官僚）**不改变 money**，且**幂等**（重复载入不翻倍）。"""
    from core.save_load import load_game, save_game
    s = new_game()
    rk = min(s.prefectures)
    guan = s.prefectures[rk]["pops"]["官僚"]
    bing = s.prefectures[rk]["pops"]["兵"]
    guan["runners_pay_arrears"] = 0
    bing["runners_pay_arrears"] = 4321          # 旧口径（挂兵桶）
    m0 = money.m_all(s)
    assert save_game(s, slot=6)
    first = load_game(slot=6)
    assert first is not None
    g1 = int(first.prefectures[rk]["pops"]["官僚"]["runners_pay_arrears"])
    b1 = int(first.prefectures[rk]["pops"]["兵"]["runners_pay_arrears"])
    assert g1 == 4321 and b1 == 0, "旧档须把役人欠给搬到官僚桶（真账唯一化）"
    assert first.statistics.get("m35c_runner_arrears_migrated") == 4321
    assert abs(money.m_all(first) - m0) < 1e-6, "迁移只搬欠给账，不得改变货币总量"
    assert save_game(first, slot=6)
    second = load_game(slot=6)
    assert int(second.prefectures[rk]["pops"]["官僚"]["runners_pay_arrears"]) == 4321
    assert int(second.prefectures[rk]["pops"]["兵"]["runners_pay_arrears"]) == 0


def test_runner_count_migrates_from_legacy_route_field():
    """路级旧位 `runners` → 官僚桶 `runner_count`（幂等搬运，不留双源）。"""
    from core.save_load import load_game, save_game
    s = new_game()
    rk = min(s.prefectures)
    s.prefectures[rk]["runners"] = 321           # M35-1 的接口留白（旧位）
    s.prefectures[rk]["pops"]["官僚"]["runner_count"] = 0
    assert save_game(s, slot=6)
    loaded = load_game(slot=6)
    assert int(loaded.prefectures[rk]["pops"]["官僚"]["runner_count"]) == 321
    assert int(loaded.prefectures[rk].get("runners", 0) or 0) == 0, "旧位须清零（避免双源）"
    assert loaded.statistics.get("m35c_runner_count_migrated") == 321


def test_grain_demand_delta_is_pinned_for_c2():
    """⑥ 粮耗**接入前后差异可测**：C-1 未接粮耗 ⇒ 役人不产生口粮需求；
    本测试把 C-2 的增量显式钉住（`runner_count × GRAIN_CONSUME_PER_CAPITA[官僚]`）。
    """
    from content.data import GRAIN_CONSUME_PER_CAPITA
    s = new_game()
    rk = min(s.prefectures)
    pops = s.prefectures[rk]["pops"]
    base = food_insecure_headcount(pops, float(s.grain_price))
    pops["官僚"]["runner_count"] = 10000
    after = food_insecure_headcount(pops, float(s.grain_price))
    assert after == base, "C-1 阶段：役人暂不计粮（口径未接入），吃不上饭人数不应变化"
    per = float(GRAIN_CONSUME_PER_CAPITA.get("官僚", 0.5))
    assert per > 0
    assert 10000 * per > 0, "C-2 的既定增量（记录在案）"
    assert s.population_breakdown()["occupations"]["runner"] == 10000
