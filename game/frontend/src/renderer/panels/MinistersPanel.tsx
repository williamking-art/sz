import { useState } from "react";
import { Loader2, User, Swords } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import constants from "../data/constants.json";

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

// 衙门 faction 简称 → 派系名（panels_govern.py::_FACTION_ALIAS）
const FACTION_ALIAS: Record<string, string> = {
  宦官: "宦官集团",
  西军: "西军集团",
  枢密: "清流言官"
};
// 武臣派系（对齐 _minister_kind：FACTION_PROFILES.kind == military）
const MILITARY_FACTIONS = new Set(["西军集团", "宦官集团"]);

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
  const [dialogue, setDialogue] = useState<{ minister: string; role: string } | null>(null);

  if (!state) {
    return <p className="py-10 text-center text-dim">尚未开局，无群臣可览。</p>;
  }

  const factions = asDict(pick(state, "factions", {}));
  const yamen = asDict(pick(state, "yamen", {}));
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
    const facShort = asStr(y.faction);
    const facName = FACTION_ALIAS[facShort] ?? facShort;
    const leader = asStr(asDict(factions[facName]).leader);
    return {
      name: leader || `${name}堂官`,
      role: `尚书·${name}`,
      faction: facName,
      kind: MILITARY_FACTIONS.has(facName) ? ("military" as const) : ("civil" as const),
      yamen: y
    };
  });

  return (
    <div className="space-y-5">
      <p className="px-1 text-sm leading-relaxed text-dim">
        朝堂臣工，各有职司；召见入对，垂询天下。凡施政诏令，皆由圣旨推演。
      </p>

      {/* 宰执 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="宰 执" />
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {chancellorCards.map((c) => (
            <MinisterCard key={c.name} card={c} gold onAudience={() => setDialogue({ minister: c.name, role: c.role })} />
          ))}
        </div>
      </div>

      {/* 派系领袖 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="派 系 领 袖" />
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {leaderCards.map((c) => (
            <MinisterCard key={c.name} card={c} onAudience={() => setDialogue({ minister: c.name, role: c.role })} />
          ))}
        </div>
      </div>

      {/* 六部尚书 */}
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        <SectionTitle text="中 枢 六 部 尚 书" />
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {yamenCards.map((c) => (
            <MinisterCard key={c.role} card={c} yamen={c.yamen} onAudience={() => setDialogue({ minister: c.name, role: c.role })} />
          ))}
        </div>
      </div>

      {/* 召对浮层（内联展开） */}
      {dialogue && (
        <DialogueBox
          minister={dialogue.minister}
          role={dialogue.role}
          onClose={() => setDialogue(null)}
        />
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
  return (
    <div
      className={`flex flex-col rounded-lg border bg-card p-3 ${
        gold ? "border-gold shadow-card" : "border-gold/40"
      }`}
    >
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-gold/50 bg-paper/70 text-red">
          {card.kind === "military" ? <Swords size={22} /> : <User size={22} />}
        </div>
        <div className="min-w-0">
          <p className="truncate font-kai text-[15px] font-bold text-ink">{card.name}</p>
          <p className="text-xs font-bold text-red">{card.role}</p>
        </div>
      </div>
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
        className="mt-2.5 rounded-lg bg-paper/60 px-3 py-1.5 font-kai text-sm tracking-widest text-ink transition hover:bg-gold-light"
      >
        召见奏对
      </button>
    </div>
  );
}

// 召对条：口谕输入 + AI 奏对回复（对齐 _panel_dialogue 简化版）
function DialogueBox({
  minister, role, onClose
}: {
  minister: string;
  role: string;
  onClose: () => void;
}) {
  const setState = useGameStore((s) => s.setState);
  const [text, setText] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function ask() {
    if (busy || !text.trim()) return;
    setBusy(true);
    setReply(null);
    try {
      const res = await getApiClient().action("audience_dialogue", {
        minister,
        text: text.trim()
      });
      setState(res.state);
      setReply(res.message);
    } catch (e) {
      console.error("[audience_dialogue]", e);
      setReply("召对失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/25 p-4 backdrop-blur-[1px]">
      <div className="flex max-h-[70vh] w-[min(520px,92vw)] flex-col rounded-[4px] border border-gold bg-card shadow-card">
        <div className="flex items-center justify-between border-b border-gold/50 px-5 py-2.5">
          <span className="font-kai text-[19px] tracking-[0.18em] text-ink">召对 · {minister}</span>
          <button onClick={onClose} className="rounded px-2 py-0.5 text-sm text-ink-light transition hover:bg-gold-light hover:text-ink">
            关闭
          </button>
        </div>
        <div className="space-y-3 overflow-y-auto p-5">
          <p className="text-xs text-dim">{role} · 垂询国事，口谕问策</p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            placeholder="口谕（如：今岁国用不足，卿有何策？）"
            className="w-full rounded-lg border border-border bg-paper/70 px-3 py-2 text-sm text-ink outline-none focus:border-gold"
          />
          <div className="flex justify-end">
            <button
              onClick={ask}
              disabled={busy || !text.trim()}
              className="flex items-center gap-2 rounded-lg bg-red px-5 py-1.5 font-kai text-sm tracking-widest text-paper transition hover:bg-red-dark disabled:opacity-60"
            >
              {busy && <Loader2 size={14} className="animate-spin" />}
              {busy ? "奏对中…" : "传 谕"}
            </button>
          </div>
          {reply && (
            <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
              <p className="whitespace-pre-wrap font-kai text-[15px] leading-relaxed text-ink">{reply}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
