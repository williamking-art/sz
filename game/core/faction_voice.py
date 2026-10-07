# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.politics.voice（第十七包，2026-10-07）。
# 公开面上每个名字都从实现模块转发（含 `_` 开头私有名与 typing/logging 绑定名）；
# ⚠️ 打在桩上的 monkeypatch 不会再影响消费者——两处提供方 patch 已同批改指实现模块。
"""宋祚 · 派系话语权（faction voice）（兼容入口）。实现在 `core/domains/politics/voice.py`。"""
from core.domains.politics.voice import (  # noqa: F401
    Any, DEFAULT_MATTER_WEIGHT, Dict, MATTER_VOICE_WEIGHT, Optional, Tuple, VOICE_FULL, _clamp, _faction_of, _log1p, _orgs, annotations, log, logging, org_voice, total_voice, voice_norm, voice_seats, voice_share,
)
