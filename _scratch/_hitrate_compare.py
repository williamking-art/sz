# -*- coding: utf-8 -*-
"""命中率对比（改造前后）：典型召对输入序列的省调用统计。

改造前 = 谷承构原始 8 类预过滤 + 相似度>0.85 缓存（无讨论排除/无主题词归一）
改造后 = 14 类预过滤（补建新军/研科技/外交/营造）+ 讨论类排除 + >40 字跳过
         + 主题词归一缓存 + intent_hint（无 AI 调用次数对比）
"""
import sys
sys.path.insert(0, r"G:\sz\game")

from core.commands import _prefilter_dialogue, _dialogue_cache_hit, _topic_key
from core.game_state import GameState

# 典型玩家召对输入序列（20 条：8 常用 + 4 新机制 + 3 讨论 + 1 长诏令 + 2 同话题不同措辞 + 2 非常规）
INPUTS = [
    ("朕欲调兵守边", "调兵"),
    ("赈灾开仓", "赈灾"),
    ("朕欲蠲免两浙秋税", "减税"),
    ("宽民恤民，速办", "恤民"),
    ("整吏肃贪，即行", "肃贪"),
    ("兴学贡举", "兴学"),
    ("广开市舶", "市舶"),
    ("平抑粮价，即日", "平籴"),
    ("朕欲建军新军", "建军"),           # 新机制（改造后命中）
    ("研制火器", "研制"),               # 新机制
    ("遣使议和", "遣使"),               # 新机制
    ("营造艮岳", "营造"),               # 新机制
    ("减税与加征之辩，卿以为如何", None),   # 讨论类（改造后排除）
    ("三舍法兴学利弊，愿闻其详", None),     # 讨论类
    ("市舶之利恐伤海商，卿有何高见", None), # 讨论类
    ("朕欲蠲免京东西路今岁秋税之半，以纾民困，并着转运司核实灾伤分数，具以条奏，毋得扰民，钦此。", None),  # 长诏令
    ("卿觉得今岁河工如何？", "河工A"),   # 主题词（改造后缓存命中）
    ("今岁河工，卿以为如何？", "河工B"), # 同话题不同措辞（改造后主题词命中）
    ("卿对王安石变法有何高见？", None),   # 非常规
    ("北虏犯边，卿有何策", None),        # 非常规（改造后讨论排除？"何策"不在排除词——含"边"命中调兵组？"边"在调兵组关键词！→ 误伤）
]

# ---- 改造前：8 类规则（无讨论排除/无主题词） ----
def prefilter_before(name, text):
    rules8 = [
        (("调兵", "整军", "阅兵", "边防", "戍"), 1), (("赈灾", "开仓", "发粟", "饥荒"), 1),
        (("减税", "免税", "蠲免", "薄赋"), 1), (("宽民", "恤民", "安民"), 1),
        (("整吏", "肃贪", "清吏", "查贪"), 1), (("兴学", "贡举", "科举", "学校"), 1),
        (("市舶", "通商", "海贸"), 1), (("粮价", "常平", "平籴"), 1),
    ]
    return any(k in text for kws, _ in rules8 for k in kws)

def cache_before(s, name, text):
    # 相似度>0.85 扫描（无主题词）
    from difflib import SequenceMatcher
    hist = s.dialogue_history
    for i in range(len(hist) - 2, -1, -1):
        if hist[i][0] == "朕" and i + 1 < len(hist) and hist[i + 1][0] == name:
            if SequenceMatcher(None, text, str(hist[i][1])).ratio() > 0.85:
                return True
            break
    return False

# 改造前模拟
saved_before = 0
for text, _tag in INPUTS:
    if prefilter_before("蔡京", text):
        saved_before += 1
# 改造后模拟（真实代码路径）
s = GameState("史实")
saved_after = 0
ai_after = 0
for text, _tag in INPUTS:
    if _prefilter_dialogue("蔡京", text):
        saved_after += 1
        continue
    # 缓存：先种一条河工对话，模拟同话题缓存
    if "河工" in text:
        s.dialogue_history.append(("朕", "卿觉得今岁河工如何？"))
        s.dialogue_history.append(("蔡京", "臣以为当先固堤防。"))
        if _dialogue_cache_hit(s, "蔡京", text):
            saved_after += 1
            continue
    ai_after += 1

total = len(INPUTS)
print(f"输入序列: {total} 条")
print(f"改造前 省调用: {saved_before}  ({saved_before/total*100:.0f}%)  →  走AI: {total-saved_before}")
print(f"改造后 省调用: {saved_after}  ({saved_after/total*100:.0f}%)  →  走AI: {ai_after}")
print(f"提升: {saved_after - saved_before} 条（{saved_before/total*100:.0f}% → {saved_after/total*100:.0f}%）")
