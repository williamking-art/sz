import os
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

H, W = 1080, 810


def _repo_root() -> str:
    """向上找仓库根（含 game/content/ministers 的目录），避免硬编码相对层级数。"""
    p = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(p, "game", "content", "ministers")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            raise RuntimeError("未找到仓库根（应含 game/content/ministers 目录）")
        p = parent


# 路径自 __file__ 推导（原为硬编码 g:\sz\...；2026-09-26 随工具链迁出 game/content/ 后
# 改为从仓库根定位，产物仍写/读运行时 layers 目录）
_ROOT = _repo_root()
D = os.path.join(_ROOT, "game", "content", "ministers", "layers")
PD = os.path.join(_ROOT, "game", "content", "ministers", "portraits")
CUT, FE = 0.62, 0.18
TOL = 28.0

y = np.arange(H)[:, None]
fade = np.clip((CUT * H - y) / (FE * H), 0, 1)


def load(fn):
    im = Image.open(os.path.join(PD, fn)).convert("RGB").resize((W, H), Image.LANCZOS)
    pad = max(4, int(W * 0.02))
    l = im.crop((pad, 0, pad + 1, H)).resize((pad, H), Image.NEAREST)
    r = im.crop((W - pad - 1, 0, W - pad, H)).resize((pad, H), Image.NEAREST)
    im.paste(l, (0, 0))
    im.paste(r, (W - pad, 0))
    return im


def clean_alpha(im):
    a = np.array(im).astype(np.float32)
    c = np.concatenate([a[0:40, 0:40].reshape(-1, 3), a[0:40, -40:].reshape(-1, 3),
                        a[-40:, 0:40].reshape(-1, 3), a[-40:, -40:].reshape(-1, 3)])
    bg = np.median(c, axis=0)
    d = np.sqrt(((a - bg) ** 2).sum(axis=2))
    fg = d >= TOL
    lab, n = ndimage.label(fg)
    if n == 0:
        return np.zeros((H, W), np.float32)
    # 选含头心的连通域（头部集中在中央上区），否则退化为最大连通域
    hy, hx = int(0.18 * H), int(0.5 * W)
    band = lab[max(0, hy - 60):hy + 60, max(0, hx - 120):hx + 120]
    cand = band[band > 0]
    if cand.size:
        vals, cnts = np.unique(cand, return_counts=True)
        target = int(vals[np.argmax(cnts)])
    else:
        sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        target = int(np.argmax(sizes)) + 1
    keep = (lab == target)
    keep = ndimage.binary_fill_holes(keep)
    return keep.astype(np.float32)


def run(names):
    for name in names:
        fn = name + ".png"
        im = load(fn)
        m = clean_alpha(im)
        alpha = (m * fade * 255).astype("uint8")
        am = Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(3.5))
        core = ndimage.binary_erosion(m > 0.5, iterations=2)
        aa = np.maximum(np.array(am).astype(np.float32), core * fade * 255)
        am2 = Image.fromarray(aa.astype("uint8"), "L")
        Image.merge("RGBA", (*im.split(), am2)).save(os.path.join(D, "head_%s.png" % name))
        print("head", name, flush=True)


if __name__ == "__main__":
    import sys
    names = sys.argv[1:]
    if not names:
        names = [f[:-4] for f in sorted(os.listdir(PD)) if f.endswith(".png")]
    run(names)
