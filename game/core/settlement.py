# -*- coding: utf-8 -*-
"""宋祚 · 月度结算主流程（合并原 settlement_extensions.py / settlement_reform.py）

结构：
  - run_monthly_settlement 主流水线（Step 0 ~ 11）
  - MECHANISMS 注册表 + 五层承接层月度钩子（机制槽 / 研发管线 / 机构经济生命周期）
  - settle_reform 机构改制后果推演（reform_org 类圣旨）

各 Step 结算函数见 core/settlement_steps.py；本文件 re-export 常用符号保持
既有 import 兼容（commands / panels 等）。
"""
import functools
import random

from content.data import (
    TREASURY_CRISIS_LINE, TREASURY_COLLAPSE_LINE,
    CHANGPING_HIGH, CHANGPING_LOW,
)
from core.game_state import _next_month

from core.settlement_steps import (
    _settle_decrees, _apply_decree_effect,
    _settle_factions,
    _settle_economy, _settle_land_local, _settle_extensions,
    _settle_literacy,
    _settle_longterm_decrees, _simulate_external, _settle_external_economy,
    _settle_granary, _settle_region_deepen,
    _settle_upkeep, _settle_officialdom, _settle_clan, _settle_clerks,
    _settle_finance, _settle_bank_stock,
    _settle_projects, _settle_workshops, _settle_econ_prices,
    _settle_treasury,
    _evaluate_timeline_breaks,
    _settle_military_diplomacy,
    _settle_events,
    _normalize_disaster_region, _settle_disaster,
    _settle_emperor_personal,
    _settle_hidden,
)
# 局势结算步（规范 §4）：实现于 core/situation_settle.py，此处**以私有名导入**，
# 使其与其它 `_settle_*` 步同形——`test_pop_identity.py::_STEPS` 镜像据此逐步比对。
from core.situation_settle import settle_situations as _settle_situations  # noqa: E402

# 利益集团派生结算（方案第 3 步）：实现于 core/faction_settle.py，此处**以私有名导入**，
# 使其与其它 `_settle_*` 步同形——`test_pop_identity.py::_STEPS` 镜像据此逐步比对。
from core.faction_settle import settle_factions_from_pop as _settle_faction_metrics  # noqa: E402

# 🔴 帝王行动开关（2026-10-07 用户裁定，已登记 decisions:IMPERIAL-ACTION-停用）
#   False = 已停用（当前值）；True = 恢复。
#   停用原因：帝王行动尚未定型（「行动矩阵契约 v2」尚无完整玩法口径）。
#   恢复方法：本常量改 True，并去掉 tests/test_imperial_action.py 的 module 级 skip 标记。
IMPERIAL_ACTION_ENABLED = False

from core.settlement_pipeline import (  # noqa: E402
    SettlementStep,
    SettlementPipeline,
    get_default_pipeline,
    get_pipeline_step_pairs,
)

# 兼容旧调用方可能直接引用这些符号
__all__ = [
    "run_monthly_settlement",
    "settle_reform",
    "_apply_decree_effect",
    "_normalize_disaster_region",
    "MECHANISMS",
    "SettlementStep",
    "SettlementPipeline",
    "get_default_pipeline",
    "get_pipeline_step_pairs",
]


# ============================================================
# 五层承接层（原 settlement_extensions.py）
# ============================================================
# 层②机制槽注册表：键为玩家圣旨可声明的机制名，值为结算加成函数标识。
# 仅做轻量、可解释的修正，不替换任何既有结算分支。
MECHANISMS = {
    "复式记账": {"desc": "钱粮出入双簿相核，月结精度提升，隐性亏空下降", "effect": "finance_precision"},
    "运票": {"desc": "票物一致方可核销，转运损耗下降", "effect": "transport_loss_down"},
    "常平粜籴": {"desc": "丰敛歉粜，平抑粮价波动", "effect": "grain_price_smooth"},
    "工训营": {"desc": "召流民为工，训以匠艺，育理工人才", "effect": "train_craftsman"},
    "市舶抽解": {"desc": "海舶抽税，增市舶之利", "effect": "maritime_tax_up"},
}


def _settle_mechanisms(state, log):
    """层②机制槽：依据 state.mechanisms 注册项，施加纯加成/减耗修正。"""
    for mname, m in state.mechanisms.items():
        spec = MECHANISMS.get(mname)
        if not spec:
            continue
        eff = spec["effect"]
        org = m.get("org", "")
        if eff == "finance_precision":
            o = state.central_orgs.get(org)
            if o:
                o["efficiency"] = min(1.2, round(o["efficiency"] + 0.02, 2))
        elif eff == "transport_loss_down":
            state.land["canal_eff"] = min(0.98, state.land.get("canal_eff", 0.7) + 0.01)
        elif eff == "grain_price_smooth":
            if state.grain_price > CHANGPING_HIGH:
                state.grain_price = max(CHANGPING_HIGH, state.grain_price - 2)
            elif state.grain_price < CHANGPING_LOW:
                state.grain_price = min(CHANGPING_LOW, state.grain_price + 2)
        elif eff == "train_craftsman":
            o = state.central_orgs.get(org)
            if o and o.get("net", 0) >= 0:
                for proj in state.tech.get("projects", {}).values():
                    proj["masters"] = proj.get("masters", 0) + 1
        elif eff == "maritime_tax_up":
            # 「市舶抽解」= **提高市舶税率**，由 `_settle_finance` 的**唯一**关税入账通道
            # （从商人 POP wealth 实征入 actual_tax → 国库，钱守恒）于下月增收。
            # 审查 S3：旧实现 `statistics["total_income"] += commerce * 1%` **无任何对手方**
            # （国库未动、商人未扣）→ 凭空记一笔收入（实测 +3,500,010/月），且与关税
            # 唯一通道重复计账（与本段下方 B1 修复属同类）。值域/幅度取单点权威源
            # `content.data.FINANCE_DECIDE_BASE["tariff"]`，不另立数值。
            if state.maritime.get("open"):
                from content.data import FINANCE_DECIDE_BASE as _FDB
                _tf_cfg = _FDB["tariff"]
                _old_tariff = float(state.maritime.get("tariff", 0.10))
                _new_tariff = min(float(_tf_cfg["max"]),
                                  max(float(_tf_cfg["min"]), _old_tariff + float(_tf_cfg["cap"])))
                state.maritime["tariff"] = round(_new_tariff, 4)
                log.append(f"[市舶抽解] 市舶税率 {_old_tariff:.2%} → {_new_tariff:.2%}"
                           f"（关税由户部按实征入国库）")


def _settle_tech(state, log):
    """层③研发管线：tech["projects"] 中可研项目按 资源×时间×人才 推进。"""
    projects = state.tech.get("projects", {})
    if not projects:
        return
    for pname, proj in projects.items():
        if proj.get("done"):
            continue
        masters = proj.get("masters", 0)
        # 审查 O1：`monthly <= 0` 对 NaN **恒为 False**（任何比较与 NaN 都返回 False）
        # → NaN 会穿过这道闸门，到 `:129 int(monthly or 0)` 抛 ValueError、inf 抛
        # OverflowError，**整月结算中断**。现先剔非有限值（缺失/坏值 → 不拨付并留痕）。
        from core.foundation.common.numeric import parse_number as _pn
        monthly = _pn(proj.get("monthly_cost", 0), 0.0)
        if not (monthly > 0):
            if proj.get("monthly_cost") is not None and proj.get("monthly_cost") != monthly:
                log.append(f"[科技] 项目「{pname}」月费读数非法（{proj.get('monthly_cost')!r}），本月不拨付")
            continue
        # 研发月费：国库 → 学者/工匠 POP 的**守恒转移**（整改④.2；不得无对手方销毁）
        from content.data import TECH_RESEARCH_PAY_TO
        from core.settlement_steps import transfer_public_funds_to_pops
        from core.settlement_common import MoneyChannelUnavailable, note_settlement_error
        _need = int(monthly or 0)
        try:
            # 严格模式（P2-3 应修）：通道不可用 → 抛错，与"合法 0 拨付"区分开，
            # 不得把"写入通道坏了"记成"月费不济"（那是两件完全不同的事）。
            _paid = transfer_public_funds_to_pops(
                state, _need, TECH_RESEARCH_PAY_TO, f"研发月费：{pname}",
                raise_on_unavailable=True)
        except MoneyChannelUnavailable as _e:
            note_settlement_error(
                state, "tech_layer3_channel", "研发",
                f"经费通道不可用，本月进度停滞（{type(_e).__name__}）",
                log=log, exc=_e)
            continue
        if _paid >= _need:
            talent = 1.0 + min(masters, 20) * 0.1
            proj["progress"] = proj.get("progress", 0) + int(50 * talent)
            if proj["progress"] >= 1000:
                proj["progress"] = 1000
                proj["done"] = True
                log.append(f"[研发] {pname} 研成！匠术精进，国力稍增")
                if "unlocked" not in state.tech:
                    state.tech["unlocked"] = []
                if pname not in state.tech["unlocked"]:
                    state.tech["unlocked"].append(pname)
        else:
            log.append(f"[研发] {pname} 月费不济（需 {monthly}贯，实拨 {_paid}贯），进度停滞")


def _settle_org_economy(state, log):
    """层④机构经济生命周期（2026-09-22 守恒化：货币口径规范 §13.9 方案 B）。

    旧口径缺陷：`net = int(budget_in − budget_out)` 直入国库——拨款额度从未流出过，
    逐机构取整后 ≈+39 贯/月凭空生钱（60 月审计残差 +2,360 贯唯一来源）。
    新口径（同周期借→清，无在途余额）：
      月初拨出：Σin 离开国库（度支拨款在途，月末归零）；
      月末结清：实际支出 Σout 走 burn 通道（机构运营消耗，真实销毁），
      余额 Σin−Σout 回缴国库（可为负 = 超支补拨）。
    国库净变化 = −Σout，对账残差恒 0。`o["net"]` 语义随之改为
    「国库净变化」= −int(out_i)；审计测试 test_wealth_ledger_no_hoard /
    test_pop_identity 继续按 org 步 ΔW == Σnet 断言。
    仍受 TREASURY_COLLAPSE_LINE 约束（不可绕过 game_over）；幅度为个位贯级
    的机构财政生命周期记账。
    """
    total_in = 0
    total_out = 0
    for oname, o in state.central_orgs.items():
        if o.get("abolished"):
            o["budget_in"] = o["budget_out"] = o["net"] = 0
            continue
        base_grant = 2 + len(o.get("matter_keys", [])) * 1
        o["budget_in"] = base_grant
        out = 1 + len(o.get("posts", [])) * 0.5 + len(o.get("branches", {})) * 0.3
        o["budget_out"] = round(out, 2)
        _oi = int(round(o["budget_out"]))          # 实际支取出账（整数贯；"文"级不进国库）
        o["net"] = -_oi                            # 国库净变化 = −实际支出（在途已清）
        total_in += int(o["budget_in"])
        total_out += _oi
    if total_in:
        state.change_treasury(-total_in)          # 月初拨出：度支拨款（在途）
    _back = total_in - total_out
    if _back:
        state.change_treasury(_back)              # 结余回缴 / 超支补拨
    if total_out:
        # 审查 P2-3 / M8：原为 `except Exception: pass  # 台账登记失败不影响结算`——
        # 注释是误导：未登记的销毁额会被 `core/money.reconcile` 算成**残差**，
        # 面板于是显示"存在无对手方的造币/销毁"，把登记 bug 说成造币 bug。
        from core.settlement_common import register_money_flow
        register_money_flow(state, "burn", total_out, "机构运营支出（预算实付）")
    org_net = sum(o.get("net", 0) for o in state.central_orgs.values() if not o.get("abolished"))
    state.statistics.setdefault("org_net", 0)
    state.statistics["org_net"] = round(org_net, 2)
    log.append(f"[机构经济] 拨款 {total_in} 实支 {total_out} 回缴 {_back}（burn 通道）")


def _settle_legacies(state, log):
    """帝国修正（legacies）月度结算：施加效果 + 判定消除条件。

    参考《明末：捞金模拟器》的帝国修正机制。开局即存在的条件式长期修正符，
    带明确消除条件，让开局有历史包袱与破局目标。AI 缺失时程序兜底不伪造。

    审查 P2-3 / M7：原实现 `except Exception: pass` —— 整步不生效而日志一字无，
    玩家看到的是"这个月什么也没发生"。现改为**结算日志一行（玩家可见）＋
    `logging` traceback（开发者可定位）**，并按步位命名（防与其它步混淆）。
    """
    try:
        from core.domains.politics.legacy_mechanic import settle_legacies
        settle_legacies(state, log)
    except Exception as e:  # noqa: BLE001 — 不得静默跳过整步
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "legacies", "帝国修正",
            f"本月帝国修正未结算：{type(e).__name__}（效果未施加、消除条件未判定）",
            log=log, exc=e, level="exception")


def _settle_focus(state, log):
    """国策树（focus）月度结算：对已解锁节点施加长期效果。

    参考《明末：捞金模拟器》的国策树机制。五大分支（政务/军事/科学/内卫/税务），
    带权力等级、互斥分支、解锁建筑与长期效果。AI 缺失时程序兜底不伪造。

    审查 P2-3 / M7：同上——国策长期效果整步不生效必须可见，不得静默跳过。
    """
    try:
        from core.focus_mechanic import settle_focus
        settle_focus(state, log)
    except Exception as e:  # noqa: BLE001 — 不得静默跳过整步
        from core.settlement_common import note_settlement_error
        note_settlement_error(
            state, "focus", "国策",
            f"本月国策长期效果未结算：{type(e).__name__}（进度/度支/分支效果未施加）",
            log=log, exc=e, level="exception")


# ============================================================
# 机构改制结算（原 settlement_reform.py）
# ============================================================
def _reject_reform(reason: str) -> dict:
    """机构改制拒绝式返回（不写 state；供 issue_free_decree/UI 显示真实原因）。"""
    return {
        "ok": False,
        "outcome": "rejected",
        "court_report": f"法统门禁阻断：{reason}",
        "gazette": "",
        "loyalty_delta": {},
        "org_effects": {},
        "faction_effects": {},
        "rejected_reason": reason,
    }


def settle_reform(state, decree: dict, executor=None) -> dict:
    """结算一道 reform_org 类圣旨的后果。

    **C-2 权限边界**：机构改名/裁撤/新建/改下辖/改权限属于官制事权，必须由掌
    「官吏铨选」的主体执行；未指定 executor 或非掌权者一律拒绝（fail-closed），
    绝不把客户端/AI 自报的 reform 直接写进 `central_orgs`/`authority_matters`。

    后果完全由 AI 依「威望 + 相关大臣隐藏忠诚度 + 派系立场」推演决定，
    不做写死的规则拒绝。返回叙事字典供 UI 展示（绝不泄露忠诚度数值）。
    """
    reform = decree.get("reform") or {}
    if not isinstance(reform, dict) or not reform:
        return _reject_reform("改制契约为空或非法")
    executor = executor or decree.get("executor") or decree.get("executor_hint")
    if not executor:
        return _reject_reform("改制须指定执行主体（掌「官吏铨选」的部门/官职/任职人）")
    try:
        from core.authority_gate import check_matter_authority
        _ok, _label = check_matter_authority(state, executor, "官吏铨选")
    except Exception as e:  # noqa: BLE001
        return _reject_reform(f"执行主体核验异常（{type(e).__name__}）：{e}")
    if not _ok:
        return _reject_reform(f"执行主体核验失败：{_label}")
    # 2026-09-27：原在此组装 reform_settle 提示词上下文（算完即弃）；该模板与
    # `authority_brief_for_ai` 已按「如无必要勿增实体」一并移除（审查报告 §14.1/§14.2）。
    target = reform.get("target_org", "")
    matter = reform.get("matter", "")

    related = set()
    if target and target in state.central_orgs:
        lead = state.central_orgs[target].get("lead")
        if lead:
            related.add(lead)
    if matter and matter in state.authority_matters:
        owner = state.authority_matters[matter].get("owner", "")
        if owner in state.central_orgs:
            l = state.central_orgs[owner].get("lead")
            if l:
                related.add(l)
    related = list(related)



    # 优先用结算前注入的 _reform_ai 槽位；无则本地兜底（禁止结算路径同步 HTTP）
    res = getattr(state, "_reform_ai", None)
    if isinstance(res, dict) and not res.get("_error"):
        res = res.get("result") if isinstance(res.get("result"), dict) else res
    else:
        res = _fallback_reform(state, reform, related)
    _apply_reform_result(state, decree, reform, res, related)
    return res


def _apply_reform_result(state, decree, reform, res, related):
    """把 AI 推演结果回写：隐藏忠诚度变动、机构运行联动、机构树变更、派系联动。"""
    for name, delta in res.get("loyalty_delta", {}).items():
        if name in state.loyalty and isinstance(delta, (int, float)):
            state.loyalty[name] = max(0.0, min(1.0, state.loyalty[name] + float(delta)))

    for name, delta in res.get("corruption_delta", {}).items():
        if name in state.corruption and isinstance(delta, (int, float)):
            state.corruption[name] = max(0.0, min(1.0, state.corruption[name] + float(delta)))

    for oname, eff in res.get("org_effects", {}).items():
        o = state.central_orgs.get(oname)
        if not o:
            continue
        if "efficiency" in eff and isinstance(eff["efficiency"], (int, float)):
            o["efficiency"] = max(0.1, round(o["efficiency"] + float(eff["efficiency"]), 2))
        if "backlog" in eff and isinstance(eff["backlog"], (int, float)):
            o["backlog"] = max(0, int(o["backlog"] + float(eff["backlog"])))

    fe = res.get("faction_effects", {})
    fs = decree.setdefault("faction_stances", {})
    for fname, d in fe.items():
        if isinstance(d, (int, float)):
            fs[fname] = max(-1.0, min(1.0, float(fs.get(fname, 0)) + float(d)))

    rtype = reform.get("reform_type", "")
    target = reform.get("target_org", "")
    if rtype == "改名" and target in state.central_orgs and reform.get("new_name"):
        state.central_orgs[reform["new_name"]] = state.central_orgs.pop(target)
    elif rtype == "裁撤" and target in state.central_orgs:
        state.central_orgs[target]["abolished"] = True
        state.central_orgs[target]["efficiency"] = 0.0
        state.central_orgs[target].setdefault("comissions", [])
    elif rtype == "新建" and reform.get("new_org"):
        new_org = reform["new_org"]
        branches = reform.get("branches") or []
        matter_raw = reform.get("matter", []) or []
        matter_keys = [matter_raw] if isinstance(matter_raw, str) else list(matter_raw)
        state.central_orgs[new_org] = {
            "lead": "", "belong": "皇帝", "scope": reform.get("new_name", "新置机构"),
            "authority": [], "matter_keys": matter_keys, "posts": [], "holders": {},
            "comissions": [], "abolished": False,
            "efficiency": 0.6, "backlog": 0,
            "branches": {road: [f"{new_org}·{road}分司"] for road in branches},
            "budget_in": 0, "budget_out": 0, "net": 0,
        }
        for road in branches:
            if road in state.prefectures:
                state.prefectures[road].setdefault("orgs", [])
                if new_org not in state.prefectures[road]["orgs"]:
                    state.prefectures[road]["orgs"].append(new_org)
        for m in (reform.get("mechanisms") or []):
            if m in MECHANISMS and m not in state.mechanisms:
                state.mechanisms[m] = {"org": new_org, "params": {}, "progress": 0}
    elif rtype == "新建官职" and target in state.central_orgs and reform.get("new_post"):
        org = state.central_orgs[target]
        org.setdefault("posts", [])
        org.setdefault("holders", {})
        post_title = reform["new_post"]
        if not any(p.get("title") == post_title for p in org["posts"] if isinstance(p, dict)):
            org["posts"].append({"title": post_title})
            holder = reform.get("holder", "") or ""
            org["holders"][post_title] = holder
            if not org.get("lead"):
                org["lead"] = holder
    elif rtype == "改下辖" and target in state.central_orgs and reform.get("new_belong"):
        state.central_orgs[target]["belong"] = reform["new_belong"]
    elif rtype in ("改权限", "越权授权") and reform.get("matter") and reform.get("new_owner"):
        m = reform["matter"]
        if m in state.authority_matters:
            state.authority_matters[m]["owner"] = reform["new_owner"]


def _fallback_reform(state, reform, related) -> dict:
    """AI 不可用时的极简退路：仅依威望与（隐藏）忠诚度给定性后果，绝不暴露数值。"""
    pi = state.get_prestige_info()
    level = pi.get("level", "中")
    avg = sum(state.loyalty.get(n, 0.5) for n in related) / len(related) if related else 0.5
    if level in ("高", "极高") and avg >= 0.6:
        outcome = "smooth"
        report = "诏下，相关衙门奉命惟谨，事权更易井然。"
    elif avg < 0.4:
        outcome = "sabotage"
        report = "诏书虽颁，然有臣僚迁延观望，政务颇有积压。"
    else:
        outcome = "evade"
        report = "诸司受诏，外示奉行而内多斟酌，推行稍缓。"
    # 记忆知识库（Phase 3a）：机构改制写入图谱（org 实体 + governs）
    try:
        target = reform.get("target_org", "")
        rtype = reform.get("reform_type", "")
        if target:
            state.memory.add_entity(f"org_{target}", "org", target, turn=state.turn)
            state.memory.add_relation(f"org_{target}", f"reform_{rtype}",
                                      "governs", weight=1.0, turn=state.turn,
                                      note=f"{rtype}·{outcome}")
    except Exception:
        pass
    return {
        "outcome": outcome,
        "court_report": report,
        "gazette": "朝廷更定官制，以肃庶务。",
        "loyalty_delta": {},
        "org_effects": {},
        "faction_effects": {},
    }


# ------------------------------------------------------------
# 主流水线
# ------------------------------------------------------------
def _isolated_rng(fn):
    """装饰器：结算期间播种全局 RNG，**结束后还原**（对外零副作用，内部仍按回合确定）。

    为什么用装饰器而不是"wrapper + 改名"：`test_econ_price_review` / `test_middle_calibration`
    以内省 `run_monthly_settlement` 的**源码/AST**守护流水线步序与测试镜像；把函数体挪走会让
    这两条安全网失效（改完当场变红）。装饰器下函数体仍在原函数内，且 `inspect.getsourcelines`
    会 `unwrap()`（`functools.wraps` 设了 `__wrapped__`）→ 内省拿到的仍是真实流水线。
    """
    @functools.wraps(fn)
    def _wrapper(state, seed_offset: int = 0):
        _saved = random.getstate()
        random.seed(state.turn * 1000003 + seed_offset)
        try:
            return fn(state, seed_offset)
        finally:
            random.setstate(_saved)
    return _wrapper


@_isolated_rng
def run_monthly_settlement(state, seed_offset: int = 0) -> list:
    """执行月度结算，返回本轮结算日志列表。

    seed_offset 用于确定性复现：以 (state.turn + seed_offset) 派生随机种子，
    使相同回合+offset 的结算结果可复现，为 dev/replay 回放与平衡 A/B 对比打基础。

    **地基（2026-09-27）**：结算结束必须**还原全局随机流**（由 `@_isolated_rng` 负责）。
    原实现直接 `random.seed(...)` 播种全局 RNG 且不还原 —— 实测污染调用方后续随机序列
    （结算前抽 `[0.41662, 0.010169, 0.825207]`，结算后变成 `[0.481827, 0.610136, 0.673403]`）。
    """
    log = []

    # 局势 intent 校验用：本回合 `state_applier` 事务记录的起始游标（§5.2）。
    # 必须在这里取——Step 1 诏令执行起就会向 CHANGE_LOG 追加本回合变更。
    try:
        from engine.state_applier import CHANGE_LOG as _CHANGE_LOG
        _situation_journal_base = len(_CHANGE_LOG)
    except Exception:  # noqa: BLE001
        _situation_journal_base = 0

    # 更新年号
    state.update_era_name()

    # 钱在途到期入账（G-3/P4a，2026-10-18）：无在途批次时是**空操作**，零行为变更。
    # 放在结算最前：本月打款上月到期的钱先入账，再跑本月支出/收入。
    try:
        from core.foundation.ledger.money_transport import arrive_money_due as _arrive_money
        _arrived = _arrive_money(state)
        if _arrived:
            _sum = sum(int(b.get("qty", 0) or 0) for b in _arrived)
            log.append(f"[钱运] 在途钱款到账 {len(_arrived)} 批 / {_sum} 贯")
    except Exception as _me:  # noqa: BLE001 —— 测量仪器不得中断结算
        log.append(f"[钱运][WARN] 到账处理失败：{_me!r}")

    # ---- V3 建筑分级升级：每月推进在建（队列空 ⇒ 零行为变更）----
    try:
        from core.domains.construction.building_upgrade import advance_building_construction as _abc
        _done = _abc(state)
        for _item in _done or ():
            log.append("[营造] %s / %s 升至 %s 级" % (_item.get("route"), _item.get("name"),
                                                    _item.get("level")))
    except Exception as _bld_exc:  # noqa: BLE001
        import logging as _lg
        _lg.getLogger(__name__).warning("建筑升级推进失败：%r", _bld_exc, exc_info=True)

    # ---- P8 商人自主投资（2026-10-18；Jev：默认关 0.676）----
    # 开关 MERCHANT_INVEST_ENABLED=0 时**零行为变更**；开=1 才让商人按天道档位买船/车/扩品类。
    try:
        from content.data_constants import MERCHANT_INVEST_ENABLED as _MINV
        if int(_MINV or 0):
            from core.domains.economy.pop_investment import settle_merchant_investment as _smi
            _inv = _smi(state)
            if _inv.get("done"):
                log.append("[商投] %s：提案 %d、成交 %d（失败 %d）" % (
                    _inv.get("posture"), int(_inv.get("planned") or 0),
                    int(_inv.get("done") or 0), int(_inv.get("failed") or 0)))
    except Exception as _inv_exc:  # noqa: BLE001 —— 投资失败必须留痕，不得静默
        import logging as _lg
        _lg.getLogger(__name__).warning("商人投资结算失败：%r", _inv_exc, exc_info=True)
    from core.asset_context import era_switch
    era_switch(state)

    # ---- Step 0: 破产兜底（在其它步骤补血国库前，先按真实财政恶化程度判定）----
    # B3：国库禁穿底，改以「累计亏空深度」为判据（详见 GameState.deficit_depth）。
    # 2026-10-17 审计修复（B-2）：与 _settle_finance 统一采用天道动态危机线判据，消除双判据漂移
    from core.ai.tiandao_facade import TianDaoFacade
    crisis_line = TianDaoFacade.dynamic_treasury_crisis_line(state)
    collapse_line = crisis_line * 2

    if state.deficit_depth() > collapse_line:
        state.game_over = True
        state.game_result = "国用耗竭，天下鼎沸——大宋府库空虚，纲纪尽弛"
        log.append("[民生] 国库崩坏至不可复救，国用耗竭，天下鼎沸！")
        return log
    if state.deficit_depth() > crisis_line and not any(
            e.get("title") == "库藏空虚" for e in state.active_events):
        state.population_satisfaction = max(0, state.population_satisfaction - 2)
        log.append("[民生] 库藏空虚，中外忧惧，民怨渐起")
        crisis = {
            "title": "库藏空虚",
            "category": "crisis",
            "desc": "国库亏空日深，府库空虚，中外忧惧。陛下当决断出处：",
            "choices": [
                {"text": "增征商税，权宜聚财", "effects": {"commerce_tax": 0.30}},
                {"text": "裁汰冗费，省浮节流", "effects": {"curtail_waste": 1}},
                {"text": "发内帑，以私蓄济公",
                 "effects": {"treasury": min(state.imperial_treasury, 5000000),
                             "imperial_treasury": -min(state.imperial_treasury, 5000000)}},
                {"text": "卖度牒，权宜救急", "effects": {"treasury": 1000000}},
            ],
        }
        state.active_events.append({"title": crisis["title"], "message": crisis["desc"], "choices": crisis["choices"]})

    # ---- 声明式结算管线调度（Phase 1 ~ Phase 9，覆盖全部48个子步骤）----
    pipeline = get_default_pipeline()
    pipeline.execute(state, log, _situation_journal_base=_situation_journal_base)

    # ---- 外邦州府人口月末重摊（2026-10-20）：任何步骤改了省人口后，
    # 在此统一按省精确重摊到州府，保证「Σ州府 == 省」（60 月回放曾 7 条失配）。
    # 只动外邦 T1 的 pop（宋详账在 prefectures，不受影响）；失败留痕不阻断。
    try:
        from core.foundation.ledger.region_registry import distribute_regime_pops
        distribute_regime_pops(state, force=True, reset=True)
    except Exception as _rd_err:  # noqa: BLE001
        log.append('[外邦] 州府人口月末重摊失败：%r' % (_rd_err,))

    # ---- Step 10.9: 货币口径对账（阶段 B-1；**只读视图**，不改任何货币账户）----
    # 把本月各账户余额与上月末对比：`ΔM_ALL  = 外部净注入（白银流入）− 销毁 ＋ 残差`，
    # 残差 ≠ 0 即表示存在**无对手方的造币/销毁**。这正是审查 A-2（穿底造币）、
    # A-4（畜栏产肉无买方）、A-5（酒课无上限累加）、D-6（常费转负）长期存活的根因——
    # 此前游戏没有货币总量口径，无处可查。见 core/money.py 与 货币口径规范_M0M1M2.md。
    try:
        from core.foundation.ledger.money import audit_step as _money_audit_step
        _money_audit_step(state)
    except Exception as _money_err:  # noqa: BLE001 — 对账崩溃不拖垮结算，但必须响亮可见
        # P1-19：原静默「跳过」→ 对账可连续数月失效而无人知。现 ERROR 落档 + 持久计数。
        import logging as _logging
        _logging.getLogger("songzuo.money").exception("货币对账失败（必须修复）")
        log.append(f"[货币对账][ERROR] 对账失败（非跳过）：{_money_err!r}")
        _audit = getattr(state, "money_audit", None)
        if not isinstance(_audit, dict):
            _audit = {}
            state.money_audit = _audit
        _audit["last_error"] = repr(_money_err)
        _audit["error_count"] = int(_audit.get("error_count", 0)) + 1

    # ---- Step 11: 记录与回合推进 ----
    # 将月份/年份推进收敛到结算函数内部，确保与 Rust 后端（settle.rs）的推进位置一致，
    # 避免 commands 层再次推进导致双端月份各推一次的漂移。
    state.settlement_log.append(log)
    # ---- Step 11.5: 月度奏章八章（批 3 · 明末经验）----
    # 固定八章 + 章末七言联 + ▲▼ 差值摘要；只读组装，失败不阻断回合推进。
    try:
        from core.domains.administration.monthly_gazette import build_monthly_gazette
        _gaz = build_monthly_gazette(state, year=state.year, month=state.month)
        _hist = getattr(state, "monthly_gazette", None)
        if not isinstance(_hist, list):
            _hist = []
        _hist.append(_gaz)
        if len(_hist) > 12:
            del _hist[:-12]
        state.monthly_gazette = _hist
    except Exception as _gaz_e:  # noqa: BLE001
        log.append(f"[邸报][WARN] 八章组装失败：{_gaz_e!r}")
    state.turn += 1
    state.year, state.month = _next_month(state.year, state.month)
    state.update_era_name()
    # 金融推演价格系数：月度重置（不落档，运行时态；下月按新金融词重新调制）
    state._price_mult = 1.0

    return log
