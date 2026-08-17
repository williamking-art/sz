# -*- coding: utf-8 -*-
"""一次性拆分 ai/client.py：把类外自由工具函数移到 ai/client_utils.py，主文件 re-export。"""
import os, re
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
src = open("ai/client.py", encoding="utf-8").read()
lines = src.split("\n")

defs = [(i, l) for i, l in enumerate(lines) if re.match(r"^def |^class ", l)]
defs.append((len(lines), ""))

# 类外顶层 def（在 'class AIClient' 之前之后的 def 都算，只要不在 class 缩进内）
class_idx = next(i for i, l in defs if l.startswith("class AIClient"))
utils = []
for k in range(len(defs) - 1):
    s, l = defs[k]
    e = defs[k + 1][0]
    if l.startswith("def "):
        # 仅取 class 之前或 class 之后但顶层（非缩进）的 def；此处所有 def 都是顶层
        name = re.match(r"^def (\w+)", l).group(1)
        utils.append((name, "\n".join(lines[s:e])))

# 拼 utils 模块
util_body = "# -*- coding: utf-8 -*-\n"
util_body += '"""宋祚 · AI 客户端工具函数（拆分自 ai/client.py）"""\n'
util_body += "import os, json, re, hashlib\n"
util_body += "from typing import Any\n\n"
# 复制 utils 函数体
for name, body in utils:
    util_body += body.rstrip() + "\n\n\n"
open("ai/client_utils.py", "w", encoding="utf-8").write(util_body)

# 主文件：删除这些顶层 def 块，改为从 client_utils 导入并 re-export
remove_names = {n for n, _ in utils}
keep = []
i = 0
while i < len(defs) - 1:
    s, l = defs[i]
    e = defs[i + 1][0]
    if l.startswith("def ") and re.match(r"^def (\w+)", l).group(1) in remove_names:
        i += 1
        continue
    keep.extend(lines[s:e])
    i += 1

# 头部：原前 23 行（import 区）保留
head = "\n".join(lines[:23])
head += "\n\nfrom ai.client_utils import (\n"
head += "    " + ", ".join(sorted(remove_names)) + ",\n)\n"
new_src = head + "\n\n" + "\n".join(keep)
open("ai/client.py", "w", encoding="utf-8").write(new_src)
print("utils:", len(utils), "main now:", len(new_src.split(chr(10))))
