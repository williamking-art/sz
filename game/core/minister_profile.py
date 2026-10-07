# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.administration.read_models.minister_profile
# 不复制实现；新模块不得导入本薄转发。
from core.domains.administration.read_models.minister_profile import (
    _portrait_url, annotations, build_minister_profiles,
)

__all__ = ['_portrait_url', 'annotations', 'build_minister_profiles']
