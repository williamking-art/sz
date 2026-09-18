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
    M3  全社会     = M2 ＋ 白银存量 ＋ 银行资本（万贯→贯）
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
    "ACCOUNTS", "SINK_ACCOUNTS",
    "pop_money", "hoard_money", "local_treasury_total", "effective_jiaozi", "copper_share",
    "m0", "m1", "m2", "m3", "m_all",
    "snapshot", "reconcile", "audit_step", "describe_residual",
]

# 计入 M_ALL 的账户（顺序即展示顺序）
ACCOUNTS: Tuple[str, ...] = (
    "pop_wealth",        # Σ 六类 POP wealth（民间持钱，含其持有的交子）
    "treasury",          # 国库
    "imperial",          # 内帑
    "local_treasury",    # Σ 各路地方府库
    "hoard",             # Σ 士绅窖银（退出流通）
    "melt_pool",         # 熔铜池（钱→铜料，退出流通）
    "bank_reserve",      # 银行准备金
    "silver_stock",      # 海外白银存量（外部注入的唯一合法入口）
)

# 真实销毁通道（真正让货币退出 M_ALL 的机制）
SINK_ACCOUNTS: Tuple[str, ...] = ()   # step 1 暂空；换界销毁/铜料离库在 step 2 接入

# 白银流入以外的外部注入通道（step 1 仅白银）
EXTERNAL_ACCOUNTS: Tuple[str, ...] = ("silver_stock",)


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
    """流通中通货 = 民间铜钱 ＋ 有效交子。"""
    return pop_money(state) * copper_share(state) + effective_jiaozi(state)


def m1(state, working_only: bool = False, months_of_base: float = 3.0) -> float:
    """狭义货币 = M0 ＋ 政府即付资金。

    working_only=True 时只计"周转金"（`months_of_base` × 月常费），
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
    return g + base + imp + local_treasury_total(state)


def m2(state, working_only: bool = False) -> float:
    """广义货币 = M1 ＋ 沉淀层（士绅窖银 ＋ 熔铜池 ＋ 银行准备金）。"""
    coin = getattr(state, "coin", {}) or {}
    bank = getattr(state, "bank", {}) or {}
    return (m1(state, working_only=working_only)
            + hoard_money(state)
            + float(coin.get("melted_pool", 0) or 0)
            + float(bank.get("reserve", 0) or 0))


def m3(state, working_only: bool = False) -> float:
    """全社会货币资产 = M2 ＋ 白银存量 ＋ 银行资本 ＋ 交子本钱。"""
    jz = getattr(state, "jiaozi", {}) or {}
    return (m2(state, working_only=working_only)
            + _silver_stock(state)
            + _bank_capital_as_guan(state)
            + float(jz.get("reserve", 0) or 0))


def m_all(state) -> float:
    """会计全集 = 全部**计入**账户之和（见模块头"刻意不计入"表）。"""
    coin = getattr(state, "coin", {}) or {}
    bank = getattr(state, "bank", {}) or {}
    return (pop_money(state)
            + float(getattr(state, "treasury", 0) or 0)
            + float(getattr(state, "imperial_treasury", 0) or 0)
            + local_treasury_total(state)
            + hoard_money(state)
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
        "treasury": float(getattr(state, "treasury", 0) or 0),
        "imperial": float(getattr(state, "imperial_treasury", 0) or 0),
        "local_treasury": local_treasury_total(state),
        "hoard": hoard_money(state),
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


def reconcile(prev: Dict[str, float], now: Dict[str, float]) -> Dict[str, Any]:
    """对比两期账户快照，产出各账户 Δ 与对账残差。

    残差 ＝ ΔM_ALL − Σ(外部净注入) ＋ Σ(真实销毁)

    step 1 仅把 `silver_stock` 视为外部注入通道；其余任何净增/净减都会落到残差里，
    从而把"无对手方的造币/销毁"显式暴露出来。
    """
    deltas: Dict[str, float] = {}
    for k in ACCOUNTS:
        d = float(now.get(k, 0.0)) - float(prev.get(k, 0.0))
        if abs(d) > 1e-6:
            deltas[k] = d

    d_mall = float(now.get("M_ALL", 0.0)) - float(prev.get("M_ALL", 0.0))
    external = sum(deltas.get(k, 0.0) for k in EXTERNAL_ACCOUNTS)
    burned = -sum(deltas.get(k, 0.0) for k in SINK_ACCOUNTS)
    residual = d_mall - external + burned

    return {
        "d_mall": d_mall,
        "external_in": external,
        "burned": burned,
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
    if isinstance(prev, dict):
        r = reconcile(prev, now)
        rec.update(r)
        audit["cum_residual"] = float(audit.get("cum_residual", 0.0)) + float(r["residual"])
    else:
        rec.update({"d_mall": 0.0, "external_in": 0.0, "burned": 0.0,
                    "residual": 0.0, "deltas": {}})
        audit["cum_residual"] = 0.0
        audit.setdefault("start", now)

    audit["last"] = now
    audit["recent"] = (list(audit.get("recent", [])) + [rec])[-24:]   # 只留近 24 月
    return rec
