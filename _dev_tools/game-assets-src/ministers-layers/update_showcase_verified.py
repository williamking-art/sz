# -*- coding: utf-8 -*-
import base64
import os
import re

brain_dir = r"C:\Users\william\.gemini\antigravity\brain\21dc1567-8824-46b3-91a5-6021d8db2a9f"
p_master = os.path.join(brain_dir, "breakthrough_perfect_fit_810.png")

with open(p_master, "rb") as f:
    b64_master = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")

html_path = os.path.join(brain_dir, "minister_audience_showcase.html")
with open(html_path, "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(r'"cai_jing":\s*"[^"]+"', f'"cai_jing": "{b64_master}"', text)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Updated showcase HTML with verified breakthrough image!")
