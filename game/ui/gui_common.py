# -*- coding: utf-8 -*-
"""宋祚 · GUI 共享常量与纯工具函数（供 gui.py 及其职责域 Mixin 复用）。

从原 ui/gui.py 抽出，避免「常量 + 共享辅助函数」在拆分后的多文件间重复维护，
同时防止 gui.py 与各 panels_*.py 之间产生循环 import。
"""
# ── （宣纸朱红风）──
PAPER = "#f6ecd6"        # 主背景（宣纸）
PAPER2 = "#efe2c4"       # 次级背景
CARD = "#fffaf0"         # 卡片底（米白宣纸）
INK = "#2b1d12"          # 正文深褐
DIM = "#8a6b40"          # 次要文字（赭黄）
RED = "#8a2b22"          # 朱红（主色）
RED_D = "#6f201a"        # 深朱红（渐变/描边）
GOLD = "#caa24a"         # 描金
GREEN = "#5a7a3c"        # 吉（绿）
BORDER = "#d8c08a"       # 卡片描边
SEAL_BG = "#7a1f1f"      # 印章红

# 字体（Windows 优先楷体/雅黑）
KAI = "KaiTi"
SANS = "Microsoft YaHei"

DECREE_CATEGORIES = ["财政", "军事", "人事", "民生", "外交"]
LOCAL_ACTS = ["劝农", "赈灾", "平盗", "减税"]


def _bar(value, width=10):
    """委托共享实现 ui.bars.bar（消除双份维护）。"""
    from ui.bars import bar as _bar
    return _bar(value, width)


def _format_effects(effects):
    """委托共享实现 ui.effects.format_effects（消除双份维护）。"""
    from ui.effects import format_effects as _fe
    return _fe(effects)


def _judge_effects(effects):
    """统计选项 effects 里增益/减益条目数（用于朱批色高亮）。"""
    from ui.effects import iter_faction_change
    good = bad = 0
    for k, v in (effects or {}).items():
        if k == "faction_change":
            for _fn, fd in iter_faction_change(effects):
                if fd >= 0:
                    good += 1
                else:
                    bad += 1
        else:
            if v > 0:
                good += 1
            elif v < 0:
                bad += 1
    return good, bad
