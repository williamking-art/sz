import { useState } from "react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";

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
      const res = await getApiClient().resolveEvent(title, idx);
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
        <div className="relative overflow-hidden rounded-lg border border-gold/60 shadow-paper">
          <img
            src={imageSrc}
            alt={title}
            className="h-44 w-full object-cover object-center transition duration-500 hover:scale-105"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent pointer-events-none" />
          <div className="absolute bottom-2 left-3 font-kai text-sm font-bold tracking-widest text-[#f8ecd0] drop-shadow-md">
            【{title}】
          </div>
        </div>
      )}

      <p className="whitespace-pre-wrap font-kai text-sm leading-relaxed text-ink text-justify bg-card/50 p-3 rounded border border-border/40">
        {desc}
      </p>

      {!result && (
        <div className="space-y-2">
          {choices.map((c, i) => (
            <button
              key={i}
              onClick={() => choose(i)}
              disabled={busy}
              className="w-full rounded-lg border border-gold/50 bg-paper/60 px-4 py-2.5 text-left text-sm text-ink transition hover:bg-gold-light disabled:opacity-60"
            >
              {String(c.label ?? c.text ?? c.option ?? `选项 ${i + 1}`)}
            </button>
          ))}
        </div>
      )}

      {result && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-4">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{result}</p>
          <button
            onClick={popOverlay}
            className="mt-3 rounded-lg bg-red px-4 py-1.5 text-sm text-paper transition hover:bg-red-dark"
          >
            关闭
          </button>
        </div>
      )}
    </div>
  );
}