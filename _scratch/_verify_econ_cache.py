# -*- coding: utf-8 -*-
"""验证：economy_decide 的 _cached_call 缓存导致测试用例串扰（同 posture 多 raw）。"""
import json
import sys
sys.path.insert(0, r"G:\sz\game")

from ai.client import AIClient

client = AIClient.__new__(AIClient)
client.available = True
client._prev_texts = []

raws = iter([
    json.dumps({"景气": "中", "士绅": "抛", "士绅力度": "小", "生产": "中", "窖银": "大"}, ensure_ascii=False),
    json.dumps({"景气": "中", "士绅": "抛", "士绅力度": "小", "生产": "中", "窖银": "倾巢出动"}, ensure_ascii=False),
])
client._call = lambda *a, **k: next(raws)

posture = "国库紧张，粮价高企。"
r1 = client.economy_decide(posture)
r2 = client.economy_decide(posture)   # 同 posture：应校验第二个 raw（窖银非法→无）
print("r1 窖银:", r1["窖银"] if r1 else None)
print("r2 窖银:", r2["窖银"] if r2 else None)
if r2 and r2["窖银"] == "大":
    print("FAIL: 缓存串扰——第二次本应兜底「无」，却命中第一次的「大」")
else:
    print("OK")
