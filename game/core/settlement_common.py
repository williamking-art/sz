# -*- coding: utf-8 -*-
"""宋祚 · 结算共享守恒工具（从 settlement_steps.py 拆出，零行为变更）。

资金/人口守恒转移、粮贸配对、贪腐与粮价小工具、P1 档位常量。

**错误可观测性（审查 P2-3）**：本模块另提供三件结算侧公共设施，供各结算步共用，
避免每处各写一套（口径不一 → 有的静默、有的刷屏）：

  · `note_settlement_error`：结算异常统一留痕（玩家可见结算 WARN 行 ＋ 开发者日志
    ＋ 每回合去重），是"关键故障能从日志/界面区分定位"的唯一入口；
  · `register_money_flow`：货币台账登记（失败**必须**响亮可见，不得再伪装成残差）；
  · `MoneyChannelUnavailable`：状态写入通道不可用的**独立**信号（与"合法 0"区分）。
"""
from __future__ import annotations

import logging

# 🔴 方案乙 / G-3（2026-10-04）：POP 写入走桥接层 ——
#   · 粮写 `grain_bridge`（写只落一个载体，绝不双写）；
#   · size/wealth 写 `pop_bridge`（先落州府真账、再刷路级派生镜像）。
# 存量**读取**仍走路级 `pops`（桥接维护的镜像）。未下沉时桥接返回 None，调用方回落原写法。
from core.foundation.ledger.grain_bridge import grain_add as _grain_add
from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add

from content.data import (
    GRAIN_PRICE_MIN,
    GRAIN_PRICE_MAX,
)

_log = logging.getLogger("settlement")


class MoneyChannelUnavailable(RuntimeError):
    """公共资金 → 民间 POP 的**守恒转移通道**（`engine.state_applier`）不可用。

    存在这个独立异常类型的原因（审查 P2-3 应修）：原实现 import 失败时 `return 0`，
    与「国库不足 / 接收池缺失 → 合法 0」**同值**，调用方无法区分「真的一分没拨」
    与「写入通道坏了」。调用方必须显式选择策略（严格模式抛错、其余按 0 处理并留痕）。
    """


def note_settlement_error(state, key: str, tag: str, msg: str, log=None, exc=None,
                          logger=None, level: str = "warning") -> bool:
    """结算异常的统一留痕：**玩家可见**结算 WARN 行 ＋ **开发者**日志（含 traceback）。

    审查 P2-3 纪律：`log` 是结算日志列表（玩家/面板可见），`logging` 是服务端日志
    —— 需要"玩家可见"且"可定位"时必须**两者都要**，本函数一次做齐。

    去重（防噪声）：以 `(state.turn, key)` 为键，单回合内同一 key 只记一次
    （`_ext_econ_phases` 每月被 38 个政权各调一次，不去重会刷屏）。
    `key` 应取"步位 + 对象"粒度（如 `"clerks_backlog"`、`"era_links"`）。

    返回 True 表示本次确实记录了（供测试断言"正常路径不产生噪声"）。
    """
    turn = int(getattr(state, "turn", 0) or 0) if state is not None else 0
    _seen = getattr(state, "_settle_warned", None) if state is not None else None
    if not isinstance(_seen, dict) or _seen.get("_turn") != turn:
        _seen = {"_turn": turn}
        if state is not None:
            try:
                state._settle_warned = _seen
            except Exception:  # noqa: BLE001 — 诊断设施自身失败不得反噬结算
                _seen = None
    if isinstance(_seen, dict):
        if key in _seen:
            return False
        _seen[key] = str(msg)[:200]
    _lg = logger or _log
    if exc is not None:
        if level == "exception":
            _lg.exception("[%s] %s", tag, msg)
        else:
            _lg.warning("[%s] %s", tag, msg, exc_info=True)
    else:
        _lg.warning("[%s] %s", tag, msg)
    if isinstance(log, list):
        log.append(f"[{tag}][WARN] {msg}")
    return True


def register_money_flow(state, kind: str, amount: int, reason: str = "",
                        log=None, tag: str = "货币台账") -> bool:
    """登记一笔货币台账流水（`core/money.register_flow`）——**失败必须可见**。

    审查 P2-3 / M8：五处结算调用点原先一律 `except Exception: pass`（注释还写
    "不影响结算"，属误导）。后果不是"少记一笔"：`core/money.reconcile` 会把**未登记**
    的 M_ALL 变化算成**残差**，面板于是显示"⚠️ 残差 X 贯（存在无对手方的造币/销毁）"
    ——把**登记 bug 说成造币 bug**，把排查方向指向完全错误的地方。

    现口径：
      · 开发者：`logging.getLogger("settlement").warning("[货币台账] 登记失败 …", exc_info=True)`；
      · 玩家/面板：`state.money_audit["flow_errors"]` 累计（**不改** `core/money.py`
        的对账算法，只在既有 audit 视图里追加"台账登记曾失败"这一事实）；
      · 结算日志：可选（调用方给 `log` 时追加一行）。
    返回是否登记成功。
    """
    try:
        from core.foundation.ledger.money import register_flow as _reg_flow
        _reg_flow(state, kind, amount, reason)
        return True
    except Exception as e:  # noqa: BLE001 — 登记失败必须留痕，但不得中断资金主流程
        _log.warning("[货币台账] 登记失败 kind=%s amount=%s reason=%s",
                     kind, amount, reason, exc_info=True)
        audit = getattr(state, "money_audit", None)
        if not isinstance(audit, dict):
            audit = {}
            try:
                state.money_audit = audit
            except Exception:  # noqa: BLE001
                audit = None
        if isinstance(audit, dict):
            errs = audit.setdefault("flow_errors", [])
            if isinstance(errs, list):
                errs.append({"turn": int(getattr(state, "turn", 0) or 0), "kind": kind,
                             "amount": amount, "reason": reason, "error": repr(e)})
            audit["flow_error_count"] = int(audit.get("flow_error_count", 0)) + 1
        if isinstance(log, list):
            log.append(f"[{tag}][WARN] 登记失败 kind={kind} amount={amount}"
                       f"（对账残差可能被误报为造币，实为登记失败：{type(e).__name__}）")
        return False


def _state_grain_trade(state, grain_amt: int, direction: str, price: float, log, tag: str) -> tuple:
    """政府粮食交易的守恒配对（审查 P0：杜绝「国库灭钱/太仓凭空得粮」幻影对手）。

    direction='buy'（和籴/入中/平籴——政府买粮入仓）：
        太仓 +grain、国库 -钱；民间（各路农/士绅等存粮 POP）售粮得钱。
        民间存粮不足 → 少买（实际买入量封顶）。
    direction='sell'（平粜/平准粜——政府卖粮收钱）：
        太仓 -grain、国库 +钱；民间买粮付钱（按可支付财富封顶，避免扣成负）。
    钱、粮两组合计 ΣΔ==0（政府仓 ↔ 民间账户成对划转）。
    返回 (实际 grain 量, 实际钱额)；grain 与钱的价格换算用当前 price。
    """
    pools = []
    for _p in getattr(state, "prefectures", {}).values():
        pops = _p.get("pops") if isinstance(_p, dict) else None
        if not isinstance(pops, dict):
            continue
        for pk in ("农", "士绅", "工匠", "商人", "官僚", "兵"):
            pp = pops.get(pk)
            if isinstance(pp, dict):
                pools.append(pp)
    if not pools:
        return 0, 0
    p = max(float(price), 0.1)
    if direction == "buy":
        # 仓容上限：太仓 change_granary 有 cap 封顶，先按余量限购（防钱付了粮被 cap 吞）
        _room = max(0, int(getattr(state, "granary_cap", 1 << 30)) - int(getattr(state, "granary", 0) or 0))
        # 按民间存粮从多到少征购
        total = 0
        money_paid = 0
        remain = min(int(grain_amt), _room)
        # 审查修复（潜伏造币）：原实现先给民间全额记账、再用 max(0, …) 截断国库
        # → 一旦 caller 未保证 money_paid ≤ 国库（新增调用方或价格下限变动），
        # 差额即凭空产生。此处把「国库可付额」提前作为钱腿硬上限，与 _changping_trade 同规。
        _cash_cap = int(getattr(state, "treasury", 0) or 0)
        for pp in sorted(pools, key=lambda x: -int(x.get("grain", 0) or 0)):
            if remain <= 0 or money_paid >= _cash_cap:
                break
            avail = int(pp.get("grain", 0) or 0)
            take = min(remain, avail)
            if take <= 0:
                continue
            if int(take * p) > _cash_cap - money_paid:      # 国库不足则少买
                take = int((_cash_cap - money_paid) / p)
                if take <= 0:
                    break
            if _grain_add(pp, -take, state) is None:
                pp["grain"] = avail - take
            _pay = int(take * p)
            if _pop_obj_add(state, pp, "wealth", _pay) is None:
                pp["wealth"] = int(pp.get("wealth", 0) or 0) + _pay
            remain -= take
            total += take
            money_paid += _pay
        if total <= 0:
            return 0, 0
        state.change_granary(total)
        _treasury = getattr(state, "treasury", 0)
        state.treasury = max(0, _treasury - money_paid)
        log.append(f"[{tag}] 民间籴粮入仓 {total}石，散钱 {money_paid}贯与民")
        return total, money_paid
    # sell：按民间财富摊售（有钱才买得起；实际卖出量受民间可支付力限制）
    total = 0
    money_in = 0
    want = int(grain_amt)
    _buyers = [pp for pp in pools if int(pp.get("wealth", 0) or 0) > 0]
    if not _buyers:
        return 0, 0
    _total_w = sum(int(x.get("wealth", 0) or 0) for x in _buyers)
    for pp in _buyers:
        if want <= 0:
            break
        _share = min(1.0, (int(pp.get("wealth", 0) or 0)) / max(_total_w, 1))
        _alloc = min(want, int(grain_amt * _share))
        # 支付能力校验：买 _alloc 石需 _alloc*p 钱，不够则少买
        _can_afford = int((int(pp.get("wealth", 0) or 0)) // p)
        _alloc = min(_alloc, _can_afford)
        if _alloc <= 0:
            continue
        _cost = int(_alloc * p)
        if _pop_obj_add(state, pp, "wealth", -_cost) is None:
            pp["wealth"] = int(pp.get("wealth", 0) or 0) - _cost
        if _grain_add(pp, _alloc, state) is None:
            pp["grain"] = int(pp.get("grain", 0) or 0) + _alloc
        total += _alloc
        money_in += _cost
        want -= _alloc
    if total <= 0:
        return 0, 0
    state.change_granary(-total)
    state.treasury = getattr(state, "treasury", 0) + money_in
    log.append(f"[{tag}] 官仓粜粮 {total}石，回收 {money_in}贯")
    return total, money_in


def _changping_trade(pref, name, grain_amt, direction, price, log, tag, state=None):
    """州县常平仓粜籴的守恒配对（与 _state_grain_trade 同构；钱腿为本路府库）。

    审查修复背景：常平仓原实现只动 `changping_stock` / `local_treasury` 两个
    政府侧账户 —— 平粜放出的粮无买家（粮凭空消失）、回收的钱无付款方（钱凭空
    产生）；平籴买入的粮无卖家（粮凭空产生）、付出的钱无收款方（钱凭空消失）。
    现改为与本路民间 POP 成对划转，两侧合计 ΣΔ==0：

      direction='buy'（平籴·政府买粮入仓）：
          常平仓 +grain、本路府库 -钱；存粮 POP 售粮得钱。
          受「府库可付额」与「民间可售粮」双重封顶。
      direction='sell'（平粜·政府卖粮收钱）：
          常平仓 -grain、本路府库 +钱；有钱 POP 买粮付钱（按可支付力封顶）。

    返回 (实际粮量, 实际钱额)；两者皆 0 表示本次未成交易（调用方不应记动作）。
    """
    pools = []
    pops = pref.get("pops") if isinstance(pref, dict) else None
    if isinstance(pops, dict):
        for pk in ("农", "士绅", "工匠", "商人", "官僚", "兵"):
            pp = pops.get(pk)
            if isinstance(pp, dict):
                pools.append(pp)
    if not pools:
        return 0, 0
    _price = max(float(price), 0.1)

    if direction == "buy":
        _pay_cap = int(pref.get("local_treasury", 0) or 0)
        total = 0
        money = 0
        remain = int(grain_amt)
        for pp in sorted(pools, key=lambda x: -int(x.get("grain", 0) or 0)):
            if remain <= 0 or money >= _pay_cap:
                break
            avail = int(pp.get("grain", 0) or 0)
            take = min(remain, avail)
            _pay = int(take * _price)
            if _pay > _pay_cap - money:                     # 府库不足则少买
                take = int((_pay_cap - money) / _price)
                _pay = int(take * _price)
            if take <= 0:
                continue
            if _grain_add(pp, -take, state) is None:
                pp["grain"] = avail - take
            if _pop_obj_add(state, pp, "wealth", _pay) is None:
                pp["wealth"] = int(pp.get("wealth", 0) or 0) + _pay
            remain -= take
            total += take
            money += _pay
        if total <= 0:
            return 0, 0
        pref["changping_stock"] = int(pref.get("changping_stock", 0) or 0) + total
        pref["local_treasury"] = _pay_cap - money
        log.append(f"[{tag}] {name}平籴入常平 {total}石，散钱 {money}贯与民")
        return total, money

    total = 0
    money = 0
    want = int(grain_amt)
    _buyers = [pp for pp in pools if int(pp.get("wealth", 0) or 0) > 0]
    if not _buyers:
        return 0, 0
    _tw = sum(int(x.get("wealth", 0) or 0) for x in _buyers)
    for pp in _buyers:
        if want <= 0:
            break
        _share = min(1.0, int(pp.get("wealth", 0) or 0) / max(_tw, 1))
        _alloc = min(want, int(grain_amt * _share))
        _alloc = min(_alloc, int(int(pp.get("wealth", 0) or 0) // _price))   # 买得起才买
        if _alloc <= 0:
            continue
        _cost = int(_alloc * _price)
        if _pop_obj_add(state, pp, "wealth", -_cost) is None:
            pp["wealth"] = int(pp.get("wealth", 0) or 0) - _cost
        if _grain_add(pp, _alloc, state) is None:
            pp["grain"] = int(pp.get("grain", 0) or 0) + _alloc
        total += _alloc
        money += _cost
        want -= _alloc
    if total <= 0:
        return 0, 0
    pref["changping_stock"] = max(0, int(pref.get("changping_stock", 0) or 0) - total)
    pref["local_treasury"] = int(pref.get("local_treasury", 0) or 0) + money
    log.append(f"[{tag}] {name}常平粜粮 {total}石，回收 {money}贯入府库")
    return total, money


def _levy_men(state, road: str, need: int) -> int:
    """自本路农户、其次流民中征补兵员（人守恒：农/流民 → 兵）。

    审查配套：诏令/事件的整军增兵若只 add_troops，则在 _settle_finance 以
    Σbranches 重聚合兵 POP、并把 ΣPOP 写回 population 之后，会表现为「凭空
    产生人口」（实测量级可达数万）。故增兵须有来源，且不足时按实有截断
    —— 宁少征，不造人。返回实际征得人数。
    """
    if need <= 0:
        return 0
    p = getattr(state, "prefectures", {}).get(road)
    if not isinstance(p, dict):
        return 0
    got = 0
    pops = p.get("pops") or {}
    farmer = pops.get("农") if isinstance(pops, dict) else None
    if isinstance(farmer, dict):
        take = min(need, int(farmer.get("size", 0) or 0))
        if take > 0:
            farmer["size"] = int(farmer.get("size", 0) or 0) - take
            got += take
    if got < need:                                   # 农户不足 → 再征流民
        ref = int(p.get("refugees", 0) or 0)
        take = min(need - got, ref)
        if take > 0:
            p["refugees"] = ref - take
            got += take
    return got


def _return_men(state, road: str, n: int) -> int:
    """裁汰兵力回流本路农户（人守恒：兵 → 农）；无农户时归流民池。

    与 _levy_men 对称：凡减少兵额（裁汰/整编）都应把人丁送回民户，
    否则 _settle_finance 以 Σbranches 重聚合兵 POP 时表现为人口凭空消失。
    """
    if n <= 0:
        return 0
    p = getattr(state, "prefectures", {}).get(road)
    if not isinstance(p, dict):
        return 0
    pops = p.get("pops") or {}
    farmer = pops.get("农") if isinstance(pops, dict) else None
    if isinstance(farmer, dict):
        farmer["size"] = int(farmer.get("size", 0) or 0) + n
    else:
        p["refugees"] = int(p.get("refugees", 0) or 0) + n
    return n


def _collect_from_pops(state, amount: int) -> int:
    """按人口比例向六类 POP 征收 `amount` 贯（买家支付），返回**实收**额。

    用途：把"产出型/外部型入账"改为**守恒转移**——POP 挂载律要求"凡钱必须落在
    POP wealth 或国库/内帑，且来源=去向"。用于修复审查 A-4（畜栏产肉原
    `imperial_treasury += 收入` 无买方 → 凭空造币）。

    语义：按 POP `size` 比例分摊；某池 wealth 不足时**按实收计，不补差额**——
    宁可少收，也绝不凭空造币。两轮征收（第二轮补齐首轮 int 截断余额）以保证
    在余额充足时能收满 `amount`，从而使"扣减额 == 入账额"精确成立。
    """
    amount = int(amount or 0)
    if amount <= 0:
        return 0
    pools = [(pp, float(pp.get("size", 0) or 0))
             for p in state.prefectures.values()
             for pp in (p.get("pops") or {}).values()]
    total_size = sum(sz for _, sz in pools) or 1.0
    taken = 0
    remaining = amount
    for pp, size in pools:                      # 第一轮：按人口比例
        if remaining <= 0:
            break
        if size <= 0:
            continue
        want = min(int(amount * size / total_size), remaining)
        avail = int(pp.get("wealth", 0) or 0)
        got = min(want, avail)
        if got > 0:
            pp["wealth"] = avail - got
            taken += got
            remaining -= got
    for pp, _sz in pools:                       # 第二轮：补齐 int 截断余额
        if remaining <= 0:
            break
        avail = int(pp.get("wealth", 0) or 0)
        got = min(remaining, avail)
        if got > 0:
            pp["wealth"] = avail - got
            taken += got
            remaining -= got
    return taken


def distribute_cash(state, amount: int, shares: dict, applied: list = None) -> int:
    """把 `amount` 贯按 `shares` {阶层: 占比} 精确分发给各路该阶层 POP wealth。

    第十三包（2026-10-07）由 `_distribute_cash` 提升为显式接口：`focus_mechanic` 等
    **非结算模块**也要用它，按 §6 规则 2 不该借用私有符号、更不该绕道结算编排器再导出。

    末位（最后一个阶层 × 最后一支池）吃尾差，保证 **Σ入账 == amount**（精确守恒），
    从而与 `state.change_treasury(-paid)` 构成 `ΣΔ==0` 的守恒转移。
    返回实际分发额。

    ⚠️ **尾差口径：末位（最后一个阶层 × 最后一支池）吃尾差** —— 与
    `settlement_econ_helpers._distribute_pop_wealth`（**尾差归最大府**）不同；
    二者语义确有差异，**不可盲目合并**（2026-09-27 审查 §8.2-#8）。

    **原子性（审查 P2-3 / M3）**：本函数直接写各 POP `wealth`，**不走** `state_applier`
    事务。原实现边算边写 —— 中途抛错时先写进去的那些 POP 留下、调用方却按"分发 0"
    全额退款，净效果 = 国库不减而民间多钱（ΣΔ>0，凭空造币）。现改为**两阶段**：
    `① 构造`（含所有数值解析：size / wealth 取整）→ `② 一次性写入`。任何异常都发生在
    ①，此时**零写入**，与"实际分发额=0"自洽。

    `applied`（可选 list）：把**实际已入账额**逐笔追加其中。调用方在异常后据此计算
    退款额（**退款额必须用实际已分发额**，不得按请求额全退）——即便将来有人把本函数
    改回非原子写法，调用方的守恒也不破。
    """
    amount = int(amount or 0)
    if amount <= 0:
        return 0
    roads = list(state.prefectures.values())
    items = [(c, float(s)) for c, s in (shares or {}).items()]
    paid = 0
    writes = []                      # [(pop_dict, 新 wealth, 本次入账额)]
    for i, (cls, share) in enumerate(items):
        want = (amount - paid) if i == len(items) - 1 else int(amount * share)
        if want <= 0:
            continue
        pools = [(_p.get("pops") or {}).get(cls) for _p in roads]
        pools = [x for x in pools if isinstance(x, dict)]
        if not pools:
            continue
        _tot = sum(float(x.get("size", 0) or 0) for x in pools) or 1.0
        given = 0
        for j, x in enumerate(pools):
            g = (want - given) if j == len(pools) - 1 else int(
                want * float(x.get("size", 0) or 0) / _tot)
            g = max(0, int(g))
            _cur = int(x.get("wealth", 0) or 0)      # 解析在阶段①：坏值 → 零写入
            writes.append((x, _cur + g, g))
            given += g
        paid += given
    for x, _new, g in writes:                        # 阶段②：纯赋值，不再可能抛错
        if _pop_obj_add(state, x, "wealth", _new - int(x.get("wealth", 0) or 0)) is None:
            x["wealth"] = _new
        if applied is not None:
            applied.append(g)
    return paid

# 兼容别名（旧私有名）。`core/settlement_steps.py` 的再导出面与既有调用仍用旧名，
# 公开面守恒优先于好看；新代码请用 `distribute_cash`。
_distribute_cash = distribute_cash


def transfer_public_funds_to_pops(state, amount: int, shares: dict, reason: str,
                                  source_account: str = "treasury",
                                  raise_on_unavailable: bool = False) -> int:
    """公共资金（国库/内帑）→ 民间 POP wealth 的**守恒转移**（走 applier_pipeline）。

    用于研发经费、工程款等**新增支出通道**：批量事务 + 路径白名单 + ΣΔ==0 + 原子回滚，
    绝不绕开另起第三套写状态通道（engine/state_applier 铁律）。

    口径：
      · 国库/内帑不足 → 按实付（返回 < amount，调用方须据实记录，不得静默成功）；
      · 接收方池缺失 → 余额退回，仅划转实到部分；
      · 守恒/穿底/落点非法 → applier 整批拒绝 → 返回 0（可诊断，不假装已付）。

    **通道不可用（P2-3 应修）**：`engine.state_applier` 取不到时，原实现 `return 0`
    —— 与上面那几种**合法 0** 同值，调用方无从区分"真没拨"与"写入通道坏了"。
    现由 `raise_on_unavailable` 显式选择：授权范围内的调用方传 True 并捕获
    `MoneyChannelUnavailable` 自行区分；范围外调用方保持旧行为（不擅自改变其语义）。

    ⚠️ 本函数是**第三处**"公共资金 → POP"通道（另两处：`distribute_cash` 末位吃尾差、
    `settlement_econ_helpers._distribute_pop_wealth` 尾差归最大府）；三者的**分摊与尾差处理
    各不相同**，2026-09-27 审查确认**不可盲目合并**（§8.2-#8）。
    """
    amount = int(amount or 0)
    avail = max(0, int(getattr(state, source_account, 0) or 0))
    amount = min(amount, avail)
    if amount <= 0:
        return 0
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict) or not prefs:
        return 0
    roads = [r for r, p in prefs.items() if isinstance(p, dict)]
    if not roads:
        return 0
    changes = [{"path": source_account, "op": "add", "value": -amount,
                "reason": reason, "source_agent": "settlement"}]
    items = [(c, float(s)) for c, s in (shares or {}).items() if float(s) > 0]
    allocated = 0
    for i, (cls, share) in enumerate(items):
        want = (amount - allocated) if i == len(items) - 1 else int(amount * share)
        if want <= 0:
            continue
        pools = [r for r in roads
                 if isinstance((prefs[r].get("pops") or {}).get(cls), dict)]
        if not pools:
            continue
        given = 0
        for j, r in enumerate(pools):
            v = (want - given) if j == len(pools) - 1 else int(want / len(pools))
            if v <= 0:
                continue
            changes.append({"path": f"prefectures.{r}.pops.{cls}.wealth",
                            "op": "add", "value": v,
                            "reason": reason, "source_agent": "settlement"})
            given += v
        allocated += given
    if allocated <= 0:
        return 0
    changes[0]["value"] = -allocated
    try:
        from engine.state_applier import applier_pipeline
    except Exception as e:  # noqa: BLE001
        # 通道不可用 ≠ 拨了 0：默认（范围外调用方）仍返回 0 但**留 WARNING**；
        # 授权范围内的调用方传 raise_on_unavailable=True 以区分（见 docstring）。
        _log.warning("[公共资金→POP] 状态写入通道不可用（source=%s reason=%s，"
                     "本次按 0 处理，与「国库不足」不可区分）", source_account, reason,
                     exc_info=True)
        if raise_on_unavailable:
            raise MoneyChannelUnavailable(
                f"engine.state_applier 不可用（{type(e).__name__}）："
                f"公共资金→POP 转移无法执行（reason={reason}）") from e
        return 0
    res = applier_pipeline(state, [("settlement", changes)])
    if not (res.get("applied") or []):
        return 0
    return allocated


_TA = 5 / 3.0          # 大 → 巨 倍率（2.0/1.5）


_TB = 5 / 2.0          # 大 → 极 倍率（2.5/1.5）


def _tier7(v_tiny: int, v_small: int, v_mid: int, v_big: int,
           cap: int = None) -> dict:
    """构造七档换算表（无/微/小/中/大/巨/极）。

    巨/极由大档按 content.data.TIER_RANGE 比例外推；若给出 cap，则一律受其钳制
    （外交 attitude 原 CAP 8、兵额原 CAP 5 万不得因补档而被越过）。
    """
    big_j = int(v_big * _TA)
    big_k = int(v_big * _TB)
    if cap is not None:
        big_j = min(big_j, cap)
        big_k = min(big_k, cap)
    return {"无": 0, "微": v_tiny, "小": v_small, "中": v_mid, "大": v_big,
            "巨": big_j, "极": big_k}


_P1_ATT_DELTA = _tier7(3, 5, 6, 8, cap=8)      # 外交 attitude ±3~±8（CAP 8）


_P1_ARM_DELTA = _tier7(10000, 20000, 35000, 50000, cap=50000)   # 兵额 ±1万~±5万（CAP 5万）


_P1_TRAIN_DELTA = _tier7(2, 3, 5, 6)           # 训练/士气 ±2~±6


_P1_LEVY_COST = _tier7(100000, 200000, 350000, 500000)  # 征发 cost 10万~50万


_P1_RELIEF = _tier7(100000, 200000, 350000, 500000)     # 赈济 10万~50万石


_P1_REFUGEE = _tier7(50000, 120000, 200000, 300000)     # 流民 ±5万~±30万


def _avg_corruption(state):
    """全国理财主官平均贪腐度（后台隐藏，仅影响数值，绝不进 UI 文本）。"""
    names = []
    for org_key in ("户部",):
        o = state.central_orgs.get(org_key)
        if o and o.get("lead"):
            names.append(o["lead"])
    if not names:
        return 0.0
    vals = [state.corruption.get(n, 0.0) for n in names]
    return sum(vals) / len(vals)


#: 单路每月逃籍/逃荒的**爆版保护上限**（口）。用户 2026-10-01 定稿：逃籍人数由
#: 「无法吃粮人数」1:1 派生，此上限**仅作爆版保护、非驱动项**（吃饱了就不会逃，
#: 不靠比例魔数）。沿用既有饥荒逃荒通道的同名上限，避免两处各立一个数。
FLEE_CAP_PER_ROUTE = 50_000


def food_insecure_headcount(pops: dict, price: float) -> dict:
    """各类 POP 中**吃不上饭的人数**（口）——"无法吃粮"的**唯一口径**。

    口径（用户 2026-10-01 定稿）：
      · 先算该类 POP 的**月口粮需求** = `size × GRAIN_CONSUME_PER_CAPITA[类]`（石）；
      · 可支配粮 = **自有粮 ＋ 购粮能力**，其中购粮能力 = `wealth / 粮价`（石）——
        即"钱能买到多少粮"。购粮通道已落地且钱粮守恒（`_changping_trade` /
        `_state_grain_trade` / 士绅售粮），故**买得到就不算饿**；
      · 吃不上饭的人数 = `size − 可支配粮 / 人均需求`（向下取整，不为负）。

    返回：`{"农": n, "工匠": n, …, "total": n}`；`pops` 非 dict 或价格非正时返回全 0
    （**读数缺失不当饿**：不拿"价格未知"当"买不起"，也不拿它凭空造饥荒）。

    为什么要单点：逃籍（`settlement_imperial`）与饥荒逃农（`settlement_granary`）
    两处都依赖"谁吃不上饭"，**必须同源**——否则一处按公储、一处按户存，
    会出现"没饿却在逃籍"或"饿着却不逃"的矛盾（硬约束 #2 口径单点）。
    """
    from content.data import GRAIN_CONSUME_PER_CAPITA
    out = {}
    if not isinstance(pops, dict):
        return out
    _price = float(price)
    if not (_price > 0) or _price != _price or _price == float("inf"):
        return out
    total = 0
    for cls, slot in pops.items():
        if not isinstance(slot, dict):
            continue
        size = int(slot.get("size", 0) or 0)
        if size <= 0:
            out[cls] = 0
            continue
        per = float(GRAIN_CONSUME_PER_CAPITA.get(cls, 0.5))
        if per <= 0:
            out[cls] = 0
            continue
        own = max(0.0, float(slot.get("grain", 0) or 0))
        wealth = max(0.0, float(slot.get("wealth", 0) or 0))
        buyable = wealth / _price                      # 钱能买到的粮（石）
        fed = int((own + buyable) // per)              # 吃得上饭的人数
        hungry = max(0, size - fed)
        out[cls] = hungry
        total += hungry
    out["total"] = total
    return out


def _recalc_region_price(state, name: str, extra_supply: float = 0.0) -> float:
    """按当月供需（年成月均 + 常平净粮流）重算当地粮价（贯/石）。

    价格体系内部允许"文"级精度（1 贯 = 1000 文，即 0.001 贯），
    仅用于价格推导与折银换算；国库/地方府库记账仍为整数贯。
    """
    from content.data import PER_CAPITA_MONTH_GRAIN
    p = state.prefectures.get(name)
    if not p:
        return state.grain_price
    need = p.get("population", 0) * PER_CAPITA_MONTH_GRAIN          # 月需求（石）
    supply = max(p.get("grain", 0) / 12.0 + extra_supply, 0.01)     # 月供应（石）
    ratio = max(0.5, min(2.0, need / supply))
    return max(GRAIN_PRICE_MIN, min(GRAIN_PRICE_MAX, state.grain_price * ratio))


