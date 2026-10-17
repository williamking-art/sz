import { useMemo, useState } from "react";
import { Loader2, X } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";
import { formatEffects } from "../utils/effects";
import constants from "../data/constants.json";

// 科技树 —— 对齐 game/ui/panels_economy.py::_panel_tech（L771）
// 6 干线分列、节点按 era 排布的树状图（Tk Canvas 绘制 → CSS Grid 等价实现）。
// 研发 → action("start_tech_research", { node_id, silver, fund, source: "panel", signoff? })。
// 🔴 纪律（根 AGENTS.md §3-2）：节点可研状态/跨时代成本**只读后端下发**，
//    前端不得复刻 core/asset_context.py::node_status 或 data.py::tech_cost_with_era。
//    后端未下发 node 读数时，状态/费用显式显示「未定义」；立项动作只传 node_id，
//    silver=0 让后端按权威口径计算与扣拨。
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

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}
function SectionTitle({ text }: { text: string }) {
  return (
    <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">{text}</p>
  );
}

type TechStatus = "unlocked" | "researching" | "researchable" | "locked" | "unknown";
interface TechNodeReadout {
  status: TechStatus;
  silver: number | null;
  months: number | null;
  idea: boolean | null;
  reason: string | null;
}

function finiteOrNull(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  return null;
}

function parseStatus(v: unknown): TechStatus | null {
  return v === "unlocked" || v === "researching" || v === "researchable" || v === "locked"
    ? v
    : null;
}

/** 解析后端节点读数（兼容 silver / 银 两种键名）；字段缺失保持 null，不本地重算。 */
function parseNodeReadout(raw: unknown): TechNodeReadout | null {
  if (!raw || typeof raw !== "object") return null;
  const d = asDict(raw);
  const status = parseStatus(d.status);
  const silver = "silver" in d ? finiteOrNull(d.silver) : finiteOrNull(d["银"]);
  const months = finiteOrNull(d.months);
  const idea = typeof d.idea === "boolean" ? d.idea : null;
  const reason = typeof d.reason === "string" ? d.reason : null;
  if (!status && silver === null && months === null) return null;
  return { status: status ?? "unknown", silver, months, idea, reason };
}

const ST_STYLE: Record<string, string> = {
  unlocked: "border-gold bg-[#7a1f1a] text-[#f3e6c4]",
  researchable: "border-gold bg-[#f3e6c4] text-[#3a2a17]",
  researching: "border-[#7fd4e6] bg-[#1f4a5a] text-[#eaf7fb]",
  locked: "border-[#9c9486] bg-[#cfc6b4] text-[#6b6151]",
  unknown: "border-dashed border-gold/60 bg-paper/60 text-dim"
};
const ST_TXT: Record<string, string> = {
  unlocked: "已点亮", researchable: "可研发", researching: "攻关中", locked: "未解锁",
  unknown: "未定义（后端未下发判定）"
};

export default function TechPanel() {
  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);
  const readouts = useGameStore((s) => s.readouts);
  const [detail, setDetail] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [invBusy, setInvBusy] = useState<number | null>(null);
  /** 国库拨银廷议签押（对齐 Tk _build_signing：工部领衔，可钦点协赞大臣） */
  const [signoffMinister, setSignoffMinister] = useState("工部尚书");
  const [summonHint, setSummonHint] = useState("");

  const tech = asDict(pick(state, "tech", {}));
  const inventions = Array.isArray(tech.pending_inventions)
    ? (tech.pending_inventions as unknown as Dict[])
    : [];
  // 后端节点读数：兼容 `readouts.tech.nodes` 与 `state.tech.node_readouts` 两种下发布局；
  // 未下发则节点状态/费用保持「未定义」，绝不在前端用 level/need_sub/era 重算。
  const backendTech = asDict((readouts as unknown as Dict | null)?.tech);
  const backendNodes = asDict(backendTech.nodes);
  const stateNodes = asDict(tech.node_readouts);
  const unlockedSet = new Set(Array.isArray(tech.unlocked) ? (tech.unlocked as string[]) : []);
  const researchingMap = asDict(tech.researching);
  function nodeReadoutFor(n: TechNode): TechNodeReadout {
    const parsed = parseNodeReadout(backendNodes[n.id] ?? stateNodes[n.id]);
    if (parsed) return parsed;
    if (unlockedSet.has(n.id)) {
      return { status: "unlocked", silver: null, months: null, idea: null, reason: null };
    }
    if (n.id in researchingMap) {
      return { status: "researching", silver: null, months: null, idea: null, reason: null };
    }
    return {
      status: "unknown", silver: null, months: null, idea: null,
      reason: "后端未下发该节点可研判定/成本",
    };
  }

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
  const nodeInfo = node ? nodeReadoutFor(node) : null;
  const st = nodeInfo?.status ?? null;

  async function research(fund: "treasury" | "inner") {
    if (busy || !node || !nodeInfo) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await getApiClient().action("start_tech_research", {
        node_id: node.id,
        // 费用未知时传 0：后端 start_research 会按 tech_cost_with_era 权威口径计算并扣拨。
        silver: fund === "inner" ? 0 : (nodeInfo.silver ?? 0),
        fund,
        source: "panel",
        signoff: fund === "treasury" ? true : undefined,
        // 廷议签押：国库拨银时记录领衔大臣（前端记录，便于叙事/日志对齐）
        ...(fund === "treasury"
          ? { signoff_minister: signoffMinister || "工部尚书", summon_note: summonHint }
          : {}),
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

  // ---- 工部献策审批（pending_inventions，按索引操作） ----
  async function approveInv(i: number, fund: "treasury" | "inner") {
    if (invBusy !== null) return;
    setInvBusy(i);
    setResult(null);
    try {
      const res = await getApiClient().action("approve_invention", {
        index: i,
        fund,
        signoff: fund === "treasury" ? true : undefined
      });
      if (res.state) setState(res.state);
      setResult(res.message || "已嘉纳工部献策，转将有司立项。");
    } catch (e) {
      console.error("[approve_invention]", e);
      setResult("嘉纳失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setInvBusy(null);
    }
  }

  async function rejectInv(i: number) {
    if (invBusy !== null) return;
    setInvBusy(i);
    setResult(null);
    try {
      const res = await getApiClient().action("reject_invention", { index: i });
      if (res.state) setState(res.state);
      setResult(res.message || "已驳回此献。");
    } catch (e) {
      console.error("[reject_invention]", e);
      setResult("驳回失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setInvBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <img src="/images/scene_tech.jpg" alt="" className="sz-scene" />
      <p className="px-1 text-sm leading-relaxed text-dim">
        天下技艺积累，皆聚于此。新制兴工：国库拨银须经廷议，内帑乾纲独断则免。
      </p>

      {/* 工部献策：大臣召对中诉献之新制，待陛下嘉纳/驳回 */}
      {inventions.length > 0 && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <SectionTitle text="工 部 献 策" />
          <div className="mt-2 space-y-2">
            {inventions.map((inv, i) => (
              <div key={i} className="rounded border border-gold/30 bg-card/70 p-2.5">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-kai text-sm font-bold text-ink">
                    {asStr(inv.kind, "新制")} · {asStr(inv.name, "未名之制")}
                  </p>
                  <span className="shrink-0 text-[11px] text-dim">
                    献策：{asStr(inv.minister, "工部")}
                  </span>
                </div>
                <p className="mt-0.5 text-xs leading-relaxed text-ink">{asStr(inv.desc, "（无详述）")}</p>
                <p className="mt-1 text-[11px] text-dim">
                  {asStr(inv.effect_dim, "成效")}：{asStr(inv.effect_tier, "中")}
                  {asStr(inv.prereq_hint, "") ? ` · 依托：${asStr(inv.prereq_hint, "")}` : ""}
                </p>
                <div className="mt-2 flex justify-end gap-2">
                  <button
                    onClick={() => approveInv(i, "treasury")}
                    disabled={invBusy !== null}
                    className="rounded bg-red px-3 py-1 text-xs font-kai text-paper transition hover:bg-red-dark disabled:opacity-50"
                  >
                    嘉纳·国库（会签）
                  </button>
                  <button
                    onClick={() => approveInv(i, "inner")}
                    disabled={invBusy !== null}
                    className="rounded bg-paper/70 px-3 py-1 text-xs font-kai text-ink transition hover:bg-gold-light disabled:opacity-50"
                  >
                    嘉纳·内帑
                  </button>
                  <button
                    onClick={() => rejectInv(i)}
                    disabled={invBusy !== null}
                    className="rounded border border-gold/50 px-3 py-1 text-xs font-kai text-ink-light transition hover:bg-gold-light/40 disabled:opacity-50"
                  >
                    驳回
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
                        const s = nodeReadoutFor(n).status;
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
      {node && nodeInfo && st && (
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
          {st === "unlocked" || st === "researching" ? (
            <p className="mt-1 text-sm text-dim">该节点已{st === "unlocked" ? "点亮" : "在攻关"}，无需再次立项。</p>
          ) : (
            <p className="mt-1 text-sm text-dim">
              耗帑 {nodeInfo.silver === null ? "未定义（后端结算时按权威口径计算）" : humanizeCoin(nodeInfo.silver)}
              　·　工期 {nodeInfo.months === null ? "未定义" : `${nodeInfo.months}月`}
              　·　{nodeInfo.reason ? `后端：${nodeInfo.reason}` : "工部领办，匠役由将作监调拨"}
            </p>
          )}
          {Object.keys(node.effect ?? {}).length > 0 && (
            <p className="mt-1 text-sm text-dim">
              {/* 复用统一效果词表：内部键名不得直出 */}
              效用：{formatEffects(node.effect)}
            </p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2 rounded border border-gold/40 bg-paper/50 px-2 py-1.5 font-kai text-xs text-ink-light">
            <span className="font-bold text-red-dark">【廷议签押】</span>
            <span>领衔</span>
            <select
              value={signoffMinister}
              onChange={(e) => setSignoffMinister(e.target.value)}
              className="rounded border border-gold/40 bg-card px-1.5 py-0.5 text-ink"
            >
              {["工部尚书", "户部尚书", "枢密使", "参知政事"].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
            <input
              type="text"
              value={summonHint}
              onChange={(e) => setSummonHint(e.target.value)}
              placeholder="钦点协赞（可空，如：着蔡京一并入对）"
              className="flex-1 min-w-[160px] rounded border border-gold/30 bg-card px-2 py-0.5 text-ink outline-none"
            />
          </div>
          <div className="mt-3 flex justify-end gap-3">
            {st === "researchable" || st === "unknown" ? (
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
              <p className="py-2 text-sm text-dim">
                {st === "locked"
                  ? `（后端判定不可立项${nodeInfo.reason ? `：${nodeInfo.reason}` : ""}）`
                  : "（已点亮/攻关中，无需立项）"}
              </p>
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
