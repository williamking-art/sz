# -*- coding: utf-8 -*-
"""宋祚 · 大臣语音朗读（B1：edge-tts 可选层，非阻塞）

职责：把大臣台词合成为语音文件（带缓存），供 GUI 异步播放。
- 合成走 edge-tts（微软在线服务，LGPL-3.0，pip 包动态调用）；
- **非阻塞纪律**：synthesize_async 在守护线程执行，回调结果由调用方
  经 widget.after() 回主线程——绝不阻塞 mainloop（景呈宣席位红线）；
- **降级纪律**：edge-tts 未安装 / 离线 / 合成失败 → 返回 None 并带原因，
  上层静默跳过（与"缺资源静默降级"原则一致），绝不阻塞或报错打断游戏；
- 缓存：assets/audio/tts_cache/<md5(text|voice)>.mp3，同文本零重复合成；
- 音色：按大臣名确定性映射（同人同声），预设 5 个中文音色。

播放：play_file 用 winsound（Windows 标准库，SND_ASYNC 非阻塞）；
其他平台返回 False，由未来 audio/player.py 统一接管。
"""
from __future__ import annotations

import hashlib
import os
import sys
import threading

__all__ = ["TTSEngine", "tts_engine", "play_file", "VOICE_PRESETS"]

# 中文音色预设（edge-tts 官方音色名；按人物气质选用）
VOICE_PRESETS = {
    "young_official": "zh-CN-YunxiNeural",    # 少年清朗（年轻官员/宦官）
    "elder_minister": "zh-CN-YunyangNeural",  # 沉稳庄重（宰执/老臣）
    "general": "zh-CN-YunjianNeural",         # 刚毅浑厚（武将）
    "female_court": "zh-CN-XiaoxiaoNeural",   # 清亮女声（女官/后妃）
    "narrator": "zh-CN-YunyeNeural",          # 旁白/史官
}

_DEFAULT_CACHE = os.path.join("assets", "audio", "tts_cache")


def _cache_dir() -> str:
    """缓存目录（frozen 时用 exe 所在目录，与 backend.client._app_root 同约定）。"""
    try:
        if getattr(sys, "frozen", False):
            root = os.path.dirname(sys.executable)
        else:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(root, _DEFAULT_CACHE)
    except Exception:
        return _DEFAULT_CACHE


class TTSEngine:
    """edge-tts 合成器：缓存 + 异步线程 + 全链路静默降级。"""

    def __init__(self, default_voice: str = VOICE_PRESETS["elder_minister"]):
        self.default_voice = default_voice
        self._fail_reason = ""

    # ---- 可用性 ----
    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except Exception as e:
            self._fail_reason = f"edge-tts 未安装: {e}"
            return False

    def last_fail_reason(self) -> str:
        return self._fail_reason

    # ---- 音色选择 ----
    @staticmethod
    def voice_for_minister(name: str) -> str:
        """按大臣名确定性映射音色（同人同声；跨会话稳定）。"""
        if not name:
            return VOICE_PRESETS["narrator"]
        keys = list(VOICE_PRESETS.keys())
        idx = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16) % len(keys)
        return VOICE_PRESETS[keys[idx]]

    # ---- 合成（阻塞版：调用方自行放线程）----
    def synthesize(self, text: str, voice: str = "", out_path: str = "") -> str:
        """合成语音文件，返回文件路径；失败返回 ""（原因见 last_fail_reason）。"""
        text = (text or "").strip()
        if not text:
            self._fail_reason = "空文本"
            return ""
        voice = voice or self.default_voice
        try:
            cache = _cache_dir()
            os.makedirs(cache, exist_ok=True)
            key = hashlib.md5(f"{voice}|{text}".encode("utf-8")).hexdigest()
            path = out_path or os.path.join(cache, f"{key}.mp3")
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                return path  # 缓存命中
            import asyncio
            import edge_tts
            async def _run():
                com = edge_tts.Communicate(text, voice)
                await com.save(path)
            asyncio.run(_run())
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                return path
            self._fail_reason = "合成产物为空"
            return ""
        except Exception as e:
            self._fail_reason = f"合成失败: {e}"
            # 半成品清理
            try:
                if out_path and os.path.isfile(out_path):
                    os.remove(out_path)
            except Exception:
                pass
            return ""

    # ---- 合成（异步版：GUI 用）----
    def synthesize_async(self, text: str, voice: str = "",
                         callback=None, on_error=None) -> threading.Thread:
        """后台线程合成；callback(path) 成功 / on_error(reason) 失败。

        线程安全：回调在**工作线程**触发——GUI 侧必须经 widget.after()
        回主线程再碰控件（绝不跨线程直改 Tkinter）。
        """
        def _work():
            path = self.synthesize(text, voice)
            try:
                if path:
                    if callback:
                        callback(path)
                else:
                    if on_error:
                        on_error(self._fail_reason)
            except Exception:
                pass  # 回调异常不影响线程收尾
        t = threading.Thread(target=_work, daemon=True, name="songzuo-tts")
        t.start()
        return t


# 进程级单例（GUI 与工具共用缓存与配置）
tts_engine = TTSEngine()


def play_file(path: str) -> bool:
    """非阻塞播放音频文件。Windows 用 winsound(SND_ASYNC)；其他平台暂不支持。"""
    if not path or not os.path.isfile(path):
        return False
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(path, winsound.SND_ASYNC | winsound.SND_FILENAME)
            return True
    except Exception:
        pass
    return False
