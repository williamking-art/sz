# -*- coding: utf-8 -*-
"""质量放行门 · 攻占接收（P5.6 修订：**不冻结**，按残破度征税；2026-10-19）。

用户裁定：「怎么会冻结税产呢？占领后会产生财产流失，这个我理解；为什么会冻结呢」。

本门用**独立 fixture**（不依赖 new_game；他处在途改动曾使 commands.py 不可导入）：
1. 占领 ⇒ 当刻财产流失（人口 −3%/财富 −15%/存粮 −15%）+ 掠夺入账；
2. regime_intake 不冻结（tax_output_frozen=False），可征税产按残破度 > 0；
3. 宋座接收：人口读 seats 真账，土地 None + missing 清单（不假造）；
4. 归还后残破保留（不返还），intake 归零；
5. 无领地 ⇒ 人口 None + reason（缺失≠0）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.diplomacy.regime_transfer import (  # noqa: E402
    revert_change, transfer_regions)


class _S:
    def __init__(self):
        self.regions = {
            "liao_p0": {"level": "T2", "name": "南京道", "owner": "辽", "parent": "辽"},
            "liao_p0_a": {"level": "T1", "name": "析津府", "owner": "辽", "owner_at_init": "辽",
                          "parent": "liao_p0", "land": 1000,
                          "pop": {"农": {"size": 100000, "wealth": 1000000, "grain": 500000}}},
            "song_jj": {"level": "T2", "name": "京畿路", "owner": "宋", "parent": "宋"},
            "song_jj_kf": {"level": "T1", "name": "开封府", "owner": "宋", "owner_at_init": "宋",
                           "parent": "song_jj",
                           "prefecture_ref": {"route": "京畿路", "seat": "京畿路|开封府"}},
        }
        self.external_regimes = {"辽": {"treasury": 0, "territory": ["liao_p0", "liao_p0_a"]},
                                 "宋": {"treasury": 0}}
        self.prefectures = {"京畿路": {"land": 5000, "seats": {
            "京畿路|开封府": {"pops": {"农": {"size": 200000, "wealth": 2000000, "grain": 900000}}}}}}
        self.region_changes = []


def test_capture_liao_gets_people_and_tax_not_frozen():
    from core.domains.diplomacy.regime_intake import regime_intake

    s = _S()
    out = transfer_regions(s, "辽", "金", ["liao_p0"], create_to=True, reason="占领")
    assert out["ok"], out
    assert out["damage"] and out["damage"]["loot"] > 0
    got = regime_intake(s, "金")
    assert got["t1_count"] == 1
    assert got["tax_output_frozen"] is False
    assert got["devastation_avg"] == 0.6
    assert got["collectable_tax"] > 0
    assert s.regions["liao_p0_a"]["pop"]["农"]["wealth"] == 850000


def test_capture_song_seat_uses_real_ledger_and_flags_land():
    from core.domains.diplomacy.regime_intake import regime_intake

    s = _S()
    out = transfer_regions(s, "宋", "金", ["song_jj_kf"], create_to=True, reason="占宋地")
    assert out["ok"], out
    got = regime_intake(s, "金")
    assert got["population_people"] == 200000
    assert got["land"] is None
    assert got["land_missing_regions"] == ["song_jj_kf"]
    assert got["tax_output_frozen"] is False


def test_return_keeps_devastation_and_clears_intake():
    from core.domains.diplomacy.regime_intake import regime_intake

    s = _S()
    out = transfer_regions(s, "辽", "金", ["liao_p0"], create_to=True, reason="占领")
    assert regime_intake(s, "金")["t1_count"] >= 1
    assert revert_change(s, out["change_id"])["ok"]
    got = regime_intake(s, "金")
    assert got["t1_count"] == 0 and got["population_people"] is None
    assert s.regions["liao_p0_a"]["devastation"] == 0.6, "归还后残破保留"


def test_unknown_regime_population_is_none():
    from core.domains.diplomacy.regime_intake import regime_intake

    s = _S()
    got = regime_intake(s, "金")
    assert got["t1_count"] == 0
    assert got["population_people"] is None and got["population_reason"]
