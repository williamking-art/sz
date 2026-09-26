import os
import numpy as np
from PIL import Image

H, W = 1080, 810
CUT, FE = 0.40, 0.06
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
# 改为从仓库根定位，产物仍写回运行时 layers 目录）
_ROOT = _repo_root()
D = os.path.join(_ROOT, "game", "content", "ministers", "layers")
PD = os.path.join(_ROOT, "game", "content", "ministers", "portraits")
y = np.arange(H)[:, None]
A = np.repeat(np.clip((y - (CUT - FE) * H) / (FE * H), 0, 1), W, axis=1)
B8 = ((1 - A) * 255).astype("uint8")
n = 0
for fn in sorted(os.listdir(PD)):
    if not fn.endswith(".png"):
        continue
    name = fn[:-4]
    im = Image.open(os.path.join(PD, fn)).convert("RGB").resize((W, H), Image.LANCZOS)
    pad = max(4, int(W * 0.02))
    left = im.crop((pad, 0, pad + 1, H)).resize((pad, H), Image.NEAREST)
    right = im.crop((W - pad - 1, 0, W - pad, H)).resize((pad, H), Image.NEAREST)
    im.paste(left, (0, 0))
    im.paste(right, (W - pad, 0))
    rgba = np.dstack([np.array(im), B8])
    Image.fromarray(rgba, "RGBA").save(os.path.join(D, "head_%s.png" % name))
    n += 1
print("heads:", n)
