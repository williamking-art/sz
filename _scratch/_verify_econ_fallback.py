# -*- coding: utf-8 -*-
"""验证 economy_decide 兜底修复：非法档位（含档位字的"超大"）→ 无；合法别名"猛烈"→大。"""
import json
import sys
sys.path.insert(0, r"G:\sz\game")

from ai.client import AIClient

FIN = {"jiaozi_trust": "稳", "shortage": "平", "maritime": "平", "bank": "稳", "price_trend": "平"}

client = AIClient.__new__(AIClient)
client.available = True
client._prev_texts = []
raws = iter([
    json.dumps(dict({"景气": "中", "士绅": "抛", "士绅力度": "小", "生产": "中", "窖银": "超大"}, **FIN), ensure_ascii=False),
    json.dumps(dict({"景气": "中", "士绅": "抛", "士绅力度": "小", "生产": "中", "窖银": "倾巢出动"}, **FIN), ensure_ascii=False),
    json.dumps(dict({"景气": "中", "士绅": "抛", "士绅力度": "小", "生产": "中", "窖银": "猛烈"}, **FIN), ensure_ascii=False),
    json.dumps(dict({"景气": "中", "士绅": "抛", "士绅力度": "小", "生产": "中",
                     "城市化": "蜂拥", "回乡": "返乡潮", "科举": "扩招"}, **FIN), ensure_ascii=False),
    json.dumps(dict({"景气": "中", "士绅": "抛", "士绅力度": "小", "生产": "中"}, **FIN), ensure_ascii=False),
])
client._call = lambda *a, **k: next(raws)

posture = "国库紧张，粮价高企。"
r1 = client.economy_decide(posture)
assert r1["窖银"] == "无", f"含档位字非法词「超大」应兜底无，得 {r1['窖银']}"
r2 = client.economy_decide(posture)
assert r2["窖银"] == "无", f"非法词「倾巢出动」应兜底无，得 {r2['窖银']}"
r3 = client.economy_decide(posture)
assert r3["窖银"] == "大", f"合法别名「猛烈」应归一为大，得 {r3['窖银']}"
r4 = client.economy_decide(posture)
assert r4["城市化"] == "无" and r4["回乡"] == "无" and r4["科举"] == "无", f"非法城市化/回乡/科举应全兜底无：{r4}"
r5 = client.economy_decide(posture)
assert r5["窖银"] == "无" and r5["城市化"] == "无", f"缺失应默认无：{r5}"
print("economy_decide 兜底修复：ALL OK")
