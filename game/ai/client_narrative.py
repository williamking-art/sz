# -*- coding: utf-8 -*-
"""宋祚 · 部门叙事子模块（9 类 prompt 调用 + 通用叙事调用）。

拆分自 ai/client.py：以 mixin 形式承载部门叙事方法，AIClient 继承之。
"""
from ai.client_utils import _ai_unavailable, _clean_text, _load_prompt


class ClientNarrativeMixin:
    # ============================================================
    # 六部施政叙事
    # ============================================================
    def govern_yamen(self, yamen_name, yamen_duty, yamen_faction, act, state_summary):
        sys_p = _load_prompt("yamen_govern", yamen_name=yamen_name, yamen_duty=yamen_duty,
                             yamen_faction=yamen_faction, act=act)
        return self._narrative_call(sys_p, state_summary, "yamen")

    # ============================================================
    # 地方州县叙事
    # ============================================================
    def local_policy(self, pref_name, households, land, mood_desc, act, state_summary):
        sys_p = _load_prompt("local_policy", pref_name=pref_name, households=households,
                             land=land, mood_desc=mood_desc, act=act)
        return self._narrative_call(sys_p, state_summary, "local")

    # ============================================================
    # 田亩户籍叙事
    # ============================================================
    def land_manage(self, cultivated, households, hidden_rate_desc, wasteland, act, state_summary):
        sys_p = _load_prompt("land_manage", cultivated=cultivated, households=households,
                             hidden_rate_desc=hidden_rate_desc, wasteland=wasteland, act=act)
        return self._narrative_call(sys_p, state_summary, "land")

    # ------------------- 新增缺失维度 -------------------
    def finance(self, treasury_desc, jiaozi_desc, maritime_desc, coin_desc, bank_desc, act, state_summary):
        sys_p = _load_prompt("finance", treasury_desc=treasury_desc, jiaozi_desc=jiaozi_desc,
                             maritime_desc=maritime_desc, coin_desc=coin_desc, bank_desc=bank_desc, act=act)
        return self._narrative_call(sys_p, state_summary, "finance")

    def exam(self, exam_desc, school_desc, scholar_desc, act, state_summary):
        sys_p = _load_prompt("exam", exam_desc=exam_desc, school_desc=school_desc,
                             scholar_desc=scholar_desc, act=act)
        return self._narrative_call(sys_p, state_summary, "exam")

    def science(self, tech_desc, workshop_desc, miltech_desc, act, state_summary):
        sys_p = _load_prompt("science", tech_desc=tech_desc, workshop_desc=workshop_desc,
                             miltech_desc=miltech_desc, act=act)
        return self._narrative_call(sys_p, state_summary, "science")

    def military_expand(self, army_desc, front_desc, general_desc, act, state_summary):
        sys_p = _load_prompt("military_expand", army_desc=army_desc, front_desc=front_desc,
                             general_desc=general_desc, act=act)
        return self._narrative_call(sys_p, state_summary, "military")

    def diplomacy(self, liao_desc, jin_desc, xixia_desc, alliance_desc, act, state_summary):
        sys_p = _load_prompt("diplomacy", liao_desc=liao_desc, jin_desc=jin_desc,
                             xixia_desc=xixia_desc, alliance_desc=alliance_desc, act=act)
        return self._narrative_call(sys_p, state_summary, "diplomacy")

    def reform(self, court_desc, abuse_desc, lean_desc, act, state_summary):
        sys_p = _load_prompt("reform", court_desc=court_desc, abuse_desc=abuse_desc,
                             lean_desc=lean_desc, act=act)
        return self._narrative_call(sys_p, state_summary, "reform")

    # ============================================================
    # 通用叙事调用（yamen/local/land/finance/exam/...）
    # ============================================================
    def _narrative_call(self, sys_p, state_summary, tag):
        def validate(o):
            if not isinstance(o, dict) or "narrative" not in o:
                return None
            o["narrative"] = _clean_text(o.get("narrative", ""))
            o["tone"] = str(o.get("tone", "平实"))[:6]
            for extra in ("risk_hint", "talent_hint", "tech_hint", "defense_hint",
                          "alert_hint", "faction_hint"):
                if extra in o:
                    o[extra] = str(o[extra])[:60]
            if not o["narrative"]:
                return None
            return o
        raw = self._call(sys_p, f"【朝局】{state_summary}", temperature=0.85)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("narrative"))
