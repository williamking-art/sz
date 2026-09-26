# -*- coding: utf-8 -*-
"""分层立绘生成管线（唯一权威入口，顺序不可颠倒）。

  1) 官服层：_src/{_base_*, _pose_*} → layers/body_{pose}_{tier}.png
     全部不透明，绢底背景由官服层提供（头部层背景透明，叠在其上）。
  2) 姿态对齐：从「未净身」的官服层测头部质心，写入 layers/_offsets.json
     （必须早于第 3 步：净身后头部不存在，无法测质心）。
  3) 官服层净身：擦掉官服层自带的头/帽/帽翅并补绢底（_src/_bodyclean.py）。
     官服层本身画有头与幞头，而头部层是另画的头像；两者帽形不同，若不擦除
     会错位重叠成「双帽 / 帽翅残留」（拱手姿态下最明显）。
  4) 头部层：portraits/*.png → layers/head_*.png（连通域抠图 + 底部渐出）。
     旧版全局阈值会把绢底纹理留成半透明 ghost，并让细薄的幞头翅发虚。

新增大臣只需：把立绘放入 game/content/ministers/portraits/{名}.png，再跑本脚本即可有机融入。

本脚本与 _src/ 于 2026-09-26 从 game/content/ministers/layers/ 迁至
_dev_tools/game-assets-src/ministers-layers/（分层纪律：开发脚本不驻运行时内容目录），
产物仍写回 game/content/ministers/layers/。
"""
import importlib.util
import os
import json
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))          # .../ministers-layers（工具链目录）
SRC = os.path.join(HERE, "_src")


def _repo_root() -> str:
    """向上找仓库根（含 game/content/ministers 的目录），避免硬编码相对层级数。"""
    p = HERE
    while True:
        if os.path.isdir(os.path.join(p, "game", "content", "ministers")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            raise RuntimeError("未找到仓库根（应含 game/content/ministers 目录）")
        p = parent


_ROOT = _repo_root()
# 产物落运行时图层目录（2026-09-26 起工具链迁出 game/content/，但产物仍写回那里）
LAYERS = os.path.join(_ROOT, "game", "content", "ministers", "layers")
PORTRAITS = os.path.join(_ROOT, "game", "content", "ministers", "portraits")
H, W = 1080, 810
POSES = ["zheng", "gongshou", "chihu", "longxiu"]
TIERS = ["zi", "fei", "lv", "qing", "shi", "qinwang"]


def _load(tag, fname):
    path = os.path.join(SRC, fname)
    spec = importlib.util.spec_from_file_location(tag, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def src_path(pose, tier):
    if pose == "zheng":
        return os.path.join(SRC, "_base_%s.png" % tier)
    if tier == "zi":
        return os.path.join(SRC, "_pose_%s.png" % pose)
    return os.path.join(SRC, "_pose_%s_%s.png" % (pose, tier))


def load(pose, tier):
    """读图统一尺寸，并用邻近列延展覆盖左右边缘条带（消 AI 输出边缘伪影）。"""
    im = Image.open(src_path(pose, tier)).convert("RGB").resize((W, H), Image.LANCZOS)
    pad = max(4, int(W * 0.02))
    l = im.crop((pad, 0, pad + 1, H)).resize((pad, H), Image.NEAREST)
    r = im.crop((W - pad - 1, 0, W - pad, H)).resize((pad, H), Image.NEAREST)
    im.paste(l, (0, 0))
    im.paste(r, (W - pad, 0))
    return im


def head_center(im):
    """头部质心：取上部暗区（冠/发/面）质心，用于跨姿态对位。"""
    a = np.array(im.convert("L").resize((W, H)))
    y0, y1 = int(0.04 * H), int(0.30 * H)
    band = a[y0:y1]
    mask = band < 95
    if mask.sum() == 0:
        return (W / 2.0, (y0 + y1) / 2.0)
    ys, xs = np.nonzero(mask)
    return (float(xs.mean()), float(ys.mean()) + y0)


def gen_bodies():
    """第 1 步：生成全不透明官服层。"""
    for pose in POSES:
        for tier in TIERS:
            im = load(pose, tier)
            alpha = Image.new("L", (W, H), 255)
            Image.merge("RGBA", (*im.split(), alpha)).save(
                os.path.join(LAYERS, "body_%s_%s.png" % (pose, tier)))
        print("body", pose, flush=True)


def gen_offsets():
    """第 2 步：测各姿态头部质心相对正立版的偏移。"""
    base = head_center(load("zheng", "zi"))
    off = {}
    for pose in POSES:
        c = head_center(load(pose, "zi"))
        off[pose] = [round(c[0] - base[0], 2), round(c[1] - base[1], 2)]
    with open(os.path.join(LAYERS, "_offsets.json"), "w", encoding="utf-8") as f:
        json.dump(off, f)
    print("offsets", off, flush=True)


def clean_bodies():
    """第 3 步：擦除官服层自带头/帽/帽翅并补绢底。"""
    mod = _load("_bodyclean", "_bodyclean.py")
    for pose in POSES:
        for tier in TIERS:
            f = os.path.join(LAYERS, "body_%s_%s.png" % (pose, tier))
            im = np.array(Image.open(f).convert("RGB"))
            Image.fromarray(np.clip(mod.clean(im), 0, 255).astype("uint8"),
                            "RGB").save(f)
        print("clean", pose, flush=True)


def gen_heads():
    """第 4 步：从 portraits/ 抠头部层。"""
    mod = _load("_headcut", "_headcut.py")
    names = [f[:-4] for f in sorted(os.listdir(PORTRAITS)) if f.endswith(".png")]
    mod.run(names)


if __name__ == "__main__":
    gen_bodies()
    gen_offsets()
    clean_bodies()
    gen_heads()
    print("done")
