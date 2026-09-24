# -*- coding: utf-8 -*-
"""宋祚 · 诏令执行与长期政务（从 settlement_steps.py 拆出，零行为变更）。

含 `_settle_decrees` / `_apply_decree_effect` / `_settle_longterm_decrees`。"""
from __future__ import annotations

import random

from content.data import (
    CHANGPING_HIGH,
    CHANGPING_LOW,
    COMMERCE_TAX_RATE_MIN,
    COMMERCE_TAX_RATE_MAX,
    TIER_RANGE,
)

# 官制 × POP 的受控流动入口（官额/吏额/在岗/待阙/祠禄；禁止直接改 pops["官僚"]["size"]）
from core import officialdom as _officialdom

from core.settlement_common import (
    _state_grain_trade,
    _levy_men,
)

# ------------------------------------------------------------
# Step 1: 诏令执行
# ------------------------------------------------------------

def _settle_decrees(state, log):
    """执行本月诏令（12 步 agent 化 P2+：诏令执行契约接线）"""
    # 月初重置：御笔直发额度恢复；狼来了计数仍按既有衰减规则
    state.direct_decree_used = 0

    if state.wolf_count > 0:
        if random.random() < 0.1:
            state.wolf_count = max(0, state.wolf_count - 1)

    # 12 步 agent 化 P2+：读取诏令执行 AI 契约
    _decree_ai = getattr(state, "_decree_execute_ai", None)
    ai_tasks = []
    if isinstance(_decree_ai, dict) and not _decree_ai.get("_error"):
        ai_tasks = _decree_ai.get("tasks", [])
        if _decree_ai.get("narrative"):
            log.append(f"[诏令执行] {_decree_ai['narrative']}")

    executed = 0
    failed = 0
    longterm_this_turn = []

    # 吏治把持度对本轮所有诏令的执行折扣（§16.4；只读派生，见 core/clerks.py）
    try:
        from core.clerks import decree_execution_mult as _dem
        _grip_mult = _dem(state)
    except Exception:  # noqa: BLE001 — 吏制不可用时不得阻断诏令结算
        _grip_mult = 1.0
    if _grip_mult < 0.98:
        log.append(f"[吏治] 吏胥把持，政令执行率 ×{_grip_mult:.2f}")

    active_ids = {d.get("id") for d in state.active_decrees if d.get("id")}

    remaining = []
    for decree in state.pending_decrees[:]:
        # 局势意图（规范 §5.2）：诏令可选携带 `situation_intent`；无则该诏行为不变。
        # 此处**只登记**（运行时态，不落档），校验与消费由 Step 8.5 局势结算负责——
        # 校验依据是**本回合 state_applier 事务记录**，不得由最终 state 反推。
        _si = decree.get("situation_intent")
        if isinstance(_si, dict):
            _sits = getattr(state, "_situation_intents_this_turn", None)
            if not isinstance(_sits, list):
                _sits = []
                state._situation_intents_this_turn = _sits
            _sits.append(dict(_si))
        # AI 契约加成：若有对应机构的高优先级任务，提升执行率
        org_hint = decree.get("org_hint", "政府")
        ai_boost = 0.0
        for task in ai_tasks:
            if task.get("org") == org_hint and task.get("priority") == "高":
                ai_boost = 0.15  # 高优先级任务 +15% 执行率
                break
            elif task.get("org") == org_hint and task.get("priority") == "中":
                ai_boost = 0.08
                break

        rate = state.calc_decree_execution_rate(
            decree.get("faction_stances", {}),
            is_secret=decree.get("is_secret", False),
            is_direct=decree.get("is_direct", False),
            secret_loyalty=decree.get("secret_loyalty", 0.5),
            is_zhongzhi=decree.get("is_zhongzhi", False),
            org_hint=org_hint,
        )
        # §16.4 吏强官弱：实际执行率 = 官效率 × (1 − 把持度 × w)
        # 官三年一任、回避本籍；吏世代本地、掌握簿书 → 政令必须经吏才能落地。
        # 这是给审计 J-2「叙事说办了、数值没动」一个有原因、可诊断、可治理的载体：
        # 回执仍是"已施行"，但效果打折，而原因可在面板查到吏治状态。
        rate = rate * _grip_mult
        rate = min(0.95, rate + ai_boost)  # 封顶 95%

        if random.random() < rate:
            _apply_decree_effect(state, decree, log)
            executed += 1
        else:
            log.append(f"[诏令] 「{decree['title']}」执行受阻，部分落实")
            failed += 1

        did = decree.get("id")
        if decree.get("duration", 0) > 0:
            if did:
                if did not in active_ids:
                    longterm_this_turn.append(decree)
                    active_ids.add(did)
            else:
                if decree not in state.active_decrees and decree not in longterm_this_turn:
                    longterm_this_turn.append(decree)
        else:
            remaining.append(decree)

    state.active_decrees = longterm_this_turn
    state.pending_decrees = remaining

    for decree in state.pending_secret_decrees[:]:
        rate = state.calc_decree_execution_rate(
            decree.get("faction_stances", {}),
            is_secret=True,
            secret_loyalty=decree.get("secret_loyalty", 0.6),
            is_zhongzhi=decree.get("is_zhongzhi", False),
            org_hint=decree.get("org_hint", "政府"),
        )
        rate = rate * _grip_mult          # 密旨亦须经吏手，同受把持度折扣
        if random.random() < rate:
            _apply_decree_effect(state, decree, log)
            log.append(f"[密旨] 「{decree.get('title','密令')}」暗中推行")
            executed += 1
        else:
            if random.random() < 0.2:
                log.append(f"[密旨泄露] 「{decree.get('title','密令')}」被台谏察觉！")
                state.change_prestige(-3, "密旨泄露")
        state.pending_secret_decrees.remove(decree)

    if executed > 0:
        log.append(f"[本月] 诏令执行 {executed} 项，{failed} 项受阻")


def _apply_decree_effect(state, decree, log):
    """应用诏令效果"""
    effects = decree.get("effects", {})
    if "prestige" in effects:
        state.change_prestige(effects["prestige"], decree.get("title", ""))
    if "treasury" in effects:
        _dt = int(effects["treasury"])
        if _dt > 0:
            got = state.drain_pop_wealth("商人", int(_dt * 0.7)) + \
                  state.drain_pop_wealth("农", _dt - int(_dt * 0.7))
            if got < _dt:
                log.append(f"[诏令·守恒] 国库增收应 {_dt}，民间可征仅 {got}，按实入账")
            state.change_treasury(got)
        elif _dt < 0:
            need = abs(_dt)
            paid = 0
            for _road in state.prefectures:
                if paid >= need:
                    break
                paid += state.transfer_money("treasury", f"pop:{_road}:官僚", need - paid)
            if paid < need:
                state.change_treasury(-(need - paid))
    if "imperial_treasury" in effects:
        _it = int(effects["imperial_treasury"])
        if _it > 0:
            got = state.drain_pop_wealth("商人", _it)
            state.change_imperial_treasury(got if got > 0 else 0)
            if got < _it:
                log.append(f"[诏令·守恒] 内帑增收应 {_it}，实征 {got}")
        elif _it < 0:
            state.change_imperial_treasury(_it)
    if "population_satisfaction" in effects:
        state.population_satisfaction = max(0, min(100,
            state.population_satisfaction + effects["population_satisfaction"]))
    for ext_key, ek in (("external_jin", "金"), ("external_liao", "辽"), ("external_xixia", "西夏")):
        if ext_key in effects and ek in state.external:
            state.external[ek]["attitude"] = max(0, min(100,
                state.external[ek]["attitude"] + effects[ext_key]))
    if "defense_bonus" in effects:
        for line in state.defense_lines.values():
            line["fortification"] = max(0, min(100,
                line["fortification"] + effects["defense_bonus"]))
    if "faction_change" in effects and isinstance(effects["faction_change"], dict):
        for fn, d in effects["faction_change"].items():
            if fn in state.factions:
                state.factions[fn]["satisfaction"] = max(0, min(100,
                    state.factions[fn]["satisfaction"] + d))

    if "single_whip" in effects:
        state.single_whip = bool(effects["single_whip"])
        log.append(f"[改制] {'行一条鞭法，田赋改征折银' if state.single_whip else '复本色，田赋仍征粮'}")
    if "pay_reform" in effects:
        mode = effects["pay_reform"]
        if mode in ("本色折色", "仅发钱", "一体发钞", "仅本色"):
            state.pay_system["mode"] = mode
            if mode == "仅发钱":
                state.pay_system["grain_ratio"], state.pay_system["cash_ratio"] = 0.0, 1.0
            elif mode == "一体发钞":
                state.pay_system["grain_ratio"], state.pay_system["cash_ratio"] = 0.0, 1.0
            elif mode == "仅本色":
                state.pay_system["grain_ratio"], state.pay_system["cash_ratio"] = 1.0, 0.0
            else:
                state.pay_system["grain_ratio"], state.pay_system["cash_ratio"] = 0.5, 0.5
            log.append(f"[改制] 俸禄制度改为「{mode}」")
    if "commerce_tax" in effects:
        target = round(max(COMMERCE_TAX_RATE_MIN, min(COMMERCE_TAX_RATE_MAX, float(effects["commerce_tax"]))), 2)
        state.commerce_tax_rate = target
        if target >= 0.30:
            state.population_satisfaction = max(0, state.population_satisfaction - 4)
            log.append("[改制] 工商重榷，商旅怨声载道，民情愤懑")
        elif target <= 0.10:
            state.population_satisfaction = min(100, state.population_satisfaction + 3)
        log.append(f"[改制] 工商征率定为 {target:.0%}（{'重榷聚财' if target >= 0.3 else ('薄征惠商' if target <= 0.1 else '常征')}）")
    if "curtail_waste" in effects or "reduce_office" in effects:
        kind = "reduce_office" if "reduce_office" in effects else "curtail_waste"
        target = max(50_000, min(150_000, int(float(effects.get("curtail_waste") or effects.get("reduce_office") or 0)) or 100_000))
        state.waste_reform = {
            "active": True, "kind": kind, "savings": 0,
            "target": target, "months_left": random.randint(12, 18), "progress": 0,
        }
        state.change_prestige(-2, "省浮费/裁冗员阻力")
        # 政策 → POP：裁汰冗员裁减官僚 POP 人数（裁 5%，钱粮随之减少，体现三冗之减）
        # 裁冗**先从冗处裁**：优先祠禄 → 待阙 → 在岗（见 core/officialdom.remove_officials）。
        # 返乡去向：裁下的官重回士绅（ΣPOP 守恒，§13.5 出口轴）。
        if kind == "reduce_office":
            for _p in state.prefectures.values():
                _guan = _p["pops"]["官僚"]
                _cut = _officialdom.remove_officials(_p, int(_guan["size"] * 0.05))
                _p["pops"]["士绅"]["size"] += _cut
        log.append(f"[变法] 诏{ '裁汰冗员' if kind=='reduce_office' else '省浮费' }，期以{state.waste_reform['months_left']}月渐省浮费，然官僚梗阻、怨声渐起")
    # 粮量单位约定：decree effect 中的粮额（he_mi/military_supply/relief/grain_stabilize/granary_reform）
    # 语义为「万石」，转到后台「石」需 ×10000；日志仍按设计语义显示「万石」。
    if "granary_reform" in effects:
        add = int(effects["granary_reform"]) * 10000
        state.change_granary_cap(add)
        log.append(f"[仓储] 修葺仓廪，太仓增容 {int(effects['granary_reform'])*10000}石")
    if "canal_dredge" in effects:
        state.canal_block = max(0, state.canal_block - int(effects["canal_dredge"]))
        log.append(f"[漕运] 疏浚运河，漕路阻塞减 {effects['canal_dredge']}")
    if "anti_corruption" in effects:
        for org_key in ("户部",):
            o = state.central_orgs.get(org_key)
            if o and o.get("lead") and o["lead"] in state.corruption:
                state.corruption[o["lead"]] = max(0.0,
                    state.corruption[o["lead"]] - float(effects["anti_corruption"]))
        log.append("[肃贪] 诏令严饬，理财之臣稍敛，截留侵盗略减")
    if "relief" in effects:
        relief = min(int(effects["relief"]) * 10000, state.granary)
        state.change_granary(-relief)
        state.granary_stats["relief"] += relief
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + 3))
        log.append(f"[赈济] 开太仓发粟 {int(effects['relief'])*10000}石，饥民得食")
    if "he_mi" in effects:
        amount = int(effects["he_mi"]) * 10000   # 万石 → 石
        cost = int(amount * state.grain_price)   # 石 × (贯/石) = 贯
        if state.treasury >= cost:
            # 审查 P0：和籴为政府向民间买粮——国库出钱、民间售粮（钱粮均守恒）
            _amt, _cost = _state_grain_trade(state, amount, "buy", state.grain_price,
                                             log, "和籴")
            if _amt > 0:
                log.append(f"[和籴] 丰处和籴粟 {_amt}石入太仓，散钱 {_cost}贯与民")
    if "land_survey" in effects:
        state.land["hidden_rate"] = max(0.0, state.land["hidden_rate"] - float(effects["land_survey"]))
        # 政策 → 田亩归属/POP：清丈隐田转正 + 抑兼并退田 + 士绅吐粮（钱粮守恒）
        # 效果优先用结算前注入的 _survey_ai 槽位；无则本地档位兜底（禁止结算路径同步 HTTP）
        from content.data import TIER_RANGE
        _hidden_mult = TIER_RANGE.get("小", 0.5) * 0.10   # 兜底：清隐田 5%
        _gentry_mult = TIER_RANGE.get("小", 0.5) * 0.10   # 兜底：退地主田 5%
        _res = getattr(state, "_survey_ai", None)
        if isinstance(_res, dict) and not _res.get("_error"):
            _hidden_mult = TIER_RANGE.get(_res.get("hidden_cleared"), 0.5) * 0.10
            _gentry_mult = TIER_RANGE.get(_res.get("gentry_returned"), 0.5) * 0.10
        for _p in state.prefectures.values():
            # 清丈隐田：隐田转正为在册田（士绅隐漏被查出）
            _hidden_reduce = int(_p.get("hidden_land", 0) * _hidden_mult)
            _p["hidden_land"] = max(0, _p.get("hidden_land", 0) - _hidden_reduce)
            _p["land"] = _p.get("land", 0) + _hidden_reduce
            # 抑兼并退田：地主田 → 自耕农田（士绅退田给自耕农）
            _gentry_reduce = int(_p.get("gentry_land", 0) * _gentry_mult)
            _p["gentry_land"] = max(0, _p.get("gentry_land", 0) - _gentry_reduce)
            _p["self_farm_land"] = _p.get("self_farm_land", 0) + _gentry_reduce
            # 士绅囤粮吐出给农 POP（清丈打击囤积）
            _genty = _p["pops"]["士绅"]
            _release = int(_genty["grain"] * _hidden_mult)
            _genty["grain"] -= _release
            _p["pops"]["农"]["grain"] += _release
            # 抄没士绅窖银（清丈/抑兼并时抄家，窖银掏出回国库）
            _confiscate = int(_genty.get("窖银", 0) * _hidden_mult)
            _genty["窖银"] = _genty.get("窖银", 0) - _confiscate
            state.treasury += _confiscate
        for fn in ("旧党", "中立派"):
            if fn in state.factions:
                state.factions[fn]["satisfaction"] = max(0,
                    state.factions[fn]["satisfaction"] - 5)
        log.append("[方田均税] 清丈隐田转正、抑兼并退田，士绅囤粮吐还，隐漏稍抑，豪强怨望")
    if "military_supply" in effects:
        amount = int(effects["military_supply"]) * 10000
        cost = int(amount * state.grain_price)
        if state.treasury >= cost:
            # 审查 P0：入中粮草 = 政府购粮——国库出钱、民间售粮（钱粮均守恒）
            _amt, _cost = _state_grain_trade(state, amount, "buy", state.grain_price,
                                             log, "军需")
            if _amt > 0:
                log.append(f"[军需] 入中粮草 {_amt}石，军储稍实")
    if "settle_refugees" in effects:
        total_wasteland = sum(p.get("wasteland", state.land.get("wasteland", 0)) for p in state.prefectures.values()) \
            if any("wasteland" in p for p in state.prefectures.values()) else state.land.get("wasteland", 0)
        target = int(effects["settle_refugees"])
        local_total = sum(p.get("refugees", 0) for p in state.prefectures.values())
        placed = 0
        if local_total > 0:
            for name, p in state.prefectures.items():
                share = int(target * p.get("refugees", 0) / local_total)
                if share <= 0:
                    continue
                avail = min(share, p.get("refugees", 0))
                p["refugees"] = max(0, p["refugees"] - avail)
                p["pops"]["农"]["size"] += avail                  # 流民安置回农 POP（人口回流）
                wl = p.get("wasteland")
                if wl is not None:
                    reclaim = avail * 2  # 每流民垦 2 亩
                    p["wasteland"] = max(0, wl - reclaim)
                    p["cultivated"] = p.get("cultivated", 0) + reclaim
                placed += avail
        else:
            used = min(target * 2, state.land.get("wasteland", 0))  # 人数×2 转亩
            state.land["wasteland"] = max(0, state.land.get("wasteland", 0) - used)
            state.land["cultivated"] += used
            placed = used // 2
        log.append(f"[安民] 安置流民垦荒 {placed * 2}亩，各路流民渐归")
    if "grain_stabilize" in effects:
        if state.grain_price > CHANGPING_HIGH:
            want = int(effects["grain_stabilize"]) * 10000
            # 审查 P0：平粜 = 政府卖粮收钱（民间付钱得粮），钱粮守恒
            _amt, _cost = _state_grain_trade(state, min(want, state.granary), "sell",
                                             state.grain_price, log, "平准")
            if _amt > 0:
                log.append(f"[平准] 粜粮 {_amt}石以抑米价，回收 {_cost}贯")
        elif state.grain_price < CHANGPING_LOW:
            want = int(effects["grain_stabilize"]) * 10000
            budget = int(state.treasury // max(state.grain_price, 0.4))
            # 审查 P0：平籴 = 政府买粮托市（民间售粮得钱），钱粮守恒
            _amt, _cost = _state_grain_trade(state, min(want, budget), "buy",
                                             state.grain_price, log, "平准")
            if _amt > 0:
                log.append(f"[平准] 籴粮 {_amt}石以托米价")

    # 文档第八节白名单所列、此前在 _apply_decree_effect 中缺失的键：补齐以免 AI 拟诏被静默丢弃
    if "army_strength" in effects:
        # 全军员额增益：按各军现有兵力比例分摊（整训/整编）
        # 审查修复：u.troops 为只读 property（真账=Σbranches），须经 add_troops 落分支
        # —— 这一点原已修；但增兵**无人口来源**（此前不计来源直接加人），而本步之后
        # _settle_finance 会以 Σbranches 重聚合兵 POP、并把 ΣPOP 写回 population
        # → 诏令一句即凭空产生数万「人」（最多可为每军 +50% 员额）。
        # 现改为自本路农户／流民成对征补（_levy_men），不足则少增，不造人。
        bonus = int(effects["army_strength"])
        total_troops = sum(u.troops for u in state.army_units) or 1
        _want = max(0, bonus)
        _recruited = 0
        for u in state.army_units:
            if _want <= 0:
                break
            _ask = (min(int(u.troops * 1.5), u.troops + int(bonus * u.troops / total_troops))
                    - u.troops)
            if _ask <= 0:
                continue
            _got = _levy_men(state, u.station, min(_ask, _want))
            if _got > 0:
                u.add_troops(_got)
                _recruited += _got
                _want -= _got
        if _recruited > 0:
            log.append(f"[整军] 诏令整训，自民户征补 {_recruited} 人，诸军战力益壮")
        elif state.army_units:
            log.append("[整军] 诏令整训，然民户无余丁可征，员额未增")
    if "factions_prestige" in effects:
        delta = int(effects["factions_prestige"])
        for fn, f in state.factions.items():
            f["satisfaction"] = max(0, min(100, f["satisfaction"] + delta))
        log.append(f"[朝堂] 诏抚百官，诸派系人心{'稍附' if delta >= 0 else '离散'}（{delta:+d}）")
    if "art_mastery" in effects:
        state.art_mastery = max(0, min(100, state.art_mastery + int(effects["art_mastery"])))
        log.append(f"[文华] 陛下艺事精进（+{int(effects['art_mastery'])}）")


def _settle_longterm_decrees(state, log):
    """按月推进所有长期政务（公开事务 + 密令），满进度核销。"""
    presets = state.difficulty_presets.get(state.difficulty, {})
    growth = presets.get("external_growth", 1.0)

    def _progress(queue, label):
        for task in list(queue):
            months = max(1, int(task.get("task", {}).get("months", task.get("months", 18)) if isinstance(task.get("task"), dict) else task.get("months", 18)))
            rate = (100 / months) * (0.8 + 0.4 * growth)
            task["progress"] = min(100, task.get("progress", 0) + rate)
            if random.random() < 0.5:
                task["last_log"] = f"诸司奉行，事有进境（进度 {int(task['progress'])}%）。"
            # 记忆知识库（Phase 3a）：任务推进写入图谱（progresses）
            try:
                tname = task.get("task_name", "政务")
                state.memory.add_entity(f"task_{tname}", "task", tname, turn=state.turn)
                state.memory.add_relation(f"task_{tname}", f"progress_{int(task['progress'])}",
                                          "progresses", weight=1.0, turn=state.turn,
                                          note=f"{label}进度{int(task['progress'])}%")
            except Exception:
                pass
            if task["progress"] >= 100:
                queue.remove(task)
                log.append(f"[{label}] {task.get('task_name', '政务')} 告成，钦此。")

    _progress(getattr(state, "longterm_public", []), "公开事务")
    _progress(getattr(state, "longterm_secret", []), "密令")
    # free_effect 长期制度（言枢密 v3 契约）：「长期诏」步位旁月度结算
    from core.free_effect import _settle_free_effects  # 延迟导入，避免顶层环
    _settle_free_effects(state, log)


