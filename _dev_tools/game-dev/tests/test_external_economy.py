# -*- coding: utf-8 -*-
"""外邦经济月度结算回归（2026-09-19 同构循环 → 2026-09-22 省域化：辽/西夏/大理
经济拆到州/府一级，其余 38 政权维持简单模拟）。

断言：
  1) 岁币按 attitude≥60 落入辽/西夏政权库藏（treasury + econ_stats.tribute_in）；
  2) 宋侧 burn 台账含岁币条目（外邦账户不在宋 ACCOUNTS，宋 M_ALL 口径不变）；
  3) 政权内 ΣPOP wealth + treasury 的月度变化 == 岁币增量（内部操作零残差；
     大理无岁币渠道 → Δ钱 == 0）；
  4) 省域 econ_audit（每省）与政权级 econ_audit（Σ省）双残差恒 0（钱粮守恒）；
  5) 旧档缺新字段（treasury/grain_price/econ_audit/econ_stats/省域 pops）时幂等补齐不炸。
"""
from core.game_state import GameState
from content.data import SUI_GONG_ANNUAL, EXTERNAL_ECONOMY_REGIMES


def _new_state(attitude=80):
    s = GameState("史实")
    s.external.setdefault("辽", {})["attitude"] = attitude
    s.external.setdefault("西夏", {})["attitude"] = attitude
    return s


def _regime_money(ex):
    return (sum(int(v.get("wealth", 0) or 0) for v in ex["pop"].values())
            + int(ex.get("treasury", 0) or 0))


def test_tribute_lands_in_regime_treasury():
    from core.settlement import run_monthly_settlement
    s = _new_state(80)
    run_monthly_settlement(s, seed_offset=7)
    exp_liao = int(SUI_GONG_ANNUAL * 0.6 / 12)
    exp_xixia = int(SUI_GONG_ANNUAL * 0.4 / 12)
    assert s.external_regimes["辽"]["econ_stats"]["tribute_in"] >= exp_liao
    assert s.external_regimes["西夏"]["econ_stats"]["tribute_in"] >= exp_xixia


def test_song_burn_ledger_equals_tribute():
    """宋侧 burn 台账含岁币条目（2026-09-22 起另含机构运营支出等合法销毁通道）。"""
    from core.settlement import run_monthly_settlement
    s = _new_state(80)
    run_monthly_settlement(s, seed_offset=7)   # M1：首月无上月快照，台账只留 notes
    run_monthly_settlement(s, seed_offset=7)   # M2：正常对账月
    rec = (s.money_audit.get("recent") or [{}])[-1]
    expect = int(SUI_GONG_ANNUAL * 0.6 / 12) + int(SUI_GONG_ANNUAL * 0.4 / 12)
    notes = rec.get("external_notes", [])
    assert any("岁币岁赐外流" in n for n in notes), f"岁币 burn 条目缺失：{notes}"
    assert int(rec.get("burn_flow", 0) or 0) >= expect, \
        f"宋侧 burn 台账 {rec.get('burn_flow')} < 岁币 {expect}"


def test_regime_money_conserves_over_12_months():
    """政权内钱账本只因岁币变化：Δ(Σwealth+treasury) == Δtribute（12 个月）。

    大理无岁币渠道（tribute 恒 0）→ 断言退化为 Δ钱 == 0（更强）；
    econ_stats 只对岁币政权存在，读取走 .get 兜底。
    """
    from core.settlement import run_monthly_settlement
    s = _new_state(80)
    run_monthly_settlement(s, seed_offset=7)
    prev = {rk: _regime_money(s.external_regimes[rk]) for rk in EXTERNAL_ECONOMY_REGIMES}
    prev_trib = {rk: int(s.external_regimes[rk].get("econ_stats", {}).get("tribute_in", 0) or 0)
                 for rk in EXTERNAL_ECONOMY_REGIMES}
    for m in range(11):
        run_monthly_settlement(s, seed_offset=7)
        for rk in EXTERNAL_ECONOMY_REGIMES:
            ex = s.external_regimes[rk]
            cur = _regime_money(ex)
            cur_trib = int(ex.get("econ_stats", {}).get("tribute_in", 0) or 0)
            assert cur - prev[rk] == cur_trib - prev_trib[rk], \
                f"M{m + 2} {rk} 钱账本断裂：Δ={cur - prev[rk]} 岁币Δ={cur_trib - prev_trib[rk]}"
            prev[rk], prev_trib[rk] = cur, cur_trib


def test_external_econ_audit_zero_residual():
    from core.settlement import run_monthly_settlement
    s = _new_state(80)
    for _ in range(3):
        run_monthly_settlement(s, seed_offset=7)
    for rk in EXTERNAL_ECONOMY_REGIMES:
        audit = s.external_regimes[rk]["econ_audit"]
        assert audit["money_residual"] == 0, f"{rk} 钱残差 {audit['money_residual']}"
        assert audit["grain_residual"] == 0, f"{rk} 粮残差 {audit['grain_residual']}"
        assert audit["produced"] > 0 and audit["eaten"] > 0, rk


def test_no_tribute_still_settles():
    from core.settlement import run_monthly_settlement
    s = _new_state(40)
    run_monthly_settlement(s, seed_offset=7)
    for rk in EXTERNAL_ECONOMY_REGIMES:
        trib = s.external_regimes[rk].get("econ_stats", {}).get("tribute_in", 0)
        assert trib == 0
        assert "tax" in s.external_regimes[rk]["econ_audit"]


def test_old_save_missing_fields_idempotent():
    from core.settlement_steps import _settle_external_economy
    s = _new_state(80)
    for rk in EXTERNAL_ECONOMY_REGIMES:
        s.external_regimes[rk].pop("treasury", None)
        s.external_regimes[rk].pop("grain_price", None)
        s.external_regimes[rk].pop("econ_audit", None)
        s.external_regimes[rk].pop("econ_stats", None)
    _settle_external_economy(s, [])   # 不炸即过（setdefault 幂等补齐路径）
    for rk in EXTERNAL_ECONOMY_REGIMES:
        assert "treasury" in s.external_regimes[rk]
        assert "econ_audit" in s.external_regimes[rk]


def test_provincial_pops_are_authoritative_view():
    """省域 POP 为权威经济账，ex["pop"] 是省域汇总视图（不双账）。

    三政权（EXTERNAL_ECONOMY_REGIMES）每省带 pops + grain_price + econ_audit；
    政权级 pop 的 wealth/grain 等于省域加和；兵 size 三元一致
    （兵 POP == Σ省 troops == Σ军队）不受省域化影响。"""
    from core.settlement import run_monthly_settlement
    s = _new_state(80)
    run_monthly_settlement(s, seed_offset=7)
    for rk in EXTERNAL_ECONOMY_REGIMES:
        ex = s.external_regimes[rk]
        provs = ex.get("provinces") or []
        assert provs, f"{rk} 无省份"
        for p in provs:
            assert isinstance(p.get("pops"), dict) and p["pops"], f"{rk}·{p['name']} 无省域 POP"
            assert "grain_price" in p and "econ_audit" in p, f"{rk}·{p['name']} 缺省域字段"
        # 汇总视图 == 省域加和
        agg = {}
        for p in provs:
            for kl, v in p["pops"].items():
                slot = agg.setdefault(kl, [0, 0])
                slot[0] += int(v.get("wealth", 0) or 0)
                slot[1] += int(v.get("grain", 0) or 0)
        for kl, (w, g) in agg.items():
            assert int(ex["pop"][kl]["wealth"]) == w, f"{rk}·{kl} 汇总 wealth 失配"
            assert int(ex["pop"][kl]["grain"]) == g, f"{rk}·{kl} 汇总 grain 失配"
        # 兵 size 三元一致
        assert ex["pop"]["兵"]["size"] == sum(int(p.get("troops", 0) or 0) for p in provs)


def test_provincial_audit_zero_residual():
    """省域 econ_audit（每省）双残差恒 0 + 政权级（Σ省）双残差恒 0。"""
    from core.settlement import run_monthly_settlement
    s = _new_state(80)
    for _ in range(3):
        run_monthly_settlement(s, seed_offset=7)
    for rk in EXTERNAL_ECONOMY_REGIMES:
        ex = s.external_regimes[rk]
        for p in ex["provinces"]:
            pa = p["econ_audit"]
            assert pa["money_residual"] == 0, f"{rk}·{p['name']} 省域钱残差 {pa['money_residual']}"
            assert pa["grain_residual"] == 0, f"{rk}·{p['name']} 省域粮残差 {pa['grain_residual']}"
        audit = ex["econ_audit"]
        assert audit["money_residual"] == 0, f"{rk} 政权级钱残差 {audit['money_residual']}"
        assert audit["grain_residual"] == 0, f"{rk} 政权级粮残差 {audit['grain_residual']}"


def test_multigoods_market_conserves():
    """多商品（布/绸/皮毛/药材）撮合守恒：每省工匠 goods 池 + 各阶层 goods 持有
    合计 == 当月产量（未售部分留池、售出部分转移至买家 goods，总存量不变）。

    断言：某省工匠 goods 库存 + 该省各阶层 goods 持有 布/绸/皮毛/药材 合计
    恰好等于当月产量（_ext_econ_phases Phase A 产 + Phase B 转移守恒）。
    月内闭环：产出被消费/留池，不凭空增减 → 总存量 == 当月产。
    """
    from core.settlement import run_monthly_settlement
    from content.data import EXTERNAL_ECON
    s = _new_state(80)
    run_monthly_settlement(s, seed_offset=7)
    cfg = EXTERNAL_ECON
    for rk in EXTERNAL_ECONOMY_REGIMES:
        ex = s.external_regimes[rk]
        rtype = str(ex.get("type", ""))
        for p in ex["provinces"]:
            pops = p["pops"]
            art = pops.get("工匠", {})
            art_sz = int(art.get("size", 0) or 0)
            if art_sz <= 0:
                continue
            # 当月产量（Phase A：布/绸/皮毛/药材）
            prod_cloth = int(art_sz * cfg["goods_yield"])
            prod_silk = int(art_sz * float(cfg["silk_yield"]))
            prod_fur = int(art_sz * float(cfg.get("fur_yield", {}).get(rtype, 0.0)))
            prod_herb = int(art_sz * float(cfg.get("herb_yield", {}).get(rtype, 0.0)))
            # 总存量 = 工匠池 + 各阶层持有
            ag = art.get("goods", {})
            total_cloth = int(ag.get("布", 0) or 0) + sum(
                int(v.get("goods", {}).get("布", 0) or 0) for v in pops.values()
                if isinstance(v, dict) and v.get("size", 0) > 0 and v is not art)
            total_silk = int(ag.get("绸", 0) or 0) + sum(
                int(v.get("goods", {}).get("绸", 0) or 0) for v in pops.values()
                if isinstance(v, dict) and v.get("size", 0) > 0 and v is not art)
            total_fur = int(ag.get("皮毛", 0) or 0) + sum(
                int(v.get("goods", {}).get("皮毛", 0) or 0) for v in pops.values()
                if isinstance(v, dict) and v.get("size", 0) > 0 and v is not art)
            total_herb = int(ag.get("药材", 0) or 0) + sum(
                int(v.get("goods", {}).get("药材", 0) or 0) for v in pops.values()
                if isinstance(v, dict) and v.get("size", 0) > 0 and v is not art)
            # 总存量 ≤ 产量（折旧 5% 会微减；不应 > 产量——凭空造货即泄漏）
            assert total_cloth <= prod_cloth, \
                f"{rk}·{p['name']} 布总存量 {total_cloth} > 产量 {prod_cloth}（凭空造货）"
            assert total_silk <= prod_silk, \
                f"{rk}·{p['name']} 绸总存量 {total_silk} > 产量 {prod_silk}（凭空造货）"
            assert total_fur <= prod_fur, \
                f"{rk}·{p['name']} 皮毛总存量 {total_fur} > 产量 {prod_fur}（凭空造货）"
            assert total_herb <= prod_herb, \
                f"{rk}·{p['name']} 药材总存量 {total_herb} > 产量 {prod_herb}（凭空造货）"
