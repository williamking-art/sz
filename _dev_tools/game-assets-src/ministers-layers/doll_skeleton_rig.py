# -*- coding: utf-8 -*-
"""北宋官员 3D/2.5D 骨骼系统与 2D 投影换装烘焙核心定义。

用户裁定方案 B 权威实现：
1. 以 3D/2.5D 骨骼人偶（Rigged Base Doll）为刚性几何基准；
2. 锁定视角：四分之三正面（宋画经典微倾 5 度视线，俯角 0 度，正投影/微透视）；
3. 统一规范画幅：810 × 1080（3:4 黄金画幅）；
4. 核心骨骼节点（Skeletal Joints & Anchors）：
   - Root: (405, 1080)
   - Pelvis / Hip: (405, 820)
   - Waist: (405, 680)  [革带水平基准线]
   - Chest / Spine2: (405, 520)  [双手持笏/拱手中心]
   - Neck: (405, 390)
   - Collar: (405, 360)  [圆领大袍领口交界，露出内衬白绢中单]
   - Head / Skull: (405, 230)  [漆纱幞头帽体底缘基准]
   - Head_Top: (405, 120)  [发髻顶端]
   - Pouch_Anchor: (490, 710)  [右侧随身鱼袋悬挂点]
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class PoseType(str, Enum):
    """5 大标准姿态。"""
    CHIHU = "pose_chihu"          # 端直持笏：双手捧朝笏于胸前
    GONGSHOU = "pose_gongshou"    # 拱揖肃立：宽袖双抱胸前
    LONGXIU = "pose_longxiu"      # 长袖垂立：宽袍大袖垂于身侧
    FUXU = "pose_fuxu"            # 轻抚清髯：一手垂立一手抚须
    ANJIAN = "pose_anjian"        # 按带持节：手按革带带銙


@dataclass
class Joint2D:
    name: str
    x: float
    y: float
    parent: Optional[str] = None
    rotation_deg: float = 0.0


@dataclass
class SkeletonRig2D:
    """标准 810×1080 2D 骨骼定义。"""
    width: int = 810
    height: int = 1080
    joints: Dict[str, Joint2D] = field(default_factory=dict)

    @classmethod
    def create_standard_rig(cls, pose: PoseType = PoseType.CHIHU) -> "SkeletonRig2D":
        rig = cls()
        # 基础中轴骨骼
        rig.joints["root"] = Joint2D("root", 405, 1080)
        rig.joints["pelvis"] = Joint2D("pelvis", 405, 820, parent="root")
        rig.joints["waist"] = Joint2D("waist", 405, 680, parent="pelvis")
        rig.joints["chest"] = Joint2D("chest", 405, 520, parent="waist")
        rig.joints["neck"] = Joint2D("neck", 405, 390, parent="chest")
        rig.joints["collar"] = Joint2D("collar", 405, 360, parent="neck")
        rig.joints["head"] = Joint2D("head", 405, 230, parent="neck")
        rig.joints["head_top"] = Joint2D("head_top", 405, 120, parent="head")

        # 挂载配件锚点
        rig.joints["pouch_anchor"] = Joint2D("pouch_anchor", 490, 710, parent="waist")
        rig.joints["belt_anchor"] = Joint2D("belt_anchor", 405, 680, parent="waist")

        # 左右肩膀
        rig.joints["shoulder_l"] = Joint2D("shoulder_l", 270, 410, parent="collar")
        rig.joints["shoulder_r"] = Joint2D("shoulder_r", 540, 410, parent="collar")

        # 手臂与手部关节依姿态变化
        if pose == PoseType.CHIHU:
            rig.joints["elbow_l"] = Joint2D("elbow_l", 310, 560, parent="shoulder_l")
            rig.joints["elbow_r"] = Joint2D("elbow_r", 500, 560, parent="shoulder_r")
            rig.joints["wrist_l"] = Joint2D("wrist_l", 380, 530, parent="elbow_l")
            rig.joints["wrist_r"] = Joint2D("wrist_r", 430, 530, parent="elbow_r")
            rig.joints["hu_anchor"] = Joint2D("hu_anchor", 405, 470, parent="chest")
        elif pose == PoseType.GONGSHOU:
            rig.joints["elbow_l"] = Joint2D("elbow_l", 290, 540, parent="shoulder_l")
            rig.joints["elbow_r"] = Joint2D("elbow_r", 520, 540, parent="shoulder_r")
            rig.joints["wrist_l"] = Joint2D("wrist_l", 395, 510, parent="elbow_l")
            rig.joints["wrist_r"] = Joint2D("wrist_r", 415, 510, parent="elbow_r")
        elif pose == PoseType.LONGXIU:
            rig.joints["elbow_l"] = Joint2D("elbow_l", 260, 600, parent="shoulder_l")
            rig.joints["elbow_r"] = Joint2D("elbow_r", 550, 600, parent="shoulder_r")
            rig.joints["wrist_l"] = Joint2D("wrist_l", 270, 780, parent="elbow_l")
            rig.joints["wrist_r"] = Joint2D("wrist_r", 540, 780, parent="elbow_r")
        else:
            # 默认持笏
            rig.joints["elbow_l"] = Joint2D("elbow_l", 310, 560, parent="shoulder_l")
            rig.joints["elbow_r"] = Joint2D("elbow_r", 500, 560, parent="shoulder_r")
            rig.joints["wrist_l"] = Joint2D("wrist_l", 380, 530, parent="elbow_l")
            rig.joints["wrist_r"] = Joint2D("wrist_r", 430, 530, parent="elbow_r")
            rig.joints["hu_anchor"] = Joint2D("hu_anchor", 405, 470, parent="chest")

        return rig

    def get_anchor(self, name: str) -> Tuple[int, int]:
        if name in self.joints:
            j = self.joints[name]
            return int(round(j.x)), int(round(j.y))
        raise KeyError(f"未找到骨骼锚点: {name}")
