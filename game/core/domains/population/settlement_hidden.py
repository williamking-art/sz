# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import random

from content.data_constants import PERSONS_PER_HOUSEHOLD

from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add

_log = logging.getLogger('settlement')

def _hidden_people(p) -> int:
    """
宋祚 · 隐户（隐藏人口）动态结算。

> 由 core/settlement_imperial.py 按域拆出（2026-10-07 用户裁定「拆开」）。
> 归 population 域：只管隐户口数（农 POP 的 hidden 加法子池）与归籍，
> 不含帝王行动、不含金军南侵战役。

隐户口数 = 农 POP 的加法子池 hidden（POP 挂载律条 1/4），不是第 7 类人口池。
某路隐户**口数**（`农` POP 的加法子池 `hidden`；缺键视为 0）。"""
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
