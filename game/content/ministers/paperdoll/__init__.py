# -*- coding: utf-8 -*-
"""北宋官员 2D 布娃娃换装系统（Paper Doll System）公共入口。

四大标杆融合设计：
- VNDialog：纯 JSON 配置驱动展示；
- ChibiRigKit & QQ 秀：810×1080 刚性大半身像素体模特 + 8 大插槽自底向上无瑕叠装；
- Live2DMascot：沉稳官仪微动态（缓步呼吸、自然眨眼、长髯展角微颤）；
- Shinsekai：AI 对话语义驱动情绪状态机。
"""
from __future__ import annotations

try:
    from content.ministers.paperdoll.controller import MinisterAudienceController
    from content.ministers.paperdoll.engine import PaperdollRenderEngine
    from content.ministers.paperdoll.model import (
        AnchorPoint,
        DollMannequin,
        DollSkeletonRig,
        EmotionState,
        EquipmentItem,
        EquipmentSlot,
        FaceDNA,
        MinisterAudienceProfile,
        RenderZIndex,
    )
    from content.ministers.paperdoll.registry import (
        EQUIPMENT_CATALOG,
        EYEBROWS,
        EYES,
        FACE_SHAPES,
        MANNEQUIN_CATALOG,
        MOUTHS,
        NOSES,
        generate_visual_dna,
    )
    from content.ministers.paperdoll.rules import (
        RegaliaViolationError,
        resolve_promotion_equipment,
        validate_regalia_compliance,
    )
except ImportError:
    from game.content.ministers.paperdoll.controller import MinisterAudienceController
    from game.content.ministers.paperdoll.engine import PaperdollRenderEngine
    from game.content.ministers.paperdoll.model import (
        AnchorPoint,
        DollMannequin,
        DollSkeletonRig,
        EmotionState,
        EquipmentItem,
        EquipmentSlot,
        FaceDNA,
        MinisterAudienceProfile,
        RenderZIndex,
    )
    from game.content.ministers.paperdoll.registry import (
        EQUIPMENT_CATALOG,
        EYEBROWS,
        EYES,
        FACE_SHAPES,
        MANNEQUIN_CATALOG,
        MOUTHS,
        NOSES,
        generate_visual_dna,
    )
    from game.content.ministers.paperdoll.rules import (
        RegaliaViolationError,
        resolve_promotion_equipment,
        validate_regalia_compliance,
    )

__all__ = [
    "AnchorPoint",
    "DollMannequin",
    "DollSkeletonRig",
    "EmotionState",
    "EquipmentItem",
    "EquipmentSlot",
    "FaceDNA",
    "MinisterAudienceProfile",
    "RenderZIndex",
    "PaperdollRenderEngine",
    "MinisterAudienceController",
    "MANNEQUIN_CATALOG",
    "EQUIPMENT_CATALOG",
    "FACE_SHAPES",
    "EYEBROWS",
    "EYES",
    "NOSES",
    "MOUTHS",
    "generate_visual_dna",
    "resolve_promotion_equipment",
    "validate_regalia_compliance",
    "RegaliaViolationError",
]
