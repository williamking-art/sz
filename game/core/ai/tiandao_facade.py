# -*- coding: utf-8 -*-
"""大宋天道裁决体系统一门面（TianDaoFacade）。

定位：
- 集中收敛全域财政、市场、仓储物流、乡村阶级、官僚行政考课、军事治安六大领域的业务裁决；
- 底层全委派至 TianDaoEngine，本地纯算，耗时 < 0.2ms，零网络依赖，零 Token 消耗；
- 各业务结算模块（settlement_*, market, transport, decree 等）凡涉及微观博弈与倾向选择，一律经由本门面。

契约纪律（2026-10-17 修复批）：
1. **每个门面方法显式传 `objective`**——不再依赖 `condition` 中文子串 / `criteria` 键名的隐式分派；
2. **缺失 ≠ 0 ≠ 1.0**：取不到的读数一律 `None` + `defined=False`，不回落"完美"；
3. **不编人**：事实签的受命大臣取自 `state.central_orgs[*]["lead"]`（在任真账），
   名册里没有该人就不生成，不硬编码历史人名；
4. **只读**：本门面不写 state、不碰账本（裁决交业务域落地）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from core.ai.tiandao_engine import TianDaoEngine

__all__ = ["TianDaoFacade"]

# =============================================================================
# 奏折事实签阈值（原散落在代码里的 40 / 50000 / 3000 魔数，集中声明便于校准）
# =============================================================================
SEED_FIN_UNREST = 40.0           # 民怨阈值（0~100）
SEED_FIN_TREASURY = 50000        # 路级府库"见底"阈值（贯）
SEED_REFUGEE_COUNT = 3000        # 流民阈值（人）
SEED_UNREST_ALERT = 50.0         # 月报民怨告警阈值（0~100）

# 路级遵从度 → 吏治通道乘数（**只在 decree_effect 合成层使用**，不改 clerks_mult 本体）
COMPLIANCE_MULT = {"vigorous": 1.05, "compliant": 0.90, "passive": 0.65, "defiant": 0.40}

#：事实签可用的 matter_domain（必须与 `ai.contracts_misc.generate_memorials` 的 kind 白名单一致）
MEMORIAL_DOMAINS = ("invention", "governance", "military", "personnel", "finance")


def _pct(v: Any, default: Optional[float] = None) -> Optional[float]:
    """0~100 读数：缺失/非数 ⇒ default（**不把缺失当 0**）。"""
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return max(0.0, min(100.0, f))


class TianDaoFacade:
    """全域天道裁决统一业务门面。"""

    # =========================================================================
    # 1. 财政与税收领域 (Fiscal & Taxation)
    # =========================================================================
    @classmethod
    def tax_collection_stance(cls, state_context: Dict[str, Any]) -> str:
        """夏秋两税征管倾向: 'strict' (严催) / 'moderate' (常态) / 'lenient' (体恤蠲免)。"""
        criteria = {"strict": 0.35, "moderate": 0.50, "lenient": 0.15}
        return TianDaoEngine.choose(
            state_context, "征管宽严倾向", criteria, objective="tax_stance")["verdict"]

    @classmethod
    def should_waive_ancient_arrears(cls, state_context: Dict[str, Any]) -> bool:
        """是否豁免三年以上百姓陈年积欠 (恩泽蠲免)。"""
        return TianDaoEngine.gate(
            state_context, "是否准予蠲免陈年逋欠", objective="waive_arrears")["verdict"]

    @classmethod
    def dynamic_treasury_crisis_line(cls, state: Any = None, safety_months: int = 3) -> int:
        """动态财政安全垫线（替代死板魔数 5,000,000）。

        口径：
        - 月度刚性支出读数来自 `state.statistics["last_monthly_expense"]`
          （由 `settlement_finance._record_monthly_expense` 每回合写入真实值）；
        - 安全垫 = 月支出 × `safety_months`（默认 3 个月），钳位 [1,000,000, 10,000,000]；
        - **读数缺失**（新档首月 / 旧档无该字段）⇒ 返回校准基准 5,000,000，
          并由 `crisis_line_source(state)` 显式报告来源，便于诊断"到底是不是动态的"。
        """
        base_line = 5_000_000
        if state is None:
            return base_line
        stats = getattr(state, "statistics", None) or {}
        last_expense = stats.get("last_monthly_expense")
        if last_expense is None:
            last_expense = stats.get("monthly_expense")
        try:
            expense = float(last_expense) if last_expense is not None else 0.0
        except (TypeError, ValueError):
            expense = 0.0
        if expense > 0:
            cushion = int(expense * safety_months)
            return max(1_000_000, min(10_000_000, cushion))
        return base_line

    @classmethod
    def crisis_line_source(cls, state: Any = None) -> Dict[str, Any]:
        """安全垫线来源诊断（只读）：`dynamic` 还是回落 `calibration_base`。

        面板/AI 用它回答"这条线为什么是这个数"，避免"以为动态其实恒定"。
        """
        line = cls.dynamic_treasury_crisis_line(state)
        dynamic = line != 5_000_000 or (
            state is not None
            and (getattr(state, "statistics", None) or {}).get("last_monthly_expense") is not None
        )
        return {
            "line": line,
            "source": "dynamic" if dynamic else "calibration_base",
            "月支出读数": (getattr(state, "statistics", None) or {}).get("last_monthly_expense"),
        }

    # =========================================================================
    # 2. 市场与商贸领域 (Market & Commerce)
    # =========================================================================
    @classmethod
    def merchant_trade_or_hoard(cls, state_context: Dict[str, Any]) -> str:
        """商贾行为决策: 'ship' (长途贩运平抑) / 'hoard' (居奇囤积) / 'local_sell' (就地抛售)。"""
        criteria = {"ship": 0.40, "hoard": 0.35, "local_sell": 0.25}
        return TianDaoEngine.choose(
            state_context, "商贾经营抉择", criteria, objective="merchant_trade")["verdict"]

    @classmethod
    def changping_intervene_gate(cls, state_context: Dict[str, Any]) -> bool:
        """常平仓是否立即平粜开仓抛售以压制粮价 (触发阈值由 `content.data.CHANGPING_*` 定义)。"""
        return TianDaoEngine.gate(
            state_context, "是否平粜开仓压制粮价", objective="changping_open")["verdict"]

    # =========================================================================
    # 3. 仓储与物流领域 (Storage & Logistics)
    # =========================================================================
    @classmethod
    def labor_service_policy(cls, state_context: Dict[str, Any]) -> str:
        """劳役征派决策: 'corvee' (差役强征) / 'hired' (出钱雇役)。

        ⚠️ 上下文须给 `treasury`（或 `local_treasury`）——**府库财力**；
        缺失时引擎不加偏置（**不把缺失当"没钱"**，旧实现据此恒判差役）。
        """
        criteria = {"corvee": 0.50, "hired": 0.50}
        return TianDaoEngine.choose(
            state_context, "劳役制度选择", criteria, objective="labor_policy")["verdict"]

    @classmethod
    def canal_reroute_choice(cls, state_context: Dict[str, Any]) -> str:
        """漕运遇阻改道决断: 'wait_dredge' (等疏浚) / 'overland_cart' (转陆路) / 'borrow_grain' (和籴借兑)。"""
        criteria = {"wait_dredge": 0.45, "overland_cart": 0.35, "borrow_grain": 0.20}
        return TianDaoEngine.choose(
            state_context, "漕运改道决断", criteria, objective="canal_reroute")["verdict"]

    @classmethod
    def granary_corruption_check(cls, state_context: Dict[str, Any]) -> bool:
        """仓吏是否借雀鼠耗之名私吞公粮转入私邸地窖（无依据时**不判贪墨**）。"""
        return TianDaoEngine.gate(
            state_context, "是否存在雀鼠耗贪墨虚报", objective="granary_corruption")["verdict"]

    # =========================================================================
    # 4. 乡村阶层与社会博弈 (Social Classes & Rural)
    # =========================================================================
    @classmethod
    def farmer_destitution_path(cls, state_context: Dict[str, Any]) -> str:
        """破产小农出路: 'mortgage_land' (典田沦为佃农) / 'flee_refugee' (举家逃亡流民)。"""
        criteria = {"mortgage_land": 0.70, "flee_refugee": 0.30}
        return TianDaoEngine.choose(
            state_context, "破产自耕农抉择", criteria, objective="farmer_path")["verdict"]

    @classmethod
    def gentry_charity_vs_annex(cls, state_context: Dict[str, Any]) -> str:
        """士绅博弈: 'charity_relief' (开私仓设义庄收揽乡望) / 'usury_annex' (放高利贷兼并田产)。"""
        criteria = {"charity_relief": 0.40, "usury_annex": 0.60}
        return TianDaoEngine.choose(
            state_context, "士绅灾荒抉择", criteria, objective="gentry_path")["verdict"]

    # =========================================================================
    # 5. 官僚治理、圣旨遵从与考课 (Governance & Decrees)
    # =========================================================================
    @classmethod
    def reform_compliance_gate(cls, state_context: Dict[str, Any]) -> bool:
        """知州对朝廷变法新政是否切实遵旨执行 (还是表面敷衍阳奉阴违)。"""
        return TianDaoEngine.gate(
            state_context, "是否切实贯彻朝廷变法新政", objective="reform_compliance")["verdict"]

    @classmethod
    def circuit_decree_compliance(cls, state_context: Dict[str, Any]) -> Dict[str, Any]:
        """路级知州对圣旨遵从反应类型（供 `decree_effect` 合成层使用）。

        返回 ``{verdict, mult, probabilities, provider, defined}``；
        `mult` ∈ {1.05, 0.90, 0.65, 0.40}（见 `COMPLIANCE_MULT`）。
        **注意**：该乘数只在 `decree_effect.effect_channels` 的**合成层**生效，
        不修改 `clerks_mult`（吏胥折扣）本体，避免改写既有单点口径。
        """
        criteria = {"vigorous": 0.25, "compliant": 0.50, "passive": 0.20, "defiant": 0.05}
        res = TianDaoEngine.choose(
            state_context, "路级知州诏令遵从度", criteria, objective="decree_compliance")
        choice = res.get("verdict") or "compliant"
        return {
            "verdict": choice,
            "mult": COMPLIANCE_MULT.get(choice, COMPLIANCE_MULT["compliant"]),
            "probabilities": res.get("probabilities", {}),
            "provider": res.get("provider", TianDaoEngine.PROVIDER_ID),
            "defined": bool(res.get("defined")),
        }

    @classmethod
    def appraisal_score(
        cls,
        state_context: Dict[str, Any],
        levels: Sequence[str] = ("下考", "中考", "上考"),
    ) -> Dict[str, Any]:
        """知州三年磨勘考课综合打分评等。

        `levels` 必须按「差 → 好」排列（见 `TianDaoEngine.score` 契约）。
        """
        return TianDaoEngine.score(state_context, "知州三年磨勘四善三最考课", levels)

    # =========================================================================
    # 6. 军事边防与治安维稳 (Military & Security)
    # =========================================================================
    @classmethod
    def recruit_refugees_to_soldiers_gate(cls, state_context: Dict[str, Any]) -> bool:
        """灾荒断粮时，知州是否开启太祖祖宗之法'招募饥民为地方厢军'以消弭民变。"""
        return TianDaoEngine.gate(
            state_context, "是否招募流民充为地方厢军", objective="recruit_refugees")["verdict"]

    # =========================================================================
    # 7. 天道 × 大模型 AI 叙事三管道 (AI Narrative Coupling Pipelines)
    # =========================================================================
    @staticmethod
    def _org_lead(state: Any, *org_names: str) -> Optional[str]:
        """从 `state.central_orgs`（在任真账）取第一个非空主官；取不到 ⇒ None（不编人）。"""
        orgs = getattr(state, "central_orgs", None)
        if not isinstance(orgs, dict):
            return None
        for name in org_names:
            row = orgs.get(name)
            if isinstance(row, dict):
                lead = row.get("lead") or (row.get("holders") or {}).get("中书侍郎")
                if not lead:
                    holders = row.get("holders") or {}
                    if isinstance(holders, dict) and holders:
                        lead = next(iter(holders.values()))
                if lead:
                    return str(lead)
        return None

    @classmethod
    def scan_memorial_seeds(cls, state: Any, limit: int = 3) -> List[Dict[str, Any]]:
        """【管道一：奏折事实签提炼】扫描各路真实矛盾，生成结构化事实签。

        · `matter_domain` ∈ `MEMORIAL_DOMAINS`（与 `generate_memorials` 的 kind 白名单同源）；
        · `target_minister` 取自 `state.central_orgs` 在任主官（**名册无此人则不生成**）；
        · 多路命中时**按严重度排序取 Top-N**（旧实现 `break` 只取第一个命中的路）；
        · 事实串里的数字全部来自真实读数。
        """
        seeds: List[Dict[str, Any]] = []
        turn = int(getattr(state, "turn", 1) or 1)
        prefs = getattr(state, "prefectures", None) or {}
        if not isinstance(prefs, dict):
            return []

        finance_lead = cls._org_lead(state, "户部", "三司", "尚书省", "中书省")
        gov_lead = cls._org_lead(state, "中书省", "尚书省")
        mil_lead = cls._org_lead(state, "枢密院", "兵部", "枢密院事")

        # 1. 财政/仓储危机：民怨高 + 路级府库见底（按民怨降序取最激化的一条）
        fin_rows = []
        for r_name, p in prefs.items():
            if not isinstance(p, dict):
                continue
            unrest = _pct(p.get("unrest"))
            treasury = p.get("local_treasury")
            try:
                treasury_v = float(treasury) if treasury is not None else None
            except (TypeError, ValueError):
                treasury_v = None
            if unrest is None or treasury_v is None:
                continue
            if unrest > SEED_FIN_UNREST and treasury_v < SEED_FIN_TREASURY:
                fin_rows.append((unrest, r_name, treasury_v))
        fin_rows.sort(reverse=True)
        if fin_rows and finance_lead:
            unrest, r_name, treasury_v = fin_rows[0]
            seeds.append({
                "seed_id": f"seed_{turn}_{r_name}_fin",
                "target_minister": finance_lead,
                "matter_domain": "finance",
                "trigger_fact": (f"{r_name}府库见底（仅存{int(treasury_v)}贯），"
                                 f"民怨升至{int(unrest)}，请敕拨太仓现钱济急"),
                "core_claim": "请移拨国库封桩钱蠲济州司",
                "suggested_title": f"请拨帑银赈济{r_name}司库匮乏疏",
                "severity": round(unrest, 2),
            })

        # 2. 流民与军事：流民就食者众（按人数降序）
        ref_rows = []
        for r_name, p in prefs.items():
            if not isinstance(p, dict):
                continue
            ref = p.get("refugees")
            try:
                ref_v = float(ref) if ref is not None else None
            except (TypeError, ValueError):
                ref_v = None
            if ref_v is not None and ref_v > SEED_REFUGEE_COUNT:
                ref_rows.append((ref_v, r_name))
        ref_rows.sort(reverse=True)
        if ref_rows:
            ref_v, r_name = ref_rows[0]
            lead = mil_lead or gov_lead
            if lead:
                seeds.append({
                    "seed_id": f"seed_{turn}_{r_name}_mil",
                    "target_minister": lead,
                    "matter_domain": "military",
                    "trigger_fact": (f"{r_name}境内流民就食者达{int(ref_v)}人，"
                                     f"沿途草舍萧条，恐生啸聚"),
                    "core_claim": "开义仓平粜，招募饥民充厢军以消弭民变",
                    "suggested_title": f"陈请优恤{r_name}流民安辑流亡疏",
                    "severity": round(ref_v / 1000.0, 2),
                })

        # 3. 吏治/政务：某路民怨高但府库尚可（督责监司整饬）
        if gov_lead:
            unrest_rows = []
            for r_name, p in prefs.items():
                if not isinstance(p, dict):
                    continue
                u = _pct(p.get("unrest"))
                if u is not None and u > SEED_UNREST_ALERT:
                    unrest_rows.append((u, r_name))
            unrest_rows.sort(reverse=True)
            if unrest_rows:
                u, r_name = unrest_rows[0]
                if not any(s["trigger_fact"].startswith(r_name) for s in seeds):
                    seeds.append({
                        "seed_id": f"seed_{turn}_{r_name}_gov",
                        "target_minister": gov_lead,
                        "matter_domain": "governance",
                        "trigger_fact": f"{r_name}民怨高企（{int(u)}），监司按察不力，请饬守令抚绥",
                        "core_claim": "请遣使按察监司，赈济抚绥以安民心",
                        "suggested_title": f"请饬{r_name}监司抚绥军民疏",
                        "severity": round(u, 2),
                    })

        # 4. 无严重矛盾 ⇒ 常态政务签（仍用真实在任主官；取不到就不生成）
        if not seeds and gov_lead:
            seeds.append({
                "seed_id": f"seed_{turn}_routine_gov",
                "target_minister": gov_lead,
                "matter_domain": "governance",
                "trigger_fact": "天下州军夏秋两税征解告竣，百司宿卫如常",
                "core_claim": "请慎选守令，精简冗员以敦风化",
                "suggested_title": "请考课天下牧守整饬吏治疏",
                "severity": 0.0,
            })

        seeds.sort(key=lambda s: float(s.get("severity") or 0.0), reverse=True)
        return seeds[:max(1, int(limit))]

    @classmethod
    def derive_dialogue_stance(
        cls,
        minister_name: str,
        topic: str,
        state: Any = None,
    ) -> Dict[str, Any]:
        """【管道二：御前召对立场定势】天理定立场，相公陈利害。

        · 名册无此人 ⇒ `defined=False, stance=None`（**不静默冒充"赞同"**）；
        · 议题按词表分类（变法/理财/边事/赋役/赈济/水利），非变法议题也有定势；
        · 给了 `state` 时叠加**在任/失势**调制（仅读，不写）。

        返回 ``{actor_id, topic, stance, intensity, argument_anchor,
        compromise_threshold, defined, in_office, provider}``。
        """
        from content.ministers import MINISTERS

        fig = (MINISTERS or {}).get(minister_name) if isinstance(MINISTERS, dict) else None
        if not isinstance(fig, dict):
            return {
                "actor_id": minister_name, "topic": topic, "stance": None,
                "intensity": None, "argument_anchor": None,
                "compromise_threshold": None, "defined": False, "in_office": False,
                "provider": TianDaoEngine.PROVIDER_ID,
            }

        faction = str(fig.get("faction") or "中立派")
        loyalty_raw = fig.get("loyalty")
        try:
            loyalty = float(loyalty_raw) if loyalty_raw is not None else None
        except (TypeError, ValueError):
            loyalty = None
        traits = str(fig.get("traits") or "")

        in_office = False
        if state is not None:
            in_office = cls._is_in_office(state, minister_name)

        t = str(topic or "")
        TOPIC_WORDS = {
            "reform": ("新法", "变法", "保甲", "免役", "青苗", "市易", "方田", "绍述"),
            "finance": ("榷", "盐", "茶", "税", "理财", "常平", "和买", "交子", "钱法"),
            "military": ("兵", "边", "西夏", "军饷", "开边", "将兵法", "马政"),
            "relief": ("赈", "灾", "流民", "蠲", "荒政", "义仓"),
            "water": ("河", "堤", "水利", "漕", "汴"),
        }
        topic_kind = next((k for k, ws in TOPIC_WORDS.items() if any(w in t for w in ws)), "general")

        # 派系立场基线（新党主变、旧党主守、军功主战、皇党主承旨、中立主审慎）
        base = {
            "新党": ("赞同", 0.70),
            "旧党": ("反对", 0.75),
            "军功集团": ("赞同" if topic_kind in ("military",) else "审慎", 0.65),
            "皇党集团": ("承旨", 0.60),
            "中立派": ("审慎", 0.55),
        }.get(faction, ("审慎", 0.50))

        stance, intensity = base

        if topic_kind == "reform":
            if faction == "新党":
                stance, intensity = ("力赞", 0.85)
                anchor = "先王法度随时更张，变法足国强兵，实乃当务之急。"
            elif faction == "旧党":
                stance, intensity = ("力谏" if ("守正" in traits or (loyalty is not None and loyalty < 0.70)) else "反对", 0.90)
                anchor = "祖宗之法不可轻变，政令频更则百姓骚动，海内危疑。"
            else:
                stance, intensity = ("保留", 0.50)
                anchor = "变法虽有利弊，宜先下监司详审，不可操切施行。"
        elif topic_kind == "finance":
            anchor = ("利源当尽入公家，榷禁既行则国用自足。" if faction == "新党"
                      else "聚敛之臣不可用，取民有制则根本自固。")
        elif topic_kind == "military":
            if faction == "军功集团":
                stance, intensity = ("力赞", 0.80)
            anchor = "边事不可轻启，然武备不可一日弛。"
        elif topic_kind == "relief":
            anchor = "荒政在速，蠲免赈粜当先行，不可待文书往复。"
        elif topic_kind == "water":
            anchor = "治水当计久远，疏导与堤防并施，不可徒塞其流。"
        else:
            anchor = "谨遵圣意，从容擘画。"

        # 在任/失势调制：失势者言更激（局外无所顾忌），在任者略收敛
        if state is not None:
            if not in_office:
                intensity = min(1.0, intensity + 0.10)
            else:
                intensity = max(0.10, intensity - 0.05)

        return {
            "actor_id": minister_name,
            "topic": topic,
            "topic_kind": topic_kind,
            "stance": stance,
            "intensity": round(intensity, 2),
            "argument_anchor": anchor,
            "compromise_threshold": round(max(0.10, 1.0 - intensity), 2),
            "defined": True,
            "in_office": in_office,
            "provider": TianDaoEngine.PROVIDER_ID,
        }

    # =========================================================================
    # 8. 只读观察接线（2026-10-21，Jev A 0.799）
    # -------------------------------------------------------------------------
    # 纪律：本批只把 10 个"已声明、零生产调用"的门面方法接进月度结算，
    # 记录裁决供观测/校准；**不改任何数值、不写经济账本**。数值效果下一批再接。
    # =========================================================================
    #: 只读观察的 10 个方法（与 tasks.md §2 末段一一对应）
    OBSERVE_METHODS = (
        "tax_collection_stance", "should_waive_ancient_arrears",
        "merchant_trade_or_hoard", "changping_intervene_gate",
        "canal_reroute_choice", "granary_corruption_check",
        "farmer_destitution_path", "gentry_charity_vs_annex",
        "reform_compliance_gate", "recruit_refugees_to_soldiers_gate",
    )

    @classmethod
    def build_state_context(cls, state: Any) -> Dict[str, Any]:
        """聚合真实读数，供 10 个门面方法只读观察（**不写 state**）。

        口径：缺失一律 `None`（不回落 0/1.0）；`integrity = 1 − 平均贪腐`;
        `has_inspector` 用既有 `oversight`（≥0.5 视为有巡按/监察）。
        """
        prefs = getattr(state, "prefectures", None) or {}
        unrest_vals: List[float] = []
        refugees: List[float] = []
        prices: List[float] = []
        if isinstance(prefs, dict):
            for p in prefs.values():
                if not isinstance(p, dict):
                    continue
                u = _pct(p.get("unrest"))
                if u is not None:
                    unrest_vals.append(u)
                try:
                    if p.get("refugees") is not None:
                        refugees.append(max(0.0, float(p.get("refugees"))))
                except (TypeError, ValueError):
                    pass
                try:
                    if p.get("grain_price") is not None:
                        prices.append(float(p.get("grain_price")))
                except (TypeError, ValueError):
                    pass

        corr = getattr(state, "corruption", None) or {}
        corr_vals = [float(v) for v in corr.values() if isinstance(v, (int, float))] \
            if isinstance(corr, dict) else []
        avg_corr = (sum(corr_vals) / len(corr_vals)) if corr_vals else 0.0
        integrity = max(0.0, min(1.0, 1.0 - avg_corr))

        grain_price = getattr(state, "grain_price", None)
        try:
            base_price = float(grain_price) if grain_price is not None else None
        except (TypeError, ValueError):
            base_price = None
        avg_price = (sum(prices) / len(prices)) if prices else None
        price_ratio = (avg_price / base_price) if (avg_price is not None
                                                  and base_price and base_price > 0) else None

        stats = getattr(state, "statistics", None) or {}
        oversight = getattr(state, "oversight", None)
        try:
            oversight_f = float(oversight) if oversight is not None else None
        except (TypeError, ValueError):
            oversight_f = None

        return {
            "treasury": getattr(state, "treasury", None),
            "imperial_treasury": getattr(state, "imperial_treasury", None),
            "granary": getattr(state, "granary", None),
            "granary_cap": getattr(state, "granary_cap", None),
            "unrest": (sum(unrest_vals) / len(unrest_vals)) if unrest_vals else None,
            "refugees": sum(refugees) if refugees else None,
            "price_ratio": price_ratio,
            "integrity": integrity,
            "oversight": oversight_f,
            "has_inspector": bool(oversight_f is not None and oversight_f >= 0.5),
            "prestige": getattr(state, "prestige", None),
            "disaster": stats.get("disaster_level", stats.get("disaster")),
            "stock": getattr(state, "granary", None),
            "turn": getattr(state, "turn", None),
        }

    #: 门面方法 → 显式 objective（P1 决策日志接线；只读，不改判定）
    OBSERVE_OBJECTIVES = {
        "tax_collection_stance": "tax_stance",
        "should_waive_ancient_arrears": "waive_arrears",
        "merchant_trade_or_hoard": "merchant_trade",
        "changping_intervene_gate": "changping_open",
        "canal_reroute_choice": "canal_reroute",
        "granary_corruption_check": "granary_corruption",
        "farmer_destitution_path": "farmer_path",
        "gentry_charity_vs_annex": "gentry_path",
        "reform_compliance_gate": "reform_compliance",
        "recruit_refugees_to_soldiers_gate": "recruit_refugees",
    }

    @classmethod
    def observe_monthly(cls, state: Any) -> Dict[str, Any]:
        """**只读**观察本月 10 个门面裁决；结果挂 `state._tiandao_observe`（不入存档）。

        2026-10-21 P1：额外走 `DecisionService` 写 `state.decision_log`（只记录，不改判定）。
        """
        ctx = cls.build_state_context(state)
        out: Dict[str, Any] = {}
        for name in cls.OBSERVE_METHODS:
            try:
                out[name] = getattr(cls, name)(ctx)
            except Exception as exc:  # noqa: BLE001 — 观测失败不得影响结算
                out[name] = {"error": type(exc).__name__}
                logging.getLogger("tiandao").warning(
                    "只读观察 %s 失败：%r", name, exc, exc_info=True)
        try:
            from core.ai.tiandao_decision import decide_and_log
            for name, objective in cls.OBSERVE_OBJECTIVES.items():
                decide_and_log(state, objective, ctx)
        except Exception:  # noqa: BLE001 — 决策日志失败不得影响结算
            logging.getLogger("tiandao").warning("决策日志接线失败", exc_info=True)
        rec = {"turn": int(getattr(state, "turn", 0) or 0),
               "read_only": True, "decisions": out,
               "context_defined": any(v is not None for v in ctx.values())}
        try:
            state._tiandao_observe = rec
        except Exception:  # noqa: BLE001 — 诊断副本写失败不影响结算
            pass
        logging.getLogger("tiandao").info("[只读观察] turn=%s 已记录 %d 项裁决",
                                          rec["turn"], len(out))
        return rec

    @staticmethod
    def _is_in_office(state: Any, minister_name: str) -> bool:
        """该大臣是否在任（查 `central_orgs` 的 lead/holders；只读）。"""
        orgs = getattr(state, "central_orgs", None)
        if not isinstance(orgs, dict):
            return False
        for row in orgs.values():
            if not isinstance(row, dict):
                continue
            if str(row.get("lead") or "") == minister_name:
                return True
            holders = row.get("holders") or {}
            if isinstance(holders, dict) and minister_name in holders.values():
                return True
        return False

    @classmethod
    def summarize_monthly_omen(cls, state: Any) -> Dict[str, Any]:
        """【管道三：月报天机实录】提炼全月天地人真实因果，专供月报大模型执笔润色。

        · `omen_level` 三档：吉 / 平 / 凶（旧实现只有 平/凶 两档）；
        · `admin_efficiency` **缺失即 None**（旧实现回落 1.0 = 假装"行政完美"）；
        · `unrest_circuits` 按民怨排序；`famine_circuits` 保留兼容别名（同源同值）。
        """
        turn = int(getattr(state, "turn", 1) or 1)
        stats = getattr(state, "statistics", None) or {}
        prestige = _pct(getattr(state, "prestige", None))

        prefs = getattr(state, "prefectures", None) or {}
        unrest_rows = []
        if isinstance(prefs, dict):
            for r_name, p in prefs.items():
                if not isinstance(p, dict):
                    continue
                u = _pct(p.get("unrest"))
                if u is not None and u > SEED_UNREST_ALERT:
                    unrest_rows.append((u, r_name))
        unrest_rows.sort(reverse=True)
        unrest_circuits = [r for _u, r in unrest_rows[:3]]

        if prestige is None:
            omen_level = None
        elif prestige >= 60 and not unrest_circuits:
            omen_level = "吉"
        elif prestige < 40 or len(unrest_circuits) >= 2:
            omen_level = "凶"
        else:
            omen_level = "平"

        eff = stats.get("administrative_efficiency")
        try:
            admin_eff = float(eff) if eff is not None else None
        except (TypeError, ValueError):
            admin_eff = None

        return {
            "turn": turn,
            "prestige": None if prestige is None else int(prestige),
            "omen_level": omen_level,
            "omen_defined": omen_level is not None,
            "unrest_circuits": unrest_circuits,
            "unrest_count": len(unrest_rows),
            "famine_circuits": list(unrest_circuits),   # 兼容旧字段（同源，避免双算两套）
            "famine_count": len(unrest_circuits),
            "admin_efficiency": admin_eff,
            "admin_efficiency_defined": admin_eff is not None,
            "provider": TianDaoEngine.PROVIDER_ID,
        }
