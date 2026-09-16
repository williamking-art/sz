import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { useGameStore, pick } from "../store/gameStore";
import { wan } from "../utils/format";
import constants from "../data/constants.json";

// 州县治理 —— 对齐 game/ui/panels_economy.py::_panel_prefectures(L90) + _panel_prefecture(L121) + _panel_land(L144)
// 三视图（组件内 state 切换）：列表 / 单路详情 / 田亩户籍总览。只读展示，施政走「拟旨」。
type Dict = Record<string, unknown>;

const PREFECTURE_LIST = constants.prefecture_list as string[];

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function pnum(p: Dict, key: string, def = 0): number {
  const v = p[key];
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function barText(value: number, width = 20): string {
  const v = Math.max(0, Math.min(width, Math.floor((value * width) / 100)));
  const fill = value >= 70 ? "█" : value >= 40 ? "▓" : "▒";
  return fill.repeat(v) + "░".repeat(width - v);
}

function SectionTitle({ text }: { text: string }) {
  return <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">{text}</p>;
}

// 映射别名与邻路归属到 12 大经济单位
function resolveRoadKey(name?: string | null): string | null {
  if (!name) return null;
  const direct = PREFECTURE_LIST.find((k) => k === name);
  if (direct) return direct;
  const clean = name.replace(/路|府$/g, "");
  const fuzzy = PREFECTURE_LIST.find((k) => k.includes(clean) || clean.includes(k.replace(/路|府$/g, "")));
  if (fuzzy) return fuzzy;
  if (name.includes("京畿") || name.includes("开封")) return "东京开封府";
  if (name.includes("河东")) return "河东";
  if (name.includes("淮南")) return "江南东路"; // 淮南随邻近江南东路账册
  if (name.includes("广南西")) return "广南东路"; // 广南西随广南东路
  if (name.includes("利州") || name.includes("夔州")) return "成都府路"; // 川峡随成都府
  if (name.includes("京东")) return "京西路"; // 京东随京西
  return null;
}

export default function PrefecturePanel({ props }: { props?: { picked?: string } }) {
  const state = useGameStore((s) => s.state);
  const targetRoad = resolveRoadKey(props?.picked);
  const [view, setView] = useState<"list" | "detail" | "land">(targetRoad ? "detail" : "list");
  const [picked, setPicked] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(targetRoad);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无州县可览。</p>;
  }
  const prefectures = asDict(pick(state, "prefectures", {}));

  // ---- 视图：田亩户籍总览（Tk _panel_land） ----
  if (view === "land") {
    const land = asDict(pick(state, "land", {}));
    const population = pick<number>(state, "population", 0);
    const lines: string[] = [];
    lines.push(`全国垦田：${wan(pnum(land, "cultivated"), "亩")}（隐漏率 ${Math.round(pnum(land, "hidden_rate") * 100)}%）`);
    lines.push(`在籍户数：${wan(pnum(land, "households"), "户")}　约 ${wan(population, "口")}`);
    lines.push(`荒闲田土：${wan(pnum(land, "wasteland"), "亩")}　亩产系数：${pnum(land, "yield", 1).toFixed(2)}`);
    lines.push("");
    lines.push("【诸路概要】");
    for (const name of PREFECTURE_LIST) {
      const p = asDict(prefectures[name]);
      const support = Math.round(pnum(p, "public_support", pnum(p, "mood", 50)));
      const gentry = Math.round(pnum(p, "gentry_resistance", 30));
      const defense = Math.round(pnum(p, "city_defense", 40));
      const ctrl = String(p.controlled_by ?? "宋");
      lines.push(
        `  ${name}：${wan(pnum(p, "households"), "户")} ${wan(pnum(p, "land"), "亩")} 粮${wan(pnum(p, "grain"), "石")} ` +
        `民情${pnum(p, "mood")} 民心${support} 士绅${gentry} 城防${defense} 属${ctrl}`
      );
    }
    lines.push("");
    lines.push("【诸路 POP 人口】（万：农/绅/工/商/官/兵）");
    const w = (v: number) => (v >= 1e4 ? `${Math.round(v / 1e4)}` : String(v));
    for (const name of PREFECTURE_LIST) {
      const pops = asDict(asDict(prefectures[name]).pops);
      const pop = (k: string) => asDict(pops[k]);
      lines.push(
        `  ${name}：农${w(pnum(pop("农"), "size"))} 绅${w(pnum(pop("士绅"), "size"))} 工${w(pnum(pop("工匠"), "size"))} ` +
        `商${w(pnum(pop("商人"), "size"))} 官${w(pnum(pop("官僚"), "size"))} 兵${w(pnum(pop("兵"), "size"))}`
      );
    }
    let totWealth = 0;
    let totGrain = 0;
    for (const name of PREFECTURE_LIST) {
      for (const pop of Object.values(asDict(asDict(prefectures[name]).pops))) {
        totWealth += pnum(asDict(pop), "wealth");
        totGrain += pnum(asDict(pop), "grain");
      }
    }
    lines.push("");
    lines.push(`【民间 POP 汇总】持钱 ${wan(totWealth, "贯")}　存粮 ${wan(totGrain, "石")}`);
    return (
      <div className="space-y-4">
        <button
          onClick={() => setView("list")}
          className="flex items-center gap-1.5 rounded-lg bg-paper/60 px-3 py-1.5 text-sm text-ink transition hover:bg-gold-light"
        >
          <ArrowLeft size={14} /> 返回州县列表
        </button>
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
          <pre className="whitespace-pre-wrap font-sans text-[13px] leading-relaxed text-ink">
            {lines.join("\n")}
          </pre>
        </div>
      </div>
    );
  }

  // ---- 视图：单路详情（Tk _panel_prefecture） ----
  if (view === "detail" && selected) {
    const p = asDict(prefectures[selected]);
    const support = Math.round(pnum(p, "public_support", pnum(p, "mood", 50)));
    const gentry = Math.round(pnum(p, "gentry_resistance", 30));
    const defense = Math.round(pnum(p, "city_defense", 40));
    const fiscal = Math.round(pnum(p, "fiscal", 50));
    const rows: [string, string][] = [
      ["户数", wan(pnum(p, "households"), "户")],
      ["垦田", wan(pnum(p, "land"), "亩")],
      ["粮产", wan(pnum(p, "grain"), "石")],
      ["民情", `${barText(pnum(p, "mood"))} ${pnum(p, "mood")}`],
      ["治理", `${barText(pnum(p, "govern"))} ${pnum(p, "govern")}`],
      ["民心", `${barText(support)} ${support}`],
      ["士绅抵抗", `${barText(gentry)} ${gentry}`],
      ["城防", `${barText(defense)} ${defense}`],
      ["财政", `${barText(fiscal)} ${fiscal}`],
      ["控制势力", String(p.controlled_by ?? "宋")]
    ];
    return (
      <div className="space-y-4">
        <button
          onClick={() => setView("list")}
          className="flex items-center gap-1.5 rounded-lg bg-paper/60 px-3 py-1.5 text-sm text-ink transition hover:bg-gold-light"
        >
          <ArrowLeft size={14} /> 返回州县列表
        </button>
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
          {rows.map(([k, v]) => (
            <div key={k} className="flex items-baseline justify-between gap-4 py-1 text-sm">
              <span className="shrink-0 text-ink-light">{k}</span>
              <span className="text-ink">{v}</span>
            </div>
          ))}
        </div>
        <p className="px-1 text-xs leading-relaxed text-dim">
          地方之政（劝农、赈灾、平盗、减税等）请经「拟旨」系统拟诏施行，效果由中枢推演落地。
        </p>
      </div>
    );
  }

  // ---- 视图：州县列表（Tk _panel_prefectures） ----
  return (
    <div className="space-y-4">
      <p className="px-1 text-sm leading-relaxed text-dim">
        诸路安则社稷安。田亩户籍、劝农赈灾、平盗减税，皆由此出。
      </p>
      <div>
        <button
          onClick={() => setView("land")}
          className="rounded-lg border border-gold/60 bg-paper/60 px-5 py-2 font-kai text-sm tracking-widest text-ink transition hover:bg-gold-light"
        >
          田 亩 户 籍 总 览
        </button>
      </div>
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-2">
        {PREFECTURE_LIST.map((name, i) => {
          const p = asDict(prefectures[name]);
          const active = picked === name;
          return (
            <button
              key={name}
              onClick={() => setPicked(name)}
              onDoubleClick={() => { setSelected(name); setView("detail"); }}
              className={`block w-full rounded px-3 py-1.5 text-left text-[13px] transition ${
                active ? "bg-red text-paper" : "text-ink hover:bg-gold-light"
              }`}
            >
              [{i + 1}] {name}　{wan(pnum(p, "households"), "户")} {wan(pnum(p, "land"), "亩")}{" "}
              粮{wan(pnum(p, "grain"), "石")} 民情{pnum(p, "mood")} 治{pnum(p, "govern")}
            </button>
          );
        })}
      </div>
      <div className="flex justify-center">
        <button
          onClick={() => { if (picked) { setSelected(picked); setView("detail"); } }}
          disabled={!picked}
          className="rounded-lg bg-red px-6 py-2 font-kai text-base tracking-widest text-paper transition hover:bg-red-dark disabled:opacity-60"
        >
          查 看 路 情
        </button>
      </div>
    </div>
  );
}
