import { useGameStore, pick } from "../store/gameStore";

// 中枢机构 / 监察 —— 对齐 Tk 版 _panel_central_org（只读展示）
// 中央机构（central_orgs：leader/在任职守/事权/预算结余/效率/积压）+ 监察力度(oversight) + 密探(spy_network)。
type Dict = Record<string, unknown>;

function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}
function asDict(v: unknown): Dict {
  return v && typeof v === "object" ? (v as Dict) : {};
}
function asArr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function holdersText(post: unknown, holders: Dict): string {
  const p = asDict(post);
  const title = asStr(p.title, asStr(p.t, "佚职"));
  const holder = asStr(holders[title], "");
  return holder ? `${holder} 任 ${title}` : `（虚位） ${title}`;
}

export default function CentralOrgPanel() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  // 迁移补齐（原 Tk `_panel_central_org` 的「点卡片召对」）：机构主官/在职者可直达御前召对
  function openAudience(name: string, role: string) {
    if (!name) return;
    pushOverlay({ kind: "audience", title: `御前召对 · ${name}`, props: { minister: name, role } });
  }
  const orgs = asDict(pick<Dict>(state, "central_orgs", {}));
  const oversight = asNum(pick<number>(state, "oversight", 0), 0);
  const spy = asDict(pick<Dict>(state, "spy_network", {}));
  const entries = Object.keys(orgs).map((name) => {
    const o = asDict(orgs[name]);
    return {
      name,
      lead: asStr(o.lead, "—"),
      posts: asArr(o.posts),
      holders: asDict(o.holders),
      matters: asArr(o.matter_keys).map((m) => asStr(m)),
      net: asNum(o.net),
      eff: asNum(o.efficiency),
      backlog: asNum(o.backlog),
      abolished: o.abolished === true,
    };
  });

  return (
    <div className="space-y-4">
      {/* 监察与密探 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
        <p className="font-kai text-[15px] font-bold tracking-widest text-red">监 察 与 密 探</p>
        <p className="mt-1.5 text-sm text-ink">监察力度：{Math.round(oversight * 100)}</p>
        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
          {Object.keys(spy).map((k) => (
            <p key={k} className="text-xs text-ink-light">
              {k}　{Math.round(asNum(spy[k]) * 100)}
            </p>
          ))}
        </div>
      </div>

      {/* 中枢机构 */}
      <div className="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
        {entries.map((r) => (
          <div
            key={r.name}
            className={`rounded-lg border bg-paper/60 p-3 ${r.abolished ? "border-[#7a7a7a] opacity-60" : "border-gold/40"}`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <p className="font-kai text-[14px] font-bold text-ink">{r.name}{r.abolished ? "（罢废）" : ""}</p>
              <span className="flex shrink-0 items-center gap-2">
                <span className="text-xs text-dim">领：{r.lead}</span>
                {r.lead && r.lead !== "—" && !r.abolished && (
                  <button
                    onClick={() => openAudience(r.lead, `${r.name}·主官`)}
                    className="rounded border border-gold/50 bg-paper px-1.5 py-0.5 text-[10px] text-ink transition hover:bg-gold-light/40"
                  >
                    召对
                  </button>
                )}
              </span>
            </div>
            <p className="mt-1 text-xs text-dim">
              事权：{r.matters.length ? r.matters.join(" / ") : "—"}
            </p>
            {r.posts.map((p, i) => {
              const _title = asStr(asDict(p).title, asStr(asDict(p).t, "佚职"));
              const _holder = asStr(r.holders[_title], "");
              return (
                <div key={i} className="mt-0.5 flex items-center justify-between gap-2">
                  <p className="min-w-0 flex-1 text-xs text-ink-light">　{holdersText(p, r.holders)}</p>
                  {_holder && !r.abolished && (
                    <button
                      onClick={() => openAudience(_holder, `${r.name}·${_title}`)}
                      className="shrink-0 rounded border border-gold/40 bg-paper px-1.5 py-0.5 text-[10px] text-ink-light transition hover:bg-gold-light/40 hover:text-ink"
                    >
                      召对
                    </button>
                  )}
                </div>
              );
            })}
            <p className="mt-1 text-xs text-dim">
              效 {r.eff}　积压 {r.backlog}　预支结余 {r.net > 0 ? `+${r.net}` : r.net}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}