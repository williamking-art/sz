# -*- coding: utf-8 -*-
"""宋祚 · 经济基础与外部经济（从 settlement_steps.py 拆出，零行为变更）。

人口田土、识字率、地区深化、扩展维度、外邦经济、作坊与士绅囤抛。"""
from __future__ import annotations

import random

from content.data import (
    MATERIAL_PRICE_BASE,
    RESOURCE_DIMS,
    GRAIN_CONSUME_PER_CAPITA,
    POP_FLOW_RATE,
    URBAN_SPLIT,
    TIER_RANGE,
    FINANCE_DECIDE_BASE,
    SEED_GRAIN_PER_MU,

    HOARD_SPOIL_RATE,
    HOARD_DRAW_RATE,
    HOARD_CAP_MULT,
    HOARD_COPPER_RATIO_BASE,
)

from core.settlement_common import (
    _collect_from_pops,
)

# G-3 粮迁移（2026-10-04 · H 裁定为甲）：POP 存粮的读写统一走桥接层，
# 写只落一个载体（`goods[米]` 或旧 `.grain`），**绝不双写**。
# ⚠️ 迁移分片推进中：`pops[].grain` 仍有 390 处触点未改，
# 本文件内**已改的段落**与**未改段落**共用桥接，故两种载体可并存而不会双写。
from core.foundation.ledger.grain_bridge import grain_add as _grain_add, grain_get as _grain_get, grain_set as _grain_set

# 🔴 方案乙（2026-10-04 用户裁定：POP 实体下沉州府级）：POP **写入**走桥接层，
# 由它先落州府真账、再刷新路级派生镜像，杜绝漂移。存量**读取**仍走路级 `pops`（派生镜像）。
# ⚠️ 未下沉（无 `seats`）时桥接返回 None，调用方回落原写法。
from core.foundation.ledger.pop_bridge import (pop_add as _pop_add, pop_obj_add as _pop_obj_add,
                             pop_obj_set as _pop_obj_set)

from core.settlement_finance import (  # 跨域互调
    _refresh_jiaozi_credit,
    _settle_jiaozi_term,
)

from core.domains.construction.settlement_tech import (  # 跨域互调
    _settle_tech_research,
)

from core.building_jobs import (  # 宋侧岗位口径 + 就业驱动阶层流动（见 _settle_economy 2b）
    song_job_cfg,
    apply_employment_flow,
)
from core.foundation.ledger.pop_structure import move_pop_people  # B1d-b：跨 POP 迁移**带财富/粮**（人均连续）

# 宋侧岗位配置：模块级构建一次（`song_job_cfg()` 返回新 dict，不污染外邦 `EXTERNAL_ECON`
# 全局表；只需改 `core/building_jobs.song_job_cfg` 一处即可换口径）。
_SONG_JOB_CFG = song_job_cfg()

def _settle_economy(state, log):
    """经济基础结算"""
    # 整改①-3：记录**月初**物价，供物价相位（`_settle_econ_prices`）做单月涨跌上限。
    # 本步是月度第一个经济相位，必须在任何改价之前取。
    state._price_month_open = {
        "level": float(getattr(state, "price_level", 1.0) or 1.0),
        "grain": float(getattr(state, "grain_price", 1.0) or 1.0),
        "route": {n: float(p.get("grain_price", 0) or 0)
                  for n, p in state.prefectures.items()},
    }
    # 人口自然净增长（审查 2026-09 调参）：按在籍人口月化比率 + 死亡/疫病随机抖动，
    # 使长局人口稳中有升（原固定 randint(-5000,15000) 期望 +0.5 万/月，年化仅 0.075%）
    from content.data import POP_GROWTH_RATE, POP_GROWTH_JITTER
    growth = int(state.population * POP_GROWTH_RATE) + random.randint(-POP_GROWTH_JITTER, POP_GROWTH_JITTER)
    state.population = max(10_000_000, state.population + growth)
    _boom = (getattr(state, "_economy_ai", None) or {}).get("景气", "中")
    _exam_open = state.exam.get("open")
    # 增长分摊份额分母：各路在籍基准之和（恒定 = PREFECTURE_INFO population 合计 = 1 亿）。
    # 不能用"增长后的动态 state.population"做分母——否则 Σshare<1，农流入比 growth 系统性
    # 少 growth²/总人口，破 ΔΣPOP==growth 守恒不变式（审查回归修复）。
    _pop_base_total = sum(p.get("population", 0) for p in state.prefectures.values()) or 1
    # 合并4次遍历为1次：人口增长分配 → POP职业流动 → 科举入仕 → 流民吸收
    for name, p in state.prefectures.items():
        pops = p["pops"]
        # 1) 人口自然增长/萎缩落到各路农 POP（农民为主，按各路人口比例摊）
        if growth != 0:
            share = p.get("population", 1) / _pop_base_total
            # U0001f534 2026-10-08：改走桥接（新局已下沉，路级 `size` 是**派生镜像**）。
            #   原直写路级会被 `sync_route_pops` 撤销（人口增长**丢失**）。
            #   未下沉时 `pop_obj_add` 返回 None → 回退原路径，行为不变。
            _fld = "农"
            _delta = int(growth * share)
            if _pop_obj_add(state, pops[_fld], "size", _delta) is None:
                pops[_fld]["size"] = max(0, pops[_fld]["size"] + _delta)
        # 2) POP 职业流动（AI 化·Phase B 定稿）：城市化/回乡档位 → 程序换算速率，net 流守恒。
        #    全游戏级强制 AI（拒绝式）：无 _economy_ai（经济推演未注入）→ 城市化/回乡/科举
        #    一律「无」（不流动、不伪造档位）；有推演才按档位流动。
        _eco = getattr(state, "_economy_ai", None) or {}
        _boom = _eco.get("景气", "中") if _eco else None

        def _flow_tier(key, fallback):
            v = _eco.get(key)
            return v if v in TIER_RANGE else fallback

        _tier_city = _flow_tier("城市化", "中" if _boom in ("中", "大") else "无")
        _tier_back = _flow_tier("回乡", "中" if _boom == "微" else "无")
        rate_city = POP_FLOW_RATE["城市化"] * TIER_RANGE.get(_tier_city, 0.0)
        rate_back = POP_FLOW_RATE["回乡"] * TIER_RANGE.get(_tier_back, 0.0)
        urban = round(pops["农"]["size"] * rate_city)
        back = round((pops["工匠"]["size"] + pops["商人"]["size"]) * rate_back)
        net = urban - back
        if net > 0:
            net = min(net, pops["农"]["size"])                 # 钳制：农不减负
            # B1d-b：迁移**带财富/粮**（人均连续）——城市化不是"人在两池间凭空跳"
            _to_art = int(net * URBAN_SPLIT["工匠"])
            _to_mer = net - _to_art
            if _to_art > 0:
                move_pop_people(pops["农"], pops["工匠"], _to_art, state)
            if _to_mer > 0:
                move_pop_people(pops["农"], pops["商人"], _to_mer, state)
        elif net < 0:
            _out = min(-net, pops["工匠"]["size"] + pops["商人"]["size"])  # 钳制：工/商不减负
            _art_out = min(int(_out * URBAN_SPLIT["工匠"]), pops["工匠"]["size"])
            # B1d-b：回乡同样**带财富/粮**（否则"回乡者两手空空"= 人均假信号）
            if _art_out > 0:
                move_pop_people(pops["工匠"], pops["农"], _art_out, state)
            _mer_out = _out - _art_out
            if _mer_out > 0:
                move_pop_people(pops["商人"], pops["农"], _mer_out, state)
        # 2b) 就业驱动的阶层流动（宋侧接线）：**岗位缺口驱动**的农 ↔ 工匠/商人。
        #     与 2) 的关系＝协同而不双计：2) 是「景气驱动」的量（AI 城市化/回乡档位），
        #     本段**串行于其后**，只补「建筑岗位缺口」的差额，且按当月真实就业安排
        #     （`allocate_employment`）与 `JOB_FLOW_RATE` 封顶；同月同一路只有一个方向
        #     （农→工/商 与 工/商→农 互斥），故不存在同一人的两次迁移。
        #     新局 `buildings` 为空 → `apply_employment_flow` 直接返回零迁移，基线不漂移。
        #     守恒：只改 农/工匠/商人 三类 size，Σ六类 size 逐字不变（另见回归测试）。
        _emp_flow = apply_employment_flow(p, pops, p.get("buildings"), _SONG_JOB_CFG, state=state)
        if _emp_flow["moved_to_artisan"] or _emp_flow["moved_to_merchant"] \
                or _emp_flow["returned_to_farm"]:
            p.setdefault("econ_audit", {})["job_flow"] = dict(_emp_flow)
        # 3) 科举入仕已改为**离散科次**（阶段 C-6，§15）：见 `core/officialdom._triennial_exam`
        #    —— 每 EXAM_INTERVAL_YEARS 年一次，一次入仕一批（数百人），落在**待阙**池。
        #    此处不再做每月连续小额入仕：那既不符合史实形态（一期数百进士），
        #    也让"同年/座主"这类真实政治结构无从表达。
        # 4) 流民吸收（跨路迁入，非本地农户流出）
        # 语义澄清（审查复核结论，勿按「方向反了」误改）：absorb 为**流入率**——
        # 治理良好（mood/govern 高、unrest 低）时吸引外来流民迁入本路，故写成
        # local + delta；其 cap（本路人口 5%）也只对流入成立。
        # 已知取舍：跨路迁入未与来源路配对（全局人口账因此非闭合），
        # tests/test_pop_identity.py 已将此列为「设计内·非闭合」科目并断言其公式。
        local = p.get("refugees", 0)
        if local > 0 or p.get("unrest", 15) >= 20:
            mood = p.get("mood", 55)
            unrest = p.get("unrest", 15)
            govern = p.get("govern", 55)
            absorb = (mood - 50) * 0.001 + (40 - unrest) * 0.0008 + (govern - 50) * 0.0006
            delta = int(local * absorb)
            cap = int(p.get("population", 1_000_000) * 0.05)
            new_local = max(0, min(local + delta, cap))
            if new_local != local:
                p["refugees"] = new_local


def _settle_land_local(state, log):
    """田亩户籍与地方州县自然演进；田赋以实物粮（本色）征收入各州府储粮，
    或（行一条鞭后）折银入国库。粮产率随科技/工业、田亩随开垦动态变化。
    （12 步 agent 化 P2+：田亩地方契约接线）"""
    # 隐田分成参数：**函数内取属性**（模块属性读取），便于测试 monkeypatch 与后续调参热改
    from content.data_constants import HIDDEN_LAND_TENANT_SHARE
    # 12 步 agent 化 P2+：读取田亩地方 AI 契约
    _land_ai = getattr(state, "_land_local_ai", None)
    ai_prefs = {}
    if isinstance(_land_ai, dict) and not _land_ai.get("_error"):
        ai_prefs = _land_ai.get("prefectures", {})
        if _land_ai.get("narrative"):
            log.append(f"[田亩] {_land_ai['narrative']}")

    # 2026-09-27：原 `arrival = state.calc_arrival_rate()` 算完即弃（本函数未用到账率）——已删

    hyd = state.tech.get("hydraulics", 40) / 100.0
    tech = state.tech.get("level", 50) / 100.0
    tech_target = 0.6 + hyd * 0.6 + tech * 0.3
    yield_val = state.land.get("yield", 1.0)
    state.land["yield"] = max(0.3, min(2.5, yield_val * 0.97 + tech_target * 0.03))

    if state.land.get("wasteland", 0) > 0:
        cultivate = int(max(20, state.population // 4000))  # 人口(口)→亩
        cultivate = min(cultivate, state.land["wasteland"])
        state.land["cultivated"] += cultivate
        state.land["wasteland"] -= cultivate

    state.land["cultivated"] += int(state.land["cultivated"] * 0.002)
    state.land["hidden_rate"] = min(0.6, state.land["hidden_rate"] + 0.003)

    # ---- 土地演化（开局初值可变化）：自然兼并 + 诡名寄产（隐田）----
    for name, p in state.prefectures.items():
        # 自然兼并：自耕农破产卖地给士绅（每月 0.1%，北宋土地兼并的长期趋势）
        _transfer = int(p.get("self_farm_land", 0) * 0.001)
        p["self_farm_land"] = max(0, p.get("self_farm_land", 0) - _transfer)
        p["gentry_land"] = p.get("gentry_land", 0) + _transfer
        # 诡名寄产/诡名子户：士绅把地主田藏到别人名下逃税（地主田→隐田，随中立派势力增减）
        _gentry_power = state.factions.get("中立派", {}).get("influence", 50) / 100.0
        _conceal = int(p.get("gentry_land", 0) * 0.001 * (0.5 + _gentry_power))
        p["gentry_land"] = max(0, p.get("gentry_land", 0) - _conceal)
        p["hidden_land"] = p.get("hidden_land", 0) + _conceal

    _, grain_by = state.calc_monthly_grain()
    land_grain = int(sum(grain_by.values()))

    # 产粮按田亩归属分配 + 田赋按田亩归属征（粮是田产的）
    _harvest = state.month in (3, 6, 9)
    # 审查 S4：一条鞭分支的 `total_income` 原按**名义税粮**折银计收入，而实际只征到
    # `got_nong + got_shen`（不足记欠税）→ 统计口径比国库实收多（实测 +648,313/月）。
    # 故此处累加**实征银**，与国库 Δ  treasury 同源。
    _silver_actual = 0
    for name, p in state.prefectures.items():
        # AI 契约档位映射
        ai_pref = ai_prefs.get(name, {})
        tax_fair_tier = ai_pref.get("tax_fair", "小")
        ai_mood = ai_pref.get("mood", "平实")

        # 档位力度表（审查 P1：7 档闭环——原 4 档表缺 无/巨/极：
        # 无→默认 1.0 竟与「小」同效、巨/极→回落 1.0 低于「大」=档位倒挂）
        tier_map = {"无": 0.0, "微": 0.5, "小": 1.0, "中": 2.0, "大": 3.0,
                    "巨": 4.0, "极": 5.0}

        # 均税力度（AI 契约加成）
        tax_fair_boost = tier_map.get(tax_fair_tier, 1.0)

        # 地方民情：AI 契约档位词 → 程序映射为数值（AI 只给定性，数值程序定）
        _mood_map = {"安定": 75, "平实": 55, "动荡": 35}
        if ai_mood in _mood_map:
            p["mood"] = _mood_map[ai_mood]

        tax = int(grain_by.get(name, 0))
        _land = max(float(p.get("land", 1)), 1.0)
        _nong, _shen = p["pops"]["农"], p["pops"]["士绅"]
        if _harvest:
            produce = int(p["grain"] / 3.0)
            _grain_add(_nong, int(produce * p.get("self_farm_land", 0) / _land), state)          # 自耕田→自耕农
            _gp = int(produce * p.get("gentry_land", 0) / _land)
            _grain_add(_nong, _gp // 2, state); _grain_add(_shen, _gp // 2, state)                      # 地主田→佃户半+士绅半
            _op = int(produce * p.get("official_land", 0) / _land)
            # 官田→佃户半 + 太仓半。
            # 审查修复（静默丢粮）：change_granary 有 cap 封顶，原未先查余量
            # → 满仓时该半份粮被 cap 吞掉且不留痕（漕运段已先算 room，此处对齐）。
            # 现按余量截断，仓不容者归佃户，粮量不凭空消失；统计只记实际入仓数。
            _op_half = _op // 2
            _room = max(0, int(getattr(state, "granary_cap", 1 << 30))
                        - int(getattr(state, "granary", 0) or 0))
            _op_in = min(_op_half, _room)
            _grain_add(_nong, _op_half - _op_in, state)
            if _op_in > 0:
                state.change_granary(_op_in)
                state.granary_stats["official"] = (
                    state.granary_stats.get("official", 0) + _op_in)
            _ip = int(produce * p.get("imperial_land", 0) / _land)
            _grain_add(_nong, _ip // 2, state); state.imperial_granary += _ip // 2              # 皇庄→佃户半+内帑粮
            # 隐田（不籍）产出（B1c）：**隐户自产 70% / 庇护士绅 30%** —— 修正"隐户只有消费
            # 没有生产"与文档 §3.7"隐户全产归己"的冲突；两份额之和 == 原全额 ⇒ Σ粮守恒不变。
            _hp = int(produce * p.get("hidden_land", 0) / _land)
            _hp_own = int(_hp * HIDDEN_LAND_TENANT_SHARE)
            _grain_add(_nong, _hp_own, state)
            _grain_add(_shen, _hp - _hp_own, state)
            if _hp_own:
                state.statistics["hidden_produce"] = (
                    state.statistics.get("hidden_produce", 0) + _hp_own)
        # 田赋按田亩归属征：自耕田→自耕农、地主田→士绅；官田皇庄免、隐田逃税
        _st = int(tax * p.get("self_farm_land", 0) / _land); _gt = int(tax * p.get("gentry_land", 0) / _land)
        # AI 契约：均税力度减轻赋税负担
        if tax_fair_boost > 1.0:
            _st = int(_st * (1.0 - min(0.2, tax_fair_boost * 0.05)))
            _gt = int(_gt * (1.0 - min(0.2, tax_fair_boost * 0.05)))
        if state.single_whip:
            # 一条鞭：田赋折银——粮留给民间，从农/士绅 wealth 按税粮比例征银入国库（守恒）
            price = max(float(state.grain_price), 0.1)
            silver_nong = int(_st * price)
            silver_shen = int(_gt * price)
            got_nong = state.transfer_money(f"pop:{name}:农", "treasury", silver_nong) if silver_nong else 0
            got_shen = state.transfer_money(f"pop:{name}:士绅", "treasury", silver_shen) if silver_shen else 0
            short = (silver_nong + silver_shen) - (got_nong + got_shen)
            _silver_actual += (got_nong + got_shen)
            if short > 0:
                # 🔴 一条鞭短收的「欠税」也是 POP 真账：桥接后落治所，再刷新路级镜像。
                _dn = silver_nong - got_nong
                if _pop_obj_add(state, _nong, "欠税", _dn) is None:
                    _nong["欠税"] = int(_nong.get("欠税", 0)) + _dn
                _ds = silver_shen - got_shen
                if _pop_obj_add(state, _shen, "欠税", _ds) is None:
                    _shen["欠税"] = int(_shen.get("欠税", 0)) + _ds
        else:
            # 本色征粮：**只按实征入库**（审查 M1）。原实现按 `max(0, …)` 从农/士绅存粮扣
            # 名义税额，却把**名义全额**记入 `storage` → 存粮不足时凭空多出等额仓粮
            # （实测 +899,480 石/月）。现改为：扣多少、入库多少，缺口如实记账但不并入
            # `欠税`（该科目单位为贯且有逐月追缴段，粮缺口以石计，混入会污染单位语义）。
            # 🔴 G-3：读走桥接层（缺失 ⇒ 视作 0 石存粮，按实征入库，缺口如实记账）
            _avail_n = _grain_get(_nong) or 0
            _avail_s = _grain_get(_shen) or 0
            _got_n = min(_st, _avail_n)
            _got_s = min(_gt, _avail_s)
            _grain_set(_nong, _avail_n - _got_n, state)
            _grain_set(_shen, _avail_s - _got_s, state)
            _got_tot = _got_n + _got_s
            # 🟢 M40b：州仓写点走桥（未下沉 ⇒ None ⇒ 回落原写法，行为不变）
            from core.foundation.ledger import storage_bridge as _sb
            if _sb.storage_add(state, name, _got_tot) is None:
                p["storage"] = p.get("storage", 0) + _got_tot

            _tax_grain_short = (_st - _got_n) + (_gt - _got_s)
            if _tax_grain_short > 0:
                state.granary_stats["tax_grain_short"] = (
                    state.granary_stats.get("tax_grain_short", 0) + _tax_grain_short)
                log.append(f"[田赋·本色] {name} 应征粮 {_st + _gt}石，实征 {_got_n + _got_s}石，"
                           f"欠 {_tax_grain_short}石（仓中无粮，按实征入廪）")
        # 种粮（加消耗完整定案）：播种预留 = 耕地亩 × SEED_GRAIN_PER_MU / 12（石/月，约250万石/月），
        # 从农存粮扣（农户备种，真实粮耗不造币；口粮已改「纯口粮」口径防双计）
        _seed = int(p.get("land", 0) * SEED_GRAIN_PER_MU / 12.0)
        if _seed > 0:
            _grain_set(_nong, max(0, (_grain_get(_nong) or 0) - _seed), state)
            state.granary_stats["seed_grain"] = state.granary_stats.get("seed_grain", 0) + _seed
    if state.single_whip:
        if land_grain > 0:
            # 审查 S4：按**实征银**计收入（与国库 Δ 同源），不再按名义税粮折银。
            state.statistics["total_income"] += int(_silver_actual)
            log.append(f"[田赋·一条鞭] 两税折银（应收税粮当量 {land_grain}石）"
                       f"按 wealth 实征银 {_silver_actual}贯入国库，不足记欠税")
    else:
        state.granary_stats["tax"] += land_grain      # 应收（核定）口径
        if land_grain > 0:
            # 应收 vs 实征分清：实征已逐路记入 `storage`，欠征部分在上面的逐路日志里。
            _short_tot = int(state.granary_stats.get("tax_grain_short", 0) or 0)
            log.append(f"[田赋] 两税本色应收粮 {land_grain}石（三运期各征 1/3 年产），"
                       f"分储诸路仓廪；累计欠征 {_short_tot}石")

    # 整改①-3（物价）：权威物价相位在**货币信用之后**（`_settle_econ_prices`）；
    # 此处先按当期供需试算一次，供粮食市场（常平籴粜）与财政（俸禄指数化/粜粮完税）当月使用。
    # 单月涨跌一律受月度上限约束（挂月初价），避免灾荒/AI 造成的价格跳变向下游传导。
    from core.game_state_econ import cap_monthly_price as _cap_price
    from content.data import PRICE_LEVEL_MONTHLY_CAP, GRAIN_PRICE_MONTHLY_CAP
    _open = getattr(state, "_price_month_open", None) or {}
    _prev_level = float(_open.get("level", state.price_level) or state.price_level)
    _prev_grain = float(_open.get("grain", state.grain_price) or state.grain_price)
    state.price_level = _cap_price(_prev_level, state.calc_price_level(),
                                   PRICE_LEVEL_MONTHLY_CAP)
    state.grain_price = _cap_price(_prev_grain, state.calc_grain_price(),
                                   GRAIN_PRICE_MONTHLY_CAP)
    for name, p in state.prefectures.items():
        _prev_route = float((_open.get("route") or {}).get(name, _prev_grain) or _prev_grain)
        p["grain_price"] = _cap_price(_prev_route, state.calc_region_grain_price(name),
                                      GRAIN_PRICE_MONTHLY_CAP)
        target = state.population_satisfaction
        if p["mood"] > target:
            p["mood"] = max(target, p["mood"] - 1)
        elif p["mood"] < target:
            p["mood"] = min(target, p["mood"] + 1)
        p["govern"] = max(20, min(100, p["govern"] + random.randint(-1, 1)))
        p["grain"] = int(p["grain"] * 1.002)

    for yname, y in state.yamen.items():
        # 政务积压增长（§11.6 第一行）：原为 `random.randint(0, 3)` —— 一个**无载体的随机**，
        # 与"有司拖延"的成因完全脱钩。现改为 **净积压 = W − C_eff**：
        #   W     = 本路政务量（案牍件/月，见 core/clerks.route_workload）
        #   C_eff = 吏数 × (1 − 吏怨/100)，即"吏数够、但吏怨高 → 有效处理能力不足"
        # 于是「冗吏」与「积压」可以并存（§16.6 的史实悖论），且玩家有明确杠杆
        # （少下诏 / 裁并机构 / 增吏 / 治吏怨）。吏制不可用时退化为旧的随机项。
        try:
            from core.clerks import backlog_gain as _bg
            # 六部 yamen 与路的对应：近似按 yamen 名匹配路（无匹配则取全国均值增量）
            _route = yname if yname in state.prefectures else None
            if _route:
                _gain = _bg(state, _route)
            else:
                _gains = [_bg(state, r) for r in state.prefectures]
                _gain = sum(_gains) / max(1, len(_gains))
        except Exception as e:  # noqa: BLE001
            # 审查 P2-3 应修：原静默 `except Exception: _gain = float(random.randint(0,3))`
            # —— 吏制步坏掉时积压照旧随机涨，玩家/开发者都看不出用的是兜底值。
            from core.settlement_common import note_settlement_error
            note_settlement_error(
                state, "clerks_backlog", "吏治",
                f"政务积压按兜底随机项估算（clerks.backlog_gain 不可用：{type(e).__name__}）",
                log=log, exc=e)
            _gain = float(random.randint(0, 3))
        y["backlog"] = max(0, int(y["backlog"] + _gain - y["efficiency"] / 40))
        y["efficiency"] = max(20, min(100, y["efficiency"] + random.randint(-2, 1)))


def _settle_econ_prices(state, log=None):
    """物价相位（整改①-1 / ①-3）：在**货币信用**（`_settle_extensions`）之后重算物价。

    固定相位顺序：生产→工程投入→POP收入消费→粮食商品市场→税收转移→货币信用→**物价**→集团读数→提交。
    本步是月度**权威**物价读数（只写价格字段，**不碰钱粮账户**，无守恒影响）：
      - 全国 PRICE_LEVEL = 货币有效供给/实物产出（M1 口径，`calc_price_level`），单月涨跌受上限；
      - 全国粮价 = 物价 × 季节 × 丰歉 × 灾级，单月涨跌受上限；
      - 路线粮价 = 供给/需求/库存/运输/货币有效供给派生（`calc_region_grain_price`），同受上限。
    全国 PRICE_LEVEL 只是**加权读数**（`state.grain_price_readout`），不反向驱动路线价。
    """
    from core.game_state_econ import cap_monthly_price as _cap_price
    from content.data import PRICE_LEVEL_MONTHLY_CAP, GRAIN_PRICE_MONTHLY_CAP
    _open = getattr(state, "_price_month_open", None) or {}
    _prev_level = float(_open.get("level", state.price_level) or state.price_level)
    _prev_grain = float(_open.get("grain", state.grain_price) or state.grain_price)
    state.price_level = _cap_price(_prev_level, state.calc_price_level(),
                                   PRICE_LEVEL_MONTHLY_CAP)
    state.grain_price = _cap_price(_prev_grain, state.calc_grain_price(),
                                   GRAIN_PRICE_MONTHLY_CAP)
    _reads = []
    for name, p in state.prefectures.items():
        _prev_route = float((_open.get("route") or {}).get(name, _prev_grain) or _prev_grain)
        p["grain_price"] = _cap_price(_prev_route, state.calc_region_grain_price(name),
                                      GRAIN_PRICE_MONTHLY_CAP)
        _reads.append(p["grain_price"])
    # 全国加权读数（只读派生，不反向驱动路线价）
    _tot = sum(p.get("population", 0) for p in state.prefectures.values())
    if _tot > 0:
        _w = sum(float(p.get("grain_price", state.grain_price) or 0)
                 * p.get("population", 0) for p in state.prefectures.values())
        state.grain_price_readout = round(_w / _tot, 4)
    if log is not None and _reads:
        log.append(f"[物价] 全国物价指数 {state.price_level:.3f}，"
                   f"粮价读数 {state.grain_price:.3f}"
                   f"（路线价 {min(_reads):.3f}~{max(_reads):.3f}贯/石）")


def _settle_literacy(state, log=None):
    """识字率结算步（2026-09-19 新增设定）——薄壳，口径单点在 `core/domains/culture/literacy.py`。

    教育是慢变量：每月只走 6% 的差距（缓动），故太平与文教投入**长期**抬高识字率，
    而识字率又是**诏令实际效果的弱关联项**（强关联只有吏治，见 `core/decree_effect.py`）。
    零守恒风险：只写 `prefectures[路]["literacy"]` 与派生值 `state.literacy`，不碰钱粮人口。
    """
    try:
        from core.domains.culture.literacy import settle_literacy as _impl
        return _impl(state, log)
    except Exception as e:  # noqa: BLE001  文教步失败不得影响结算主流程
        # 审查 P2-3 应修：原只有结算日志一行、**无 traceback** → 玩家知道"跳过了"，
        # 开发者却拿不到定位信息。此处补 `logging.exception`（玩家可见 + 可定位）。
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "literacy", "文教",
            f"识字率结算跳过（{type(e).__name__}）", log=log, exc=e, level="exception")
        return {"routes": 0, "national": None, "changed": 0, "error": type(e).__name__}


def _settle_region_deepen(state, log):
    """地区模型深化月度结算（参考《明末：捞金模拟器》）。

    对每路补充字段做动态演化：
      - public_support（民心）：随 mood/unrest/治理度 演化；
      - gentry_resistance（士绅抵抗）：随清丈/抑兼并/士绅影响力 演化；
      - city_defense（城防）：随军备/边患 演化；
      - fiscal（财政）：随月税/支出 演化；
      - controlled_by（控制势力）：默认宋，领土争夺时由 AI/事件改写。
    轻量 O(路数)，不引入 N+1 查询；数值走既有 state 字段，不破坏守恒。
    """
    from content.data import PREFECTURE_TYPE_FRONTIER, PREFECTURE_TYPE_CAPITAL
    for name, p in state.prefectures.items():
        # 民心：随动乱与治理演化（mood 同源，向 mood 收敛）
        mood = p.get("mood", 50)
        unrest = p.get("unrest", 15)
        support = p.get("public_support", mood)
        # 动乱高则民心降，治理高则民心升
        drift = (mood - support) * 0.1 - (unrest - 15) * 0.05
        p["public_support"] = max(0, min(100, support + drift))

        # 2. 士绅抵抗：随士绅影响力与清丈力度演化
        gentry = p.get("gentry_resistance", 30)
        gentry_power = 0.0
        try:
            gentry_power = state.factions.get("中立派", {}).get("influence", 50) / 100.0
        except Exception as e:  # noqa: BLE001
            # 审查 P2-3 应修：原静默 pass → 士绅抵抗按 `gentry_power = 0.0`（既有兜底值，
            # **口径不动**）演化，而日志一字无，读者会以为"士绅毫无影响力"是真实读数。
            from core.settlement_common import note_settlement_error
            note_settlement_error(
                state, "region_deepen_gentry", "地区深化",
                f"士绅影响力读数失败，沿用兜底值 0.0（{type(e).__name__}）",
                log=log, exc=e)
        # 清丈（land_survey 施行）则士绅抵抗上升；治理高则下降
        survey = 1.0 if state.land.get("survey_active") else 0.0
        gentry_drift = (gentry_power - 0.5) * 2 + survey * 2 - (p.get("govern", 50) - 50) * 0.02
        p["gentry_resistance"] = max(0, min(100, gentry + gentry_drift))

        # 3. 城防：随军备/边患演化（边镇自然加固，腹里缓慢）
        defense = p.get("city_defense", 40)
        p_type = p.get("type", "腹里州路")
        if p_type in PREFECTURE_TYPE_FRONTIER:
            defense_drift = 0.3
        elif p_type == PREFECTURE_TYPE_CAPITAL:
            defense_drift = 0.1
        else:
            defense_drift = -0.05
        p["city_defense"] = max(0, min(100, defense + defense_drift))

        # 4. 财政：随月税与支出演化（地方财政健康度）
        fiscal = p.get("fiscal", 50)
        monthly_tax = p.get("monthly_tax", 200_000)
        # 财政健康度向"月税充足"收敛
        fiscal_target = max(0, min(100, round(monthly_tax / 8000)))
        p["fiscal"] = fiscal + (fiscal_target - fiscal) * 0.05

        # 5. 控制势力：默认宋，领土争夺由事件/命令改写（此处不主动改）
        p.setdefault("controlled_by", "宋")


def _settle_extensions(state, log):
    """金融/科举/科技/外交 等扩展维度的自然演进。

    经济金融推演接入（蔡权衡定稿）：读 _economy_ai 金融 5 字段（三态词）→ 程序换算
    （FINANCE_DECIDE_BASE CAP 封顶），守恒由既有公式（交子超发崩溃/市舶关税/钱荒联动
    tax_coeff）保证——AI 只给方向词，不触碰守恒数值。
    """
    import core.settlement_steps as _settlement_steps  # 延迟：兼容 monkeypatch
    _fin = getattr(state, "_economy_ai", None) or {}
    _bank_on = getattr(state, "bank", {}).get("established", False) \
        if isinstance(getattr(state, "bank", None), dict) else False

    _fdb = FINANCE_DECIDE_BASE   # 审查 P2-53：金融调制幅度/值域唯一权威源
    if state.jiaozi["issued"] > 0:
        _ceiling = state._jiaozi_ceiling()                    # 可发额度 = 准备金 × 准备金率（皇威放宽）
        over = max(0, state.jiaozi["issued"] - _ceiling)
        # 金融调制（交子信任/发行——三态词，CAP ±5 / +100万）
        _jt_cfg = _fdb["jiaozi_trust"]
        _jt = _fin.get("jiaozi_trust", "稳")
        if _jt == "增":
            state.jiaozi["trust"] = min(_jt_cfg["max"], state.jiaozi["trust"] + _jt_cfg["cap"])
        elif _jt == "跌":
            state.jiaozi["trust"] = max(_jt_cfg["min"], state.jiaozi["trust"] - _jt_cfg["cap"])
        if _fin.get("jiaozi_issued") == "增" and over <= 0:
            # 增发须 ≤ 可发额度（超发由下方既有超发逻辑触发崩溃）。
            # 第二节§2：发行额除准备金（皇威放宽）外，还受**税收接受度**与**信用上限**约束
            # ——三者为独立闸门，取最紧（`state.jiaozi_issue_limit()`，只读）。
            _issue_limit = max(0, min(int(_ceiling), int(state.jiaozi_issue_limit())))
            _add = min(_fdb["jiaozi_issued"]["cap"], max(0, _issue_limit - state.jiaozi["issued"]))
            if _add > 0:
                state.jiaozi["issued"] += _add
        over = max(0, state.jiaozi["issued"] - _ceiling)
        if over > 0:
            # 超发→信用崩（trust 降，贬值）+ 铜钱被挤兑囤积→钱荒加剧；皇威高可减缓贬值
            _prestige_factor = 2.0 - state.prestige / 50.0   # 皇威 0→2.0倍(快崩), 100→0(不崩)
            state.jiaozi["trust"] = max(0, state.jiaozi["trust"] - int(over / 1_000_000 * 10 * max(0.0, _prestige_factor)))
            state.coin["shortage"] = min(0.9, state.coin.get("shortage", 0.3) + 0.01)
        else:
            # 适量发钞→缓解钱荒（纸币替代铜钱，铜钱流通压力减）
            state.coin["shortage"] = max(0.1, state.coin.get("shortage", 0.3) - 0.005)
    # ---- 第二节§2：刷新交子数据契约读数（流通额/兑付率/折价/挤兑压力）----
    # 只写派生读数、不动钱粮（ΔW == ΔM_ALL == 0）；银行信贷随后读该挤兑压力做信贷收缩。
    _refresh_jiaozi_credit(state, log)
    # 钱荒调制（缓/加剧 ±0.05，clamp [0.05,0.95]；联动 tax_coeff 由 finance 既有公式）
    _sh_cfg = _fdb["shortage"]
    _sh = _fin.get("shortage", "平")
    if _sh == "缓":
        state.coin["shortage"] = max(_sh_cfg["min"], state.coin.get("shortage", 0.3) - _sh_cfg["cap"])
    elif _sh == "加剧":
        state.coin["shortage"] = min(_sh_cfg["max"], state.coin.get("shortage", 0.3) + _sh_cfg["cap"])
    if state.maritime["open"]:
        # 市舶外贸：关税抽解入国库 + 商人 POP 得外贸利润（白银流入民间）
        _trade_month = state.calc_maritime_trade() / 12.0                     # 月贸易额（贯）
        # 🔴 M179（主线 F · 载体甲，Jev 甲 0.875 / 维度分配甲 0.550）：**外贸逐笔流水**。
        # 纪律：① **只记不二次入账**——关税的**唯一**入账通道仍是 `_settle_finance`（见下方 B1 注释）；
        #      ② 纯函数 `allocate_legs` 负责拆分（**Σ货值 ≡ 总量**，最大余数法），本处**只 append**；
        #      ③ 失败**不影响结算**（warning 留痕）；④ 流水**不是账本**（无余额字段，存量仍落 POP/国库）。
        try:
            from core.domains.economy.trade_ledger import allocate_legs, assert_guards
            _tj_total = int(_trade_month)
            _tj_month = None
            try:
                from core.civil_building import abs_month_index as _ami
                _tj_month = _ami(state)
            except Exception:                                # noqa: BLE001
                _tj_month = None
            _tj = allocate_legs(state, _tj_total, month=_tj_month)
            if _tj["legs"] and not assert_guards(_tj["legs"], state, _tj_total):
                state.trade_journal.extend(_tj["legs"])
        except Exception:                                    # noqa: BLE001
            log.warning("外贸逐笔流水记账失败（不影响结算；缺失≠0）", exc_info=True)
        # 市舶调制（兴/衰：tariff ±0.02 clamp [0.05,0.20]、silver_in ±10 clamp [10,60]）
        _tf_cfg, _sv_cfg = _fdb["tariff"], _fdb["silver_in"]
        _mt = _fin.get("maritime", "平")
        if _mt == "兴":
            state.maritime["tariff"] = max(_tf_cfg["min"], min(
                _tf_cfg["max"], state.maritime.get("tariff", 0.10) + _tf_cfg["cap"]))
            state.maritime["silver_in"] = max(_sv_cfg["min"], min(
                _sv_cfg["max"], state.maritime.get("silver_in", 30) + _sv_cfg["cap"]))
        elif _mt == "衰":
            state.maritime["tariff"] = max(_tf_cfg["min"], min(
                _tf_cfg["max"], state.maritime.get("tariff", 0.10) - _tf_cfg["cap"]))
            state.maritime["silver_in"] = max(_sv_cfg["min"], min(
                _sv_cfg["max"], state.maritime.get("silver_in", 30) - _sv_cfg["cap"]))
        _tariff_rate = state.maritime.get("tariff", 0.10)
        # B1 修复（市舶关税重复计账）：关税的**唯一**入账通道是 _settle_finance
        # （从商人 POP wealth 征收并入 actual_tax → 国库，钱守恒）。此处原再
        # `state.treasury += 关税` 属第二次全额入账且无对手账户（凭空增币），
        # 使国库市舶收入被系统性放大近一倍。只保留商人外贸利润分配与白银流入。
        _merchant_profit = int(_trade_month * (1 - _tariff_rate) * 0.3)       # 商人毛利 30%
        _total_merchant = sum(p["pops"]["商人"]["size"] for p in state.prefectures.values()) or 1
        # 残差修正（两点）：①外贸毛利是**真实体外注入**（货出、外银入），须登记
        # register_flow("external")（同外销变现，货币口径规范 §4.2），否则 marine 开启后
        # 每月凭空造币；②逐府 int() 分摊截断使 Σcredit < 登记额 → 尾差归最大府守恒。
        if _merchant_profit > 0 and _total_merchant > 1:
            _mp_shares = {}
            _mp_big, _mp_big_sz = None, -1
            for _rk, _p in state.prefectures.items():
                _sz = _p["pops"]["商人"]["size"]
                if _sz > 0:
                    _mp_shares[_rk] = int(_merchant_profit * _sz / _total_merchant)
                    if _sz > _mp_big_sz:
                        _mp_big, _mp_big_sz = _rk, _sz
            _mp_shares[_mp_big] += _merchant_profit - sum(_mp_shares.values())
            for _rk, _c in _mp_shares.items():
                _mp = state.prefectures[_rk]["pops"]["商人"]
                if _pop_obj_add(state, _mp, "wealth", _c) is None:
                    _mp["wealth"] += _c
            # 审查 P2-3 / M8：原 `except Exception: pass  # 台账登记失败不影响结算`
            # —— 未登记的体外注入会被对账算成残差（面板误报"凭空造币"）。统一走
            # `register_money_flow`：WARNING + traceback + `money_audit["flow_errors"]`。
            from core.settlement_common import register_money_flow
            register_money_flow(state, "external", _merchant_profit, "外贸商人毛利")
        state.coin["shortage"] = max(0.0, state.coin["shortage"] - 0.01)      # 白银流入缓解钱荒
        # 白银**存量**累积（阶段 B-1）：silver_in 是「万两/年」的**流量**，此前只被
        # calc_price_level 当作白银存量 ×10000 使用，**从未进入任何持有账户**——
        # 既是"把流量当存量"的建模错误，也是货币对账里一笔无对手方的注入。
        # 现按 1/12 月度份额累积进 `state.silver_stock`（外部注入的唯一合法入口，
        # 供 core/money.py 对账时作为外部项扣除——EXTERNAL_ACCOUNTS 已含
        # silver_stock，reconcile 自动把 Δsilver_stock 计为外部项，**勿再**登记
        # register_flow，否则双重扣除）。**不改动任何既有数值**：
        # calc_price_level 仍读 silver_in，silver_stock 在阶段 B-1 只被 money.py 读取。
        try:
            _sv_annual = float(state.maritime.get("silver_in", 0) or 0) * 10000.0   # 万两/年 → 贯/年
            state.silver_stock = int(getattr(state, "silver_stock", 0) or 0) + int(_sv_annual / 12.0)
        except Exception:  # noqa: BLE001 — 对账辅助字段，失败不影响结算
            pass
    # 银行调制（扩/损——仅 established；capital ±20%、准备金 ±50万）
    # 第二节§3 修复：原 `reserve += 50万` 无对手方 = 凭空造币（污染货币对账残差）；
    # 现改为守恒口径——扩 → 国库划入准备金（不足不划）；损 → 准备金核销并记 burn。
    if _bank_on:
        _bk_cfg, _br_cfg = _fdb["bank_capital"], _fdb["bank_reserve"]
        _bk = _fin.get("bank", "稳")
        if _bk == "扩":
            state.bank["capital"] = state.bank.get("capital", 1.0) * _bk_cfg["up"]
            _inj = min(int(_br_cfg["cap"]), int(state.treasury))
            if _inj > 0:
                state.treasury = int(state.treasury) - _inj
                state.bank["reserve"] = int(state.bank.get("reserve", 0) or 0) + _inj
        elif _bk == "损":
            state.bank["capital"] = state.bank.get("capital", 1.0) * _bk_cfg["down"]
            _wdown = min(int(_br_cfg["cap"]), int(state.bank.get("reserve", 0) or 0))
            if _wdown > 0:
                state.bank["reserve"] = int(state.bank.get("reserve", 0) or 0) - _wdown
                from core.foundation.ledger.money import register_flow as _reg_flow
                _reg_flow(state, "burn", _wdown, "银行减资核销准备金")
        # ---- 第二节§3：存款 / 放贷 / 收息 / 坏账月度结算（全部守恒转移）----
        _settlement_steps._settle_bank_credit(state, log)
    state.jiaozi["trust"] = min(100, state.jiaozi["trust"] + 1)
    # 价格系数调制（通胀/通缩 ±5%，挂 calc_price_level ×mult，clamp [0.5,3.0]；月度重置不落档）
    _pm_cfg = _fdb["price_mult"]
    _pt = _fin.get("price_trend", "平")
    _pm = getattr(state, "_price_mult", 1.0)
    if _pt == "通胀":
        _pm = max(_pm_cfg["min"], min(_pm_cfg["max"], _pm * _pm_cfg["up"]))
    elif _pt == "通缩":
        _pm = max(_pm_cfg["min"], min(_pm_cfg["max"], _pm * _pm_cfg["down"]))
    state._price_mult = _pm
    # 大臣家产月度循环（奢侈消费/收租/聚敛窖藏/物议——守恒转移）
    # 审查 P2-3 / M7：整步静默 `pass` → 家产月循环不生效而日志一字无（家产是钱的
    # 真实所在，静默跳过会让"大臣家产不变"被误读成"本月无家产活动"）。现按步位告警。
    try:
        from core.domains.administration.estate_mechanic import settle_minister_estate
        settle_minister_estate(state, log)
    except Exception as e:  # noqa: BLE001
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "minister_estate", "家产",
            f"本月家产月循环未结算：{type(e).__name__}（奢侈消费/收租/窖藏均未施加）",
            log=log, exc=e, level="exception")
    # 投资分期回报（国库/内帑回流，守恒）
    try:
        from core.domains.administration.estate_mechanic import settle_investments
        settle_investments(state, log)
    except Exception as e:  # noqa: BLE001
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "investments", "投资",
            f"本月投资回款未结算：{type(e).__name__}（分期回报未回流，守恒转移缺失）",
            log=log, exc=e, level="exception")
    # 建筑-时代交互（言枢密方案）：下行联动（建筑累积到 era_state 五维）
    try:
        from core.era_mechanic import settle_era_links
        settle_era_links(state, log)
    except Exception as e:  # noqa: BLE001
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "era_links", "时代联动",
            f"建筑-时代联动未结算：{type(e).__name__}", log=log, exc=e)
    # 新旧产业规模化（用户指示）：转型阵痛叙事 + 记忆记录
    try:
        from core.era_mechanic import settle_industry_shift
        settle_industry_shift(state, log)
    except Exception as e:  # noqa: BLE001
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "industry_shift", "产业转型",
            f"新旧产业规模化未结算：{type(e).__name__}", log=log, exc=e)

    state.exam["talent_pool"] = max(0, min(100, state.exam["talent_pool"]
                                           - 1 + int(state.exam["schools"] / 40)))

    state.tech["level"] = max(0, min(100, state.tech["level"] + random.randint(-1, 1)))
    # 建筑反馈科技（用户指示）：学校/书院 → 科技研发加速（tech level 加成）
    try:
        from core.era_mechanic import tech_build_bonus
        _tb = tech_build_bonus(state)
        if _tb > 0:
            # 审查 P2-25 修复：tech_build_bonus 返回浮点（Σ学校等级×0.05），原 `int(_tb)`
            # 把 <1 的加成恒截断为 0（5 所学校 Lv1 → 0.25 → 0，学校加成基本永不生效）。
            # 现累积到小数池，满 1 兑现 1 点科技等级（无截断浪费）。
            _pool = float(state.tech.get("_build_bonus_pool", 0.0) or 0.0) + _tb
            _gain = int(_pool)
            state.tech["_build_bonus_pool"] = round(_pool - _gain, 4)
            if _gain > 0:
                state.tech["level"] = max(0, min(100, state.tech["level"] + _gain))
    except Exception as e:  # noqa: BLE001
        # 审查 P2-3 应修：原静默 pass → 学校/书院科技加成失效而无人知（P2-25 刚修过
        # 这条链路的截断 bug，静默会让"修了还是没生效"无法区分）。
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "tech_build_bonus", "科技建筑",
            f"学校/书院科技加成未结算：{type(e).__name__}", log=log, exc=e)
    state.tech["gunpowder"] = max(0, min(100, state.tech["gunpowder"] + random.randint(-1, 1)))
    state.tech["铁"] = max(0, min(100, state.tech["铁"] + random.randint(0, 1)))
    # west 来源制（整改④.4）：只从贸易/使团/书籍/工匠/战争累积，不再每月凭空 +0.01。
    try:
        from core.asset_context import accrue_west
        accrue_west(state)
    except Exception as e:  # noqa: BLE001
        # 审查 P2-3 应修：原静默 pass → 西学累积通道坏掉时"西学不涨"被误读为
        # "来源不足（设计）"，与"通道故障"无法区分。现留痕（每回合最多一行）。
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "accrue_west", "西学",
            f"西学来源累积未执行：{type(e).__name__}", log=log, exc=e)
    _settle_tech_research(state, log)

    # ---- T9 物价方案：交子界制销币（Step 3.6 扩展）----
    # 一界 JIAOZI_TERM=36 回合；到界换发新钞，按在发额 JIAOZI_REDEEM_FEE=5% 工墨费销毁
    # （**销币通道**：回收流通货币抑通胀）；超界未换部分作废（退出流通）。
    # 换界销毁记 statistics["jiaozi_redeemed"] + jiaozi.redeemed_total（审计/断言用）。
    _settle_jiaozi_term(state, log)

    # ---- T9 物价方案：私铸熔化真实化（Step 3.8 前）----
    # 民间铜钱逐月真实熔化：各 POP wealth 按 MELT_RATE=0.1%/月扣减退出流通
    # （非一次性 private_melt 系数，真实逐月衰减；private_melt 已 0.2→0.1 用于物价公式）。
    _settlement_steps._settle_coin_melt(state, log)


def _ext_econ_phases(pop, cfg, gy, cmul, price, pay_cfg, dz_hit=False, rtype="",
                     buildings=None, resources=None, state=None, log=None):
    """省域/政权级通用经济相位 A-E（生产→商品市场→粮市→口粮→灾害/阶层流动→税/饷计算）。

    钱粮守恒：商市/粮市/税全部整数精确转移；**不碰 treasury**——税从各阶层
    wealth 扣走、饷需求按 type 费率算出，中央库藏记账由调用侧完成（省域
    共享中央 treasury 串行记账）。阶层流动只走 size 迁移（ΣPOP 守恒），
    灾害逃散记为自然减员（unrest 由调用侧加）。`rtype` 为政权 type（特产/
    消费率表按 type 取）。返回统计 dict（含新粮价）。
    `dz_hit` 为调用侧判定的本月灾害命中（减产系数已折进传入的 gy）。
    `buildings`/`resources` 为批 4 建筑-岗位-就业模型入口（省域 `{type:{lv}}`
    与州/府物资仓）；缺省时回落旧静态产出（简单模拟 38 政权）。
    """
    produced = 0
    eaten = 0
    _staffed = {}
    _wage_stat = {}
    # ---- Phase A 生产：建筑-岗位-就业模型（批 4）优先；无新建筑结构时回落旧静态产出 ----
    _nong = pop.get("农")
    _art = pop.get("工匠")
    _bld = buildings or {}
    _use_jobs = any(isinstance(v, dict) and "lv" in v for v in _bld.values()) if _bld else False
    if _use_jobs:
        from core.building_jobs import (
            allocate_employment, produce_grain_track, produce_job_track)
        _staffed = allocate_employment(pop, _bld, cfg, rtype)
        produced += produce_grain_track(pop, _bld, cfg, gy, rtype, state)
        _goods_pool = _art.setdefault("goods", {}) if isinstance(_art, dict) else {}
        produce_job_track(pop, _bld, cfg, rtype,
                          staffed=_staffed, resources=resources,
                          goods_pool=_goods_pool)
    else:
        # 旧静态产出（简单模拟 38 政权 / 旧档无 lv 结构）
        if isinstance(_nong, dict) and int(_nong.get("size", 0) or 0) > 0:
            _g = int(int(_nong["size"]) * gy)
            _grain_add(_nong, _g, state)
            produced += _g
        if isinstance(_art, dict):
            _ag = _art.setdefault("goods", {})
            _ag["布"] = int(_ag.get("布", 0) or 0) + int(
                int(_art.get("size", 0) or 0) * cfg["goods_yield"])
            # 绸（2026-09-22）：高附加值织物，士绅/官僚消费
            _ag["绸"] = int(_ag.get("绸", 0) or 0) + int(
                int(_art.get("size", 0) or 0) * float(cfg["silk_yield"]))
            # 皮毛/药材（2026-09-22 多商品补维）：按政权 type 特产产出
            _fur_y = float(cfg.get("fur_yield", {}).get(rtype, 0.0))
            if _fur_y > 0:
                _ag["皮毛"] = int(_ag.get("皮毛", 0) or 0) + int(
                    int(_art.get("size", 0) or 0) * _fur_y)
            _herb_y = float(cfg.get("herb_yield", {}).get(rtype, 0.0))
            if _herb_y > 0:
                _ag["药材"] = int(_ag.get("药材", 0) or 0) + int(
                    int(_art.get("size", 0) or 0) * _herb_y)
    # ---- Phase B 商品市场：布/绸/皮毛/药材 按 wealth 比例消费，货出工匠。
    # 旧口径：钱 7/3 分（尾差归商人）。批 4 job 模式：买家付款先进建筑营收，
    # 之后 pay_wages_from_revenue 发薪 + 利润归士绅（§6.1，禁 burn）。----
    _mer = pop.get("商人")
    _fur_rates = cfg.get("fur_consume_rate", {}).get(rtype, {})
    _herb_rates = cfg.get("herb_consume_rate", {}).get(rtype, {})
    _goods_revenue = 0   # job 模式：建筑营收（transient，发薪后归零）
    for kl, slot in pop.items():
        if kl == "工匠" or not isinstance(slot, dict) or not isinstance(_art, dict):
            continue
        _ag = _art.setdefault("goods", {})
        slot.setdefault("goods", {})
        # 布（日用，全阶层）
        _spend = int(int(slot.get("wealth", 0) or 0)
                     * float(cfg["goods_consume_rate"].get(kl, 0.005)))
        _gpool = int(_ag.get("布", 0) or 0)
        if _spend > 0 and _gpool > 0:
            _buy = min(_gpool, int(_spend / float(cfg["goods_price"])))
            if _buy > 0:
                _pay = int(_buy * float(cfg["goods_price"]))
                slot["wealth"] = int(slot.get("wealth", 0) or 0) - _pay
                slot["goods"]["布"] = int(slot["goods"].get("布", 0) or 0) + _buy
                _ag["布"] = int(_ag.get("布", 0) or 0) - _buy
                if _use_jobs:
                    _goods_revenue += _pay   # 营收入池，发薪统一走 §6.1
                else:
                    _art_share = int(_pay * 0.7)
                    _art["wealth"] = int(_art.get("wealth", 0) or 0) + _art_share
                    if isinstance(_mer, dict):
                        _mer["wealth"] = int(_mer.get("wealth", 0) or 0) + (_pay - _art_share)
        # 绸（富阶层；silk_consume_rate）
        _sr = float(cfg.get("silk_consume_rate", {}).get(kl, 0.0))
        _sspend = int(int(slot.get("wealth", 0) or 0) * _sr)
        _spool = int(_ag.get("绸", 0) or 0)
        if _sspend > 0 and _spool > 0:
            _sbuy = min(_spool, int(_sspend / float(cfg["silk_price"])))
            if _sbuy > 0:
                _spay = int(_sbuy * float(cfg["silk_price"]))
                slot["wealth"] = int(slot.get("wealth", 0) or 0) - _spay
                slot["goods"]["绸"] = int(slot["goods"].get("绸", 0) or 0) + _sbuy
                _ag["绸"] = int(_ag.get("绸", 0) or 0) - _sbuy
                if _use_jobs:
                    _goods_revenue += _spay
                else:
                    _sart = int(_spay * 0.7)
                    _art["wealth"] = int(_art.get("wealth", 0) or 0) + _sart
                    if isinstance(_mer, dict):
                        _mer["wealth"] = int(_mer.get("wealth", 0) or 0) + (_spay - _sart)
        # 皮毛（按 type 消费率表；游牧全阶层日用、党项仅富阶层）
        _fr = float(_fur_rates.get(kl, 0.0))
        _fpool = int(_ag.get("皮毛", 0) or 0)
        if _fr > 0 and _fpool > 0:
            _fexp = int(int(slot.get("wealth", 0) or 0) * _fr)
            if _fexp > 0:
                _fbuy = min(_fpool, int(_fexp / float(cfg.get("fur_price", 4.0))))
                if _fbuy > 0:
                    _fpay = int(_fbuy * float(cfg.get("fur_price", 4.0)))
                    slot["wealth"] = int(slot.get("wealth", 0) or 0) - _fpay
                    slot["goods"]["皮毛"] = int(slot["goods"].get("皮毛", 0) or 0) + _fbuy
                    _ag["皮毛"] = int(_ag.get("皮毛", 0) or 0) - _fbuy
                    if _use_jobs:
                        _goods_revenue += _fpay
                    else:
                        _fart = int(_fpay * 0.7)
                        _art["wealth"] = int(_art.get("wealth", 0) or 0) + _fart
                        if isinstance(_mer, dict):
                            _mer["wealth"] = int(_mer.get("wealth", 0) or 0) + (_fpay - _fart)
        # 药材（大理型全阶层小比例自用）
        _hr = float(_herb_rates.get(kl, 0.0))
        _hpool = int(_ag.get("药材", 0) or 0)
        if _hr > 0 and _hpool > 0:
            _hexp = int(int(slot.get("wealth", 0) or 0) * _hr)
            if _hexp > 0:
                _hbuy = min(_hpool, int(_hexp / float(cfg.get("herb_price", 5.0))))
                if _hbuy > 0:
                    _hpay = int(_hbuy * float(cfg.get("herb_price", 5.0)))
                    slot["wealth"] = int(slot.get("wealth", 0) or 0) - _hpay
                    slot["goods"]["药材"] = int(slot["goods"].get("药材", 0) or 0) + _hbuy
                    _ag["药材"] = int(_ag.get("药材", 0) or 0) - _hbuy
                    if _use_jobs:
                        _goods_revenue += _hpay
                    else:
                        _hart = int(_hpay * 0.7)
                        _art["wealth"] = int(_art.get("wealth", 0) or 0) + _hart
                        if isinstance(_mer, dict):
                            _mer["wealth"] = int(_mer.get("wealth", 0) or 0) + (_hpay - _hart)
    # ---- Phase B2 工资发放（批 4 §6.1 · job 模式专属）：建筑营收 → 在岗 POP + 利润归士绅 ----
    _wage_stat = {}
    if _use_jobs:
        from core.building_jobs import pay_wages_from_revenue
        _wage_stat = pay_wages_from_revenue(
            pop, _bld, cfg, _staffed, _goods_revenue, rtype=rtype)
        _profit = int(_wage_stat.get("profit", 0) or 0)
        _gentry = pop.get("士绅")
        if _profit > 0 and isinstance(_gentry, dict):
            _gentry["wealth"] = int(_gentry.get("wealth", 0) or 0) + _profit
    # 工匠余货月折旧（同宋 5%；布/绸/皮毛/药材均折旧）
    if isinstance(_art, dict):
        _ag = _art.setdefault("goods", {})
        for _gd in ("布", "绸", "皮毛", "药材"):
            if _ag.get(_gd):
                _ag[_gd] = int(_ag[_gd] * cfg["goods_decay"])
    # ---- Phase C 粮市撮合（净头寸；卖方分得同一笔实付额，尾差归最大卖/买方）----
    # 🟢 M35-C-2：粮市撮合需求＝**有效人口**×人均（含职业附加；单点口径）
    from core.foundation.ledger.occupation import food_need_of
    need_of = {kl: int(food_need_of(pop, kl) * cmul)
               for kl, v in pop.items() if isinstance(v, dict)}
    sellers = []
    for kl, v in pop.items():
        if not isinstance(v, dict):
            continue
        surplus = max(0, int(v.get("grain", 0) or 0) - need_of.get(kl, 0))
        if kl == "农":
            surplus = max(0, surplus - need_of.get(kl, 0))   # 农保底：留 1 月口粮（同宋 P0-①）
        if surplus > 0:
            sellers.append((kl, surplus))
    buyers = []
    buyer_pool = 0
    price_wen = max(int(price * 1000), 1)
    for kl, v in pop.items():
        if not isinstance(v, dict):
            continue
        short = max(0, need_of.get(kl, 0) - int(v.get("grain", 0) or 0))
        if short <= 0:
            continue
        can_buy = min(short, (max(0, int(v.get("wealth", 0) or 0)) * 1000) // price_wen)
        if can_buy > 0:
            buyers.append((kl, can_buy))
            buyer_pool += can_buy
    famine_units = 0
    sell_total = sum(s for _, s in sellers)
    if sell_total > 0 and buyers:
        trade = min(buyer_pool, sell_total)
        # 卖方分配：按盈余占比（无宋制 FLOOR 抬权——floor 会越权卖出超额存粮）
        _sell_q = {kl: int(trade * s / sell_total) for kl, s in sellers}
        _deficit = trade - sum(_sell_q.values())
        if _deficit and _sell_q:
            _sk = max(_sell_q, key=lambda k: dict(sellers)[k])
            _sell_q[_sk] += _deficit
        # 买方分配：按可购占比，尾差归最大可购方（付得起的兜余款）
        _can = dict(buyers)
        _buy_q = {kl: int(trade * c / buyer_pool) for kl, c in buyers}
        _deficit = trade - sum(_buy_q.values())
        if _deficit and _buy_q:
            _bk = max(_buy_q, key=lambda k: _can[k])
            _buy_q[_bk] += _deficit
        # 落地：买方粮+钱−（实付求和）；卖方粮−、分得**同一笔实付额**（尾差归末位）
        _paid_total = 0
        for kl, q in _buy_q.items():
            if q > 0:
                _grain_add(pop[kl], q, state)
                _c = int(q * price)
                pop[kl]["wealth"] = int(pop[kl].get("wealth", 0) or 0) - _c
                _paid_total += _c
        _items = [(kl, q) for kl, q in _sell_q.items() if q > 0]
        _qtot = sum(q for _, q in _items) or 1
        _left = _paid_total
        for j, (kl, q) in enumerate(_items):
            _grain_set(pop[kl], max(0, (_grain_get(pop[kl]) or 0) - q), state)
            if j == len(_items) - 1:
                _c = _left
            else:
                _c = int(_paid_total * q / _qtot)
                _left -= _c
            pop[kl]["wealth"] = int(pop[kl].get("wealth", 0) or 0) + _c
    # ---- 口粮消费（按职业×type 乘数；不足记饥荒）----
    for kl, v in pop.items():
        if not isinstance(v, dict):
            continue
        need = need_of.get(kl, 0)
        _gr = _grain_get(v) or 0
        if _gr >= need:
            _grain_set(v, _gr - need, state)
            eaten += need
        else:
            eaten += _gr
            famine_units += need - _gr
            _grain_set(v, 0, state)
    # ---- Phase C2 省域随机灾害（2026-09-22，镜像宋 Step 8 天灾相位）----
    # 本月若受灾：产粮已按减产系数打过折（调用侧传入 gy 已折），粮价上浮（粮需比
    # 失衡触发），unrest + 逃散（农 size 小比例流失，ΣPOP 守恒记为自然减员）。
    # 无流民通道（外邦 POP 无 refugees），逃散即该省农 POP 直接减少。
    disaster_loss = 0
    _dz_cfg = cfg.get("disaster", {})
    if dz_hit:
        _flee = int(int(_nong.get("size", 0) or 0) * float(_dz_cfg.get("flee_rate", 0.01)))
        if _flee > 0:
            _nong["size"] = int(_nong.get("size", 0) or 0) - _flee
            disaster_loss = _flee
    # ---- Phase C3 省域阶层自然流动（2026-09-22，镜像宋阶层通道；走 size 迁移，ΣPOP 守恒）----
    # 择优就业：农 wealth 人均低于工匠/商人 人均 wealth 时，部分农转工匠/商人；反之回流。
    # 比例小（rate），月内单方向，保证 size 迁移 Σ 守恒（迁移者 size 原样搬，不增不减）。
    class_migrated = 0
    _cf_cfg = cfg.get("class_flow", {})
    _cf_rate = float(_cf_cfg.get("rate", 0.001))
    _cf_thr = float(_cf_cfg.get("threshold", 0.8))
    if _cf_rate > 0 and isinstance(_art, dict):
        _nong_sz = int(_nong.get("size", 0) or 0) if isinstance(_nong, dict) else 0
        _art_sz = int(_art.get("size", 0) or 0)
        _mer_sz = int(_mer.get("size", 0) or 0) if isinstance(_mer, dict) else 0
        # 人均 wealth 比较：农 vs 工匠（择优就业：农穷而工匠富 → 农转工匠）
        _nong_pc = int(_nong.get("wealth", 0) or 0) / _nong_sz if _nong_sz > 0 else 0.0
        _art_pc = int(_art.get("wealth", 0) or 0) / _art_sz if _art_sz > 0 else 0.0
        _target = max(_art_sz, _mer_sz)   # 流向富的（工匠或商人，取额大者）
        _rich = _art if _art_sz >= _mer_sz else _mer
        _rich_sz = int(_rich.get("size", 0) or 0)
        if _rich_sz > 0:
            _rich_pc = int(_rich.get("wealth", 0) or 0) / _rich_sz
            if _nong_sz > 0 and _nong_pc < _rich_pc * _cf_thr:
                _move = int(_nong_sz * _cf_rate)
                if _move > 0:
                    _nong["size"] = _nong_sz - _move
                    _rich["size"] = _rich_sz + _move
                    class_migrated = _move
    # ---- Phase D 税/饷**计算**（wealth 扣税；饷需求算出，treasury 记账在调用侧）----
    tax_total = 0
    for kl, rate in cfg["tax_rate"].items():
        slot = pop.get(kl)
        if isinstance(slot, dict) and float(rate) > 0:
            _t = int(int(slot.get("wealth", 0) or 0) * float(rate))
            if _t > 0:
                slot["wealth"] = int(slot.get("wealth", 0) or 0) - _t
                tax_total += _t
    _bs = pop.get("兵")
    _os = pop.get("官僚")
    _troops = int(_bs.get("size", 0) or 0) if isinstance(_bs, dict) else 0
    _offs = int(_os.get("size", 0) or 0) if isinstance(_os, dict) else 0
    _need_army = int(_troops * float(pay_cfg["soldier"]))
    _need_off = int(_offs * float(pay_cfg["official"]))
    # ---- Phase F 物价缓动 + 批 7 动态商品价 ----
    # 粮价沿用粮需比 ±5% 缓动；商品价走 update_goods_prices（基准×供需比钳位，月涨跌 ±20%）
    _grain_all = sum(int(v.get("grain", 0) or 0) for v in pop.values() if isinstance(v, dict))
    _need_g = sum(need_of.values())
    if _need_g > 0:
        if _grain_all < _need_g:
            price = min(float(cfg["price_cap"]), price * 1.05)
        elif _grain_all > _need_g * 2:
            price = max(float(cfg["price_floor"]), price * 0.95)
    # 批 7 动态商品价（§8.1）：基准 × clamp(demand/supply, 0.5, 1.5)，月涨跌 ±20%
    _goods_prices = {}
    try:
        from core.domains.economy.dynamic_price import update_goods_prices
        _demand = {}
        _supply = {}
        _produced_g = {}
        for _kl, _slot in pop.items():
            if not isinstance(_slot, dict):
                continue
            for _gd, _qty in ((_slot.get("goods") or {}).items() if isinstance(_slot.get("goods"), dict) else []):
                _supply[_gd] = _supply.get(_gd, 0) + int(_qty or 0)
        if isinstance(_art, dict):
            for _gd, _qty in ((_art.get("goods") or {}).items() if isinstance(_art.get("goods"), dict) else []):
                _produced_g[_gd] = _produced_g.get(_gd, 0) + int(_qty or 0)
        _prev_p = {g: float(cfg.get("GOODS_EXT_PRICES", {}).get(g, 1.0))
                   for g in (cfg.get("GOODS_BASE_PRICE") or {})}
        _goods_prices = update_goods_prices(_prev_p, _demand, _supply, _produced_g, cfg)
    except Exception as e:  # noqa: BLE001
        # 审查 P2-3 应修：原静默 pass → 动态商品价整相位失败（_goods_prices 保持空表，
        # 外邦经济按静态价走）而无人知。**本函数每月被 38 个政权各调一次**，故经
        # `note_settlement_error` 做"每回合最多一行"去重（防刷屏）。
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "ext_goods_prices", "外邦物价",
            f"动态商品价未结算（沿用静态价）：{type(e).__name__}", log=log, exc=e)
    # ---- Phase F8 本色饷 + 官仓平粜（批 6 · §6.5/§6.6 粮=硬通货）----
    _grain_pay = {"soldier": 0, "official": 0, "arrears_grain": 0,
                  "ping_tiao_out": 0, "ping_tiao_in": 0, "grain_tax_in_kind": 0}
    if isinstance(resources, dict):
        # 兼容 `{dim: int}` 与 `{dim: {"stock": n}}` 两种仓格式
        _gr_raw = resources.get("粮", resources.get("grain", 0))
        _gr_is_dict = isinstance(_gr_raw, dict)
        _gr_stock = int(_gr_raw.get("stock", 0) or 0) if _gr_is_dict else int(_gr_raw or 0)

        def _write_grain(n):
            if _gr_is_dict:
                _gr_raw["stock"] = n
            else:
                resources["粮"] = n

        _bs = pop.get("兵")
        _os = pop.get("官僚")
        # ① 本色粮税（从**产出**直接扣，先于市场/口粮）：产粮 × 本色税率 → 官仓
        _g_tax_rate = float(cfg.get("GRAIN_TAX_IN_KIND", 0.10))
        _g_tax = int(produced * _g_tax_rate) if produced > 0 else 0
        if _g_tax > 0:
            # 产出已计入农 POP grain（Phase A / produce_grain_track），此处从产出部分扣
            _nong_g = pop.get("农")
            if isinstance(_nong_g, dict):
                _take = min(_g_tax, int(_nong_g.get("grain", 0) or 0))
                if _take > 0:
                    _grain_set(_nong_g, max(0, (_grain_get(_nong_g) or 0) - _take), state)
                    _gr_stock += _take
                    _grain_pay["grain_tax_in_kind"] = _take
        # ② 本色兵粮/禄米：官仓 → 兵/官僚 POP grain（硬通货发饷）
        _s_rate = float((cfg.get("SOLDIER_GRAIN_RATE") or {}).get(
            rtype, (cfg.get("SOLDIER_GRAIN_RATE") or {}).get("default", 1.2)))
        _o_rate = float((cfg.get("OFFICIAL_GRAIN_RATE") or {}).get(
            rtype, (cfg.get("OFFICIAL_GRAIN_RATE") or {}).get("default", 1.5)))
        _s_need = int(int(_bs.get("size", 0) or 0) * _s_rate) if isinstance(_bs, dict) else 0
        _o_need = int(int(_os.get("size", 0) or 0) * _o_rate) if isinstance(_os, dict) else 0
        _g_need = _s_need + _o_need
        _g_give = min(_g_need, max(0, _gr_stock))
        _g_arrears = _g_need - _g_give
        _s_give = int(_s_need * (_g_give / _g_need)) if _g_need > 0 else 0
        _o_give = _g_give - _s_give
        if isinstance(_bs, dict) and _s_give > 0:
            _grain_add(_bs, _s_give, state)
        if isinstance(_os, dict) and _o_give > 0:
            _grain_add(_os, _o_give, state)
        _grain_pay["soldier"] = _s_give
        _grain_pay["official"] = _o_give
        _grain_pay["arrears_grain"] = _g_arrears
        _gr_stock -= _g_give
        # ③ 官仓平粜（外邦版常平）：价高放粮抑价、价低籴入托市
        _p0 = float(cfg.get("grain_price0", {}).get(rtype, cfg.get("grain_price0", {}).get("default", 1.6)))
        _hi = _p0 * float(cfg.get("PING_TIAO_HIGH", 1.5))
        _lo = _p0 * float(cfg.get("PING_TIAO_LOW", 0.7))
        if price > _hi and _gr_stock > 0:
            _release = int(_gr_stock * float(cfg.get("PING_TIAO_RELEASE_RATIO", 0.20)))
            if _release > 0:
                _gr_stock -= _release
                _nong = pop.get("农")
                if isinstance(_nong, dict):
                    _grain_add(_nong, _release, state)
                _grain_pay["ping_tiao_out"] = _release
        elif price < _lo:
            _nong = pop.get("农")
            if isinstance(_nong, dict):
                _surplus = max(0, int(_nong.get("grain", 0) or 0) - need_of.get("农", 0) * 2)
                _buy = min(_surplus, max(50, int(_gr_stock * 0.1))) if _surplus > 0 else 0
                if _buy > 0:
                    _grain_set(_nong, max(0, (_grain_get(_nong) or 0) - _buy), state)
                    _gr_stock += _buy
                    _grain_pay["ping_tiao_in"] = _buy
        _write_grain(_gr_stock)
    return {"produced": produced, "eaten": eaten, "tax": tax_total,
            "need_army": _need_army, "need_off": _need_off,
            "famine": famine_units, "price": price,
            "disaster_loss": disaster_loss, "class_migrated": class_migrated,
            "staffed": _staffed, "wages": _wage_stat,
            "grain_pay": _grain_pay, "goods_prices": _goods_prices}


def _settle_external_economy(state, log):
    """外邦经济月度结算（2026-09-19 同构循环 → 2026-09-22 省域化）。

    三政权（EXTERNAL_ECONOMY_REGIMES：辽/西夏/大理）：经济拆到**州/府一级**——
    每省独立六类 POP（size 按省人口 × type 份额，权威经济账）+ 省域粮价，
    逐省跑 生产→商品市场→省域粮市→口粮→税/饷；中央 treasury 共享（税汇总入
    藏、饷按省序实付），省域 econ_audit 零残差断言，政权级 econ_audit = Σ省。
    其余 38 政权：维持简单模拟（政权级聚合账单市场，同 2026-09-19 版）。

    守恒（§13.10/§13.11）：外邦账户**不在宋 ACCOUNTS**——宋 M_ALL 对账不受
    影响（岁币仍为 burn）；政权内 ΣPOP wealth + treasury 只因跨境流（岁币入账）
    变化，省域 audit 公式：money_residual == Δ省wealth −(饷入账 − 税)，
    grain_residual == Δ省grain −(产 − 食)，恒 0（回归 test_external_economy.py）。
    旧档缺省域 pops 时按省人口幂等重建（setdefault 语义）。
    """
    from content.data import (EXTERNAL_ECONOMY_REGIMES,
                              EXTERNAL_ECON, _ext_pop_by_heads)
    regimes = getattr(state, "external_regimes", None)
    if not isinstance(regimes, dict):
        return
    for rk in EXTERNAL_ECONOMY_REGIMES:
        ex = regimes.get(rk)
        if not isinstance(ex, dict):
            continue
        cfg = EXTERNAL_ECON
        rtype = str(ex.get("type", ""))
        gy = float(cfg["grain_yield"].get(rtype, cfg["grain_yield"]["default"]))
        cmul = float(cfg["consume_mult"].get(rtype, cfg["consume_mult"]["default"]))
        pay_cfg = cfg["pay"].get(rtype, cfg["pay"]["default"])
        treasury = int(ex.setdefault("treasury", 0) or 0)
        provinces = ex.get("provinces") or []
        provinces = [p for p in provinces if isinstance(p, dict)]
        # ---- 省域路径：任一省带 pops 即省域化（三政权；旧档按省人口重建缺失）----
        _prov_econ = False
        for _p in provinces:
            if not isinstance(_p.get("pops"), dict):
                # 旧档兜底：按该省**精确人口**重建省域 POP（setdefault 幂等）
                _p["pops"] = _ext_pop_by_heads(rtype, int(_p.get("population", 0) or 0))
                _p["pops"].setdefault("兵", {"size": 0, "wealth": 0, "grain": 0})
                _p["pops"]["兵"]["size"] = int(_p.get("troops", 0) or 0)
            _prov_econ = True
        if not provinces:
            _prov_econ = False
        # 省域粮价初值（setdefault 幂等；旧档兜底）
        _p0 = float(cfg["grain_price0"].get(rtype, cfg["grain_price0"]["default"]))
        for _p in provinces:
            _p.setdefault("grain_price", _p0)
        if _prov_econ:
            agg = {"produced": 0, "eaten": 0, "tax": 0, "famine": 0,
                   "paid_army": 0, "paid_off": 0, "arrears": 0,
                   "disaster_loss": 0, "class_migrated": 0,
                   "money_residual": 0, "grain_residual": 0}
            for _p in provinces:
                ppop = _p["pops"]
                pprice = max(float(cfg["price_floor"]),
                             min(float(cfg["price_cap"]),
                                 float(_p.get("grain_price", 0) or 0) or _p0))
                # 省域随机灾害（镜像宋 Step 8）：本月命中则产粮打折（折进 gy）+ 粮价上浮
                _dz = cfg.get("disaster", {})
                _dz_hit = random.random() < float(_dz.get("prob", 0.04))
                _dz_gy = gy
                if _dz_hit:
                    _dz_gy = gy * random.uniform(float(_dz.get("min_yield", 0.5)),
                                                 float(_dz.get("max_yield", 0.8)))
                # 省域审计窗口起点（省 POP wealth/grain；中央 treasury 不在窗口）
                _pm0 = sum(int(v.get("wealth", 0) or 0) for v in ppop.values() if isinstance(v, dict))
                _pg0 = sum(int(v.get("grain", 0) or 0) for v in ppop.values() if isinstance(v, dict))
                st = _ext_econ_phases(ppop, cfg, _dz_gy, cmul, pprice, pay_cfg,
                                      dz_hit=_dz_hit, rtype=rtype,
                                      buildings=_p.get("buildings"),
                                      resources=_p.get("resources"),
                                      state=state, log=log)
                # 灾害 unrest 记账（逃散已在相位内折进 size；unrest 由调用侧加）
                if _dz_hit:
                    ex["unrest"] = min(100, int(ex.get("unrest", 15) or 0) + 1)
                    log.append(f"[外邦经济·{rk}·{_p.get('name')}] ⚠ 省域灾害：产粮打折、粮价上浮、unrest+1")
                # 中央 treasury 串行记账：税入藏 → 饷按省序实付（共享库藏、先省先得）
                treasury += int(st["tax"])
                _need_all = int(st["need_army"]) + int(st["need_off"])
                _scale = 1.0 if _need_all <= 0 else min(1.0, treasury / _need_all)
                _pa = int(st["need_army"] * _scale)
                _po = int(st["need_off"] * _scale)
                treasury -= _pa + _po
                _bs = ppop.get("兵")
                if isinstance(_bs, dict) and _pa > 0:
                    _bs["wealth"] = int(_bs.get("wealth", 0) or 0) + _pa
                _os = ppop.get("官僚")
                if isinstance(_os, dict) and _po > 0:
                    _os["wealth"] = int(_os.get("wealth", 0) or 0) + _po
                _arrears = _need_all - _pa - _po
                if _arrears > 0:
                    ex["unrest"] = min(100, int(ex.get("unrest", 15) or 0) + 1)
                if int(st["famine"]) > 0:
                    ex["unrest"] = min(100, int(ex.get("unrest", 15) or 0) + 1)
                # 省域守恒审计：money_residual == Δ省wealth −(饷 − 税)；grain == Δ−(产−食)
                _pm1 = sum(int(v.get("wealth", 0) or 0) for v in ppop.values() if isinstance(v, dict))
                _pg1 = sum(int(v.get("grain", 0) or 0) for v in ppop.values() if isinstance(v, dict))
                pa = _p.setdefault("econ_audit", {})
                pa["money_residual"] = (_pm1 - _pm0) - (_pa + _po - int(st["tax"]))
                # 粮残差（批 6 · 粮=硬通货）：ΔPOP粮 == 产 − 食 + 本色饷入 + 平粜入POP − 本色税出 − 籴入出POP
                _gp = st.get("grain_pay") or {}
                pa["grain_residual"] = (_pg1 - _pg0) - (
                    int(st["produced"]) - int(st["eaten"])
                    + int(_gp.get("soldier", 0) or 0) + int(_gp.get("official", 0) or 0)
                    + int(_gp.get("ping_tiao_out", 0) or 0)
                    - int(_gp.get("grain_tax_in_kind", 0) or 0)
                    - int(_gp.get("ping_tiao_in", 0) or 0)
                )
                pa.update({"produced": int(st["produced"]), "eaten": int(st["eaten"]),
                           "tax": int(st["tax"]), "paid_army": _pa, "paid_off": _po,
                           "arrears": max(0, _arrears), "famine": int(st["famine"]),
                           "disaster_loss": int(st.get("disaster_loss", 0)),
                           "class_migrated": int(st.get("class_migrated", 0)),
                           "grain_pay": dict(st.get("grain_pay") or {})})
                # ---- Phase G 建筑等级演化 + 就业流动 + 轻量倒闭（批 4 · §3.4/§3.6/§6.3）----
                _blds = _p.get("buildings") or {}
                if any(isinstance(v, dict) and "lv" in v for v in _blds.values()):
                    try:
                        from core.building_jobs import (
                            evolve_building_levels, job_flow_unemployed, apply_bankruptcy)
                        # 🔴 2026-10-06 D 裁定：升级**须付造价**，不得免费增产能。
                        #   `surplus` 由布尔改为**金额**（结余真值，非「是否 >0」）；
                        #   付款主体是**该政权自有中央库藏 `treasury`**，
                        #   **不扣宋的国库、不扣任何 POP 账户**（主要国家按「底层一致」与宋对齐）。
                        _surplus_amt = int(st["tax"]) - _pa - _po
                        _chg = evolve_building_levels(
                            _p, cfg,
                            surplus=_surplus_amt,
                            famine=int(st["famine"]) > 0,
                            arrears=_arrears > 0,
                            idle_streak=_p.get("building_idle_streak"),
                        )
                        if _chg:
                            pa["building_lv_changes"] = _chg
                            # 建造支出从政权库藏实扣（守恒：库藏减、营造方得）
                        # 🔴 2026-10-06 批 B/C 接线：科技推进 + 科技建筑
                        #   （⚠️ 此处曾遗漏接线——模块已存在但无人调用；
                        #    现由 `test_regime_tech_wired_into_settlement` 守住）
                        try:
                            from core.domains.economy.regime_tech import (advance_regime_tech,
                                                        deployable_nodes,
                                                        deploy_regime_building,
                                                        charge_maintenance)
                            _tech_res = advance_regime_tech(ex)
                            if _tech_res and (_tech_res.get("spent")
                                              or _tech_res.get("unlocked")):
                                pa["tech"] = _tech_res
                            _techb = ex.get("tech") or {}
                            if isinstance(_techb, dict):
                                for _nid in deployable_nodes(_techb):
                                    if _nid not in (_techb.get("deployed") or []):
                                        _dep = deploy_regime_building(ex, _nid)
                                        if _dep.get("ok"):
                                            pa.setdefault("tech_buildings", []).append(
                                                {"node": _nid, "name": _dep["name"],
                                                 "cost": _dep["cost"]})
                                _maint = charge_maintenance(ex)
                                if _maint.get("due"):
                                    pa["tech_maintenance"] = _maint
                        except Exception:  # noqa: BLE001 科技不得阻断政权经济结算
                            pass
                            _build_spend = sum(int(c.get("cost", 0) or 0) for c in _chg)
                            if _build_spend:
                                # 🔴 **钱守恒**：建造支出必须**落到政权内的 Σwealth**，
                                #   与宋侧 `pay_wages_from_revenue` 同一口径（营建造价→工匠）。
                                #   只扣不放会凭空销毁钱（实测差 -3225）。
                                _builder = ppop.get("工匠")
                                _paid = 0
                                if isinstance(_builder, dict):
                                    _paid = _build_spend
                                    _builder["wealth"] = int(_builder.get("wealth", 0) or 0) + _paid
                                else:
                                    # ⚠️ 无工匠载体 ⇒ **不得凭空销毁**；退回库藏并记账
                                    _paid = 0
                                    pa["construction_unpaid"] = _build_spend
                                treasury = max(0, treasury - _paid)
                                pa["construction_spend"] = _paid
                        _flow = job_flow_unemployed(
                            ppop, st.get("staffed") or {}, cfg, _blds, rtype=rtype)
                        if any(_flow.values()):
                            pa["job_flow"] = _flow
                        # 轻量倒闭：连续 2 月欠薪 → 裁员+降级；lv=0 且欠薪 → closed
                        _arrears_b = int((st.get("wages") or {}).get("arrears_building", 0) or 0)
                        _bk = apply_bankruptcy(
                            _p, cfg, _arrears_b,
                            staffed=st.get("staffed") or {})
                        if _bk:
                            pa["bankruptcy"] = _bk
                    except Exception as _bje:  # noqa: BLE001
                        log.append(f"[外邦经济·{rk}·{_p.get('name')}] ⚠ 建筑演化失败：{_bje!r}")
                _p["grain_price"] = round(float(st["price"]), 3)
                agg["produced"] += int(st["produced"]); agg["eaten"] += int(st["eaten"])
                agg["tax"] += int(st["tax"]); agg["famine"] += int(st["famine"])
                agg["paid_army"] += _pa; agg["paid_off"] += _po
                agg["arrears"] += max(0, _arrears)
                agg["disaster_loss"] += int(st.get("disaster_loss", 0))
                agg["class_migrated"] += int(st.get("class_migrated", 0))
                agg["money_residual"] += int(pa.get("money_residual", 0))
                agg["grain_residual"] += int(pa.get("grain_residual", 0))
                # 粮=硬通货：省域 grain_pay 汇总到政权级（供粮池闭合断言）
                _agp = agg.setdefault("grain_pay", {
                    "soldier": 0, "official": 0, "arrears_grain": 0,
                    "ping_tiao_out": 0, "ping_tiao_in": 0, "grain_tax_in_kind": 0})
                for _k, _v in (pa.get("grain_pay") or {}).items():
                    _agp[_k] = _agp.get(_k, 0) + int(_v or 0)
                if int(pa.get("money_residual", 0)) != 0 or int(pa.get("grain_residual", 0)) != 0:
                    log.append(f"[外邦经济·{rk}·{_p.get('name')}] ⚠ 省域守恒断裂 "
                               f"money={pa['money_residual']:+d} grain={pa['grain_residual']:+d}")
            ex["treasury"] = treasury
            # 🔴 2026-10-06 用户裁定：「全局都要有，宋不用」——
            #   AI 政权欠饷**自会削减开销**（裁军/减官/加税阶梯）；
            #   宋侧财政处置权在玩家手里，**不做任何自动处置**。
            #   裁减走 `move_pop_people`（ΣPOP 守恒），并须在本函数刷新
            #   `ex["pop"]` 聚合视图**之前**执行，保证政级读数与省域一致。
            try:
                from core.domains.economy.regime_fiscal import apply_fiscal_response
                _fisc = apply_fiscal_response(ex, provinces, int(agg.get("arrears", 0) or 0))
                if _fisc and (_fisc.get("streak", 0) or _fisc.get("cut_army")
                              or _fisc.get("cut_officials") or _fisc.get("surcharge_steps")):
                    agg["fiscal_response"] = _fisc
            except Exception:  # noqa: BLE001 财政处置失败不得阻断政权结算
                pass
            ex["econ_audit"] = agg
            # ex["pop"] 汇总视图刷新（size 由 _simulate_external 对齐；wealth/grain
            # 从省域权威账加和——面板/岁币/审计读 ex["pop"] 始终与省域一致，不双账）
            _aggv = {}
            for _p in provinces:
                for _kl, _v in (_p.get("pops") or {}).items():
                    if not isinstance(_v, dict):
                        continue
                    _slot = _aggv.setdefault(_kl, {"wealth": 0, "grain": 0})
                    _slot["wealth"] += int(_v.get("wealth", 0) or 0)
                    _slot["grain"] += _grain_get(_v) or 0
            _reg_pop = ex.setdefault("pop", {})
            for _kl, _v in _aggv.items():
                _slot = _reg_pop.setdefault(_kl, {"size": 0, "wealth": 0, "grain": 0})
                _slot["wealth"] = _v["wealth"]
                _slot["grain"] = _v["grain"]
            _ppr = max(float(_p.get("grain_price", 0) or 0) for _p in provinces) if provinces else _p0
            log.append(f"[外邦经济·{rk}·省域×{len(provinces)}] 税入{agg['tax']:,} "
                       f"军饷{agg['paid_army']:,} 官俸{agg['paid_off']:,} "
                       f"产粮{agg['produced']:,} 饥荒{agg['famine']:,}石 "
                       f"粮价≤{_ppr:.2f} 库藏{treasury:,}")
            continue
        # ---- 简单模拟路径（38 政权：政权级聚合账单市场，同 2026-09-19 版）----
        pop = ex.get("pop")
        if not isinstance(pop, dict) or not pop:
            continue
        price = float(ex.get("grain_price", 0) or 0) or _p0
        price = max(float(cfg["price_floor"]), min(float(cfg["price_cap"]), price))
        _m0 = sum(int(v.get("wealth", 0) or 0) for v in pop.values() if isinstance(v, dict)) + treasury
        _g0 = sum(int(v.get("grain", 0) or 0) for v in pop.values() if isinstance(v, dict))
        st = _ext_econ_phases(pop, cfg, gy, cmul, price, pay_cfg, dz_hit=False,
                              rtype=rtype, state=state, log=log)
        treasury += int(st["tax"])
        _need_all = int(st["need_army"]) + int(st["need_off"])
        _scale = 1.0 if _need_all <= 0 else min(1.0, treasury / _need_all)
        _pa = int(st["need_army"] * _scale)
        _po = int(st["need_off"] * _scale)
        treasury -= _pa + _po
        _bs = pop.get("兵")
        if isinstance(_bs, dict) and _pa > 0:
            _bs["wealth"] = int(_bs.get("wealth", 0) or 0) + _pa
        _os = pop.get("官僚")
        if isinstance(_os, dict) and _po > 0:
            _os["wealth"] = int(_os.get("wealth", 0) or 0) + _po
        _arrears = _need_all - _pa - _po
        if _arrears > 0:
            ex["unrest"] = min(100, int(ex.get("unrest", 15) or 0) + 1)
        if int(st["famine"]) > 0:
            ex["unrest"] = min(100, int(ex.get("unrest", 15) or 0) + 1)
        _m1 = sum(int(v.get("wealth", 0) or 0) for v in pop.values() if isinstance(v, dict)) + treasury
        _g1 = sum(int(v.get("grain", 0) or 0) for v in pop.values() if isinstance(v, dict))
        ex["treasury"] = treasury
        audit = ex.setdefault("econ_audit", {})
        audit["money_residual"] = _m1 - _m0
        audit["grain_residual"] = (_g1 - _g0) - (int(st["produced"]) - int(st["eaten"]))
        audit.update({"produced": int(st["produced"]), "eaten": int(st["eaten"]),
                      "tax": int(st["tax"]), "paid_army": _pa, "paid_off": _po,
                      "arrears": max(0, _arrears), "famine": int(st["famine"])})
        if audit["money_residual"] != 0 or audit["grain_residual"] != 0:
            log.append(f"[外邦经济·{rk}] ⚠ 守恒断裂 money={audit['money_residual']:+d} "
                       f"grain={audit['grain_residual']:+d}")
        log.append(f"[外邦经济·{rk}] 税入{int(st['tax']):,} 军饷{_pa:,} 官俸{_po:,} "
                   f"产粮{int(st['produced']):,} 饥荒{int(st['famine']):,}石 "
                   f"粮价{float(st['price']):.2f} 库藏{treasury:,}")


def _buyer_pool(p, price):
    """该路缺粮 POP 的可支付财富池（A1/B1 抛粮买方化）。

    买方 = 工匠/商人/官僚/兵 中当月缺粮者；可支付财富 = wealth - 保底线
    （保底线 = 1 个月口粮钱，与税征段 _min_wealth 同口径）。
    返回 ([ (pop_name, 缺口石, 可支付贯) ...], 池总额贯)；无合格买方返回 ([], 0)。
    """
    from content.data import PER_CAPITA_MONTH_GRAIN
    buyers = []
    pool = 0
    for pop_name in ("工匠", "商人", "官僚", "兵"):
        pop = p["pops"][pop_name]
        need = int(pop["size"] * PER_CAPITA_MONTH_GRAIN)
        short = max(0, need - pop.get("grain", 0))
        if short <= 0:
            continue
        floor = int(pop["size"] * PER_CAPITA_MONTH_GRAIN * price)   # 保底线（贯）
        afford = max(0, pop["wealth"] - floor)
        if afford <= 0:
            continue
        buyers.append((pop_name, short, afford))
        pool += afford
    return buyers, pool


def _sell_to_buyers(p, seller, qty, price, copper_share=1.0, state=None):
    """把 qty 石粮卖给该路缺粮 POP 买方池，返回实售石数（A1/B1）。

    实售 = min(qty, 池可购石数)；买方按缺口比例扣 wealth、得粮（钱粮双向守恒）：
      买方 wealth -= share（钱出）、grain += 份额粮（缺口被填补，粮进）；
      卖方士绅 grain -= sold（粮出，调用处扣减）、wealth+窖银 += sold×price（钱进）。
    尾差归末位：买方扣款合计 == cost、买方得粮合计 == sold（无凭空生钱/灭粮）。
    窖银只藏铜钱（用户史实指示 b）：交子有界贬值、不能窖藏——交子部分全额进 wealth，
    仅铜钱部分按 30/70 拆分（copper_share = 铜钱占流通货币比例）。
    池为 0 → 实售 0（囤积维持，不造币）。
    """
    buyers, pool = _buyer_pool(p, price)
    if not buyers:
        return 0
    price_wen = max(int(price * 1000), 1)
    can_buy = (pool * 1000) // price_wen   # pool（贯）按文级单价折算石（×1000 对齐 price_wen，防贯/文量级 bug）
    sold = min(qty, can_buy)
    if sold <= 0:
        return 0
    cost = int(sold * price)
    short_total = sum(b[1] for b in buyers)
    aff_total = sum(b[2] for b in buyers) or 1
    paid = 0
    grain_given = 0
    _n = len(buyers)
    for i, (pop_name, short, aff) in enumerate(buyers):
        # 审查 P2-17 修复：扣款按「可支付力 afford」加权分摊。原按缺口 short 分摊，
        # 缺口大但 wealth 少的买方会被分摊超额款项（wealth 可被扣穿甚至为负）；
        # 粮仍按缺口 short 分配（谁缺得多谁得粮）。
        if i == _n - 1:                     # 尾差归末位：得粮合计 == sold
            share = cost - paid
            grain_share = sold - grain_given
        else:
            share = int(cost * aff / aff_total)
            grain_share = int(sold * short / short_total)
        pop = p["pops"][pop_name]
        # 逐户封顶：绝不扣穿当前 wealth（实收不足部分由卖方按实收记账，钱不进不出）
        share = max(0, min(share, int(pop.get("wealth", 0))))
        # 批 2-1：`wealth` 写入必须先落治所真账；未下沉才回退旧路级写法。
        if _pop_obj_add(state, pop, "wealth", -share) is None:
            pop["wealth"] -= share              # 钱出（未下沉回退）
        _grain_add(pop, grain_share, state)   # 粮进（缺口被填补）
        paid += share
        grain_given += grain_share
    # 用户关键修正：**窖银只囤银**——铜钱/交子（钞）均不入窖，全部进 wealth（流通）；
    # 窖银（白银）由 _settle_civilian_hoard 从市舶 silver 池分配（银硬通货可窖、钞不可窖）
    # 审查 P2-17：卖方按「实收 paid」入账（与买方实扣合计一致，钱粮双向守恒）
    # 批 2-1：卖方入账同样走 POP 桥，保持买卖双方钱账都落真账。
    if _pop_obj_add(state, seller, "wealth", paid) is None:
        seller["wealth"] += paid              # 未下沉回退
    return sold


def _settle_civilian_hoard(state, log):
    """士绅囤粮操作（钱粮守恒）：AI 推演档位优先，无 AI 时按粮价方向兜底。

    囤 = 士绅用 wealth 买粮（wealth↓ grain↑，受资金约束）；抛 = 卖粮得钱（grain↓ wealth↑）。
    士绅囤粮挤压市场流通（见 calc_region_grain_price 的 HOARD_SUPPLY_SQUEEZE）。
    """
    # AI 经济动态推演（settle_turn 已注入 state._economy_ai：{景气,士绅,士绅力度,生产,窖银}）或无
    _eco = getattr(state, "_economy_ai", None) or {}
    _ai_act = _eco.get("士绅", "") if _eco.get("士绅") in ("囤", "抛") else None
    _ai_tier = _eco.get("士绅力度", "中")
    # 窖银只藏铜钱（用户史实指示 b）：铜钱占流通货币比例 = 1 - 交子有效额 / 货币总量
    # （交子有界贬值、不能窖藏；issued=0 时 100% 铜钱，藏富不受影响）
    _jiaozi_eff = state.jiaozi.get("issued", 0) * state._jiaozi_acceptance()
    _pop_money = sum(pop.get("wealth", 0)
                     for _p in state.prefectures.values() for pop in _p.get("pops", {}).values())
    _money_total = _jiaozi_eff + _pop_money + max(0, state.treasury) + max(0, state.imperial_treasury)
    _copper_share = max(0.0, min(1.0, 1.0 - _jiaozi_eff / max(_money_total, 1.0)))
    # 窖银动用档位（A1 定稿·用户史实指示 c）：AI 推演决定每月动用比例，程序换算；
    # 无 AI（本地降级/_economy_ai 缺该键）默认「无」= 冻结不动用（藏富不到最后关头不用）。
    _draw_tier = _eco.get("窖银") if _eco.get("窖银") in HOARD_DRAW_RATE else "小"   # no-AI 被动缓释 0.5%/月（防永久抽水；有 AI 由档位决定）
    _draw_rate = HOARD_DRAW_RATE.get(_draw_tier, 0.0)
    for name, p in state.prefectures.items():
        genty = p["pops"]["士绅"]
        price = p.get("grain_price", state.grain_price)
        # 用户关键修正：**窖银只囤银**——每月从市舶白银池（silver_in，硬通货）按
        # HOARD_COPPER_RATIO_BASE 比例分配入士绅窖银（白银退出流通）；铜钱/交子不可入窖
        try:
            _mar = getattr(state, "maritime", None) or {}
            _silver = int(_mar.get("silver_in", 0)) if isinstance(_mar, dict) else 0
            if _silver > 0 and _mar.get("open"):
                _silver_share = int(_silver * HOARD_COPPER_RATIO_BASE / max(len(state.prefectures), 1))
                if _silver_share > 0:
                    if _pop_obj_add(state, genty, "窖银", _silver_share) is None:
                        genty["窖银"] = genty.get("窖银", 0) + _silver_share
                    _mar["silver_in"] = max(0, _mar["silver_in"] - _silver_share)  # 银入窖退出流通
                    state.statistics["hoard_growth"] = state.statistics.get("hoard_growth", 0) + _silver_share
        except Exception:
            pass
        if _ai_act:
            act, tier = _ai_act, _ai_tier   # AI 推演（全国统一景气下的士绅行为）
        elif not _eco:
            # 阶段 C：接入 Jev 商帮微观决策门面（综合本地粮价、跨路价差与常平仓储备进行博弈）
            from core.ai.merchant_decision import decide_merchant_operation
            m_dec = decide_merchant_operation(state, p)
            if m_dec.action == "hoard":
                act, tier = "囤", m_dec.tier
            elif m_dec.action == "dump":
                act, tier = "抛", m_dec.tier
            else:
                act, tier = "观望", "无"
        else:
            # 兜底：丰收贱买囤积、高价惜售/抛售获利（不再高价囤，与常平粜粮方向一致）
            if price < 0.6:
                act, tier = "囤", "小"
            elif price > 2.2:
                act, tier = "抛", "中"
            elif price > 1.6:
                act, tier = "抛", "微"       # 高价惜售（小幅抛售获利）
            else:
                # 粮价平稳：士绅卖囤粮换钱（买商品/维持现金流），卖 5%/月使囤粮存量稳定
                act, tier = "抛", "中"
        mult = TIER_RANGE.get(tier, 0.5) * 0.05   # 囤/抛比例：微0.0125/小0.025/中0.05/大0.09（不 round）
        # 囤粮上限（A1 定案·软约束）：软上限 = 士绅田产年产 × HOARD_CAP_MULT（0.3），
        # 硬上限 = 软上限 × 1.5。超软上限先售买方池、未售保留（囤积居奇机制保留）；
        # 仅超硬上限强制出清，未售按 3% 损耗核销（防无限囤积）。
        _land = max(float(p.get("land", 1)), 1.0)
        _gentry_land_total = float(p.get("gentry_land", 0)) + float(p.get("hidden_land", 0))
        _soft_cap = int(p.get("grain", 0) * _gentry_land_total / _land * HOARD_CAP_MULT)
        _hard_cap = int(_soft_cap * 1.5)
        if act == "囤":
            buy = int(p.get("grain", 0) / 12.0 * mult)      # 月产 × 档位
            price_wen = max(int(price * 1000), 1)           # 文级单价（与 _sell_to_buyers 同口径）
            # 审查修复（量级错）：wealth 单位为贯、price_wen 为文/石，
            # 原式 wealth // price_wen 少乘 1000 → 可购量被低估千倍，囤粮机制实质失效
            # （例：26 万贯、1 贯/石 时只能买 260 石）。统一为贯→文换算。
            afford = genty["wealth"] * 1000 // price_wen     # 资金能买多少石（文级精度）
            room = max(0, _soft_cap - (_grain_get(genty) or 0))       # 囤粮余量（软上限约束）
            src = max(0, int(p.get("grain", 0) / 12.0))     # 粮源上限：本路在库粮的月产部分
            buy = min(buy, afford, room, src)
            if buy > 0:
                # 审查 P2-16 修复（钱粮双破守恒）：原实现士绅 wealth 减少无对手方、
                # grain 增加无来源，且 `int(...)/1000.0` 使 wealth 变 float。
                # 现改为成对划转：钱 士绅→本路农户 wealth；粮 本路在库粮→士绅囤粮。
                cost = int(buy * price)                     # 贯（整数）
                farmers = (p.get("pops") or {}).get("农")
                if isinstance(farmers, dict):
                    if _pop_obj_add(state, genty, "wealth", -cost) is None:
                        genty["wealth"] -= cost
                    if _pop_obj_add(state, farmers, "wealth", cost) is None:
                        farmers["wealth"] = farmers.get("wealth", 0) + cost
                # 无农户接收方时不划钱（宁可不流转，也不凭空灭币）
                _grain_add(genty, buy, state)
                p["grain"] = max(0, int(p.get("grain", 0)) - buy)
        elif act == "抛":
            sell = int((_grain_get(genty) or 0) * mult)
            if sell > 0:
                # B1：抛粮买方化——卖给该路缺粮 POP 可支付财富池，不卖给虚空；
                # 未售部分继续囤（囤积维持，不造币）。窖银只藏铜钱（copper_share）。
                sold = _sell_to_buyers(p, genty, sell, price, _copper_share, state)
                if sold > 0:
                    _grain_add(genty, -sold, state)
        # 超软上限：先售买方池，未售保留（不压回、不核销）——囤积居奇机制保留
        if (_grain_get(genty) or 0) > _soft_cap:
            sold = _sell_to_buyers(p, genty, (_grain_get(genty) or 0) - _soft_cap, price, _copper_share, state)
            if sold > 0:
                _grain_add(genty, -sold, state)
        # 仅超硬上限：强制出清，未售按损耗核销（不凭空变钱；粮压回硬上限，防无限囤积）
        if (_grain_get(genty) or 0) > _hard_cap:
            _excess = (_grain_get(genty) or 0) - _hard_cap
            sold = _sell_to_buyers(p, genty, _excess, price, _copper_share, state)
            _grain_set(genty, _hard_cap, state)
            _unsold = _excess - sold
            if _unsold > 0:
                # 未售部分**全部**按损耗核销（雀鼠耗/霉变）：`genty["grain"]` 已被压回
                # `_hard_cap`，即 `_unsold` 石**全部消失**。
                # 审查 O4：原统计只记 `int(_unsold * HOARD_SPOIL_RATE)`（3%），
                # 与实际销毁额差 ~33 倍 → 「囤粮损耗」面板读数严重低估。
                # 现记**实销额**；HOARD_SPOIL_RATE 仍用于分层口径（损耗/压回）留痕。
                state.granary_stats["hoard_spoil"] = (
                    state.granary_stats.get("hoard_spoil", 0) + _unsold)
                state.granary_stats["hoard_spoil_3pct"] = (
                    state.granary_stats.get("hoard_spoil_3pct", 0)
                    + int(_unsold * HOARD_SPOIL_RATE))
        # 窖银动用（A1 定稿·用户史实指示 c）：按 AI 档位换算的每月动用比例取窖银出窖，
        # 流向工匠/商人（挥霍/购地/市舶投资等服务消费），死钱转活钱、不积累 wealth；
        # 无 AI 时 _draw_rate = 0（冻结，不到最后关头不用）。
        _draw = int(genty.get("窖银", 0) * _draw_rate)
        if _draw > 0:
            if _pop_obj_add(state, genty, "窖银", -_draw) is None:
                genty["窖银"] = genty.get("窖银", 0) - _draw
            _half = int(_draw * 0.5)
            _art = p["pops"]["工匠"]
            _mer = p["pops"]["商人"]
            if _pop_obj_add(state, _art, "wealth", _half) is None:
                _art["wealth"] += _half
            if _pop_obj_add(state, _mer, "wealth", _half) is None:
                _mer["wealth"] += _half


def _input_scale(got_dims: dict, got_grain: float, recipe: dict) -> float:
    """实得料 ÷ 应需料（0~1）——欠产同比例缩放，杜绝「少拿料却满产」。

    无投入（纯产能型工坊）⇒ 返回 1.0（不缩放）。任一必需维实得为 0 ⇒ 0（停产）。
    """
    need_tot = 0.0
    got_tot = 0.0
    for dim, need in (recipe or {}).items():
        if dim in ("grain_feed", "ration_weight"):
            continue
        n = float(need or 0)
        if n > 0:
            need_tot += n
            got_tot += float(got_dims.get(dim, 0.0) or 0.0)
    gf = float((recipe or {}).get("grain_feed", 0) or 0)
    if gf > 0:
        need_tot += gf
        got_tot += float(got_grain or 0.0)
    if need_tot <= 0:
        return 1.0
    return max(0.0, min(1.0, got_tot / need_tot))


def _pool_dims_any(got_dims: dict, got_grain: float, pool_dims, ws: dict) -> bool:
    """缺料时是否仍产出可交易/可折钱成品：任一实得投入 > 0 即继续（按比例减产）。

    全额缺料（所有实得皆 0）⇒ 返回 False ⇒ `continue` 停产。
    """
    if float(got_grain or 0.0) > 0:
        return True
    for v in (got_dims or {}).values():
        if float(v or 0.0) > 0:
            return True
    return False


def _settle_workshops(state, log):
    """作坊月度推进：配方消耗 inputs（如粮→酒），产出 outputs 入 resources/内帑。"""
    _wine_bonus = 0     # 本月酒课**加成**汇总；下方据此**重算** wine_tax（不做月度累加，见 A-5）
    # 2026-10-11（B1）：成品维（布/绸）产出另计入工匠 goods 池（待售位）。
    # 依 `building_jobs.produce_job_track`「原料维 → resources；成品维 → goods_pool」。
    # ⚠️ `wine` 也是成品维，但走**酒课入内帑**（既有口径，`wine_tax`），
    # 不进工匠池——池子只放**民间可买的布/绸**。
    _finished_goods: dict = {}
    # 🟢 M47：**产出地点并轨** —— 可按作坊所属路归属的成品另记一路，
    #   分派时落**该路**（§14.1「产出先入本地经营库存」）；判不出路的作坊
    #   仍走原「全局按工匠 size 占比」分派（**不销毁产出、不臆造地点**）。
    _finished_by_route: dict = {}
    _unattributed_dims: dict = {}
    from content.data_constants import (FINISHED_DIMS as _FIN_DIMS,
                                      FINISHED_TAX_DIMS as _FIN_TAX_DIMS)
    # 工匠货栈（可交易）= 成品维 − 即产即销折钱入内帑的维（wine 酒课 / meat 按人口征收）。
    # ⚠️ 2026-10-04：`meat` 已登记进 `FINISHED_DIMS`，但它**不可交易** ——
    # 若沿用旧的「排除 wine」写法，`meat` 会自动进池，改变「畜栏产肉折钱入内帑」的业务语义。
    _POOL_DIMS = tuple(d for d in _FIN_DIMS if d not in _FIN_TAX_DIMS)
    # 🔴 **L1′ 同源争抢仲裁**（2026-10-04）：此前按 `state.workshops` 字典序逐坊「先到先得」——
    # 绢坊/绫罗坊/紬坊共读同一味「丝」时，谁先跑谁拿满，后跑的全额缺料停产，
    # **产出结构随字典/注册顺序漂移**（不可预期，且换注册顺序就换结果）。
    # 现改为**两阶段配给**：①先收集全路在营工坊对每个原料维的需求；
    # ②按**显式权重**分配当月可用量，不足时**同比例欠产**（而非随机全停）。
    # 权重来源：`recipe` 的可选 `ration_weight`（缺省 1.0）——未声明即等权，不臆造偏好。
    _demands: Dict[str, List[Tuple[str, float, float]]] = {}   # dim -> [(wid, need, weight)]
    _grain_demands: List[Tuple[str, float, float]] = []        # (wid, need, weight)
    _order: List[str] = []                                    # 稳定的工坊顺序（按 wid 排序）
    for wid in sorted(state.workshops.keys()):
        ws = state.workshops.get(wid) or {}
        if not ws.get("active"):
            continue
        _order.append(wid)
        recipe = ws.get("recipe") or {}
        # 用 get 而非 pop：recipe 是存档持久 dict，pop 会销毁 grain_feed 键，
        # 导致次月起作坊不再耗粮、白嫖产出。
        w = float(recipe.get("ration_weight", 1.0) or 1.0)
        if w <= 0:
            w = 1.0
        gf = float(recipe.get("grain_feed", 0) or 0)
        if gf > 0:
            _grain_demands.append((wid, gf, w))
        for dim, need in recipe.items():
            if dim == "grain_feed" or dim == "ration_weight":
                continue
            n = float(need or 0)
            if n > 0:
                _demands.setdefault(dim, []).append((wid, n, w))
    # 配给表：dim -> {wid: 实发量}。Σ实发 ≤ 可用量，差额为未领余量（不凭空造料）。
    _alloc: Dict[str, Dict[str, float]] = {}
    for dim, wants in _demands.items():
        avail = float((state.resources.get(dim) or {}).get("stock", 0) or 0)
        tw = sum(x[2] for x in wants)
        got: Dict[str, float] = {}
        if avail > 0 and tw > 0:
            for wid, need, w in wants:
                got[wid] = min(need, avail * w / tw)
        _alloc[dim] = got
    _grain_alloc: Dict[str, float] = {}
    if _grain_demands:
        gavail = float(state.granary)
        gtw = sum(x[2] for x in _grain_demands)
        for wid, need, w in _grain_demands:
            _grain_alloc[wid] = min(need, gavail * w / gtw) if (gavail > 0 and gtw > 0) else 0.0
    # 按**欠产比例**缩放产出：拿到 60% 料就只产 60%，不允许「少拿料却满产」。
    for dim, wants in _demands.items():
        for wid, need, _w in wants:
            got = _alloc[dim].get(wid, 0.0)
            if got > 0:
                _slot = state.resources.setdefault(dim, {"stock": 0, "cap": 0})
                _cur_s = int(_slot.get("stock", 0) or 0)
                _take = min(_cur_s, int(round(got)))
                # 🟢 M64a（**先桥**步）：作坊可定路（键内路名）⇒ 先问资源存量桥；
                #   未接管（None）⇒ 保留原写法 ⇒ 今日零行为变化。
                from core.foundation.ledger import resource_stock_bridge as _rsb
                from core.domains.economy.seat_goods_readout import route_of_workshop as _row_of
                _wroute = _row_of(state, wid)
                _rsb_ret = (_rsb.stock_take(state, dim, int(round(got)), route=_wroute)
                            if _wroute else None)
                if _rsb_ret is None:
                    _slot["stock"] = max(0, _cur_s - int(round(got)))
                # 🟢 M42a：逐维流量登记（作坊投料**出账**；只记实际扣减量）
                if _take > 0:
                    from core.domains.economy import stock_flow as _sf
                    _sf.record_out(state, dim, _take, reason="workshop_feed")
    for wid, g in _grain_alloc.items():
        if g > 0:
            state.change_granary(-int(round(g)))
            state.granary_stats["workshop_feed"] = (
                state.granary_stats.get("workshop_feed", 0) + int(round(g)))
    for wid in _order:
        ws = state.workshops.get(wid) or {}
        recipe = ws.get("recipe") or {}
        # 本坊实际拿到的各维量（粮另计）
        got_dims = {d: _alloc.get(d, {}).get(wid, 0.0) for d in _demands}
        got_grain = _grain_alloc.get(wid, 0.0)
        lack = []
        for dim, need in recipe.items():
            if dim in ("grain_feed", "ration_weight"):
                continue
            if got_dims.get(dim, 0.0) < float(need or 0) - 1e-9:
                lack.append(dim)
        if recipe.get("grain_feed", 0) and got_grain < float(recipe.get("grain_feed", 0) or 0) - 1e-9:
            lack.append("太仓粮")
        if lack:
            log.append(f"[作坊] {ws.get('name','作坊')} 缺料减产/停产（缺：{','.join(lack)}）")
            if not _pool_dims_any(got_dims, got_grain, _POOL_DIMS, ws):
                continue
        # 产出按**实得料占比**缩放（欠产同比例），杜绝「少拿料满产」。
        _scale = _input_scale(got_dims, got_grain, recipe)
        out_dim = ws.get("output_dim")
        # 欠产同比例缩放：拿到 60% 料只产 60%（L1′ 核心约束）
        yld = float(ws.get("yield", 0)) * _scale
        if out_dim == "wine":
            # 酒坊产能 → 酒课**加成**（汇入下方重算，**不在此累加**）
            # 审查 A-5 修复（2026-09-18 阶段 B-1 实测：内帑 +2.91M/月、民间 −2.28M/月、
            # 残差 +0.93M/月 的主要来源）：`state.wine_tax` 是**月度收入率**
            # （见 game_state_econ.py:520 与下方财政步 `_wine_tax_cash = int(wine_coin)`），
            # 原实现在此 `+=` 每月再加一次常量 → 60 个月把月率抬高约 60 倍，
            # 使财政步每月从工匠/商人 wealth **超额扣缴**进内帑，是"钱荒"的直接推手。
            # 现改为按月**重算**：酒课 = 保底 WINE_COIN_BASE ＋ Σ各酒坊产能加成。
            _wine_bonus += int(yld * MATERIAL_PRICE_BASE.get("wine", 0) * 0.1)
        # U0001f534 2026-10-08 用户裁定：肉是**商品**，不再「按人口摊派折钱」。
        #   原分支用 `_collect_from_pops` 向六类 POP 等比例扣钱，无对应买方（等价于税），
        #   且与 `goods` 成品通道双记账。现与「绢/布/纸/糖」同路：落 `resources` + 工匠 `goods` 池，
        #   由民间成交付钱。排除下方 `elif out_dim in RESOURCE_DIMS` 保留分支。

        elif out_dim in RESOURCE_DIMS:
            # 审查防御：同上（缺槽即 KeyError）；且 cap<=0 时原式 min(0, …) 会把
            # 全部产出抹成 0（静默丢料），故仅在 cap>0 时封顶。
            # 🟢 M64b（**先桥**步）：作坊可定路（键内路名）⇒ 先问资源存量桥。
            #   桥接管 ⇒ 写治所真账、**无全国 cap** ⇒ 实际入账 = round(yld)；
            #   未接管（`None`）⇒ **保留原写法**（今日零行为变化）。
            _bridge_added = None
            try:
                from core.domains.economy.seat_goods_readout import route_of_workshop as _row_s
                _wroute_s = _row_s(state, wid)
            except Exception:                                   # noqa: BLE001
                _wroute_s = None
            if _wroute_s:
                from core.foundation.ledger import resource_stock_bridge as _rsb_out
                _q_yld = int(round(yld))
                if _rsb_out.stock_add(state, out_dim, _q_yld, route=_wroute_s) is not None:
                    _bridge_added = _q_yld
            if _bridge_added is None:
                _slot = state.resources.setdefault(out_dim, {"stock": 0, "cap": 0})
                _cap = int(_slot.get("cap", 0) or 0)
                _before_s = int(_slot.get("stock", 0) or 0)
                _new = _before_s + yld
                # 审查 O6：`yld` 是 float，cap<=0 时旧式直接赋值 → `resources[dim]["stock"]`
                # **变成 float**（落档 `_safe_int` 会再截一次，读数面板类型不稳）。
                # 现归一为 int（round 而非截断，避免 0.5 进位丢失）。
                _slot["stock"] = min(_cap, int(round(_new))) if _cap > 0 else int(round(_new))
                _added_s = int(_slot["stock"]) - _before_s
            else:
                _added_s = int(_bridge_added)
            if _added_s > 0:
                from core.domains.economy import stock_flow as _sf
                _sf.record_in(state, out_dim, _added_s, reason="workshop_output")
            # 2026-10-11（规格 market-civilian-economy B1）：**成品维（布/绸）另入工匠 goods 池**。
            # 口径依 `building_jobs.produce_job_track`（:327-331）「原料维 → resources；
            # 成品维 → goods_pool，单一产出通道原则」——宋侧此前只写 resources，
            # 导致 B1 消费端改真成交后**没有可售成品**（民间买到 0）。
            # 两处是**同一批货的两个用途槽**（`storage` 仓储读数 / `resale` 待售），
            # 不是两批货：B1-3 台账须标明，**不得相加当"总产量"**。
            if out_dim in _POOL_DIMS:
                # 🟢 M47：能归属到作坊所属路 ⇒ 记到**该路**（产出先入本地经营库存）；
                #   判不出路 ⇒ 仍走原全局分派（**不销毁产出**），并计入 `workshop_unattributed`
                from core.domains.economy.seat_goods_readout import route_of_workshop as _row_route
                _q_pool = int(round(yld))
                _wroute = _row_route(state, wid)
                if _wroute:
                    _rb = _finished_by_route.setdefault(_wroute, {})
                    _rb[out_dim] = int(_rb.get(out_dim, 0) or 0) + _q_pool
                else:
                    _fg = _finished_goods.setdefault(out_dim, 0)
                    _finished_goods[out_dim] = _fg + _q_pool
                    _unattributed_dims[out_dim] = int(_unattributed_dims.get(out_dim, 0) or 0) + _q_pool
    # 酒课按月**重算**（保底 ＋ Σ酒坊产能加成）——杜绝"月度率被逐月累加"（A-5）
    from content.data import WINE_COIN_BASE
    state.wine_tax = int(WINE_COIN_BASE) + int(_wine_bonus)

    # ---- M47（2026-10-13）**产出地点并轨** ----
    # ① 可按作坊所属路归属的成品 ⇒ 落**本路治所真账**（按该路人口权重拆、尾差归最大权重治所，
    #    Σ 精确不丢量）。这是 §14.1「产出先入本地经营库存」的最小落地。
    # ② 判不出路 / 该路无治所权重 ⇒ 退回下方**原「全局按工匠 size 占比」分派**（不销毁产出）。
    if _finished_goods or _finished_by_route:
        _stats = getattr(state, "statistics", None)
        if isinstance(_stats, dict):
            _stats["workshop_finished_goods"] = (
                sum(int(v or 0) for v in _finished_goods.values())
                + sum(int(q or 0) for _m in _finished_by_route.values() for q in _m.values()))
            if _unattributed_dims:
                _stats["workshop_unattributed"] = sum(int(v or 0)
                                                      for v in _unattributed_dims.values())
    for _wr, _wn in (_finished_by_route or {}).items():
        _pd = (getattr(state, "prefectures", None) or {}).get(_wr)
        from core.foundation.ledger.pop_bridge import seat_pop_weights as _spw
        _w = _spw(_wr) if isinstance(_pd, dict) else []
        if not isinstance(_pd, dict) or not _w:
            for _d, _q in _wn.items():                     # 路不存在/无权重 ⇒ 退回全局分派
                _finished_goods[_d] = int(_finished_goods.get(_d, 0) or 0) + int(_q or 0)
            continue
        _tw = sum(x for _s, x in _w)
        _anchor = max(_w, key=lambda kv: kv[1])[0]
        for _d, _q in _wn.items():
            _q = int(_q or 0)
            if _q <= 0:
                continue
            _parts = {_s: int(round(_q * x / _tw)) for _s, x in _w}
            _parts[_anchor] += _q - sum(_parts.values())   # 尾差归最大权重治所 ⇒ Σ 精确
            for _sid, _pq in _parts.items():
                if _pq <= 0:
                    continue
                from core.foundation.ledger import pop_bridge as _pb
                _put = _pb.pop_goods_add(_pd, "工匠", _d, _pq, seat_id=_sid)
                if _put is not None:
                    from core.domains.economy import stock_flow as _sf
                    _sf.record_in(state, _d, _pq, reason="workshop_pool",
                                  custody=_sf.CUSTODY_POP)
                else:
                    _finished_goods[_d] = int(_finished_goods.get(_d, 0) or 0) + _pq

    # ---- 2026-10-11（B1）：**判不出路**的成品退回全局分派（待售位）----
    # 原口径：作坊产出是全局记账 ⇒ 按各路**工匠 size 占比**分派；整数尾差归末路。
    # M47 后此路只服务"地点不可归属"的残余（正常应为 0，`statistics['workshop_unattributed']` 可见）。
    if _finished_goods:
        _rows = []
        for r, p in (getattr(state, "prefectures", None) or {}).items():
            if not isinstance(p, dict):
                continue
            a = (p.get("pops") or {}).get("工匠")
            if isinstance(a, dict):
                _rows.append((r, a, max(0, int(a.get("size", 0) or 0))))
        _sum_sz = sum(sz for _, _, sz in _rows)
        if _sum_sz <= 0 or not _rows:
            return
        _assigned = {dim: 0 for dim in _finished_goods}
        for _i, (_r, a, sz) in enumerate(_rows):
            g = a.setdefault("goods", {})
            _pd = (getattr(state, "prefectures", None) or {}).get(_r)
            for dim, q in _finished_goods.items():
                # 末路取余数（q − 已分派），其余按占比
                got = (int(q) - _assigned[dim]) if _i == len(_rows) - 1 \
                    else int(int(q) * sz / float(_sum_sz))
                got = max(0, got)
                _assigned[dim] += got
                # 🟢 M42h（M45 已修后可落地）：分派落**治所真账**
                _put = None
                if isinstance(_pd, dict) and got > 0:
                    from core.foundation.ledger import pop_bridge as _pb
                    _put = _pb.pop_goods_add(_pd, "工匠", dim, got)
                    if _put is not None:
                        from core.domains.economy import stock_flow as _sf
                        _sf.record_in(state, dim, got, reason="workshop_pool",
                                      custody=_sf.CUSTODY_POP)
                if _put is None:
                    g[dim] = int(g.get(dim, 0) or 0) + got


