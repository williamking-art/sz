# -*- coding: utf-8 -*-
"""宋祚 · 仓廪漕运与灾荒（从 settlement_steps.py 拆出，零行为变更）。

`_settle_granary` / `_settle_disaster` 及相关守恒配对。"""
from __future__ import annotations

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
    FARMER_SELL_FLOOR,
    BOOM_MULT,
    FARMER_STORE_CAP,
    FARMER_SPOIL_RATE,
    DISASTER_RELIEF_GRAIN,
)

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
        canal_eff = CANAL_MONTHLY_RATE * (1.0 - block / 100.0) * inflow_mult
    else:
        canal_eff = 0.0

    corrupt_avg = _avg_corruption(state)
    loss_rate = CANAL_LOSS_BASE + corrupt_avg * CANAL_LOSS_CORRUPT_WEIGHT
    canal = 0
    for p in state.prefectures.values():
        movable = int(p.get("storage", 0) * canal_eff)
        room = max(0, state.granary_cap - state.granary)
        take = min(movable, room)
        if take > 0:
            loss = int(take * loss_rate)
            p["storage"] -= take
            state.change_granary(take - loss)
            state.granary_stats["canal_loss"] += loss
            canal += (take - loss)
    if canal > 0:
        state.granary_stats["canal_in"] += canal
        log.append(f"[漕运] 诸路上供输粟 {canal}石（途中耗 {state.granary_stats['canal_loss']}石），太仓现 {state.granary}石")

    granary_before_out = state.granary

    # AI 契约：雀鼠耗（outflow 档位调制）
    sparrow = int(state.granary * SPARROW_RAT * outflow_mult)
    if sparrow > 0:
        state.granary = max(0, state.granary - sparrow)
        state.granary_stats["sparrow"] += sparrow
        log.append(f"[雀鼠耗] 仓储月耗 {sparrow}石（存粮折损）")

    pay = state.pay_system.get("grain_ratio", 0.5)
    # 兵口粮联动（蔡权衡定案）：军粮实发按「禁/厢加权实发 + 乡兵缺口自备」口径
    # （乡兵军粮自备，太仓不造粮），故用 calc_army_grain(for_issue=True)
    army_grain_total, _ = state.calc_army_grain(for_issue=True)
    # AI 契约：军粮保障档位调制
    mil_grain = int(army_grain_total * pay * army_supply_mult)
    official_grain_total, _ = state.calc_official_grain()
    off_grain = int(official_grain_total * pay)
    clerk_grain_total, _ = state.calc_clerk_grain()
    clerk_grain = int(clerk_grain_total * pay)
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
                state.prefectures[_rk]["pops"][_cls]["grain"] += _c
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
                              CHANGPING_SELL_RATIO, CHANGPING_PRICE_TARGET_HIGH,
                              CHANGPING_PRICE_TARGET_LOW, PRICE_TARGET_SUPER)
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
            _g, _recycled = _changping_trade(p, name, sell, "sell", price, log, "常平")
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
                _g, _ = _changping_trade(p, name, buy, "buy", price, log, "常平")
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
                _g, _recycled = _changping_trade(p, name, sell, "sell", price, log, "常平·AI")
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
                    _g, _ = _changping_trade(p, name, buy, "buy", price, log, "常平·AI")
                    if _g > 0:
                        p["grain_price"] = _recalc_region_price(state, name, extra_supply=-_g)
                        changping_acted = True

    if changping_acted:
        state._stabilizer_recycled = _recycled_total
        log.append("[常平] 州县常平仓平粜籴，物价稍纾")
        _settle_stabilizer_recycle(state, log)

    # ---- 商品交易（多商品）+ 粮市交易 + 各 POP 消费 ----
    # 工匠产不同商品、各 POP 按阶级买不同商品（钱→工匠/商人，钱守恒；新增商品经 register_finished_good 扩展）
    _eco = getattr(state, "_economy_ai", None) or {}
    # 全游戏级强制 AI（拒绝式）：无经济推演 → 景气消费倍率中性 1.0（不伪造景气档位）
    _boom = BOOM_MULT.get(_eco.get("景气", "中"), 1.0) if _eco else 1.0
    _prod = {"无": 0.0, "微": 0.5, "小": 0.75, "中": 1.0, "大": 1.3, "巨": 1.6, "极": 1.9}.get(_eco.get("生产", "中"), 1.0)  # 生产力度（审查 P1-3：7 档闭合）
    for name, p in state.prefectures.items():
        artisan, merchant = p["pops"]["工匠"], p["pops"]["商人"]
        # 1) 商品单通道（批 4 S2）：成品唯一产出是作坊 PM（`_settle_workshops` 已在
        #    Step 4.5 跑过，产出入 resources/工匠 goods）。原「工匠 size 直产布/绸」
        #    删除；**不断供护栏**：若本月 goods 池为空（作坊缺料停滞），回退旧直产
        #    口径补产，保证成交率 ≥ 改造前 90%。
        _goods_empty = all(int(v or 0) <= 0 for v in artisan.get("goods", {}).values()) \
            if isinstance(artisan, dict) else True
        if _goods_empty:
            from core.production_chain import goods_direct_production_backup
            goods_direct_production_backup(artisan, merchant, prod_mult=_prod)
        # 2) 各 POP 按阶级买商品（有钱就消费，wealth 弹性收敛；买家支出全额入工匠/商人，钱守恒）
        for pop_name, pop in p["pops"].items():
            base_rate = GOODS_CONSUME_RATE.get(pop_name, 0.01)   # Phase B 定稿：商品消费率（单一权威源）
            _per_capita = pop["wealth"] / max(pop["size"], 1)
            _elastic = min(3.0, max(1.0, _per_capita / 5.0))
            spend = int(pop["wealth"] * base_rate * _elastic * _boom)
            if spend > 0:
                pop["wealth"] -= spend
                for gdim, share in GOODS_DEMAND.get(pop_name, {"布": 1.0}).items():
                    if share > 0:
                        pop["goods"][gdim] = pop["goods"].get(gdim, 0) + int(spend * share)
                # 尾差归商人（守恒修正）：int(0.7x)+int(0.3x) ≤ x，截断差是无对手方销毁
                # （逐月 ~百贯级残差漂移主源）；改为商人收余款，保证 Σcredit == spend。
                _art_share = int(spend * 0.7)
                artisan["wealth"] += _art_share
                merchant["wealth"] += spend - _art_share
        # 3) 商品折旧（各 POP 持有商品每月 5% 消耗，商品有使用寿命、用完再买，防只增不耗）
        for _pop in p["pops"].values():
            for _gdim in _pop.get("goods", {}):
                _pop["goods"][_gdim] = int(_pop["goods"][_gdim] * 0.95)
        # 3.5) 存货外销变现（蔡权衡裁决：goods 存量 > 库存上限（月产×12）→ 外销
        #      min(存量-上限, 月产×0.3) × GOODS_PRICE 入工匠 wealth；goods 出 == 外部钱入，
        #      守恒（来源=外销，非凭空）；记 statistics["export_income"]）
        try:
            from content.data import GOODS_PRICE, EXPORT_STOCK_MONTHS, EXPORT_RATE
            for _gdim, _gprice in GOODS_PRICE.items():
                _month_prod = int(artisan["size"] * (0.10 if _gdim == "绸" else 0.20) * _prod)
                _cap = _month_prod * EXPORT_STOCK_MONTHS
                _stock = artisan["goods"].get(_gdim, 0)
                if _stock > _cap and _month_prod > 0:
                    _export = min(_stock - _cap, int(_month_prod * EXPORT_RATE))
                    if _export > 0:
                        artisan["goods"][_gdim] = _stock - _export
                        _income = int(_export * _gprice)
                        artisan["wealth"] += _income
                        state.statistics["export_income"] = state.statistics.get("export_income", 0) + _income
                        # 阶段 B-2：外销变现是**真实体外注入**（goods 出、外部钱入），
                        # 登记入货币台账，使对账残差不再把它误算成"凭空造币"。
                        # 见 core/money.py 的 register_flow 与 货币口径规范 §4.2。
                        try:
                            from core.money import register_flow as _reg_flow
                            _reg_flow(state, "external", _income, f"外销变现·{_gdim}")
                        except Exception:  # noqa: BLE001 — 台账登记失败不影响结算
                            pass
        except Exception:
            pass
        # 4) 士绅奢侈消费（蓄养奴婢/园林/宴饮/香火/收藏），消耗财富、钱流向工匠商人（服务），体现"富而奢"
        # Phase B 定稿：奢侈品 = 士绅wealth × 0.01 × 景气倍率（景气驱动，繁荣挥霍、萧条收缩）
        _genty = p["pops"]["士绅"]
        _lux = int(_genty["wealth"] * 0.01 * _boom)
        if _lux > 0:
            _genty["wealth"] -= _lux
            _lux_art = int(_lux * 0.5)
            artisan["wealth"] += _lux_art
            merchant["wealth"] += _lux - _lux_art   # 尾差归商人（守恒修正，奇数 _lux 不再丢 1 贯）
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
    _famine = False
    for name, p in state.prefectures.items():
        price = p.get("grain_price", state.grain_price)
        price_wen = max(int(price * 1000), 1)
        pops = p["pops"]
        # 1) 各 POP 净头寸（need 按职业口粮）
        need_of = {pn: int(pop["size"] * GRAIN_CONSUME_PER_CAPITA.get(pn, 0.5))
                   for pn, pop in pops.items()}
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
            floor = int(pop["size"] * GRAIN_CONSUME_PER_CAPITA.get(pn, 0.5) * price)  # 保底线（贯）
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
                    pops[bname]["grain"] += q
                    _c = int(q * price)
                    pops[bname]["wealth"] -= _c
                    _paid_total += _c
            _seller_items = [(sname, q) for sname, q in _sell_q.items() if q > 0]
            _qtot = sum(q for _, q in _seller_items) or 1
            _left = _paid_total
            for _j, (sname, q) in enumerate(_seller_items):
                pops[sname]["grain"] -= q
                if _j == len(_seller_items) - 1:
                    _c = _left
                else:
                    _c = int(_paid_total * q / _qtot)
                    _left -= _c
                pops[sname]["wealth"] += _c
        # 4) 口粮消费（按职业）：不足则饥荒（农逃荒）
        for pn, pop in pops.items():
            need = need_of[pn]
            if pop["grain"] >= need:
                pop["grain"] -= need
            else:
                pop["grain"] = 0
                # 兵口粮由军粮段（太仓本色）单独保障与惩罚（训练/士气/民心），
                # 本色半折+俸禄折钞、不靠粮市买粮——此处不重复计入民间饥荒 _famine，
                # 防兵永远缺粮→每月 _famine→民心持续 -1（P0 崩盘链一部分）。
                if pn != "兵":
                    _famine = True
                if pn == "农":                    # 农民缺粮 → 逃荒为流民（POP 人数减、本地流民池增）
                    # P0-④ 逃荒降档（0.01 → 0.002）并设单路上限 5 万/月，
                    # 防粮市冲击下农缺粮触发海量流民 → 起义压力爆炸。
                    _flee = min(int(pop["size"] * 0.002), 50_000)
                    pop["size"] -= _flee
                    p["refugees"] = p.get("refugees", 0) + _flee
        # 5) 农储粮上限+霉耗（加消耗兜底·自然消耗）：农 grain > 12石/人 → 超出按 2%/月霉耗核销（收敛 ~12石/人）
        _nong_g = pops["农"]
        _cap_g = _nong_g["size"] * FARMER_STORE_CAP
        if _nong_g["grain"] > _cap_g:
            _spoil = int((_nong_g["grain"] - _cap_g) * FARMER_SPOIL_RATE)
            if _spoil > 0:
                _nong_g["grain"] -= _spoil
                state.granary_stats["farmer_spoil"] = state.granary_stats.get("farmer_spoil", 0) + _spoil
        # 6) 隐户消费（Phase B）：隐户不落籍（每户按 4 口计），吃粮由该路士绅/地主供给（记 hidden_feed）
        _hidden_share = state.land.get("hidden_households", 0) * 4 * p.get("population", 1) / max(state.population, 1)
        _hidden_feed = int(_hidden_share * HIDDEN_CONSUME_PER_CAPITA)
        if _hidden_feed > 0:
            _g0 = pops["士绅"]
            _g0["grain"] = max(0, _g0["grain"] - _hidden_feed)
            state.granary_stats["hidden_feed"] = state.granary_stats.get("hidden_feed", 0) + _hidden_feed
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
                state.prefectures[region]["pops"]["农"]["size"] += used
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
                            state.prefectures[k]["pops"]["农"]["size"] += add
            log.append(f"[赈济·{region}] 开太仓发粟 {relief}石赈灾，本地流民稍安，余者溢邻路")
        else:
            state.population_satisfaction = max(0, state.population_satisfaction - 3)
            log.append(f"[饥馑] 太仓乏粟（仅发 {relief}石），饿殍渐现，逃荒者众！")
        log.append(f"[灾荒] {state.disaster_region} 持续，严重度 {state.disaster_severity}")

    if random.random() < 0.03:
        severity = random.randint(1, 5)
        region = random.choice(["河北", "京东", "两浙", "陕西", "河东", "荆湖"])
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
            flee = min(add_ref, room, p["pops"]["农"]["size"])
            p["pops"]["农"]["size"] -= flee
            p["refugees"] = p.get("refugees", 0) + flee
            # 灾荒减产：受灾路年产减产（8%/级），下次收获即少粮，体现"灾年减产"而非只涨价
            p["grain"] = int(p.get("grain", 0) * (1 - 0.08 * severity))
            log.append(f"[流民] {region}灾荒（{severity}级），本地流民骤增 {flee}，四散就食，田禾减产")
        log.append(f"[灾荒] {region}发生灾荒！严重度 {severity}")
        state.statistics["total_disasters"] += 1


