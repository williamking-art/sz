# -*- coding: utf-8 -*-
"""合并 G:\sz\game 与 G:\sz\songzuo。

合并策略（默认）：
- 以 game（新版重构，文件更全）作为冲突文件的胜方；
- 把 game 的全部内容复制合并进 songzuo（保持 CodeBuddy 工作区路径不变）；
- songzuo 独有文件（main.py、ui/terminal.py、ai_config.json、saves 等）保留不动；
- 合并前自动把 songzuo 完整备份到 G:\sz\songzuo_backup_<时间戳>；
- 合并完成后不删除 game，确认无误后由用户手动删除，避免误删。

用法：python merge_songzuo_game.py
"""

import os
import shutil
import sys
import time
from pathlib import Path

BASE = Path(r"G:\sz")
SRC = BASE / "game"
DST = BASE / "songzuo"

# 不复制 Python 缓存目录/文件
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def make_backup_dir() -> Path:
    """生成不冲突的备份目录名。"""
    for i in range(100):
        ts = time.strftime("%Y%m%d_%H%M%S")
        if i:
            ts = f"{ts}_{i}"
        p = BASE / f"songzuo_backup_{ts}"
        if not p.exists():
            return p
    raise SystemExit("无法生成备份目录，请清理 G:\\sz 下的 songzuo_backup_* 后重试。")


def check_dirs() -> None:
    if not SRC.is_dir():
        raise SystemExit(f"源目录不存在：{SRC}")
    if not DST.is_dir():
        raise SystemExit(f"目标目录不存在：{DST}")


def collect_conflicts() -> list:
    """找出 game 中将会覆盖 songzuo 同路径的文件列表。"""
    conflicts = []
    for f in sorted(SRC.rglob("*")):
        if f.is_file():
            rel = f.relative_to(SRC)
            if (DST / rel).exists():
                conflicts.append(str(rel))
    return conflicts


def verify_songzuo_only_files() -> None:
    """校验 songzuo 独有文件在合并后仍然存在。"""
    only_files = [
        "main.py",
        os.path.join("ui", "terminal.py"),
        "ai_config.json",
    ]
    print("\n[3/3] 校验 songzuo 独有文件：")
    missing = []
    for rel in only_files:
        p = DST / rel
        mark = "OK  " if p.exists() else "MISS"
        print(f"  {mark}  {rel}")
        if not p.exists():
            missing.append(rel)
    if missing:
        print("  存在缺失文件，请检查合并结果。")
    else:
        print("  全部保留。")


def main() -> None:
    check_dirs()

    backup = make_backup_dir()
    print("[1/3] 备份 songzuo ...")
    print(f"  {DST} -> {backup}")
    shutil.copytree(DST, backup, ignore=IGNORE)
    print("  备份完成。")

    conflicts = collect_conflicts()
    print(f"\n[2/3] 合并 game -> songzuo（覆盖 {len(conflicts)} 个同名文件）")
    if conflicts:
        print("  将被 game 版本覆盖的文件：")
        for c in conflicts:
            print(f"    - {c}")
    shutil.copytree(SRC, DST, dirs_exist_ok=True, ignore=IGNORE)
    print("  合并完成。")

    verify_songzuo_only_files()

    print("\n" + "=" * 60)
    print(f"合并完成。备份位置：{backup}")
    print("确认运行无误后，可手动删除 G:\\sz\\game。")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # 打印错误，便于双击 .bat 时看到原因
        print(f"\n[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        input("按回车退出...")
        sys.exit(1)
