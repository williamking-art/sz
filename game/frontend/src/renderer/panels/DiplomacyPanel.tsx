import { useState } from "react";
import { Globe2, Shield, Heart, AlertTriangle, Send, Loader2, Landmark, Compass } from "lucide-react";
import { useGameStore, pick } from "../store/gameStore";
import { getApiClient } from "../api/client";

// 外交势力区域分组
const DIPLO_GROUPS = [
  {
    title: "北境抗衡",
    keys: ["辽", "西夏", "喀尔喀蒙古", "金"]
  },
  {
    title: "西南与天竺",
    keys: ["大理", "吐蕃诸部", "身毒", "塞尔柱", "高昌回鹘", "喀喇汗"]
  },
  {
    title: "海东列邦",
    keys: ["高丽", "日本", "琉球"]
  },
  {
    title: "南洋交涉",
    keys: ["大越", "占婆", "吴哥", "罗斛", "蒲甘", "澜沧", "三佛齐", "爪哇", "婆罗", "吕宋"]
  }
];

function attitudeText(att: number): { text: string; color: string } {
  if (att >= 80) return { text: "藩属恭顺", color: "text-emerald-700" };
  if (att >= 60) return { text: "和睦通好", color: "text-emerald-600" };
  if (att >= 40) return { text: "羁縻相持", color: "text-amber-700" };
  if (att >= 25) return { text: "猜忌怀异", color: "text-amber-800" };
  return { text: "枕戈待旦", color: "text-red" };
}

export default function DiplomacyPanel() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const [selectedKey, setSelectedKey] = useState<string>("辽");
  const [diplomaticText, setDiplomaticText] = useState("");
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState<string | null>(null);

  if (!state) {
    return <div className="py-12 text-center font-kai text-sm text-dim">尚未开局，万邦方舆未启。</div>;
  }

  const externalRegimes = (pick<Record<string, any>>(state, "external_regimes", {}) || {}) as Record<string, any>;

  const currentInfo = externalRegimes[selectedKey] || {
    name: selectedKey,
    type: "域外政权",
    power: 50,
    attitude: 50,
    internal_pressure: 20
  };

  const att = Number(currentInfo.attitude ?? 50);
  const attInfo = attitudeText(att);
  const power = Number(currentInfo.power ?? 50);
  const pressure = Number(currentInfo.internal_pressure ?? 20);

  async function handleSendEnvoy() {
    if (busy || !diplomaticText.trim()) return;
    setBusy(true);
    setReply(null);
    try {
      // 走自由口谕对话通道（对接大模型外邦使节口吻）
      const res = await getApiClient().action("audience_dialogue", {
        minister: `${selectedKey}国主/正使`,
        text: diplomaticText.trim(),
      });
      setReply(res.message || "国书已由鸿胪寺译进，外夷奉表以闻。");
      setDiplomaticText("");
    } catch (e) {
      setReply("遣使未达：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[520px] flex-col gap-3.5">
      {/* 顶部简述 */}
      <div className="flex items-center justify-between border-b border-gold/40 pb-2">
        <div className="flex items-center gap-2">
          <Globe2 size={18} className="text-red" />
          <span className="font-kai text-base font-bold text-ink">四夷外邦 · 鸿胪宾礼</span>
        </div>
        <span className="font-kai text-xs text-dim">羁縻绥抚 · 兼筹并顾</span>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* 左侧：政权树状目录 */}
        <div className="w-56 space-y-3 overflow-y-auto pr-1">
          {DIPLO_GROUPS.map((grp) => (
            <div key={grp.title} className="space-y-1">
              <div className="font-kai text-xs font-bold tracking-widest text-goldDark px-1">
                ── {grp.title} ──
              </div>
              <div className="space-y-1">
                {grp.keys.map((k) => {
                  const reg = externalRegimes[k];
                  const rAtt = Number(reg?.attitude ?? 50);
                  const isSelected = selectedKey === k;
                  return (
                    <button
                      key={k}
                      onClick={() => {
                        setSelectedKey(k);
                        setReply(null);
                      }}
                      className={`flex w-full items-center justify-between rounded border px-2.5 py-1.5 text-left transition ${
                        isSelected
                          ? "border-red/60 bg-red/10 text-red-dark shadow-sm"
                          : "border-gold/30 bg-paper/50 text-ink hover:border-gold hover:bg-paper"
                      }`}
                    >
                      <span className="font-kai text-sm font-medium">{k}</span>
                      <div className="flex items-center gap-1.5 font-sans text-[10px]">
                        <span className="text-dim">力{reg?.power ?? 50}</span>
                        <span className={attitudeText(rAtt).color}>态{rAtt}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* 右侧：国政详情与国书对答 */}
        <div className="flex flex-1 flex-col justify-between overflow-y-auto rounded-lg border border-gold/50 bg-paper/70 p-4 shadow-paper">
          <div className="space-y-3.5">
            {/* 国号与状态 */}
            <div className="flex items-center justify-between border-b border-gold/30 pb-2">
              <div>
                <span className="font-kai text-2xl font-bold tracking-widest text-ink">
                  {currentInfo.name || selectedKey}
                </span>
                <span className="ml-2 font-kai text-xs text-goldDark">
                  〔{currentInfo.type || "域外邦国"}〕
                </span>
              </div>
              <div className={`font-kai text-sm font-bold ${attInfo.color}`}>
                {attInfo.text}
              </div>
            </div>

            {/* 数值指标三格卡 */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded border border-gold/30 bg-card/60 p-2">
                <div className="flex items-center justify-center gap-1 text-dim text-xs font-kai">
                  <Shield size={12} /> 国力盛衰
                </div>
                <div className="mt-1 font-sans text-lg font-bold text-ink">{power}</div>
              </div>
              <div className="rounded border border-gold/30 bg-card/60 p-2">
                <div className="flex items-center justify-center gap-1 text-dim text-xs font-kai">
                  <Heart size={12} /> 对宋和好
                </div>
                <div className="mt-1 font-sans text-lg font-bold text-ink">{att}</div>
              </div>
              <div className="rounded border border-gold/30 bg-card/60 p-2">
                <div className="flex items-center justify-center gap-1 text-dim text-xs font-kai">
                  <AlertTriangle size={12} /> 内讧压力
                </div>
                <div className="mt-1 font-sans text-lg font-bold text-ink">{pressure}</div>
              </div>
            </div>

            {/* 外交行动快捷指令 */}
            <div className="space-y-1.5">
              <div className="font-kai text-xs font-bold text-red-dark">【御前国书 · 遣使通谕】</div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={diplomaticText}
                  onChange={(e) => setDiplomaticText(e.target.value)}
                  placeholder={`降敕谕${selectedKey}国主（例：敦聘和睦互通互市，或严饬边关勿生衅端）`}
                  className="flex-1 rounded border border-gold/40 bg-card px-3 py-1.5 font-kai text-xs text-ink outline-none focus:border-red"
                />
                <button
                  onClick={handleSendEnvoy}
                  disabled={busy || !diplomaticText.trim()}
                  className="flex items-center gap-1 rounded bg-red px-4 py-1.5 font-kai text-xs font-bold tracking-widest text-paper shadow-sm transition hover:bg-red-dark disabled:opacity-50"
                >
                  {busy ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                  发敕
                </button>
              </div>
            </div>

            {/* 回音反馈 */}
            {reply && (
              <div className="rounded-lg border border-gold/40 bg-card/80 p-3 shadow-sm">
                <div className="font-kai text-xs font-bold text-goldDark mb-1">【夷国回表】</div>
                <p className="font-kai text-xs leading-relaxed text-ink/90 whitespace-pre-wrap">
                  {reply}
                </p>
              </div>
            )}
          </div>

          {/* 底部快捷操作 */}
          <div className="pt-3 border-t border-gold/30 flex items-center justify-between">
            <button
              onClick={() => {
                // 聚焦地图上的该政权
                window.dispatchEvent(
                  new CustomEvent("sz:map-focus", {
                    detail: { name: selectedKey, kind: "regime", props: currentInfo },
                  })
                );
              }}
              className="flex items-center gap-1 rounded border border-gold/40 bg-paper/60 px-3 py-1 font-kai text-xs text-ink transition hover:bg-gold-light"
            >
              <Compass size={13} /> 舆图远眺
            </button>

            <button
              onClick={() => {
                pushOverlay({
                  kind: "decree",
                  title: `拟旨 · ${selectedKey}事务`,
                });
              }}
              className="flex items-center gap-1 rounded border border-red/40 bg-red/10 px-3 py-1 font-kai text-xs text-red transition hover:bg-red/20"
            >
              拟定向该国国策诏敕
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
