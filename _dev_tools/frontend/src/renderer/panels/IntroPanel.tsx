import { useGameStore, pick } from "../store/gameStore";

// 开局引子 + 邸报 + 「登基治国」入局仪式
// 迁移补齐：对齐 Tk game/ui/panels_menu.py::_show_intro（L173-217）——
//   Tk 版为「建中靖国元年 · 春正月」横幅 + 引子正文 + 开局邸报（含按语）+ 入局按钮，
//   Web 此前直接 setInGame(true) 进舆图，整段新局叙事缺失。
type Dict = Record<string, unknown>;

const INTRO_TEXT =
  "元符三年，向太后垂帘，立端王赵佶为帝。\n\n" +
  "新帝登基，年号建中靖国，意在新旧两党之间调停中正，以靖国家。" +
  "朝堂之上，新党蔡京卷土重来之势渐显，旧党元祐诸臣仍据要津。" +
  "宦官童贯深得帝心，西军种师道枕戈待旦……\n\n" +
  "而你，就是这位年仅十九岁的新天子——赵佶。\n\n" +
  "你的每一个决定，都将影响大宋国祚的命运。\n是重蹈史实，还是中兴大宋？";

function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}

export default function IntroPanel() {
  const state = useGameStore((s) => s.state);
  const clearOverlays = useGameStore((s) => s.clearOverlays);
  const gazette = (pick<Dict>(state, "opening_gazette", {}) || {}) as Dict;
  const tasks = Array.isArray(gazette.tasks) ? (gazette.tasks as Dict[]) : [];

  return (
    <div className="space-y-4">
      {/* 纪年横幅 */}
      <div className="-mx-4 -mt-4 rounded-t bg-red px-4 py-3 text-center">
        <p className="font-kai text-xl font-bold tracking-[0.35em] text-[#f3e6c4]">
          建中靖国元年 · 春正月
        </p>
      </div>

      {/* 引子正文 */}
      <p className="whitespace-pre-wrap px-1 font-kai text-[15px] leading-loose text-ink text-justify">
        {INTRO_TEXT}
      </p>

      {/* 开局邸报（含按语） */}
      {Object.keys(gazette).length > 0 && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <p className="text-center font-kai text-base tracking-widest text-ink">
            {asStr(gazette.header)} · {asStr(gazette.era)}
          </p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink">
            {asStr(gazette.body)}
          </p>
          {tasks.map((t, i) => (
            <p key={i} className="py-0.5 text-sm text-ink">
              {t.urgent ? "●" : "○"} {asStr(t.title)}：{asStr(t.desc)}
            </p>
          ))}
          {asStr(gazette.hint) && (
            <p className="mt-1.5 border-t border-gold/20 pt-1.5 font-kai text-xs leading-relaxed text-dim">
              〔按语〕{asStr(gazette.hint)}
            </p>
          )}
        </div>
      )}

      <div className="flex justify-center pt-1">
        <button
          onClick={clearOverlays}
          className="rounded-lg bg-gradient-to-r from-red to-red-dark px-10 py-2.5 font-kai text-base font-bold tracking-[0.3em] text-[#f8ecd0] shadow-card ring-1 ring-gold transition hover:scale-105"
        >
          登 基 治 国
        </button>
      </div>
    </div>
  );
}
