import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { getApiClient, type ReadoutsResult, type ArmyUnitReadout } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import { wan } from "../utils/format";

// 军政机务 —— 对齐 game/ui/panels_economy.py::_panel_military_affairs（L644）
// 诸军实体/边防要线/战事动态/中央武库，全部只读（Tk 版亦无施政按钮）。
// 军队/武库/防线为后端对象，经 /api/readouts 派生读数取。
type Dict = Record<string, unknown>;

// panels_military.py::EQUIP_KEYS
const EQUIP_KEYS: [string, string][] = [
  ["枪刀", "件"], ["弓弩", "件"], ["火器", "件"],
  ["战马", "匹"], ["盔甲", "件"], ["舟船", "艘"], ["器械", "件"]
];

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}

function SectionTitle({ text }: { text: string }) {
  return <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">{text}</p>;
}

export default function MilitaryPanel() {
  const state = useGameStore((s) => s.state);
  const [ro, setRo] = useState<ReadoutsResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  // 诸军明细窗（阶段 B-3：点开某军 → 人员/兵种/装备/士气/欠饷）
  const [detail, setDetail] = useState<ArmyUnitReadout | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().readouts();
        if (alive) setRo(res);
      } catch (e) {
        console.error("[readouts]", e);
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { alive = false; };
  }, []);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无军机可览。</p>;
  }

  const settlement = pick<unknown[]>(state, "settlement_log", []);
  const lastLog = settlement.length
    ? (Array.isArray(settlement[settlement.length - 1])
        ? (settlement[settlement.length - 1] as string[]).map(String)
        : [String(settlement[settlement.length - 1])])
    : [];

  // 诸军按驻地分组（对齐 Tk：按 prefectures 顺序，组内禁军优先、兵额降序）
  const army = ro?.army ?? [];
  const byStation = new Map<string, typeof army>();
  for (const u of army) {
    const list = byStation.get(u.station) ?? [];
    list.push(u);
    byStation.set(u.station, list);
  }
  const stations = Object.keys(asDict(pick(state, "prefectures", {}))).filter(
    (st) => byStation.get(st)?.length
  );

  const defenseLines = Object.entries(ro?.defense_lines ?? {});

  return (
    <div className="space-y-4">
      <img src="/images/scene_arsenal.jpg" alt="" className="sz-scene" />
      <p className="px-1 text-sm leading-relaxed text-dim">
        军机事务：诸军实体、边防线、战事、中央武库。凡军国诏令皆下诏推演。
      </p>

      {!ro && (
        <div className="flex items-center justify-center gap-2 rounded-lg border border-gold/40 bg-paper/60 p-4 text-sm text-dim">
          {error ? (
            <span className="text-red">军备读数读取失败：{error}</span>
          ) : (
            <>
              <Loader2 size={14} className="animate-spin" /> 枢密院军籍核算中…
            </>
          )}
        </div>
      )}

      {/* 诸军实体 */}
      {ro && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <SectionTitle text="诸 军 实 体" />
          <div className="mt-1.5 space-y-3">
            {stations.map((st) => {
              const units = [...(byStation.get(st) ?? [])].sort(
                (a, b) => (a.tier === "禁军" ? 0 : 1) - (b.tier === "禁军" ? 0 : 1) || b.troops - a.troops
              );
              return (
                <div key={st}>
                  <p className="font-kai text-sm font-bold text-red">{st}</p>
                  {units.map((u) => {
                    const brs = Object.entries(asDict(u.branches))
                      .filter(([, n]) => asNum(n) > 0)
                      .map(([b, n]) => `${b}${n}`)
                      .join("/");
                    return (
                      <button
                        key={u.unit_id}
                        type="button"
                        onClick={() => setDetail(u)}
                        title="点开查看该军明细：人员 / 兵种 / 装备 / 士气 / 欠饷"
                        className="flex w-full items-baseline justify-between gap-3 rounded py-0.5 pl-4 pr-1 text-left hover:bg-gold/10"
                      >
                        <span className="min-w-0 truncate text-[13px] text-ink">
                          {u.name}（{brs}）
                        </span>
                        <span className="shrink-0 text-xs text-dim">
                          {wan(u.troops, "人")}　备{Math.round(asNum(u.equip_rate) * 100)}%　
                          气{Math.round(asNum(u.morale))}　训{Math.round(asNum(u.training))}　{u.defense_line}
                          {asNum(u.arrears) > 0 && (
                            <span className="ml-2 text-red">欠饷{wan(asNum(u.arrears), "贯")}</span>
                          )}
                        </span>
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 边防要线 */}
      {ro && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <SectionTitle text="边 防 要 线" />
          <div className="mt-1.5">
            {defenseLines.map(([ln, l]) => (
              <div key={ln} className="flex items-baseline justify-between gap-3 py-1">
                <span className="font-kai text-sm font-bold text-red">{ln}</span>
                <span className="text-sm text-ink">
                  驻防{wan(asNum(l.garrison), "人")}　城防{asNum(l.fortification)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 战事动态 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="战 事 动 态" />
        <div className="mt-1.5">
          {lastLog.length ? (
            lastLog.map((e, i) => (
              <p key={i} className="py-0.5 text-sm text-ink">· {e}</p>
            ))
          ) : (
            <p className="py-1 text-sm text-dim">— 边境无事，海内承平 —</p>
          )}
        </div>
      </div>

      {/* 中央武库 */}
      {ro && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <SectionTitle text="中 央 武 库" />
          <p className="mt-1.5 text-sm leading-relaxed text-ink">
            {EQUIP_KEYS.map(([k, unit]) => `${k}${wan(asNum(asDict(ro.arsenal)[k]), unit)}`).join("　")}
          </p>
        </div>
      )}

      {/* 诸军明细窗（阶段 B-3：点开某军 → 人员 / 兵种 / 装备 / 士气 / 欠饷） */}
      {detail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setDetail(null)}
        >
          <div
            className="max-h-[80vh] w-full max-w-lg overflow-auto rounded-lg border border-gold/60 bg-paper p-4 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-baseline justify-between gap-3">
              <p className="font-kai text-base font-bold text-red">{detail.name}</p>
              <button
                type="button"
                onClick={() => setDetail(null)}
                className="shrink-0 rounded border border-gold/40 px-2 py-0.5 text-xs text-dim hover:bg-gold/10"
              >
                关闭
              </button>
            </div>
            <p className="mt-1 text-xs text-dim">
              {detail.tier}　{detail.army_name || "—"}　{detail.org_arm || "—"}　
              {detail.scale || "—"}{detail.serial ? `第${detail.serial}` : ""}
            </p>

            <dl className="mt-3 space-y-1.5 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="shrink-0 text-dim">驻地 / 防区</dt>
                <dd className="text-right text-ink">{detail.station}　{detail.defense_line}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-dim">兵力</dt>
                <dd className="text-ink">{wan(asNum(detail.troops), "人")}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-dim">士气 / 训练</dt>
                <dd className="text-ink">气{Math.round(asNum(detail.morale))}　训{Math.round(asNum(detail.training))}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-dim">装备配给率</dt>
                <dd className="text-ink">{Math.round(asNum(detail.equip_rate) * 100)}%</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="shrink-0 text-dim">累计欠饷</dt>
                <dd className={asNum(detail.arrears) > 0 ? "font-bold text-red" : "text-ink"}>
                  {wan(asNum(detail.arrears), "贯")}
                </dd>
              </div>
            </dl>

            <p className="mt-3 font-kai text-sm font-bold text-red">兵 种 构 成</p>
            <ul className="mt-1 space-y-0.5 text-sm text-ink">
              {Object.entries(asDict(detail.branches))
                .filter(([, n]) => asNum(n) > 0)
                .sort((a, b) => asNum(b[1]) - asNum(a[1]))
                .map(([b, n]) => (
                  <li key={b} className="flex justify-between gap-3">
                    <span>{b}</span>
                    <span>{asNum(n).toLocaleString()}人</span>
                  </li>
                ))}
            </ul>

            <p className="mt-3 font-kai text-sm font-bold text-red">装 备 明 细</p>
            <ul className="mt-1 space-y-0.5 text-sm text-ink">
              {EQUIP_KEYS.map(([k, unit]) => (
                <li key={k} className="flex justify-between gap-3">
                  <span>{k}</span>
                  <span>{wan(asNum(asDict(detail.equip)[k]), unit)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
