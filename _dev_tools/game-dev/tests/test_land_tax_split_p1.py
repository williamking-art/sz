# -*- coding: utf-8 -*-
"""P1 双层税基 · 四率（V1.3 终稿 §2-§3）：验收断言 1-6 ＋ 10 的落地测试。

- 归一化单点（全库唯一，保护顺序 div→keep→transfer）；
- 田赋折色征收器守恒三连（函数级 / 入账级 / m_all 归零）；
- 三分落点精确对账（留州=paid×keep、侵渔=paid×div）；
- 其余税种旧路径回归锁（Q3 甲）；
- 存档迁移 `_migrate_finance` 幂等补值。
"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

import pytest

from core.commands import new_game
from core.foundation.ledger.money import m_all
from core.game_state_econ import normalize_finance_split
from core.settlement_finance import _settle_finance, _settle_land_tax_color
from content.data import (FIN_COLLECTION_BASE, FIN_DIV_RATE, FIN_KEEP_BASE,
                          FIN_TRANSFER_RATE)


def _pools_total(state):
    t = 0
    for p in state.prefectures.values():
        for row in (p.get("pops") or {}).values():
            if isinstance(row, dict):
                t += int(row.get("wealth", 0) or 0)
    return t


def _local_total(state):
    return sum(int(p.get("local_treasury", 0) or 0) for p in state.prefectures.values())


# ---------------- 归一化单点 ----------------

def test_normalize_default_exact():
    t, k, d = normalize_finance_split(FIN_TRANSFER_RATE, FIN_KEEP_BASE, FIN_DIV_RATE)
    assert t + k + d == pytest.approx(1.0, abs=1e-12)


def test_normalize_div_absorbs_first_transfer_protected():
    t, k, d = normalize_finance_split(0.94, 0.047, 0.02)
    assert t == pytest.approx(0.94)          # transfer 未被动（最高保护）
    assert k == pytest.approx(0.047)         # keep 未被动
    assert d == pytest.approx(0.013)         # diversion 残差吸收
    assert t + k + d == pytest.approx(1.0, abs=1e-12)


def test_normalize_cascade_and_caps():
    t, k, d = normalize_finance_split(1.5, 0.30, 0.05)
    assert t + k + d == pytest.approx(1.0, abs=1e-12)
    assert t <= 0.98 and k <= 0.20 and d >= 0.0


# ---------------- 通道读数 ----------------

def test_channels_assessed_and_normalized():
    s = new_game()
    chan = s.calc_land_tax_channels()
    total = 0
    for rk, row in chan["by_route"].items():
        assert row["assessed"] == int(row["tax_base"] * s.calc_collection_rate(rk))
        assert row["transfer"] + row["keep"] + row["div"] == pytest.approx(1.0, abs=1e-9)
        total += row["assessed"]
    assert total == chan["assessed_total"]


# ---------------- 征收器守恒三连 ----------------

def test_collection_conservation_and_landings():
    s = new_game()
    m0 = m_all(s)
    loc0 = _local_total(s)
    ret = _settle_land_tax_color(s, [])

    # ① 三分和 ≡ 实收（无残差）
    assert ret["central"] + ret["local"] + ret["diverted"] == ret["collected"]
    # ② 函数级守恒：m_all 减少额 == central（中央尚未入账）
    assert m_all(s) - m0 == -ret["central"]
    # ③ 留州落点：与返回/统计一致
    assert _local_total(s) - loc0 == ret["local"]
    assert s.statistics["land_tax_local"] == ret["local"]
    assert s.statistics["land_tax_central"] == ret["central"]
    assert s.statistics["land_tax_diverted"] == ret["diverted"]
    assert s.statistics["land_tax_assessed"] == ret["assessed"]
    # ④ 中央入账后 m_all 归零（纯转移，不造币不销币）
    s.change_treasury(int(ret["central"]))
    assert abs(m_all(s) - m0) < 1e-9
    # ⑤ 逐路精确：留州 == int(paid×keep)，侵渔 == int(paid×div)
    for rk, l in ret["local_by_route"].items():
        _t, k, _d = s.finance_split(rk)
        assert l == int(ret["by_route"][rk] * k)
    for rk, dv in ret["div_by_route"].items():
        _t, _k, d = s.finance_split(rk)
        assert dv == int(ret["by_route"][rk] * d)


# ---------------- 全管线落点 ----------------

def test_full_finance_pipeline_local_landing():
    s = new_game()
    loc0 = _local_total(s)
    _settle_finance(s, [])
    assert _local_total(s) - loc0 == int(s.statistics["land_tax_local"])


# ---------------- Q3 甲：其余税种旧路径回归锁 ----------------

def test_non_land_taxes_legacy_path_locked():
    """其余税种仍走旧路径（税基 × arrival × tax_coeff）——Q3 甲回归锁。

    若 P4 迁移非田赋税种，本测试随设计更新；此锁只防"误伤"。
    """
    from content.data import (CRAFT_OUTPUT_PER_CAPITA, COMMERCE_TAX_RATE_DEFAULT,
                              COMMERCE_TAX_RATE_MIN, COMMERCE_TAX_RATE_MAX,
                              TAX_COEFF_MIN, TAX_COEFF_MAX, TAX_POLL_RATIO)
    from core.foundation.ledger.pop_structure import service_ding_total

    s = new_game()
    arrival = s.calc_arrival_rate()
    shortage = s.coin.get("shortage", 0.3)
    tax_coeff = TAX_COEFF_MIN + (TAX_COEFF_MAX - TAX_COEFF_MIN) * (1 - shortage)
    commerce_monthly = sum((p["pops"]["工匠"]["size"] + p["pops"]["商人"]["size"])
                           * CRAFT_OUTPUT_PER_CAPITA for p in s.prefectures.values())
    rate = max(COMMERCE_TAX_RATE_MIN, min(COMMERCE_TAX_RATE_MAX,
               getattr(s, "commerce_tax_rate", COMMERCE_TAX_RATE_DEFAULT)))
    expected_commerce = int(commerce_monthly * rate * arrival * tax_coeff)
    expected_poll = int((service_ding_total(s) * TAX_POLL_RATIO / 12) * arrival * tax_coeff)

    _settle_finance(s, [])
    assert s.tax_breakdown["commerce"] == expected_commerce
    assert s.tax_breakdown["poll"] == expected_poll


# ---------------- 容器与迁移 ----------------

def test_finance_container_initialized():
    s = new_game()
    assert s.finance["tax_version"] == 1
    assert s.finance["transfer_rate"] == FIN_TRANSFER_RATE
    assert s.finance["local_keep_rate"] == FIN_KEEP_BASE
    assert s.finance["diversion_rate"] == FIN_DIV_RATE
    assert s.finance["collection_rate"] == FIN_COLLECTION_BASE


def test_migrate_finance_idempotent_defaults():
    from core.save_load import _migrate_finance
    d = _migrate_finance(None)
    assert d["tax_version"] == 1
    assert d["transfer_rate"] == FIN_TRANSFER_RATE
    d2 = _migrate_finance({"transfer_rate": 0.90, "bad_key": "x",
                           "collection_rate": True})   # bool 拒收 → 默认
    assert d2["transfer_rate"] == 0.90
    assert d2["collection_rate"] == FIN_COLLECTION_BASE
    assert "bad_key" not in d2
    assert _migrate_finance(d2) == d2                    # 幂等


def test_finance_roundtrip_and_legacy_default():
    """存档往返：`finance` 持久化；缺键（旧档）载入幂等补默认。

    SAVE_DIR 由 conftest 的 `_isolate_save_dir` 全局重定向到 tmp_path，不触真实存档。
    """
    import json
    import core.foundation.persistence.slots as _slots
    from core.save_load import save_game, load_game

    s = new_game()
    s.finance["transfer_rate"] = 0.90          # 模拟改革后
    assert save_game(s, 9) is True
    s2 = load_game(9)
    assert s2 is not None
    assert s2.finance["transfer_rate"] == 0.90
    assert s2.finance["tax_version"] == 1

    # 旧档模拟：删除 finance 键后载入 → 全默认（迁移幂等）
    p = _slots._slot_path(9)
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    raw.pop("finance", None)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    s3 = load_game(9)
    assert s3 is not None
    assert s3.finance["transfer_rate"] == FIN_TRANSFER_RATE
    assert s3.finance["collection_rate"] == FIN_COLLECTION_BASE
    assert s3.finance["tax_version"] == 1
