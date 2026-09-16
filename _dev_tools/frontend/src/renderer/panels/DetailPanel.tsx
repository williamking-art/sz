import { useGameStore } from "../store/gameStore";
import { Scroll, Landmark, Search } from "lucide-react";

/** 外邦省份反查（迁移补齐：Tk `_panel_external_province`，l.1635）：
 *  从 state.external_regimes[*].provinces 里按省名（可加 owner/parent 限定）定位。 */
function findExternalProvince(
  state: unknown,
  p: Record<string, unknown>,
  name: string
): [string, Record<string, unknown>] | null {
  const ext = state && typeof state === "object"
    ? (state as Record<string, unknown>).external_regimes
    : null;
  if (!ext || typeof ext !== "object") return null;
  const regimes = ext as Record<string, Record<string, unknown>>;
  const ownerKey = String(p.owner ?? p.parent ?? p.regime ?? p.name ?? "");
  for (const [rk, rv] of Object.entries(regimes)) {
    if (!rv || typeof rv !== "object") continue;
    const rname = String(rv.name ?? rk);
    if (ownerKey && ownerKey !== rk && ownerKey !== rname) continue;
    const provs = Array.isArray(rv.provinces) ? rv.provinces : [];
    for (const pv of provs) {
      if (pv && typeof pv === "object" &&
          String((pv as Record<string, unknown>).name ?? "") === name) {
        return [rk, pv as Record<string, unknown>];
      }
    }
  }
  return null;
}

// 舆图要素详情卡：城池/诸路/政权/分路
export default function DetailPanel({ props }: { props?: Record<string, unknown> }) {
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const state = useGameStore((s) => s.state);
  const kind = typeof props?.kind === "string" ? props.kind : "";
  const name = typeof props?.name === "string" ? props.name : "";
  const p = (props?.props as Record<string, unknown>) || {};
  const extProv = kind === "sub" ? findExternalProvince(state, p, name) : null;

  const kindText: Record<string, string> = {
    city: "城池", circuit: "诸路", regime: "政权", sub: "分路"
  };

  const rows: [string, string][] = [];
  if (kind === "city") {
    rows.push(["等级", str(p.level) || (p.is_seat ? "府城" : "州城")]);
    rows.push(["所属路分", str(p.circuit)]);
    rows.push(["职任", p.is_seat ? "路道治所" : "属城"]);
    if (p.game_unit) rows.push(["辖区经济", str(p.game_unit)]);
  } else if (kind === "circuit" || kind === "sub") {
    if (p.type) rows.push(["类型", str(p.type)]);
    if (p.seat) rows.push(["治所府城", str(p.seat)]);
    if (p.member_count) rows.push(["辖属州府", `${p.member_count} 州/府`]);
    if (p.owner || p.parent || (p.name && p.name !== name)) {
      rows.push(["所属势力", str(p.owner || p.parent || p.name)]);
    }
    if (p.game_unit) rows.push(["辖属经济", str(p.game_unit)]);
  } else {
    rows.push(["状态", p.active ? "活跃" : "中立/未兴"]);
    if (p.owner) rows.push(["所属主号", str(p.owner)]);
    if (p.province && p.province !== name) rows.push(["省道区域", str(p.province)]);
  }

  return (
    <div className="space-y-3">
      <div className="font-kai text-lg tracking-widest text-ink">{name}</div>
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        {rows.filter(([, v]) => v).map(([k, v]) => (
          <div key={k} className="flex justify-between py-1 text-sm">
            <span className="text-ink-light">{k}</span>
            <span className="text-ink">{v}</span>
          </div>
        ))}
      </div>
      {str(p.note) && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3 text-sm leading-relaxed text-ink">
          {str(p.note)}
        </div>
      )}

      {/* 外邦省份详情（迁移补齐：Tk `_panel_external_province` 的三块——
          人口 / 军队（名·员·气·训·兵种）/ 建筑） */}
      {extProv && (
        <>
          <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
            <p className="font-kai text-sm font-bold tracking-widest text-red">人 口</p>
            <p className="mt-1 text-sm text-ink">
              在籍 {Number(extProv[1].population ?? 0).toLocaleString("en-US")} 口
              {extProv[1].weight !== undefined && (
                <span className="ml-3 text-ink-light">
                  占国 {Math.round(Number(extProv[1].weight ?? 0) * 100)}%
                </span>
              )}
            </p>
          </div>
          <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
            <p className="font-kai text-sm font-bold tracking-widest text-red">军 队</p>
            {(Array.isArray(extProv[1].armies) ? (extProv[1].armies as Record<string, unknown>[]) : [])
              .length > 0 ? (
              (extProv[1].armies as Record<string, unknown>[]).map((a, i) => (
                <div key={i} className="mt-1.5">
                  <p className="text-sm text-ink">
                    {str(a.name)}　员 {Number(a.troops ?? 0).toLocaleString("en-US")}
                    　气 {Number(a.morale ?? 0)}　训 {Number(a.training ?? 0)}
                  </p>
                  <p className="text-xs text-ink-light">
                    {Object.entries((a.branches as Record<string, number>) ?? {})
                      .map(([k, v]) => `${k}${Number(v).toLocaleString("en-US")}`)
                      .join("、")}
                  </p>
                </div>
              ))
            ) : (
              <p className="mt-1 text-sm text-dim">尚无常备军。</p>
            )}
          </div>
          <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
            <p className="font-kai text-sm font-bold tracking-widest text-red">建 筑</p>
            {Object.keys((extProv[1].buildings as Record<string, unknown>) ?? {}).length > 0 ? (
              <p className="mt-1 text-sm text-ink">
                {Object.entries((extProv[1].buildings as Record<string, unknown>) ?? {})
                  .map(([k, v]) => `${k}×${Number(v)}`)
                  .join("　")}
              </p>
            ) : (
              <p className="mt-1 text-sm text-dim">（未见城郭营造，或为穹庐部落）</p>
            )}
          </div>
        </>
      )}

      {/* 治国施政与巡幸操作区 */}
      <div className="pt-2 flex flex-col gap-2">
        {/* 1. 若为宋朝经济单位、路分或所属府州，提供直达账册功能 */}
        {(p.game_unit || (kind === "circuit" && name) || Boolean(p.circuit)) && (
          <button
            onClick={() => {
              const target = String(p.game_unit || (kind === "circuit" ? name : String(p.circuit || "")) || name);
              pushOverlay({
                kind: "prefecture",
                title: `${target} 治理`,
                props: { picked: target },
              });
            }}
            className="flex items-center justify-center gap-2 rounded border border-gold/60 bg-paper px-3 py-1.5 font-kai text-sm text-ink shadow-sm transition hover:border-gold hover:bg-gold-light/40"
          >
            <Landmark size={15} className="text-goldDark" /> 查阅路分账册 ({String(p.game_unit || (kind === "circuit" ? name : String(p.circuit || "")) || name)})
          </button>
        )}

        <div className="grid grid-cols-2 gap-2">
          {/* 2. 聚焦巡阅 (平滑镜头飞跃下钻) */}
          <button
            onClick={() => {
              window.dispatchEvent(
                new CustomEvent("sz:map-focus", {
                  detail: { name, kind, props: p },
                })
              );
            }}
            className="flex items-center justify-center gap-1.5 rounded border border-gold/40 bg-paper/80 px-2 py-1.5 font-kai text-xs text-ink transition hover:bg-gold-light/30"
          >
            <Search size={13} className="text-ink-light" /> 巡阅聚焦
          </button>

          {/* 3. 颁旨施政快捷入口 */}
          <button
            onClick={() => {
              pushOverlay({ kind: "decree", title: "拟旨" });
            }}
            className="flex items-center justify-center gap-1.5 rounded border border-red/40 bg-paper/80 px-2 py-1.5 font-kai text-xs text-red transition hover:bg-red/10"
          >
            <Scroll size={13} className="text-red" /> 拟旨施政
          </button>
        </div>
      </div>
    </div>
  );
}

function str(v: unknown): string {
  if (v === undefined || v === null) return "";
  return String(v);
}