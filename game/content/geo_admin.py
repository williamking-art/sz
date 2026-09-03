# -*- coding: utf-8 -*-
"""宋祚 · 地理行政归属（路/府两级，单一权威源）

层级定稿（2026-09-03 用户确认）：
    路（省级）→ 府 / 州 / 军（市级）→ 县（不入库）
- **东京开封府为京府，隶京畿路**——游戏经济单位"东京开封府"是京畿路的
  府级载体，不再与诸路并列混称。
- CIRCUIT_INFO：路级注册表（类型/治所/对应游戏单位/成员府州及治所经纬度）。
- PREFECTURE_ADMIN：游戏 12 个经济/军事单位（PREFECTURE_LIST）→ 行政归属映射。
  现有代码以 PREFECTURE_LIST 名为键（state.prefectures / ARMY_UNIT_INIT /
  粮产分摊），**键名不变**，本模块只加"归属"层，零破坏。
- CIRCUIT_BOUNDS / REGIME_GEO：舆图矢量数据（真实经纬度，简化示意边界），
  由 content/build_map_geo.py 生成 GeoJSON 供 MapLibre 舆图消费。
- REGIME_SUBDIVISIONS：周边政权内部分路（省级以下再分一级，如辽五京道、
  西夏三司）。分路是地不是政权的附属：**自持 owner**（初始=母政权），
  可单独易主（宋北伐取南京道/西京道即燕云十六州，辽其余诸道仍辽）；
  整体易主（金崛起代辽）用 set_regime_owner(cascade=True) 级联。金激活后
  可照此追加五京道（扩展点，本次未实现）。
- 坐标系：WGS84 经纬度；边界为**简化示意**（玩法分组，非严格历史界），
  标注"示意"处不得当史实引用（史翰青席位口径）。
"""
from __future__ import annotations

__all__ = ["CIRCUIT_INFO", "CIRCUIT_BOUNDS", "REGIME_GEO", "REGIME_SUBDIVISIONS",
           "PREFECTURE_ADMIN", "circuit_of", "members_of", "all_city_points",
           "subdivisions_of", "set_subdivision_owner", "set_regime_owner",
           "MAP_VIEW"]

# 舆图数据覆盖范围（经纬度）：东亚 + 东南亚 + 澳大利亚。
# 西界 60°E = 阿拉伯半岛最东端（阿曼），刚好令半岛出画；南界 -44° 含澳大利亚全境。
# 数据四至仅限定可平移边界；玩家默认视野（东亚重心）由 build_map_geo.build_view 下发。
MAP_VIEW = {"west": 60.0, "east": 150.0, "south": -44.0, "north": 56.0}

# ============================================================
# 一、路级注册表（省级）
#    members: (府/州名, 等级, 治所经度, 治所纬度)
#    game_unit: 对应 PREFECTURE_LIST 经济/军事单位键；None=未单列（随邻路分摊）
# ============================================================
CIRCUIT_INFO: dict = {
    "京畿路": {
        "type": "京畿", "seat": "开封府", "game_unit": "京畿路",
        "members": [
            ("开封府", "京府", 114.31, 34.80),
            ("颍昌府", "府", 113.85, 34.04),
            ("郑州", "州", 113.63, 34.75),
            ("滑州", "州", 114.52, 35.58),
            ("陈州", "州", 114.88, 33.73),
        ],
    },
    "京西路": {
        "type": "腹里", "seat": "河南府", "game_unit": "京西路",
        "members": [
            ("河南府", "府", 112.45, 34.62),
            ("颍昌府", "府", 113.85, 34.04),
            ("襄阳府", "府", 112.12, 32.01),
            ("邓州", "州", 112.09, 32.69),
            ("唐州", "州", 112.84, 32.68),
            ("随州", "州", 113.38, 31.69),
        ],
    },
    "河北路": {
        "type": "沿边", "seat": "大名府", "game_unit": "河北路",
        "members": [
            ("大名府", "府", 115.15, 36.28),
            ("真定府", "府", 114.57, 38.14),
            ("河间府", "府", 116.10, 38.45),
            ("定州", "州", 114.99, 38.51),
            ("澶州", "州", 115.03, 35.76),
            ("沧州", "州", 116.86, 38.30),
            ("邢州", "州", 114.50, 37.07),
            ("雄州", "州", 116.11, 38.99),
        ],
    },
    "河东路": {
        "type": "沿边", "seat": "太原府", "game_unit": "河东路",
        "members": [
            ("太原府", "府", 112.55, 37.87),
            ("潞州", "州", 113.12, 36.19),
            ("平阳府", "府", 111.52, 36.09),
            ("代州", "州", 112.96, 39.07),
            ("忻州", "州", 112.73, 38.42),
            ("石州", "州", 111.14, 37.52),
        ],
    },
    "陕西路": {
        "type": "沿边", "seat": "京兆府", "game_unit": "陕西路",
        "members": [
            ("京兆府", "府", 108.94, 34.27),
            ("延安府", "府", 109.49, 36.60),
            ("凤翔府", "府", 107.40, 34.52),
            ("秦州", "州", 105.72, 34.58),
            ("渭州", "州", 106.68, 35.55),
            ("庆州", "州", 107.64, 35.73),
            ("熙州", "州", 103.86, 35.38),
        ],
    },
    "两浙路": {
        "type": "腹里", "seat": "杭州", "game_unit": "两浙路",
        "members": [
            ("杭州", "州", 120.16, 30.25),
            ("苏州", "州", 120.62, 31.32),
            ("越州", "州", 120.58, 30.00),
            ("润州", "州", 119.42, 32.20),
            ("明州", "州", 121.55, 29.87),
            ("湖州", "州", 120.09, 30.87),
            ("婺州", "州", 119.65, 29.08),
            ("台州", "州", 121.13, 28.86),
            ("温州", "州", 120.70, 28.00),
        ],
    },
    "江南东路": {
        "type": "腹里", "seat": "江宁府", "game_unit": "江南东路",
        "members": [
            ("江宁府", "府", 118.78, 32.06),
            ("宣州", "州", 118.76, 30.95),
            ("歙州", "州", 118.44, 29.87),
            ("池州", "州", 117.49, 30.66),
            ("饶州", "州", 116.68, 29.00),
            ("信州", "州", 117.94, 28.45),
            ("太平州", "州", 118.50, 31.57),
        ],
    },
    "江南西路": {
        "type": "腹里", "seat": "洪州", "game_unit": "江南西路",
        "members": [
            ("洪州", "州", 115.89, 28.68),
            ("吉州", "州", 114.99, 27.12),
            ("虔州", "州", 114.94, 25.85),
            ("抚州", "州", 116.36, 27.98),
            ("袁州", "州", 114.39, 27.81),
            ("筠州", "州", 115.38, 28.42),
        ],
    },
    "荆湖南路": {
        "type": "腹里", "seat": "潭州", "game_unit": "荆湖南路",
        "members": [
            ("潭州", "州", 112.94, 28.23),
            ("衡州", "州", 112.61, 26.89),
            ("永州", "州", 111.62, 26.22),
            ("道州", "州", 111.60, 25.52),
            ("郴州", "州", 113.03, 25.79),
            ("邵州", "州", 111.47, 27.24),
        ],
    },
    "福建路": {
        "type": "腹里", "seat": "福州", "game_unit": "福建路",
        "members": [
            ("福州", "州", 119.30, 26.08),
            ("泉州", "州", 118.59, 24.91),
            ("建州", "州", 118.30, 27.04),
            ("漳州", "州", 117.65, 24.51),
            ("汀州", "州", 116.36, 25.85),
            ("南剑州", "州", 118.18, 26.64),
            ("兴化军", "军", 119.01, 25.45),
        ],
    },
    "成都府路": {
        "type": "腹里", "seat": "成都府", "game_unit": "成都府路",
        "members": [
            ("成都府", "府", 104.07, 30.67),
            ("眉州", "州", 103.85, 30.05),
            ("蜀州", "州", 103.67, 30.63),
            ("彭州", "州", 103.96, 30.99),
            ("绵州", "州", 104.68, 31.47),
            ("汉州", "州", 104.28, 30.98),
            ("嘉州", "州", 103.77, 29.55),
        ],
    },
    "广南东路": {
        "type": "沿边", "seat": "广州", "game_unit": "广南东路",
        "members": [
            ("广州", "州", 113.26, 23.13),
            ("韶州", "州", 113.60, 24.81),
            ("潮州", "州", 116.63, 23.66),
            ("惠州", "州", 114.42, 23.11),
            ("端州", "州", 112.47, 23.05),
            ("英州", "州", 113.42, 24.19),
        ],
    },
    # —— 未单列经济单位的路（舆图补全；钱粮随邻路分摊，钱盈仓口径）——
    "淮南东路": {"type": "腹里", "seat": "扬州", "game_unit": "淮南东路",
                 "members": [("扬州", "州", 119.42, 32.39), ("楚州", "州", 119.15, 33.61),
                              ("泰州", "州", 119.90, 32.49), ("通州", "州", 120.86, 32.01),
                              ("真州", "州", 119.18, 32.27)]},
    "淮南西路": {"type": "腹里", "seat": "庐州", "game_unit": "淮南西路",
                 "members": [("庐州", "州", 117.28, 31.86), ("寿州", "州", 116.79, 32.58),
                              ("舒州", "州", 117.05, 30.51), ("黄州", "州", 114.87, 30.45),
                              ("蕲州", "州", 115.44, 30.23), ("光州", "州", 115.05, 32.13)]},
    "荆湖北路": {"type": "腹里", "seat": "江陵府", "game_unit": "荆湖北路",
                 "members": [("江陵府", "府", 112.24, 30.33), ("岳州", "州", 113.13, 29.37),
                              ("鼎州", "州", 111.69, 29.04), ("澧州", "州", 111.76, 29.64),
                              ("鄂州", "州", 114.31, 30.60), ("归州", "州", 110.98, 30.82),
                              ("辰州", "州", 110.40, 28.46)]},
    "广南西路": {"type": "沿边", "seat": "桂州", "game_unit": "广南西路",
                 "members": [("桂州", "州", 110.29, 25.27), ("柳州", "州", 109.42, 24.33),
                              ("梧州", "州", 111.28, 23.48), ("邕州", "州", 108.32, 22.82),
                              ("容州", "州", 110.55, 22.85), ("琼州", "州", 110.35, 20.03),
                              ("雷州", "州", 110.08, 20.91)]},
    "利州路": {"type": "沿边", "seat": "兴元府", "game_unit": "利州路",
               "members": [("兴元府", "府", 107.03, 33.07), ("利州", "州", 105.84, 32.44),
                            ("阆州", "州", 105.97, 31.57), ("剑州", "州", 105.52, 32.02)]},
    "夔州路": {"type": "沿边", "seat": "夔州", "game_unit": "夔州路",
               "members": [("夔州", "州", 109.46, 31.02), ("忠州", "州", 108.04, 30.30),
                            ("万州", "州", 108.41, 30.81), ("达州", "州", 107.47, 31.21),
                            ("涪州", "州", 107.39, 29.70), ("黔州", "州", 108.17, 29.29),
                            ("施州", "州", 109.49, 30.27)]},
    "京东东路": {
        "type": "腹里", "seat": "青州", "game_unit": "京东东路",
        "members": [
            ("青州", "府", 118.48, 36.68),
            ("密州", "州", 119.41, 35.99),
            ("沂州", "州", 118.35, 35.06),
            ("登州", "州", 120.76, 37.81),
            ("莱州", "州", 119.94, 37.18),
            ("潍州", "州", 119.16, 36.71),
            ("淄州", "州", 117.97, 36.64),
        ],
    },
    "京东西路": {
        "type": "腹里", "seat": "兖州", "game_unit": "京东西路",
        "members": [
            ("兖州", "州", 116.83, 35.55),
            ("徐州", "州", 117.18, 34.26),
            ("济州", "州", 116.06, 35.40),
            ("郓州", "州", 116.30, 35.93),
            ("濮州", "州", 115.51, 35.56),
        ],
    },
}

# ============================================================
# 二、路界多边形（简化示意，WGS84）
# ============================================================
CIRCUIT_BOUNDS: dict = {
    "京东东路": [[116.0, 34.6], [122.7, 34.7], [122.7, 37.7], [118.0, 38.0], [116.0, 37.0]],
    "京东西路": [[114.8, 34.2], [118.4, 34.3], [118.4, 36.1], [116.3, 36.4], [114.9, 36.0]],
    "京畿路":   [[113.9, 34.3], [116.4, 34.2], [116.6, 35.3], [115.5, 35.8], [114.0, 35.6], [113.8, 34.9]],
    "京西路":   [[110.6, 33.2], [112.0, 34.4], [113.9, 34.1], [113.8, 33.0], [112.5, 31.6], [110.8, 31.6]],
    "河北路":   [[114.5, 36.3], [116.0, 36.0], [118.0, 36.6], [119.3, 37.8], [118.6, 39.5], [116.5, 40.0], [114.8, 39.6], [114.3, 38.0]],
    "河东路":   [[110.9, 35.4], [112.5, 35.1], [114.2, 35.9], [114.4, 37.5], [113.2, 39.9], [111.2, 40.1], [110.6, 38.0]],
    "陕西路":   [[105.2, 34.5], [106.5, 33.0], [108.5, 32.7], [110.7, 33.4], [110.9, 35.2], [110.6, 37.4], [108.0, 37.6], [105.5, 36.9], [104.9, 35.6]],
    "两浙路":   [[119.0, 31.9], [120.5, 32.3], [121.9, 31.4], [122.0, 29.8], [121.2, 28.4], [119.6, 27.6], [118.8, 28.6], [118.6, 30.5]],
    "江南东路": [[116.3, 31.6], [118.0, 32.1], [119.3, 31.5], [119.0, 30.0], [117.8, 29.1], [116.4, 29.5]],
    "江南西路": [[113.7, 29.6], [115.5, 29.9], [117.6, 29.3], [117.9, 27.5], [116.0, 25.0], [114.2, 24.7], [113.5, 27.0]],
    "荆湖南路": [[109.2, 29.4], [111.5, 29.6], [114.4, 29.2], [114.5, 27.0], [112.0, 24.6], [109.4, 25.2], [108.9, 27.3]],
    "福建路":   [[115.7, 27.9], [117.5, 28.3], [119.5, 27.6], [120.3, 26.2], [119.0, 23.9], [117.0, 23.3], [115.6, 24.2], [115.5, 26.0]],
    "成都府路": [[102.2, 30.5], [103.5, 32.3], [105.8, 32.4], [106.7, 30.8], [105.5, 28.6], [103.0, 28.4], [101.9, 29.4]],
    "广南东路": [[110.7, 24.9], [112.5, 25.5], [115.0, 25.2], [117.1, 24.4], [116.5, 22.6], [113.5, 21.6], [110.9, 21.2], [110.5, 23.0]],
    "淮南东路": [[114.8, 34.2], [117.5, 34.4], [119.5, 33.6], [119.2, 31.8], [117.0, 30.7], [115.0, 31.2], [114.6, 32.8]],
    "淮南西路": [[114.8, 32.9], [117.0, 32.6], [119.0, 31.6], [117.2, 30.0], [115.2, 30.6], [114.7, 31.8]],
    "荆湖北路": [[109.8, 31.8], [112.5, 32.0], [114.7, 31.2], [114.6, 29.5], [112.0, 29.4], [109.9, 30.0]],
    "广南西路": [[104.8, 24.6], [107.5, 25.7], [110.6, 25.4], [111.4, 23.4], [109.0, 20.7], [106.0, 21.5], [104.6, 22.8]],
    "利州路":   [[103.8, 32.6], [105.8, 32.5], [106.9, 32.4], [106.0, 31.0], [104.5, 31.2], [103.6, 31.8]],
    "夔州路":   [[106.9, 32.4], [110.3, 32.2], [110.5, 29.9], [108.2, 28.1], [106.0, 28.3], [106.8, 30.6]],
}

# ============================================================
# 三、周边政权疆域（键对齐 content.data.EXTERNAL_REGIMES / EXTERNAL_FORCES）
#    active=False 待 timeline break 激活（金崛起）；owner 可被扩张改写
# ============================================================
REGIME_GEO: dict = {
    # use_parts=True:多边形不再用手工 polygon,由 build_map_geo 按真实政区
    # (REGIME_PARTS,省/地级拼合)生成;label_at/active/owner 仍为本表权威。
    "辽": {"name": "辽", "active": True, "owner": "辽", "label_at": [119.5, 45.5],
           "use_parts": True,
           "polygon": [[112.8, 41.5], [115.0, 39.9], [118.5, 40.3], [121.8, 39.8],
                        [124.5, 40.8], [128.0, 42.0], [131.5, 43.5], [133.5, 46.5],
                        [131.0, 49.0], [126.5, 49.5], [122.0, 48.0], [117.5, 46.5],
                        [113.5, 44.5], [112.8, 41.5]]},
    "金": {"use_parts": True, "name": "金", "active": False, "owner": "金", "label_at": [128.5, 44.5],
           "polygon": [[125.8, 43.5], [129.5, 42.0], [131.5, 43.5], [131.0, 46.0],
                        [128.0, 46.5], [125.5, 45.0], [125.8, 43.5]],
           "note": "生女真；timeline break'金崛起'激活，同时辽收缩"},
    "西夏": {"name": "西夏", "active": True, "owner": "西夏", "label_at": [101.0, 39.0],
             "use_parts": True,
             "polygon": [[97.5, 38.5], [100.5, 37.2], [103.5, 36.2], [106.4, 36.3],
                          [106.4, 38.6], [103.0, 40.5], [99.5, 41.5], [97.0, 40.5],
                          [96.5, 39.5], [97.5, 38.5]]},
    "吐蕃": {"name": "吐蕃诸部", "active": True, "owner": "吐蕃", "label_at": [87.0, 32.0],
             "use_parts": True,
             "polygon": [[78.5, 35.5], [82.0, 36.5], [86.0, 36.8], [90.0, 36.0],
                          [93.5, 34.5], [96.5, 33.5], [97.5, 31.5], [95.0, 29.0],
                          [91.0, 27.8], [86.0, 28.2], [81.0, 29.5], [78.0, 31.5],
                          [77.5, 33.5], [78.5, 35.5]]},
    "大理": {"name": "大理", "active": True, "owner": "大理", "label_at": [101.0, 25.0],
             "use_parts": True,
             "polygon": [[98.5, 28.0], [103.5, 28.0], [106.0, 25.5], [105.5, 22.5],
                          [101.5, 21.2], [97.8, 23.5], [97.5, 26.0], [98.5, 28.0]],
             "note": "云南·贵州；政区归属玩法抽象，史实边界待考"},
    "喀尔喀蒙古": {"name": "喀尔喀蒙古", "active": True, "owner": "喀尔喀蒙古", "use_parts": True,
                  "label_at": [99.0, 46.0],
                  "polygon": [[88.0, 46.5], [93.0, 48.5], [99.0, 49.5], [106.0, 49.0],
                               [111.5, 47.5], [112.0, 45.0], [107.0, 43.5], [99.0, 42.5],
                               [92.0, 43.5], [87.5, 44.5], [88.0, 46.5]]},
    "漠南蒙古": {"use_parts": True, "name": "漠南蒙古", "active": True, "owner": "漠南蒙古",
                 "label_at": [107.0, 42.5],
                 "polygon": [[107.0, 43.5], [112.0, 45.0], [112.8, 43.0], [110.0, 41.0],
                              [106.0, 40.8], [103.0, 41.5], [102.5, 43.0], [104.5, 43.8],
                              [107.0, 43.5]]},
    "科尔沁": {"use_parts": True, "name": "科尔沁", "active": True, "owner": "科尔沁", "label_at": [121.0, 46.5],
               "polygon": [[118.0, 44.5], [122.0, 45.5], [125.0, 46.5], [124.5, 48.0],
                            [120.5, 48.5], [117.5, 47.0], [117.0, 45.5], [118.0, 44.5]]},
    "察哈尔": {"use_parts": True, "name": "察哈尔", "active": True, "owner": "察哈尔", "label_at": [112.5, 42.3],
               "polygon": [[110.5, 41.0], [113.5, 41.8], [115.5, 42.5], [114.5, 43.8],
                            [111.5, 43.5], [109.5, 42.3], [110.5, 41.0]]},
    "海西": {"use_parts": True, "name": "海西女真", "active": True, "owner": "海西", "label_at": [129.5, 48.5],
             "polygon": [[127.5, 46.5], [131.0, 46.8], [133.5, 48.5], [131.5, 50.5],
                          [127.5, 50.0], [125.5, 48.0], [127.5, 46.5]]},
    "建州": {"use_parts": True, "name": "建州女真", "active": True, "owner": "建州", "label_at": [127.8, 44.3],
             "polygon": [[125.8, 43.5], [128.5, 43.0], [130.5, 43.8], [129.5, 45.2],
                          [126.8, 45.3], [125.5, 44.3], [125.8, 43.5]]},
    "东海": {"use_parts": True, "name": "东海女真", "active": True, "owner": "东海", "label_at": [133.5, 46.0],
             "polygon": [[131.5, 43.8], [134.5, 44.5], [136.0, 46.5], [134.0, 48.0],
                          [132.0, 47.0], [131.0, 45.2], [131.5, 43.8]]},
    "高丽": {"name": "高丽", "active": True, "owner": "高丽", "label_at": [127.0, 37.5],
             "use_parts": True,
             "polygon": [[124.6, 39.8], [125.8, 40.5], [127.2, 39.5], [128.5, 38.5],
                          [129.5, 37.0], [129.2, 35.2], [127.8, 34.8], [126.5, 36.8],
                          [126.0, 38.0], [124.6, 38.5], [124.6, 39.8]]},
    "日本": {"name": "日本", "active": True, "owner": "日本", "label_at": [137.5, 36.5],
             "use_parts": True,
             "polygon": [[129.5, 31.2], [130.8, 33.0], [131.5, 34.5], [133.5, 35.5],
                          [136.0, 35.8], [138.5, 37.5], [140.5, 39.5], [141.5, 41.5],
                          [142.5, 43.5], [144.0, 44.2], [145.5, 43.5], [143.5, 42.0],
                          [141.0, 40.0], [139.5, 37.5], [137.0, 36.0], [134.5, 34.0],
                          [132.0, 32.8], [130.5, 31.0], [129.5, 31.2]]},
    "琉球": {"name": "琉球", "active": True, "owner": "琉球", "label_at": [121.0, 23.7],
             "use_parts": True},  # 版图=台湾岛(游戏设定)
    "喀喇汗": {"name": "喀喇汗", "active": True, "owner": "喀喇汗", "label_at": [79.5, 39.3],
             "use_parts": True,
             "note": "西域大部；政区归属玩法抽象，史实边界待考"},
    "高昌回鹘": {"name": "高昌回鹘", "active": True, "owner": "高昌回鹘", "label_at": [89.8, 42.9],
             "use_parts": True,
             "note": "东部天山；政区归属玩法抽象，史实边界待考"},
    "塞尔柱": {"name": "塞尔柱", "active": True, "owner": "塞尔柱", "label_at": [68.0, 39.5],
            "use_parts": True, "note": "塞尔柱帝国中亚东部/河中诸邦，西抵60°E舆图边界"},
    "身毒": {"name": "身毒", "active": True, "owner": "身毒", "label_at": [79.0, 22.5],
           "use_parts": True, "note": "印度诸王国；天竺古称"},
    "蒲甘": {"name": "蒲甘", "active": True, "owner": "蒲甘", "label_at": [95.0, 21.0],
           "use_parts": True, "note": "缅甸蒲甘王国"},
    "大越": {"name": "大越", "active": True, "owner": "大越", "label_at": [105.5, 20.8],
           "use_parts": True, "note": "安南李朝/交趾"},
    "占婆": {"name": "占婆", "active": True, "owner": "占婆", "label_at": [108.5, 13.8],
           "use_parts": True, "note": "占城国，占城稻原产地"},
    "吴哥": {"name": "吴哥", "active": True, "owner": "吴哥", "label_at": [104.8, 12.5],
           "use_parts": True, "note": "高棉帝国/真腊"},
    "罗斛": {"name": "罗斛", "active": True, "owner": "罗斛", "label_at": [100.5, 15.0],
           "use_parts": True, "note": "暹罗/素可泰前身"},
    "澜沧": {"name": "澜沧", "active": True, "owner": "澜沧", "label_at": [102.5, 18.5],
           "use_parts": True, "note": "老挝部族/南掌前身，填补中南内陆"},
    "柔佛": {"name": "柔佛", "active": True, "owner": "柔佛", "label_at": [102.5, 4.0],
           "use_parts": True, "note": "马来半岛各邦"},
    "三佛齐": {"name": "三佛齐", "active": True, "owner": "三佛齐", "label_at": [102.0, 0.5],
            "use_parts": True, "note": "室利佛逝/苏门答腊大岛，海商枢纽"},
    "爪哇": {"name": "爪哇", "active": True, "owner": "爪哇", "label_at": [110.0, -7.2],
           "use_parts": True, "note": "爪哇大岛"},
    "婆罗": {"name": "婆罗", "active": True, "owner": "婆罗", "label_at": [114.0, 0.5],
           "use_parts": True, "note": "婆罗洲/加里曼丹大岛"},
    "吕宋": {"name": "吕宋", "active": True, "owner": "吕宋", "label_at": [121.5, 14.5],
           "use_parts": True, "note": "吕宋国/菲律宾群岛"},
}

# ============================================================
# 三·四·a 政权版图配色(低饱和宋画色板;fill 由构建期烘焙进要素属性)
# ============================================================
REGIME_COLORS: dict = {
    "辽": "#d0b184",        # 赭金
    "金": "#e3dbc8",        # 未兴灰米(金崛起改写后另配)
    "西夏": "#cf9a72",      # 赤陶
    "吐蕃": "#c4a3b4",      # 灰紫
    "大理": "#a9bfa8",      # 苍山绿
    "高丽": "#a3b8cc",      # 青灰蓝
    "日本": "#d3aca4",      # 灰樱
    "喀尔喀蒙古": "#c6b393",  # 驼
    "琉球": "#c2b2a0",
    "身毒": "#cfb997",       # 檀木褐金
    "蒲甘": "#c2a688",       # 黄土褐
    "大越": "#9fae9d",       # 青瓷绿
    "占婆": "#c7a38f",       # 肉褐赤
    "吴哥": "#b8ab93",       # 洞里萨灰绿
    "罗斛": "#d2be92",       # 金稻黄
    "澜沧": "#c4b79b",       # 湄公土黄(老挝)
    "柔佛": "#a6b5a3",       # 马来青碧(马来半岛)
    "三佛齐": "#cfae88",     # 海商赭金(苏门答腊)
    "爪哇": "#c8a598",       # 赤陶赭(爪哇岛)
    "婆罗": "#9faea2",       # 黛绿(婆罗洲/加里曼丹)
    "吕宋": "#baa58e",       # 珍珠灰金(菲律宾诸岛)
    "喀喇汗": "#b39d7e",     # 灰驼褐(西域)
    "高昌回鹘": "#d8c49a",   # 沙金(东部天山)
    "塞尔柱": "#b99684",     # 呼罗珊泥金(中亚大帝国)
    "南洋诸番": "#d8cfbe",   # 外围海岛中立底色(有省份无势力)
}
_DEFAULT_REGIME_COLOR = "#d8cbaa"

# ============================================================
# 三·四·b 政权疆域省级拼合表（use_parts=True 的政权走真实政区边界）
#    现代中国境内政权按省/地级真实边界拼合（"省份划分细致"）；
#    境外势力一势力一块（REGIME_GEO.polygon 手工近似）。
#    province = 整省一块 feature；prefecture = 跨政权省的地级拆分。
#    数据源 assets/map/raw/datav_*_full.json（fetch_basemap.py 下载）。
#    归属为玩法抽象（示意），史实边界待考。
# ============================================================
REGIME_PARTS: dict = {
    # 辽朝：五京道体系（如宋分路分省），各道真实地级合并成大省，附省界线与府治
    "辽": {
        "sub_roads": {
            "南京道": {
                "seat": "析津府", "seat_at": [116.4, 39.9], "label_at": [117.8, 39.3],
                "prefectures": {
                    "北京市": "*", "天津市": "*",
                    "河北省": ["唐山市", "秦皇岛市"],
                },
            },
            "西京道": {
                "seat": "大同府", "seat_at": [113.3, 40.1], "label_at": [111.8, 41.5],
                "prefectures": {
                    "山西省": ["大同市", "朔州市"],
                    "河北省": ["张家口市"],
                    "内蒙古自治区": ["乌兰察布市", "呼和浩特市", "包头市"],
                },
            },
            "中京道": {
                "seat": "大定府", "seat_at": [120.2, 41.6], "label_at": [118.5, 43.2],
                "prefectures": {
                    "河北省": ["承德市"],
                    "内蒙古自治区": ["赤峰市", "锡林郭勒盟"],
                    "辽宁省": ["朝阳市", "阜新市"],
                },
            },
            "东京道": {
                "seat": "辽阳府", "seat_at": [123.2, 41.3], "label_at": [125.8, 42.5],
                "prefectures": {
                    "辽宁省": ["沈阳市", "大连市", "鞍山市", "抚顺市", "本溪市", "丹东市", "锦州市", "营口市", "辽阳市", "盘锦市", "铁岭市", "葫芦岛市"],
                    "吉林省": ["通化市", "白山市", "延边朝鲜族自治州"],
                },
            },
            "上京道": {
                "seat": "临潢府", "seat_at": [119.4, 43.9], "label_at": [125.5, 46.8],
                "prefectures": {
                    "黑龙江省": "*",
                    "吉林省": ["长春市", "吉林市", "四平市", "辽源市", "白城市", "松原市"],
                    "内蒙古自治区": ["通辽市", "兴安盟", "呼伦贝尔市"],
                },
            },
        },
        "borders": True,
    },
    # 西夏：监军司道体系（如宋分路分省）
    "西夏": {
        "sub_roads": {
            "兴庆府直辖": {
                "seat": "兴庆府", "seat_at": [106.3, 38.5], "label_at": [104.2, 39.5],
                "prefectures": {
                    "宁夏回族自治区": "*",
                    "内蒙古自治区": ["乌海市", "阿拉善盟"],
                },
            },
            "河西走廊": {
                "seat": "西凉府", "seat_at": [102.6, 37.9], "label_at": [100.2, 39.8],
                "prefectures": {
                    "甘肃省": ["武威市", "金昌市", "张掖市", "酒泉市", "嘉峪关市"],
                    "内蒙古自治区": ["巴彦淖尔市"],
                },
            },
            "河南地": {
                "seat": "西平府", "seat_at": [106.3, 38.1], "label_at": [107.5, 37.5],
                "prefectures": {
                    "甘肃省": ["白银市", "兰州市", "定西市", "平凉市", "庆阳市", "陇南市", "天水市", "临夏回族自治州"],
                    "内蒙古自治区": ["鄂尔多斯市"],
                },
            },
        },
        "borders": True,
    },
    "吐蕃": {
        "provinces": ["青海省", "西藏自治区"],
        "prefectures": {
            "四川省": ["甘孜藏族自治州", "阿坝藏族羌族自治州"],
            "甘肃省": ["甘南藏族自治州"],
        },
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "吐蕃_藏南"},
        "merge": False,  # 保留省份拼合
    },
    "大理": {
        "provinces": ["云南省", "贵州省"],
        "prefectures": {"四川省": ["凉山彝族自治州", "攀枝花市"]},
    },
    # 境外一体块:NE Admin-1 按国家过滤后 union 出精确国界轮廓
    "高丽": {
        "union_external": {"file": "ne_admin1_ext.json",
                            "admin": ["North Korea", "South Korea"]},
    },
    "日本": {
        "union_external": {"file": "ne_admin1_ext.json",
                            "admin": ["Japan"],
                            "exclude": ["沖縄県"]},  # 琉球单独成体
    },
    "喀尔喀蒙古": {
        "union_external": {"file": "ne_admin1_ext.json",
                            "admin": ["Mongolia"]},
        "merge": True,
        "borders": False,
    },
    "喀喇汗": {
        "provinces": [],
        "prefectures": {"新疆维吾尔自治区": [
            "克拉玛依市", "喀什地区", "和田地区", "阿克苏地区", "克孜勒苏柯尔克孜自治州",
            "巴音郭楞蒙古自治州", "伊犁哈萨克自治州", "塔城地区", "阿勒泰地区",
            "博尔塔拉蒙古自治州", "石河子市", "阿拉尔市", "图木舒克市",
            "五家渠市", "北屯市", "铁门关市", "双河市", "可克达拉市",
            "昆玉市", "胡杨河市",
        ]},
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "喀喇汗_七河"},
        "merge": False,
    },
    "塞尔柱": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "塞尔柱"},
        "merge": True,
    },
    # 东南亚外围诸岛：有省份、不用势力，一大岛一省
    "南洋诸番_苏拉威西": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "南洋岛省_苏拉威西"},
        "merge": True, "fill": "#d8cfbe", "neutral": True, "display_name": "",
    },
    "南洋诸番_马鲁古": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "南洋岛省_马鲁古"},
        "merge": True, "fill": "#d8cfbe", "neutral": True, "display_name": "",
    },
    "南洋诸番_努沙登加拉": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "南洋岛省_努沙登加拉"},
        "merge": True, "fill": "#d8cfbe", "neutral": True, "display_name": "",
    },
    "南洋诸番_新几内亚": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "南洋岛省_新几内亚"},
        "merge": True, "fill": "#d8cfbe", "neutral": True, "display_name": "",
    },
    "高昌回鹘": {
        "provinces": [],
        "prefectures": {"新疆维吾尔自治区": [
            "哈密市", "吐鲁番市", "乌鲁木齐市", "昌吉回族自治州",
        ]},
    },
    "琉球": {
        "provinces": ["台湾省"],
    },
    "身毒": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "身毒"},
        "merge": True,
    },
    "蒲甘": {
        "union_external": {"file": "ne_admin1_ext.json", "admin": ["Myanmar"]},
        "merge": True,
    },
    "大越": {
        "union_external": {"file": "ne_admin1_ext.json", "admin": ["Vietnam"], "sub_admin": "大越"},
        "merge": True,
    },
    "占婆": {
        "union_external": {"file": "ne_admin1_ext.json", "admin": ["Vietnam"], "sub_admin": "占婆"},
        "merge": True,
    },
    "吴哥": {
        "union_external": {"file": "ne_admin1_ext.json", "admin": ["Cambodia"]},
        "merge": True,
    },
    "罗斛": {
        "union_external": {"file": "ne_admin1_ext.json", "admin": ["Thailand"]},
        "merge": True,
    },
    "澜沧": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "澜沧"},
        "merge": True,
    },
    "柔佛": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "柔佛"},
        "merge": True,
    },
    "三佛齐": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "三佛齐"},
        "merge": True,
    },
    "爪哇": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "爪哇"},
        "merge": True,
    },
    "婆罗": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "婆罗"},
        "merge": True,
    },
    "吕宋": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "吕宋"},
        "merge": True,
    },
    # 澳大利亚大陆：单一整体无势力省份，宣纸中立底色
    "大洋洲_澳洲大陆": {
        "union_external": {"file": "ne_admin1_ext.json", "target_regime": "大洋洲_澳洲大陆"},
        "merge": True, "fill": "#d8cfbe", "neutral": True, "display_name": "",
    },
}

# ============================================================
# 三·四·c 境外政权重点城市(装饰性标识,玩法抽象)
# ============================================================
REGIME_CITIES: dict = {
    "辽": [
        ("析津府", 116.4, 39.9),   # 南京道治所 (幽州)
        ("大同府", 113.3, 40.1),   # 西京道治所 (云中)
        ("大定府", 120.2, 41.6),   # 中京道治所
        ("辽阳府", 123.2, 41.3),   # 东京道治所
        ("临潢府", 119.4, 43.9),   # 上京道治所 (辽都)
    ],
    "西夏": [
        ("兴庆府", 106.3, 38.5),   # 夏都
        ("西平府", 106.3, 38.1),   # 灵州重镇
        ("西凉府", 102.6, 37.9),   # 凉州
        ("甘州", 100.4, 38.9),     # 张掖
        ("肃州", 98.5, 39.7),      # 酒泉
    ],
    "高丽": [("开京", 126.62, 37.97), ("西京", 125.75, 39.03)],
    "日本": [("平安京", 135.77, 35.01), ("奈良", 135.83, 34.69), ("大宰府", 130.55, 33.52)],
}

# ============================================================
# 三·五、周边政权内部分路（省级以下再分一级）
#    键 = 母政权 id（须在 REGIME_GEO 注册）；值 = 分路列表，每项：
#      name     分路名
#      seat     治所名
#      seat_at  [经,纬] 治所点位
#      polygon  分路多边形（与母政权铺满、共享边不重叠；允许开环存储）
#      label_at [经,纬] 标注点
#      owner    当前归属（初始=母政权 id；地名是地名，地可易主——
#               宋取燕云只改南京道/西京道 owner，辽其余诸道仍辽）
#    整体易主（金崛起代辽）用 set_regime_owner(cascade=True) 级联改写；
#    金激活后可照此追加五京道（扩展点，本次未实现）。
# ============================================================
REGIME_SUBDIVISIONS: dict[str, list[dict[str, object]]] = {
    "辽": [
        {"name": "西京道", "owner": "辽", "seat": "大同府", "seat_at": [113.3, 40.1],
         "label_at": [113.9, 40.7],
         "polygon": [[112.8, 41.5], [115.0, 41.5], [115.0, 39.9],
                      [113.2, 41.2], [112.8, 41.5]]},
        {"name": "南京道", "owner": "辽", "seat": "析津府", "seat_at": [116.4, 39.9],
         "label_at": [116.9, 41.0],
         "polygon": [[115.0, 41.5], [119.0, 42.5], [118.5, 40.3],
                      [115.0, 39.9], [115.0, 41.5]]},
        {"name": "上京道", "owner": "辽", "seat": "临潢府", "seat_at": [119.4, 43.9],
         "label_at": [116.5, 44.8],
         "polygon": [[112.8, 41.5], [113.5, 44.5], [117.5, 46.5],
                      [122.0, 48.0], [121.5, 44.5], [119.0, 42.5],
                      [115.0, 41.5], [112.8, 41.5]]},
        {"name": "中京道", "owner": "辽", "seat": "大定府", "seat_at": [120.2, 41.6],
         "label_at": [119.3, 41.9],
         "polygon": [[115.0, 41.5], [119.0, 42.5], [121.5, 44.5],
                      [124.5, 40.8], [121.8, 39.8], [118.5, 40.3],
                      [115.0, 41.5]]},
        {"name": "东京道", "owner": "辽", "seat": "辽阳府", "seat_at": [123.2, 41.3],
         "label_at": [126.0, 43.9],
         "polygon": [[121.5, 44.5], [122.0, 48.0], [126.5, 49.5],
                      [131.0, 49.0], [133.5, 46.5], [131.5, 43.5],
                      [128.0, 42.0], [124.5, 40.8], [121.8, 39.8],
                      [121.5, 44.5]]},
    ],
    "西夏": [
        {"name": "河西走廊", "owner": "西夏", "seat": "甘州", "seat_at": [100.4, 38.9],
         "label_at": [99.8, 39.3],
         "polygon": [[96.5, 39.5], [97.0, 40.5], [99.5, 41.5],
                      [103.0, 40.5], [102.8, 38.0], [100.0, 37.0],
                      [97.5, 38.5], [96.5, 39.5]]},
        {"name": "兴庆府直辖", "owner": "西夏", "seat": "兴庆府", "seat_at": [106.3, 38.5],
         "label_at": [104.3, 38.9],
         "polygon": [[102.8, 38.0], [103.0, 40.5], [104.8, 40.6],
                      [105.8, 38.8], [105.8, 37.2], [103.5, 36.2],
                      [102.8, 38.0]]},
        {"name": "河南地", "owner": "西夏", "seat": "韦州", "seat_at": [106.0, 37.2],
         "label_at": [105.3, 37.1],
         "polygon": [[105.8, 37.2], [106.4, 38.6], [106.4, 36.3],
                      [105.3, 36.0], [103.5, 36.2], [105.8, 37.2]]},
    ],
    # "金": [  # 扩展点：金激活（timeline break）后照此追加五京道
    #     ...
    # ],
}

# ============================================================
# 四、游戏单位 → 行政归属映射（由 CIRCUIT_INFO 单源派生）
#    键 = PREFECTURE_LIST 稳定 ID（content.data，不可改）；
#    值 = {circuit 路, type 路类, seat 治所, label_at [经,纬] 标注点}。
#    label_at 取治所坐标；治所不在 members 时回退为 None（校验函数会报出）。
# ============================================================
def _build_prefecture_admin() -> dict[str, dict[str, object]]:
    admin: dict[str, dict[str, object]] = {}
    for circuit, info in CIRCUIT_INFO.items():
        unit = info.get("game_unit")
        if not unit:
            continue  # 未单列经济单位的路：钱粮随邻路分摊，不入归属映射
        seat = info["seat"]
        label_at = None
        for name, _lvl, lon, lat in info["members"]:
            if name == seat:
                label_at = [lon, lat]
                break
        admin[unit] = {
            "circuit": circuit,
            "type": info["type"],
            "seat": seat,
            "label_at": label_at,
        }
    return admin


PREFECTURE_ADMIN: dict[str, dict[str, object]] = _build_prefecture_admin()


# ============================================================
# 五、查询 API（只读，无副作用；UI/AI 一律经此取数，禁止直改表）
# ============================================================
def circuit_of(game_unit: str) -> str | None:
    """游戏经济/军事单位 → 所隶路名；未知单位返回 None。"""
    entry = PREFECTURE_ADMIN.get(game_unit)
    if not entry:
        return None
    circuit = entry.get("circuit")
    return circuit if isinstance(circuit, str) else None


def game_unit_of(circuit: str) -> str | None:
    """路名 → 对应游戏单位键；未单列（game_unit=None）返回 None。"""
    info = CIRCUIT_INFO.get(circuit)
    return info["game_unit"] if info else None


def members_of(circuit: str) -> list[tuple[str, str, float, float]]:
    """路名 → 成员 [(府/州名, 等级, 经度, 纬度), ...]；未知路返回空表。"""
    info = CIRCUIT_INFO.get(circuit)
    return list(info["members"]) if info else []


def all_city_points() -> list[dict[str, object]]:
    """全部府/州/军治所点位（去重前为 CIRCUIT_INFO 展平）。

    返回 [{name, level, circuit, game_unit, lon, lat}, ...]，
    供 GeoJSON 城市点层与命中测试消费。
    """
    points: list[dict[str, object]] = []
    for circuit, info in CIRCUIT_INFO.items():
        unit = info.get("game_unit")
        for name, level, lon, lat in info["members"]:
            points.append({
                "name": name, "level": level, "circuit": circuit,
                "game_unit": unit, "lon": lon, "lat": lat,
            })
    return points


def regime_geo(regime: str) -> dict[str, object] | None:
    """周边政权键（对齐 EXTERNAL_REGIMES / EXTERNAL_FORCES）→ 疆域条目。"""
    return REGIME_GEO.get(regime)


def active_regimes() -> list[str]:
    """当前已激活（active=True）的政权键列表，保持注册表顺序。"""
    return [k for k, v in REGIME_GEO.items() if v.get("active")]


def subdivisions_of(regime_id: str) -> list[dict[str, object]]:
    """政权 id → 内部分路列表（深拷贝，防调用方改表）；无分路返回空表。

    分路自持 owner（初始=母政权），易主后可与母政权不同；改归属用
    set_subdivision_owner / set_regime_owner，勿直接改本表。
    """
    subs = REGIME_SUBDIVISIONS.get(regime_id)
    return [dict(s) for s in subs] if subs else []


_KNOWN_OWNERS = frozenset({"宋"})  # 运行期再并入 REGIME_GEO 键


def _owner_known(owner: str) -> bool:
    return owner in _KNOWN_OWNERS or owner in REGIME_GEO


def set_subdivision_owner(sub_name: str, owner: str) -> bool:
    """分路单独易主（如宋北伐取燕云：set_subdivision_owner("南京道", "宋")）。

    按分路名全局唯一定位；成功返回 True，分路不存在或 owner 未知返回 False。
    """
    if not _owner_known(owner):
        return False
    for subs in REGIME_SUBDIVISIONS.values():
        for sub in subs:
            if sub.get("name") == sub_name:
                sub["owner"] = owner
                return True
    return False


def set_regime_owner(regime_id: str, owner: str, cascade: bool = True) -> bool:
    """政权整体易主。cascade=True 时其全部分路一并改写（金崛起代辽）；
    cascade=False 只改母政权本体（分路保留各自归属，用于部分征服后的残余）。
    政权不存在或 owner 未知返回 False。
    """
    if regime_id not in REGIME_GEO or not _owner_known(owner):
        return False
    REGIME_GEO[regime_id]["owner"] = owner
    if cascade:
        for sub in REGIME_SUBDIVISIONS.get(regime_id, []):
            sub["owner"] = owner
    return True


# ============================================================
# 六、一致性校验（启动/构建期调用；返回问题清单，空表=通过）
#    不抛异常、不静默修复——问题交由调用方决定失败策略。
# ============================================================
def validate_geo() -> list[str]:
    problems: list[str] = []

    def _ring_closed(pts: list[list[float]]) -> bool:
        return len(pts) >= 4 and pts[0] == pts[-1]

    def _in_view(pts: list[list[float]]) -> bool:
        return all(MAP_VIEW["west"] - 5 <= x <= MAP_VIEW["east"] + 5
                   and MAP_VIEW["south"] - 5 <= y <= MAP_VIEW["north"] + 5
                   for x, y in pts)

    # 1) 归属映射键集 == PREFECTURE_LIST（延迟导入，保持本模块可独立加载）
    try:
        from content.data import PREFECTURE_LIST
        missing = [u for u in PREFECTURE_LIST if u not in PREFECTURE_ADMIN]
        extra = [u for u in PREFECTURE_ADMIN if u not in PREFECTURE_LIST]
        if missing:
            problems.append(f"PREFECTURE_ADMIN 缺游戏单位: {missing}")
        if extra:
            problems.append(f"PREFECTURE_ADMIN 多出未知单位: {extra}")
    except Exception as exc:  # 独立加载（如纯构建环境）时跳过该项
        problems.append(f"跳过 PREFECTURE_LIST 对齐校验: {exc!r}")

    # 2) CIRCUIT_BOUNDS 与 CIRCUIT_INFO 键一致；坐标在视野内。
    #    路界允许开环存储（隐式闭合），GeoJSON 输出前由 build_map_geo 补首点。
    for key in CIRCUIT_INFO:
        if key not in CIRCUIT_BOUNDS:
            problems.append(f"CIRCUIT_BOUNDS 缺路界: {key}")
    for key, ring in CIRCUIT_BOUNDS.items():
        if key not in CIRCUIT_INFO:
            problems.append(f"CIRCUIT_BOUNDS 多出未知路: {key}")
        if len(ring) < 3:
            problems.append(f"路界顶点不足 3 个: {key}")
        if not _in_view(ring):
            problems.append(f"路界坐标超出 MAP_VIEW 容差: {key}")

    # 3) REGIME_GEO 多边形闭合；active 键须在 data 侧注册
    for key, geo in REGIME_GEO.items():
        poly = geo.get("polygon") or []
        if not geo.get("use_parts"):  # use_parts 政权几何由拼合产物承担,无 polygon 合法
            if not poly:
                problems.append(f"政权疆域缺 polygon: {key}")
            elif not _ring_closed(poly):
                problems.append(f"政权疆域未闭合(首尾点须相同): {key}")
            if not _in_view(poly):
                problems.append(f"政权疆域坐标超出 MAP_VIEW 容差: {key}")
        if geo.get("active") and geo.get("owner") != key:
            problems.append(f"激活政权 owner 与键不一致: {key} owner={geo.get('owner')}")
    try:
        from content.data import EXTERNAL_FORCES, EXTERNAL_REGIMES
        known = set(EXTERNAL_REGIMES) | set(EXTERNAL_FORCES)
        orphan = [k for k in REGIME_GEO if k not in known]
        if orphan:
            problems.append(f"REGIME_GEO 键未在 data 注册: {orphan}")
    except Exception as exc:
        problems.append(f"跳过政权注册对齐校验: {exc!r}")

    # 4) 治所必须能定位到成员坐标（label_at 非 None）
    for unit, entry in PREFECTURE_ADMIN.items():
        if entry["label_at"] is None:
            problems.append(f"治所 {entry['seat']} 不在 {entry['circuit']} 成员表中: {unit}")

    # 5) REGIME_SUBDIVISIONS：母政权存在、多边形闭合、坐标在视野内
    for key, subs in REGIME_SUBDIVISIONS.items():
        if key not in REGIME_GEO:
            problems.append(f"分路母政权未在 REGIME_GEO 注册: {key}")
            continue
        for sub in subs:
            sname = sub.get("name", "?")
            tag = f"{key}/{sname}"
            poly = sub.get("polygon")
            if not isinstance(poly, list) or not poly:
                problems.append(f"分路缺 polygon: {tag}")
            else:
                if not _ring_closed(poly):
                    problems.append(f"分路多边形未闭合(首尾点须相同): {tag}")
                if not _in_view(poly):
                    problems.append(f"分路坐标超出 MAP_VIEW 容差: {tag}")
            if not sub.get("seat"):
                problems.append(f"分路缺治所: {tag}")
            seat_at = sub.get("seat_at")
            if not (isinstance(seat_at, list) and len(seat_at) == 2
                    and all(isinstance(v, (int, float)) for v in seat_at)):
                problems.append(f"分路 seat_at 须为 [经,纬]: {tag}")
            elif not _in_view([seat_at]):
                problems.append(f"分路治所坐标超出 MAP_VIEW 容差: {tag}")
            owner = sub.get("owner")
            if not isinstance(owner, str) or not _owner_known(owner):
                problems.append(f"分路 owner 须为宋或已注册政权: {tag} owner={owner}")

    return problems
