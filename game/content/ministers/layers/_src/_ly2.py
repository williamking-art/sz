import os
import numpy as np
from PIL import Image

H, W = 1080, 810
CUT, FE = 0.40, 0.06
# 路径自 __file__ 推导（原为硬编码 g:\sz\...）
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../layers
PD = os.path.join(os.path.dirname(D), "portraits")                # .../ministers/portraits
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
