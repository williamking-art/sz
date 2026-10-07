# -*- coding: utf-8 -*-
"""宋祚 · 科技攻关与工程（从 settlement_steps.py 拆出，零行为变更）。

`_settle_tech_research` / `_settle_projects`。"""
from __future__ import annotations

import logging
import math

from core.settlement_common import (
    transfer_public_funds_to_pops,
    _collect_from_pops,
)

_log = logging.getLogger("settlement")


def _research_rate_mult(state, node, r, log=None) -> float:
    """研发速率乘数（整改④.2）：受学校/书院、识字率、材料、总体 level 影响。

    总体 level 只作**软因子**（不再是能力关卡）；材料不足只降效（不归零）。

    审查 P2-3 应修：原两处 `except Exception: pass` 静默降级 → 乘数少算一档而无人知
    （玩家看到的是"研究变慢"，看不出是通道坏了）。现经 `note_settlement_error` 留痕
    （`(state.turn, key)` 去重 → 每回合最多一行，且两个降级点分别命名的 key）。
    """
    from content.data import (TECH_RESEARCH_LITERACY_W, TECH_RESEARCH_SCHOOL_CAP,
                              TECH_RESEARCH_MATERIAL_FLOOR, TECH_RESEARCH_RATE_CAP)
    from core.settlement_common import note_settlement_error
    mult = 1.0
    try:
        from core.era_mechanic import tech_build_bonus
        mult += min(TECH_RESEARCH_SCHOOL_CAP, max(0.0, float(tech_build_bonus(state))))
    except Exception as e:  # noqa: BLE001
        note_settlement_error(
            state, "research_school_bonus", "研发",
            f"学校/书院加成读数失败，速率按无加成计算（{type(e).__name__}）",
            log=log, exc=e)
    # 审查 S8：① `or 0.0` 把「缺失」吞成「实测 0% 识字率」（缺失≠0）；且
    #    `float(nan)` 经 `min(100, nan)`/`max(0, ·)` 会变成**100% 识字率**（与 M4 同族的
    #    非有限值漏洞）。现：缺失 → 记留痕并按"无识字率加成"处理（不伪造读数）；
    #    非有限值 → 同样按缺失处理，绝不参与乘算。
    try:
        _lit_raw = getattr(state, "literacy", None)
        _lit = None if _lit_raw is None else float(_lit_raw)
        if _lit is None or not math.isfinite(_lit):
            note_settlement_error(
                state, "research_literacy_bonus", "研发",
                "识字率读数缺失或非有限，速率按无识字率加成计算（不伪造读数）",
                log=log)
            _lit = None
        else:
            _lit = max(0.0, min(100.0, _lit))
    except Exception as e:  # noqa: BLE001
        _lit = None
        note_settlement_error(
            state, "research_literacy_bonus", "研发",
            f"识字率加成读数失败，速率按无加成计算（{type(e).__name__}）",
            log=log, exc=e)
    if _lit is not None:
        mult += (_lit / 100.0) * TECH_RESEARCH_LITERACY_W
    # 总体 level 只作综合读数：作为软因子影响速率，不作硬门槛（§四.1）
    need_lv = max(1, int(node[6] or 0))
    lv = max(0, min(100, int((state.tech or {}).get("level", 0) or 0)))
    mult *= 0.85 + 0.15 * min(1.0, lv / need_lv)
    # 材料（缺料降效不归零）：r["materials"] 或节点 cost 声明
    need = dict(r.get("materials") or {})
    if not need:
        _c = node[8] or {}
        if isinstance(_c, dict):
            need = dict(_c.get("materials") or {})
    if need:
        cover = 1.0
        _res = getattr(state, "resources", {}) or {}
        for dim, q in need.items():
            try:
                q = float(q or 0)
            except (TypeError, ValueError):
                continue
            if q <= 0:
                continue
            stock = float((_res.get(dim) or {}).get("stock", 0) or 0)
            cover = min(cover, stock / q)
        cover = max(0.0, min(1.0, cover))
        mult *= TECH_RESEARCH_MATERIAL_FLOOR + (1 - TECH_RESEARCH_MATERIAL_FLOOR) * cover
    return max(0.1, min(TECH_RESEARCH_RATE_CAP, mult))


def _settle_tech_research(state, log):
    """按月推进攻关节点（整改④）：消耗预算与人才时间 / 中断保留进度 / 部署覆盖率结算。

    纪律：
      · researching 每月消耗**月预算**（国库 → 学者·工匠 POP，守恒转移）与人才时间；
        经费不继 → 中断（progress 保留，记 idle_months，属机会成本），**不静默完成**；
      · 速率受学校/书院、识字率、材料、总体 level（只作软因子）影响；
      · west 仅作受来源约束的加速因子（≤TECH_WEST_ACCEL_CAP），非万能加速器；
      · 解锁 ≠ 全国生效：月末按部署建筑结算 adoption 覆盖率（settle_adoption）。
    """
    from core.asset_context import (unlock_node, tech_cost_with_era, get_tech_node,
                                    settle_adoption)
    from content.data import (TECH_RESEARCH_PAY_TO,
                              TECH_WEST_ACCEL_PER_POINT, TECH_WEST_ACCEL_CAP)
    tech = state.tech
    researching = tech.get("researching", {})
    # 部署覆盖率月度结算：解锁 ≠ 全国生效（维护欠费 → 覆盖率折旧）
    settle_adoption(state, log)
    if not researching:
        return
    _stats = state.statistics if isinstance(getattr(state, "statistics", None), dict) else {}
    for node_id, r in list(researching.items()):
        node = get_tech_node(node_id)
        _lookup_err = None
        if node is None:
            # 承接模式：玩家注册节点兼容
            try:
                from core.registries import node_entry
                node = node_entry(state, node_id)
            except Exception as e:  # noqa: BLE001
                _lookup_err = e
                node = None
        if not node:
            if _lookup_err is not None:
                # 审查 P2-3 / M14：查表**抛错** ≠ "节点不存在"。原实现把两者都当
                # `node=None` → `researching.pop(node_id)`，于是**进度＋已投入经费＋
                # 人才时间一起消失**（玩家看到的只是"研究莫名其妙没了"）。
                # 现保留条目（下月重试）并留可定位证据。
                _log.warning("[研发] 节点 %s 查表失败（第 %s 回合）：保留研究条目待重试",
                             node_id, getattr(state, "turn", 0), exc_info=True)
                if isinstance(log, list):
                    log.append(f"[研发][WARN] 节点 {node_id} 查表失败"
                               f"（{type(_lookup_err).__name__}），本月保留研究进度待重试")
                continue
            researching.pop(node_id, None)     # 真正未注册（旧档残留）→ 清理
            continue
        cost = tech_cost_with_era(node, int(tech.get("era", 0)))
        # P1 修复（蔡权衡·超时代软约束递增）：第 N 个超时代节点研发成本 ×(1+0.1×(N-1))
        # （era ≥4 的超时代节点；防一口气全研，与工具注册软约束同构）
        if int(node[2]) >= 4:
            _n = sum(1 for nid in tech.get("unlocked", [])
                     if (lambda nd: nd and int(nd[2]) >= 4)(get_tech_node(nid)))
            from core.registries import soft_cost_mult
            _mult = soft_cost_mult(_n)
            cost = {k: (int(v * _mult) if isinstance(v, (int, float)) else v)
                    for k, v in cost.items()}
        months = max(1, r.get("months", cost["months"]))
        if r.get("idea"):
            from content.data import get_prestige_level
            _, _, authority = get_prestige_level(state.prestige)
            push = 0.6 + authority * 0.4
            if abs(state.factions.get("新党", {}).get("influence", 50) -
                   state.factions.get("旧党", {}).get("influence", 50)) > 40:
                push *= 0.85
            rate = (100.0 / months) * push * _research_rate_mult(state, node, r, log=log)
            r["progress"] = min(100.0, r.get("progress", 0) + rate)
        else:
            # 月度预算消耗（整改④.2）：不济 → 中断并保留进度（机会成本可诊断）
            monthly = int(r.get("monthly_cost", 0) or 0)
            if monthly > 0:
                # 审查 S8：与 `settlement.py:119`（同一研发月费机制）**对齐严格模式**——
                # 原实现未开 `raise_on_unavailable`，通道损坏会被静默记成"经费不济"
                # （idle_months++），把两件完全不同的事混为一谈。
                from core.settlement_common import MoneyChannelUnavailable
                from core.settlement_common import note_settlement_error
                try:
                    paid = transfer_public_funds_to_pops(
                        state, monthly, TECH_RESEARCH_PAY_TO,
                        f"研发月费：{node[3]}", raise_on_unavailable=True)
                except MoneyChannelUnavailable as _e:
                    note_settlement_error(
                        state, "tech_layer3_channel", "研发",
                        f"经费通道不可用，本月进度停滞（{type(_e).__name__}）",
                        log=log, exc=_e)
                    r["idle_months"] = int(r.get("idle_months", 0) or 0) + 1
                    continue
                if paid < monthly:
                    r["idle_months"] = int(r.get("idle_months", 0) or 0) + 1
                    _stats["research_idle_months"] =                         int(_stats.get("research_idle_months", 0) or 0) + 1
                    log.append(f"[科技] 新制「{node[3]}」经费不继（需 {monthly:,} 贯/月，"
                               f"实拨 {paid:,}），进度保留 {float(r.get('progress', 0) or 0):.0f}")
                    continue
            masters = max(1, r.get("masters", cost["masters"]))
            rate = (100.0 / months) * (0.8 + 0.15 * masters)
            rate *= _research_rate_mult(state, node, r, log=log)
            # 承接模式：玩家投入（invest_silver/grain）加速推进
            _invest = max(0, float(r.get("invest_silver", 0)))
            if _invest > 0:
                rate *= 1 + min(2.0, _invest / 1_000_000.0)
            # west 加速：受来源约束，封顶 ≤TECH_WEST_ACCEL_CAP（非万能加速器，§四.4）
            _west = max(0.0, float(tech.get("west", 0) or 0))
            _wmult = min(TECH_WEST_ACCEL_CAP,
                         1.0 + _west * TECH_WEST_ACCEL_PER_POINT)
            rate *= _wmult
            r["progress"] = min(100.0, r.get("progress", 0) + rate)
        if r["progress"] >= 100:
            researching.pop(node_id, None)
            unlock_node(state, node_id)
            # ---- B4-2 新材科技解锁（market-civilian-economy · 2026-11 接线）----
            # 科技节点点亮时，按注册表解锁该节点对应的新材。
            # 水泥/钢筋是**架空后世材料**（北宋无），未解锁 ⇒ 不可用、不可定价。
            # `skipped` **保留 reason 写日志**，不静默吞掉。
            try:
                from core.domains.construction.material_tech import unlock_materials_for_node
                _mt = unlock_materials_for_node(state, node_id, log=log)
                for _sk in (_mt.get("skipped") or []):
                    log.append(f"[建材] {_sk.get('material')} 未解锁"
                               f"（{_sk.get('reason')}）")
            except Exception as _mte:      # noqa: BLE001 — 新材解锁失败不阻断科技结算
                log.append(f"[建材][WARN] 新材解锁结算失败：{_mte!r}")
            tag = "颁行" if r.get("idea") else "研成"
            log.append(f"[科技] 新制「{node[3]}」{tag}，技进于器！")

    base = {"金": 50, "辽": 50, "西夏": 50}
    for k in ("金", "辽", "西夏"):
        cur = state.external[k]["attitude"]
        base_k = base[k]
        if state.alliance_jin_liao:
            if k == "金":
                base_k += 10
            elif k == "辽":
                base_k -= 10
        state.external[k]["attitude"] = max(0, min(100, cur + int((base_k - cur) * 0.05)))


def _settle_projects(state, log):
    """工程月度推进（整改③）：状态机 + 工匠工时 + 运维折旧。

    状态机：proposed → funded → building → operating → degraded/abandoned。
    纪律（源：整改意见 §三）：
      · 资金/材料/工匠工时/治安不足 → 延期或降效并记日志，绝不静默完工；
      · 就地消耗工匠 POP 可用工时（工役），营造款守恒转移入工匠/商人 POP wealth；
        时间损失只记 statistics["project_corvee_time_loss"] 审计读数，不新增工程人口；
      · 完工 → operating（capacity=1.0）；运行按月折旧，维持欠费 → degraded，可恢复。
    """
    from content.data import (
        GOV_SPEND_TO, PROJECT_STATUS_FLOW, PROJECT_LABOR_RATIO,
        PROJECT_UNDERSTAFF_MIN, PROJECT_SECURITY_UNREST,
        PROJECT_SECURITY_MIN_FACTOR, PROJECT_DEPRECIATION_RATE,
        PROJECT_MAINTENANCE_RECOVER, PROJECT_DEGRADED_LINE,
        PROJECT_PROPOSED_TIMEOUT,
    )
    stats = state.statistics if isinstance(getattr(state, "statistics", None), dict) else {}
    for pid, proj in list(state.projects.items()):
        if not isinstance(proj, dict):
            continue
        name = proj.get("name") or proj.get("type") or "工程"
        status = proj.get("status")
        if status is None:
            # 旧档兼容：已完工按 operating，否则按 building
            status = "operating" if proj.get("done") else "building"
            proj["status"] = status
        if status not in PROJECT_STATUS_FLOW:
            log.append(f"[工程] {name} 状态「{status}」非法，按 building 处理（可诊断）")
            status = proj["status"] = "building"
        # ---- 运行 / 降效：容量折旧与维持（维护 → 折旧，收益有容量） ----
        if status in ("operating", "degraded"):
            _arr = int(stats.get("upkeep_arrears", 0) or 0)
            _seen = proj.get("_upkeep_arrears_seen")
            if _seen is None:
                proj["_upkeep_arrears_seen"] = _arr
                _seen = _arr
            maintained = _arr <= int(_seen)
            proj["_upkeep_arrears_seen"] = _arr
            cap = float(proj.get("capacity", 1.0) or 0.0)
            if maintained:
                cap = min(1.0, cap + PROJECT_MAINTENANCE_RECOVER)
            else:
                _dep = float(proj.get("depreciation") or PROJECT_DEPRECIATION_RATE)
                cap = max(0.0, cap - _dep)
            proj["capacity"] = round(cap, 4)
            new_status = "operating" if cap >= PROJECT_DEGRADED_LINE else "degraded"
            if new_status != status:
                proj["status"] = new_status
                log.append(f"[工程] {name} 产能 {cap:.0%} → "
                           f"{'降效' if new_status == 'degraded' else '恢复运行'}"
                           f"（维持{'到位' if maintained else '欠费'}）")
            # ---- 运行期产出（规格任务 4）：按 **capacity** 按月执行 operators ----
            # 口径：产出随产能线性缩放（降效即减产，符合"维护与折旧影响运行"）；
            # 金额一律经**既有守恒通道** `_collect_from_pops` 向民间征收（实收才入账，
            # 不足则少收、绝不凭空造币），并写 provenance 供面板/审计回看。
            _rt = proj.get("_runtime") or {}
            if isinstance(_rt, dict) and _rt and cap > 0:
                _paid = 0
                for _ok, _amt in _rt.items():
                    _want = int(round(float(_amt or 0) * cap))
                    if _want <= 0:
                        continue
                    if _ok == "wine_coin_add":
                        _got = int(_collect_from_pops(state, _want) or 0)
                        state.imperial_treasury += _got
                        _paid += _got
                        stats["project_runtime_yield"] = \
                            float(stats.get("project_runtime_yield", 0) or 0) + _got
                        _rlog = proj.setdefault("_runtime_log", [])
                        if isinstance(_rlog, list):
                            _rlog.append({"turn": getattr(state, "turn", 0), "op": _ok,
                                          "want": _want, "got": _got,
                                          "capacity": round(cap, 4),
                                          "note": "运行期产出（守恒征收）"})
                            del _rlog[:-6]          # 只留最近 6 条，防存档膨胀
                        if _got < _want:
                            log.append(f"[工程] {name} 运行产出应 {_want:,} 贯，"
                                       f"民间可缴 {_got:,} 贯，按实入账")
                    elif _ok == "grain_buy":
                        # 粮类运行产出：走**既有守恒配对**通道（太仓 +粮、国库 −钱、
                        # 民间售粮得钱；钱粮两组 ΣΔ==0）。民间存粮不足 → 少买，不凭空造粮。
                        from core.settlement_common import _state_grain_trade
                        _g_got, _c_paid = _state_grain_trade(
                            state, _want, "buy", float(getattr(state, "grain_price", 1.0) or 1.0),
                            log, f"工程籴买·{name}")
                        if _g_got > 0:
                            stats["project_runtime_grain"] = \
                                float(stats.get("project_runtime_grain", 0) or 0) + int(_g_got)
                            _rlog = proj.setdefault("_runtime_log", [])
                            if isinstance(_rlog, list):
                                _rlog.append({"turn": getattr(state, "turn", 0), "op": _ok,
                                              "want": _want, "got": int(_g_got),
                                              "cost": int(_c_paid),
                                              "capacity": round(cap, 4),
                                              "note": "运行期籴买（国库出钱、太仓得粮、民间售粮）"})
                                del _rlog[:-6]
                        if int(_g_got) < _want:
                            log.append(f"[工程] {name} 运行籴买应 {_want:,} 石，"
                                       f"实籴 {int(_g_got):,} 石（民间存粮/国库钱不足），按实入账")
                    else:
                        # 未登记落点方式的运行键**不落地**（绝不凭空发明通道），但留痕
                        log.append(f"[工程] {name} 运行产出键「{_ok}」无守恒落点，本月未执行")
                if _paid:
                    log.append(f"[工程] {name} 运行产出 {_paid:,} 贯"
                               f"（产能 {cap:.0%}），入内帑")
            continue
        # ---- 拟议（proposed）→ 拨款（funded）：无款不开工，超期作罢 ----
        if status == "proposed":
            proj["proposed_months"] = int(proj.get("proposed_months", 0) or 0) + 1
            fund_need = int(proj.get("fund_cost", proj.get("cost_coin", 0)) or 0)
            if fund_need > 0 and int(getattr(state, "treasury", 0) or 0) < fund_need:
                if proj["proposed_months"] >= PROJECT_PROPOSED_TIMEOUT:
                    proj["status"] = "abandoned"
                    log.append(f"[工程] {name} 拟议逾 {PROJECT_PROPOSED_TIMEOUT} 月未得拨款，作罢")
                else:
                    stats["project_delay_months"] = int(stats.get("project_delay_months", 0) or 0) + 1
                    log.append(f"[工程] {name} 拟议待款（需 {fund_need:,} 贯，国库不足），暂缓")
                continue
            proj["status"] = "funded"
            log.append(f"[工程] {name} 已获拨款立项")
            status = "funded"

        # ---- 拨款 → 开工 ----
        if proj.get("status") == "funded":
            proj["status"] = "building"
            status = "building"
            log.append(f"[工程] {name} 开工营建")
        # ---- 营建（building）：供给率降效 + 工匠工时 + 治安 ----
        # 整改③：材料/钱不足按最短板同比例消耗与推进（逐步降效），不静默停滞/完工。
        from core.game_state_econ import project_supply_ratio, project_declaration_gaps
        _gaps = project_declaration_gaps(proj)
        if _gaps and not proj.get("_declared_warned"):
            proj["_declared_warned"] = True
            log.append(f"[工程] {name} 声明不全（缺：{','.join(_gaps)}），按实际供给降效推进")
        # 🔴 **E-1 + C-c**：供给率**只看本路商人货栈**，与落扣
        # （`consume_for_circuit`）**同一读口** —— 否则"判定说有料、落扣没料"，
        # 即 §14.2 **障碍 2（判定与采购口径分叉）**。
        # 传 `resources` 仅供 `project_supply_ratio` 读**非建材**维度。
        _route0 = proj.get("route") or proj.get("prefecture") or ""
        from core.foundation.ledger.material_holding import (material_holding_for_circuit as _mh,
                                           to_material_dim)
        _mat_view = {}
        for _d in (proj.get("cost_material") or {}):
            _md = to_material_dim(_d)
            if _md is None:
                # 非建材维度（如 `粮`）：仍查仓总账，保持既有口径
                _mat_view[_d] = (getattr(state, "resources", {}) or {}).get(_d)
                continue
            # 建材：值取**本路商人货栈**（E-1/C-c），形状须为 `{"stock": n}`
            _mat_view[_d] = {"stock": int(_mh(state, _route0, _md) or 0)}
        ratio = float(project_supply_ratio(
            proj, _mat_view or (getattr(state, "resources", {}) or {}),
            getattr(state, "treasury", 0) or 0))
        if ratio <= 0:
            _short = [dim for dim, need in (proj.get("cost_material") or {}).items()
                      if (_mh(state, _route0, to_material_dim(dim) or dim) or 0)
                      < float(need or 0)]
            if int(proj.get("cost_coin", 0) or 0) > 0 and \
                    int(getattr(state, "treasury", 0) or 0) < int(proj.get("cost_coin", 0) or 0):
                _short.append("钱")
            stats["project_delay_months"] = int(stats.get("project_delay_months", 0) or 0) + 1
            log.append(f"[工程] {name} 缺料停滞（供给率 0%，缺：{','.join(_short) or '资源'}），待补给")
            continue

        # 工匠工时（工役）：就地征用本路工匠 POP 可用工时；不足降效，无工匠停滞；
        # 工役时间损失只记 statistics 审计读数，不新增工程人口、不建平行账本。
        route = proj.get("route") or proj.get("prefecture")
        labor_need = float(proj.get("craft_hours", proj.get("labor_need", 0)) or 0)
        labor_cover = 1.0
        if labor_need > 0:
            prefs = getattr(state, "prefectures", {}) or {}
            if route in prefs:
                pools = [(prefs[route].get("pops") or {}).get("工匠")]
            else:
                pools = [(p.get("pops") or {}).get("工匠") for p in prefs.values()]
            avail = sum(float(x.get("size", 0) or 0)
                        for x in pools if isinstance(x, dict)) * PROJECT_LABOR_RATIO
            if avail <= 0:
                stats["project_delay_months"] = int(stats.get("project_delay_months", 0) or 0) + 1
                log.append(f"[工程] {name} 工匠工时不足（无可用工匠），停滞")
                continue
            labor_cover = min(1.0, avail / labor_need)
            if labor_cover < PROJECT_UNDERSTAFF_MIN:
                log.append(f"[工程] {name} 工匠工时严重不足（到位 {labor_cover:.0%}），降效")
            _workers = min(labor_need, avail)
            stats["project_corvee_worker_months"] = \
                float(stats.get("project_corvee_worker_months", 0) or 0) + _workers
            stats["project_corvee_time_loss"] = \
                float(stats.get("project_corvee_time_loss", 0) or 0) + _workers
        # 2026-10-11（B4-6 · 规格 market-civilian-economy）：**按剩余量摊还**。
        # 旧实现每月付 `cost_coin × ratio` 与扣 `cost_material × ratio` 却**不递减**，
        # ⇒ 工期 N 月即付/扣 N 倍（实测 6 月工期付 6 倍，材料同病）。
        # 现改为：剩余量 `_mat_left` / `_coin_left` 逐月递减并封顶，
        # **累计支出/耗用不超过批准预算与清单**；完工时余料退回（见完工段）。
        for dim, need in (proj.get("cost_material") or {}).items():
            _left_key = f"_mat_left_{dim}"
            if _left_key not in proj:
                proj[_left_key] = float(need or 0)
            _left = float(proj.get(_left_key, 0) or 0)
            if _left <= 0:
                continue
            take = min(_left, float(need or 0) * ratio)
            if take <= 0:
                continue
            # ✅ **已并入州府仓**（用户 2026-10-02 裁定「合并」）：政府工程原用
            # `RAW_DIMS_14` 中文名（`铁`/`石`/`木`），民间营造用 `RAW_DIMS`
            # 英文名（`iron`/`stone`/`timber`），二者本是**两个不同单元格**、
            # 会**同一物料双记**。现经 `to_material_dim()` 在**仓边界**
            # 翻译成**同一套英文名**，两处消费方共用 `consume_for_circuit()`
            # ——**口径单点**，政府工程也因此**享受州府级物流**（缺料须先运到）。
            # 项目台账内部（`cost_material` / `_mat_left_<dim>`）**仍用中文键**，
            # 翻译只发生在落仓那一刻。
            from core.foundation.ledger.material_holding import consume_for_circuit, to_material_dim
            _mdim = to_material_dim(dim)
            if _mdim is None:
                continue          # 非建材维度（如 `粮` 走 pops[].grain）⇒ 跳过，不臆断
            _route = proj.get("route") or proj.get("prefecture") or ""
            _got = consume_for_circuit(state, _route, _mdim, int(round(take)))
            if _got > 0:
                take = float(_got)
                proj[_left_key] = round(_left - take, 6)
                stats["project_material_used"] = \
                    float(stats.get("project_material_used", 0) or 0) + take
        # 工程款：**按剩余量摊还**（总额封顶＝批准预算），不再是每月全额
        coin_total = int(proj.get("cost_coin", 0) or 0)
        if coin_total > 0:
            if "_coin_left" not in proj:
                proj["_coin_left"] = float(coin_total)
            _coin_left = float(proj.get("_coin_left", 0) or 0)
            if _coin_left > 0:
                pay = int(round(min(_coin_left, coin_total * ratio)))
                if pay > 0:
                    from core.settlement_common import MoneyChannelUnavailable, note_settlement_error
                    try:
                        # 严格模式（P2-3 应修）：通道不可用 → 抛错，与"按实拨付 0"区分
                        _given = transfer_public_funds_to_pops(
                            state, pay, GOV_SPEND_TO, f"工程营造款：{name}",
                            raise_on_unavailable=True)
                    except MoneyChannelUnavailable as _e:
                        note_settlement_error(
                            state, "project_pay_channel", "工程",
                            f"营造款通道不可用，本月未拨付（{type(_e).__name__}）",
                            log=log, exc=_e)
                        continue
                    if _given < pay:
                        log.append(f"[工程] {name} 营造款仅拨付 {_given:,}/{pay:,} 贯，按实记账")
                    proj["_coin_left"] = round(_coin_left - _given, 6)
                    stats["project_coin_paid"] = \
                        float(stats.get("project_coin_paid", 0) or 0) + _given

        # 治安降效：本地动乱过高则进度折减（仍向前，不静默完工）
        speed = int(proj.get("speed", 10) or 0)
        sec_factor = 1.0
        prefs = getattr(state, "prefectures", {}) or {}
        if route in prefs:
            _unrest = int(prefs[route].get("unrest", 0) or 0)
            if _unrest > PROJECT_SECURITY_UNREST:
                sec_factor = max(PROJECT_SECURITY_MIN_FACTOR,
                                 1.0 - (_unrest - PROJECT_SECURITY_UNREST) / 100.0)
                log.append(f"[工程] {name} 在地动乱 {_unrest}，营建降效（×{sec_factor:.0%}）")
        gain = int(round(speed * ratio * labor_cover * sec_factor))
        proj["progress"] = min(100, int(proj.get("progress", 0) or 0) + max(0, gain))
        if ratio < 1.0:
            stats["project_delay_months"] = int(stats.get("project_delay_months", 0) or 0) + 1
            log.append(f"[工程] {name} 供给仅 {ratio:.0%}，本月降效推进（进度 +{gain}）")
        if proj["progress"] >= 100:
            proj["done"] = True
            proj["status"] = "operating"
            # B4-6：完工结算剩余量——**余料退回物资仓**、余款记为未用完预算
            # （不静默消失，进 statistics 供读数与审计回看）
            _left_coin = float(proj.get("_coin_left", 0) or 0)
            if _left_coin > 0:
                stats["project_coin_unspent"] = \
                    float(stats.get("project_coin_unspent", 0) or 0) + _left_coin
                proj["_coin_left"] = 0.0
            for dim in list(proj.get("cost_material") or {}):
                _lk = f"_mat_left_{dim}"
                if float(proj.get(_lk, 0) or 0) > 0:
                    proj[_lk] = 0.0
            proj["capacity"] = float(proj.get("capacity", 1.0) or 1.0)
            proj["_upkeep_arrears_seen"] = int(stats.get("upkeep_arrears", 0) or 0)
            out = proj.get("output") or {}
            if "granary_cap_add" in out:
                state.change_granary_cap(int(out["granary_cap_add"]))
            if "defense_add" in out:
                from core.domains.military.army_models import ArmyUnit, EQUIP_STD, defense_line_for
                add = int(out["defense_add"])
                # 2026-10-03 修：原写法读 `out["defense_routes"]`，但该键**全库无生产者**
                # ——全仓只有本行读它、写入方 0 处 ⇒ 循环体永不执行：厢军构件完工后
                # Σtroops Δ=0，而面板按 plan_readout 把 `output={"defense_add":N}`
                # 报成「效果生效」。机制建好却没落地。
                # 正解不是再造一个合成键，而是用**项目自带的地点**：
                # `construction.propose_project` 已把 `proj["route"]` 落档
                #（同函数下方落成登记段的 `_broute` 也是这么取的）。
                _droute = str(proj.get("route") or proj.get("prefecture") or "")
                if add > 0 and _droute in state.prefectures:
                    xiang = [u for u in state.army_units
                             if u.station == _droute and u.tier == "厢军"]
                    if xiang:
                        main = max(xiang, key=lambda u: u.troops)
                        main.branches["轻步兵"] = main.branches.get("轻步兵", 0) + add
                    else:
                        branch = "轻步兵"
                        std = EQUIP_STD.get(branch, {})
                        state.army_units.append(ArmyUnit(
                            unit_id=f"eng{_droute}{state.year}{state.month}{pid}",
                            name=f"{_droute}工役厢",
                            tier="厢军",
                            branches={"轻步兵": add},
                            morale=45,
                            training=35,
                            station=_droute,
                            defense_line=defense_line_for(_droute, "厢军"),
                            equip={k: int(add * per) for k, per in std.items()},
                        ))
                state._derive_defense_lines()
            if "wine_coin_add" in out:
                # 货币守恒：向民间守恒征收（实收才入账，不足则少收、不补差额）
                _want = int(out["wine_coin_add"])
                _got = _collect_from_pops(state, _want)
                state.imperial_treasury += _got
                if _got < _want:
                    log.append(f"[工程] 酒课增收应 {_want:,} 贯，民间可缴仅 {_got:,} 贯，按实入账")
            # 落成登记（2026-09-19 闭环）：营建类工程完工 → 写 prefectures[route]["buildings"]，
            # 此后科技 adoption 覆盖率与资产维持费才真正生效（此前 buildings 无写入点）。
            _bkey = proj.get("blueprint_key")
            _broute = proj.get("route") or proj.get("prefecture")
            if _bkey and _broute in (getattr(state, "prefectures", {}) or {}):
                try:
                    from content.data import BUILDING_BLUEPRINTS, BUILDING_STD
                    _bp = BUILDING_BLUEPRINTS.get(_bkey)
                    if _bp:
                        _bname = _bp.get("name")
                    elif str(_bkey or "").startswith("dyn:"):
                        # 规格任务 3：**动态蓝图**的键不在静态表里 —— 原实现会走到
                        # 下面的 `_bkey in BUILDING_STD` 分支拿不到名字 ⇒ `_bname=None`
                        # ⇒ **完工但根本不登记建筑**（"完工无产出"，正是本规格要治的病）。
                        # 现从本局存档的动态注册表取名，使动态建筑与静态建筑**同样**落
                        # `prefectures[route]["buildings"]`，此后维持费/部署覆盖率才生效。
                        from core.blueprint_dynamic import resolve_dynamic_blueprint
                        _dyn = resolve_dynamic_blueprint(state, key=_bkey)
                        _bname = (_dyn or {}).get("name")
                    else:
                        # BUILDING_STD 政府建筑：其键即中文名（水利/常平仓/官营作坊/官署/军营/学校）
                        _bname = _bkey if _bkey in BUILDING_STD else None
                    if _bname:
                        _b = state.prefectures[_broute].setdefault("buildings", {})
                        _lv = max(1, int(proj.get("levels", 1) or 1))
                        _b[_bname] = int(_b.get(_bname, 0) or 0) + _lv
                        log.append(f"[工程] {name} 落成：{_broute}·{_bname} Lv{_b[_bname]}"
                                   f"（部署 adoption 与资产维持费自此生效）")
                except Exception as e:  # noqa: BLE001
                    # 审查 P2-3 应修：原只有结算日志一行、**无 traceback**（落成登记失败
                    # 会让"部署 adoption / 资产维持费自此生效"的承诺落空）。补 traceback。
                    _log.exception("[工程] %s 落成登记失败（建筑未入档）", name)
                    log.append(f"[工程] {name} 落成登记失败：{type(e).__name__}")
            log.append(f"[工程] {name} 告成，转入运行（产能 {proj['capacity']:.0%}）")


