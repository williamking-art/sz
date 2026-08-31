# -*- coding: utf-8 -*-
"""临时验证：召对缓存主题词命中 + AI 结果缓存（tests 目录被并发重构删除，无法 pytest）。"""
import sys
sys.path.insert(0, r"G:\sz\game")

from core.game_state import GameState
from core.commands import _dialogue_cache_hit, _dialogue_stats

# 召对缓存：主题词归一 → 同话题不同措辞命中
s = GameState("史实")
s.dialogue_history.append(("朕", "卿觉得今岁河工如何？"))
s.dialogue_history.append(("蔡京", "臣以为当先固堤防。"))
assert _dialogue_cache_hit(s, "蔡京", "卿觉得今岁河工如何？") == "臣以为当先固堤防。", "首次"
assert _dialogue_cache_hit(s, "蔡京", "今岁河工，卿以为如何？") == "臣以为当先固堤防。", "不同措辞主题词命中"
st = _dialogue_stats(s)
assert st["cache_hits"] >= 2, st
print("召对缓存主题词：OK hits=%d" % st["cache_hits"])

# AI 结果缓存（_cached_call json_mode/input_key）
from ai.client import AIClient
c = AIClient.__new__(AIClient)
c.available = True
n = {"v": 0}


def fake_call(*a, **k):
    n["v"] += 1
    return '{"ok": 1}'


c._call = fake_call
c._postprocess = lambda raw, v, fb, **k: raw
c._cached_call("parse", "朝局A", "sys", "user", 0.3, 900, json_mode=True, input_key="诏A")
c._cached_call("parse", "朝局A", "sys", "user", 0.3, 900, json_mode=True, input_key="诏A")
assert n["v"] == 1, "同输入同朝局应命中缓存 n=%d" % n["v"]
c._cached_call("parse", "朝局A", "sys", "user", 0.3, 900, json_mode=True, input_key="诏B")
assert n["v"] == 2, "不同输入不互撞"
c._cached_call("parse", "朝局B", "sys", "user", 0.3, 900, json_mode=True, input_key="诏A")
assert n["v"] == 3, "不同朝局不互撞"
st2 = c.cache_stats()
assert st2["hits"] == 1 and st2["misses"] == 3, st2
print("AI 结果缓存：OK hits=%d misses=%d" % (st2["hits"], st2["misses"]))
print("ALL OK")
