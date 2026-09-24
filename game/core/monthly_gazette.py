# -*- coding: utf-8 -*-
"""宋祚 · 月度奏章八章（批 3 · 明末经验搬运）。

依据《改进方案_合并版》A2 与《明末经验》§2.2：
  每回合固定八章 + 章末七言联 + ▲▼ 差值摘要，把「看不见的数值变化」翻译成可读叙事。

八章：`诏书核销 / 指令核销 / 长期局势 / 密令动向 / 讣闻登场 / 人物历练 / 军事 / 邦交`。
必补三章（明末实测缺口）：① 局势进展逐条 ② 人物历练/属性涨跌 ③ 密令动向。

纪律：
- **不伪造数字**：只引用 `settlement_log` / `short_term_log` / `state.situations` 等程序真值；
- **不写状态**：本模块只读组装，产物写 `state.monthly_gazette` 由调用方落账；
- 空章保留标题 + 「本月无事」，保证章节完整率 100%（验收硬指标）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["CHAPTER_ORDER", "build_monthly_gazette", "GAZETTE_COUPLETS"]

# 八章固定顺序（明末 §2.2 对齐；标题即 UI 章名）
CHAPTER_ORDER: tuple = (
    "诏书核销",
    "指令核销",
    "长期局势",
    "密令动向",
    "讣闻登场",
    "人物历练",
    "军事",
    "邦交",
)

# 章末七言联模板池（确定性轮换；AI 可后续润色，程序版先落）
GAZETTE_COUPLETS: tuple = (
    "四海升平民乐业，九州贡赋入王畿。",
    "诏下九重风动野，春回万户谷盈仓。",
    "边烽暂息农桑稳，朝议初成简牍新。",
    "太仓粟米因时实，御路衣冠逐岁更。",
    "疏陈玉陛灯花落，事了金鸡晓漏残。",
)

# 结算日志关键词 → 章（按行分类；一行只进第一章命中）
_CHAPTER_KEYWORDS: Dict[str, tuple] = {
    "诏书核销": ("诏", "敕", "颁", "拟旨", "朱批", "下诏", "降诏"),
    "指令核销": ("长期", "政务", "核销", "完结", "变法", "在办"),
    "密令动向": ("密旨", "密令", "密折", "暗中", "泄露"),
    "军事": ("军", "兵", "饷", "戍", "边", "防", "战", "剿", "城防"),
    "邦交": ("辽", "夏", "金", "大理", "岁币", "岁赐", "邦交", "外邦", "朝贡", "和议"),
    "讣闻登场": ("讣", "薨", "卒", "故", "贬", "黜", "擢", "迁", "拜", "除", "致仕"),
}


def _couplet(year: int, month: int) -> str:
    """确定性轮换七言联（同月同联，跨进程可复现）。"""
    import zlib
    idx = zlib.crc32(f"{year}:{month}".encode()) % len(GAZETTE_COUPLETS)
    return GAZETTE_COUPLETS[idx]


def _fmt_delta(v: Optional[float], unit: str = "") -> str:
    """▲▼ 差值摘要片段；无变化返回空串。"""
    if v is None:
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    if abs(n) < 0.5:
        return ""
    arrow = "▲" if n > 0 else "▼"
    return f"{arrow}{abs(n):,.0f}{unit}"


def _chapter_situations(state) -> List[str]:
    """长期局势章：逐条 bar 进度 + 状态 + 成败语义（批 2 成果直出）。"""
    lines: List[str] = []
    for rec in (getattr(state, "situations", None) or []):
        if not isinstance(rec, dict):
            continue
        title = str(rec.get("title") or "局势")
        status = str(rec.get("status") or "active")
        bar = rec.get("bar_value")
        status_cn = {"active": "在办", "resolved": "已解",
                     "failed": "已败", "cancelled": "已罢"}.get(status, status)
        if bar is not None:
            good = rec.get("bar_good_meaning") or "渐平"
            bad = rec.get("bar_bad_meaning") or "恶化"
            lines.append(f"「{title}」{status_cn}，进度 {int(bar)}/100"
                         f"（推进则{good}，恶化则{bad}）")
        else:
            lines.append(f"「{title}」{status_cn}（无进度条）")
        # 本月 timeline 尾条（若有）
        tl = rec.get("timeline") or []
        if isinstance(tl, list) and tl:
            last = tl[-1]
            if isinstance(last, dict) and last.get("text"):
                lines.append(f"　└ {str(last['text'])[:80]}")
    return lines or ["本月无长期局势变动。"]


def _chapter_secret(state) -> List[str]:
    """密令动向章：待发 / 在办 / 本月泄露（程序真值）。"""
    lines: List[str] = []
    for d in (getattr(state, "pending_secret_decrees", None) or []):
        if isinstance(d, dict):
            lines.append(f"待发密令：「{d.get('title') or d.get('content', '密令')[:20]}」")
    for d in (getattr(state, "longterm_secret", None) or []):
        if isinstance(d, dict):
            prog = d.get("progress")
            tail = f"（进度 {prog}）" if prog is not None else ""
            lines.append(f"在办密令：「{d.get('title') or '密令'}」{tail}")
    # 本月结算日志里的密旨行（泄露/推行）
    for line in _last_month_lines(state):
        if any(k in line for k in ("密旨", "密令", "泄露")):
            lines.append(line[:100])
    return lines or ["本月无密令动向。"]


def _chapter_life(state) -> List[str]:
    """人物历练章：召对/擢贬/致仕 等人事变动（short_term_log + 结算日志）。"""
    lines: List[str] = []
    for e in (getattr(state, "short_term_log", None) or []):
        if not isinstance(e, dict):
            continue
        kind = str(e.get("kind") or "")
        title = str(e.get("title") or "")
        note = str(e.get("note") or "")
        if kind in ("personnel", "minister", "audience") or any(
                k in title + note for k in ("擢", "贬", "黜", "拜", "除", "致仕", "召对", "进谏")):
            lines.append(f"{title} —— {note}" if note else title)
    for line in _last_month_lines(state):
        if any(k in line for k in ("擢", "贬", "黜", "拜", "除", "致仕", "考成", "历练", "进秩")):
            if line not in lines:
                lines.append(line[:100])
    return lines or ["本月无人事进退可记。"]


def _chapter_by_keywords(state, chapter: str) -> List[str]:
    """按关键词把本月结算行归入指定章。"""
    kws = _CHAPTER_KEYWORDS.get(chapter, ())
    lines = []
    for line in _last_month_lines(state):
        if any(k in line for k in kws):
            lines.append(line[:120])
    return lines


def _last_month_lines(state) -> List[str]:
    """最近一月结算日志行（list[str]；旧档兼容 dict/str）。"""
    logs = getattr(state, "settlement_log", None) or []
    if not logs:
        return []
    last = logs[-1]
    if isinstance(last, list):
        return [str(x) for x in last]
    if isinstance(last, dict):
        return [str(last.get("text") or last.get("line") or last)]
    return [str(last)]


def _diff_summary(state) -> List[str]:
    """▲▼ 差值摘要：本月关键指标环比（读 state 派生，不伪造）。"""
    bits: List[str] = []
    for label, key, unit in (
        ("国库", "treasury", "贯"),
        ("民心", "population_satisfaction", ""),
        ("皇威", "prestige", ""),
        ("太仓", "granary", "石"),
    ):
        cur = getattr(state, key, None)
        # 与上月邸报比（若有）；否则跳过
        prev = None
        hist = getattr(state, "monthly_gazette", None) or []
        if hist and isinstance(hist[-1], dict):
            prev = (hist[-1].get("diff_raw") or {}).get(key)
        if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
            seg = _fmt_delta(float(cur) - float(prev), unit)
            if seg:
                bits.append(f"{label} {seg}")
        # 记录本期原始值供下月比对
        if isinstance(cur, (int, float)):
            if not isinstance(getattr(state, "_gazette_diff_raw", None), dict):
                state._gazette_diff_raw = {}
            state._gazette_diff_raw[key] = float(cur)
    return bits


def build_monthly_gazette(state, year: Optional[int] = None,
                          month: Optional[int] = None) -> Dict[str, Any]:
    """组装当月八章奏章（只读；返回 dict 供调用方写入 `state.monthly_gazette`）。

    返回结构：
    ```
    {
      "year": int, "month": int,
      "chapters": [{"title": "诏书核销", "lines": [...]}, ... 8 章],
      "couplet": "七言联",
      "diff_summary": ["国库 ▲…", ...],
      "diff_raw": {treasury, population_satisfaction, prestige, granary},
    }
    ```
    """
    y = int(year if year is not None else getattr(state, "year", 0) or 0)
    m = int(month if month is not None else getattr(state, "month", 1) or 1)

    chapters: List[Dict[str, Any]] = []
    for name in CHAPTER_ORDER:
        if name == "长期局势":
            lines = _chapter_situations(state)
        elif name == "密令动向":
            lines = _chapter_secret(state)
        elif name == "人物历练":
            lines = _chapter_life(state)
        elif name == "讣闻登场":
            lines = _chapter_by_keywords(state, name) or ["本月无讣闻、无新擢。"]
        else:
            lines = _chapter_by_keywords(state, name) or [f"本月无{name}可记。"]
        chapters.append({"title": name, "lines": lines})

    diff = _diff_summary(state)
    return {
        "year": y,
        "month": m,
        "chapters": chapters,
        "couplet": _couplet(y, m),
        "diff_summary": diff,
        "diff_raw": dict(getattr(state, "_gazette_diff_raw", None) or {}),
    }
