# -*- coding: utf-8 -*-
# ⚠️ **已废弃**（2026-09-22）：旧版净身脚本，会覆盖 _lay2.py 权威产物。禁止运行。
import os, numpy as np
from PIL import Image, ImageFilter


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
# 改为从仓库根定位；__main__ 独立运行时产物仍写回运行时 layers 目录）
L = os.path.join(_repo_root(), "game", "content", "ministers", "layers")
PO=["zheng","gongshou","chihu","longxiu"]
TI=["zi","fei","lv","qing","shi","qinwang"]
H,W=1080,810
TOL=26.0
def clean(im):
    a=im.astype(np.float32)
    js=np.concatenate([a[:30,:30].reshape(-1,3),a[:30,-30:].reshape(-1,3),
                       a[-30:,:30].reshape(-1,3),a[-30:,-30:].reshape(-1,3)])
    bgc=np.median(js,0)
    d=np.sqrt(((a-bgc)**2).sum(2))
    y=np.arange(H)[:,None]
    x=np.arange(W)[None,:]
    sat=a.max(2)-a.min(2); lum=a.mean(2)
    fg=(d>=TOL)
    up=fg&(y<int(0.36*H))
    low=fg&(y>=int(0.36*H))&(y<int(0.45*H))&(x>=int(0.22*W))&(x<=int(0.78*W))
    m=(up|low).astype(np.float32)
    m=np.array(Image.fromarray((m*255).astype("uint8")).filter(
        ImageFilter.MaxFilter(25)).filter(ImageFilter.GaussianBlur(9)),dtype=np.float32)/255.0
    l=a[:,2:8].mean(1); r=a[:,W-8:W-2].mean(1)
    xs=np.linspace(0,1,W)[None,:,None]
    base=l[:,None,:]*(1-xs)+r[:,None,:]*xs
    fill=a.copy()
    for yy in range(H):
        rm=m[yy]>0.02
        if not rm.any(): continue
        idx=np.nonzero(rm)[0]; xa,xb=int(idx[0]),int(idx[-1])
        if xa<2 or xb>W-3: continue
        n=xb-xa+1
        lsq=a[yy,np.clip(np.arange(xa-1,xa-1-n,-1),0,W-1)]
        rsq=a[yy,np.clip(np.arange(xb+1,xb+1+n),0,W-1)][::-1]
        w=np.linspace(0,1,n)[:,None]
        fill[yy,xa:xb+1]=lsq*(1-w)+rsq*w
    out=a*(1-m[...,None])+fill*m[...,None]
    return out
if __name__=="__main__":
    for p in PO:
        for t in TI:
            f=f"{L}\\body_{p}_{t}.png"
            im=np.array(Image.open(f).convert("RGB"))
            Image.fromarray(np.clip(clean(im),0,255).astype("uint8"),"RGB").save(f)
            print(p,t,flush=True)
