# -*- coding: utf-8 -*-
"""抓取 ESRI World Hillshade 地形晕渲瓦片到 assets/map/web/tiles/hill/{z}/{x}/{y}.png。

覆盖范围：lon 45-150, lat -12-56（= MAP_VIEW 全视野），z5-z7。
ESRI 瓦片 URL 模式：/tile/{z}/{y}/{x}（注意 y 在前）。
"""
import math
import os
import concurrent.futures as cf
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BASE, "assets", "map", "web")
OUT = os.path.join(WEB, "tiles", "hill")
UA = {"User-Agent": "Mozilla/5.0 (Songzuo basemap fetcher)"}

LON0, LON1, LAT0, LAT1 = 45.0, 150.0, -12.0, 56.0
ZOOMS = [5, 6, 7]


def lonlat_to_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    rad = math.radians(lat)
    y = (1.0 - math.log(math.tan(rad) + 1.0 / math.cos(rad)) / math.pi) / 2.0 * n
    return x, y


def tile_range(z):
    x0, y1 = lonlat_to_xy(LON0, LAT0, z)   # 西南角 → x0, y 大
    x1, y0 = lonlat_to_xy(LON1, LAT1, z)   # 东北角 → x1, y 小
    return (int(x0), int(x1), int(y0), int(y1))


def fetch_tile(z, x, y):
    dest = os.path.join(OUT, str(z), str(x), f"{y}.png")
    if os.path.isfile(dest) and os.path.getsize(dest) > 200:
        return "skip"
    url = (f"https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/"
           f"World_Hillshade/MapServer/tile/{z}/{y}/{x}")
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) < 200:
            return f"empty {z}/{x}/{y}"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        return "ok"
    except Exception as e:
        return f"fail {z}/{x}/{y} {e!r}"


jobs = []
for z in ZOOMS:
    x0, x1, y0, y1 = tile_range(z)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            jobs.append((z, x, y))
print("tiles:", len(jobs))

ok = fail = skip = 0
with cf.ThreadPoolExecutor(max_workers=10) as ex:
    for r in ex.map(lambda j: fetch_tile(*j), jobs):
        if r == "ok":
            ok += 1
        elif r == "skip":
            skip += 1
        else:
            fail += 1
            if fail <= 5:
                print(r)
print(f"ok={ok} skip={skip} fail={fail}")
