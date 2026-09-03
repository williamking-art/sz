# -*- coding: utf-8 -*-
"""宋祚 · Web 舆图独立启动器（开发 / 验收用）

不依赖 tkinter 主程序，单独拉起 MapLibre 舆图：
    python map_web_main.py            # 优先 pywebview 窗口，缺失降级浏览器
    python map_web_main.py --browser  # 强制系统浏览器（HTTP 桥 + 轮询通道）
    python map_web_main.py --demo     # 就绪后下发演示状态（金崛起/选中/标注）

桥接事件打印到控制台，便于验收 JS↔Python 双向通道。
"""
import argparse
import sys

from ui.map_web import WebMapController, webview_available


def main() -> int:
    ap = argparse.ArgumentParser(description="宋祚 · Web 舆图独立启动器")
    ap.add_argument("--browser", action="store_true", help="强制使用系统浏览器")
    ap.add_argument("--demo", action="store_true", help="就绪后下发演示状态")
    ap.add_argument("--width", type=int, default=1180)
    ap.add_argument("--height", type=int, default=780)
    args = ap.parse_args()

    def on_feature(kind, name, props, lnglat):
        pos = ""
        if lnglat and lnglat[0] is not None and lnglat[1] is not None:
            pos = f"  @({lnglat[0]:.2f},{lnglat[1]:.2f})"
        print(f"[点击] {kind} · {name}{pos}  {props}")

    def on_ready(info):
        print(f"[就绪] {info}")

    def on_closed():
        print("[关闭] 舆图窗口已退出")

    ctl = WebMapController(
        root=None, on_feature=on_feature, on_ready=on_ready, on_closed=on_closed,
        width=args.width, height=args.height)

    if args.demo:
        def push_demo(_info):
            ctl.set_hud(era="建中靖国", year=1101, month=1, season="春")
            ctl.set_active_regimes(["金"])          # 演示：金崛起
            ctl.set_markers([
                {"lng": 114.31, "lat": 34.80, "label": "行在", "kind": "seal"},
                {"lng": 103.5, "lat": 36.0, "label": "边警", "kind": "warn"},
            ])
            ctl.select("city", "开封府")
        ctl._on_ready = push_demo  # noqa: SLF001 - 启动器内替换就绪回调

    mode = ctl.open(mode="browser" if args.browser else "auto")
    print(f"[模式] {mode}（pywebview 可用：{webview_available()}）")
    print(f"[地址] {ctl.url}")
    if not ctl.wait_ready(timeout=10):
        print("[警告] 10s 内未收到 map_ready，请查看日志：")
        for line in ctl.recent_logs(20):
            print("   ", line)

    if mode == "browser":
        # 浏览器模式 open() 立即返回，需驻留进程伺服 HTTP 桥
        print("[提示] 浏览器模式：回车退出。")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass
        ctl.close()
    else:
        # pywebview 模式：open() 已在当前线程阻塞至窗口关闭
        ctl.close()
    print("[退出] 再见")
    return 0


if __name__ == "__main__":
    sys.exit(main())
