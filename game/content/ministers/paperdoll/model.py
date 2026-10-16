# -*- coding: utf-8 -*-
"""北宋官员 2D 布娃娃换装系统（Paper Doll System）核心数据模型与契约。

借鉴 RPG 工业架构与开源标杆：
1. 插槽解耦：装备与人体素体彻底分离；
2. 绝对层级（Z-Index）：严格定义渲染次序，消除穿模与重影；
3. 锚点对齐（Rigging Anchors）：每一个素体拥有一套骨骼锚点坐标；
4. 画布标准：统一 810×1080 3:4 黄金肖像比例大半身像。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple


class EquipmentSlot(str, Enum):
    """布娃娃换装系统的标准装备插槽。"""
    BASE_DOLL = "base_doll"       # 人形素体 (体型/姿态/手势)
    FACE = "face"                 # 五官面模 (眼睛/眉毛/鼻嘴)
    BEARD = "beard"               # 独立胡须髯口
    COLLAR = "collar"             # 白色中单交领 (护颈)
    ROBE = "robe"                 # 官制袍服 (圆领大袖襕袍)
    BELT = "belt"                 # 公服革带 (带銙板)
    POUCH = "pouch"               # 随身鱼袋 (金鱼袋/银鱼袋)
    HELD = "held"                 # 手持朝笏手板
    HEADWEAR = "headwear"         # 漆纱幞头官帽 (极展长角/平角/短角)


class RenderZIndex(IntEnum):
    """严格的渲染图层深度顺序（自底向顶）。"""
    BACKGROUND = 0                # 0: 老绢本画心底色
    BASE_DOLL = 10                # 10: 人形素体 (脖颈/肩身/四肢)
    FACE = 20                     # 20: 五官面貌
    BEARD = 30                    # 30: 唇髭与长髯
    COLLAR = 40                   # 40: 中单交领素衬
    ROBE = 50                     # 50: 官服大袍与大袖
    BELT = 60                     # 60: 革带扎腰
    POUCH = 70                    # 70: 右侧佩鱼
    HELD = 80                     # 80: 胸前双手捧朝笏
    HEADWEAR = 90                 # 90: 漆纱幞头紧扣发际


@dataclass
class AnchorPoint:
    """骨骼插槽锚点坐标。"""
    x: int
    y: int
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0


@dataclass
class DollSkeletonRig:
    """布娃娃骨架锚点配置集合（基于 810×1080 画布）。"""
    head_mount: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 230))
    face_center: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 300))
    eyes_line: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 285))
    chin: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 395))
    collar: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 430))
    waist: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 715))
    pouch: AnchorPoint = field(default_factory=lambda: AnchorPoint(500, 720))
    hands: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 595))


@dataclass
class EquipmentItem:
    """装备部件定义。"""
    id: str                       # 部件唯一标识，如 "robe_chihu_zi"
    name: str                     # 部件中文名称，如 "绛紫素罗襕袍"
    slot: EquipmentSlot           # 所属装备插槽
    tier: str                     # 官阶等级 ("zi", "fei", "lv", "qing", "shi")
    z_index: int                  # 渲染深度 (默认继承插槽默认深度)
    render_type: str = "vector"   # 渲染类型 ("vector" / "baked_image")
    asset_path: Optional[str] = None # 预烘焙静态图片路径 (可选)
    svg_generator: Optional[Callable[[DollSkeletonRig, Dict[str, Any]], str]] = None
    mask_slots: List[EquipmentSlot] = field(default_factory=list) # 遮蔽/隐藏的下层插槽
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DollMannequin:
    """人形素体底模定义（Mannequin）。"""
    id: str                       # 素体 ID，如 "doll_young_scholar"
    name: str                     # 素体中文名称，如 "青年清俊及第进士"
    age_group: str                # 年龄段: "young", "middle", "elder"
    pose: str                     # 动作姿态: "chihu", "gongshou", "longxiu", "fuxu"
    rig: DollSkeletonRig          # 骨架锚点
    default_face: str             # 默认五官
    default_beard: str            # 默认胡须
    render_handler: Optional[Callable[[DollSkeletonRig], str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
