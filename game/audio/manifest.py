# -*- coding: utf-8 -*-
"""宋祚 · 音频资源清单（规划性骨架）

声明已知音频槽位（事件/回合/界面），全部为"待生成"占位。
任何真实资源落地后，在此登记：用途、文件、时长、循环、触发点、音量档位、来源/授权。

资源命名约定：<类别>_<语义>.ogg（背景乐用 .ogg，短音效可用 .wav）。
试验稿与未批准素材禁止出现在此清单，统一放 _scratch/generated-audio/。
"""
from dataclasses import dataclass, field

__all__ = ["AUDIO_SLOTS", "register_slot", "EVENT_AUDIO_CLASS", "audio_class_for"]

# —— 事件→音效分类的单一权威源 ——
# 与 ui/panels_meta.py 事件插图的四档朱批色（灾/战=急、祥瑞=吉、常=褐）
# 共用同一份事件 ID 分类，避免 UI 与 audio 各写各的导致漂移。
# 值约定："urgent"(灾/战) / "auspicious"(祥瑞) / "normal"(朝务/一般)
EVENT_AUDIO_CLASS: dict = {
    # 灾异 / 战争（急·朱红）
    "huanghe_flood": "urgent",
    "fangla_uprising": "urgent",
    "songjiang": "urgent",
    "jin_invasion": "urgent",
    "jin_destroys_liao": "urgent",
    "sea_alliance": "urgent",
    # 祥瑞（吉·绿）
    "xiangrui": "auspicious",
}


def audio_class_for(event_id: str, default: str = "normal") -> str:
    """返回事件对应的音效分类，未知事件回落 default（朝务/一般）。"""
    return EVENT_AUDIO_CLASS.get(event_id, default)


@dataclass
class AudioSlot:
    key: str                # 逻辑键，如 "event_disaster"
    category: str           # bgm / sfx / voice
    file: str = ""          # 资源文件名（落 assets/audio/），生成前为空
    loop: bool = False      # 是否循环（背景乐 True）
    trigger: str = ""       # 触发点描述（事件类型 / 回合 / 界面动作）
    volume_bias: float = 1.0  # 相对主音量的档位系数
    source: str = ""        # 来源与授权（生成后填写）
    ready: bool = False     # 资源是否已生成并落位


# 初始槽位：与 ui/panels_meta.py 事件插图四档朱批色（灾/战=急、祥瑞=吉、常=褐）
# 共用 EVENT_AUDIO_CLASS 单一权威源，分类口径严格对齐。
AUDIO_SLOTS: list = [
    AudioSlot("bgm_court", "bgm", loop=True, trigger="主界面/朝堂常驻", volume_bias=0.6),
    AudioSlot("bgm_battle", "bgm", loop=True, trigger="军事/战争事件", volume_bias=0.7),
    AudioSlot("sfx_disaster", "sfx", trigger="灾异事件（急·朱）"),
    AudioSlot("sfx_omen", "sfx", trigger="祥瑞事件（吉·朱）"),
    AudioSlot("sfx_decree", "sfx", trigger="下诏/拟诏"),
    AudioSlot("sfx_click", "sfx", trigger="界面按钮点击（克制）"),
]


def register_slot(slot: AudioSlot):
    AUDIO_SLOTS.append(slot)
