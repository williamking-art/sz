# -*- coding: utf-8 -*-
import base64
import json
import os

BRAIN_DIR = r"C:\Users\william\.gemini\antigravity\brain\21dc1567-8824-46b3-91a5-6021d8db2a9f"
p_master = os.path.join(BRAIN_DIR, "knee_up_cai_jing_master.png")

with open(p_master, "rb") as f:
    b64_master = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")

html_path = os.path.join(BRAIN_DIR, "minister_audience_showcase.html")
with open(html_path, "r", encoding="utf-8") as f:
    text = f.read()

# 在 HTML 的 ASSETS 字典中注入 master_cai_jing
text = text.replace('"cai_jing": "', f'"cai_jing": "{b64_master}", "old_cai_jing": "')

with open(html_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Showcase HTML updated with knee-up master!")
