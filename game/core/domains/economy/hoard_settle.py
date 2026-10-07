# -*- coding: utf-8 -*-
"""封桩分层代价通道（货币口径规范 §12.2/§12.3；仓鼠-D1/D2 落地）。

M1 只计「周转金」（国库 3×月常费、内帑 1×月常费），超出部分为**封桩**死钱
（`core/money.py::m1(working_only=True)` 口径）。囤积本身不是罪——但必须挂代价，
否则"仓鼠"是支配策略：

  C2 侵渔（本模块，自动）：库存越大，鼠耗/胥吏侵盗的**绝对额**越大
      （封桩 × 月率，封顶）。钱**不消失**——守恒划转进 吏 POP 私囊（侵盗入私），
      ΣM_ALL 零残差。
  C3/C4 挥霍与政治要价（本模块产出压力 → core/events.py 富事件卡）：帑藏充溢
      （国库 > 24×月常费 或 内帑 > 12×月常费）→ 「帑藏充溢」事件压力月增，
      达阈值触发富事件卡（发内帑充军国 / 大兴土木 / 拒而弗听）。
      压力通道**不走 EVENT_CATEGORIES 基线增长**（基线 0~2/月会让该卡随机触发），
      仅由本模块按库存条件增减。

纪律（与全库一致）：
- 守恒：所有划转走 `state.transfer_money`（返回实划额），禁止凭空铸/毁币；
- 只给档位/日志，不向玩家外泄满意度等隐藏数值；
- 调用点：Step 5 `_settle_treasury`（`core/settlement_finance.py`）——财政各步
  已写完、Step 7 事件步之前，压力当月即可生效。
"""
from __future__ import annotations

import random
from typing import Any, Dict

__all__ = ["settle_hoard", "hoard_readout",
           "HOARD_K_GUO", "HOARD_K_NEI", "INVASION_RATE", "INVASION_CAP"]

# ---- 参数（货币规范 §12.2/§12.4 建议初值，须回放校准）----
HOARD_K_GUO = 3.0            # 国库周转金 = 3 × 月常费（约 264 万贯）
HOARD_K_NEI = 1.0            # 内帑周转金 = 1 × 月常费（内帑本职"死钱"）
INVASION_RATE = 0.005        # C2 侵渔月率（封桩的 0.5%/月）
INVASION_CAP = 500_000       # C2 单月侵渔封顶（贯）——边际递减，防硬吃
OVERFLOW_TREASURY_MULT = 24.0   # C3 阈值：国库 > 24×月常费（≈2,112 万贯）
OVERFLOW_IMPERIAL_MULT = 12.0   # C3 阈值：内帑 > 12×月常费


def hoard_readout(state) -> Dict[str, Any]:
    """封桩只读口径：周转金上限、封桩额、侵渔月估（供面板/审计/测试）。"""
    from content.data import MONTHLY_EXP_CIVIL_BASE
    base = float(MONTHLY_EXP_CIVIL_BASE)
    treasury = float(getattr(state, "treasury", 0) or 0)
    imperial = float(getattr(state, "imperial_treasury", 0) or 0)
    cap_guo = HOARD_K_GUO * base
    cap_nei = HOARD_K_NEI * base
    idle_t = max(0.0, treasury - cap_guo)
    idle_i = max(0.0, imperial - cap_nei)
    idle = idle_t + idle_i
    return {
        "monthly_base": base,
        "treasury_working_cap": cap_guo,
        "imperial_working_cap": cap_nei,
        "treasury_idle": idle_t,
        "imperial_idle": idle_i,
        "hoard_total": idle,
        "invasion_monthly_estimate": min(INVASION_CAP, idle * INVASION_RATE),
        "overflow": (treasury > OVERFLOW_TREASURY_MULT * base
                     or imperial > OVERFLOW_IMPERIAL_MULT * base),
    }


def _drain_into_clerks(state, src: str, amount: float) -> int:
    """把 src（treasury/imperial_treasury）的 amount 侵渔进各路「吏」POP 私囊。

    守恒划转（`transfer_money` 返回实划额）；逐路轮转直到用尽或无可入之池。
    新局尚无「吏」POP（吏由官制/吏制步生成）→ 回退「官僚」（监守自盗同义）。
    返回实划总额。
    """
    if amount <= 0:
        return 0
    pops_by_road = {name: (p.get("pops") or {})
                    for name, p in (getattr(state, "prefectures", {}) or {}).items()
                    if isinstance(p, dict)}
    target_pop = None
    for cand in ("吏", "官僚"):  # 吏胥侵盗 → 监守自盗（官僚）回退
        if any(cand in (pops or {}) for pops in pops_by_road.values()):
            target_pop = cand
            break
    if target_pop is None:
        return 0
    roads = [name for name, pops in pops_by_road.items() if target_pop in (pops or {})]
    moved_total = 0
    idx = 0
    remaining = int(amount)
    while remaining > 0 and roads:
        road = roads[idx % len(roads)]
        idx += 1
        # 单路单次 ≤ 5 万贯，避免一次性砸进一路（分布感 + 数值安全）
        part = min(remaining, 50_000)
        moved = state.transfer_money(src, f"pop:{road}:{target_pop}", part)
        moved_total += moved
        remaining -= moved
        if moved <= 0:
            # 该路不可入（理论上不会：dst 是加钱方向）——换下一路，防死循环
            if road in roads:
                roads.remove(road)
            if not roads:
                break
    return moved_total


def settle_hoard(state, log) -> None:
    """封桩分层月度代价（Step 5 调用；详见模块 docstring）。"""
    ro = hoard_readout(state)

    # ---- C2 侵渔：封桩越大，鼠耗/胥吏侵盗绝对额越大（钱入吏私囊，零残差）----
    idle = ro["hoard_total"]
    if idle > 0:
        drain = min(INVASION_CAP, idle * INVASION_RATE)
        idle_t, idle_i = ro["treasury_idle"], ro["imperial_idle"]
        # 按国库/内帑封桩占比分摊来源
        plan = []
        if idle > 0:
            if idle_t > 0:
                plan.append(("treasury", drain * idle_t / idle))
            if idle_i > 0:
                plan.append(("imperial_treasury", drain * idle_i / idle))
        moved_total = 0
        for src, amt in plan:
            moved_total += _drain_into_clerks(state, src, amt)
        if moved_total > 0:
            log.append(f"[封桩] 库藏封桩 {idle:,.0f}贯，鼠耗侵渔 {moved_total:,.0f}贯"
                       f"流入吏胥私囊")

    # ---- C3/C4 帑藏充溢：挥霍与请开内帑的政治要价（事件压力通道）----
    pressure_key = "帑藏充溢"
    if ro["overflow"]:
        state.event_pressure[pressure_key] = \
            state.event_pressure.get(pressure_key, 0) + random.uniform(6, 10)
        log.append("[封桩] 帑藏充溢，请开内帑以充军国之疏日上，亦有劝兴土木者")
    else:
        # 未超阈值：压力自然衰减（让步于封桩回落）
        cur = state.event_pressure.get(pressure_key, 0)
        if cur > 0:
            state.event_pressure[pressure_key] = max(0.0, cur - random.uniform(2, 4))
