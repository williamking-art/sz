# -*- coding: utf-8 -*-
"""宋祚 · 音频包（规划性骨架）

本包为《宋祚》宋式音效与音乐设计的落地骨架，目前仅提供接口与资源约定，
不引用任何尚未生成的音频文件——所有加载/播放在资源缺失时静默降级。

纪律（见 README 三层隔离与单一权威源）：
- 音量权威源为 ui_config.json 的 "volume" 键（0-100，默认 60），由 ui/panels_meta.py
  的 _misc_get/_misc_set 读写；本包只读取，不重复定义。
- 资源根目录复用 ui/assets.py 的 _asset_root() 约定（sys._MEIPASS 兼容）。
- 游戏本体不得 import dev/ 或 _scratch/。
"""
