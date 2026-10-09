# -*- coding: utf-8 -*-
"""宋祚 · 诏令执行与长期政务（从 settlement_steps.py 拆出，零行为变更）。

含 `_settle_decrees` / `_apply_decree_effect` / `_settle_longterm_decrees`。"""
from __future__ import annotations

import logging
import math
import random

_log = logging.getLogger("settlement_decree")

from content.data import (
    CHANGPING_HIGH,
    CHANGPING_LOW,
    COMMERCE_TAX_RATE_MIN,
    COMMERCE_TAX_RATE_MAX,
)

# 官制 × POP 的受控流动入口（官额/吏额/在岗/待阙/祠禄；禁止直接改 pops["官僚"]["size"]）
from core.domains.administration import officialdom as _officialdom

# 🔴 方案乙 / G-3（2026-10-04 POP 实体下沉州府级）：POP 写入走桥接层。
# 粮走 `grain_bridge`（写只落一个载体）；size/窖银走 `pop_bridge`（先落州府真账再刷派生镜像）。
# 未下沉时桥接返回 None，调用方回落原写法。
from core.foundation.ledger.grain_bridge import grain_add as _grain_add
from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add
from core.settlement_common import (
    _state_grain_trade,
    _levy_men,
)

# ------------------------------------------------------------
# Step 1: 诏令执行
# ------------------------------------------------------------


def _ensure_decree_id(state, decree: dict) -> str:
    """为旨意补 `decree_id`——**转发 `core/decree_confirm.ensure_decree_id`（口径单点）**。

    背景（2026-11 实测缺陷）：`commands_decree` 的四条下旨路径从不写
    `decree_id`/`id` ⇒ B5-5 分支 `if _did:` 恒假、**密令泄露推演从未执行**，
    `_secret_contacts` 恒返回 `[]`，去重集合恒空。
    实现归 `decree_confirm`（它是幂等锚的所有者），此处只做**薄转发**，
    避免两个口径分叉。缺失或模块不可用时返回 `""`（**不编造 id**）。
    """
    try:
        from core.decree_confirm import ensure_decree_id
        return ensure_decree_id(state, decree)
    except Exception:                # noqa: BLE001 — 模块不可用不阻断结算
        return str((decree or {}).get("decree_id") or "").strip()


def _secret_contacts(state, decree):
    """本月该密令的**接触途径**（B5-5 接线用；全部由既有读数派生，不新增名单）。

    途径口径：
    - 承办者＝`knowledge_of` 里的授权人（他们**必然**接触到）；
    - 本月有`朝议` 记忆者＝同场廷议者（真同场，不是"在朝就算"）；
    - `decree["抄送"]` 列名者＝公文抄送；
    - 承办者在野且 `state.oversight` 高 → 被监听（已听见＝事实，非概率）。

    读数缺失一律**如实返回空**并让下游判`undefined`，**不按"无人接触"结案**。
    """
    out = []
    did = decree.get("decree_id")
    if not did:
        return out
    try:
        from core.decree_confidential import knowledge_of
        from core.domains.administration.minister_agent import recall
        auth = (knowledge_of(state, did) or {}).get("authorized") or []
    except Exception:                # noqa: BLE001 — 读数不可用 ⇒ 接触面不可判定
        return out
    for aid in auth:
        out.append({"actor_id": aid, "channel": "奏对", "freq": 1})
        try:
            if recall(state, aid, kind="朝议"):
                out.append({"actor_id": aid, "channel": "廷议", "freq": 1})
        except Exception:            # noqa: BLE001
            pass
    for aid in (decree.get("抄送") or []):
        out.append({"actor_id": aid, "channel": "公文抄送", "freq": 1})
    return out

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

    # ---- 效果口径**单点**（用户 2026-10-01 定稿 (a)）----
    # 一次性诏令此前**从不**调用 `core.decree_effect.decree_effect_mult`（探针实测调用次数 = 0），
    # 只用 `clerks.decree_execution_mult`（吏治腿），导致：
    #   ① 口径单点被破——民心/识字率弱关联与军队督行加成对一次性诏令**完全缺失**；
    #   ② 读数缺失时**回落 1.0** ＝「吏治完美」（注释与实现相反）。
    # 现改为：逐道诏令调用单点 `decree_effect_mult(...)`（含 `enforce_troops` 调兵强制施行），
    # `None`（读数未定义）时**挂起该诏令并标明原因**，**不回落 1.0、不用默认值假装执行**，
    # 待数据可用后再由后续回合结算。
    from core.decree_effect import decree_effect_mult as _eff_mult
    _undefined_suspended = 0

    def _resolve_effect_mult(d: dict, org: str) -> "tuple[float | None, str]":
        """→ (效果系数, 挂起原因)。`None` = 读数未定义（须挂起，不得回落 1.0）。"""
        try:
            m = _eff_mult(
                state,
                org_hint=org,
                text=str(d.get("title") or ""),
                enforce_troops=bool(d.get("enforce_troops", False)),
            )
        except Exception as e:  # noqa: BLE001 — 读数缺失不得阻断结算，也不得假装有值
            log.warning("[诏令] 效果系数读取失败（挂起本诏令，不按 1.0 假装执行）: %s", e,
                        exc_info=True)
            return None, f"读数异常（{type(e).__name__}）"
        if m is None:
            return None, "吏治读数未定义"
        return float(m), ""

    # B5-4：去重集合改用**统一 `decree_id`**。原`{d.get("id")}` 恒为空集
    # （全仓从不写 `id`），该守卫实际从未生效。
    active_ids = {str(d.get("decree_id") or "").strip()
                  for d in (getattr(state, "active_decrees", None) or [])
                  if isinstance(d, dict) and str(d.get("decree_id") or "").strip()}

    remaining = []
    for decree in state.pending_decrees[:]:
        # B5-4/B5-5：先补确定性 `decree_id`（幂等与知情范围的锚）。
        # 原实现全仓从不写该键⇒ B5-5 分支恒假、泄露推演从未执行。
        _ensure_decree_id(state, decree)
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
        # **效果系数走单点**（吏治强关联 × 民心/识字弱关联，调兵强制施行再补缺口）。
        _eff_mult_v, _why_undef = _resolve_effect_mult(decree, org_hint)
        if _eff_mult_v is None:
            # 读数未定义 → **挂起**：本月不执行、不生效，退回待办，待数据可用后再结算。
            # 不回落 1.0、不用默认值假装执行（硬约束 #3）。
            remaining.append(decree)
            _undefined_suspended += 1
            log.append(f"[诏令] 「{decree.get('title', '（无题）')}」**挂起**："
                       f"效果系数未定义（{_why_undef}），本月不执行，待读数可用后另行结算。")
            continue
        if _eff_mult_v < 0.98:
            log.append(f"[吏治] 「{decree.get('title', '（无题）')}」执行率 ×{_eff_mult_v:.2f}"
                       f"（吏治折扣 × 民心/识字弱关联"
                       f"{'，已调兵强制施行' if decree.get('enforce_troops') else ''}）")
        rate = rate * _eff_mult_v
        rate = min(0.95, rate + ai_boost)  # 封顶 95%

        if random.random() < rate:
            _apply_decree_effect(state, decree, log)
            executed += 1
            _ok = True
        else:
            log.append(f"[诏令] 「{decree['title']}」执行受阻，部分落实")
            failed += 1
            _ok = False
        # 长期事务关联诏（P1-1）：把**本次结算结果**回写到事务支持与因果留痕。
        # 执行受阻 → 支持增量为 0（"颁旨 ≠ 成功"），见 core/longterm_task.apply_decree_to_task。
        if decree.get("task_id"):
            from core.longterm_task import apply_decree_to_task
            apply_decree_to_task(state, decree, _ok, log, rate=rate)

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
        # B5-5：密令必须有 `decree_id` 才能界定知情范围并推演泄露。
        # 原实现全仓从不写该键 ⇒ 下方 `if _did:` 恒假、泄露推演从未执行过。
        _ensure_decree_id(state, decree)
        rate = state.calc_decree_execution_rate(
            decree.get("faction_stances", {}),
            is_secret=True,
            secret_loyalty=decree.get("secret_loyalty", 0.6),
            is_zhongzhi=decree.get("is_zhongzhi", False),
            org_hint=decree.get("org_hint", "政府"),
        )
        # 密旨亦走同一效果单点；读数未定义同样**挂起**（不回落 1.0 假装执行）
        _eff_s, _why_s = _resolve_effect_mult(decree, decree.get("org_hint", "政府"))
        if _eff_s is None:
            state.pending_secret_decrees.remove(decree)
            state.pending_secret_decrees.append(decree)   # 退回待办，次月再议
            _undefined_suspended += 1
            log.append(f"[密旨] 「{decree.get('title', '密令')}」**挂起**："
                       f"效果系数未定义（{_why_s}），本月不执行。")
            continue
        rate = rate * _eff_s
        if random.random() < rate:
            _apply_decree_effect(state, decree, log)
            log.append(f"[密旨] 「{decree.get('title','密令')}」暗中推行")
            executed += 1
            _sok = True
        else:
            # B5-5（2026-11 接线）：密令泄露改由**真实知情范围/传递路径**推演，
            # 替代原 `random.random() < 0.2` 固定概率。
            # 读数未定义（知情范围不可判定）时**不按"无人泄"结案**，显式记未决。
            _did = decree.get("decree_id")
            _leaked = _detected = False
            if _did:
                try:
                    from core.decree_confidential import simulate_leak
                    _lk = simulate_leak(state, _did,
                                        contacts=_secret_contacts(state, decree),
                                        turn=state.turn)
                    _detected = bool(_lk.get("detected"))
                    _leaked = bool(_lk.get("leaked"))
                    if _detected:
                        log.append(f"[密旨泄露] 「{decree.get('title','密令')}」"
                                   f"被{'、'.join(_lk.get('detected_by') or [])}察觉！")
                        state.change_prestige(-3, "密旨泄露")
                    elif _leaked:
                        _c = (_lk.get("chain") or [{}])[0]
                        log.append(f"[密旨走漏] 「{decree.get('title','密令')}」"
                                   f"经{_c.get('channel','?')}传至{_c.get('witness','?')}，"
                                   f"{'并闻其文' if _c.get('carried') == 'body' else '只闻其声'}")
                    elif _lk.get("outcome") in ("undefined", "undefined_partial"):
                        log.append("[密旨] 知情范围读数未定义，泄露与否**未决**"
                                   "（不按『无人泄』结案）")
                except Exception as _lke:     # noqa: BLE001 — 推演失败不阻断密旨结算
                    log.append(f"[密旨][WARN] 泄露推演不可用：{type(_lke).__name__}")
            _sok = False
        if decree.get("task_id"):
            from core.longterm_task import apply_decree_to_task
            apply_decree_to_task(state, decree, _sok, log, rate=rate)
        state.pending_secret_decrees.remove(decree)

    if executed > 0:
        log.append(f"[本月] 诏令执行 {executed} 项，{failed} 项受阻")
    if _undefined_suspended > 0:
        # 可诊断读数（缺失≠静默）：本月因"效果系数未定义"而挂起的诏令数
        state.statistics["decree_effect_undefined"] = \
            int(state.statistics.get("decree_effect_undefined", 0) or 0) + _undefined_suspended
        log.append(f"[诏令] 本月 {_undefined_suspended} 道诏令因效果系数未定义而**挂起**"
                   f"（未执行、未生效；待读数可用后另行结算）")


def _apply_decree_effect(state, decree, log):
    """应用诏令效果

    审查 M4（**结算侧兜底**）：AI 侧已丢弃非有限值，但诏令也可能来自存档/其它写入方。
    此处对每个效果键做 `int()`/`float()` 前先剔非有限值 —— 旧实现直接
    `int(effects["treasury"])`，遇 NaN 抛 ValueError、遇 Inf 抛 OverflowError，
    **整月结算被打断**；`commerce_tax` 的 min/max 钳位遇 NaN 会返回下界（=最高税）。
    """
    _raw = decree.get("effects", {})
    effects = {}
    if isinstance(_raw, dict):
        for _k, _v in _raw.items():
            if isinstance(_v, bool):
                continue
            try:
                if not math.isfinite(float(_v)):
                    log.append(f"[诏令·守恒] 效果 {_k} 为非有限值，已丢弃（缺失≠0，不猜值）")
                    continue
            except (TypeError, ValueError):
                log.append(f"[诏令·守恒] 效果 {_k} 非数值，已丢弃：{_v!r}")
                continue
            effects[_k] = _v
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
        # 裁冗**先从冗处裁**：优先祠禄 → 待阙 → 在岗（见 core/domains/administration/officialdom.remove_officials）。
        # 返乡去向：裁下的官重回士绅（ΣPOP 守恒，§13.5 出口轴）。
        if kind == "reduce_office":
            for _p in state.prefectures.values():
                _guan = _p["pops"]["官僚"]
                _cut = _officialdom.remove_officials(_p, int(_guan["size"] * 0.05))
                _sh = _p["pops"]["士绅"]
                if _pop_obj_add(state, _sh, "size", _cut) is None:
                    _sh["size"] += _cut
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
        # 审查 S5：日志原记**请求额**（`int(effects['relief'])*10000`），与实际发放额
        # （`relief`，受太仓存量 `min()` 钳位）不符 → 太仓空时面板仍报"发粟 N 石"，
        # 玩家无法解释"仓里明明没粮却记了赈济"。改为如实记实发额，缺口另注。
        _asked = int(effects["relief"]) * 10000
        if relief < _asked:
            log.append(f"[赈济] 请发 {_asked}石，太仓仅存 {int(state.granary) + relief}石，"
                       f"实发 {relief}石，饥民得食")
        else:
            log.append(f"[赈济] 开太仓发粟 {relief}石，饥民得食")
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
            _release = int(_genty.get("grain", 0) * _hidden_mult)
            _ng = _p["pops"]["农"]
            if _grain_add(_genty, -_release, state) is None:
                _genty["grain"] -= _release
            if _grain_add(_ng, _release, state) is None:
                _ng["grain"] += _release
            # 抄没士绅窖银（清丈/抑兼并时抄家，窖银掏出回国库）
            _confiscate = int(_genty.get("窖银", 0) * _hidden_mult)
            if _pop_obj_add(state, _genty, "窖银", -_confiscate) is None:
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
                _rf = p["pops"]["农"]                          # 流民安置回农 POP（人口回流）
                if _pop_obj_add(state, _rf, "size", avail) is None:
                    _rf["size"] += avail
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
    """按月推进所有长期政务（公开事务 + 密令）。

    P1-1（审查整改，2026-09-27）：进度**不再**由「月数 × 难度」固定增长，改由
    `core.longterm_task.monthly_advance` 按
    **支持方 / 阻力方 × 执行能力（吏治强关联、民心·识字率弱关联、军队加成）** 推进；
    告成与罢废（连续 `STALL_MONTHS_FAIL` 月无实质推进）都有可解释原因与日志。
    旧存档缺字段由 `normalize_tasks` 幂等补齐，坏条目隔离而不拒档；
    单件结算异常按件隔离并**显式上报**，不伪报推进、不中断整月结算。
    """
    from core.longterm_task import normalize_tasks, monthly_advance

    nm = normalize_tasks(state, log)
    if nm["migrated"] or nm["isolated"]:
        log.append(f"[事务] 旧档迁移：补齐字段 {nm['migrated']} 件、隔离坏条目 {nm['isolated']} 件。")

    for is_secret, label in ((False, "公开事务"), (True, "密令")):
        queue = getattr(state, "longterm_secret" if is_secret else "longterm_public", None)
        if not isinstance(queue, list):
            continue
        keep = []
        for i, task in enumerate(list(queue)):
            name = str(task.get("task_name") or task.get("title") or "政务")
            try:
                res = monthly_advance(state, task, log, is_secret=is_secret, index=i)
            except Exception as e:  # noqa: BLE001 — 单件异常按件隔离，但必须可见、不得伪报
                _log.warning("[事务] 结算异常已隔离（%s / %s）：%s", label, name, e,
                             exc_info=True)
                task["last_change"] = (f"结算异常（已隔离）：{type(e).__name__}"
                                       f"——本月未推进，详见服务端日志")
                task["readout"] = None
                log.append(f"[{label}] {name} 本月结算异常（已隔离，未伪报推进）。")
                keep.append(task)
                continue
            if res["status"] == "ongoing":
                keep.append(task)
                _record_task_memory(state, task, label)
                continue
            if res["status"] == "unsupported":
                # 规格任务 4：满进度但**未绑定程序侧落点** → 待支持（不宣告成、不改数值）。
                # 计入可诊断读数，供面板逐条展示"哪些旨意议毕却无从落地"。
                state.statistics["task_unsupported"] = \
                    int(state.statistics.get("task_unsupported", 0) or 0) + 1
                _ul = state.statistics.setdefault("task_unsupported_list", [])
                if isinstance(_ul, list) and len(_ul) < 20:
                    _ul.append({"name": name, "turn": getattr(state, "turn", 0),
                                "reason": res.get("reason", "")})
                log.append(f"[{label}] {name}：议毕但**未绑定程序侧落点 → 待支持**"
                           f"（不计为告成，未改任何数值）。")
                try:
                    state.memory.add_entity(f"task_{name}", "task", name, turn=state.turn)
                    state.memory.add_relation(f"task_{name}", "unsupported", "待支持",
                                              weight=1.0, turn=state.turn,
                                              note=(f"{label}待支持（无程序侧落点）"
                                                    f"（{task.get('last_change', '')}）"))
                except Exception as e:  # noqa: BLE001
                    _log.debug("[事务] 记忆图谱写入失败（%s）：%s", name, e)
                continue          # 移出在办队列（政治轨道已议毕），但不写"completed"
            done = res["status"] == "done"
            log.append(f"[{label}] {name}{'告成，钦此。' if done else '受阻罢废，销案。'}")
            try:
                state.memory.add_entity(f"task_{name}", "task", name, turn=state.turn)
                state.memory.add_relation(f"task_{name}", "completed" if done else "aborted",
                                          "完成" if done else "中止", weight=1.0,
                                          turn=state.turn,
                                          note=(f"{label}{'告成' if done else '罢废'}"
                                                f"（{task.get('last_change', '')}）"))
            except Exception as e:  # noqa: BLE001 — 记忆图谱为可选旁路，失败不阻断结算
                _log.debug("[事务] 记忆图谱写入失败（%s）：%s", name, e)
        queue[:] = keep
    # free_effect 长期制度（言枢密 v3 契约）：「长期诏」步位旁月度结算
    from core.free_effect import _settle_free_effects  # 延迟导入，避免顶层环
    _settle_free_effects(state, log)


def _record_task_memory(state, task, label):
    """事务推进写入记忆图谱（Phase 3a，原有行为保留）。

    P2-3：原 `except Exception: pass` 是纯静默；现记 debug（记忆图谱属可选旁路，
    失败确实无害，但不得无痕）。
    """
    try:
        tname = task.get("task_name", "政务")
        state.memory.add_entity(f"task_{tname}", "task", tname, turn=state.turn)
        state.memory.add_relation(f"task_{tname}", f"progress_{int(task.get('progress', 0))}",
                                  "progresses", weight=1.0, turn=state.turn,
                                  note=f"{label}进度{int(task.get('progress', 0))}%")
    except Exception as e:  # noqa: BLE001
        _log.debug("[事务] 记忆图谱写入失败（%s）：%s", task.get("task_name", ""), e)


