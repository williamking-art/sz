"""分层立绘抽查：用游戏实际合成代码渲染抽样表，肉眼复核残留/色差。

新增大臣后把名字加进 names 即可；产物落在本目录 _verify.png（不进游戏资源）。
"""
import os
import sys

_GAME = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "..", ".."))
sys.path.insert(0, _GAME)
from PIL import Image           # noqa: E402
from content.ministers import data as D   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verify.png")
names = ["陈瓘", "蔡京", "童贯", "曾布", "李纲", "高俅", "赵桓", "张叔夜", "韩世忠", "余深"]
box = (40, 30, 770, 580)
w, h = box[2] - box[0], box[3] - box[1]
sheet = Image.new("RGB", (w * 2 + 30, h * 5 + 40), (90, 90, 90))
for i, n in enumerate(names):
    t = D.minister_tier(n)
    p = D.minister_pose(n)
    f = D.compose_portrait(n, t, p)
    im = Image.open(f).convert("RGB").crop(box)
    sheet.paste(im, ((i % 2) * (w + 10), (i // 2) * (h + 10)))
sheet.resize((sheet.size[0] // 2, sheet.size[1] // 2)).save(OUT)
print("ok")
