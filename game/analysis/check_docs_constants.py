# -*- coding: utf-8 -*-
"""文档-常量一致性自检：防 docs/游戏机制说明.md 与 content/data.py 再次漂移。

运行：python analysis/check_docs_constants.py
退出码 0 = 全部一致；1 = 发现漂移（打印差异，供 CI / 复审）。

比对方式：抽取 data.py 中关键常量真实值，与文档「附：关键数值速查」表内
人工维护的（常量名 → 值）做逐项对照；同时校验文档正文出现过、但有硬编码
疑点的数值（如常支、人均月耗粮）。
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from content import data as D  # noqa: E402

DOC_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "游戏机制说明.md")

# 文档"速查表"维护的常量名 → 期望从 data.py 取到的属性名（相同则省略映射）
DOC_TO_ATTR = {
    "END_YEAR": "END_YEAR",
    "PRESTIGE_START": "PRESTIGE_START",
    "TREASURY_START": "TREASURY_START",
    "GRANARY_START": "GRANARY_START",
    "GRANARY_START_CAP": "GRANARY_START_CAP",
    "TREASURY_CRISIS": "TREASURY_CRISIS_LINE",
    "TREASURY_COLLAPSE": "TREASURY_COLLAPSE_LINE",
    "MONTHLY_EXP_CIVIL_BASE": "MONTHLY_EXP_CIVIL_BASE",
    "TAX_COLOR_RATE": "TAX_COLOR_RATE",
    "LAND_TAX_RATE_BENEFIT": "LAND_TAX_RATE_BENEFIT",
    "TAX_POLL_RATIO": "TAX_POLL_RATIO",
    "PER_CAPITA_MONTH_GRAIN": "PER_CAPITA_MONTH_GRAIN",
    "SALT_PROFIT_PER_JIN": "SALT_PROFIT_PER_JIN",
    "SUI_GONG_ANNUAL": "SUI_GONG_ANNUAL",
    "ANNUAL_TAX_BASE": "ANNUAL_TAX_BASE",
    "ARRIVAL_BASE": "ARRIVAL_BASE",
    "TREASURY_CRISIS": "TREASURY_CRISIS_LINE",
    "TREASURY_COLLAPSE": "TREASURY_COLLAPSE_LINE",
}


def _parse_doc_table(path: str) -> dict:
    """抽取文档速查表中「常量 | 值 | 含义」行，返回 {常量名: 值字符串}。

    兼容组合键写法：文档用「GRANARY_START / CAP」「TREASURY_CRISIS / COLLAPSE」
    表示两常量，解析时按别名折叠为独立键。
    """
    alias = {"CAP": "GRANARY_START_CAP", "COLLAPSE": "TREASURY_COLLAPSE"}
    out = {}
    text = open(path, encoding="utf-8").read()
    section = text.split("## 附：关键数值速查")[-1]
    for line in section.splitlines():
        m = re.match(r"\|\s*([A-Za-z_][A-Za-z0-9_ /]*?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", line)
        if not m:
            continue
        names = [n.strip() for n in m.group(1).split("/")]
        value = m.group(2).strip()
        vals = [v.strip() for v in re.split(r"\s*/\s*", value)]
        unit = next((u for u in _UNIT_MULT if u in value), "")
        for i, n in enumerate(names):
            key = alias.get(n, n)
            seg = vals[i] if i < len(vals) else value
            # 该段缺单位但同行有单位（如 "1500" 与 "2000 万石"）→ 补单位
            if unit and not any(u in seg for u in _UNIT_MULT):
                seg = seg + unit
            out[key] = seg
    return out


_UNIT_MULT = {"亿": 1e8, "万": 1e4}


def _norm_number(s: str, inherit_from: str = ""):
    """把 '55万贯/月' '0.5 石' '-500万 / -2000万贯' 解析为可比对的 float（带单位换算）。

    inherit_from：当 s 本身无单位字（如组合键拆出的 "1500"）时，从原整值继承
    "万/亿" 单位。
    """
    m = re.search(r"-?\d+(?:\.\d+)?\s*(?:亿|万)?", s)
    if not m:
        return None
    seg = m.group(0).replace(" ", "")
    num = float(re.match(r"-?\d+(?:\.\d+)?", seg).group(0))
    source = seg + inherit_from
    for unit, mult in _UNIT_MULT.items():
        if unit in source:
            num *= mult
            break
    return num


def main() -> int:
    doc = _parse_doc_table(DOC_PATH)
    problems = []

    for doc_name, attr in DOC_TO_ATTR.items():
        if doc_name not in doc:
            problems.append(f"[缺失] 文档速查表未列 {doc_name}")
            continue
        if not hasattr(D, attr):
            problems.append(f"[缺失] data.py 无常量 {attr}（文档列 {doc_name}）")
            continue
        real = getattr(D, attr)
        doc_val = _norm_number(doc[doc_name], inherit_from=doc[doc_name])
        if doc_val is None:
            problems.append(f"[格式] 文档 {doc_name} 值无法解析：{doc[doc_name]}")
            continue
        if abs(float(real) - doc_val) > 1e-6:
            problems.append(
                f"[漂移] {doc_name}: 文档={doc[doc_name]} | data.py={attr}={real}"
            )

    # 正文硬编码疑点：常支（文档第四章写 55 万贯/月，应等于 MONTHLY_EXP_CIVIL_BASE）
    if hasattr(D, "MONTHLY_EXP_CIVIL_BASE"):
        text = open(DOC_PATH, encoding="utf-8").read()
        if "55 万贯/月" not in text and "55万贯/月" not in text:
            problems.append("[正文] 经济章未出现常支 55 万贯/月（与 MONTHLY_EXP_CIVIL_BASE 不符）")

    if problems:
        print("===== 文档-常量漂移检出 =====")
        for p in problems:
            print(" -", p)
        print(f"\n共 {len(problems)} 处不一致")
        return 1

    print("OK: docs/游戏机制说明.md 与 content/data.py 关键常量一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
