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

# 兼容旧调用方可能直接引用这些符号
__all__ = [
    "run_monthly_settlement",
    "settle_reform",
    "_apply_decree_effect",
    "_normalize_disaster_region",
    "MECHANISMS",
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
def settle_reform(state, decree: dict) -> dict:
    """结算一道 reform_org 类圣旨的后果。

    后果完全由 AI 依「威望 + 相关大臣隐藏忠诚度 + 派系立场」推演决定，
    不做写死的规则拒绝。返回叙事字典供 UI 展示（绝不泄露忠诚度数值）。
    """

    reform = decree.get("reform") or {}
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
    from core.asset_context import era_switch
    era_switch(state)

    # ---- Step 0: 破产兜底（在其它步骤补血国库前，先按真实财政恶化程度判定）----
    # B3：国库禁穿底，改以「累计亏空深度」为判据（详见 GameState.deficit_depth）。
    if state.deficit_depth() > TREASURY_COLLAPSE_LINE:
        state.game_over = True
        state.game_result = "国用耗竭，天下鼎沸——大宋府库空虚，纲纪尽弛"
        log.append("[民生] 国库崩坏至不可复救，国用耗竭，天下鼎沸！")
        return log
    if state.deficit_depth() > TREASURY_CRISIS_LINE and not any(
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

    # ---- Step 1: 诏令执行 ----
    _settle_decrees(state, log)

    # ---- Step 2: 派系结算 ----
    _settle_factions(state, log)

    # ============================================================
    # 经济相位（整改①-1 固定回合顺序）：
    #   生产 → 工程投入 → POP收入消费 → 粮食商品市场 → 税收转移
    #   → 货币信用 → 物价 → 集团读数 → 提交
    # 说明：现行步骤是单函数多相位（如 `_settle_granary` 含「POP 消费 + 粮食市场」、
    # `_settle_finance` 含「俸禄入 POP + 税收转移」），故按**相对顺序**落实，不拆函数：
    # 生产段 → 工程段 → 市场段 → 税收段 → 货币信用段 → 物价段 → 集团读数段。
    # 失败整月回滚：异常由 `core/commands.settle_local` / `advance_and_settle`
    # 在本函数外包裹快照，抛出时整月回滚、回合不推进。
    # ============================================================

    # ---- [生产] Step 3: 经济（人口→田土→工商） ----
    _settle_economy(state, log)

    # ---- [生产] Step 3.5: 田亩与地方州县 ----
    _settle_land_local(state, log)

    # ---- [生产] Step 3.5.2: 农业投资效果（B2-R4 · 2026-10-11 接线）----
    # 放在 `_settle_land_local` 之后、`_settle_region_deepen` 之前：
    # ① 紧随收获分配/田赋 ⇒ 增产**不二次计税**（与"田赋按核定田亩"不冲突）；
    # ② 早于 Step 4.5 的粮市撮合 ⇒ 同月即形成可售粮与农户收入；
    # ③ 晚于 `_settle_economy` ⇒ 人口/阶层流动先于增产落账。
    # 口径：增产只落 `pops["农"]["grain"]`；四项成本（土地/材料/工时/维护）
    # **先扣后产**，最短板降效，**不存在零成本增产**；从不给 POP 加 wealth。
    try:
        from core.domains.production.settlement_agri import apply_agri_effects
        apply_agri_effects(state, log)
    except Exception as _ae_e:      # noqa: BLE001 — 农业效果失败不阻断结算
        log.append(f"[农业][WARN] 投资效果结算失败：{_ae_e!r}")

    # ---- [生产] Step 3.5.5: 地区模型深化（民心/士绅抵抗/城防/财政） ----
    _settle_region_deepen(state, log)

    # ---- [生产] Step 3.5.6: 识字率缓动（2026-09-19 新增；教育慢变量，诏令效果弱关联项）----
    _settle_literacy(state, log)

    # ---- Step 3.7: 长期拟旨（公开 / 密令）推进与外部政权简单模拟 ----
    _settle_longterm_decrees(state, log)
    _simulate_external(state, log)

    # ---- [工程投入] Step 4.5: 工程 / 制作系统 ----
    # 顺序修正（整改①-1）：工程投入必须排在粮食市场与税收之前——工程量在当月
    # 形成产能/耗料/占款，才能被当月市场与财政读到。
    # Step 4.4 产出链（批 4 S1）：原料 yields 年额/12 × 建筑乘数 → state.resources
    # （消除「原料只出不进」缺口；须在作坊耗料之前入仓）。
    try:
        from core.domains.production.production_chain import settle_production_chain
        settle_production_chain(state, log)
        # 🔴 Y 轨（用户 2026-10-05 裁定）：农家产物先归农户，官府**和买**后方入官仓供工坊。
        # 钱货同时转移；未买走的仍归农户（不无偿入库）。
        try:
            from core.domains.production.farm_procurement import procure_from_farmers
            procure_from_farmers(state, log)
            # 丙（用户 2026-10-05 裁定）：农户余料向本路商人售出（民间售料）。
            # 钱货同时；成交受商人资金约束 ⇒ 自限。
            try:
                from core.domains.production.farm_procurement import sell_surplus_to_merchants
                sell_surplus_to_merchants(state, log)
            except Exception as _ms_e:  # noqa: BLE001
                log.append("[民间售料] [WARN] %r" % (_ms_e,))
        except Exception as _fp_e:  # noqa: BLE001
            log.append("[和买][WARN] 采购失败：%r" % (_fp_e,))
    except Exception as _pc_e:  # noqa: BLE001
        log.append(f"[产出链][WARN] 原料入仓失败：{_pc_e!r}")

    # ---- [建材供给] Step 4.45: 建材**入商人货栈**（口径 E-1）----
    # 排在 Step 4.4 产出链之后 ⇒ 搬的是**已含本月产出**的全国仓总量；
    # 排在 Step 3.85 民间营造与 Step 4.5 工程之前 ⇒ 消费侧读到的是**已配货**的商人。
    #
    # 🔴 E-1（用户 2026-10-02「建材也是商品啊」）：建材是**商品**，存量落在
    # **商人 POP `goods`**（POP 挂载律），商人因此有囤货与定价动机；
    # 施工侧（C-c）仍**只从本地取、取不到即缺料** ⇒ 物流仍有意义。
    # 本步只把 `state.resources[dim]["stock"]` **搬到商人**，**总量守恒、不凭空增物**。
    try:
        # 🔴 G-2 收口：走 `supply_goods_to_seats`（**全商品**入州府桶），
        # 取代只服务建材三维的旧入口 `supply_merchant_materials`。
        # 旧入口保留为**历史 API**（外部若有引用不致断裂），但不再走流水线。
        from core.foundation.ledger.material_holding import supply_goods_to_seats
        supply_goods_to_seats(state)
    except Exception as _mh_e:  # noqa: BLE001
        log.append(f"[供给][WARN] 商品配货失败：{_mh_e!r}")

    # ---- [建材在途] Step 4.46: 本月到期的建材批次入账（P0 · 2026-10-02）----
    # 🔴 C-c「只从本地取、取不到即缺料」要成立，**必须能观测"运没运到"** ⇒ 需要在途。
    # 排在 Step 4.45 配货**之后**：这样"本月新发货"与"本月到货"都能被读到；
    # 排在消费侧（Step 3.85 / 4.5）**之前** ⇒ 当月到货当月即可用。
    try:
        from core.transport import arrive_due
        _arrived = arrive_due(state)
        if _arrived:
            _tot = sum(int(b.get("qty", 0) or 0) for b in _arrived)
            log.append(f"[建材在途] 本月到货 {_tot} 件（{len(_arrived)} 批）")
    except Exception as _tr_e:  # noqa: BLE001
        log.append(f"[建材在途][WARN] 到货结算失败：{_tr_e!r}")

    # ---- [建材采购] Step 4.47: 商人**补货下单**（E-1 的囤货动机落地）----
    # 排在 4.46 到货**之后**：先把本月到的算进存量，再判断还缺不缺。
    # 🔴 建材是商品（E-1）⇒ 商人有囤货动机；C-c ⇒ 货必须**走在途**，不能瞬移。
    # 每月只跑一次；失败只记 WARN，不阻断结算。
    try:
        from core.material_trade import procure_materials
        _proc = procure_materials(state)
        if _proc.get("bought"):
            _b = sum(int(x["qty"]) for x in _proc["bought"])
            log.append(f"[建材采购] 本月下单 {_b} 件（{len(_proc['bought'])} 笔，均为在途）")
    except Exception as _pm_e:  # noqa: BLE001
        log.append(f"[建材采购][WARN] 补货下单失败：{_pm_e!r}")

    _settle_projects(state, log)
    _settle_workshops(state, log)

    # ---- [民间营造] Step 3.85: B4-7 民间自发造房（2026-11 接线）----
    # 排在 Step 4.4 产出链之后 ⇒ 本月入仓的建材当月可用；
    # 排在 Step 3.9 `_settle_upkeep` 之前 ⇒ 新造民居/货栈**当月即进资产维持费**
    # （否则出现"造完当月免维护"的漏洞）。
    # 口径：料真扣 `state.resources`、钱经`transfer_money` 由出资阶层划转本路工匠
    #（**有付款对手方**）、工时只记 `statistics`；**全程不写任何 POP `size`**。
    try:
        from core.civil_building import apply_civil_construction
        apply_civil_construction(state, log)
    except Exception as _cb_e:      # noqa: BLE001 — 民间营造失败不阻断结算
        log.append(f"[营造][WARN] 民间营造触发结算失败：{_cb_e!r}")

    # ---- [工程运行维护] Step 3.9: 资产维持费（L1 money sink，B-3）----
    _settle_upkeep(state, log)

    # ---- [粮食商品市场 + POP消费] Step 3.8: 仓廪漕运 / 常平籴粜 / 粮市 / 各POP消费 ----
    _settle_granary(state, log)

    # ---- Step 3.95: 官制（消灭 officials/POP 双账 + 子池一致性 + 镜像同步）----
    # 必须排在财政步之前：`calc_official_*` / `calc_clerk_*` 读的就是这里刷新后的官额与子池。
    _settle_officialdom(state, log)

    # ---- Step 3.96: 宗室俸禄（L2c sink，内帑 → 士绅 POP，零残差转移）----
    _settle_clan(state, log)

    # ---- Step 3.97: 吏制（吏额由政务量驱动 / 吏禄→陋规 / 把持度 / 吏怨，§16）----
    # 必须排在财政步之前：俸禄与贪腐要读**本月**吏额与吏怨。
    # 注（2026-09-18 结算步专项检查更正）：Step 1 诏令执行用的把持度折扣读的是**上月**
    # 吏治状态（`clerks.decree_execution_mult` 由本步在上月写入）。这是**构造性滞后 1 月**，
    # 不是 bug —— 吏治是存量、月度结算一次，诏令执行时本月吏治尚未结算。原注释称
    # "诏令执行也要读本月吏额与吏怨"与实现不符，已更正。
    _settle_clerks(state, log)

    # ---- [税收转移 + POP收入] Step 4: 财政 ----
    # 税从 POP wealth/grain 征（先改 POP、再入国库）；俸禄按实付回流兵/官僚 POP；
    # 禁止直接给集团发钱（集团读数由下方 Step 5.5 从 POP 实际变化派生）。
    _settle_finance(state, log)

    # ---- [外邦经济] Step 4.1: 辽/西夏月度经济循环（2026-09-19）----
    # 位置：紧随宋财政之后——岁币本月入辽/夏库藏（_settle_finance 岁币落账），
    # 随即参与其税饷/粮市循环，同月闭环。外邦账户不在宋 ACCOUNTS，
    # 宋 M_ALL 对账不受影响（岁币仍为 burn）。
    _settle_external_economy(state, log)

    # ---- [货币信用] Step 4.2: 扩展维度自然演进（交子/铸币/熔化/金融/科举/科技/外交）----
    # 顺序修正（整改①-1）：货币信用排在税收之后——税率/税额先落账，货币发行与
    # 信用变化再影响物价（由下方物价相位读取），避免“先通胀再收税”的次序倒置。
    _settle_extensions(state, log)

    # ---- [物价] Step 4.3: 物价相位（整改①-3）----
    # 由货币有效供给/供需/库存/运输派生路线粮价；全国 PRICE_LEVEL 仅加权读数，月度上限。
    _settle_econ_prices(state, log)

    # ---- Step 5: 国库 ----
    _settle_treasury(state, log)

    # ---- [集团读数] Step 5.5: 利益集团指标由 POP 派生（方案第 3 步）----
    # 位置：生产/工程/市场/税收/货币信用/物价**之后**——文档要求
    # “满意度在 POP、财政、制度结算后计算”，且“最终利益集团只读取 POP 实际变化”。
    # `state.factions` 的**唯一写入点**；本步之前任何对满意度的直写（事件/诏令/AI 契约）
    # 只作为即时冲击，在此被消化（实际满意度以本步算出的存量为准）。构造性滞后 1 月：
    # 灾荒（Step 8）等在本步之后的 POP 变化，从下月的派生中体现。
    _settle_faction_metrics(state, log)

    # ---- Step 6: 军事/外交 ----
    _settle_military_diplomacy(state, log)

    # ---- Step 6.5: 历史改写位评估 ----
    _evaluate_timeline_breaks(state, log)

    # ---- Step 6.8: 五层承接层月度钩子 ----
    _settle_mechanisms(state, log)      # 层②机制槽：纯加成/减耗
    _settle_tech(state, log)            # 层③研发管线：资源×时间×人才推进
    _settle_org_economy(state, log)     # 层④机构经济生命周期：受崩盘线约束

    # ---- Step 6.9: 帝国修正（legacies）结算 ----
    _settle_legacies(state, log)

    # ---- Step 6.10: 国策树（focus）长期效果结算 ----
    _settle_focus(state, log)

    # ---- Step 7: 事件压力 ----
    _settle_events(state, log)

    # ---- Step 8: 灾荒 ----
    _settle_disaster(state, log)

    # ---- Step 8.5: 局势结算（规范 §4.1：灾荒之后、皇帝个人之前）----
    # 唯一写 `state.situations` 的地方；扣费/效果走 state_applier 同一批量事务 API，
    # intent 只按本回合事务记录校验（`_situation_journal_base` 游标）。
    _settle_situations(state, log, _situation_journal_base)

    # ---- Step 9: 皇帝个人 ----
    # 🔴 2026-10-07 用户裁定（选甲）：「帝王行动」此时尚未定型，从结算中**暂时停用**。
    # 幂等性：改一个常量（settlement.IMPERIAL_ACTION_ENABLED）即可恢复；代码与 16 个专用用例均原样保留。
    # 🔴 旧档：已开局存的档不会自动获得帝王行动，且报告中的动作记录仍在。
    if IMPERIAL_ACTION_ENABLED:
        _settle_emperor_personal(state, log)

    # ---- Step 10: 隐藏状态 ----
    _settle_hidden(state, log)

    # ---- Step 10.5: 人口总账校正（P1-3）----
    # 全局在籍人口 population 与「Σ六类 POP + 流民」对齐：逃荒/归籍/职业流动等
    # 在 POP 规模上的净变化此前不回写 population，长期回放背离数百万（60 月差 600万+），
    # 导致按 population 比例分配的逻辑（人口增长分摊、隐户比例、税收人口）失真。
    # growth 已在 Step 3 分配到农 POP，故校正后 population 仍含当月增长效果，数学一致。
    # 2026-09-27（方案 A）：隐户人口已并入 `农` POP 的加法子池 `hidden`（口），但**不在籍**
    # （不落籍、不纳税）→ 本式**不含**隐户；「总口」口径 = 本式结果 ＋ Σ`农.hidden`。
    _pop_total = sum(_pop["size"] for _p in state.prefectures.values()
                     for _pop in _p["pops"].values()) + state.refugee_count
    state.population = max(10_000_000, _pop_total)

    # ---- Step 10.55: 农的职位/丁口子池对齐（B1d-a **月度兜底**，幂等）----
    # 本月内一切改动 `农.size` 的通道（城市化/回乡、就业流动、逃荒赈济、征兵裁兵、逃籍归籍、
    # 人口自然增长…）都可能让「Σ职位 == size」「ding+kou == size」暂时失衡；此处按**现有比例**
    # 一次性对齐（**只改子池、不改 size**，不掩盖人口守恒）。诊断读数：
    # `farm_slice_fixes > 0` 长期出现 ⇒ 有通道漏挂钩（可观测、不阻断）；`farm_slice_violations`
    # 用于记录兜底后仍不成立的异常（应为空）。
    try:
        from core.foundation.ledger.pop_structure import check_farm_invariants, sync_all_farm_slices
        _audit = getattr(state, "settlement_audit", None)
        if not isinstance(_audit, dict):
            _audit = {}
            state.settlement_audit = _audit
        _fixed = sync_all_farm_slices(state)
        if _fixed:
            _audit["farm_slice_fixes"] = _fixed
        _bad = check_farm_invariants(state)
        if _bad:
            _audit["farm_slice_violations"] = _bad[:5]
    except Exception:  # noqa: BLE001  兜底失败不得阻断结算
        pass

    # ---- Step 10.6: 银行（抵当所）存款**存量**月末硬收敛 ----
    # 必须在全部结算步之后：存款上限 = 目标阶层财富 × didang_deposit_cap，而 wealth 在
    # 银行步（Step 4.2）之后仍会被赋税/俸禄/物价改变；银行步内收敛月末仍会超限
    # （240 月压力测试：15,541,569 贯 vs 上限 5,897,845 贯）。
    _settle_bank_stock(state, log)

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
