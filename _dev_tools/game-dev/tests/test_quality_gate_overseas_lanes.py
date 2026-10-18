# -*- coding: utf-8 -*-
"""质量放行门 · 外海航线（日本 / 高丽 / 南洋，2026-10-18 用户指示）。

境内海路图（SEA_LANES）只管沿海治所；外贸还需要**外海航线**到外邦港。
本门钉住：
1. 外海段表自洽：起点是境内沿海治所、对家可查、里程 > 0、每段有 note 依据；
2. 日本 / 高丽 / 南洋（三佛齐/阇婆/大食/注辇）**都有航线**；
3. 直航正确（明州→日本、登州→高丽）；
4. **转口**正确：明州→三佛齐 = 境内 明州→泉州 + 泉州→三佛齐，且标出 transship_via；
5. 无航线 / 未知对家 ⇒ None（不臆造）；
6. 外贸对家表覆盖：OVERSEAS_PARTNERS ⊆ REGIME_IMPORTS 且 ⊆ SEA_TRADERS。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_constants import (  # noqa: E402
    OVERSEAS_PARTNERS, SEA_LANES, SEA_OVERSEAS_LANES)
from core.domains.economy import trade_shadow as ts  # noqa: E402
from core.foundation.ledger.prefecture_entity import all_seats  # noqa: E402
from core.transport import overseas_route, sea_route  # noqa: E402

MINGZHOU, DENGRUO, QUANZHOU = "两浙路|明州", "京东东路|登州", "福建路|泉州"


def test_overseas_table_is_sane():
    ids = {s["seat_id"] for s in all_seats()}
    coastal = {l["a"] for l in SEA_LANES} | {l["b"] for l in SEA_LANES}
    assert SEA_OVERSEAS_LANES, "外海段表为空 ⇒ 门是空转"
    for lane in SEA_OVERSEAS_LANES:
        assert lane["from"] in ids, f"起点不是真实治所：{lane}"
        assert lane["from"] in coastal, f"起点不是沿海治所（须先在 SEA_LANES 中）：{lane}"
        assert lane["partner"] in OVERSEAS_PARTNERS, f"对家未登记：{lane}"
        assert float(lane.get("km") or 0) > 0, f"里程非正：{lane}"
        assert lane.get("note"), f"缺航路依据：{lane}"


def test_japan_korea_nanyang_are_covered():
    partners = {l["partner"] for l in SEA_OVERSEAS_LANES}
    assert "日本" in partners, "缺日本航线"
    assert "高丽" in partners, "缺高丽（朝鲜）航线"
    nanyang = {"三佛齐", "阇婆", "大食", "注辇"}
    assert nanyang <= partners, f"缺南洋航线：{sorted(nanyang - partners)}"


def test_direct_routes():
    jp = overseas_route(MINGZHOU, "日本")
    assert jp and jp["km"] == 1400 and jp["port"] == "博多", jp
    kr = overseas_route(DENGRUO, "高丽")
    assert kr and kr["km"] == 700 and kr["port"] == "礼成江", kr
    assert jp["days"] >= 1 and kr["days"] >= 1


def test_transshipment_route():
    """明州→三佛齐 无直航 ⇒ 经泉州转口，里程 = 境内段 + 外海段。"""
    domestic = sea_route(MINGZHOU, QUANZHOU)
    assert domestic, "境内段应可达"
    r = overseas_route(MINGZHOU, "三佛齐")
    assert r is not None, "应能经泉州转口到达三佛齐"
    assert r["transship_via"] == QUANZHOU, r
    assert abs(r["km"] - (domestic["km"] + 3000.0)) < 1.0, f"{r} vs 境内 {domestic["km"]}+3000"


def test_unknown_partner_returns_none():
    assert overseas_route(MINGZHOU, "火星") is None
    assert overseas_route("两浙路|越州", "日本") is None, "非海港不得臆造外海航线"


def test_partner_tables_are_consistent():
    missing_imports = [p for p in OVERSEAS_PARTNERS if p not in ts.REGIME_IMPORTS]
    assert not missing_imports, f"外贸对家表缺：{missing_imports}"
    missing_sea = [p for p in OVERSEAS_PARTNERS if p not in ts.SEA_TRADERS]
    assert not missing_sea, f"外海对家未列入海运对家：{missing_sea}"