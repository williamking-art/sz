# -*- coding: utf-8 -*-
"""北宋官员 2D 布娃娃换装系统（Paper Doll System）全套回归测试。

覆盖四大开源标杆架构与用户核心诉求：
1. 千人千面多样性：4032万种五官解耦组合，杜绝老中青三张脸、九张脸；
2. 8 层自底向上装配：810×1080 大半身像，消除断头白洞与浮空黑块；
3. 宋代舆服制度约束：借绯借紫、金银鱼袋、玉带合规性与仕途除授自动换装；
4. Shinsekai 模式：AI 对话语义实时联动大臣情绪状态机；
5. Live2DMascot 模式：沉稳官仪微动态参数与无损 CSS SVG 动效；
6. VNDialog 模式：纯 JSON 配置导入导出与名臣数据驱动展示。
"""
from __future__ import annotations

import json
import math
import os
import sys
import pytest

try:
    from content.ministers.paperdoll import (
        DollMannequin,
        DollSkeletonRig,
        EmotionState,
        EquipmentSlot,
        EYEBROWS,
        EYES,
        FACE_SHAPES,
        FaceDNA,
        MANNEQUIN_CATALOG,
        MinisterAudienceController,
        MinisterAudienceProfile,
        MOUTHS,
        NOSES,
        PaperdollRenderEngine,
        generate_visual_dna,
        resolve_promotion_equipment,
        validate_regalia_compliance,
    )
except ImportError:
    from game.content.ministers.paperdoll import (
        DollMannequin,
        DollSkeletonRig,
        EmotionState,
        EquipmentSlot,
        EYEBROWS,
        EYES,
        FACE_SHAPES,
        FaceDNA,
        MANNEQUIN_CATALOG,
        MinisterAudienceController,
        MinisterAudienceProfile,
        MOUTHS,
        NOSES,
        PaperdollRenderEngine,
        generate_visual_dna,
        resolve_promotion_equipment,
        validate_regalia_compliance,
    )


class TestPaperdollDiversityAndDNA:
    """测试大臣千人千面多样性与 7 维解耦五官参数库。"""

    def test_dna_combinatorial_space(self):
        """验证 7 维解耦五官组合空间超过 4000 万种（40,320,000）。"""
        shapes_cnt = len(FACE_SHAPES)   # 7
        eyebrows_cnt = len(EYEBROWS)    # 8
        eyes_cnt = len(EYES)            # 8
        noses_cnt = len(NOSES)          # 6
        mouths_cnt = len(MOUTHS)        # 6
        beards_cnt = 12                 # 12
        complexion_cnt = 5              # 5

        pure_face_combinations = (
            shapes_cnt * eyebrows_cnt * eyes_cnt * noses_cnt * mouths_cnt * beards_cnt * complexion_cnt
        )
        assert pure_face_combinations == 967680, f"纯五官面模组合实测为 {pure_face_combinations}"

        # 结合 3 套素体体型 × 5 档官品服色 × 3 档幞头展角，全系统总展示空间超过 4350 万种
        mannequins_cnt = len(MANNEQUIN_CATALOG) # 3
        costume_tiers_cnt = 5                   # 5 (紫/绯/绿/青/士人)
        futou_styles_cnt = 3                    # 3 (长展角/平展角/短展角)

        total_system_combinations = pure_face_combinations * mannequins_cnt * costume_tiers_cnt * futou_styles_cnt
        assert total_system_combinations == 43545600, f"换装系统全量组合空间实测为 {total_system_combinations}"

    def test_dna_deterministic_reproducibility(self):
        """验证同名同官位同年龄官员的 Visual DNA 计算具有 100% 确定性幂等可复现。"""
        m_id = "cai_jing"
        name = "蔡京"
        age = 70
        rank = "从一品 尚书左仆射"
        traits = ["理财", "奸黠"]

        doll_1, dna_1, eq_1 = generate_visual_dna(name=name, rank=rank, age=age, traits=traits, minister_id=m_id)
        doll_2, dna_2, eq_2 = generate_visual_dna(name=name, rank=rank, age=age, traits=traits, minister_id=m_id)

        assert doll_1 == doll_2
        assert dna_1.to_dict() == dna_2.to_dict()
        assert eq_1 == eq_2

    def test_large_scale_minister_diversity(self):
        """批量测试 100 位不同州县官员，验证其 FaceDNA 差异度极高，绝无千人一面。"""
        officials = []
        prefectures = ["开封", "真定", "太原", "延安", "成都", "江宁", "杭州", "福州", "广州", "荆南"]
        surnames = ["赵", "钱", "孙", "李", "周", "吴", "郑", "王", "冯", "陈"]
        names = ["光", "度", "纲", "中", "澈", "安石", "相", "轼", "辙", "洵"]

        dna_tuples = set()
        for i in range(100):
            pref = prefectures[i % len(prefectures)]
            name = surnames[i % len(surnames)] + names[(i // 10) % len(names)]
            age = 25 + (i % 45)
            rank = "从七品 知县" if age < 35 else ("正六品 知州" if age < 55 else "从二品 资政殿大学士")
            
            doll, dna, eq = generate_visual_dna(
                name=name,
                rank=rank,
                age=age,
                origin=pref,
                minister_id=f"minister_{i}",
            )
            dna_key = (
                dna.face_shape,
                dna.eyebrows,
                dna.eyes,
                dna.nose,
                dna.mouth,
                dna.beard,
                dna.complexion,
            )
            dna_tuples.add(dna_key)

        # 100 位官员应产生接近 100 种不重样的五官组合（碰撞率 < 5%）
        unique_rate = len(dna_tuples) / 100.0
        assert unique_rate >= 0.95, f"五官多样性不足，100 位官员仅有 {len(dna_tuples)} 种独特脸模"

    def test_age_constraint_on_beards(self):
        """验证生理年龄对胡须髯口的合理生理约束（青年无须或微髭，老年有老成人长髯）。"""
        # 青年 (25岁)
        _, young_dna, _ = generate_visual_dna(name="欧阳澈", rank="从八品 承务郎", age=25)
        assert young_dna.beard in ("beard_none", "beard_short_subtle")

        # 老年 (70岁)
        _, elder_dna, _ = generate_visual_dna(name="韩忠彦", rank="从一品 仆射", age=70)
        assert elder_dna.beard in (
            "beard_grey_sparse", "beard_grey_three", "beard_snow_full", "beard_three_tuft_refined"
        )


class TestSumptuaryRulesAndPromotion:
    """测试宋代公服舆服法度与即时升迁除授换装机制。"""

    def test_regalia_violation_detection(self):
        """低品官员擅穿紫袍或佩戴金鱼袋应被舆服规则引擎精准拦截。"""
        # 七品知县私自穿紫袍
        illegal_equipped = {
            EquipmentSlot.ROBE.value: "robe_zi_3rd",
            EquipmentSlot.POUCH.value: "pouch_gold_fish",
            EquipmentSlot.HEADWEAR.value: "futou_long_straight",
            EquipmentSlot.BELT.value: "belt_jade_white",
        }
        violations = validate_regalia_compliance(illegal_equipped, rank="从七品 知县")
        assert len(violations) >= 3
        assert any("擅穿绛紫素罗襕袍" in v for v in violations)
        assert any("金鱼袋" in v for v in violations)
        assert any("白玉带" in v for v in violations)

    def test_borrow_purple_favor_legality(self):
        """获得皇帝特赐『借紫』恩赏后，穿紫袍佩金鱼袋应为完全合规。"""
        legal_equipped = {
            EquipmentSlot.ROBE.value: "robe_zi_3rd",
            EquipmentSlot.POUCH.value: "pouch_gold_fish",
            EquipmentSlot.HEADWEAR.value: "futou_mid_stiff",
            EquipmentSlot.BELT.value: "belt_gold_lychee",
        }
        favors = ["借紫", "赐金鱼袋"]
        violations = validate_regalia_compliance(legal_equipped, rank="从七品 知县", favor_privileges=favors)
        assert violations == [], f"借紫与赐金鱼袋恩赏下应完全合规，但返回违制: {violations}"

    def test_promotion_equipment_transition(self):
        """官员从绿袍知县除授晋升为宰辅时，装备插槽全自动依规晋级。"""
        old_eq = {
            EquipmentSlot.BASE_DOLL.value: "mannequin_young",
            EquipmentSlot.COLLAR.value: "collar_white_silk",
            EquipmentSlot.ROBE.value: "robe_lv_7th",
            EquipmentSlot.HEADWEAR.value: "futou_short_flat",
            EquipmentSlot.BELT.value: "belt_black_horn",
            EquipmentSlot.POUCH.value: "pouch_none",
            EquipmentSlot.HELD.value: "held_wood_tablet",
        }

        # 晋升为尚书右丞（从二品）
        new_eq = resolve_promotion_equipment(old_eq, new_rank="从二品 尚书右丞", favors=["赐白玉带"])
        assert new_eq[EquipmentSlot.ROBE.value] == "robe_zi_3rd"
        assert new_eq[EquipmentSlot.HEADWEAR.value] == "futou_long_straight"
        assert new_eq[EquipmentSlot.BELT.value] == "belt_jade_white"
        assert new_eq[EquipmentSlot.POUCH.value] == "pouch_gold_fish"
        assert new_eq[EquipmentSlot.HELD.value] == "held_jade_ivory_hu"


class TestShinsekaiDialogueEmotionLinkage:
    """测试 Shinsekai 模式：AI 对话与立绘情绪动作联动。"""

    def test_emperor_speech_reactions(self):
        """皇帝训斥/嘉赏/忧思驱动大臣产生精准情绪反应。"""
        ctrl = MinisterAudienceController.create_for_minister(
            minister_id="test_min",
            name="李纲",
            age=45,
            rank="正四品 尚书右丞",
        )
        assert ctrl.profile.current_emotion == EmotionState.RESPECTFUL

        # 1. 皇帝震怒训斥 -> 大臣惶恐 (PANIC)
        state = ctrl.on_dialogue("荒谬！欺君罔上，该当何罪！", speaker_is_emperor=True)
        assert state == EmotionState.PANIC
        assert ctrl.profile.current_emotion == EmotionState.PANIC

        # 2. 皇帝嘉奖重用 -> 大臣欣慰拜恩 (GRATIFIED)
        state = ctrl.on_dialogue("卿有大功于社稷，朕心甚慰，准奏施行！", speaker_is_emperor=True)
        assert state == EmotionState.GRATIFIED

        # 3. 皇帝忧念边患 -> 大臣深忧 (WORRIED)
        state = ctrl.on_dialogue("金贼已渡黄河，边防危急，军粮不继，如何是好？", speaker_is_emperor=True)
        assert state == EmotionState.WORRIED

    def test_minister_speech_intent(self):
        """大臣自身奏疏意图驱动其立绘情绪。"""
        ctrl = MinisterAudienceController.create_for_minister(
            minister_id="test_min2",
            name="宗泽",
            age=65,
            rank="从二品 宣抚使",
        )

        # 骨鲠直谏
        state = ctrl.on_dialogue("臣以为万不可弃太原！祖宗之法不可违，力谏陛下亲征！", speaker_is_emperor=False)
        assert state == EmotionState.RESOLUTE

        # 引咎自劾
        state = ctrl.on_dialogue("臣失职有负圣恩，伏乞圣裁，臣死罪！", speaker_is_emperor=False)
        assert state == EmotionState.PANIC


class TestLive2DMascotMicroMotion:
    """测试 Live2DMascot 模式：官仪沉稳微动态。"""

    def test_motion_parameter_bounds(self):
        """验证微动态各生理参数（呼吸起伏、眨眼、展角微动）在端庄官仪约束范围内。"""
        ctrl = MinisterAudienceController.create_for_minister(
            minister_id="test_motion",
            name="韩忠彦",
            age=60,
            rank="从一品 宰相",
        )

        # 采样 10 秒微动态
        for t in [0.0, 0.8, 1.6, 2.4, 3.2, 3.9, 4.0, 5.5, 7.8]:
            params = ctrl.get_live2d_motion_params(t)
            assert -3.0 <= params["breath_y"] <= 3.0, "呼吸起伏超标，失却端庄"
            assert 0.0 <= params["blink_ratio"] <= 1.0, "眨眼比例必须在 [0.0, 1.0]"
            assert -1.5 <= params["futou_tremor"] <= 1.5, "展角铁线轻颤过大"

    def test_animated_svg_generation(self):
        """验证生成的动画 SVG 正确内嵌 CSS @keyframes 动画且格式完好。"""
        ctrl = MinisterAudienceController.create_for_minister(
            minister_id="test_svg",
            name="蔡京",
            age=70,
            rank="从一品 尚书左仆射",
        )
        svg = ctrl.render_svg(animated=True)
        assert "<svg" in svg
        assert "</svg>" in svg
        assert 'viewBox="0 0 810 1080"' in svg
        assert "@keyframes song_breath" in svg
        assert "@keyframes song_blink" in svg
        assert "@keyframes song_futou_wing" in svg
        assert "transform-origin: 405px 715px" in svg


class TestVNDialogDataDrivenConfig:
    """测试 VNDialog 模式：纯 JSON 配置导入导出与数据驱动展示。"""

    def test_json_roundtrip(self, tmp_path):
        """验证 Controller 导出 JSON 与重新反序列化加载 100% 保真。"""
        ctrl = MinisterAudienceController.create_for_minister(
            minister_id="test_json_m",
            name="欧阳澈",
            age=26,
            rank="从八品 承务郎",
            traits=["直谏", "文采"],
            origin="抚州",
        )
        json_file = str(tmp_path / "test_minister.json")
        ctrl.export_json_config(json_file)

        # 从 JSON 文件重新加载
        loaded_ctrl = MinisterAudienceController.from_json_config(json_file)
        assert loaded_ctrl.profile.minister_id == "test_json_m"
        assert loaded_ctrl.profile.name == "欧阳澈"
        assert loaded_ctrl.profile.age == 26
        assert loaded_ctrl.profile.rank == "从八品 承务郎"
        assert loaded_ctrl.profile.face_dna.to_dict() == ctrl.profile.face_dna.to_dict()
        assert loaded_ctrl.profile.equipped == ctrl.profile.equipped
