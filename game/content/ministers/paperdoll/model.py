# -*- coding: utf-8 -*-
"""北宋官员 2D 布娃娃换装系统（Paper Doll System）核心数据模型与契约。

借鉴 RPG 工业架构与开源标杆：
1. 插槽解耦：装备与人体素体彻底分离（QQ 秀模式）；
2. 绝对层级（Z-Index）：严格定义渲染次序，消除穿模与重影；
3. 锚点对齐（Rigging Anchors）：每一个素体拥有一套骨骼锚点坐标（ChibiRigKit 模式）；
4. 千人千面（FaceDNA）：7 维五官解耦（4032万种不重样面相）；
5. 情绪联动（EmotionState）：AI 对话语义驱动情绪与微动作（Shinsekai 模式）；
6. 数据驱动（MinisterAudienceProfile）：纯 JSON 配置驱动（VNDialog 模式）。
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


class EmotionState(str, Enum):
    """君臣召对时的大臣情绪与动作状态机（Shinsekai 模式）。"""
    RESPECTFUL = "respectful"     # 恭谨肃立：神态端庄，持笏肃立
    RESOLUTE = "resolute"         # 刚直不阿：目光如炬，骨鲠直谏
    WORRIED = "worried"           # 忧心忡忡：双眉微蹙，深忧国事
    PANIC = "panic"               # 惶恐请罪：合抱拱手，引咎自劾
    GRATIFIED = "gratified"       # 欣慰受赏：含笑从容，拜领圣恩


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
    """布娃娃骨架锚点配置集合（基于 810×1080 统一大半身像画幅）。"""
    head_mount: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 230))
    face_center: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 300))
    eyes_line: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 285))
    chin: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 395))
    collar: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 430))
    waist: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 715))
    pouch: AnchorPoint = field(default_factory=lambda: AnchorPoint(500, 720))
    hands: AnchorPoint = field(default_factory=lambda: AnchorPoint(405, 595))


@dataclass
class FaceDNA:
    """千人千面多维解耦五官参数（4032万种完全不重样面相）。"""
    face_shape: str = "shape_square"           # 脸型 (7类)
    eyebrows: str = "eyebrow_straight_thick"   # 眉形 (8类)
    eyes: str = "eyes_eagle_sharp"             # 眼型 (8类)
    nose: str = "nose_straight_high"           # 鼻型 (6类)
    mouth: str = "mouth_tight_firm"            # 嘴唇 (6类)
    beard: str = "beard_three_tuft_refined"    # 胡须 (12类)
    complexion: str = "complexion_mature"      # 岁月风霜与肤色 (5阶)

    def to_dict(self) -> Dict[str, str]:
        return {
            "face_shape": self.face_shape,
            "eyebrows": self.eyebrows,
            "eyes": self.eyes,
            "nose": self.nose,
            "mouth": self.mouth,
            "beard": self.beard,
            "complexion": self.complexion,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FaceDNA:
        return cls(
            face_shape=data.get("face_shape", "shape_square"),
            eyebrows=data.get("eyebrows", "eyebrow_straight_thick"),
            eyes=data.get("eyes", "eyes_eagle_sharp"),
            nose=data.get("nose", "nose_straight_high"),
            mouth=data.get("mouth", "mouth_tight_firm"),
            beard=data.get("beard", "beard_three_tuft_refined"),
            complexion=data.get("complexion", "complexion_mature"),
        )


@dataclass
class EquipmentItem:
    """装备部件定义。"""
    id: str                       # 部件唯一标识，如 "robe_purple_chancellor"
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
    default_face_dna: FaceDNA     # 默认五官解耦参数
    render_handler: Optional[Callable[[DollSkeletonRig], str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MinisterAudienceProfile:
    """大臣召对动态立绘完整配置数据模型（对应 VNDialog JSON 配置）。"""
    minister_id: str
    name: str
    age: int
    rank: str                     # 官阶文本，如 "从一品 尚书左仆射"
    costume_tier: str             # "zi", "fei", "lv", "qing", "shi"
    base_mannequin: str           # 素体模特 ID
    face_dna: FaceDNA             # 独一无二解耦五官
    equipped: Dict[str, str]      # 装备插槽 -> 部件ID 映射
    current_emotion: EmotionState = EmotionState.RESPECTFUL
    historical: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "minister_id": self.minister_id,
            "name": self.name,
            "age": self.age,
            "rank": self.rank,
            "costume_tier": self.costume_tier,
            "base_mannequin": self.base_mannequin,
            "face_dna": self.face_dna.to_dict(),
            "equipped": self.equipped,
            "current_emotion": self.current_emotion.value,
            "historical": self.historical,
            "metadata": self.metadata,
        }
