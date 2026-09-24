# -*- coding: utf-8 -*-
"""宋祚 · 叙事/事件/建言/结局契约子模块。

拆分自 ai/client.py：以 mixin 形式承载契约方法，AIClient 继承之。
零行为变更：方法体原样搬运。
"""
from ai.client_utils import (
    _ai_unavailable, _clean_text, _load_prompt,
)
from ai.narrative_guard import (
    _validate_narrative_numbers, _build_numeric_ranges, _build_source_closure,
    build_character_statuses, _validate_characters,
)
from ai.validators import _narrative_fallback


def _validate_scenes(scenes: list, min_count: int = 2, max_count: int = 12) -> list:
    """③ 分幕约束后验：幕数钳位、字数钳位、脱敏（去阿拉伯数字）、空幕占位。

    - 幕数 < min_count：补「有司补录」占位幕；> max_count：截断；
    - 每幕 text 20–120 字：过长截断、过短标 [文略]；
    - text 含阿拉伯数字：替换为「数」（脱敏约束，与 prompt「不写具体数字」对齐）。
    """
    if not isinstance(scenes, list):
        return []
    out = []
    for s in scenes[:max_count]:
        if not isinstance(s, dict):
            continue
        text = str(s.get("text", "") or "")
        # 脱敏：阿拉伯数字 → 「数」（prompt 约束后验）
        import re
        text = re.sub(r"\d+", "数", text)
        if len(text) < 20:
            text = text + "（文略）"
        elif len(text) > 120:
            text = text[:118] + "…"
        out.append({"scene": str(s.get("scene", ""))[:16], "text": text})
    # 不足 min_count 补占位
    while len(out) < min_count:
        idx = len(out) + 1
        out.append({"scene": f"补录{idx}", "text": "（本月此幕暂缺，有司补录存档。）"})
    return out

class MiscContractMixin:
    def monthly_report(self, year, month, era_name, posture):
        sys_p = _load_prompt("monthly_report", year=year, month=month, era_name=era_name, posture=posture)

        def validate(o):
            if not isinstance(o, dict) or "report" not in o:
                return None
            o["report"] = _clean_text(o.get("report", ""))
            # 众生相分幕（可选，向后兼容）：scenes 为 [{"scene","text"}] 数组
            scenes = o.get("scenes")
            if isinstance(scenes, list):
                o["scenes"] = [
                    {"scene": str(s.get("scene", ""))[:16],
                     "text": _clean_text(str(s.get("text", "")))}
                    for s in scenes if isinstance(s, dict) and s.get("text")
                ]
            else:
                o["scenes"] = []
            # ③ 分幕约束后验：幕数/字数/脱敏
            o["scenes"] = _validate_scenes(o["scenes"], min_count=2, max_count=12)
            return o if o["report"] else None
        # 朝局 hash 缓存（同月同态势不重复烧 token）
        raw = self._cached_call("monthly", posture, sys_p, "", 0.7, 600)
        return self._postprocess(raw, validate, lambda: _narrative_fallback("report"))

    def civilian_situation(self, state=None):
        """**民间反应（AI 版）**：按〔当前局势真值 + 本回合落下的圣旨〕推演民间当场反应。

        语义分工（用户定稿 2026-09-21）：「民间情况」＝民间反应（平民/士绅/商贾），
        与"月报"（结算后的**官方总结**：数值变化/政务进度/人事变动）**不同源、不同时**——
        本路只写"民间会怎么看"，不碰月底结算的数值结果（官方月报走 `monthly_report`）。

        失败 → 程序版兜底（`narrative_fallback.civilian_situation` 或 fallback_civilian），
        不阻塞结算：装饰层全兜底，与 month-report 同一韧性口径。
        """
        from ai.narrative_fallback import civilian_situation as _civ_fallback
        # ---- 真值输入（program side）----
        era_name = str(getattr(state, "era_name", "") or "")
        posture = str(getattr(state, "posture", "") or "")
        decs = list(getattr(state, "pending_decrees", None) or [])
        titles = [str(d.get("title", "")) for d in decs[-3:]
                  if isinstance(d, dict) and d.get("title")]
        fmt = lambda v: ("，".join(titles) if titles else "（本回合未落新旨）")   # noqa: E731
        # 局势真值摘要（简短，不做决策数值）——防伪造，只把真值喂给模型
        facts = []
        try:
            prefs = getattr(state, "prefectures", {}) or {}
            if prefs:
                ps = [round(float(p.get("grain_price", 1.0) or 1.0), 2) for p in prefs.values()]
                ms = [int(p.get("mood", 50) or 50) for p in prefs.values()]
                facts.append(f"粮价均值 {sum(ps) / len(ps):.2f}"
                             f"（最高 {max(ps):.2f} / 最低 {min(ps):.2f}）")
                facts.append(f"民情均值 {sum(ms) / len(ms):.0f}/100")
            # 众生相 P1：六民生齿真值（民间反应按阶层锚定）
            try:
                from core.commands import pop_sentiment_brief
                _brief = pop_sentiment_brief(state)
                for _ln in _brief.split("\n")[1:]:   # 跳过标题行
                    if _ln.strip() and _ln.startswith("- "):
                        facts.append(_ln.strip()[2:])
            except Exception:
                pass
            if int(getattr(state, "disaster_severity", 0) or 0) > 0:
                facts.append(f"灾情 {int(state.disaster_severity)} 级（民间流民渐多）")
            facs = getattr(state, "factions", None)
            neg = [k for k, v in (facs or {}).items()
                   if isinstance(v, dict) and int(v.get("satisfaction", 50) or 50) < 40]
            if neg:
                facts.append("集团不满：" + "、".join(neg))
        except Exception:
            pass
        sys_p = _load_prompt(
            "civilian_reaction",
            era_name=era_name, posture=posture,
            plural_decrees=("" if len(titles) < 2 else "（本回合最多 3 道；无新旨则此栏为空）"),
            titles="；".join(titles) if titles else "（本回合未落新旨）",
            facts="；".join(facts) if facts else "（无显著变动）")

        def validate(o):
            if not isinstance(o, dict) or not o.get("text"):
                return None
            o["text"] = _clean_text(o.get("text", ""))
            # 众生相分幕（④ 民间反应分幕化）：农人/士绅/商贾 3 幕 + ③ 后验
            scenes = o.get("scenes")
            if isinstance(scenes, list):
                o["scenes"] = [
                    {"scene": str(s.get("scene", ""))[:16],
                     "text": _clean_text(str(s.get("text", "")))}
                    for s in scenes if isinstance(s, dict) and s.get("text")
                ]
            else:
                o["scenes"] = []
            o["scenes"] = _validate_scenes(o["scenes"], min_count=1, max_count=5)
            return o if o["text"] else None

        raw = self._cached_call("civilian", posture, sys_p, "", 0.8, 500)
        res = self._postprocess(raw, validate, None)
        if not isinstance(res, dict) or not res.get("text"):
            return {"text": _civ_fallback(state), "_fallback": True}
        return res

    def event_narrative(self, event_title, event_context, state=None):
        sys_p = _load_prompt("event_narrative", event_title=event_title, event_context=event_context)
        # 12 步 agent 化 P2：事件叙事闭集化（agent 只从本期来源闭集取材）
        if state is not None:
            try:
                closure = _build_source_closure(state)
                sys_p += f"\n{closure}"
            except Exception:
                pass
            # 众生相 P1：六民生齿真值注入（锚定各阶层真实状态）
            try:
                from core.commands import pop_sentiment_brief
                sys_p += "\n" + pop_sentiment_brief(state)
            except Exception:
                pass

        def validate(o):
            if not isinstance(o, dict) or "narrative" not in o:
                return None
            o["narrative"] = _clean_text(o.get("narrative", ""))
            # 拒绝式：severity_hint 缺失/非法 → 整单失败（不默认「中」）
            if o.get("severity_hint") not in ("轻", "中", "重"):
                return None
            # 众生相分幕（可选，向后兼容）+ ③ 后验
            scenes = o.get("scenes")
            if isinstance(scenes, list):
                o["scenes"] = [
                    {"scene": str(s.get("scene", ""))[:16],
                     "text": _clean_text(str(s.get("text", "")))}
                    for s in scenes if isinstance(s, dict) and s.get("text")
                ]
            else:
                o["scenes"] = []
            o["scenes"] = _validate_scenes(o["scenes"], min_count=1, max_count=8)
            # 审查 P2-4 修复：人物查表——叙事命中已故/已黜 → 标记回喂
            if state is not None:
                try:
                    statuses = build_character_statuses(state)
                    _bad, _names = _validate_characters(o["narrative"], statuses)
                    if _bad:
                        o["_char_violation"] = _names
                except Exception:
                    pass
            return o if o["narrative"] else None
        # 审查 P2-4 修复：传入数字区间 ranges（叙事数字须落在注入区间，区间外改写定性词）
        _ranges = None
        if state is not None:
            try:
                _ranges = _build_numeric_ranges(state)
            except Exception:
                _ranges = None
        raw = self._cached_call("event", event_context, sys_p, "", 0.8, 700)
        out = self._postprocess(raw, validate, lambda: _narrative_fallback("event"), ranges=_ranges)
        # C6 修复（人物护栏空转）：validate 命中已故/已黜人物时只写 o["_char_violation"]，
        # 而全库无任何读取方 → narrative_guard 文档所称「命中已故/已黜 → 标记回喂」
        # 从未发生，AI 仍可让亡者出场。现按文档意图**回喂一次**：以订正要求重发；
        # 改好则采用新稿，仍不合则保留原稿（叙事不丢，仅不再重复回喂）。
        if isinstance(out, dict) and out.get("_char_violation"):
            _names = out.pop("_char_violation", []) or []
            _retry_sys = (sys_p + "\n\n【订正要求】上稿叙及已故或已去职之人："
                          + "、".join(str(n) for n in _names)
                          + "。请据实改写，勿使亡者/已黜者出场行事。")
            try:
                _raw2 = self._cached_call("event", event_context, _retry_sys, "",
                                          0.8, 700, input_key="charfix")
                _out2 = self._postprocess(_raw2, validate, lambda: out, ranges=_ranges)
                if isinstance(_out2, dict) and not _out2.get("_char_violation"):
                    return _out2
            except Exception:
                pass
        return out

    def advice(self, posture, faction_hint=""):
        sys_p = _load_prompt("advice", posture=posture, faction_hint=faction_hint)

        def validate(o):
            if not isinstance(o, dict) or "advice" not in o:
                return None
            o["advice"] = _clean_text(o.get("advice", ""))
            return o if o["advice"] else None
        raw = self._call(sys_p, "", temperature=0.9, max_tokens=200)
        return self._postprocess(raw, validate, lambda: _narrative_fallback("advice"))

    def generate_memorials(self, posture, state=None, count=3):
        """每回合开始按当下局势拟 1~count 道奏折（无 AI → 模板兜底，标注 _fallback）。

        返回 {"memorials": [{kind, title, body, name?, effect_dim?, effect_tier?}], ...}。
        kinds：invention/governance/military/personnel/finance。
        只上折不落地——落地由 review_memorial（批准时）决定。
        """
        from ai.narrative_fallback import fallback_memorials
        era_name = str(getattr(state, "era_name", "") or "")
        sys_p = _load_prompt("memorial", posture=posture, era_name=era_name)

        def validate(o):
            if not isinstance(o, dict) or not isinstance(o.get("memorials"), list):
                return None
            out = []
            for m in o["memorials"]:
                if not isinstance(m, dict):
                    continue
                kind = m.get("kind", "")
                if kind not in ("invention", "governance", "military", "personnel", "finance"):
                    continue
                title = _clean_text(str(m.get("title", "")) or "")
                body = _clean_text(str(m.get("body", "")) or "")
                if not title or not body:
                    continue
                rec = {"kind": kind, "title": title, "body": body}
                if kind == "invention":
                    rec["name"] = _clean_text(str(m.get("name", "")) or "") or title
                    rec["effect_dim"] = _clean_text(str(m.get("effect_dim", "")) or "") or "production"
                    tier = _clean_text(str(m.get("effect_tier", "")) or "") or "中"
                    rec["effect_tier"] = tier if tier in ("无", "微", "小", "中", "大") else "中"
                out.append(rec)
            return {"memorials": out[:count]} if out else None

        raw = self._call(sys_p, "", temperature=0.9, max_tokens=700)
        return self._postprocess(raw, validate, lambda: fallback_memorials(state=state, turn=getattr(state, "turn", 0)))

    def final_eval(self, start_year, end_year, posture):
        sys_p = _load_prompt("final_eval", start_year=start_year, end_year=end_year, posture=posture)

        def validate(o):
            if not isinstance(o, dict) or "commentary" not in o:
                return None
            o["commentary"] = _clean_text(o.get("commentary", ""))
            return o if o["commentary"] else None
        raw = self._call(sys_p, "", temperature=0.7, max_tokens=700)
        return self._postprocess(raw, validate, lambda: _ai_unavailable("eval"))
