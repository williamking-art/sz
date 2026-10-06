# -*- coding: utf-8 -*-
"""宋的势力配置（P1）。

本文件**不复制任何数值** —— 全部**引用** `core.building_jobs.SONG_*` 原值，
保证「原值迁入」且**不产生第二份真账**（承 AGENTS.md 口径单点）。

P1 范围：**仅登记既有值**，不改业务结算、不改数值口径。
"""
from core.building_jobs import (
    SONG_BUILDING_WORKER, SONG_JOB_CLASSES, SONG_JOB_FLOW_RATE,
    SONG_JOB_PUSH_UNEMPLOYED, SONG_JOB_QUEUE, SONG_JOB_SHARE_DEFAULT,
    SONG_JOBS_PER_LEVEL, SONG_POSITION_CLASS,
)
from content.faction_schema import FieldState

FACTION_ID = 'song'
DISPLAY_NAME = '宋'

#: 共同目录之外的扩展/变体建筑（宋侧暂无）。
EXTENSION_BUILDINGS = ()

CONFIG = {
    'POSITIONS': tuple(SONG_POSITION_CLASS.keys()),
    'POSITION_CLASS': SONG_POSITION_CLASS,
    'INSTITUTIONS': (),
    'OFFICIAL_PARAMS': (),
    'JOBS_PER_LEVEL': SONG_JOBS_PER_LEVEL,
    'BUILDING_WORKER': SONG_BUILDING_WORKER,
    'JOB_CLASSES': tuple(SONG_JOB_CLASSES),
    'JOB_QUEUE': SONG_JOB_QUEUE,
    'JOB_SHARE': SONG_JOB_SHARE_DEFAULT,
    'JOB_FLOW_RATE': SONG_JOB_FLOW_RATE,
    'JOB_PUSH_UNEMPLOYED': SONG_JOB_PUSH_UNEMPLOYED,
    'FIELD_STATES': {
        'INSTITUTIONS': FieldState.MISSING,
        'OFFICIAL_PARAMS': FieldState.MISSING,
    },
    'NA_REASONS': {},
}