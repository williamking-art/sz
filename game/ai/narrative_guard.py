# -*- coding: utf-8 -*-
"""宋祚 · 叙事-数值一致守卫（三方案落地，言枢密设计已审）。

一、叙事-数值一致：
- `_validate_narrative_numbers(text, ranges)`：正则提取「数字+单位」（万/缗/贯/石/口/户/里/人
  两/斤/匹/顷/亩）→ 数字须落在注入区间（ranges: {单位键: (lo, hi)}）→ 区间外改写为定性词
  （不向玩家泄露伪造数字）；硬锚不变量（清丈≤隐田存量、调粮≤存粮、赈济≤仓廪、兵力增减≤现有兵力）
  由区间上限封顶实现。
  两条**保守兜底**（2026-10-20 全审 R-AI-4）：
  ① 无区间锚的单位（匹/两/斤/顷/亩 —— 无权威换算，宁缺不猜）⇒ 大额（≥1000）标 `flagged`，
     **不改写**（缺锚不得凭猜换算）；
  ② 无单位但带中文量级（万/千/百）且含数字的裸数值（如「增兵三百万」）⇒ 标 `flagged`
     并留 warning（具体数字不做改写：无量纲无法换算，改写反而更假）。
- 叙事类注入只给区间脱敏读数（posture 形态）；结构性推演注入真值快照（内部用，AI 不可见）。

二、来源锚定（取材闭集）：`_build_source_closure` 构建本回合真实来源闭集
（①诏书/在办事务 ②本回合事件 ③记忆图谱检索闭集 ④本回合 settlement log），
注入【本期取材（仅限以下来源）】+ 硬约束「禁止引用闭集外剧情」。

三、防错校验表：`build_character_statuses`（{人物: {alive, in_office, current_post,
faction, status}}）；`_validate_characters` 叙事具名人物查表，命中已故/已黜 → 标记回喂。
"""
import re
import logging

log = logging.getLogger("ai.narrative_guard")

# 数字+单位正则（支持「300万石」= 300×万×石；审查 P2-42 修复：原只匹配阿拉伯数字，
# 「三百万石」等中文数字表述全部绕过数值区间校验 —— 现同时匹配中文数字，由 _cn_to_int 解析）
# 2026-10-20（R-AI-4）：单位表补 两/斤/匹/顷/亩 —— 原表漏这些单位，导致「三千匹/五千两」
# 整句放行（探针 flagged=False），守卫形同只认钱粮。
_NUM_RE = re.compile(r"(\d+|[零一二两三四五六七八九十百千万]+)(万)?(贯|石|口|户|缗|里|人|两|斤|匹|顷|亩)")

_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def _cn_to_int(text: str) -> int:
    """中文数字 → 整数（支持 十/百/千/万 组合，如「三百万」「一百二十」）；无法解析返回 0。"""
    total, section, num = 0, 0, 0
    for ch in text:
        if ch in _CN_DIGITS:
            num = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            section += (num or 1) * _CN_UNITS[ch]
            num = 0
        elif ch == "万":
            section = (section + num) * 10000
            total += section
            section, num = 0, 0
        else:
            return 0
    return total + section + num

# 单位 → 定性词档位（区间内按位置）
_UNIT_QUALIFIERS = {
    "贯": ("寥寥", "可观", "充盈"), "缗": ("寥寥", "可观", "充盈"),
    "石": ("杯水车薪", "可观", "浩大"), "口": ("寥寥", "颇众", "浩繁"),
    "户": ("寥寥", "颇众", "浩繁"), "里": ("咫尺", "百里", "千里"),
    "人": ("寥寥", "颇众", "浩繁"),
    # 2026-10-20（R-AI-4）：补单位定性词（供调用方自带这些单位的区间时改写用）
    "两": ("寥寥", "可观", "充盈"), "斤": ("杯水车薪", "可观", "浩大"),
    "匹": ("寥寥", "可观", "浩繁"), "顷": ("区区", "可观", "连阡"),
    "亩": ("区区", "可观", "连阡"),
}

#: 全部已识别单位字符（裸数字后紧跟这些字符 ⇒ 已由 `_NUM_RE` 处理，不重复计入裸量级）
_UNIT_CHARS = "贯石口户缗里人两斤匹顷亩"

#: 无区间锚的单位：**大额**（≥此值）标 flagged（缺锚不猜换算，也不改写）
_UNVERIFIABLE_MIN = 1000

#: 裸数值（无单位）匹配：用于识别「增兵三百万」这类**无单位但带量级**的伪造面
_BARE_NUM_RE = re.compile(r"(\d+|[零一二两三四五六七八九十百千万]+)")
_MAG_CHARS = ("万", "千", "百")


def _flag_bare_magnitudes(text):
    """找出**无单位**但带中文量级（万/千/百）且含数字的裸数值。

    返回命中的 token 列表（供 flagged/审计）。排除「万岁/百官/千万不可」这类
    **无数字的固定词**：要求 token 内含数字字符（阿拉伯数字或中文数字）。
    """
    hits = []
    if not text:
        return hits
    for m in _BARE_NUM_RE.finditer(text):
        tok = m.group(1)
        nxt = text[m.end():m.end() + 1]
        if nxt and nxt in _UNIT_CHARS:
            continue                      # 带单位：交给 _NUM_RE 那一遍判定
        if not any(c in _MAG_CHARS for c in tok):
            continue
        if not any(c.isascii() and c.isdigit() or c in _CN_DIGITS for c in tok):
            continue
        hits.append(tok)
    return hits


def _validate_narrative_numbers(text, ranges=None):
    """AI 叙事数字+单位校验：数字须落在注入区间；区间外改写为定性词。

    返回 (new_text, flagged)。无 ranges 时跳过（仅原样返回）。
    硬锚不变量：ranges 键的上限即硬锚（清丈≤隐田/调粮≤存粮/赈济≤仓廪/兵力≤现有）。
    flagged 语义（2026-10-20）：**出现无法与账本核对的数值表述**即为 True——
      · 有区间且越界（已改写为定性词）；
      · 无区间锚的单位且金额/数量 ≥ `_UNVERIFIABLE_MIN`（不改写，留痕）；
      · 无单位裸量级（万/千/百，见 `_flag_bare_magnitudes`，不改写，留痕）。
    """
    if not text or not ranges:
        return (text or ""), False
    flagged = False

    def _repl(m):
        nonlocal flagged
        _tok = m.group(1)
        _base = int(_tok) if _tok.isdigit() else _cn_to_int(_tok)
        num = _base * (10000 if m.group(2) else 1)
        unit = m.group(3)
        key = unit
        if key in ranges:
            lo, hi = ranges[key]
            if not (lo <= num <= hi):
                flagged = True
                q = _UNIT_QUALIFIERS.get(unit, ("寡", "中", "众"))
                ratio = (num - lo) / max(1, (hi - lo))
                return q[0] if ratio < 0.4 else q[1] if ratio < 0.8 else q[2]
            return m.group(0)
        # 无锚单位：不能与账本核对 → 大额即标 flagged（**不改写**：无权威换算，猜就是造假）
        if num >= _UNVERIFIABLE_MIN:
            flagged = True
            log.warning("[叙事] 无法核验的数量表述（无区间锚）：%s%s", m.group(0), unit)
        return m.group(0)

    out = _NUM_RE.sub(_repl, text)
    _bare = _flag_bare_magnitudes(out)
    if _bare:
        flagged = True
        log.warning("[叙事] 无单位量级数值（无法核对，已标 flagged）：%s", _bare[:5])
    return out, flagged


def _build_numeric_ranges(state):
    """注入区间（叙事类只给区间脱敏读数；硬锚上限封顶）：
    贯=国库量级（×1.5 浮动）、石=太仓存量（硬锚：赈济/调粮≤仓廪）、
    口=人口、户=户数、里=疆域、人=兵额（兵力增减≤现有兵力）。"""
    treasury = int(getattr(state, "treasury", 0))
    granary = int(getattr(state, "granary", 0))
    population = int(getattr(state, "population", 0))
    from content.data_constants import PERSONS_PER_HOUSEHOLD
    households = int(getattr(state, "households", 0)) or population // PERSONS_PER_HOUSEHOLD
    army = sum(u.troops for u in getattr(state, "army_units", []))
    return {
        "贯": (0, max(1, int(treasury * 1.5))),
        "缗": (0, max(1, int(treasury * 1.5))),
        "石": (0, max(1, granary)),          # 硬锚：调粮/赈济 ≤ 存粮/仓廪
        "口": (0, max(1, population)),
        "户": (0, max(1, households)),
        "里": (0, 6000),
        "人": (0, max(1, army * 2)),          # 兵力增减 ≤ 现有兵额（×2 允许表述浮动）
    }


def _build_source_closure(state, extra=None):
    """本回合真实来源闭集：①诏书/在办事务/国策 ②本回合事件 ③记忆图谱检索闭集 ④本回合 log
    ⑤**真实工程/事务状态**（规格任务 5）。
    返回注入文本【本期取材（仅限以下来源）】。"""
    parts = []
    # ① 诏书/在办事务/国策推进
    for d in list(getattr(state, "pending_decrees", []) or [])[-5:]:
        parts.append(f"诏·{d.get('title', '')[:12]}")
    for t in list(getattr(state, "longterm_public", []) or [])[-5:]:
        parts.append(f"务·{t.get('title', '')[:12]}")
    act_focus = getattr(state, "active_focus", None)
    if act_focus and isinstance(act_focus, dict) and act_focus.get("status") == "in_progress":
        parts.append(f"策·推行{act_focus.get('name', '')}")
    for cf in list(getattr(state, "completed_focuses", []) or [])[-3:]:
        parts.append(f"策·既成{cf.get('name', '')}")
    # ② 本回合事件
    for e in list(getattr(state, "active_events", []) or [])[-5:]:
        parts.append(f"事·{e.get('category', '')[:12]}")
    # ③ 记忆图谱检索闭集（近期决策/事件）
    try:
        rows = state.memory.query("decision", time_window=12, top_k=5)
        for r in rows[:3]:
            ent = state.memory.entities.get(r[1], {})
            parts.append(f"史·{ent.get('name', '')[:12]}")
    except Exception:
        pass
    # ④ 本回合 settlement log
    for line in list(getattr(state, "last_settlement_log", []) or [])[-8:]:
        parts.append(f"报·{str(line)[:20]}")
    # ⑤ 真实工程/事务状态（规格任务 5）：让 AI 看到**实际**进度与产出，
    #    而不是凭上下文猜"应该盖好了"。读数与面板同源（core/plan_readout.py）。
    try:
        from core.plan_readout import build_plan_readout, render_briefing_text
        _rt = render_briefing_text(build_plan_readout(state))
        if _rt:
            parts.append(_rt)
    except Exception:  # noqa: BLE001 — 读数失败不得阻断注入（也不编造）
        log.warning("[叙事] 工程读数注入失败（跳过该段，不编造）", exc_info=True)
    if extra:
        parts.extend(extra)
    closure = "；".join(parts) if parts else "（本期无重大事项）"
    return ("【本期取材（仅限以下来源）】" + closure +
            "\n硬约束：叙事仅可引用上述来源，**禁止引用闭集外剧情/数字/人物**；"
            "**未告成的工程不得说成完工，无程序侧落点的事务不得说成已生效**。")


# ------------------------------------------------------------
# 完成宣称核对（规格任务 5：叙事宣称须与真实 state 一致）
# ------------------------------------------------------------
#: 「已完工/已生效」类宣称的触发词
_COMPLETION_WORDS = ("告成", "竣工", "落成", "已完工", "建成", "完工", "已生效",
                     "施行完毕", "大功告成")
#: 可能**不实**的否定语境（"未完工""尚未落成"这类是在说实话，不该被改写）
_NEGATION_PREFIX = ("未", "尚未", "未能", "没有", "还没", "不曾", "难以", "无法")


def _validate_completion_claims(text, readout):
    """核对"完工/生效"类宣称是否与**真实状态**相符；不符则改写为如实表述。

    返回 `(new_text, flagged)`。`flagged` 为被改写的宣称列表（供审计/面板）。
    无 readout 时原样返回（不猜、不误伤）。
    """
    if not text or not isinstance(readout, dict):
        return text, []
    rows = readout.get("projects") or []
    unsupported = readout.get("unsupported_tasks") or []
    # 真实已成（可称告成）的名字集合
    done_names = {str(p.get("name") or "") for p in rows
                  if p.get("status") in ("operating", "degraded")}
    flagged = []
    new = text
    for w in _COMPLETION_WORDS:
        idx = 0
        while True:
            i = new.find(w, idx)
            if i < 0:
                break
            # 否定语境（"未完工"）是如实表述，跳过
            head = new[max(0, i - 3):i]
            if any(head.endswith(p) for p in _NEGATION_PREFIX):
                idx = i + len(w)
                continue
            # 该宣称附近是否点到某个**真实已成**的工程名？点到就算属实
            seg = new[max(0, i - 24):i + len(w) + 8]
            if any(n and n in seg for n in done_names):
                idx = i + len(w)
                continue
            # 不实：若附近点了某个仍在办/拟议的工程名 → 改为如实表述；否则泛化
            fixing = next((str(p.get("name") or "") for p in rows
                           if p.get("name") and str(p["name"]) in seg
                           and p.get("status") not in ("operating", "degraded")), "")
            if fixing:
                # 工程名若**已在紧邻前缀**（12 字窗口）里出现过，就只补"尚未告成"，
                # 否则会拼成"乙工程亦乙工程尚未告成"（重复工程名）。
                near = new[max(0, i - 12):i]
                repl = "尚未告成" if fixing in near else f"{fixing}尚未告成"
            elif unsupported:
                repl = "此事尚待落实"
            else:
                repl = "工程尚在进行"
            flagged.append({"word": w, "at": i, "replaced": repl,
                            "context": seg.strip()[:40]})
            new = new[:i] + repl + new[i + len(w):]
            idx = i + len(repl)
    return new, flagged


def build_character_statuses(state):
    """每回合人物状态校验表：{人物: {alive, in_office, current_post, faction, status}}。

    **未知即 `unknown`，不得回落 `active`**（审查 P2-3）：先前 `minister_status`
    异常时 `st="active"`，会把已死/贬谪而查不出的角色当成**在场**写进叙事
    （`in_office=True` 进「在朝具名人物」名单，`_validate_characters` 也不再拦），
    属"把未知当在场"的伪造。现逐项留 warning，未知落 `unknown`（保守：不算在场，
    也进不了"已故"名单，避免误伤名单本身）。
    """
    from content.ministers.data import MINISTERS
    out = {}
    _warned = {"status": False, "post": False}   # 每表一次：防"某接口整体坏掉"时刷屏
    for name in MINISTERS:
        fig = MINISTERS[name]
        # 审查 P3 修复：就地 try 保护（原依赖调用方外层 try，新调用方漏包即崩）
        try:
            st = state.minister_status(name)
        except Exception:
            if not _warned["status"]:
                log.warning("角色状态读取失败，按 unknown 处理（首个：%s）", name, exc_info=True)
                _warned["status"] = True
            st = "unknown"
        if not st:
            if not _warned["status"]:
                log.warning("角色状态为空值，按 unknown 处理（首个：%s）", name)
                _warned["status"] = True
            st = "unknown"
        post = ""
        try:
            post = state.ministers.get(name, {}).get("post", "") or fig.get("role", "")
        except Exception:
            if not _warned["post"]:
                log.warning("角色现任官职读取失败，回落档案职衔（首个：%s）", name, exc_info=True)
                _warned["post"] = True
            post = fig.get("role", "")
        out[name] = {
            "alive": st != "dead",
            "in_office": st == "active",
            "current_post": post,
            "faction": fig.get("faction", ""),
            "status": st,
        }
    return out


def build_character_blacklist(statuses):
    """黑名单注入：本朝已故/已黜名单 + 在朝具名人物名单（省 token 模式）。"""
    dead = [n for n, s in statuses.items() if not s["alive"]]
    out = [n for n, s in statuses.items() if s["in_office"]]
    return ("【本朝已故/已黜：】" + ("、".join(dead) if dead else "（无）") +
            "\n【在朝具名人物：】" + ("、".join(out[:40]) if out else "（无）"))


_CHAR_RE = re.compile(r"[\u4e00-\u9fa5]{2,4}(?:[相郎]|公|卿|监|使)?")


def _validate_characters(text, statuses):
    """叙事具名人物查表：命中已故/已黜（status != active）→ 标记（回喂修正）。
    返回 (是否命中违规, 违规名单)。"""
    if not text or not statuses:
        return False, []
    bad = []
    for name, st in statuses.items():
        if st["status"] == "active":
            continue
        if name in text:
            bad.append(f"{name}({st['status']})")
    return bool(bad), bad


