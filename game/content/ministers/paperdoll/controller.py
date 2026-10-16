# -*- coding: utf-8 -*-
"""北宋官员召对立绘换装控制器（Minister Audience Controller）。

融合四大开源标杆架构：
1. VNDialog 模式：通过纯 JSON 配置文件驱动立绘展示与部件加载；
2. Live2DMascot 模式：提供沉稳端庄的官仪微动态（缓步呼吸、自然眨眼、长髯微拂、铁线展角微颤）；
3. Shinsekai 模式：召对/廷辩时，AI 对话语义与君臣问答实时驱动立绘情绪与动作状态机；
4. ChibiRigKit & QQ 秀模式：骨骼插槽无瑕叠装、仕途升迁自动除授换装（绿/绯/紫、金银鱼袋、玉带）。
"""
from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from content.ministers.paperdoll.engine import PaperdollRenderEngine
    from content.ministers.paperdoll.model import (
        EmotionState,
        EquipmentSlot,
        FaceDNA,
        MinisterAudienceProfile,
    )
    from content.ministers.paperdoll.registry import (
        EQUIPMENT_CATALOG,
        MANNEQUIN_CATALOG,
        generate_visual_dna,
    )
    from content.ministers.paperdoll.rules import (
        resolve_promotion_equipment,
        validate_regalia_compliance,
    )
except ImportError:
    from game.content.ministers.paperdoll.engine import PaperdollRenderEngine
    from game.content.ministers.paperdoll.model import (
        EmotionState,
        EquipmentSlot,
        FaceDNA,
        MinisterAudienceProfile,
    )
    from game.content.ministers.paperdoll.registry import (
        EQUIPMENT_CATALOG,
        MANNEQUIN_CATALOG,
        generate_visual_dna,
    )
    from game.content.ministers.paperdoll.rules import (
        resolve_promotion_equipment,
        validate_regalia_compliance,
    )


class MinisterAudienceController:
    """召对场景下官员立绘的核心状态机与控制器。"""

    def __init__(
        self,
        profile: MinisterAudienceProfile,
        render_engine: Optional[PaperdollRenderEngine] = None,
    ):
        self.profile = profile
        self.engine = render_engine or PaperdollRenderEngine()
        self.dialogue_history: List[Dict[str, Any]] = []

    @classmethod
    def create_for_minister(
        cls,
        minister_id: str,
        name: str,
        age: int,
        rank: str,
        traits: Optional[List[str]] = None,
        origin: str = "",
        historical: bool = False,
        render_engine: Optional[PaperdollRenderEngine] = None,
    ) -> MinisterAudienceController:
        """根据官员基本身世、官阶与特质，通过确定性 Visual DNA 算法一键生成专属控制器。"""
        traits = traits or []
        base_mannequin, face_dna, equipped = generate_visual_dna(
            minister_id=minister_id,
            name=name,
            age=age,
            rank=rank,
            traits=traits,
            origin=origin,
        )

        try:
            from content.ministers.costumes import parse_costume_tier
        except ImportError:
            from game.content.ministers.costumes import parse_costume_tier
        costume_tier = parse_costume_tier(rank)

        profile = MinisterAudienceProfile(
            minister_id=minister_id,
            name=name,
            age=age,
            rank=rank,
            costume_tier=costume_tier,
            base_mannequin=base_mannequin,
            face_dna=face_dna,
            equipped=equipped,
            current_emotion=EmotionState.RESPECTFUL,
            historical=historical,
            metadata={
                "traits": traits,
                "origin": origin,
            },
        )
        return cls(profile, render_engine=render_engine)

    @classmethod
    def from_json_config(
        cls,
        json_path_or_content: str,
        render_engine: Optional[PaperdollRenderEngine] = None,
    ) -> MinisterAudienceController:
        """从 VNDialog 风格的标准 JSON 配置文件（或 JSON 字符串）加载立绘控制器。"""
        if os.path.exists(json_path_or_content):
            with open(json_path_or_content, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(json_path_or_content)

        face_dna_data = data.get("face_dna", {})
        face_dna = FaceDNA.from_dict(face_dna_data)

        emotion_str = data.get("current_emotion", EmotionState.RESPECTFUL.value)
        try:
            current_emotion = EmotionState(emotion_str)
        except ValueError:
            current_emotion = EmotionState.RESPECTFUL

        profile = MinisterAudienceProfile(
            minister_id=data.get("minister_id", "unknown"),
            name=data.get("name", "无名"),
            age=int(data.get("age", 40)),
            rank=data.get("rank", "从八品 承务郎"),
            costume_tier=data.get("costume_tier", "lv"),
            base_mannequin=data.get("base_mannequin", "mannequin_middle"),
            face_dna=face_dna,
            equipped=data.get("equipped", {}),
            current_emotion=current_emotion,
            historical=bool(data.get("historical", False)),
            metadata=data.get("metadata", {}),
        )
        return cls(profile, render_engine=render_engine)

    def to_dict(self) -> Dict[str, Any]:
        """导出为符合 VNDialog 规范的结构化字典。"""
        return self.profile.to_dict()

    def export_json_config(self, file_path: Optional[str] = None) -> str:
        """导出 VNDialog JSON 配置并持久化（可选）。"""
        data = self.to_dict()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        if file_path:
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str

    # ==================== 1. Shinsekai 模式：对话语义与情绪联动 ====================

    def set_emotion(self, emotion: Union[EmotionState, str]) -> None:
        """手动设置大臣当前情绪状态。"""
        if isinstance(emotion, str):
            emotion = EmotionState(emotion)
        self.profile.current_emotion = emotion

    def on_dialogue(self, speech_text: str, speaker_is_emperor: bool = False) -> EmotionState:
        """根据召对对话语义实时驱动大臣情绪状态机（Shinsekai 模式）。
        
        支持两类对话场景：
        1. 皇帝问话/圣谕：大臣听到圣旨或斥责/褒奖时的心理反应；
        2. 大臣自奏/答对：大臣自身言辞蕴含的直谏、请罪、忧国或受赏之意。
        """
        text = speech_text.strip()
        matched_emotion = EmotionState.RESPECTFUL

        if speaker_is_emperor:
            # 皇帝言论对大臣情绪的影响
            if re.search(r"(荒谬|欺君|严惩|罢黜|下狱|革职|放肆|问罪|责罚|何罪)", text):
                matched_emotion = EmotionState.PANIC
            elif re.search(r"(嘉奖|升迁|重用|赏|功在社稷|朕心甚慰|依卿所奏|准奏)", text):
                matched_emotion = EmotionState.GRATIFIED
            elif re.search(r"(边患|兵败|溃退|军粮|大水|民变|旱灾|亏空|危急)", text):
                matched_emotion = EmotionState.WORRIED
            elif re.search(r"(卿意下如何|如何处置|可有良策|祖宗法度)", text):
                matched_emotion = EmotionState.RESOLUTE
        else:
            # 大臣自奏的言语意图
            if re.search(r"(臣死罪|臣失职|引咎|伏乞|惶恐|罪该万死|乞骸骨|待罪)", text):
                matched_emotion = EmotionState.PANIC
            elif re.search(r"(万不可|切不可|断然不能|祖宗之法|严惩|严劾|必当|抗颜|据理|力争)", text):
                matched_emotion = EmotionState.RESOLUTE
            elif re.search(r"(臣忧之|臣窃深忧|大患|流民|国帑空虚|边防吃紧|危急存亡|荼毒|饥馑)", text):
                matched_emotion = EmotionState.WORRIED
            elif re.search(r"(圣明天子|万岁|谢陛下|叩谢|大捷|海内升平|瑞雪|拜领|臣敢不竭忠)", text):
                matched_emotion = EmotionState.GRATIFIED

        self.profile.current_emotion = matched_emotion
        self.dialogue_history.append({
            "speaker": "emperor" if speaker_is_emperor else "minister",
            "text": text,
            "reaction": matched_emotion.value,
        })
        return matched_emotion

    # ==================== 2. QQ 秀模式：仕途升迁与规制换装 ====================

    def promote_and_equip(self, new_rank: str, favors: Optional[List[str]] = None) -> List[str]:
        """官员仕途除授或得获恩赐，换装并进行舆服法度校验。"""
        favors = favors or []
        old_rank = self.profile.rank
        new_equipped = resolve_promotion_equipment(self.profile.equipped, new_rank, favors)

        # 舆服违制合规检查
        violations = validate_regalia_compliance(new_equipped, new_rank, favors)

        try:
            from content.ministers.costumes import parse_costume_tier
        except ImportError:
            from game.content.ministers.costumes import parse_costume_tier
        new_tier = parse_costume_tier(new_rank)
        if "借紫" in favors or "赐紫" in favors:
            new_tier = "zi"
        elif "借绯" in favors or "赐绯" in favors:
            if new_tier not in ("zi", "qinwang"):
                new_tier = "fei"

        # 应用换装
        self.profile.rank = new_rank
        self.profile.costume_tier = new_tier
        self.profile.equipped = new_equipped

        notes = [f"除授品位：从【{old_rank}】晋为【{new_rank}】"]
        if "zi" in new_tier:
            notes.append("得赐/借紫服，改服绛紫素罗大袖襕袍")
        elif "fei" in new_tier:
            notes.append("得赐/借绯服，改服朱红细罗大袖襕袍")
        
        if "pouch_gold_fish" in new_equipped.values():
            notes.append("佩带随身鎏金金鱼袋")
        elif "pouch_silver_fish" in new_equipped.values():
            notes.append("佩带随身刻纹银鱼袋")

        if violations:
            notes.append(f"【舆服警告】：{'; '.join(violations)}")

        return notes

    # ==================== 3. Live2DMascot 模式：沉稳官仪微动态 ====================

    def get_live2d_motion_params(self, t_seconds: float) -> Dict[str, float]:
        """计算指定时间刻（秒）的大臣微动态参数。
        
        北宋官仪讲究庄重肃穆、不怒自威，因此微动态幅度沉稳克制：
        - 呼吸起伏：周期约 3.2 秒，胸腔自然轻微起伏 1.5 ~ 2.0 像素；
        - 眨眼周期：约 3.5 ~ 4.2 秒眨眼一次，闭眼历时约 0.15 秒；
        - 髭髯/展角微动：微风与呼吸带动的极微幅物理惯性；
        """
        # 1. 呼吸周期 (3.2 秒周期)
        breath_phase = (t_seconds % 3.2) / 3.2 * 2 * math.pi
        breath_y = math.sin(breath_phase) * 1.8  # 上下起伏微小偏移

        # 2. 自然眨眼 (4.0 秒周期，其中 0.15 秒为闭眼)
        cycle_t = t_seconds % 4.0
        if 3.85 <= cycle_t < 4.0:
            # 闭眼过渡: 0.0 为全闭，1.0 为全开
            blink_ratio = 0.0 if cycle_t < 3.95 else (cycle_t - 3.95) / 0.05
        else:
            blink_ratio = 1.0

        # 3. 情绪修饰
        emotion = self.profile.current_emotion
        frown_offset = 0.0
        head_tilt = 0.0

        if emotion == EmotionState.WORRIED:
            frown_offset = 3.0  # 眉头内蹙压低
            head_tilt = -1.2    # 微侧低首
        elif emotion == EmotionState.PANIC:
            breath_y *= 1.8     # 惊惧急促呼吸
            blink_ratio = min(blink_ratio, 0.4) # 双眸微敛请罪
            head_tilt = -2.5    # 躬身垂首
        elif emotion == EmotionState.RESOLUTE:
            frown_offset = 1.5  # 刚直凝视
            head_tilt = 0.5     # 挺立昂首
        elif emotion == EmotionState.GRATIFIED:
            head_tilt = 0.8     # 喜悦和畅

        # 4. 铁线展角轻颤 (0.8 秒高频极微幅)
        futou_tremor = math.sin(t_seconds * 3.5) * 0.4

        return {
            "time_sec": t_seconds,
            "breath_y": round(breath_y, 2),
            "blink_ratio": round(blink_ratio, 2),
            "frown_offset": round(frown_offset, 2),
            "head_tilt": round(head_tilt, 2),
            "futou_tremor": round(futou_tremor, 2),
            "emotion": emotion.value,
        }

    # ==================== 4. 渲染与输出接口 ====================

    def render_svg(self, animated: bool = True) -> str:
        """渲染当前大臣立绘为完整高质量工笔矢量 SVG。
        
        若 animated=True，将在 SVG 中内嵌标准 CSS @keyframes 微动态动画：
        - 缓步官仪呼吸起伏（针对袍服与胸膛）；
        - 自然眨眼（针对眼帘）；
        - 展角铁线极微幅缓震。
        无需额外加载外部 heavy JS 库即可在网页、Electron 与任何 SVG 渲染器中直接动起来！
        """
        base_svg = self.engine.render_to_svg(self.profile)

        if not animated:
            return base_svg

        # 在 SVG <defs> 中注入沉稳微动态 CSS
        css_animation = '''
    <style>
      @keyframes song_breath {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-2.2px); }
      }
      @keyframes song_blink {
        0%, 94%, 100% { transform: scaleY(1); }
        96%, 98% { transform: scaleY(0.08); }
      }
      @keyframes song_futou_wing {
        0%, 100% { transform: rotate(0deg); }
        50% { transform: rotate(0.12deg); }
      }
      #layer5_robe, #layer4_collar, #layer6_belt, #layer7_pouch, #layer8_held {
        animation: song_breath 3.6s ease-in-out infinite;
        transform-origin: 405px 715px;
      }
      #layer2_face .eyes_pupil, #layer2_face .eye_opening {
        animation: song_blink 4.2s ease-in-out infinite;
        transform-origin: 405px 285px;
      }
      #layer9_futou {
        animation: song_futou_wing 4.5s ease-in-out infinite;
        transform-origin: 405px 225px;
      }
    </style>
'''
        # 插入到 </defs> 之前
        if "</defs>" in base_svg:
            animated_svg = base_svg.replace("</defs>", f"{css_animation}  </defs>")
        else:
            animated_svg = base_svg.replace("<svg", f"<svg\n<defs>{css_animation}</defs>")

        return animated_svg

    def render_to_file(self, file_path: str, animated: bool = True) -> str:
        """渲染立绘并保存至指定文件。"""
        svg_content = self.render_svg(animated=animated)
        svg_path = file_path if file_path.endswith(".svg") else file_path.rsplit(".", 1)[0] + ".svg"
        os.makedirs(os.path.dirname(os.path.abspath(svg_path)), exist_ok=True)
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        return svg_path
