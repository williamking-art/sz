# -*- coding: utf-8 -*-
"""一次性拆分 core/commands.py：按功能拆为 decree / policy / turn 子模块，主文件 re-export。"""
import os, re
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
src = open("core/commands.py", encoding="utf-8").read()
lines = src.split("\n")

# 顶层 def 边界
defs = [(i, l) for i, l in enumerate(lines) if re.match(r"^def ", l)]
defs.append((len(lines), ""))  # 末尾哨兵

# 归类
decree_fns = {
    "issue_decree", "issue_secret_decree", "_generate_decree_effects",
    "_random_faction_stances", "issue_free_decree", "_enqueue", "_run_fixed",
    "_apply_rename", "_draft_to_effects_dict", "issue_edict_from_review",
    "reject_edict_draft", "issue_kouyu", "merge_drafts", "_rule_draft",
    "preview_draft", "issue_drafted_decree", "confirm_timeline_break",
    "dismiss_pending_break",
}
policy_fns = {
    "govern_yamen", "local_policy", "_state_summary_min", "finance_policy",
    "granary_policy", "exam_policy", "science_policy", "military_expand",
    "diplomacy_policy", "reform_policy", "start_project", "start_workshop",
}
# turn/audience/event/save 等留在主文件：new_game, audience_minister, do_personal_action,
# choose_major_policy, advance_month, _next_month, settle_turn, resolve_event,
# save, load, save_slots, conclude, audience_dialogue

# 提取每个 def 的文本块
blocks = {}
for k in range(len(defs) - 1):
    s, _ = defs[k]
    e = defs[k + 1][0]
    name = re.match(r"^def (\w+)", lines[s]).group(1)
    blocks[name] = "\n".join(lines[s:e])

HEADER = (
    "# -*- coding: utf-8 -*-\n"
    '"""宋祚 · 诏令/密旨/拟旨/会签 指令族（拆分自 core/commands.py）"""\n'
    "from typing import Any\n"
    "from core.game_state import GameState\n"
    "from core.settlement import run_monthly_settlement, settle_reform, _apply_decree_effect\n"
    "from content.data import (\n"
    "    ZHONGZHI_AFFILIATION_RATE, CENTRAL_ORG_INFO, AUTHORITY_MATTERS,\n"
    "    REFORM_TYPES, PREFECTURE_LIST, PRESTIGURE_INFO if False else PREFECTURE_LIST,\n"
    ")\n"
    "from content.ministers import MINISTERS, loyalty_init\n\n\n"
)
# 修正上面拼写错误
HEADER = (
    "# -*- coding: utf-8 -*-\n"
    '"""宋祚 · 诏令/密旨/拟旨/会签 指令族（拆分自 core/commands.py）"""\n'
    "from typing import Any\n"
    "from core.game_state import GameState\n"
    "from core.settlement import run_monthly_settlement, settle_reform, _apply_decree_effect\n"
    "from content.data import (\n"
    "    ZHONGZHI_AFFILIATION_RATE,\n"
    ")\n"
    "from content.ministers import MINISTERS, loyalty_init\n\n\n"
)

def write_module(fname, fns, extra_header=""):
    body = extra_header
    for fn in fns:
        if fn in blocks:
            body += blocks[fn].rstrip() + "\n\n\n"
    open(fname, "w", encoding="utf-8").write(body)
    return body

# decree 子模块
dec_body = HEADER
for fn in decree_fns:
    if fn in blocks:
        dec_body += blocks[fn].rstrip() + "\n\n\n"
open("core/commands_decree.py", "w", encoding="utf-8").write(dec_body)

# policy 子模块（需更多 data 导入，先写占位头，再补 import）
pol_header = (
    "# -*- coding: utf-8 -*-\n"
    '"""宋祚 · 各项施政 policy 指令族（拆分自 core/commands.py）"""\n'
    "from typing import Any\n"
    "from core.game_state import GameState\n"
    "from core.settlement import run_monthly_settlement\n\n\n"
)
pol_body = pol_header
for fn in policy_fns:
    if fn in blocks:
        pol_body += blocks[fn].rstrip() + "\n\n\n"
open("core/commands_policy.py", "w", encoding="utf-8").write(pol_body)

# 主文件：删除被移走的函数块，改为 import + re-export
remove_names = decree_fns | policy_fns
keep = []
i = 0
while i < len(defs) - 1:
    s, _ = defs[i]
    e = defs[i + 1][0]
    name = re.match(r"^def (\w+)", lines[s]).group(1)
    if name in remove_names:
        i += 1
        continue
    keep.extend(lines[s:e])
    i += 1

# 主文件头：原文件前 25 行（import 区）保留，再追加子模块 import
head = "\n".join(lines[:25])
head += "\n\nfrom core.commands_decree import (\n"
head += "    " + ", ".join(sorted(decree_fns & set(blocks))) + ",\n)\n"
head += "from core.commands_policy import (\n"
head += "    " + ", ".join(sorted(policy_fns & set(blocks))) + ",\n)\n"
new_src = head + "\n\n" + "\n".join(keep)
open("core/commands.py", "w", encoding="utf-8").write(new_src)
print("done. main lines:", len(new_src.split(chr(10))),
      "decree:", len(dec_body.split(chr(10))), "policy:", len(pol_body.split(chr(10))))
