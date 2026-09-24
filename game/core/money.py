# -*- coding: utf-8 -*-
"""宋祚 · 货币口径（M0/M1/M2/M3）与月度对账 —— **只读视图**。

依据：`_dev_tools/game-docs/docs/货币口径规范_M0M1M2.md`
（§二 账户表 / §三 分层定义 / §四 会计恒等式 / §十二 封桩与仓鼠症）。

## 纪律（POP 挂载律，见 游戏机制说明.md §五）

1. 本模块**只读**状态，**绝不写任何货币账户**——权威源始终是
   `pops[阶层].wealth` 与国库 / 内帑 / 地方府库。
2. 唯一新增字段是 `state.silver_stock`（海外白银**存量**，贯），用于修复
   "把流量当存量"：原先 `maritime.silver_in`（万两/**年**）被 `calc_price_level`
   直接当作白银存量 ×10000 使用，而它从未进入任何持有账户。
3. 不得新增与 POP 平行的独立存量账本。

## 分层

    M0  流通中通货 = 民间铜钱（按 copper_share 拆分）＋ 有效交子
    M1  狭义货币   = M0 ＋ 政府即付资金（国库＋内帑＋地方府库）
         · `m1_full`    ：全额计入（旧口径，便于对比）
         · `m1_working` ：仅计"周转金"（k×月常费），其余视为**封桩**沉淀（§12.2）
    M2  广义货币   = M1 ＋ 沉淀层（士绅窖银 ＋ 熔铜池 ＋ 银行准备金）
    M3  全社会     = M2 ＋ 白银存量 ＋ 交子本钱
         · **不含 bank["capital"]**（P0-4：capital 与 reserve 同源双计会虚增 M3；
           capital 为 legacy 展示字段，真实银行钱在 reserve，已由 M2 计入）
    M_ALL 会计全集 = 全部持有主体之和（见 `ACCOUNTS`）

## 刻意**不计入** M_ALL 的项（避免重复计算 / 非实际持有）

| 字段 | 不计入的理由 |
|---|---|
| `jiaozi["issued"]` | 交子是**发行方负债**，其价值已包含在持有者（POP/国库）的 wealth 里；同时计入会双重计算。见规范 §4.3 |
| `jiaozi["reserve"]` | "本钱准备"是**名义常量**，代码中从无实际划转（只被 `_jiaozi_ceiling` 读取），非独立持有的资金 |
| `bank["capital"]` | 语义混乱（注释标"万贯"，但 `:1038` 按 `×1.2` 乘数式改动，且 `BANK_INFO` 初值 0）——**待裁定**，故仅列入 M3 并显式标注换算 |

## 月度对账

`audit_step(state)` 在每月结算末尾调用：把本月各账户余额与上月末对比，产出

    ΔM_ALL  ＝ 外部净注入（本月白银流入）− 真实销毁 ＋ 残差

**残差 ≠ 0 即表示存在无对手方的造币/销毁。** 这正是审查中
A-2（穿底造币）/ A-4（畜栏产肉无买方）/ A-5（酒课无上限累加）/ D-6（常费转负）
能够长期存活的根本原因——**此前游戏没有货币总量口径，无处可查**。
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

__all__ = [
    "ACCOUNTS", "SINK_ACCOUNTS", "EXTERNAL_ACCOUNTS",
    "pop_money", "hoard_money", "local_treasury_total", "effective_jiaozi", "copper_share",
    "m0", "m1", "m2", "m3", "m_all",
    "snapshot", "reconcile", "audit_step", "describe_residual",
    "register_flow", "take_flow",
    # ---- 金融口径只读视图（第二节§1/§2/§3/§5；第六节数据契约）----
    "jiaozi_issued", "jiaozi_circulating", "jiaozi_reserve", "jiaozi_redeem_rate",
    "jiaozi_discount", "jiaozi_run_pressure", "jiaozi_view",
    "bank_view", "bank_capital_as_guan",
    "standard_rates", "exchange_quote",
    "circulating_copper", "circulating_jiaozi", "circulating_silver",
    "effective_money_supply", "supply_breakdown", "assert_supply_no_double_count",
    "finance_report",
]

# 计入 M_ALL 的账户（顺序即展示顺序）
ACCOUNTS: Tuple[str, ...] = (
    "pop_wealth",        # Σ 六类 POP wealth（民间持钱，含其持有的交子）
    "estate_wealth",     # Σ 大臣家产 wealth（官僚私人持钱；**待迁移到 POP**，见下注）
    "treasury",          # 国库
    "imperial",          # 内帑
    "local_treasury",    # Σ 各路地方府库
    "payraise_budget",   # 加俸预算池（由国库拨入、随后发放给官僚/吏）
    "invest_principal",  # 未到期投资本金（由国库/内帑拨出、尚在"体外"）
    "hoard",             # Σ 士绅窖银（退出流通）
    "estate_hoard",      # Σ 大臣家产窖藏（退出流通；修复 D-11 后新增）
    "melt_pool",         # 熔铜池（钱→铜料，退出流通）
    "bank_reserve",      # 银行准备金
    "silver_stock",      # 海外白银存量（外部注入的唯一合法入口）
)

# ⚠️ POP 挂载律违规记录（2026-09-18 阶段 B-2）
# `estate_wealth` / `estate_hoard` 对应 `state.minister_estate[*]`，它是**与 POP 平行的
# 独立钱账本**，违反 POP 挂载律律条 4（"禁止任何与 POP 平行的独立存量账本"）。
# 正确归宿：挂到 `官僚`（及 `士绅`）POP 的子池上。
# 现阶段先把它**纳入货币口径**（否则它一进一出都会污染对账残差），
# 迁移到 POP 的工作排入批次 C（官制完善），届时本注与两个账户一并移除。

# 真实销毁通道（真正让货币退出 M_ALL 的机制）
SINK_ACCOUNTS: Tuple[str, ...] = ()   # step 1 暂空；换界销毁/铜料离库在 step 2 接入

# 白银流入以外的外部注入通道（step 1 仅白银）
EXTERNAL_ACCOUNTS: Tuple[str, ...] = ("silver_stock",)


# --------------------------------------------------------------------------
# 外部注入 / 真实销毁 台账（规范 §4.2 的"外部净注入"与"真实销毁"两项）
# --------------------------------------------------------------------------
# 说明：这是**流水台账**（记本月发生了多少外部注入/销毁），**不是货币账户**，
# 因此不违反 POP 挂载律（律条禁的是与 POP 平行的"存量账本"）。
# 用途：把**合法**的体外出入口从对账残差里扣除，使残差只剩下真正的漏洞。
_FLOW_KEY = "_money_flow_month"


def _flow(state) -> Dict[str, Any]:
    f = getattr(state, _FLOW_KEY, None)
    if not isinstance(f, dict):
        f = {"external_in": 0, "burned": 0, "notes": []}
        setattr(state, _FLOW_KEY, f)
    return f


def register_flow(state, kind: str, amount: int, reason: str = "") -> int:
    """登记一笔**外部注入**（kind="external"）或**真实销毁**（kind="burn"）。

    只登记台账，**不移动任何账户**——资金的实际移动由调用方完成（守恒仍由调用方保证）。
    本函数的作用是告诉对账层："这笔 M_ALL 变化是体外进出，不算残差"。

    仅用于**可验证**的体外通道，例如：
      · external：存货外销变现（goods 出、外部钱入）、海外白银流入
      · burn：岁币岁赐外流（钱付与辽/西夏）、交子换界销毁、铜料离库
    """
    amount = int(amount or 0)
    if amount <= 0:
        return 0
    f = _flow(state)
    if kind == "external":
        f["external_in"] = int(f.get("external_in", 0)) + amount
    elif kind == "burn":
        f["burned"] = int(f.get("burned", 0)) + amount
    else:
        raise ValueError(f"register_flow: 未知 kind {kind!r}（应为 'external' 或 'burn'）")
    if reason:
        f.setdefault("notes", []).append(f"{reason}:{amount:+,}")
    return amount


def take_flow(state) -> Dict[str, Any]:
    """读取并**清零**本月台账（由 `audit_step` 每月末调用一次）。"""
    f = _flow(state)
    out = {"external_in": int(f.get("external_in", 0)),
           "burned": int(f.get("burned", 0)),
           "notes": list(f.get("notes", []))}
    setattr(state, _FLOW_KEY, {"external_in": 0, "burned": 0, "notes": []})
    return out


# --------------------------------------------------------------------------
# 账户读数（全部只读）
# --------------------------------------------------------------------------
def pop_money(state) -> float:
    """Σ 六类 POP wealth（民间持钱；交子已含在持有者 wealth 中）。"""
    total = 0.0
    for p in getattr(state, "prefectures", {}).values():
        for pp in (p.get("pops") or {}).values():
            total += float(pp.get("wealth", 0) or 0)
    return total


def hoard_money(state) -> float:
    """Σ 士绅窖银（贯）——退出流通，计入 M2 沉淀层。"""
    total = 0.0
    for p in getattr(state, "prefectures", {}).values():
        g = (p.get("pops") or {}).get("士绅") or {}
        total += float(g.get("窖银", 0) or 0)
    return total


def local_treasury_total(state) -> float:
    """Σ 各路地方府库（贯）——能即付，计入 M1。"""
    return float(sum((p.get("local_treasury", 0) or 0)
                     for p in getattr(state, "prefectures", {}).values()))


def estate_wealth(state) -> float:
    """Σ 大臣家产 wealth（贯）。**待迁移到 POP**（POP 挂载律违规项，见 ACCOUNTS 注）。"""
    me = getattr(state, "minister_estate", None)
    if not isinstance(me, dict):
        return 0.0
    return float(sum(int((v or {}).get("wealth", 0) or 0)
                     for v in me.values() if isinstance(v, dict)))


def estate_hoard(state) -> float:
    """Σ 大臣家产窖藏（贯）——退出流通，计入 M2 沉淀层（修复 D-11 后新增的对手账户）。"""
    me = getattr(state, "minister_estate", None)
    if not isinstance(me, dict):
        return 0.0
    return float(sum(int((v or {}).get("窖银", 0) or 0)
                     for v in me.values() if isinstance(v, dict)))


def payraise_budget_total(state) -> float:
    """加俸预算池余额（贯）——国库已拨出、尚未发放，仍属政府持有（M1）。"""
    return float(getattr(state, "payraise_budget", 0) or 0)


def invest_principal_total(state) -> float:
    """未到期投资本金（贯）——国库/内帑已拨出、尚在体外，故必须计账。"""
    inv = getattr(state, "investments", None)
    if not isinstance(inv, dict):
        return 0.0
    total = 0.0
    for v in inv.values():
        if isinstance(v, dict) and int(v.get("months_left", 0) or 0) > 0:
            total += float(int(v.get("amount", 0) or 0))
    return total


def effective_jiaozi(state) -> float:
    """有效交子 = 发行面值 × 接受度（trust/100）。"""
    jz = getattr(state, "jiaozi", {}) or {}
    trust = float(jz.get("trust", 0) or 0)
    return float(jz.get("issued", 0) or 0) * max(0.0, min(1.0, trust / 100.0))


def copper_share(state) -> float:
    """铜钱在"民间+政府"持钱中的占比（沿用既有权重算法，见 settlement_steps 窖银分配段）。"""
    jz_eff = effective_jiaozi(state)
    base = jz_eff + pop_money(state) + max(0.0, float(getattr(state, "treasury", 0) or 0)) \
        + max(0.0, float(getattr(state, "imperial_treasury", 0) or 0))
    if base <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - jz_eff / base))


def _silver_stock(state) -> float:
    return float(getattr(state, "silver_stock", 0) or 0)


def _bank_capital_as_guan(state) -> float:
    """银行资本**万贯 → 贯**（注释标"万贯"；换算在此显式化，避免又一处 10000× 黑洞）。"""
    cap = float((getattr(state, "bank", {}) or {}).get("capital", 0) or 0)
    return cap * 10000.0


# --------------------------------------------------------------------------
# 分层
# --------------------------------------------------------------------------
def m0(state) -> float:
    """流通中通货 = 民间铜钱（含大臣家产持钱）＋ 有效交子。"""
    return (pop_money(state) + estate_wealth(state)) * copper_share(state) \
        + effective_jiaozi(state)


def m1(state, working_only: bool = False, months_of_base: float = 3.0) -> float:
    """狭义货币 = M0 ＋ 政府即付资金（国库＋内帑＋地方府库＋加俸预算）。

    working_only=True 时国库/内帑只计"周转金"（`months_of_base` × 月常费），
    超出部分视为**封桩**（沉淀层，归 M2）——对应规范 §12.2 的仓鼠症处理。
    """
    g = m0(state)
    base = float(getattr(state, "treasury", 0) or 0)
    imp = float(getattr(state, "imperial_treasury", 0) or 0)
    if working_only:
        from content.data import MONTHLY_EXP_CIVIL_BASE
        cap = months_of_base * float(MONTHLY_EXP_CIVIL_BASE)
        base = min(base, cap)
        imp = min(imp, cap / 3.0)     # 内帑本职"死钱"，周转口径更紧（§12.2 建议 k_内≈1）
    return (g + base + imp + local_treasury_total(state)
            + payraise_budget_total(state) + invest_principal_total(state))


def m2(state, working_only: bool = False) -> float:
    """广义货币 = M1 ＋ 沉淀层（士绅窖银 ＋ 大臣家产窖藏 ＋ 熔铜池 ＋ 银行准备金）。"""
    coin = getattr(state, "coin", {}) or {}
    bank = getattr(state, "bank", {}) or {}
    return (m1(state, working_only=working_only)
            + hoard_money(state)
            + estate_hoard(state)
            + float(coin.get("melted_pool", 0) or 0)
            + float(bank.get("reserve", 0) or 0))


def m3(state, working_only: bool = False) -> float:
    """全社会货币资产 = M2 ＋ 白银存量 ＋ 交子本钱。

    **P0-4**：不再加 `_bank_capital_as_guan`——bank.capital 与 bank.reserve 是同一笔
    准备金的两种记法（establish_bank 曾同时入账），reserve 已在 M2，再加 capital 即双计。
    capital 仅作 legacy 展示（万贯），不入货币分层。
    """
    jz = getattr(state, "jiaozi", {}) or {}
    return (m2(state, working_only=working_only)
            + _silver_stock(state)
            + float(jz.get("reserve", 0) or 0))


def m_all(state) -> float:
    """会计全集 = 全部**计入**账户之和（见模块头"刻意不计入"表）。"""
    coin = getattr(state, "coin", {}) or {}
    bank = getattr(state, "bank", {}) or {}
    return (pop_money(state)
            + estate_wealth(state)
            + float(getattr(state, "treasury", 0) or 0)
            + float(getattr(state, "imperial_treasury", 0) or 0)
            + local_treasury_total(state)
            + payraise_budget_total(state)
            + invest_principal_total(state)
            + hoard_money(state)
            + estate_hoard(state)
            + float(coin.get("melted_pool", 0) or 0)
            + float(bank.get("reserve", 0) or 0)
            + _silver_stock(state))


# --------------------------------------------------------------------------
# 快照与对账
# --------------------------------------------------------------------------
def snapshot(state) -> Dict[str, Any]:
    """全部账户余额 ＋ 各口径读数（供面板、存档与对账）。"""
    coin = getattr(state, "coin", {}) or {}
    bank = getattr(state, "bank", {}) or {}
    accounts = {
        "pop_wealth": pop_money(state),
        "estate_wealth": estate_wealth(state),
        "treasury": float(getattr(state, "treasury", 0) or 0),
        "imperial": float(getattr(state, "imperial_treasury", 0) or 0),
        "local_treasury": local_treasury_total(state),
        "payraise_budget": payraise_budget_total(state),
        "invest_principal": invest_principal_total(state),
        "hoard": hoard_money(state),
        "estate_hoard": estate_hoard(state),
        "melt_pool": float(coin.get("melted_pool", 0) or 0),
        "bank_reserve": float(bank.get("reserve", 0) or 0),
        "silver_stock": _silver_stock(state),
    }
    accounts["M_ALL"] = float(sum(accounts[k] for k in ACCOUNTS))
    accounts["m0"] = m0(state)
    accounts["m1_full"] = m1(state, working_only=False)
    accounts["m1_working"] = m1(state, working_only=True)
    accounts["m2"] = m2(state, working_only=False)
    accounts["m3"] = m3(state, working_only=False)
    accounts["jiaozi_eff"] = effective_jiaozi(state)
    accounts["copper_share"] = copper_share(state)
    return accounts


def reconcile(prev: Dict[str, float], now: Dict[str, float],
              external_in: float = 0.0, burned: float = 0.0) -> Dict[str, Any]:
    """对比两期账户快照，产出各账户 Δ 与对账残差。

    残差 ＝ ΔM_ALL − 外部净注入 ＋ 真实销毁

    外部净注入 =「存量式通道」Δsilver_stock ＋「流水式通道」`external_in`
                （外销变现等，由 `register_flow` 登记）
    真实销毁   = `burned`（岁币外流、交子销毁、铜料离库等）

    只有**可验证的体外出入口**才应从残差中扣除；其余任何净增/净减都会落到残差里，
    从而把"无对手方的造币/销毁"显式暴露出来。
    """
    deltas: Dict[str, float] = {}
    for k in ACCOUNTS:
        d = float(now.get(k, 0.0)) - float(prev.get(k, 0.0))
        if abs(d) > 1e-6:
            deltas[k] = d

    d_mall = float(now.get("M_ALL", 0.0)) - float(prev.get("M_ALL", 0.0))
    external = sum(deltas.get(k, 0.0) for k in EXTERNAL_ACCOUNTS) + float(external_in)
    burned_total = -sum(deltas.get(k, 0.0) for k in SINK_ACCOUNTS) + float(burned)
    residual = d_mall - external + burned_total

    return {
        "d_mall": d_mall,
        "external_in": external,
        "external_flow": float(external_in),
        "burned": burned_total,
        "burn_flow": float(burned),
        "residual": residual,
        "deltas": deltas,
        "m0": now.get("m0", 0.0),
        "m1_working": now.get("m1_working", 0.0),
        "m1_full": now.get("m1_full", 0.0),
        "m2": now.get("m2", 0.0),
        "m3": now.get("m3", 0.0),
    }


def describe_residual(rec: Dict[str, Any], tol: float = 1.0) -> str:
    """把对账记录渲染成一行结论（面板/日志/探针共用）。"""
    res = float(rec.get("residual", 0.0))
    if abs(res) <= tol:
        return "对账通过（残差≈0）"
    verb = "凭空造币" if res > 0 else "凭空销毁"
    top = sorted(rec.get("deltas", {}).items(), key=lambda kv: -abs(kv[1]))[:3]
    detail = "、".join(f"{k} {v:+,.0f}" for k, v in top)
    return f"⚠️ 残差 {res:+,.0f} 贯（{verb}）｜主要变动账户：{detail}"


def audit_step(state) -> Dict[str, Any]:
    """每月结算末尾调用：与上月快照对比，写入 `state.money_audit`（**只读对账**）。

    不修改任何货币账户；只维护 `state.money_audit`（上月快照 ＋ 本期记录 ＋ 累计残差）。
    """
    now = snapshot(state)
    audit = getattr(state, "money_audit", None)
    if not isinstance(audit, dict):
        audit = {}
        state.money_audit = audit

    prev = audit.get("last")
    rec: Dict[str, Any] = {"turn": int(getattr(state, "turn", 0) or 0), "now": now}
    flow = take_flow(state)          # 读取并清零本月外部/销毁台账
    rec["external_notes"] = flow.get("notes", [])
    if isinstance(prev, dict):
        r = reconcile(prev, now,
                      external_in=flow.get("external_in", 0),
                      burned=flow.get("burned", 0))
        rec.update(r)
        audit["cum_residual"] = float(audit.get("cum_residual", 0.0)) + float(r["residual"])
    else:
        rec.update({"d_mall": 0.0, "external_in": 0.0, "external_flow": 0.0,
                    "burned": 0.0, "burn_flow": 0.0, "residual": 0.0, "deltas": {}})
        audit["cum_residual"] = 0.0
        audit.setdefault("start", now)

    audit["last"] = now
    audit["recent"] = (list(audit.get("recent", [])) + [rec])[-24:]   # 只留近 24 月
    return rec


# ==========================================================================
# 金融口径只读视图（第二节§1/§2/§3/§5；第六节数据契约）
# --------------------------------------------------------------------------
# 铁律：本段全部为**只读派生视图**，绝不写任何账户、绝不做守恒运算的输入权威。
# 货币守恒权威仍是 POP/国库/内帑/银行准备金等真实余额；本段只把它们**读**成
# 「发行额/流通额/兑付率/折价/存款/贷款/汇率」等口径，供面板、存档对账与 API。
# ==========================================================================
def _num(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _clamp01(v) -> float:
    return max(0.0, min(1.0, _num(v)))


def bank_capital_as_guan(state) -> float:
    """银行资本「万贯 → 贯」的唯一换算入口（第六节：禁止贯与万贯混用）。"""
    return _bank_capital_as_guan(state)


def jiaozi_issued(state) -> float:
    """交子**发行额**（贯）：存量券面；不等于流通额。"""
    return max(0.0, _num((getattr(state, "jiaozi", {}) or {}).get("issued")))


def jiaozi_circulating(state) -> float:
    """交子**流通额**（贯）。

    唯一权威公式 = 发行额 × 接受度(trust/100)（即 `effective_jiaozi`）；
    `jiaozi["circulating"]` 只是结算步逐月刷新的**派生缓存/展示字段**，
    不作为权威读取——避免「缓存陈旧 → 流通额失真」的双权威问题。
    """
    return effective_jiaozi(state)


def jiaozi_reserve(state) -> float:
    """交子**准备金**（贯）：不得计入流通货币供给（仅供兑付）。"""
    return max(0.0, _num((getattr(state, "jiaozi", {}) or {}).get("reserve")))


def jiaozi_redeem_rate(state) -> float:
    """交子**兑付率** = 准备金 ÷ 流通额（流通为 0 时记足额 1.0）。"""
    c = jiaozi_circulating(state)
    if c <= 0:
        return 1.0
    return jiaozi_reserve(state) / c


def _derived_jiaozi_discount(state) -> float:
    """折价率（0~1）派生：兑付不足 × 信用不足。损失由持券者承担。"""
    r = min(1.0, jiaozi_redeem_rate(state))
    trust = _clamp01(_num((getattr(state, "jiaozi", {}) or {}).get("trust", 0)) / 100.0)
    if jiaozi_issued(state) <= 0:
        return 0.0
    return _clamp01((1.0 - r) * (1.0 - trust))


def jiaozi_discount(state) -> float:
    """交子折价率（0~1）：唯一权威 = 兑付率不足 × 信用不足（公式派生）。

    `jiaozi["discount"]` 只是结算步逐月刷新的派生缓存/展示字段，不作权威读取。
    """
    return _derived_jiaozi_discount(state)


def _derived_jiaozi_run(state) -> float:
    """挤兑压力（0~1）派生：信用跌破线 / 兑付率不足 → 持券人集中兑现。"""
    from content.data import JIAOZI_RUN_RESERVE_LINE, JIAOZI_RUN_TRUST_LINE
    if jiaozi_issued(state) <= 0:
        return 0.0
    trust = _num((getattr(state, "jiaozi", {}) or {}).get("trust", 0))
    r = jiaozi_redeem_rate(state)
    return _clamp01((r < JIAOZI_RUN_RESERVE_LINE) * 0.5
                    + max(0.0, JIAOZI_RUN_TRUST_LINE - trust) / max(JIAOZI_RUN_TRUST_LINE, 1e-9) * 0.5)


def jiaozi_run_pressure(state) -> float:
    """挤兑压力（0~1）：唯一权威 = 信用/兑付率派生（公式）。

    `jiaozi["run_pressure"]` 只是结算步逐月刷新的派生缓存/展示字段，不作权威读取。
    """
    return _derived_jiaozi_run(state)


def jiaozi_view(state) -> dict:
    """交子只读口径：发行额/流通额/准备金/兑付率/折价/挤兑/界期。"""
    jz = getattr(state, "jiaozi", {}) or {}
    term = int(_num(jz.get("term", 36), 36))
    age = int(_num(jz.get("age", 0)))
    return {
        "issued": jiaozi_issued(state),
        "circulating": jiaozi_circulating(state),
        "reserve": jiaozi_reserve(state),
        "redeem_rate": jiaozi_redeem_rate(state),
        "discount": jiaozi_discount(state),
        "run_pressure": jiaozi_run_pressure(state),
        "trust": _num(jz.get("trust", 0)),
        "tax_acceptance": _clamp01(jz.get("tax_acceptance", 1.0)),
        "term": term,
        "cycle": int(_num(jz.get("cycle", 0))),
        "age": age,
        "cycle_progress": (age / term) if term > 0 else 0.0,
        "redeemed_total": _num(jz.get("redeemed_total", 0)),
    }


def bank_view(state) -> dict:
    """银行只读口径：存款/贷款/准备金率/逾期率/挤兑压力/网点/对象/资本（贯）。"""
    b = getattr(state, "bank", {}) or {}
    reserve = _num(b.get("reserve"))
    deposits = _num(b.get("deposits"))
    loans = _num(b.get("loans"))
    return {
        "established": bool(b.get("established", False)),
        "capital_guan": bank_capital_as_guan(state),   # 万贯 → 贯（唯一换算入口）
        "capital_won": _num(b.get("capital")),
        "reserve": reserve,
        "deposits": deposits,
        "loans": loans,
        "reserve_ratio": _clamp01(b.get("reserve_ratio", 0.0)),
        "overdue_rate": _clamp01(b.get("overdue_rate", 0.0)),
        "run_pressure": _clamp01(b.get("run_pressure", 0.0)),
        "branches": int(_num(b.get("branches", 0))),
        "target": str(b.get("target", "") or ""),
        "loan_to_deposit": (loans / deposits) if deposits > 0 else 0.0,
    }


def standard_rates(state, market: bool = False) -> dict:
    """本位只读汇率：market=False 取**记账汇率**，True 取**市场汇率**（旧档回退 legacy）。"""
    s = getattr(state, "standard", {}) or {}
    if market:
        silver = s.get("market_silver_per_copper", s.get("silver_per_copper", 1.0))
        gold = s.get("market_gold_per_copper", s.get("gold_per_copper", 10.0))
    else:
        silver = s.get("book_silver_per_copper", s.get("silver_per_copper", 1.0))
        gold = s.get("book_gold_per_copper", s.get("gold_per_copper", 10.0))
    silver = max(1e-9, _num(silver, 1.0))
    gold = max(1e-9, _num(gold, 10.0))
    return {"silver_per_copper": silver, "gold_per_copper": gold,
            "rate_basis": "market" if market else "book"}


def _unit_per_copper(rate: dict, unit: str) -> float:
    """1 贯铜钱折合多少 <unit>。"""
    u = str(unit or "copper")
    if u in ("copper", "铜", "贯", "铜钱"):
        return 1.0
    if u in ("silver", "银", "两", "白银"):
        return 1.0 / rate["silver_per_copper"]
    if u in ("gold", "金", "黄金"):
        return 1.0 / rate["gold_per_copper"]
    raise ValueError(f"未知币种单位：{unit!r}")


def exchange_quote(state, amount, *, from_unit: str = "copper",
                   to_unit: str = "silver", market: bool = True) -> dict:
    """兑换**只读报价**（第二节§5）：返回手续费、铸币损耗与**双方资产变化**。

    本函数不写任何状态；调用方落地时必须：
      ① 用 `transfer_money` 在双方账户间成对划转净额；
      ② 手续费/铸币损耗用 `register_flow(kind="burn")` 登记（真实退出流通）。
    失败（非法单位/非正金额）返回 ok=False + error，**不得静默成功**。
    """
    amt = _num(amount)
    if amt <= 0:
        return {"ok": False, "error": "兑换额须为正", "amount": amt}
    s = getattr(state, "standard", {}) or {}
    fee_rate = _clamp01(s.get("fee_rate", 0.01))
    mint_loss = _clamp01(s.get("mint_loss", 0.02))
    book = standard_rates(state, market=False)
    mkt = standard_rates(state, market=True)
    rate = mkt if market else book
    try:
        copper = amt / _unit_per_copper(rate, from_unit)   # 付出方价值（铜钱/贯口径）
        out = copper * _unit_per_copper(rate, to_unit)     # 收方毛额（to_unit）
    except ValueError as e:
        return {"ok": False, "error": str(e), "amount": amt}
    # 口径统一到铜钱（贯）做守恒：付出 copper、收方净得、手续费、熔铸损耗
    fee_copper = copper * fee_rate
    loss_copper = copper * mint_loss
    net_copper = copper - fee_copper - loss_copper
    # 收方按 to_unit 计的明细（内部与 copper 口径一致，仅做单位换算）
    fee = out * fee_rate
    loss = out * mint_loss
    net = out - fee - loss
    return {
        "ok": True, "error": "",
        "from_unit": str(from_unit), "to_unit": str(to_unit), "market": bool(market),
        "amount": amt, "copper_value": copper,
        "book_rate": book, "market_rate": mkt,
        "gross": out, "fee": fee, "mint_loss": loss, "net": net,
        # 铜钱口径守恒项：payer_copper + net_copper + fee + burn == 0
        "payer_copper": -copper, "receiver_copper": net_copper,
        "fee_copper": fee_copper, "burn_copper": loss_copper,
        # 双方资产变化（各自计量单位）：付方 -amt，收方 +net，手续费归兑换机构，损耗退出流通
        "payer_delta": -amt, "receiver_delta": net,
        "fee_sink": fee, "burn": loss,
    }


def circulating_copper(state) -> float:
    """流通铜钱（贯）= 民间持钱 × 铜钱占比（窖藏银/准备金/仓粮不计）。"""
    return max(0.0, (pop_money(state) + estate_wealth(state)) * copper_share(state))


def circulating_jiaozi(state) -> float:
    """有效交子余额（贯，流通额）：= 发行额 × 接受度。"""
    return jiaozi_circulating(state)


def circulating_silver(state) -> float:
    """实际流通白银折钱（贯）：`state.silver_stock`（窖银另计、不重复）。"""
    return max(0.0, _silver_stock(state))


def effective_money_supply(state) -> float:
    """统一**有效货币供给**口径（第二节§1）：

        流通铜钱 + 有效交子余额 + 实际流通白银折钱

    **不重复计入**：窖藏（hoard/estate_hoard/窖银）、准备金（bank reserve /
    jiaozi reserve）、熔铜池（退出流通的铜料）、仓粮（非货币）。
    """
    return circulating_copper(state) + circulating_jiaozi(state) + circulating_silver(state)


def supply_breakdown(state) -> dict:
    """有效货币供给拆解 + 明确排除项（供对账/面板/API）。"""
    coin = getattr(state, "coin", {}) or {}
    excluded = {
        "hoard": hoard_money(state),                 # 士绅窖银（窖藏，退出流通）
        "estate_hoard": estate_hoard(state),         # 大贾窖藏
        "bank_reserve": _num((getattr(state, "bank", {}) or {}).get("reserve")),
        "jiaozi_reserve": jiaozi_reserve(state),
        "melt_pool": _num(coin.get("melted_pool")),  # 钱→铜料，退出流通
        "grain": 0.0,                                # 仓粮（石）非货币，恒不计
    }
    copper = circulating_copper(state)
    jz = circulating_jiaozi(state)
    silver = circulating_silver(state)
    return {
        "copper": copper, "jiaozi": jz, "silver": silver,
        "effective": copper + jz + silver,
        "excluded": excluded,
        "excluded_total": sum(excluded.values()),
    }


def assert_supply_no_double_count(state, tol: float = 1.0) -> dict:
    """守恒断言：有效货币供给恰为「M0 口径 + 流通白银」，且三项均非负。

    口径恒等式（第二节§1）：有效货币供给 == (流通铜钱 + 有效交子) + 流通白银折钱
                                       == `m0(state)` + `circulating_silver(state)`。
    窖藏 / 银行准备金 / 交子准备金 / 熔铜池 / 仓粮**不在**上式，故不重复计入。
    违反则抛 AssertionError（失败不得静默）。
    """
    bd = supply_breakdown(state)
    expect = m0(state) + circulating_silver(state)
    if abs(bd["effective"] - expect) > tol:
        raise AssertionError(
            f"有效货币供给口径不一致：{bd['effective']:.0f} != m0+白银 {expect:.0f}")
    if min(bd["copper"], bd["jiaozi"], bd["silver"]) < -tol:
        raise AssertionError(f"有效货币供给出现负项：{bd}")
    return bd


def finance_report(state) -> dict:
    """金融 API**只读**汇总（第六节：返回来源、去向、状态、错误）。

    不写任何状态；status != "ok" 时 error 给出显式原因（不静默成功）。
    """
    from content.data import FINANCE_SCHEMA_VERSION, GRAIN_UNIT, MONEY_UNIT
    audit = getattr(state, "money_audit", {}) or {}
    recent = audit.get("recent", []) or []
    rec = recent[-1] if recent else {}
    residual = float(rec.get("residual", 0.0))
    ok = abs(residual) <= 1.0
    return {
        "schema_version": FINANCE_SCHEMA_VERSION,
        "units": {"money": MONEY_UNIT, "grain": GRAIN_UNIT},
        "source": "core.money 只读口径（权威源：POP wealth/grain、国库、内帑、银行准备金）",
        "status": "ok" if ok else "mismatch",
        "error": "" if ok else f"月度货币对账残差 {residual:+,.0f} 贯（存在无对手方的造币/销毁）",
        "residual": residual,
        "cum_residual": float(audit.get("cum_residual", 0.0)),
        "sinks": list(SINK_ACCOUNTS),
        "exclude_accounts": list(EXTERNAL_ACCOUNTS),
        "supply": supply_breakdown(state),
        "jiaozi": jiaozi_view(state),
        "bank": bank_view(state),
        "standard_book": standard_rates(state, market=False),
        "standard_market": standard_rates(state, market=True),
    }
