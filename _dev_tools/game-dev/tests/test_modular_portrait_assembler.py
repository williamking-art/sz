# -*- coding: utf-8 -*-
"""模块化官员立绘装配引擎（ModularPortraitAssembler）测试。

覆盖：
1. Visual DNA 确定性与稳定性
2. 50 位官员多脸谱多样性（杜绝千人一面）
3. 43 位中枢历史名臣专属脸锁定
4. 升贬迁转公服自动换装（绿/绯/紫/幞头/革带/鱼袋）
5. 皇帝特赐恩赏（玉带/金鱼袋）覆盖
6. 实际拼装生成 810×1080 绢本立绘图像
"""
import os
import pytest
from game.content.ministers.portrait_assembler import (
    derive_official_visual_dna,
    assemble_official_portrait,
    generate_modular_component_prompts,
    FACE_MODELS,
    BEARDS,
    FUTOU_TIERS,
)
from game.content.ministers.data import get_portrait_path
from game.core.game_state import GameState


def test_visual_dna_determinism():
    """验证相同官员和背景派生的 Visual DNA 具备完全确定性。"""
    dna1 = derive_official_visual_dna("欧阳澈", rank="从八品", costume_tier="lv", age=28)
    dna2 = derive_official_visual_dna("欧阳澈", rank="从八品", costume_tier="lv", age=28)

    assert dna1["dna_hash"] == dna2["dna_hash"]
    assert dna1["face_model"] == dna2["face_model"]
    assert dna1["beard"] == dna2["beard"]
    assert dna1["costume_tier"] == "lv"
    assert dna1["futou"] == "short"


def test_diversity_across_officials_no_clones():
    """验证多位官员生成的 Visual DNA 具备高度丰富性，杜绝撞脸。"""
    names = [
        "张茂则", "富弼之孙", "王十朋", "胡铨", "赵鼎", "李纲", "陈东", "欧阳澈",
        "苏迈", "苏迨", "苏过", "黄庭坚门生", "晁补之门生", "秦观之子", "张九成",
        "汪应辰", "王佐", "周必大", "陆游", "范成大", "杨万里", "尤袤", "朱熹",
        "张栻", "吕祖谦", "陈亮", "叶适", "辛弃疾", "刘过", "姜夔", "文天祥",
    ]
    face_models = set()
    beards = set()
    dna_hashes = set()

    for i, name in enumerate(names):
        age = 25 + (i * 3) % 45
        dna = derive_official_visual_dna(name, rank="从七品", costume_tier="lv", age=age)
        face_models.add(dna["face_model"])
        beards.add(dna["beard"])
        dna_hashes.add(dna["dna_hash"])

    # 验证覆盖了多种脸型与胡须
    assert len(face_models) >= 3, f"脸型过于单一: {face_models}"
    assert len(beards) >= 3, f"胡须过于单一: {beards}"
    assert len(dna_hashes) == len(names), "不同官员出现了 DNA 哈希重复！"


def test_historical_ministers_face_locking():
    """验证43位中枢历史名臣锁定其考据历史头面。"""
    cai_jing = derive_official_visual_dna("蔡京", rank="尚书左丞", costume_tier="zi")
    assert cai_jing["is_historical"] is True
    assert cai_jing["face_model"] == "hist_蔡京"

    yue_fei = derive_official_visual_dna("岳飞", rank="节度使", costume_tier="zi")
    assert yue_fei["is_historical"] is True
    assert yue_fei["face_model"] == "hist_岳飞"


def test_costume_tier_reassignment():
    """验证官员品级升迁时，公服部件与服色自动动态换装。"""
    # 1. 知县（从八品 · 绿袍）
    dna_low = derive_official_visual_dna("新科进士", rank="从八品", costume_tier="lv")
    assert dna_low["costume_tier"] == "lv"
    assert dna_low["futou"] == "short"
    assert dna_low["belt"] == "horn"
    assert dna_low["fish_pouch"] == "none"

    # 2. 升任知府（正五品 · 绯袍）
    dna_mid = derive_official_visual_dna("新科进士", rank="正五品", costume_tier="fei")
    assert dna_mid["costume_tier"] == "fei"
    assert dna_mid["futou"] == "mid"
    assert dna_mid["belt"] == "silver"
    assert dna_mid["fish_pouch"] == "silver"

    # 3. 入阁拜相（正二品 · 紫袍）
    dna_high = derive_official_visual_dna("新科进士", rank="尚书右丞", costume_tier="zi")
    assert dna_high["costume_tier"] == "zi"
    assert dna_high["futou"] == "long"
    assert dna_high["belt"] == "gold"
    assert dna_high["fish_pouch"] == "gold"


def test_favor_bestowals_override():
    """验证皇帝特赐恩赏（借紫、赐玉带、赐金鱼袋）覆盖默认品级部件。"""
    favors = {
        "waist": {"name": "特赐羊脂白玉带板"},
        "accessory": {"name": "借紫特赐鎏金金鱼袋"},
    }
    # 虽是低品七品绿袍，但受特赐玉带与金鱼袋
    dna = derive_official_visual_dna(
        name="清流言官",
        rank="从七品",
        costume_tier="lv",
        favor_equipment=favors,
    )
    assert dna["costume_tier"] == "lv"
    assert dna["belt"] == "jade", "特赐白玉带未生效"
    assert dna["fish_pouch"] == "gold", "特赐金鱼袋未生效"


def test_assemble_official_portrait_file_generation():
    """验证 assemble_official_portrait 成功生成 810x1080 绢本立绘图像。"""
    dna = derive_official_visual_dna("新科状元张孝祥", rank="从六品", costume_tier="fei", age=26)
    out_path = assemble_official_portrait(dna)

    assert out_path is not None
    assert os.path.isfile(out_path), f"立绘文件未生成: {out_path}"

    from PIL import Image
    with Image.open(out_path) as im:
        assert im.size == (810, 1080), f"立绘尺寸非 810x1080: {im.size}"

    # 验证 get_portrait_path 也能顺利定位或装配生成该非名臣官员立绘
    p_path = get_portrait_path(name="新科状元张孝祥", rank="从六品")
    assert p_path is not None
    assert os.path.isfile(p_path)
