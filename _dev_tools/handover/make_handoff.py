# -*- coding: utf-8 -*-
"""生成 `_dev_tools/handover/HANDOFF.md` —— **四件事一页**（只链接，不复制正文）。

借鉴 <https://github.com/jidekaixin2dian/handoff>：宁可**一个当前入口 + 按任务链接**，
也不要把实现史抄进多个文件。本脚本**只读**交接层与 git，产出聚合页：
1. **当前状态**：各 agent phase · 最近提交 · 上一轮门禁结论
2. **下一步**：未完成任务（`tasks/*.json` 中 `status` 非 done）
3. **关键约束 / 待人决定**：`decisions/*.json` 中 `status` 含「待裁定/待设计」
4. **证据入口**：`DECISIONS-INDEX.md` · `INDEX.md` · 各 agent 的 `_scratch` 日志约定 · 提交 hash

用法：`python _dev_tools/handover/make_handoff.py`（幂等覆盖 `HANDOFF.md`）。
⚠️ 本脚本**不写** tasks/decisions/phase，只在交接目录里写这一个聚合页。
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:                                   # noqa: BLE001
        return {"_invalid": str(e)[:60]}


def _git(args):
    try:
        out = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", timeout=20)
        return (out.stdout or "").strip()
    except Exception:                                        # noqa: BLE001
        return ""


def main() -> int:
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines += ["# HANDOFF · 当前入口（自动生成，勿手改）", "",
              f"> 生成时间：**{now}** · 生成器：`_dev_tools/handover/make_handoff.py`"
              "（只读交接层与 git；**只链接，不复制正文**）。",
              "> 权威仍是各 `tasks/`、`decisions/`、`phase/`、`specs/` 与代码本身。", ""]

    # 1) 当前状态
    lines += ["## 1. 当前状态（哪个版本有效 · 哪些结果已验证）", ""]
    ph = sorted(glob.glob(os.path.join(BASE, "phase", "*.json")))
    if ph:
        lines += ["| agent | phase（节选） | 更新 |", "|---|---|---|"]
        for p in ph:
            d = _load(p)
            if d.get("_invalid"):
                lines.append(f"| `{os.path.basename(p)}` | ⚠️ JSON 非法：{d['_invalid']} | - |")
                continue
            phase = str(d.get("phase") or "-")
            phase = (phase[:160] + "…") if len(phase) > 160 else phase
            lines.append(f"| {os.path.basename(p)} | {phase} | {d.get('updatedAt') or '-'} |")
    else:
        lines.append("（无 `phase/*.json`）")
    lines += ["", "最近提交：", "", "```", _git(["log", "--oneline", "-5"]) or "(不可读)", "```", ""]

    # 2) 下一步
    lines += ["## 2. 下一步（什么尚未完成）", ""]
    open_tasks = []
    for t in sorted(glob.glob(os.path.join(BASE, "tasks", "*.json"))):
        d = _load(t)
        st = str(d.get("status") or "").lower()
        if st in ("done", "completed", "landed"):
            continue
        open_tasks.append((os.path.basename(t), st or "?", str(d.get("title") or "")[:80],
                           str(d.get("claimedBy") or "-")))
    if open_tasks:
        lines += ["| 任务 | status | 标题 | claimedBy |", "|---|---|---|---|"]
        for n, st, ti, by in open_tasks:
            lines.append(f"| `{n}` | {st} | {ti} | {by} |")
    else:
        lines.append("（`tasks/` 中无未完成项）")
    lines += ["", f"> 已完成任务共 **{len(glob.glob(os.path.join(BASE, 'tasks', '*.json'))) - len(open_tasks)}** 条，"
                  "见 `INDEX.md`（看板）。", ""]

    # 3) 待人决定
    lines += ["## 3. 关键约束 / **待人决定**", ""]
    pend = []
    for p in sorted(glob.glob(os.path.join(BASE, "decisions", "*.json"))):
        d = _load(p)
        st = str(d.get("status") or "")
        if any(k in st for k in ("待裁定", "待设计", "pending")):
            pend.append((os.path.basename(p), st, str(d.get("title") or d.get("question") or "")[:80]))
    if pend:
        lines += ["| 决策档 | status | 主题 |", "|---|---|---|"]
        for n, st, ti in pend:
            lines.append(f"| `{n}` | {st} | {ti} |")
    else:
        lines.append("（无待裁项）")
    lines += ["", "> 硬约束：仓库根 `AGENTS.md` §3（POP 挂载律 / 口径单点 / **缺失≠0** / 不新增平行账本 / "
                  "保留他人未提交改动）。", ""]

    # 4) 证据入口
    lines += ["## 4. 证据入口（按任务链到权威文件，细节按需展开）", "",
              "| 要什么 | 去哪儿 |", "|---|---|",
              "| 看板 / 全部任务状态 | `INDEX.md`（`handover.py summary` 重建） |",
              "| **所有 Jev 裁定与概率** | `DECISIONS-INDEX.md` |",
              "| **待拍板的决策（一页简报）** | `_dev_tools/game-docs/specs/cross-cutting/待裁清单_*.md` |",
              "| **接手指南 / 收口总表** | `_dev_tools/game-docs/specs/economy/unified-civilian-market/{接手指南,收口总表}_*.md` |",
              "| 逐批实测数字与门禁结论 | `worklog/`（追加式，一条一文件） |",
              "| 全量回归原始输出 | `_scratch/full_regression_*.log`（各 agent 约定） |",
              "| 规范与设计 | `_dev_tools/game-docs/specs/**`（含 `接手指南_*.md`） |",
              "| 提交与哈希 | `git log`（`claim finish --commit <hash>` 亦记录） |",
              "",
              "### P6 长局哨兵（60/240 月 · 固定种子）", "",
              "```powershell",
              "& $py -m pytest _dev_tools/game-dev/tests/test_m162_long_run_sentinel.py -q -p no:cacheprovider   # 12 月（默认档）",
              '$env:SONGZUO_LONG_RUN="1";   & $py -m pytest _dev_tools/game-dev/tests/test_m162_long_run_sentinel.py -q   # 60 月（约 46s）',
              '$env:SONGZUO_LONG_RUN="240"; & $py -m pytest _dev_tools/game-dev/tests/test_m162_long_run_sentinel.py -q   # 240 月（约 184s）',
              "```",
              "锁定四项：**无异常** · 货币恒等式残差 **0** · POP 守恒违规 **0** · 读数契约违规 **0**"
              "（60/240 月实测均通过）。", "",
              "### 提交前门禁（每次提交不可省）", "",
              "```powershell",
              "& $py _dev_tools/handover.py check",
              "git diff --cached --check                                   # 尾随空白/冲突标记 ⇒ 非 0 阻止提交",
              "& $py -m pytest _dev_tools/game-dev/tests/test_readme_sync.py -q -p no:cacheprovider",
              "& $py -m pytest _dev_tools/game-dev/tests -q -p no:cacheprovider > $env:TEMP\\full.log 2>&1",
              '"FULL EXIT=$LASTEXITCODE"                                   # 🔴 只看退出码',
              "```", ""]
    lines += ["### 三条护栏（违反即交接失效）", "",
              "1. **不得混淆验证层级**：「离线检查通过」≠「人工已接受」；「全量回归 EXIT=0」≠「功能已被验收」。",
              "2. **授权不继承**：旧交接里的发布/实施计划不得当作新一轮授权；改数值/改 state/对外发布须当轮取得确认。",
              "3. **保留边界**：原始数据、冻结评估、哈希、独有决策、**他人未提交改动**一律保留；"
              "**无明确清理请求不删文件**；「还能重新下载」不是删除理由。", ""]

    out = os.path.join(BASE, "HANDOFF.md")
    # 🔴 **必须以单个换行结尾**（多余空行会被 `git diff --cached --check` 判为 new blank line at EOF ⇒ 阻止提交）
    text = "\n".join(lines).rstrip("\n") + "\n"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("写出 HANDOFF.md：", len(lines), "行 ｜ 未完成任务", len(open_tasks), "｜ 待裁", len(pend))
    return 0


if __name__ == "__main__":
    sys.exit(main())
