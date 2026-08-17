#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宋祚游戏制造组 · Team 模式一键加载脚本

解析 agents/ 下的专家角色卡（含 frontmatter），生成可供主理人（邹运筹）
在 Team 模式下一键加载的团队配置与启动剧本。

用法：
    python scripts/load_team.py                 # 打印团队概览 + 启动剧本
    python scripts/load_team.py --json          # 输出团队配置 JSON 到 stdout
    python scripts/load_team.py --json -o team.json
    python scripts/load_team.py --member strategy-systems   # 打印某成员摘要
    python scripts/load_team.py --task "新增河患赈济系统"     # 生成任务路由卡草稿

约定（见 agents/songzuo-game-studio-team-lead.md）：
    - Agent 工具的 name 与 subagent_type 均传成员 ID（即 .md 文件名去扩展名）
    - 主理人先 TeamCreate，再 spawn 成员；成员互不直连，经主理人中转
    - 禁止用中文名或自创名作为 subagent_type
"""

import argparse
import json
import os
import re
import sys

# agents 目录相对本脚本：songzuo-game-studio/scripts/../agents
AGENTS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "agents"))
TEAM_NAME = "songzuo-game-studio"
LEAD_MARK = "team-lead"  # 文件名含此标记者为主理人

# frontmatter 字段
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
FIELD_RE = re.compile(r'^(\w[\w-]*):\s*(.*)$', re.MULTILINE)


def parse_frontmatter(text):
    """解析 md 文件顶部的 YAML frontmatter。

    支持两种形态：
      - 单行标量：  key: value
      - 嵌套块：    key:            （下一行缩进的 en:/zh: 子键）
    对 displayName / profession 额外提取 zh 子键。
    """
    m = FM_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    fields = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        fm = FIELD_RE.match(line)
        if fm and not line.startswith((" ", "\t")):
            key, val = fm.group(1), fm.group(2).strip()
            # 块状（值为空，下一行缩进）：收集子键
            if val == "":
                sub = {}
                j = i + 1
                while j < len(lines) and (lines[j].startswith((" ", "\t"))):
                    sm = FIELD_RE.match(lines[j].strip())
                    if sm:
                        sv = sm.group(2).strip().strip('"').strip("'")
                        sub[sm.group(1)] = sv
                    j += 1
                fields[key] = sub
                i = j
                continue
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            fields[key] = val
        i += 1
    # 兜底：直接抓 displayName/profession 下的 zh 子键
    for parent in ("displayName", "profession"):
        if isinstance(fields.get(parent), dict) and "zh" not in fields[parent]:
            mm = re.search(rf'^\s*{parent}:\s*\n(?:\s+\w+:\s*".*"\s*\n)*?\s+zh:\s*"(.+?)"',
                           block, re.MULTILINE)
            if mm:
                fields[parent]["zh"] = mm.group(1)
    return fields


def load_members():
    """扫描 agents/ 目录，返回 (lead, members) 列表。"""
    if not os.path.isdir(AGENTS_DIR):
        sys.exit(f"[错误] 找不到 agents 目录：{AGENTS_DIR}")
    lead = None
    members = []
    for fn in sorted(os.listdir(AGENTS_DIR)):
        if not fn.endswith(".md") or fn == "INDEX.md":
            continue
        path = os.path.join(AGENTS_DIR, fn)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        fm = parse_frontmatter(text)
        agent_id = fm.get("name") or os.path.splitext(fn)[0]
        rec = {
            "agent_id": agent_id,            # 即 subagent_type
            "file": fn,
            "name": fm.get("name", ""),
            "description": fm.get("description", ""),
            "profession_zh": (fm.get("profession", {}).get("zh")
                              if isinstance(fm.get("profession"), dict)
                              else fm.get("profession", "")),
            "display_zh": (fm.get("displayName", {}).get("zh")
                           if isinstance(fm.get("displayName"), dict)
                           else fm.get("displayName", "")),
            "maxTurns": fm.get("maxTurns", ""),
        }
        # 修正嵌套 dict（YAML 简单解析可能留字典）
        if isinstance(fm.get("profession"), dict):
            rec["profession_zh"] = fm["profession"].get("zh", "")
            rec["profession_en"] = fm["profession"].get("en", "")
        if isinstance(fm.get("displayName"), dict):
            rec["display_zh"] = fm["displayName"].get("zh", "")
            rec["display_en"] = fm["displayName"].get("en", "")
        if LEAD_MARK in fn or LEAD_MARK in agent_id:
            lead = rec
        else:
            members.append(rec)
    if lead is None:
        sys.exit("[错误] 未找到主理人文件（文件名/name 应含 'team-lead'）")
    return lead, members


def print_overview(lead, members):
    print(f"== 宋祚游戏制造组（Team: {TEAM_NAME}）==")
    print(f"主理人 : {lead['display_zh']} ({lead['agent_id']})  maxTurns={lead['maxTurns']}")
    print(f"成员数 : {len(members)}")
    print("-" * 60)
    for i, m in enumerate(members, 1):
        print(f"  {i:02d}. {m['display_zh']:<6} {m['agent_id']:<28} "
              f"maxTurns={m['maxTurns']}")
    print("-" * 60)


def print_playbook(lead, members):
    """打印主理人 Team 模式标准启动剧本。"""
    member_ids = "\n".join(f"      - {m['agent_id']}  ({m['display_zh']})" for m in members)
    print(f"""
== 主理人启动剧本（Team 模式）==

1. 读取 agents/INDEX.md 与包根 TEAM.md 第一部分（总提示词 / DoD）。
2. TeamCreate(name="{TEAM_NAME}") 建立团队。
3. 按任务路由 spawn 所需最少成员（name 与 subagent_type 均传 agent_id）：

      Agent(name=<agent_id>, subagent_type=<agent_id>,
            team_name="{TEAM_NAME}",
            prompt=<任务卡 + 对应角色卡摘要 + 工程约束>)

   可用成员：
{member_ids}

4. 成员产出经 SendMessage 回传主理人；主理人中转，成员互不直连。
5. 跨模块功能：主责出唯一方案 → 复核成员回传约束 → 主理人汇总。
6. 验证阶段 spawn regression-qa；发布 spawn release-engineering。
7. 主理人按 TEAM.md 第七部分 DoD 逐项验收并交付综合报告。
""")


def build_config(lead, members):
    return {
        "team_name": TEAM_NAME,
        "lead": lead,
        "members": members,
        "agents_dir": AGENTS_DIR,
    }


def guess_owners(task, members):
    """根据任务关键词粗略猜测主责成员（仅辅助，最终由主理人裁决）。"""
    kw = {
        "event": ["song-narrative-designer", "ai-pipeline"],
        "叙事": ["song-narrative-designer", "ai-pipeline"],
        "史实": ["song-narrative-designer"],
        "数值": ["strategy-systems", "data-analytics"],
        "平衡": ["strategy-systems", "data-analytics"],
        "结算": ["core-engineering", "strategy-systems"],
        "存档": ["core-engineering"],
        "状态": ["core-engineering"],
        "prompt": ["ai-pipeline"],
        "ai": ["ai-pipeline"],
        "界面": ["tkinter-ui"],
        "ui": ["tkinter-ui"],
        "美术": ["art-assets"],
        "资源": ["art-assets"],
        "立绘": ["art-assets"],
        "音": ["sound-music-designer"],
        "乐": ["sound-music-designer"],
        "测试": ["regression-qa"],
        "回归": ["regression-qa"],
        "打包": ["release-engineering"],
        "exe": ["release-engineering"],
        "发布": ["release-engineering"],
        "遥测": ["data-analytics"],
        "模拟": ["data-analytics"],
    }
    hits = []
    low = task.lower()
    for k, ids in kw.items():
        if k.lower() in low:
            hits.extend(ids)
    # 去重保序
    seen, uniq = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h); uniq.append(h)
    by_id = {m["agent_id"]: m for m in members}
    return [by_id[h] for h in uniq if h in by_id]


def main():
    ap = argparse.ArgumentParser(description="宋祚专家团 Team 模式加载脚本")
    ap.add_argument("--json", action="store_true", help="输出团队配置 JSON")
    ap.add_argument("-o", "--output", help="将 JSON 写入指定文件")
    ap.add_argument("--member", help="打印指定 agent_id 的成员摘要")
    ap.add_argument("--task", help="根据任务描述生成路由卡草稿")
    args = ap.parse_args()

    lead, members = load_members()

    if args.member:
        rec = next((m for m in members if m["agent_id"] == args.member), None)
        if not rec:
            rec = lead if lead["agent_id"] == args.member else None
        if not rec:
            sys.exit(f"[错误] 未找到成员：{args.member}")
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return

    if args.task:
        owners = guess_owners(args.task, members)
        print(f"== 任务路由卡草稿：{args.task} ==")
        print(f"建议主责（待主理人裁决）：")
        for o in owners:
            print(f"  - {o['display_zh']} ({o['agent_id']})：{o['description'][:40]}...")
        if not owners:
            print("  （无关键词命中，建议直接交主理人 songzuo-game-studio-team-lead 路由）")
        print("\n完整路由请由主理人按 TEAM.md 第五部分调度规则执行。")
        return

    if args.json:
        cfg = build_config(lead, members)
        out = json.dumps(cfg, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out)
            print(f"已写入：{args.output}")
        else:
            print(out)
        return

    # 默认：概览 + 剧本
    print_overview(lead, members)
    print_playbook(lead, members)


if __name__ == "__main__":
    main()
