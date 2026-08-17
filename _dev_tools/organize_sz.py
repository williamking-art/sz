# -*- coding: utf-8 -*-
"""整理 G:\sz 目录。

目标结构：
    G:\sz\
    ├── game\                  # 前端（游戏本体）
    ├── songzuo_server\        # 后端（Rust 服务）
    └── _dev_tools\            # 其他开发用文件

运行后，根目录下除 game、songzuo_server、_dev_tools 以及本脚本自身之外，
其余文件/目录都会移动到 _dev_tools 中。
"""

import shutil
import sys
import time
from pathlib import Path

BASE = Path(r"G:\sz")
DEV = BASE / "_dev_tools"

# 根目录保留名单
KEEP = {
    "game",
    "songzuo_server",
    "_dev_tools",
    "organize_sz.py",
    "整理sz文件夹.bat",
    "desktop.ini",  # Windows 系统文件，不移动
}


def unique_target(target: Path) -> Path:
    """若目标已存在，自动加 _1/_2 后缀，避免覆盖。"""
    if not target.exists():
        return target
    for i in range(1, 100):
        p = target.with_name(f"{target.stem}_{i}{target.suffix}")
        if not p.exists():
            return p
    raise SystemExit(f"无法为目标 {target.name} 生成可用文件名，请先清理 _dev_tools。")


def main() -> None:
    DEV.mkdir(exist_ok=True)

    moved = []
    for item in sorted(BASE.iterdir(), key=lambda p: p.name):
        if item.name in KEEP:
            continue
        target = unique_target(DEV / item.name)
        shutil.move(str(item), str(target))
        moved.append(f"{item.name}  ->  _dev_tools\\{target.name}")

    print("已完成 G:\\sz 整理。\n")
    if moved:
        print("以下文件已移入 _dev_tools：")
        for line in moved:
            print("  " + line)
    else:
        print("根目录没有需要移动的文件。")
    print("\n保留目录：")
    print("  - game（前端）")
    print("  - songzuo_server（后端）")
    print("  - _dev_tools（开发用文件）")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        input("按回车退出...")
        sys.exit(1)
