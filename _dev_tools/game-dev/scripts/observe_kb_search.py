#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""观测 kb_search 真实调用率。

用法（从仓库根目录执行）：
    python _dev_tools/game-dev/scripts/observe_kb_search.py

逻辑：
1. 读取 game/ai_config.json 创建 AIClient（真实模型）。
2. 新建一局游戏。
3. 向若干大臣抛出需要调用典章知识库的问题，观察 state._kb_stats。
4. 打印每次召对的回复摘要与当前 kb_search 命中/调用计数。
"""

import json
import os
import sys
import textwrap

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GAME_DIR = os.path.join(ROOT, "game")

# 保证 Windows 控制台也能正确输出中文
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, GAME_DIR)

from ai.client import AIClient
from core.commands import new_game, audience_dialogue


def load_config():
    cfg_path = os.path.join(GAME_DIR, "ai_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    cfg = load_config()
    client = AIClient(
        api_key=cfg.get("api_key", ""),
        base_url=cfg.get("base_url", ""),
        model=cfg.get("model", ""),
        enable_tools=cfg.get("enable_tools", "auto"),
    )

    if not client.available:
        print("AI 未配置，无法观测真实调用率。", file=sys.stderr)
        sys.exit(1)

    # 强制开启 tools，避免 auto 探测阶段部分请求未带工具
    client.enable_tools("on")

    state = new_game(difficulty="史实", ai_client=client)

    # 用「如何/利弊/可否/之辩」等讨论词或 >40 字绕过本地预过滤，确保走 AI
    questions = [
        ("富弼", "卿为朕详解三冗之弊，究竟于国计民生有何深远影响，又该如何革除？"),
        ("王安石", "卿且说说交子准备金之法，其于稳定市舶贸易有何利弊，施政时又当注意哪些要点？"),
        ("司马光", "朕闻常平仓可平抑粮价，其运作机理与弊端各在何处，卿可细陈其详？"),
        ("范仲淹", "朕欲整饬吏治，卿以为考课之制当如何与台谏相配合，方能杜渐防微？"),
        ("欧阳修", "馆阁科举之制，历代沿革如何，卿可为朕梳理其源流与得失？"),
    ]

    def kb_stats():
        return getattr(state, "_kb_stats", {"kb_search": {"calls": 0, "hits": 0}})

    print(f"模型: {client.model}")
    print(f"初始 kb_stats: {kb_stats()}")
    print("-" * 60)

    for minister, q in questions:
        try:
            reply = audience_dialogue(state, minister, q, client)
        except Exception as exc:
            reply = f"（调用异常：{exc}）"
        snippet = textwrap.shorten(reply.replace("\n", " "), width=80, placeholder="...")
        print(f"[{minister}] {q}")
        print(f"  -> {snippet}")
        print(f"  -> kb_stats: {kb_stats()}")
        print("-" * 60)

    print("\n汇总:")
    print(f"  kb_stats: {kb_stats()}")
    print(f"  召对统计: {state._dialogue_stats if hasattr(state, '_dialogue_stats') else '无'}")
    print(f"  token 用量: {client.token_usage}")


if __name__ == "__main__":
    main()
