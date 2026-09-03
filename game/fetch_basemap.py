# -*- coding: utf-8 -*-
"""下载舆图底图数据（Natural Earth 矢量+栅格、DataV 政区），存 assets/map/raw/。

产物：
    ne_50m_land.geojson                    陆地/海岸线
    ne_50m_rivers_lake_centerlines.geojson 河流中线
    ne_50m_lakes.geojson                   湖泊
    NE2_50M_SR_W.*                         分层设色+晕渲栅格（从 zip 解出）
    datav_100000_all.json / _full.json     DataV 全国政区（地级/省级）
"""
import os
import zipfile
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "assets", "map", "raw")
os.makedirs(RAW, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Songzuo basemap fetcher)"}

GH = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
CDN = "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/"
FILES = {
    "ne_50m_land.geojson": [GH + "ne_50m_land.geojson",
                            CDN + "ne_50m_land.geojson"],
    "ne_50m_rivers_lake_centerlines.geojson": [
        GH + "ne_50m_rivers_lake_centerlines.geojson",
        CDN + "ne_50m_rivers_lake_centerlines.geojson"],
    "ne_50m_lakes.geojson": [GH + "ne_50m_lakes.geojson",
                             CDN + "ne_50m_lakes.geojson"],
    "ne_10m_rivers_lake_centerlines.geojson": [
        GH + "ne_10m_rivers_lake_centerlines.geojson",
        CDN + "ne_10m_rivers_lake_centerlines.geojson"],
    "ne_10m_lakes.geojson": [GH + "ne_10m_lakes.geojson",
                             CDN + "ne_10m_lakes.geojson"],
    "datav_100000_full.json": [
        "http://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"],
}

# 地级政区：逐省 _full（100000_all 不存在，404 实测）
PROVINCES = [
    "110000", "120000", "130000", "140000", "150000", "210000", "220000",
    "230000", "310000", "320000", "330000", "340000", "350000", "360000",
    "370000", "410000", "420000", "430000", "440000", "450000", "460000",
    "500000", "510000", "520000", "530000", "540000", "610000", "620000",
    "630000", "640000", "650000", "710000", "810000", "820000",
]


def fetch(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


for name, urls in FILES.items():
    dest = os.path.join(RAW, name)
    if os.path.isfile(dest) and os.path.getsize(dest) > 1024:
        print("skip", name, os.path.getsize(dest))
        continue
    ok = False
    for u in urls:
        try:
            data = fetch(u)
            with open(dest, "wb") as f:
                f.write(data)
            print("ok", name, len(data))
            ok = True
            break
        except Exception as e:
            print("fail", name, repr(e))
    if not ok:
        print("MISS", name)

zipp = os.path.join(RAW, "NE2_50M_SR_W.zip")
if os.path.isfile(zipp):
    with zipfile.ZipFile(zipp) as z:
        for n in z.namelist():
            if n.lower().endswith((".tif", ".jpg", ".png", ".prj")):
                out = os.path.join(RAW, os.path.basename(n))
                with open(out, "wb") as f:
                    f.write(z.read(n))
                print("unzip", os.path.basename(n), z.getinfo(n).file_size)

for ad in PROVINCES:
    name = f"datav_{ad}_full.json"
    dest = os.path.join(RAW, name)
    if os.path.isfile(dest) and os.path.getsize(dest) > 1024:
        continue
    try:
        data = fetch(f"http://geo.datav.aliyun.com/areas_v3/bound/{ad}_full.json")
        with open(dest, "wb") as f:
            f.write(data)
        print("ok", name, len(data))
    except Exception as e:
        print("fail", name, repr(e))

try:
    import PIL
    print("PIL", PIL.__version__)
except Exception as e:
    print("PIL missing:", repr(e))
