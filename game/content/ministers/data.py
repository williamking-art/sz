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
# ============================================================
# 爵位体系（Nobility）：宋代封爵参照史实（王/郡王/国公/郡公/县公/侯/伯/子/男）。
# 规则：爵位是「身分性荣誉」，不随官职罢黜而消失（贬谪在野仍保留爵位）；
#       官品是「职事官阶」，随在任而定——在野/贬谪/未起用者不具官品（留空）。
#   nobility  爵位称号（含史实建中靖国元年已封者与皇子皇弟身份爵）；未封者留空 ""
#   rank      职事官品（"正一品"/"从一品"/"正二品"/"从二品"/"正三品"/"从三品"/"正四品"/"从四品"/"正五品"…）
#             in_office=False 者 rank 一律留空 ""（在野无官品，只有爵位或白身）
# ============================================================
MINISTERS = {
    # ===================== 中枢实权（1101 在任） =====================
    "韩忠彦": {"born": 1038, "role": "左相(尚书左仆射兼门下侍郎)", "faction": "旧党", "traits": "老成/调停/守正",
               "nobility": "仪国公", "rank": "正一品",
               "portrait": "", "in_office": True, "loyalty": 0.42, "corruption": 0.30, "trait_ids": ["调停"]},
    "曾布":   {"born": 1036, "role": "右相(尚书右仆射兼中书侍郎)", "faction": "东南士人", "traits": "权谋/善变/理财",
               "nobility": "鲁国公", "rank": "正一品",
               "portrait": "", "in_office": True, "loyalty": 0.55, "corruption": 0.40, "trait_ids": ["权谋", "理财"]},
    "蔡京":   {"born": 1047, "role": "在野(1101被贬,1102崇宁拜相)", "faction": "新党", "traits": "权谋/聚敛/书法",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.85, "corruption": 0.78, "trait_ids": ["聚敛", "变法", "才艺"]},
    "李清臣": {"born": 1032, "role": "门下侍郎(1101十月罢)", "faction": "旧党", "traits": "文士/持重",
               "nobility": "", "rank": "从一品",
               "portrait": "", "in_office": True, "loyalty": 0.40, "corruption": 0.28, "trait_ids": ["调停"]},
    "赵挺之": {"born": 1040, "role": "御史中丞", "faction": "旧党", "traits": "刚峭/与蔡京不合",
               "nobility": "", "rank": "从二品",
               "portrait": "", "in_office": True, "loyalty": 0.40, "corruption": 0.32},
    "邓洵武": {"born": 1055, "role": "吏部侍郎/枢密都承旨", "faction": "新党", "traits": "绍述/崇宁党人碑",
               "nobility": "", "rank": "从二品",
               "portrait": "", "in_office": True, "loyalty": 0.76, "corruption": 0.50, "trait_ids": ["权谋", "变法"]},

    # ===================== 台谏（1101 在任，弹蔡京） =====================
    "陈瓘":   {"born": 1057, "role": "右司谏", "faction": "清流言官", "traits": "刚直/弹蔡京/谪贬",
               "nobility": "", "rank": "从四品",
               "portrait": "", "in_office": True, "loyalty": 0.46, "corruption": 0.12, "trait_ids": ["刚直"]},
    "陈师锡": {"born": 1057, "role": "殿中侍御史", "faction": "清流言官", "traits": "清正/论事切直",
               "nobility": "", "rank": "从四品",
               "portrait": "", "in_office": True, "loyalty": 0.48, "corruption": 0.14, "trait_ids": ["清正"]},
    "丰稷":   {"born": 1033, "role": "殿中侍御史(1101被黜改任)", "faction": "清流言官", "traits": "鲠亮/极论蔡京",
               "nobility": "", "rank": "从四品",
               "portrait": "", "in_office": True, "loyalty": 0.50, "corruption": 0.10, "trait_ids": ["刚直", "清正"]},

    # ===================== 宦官（1101 初近幸，未掌大权） =====================
    "童贯":   {"born": 1054, "role": "供奉官/初近幸(未掌兵)", "faction": "宦官集团", "traits": "军略/逢迎/宦官",
               "nobility": "", "rank": "正五品",
               "portrait": "", "in_office": True, "loyalty": 0.80, "corruption": 0.60},

    # ===================== 西军（1101 在边） =====================
    "种师道": {"born": 1051, "role": "西军将领/后统帅", "faction": "西军集团", "traits": "老成/忠勇/将略",
               "nobility": "", "rank": "正四品",
               "portrait": "", "in_office": True, "loyalty": 0.74, "corruption": 0.30, "trait_ids": ["军略"]},
    "姚古":   {"born": 1058, "role": "西军将领", "faction": "西军集团", "traits": "宿将/累战",
               "nobility": "", "rank": "正四品",
               "portrait": "", "in_office": True, "loyalty": 0.68, "corruption": 0.32, "trait_ids": ["军略"]},
    "刘延庆": {"born": 1060, "role": "泾原将", "faction": "西军集团", "traits": "庸怯/拥兵",
               "nobility": "", "rank": "正五品",
               "portrait": "", "in_office": True, "loyalty": 0.62, "corruption": 0.40, "trait_ids": ["怯懦"]},
    "刘法":   {"born": 1055, "role": "熙河将", "faction": "西军集团", "traits": "骁勇/战殁",
               "nobility": "", "rank": "正四品",
               "portrait": "", "in_office": True, "loyalty": 0.70, "corruption": 0.28, "trait_ids": ["军略"]},

    # ===================== 主战/忠义（1101 在，未显） =====================
    "李纲":   {"born": 1083, "role": "太学/主战派", "faction": "清流言官", "traits": "刚直/主战/抗金",
               "nobility": "", "rank": "从八品",
               "portrait": "", "in_office": True, "loyalty": 0.58, "corruption": 0.15, "trait_ids": ["忠勇"]},
    "宗泽":   {"born": 1060, "role": "地方官/后抗金", "faction": "清流言官", "traits": "忠勇/抗金",
               "nobility": "", "rank": "从六品",
               "portrait": "", "in_office": True, "loyalty": 0.62, "corruption": 0.18, "trait_ids": ["忠勇"]},
    "张叔夜": {"born": 1065, "role": "知海州(1101降地方官,非开封府尹)", "faction": "清流言官", "traits": "忠义/守城",
               "nobility": "", "rank": "从六品",
               "portrait": "", "in_office": True, "loyalty": 0.64, "corruption": 0.22, "trait_ids": ["忠勇"]},
    "韩世忠": {"born": 1089, "role": "低级军官", "faction": "西军集团", "traits": "悍勇/水战",
               "nobility": "", "rank": "正九品",
               "portrait": "", "in_office": True, "loyalty": 0.60, "corruption": 0.35, "trait_ids": ["忠勇"]},

    # ===================== 皇子（1101 在）—— 皇子以亲王身份爵为尊 =====================
    "赵桓":   {"born": 1100, "role": "皇长子", "faction": "无", "traits": "平庸",
               "nobility": "京兆郡王", "rank": "",
               "portrait": "", "in_office": True, "loyalty": 0.66, "corruption": 0.20},
    "赵楷":   {"born": 1101, "role": "皇子", "faction": "无", "traits": "才华/夺嫡心",
               "nobility": "嘉王", "rank": "",
               "portrait": "", "in_office": True, "loyalty": 0.30, "corruption": 0.40, "trait_ids": ["才艺"]},

    # ===================== 1101 中枢佐贰/新任（考据确证） =====================
    # 注：以下人物于建中靖国元年确证在任，补全中枢佐贰官，供「补佐贰/新建官职」推演。
    "蒋之奇": {"born": 1031, "role": "知枢密院事", "faction": "东南士人", "traits": "干练/通军务/善理财",
               "nobility": "", "rank": "从一品",
               "portrait": "", "in_office": True, "loyalty": 0.58, "corruption": 0.35, "trait_ids": ["理财"]},
    "章楶":   {"born": 1027, "role": "同知枢密院事", "faction": "西军集团", "traits": "宿将/边防老成",
               "nobility": "", "rank": "正二品",
               "portrait": "", "in_office": True, "loyalty": 0.62, "corruption": 0.20, "trait_ids": ["军略"]},
    "陆佃":   {"born": 1042, "role": "尚书左丞", "faction": "旧党", "traits": "守正/博学/调停",
               "nobility": "", "rank": "从二品",
               "portrait": "", "in_office": True, "loyalty": 0.46, "corruption": 0.25, "trait_ids": ["调停"]},
    "温益":   {"born": 1037, "role": "尚书右丞", "faction": "新党", "traits": "圆滑/阿附/多机变",
               "nobility": "", "rank": "从二品",
               "portrait": "", "in_office": True, "loyalty": 0.72, "corruption": 0.45, "trait_ids": ["权谋"]},
    "吴居厚": {"born": 1037, "role": "知开封府", "faction": "新党", "traits": "聚敛/明达政务/吏干",
               "nobility": "", "rank": "从三品",
               "portrait": "", "in_office": True, "loyalty": 0.70, "corruption": 0.50, "trait_ids": ["聚敛"]},
    "王古":   {"born": 1040, "role": "户部尚书", "faction": "东南士人", "traits": "理财/慎密/循良",
               "nobility": "", "rank": "正二品",
               "portrait": "", "in_office": True, "loyalty": 0.55, "corruption": 0.28, "trait_ids": ["理财"]},
    "江公望": {"born": 1055, "role": "右司谏", "faction": "清流言官", "traits": "敢言/讽谏/守正",
               "nobility": "", "rank": "从四品",
               "portrait": "", "in_office": True, "loyalty": 0.50, "corruption": 0.12, "trait_ids": ["刚直"]},
    "陈次升": {"born": 1044, "role": "左谏议大夫", "faction": "清流言官", "traits": "鲠直/弹劾/论蔡京",
               "nobility": "", "rank": "正三品",
               "portrait": "", "in_office": True, "loyalty": 0.48, "corruption": 0.12, "trait_ids": ["刚直"]},

    # ===================== 地方大员（1101 已入仕） =====================
    "唐恪":   {"born": 1057, "role": "地方大员/后入中枢", "faction": "东南士人", "traits": "干练/后主和",
               "nobility": "", "rank": "从三品",
               "portrait": "", "in_office": True, "loyalty": 0.52, "corruption": 0.30},
    "聂昌":   {"born": 1068, "role": "地方大员", "faction": "东南士人", "traits": "峻急/敢任事",
               "nobility": "", "rank": "从四品",
               "portrait": "", "in_office": True, "loyalty": 0.54, "corruption": 0.28},

    # ===================== 在野/未起用（政和/宣和才得势，in_office=False） =====================
    # 规则铁律：在野/贬谪者不具职事官品（rank=""），若史实已封爵则保留爵位，未封者彻底白身。
    "蔡攸":   {"born": 1077, "role": "在野(蔡京之子)", "faction": "新党", "traits": "骄奢/佞幸/揽权",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.82, "corruption": 0.72, "trait_ids": ["揽权"]},
    "何执中": {"born": 1044, "role": "在野", "faction": "新党", "traits": "圆滑/持重/附蔡",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.78, "corruption": 0.55},
    "郑居中": {"born": 1059, "role": "在野(外戚)", "faction": "新党", "traits": "恭俭/善逢迎/外戚",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.76, "corruption": 0.50, "trait_ids": ["阿附"]},
    "余深":   {"born": 1050, "role": "在野", "faction": "新党", "traits": "柔佞/唯蔡京马首",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.80, "corruption": 0.60, "trait_ids": ["阿附"]},
    "王黼":   {"born": 1079, "role": "在野(后少宰)", "faction": "新党", "traits": "巧佞/聚敛/好大喜功",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.74, "corruption": 0.75, "trait_ids": ["聚敛", "揽权"]},
    "朱勔":   {"born": 1075, "role": "在野(后花石纲)", "faction": "新党", "traits": "搜括/花石纲/媚上",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.78, "corruption": 0.85, "trait_ids": ["聚敛"]},
    "林摅":   {"born": 1050, "role": "在野(后刑部尚书)", "faction": "新党", "traits": "苛酷/附新法",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.70, "corruption": 0.55, "trait_ids": ["阿附"]},
    "张商英": {"born": 1043, "role": "在野(被贬)", "faction": "新党", "traits": "能臣/变法/才高",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.60, "corruption": 0.35, "trait_ids": ["变法"]},
    "梁师成": {"born": 1063, "role": "在野(后掌书命)", "faction": "宦官集团", "traits": "狡黠/掌书命/豫政",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.76, "corruption": 0.72, "trait_ids": ["阿附", "揽权"]},
    "杨戬":   {"born": 1058, "role": "在野(后措置房)", "faction": "宦官集团", "traits": "搜括/营田/聚敛",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.74, "corruption": 0.70, "trait_ids": ["聚敛"]},
    "高俅":   {"born": 1068, "role": "殿前都指挥使", "faction": "宦官集团", "traits": "蹴鞠/典禁军/怙宠",
               "nobility": "", "rank": "从二品",
               "portrait": "", "in_office": True, "loyalty": 0.72, "corruption": 0.55, "trait_ids": ["才艺"]},
    "侯蒙":   {"born": 1054, "role": "在野(后户部尚书)", "faction": "清流言官", "traits": "通达/敢言/识人才",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.50, "corruption": 0.18, "trait_ids": ["清正"]},

    # ===================== 未生（1101 尚未出生） =====================
    "岳飞":   {"born": 1103, "role": "未生(未来名将)", "faction": "西军集团", "traits": "精忠/神勇/军神",
               "nobility": "", "rank": "",
               "portrait": "", "in_office": False, "loyalty": 0.50, "corruption": 0.10},
}

# 未在素材 2.2 标注特质的大臣，trait_ids 统一补空列表（不臆造，待考据单补齐）；
# 已显式标注者见上（字段在档案内）。保证全部大臣均带 trait_ids 字段（机制层引用 TRAITS 键）。
for _name, _fig in MINISTERS.items():
    _fig.setdefault("trait_ids", [])

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


# ============================================================
# 大臣特质表（A3 落地，素材 a6_narrative_materials.md 第 2.2 节）
#
#   TRAITS = {特质id: {kind, desc, effects: {场景: 档位}, note}}
#   kind: moral 品性 / political 政术 / fiscal 财政 / military 军事 / talent 才艺
#   effects 全部为档位词（无/微/小/中/大，可带 +/-），数值换算归 content.data.TIER_RANGE
#   （单一权威源），本表只承载"机制影响描述"；实际换算/触发由 core 侧按场景调用
#   （本期已落地离任场景 apply_minister_departure）。
#   三标签：代表大臣=史实概括；机制影响=玩法抽象。
# ============================================================
TRAITS = {
    "刚直": {"kind": "moral", "desc": "不避权贵、直言敢谏",
             "effects": {"谏诤弹劾_言路": "小", "因言获罪_清流": "-大"},
             "note": "代表：陈瓘、陈次升、江公望、丰稷"},
    "清正": {"kind": "moral", "desc": "廉洁自律、循规守法",
             "effects": {"机构_贪腐": "-微", "贪墨案_免于牵连": "特殊"},
             "note": "代表：丰稷、陈师锡、侯蒙"},
    "权谋": {"kind": "political", "desc": "善纵横捭阖、结党营私",
             "effects": {"朝争_派系手段": "小", "改制_党争分歧": "微"},
             "note": "代表：曾布、邓洵武、温益"},
    "理财": {"kind": "fiscal", "desc": "精于调度、通晓钱谷",
             "effects": {"财政事件_treasury": "小", "户部_效率": "微"},
             "note": "代表：曾布、王古、蒋之奇"},
    "聚敛": {"kind": "fiscal", "desc": "搜括民财以媚上",
             "effects": {"聚敛事件_treasury": "小", "聚敛事件_民怨": "-小"},
             "note": "代表：蔡京、朱勔、杨戬、吴居厚、王黼"},
    "军略": {"kind": "military", "desc": "晓畅军事、善守善攻",
             "effects": {"西线防御_defense": "小", "边事_主战": "叙事"},
             "note": "代表：章楶、种师道、姚古、刘法"},
    "忠勇": {"kind": "military", "desc": "忠义敢战、临难不避",
             "effects": {"战事_army士气": "小", "敌军压境_不降": "叙事"},
             "note": "代表：李纲、宗泽、张叔夜、韩世忠"},
    "怯懦": {"kind": "military", "desc": "临战畏葸、避战保全",
             "effects": {"军事事件_army": "-小", "兵临城下_乞和": "叙事"},
             "note": "代表：刘延庆"},
    "阿附": {"kind": "political", "desc": "逢迎圣意、揣摩上心",
             "effects": {"圣旨_执行效率": "小", "朝局_腐化": "微", "清流_厌恶": "叙事"},
             "note": "代表：余深、林摅、郑居中、梁师成"},
    "调停": {"kind": "political", "desc": "持重守中、弥合两党",
             "effects": {"党争_调停选项": "小", "两派_满意度回落": "微"},
             "note": "代表：韩忠彦、陆佃、李清臣"},
    "变法": {"kind": "political", "desc": "笃信新法、绍述熙丰",
             "effects": {"新法事件_推进": "小", "旧党_满意度": "-微"},
             "note": "代表：邓洵武、张商英、蔡京（附）"},
    "揽权": {"kind": "political", "desc": "权力欲强、私植党羽",
             "effects": {"人事_安插亲信": "叙事", "同僚_冲突": "微", "权臣事件_派系": "小"},
             "note": "代表：蔡攸、王黼、梁师成"},
    "才艺": {"kind": "talent", "desc": "翰墨丹青、文采风流",
             "effects": {"艺术翰林_art_mastery": "微", "诏书_文风": "叙事"},
             "note": "代表：蔡京（书法）、赵楷、高俅（蹴鞠彩蛋）"},
}

# 生涯标记（素材 2.2 注：不属于"特质"，不参与机制换算，防"玩家改变不了史实结局"的挫败；
# 仅供叙事/考据查询，不进入 trait_ids 机制引用）
FATE_MARKS = {
    "战殁": {"desc": "史实中阵亡于边事",
             "note": "军事事件阵亡概率修正（叙事层，非玩家可干预）；代表：刘法（史实战殁于统安城之役）"},
}

# ============================================================
# 离任影响表（A3 落地，素材 2.3 节）
#
#   DEPARTURE_RULES = {reason: {
#       prestige / treasury / faction_satisfaction: 档位词（可带 +/-，无=不生效）,
#       specials: [{when: 判定条件, effects: {目标: 档位词}}],   # 条件修饰
#       handle: 岗位处理描述,
#   }}
#   when 判定口径（apply_minister_departure 写死，可审查）：
#     清流言官=大臣派系；权臣=corruption≥0.6；老臣=(当前年-born)≥60；
#     名将=含「军略/忠勇」特质；惩贪=corruption≥0.5（处死）；冤杀=其余处死。
#   目标键：派系名→派系满意度；"corruption"→隐藏贪腐度（0-1 刻度微调）；"边境士气"→defense_bonus。
#   离任数值化=玩法抽象；因果修饰=合理推演；离任事实（某人某年贬/殁）待考据单逐人核卷。
# ============================================================
DEPARTURE_RULES = {
    "贬黜": {"prestige": "-微", "treasury": "无", "faction_satisfaction": "-小",
             "handle": "清岗，依官制补缺",
             "specials": [
                 {"when": "清流言官", "effects": {"清流言官": "-大"}},
                 {"when": "权臣", "effects": {"新党": "-中"}},
             ]},
    "致仕": {"prestige": "-微", "treasury": "-微", "faction_satisfaction": "-微",
             "handle": "清岗，补缺",
             "specials": [{"when": "老臣", "effects": {"东南士人": "微"}}]},
    "病故": {"prestige": "-微", "treasury": "无", "faction_satisfaction": "-微",
             "handle": "清岗，补缺", "specials": []},
    "战殁": {"prestige": "-小", "treasury": "无", "faction_satisfaction": "-大",
             "handle": "清岗，西军同袍接任（推演）",
             "specials": [{"when": "名将", "effects": {"西军集团": "-大", "边境士气": "-小"}}]},
    "处死": {"prestige": "无", "treasury": "无", "faction_satisfaction": "-中",
             "handle": "清岗，补缺 + 派系失衡风险",
             "specials": [
                 {"when": "惩贪", "effects": {"清流言官": "微", "corruption": "-微"}},
                 {"when": "冤杀", "effects": {"清流言官": "-大"}},
             ]},
    "乞休": {"prestige": "无", "treasury": "无", "faction_satisfaction": "-微",
             "handle": "清岗，补缺", "specials": []},
}


def traits_of(name: str) -> list:
    """大臣机制特质引用（MINISTERS[name].trait_ids → TRAITS 键）。

    展示层 traits（自由文本字符串）保留不动；本函数只读机制层。
    未标注特质的大臣返回 []（不臆造，待考据单补齐）。
    """
    return list(MINISTERS.get(name, {}).get("trait_ids", []))


def departure_effects(reason: str) -> dict:
    """离任原因 → 影响规则 dict（档位词，未换算；数值换算归 core 侧）。

    未知原因返回 {}（调用方安全失败）。
    """
    return DEPARTURE_RULES.get(reason, {})
