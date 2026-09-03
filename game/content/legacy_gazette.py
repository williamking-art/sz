# -*- coding: utf-8 -*-
"""宋祚 · 开局邸报与待办三事（content/legacy_gazette.py）

仿《明末：捞金模拟器》开局邸报，用文言交代徽宗朝（建中靖国元年）开局局势，
并给出「待办三事」——户部亏空、西夏边患、花石纲民怨等历史包袱与破局目标。

数据驱动风格与 content/data.py 一致（Python 常量，不引入 JSON）。
本模块只定义文本与结构，不写状态；由 core/commands.new_game 生成并注入
state.opening_gazette，供 UI 全屏邸报展示与朝局简报引导。
"""

# 邸报标题（仿宋《邸报》/《朝报》题头）
GAZETTE_HEADER = "大宋邸报"

# 年号与纪元（建中靖国元年，徽宗即位初）
GAZETTE_ERA = "建中靖国元年"

# 邸报正文（文言，交代开局局势）
GAZETTE_BODY = (
    "朕承祖宗之业，嗣守神器，夙夜祗惧，罔敢宁息。"
    "自元祐更化以来，新旧交争，党论纷纭，朝纲未一。"
    "迨至今日，府库空虚，冗官冗费，隐田蔽课，民力已疲。"
    "北有契丹，虎视眈眈；西有夏贼，屡犯边陲。"
    "花石之纲，东南骚动；盐铁之利，尽入私门。"
    "此诚多事之秋，社稷安危，系于朕躬。"
    "惟愿与诸卿共图至治，拨乱反正，以安黎庶，以固邦本。"
)

# 待办三事（开局破局目标）
# 每项：{key, title, desc, goto(跳转语义), urgent}
# goto 语义与 core/briefing.py 对齐：decree/audience/tech/army/todo
OPENING_TASKS = [
    {
        "key": "treasury_deficit",
        "title": "户部亏空",
        "desc": "府库空虚，岁入不敷岁出，冗官冗费积重难返。宜开源节流，理盐铁、裁冗费、清隐田，以实国库。",
        "goto": "decree",
        "urgent": True,
    },
    {
        "key": "western_border",
        "title": "西夏边患",
        "desc": "夏贼屡犯西陲，陕西、河东边烽有警。宜整军经武、修城储粮、备边严守，以固疆圉。",
        "goto": "army",
        "urgent": True,
    },
    {
        "key": "huashigang_grievance",
        "title": "花石纲民怨",
        "desc": "东南花石纲扰民，民怨沸腾，隐田蔽课，士绅抗税。宜宽恤民力、清丈田亩、平抑物价，以安民心。",
        "goto": "decree",
        "urgent": False,
    },
]

# 邸报落款（仿邸报题署）
GAZETTE_SIGN = "门下省 录呈 御前"

# 开局提示（UI 展示用，简短）
OPENING_HINT = "建中靖国元年，陛下初登大宝，天下多事，宜早定国策，以安社稷。"


def build_opening_gazette() -> dict:
    """构建开局邸报数据结构（供 new_game 注入 state.opening_gazette）。

    返回：
      {
        "header": 邸报标题,
        "era": 年号,
        "body": 正文,
        "tasks": [待办三事...],
        "footer": 落款,
        "hint": 开局提示,
        "shown": False,   # UI 是否已展示（首次开局全屏展示后置 True）
      }
    """
    return {
        "header": GAZETTE_HEADER,
        "era": GAZETTE_ERA,
        "body": GAZETTE_BODY,
        "tasks": [dict(t) for t in OPENING_TASKS],
        "footer": OPENING_HINT,
        "hint": OPENING_HINT,
        "shown": False,
    }


__all__ = [
    "GAZETTE_HEADER", "GAZETTE_ERA", "GAZETTE_BODY",
    "OPEN_TASKS", "OPENING_HINT", "build_opening_gazette",
]