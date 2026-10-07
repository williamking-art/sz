# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.administration.minister_agent
# 不复制实现；新模块不得导入本薄转发。
from core.domains.administration.minister_agent import (
    ACTOR_MIN_FIELDS, ACTOR_SCHEMA_VERSION, Any,
    Dict, List, MINISTER_STATUS_IN_OFFICE,
    MINISTER_STATUS_OUT, Optional, _actor_store,
    _num, actor_ids_of, actor_view,
    annotations, can_act, ensure_actor,
    intents_of, recall, record_intent,
    remember,
)

__all__ = ['ACTOR_MIN_FIELDS', 'ACTOR_SCHEMA_VERSION', 'Any', 'Dict', 'List', 'MINISTER_STATUS_IN_OFFICE', 'MINISTER_STATUS_OUT', 'Optional', '_actor_store', '_num', 'actor_ids_of', 'actor_view', 'annotations', 'can_act', 'ensure_actor', 'intents_of', 'recall', 'record_intent', 'remember']
