# -*- coding: utf-8 -*-
"""北宋官员膝盖以上大半身（Knee-up，7头身）标准布娃娃装配烘焙器。

规格：
- 画幅：810 × 1080 (3:4)
- 构图：头顶到膝盖，7头身宋画比例
- 骨骼锚点：
  - Headwear Mount: (405, 215)
  - Chin / Beard: (405, 260)
  - Collar: (405, 310)
  - Chest / Hands: (405, 480)
  - Waist: y = 650
  - Knees: y = 1000
"""
from __future__ import annotations

import os
import numpy as np
from PIL import Image, ImageFilter

TARGET_W, TARGET_H = 810, 1080


def extract_white_alpha(img: Image.Image, threshold: float = 20.0, blur: float = 1.0) -> Image.Image:
    raw = img.convert("RGB")
    arr = np.array(raw, dtype=np.float32)
    diff = np.sqrt(np.sum((255.0 - arr) ** 2, axis=2))
    alpha = np.clip((diff - threshold) / 25.0, 0.0, 1.0) * 255.0
    alpha_img = Image.fromarray(alpha.astype(np.uint8), mode="L")
    if blur > 0:
        alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(blur))
    rgba = raw.convert("RGBA")
    rgba.putalpha(alpha_img)
    return rgba


def crop_active(rgba: Image.Image) -> Image.Image:
    bbox = rgba.getbbox()
    return rgba.crop(bbox) if bbox else rgba
