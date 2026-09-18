import { useState } from "react";
import { Globe2, Shield, Heart, AlertTriangle, Send, Loader2, Landmark, Compass } from "lucide-react";
import { useGameStore, pick } from "../store/gameStore";
import { getApiClient } from "../api/client";

// 外交势力区域分组（**排序白名单**，与 game/ui/panels_govern.py::_DIPLO_GROUPS 同源全 41 政权；
// Tk 废弃后此表为唯一映射源）。
// 审查 P2 修复：原前端硬编码 4 组约 23 个政权（缺建州/察哈尔/安南/占城/真腊/暹罗/缅甸/注辇/
// 西辽/汪古部/柔佛/苏门答剌/美洛居/渤泥 等），且对局中不存在的键用默认 50/50/20 兜底
// → 会显示局中并无的政权。现名录一律从 state.external_regimes 派生，白名单只决定分组与排序。
const DIPLO_GROUPS: { title: string; keys: string[] }[] = [
  {
    title: "北方与西北",
    keys: ["辽", "西夏", "吐蕃", "喀尔喀蒙古", "漠南蒙古", "科尔沁",
           "察哈尔", "海西", "建州", "东海"]
  },
  { title: "东 方", keys: ["高丽", "日本", "琉球"] },
  {
    title: "西南与南方",
    keys: ["大理", "安南", "大越", "占城", "占婆", "真腊", "吴哥",
           "暹罗", "罗斛", "澜沧", "缅甸", "蒲甘", "喜马拉雅山南诸国"]
  },
  {
    title: "中亚南亚",
    keys: ["注辇", "身毒", "西辽", "高昌回鹘", "塞尔柱", "喀喇汗", "汪古部"]
  },
  {
    title: "南 洋",
    keys: ["三佛齐", "吕宋", "柔佛", "苏门答剌", "婆罗", "爪哇", "美洛居", "渤泥"]
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
  const [selProv, setSelProv] = useState<string | null>(null);

  if (!state) {
    return <div className="py-12 text-center font-kai text-sm text-dim">尚未开局，万邦方舆未启。</div>;
  }

  const externalRegimes = (pick<Record<string, any>>(state, "external_regimes", {}) || {}) as Record<string, any>;
  // 名录派生（审查 P2）：白名单只定分组/顺序，实际政权一律取自 external_regimes；
  // 未列入白名单者（后续新增政权）归入「其余邦交」，不再凭空显示局中不存在的政权。
  const _listed = new Set(DIPLO_GROUPS.flatMap((g) => g.keys));
  const groups = [
    ...DIPLO_GROUPS.map((g) => ({
      title: g.title,
      keys: g.keys.filter((k) => k in externalRegimes)
    })),
    { title: "其余邦交", keys: Object.keys(externalRegimes).filter((k) => !_listed.has(k)) }
  ].filter((g) => g.keys.length > 0);
  const allKeys = groups.flatMap((g) => g.keys);
  const currentKey = allKeys.includes(selectedKey) ? selectedKey : (allKeys[0] ?? "");
  const currentInfo = currentKey ? (externalRegimes[currentKey] || {}) : {};
  // 玩法真值在 state.external（诏令 external_* 效果、事件、岁币、金入侵均写此处）；
  // external_regimes 为静态底数 + 月度 ±2 随机游走。故真值优先、静态兜底。
  const externalLive = (pick<Record<string, any>>(state, "external", {}) || {}) as Record<string, any>;
  const currentLive = currentKey ? (externalLive[currentKey] || {}) : {};

  const att = Number(currentLive.attitude ?? currentInfo.attitude ?? 50);
  const attInfo = attitudeText(att);
  const power = Number(currentLive.power ?? currentInfo.power ?? 50);
  const pressure = Number(currentLive.internal_pressure ?? currentInfo.internal_pressure ?? 20);

  async function handleSendEnvoy() {
    if (busy || !diplomaticText.trim()) return;
    setBusy(true);
    setReply(null);
    try {
      // 走外交专用通道（国主 persona + 协议落地）。
      // 原走 audience_dialogue（把外国君主当大臣召对）→ 协议永不落地、
      // state.treaties 恒空、本页「条约」栏永久无内容。
      const res = await getApiClient().action("envoy_diplomacy", {
        target: currentKey,
        speech: diplomaticText.trim(),
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
          {groups.map((grp) => (
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
                        setSelProv(null);
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
                  {currentInfo.name || currentKey || "（万邦未启）"}
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

            {/* 外邦省份（对齐 Tk _panel_external_province：人口/军队/建筑） */}
            {(() => {
              const provs = Array.isArray(currentInfo.provinces)
                ? (currentInfo.provinces as Record<string, unknown>[])
                : [];
              if (provs.length === 0) return null;
              const cur = selProv
                ? provs.find((p) => p.name === selProv)
                : null;
              return (
                <div className="rounded border border-gold/40 bg-card/50 p-2">
                  <div className="mb-1.5 flex flex-wrap items-center gap-1.5 font-kai text-xs text-dim">
                    <span className="font-bold text-red-dark">【诸 省】</span>
                    {provs.map((p) => {
                      const name = String(p.name || "");
                      return (
                        <button
                          key={name}
                          onClick={() => setSelProv(name === selProv ? null : name)}
                          className={`rounded px-1.5 py-0.5 transition ${
                            selProv === name
                              ? "bg-red text-paper"
                              : "bg-gold-light/50 text-ink hover:bg-gold-light"
                          }`}
                        >
                          {name}
                        </button>
                      );
                    })}
                  </div>
                  {cur && (
                    <div className="space-y-1 font-sans text-[11px] text-ink-light">
                      <p>
                        人口：在籍 {Number(cur.population || 0).toLocaleString()} 口　占国{" "}
                        {Math.round(Number(cur.weight || 0) * 100)}%
                      </p>
                      {(() => {
                        const armies = Array.isArray(cur.armies)
                          ? (cur.armies as Record<string, unknown>[])
                          : [];
                        if (armies.length === 0) return <p>军队：尚无常备军</p>;
                        return (
                          <div>
                            <p className="font-kai font-bold text-dim">军队</p>
                            {armies.map((a, i) => {
                              const br = (a.branches || {}) as Record<string, number>;
                              const btxt = Object.entries(br)
                                .map(([k, v]) => `${k}${Number(v).toLocaleString()}`)
                                .join("、");
                              return (
                                <p key={i}>
                                  {String(a.name || "")}　员 {Number(a.troops || 0).toLocaleString()}　
                                  气 {String(a.morale ?? "—")}　训 {String(a.training ?? "—")}
                                  {btxt ? `　${btxt}` : ""}
                                </p>
                              );
                            })}
                          </div>
                        );
                      })()}
                      {(() => {
                        const bld = (cur.buildings || {}) as Record<string, number>;
                        const keys = Object.keys(bld);
                        if (!keys.length) return null;
                        return (
                          <p>
                            建筑：{keys.map((k) => `${k}×${bld[k]}`).join("　")}
                          </p>
                        );
                      })()}
                    </div>
                  )}
                </div>
              );
            })()}

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
