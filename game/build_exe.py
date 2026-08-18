# -*- coding: utf-8 -*-
"""宋祚 · PyInstaller 目录模式(onedir)打包脚本

用法（在项目根 game/ 下执行）：
    python build_exe.py

产物： game/SongZuo/SongZuo.exe （目录模式，windowed，带图标）
      game/SongZuo/ 内含全部依赖/资源，整体拷贝即可分发。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 目录模式产物直接输出到 game/ 下（distpath=game，内部生成 SongZuo/ 子目录）
OUT_DIR = HERE

# 图标（项目自带）
ICON = os.path.join(HERE, "assets", "icon.ico")

# 需作为数据目录一起打包的内容（游戏运行时需要读取，非纯 Python 代码）
DATA_DIRS = ["assets", "ai", "core", "ui", "backend", "content", "audio"]

# 运行时动态 import 的包（README 提到函数内延迟导入，PyInstaller 无法静态分析）
HIDDEN_IMPORTS = [
    "ai", "ai.client", "ai.decree", "ai.desensitize",
    "core", "core.commands", "core.commands_policy", "core.commands_decree",
    "core.game_state", "core.game_state_econ", "core.save_load", "core.events",
    "core.evaluation", "core.asset_context", "core.settlement", "core.settlement_steps",
    "core.settlement_reform", "core.settlement_extensions",
    "ui", "ui.gui", "ui.map", "ui.theme", "ui.assets",
    "backend", "backend.client",
    "content", "content.data", "content.ministers.data",
    "audio", "audio.player", "audio.manifest",
]

add_data_args = []
for d in DATA_DIRS:
    src = os.path.join(HERE, d)
    if os.path.isdir(src):
        # Windows: --add-data "src;destname"
        add_data_args += ["--add-data", f"{src};{d}"]

hidden_args = []
for m in HIDDEN_IMPORTS:
    hidden_args += ["--hidden-import", m]

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--name", "SongZuo",
    "--onedir",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--icon", ICON,
    "--distpath", OUT_DIR,
    "--workpath", os.path.join(HERE, "build"),
    *add_data_args,
    *hidden_args,
    os.path.join(HERE, "gui_main.py"),
]

print(">>> " + " ".join(cmd))
subprocess.check_call(cmd)
print(f"\n[完成] 产物位于 {os.path.join(OUT_DIR, 'SongZuo', 'SongZuo.exe')}")
print(f"[完成] 运行入口: g:/sz/game/SongZuo/SongZuo.exe")
