# -*- coding: utf-8 -*-
"""宋祚 · 皇帝个人与隐藏状态（从 settlement_steps.py 拆出，零行为变更）。

`_settle_emperor_personal` / 帝王行动效果 / `_settle_hidden(_pop)`。"""
from __future__ import annotations

import logging
import random

from content.data import (
    TIER_RANGE,
)

# 🔴 方案乙（2026-10-04 POP 实体下沉州府级）：POP 写入走桥接层；未下沉时回落原写法
from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add
from core.settlement_common import (
    _distribute_cash,
)
from content.data_constants import PERSONS_PER_HOUSEHOLD

_log = logging.getLogger("settlement")

def _hidden_people(p) -> int:
    """某路隐户**口数**（`农` POP 的加法子池 `hidden`；缺键视为 0）。"""
    return max(0, int((((p.get("pops") or {}).get("农")) or {}).get("hidden", 0) or 0))


def ensure_hidden_in_pops(state) -> int:
    """幂等迁移：把 `land["hidden_households"]`（户，含旧档镜像）**物化**进各路 `农.hidden`（口）。

    - **新局**：`content/data.py` 的 land 初值给出 500 万户（= 2000 万口，设计锚：
      总口 1 亿 = 在籍 8000 万 + 隐户 2000 万），而 POP 子池初值为 0 →
      由本函数按各路 `population` 比例注入，使「总口 = 在籍 + 隐户」与旧口径**数值一致**；
    - **旧档**：只有镜像、无子池 → 同样注入；
    - **幂等**：Σ子池 > 0 时不动（新档已同时存子池与派生镜像，载入后保持一致）。

    返回注入的口数（0 = 无需迁移）。**不改在籍口径**（`state.population` 不含隐户）。
    """
    prefs = getattr(state, "prefectures", None) or {}
    land = getattr(state, "land", None)
    if not prefs or not isinstance(land, dict):
        return 0
    if sum(_hidden_people(p) for p in prefs.values()) > 0:
        return 0
    want = int(land.get("hidden_households", 0) or 0) * PERSONS_PER_HOUSEHOLD
    if want <= 0:
        return 0
    items = list(prefs.values())
    weights = [max(1, int(p.get("population", 0) or 0)) for p in items]
    total_w = sum(weights)
    given = 0
    for i, p in enumerate(items):
        slot = (p.get("pops") or {}).get("农")
        if not isinstance(slot, dict):
            continue
        part = (want - given) if i == len(items) - 1 else int(want * weights[i] / total_w)
        if part <= 0:
            continue
        slot["hidden"] = int(slot.get("hidden", 0) or 0) + part
        given += part
    if given < want:                      # 尾差：补进第一个有农槽的路（不凭空少口）
        for p in items:
            slot = (p.get("pops") or {}).get("农")
            if isinstance(slot, dict):
                slot["hidden"] = int(slot.get("hidden", 0) or 0) + (want - given)
                break
    return given


def _settle_hidden_pop(state, log):
    """隐户动态（月度，**人口守恒**）：隐户是 `农` POP 的**加法子池 `hidden`（口）**，
    **不再是第 7 类人口池**（POP 挂载律条 1/4；2026-09-27 用户拍板方案 A 落地）。

    1) 逃籍（在籍 → 隐户）：税重 + 灾荒 + 民怨 → 部分 农/工匠/商人 转隐户。
       **逐路局部守恒**：该路来源 POP `size` 减、该路 `农.hidden` 增，两侧同额。
    2) 归籍（隐户 → 在籍）：清丈/轻徭/招抚 → 该路 `农.hidden` 减、`农.size` 增（同额）。

    口径（与旧实现的差异）：
      · **在籍人口 `state.population` 不含隐户**（隐户不落籍、不纳税）；
      · 「总口」= Σ六类 `size` ＋ Σ`农.hidden`（需求侧见 `game_state_econ`）；
      · 旧实现以**户**记账并维护 `land["hidden_rem"]` 余数科目（÷4 换算的产物）；
        现**直接以口记账** → 余数科目消灭，也不再需要"全局户数按路摊派"；
      · `land["hidden_households"]` 降级为**派生镜像**（= Σhidden // `PERSONS_PER_HOUSEHOLD`，户），
        仅供 UI/旧档/文档读取。
    隐户不落籍不纳税；UI 不显示（设计锚）。
    """
    land = state.land
    prefs = state.prefectures or {}
    # 1) 逃户压力（在籍→隐户）：税率高 + 灾荒 + 民怨（压力口径与旧实现一致）
    # 审查 P2-20 修复保留：原读 `commerce_tax`（不存在，getattr 恒返回默认 0.05）→ 压力恒 0，
    # 「税重→逃户」永不触发；现读真实字段 `commerce_tax_rate`，基准取默认税率 0.15。
    _tax_pressure = min(0.010, max(0.0, (getattr(state, "commerce_tax_rate", 0.15) - 0.15) * 1.0))
    _sat_pressure = max(0.0, (50 - getattr(state, "population_satisfaction", 50)) / 50.0) * 0.004

    # ---- S6 落地（用户 2026-10-01 口径裁决 · 经二次细化）----
    # **逃籍人数由「实际无法吃粮的人数」1:1 派生，不用 2%/0.008 这类比例魔数。**
    #   缺粮人数 = Σ各类 POP 中吃不上饭的人数，口径见
    #   `core/settlement_common.py::food_insecure_headcount`（**单点**）：
    #   可支配粮 = 自有粮 ＋ 购粮能力(`wealth / 粮价`)，买得到就不算饿；
    #   需求 = `size × GRAIN_CONSUME_PER_CAPITA[类]`。
    #   逃籍 = `min(该路缺粮人数, FLEE_CAP_PER_ROUTE)` —— 上限仅作爆版保护。
    #
    # **与既有"饥荒逃农"通道同源**（`settlement_granary` 也调同一 helper 去魔数）：
    # 两条通道语义不同但同判据 —— 逃籍=**躲籍**（留在本路、不落籍不纳税）、
    # 逃荒=**离籍**（迁为流民），不再出现"没饿却在逃籍"的矛盾。
    #
    # 口径演进（留痕）：
    #   ① 原式 `p["grain"] < population * 0.3`：年粮 vs 口×0.3，**量纲错配** → 0/20 死码；
    #   ② 曾按用户口径改为"逐路公储 `grain_months < 1 月" —— 但实测成都府路公储 0.79 月
    #      而户储 2.39 月，**没人真饿**却判逃籍（假逃籍），且公储信号近乎二值；
    #   ③ 现按缺粮人数驱动：开局实算缺粮 75 万 / 1.0075 亿 = 0.74%，梯度连续、可解释。
    #      `grain_months` 仍是面板上的**公储告急读数**（`region_brief`），但不再当逃籍判据。
    from core.settlement_common import FLEE_CAP_PER_ROUTE, food_insecure_headcount
    # 逃籍只可能来自 农/工匠/商人（挂 `hidden` 子池）；**兵**缺粮由军粮段单独保障，
    # 不转隐户，故不计入逃籍驱动量（但仍单列诊断，见下）。
    _FLEE_CLASSES = ("农", "工匠", "商人")
    _hungry_by_route = {}
    _hungry_total = 0
    _hungry_army = 0
    for _rname, _p in prefs.items():
        if not isinstance(_p, dict):
            continue
        _pops = _p.get("pops") or {}
        _h = food_insecure_headcount(_pops, float(_p.get("grain_price", state.grain_price)))
        _n = sum(int(_h.get(_c, 0) or 0) for _c in _FLEE_CLASSES)
        _hungry_army += int(_h.get("兵", 0) or 0)
        if _n > 0:
            _hungry_by_route[_rname] = _n
            _hungry_total += _n
    # 可诊断读数（缺失≠静默）：谁在挨饿，面板/日志可查。
    # `hidden_flee_actual`（本月实际逃籍人数）在下方逃籍循环**之后**回填——
    # 它与 `hidden` 净变化不同：同一次调用里归籍会同时减 `hidden`。
    state.statistics["hidden_flee_hungry"] = _hungry_total
    state.statistics["hidden_flee_by_route"] = dict(sorted(_hungry_by_route.items()))
    # 兵缺粮单列（不驱动逃籍，但要让"为什么不动"可查）
    state.statistics["army_grain_hungry"] = _hungry_army

    _flee_actual = 0
    for _rname, _p in prefs.items():
        pops = _p.get("pops") or {}
        _nong = pops.get("农")
        if not isinstance(_nong, dict):
            continue
        # ---- 腿①**粮**：缺粮人数 1:1 派生（无比例魔数，上限仅爆版保护）----
        _hungry = int(_hungry_by_route.get(_rname, 0) or 0)
        _want = min(_hungry, FLEE_CAP_PER_ROUTE)
        # ---- 腿②**税重/民怨**：压力率折算（沿用原口径，非人数派生）----
        # 这两条是**独立机制**（逃税 / 逃乱，不等于逃饥），无"人数"可用，故保留原有
        # 压力权重；若一并改成人数驱动需另定口径，故此处不动，仅受总上限约束。
        _rate = min(0.012, _tax_pressure + _sat_pressure)
        if _rate > 0:
            _avail = sum(int((pops.get(_k) or {}).get("size", 0) or 0)
                         for _k in ("农", "工匠", "商人"))
            _want += int(_avail * _rate)
        if _want <= 0:
            continue
        _left = _want
        for _name in ("农", "工匠", "商人"):
            if _left <= 0:
                break
            _slot = pops.get(_name)
            if not isinstance(_slot, dict):
                continue
            _sz = int(_slot.get("size", 0) or 0)
            _t = min(_left, _sz)
            if _t > 0:
                if _pop_obj_add(state, _slot, "size", -_t) is None:
                    _slot["size"] = _sz - _t
                _left -= _t
        _got = _want - _left
        if _got > 0:
            if _pop_obj_add(state, _nong, "hidden", _got) is None:
                _nong["hidden"] = int(_nong.get("hidden", 0) or 0) + _got
            _flee_actual += _got
    state.statistics["hidden_flee_actual"] = _flee_actual
    if _flee_actual > 0:
        log.append(f"[隐户] {_flee_actual:,} 人吃不上饭，逃为隐户"
                   f"（不落籍不纳税；挂本路 农 POP 子池 `hidden`；"
                   f"全图缺粮 {_hungry_total:,} 人）")
    if _hungry_total > 0 and not _flee_actual:
        log.append(f"[粮储] 全图 {_hungry_total:,} 人吃不上饭，但无可逃之众（各路在籍为 0）")
    # 2) 归籍（隐户→在籍）：清丈/轻徭/招抚——逐路 `农.hidden` 减、`农.size` 增（同额）
    _survey = int(land.get("survey", 0) or 0)
    _back_rate = 0.004 + (0.010 if _survey else 0.0)
    _back_people = 0
    if _back_rate > 0:
        for _p in prefs.values():
            _nong = (_p.get("pops") or {}).get("农")
            if not isinstance(_nong, dict):
                continue
            _hid = int(_nong.get("hidden", 0) or 0)
            _t = min(_hid, int(_hid * _back_rate))
            if _t <= 0:
                continue
            if _pop_obj_add(state, _nong, "hidden", -_t) is None:
                _nong["hidden"] = _hid - _t
            if _pop_obj_add(state, _nong, "size", _t) is None:
                _nong["size"] = int(_nong.get("size", 0) or 0) + _t
            _back_people += _t
    if _back_people > 0:
        log.append(f"[隐户] {'清丈' if _survey else '招抚'}，{_back_people:,} 口归籍复业（回本路 农 POP）")

    # 派生镜像（户）+ 旧余数科目清理：`hidden_rem` 是旧"以户记账 ÷4"的产物，随以口记账消灭
    land["hidden_households"] = sum(_hidden_people(_p) for _p in prefs.values()) // PERSONS_PER_HOUSEHOLD
    land.pop("hidden_rem", None)


def _settle_emperor_personal(state, log):
    """皇帝个人行动结算（行动矩阵契约 v2）。

    时序：带宽回调 → 自然衰老 → 出京政务减损（远程批奏 -1）→
    出京准备期月度推进（pending_imperial_trip）→ 成行落地（程序基础开销守恒 +
    效果档位落地 + 风险事件）→ 清场（行动/准备/微服计数/旧字段）。
    AI（_emperor_ai 契约 v2）只给 effects 档位词与 risk/narrative；失败走矩阵
    base_effects 程序兜底（不伪造 AI 文本）。费用由程序按行动类型核算，AI 不写数值。
    """
    # 1) 基础回调：上月临时带宽过期（最低 6）
    state.decree_bandwidth = max(6, state.decree_bandwidth - 2)

    # 2) 自然衰老（原有；健康不触发 game over，仅影响衰减/行动）
    if state.year >= 1120:
        natural_decay = 1 + (state.year - 1120) // 2
    else:
        natural_decay = (state.year - 1101) // 4
    if natural_decay > 0:
        state.emperor_health = max(0, state.emperor_health - natural_decay)
        log.append(f"[皇帝] 春秋渐高，龙体自然损耗 {natural_decay}")

    # 3) 公开出京：不影响政务（远程批奏），圣旨带宽仅 -1
    act = state.imperial_action or {}
    if act and act.get("location") == "出京" and act.get("mode") == "公开":
        state.decree_bandwidth = max(5, state.decree_bandwidth - 1)
        log.append("[皇帝] 大驾出京，政务远程批奏，圣旨额度稍减（-1）")

    # 4) 出京准备期月度推进（pending_imperial_trip）
    if getattr(state, "pending_imperial_trip", None) is not None:
        state.pending_imperial_trip["pending_months"] = max(
            0, state.pending_imperial_trip.get("pending_months", 1) - 1)
        if state.pending_imperial_trip.get("pending_months", 0) > 0:
            _left = state.pending_imperial_trip["pending_months"]
            log.append(f"[皇帝] {act.get('action', '出京')}准备中，尚余 {_left} 月")
            state.personal_action = ""
            state.major_policy = ""
            state.imperial_micro_count = 0
            return
        log.append("[皇帝] 銮驾备毕，本月成行")

    # 5) 行动落地（宫里/京城 当月生效；出京准备完成当月成行）
    if act:
        _apply_imperial_action(state, act, log)
    else:
        # 旧档/旧通道兼容：单值 personal_action → 宫里·公开 矩阵行动
        from content.data import LEGACY_PERSONAL_ACTION_MAP
        _legacy = LEGACY_PERSONAL_ACTION_MAP.get(getattr(state, "personal_action", ""))
        if _legacy:
            state.imperial_action = {
                "location": "宫里", "mode": "公开", "action": _legacy,
                "prepared": False, "pending_months": 0, "target": "",
            }
            _apply_imperial_action(state, state.imperial_action, log)
        else:
            # 无行动：龙体自然起伏（原有 idle 漂移）
            state.emperor_health = max(0, min(100,
                state.emperor_health + random.randint(-1, 1)))

    # 6) 清场
    state.imperial_action = {}
    state.pending_imperial_trip = None
    state.personal_action = ""
    state.major_policy = ""
    state.imperial_micro_count = 0


def _imp_split_tier(value):
    """皇帝行动效果档位拆解：'±档位词' → (档位词, 方向 ±1)；数字原样 (值, +1)。"""
    if isinstance(value, (int, float)):
        return str(value), 1.0
    text = str(value).strip()
    direction = 1.0
    if text.startswith("+"):
        text = text[1:]
    elif text.startswith("-"):
        direction = -1.0
        text = text[1:]
    return text, direction


def _imp_tier_delta(dim, tier, direction):
    """档位词 → 数值：prestige/民心走 ai.client_utils 既有换算；
    健康/心情等 0~100 刻度维度用 IMPERIAL_EFFECT_BASE 基准（单一权威源 content.data）。"""
    from content.data import IMPERIAL_EFFECT_BASE
    if dim == "prestige":
        from ai.client_utils import tier_to_value
        return int(round(direction * tier_to_value("prestige", tier, 1.0)))
    if dim == "population_satisfaction":
        from ai.client_utils import tier_to_value
        return int(round(direction * tier_to_value("population_satisfaction", tier, 1.0)))
    base = IMPERIAL_EFFECT_BASE.get(dim, 3.0)
    return int(round(direction * base * TIER_RANGE.get(tier, 0.0)))


def _apply_imperial_action(state, act, log):
    """落地皇帝个人行动：程序基础开销（守恒）→ 效果（AI 档位/矩阵兜底）→ 风险事件。"""
    from content.data import (IMPERIAL_ACTION_MATRIX, IMPERIAL_RISK_PROB,
                              IMPERIAL_EFFECT_DIM)
    from core.events import get_imperial_risk_event
    cell = (IMPERIAL_ACTION_MATRIX.get(act.get("location", ""), {})
                                   .get(act.get("mode", ""), {}).get(act.get("action", "")))
    if not cell:
        log.append("[皇帝] 行止无效（矩阵外），未执行")
        return
    _name = f"{act.get('location', '')}·{act.get('mode', '')}·{act.get('action', '')}"

    # 1) 程序基础开销（守恒：公开→国库 / 微服→内帑；AI 不写数值）
    cost = int(cell.get("base_cost", 0))
    fund = cell.get("fund", "treasury")
    if cost > 0:
        avail = state.treasury if fund == "treasury" else state.imperial_treasury
        paid = min(cost, max(0, int(avail)))
        short = cost - paid
        # 2026-09-18 测试体检修复（货币守恒）：原为裸扣（`change_treasury(-paid)` /
        # `imperial_treasury -= paid`）—— 无对手方，皇帝个人行动的度支凭空消失。
        # 皇帝挥霍/兴造是**宫廷支出**，按"支出回流"口径转入民间（工匠40%/商人60%），
        # 与 `_settle_finance` 常费、`_settle_upkeep` 维持费、国策度支同口径。
        #
        # 审查 P2-3 / M3 修复（**部分分发后全额退款 = 造币 + 日志谎报**）：
        # 原实现 `except Exception: _given = 0` → 退 `paid - 0` **全额**回国库/内帑，
        # 而 `_distribute_cash` 是边算边写各 POP `wealth` 的（非原子）——先入账的 POP
        # 留下、国库又全退 ⇒ 净扣 0 而民间多钱（ΣΔ>0，凭空造币）；随后日志仍写
        # 「支 {paid} 贯」把没花出去的钱说成花出去了。
        # 现口径：① `_distribute_cash` 两阶段（构造完才写，异常时零写入）；
        #          ② 退款额用**实际已分发额**（`_applied` 逐笔累加，不信任"0"）；
        #          ③ 日志打印**实扣额**（= 已分发额），异常另补一行可见说明＋traceback。
        _applied = []
        _given = 0
        _dist_err = None
        if paid > 0:
            if fund == "treasury":
                state.change_treasury(-paid)
            else:
                state.imperial_treasury = max(0, state.imperial_treasury - paid)
            try:
                from content.data import GOV_SPEND_TO
                _given = _distribute_cash(state, paid, GOV_SPEND_TO, applied=_applied)
            except Exception as e:            # noqa: BLE001 — 必须可见，且按实际已分发额退款
                _given = sum(_applied)        # ← 实际已分发额（不得按 0 全额退）
                _dist_err = e
                logging.getLogger("settlement").exception(
                    "[皇帝] %s：宫廷支出分发异常（已分发 %s/%s 贯，按实际额退款）",
                    _name, _given, paid)
                log.append(f"[皇帝][WARN] {_name}：支出发放异常，仅按已分发额记账"
                           f"（{type(e).__name__}）")
            if _given != paid:           # 无接收方/异常兜底：退回未分发部分，不静默销毁
                _back = paid - _given
                if fund == "treasury":
                    state.change_treasury(_back)
                else:
                    state.imperial_treasury += _back
        _actual = _given                          # 实扣额 = 实际分发额（自洽，非请求额）
        _note = f"（府库不足，缺 {short:,} 贯）" if short else ""
        # 未散出部分与实扣额写在**同一行**：`flow_summary._extract_one_off` 取该行
        # 第一个「数字+贯」，若另起一行会被当成第二笔「皇帝行止」支出（面板双计）。
        if _dist_err is not None and _actual < paid:
            _note += f"（{paid - _actual:,} 贯未散出，已退回国库/内帑）"
        _src = "国库" if fund == "treasury" else "内帑"
        # 日志金额 == **实扣额**（审查 P2-3 验收断言）：分发出错时不得仍写请求额。
        log.append(f"[皇帝] {_name}：{_src}支 {_actual:,} 贯{_note}")

    # 2) 效果：矩阵 base_effects（程序兜底）+ AI 契约 v2 档位词（有则覆盖核心 4 键）
    _ai = getattr(state, "_emperor_ai", None)
    ai_eff = _ai.get("effects") if isinstance(_ai, dict) and not _ai.get("_error") else None
    deltas = {}
    for k, v in (cell.get("base_effects") or {}).items():
        if k == "faction_change":
            continue  # 派系单独处理（见落地）
        deltas[k] = v
    if isinstance(ai_eff, dict):
        for k, tier in ai_eff.items():
            dim = IMPERIAL_EFFECT_DIM.get(k)
            if not dim:
                continue
            t, d = _imp_split_tier(tier)
            deltas[dim] = _imp_tier_delta(dim, t, d)   # AI 覆盖 base 的同键
    _apply_imperial_effects(state, deltas, cell, log, _name)

    # 3) 风险事件（risk 档 → 程序概率：低2%/中8%/高20%；时代门槛/史实锚见 events.py）
    risk = cell.get("risk", "低")
    if isinstance(_ai, dict) and not _ai.get("_error") and _ai.get("risk") in IMPERIAL_RISK_PROB:
        risk = _ai["risk"]
    prob = IMPERIAL_RISK_PROB.get(risk, 0.02)
    if random.random() < prob:
        ev = get_imperial_risk_event(state, act)
        if ev:
            _apply_imperial_effects(state, ev.get("effects") or {}, None, log, ev.get("title", "风险事件"))
            _tag = ev.get("label", "合理推演")
            _desc = ev.get("desc", "")
            log.append(f"[风险·{_tag}] {ev.get('title', '')}：{_desc}")
            state.active_events.append({"title": ev.get("title", "风险事件"),
                                        "message": _desc, "label": _tag, "risk": risk})
            state.event_history.append(ev)
            try:
                state.memory.record_event(f"imperial_{ev.get('id', 'risk')}",
                                          ev.get("title", ""), involved=(), turn=state.turn)
            except Exception:
                pass  # 记忆知识库写入失败属纯增强，无状态风险（设计豁免，保留不留痕）


def _apply_imperial_effects(state, effects, cell, log, name):
    """效果落地（state_applier 白名单 path：prestige/population_satisfaction/emperor_health/
    art_mastery/taoism_leaning/pleasure_leaning/factions.*.satisfaction/decree_bandwidth）。"""
    if "bandwidth_bonus" in effects:
        state.decree_bandwidth = min(10, state.decree_bandwidth + int(effects["bandwidth_bonus"]))
    if "prestige" in effects:
        d = int(effects["prestige"])
        state.change_prestige(d, name)
        log.append(f"[皇帝] {name}：皇威 {'+' if d >= 0 else ''}{d}")
    if "population_satisfaction" in effects:
        d = int(effects["population_satisfaction"])
        state.population_satisfaction = max(0, min(100, state.population_satisfaction + d))
        log.append(f"[皇帝] {name}：民心 {'+' if d >= 0 else ''}{d}")
    if "emperor_health" in effects:
        d = int(effects["emperor_health"])
        state.emperor_health = max(0, min(100, state.emperor_health + d))
        log.append(f"[皇帝] {name}：龙体 {'+' if d >= 0 else ''}{d}")
    if "pleasure_leaning" in effects:
        d = int(effects["pleasure_leaning"])
        state.pleasure_leaning = max(0, min(100, state.pleasure_leaning + d))
    if "art_mastery" in effects:
        d = int(effects["art_mastery"])
        state.art_mastery = max(0, min(100, state.art_mastery + d))
    if "taoism_leaning" in effects:
        d = int(effects["taoism_leaning"])
        state.taoism_leaning = max(0, min(100, state.taoism_leaning + d))
    if "treasury" in effects:
        d = int(effects["treasury"])
        state.change_treasury(d)   # 风险事件（地方应奉/花石纲等）显式收支，reason 见事件描述
        log.append(f"[皇帝] {name}：国帑 {'+' if d >= 0 else ''}{d:,} 贯")
    if cell and (cell.get("base_effects") or {}).get("faction_change"):
        for fname, d in (cell["base_effects"]["faction_change"] or {}).items():
            if fname in state.factions:
                state.factions[fname]["satisfaction"] = max(0, min(100,
                    state.factions[fname]["satisfaction"] + int(d)))
                log.append(f"[皇帝] {name}：{fname}满意度 {'+' if d >= 0 else ''}{d}")


# ------------------------------------------------------------
# Step 10: 隐藏状态
# ------------------------------------------------------------

def _settle_hidden(state, log):
    """隐藏状态结算（灾害、政令累积效果等）"""
    # 隐户动态（用户指示：隐户是动态人口池，与六类 POP 转换，非静态）——月度逃户/归籍
    try:
        _settle_hidden_pop(state, log)
    except Exception as e:  # noqa: BLE001 — 已改为记入结算日志（失败可见）
        _log.exception("[归籍] 隐户结算失败（本月未归籍，POP 未变）")
        log.append("[归籍] 隐户归籍结算失败，本月未归籍（POP 未变）"
                   f"（{type(e).__name__}）")
    if state.population_satisfaction < 30:
        if random.random() < 0.15:
            # 审查 P2-21：补下限钳制（其余结算处均已 max(0,…)，此处漏）
            state.population_satisfaction = max(0, state.population_satisfaction - 1)
            log.append("[激变] 民怨沸腾，偶有骚乱")

    jin = state.external["金"]
    if jin.get("invasion_will", 0) >= 90 and state.year >= 1122:
        if random.random() < 0.08:
            from core.army_models import _army_power, _army_power_total, _resolve_battle
            jin["invasion_will"] = 80
            gunpowder = state.tech.get("gunpowder", 20)
            front_routes = ("河北路", "河东路", "陕西路")
            front_units = [u for u in state.army_units if u.station in front_routes]
            my_power = _army_power_total(front_units, gunpowder)
            jin_power = state.external["金"]["power"]
            win, loss_power, breach = _resolve_battle(my_power, jin_power)
            # 按各 unit 战力占比把 loss_power 分摊成真实伤亡（向下取整，余数归主将部）
            casualty = 0
            if my_power > 0 and loss_power > 0 and front_units:
                powers = [_army_power(u, gunpowder) for u in front_units]
                total_p = sum(powers)
                # 总伤亡人数 = 沿线总兵力 × (loss_power/my_power)
                total_troops = sum(u.troops for u in front_units)
                total_cas = int(total_troops * (loss_power / my_power))
                assigned = 0
                # 主将部 = 战力最大的 unit（余数归它）
                main_idx = max(range(len(front_units)), key=lambda i: powers[i])
                for i, u in enumerate(front_units):
                    if i == main_idx:
                        continue
                    part = int(total_cas * (powers[i] / total_p)) if total_p > 0 else 0
                    part = min(part, u.troops)
                    u.add_troops(-part)
                    assigned += part
                rest = min(total_cas - assigned, front_units[main_idx].troops)
                front_units[main_idx].add_troops(-max(0, rest))
                casualty = assigned + max(0, rest)
            if breach:
                for line in ("北线_太原真定", "北线_陕西"):
                    if line in state.defense_lines:
                        f0 = state.defense_lines[line].get("fortification", 0)
                        state.defense_lines[line]["fortification"] = max(0, min(100, int(f0 * 0.5)))
            if win:
                log.append(f"[紧急] 金军大举南下！沿边诸军力战却敌，伤亡约{casualty}人")
            else:
                log.append(f"[紧急] 金军大举南下！沿边诸军败绩，防线告破，伤亡约{casualty}人")
            state._derive_defense_lines()

    if state.pleasure_leaning > 80 and random.random() < 0.05:
        state.emperor_health -= 3

    if state.emperor_health > 0 and random.random() < 0.02:
        state.emperor_health -= 1


