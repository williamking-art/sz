# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.administration.monthly_gazette
# 不复制实现；新模块不得导入本薄转发。
from core.domains.administration.monthly_gazette import (
    Any, CHAPTER_ORDER, DIFF_PATH_LABELS,
    Dict, GAZETTE_COUPLETS, List,
    Optional, _CHAPTER_KEYWORDS, _CHAPTER_SCENE_TEMPLATES,
    _DIFF_POP_LABELS, _chapter_agent_diff, _chapter_by_keywords,
    _chapter_life, _chapter_scenes, _chapter_secret,
    _chapter_situations, _couplet, _diff_path_label,
    _diff_summary, _fmt_delta, _last_month_lines,
    annotations, build_monthly_gazette,
)

__all__ = ['Any', 'CHAPTER_ORDER', 'DIFF_PATH_LABELS', 'Dict', 'GAZETTE_COUPLETS', 'List', 'Optional', '_CHAPTER_KEYWORDS', '_CHAPTER_SCENE_TEMPLATES', '_DIFF_POP_LABELS', '_chapter_agent_diff', '_chapter_by_keywords', '_chapter_life', '_chapter_scenes', '_chapter_secret', '_chapter_situations', '_couplet', '_diff_path_label', '_diff_summary', '_fmt_delta', '_last_month_lines', 'annotations', 'build_monthly_gazette']
