import { useGameStore } from "../store/gameStore";
import { Scroll, Landmark, Search } from "lucide-react";

// 舆图要素详情卡：城池/诸路/政权/分路
export default function DetailPanel({ props }: { props?: Record<string, unknown> }) {
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const kind = typeof props?.kind === "string" ? props.kind : "";
  const name = typeof props?.name === "string" ? props.name : "";
  const p = (props?.props as Record<string, unknown>) || {};

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