# -*- coding: utf-8 -*-
"""宋祚 · 国库/内帑收支悬浮栏数据（纯派生，只读 GameState）

口径（不伪造、标注来源）：
- 常项（月度科目）：
  · 国库收入 = tax_breakdown（工商税/役钱/市舶税，结算 Step4 权威分项）；
  · 国库收支总结 = 本月 [财政] 日志（货币月入/科目/月支/结余或亏空）；
  · 内帑收入 = 酒课（wine_tax）+ 国库净结余抽成（calc_imperial_treasury，按本月净结余）；
- 一次性收支：从本月结算日志提取带金额的关键条目（皇帝行止/岁币/征发军资/铸钱/交子/
  田赋折银/内帑等），按行内「内帑」字样归内帑、其余归国库；
- 累计：statistics.total_income / total_expenditure。

仅供 UI 展示；不写状态、不改数值。
"""
import re

__all__ = ["build_flow_summary"]

_FINANCE_LOG_RE = re.compile(
    r"\[财政\] 货币月入 ([\d.]+)贯（(.*?)） 支 ([\d.]+)贯"
    r"(?: 亏空 ([\d.]+)贯| 结余 ([\d.]+)贯)?")

# 一次性条目提取：日志行模式 → 标签（匹配首处金额）
_ONE_OFF_PATTERNS = [
    (re.compile(r"\[皇帝\].*?([+-]?\d[\d,]*)\s*贯"), "皇帝行止"),
    (re.compile(r"\[岁币\].*?(\d[\d,]*)\s*贯"), "岁币"),
    (re.compile(r"\[枢密\].*?(\d[\d,]*)\s*贯"), "征发军资"),
    (re.compile(r"\[铸钱\].*?(\d[\d,]*)\s*贯"), "铸钱"),
    (re.compile(r"\[交子\].*?(\d[\d,]*)\s*贯"), "交子"),
    (re.compile(r"\[田赋·一条鞭\].*?(\d[\d,]*)\s*贯"), "田赋折银"),
    (re.compile(r"\[内帑\].*?(\d[\d,]*)\s*贯"), "内帑"),
    (re.compile(r"\[自由动作\].*?(\d[\d,]*)\s*贯"), "自由制度"),
]


def _this_month_log(state):
    logs = getattr(state, "settlement_log", None) or []
    return logs[-1] if logs else []


def _parse_finance_line(state):
    """从本月 [财政] 日志解析 (月入, 科目文字, 月支, 净结余|None)。"""
    for line in reversed(_this_month_log(state)):
        m = _FINANCE_LOG_RE.search(str(line))
        if m:
            net = None
            if m.group(4) is not None:
                net = -float(m.group(4))      # 亏空
            elif m.group(5) is not None:
                net = float(m.group(5))       # 结余
            return float(m.group(1)), m.group(2), float(m.group(3)), net
    return None, "", None, None


def _extract_one_off(state, max_items=6):
    """从本月日志提取一次性收支条目：[(标签, 金额, 归属treasury/imperial), ...]。"""
    items = []
    for line in _this_month_log(state):
        text = str(line)
        for pat, label in _ONE_OFF_PATTERNS:
            m = pat.search(text)
            if not m:
                continue
            try:
                val = int(m.group(1).replace(",", ""))
            except ValueError:
                continue
            fund = "imperial" if "内帑" in text else "treasury"
            items.append((label, val, fund))
            break
        if len(items) >= max_items:
            break
    return items


def build_flow_summary(state) -> dict:
    """国库/内帑收支悬浮栏数据（纯派生，不写 state）。

    返回：
      treasury: {regular_in: [(科目, 额)], month_in, month_out, inc_parts,
                 one_off: [(标签, 额, 归属)], total_in, total_out}
      imperial: {regular_in: [(酒课, 额), (抽成, 额)], one_off: [...],
                 balance}
    """
    tb = getattr(state, "tax_breakdown", None) or {}
    stat = getattr(state, "statistics", None) or {}

    # —— 国库常项（月度税入分项）——
    regular_in = []
    for lab, key in (("工商税", "commerce"), ("役钱", "poll"), ("市舶税", "maritime")):
        v = int(tb.get(key, 0) or 0)
        if v:
            regular_in.append((lab, v))

    month_in, inc_parts, month_out, net = _parse_finance_line(state)
    if month_in is None:
        month_in = sum(v for _l, v in regular_in)
        month_out = 0

    # —— 内帑常项（酒课 + 抽成）——
    wine = int(getattr(state, "wine_tax", 0) or 0)
    share = 0
    if net is not None:
        try:
            share = int(state.calc_imperial_treasury(net)[0])
        except Exception:
            share = 0
    imperial_in = [("酒课", wine)]
    if share:
        imperial_in.append(("抽成", share))

    one_off = _extract_one_off(state)
    return {
        "treasury": {
            "regular_in": regular_in,
            "month_in": int(month_in),
            "month_out": int(month_out),
            "inc_parts": inc_parts or "（税入分项）",
            "one_off": one_off,
            "total_in": int(stat.get("total_income", 0) or 0),
            "total_out": int(stat.get("total_expenditure", 0) or 0),
        },
        "imperial": {
            "regular_in": imperial_in,
            "one_off": [it for it in one_off if it[2] == "imperial"],
            "balance": int(getattr(state, "imperial_treasury", 0) or 0),
        },
    }
