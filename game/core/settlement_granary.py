# -*- coding: utf-8 -*-
"""宋祚 · 仓廪漕运与灾荒（从 settlement_steps.py 拆出，零行为变更）。

`_settle_granary` / `_settle_disaster` 及相关守恒配对。"""
from __future__ import annotations

import logging
import random

from content.data import (
    CANAL_MONTHLY_RATE,
    SPARROW_RAT,
    CANAL_LOSS_BASE,
    CANAL_LOSS_CORRUPT_WEIGHT,
    CHANGPING_HIGH,
    CHANGPING_LOW,
    GOODS_DEMAND,
    GRAIN_CONSUME_PER_CAPITA,
    HIDDEN_CONSUME_PER_CAPITA,
    GOODS_CONSUME_RATE,
    GOODS_PRICE,
    FARMER_SELL_FLOOR,
    BOOM_MULT,
    FARMER_STORE_CAP,
    FARMER_SPOIL_RATE,
    DISASTER_RELIEF_GRAIN,
)

# 2026-10-11（规格 market-civilian-economy B1）：商品成交**唯一入口**（口径单点）。
from core.domains.economy.market import sellable_stock, trade_goods
# B2-4/B2-5：价格发现与四类价格口径分离（买入价 ≠ 外销价）
from core.market_price import (discover_price, effective_buy_price,
                               record_trade_price, pref_good_key)
# B2-1/2/3：需求分层（温饱线 × 余量释放）
from core.domains.economy.demand import basic_need, demand_release

# 🔴 方案乙 / G-3（2026-10-04）：POP 写入走桥接层 ——
#   · 粮写 `grain_bridge`（写只落一个载体，绝不双写）；
#   · size/wealth 等写 `pop_bridge`（先落州府真账、再刷路级派生镜像）。
# 存量**读取**仍走路级 `pops`（它是桥接维护的镜像）。未下沉时桥接返回 None，调用方回落原写法。
from core.foundation.ledger.grain_bridge import grain_add as _grain_add
from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add

from core.settlement_common import (
    _avg_corruption,
    _recalc_region_price,
    _changping_trade,
    _P1_RELIEF,
)

from core.settlement_finance import (  # 跨域互调
    _settle_stabilizer_recycle,
)

def _settle_granary(state, log):
    """仓廪系统月度结算：漕运汇聚 + 雀鼠耗 + 本色支取 + 常平仓 + 认知层。
    （12 步 agent 化 P2+：仓廪漕运契约接线）"""
    import core.settlement_steps as _settlement_steps  # 延迟：兼容 monkeypatch
    # 12 步 agent 化 P2+：读取仓廪漕运 AI 契约
    _granary_ai = getattr(state, "_granary_ai", None)
    ai_granary = {}
    if isinstance(_granary_ai, dict) and not _granary_ai.get("_error"):
        ai_granary = _granary_ai.get("granary", {})
        if _granary_ai.get("narrative"):
            log.append(f"[仓漕] {_granary_ai['narrative']}")

    block = state.canal_block
    if random.random() < 0.08:
        block = min(100, block + random.randint(3, 8))
    if state.disaster_severity > 0 and random.random() < 0.3:
        block = min(100, block + random.randint(5, 15))
    jin_will = state.external.get("金", {}).get("invasion_will", 0)
    if jin_will >= 80 and random.random() < 0.3:
        block = min(100, block + random.randint(3, 10))
    block = max(0, block - random.randint(0, 2))
    # 🟢 M39c-1：全国级写点走桥（未下沉 ⇒ None ⇒ 回落原写法，行为不变）
    from core.domains.economy import canal_bridge as _cb
    if _cb.canal_set_national(state, block) is None:
        state.canal_block = block

    # AI 契约档位映射（审查 P1：7 档闭环——原 4 档表 无→1.0 错当「小」执行、
    # 巨/极→回落 1.0 低于「大」=档位倒挂）
    tier_map = {"无": 0.0, "微": 0.5, "小": 1.0, "中": 1.5, "大": 2.0,
                "巨": 2.5, "极": 3.0}
    inflow_tier = ai_granary.get("inflow", "小")
    outflow_tier = ai_granary.get("outflow", "小")
    price_stabilize_tier = ai_granary.get("price_stabilize", "小")
    army_supply_tier = ai_granary.get("army_supply", "小")

    inflow_mult = tier_map.get(inflow_tier, 1.0)
    outflow_mult = tier_map.get(outflow_tier, 1.0)
    price_stabilize_mult = tier_map.get(price_stabilize_tier, 1.0)
    army_supply_mult = tier_map.get(army_supply_tier, 1.0)

    # 三运制：漕运非月月进行——一年分春(3月)/夏(6月)/秋(9月)三个运期，
    # 运期当月发纲集中上供，其余月份不发纲（史实纲运节奏：岁漕三运）。
    if state.month in (3, 6, 9):
        # B2-R4 接线：漕运阻断率可被水利/疏浚工程降低（`transport_relief` 效果）。
        # **`None` 表示"未定义"→ 用原阻断率**，不得回落 0（回落 0＝运力全通，凭空增粮）。
        _block_eff = block
        try:
            from core.domains.production.settlement_agri import effective_canal_block
            _rb = effective_canal_block(state, block)
            if _rb is not None:
                _block_eff = _rb
        except Exception as _cb_e:      # noqa: BLE001 — 钩子失败用原值，不阻断
            log.append(f"[漕运][WARN] 农业运力钩子不可用：{_cb_e!r}")
        canal_eff = CANAL_MONTHLY_RATE * (1.0 - _block_eff / 100.0) * inflow_mult
    else:
        canal_eff = 0.0

    corrupt_avg = _avg_corruption(state)
    loss_rate = CANAL_LOSS_BASE + corrupt_avg * CANAL_LOSS_CORRUPT_WEIGHT
    canal = 0
    for rname, p in state.prefectures.items():
        movable = int(p.get("storage", 0) * canal_eff)
        room = max(0, state.granary_cap - state.granary)
        take = min(movable, room)
        if take > 0:
            loss = int(take * loss_rate)
            # 🟢 M40b：州仓写点走桥（未下沉 ⇒ None ⇒ 回落原写法，行为不变）
            from core.foundation.ledger import storage_bridge as _sb
            if _sb.storage_add(state, rname, -take) is None:
                p["storage"] -= take
            state.change_granary(take - loss)
            state.granary_stats["canal_loss"] += loss
            canal += (take - loss)

    if canal > 0:
        state.granary_stats["canal_in"] += canal
        log.append(f"[漕运] 诸路上供输粟 {canal}石（途中耗 {state.granary_stats['canal_loss']}石），太仓现 {state.granary}石")

    granary_before_out = state.granary

    # 仓储损耗（2026-10-18 用户裁定：「粮的损耗不是有天道系统来裁决多寡吗」）：
    # 天道只给 storage_loss 档位（无/轻/中/重），程序按表换算率。
    # ⚠️ 旧实现把损耗挂在 outflow（发仓档位）上，语义错位（出仓多 ≠ 鼠患重）；
    #    此处改为 storage_loss 主导。缺档/无 AI ⇒ 「中」= 既有 1.2%，默认零变更。
    # TODO(P2c)：outflow 档位当前除损耗外无落点，需接到真正的发仓/平粜动作上。
    from core.foundation.ledger.grain_ledger import storage_loss_rate as _loss_rate
    _loss_tier = ai_granary.get("storage_loss", "中")
    _loss_mult = _loss_rate(_loss_tier)
    sparrow = int(state.granary * _loss_mult)
    if _loss_tier != "中" and sparrow > 0:
        log.append(f"[仓储损耗] 天道裁定档位「{_loss_tier}」⇒ 本月损耗率 {_loss_mult:.4f}")
    if sparrow > 0:
        state.granary = max(0, state.granary - sparrow)
        state.granary_stats["sparrow"] += sparrow
        log.append(f"[雀鼠耗] 仓储月耗 {sparrow}石（存粮折损）")

    pay = state.pay_system.get("grain_ratio", 0.5)
    # 🟢 P2c（2026-10-18）：outflow = 本月**发仓总闸门**（天道对"该发多少粮出太仓"的裁决）。
    # 旧实现把 outflow 当损耗倍率用（语义错位，已由 storage_loss 接管）；
    # 现改为作用于本色支出总量：无=0（停发）、微=0.5、小=1.0（与旧行为一致）、中=1.5、大=2.0…
    # 军粮份额仍由 army_supply 决定；赈济走独立契约档位，不在此闸门内。
    _outflow_gate = float(outflow_mult)
    # 兵口粮联动（蔡权衡定案）：军粮实发按「禁/厢加权实发 + 乡兵缺口自备」口径
    # （乡兵军粮自备，太仓不造粮），故用 calc_army_grain(for_issue=True)
    army_grain_total, _ = state.calc_army_grain(for_issue=True)
    # AI 契约：军粮保障档位调制 × 发仓总闸门
    mil_grain = int(army_grain_total * pay * army_supply_mult * _outflow_gate)
    official_grain_total, _ = state.calc_official_grain()
    off_grain = int(official_grain_total * pay * _outflow_gate)
    clerk_grain_total, _ = state.calc_clerk_grain()
    clerk_grain = int(clerk_grain_total * pay * _outflow_gate)
    if _outflow_gate != 1.0:
        log.append(f"[发仓闸门] 天道裁定 outflow 档位 ⇒ 本色支出 ×{_outflow_gate:g}")
    _, corruption_grain_loss = state.calc_corruption_deduction()
    corr_grain = int(corruption_grain_loss * pay)

    need = mil_grain + off_grain + clerk_grain
    given = min(need, state.granary)
    state.change_granary(-given)
    # 收支双向落地：太仓本色支出 → 兵/官僚 POP 粮持有（钱粮循环闭环，不凭空消失）
    if given > 0 and need > 0:
        ratio = given / need
        total_soldiers = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values()) or 1
        total_guan = sum(p["pops"]["官僚"]["size"] for p in state.prefectures.values()) or 1
        soldier_grain = mil_grain * ratio
        guan_grain = (off_grain + clerk_grain) * ratio
        # 尾差归最大府（同 _distribute_pop_wealth）：int() 截断会使 Σ入账 < given，
        # 差额成为无端消失的粮（audit 残差源）。
        for _cls, _lump, _tot in (("兵", soldier_grain, total_soldiers),
                                  ("官僚", guan_grain, total_guan)):
            _lump_i = int(_lump)
            if _lump_i <= 0 or _tot <= 0:
                continue
            _shares = {}
            _big, _big_sz = None, -1
            for _rk, _p in state.prefectures.items():
                _sz = _p["pops"][_cls]["size"]
                if _sz > 0:
                    _shares[_rk] = int(_lump_i * _sz / _tot)
                    if _sz > _big_sz:
                        _big, _big_sz = _rk, _sz
            if _big is None:
                continue
            _shares[_big] += _lump_i - sum(_shares.values())
            for _rk, _c in _shares.items():
                _tg = state.prefectures[_rk]["pops"][_cls]
                if _grain_add(_tg, _c, state) is None:
                    _tg["grain"] += _c
    # 贪腐本色损耗实发受剩余太仓约束：change_granary 有 0 下限，
    # 先截断再出账，保证下方太仓恒等断言在枯竭时仍闭合（不因 clamp 断裂）。
    corr_actual = min(corr_grain, state.granary)
    state.change_granary(-corr_actual)
    # 记录**实际**扣减额（供面板与账本测试读取）。此前测试改为"事后复算"同一条公式，
    # 但复算点在月内的位置与这里不同（官额会因科举在月内变化）→ 会算出 42 石的假残差。
    # 账本测试必须读**台账记录的实扣额**，而不是在别处重算派生量。
    state.granary_stats["corruption_grain"] = \
        state.granary_stats.get("corruption_grain", 0) + corr_actual
    state.granary_stats["military"] += given
    short = need - given
    if short > 0:
        for u in state.army_units:
            u.training = max(10, u.training - 2)
            u.morale = max(10, u.morale - 2)
        log.append(f"[军粮] 太仓乏粮，本色俸饷短 {short}石，士卒困顿")
        state.population_satisfaction = max(0, state.population_satisfaction - 1)
    elif given > 0:
        log.append(f"[俸禄·本色] 支禄米军粮 {given}石（军粮{mil_grain}+官禄{off_grain}+吏禄{clerk_grain}）")

    out_total = sparrow + given + corr_actual
    assert abs((granary_before_out - state.granary) - out_total) < 1, \
        f"太仓恒等断裂：Δ={granary_before_out - state.granary} out={out_total}"

    changping_acted = False
    # T9 常平扩容为货币稳定器：平粜吸买家钱入地方府库（货币回收，不碰内帑；
    # local_treasury 不在 money 公式）。净回收联动：价>2.0 时平粜量上限 60%，
    # 并评估稳定器净回收目标（月销币目标 = money×(price−1.2)/price×0.5）。
    from content.data import (CHANGPING_BUY_BUDGET_RATIO, CHANGPING_CAP_RATIO,
                              CHANGPING_SELL_RATIO)
    _sell_ratio = CHANGPING_SELL_RATIO          # 0.60（价>2.0 档，原 0.45）
    _recycled_total = 0                          # 本月平粜回收累计（稳定器达成度）
    for name, p in state.prefectures.items():
        price = p.get("grain_price", state.grain_price)
        cp_stock = p.get("changping_stock", 0)
        coffer = p.get("local_treasury", 0)
        if price > CHANGPING_HIGH and cp_stock > 0:
            # 平粜（高价抑价）：放常平仓粮入市，钱入地方府库（货币回收，不碰内帑）。
            # 量随价格超幅线性放大：price 1.6→放 5% 常平储、2.5→放 60%（T9 扩容 45%→60%）
            # 审查修复：原实现对手方未建模（粮凭空消失、钱凭空产生），
            # 现经 _changping_trade 与本路民间 POP 成对划转（买不起则少卖）。
            ratio = min(_sell_ratio, (price - CHANGPING_HIGH) * 0.5)
            sell = max(1, int(cp_stock * ratio))
            sell = min(sell, cp_stock)
            _g, _recycled = _changping_trade(p, name, sell, "sell", price, log, "常平", state)
            if _g > 0:
                _recycled_total += _recycled
                # 对账统计：平粜回收（买家钱入地方府库）
                state.statistics["changping_recycled"] = (
                    state.statistics.get("changping_recycled", 0) + _recycled)
                # 放粮入市 → 当地粮价回落（常平抑价的正确触发）
                p["grain_price"] = _recalc_region_price(state, name, extra_supply=_g)
                changping_acted = True
        elif price < CHANGPING_LOW and coffer > 0:
            # 平籴（低价托市）：动用地方府库 50% 预算买粮入常平仓（T9 扩容 30%→50%）。
            # 量不超过当地月供一半，且受常平仓容（月产 100%，T9 扩容 50%→100%）约束，防止无上限膨胀
            budget = int(coffer * CHANGPING_BUY_BUDGET_RATIO)
            monthly_supply = max(p.get("grain", 0) / 12.0, 1.0)
            cap = max(monthly_supply * CHANGPING_CAP_RATIO, 1.0)
            room = max(0, int(cap - cp_stock))
            buy = min(int(budget / max(price, 0.4)), int(monthly_supply * 0.5), room)
            if buy > 0:
                _g, _ = _changping_trade(p, name, buy, "buy", price, log, "常平", state)
                if _g > 0:
                    # 收粮出市 → 当地粮价回升（常平托市的正确触发）
                    p["grain_price"] = _recalc_region_price(state, name, extra_supply=-_g)
                    changping_acted = True
    # AI 契约：平抑物价（price_stabilize 档位调制常平仓操作强度）
    # 注：本分支须排在「稳定器回收结算」之前，其回收额才会计入
    # state._stabilizer_recycled（原顺序在后，致 AI 加强档的销币账漏记，
    # 稳定器「目标 vs 实回收」读数系统性偏低）。
    if price_stabilize_mult > 1.0:
        for name, p in state.prefectures.items():
            price = p.get("grain_price", state.grain_price)
            cp_stock = p.get("changping_stock", 0)
            coffer = p.get("local_treasury", 0)
            if price > CHANGPING_HIGH and cp_stock > 0:
                # AI 加强平粜（T9 扩容：上限 60%）
                ratio = min(_sell_ratio, (price - CHANGPING_HIGH) * 0.5 * price_stabilize_mult)
                sell = max(1, int(cp_stock * ratio))
                sell = min(sell, cp_stock)
                _g, _recycled = _changping_trade(p, name, sell, "sell", price, log, "常平·AI", state)
                if _g > 0:
                    _recycled_total += _recycled
                    state.statistics["changping_recycled"] = (
                        state.statistics.get("changping_recycled", 0) + _recycled)
                    p["grain_price"] = _recalc_region_price(state, name, extra_supply=_g)
                    changping_acted = True
            elif price < CHANGPING_LOW and coffer > 0:
                # AI 加强平籴（T9 扩容：预算 50%、仓容月产 100%）
                budget = int(coffer * CHANGPING_BUY_BUDGET_RATIO * price_stabilize_mult)
                monthly_supply = max(p.get("grain", 0) / 12.0, 1.0)
                cap = max(monthly_supply * CHANGPING_CAP_RATIO, 1.0)
                room = max(0, int(cap - cp_stock))
                buy = min(int(budget / max(price, 0.4)), int(monthly_supply * 0.5), room)
                if buy > 0:
                    _g, _ = _changping_trade(p, name, buy, "buy", price, log, "常平·AI", state)
                    if _g > 0:
                        p["grain_price"] = _recalc_region_price(state, name, extra_supply=-_g)
                        changping_acted = True

    if changping_acted:
        state._stabilizer_recycled = _recycled_total
        log.append("[常平] 州县常平仓平粜籴，物价稍纾")
        _settle_stabilizer_recycle(state, log)

    # ---- 商品交易（多商品）+ 粮市交易 + 各 POP 消费 ----
    # 2026-10-11（B2-R5 审查发现 · P0）：**当月流量键按月清零**。
    # `statistics` 全库无清零点，`price_demand` / `goods_spend` / `goods_traded` /
    # `goods_unmet` / `basics_unmet` 会被逐月累加；而 `discover_price` 把
    # **累计期望需求**与**当月末可售量**配对 ⇒ 价格压力被系统性放大
    # （实测京畿路|布 1814→7923 单调累加）。这些键的语义是**当月流量**，
    # 必须在月初归零。累加值若需长期保留，另设独立 `*_cum` 键。
    _stats_m = getattr(state, "statistics", None)
    if isinstance(_stats_m, dict):
        for _k in ("price_demand", "goods_spend", "goods_traded",
                   "goods_unmet", "basics_unmet"):
            _stats_m.pop(_k, None)
    # 工匠产不同商品、各POP 按阶级买不同商品（钱→工匠/商人，钱守恒；新增商品经 register_finished_good 扩展）
    _eco = getattr(state, "_economy_ai", None) or {}
    # 全游戏级强制 AI（拒绝式）：无经济推演 → 景气消费倍率中性 1.0（不伪造景气档位）
    _boom = BOOM_MULT.get(_eco.get("景气", "中"), 1.0) if _eco else 1.0
    _prod = {"无": 0.0, "微": 0.5, "小": 0.75, "中": 1.0, "大": 1.3, "巨": 1.6, "极": 1.9}.get(_eco.get("生产", "中"), 1.0)  # 生产力度（审查 P1-3：7 档闭合）
    for name, p in state.prefectures.items():
        artisan, merchant = p["pops"]["工匠"], p["pops"]["商人"]
        # 1) 商品供给（**真实来源**：作坊成品 → 工匠 goods 池）
        # 2026-10-11（B1-5，用户裁定「移除兜底直产，让消费无货则不买」）：
        #   原 `goods_direct_production_backup` 兜底直产**已移除**——它按工匠 size 直接
        #   凭空补布/绸，是"虚拟供给"的另一来源。供给改由 `_settle_workshops`
        #   （麻坊/丝坊 → 工匠 goods 池）提供；无货则**不买**，记未满足。
        # 2) 各 POP 按阶级买商品（**真实成交**：扣钱 ⇄ 扣工匠库存，无货不买）
        # 2026-10-11（规格 market-civilian-economy B1-5，用户裁定）：
        #   原实现 `pop["wealth"] -= spend; pop["goods"][g] += spend*share`
        #   **扣钱后凭空给货**（虚拟供给），已改为经`core/market.trade_goods` 真成交：
        #   卖方＝工匠 goods 池（`purpose="resale"`），成交量受**真实可售量**约束。
        #   无货 → 记未满足（`no_stock_local`），**不产生凭空商品**。
        for pop_name, pop in p["pops"].items():
            base_rate = GOODS_CONSUME_RATE.get(pop_name, 0.01)   # Phase B 定稿：商品消费率（单一权威源）
            _per_capita = pop["wealth"] / max(pop["size"], 1)
            _elastic = min(3.0, max(1.0, _per_capita / 5.0))
            # B2-2：**余量释放**（阶层需求 × 财富余量，用户 2026-10-01 定论）。
            # 温饱线以下 → 释放 0（不买）；温饱线未配置该阶层 → 1.0（现状口径）。
            _rel = demand_release(pop_name, _per_capita)
            if _rel is None or _rel <= 0:
                if _rel is not None:
                    # 温饱线以下：基本需求未满足**如实记录**（不是"没需求"）
                    _st_u = getattr(state, "statistics", None)
                    if isinstance(_st_u, dict):
                        _bu = _st_u.setdefault("basics_unmet", {})
                        for _d0 in (GOODS_DEMAND.get(pop_name, {}) or {}):
                            _q0 = basic_need(pop_name, _d0, pop["size"])
                            if _q0:
                                _bu[_d0] = _bu.get(_d0, 0) + int(_q0)
                continue
            _want_spend = int(pop["wealth"] * base_rate * _elastic * _boom * _rel)
            if _want_spend <= 0:
                continue
            for gdim, share in GOODS_DEMAND.get(pop_name, {"布": 1.0}).items():
                if share <= 0:
                    continue
                # B2-R2：价格按**本路**读取（不再全局共享）。
                _px = effective_buy_price(dim=gdim, state=state, pref=name)
                _price = float(_px.get("price") or 0.0)
                if _price <= 0:
                    continue
                _want_qty = int(_want_spend * share / _price)
                if _want_qty <= 0:
                    continue
                _r = trade_goods(state, dim=gdim, qty=_want_qty, price=_price,
                                 buyer=pop, seller=artisan,
                                 purpose="resale", trade_id=None)
                _stats = getattr(state, "statistics", None)
                if isinstance(_stats, dict):
                    _stats["goods_spend"] = float(_stats.get("goods_spend", 0) or 0) \
                        + float(_r.get("paid", 0) or 0)
                    _gtr = _stats.setdefault("goods_traded", {})
                    _gtr[gdim] = _gtr.get(gdim, 0) + int(_r.get("traded", 0) or 0)
                    # 未满足原因四分解（与 B0-3 读数口径一致）：零需求单列，
                    # 涨价导致的买不起归入购买力不足，不另计一类。
                    if int(_r.get("unmet_qty", 0) or 0) > 0:
                        _un = _stats.setdefault("goods_unmet", {})
                        _un[_r["reason"]] = _un.get(_r["reason"], 0) + int(_r["unmet_qty"])
                    # B2-R2：需求键统一为 `(route, good)`；**记录期望需求**（`_want_qty`）
                    # 而非仅成交量——高未满足需求必须反映在价格压力里。
                    _pd = _stats.setdefault("price_demand", {})
                    _pdk = pref_good_key(name, gdim)
                    _pd[_pdk] = _pd.get(_pdk, 0) + int(_want_qty)
                # 登记**本路**动态成交均价（**不改基准表**，B2-5；路级键 B2-R2）
                if int(_r.get("traded", 0) or 0) > 0:
                    record_trade_price(state, gdim, pref=name,
                                       paid=float(_r.get("paid", 0) or 0),
                                       qty=float(_r.get("traded", 0) or 0))
        # 3) 商品折旧（各 POP 持有商品每月 5% 消耗，商品有使用寿命、用完再买，防只增不耗）
        # 2026-10-03：`goods` 含 `治所→{dim:n}` 州府桶，须只对**商品维**折旧，
        # 否则会对 dict 做乘法（旧写法直接炸 `unsupported operand *: 'dict' and 'float'`）。
        from core.domains.economy.material_trade_ops import commodity_dims
        from core.foundation.ledger import pop_bridge as _pb
        _sales_decay = None
        for _cls_g, _pop in p["pops"].items():
            if not isinstance(_pop, dict):
                continue
            # 🟢 M43 修复：折旧必须落**治所真账**（路级 goods 是派生镜像，直写被覆盖 ⇒
            #   实测该段在下沉档从未生效）。未下沉 ⇒ 空表 ⇒ 回落原写法（行为不变）。
            _decay_map = _pb.pop_goods_decay(p, _cls_g, 0.05)
            if _decay_map:
                from core.domains.economy import stock_flow as _sf
                for _gd, _q in _decay_map.items():
                    _sf.record_out(state, _gd, _q, reason="goods_decay",
                                   custody=_sf.CUSTODY_POP)
                continue
            for _gdim in commodity_dims(_pop.get("goods")):
                _before_g = _pop["goods"][_gdim]
                _pop["goods"][_gdim] = int(_pop["goods"][_gdim] * 0.95)
                _decay = int(_before_g) - int(_pop["goods"][_gdim])
                if _decay > 0:
                    from core.domains.economy import stock_flow as _sf
                    _sf.record_out(state, _gdim, _decay, reason="goods_decay",
                                   custody=_sf.CUSTODY_POP)
        # 3.1) **价格发现（B2-4 ＋ B2-R2 路级修正）**：
        # 供需**同域**——需求取**本路** `(route, good)`，供给取**本路**工匠可售库存，
        # 上期价取**本路**动态价。原实现把多路累计需求与"循环中当前一路"的库存配对，
        # 且动态价全局共享 ⇒ 甲路短缺会带着乙路一起跳价（B2-R2 指控，已修）。
        # `price_demand` 记的是**期望需求**（含未满足），故高未满足会推高价格压力。
        try:
            _stats_g = getattr(state, "statistics", None)
            _pd_all = (_stats_g or {}).get("price_demand") or {}
            if _pd_all:
                _dyn_slot = getattr(state, "dynamic_prices", None)
                if not isinstance(_dyn_slot, dict):
                    _dyn_slot = {}
                    state.dynamic_prices = _dyn_slot
                for _gdim in GOODS_DEMAND.get("农", {"布": 1.0}).keys() | \
                        GOODS_DEMAND.get("士绅", {"绸": 1.0}).keys():
                    _pdk = pref_good_key(name, _gdim)
                    _dq = _pd_all.get(_pdk)
                    if not _dq:
                        continue        # 本路本月无需求 → 不定价（不是"价格为 0"）
                    _sup_q = sellable_stock(seller=artisan, dim=_gdim)
                    _res = discover_price(
                        dim=_gdim, demand_qty=_dq, supply_qty=_sup_q,
                        prev_price=_dyn_slot.get(_pdk))
                    _pv = _res.get("price")
                    if _pv is not None:
                        _dyn_slot[_pdk] = float(_pv)
        except Exception as _pe:      # noqa: BLE001 — 价格发现失败不阻断结算
            (getattr(state, "statistics", None) or {}).setdefault(
                "price_discovery_error", str(_pe)[:200])
        # 3.5) 存货外销变现（B2-R6 · 2026-10-11 接线：换单点，**不改参数**）
        #      口径：`core/export_policy.py` 是外销决策**唯一入口**——
        #      `free=max(0, 存量−国内承诺需求预留)` → `surplus=max(0, free−月产×12)`
        #      → `qty=min(surplus, 月产×0.3, 存量)` → `income=qty×GOODS_PRICE`。
        #      **不重复出售是结构性保证**：只认**内销真成交后**的存量，
        #      从不读内销前库存，也不自行扣内销量。
        #      ⚠️ 累计键 `export_income` **不得**在无外销时写 0——`statistics` 整局不清零，
        #      累计 0 ＝"整局从未外销"≠"本月无外销"；本月 0 走 `export_month` 读数。
        try:
            from core.export_policy import (apply_export_decision, export_decision,
                                            export_unit_price, read_artisan_stock)
            _st = getattr(state, "statistics", None) or {}
            for _gdim in GOODS_PRICE:
                # 月产重估留在**结算层**（属结算估算，不复制进模块）
                _month_prod = int(artisan["size"] * (0.10 if _gdim == "绸" else 0.20) * _prod)
                _dec = export_decision(
                    dim=_gdim,
                    stock=read_artisan_stock(state, name, _gdim),   # 内销后的真实存量
                    month_prod=_month_prod,
                    price=export_unit_price(_gdim),
                    pref=name,
                    domestic_sold_qty=int((_st.get("goods_traded") or {}).get(_gdim, 0) or 0),
                    # domestic_commitment_qty=待 `goods_unmet` 升级为 (路,商品) 后补
                )
                apply_export_decision(state, _dec, seller=artisan, log=log)
        except Exception as e:  # noqa: BLE001 — 已改为记入结算日志（失败可见）
            # 审查 P2-3 应修：原只有结算日志一行、**无 traceback**。补 logging.exception。
            logging.getLogger("settlement").exception("[外销] 外销变现失败（goods/wealth 未变）")
            log.append("[外销] 外销变现失败，本月未变现（goods/wealth 未变）"
                       f"（{type(e).__name__}）")
        # 4) 士绅奢侈消费（蓄养奴婢/园林/宴饮/香火/收藏），消耗财富、钱流向工匠商人（服务），体现"富而奢"
        # Phase B 定稿：奢侈品 = 士绅wealth × 0.01 × 景气倍率（景气驱动，繁荣挥霍、萧条收缩）
        _genty = p["pops"]["士绅"]
        _lux = int(_genty["wealth"] * 0.01 * _boom)
        if _lux > 0:
            if _pop_obj_add(state, _genty, "wealth", -_lux) is None:
                _genty["wealth"] -= _lux
            _lux_art = int(_lux * 0.5)
            if _pop_obj_add(state, artisan, "wealth", _lux_art) is None:
                artisan["wealth"] += _lux_art
            _lux_mer = _lux - _lux_art   # 尾差归商人（守恒修正，奇数 _lux 不再丢 1 贯）
            if _pop_obj_add(state, merchant, "wealth", _lux_mer) is None:
                merchant["wealth"] += _lux_mer
    # ---- 士绅囤粮操作（AI 推演档位优先，无 AI 按粮价方向兜底；钱粮守恒）----
    # B1（A1）出清顺序裁决：士绅先售、农售余量——士绅囤抛先于下方"非农缺粮买农粮"执行，
    # 与农售粮共用同一批缺粮 POP（工匠/商人/官僚/兵）的 wealth 池：先扣士绅粮款，
    # 剩余可支付余力才买农粮，写死防双重扣款（同一笔钱不得两处买粮）。
    _settlement_steps._settle_civilian_hoard(state, log)

    # 粮市净头寸撮合（Phase B 定稿）：各 POP 净头寸 = 持有 − 消费 need；盈余者入卖方池、
    # 缺口者入买方池；买方池 = Σmin(缺口, (wealth−保底线)/区域价)；按卖方供给占比分配
    # （农保底 FARMER_SELL_FLOOR）；买方扣款 == 卖方收款（尾差归末位）；净头寸单边参与防双重扣款。
    # 顺序：士绅囤抛（_settle_civilian_hoard）先售（B1），本撮合处理余量——缺粮 POP 先扣士绅粮款、
    # 剩余可支付余力才入本撮合买方池，写死防双重扣款（同一笔钱不得两处买粮）。
    from content.data import GRAIN_CONSUME_PER_CAPITA
    from core.foundation.ledger.occupation import food_need_of   # M35-C-2 单点口径
    _famine = False
    for name, p in state.prefectures.items():
        price = p.get("grain_price", state.grain_price)
        price_wen = max(int(price * 1000), 1)
        pops = p["pops"]
        # 1) 各 POP 净头寸（need 按职业口粮）
        # 1) 各 POP 净头寸（need 按口粮；🟢 M35-C-2：**有效人口**含职业附加，单点口径）
        need_of = {pn: int(food_need_of(pops, pn)) for pn, pop in pops.items()}
        sellers = []
        for pn, pop in pops.items():
            surplus = max(0, pop["grain"] - need_of[pn])
            if pn == "农":
                # P0-① 农存粮安全垫：保留 1 个月口粮不卖（可卖 = grain − 2×need），
                # 防农存粮被粮市系统性抽干 → 非收获月缺粮 → 1% 逃荒 → 流民爆炸。
                surplus = max(0, surplus - need_of[pn])
            if surplus > 0:
                sellers.append((pn, surplus))
        buyers = []
        buyer_pool = 0
        for pn, pop in pops.items():
            short = max(0, need_of[pn] - pop["grain"])
            if short <= 0:
                continue
            floor = int(food_need_of(pops, pn) * price)  # 保底线（贯；🟢 M35-C-2 含职业附加）
            # 可购量：wealth（贯）按文级单价折算石（×1000 对齐 price_wen=文/石，防贯/文 1000 倍量级 bug）
            can_buy = min(short, (max(0, pop["wealth"] - floor) * 1000) // price_wen)
            if can_buy > 0:
                buyers.append((pn, can_buy))
                buyer_pool += can_buy
        # 2) 撮合：成交 = min(买方池, 卖方供给)
        sell_total = sum(s for _, s in sellers)
        if sell_total > 0 and buyers:
            trade = min(buyer_pool, sell_total)
            # 诊断统计：粮市撮合月成交量（石），供回归断言防 P0 量级 bug（买方池饿死）
            state.granary_stats["grain_market_trade"] = state.granary_stats.get("grain_market_trade", 0) + trade
            # 卖方分配：按盈余占比，农保底 FARMER_SELL_FLOOR（权重抬升，防农被挤出粮市）
            _sw = {}
            for sname, s in sellers:
                w = s / sell_total
                if sname == "农":
                    w = max(w, FARMER_SELL_FLOOR)
                _sw[sname] = w
            _wsum = sum(_sw.values())
            _sell_q = {}
            _left = trade
            _snames = list(_sw.keys())
            for j, sname in enumerate(_snames):
                q = int(trade * _sw[sname] / _wsum)
                if j == len(_snames) - 1:
                    q = _left                    # 尾差归末位（trade ≤ sell_total 保证不超盈余）
                _sell_q[sname] = q
                _left -= q
            # 买方分配：按可购占比（trade ≤ buyer_pool 保证不超可购）
            _buy_q = {}
            _left = trade
            for i, (bname, can_buy) in enumerate(buyers):
                q = int(trade * can_buy / buyer_pool)
                if i == len(buyers) - 1:
                    q = _left
                _buy_q[bname] = q
                _left -= q
            # 3) 落地：卖方 grain −、wealth +；买方 grain +、wealth −（钱粮双向守恒，总量 == trade）
            # 守恒修正：买卖两侧原本各自 int(q*price) 截断，Σ卖收 ≠ Σ买付（差额成无对手方
            # 销毁/造币）。改为买方扣款求和后，卖方按份额分得**同一笔实付额**（尾差归末位）。
            _paid_total = 0
            for bname, q in _buy_q.items():
                if q > 0:
                    if _grain_add(pops[bname], q, state) is None:
                        pops[bname]["grain"] += q
                    _c = int(q * price)
                    if _pop_obj_add(state, pops[bname], "wealth", -_c) is None:
                        pops[bname]["wealth"] -= _c
                    _paid_total += _c
            _seller_items = [(sname, q) for sname, q in _sell_q.items() if q > 0]
            _qtot = sum(q for _, q in _seller_items) or 1
            _left = _paid_total
            for _j, (sname, q) in enumerate(_seller_items):
                if _grain_add(pops[sname], -q, state) is None:
                    pops[sname]["grain"] -= q
                if _j == len(_seller_items) - 1:
                    _c = _left
                else:
                    _c = int(_paid_total * q / _qtot)
                    _left -= _c
                if _pop_obj_add(state, pops[sname], "wealth", _c) is None:
                    pops[sname]["wealth"] += _c
        # 4) 口粮消费（按职业）：不足则饥荒（农逃荒）
        # 判据**单点**：`food_insecure_headcount`（自有粮 ＋ 购粮能力 = 能吃到几成）。
        # 用户 2026-10-01 定稿：逃荒人数由**实际吃不上饭的人数**1:1 派生，
        # 不再用「size × 0.2%」这类比例魔数（上限仍作爆版保护，见 FLEE_CAP_PER_ROUTE）。
        from core.settlement_common import FLEE_CAP_PER_ROUTE, food_insecure_headcount
        _hungry_map = food_insecure_headcount(pops, price)
        _famine_total = 0
        for pn, pop in pops.items():
            need = need_of[pn]
            # 实际消费：先扣自有粮（粮账必须真扣，否则 Σ粮 不守恒）
            if (pop.get("grain") or 0) >= need:
                if _grain_add(pop, -need, state) is None:
                    pop["grain"] -= need
            # 缺粮判定（单点 `food_insecure_headcount`：自有粮 ＋ 购粮能力）
            hungry = int(_hungry_map.get(pn, 0) or 0)
            if hungry > 0:
                # 兵口粮由军粮段（太仓本色）单独保障与惩罚，本色半折+俸禄折钞、不靠粮市买粮
                # ——此处**不**重复计入民间饥荒 `_famine`，防兵永远缺粮→每月 _famine
                # → 民心持续 -1（P0 崩盘链的一部分）。
                if pn != "兵":
                    _famine = True
                    _famine_total += hungry
                if pn == "农":       # 农缺粮 → 逃荒为流民（人数＝缺粮人数，1:1）
                    _flee = min(hungry, FLEE_CAP_PER_ROUTE, int(pop["size"]))
                    if _flee > 0:
                        # U0001f534 2026-10-08：改走桥接。路级 `size` 在已下沉档中是**派生镜像**，
                        #   直写会被 `sync_route_pops` 撤销（流民增了但农不减 → 人口平白增长）。
                        #   未下沉时返回 None → 回退原路径，行为不变。
                        if _pop_obj_add(state, pop, "size", -_flee) is None:
                            pop["size"] -= _flee
                        p["refugees"] = p.get("refugees", 0) + _flee
        state.statistics["grain_hungry"] = state.statistics.get("grain_hungry", 0) + _famine_total
        # 5) 农储粮上限+霉耗（加消耗兜底·自然消耗）：农 grain > 12石/人 → 超出按 2%/月霉耗核销（收敛 ~12石/人）
        _nong_g = pops["农"]
        _cap_g = _nong_g["size"] * FARMER_STORE_CAP
        if _nong_g["grain"] > _cap_g:
            # B2-R4 接线：霉耗率可被农业投资（常平仓储/谷仓设施）降低。
            # **返回 `None` 表示"未定义"→ 按原始基率处理，不得回落 0**
            # （回落 0 会凭空取消霉耗，凭空增粮）。
            _spoil_rate = FARMER_SPOIL_RATE
            try:
                from core.domains.production.settlement_agri import effective_spoil_rate
                _r = effective_spoil_rate(state, name, FARMER_SPOIL_RATE)
                if _r is not None:
                    _spoil_rate = _r
            except Exception as _se_e:      # noqa: BLE001 —钩子失败用基率，不阻断
                log.append(f"[霉耗][WARN] 农业霉耗钩子不可用：{_se_e!r}")
            _spoil = int((_nong_g["grain"] - _cap_g) * _spoil_rate)
            if _spoil > 0:
                if _grain_add(_nong_g, -_spoil, state) is None:
                    _nong_g["grain"] -= _spoil
                state.granary_stats["farmer_spoil"] = state.granary_stats.get("farmer_spoil", 0) + _spoil
        # 6) 隐户消费（B1c）：隐户**自产自食**——先扣本路 `农` POP 的粮，不足部分才由该路
        #    士绅/地主兜底（庇护关系）。B1a 起隐户按路存在 → 逐路按**本路隐户口**计，
        #    不再按在籍比例摊派（旧"按路摊派"口径已被子池结构取代）。
        _hidden_route = max(0, int((pops.get("农") or {}).get("hidden", 0) or 0))
        _hidden_feed = int(_hidden_route * HIDDEN_CONSUME_PER_CAPITA)
        if _hidden_feed > 0:
            _nong_g = pops["农"]
            _from_self = min(_hidden_feed, max(0, int(_nong_g.get("grain", 0) or 0)))
            if _from_self > 0:
                _ns = int(_nong_g.get("grain", 0) or 0) - _from_self
                if _grain_add(_nong_g, -_from_self, state) is None:
                    _nong_g["grain"] = _ns
            _rest = _hidden_feed - _from_self
            if _rest > 0:
                _g0 = pops["士绅"]
                # 审查 O3：士绅兜底量原被 `max(0, …)` **静默截断**，但统计仍记**全额**
                # `_hidden_feed` → 「喂了多少粮」与「实际扣了多少粮」不同源（同 S3/S4 类）。
                # 现记**实扣额**；士绅无粮则实喂 < 应喂，如实反映为差额（不粉饰）。
                _g0_before = max(0, int(_g0.get("grain", 0) or 0))
                _g0_after = max(0, _g0_before - _rest)
                if _grain_add(_g0, _g0_after - _g0_before, state) is None:
                    _g0["grain"] = _g0_after
                _rest = min(_rest, _g0_before - _g0_after)
            _fed = _from_self + _rest
            state.granary_stats["hidden_feed"] = state.granary_stats.get("hidden_feed", 0) + _fed
            if _fed < _hidden_feed:
                state.granary_stats["hidden_feed_short"] = (
                    state.granary_stats.get("hidden_feed_short", 0) + (_hidden_feed - _fed))
                log.append(f"[隐户] 本路隐户应喂 {_hidden_feed}石，仅实喂 {_fed}石"
                           f"（士绅兜底不足，缺 {_hidden_feed - _fed}石）")
    if _famine:
        state.population_satisfaction = max(0, state.population_satisfaction - 1)

    state.economy_history.append({
        "granary": state.granary,
        "granary_cap": state.granary_cap,
        "grain_price": state.grain_price,
        "price_level": state.price_level,
        "coin_shortage": state.coin.get("shortage", 0.3),
        "canal_block": state.canal_block,
        # 认知层滞后快照（供脱敏层做"奏报延迟"，AI 看到的是上月数而非实时）
        "treasury": state.treasury,
        "imperial_treasury": state.imperial_treasury,
        "refugee_count": state.refugee_count,
    })
    if len(state.economy_history) > 12:
        state.economy_history = state.economy_history[-12:]
    if state.economy_history:
        state.economy_knowledge = dict(state.economy_history[-1])


def _normalize_disaster_region(state, region):
    """把灾荒 region 俗名归一到 prefectures 稳定键。"""
    if not region:
        return None
    if region in state.prefectures:
        return region
    for key, p in state.prefectures.items():
        if p.get("name") == region:
            return key
    for key, p in state.prefectures.items():
        name = p.get("name", key)
        if region in key or region in name:
            return key
    return None


def _settle_disaster(state, log):
    """天灾结算。灾荒时开仓赈济，耗太仓存粮；有粮则安民，无粮则民怨更重。

    12 步 agent 化 P1：有 _relief_ai 契约（按察使）时赈济量/流民按档位换算（10万~50万石、
    流民 ±5万~±30万），灾级 1~5 放大既有减产/粮价；无契约走既有 DISASTER_RELIEF_GRAIN。
    守恒铁律：赈济扣太仓/流民回流农 POP 由本步程序守恒（agent 只给档位词）。
    """
    _relief_ai = getattr(state, "_relief_ai", None)
    relief_grain = DISASTER_RELIEF_GRAIN
    if isinstance(_relief_ai, dict) and not _relief_ai.get("_error"):
        relief_grain = _P1_RELIEF.get(_relief_ai.get("relief", "微"), DISASTER_RELIEF_GRAIN)
        # 灾级 1~5 放大既有公式（减产/粮价由灾荒触发方按 severity 处理）
        state.disaster_severity = max(1, min(5, int(_relief_ai.get("disaster_level", 1))))
    if state.disaster_severity > 0:
        state.disaster_severity = max(0, state.disaster_severity - 1)
        relief = min(relief_grain, state.granary)
        state.change_granary(-relief)
        state.granary_stats["relief"] += relief
        if relief >= relief_grain:
            state.population_satisfaction = max(0, min(100, state.population_satisfaction + 1))
            relieved = relief * 3000
            region = _normalize_disaster_region(state, state.disaster_region)
            if region is not None:
                local = state.prefectures[region].get("refugees", 0)
                used = min(relieved, local)
                state.prefectures[region]["refugees"] = max(0, local - used)
                # 人口守恒（QA 定位修复）：本地安置流民回流农 POP（流民→自耕农/佃户），
                # 防止"流民减少但人口凭空消失"；人口守恒：本地 used + 邻路 Σadd == 流民减少 == 农 POP 增加。
                _f = state.prefectures[region]["pops"]["农"]
                if _pop_obj_add(state, _f, "size", used) is None:
                    _f["size"] += used
                spill = relieved - used
            else:
                used = 0
                spill = relieved
            if spill > 0:
                others = {k: v.get("refugees", 0) for k, v in state.prefectures.items()}
                tot = sum(others.values())
                if tot > 0:
                    for k, rv in others.items():
                        # add 受该路流民存量约束（min(rv)）：每路最多安置其全部流民，
                        # 防止赈济能力（relief×3000）远超流民存量时"超额安置"凭空创造人口。
                        add = min(int(spill * rv / tot), rv)
                        if add > 0:
                            state.prefectures[k]["refugees"] = max(0, state.prefectures[k]["refugees"] - add)
                            # 人口守恒（QA 定位修复）：溢邻路安置流民回流该路农 POP
                            _fk = state.prefectures[k]["pops"]["农"]
                            if _pop_obj_add(state, _fk, "size", add) is None:
                                _fk["size"] += add
            log.append(f"[赈济·{region}] 开太仓发粟 {relief}石赈灾，本地流民稍安，余者溢邻路")
        else:
            state.population_satisfaction = max(0, state.population_satisfaction - 3)
            log.append(f"[饥馑] 太仓乏粟（仅发 {relief}石），饿殍渐现，逃荒者众！")
        log.append(f"[灾荒] {state.disaster_region} 持续，严重度 {state.disaster_severity}")

    # 灾情档位化（2026-10-19）：是否成灾仍按频次模型；严重度由天道出档位
    # （轻/中/重/极重），程序换算 1–5；天道缺档 ⇒ 程序均匀兜底并标来源。
    from core.domains.events.disaster_tier import resolve_disaster
    _ds = resolve_disaster(state)
    if _ds["occur"]:
        severity = _ds["severity"]
        region = _ds["region"]
        if _ds.get("note"):
            log.append("[天意] " + str(region) + "：" + str(_ds.get("note"))
                       + "（" + str(_ds.get("source")) + "）")
        state.disaster_severity = severity
        state.disaster_region = region
        state.population_satisfaction = max(0, state.population_satisfaction - severity * 2)
        road_key = _normalize_disaster_region(state, region)
        if road_key is not None:
            p = state.prefectures[road_key]
            add_ref = severity * 5000
            cap = int(p.get("population", 1_000_000) * 0.10)  # 人口(口)上限
            # BUG#2 修复（人口守恒，与 BUG#1 对称）：灾荒新发流民不再凭空增——
            # flee 受 add_ref、流民 cap 余量与农 POP size 三重约束；
            # 受灾农 POP 减少 flee（逃荒为流民），流民增加 flee，人口不凭空增减。
            room = max(0, cap - p.get("refugees", 0))
            _fp = p["pops"]["农"]
            flee = min(add_ref, room, _fp["size"])
            if _pop_obj_add(state, _fp, "size", -flee) is None:
                _fp["size"] -= flee
            p["refugees"] = p.get("refugees", 0) + flee
            # 灾荒减产：受灾路年产减产（8%/级），下次收获即少粮，体现"灾年减产"而非只涨价
            p["grain"] = int(p.get("grain", 0) * (1 - 0.08 * severity))
            log.append(f"[流民] {region}灾荒（{severity}级），本地流民骤增 {flee}，四散就食，田禾减产")
        log.append(f"[灾荒] {region}发生灾荒！严重度 {severity}")
        state.statistics["total_disasters"] += 1


