# -*- coding: utf-8 -*-
"""外邦州府静态表（2026-10-19 重建：以舆图切分为准）。

来源：辽/西夏/吐蕃/大理 = `content.geo_admin.REGIME_PREFECTURES` 的**实际切分**（县名与数量按舆图）；
      高丽/日本/安南 = 无面数据，仅点名列（史实近似名）。

纪律：
- **不手抄**：前四国由生成脚本从 REGIME_PREFECTURES 导出，改图后重跑脚本即可；
- `pop` 一律 None（缺失≠0），人口由权重分解在后续阶段写入；
- `weight`：首都 1.5 / 要冲 1.2 / 普通 1.0（设定值）；`lonlat` 为 seat_at 或近似坐标。
"""

__all__ = ["REGIME_SEATS", "REGIME_TIER1"]

#: 做 T1（州府级）的七国
REGIME_TIER1 = ("辽", "西夏", "吐蕃", "大理", "高丽", "日本", "安南")

REGIME_SEATS = {
    '辽': {
        '南京道': [
            {"name": '析津府', "kind": "州", "weight": 1.5, "lonlat": [116.4, 39.9]},
            {"name": '平州', "kind": "州", "weight": 1.0, "lonlat": None},
            {"name": '滦州', "kind": "州", "weight": 1.0, "lonlat": None},
        ],
        '西京道': [
            {"name": '大同府', "kind": "州", "weight": 1.5, "lonlat": [113.3, 40.1]},
            {"name": '归化州', "kind": "州", "weight": 1.0, "lonlat": None},
            {"name": '丰州', "kind": "州", "weight": 1.0, "lonlat": None},
            {"name": '云内州', "kind": "州", "weight": 1.0, "lonlat": None},
        ],
        '中京道': [
            {"name": '大定府', "kind": "州", "weight": 1.5, "lonlat": [120.2, 41.6]},
            {"name": '兴中府', "kind": "州", "weight": 1.0, "lonlat": None},
        ],
        '东京道': [
            {"name": '辽阳府', "kind": "州", "weight": 1.5, "lonlat": [123.2, 41.3]},
            {"name": '显州', "kind": "州", "weight": 1.0, "lonlat": None},
            {"name": '辰州', "kind": "州", "weight": 1.0, "lonlat": None},
            {"name": '苏州', "kind": "州", "weight": 1.0, "lonlat": None},
            {"name": '黄龙府', "kind": "州", "weight": 1.0, "lonlat": None},
        ],
        '上京道': [
            {"name": '临潢府', "kind": "州", "weight": 1.5, "lonlat": [119.4, 43.9]},
            {"name": '泰州', "kind": "州", "weight": 1.0, "lonlat": None},
            {"name": '长春州', "kind": "州", "weight": 1.0, "lonlat": None},
            {"name": '上京北', "kind": "州", "weight": 1.0, "lonlat": None},
        ],
    },
    '西夏': {
        '兴庆府直辖': [
            {"name": '兴庆府', "kind": "州", "weight": 1.5, "lonlat": [106.3, 38.5]},
            {"name": '西平府', "kind": "州", "weight": 1.5, "lonlat": [106.3, 38.1]},
            {"name": '会州', "kind": "州", "weight": 1.5, "lonlat": [104.3, 36.54]},
            {"name": '白马强镇', "kind": "州", "weight": 1.0, "lonlat": None},
        ],
        '河西走廊': [
            {"name": '西凉府', "kind": "州", "weight": 1.5, "lonlat": [102.6, 37.9]},
            {"name": '甘州', "kind": "州", "weight": 1.5, "lonlat": [100.4, 38.9]},
            {"name": '肃州', "kind": "州", "weight": 1.5, "lonlat": [98.5, 39.7]},
            {"name": '黑山威福军', "kind": "州", "weight": 1.0, "lonlat": None},
        ],
        '河套南': [
            {"name": '宥州', "kind": "州", "weight": 1.0, "lonlat": None},
        ],
    },
    '吐蕃': {
        '青唐': [
            {"name": '西宁州', "kind": "州", "weight": 1.5, "lonlat": [101.8, 36.62]},
            {"name": '湟州', "kind": "州", "weight": 1.5, "lonlat": [100.9, 36.96]},
            {"name": '廓州', "kind": "州", "weight": 1.5, "lonlat": [102.03, 35.52]},
            {"name": '青海湖诸部', "kind": "州", "weight": 1.5, "lonlat": [99.0, 36.6]},
            {"name": '柴达木', "kind": "州", "weight": 1.5, "lonlat": [97.37, 37.37]},
        ],
        '逻些': [
            {"name": '逻些城', "kind": "州", "weight": 1.5, "lonlat": [91.11, 29.65]},
            {"name": '乌如', "kind": "州", "weight": 1.5, "lonlat": [91.77, 29.24]},
            {"name": '约如', "kind": "州", "weight": 1.5, "lonlat": [94.36, 29.65]},
            {"name": '朵康', "kind": "州", "weight": 1.5, "lonlat": [97.17, 31.14]},
        ],
        '后藏': [
            {"name": '日喀则', "kind": "州", "weight": 1.5, "lonlat": [88.88, 29.27]},
            {"name": '象雄', "kind": "州", "weight": 1.5, "lonlat": [80.1, 32.5]},
            {"name": '云如', "kind": "州", "weight": 1.5, "lonlat": [92.05, 31.48]},
        ],
    },
    '大理': {
        '大理': [
            {"name": '大理府', "kind": "州", "weight": 1.5, "lonlat": [100.23, 25.6]},
            {"name": '善阐府', "kind": "州", "weight": 1.5, "lonlat": [102.71, 25.04]},
            {"name": '威楚府', "kind": "州", "weight": 1.5, "lonlat": [101.53, 25.05]},
            {"name": '石城郡', "kind": "州", "weight": 1.5, "lonlat": [103.8, 25.5]},
            {"name": '秀山郡', "kind": "州", "weight": 1.5, "lonlat": [103.37, 23.37]},
            {"name": '永昌府', "kind": "州", "weight": 1.5, "lonlat": [99.17, 25.11]},
            {"name": '金齿镇', "kind": "州", "weight": 1.5, "lonlat": [98.58, 24.44]},
            {"name": '银生府', "kind": "州", "weight": 1.5, "lonlat": [100.97, 22.79]},
            {"name": '铁桥节度', "kind": "州", "weight": 1.5, "lonlat": [99.7, 27.82]},
            {"name": '东川郡', "kind": "州", "weight": 1.5, "lonlat": [103.72, 27.34]},
            {"name": '建昌府', "kind": "州", "weight": 1.5, "lonlat": [102.26, 27.89]},
            {"name": '会川府', "kind": "州", "weight": 1.5, "lonlat": [101.72, 26.58]},
        ],
    },
    '高丽': {
        '开京': [
            {"name": '开京', "kind": '京', "weight": 1.5, "lonlat": [126.6, 37.9], "note": '开城，高丽王京'},
            {"name": '汉阳', "kind": '州', "weight": 1.1, "lonlat": [127.0, 37.6], "note": '南京（汉阳）'},
        ],
        '西京平壤': [
            {"name": '西京', "kind": '京', "weight": 1.3, "lonlat": [125.8, 39.0], "note": '平壤，高丽西京'},
            {"name": '安州', "kind": '州', "weight": 1.0, "lonlat": [125.5, 39.6], "note": '清川江要冲'},
        ],
        '东京开城': [
            {"name": '东京', "kind": '京', "weight": 1.2, "lonlat": [129.2, 35.8], "note": '庆州，高丽东京'},
            {"name": '金州', "kind": '州', "weight": 1.0, "lonlat": [128.6, 35.2], "note": '南境重镇'},
        ],
    },
    '日本': {
        '京都': [
            {"name": '京都', "kind": '京', "weight": 1.5, "lonlat": [135.8, 35.0], "note": '平安京'},
            {"name": '摄津', "kind": '州', "weight": 1.1, "lonlat": [135.5, 34.7], "note": '濑户内要冲'},
        ],
        '镰仓': [
            {"name": '镰仓', "kind": '京', "weight": 1.4, "lonlat": [139.5, 35.3], "note": '武家政权'},
            {"name": '博多', "kind": '州', "weight": 1.3, "lonlat": [130.4, 33.6], "note": '与宋海贸主港'},
        ],
        '九州': [
            {"name": '太宰府', "kind": '府', "weight": 1.2, "lonlat": [130.5, 33.5], "note": '西国政务中心'},
        ],
    },
    '安南': {
        '升龙': [
            {"name": '升龙', "kind": '京', "weight": 1.5, "lonlat": [105.8, 21.0], "note": '河内，安南都护府故地'},
            {"name": '谅山', "kind": '州', "weight": 1.0, "lonlat": [106.7, 21.8], "note": '与宋邕州接境'},
        ],
        '清化': [
            {"name": '清化', "kind": '州', "weight": 1.1, "lonlat": [105.8, 19.8], "note": '清化，南境重镇'},
            {"name": '演州', "kind": '州', "weight": 1.0, "lonlat": [105.6, 19.0], "note": '中北要冲'},
        ],
        '乂安': [
            {"name": '乂安', "kind": '州', "weight": 1.0, "lonlat": [105.7, 18.7], "note": '南陲'},
        ],
    },
}

#: 地图省 → 运行态省（`external_regimes[国].provinces`）映射；
#: 西夏/大理 数量不同，逐条标「设定值」；未列出的省默认同名。
REGIME_PROVINCE_MAP = {
    "西夏": {
        "兴庆府直辖": "兴庆府",
        "河西走廊": "西平府",   # 设定值：运行态无「河西」省，暂隶西平府（待补省）
        "河套南": "西平府",     # 设定值：同上
    },
    "大理": {
        "大理": "大理",
    },
}

#: 运行态有、地图无对应省的（T2 无子块，登记原因便于读数）
PROVINCE_WITHOUT_MAP = {
    "大理": {"善阐": "地图仅 1 省（大理），善阐府块挂在大理省下"},
}