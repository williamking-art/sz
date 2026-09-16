import json
import os
import numpy as np
from PIL import Image

SRC = r"g:\sz\game\content\ministers\layers\_src"
DST = r"g:\sz\game\content\ministers\layers"
H, W = 1080, 810
CUT, FE = 0.40, 0.06
POSES = ["zheng", "gongshou", "chihu", "longxiu"]
TIERS = ["zi", "fei", "lv", "qing", "shi", "qinwang"]


def src_path(pose, tier):
    if pose == "zheng":
        return os.path.join(SRC, "_base_%s.png" % tier)
    if tier == "zi":
        return os.path.join(SRC, "_pose_%s.png" % pose)
    return os.path.join(SRC, "_pose_%s_%s.png" % (pose, tier))


def load(pose, tier):
    """读图统一尺寸，并用邻近列延展覆盖左右边缘条带（消 AI 输出边缘伪影）。"""
    im = Image.open(src_path(pose, tier)).convert("RGB").resize((W, H), Image.LANCZOS)
    pad = max(4, int(W * 0.015))
    left = im.crop((pad, 0, pad + 1, H)).resize((pad, H), Image.NEAREST)
    right = im.crop((W - pad - 1, 0, W - pad, H)).resize((pad, H), Image.NEAREST)
    im.paste(left, (0, 0))
    im.paste(right, (W - pad, 0))
    return im


def head_center(im):
    a = np.array(im.convert("L").resize((W, H)))
    y0, y1 = int(0.04 * H), int(0.30 * H)
    band = a[y0:y1]
    mask = band < 95
    if mask.sum() == 0:
        return (W / 2.0, (y0 + y1) / 2.0)
    ys, xs = np.nonzero(mask)
    return (float(xs.mean()), float(ys.mean()) + y0)


y = np.arange(H)[:, None]
A = np.repeat(np.clip((y - (CUT - FE) * H) / (FE * H), 0, 1), W, axis=1)
A8 = (A * 255).astype("uint8")
B8 = ((1 - A) * 255).astype("uint8")

base_c = None
offsets = {}
for pose in POSES:
    for tier in TIERS:
        im = load(pose, tier)
        if pose == "zheng" and tier == "zi":
            base_c = head_center(im)
        if tier == "zi":
            offsets[pose] = head_center(im)
        rgba = np.dstack([np.array(im), A8])
        Image.fromarray(rgba, "RGBA").save(
            os.path.join(DST, "body_%s_%s.png" % (pose, tier)))
    print("pose done", pose, flush=True)

json.dump({p: [round(offsets[p][0] - base_c[0], 2),
               round(offsets[p][1] - base_c[1], 2)] for p in POSES},
          open(os.path.join(DST, "_offsets.json"), "w"))
print("offsets", {p: [round(offsets[p][0] - base_c[0]), round(offsets[p][1] - base_c[1])] for p in POSES})
