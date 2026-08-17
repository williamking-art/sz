# -*- coding: utf-8 -*-
"""数值进度条 · 共享单一权威实现。

原先不同界面各维护一份逻辑相同的 `_bar`，易随三档阈值/字符调整漂移。
此处收敛为单一权威源，各界面委托调用。
"""


def bar(value, width: int = 10) -> str:
    """生成数值进度条：三档填充字符（█/▓/▒）+ 空位 ░，阈值 70/40。"""
    v = max(0, min(width, int(value * width / 100)))
    if value >= 70:
        return "█" * v + "░" * (width - v)
    elif value >= 40:
        return "▓" * v + "░" * (width - v)
    return "▒" * v + "░" * (width - v)
