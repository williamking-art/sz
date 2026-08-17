# -*- coding: utf-8 -*-
"""大臣独立数据模块。

设计目标：
- 大臣数量会持续扩充，故单列文件夹，新增大臣只需在此追加一条 + 放一张立绘。
- 每位大臣含后台「忠诚度 loyalty」初值（0.0 离心 ~ 1.0 死忠），该数值不可见，
  仅在 AI 推演与后台结算中使用，绝不进入任何 UI 文本。
- 中枢机构树 / 事权归属表一并置于此处，供改制类圣旨推演。
"""
import os

_BASE = os.path.dirname(os.path.abspath(__file__))
PORTRAIT_DIR = os.path.join(_BASE, "portraits")

# ============================================================
# 大臣档案（中枢 + 地方核心）
#   born      生年
#   role      职衔/定位
#   faction   派系
#   traits    性格特征
#   portrait  立绘文件名（置于 portraits/ 下）；留空则按 kind 回退
#   in_office 建中靖国元年(1101)是否在朝/已起用：True=已在任，False=在野/未起用/未生
#             供「按年份筛人」与后续历史进程启用。开局中枢 lead 仅取 in_office=True 者。
#   loyalty   开局忠诚度（后台隐藏，不可见）
#   corruption 开局贪腐度（后台隐藏，不可见）：0.0 清廉 ~ 1.0 贪墨极甚；
#             仅用于制度/圣旨后事件推演，绝不进入任何 UI 文本。
# ============================================================
# 开局年代：建中靖国元年（1101），徽宗刚登基、推行「调停」路线。
#   在任核心：韩忠彦(左相/旧党)、曾布(右相/东南士人) —— 中枢实权。
#   蔡京已在朝(任翰林学士承旨)但未为相(1102崇宁才拜相)；童贯初近幸未掌兵；
#   台谏陈瓘/陈师锡/丰稷在任弹蔡京；西军种师道等在边。
#   蔡攸/王黼/梁师成/朱勔/杨戬/高俅/余深/林摅/郑居中/何执中/张商英/侯蒙等均政和/宣和
#   才得势，1101标注 in_office=False(在野/未起用)，不任中枢 lead，待历史进程启用。
# ============================================================
MINISTERS = {
    # ===================== 中枢实权（1101 在任） =====================
    "韩忠彦": {"born": 1038, "role": "左相(尚书左仆射兼门下侍郎)", "faction": "旧党", "traits": "老成/调停/守正",
               "portrait": "", "in_office": True, "loyalty": 0.42, "corruption": 0.30},
    "曾布":   {"born": 1036, "role": "右相(尚书右仆射兼中书侍郎)", "faction": "东南士人", "traits": "权谋/善变/理财",
               "portrait": "", "in_office": True, "loyalty": 0.55, "corruption": 0.40},
    "蔡京":   {"born": 1047, "role": "在野(1101被贬,1102崇宁拜相)", "faction": "新党", "traits": "权谋/聚敛/书法",
               "portrait": "", "in_office": False, "loyalty": 0.85, "corruption": 0.78},
    "李清臣": {"born": 1032, "role": "门下侍郎(1101十月罢)", "faction": "旧党", "traits": "文士/持重",
               "portrait": "", "in_office": True, "loyalty": 0.40, "corruption": 0.28},
    "赵挺之": {"born": 1040, "role": "御史中丞", "faction": "旧党", "traits": "刚峭/与蔡京不合",
               "portrait": "", "in_office": True, "loyalty": 0.40, "corruption": 0.32},
    "邓洵武": {"born": 1055, "role": "吏部侍郎/枢密都承旨", "faction": "新党", "traits": "绍述/崇宁党人碑",
               "portrait": "", "in_office": True, "loyalty": 0.76, "corruption": 0.50},

    # ===================== 台谏（1101 在任，弹蔡京） =====================
    "陈瓘":   {"born": 1057, "role": "右司谏", "faction": "清流言官", "traits": "刚直/弹蔡京/谪贬",
               "portrait": "", "in_office": True, "loyalty": 0.46, "corruption": 0.12},
    "陈师锡": {"born": 1057, "role": "殿中侍御史", "faction": "清流言官", "traits": "清正/论事切直",
               "portrait": "", "in_office": True, "loyalty": 0.48, "corruption": 0.14},
    "丰稷":   {"born": 1033, "role": "殿中侍御史(1101被黜改任)", "faction": "清流言官", "traits": "鲠亮/极论蔡京",
               "portrait": "", "in_office": True, "loyalty": 0.50, "corruption": 0.10},

    # ===================== 宦官（1101 初近幸，未掌大权） =====================
    "童贯":   {"born": 1054, "role": "供奉官/初近幸(未掌兵)", "faction": "宦官集团", "traits": "军略/逢迎/宦官",
               "portrait": "", "in_office": True, "loyalty": 0.80, "corruption": 0.60},

    # ===================== 西军（1101 在边） =====================
    "种师道": {"born": 1051, "role": "西军将领/后统帅", "faction": "西军集团", "traits": "老成/忠勇/将略",
               "portrait": "", "in_office": True, "loyalty": 0.74, "corruption": 0.30},
    "姚古":   {"born": 1058, "role": "西军将领", "faction": "西军集团", "traits": "宿将/累战",
               "portrait": "", "in_office": True, "loyalty": 0.68, "corruption": 0.32},
    "刘延庆": {"born": 1060, "role": "泾原将", "faction": "西军集团", "traits": "庸怯/拥兵",
               "portrait": "", "in_office": True, "loyalty": 0.62, "corruption": 0.40},
    "刘法":   {"born": 1055, "role": "熙河将", "faction": "西军集团", "traits": "骁勇/战殁",
               "portrait": "", "in_office": True, "loyalty": 0.70, "corruption": 0.28},

    # ===================== 主战/忠义（1101 在，未显） =====================
    "李纲":   {"born": 1083, "role": "太学/主战派", "faction": "清流言官", "traits": "刚直/主战/抗金",
               "portrait": "", "in_office": True, "loyalty": 0.58, "corruption": 0.15},
    "宗泽":   {"born": 1060, "role": "地方官/后抗金", "faction": "清流言官", "traits": "忠勇/抗金",
               "portrait": "", "in_office": True, "loyalty": 0.62, "corruption": 0.18},
    "张叔夜": {"born": 1065, "role": "知海州(1101降地方官,非开封府尹)", "faction": "清流言官", "traits": "忠义/守城",
               "portrait": "", "in_office": True, "loyalty": 0.64, "corruption": 0.22},
    "韩世忠": {"born": 1089, "role": "低级军官", "faction": "西军集团", "traits": "悍勇/水战",
               "portrait": "", "in_office": True, "loyalty": 0.60, "corruption": 0.35},

    # ===================== 皇子（1101 在） =====================
    "赵桓":   {"born": 1100, "role": "皇长子", "faction": "无", "traits": "平庸",
               "portrait": "", "in_office": True, "loyalty": 0.66, "corruption": 0.20},
    "赵楷":   {"born": 1101, "role": "皇子", "faction": "无", "traits": "才华/夺嫡心",
               "portrait": "", "in_office": True, "loyalty": 0.30, "corruption": 0.40},

    # ===================== 1101 中枢佐贰/新任（考据确证） =====================
    # 注：以下人物于建中靖国元年确证在任，补全中枢佐贰官，供「补佐贰/新建官职」推演。
    "蒋之奇": {"born": 1031, "role": "知枢密院事", "faction": "东南士人", "traits": "干练/通军务/善理财",
               "portrait": "", "in_office": True, "loyalty": 0.58, "corruption": 0.35},
    "章楶":   {"born": 1027, "role": "同知枢密院事", "faction": "西军集团", "traits": "宿将/边防老成",
               "portrait": "", "in_office": True, "loyalty": 0.62, "corruption": 0.20},
    "陆佃":   {"born": 1042, "role": "尚书左丞", "faction": "旧党", "traits": "守正/博学/调停",
               "portrait": "", "in_office": True, "loyalty": 0.46, "corruption": 0.25},
    "温益":   {"born": 1037, "role": "尚书右丞", "faction": "新党", "traits": "圆滑/阿附/多机变",
               "portrait": "", "in_office": True, "loyalty": 0.72, "corruption": 0.45},
    "吴居厚": {"born": 1037, "role": "知开封府", "faction": "新党", "traits": "聚敛/明达政务/吏干",
               "portrait": "", "in_office": True, "loyalty": 0.70, "corruption": 0.50},
    "王古":   {"born": 1040, "role": "户部尚书", "faction": "东南士人", "traits": "理财/慎密/循良",
               "portrait": "", "in_office": True, "loyalty": 0.55, "corruption": 0.28},
    "江公望": {"born": 1055, "role": "右司谏", "faction": "清流言官", "traits": "敢言/讽谏/守正",
               "portrait": "", "in_office": True, "loyalty": 0.50, "corruption": 0.12},
    "陈次升": {"born": 1044, "role": "左谏议大夫", "faction": "清流言官", "traits": "鲠直/弹劾/论蔡京",
               "portrait": "", "in_office": True, "loyalty": 0.48, "corruption": 0.12},

    # ===================== 地方大员（1101 已入仕） =====================
    "唐恪":   {"born": 1057, "role": "地方大员/后入中枢", "faction": "东南士人", "traits": "干练/后主和",
               "portrait": "", "in_office": True, "loyalty": 0.52, "corruption": 0.30},
    "聂昌":   {"born": 1068, "role": "地方大员", "faction": "东南士人", "traits": "峻急/敢任事",
               "portrait": "", "in_office": True, "loyalty": 0.54, "corruption": 0.28},

    # ===================== 在野/未起用（政和/宣和才得势，in_office=False） =====================
    "蔡攸":   {"born": 1077, "role": "在野(蔡京之子)", "faction": "新党", "traits": "骄奢/佞幸/揽权",
               "portrait": "", "in_office": False, "loyalty": 0.82, "corruption": 0.72},
    "何执中": {"born": 1044, "role": "在野", "faction": "新党", "traits": "圆滑/持重/附蔡",
               "portrait": "", "in_office": False, "loyalty": 0.78, "corruption": 0.55},
    "郑居中": {"born": 1059, "role": "在野(外戚)", "faction": "新党", "traits": "恭俭/善逢迎/外戚",
               "portrait": "", "in_office": False, "loyalty": 0.76, "corruption": 0.50},
    "余深":   {"born": 1050, "role": "在野", "faction": "新党", "traits": "柔佞/唯蔡京马首",
               "portrait": "", "in_office": False, "loyalty": 0.80, "corruption": 0.60},
    "王黼":   {"born": 1079, "role": "在野(后少宰)", "faction": "新党", "traits": "巧佞/聚敛/好大喜功",
               "portrait": "", "in_office": False, "loyalty": 0.74, "corruption": 0.75},
    "朱勔":   {"born": 1075, "role": "在野(后花石纲)", "faction": "新党", "traits": "搜括/花石纲/媚上",
               "portrait": "", "in_office": False, "loyalty": 0.78, "corruption": 0.85},
    "林摅":   {"born": 1050, "role": "在野(后刑部尚书)", "faction": "新党", "traits": "苛酷/附新法",
               "portrait": "", "in_office": False, "loyalty": 0.70, "corruption": 0.55},
    "张商英": {"born": 1043, "role": "在野(被贬)", "faction": "新党", "traits": "能臣/变法/才高",
               "portrait": "", "in_office": False, "loyalty": 0.60, "corruption": 0.35},
    "梁师成": {"born": 1063, "role": "在野(后掌书命)", "faction": "宦官集团", "traits": "狡黠/掌书命/豫政",
               "portrait": "", "in_office": False, "loyalty": 0.76, "corruption": 0.72},
    "杨戬":   {"born": 1058, "role": "在野(后措置房)", "faction": "宦官集团", "traits": "搜括/营田/聚敛",
               "portrait": "", "in_office": False, "loyalty": 0.74, "corruption": 0.70},
    "高俅":   {"born": 1068, "role": "殿前都指挥使", "faction": "宦官集团", "traits": "蹴鞠/典禁军/怙宠",
               "portrait": "", "in_office": True, "loyalty": 0.72, "corruption": 0.55},
    "侯蒙":   {"born": 1054, "role": "在野(后户部尚书)", "faction": "清流言官", "traits": "通达/敢言/识人才",
               "portrait": "", "in_office": False, "loyalty": 0.50, "corruption": 0.18},

    # ===================== 未生（1101 尚未出生） =====================
    "岳飞":   {"born": 1103, "role": "未生(未来名将)", "faction": "西军集团", "traits": "精忠/神勇/军神",
               "portrait": "", "in_office": False, "loyalty": 0.50, "corruption": 0.10},
}

# 派系统一档案：忠诚基线 / 贪腐基线 / 立绘分类 聚合为单条记录（唯一权威源）。
# 各字段「无/未知派系」兜底互不相同，必须各自独立，严禁合并共享。
FACTION_PROFILES = {
    "新党":     {"loyalty": 0.82, "corruption": 0.70, "kind": "civil"},
    "宦官集团": {"loyalty": 0.78, "corruption": 0.66, "kind": "eunuch"},
    "西军集团": {"loyalty": 0.70, "corruption": 0.35, "kind": "military"},
    "旧党":     {"loyalty": 0.28, "corruption": 0.30, "kind": "civil"},
    "东南士人": {"loyalty": 0.52, "corruption": 0.45, "kind": "civil"},
    "清流言官": {"loyalty": 0.40, "corruption": 0.18, "kind": "civil"},
}

# 只读派生别名（保持既有引用与数值不变，新增派系只需改 FACTION_PROFILES 一处）
_FACTION_LOYALTY_BASE = {f: p["loyalty"] for f, p in FACTION_PROFILES.items()}
_FACTION_CORRUPTION_BASE = {f: p["corruption"] for f, p in FACTION_PROFILES.items()}


def _init_field(field, no_faction_default, unknown_default, base) -> dict:
    """从 MINISTERS 构造某隐藏数值字段：显式值优先，否则按派系基线/缺省。

    注意：no_faction_default（无派系缺省）与 unknown_default（未知派系兜底）
    是两个独立值，各字段必须显式传入自己的二元组，严禁共享，否则改变初始数值。
    """
    out = {}
    for name, fig in MINISTERS.items():
        if field in fig and fig[field] is not None:
            out[name] = fig[field]
        else:
            fac = fig.get("faction", "无")
            out[name] = no_faction_default if fac == "无" else base.get(fac, unknown_default)
    return out


def loyalty_init() -> dict:
    """构造开局忠诚度字典：以 MINISTERS 中显式 loyalty 为准，缺省按派系基线。"""
    return _init_field("loyalty", 0.55, 0.5, _FACTION_LOYALTY_BASE)


def corruption_init() -> dict:
    """构造开局贪腐度字典：以 MINISTERS 中显式 corruption 为准，缺省按派系基线。

    0.0 清廉 ~ 1.0 贪墨极甚；该数值后台隐藏，绝不进入任何 UI 文本。
    """
    return _init_field("corruption", 0.25, 0.3, _FACTION_CORRUPTION_BASE)


# ============================================================
# 中枢机构树（宋制，供改制类圣旨推演）
#
# 重要原则：权限跟随「机构/职位」，不跟随「人」。
#   lead        该职位「当前在任者」占位（仅用于推演时查其忠诚度；
#               换人后此字段随任职变动，机构权限本身不变）
#   belong      上级机构/皇帝
#   scope       机构定位
#   authority   该机构「固有事权」——属职位，不属个人（改制改的就是这一层）
#   matter_keys 关联事权 key（见 AUTHORITY_MATTERS）
#
# 宋制财政逻辑（关键，1101 元丰改制后）：
#   - 财政事权（国库、钱粮户籍、赋税）本属「户部」——六部之一，尚书省下辖。
#   - 「三司」已于元丰改制（1080）裁撤，其「度支/盐铁/户部三衙」理财执行并入户部。
#     故 1101 年不存在三司，度支调度/盐铁专营/财政勾稽三件事权 owner 归户部。
#   - 六部（吏户礼兵刑工）是尚书省下辖的「实际执行政务」部门，必须单独列出。
#
# 权限模型（三层分离，职权重构核心）：
#   posts      本机构「岗位表」：每岗 title（职位名），属机构本身，不随人。
#   holders    人岗映射：{岗位title: 在任大臣名}。换人不变权——换人只改 holders。
#   comissions 本机构当前「差遣」列表：差遣职权跟「差遣本体」，交差即撤、事权归还机构。
#   lead       兼容字段 = posts[0] 岗位的现任 holder（仅作旧接口引用，不承载权限）。
# ============================================================
CENTRAL_ORG_INFO = {
    # ---- 三省：决策/审议/执行（建中靖国：韩忠彦左相、曾布右相主政）----
    "中书省":   {"belong": "皇帝", "scope": "决策/除授",
                 "authority": ["官制", "人事除授", "朝政决策"],
                 "matter_keys": ["官制", "人事除授", "朝政决策"],
                 "posts": [{"title": "中书侍郎"}],
                 "holders": {"中书侍郎": "曾布"}, "comissions": []},
    "门下省":   {"belong": "皇帝", "scope": "封驳/审议",
                 "authority": ["诏令封驳", "政令审议"],
                 "matter_keys": ["诏令封驳", "政令审议"],
                 "posts": [{"title": "门下侍郎"}],
                 "holders": {"门下侍郎": "李清臣"}, "comissions": []},
    "尚书省":   {"belong": "皇帝", "scope": "总领六部/奉行",
                 "authority": ["六部行政", "政令奉行"],
                 "matter_keys": ["六部行政", "政令奉行"],
                 "posts": [{"title": "尚书左仆射"}, {"title": "尚书右仆射"},
                           {"title": "尚书左丞"}, {"title": "尚书右丞"}],
                 "holders": {"尚书左仆射": "韩忠彦", "尚书右仆射": "曾布",
                             "尚书左丞": "陆佃", "尚书右丞": "温益"}, "comissions": []},

    # ---- 六部：尚书省下辖的实际执行部门（1101 在任者，各配尚书+侍郎佐贰）----
    "吏部":     {"belong": "尚书省", "scope": "官吏铨选/考课",
                 "authority": ["官吏铨选", "官员考课"],
                 "matter_keys": ["官吏铨选"],
                 "posts": [{"title": "吏部尚书"}, {"title": "吏部侍郎"}],
                 "holders": {"吏部尚书": "邓洵武", "吏部侍郎": ""}, "comissions": []},
    "户部":     {"belong": "尚书省", "scope": "财政/户籍/国库/度支盐铁勾稽",
                 "authority": ["国库", "钱粮户籍", "赋税", "度支调度", "盐铁专营", "财政勾稽"],
                 "matter_keys": ["国库", "钱粮户籍", "度支调度", "盐铁专营", "财政勾稽"],
                 "posts": [{"title": "户部尚书"}, {"title": "户部侍郎"}],
                 "holders": {"户部尚书": "王古", "户部侍郎": ""}, "comissions": []},
    "礼部":     {"belong": "尚书省", "scope": "礼仪/科举/外事",
                 "authority": ["礼仪", "科举", "外事"],
                 "matter_keys": ["礼仪", "科举", "外事"],
                 "posts": [{"title": "礼部尚书"}, {"title": "礼部侍郎"}],
                 "holders": {"礼部尚书": "", "礼部侍郎": ""}, "comissions": []},
    "兵部":     {"belong": "尚书省", "scope": "武官/军籍/后勤",
                 "authority": ["武官铨选", "军籍", "军需后勤"],
                 "matter_keys": ["武官铨选", "军籍", "军需后勤"],
                 "posts": [{"title": "兵部尚书"}, {"title": "兵部侍郎"}],
                 "holders": {"兵部尚书": "", "兵部侍郎": ""}, "comissions": []},
    "刑部":     {"belong": "尚书省", "scope": "刑名/狱讼",
                 "authority": ["刑狱", "律令"],
                 "matter_keys": ["刑狱"],
                 "posts": [{"title": "刑部尚书"}, {"title": "刑部侍郎"}],
                 "holders": {"刑部尚书": "", "刑部侍郎": ""}, "comissions": []},
    "工部":     {"belong": "尚书省", "scope": "工程/营造/屯田",
                 "authority": ["工程营造", "屯田", "山泽"],
                 "matter_keys": ["工程营造"],
                 "posts": [{"title": "工部尚书"}, {"title": "工部侍郎"}],
                 "holders": {"工部尚书": "", "工部侍郎": ""}, "comissions": []},

    # ---- 枢密院与三衙：军务（蒋之奇知院事、章楶同知；三衙高俅领殿前）----
    "枢密院":   {"belong": "皇帝", "scope": "军国机务/兵防",
                 "authority": ["调兵", "边防", "军务机要"],
                 "matter_keys": ["调兵", "边防", "军务机要"],
                 "posts": [{"title": "知枢密院事"}, {"title": "同知枢密院事"}],
                 "holders": {"知枢密院事": "蒋之奇", "同知枢密院事": "章楶"}, "comissions": []},
    "殿前司":   {"belong": "枢密院", "scope": "禁军统制",
                 "authority": ["禁军", "京城防务"],
                 "matter_keys": ["禁军", "京城防务"],
                 "posts": [{"title": "殿前都指挥使"}, {"title": "殿前副都指挥使"}],
                 "holders": {"殿前都指挥使": "高俅", "殿前副都指挥使": ""}, "comissions": []},
    "侍卫亲军马军司": {"belong": "枢密院", "scope": "禁军马军",
                 "authority": ["禁军", "北边防务"],
                 "matter_keys": ["禁军", "北边防务"],
                 "posts": [{"title": "马军都指挥使"}, {"title": "马军副都指挥使"}],
                 "holders": {"马军都指挥使": "", "马军副都指挥使": ""}, "comissions": []},
    "侍卫亲军步军司": {"belong": "枢密院", "scope": "禁军步军",
                 "authority": ["禁军", "内地屯驻"],
                 "matter_keys": ["禁军", "内地屯驻"],
                 "posts": [{"title": "步军都指挥使"}, {"title": "步军副都指挥使"}],
                 "holders": {"步军都指挥使": "", "步军副都指挥使": ""}, "comissions": []},

    # ---- 监察与内廷 ----
    "御史台":   {"belong": "皇帝", "scope": "监察/弹劾",
                 "authority": ["监察百官", "弹劾"],
                 "matter_keys": ["监察百官", "弹劾"],
                 "posts": [{"title": "御史中丞"}, {"title": "殿中侍御史"}],
                 "holders": {"御史中丞": "赵挺之", "殿中侍御史": "陈师锡"}, "comissions": []},
    "谏院":     {"belong": "皇帝", "scope": "谏诤/言路",
                 "authority": ["言路", "谏诤"],
                 "matter_keys": ["言路", "谏诤"],
                 "posts": [{"title": "左谏议大夫"}, {"title": "右司谏"}],
                 "holders": {"左谏议大夫": "陈次升", "右司谏": "陈瓘"}, "comissions": []},
    "翰林学士院": {"belong": "皇帝", "scope": "草诏/顾问",
                 "authority": ["草诏", "内制"],
                 "matter_keys": ["草诏", "内制"],
                 "posts": [{"title": "翰林学士承旨"}],
                 "holders": {"翰林学士承旨": "江公望"}, "comissions": []},
    "内侍省":   {"belong": "皇帝", "scope": "内廷/禁中",
                 "authority": ["内廷", "禁中庶务"],
                 "matter_keys": ["内廷", "禁中庶务"],
                 "posts": [{"title": "内侍押班"}],
                 "holders": {"内侍押班": "童贯"}, "comissions": []},

    # ---- 京畿（东京开封府，京畿要职，常由重臣领）----
    "开封府":   {"belong": "皇帝", "scope": "京畿民政/治安",
                 "authority": ["京畿", "京城治安"],
                 "matter_keys": ["京畿"],
                 "posts": [{"title": "知开封府"}, {"title": "开封府少尹"}],
                 "holders": {"知开封府": "吴居厚", "开封府少尹": ""}, "comissions": []},
}

# 事权归属表（开局，用于「改权限/越权授权」推演）
#   事权归属于「机构」（owner），与谁任该职无关；故此处只有 owner，无个人字段。
#   注意：1101 已废三司，度支调度/盐铁专营/财政勾稽 事权 owner 为「户部」。
AUTHORITY_MATTERS = {
    "官制":     {"owner": "中书省"},
    "人事除授": {"owner": "中书省"},
    "诏令封驳": {"owner": "门下省"},
    "六部行政": {"owner": "尚书省"},
    "官吏铨选": {"owner": "吏部"},
    "国库":     {"owner": "户部"},
    "钱粮户籍": {"owner": "户部"},
    "赋税":     {"owner": "户部"},
    "度支调度": {"owner": "户部"},
    "盐铁专营": {"owner": "户部"},
    "财政勾稽": {"owner": "户部"},
    "礼仪":     {"owner": "礼部"},
    "科举":     {"owner": "礼部"},
    "外事":     {"owner": "礼部"},
    "武官铨选": {"owner": "兵部"},
    "军籍":     {"owner": "兵部"},
    "刑狱":     {"owner": "刑部"},
    "工程营造": {"owner": "工部"},
    "调兵":     {"owner": "枢密院"},
    "边防":     {"owner": "枢密院"},
    "监察百官": {"owner": "御史台"},
    "言路":     {"owner": "谏院"},
    "草诏":     {"owner": "翰林学士院"},
    "内廷":     {"owner": "内侍省"},
    "禁军":     {"owner": "殿前司"},
    "京畿":     {"owner": "开封府"},
}

# 改制类型枚举（完全自由，无硬性禁令）
REFORM_TYPES = ["改名", "裁撤", "新建", "新建官职", "改下辖", "改权限", "越权授权"]


def org_lead(info: dict) -> str:
    """由机构 info 推导「主官」：取 posts 首个岗位的现任 holder，缺则回退 ''。
    兼容旧接口：state.central_orgs[org]['lead'] 由此字段派生，不直接承载权限。
    """
    holders = info.get("holders") or {}
    posts = info.get("posts") or []
    if posts:
        first_title = posts[0].get("title") if isinstance(posts[0], dict) else posts[0]
        if first_title in holders:
            return holders[first_title]
    return ""


# 派系 → 立绘分类（供 get_portrait_path 在无个人立绘时按类回退默认图）。
# 由 FACTION_PROFILES 派生，保持单一权威源；未知派系独立兜底 "civil"（勿借数值兜底）。
_FACTION_KIND = {f: p["kind"] for f, p in FACTION_PROFILES.items()}
_KIND_DEFAULT = "civil"
# 皇子/宗室特例（role 含"皇"字视为 royal）
_ROYAL_ROLE_HINT = ("皇子", "皇长子", "亲王", "宗室")


def _minister_kind(name: str) -> str:
    """按派系/role 推断大臣立绘分类，供回退默认图使用。"""
    fig = MINISTERS.get(name, {})
    role = fig.get("role", "")
    if any(h in role for h in _ROYAL_ROLE_HINT):
        return "royal"
    return _FACTION_KIND.get(fig.get("faction", ""), _KIND_DEFAULT)


def get_portrait_path(name: str, kind: str = None):
    """返回大臣立绘绝对路径；接口已预留分类回退，资源未到位时回退 None。

    查找优先级：
      1. 大臣档案显式 ``portrait`` 文件名（如有且存在）
      2. 个人立绘 ``portraits/{name}.png``（未来放入即可启用）
      3. 分类默认图 ``portraits/{kind}.png``（kind 缺省按派系/role 自动推断：
         civil / military / eunuch / royal）——放入即自动启用
    任一命中即返回路径；全缺返回 None，由上层按 UI 默认处理。
    """
    fig = MINISTERS.get(name, {})
    candidates = []
    if fig.get("portrait"):
        candidates.append(fig["portrait"])
    candidates.append(f"{name}.png")
    if kind is None:
        kind = _minister_kind(name)
    candidates.append(f"{kind}.png")
    for fname in candidates:
        path = os.path.join(PORTRAIT_DIR, fname)
        if os.path.isfile(path):
            return path
    return None
