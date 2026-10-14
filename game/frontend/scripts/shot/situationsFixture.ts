// 截图台 situations fixture（**仅 dev 用**）——由**真实后端口径单点**产出，非手写：
//   `core.situations.build_situation_readout(state)`（`backend/server.py:888` 的同源调用；
//   state = commands.new_game()，seed=20261013，先跑 6 个月结算）。
//   ⚠️ 重新生成见本目录 README；**不要手改数字**（口径单点）。生成日期：2026-10-14（M271）

export const SITUATIONS = {
  "items": [
    {
      "id": "legacy:hidden_land",
      "title": "隐田蔽课",
      "source": "legacy",
      "status": "active",
      "bar_value": 0,
      "resolve_condition_text": "解除：清丈田亩，检括隐田（施行 land_survey）。",
      "fail_condition_text": null,
      "ongoing_text": null,
      "progress_text": null,
      "severity": 90,
      "phase": "起",
      "region_hint": null,
      "faction_hint": null,
      "pop_highlights": null,
      "timeline": [
        {
          "turn": 6,
          "kind": "报",
          "text": "[修正] 隐田蔽课：豪强隐田，赋税隐匿，岁入有亏（减收计入二税折色）",
          "source": "program"
        }
      ],
      "execution_channels": null,
      "channel_highlights": null
    },
    {
      "id": "legacy:redundant_officials",
      "title": "冗官冗费",
      "source": "legacy",
      "status": "active",
      "bar_value": 0,
      "resolve_condition_text": "解除：裁汰冗官冗费（施行 curtail_waste）。",
      "fail_condition_text": null,
      "ongoing_text": null,
      "progress_text": null,
      "severity": 90,
      "phase": "起",
      "region_hint": null,
      "faction_hint": null,
      "pop_highlights": null,
      "timeline": [
        {
          "turn": 6,
          "kind": "报",
          "text": "[修正] 冗官冗费：官冗于上、吏冗于下，俸给浩繁，府库日耗（成本计入官俸/吏俸）",
          "source": "program"
        }
      ],
      "execution_channels": null,
      "channel_highlights": null
    },
    {
      "id": "event_pool:liaoshi_bianbei",
      "title": "辽事边备",
      "source": "record",
      "status": "active",
      "bar_value": 20,
      "progress_mode": "bar",
      "resolve_condition_text": "看【北线城防与欠饷】：河北路与河东路军心 ≥50 且欠饷 ≤10 万贯，连续 2 月 → 解除",
      "fail_condition_text": "北线军心 <30 或欠饷 ≥30 万贯激成兵变，或燕云失守 → 立即失败",
      "ongoing_text": "国库 −8 万/月（边饷）、军心 −1/月",
      "bar_good_meaning": "边备渐修",
      "bar_bad_meaning": "烽火告警",
      "progress_text": null,
      "severity": 82,
      "phase": "起",
      "region_hint": "河北",
      "faction_hint": null,
      "pop_highlights": null,
      "timeline": [
        {
          "turn": 1,
          "kind": "报",
          "text": "资财不足，本月暂缓（落点未注册：effects[1]: 未注册路径 'army_morale'（首批白名单见 SITUATION_EFFECT_PATHS））",
          "source": "program"
        },
        {
          "turn": 2,
          "kind": "报",
          "text": "资财不足，本月暂缓（落点未注册：effects[1]: 未注册路径 'army_morale'（首批白名单见 SITUATION_EFFECT_PATHS））",
          "source": "program"
        },
        {
          "turn": 3,
          "kind": "报",
          "text": "资财不足，本月暂缓（落点未注册：effects[1]: 未注册路径 'army_morale'（首批白名单见 SITUATION_EFFECT_PATHS））",
          "source": "program"
        },
        {
          "turn": 4,
          "kind": "报",
          "text": "资财不足，本月暂缓（落点未注册：effects[1]: 未注册路径 'army_morale'（首批白名单见 SITUATION_EFFECT_PATHS））",
          "source": "program"
        },
        {
          "turn": 5,
          "kind": "报",
          "text": "资财不足，本月暂缓（落点未注册：effects[1]: 未注册路径 'army_morale'（首批白名单见 SITUATION_EFFECT_PATHS））",
          "source": "program"
        }
      ],
      "execution_channels": {
        "strong": "clerks",
        "clerks_mult": 0.9418,
        "clerks_grievance": 13.42,
        "clerks_grip": 0.1662,
        "clerks_quality": "案牍清明",
        "official_support": {
          "proxy": true,
          "weighted": 58.01,
          "min": 51.91,
          "min_faction": "旧党"
        },
        "civil_mult": 0.9022,
        "kind": "军政",
        "military_mult": null,
        "military_applies": true,
        "military_route": "河北",
        "military_reason": "军政/边事类诏令（军队天然参与）；但无驻军读数（未计入）",
        "combined_mult": 0.8497,
        "faction_min": 51.91,
        "faction_min_name": "旧党",
        "note": "吏治（强）折扣 ×0.94；民心/识字率（弱）×0.90；军队督行：无驻军读数（未计入）"
      },
      "channel_highlights": [
        "吏怨 13.4，政令折扣 ×0.94",
        "军心 63、欠饷 710,733 贯（督行 ×0.72）"
      ]
    },
    {
      "id": "event_pool:huashigang_minyuan",
      "title": "花石纲民怨",
      "source": "record",
      "status": "active",
      "bar_value": 25,
      "progress_mode": "bar",
      "resolve_condition_text": "看【花石纲抽分】：两浙路与江南东路民心 ≥55 且动乱 ≤30，连续 2 月 → 解除",
      "fail_condition_text": "两浙路或江南东路动乱 ≥85 且民心 ≤30，或激起民变破州县 → 立即失败",
      "ongoing_text": "国库 −5 万/月（应奉局靡费）、东南民心 −2/月",
      "bar_good_meaning": "民怨渐平",
      "bar_bad_meaning": "东南鼎沸",
      "progress_text": null,
      "severity": 80,
      "phase": "起",
      "region_hint": "东南",
      "faction_hint": null,
      "pop_highlights": null,
      "timeline": [
        {
          "turn": 1,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-50000：treasury [situati(-50000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        },
        {
          "turn": 2,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-50000：treasury [situati(-50000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        },
        {
          "turn": 3,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-50000：treasury [situati(-50000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        },
        {
          "turn": 4,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-50000：treasury [situati(-50000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        },
        {
          "turn": 5,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-50000：treasury [situati(-50000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        }
      ],
      "execution_channels": {
        "strong": "clerks",
        "clerks_mult": 0.9418,
        "clerks_grievance": 13.42,
        "clerks_grip": 0.1662,
        "clerks_quality": "案牍清明",
        "official_support": {
          "proxy": true,
          "weighted": 58.01,
          "min": 51.91,
          "min_faction": "旧党"
        },
        "civil_mult": 0.9022,
        "kind": "民政",
        "military_mult": null,
        "military_applies": false,
        "military_route": "东南",
        "military_reason": "民政诏令，未调兵（军队不参与）",
        "combined_mult": 0.8497,
        "faction_min": 51.91,
        "faction_min_name": "旧党",
        "note": "吏治（强）折扣 ×0.94；民心/识字率（弱）×0.90；军队不参与（民政诏令，未调兵）"
      },
      "channel_highlights": [
        "吏怨 13.4，政令折扣 ×0.94",
        "军心 63、欠饷 710,733 贯（督行 ×0.72）"
      ]
    },
    {
      "id": "event_pool:dongnan_caikui",
      "title": "东南财政亏空",
      "source": "record",
      "status": "active",
      "bar_value": 30,
      "progress_mode": "bar",
      "resolve_condition_text": "看【国库上月实绩】：结余 ≥0 则 +10/月；连续 3 月盈余 → 解除",
      "fail_condition_text": "国库见底致刚性支出违约（欠饷哗变/官俸断发/宗禄拖欠）→ 立即失败",
      "ongoing_text": "国库 −10 万/月（亏空利息）、民心 −1/月",
      "bar_good_meaning": "财用渐丰",
      "bar_bad_meaning": "太仓见底",
      "progress_text": null,
      "severity": 78,
      "phase": "起",
      "region_hint": null,
      "faction_hint": null,
      "pop_highlights": null,
      "timeline": [
        {
          "turn": 1,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-100000：treasury [situati(-100000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        },
        {
          "turn": 2,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-100000：treasury [situati(-100000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        },
        {
          "turn": 3,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-100000：treasury [situati(-100000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        },
        {
          "turn": 4,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-100000：treasury [situati(-100000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        },
        {
          "turn": 5,
          "kind": "报",
          "text": "资财不足，本月暂缓（money 组守恒失败 ΣΔ=-100000：treasury [situati(-100000) 缺来源——请补充成对变更（reason: 税征/俸给划转））",
          "source": "program"
        }
      ],
      "execution_channels": {
        "strong": "clerks",
        "clerks_mult": 0.9418,
        "clerks_grievance": 13.42,
        "clerks_grip": 0.1662,
        "clerks_quality": "案牍清明",
        "official_support": {
          "proxy": true,
          "weighted": 58.01,
          "min": 51.91,
          "min_faction": "旧党"
        },
        "civil_mult": 0.9022,
        "kind": "民政",
        "military_mult": null,
        "military_applies": false,
        "military_route": null,
        "military_reason": "民政诏令，未调兵（军队不参与）",
        "combined_mult": 0.8497,
        "faction_min": 51.91,
        "faction_min_name": "旧党",
        "note": "吏治（强）折扣 ×0.94；民心/识字率（弱）×0.90；军队不参与（民政诏令，未调兵）"
      },
      "channel_highlights": [
        "吏怨 13.4，政令折扣 ×0.94",
        "军心 63、欠饷 710,733 贯（督行 ×0.72）"
      ]
    },
    {
      "id": "legacy:huashigang_grievance",
      "title": "花石纲民怨",
      "source": "legacy",
      "status": "active",
      "bar_value": 80,
      "resolve_condition_text": "解除：停罢花石纲（stop_huashigang）或民心恢复至 60 以上。",
      "fail_condition_text": null,
      "ongoing_text": null,
      "progress_text": null,
      "severity": 58,
      "phase": "终前",
      "region_hint": null,
      "faction_hint": null,
      "pop_highlights": null,
      "timeline": [
        {
          "turn": 6,
          "kind": "报",
          "text": "[局势] 花石纲民怨：资财不足，暂缓",
          "source": "program"
        }
      ],
      "execution_channels": null,
      "channel_highlights": null
    },
    {
      "id": "legacy:liao_xia_border",
      "title": "辽夏边患",
      "source": "legacy",
      "status": "resolved",
      "bar_value": 100,
      "resolve_condition_text": "解除：整军经武（border_garrison）或与辽夏和议（peace_treaty）。",
      "fail_condition_text": null,
      "ongoing_text": null,
      "progress_text": null,
      "severity": 50,
      "phase": "终前",
      "region_hint": null,
      "faction_hint": null,
      "pop_highlights": null,
      "timeline": [],
      "execution_channels": null,
      "channel_highlights": null
    },
    {
      "id": "legacy:new_party_dominance",
      "title": "新党专权",
      "source": "legacy",
      "status": "resolved",
      "bar_value": 100,
      "resolve_condition_text": "解除：调和新旧党争，使党争缓和（faction_conflict 归零）。",
      "fail_condition_text": null,
      "ongoing_text": null,
      "progress_text": null,
      "severity": 50,
      "phase": "终前",
      "region_hint": null,
      "faction_hint": null,
      "pop_highlights": null,
      "timeline": [],
      "execution_channels": null,
      "channel_highlights": null
    }
  ],
  "by_status": {
    "active": 6,
    "resolved": 2
  },
  "pop_channels": {
    "channels": {
      "农": {
        "label": "民心",
        "primary": "region.public_support",
        "secondary": "pop.arrears_ratio",
        "source": "core/region_brief.py + POP 欠税"
      },
      "士绅": {
        "label": "士绅抵抗",
        "primary": "region.gentry_resistance",
        "secondary": "pop.hoard_ratio",
        "source": "core/region_brief.py + POP 窖银"
      },
      "工匠": {
        "label": "工困（市面/欠缴）",
        "primary": "region.fiscal",
        "secondary": "pop.arrears_ratio",
        "source": "core/region_brief.py + POP 欠税"
      },
      "商人": {
        "label": "商情（市面/欠缴）",
        "primary": "region.fiscal",
        "secondary": "pop.arrears_ratio",
        "source": "core/region_brief.py + POP 欠税"
      },
      "官僚": {
        "label": "官心（冗官/派系满意度）",
        "primary": "officials.redundant_rate",
        "secondary": "faction.satisfaction",
        "source": "core/officialdom.py + state.factions"
      },
      "兵": {
        "label": "军心（士气/欠饷）",
        "primary": "army.morale",
        "secondary": "army.enforcement_mult",
        "source": "core/army_models.py"
      },
      "吏": {
        "label": "吏怨/把持度 → 政令折扣",
        "primary": "clerks.route_grievance",
        "secondary": "clerks.execution_mult",
        "source": "core/clerks.py"
      }
    },
    "nation": {
      "农": {
        "民心": {
          "最低": 52.5,
          "均": 57.5
        }
      },
      "士绅": {
        "抵抗": {
          "最低": 29.1,
          "均": 39.6
        },
        "窖藏率": {
          "最低": 0.0,
          "均": 0.0
        }
      },
      "工匠": {
        "市面": {
          "最低": 11.0,
          "均": 34.2
        },
        "欠缴率": {
          "最低": 0.0,
          "均": 0.0
        }
      },
      "商人": {
        "市面": {
          "最低": 11.0,
          "均": 34.2
        },
        "欠缴率": {
          "最低": 0.0,
          "均": 0.0
        }
      },
      "官僚": {
        "冗官率": 0.1627,
        "待阙率": 0.0674,
        "最低派系满意度": 51.91,
        "最低派系": "旧党"
      },
      "兵": {
        "军心": 62.81,
        "欠饷": 710733,
        "督行系数": 0.7237
      },
      "吏": {
        "吏怨": 13.42,
        "把持度": 0.1662,
        "有效吏力": 187125,
        "政令折扣": 0.9418
      },
      "识字率": {
        "全国": 8.41
      }
    },
    "literacy": {
      "nation": {
        "农": 5.36,
        "士绅": 80.73,
        "工匠": 23.58,
        "商人": 34.3,
        "官僚": 97.46,
        "兵": 8.51
      },
      "by_route": {
        "京畿路": {
          "农": 5.43,
          "士绅": 81.37999999999998,
          "工匠": 23.87,
          "商人": 34.72,
          "官僚": 98.0,
          "兵": 8.69
        },
        "京西路": {
          "农": 5.35,
          "士绅": 80.22,
          "工匠": 23.54,
          "商人": 34.24,
          "官僚": 98.0,
          "兵": 8.56
        },
        "京东东路": {
          "农": 5.35,
          "士绅": 80.13,
          "工匠": 23.5,
          "商人": 34.19,
          "官僚": 97.96,
          "兵": 8.56
        },
        "京东西路": {
          "农": 5.35,
          "士绅": 80.13,
          "工匠": 23.5,
          "商人": 34.19,
          "官僚": 97.96000000000001,
          "兵": 8.56
        },
        "河北路": {
          "农": 5.19,
          "士绅": 77.96,
          "工匠": 22.87,
          "商人": 33.26,
          "官僚": 95.64,
          "兵": 8.32
        },
        "河东路": {
          "农": 5.18,
          "士绅": 77.86,
          "工匠": 22.84,
          "商人": 33.22,
          "官僚": 95.51,
          "兵": 8.3
        },
        "陕西路": {
          "农": 5.23,
          "士绅": 78.63999999999999,
          "工匠": 23.07,
          "商人": 33.56,
          "官僚": 96.04,
          "兵": 8.39
        },
        "两浙路": {
          "农": 5.51,
          "士绅": 82.67,
          "工匠": 24.25,
          "商人": 35.28,
          "官僚": 98.0,
          "兵": 8.82
        },
        "江南东路": {
          "农": 5.51,
          "士绅": 82.59,
          "工匠": 24.24,
          "商人": 35.23,
          "官僚": 98.0,
          "兵": 8.82
        },
        "江南西路": {
          "农": 5.51,
          "士绅": 82.59,
          "工匠": 24.24,
          "商人": 35.23,
          "官僚": 98.0,
          "兵": 8.82
        },
        "淮南东路": {
          "农": 5.35,
          "士绅": 80.13,
          "工匠": 23.5,
          "商人": 34.19,
          "官僚": 97.96,
          "兵": 8.56
        },
        "淮南西路": {
          "农": 5.349999999999999,
          "士绅": 80.13,
          "工匠": 23.5,
          "商人": 34.19,
          "官僚": 97.96,
          "兵": 8.56
        },
        "荆湖北路": {
          "农": 5.35,
          "士绅": 80.13,
          "工匠": 23.5,
          "商人": 34.19,
          "官僚": 97.96,
          "兵": 8.56
        },
        "荆湖南路": {
          "农": 5.35,
          "士绅": 80.23,
          "工匠": 23.54,
          "商人": 34.24,
          "官僚": 98.0,
          "兵": 8.56
        },
        "福建路": {
          "农": 5.35,
          "士绅": 80.23000000000002,
          "工匠": 23.54,
          "商人": 34.24,
          "官僚": 98.0,
          "兵": 8.56
        },
        "成都府路": {
          "农": 5.35,
          "士绅": 80.26,
          "工匠": 23.54,
          "商人": 34.25,
          "官僚": 98.0,
          "兵": 8.56
        },
        "利州路": {
          "农": 5.18,
          "士绅": 77.65,
          "工匠": 22.77,
          "商人": 33.13,
          "官僚": 95.26,
          "兵": 8.3
        },
        "夔州路": {
          "农": 5.35,
          "士绅": 80.13,
          "工匠": 23.5,
          "商人": 34.19,
          "官僚": 97.96,
          "兵": 8.56
        },
        "广南东路": {
          "农": 5.35,
          "士绅": 80.23,
          "工匠": 23.54,
          "商人": 34.24,
          "官僚": 98.0,
          "兵": 8.56
        },
        "广南西路": {
          "农": 5.18,
          "士绅": 77.65,
          "工匠": 22.77,
          "商人": 33.13,
          "官僚": 95.26,
          "兵": 8.3
        }
      }
    },
    "by_route": {
      "两浙路": {
        "农": 63.0,
        "士绅": 29.1,
        "工匠": 81.0,
        "商人": 81.0,
        "官僚": 0.1627,
        "兵": 54.33,
        "吏": null,
        "识字率": 9.0
      },
      "京东东路": {
        "农": 57.2,
        "士绅": 41.5,
        "工匠": 29.0,
        "商人": 29.0,
        "官僚": 0.1627,
        "兵": null,
        "吏": null,
        "识字率": 8.2
      },
      "京东西路": {
        "农": 57.2,
        "士绅": 41.6,
        "工匠": 25.0,
        "商人": 25.0,
        "官僚": 0.1627,
        "兵": null,
        "吏": null,
        "识字率": 8.2
      },
      "京畿路": {
        "农": 60.7,
        "士绅": 37.1,
        "工匠": 52.0,
        "商人": 52.0,
        "官僚": 0.1627,
        "兵": 63.0,
        "吏": null,
        "识字率": 8.2
      },
      "京西路": {
        "农": 57.7,
        "士绅": 41.6,
        "工匠": 28.0,
        "商人": 28.0,
        "官僚": 0.1627,
        "兵": 54.33,
        "吏": null,
        "识字率": 8.2
      },
      "利州路": {
        "农": 52.5,
        "士绅": 41.5,
        "工匠": 12.0,
        "商人": 12.0,
        "官僚": 0.1627,
        "兵": null,
        "吏": null,
        "识字率": 7.9
      },
      "夔州路": {
        "农": 57.2,
        "士绅": 41.9,
        "工匠": 11.0,
        "商人": 11.0,
        "官僚": 0.1627,
        "兵": null,
        "吏": null,
        "识字率": 8.2
      },
      "广南东路": {
        "农": 57.7,
        "士绅": 41.5,
        "工匠": 26.0,
        "商人": 26.0,
        "官僚": 0.1627,
        "兵": 54.33,
        "吏": null,
        "识字率": 8.8
      },
      "广南西路": {
        "农": 52.5,
        "士绅": 41.8,
        "工匠": 14.0,
        "商人": 14.0,
        "官僚": 0.1627,
        "兵": null,
        "吏": null,
        "识字率": 7.8
      },
      "成都府路": {
        "农": 57.9,
        "士绅": 42.0,
        "工匠": 35.0,
        "商人": 35.0,
        "官僚": 0.1627,
        "兵": 50.75,
        "吏": null,
        "识字率": 8.8
      },
      "江南东路": {
        "农": 62.5,
        "士绅": 29.4,
        "工匠": 56.0,
        "商人": 56.0,
        "官僚": 0.1627,
        "兵": 54.67,
        "吏": null,
        "识字率": 9.0
      },
      "江南西路": {
        "农": 62.5,
        "士绅": 29.3,
        "工匠": 60.0,
        "商人": 60.0,
        "官僚": 0.1627,
        "兵": 54.67,
        "吏": null,
        "识字率": 9.0
      },
      "河东路": {
        "农": 53.4,
        "士绅": 41.8,
        "工匠": 28.0,
        "商人": 28.0,
        "官僚": 0.1627,
        "兵": 59.4,
        "吏": null,
        "识字率": 7.9
      },
      "河北路": {
        "农": 53.9,
        "士绅": 41.5,
        "工匠": 41.0,
        "商人": 41.0,
        "官僚": 0.1627,
        "兵": 59.62,
        "吏": null,
        "识字率": 7.9
      },
      "淮南东路": {
        "农": 57.2,
        "士绅": 41.9,
        "工匠": 29.0,
        "商人": 29.0,
        "官僚": 0.1627,
        "兵": null,
        "吏": null,
        "识字率": 8.1
      },
      "淮南西路": {
        "农": 57.2,
        "士绅": 41.8,
        "工匠": 25.0,
        "商人": 25.0,
        "官僚": 0.1627,
        "兵": null,
        "吏": null,
        "识字率": 8.1
      },
      "福建路": {
        "农": 57.7,
        "士绅": 41.8,
        "工匠": 42.0,
        "商人": 42.0,
        "官僚": 0.1627,
        "兵": 55.0,
        "吏": null,
        "识字率": 8.8
      },
      "荆湖北路": {
        "农": 57.2,
        "士绅": 41.7,
        "工匠": 28.0,
        "商人": 28.0,
        "官僚": 0.1627,
        "兵": null,
        "吏": null,
        "识字率": 8.1
      },
      "荆湖南路": {
        "农": 57.7,
        "士绅": 41.4,
        "工匠": 30.0,
        "商人": 30.0,
        "官僚": 0.1627,
        "兵": 54.33,
        "吏": null,
        "识字率": 8.1
      },
      "陕西路": {
        "农": 56.8,
        "士绅": 41.5,
        "工匠": 32.0,
        "商人": 32.0,
        "官僚": 0.1627,
        "兵": 73.92,
        "吏": null,
        "识字率": 8.0
      }
    }
  },
  "faction_channels": {
    "factions": {
      "新党": {
        "influence": 27.31,
        "satisfaction": 63.57,
        "cohesion": 67.05,
        "leader": "蔡京",
        "pop_basis": {
          "pop_classes": [
            "官僚"
          ],
          "pool": "officials",
          "routes": null,
          "subset_of": [
            "官僚"
          ],
          "subset_kind": "faction",
          "desc": "变法受益的在朝官——**官僚 POP 在岗官子池中持新法立场的那一部分**（立场按派系而非地域切；地域只是出身）",
          "kind": "policy_network",
          "aliases": [
            "新法系",
            "绍述派",
            "new_law_network"
          ],
          "interests": [
            {
              "pop_class": "官僚",
              "topic": "新法财利与差遣恩泽",
              "direction": 1
            },
            {
              "pop_class": "士绅",
              "topic": "新法政策暴露",
              "direction": 1
            }
          ],
          "red_lines": [
            "废署新法",
            "追夺绍述之政"
          ],
          "subchannels": [],
          "overlaps": [
            "皇党集团"
          ],
          "thresholds": {
            "population_share": 0.05,
            "cohesion": 30,
            "exposure_months": 6
          }
        },
        "basis_readout": {
          "routes": null,
          "routes_count": 20,
          "pop_classes": [
            "官僚"
          ],
          "subset_of": [
            "官僚"
          ],
          "subset_kind": "faction",
          "pool": "officials",
          "pop_size": 11968.6,
          "pool_size": 11968.6,
          "parent_pop_size": 248420,
          "parent_total": 32290,
          "share": 0.3707,
          "subset_note": "新党 ⊆ 官僚 POP · officials 子池（全国），占 37.1%",
          "troops": 0,
          "morale": null,
          "public_support_avg": 57.5,
          "gentry_resistance_avg": 39.6
        },
        "basis_errors": [],
        "display_name": "新法系",
        "kind": "policy_network",
        "aliases": [
          "新法系",
          "绍述派",
          "new_law_network"
        ],
        "interests": [
          {
            "pop_class": "官僚",
            "topic": "新法财利与差遣恩泽",
            "direction": 1
          },
          {
            "pop_class": "士绅",
            "topic": "新法政策暴露",
            "direction": 1
          }
        ],
        "red_lines": [
          "废署新法",
          "追夺绍述之政"
        ],
        "subchannels": [],
        "overlaps": [
          "皇党集团"
        ],
        "thresholds": {
          "population_share": 0.05,
          "cohesion": 30,
          "exposure_months": 6
        }
      },
      "旧党": {
        "influence": 38.09,
        "satisfaction": 51.91,
        "cohesion": 59.18,
        "leader": "韩忠彦",
        "pop_basis": {
          "pop_classes": [
            "士绅",
            "官僚"
          ],
          "pool": null,
          "routes": null,
          "subset_of": [
            "士绅",
            "官僚"
          ],
          "subset_kind": "faction",
          "desc": "持旧法立场的士绅与在朝官——**士绅/官僚 POP 中反对绍述的那一部分**（按立场切，不与任何地域绑定）",
          "kind": "gentry_alliance",
          "aliases": [
            "旧法系",
            "元祐旧臣",
            "元祐党人",
            "yuanyou_old_officials"
          ],
          "interests": [
            {
              "pop_class": "士绅",
              "topic": "田税与隐田",
              "direction": 1
            },
            {
              "pop_class": "士绅",
              "topic": "科举取士",
              "direction": 1
            },
            {
              "pop_class": "官僚",
              "topic": "元祐旧制与差遣",
              "direction": 1
            }
          ],
          "red_lines": [
            "恢复新法",
            "绍述绍圣之政"
          ],
          "subchannels": [],
          "overlaps": [
            "中立派"
          ],
          "thresholds": {
            "population_share": 0.05,
            "cohesion": 25,
            "exposure_months": 6
          }
        },
        "basis_readout": {
          "routes": null,
          "routes_count": 20,
          "pop_classes": [
            "士绅",
            "官僚"
          ],
          "subset_of": [
            "士绅",
            "官僚"
          ],
          "subset_kind": "faction",
          "pool": null,
          "pop_size": 773468.95,
          "pool_size": 773468.95,
          "parent_pop_size": 1646115,
          "parent_total": 1646115,
          "share": 0.4699,
          "subset_note": "旧党 ⊆ 士绅/官僚 POP（全国），占 47.0%",
          "troops": 0,
          "morale": null,
          "public_support_avg": 57.5,
          "gentry_resistance_avg": 39.6
        },
        "basis_errors": [],
        "display_name": "元祐旧臣与保守士绅",
        "kind": "gentry_alliance",
        "aliases": [
          "旧法系",
          "元祐旧臣",
          "元祐党人",
          "yuanyou_old_officials"
        ],
        "interests": [
          {
            "pop_class": "士绅",
            "topic": "田税与隐田",
            "direction": 1
          },
          {
            "pop_class": "士绅",
            "topic": "科举取士",
            "direction": 1
          },
          {
            "pop_class": "官僚",
            "topic": "元祐旧制与差遣",
            "direction": 1
          }
        ],
        "red_lines": [
          "恢复新法",
          "绍述绍圣之政"
        ],
        "subchannels": [],
        "overlaps": [
          "中立派"
        ],
        "thresholds": {
          "population_share": 0.05,
          "cohesion": 25,
          "exposure_months": 6
        }
      },
      "皇党集团": {
        "influence": 15.8,
        "satisfaction": 59.99,
        "cohesion": 65.74,
        "leader": "童贯",
        "pop_basis": {
          "pop_classes": [
            "官僚"
          ],
          "pool": "officials",
          "routes": null,
          "subset_of": [
            "官僚"
          ],
          "subset_kind": "faction",
          "desc": "内廷与入内内侍省及依附内廷者——**官僚 POP 在岗官子池中依附皇权的那一部分**（按立场切，不绑定京畿）",
          "kind": "court_network",
          "aliases": [
            "宦官集团",
            "内侍与内廷势力",
            "内廷",
            "inner_court"
          ],
          "interests": [
            {
              "pop_class": "官僚",
              "topic": "入内供奉与内库",
              "direction": 1
            },
            {
              "pop_class": "官僚",
              "topic": "御笔与中旨",
              "direction": 1
            }
          ],
          "red_lines": [
            "裁押内侍",
            "罢内库供奉"
          ],
          "subchannels": [
            {
              "name": "入内内侍省",
              "pop_class": "官僚"
            },
            {
              "name": "内廷供奉官",
              "pop_class": "官僚"
            },
            {
              "name": "依附内廷的官僚",
              "pop_class": "官僚"
            }
          ],
          "overlaps": [
            "新党"
          ],
          "thresholds": {
            "population_share": 0.02,
            "cohesion": 40,
            "exposure_months": 3
          }
        },
        "basis_readout": {
          "routes": null,
          "routes_count": 20,
          "pop_classes": [
            "官僚"
          ],
          "subset_of": [
            "官僚"
          ],
          "subset_kind": "faction",
          "pool": "officials",
          "pop_size": 1323.59,
          "pool_size": 1323.59,
          "parent_pop_size": 248420,
          "parent_total": 32290,
          "share": 0.041,
          "subset_note": "皇党集团 ⊆ 官僚 POP · officials 子池（全国），占 4.1%",
          "troops": 0,
          "morale": null,
          "public_support_avg": 57.5,
          "gentry_resistance_avg": 39.6
        },
        "basis_errors": [],
        "display_name": "皇党集团",
        "kind": "court_network",
        "aliases": [
          "宦官集团",
          "内侍与内廷势力",
          "内廷",
          "inner_court"
        ],
        "interests": [
          {
            "pop_class": "官僚",
            "topic": "入内供奉与内库",
            "direction": 1
          },
          {
            "pop_class": "官僚",
            "topic": "御笔与中旨",
            "direction": 1
          }
        ],
        "red_lines": [
          "裁押内侍",
          "罢内库供奉"
        ],
        "subchannels": [
          {
            "name": "入内内侍省",
            "pop_class": "官僚"
          },
          {
            "name": "内廷供奉官",
            "pop_class": "官僚"
          },
          {
            "name": "依附内廷的官僚",
            "pop_class": "官僚"
          }
        ],
        "overlaps": [
          "新党"
        ],
        "thresholds": {
          "population_share": 0.02,
          "cohesion": 40,
          "exposure_months": 3
        }
      },
      "军功集团": {
        "influence": 30.45,
        "satisfaction": 63.32,
        "cohesion": 68.36,
        "leader": "种师道",
        "pop_basis": {
          "pop_classes": [
            "兵",
            "官僚"
          ],
          "pool": null,
          "routes": null,
          "subset_of": [
            "兵",
            "官僚"
          ],
          "subset_kind": "faction",
          "desc": "以军功晋身的武臣与文官——**兵/官僚 POP 中持军功立场的那一部分**（经略安抚、军前参议、军功补官者皆入此网络；兵系仍只来自兵 POP）",
          "kind": "military_command",
          "aliases": [
            "西军集团",
            "西北武人集团",
            "陕西边将与西军",
            "西军",
            "northwest_frontier_command"
          ],
          "interests": [
            {
              "pop_class": "兵",
              "topic": "军饷与编制",
              "direction": 1
            },
            {
              "pop_class": "兵",
              "topic": "军功与迁补",
              "direction": 1
            },
            {
              "pop_class": "官僚",
              "topic": "军前差遣与边帅除授",
              "direction": 1
            },
            {
              "pop_class": "官僚",
              "topic": "军功补官与武臣转文",
              "direction": 1
            }
          ],
          "red_lines": [
            "裁撤边军",
            "夺边将兵柄",
            "废军功补官"
          ],
          "subchannels": [
            {
              "name": "陕西边将",
              "pop_class": "兵"
            },
            {
              "name": "西军",
              "pop_class": "兵"
            },
            {
              "name": "军户",
              "pop_class": "兵"
            },
            {
              "name": "边地军民",
              "pop_class": "兵"
            },
            {
              "name": "边帅与军前文官",
              "pop_class": "官僚"
            }
          ],
          "overlaps": [
            "皇党集团"
          ],
          "thresholds": {
            "population_share": 0.05,
            "cohesion": 45,
            "exposure_months": 3
          }
        },
        "basis_readout": {
          "routes": null,
          "routes_count": 20,
          "pop_classes": [
            "兵",
            "官僚"
          ],
          "subset_of": [
            "兵",
            "官僚"
          ],
          "subset_kind": "faction",
          "pool": null,
          "pop_size": 752648.07,
          "pool_size": 752648.07,
          "parent_pop_size": 998420,
          "parent_total": 998420,
          "share": 0.7538,
          "subset_note": "军功集团 ⊆ 兵/官僚 POP（全国），占 75.4%；兵额 750,000 人",
          "troops": 750000,
          "morale": 62.81,
          "public_support_avg": 57.5,
          "gentry_resistance_avg": 39.6
        },
        "basis_errors": [],
        "display_name": "军功集团",
        "kind": "military_command",
        "aliases": [
          "西军集团",
          "西北武人集团",
          "陕西边将与西军",
          "西军",
          "northwest_frontier_command"
        ],
        "interests": [
          {
            "pop_class": "兵",
            "topic": "军饷与编制",
            "direction": 1
          },
          {
            "pop_class": "兵",
            "topic": "军功与迁补",
            "direction": 1
          },
          {
            "pop_class": "官僚",
            "topic": "军前差遣与边帅除授",
            "direction": 1
          },
          {
            "pop_class": "官僚",
            "topic": "军功补官与武臣转文",
            "direction": 1
          }
        ],
        "red_lines": [
          "裁撤边军",
          "夺边将兵柄",
          "废军功补官"
        ],
        "subchannels": [
          {
            "name": "陕西边将",
            "pop_class": "兵"
          },
          {
            "name": "西军",
            "pop_class": "兵"
          },
          {
            "name": "军户",
            "pop_class": "兵"
          },
          {
            "name": "边地军民",
            "pop_class": "兵"
          },
          {
            "name": "边帅与军前文官",
            "pop_class": "官僚"
          }
        ],
        "overlaps": [
          "皇党集团"
        ],
        "thresholds": {
          "population_share": 0.05,
          "cohesion": 45,
          "exposure_months": 3
        }
      },
      "中立派": {
        "influence": 32.49,
        "satisfaction": 54.55,
        "cohesion": 61.81,
        "leader": "曾布",
        "pop_basis": {
          "pop_classes": [
            "士绅",
            "商人"
          ],
          "pool": null,
          "routes": null,
          "subset_of": [
            "士绅",
            "商人"
          ],
          "subset_kind": "faction",
          "desc": "**党争之外的第三方**（不结党的士商力量）——**士绅/商人 POP 中不结党的那一部分**：以保境安民、通商与科举为诉求，不卷入新旧党争（按立场切，不绑定东南）",
          "kind": "gentry_merchant_alliance",
          "aliases": [
            "东南士人",
            "东南士商集团",
            "东南形势户与市舶商人",
            "southeast_gentry_merchants"
          ],
          "interests": [
            {
              "pop_class": "士绅",
              "topic": "不结党与保境安民",
              "direction": 1
            },
            {
              "pop_class": "士绅",
              "topic": "科举取士与地方秩序",
              "direction": 1
            },
            {
              "pop_class": "商人",
              "topic": "通商与市舶",
              "direction": 1
            },
            {
              "pop_class": "商人",
              "topic": "货币与盐茶",
              "direction": 1
            }
          ],
          "red_lines": [
            "党争倾轧",
            "禁海",
            "抑商与榷禁过苛"
          ],
          "subchannels": [
            {
              "name": "东南士人",
              "pop_class": "士绅"
            },
            {
              "name": "形势户",
              "pop_class": "士绅"
            },
            {
              "name": "市舶商人",
              "pop_class": "商人"
            },
            {
              "name": "城市商人",
              "pop_class": "商人"
            }
          ],
          "overlaps": [],
          "thresholds": {
            "population_share": 0.05,
            "cohesion": 30,
            "exposure_months": 6
          }
        },
        "basis_readout": {
          "routes": null,
          "routes_count": 20,
          "pop_classes": [
            "士绅",
            "商人"
          ],
          "subset_of": [
            "士绅",
            "商人"
          ],
          "subset_kind": "faction",
          "pool": null,
          "pop_size": 3633675.72,
          "pool_size": 3633675.72,
          "parent_pop_size": 4397695,
          "parent_total": 4397695,
          "share": 0.8263,
          "subset_note": "中立派 ⊆ 士绅/商人 POP（全国），占 82.6%",
          "troops": 0,
          "morale": null,
          "public_support_avg": 57.5,
          "gentry_resistance_avg": 39.6
        },
        "basis_errors": [],
        "display_name": "中立派",
        "kind": "gentry_merchant_alliance",
        "aliases": [
          "东南士人",
          "东南士商集团",
          "东南形势户与市舶商人",
          "southeast_gentry_merchants"
        ],
        "interests": [
          {
            "pop_class": "士绅",
            "topic": "不结党与保境安民",
            "direction": 1
          },
          {
            "pop_class": "士绅",
            "topic": "科举取士与地方秩序",
            "direction": 1
          },
          {
            "pop_class": "商人",
            "topic": "通商与市舶",
            "direction": 1
          },
          {
            "pop_class": "商人",
            "topic": "货币与盐茶",
            "direction": 1
          }
        ],
        "red_lines": [
          "党争倾轧",
          "禁海",
          "抑商与榷禁过苛"
        ],
        "subchannels": [
          {
            "name": "东南士人",
            "pop_class": "士绅"
          },
          {
            "name": "形势户",
            "pop_class": "士绅"
          },
          {
            "name": "市舶商人",
            "pop_class": "商人"
          },
          {
            "name": "城市商人",
            "pop_class": "商人"
          }
        ],
        "overlaps": [],
        "thresholds": {
          "population_share": 0.05,
          "cohesion": 30,
          "exposure_months": 6
        }
      }
    },
    "emerging": [],
    "basis_table": {
      "新党": {
        "pop_classes": [
          "官僚"
        ],
        "pool": "officials",
        "routes": null,
        "subset_of": [
          "官僚"
        ],
        "subset_kind": "faction",
        "desc": "变法受益的在朝官——**官僚 POP 在岗官子池中持新法立场的那一部分**（立场按派系而非地域切；地域只是出身）",
        "kind": "policy_network",
        "aliases": [
          "新法系",
          "绍述派",
          "new_law_network"
        ],
        "interests": [
          {
            "pop_class": "官僚",
            "topic": "新法财利与差遣恩泽",
            "direction": 1
          },
          {
            "pop_class": "士绅",
            "topic": "新法政策暴露",
            "direction": 1
          }
        ],
        "red_lines": [
          "废署新法",
          "追夺绍述之政"
        ],
        "subchannels": [],
        "overlaps": [
          "皇党集团"
        ],
        "thresholds": {
          "population_share": 0.05,
          "cohesion": 30,
          "exposure_months": 6
        }
      },
      "旧党": {
        "pop_classes": [
          "士绅",
          "官僚"
        ],
        "pool": null,
        "routes": null,
        "subset_of": [
          "士绅",
          "官僚"
        ],
        "subset_kind": "faction",
        "desc": "持旧法立场的士绅与在朝官——**士绅/官僚 POP 中反对绍述的那一部分**（按立场切，不与任何地域绑定）",
        "kind": "gentry_alliance",
        "aliases": [
          "旧法系",
          "元祐旧臣",
          "元祐党人",
          "yuanyou_old_officials"
        ],
        "interests": [
          {
            "pop_class": "士绅",
            "topic": "田税与隐田",
            "direction": 1
          },
          {
            "pop_class": "士绅",
            "topic": "科举取士",
            "direction": 1
          },
          {
            "pop_class": "官僚",
            "topic": "元祐旧制与差遣",
            "direction": 1
          }
        ],
        "red_lines": [
          "恢复新法",
          "绍述绍圣之政"
        ],
        "subchannels": [],
        "overlaps": [
          "中立派"
        ],
        "thresholds": {
          "population_share": 0.05,
          "cohesion": 25,
          "exposure_months": 6
        }
      },
      "皇党集团": {
        "pop_classes": [
          "官僚"
        ],
        "pool": "officials",
        "routes": null,
        "subset_of": [
          "官僚"
        ],
        "subset_kind": "faction",
        "desc": "内廷与入内内侍省及依附内廷者——**官僚 POP 在岗官子池中依附皇权的那一部分**（按立场切，不绑定京畿）",
        "kind": "court_network",
        "aliases": [
          "宦官集团",
          "内侍与内廷势力",
          "内廷",
          "inner_court"
        ],
        "interests": [
          {
            "pop_class": "官僚",
            "topic": "入内供奉与内库",
            "direction": 1
          },
          {
            "pop_class": "官僚",
            "topic": "御笔与中旨",
            "direction": 1
          }
        ],
        "red_lines": [
          "裁押内侍",
          "罢内库供奉"
        ],
        "subchannels": [
          {
            "name": "入内内侍省",
            "pop_class": "官僚"
          },
          {
            "name": "内廷供奉官",
            "pop_class": "官僚"
          },
          {
            "name": "依附内廷的官僚",
            "pop_class": "官僚"
          }
        ],
        "overlaps": [
          "新党"
        ],
        "thresholds": {
          "population_share": 0.02,
          "cohesion": 40,
          "exposure_months": 3
        }
      },
      "军功集团": {
        "pop_classes": [
          "兵",
          "官僚"
        ],
        "pool": null,
        "routes": null,
        "subset_of": [
          "兵",
          "官僚"
        ],
        "subset_kind": "faction",
        "desc": "以军功晋身的武臣与文官——**兵/官僚 POP 中持军功立场的那一部分**（经略安抚、军前参议、军功补官者皆入此网络；兵系仍只来自兵 POP）",
        "kind": "military_command",
        "aliases": [
          "西军集团",
          "西北武人集团",
          "陕西边将与西军",
          "西军",
          "northwest_frontier_command"
        ],
        "interests": [
          {
            "pop_class": "兵",
            "topic": "军饷与编制",
            "direction": 1
          },
          {
            "pop_class": "兵",
            "topic": "军功与迁补",
            "direction": 1
          },
          {
            "pop_class": "官僚",
            "topic": "军前差遣与边帅除授",
            "direction": 1
          },
          {
            "pop_class": "官僚",
            "topic": "军功补官与武臣转文",
            "direction": 1
          }
        ],
        "red_lines": [
          "裁撤边军",
          "夺边将兵柄",
          "废军功补官"
        ],
        "subchannels": [
          {
            "name": "陕西边将",
            "pop_class": "兵"
          },
          {
            "name": "西军",
            "pop_class": "兵"
          },
          {
            "name": "军户",
            "pop_class": "兵"
          },
          {
            "name": "边地军民",
            "pop_class": "兵"
          },
          {
            "name": "边帅与军前文官",
            "pop_class": "官僚"
          }
        ],
        "overlaps": [
          "皇党集团"
        ],
        "thresholds": {
          "population_share": 0.05,
          "cohesion": 45,
          "exposure_months": 3
        }
      },
      "中立派": {
        "pop_classes": [
          "士绅",
          "商人"
        ],
        "pool": null,
        "routes": null,
        "subset_of": [
          "士绅",
          "商人"
        ],
        "subset_kind": "faction",
        "desc": "**党争之外的第三方**（不结党的士商力量）——**士绅/商人 POP 中不结党的那一部分**：以保境安民、通商与科举为诉求，不卷入新旧党争（按立场切，不绑定东南）",
        "kind": "gentry_merchant_alliance",
        "aliases": [
          "东南士人",
          "东南士商集团",
          "东南形势户与市舶商人",
          "southeast_gentry_merchants"
        ],
        "interests": [
          {
            "pop_class": "士绅",
            "topic": "不结党与保境安民",
            "direction": 1
          },
          {
            "pop_class": "士绅",
            "topic": "科举取士与地方秩序",
            "direction": 1
          },
          {
            "pop_class": "商人",
            "topic": "通商与市舶",
            "direction": 1
          },
          {
            "pop_class": "商人",
            "topic": "货币与盐茶",
            "direction": 1
          }
        ],
        "red_lines": [
          "党争倾轧",
          "禁海",
          "抑商与榷禁过苛"
        ],
        "subchannels": [
          {
            "name": "东南士人",
            "pop_class": "士绅"
          },
          {
            "name": "形势户",
            "pop_class": "士绅"
          },
          {
            "name": "市舶商人",
            "pop_class": "商人"
          },
          {
            "name": "城市商人",
            "pop_class": "商人"
          }
        ],
        "overlaps": [],
        "thresholds": {
          "population_share": 0.05,
          "cohesion": 30,
          "exposure_months": 6
        }
      }
    },
    "display_names": {
      "新党": "新法系",
      "旧党": "元祐旧臣与保守士绅",
      "皇党集团": "皇党集团",
      "军功集团": "军功集团",
      "中立派": "中立派"
    },
    "basis_errors": [],
    "declared": true
  },
  "readout_status": "ok",
  "readout_errors": []
};
