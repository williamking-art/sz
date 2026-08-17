# -*- coding: utf-8 -*-
"""宋祚 · 音频播放器封装（规划性骨架）

提供非阻塞音频播放的最小接口。资源缺失时静默降级，绝不抛异常崩溃，
也不阻塞 Tkinter mainloop（长音频/背景乐走异步线程）。

注意：当前尚无真实音频资源，play() 在文件不存在时直接 return，
不进行任何第三方库 import，保证零依赖、可安全被 UI 调用。

待回填实勘（落地后由 songzuo-audio-music 技能维护，见其 references/project_benchmarks.md）：
- 选择播放后端（stdlib wave/winsound 或社区库），在此封装；
- 与 ui/effects.py、ui/gui.py 的播放时机接驳点；
- 中文/特殊字符路径在冻结环境 sys._MEIPASS 下的兼容性。
"""
import os
import sys
import threading

__all__ = ["AudioPlayer", "get_player"]

# 资源根目录：与 ui/assets.py 的 _asset_root() 保持一致
def _asset_root():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# 音量权威源：复用 ui_config.json 的 "volume" 键（0-100，默认 60）
# 由 ui/panels_meta.py 的 _misc_get/_misc_set 读写；此处只读，不重复定义。
def _read_volume(default=60):
    try:
        import json
        base = _asset_root()
        p = os.path.join(base, "ui_config.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return float(json.load(f).get("volume", default))
    except Exception:
        pass
    return float(default)


class AudioPlayer:
    """极简非阻塞音频播放器（占位实现）。"""

    def __init__(self, audio_dir="assets/audio"):
        self.audio_dir = audio_dir
        self._lock = threading.Lock()
        self._muted = False

    def _resolve(self, name):
        """将音效名解析为磁盘路径；资源不存在返回 None。"""
        root = _asset_root()
        p = os.path.join(root, self.audio_dir, name)
        return p if os.path.exists(p) else None

    @property
    def volume(self):
        """0.0-1.0，取自 ui_config.json 的 volume 键。"""
        return _read_volume() / 100.0

    def set_muted(self, muted):
        self._muted = bool(muted)

    def play(self, name, loop=False):
        """播放音效 name（如 'event_disaster.ogg'）。资源缺失时静默降级。

        loop 仅作接口预留，当前占位实现忽略。
        """
        if self._muted:
            return
        path = self._resolve(name)
        if path is None:
            # 静默降级：资源尚未生成，不报错、不阻塞
            return
        # TODO(landing): 在此接入真实播放后端（异步线程，避免阻塞 mainloop）
        # 资源落地前不 import 任何音频库，保证零依赖运行。
        return

    def stop(self, name=None):
        """停止播放（接口预留）。"""
        return


_player = None


def get_player():
    """进程内单例，供 UI 延迟获取，避免顶层 import 副作用。"""
    global _player
    if _player is None:
        _player = AudioPlayer()
    return _player
