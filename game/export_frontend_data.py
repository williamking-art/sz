# -*- coding: utf-8 -*-
"""导出前端静态数据 JSON（与 export_constants.py 同规：手工一次性 → 现固化为可复现步骤）。

运行（工作目录为 game/）：python export_frontend_data.py
输出（frontend/src/renderer/data/）：
  codex.json           ← content.codex_data.get_codex_data()（8 类图鉴）
  focus_tree.json      ← core.focus_mechanic.FOCUS_TREE
  ministers_dict.json  ← content.ministers.data.MINISTERS（固定字段投影）

审查背景：这三个文件此前在仓库内**无任何生成脚本**，属人工快照，与 content/ 权威源
之间没有任何同步机制（同类漂移已实际发生：codex.json 少 mechanism/event 两类）。
本脚本把它们纳入可复现流程：改 content/ 后重跑本脚本即可，勿手工编辑产物。

校验建议（防止再次漂移）：在 CI 或提交前跑一次本脚本后执行
`git diff --exit-code frontend/src/renderer/data/`，有差异即说明产物过期。
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

from content.codex_data import get_codex_data                     # noqa: E402
from content.ministers.data import MINISTERS                      # noqa: E402
from core.focus_mechanic import FOCUS_TREE                        # noqa: E402

_OUT = os.path.join(_ROOT, "frontend", "src", "renderer", "data")

# 大臣档案件：前端列表/召对面板所需字段（与既有 ministers_dict.json 一致）
_MINISTER_FIELDS = ("role", "faction", "traits", "nobility", "rank", "in_office")


def _write(name: str, payload) -> None:
    path = os.path.join(_OUT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"[export] {name} ← {len(payload)} 项", file=sys.stderr)


def main() -> None:
    _write("codex.json", get_codex_data())
    _write("focus_tree.json", FOCUS_TREE)
    _write("ministers_dict.json",
           {n: {k: f.get(k) for k in _MINISTER_FIELDS} for n, f in MINISTERS.items()})


if __name__ == "__main__":
    main()
