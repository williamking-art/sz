import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import { humanizeCoin } from "../utils/format";
import constants from "../data/constants.json";

// 个人行止 —— 对齐 game/ui/panels_economy.py::_panel_personal（L195）
// 全矩阵：地点（宫里/京城/出京）× 方式（公开/微服）→ 行动白名单（constants.json::imperial_matrix）。
// 钦定行止 → action("choose_imperial_action", { location, mode, action, target, prepared: false })。
// 风险概率/距离档为纯展示常量（content/data.py::IMPERIAL_RISK_PROB / IMPERIAL_ROUTE_DISTANCE）。
type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}

// content/data.py::IMPERIAL_RISK_PROB
const RISK_PROB: Record<string, number> = { 低: 0.02, 中: 0.08, 高: 0.2 };
const RISK_COLOR: Record<string, string> = {
  低: "text-[#5a7a3c]",
  中: "text-[#8f6e28]",
  高: "text-[#8a2b22]"
};
// content/data.py::IMPERIAL_ROUTE_DISTANCE / IMPERIAL_DISTANCE_MONTHS
const ROUTE_DISTANCE: [string, string[]][] = [
  ["近", ["开封", "京畿", "京西", "京东"]],
  ["中", ["河北", "河东", "淮南", "京西南", "京西北", "京东南", "京东北"]],
  ["远", ["陕西", "江南", "两浙", "荆湖", "四川", "广南", "福建", "燕云", "永兴", "秦凤"]]
];
const DISTANCE_MONTHS: Record<string, number> = { 近: 0, 中: 1, 远: 2 };

function imperialDistance(target: string): string {
  for (const [d, kws] of ROUTE_DISTANCE) {
    if (kws.some((k) => target.includes(k))) return d;
  }
  return "中";
}

// panels_economy.py::_IMPERIAL_EFFECT_NAMES
const EFFECT_NAMES: Record<string, string> = {
  prestige: "威望",
  population_satisfaction: "民心",
  emperor_health: "健康",
  pleasure_leaning: "心情",
  art_mastery: "艺术造诣",
  taoism_leaning: "道门倾向",
  bandwidth_bonus: "圣旨额度",
  faction_change: "派系"
};

const LOCATIONS = constants.imperial_locations as string[];
const MODES = constants.imperial_modes as string[];
const MATRIX = constants.imperial_matrix as Record<string, Record<string, Dict>>;
const LOC_NOTE: Record<string, string> = {
  宫里: "宫中视事，政务闲暇",
  京城: "汴京内外，四方辐辏",
  出京: "离京巡幸，需备銮驾"
};

interface ActionRow {
  name: string;
  cell: Dict;
  disabled: string;
  reason: string;
}

export default function PersonalPanel() {
  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);
  const [loc, setLoc] = useState("宫里");
  const [mode, setMode] = useState("公开");
  const [sel, setSel] = useState(0);
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const pending = pick<Dict | null>(state, "pending_imperial_trip", null);
  const cur = asDict(pick(state, "imperial_action", {}));
  const microUsed = asNum(pick(state, "imperial_micro_count", 0)) >= 1;
  const year = asNum(pick(state, "year", 0));

  const rows = useMemo<ActionRow[]>(() => {
    const matrix = asDict(MATRIX[loc]?.[mode]);
    const blocked = pending !== null;
    return Object.entries(matrix).map(([name, cellRaw]) => {
      const cell = asDict(cellRaw);
      let disabled = "";
      let reason = "";
      if (blocked) {
        disabled = "blocked";
        reason = "大驾出京准备中，不可另定行止";
      } else if (cell.micro_once === true && microUsed) {
        disabled = "micro";
        reason = "陛下本月已微服出宫，只可一次";
      } else if (cell.era_gate != null && year < asNum(cell.era_gate)) {
        disabled = "era";
        reason = `未至该时代（${asNum(cell.era_gate)} 年起可行）`;
      }
      return { name, cell, disabled, reason };
    });
  }, [loc, mode, pending, microUsed, year]);

  const row = rows[sel] ?? null;
  const noMicro = loc === "宫里";

  function setLocSafe(k: string) {
    setLoc(k);
    if (k === "宫里") setMode("公开");
    setSel(0);
  }

  function effectLine(cell: Dict): string {
    const eff = asDict(cell.base_effects);
    const parts: string[] = [];
    for (const [k, v] of Object.entries(eff)) {
      if (k === "faction_change") {
        const fc = Object.entries(asDict(v))
          .map(([fn, val]) => `${fn}${(val as number) > 0 ? "+" : ""}${val}`)
          .join("、");
        parts.push(`派系 ${fc}`);
        continue;
      }
      parts.push(`${EFFECT_NAMES[k] ?? k}${(v as number) > 0 ? "+" : ""}${v}`);
    }
    return parts.join("，");
  }

  async function confirm() {
    if (busy || !row) return;
    if (row.disabled) {
      setResult(row.reason || "此行动暂不可行。");
      return;
    }
    let t = "";
    if (row.cell.distance === true) {
      t = target.trim();
      if (!t) {
        setResult("请填写微服目标州路（如「两浙路」）。");
        return;
      }
    }
    setBusy(true);
    setResult(null);
    try {
      const res = await getApiClient().action("choose_imperial_action", {
        location: loc,
        mode,
        action: row.name,
        target: t,
        prepared: false
      });
      setState(res.state);
      setResult(res.message);
    } catch (e) {
      console.error("[choose_imperial_action]", e);
      setResult("钦定失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  const distHint = (() => {
    const t = target.trim();
    if (!t || !row || row.cell.distance !== true) return "";
    const d = imperialDistance(t);
    return `「${d}」备 ${DISTANCE_MONTHS[d]} 月`;
  })();

  return (
    <div className="space-y-4">
      {/* 顶部：当前行止状态 */}
      {pending !== null ? (
        <p className="font-kai text-sm font-bold text-[#8a2b22]">
          大驾出京准备中：「{asStr(pending.action)}」尚余 {asNum(pending.pending_months, 1)} 月（准备期内不可另定行止）
        </p>
      ) : asStr(cur.action) ? (
        <p className="font-kai text-sm font-bold text-red">
          本回合已定行止：{asStr(cur.location)}·{asStr(cur.mode)}·{asStr(cur.action)}（月末结算生效）
        </p>
      ) : (
        <p className="text-sm text-dim">择地点与行止方式，钦定陛下本回合行止（每月一次）。</p>
      )}

      {/* 主区：左地点 / 右方式+行动 */}
      <div className="flex flex-col gap-4 xl:flex-row">
        {/* 左：地点 */}
        <div className="w-full shrink-0 xl:w-44">
          <p className="font-kai text-sm font-bold text-red">行止地点</p>
          <div className="mt-2 space-y-2">
            {LOCATIONS.map((k) => (
              <button
                key={k}
                onClick={() => setLocSafe(k)}
                className={`w-full rounded-lg px-4 py-2 font-kai text-sm tracking-widest transition ${
                  loc === k ? "bg-red text-paper" : "bg-paper/60 text-red hover:bg-gold-light"
                }`}
              >
                {k}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs leading-relaxed text-dim">{LOC_NOTE[loc] ?? ""}</p>
        </div>

        {/* 右：方式 + 行动列表 + 细目 */}
        <div className="min-w-0 flex-1 space-y-3">
          {/* 方式行 */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-ink">行止方式：</span>
            {MODES.map((md) => {
              const disabledBtn = md === "微服" && noMicro;
              return (
                <button
                  key={md}
                  disabled={disabledBtn}
                  onClick={() => { setMode(md); setSel(0); }}
                  className={`rounded-lg px-4 py-1.5 font-kai text-sm tracking-widest transition ${
                    mode === md ? "bg-red text-paper" : "bg-paper/60 text-red hover:bg-gold-light"
                  } ${disabledBtn ? "cursor-not-allowed opacity-40" : ""}`}
                >
                  {md === "公开" ? "公开大驾" : "微服便服"}
                </button>
              );
            })}
            <span className="text-xs text-dim">
              {noMicro ? "宫里不设微服（宫中即陛下起居之地）。" : "微服出行开销走内帑，暴露风险较高。"}
            </span>
          </div>

          {/* 行动列表 + 细目 */}
          <div className="flex flex-col gap-3 xl:flex-row">
            {/* 列表 */}
            <div className="min-w-0 flex-1 rounded-lg border border-gold/40 bg-paper/60 p-3">
              <p className="font-kai text-sm font-bold tracking-[0.3em] text-red">可 行 之 事</p>
              <div className="mt-2 space-y-1">
                {rows.length === 0 && (
                  <p className="py-6 text-center text-sm text-dim">（该格子无可行行动）</p>
                )}
                {rows.map((r, i) => {
                  const fundLab = r.cell.fund === "treasury" ? "国库" : "内帑";
                  return (
                    <button
                      key={r.name}
                      onClick={() => setSel(i)}
                      className={`w-full rounded-md px-3 py-1.5 text-left text-sm transition ${
                        sel === i ? "bg-red text-paper" : "bg-card text-ink hover:bg-gold-light"
                      } ${r.disabled ? "opacity-50" : ""}`}
                    >
                      {r.disabled ? "〔不可〕" : "　"}
                      {r.name}　·　{fundLab} {humanizeCoin(asNum(r.cell.base_cost))}
                      　·　风险{asStr(r.cell.risk, "低")}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 细目 */}
            <div className="w-full shrink-0 rounded-lg border border-gold/40 bg-paper/60 p-3 xl:w-72">
              <p className="font-kai text-sm font-bold tracking-[0.3em] text-red">细 目</p>
              {!row ? (
                <p className="mt-3 text-center font-kai text-[15px] font-bold text-red">（请选行动）</p>
              ) : (
                <div className="mt-2 space-y-1.5">
                  <p className="text-center font-kai text-[15px] font-bold text-red">{row.name}</p>
                  <p className="text-sm leading-relaxed text-ink">{asStr(row.cell.desc)}</p>
                  <div className="space-y-1 text-sm">
                    <p className="text-ink">
                      开销：{row.cell.fund === "treasury" ? "国库" : "内帑"} {humanizeCoin(asNum(row.cell.base_cost))}
                    </p>
                    <p className={`font-bold ${RISK_COLOR[asStr(row.cell.risk, "低")] ?? "text-ink"}`}>
                      风险：{asStr(row.cell.risk, "低")}（{Math.round((RISK_PROB[asStr(row.cell.risk, "低")] ?? 0.02) * 100)}%）
                    </p>
                    {effectLine(row.cell) && (
                      <p className="text-red">预期：{effectLine(row.cell)}</p>
                    )}
                    {Boolean(row.cell.bandwidth_cost) && (
                      <p className="text-xs text-dim">圣旨额度 -1（大驾在途，远程批奏）</p>
                    )}
                    {Boolean(row.cell.micro_once) && (
                      <p className="text-xs text-dim">微服限次：每月 1 次</p>
                    )}
                    {Boolean(row.cell.prep) && (
                      <p className="text-xs text-dim">准备期：{asNum(row.cell.prep)} 月（銮驾备毕成行）</p>
                    )}
                  </div>
                  {row.reason && (
                    <p className="text-xs leading-relaxed text-[#8f6e28]">{row.reason}</p>
                  )}
                  {/* 微服他地：目标路名输入（距离核算） */}
                  {row.cell.distance === true && (
                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-sm text-ink">目标路：</span>
                      <input
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                        placeholder="如「两浙路」"
                        className="w-28 rounded-lg border border-border bg-card px-2 py-1 text-sm text-ink outline-none focus:border-gold"
                      />
                      <span className="text-xs text-dim">{distHint}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 底部：钦定行止 */}
      <div className="flex justify-end gap-3">
        <button
          onClick={confirm}
          disabled={busy}
          className="flex items-center gap-2 rounded-lg bg-red px-6 py-2 font-kai text-base tracking-widest text-paper transition hover:bg-red-dark disabled:opacity-60"
        >
          {busy && <Loader2 size={16} className="animate-spin" />}
          {busy ? "钦定中…" : "钦 定 行 止"}
        </button>
      </div>

      {result && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <p className="whitespace-pre-wrap font-kai text-[15px] leading-relaxed text-ink">{result}</p>
        </div>
      )}
    </div>
  );
}
