# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import random

from content.data import TIER_RANGE
from core.settlement_common import distribute_cash

_log = logging.getLogger('settlement')


def _settle_emperor_health_decay(state, log):
    """皇帝健康自然衰减（逸乐>80 加速；健康>0 月度小减）。"""
    if state.pleasure_leaning > 80 and random.random() < 0.05:
        state.emperor_health -= 3

    if state.emperor_health > 0 and random.random() < 0.02:
        state.emperor_health -= 1
