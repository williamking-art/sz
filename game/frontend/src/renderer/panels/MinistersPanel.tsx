import { useState } from "react";
import { Loader2, User, Swords } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import { portraitSrc } from "../utils/portrait";
import constants from "../data/constants.json";
import codexData from "../data/codex.json";

// 群臣名录 —— 对齐 game/ui/panels_govern.py::_panel_yamen（L1498）
// 三段卡片网格：宰执（跟人：占尚书左/右仆射者所属派系）/ 派系领袖 / 六部尚书。
// 召见奏对 → action("audience_dialogue", { minister, text })（对齐 backend/client.py）。
// 降级说明：Tk 版大臣年龄/个性/生平时取后端 MINISTERS/persona/CODEX_MINISTER_BIO，
// HTTP 契约未暴露，以派系与衙门运行态数据代替；立绘以 lucide 占位符代替。
type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}

// 武臣派系（对齐 _minister_kind：FACTION_PROFILES.kind == military）
const MILITARY_FACTIONS = new Set(["军功集团", "皇党集团"]);

interface CardInfo {
  name: string;
  role: string;
  faction: string;
  kind: "civil" | "military";
}

function SectionTitle({ text }: { text: string }) {
  return <p className="font-kai text-[15px] font-bold tracking-[0.3em] text-red">{text}</p>;
}

export default function MinistersPanel() {
  const state = useGameStore((s) => s.state);
  const readouts = useGameStore((s) => s.readouts);
  const [tab, setTab] = useState<"cabinet" | "all">("cabinet");
  const pushOverlay = useGameStore((s) => s.pushOverlay);

  function openAudience(name: string, role: string) {
    pushOverlay({
      kind: "audience",
      title: `御前召对 · ${name}`,
      props: { minister: name, role }
    });
  }

  const factions = state ? asDict(pick(state, "factions", {})) : {};
  const yamen = state ? asDict(pick(state, "yamen", {})) : {};
  const centralOrgs = asDict(pick(state, "central_orgs", {}));

  // 宰执派系（跟人）：占尚书左/右仆射者所属派系
  const holders = asDict(asDict(centralOrgs["尚书省"]).holders);
  const chancellorNames = new Set(
    ["尚书左仆射", "尚书右仆射"].map((p) => asStr(holders[p])).filter(Boolean)
  );
  const chancellorFactions = new Set(
    Object.entries(factions)
      .filter(([, f]) => chancellorNames.has(asStr(asDict(f).leader)))
      .map(([fn]) => fn)
  );

  // 宰执卡
  const chancellorCards: CardInfo[] = [...chancellorFactions]
    .map((fn) => {
      const f = asDict(factions[fn]);
      const leader = asStr(f.leader);
      return {
        name: leader,
        role: `${fn}·宰执`,
        faction: fn,
        kind: MILITARY_FACTIONS.has(fn) ? ("military" as const) : ("civil" as const)
      };
    })
    .filter((c) => c.name);

  // 其余派系领袖卡
  const leaderCards: CardInfo[] = (constants.faction_names as string[])
    .filter((fn) => !chancellorFactions.has(fn) && asDict(factions[fn]).leader)
    .map((fn) => ({
      name: asStr(asDict(factions[fn]).leader),
      role: `${fn}·领袖`,
      faction: fn,
      kind: MILITARY_FACTIONS.has(fn) ? ("military" as const) : ("civil" as const)
    }));

  // 六部尚书卡（附衙门运行态）
  const yamenCards = (constants.yamen_list as string[]).map((name) => {
    const y = asDict(yamen[name]);
    const facName = asStr(y.faction);
    const leader = asStr(asDict(factions[facName]).leader);
    return {
      name: leader || `${name}堂官`,
      role: `尚书·${name}`,
      faction: facName,
      kind: MILITARY_FACTIONS.has(facName) ? ("military" as const) : ("civil" as const),
      yamen: y
    };
  });

  const allMinisters = (codexData.minister || []) as any[];
  // 群臣档案（/api/readouts::ministers）：含按品级合成的立绘 URL（官级变化即换官服）
  const minProf = (readouts?.ministers || {}) as Record<
    string, { portrait?: string; tier?: string }
  >;

  return (
    <div className="space-y-4">
      {/* 顶部模式切换 Tab */}
      <div className="flex items-center justify-between border-b border-gold/40 pb-2">
        <div className="flex gap-2">
          <button
            onClick={() => setTab("cabinet")}
            className={`rounded px-3 py-1 font-kai text-sm transition ${
              tab === "cabinet"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            宰执三省
          </button>
          <button
            onClick={() => setTab("all")}
            className={`rounded px-3 py-1 font-kai text-sm transition ${
              tab === "all"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            朝野列卿 ({allMinisters.length}人)
          </button>
        </div>
        <p className="text-xs text-dim font-kai">
          {tab === "cabinet" ? "尚书省/枢密院/六部现任长官" : "北宋建中靖国年间在朝与在野名臣全览"}
        </p>
      </div>

      {tab === "all" ? (
        /* 全景列卿名录 */
        <div className="grid grid-cols-2 gap-3 max-h-[500px] overflow-y-auto pr-1">
          {allMinisters.map((m) => {
            const inOffice = m.sub === "在朝";
            const faction = m.fields?.find((f: any) => f[0] === "派系")?.[1] || "—";
            const role = m.fields?.find((f: any) => f[0] === "职司")?.[1] || "—";
            const traits = m.fields?.find((f: any) => f[0] === "性情")?.[1] || "";
            return (
              <div
                key={m.key}
                className="group relative flex flex-col justify-between rounded-[3px] border border-border bg-card p-3 shadow-paper transition hover:border-gold hover:bg-gold-light/20"
              >
                <div className="flex gap-2.5">
                  {minProf[m.name]?.portrait && (
                    <img
                      src={portraitSrc(minProf[m.name].portrait)}
                      alt={m.name}
                      className="h-[74px] w-14 shrink-0 rounded border border-gold/50 bg-paper/60 object-cover object-top"
                    />
                  )}
                  <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-kai text-base font-bold text-ink">{m.name}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-kai ${
                        inOffice ? "bg-red/10 text-red-dark border border-red/30" : "bg-paper text-dim"
                      }`}
                    >
                      {m.sub}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-ink-light">
                    <span className="text-dim">派系：</span>{faction}
                  </div>
                  <div className="text-xs text-ink-light truncate" title={role}>
                    <span className="text-dim">职任：</span>{role}
                  </div>
                  {traits && (
                    <div className="mt-1 text-[11px] text-dim truncate" title={traits}>
                      性情：{traits}
                    </div>
                  )}
                  {m.desc && (
                    <p className="mt-2 text-xs leading-relaxed text-ink/80 line-clamp-2 text-justify font-kai bg-paper/40 p-1.5 rounded">
                      {m.desc}
                    </p>
                  )}
                  </div>
                </div>

                <div className="mt-2 pt-2 border-t border-border/40 flex justify-end">
                  <button
                    onClick={() => openAudience(m.name, role)}
                    className="flex items-center gap-1 rounded bg-red/90 px-3 py-1 font-kai text-xs font-bold tracking-wider text-paper transition hover:bg-red-dark"
                  >
                    <User size={12} /> 御前召对
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* 原有内阁与六部网格 */
        <div className="space-y-5">
          {!state ? (
            <div className="rounded border border-gold/40 bg-card p-8 text-center">
              <p className="font-kai text-base text-ink">尚未建立新朝开局，中枢职司虚位以待。</p>
              <p className="mt-1 font-kai text-xs text-dim">请在上方切换【朝野列卿】浏览北宋名臣档案，或于朝堂开启新局。</p>
            </div>
          ) : (
            <>
              <p className="px-1 text-sm leading-relaxed text-dim">
                朝堂臣工，各有职司；召见入对，垂询天下。凡施政诏令，皆由圣旨推演。
              </p>

      {/* 宰执 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="宰 执" />
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {chancellorCards.map((c) => (
            // D 修复：原 key={c.name} —— 两派系由同一人任领袖时 key 重复（React 警告
            // 且可能错配子树）。改用稳定的「派系+姓名」组合键。
            <MinisterCard key={`${c.faction}-${c.name}`} card={c} gold onAudience={() => openAudience(c.name, c.role)} />
          ))}
        </div>
      </div>

      {/* 派系领袖 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="派 系 领 袖" />
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {leaderCards.map((c) => (
            // D 修复：同上，改用「派系+姓名」组合键，避免同人跨派系时 key 重复。
            <MinisterCard key={`${c.faction}-${c.name}`} card={c} onAudience={() => openAudience(c.name, c.role)} />
          ))}
        </div>
      </div>

      {/* 六部尚书 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="中 枢 六 部 尚 书" />
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {yamenCards.map((c) => (
            <MinisterCard key={c.role} card={c} yamen={c.yamen} onAudience={() => openAudience(c.name, c.role)} />
          ))}
        </div>
      </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function MinisterCard({
  card, gold, yamen, onAudience
}: {
  card: CardInfo;
  gold?: boolean;
  yamen?: Dict;
  onAudience: () => void;
}) {
  // 迁移补齐（原 Tk `_minister_card_data`）：年龄/性情/生平 —— 数据来自 /api/readouts::ministers
  const readouts = useGameStore((s) => s.readouts);
  const profile = (readouts?.ministers?.[card.name] ?? null) as Dict | null;
  const pAge = typeof profile?.age === "number" ? profile.age : null;
  const pFaction = typeof profile?.faction === "string" ? profile.faction : "";
  const pStyle = typeof profile?.style === "string" ? profile.style : "";
  const pBio = typeof profile?.bio === "string" ? profile.bio : "";
  return (
    <div
      className={`flex flex-col rounded-lg border bg-card p-3 ${
        gold ? "border-gold shadow-card" : "border-gold/40"
      }`}
    >
      <div className="flex items-center gap-3">
        <div className="relative h-14 w-12 shrink-0 overflow-hidden rounded border border-gold/60 bg-paper/70 shadow-sm">
          <img
            src={
              typeof profile?.portrait === "string" && profile.portrait
                ? portraitSrc(profile.portrait)
                : card.kind === "military"
                  ? "./portraits/general.png"
                  : "./portraits/minister.png"
            }
            alt={card.name}
            className="h-full w-full object-cover object-top"
          />
        </div>
        <div className="min-w-0">
          <p className="truncate font-kai text-[15px] font-bold text-ink">{card.name}</p>
          <p className="text-xs font-bold text-red">{card.role}</p>
          {(pAge !== null || pFaction) && (
            <p className="text-[11px] text-dim">
              {pAge !== null ? `${pAge} 岁` : ""}
              {pFaction ? `　${pFaction}` : ""}
            </p>
          )}
        </div>
      </div>
      {pStyle ? (
        <p className="mt-1.5 border-t border-gold/20 pt-1.5 text-[11px] leading-relaxed text-ink-light">
          性情：{pStyle}
        </p>
      ) : null}
      {pBio ? (
        <p className="mt-1 text-[11px] leading-relaxed text-dim">{pBio}</p>
      ) : null}
      {yamen && (
        <div className="mt-2 space-y-0.5 border-t border-gold/30 pt-2 text-xs text-dim">
          <p>职掌：{asStr(yamen.duty, "—")}</p>
          <p>
            效率 {String(yamen.efficiency ?? "—")}　积压 {String(yamen.backlog ?? 0)}
          </p>
          {(yamen.acts as string[] | undefined)?.length ? (
            <p className="leading-relaxed">可为：{(yamen.acts as string[]).join("、")}</p>
          ) : null}
        </div>
      )}
      <button
        onClick={onAudience}
        className="mt-2.5 rounded-lg bg-paper/60 px-3 py-1.5 font-kai text-sm font-bold tracking-widest text-ink transition hover:bg-gold-light hover:text-red border border-gold/30"
      >
        御前召对
      </button>
    </div>
  );
}
