import { useState } from "react";
import { Users2, Coins, Wheat, TrendingUp, Sparkles, AlertCircle } from "lucide-react";
import { useGameStore, pick } from "../store/gameStore";
import { wan } from "../utils/format";
import constants from "../data/constants.json";

const PREFECTURE_LIST = constants.prefecture_list as string[];

type Dict = Record<string, unknown>;
function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function pnum(p: Dict, key: string, def = 0): number {
  const v = p[key];
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}

const POP_PROFILES: Record<string, { label: string; role: string; focus: string; color: string }> = {
  农: { label: "农夫佣耕", role: "衣食之本，提供夏秋两税与漕粮", focus: "轻徭薄赋，平抑粮价，勿兴大役", color: "text-amber-800" },
  士绅: { label: "士绅豪富", role: "宗族乡贤，隐占田土与私粮囤储", focus: "保护私产，宽假铨选，抵制清丈", color: "text-purple-800" },
  工匠: { label: "官私百工", role: "营造兵器，营缮水利与火药作坊", focus: "工食充足，工役公允，科技拓新", color: "text-blue-800" },
  商人: { label: "行商坐贾", role: "通达互市，经手盐茶钞法与商税", focus: "行路畅通，钞法稳定，减免榷税", color: "text-emerald-800" },
  官僚: { label: "中枢守牧", role: "治国牧民，维持州县治理与政令", focus: "俸给充足，铨选公允，升迁有望", color: "text-red-dark" },
  兵: { label: "禁厢戎卒", role: "御敌戍边，拱卫京师与关隘", focus: "月粮足额，月饷不拖，按时换防", color: "text-red" }
};

export default function PopPanel() {
  const state = useGameStore((s) => s.state);
  const [selectedRoad, setSelectedRoad] = useState<string>("全国汇总");

  if (!state) {
    return <div className="py-12 text-center font-kai text-sm text-dim">尚未开局，民生籍册未全。</div>;
  }

  const prefectures = asDict(pick(state, "prefectures", {}));

  // 计算全国六民汇总
  const nationalPops: Record<string, { size: number; wealth: number; grain: number }> = {
    农: { size: 0, wealth: 0, grain: 0 },
    士绅: { size: 0, wealth: 0, grain: 0 },
    工匠: { size: 0, wealth: 0, grain: 0 },
    商人: { size: 0, wealth: 0, grain: 0 },
    官僚: { size: 0, wealth: 0, grain: 0 },
    兵: { size: 0, wealth: 0, grain: 0 }
  };

  for (const rname of PREFECTURE_LIST) {
    const rInfo = asDict(prefectures[rname]);
    const pops = asDict(rInfo.pops);
    for (const [k, pData] of Object.entries(pops)) {
      const p = asDict(pData);
      if (nationalPops[k]) {
        nationalPops[k].size += pnum(p, "size");
        nationalPops[k].wealth += pnum(p, "wealth");
        nationalPops[k].grain += pnum(p, "grain");
      }
    }
  }

  // 当前选中区域数据
  const isNational = selectedRoad === "全国汇总";
  const displayPops = isNational
    ? nationalPops
    : (asDict(asDict(prefectures[selectedRoad]).pops) as Record<string, any>);

  const totalPopSize = Object.values(displayPops).reduce((acc, it) => acc + (it.size || 0), 0);
  const totalWealth = Object.values(displayPops).reduce((acc, it) => acc + (it.wealth || 0), 0);
  const totalGrain = Object.values(displayPops).reduce((acc, it) => acc + (it.grain || 0), 0);

  return (
    <div className="flex h-[520px] flex-col gap-3.5">
      {/* 顶部：标题与区域选择 */}
      <div className="flex items-center justify-between border-b border-gold/40 pb-2">
        <div className="flex items-center gap-2">
          <Users2 size={18} className="text-red" />
          <span className="font-kai text-base font-bold text-ink">天下民生 · 六民生齿与财帛</span>
        </div>

        {/* 区域快速切换下拉 */}
        <select
          value={selectedRoad}
          onChange={(e) => setSelectedRoad(e.target.value)}
          className="rounded border border-gold/40 bg-card px-2.5 py-1 font-kai text-xs text-ink outline-none"
        >
          <option value="全国汇总">全国汇总（大宋全境）</option>
          {PREFECTURE_LIST.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>

      {/* 宏观总盘看板 */}
      <div className="grid grid-cols-3 gap-3 rounded-lg border border-gold/40 bg-card/60 p-3 text-center">
        <div>
          <div className="flex items-center justify-center gap-1 text-dim text-xs font-kai">
            <Users2 size={12} /> 在籍生齿
          </div>
          <div className="mt-1 font-sans text-base font-bold text-ink">{wan(totalPopSize, "口")}</div>
        </div>
        <div>
          <div className="flex items-center justify-center gap-1 text-dim text-xs font-kai">
            <Coins size={12} className="text-goldDark" /> 民间私财
          </div>
          <div className="mt-1 font-sans text-base font-bold text-ink">{wan(totalWealth, "贯")}</div>
        </div>
        <div>
          <div className="flex items-center justify-center gap-1 text-dim text-xs font-kai">
            <Wheat size={12} className="text-amber-700" /> 民间囤粮
          </div>
          <div className="mt-1 font-sans text-base font-bold text-ink">{wan(totalGrain, "石")}</div>
        </div>
      </div>

      {/* 六民阶层详尽大表 */}
      <div className="flex-1 space-y-2.5 overflow-y-auto pr-1">
        {Object.entries(POP_PROFILES).map(([popKey, prof]) => {
          const it = displayPops[popKey] || { size: 0, wealth: 0, grain: 0 };
          const size = it.size || 0;
          const wealth = it.wealth || 0;
          const grain = it.grain || 0;
          const pct = totalPopSize > 0 ? ((size / totalPopSize) * 100).toFixed(1) : "0";

          return (
            <div
              key={popKey}
              className="flex flex-col justify-between rounded-lg border border-gold/30 bg-paper/60 p-3 shadow-paper transition hover:bg-card"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-kai text-base font-bold text-ink">
                      【{popKey}】{prof.label}
                    </span>
                    <span className="rounded bg-card px-1.5 py-0.2 font-kai text-[10px] text-dim border border-border">
                      占生齿 {pct}%
                    </span>
                  </div>
                  <p className="mt-1 font-kai text-xs text-dim leading-relaxed">
                    {prof.role}
                  </p>
                </div>

                <div className="text-right font-sans text-xs">
                  <div className="font-bold text-ink">{wan(size, "口")}</div>
                  <div className="text-[11px] text-goldDark">持钱：{wan(wealth, "贯")}</div>
                  <div className="text-[11px] text-amber-800">存粮：{wan(grain, "石")}</div>
                </div>
              </div>

              {/* 核心诉求 */}
              <div className="mt-2.5 pt-2 border-t border-border/40 flex items-center justify-between text-xs font-kai">
                <span className="text-dim flex items-center gap-1">
                  <Sparkles size={12} className="text-goldDark" /> 核心民意诉求：
                </span>
                <span className={`${prof.color} font-medium`}>{prof.focus}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
