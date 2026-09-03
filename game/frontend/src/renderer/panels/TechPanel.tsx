import { useMemo, useState } from "react";
import { Loader2, X } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";
import constants from "../data/constants.json";

// 科技树 —— 对齐 game/ui/panels_economy.py::_panel_tech（L771）
// 6 干线分列、节点按 era 排布的树状图（Tk Canvas 绘制 → CSS Grid 等价实现）。
// 研发 → action("start_tech_research", { node_id, silver, fund, source: "panel", signoff? })。
// 节点状态/跨时代成本为纯前端复刻（core/asset_context.py::node_status + data.py::tech_cost_with_era）。
type Dict = Record<string, unknown>;

interface TechNode {
  id: string;
  line: string;
  era: number;
  name: string;
  desc: string;
  prereq: string[];
  cost: { silver: number; months: number; masters: number; idea?: boolean };
  effect: Dict;
}

const NODES = (constants.tech_nodes as unknown as TechNode[]).filter((n) => !n.id.startsWith("gen_"));
const LINES = constants.tech_lines as string[];

// content/data.py::TECH_ERAS（静态表）
const TECH_ERAS: [number, number, number][] = [
  [960, 1100, 0], [1100, 1279, 1], [1279, 1368, 2], [1368, 1600, 3],
  [1600, 1800, 4], [1800, 1870, 5], [1870, 1900, 6]
];

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}

function currentEra(year: number): number {
  for (const [lo, hi, idx] of TECH_ERAS) {
    if (lo <= year && year <= hi) return idx;
  }
  return 0;
}

// 节点状态（core/asset_context.py::node_status 前端复刻）
function nodeStatus(tech: Dict, node: TechNode): "unlocked" | "researching" | "researchable" | "locked" {
  const unlocked = new Set((tech.unlocked as string[] | undefined) ?? []);
  const researching = asDict(tech.researching);
  if (unlocked.has(node.id)) return "unlocked";
  if (node.id in researching) return "researching";
  if ((node.prereq ?? []).every((p) => unlocked.has(p))) return "researchable";
  return "locked";
}

// 跨时代成本（content/data.py::tech_cost_with_era 前端复刻）
function costWithEra(node: TechNode, curEra: number): { silver: number; months: number; idea: boolean } {
  const mult = 1 + Math.max(0, node.era - curEra) * 0.2;
  const isIdea = node.cost?.idea === true;
  return {
    silver: isIdea ? 0 : Math.round(asNum(node.cost?.silver) * mult),
    months: Math.max(1, Math.round(asNum(node.cost?.months) * mult)),
    idea: isIdea
  };
}

const ST_STYLE: Record<string, string> = {
  unlocked: "border-gold bg-[#7a1f1a] text-[#f3e6c4]",
  researchable: "border-gold bg-[#f3e6c4] text-[#3a2a17]",
  researching: "border-[#7fd4e6] bg-[#1f4a5a] text-[#eaf7fb]",
  locked: "border-[#9c9486] bg-[#cfc6b4] text-[#6b6151]"
};
const ST_TXT: Record<string, string> = {
  unlocked: "已点亮", researchable: "可研发", researching: "攻关中", locked: "未解锁"
};

export default function TechPanel() {
  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);
  const [detail, setDetail] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const tech = asDict(pick(state, "tech", {}));
  const year = pick<number>(state, "year", 1101);
  const curEra = currentEra(year);

  // 按线分列、era 排序（对齐 Tk _draw_tech_tree）
  const columns = useMemo(
    () =>
      LINES.map((line) =>
        NODES.filter((n) => n.line === line).sort((a, b) => a.era - b.era)
      ),
    []
  );
  const maxEra = Math.max(...NODES.map((n) => n.era), 0);
  const nodeById = useMemo(() => new Map(NODES.map((n) => [n.id, n])), []);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无技艺可览。</p>;
  }

  const node = detail ? nodeById.get(detail) : null;
  const st = node ? nodeStatus(tech, node) : null;
  const realCost = node ? costWithEra(node, curEra) : null;

  async function research(fund: "treasury" | "inner") {
    if (busy || !node || !realCost) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await getApiClient().action("start_tech_research", {
        node_id: node.id,
        silver: fund === "inner" ? 0 : realCost.silver,
        fund,
        source: "panel",
        signoff: fund === "treasury" ? true : undefined
      });
      setState(res.state);
      setResult(res.message);
      setDetail(null);
    } catch (e) {
      console.error("[start_tech_research]", e);
      setResult("立项失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="px-1 text-sm leading-relaxed text-dim">
        天下技艺积累，皆聚于此。新制兴工：国库拨银须经廷议，内帑乾纲独断则免。
      </p>

      {/* 科技树谱：6 列 × era 行 */}
      <div className="overflow-x-auto rounded-lg border border-gold/40 bg-paper/60 p-3">
        <div className="min-w-[720px]">
          {/* 列头 */}
          <div className="grid grid-cols-6 gap-2">
            {LINES.map((line) => (
              <p key={line} className="text-center font-kai text-sm font-bold text-ink">{line}</p>
            ))}
          </div>
          {/* era 行 */}
          <div className="mt-2 space-y-2">
            {Array.from({ length: maxEra + 1 }, (_, era) => (
              <div key={era} className="grid grid-cols-6 gap-2">
                {columns.map((col, li) => {
                  const cells = col.filter((n) => n.era === era);
                  return (
                    <div key={li} className="flex flex-col justify-center gap-1.5">
                      {cells.map((n) => {
                        const s = nodeStatus(tech, n);
                        return (
                          <button
                            key={n.id}
                            onClick={() => { setDetail(n.id); setResult(null); }}
                            className={`rounded-lg border-2 px-1 py-1.5 text-center text-xs font-bold transition hover:brightness-95 ${ST_STYLE[s]}`}
                          >
                            {n.name.length > 7 ? n.name.slice(0, 6) + "…" : n.name}
                          </button>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 节点详情（内联展开，对齐 Tk _tech_detail） */}
      {node && st && realCost && (
        <div className="rounded-lg border-2 border-gold bg-card p-4">
          <div className="flex items-start justify-between">
            <p className="font-kai text-lg font-bold text-red">〔{node.line}〕{node.name}</p>
            <button
              onClick={() => setDetail(null)}
              className="rounded px-2 py-0.5 text-sm text-ink-light transition hover:bg-gold-light hover:text-ink"
            >
              <X size={16} />
            </button>
          </div>
          <p className="mt-1 text-sm text-ink">
            状态：{ST_TXT[st]}　·　时代层级：{node.era}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-ink">{node.desc}</p>
          <p className="mt-2 text-sm text-dim">
            前置：{node.prereq?.length
              ? node.prereq.map((p) => nodeById.get(p)?.name ?? p).join("、")
              : "无"}
          </p>
          <p className="mt-1 text-sm text-dim">
            {realCost.silver || realCost.months
              ? `耗帑 ${humanizeCoin(realCost.silver)}　·　工期 ${realCost.months}月　·　工部领办，匠役由将作监调拨`
              : "近零成本（观念/基础）"}
          </p>
          {Object.keys(node.effect ?? {}).length > 0 && (
            <p className="mt-1 text-sm text-dim">
              效用：{Object.entries(node.effect)
                .map(([k, v]) => `${k}${typeof v === "number" ? (v > 0 ? "+" : "") + v : ""}`)
                .join("，")}
            </p>
          )}
          <div className="mt-3 flex justify-end gap-3">
            {st === "researchable" ? (
              <>
                <button
                  onClick={() => research("treasury")}
                  disabled={busy}
                  className="rounded-lg bg-red px-5 py-2 font-kai text-sm tracking-widest text-paper transition hover:bg-red-dark disabled:opacity-60"
                >
                  国库拨银（会签）
                </button>
                <button
                  onClick={() => research("inner")}
                  disabled={busy}
                  className="rounded-lg bg-paper/60 px-5 py-2 font-kai text-sm tracking-widest text-ink transition hover:bg-gold-light disabled:opacity-60"
                >
                  内帑独断
                </button>
              </>
            ) : (
              <p className="py-2 text-sm text-dim">（当前不可立项）</p>
            )}
          </div>
        </div>
      )}

      {busy && (
        <p className="flex items-center justify-center gap-2 text-sm text-dim">
          <Loader2 size={14} className="animate-spin" /> 廷议推演中…
        </p>
      )}
      {result && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <p className="whitespace-pre-wrap font-kai text-[15px] leading-relaxed text-ink">{result}</p>
        </div>
      )}
    </div>
  );
}
