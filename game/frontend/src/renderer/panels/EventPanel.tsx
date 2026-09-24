import { useState } from "react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";
import { formatEffects, judgeEffects } from "../utils/effects";

// 历史大事件工笔画卷映射表
const EVENT_ART_MAP: Record<string, string> = {
  fangla_uprising: "./events/fangla_uprising.png",
  方腊起义: "./events/fangla_uprising.png",
  huanghe_flood: "./events/huanghe_flood.png",
  黄河决口: "./events/huanghe_flood.png",
  huashigang: "./events/huashigang.png",
  花石纲: "./events/huashigang.png",
  jin_destroys_liao: "./events/jin_destroys_liao.png",
  金灭辽: "./events/jin_destroys_liao.png",
  jin_invasion: "./events/jin_invasion.png",
  金军南侵: "./events/jin_invasion.png",
  party_strife: "./events/party_strife.png",
  元祐党争: "./events/party_strife.png",
  sea_alliance: "./events/sea_alliance.png",
  海上之盟: "./events/sea_alliance.png",
  songjiang: "./events/songjiang.png",
  宋江起义: "./events/songjiang.png",
  xiangrui: "./events/xiangrui.png",
  祥瑞降世: "./events/xiangrui.png"
};

// 事件抉择弹窗：展示事件描述与选项，选择后 resolve_event
export default function EventPanel({ props }: { props?: Record<string, unknown> }) {
  const event = props?.event as Record<string, unknown> | undefined;
  const title = typeof props?.title === "string" ? props.title : String(event?.title ?? "事件");
  const eventId = typeof event?.id === "string" ? event.id : "";
  const desc = typeof event?.desc === "string" ? event.desc : String(event?.description ?? "");
  const choices = Array.isArray(event?.choices)
    ? (event.choices as Array<Record<string, unknown>>)
    : Array.isArray(event?.options)
      ? (event.options as Array<Record<string, unknown>>)
      : [];
  // 迁移补齐：战略决策点（朱批）角标标记——Tk `panels_meta.py:749` 的 `_break_id`
  const breakId = typeof event?._break_id === "string" ? event._break_id : "";
  const needsConfirm = event?.needs_confirm === true;

  // 获取对应历史工笔插图
  const imageSrc = EVENT_ART_MAP[eventId] || EVENT_ART_MAP[title] || null;

  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const setState = useGameStore((s) => s.setState);
  const popOverlay = useGameStore((s) => s.popOverlay);

  async function choose(idx: number) {
    if (busy) return;
    setBusy(true);
    try {
      const res = await getApiClient().resolveEvent(
        title, idx, typeof event?.id === "string" ? event.id : undefined
      );
      setState(res.state);
      setResult(res.message);
    } catch (e) {
      console.error("[resolve_event]", e);
      setResult("抉择处理失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* 2K 历史事件工笔插图 */}
      {imageSrc && (
        <div className="relative overflow-hidden rounded border border-gold/60 shadow-paper">
          <img
            src={imageSrc}
            alt={title}
            className="h-56 w-full object-cover object-center"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent pointer-events-none" />
          {/* 战略决策角标（迁移补齐：原 Tk `_break_id` → 〔军机·战略决策〕） */}
          {(breakId || needsConfirm) && (
            <span className="absolute left-2 top-2 rounded border border-gold/70 bg-red/85 px-2 py-0.5 font-kai text-[11px] tracking-widest text-[#f3e6c4] shadow-sm">
              军机 · 战略决策
            </span>
          )}
          <div className="absolute bottom-0 left-0 right-0 flex items-end justify-between gap-2 px-3 pb-2">
            <span className="font-kai text-base font-bold tracking-[0.2em] text-[#f8ecd0] drop-shadow-md">
              【{title}】
            </span>
            <img src="/images/seal.png" alt="" className="sz-seal opacity-90" />
          </div>
        </div>
      )}

      <p className="sz-card whitespace-pre-wrap p-3 font-kai text-sm leading-relaxed text-ink text-justify">
        {desc}
      </p>

      {!result && (
        <div className="space-y-2">
          {choices.map((c, i) => {
            // 迁移补齐：选项 effects 预览 + 吉/凶朱批色（原 Tk `_format_effects`/`_judge_effects`）
            const eff = c.effects;
            const effTxt = formatEffects(eff);
            const { good, bad } = judgeEffects(eff);
            const tone =
              good > bad
                ? "border-[#3f6655] bg-[#eef3ec]"
                : bad > good
                  ? "border-red/50 bg-red/5"
                  : "border-gold/40";
            const effColor =
              good > bad ? "text-[#3f6655]" : bad > good ? "text-red" : "text-dim";
            return (
              <button
                key={i}
                onClick={() => choose(i)}
                disabled={busy}
                className={`w-full rounded-lg border px-4 py-2.5 text-left text-sm text-ink transition hover:bg-gold-light/30 disabled:opacity-60 ${tone}`}
              >
                <span className="block">
                  {String(c.label ?? c.text ?? c.option ?? `选项 ${i + 1}`)}
                </span>
                <span className={`mt-0.5 block font-kai text-xs ${effColor}`}>
                  〔{effTxt}〕
                  {good > bad ? "　吉" : bad > good ? "　凶" : ""}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {result && (
        <div className="sz-card p-4">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{result}</p>
          <button onClick={popOverlay} className="sz-btn-primary mt-3 rounded-lg px-4 py-1.5 text-sm">
            关闭
          </button>
        </div>
      )}
    </div>
  );
}