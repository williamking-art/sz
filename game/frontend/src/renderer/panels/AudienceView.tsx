import { useState, useRef, useEffect } from "react";
import { Loader2, X, Send, Heart, Shield, Award, BookOpen, UserCheck, Flame, Scale, Coffee, ThumbsUp, AlertTriangle, UserMinus } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import constants from "../data/constants.json";

interface DialogueTurn {
  id: string;
  speaker: string;
  isEmperor: boolean;
  timeLabel: string;
  actionNote?: string;
  content: string;
}

export default function AudienceView({ props }: { props?: Record<string, unknown> }) {
  const popOverlay = useGameStore((s) => s.popOverlay);
  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);

  const ministerName = String(props?.minister || "韩忠彦");
  const ministerRole = String(props?.role || "尚书左仆射兼门下侍郎");

  // 大臣立绘推导
  const isMilitary = ministerRole.includes("军") || ministerRole.includes("枢密") || ministerRole.includes("将");
  const portraitUrl = isMilitary ? "./portraits/general.png" : "./portraits/minister.png";

  // 大臣所属派系
  const factions = (constants as any).faction_init || {};
  let ministerFaction = "清流正论";
  for (const [fn, fv] of Object.entries(factions) as any) {
    if (fv.leader === ministerName) {
      ministerFaction = fn;
      break;
    }
  }

  // 六维属性与特质参数生成（稳定伪随机）
  let seed = 0;
  for (let i = 0; i < ministerName.length; i++) seed = (seed * 37 + ministerName.charCodeAt(i)) % 10007;
  const stats = {
    loyalty: 75 + (seed % 20),
    reputation: 80 + ((seed * 3) % 18),
    courage: 70 + ((seed * 7) % 25),
    military: isMilitary ? 85 + ((seed * 11) % 12) : 50 + ((seed * 11) % 25),
    govern: 82 + ((seed * 13) % 16),
    scholar: isMilitary ? 65 + ((seed * 17) % 20) : 88 + ((seed * 17) % 11)
  };

  const traits = [
    ministerFaction,
    isMilitary ? "经略九边" : "深谋远虑",
    stats.loyalty >= 85 ? "忠直刚方" : "顾全大局",
    stats.govern >= 90 ? "治国干城" : "老成持重"
  ];

  // 历史对白记录流
  const era = state ? `${pick<string>(state, "era_name", "建中靖国")}${pick<number>(state, "year", 1101)}年${pick<number>(state, "month", 1)}月` : "建中靖国元年正月";
  
  const [turns, setTurns] = useState<DialogueTurn[]>([
    {
      id: "init-1",
      speaker: ministerName,
      isEmperor: false,
      timeLabel: `${ministerName} · ${era}`,
      actionNote: "（肃立御案前，展角幞头微垂，拱手端肃而立，目光恭慎而沉毅）",
      content: `臣【${ministerName}】蒙陛下召对垂询，敢不竭愚竭虑，上裨圣明。今朝廷纲维初定，四方政务繁剧，陛下有何谕示，臣敬聆圣裁。`
    }
  ]);

  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns, busy]);

  async function handleSend(textToSend?: string) {
    const text = (textToSend || input).trim();
    if (busy || !text) return;

    const userTurn: DialogueTurn = {
      id: `u-${Date.now()}`,
      speaker: "皇帝陛下",
      isEmperor: true,
      timeLabel: `御批天谕 · ${era}`,
      content: text
    };
    setTurns((prev) => [...prev, userTurn]);
    if (!textToSend) setInput("");
    setBusy(true);

    try {
      const res = await getApiClient().action("audience_dialogue", {
        minister: ministerName,
        text
      });
      if (res.state) setState(res.state);

      const aiReply = res.message || "臣敬遵温谕，必体察上意，恭谨奉行。";
      const replyTurn: DialogueTurn = {
        id: `m-${Date.now()}`,
        speaker: ministerName,
        isEmperor: false,
        timeLabel: `${ministerName} · ${era}`,
        actionNote: "（闻天语温切，躬身再拜，肃容敬答）",
        content: aiReply
      };
      setTurns((prev) => [...prev, replyTurn]);
    } catch (e) {
      const errTurn: DialogueTurn = {
        id: `err-${Date.now()}`,
        speaker: ministerName,
        isEmperor: false,
        timeLabel: `${ministerName} · 传谕受阻`,
        actionNote: "（有司飞报，奏对有碍）",
        content: `奏对有阻：${e instanceof Error ? e.message : String(e)}`
      };
      setTurns((prev) => [...prev, errTurn]);
    } finally {
      setBusy(false);
    }
  }

  // 快捷公文与君臣互动行止
  function handleAction(act: string) {
    if (act === "准奏") {
      handleSend("准卿所奏，着中书、门下速拟明诏颁行。");
    } else if (act === "赐茶") {
      handleSend("卿经年国事鞅掌，内侍，且赐顾渚紫笋御茶，为卿解乏。");
    } else if (act === "抚慰") {
      handleSend("朕知卿一片体国忠诚，虽毁誉并至，朕自为卿洞察。");
    } else if (act === "敲打") {
      handleSend("近来朝堂朋党攻讦日烈，卿领袖群伦，当谨防任私徇情，清肃门生。");
    } else if (act === "问财政") {
      handleSend("今岁国库二税与两浙商榷岁入实收几何？仓庾可充兵食否？");
    } else if (act === "问边防") {
      handleSend("北疆辽夏兵甲动向如何？各路军帅整备坚壁可足御敌？");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col select-text font-kai overflow-hidden">
      {/* 1. 深度宫阙水墨背景（全屏包裹） */}
      <div
        className="absolute inset-0 bg-cover bg-center transition-all duration-700"
        style={{ backgroundImage: `url(./images/court_bg.png)` }}
      >
        <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/75 to-black/80 backdrop-blur-[2px]" />
      </div>

      {/* 2. 顶部金色端庄仪仗栏 */}
      <div className="relative z-10 flex items-center justify-between border-b border-gold/40 bg-black/40 px-6 py-2.5 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red ring-1 ring-gold shadow-md">
            <span className="font-kai text-[17px] font-bold text-[#f5ebd3]">宋</span>
          </div>
          <div>
            <h1 className="font-kai text-[18px] font-bold tracking-[0.25em] text-[#f5ebd3]">
              大 宋 垂 拱 殿 · 御 前 召 对
            </h1>
            <p className="font-kai text-[11.5px] text-gold/80 tracking-wider">
              天子亲询中枢大僚 · 言路通达 · {era}
            </p>
          </div>
        </div>

        <button
          onClick={() => popOverlay()}
          className="flex items-center gap-1.5 rounded border border-gold/40 bg-card/10 px-3.5 py-1 text-xs font-bold text-paper transition hover:border-gold hover:bg-gold/20 hover:text-white"
        >
          <X size={15} /> 退出召对
        </button>
      </div>

      {/* 3. 核心双栏主舞台（左立绘身份，右长卷对白） */}
      <div className="relative z-10 flex flex-1 overflow-hidden px-6 py-4 gap-6">
        {/* 左侧：大臣立绘 + 宣纸六维卡片 (~32%) */}
        <div className="flex w-[340px] shrink-0 flex-col justify-between">
          {/* 大臣大立绘展示位 */}
          <div className="relative flex flex-1 items-end justify-center overflow-hidden rounded-t-[4px] border-t border-x border-gold/50 bg-gradient-to-t from-black/60 via-transparent to-transparent">
            <img
              src={portraitUrl}
              alt={ministerName}
              className="max-h-[85%] w-auto object-contain filter drop-shadow-[0_12px_24px_rgba(0,0,0,0.8)]"
            />
            {/* 顶部品阶标签 */}
            <div className="absolute top-3 left-3 rounded border border-gold/50 bg-black/70 px-2.5 py-1 text-[11.5px] font-bold text-gold tracking-widest backdrop-blur-sm">
              正一品 · 中枢枢辅
            </div>
          </div>

          {/* 下方宣纸质感身份与属性面板 */}
          <div className="rounded-b-[4px] border border-gold/60 bg-[#fbf7ed] p-3.5 shadow-2xl text-ink">
            {/* 姓名与派系标签 */}
            <div className="flex items-baseline justify-between border-b border-gold/40 pb-2">
              <span className="font-kai text-[20px] font-bold text-ink tracking-widest">
                {ministerName}
              </span>
              <span className="rounded bg-red/10 border border-red/30 px-2 py-0.5 text-[11.5px] font-bold text-red">
                {ministerFaction}
              </span>
            </div>
            <p className="mt-1 text-[12px] font-bold text-goldDark truncate">
              {ministerRole}
            </p>

            {/* 六维属性横排条（对齐参考图样式） */}
            <div className="mt-2.5 grid grid-cols-3 gap-1.5 text-center text-[11px] font-sans">
              <div className="rounded border border-gold/30 bg-card py-1">
                <span className="text-dim">忠诚</span> <strong className="text-red font-kai">{stats.loyalty}</strong>
              </div>
              <div className="rounded border border-gold/30 bg-card py-1">
                <span className="text-dim">清誉</span> <strong className="text-ink font-kai">{stats.reputation}</strong>
              </div>
              <div className="rounded border border-gold/30 bg-card py-1">
                <span className="text-dim">胆识</span> <strong className="text-ink font-kai">{stats.courage}</strong>
              </div>
              <div className="rounded border border-gold/30 bg-card py-1">
                <span className="text-dim">武略</span> <strong className="text-ink font-kai">{stats.military}</strong>
              </div>
              <div className="rounded border border-gold/30 bg-card py-1">
                <span className="text-dim">理政</span> <strong className="text-ink font-kai">{stats.govern}</strong>
              </div>
              <div className="rounded border border-gold/30 bg-card py-1">
                <span className="text-dim">学识</span> <strong className="text-ink font-kai">{stats.scholar}</strong>
              </div>
            </div>

            {/* 大臣特质词卡 */}
            <div className="mt-2.5 flex flex-wrap gap-1">
              {traits.map((tr) => (
                <span key={tr} className="rounded bg-paper px-1.5 py-0.5 text-[10.5px] text-dim border border-border">
                  #{tr}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧：长卷对白对话流 (~68%) */}
        <div className="flex flex-1 flex-col rounded-[4px] border border-gold/60 bg-[#f9f5ea]/95 shadow-2xl overflow-hidden">
          {/* 对白卷轴流主体 */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
            {turns.map((t) => (
              <div
                key={t.id}
                className={`flex flex-col animate-card-in ${
                  t.isEmperor ? "items-end" : "items-start"
                }`}
              >
                {/* 说话人与时节 */}
                <div className="flex items-center gap-2 mb-1 text-[11.5px] text-dim px-1">
                  <span className="font-bold">{t.timeLabel}</span>
                </div>

                {/* 动作细节描写（灰色宋体斜体，参考图核心神韵） */}
                {t.actionNote && (
                  <div className="max-w-[85%] text-[12px] italic text-dim/90 mb-1.5 px-2 leading-relaxed">
                    {t.actionNote}
                  </div>
                )}

                {/* 对话正文长卷 */}
                <div
                  className={`relative max-w-[88%] rounded-lg p-3.5 shadow-sm text-[14.5px] leading-relaxed border ${
                    t.isEmperor
                      ? "border-red/40 bg-red/10 text-red-dark font-medium"
                      : "border-gold/40 bg-card text-ink font-normal"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{t.content}</p>
                </div>
              </div>
            ))}

            {busy && (
              <div className="flex items-center gap-2 text-dim text-xs py-2 px-1">
                <Loader2 size={14} className="animate-spin text-goldDark" />
                <span>大臣深思谋定，正拟奏对草疏中…</span>
              </div>
            )}
          </div>

          {/* 底部圣意交互区 */}
          <div className="border-t border-gold/40 bg-[#f4ebd6] p-3 space-y-2.5">
            {/* 上层：预置决策快速操作条 */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[12px] font-bold text-red-dark mr-1">圣意亲裁：</span>
              <button
                onClick={() => handleAction("准奏")}
                disabled={busy}
                className="flex items-center gap-1 rounded bg-red px-3 py-1 text-xs font-bold text-paper shadow-sm hover:bg-red-dark transition disabled:opacity-50"
              >
                <ThumbsUp size={12} /> 准 奏
              </button>
              <button
                onClick={() => handleAction("赐茶")}
                disabled={busy}
                className="flex items-center gap-1 rounded border border-gold/60 bg-paper px-2.5 py-1 text-xs text-ink hover:bg-gold-light transition disabled:opacity-50"
              >
                <Coffee size={12} className="text-goldDark" /> 赐御茶
              </button>
              <button
                onClick={() => handleAction("抚慰")}
                disabled={busy}
                className="flex items-center gap-1 rounded border border-gold/60 bg-paper px-2.5 py-1 text-xs text-ink hover:bg-gold-light transition disabled:opacity-50"
              >
                <Heart size={12} className="text-red" /> 勉励抚慰
              </button>
              <button
                onClick={() => handleAction("敲打")}
                disabled={busy}
                className="flex items-center gap-1 rounded border border-gold/60 bg-paper px-2.5 py-1 text-xs text-ink hover:bg-gold-light transition disabled:opacity-50"
              >
                <AlertTriangle size={12} className="text-amber-800" /> 申饬戒骄
              </button>
              <button
                onClick={() => handleAction("问财政")}
                disabled={busy}
                className="rounded border border-gold/60 bg-paper px-2.5 py-1 text-xs text-ink hover:bg-gold-light transition disabled:opacity-50"
              >
                问钱粮亏盈
              </button>
              <button
                onClick={() => handleAction("问边防")}
                disabled={busy}
                className="rounded border border-gold/60 bg-paper px-2.5 py-1 text-xs text-ink hover:bg-gold-light transition disabled:opacity-50"
              >
                问辽夏戎备
              </button>
            </div>

            {/* 下层：长条宣纸传旨输入框 */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                disabled={busy}
                placeholder={`向 ${ministerName} 传达圣意口谕（例：今岁边患频起，卿有何经略之策？直接敲 Enter 发送）`}
                className="flex-1 rounded border border-gold/60 bg-card px-3.5 py-2 text-[14px] text-ink outline-none focus:border-red shadow-inner placeholder:text-dim/60"
              />
              <button
                onClick={() => handleSend()}
                disabled={busy || !input.trim()}
                className="flex items-center gap-1.5 rounded bg-red px-5 py-2 text-sm font-bold tracking-widest text-paper shadow-card hover:bg-red-dark transition disabled:opacity-50"
              >
                {busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                传 谕
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
