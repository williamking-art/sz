// 舆图要素详情卡：城池/诸路/政权/分路
export default function DetailPanel({ props }: { props?: Record<string, unknown> }) {
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
    </div>
  );
}

function str(v: unknown): string {
  if (v === undefined || v === null) return "";
  return String(v);
}