# -*- coding: utf-8 -*-
"""宋祚 · 结算推演契约子模块（各 *_decide 与 survey_settle）。

拆分自 ai/client.py：以 mixin 形式承载契约方法，AIClient 继承之。
零行为变更：方法体原样搬运。
"""
from ai.client_utils import (
    _ai_unavailable, _clean_text, _load_prompt,
)
from ai.validators import _TIERS7, _decide_state_text
from content.data import normalize_tier

class SettleContractMixin:
    # ============================================================
    # 12 步 agent 化 P1：外交/军事/灾荒契约（档位词输出，程序换算封顶；守恒铁律——
    # agent 只叙事/档位，不触碰税收/军粮/仓廪/国库守恒数值）
    # ============================================================
    def _agent_inject(self, state, role):
        """角色注入（Phase 3b persona + Phase 3a 记忆图谱），loyalty 数值绝不注入。"""
        try:
            from content.ministers.persona import _build_persona_prompt
            hint = _build_persona_prompt(state, role, getattr(state, "turn", 0))
        except Exception:
            hint = ""
        try:
            rows = state.memory.query(role, time_window=0, top_k=6)
            mem = state.memory.summarize(rows, max_chars=100)
        except Exception:
            mem = ""
        parts = [hint] if hint else []
        if mem:
            parts.append(f"【相关历史】{mem}")
        return "\n".join(parts)

    def economy_decide(self, posture, state=None):
        """AI 推演本月全国经济动态（全系统强制 AI，拒绝式）+ 金融 5 字段（蔡权衡定稿）。

        核心字段（景气/士绅/士绅力度/生产）缺失或非法 → **整单返回 None**；金融字段
        （交子信任/钱荒/市舶/银行/物价趋势）三态词白名单，缺失/非法 → **拒绝式报错**。
        state：与 agent 化签名一致（agent_router 统一传 state）；当前经济推演仅消费
        posture，state 预留供记忆/角色注入，不改变既有语义。
        """
        from content.data import FINANCE_STATES
        sys_p = _load_prompt("economy", posture=posture)

        def validate(o):
            if not isinstance(o, dict):
                return None
            # 拒绝式：核心字段缺失/非法 → 整单拒绝（丰富表达归一）
            for k in ("景气", "士绅力度", "生产"):
                if not isinstance(o.get(k), str) or not o[k].strip():
                    return None
                o[k] = normalize_tier(o[k])
            if not isinstance(o.get("士绅"), str) or o["士绅"] not in ("囤", "抛", "观望"):
                return None
            out = {
                "景气": o["景气"], "士绅": o["士绅"], "士绅力度": o["士绅力度"], "生产": o["生产"],
            }
            # 窖银/城市化/回乡/科举：合法档位词或合法别名 → 归一；其他（含含档位字的非法词如
            # "超大"）→ 兜底「无」（本月不发生）。normalize_tier 对含档位字的词会字形就近归一，
            # 故先校验词 ∈ 合法档位/别名集，避免"超大→大"式误归一。
            _tier_words = set(_TIERS7)
            try:
                from content.data import TIER_ALIAS
                for _vals in TIER_ALIAS.values():
                    _tier_words.update(_vals)
            except Exception:
                pass
            for k in ("窖银", "城市化", "回乡", "科举"):
                v = o.get(k)
                if isinstance(v, str) and v.strip():
                    w = v.strip()
                    out[k] = normalize_tier(w) if w in _tier_words else "无"
                else:
                    out[k] = "无"   # 缺省 = 本月不发生（明确语义）
            # 金融 5 字段（三态词白名单；缺失/非法 → 拒绝式整单失败）
            for fk, states in (("jiaozi_trust", FINANCE_STATES["jiaozi_trust"]),
                               ("shortage", FINANCE_STATES["shortage"]),
                               ("maritime", FINANCE_STATES["maritime"]),
                               ("bank", FINANCE_STATES["bank"]),
                               ("price_trend", FINANCE_STATES["price_trend"])):
                v = o.get(fk)
                if not isinstance(v, str) or v not in states:
                    return None
                out[fk] = v
            return out
        raw = self._call(sys_p, "", temperature=0.7, max_tokens=300)
        return self._postprocess(raw, validate, lambda: None)

    def survey_settle(self, posture):
        """推演方田均税/清丈隐田/抑兼并的落地效果档位。

        返回 {"hidden_cleared": tier, "gentry_returned": tier, "outcome": str}；
        失败返回 None，由调用方回退到按 effects 档位的兜底。
        """
        sys_p = _load_prompt("survey_settle", posture=posture)

        def validate(o):
            if not isinstance(o, dict):
                return None
            # 拒绝式：三字段缺失/非法 → 整单失败（丰富表达归一）
            hc = o.get("hidden_cleared")
            gr = o.get("gentry_returned")
            oc = o.get("outcome")
            if not isinstance(hc, str) or not isinstance(gr, str):
                return None
            hc = normalize_tier(hc)
            gr = normalize_tier(gr)
            if hc not in _TIERS7 or gr not in _TIERS7:
                return None
            if oc not in ("顺利", "小成", "受阻"):
                return None
            return {"hidden_cleared": hc, "gentry_returned": gr, "outcome": oc}
        raw = self._call(sys_p, "", temperature=0.7, max_tokens=200)
        return self._postprocess(raw, validate, lambda: None)

    def diplomacy_decide(self, posture, state=None):
        """外部外交（使节）契约：attitude 档位（微/小/中/大 → ±3~±8，CAP 8）、
        岁币（订/毁 布尔，SUI_GONG_ANNUAL 由结算算）、盟约（结/断 布尔 → alliance_jin_liao）。
        agent 只给档位词，不触碰岁币金额/国库。"""
        role = "使节"
        inj = self._agent_inject(state, role) if state is not None else ""
        sys_p = (
            "你是北宋外交使节。把本季外交动态量化为 JSON 契约：\n"
            '{"attitude": "微|小|中|大", "sui_gong": "订|毁|不变", "alliance": "结|断|不变"}'
            "\nattitude 档位（对金/辽/西夏态度变化 ±3~±8，程序换算封顶）；"
            "岁币/盟约只给布尔意图，金额与国库由朝廷程序核算。"
        )
        if inj:
            sys_p += f"\n{inj}"

        def validate(o):
            if not isinstance(o, dict) or "attitude" not in o:
                return None
            if not isinstance(o.get("attitude"), str) or not o["attitude"].strip():
                return None
            o["attitude"] = normalize_tier(o["attitude"])
            if o["attitude"] not in _TIERS7:
                return None
            o["sui_gong"] = o.get("sui_gong", "不变") if o.get("sui_gong") in ("订", "毁", "不变") else "不变"
            o["alliance"] = o.get("alliance", "不变") if o.get("alliance") in ("结", "断", "不变") else "不变"
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.5, max_tokens=200, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("diplomacy"))

    def military_decide(self, posture, state=None):
        """军事（枢密）契约：power 档位（战力 ±3~±8%）、army 档位（兵额 ±1万~±5万，CAP 5万）、
        training/morale 档位（±2~±6）、levy 档位（征发 cost 10万~50万）。agent 只给档位词。"""
        role = "枢密使"
        inj = self._agent_inject(state, role) if state is not None else ""
        sys_p = (
            "你是北宋枢密使。把本季军事动态量化为 JSON 契约：\n"
            '{"power": "微|小|中|大", "army": "微|小|中|大", "training": "微|小|中|大",'
            '"morale": "微|小|中|大", "levy": "微|小|中|大"}'
            "\n档位含义：power 战力 ±3~±8%；army 兵额 ±1万~±5万（CAP 5万）；"
            "training/morale ±2~±6；levy 征发 cost 10万~50万。程序换算封顶。"
        )
        if inj:
            sys_p += f"\n{inj}"

        def validate(o):
            if not isinstance(o, dict):
                return None
            for k in ("power", "army", "training", "morale", "levy"):
                v = o.get(k)
                if not isinstance(v, str) or not v.strip():
                    return None
                o[k] = normalize_tier(v)
                if o[k] not in _TIERS7:
                    return None
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.5, max_tokens=200, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("military"))

    def relief_decide(self, posture, state=None):
        """灾荒赈济（按察使）契约：disaster_level 1~5（减产/粮价 1.5~3.5×）、
        relief 档位（赈济 10万~50万石）、refugee 档位（流民 ±5万~±30万）。"""
        role = "按察使"
        inj = self._agent_inject(state, role) if state is not None else ""
        sys_p = (
            "你是朝廷按察使。把本季灾荒动态量化为 JSON 契约：\n"
            '{"disaster_level": 1~5, "relief": "微|小|中|大", "refugee": "微|小|中|大"}'
            "\ndisaster_level 灾级 1~5（减产/粮价 1.5~3.5× 既有公式）；"
            "relief 赈济 10万~50万石；refugee 流民 ±5万~±30万。程序换算封顶。"
        )
        if inj:
            sys_p += f"\n{inj}"

        def validate(o):
            if not isinstance(o, dict) or "disaster_level" not in o:
                return None
            lv = o.get("disaster_level")
            if isinstance(lv, bool) or not isinstance(lv, (int, float)) or not (1 <= int(lv) <= 5):
                return None
            o["disaster_level"] = int(lv)
            for k in ("relief", "refugee"):
                v = o.get(k)
                if not isinstance(v, str) or not v.strip():
                    return None
                o[k] = normalize_tier(v)
                if o[k] not in _TIERS7:
                    return None
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.5, max_tokens=200, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("relief"))

    def invest_decide(self, posture, state=None):
        """投资推演契约（复用 free_effect 载体）：领域/力度/来源/期限档位词。

        对齐（复用原有机制）：field 支持"科技"领域（研发投入走既有投资通道，
        落地 invest() field=科技 → tech researching 加速；node 可选：field=科技 时指定节点）。
        返回 {"field": 七领域, "fund": "treasury"|"imperial_treasury", "tier": 档位, "months": int,
              "node": 可选}
        """
        from content.data import INVEST_BASE, INVEST_FUND_SOURCES
        sys_p = (
            "你是朝廷度支。把本季投资计划量化为 JSON 契约：\n"
            '{"field": "农业|水利|工坊|商铺|漕运|军器|科技", "fund": "treasury|imperial_treasury",'
            '"tier": "微|小|中|大|巨|极", "months": 12, "node": "科技领域必填的节点id（官方或玩家注册）"}'
            "\nfield 七领域（INVEST_BASE 基准；科技=研发投入走既有投资通道）；"
            "fund=国库（会签执行）/内帑（乾纲独断）；tier 投资力度档位；months 回报期限。"
        )

        def validate(o):
            if not isinstance(o, dict) or "field" not in o or "fund" not in o:
                return None
            if o.get("field") not in INVEST_BASE:
                return None
            if o.get("fund") not in INVEST_FUND_SOURCES:
                return None
            if not isinstance(o.get("tier"), str) or not o["tier"].strip():
                return None
            o["tier"] = normalize_tier(o["tier"])
            if o["tier"] not in _TIERS7:
                return None
            m = o.get("months", 12)
            o["months"] = int(m) if isinstance(m, (int, float)) and 3 <= int(m) <= 60 else 12
            # 对齐：field=科技 时 node 必填（官方或玩家注册节点）
            if o["field"] == "科技":
                nid = str(o.get("node", "")).strip()
                if not nid:
                    return None
                from core.asset_context import get_tech_node
                from core.registries import node_entry
                ok = get_tech_node(nid) is not None or (state is not None and node_entry(state, nid) is not None)
                if not ok:
                    return None
                o["node"] = nid
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.4, max_tokens=250, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("invest"))

    def era_decide(self, posture, state=None):
        """时代推演契约（史官，每半年/重大事件后）：era_change 五维白名单 + trend 兴/平/衰
        + region + narrative（≤120字）；拒绝式校验；era_state 按 trend 程序定幅迁移。"""
        from content.data import ERA_DIMENSIONS
        sys_p = (
            "你是北宋史官。把本半年的时代变迁量化为 JSON 契约：\n"
            '{"era_change": {"economy_center": "兴|平|衰", "culture": "兴|平|衰",'
            '"commerce": "兴|平|衰", "military": "兴|平|衰", "urban": "兴|平|衰"},'
            '"region": "路名或全国", "narrative": "≤120字时代注记"}'
            "\nera_change 键仅限五维（economy_center/culture/commerce/military/urban）；"
            "trend 只给 兴/平/衰（幅度 ±10 由程序定幅迁移，不报数字）；narrative 只叙事。"
        )
        inj = ""
        if state is not None:
            try:
                from core.era_mechanic import era_brief, industry_brief
                inj = f"\n【当前时代】{era_brief(state)}\n【产业结构】{industry_brief(state)}"
            except Exception:
                pass
        sys_p += inj

        def validate(o):
            if not isinstance(o, dict) or "era_change" not in o:
                return None
            ec = o.get("era_change")
            if not isinstance(ec, dict):
                return None
            out = {}
            for d in ERA_DIMENSIONS:
                v = ec.get(d)
                if v not in ("兴", "平", "衰"):
                    return None
                out[d] = v
            o["era_change"] = out
            o["region"] = str(o.get("region", "全国"))[:12]
            o["narrative"] = _clean_text(str(o.get("narrative", "")))[:120]
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.5, max_tokens=300, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("era"))

    def situations_grade_decide(self, state=None, max_items=8):
        """局势推进档位契约（规范 §7）：**只给档位与叙事，数值由程序算**。

        输入（§7.1）：标题 / 进度档位 / **成败条件文本（含阈值）** / 最近 3 条 timeline /
        玩家 intent 文本。**禁止注入当前真实盘面读数**（阈值是规则，不是读数）；
        按"迫近者先评"排序（`deadline` 升序、次级 `id`），最多 `max_items` 条。
        输出（§7.2）：`{"grades": [{"situation_id", "grade", "narrative"}]}`，
        `grade ∈ verybad|bad|normal|good|verygood`，`narrative` 可为 null。
        非法档位 / 缺字段 / 重复 id / 未知 id / 越权字段 → **该条丢弃**（不改任何状态）；
        结果只写入 `state._situation_grades`（临时变量），由 Step 8.5 结算步消费。
        """
        from core.situations import GRADE_DELTA, describe_condition

        recs = [r for r in (getattr(state, "situations", None) or [])
                if isinstance(r, dict) and r.get("status") == "active"] if state is not None else []
        if not recs:
            return {"grades": []}
        recs = sorted(recs, key=lambda r: (r.get("deadline") if isinstance(r.get("deadline"), int)
                                           else 10 ** 9, str(r.get("id") or "")))
        recs = recs[:max_items]
        known = {str(r.get("id")) for r in recs}
        intents = {str(i.get("situation_id")): i
                   for i in (getattr(state, "_situation_intents_this_turn", None) or [])
                   if isinstance(i, dict)}

        def _band(v):
            """0–100 → 档位词（只给档位，不给读数）。"""
            try:
                x = float(v)
            except (TypeError, ValueError):
                return "未知"
            return "极低" if x < 20 else "低" if x < 40 else "中" if x < 60 else "高" if x < 80 else "极高"

        lines = []
        for r in recs:
            tl = [str(t.get("text")) for t in (r.get("timeline") or [])[-3:] if isinstance(t, dict)]
            it = intents.get(str(r.get("id")))
            lines.append(
                f"- id={r.get('id')}｜{r.get('title')}｜进度档位={_band(r.get('bar_value'))}"
                f"｜达成={describe_condition(r.get('resolve_condition'))}"
                f"｜失败={describe_condition(r.get('fail_condition'))}"
                f"｜连成={r.get('streak_ok')}/连败={r.get('streak_fail')}"
                + (f"｜本月圣意：{it.get('kind')}（{it.get('note') or ''}）" if it else "")
                + (f"｜近事：{' / '.join(tl)}" if tl else ""))
        sys_p = (
            "你是北宋史官兼枢密院检详，按月评定国事进展。\n"
            "输入：每条局势的标题、进度档位、达成/失败条件（阈值）、连续月数、最近三条月报线索、本月圣意。\n"
            "输出契约（严格 JSON）：\n"
            '{"grades": [{"situation_id": "上述 id 原样", "grade": "verybad|bad|normal|good|verygood",'
            ' "narrative": "本月该局势的一句史笔（≤60字，可 null）"}]}\n'
            "- 档位语义：verygood=大进、good=有进、normal=止步、bad=倒退、verybad=崩坏。\n"
            "- **只给档位与叙事，不得给出任何数字**；不得新增 id、不得改动条件、不得评价未列出的局势。"
        )
        user_p = "【本月经略】\n" + "\n".join(lines)

        def validate(o):
            if not isinstance(o, dict) or "grades" not in o:
                return None
            from core.situations import filter_grade_payload
            filtered = filter_grade_payload(o, known)      # 白名单过滤在 core 单点实现
            for g in filtered:
                if g.get("narrative") is not None:
                    g["narrative"] = _clean_text(str(g["narrative"]))[:60]
            o["grades"] = filtered
            return o

        raw = self._call(sys_p, user_p, temperature=0.3, max_tokens=900, json_mode=True)
        res = self._postprocess(raw, validate,
                                lambda: _ai_unavailable("situations_grade"))
        # 写入**临时变量**（不落档）：Step 8.5 消费后清空；AI 缺失 → 空表 → 程序按 inertia 推进
        grades = {}
        for g in (res.get("grades") if isinstance(res, dict) else []) or []:
            grades[str(g["situation_id"])] = {"grade": g.get("grade"),
                                              "narrative": g.get("narrative")}
        if state is not None:
            try:
                state._situation_grades = grades
            except Exception:
                pass
        return {"grades": list(grades.values())}

    def faction_decide(self, posture, state=None):
        """派系结算契约（党争推演）：推演各派系满意度/影响力变动、党争事件触发。
        输出：{"factions": {"新党": {"satisfaction": "微|小|中|大", "influence": "微|小|中|大", "stance": "进取|守成|观望"}, ...}, "events": [{"type": "党争|联姻|分裂|和解", "desc": "事件描述", "tier": "微|小|中|大"}], "narrative": "党争叙事"}"""
        sys_p = (
            "你是北宋史官，记录朝堂党争流变。根据当前派系满意度、影响力、皇威、政策倾向，推演本月派系动态。\n"
            "输出契约（严格 JSON）：\n"
            '{"factions": {"新党": {"satisfaction": "微|小|中|大", "influence": "微|小|中|大", "stance": "进取|守成|观望"}, '
            '"旧党": {"satisfaction": "微|小|中|大", "influence": "微|小|中|大", "stance": "进取|守成|观望"}}, '
            '"events": [{"type": "党争|联姻|分裂|和解|清算", "desc": "事件描述（≤40字）", "tier": "微|小|中|大"}], '
            '"narrative": "党争叙事（≤150字，体现朝堂倾轧、言路攻讦、陛下平衡之术）"}\n'
            "- satisfaction/influence 档位：微/小/中/大（正负由程序根据 stance 与政策判定）。\n"
            "- stance：进取=主张变法、守成=维护祖制、观望=随势而动。\n"
            "- events 类型仅限：党争/联姻/分裂/和解/清算。\n"
            "- 只给档位不给数字；不写数值。"
        )
        inj = ""
        if state is not None:
            try:
                factions = getattr(state, "factions", {})
                if factions:
                    # 审查 P0-2：满意度/影响力用区间脱敏，皇威用等级描述——不泄精确值
                    from ai.desensitize import desensitize_band
                    lines = []
                    for name, f in factions.items():
                        sat = f.get("satisfaction", 50)
                        inf = f.get("influence", 50)
                        lines.append(f"{name}: 满意度{desensitize_band(sat, '', 0.18, 0.03)}"
                                     f" 影响力{desensitize_band(inf, '', 0.18, 0.03)}")
                    inj += f"\n【当前派系】{'; '.join(lines)}"
                try:
                    pi = state.get_prestige_info()
                    inj += f"\n【皇威】{pi.get('description', '平平')}"
                except Exception:
                    inj += "\n【皇威】平平"
                # 集团 ⊆ POP：每派的**人口/财赋基本盘**（势力有源，不是无源影响力）
                # 以及在场的改革使哪些 POP 受益/受损 —— AI 据此推演满意度与影响力档位，
                # 数值仍由程序算（POP 挂载律；`core/faction_basis.py` 为唯一权威）。
                try:
                    from core.faction_basis import build_faction_channels
                    fc = build_faction_channels(state)
                    bases = []
                    for name, row in (fc.get("factions") or {}).items():
                        b = row.get("basis_readout") or {}
                        if b:
                            bases.append(f"{name}={b.get('subset_note', '')}"
                                         f"（人口 {int(b.get('pop_size') or 0):,}）")
                    if bases:
                        inj += "\n【集团基本盘（⊆POP阶级）】" + "；".join(bases)
                    for item in (fc.get("emerging") or []):
                        gain = "、".join(f"{g.get('class')}（{g.get('why')}）"
                                        for g in item.get("gain") or [])
                        lose = "、".join(f"{l.get('class')}（{l.get('why')}）"
                                         for l in item.get("lose") or [])
                        inj += (f"\n【在场改革·{item.get('label')}】受益 POP：{gain or '—'}；"
                                f"受损 POP：{lose or '—'}")
                        for f in item.get("emergent") or []:
                            inj += (f"；或催生新集团「{f.get('name')}」"
                                    f"（基本盘 {f.get('pop_basis', {}).get('subset_of')}"
                                    f"／{'/'.join(f.get('pop_basis', {}).get('pop_classes') or [])}）")
                    inj += ("\n- 请按上述 POP 得失推演各派满意度/影响力档位（受益者升、受损者降）；"
                            "未声明 POP 基本盘的集团不得凭空出现。")
                except Exception:
                    pass
            except Exception:
                pass
        sys_p += inj

        def validate(o):
            if not isinstance(o, dict) or "factions" not in o:
                return None
            facs = o.get("factions", {})
            if not isinstance(facs, dict):
                return None
            valid_facs = {}
            for name, f in facs.items():
                if not isinstance(f, dict):
                    return None
                sat = str(f.get("satisfaction", "")).strip()
                inf = str(f.get("influence", "")).strip()
                stance = str(f.get("stance", "")).strip()
                # P1-14：拒绝式——非法档位不得静默填「小/观望」
                if sat not in ("微", "小", "中", "大") or inf not in ("微", "小", "中", "大") \
                        or stance not in ("进取", "守成", "观望"):
                    return None
                valid_facs[name] = {"satisfaction": sat, "influence": inf, "stance": stance}
            o["factions"] = valid_facs
            events = o.get("events", [])
            if not isinstance(events, list):
                return None
            valid_events = []
            for e in events[:3]:
                if not isinstance(e, dict):
                    return None
                etype = str(e.get("type", "")).strip()
                desc = str(e.get("desc", "")).strip()
                tier = str(e.get("tier", "")).strip()
                if etype not in ("党争", "联姻", "分裂", "和解", "清算"):
                    return None
                if tier not in ("微", "小", "中", "大"):
                    return None
                valid_events.append({"type": etype, "desc": desc[:40], "tier": tier})
            o["events"] = valid_events
            o["narrative"] = _clean_text(str(o.get("narrative", "")))[:150]
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.5, max_tokens=400, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("faction"))

    def land_local_decide(self, posture, state=None):
        """田亩与地方州县契约（户部/转运司/路分）：推演清丈、劝垦、均税、地方民情。
        输出：{"prefectures": {"路名": {"survey": "微|小|中|大", "reclaim": "微|小|中|大", "tax_fair": "微|小|中|大", "mood": "安定|平实|动荡"}}, "narrative": "田亩地方叙事"}"""
        sys_p = (
            "你是北宋转运使，巡按诸路田亩户籍。根据当前垦田、隐漏、荒田、各路民情，推演本月清丈劝垦成效。\n"
            "输出契约（严格 JSON）：\n"
            '{"prefectures": {"京东": {"survey": "微|小|中|大", "reclaim": "微|小|中|大", "tax_fair": "微|小|中|大", "mood": "安定|平实|动荡"}, '
            '"河北": {"survey": "微|小|中|大", "reclaim": "微|小|中|大", "tax_fair": "微|小|中|大", "mood": "安定|平实|动荡"}}, '
            '"narrative": "田亩地方叙事（≤150字，体现清丈阻力、劝垦成效、百姓疾苦）"}\n'
            "- survey=清丈力度、reclaim=劝垦力度、tax_fair=均税力度，档位：微/小/中/大。\n"
            "- mood：安定/平实/动荡。\n"
            "- 只给档位不给数字；不写数值。"
        )
        inj = ""
        if state is not None:
            try:
                prefs = getattr(state, "prefectures", {})
                if prefs:
                    # 审查 P0-2：户数/田亩为精确真值，不外泄——只给路名+定性民情
                    lines = []
                    for name, p in list(prefs.items())[:8]:
                        mood = p.get("mood", "中")
                        lines.append(f"{name}: 民情{mood}")
                    inj += f"\n【诸路概况】{'; '.join(lines)}"
                inj += "（田亩隐漏难测，以清丈/劝垦档位推演为准，不必外引精确亩数。）"
            except Exception:
                pass
        sys_p += inj

        def validate(o):
            if not isinstance(o, dict) or "prefectures" not in o:
                return None
            prefs = o.get("prefectures", {})
            if not isinstance(prefs, dict):
                return None
            valid_prefs = {}
            for name, p in prefs.items():
                if not isinstance(p, dict):
                    return None
                survey = str(p.get("survey", "")).strip()
                reclaim = str(p.get("reclaim", "")).strip()
                tax_fair = str(p.get("tax_fair", "")).strip()
                mood = str(p.get("mood", "")).strip()
                # P1-14：拒绝式——非法档位不得静默填「小/平实」
                if survey not in ("微", "小", "中", "大") or reclaim not in ("微", "小", "中", "大") \
                        or tax_fair not in ("微", "小", "中", "大") \
                        or mood not in ("安定", "平实", "动荡"):
                    return None
                valid_prefs[name] = {"survey": survey, "reclaim": reclaim, "tax_fair": tax_fair, "mood": mood}
            o["prefectures"] = valid_prefs
            o["narrative"] = _clean_text(str(o.get("narrative", "")))[:150]
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.4, max_tokens=500, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("land_local"))

    def granary_decide(self, posture, state=None):
        """仓廪漕运契约（户部/漕运司）：推演太仓存粟、漕运到仓、常平仓平粜、军粮调拨。
        输出：{"granary": {"inflow": "微|小|中|大", "outflow": "微|小|中|大", "price_stabilize": "微|小|中|大", "army_supply": "微|小|中|大"}, "narrative": "仓漕叙事"}"""
        sys_p = (
            "你是北宋漕运使，掌太仓出纳、漕船调度、常平平粜。根据当前太仓存粟、漕运能力、军粮需求、粮价，推演本月仓漕运作。\n"
            "输出契约（严格 JSON）：\n"
            '{"granary": {"inflow": "微|小|中|大", "outflow": "微|小|中|大", "price_stabilize": "微|小|中|大", "army_supply": "微|小|中|大"}, '
            '"narrative": "仓漕叙事（≤120字，体现漕运风险、仓储损耗、平粜成效、军粮保障）"}\n'
            "- inflow=漕运入仓、outflow=发仓/平粜/军粮、price_stabilize=平抑物价、army_supply=军粮保障，档位：微/小/中/大。\n"
            "- 只给档位不给数字；不写数值。"
        )
        inj = ""
        if state is not None:
            try:
                # 审查 P0-2：仓漕读数改走区间/滞后（_decide_state_text），
                # 杜绝精确太仓/漕运/粮价进 prompt。
                inj = "\n【仓部奏报】\n" + _decide_state_text(state)
            except Exception:
                pass
        sys_p += inj

        def validate(o):
            if not isinstance(o, dict) or "granary" not in o:
                return None
            g = o.get("granary", {})
            if not isinstance(g, dict):
                return None
            valid_g = {}
            for k in ("inflow", "outflow", "price_stabilize", "army_supply"):
                v = str(g.get(k, "")).strip()
                # P1-14：拒绝式——非法档位不得静默填「小」
                if v not in ("微", "小", "中", "大"):
                    return None
                valid_g[k] = v
            o["granary"] = valid_g
            o["narrative"] = _clean_text(str(o.get("narrative", "")))[:120]
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.4, max_tokens=300, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("granary"))

    def finance_decide(self, posture, state=None):
        """财政金融契约（户部度支/市舶/交子务/银行）：推演货币、市舶、交子、银行、本位制等财政金融政务。
        输出：{"narrative": "财政金融叙事（≤150字）", "tone": "得利|平实|扰民", "risk_hint": "隐患提示"}"""
        sys_p = _load_prompt("finance", **{
            "treasury_desc": "国库充盈" if (state and getattr(state, "treasury", 0) > 5_000_000) else "国库告匮",
            "jiaozi_desc": "交子流通良好" if (state and getattr(state, "jiaozi", {}).get("issued", 0) > 0) else "交子未行",
            "maritime_desc": "市舶通商兴旺" if (state and getattr(state, "maritime_trade", 0) > 0) else "市舶未通",
            "coin_desc": "钱荒稍缓" if (state and getattr(state, "grain_price", 1.0) < 1.2) else "钱荒加剧",
            "bank_desc": "银行已设" if (state and getattr(state, "bank", {}).get("established", False)) else "银行未设",
            "act": "常规度支"
        })
        # 使用现有 finance.md 提示词

        def validate(o):
            if not isinstance(o, dict):
                return None
            o["narrative"] = _clean_text(str(o.get("narrative", "")))[:150]
            tone = str(o.get("tone", "平实")).strip()
            if tone not in ("得利", "平实", "扰民"):
                tone = "平实"
            o["tone"] = tone
            o["risk_hint"] = _clean_text(str(o.get("risk_hint", "")))[:80]
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.5, max_tokens=300, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("finance"))

    def treasury_decide(self, posture, state=None):
        """国库契约（三司/内帑）：推演国库收支、内帑拨付、度支平衡、储备金。
        输出：{"treasury": {"income": "微|小|中|大", "expenditure": "微|小|中|大", "reserve": "微|小|中|大", "imperial_transfer": "微|小|中|大"}, "narrative": "国库叙事"}"""
        sys_p = (
            "你是北宋三司使，掌天下财赋出纳。根据当前国库存款、税收、支出、内帑拨付，推演本月国库收支平衡。\n"
            "输出契约（严格 JSON）：\n"
            '{"treasury": {"income": "微|小|中|大", "expenditure": "微|小|中|大", "reserve": "微|小|中|大", "imperial_transfer": "微|小|中|大"}, '
            '"narrative": "国库叙事（≤120字，体现入不敷出、节流开源、内帑拨付、储备金安危）"}\n'
            "- income=税收收入、expenditure=经常支出、reserve=储备金积累、imperial_transfer=内帑拨付/回笼，档位：微/小/中/大。\n"
            "- 只给档位不给数字；不写数值。"
        )
        inj = ""
        if state is not None:
            try:
                # 审查 P0-2：只注入区间/滞后/定性文本（_decide_state_text），
                # 杜绝把精确国库/内帑/收支写进 prompt（脱敏四层失效）。
                inj = "\n【三司奏报】\n" + _decide_state_text(state)
            except Exception:
                pass
        sys_p += inj

        def validate(o):
            if not isinstance(o, dict) or "treasury" not in o:
                return None
            t = o.get("treasury", {})
            if not isinstance(t, dict):
                return None
            valid_t = {}
            for k in ("income", "expenditure", "reserve", "imperial_transfer"):
                v = str(t.get(k, "小")).strip()
                if v not in ("微", "小", "中", "大"):
                    v = "小"
                valid_t[k] = v
            o["treasury"] = valid_t
            o["narrative"] = _clean_text(str(o.get("narrative", "")))[:120]
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.4, max_tokens=300, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("treasury"))

    def emperor_personal_decide(self, posture, state=None):
        """皇帝个人行动契约 v2（言枢密定稿 + A15 素材）：推演陛下本月个人行止与后果。

        输出：{"location": "宫里|京城|出京", "mode": "公开|微服",
              "action": "该 location×mode 格内白名单行动（跨格子非法）",
              "prepared": bool, "risk": "低|中|高",
              "effects": {"威望|民心|健康|心情": 档位词(可带 +/- 前缀)},
              "narrative": "≤100字起居注叙事"}
        拒绝式：location/mode/action 越界、跨格子、risk 非法、effects 键越界 → 整单失败
        （程序只取档位词换算封顶；费用/时代门槛/月度限由程序核算，AI 不写数值）。
        """
        from content.data import (
            IMPERIAL_ACTION_MATRIX, IMPERIAL_LOCATIONS, IMPERIAL_MODES,
            IMPERIAL_RISK_LEVELS, IMPERIAL_EFFECT_DIM,
        )
        sys_p = (
            "你是北宋起居注兼内侍省都知，推演陛下本月个人行动与后果。\n"
            "输出契约（严格 JSON）：\n"
            '{"location": "宫里|京城|出京", "mode": "公开|微服", "action": "行动名",'
            '"prepared": bool, "risk": "低|中|高",'
            '"effects": {"威望": 档位词, "民心": 档位词, "健康": 档位词, "心情": 档位词},'
            '"narrative": "起居注叙事（≤100字）"}\n'
            "- action 必须属于该 (location, mode) 组合的合法行动白名单（跨格子非法）；\n"
            "- effects 键仅限 威望/民心/健康/心情，值只用档位词（无/微/小/中/大/巨/极，可带 +/- 前缀表升降）；\n"
            "- 只给档位不给数值；费用、时代门槛、行程由朝廷程序核算，陛下不可自定。"
        )
        inj = ""
        if state is not None:
            try:
                act = getattr(state, "imperial_action", None) or {}
                if act:
                    inj += (f"\n【陛下本月已定行止】{act.get('location', '')}·"
                            f"{act.get('mode', '')}·{act.get('action', '')}"
                            f"（契约 action 须与此一致）")
                try:
                    from content.data import desensitize_satisfaction
                    pi = state.get_prestige_info()
                    inj += (f"\n【皇威】{pi.get('description', '平平')} "
                            f"【民心】{desensitize_satisfaction(getattr(state, 'population_satisfaction', 50))} "
                            f"【年份】{getattr(state, 'year', 1)}年")
                except Exception:
                    inj += f"\n【年份】{getattr(state, 'year', 1)}年"
            except Exception:
                pass
        sys_p += inj

        def validate(o):
            if not isinstance(o, dict):
                return None
            loc = str(o.get("location", ""))
            mode = str(o.get("mode", ""))
            action = str(o.get("action", ""))
            if loc not in IMPERIAL_LOCATIONS or mode not in IMPERIAL_MODES:
                return None
            matrix = IMPERIAL_ACTION_MATRIX.get(loc, {}).get(mode, {})
            if action not in matrix:
                return None  # 跨格子非法 → 拒绝式整单失败
            prepared = o.get("prepared")
            if not isinstance(prepared, bool):
                return None
            risk = str(o.get("risk", ""))
            if risk not in IMPERIAL_RISK_LEVELS:
                return None
            eff = o.get("effects")
            if not isinstance(eff, dict):
                return None
            out_eff = {}
            for k, v in eff.items():
                if k not in IMPERIAL_EFFECT_DIM:
                    return None  # 键越界 → 拒绝式
                if not isinstance(v, str) or not v.strip():
                    return None
                text = v.strip()
                direction = 1.0
                if text.startswith("+"):
                    text = text[1:]
                elif text.startswith("-"):
                    direction = -1.0
                    text = text[1:]
                tier = normalize_tier(text)
                if tier not in _TIERS7:
                    return None
                out_eff[k] = ("-" if direction < 0 else "") + tier
            narrative = _clean_text(str(o.get("narrative", "")))[:100]
            return {"location": loc, "mode": mode, "action": action,
                    "prepared": prepared, "risk": risk,
                    "effects": out_eff, "narrative": narrative}

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.5, max_tokens=300, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("emperor_personal"))

    def hidden_state_decide(self, posture, state=None):
        """隐藏状态契约（密探/内侍/枢密）：推演谍报、暗流、潜在危机、未公开情报。
        输出：{"intel": [{"region": "路名/外邦", "type": "谍报|流言|异动|密谋", "credibility": "低|中|高", "desc": "情报摘要"}], "crises": [{"type": "叛乱|瘟疫|外患|党祸|水旱", "probability": "微|小|中|大", "desc": "潜在危机描述"}], "narrative": "密探叙事"}"""
        sys_p = (
            "你是北宋枢密院密探头目，掌握朝野未公开之情报。根据当前外邦态度、派系矛盾、民情、灾荒征兆，推演本月隐情暗流。\n"
            "输出契约（严格 JSON）：\n"
            '{"intel": [{"region": "河北/金国/辽国/...", "type": "谍报|流言|异动|密谋", "credibility": "低|中|高", "desc": "情报摘要（≤30字）"}], '
            '"crises": [{"type": "叛乱|瘟疫|外患|党祸|水旱", "probability": "微|小|中|大", "desc": "潜在危机描述（≤40字）"}], '
            '"narrative": "密探叙事（≤120字，体现情报网运作、真假难辨、防微杜渐）"}\n'
            "- intel.type 仅限：谍报/流言/异动/密谋；credibility：低/中/高。\n"
            "- crises.type 仅限：叛乱/瘟疫/外患/党祸/水旱；probability：微/小/中/大。\n"
            "- 只给定性不给数值。"
        )
        inj = ""
        if state is not None:
            try:
                # 审查 P0-2：外邦态度给定性、流民给区间（滞后）——不泄精确 attitude/流民数
                ext = getattr(state, "external", {}) or {}
                _rel = lambda a: "友善" if a >= 70 else ("一般" if a >= 40 else ("敌视" if a >= 20 else "仇敌"))
                _parts = [f"{k}:{_rel((v or {}).get('attitude', 50))}"
                          for k, v in ext.items() if isinstance(v, dict)]
                from ai.desensitize import desensitize_band
                _ek = getattr(state, "economy_knowledge", None)
                _lag = _ek.get("refugee_count") if isinstance(_ek, dict) else None
                refugee = getattr(state, "refugee_count", 0)
                _rb = desensitize_band(refugee, "口", 0.20, 0.05, lag_value=_lag) if refugee else "无"
                inj += f"\n【外邦】{('；'.join(_parts)) if _parts else '未详'} 【流民】{_rb}"
                factions = getattr(state, "factions", {})
                if factions:
                    for name, f in factions.items():
                        sat = f.get("satisfaction", 50)
                        if sat < 30:
                            inj += f" 【{name}不满】"
            except Exception:
                pass
        sys_p += inj

        def validate(o):
            if not isinstance(o, dict):
                return None
            intel = o.get("intel", [])
            if not isinstance(intel, list):
                intel = []
            valid_intel = []
            for i in intel[:4]:
                if not isinstance(i, dict):
                    continue
                region = str(i.get("region", "")).strip()
                itype = str(i.get("type", "")).strip()
                cred = str(i.get("credibility", "中")).strip()
                desc = str(i.get("desc", "")).strip()
                if itype not in ("谍报", "流言", "异动", "密谋"):
                    continue
                if cred not in ("低", "中", "高"):
                    cred = "中"
                valid_intel.append({"region": region[:8], "type": itype, "credibility": cred, "desc": desc[:30]})
            o["intel"] = valid_intel
            crises = o.get("crises", [])
            if not isinstance(crises, list):
                crises = []
            valid_crises = []
            for c in crises[:3]:
                if not isinstance(c, dict):
                    continue
                ctype = str(c.get("type", "")).strip()
                prob = str(c.get("probability", "小")).strip()
                desc = str(c.get("desc", "")).strip()
                if ctype not in ("叛乱", "瘟疫", "外患", "党祸", "水旱"):
                    continue
                if prob not in ("微", "小", "中", "大"):
                    prob = "小"
                valid_crises.append({"type": ctype, "probability": prob, "desc": desc[:40]})
            o["crises"] = valid_crises
            o["narrative"] = _clean_text(str(o.get("narrative", "")))[:120]
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.5, max_tokens=400, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("hidden_state"))

    def research_decide(self, posture, state=None):
        """承接模式·研发推演契约（言枢密设计）：{node, invest, talent, risk, narrative}——
        node 存在（官方 TECH_NODES 或玩家 tech_registry）、三档 ∈ 7 档词、拒绝式；
        程序换算（invest→拨款额守恒、talent→masters 加成、risk→失败概率程序随机）。"""
        from core.asset_context import get_tech_node
        from core.registries import node_entry
        sys_p = (
            "你是承接研发的工部侍郎。把本期攻关量化为 JSON 契约：\n"
            '{"node": "节点id（官方或玩家注册）", "invest": "微|小|中|大",'
            '"talent": "微|小|中|大", "risk": "微|小|中|大", "narrative": "≤120字"}'
            "\ninvest 拨款力度（程序按 10万~50万×档换算守恒入 tech 攻关）；"
            "talent 工匠投入（→ masters 加成）；risk 失败概率（程序随机，非档位直译）。"
        )

        def validate(o):
            if not isinstance(o, dict) or "node" not in o:
                return None
            nid = str(o.get("node", "")).strip()
            if not nid:
                return None
            # node 存在（官方或玩家注册）
            node = None
            if get_tech_node(nid):
                node = nid
            elif state is not None:
                try:
                    if node_entry(state, nid):
                        node = nid
                except Exception:
                    node = None
            if not node:
                return None
            for k in ("invest", "talent", "risk"):
                v = o.get(k)
                if not isinstance(v, str) or v not in _TIERS7:
                    return None
                o[k] = v
            o["node"] = nid
            o["narrative"] = _clean_text(str(o.get("narrative", "")))[:120]
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.4, max_tokens=300, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("research"))

    def build_new_branch_decide(self, posture, state=None):
        """新兵种设立契约（言枢密 schema，branch_registry 落地）：
        branch_name 任意名≤12字 + lineage 7 系（equipment/training/mobility 特化 +
        position 场景）+ specialization 档位 + equip_focus（可选）+ narrative；
        拒绝式（不重名/合法档位/不超科技由 register_branch 复核）。"""
        from core.registries import SPECIALIZATION_TIERS
        from content.data import BRANCH_BASE
        sys_p = (
            "你是北宋枢密院。把陛下设立新兵种的提案量化为 JSON 契约：\n"
            '{"branch_name": "兵种名≤12字（史实番号如 神臂弩/胜捷军/水虎翼 或自创）",'
            '"lineage": "重骑兵|轻骑兵|重步兵|轻步兵|弓弩兵|水军|器械兵",'
            '"specialization": "equipment|training|mobility|equipment_training|equipment_mobility|training_mobility|balanced",'
            '"tier": "微|小|中|大", "position": "平原|山地|水战|攻城|守城|野战|巷战",'
            '"equip_focus": "火器|弓弩|战马|(可空)", "narrative": "≤120字建军叙事"}'
            "\nspecialization 7 系 + tier 档位（程序按 BRANCH_SPEC 换算系数封顶）；"
            "equip_focus 触发科技门槛（火器→gunpowder、弓弩→弓弩工艺、战马→马政）；"
            "只给意图与叙事，数值/成本由 register_branch 程序核算。"
        )

        def validate(o):
            if not isinstance(o, dict) or "branch_name" not in o:
                return None
            name = str(o.get("branch_name", "")).strip()[:12]
            if not name:
                return None
            if o.get("lineage") not in BRANCH_BASE:
                return None
            if o.get("specialization") not in SPECIALIZATION_TIERS:
                return None
            if o.get("tier") not in _TIERS7:
                return None
            if o.get("position") not in ("平原", "山地", "水战", "攻城", "守城", "野战", "巷战"):
                return None
            o["branch_name"] = name
            o["narrative"] = _clean_text(str(o.get("narrative", "")))[:120]
            o["equip_focus"] = o.get("equip_focus") if o.get("equip_focus") in ("火器", "弓弩", "战马") else ""
            return o

        raw = self._call(sys_p, f"【朝局】{posture}", temperature=0.4, max_tokens=300, json_mode=True)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("branch"))
