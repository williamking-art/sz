# -*- coding: utf-8 -*-
"""宋祚 · 舆图独立预览启动器（无 Tk、无游戏主程序，复用 ui.map_web 全套服务）。

用法：
    python preview_map.py             # pywebview 窗口优先，缺失降级系统浏览器
    python preview_map.py --browser   # 强制系统浏览器
    python preview_map.py --demo      # 演示分路易主：燕云十六州（南京道/西京道）归宋
    python preview_map.py --port 8907 # 固定服务端口（默认自动分配）
    python preview_map.py --serve     # 只起服务不开浏览器（供 IDE 内置浏览器连接）

浏览器模式下关闭本控制台窗口或按 Ctrl+C 退出；pywebview 模式关窗即退。
"""
from __future__ import annotations

import sys
import time

from ui.map_web import WebMapController

_DEMO_STATE = {
    "hud": {"era": "演示 · 燕云归宋", "year": 1120, "month": 1},
    "sub_owners": {"南京道": "宋", "西京道": "宋"},
}


def main(argv: list[str]) -> int:
    force_browser = "--browser" in argv
    demo = "--demo" in argv
    port = 0
    if "--port" in argv:
        i = argv.index("--port")
        if i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                port = 0
    print("[宋祚] 正在启动舆图服务……")
    ctl = WebMapController(
        title="宋祚 · 舆图预览",
        port=port,
        # pywebview 模式页面加载完成后补推演示状态（浏览器模式靠 /state 轮询兜底）
        on_ready=(lambda info: ctl.push_state(_DEMO_STATE)) if demo else None,
    )
    if demo:
        ctl.push_state(_DEMO_STATE)  # 开局先入状态盒：浏览器首轮轮询即可见
    if "--serve" in argv:
        # 只起服务不开浏览器：前端由外部提供（如 IDE 内置浏览器）
        ctl._start_server()
        print(f"[宋祚] 舆图地址：{ctl.url}（serve-only，不开浏览器）")
        if demo:
            print("[宋祚] 演示：南京道/西京道 → 宋（虚线内界、腹里色），辽其余诸道仍辽")
        print("[宋祚] 关闭本窗口或按 Ctrl+C 退出。")
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        ctl.close()
        return 0
    mode = ctl.open(mode="browser" if force_browser else "auto")
    print(f"[宋祚] 舆图地址：{ctl.url}（模式：{mode}）")
    if demo:
        print("[宋祚] 演示：南京道/西京道 → 宋（虚线内界、腹里色），辽其余诸道仍辽")
    if mode == "browser":
        print("[宋祚] 浏览器模式：关闭本窗口或按 Ctrl+C 退出。")
        try:
            while ctl.is_open():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    else:
        print("[宋祚] pywebview 窗口已关闭。")
    ctl.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
