import { useState, useRef, useEffect } from "react";
import { Loader2, X, Send, Heart, Coffee, ThumbsUp, AlertTriangle } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import ministersDict from "../data/ministers_dict.json";

interface DialogueTurn {
  id: string;
  speaker: string;
  isEmperor: boolean;
  timeLabel: string;
  actionNote?: string;
  content: string;
}

interface MinisterMeta {
  role: string;
  faction: string;
  traits: string;
  nobility: string;
  rank: string;
  in_office: boolean;
}

export default function AudienceView({ props }: { props?: Record<string, unknown> }) {
  const popOverlay = useGameStore((s) => s.popOverlay);
  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);

  const ministerName = String(props?.minister || "韩忠彦");

  // 1. 优先从权威字典查询该大臣史实职衔与派系，彻底杜绝从列表传进来的泛化“堂官/领袖”字符串
  const dictInfo = ((ministersDict as Record<string, MinisterMeta>)[ministerName]) || null;
  const ministerRole = dictInfo?.role || String(props?.role || "执政大臣");
  const ministerFaction = dictInfo?.faction || "清流正论";

  // 2. 官品与爵位双轨呈现（依据宋代官制铁律）：
  //    - 官品（rank）= 职事官阶，仅在朝为官者具备；在野/贬谪者官品空缺，绝不臆造；
  //    - 爵位（nobility）= 身分性荣誉，虽贬谪在野仍保留（如国公/郡王/县公）。
  const officialRank = dictInfo?.rank || "";
  const nobleTitle = dictInfo?.nobility || "";

  // 3. 大臣立绘推导
  const isMilitary = ministerRole.includes("军") || ministerRole.includes("枢密") || ministerRole.includes("将") || ministerRole.includes("节度");
  const portraitUrl = isMilitary ? "./portraits/general.png" : "./portraits/minister.png";

  // 4. 六维属性与特质参数生成（稳定伪随机）
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

  // 特质标签（纯正中文标签，完全剥离前置 # 符号，对齐古代书契印鉴风格）
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

  // 根据大臣专业职掌分类 + 大宋当前国情态势，高度精准派生对应的圣意选项
  interface PolicyOption {
    label: string;
    badge: string;
    text: string;
    isPrimary?: boolean;
  }

  function getDynamicOptions(): PolicyOption[] {
    const opts: PolicyOption[] = [];
    const treasury = state ? pick<number>(state, "treasury", 5000000) : 5000000;
    const granary = state ? pick<number>(state, "granary", 15000000) : 15000000;
    const canalBlock = state ? pick<number>(state, "canal_block", 10) : 10;
    const external = (state as any)?.external || {};
    const liaoAtt = external["辽"]?.attitude ?? 50;
    const xixiaAtt = external["西夏"]?.attitude ?? 50;
    const activeEvents = (state as any)?.active_events || [];

    // 1. 核心定策：准奏
    opts.push({
      label: "准 奏",
      badge: "敕旨",
      text: "准卿所奏，着中书、门下及该管衙门速拟明诏颁行，毋得稽迟。",
      isPrimary: true
    });

    // 2. 根据大臣真实职权精确分类派生专业选项
    if (isMilitary || ministerRole.includes("枢密") || ministerRole.includes("边") || ministerRole.includes("帅")) {
      // 军事/边防枢臣
      if (liaoAtt < 40 || xixiaAtt < 40) {
        opts.push({
          label: "九边饬备",
          badge: "戎备",
          text: "北疆辽夏塞上烽火戒严，卿总司枢府兵要，着即严饬河东、河北诸关隘坚壁清野，严防谍探。"
        });
      }
      opts.push({
        label: "点检禁厢",
        badge: "治军",
        text: "三衙禁军与各路厢军月粮饷钱可曾足额？老弱羸病者当速核定，整军经武。"
      });
      opts.push({
        label: "边贸榷场",
        badge: "互市",
        text: "辽夏近来边贸互市虚实如何？铁货茶引走私有无边吏私纵情弊？"
      });
    } else if (
      ministerRole.includes("相") ||
      ministerRole.includes("仆射") ||
      ministerRole.includes("侍郎") ||
      ministerRole.includes("门下") ||
      ministerRole.includes("中书")
    ) {
      // 宰相/三省宰执
      opts.push({
        label: "调停党争",
        badge: "朝局",
        text: "自建中靖国以来，朝堂新旧相攻，朋党蔓延。卿位极人臣，当如何调停众论，以安社稷？"
      });
      if (treasury < 4000000) {
        opts.push({
          label: "度支节流",
          badge: "度支",
          text: "目下国库用度日紧，三冗耗费颇巨。中书当速定裁汰冗官、省减浮费之策以充府库。"
        });
      } else {
        opts.push({
          label: "宽免积欠",
          badge: "恤民",
          text: "岁入尚安，江淮数路积年逃税包税亏欠，可议除豁免二分，以苏疲瘵。"
        });
      }
      opts.push({
        label: "整饬铨选",
        badge: "大政",
        text: "考课之法久废，请卿会同吏部严核中外荐举，务求公允。"
      });
    } else if (ministerRole.includes("户部") || ministerRole.includes("转运") || ministerRole.includes("理财")) {
      // 户部/财税重臣
      opts.push({
        label: "核查两税",
        badge: "赋税",
        text: "目下诸路夏秋两税实收与折色成数几何？隐漏逃税之田当如何稽核？"
      });
      opts.push({
        label: "平粜常平",
        badge: "仓庾",
        text: "常平太仓粮储与各路仓窖积粟足支几何？米价平籴平粜之政宜早为计。"
      });
    } else if (
      ministerRole.includes("御史") ||
      ministerRole.includes("司谏") ||
      ministerRole.includes("正言") ||
      ministerRole.includes("台") ||
      ministerRole.includes("谏")
    ) {
      // 言官台谏清流
      opts.push({
        label: "弹劾贪墨",
        badge: "风宪",
        text: "言路乃天下喉舌，近来内外百僚若有专权奸弊、贪墨渔利者，卿等自可直斥上闻。"
      });
      opts.push({
        label: "整肃言路",
        badge: "谏议",
        text: "台谏论事当秉公体国，切不可借言事攻讦异己，陷入朋党倾轧之弊。"
      });
    } else if (ministerRole.includes("工部") || ministerRole.includes("营造") || ministerRole.includes("修内司")) {
      // 工部营造
      opts.push({
        label: "督办营造",
        badge: "工役",
        text: "京畿修缮水利与军器修造工费度支如何？务使工物精纯，毋劳民伤财。"
      });
    } else {
      // 通用卿僚
      opts.push({
        label: "勤修厥职",
        badge: "勤政",
        text: "卿在所司宜尽心奉职，凡有关于军国利害之实务，毋得隐匿瞻顾。"
      });
    }

    // 3. 结合当前大宋宏观国情动态补充紧迫危机
    if (canalBlock >= 20) {
      opts.push({
        label: "疏浚漕纲",
        badge: "急务",
        text: "汴河淮泗漕运梗阻，江淮纲船阻滞。着发工匠民夫疏浚浅涩，按期上供太仓。"
      });
    } else if (granary < 10000000) {
      opts.push({
        label: "平抑粮价",
        badge: "仓庾",
        text: "常平仓粮储见底，京畿米价腾贵。卿当严查豪商囤积，平籴平粜以安市井。"
      });
    } else if (activeEvents.length > 0) {
      const topEv = activeEvents[0];
      const evName = topEv.title || topEv.category || "四方奏报";
      opts.push({
        label: "应对边报",
        badge: "急报",
        text: `近日地方有报【${evName}】，物议鼎沸。卿身为朝廷栋梁，可有周全应对之方？`
      });
    }

    // 4. 经典君臣情境互动
    opts.push({
      label: "赐顾渚紫笋",
      badge: "皇恩",
      text: "卿国事鞅掌，夙夜在公。内侍，特赐顾渚紫笋御茶一橐，以彰劳绩。"
    });
    opts.push({
      label: "戒骄申饬",
      badge: "戒勉",
      text: "位高权重更当谨慎自守，毋任门生亲故擅作威福，引惹言路台谏非议。"
    });

    return opts;
  }

  const dynamicOptions = getDynamicOptions();

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
      <div className="relative z-10 flex items-center justify-between border-b border-gold/40 bg-black/50 px-6 py-2.5 backdrop-blur-sm shadow-md">
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

      {/* 3. 核心双栏主舞台（左立绘顶天立地，右长卷对白） */}
      <div className="relative z-10 flex flex-1 overflow-hidden px-6 pt-2 pb-4 gap-6">
        {/* 左侧：大臣立绘顶头全幅展现 + 宣纸属性面板 (~32%) */}
        <div className="flex w-[340px] shrink-0 flex-col justify-between h-full">
          {/* 大臣大立绘展示位：立绘顶头全高展示，无多余顶部留白 */}
          <div className="relative flex flex-1 items-end justify-center overflow-hidden rounded-t-[4px] border-t border-x border-gold/50 bg-gradient-to-t from-black/70 via-black/20 to-transparent">
            <img
              src={portraitUrl}
              alt={ministerName}
              className="h-full max-h-none w-auto object-cover object-top filter drop-shadow-[0_12px_24px_rgba(0,0,0,0.85)] scale-105 transform origin-top"
            />
            {/* 顶部官阶/爵位标签：官品标官职之侧（在朝），爵位独立尊显（在野保留爵、白身示「布衣」） */}
            <div className="absolute top-2 left-2 flex flex-col gap-1 items-start">
              {officialRank && (
                <div className="rounded border border-gold/60 bg-black/80 px-2.5 py-1 text-[11.5px] font-bold text-gold tracking-widest backdrop-blur-sm shadow-md">
                  {officialRank}
                </div>
              )}
              {nobleTitle && (
                <div className="rounded border border-red/60 bg-red-950/70 px-2.5 py-1 text-[11.5px] font-bold text-[#f2d3a0] tracking-widest backdrop-blur-sm shadow-md">
                  {nobleTitle}
                </div>
              )}
              {!officialRank && !nobleTitle && (
                <div className="rounded border border-border/60 bg-black/60 px-2.5 py-1 text-[11.5px] font-bold text-[#c9bda0] tracking-widest backdrop-blur-sm">
                  白身布衣
                </div>
              )}
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

            {/* 六维属性横排条 */}
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

            {/* 大臣特质词卡：完全去除 # 符号，采用古雅方印徽标签 */}
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {traits.map((tr) => (
                <span key={tr} className="rounded bg-paper px-2 py-0.5 text-[11px] font-kai font-medium text-dim border border-gold/30 shadow-xs">
                  {tr}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧：长卷对白对话流 (~68%) */}
        <div className="flex flex-1 flex-col rounded-[4px] border border-gold/60 bg-[#f9f5ea]/95 shadow-2xl overflow-hidden h-full">
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
            {/* 上层：基于大宋当前局势与大臣职权动态派生的决策命令标签条 */}
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[12px] font-bold text-red-dark mr-1">圣意亲裁：</span>
              {dynamicOptions.map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => handleSend(opt.text)}
                  disabled={busy}
                  title={opt.text}
                  className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-bold transition shadow-sm disabled:opacity-50 ${
                    opt.isPrimary
                      ? "bg-red text-paper hover:bg-red-dark"
                      : "border border-gold/60 bg-paper text-ink hover:bg-gold-light hover:border-gold hover:text-red"
                  }`}
                >
                  <span className={`text-[9.5px] px-1 py-0.2 rounded font-sans ${opt.isPrimary ? "bg-black/20 text-gold-light" : "bg-gold/15 text-goldDark"}`}>
                    {opt.badge}
                  </span>
                  <span>{opt.label}</span>
                </button>
              ))}
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
                placeholder={`向 ${ministerName} 传达圣意口谕（例：卿身为朝廷柱石，有何经略之策？直接敲 Enter 发送）`}
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
