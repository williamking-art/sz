# -*- coding: utf-8 -*-
"""宋祚 · free_effect 通用契约（言枢密 v3 设计）。

AI 自由动作（free_edict 推演）产出的效果契约，程序侧**拒绝式**校验 + 落地：
- 白名单 13 字段（FREE_EFFECT_FIELD_WHITELIST，content/data.py 单一权威源），AI 只能提议；
- 数值经 TIER_RANGE/tier_to_value 换算并 CAP 封顶（FREE_EFFECT_CAP）；
- cost 超存量 → 整单不执行（拒绝）；成本失衡（cost 远超效果价值）→ 拒绝；
- mode=once 即时落地；mode=ongoing 入 state.longterm_effects 队列，由
  _settle_free_effects 在 12 步流水线「长期诏」步位月度结算（effects/cost 每月 apply、
  duration 递减、0=永久、到期核销）。
- AI 只有叙事/提议权，数值换算封顶归程序（与全游戏 AI 档位封顶同源）。
"""
import math

from content.data import FREE_EFFECT_FIELD_WHITELIST, FREE_EFFECT_CAP, FREE_EFFECT_COST_REJECT_RATIO


def _is_finite_number(v) -> bool:
    """真有限数值：排除 bool（bool 是 int 子类）、NaN、±inf。"""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return math.isfinite(v)
    return False


def _safe_int(v, default: int = 0) -> int:
    """安全取整：bool/NaN/Inf/非法 → default（禁止 int(nan) 抛错、int(True)==1 混入）。"""
    if not _is_finite_number(v):
        return default
    try:
        return int(v)
    except (ValueError, OverflowError, TypeError):
        return default


def _clamp(v, cap):
    """clamp 到 ±cap（保留小数——档位微 0.75 不截断，成本平衡评估准确；落地处自行 int）。

    非有限输入一律回落 0：修复 min(cap, nan) 在 CPython 下返回 cap（NaN 被当成 +CAP 铸币）。
    """
    if not _is_finite_number(v):
        return 0
    return max(-cap, min(cap, v))


# ============================================================
# 守恒层（审查 P0-5 修复）：free_effect 的 treasury/finance/cost 一律经
# 「国库 ↔ 民间钱池」成对划转，ΣΔ(国库+民间钱)==0——杜绝 AI 零成本铸币/销币。
# 民间钱池 = 各路 6 阶层 POP wealth；粮池 = 各路 POP grain（cost.granary 配对用）。
# ============================================================
def _money_pools(state):
    """全部民间钱池（[pop dict, ...]，含 wealth 字段的 6 阶层）。"""
    pools = []
    for p in getattr(state, "prefectures", {}).values():
        pops = p.get("pops") if isinstance(p, dict) else None
        if not isinstance(pops, dict):
            continue
        for pk in ("农", "士绅", "工匠", "商人", "官僚", "兵"):
            pp = pops.get(pk)
            if isinstance(pp, dict) and pp.get("wealth") is not None:
                pools.append(pp)
    return pools


def _grain_pools(state):
    """全部民间粮池（[pop dict, ...]，含 grain 字段的阶层）。"""
    pools = []
    for p in getattr(state, "prefectures", {}).values():
        pops = p.get("pops") if isinstance(p, dict) else None
        if not isinstance(pops, dict):
            continue
        for pk in ("农", "士绅", "工匠", "商人", "官僚", "兵"):
            pp = pops.get(pk)
            if isinstance(pp, dict) and pp.get("grain") is not None:
                pools.append(pp)
    return pools


def _money_feasible(state, d: int) -> bool:
    """money 效果可行性：d>0（征自民间入国库）需民间总持钱 ≥ d；
    d<0（国库出赏/购办入民间）需国库 ≥ |d|。"""
    d = int(round(d or 0))
    if d > 0:
        return sum(int(pp.get("wealth", 0) or 0) for pp in _money_pools(state)) >= d
    return getattr(state, "treasury", 0) >= -d


def _apply_money_delta(state, d: int) -> bool:
    """国库 ↔ 民间钱池守恒划转（ΣΔ==0，调用前须 _money_feasible 通过）：
    - d>0：国库入账，民间按持钱从高到低摊扣（税征/榷利等收益来源）；
    - d<0：国库出账，民间均分发放（赏赐/购办）。

    返回是否真正落地。**原子**：无民间池 / 余额不足 → 返回 False 且**零副作用**
    （修复前：空池时静默 return，cost.treasury 被记「耗国帑」实未扣 → 成本逃逸）。
    """
    d = _safe_int(d)
    if d == 0:
        return True
    pools = _money_pools(state)
    if not pools:
        return False
    if d > 0:
        remain = d
        for pp in sorted(pools, key=lambda x: -int(x.get("wealth", 0) or 0)):
            if remain <= 0:
                break
            w = int(pp.get("wealth", 0) or 0)
            take = min(remain, w)
            pp["wealth"] = w - take
            remain -= take
        if remain > 0:  # 预检已挡；防御兜底——不半落地
            return False
        state.change_treasury(d)
        return True
    spend = -d
    if getattr(state, "treasury", 0) < spend:
        return False
    n = len(pools)
    base, extra = spend // n, spend % n
    for i, pp in enumerate(pools):
        pp["wealth"] = int(pp.get("wealth", 0) or 0) + base + (1 if i < extra else 0)
    state.change_treasury(-spend)
    return True


def _grant_grain(state, amount: int) -> bool:
    """cost.granary 守恒配对：太仓出粮 → 民间粮池均分（粜济），ΣΔ==0。

    返回是否真正落地。无民间粮池 → False 且零副作用（调用方不得先扣太仓）。
    """
    amount = _safe_int(amount)
    if amount <= 0:
        return True
    pools = _grain_pools(state)
    if not pools:
        return False
    n = len(pools)
    base, extra = amount // n, amount % n
    for i, pp in enumerate(pools):
        pp["grain"] = int(pp.get("grain", 0) or 0) + base + (1 if i < extra else 0)
    return True


def _resolve_effect_value(dim, value):
    """效果值归一：档位词（无/微/小/中/大，可带 +/-）→ 数值；数字 → 原值；均 CAP 封顶。

    非有限（NaN/Inf）与 bool 一律回落 0——禁止 NaN 经 min(cap, nan) 变成 +CAP 铸币。
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return _clamp(value, FREE_EFFECT_CAP.get(dim, 1 << 30))
    if isinstance(value, str):
        text = str(value).strip()
        direction = 1.0
        if text.startswith("+"):
            text = text[1:]
        elif text.startswith("-"):
            direction = -1.0
            text = text[1:]
        from ai.client_utils import tier_to_value  # 延迟导入，避免顶层环
        v = direction * tier_to_value(dim, text, 1.0)
        return _clamp(v, FREE_EFFECT_CAP.get(dim, 1 << 30))
    return 0


def validate_free_effect(contract) -> str:
    """拒绝式校验契约，返回错误消息（"" = 通过）。"""
    if not isinstance(contract, dict):
        return "契约须为对象"
    mode = contract.get("mode")
    if mode not in ("once", "ongoing"):
        return "mode 须为 once/ongoing"
    eff = contract.get("effects")
    if not isinstance(eff, dict) or not eff:
        return "effects 须为非空对象"
    for k, v in eff.items():
        if k not in FREE_EFFECT_FIELD_WHITELIST:
            return f"effects 字段「{k}」不在白名单，整单拒绝"
        if k == "faction_change":
            if not isinstance(v, dict):
                return "faction_change 须为 {派系: 档位/数值}"
        elif k == "institution":
            # 阶段 C-7：编制参数须为 {参数名: 档位/数值}；具体键由 core.institution 逐项校验
            if not isinstance(v, dict) or not v:
                return "institution 须为非空 {参数名: 档位/数值}"
            from content.data import INSTITUTION_PARAM_SPEC
            unknown = [kk for kk in v if kk not in INSTITUTION_PARAM_SPEC]
            if unknown:
                return f"institution 含未授权参数 {unknown}，整单拒绝"
        elif isinstance(v, bool) or not isinstance(v, (int, float, str)):
            return f"effects[{k}] 值须为数字或档位词"
        elif isinstance(v, (int, float)) and not math.isfinite(v):
            return f"effects[{k}] 不接受 NaN/Inf"
    cost = contract.get("cost") or {}
    if cost:
        if not isinstance(cost, dict):
            return "cost 须为对象"
        for ck, cv in cost.items():
            if ck not in ("treasury", "granary"):
                return f"cost 字段「{ck}」不支持"
            if isinstance(cv, bool) or not isinstance(cv, (int, float)):
                return f"cost.{ck} 须为非负数字"
            if not math.isfinite(cv) or cv < 0:
                return f"cost.{ck} 须为非负有限数字"
    if mode == "ongoing":
        dur = contract.get("duration", 12)
        if isinstance(dur, bool) or not isinstance(dur, (int, float)):
            return "duration 须为非负整数（0=永久）"
        if not math.isfinite(dur) or dur < 0:
            return "duration 须为非负有限数（0=永久）"
    return ""


def _apply_effect_to_state(state, effects):
    """把白名单 effects 落地到 GameState（CAP 封顶，AI 只有提议权）。返回日志。"""
    log = []
    for k, v in effects.items():
        if k == "faction_change":
            for fname, fv in (v or {}).items():
                if fname in state.factions:
                    d = int(_resolve_effect_value("population_satisfaction", fv))
                    state.factions[fname]["satisfaction"] = max(0, min(100, state.factions[fname]["satisfaction"] + d))
                    log.append(f"派系{fname}{'+' if d >= 0 else ''}{d}")
            continue
        if k == "institution":
            # 阶段 C-7：编制参数（§12.3 六杠杆 ＋ §17.4 参数清单 ＋ S-D6 维持费）。
            # 值域由 INSTITUTION_PARAM_SPEC 单点约束；逐项钳制，未知键逐项拒绝。
            from core import institution as _inst
            log += _inst.apply_reform(state, v)
            continue
        if k == "prestige":
            d = _resolve_effect_value(k, v)
            state.change_prestige(d, "自由动作")
        elif k == "treasury":
            # 审查 P0-5：国库增减一律与民间钱池成对（税征/赏赐），ΣΔ==0，不凭空铸币
            d = _safe_int(_resolve_effect_value(k, v))
            if not _money_feasible(state, d) or not _apply_money_delta(state, d):
                log.append(f"{k} 效果未落地：余额不足（{d:+d}）")
                continue
        elif k == "population_satisfaction":
            d = _resolve_effect_value(k, v)
            state.population_satisfaction = max(0, min(100, state.population_satisfaction + d))
        elif k.startswith("external_"):
            d = _resolve_effect_value(k, v)
            ext_key = {"external_jin": "金", "external_liao": "辽", "external_xixia": "西夏"}[k]
            state.external[ext_key]["attitude"] = max(0, min(100, state.external[ext_key].get("attitude", 50) + d))
        elif k == "defense_bonus":
            d = _resolve_effect_value(k, v)
            for line in state.defense_lines.values():
                line["fortification"] = max(0, min(100, line.get("fortification", 50) + d))
        elif k == "tech":
            d = _resolve_effect_value(k, v)
            state.tech["level"] = max(0, min(100, state.tech.get("level", 50) + d))
        elif k == "art_mastery":
            d = _resolve_effect_value(k, v)
            state.art_mastery = max(0, min(100, state.art_mastery + d))
        elif k == "army":
            d = _resolve_effect_value(k, v)
            for u in state.army_units:
                u.training = max(0, min(100, u.training + d))
                u.morale = max(0, min(100, u.morale + d))
        elif k == "finance":
            # 审查 P0-5：金融/市舶收益视同征自民间（国库入 ↔ 民间扣），ΣΔ==0
            d = _safe_int(_resolve_effect_value(k, v))
            if not _money_feasible(state, d) or not _apply_money_delta(state, d):
                log.append(f"{k} 效果未落地：余额不足（{d:+d}）")
                continue
        elif k == "talent":
            d = _resolve_effect_value(k, v)
            state.exam["talent_pool"] = max(0, min(100, state.exam.get("talent_pool", 0) + d))
        log.append(f"{k}{'+' if d >= 0 else ''}{d}")
    return log


def _pay_cost(state, cost, log):
    """扣除契约成本（treasury/granary）。超存量在调用前由检查拒绝，不造钱。

    审查 P0-5：政府开支守恒化——cost.treasury 出账后均分发放至民间钱池
    （工钱/购办），cost.granary 出仓后均分至民间粮池（粜济），ΣΔ==0，
    杜绝"国库灭钱/太仓灭粮无去向"的凭空销毁。
    """
    for k, v in (cost or {}).items():
        cv = _safe_int(v)
        if cv <= 0:
            continue
        if k == "treasury":
            if getattr(state, "treasury", 0) < cv:
                continue
            # 国库 -cv 且民间 +cv（成对，ΣΔ==0）；空池/失败 → 不扣账、不记假账
            if _apply_money_delta(state, -cv):
                log.append(f"耗国帑{cv}（散入民间工赈）")
            else:
                log.append(f"耗国帑{cv} 未执行：民间池不可达（守恒拒绝，防灭钱）")
        elif k == "granary":
            if getattr(state, "granary", 0) < cv:
                continue
            # 先确认民间粮池可达再出仓——防「已出仓却无去向」的灭粮
            if not _grant_grain(state, cv):
                log.append(f"耗太仓{cv}石 未执行：民间粮池不可达（守恒拒绝，防灭粮）")
                continue
            state.change_granary(-cv)
            log.append(f"耗太仓{cv}石（粜济民间）")


def _cost_affordable(state, cost) -> bool:
    """成本可承受判定（超存量 → 整单不执行）。"""
    for k, v in (cost or {}).items():
        cv = _safe_int(v)
        if cv <= 0:
            continue
        if k == "treasury" and state.treasury < cv:
            return False
        if k == "granary" and state.granary < cv:
            return False
    return True


def _cost_balanced(effects, cost) -> bool:
    """成本失衡拒绝：cost 总额 > FREE_EFFECT_COST_REJECT_RATIO × 效果价值（粗估折价）。"""
    if not cost:
        return True
    cost_total = _safe_int(cost.get("treasury", 0)) + _safe_int(cost.get("granary", 0)) * 2   # 粮折钱粗估 2 贯/石
    value = 0.0
    for k, v in effects.items():
        if k in ("treasury", "finance"):
            value += abs(_resolve_effect_value(k, v))
        elif k in ("prestige", "population_satisfaction", "tech", "art_mastery",
                   "army", "talent", "defense_bonus", "external_jin", "external_liao", "external_xixia"):
            value += abs(_resolve_effect_value(k, v)) * 200_000   # 非国库效果折价（量级粗估）
        elif k == "faction_change":
            value += sum(abs(_resolve_effect_value("population_satisfaction", fv))
                         for fv in (v or {}).values()) * 100_000
    return cost_total <= max(1, value * FREE_EFFECT_COST_REJECT_RATIO)


def _money_effects_feasible(state, effects, cost) -> bool:
    """前置可行性（审查 P0-5 / B6 修复）：effects 的 treasury/finance 增减**与 cost 出账**
    按**合计**校验，任一不足 → 整单不执行（原子拒绝，不部分落地）。

    修复前（B6）：逐项各自判 `_money_feasible`，并单独判 `cost.treasury <= treasury`，
    **从不校验「Σ出账 + cost ≤ 可用余额」**。当契约同时含多项出账（如
    `treasury:-80` 与 `finance:-80`，或效果出账 + cost 出账）时预检全部通过，
    而落地阶段第二个键因余额不足被静默 `continue` 跳过 → 契约**半落地**，
    与模块文档「任一无足额 → 整单不执行」直接矛盾。

    现口径（净额）：
      - 国库净变动 = Σ(effects.treasury/finance) − cost.treasury；
        净出账时要求 `treasury >= |净出账|`；
      - 自民间征收合计（Σ 正项）须 ≤ 民间总持钱（征收先于 cost 的发放）；
      - cost.granary 须 ≤ 太仓存粮。
    """
    try:
        effects = effects or {}
        cost = cost or {}
        treasury_delta = 0
        pop_demand = 0
        for k, v in effects.items():
            if k in ("treasury", "finance"):
                d = _safe_int(round(_resolve_effect_value(k, v) or 0))
                treasury_delta += d
                if d > 0:
                    pop_demand += d
        treasury_delta -= int(cost.get("treasury", 0) or 0)
        if treasury_delta < 0 and getattr(state, "treasury", 0) < -treasury_delta:
            return False
        if pop_demand > 0:
            pop_have = sum(int(pp.get("wealth", 0) or 0) for pp in _money_pools(state))
            if pop_have < pop_demand:
                return False
        if _safe_int(cost.get("granary", 0) or 0) > getattr(state, "granary", 0):
            return False
    except Exception:
        return False
    return True


def _apply_free_effect(state, contract) -> list:
    """AI free_effect 契约落地（拒绝式）：白名单校验 → cost 承受 → 成本平衡 → 落地。

    mode=once 立即 apply effects + cost；mode=ongoing 入 state.longterm_effects 队列。
    任一校验失败/成本不可承受/失衡/国库民间资财不足 → 不落地，返回错误日志
    （不伪造、不部分执行）。
    """
    err = validate_free_effect(contract)
    if err:
        return [f"[自由动作] 契约拒绝：{err}"]
    cost = contract.get("cost") or {}
    if not _cost_affordable(state, cost):
        return [f"[自由动作] 成本不足，整单不执行（需 {cost}）"]
    if not _cost_balanced(contract.get("effects", {}), cost):
        return ["[自由动作] 成本失衡拒绝（cost 远超效果价值）"]
    if not _money_effects_feasible(state, contract.get("effects", {}), cost):
        return ["[自由动作] 国库/民间资财不足，整单不执行（守恒拒绝，防凭空造灭）"]
    log = []
    mode = contract.get("mode", "once")
    if mode == "once":
        log += _apply_effect_to_state(state, contract.get("effects", {}))
        _pay_cost(state, cost, log)
    else:
        item = {
            "name": str(contract.get("name", "自由制度"))[:20],
            "mode": "ongoing",
            "duration": _safe_int(contract.get("duration", 12), default=12),
            "effects": contract.get("effects", {}),
            "cost": dict(cost),
        }
        state.longterm_effects.append(item)
        log.append(f"[自由动作] 立长期制度「{item['name']}」（duration={item['duration']}，0=永久）")
    return log


def _settle_free_effects(state, log) -> None:
    """12 步流水线「长期诏」步位：月度结算 longterm_effects（effects/cost 每月 apply、
    duration 递减、0=永久、到期核销）。"""
    if not getattr(state, "longterm_effects", None):
        return
    keep = []
    for item in state.longterm_effects:
        effects = item.get("effects", {})
        cost = item.get("cost", {})
        # 审查 P0-5：成本承受 + 国库/民间资财可行性（money 效果成对划转）
        applied = bool(_cost_affordable(state, cost)
                       and _money_effects_feasible(state, effects, cost))
        if applied:
            log += _apply_effect_to_state(state, effects)
            _pay_cost(state, cost, log)
            log.append(f"[制度] {item.get('name', '')} 本月生效")
        else:
            log.append(f"[制度] {item.get('name', '')} 资财不足，本月暂缓")
        dur = int(item.get("duration", 0))
        if dur == 0:
            keep.append(item)            # 0 = 永久
        elif applied:
            # 审查 P3 修复：仅在「真正生效」的月份递减 duration。原实现暂缓月也照常
            # 递减寿命，长期制度在未足额生效的月份被消耗、提前核销。
            dur -= 1
            if dur > 0:
                item["duration"] = dur
                keep.append(item)
            else:
                log.append(f"[制度] {item.get('name', '')} 到期核销")
        else:
            keep.append(item)            # 本月暂缓：保留原 duration，下月继续尝试
    state.longterm_effects = keep
